"""B2 — composition and leakage from the input-output table (PHASE4_SPEC §1).

**This module returns shares and fractions. It never returns a level.** That is the
whole design, and the reason is the anti-double-counting rule §1 opens with: the
literature's fiscal multipliers already contain input-output propagation and induced
effects. Running an impulse through a Leontief inverse *and* multiplying the result by
a literature multiplier counts the same propagation twice.

So the two mechanisms have disjoint jobs, and the split runs exactly along
shape-versus-size:

* the **multiplier** decides how big the macro response is;
* the **table** decides which branches it lands in, and how much of it leaks abroad
  before it can land anywhere.

Every public function here therefore returns something dimensionless. A function that
returned euros of output would be an invitation to add it to the aggregate path, and
`first_round_shares` sums to one by construction rather than by convention.

**Type I, and the assertion the spec asked for.** The coefficient matrix is the
branch × branch block alone: households stay exogenous, so the inverse propagates
inter-industry demand and nothing else. Closing the model on household income — the
Type II inverse — would add the induced consumption round, which is precisely the round
the literature multiplier already contains. `assert_type_one` states it, and
`test_type_two_would_double_count` measures how much it would have added.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from impots.macro.tes import Tes

#: Below this, an impulse is numerically indistinguishable from no impulse and its
#: composition is meaningless rather than merely uncertain.
MINIMUM_IMPULSE_EUR = 1.0


class IoLayerError(RuntimeError):
    """The input-output layer was asked for something it must not provide."""


@dataclass(frozen=True)
class Composition:
    """The shape of a first-round shock. Dimensionless throughout."""

    branches: tuple[str, ...]
    output_shares: np.ndarray
    """Share of first-round domestic output by branch. Sums to 1."""
    employment_shares: np.ndarray
    """Share of the first-round employment content by branch. Sums to 1."""
    persons_per_million_eur: float
    """Employment intensity of *this* impulse's mix, in persons per million euros of
    domestic output. A property of the composition, not a forecast: multiplied by a
    level it would produce jobs, which is B3's business, not B2's.

    Persons, not thousands. The accounts publish thousands and the arithmetic runs in
    them, but a coefficient near 0.005 invites a factor-of-a-thousand error at every
    later use, so the unit is converted once, here, where it can be tested."""
    leakage: float
    """Imports induced per euro of impulse, in [0, 1). Both channels: product bought
    directly from abroad to meet the final demand, and the imported input content of
    the domestic production the rest of it sets off. The correction §1 requires to be
    computed rather than assumed."""
    direct_leakage: float
    """The first channel alone, kept separate because it is the one a reader can check
    against the published import table."""
    vintage: str
    base_year: int

    def __post_init__(self) -> None:
        for name in ("output_shares", "employment_shares"):
            shares = getattr(self, name)
            if not np.isclose(shares.sum(), 1.0, atol=1e-9):
                raise IoLayerError(f"{name} sums to {shares.sum()}, not 1")
        if not 0.0 <= self.leakage < 1.0:
            raise IoLayerError(f"leakage {self.leakage} is not a fraction")

    @property
    def domestic_share(self) -> float:
        """What survives leakage — the factor B3 applies to the aggregate impulse."""
        return 1.0 - self.leakage


def technical_coefficients(tes: Tes) -> np.ndarray:
    """A, the domestic input-output coefficient matrix.

    Branch × branch only. The published table carries one negative cell (the SIFIM
    adjustment, D-048), which is kept: clamping it would break a balance identity that
    closes exactly, and the properties propagation needs survive it.
    """
    output = tes.total_output
    if (output <= 0).any():
        zero = [tes.branches[i] for i, v in enumerate(output) if v <= 0]
        raise IoLayerError(f"branches with non-positive output cannot be inverted: {zero}")
    return tes.domestic / output


def leontief_inverse(coefficients: np.ndarray) -> np.ndarray:
    """(I - A)^-1, the Type I inverse.

    Type I because households are exogenous: the branch × branch block propagates
    inter-industry demand and stops. The induced consumption round belongs to the
    literature multiplier and adding it here would count it twice.
    """
    radius = float(np.max(np.abs(np.linalg.eigvals(coefficients))))
    if radius >= 1.0:
        raise IoLayerError(
            f"spectral radius {radius:.4f} >= 1: a unit of demand would generate "
            f"unbounded output, and the inverse does not converge"
        )
    return np.linalg.inv(np.eye(len(coefficients)) - coefficients)


def assert_type_one(coefficients: np.ndarray, tes: Tes) -> None:
    """The coefficient matrix must be the branch block and nothing more.

    §1's sentence — "the induced round belongs to the multiplier and must not be added
    here" — as a check rather than a comment. A Type II matrix is square in n+1, with a
    household row and column closing income onto consumption; this refuses one.
    """
    if coefficients.shape != (tes.n, tes.n):
        raise IoLayerError(
            f"coefficients are {coefficients.shape}, not ({tes.n}, {tes.n}). A closed "
            f"(Type II) matrix adds the induced consumption round, which the literature "
            f"multiplier already contains — that is double counting, not more realism."
        )


def import_share_of_final_use(tes: Tes, use: str) -> np.ndarray:
    """Share of each product's final demand met by imports rather than domestic output.

    This is the direct channel, and reading only the domestic sheet makes it invisible:
    9.1 % of final consumption and 14.8 % of fixed capital formation are imported
    product, bought as such. An impulse routed entirely through the domestic Leontief
    would credit French branches with output that is in fact bought abroad.
    """
    if use not in tes.final_uses or use not in tes.imported_final_uses:
        raise IoLayerError(f"unknown final-use category {use!r}; have {sorted(tes.final_uses)}")
    domestic, imported = tes.final_uses[use], tes.imported_final_uses[use]
    total = domestic + imported
    # A product with no final use of this kind gets no split rather than a divide by
    # zero; nothing is allocated to it anyway.
    return np.where(total > 0, imported / np.where(total > 0, total, 1.0), 0.0).clip(0.0, 1.0)


def split_demand(tes: Tes, demand: np.ndarray, use: str) -> tuple[np.ndarray, np.ndarray]:
    """(demand met domestically, demand met directly by imports)."""
    share = import_share_of_final_use(tes, use)
    direct = demand * share
    return demand - direct, direct


def leakage(tes: Tes, demand: np.ndarray,
            use: str = "total_emplois_finals") -> tuple[float, float]:
    """(total leakage, direct leakage) per euro of impulse.

    Total is imports induced per euro of impulse — the fraction that never reaches a
    French producer, through either channel. The denominator is the impulse itself, not
    gross output: gross output double-counts inter-industry sales and would make the
    ratio depend on how vertically integrated the affected branches happen to be.
    """
    total_impulse = float(demand.sum())
    if total_impulse <= 0:
        raise IoLayerError("an impulse of zero or less has no import content")
    domestic_demand, direct = split_demand(tes, demand, use)
    output = first_round_output(tes, domestic_demand)
    input_coefficients = tes.imported.sum(axis=0) / tes.total_output
    indirect = float((input_coefficients * output).sum())
    return (float(direct.sum()) + indirect) / total_impulse, float(direct.sum()) / total_impulse


def first_round_output(tes: Tes, demand: np.ndarray) -> np.ndarray:
    """Domestic output by branch generated by a final-demand vector, Type I.

    Internal: the level it returns is in the units of `demand`, and letting it out of
    the module is how the aggregate path would come to be counted twice. Public callers
    get `composition`, which normalises it.
    """
    if demand.shape != (tes.n,):
        raise IoLayerError(f"demand is {demand.shape}, expected ({tes.n},)")
    if (demand < 0).any():
        raise IoLayerError(
            "a negative final-demand component makes the composition shares meaningless; "
            "split a mixed impulse into its expansionary and contractionary parts and "
            "compose each"
        )
    coefficients = technical_coefficients(tes)
    assert_type_one(coefficients, tes)
    return leontief_inverse(coefficients) @ demand


def composition(tes: Tes, demand: np.ndarray, jobs: np.ndarray,
                use: str = "total_emplois_finals") -> Composition:
    """The shape of a first-round shock: where it lands, and what leaks.

    `demand` is TOTAL final demand by product — domestic and imported together, as a
    reform's spending impulse arrives — in any consistent unit; the result is
    dimensionless, so the unit cancels and is deliberately not recorded. `use` names
    which published category supplies the domestic/import split, since consumption and
    capital formation do not import in the same proportion. `jobs` is employment by
    branch in thousands, ordered to match, from the same accounts vintage.
    """
    if demand.shape != (tes.n,):
        raise IoLayerError(f"demand is {demand.shape}, expected ({tes.n},)")
    total = float(demand.sum())
    if total < MINIMUM_IMPULSE_EUR:
        raise IoLayerError(
            f"impulse of {total} is below {MINIMUM_IMPULSE_EUR}: its composition would "
            f"be numerical noise, not a small effect"
        )
    if jobs.shape != (tes.n,):
        raise IoLayerError(f"employment is {jobs.shape}, expected ({tes.n},)")

    domestic_demand, _ = split_demand(tes, demand, use)
    output = first_round_output(tes, domestic_demand)
    intensity = jobs / tes.total_output          # thousands of persons per M EUR
    employment = output * intensity
    total_leakage, direct = leakage(tes, demand, use)
    return Composition(
        branches=tes.branches,
        output_shares=output / output.sum(),
        employment_shares=employment / employment.sum(),
        persons_per_million_eur=float(employment.sum() / output.sum()) * 1_000.0,
        leakage=total_leakage,
        direct_leakage=direct,
        vintage=tes.vintage,
        base_year=tes.base_year,
    )
