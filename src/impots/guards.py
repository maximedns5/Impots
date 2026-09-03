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

from collections.abc import Iterable, Sequence

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


# --------------------------------------------------------------------------- #
# Double-entry: every euro a reform moves has to land somewhere (D-045)
# --------------------------------------------------------------------------- #
#: Household-side instruments the state RECEIVES. Positive delta = the state collects
#: more. Signs are normalised upstream in `engine.outputs`, so these are all the same
#: way round here.
STATE_RECEIPTS = (
    "ir", "csg_imposable", "csg_deductible", "crds", "cotisations_salariales",
)

#: Household-side instruments the state PAYS. Positive delta = the state pays more.
#: `aefa` — the prime de Noël — joined this list when the prestations knobs arrived.
#: It is not a benefit anyone reforms directly, but it rides on RSA ELIGIBILITY, so any
#: reform that moves the RSA threshold moves it too. Leaving it out made a national RSA
#: reform miss by 0.99 %, which is what the guard is for.
#: The CRDS entries are NEGATIVE as openfisca stores them, and they belong here rather
#: than among the receipts: a household's benefit is `gross + crds`, `revenu_disponible`
#: uses the net figure, and the population reports the gross one. Netting them here
#: makes the reconstitution the state's actual burden. Without them a national AF
#: reform missed by 0.50 % — five times the tolerance, and exactly 0.5 % of the AF
#: moved, which is the CRDS rate.
STATE_TRANSFERS = ("af", "ppa", "rsa", "aide_logement", "aefa",
                   "crds_pfam", "crds_logement", "crds_mini")

#: The identity is checked in absolute euros against a floor, and relatively above it.
#: A reform moving a few million is not worth a relative test; one moving billions is.
BALANCE_FLOOR_EUR = 5.0e6

#: How much of a reform's effect may run through instruments the runner does not
#: report before the identity refuses.
#:
#: It is not zero, and the reason is worth stating. `revenu_disponible` is computed by
#: OpenFisca over the whole benefits cascade, which is wider than the handful of
#: instruments this runner reports: a CSG rise pulls a little through the complément
#: familial, the ARS and the minima that have no row of their own. Measured, that
#: leakage is 0.066 % of a 10.4 bn CSG reform. The floor sits at 0.1 %, an order of
#: magnitude below the failure this guard exists for — the 17.7 bn labour-cost reform
#: whose public cost read zero, which breaches it by 100 %.
BALANCE_RTOL = 1e-3


#: The niche outputs a reform can move. If a reform touches a niche knob and these are
#: zero across the population, the reform's cost is zero because the DATA is missing,
#: not because the instrument does nothing.
NICHE_TOTALS = ("reductions", "credits_impot")


def niche_blind_spot(
    knobs: Iterable[str], totals: dict[str, float], niche_knobs: Iterable[str],
) -> tuple[str, ...]:
    """Niche knobs this reform moves that the population cannot answer for.

    The most dangerous output this project could produce is a confident zero. A reader
    who cuts the home-help credit from 50 % to 30 % and is told the reform costs
    0 EUR will conclude the credit is worthless; the truth is that the synthetic
    population declares no home-help spending at all, so there is nothing for the rate
    to apply to. The 19.53 bn of réductions and crédits nationally is money this
    population has no way to express.

    Returns the offending knobs, empty when there is nothing to warn about — either
    because the reform touches no niche, or because the population has bases.
    """
    touched = tuple(sorted(set(knobs) & set(niche_knobs)))
    if not touched:
        return ()
    declared = sum(abs(totals.get(name, 0.0)) for name in NICHE_TOTALS)
    return () if declared > 0.0 else touched


class SectorBalanceError(RuntimeError):
    """A reform's reported cost does not match what the instruments say moved."""


