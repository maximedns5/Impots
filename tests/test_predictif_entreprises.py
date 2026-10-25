"""Phase 11 M1 — a firm reform enters the predictive chain (PHASE11_SPEC §3, D-244).

What is held here, on the committed firm fixture and without household data: the firm
layer's cost for the first year joins the households', each named; a firm reform alone
runs no population pass; its taxes have no Mésange variant, so the loop says them
uncovered rather than reading them as nothing; the CIR stays out of the chain; and the
explorer walks firm knobs, passing the firm part only to the bundles that have one.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from exploration_cases import exploration_request as _request
from exploration_cases import run_search
from impots.api import main
from impots.api.schemas import (
    ExplorationRequest,
    PopulationSimulateRequest,
    PredictifResponse,
    ReformSpec,
)
from impots.dette import reference
from impots.entreprises import aggregate as firm_aggregate
from impots.entreprises import runner as firm_runner
from impots.entreprises.reforms import FirmReformSpec
from impots.predictif import indices as indices_module
from impots.predictif import recherche
from impots.predictif.exploration import Priced
from macro_cases import synthetic_macro_store

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
IS_24 = FirmReformSpec(is_taux_normal=0.24)
PAYLOAD = {"spending": {"rule": "gele_en_volume"},
           "growth": {"name": "Croissance réelle 1 %, prix 2 %", "real": 0.01,
                      "prices": 0.02},
           "rate": {"name": "Taux implicite tenu à son niveau de 2025",
                    "kind": "implicite_tenu"},
           "horizon": 3, "theta": {"common": 0.5},
           "uprating": {"wage": 0.03, "source": "3 % ronds"}}


@pytest.fixture(scope="module", autouse=True)
def firm_population() -> None:
    """The firm population from the committed fixture, as `tests/test_api.py` builds it."""
    from impots.entreprises.build import FIXTURE_CELLS, PROCESSED, build

    if not (PROCESSED / "firms_fixture.parquet").exists():
        build(FIXTURE_CELLS)


#: The aged view's multiplier in these tests: the fixture names no year, and the real
#: factor reads the national accounts (`test_firmes_vues.py` holds it).
AGED = 1.08
REAL_AGING = main._firm_aging_factor


@pytest.fixture(autouse=True)
def aged_by(monkeypatch) -> list:
    """The aged view's factor, stubbed; each call recorded with the growth it was given."""
    calls: list = []

    def factor(year, growth):
        calls.append((year, growth))
        return AGED

    monkeypatch.setattr(main, "_firm_aging_factor", factor)
    return calls


def _firm_cost(spec: FirmReformSpec, year: int = 2026) -> float:
    result = firm_runner.run(main._firm_population(), year=year, reform=spec)
    return float(firm_aggregate.aggregate(result.firms).reform_cost)


def _no_household_pass(*args, **kwargs):
    raise AssertionError("une réforme des seules entreprises ne lance aucune passe de "
                         "population")


def _households(cost: float):
    """The households' pass, stubbed: `cost`, an income-tax impulse when the loop runs."""
    def stub(request, *, uprating, macro, view):
        return SimpleNamespace(cost=cost, inputs=None, view=view, note="ménages",
                               impulse={"impot_sur_le_revenu": cost} if macro else None,
                               uncovered={}, deciles=[])
    return stub


def test_a_firm_reform_alone_is_the_firm_layers_cost_and_no_population_pass(
        monkeypatch) -> None:
    monkeypatch.setattr(main, "_price_households", _no_household_pass)
    first = main._price_first_year(main._first_year_request(ReformSpec(), 2026, False),
                                   uprating=None, macro=True, firm_reform=IS_24)
    cost = _firm_cost(IS_24) * AGED
    assert cost > 0
    assert first.cost == pytest.approx(cost)
    assert first.layers == {"menages": 0.0, "entreprises": pytest.approx(cost)}
    assert first.impulse == {}
    assert first.uncovered["impot_societes"] == main.FIRM_NO_VARIANT
    assert main.FIRM_TOTAL not in first.uncovered
    assert "vue vieillie" in first.note and "×1,0800" in first.note
    assert "exercice" in first.note
    assert "synthétiques" in first.note


