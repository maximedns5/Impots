"""ERFS E2 — the pre-registration itself, tested before any ERFS number exists.

These tests do not touch the delivery. They check that the scorecard is the kind of thing
that can fail: tolerances present and tight, reasons attached, expectations recorded in
advance, and the two no-verdict axes declared as such rather than excused later.
"""

from __future__ import annotations

from impots.erfs import scorecard


def test_the_vintage_rule_is_2022_and_stated_in_code() -> None:
    """The engine runs AT 2022 against ERFS 2022. Ageing our population forward onto a
    2024 base and comparing would call the ageing error a model error."""
    assert scorecard.VINTAGE == 2022


def test_every_axis_carries_a_reason_for_its_tolerance() -> None:
    """A tolerance without a reason is a number somebody will widen. Each rationale has to
    say why THIS band and not a rounder one."""
    for axis in scorecard.AXES:
        assert len(axis.rationale) > 120, axis.key
        assert axis.expected, axis.key


def test_the_verdict_axes_have_tolerances_tight_enough_to_refuse() -> None:
    """The handoff's rule: a scorecard that admits everything measures nothing.

    Upper bound, not lower: 25 % on a distributional share would pass almost any population
    anyone would bother to build.
    """
    verdicts = scorecard.verdict_axes()
    assert verdicts, "aucun axe ne rend de verdict : le tableau ne mesurerait rien"
    for axis in verdicts:
        assert 0 < axis.tolerance <= 0.25, f"{axis.key}: {axis.tolerance}"


def test_the_no_verdict_axes_are_declared_in_advance() -> None:
    """Both are refusals of comparison, pre-registered rather than discovered.

    The tails because two undercounts compared measure neither; the capital joint because a
    residual of −100 % against an identically-zero column is an absence, not a measurement.
    """
    silent = [a for a in scorecard.AXES if a.band == "no_verdict"]
    assert {a.key for a in silent} == {"a1_decile_tails", "a4_capital_joint"}
    for axis in silent:
        assert axis.tolerance == 0.0, (
            f"{axis.key}: un axe sans verdict ne doit pas porter de tolérance, sinon "
            f"quelqu'un la lira comme une bande")


def test_the_capital_axis_records_that_it_fails_by_construction() -> None:
    """Pre-registered so that a predicted failure cannot later be presented as a discovery.
    The population carries identically zero capital income."""
    axis = scorecard.axis("a4_capital_joint")
    assert "construction" in axis.expected.lower()
    assert "ZÉRO" in axis.rationale or "zéro" in axis.rationale


def test_the_top_tail_is_refused_for_BOTH_sources_not_only_ours() -> None:
    """The asymmetric version of this refusal would be wrong and flattering: it is not only
    that our tail was thin, it is that ERFS's own top tail undercounts. A survey cannot see
    the very top — which is why DGFiP n° 41 exists at all."""
    axis = scorecard.axis("a1_decile_tails")
    assert "ERFS" in axis.rationale and "enquête" in axis.rationale


def test_the_scorecard_does_not_touch_the_delivery() -> None:
    """The pre-registration must be committable on a machine that does not hold ERFS —
    that is what «before the first number» means operationally."""
    import inspect

    source = inspect.getsource(scorecard)
    for forbidden in ("erfs_dir", "read_csv", "open(", "fpr_"):
        assert forbidden not in source, forbidden
