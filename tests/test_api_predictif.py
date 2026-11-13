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

from impots import service
from impots.api import main
from impots.dette import maturite, reference
from impots.predictif import chaine
from impots.predictif import indices as indices_module
from macro_cases import index_rows_store, synthetic_macro_store

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = {"name": "Croissance réelle 1 %, prix 2 %", "real": 0.01, "prices": 0.02}
HELD = {"name": "Taux implicite tenu à son niveau de 2025", "kind": "implicite_tenu"}
#: The wage index the first year's population is aged with (D-226); prices are GROWTH's.
WAGES = {"wage": 0.03, "source": "3 % ronds, le rythme du PIB nominal du scénario"}
#: A barème with a higher top rate: the ETI rows claim `ir_bareme`, so the θ box moves.
TOP_RATE_50 = {"ir_bareme": [
    {"threshold": 0, "rate": 0.00}, {"threshold": 11497, "rate": 0.11},
    {"threshold": 29315, "rate": 0.30}, {"threshold": 83823, "rate": 0.41},
    {"threshold": 180294, "rate": 0.50}]}


def _payload(**overrides) -> dict:
    payload = {"reform": {"abattement_pensions_plafond": 0.0},
               "spending": {"rule": "gele_en_volume"}, "growth": GROWTH, "rate": HELD,
               "horizon": 10, "theta": {"common": 0.5}, "uprating": WAGES}
    payload.update(overrides)
    return payload


def _households() -> dict:
    """What `band.compute` reads for C1: forty households whose marginal rate rises."""
    rng = np.random.default_rng(3)
    base = rng.uniform(10_000, 200_000, 40)
    emtr = rng.uniform(0.1, 0.45, 40)
    return {"taxable_base": base, "weights": np.full(40, 1_000.0), "emtr_baseline": emtr,
            "emtr_reform": emtr + 0.03, "emtr_ir_baseline": emtr,
            "emtr_ir_reform": emtr + 0.03, "top_decile": base > np.quantile(base, 0.9)}


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def priced(monkeypatch) -> list:
    """The population pass, stubbed: 5 Md€ of cost, synthetic households when behaviour
    is asked for, and the requests it received."""
    seen: list = []

    def stub(request, *, uprating, macro=False):
        seen.append(request)
        # A 5 Md€ income-tax cut, and a transfer the loop cannot read, when asked for.
        return SimpleNamespace(cost=5e9, view="vieillie", note="sous-échantillon de 20 000",
                               inputs=_households() if request.behavioural else None,
                               impulse={"impot_sur_le_revenu": 5e9} if macro else None,
                               uncovered={"rsa": "transfert"} if macro else {})

    monkeypatch.setattr(service, "price_first_year", stub)
    monkeypatch.setattr(service, "predictif_macro_store", synthetic_macro_store)
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
    assert len(body["theta"]) == 20 and body["theta"]["eti_all"] == 0.1  # D-252, D-263
    assert body["theta_applied"] is False and "θ" in body["absent"]
    # The dividends left the closed list in D-250: C10 is open since D-249.
    assert "transferts" in body["closed"] and all(body["closed"].values())
    assert "dividendes" not in body["closed"]
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


@pytest.mark.parametrize("missing", ["spending", "growth", "rate", "horizon", "uprating"])
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


def test_past_three_years_without_a_persistence_both_stand_side_by_side(
        client, priced) -> None:
    """D-230, the owner's choice on §4.5: unnamed, the persistence is not asked for nor
    defaulted — both scenarios are computed from the ONE pass and returned side by side,
    and the response carries no path of its own, so that neither reads as the lead."""
    response = client.post("/predictif/simulate", json=_payload(macro=True))
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(priced) == 1, "both scenarios must come from the same population pass"
    both = {p["persistence"]: p for p in body["side_by_side"]}
    assert sorted(both) == ["eteint", "lue", "tenu"]
    assert both["eteint"]["label"] == "Effet macro éteint après trois ans"
    for field in ("reform", "delta", "delta_primary", "gdp_gap", "feedback_primary",
                  "persistence"):
        assert body[field] is None, field
    assert body["slices"] == []
    # Mésange is read to three years: there the two are one path, and past it they part.
    off, held = both["eteint"], both["tenu"]
    assert off["delta"][:3] == pytest.approx(held["delta"][:3])
    assert off["gdp_gap"][3:] == pytest.approx([0.0] * 7, abs=1e-15)
    assert held["gdp_gap"][3:] == pytest.approx([held["gdp_gap"][2]] * 7)
    assert off["delta"][-1] != pytest.approx(held["delta"][-1])
    # each path's own convention past three years, and none of them in the shared list
    assert any("éteint" in c for c in off["conventions"])
    assert not any("Au-delà de trois ans" in c for c in body["conventions"])
    short = client.post("/predictif/simulate", json=_payload(macro=True, horizon=3))
    assert short.status_code == 200 and len(short.json()["gdp_gap"]) == 3
    assert short.json()["side_by_side"] == []