@pytest.mark.parametrize("view", ["vieillie", "figee"])
def test_the_two_layers_add_up_and_the_households_keep_their_loop(monkeypatch,
                                                                  view: str) -> None:
    """A mixed reform: the households' pass as it always was, the firm cost added, the
    firm taxes listed as uncovered beside the income tax the loop reads."""
    monkeypatch.setattr(main, "_price_households", _households(5e9))
    first = main._price_first_year(
        PopulationSimulateRequest(reform=ReformSpec(decote_taux=0.4), year=2026),
        uprating=None, macro=True, view=view, firm_reform=IS_24)
    cost = _firm_cost(IS_24) * (AGED if view == "vieillie" else 1.0)
    assert first.cost == pytest.approx(5e9 + cost)
    assert first.layers == {"menages": 5e9, "entreprises": pytest.approx(cost)}
    assert first.impulse == {"impot_sur_le_revenu": 5e9}
    assert set(first.uncovered) >= {"impot_societes"}
    assert first.note.startswith("ménages")


def test_a_household_reform_goes_through_the_call_it_always_did(monkeypatch) -> None:
    """No firm part, no keyword: the seam's stubs in every other test are called exactly
    as before, and an empty firm reform is no firm reform."""
    assert main._firm_part(None) == {} and main._firm_part(FirmReformSpec()) == {}
    seen = []

    def households(request, *, uprating, macro, view):
        seen.append(request.reform)
        return SimpleNamespace(cost=1e9, view=view)

    monkeypatch.setattr(main, "_price_households", households)
    first = main._price_first_year(
        PopulationSimulateRequest(reform=ReformSpec(decote_taux=0.4), year=2026),
        uprating=None, firm_reform=FirmReformSpec())
    assert first.cost == 1e9 and not hasattr(first, "layers") and len(seen) == 1


@pytest.fixture
def chain(monkeypatch):
    monkeypatch.setattr(main, "_price_households", _no_household_pass)
    monkeypatch.setattr(main, "_predictif_macro_store", synthetic_macro_store)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    with TestClient(main.app) as client:
        yield client


def test_a_firm_reform_has_its_debt_path_and_says_the_loop_absent(chain) -> None:
    response = chain.post("/predictif/simulate", json={
        **PAYLOAD, "firm_reform": {"is_taux_normal": 0.24}, "macro": True})
    assert response.status_code == 200, response.text
    body = response.json()
    cost = _firm_cost(IS_24) * AGED
    assert body["mechanical_first_year_eur"] == pytest.approx(cost)
    assert body["mechanical_first_year_by_layer"] == {
        "menages": 0.0, "entreprises": pytest.approx(cost)}
    assert body["delta"][0] > 0
    assert "impot_societes" in body["absent"]["rétroaction"]
    assert "sans variante dans Mésange" in body["absent"]["rétroaction"]
    assert "vue vieillie" in body["population_note"]
    firm_rows = [i for i in body["indices"] if i["stage"] == indices_module.FIRMES]
    assert firm_rows and all(i["reason"] == indices_module.FIRM_PENDING
                             for i in firm_rows)


@pytest.mark.parametrize("payload, needle", [
    ({}, "Une réforme est requise"),
    ({"firm_reform": {}}, "Une réforme est requise"),
    ({"firm_reform": {"cir_taux": 0.2}}, "hors de la chaîne"),
    ({"firm_reform": {"is_taux_normal": 0.24, "cir_taux_au_dela": 0.04}},
     "hors de la chaîne"),
])
def test_a_firm_request_the_chain_cannot_price_is_refused(chain, payload: dict,
                                                          needle: str) -> None:
    """Nothing to price, or the CIR, whose créance is not a year's receipts (D-222)."""
    response = chain.post("/predictif/simulate", json={**PAYLOAD, **payload})
    assert response.status_code == 422
    assert needle in response.text


SEARCH_IS = [{"knob": "is_taux_normal", "low": 0.22, "high": 0.24, "step": 0.01}]


def _firm_price(seen: list):
    def price(reform, view, firm=None):
        seen.append((reform.model_dump(exclude_none=True),
                     firm.model_dump(exclude_none=True) if firm else None, view))
        cost = 1e9 * (0.25 - (firm.is_taux_normal if firm else 0.25)) * 100
        return Priced(cost=cost, inputs=None, impulse=None)
    return price


