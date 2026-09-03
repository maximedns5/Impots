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


def subsample(frame: pl.DataFrame, households: int, seed: int = SAMPLE_SEED) -> pl.DataFrame:
    """A deterministic subsample of `households` ménages that estimates the same totals.

    Selection is with probability proportional to household weight, which makes the
    design **self-weighting**: under PPS the inclusion probability of household *i*
    is n·w_i/W, so the Horvitz-Thompson weight w_i/π_i collapses to the constant
    W/n. Every selected household therefore carries the same total weight,
    regardless of how heavy it was in the full file.

    Getting this wrong is easy and quiet. Rescaling the *original* weights so they
    sum back to W — the obvious move — over-weights exactly the households PPS
    already over-selected, and inflated every aggregate here by a factor of 2.8
    before it was caught. There is no error and no NaN; the totals are simply
    wrong, which is why the quick tier is checked against a full run in the tests.
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
    probabilities = weights / weights.sum()
    chosen = np.sort(rng.choice(total, size=households, replace=False, p=probabilities))
    keep = household_weights["household_id"].to_numpy()[chosen]

    # Each survivor stands for W/n of population weight, spread across its members
    # in the proportions the survey gave them.
    target = weights.sum() / households
    scale = pl.DataFrame({
        "household_id": keep,
        "_hh_scale": target / weights[chosen],
    })
    return (
        frame.filter(pl.col("household_id").is_in(keep))
        .join(scale, on="household_id", how="inner")
        .with_columns((pl.col("weight") * pl.col("_hh_scale")).alias("weight"))
        .drop("_hh_scale")
    )


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


def run(
    population: pl.DataFrame | Path,
    year: int = 2024,
    reform: ReformSpec | None = None,
    tier: Tier = "light",
    sample: int | None = None,
    impute_niches: bool = False,
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
    """
    frame = pl.read_parquet(population) if isinstance(population, Path) else population
    if sample is not None:
        frame = subsample(frame, sample)
    frame = frame.sort("person_id")

    guards: dict[str, Any] = {}
    timings: dict[str, float] = {}

    started = time.perf_counter()
    built = build_simulation(frame, baseline(), year)
    timings["build_s"] = round(time.perf_counter() - started, 2)

    niche_bases: dict[str, Any] | None = None
    if impute_niches:
        started = time.perf_counter()
        niche_bases = _impute_niches(built, frame, year)
        built = build_simulation(frame, baseline(), year, niche_bases)
        timings["impute_s"] = round(time.perf_counter() - started, 2)

    started = time.perf_counter()
    baseline_rows = _extract(built, frame, tier, guards)
    timings["baseline_s"] = round(time.perf_counter() - started, 2)

    columns: dict[str, np.ndarray] = dict(baseline_rows)
    if reform is not None and not reform.is_empty():
        started = time.perf_counter()
        reformed_built = build_simulation(
            frame, reformed_for(reform, year), year, niche_bases)
        reform_guards: dict[str, Any] = {}
        reform_rows = _extract(reformed_built, frame, tier, reform_guards)
        guards["nbptr_min_reform"] = reform_guards["nbptr_min"]
        timings["reform_s"] = round(time.perf_counter() - started, 2)
        for key, values in reform_rows.items():
            columns[f"{key}_reform"] = values

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
    )