def test_a_named_persistence_gives_its_one_path_and_nothing_side_by_side(
        client, priced) -> None:
    body = client.post("/predictif/simulate",
                       json=_payload(macro=True, persistence="eteint")).json()
    assert body["persistence"] == "eteint" and body["side_by_side"] == []
    assert len(body["delta"]) == 10


def test_side_by_side_the_debt_indices_are_each_paths_own(client, priced) -> None:
    """The balance, debt and interest indices depend on the path: listed with each
    scenario, and in the response as carried by them, never as one scenario's."""
    body = client.post("/predictif/simulate", json=_payload(macro=True)).json()
    shared = {i["key"]: i for i in body["indices"]}
    assert not shared["dette"]["available"]
    assert "côte à côte" in shared["dette"]["reason"]
    for path in body["side_by_side"]:
        own = {i["key"]: i for i in path["indices"]}
        assert set(own) == {"solde_primaire", "dette", "charge_interets"}
        assert own["dette"]["values"]["2035"] == pytest.approx(path["delta"][-1])


def test_a_response_with_one_scenario_in_the_lead_refuses_to_exist(client,
                                                                   priced) -> None:
    """The schema's own guard: side by side, a path of the response's own would be one
    of the two promoted to the headline — a default by placement."""
    from pydantic import ValidationError

    from impots.api.schemas import PredictifResponse

    body = client.post("/predictif/simulate", json=_payload(macro=True)).json()
    led = {**body, "delta": body["side_by_side"][0]["delta"]}
    with pytest.raises(ValidationError, match="aucune trajectoire en propre"):
        PredictifResponse.model_validate(led)
    one = {**body, "side_by_side": body["side_by_side"][:1]}
    with pytest.raises(ValidationError, match="chacun une fois"):
        PredictifResponse.model_validate(one)
    with pytest.raises(ValidationError, match="ni scénarios côte à côte"):
        PredictifResponse.model_validate({**body, "side_by_side": []})


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
    monkeypatch.setattr(service, "predictif_macro_store", _with_index_rows)
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
    monkeypatch.setattr(service, "predictif_macro_store", _with_index_rows)
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
        raise service.MacroSourceError("insee_G2017-04_mesange.pdf introuvable")

    monkeypatch.setattr(service, "predictif_macro_store", unreadable)
    response = client.post("/predictif/simulate", json=_payload(
        macro=True, spending={"rule": "part_pib_constante"}))
    assert response.status_code == 200, response.text
    got = _indices(response.json())
    assert "illisible" in got["consommation"]["reason"]
    assert "introuvable" in got["emploi_marchand"]["reason"]


# --------------------------------------------------------------------------- #
# The view the first year is priced in: the aged population (D-226)
# --------------------------------------------------------------------------- #
def test_the_first_year_is_priced_on_the_aged_population_and_says_so(
        client, monkeypatch) -> None:
    """The real `_price_first_year`, its pass stubbed one layer down: the population is
    aged from 2024 to 2026 before the pass — wages and unemployment on the declared wage
    index, pensions and rents on the growth scenario's prices, nothing else — and the
    response names that view, in its own field and in its note, with the caveat of an
    aged population. The command's headline is the same view (D-216)."""
    import polars as pl

    population = pl.DataFrame({
        "person_id": [0, 1], "household_id": ["h0", "h1"], "weight": [500.0, 700.0],
        "age": [40, 70], "salaire_brut_annuel": [30_000.0, 0.0],
        "chomage_annuel": [1_000.0, 0.0], "pension_annuelle": [0.0, 20_000.0], "revenu_non_salarie_annuel": [0.0, 0.0],
        "loyer_mensuel": [600.0, 0.0]})
    passed: list = []

    def run(request, frame):
        passed.append(frame)
        return (SimpleNamespace(households=None),
                SimpleNamespace(reform_cost=5e9, deciles=[],
                                employer_contribution_delta=0.0))

    monkeypatch.setattr(service, "population_frame", lambda: population)
    monkeypatch.setattr(service, "run_population", run)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    response = client.post("/predictif/simulate", json=_payload())
    assert response.status_code == 200, response.text
    (aged,) = passed
    wages, prices = 1.03 ** 2, 1.02 ** 2
    for column, factor in (("salaire_brut_annuel", wages), ("chomage_annuel", wages),
                           ("pension_annuelle", prices), ("loyer_mensuel", prices)):
        assert aged[column].to_list() == pytest.approx(
            [v * factor for v in population[column].to_list()]), column
    for column in ("person_id", "household_id", "weight", "age"):
        assert aged[column].to_list() == population[column].to_list(), column
    body = response.json()
    assert body["mechanical_first_year_eur"] == 5e9
    assert body["population_view"] == "vieillie"
    note = body["population_note"]
    assert "Vue « vieillie »" in note and "2026" in note and "D-216" in note
    assert "n'est plus calibrée" in note and WAGES["source"] in note


