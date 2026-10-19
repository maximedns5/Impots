"""Phase 9 M1 — the reference path: consolidated totals, named scenarios, the spending rule.

Most tests run on CONSTRUCTED inputs, so they hold whatever the published figures become;
the few that read the manifested INSEE files skip without them (data/raw is ignored).
"""

from __future__ import annotations

import datetime as dt

import pytest

from impots.dette import comptes, maturite, reference, scenarios
from impots.dette.path import SHIPPED, DebtError, SpendingScenario

needs_totals = pytest.mark.skipif(
    not all((comptes.RAW / f).exists() for f in (
        comptes.TOTALS_FILE, comptes.APU_FILE, comptes.PIB_FILE, comptes.DETTE_FILE)),
    reason="les fichiers INSEE ne sont pas dans ce checkout (data/raw est ignoré)",
)

GROWTH = scenarios.GrowthScenario("Croissance réelle 1 %, prix 2 %", 0.01, 0.02)
START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)


# --------------------------------------------------------------------------- #
# table 3.201 — consolidated totals, closed on themselves and against 7.301
# --------------------------------------------------------------------------- #
def _table(spending: float, receipts: float, net_lending: float,
           label: str = "Total des dépenses") -> list[tuple]:
    """A 3.201-shaped sheet, in milliards, with one year column."""
    return [
        ("3.201 Dépenses et recettes", None), (None,), (None, None, "2025"),
        ("DEPENSES", None, None),
        ("Intérêts (D41)", None, 65.7209),
        ("Intérêts hors correction SIFIM (D41)", None, 64.6519),
        (label, None, spending),
        ("RECETTES", None, None),
        ("Intérêts (D41)", None, 3.4728),
        ("Total des recettes", None, receipts),
        ("SOLDES", None, None),
        ("Capacité (+) ou besoin (-) de financement (B9NF)", None, net_lending),
    ]


def _patch(monkeypatch, rows: list[tuple], b9: float = -151.592e9) -> None:
    monkeypatch.setattr(comptes, "_rows", lambda *a, **k: rows)
    monkeypatch.setattr(comptes, "_year_columns", lambda *a, **k: {2025: 2})
    account = comptes.ApuYear(year=2025, interest_resources_eur=5.268e9,
                              interest_uses_eur=67.516e9, net_lending_eur=b9)
    monkeypatch.setattr(comptes, "apu_account", lambda years: {2025: account})


def test_totals_that_close_are_read_with_their_primary_balance(monkeypatch) -> None:
    _patch(monkeypatch, _table(1714.1117, 1562.5197, -151.592))
    totals = comptes.apu_totals(2025)
    assert totals.primary_spending_eur == pytest.approx(1648.3908e9)
    assert totals.primary_receipts_eur == pytest.approx(1559.0469e9)
    # The primary balance from the totals and from 7.301 are the same number reached by
    # two different tables — the read-back is against an independent construction.
    account = comptes.apu_account([2025])[2025]
    assert totals.primary_balance_eur == pytest.approx(account.primary_balance_eur,
                                                       abs=1e7)


def test_totals_that_do_not_close_the_identity_are_refused(monkeypatch) -> None:
    """The kill test of the closing check: a total read from the wrong row — here ten
    milliards off — still parses and still plots, and would carry a spending ratio a
    third of a point wrong into every year of the path."""
    _patch(monkeypatch, _table(1724.1117, 1562.5197, -151.592))
    with pytest.raises(DebtError, match="ne se referme pas"):
        comptes.apu_totals(2025)


def test_a_label_is_matched_whole_never_as_a_substring(monkeypatch) -> None:
    """« Total des dépenses hors éléments imputés » CONTAINS « Total des dépenses ». A
    substring match would read it, and its value differs by about a hundred milliards."""
    _patch(monkeypatch, _table(1714.1117, 1562.5197, -151.592,
                               label="Total des dépenses hors éléments imputés"))
    with pytest.raises(DebtError, match="0 ligne"):
        comptes.apu_totals(2025)


def test_totals_that_disagree_with_table_7301_are_refused(monkeypatch) -> None:
    """Closed on itself but not with its sibling table: two tables of one vintage that
    differ cannot carry the same path."""
    _patch(monkeypatch, _table(1714.1117, 1562.5197, -151.592), b9=-150.0e9)
    with pytest.raises(DebtError, match="divergent"):
        comptes.apu_totals(2025)


