"""Phase 7 L1 — the top-tail rake, and the three things it must never do silently.

The rake is a CALIBRATION: after it runs, the top IR lines fit n° 41 by construction. So
the tests here are less about arithmetic than about the rake refusing to be quiet — about
a factor out of range stopping the run, a missing column stopping it, and the price to the
national total being returned rather than absorbed.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from impots.population import top_tail as tt


@pytest.fixture
def toy() -> tuple[np.ndarray, np.ndarray]:
    """A thousand foyers on a deliberately thin tail, equally weighted."""
    rng = np.random.default_rng(20260911)
    per_part = np.sort(rng.lognormal(9.5, 0.6, 1000))
    return per_part, np.ones(1000)


def test_the_nested_published_means_become_disjoint_targets() -> None:
    """«dont dernier centième» sits INSIDE «dernier dixième», and the millième inside both.

    Treating the three as separate bands would count the top thousandth three times and
    produce targets no distribution can meet at once. The conversion is the step most
    likely to be got wrong, so it is asserted directly: the 90-99 target must fall BELOW
    the published decile mean, because the decile mean is pulled up by the centile it
    contains.
    """
    targets = tt.published_targets()
    assert targets["90–99 %"] < 65_532, "la cible 90-99 doit être sous la moyenne du dixième"
    assert targets["99–99,9 %"] < targets["99,9–100 %"]
    assert targets["99,9–100 %"] == pytest.approx(916_590, rel=1e-3)


def test_every_band_except_the_first_decile_has_a_target() -> None:
    """The first decile is published «n.s.» and must have none — a missing comparator and
    a zero one look identical in a residual column, so it is excluded rather than zeroed."""
    targets = tt.published_targets()
    missing = [label for label, _low, _high in tt.BANDS if label not in targets]
    assert missing == ["1er dixième"], missing


def test_a_factor_outside_the_measured_range_stops_the_run(toy) -> None:
    """The gate measured ×0,92 to ×2,80. A factor beyond the bounds means the comparator
    or the population has moved, and rewriting incomes silently would be the worst
    available response."""
    per_part, weights = toy
    absurd = {"99,9–100 %": 1e9}
    with pytest.raises(tt.TopTailError, match="hors de"):
        tt.factors(per_part, weights, absurd)


def test_a_missing_money_column_stops_the_run() -> None:
    frame = pl.DataFrame({"foyer_id": ["a"], "weight": [1.0],
                          "salaire_brut_annuel": [1000.0]})
    with pytest.raises(tt.TopTailError, match="colonnes absentes"):
        tt.apply(frame, ["a"], np.array([1.5]))


def test_the_rake_returns_the_price_it_charged_the_national_total() -> None:
    """**The rake cannot both match the published fractiles and preserve the calibrated
    total.** Measured at -2,03 % on the real population. The figure is returned rather than
    absorbed, because a calibration that silently moves a total the model was calibrated
    to is the exact shape of a line that validates itself."""
    frame = pl.DataFrame({
        "foyer_id": ["a", "b"], "weight": [1.0, 1.0],
        "salaire_brut_annuel": [100.0, 200.0],
        "pension_annuelle": [0.0, 0.0], "chomage_annuel": [0.0, 0.0]})
    _raked, result = tt.apply(frame, ["a", "b"], np.array([0.5, 2.0]))

    assert result.total_before_eur == pytest.approx(300.0)
    assert result.total_after_eur == pytest.approx(450.0)
    assert result.total_shift == pytest.approx(0.5)


def test_only_money_moves_and_the_rows_stay_put() -> None:
    """Structure, weights and identities are untouched — the same rule as `uprating`, for
    the same reason: a population whose rows moved makes every per-foyer trajectory
    meaningless."""
    frame = pl.DataFrame({
        "foyer_id": ["a", "b"], "weight": [3.0, 7.0], "age": [40, 50],
        "salaire_brut_annuel": [100.0, 200.0],
        "pension_annuelle": [10.0, 0.0], "chomage_annuel": [0.0, 5.0]})
    raked, _result = tt.apply(frame, ["a", "b"], np.array([2.0, 2.0]))

    assert raked.height == frame.height
    assert raked["weight"].to_list() == frame["weight"].to_list()
    assert raked["age"].to_list() == frame["age"].to_list()
    assert raked["salaire_brut_annuel"].to_list() == [200.0, 400.0]
    assert raked["pension_annuelle"].to_list() == [20.0, 0.0]


def test_a_foyer_absent_from_the_factor_map_is_left_alone(toy) -> None:
    """Not scaled by a default guess: unlisted means unchanged, and a factor of 1.0 is the
    only honest reading of «no information»."""
    frame = pl.DataFrame({
        "foyer_id": ["a", "inconnu"], "weight": [1.0, 1.0],
        "salaire_brut_annuel": [100.0, 100.0],
        "pension_annuelle": [0.0, 0.0], "chomage_annuel": [0.0, 0.0]})
    raked, _ = tt.apply(frame, ["a"], np.array([3.0]))
    assert raked["salaire_brut_annuel"].to_list() == [300.0, 100.0]


def test_residuals_report_the_miss_rather_than_asserting_it_away(toy) -> None:
    """Fractile membership is fixed BEFORE scaling, so the raked population lands near its
    targets and not on them. The residual is published, not iterated away — measured at
    +7,8 % on the top millième against -64,3 % before."""
    per_part, weights = toy
    targets = {label: tt.band_means(per_part, weights)[label] * 1.1
               for label, _lo, _hi in tt.BANDS
               if label in tt.band_means(per_part, weights)}
    residuals = tt.residuals(per_part, weights, targets)

    assert residuals, "aucun résidu rendu : le contrôle ne contrôle rien"
    for label, value in residuals.items():
        assert value == pytest.approx(-1 / 11, abs=1e-9), label


# ----------------------------------------------- the wiring, which is half the lever

def test_the_rake_is_off_by_default() -> None:
    """A calibration that ran unless you asked it not to would be the worst possible
    default: every figure downstream would be fitted, and nobody would know."""
    import inspect

    from impots.population.runner import run

    parameter = inspect.signature(run).parameters["rake_top_tail"]
    assert parameter.default is False


def test_the_rake_runs_before_the_niche_imputation() -> None:
    """The order is load-bearing and therefore asserted on the source.

    Niche bases are handed out by DECILE OF RFR PER PART, and the rake moves RFR per part.
    Imputing first would distribute bases by a ranking the rake then invalidates — a
    plausible population that nobody could trace back to a defect.
    """
    from pathlib import Path

    source = Path("src/impots/population/runner.py").read_text(encoding="utf-8")
    body = source[source.index("def run("):]
    assert body.index("if rake_top_tail:") < body.index("if impute_niches:"), (
        "le recalage doit précéder l'imputation des niches")


def test_a_raked_line_refuses_a_tolerance_verdict() -> None:
    """L1's completion condition, and the exact analogue of F3 M2's.

    After the rake the top IR lines fit n° 41 by construction. A tolerance verdict on them
    would report the rake working rather than the model being right.
    """
    from impots.reporting import Line

    raked = Line(label="IR au barème", simulated=100.0, published=100.0, unit="EUR",
                 tolerance=0.10, use="validation", source="DGFiP n° 41",
                 raked_top_tail=True)
    assert raked.status == "not comparable (queue recalée)"

    # And the kill: the SAME line without the flag must return a real verdict, or the
    # refusal above proves nothing about the flag.
    plain = Line(label="IR au barème", simulated=100.0, published=100.0, unit="EUR",
                 tolerance=0.10, use="validation", source="DGFiP n° 41")
    assert plain.status != "not comparable (queue recalée)"


def test_the_two_refusals_are_distinguishable() -> None:
    """An uprated population is compared to the wrong YEAR; a raked one to a figure it was
    fitted to. Two reasons, two messages — a reader deserves to know which applies."""
    from impots.reporting import Line

    aged = Line(label="x", simulated=1.0, published=1.0, unit="EUR", tolerance=0.1,
                use="validation", source="s", population_year=2028, comparator_year=2024)
    raked = Line(label="x", simulated=1.0, published=1.0, unit="EUR", tolerance=0.1,
                 use="validation", source="s", raked_top_tail=True)
    assert aged.status != raked.status
    assert "vieillie" in aged.status and "recalée" in raked.status
