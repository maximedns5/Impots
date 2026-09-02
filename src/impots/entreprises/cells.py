"""Compute the firm cell table from manifested primary files (D-026).

**No number in this module comes from an agent's prose.** Every figure is read
out of a file in `data/raw/` whose sha256 is recorded in the manifest, by code
that is tested — so a cell total is reproducible from the manifested file, and a
disagreement about it is settled by re-running rather than by re-asking.

That rule exists because the alternative was measured twice and failed twice:
Phase 1 put six statistics through research agents and got six scope problems
back; Phase 2's firm-data agent returned `WRONG` with fifteen. Agents locate
files and adversarially check what this code computed. They are never the source
of record for a figure.

## The three files and what each is for

* **INSEE Ésane 2023, `princ_caract_taille`** — the only published cross-tab of
  sector by size. It supplies the shape: 19 NAF sections × three size classes,
  with firm counts, turnover, value added and résultat courant avant impôts.
* **INSEE Focus 372** — supplies what Ésane merges. At the `a21` level Ésane
  publishes *"ETI ou GE"* as one class; Focus figures 3a, 3b and 3c publish that
  split by broad sector for counts, turnover and value added respectively. Its
  complementary table 3 also publishes the value-added dispersion, which is what
  lets the population draw a fitted spread inside a cell rather than an assumed one.
* **DGFiP Statistiques 39** — the fiscal control totals: how many firms are
  liable to IS at all (2.72 M against Ésane's 5.18 M marchand enterprises), and
  the national résultat fiscal that pins the fiscal-to-accounting ratio.

## What this changes about the fiscal-to-accounting ratio

It stops being free. D-024 set the IS tolerance at ±20 % precisely because that
ratio was an unpinned scalar and a tighter gate would have invited tuning it. Here
it is **computed** — national résultat fiscal over Ésane's résultat courant avant
impôts, both from manifested files — so there is nothing left to tune.

## The one figure this module does not compute

`P_LOSS_BY_SIZE`. Loss-making is a *count* and no machine-readable source
publishes it per size class; Ésane gives no loss counts and DGFiP's data file
gives loss *amounts*. It is therefore read from a publication, cited below, and
flagged in the provenance so it cannot be mistaken for a computed figure. It is
the remaining D-026 gap in this table and it is deliberately the only one.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import NormalDist
from typing import Any

NORMAL = NormalDist()

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"

ESANE_FILE = "insee_esane2023_caracteristiques_par_taille.xlsx"
FOCUS_FILE = "insee_focus372_tissu_productif_categorie_2023.xlsx"
DGFIP_FILE = "dgfip_stat_39_impot_benefice_2024_donnees.xlsx"

SIZES = ("micro", "PME", "ETI", "GE")

#: Ésane's own category labels, verbatim. Matched exactly rather than by
#: substring: "PME, hors Microentreprises" contains "Microentreprises".
ESANE_CATEGORIES = {
    "Ensemble des catégories d'entreprise": "total",
    "Microentreprises (MICRO)": "micro",
    "Petites et moyennes entreprises (PME), hors Microentreprises": "PME",
    "Entreprises de taille intermédiaire (ETI) ou Grandes entreprises (GE)": "ETI_GE",
}

#: Ésane column indices in `princ_caract_taille`, 0-based.
COL_NIVEAU, COL_SECTION, COL_CATEGORIE = 0, 1, 3
COL_N, COL_CA, COL_VA, COL_RCAI = 4, 8, 10, 14

#: NAF section -> the broad sector Focus 372 uses. Focus reports five; sections
#: outside its "principalement marchands" champ (A agriculture, K finance) are
#: mapped to the nearest broad sector for the ETI/GE split only, which affects
#: nothing else because both are suppressed at that size in Ésane anyway.
SECTION_TO_BROAD = {
    "A": "Industrie", "B": "Industrie", "C": "Industrie", "D": "Industrie",
    "E": "Industrie", "F": "Construction", "G": "Commerce", "H": "Transports",
    "I": "Services marchands", "J": "Services marchands", "K": "Services marchands",
    "L": "Services marchands", "M": "Services marchands", "N": "Services marchands",
    "P": "Services marchands", "Q": "Services marchands", "R": "Services marchands",
    "S": "Services marchands",
}

#: A sub-aggregate of section C that Ésane repeats at a21. Summing it double-counts.
EXCLUDED_SECTIONS = {"Cy"}

#: Share of IS payers with no positive taxable profit, by size class.
#:
#: THE ONE FIGURE HERE NOT COMPUTED FROM A MACHINE-READABLE FILE. Loss-making is
#: a count, and no open data file publishes it per size class. Source: INSEE
#: Références, *Les entreprises en France* édition 2023, fiche 3.6 « Impôt sur les
#: sociétés », figure 1 (2021 data, DGFiP liasses): share declaring a profit of
#: 60.2 % MIC, 78.9 % PME, 78.3 % ETI, 75.5 % GE. Recorded as its complement.
P_LOSS_BY_SIZE = {"micro": 0.398, "PME": 0.211, "ETI": 0.217, "GE": 0.245}
P_LOSS_SOURCE = (
    "INSEE Références, Les entreprises en France 2023, fiche 3.6, figure 1 "
    "(données 2021) — lu dans la publication, non calculé depuis un fichier"
)

#: Ésane reports in millions of euros.
MILLIONS = 1e6

#: The DGFiP row carrying the IS-liable firm count, matched in full. Whitespace is
#: normalised before comparison because the published cell has a trailing space.
IS_FIRM_COUNT_LABEL = "Nombre d'entreprises à l'IS"


class CellBuildError(RuntimeError):
    """The primary files cannot produce a cell table as they stand."""


@dataclass(frozen=True)
class Cell:
    """One published sector x size cell, in euros and whole firms."""

    naf_section: str
    taille: str
    n_firms: float
    turnover_total: float
    value_added_total: float
    result_total: float
    p_loss: float
    sigma: float | None = None


@dataclass
class CellProvenance:
    vintage: str
    sources: dict[str, str]
    fiscal_to_accounting: float
    esane_firms: float
    esane_turnover: float
    is_liable_firms: float
    is_share_by_size: dict[str, float]
    resultat_fiscal_national: float
    esane_rcai_national: float
    gross_up_by_size: dict[str, float] = field(default_factory=dict)
    suppressed_cells: list[str] = field(default_factory=list)
    derived_cells: list[str] = field(default_factory=list)
    p_loss_by_size: dict[str, float] = field(default_factory=lambda: dict(P_LOSS_BY_SIZE))
    p_loss_source: str = P_LOSS_SOURCE
    dispersion_sigma: dict[str, float] = field(default_factory=dict)
    """Lognormal sigma of value added per cell, fitted to published quartiles.
    Carried for the population draw, which currently assumes its own."""


def _sheet(path: Path, name: str) -> Any:
    try:
        import openpyxl
    except ModuleNotFoundError as error:  # pragma: no cover - environment
        raise CellBuildError(
            "openpyxl is required to read the primary spreadsheets: pip install openpyxl"
        ) from error
    if path.parent == RAW:
        # D-028: a file with no recorded source cannot back a published figure. Only
        # enforced for the real raw tree, so tests may build their own workbooks.
        from impots.population.ingest import UnmanifestedInput, require_sourced

        try:
            require_sourced(path.name)
        except UnmanifestedInput as error:
            raise CellBuildError(str(error)) from error
    if not path.exists():
        raise CellBuildError(f"{path} not found — download it and record it with "
                             "`impots population manifest`")
    workbook = openpyxl.load_workbook(path, data_only=True)
    if name not in workbook.sheetnames:
        raise CellBuildError(f"{path.name} has no sheet {name!r}; got {workbook.sheetnames}")
    return workbook[name]


#: Ésane's own missing-data codes, from its note de lecture: "N = Donnée non
#: disponible, S = Donnée soumise au secret statistique". Both are missing. Handling
#: only "S" — as an earlier version did — meant a future vintage carrying an "N"
#: would reach float("N") and abort the build. That fails loud rather than quiet,
#: which is the right direction, but it is not the same as handling the file's
#: convention, which is what the docstring claimed.
MISSING_CODES = {"S", "N"}


def _number(value: Any) -> float | None:
    """A published number, or None where Ésane withheld it. Never zero: the firms in
    a suppressed cell exist, only their number is withheld."""
    if value is None or (isinstance(value, str) and value.strip() in MISSING_CODES):
        return None
    return float(value)


# --------------------------------------------------------------------------- #
# readers — one per file, each doing nothing but turning a sheet into numbers
# --------------------------------------------------------------------------- #
def read_esane(path: Path) -> dict[tuple[str, str], dict[str, float | None]]:
    """Ésane's a21 rows: (section, category) -> the four quantities we need."""
    sheet = _sheet(path, "princ_caract_taille")
    table: dict[tuple[str, str], dict[str, float | None]] = {}
    for row in sheet.iter_rows(values_only=True):
        if not row or row[COL_NIVEAU] != "a21":
            continue
        section = str(row[COL_SECTION])
        if section in EXCLUDED_SECTIONS:
            continue
        category = ESANE_CATEGORIES.get(str(row[COL_CATEGORIE]))
        if category is None:
            raise CellBuildError(f"unknown Ésane category {row[COL_CATEGORIE]!r}")
        table[(section, category)] = {
            "n": _number(row[COL_N]),
            "turnover": _number(row[COL_CA]),
            "value_added": _number(row[COL_VA]),
            "result": _number(row[COL_RCAI]),
        }
    if not table:
        raise CellBuildError(f"{path.name} yielded no a21 rows")

    # Ésane suppresses a cell but still publishes its section's "Ensemble" row. Where
    # exactly one size class is missing a quantity, it is recoverable by subtraction
    # — this is arithmetic on published numbers, not imputation. It restores about
    # 150 bn of turnover in sections K, P, Q and S that was otherwise discarded, and
    # discarding it silently inflated the micro class, because the firms it stood for
    # were being swept into the micro residual.
    sizes = ("micro", "PME", "ETI_GE")
    for section in {section for section, _ in table}:
        total = table.get((section, "total"))
        if total is None:
            continue
        for quantity in ("n", "turnover", "value_added", "result"):
            if total[quantity] is None:
                continue
            missing = [s for s in sizes if table.get((section, s), {}).get(quantity) is None]
            if len(missing) != 1:
                continue
            known = sum(
                table[(section, s)][quantity] or 0.0
                for s in sizes
                if s != missing[0] and (section, s) in table
            )
            table.setdefault((section, missing[0]), dict.fromkeys(
                ("n", "turnover", "value_added", "result")))
            table[(section, missing[0])][quantity] = float(total[quantity]) - known
    return table


