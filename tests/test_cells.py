"""The firm cell table, computed from primary files (D-026).

Two kinds of test here, on purpose.

The **synthetic-workbook** tests build a tiny spreadsheet with the same shape as
INSEE's and run the readers over it. They exercise every branch that has ever
looked likely to break — exact category matching, statistical suppression, the
sub-aggregate row that double-counts if summed — and they run everywhere, because
the fixture is three sheets of made-up numbers rather than an 187 kB download.

The **real-file** tests run only where `data/raw/` has been populated. They are the
ones that would catch INSEE republishing a workbook with a column moved, which no
synthetic fixture can. They skip in CI rather than failing, exactly as the household
tests do against the EEC.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from impots.entreprises import cells as C

openpyxl = pytest.importorskip("openpyxl")

HAVE_PRIMARY = all(
    (C.RAW / name).exists() for name in (C.ESANE_FILE, C.FOCUS_FILE, C.DGFIP_FILE)
)
needs_primary = pytest.mark.skipif(
    not HAVE_PRIMARY,
    reason="data/raw/ has no primary spreadsheets — they are not redistributable",
)

ESANE_HEADER = [
    "NIVEAU NAF", "Secteur d'activité", "Activité", "Catégorie de l'entreprise",
    "Nombre d'entreprises", "eqtp", "emploi", "au 31 déc", "Chiffre d'affaires Hors Taxes",
    "CA export", "Valeur ajoutée", "Frais de personnel", "EBE", "CAF",
    "Résultat courant avant impôts", "Résultat net comptable", "Investissements",
]


def write_esane(path: Path, rows: list[tuple]) -> Path:
    """A workbook shaped like Ésane's `princ_caract_taille`, with our own numbers."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "princ_caract_taille"
    for _ in range(11):
        sheet.append([None])
    sheet.append(ESANE_HEADER)
    for niveau, section, categorie, n, ca, va, rcai in rows:
        line: list = [niveau, section, "libellé", categorie, n, None, None, None, ca,
                      None, va, None, None, None, rcai, None, None]
        sheet.append(line)
    workbook.save(path)
    return path


ESANE_ROWS = [
    ("a21", "C", "Ensemble des catégories d'entreprise", 300.0, 1000.0, 300.0, 100.0),
    ("a21", "C", "Microentreprises (MICRO)", 250.0, 100.0, 30.0, 5.0),
    ("a21", "C", "Petites et moyennes entreprises (PME), hors Microentreprises",
     45.0, 300.0, 90.0, 25.0),
    ("a21", "C", "Entreprises de taille intermédiaire (ETI) ou Grandes entreprises (GE)",
     5.0, 600.0, 180.0, 70.0),
    # A sub-aggregate INSEE repeats at a21. Summing it double-counts section C.
    ("a21", "Cy", "Ensemble des catégories d'entreprise", 40.0, 90.0, 20.0, 3.0),
    # Another NAF level, which must be ignored entirely.
    ("a88", "25", "Ensemble des catégories d'entreprise", 999.0, 999.0, 999.0, 999.0),
    # ONE suppressed class, with the section total published: recoverable by
    # subtraction, which is arithmetic on published numbers rather than imputation.
    ("a21", "F", "Ensemble des catégories d'entreprise", 100.0, 200.0, 60.0, 20.0),
    ("a21", "F", "Microentreprises (MICRO)", 88.0, 40.0, 12.0, 3.0),
    ("a21", "F", "Petites et moyennes entreprises (PME), hors Microentreprises",
     "S", "S", "S", "S"),
    ("a21", "F", "Entreprises de taille intermédiaire (ETI) ou Grandes entreprises (GE)",
     10.0, 150.0, 45.0, 16.0),
    # TWO suppressed classes: nothing is recoverable, and nothing may be invented.
    ("a21", "G", "Ensemble des catégories d'entreprise", 500.0, 900.0, 300.0, 80.0),
    ("a21", "G", "Microentreprises (MICRO)", 450.0, 100.0, 30.0, 8.0),
    ("a21", "G", "Petites et moyennes entreprises (PME), hors Microentreprises",
     "S", "S", "S", "S"),
    ("a21", "G", "Entreprises de taille intermédiaire (ETI) ou Grandes entreprises (GE)",
     "S", "S", "S", "S"),
]


