"""The capital income the PFU taxes, imputed from DGFiP n° 41's fractiles (F1b, D-248).

What is held here: Tableau 2's hors-barème column is read with the CEHR stripped and the
nested top rows turned into disjoint bands, and refused when its means do not give back
the amounts printed below them; the base is the tax over the PFU rate the law carries;
the composition is the national 2042 boxes', whose total is the second route to the same
base; every foyer of a band gets the band's base; the imputation is opt-in, runs before
the niches, holds for 2024 only and is refused beside the top-tail rake; and a run with
it pays the PFU and the social levies on the base, on every year of the history.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots.population import capital, margins, top_tail

WORKBOOK_PRESENT = capital.WORKBOOK.exists()
BOXES_PRESENT = (capital.RAW / capital.DECLARATIONS_FILE).exists()
needs_workbook = pytest.mark.skipif(not WORKBOOK_PRESENT, reason="n° 41 absent de data/raw")
needs_boxes = pytest.mark.skipif(not BOXES_PRESENT, reason="cases 2042 absentes de data/raw")


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #
@needs_workbook
def test_the_hors_bareme_column_is_read_with_the_cehr_stripped() -> None:
    """Pinned by eye off Tableau 2: deciles 1-9 as printed, then the nested rows made
    disjoint — the 90-99 band (2 290 × 10 − 19 423) / 9, not the 2 290 + 476 a reader
    would take with the CEHR."""
    table = capital.published()
    assert [table.tax[label] for label, *_ in top_tail.BANDS[:9]] == [
        4, 6, 9, 11, 15, 18, 25, 36, 68]
    assert table.tax["90–99 %"] == pytest.approx((2290 * 0.1 - 19423 * 0.01) / 0.09)
    assert table.tax["99–99,9 %"] == pytest.approx((19423 * 0.01 - 135784 * 0.001) / 0.009)
    assert table.tax["99,9–100 %"] == 135784
    assert (table.total_eur, table.cehr_eur) == (pytest.approx(10.32e9),
                                                 pytest.approx(1.98e9))


@pytest.mark.parametrize("cell, expected", [
    ("2 290  (+ 476)", (2290.0, 476.0)), ("10,32 (+ 1,98)", (10.32, 1.98)),
    ("135\u00a0784 (+\u202f45 366)", (135784.0, 45366.0)), (68, (68.0, 0.0)),
])
def test_a_cell_is_split_into_the_tax_and_the_cehr(cell, expected) -> None:
    assert capital._split(cell) == expected


def test_a_cell_without_its_cehr_is_refused() -> None:
    with pytest.raises(capital.CapitalImputationError, match="CEHR entre parenthèses"):
        capital._split("2 290")


def _workbook(tmp_path: Path, **override: object) -> Path:
    """A Tableau 2 carrying only the cells the reader takes, as n° 41 prints them."""
    import openpyxl

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Tableau 2"
    labels = ["1er dixième", *(f"{i}e  dixième" for i in range(2, 10)), "dernier  dixième",
              "dont dernier  centième", "dont dernier  millième"]
    values = [4, 6, 9, 11, 15, 18, 25, 36, 68, "2 290  (+ 476)", "19 423  (+ 4 754)",
              "135 784  (+ 45 366)"]
    for row, (label, value) in enumerate(zip(labels, values, strict=True), capital.FIRST_ROW):
        sheet.cell(row, capital.LABEL_COLUMN, label)
        sheet.cell(row, capital.TAX_COLUMN, override.get(label, value))
    sheet.cell(capital.TOTAL_ROW, capital.TAX_COLUMN, override.get("total", "10,32 (+ 1,98)"))
    for (label, row), amount in zip(capital.AMOUNT_ROWS.items(),
                                    ("9,53 (+ 1,98)", "8,08 (+ 1,98)", "5,65 (+ 1,89)"),
                                    strict=True):
        sheet.cell(row, capital.TAX_COLUMN, override.get(f"montant {label}", amount))
    path = tmp_path / "n41.xlsx"
    book.save(path)
    return path


def test_the_built_table_reads_like_the_real_one(tmp_path: Path) -> None:
    assert capital.published(_workbook(tmp_path)).tax["99,9–100 %"] == 135784


@pytest.mark.parametrize("override, needle", [
    ({"montant dont dernier millième": "7,65 (+ 1,89)"}, "ne se recoupe pas"),
    ({"dont dernier  centième": "1 000  (+ 4 754)"}, "bande négative"),
    ({"dernier  dixième": "2 290"}, "CEHR entre parenthèses"),
], ids=["montant-faux", "emboitement-impossible", "sans-cehr"])
def test_a_table_that_does_not_hold_together_is_refused(tmp_path, override, needle) -> None:
    with pytest.raises(capital.CapitalImputationError, match=needle):
        capital.published(_workbook(tmp_path, **override))


def test_a_table_missing_a_row_or_a_file_is_refused(tmp_path: Path) -> None:
    import openpyxl

    path = _workbook(tmp_path)
    book = openpyxl.load_workbook(path)
    book["Tableau 2"].cell(capital.FIRST_ROW + 4, capital.LABEL_COLUMN, "autre chose")
    book.save(path)
    with pytest.raises(capital.CapitalImputationError, match="introuvables"):
        capital.published(path)
    with pytest.raises(capital.CapitalImputationError, match="introuvable"):
        capital.published(tmp_path / "absent.xlsx")


# --------------------------------------------------------------------------- #
# The base, its composition, and the second route
# --------------------------------------------------------------------------- #
def test_the_pfu_rate_is_the_laws() -> None:
    assert capital.pfu_rate(2024) == pytest.approx(0.128)


def test_the_base_is_the_tax_over_the_rate_and_a_rate_outside_is_refused() -> None:
    table = capital.Published(tax={"a": 12.8, "b": 128.0}, total_eur=1.0, cehr_eur=0.0)
    assert capital.bases(table, 0.128) == {"a": pytest.approx(100.0),
                                           "b": pytest.approx(1000.0)}
    for rate in (0.0, 1.0):
        with pytest.raises(capital.CapitalImputationError, match="ne se dérive pas"):
            capital.bases(table, rate)


@needs_boxes
@needs_workbook
def test_the_boxes_split_the_base_and_their_total_is_the_second_route() -> None:
    """The four 2042 boxes sum to 80,69 bn; n° 41's column over 12,8 % gives 80,63 bn.
    Two routes, 0,1 % apart (gate, § 1)."""
    shares = capital.composition()
    assert set(shares) == set(capital.CASES) and sum(shares.values()) == pytest.approx(1.0)
    assert shares["f2dc"] == pytest.approx(0.621, abs=0.001)
    boxes = capital.national_boxes_eur()
    derived = capital.published().total_eur / capital.pfu_rate()
    assert boxes == pytest.approx(80.69e9, rel=1e-3)
    assert abs(boxes / derived - 1.0) < 0.002
    assert margins.CAPITAL_BOXES_2042.value == pytest.approx(boxes, rel=1e-3)


def test_a_box_missing_from_the_declarations_is_refused(tmp_path: Path) -> None:
    (tmp_path / capital.DECLARATIONS_FILE).write_text(
        "Année;Libellé;Nom;Nombre;Montant\n2024;x;2DC;1;10\n2024;x;2TR;1;10\n",
        encoding="utf-8")
    with pytest.raises(capital.CapitalImputationError, match="absentes"):
        capital.composition(tmp_path)


# --------------------------------------------------------------------------- #
# The imputation
# --------------------------------------------------------------------------- #
def test_the_bands_are_weighted_ranks() -> None:
    per_part = np.arange(1000, dtype=float)[::-1]
    index = capital.bands(per_part, np.ones(1000))
    assert (index[per_part < 100] == 0).all() and (index[per_part >= 999] == 11).all()
    assert (index == 10).sum() == 9 and (index == 9).sum() == 90


@needs_boxes
@needs_workbook
def test_every_foyer_of_a_band_gets_its_base_in_the_national_shares() -> None:
    rng = np.random.default_rng(1)
    per_part, weights = rng.lognormal(10, 1, 100_000), np.full(100_000, 400.0)
    cases = capital.impute(per_part, weights)
    total = sum(cases.values())
    index = capital.bands(per_part, weights)
    expected = capital.bases(capital.published(), capital.pfu_rate())
    for band, (label, *_) in enumerate(top_tail.BANDS):
        assert np.allclose(total[index == band], expected[label]), label
    shares = capital.composition()
    assert np.allclose(cases["f2dc"], total * shares["f2dc"])
    mean = capital.imputed_total(cases, weights) / weights.sum()
    # n° 41's mean per foyer, its own total over its own foyers (≈ 41,58 M).
    assert mean == pytest.approx(capital.published().total_eur / 0.128 / 41.58e6, rel=1e-3)


def test_a_foyer_outside_every_band_is_refused() -> None:
    """A foyer of zero weight at the bottom ranks nowhere: refused, not dropped."""
    weights = np.ones(100)
    weights[0] = 0.0
    with pytest.raises(capital.CapitalImputationError, match="hors de toute bande"):
        capital.impute(np.arange(100, dtype=float), weights)


def test_another_year_and_mismatched_shapes_are_refused() -> None:
    with pytest.raises(capital.CapitalImputationError, match="vieillir l'assiette"):
        capital.impute(np.ones(3), np.ones(3), year=2026)
    with pytest.raises(capital.CapitalImputationError, match="diffèrent"):
        capital.impute(np.ones(3), np.ones(2))


# --------------------------------------------------------------------------- #
# The runner
# --------------------------------------------------------------------------- #
def test_the_imputation_is_off_by_default_and_runs_before_the_niches() -> None:
    import inspect

    from impots.population.runner import run

    assert inspect.signature(run).parameters["impute_capital"].default is False
    source = Path("src/impots/population/runner.py").read_text(encoding="utf-8")
    body = source[source.index("def run("):]
    assert body.index("if impute_capital:\n        started") < body.index("if impute_niches:")


@pytest.mark.parametrize("kwargs, needle", [
    ({"year": 2026}, "vieillir l'assiette"),
    ({"rake_top_tail": True}, "5,4 %"),
], ids=["autre-annee", "avec-le-recalage"])
def test_the_runner_refuses_before_any_pass(monkeypatch, kwargs, needle) -> None:
    from impots.population import runner

    def no_pass(*args, **kw):
        raise AssertionError("aucune passe ne devait tourner")

    monkeypatch.setattr(runner, "build_simulation", no_pass)
    with pytest.raises(ValueError, match=needle):
        runner.run(pl.DataFrame({"person_id": [1]}), impute_capital=True,
                   **{"year": 2024, **kwargs})


@pytest.fixture(scope="module")
def fixture_population() -> pl.DataFrame:
    """The 400-dwelling fixture, built as `tests/test_population.py` builds it."""
    from impots.population.incomes import attach_incomes, household_share_of_france
    from impots.population.skeleton import build_skeleton

    source = Path(__file__).parent / "fixtures" / "eec_sample.parquet"
    children = {k: np.array(v) for k, v in margins.CHILDREN_PER_FAMILY.items()}
    frame, _ = build_skeleton(children_per_household=children, source=pl.read_parquet(source))
    frame, _ = attach_incomes(frame, targets_scale=household_share_of_france(frame))
    return frame


@needs_boxes
@needs_workbook
def test_a_run_with_it_pays_the_pfu_and_the_levies_on_the_base(fixture_population) -> None:
    """Every household owes the PFU (every foyer has a base), the social levies stand to
    it as 17,2 to 12,8, the RFR holds the base, and none of it exists without the flag."""
    from impots.population.runner import run

    plain = run(fixture_population, year=2024, tier="light").households
    assert plain["pfu"].sum() == 0 and plain["prelevements_sociaux_capital"].sum() == 0
    taxed = run(fixture_population, year=2024, tier="light", impute_capital=True).households
    assert (taxed["pfu"] > 0).all()
    ratio = taxed["prelevements_sociaux_capital"] / taxed["pfu"]
    assert np.allclose(ratio.to_numpy(), 0.172 / 0.128, rtol=1e-6)
    rfr_gain = (taxed["revenu_fiscal_reference"] - plain["revenu_fiscal_reference"]).to_numpy()
    pfu = taxed["pfu"].to_numpy()
    assert np.allclose(rfr_gain, pfu / 0.128, rtol=1e-6)
    assert ((taxed["ir"] - plain["ir"]).to_numpy() >= -1e-6).all()


def test_the_reform_pass_carries_the_capital_too(fixture_population) -> None:
    """A reform that does not touch capital leaves the PFU and the levies where they
    were: the reformed pass is given the same bases as the baseline's."""
    from impots.api.schemas import ReformSpec
    from impots.population.runner import run

    households = run(fixture_population, year=2024, tier="light", impute_capital=True,
                     reform=ReformSpec(decote_taux=0.40)).households
    for key in ("pfu", "prelevements_sociaux_capital"):
        assert households[key].sum() > 0
        assert np.allclose(households[f"{key}_reform"].to_numpy(),
                           households[key].to_numpy(), atol=0.01), key


