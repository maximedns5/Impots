"""The shared reconciliation-report engine and the guards (PHASE2_SPEC §0.5 P1).

Written before the firm module gets a second report, because the audit's top open
item was that the module generating the project's credibility page had 345
untested lines and had already shipped two real defects. Both are the first
regression tests here.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from impots import guards, reporting
from impots.reporting import Figure, Line, SpentMarginError

PUBLISHED = Figure(
    value=100e9, unit="EUR", year=2024, scope="a published total",
    source="Somewhere", url="https://example.org", use="validation",
)
CALIBRATED = Figure(
    value=100e9, unit="EUR", year=2024, scope="a margin we fitted to",
    source="Somewhere", url="https://example.org", use="calibration",
)


def render(lines: list[Line], **kwargs: object) -> str:
    return reporting.render(
        title="Test", vintage="2024", engine="test", intro="intro",
        lines=lines, sources={}, **kwargs,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------------- #
# regression 1 — the formatter defect found by the 2026-09-01 audit
# --------------------------------------------------------------------------- #
def test_ratios_keep_their_decimals() -> None:
    """The defect: euro amounts and ratios shared one formatter, so an interdecile
    ratio of 4.88 printed as "5" against a published 3.50 shown as "4" — on the
    page whose whole job is stating how far off the model is."""
    assert reporting.format_value(4.88, "raw") == "4.88"
    assert reporting.format_value(3.50, "raw") == "3.50"
    assert reporting.format_value(0.297, "raw") == "0.30"


def test_large_values_do_not_get_spurious_decimals() -> None:
    """The other half of the same choice: a niveau de vie of 22 780 € is not
    '22 780.00', and the thousands separator is a space, not a comma."""
    assert reporting.format_value(22_780.0, "raw") == "22 780"
    assert reporting.format_value(1_111.65e9, "EUR") == "1 111.7 bn €"
    assert reporting.format_value(31_274_700.0, "count") == "31.27 M"


def test_missing_values_render_as_absent_not_zero() -> None:
    assert reporting.format_value(None, "EUR") == "—"
    assert reporting.format_residual(None) == "—"


# --------------------------------------------------------------------------- #
# regression 2 — the spent-margin defect
# --------------------------------------------------------------------------- #
def test_a_line_takes_its_use_from_its_figure() -> None:
    """The defect: the ménage count was presented as a validation line while
    raking targeted it, so the report claimed credit for hitting what it had been
    tuned to. `from_figure` makes the two impossible to disagree."""
    line = Line.from_figure(CALIBRATED, "Ménages", 99e9, 0.02)
    assert line.use == "calibration"
    assert line.status == "calibrated (spent)"


def test_render_refuses_a_line_that_drifted_from_its_figure() -> None:
    """Belt and braces: if a caller builds a line from a calibration figure and
    then relabels it as validation, the report refuses to be generated."""
    line = Line.from_figure(CALIBRATED, "Ménages", 99e9, 0.02)
    line.use = "validation"
    with pytest.raises(SpentMarginError, match="presented as evidence"):
        render([line])


def test_calibration_and_validation_are_rendered_in_separate_tables() -> None:
    text = render([
        Line.from_figure(CALIBRATED, "Spent thing", 99e9, 0.02),
        Line.from_figure(PUBLISHED, "Free thing", 99e9, 0.10),
    ])
    calibration = text.split("## Calibration targets")[1].split("## Validation")[0]
    validation = text.split("## Validation lines")[1]
    assert "Spent thing" in calibration and "Spent thing" not in validation
    assert "Free thing" in validation and "Free thing" not in calibration


# --------------------------------------------------------------------------- #
# tolerance evaluation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("simulated", "tolerance", "expected"),
    [
        (100e9, 0.10, "within tolerance"),
        (109e9, 0.10, "within tolerance"),
        (110e9, 0.10, "within tolerance"),   # exactly on the edge counts as within
        (111e9, 0.10, "OUTSIDE tolerance"),
        (89e9, 0.10, "OUTSIDE tolerance"),
        (None, 0.10, "not modelled"),
    ],
)
def test_status_follows_the_declared_tolerance(
    simulated: float | None, tolerance: float, expected: str
) -> None:
    assert Line.from_figure(PUBLISHED, "x", simulated, tolerance).status == expected


def test_residual_is_none_rather_than_infinite_when_nothing_is_published() -> None:
    zero = Figure(0.0, "EUR", 2024, "s", "src", "url", "validation")
    assert Line.from_figure(zero, "x", 5.0, 0.1).residual is None


def test_a_line_with_nothing_to_compare_is_shown_not_dropped() -> None:
    """A table that quietly loses the lines the model does badly on — or has no
    answer for — is worse than no table."""
    text = render([Line.from_figure(PUBLISHED, "Unmodelled thing", None, 0.10)])
    assert "Unmodelled thing" in text
    assert "not modelled" in text


def test_the_verdict_names_every_failing_line() -> None:
    text = render([
        Line.from_figure(PUBLISHED, "Fine", 100e9, 0.10),
        Line.from_figure(PUBLISHED, "Bad", 300e9, 0.10),
    ])
    verdict = text.split("## Verdict")[1]
    assert "1 validation line(s) outside" in verdict
    assert "Bad" in verdict and "Fine" not in verdict


def test_a_clean_report_says_so() -> None:
    text = render([Line.from_figure(PUBLISHED, "Fine", 100e9, 0.10)])
    assert "Every validation line is within its declared tolerance." in text


# --------------------------------------------------------------------------- #
# take-up bridges
# --------------------------------------------------------------------------- #
def test_bridge_emits_both_readings() -> None:
    """A benefit computed at full entitlement is not comparable with observed
    spend without the bridge, and the two readings can disagree: inside a flat
    tolerance raw, well below where a full-take-up model should put it."""
    lines = reporting.bridge_lines(
        "RSA", 25.5e9, Figure(12.4e9, "EUR", 2024, "s", "CNAF", "url", "validation"),
        bridge=(1.30, 1.41), flat_tolerance=0.25,
        bridge_note="bridge", raw_note="raw",
    )
    assert [line.label for line in lines] == ["RSA (bridge-adjusted)", "RSA"]
    centre = (1.30 + 1.41) / 2
    assert lines[0].simulated == pytest.approx(25.5e9 / centre)
    assert lines[1].simulated == 25.5e9


def test_bridge_tolerance_widens_with_the_published_range() -> None:
    narrow = reporting.bridge_lines(
        "x", 1.0, PUBLISHED, (1.30, 1.31), 0.25, "b", "r")[0].tolerance
    wide = reporting.bridge_lines(
        "x", 1.0, PUBLISHED, (1.30, 1.80), 0.25, "b", "r")[0].tolerance
    assert wide > narrow, "a wider published bridge is a weaker claim, not a stricter one"


# --------------------------------------------------------------------------- #
# comparison column
# --------------------------------------------------------------------------- #
def test_comparison_column_shows_lines_that_got_worse() -> None:
    """The point of the column: reporting the lines that moved the wrong way
    alongside the ones that improved."""
    line = Line.from_figure(PUBLISHED, "Thing", 120e9, 0.10)
    text = render([line], comparison={"Thing": 0.05}, comparison_title="Before")
    assert "Before" in text
    assert "+5.0%" in text and "+20.0%" in text


def test_comparison_absent_when_not_asked_for() -> None:
    text = render([Line.from_figure(PUBLISHED, "Thing", 120e9, 0.10)])
    assert "Before" not in text


# --------------------------------------------------------------------------- #
# the guards — regression 3, the weight defects
# --------------------------------------------------------------------------- #
def _frame(weights: list[float], values: list[float]) -> pl.DataFrame:
    return pl.DataFrame({"weight": weights, "ca": values})


def test_weight_identity_accepts_a_reweighting_that_preserves_totals() -> None:
    # Weight moves between units; the weighted total does not. 2x10 + 2x20 = 60,
    # and 4x10 + 1x20 = 60.
    before = _frame([2.0, 2.0], [10.0, 20.0])
    after = _frame([4.0, 1.0], [10.0, 20.0])
    assert guards.weighted_total(before, "ca") == guards.weighted_total(after, "ca") == 60.0
    guards.weight_identity(before, after, ["ca"], step="test")


def test_weight_identity_catches_the_summed_weight_defect() -> None:
    """The real defect: household weight taken as the sum of member weights
    rather than the mean, implying a population of 120 M and multiplying every
    euro aggregate by 2.2. Finite, positive, no exception anywhere."""
    before = _frame([1.0, 1.0], [100.0, 100.0])
    inflated = _frame([2.2, 2.2], [100.0, 100.0])
    with pytest.raises(guards.WeightIdentityError, match="pre-step total"):
        guards.weight_identity(before, inflated, ["ca"], step="household weighting")


def test_weight_identity_catches_the_rescaled_pps_defect() -> None:
    """The other real defect: a PPS subsample rescaled on top of a design that is
    already self-weighting, multiplying every aggregate by 2.8."""
    before = _frame([1.0] * 4, [50.0] * 4)
    rescaled = _frame([2.8] * 4, [50.0] * 4)
    with pytest.raises(guards.WeightIdentityError) as excinfo:
        guards.weight_identity(before, rescaled, ["ca"], step="subsample")
    assert "+180" in str(excinfo.value)


def test_weight_identity_allows_a_step_that_is_itself_a_calibration() -> None:
    """Raking is allowed to move the total it is fitted to — and only that one."""
    before = _frame([1.0, 1.0], [100.0, 100.0])
    raked = _frame([1.5, 1.5], [100.0, 100.0])
    guards.weight_identity(before, raked, ["ca"], step="raking", targets={"ca": 300.0})
    with pytest.raises(guards.WeightIdentityError, match="calibration target"):
        guards.weight_identity(before, raked, ["ca"], step="raking", targets={"ca": 999.0})


def test_weight_identity_reports_every_column_at_once() -> None:
    before = pl.DataFrame({"weight": [1.0], "ca": [10.0], "va": [5.0]})
    after = pl.DataFrame({"weight": [2.0], "ca": [10.0], "va": [5.0]})
    with pytest.raises(guards.WeightIdentityError) as excinfo:
        guards.weight_identity(before, after, ["ca", "va"], step="s")
    assert "ca:" in str(excinfo.value) and "va:" in str(excinfo.value)


def test_no_nan_guard() -> None:
    guards.no_nan(np.array([1.0, 2.0]), "fine")
    with pytest.raises(guards.GuardError, match="2 non-finite"):
        guards.no_nan(np.array([1.0, np.nan, np.inf]), "broken")


def test_non_negative_guard() -> None:
    guards.non_negative(np.array([0.0, 1.0]), "fine")
    with pytest.raises(guards.GuardError, match="1 negative"):
        guards.non_negative(np.array([1.0, -1.0]), "ca")


def test_not_greater_counts_rather_than_raises() -> None:
    """Value added should not exceed turnover, but published sector aggregates
    occasionally say otherwise. Worth counting and reporting; not worth aborting."""
    assert guards.not_greater(np.array([1.0, 3.0]), np.array([2.0, 2.0]), "va<=ca") == 1
    assert guards.not_greater(np.array([1.0]), np.array([2.0]), "va<=ca") == 0


# --------------------------------------------------------------------------- #
# the population report still uses all of it
# --------------------------------------------------------------------------- #
def test_population_report_lines_are_all_figure_backed() -> None:
    """Every line in the household report comes from a `Figure`, so none of them
    can drift from its own tagging."""
    import json
    from pathlib import Path

    from impots.population import reconcile
    from impots.population.aggregate import Aggregates, DecileRow

    baseline = Path(__file__).resolve().parents[1] / "data" / "processed" / "baseline_2024.json"
    if not baseline.exists():
        pytest.skip("no population built")
    raw = json.loads(baseline.read_text(encoding="utf-8"))
    agg = Aggregates(
        totals=raw["totals"], counts=raw["counts"],
        deciles=[DecileRow(**row) for row in raw["deciles"]],
        households=raw["households"], persons=raw["persons"],
    )
    lines = reconcile.build_lines(agg)
    assert lines
    assert all(line.figure_use is not None for line in lines)
    assert all(line.figure_use == line.use for line in lines)
    # and the whole report renders, which exercises the tagging check
    assert "## Verdict" in reconcile.render(agg, "2024")
