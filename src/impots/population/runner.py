"""Run a population through current law and, optionally, through a reform (§4.4).

Reuses the household engine's `system.baseline()` and `system.reformed_for()`, so
the reform cache and `verify_bareme` apply unchanged. That matters: a population
run through an unverified barème is the same worst-case failure as a household run
through one (D-007), multiplied by 199 451.

Results come back as one row per **ménage**, because that is the unit a
distributional analysis works in. Variables computed on other entities are summed
into their ménage: individual variables over household members, foyer and famille
variables over the units inside the household.
"""

from __future__ import annotations

import gc
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import polars as pl

from impots.engine import outputs
from impots.engine.system import baseline, reformed_for
from impots.population import margins
from impots.population.aggregate import ASSIS_SUR_LES_SALAIRES, HORS_CHAMP
from impots.population.to_openfisca import WiringError, build_simulation

if TYPE_CHECKING:  # pragma: no cover - typing only
    from impots.api.schemas import ReformSpec

Tier = Literal["light", "full"]

RUNS_DIR = Path(__file__).resolve().parents[3] / "data" / "processed" / "runs"

#: Deterministic everywhere: the golden aggregates are asserted to the euro.
SAMPLE_SEED = 20240101


@dataclass
class RunResult:
    households: pl.DataFrame
    """One row per ménage: `weight`, then `{key}` and `{key}_reform` per registry row."""
    year: int
    tier: Tier
    n_households: int
    n_persons: int
    sampled: int | None
    timings: dict[str, float] = field(default_factory=dict)
    guards: dict[str, Any] = field(default_factory=dict)
    persons: pl.DataFrame | None = None
    """One row per person of the run: `person_id`, `household_id`,
    `salaire_brut_annuel`, `weight`, then `salaire_super_brut` and, with a reform,
    `salaire_super_brut_reform`. Each person's own labour cost, which C2 reads: a
    household's would lend an earner at the SMIC the cut of a partner at 3 SMIC (D-261).
    And each person's own weight in the run's frame, as the quick tier's subsample scales
    it: the household's mean would miscount members whose weights differ (D-255, D-269).
    """


#: The deductible CSG of the self-employed, a working column of `run` (not reported).
CSG_DEDUCTIBLE_NS = "_csg_deductible_non_salarie"


def households_par_lots(population: pl.DataFrame | Path, lots: int, **kwargs: Any
                        ) -> pl.DataFrame:
    """`run(...).households` over the whole population, `lots` groups of ménages at a time
    (D-362). A full-tier run over 199 451 ménages computes every benefit month by month
    and held 14 GB, past what the container gives; its totals and its deciles are those
    of the households frame, which concatenates. Each ménage goes to one lot by a stable
    hash of its identifier, so a lot is a fair draw and the run is reproducible. What a
    lot cannot see is the population around it: an imputation that ranks ménages (the
    niches, by RFR decile) ranks them within their lot, a sampling term the caller says."""
    import gc
    import zlib

    if lots <= 1:
        return run(population, **kwargs).households
    frame = pl.read_parquet(population) if isinstance(population, Path) else population
    lot = frame["household_id"].map_elements(
        lambda key: zlib.crc32(str(key).encode()) % lots, return_dtype=pl.Int64)
    # The niches are drawn with the probability « published claimants / weighted foyers
    # of the bracket » (`niches.impute`): a lot that weighs a quarter of France would draw
    # four times too many (but 19, étape 1). Each lot then weighs all France while it runs,
    # and its households take their own weight back after. The households' data of
    # `population.menages` the same: each total is calibrated on the lot's weights.
    rescale = bool(kwargs.get("impute_niches") or kwargs.get("impute_menages"))
    total = _household_weight(frame) if rescale else 1.0
    parts = []
    for k in range(lots):
        part = frame.filter(lot == k)
        factor = total / _household_weight(part) if rescale else 1.0
        if rescale:
            part = part.with_columns(pl.col("weight") * factor)
        households = run(part, **kwargs).households
        parts.append(households.with_columns(pl.col("weight") / factor) if rescale
                     else households)
        del part
        gc.collect()
    return pl.concat(parts, how="vertical")


def _household_weight(frame: pl.DataFrame) -> float:
    return float(frame.group_by("household_id").agg(pl.col("weight").mean())["weight"].sum())


