"""Phase 9 M1 — `POST /predictif/simulate`, the fast version (PHASE9_SPEC §3.4, M0 R3).

The population pass is replaced by a stub that records what it was asked: the endpoint's
own logic — the refusals, the first projected year, the carry convention, what is absent —
is what these tests hold, in seconds and without data. The pass itself has its own tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from impots.api import main
from impots.dette import maturite, reference
from impots.predictif import chaine

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = {"name": "Croissance réelle 1 %, prix 2 %", "real": 0.01, "prices": 0.02}
HELD = {"name": "Taux implicite tenu à son niveau de 2025", "kind": "implicite_tenu"}


def _payload(**overrides) -> dict:
    payload = {"reform": {"abattement_pensions_plafond": 0.0},
               "spending": {"rule": "gele_en_volume"}, "growth": GROWTH, "rate": HELD,
               "horizon": 10}
    payload.update(overrides)
    return payload


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def priced(monkeypatch) -> list:
    """The population pass, stubbed: 5 Md€ of cost, and the requests it received."""
    seen: list = []

    def stub(request):
        seen.append(request)
        band = (SimpleNamespace(band=SimpleNamespace(p10=-6e9, p50=-5e9, p90=-3e9))
                if request.behavioural else None)
        return SimpleNamespace(reform_cost=5e9, behavioural=band,
                               meta=SimpleNamespace(note="sous-échantillon de 20 000"))

    monkeypatch.setattr(main, "population_simulate", stub)
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


def test_a_requested_band_reaches_the_behavioural_slice(client, priced) -> None:
    body = client.post("/predictif/simulate", json=_payload(behavioural=True)).json()
    band = next(s for s in body["slices"] if s["source"] == "bande")
    assert band["computed"] is True and len(band["low"]) == 10
    assert all(lo <= c <= hi for lo, c, hi in zip(band["low"], body["reform"],
                                                  band["high"], strict=True))


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