@pytest.mark.parametrize("uprating, needle", [
    ({"wage": 0.03, "source": "  "}, "sans source"),
    ({"wage": 3.0, "source": "salaires à 3 % par an"}, "taux annuel"),
])
def test_a_wage_index_without_a_source_or_not_annual_is_refused_before_the_pass(
        client, priced, uprating: dict, needle: str) -> None:
    """The refusal is `Uprating`'s own, which says why; 3.0 is 300 % a year, the classic
    slip for « 3 % »."""
    response = client.post("/predictif/simulate", json=_payload(uprating=uprating))
    assert response.status_code == 422 and needle in response.json()["detail"]
    assert priced == []


def test_the_behavioural_pass_on_the_aged_population_keys_its_caches_on_the_uprating(
        client, monkeypatch) -> None:
    """The EMTR caches are keyed on vintage, year, sample and reform: the aged frame
    alone does not tell them it is aged, and `/population/simulate` caches the same
    reform, year and sample on the population as built. The key must say it (D-226)."""
    import polars as pl

    from impots.behavioural import emtr as emtr_module

    population = pl.DataFrame({
        "person_id": [0], "household_id": ["h0"], "weight": [1.0], "age": [40],
        "salaire_brut_annuel": [30_000.0], "chomage_annuel": [0.0],
        "pension_annuelle": [0.0], "loyer_mensuel": [0.0],
        "revenu_non_salarie_annuel": [0.0]})
    keys: list = []

    def cached(frame, vintage, **kwargs):
        keys.append(kwargs.get("uprating_key"))
        return SimpleNamespace(with_earnings=pl.DataFrame())

    monkeypatch.setattr(service, "population_frame", lambda: population)
    monkeypatch.setattr(service, "run_population", lambda request, frame: (
        SimpleNamespace(households=None), SimpleNamespace(reform_cost=5e9, deciles=[],
                                employer_contribution_delta=0.0)))
    monkeypatch.setattr(emtr_module, "cached", cached)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    response = client.post("/predictif/simulate", json=_payload(behavioural=True))
    assert response.status_code == 200, response.text
    assert keys == ["w+0.030000_p+0.020000_b2024"]


def test_the_frozen_view_keys_its_emtr_caches_on_the_frame_it_prices(monkeypatch) -> None:
    """The frozen view prices the vintage as built: its caches are the vintage's, not
    the aged view's. Under the aged key, the view priced first wrote what both read, and
    the annual path, which prices the frozen view first, served the frozen frame's rates
    to the aged view every year (D-276)."""
    import polars as pl

    from impots.api.schemas import ReformSpec
    from impots.behavioural import emtr as emtr_module
    from impots.uprating import Uprating

    population = pl.DataFrame({
        "person_id": [0], "household_id": ["h0"], "weight": [1.0], "age": [40],
        "salaire_brut_annuel": [30_000.0], "chomage_annuel": [0.0],
        "pension_annuelle": [0.0], "loyer_mensuel": [0.0],
        "revenu_non_salarie_annuel": [0.0]})
    seen: list = []

    def cached(frame, vintage, **kwargs):
        seen.append((kwargs.get("uprating_key"), frame["salaire_brut_annuel"][0]))
        return SimpleNamespace(with_earnings=pl.DataFrame())

    monkeypatch.setattr(service, "population_frame", lambda: population)
    monkeypatch.setattr(service, "run_population", lambda request, frame: (
        SimpleNamespace(households=None), SimpleNamespace(reform_cost=5e9, deciles=[],
                                employer_contribution_delta=0.0)))
    monkeypatch.setattr(emtr_module, "cached", cached)
    uprating = Uprating(wage=0.03, price=0.02, source=WAGES["source"], base_year=2024)
    year = service.YearPass(reform=ReformSpec(decote_taux=0.4), year=2027, behavioural=True)
    for view in (service.FROZEN_VIEW, service.FIRST_YEAR_VIEW):
        service.price_first_year(year, uprating=uprating, view=view)
    assert seen == [(None, 30_000.0),
                    (uprating.key(), pytest.approx(30_000.0 * 1.03 ** 3))]