def read_focus_split(path: Path) -> dict[str, dict[str, dict[str, float]]]:
    """Focus 372 figures 3a/3b/3c: counts, turnover and value added, by broad sector
    x each of the four size classes.

    This is the published answer to the question `_split_eti_ge` used to estimate.
    An earlier version weighted the split by national mean turnover per firm and got
    the GE share of turnover wrong by up to 7 points and of value added by up to 12,
    moving 128 bn of turnover and 39 bn of value added against a table sitting in the
    same workbook. Estimating what a file already publishes is the exact failure
    D-026 exists to stop, and it happened here.
    """
    sheets = {"n": "Figure 3a", "turnover": "Figure 3b", "value_added": "Figure 3c"}
    columns = {"micro": 2, "PME": 4, "ETI": 6, "GE": 8}
    split: dict[str, dict[str, dict[str, float]]] = {}
    for quantity, sheet_name in sheets.items():
        sheet = _sheet(path, sheet_name)
        for row in range(5, sheet.max_row + 1):
            sector = sheet.cell(row, 1).value
            if not sector or str(sector).startswith(
                ("Ensemble", "1.", "Lecture", "Champ", "Source")
            ):
                continue
            values = {size: sheet.cell(row, col).value for size, col in columns.items()}
            if any(not isinstance(v, (int, float)) for v in values.values()):
                continue
            bucket = split.setdefault(str(sector), {})
            for size, value in values.items():
                # 3b and 3c are in billions; 3a is a count.
                scale = 1.0 if quantity == "n" else 1e3  # -> millions, like Ésane
                bucket.setdefault(size, {})[quantity] = float(value) * scale
    if not split:
        raise CellBuildError(f"{path.name} figures 3a/3b/3c yielded no sector rows")
    return split


