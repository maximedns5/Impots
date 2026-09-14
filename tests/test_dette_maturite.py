"""Phase 8 §3.2 — the implicit rate on Block 1, and the four kill tests the spec names.

Three of the four run on CONSTRUCTED portfolios, and that is the point: «zero rollover» and
«instant full rollover» do not exist in the real stock, so a test that only ever sees the
real stock cannot tell a correct rollover from a broken one. The fourth runs on the real
manifested data, because that is where the perimeter question lives.
"""

from __future__ import annotations

import datetime as dt

import pytest

from impots.dette import maturite as m

AS_OF = dt.date(2026, 7, 31)
HAS_DATA = (m.__file__ and __import__("pathlib").Path(
    "data/raw/aft_bulletin_mensuel_435_aout_2026.pdf").exists())
needs_aft = pytest.mark.skipif(not HAS_DATA, reason="bulletin AFT non manifesté ici")


def bond(coupon: float, year: int, amount: float, isin: str = "FR0000000000",
         kind: str = "OAT") -> m.Security:
    return m.Security(isin=isin, kind=kind, coupon=coupon,
                      maturity=dt.date(year, 6, 25), outstanding_eur=amount)


# ------------------------------------------------------------------ kill test 1

def test_zero_rollover_and_zero_deficit_hold_the_rate_constant() -> None:
    """§3.2's first kill test. Nothing matures inside the horizon and nothing is borrowed,
    so the implicit rate cannot move.

    **An implementation that leaks the market rate into a frozen stock fails here** — which
    is the specific defect the spec names, and the reason the market rate below is set far
    from the portfolio's own coupon: if it bled in at all, 3,0 % would drag 1,0 % visibly.
    """
    far = [bond(0.01, 2060, 1_000e9)]
    path = m.implicit_rate_path(far, market_rate=0.03, scenario="marché 3 %",
                                years=5, as_of=AS_OF)
    assert [round(p.implicit_rate, 12) for p in path] == [0.01] * 5
    assert all(p.rolled_eur == 0.0 for p in path)


# ------------------------------------------------------------------ kill test 2

def test_instant_full_rollover_puts_the_implicit_rate_at_the_market_rate() -> None:
    """§3.2's second. Everything matures in year 1, so after the roll the whole stock is
    new issuance and the implicit rate IS the market rate."""
    now = [bond(0.005, 2026, 800e9), bond(0.02, 2026, 200e9)]
    path = m.implicit_rate_path(now, market_rate=0.035, scenario="marché 3,5 %",
                                years=2, as_of=AS_OF)
    assert path[0].implicit_rate == pytest.approx(0.035)
    assert path[0].rolled_eur == pytest.approx(1_000e9)


def test_a_partial_rollover_lands_between_the_old_coupon_and_the_market_rate() -> None:
    """The interpolation between the two kill tests above. Half the stock rolls, so the
    blend must sit strictly between 1 % and 5 % — a rollover that jumped straight to either
    end would pass both extremes and still be wrong in every real case."""
    mixed = [bond(0.01, 2026, 500e9, isin="A"), bond(0.01, 2060, 500e9, isin="B")]
    path = m.implicit_rate_path(mixed, market_rate=0.05, scenario="marché 5 %",
                                years=1, as_of=AS_OF)
    assert 0.01 < path[0].implicit_rate < 0.05
    assert path[0].implicit_rate == pytest.approx(0.03)


# ------------------------------------------------------------------ kill test 4

@needs_aft
def test_the_redemption_schedule_sums_to_the_manifested_stock() -> None:
    """§3.2's fourth. A schedule that loses a line understates every future rollover, and
    it would do so silently: the sum is the only thing that notices."""
    securities = m.load_block1()
    stock = sum(s.outstanding_eur for s in securities)
    schedule = m.redemption_schedule(securities, as_of=AS_OF, horizon=60)
    assert sum(schedule.values()) == pytest.approx(stock, rel=1e-12)


