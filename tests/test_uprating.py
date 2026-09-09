"""F3 M2 — ageing the population, and losing its calibration by doing so.

The load-bearing test is `test_a_reconciliation_line_on_an_aged_population_refuses_a_verdict`:
the milestone is not finished until `reconcile` declines to say «within tolerance» for a
year whose published totals do not exist. Everything else here guards the arithmetic and
the three stated limits.
"""

from __future__ import annotations

import polars as pl
import pytest

from impots import uprating as up

HYPO = up.Uprating(wage=0.025, price=0.02,
                   source="2,5 % et 2 % ronds, déclarés, non prévus", base_year=2024)


def frame() -> pl.DataFrame:
    return pl.DataFrame({
        "person_id": [1, 2], "household_id": [1, 1], "weight": [100.0, 100.0],
        "age": [40, 70], "salaire_brut_annuel": [30_000.0, 0.0],
        "pension_annuelle": [0.0, 20_000.0], "chomage_annuel": [0.0, 0.0],
        "loyer_mensuel": [700.0, 700.0],
    })


# --------------------------------------------------------------------------- #
# The milestone's completion condition
# --------------------------------------------------------------------------- #


def test_a_reconciliation_line_on_an_aged_population_refuses_a_verdict():
    """THE condition F3 M2 is not finished without.

    An uprated population reproduces no published total, because there are none for a
    future year. A line comparing a simulated 2028 figure with a published 2024 one is
    not a loose comparison — the two numbers are about different things. Fails if the
    line returns any tolerance verdict, which a reader would take for validation.
    """
    from impots.reporting import Line

    aged = Line(label="Masse salariale", simulated=1.0e12, published=1.0e12,
                unit="EUR", source="INSEE", use="validation", tolerance=0.02,
                population_year=2028, comparator_year=2024)
    assert aged.status == "not comparable (population vieillie)"
    assert aged.passes is False


def test_the_refusal_does_not_touch_a_base_year_line():
    """The kill test for the refusal: refusing everything would prove nothing, and every
    existing reconciliation line must be unaffected."""
    from impots.reporting import Line

    base = dict(label="x", simulated=1.02e12, published=1.0e12, unit="EUR",
                source="INSEE", use="validation", tolerance=0.05)
    assert Line(**base).status == "within tolerance"
    assert Line(**base, population_year=2024, comparator_year=2024).status == (
        "within tolerance")


def test_a_mismatch_is_refused_before_the_tolerance_is_even_evaluated():
    """Fails if the vintage check moves below the tolerance test — a line that is
    numerically far off AND on the wrong year must report the vintage problem, because
    that is the one that makes the number meaningless rather than merely bad."""
    from impots.reporting import Line

    wild = Line(label="x", simulated=5.0e12, published=1.0e12, unit="EUR", source="s",
                use="validation", tolerance=0.02,
                population_year=2029, comparator_year=2024)
    assert wild.status == "not comparable (population vieillie)"


# --------------------------------------------------------------------------- #
# The arithmetic
# --------------------------------------------------------------------------- #


def test_wages_and_prices_move_on_their_own_indices():
    """Two indices, not one. Using a single index would quietly assume wages and prices
    move together: pensions and rents follow prices, salaries do not.

    Fails if a column is uprated on the wrong index — which compounds, so a 2029 figure
    would be wrong by several per cent without anything looking odd.
    """
    out = up.uprate(frame(), 2028, HYPO)
    wage_factor, price_factor = 1.025 ** 4, 1.02 ** 4
    assert out["salaire_brut_annuel"][0] == pytest.approx(30_000.0 * wage_factor)
    assert out["pension_annuelle"][1] == pytest.approx(20_000.0 * price_factor)
    assert out["loyer_mensuel"][0] == pytest.approx(700.0 * price_factor)


def test_the_base_year_is_returned_untouched():
    out = up.uprate(frame(), 2024, HYPO)
    assert out["salaire_brut_annuel"].to_list() == [30_000.0, 0.0]


def test_nothing_but_money_moves():
    """Structure, identities, ages and weights are frozen — limits 1 to 3 of the module.

    Fails if ageing starts advancing ages or reweighting, which would look like a better
    model and would be an unstated one: a population older by four years but with the
    same number of children is worse than a uniformly frozen one.
    """
    before, after = frame(), up.uprate(frame(), 2029, HYPO)
    for column in ("person_id", "household_id", "weight", "age"):
        assert before[column].to_list() == after[column].to_list(), column
    assert before.height == after.height


