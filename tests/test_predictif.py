"""Phase 9 M1 — the chain reform → primary balance → debt (`predictif.chaine`).

Every test runs on a CONSTRUCTED starting point: the chain's arithmetic must hold whatever
the published accounts become, and the published start has its own tests
(`test_dette_reference.py`).
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import pytest

from impots.dette import maturite, path, reference, scenarios
from impots.dette.path import SHIPPED, DebtError
from impots.predictif import chaine
from impots.predictif.comportement import AtTheta
from impots.predictif.theta import Theta, ThetaError

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = scenarios.GrowthScenario("Croissance réelle 1 %, prix 2 %", 0.01, 0.02)
HELD = scenarios.RateScenario("Taux implicite tenu à son niveau de 2025", "implicite_tenu")
FROZEN = SHIPPED["gele_en_volume"]
#: Named by every test that runs a path: the chain has no default θ, so neither does this.
HALF = Theta(common=0.5)


def _run(costs: chaine.ReformCosts, horizon: int = 10, **kwargs) -> chaine.Trajectoire:
    options = {"spending": FROZEN, "growth": GROWTH, "rate": HELD, "theta": HALF,
               **kwargs}
    return chaine.run(START, horizon=horizon, costs=costs, **options)


def _at(receipts: float, low: float, high: float) -> AtTheta:
    """What `comportement.evaluate` returns, RECEIPTS POSITIVE."""
    return AtTheta(receipts=receipts, grade="in-support", box=(low, high),
                   claimed=("eti_all", "eti_top_decile"))


def _carried(cost: float, **kwargs) -> chaine.ReformCosts:
    return chaine.ReformCosts(by_year={2026: cost}, carry=chaine.CARRY, **kwargs)


# --------------------------------------------------------------------------- #
# the arithmetic
# --------------------------------------------------------------------------- #
def test_a_null_reform_leaves_the_debt_where_the_reference_puts_it() -> None:
    result = _run(_carried(0.0))
    assert result.delta == pytest.approx((0.0,) * 10, abs=1e-15)
    assert result.reform == result.reference


def test_the_difference_matches_an_independent_recurrence_on_the_whole_balance() -> None:
    """D-042: a read-back compares against an INDEPENDENT construction. Under a held rate
    the identity is linear, so the reform path computed in one go — the reference balance
    plus the reform's — must equal reference + difference. A chain that applied the
    reform to one path and not the other, or charged it at another rate, fails here."""
    result = _run(_carried(5e9))
    years = reference.reference_years(START, 10, spending=FROZEN, growth=GROWTH)
    whole = path.project(START.debt_ratio, [
        path.YearInputs(year=y.year, r=START.implicit_rate, g=GROWTH.nominal,
                        primary_balance=y.primary_balance + result.delta_primary[i])
        for i, y in enumerate(years)], spending=FROZEN)
    assert [p.ratio for p in whole] == pytest.approx(result.reform, abs=1e-12)


def test_a_cost_raises_the_debt_and_a_yield_lowers_it() -> None:
    """Engine convention: a cost is positive. A sign error inverts the answer to the
    question the whole phase exists for, while still drawing a plausible path."""
    assert all(d > 0 for d in _run(_carried(5e9)).delta)
    assert all(d < 0 for d in _run(_carried(-5e9)).delta)


def test_the_first_year_difference_is_the_cost_over_gdp() -> None:
    result = _run(_carried(6e9), horizon=1)
    assert result.delta[0] == pytest.approx(6e9 / (START.gdp_eur * (1 + GROWTH.nominal)))


def test_extra_debt_is_charged_at_the_market_rate_under_the_market_scenario() -> None:
    """Two years by hand, in levels: Δb_2 = Δb_1 (1 + m) / (1 + g) + Δcost_2 / Y_2, with
    m the MARKET rate, not the held implicit rate."""
    market = scenarios.RateScenario("Refinancement à 4 %", "marche", market_rate=0.04)
    securities = [maturite.Security(isin="FR0000000000", kind="OAT", coupon=0.015,
                                    maturity=dt.date(2030, 6, 25), outstanding_eur=2e12)]
    result = _run(chaine.ReformCosts(by_year={2026: 5e9, 2027: 5e9}), horizon=2,
                  rate=market, securities=securities)
    y1 = START.gdp_eur * (1 + GROWTH.nominal)
    y2 = y1 * (1 + GROWTH.nominal)
    first = 5e9 / y1
    assert result.delta[0] == pytest.approx(first)
    assert result.delta[1] == pytest.approx(first * 1.04 / (1 + GROWTH.nominal) + 5e9 / y2)
    assert chaine.RATE_PROXY in result.conventions


# --------------------------------------------------------------------------- #
# the refusals
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("missing, needle", [
    ({"spending": None}, "dépense"),
    ({"growth": None}, "croissance"),
    ({"rate": None}, "taux"),
])
def test_each_unnamed_hypothesis_is_refused(missing: dict, needle: str) -> None:
    with pytest.raises(DebtError, match=f"aucun scénario de {needle}"):
        _run(_carried(5e9), **missing)


def test_unpriced_years_are_refused_without_the_named_convention() -> None:
    with pytest.raises(DebtError, match="non chiffrées"):
        _run(chaine.ReformCosts(by_year={2026: 5e9}))


def test_the_carry_convention_labels_every_year_it_fills() -> None:
    result = _run(_carried(5e9), horizon=4)
    assert result.priced_years == (2026,)
    assert result.carried_years == (2027, 2028, 2029)
    assert chaine.CARRY_LABEL in result.conventions
    # Held as a share of GDP: every year's Δp is the first year's.
    assert result.delta_primary == pytest.approx((result.delta_primary[0],) * 4)


def test_priced_years_with_a_gap_or_a_late_start_are_refused() -> None:
    with pytest.raises(DebtError, match="suite qui commence"):
        _run(chaine.ReformCosts(by_year={2026: 5e9, 2028: 5e9}, carry=chaine.CARRY))
    with pytest.raises(DebtError, match="suite qui commence"):
        _run(chaine.ReformCosts(by_year={2027: 5e9}, carry=chaine.CARRY))


def test_the_market_scenario_without_the_aft_outstanding_is_refused() -> None:
    market = scenarios.RateScenario("Refinancement à 4 %", "marche", market_rate=0.04)
    with pytest.raises(DebtError, match="sans encours AFT"):
        _run(_carried(5e9), rate=market)


# --------------------------------------------------------------------------- #
# what is absent, and says so
# --------------------------------------------------------------------------- #
def test_the_feedback_is_absent_with_its_reason_and_no_winner_is_named() -> None:
    result = _run(_carried(5e9))
    feedback = next(s for s in result.decomposition.slices if s.source == "eventail")
    assert not feedback.computed and "M3" in feedback.reason
    assert "rétroaction" in result.absent
    with pytest.raises(DebtError, match="non calculée"):
        result.decomposition.dominant_source(0)


def test_without_behaviour_the_box_is_absent_not_zero() -> None:
    result = _run(_carried(5e9))
    band = next(s for s in result.decomposition.slices if s.source == "bande")
    assert not band.computed and band.low == () and band.reason


def test_the_theta_box_brackets_the_path_at_theta() -> None:
    """The box is RECEIPTS POSITIVE (`comportement.evaluate`), the cost is COST POSITIVE.
    With the receipts at θ at −5,5 Md€ inside a box of −6 to −3, the box's paths must
    bracket the path at θ every year. Read with the cost's sign, they would sit on the
    far side of the reference, nowhere near it — which is what this catches."""
    result = _run(_carried(5e9, behavioural={2026: _at(-5.5e9, -6e9, -3e9)}))
    band = next(s for s in result.decomposition.slices if s.source == "bande")
    assert band.computed and band.label == chaine.BOX_LABEL
    for low, central, high in zip(band.low, result.reform, band.high, strict=True):
        assert low <= central <= high
    assert chaine.BOX_CONVENTION in result.conventions


def test_with_behaviour_the_headline_is_at_theta_and_the_mechanical_stands_beside() -> None:
    """−5,5 Md€ of receipts at θ against a mechanical cost of 5 Md€: the headline moves
    by the behavioural half-milliard, the mechanical difference does not."""
    plain = _run(_carried(5e9))
    at = _run(_carried(5e9, behavioural={2026: _at(-5.5e9, -6e9, -3e9)}))
    assert at.delta_mechanical == pytest.approx(plain.delta)
    assert at.delta[0] == pytest.approx(5.5e9 / (3_000e9 * 1.01 * 1.02))
    assert at.theta_applied and not plain.theta_applied


def test_a_null_reform_leaves_the_debt_alone_at_any_theta() -> None:
    for common in (0.0, 0.5, 1.0):
        result = _run(_carried(0.0, behavioural={2026: _at(0.0, 0.0, 0.0)}),
                      theta=Theta(common=common))
        assert result.delta == pytest.approx((0.0,) * 10, abs=1e-15)


def test_a_box_on_part_of_the_priced_years_is_refused() -> None:
    with pytest.raises(DebtError, match="mêmes années"):
        chaine.ReformCosts(by_year={2026: 5e9, 2027: 5e9},
                           behavioural={2026: _at(-5e9, -6e9, -3e9)})


def test_receipts_at_theta_outside_their_box_are_refused() -> None:
    with pytest.raises(DebtError, match="hors de leur boîte"):
        _carried(5e9, behavioural={2026: _at(-7e9, -6e9, -3e9)})


# --------------------------------------------------------------------------- #
# θ — guards 1 and 2 (§2.4)
# --------------------------------------------------------------------------- #
def test_a_path_without_a_theta_is_refused() -> None:
    """GUARD 1, in the chain: no default θ, not even 1/2."""
    with pytest.raises(ThetaError, match="aucun θ"):
        _run(_carried(5e9), theta=None)


def test_a_theta_for_a_row_the_store_does_not_hold_is_refused() -> None:
    with pytest.raises(ThetaError, match="inconnues"):
        _run(_carried(5e9), theta=Theta(rows={"eti_al": 0.2}, common=0.5))


def test_the_result_lists_every_open_row_even_in_the_mechanical_view() -> None:
    result = _run(_carried(5e9), theta=Theta(rows={"eti_all": 0.2}, common=0.7))
    assert sorted(result.theta) == sorted(result.open_rows)
    assert len(result.open_rows) == 8
    assert result.theta["eti_all"] == 0.2 and result.theta["eti_top_decile"] == 0.7
    assert "θ" in result.absent and not result.theta_applied
    assert any("non lus" in line for line in result.lines())


def test_a_result_with_a_theta_missing_refuses_to_exist() -> None:
    """GUARD 2. The precedent is the banner: a checked field, not a decoration."""
    result = _run(_carried(5e9), horizon=2)
    short = dict(result.theta)
    short.pop("employment_elasticity_smic")
    with pytest.raises(ThetaError, match="manquant"):
        dataclasses.replace(result, theta=short)


def test_a_closed_channel_without_its_reason_refuses_to_exist() -> None:
    result = _run(_carried(5e9), horizon=2)
    assert set(result.closed) == set(chaine.CLOSED)
    with pytest.raises(ThetaError, match="sans leur raison"):
        dataclasses.replace(result, closed={**result.closed, "R&D et CIR": " "})


def test_the_banner_is_a_checked_field_not_a_decoration() -> None:
    result = _run(_carried(5e9), horizon=2)
    with pytest.raises(DebtError, match="bannière"):
        dataclasses.replace(result, banner="")
    assert chaine.BANNER in result.lines()