@needs_totals
def test_the_published_start_matches_the_backtest_definitions() -> None:
    """The starting point, read from 3.201, against what 7.301 gives by another road:
    the primary balance (D-168 tabulates −2,99 % for 2025) and the implicit rate as net
    interest over the opening stock (D-168: 1,88 %)."""
    start = reference.start_from_accounts(2025)
    account = comptes.apu_account([2025])[2025]
    product = comptes.gdp([2025])[2025]
    opening, _ = comptes.debt([2024])[2024]
    assert start.primary_balance == pytest.approx(account.primary_balance_eur / product,
                                                  abs=1e-5)
    # The two tables print different decimals: 3.201 gives 62,2481 Md€ of net interest,
    # 7.301 gives 62,248. The rates agree to that rounding, a relative 2e-6.
    assert start.implicit_rate == pytest.approx(account.interest_net_eur / opening,
                                                rel=1e-5)
    assert start.primary_balance == pytest.approx(-0.0299, abs=5e-4)
    assert start.implicit_rate == pytest.approx(0.0188, abs=5e-4)
    assert start.debt_ratio == pytest.approx(comptes.debt([2025])[2025][1])


# --------------------------------------------------------------------------- #
# the named scenarios
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("name", ["Croissance probable", "Taux attendu", ""])
def test_a_scenario_name_must_exist_and_claim_no_likelihood(name: str) -> None:
    with pytest.raises(DebtError, match=r"sans nom|probabilité"):
        scenarios.GrowthScenario(name, 0.01, 0.02)
    with pytest.raises(DebtError, match=r"sans nom|probabilité"):
        scenarios.RateScenario(name, "implicite_tenu")


def test_nominal_growth_compounds_volume_and_prices() -> None:
    assert GROWTH.nominal == pytest.approx(1.01 * 1.02 - 1)


def test_a_growth_at_or_below_minus_one_hundred_percent_is_refused() -> None:
    with pytest.raises(DebtError, match=r"−100 %"):
        scenarios.GrowthScenario("Effondrement", -1.0, 0.0)


def test_a_rate_scenario_of_an_unknown_kind_is_refused() -> None:
    """D-229. `RateKind` is a `Literal`, unchecked at run time: an unknown kind would
    otherwise be charged as a market scenario by `chaine._rate_path`, whose test is
    `kind == "implicite_tenu"`."""
    with pytest.raises(DebtError, match="scénario de taux « au_fil_de_l_eau » inconnu"):
        scenarios.RateScenario("Taux au fil de l'eau", "au_fil_de_l_eau")


def test_a_market_scenario_must_carry_its_rate_and_the_held_one_must_not() -> None:
    with pytest.raises(DebtError, match=r"EST le scénario"):
        scenarios.RateScenario("Refinancement", "marche")
    with pytest.raises(DebtError, match="ignoré en silence"):
        scenarios.RateScenario("Taux tenu", "implicite_tenu", market_rate=0.03)


# --------------------------------------------------------------------------- #
# the spending rule, which until now no line read
# --------------------------------------------------------------------------- #
def _shares(rule_scenario: SpendingScenario, growth=GROWTH) -> list[float]:
    years = reference.reference_years(START, 10, spending=rule_scenario, growth=growth)
    return [y.spending_ratio for y in years]


def test_spending_kept_as_a_share_of_gdp_keeps_its_share() -> None:
    assert _shares(SHIPPED["part_pib_constante"]) == pytest.approx([0.55] * 10)


def test_spending_frozen_in_volume_loses_share_at_the_rate_of_real_growth() -> None:
    """THE KILL TEST FOR CORRECTION 3 (D-213). Until M1 the rule was carried by name and
    never read; an implementation that still ignores it gives the same path for both
    rules, and this fails."""
    frozen = _shares(SHIPPED["gele_en_volume"])
    assert frozen == pytest.approx([0.55 / 1.01 ** t for t in range(1, 11)])
    assert frozen[-1] < _shares(SHIPPED["part_pib_constante"])[-1]


def test_frozen_in_volume_does_not_depend_on_prices_but_the_gdp_does() -> None:
    """Spending follows prices and GDP follows prices: the SHARE is the same at 2 % and at
    5 % inflation, while every nominal level differs. Splitting growth into volume and
    prices is what lets the rule be computed at all."""
    inflation = scenarios.GrowthScenario("Croissance réelle 1 %, prix 5 %", 0.01, 0.05)
    assert _shares(SHIPPED["gele_en_volume"], inflation) == pytest.approx(
        _shares(SHIPPED["gele_en_volume"]))
    low = reference.reference_years(START, 3, spending=SHIPPED["gele_en_volume"],
                                    growth=GROWTH)
    high = reference.reference_years(START, 3, spending=SHIPPED["gele_en_volume"],
                                     growth=inflation)
    assert high[-1].gdp_eur > low[-1].gdp_eur


