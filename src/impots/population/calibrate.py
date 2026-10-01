"""Iterative proportional fitting of the population weights (spec §4.3, D-017).

Classic raking, implemented directly: no dependency, ~120 lines of substance.
Weights are scaled repeatedly so that weighted totals match published margins,
until they stop moving or the iteration budget runs out.

## Why this exists, given that EXTRIAN is already calibrated

The obvious objection — INSEE already calibrates `EXTRIAN` on sex and quinquennial
age, so re-raking to those margins is close to an identity — is true and misses
the point. **Raking is joint.** Keeping sex×age in the margin set is not there to
move sex×age; it is there to *constrain* the adjustment made to everything else,
so that fitting household type cannot quietly distort the age structure.

The A' population is +1.5 % on households against −0.0 % on individuals. That pair
is not a clean bill: at fixed persons, 1.5 % too many households means household
size runs about 1.5 % small — a composition skew, mild here, and precisely what a
household-type margin corrects.

D-017 puts this on **Branch C's** critical path rather than A''s. Real income
microdata arrives weighted to its own vintage, two or three years stale, and must be
re-raked to simulation-year margins before anything it produces is comparable. (Branch C
is a plan on the shelf since D-096 — ERFS access is unavailable for the foreseeable
future — but the requirement is a property of any such source, not of ERFS.)

## The one methodological choice worth arguing about

Textbook IPF assumes each unit belongs to exactly one cell per margin. That holds
for a household-type margin — a household has one type. It does **not** hold for a
person-level margin: a household spans several age×sex cells, and its members
share one weight, because the household is the unit the survey sampled and the
unit whose weight we may move.

This module resolves that by **integrated household weighting**: a household's
adjustment for a person-level margin is the mean of its members' cell factors,
weighted by how many members fall in each cell. It is the standard pragmatic
treatment, it converges, and it keeps the household as the weight-bearing unit.
The alternative — letting members of one household carry different weights —
would break every household-level aggregate downstream.

## Bounds

Final weight ratios are clipped to [0.2, 5] of their initial value. Raking with no
bound will happily hand one household a weight of 40 000 to close a margin it
cannot otherwise reach, and that household then dominates every aggregate it
appears in. Clipping trades an exact margin fit for a population that still
behaves like a sample; `RakeDiagnostics` reports what the clipping cost.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import polars as pl

from impots.population.margins import HOUSEHOLDS_BY_TYPE as _HOUSEHOLDS_BY_TYPE

#: Stop when the largest relative weight change in a full pass falls below this.
TOLERANCE = 1e-6
MAX_ITERATIONS = 200

#: Final weight may not fall below 0.2x or rise above 5x its starting value.
WEIGHT_RATIO_BOUNDS = (0.2, 5.0)

#: The worst relative miss a margin may still have when the raking stops.
#:
#: **Convergence is not fit, and the difference is not academic.** `TOLERANCE`
#: above is met when the weights stop moving, which is a property of the
#: iteration; whether any margin was reached is a property of the result, and IPF
#: on two mutually inconsistent margins reaches a fixed point that satisfies
#: neither. Measured on the committed test fixture: converged in 34 iterations at
#: a maximum weight change of 8.1e-07, with the published household-type margin
#: missed by 99.8 % — nothing clipped, no warning, no failure (D-150).
#:
#: 10 % is loose against D-017's measured 0.84 % on the real population, and the
#: reconciliation report's ménage line remains the sharp check. This is the
#: backstop that refuses a fit that is not a fit at all.
MAX_MARGIN_MISS = 0.10

class RakingRefused(RuntimeError):
    """The raking produced something the build will not carry forward."""


Level = Literal["household", "person"]


@dataclass(frozen=True)
class Margin:
    """A published total the weighted population must reproduce.

    `column` names a categorical column of the population frame; `targets` maps
    each of its values to the weighted count that value should reach. Categories
    present in the frame but absent from `targets` are ignored — they are not
    constrained, rather than being constrained to zero.
    """

    name: str
    level: Level
    column: str
    targets: dict[str, float]
    source: str = ""


@dataclass
class RakeDiagnostics:
    converged: bool
    iterations: int
    max_change: float
    """Largest relative weight change in the final pass."""
    clipped_households: int
    """How many households hit the weight-ratio bounds."""
    weight_ratio_range: tuple[float, float]
    effective_sample_size: float
    """Kish's ESS after raking: `(sum w)^2 / sum w^2`, in households.

    The number that says what the reweighting cost in precision. A population that
    hits every margin by concentrating weight on a handful of households has a
    small ESS and is worse than the one it replaced.
    """
    fit_before: dict[str, float] = field(default_factory=dict)
    fit_after: dict[str, float] = field(default_factory=dict)
    """Worst relative miss per margin, before and after."""


def check_rake_result(diagnostics: RakeDiagnostics) -> None:
    """Refuse a raking that did not come to rest, or that came to rest off its margins.

    Two conditions, and until D-150 only the first was checked — under a message
    that described the second. `converged` is a property of the iteration: the
    weights stopped moving. Whether any margin was *reached* is a property of the
    result, and the two come apart precisely when the margin set is inconsistent,
    because IPF then settles at a fixed point that satisfies none of it.

    The committed test fixture is that case in the repository: 400 dwellings raked
    onto an absolute published household count they are three orders of magnitude
    short of, converging in 34 iterations, nothing clipped, the margin missed by
    99.8 %, and accepted.
    """
    if not diagnostics.converged:
        raise RakingRefused(
            f"raking did not converge in {diagnostics.iterations} iterations "
            f"(max change {diagnostics.max_change:.2e}). A population raked to "
            "margins it cannot reach is worse than an unraked one: refusing."
        )
    worst = max(diagnostics.fit_after.values(), default=0.0)
    if worst > MAX_MARGIN_MISS:
        off = {
            name: f"{miss:.1%}"
            for name, miss in diagnostics.fit_after.items()
            if miss > MAX_MARGIN_MISS
        }
        raise RakingRefused(
            f"raking converged in {diagnostics.iterations} iterations and is still "
            f"{worst:.1%} off its margins, against a {MAX_MARGIN_MISS:.0%} bound: "
            f"{off}. Converging is the weights coming to rest; it is not the margins "
            "being met. A population raked to margins it cannot reach is worse than "
            "an unraked one: refusing."
        )


def _household_table(frame: pl.DataFrame, margins: list[Margin]) -> pl.DataFrame:
    """One row per household, carrying its weight and its cell membership counts.

    Household weight is the MEAN of member weights, matching `runner.py`: EXTRIAN
    is an individual weight but the survey weights a whole dwelling together, and
    the mean is what reproduces both the person and household totals.
    """
    aggregations = [pl.col("weight").mean().alias("w0")]
    for margin in margins:
        if margin.level == "household":
            aggregations.append(pl.col(margin.column).first().alias(f"__{margin.name}"))
    table = frame.group_by("household_id").agg(aggregations).sort("household_id")

    # Person-level margins become one count column per cell: how many members of
    # this household fall in that cell.
    for margin in margins:
        if margin.level != "person":
            continue
        counts = (
            frame.group_by(["household_id", margin.column])
            .agg(pl.len().alias("n"))
            .pivot(on=margin.column, index="household_id", values="n")
            .fill_null(0)
            .sort("household_id")
        )
        renamed = {
            column: f"__{margin.name}::{column}"
            for column in counts.columns
            if column != "household_id"
        }
        table = table.join(counts.rename(renamed), on="household_id", how="left").fill_null(0)
    return table


def _apply_margin(
    table: pl.DataFrame, margin: Margin, weights: np.ndarray
) -> tuple[np.ndarray, float]:
    """One IPF pass for a single margin. Returns new weights and the worst miss."""
    worst = 0.0

    if margin.level == "household":
        categories = table[f"__{margin.name}"].to_numpy().astype(str)
        factors = np.ones_like(weights)
        for value, target in margin.targets.items():
            mask = categories == value
            current = float(weights[mask].sum())
            if current <= 0 or target <= 0:
                continue
            factors[mask] = target / current
            worst = max(worst, abs(current / target - 1.0))
        return weights * factors, worst

    # Person-level: a household spans several cells, so its adjustment is the mean
    # of its cells' factors weighted by how many members it has in each.
    numerator = np.zeros_like(weights)
    denominator = np.zeros_like(weights)
    for value, target in margin.targets.items():
        column = f"__{margin.name}::{value}"
        if column not in table.columns:
            continue
        counts = table[column].to_numpy().astype(np.float64)
        current = float((weights * counts).sum())
        if current <= 0 or target <= 0:
            continue
        factor = target / current
        worst = max(worst, abs(current / target - 1.0))
        numerator += counts * factor
        denominator += counts
    adjustment = np.where(denominator > 0, numerator / np.maximum(denominator, 1e-12), 1.0)
    return weights * adjustment, worst


def _fit(table: pl.DataFrame, margins: list[Margin], weights: np.ndarray) -> dict[str, float]:
    """Worst relative miss per margin at the current weights."""
    fit: dict[str, float] = {}
    for margin in margins:
        worst = 0.0
        if margin.level == "household":
            categories = table[f"__{margin.name}"].to_numpy().astype(str)
            for value, target in margin.targets.items():
                current = float(weights[categories == value].sum())
                if target > 0:
                    worst = max(worst, abs(current / target - 1.0))
        else:
            for value, target in margin.targets.items():
                column = f"__{margin.name}::{value}"
                if column not in table.columns or target <= 0:
                    continue
                current = float((weights * table[column].to_numpy()).sum())
                worst = max(worst, abs(current / target - 1.0))
        fit[margin.name] = worst
    return fit


def rake(
    frame: pl.DataFrame,
    margins: list[Margin],
    tolerance: float = TOLERANCE,
    max_iterations: int = MAX_ITERATIONS,
    bounds: tuple[float, float] = WEIGHT_RATIO_BOUNDS,
) -> tuple[pl.DataFrame, RakeDiagnostics]:
    """Rake household weights onto `margins`, returning a new frame and diagnostics.

    Every member of a household keeps a weight in the proportion the survey gave
    them; only the household's overall level moves.
    """
    if not margins:
        raise ValueError("raking needs at least one margin")

    table = _household_table(frame, margins)
    initial = table["w0"].to_numpy().astype(np.float64).copy()
    weights = initial.copy()
    fit_before = _fit(table, margins, weights)

    converged = False
    iterations = 0
    change = float("inf")
    for iterations in range(1, max_iterations + 1):  # noqa: B007
        previous = weights.copy()
        for margin in margins:
            weights, _ = _apply_margin(table, margin, weights)
        # Bound inside the loop, not only at the end: clipping a converged answer
        # would silently undo the last pass and leave margins unmet without saying so.
        weights = np.clip(weights, initial * bounds[0], initial * bounds[1])
        change = float(np.max(np.abs(weights - previous) / np.maximum(previous, 1e-12)))
        if change < tolerance:
            converged = True
            break

    ratios = weights / np.maximum(initial, 1e-12)
    clipped = int(
        ((ratios <= bounds[0] * (1 + 1e-9)) | (ratios >= bounds[1] * (1 - 1e-9))).sum()
    )
    diagnostics = RakeDiagnostics(
        converged=converged,
        iterations=iterations,
        max_change=change,
        clipped_households=clipped,
        weight_ratio_range=(float(ratios.min()), float(ratios.max())),
        effective_sample_size=float(weights.sum() ** 2 / (weights**2).sum()),
        fit_before=fit_before,
        fit_after=_fit(table, margins, weights),
    )

    # Push the household factor back onto every member, preserving within-household
    # weight proportions rather than flattening them.
    factors = pl.DataFrame({
        "household_id": table["household_id"],
        "__factor": weights / np.maximum(initial, 1e-12),
    })
    raked = (
        frame.join(factors, on="household_id", how="left")
        .with_columns((pl.col("weight") * pl.col("__factor").fill_null(1.0)).alias("weight"))
        .drop("__factor")
    )
    return raked, diagnostics


def household_type(frame: pl.DataFrame) -> pl.DataFrame:
    """Derive INSEE's household typology from the entity roles.

    Derived from roles rather than carried from the EEC's `TYPLOG5`, so that the
    same margin works unchanged when the population moves to ERFS, which has no
    such variable. The categories are the census ones: personne seule, couple sans
    enfant, couple avec enfant(s), famille monoparentale, ménage complexe.
    """
    # INSEE's "enfant d'une famille" is anyone living with a parent who has no
    # partner or child of their own — **at any age**. Our `role_menage == "enfant"`
    # is narrower: it stops at rattachement age, because that is what the tax code
    # cares about (D-013). Mapping the difference to "ménage complexe" put 2.6 M
    # households there against a census 1.1 M, by counting every adult child living
    # at home as an unrelated person.
    #
    # So a member who is neither the reference person nor their partner counts as a
    # child of the family when they are younger than the reference person, and as
    # an unrelated person otherwise. Age is the only relationship signal the EEC
    # affords; it puts a 30-year-old living with parents on the right side and a
    # grandparent or a flatmate of similar age on the other.
    reference_age = (
        pl.when(pl.col("role_menage") == "personne_de_reference")
        .then(pl.col("age")).otherwise(None).max().over("household_id")
    )
    frame = frame.with_columns(
        (
            pl.col("role_menage").is_in(["enfant", "autre"])
            & (pl.col("age") < reference_age)
        ).alias("__family_child")
    )
    per_household = frame.group_by("household_id").agg(
        pl.len().alias("size"),
        (pl.col("role_menage") == "conjoint").sum().alias("partners"),
        pl.col("__family_child").sum().alias("children"),
        (
            pl.col("role_menage").is_in(["enfant", "autre"]) & ~pl.col("__family_child")
        ).sum().alias("others"),
    )
    typology = (
        pl.when(pl.col("others") > 0).then(pl.lit("complexe"))
        .when((pl.col("partners") > 0) & (pl.col("children") > 0))
        .then(pl.lit("couple_avec_enfant"))
        .when(pl.col("partners") > 0).then(pl.lit("couple_sans_enfant"))
        .when(pl.col("children") > 0).then(pl.lit("monoparentale"))
        .when(pl.col("size") == 1).then(pl.lit("personne_seule"))
        .otherwise(pl.lit("complexe"))
    )
    return frame.drop("__family_child").join(
        per_household.with_columns(typology.alias("hh_type")).select(["household_id", "hh_type"]),
        on="household_id",
        how="left",
    )


#: Age bands for the drift constraint — the EEC's own `AGE6` groups, which is the
#: grouping `EXTRIAN` was calibrated on and therefore the only one where holding
#: the margin fixed means anything.
AGE_BANDS: tuple[tuple[str, int, int], ...] = (
    ("15_24", 15, 24), ("25_49", 25, 49), ("50_64", 50, 64),
    ("65_89", 65, 89), ("90_plus", 90, 200),
)


def with_cells(frame: pl.DataFrame) -> pl.DataFrame:
    """Add the categorical columns the standard margins are defined on."""
    band = pl.when(pl.col("age") < 15).then(pl.lit("under_15"))
    for name, low, high in AGE_BANDS:
        band = band.when((pl.col("age") >= low) & (pl.col("age") <= high)).then(pl.lit(name))
    return household_type(frame).with_columns(
        pl.concat_str([band.otherwise(pl.lit("unknown")), pl.lit("_"), pl.col("sex")])
        .alias("age_sex")
    )


def standard_margins(frame: pl.DataFrame) -> list[Margin]:
    """The two margin sets D-017 rules on, and no others.

    **Households by type** is the one doing work: it is published, the population
    misses it by up to 41 % on the smallest category, and fitting it corrects the
    household-size skew that the aggregate household count hides.

    **Age band × sex is a drift constraint**, and its targets are the population's
    *own* current totals rather than an external publication. That is not a
    shortcut — it is what a drift constraint means here. `EXTRIAN` is already
    calibrated by INSEE on sex and quinquennial age, so the correct instruction to
    the raking is "do not move these while fitting household type", and the way to
    say that is to target where they already are.

    Restricted to the 15+ population, because that is the scope `EXTRIAN` was
    calibrated over: the synthesised under-15s (D-013) were never in it, and
    pinning an invented margin would constrain the fit towards our own assumption.

    No region margin: the EEC has none (M0_RECON §4.3).
    """
    weight = frame["weight"].to_numpy()
    cells = frame["age_sex"].to_numpy()
    targets = {
        value: float(weight[cells == value].sum())
        for value in np.unique(cells)
        if not str(value).startswith("under_15")
    }
    return [
        Margin(
            name="household_type", level="household", column="hh_type",
            targets=dict(_HOUSEHOLDS_BY_TYPE),
            source="INSEE, recensement 2023 — ménages par type",
        ),
        Margin(
            name="age_sex", level="person", column="age_sex", targets=targets,
            source="drift constraint: the population's own 15+ totals, which INSEE "
                   "already calibrated EXTRIAN onto",
        ),
    ]