def test_every_money_column_is_uprated_or_named():
    """Fails when a money column is added to the population and not accounted for.

    A column left out of `UPRATED` shrinks in real terms every year, silently — a
    trajectory that slowly invents an impoverishment. `NOT_UPRATED` is where an
    exception must be justified rather than merely omitted.
    """
    from pathlib import Path

    path = Path("data/processed/population_2024.parquet")
    if not path.exists():
        pytest.skip("population non construite")
    columns = pl.read_parquet(path, n_rows=1).columns
    money = [c for c in columns
             if any(k in c for k in ("salaire", "pension", "chomage", "loyer",
                                     "revenu", "montant"))]
    accounted = set(up.UPRATED) | set(up.NOT_UPRATED)
    assert set(money) <= accounted, f"colonnes monétaires non traitées : {set(money) - accounted}"


# --------------------------------------------------------------------------- #
# The refusals
# --------------------------------------------------------------------------- #


def test_an_uprating_without_a_source_is_refused():
    with pytest.raises(up.UpratingError, match="prévision anonyme"):
        up.Uprating(wage=0.02, price=0.02, source="  ", base_year=2024)


@pytest.mark.parametrize("kwargs", [
    dict(wage=0.8, price=0.02), dict(wage=0.02, price=-0.9),
])
def test_an_implausible_index_is_refused(kwargs):
    with pytest.raises(up.UpratingError, match="taux annuel"):
        up.Uprating(source="s", base_year=2024, **kwargs)


def test_ageing_backwards_is_refused():
    """Rejuvenating is a different operation needing observed indices year by year, and
    a population not already calibrated on the arrival year. Fails if it silently
    divides instead."""
    with pytest.raises(up.UpratingError, match="rajeunir"):
        HYPO.factor("wage", 2020)


def test_a_missing_money_column_is_refused_rather_than_skipped():
    """Fails if `uprate` quietly skips a column it cannot find, which would age part of
    the population and leave the rest behind."""
    incomplete = frame().drop("pension_annuelle")
    with pytest.raises(up.UpratingError, match="colonnes absentes"):
        up.uprate(incomplete, 2028, HYPO)


def test_the_caveat_states_all_three_limits_and_the_lost_calibration():
    """These are invisible in the output, so they travel with every figure or they are
    not said at all."""
    text = up.caveat(2028, HYPO)
    assert "n'ont PAS bougé" in text
    assert "immobilité démographique" in text
    assert "n'est plus calibrée" in text
    assert "2,5" in text and "2,0" in text
    assert HYPO.source in text


# --------------------------------------------------------------------------- #
# The refusal, end to end through build_lines
# --------------------------------------------------------------------------- #


def test_build_lines_refuses_every_verdict_on_an_aged_population():
    """M2's completion condition, at the level a report actually goes through.

    Measured on the real population: the base year gives the usual spread — 2 spent,
    2 off target, 9 within, 8 outside — and the same aggregates declared as a 2028
    population against 2024 comparators give «not comparable» on all 21 lines, with
    nothing passing.

    Fails if `build_lines` stops threading the vintages, or if a single line escapes the
    refusal — one line reading «within tolerance» in a trajectory report would be the
    whole misreading this milestone exists to prevent.
    """
    from pathlib import Path

    if not Path("data/processed/population_2024.parquet").exists():
        pytest.skip("population non construite")

    from impots.population import aggregate as agg_mod
    from impots.population.reconcile import build_lines
    from impots.population.runner import run as population_run

    raw = pl.read_parquet("data/processed/population_2024.parquet")
    agg = agg_mod.aggregate(population_run(raw, year=2024, tier="full",
                                           sample=4_000).households)

    base = build_lines(agg)
    assert any(line.status == "within tolerance" for line in base), (
        "l'année de base doit produire des verdicts, sinon le refus ne prouve rien")

    aged = build_lines(agg, population_year=2028, comparator_year=2024)
    assert aged, "aucune ligne construite"
    assert all(line.status == "not comparable (population vieillie)" for line in aged)
    assert not any(line.passes for line in aged)


def test_matching_years_are_not_treated_as_aged():
    """A trajectory priced ON the base year is a base-year run and must reconcile
    normally. Fails if the check compares «is not None» instead of «differs»."""
    from pathlib import Path

    if not Path("data/processed/population_2024.parquet").exists():
        pytest.skip("population non construite")

    from impots.population import aggregate as agg_mod
    from impots.population.reconcile import build_lines
    from impots.population.runner import run as population_run

    raw = pl.read_parquet("data/processed/population_2024.parquet")
    agg = agg_mod.aggregate(population_run(raw, year=2024, tier="full",
                                           sample=4_000).households)
    lines = build_lines(agg, population_year=2024, comparator_year=2024)
    assert any(line.status == "within tolerance" for line in lines)
    assert not any("not comparable" in line.status for line in lines)
