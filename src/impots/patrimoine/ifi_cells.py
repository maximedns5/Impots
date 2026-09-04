"""The IFI cell population, read from DGFiP's published tranche statistics.

**This module reads. It does not fit.** The point of the whole phase is that the
baseline is a mechanical check with ZERO calibration: DGFiP publishes the population,
so nothing about it is ours to tune. If anything here ever acquires a scaling factor
chosen to make a comparison come out, the design has failed rather than needed help
(D-077).

WHAT IS PUBLISHED, AND WHAT IS NOT — established at M0 by reading the files rather
than the spec. `PHASE5_SPEC.md` §2 states the tranche table gives "redevable counts,
taxable base, tax due", and says the mechanical check is to apply our barème to the
published base per tranche. **The base per tranche is not published.** What is:

  * per tranche (n° 33, Graphique 3): share of taxable foyers, share of total IFI,
    and mean IFI. Four tranches only — the barème's 0,8-1,3 M bracket never appears,
    because liability starts at 1,3 M;
  * in aggregate (n° 45, Tableau 1): the count of foyers, the TOTAL net taxable
    wealth, the total IFI paid, and the total dons.

So the check is reformulated, and the substitute is not weaker. Invert the barème on
each tranche's mean IFI to get that tranche's implied mean base, then confront the
reconstructed aggregate against the independently published aggregate. Nothing is
fitted: the per-tranche tax and the aggregate base are two separate published
quantities, and our arithmetic is what connects them. See `docs/M0_IFI.md`.

THE UNITS TRAP, again. n° 45's Tableau 1 is headed "(M€)" and its cells are in EUROS
— 4.6679e11 against a header claiming millions. The niches module met the same trap in
the other direction (thousands vs euros between vintages). `_plausible` therefore
refuses a total outside a band rather than trusting either the header or the cell.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"

#: The publication that carries each piece. Two bulletins, because the per-tranche
#: breakdown and the aggregate levels are not published in the same one.
TRANCHE_FILE = "dgfip_stats_33_ifi_2024.xlsx"
AGGREGATE_FILE = "dgfip_stats_45_ifi_2025.xlsx"

#: Assessment year of the tranche breakdown. Stated because the comparator-vintage
#: rule binds every published figure in this phase: n° 33 reports the 2024 assessment,
#: n° 45 reports 2025 and carries 2024 as its comparison column, and the budget line
#: books on yet another basis.
TRANCHE_YEAR = 2024


class IfiCellError(RuntimeError):
    """The published tranche table cannot be read as expected."""


@dataclass(frozen=True)
class Aggregate:
    """The published national totals for one assessment year."""

    year: int
    foyers: float
    """The count as PUBLISHED, which is rounded to the nearest hundred."""
    base_eur: float
    """Total net taxable wealth — 'patrimoine net total'."""
    ifi_eur: float
    dons_eur: float
    published_mean_base_eur: float
    """The publication's own 'Patrimoine moyen', to full precision."""

    @property
    def mean_base_eur(self) -> float:
        return self.base_eur / self.exact_foyers

    @property
    def exact_foyers(self) -> float:
        """The unrounded count, recovered as total base / published mean.

        The bulletin rounds `Effectif` to the nearest hundred — 186 100 — while giving
        the total and the mean to full precision. Their quotient comes out to
        186 094.000, INTEGRAL to three decimals, which is what identifies it as the
        true count rather than a coincidence. Using the rounded figure would put a
        0.0032 % error into every tranche count for no reason, and this module's claim
        is a mechanical check with zero calibration: where the exact number is
        recoverable, it is recovered.
        """
        return self.base_eur / self.published_mean_base_eur


@dataclass(frozen=True)
class Tranche:
    """One published wealth tranche."""

    lower_eur: float
    upper_eur: float
    """+inf for the open top tranche."""
    foyers: float
    ifi_eur: float
    mean_ifi_eur: float

    @property
    def label(self) -> str:
        top = "∞" if self.upper_eur == float("inf") else f"{self.upper_eur / 1e6:g}"
        return f"{self.lower_eur / 1e6:g}–{top} M€"


#: Any IFI total must land in this band, in euros. It exists to turn the header-says-
#: millions-cells-say-euros trap into a loud failure rather than a silent factor of 1e6.
PLAUSIBLE_IFI_EUR = (1.0e9, 5.0e9)
PLAUSIBLE_BASE_EUR = (1.0e11, 1.0e12)


def _sheet(workbook: str, name: str, raw: Path | None = None):
    try:
        import openpyxl
    except ModuleNotFoundError as error:  # pragma: no cover - environment
        raise IfiCellError("openpyxl is required") from error
    path = (raw or RAW) / workbook
    if not path.exists():
        raise IfiCellError(f"{path} not found — download it and manifest it")
    book = openpyxl.load_workbook(path, data_only=True)
    if name not in book.sheetnames:
        raise IfiCellError(
            f"{workbook} has no sheet {name!r}; it has {book.sheetnames}. The "
            f"publication may have been reorganised — do not fall back to a neighbour."
        )
    return book[name]


def _plausible(label: str, value: float, band: tuple[float, float]) -> float:
    low, high = band
    if not low <= value <= high:
        raise IfiCellError(
            f"{label} reads {value:,.0f} EUR, outside the plausible band "
            f"[{low:,.0f}, {high:,.0f}]. n° 45's Tableau 1 is HEADED '(M€)' and its "
            f"cells are in euros; this looks like the wrong convention rather than a "
            f"surprising figure."
        )
    return value


