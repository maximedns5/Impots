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
from macro_cases import synthetic_macro_store

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


def test_priced_years_past_the_horizon_are_refused_rather_than_dropped() -> None:
    """A year priced beyond the horizon would be ignored without a word (D-229): three
    priced years on a two-year path would print as the first two."""
    with pytest.raises(DebtError, match="au-delà de l'horizon"):
        _run(chaine.ReformCosts(by_year={2026: 5e9, 2027: 5e9, 2028: 5e9}), horizon=2)


def test_a_cost_without_a_priced_year_or_with_an_unknown_carry_is_refused() -> None:
    """The two refusals `ReformCosts` makes on its own (D-229): no year priced, and a carry
    convention that is not the one the chain names and labels."""
    with pytest.raises(DebtError, match="aucune année chiffrée"):
        chaine.ReformCosts(by_year={})
    with pytest.raises(DebtError, match="convention de report « reconduit » inconnue"):
        chaine.ReformCosts(by_year={2026: 5e9}, carry="reconduit")


def test_an_aft_outstanding_dated_for_another_start_is_refused() -> None:
    """The maturities of July 2026 are not those of a path that starts in 2024 (D-229):
    the market scenario would refinance debt that had not yet been issued."""
    market = scenarios.RateScenario("Refinancement à 4 %", "marche", market_rate=0.04)
    earlier = dataclasses.replace(START, year=maturite.AS_OF.year - 2)
    with pytest.raises(DebtError, match="l'encours AFT est daté"):
        chaine.run(earlier, horizon=3,
                   costs=chaine.ReformCosts(by_year={earlier.year + 1: 5e9},
                                            carry=chaine.CARRY),
                   spending=FROZEN, growth=GROWTH, rate=market, theta=HALF,
                   securities=[object()])


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
    assert not feedback.computed and "non demandé" in feedback.reason
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


def test_a_reversed_box_is_refused_by_its_own_name() -> None:
    """A box with its bounds swapped holds no receipts at all, and would be refused as
    receipts outside their box — true, and the wrong reason (D-229)."""
    with pytest.raises(DebtError, match="boîte retournée"):
        _carried(5e9, behavioural={2026: _at(-4.9e9, -4.8e9, -5.0e9)})


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
    # + D-220's four rows, D-221's, D-222's, D-246's, D-249's three and D-256's
    assert len(result.open_rows) == 19
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


def test_a_result_with_a_theta_outside_the_unit_interval_refuses_to_exist() -> None:
    """`Theta` refuses such a value when it is built; the result checks again, because a
    table can reach it without passing through `Theta` (D-229)."""
    result = _run(_carried(5e9), horizon=2)
    with pytest.raises(ThetaError, match="hors de"):
        dataclasses.replace(result, theta={**result.theta, "eti_all": 1.2})


def test_a_result_whose_series_differ_in_length_refuses_to_exist() -> None:
    """A path shifted by one year would draw without any visible error (D-229)."""
    result = _run(_carried(5e9), horizon=3)
    for series in ("reference", "reform", "delta", "delta_primary", "delta_mechanical"):
        with pytest.raises(DebtError, match="longueurs différentes"):
            dataclasses.replace(result, **{series: getattr(result, series)[:-1]})


def test_a_result_with_an_absence_without_its_reason_refuses_to_exist() -> None:
    """D-229. Guard 2 holds every CLOSED channel to its reason; an ABSENT one — the band
    not asked for, the loop not applied — was held by nothing, and an absence with an
    empty reason reads as a quantity measured at zero."""
    result = _run(_carried(5e9), horizon=2)
    assert result.absent["bande"] == chaine.ABSENT_BAND
    with pytest.raises(DebtError, match="absent sans sa raison"):
        dataclasses.replace(result, absent={**result.absent, "bande": "  "})


def test_a_closed_channel_without_its_reason_refuses_to_exist() -> None:
    result = _run(_carried(5e9), horizon=2)
    assert set(result.closed) == {*chaine.CLOSED, *chaine.MACRO_CHANNELS}
    with pytest.raises(ThetaError, match="sans leur raison"):
        dataclasses.replace(result, closed={**result.closed, "R&D et CIR": " "})


def test_the_banner_is_a_checked_field_not_a_decoration() -> None:
    result = _run(_carried(5e9), horizon=2)
    with pytest.raises(DebtError, match="bannière"):
        dataclasses.replace(result, banner="")
    assert chaine.BANNER in result.lines()


# --------------------------------------------------------------------------- #
# M3 — the GDP → receipts loop in the chain (D-218)
# --------------------------------------------------------------------------- #
def _looped(cost: float = 5e9, impulse: dict | None = None, **kwargs) -> chaine.Trajectoire:
    """An income-tax cut of `cost`, its impulse expansionary-positive, with the loop."""
    costs = chaine.ReformCosts(
        by_year={2026: cost}, carry=chaine.CARRY,
        impulses={2026: impulse if impulse is not None else {"impot_sur_le_revenu": cost}})
    options = {"persistence": "tenu", "macro_store": synthetic_macro_store(), **kwargs}
    return _run(costs, **options)