@pytest.fixture
def esane(tmp_path: Path) -> Path:
    return write_esane(tmp_path / "esane.xlsx", ESANE_ROWS)


# --------------------------------------------------------------------------- #
# the readers, on a workbook whose right answers are known by construction
# --------------------------------------------------------------------------- #
def test_only_a21_rows_are_read(esane: Path) -> None:
    """Ésane publishes the same firms at four NAF levels. Reading more than one
    multiplies the country."""
    table = C.read_esane(esane)
    assert {section for section, _ in table} == {"C", "F", "G"}
    assert ("25", "total") not in table


def test_the_repeated_sub_aggregate_is_excluded(esane: Path) -> None:
    """`Cy` is a sub-total of section C. It has its own a21 row, so a reader that
    trusts the level alone counts those firms twice."""
    table = C.read_esane(esane)
    assert all(section != "Cy" for section, _ in table)


def test_categories_match_exactly_not_by_substring(esane: Path) -> None:
    """'Petites et moyennes entreprises (PME), hors Microentreprises' contains the
    string 'Microentreprises'. A substring match silently files every PME as a
    micro-enterprise, and the totals still add up."""
    table = C.read_esane(esane)
    assert table[("C", "micro")]["n"] == 250.0
    assert table[("C", "PME")]["n"] == 45.0
    assert table[("C", "micro")]["turnover"] == 100.0


def test_suppression_reads_as_missing_not_zero(esane: Path) -> None:
    """'S' is secret statistique. Zero would be a claim about the cell, and a false
    one — the firms are there, only the number is withheld."""
    assert C._number("S") is None
    assert C._number(0) == 0.0
    table = C.read_esane(esane)
    assert table[("G", "PME")]["n"] is None
    assert table[("G", "ETI_GE")]["turnover"] is None


def test_a_single_suppressed_class_is_recovered_by_subtraction(esane: Path) -> None:
    """Ésane withholds a cell but still publishes its section's total. Where exactly
    one class is missing, the difference IS the cell — arithmetic on published
    numbers, not imputation. Discarding it instead threw away 150 bn of turnover and,
    worse, quietly swept those firms into the micro residual."""
    table = C.read_esane(esane)
    assert table[("F", "PME")]["n"] == pytest.approx(100.0 - 88.0 - 10.0)
    assert table[("F", "PME")]["turnover"] == pytest.approx(200.0 - 40.0 - 150.0)
    assert table[("F", "PME")]["result"] == pytest.approx(20.0 - 3.0 - 16.0)


def test_two_suppressed_classes_are_left_alone(esane: Path) -> None:
    """One equation, two unknowns. Splitting the difference between them would be
    inventing a number and calling it published."""
    table = C.read_esane(esane)
    assert table[("G", "PME")]["turnover"] is None
    assert table[("G", "ETI_GE")]["turnover"] is None


def test_an_unknown_category_is_refused(tmp_path: Path) -> None:
    """A relabelled category must stop the build, not fall through as a new class."""
    path = write_esane(tmp_path / "odd.xlsx",
                       [("a21", "C", "Entreprises moyennes (nouveau libellé)", 1, 1, 1, 1)])
    with pytest.raises(C.CellBuildError, match="unknown Ésane category"):
        C.read_esane(path)


def test_a_missing_file_says_what_to_run(tmp_path: Path) -> None:
    with pytest.raises(C.CellBuildError, match="not found"):
        C.read_esane(tmp_path / "absent.xlsx")


# --------------------------------------------------------------------------- #
# the split and the dispersion, which are the invented-looking steps
# --------------------------------------------------------------------------- #
#: A published split, shaped like Focus 372 figures 3a/3b/3c. Turnover and value
#: added deliberately disagree: ETI and GE have different VA/CA ratios, so one share
#: cannot carry both.
PUBLISHED_SPLIT = {
    "Industrie": {
        "ETI": {"n": 90.0, "turnover": 476.2e3, "value_added": 122.0e3},
        "GE": {"n": 10.0, "turnover": 838.0e3, "value_added": 168.7e3},
    },
}


