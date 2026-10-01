"""Phase 7 A0 — the eight reference reforms, and what each of their sources actually is.

**One reform per instrument family, committed as data.** A0's ranking is only meaningful
against a fixed set: if the cases moved between runs, a lever's score would be a fact about
which reform someone happened to pick that week. So they live here as literals with their
provenance, not as arguments.

THE CASES ARE FIXED DESIGN POINTS, NEVER A SOURCE. Reform knobs carry no distribution
anywhere in this repository, and `ReformSpec`'s `ge`/`le` are input validation — the schema
says so in its own words. Treating a validation bound as an uncertainty would invent an
error bar for a number the legislator states exactly.

TWO SOURCES THAT LOOK LIKE UNCERTAINTY AND ARE NOT. Both were found by asking standing
question four — «what is this number the difference of, exactly?» — and both would have
ranked high enough to misdirect the campaign:

1. **The aged/frozen pair is not an uprating interval.** Its low end prices a 2024
   population whose incomes never grew at all. See `accuracy` for the full argument.
2. **Subsample-seed noise is zero in production.** `runner.run(sample=None)` uses the whole
   frame, so re-seeding `subsample` changes nothing that is deployed. It is real, it is
   worth knowing — it is the RESOLUTION of any measurement A0 itself makes on a subsample —
   but it is not a model error source, and ranking it as one would send Phase 7 at a
   quantity that does not exist when the model is run for real. It is therefore reported in
   its own section rather than in the ranking.

The population-construction seeds that DO survive are `skeleton.SEED` and `incomes.SEED`:
the synthetic France is built once from them and never rebuilt. Measuring that source means
rebuilding the population at a second seed, which is a gate of its own — so it is declared
UNMEASURED here, with that as its reason, rather than quietly proxied by the subsample.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from impots.accuracy import Source
from impots.donnees import PROCESSED

#: The firm cell table and its vintage — GENERATED, not committed. `data/processed/*` is
#: gitignored and this file has never been in git history; the comment here used to say
#: « Committed », which is part of why nobody looked for the command that produces it.
#: There was none: `impots entreprises cells` writes it now, from the three published
#: spreadsheets, and `impots data check` says when it is missing. A re-run reads the same
#: cells because the build is deterministic from checksummed sources, not because the
#: output is versioned.
#:
#: Anchored at the repository root. It was `Path("data/processed/...")`, relative to the
#: CURRENT directory, so a file that was present read as absent outside the root.
FIRM_CELLS = PROCESSED / "firm_cells_2023.json"

#: L'année que la chaîne entreprises chiffre. Une seule constante, lue par
#: l'échantillonneur ET par le refus structurel, pour que les deux ne jugent jamais
#: deux années différentes.
FIRM_YEAR = 2026

#: Draw counts. The firm placement chain costs ~0,2 s a draw, so it can afford a real
#: sample; the household chain costs ~15 s a call and cannot. Stated rather than tuned:
#: a budget whose draw count moved between sources would be comparing resolutions.
FIRM_DRAWS = 128
HOUSEHOLD_DRAWS = 12


@dataclass(frozen=True)
class ReferenceReform:
    """One committed reference reform, with the family it stands for."""

    key: str
    label: str
    family: str
    chain: str
    knob: str
    value: float
    note: str = ""


#: The eight families the spec names. Values are the committed reference values already
#: executed elsewhere in the repository — `tests/knob_cases.py` for the household knobs, the
#: `scenarios/` fiches for the two with published cards — so A0 prices what the project has
#: already priced rather than inventing a new design point nobody has looked at.
REFERENCE_REFORMS: tuple[ReferenceReform, ...] = (
    ReferenceReform(
        key="bareme", label="Décote : taux porté à 30 %", family="barème",
        chain="household", knob="decote_taux", value=0.30,
        note="valeur de référence de tests/knob_cases.py"),
    ReferenceReform(
        key="allegements", label="Allègements généraux : plafond porté à 2 SMIC",
        family="allègements", chain="household", knob="allegement_general_plafond",
        value=2.0, note="le cas de la fiche allegement_2smic (+17,92 md€ mécaniques)"),
    ReferenceReform(
        key="prestations", label="RSA : montant de base porté à 700 €",
        family="prestations", chain="household", knob="rsa_montant_de_base", value=700.0,
        note="le cas de la fiche rsa_700 (+3,78 md€ mécaniques)"),
    ReferenceReform(
        key="niches", label="Plafond du quotient familial porté à 1 000 €",
        family="niches", chain="household", knob="plafond_qf_demi_part", value=1000.0,
        note="valeur de référence de tests/knob_cases.py"),
    ReferenceReform(
        key="is", label="IS : taux normal porté à 30 %", family="IS", chain="firm",
        knob="is_taux_normal", value=0.30),
    ReferenceReform(
        key="cvae", label="CVAE : taux maximal porté à 0,5 %", family="CVAE",
        chain="firm", knob="cvae_taux_max", value=0.005,
        note="0,0028 est la valeur EN VIGUEUR : ce cas-là ne bougeait rien et sa "
             "variance de placement valait zéro pour cette seule raison"),
    ReferenceReform(
        key="ifi", label="IFI : seuil d'assujettissement porté à 2 M€",
        family="IFI", chain="patrimoine", knob="seuil_ifi", value=2_000_000.0,
        note="il FAUT une réforme qui coupe une tranche : à barème inchangé "
             "l'encadrement de placement est un POINT, et le module le vérifie "
             "lui-même (« the baseline band is a point, not an interval »)"),
    ReferenceReform(
        key="trajectoire", label="Gel du barème, trajectoire 2026-2029",
        family="trajectoire", chain="trajectory", knob="gel_bareme", value=0.0,
        note="scenarios/gel_bareme.json, référence « indexe »"),
)


#: A reference reform whose central figure is this close to zero is not a reform. Sized on
#: `scenarios.NEUTRAL_TOLERANCE_EUR`, which is itself sized on the subsample's sampling
#: noise — below it, nothing can be told from nothing.
MOVES_EPSILON_EUR = 50e6


def structural_noop(case: ReferenceReform) -> bool:
    """Vrai SEULEMENT quand la réforme ne change rien de façon prouvable — sans donnée.

    `central_for` chargeait les cellules entreprises avant de pouvoir constater qu'une
    réforme qui remet un paramètre à sa valeur en vigueur ne bouge rien. Ce constat ne
    demande pas d'échantillon : `make_reform` écrit la valeur dans l'arbre à partir du
    1er janvier ; si elle est ÉGALE à la valeur en vigueur sur toute l'année chiffrée,
    l'arbre réformé EST l'arbre de base, et le chiffrage vaut zéro par construction.

    Volontairement étroit, parce qu'un faux refus serait pire qu'un chargement inutile :

    * chaîne entreprises seulement, et levier SCALAIRE seulement — un levier apparié (la
      CEBGE) dérive sa bande de lissage et n'est pas décidé ici ;
    * égalité EXACTE, pas une tolérance — dans le doute, on mesure ;
    * aux DEUX bornes de l'année — un paramètre qui change en cours d'année n'est pas
      « en vigueur » au sens où la réforme le laisserait intact.

    Tout ce qui n'est pas prouvé nul ici retombe sur la MESURE, et le seuil
    `MOVES_EPSILON_EUR` continue de refuser ce qui, mesuré, ne bouge pas.
    """
    if case.chain != "firm":
        return False
    from impots.entreprises.reforms import SCALAR_KNOBS

    if case.knob not in SCALAR_KNOBS:
        return False
    from impots.entreprises.system import baseline
    from impots.parameters import resolve

    parameter = resolve(baseline().parameters, SCALAR_KNOBS[case.knob])
    for instant in (f"{FIRM_YEAR}-01-01", f"{FIRM_YEAR}-12-31"):
        in_force = parameter(instant)
        if in_force is None or float(in_force) != float(case.value):
            return False
    return True


def central_for(case: ReferenceReform) -> float:
    """The case's central figure — and a refusal if the case does not move.

    **A reference reform that is a no-op makes every variance share on it a statement about
    nothing.** It happened twice while A0 was being built, both times silently:

    * `cvae_taux_max = 0,0028` is the value IN FORCE. The case priced at -0,0000 md€ and
      its placement variance came out at exactly zero — which the report would have
      rendered as «placement contributes 0,0 % to CVAE», a sentence about CVAE that was
      really a sentence about a reform that did nothing.
    * The IFI case first used an UNCHANGED barème, where `placement.band` returns a point
      by construction — the patrimoine tests assert that zero width themselves, as their
      own anti-theatre check.

    Both are the project's standing rule arriving in a new place: a comparison is untested
    until both sides are non-zero. So the check lives here, once, rather than being
    remembered per case.
    """
    if structural_noop(case):
        raise ValueError(
            f"{case.key} : {case.knob} = {case.value} est la valeur EN VIGUEUR en "
            f"{FIRM_YEAR} — la réforme n'écrit aucun paramètre qui diffère du barème, donc "
            f"son chiffrage vaut zéro par construction. Ce n'est pas une réforme, et toute "
            f"part de variance calculée dessus parlerait du néant plutôt que de la famille "
            f"{case.family}. Refusé sans tirer d'échantillon : l'arbre de paramètres suffit "
            f"à le prouver.")
    if case.chain == "firm":
        value = firm_placement_sampler(case.knob, case.value)(20260101)
    elif case.chain == "patrimoine":
        swing = ifi_cell_bound_swing()
        value = (swing("concentre") + swing("extremal")) / 2
    else:
        return 0.0  # priced by the caller; household/trajectory chains cost engine passes

    if abs(value) < MOVES_EPSILON_EUR:
        raise ValueError(
            f"{case.key} : la réforme de référence chiffre {value:+,.0f} EUR, sous le "
            f"seuil de {MOVES_EPSILON_EUR:+,.0f}. Ce n'est pas une réforme, et toute part "
            f"de variance calculée dessus parlerait du néant plutôt que de la famille "
            f"{case.family}.")
    return value


def reform(key: str) -> ReferenceReform:
    for case in REFERENCE_REFORMS:
        if case.key == key:
            return case
    raise KeyError(key)


# --------------------------------------------------------------------- firm placement

def firm_placement_sampler(knob: str, value: float) -> Any:
    """A sampler over WHERE firms sit inside their published cells.

    This is a genuine samplable measure and the only one on the firm side. Re-seeding
    re-places every firm while the weight identity reproduces headcount, turnover and value
    added to under 1e-9 — so a seed sweep isolates within-cell placement with nothing else
    moving. It is NOT a Sobol decomposition over a declared parameter law, and the report
    says so.

    **It had never been run at a second seed.** One seed, 20260101, had produced every firm
    figure this project has published. A0 draws it properly for the first time.
    """
    from impots.entreprises import aggregate as aggregate_module
    from impots.entreprises import runner as runner_module
    from impots.entreprises.build import load_cells
    from impots.entreprises.population import build_firms
    from impots.entreprises.reforms import FirmReformSpec

    # Le levier est validé TOUT DE SUITE — c'est gratuit et sans donnée, et un levier
    # inconnu doit tomber à la déclaration. Les cellules, elles, ne sont chargées qu'au
    # premier tirage : `sources_for` DÉCLARE les sources d'un cas, et déclarer une source
    # ne doit pas exiger les données qu'il faut pour la TIRER. C'est ce couplage qui
    # faisait échouer `test_every_unmeasured_source_names_why`, un test de métadonnées.
    spec = FirmReformSpec.model_validate({knob: value})
    loaded: list[tuple[Any, float]] = []

    def sample(seed: int) -> float:
        if not loaded:
            if not FIRM_CELLS.exists():
                raise FileNotFoundError(
                    f"{FIRM_CELLS} not found — aucune donnée ne l'accompagne : il se "
                    f"CONSTRUIT par `impots entreprises cells` depuis Ésane × Focus 372 × "
                    f"DGFiP n° 39. `impots data prepare --profile tests` fait les deux.")
            cells, ratio, _vintage = load_cells(FIRM_CELLS)
            loaded.append((cells, ratio))
        cells, ratio = loaded[0]
        firms, _stats = build_firms(cells, fiscal_to_accounting=ratio, seed=seed)
        result = runner_module.run(firms, year=FIRM_YEAR, reform=spec)
        cost = aggregate_module.aggregate(result.firms).reform_cost
        if cost is None:
            raise RuntimeError(f"{knob}: aucun coût de réforme rendu")
        return float(cost)

    return sample


# ----------------------------------------------------------------- household subsample

def household_subsample_sampler(knob: str, value: float, *, households: int,
                                year: int = 2024) -> Any:
    """A sampler over WHICH households the subsample drew.

    Reported as the instrument's RESOLUTION, never in the ranking: `run(sample=None)` prices
    the whole frame, so this variance is exactly zero in production. D-074 already measured
    the same quantity from the other end — 1,49 point of standard deviation per draw on the
    IR barème line at n = 50 000.
    """
    import polars as pl

    from impots import scenarios
    from impots.population.build import PROCESSED

    frame = pl.read_parquet(PROCESSED / "population_2024.parquet")

    def sample(seed: int) -> float:
        from impots.population import runner as runner_module
        drawn = runner_module.subsample(frame, households, seed=seed)
        price = scenarios.knob_pricer(knob, year=year, frame=drawn)
        return float(price(value))

    return sample


# ------------------------------------------------------------------- patrimoine bounds

def ifi_cell_bound_swing() -> Any:
    """The interval of IFI yield the published tranches permit — a BOUND, not a law.

    `reform_band` prices the reformed and the baseline scale under the SAME placement, so
    the width is a placement uncertainty and not a policy difference smuggled in.

    THE CASE HAD TO BE A REFORM THAT CUTS A TRANCHE. At an unchanged barème the bracket is
    a POINT — `placement.band` returns low == high, and the patrimoine tests assert exactly
    that as their anti-theatre check. A0's first draft used the unchanged barème and would
    have measured a rigorous zero, then reported «placement does not matter» about a case
    constructed so that it could not.

    Moving the seuil to 2 M€ puts a kink inside the first tranche: at the point placement
    every foyer sits at 1,7052 M€ and nobody pays; at the mean-preserving spread some sit
    above 2 M€ and do. The published cells cannot distinguish these two worlds, and that
    inability IS the uncertainty.
    """
    from impots.patrimoine import bareme as bareme_module
    from impots.patrimoine import placement as placement_module
    from impots.patrimoine.cells import cells

    baseline = bareme_module.scale_at(2024)
    # The seuil d'assujettissement is the 1,3 M€ row, not the 800 k€ one from which the
    # tax is COMPUTED. Raising it to 2 M€ therefore drops the 800 k€ entry and starts the
    # scale at 2 M€ — which is the scale the patrimoine tests use for exactly this case.
    #
    # A first draft rewrote the 800 k€ threshold to 2 M€ and left 1,3 M€ behind it, giving
    # a scale whose thresholds were out of order. It still returned a number.
    reformed = [(2_000_000.0, 0.007), (2_570_000.0, 0.01),
                (5_000_000.0, 0.0125), (10_000_000.0, 0.015)]
    if [t for t, _r in reformed] != sorted(t for t, _r in reformed):
        raise ValueError("barème réformé non monotone")
    # Même règle que pour l'échantillonneur entreprises : le barème réformé est vérifié
    # tout de suite (sans donnée), les tranches publiées ne sont lues qu'au premier appel.
    bands: list[Any] = []

    def swing(endpoint: str) -> float:
        if not bands:
            bands.append(placement_module.reform_band(cells(), baseline, reformed))
        band = bands[0]
        return band.low_eur if endpoint == "concentre" else band.high_eur

    return swing


def sources_for(case: ReferenceReform, *, households: int) -> list[Source]:
    """The declared sources for one case, each with the method this repository supports.

    An UNMEASURED row carries the reason and no score. That is the point: a source dropped
    from a budget reads as a source that does not matter, and three of the spec's declared
    sources genuinely have neither a law nor bounds today.
    """
    common = [
        Source(key="population_construction",
               label="construction de la population (graines skeleton/incomes)",
               method="unmeasured",
               unmeasured_reason=(
                   "les graines de construction (20240101) ne sont tirées qu'une fois et "
                   "la France synthétique n'est jamais reconstruite ; mesurer cette "
                   "source demande une reconstruction complète à une seconde graine, "
                   "c'est un gate en soi. Le sous-échantillon N'EST PAS un substitut : "
                   "sa variance est nulle en production.")),
    ]

    if case.chain == "firm":
        return [
            Source(key="placement", label="placement intra-cellule des entreprises",
                   method="sampled", sample=firm_placement_sampler(case.knob, case.value),
                   note="mesure tirable, jamais tirée à une seconde graine avant A0"),
            Source(key="cell_bound", label="encadrement de cellule (entreprises)",
                   method="unmeasured",
                   unmeasured_reason=(
                       "rien dans src/impots/entreprises/ ne calcule de bas/haut : "
                       "FirmAggregates n'a pas de champ d'intervalle. L'incertitude de "
                       "cellule y est portée par le placement, pas par une borne.")),
            *common,
        ]

    if case.chain == "household":
        return [
            Source(key="behavioural", label="store comportemental (lois tirables)",
                   method="unmeasured",
                   unmeasured_reason=(
                       "attribuer la variance par paramètre demande de rejouer "
                       "band.compute sur les tableaux d'une passe plein tarif ; le coût "
                       "est une passe moteur par cas, pas par tirage. Prévu en A0 v2. "
                       "Mesuré au gate : le store porte 10 lignes dont 2 dégénérées, et "
                       "in_revenue_band n'apparaît que deux fois — trois lignes seulement "
                       "peuvent déplacer un euro.")),
            *common,
        ]

    if case.chain == "patrimoine":
        return [
            Source(key="cell_bound", label="placement intra-tranche (IFI)", method="swing",
                   swing=ifi_cell_bound_swing(), endpoints=("concentre", "extremal"),
                   note="l'ensemble exact des réponses que les tranches publiées "
                        "autorisent ; aucune densité dessus"),
            Source(key="composition", label="facteur de composition (ISF)",
                   method="unmeasured",
                   unmeasured_reason=(
                       "CompositionFactor est plat et sourcé sur un seul fractile (D-085) ; "
                       "le module écrit lui-même « rien ici n'est un intervalle de "
                       "confiance ». Il ne s'applique qu'au chiffrage ISF, pas à ce cas.")),
            *common,
        ]

    return [
        Source(key="uprating", label="hypothèse d'uprating", method="unmeasured",
               unmeasured_reason=(
                   "la paire vieillie/gelée N'EST PAS un intervalle d'uprating : sa borne "
                   "basse chiffre une population dont les revenus n'ont pas bougé. Un vrai "
                   "balayage demande deux hypothèses SOURCÉES autour de l'hypothèse "
                   "déclarée, et ce projet ne prévoit ni salaires ni prix — les bornes sont "
                   "à l'appelant de les sourcer.")),
        *common,
    ]
