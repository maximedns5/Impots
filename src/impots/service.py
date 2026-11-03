"""La couche de service : ce que l'API, la CLI, les scénarios, les programmes, les études
et les scripts appellent pour chiffrer (but 14, D-336).

Elle vivait dans `api/main.py`, en fonctions privées que le domaine importait de l'API :
`scenarios.py` et `programme_chiffrage.py` dépendaient de FastAPI (audit du but 14,
annexe 2, § 4.3). Ici, des noms publics, et aucune dépendance au serveur : un refus est une
`ServiceError`, qui porte le statut HTTP que l'API lui donne (`api.main._served`) et la
raison que la CLI imprime. Le code a été déplacé tel quel ; aucun nombre ne change.
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from impots import guards
from impots.api.schemas import (
    MAX_YEAR,
    MIN_YEAR,
    QUICK_TIER_HOUSEHOLDS,
    PopulationSimulateRequest,
    PredictifBehaviour,
    PredictifIndex,
    PredictifPersistence,
    PredictifResponse,
    PredictifSlice,
    PredictifStart,
    ReformSpec,
)
from impots.identifiants import millesime


class ServiceError(Exception):
    """Un chiffrage refusé, avec le statut que l'API lui donne et sa raison : 422 pour une
    demande que le moteur refuse, 503 pour une source absente du checkout, 500 pour un
    défaut du moteur. Les mêmes attributs qu'une `HTTPException`, sans le serveur."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


POPULATION_VINTAGE = "2024"


#: Said on every population response and printed in the UI banner. The population
#: is a construction and the numbers it produces are worth what the reconciliation
#: report says they are worth.
POPULATION_NOTE = (
    "Population synthétique construite à partir de données ouvertes : structure des "
    "ménages observée dans l'enquête Emploi, revenus entièrement simulés à partir de "
    "distributions publiées. Les écarts aux totaux publiés sont dans "
    "reports/reconciliation.md. Les niveaux de RSA, de prime d'activité et de la "
    "distribution des niveaux de vie ne sont pas publiables en l'état (D-015) ; les "
    "écarts entre droit courant et réforme le sont."
)


