"""The IFI cell population, and the mechanical check that validates it (Phase 5 M2).

**Every line this module produces is VALIDATION.** Nothing is calibrated, because
there is nothing to calibrate to: DGFiP publishes the population, so the cells are read
rather than fitted, and agreement with the published totals is evidence rather than
arithmetic. That is the module's distinctive property and the reason the phase was
chosen (D-077). The day something here acquires a factor chosen to close a gap, the
design has failed rather than needed help.

HOW A CELL GETS ITS BASE. The published table gives counts and tax per tranche but no
base per tranche (D-078), so each cell's mean base is obtained by INVERTING the scale
on its published mean tax. That inversion cannot see the reliefs — décote, plafonnement
and the dons reduction all lower tax — so every implied base is a LOWER BOUND, and the
reconstructed aggregate necessarily falls short of the published one.

THE SHORTFALL IS QUANTIFIED, NOT TOLERATED, which is what §2 asks. Measured against the
published aggregate base of 466.79 bn:

  total shortfall                       30.18 bn   (-6.46 %)
    dons: 220.7 M declared, 165.5 M of  17.43 bn   ( 58 % of it)
      relief at 75 %, put back and
      re-inverted
    décote: at most 1 250 EUR over the   0.97 bn   (  3 %, an upper bound)
      foyers in the 1,3-1,4 M window
    left for the plafonnement and rest  11.77 bn   ( 39 %)

The plafonnement is the plausible home for most of the remainder — it bites hardest
exactly where wealth is large and income is not — but we do not have the data to
apportion it, and it is left named and unallocated rather than assigned by difference
and called explained.

COMPARATOR VINTAGES, stated because the rule binds every published figure in this
phase and the three are genuinely different years:

  * assessment year of the tranche split — 2024 (n° 33, published April 2025);
  * assessment year of the aggregates — 2024, taken from n° 45 (published April 2026),
    which prints 2024 beside 2025;
  * the year our engine prices — 2024 law, `bareme.scale_at(2024)`.

A budget-line booking year is a fourth and is NOT used here; it belongs to the
reconciliation section, against the manifested budget source rather than against this
docstring.
"""

from __future__ import annotations

from dataclasses import dataclass

from impots.patrimoine import bareme, ifi_cells
from impots.patrimoine.ifi_cells import Aggregate, Tranche

#: The dons reduction rate, read here only to apportion the residual. The engine
#: applies its own; this is arithmetic about a published total, not a second source.
DONS_RELIEF_RATE = 0.75


@dataclass(frozen=True)
class IfiCell:
    """One published tranche, with the base its published tax implies."""

    tranche: Tranche
    implied_mean_base_eur: float
    """LOWER BOUND. Inverting tax cannot see the reliefs, all of which lower tax."""
    year: int

    @property
    def label(self) -> str:
        return self.tranche.label

    @property
    def foyers(self) -> float:
        return self.tranche.foyers

    @property
    def implied_base_eur(self) -> float:
        return self.implied_mean_base_eur * self.tranche.foyers

    @property
    def published_ifi_eur(self) -> float:
        return self.tranche.ifi_eur

    @property
    def inside_its_tranche(self) -> bool:
        """The falsifiable property from D-078. Nothing forces it."""
        return (self.tranche.lower_eur <= self.implied_mean_base_eur
                <= self.tranche.upper_eur)


@dataclass(frozen=True)
class MechanicalCheck:
    """What the cells reproduce, and what they miss. All validation."""

    year: int
    cells: list[IfiCell]
    aggregate: Aggregate
    reconstructed_base_eur: float
    shortfall_eur: float
    dons_explains_eur: float
    decote_explains_at_most_eur: float

    @property
    def shortfall_share(self) -> float:
        return self.shortfall_eur / self.aggregate.base_eur

    @property
    def unexplained_eur(self) -> float:
        return (self.shortfall_eur - self.dons_explains_eur
                - self.decote_explains_at_most_eur)

    @property
    def every_mean_inside_its_tranche(self) -> bool:
        return all(cell.inside_its_tranche for cell in self.cells)

    @property
    def shortfall_has_the_right_sign(self) -> bool:
        """Positive shortfall = the reconstruction is BELOW published, as the reliefs
        require. A negative one would mean the arithmetic overstates tax, which no
        unmodelled relief can explain."""
        return self.shortfall_eur > 0


def cells(year: int = ifi_cells.TRANCHE_YEAR) -> list[IfiCell]:
    """One cell per published tranche, base implied from published tax."""
    scale = bareme.scale_at(year)
    return [
        IfiCell(tranche=tranche, year=year,
                implied_mean_base_eur=bareme.invert(tranche.mean_ifi_eur, scale))
        for tranche in ifi_cells.tranches()
    ]


def mechanical_check(year: int = ifi_cells.TRANCHE_YEAR) -> MechanicalCheck:
    """The zero-calibration check, with its residual apportioned.

    Nothing here is fitted: the per-tranche tax and the aggregate base are separate
    publications, and our scale arithmetic is the only thing connecting them.
    """
    scale = bareme.scale_at(year)
    built = cells(year)
    aggregate = ifi_cells.aggregate(year)

    reconstructed = sum(cell.implied_base_eur for cell in built)
    shortfall = aggregate.base_eur - reconstructed

    # Dons: put the published relief back as tax and re-invert. Apportioned across
    # tranches by each one's share of total IFI, which is the only split published.
    # The 50 000 EUR per-foyer cap is NOT applied, so this is an UPPER bound on the
    # relief and therefore on the base it explains.
    relief = aggregate.dons_eur * DONS_RELIEF_RATE
    dons_base = 0.0
    for cell in built:
        share = cell.published_ifi_eur / aggregate.ifi_eur
        gross_mean = cell.tranche.mean_ifi_eur + relief * share / cell.foyers
        dons_base += (bareme.invert(gross_mean, scale)
                      - cell.implied_mean_base_eur) * cell.foyers

    # Décote: at most 1 250 EUR (its value at the 1,3 M floor), and only for foyers in
    # the 1,3-1,4 M window. Placing them uniformly across the first tranche is the
    # generous extreme — cell-bound reasoning, not an invented density — and halving
    # accounts for the décote falling linearly to zero across the window.
    first = built[0].tranche
    width = first.upper_eur - first.lower_eur
    in_window = first.foyers * min(1.0, (1.4e6 - first.lower_eur) / width)
    decote_tax = in_window * 1_250.0 * 0.5
    decote_base = decote_tax / scale[1][1]  # at the 0,7 % marginal rate

    return MechanicalCheck(
        year=year, cells=built, aggregate=aggregate,
        reconstructed_base_eur=reconstructed, shortfall_eur=shortfall,
        dons_explains_eur=dons_base, decote_explains_at_most_eur=decote_base,
    )
