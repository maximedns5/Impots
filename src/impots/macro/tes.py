"""Reading INSEE's symmetric input-output table (M0).

Reading, not propagating. `scripts/verify_tes.py` must be green and `docs/M0_TES.md`
written before any Leontief code exists — the EEC's M0 changed the shape of its
problem, and this gate is why that is now a procedure rather than a memory.

The file is the *TES symétrique* — branch × branch, already converted from the
supply-use form, which is the object a Leontief inverse needs. It ships as three
sheets: a presentation note, the domestic table, and a separate import matrix. The
second is what the composition comes from; the third is what measures leakage, which
§1 requires to be computed rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"

DOMESTIC_SHEET = "TES de production domestique"
IMPORTS_SHEET = "TES des importations"

#: Where each block begins and ends is DISCOVERED per sheet, not assumed.
#:
#: The two sheets do not share a layout, and assuming they did is the first thing M0
#: caught: on the domestic sheet the intermediate matrix starts at column 45 and the
#: product codes sit in column 3, while on the import sheet the matrix starts at
#: column 10 and the codes sit in column 9. A reader carrying one set of constants
#: reads the import matrix out of the wrong columns and raises — or worse, does not.
#:
#: The block is found by its own headers: row 6 announces it, row 8 closes it.
BLOCK_START_MARKER = "ENTREES INTERM"
BLOCK_END_MARKER = "Total des entrées interm"
CODE_ROW = 9
FIRST_PRODUCT_ROW = 11
HEADER_ROW = 8
BLOCK_TITLE_ROW = 6

#: Final-use columns, matched by the header text the sheet prints above them, as
#: (header, exact-match, sub-code).
#:
#: The third element is the finding that made this table's M0 worth running. Final
#: consumption is published as FOUR columns under ONE merged header — Ménages, APU,
#: ISBLSM, TOTAL — with the institutional sector written on the code row beneath.
#: Matching the header alone returns its leftmost column, so `consommation_finale`
#: silently meant *households only*: 1 158.7 bn where the total is 1 888.2 bn. The
#: balance identity did not catch it, because that identity is built on "Total des
#: emplois finals", a separate column that is correct either way. It surfaced only
#: from adding the components up by hand and finding 730 bn missing.
#:
#: The institutional split is kept rather than discarded: a public-spending shock and
#: a household-transfer shock enter the macro layer through different columns, and the
#: MPC that applies to one does not apply to the other.
FINAL_USE_MARKERS: dict[str, tuple[str, bool, str | None]] = {
    "consommation_finale_menages": ("Dépenses de consommation finale (1)", True, "Ménages"),
    "consommation_finale_apu": ("Dépenses de consommation finale (1)", True, "APU"),
    "consommation_finale_isblsm": ("Dépenses de consommation finale (1)", True, "ISBLSM"),
    "consommation_finale": ("Dépenses de consommation finale (1)", True, "TOTAL"),
    "fbcf": ("Formation brute de capital fixe (1)", True, None),
    "objets_de_valeur": ("Acq. moins cessions d'objets de valeur (1)", True, None),
    "variation_stocks": ("Variation de stocks (1)", True, None),
    "formation_brute_capital": ("Formation brute de capital (1)", True, None),
    "exportations": ("Exportations", True, None),
    "total_emplois_finals": ("Total des emplois finals", True, None),
    "total_emplois": ("Total des emplois", True, None),
}


class TesError(RuntimeError):
    """The input-output table cannot be read as expected."""


@dataclass(frozen=True)
class Tes:
    """One vintage of the symmetric table, in millions of euros."""

    branches: tuple[str, ...]
    labels: tuple[str, ...]
    domestic: np.ndarray
    """Intermediate consumption, domestic production. `domestic[i, j]` is product i
    consumed by branch j."""
    imported: np.ndarray
    """The same, for imported product. Its row sums are the leakage §1 needs."""
    final_uses: dict[str, np.ndarray]
    total_output: np.ndarray
    """Total resources of each product at basic prices, domestic production only."""
    vintage: str
    source_file: str

    @property
    def n(self) -> int:
        return len(self.branches)

    @property
    def base_year(self) -> int:
        """The year the table describes, taken from the vintage rather than the clock.

        Pairing a 2022 table with 2023 employment would silently misstate every
        employment coefficient, so the year travels with the table.
        """
        return int(self.vintage[:4])


def _sheet(path: Path, name: str) -> Any:
    try:
        import openpyxl
    except ModuleNotFoundError as error:  # pragma: no cover - environment
        raise TesError("openpyxl is required to read the TES") from error
    if not path.exists():
        raise TesError(f"{path} not found — download it and record it in the manifest")
    workbook = openpyxl.load_workbook(path, data_only=True)
    if name not in workbook.sheetnames:
        raise TesError(f"{path.name} has no sheet {name!r}; got {workbook.sheetnames}")
    return workbook[name]


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise TesError(f"expected a number, got {value!r}") from error


def _find(sheet: Any, row: int, marker: str, *, exact: bool = False) -> int | None:
    """Leftmost column on `row` whose header matches `marker`.

    `exact` exists because two of the headers are prefixes of each other: "Total des
    emplois" is contained in "Total des emplois finals", which sits to its left, so a
    substring search returns the same column for both and the two totals come back
    identical — 3 245.8 bn each, where the real values differ by the whole
    intermediate block. Found by reading the numbers rather than by the code failing.
    """
    for column in range(1, sheet.max_column + 1):
        value = sheet.cell(row, column).value
        if not value:
            continue
        text = " ".join(str(value).split())
        if (text.lower() == marker.lower()) if exact else (marker.lower() in text.lower()):
            return column
    return None


def _subcolumn(sheet: Any, header_column: int, subcode: str, key: str) -> int:
    """The column under a merged header carrying `subcode` on the code row.

    Walks right from the header until the next header begins. Raises rather than
    falling back to the header column: a silent fallback is exactly how
    `consommation_finale` came to mean households only.
    """
    column = header_column
    while column <= sheet.max_column:
        if column > header_column and sheet.cell(HEADER_ROW, column).value:
            break
        found = " ".join(str(sheet.cell(CODE_ROW, column).value or "").split())
        if found.lower() == subcode.lower():
            return column
        column += 1
    raise TesError(
        f"final-use column {key!r}: no sub-column {subcode!r} under its header at "
        f"column {header_column}"
    )


def _geometry(sheet: Any) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """(product rows, branch columns) for one sheet, from that sheet's own headers.

    The published symmetric table carries **37** branches, not the 38 its name
    suggests — an M0 finding, recorded rather than worked around. The rows also end
    with several literally labelled TOTAL, and the columns continue past the matrix
    into consumption by sector (Ménages, APU, ISBLSM); both are excluded by taking
    only what lies inside the announced block.
    """
    start = _find(sheet, BLOCK_TITLE_ROW, BLOCK_START_MARKER)
    end = _find(sheet, HEADER_ROW, BLOCK_END_MARKER)
    if start is None or end is None or end <= start:
        raise TesError(
            "could not locate the intermediate-consumption block from its own headers; "
            "the sheet layout has moved and the reader must be re-derived, not patched"
        )
    columns = [
        (c, str(sheet.cell(CODE_ROW, c).value).strip())
        for c in range(start, end)
        if sheet.cell(CODE_ROW, c).value
    ]
    branch_codes = {code for _, code in columns}
    # The product-code column is the one immediately left of the block that carries
    # the same codes going down.
    code_column = None
    for candidate in range(start - 1, 0, -1):
        found = [
            str(sheet.cell(r, candidate).value).strip()
            for r in range(FIRST_PRODUCT_ROW, sheet.max_row + 1)
            if sheet.cell(r, candidate).value
        ]
        if found and set(found) & branch_codes:
            code_column = candidate
            break
    if code_column is None:
        raise TesError("could not locate the product-code column beside the block")

    product_rows = [
        (r, str(sheet.cell(r, code_column).value).strip())
        for r in range(FIRST_PRODUCT_ROW, sheet.max_row + 1)
        if sheet.cell(r, code_column).value
        and str(sheet.cell(r, code_column).value).strip() in branch_codes
    ]
    if [code for _, code in product_rows] != [code for _, code in columns]:
        raise TesError(
            "the symmetric table's rows and columns are not the same branches in the "
            "same order, which every identity below assumes"
        )
    return product_rows, columns


def load(vintage: str = "2023SD", raw: Path | None = None) -> Tes:
    """Read one vintage. Millions of euros throughout, as published."""
    name = f"insee_TES_symetrique_A38_{vintage}.xlsx"
    path = (raw or RAW) / name
    domestic_sheet = _sheet(path, DOMESTIC_SHEET)
    import_sheet = _sheet(path, IMPORTS_SHEET)

    product_rows, branch_columns = _geometry(domestic_sheet)
    branches = tuple(code for _, code in product_rows)
    labels = tuple(
        str(domestic_sheet.cell(r, 2).value or "").strip() for r, _ in product_rows
    )
    n = len(branches)

    domestic = np.array([
        [_number(domestic_sheet.cell(r, c).value) for c, _ in branch_columns]
        for r, _ in product_rows
    ])

    # The import sheet repeats the layout on its own grid, so its coordinates are
    # resolved from its own headers rather than borrowed from the domestic one.
    import_rows, import_columns = _geometry(import_sheet)
    if [code for _, code in import_rows] != list(branches):
        raise TesError("the import matrix does not carry the same branches")
    imported = np.array([
        [_number(import_sheet.cell(r, c).value) for c, _ in import_columns]
        for r, _ in import_rows
    ])

    final_uses = {}
    for key, (marker, exact, subcode) in FINAL_USE_MARKERS.items():
        column = _find(domestic_sheet, HEADER_ROW, marker, exact=exact)
        if column is None:
            raise TesError(f"final-use column {key!r} not found from its header")
        if subcode is not None:
            column = _subcolumn(domestic_sheet, column, subcode, key)
        final_uses[key] = np.array(
            [_number(domestic_sheet.cell(r, column).value) for r, _ in product_rows]
        )
    total_output = final_uses["total_emplois"]

    if domestic.shape != (n, n) or imported.shape != (n, n):
        raise TesError(
            f"expected square {n}x{n} matrices, got {domestic.shape} and {imported.shape}"
        )
    return Tes(
        branches=branches, labels=labels, domestic=domestic, imported=imported,
        final_uses=final_uses, total_output=total_output,
        vintage=vintage, source_file=name,
    )


# --------------------------------------------------------------------------- #
# Employment by branch — same accounts vintage, a different nomenclature habit
# --------------------------------------------------------------------------- #
EMPLOYMENT_FILE = "insee_cn2024_t6208_emploi_par_branche_a38.xlsx"
EMPLOYMENT_SHEET = "T_6208 en niveau"

#: Three A38 branches whose employment row carries an A17 code with a DIFFERENT
#: letter, because at A17 each is a single-branch aggregate with its own label.
#:
#: The table is hierarchical: a branch is written at the coarsest level where it
#: coincides with itself, so most rows resolve by suffix — `AZ` appears as `A5_AZ`,
#: `FZ` as `A5_FZ`. These three do not, and matching them by suffix leaves ten
#: branches unmatched with no error: `CA` is `A17_C1`, `CD` is `A17_C2`, `CL` is
#: `A17_C4`. Each is one-to-one with its A38 branch, verified against the labels —
#: not an aggregation being silently spread.
EMPLOYMENT_ALIASES = {"CA": "C1", "CD": "C2", "CL": "C4"}


def employment(branches: tuple[str, ...], year: int = 2023,
               raw: Path | None = None) -> np.ndarray:
    """Domestic employment by branch, in thousands of persons.

    Ordered to match `branches`, so it can be divided into output directly. Raises
    rather than filling a gap: a branch with no employment row would otherwise get a
    coefficient of zero and quietly contribute no jobs to any shock.
    """
    sheet = _sheet((raw or RAW) / EMPLOYMENT_FILE, EMPLOYMENT_SHEET)
    # The year headers are STRINGS in this workbook, not integers — the column would
    # never be found by an int lookup, and the failure reads as "no such year".
    years: dict[int, int] = {}
    for c in range(3, sheet.max_column + 1):
        header = str(sheet.cell(4, c).value or "").strip()
        if header.isdigit():
            years[int(header)] = c
    if year not in years:
        raise TesError(f"employment table has no year {year}; has {min(years)}-{max(years)}")
    column = years[year]

    by_suffix: dict[str, int] = {}
    for row in range(6, sheet.max_row + 1):
        code = sheet.cell(row, 1).value
        if not code or "_" not in str(code):
            continue
        by_suffix.setdefault(str(code).strip().split("_", 1)[1], row)

    values, missing = [], []
    for branch in branches:
        row = by_suffix.get(branch) or by_suffix.get(EMPLOYMENT_ALIASES.get(branch, ""))
        if row is None:
            missing.append(branch)
            continue
        values.append(_number(sheet.cell(row, column).value))
    if missing:
        raise TesError(
            f"no employment row for {missing} — matching by code suffix leaves these "
            f"unmatched, and filling them with zero would silently make those branches "
            f"contribute no jobs to any shock"
        )
    return np.array(values)