def test_the_loop_gives_back_part_of_the_cost_and_divides_by_the_reform_gdp() -> None:
    """Year one by hand: the balance loses 0,81 of the cost (0,19 comes back), and the
    reform's debt ratio is divided by its GDP, 0,41 of the cost above the reference's."""
    result = _looped()
    y = 3_000e9 * 1.01 * 1.02
    raw = 0.81 * 5e9 / y
    expected = (result.reference[0] + raw) / (1.0 + 0.41 * 5e9 / y)
    assert result.reform[0] == pytest.approx(expected, rel=1e-12)
    assert result.feedback_primary[0] == pytest.approx(0.19 * 5e9 / y, rel=1e-12)
    assert result.gdp_gap[0] == pytest.approx(0.41 * 5e9 / y, rel=1e-12)
    assert result.delta_mechanical[0] == pytest.approx(5e9 / y, rel=1e-12)
    assert 0 < result.delta[0] < result.delta_mechanical[0]


def test_with_the_loop_the_macro_theta_is_listed_and_the_eventail_computed() -> None:
    result = _looped()
    assert result.theta[chaine.MACRO_ROW] == 0.5 and chaine.MACRO_ROW in result.open_rows
    eventail = next(s for s in result.decomposition.slices if s.source == "eventail")
    assert eventail.computed and eventail.label == chaine.EVENTAIL_LABEL
    for low, central, high in zip(eventail.low, result.reform, eventail.high, strict=True):
        assert low <= central <= high
    assert not any(k in result.closed for k in chaine.MACRO_CHANNELS)
    assert "rétroaction" not in result.absent
    assert any("1,18" in c for c in result.conventions)


def test_under_another_spending_rule_the_loop_is_absent_with_its_reason() -> None:
    """D-214: Mésange's spending reacts in prices only; under a GDP-share rule the row
    cannot be read as printed, and the loop says so instead of correcting it."""
    result = _looped(spending=SHIPPED["part_pib_constante"], persistence=None)
    assert "note 70" in result.absent["rétroaction"]
    assert result.gdp_gap is None and chaine.MACRO_ROW not in result.theta
    assert all("note 70" in result.closed[k] for k in chaine.MACRO_CHANNELS)
    assert result.delta == pytest.approx(result.delta_mechanical)


def test_past_three_years_the_loop_needs_a_named_persistence() -> None:
    with pytest.raises(retroaction_error(), match="persistance"):
        _looped(persistence=None)
    assert len(_looped(persistence=None, horizon=3).years) == 3


def test_a_persistence_the_chain_would_ignore_is_refused() -> None:
    with pytest.raises(DebtError, match="ignorée"):
        _run(_carried(5e9), persistence="tenu")
    with pytest.raises(DebtError, match="ignorée"):
        _looped(spending=SHIPPED["part_pib_constante"])


def test_an_impulse_with_no_balance_row_leaves_the_loop_absent_not_zero() -> None:
    result = _looped(impulse={"cotisations_employeurs_ciblees": 5e9})
    assert "aucun instrument" in result.absent["rétroaction"]
    assert result.gdp_gap is None


def test_a_loop_without_the_macro_theta_is_refused() -> None:
    with pytest.raises(ThetaError, match="refusé"):
        _looped(theta=Theta(rows={k: 0.5 for k in _looped().open_rows
                                  if k != chaine.MACRO_ROW}))


def test_a_result_listing_the_macro_theta_without_its_effect_refuses_to_exist() -> None:
    """Guard 2, extended: the macro θ is listed only with the GDP effect it produced, and
    the loop's channels are never listed closed while it runs."""
    result = _looped()
    with pytest.raises(ThetaError, match="sans effet"):
        dataclasses.replace(result, gdp_gap=None)
    with pytest.raises(ThetaError, match="contredirait"):
        dataclasses.replace(result, closed={**result.closed,
                                            chaine.MACRO_CHANNELS[0]: "fermée"})


def test_an_impulse_on_other_years_than_the_costing_is_refused() -> None:
    with pytest.raises(DebtError, match="mêmes années"):
        chaine.ReformCosts(by_year={2026: 5e9, 2027: 5e9},
                           impulses={2026: {"impot_sur_le_revenu": 5e9}})


def retroaction_error():
    from impots.predictif.retroaction import FeedbackError

    return FeedbackError


def test_the_transfers_and_the_corporate_tax_are_shown_closed_with_what_was_found() -> None:
    """M4 (D-219): neither opened. A reader sees why on the result itself — the two
    meta-analyses that disagree, the IS variant that does not exist."""
    result = _run(_carried(5e9), horizon=2)
    assert "2,5" in result.closed["transferts"]
    assert "Mésange 2017" in result.closed["IS et investissement des entreprises"]


def test_the_dividends_are_not_said_closed_for_want_of_capital_income() -> None:
    """D-250. The population carries capital income since D-248, and the dividends'
    response is C10, in the receipts of a PFU reform, since D-249. A result that still
    says the channel closed because the population carries none says what is no longer
    true. Like labour supply in D-220, C10 says itself why it does not open."""
    result = _run(_carried(5e9), horizon=2)
    assert "dividendes" not in result.closed
    assert not any("revenu du capital" in reason for reason in result.closed.values())