def subsample(frame: pl.DataFrame, households: int, seed: int = SAMPLE_SEED) -> pl.DataFrame:
    """A deterministic subsample of `households` ménages that estimates the same totals.

    **Certainty stratum, then SYSTEMATIC PPS on the rest.** Both halves are necessary,
    and the first one is why this function was rewritten.

    Probability-proportional-to-size selection is self-weighting: if the inclusion
    probability of household *i* is π_i = n·w_i/W, the Horvitz-Thompson weight w_i/π_i
    collapses to the constant W/n, so every survivor carries the same population weight
    regardless of how heavy it was in the full file. That is the design this function
    implements, and the constant weight is only correct if π_i really is n·w_i/W.

    **It was not.** The previous implementation drew with
    `np.random.default_rng().choice(..., replace=False, p=...)`, which is NOT PPS
    sampling: numpy draws sequentially and renormalises the remaining probabilities
    after each draw, so a heavy unit's realised inclusion probability saturates towards
    1 instead of reaching n·w_i/W. Measured on a synthetic heavy-tailed population, the
    six heaviest units had assumed π of 1.80 down to 1.31 — values above 1, which is
    already the proof, since no inclusion probability can exceed one — against realised
    π of 0.94 down to 0.86, while the lightest units came in at 1.5x their assumed π.
    Weighting every survivor at W/n on top of that is a BIAS, not noise: the same
    experiment estimated a heavy-tailed total at -10.05 % of truth, where
    Horvitz-Thompson with the realised π returned +0.03 %.

    On this population the bias GREW with the sample, which is the signature that
    distinguishes it from sampling error: the pension mass, calibrated to hit its target
    exactly on the full frame, came out at +1.12 % at n=20 000, +2.34 % at n=50 000 and
    +6.39 % at n=100 000. Unemployment benefit went +0.55 %, -2.61 %, -5.80 %. A larger
    sample was making every reported figure worse.

    The fix has two parts.

    1. **The certainty stratum.** When n·w_i/W >= 1 no design can give unit *i* the
       inclusion probability the self-weighting argument assumes, because that number
       exceeds 1. Such units are taken with certainty and keep their OWN weight. Removing
       them shrinks W and n for the remainder, which can push further units over the
       line, so this iterates to a fixed point.
    2. **Systematic PPS (Madow) on the rest**, over a randomly permuted order: one
       uniform start in [0, W_r/k), then k regular steps through the cumulative weight.
       Every remaining unit then has π_i = k·w_i/W_r exactly, which is <= 1 by
       construction of the stratum, so the constant weight W_r/k is exactly right.

    Total weight is preserved either way — W_certain + k·(W_r/k) = W — which is why the
    test that checked only the total could not fail and did not catch any of this. The
    guard that does is `test_subsample_is_unbiased_for_a_heavy_tailed_total`.
    """
    # MEAN, matching the household weight the runner aggregates with. Using the
    # sum here instead makes the two disagree by household size: PPS then selects
    # on weight x size, and the rescale leaves a big household with mean weight
    # target/size where it should be target. Every aggregate tilts towards small
    # households and nothing raises.
    household_weights = (
        frame.group_by("household_id")
        .agg(pl.col("weight").mean().alias("hw"))
        .sort("household_id")
    )
    total = household_weights.height
    if households >= total:
        return frame

    rng = np.random.default_rng(seed)
    weights = household_weights["hw"].to_numpy().astype(np.float64)
    certain, sampled = _pps_certainty_split(weights, households, rng)

    chosen = np.concatenate([certain, sampled])
    keep = household_weights["household_id"].to_numpy()[chosen]

    # Certainty units keep their own weight (π = 1); the rest are self-weighting at
    # W_rest / k, spread across each household's members in the proportions the survey
    # gave them.
    remainder_weight = weights.sum() - weights[certain].sum()
    per_sampled = remainder_weight / sampled.size if sampled.size else 0.0
    targets = np.concatenate([weights[certain], np.full(sampled.size, per_sampled)])

    scale = pl.DataFrame({
        "household_id": keep,
        "_hh_scale": targets / weights[chosen],
    })
    return (
        frame.filter(pl.col("household_id").is_in(keep))
        .join(scale, on="household_id", how="inner")
        .with_columns((pl.col("weight") * pl.col("_hh_scale")).alias("weight"))
        .drop("_hh_scale")
    )


