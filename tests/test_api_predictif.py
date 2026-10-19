"""Phase 9 M1 — `POST /predictif/simulate`, the fast version (PHASE9_SPEC §3.4, M0 R3).

The population pass is replaced by a stub that records what it was asked: the endpoint's
own logic — the refusals, the first projected year, the carry convention, what is absent,
and since M2 the θ it must be given (D-217) — is what these tests hold, in seconds and
without data. The pass itself has its own tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from impots.api import main
from impots.dette import maturite, reference
from impots.predictif import chaine
from macro_cases import synthetic_macro_store

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = {"name": "Croissance réelle 1 %, prix 2 %", "real": 0.01, "prices": 0.02}
HELD = {"name": "Taux implicite tenu à son niveau de 2025", "kind": "implicite_tenu"}
#: A barème with a higher top rate: the ETI rows claim `ir_bareme`, so the θ box moves.
TOP_RATE_50 = {"ir_bareme": [
    {"threshold": 0, "rate": 0.00}, {"threshold": 11497, "rate": 0.11},
    {"threshold": 29315, "rate": 0.30}, {"threshold": 83823, "rate": 0.41},
    {"threshold": 180294, "rate": 0.50}]}


def _payload(**overrides) -> dict:
    payload = {"reform": {"abattement_pensions_plafond": 0.0},
               "spending": {"rule": "gele_en_volume"}, "growth": GROWTH, "rate": HELD,
               "horizon": 10, "theta": {"common": 0.5}}
    payload.update(overrides)
    return payload


def _households() -> dict:
    """What `band.compute` reads for C1: forty households whose marginal rate rises."""
    rng = np.random.default_rng(3)
    base = rng.uniform(10_000, 200_000, 40)
    emtr = rng.uniform(0.1, 0.45, 40)
    return {"taxable_base": base, "weights": np.full(40, 1_000.0), "emtr_baseline": emtr,
            "emtr_reform": emtr + 0.03, "top_decile": base > np.quantile(base, 0.9)}


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def priced(monkeypatch) -> list:
    """The population pass, stubbed: 5 Md€ of cost, synthetic households when behaviour
    is asked for, and the requests it received."""
    seen: list = []

    def stub(request, *, macro=False):
        seen.append(request)
        # A 5 Md€ income-tax cut, and a transfer the loop cannot read, when asked for.
        return SimpleNamespace(cost=5e9, note="sous-échantillon de 20 000",
                               inputs=_households() if request.behavioural else None,
                               impulse={"impot_sur_le_revenu": 5e9} if macro else None,
                               uncovered={"rsa": "transfert"} if macro else {})

    monkeypatch.setattr(main, "_price_first_year", stub)
    monkeypatch.setattr(main, "_predictif_macro_store", synthetic_macro_store)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    return seen


def test_a_complete_request_prices_the_first_year_and_carries_it(client, priced) -> None:
    response = client.post("/predictif/simulate", json=_payload())
    assert response.status_code == 200, response.text
    body = response.json()
    assert [r.year for r in priced] == [2026]
    assert body["years"] == list(range(2026, 2036))
    assert body["priced_years"] == [2026]
    assert body["carried_years"] == list(range(2027, 2036))
    assert chaine.CARRY_LABEL in body["conventions"]
    assert body["delta"][0] == pytest.approx(5e9 / (3_000e9 * 1.01 * 1.02))
    assert body["mechanical_first_year_eur"] == 5e9
    assert body["spending_name"] == "Dépenses gelées en volume"


def test_what_is_absent_is_said_and_the_banners_ride_along(client, priced) -> None:
    body = client.post("/predictif/simulate", json=_payload()).json()
    assert "rétroaction" in body["absent"]
    feedback = next(s for s in body["slices"] if s["source"] == "eventail")
    assert feedback["computed"] is False and feedback["low"] == []
    assert body["banner"] == chaine.BANNER
    assert "PAS microsimulées" in body["debt_banner"]


def test_requested_behaviour_puts_the_path_at_theta_inside_its_box(client, priced) -> None:
    body = client.post("/predictif/simulate",
                       json=_payload(reform=TOP_RATE_50, behavioural=True)).json()
    band = next(s for s in body["slices"] if s["source"] == "bande")
    assert band["computed"] is True and len(band["low"]) == 10
    assert all(lo <= c <= hi for lo, c, hi in zip(band["low"], body["reform"],
                                                  band["high"], strict=True))
    behaviour = body["behaviour"]
    assert behaviour["claimed"] == ["eti_all", "eti_top_decile"]
    low, high = behaviour["box_first_year_eur"]
    assert low < behaviour["receipts_first_year_eur"] < high < 0
    # The rates rise, so the base shrinks: the path at θ sits above the mechanical one.
    assert body["delta"][0] > body["delta_mechanical"][0] > 0
    assert body["theta_applied"] is True


def test_the_theta_is_listed_for_every_open_row_and_the_closed_say_why(
        client, priced) -> None:
    body = client.post("/predictif/simulate", json=_payload(
        theta={"common": 0.5, "rows": {"eti_all": 0.1}})).json()
    assert len(body["theta"]) == 13 and body["theta"]["eti_all"] == 0.1  # D-221
    assert body["theta_applied"] is False and "θ" in body["absent"]
    assert "dividendes" in body["closed"] and all(body["closed"].values())
    assert body["behaviour"] is None


def test_a_request_without_theta_is_refused_before_any_pass(client, priced) -> None:
    """GUARD 1. No default θ — not even 1/2, which the page may prefill only if it shows
    it."""
    payload = _payload()
    del payload["theta"]
    assert client.post("/predictif/simulate", json=payload).status_code == 422
    response = client.post("/predictif/simulate", json=_payload(theta={}))
    assert response.status_code == 422 and "Aucun défaut" in response.json()["detail"]
    assert priced == []


@pytest.mark.parametrize("theta, needle", [
    ({"common": 1.2}, "écrêté"),
    ({"common": 0.5, "rows": {"eti_al": 0.2}}, "inconnues"),
])
def test_a_theta_out_of_range_or_for_an_unknown_row_is_refused_by_name(
        client, priced, theta: dict, needle: str) -> None:
    response = client.post("/predictif/simulate", json=_payload(theta=theta))
    assert response.status_code == 422 and needle in response.json()["detail"]
    assert priced == []


@pytest.mark.parametrize("missing", ["spending", "growth", "rate", "horizon"])
def test_no_hypothesis_has_a_default(client, priced, missing: str) -> None:
    payload = _payload()
    del payload[missing]
    assert client.post("/predictif/simulate", json=payload).status_code == 422
    assert priced == []


def test_a_scenario_name_claiming_likelihood_is_refused(client, priced) -> None:
    growth = {**GROWTH, "name": "Croissance la plus probable"}
    response = client.post("/predictif/simulate", json=_payload(growth=growth))
    assert response.status_code == 422
    assert "probabilité" in response.json()["detail"]


def test_a_shipped_rule_refuses_a_name_it_would_ignore(client, priced) -> None:
    spending = {"rule": "gele_en_volume", "name": "Autre chose"}
    response = client.post("/predictif/simulate", json=_payload(spending=spending))
    assert response.status_code == 422 and "ignoré" in response.json()["detail"]


def test_the_market_scenario_without_the_aft_file_is_refused_by_name(
        client, priced, monkeypatch) -> None:
    def missing():
        raise maturite.MaturityError("bulletin AFT absent")

    monkeypatch.setattr(maturite, "load_block1", missing)
    rate = {"name": "Refinancement à 4 %", "kind": "marche", "market_rate": 0.04}
    response = client.post("/predictif/simulate", json=_payload(rate=rate))
    assert response.status_code == 503
    assert "indisponibles" in response.json()["detail"]
    assert priced == []


# --------------------------------------------------------------------------- #
# M3 — the loop, asked for by `macro` (D-218)
# --------------------------------------------------------------------------- #
def test_the_loop_runs_under_frozen_spending_and_lists_the_macro_theta(client, priced) -> None:
    body = client.post("/predictif/simulate",
                       json=_payload(macro=True, persistence="tenu")).json()
    assert len(body["gdp_gap"]) == 10 and body["gdp_gap"][0] > 0
    assert body["theta"]["multiplicateur_macro"] == 0.5
    assert 0 < body["delta"][0] < body["delta_mechanical"][0]
    eventail = next(s for s in body["slices"] if s["source"] == "eventail")
    assert eventail["computed"] is True
    assert "rsa" in body["absent"]["rétroaction, instruments non couverts"]
    assert body["persistence"] == "tenu"


def test_the_loop_past_three_years_without_persistence_is_refused_before_the_pass(
        client, priced) -> None:
    response = client.post("/predictif/simulate", json=_payload(macro=True))
    assert response.status_code == 422 and "persistance" in response.json()["detail"]
    assert priced == []
    short = client.post("/predictif/simulate", json=_payload(macro=True, horizon=3))
    assert short.status_code == 200 and len(short.json()["gdp_gap"]) == 3


def test_a_persistence_without_the_loop_is_refused_before_the_pass(client, priced) -> None:
    response = client.post("/predictif/simulate", json=_payload(persistence="eteint"))
    assert response.status_code == 422 and "ignorée" in response.json()["detail"]
    assert priced == []


def test_under_a_gdp_share_rule_the_loop_is_absent_and_says_why(client, priced) -> None:
    body = client.post("/predictif/simulate", json=_payload(
        macro=True, spending={"rule": "part_pib_constante"})).json()
    assert "note 70" in body["absent"]["rétroaction"]
    assert body["gdp_gap"] is None and "multiplicateur_macro" not in body["theta"]


def test_the_loop_without_a_macro_theta_is_refused_before_the_pass(client, priced) -> None:
    rows = {"eti_all": 0.5, "eti_top_decile": 0.5, "employment_elasticity_smic": 0.5,
            "passthrough_benefit_linked": 0.5, "passthrough_unlinked": 0.5,
            "production_tax_investment": 0.5, "wealth_disclosure_growth_effect_pp": 0.5,
            "wealth_tax_rate_elasticity": 0.5}
    response = client.post("/predictif/simulate", json=_payload(
        macro=True, horizon=3, theta={"rows": rows}))
    assert response.status_code == 422 and "multiplicateur_macro" in response.json()["detail"]
    assert priced == []