def test_the_bands_rank_rfr_per_part_on_the_foyer_mean_weight(monkeypatch) -> None:
    """`_impute_capital` hands the imputation RFR over parts, and each foyer's MEAN
    member weight — the household convention of `run`; a sum would weight a foyer by its
    size and move every band boundary."""
    import types

    from impots.population import runner

    rfr, parts = np.array([30_000.0, 90_000.0]), np.array([1.0, 3.0])
    simulation = types.SimpleNamespace(
        calculate=lambda name, period: {"rfr": rfr, "nbptr": parts}[name])
    frame = pl.DataFrame({"foyer_id": ["a", "a", "b"], "weight": [100.0, 300.0, 50.0]})
    seen = {}

    def spy(per_part, weights, year):
        seen.update(per_part=per_part, weights=weights, year=year)
        return {}

    monkeypatch.setattr(capital, "impute", spy)
    runner._impute_capital(types.SimpleNamespace(simulation=simulation), frame, 2024)
    assert np.allclose(seen["per_part"], [30_000.0, 30_000.0])
    assert np.allclose(seen["weights"], [200.0, 50.0]) and seen["year"] == 2024


def test_the_income_tax_collects_the_pfu_except_under_the_collection_threshold(
        fixture_population) -> None:
    """At the foyer: a foyer already taxed pays the PFU on top, to the cent; one that paid
    nothing and owes 12,80 € of PFU still pays nothing, because the PFU is income tax and
    an income tax under 61 € is not collected. So the `pfu` row is the PFU owed, and
    the `ir` row what is collected of it."""
    from impots.engine.system import baseline
    from impots.population.to_openfisca import build_simulation

    n_foyers = fixture_population["foyer_id"].n_unique()
    plain = build_simulation(fixture_population, baseline(), 2024)
    taxed = build_simulation(fixture_population, baseline(), 2024,
                             capital_bases={"f2tr": np.full(n_foyers, 100.0)})
    before = -plain.simulation.calculate("impot_revenu_restant_a_payer", "2024")
    after = -taxed.simulation.calculate("impot_revenu_restant_a_payer", "2024")
    owed = taxed.simulation.calculate("prelevement_forfaitaire_unique_ir", "2024")
    assert np.allclose(owed, 12.8, atol=1e-3)
    rfr = taxed.simulation.calculate("rfr", "2024")
    already = (before > 100) & (rfr < 250_000)
    # openfisca computes in float32: a thousandth of a euro on a few hundred.
    assert already.any() and np.allclose(after[already] - before[already], 12.8, atol=0.01)
    # Untaxed, and still under the threshold once the PFU is added to what it owed.
    owed_before = plain.simulation.calculate("ip_net", "2024")
    untaxed = (before <= 0) & (owed_before + 12.8 < 61)
    assert untaxed.any() and np.allclose(after[untaxed], 0.0)