def _pps_certainty_split(
    weights: np.ndarray, households: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Indices taken with certainty, and indices drawn by systematic PPS.

    Split out because the fixed-point loop is the part that is easy to get subtly
    wrong, and it deserves its own test rather than only being exercised through a
    full subsample.
    """
    total = weights.size
    certain = np.zeros(total, dtype=bool)
    while True:
        free = ~certain
        k = households - int(certain.sum())
        if k <= 0:
            break
        remainder = float(weights[free].sum())
        if remainder <= 0:
            break
        # π would be >= 1 for these, which no design can deliver.
        newly = free & (k * weights >= remainder)
        if not newly.any():
            break
        certain |= newly

    free_index = np.flatnonzero(~certain)
    k = households - int(certain.sum())
    if k <= 0:  # pragma: no cover - only if every unit is a certainty unit
        return np.sort(np.flatnonzero(certain)), np.array([], dtype=np.int64)
    if k >= free_index.size:  # pragma: no cover - degenerate, take everything
        return np.sort(np.flatnonzero(certain)), free_index

    # Systematic PPS over a RANDOM permutation: without the shuffle the selection
    # would depend on the arbitrary household_id ordering, and neighbouring ids in
    # this population are not independent.
    order = rng.permutation(free_index)
    free_weights = weights[order]
    step = free_weights.sum() / k
    start = rng.uniform(0.0, step)
    cumulative = np.cumsum(free_weights)
    picks = np.searchsorted(cumulative, start + step * np.arange(k), side="right")
    picks = np.clip(picks, 0, order.size - 1)
    return np.sort(np.flatnonzero(certain)), np.sort(order[picks])


def _household_index(frame: pl.DataFrame, key: str, household_ids: np.ndarray) -> np.ndarray:
    """For each group of `key`, the position of its ménage in `household_ids`.

    Built by sorting on the same key used to declare the entity, so the returned
    positions line up with the arrays OpenFisca hands back.
    """
    groups = (
        frame.group_by(key).agg(pl.col("household_id").first()).sort(key)
    )
    return np.searchsorted(household_ids, groups["household_id"].to_numpy().astype(str))


def _to_households(
    values: np.ndarray, index: np.ndarray, n_households: int
) -> np.ndarray:
    """Sum an entity-level array into its ménages."""
    return np.bincount(index, weights=values, minlength=n_households)


def _extract(
    built: Any, frame: pl.DataFrame, tier: Tier, guards: dict[str, Any]
) -> dict[str, np.ndarray]:
    """Every registry row for the tier, projected onto ménages and sign-normalised."""
    n_households = built.household_ids.size
    person_index = np.searchsorted(
        built.household_ids, frame["household_id"].to_numpy().astype(str)
    )
    foyer_index = _household_index(frame, "foyer_id", built.household_ids)
    famille_index = _household_index(frame, "famille_id", built.household_ids)
    index_for = {
        "individu": person_index,
        "foyer_fiscal": foyer_index,
        "famille": famille_index,
    }

    # The guard from §1.2: a role that failed to join produces nbptr = 0 for every
    # foyer and no exception anywhere. Checked before anything else is believed.
    nbptr = built.calculate("nbptr")
    guards["nbptr_min"] = float(nbptr.min())
    if nbptr.min() < 1:
        raise WiringError(
            f"nbptr.min() = {nbptr.min()} — a foyer has no parts, which means the role "
            "join silently failed. See to_openfisca.check_role_vocabulary."
        )

    results: dict[str, np.ndarray] = {}
    # Foyer counts, taken at foyer level before anything is summed into ménages.
    # `foyers_imposés` is one of the few validation lines the wage calibration does
    # not touch, so it has to be counted where it actually lives.
    ir_per_foyer = built.calculate("impot_revenu_restant_a_payer")
    results["n_foyers"] = _to_households(
        np.ones_like(ir_per_foyer, dtype=np.float64), foyer_index, n_households
    )
    results["n_foyers_imposes"] = _to_households(
        (ir_per_foyer < -0.5).astype(np.float64), foyer_index, n_households
    )
    # Foyers by marginal bracket (D-362), the DGFiP's « taux marginal » table: the index
    # of the barème's top bracket each foyer reaches, 0 for the 0 % one.
    tranche = built.calculate("ir_tranche")
    for k in range(5):
        results[f"n_foyers_tmi_{k}"] = _to_households(
            (tranche == k).astype(np.float64), foyer_index, n_households
        )
    # The CSG on replacement incomes, by base (D-362), for the verification grid only:
    # population passes, not the wire format, whose rows are the API's. Engine-signed
    # negative, reported as a positive receipt like the salary's CSG rows.
    individu_index = index_for["individu"]
    for key, names in (("csg_retraite", ("csg_deductible_retraite", "csg_imposable_retraite")),
                       ("csg_chomage", ("csg_deductible_chomage", "csg_imposable_chomage")),
                       # What the state takes back on a pension and the household feels:
                       # the pensions are declared net of the deductible CSG (D-176), so
                       # only these move disposable income (D-387).
                       ("prelevements_pensions", ("csg_imposable_retraite", "crds_retraite",
                                                  "casa"))):
        array = sum(built.calculate(name, add=True) for name in names)
        results[key] = -_to_households(array.astype(np.float64), individu_index,
                                       n_households)
    # The self-employed (but 19, étape 2), for the grid too: their CSG, which the
    # published CSG on activity income counts beside the salaries', and their income as
    # the 2042-C-PRO declares it, after the micro abatement, versement libératoire
    # included; and the same without the gérants majoritaires, whose pay the DGFiP
    # counts among the salaries (art. 62 CGI) and the population as a réel profit.
    csg_ns = sum(built.calculate(name) for name in ("csg_deductible_non_salarie",
                                                    "csg_imposable_non_salarie"))
    results["csg_non_salarie"] = -_to_households(csg_ns.astype(np.float64), individu_index,
                                                 n_households)
    # Its deductible part, apart: the declared income the population gives openfisca is
    # already net of it, so a reform of its rate moves the receipt and not the income;
    # `run` gives the difference back to the reform's disposable income (but 19).
    results[CSG_DEDUCTIBLE_NS] = -_to_households(
        built.calculate("csg_deductible_non_salarie").astype(np.float64), individu_index,
        n_households)
    rpns = built.calculate("rpns_imposables").astype(np.float64)
    liberatoire = _to_households(built.calculate("microentreprise").astype(np.float64),
                                 foyer_index, n_households)
    results["revenus_non_salaries"] = (
        _to_households(rpns, individu_index, n_households) + liberatoire)
    gerant = (frame["regime_non_salarie"].is_in(["gerant_bic", "gerant_bnc"])
              .fill_null(False).to_numpy() if "regime_non_salarie" in frame.columns
              else np.zeros(frame.height, dtype=bool))
    results["revenus_non_salaries_hors_gerants"] = (
        _to_households(np.where(gerant, 0.0, rpns), individu_index, n_households)
        + liberatoire)
    # What each person's wage-borne amounts count beyond themselves in the totals: the
    # employees the survey does not see, taken to be like those it does (étape
    # « extrapolation », `aggregate.ASSIS_SUR_LES_SALAIRES`). The gérants are paid their
    # declared pay, already the whole of theirs, and are not carried.
    hors_champ = np.where(gerant, 0.0, margins.EXTRAPOLATION_SALARIES.value - 1.0)

    # The employers' contributions as the national accounts count them (D121), for the
    # verification grid only (but 19, étape 1; `docs/diagnostics/cotisations_employeurs.md`).
    # `salaire_super_brut − salaire_brut` holds three things D121 does not, each kept
    # here as a positive amount so the grid can take it out and show it apart:
    # the levies on wages the Insee books as taxes (D291), the State's contribution to
    # its own civil servants' and soldiers' pensions (an imputed contribution, D122),
    # and the résidence allowance and the SFT, wages (D11) that `salaire_brut` leaves out.
    # Population passes, not the API's rows (D-363); no cost reads them.
    for key, value in employeurs_d121(built).items():
        results[key] = _to_households(value, individu_index, n_households)
        _hors_champ(results, key, value, hors_champ, individu_index, n_households)

    # Allocataire counts, at FAMILLE level and in December.
    #
    # `margins.BENEFIT_RECIPIENTS` carries four `use="validation"` figures that were
    # printed in the report's Sources table with no line comparing anything to them —
    # the D-072 defect in the counts: a target that looks spent and never was. The
    # zero-masked sweep found them.
    #
    # December, not the year: the published figures are stocks au 31/12, and an annual
    # read counts every famille entitled at any point, which is a larger and different
    # number. Famille, not ménage: an allocataire is a famille, and a ménage can hold
    # more than one — counting ménages would understate by exactly the households that
    # contain two claiming familles.
    # Full tier only: these are the benefit variables, and the light tier exists
    # precisely so a caller can skip computing them.
    if tier == "full":
        for key in ("af", "ppa", "rsa", "aide_logement"):
            monthly = built.calculate(key, month=12)
            results[f"n_allocataires_{key}"] = _to_households(
                (monthly > 0.5).astype(np.float64), famille_index, n_households
            )

    variables = built.simulation.tax_benefit_system.variables
    for row in outputs.rows_for(tier):
        # A variable of the project's that this system does not carry reads zero, as in
        # `outputs.extract`: the new benefits of a programme exist only in the reform that
        # poses them (but 21, étape 3).
        if row.projet and row.variable not in variables:
            results[row.key] = np.zeros(n_households)
            continue
        array = sum(built.calculate(name, add=row.period == "month")
                    for name in (row.variable, *row.extra))
        if row.entity == "menage":
            values = array.astype(np.float64)
        else:
            values = _to_households(
                array.astype(np.float64), index_for[row.entity], n_households
            )
        results[row.key] = -values if row.negate else values
        if row.key in ASSIS_SUR_LES_SALAIRES and row.entity == "individu":
            _hors_champ(results, row.key,
                        -array.astype(np.float64) if row.negate else array.astype(np.float64),
                        hors_champ, individu_index, n_households)
    if tier == "full":
        _serve_in_expectation(results, built, famille_index, n_households)
    return results


def _hors_champ(results: dict[str, np.ndarray], key: str, per_person: np.ndarray,
                hors_champ: np.ndarray, index: np.ndarray, n_households: int) -> None:
    """`{key}_hors_champ`: per ménage, what its members' `key` stands for beyond
    themselves, the employees outside the survey (`aggregate.extrapole`). Zero for a
    ménage without an employee; never read by a household's own figures."""
    results[f"{key}{HORS_CHAMP}"] = _to_households(per_person * hors_champ, index,
                                                   n_households)


#: The levies on wages OpenFisca counts in `cotisations_employeur` and the national
#: accounts class as taxes on wages (D291, Insee tableau 3.217, lines 39 to 48): training
#: and apprenticeship, the CSA, the Fnal, the AGS, the taxe sur les salaires, the forfait
#: social, the versement mobilité, the PEEC. Six are zero in the population today (no
#: employer size, commune or liability is wired); they are listed so that wiring them
#: later moves them out of D121 with the rest.
PRELEVEMENTS_D291 = (
    "contribution_unique_formation_professionnelle_alternance",
    "contribution_solidarite_autonomie", "fnal", "ags", "taxe_salaires", "forfait_social",
    "versement_transport", "participation_effort_construction",
    "contribution_developpement_apprentissage",
    "contribution_supplementaire_apprentissage", "conge_individuel_formation_cdd",
)
#: The categories whose employer, the State, pays their pension itself: its
#: contribution is imputed (D122), not effective. The CNRACL's (territorial, hospital)
#: is a fund apart, and stays in D121.
PENSION_ETAT = ("public_titulaire_etat", "public_titulaire_militaire")
#: Wages (D11) that `salaire_super_brut` holds and `salaire_brut` does not.
REMUNERATION_HORS_BRUT = ("indemnite_residence", "supplement_familial_traitement")


def employeurs_d121(built: Any) -> dict[str, np.ndarray]:
    """Per person, over the year, in euros and positive: what separates
    `salaire_super_brut − salaire_brut` from D121 (but 19, étape 1).

    * `prelevements_salaires_d291`: the `PRELEVEMENTS_D291`, engine-signed negative;
    * `pension_employeur_etat`: `pension_employeur` of the months a person is in a
      `PENSION_ETAT` category, month by month as the category is posed. The ATI the
      State pays (`ati_atiacl`, 0,3 Md€ on the diagnostic's sample) stays in D121, a
      hypothesis said in the step's report;
    * `remuneration_hors_brut`: the `REMUNERATION_HORS_BRUT`.

    Worked example, held in the tests: a State civil servant whose `salaire_brut` is
    36 000 € has a TIB of 36 000 / 1,195 = 30 126 €, and the State's pension
    contribution, 74,28 % of it, is 22 378 €."""
    d291 = -sum(np.asarray(built.calculate(name, add=True), dtype=np.float64)
                for name in PRELEVEMENTS_D291)
    etat = np.zeros_like(d291)
    for month in range(1, 13):
        categorie = built.calculate("categorie_salarie", month=month)
        mask = np.isin(np.asarray(categorie.decode_to_str()), PENSION_ETAT)
        pension = np.asarray(built.calculate("pension_employeur", month=month),
                             dtype=np.float64)
        etat -= np.where(mask, pension, 0.0)
    hors_brut = sum(np.asarray(built.calculate(name, add=True), dtype=np.float64)
                    for name in REMUNERATION_HORS_BRUT)
    return {"prelevements_salaires_d291": d291, "pension_employeur_etat": etat,
            "remuneration_hors_brut": hors_brut}


#: The columns the take-up layer serves in expectation (but 19, étape 4). Each keeps its
#: full-take-up entitlement beside it as `{key}_droit`.
SERVED = ("rsa", "ppa", "crds_mini", "aefa")


def _serve_in_expectation(results: dict[str, np.ndarray], built: Any,
                          famille_index: np.ndarray, n_households: int) -> None:
    """Serve the RSA and the prime d'activité in expectation (`population.recours`).

    The engine computes an ENTITLEMENT; the Caf counts what it PAYS. From here on, `rsa`,
    `ppa`, their CRDS (`crds_mini`) and the prime de Noël (`aefa`) are what each famille
    is paid in expectation, its probability of take-up times its entitlement, month by
    month; `revenu_disponible` loses what is not claimed. The entitlements stay, as
    `{key}_droit` and `revenu_disponible_droit`, for the lines that compare an
    entitlement through the Drees bridge (the reconciliation and the grid, D-363), and
    for a reader who wants the full-take-up figure. The cost of a reform, its deciles and
    its instrument deltas are then the difference of two expectations, which counts the
    families a larger entitlement brings to claim it. The allocataire counts stay
    entitlement counts; `n_allocataires_{rsa,ppa}_servi` are the expected payees.
    """
    from impots.population import recours

    famille = recours.colonnes(built)
    unclaimed = np.zeros(n_households)
    # The new benefits a reform poses are served too, each with the law of the benefit
    # closest to it (`recours.LOI_PROCHE`, but 21, étape 3). Where the system does not
    # carry one, the law above all, it is zero, and so is its entitlement.
    for key in recours.LOI_PROCHE:
        if f"{key}_droit" not in famille:
            results[f"{key}_droit"] = results[key]
    for key in (*SERVED, *(k for k in recours.LOI_PROCHE if f"{k}_droit" in famille)):
        droit = _to_households(famille[f"{key}_droit"], famille_index, n_households)
        paid = _to_households(famille[f"{key}_servi"], famille_index, n_households)
        # The registry's own read and the month-by-month one must be the same euros:
        # a gap would be served money the cost cannot see.
        if not np.allclose(droit, results[key], rtol=1e-6, atol=0.05):
            raise WiringError(f"{key} : le droit mois par mois ne refait pas celui de la "
                              f"passe ({float(droit.sum()):.2f} contre "
                              f"{float(results[key].sum()):.2f})")
        results[f"{key}_droit"] = results[key]
        results[key] = paid
        unclaimed += results[f"{key}_droit"] - paid
    for key in recours.PRESTATIONS:
        results[f"n_allocataires_{key}_servi"] = _to_households(
            famille[f"n_{key}_servi"], famille_index, n_households)
    results["revenu_disponible_droit"] = results["revenu_disponible"]
    results["revenu_disponible"] = results["revenu_disponible"] - unclaimed


def _impute_niches(built: Any, frame: pl.DataFrame, year: int) -> dict[str, Any]:
    """Draw niche bases from the published decile table, keyed on RFR per part.

    Needs a simulation that has already been built, because the decile a foyer falls
    into depends on its revenu fiscal de référence — which is an output, not an input.
    That is the whole reason this costs a second pass.
    """
    from impots.population import niches as niches_module

    simulation = built.simulation
    rfr = np.asarray(simulation.calculate("rfr", str(year)), dtype=np.float64)
    parts = np.asarray(simulation.calculate("nbptr", str(year)), dtype=np.float64)
    # A foyer with no parts would be a wiring failure upstream; guard rather than
    # divide, so it surfaces here instead of as a silent decile-1 assignment.
    if (parts <= 0).any():
        raise WiringError("a foyer fiscal reports zero parts; RFR per part is undefined")
    rfr_per_part = rfr / parts

    # Foyer weight: the MEAN of member weights, matching the household convention in
    # `run` — EXTRIAN is an individual weight but the survey weights a dwelling
    # together, and summing would multiply every foyer-level total by foyer size.
    weights = (
        frame.group_by("foyer_id").agg(pl.col("weight").mean().alias("weight"))
        .sort("foyer_id")["weight"].to_numpy().astype(np.float64)
    )
    if weights.shape != rfr_per_part.shape:
        raise WiringError(
            f"foyer weights {weights.shape} do not line up with RFR {rfr_per_part.shape}")
    return niches_module.impute(rfr_per_part, weights, year=year)


def _impute_capital(built: Any, frame: pl.DataFrame, year: int,
                    index: float = 1.0) -> dict[str, Any]:
    """Hand out the PFU's base from DGFiP n° 41's fractiles, keyed on RFR per part (D-248).

    Needs a simulation that has already been built, for the same reason `_impute_niches`
    does. **It runs FIRST, before the niches, and the order is load-bearing:** the
    capital income enters the RFR, and the niche deciles are deciles of that RFR. The
    top-tail rake is refused beside it (`run`): it fits n° 41's RFR, which holds the
    capital, by scaling earnings alone.

    In another year than the table's, the foyers are ranked on that year's RFR per part,
    and each band's 2024 base is multiplied by `index`, the base's growth since 2024
    (D-249): the ranks move nothing, the euros follow the index.
    """
    from impots.population import capital as capital_module

    simulation = built.simulation
    rfr = np.asarray(simulation.calculate("rfr", str(year)), dtype=np.float64)
    parts = np.asarray(simulation.calculate("nbptr", str(year)), dtype=np.float64)
    if (parts <= 0).any():
        raise WiringError("a foyer fiscal reports zero parts; RFR per part is undefined")
    weights = (
        frame.group_by("foyer_id").agg(pl.col("weight").mean().alias("weight"))
        .sort("foyer_id")["weight"].to_numpy().astype(np.float64)
    )
    if weights.shape != rfr.shape:
        raise WiringError(
            f"foyer weights {weights.shape} do not line up with RFR {rfr.shape}")
    menages = float(frame.group_by("household_id").agg(pl.col("weight").mean())
                    ["weight"].sum())
    bases = capital_module.impute(rfr / parts, weights, menages=menages,
                                  year=capital_module.YEAR)
    return {case: base * index for case, base in bases.items()}


def _salaires_payes(built: Any, reformed_built: Any, frame: pl.DataFrame
                    ) -> dict[str, np.ndarray]:
    """Per ménage, base and reform, the wage bills a reform of the salaries moves
    (`aggregate.SALAIRES_PAYES`): the gross pay of the private earners, which their
    employers pay and the state does not, and the gross and labour cost of the public
    ones, which the state pays. Each with its `_hors_champ` column, as the other wage-borne
    amounts (étape « extrapolation »)."""
    from impots.population.aggregate import SALAIRES_PAYES

    public = (frame["secteur_public"].fill_null(False).to_numpy().astype(bool)
              if "secteur_public" in frame.columns else np.zeros(frame.height, dtype=bool))
    gerant = (frame["regime_non_salarie"].is_in(["gerant_bic", "gerant_bnc"])
              .fill_null(False).to_numpy() if "regime_non_salarie" in frame.columns
              else np.zeros(frame.height, dtype=bool))
    hors_champ = np.where(gerant, 0.0, margins.EXTRAPOLATION_SALARIES.value - 1.0)
    n_households = built.household_ids.size
    index = np.searchsorted(built.household_ids,
                            frame["household_id"].to_numpy().astype(str))
    out: dict[str, np.ndarray] = {}
    for suffix, sim in (("", built), ("_reform", reformed_built)):
        # `salaire_brut` as the registry reads it (`engine.outputs`): the base, the
        # traitement and the public primes.
        brut = sum(np.asarray(sim.calculate(name, add=True), dtype=np.float64)
                   for name in ("salaire_de_base", "remuneration_principale",
                                "primes_fonction_publique"))
        super_brut = np.asarray(sim.calculate("salaire_super_brut", add=True),
                                dtype=np.float64)
        # And the CSG compensation allowance, paid on the traitement, which the salaire
        # imposable holds and neither the brut nor the super-brut does.
        hors_brut = sum(np.asarray(sim.calculate(name, add=True), dtype=np.float64)
                        for name in (*REMUNERATION_HORS_BRUT,
                                     "indemnite_compensatrice_csg"))
        par_cle = {SALAIRES_PAYES[0]: np.where(public, 0.0, brut),
                   SALAIRES_PAYES[1]: np.where(public, brut, 0.0),
                   SALAIRES_PAYES[2]: np.where(public, super_brut, 0.0),
                   SALAIRES_PAYES[3]: np.where(public, hors_brut, 0.0)}
        for key, per_person in par_cle.items():
            out[f"{key}{suffix}"] = _to_households(per_person, index, n_households)
            out[f"{key}{HORS_CHAMP}{suffix}"] = _to_households(
                per_person * hors_champ, index, n_households)
    return out


def _rake_top_tail(built: Any, frame: pl.DataFrame, year: int) -> tuple[pl.DataFrame, Any]:
    """Rake the income distribution's upper tail onto DGFiP n° 41's fractiles (L1, D-121).

    Needs a simulation that has already been built, for the same reason `_impute_niches`
    does: the band a foyer falls into depends on its RFR per part, which is an OUTPUT. That
    is why this costs an extra pass rather than being a frame transformation.

    **It runs BEFORE the niche imputation, and the order is load-bearing.** The niche
    deciles are deciles of RFR per part; the rake moves RFR per part. Imputing first would
    hand out niche bases by a decile ranking the rake then invalidates.
    """
    from impots.population import top_tail as top_tail_module

    simulation = built.simulation
    rfr = np.asarray(simulation.calculate("rfr", str(year)), dtype=np.float64)
    parts = np.asarray(simulation.calculate("nbptr", str(year)), dtype=np.float64)
    if (parts <= 0).any():
        raise WiringError("a foyer fiscal reports zero parts; RFR per part is undefined")

    grouped = (frame.group_by("foyer_id").agg(pl.col("weight").mean().alias("weight"))
               .sort("foyer_id"))
    weights = grouped["weight"].to_numpy().astype(np.float64)
    if weights.shape != rfr.shape:
        raise WiringError(
            f"foyer weights {weights.shape} do not line up with RFR {rfr.shape}")

    per_foyer, band_factors = top_tail_module.factors(rfr / parts, weights)
    return top_tail_module.apply(frame, grouped["foyer_id"].to_list(), per_foyer,
                                 band_factors)


def run(
    population: pl.DataFrame | Path,
    year: int = 2024,
    reform: ReformSpec | None = None,
    tier: Tier = "light",
    sample: int | None = None,
    impute_niches: bool = False,
    rake_top_tail: bool = False,
    impute_capital: bool = False,
    capital_index: float | None = None,
    impute_ij: bool = False,
    impute_consommation: bool = False,
    prix_au_dela: dict[int, float] | None = None,
    annee_consommation: int | None = None,
    impute_menages: bool = False,
    menages_facteurs: dict[str, float] | None = None,
) -> RunResult:
    """Run the population through current law and, optionally, one reform.

    `impute_niches` hands out réduction and crédit d'impôt bases from the published
    DGFiP decile table before the figures are taken. It costs one extra baseline pass,
    because the deciles are of revenu fiscal de référence per part and that is not
    known until a first pass has computed it.

    **It is a calibration.** The national niche total then matches DGFiP by
    construction and cannot afterwards be cited as evidence of anything —
    `population.niches` says so at length, and `margins.NICHE_CREDITS_BY_DECILE`
    carries `use="calibration"`.

    `impute_capital` hands out the base the PFU taxes, from n° 41's fractiles (D-248).
    It is a calibration too — `margins.CAPITAL_PFU_BY_FRACTILE` — and runs before the
    rake and the niches, which read the RFR it moves. The tables describe the 2024
    income: another year takes `capital_index`, the base's growth since 2024, which the
    caller declares as it declares the population's uprating (D-249), and is refused by
    name without it, before any pass. So is the top-tail rake beside it: the rake fits
    n° 41's RFR, which holds the capital, by scaling earnings alone, so with the capital
    imputed it takes 5,4 % off the wage bill (measured on 2 000 ménages) and the spent
    wage margin no longer holds.

    `impute_ij` hands the régime général's sick pay of 2024 to the private sector's
    employees, from the CCSS of May 2026 (D-305). A calibration again —
    `margins.SICK_PAY_BY_BRANCH` — and a frame transformation, so it costs no pass. It is
    refused for another year, by `population.ij`, before any pass.

    `impute_menages` hands out the households' data the programmes' measures need (but 21,
    étape 4): overtime, commuting costs and frais réels, alimony received and paid,
    childcare under six, the interest on a main-residence loan, each calibrated on the
    published total it names (`population.menages`, spent). A frame transformation, no
    pass; its childcare replaces the niches' case 7GA when both run. For another year than
    2024, `menages_facteurs` says what aged the frame (wage and price factors from 2024,
    `menages.facteurs_de`): the imputation runs on the frame brought back to 2024 and its
    amounts age with the index of `menages.INDICES`. Without them, refused.

    A reform of the SMIC or of the point d'indice (`population.salaires`) changes the
    salaries of the priced year: the reformed pass is built on the population whose
    salaries it raises, on a tree that carries the new SMIC, and the households frame
    carries the wage bills the cost needs (`SALAIRES_PAYES`).
    """
    from impots import consommation as conso_module

    if conso_module.touche(reform) and not impute_consommation:
        raise WiringError(
            "la réforme règle la TVA ou une accise, que seule la consommation imputée "
            "porte : demander l'imputation « consommation » (D-323)")
    from impots.population.imputations import menages_knobs

    lus = sorted(set(reform.model_dump(exclude_none=True)) & menages_knobs()
                 if reform is not None else ())
    if lus and not impute_menages:
        raise WiringError(
            f"{', '.join(lus)} sur la population sans les données de ménages : ni les "
            f"heures supplémentaires, ni les frais de trajet, ni les pensions alimentaires, "
            f"ni les intérêts d'emprunt, ni les étudiants du supérieur n'y sont, et le coût "
            f"serait un zéro qui se lirait comme un chiffrage. Demander l'imputation "
            f"« menages » (but 21, étape 4).")
    if menages_facteurs is not None and not impute_menages:
        raise ValueError("facteurs des données de ménages sans leur imputation : ils "
                         "vieillissent les montants imputés, et ne se donnent qu'avec elle")
    conso_reform = reform
    if reform is not None and conso_module.touche(reform):
        reform = conso_module.sans_consommation(reform)
    if capital_index is not None and (not impute_capital or not capital_index > 0):
        raise ValueError(
            f"indice du capital {capital_index} : il vieillit l'assiette imputée, et ne "
            f"se donne qu'avec l'imputation, strictement positif (D-249)")
    if impute_capital:
        from impots.population import capital as capital_module

        if year != capital_module.YEAR and capital_index is None:
            raise ValueError(
                f"imputation des revenus du capital pour {year} : la DGFiP n° 41 décrit "
                f"les revenus {capital_module.YEAR}, et une autre année demande de "
                f"vieillir l'assiette par un indice déclaré (`capital_index`), qui manque "
                f"(D-248, D-249)")
        if rake_top_tail:
            raise ValueError(
                "imputation du capital et recalage de la queue (L1) ensemble : le "
                "recalage vise le RFR de la DGFiP n° 41, qui contient le capital, en ne "
                "touchant qu'aux salaires, pensions et chômage ; avec le capital imputé "
                "il retire 5,4 % à la masse salariale, et la marge des salaires, "
                "dépensée, ne tient plus (D-248)")
    frame = pl.read_parquet(population) if isinstance(population, Path) else population
    if sample is not None:
        frame = subsample(frame, sample)
    frame = frame.sort("person_id")
    if impute_ij:
        from impots.population import ij as ij_module

        frame = ij_module.impute(frame, year)
    menages_stats = None
    if impute_menages:
        from impots.population import menages as menages_module

        started = time.perf_counter()
        # A `MenagesError` is a `ValueError`: each path refuses it as it refuses the others.
        frame, menages_stats = menages_module.impute(frame, year, facteurs=menages_facteurs)
        menages_timing = round(time.perf_counter() - started, 2)
    from impots.population import salaires as salaires_module

    salary_reform = salaires_module.touche(reform)
    reform_frame, salary_stats = frame, None
    if salary_reform:
        reform_frame, salary_stats = salaires_module.appliquer(frame, reform, year)

    guards: dict[str, Any] = {}
    timings: dict[str, float] = {}
    if menages_stats is not None:
        timings["menages_s"] = menages_timing

    started = time.perf_counter()
    built = build_simulation(frame, baseline(), year)
    timings["build_s"] = round(time.perf_counter() - started, 2)

    # The capital income first: it enters the RFR the rake and the niches read (D-248).
    capital_bases: dict[str, Any] | None = None
    if impute_capital:
        started = time.perf_counter()
        capital_bases = _impute_capital(
            built, frame, year, 1.0 if capital_index is None else capital_index)
        built = build_simulation(frame, baseline(), year, capital_bases=capital_bases)
        timings["capital_s"] = round(time.perf_counter() - started, 2)

    # L1's rake, BEFORE the niche imputation: the niche deciles are deciles of RFR per
    # part, and the rake moves RFR per part.
    rake: Any = None
    if rake_top_tail:
        started = time.perf_counter()
        frame, rake = _rake_top_tail(built, frame, year)
        built = build_simulation(frame, baseline(), year, capital_bases=capital_bases)
        timings["rake_s"] = round(time.perf_counter() - started, 2)
        guards["top_tail_total_shift"] = rake.total_shift
        guards["top_tail_foyers_moved"] = rake.foyers_moved

    niche_bases: dict[str, Any] | None = None
    if impute_niches:
        started = time.perf_counter()
        niche_bases = _impute_niches(built, frame, year)
        if impute_menages:
            # The childcare `population.menages` imputes, child by child, replaces the
            # niches' 7GA, drawn by decile without looking at the children's ages.
            niche_bases = {case: base for case, base in niche_bases.items()
                           if case not in menages_module.REMPLACE_NICHES}
        built = build_simulation(frame, baseline(), year, niche_bases,
                                 capital_bases=capital_bases)
        timings["impute_s"] = round(time.perf_counter() - started, 2)

    started = time.perf_counter()
    baseline_rows = _extract(built, frame, tier, guards)
    timings["baseline_s"] = round(time.perf_counter() - started, 2)

    # Per person, in the frame's order, as the simulation was built. Already computed
    # for the registry's household row, so this reads openfisca's cache.
    persons = frame.select("person_id", "household_id", "salaire_brut_annuel",
                           "weight").with_columns(
        pl.Series("salaire_super_brut",
                  built.calculate("salaire_super_brut", add=True).astype(np.float64)))
    columns: dict[str, np.ndarray] = dict(baseline_rows)
    if reform is not None and not reform.is_empty():
        started = time.perf_counter()
        # Les pensions sont des données : leur indexation multiplie la pension de la passe
        # de la réforme, et d'elle seule (but 21, étape 2).
        from impots.engine.boutons_programmes import facteur_pensions

        pension_factor = facteur_pensions(reform, year)
        if pension_factor != 1.0:
            reform_frame = reform_frame.with_columns(
                pl.col("pension_annuelle") * pension_factor)
        if not salary_reform:
            system = reformed_for(reform, year)
        else:
            tree = salaires_module.sans_salaires(reform)
            system = baseline() if tree.is_empty() else reformed_for(tree, year)
            if reform.smic_revalorisation is not None:
                system = salaires_module.reforme_smic(system, reform.smic_revalorisation,
                                                      year)
        reformed_built = build_simulation(
            reform_frame, system, year, niche_bases,
            capital_bases=capital_bases)
        reform_guards: dict[str, Any] = {}
        reform_rows = _extract(reformed_built, frame, tier, reform_guards)
        guards["nbptr_min_reform"] = reform_guards["nbptr_min"]
        timings["reform_s"] = round(time.perf_counter() - started, 2)
        for key, values in reform_rows.items():
            columns[f"{key}_reform"] = values
        # A self-employed person declares an income net of the deductible CSG (5KC, 5QC…):
        # the population holds that declared income fixed, so a cut of the rate would
        # leave it where it is while the receipt falls, a cost no household receives
        # (the sector balance refused Lisnard's CSG at 6,6 % by exactly that part, 1,27
        # Md€ on 15 000 ménages). The declared income of the reform is the baseline's
        # plus the deductible CSG it no longer pays; its income-tax feedback, which that
        # higher declared income would carry, is not computed, a small omission said.
        gain = columns[CSG_DEDUCTIBLE_NS] - columns[f"{CSG_DEDUCTIBLE_NS}_reform"]
        for key in ("revenu_disponible", "revenu_disponible_droit"):
            if f"{key}_reform" in columns:
                columns[f"{key}_reform"] = columns[f"{key}_reform"] + gain
        persons = persons.with_columns(pl.Series(
            "salaire_super_brut_reform",
            reformed_built.calculate("salaire_super_brut", add=True).astype(np.float64)))
        if salary_reform:
            columns.update(_salaires_payes(built, reformed_built, frame))
    for key in [k for k in columns if k.startswith(CSG_DEDUCTIBLE_NS)]:
        del columns[key]
    baseline_rows.pop(CSG_DEDUCTIBLE_NS, None)

    # The MEAN of member weights, not the sum. EXTRIAN is an individual weight, but
    # the survey weights a whole dwelling together: it is identical across members
    # in 98.5 % of households. Taking the mean reproduces both published totals
    # exactly — 55.44 M persons aged 15+ and 31.45 M ménages, against INSEE's ~31 M.
    # Taking the sum, which is the natural thing to write, multiplies every
    # household-level aggregate by household size: it implied a population of
    # 120 M and inflated every euro total by 2.2x, silently.
    household_weight = (
        frame.group_by("household_id").agg(pl.col("weight").mean().alias("weight"))
        .sort("household_id")
    )
    # Counts keyed on AGE, not on role: the OECD-modified consumption scale splits
    # at 14, which has nothing to do with who is a dependant for tax.
    persons_per_household = (
        frame.group_by("household_id").agg(
            pl.len().alias("n_persons"),
            (pl.col("age") >= 14).sum().alias("n_aged_14_plus"),
            (pl.col("age") < 14).sum().alias("n_children_under_14"),
            (pl.col("role_foyer") == "personne_a_charge").sum().alias("n_dependants"),
        ).sort("household_id")
    )

    households = pl.DataFrame({
        "household_id": built.household_ids,
        "weight": household_weight["weight"].to_numpy(),
        "n_persons": persons_per_household["n_persons"].to_numpy(),
        "n_aged_14_plus": persons_per_household["n_aged_14_plus"].to_numpy(),
        "n_children_under_14": persons_per_household["n_children_under_14"].to_numpy(),
        "n_dependants": persons_per_household["n_dependants"].to_numpy(),
        **{key: values for key, values in columns.items()},
    })

    if conso_reform is not None and not conso_reform.is_empty() and (
            reform is None or reform.is_empty()):
        # A reform of consumption taxes alone moves nothing in the tree: its rows are the
        # baseline's, and the consumption layer below carries the whole of it (D-323).
        households = households.with_columns(
            [pl.col(key).alias(f"{key}_reform") for key in baseline_rows])
    if impute_consommation:
        started = time.perf_counter()
        couche = conso_module.colonnes(households, year, conso_reform, prix_au_dela,
                                       annee_consommation)
        households = households.with_columns(
            [pl.Series(key, values) for key, values in couche.items()])
        columns.update(couche)
        timings["consommation_s"] = round(time.perf_counter() - started, 2)

    guards["nan_columns"] = [
        key for key in columns if not np.isfinite(columns[key]).all()
    ]
    if guards["nan_columns"]:
        raise WiringError(f"non-finite values in {guards['nan_columns']}")

    # A simulation is a cycle, its holders and populations pointing back at it, that only a
    # full collection frees: kept, the run's outlived it, and four runs in one process went
    # past the container (D-334). What the run returns no longer needs them.
    n_households, n_persons = built.household_ids.size, built.n_persons
    built = reformed_built = None
    gc.collect()
    if salary_stats is not None:
        guards["salaires"] = salary_stats
    if menages_stats is not None:
        guards["menages"] = menages_stats
    return RunResult(
        households=households,
        year=year,
        tier=tier,
        n_households=n_households,
        n_persons=n_persons,
        sampled=sample,
        timings=timings,
        guards=guards,
        persons=persons,
    )
