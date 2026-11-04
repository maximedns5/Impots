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

from impots import service
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


def _run(frame):
    """What `runner.run` hands back for `frame`, without the engine. Its persons, each
    with a labour cost equal to their gross, moved by their own `move`; and one row per
    household at the MEAN of its members' weights, as the runner aggregates, with its
    persons' wages and costs summed."""
    from types import SimpleNamespace

    import polars as pl

    persons = frame.select(
        "person_id", "household_id", "salaire_brut_annuel", "weight",
        pl.col("salaire_brut_annuel").alias("salaire_super_brut"),
        (pl.col("salaire_brut_annuel") + pl.col("move")).alias("salaire_super_brut_reform"))
    households = (
        frame.group_by("household_id").agg(pl.col("weight").mean())
        .join(persons.group_by("household_id").agg(
            pl.col("salaire_brut_annuel").sum().alias("salaire_brut"),
            pl.col("salaire_super_brut").sum(), pl.col("salaire_super_brut_reform").sum()),
            on="household_id")
        .with_columns(pl.col("salaire_brut").alias("salaire_imposable"),
                      pl.lit(0.0).alias("revenu_disponible"),
                      pl.lit(0.0).alias("revenu_disponible_reform"))
        .sort("household_id"))
    return SimpleNamespace(households=households, persons=persons)


def test_the_wage_family_reads_the_quick_tier_at_its_own_weights() -> None:
    """D-260. The quick tier prices 20 000 households, reweighted to the population; the
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

    from impots.api.schemas import ReformSpec
    from impots.population.runner import subsample

    smic = service.smic_annual(2024)
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

    full = service.narrow_band(request, _run(frame))
    assert full.share == pytest.approx(expected, rel=1e-9)
    drawn = subsample(frame, 100)
    assert drawn.height == 100
    quick = service.narrow_band(request, _run(drawn))
    assert quick.share == pytest.approx(expected, rel=1e-9), (
        "the quick tier must measure the share of the population it was reweighted to")
    assert quick.flagged


def test_the_wage_family_reads_each_earner_s_own_movement() -> None:
    """D-261. Each earner carried their household's movement split evenly among its
    earners, so a partner sitting at a plafond who did not move took half of a cut that
    reached a wage far below it, and counted it inside the window.

    Worked example, two households of weight 1 000. In the first, an earner at a
    2.25-SMIC plafond whose labour cost does not move, and a partner at 1.2 SMIC, far
    below it, whose cost falls 1 000 EUR. In the second, one earner at the plafond whose
    cost falls 400 EUR. On their own movements, 400 of 1 400 EUR come from inside the
    window: 29 %, under the bar. Split evenly, the first earner took 500 of the
    partner's 1 000, and the share read 900 / 1 400 = 64 %: flagged.
    """
    from types import SimpleNamespace

    import polars as pl

    from impots.api.schemas import ReformSpec

    smic = service.smic_annual(2024)
    frame = pl.DataFrame({
        "household_id": [0, 0, 1],
        "person_id": [0, 1, 2],
        "salaire_brut_annuel": [2.25 * smic, 1.2 * smic, 2.25 * smic],
        "weight": [1_000.0] * 3,
        "move": [0.0, -1_000.0, -400.0],
    })
    request = SimpleNamespace(year=2024, reform=ReformSpec(bandeau_maladie_plafond=2.25))
    flag = service.narrow_band(request, _run(frame))
    assert flag.share == pytest.approx(400 / 1_400, rel=1e-9), (
        "an earner's movement is their own, not a share of their household's")
    assert not flag.flagged


def test_the_wage_family_reads_each_earner_at_their_own_weight() -> None:
    """D-269. Each earner counted at their household's weight, the mean of its members'.
    Members' weights can differ, and the quick tier's subsample scales each by the same
    factor, so the mean miscounts the heavier member and the lighter one (D-255).

    Worked example, one household weighing 300 on average: an earner at a 2.25-SMIC
    plafond weighing 360, whose labour cost falls 1 000 EUR, and a partner at 1.2 SMIC,
    far below it, weighing 240, whose cost falls 1 000 EUR too. At their own weights,
    360 000 of 600 000 come from inside the window: 60 %, flagged. At the household's
    300 each, 50 %: under the bar.
    """
    from types import SimpleNamespace

    import polars as pl

    from impots.api.schemas import ReformSpec

    smic = service.smic_annual(2024)
    frame = pl.DataFrame({
        "household_id": [0, 0],
        "person_id": [0, 1],
        "salaire_brut_annuel": [2.25 * smic, 1.2 * smic],
        "weight": [360.0, 240.0],
        "move": [-1_000.0, -1_000.0],
    })
    request = SimpleNamespace(year=2024, reform=ReformSpec(bandeau_maladie_plafond=2.25))
    flag = service.narrow_band(request, _run(frame))
    assert flag.share == pytest.approx(0.6, rel=1e-9), (
        "an earner must count at their own weight in the run, not their household's")
    assert flag.flagged