def read_focus_dispersion(path: Path) -> dict[tuple[str, str], float]:
    """Focus complementary table 3: value-added quartiles by broad sector x size.

    Returned as a fitted lognormal sigma, because that is what a population draw
    needs. For a lognormal, sigma = ln(Q3/Q1) / (2 x 0.6745).
    """
    sheet = _sheet(path, "Tableau complémentaire 3")
    quartile_columns = {"micro": 2, "PME": 5, "ETI": 8, "GE": 11}  # 1st quartile column
    sigmas: dict[tuple[str, str], float] = {}
    for row in range(5, sheet.max_row + 1):
        sector = sheet.cell(row, 1).value
        if not sector or str(sector).startswith(("Ensemble", "Lecture", "Champ", "Source", "1.")):
            continue
        for size, first in quartile_columns.items():
            q1 = sheet.cell(row, first).value
            q3 = sheet.cell(row, first + 2).value
            if not isinstance(q1, (int, float)) or not isinstance(q3, (int, float)):
                continue
            if q1 <= 0 or q3 <= 0 or q3 <= q1:
                continue  # a zero quartile carries no information about spread
            sigmas[(str(sector), size)] = math.log(q3 / q1) / (2 * 0.6745)
    return sigmas


def read_dgfip(path: Path) -> dict[str, Any]:
    """DGFiP Statistiques 39: the fiscal control totals."""
    sheet = _sheet(path, "Tableau 2")
    labels = {2: "n", 4: "resultat_fiscal", 6: "benefices", 8: "is_brut"}
    order = ("micro", "PME", "ETI", "GE")  # TPE / PME / ETI / GE, in column order
    by_size: dict[str, dict[str, float]] = {size: {} for size in order}
    for row, key in labels.items():
        for index, size in enumerate(order):
            value = sheet.cell(row + 1, 3 + index).value
            if not isinstance(value, (int, float)):
                raise CellBuildError(f"{path.name} Tableau 2 cell for {size}/{key} is not a number")
            by_size[size][key] = float(value)

    graph = _sheet(path, "Graphique 1")
    is_firms = None
    for row in range(1, graph.max_row + 1):
        label = " ".join(str(graph.cell(row, 2).value or "").replace("\u2019", "'").split())
        # WHOLE-LABEL EQUALITY, deliberately. Substring tests against a French display
        # string are banned in ingest and this row is why: `"IS" in label.upper()` is
        # also true of "Nombre d'entreprises à l'IR" directly beneath, because
        # ENTREPRISES contains IS. The right row was being selected by publication
        # order alone, and a reordered sheet would have substituted the 4.7 M
        # income-tax count for the 2.7 M corporation-tax one, moving every level in
        # this table with it. Even `"l'IS" in label` is the wrong shape of test.
        if label == IS_FIRM_COUNT_LABEL:
            values = [graph.cell(row, c).value for c in range(3, graph.max_column + 1)]
            numbers = [v for v in values if isinstance(v, (int, float))]
            if numbers:
                is_firms = float(numbers[-1]) * 1e6  # published in millions
                break
    if is_firms is None:
        is_firms = sum(size["n"] for size in by_size.values())
    return {
        "by_size": by_size,
        "is_firms": is_firms,
        "resultat_fiscal": sum(s["resultat_fiscal"] for s in by_size.values()),
    }


