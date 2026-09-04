"""The IFI scale, read from the engine's tree, plus the inversion the cells need.

Small on purpose. It lives here rather than in `scripts/verify_ifi.py` because both
the gate and the cell population need it, and a test that imports from `scripts/` has
the dependency backwards.

`tax_on` reimplements what `isf_ifi_iai` does — `bareme.calc(assiette)` — against the
same thresholds and rates pulled from the tree. That duplication is deliberate and
tested: `test_our_scale_arithmetic_matches_the_engines` runs both over a ladder of
bases, so the reimplementation cannot drift from the engine it stands in for. The
reason not to call the engine instead is bisection: inverting a tax takes ~200
evaluations, and 200 full simulations per cell is not a thing to do.
"""

from __future__ import annotations

from typing import Any

Scale = list[tuple[float, float]]
"""(threshold, marginal rate), ascending. No leading zero bracket: liability below the
first threshold is the ABSENCE of a bracket, not a zero one."""

IFI_NODE = "impot_fortune_immobiliere_ifi_partir_2018"


def scale_at(year: int, system: Any | None = None) -> Scale:
    """The IFI barème in force at 1 January of `year`."""
    if system is None:
        from openfisca_france import FranceTaxBenefitSystem

        system = FranceTaxBenefitSystem()
    node = getattr(
        system.get_parameters_at_instant(f"{year}-01-01").taxation_capital, IFI_NODE
    ).bareme
    return list(zip(node.thresholds, node.rates, strict=True))


def tax_on(base: float, scale: Scale) -> float:
    """Marginal-rate tax on `base`, before décote, plafonnement and réductions."""
    total = 0.0
    for index, (threshold, rate) in enumerate(scale):
        upper = scale[index + 1][0] if index + 1 < len(scale) else float("inf")
        total += max(0.0, min(base, upper) - threshold) * rate
    return total


def invert(tax: float, scale: Scale, *, ceiling: float = 1.0e9) -> float:
    """The base that produces `tax`.

    Bisection rather than algebra: the scale is monotone so bisection is exact enough,
    and it cannot be fooled at a bracket boundary the way a per-bracket algebraic
    inversion can when the tax lands exactly on a kink.
    """
    low, high = 0.0, ceiling
    for _ in range(200):
        mid = (low + high) / 2.0
        if tax_on(mid, scale) < tax:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0