def test_a_custom_rate_equal_to_nominal_growth_keeps_the_share() -> None:
    custom = SpendingScenario("Dépense au rythme du PIB nominal", "personnalise",
                              growth=GROWTH.nominal)
    assert _shares(custom) == pytest.approx([0.55] * 10)


def test_receipts_stay_a_constant_share_and_the_balance_follows_spending() -> None:
    years = reference.reference_years(START, 10, spending=SHIPPED["gele_en_volume"],
                                      growth=GROWTH)
    assert all(y.receipts_ratio == 0.52 for y in years)
    balances = [y.primary_balance for y in years]
    assert balances == sorted(balances)
    assert balances[0] > START.primary_balance


@pytest.mark.parametrize("kwargs, needle", [
    ({"spending": None, "growth": GROWTH}, "dépense"),
    ({"spending": SHIPPED["gele_en_volume"], "growth": None}, "croissance"),
])
def test_the_reference_refuses_an_unnamed_hypothesis(kwargs, needle) -> None:
    with pytest.raises(DebtError, match=f"aucun scénario de {needle}"):
        reference.reference_years(START, 5, **kwargs)


def test_the_reference_refuses_a_spending_rule_it_does_not_know() -> None:
    """D-229. `SpendingRule` is a `Literal`, which nothing checks at run time: a scenario
    built with another rule passes its own dataclass, and only this refusal stands
    between it and a spending ratio computed from nothing."""
    unknown = SpendingScenario("Dépenses au fil de l'eau", "au_fil_de_l_eau")
    with pytest.raises(DebtError, match="règle de dépense inconnue : au_fil_de_l_eau"):
        reference.reference_years(START, 3, spending=unknown, growth=GROWTH)


@pytest.mark.parametrize("horizon", [0, 11])
def test_the_reference_refuses_an_horizon_outside_one_to_ten(horizon: int) -> None:
    with pytest.raises(DebtError, match="exacte et vide"):
        reference.reference_years(START, horizon, spending=SHIPPED["gele_en_volume"],
                                  growth=GROWTH)


# --------------------------------------------------------------------------- #
# the implicit rate path, with one deficit per year
# --------------------------------------------------------------------------- #
def _bond(coupon: float, year: int, amount: float) -> maturite.Security:
    return maturite.Security(isin="FR0000000000", kind="OAT", coupon=coupon,
                             maturity=dt.date(year, 6, 25), outstanding_eur=amount)


PORTFOLIO = [_bond(0.01, 2027, 500e9), _bond(0.02, 2040, 1500e9)]


def test_a_constant_deficit_sequence_equals_the_scalar() -> None:
    scalar = maturite.implicit_rate_path(PORTFOLIO, market_rate=0.035, scenario="3,5 %",
                                         deficit_eur=100e9, years=4)
    sequence = maturite.implicit_rate_path(PORTFOLIO, market_rate=0.035,
                                           scenario="3,5 %", deficit_eur=[100e9] * 4,
                                           years=4)
    assert [p.implicit_rate for p in sequence] == [p.implicit_rate for p in scalar]


def test_larger_deficits_raise_the_implicit_rate_when_the_market_is_above_the_stock() -> None:
    small = maturite.implicit_rate_path(PORTFOLIO, market_rate=0.035, scenario="3,5 %",
                                        deficit_eur=[50e9] * 4, years=4)
    large = maturite.implicit_rate_path(PORTFOLIO, market_rate=0.035, scenario="3,5 %",
                                        deficit_eur=[50e9, 150e9, 150e9, 150e9], years=4)
    assert small[0].implicit_rate == pytest.approx(large[0].implicit_rate)
    assert large[-1].implicit_rate > small[-1].implicit_rate


def test_a_deficit_sequence_of_the_wrong_length_is_refused() -> None:
    with pytest.raises(maturite.MaturityError, match="déficits pour"):
        maturite.implicit_rate_path(PORTFOLIO, market_rate=0.035, scenario="3,5 %",
                                    deficit_eur=[100e9] * 3, years=4)
