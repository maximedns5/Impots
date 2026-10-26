"""Phase 9 M1b — the full path, priced year by year (`predictif.annuel`).

The engine is injected: a stub prices each year, so the logic — both views, no carry, the
coherence between the population's prices and the GDP's — is held in seconds.
"""

from __future__ import annotations

import pytest

from impots.dette import reference, scenarios
from impots.dette.path import SHIPPED, DebtError
from impots.predictif import annuel, chaine
from impots.predictif.theta import Theta, ThetaError

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = scenarios.GrowthScenario("Croissance réelle 1 %, prix 2 %", 0.01, 0.02)
HELD = scenarios.RateScenario("Taux implicite tenu à son niveau de 2025", "implicite_tenu")
YEARS = list(range(2026, 2031))


def _stub(year: int, view: str) -> float:
    """A cost that grows with the year, and more in the aged view."""
    return 5e9 * (1.03 if view == "vieillie" else 1.0) ** (year - 2025)


HALF = Theta(common=0.5)


def _build(prices, uprating=None, theta=HALF) -> annuel.Rapport:
    uprating = uprating or annuel.uprating_for(GROWTH, wage=0.03, source="test",
                                               base_year=2024)
    return annuel.build(START, prices, scenario="test", titre="Test", source="test",
                        reference="reconduit", computed="2026-10-16",
                        spending=SHIPPED["gele_en_volume"], growth=GROWTH, rate=HELD,
                        theta=theta, uprating=uprating, uprating_note="note")


def test_every_year_is_priced_in_both_views() -> None:
    seen = []

    def spy(year, view):
        seen.append((year, view))
        return _stub(year, view)

    prices = annuel.price_years(YEARS, spy, basis_for=lambda y: "legislated")
    assert sorted(seen) == sorted((y, v) for y in YEARS for v in annuel.VIEWS)
    assert [p.year for p in prices] == YEARS


def test_the_full_path_carries_no_year_and_names_no_carry_convention() -> None:
    """The batch job exists so that no year is a convention: if a carried year slipped in,
    the report would look priced where it is not."""
    rapport = _build(annuel.price_years(YEARS, _stub, basis_for=lambda y: "legislated"))
    assert rapport.aged.carried_years == () and rapport.frozen.carried_years == ()
    assert chaine.CARRY_LABEL not in rapport.aged.conventions


def test_a_gap_in_the_priced_years_is_refused_rather_than_carried() -> None:
    """`build` asks the chain for as many years as were priced, with no carry. A year
    that went missing in the middle — a pass that failed and was skipped — is refused by
    the chain's own guard instead of being filled."""
    prices = annuel.price_years([2026, 2028], _stub, basis_for=lambda y: "legislated")
    with pytest.raises(DebtError, match="suite qui commence"):
        _build(prices)


def test_a_report_with_no_priced_year_is_refused_by_name() -> None:
    """`build` refuses before the chain is asked (D-229): a report without pricing has
    nothing to say, and the chain's own refusal would speak of a trajectory instead."""
    with pytest.raises(DebtError, match="un rapport sans chiffrage"):
        _build([])


def test_the_aged_view_is_the_headline_and_the_frozen_one_stands_beside_it() -> None:
    rapport = _build(annuel.price_years(YEARS, _stub, basis_for=lambda y: "legislated"))
    row = rapport.payload()["years"][-1]
    assert row["delta_aged"] > row["delta_frozen"] > 0
    assert row["mechanical_aged_eur"] == pytest.approx(_stub(2030, "vieillie"))


def test_the_population_and_the_gdp_must_inflate_at_the_same_rate() -> None:
    """THE COHERENCE GUARD. A population aged at 1,5 % of prices beside a GDP growing at
    2 % would divide the reform's euros by a denominator inflating faster than they do."""
    from impots.uprating import Uprating

    prices = annuel.price_years(YEARS, _stub, basis_for=lambda y: "legislated")
    with pytest.raises(DebtError, match="rythmes différents"):
        _build(prices, Uprating(wage=0.03, price=0.015, source="test", base_year=2024))


def test_the_uprating_takes_its_prices_from_the_growth_scenario() -> None:
    uprating = annuel.uprating_for(GROWTH, wage=0.03, source="test", base_year=2024)
    assert uprating.price == GROWTH.prices and uprating.wage == 0.03


def test_the_report_names_its_scenarios_and_carries_both_banners() -> None:
    payload = _build(annuel.price_years(YEARS, _stub,
                                        basis_for=lambda y: "reconducted")).payload()
    assert payload["spending_name"] == "Dépenses gelées en volume"
    assert payload["growth_name"] == GROWTH.name and payload["rate_name"] == HELD.name
    assert payload["banner"] == chaine.BANNER and "PAS microsimulées" in payload["debt_banner"]
    assert "rétroaction" in payload["absent"]
    assert {row["basis"] for row in payload["years"]} == {"reconducted"}


def test_the_report_names_its_theta_and_says_nothing_reads_it() -> None:
    """The command prices no behaviour: the θ is listed, every open row with it, beside
    the statement that the mechanical view does not read it."""
    payload = _build(annuel.price_years(YEARS, _stub, basis_for=lambda y: "legislated"),
                     theta=Theta(common=0.3)).payload()
    assert len(payload["theta"]) == 19 and set(payload["theta"].values()) == {0.3}  # D-256
    assert payload["theta_applied"] is False and "θ" in payload["absent"]
    assert set(payload["closed"]) == {*chaine.CLOSED, *chaine.MACRO_CHANNELS}


def test_a_report_without_a_theta_is_refused() -> None:
    with pytest.raises(ThetaError, match="aucun θ"):
        _build(annuel.price_years(YEARS, _stub, basis_for=lambda y: "legislated"),
               theta=None)