def baseline_summary() -> dict[str, Any]:
    """The precomputed baseline aggregates, written by `impots population reconcile`."""
    from impots.population.build import PROCESSED

    path = PROCESSED / f"baseline_{POPULATION_VINTAGE}.json"
    if not path.exists():
        raise ServiceError(
            status_code=503,
            detail="Aucune population n'a encore été construite. Lancez "
                   "`impots population build` puis `impots population reconcile`.",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def population_frame() -> Any:
    """The population parquet, loaded once. ~420 000 rows, a few hundred MB in the
    engine but only tens of MB as a frame."""
    import polars as pl

    from impots.population.build import PROCESSED

    path = PROCESSED / f"population_{POPULATION_VINTAGE}.parquet"
    if not path.exists():
        raise ServiceError(
            status_code=503,
            detail="Aucune population n'a encore été construite. Lancez "
                   "`impots population build`.",
        )
    return pl.read_parquet(path)


#: Households the behavioural EMTR runs on. Smaller than the mechanical subsample
#: because a marginal rate costs two full-tier runs, and the band is a range anyway —
#: a band whose sampling noise is well inside its own width loses nothing by being
#: computed on fewer households. The number is reported so nobody has to guess.
BEHAVIOURAL_EMTR_HOUSEHOLDS = 3_000


def smic_annual(year: int) -> float:
    """The annual SMIC, read from the parameter tree rather than written down."""
    from impots.engine.system import baseline as engine_baseline

    smic = engine_baseline().parameters(f"{year}-01-01").marche_travail.salaire_minimum.smic
    return float(smic.smic_b_horaire) * float(smic.nb_heures_travail_mensuel) * 12.0


def employer_inputs(request: Any, run: Any, agg: Any) -> dict[str, Any]:
    """What C2 and C3 need, or nothing when the reform moves no employer contribution.

    EACH EARNER RESPONDS TO THEIR OWN LABOUR COST, read off the run's `persons`, at the
    SMIC multiple of their own salary. Every earner used to carry their household's
    rate: an earner at the SMIC took a share of a partner's cut at 3 SMIC, and the
    study's plafond, which relieves only wages above 3 SMIC, where C2 does not respond,
    counted 1 317 jobs, every one of them from such a household (D-261).

    THE EARNERS ARE THOSE OF THE HOUSEHOLDS THE RUN PRICED, AT THE RUN'S WEIGHT, as C7's
    are (`labour.inputs`). `run` is the quick tier's pass, on a subsample reweighted to
    the population (`runner.subsample`): its `persons` are that subsample's. Every earner
    of the whole frame at the frame's weight, with no cost change outside the
    subsample, counted 15 % of the earners: C2 gave 1 558 jobs for 1 Md€ of `t_delta`
    where the run holds 9 960 (D-259; D-255 found the same dilution apart). Each earner
    counts at THEIR OWN weight in the run, as the subsample scales it, not at their
    household's mean: members' weights can differ (D-255, D-269).
    """
    import numpy as np
    import polars as pl

    persons = run.persons
    if persons is None:
        from impots.behavioural.channels import ChannelInputMissing

        raise ChannelInputMissing("C2 needs the run's persons; this run has none")
    if "salaire_super_brut_reform" not in persons.columns:
        return {}
    earners = persons.filter(pl.col("salaire_brut_annuel") > 0)
    cost = earners["salaire_super_brut"].to_numpy()
    cost_reform = earners["salaire_super_brut_reform"].to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = np.where(cost > 0, (cost_reform - cost) / np.maximum(cost, 1e-9), 0.0)
    if not np.any(np.abs(rate) > 1e-12):
        return {}

    from impots.macro import shocks

    smic = smic_annual(request.year)
    return {
        "smic_multiple": earners["salaire_brut_annuel"].to_numpy() / max(smic, 1.0),
        "relative_cost_change": rate,
        "earner_weights": earners["weight"].to_numpy(),
        # NOT deltas["cotisations_employeur"] — that figure is gross of the
        # allègements and reported exactly zero for a reform costing 17.7 bn (D-039).
        "contribution_delta": agg.employer_contribution_delta,
        # C11 reads the cut's self-financing only where the shock builder routes it to
        # Mésange's targeted variant, which has no balance row: the same test, so the loop
        # and C11 never both carry the return (D-263).
        "targets_low_wages": shocks.targets_low_wages(
            tuple(request.reform.model_dump(exclude_none=True)), request.year),
        **self_financing_inputs(request),
    }


#: Why C11 stays shut on a targeted cut mixed with a knob the targeted variant does not
#: carry.
MIXED_CUT = ("{knobs} ne fait pas une baisse ciblée en {year} : le Trésor-Éco n° 97 lit "
             "des allègements au voisinage du SMIC, et la variation des cotisations "
             "patronales est un seul total, qui ne se partage pas entre les boutons "
             "(D-239, D-256).")


LOOP_AND_C11 = ("la variante ciblée de Mésange a une ligne de solde : la boucle et C11 "
                "compteraient deux fois les mêmes emplois. C11 est refusé tant que la "
                "boucle les porte (D-256).")


LOOP_UNREAD = ("les lignes de solde de Mésange ne se lisent pas ({error}) : sans elles, rien "
               "ne dit que la boucle ne compte pas déjà ces emplois, et C11 ne s'ouvre pas "
               "(D-256).")


def self_financing_inputs(request: Any) -> dict[str, Any]:
    """C11's inputs beyond C2's (D-256, D-270): what a full-time SMIC job brings the public
    finances in the year, or why the channel stays shut on a targeted cut all the same.

    Nothing for a cut the shock builder does not route to the targeted variant: C11 says
    so itself. A targeted cut has a reading only if every employer knob of it is
    targeted, the employer contribution delta being one total. And only while the
    targeted variant has no balance row in Mésange, where the loop would count the same
    jobs; the loop is absent for it today (D-242), and this refuses if it is not."""
    import fnmatch

    from impots.behavioural import autofinancement, channels
    from impots.macro import shocks
    from impots.macro import store as macro_store
    from impots.predictif.retroaction import BALANCE_TABLE

    if not shocks.targets_low_wages(tuple(request.reform.model_dump(exclude_none=True)),
                                    request.year):
        return {}
    employer = [knob for knob in channels._knobs(request.reform)
                if any(fnmatch.fnmatch(knob, pattern)
                       for pattern in shocks.TARGETED_EMPLOYER_KNOBS)]
    untargeted = [knob for knob in employer
                  if not shocks.targets_low_wages((knob,), request.year)]
    if untargeted:
        return {"self_financing_refused": MIXED_CUT.format(
            knobs=", ".join(f"`{knob}`" for knob in untargeted), year=request.year)}
    try:
        balance = macro_store.load().tables.get(BALANCE_TABLE)
    except (macro_store.MissingSourceTable, macro_store.UnverifiedParameter) as error:
        return {"self_financing_refused": LOOP_UNREAD.format(error=error)}
    if balance is None:
        return {"self_financing_refused": LOOP_UNREAD.format(error="la table est absente")}
    if "cotisations_employeurs_ciblees" in balance.values:
        return {"self_financing_refused": LOOP_AND_C11}
    return {"self_financing_value_per_job": autofinancement.job_value(request.year)}


def narrow_band(request: Any, run: Any) -> Any:
    """How much of this reform's movement comes from near its own thresholds.

    Measured per threshold FAMILY against the income each family is defined on — the
    barème and décote on taxable salary, the allègement plafonds on gross wage — and
    the largest share wins. Comparing a SMIC multiple against taxable income would
    put every threshold in the wrong place on the axis.
    """
    import numpy as np

    from impots import narrow_band as narrow_band_module
    from impots.api.schemas import NarrowBandFlag

    households = run.households
    if "revenu_disponible_reform" not in households.columns:
        return None
    smic = smic_annual(request.year)
    spec = request.reform.model_dump(exclude_none=True)

    taxable_knobs = {"ir_bareme", "decote_seuil_celib", "decote_seuil_couple",
                     "plafond_qf_demi_part"}
    wage_knobs = {"allegement_general_plafond", "bandeau_maladie_plafond",
                  "bandeau_famille_plafond"}

    weights = households["weight"].to_numpy()
    disposable_move = (
        households["revenu_disponible_reform"].to_numpy()
        - households["revenu_disponible"].to_numpy()
    )
    cost_move = (
        households["salaire_super_brut_reform"].to_numpy()
        - households["salaire_super_brut"].to_numpy()
        if "salaire_super_brut_reform" in households.columns
        else np.zeros(len(weights))
    )

    # The wage family is measured PER EARNER, not per household. A plafond is an
    # individual threshold: a two-earner household at 1.5 SMIC each has a household
    # gross of 3 SMIC and sits inside a 3.3-SMIC window while neither earner is
    # anywhere near it. Measured at household level the cliff case scored 56 % against
    # a 50 % bar — the right side of the line, for the wrong reason and by too little.
    wage_income, wage_move, wage_weights = (
        households["salaire_brut"].to_numpy(), cost_move, weights
    )
    # The earners are those of the households the run priced, each at their own weight
    # in the run, as C2's are (D-260, D-269): the frame's weight on the quick tier's
    # households tilted the share towards the heavy ones, which the draw keeps at their
    # own weight. Each moves by their OWN labour cost, from the run's persons (D-261):
    # split evenly, a partner sitting at a plafond who did not move took half of a cut
    # far below it.
    if run.persons is not None:
        import polars as pl

        earners = run.persons.filter(pl.col("salaire_brut_annuel") > 0)
        wage_income = earners["salaire_brut_annuel"].to_numpy()
        wage_move = (
            (earners["salaire_super_brut_reform"] - earners["salaire_super_brut"]).to_numpy()
            if "salaire_super_brut_reform" in earners.columns
            else np.zeros(earners.height)
        )
        wage_weights = earners["weight"].to_numpy()

    families = [
        ({k: v for k, v in spec.items() if k in taxable_knobs},
         households["salaire_imposable"].to_numpy(), disposable_move, weights),
        ({k: v for k, v in spec.items() if k in wage_knobs},
         wage_income, wage_move, wage_weights),
    ]
    best = None
    for subset, income, movement, group_weights in families:
        if not subset:
            continue
        thresholds = narrow_band_module.household_thresholds(
            type(request.reform).model_validate(subset), smic
        )
        result = narrow_band_module.measure(income, movement, group_weights, thresholds)
        if best is None or result.share > best.share:
            best = result
    if best is None:
        return None
    return NarrowBandFlag(
        share=best.share, flagged=best.flagged, window=best.window,
        share_threshold=best.share_threshold, thresholds=best.thresholds,
        caveat=best.caveat,
    )


def niche_blind_spot(request: Any, agg: Any) -> Any:
    """Flag a niche reform the population cannot price, or return None.

    Never raises: the rest of the reform may be perfectly answerable, and refusing the
    whole request over one blind knob would hide a valid mechanical figure.
    """
    from impots.api.schemas import NicheBlindSpot
    from impots.engine.reforms import NICHE_KNOBS
    from impots.guards import zero_confiant
    from impots.population import imputations as imp

    knobs = tuple(request.reform.model_dump(exclude_none=True))
    imputed = getattr(request, "impute_niches", False)
    blind = sorted(set(zero_confiant(knobs, (imp.NICHES,) if imputed else (), agg.totals))
                   & NICHE_KNOBS)
    if not blind:
        return None
    if imputed:
        return NicheBlindSpot(
            knobs=list(blind), declared_base_eur=float(
                agg.totals.get("reductions", 0.0) + agg.totals.get("credits_impot", 0.0)),
            message=(
                f"Les bases sont imputées, mais {', '.join(blind)} ne peut toujours pas "
                "être chiffré : le plafond global ne mord que sur les foyers cumulant "
                "plus de 10 000 € d'avantages, or l'imputation donne à chaque "
                "bénéficiaire d'un décile le MÊME montant — un décile n'a ni queue ni "
                "dispersion. Le crédit imputé le plus élevé avoisine 1 900 €, personne "
                "n'atteint le plafond, et un coût nul ici ne dit rien du dispositif."
            ),
        )
    return NicheBlindSpot(
        knobs=list(blind),
        declared_base_eur=0.0,
        message=(
            "Cette population ne déclare AUCUNE réduction ni crédit d'impôt : les "
            f"leviers {', '.join(blind)} n'ont donc rien sur quoi s'appliquer et leur "
            "coût affiché est nul par absence de base, non par absence d'effet. "
            "Nationalement ces dispositifs représentent 19,53 Md€ contre un barème de "
            "98,84 Md€ (DGFiP). Le calculateur foyer par foyer, lui, les chiffre "
            "exactement dès que la dépense est saisie."
        ),
    )


def macro(request: Any, agg: Any) -> Any:
    """The L4 fan, or a block explaining why there is not one.

    Never raises. A reform with no published multiplier, or a checkout without the
    primary sources on disk, both produce `available: false` with a reason — the fan
    being unavailable is the designed outcome for most reforms, not an error.
    """
    from impots.api.schemas import (
        Macro,
        MacroAssumptions,
        MacroBranch,
        MacroDecomposition,
        MacroQuantiles,
    )
    from impots.macro import fan as fan_module
    from impots.macro import io_layer, shocks
    from impots.macro import store as store_module
    from impots.macro import tes as tes_module

    knobs = tuple(request.reform.model_dump(exclude_none=True))
    try:
        impulse = shocks.build(
            shocks.instrument_deltas(
                agg.deltas, employer_contribution_delta=agg.employer_contribution_delta),
            year=request.year, reform_cost=agg.reform_cost, knobs=knobs)
    except shocks.ShockError as error:
        return Macro(available=False, unavailable_because=str(error))

    uncovered = {name: reason for name, reason in impulse.reasons().items()}
    if not impulse.by_instrument:
        return Macro(
            available=False, uncovered=uncovered,
            unavailable_because=(
                "Aucun instrument de cette réforme n'a de multiplicateur publié : il n'y "
                "a pas de trajectoire macro à tracer."
            ),
        )

    try:
        table = tes_module.load()
        jobs = tes_module.employment(table.branches, table.base_year)
        store = store_module.load()
        composition = io_layer.composition(
            table, shocks.allocation(table, impulse), jobs, use="consommation_finale")
        result = fan_module.run(
            impulse, store, gdp_eur=tes_module.gdp(table) * 1e6, composition=composition)
    except (tes_module.TesError, io_layer.IoLayerError, fan_module.FanError,
            store_module.MissingSourceTable, RuntimeError) as error:
        return Macro(available=False, uncovered=uncovered,
                     unavailable_because=f"Couche macro indisponible : {error}")

    strip = result.assumptions
    branches = sorted(
        range(table.n), key=lambda i: composition.output_shares[i], reverse=True)[:12]
    return Macro(
        available=True,
        uncovered=uncovered,
        gdp={h: MacroQuantiles(p10=q.p10, p50=q.p50, p90=q.p90, unit="EUR")
             for h, q in result.gdp_eur.items()},
        jobs={h: MacroQuantiles(p10=q.p10, p50=q.p50, p90=q.p90, unit="milliers ETP")
              for h, q in result.jobs_thousands_etp.items()},
        decomposition=[
            MacroDecomposition(
                horizon=h, parameter=d.parameter, scenario=d.scenario,
                scenario_available=d.scenario_available,
                scenario_unavailable_because=d.scenario_unavailable_because)
            for h, d in result.decomposition.items()
        ],
        composition=[
            MacroBranch(
                code=table.branches[i], label=table.labels[i].title(),
                output_share=float(composition.output_shares[i]),
                employment_share=float(composition.employment_shares[i]))
            for i in branches
        ],
        assumptions=MacroAssumptions(
            cycle_state=strip.cycle_state, design=strip.design,
            leakage=None if math.isnan(strip.leakage) else strip.leakage,
            leakage_applied=strip.leakage_applied, horizons=list(strip.horizons),
            parameters_vintage=strip.parameters_vintage, grade=strip.grade,
            covered_share=strip.covered_share, instruments=list(strip.instruments),
            simulation_conditions=strip.simulation_conditions,
            caveats=list(strip.caveats), banner=strip.banner,
        ),
        notes=list(result.notes),
    )


def behavioural_inputs(request: Any, frame: Any, agg: Any, run: Any = None,
                        uprating_key: str | None = None) -> tuple[dict[str, Any], int | None]:
    """What `band.compute` reads besides the mechanical figure and the reform.

    `(inputs, households)`: the employer inputs, plus the households' marginal rates when
    the EMTR pass has them — `households` counts those, and is None when it has none.
    Shared by the band (`behavioural`) and by the receipts at θ (`/predictif/simulate`),
    so the two read the same population the same way. `uprating_key` says `frame` was
    aged, for the EMTR caches, which the frame alone does not tell (D-226).

    C1 reads the rates of several samples, pooled (D-284): `households` then counts them
    all. C7 reads the first sample alone, and a reform C1 does not read pays for one.
    """
    from impots.behavioural import channels
    from impots.behavioural import emtr as emtr_module
    from impots.behavioural.store import load as load_store

    run_households = run.households if run is not None else None
    employer = (employer_inputs(request, run, agg)
                if run_households is not None else {})
    # C10 reads the run's households, not their marginal rates (D-249).
    employer = {**employer, **dividend_inputs(request, run_households)}

    def rates(**seed: int) -> Any:
        return emtr_module.cached(
            frame, POPULATION_VINTAGE, year=request.year, reform=request.reform,
            sample=BEHAVIOURAL_EMTR_HOUSEHOLDS, uprating_key=uprating_key, **seed,
        ).with_earnings

    households = rates()
    if households.is_empty() or "emtr_reform" not in households.columns:
        return employer, None
    samples = [households]
    if channels._claimed(load_store(), request.reform, channels.C1_KEYS):
        samples += [rates(seed=seed) for seed in emtr_module.C1_SAMPLES[1:]]

    return {
        **employer,
        **pooled_eti_inputs(frame, samples),
        **labour_inputs(request, frame, agg, households),
    }, int(sum(sample.height for sample in samples))


def pooled_eti_inputs(frame: Any, samples: list[Any]) -> dict[str, Any]:
    """C1's inputs over several samples of households, each weighed by the share of the
    samples it is (D-284). Each sample keeps its own top-decile split, so that C1 on the
    pool is the mean of C1 on each sample, to the rounding."""
    import numpy as np

    parts = [eti_inputs(frame, households) for households in samples]
    pooled = {key: np.concatenate([part[key] for part in parts]) for key in parts[0]}
    pooled["weights"] = pooled["weights"] / len(parts)
    return pooled


def eti_inputs(frame: Any, households: Any) -> dict[str, Any]:
    """C1's inputs: the households' marginal rates before and after the reform, their
    taxable base, their weights and the top-decile split. `households` are the EMTR
    pass's households with earnings, `frame` the population their rates were computed
    on. Read apart by the measure of C1's noise (`scripts/bruit_c1.py`, D-282), so that
    it prices C1 exactly as the chain does."""
    import numpy as np
    import polars as pl

    weights = households["weight"].to_numpy()
    # Taxable base per household: what C1's response applies to. Deciles of it give
    # the top-decile split the two ETI parameters need.
    frame_base = (
        frame.group_by("household_id")
        .agg(pl.col("salaire_brut_annuel").sum().alias("base"))
        .sort("household_id")
    )
    lookup = dict(zip(frame_base["household_id"].to_list(),
                      frame_base["base"].to_list(), strict=False))
    base = np.array([lookup.get(h, 0.0) for h in households["household_id"].to_list()])
    order = np.argsort(base)
    cumulative = np.cumsum(weights[order])
    top = np.zeros(len(base), dtype=bool)
    if cumulative[-1] > 0:
        top[order[cumulative >= 0.9 * cumulative[-1]]] = True
    return {
        "emtr_baseline": households["emtr"].to_numpy(),
        "emtr_reform": households["emtr_reform"].to_numpy(),
        "taxable_base": base, "weights": weights, "top_decile": top,
    }


def dividend_inputs(request: Any, households: Any) -> dict[str, Any]:
    """C10's inputs (D-249): the dividends the run's households declare at the PFU,
    weighted, and the whole rate on them before and after — the PFU's income-tax part,
    read from the law and the reform, plus the social levies, measured. None when the
    reform leaves the PFU alone, and no base when the run did not impute capital income:
    the channel then says it was not computed, rather than pricing a response on nothing.
    Read on the households rather than the aggregate, whose totals are a closed list of
    instruments that the dividends, a base and not a levy, do not belong to.

    A household the CDHR holds, before or after the reform, is left out of the base and
    named apart (D-250): the CDHR tops its tax up to 20 % of its RFR, PFU included, so a
    PFU cut is taken back and its net-of-tax rate does not move. A run without the row —
    a year before 2025 — has none to leave out.

    With them, the wage the firm owners shift (D-252): what a euro of it brings the state
    and costs the firm, measured on the engine, and the IS rate the profit it becomes
    pays — the reform's when it sets one, the law's otherwise."""
    import polars as pl

    from impots.behavioural import channels
    from impots.behavioural.store import load as load_store
    from impots.entreprises import system as firm_system
    from impots.population import capital as capital_module

    if not channels._claimed(load_store(), request.reform, channels.C10_KEYS):
        return {}
    if households is None or "dividendes" not in households.columns:
        return {}
    weighted = households["dividendes"] * households["weight"]
    if float(weighted.sum()) <= 0:
        return {}
    held = pl.lit(False)
    for column in ("cdhr", "cdhr_reform"):
        if column in households.columns:
            held = held | (pl.col(column) != 0)
    is_held = households.select(held.alias("held"))["held"]
    levies = capital_module.social_levy_rate(request.year)
    before = capital_module.pfu_rate(request.year)
    after = request.reform.pfu_taux if request.reform.pfu_taux is not None else before
    wage_levy, wage_cost = capital_module.wage_wedge(request.year)
    firm = getattr(request, "firm_reform", None)
    corporate = getattr(firm, "is_taux_normal", None) if firm is not None else None
    return {"dividend_base_eur": float(weighted.filter(~is_held).sum()),
            "dividend_base_cdhr_eur": float(weighted.filter(is_held).sum()),
            "levy_rate_baseline": before + levies, "levy_rate_reform": after + levies,
            "wage_levy_rate": wage_levy, "wage_cost_rate": wage_cost,
            "corporate_rate": (corporate if corporate is not None
                               else firm_system.normal_rate(request.year))}


def labour_inputs(request: Any, frame: Any, agg: Any, households: Any) -> dict[str, Any]:
    """C7's persons, only when the reform moves a levy C7 prices (D-220): none otherwise,
    and the channel then says why it did not open rather than pricing nothing."""
    import math

    from impots.behavioural import channels
    from impots.behavioural import labour as labour_module
    from impots.behavioural.store import load as load_store

    if not channels._claimed(load_store(), request.reform, channels.C7_KEYS):
        return {}
    before = agg.totals.get("salaire_net")
    after = agg.totals_reform.get("salaire_net")
    if not before or not after:
        raise channels.ChannelInputMissing(
            "C7 needs the net wage bill before and after the reform; the run has "
            f"{before!r} and {after!r}")
    return labour_module.inputs(frame, households, math.log(after / before))


def behavioural(request: Any, frame: Any, agg: Any, run: Any = None) -> Any:
    """The band for a household reform, or a mechanical-only answer with its reason."""
    from impots.api.schemas import Behavioural
    from impots.behavioural import band as band_module

    inputs, households = behavioural_inputs(request, frame, agg, run)
    computed = band_module.compute(
        mechanical=-guards.cout_calcule(agg.reform_cost, chemin="la bande des ménages"),
        reform=request.reform, **inputs)
    payload = computed.as_dict()
    if households is not None:
        payload["emtr_households"] = households
    return Behavioural(**payload)


def imputations_of(request: Any) -> Any:
    """What a pass of `request` imputes: the one policy every path reads
    (`population.imputations`), with what the request asks for — the niches, the capital —
    and what its reform needs to move. A knob the population cannot move on is refused
    here, before the pass, with its reason: a 422, never a zero."""
    from impots.population import imputations as imp

    asked = [name for name, flag in ((imp.NICHES, getattr(request, "impute_niches", False)),
                                     (imp.CAPITAL, getattr(request, "impute_capital", False)))
             if flag]
    try:
        return imp.imputations(request.reform, request.year, demandees=asked,
                               chemin="l'API")
    except imp.ImputationRefusee as error:
        raise ServiceError(status_code=422, detail=str(error)) from error


def imputes_capital(request: Any) -> bool:
    """Whether a pass imputes capital income: when asked, and whenever the reform moves the
    PFU, which bites on nothing else (D-249). A PFU reform on a population without capital
    would cost exactly zero, and say nothing."""
    return imputations_of(request).capital


def run_population(request: Any, frame: Any,
                    capital_index: float | None = None,
                    annee_consommation: int | None = None,
                    prix_consommation: dict[int, float] | None = None) -> tuple[Any, Any]:
    """The quick-tier pass and its aggregate: `(run, aggregate)`. Shared by
    `/population/simulate` and `/predictif/simulate`. `capital_index` ages the imputed
    capital to the year, when the frame was aged to it (D-249)."""
    from impots.population import aggregate as aggregate_module
    from impots.population.runner import run as population_run
    from impots.population.to_openfisca import WiringError

    imputed = imputations_of(request)
    try:
        result = population_run(
            frame, year=request.year, reform=request.reform, tier="full",
            sample=QUICK_TIER_HOUSEHOLDS,
            # The capital whenever the reform moves the PFU (D-249), the consumption
            # whenever it moves a consumption tax (D-323), the sick pay whenever it moves
            # their tax (D-306): each bites on nothing else. The consumption's euros follow
            # the frame: the year it was aged to, at the frame's prices, or the vintage
            # when it was not (D-328). Named one by one, as the API always passed them.
            impute_niches=imputed.niches, impute_capital=imputed.capital,
            impute_consommation=imputed.consommation,
            **({"impute_ij": True} if imputed.ij else {}),
            capital_index=capital_index if imputed.capital else None,
            annee_consommation=(int(POPULATION_VINTAGE) if annee_consommation is None
                                else annee_consommation),
            prix_au_dela=prix_consommation,
        )
    except WiringError as error:  # pragma: no cover - guarded upstream
        raise ServiceError(status_code=500, detail=str(error)) from error
    except ValueError as error:
        raise ServiceError(status_code=422, detail=str(error)) from error
    agg = aggregate_module.aggregate(result.households)
    # The confident-zero guard, on every path (but 14): a niche the population declares no
    # base for is flagged in the response (`niche_blind_spot`); anything else is a pass
    # the policy should have refused, and is refused here.
    from impots.engine.reforms import NICHE_KNOBS

    try:
        guards.refuse_zero_confiant(
            set(request.reform.model_dump(exclude_none=True)) - NICHE_KNOBS,
            imputed.noms(), agg.totals, chemin="l'API")
    except guards.ZeroConfiantError as error:  # pragma: no cover - refused before the pass
        raise ServiceError(status_code=422, detail=str(error)) from error
    return result, agg


def quick_tier_note() -> str:
    return (POPULATION_NOTE
            + f" Ce résultat porte sur un sous-échantillon déterministe de "
              f"{QUICK_TIER_HOUSEHOLDS:,} ménages repondérés"
              .replace(",", " ")
            + ", pas sur la population complète : attendez-vous à un bruit "
              "d'échantillonnage de l'ordre du pour cent sur les agrégats.")


# It names the parquet read below, so it takes the vintage rule (D-173).
FIRM_VINTAGE = millesime(os.environ.get("IMPOTS_FIRM_VINTAGE", "fixture"))


@lru_cache(maxsize=1)
def firm_population() -> Any:
    import polars as pl

    from impots.entreprises.build import PROCESSED as FIRM_PROCESSED

    path = FIRM_PROCESSED / f"firms_{FIRM_VINTAGE}.parquet"
    if not path.exists():
        raise ServiceError(
            status_code=503,
            detail="Aucune population d'entreprises n'a été construite. Lancez "
                   "`impots entreprises build`.",
        )
    return pl.read_parquet(path)


def firm_behavioural(request: Any, agg: Any) -> Any:
    """The investment band for a production-tax reform, reported in per cent.

    Never folded into the revenue figures: investment is not revenue, and the band is
    centred on zero because the evaluation behind it found nothing robust (D-037).
    """
    from impots.api.schemas import Behavioural
    from impots.behavioural import band as band_module

    baseline_tax = agg.totals.get("cvae", 0.0)
    reformed_tax = agg.totals_reform.get("cvae", baseline_tax)
    computed = band_module.compute(
        mechanical=-guards.cout_calcule(agg.reform_cost, chemin="la bande des entreprises"),
        reform=request.reform,
        production_tax_baseline=baseline_tax, production_tax_reform=reformed_tax,
        is_rate_change_points=is_rate_change_points(request),
        cir_margins=cir_margins(request),
    )
    return Behavioural(**computed.as_dict())


def cir_margins(request: Any) -> tuple[tuple[float, float], ...] | None:
    """C9's inputs (D-222): the créance change at fixed R&D and the marginal rate, for
    the two groups of declarants. None when the reform leaves the CIR alone; a missing
    GECIR is left to the CIR block's 503, which names it."""
    from impots.agregats import cir as cir_module

    knobs = {knob: getattr(request.reform, knob) for knob in cir_module.KNOBS}
    if all(value is None for value in knobs.values()):
        return None
    try:
        return cir_module.margins(cir_module.read_gecir(), **knobs)
    except cir_module.CirError:
        return None


def is_rate_change_points(request: Any) -> float | None:
    """The reform's IS normal rate minus current law's for the year, in points — what
    C8 reads (D-221). None when the reform leaves the normal rate alone."""
    from impots.entreprises import system as firm_system

    return firm_system.normal_rate_change_points(request.reform, request.year)


def firm_cir(request: Any) -> Any:
    """The CIR block when the reform moves a CIR rate (D-222), else None. Its sources
    absent from this checkout is a 503 that names them, not a zero."""
    from impots.agregats import cir as cir_module
    from impots.api.schemas import FirmCir

    knobs = {knob: getattr(request.reform, knob) for knob in cir_module.KNOBS}
    if all(value is None for value in knobs.values()):
        return None
    try:
        reading = cir_module.read_gecir()
        depense = cir_module.read_depense_fiscale()
        priced = cir_module.price(reading, **knobs)
    except cir_module.CirError as error:
        raise ServiceError(status_code=503, detail=str(error)) from error
    rates = {"cir_taux": reading.rate_low, "cir_taux_au_dela": reading.rate_high}
    return FirmCir(
        millesime=reading.millesime, rates=rates,
        rates_reform={k: (v if v is not None else rates[k]) for k, v in knobs.items()},
        creance_publiee_eur=reading.creance_eur,
        creance_eur=priced.baseline_eur, creance_reform_eur=priced.reformed_eur,
        delta_creance_eur=priced.delta_eur, depense_fiscale_eur=depense,
        banner=cir_module.BANNER.format(millesime=reading.millesime),
        sources=[cir_module.GECIR_FILE, cir_module.VM_FILE])


class MacroSourceError(RuntimeError):
    """The macro store's primary files are not in this checkout."""


def predictif_macro_store() -> Any:
    """The macro store the loop reads, or a named refusal when its PDFs are absent —
    the loop is then unavailable, never silently zero. A seam the tests stub."""
    from impots.macro import imk, mesange
    from impots.macro import store as macro_store_module

    try:
        return macro_store_module.load()
    except (mesange.MesangeError, imk.ImkError,
            macro_store_module.MissingSourceTable) as error:
        raise MacroSourceError(f"magasin macro illisible : {error}") from error


#: Side by side, a chain-stage index has one value per persistence scenario: the
#: response lists it as carried by each path rather than pick one (D-230).
SIDE_BY_SIDE_INDEX = ("une valeur par scénario de persistance, donnée avec chacun des deux, "
                      "côte à côte")


#: The population view the predictive path's first year is priced in, in
#: `predictif.annuel`'s words: the population aged to that year, the command's headline
#: (D-216), by the owner's choice (D-226). `price_first_year` ages the frame before the
#: pass; pricing another view would change the numbers, and this name and
#: `first_year_note` with them.
FIRST_YEAR_VIEW = "vieillie"


#: The other view, the 2024 population as it is: the explorer prices it beside the headline,
#: because a bundle that meets its target only there is not a plan (D-155, PHASE10_SPEC §2).
FROZEN_VIEW = "figee"


def first_year_note(year: int, uprating: Any) -> str:
    """The quick tier's note, the view the predictive path's first year is priced in,
    and the caveat that must travel with any figure computed on an aged population."""
    from impots import uprating as uprating_module

    return (quick_tier_note()
            + f" Vue « vieillie » : l'année {year} est chiffrée avec sa législation sur la "
              f"population {POPULATION_VINTAGE} vieillie jusqu'à elle, la vue de tête de la "
              "commande `impots predictif` (D-216, D-226) ; la vue « figée », que la "
              "commande donne à côté, n'est pas chiffrée ici. "
            + uprating_module.caveat(year, uprating))


@dataclass(frozen=True)
class YearPass:
    """One year for `price_first_year`, past the window the API serves (`MAX_YEAR`).

    `impots predictif` prices 2026 to 2035 with each year's law as openfisca carries it,
    each year labelled by its basis (D-216). With behaviour or the loop it does so through
    this seam, the simulator's own: the same pass, the same channel inputs, the same
    impulse, year after year (PHASE10_SPEC §4, D-236). The request schema's year bound
    is the API's, not the engine's."""

    reform: ReformSpec
    year: int
    behavioural: bool = False


def frozen_year_note(year: int) -> str:
    """The note of the frozen view, which no uprating caveat concerns."""
    return (quick_tier_note()
            + f" Vue « figée » : l'année {year} est chiffrée avec sa législation sur la "
              f"population {POPULATION_VINTAGE} telle quelle, sans vieillissement.")


#: Why the firm layer's taxes have no macro effect in the chain (PHASE11_SPEC §4, D-246).
FIRM_NO_VARIANT = (
    "impôt des entreprises, sans variante dans Mésange (D-214), et la boucle par "
    "élasticités (CE, DP 098) refusée : appliquée aux variantes où Mésange imprime son "
    "solde, elle ne redonne pas sa boucle (D-246). Ni rétroaction ni effet sur le PIB "
    "dans la dette (D-218) ; l'effet de l'IS sur le PIB s'affiche à part, en indice")


#: The firm totals that are the sum of the others, not an instrument.
FIRM_TOTAL = "prelevements_entreprise"


def firm_aging_factor(year: int, growth: Any) -> float:
    """The aged view's multiplier: GDP of `year` over GDP of the vintage's — the seam the
    tests stub, so that no test needs the national accounts (D-246)."""
    from impots.predictif import firmes

    return firmes.aging_factor(year, growth, FIRM_VINTAGE)


def firm_first_year(firm_reform: Any, year: int, *, view: str = FIRST_YEAR_VIEW,
                     growth: Any = None) -> Any:
    """The firm layer's part of a predictive first year (PHASE11_SPEC §3, D-244, D-246).

    The firm population is the one the layer is built from, of its own vintage, under
    the law of `year`. In the frozen view that is the cost; in the aged view it is
    followed at the pace of the scenario's nominal GDP from the vintage (M0, R7), which
    needs the scenario's growth and a vintage that names its year. The IS is counted by
    exercise, not by cash, and the note says so.
    """
    from types import SimpleNamespace

    from impots.entreprises import aggregate as firm_aggregate
    from impots.entreprises import runner as firm_runner
    from impots.predictif import firmes

    if view not in (FIRST_YEAR_VIEW, FROZEN_VIEW):
        raise ValueError(f"vue « {view} » inconnue : {FIRST_YEAR_VIEW} ou {FROZEN_VIEW}")
    try:
        factor = firm_aging_factor(year, growth) if view == FIRST_YEAR_VIEW else None
    except firmes.FirmViewError as error:
        raise ServiceError(status_code=422, detail=str(error)) from error
    try:
        result = firm_runner.run(firm_population(), year=year, reform=firm_reform)
    except firm_runner.FirmRunError as error:
        raise ServiceError(status_code=500, detail=str(error)) from error
    except ValueError as error:
        raise ServiceError(status_code=422, detail=str(error)) from error
    aggregates = firm_aggregate.aggregate(result.firms)
    scale = 1.0 if factor is None else factor
    note = (f"Couche entreprises : population d'entreprises du millésime {FIRM_VINTAGE}, "
            f"sous le droit de {year} ; "
            f"{firmes.note(view, FIRM_VINTAGE, year, factor)} ; l'IS est compté à "
            f"l'exercice, non à la caisse (PHASE11_SPEC §3).")
    if firm_cells_are_synthetic():
        note = FIRM_SYNTHETIC + note
    deltas = {name: value * scale for name, value in aggregates.deltas.items()
              if name != FIRM_TOTAL and value}
    cost = guards.cout_calcule(aggregates.reform_cost, chemin="la couche entreprises")
    return SimpleNamespace(cost=cost * scale,
                           deltas=deltas, note=note, factor=factor)


FIRM_SYNTHETIC = ("ATTENTION : population d'entreprises construite à partir de cellules "
                  "synthétiques de test, pas de SIRENE × ESANE ; son chiffrage n'est pas "
                  "une affirmation sur la France. ")


def firm_cells_are_synthetic() -> bool:
    from impots.entreprises import build as firm_build

    manifest = firm_build.PROCESSED / f"firms_{FIRM_VINTAGE}.manifest.json"
    return (not manifest.exists() or bool(
        json.loads(manifest.read_text(encoding="utf-8"))["cells_are_synthetic"]))


def firm_report_note(firm_reform: Any = None, years: list[int] | tuple = ()) -> str:
    """The firm layer's conventions for a report that spans years (D-246): what each
    first year's note says, without the year; and, for a factor on the CVAE's schedule,
    the year the law abolishes it within `years` (D-254)."""
    from impots.predictif import firmes

    note = firmes.convention(FIRM_VINTAGE)
    gone = firmes.extinction(firm_reform, list(years))
    if gone:
        note += " " + gone
    return FIRM_SYNTHETIC + note if firm_cells_are_synthetic() else note


def first_year_request(reform: ReformSpec, year: int, behavioural: bool) -> Any:
    """The request a predictive first year is priced on. A firm reform alone leaves the
    households' empty, which `PopulationSimulateRequest` rightly refuses for its own
    endpoint; the internal `YearPass` carries the same three fields without that refusal."""
    if reform.is_empty():
        return YearPass(reform=reform, year=year, behavioural=behavioural)
    return PopulationSimulateRequest(reform=reform, year=year, behavioural=behavioural)


def firm_part(firm_reform: Any, growth: Any = None) -> dict[str, Any]:
    """The keywords a predictive pass takes for a firm reform — the reform, and the growth
    scenario its aged view follows (D-246): none when there is none, so a household
    reform goes through the very call it always did."""
    return ({"firm_reform": firm_reform, "growth": growth}
            if firm_reform is not None and not firm_reform.is_empty() else {})


def price_first_year(request: PopulationSimulateRequest, *, uprating: Any,
                      macro: bool = False, view: str = FIRST_YEAR_VIEW,
                      firm_reform: Any = None, growth: Any = None) -> Any:
    """One quick-tier pass for the predictive path's first year — the seam its tests stub.

    The population is aged to the year with `uprating` first (D-226), and everything
    below reads the aged frame. With `view` « figee » it is read as it is: the explorer
    prices both views of each bundle through this one seam (PHASE10_SPEC §2), and the
    endpoint the aged one only. `cost` is the engine's, COST POSITIVE; `inputs` is what
    `band.compute` reads, when behaviour was asked for, so the receipts at θ run on the
    very population the cost came from; `impulse` is the reform's macro impulse by
    Mésange variant, EXPANSIONARY-POSITIVE, and `uncovered` the deltas without one, when
    the loop was asked for (`macro`); `view` is the population view priced,
    `FIRST_YEAR_VIEW`, and `note` the quick tier's, which names it with its caveat.

    A FIRM REFORM (`firm_reform`, PHASE11_SPEC §3) adds the firm layer's cost for the
    year, and its deltas join `uncovered`: no Mésange variant reads them. `layers` then
    names each layer's cost. A firm reform alone runs no population pass at all: the
    households are untouched, their cost is zero, and nothing of theirs is read; with
    behaviour asked, `behaviour_asked` says so, for no household channel reads it (D-268).
    """
    from types import SimpleNamespace

    if view not in (FIRST_YEAR_VIEW, FROZEN_VIEW):
        raise ValueError(f"vue « {view} » inconnue : {FIRST_YEAR_VIEW} ou {FROZEN_VIEW}")
    firm = (firm_first_year(firm_reform, request.year, view=view, growth=growth)
            if firm_reform is not None and not firm_reform.is_empty() else None)
    if firm is None:
        return price_households(request, uprating=uprating, macro=macro, view=view)
    households = (SimpleNamespace(cost=0.0, inputs=None, impulse={} if macro else None,
                                  uncovered={}, view=view, note="", deciles=[])
                  if request.reform.is_empty()
                  else price_households(request, uprating=uprating, macro=macro,
                                         view=view))
    return SimpleNamespace(
        cost=households.cost + firm.cost, inputs=households.inputs,
        impulse=households.impulse,
        uncovered=({**households.uncovered, **dict.fromkeys(firm.deltas, FIRM_NO_VARIANT)}
                   if macro else {}),
        view=view, note=" ".join(n for n in (households.note, firm.note) if n),
        deciles=households.deciles,
        layers={"menages": households.cost, "entreprises": firm.cost},
        behaviour_asked=bool(request.behavioural) and request.reform.is_empty())


def price_households(request: PopulationSimulateRequest, *, uprating: Any,
                      macro: bool, view: str) -> Any:
    """The households' pass of `price_first_year`, the one it always was."""
    from types import SimpleNamespace

    from impots import uprating as uprating_module
    from impots.macro import shocks

    frame = (uprating_module.uprate(population_frame(), request.year, uprating)
             if view == FIRST_YEAR_VIEW else population_frame())
    # The imputed capital ages with the frame: on the wage index in the aged view — in the
    # study's frame the nominal growth of the economy — and not at all in the frozen one,
    # whose frame is the vintage's (D-249). Only a pass that imputes it is told the index.
    index = (uprating.factor("wage", request.year) if view == FIRST_YEAR_VIEW else 1.0)
    # The imputed consumption follows the frame too: the year's euros at the frame's own
    # price index in the aged view, the vintage's in the frozen one (D-328).
    from impots import consommation

    aged = view == FIRST_YEAR_VIEW
    imputed = imputations_of(request)
    conso = ({"annee_consommation": request.year if aged else int(POPULATION_VINTAGE),
              "prix_consommation": (consommation.prix_du_cadre(uprating, request.year)
                                    if aged else None)}
             if imputed.consommation else {})
    result, agg = run_population(
        request, frame, **({"capital_index": index} if imputed.capital else {}), **conso)
    if agg.reform_cost is None:  # pragma: no cover - a reform always has a cost
        raise ServiceError(status_code=500, detail="la réforme n'a pas de coût calculé")
    # The EMTR caches are keyed on the frame priced: the aged view's on its uprating, the
    # frozen view's on the vintage as built, which it prices. Under one key, the view
    # priced first wrote the rates both read (D-276).
    inputs = (behavioural_inputs(
        request, frame, agg, result,
        uprating_key=uprating.key() if view == FIRST_YEAR_VIEW else None)[0]
        if request.behavioural else None)
    impulse, uncovered = None, {}
    if macro:
        try:
            built = shocks.build(
                shocks.instrument_deltas(
                    agg.deltas,
                    employer_contribution_delta=agg.employer_contribution_delta),
                year=request.year, reform_cost=agg.reform_cost,
                knobs=tuple(request.reform.model_dump(exclude_none=True)))
        except shocks.ShockError as error:
            raise ServiceError(status_code=422, detail=str(error)) from error
        impulse, uncovered = dict(built.by_instrument), built.reasons()
    return SimpleNamespace(cost=float(agg.reform_cost), inputs=inputs, impulse=impulse,
                           uncovered=uncovered, view=view,
                           note=(first_year_note(request.year, uprating)
                                 if view == FIRST_YEAR_VIEW
                                 else frozen_year_note(request.year)),
                           deciles=list(agg.deciles))


def predictif_hypotheses(request: Any) -> Any:
    """The named scenarios, the uprating, θ and the persistences of a predictive request.

    `/predictif/simulate` and `impots exploration` build them here, in one place, so that
    the explorer cannot price under other hypotheses than the simulator (PHASE10_SPEC §2).
    The chain's own errors are raised as they are; each caller turns them into its own
    refusal, a 422 or an exit status.
    """
    from types import SimpleNamespace

    from impots.behavioural.store import load as load_store
    from impots.dette.path import SHIPPED, DebtError, SpendingScenario
    from impots.dette.scenarios import GrowthScenario, RateScenario
    from impots.predictif import annuel, retroaction
    from impots.predictif.theta import MACRO_ROW, Theta

    if request.spending.rule == "personnalise":
        spending = SpendingScenario(request.spending.name or "", "personnalise",
                                    growth=request.spending.growth)
    else:
        if request.spending.name is not None or request.spending.growth is not None:
            raise DebtError(
                f"la règle « {request.spending.rule} » porte son propre nom et ne lit "
                f"aucun taux : un nom ou un taux fourni avec elle serait ignoré.")
        spending = SHIPPED[request.spending.rule]
    growth = GrowthScenario(request.growth.name, request.growth.real,
                            request.growth.prices)
    rate = RateScenario(request.rate.name, request.rate.kind,
                        market_rate=request.rate.market_rate)
    uprating = annuel.uprating_for(growth, wage=request.uprating.wage,
                                   source=request.uprating.source,
                                   base_year=int(POPULATION_VINTAGE))
    theta = Theta(rows=dict(request.theta.rows), common=request.theta.common)
    store = load_store()
    theta.check_known(store)
    looped = request.macro and spending.rule == retroaction.SPENDING_RULE
    if request.persistence is not None and not looped:
        raise DebtError(
            f"persistance « {request.persistence} » sans rétroaction appliquée (non "
            f"demandée, ou absente sous « {spending.name} ») : elle serait ignorée.")
    # Past three years the loop needs a persistence scenario. Named, it is that one;
    # unnamed, both are computed from the one pass and shown side by side, neither
    # in the lead: none is the default (§4.5, D-230).
    persistences: list[str | None] = (
        [request.persistence] if request.persistence is not None
        else list(retroaction.PERSISTENCE_LABELS)
        if looped and request.horizon > retroaction.MAX_HORIZON else [None])
    if looped:
        theta.for_row(MACRO_ROW)
    return SimpleNamespace(spending=spending, growth=growth, rate=rate, uprating=uprating,
                           theta=theta, store=store, looped=looped,
                           persistences=persistences)


def predictif_simulate(request: Any) -> PredictifResponse:
    """The reform's debt path against the reference, under named scenarios (PHASE9_SPEC §3).

    THE FAST VERSION (M0, R3). Pricing ten years one by one takes about an hour, so the
    endpoint prices the FIRST projected year on the quick-tier population, aged to that
    year — the command's headline view, « vieillie » (D-226) — and carries that cost as
    a constant share of GDP, a convention every carried year is labelled with. The full
    year-by-year path belongs to a batch command.

    THE WAGE INDEX IS REQUIRED, with its source, like every hypothesis (D-213): the price
    index is the growth scenario's (`annuel.uprating_for`), so the reform's euros and the
    GDP that divides them inflate together. A source left blank or a rate that is not an
    annual one is refused by `Uprating`'s own message, before the pass.

    θ IS REQUIRED (D-217, guard 1): the schema has no default for it, and a θ outside
    [0, 1] or named for a row the store does not hold is refused here, before the pass.
    With behaviour, the first year's receipts are evaluated at θ and at the corners of
    the θ box, on the same population the cost came from.
    """
    from impots.dette import maturite
    from impots.dette import reference as reference_module
    from impots.dette.path import BANNER as DEBT_BANNER
    from impots.dette.path import DebtError
    from impots.entreprises import system as firm_system
    from impots.predictif import chaine, comportement, retroaction
    from impots.predictif import indices as indices_module
    from impots.predictif.theta import ThetaError
    from impots.uprating import UpratingError

    try:
        hypotheses = predictif_hypotheses(request)
        specs = indices_module.select(request.indices)
    except (DebtError, ThetaError, UpratingError, indices_module.IndicesError) as error:
        raise ServiceError(status_code=422, detail=str(error)) from error
    spending, growth, rate = hypotheses.spending, hypotheses.growth, hypotheses.rate
    uprating, theta, store = hypotheses.uprating, hypotheses.theta, hypotheses.store
    looped, persistences = hypotheses.looped, hypotheses.persistences

    try:
        start = reference_module.start_from_accounts(chaine.START_YEAR)
        securities = maturite.load_block1() if rate.kind == "marche" else None
        macro_store = predictif_macro_store() if looped else None
    except (DebtError, maturite.MaturityError, OSError, MacroSourceError) as error:
        raise ServiceError(
            status_code=503,
            detail=f"Données de départ indisponibles dans ce checkout : {error}") from error

    # The indices read Mésange whenever the impulse is computed, loop or not (§7); a store
    # the loop does not need and cannot read leaves them absent, with why, not a 503.
    indices_store, indices_reason = macro_store, indices_module.NO_IMPULSE
    if indices_store is None and request.macro:
        try:
            indices_store = predictif_macro_store()
        except MacroSourceError as error:
            indices_reason = f"Magasin macro illisible dans ce checkout : {error}"

    year = start.year + 1
    if year > MAX_YEAR:
        raise ServiceError(
            status_code=422,
            detail=f"la première année projetée, {year}, sort de la fenêtre que la couche "
                   f"population sert ({MIN_YEAR}–{MAX_YEAR}).")
    first = price_first_year(
        first_year_request(request.reform, year, request.behavioural),
        uprating=uprating, macro=request.macro,
        **firm_part(request.firm_reform, growth=growth))
    try:
        at = (comportement.evaluate(theta, mechanical=-first.cost, reform=request.reform,
                                    store=store, **first.inputs)
              if first.inputs is not None else None)
        costs = chaine.ReformCosts(
            by_year={year: first.cost}, carry=chaine.CARRY,
            behavioural=({year: at} if at is not None else None),
            impulses=({year: first.impulse} if first.impulse is not None else None),
            uncovered=dict(first.uncovered),
            behaviour_asked=getattr(first, "behaviour_asked", False))
        results = [chaine.run(start, horizon=request.horizon, costs=costs,
                              spending=spending, growth=growth, rate=rate, theta=theta,
                              securities=securities, store=store, persistence=persistence,
                              macro_store=macro_store)
                   for persistence in persistences]
        index_inputs = dict(
            deciles_rows=getattr(first, "deciles", None), impulse=first.impulse,
            gdp_eur=reference_module.reference_years(
                start, 1, spending=spending, growth=growth)[0].gdp_eur,
            macro_store=indices_store, macro_reason=indices_reason, theta=theta,
            store=store, reform=request.reform, mechanical=-first.cost,
            inputs=first.inputs, year=year,
            firm_reform=(request.firm_reform if firm_part(request.firm_reform) else None),
            is_rate_change=firm_system.normal_rate_change_points(request.firm_reform,
                                                                 year),
            behaviour_asked=getattr(first, "behaviour_asked", False))
        side = len(results) > 1
        # Side by side, the chain-stage indices (balance, debt, interest) belong to each
        # path; the response lists them as such rather than pick one path's.
        shared = [s for s in specs if not (side and s.stage == indices_module.CHAINE)]
        computed = {i.spec.key: i for i in indices_module.compute(
            shared, trajectory=results[0], **index_inputs)}
        computed = [computed.get(s.key) or indices_module.absent(s, SIDE_BY_SIDE_INDEX)
                    for s in specs]
        per_path = [indices_module.compute(
            [s for s in specs if s.stage == indices_module.CHAINE], trajectory=r,
            **index_inputs) for r in results] if side else []
    except (DebtError, ThetaError, retroaction.FeedbackError,
            maturite.MaturityError) as error:
        raise ServiceError(status_code=422, detail=str(error)) from error

    result = results[0]

    def slices(r: Any) -> list[PredictifSlice]:
        return [PredictifSlice(source=s.source, label=s.label, computed=s.computed,
                               reason=s.reason, low=list(s.low), high=list(s.high))
                for s in r.decomposition.slices]

    def index_rows(found: Any) -> list[PredictifIndex]:
        return [PredictifIndex(**i.payload()) for i in found]

    side_by_side = [PredictifPersistence(
        persistence=r.persistence, label=retroaction.PERSISTENCE_LABELS[r.persistence],
        reform=list(r.reform), delta=list(r.delta), delta_primary=list(r.delta_primary),
        slices=slices(r), conventions=list(r.conventions), gdp_gap=list(r.gdp_gap),
        feedback_primary=list(r.feedback_primary), indices=index_rows(found))
        for r, found in zip(results, per_path, strict=True)] if side else []
    own = None if side else result

    return PredictifResponse(
        years=list(result.years), reference=list(result.reference),
        reform=list(own.reform) if own else None, delta=list(own.delta) if own else None,
        reference_primary=list(result.reference_primary),
        delta_primary=list(own.delta_primary) if own else None,
        priced_years=list(result.priced_years), carried_years=list(result.carried_years),
        spending_name=result.spending_name, growth_name=result.growth_name,
        rate_name=result.rate_name,
        conventions=[c for c in result.conventions if all(c in r.conventions
                                                            for r in results)],
        absent=dict(result.absent), slices=slices(own) if own else [],
        start=PredictifStart(year=start.year, debt_ratio=start.debt_ratio,
                             primary_balance=start.primary_balance,
                             implicit_rate=start.implicit_rate, gdp_eur=start.gdp_eur),
        mechanical_first_year_eur=first.cost,
        mechanical_first_year_by_layer=getattr(first, "layers", None)
        or {"menages": first.cost},
        delta_mechanical=list(result.delta_mechanical),
        theta=dict(result.theta), theta_applied=result.theta_applied,
        closed=dict(result.closed),
        behaviour=(PredictifBehaviour(
            receipts_first_year_eur=at.receipts, box_first_year_eur=list(at.box),
            claimed=list(at.claimed), grade=at.grade) if at is not None else None),
        gdp_gap=list(own.gdp_gap) if own and own.gdp_gap is not None else None,
        feedback_primary=(list(own.feedback_primary)
                          if own and own.feedback_primary is not None else None),
        persistence=own.persistence if own else None, side_by_side=side_by_side,
        indices=index_rows(computed),
        population_view=first.view, population_note=first.note,
        banner=result.banner, debt_banner=DEBT_BANNER,
    )