def test_the_explorer_walks_firm_knobs_and_passes_only_the_firm_part() -> None:
    seen: list = []
    request = ExplorationRequest.model_validate(_request(bounds=SEARCH_IS, macro=False))
    report = recherche.run(request, price=_firm_price(seen),
                           hypotheses=main._predictif_hypotheses(request), start=START,
                           commit="c" * 40, computed="2026-10-24")
    assert {(r == {}, f["is_taux_normal"], v) for r, f, v in seen} == {
        (True, rate, view) for rate in (0.22, 0.23, 0.24) for view in ("vieillie", "figee")}
    evaluations = report["searches"][0]["evaluations"]
    assert [e["knobs"] for e in evaluations] == [
        {"is_taux_normal": 0.22}, {"is_taux_normal": 0.23}, {"is_taux_normal": 0.24}]
    assert evaluations[0]["cost_aged_eur"] == pytest.approx(3e9)
    assert "firm_base" not in report["request"]


def test_a_household_search_still_calls_price_with_two_arguments() -> None:
    """The household search's request and calls read as they always did: no `firm_base`
    in the report's request, no third argument to `price`."""
    seen: list = []
    report = run_search(_request(), seen=seen)
    assert seen and "firm_base" not in report["request"]


@pytest.mark.parametrize("overrides, needle", [
    ({"bounds": SEARCH_IS, "firm_base": {"is_taux_normal": 0.25}},
     "fixé aussi dans `firm_base`"),
    ({"bounds": [{"knob": "cir_taux", "low": 0.2, "high": 0.3, "step": 0.1}]},
     "hors de la chaîne"),
    ({"bounds": SEARCH_IS, "firm_base": {"cir_taux": 0.2}}, "hors de la chaîne"),
    ({"bounds": [{"knob": "cebge_seuils_et_taux", "low": 0, "high": 1, "step": 1}]},
     "pas un nombre"),
])
def test_a_firm_grid_the_request_cannot_honour_is_refused(overrides: dict,
                                                          needle: str) -> None:
    with pytest.raises(ValidationError, match=needle):
        ExplorationRequest.model_validate(_request(**overrides))


def test_a_firm_bundle_the_firm_reform_refuses_stops_before_the_first_pass() -> None:
    """A reduced rate above the normal one is refused by `FirmReformSpec`, at the grid's
    check, before any pass."""
    request = ExplorationRequest.model_validate(_request(
        bounds=[{"knob": "is_taux_normal", "low": 0.14, "high": 0.14, "step": 0.01}],
        firm_base={"is_taux_reduit": 0.15}))
    with pytest.raises(recherche.RechercheError, match="avant toute passe"):
        recherche.check_grid(request)


#: Two firm reforms the layer itself refuses: a year before the scalar IS rate (2022), and
#: a CEBGE revived in a year where it still exists (D-044).
REVIVED_CEBGE = FirmReformSpec(
    cebge_seuils_et_taux=[{"seuil_ca": 1e9, "taux": 0.2}, {"seuil_ca": 3e9, "taux": 0.4}],
    cebge_prorogation_largeur=1e8)


@pytest.mark.parametrize("year, spec, status, needle", [
    (2021, IS_24, 500, "ne sait pas chiffrer 2021"),
    (2026, REVIVED_CEBGE, 422, "existe déjà"),
], ids=["annee", "cebge"])
def test_a_firm_pass_the_layer_refuses_keeps_its_status_and_reason(year: int,
                                                                   spec: FirmReformSpec,
                                                                   status: int,
                                                                   needle: str) -> None:
    """The firm layer's own refusals reach the predictive caller as `/entreprises/simulate`
    gives them: a year it cannot price is the server's limit, a reform the law refuses
    is the request's fault, and each keeps its reason."""
    with pytest.raises(HTTPException) as caught:
        main._firm_first_year(spec, year)
    assert caught.value.status_code == status
    assert needle in str(caught.value.detail)


def test_a_response_whose_cost_is_not_its_layers_sum_refuses_to_exist(chain) -> None:
    """PHASE11_SPEC §10, guard 8: the first year's cost is the households' plus the firms',
    each named. A response whose total is not that sum, which leaves its layers out, or
    names a layer the chain has not, refuses to exist."""
    body = chain.post("/predictif/simulate", json={
        **PAYLOAD, "firm_reform": {"is_taux_normal": 0.24}}).json()
    PredictifResponse.model_validate(body)
    layers = body["mechanical_first_year_by_layer"]
    with pytest.raises(ValidationError, match="somme de ses couches"):
        PredictifResponse.model_validate(
            {**body, "mechanical_first_year_by_layer": {**layers, "menages": 1e9}})
    with pytest.raises(ValidationError, match="couche inconnue"):
        PredictifResponse.model_validate(
            {**body, "mechanical_first_year_by_layer": {**layers, "etat": 0.0}})
    with pytest.raises(ValidationError, match="mechanical_first_year_by_layer"):
        PredictifResponse.model_validate(
            {k: v for k, v in body.items() if k != "mechanical_first_year_by_layer"})