def test_the_split_uses_each_published_share_for_its_own_quantity() -> None:
    """Turnover takes figure 3b's share and value added takes 3c's. An earlier version
    estimated both from national mean turnover per firm and was out by up to 7 points
    on turnover and 12 on value added — against a table in the same workbook."""
    merged = {"n": 100.0, "turnover": 1000.0, "value_added": 300.0, "result": 100.0}
    split = C._split_eti_ge("C", merged, PUBLISHED_SPLIT)
    assert split is not None
    assert split["ETI"]["n"] == pytest.approx(90.0)
    assert split["GE"]["n"] == pytest.approx(10.0)
    ge_turnover = 838.0 / (476.2 + 838.0)
    ge_value_added = 168.7 / (122.0 + 168.7)
    assert split["GE"]["turnover"] == pytest.approx(1000.0 * ge_turnover)
    assert split["GE"]["value_added"] == pytest.approx(300.0 * ge_value_added)
    assert ge_turnover != pytest.approx(ge_value_added), (
        "the fixture must keep the two shares distinct, or this proves nothing"
    )


def test_result_borrows_the_value_added_share_because_none_is_published() -> None:
    """The one assumption left in the split, pinned so it stays visible."""
    merged = {"n": 100.0, "turnover": 1000.0, "value_added": 300.0, "result": 100.0}
    split = C._split_eti_ge("C", merged, PUBLISHED_SPLIT)
    assert split is not None
    assert split["GE"]["result"] / 100.0 == pytest.approx(
        split["GE"]["value_added"] / 300.0
    )


def test_the_split_conserves_every_quantity() -> None:
    """Whatever the shares, the two halves must add back to the published cell."""
    merged = {"n": 40.0, "turnover": 500.0, "value_added": 120.0, "result": 33.0}
    split = C._split_eti_ge("C", merged, PUBLISHED_SPLIT)
    assert split is not None
    for quantity, total in (("n", 40.0), ("turnover", 500.0), ("value_added", 120.0),
                            ("result", 33.0)):
        assert split["ETI"][quantity] + split["GE"][quantity] == pytest.approx(total)


def test_the_split_declines_rather_than_guessing() -> None:
    """A suppressed count, or a section with no published ETI/GE mix, returns nothing
    — the cells are dropped and listed, not filled in."""
    assert C._split_eti_ge("C", {"n": None}, PUBLISHED_SPLIT) is None
    assert C._split_eti_ge("C", {"n": 10.0}, {}) is None


def test_the_champ_haircut_follows_the_distribution_not_the_headcount() -> None:
    """Half of Ésane's micro-enterprises are not liable to IS, but they are the
    *smallest* half. Under the lognormal this module fits to that class, the smallest
    half holds a couple of percent of turnover — scaling value by headcount instead
    removed 334 bn of it."""
    assert C._top_share_of_total(0.51, 3.0) > 0.99
    assert C._top_share_of_total(0.51, 0.0) == pytest.approx(0.51, abs=0.01)
    assert C._top_share_of_total(1.0, 2.0) == 1.0
    assert C._top_share_of_total(0.0, 2.0) == 0.0
    # Monotone in sigma: the fatter the tail, the less the small firms carry.
    shares = [C._top_share_of_total(0.5, sigma) for sigma in (0.5, 1.0, 2.0, 3.0)]
    assert shares == sorted(shares)


def test_a_negative_cell_result_does_not_zero_a_sector() -> None:
    """Ésane's résultat is net of the cell's own loss-makers, so a cell can publish a
    negative aggregate while containing profitable firms. Flooring it at zero gave a
    taxable base of exactly zero to 8 057 information-and-communication PMEs turning
    over 46.8 bn, and to the whole of real-estate ETI and GE."""
    if not HAVE_PRIMARY:
        pytest.skip("needs the primary spreadsheets")
    table, _ = C.build_cells()
    by_key = {(cell.naf_section, cell.taille): cell for cell in table}
    for key in (("J", "PME"), ("L", "ETI"), ("L", "GE")):
        assert key in by_key, f"{key} vanished from the table"
        assert by_key[key].result_total > 0, (
            f"{key} carries no taxable profit at all, which is what the loss "
            f"add-back exists to prevent"
        )