def test_lines_past_their_maturity_are_folded_forward_not_dropped() -> None:
    """A line already past `as_of` is still money to refinance; dropping it shrinks the
    stock the schedule is supposed to reconstruct.

    **CONSTRUCTED, because the real stock has no such line.** The first version of this
    test ran on the manifested bulletin, where the earliest maturity is 2026-08-05 and
    `as_of` is 2026-07-31 — zero securities past maturity, so the premise never occurred
    and the test passed against an implementation that dropped them. Mutation-testing
    caught it: «throw away already-matured lines» passed all nine tests. That is the D-044
    shape, in a file whose own docstring explains why three of the four kill tests are
    constructed.
    """
    stale = [bond(0.02, 2020, 300e9, isin="VIEUX"), bond(0.03, 2030, 700e9, isin="VIF")]
    schedule = m.redemption_schedule(stale, as_of=AS_OF, horizon=10)

    assert sum(schedule.values()) == pytest.approx(1_000e9), "la ligne échue a été perdue"
    assert schedule[AS_OF.year] == pytest.approx(300e9), (
        "la ligne échue doit tomber dans la PREMIÈRE année, pas dans son année d'origine")


# ------------------------------------------------- kill test 3, and its perimeter

@needs_aft
def test_year_one_charge_against_the_p117_anchor_with_the_residual_measured() -> None:
    """§3.2's third kill test, and the one that cannot be squeezed.

    Market scenario set to the current implicit rate → the year-1 charge should land near
    the R2 anchor. Measured: 52,78 md€ against programme 117's 58,615 md€, **−9,9 %**.

    THE RESIDUAL IS A PERIMETER DIFFERENCE AND IS RECORDED RATHER THAN TUNED AWAY. P117 is
    a BUDGETARY charge on the État's whole debt; this module sums coupon legs and omits the
    indexation uplift by declared simplification (D-133). That omission is signed — it makes
    the modelled charge too LOW — and it is the right size: 2 % inflation on the 312,8 md€
    of indexed stock is 6,3 md€, which more than covers the 5,8 md€ gap.

    The tolerance is therefore set at the MEASURED residual plus room, and a tolerance that
    a perimeter error fits inside is a perimeter error with a certificate — so this test
    asserts the sign and the magnitude, not merely «within tolerance».
    """
    securities = m.load_block1()
    current = m.current_implicit_rate(securities)
    path = m.implicit_rate_path(securities, market_rate=current,
                                scenario="marché = implicite courant", years=1,
                                as_of=AS_OF)
    charge = path[0].interest_eur
    residual = charge / m.P117_ANCHOR_EUR - 1

    assert -0.12 < residual < -0.06, f"résidu {residual:+.1%} hors de la plage mesurée"
    assert charge < m.P117_ANCHOR_EUR, (
        "le résidu doit être NÉGATIF : la provision d'indexation omise ne peut que "
        "sous-estimer la charge, et un résidu positif dirait que l'explication est fausse")

    indexed = sum(s.outstanding_eur for s in securities
                  if s.kind in ("OATi", "OAT€i"))
    assert 0.02 * indexed > abs(charge - m.P117_ANCHOR_EUR), (
        "l'indexation omise doit pouvoir couvrir l'écart, sinon il reste inexpliqué")


@needs_aft
def test_the_current_implicit_rate_is_plausible_for_a_state_debt() -> None:
    """A guard on the parse as much as on the arithmetic: a coupon read as 250 instead of
    2,50 would give a rate of 250 % and still be a float."""
    rate = m.current_implicit_rate(m.load_block1())
    assert 0.005 < rate < 0.06, f"taux implicite {rate:.2%} implausible"


# ------------------------------------------------------------------ the refusals

def test_a_rate_path_without_a_named_scenario_is_refused() -> None:
    """A rate with no named scenario reads as a forecast."""
    with pytest.raises(m.MaturityError, match="sans nom"):
        m.implicit_rate_path([bond(0.02, 2030, 1e9)], market_rate=0.03, scenario="  ")


def test_an_empty_portfolio_is_refused_rather_than_rated_at_zero() -> None:
    with pytest.raises(m.MaturityError, match="encours vide"):
        m.implicit_rate_path([], market_rate=0.03, scenario="marché 3 %")