def _sample(seed: int):
    """Households with earnings as an EMTR pass gives them, different for each of the
    samples C1 reads, by its rank among them."""
    import polars as pl

    from impots.behavioural import emtr as emtr_module

    rank = emtr_module.C1_SAMPLES.index(seed)
    ids = [f"h{(rank * 3 + i) % 12:02d}" for i in range(4)]
    return pl.DataFrame({
        "household_id": ids, "weight": [10.0 + rank] * 4, "n_earners": [1] * 4,
        "emtr": [0.30, 0.41, 0.53, 0.20], "emtr_reform": [0.28 - 0.01 * rank, 0.45, 0.80,
                                                           0.20 + 0.02 * rank],
        "emtr_ir": [0.11, 0.30, 0.41, 0.0], "emtr_ir_reform": [0.10 - 0.01 * rank, 0.30, 0.45,
                                                              0.01 * rank]})


@pytest.mark.parametrize("reform, read", [
    ({"decote_taux": 0.4}, "every sample"), ({"csg_activite_deductible": 0.063}, "one")])
def test_c1_reads_its_samples_pooled_and_c7_the_first(monkeypatch, reform, read) -> None:
    """One sample of 3 000 households carries a standard deviation of up to 0.09 point of
    Δb 2035 in C1, from a few top-decile households whose step crosses a small jump
    (D-283). C1 reads four samples, pooled, and its receipt is then the mean of the four.
    C7 reads the first, and a reform C1 does not read pays for one (D-284)."""
    import polars as pl

    from impots.api.schemas import ReformSpec
    from impots.behavioural import channels
    from impots.behavioural import emtr as emtr_module
    from impots.behavioural.store import load as load_store
    from impots.population.runner import SAMPLE_SEED
    from impots.predictif.theta import Theta, pinned

    frame = pl.DataFrame({"household_id": [f"h{i:02d}" for i in range(12)],
                          "salaire_brut_annuel": [20_000.0 + 9_000.0 * i for i in range(12)]})
    seen, labour = [], []

    def cached(frame, vintage, *, seed=SAMPLE_SEED, **kwargs):
        seen.append(seed)
        return SimpleNamespace(with_earnings=_sample(seed))

    monkeypatch.setattr(emtr_module, "cached", cached)
    monkeypatch.setattr(service, "labour_inputs",
                        lambda request, frame, agg, households: labour.append(households)
                        or {})
    request = SimpleNamespace(year=2026, reform=ReformSpec(**reform))
    inputs, households = service.behavioural_inputs(request, frame, SimpleNamespace(), None)

    seeds = list(emtr_module.C1_SAMPLES) if read == "every sample" else [SAMPLE_SEED]
    assert seen == seeds and households == 4 * len(seeds)
    assert labour[0].equals(_sample(SAMPLE_SEED))
    assert len(inputs["weights"]) == 4 * len(seeds)
    assert inputs["weights"].sum() == pytest.approx(
        np.mean([_sample(seed)["weight"].sum() for seed in seeds]))
    if read == "every sample":
        store = pinned(load_store(), Theta(common=0.5))

        def c1(**given):
            return float(channels.elasticity_of_taxable_income(
                store, request.reform, **given, draws=1,
                rng=np.random.default_rng(0)).draws[0])

        pooled = c1(**{k: inputs[k] for k in ("emtr_baseline", "emtr_reform",
                                              "emtr_ir_baseline", "emtr_ir_reform",
                                              "taxable_base", "weights", "top_decile")})
        each = [c1(**service.eti_inputs(frame, _sample(seed))) for seed in seeds]
        assert pooled == pytest.approx(np.mean(each), rel=1e-12)
        assert len(set(np.round(each, 6))) > 1, "the samples must differ for the test to bite"