def test_the_is_gdp_index_stands_beside_the_debt_and_never_in_it(chain) -> None:
    """D-246: a point of IS cut has its GDP gap at θ, a ten-year ramp, while the debt path
    reads no GDP effect at all — no loop, and D-218 gives none without one."""
    body = chain.post("/predictif/simulate", json={
        **PAYLOAD, "firm_reform": {"is_taux_normal": 0.24}, "macro": True}).json()
    index = next(i for i in body["indices"] if i["key"] == "pib_is")
    assert index["available"], index["reason"]
    assert index["values"] == {"2026": pytest.approx(0.00945),
                               "2027": pytest.approx(0.0189),
                               "2028": pytest.approx(0.02835)}
    assert index["box"]["2028"] == [pytest.approx(-0.0003), pytest.approx(0.057)]
    assert body["gdp_gap"] is None and body["feedback_primary"] is None
    assert body["delta"] == pytest.approx(body["delta_mechanical"])
    household = chain.post("/predictif/simulate", json={
        **PAYLOAD, "firm_reform": {"cs_taux": 0.02}}).json()
    index = next(i for i in household["indices"] if i["key"] == "pib_is")
    assert not index["available"] and index["reason"] == indices_module.NO_IS_RATE


def test_the_aged_view_follows_gdp_and_a_vintage_without_a_year_has_none(
        monkeypatch) -> None:
    """D-246: the frozen view is the vintage as it is; the aged view multiplies it by the
    scenario's nominal GDP over the vintage's — and the fixture, which names no year, is
    refused by name in that view rather than given one."""
    cost = _firm_cost(IS_24)
    frozen = main._firm_first_year(IS_24, 2026, view="figee")
    assert frozen.cost == pytest.approx(cost) and frozen.factor is None
    assert "vue figée" in frozen.note
    aged = main._firm_first_year(IS_24, 2026)
    assert aged.cost == pytest.approx(cost * AGED)
    assert aged.deltas["impot_societes"] == pytest.approx(
        frozen.deltas["impot_societes"] * AGED)
    monkeypatch.setattr(main, "_firm_aging_factor", REAL_AGING)
    with pytest.raises(HTTPException) as caught:
        main._firm_first_year(IS_24, 2026)
    assert caught.value.status_code == 422
    assert "n'a pas d'année" in str(caught.value.detail)
    assert main._firm_first_year(IS_24, 2026, view="figee").cost == pytest.approx(cost)


def test_the_aged_view_is_given_the_requests_growth(chain, aged_by) -> None:
    """The aged firm view follows the scenario's nominal GDP: the request's growth, not
    one the tool would choose (D-246)."""
    chain.post("/predictif/simulate", json={**PAYLOAD,
                                            "firm_reform": {"is_taux_normal": 0.24}})
    year, growth = aged_by[-1]
    assert year == 2026 and (growth.real, growth.prices) == (0.01, 0.02)


def test_the_explorer_command_gives_the_firm_pass_its_growth(monkeypatch,
                                                             tmp_path) -> None:
    import json

    from impots.population import cli

    seen: list = []

    def stub(request, *, uprating, macro=False, view="vieillie", firm_reform=None,
             growth=None):
        seen.append((view, firm_reform, growth))
        return SimpleNamespace(cost=1e9, inputs=None, impulse=None, uncovered={},
                               deciles=[], view=view, note="")

    monkeypatch.setattr(main, "_price_first_year", stub)
    monkeypatch.setattr(main, "_predictif_macro_store", synthetic_macro_store)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    monkeypatch.setattr(recherche, "code_state", lambda: ("c" * 40, False))
    payload = _request(bounds=SEARCH_IS, macro=False)
    path = tmp_path / "requete.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert cli.main(["exploration", str(path), "--out-dir", str(tmp_path)]) == 0
    assert seen and all(f is not None for _, f, _ in seen)
    assert {(g.real, g.prices) for _, _, g in seen} == {
        (payload["growth"]["real"], payload["growth"]["prices"])}


def test_a_firm_pass_in_a_view_that_does_not_exist_is_refused() -> None:
    with pytest.raises(ValueError, match="inconnue"):
        main._firm_first_year(IS_24, 2026, view="gelee")