def sector_balance(
    deltas: dict[str, float],
    *,
    reform_cost: float,
    employer_contribution_delta: float = 0.0,
    rtol: float = BALANCE_RTOL,
    floor: float = BALANCE_FLOOR_EUR,
) -> dict[str, float]:
    """Assert that the reported public cost equals what the instruments say moved.

    **The first version of this guard did not work, and how it failed is the point.**
    It asserted `households + firms + state = 0` with the state's side written in
    terms of the firm's — so removing the firm term moved both sides together and the
    identity balanced at zero. It could not have caught the bug it was written for.
    That is the D-044 shape again, appearing inside the guard meant to enforce it: a
    check is only as good as its independence from the thing it checks.

    The bug was never an accounting *inconsistency*. The accounting was consistent;
    `reform_cost` simply reported one sector out of two. So the thing to check is not
    that the sectors balance — they will, being derived from each other — but that the
    **headline figure agrees with the sum of the instruments**, which is assembled
    here and computed elsewhere.

    A reform that moves 17.7 bn of labour cost and reports a public cost of zero
    breaches this by 100 %.
    """
    receipts = sum(deltas.get(name, 0.0) for name in STATE_RECEIPTS)
    transfers = sum(deltas.get(name, 0.0) for name in STATE_TRANSFERS)
    # What the state collects, across both sides. Employers paying less is a fall in
    # receipts, so the delta enters with its own sign.
    state_gain = receipts - transfers + employer_contribution_delta
    # A cost to the state is the negative of what it gains.
    expected_cost = -state_gain
    unexplained = reform_cost - expected_cost

    scale = max(abs(reform_cost), abs(expected_cost), floor)
    if abs(unexplained) > rtol * scale:
        raise SectorBalanceError(
            f"le coût annoncé ne correspond pas à ce que les instruments ont bougé : "
            f"coût rapporté {reform_cost:+,.0f} EUR contre {expected_cost:+,.0f} EUR "
            f"reconstitué depuis les postes (prélèvements {receipts:+,.0f}, "
            f"transferts {transfers:+,.0f}, cotisations patronales "
            f"{employer_contribution_delta:+,.0f}), soit un écart de "
            f"{unexplained:+,.0f} EUR ({unexplained / scale:+.2%}). Un secteur "
            f"a bougé sans entrer dans le coût, ou l'inverse."
        )
    return {
        "reform_cost": reform_cost,
        "expected_cost": expected_cost,
        "state_gain": state_gain,
        "unexplained": unexplained,
    }


#: The firm instruments whose sum IS the total. `prelevements_entreprise` is computed
#: by an OpenFisca formula; adding these up here is a second, independent route to the
#: same number, so an instrument added to one and not the other breaks the identity.
FIRM_COMPONENTS = (
    "impot_societes", "contribution_sociale_is", "cebge", "cvae", "c3s",
)


def firm_balance(
    deltas: dict[str, float],
    *,
    reform_cost: float,
    rtol: float = BALANCE_RTOL,
    floor: float = BALANCE_FLOOR_EUR,
) -> dict[str, float]:
    """Assert a firm reform's cost equals the sum of the instruments that moved.

    The firm side has no household term, so the double entry is between the total the
    engine computes and the components this guard adds. A new instrument wired into
    `prelevements_entreprise` but not into the reported set — or the reverse — shows up
    here rather than as a quietly wrong headline.
    """
    components = sum(deltas.get(name, 0.0) for name in FIRM_COMPONENTS)
    expected_cost = -components
    unexplained = reform_cost - expected_cost
    scale = max(abs(reform_cost), abs(expected_cost), floor)
    if abs(unexplained) > rtol * scale:
        missing = {
            name: value for name, value in deltas.items()
            if name not in FIRM_COMPONENTS and abs(value) > floor
        }
        raise SectorBalanceError(
            f"le coût annoncé de la réforme entreprises ne correspond pas à la somme "
            f"des instruments : {reform_cost:+,.0f} EUR contre {expected_cost:+,.0f} "
            f"reconstitué, écart {unexplained:+,.0f} EUR "
            f"({unexplained / scale:+.2%}). Postes hors périmètre ayant bougé : "
            f"{sorted(missing) or 'aucun'}."
        )
    return {
        "reform_cost": reform_cost,
        "expected_cost": expected_cost,
        "unexplained": unexplained,
    }
