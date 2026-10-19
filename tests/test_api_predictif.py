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
from impots.predictif import indices as indices_module
from macro_cases import index_rows_store, synthetic_macro_store

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
        return SimpleNamespace(cost=5e9, view="figee", note="sous-échantillon de 20 000",
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
    assert len(body["theta"]) == 14 and body["theta"]["eti_all"] == 0.1  # D-222
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


# --------------------------------------------------------------------------- #
# M6 — the indices of §7 (D-223)
# --------------------------------------------------------------------------- #
def _with_index_rows():
    return index_rows_store()


def _indices(body: dict) -> dict:
    return {i["key"]: i for i in body["indices"]}


def test_an_unknown_index_is_refused_before_the_pass(client, priced) -> None:
    response = client.post("/predictif/simulate",
                           json=_payload(indices=["dette", "emploi_total"]))
    assert response.status_code == 422 and "emploi_total" in response.json()["detail"]
    assert priced == []


def test_the_indices_ride_along_each_computed_or_saying_why(client, priced,
                                                           monkeypatch) -> None:
    """Derived by hand: 5 Md€ of income tax over the first year's GDP, 3 000 × 1,01 ×
    1,02 Md€, is 0,1618 point of the variant; consumption at θ = 1/2 is 0,81 × that in
    year one. The State's three indices are the path's own; the firm layer is listed and
    not computed; the deciles the stub does not carry are said to be missing."""
    monkeypatch.setattr(main, "_predictif_macro_store", _with_index_rows)
    body = client.post("/predictif/simulate",
                       json=_payload(macro=True, persistence="tenu")).json()
    got = _indices(body)
    assert list(got) == [s.key for s in indices_module.CATALOGUE]
    points = 5e9 / (3_000e9 * 1.01 * 1.02) * 100
    assert got["consommation"]["values"]["1"] == pytest.approx(0.81 * points)
    assert got["consommation"]["box"]["1"][0] < got["consommation"]["values"]["1"]
    assert got["revenu_disponible_reel"]["box"] is None
    assert got["dette"]["values"]["2026"] == pytest.approx(body["delta"][0])
    assert got["charge_interets"]["values"]["2026"] == 0.0
    assert got["depense_rd"]["reason"] == indices_module.FIRM_LAYER
    assert not got["revenu_disponible_deciles"]["available"]
    assert not got["emploi_smic"]["available"]
    assert got["emploi_smic"]["reason"] == indices_module.NO_BEHAVIOUR


def test_the_mesange_indices_read_without_the_loop_and_say_so_without_the_impulse(
        client, priced, monkeypatch) -> None:
    """The indices are read under Mésange's own conditions, whatever the path's spending
    rule; without the impulse there is no shock to read."""
    monkeypatch.setattr(main, "_predictif_macro_store", _with_index_rows)
    looped_off = _indices(client.post("/predictif/simulate", json=_payload(
        macro=True, spending={"rule": "part_pib_constante"})).json())
    assert looped_off["investissement_entreprises"]["available"]
    unasked = _indices(client.post("/predictif/simulate", json=_payload()).json())
    assert unasked["consommation"]["reason"] == indices_module.NO_IMPULSE
    assert unasked["solde_primaire"]["available"]


def test_an_unreadable_macro_store_the_loop_does_not_need_leaves_the_indices_absent(
        client, priced, monkeypatch) -> None:
    """Without the loop, the macro store serves the indices only: a checkout without the
    Mésange PDF says why they are missing, rather than refusing the whole path."""
    def unreadable():
        raise main.MacroSourceError("insee_G2017-04_mesange.pdf introuvable")

    monkeypatch.setattr(main, "_predictif_macro_store", unreadable)
    response = client.post("/predictif/simulate", json=_payload(
        macro=True, spending={"rule": "part_pib_constante"}))
    assert response.status_code == 200, response.text
    got = _indices(response.json())
    assert "illisible" in got["consommation"]["reason"]
    assert "introuvable" in got["emploi_marchand"]["reason"]


# --------------------------------------------------------------------------- #
# The view the first year is priced in (D-225)
# --------------------------------------------------------------------------- #
def test_the_first_year_is_priced_on_the_frozen_population_and_says_so(
        client, monkeypatch) -> None:
    """The real `_price_first_year`, its pass stubbed one layer down: it hands the pass
    the population as loaded — 2026 law on 2024 incomes, nothing aged, « figée » — and
    the response names that view, in its own field and in its note. The command prices
    « vieillie » too and puts it first (D-216): without the name, the two 2026 figures
    read as one. Ageing the frame here fails the first assertion, and the name must then
    change with the numbers."""
    population = object()
    passed: list = []

    def run(request, frame):
        passed.append(frame)
        return (SimpleNamespace(households=None),
                SimpleNamespace(reform_cost=5e9, deciles=[]))

    monkeypatch.setattr(main, "_population_frame", lambda: population)
    monkeypatch.setattr(main, "_run_population", run)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    response = client.post("/predictif/simulate", json=_payload())
    assert response.status_code == 200, response.text
    assert len(passed) == 1 and passed[0] is population
    body = response.json()
    assert body["mechanical_first_year_eur"] == 5e9
    assert body["population_view"] == "figee"
    note = body["population_note"]
    assert "« figée »" in note and "2026" in note and "non vieillis" in note
    assert "« vieillie »" in note and "D-216" in note
