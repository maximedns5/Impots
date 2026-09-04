"""Cell-bound uncertainty: what a reform costs when we refuse to invent a density.

A published tranche says how many foyers it holds and what they pay on average. It does
not say where inside the tranche they sit. For most questions that does not matter; for
some it decides the answer; and the difference between those two cases is exactly what
this module computes.

WHEN IT MATTERS, AND WHY IT USUALLY DOES NOT. Tax is piecewise linear in the base, so on
any interval containing no barème kink it is AFFINE, and an affine function satisfies
E[f(W)] = f(E[W]) exactly — the mean is sufficient and placement is irrelevant. Measured:
the four published tranches are 1,3-2,57 / 2,57-5 / 5-10 / 10-∞ and the barème's
thresholds are 0,8 / 1,3 / 2,57 / 5 / 10, so **no published tranche contains an interior
kink**. The baseline therefore carries NO cell-bound uncertainty at all, and neither does
a reform that only changes rates.

It appears when a reform puts a kink inside a tranche: moving the seuil d'assujettissement
into the first tranche, inserting a new bracket, or setting a floor at 100 M inside the
open top cell. Then the answer depends on the placement, and this module brackets it.

**THE SPEC'S METHOD DOES NOT WORK, AND THE REPLACEMENT IS TIGHTER.** `PHASE5_SPEC` §2
says to bracket with "mass at published mean vs uniform across the tranche". Uniform on
[a, b] has mean (a+b)/2, which is not the published mean — measured, the first tranche's
implied mean is 1,7052 M against a uniform mean of 1,935 M. So the uniform placement
CONTRADICTS the published data it is meant to respect, and it is not an extreme of
anything.

The honest bracket is over the distributions actually consistent with what is published:
support inside [a, b], and the mean the published tax implies. Over that family, for a
convex tax:

  * the MINIMUM is the point mass at the mean — Jensen's inequality;
  * the MAXIMUM is the two-point distribution on the endpoints {a, b} with weights that
    reproduce the mean, whose value is the chord of f from a to b evaluated at the mean.

Both are attainable, so the interval is tight rather than merely valid. Nothing is
invented: the bracket is the set of answers the published numbers permit, and its width
is a fact about the publication rather than a modelling choice.

**THE TOP CELL IS OPEN, AND ITS BRACKET IS INFINITE.** The last tranche runs from 10 M
upward with no published ceiling, so the maximising two-point distribution can put mass
arbitrarily high and the upper bound does not exist. This is not a technicality to be
patched with a default: it is the reason a Zucman-style floor at 100 M cannot be priced
from these cells alone, and why an external anchor is needed for that band. `band()`
refuses the open cell rather than substituting a number, and callers must pass an
explicit, sourced ceiling to get an answer at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from impots.patrimoine.bareme import Scale, tax_on
from impots.patrimoine.cells import IfiCell


class PlacementError(RuntimeError):
    """A bracket was asked for where the published data does not permit one."""


@dataclass(frozen=True)
class Placement:
    """Where a cell's foyers sit inside their tranche, as a discrete distribution.

    `points` are (base, share of the cell's foyers) and the shares sum to one. Both
    placements this module builds reproduce the cell's implied mean base exactly, which
    is what makes them consistent with the publication rather than alternatives to it.
    """

    name: str
    points: tuple[tuple[float, float], ...]

    def mean(self) -> float:
        return sum(base * share for base, share in self.points)

    def tax(self, scale: Scale, foyers: float) -> float:
        return foyers * sum(share * tax_on(base, scale) for base, share in self.points)


def point_mass(cell: IfiCell) -> Placement:
    """Everyone at the cell's implied mean. Minimises tax under a convex scale."""
    return Placement("point", ((cell.implied_mean_base_eur, 1.0),))


def extremal(cell: IfiCell, *, ceiling: float | None = None) -> Placement:
    """The mean-preserving spread onto the tranche's endpoints. Maximises tax.

    `ceiling` supplies the upper endpoint for the open top tranche, and is REQUIRED
    there: without a published ceiling the maximum does not exist, and inventing one
    would be exactly the density this class refuses to invent.
    """
    lower = cell.tranche.lower_eur
    upper = cell.tranche.upper_eur
    if upper == float("inf"):
        if ceiling is None:
            raise PlacementError(
                f"{cell.label} is open at the top, so no maximising placement exists: "
                f"mass can sit arbitrarily high and the upper bound is infinite. Pass a "
                f"sourced `ceiling` to bound it, or price this cell as point-mass only "
                f"and say the band is one-sided. Do not substitute a convenient number."
            )
        upper = ceiling

    mean = cell.implied_mean_base_eur
    if not lower <= mean <= upper:
        raise PlacementError(
            f"{cell.label}: implied mean {mean:,.0f} is outside [{lower:,.0f}, "
            f"{upper:,.0f}], so no distribution on those endpoints has it as its mean"
        )
    if upper == lower:  # pragma: no cover - a degenerate tranche
        return Placement("extremal", ((lower, 1.0),))
    share_low = (upper - mean) / (upper - lower)
    return Placement("extremal", ((lower, share_low), (upper, 1.0 - share_low)))


def band(cell: IfiCell, scale: Scale, *, ceiling: float | None = None) -> tuple[float, float]:
    """The interval of total tax this cell's published numbers permit, in euros.

    Returns (low, high). For a scale with no kink inside the tranche the two coincide,
    which is the module's own check that it is not manufacturing width: the baseline
    band is a point, and only a reform that cuts the tranche opens it.
    """
    low = point_mass(cell).tax(scale, cell.foyers)
    high = extremal(cell, ceiling=ceiling).tax(scale, cell.foyers)
    # Convexity guarantees low <= high; if it does not hold the scale is not convex and
    # the extremal argument does not apply, so say so rather than silently sorting.
    if high < low - 1e-6:
        raise PlacementError(
            f"{cell.label}: the spread placement taxes LESS than the point placement "
            f"({high:,.0f} < {low:,.0f}). The scale is not convex over this tranche, so "
            f"the endpoints are not the extremes and this bracket is not valid."
        )
    return low, high


def has_interior_kink(cell: IfiCell, scale: Scale) -> bool:
    """Does this scale cut the cell? If not, placement cannot matter."""
    return any(cell.tranche.lower_eur < threshold < cell.tranche.upper_eur
               for threshold, _ in scale)


@dataclass(frozen=True)
class ReformBand:
    """A reform's yield, as the interval the published cells permit."""

    low_eur: float
    high_eur: float
    open_cell_excluded: bool
    """True when the top cell was priced point-mass only because it is unbounded."""
    cells_with_interior_kink: tuple[str, ...]

    @property
    def width_eur(self) -> float:
        return self.high_eur - self.low_eur

    @property
    def is_a_point(self) -> bool:
        return self.width_eur < 1.0


def reform_band(cells: list[IfiCell], baseline: Scale, reformed: Scale, *,
                ceiling: float | None = None) -> ReformBand:
    """What a scale change yields, bracketed by placement.

    The yield is (reformed tax − baseline tax), and BOTH are evaluated under the SAME
    placement — otherwise the band would mix a placement difference into what is
    supposed to be a policy difference, and would be wide for the wrong reason.
    """
    low_total = high_total = 0.0
    open_excluded = False
    cut = []
    for cell in cells:
        if has_interior_kink(cell, reformed) or has_interior_kink(cell, baseline):
            cut.append(cell.label)
        placements = [point_mass(cell)]
        try:
            placements.append(extremal(cell, ceiling=ceiling))
        except PlacementError:
            open_excluded = True
        yields = [p.tax(reformed, cell.foyers) - p.tax(baseline, cell.foyers)
                  for p in placements]
        low_total += min(yields)
        high_total += max(yields)
    return ReformBand(low_eur=low_total, high_eur=high_total,
                      open_cell_excluded=open_excluded,
                      cells_with_interior_kink=tuple(cut))
