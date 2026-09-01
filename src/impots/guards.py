"""Assertions that turn silent wrongness into a stack trace.

Every defect in the Phase 0/1 audit's table that mattered had the same shape:
plausible numbers, no exception, all existing guards green. Two of them were
weighting bugs, and both changed every aggregate in the model by a factor:

* household weight taken as the **sum** of member weights rather than the mean —
  implied a population of 120 M and multiplied every euro total by 2.2;
* a PPS subsample **rescaled on top of** a design that is already self-weighting,
  multiplying every aggregate by 2.8.

Neither raised anything. Neither was caught by a NaN check or a range check,
because the numbers stayed finite and positive. What would have caught both is
the observation that a *reweighting step must not change what the weights add up
to* — so that is what `weight_identity` asserts, and PHASE2_SPEC §3.5 requires it
around every weighting step in the firm module.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import polars as pl


class GuardError(RuntimeError):
    """A guard fired. The number was wrong in a way that would not have raised."""


class WeightIdentityError(GuardError):
    """A weighting step changed a total it had no business changing."""


def weighted_total(frame: pl.DataFrame, column: str, weight: str = "weight") -> float:
    """`sum(column * weight)` — the quantity a reweighting must preserve."""
    return float((frame[column].to_numpy() * frame[weight].to_numpy()).sum())


def weight_identity(
    before: pl.DataFrame,
    after: pl.DataFrame,
    columns: Sequence[str],
    *,
    step: str,
    weight: str = "weight",
    targets: dict[str, float] | None = None,
    rtol: float = 1e-6,
) -> dict[str, float]:
    """Assert a weighting step preserved the totals it should have.

    For each column, the weighted total after the step must equal the total
    before it — or, where the step *is* a calibration, the target it was fitted
    to. Returns the totals after, so a caller can log them.

    `targets` names the columns the step was allowed to move, and to what. A
    column that is neither preserved nor targeted is exactly the case both
    historical defects fell into.
    """
    targets = targets or {}
    after_totals: dict[str, float] = {}
    problems: list[str] = []

    for column in columns:
        was = weighted_total(before, column, weight)
        now = weighted_total(after, column, weight)
        after_totals[column] = now
        expected = targets.get(column, was)
        if expected == 0:
            if abs(now) > rtol:
                problems.append(f"{column}: expected 0, got {now:,.6g}")
            continue
        drift = abs(now / expected - 1.0)
        if drift > rtol:
            kind = "calibration target" if column in targets else "pre-step total"
            problems.append(
                f"{column}: {now:,.6g} against a {kind} of {expected:,.6g} "
                f"({now / expected - 1:+.4%})"
            )

    if problems:
        raise WeightIdentityError(
            f"the weighting step {step!r} moved totals it should not have — this is "
            "the shape of a bug that produces plausible numbers and raises nothing:\n  "
            + "\n  ".join(problems)
        )
    return after_totals


def no_nan(values: np.ndarray, name: str) -> np.ndarray:
    """Refuse non-finite output.

    Zero-income households legitimately make openfisca emit divide-by-zero
    RuntimeWarnings; the results stay finite. A NaN is not noise — it is how a
    broken entity join first announced itself in Phase 1.
    """
    bad = int((~np.isfinite(values)).sum())
    if bad:
        raise GuardError(
            f"{name} produced {bad} non-finite values of {values.size} — a wiring bug, "
            "not an edge case"
        )
    return values


def non_negative(values: np.ndarray, name: str) -> np.ndarray:
    bad = int((values < 0).sum())
    if bad:
        raise GuardError(f"{name} has {bad} negative values of {values.size}")
    return values


def not_greater(
    smaller: np.ndarray, larger: np.ndarray, name: str, tolerance: float = 0.0
) -> int:
    """Count violations of `smaller <= larger` without raising.

    Some relations are near-identities that real data breaks in a few cells —
    value added should not exceed turnover, but published sector aggregates
    occasionally say otherwise. Those are worth counting and reporting, not worth
    aborting a build over. Returns the count so the caller can decide.
    """
    return int((smaller > larger + tolerance).sum())
