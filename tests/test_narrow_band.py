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