def test_sigma_is_the_lognormal_fit_to_the_published_quartiles(tmp_path: Path) -> None:
    """sigma = ln(Q3/Q1) / (2 x 0.6745). Checked against a lognormal whose sigma is
    known, so the test fails if the constant or the formula drifts."""
    sigma = 0.8
    q1, q3 = math.exp(-0.6745 * sigma), math.exp(0.6745 * sigma)
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Tableau complémentaire 3"
    for _ in range(4):
        sheet.append([None])
    sheet.append(["Industrie", q1, 1.0, q3, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    path = tmp_path / "focus.xlsx"
    workbook.save(path)
    assert C.read_focus_dispersion(path)[("Industrie", "micro")] == pytest.approx(sigma)


def test_a_degenerate_quartile_pair_yields_no_sigma(tmp_path: Path) -> None:
    """A published first quartile of zero — common for micro-enterprises — carries no
    information about spread. Better no sigma than an infinite one."""
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Tableau complémentaire 3"
    for _ in range(4):
        sheet.append([None])
    sheet.append(["Industrie", 0, 5, 54, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    path = tmp_path / "focus.xlsx"
    workbook.save(path)
    assert ("Industrie", "micro") not in C.read_focus_dispersion(path)


# --------------------------------------------------------------------------- #
# the real files
# --------------------------------------------------------------------------- #
@needs_primary
def test_the_table_reproduces_the_published_firm_count() -> None:
    """The IS population is 2 718 376 firms. The build lands on it by construction —
    this is the identity that says the champ mapping ran, not evidence about France."""
    _, provenance = C.build_cells()
    assert provenance.is_liable_firms == pytest.approx(2_718_376, rel=1e-4)


@needs_primary
def test_only_the_micro_class_is_scaled_to_the_fiscal_champ() -> None:
    """DGFiP's size buckets are not INSEE's, so scaling class by class would produce
    ratios above one and invent firms. Companies of PME size and up are liable to IS
    by legal form, so the whole adjustment lands on micro-enterprises."""
    _, provenance = C.build_cells()
    assert provenance.is_share_by_size["micro"] < 1.0
    for size in ("PME", "ETI", "GE"):
        assert provenance.is_share_by_size[size] == 1.0


@needs_primary
def test_the_fiscal_ratio_is_computed_and_reproduces_published_profits() -> None:
    """D-024 set the IS tolerance wide because this scalar was free. It is derived
    now, and the identity it is derived from is the test."""
    table, provenance = C.build_cells()
    implied = sum(cell.result_total for cell in table) * provenance.fiscal_to_accounting
    assert implied == pytest.approx(283.950641563e9, rel=1e-6)
    assert 0.0 < provenance.fiscal_to_accounting < 2.0


@needs_primary
def test_no_cell_survives_with_firms_but_no_turnover() -> None:
    """Ésane can publish a count while suppressing the value. Carrying such a cell
    puts firms with no turnover into the population — they pay nothing, drag the
    effective-rate profile toward zero, and divide by zero on the way."""
    table, provenance = C.build_cells()
    assert all(cell.turnover_total > 0 for cell in table)
    assert any("turnover suppressed" in entry for entry in provenance.suppressed_cells)


@needs_primary
def test_every_cell_is_internally_plausible() -> None:
    table, _ = C.build_cells()
    assert table, "the primary files produced no cells at all"
    for cell in table:
        assert cell.n_firms > 0
        assert cell.turnover_total > 0
        assert cell.value_added_total >= 0
        assert cell.result_total >= 0
        assert 0.0 <= cell.p_loss < 1.0
        assert cell.taille in C.SIZES
        assert cell.sigma is None or 0.0 < cell.sigma < 10.0


@needs_primary
def test_the_dispersion_is_fitted_for_most_cells_rather_than_assumed() -> None:
    """The population's fallback sigma of 1.4 was a declared assumption. The fitted
    values run from roughly 0.7 to 3.1, so a single constant was wrong in both
    directions at once — most visibly at the CEBGE thresholds, where too fat a tail
    invents firms above 1.5 bn of turnover."""
    table, _ = C.build_cells()
    fitted = [cell.sigma for cell in table if cell.sigma is not None]
    assert len(fitted) > 0.8 * len(table)
    assert min(fitted) < 1.0 < max(fitted)


@needs_primary
def test_the_p_loss_gap_is_declared_in_the_provenance() -> None:
    """The one figure in this table not computed from a machine-readable file. It has
    to be findable as such, or it looks like all the others."""
    _, provenance = C.build_cells()
    assert provenance.p_loss_by_size == C.P_LOSS_BY_SIZE
    assert "non calculé" in provenance.p_loss_source
