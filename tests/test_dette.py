"""Phase 8 M1 §3.1 — the debt identity, and the guards that make a path honest.

The recurrence is arithmetic and would be dull to test alone. What is worth testing is the
REFUSALS: a path without a named spending scenario, a scenario whose name claims
likelihood, a horizon past which the numbers are exact and empty. Each refusal here has its
kill — the case that must still succeed — because a guard that refuses everything passes a
refusal test and protects nothing.
"""

from __future__ import annotations

import pytest

from impots.dette import path as dette


def year(y: int = 2027, *, r: float = 0.02, g: float = 0.03, p: float = 0.0,
         sfa: float = 0.0) -> dette.YearInputs:
    return dette.YearInputs(year=y, r=r, g=g, primary_balance=p, sfa=sfa)


# ------------------------------------------------------------------ the arithmetic

def test_one_year_of_the_identity_by_hand() -> None:
    """A single year checked against arithmetic done outside the module.

    117,5 × 1,02 / 1,03 − 0 + 0 = 116,359…  A recurrence only ever checked end-to-end is
    one whose first year is never checked at all.
    """
    point = dette.step(117.5, year(r=0.02, g=0.03))
    assert point.ratio == pytest.approx(117.5 * 1.02 / 1.03)
    assert point.ratio == pytest.approx(116.3592233, abs=1e-6)


def test_the_snowball_turns_when_r_exceeds_g() -> None:
    """r > g raises the ratio with a zero primary balance; r < g lowers it. The sign of
    (r − g) is the whole debate, so it gets its own test rather than riding inside another."""
    assert dette.step(100.0, year(r=0.04, g=0.02)).ratio > 100.0
    assert dette.step(100.0, year(r=0.02, g=0.04)).ratio < 100.0
    assert dette.step(100.0, year(r=0.03, g=0.03)).ratio == pytest.approx(100.0)


def test_a_surplus_reduces_the_ratio_which_pins_the_sign_convention() -> None:
    """`primary_balance` is SURPLUS POSITIVE. The literature is split on this sign, and
    getting it backwards inverts every path while leaving it perfectly plausible."""
    neutral = dette.step(100.0, year(r=0.03, g=0.03, p=0.0)).ratio
    surplus = dette.step(100.0, year(r=0.03, g=0.03, p=1.0)).ratio
    assert surplus == pytest.approx(neutral - 1.0)


def test_the_decomposition_terms_sum_back_to_the_ratio() -> None:
    """§3.6 renders the terms separately; if they do not reconstruct the total the display
    is a decoration rather than a decomposition."""
    start = 117.5
    p = dette.step(start, year(r=0.025, g=0.031, p=0.4, sfa=0.2))
    rebuilt = (start / 1.031) + p.interest_ratio + p.contribution_primary + p.contribution_sfa
    assert rebuilt == pytest.approx(p.ratio)


def test_growth_of_minus_one_hundred_percent_is_refused() -> None:
    """The denominator (1+g) vanishes. Refused by name rather than returning an infinity
    that would propagate through the whole path looking like a number."""
    with pytest.raises(dette.DebtError, match="dénominateur"):
        dette.step(100.0, year(g=-1.0))


# --------------------------------------------------- the spending-scenario guard (§3.5)

def test_a_path_without_a_named_spending_scenario_is_refused() -> None:
    """The phase-defining refusal. Spending is ~57 % of GDP and only the transfer slice is
    microsimulated; a path with receipts moving and spending unstated implies that taxes
    alone carry the adjustment."""
    with pytest.raises(dette.DebtError, match="aucun scénario de dépense nommé"):
        dette.project(117.5, [year()])


def test_the_same_call_succeeds_once_a_scenario_is_named() -> None:
    """The kill test for the refusal above. Without it, a `project` that refused every call
    would pass the previous test and protect nothing."""
    out = dette.project(117.5, [year()], spending=dette.SHIPPED["gele_en_volume"])
    assert len(out) == 1
    assert out[0].ratio == pytest.approx(117.5 * 1.02 / 1.03)


def test_no_default_scenario_is_silently_applied() -> None:
    """A default here would be a political claim wearing an engineering default's clothes:
    whoever picks the spending path picks who bears the adjustment."""
    import inspect

    assert inspect.signature(dette.project).parameters["spending"].default is None


def test_a_scenario_name_claiming_likelihood_is_refused() -> None:
    """Scenarios are scenarios. Nothing here has a probability model, so a name that
    asserts likelihood asserts something the module cannot support."""
    for name in ("Scénario le plus probable", "Central forecast", "Trajectoire attendue"):
        with pytest.raises(dette.DebtError, match="probabilité"):
            dette.SpendingScenario(name, "gele_en_volume")


def test_an_ordinary_scenario_name_is_accepted() -> None:
    """The kill for the check above — and it is the half that matters, because the
    probability check is DENYLIST-shaped and this project has shipped a denylist refusal
    that accepted everything it should have rejected (`refuse_banded`). The limit is
    stated in the module: a new way of saying «probable» slips through."""
    s = dette.SpendingScenario("Dépenses gelées en volume", "gele_en_volume")
    assert s.name == "Dépenses gelées en volume"


def test_a_nameless_scenario_is_refused() -> None:
    with pytest.raises(dette.DebtError, match="sans nom"):
        dette.SpendingScenario("   ", "gele_en_volume")


def test_a_custom_scenario_must_carry_its_rate_and_the_others_must_not() -> None:
    """Both directions. A « personnalisé » without a rate is the scenario nobody chose; a
    rate handed to a rule that ignores it would be dropped in silence while the chart
    displayed a name that no longer describes the arithmetic."""
    with pytest.raises(dette.DebtError, match="EST le"):
        dette.SpendingScenario("Trajectoire personnalisée", "personnalise")
    with pytest.raises(dette.DebtError, match="ignoré en silence"):
        dette.SpendingScenario("Dépenses gelées en volume", "gele_en_volume", growth=0.02)
    ok = dette.SpendingScenario("Trajectoire personnalisée", "personnalise", growth=0.02)
    assert ok.growth == 0.02


# ---------------------------------------------------------------- the horizon cap

def test_beyond_the_horizon_the_path_is_refused_not_truncated() -> None:
    """A silently shortened path looks like a finished one."""
    many = [year(2027 + i) for i in range(dette.HORIZON_CAP_YEARS + 1)]
    with pytest.raises(dette.DebtError, match="exacte et vide"):
        dette.project(117.5, many, spending=dette.SHIPPED["gele_en_volume"])


def test_exactly_the_horizon_is_allowed() -> None:
    """The kill: an off-by-one would make the cap refuse the last legal year, and a cap
    tested only from the outside cannot tell the two apart."""
    ok = [year(2027 + i) for i in range(dette.HORIZON_CAP_YEARS)]
    assert len(dette.project(117.5, ok, spending=dette.SHIPPED["gele_en_volume"])) == \
        dette.HORIZON_CAP_YEARS


def test_the_banner_names_what_is_not_simulated() -> None:
    """The standing banner is load-bearing text, so it is asserted rather than trusted."""
    assert "57" in dette.BANNER and "microsimulées" in dette.BANNER