# --------------------------------------------------------------------------- #
# The refusals the endpoint translates (D-229)
# --------------------------------------------------------------------------- #
def test_a_first_year_outside_the_population_window_is_refused(client, priced,
                                                               monkeypatch) -> None:
    monkeypatch.setattr(service, "MAX_YEAR", 2025)
    response = client.post("/predictif/simulate", json=_payload())
    assert response.status_code == 422 and "sort de la fenêtre" in response.json()["detail"]
    assert priced == []


def test_a_shock_the_builder_refuses_is_a_422_with_its_reason(client,
                                                              monkeypatch) -> None:
    """The real `_price_first_year`, its pass stubbed: a reform whose deltas build no
    shock answers with the builder's reason, not with a server error."""
    import polars as pl

    from impots.macro import shocks

    def refuse(*args, **kwargs):
        raise shocks.ShockError("aucun choc lisible pour ces deltas (test)")

    population = pl.DataFrame({
        "person_id": [0], "household_id": ["h0"], "weight": [1.0], "age": [40],
        "salaire_brut_annuel": [30_000.0], "chomage_annuel": [0.0],
        "pension_annuelle": [0.0], "loyer_mensuel": [0.0],
        "revenu_non_salarie_annuel": [0.0]})
    monkeypatch.setattr(service, "population_frame", lambda: population)
    monkeypatch.setattr(service, "run_population", lambda request, frame: (
        SimpleNamespace(households=None),
        SimpleNamespace(reform_cost=5e9, deciles=[], deltas={},
                        employer_contribution_delta=0.0)))
    monkeypatch.setattr(shocks, "build", refuse)
    monkeypatch.setattr(service, "predictif_macro_store", synthetic_macro_store)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    response = client.post("/predictif/simulate", json=_payload(macro=True,
                                                                persistence="tenu"))
    assert response.status_code == 422
    assert "aucun choc lisible" in response.json()["detail"]


def test_a_refusal_inside_the_chain_is_a_422_with_its_reason(client, priced,
                                                             monkeypatch) -> None:
    """Every refusal the chain makes after the pass — a box, a feedback row, a maturity
    — reaches the caller as what it is, a refused request, with the chain's words."""
    from impots.dette.path import DebtError

    def refuse(*args, **kwargs):
        raise DebtError("trajectoire refusée par la chaîne (test)")

    monkeypatch.setattr(chaine, "run", refuse)
    response = client.post("/predictif/simulate", json=_payload())
    assert response.status_code == 422
    assert "refusée par la chaîne" in response.json()["detail"]


def test_a_report_name_the_router_lets_through_is_refused_by_the_handler(client) -> None:
    """Exactly 422, on a form that reaches the handler: `..%2F` is answered by the
    router itself, and a test that accepted its 404 stayed green without the guard
    (D-173). The trailing newline is the form `re.match` with `$` once let pass."""
    assert client.get("/predictif/gel_bareme%0A").status_code == 422


def test_an_unreadable_macro_store_is_a_named_refusal(monkeypatch) -> None:
    """Without its PDFs the store does not load; the loop is then unavailable, said so,
    never a bare reader error and never a silent zero."""
    from impots.macro import store as macro_store_module

    def missing(*args, **kwargs):
        raise macro_store_module.MissingSourceTable("multiplier_by_instrument (test)")

    monkeypatch.setattr(macro_store_module, "load", missing)
    with pytest.raises(service.MacroSourceError, match="magasin macro illisible"):
        service.predictif_macro_store()


def test_a_pass_without_a_cost_is_a_server_error_with_its_reason(client,
                                                                monkeypatch) -> None:
    """A reform always has a cost; a pass that returned none would otherwise meet
    `float(None)` three lines later, and the caller a trace."""
    import polars as pl

    population = pl.DataFrame({
        "person_id": [0], "household_id": ["h0"], "weight": [1.0], "age": [40],
        "salaire_brut_annuel": [30_000.0], "chomage_annuel": [0.0],
        "pension_annuelle": [0.0], "loyer_mensuel": [0.0],
        "revenu_non_salarie_annuel": [0.0]})
    monkeypatch.setattr(service, "population_frame", lambda: population)
    monkeypatch.setattr(service, "run_population", lambda request, frame: (
        SimpleNamespace(households=None), SimpleNamespace(reform_cost=None, deciles=[])))
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    response = client.post("/predictif/simulate", json=_payload())
    assert response.status_code == 500 and "pas de coût" in response.json()["detail"]