def test_the_capital_is_written_on_every_year_of_the_history(fixture_population) -> None:
    from impots.engine.system import baseline
    from impots.population.to_openfisca import HISTORY_YEARS, build_simulation

    n_foyers = fixture_population["foyer_id"].n_unique()
    bases = {"f2dc": np.full(n_foyers, 1000.0)}
    built = build_simulation(fixture_population, baseline(), 2024, capital_bases=bases)
    for offset in range(HISTORY_YEARS + 1):
        year = str(2024 - offset)
        assert np.allclose(built.simulation.calculate("f2dc", year), 1000.0), year
    niches = build_simulation(fixture_population, baseline(), 2024, niche_bases=bases)
    assert np.allclose(niches.simulation.calculate("f2dc", "2022"), 0.0)


# --------------------------------------------------------------------------- #
# The ledger
# --------------------------------------------------------------------------- #
def test_the_levies_are_a_receipt_and_the_pfu_is_not_counted_twice() -> None:
    from impots.engine import outputs
    from impots.guards import STATE_RECEIPTS

    keys = {row.key for row in outputs.REGISTRY}
    assert {"pfu", "prelevements_sociaux_capital"} <= keys
    assert "prelevements_sociaux_capital" in STATE_RECEIPTS
    assert "pfu" not in STATE_RECEIPTS


@needs_workbook
def test_the_target_is_registered_spent_and_is_what_the_table_says() -> None:
    assert margins.CAPITAL_PFU_BY_FRACTILE.use == "calibration"
    assert margins.CAPITAL_PFU_BY_FRACTILE.value == pytest.approx(
        capital.published().total_eur)
    assert "CAPITAL_PFU_BY_FRACTILE" in margins.IR_NET_YIELD.caveat


def test_the_net_yield_note_says_whether_the_pfu_was_imputed() -> None:
    from impots.population.reconcile import _net_yield_note

    assert "absent de notre côté" in _net_yield_note({})
    note = _net_yield_note({"pfu": 10.3e9})
    assert "imputé dans ce passage (10.3 md" in note and "absent" not in note
    with_niches = _net_yield_note({"pfu": 10.3e9, "reductions": 5e9})
    assert "calibrée elle aussi" in with_niches
