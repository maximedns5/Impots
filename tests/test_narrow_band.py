"""The narrow-band flag (D-046).

Metadata about a mechanical result, never a change to it. The backtest suite measured
why it exists: a barème indexation overshoots its published cost by 10 %, while the
2025 allègements step — which moves two cliffs — overshoots by 107 %. Same population,
same engine. A cliff's yield comes entirely from the households between the old
ceiling and the new one, so it is proportional to the density in a narrow band and to
nothing else, and that density is the least reliable thing in a synthetic population.
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.narrow_band import SHARE, WINDOW, household_thresholds, measure


class FakeReform:
    def __init__(self, **knobs: object) -> None:
        self._knobs = knobs

    def model_dump(self, exclude_none: bool = True) -> dict[str, object]:
        return dict(self._knobs)


SMIC = 21_203.0


def test_a_cliff_puts_all_of_its_movement_in_the_band() -> None:
    """The shape the flag exists for: only households between the two ceilings move,
    and they are by construction within a window of the new one."""
    income = np.array([20e3, 45e3, 50e3, 52e3, 90e3])
    movement = np.array([0.0, 0.0, -500.0, -500.0, 0.0])
    result = measure(income, movement, np.ones(5), [50e3])
    assert result.share == pytest.approx(1.0)
    assert result.flagged
    assert "bande de salaires étroite" in result.caveat


def test_a_broad_reform_is_not_flagged() -> None:
    """Movement spread across the whole distribution cannot rest on one band."""
    income = np.linspace(10e3, 200e3, 400)
    result = measure(income, -np.full(400, 100.0), np.ones(400),
                     [11497.0, 29315.0, 83823.0, 180294.0])
    assert result.share < SHARE
    assert not result.flagged
    assert result.caveat == ""


def test_winners_and_losers_that_cancel_still_count() -> None:
    """Absolute movement, not net. A reform whose gains and losses cancel still rests
    on the density where those households sit, and reporting a zero share would say
    the opposite."""
    income = np.array([49e3, 51e3])
    result = measure(income, np.array([-500.0, +500.0]), np.ones(2), [50e3])
    assert result.share == pytest.approx(1.0)
    assert result.flagged


def test_a_rate_change_with_no_threshold_contributes_nothing() -> None:
    """A CSG rate or a décote rate moves everyone it touches proportionally; it has no
    threshold of its own and cannot concentrate a yield. The share stays zero rather
    than being undefined."""
    assert household_thresholds(FakeReform(csg_activite_imposable=0.034), SMIC) == []
    assert household_thresholds(FakeReform(decote_taux=0.5), SMIC) == []
    result = measure(np.array([30e3]), np.array([-100.0]), np.ones(1), [])
    assert result.share == 0.0 and not result.flagged


def test_smic_multiples_become_wage_levels() -> None:
    """A plafond is in SMIC multiples and the income axis is in euros. Comparing the
    two without converting would put every threshold near zero and flag nothing."""
    thresholds = household_thresholds(
        FakeReform(bandeau_maladie_plafond=2.25, bandeau_famille_plafond=3.3), SMIC
    )
    assert thresholds == pytest.approx([2.25 * SMIC, 3.3 * SMIC])


def test_the_bareme_contributes_its_thresholds_but_not_its_zero() -> None:
    """A zero threshold is the bottom of the scale, not a place anyone clusters."""
    thresholds = household_thresholds(
        FakeReform(ir_bareme=[{"threshold": 0, "rate": 0.0},
                              {"threshold": 11497, "rate": 0.11}]), SMIC
    )
    assert thresholds == [11497.0]


def test_the_window_is_wide_enough_for_the_step_that_motivated_it() -> None:
    """The 2025 step moved the maladie ceiling about 11 %. A window narrower than the
    move would miss the very households the measure acts on."""
    assert WINDOW > 0.11
    income = np.array([2.35 * SMIC])  # between the old 2.5 and the new 2.25
    result = measure(income, np.array([-300.0]), np.ones(1), [2.25 * SMIC])
    assert result.flagged


def _run_households(frame):
    """What `runner.run` hands back for `frame`, without the engine: one row per
    household at the MEAN of its members' weights, as the runner aggregates, and a
    labour cost moved by the frame's `move`."""
    import polars as pl

    return (
        frame.group_by("household_id")
        .agg(pl.col("weight").mean(),
             pl.col("salaire_brut_annuel").sum().alias("salaire_brut"),
             pl.col("move").sum())
        .with_columns(
            pl.col("salaire_brut").alias("salaire_super_brut"),
            pl.col("salaire_brut").alias("salaire_imposable"),
            (pl.col("salaire_brut") + pl.col("move")).alias("salaire_super_brut_reform"),
            pl.lit(0.0).alias("revenu_disponible"),
            pl.lit(0.0).alias("revenu_disponible_reform"))
        .sort("household_id")
    )


def test_the_wage_family_reads_the_quick_tier_at_its_own_weights() -> None:
    """D-247. The quick tier prices 20 000 households, reweighted to the population; the
    wage family read every earner of the WHOLE frame at the frame's weight, with no
    movement outside the subsample. A share, so the zeros cancel and nothing is divided
    by the sampling fraction; but the households drawn weighed their own weight, not the
    subsample's, and the light ones, which the draw scales up most, counted for too
    little.

    Worked example: 10 households of weight 1 000 000, each one earner at 1.2 SMIC,
    far from a 2.25-SMIC plafond, whose labour cost falls 100 EUR; 990 of weight 1 000,
    each one earner at the plafond, whose cost falls 2 000 EUR. The population's share
    from inside the window is 990 × 1 000 × 2 000 / (that + 10 × 1 000 000 × 100) =
    1.98 / 2.98 = 66 %: flagged. Drawn down to 100 households, the 10 heavy ones are
    certain and keep their weight, and 90 light ones weigh 990 000 / 90 = 11 000 each:
    the same 66 %. At the frame's weight they weigh 1 000, and the share fell to 15 %,
    under the bar.
    """
    from types import SimpleNamespace

    import polars as pl

    from impots.api import main as api_main
    from impots.api.schemas import ReformSpec
    from impots.population.runner import subsample

    smic = api_main._smic_annual(2024)
    heavy, light = 10, 990
    frame = pl.DataFrame({
        "household_id": np.arange(heavy + light),
        "person_id": np.arange(heavy + light),
        "salaire_brut_annuel": np.r_[np.full(heavy, 1.2 * smic), np.full(light, 2.25 * smic)],
        "weight": np.r_[np.full(heavy, 1_000_000.0), np.full(light, 1_000.0)],
        "move": np.r_[np.full(heavy, -100.0), np.full(light, -2_000.0)],
    })
    request = SimpleNamespace(year=2024, reform=ReformSpec(bandeau_maladie_plafond=2.25))
    expected = 1.98 / 2.98

    full = api_main._narrow_band(request, _run_households(frame), frame)
    assert full.share == pytest.approx(expected, rel=1e-9)
    drawn = subsample(frame, 100)
    assert drawn.height == 100
    quick = api_main._narrow_band(request, _run_households(drawn), frame)
    assert quick.share == pytest.approx(expected, rel=1e-9), (
        "the quick tier must measure the share of the population it was reweighted to")
    assert quick.flagged
