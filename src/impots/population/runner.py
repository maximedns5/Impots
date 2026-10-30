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

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import polars as pl

from impots.engine import outputs
from impots.engine.system import baseline, reformed_for
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

    for row in outputs.rows_for(tier):
        array = built.calculate(row.variable, add=row.period == "month")
        if row.entity == "menage":
            values = array.astype(np.float64)
        else:
            values = _to_households(
                array.astype(np.float64), index_for[row.entity], n_households
            )
        results[row.key] = -values if row.negate else values
    return results


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
    """
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

    guards: dict[str, Any] = {}
    timings: dict[str, float] = {}

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
        reformed_built = build_simulation(
            frame, reformed_for(reform, year), year, niche_bases,
            capital_bases=capital_bases)
        reform_guards: dict[str, Any] = {}
        reform_rows = _extract(reformed_built, frame, tier, reform_guards)
        guards["nbptr_min_reform"] = reform_guards["nbptr_min"]
        timings["reform_s"] = round(time.perf_counter() - started, 2)
        for key, values in reform_rows.items():
            columns[f"{key}_reform"] = values
        persons = persons.with_columns(pl.Series(
            "salaire_super_brut_reform",
            reformed_built.calculate("salaire_super_brut", add=True).astype(np.float64)))

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

    guards["nan_columns"] = [
        key for key in columns if not np.isfinite(columns[key]).all()
    ]
    if guards["nan_columns"]:
        raise WiringError(f"non-finite values in {guards['nan_columns']}")

    return RunResult(
        households=households,
        year=year,
        tier=tier,
        n_households=built.household_ids.size,
        n_persons=built.n_persons,
        sampled=sample,
        timings=timings,
        guards=guards,
        persons=persons,
    )