# --------------------------------------------------------------------------- #
# the build
# --------------------------------------------------------------------------- #
def _split_eti_ge(
    section: str,
    merged: dict[str, float | None],
    focus: dict[str, dict[str, dict[str, float]]],
) -> dict[str, dict[str, float]] | None:
    """Split Ésane's merged "ETI ou GE" cell using Focus 372's published split.

    Every share here is read, not estimated: counts from figure 3a, turnover from
    3b, value added from 3c, each at broad-sector level. Turnover and value added
    get their *own* shares, because ETI and GE have materially different VA/CA ratios
    — in industry 25.6 % against 20.1 % — so one share cannot carry both.

    Only **résultat** has no published split. It takes the value-added share, which
    is the closest published proxy, and that single borrowed share is the one
    assumption left in this function.

    What remains assumed throughout: that the ETI/GE mix inside a NAF section matches
    its broad sector. Section D (energy) shows the cost — it is far more GE-heavy
    than the manufacturing that dominates "Industrie", and a broad-sector share
    cannot see that.
    """
    if merged.get("n") is None:
        return None
    published = focus.get(SECTION_TO_BROAD.get(section, ""))
    if not published or not {"ETI", "GE"} <= set(published):
        return None

    split: dict[str, dict[str, float]] = {"ETI": {}, "GE": {}}
    for quantity, published_key in (
        ("n", "n"), ("turnover", "turnover"),
        ("value_added", "value_added"), ("result", "value_added"),
    ):
        total = merged.get(quantity)
        eti = published["ETI"].get(published_key, 0.0)
        ge = published["GE"].get(published_key, 0.0)
        denominator = eti + ge
        if total is None or denominator <= 0:
            split["ETI"][quantity] = split["GE"][quantity] = 0.0
            continue
        split["ETI"][quantity] = float(total) * eti / denominator
        split["GE"][quantity] = float(total) * ge / denominator
    return split