def aggregate(year: int = TRANCHE_YEAR, raw: Path | None = None) -> Aggregate:
    """The published national totals, read from n° 45's Tableau 1.

    That bulletin prints 2024 and 2025 side by side, so both assessment years are
    available from one sheet and the column is chosen by year rather than by position.
    """
    sheet = _sheet(AGGREGATE_FILE, "Tableau_1", raw)
    # The year header is FOUND, not indexed. The sheet carries a title row of its own
    # whose position has already moved once between vintages, and addressing a header
    # by row number is how a reader silently picks up the wrong column.
    column = None
    for r in range(1, min(sheet.max_row, 6) + 1):
        for c in range(1, sheet.max_column + 1):
            value = sheet.cell(r, c).value
            if value is not None and str(value).strip() == str(year):
                column = c
                break
        if column is not None:
            break
    if column is None:
        raise IfiCellError(
            f"n° 45 Tableau_1 has no column headed {year} in its first six rows; they "
            f"read {[[sheet.cell(r, c).value for c in range(1, sheet.max_column + 1)] for r in range(1, 4)]}"
        )

    # Labels are searched across every column LEFT of the year column, not read from
    # column 1: this sheet indents its stub into column 2, and the 2024 vintage does
    # not. Addressing either by number would break on the other.
    wanted = {"Effectif": None, "Patrimoine net total": None, "IFI payé": None,
              "Dons IFI": None, "Patrimoine moyen": None}
    for r in range(1, sheet.max_row + 1):
        heads = [str(sheet.cell(r, c).value or "").strip() for c in range(1, column)]
        for key in wanted:
            if any(head.startswith(key) for head in heads):
                wanted[key] = sheet.cell(r, column).value
    missing = [k for k, v in wanted.items() if v is None]
    if missing:
        raise IfiCellError(f"n° 45 Tableau_1 is missing rows {missing}")

    return Aggregate(
        year=year,
        foyers=float(wanted["Effectif"]),
        base_eur=_plausible("patrimoine net total",
                            float(wanted["Patrimoine net total"]), PLAUSIBLE_BASE_EUR),
        ifi_eur=_plausible("IFI payé", float(wanted["IFI payé"]), PLAUSIBLE_IFI_EUR),
        dons_eur=float(wanted["Dons IFI"]),
        published_mean_base_eur=float(wanted["Patrimoine moyen"]),
    )


#: The tranche bounds as the publication labels them, in euros. Read off the labels
#: rather than hardcoded blind: `tranches()` asserts the sheet still says this.
TRANCHE_BOUNDS = ((1.30e6, 2.57e6), (2.57e6, 5.0e6), (5.0e6, 10.0e6),
                  (10.0e6, float("inf")))


def tranches(raw: Path | None = None) -> list[Tranche]:
    """The four published tranches, as counts and euros rather than shares.

    The sheet gives shares of foyers and shares of total IFI; the levels come from the
    aggregate. Both routes to a tranche's IFI — its published share of the total, and
    its published mean times its count — are computed, and `verify_ifi.py` checks they
    agree. They are independent numbers in the publication, so their agreement is a
    real check on our reading and not a tautology.
    """
    sheet = _sheet(TRANCHE_FILE, "Graphique 3", raw)
    totals = aggregate(TRANCHE_YEAR, raw)

    # The data block is FOUND by shape, not addressed by coordinates: this sheet puts
    # its stub in column 2 and its rows at 26-29, under a chart that occupies the top
    # of the sheet, and neither is a promise the publication has made.
    rows: list[tuple[str, float, float, float]] = []
    for r in range(1, sheet.max_row + 1):
        for c in range(1, sheet.max_column - 2):
            label = sheet.cell(r, c).value
            trio = [sheet.cell(r, c + i).value for i in (1, 2, 3)]
            if isinstance(label, str) and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in trio
            ):
                rows.append((label.strip(), float(trio[0]), float(trio[1]),
                             float(trio[2])))
                break

    if len(rows) != len(TRANCHE_BOUNDS):
        raise IfiCellError(
            f"n° 33 Graphique 3 gave {len(rows)} tranche rows, expected "
            f"{len(TRANCHE_BOUNDS)}: {[r[0] for r in rows]}"
        )

    out: list[Tranche] = []
    for (lower, upper), (label, share_foyers, share_ifi, mean_keur) in zip(
        TRANCHE_BOUNDS, rows, strict=True
    ):
        # The bounds are checked against the sheet's own labels rather than trusted.
        # "De 1,3 à 2,57" / "Plus de 10": pull every number out and require that it
        # names this tranche. A publication that re-cut its tranches would otherwise be
        # read with the old bounds and nothing would say so.
        printed = [float(m.replace(",", ".")) * 1e6
                   for m in re.findall(r"\d+(?:[.,]\d+)?", label)]
        expected = [lower] if upper == float("inf") else [lower, upper]
        if printed != expected:
            raise IfiCellError(
                f"tranche label {label!r} reads {printed} where the bounds say "
                f"{expected}. The publication has re-cut its tranches; re-read it "
                f"rather than adjusting TRANCHE_BOUNDS to match."
            )
        # The mean is printed in THOUSANDS of euros on the right-hand axis.
        out.append(Tranche(
            lower_eur=lower,
            upper_eur=upper,
            foyers=totals.exact_foyers * share_foyers / 100.0,
            ifi_eur=totals.ifi_eur * share_ifi / 100.0,
            mean_ifi_eur=mean_keur * 1e3,
        ))
    return out
