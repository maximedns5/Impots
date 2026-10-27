"""Phase 9 M5 — the labour-supply channel C7, reopened on the paper's cells (D-220).

What is held here: the France cells are read off Bargain, Orsini and Peichl's annex F by
their header, never by position, and each row inside its own block, never past it; the
store's four rows are the stated convention applied to those cells, to the digit; C7 opens
for the CSG on earnings and for nothing the income tax's C1 already prices; its arithmetic
is the hand-derived example; and the population's earners are put in the paper's groups,
household by household, or counted outside them, not guessed in.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots.behavioural import band, bop, channels, labour
from impots.behavioural.store import (
    Parameter,
    Source,
    Store,
    Support,
    Verifier,
)
from impots.behavioural.store import load as load_store

STORE = load_store()


class Reform:
    """A reform reduced to the knobs it sets, as `channels._knobs` reads them."""

    def __init__(self, **knobs) -> None:
        self._knobs = knobs

    def model_dump(self, exclude_none: bool = True, **_) -> dict:
        return dict(self._knobs)


CSG = Reform(csg_activite_deductible=0.078)
IR = Reform(ir_bareme=[{"threshold": 0, "rate": 0.0}])


def _paper() -> dict:
    pytest.importorskip("pypdf")
    if not (bop.RAW / bop.SOURCE_FILE).exists():
        pytest.skip("data/raw/ n'a pas l'article de Bargain, Orsini et Peichl — les sources "
                    "primaires ne sont pas versionnées")
    return bop.load()


# --------------------------------------------------------------------------- #
# Reading the paper
# --------------------------------------------------------------------------- #
#: (group, year, block) → (estimate, standard error, PDF page) of « Total hours », read by
#: eye off tables F.1, F.3, F.5 and F.7, columns FR 98 and FR 01; the cross-wage block
#: exists in the couples' tables only.
TOTAL_HOURS = {
    ("femmes_en_couple", "98", "own"): (0.23, 0.02, 67),
    ("femmes_en_couple", "01", "own"): (0.13, 0.01, 67),
    ("femmes_en_couple", "98", "cross"): (-0.11, 0.01, 67),
    ("femmes_en_couple", "01", "cross"): (-0.07, 0.02, 67),
    ("hommes_en_couple", "98", "own"): (0.09, 0.01, 69),
    ("hommes_en_couple", "01", "own"): (0.06, 0.01, 69),
    ("hommes_en_couple", "98", "cross"): (-0.01, 0.00, 69),
    ("hommes_en_couple", "01", "cross"): (-0.01, 0.00, 69),
    ("femmes_seules", "98", "own"): (0.18, 0.04, 71),
    ("femmes_seules", "01", "own"): (0.12, 0.02, 71),
    ("hommes_seuls", "98", "own"): (0.14, 0.04, 73),
    ("hommes_seuls", "01", "own"): (0.14, 0.03, 73),
}


def test_the_france_cells_are_the_ones_printed_in_annex_f() -> None:
    """Pinned by eye, not by the reader: FI 98, the column beside FR 98 in table F.1,
    prints 0,13 for married women where France prints 0,23 — a reader one column off
    would hand back the 2001 value for 1998 and nobody would see it."""
    cells = _paper()
    for (group, year, block), (estimate, se, page) in TOTAL_HOURS.items():
        cell = cells[(group, year, block, "Total hours")]
        assert (cell.estimate, cell.se, cell.page) == (estimate, se, page), (group, year)
    assert not any(k[2] == "cross" for k in cells if k[0] in ("femmes_seules", "hommes_seuls"))
    # Rows are found by label, not by rank: the intensive margin is its own line.
    assert cells[("femmes_en_couple", "98", "own", "Intensive margin (hour)")].estimate == 0.03


def test_the_columns_are_found_by_their_header_wherever_france_sits() -> None:
    """GUARD. A table where France has moved one column left: the columns come from the
    country row and the year row, so the reader follows. A reader that knew France was
    the sixth and seventh column would read Finland's figure and Denmark's."""
    lines = ("AT BE BE DK FR FR FI", "98 98 01 98 98 01 98")
    assert bop._france_columns(lines) == {"98": 4, "01": 5}
    with pytest.raises(bop.BopError, match="France"):
        bop._france_columns(("AT BE BE DK FI GR HU", "98 98 01 98 98 01 98"))


#: A singles' table, cut down: its own-wage block is titled « Wage elasticity », and every
#: block below has a « Total hours » line of its own.
SINGLES = ("AT BE", "98 01",
           "Wage elasticity",
           "Total hours .10 .20", "(.01) (.02)",
           "Own-wage elasticity (sub-groups)",
           "quintile 1 total hours .30 .40",
           "Income elasticity",
           "Total hours ­.0006 .0011", "(.0005) (.0004)")


def test_each_row_is_read_inside_its_block_and_never_past_it() -> None:
    """GUARD. A label is looked for between its block's title and the next title. Read
    from the first line that merely began with « Own-wage elasticity », a singles' table —
    whose own-wage block is titled « Wage elasticity » — would have been read from its
    sub-groups on, and its « Total hours » taken from the income elasticity."""
    assert bop._row(SINGLES, "Total hours") == ([0.10, 0.20], [0.01, 0.02])
    # A row missing from its block is missing, not borrowed from the next one.
    without = tuple(line for line in SINGLES
                    if not line.startswith(("Total hours .1", "(.01)")))
    with pytest.raises(bop.BopError, match="introuvable"):
        bop._row(without, "Total hours")
    with pytest.raises(bop.BopError, match="Cross-wage"):
        bop._row(SINGLES, "Total hours", "cross")
    # And a minus sign printed as a soft hyphen is a minus sign.
    assert bop._row(("Cross-wage elasticity", "Total hours ­.05 .20", "(.01) (.02)"),
                    "Total hours", "cross")[0] == [-0.05, 0.20]


def test_a_missing_paper_names_the_manifest_rather_than_returning_nothing(
        tmp_path: Path) -> None:
    with pytest.raises(bop.BopError, match="impots data fetch"):
        bop.load(tmp_path)


# --------------------------------------------------------------------------- #
# The four rows
# --------------------------------------------------------------------------- #
def test_the_convention_reproduces_the_hand_derived_married_women_row() -> None:
    """Derived by hand from table F.1. Own plus cross, per year:
        1998: 0,23 − 0,11 = 0,12, s.e. at most 0,02 + 0,01 = 0,03;
        2001: 0,13 − 0,07 = 0,06, s.e. at most 0,01 + 0,02 = 0,03.
    Two printed figures in each sum, so each is widened by 2 × 0,005 = 0,01:
        low  = 0,06 − 0,01 − 1,96 × (0,03 + 0,01) = −0,0284 (2001),
        high = 0,12 + 0,01 + 1,96 × (0,03 + 0,01) = 0,2084 (1998),
    centre the mean of the two years, 0,09 — beside the paper's own pooled estimate of
    the own-wage term alone, 0,17 against a mean of 0,18 (table G.1)."""
    cells = {(g, y, b, "Total hours"): bop.Cell(g, y, b, "Total hours", e, se, 67)
             for (g, y, b), (e, se, _) in TOTAL_HOURS.items()}
    assert bop.convention(cells, "femmes_en_couple") == bop.Range(-0.0284, 0.09, 0.2084)
    # A single's row has no cross term and one rounding per figure.
    assert bop.convention(cells, "hommes_seuls") == bop.Range(
        low=round(0.14 - 0.005 - 1.96 * 0.045, 10), central=0.14,
        high=round(0.14 + 0.005 + 1.96 * 0.045, 10))


@pytest.mark.parametrize("group, key", sorted(channels.LABOUR_GROUPS.items()))
def test_each_row_is_the_convention_applied_to_the_paper_cells(group: str, key: str) -> None:
    """The store against the PDF, through the convention: a retyped digit in the YAML, or
    a cell the reader stopped finding, fails here."""
    expected = bop.convention(_paper(), group)
    row = STORE[key]
    assert (row.low, row.central, row.high) == (expected.low, expected.central,
                                                expected.high)


def test_the_rows_price_the_csg_on_earnings_and_never_the_income_tax() -> None:
    """GUARD. C1's taxable-income elasticity already carries the hours an income-tax
    change moves; C7 claiming the IR too would count them twice. And no other row may
    claim the CSG on earnings, or the same euro would be priced by two channels."""
    for key in channels.C7_KEYS:
        assert STORE[key].claims("csg_activite_deductible"), key
        assert STORE[key].claims("csg_activite_imposable"), key
        for knob in ("ir_bareme", "decote_taux", "plafond_qf_demi_part"):
            assert not STORE[key].claims(knob), (key, knob)
    for knob in ("csg_activite_deductible", "csg_activite_imposable"):
        assert sorted(p.key for p in STORE.for_knob(knob)) == sorted(channels.C7_KEYS)


def test_labour_supply_is_a_channel_with_its_theta_and_no_longer_a_closed_one() -> None:
    """A closed channel's reason is shown on every trajectory: « aucune ligne vérifiée au
    magasin » left there beside four verified rows would be false on its face."""
    from impots.predictif import chaine

    assert "offre de travail" not in chaine.CLOSED
    assert all(STORE[key].is_open and STORE[key].theta_one == "high"
               for key in channels.C7_KEYS)


# --------------------------------------------------------------------------- #
# C7's arithmetic, against the hand-derived example
# --------------------------------------------------------------------------- #
def _fixed(**values: float) -> Store:
    """The four rows, each fixed at one value, so a draw is that value."""
    def row(key: str, value: float) -> Parameter:
        return Parameter(
            key=key, central=value, low=value, high=value, applies_to="test",
            support=Support(estimated_on="test", max_variation_graded_in_support=0.10),
            source=Source(citation="test"), verifier=Verifier(verdict="CONFIRMED"),
            responds_to_knobs=("csg_activite_*",))
    return Store(parameters={key: row(key, values.get(group, 0.0))
                             for group, key in channels.LABOUR_GROUPS.items()})


def _people(**overrides) -> dict:
    people = {
        "labour_group": np.array(["femmes_en_couple", "hommes_seuls", labour.OUTSIDE]),
        "labour_earnings": np.array([30_000.0, 20_000.0, 25_000.0]),
        "labour_delta_log_net": np.array([0.01, 0.01, 0.01]),
        "labour_weights": np.array([1.0, 1.0, 1.0]),
        "labour_emtr": np.array([0.40, 0.30, 0.50]),
    }
    return {**people, **overrides}


def test_c7_reproduces_the_worked_example() -> None:
    """Derived by hand. A woman in a couple earning 30 000 EUR whose net wage rises 1 %
    (Δln = 0,01), at the row's centre of 0,09, earns 30 000 × 0,09 × 0,01 = 27 EUR more;
    at a marginal rate of 40 %, 10,80 EUR come back. A single man earning 20 000 EUR at
    0,14: 28 EUR more, 8,40 EUR at 30 %. Together 55 EUR of earnings and 19,20 EUR of
    receipts. The adult child earning 25 000 EUR is outside the paper's sample: priced at
    nothing, and counted — 25 000 of 75 000 EUR of earnings, a third."""
    store = _fixed(femmes_en_couple=0.09, hommes_seuls=0.14)
    result = channels.labour_supply(store, CSG, draws=1, rng=np.random.default_rng(0),
                                    **_people())
    assert result.applies and result.in_revenue_band
    assert result.draws[0] == pytest.approx(10.80 + 8.40, abs=1e-9)
    assert result.diagnostics["gross_earnings_change_eur"] == pytest.approx(55.0)
    assert result.diagnostics["persons_outside_the_sample"] == 1
    assert result.diagnostics["earnings_outside_the_sample_share"] == pytest.approx(0.3333)
    assert result.diagnostics["persons_by_group"]["femmes_en_couple"] == 1


def test_c7_does_not_open_for_an_income_tax_reform() -> None:
    result = channels.labour_supply(STORE, IR, draws=1, rng=np.random.default_rng(0),
                                    **_people())
    assert not result.applies and result.message == channels.NO_LABOUR_KNOB


def test_c7_without_its_inputs_says_so_and_with_empty_ones_raises() -> None:
    """The Phase 1 distinction: not computed is a sentence; promised and empty is a
    defect, and raises."""
    store = _fixed(femmes_en_couple=0.09)
    quiet = channels.labour_supply(store, CSG)
    assert not quiet.applies and quiet.message.startswith("Non calculé")
    with pytest.raises(channels.ChannelInputMissing, match="labour_emtr"):
        channels.labour_supply(store, CSG, draws=1, rng=np.random.default_rng(0),
                               **_people(labour_emtr=np.array([])))


def test_a_net_wage_move_past_ten_percent_is_graded_an_extrapolation() -> None:
    """The paper checks 1 % against 10 % and finds them alike; past 10 % the row
    extrapolates and the band says so. A FALL of 15 %, as a CSG rise gives: the metric is
    the size of the move, not its signed value."""
    store = _fixed(femmes_en_couple=0.09, hommes_seuls=0.14)
    inside = band.compute(mechanical=-1e9, reform=CSG, store=store, draws=50, **_people())
    outside = band.compute(mechanical=-1e9, reform=CSG, store=store, draws=50,
                           **_people(labour_delta_log_net=np.array([-0.15, -0.15, -0.15])))
    assert inside.grade == "in-support"
    assert outside.grade == "illustrative"


# --------------------------------------------------------------------------- #
# The population, in the paper's groups
# --------------------------------------------------------------------------- #
def _frame() -> pl.DataFrame:
    employed, inactive = "employed", "inactive"
    rows = [
        # household, role, sex, age, gross wage, pension, status, employee
        ("A", "personne_de_reference", "female", 40, 30_000.0, 0.0, employed, True),
        ("A", "conjoint", "male", 42, 35_000.0, 0.0, employed, True),
        ("A", "enfant", "female", 22, 12_000.0, 0.0, employed, True),
        ("B", "personne_de_reference", "male", 30, 20_000.0, 0.0, employed, True),
        ("C", "personne_de_reference", "female", 61, 25_000.0, 0.0, employed, True),
        ("D", "personne_de_reference", "female", 35, 0.0, 0.0, inactive, False),
        ("E", "personne_de_reference", "female", 50, 28_000.0, 0.0, employed, True),
        ("E", "enfant", "male", 12, 0.0, 0.0, "student", False),
        ("F", "personne_de_reference", "male", 45, 0.0, 0.0, inactive, False),
        ("F", "conjoint", "female", 44, 18_000.0, 0.0, employed, True),
        ("G", "personne_de_reference", "male", 58, 40_000.0, 0.0, employed, True),
        ("G", "conjoint", "female", 63, 0.0, 14_000.0, inactive, False),
        ("H", "personne_de_reference", "female", 38, 22_000.0, 0.0, employed, True),
        ("H", "conjoint", "male", 39, 0.0, 0.0, employed, False),
    ]
    columns = ("household_id", "role_menage", "sex", "age", "salaire_brut_annuel",
               "pension_annuelle", "statut_activite", "is_salarie")
    # One weight per household, as most of the frame has: the subsample's then is each
    # member's (D-258).
    return pl.DataFrame({"person_id": list(range(1, len(rows) + 1)),
                         **{c: [r[i] for r in rows] for i, c in enumerate(columns)},
                         "weight": [1.0] * len(rows)})


def test_earners_are_put_in_the_papers_groups_or_counted_outside_them() -> None:
    """A partner makes a couple whether or not the partner earns (F); a reference person
    alone with a child is single (E); an adult child is neither, and stays outside (A);
    a 61-year-old is past the paper's band (C); a non-earner contributes nothing (D).
    And the sample is one of HOUSEHOLDS: a 58-year-old employee whose wife is 63 and
    retired (G), or one whose husband is self-employed (H), is in a household the paper
    did not keep — outside, though each of them alone would pass."""
    assigned = dict(zip(labour.groups(_frame())["person_id"].to_list(),
                        labour.groups(_frame())["group"].to_list(), strict=True))
    assert assigned == {1: "femmes_en_couple", 2: "hommes_en_couple", 3: labour.OUTSIDE,
                        4: "hommes_seuls", 7: "femmes_seules", 10: "femmes_en_couple",
                        11: labour.OUTSIDE, 13: labour.OUTSIDE}


def test_the_inputs_carry_the_subsample_weight_and_the_households_rate() -> None:
    households = pl.DataFrame({"household_id": ["A", "B", "E"], "weight": [10.0, 20.0, 30.0],
                               "emtr_reform": [0.4, 0.3, 0.5]})
    arrays = labour.inputs(_frame(), households, delta_log_net=-0.01)
    assert arrays["labour_group"].tolist() == ["femmes_en_couple", "hommes_en_couple",
                                               labour.OUTSIDE, "hommes_seuls",
                                               "femmes_seules"]
    assert arrays["labour_weights"].tolist() == [10.0, 10.0, 10.0, 20.0, 30.0]
    assert arrays["labour_emtr"].tolist() == [0.4, 0.4, 0.4, 0.3, 0.5]
    assert np.all(arrays["labour_delta_log_net"] == -0.01)


def test_each_member_keeps_the_weight_the_subsample_gives_them() -> None:
    """D-258. The EMTR pass weighs a household at its members' mean, and the subsample
    scales every member by the same factor. In A, weights 1,2, 0,9 and 0,9 in the frame,
    mean 1, at 10 in the pass: 12, 9 and 9, what the subsampled frame carries. The
    household's 10 for each, as C7 first took it, counts the first a sixth too few."""
    frame = _frame().with_columns(
        pl.when(pl.col("person_id") == 1).then(1.2)
        .when(pl.col("person_id").is_in([2, 3])).then(0.9)
        .otherwise(pl.col("weight")).alias("weight"))
    households = pl.DataFrame({"household_id": ["A", "B", "E"], "weight": [10.0, 20.0, 30.0],
                               "emtr_reform": [0.4, 0.3, 0.5]})
    arrays = labour.inputs(frame, households, delta_log_net=-0.01)
    assert arrays["labour_weights"] == pytest.approx([12.0, 9.0, 9.0, 20.0, 30.0])


def test_the_persons_weigh_what_they_weigh_in_the_subsampled_frame() -> None:
    """Against `runner.subsample` itself, on weights unequal inside households: C7's
    persons are those of the subsampled frame, at its weights."""
    from impots.population.runner import subsample

    rng = np.random.default_rng(7)
    base = _frame()
    frames = []
    for copy in range(40):
        frames.append(base.with_columns(
            (pl.col("person_id") + 100 * copy).alias("person_id"),
            (pl.col("household_id") + str(copy)).alias("household_id"),
            pl.Series("weight", rng.lognormal(3.0, 0.7) * rng.choice([0.8, 1.0, 1.25],
                                                                      size=base.height))))
    frame = pl.concat(frames)
    sub = subsample(frame, 60)
    households = (sub.group_by("household_id").agg(pl.col("weight").mean())
                  .with_columns(emtr_reform=pl.lit(0.3)))
    arrays = labour.inputs(frame, households, delta_log_net=-0.01)
    expected = labour.groups(sub).join(sub.select("person_id", "weight"), on="person_id")
    assert len(arrays["labour_weights"]) == expected.height
    assert float(arrays["labour_weights"].sum()) == pytest.approx(
        float(expected["weight"].sum()), rel=1e-12)