def _top_share_of_total(keep_fraction: float, sigma: float) -> float:
    """Share of a lognormal total held by its **largest** `keep_fraction` of units.

    For X ~ LogNormal(mu, sigma), the top p of units hold 1 - Phi(Phi^-1(1-p) - sigma).

    This is what stops the champ adjustment from being wrong by a factor of two. Half
    of Ésane's micro-enterprises are not liable to IS, but they are the *smallest*
    half — micro-entrepreneurs and entreprises individuelles, not micro SARLs. Scaling
    their turnover proportionally removed 334 bn of it when, under the very lognormal
    this module fits to that class (sigma around 2.6 to 3.1), the smallest half holds
    between 0.1 % and 2 % of it. The module was fitting a heavy-tailed distribution
    and then adjusting it as if it were uniform.
    """
    if keep_fraction >= 1.0:
        return 1.0
    if keep_fraction <= 0.0:
        return 0.0
    return 1.0 - NORMAL.cdf(NORMAL.inv_cdf(1.0 - keep_fraction) - sigma)


def build_cells(raw: Path | None = None, vintage: str = "2023") -> tuple[list[Cell], CellProvenance]:
    """Compute the cell table. Every number traces to a manifested file.

    The three modelling decisions, all declared because none of them is forced by
    the data:

    **Champ.** Ésane counts 5.18 M marchand enterprises; 2.72 M are liable to IS.
    Only the **micro** class is scaled, and only its count is scaled proportionally:
    the firms that fall out are the smallest, so their share of turnover is taken from
    the cell's own fitted lognormal rather than from their headcount. DGFiP's size
    buckets are not INSEE's — its PME bucket is a quarter larger than INSEE's whole
    PME class — so its by-class counts are deliberately not used, and the whole
    taxonomy gap lands in the micro residual. That is a known overstatement of the
    micro count, of the order of 2 %.

    **One ratio, doing one job.** Ésane publishes a *net* résultat courant avant
    impôts while the population's draw wants the *positive* result of profitable
    firms — loss-makers are zeroed separately, so feeding it a net figure would
    subtract their losses twice. Rather than gross up and then convert, which sets
    two scalars fighting each other, a single `fiscal_to_accounting` absorbs both
    steps: DGFiP's national bénéfices over this table's own positive accounting
    result. **It is computed, not chosen.** D-024 set the IS tolerance at +/-20 %
    because that scalar was free and a tighter gate would have invited tuning it.
    It is not free any more, and the consequence — the national IS total becomes
    calibrated, while its distribution across sectors and sizes stays free — is
    stated on the report line rather than left for a reader to infer.
    """
    raw = raw or RAW
    esane = read_esane(raw / ESANE_FILE)
    focus = read_focus_split(raw / FOCUS_FILE)
    sigmas = read_focus_dispersion(raw / FOCUS_FILE)
    dgfip = read_dgfip(raw / DGFIP_FILE)

    sections = sorted({section for section, _ in esane})
    suppressed: list[str] = []
    raw_cells: dict[tuple[str, str], dict[str, float]] = {}

    for section in sections:
        for size in ("micro", "PME"):
            row = esane.get((section, size))
            if row is None or row["n"] is None:
                suppressed.append(f"{section}/{size}")
                continue
            if row["turnover"] is None or row["value_added"] is None:
                # A cell can publish its count while withholding a value. Coercing the
                # withheld one to zero would state something the file does not — and
                # would put firms with no turnover into the population.
                suppressed.append(f"{section}/{size} (count published, value suppressed)")
                continue
            raw_cells[(section, size)] = {
                "n": float(row["n"]),
                "turnover": float(row["turnover"]),
                "value_added": float(row["value_added"]),
                # Only résultat may legitimately be absent while the rest is published:
                # it is the one quantity the loss add-back can supply from its class.
                "result": float(row["result"]) if row["result"] is not None else 0.0,
            }
        merged = esane.get((section, "ETI_GE"))
        split = _split_eti_ge(section, merged or {}, focus) if merged else None
        if split is None:
            suppressed += [f"{section}/ETI", f"{section}/GE"]
            continue
        for size in ("ETI", "GE"):
            raw_cells[(section, size)] = split[size]

    # A cell can survive with a published firm count but a suppressed turnover —
    # section Q's grandes entreprises, for instance. Carrying it would put firms with
    # no turnover into the population, which is not a small firm but a meaningless
    # one: it pays nothing, drags the effective-rate profile toward zero and divides
    # by zero on the way. Dropped here, before the counts are scaled, so the firms it
    # would have held are redistributed rather than lost.
    for key in [k for k, cell in raw_cells.items() if cell["turnover"] <= 0.0]:
        suppressed.append(f"{key[0]}/{key[1]} (count published, turnover suppressed)")
        del raw_cells[key]

    if not raw_cells:
        raise CellBuildError("no usable cells survived Ésane's statistical suppression")

    esane_firms = sum(cell["n"] for cell in raw_cells.values())
    esane_turnover = sum(cell["turnover"] for cell in raw_cells.values()) * MILLIONS
    esane_rcai = sum(cell["result"] for cell in raw_cells.values()) * MILLIONS

    # Champ. DGFiP's size taxonomy is NOT INSEE's — its PME bucket is larger, so
    # dividing class by class produces ratios above one and would *invent* firms.
    # Only DGFiP's TOTAL is used. A PME, an ETI and a GE are companies and so liable
    # to IS as a matter of legal form; the firms that fall out are almost all
    # micro-enterprises taxed at the income tax. So the whole adjustment is one share
    # on the micro class, and it is derived, not chosen.
    counts = {
        size: sum(cell["n"] for (_, s), cell in raw_cells.items() if s == size)
        for size in SIZES
    }
    larger = sum(counts[size] for size in ("PME", "ETI", "GE"))
    micro_target = max(dgfip["is_firms"] - larger, 0.0)
    is_share = {size: 1.0 for size in SIZES}
    is_share["micro"] = micro_target / counts["micro"] if counts["micro"] else 0.0

    benefices = sum(s["benefices"] for s in dgfip["by_size"].values())
    resultat_fiscal = dgfip["resultat_fiscal"]

    # Net result -> positive result, size class by size class. Ésane publishes a NET
    # résultat courant avant impôts: profits minus losses, netted *inside* the cell.
    # The population's draw wants the positive result of profitable firms, because it
    # zeroes loss-makers separately — feeding it a net figure subtracts their losses
    # twice, and it does so hardest where losses are most common, which is the small
    # end. DGFiP publishes both quantities per size class, so the conversion is a
    # published ratio rather than a fitted one. It runs from 1.94 for the smallest
    # firms to 1.61 for the largest, and that gradient is the whole point: a single
    # national gross-up would leave the profit distribution tilted toward big firms.
    #
    # DGFiP's size taxonomy is not INSEE's, as above — but here it enters only as a
    # ratio of two DGFiP quantities within the same class, which is far more robust
    # to the mismatch than a count would be.
    gross_up = {
        size: (values["benefices"] / values["resultat_fiscal"])
        if values["resultat_fiscal"] > 0 else 1.0
        for size, values in dgfip["by_size"].items()
    }

    # Pass 1: scale counts to the fiscal champ, and values by the share of the total
    # the surviving firms actually hold.
    scaled: dict[tuple[str, str], dict[str, float]] = {}
    for (section, size), cell in sorted(raw_cells.items()):
        sigma = sigmas.get((SECTION_TO_BROAD.get(section, ""), size))
        count_scale = is_share[size]
        value_scale = (
            1.0 if count_scale >= 1.0
            else _top_share_of_total(count_scale, sigma or 1.4)
        )
        if cell["n"] * count_scale <= 0:
            continue
        scaled[(section, size)] = {
            "n": cell["n"] * count_scale,
            "turnover": cell["turnover"] * MILLIONS * value_scale,
            "value_added": cell["value_added"] * MILLIONS * value_scale,
            "net_result": cell["result"] * MILLIONS * value_scale,
            "sigma": sigma,
        }

    # Pass 2: net result -> positive result of profitable firms.
    #
    # A cell's published résultat is NET: the profits of its profitable firms minus
    # the losses of its loss-makers. The population zeroes loss-makers separately, so
    # it wants the first term alone. Flooring the net at zero was the wrong way to get
    # there and it was not a small error — it handed a taxable base of exactly zero to
    # every cell whose aggregate happened to be negative, including 8 057 information
    # -and-communication PMEs turning over 46.8 bn and the whole of real-estate ETI/GE.
    # Those two cells alone are why the report read -70 % and -91 % on those sectors.
    #
    # Instead, each size class's losses are added back across its cells in proportion
    # to value added. The assumption is that losses fall where economic activity is,
    # within a size class; it is an assumption, but it is one that cannot zero a
    # sector, and the class totals still land where DGFiP puts them.
    negative_after: list[str] = []
    positive: dict[tuple[str, str], float] = {}
    for size in SIZES:
        in_size = [key for key in scaled if key[1] == size]
        net_size = sum(scaled[key]["net_result"] for key in in_size)
        va_size = sum(scaled[key]["value_added"] for key in in_size)
        losses = net_size * (gross_up[size] - 1.0)
        for key in in_size:
            share = scaled[key]["value_added"] / va_size if va_size > 0 else 0.0
            value = scaled[key]["net_result"] + losses * share
            if value < 0:
                negative_after.append(f"{key[0]}/{key[1]}")
                value = 0.0
            positive[key] = value

    cells = [
        Cell(
            naf_section=section,
            taille=size,
            n_firms=cell["n"],
            turnover_total=cell["turnover"],
            value_added_total=cell["value_added"],
            result_total=positive[(section, size)],
            p_loss=P_LOSS_BY_SIZE[size],
            sigma=cell["sigma"],
        )
        for (section, size), cell in sorted(scaled.items())
    ]
    accounting_positive_result = sum(cell.result_total for cell in cells)
    fiscal_to_accounting = (
        benefices / accounting_positive_result if accounting_positive_result else 1.0
    )

    provenance = CellProvenance(
        vintage=vintage,
        sources={
            "esane": ESANE_FILE, "focus": FOCUS_FILE, "dgfip": DGFIP_FILE,
        },
        fiscal_to_accounting=fiscal_to_accounting,
        esane_firms=esane_firms,
        esane_turnover=esane_turnover,
        is_liable_firms=sum(cell.n_firms for cell in cells),
        is_share_by_size=is_share,
        gross_up_by_size=gross_up,
        resultat_fiscal_national=resultat_fiscal,
        esane_rcai_national=esane_rcai,
        suppressed_cells=suppressed + [
            f"{entry} (still negative after loss add-back)" for entry in negative_after
        ],
        dispersion_sigma={
            f"{section}/{size}": sigmas[(SECTION_TO_BROAD[section], size)]
            for section, size in ((c.naf_section, c.taille) for c in cells)
            if section in SECTION_TO_BROAD and (SECTION_TO_BROAD[section], size) in sigmas
        },
    )
    return cells, provenance


def as_cell_table(cells: list[Cell], provenance: CellProvenance) -> dict[str, Any]:
    """The JSON shape `impots.entreprises.build` already reads."""
    return {
        "vintage": provenance.vintage,
        "fiscal_to_accounting": provenance.fiscal_to_accounting,
        "cells_are_synthetic": False,
        "provenance": asdict(provenance),
        "cells": [asdict(cell) for cell in cells],
    }
