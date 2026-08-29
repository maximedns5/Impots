"""HTTP surface (spec §4, §6).

The client is module-scoped so the app's lifespan — and therefore the warm-up —
runs once. A per-test client would pay the 5 s cold start every time and make the
timing assertions meaningless.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from impots.api.main import app

SINGLE_30K: dict[str, Any] = {
    "household": {"adults": [{"salaire_brut_annuel": 30000, "annee_naissance": 1990}]},
    "year": 2024,
    "tier": "light",
}
TOP_RATE_50: dict[str, Any] = {
    "ir_bareme": [
        {"threshold": 0, "rate": 0.00},
        {"threshold": 11497, "rate": 0.11},
        {"threshold": 29315, "rate": 0.30},
        {"threshold": 83823, "rate": 0.41},
        {"threshold": 180294, "rate": 0.50},
    ]
}


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["openfisca_france"] == "176.0.8"
    assert body["openfisca_core"] == "44.7.0"
    assert body["warm"] is True


def test_parameters_ir_reads_current_law(client: TestClient) -> None:
    body = client.get("/parameters/ir", params={"year": 2024}).json()
    assert body["year"] == 2024
    assert [bracket["threshold"] for bracket in body["bareme"]] == [
        0, 11497, 29315, 83823, 180294
    ]
    assert [bracket["rate"] for bracket in body["bareme"]] == [0, 0.11, 0.30, 0.41, 0.45]
    assert body["decote"] == {"seuil_celib": 889.0, "seuil_couple": 1470.0, "taux": 0.4525}
    assert body["plafond_qf_demi_part"] == 1791.0
    assert body["csg_activite"] == {"imposable": pytest.approx(0.024),
                                    "deductible": pytest.approx(0.068)}


def test_parameters_ir_rejects_an_out_of_range_year(client: TestClient) -> None:
    assert client.get("/parameters/ir", params={"year": 1998}).status_code == 422


def test_simulate_light(client: TestClient) -> None:
    response = client.post("/simulate", json=SINGLE_30K)
    assert response.status_code == 200
    body = response.json()
    assert body["baseline"]["ir"] == pytest.approx(812, abs=2)
    assert body["baseline"]["salaire_net"] == pytest.approx(23748, abs=2)
    assert body["reform"] is None and body["delta"] is None and body["emtr"] is None
    assert body["tier"] == "light"
    assert body["engine"]["openfisca_france"] == "176.0.8"
    # famille/ménage rows are absent from a light answer, not zero
    assert body["baseline"]["revenu_disponible"] is None
    assert body["baseline"]["af"] is None


def test_simulate_full_includes_benefits(client: TestClient) -> None:
    body = client.post("/simulate", json={**SINGLE_30K, "tier": "full"}).json()
    assert body["baseline"]["revenu_disponible"] == pytest.approx(23148, abs=2)
    assert body["baseline"]["af"] == 0.0
    assert body["baseline"]["aide_logement"] == 0.0


def test_simulate_with_reform_returns_the_three_columns(client: TestClient) -> None:
    """The end-to-end story of the whole phase: a top-rate reform costs this
    household exactly 200 € more, an amount checkable on paper."""
    body = client.post(
        "/simulate",
        json={
            "household": {"adults": [{"salaire_brut_annuel": 240000, "annee_naissance": 1980}]},
            "year": 2024,
            "tier": "light",
            "reform": TOP_RATE_50,
        },
    ).json()
    assert body["baseline"]["ir"] == pytest.approx(59668, abs=2)
    assert body["reform"]["ir"] == pytest.approx(59868, abs=2)
    assert body["delta"]["ir"] == pytest.approx(200, abs=2)


def test_simulate_couple_with_children(client: TestClient) -> None:
    body = client.post(
        "/simulate",
        json={
            "household": {
                "adults": [
                    {"salaire_brut_annuel": 45000, "annee_naissance": 1985},
                    {"salaire_brut_annuel": 25000, "annee_naissance": 1987},
                ],
                "children": [{"annee_naissance": 2015}, {"annee_naissance": 2018}],
                "couple_marie_ou_pacse": True,
            },
            "year": 2024,
            "tier": "full",
        },
    ).json()
    assert body["baseline"]["parts_fiscales"] == 3.0
    assert body["baseline"]["ir"] == pytest.approx(1274, abs=2)
    assert body["baseline"]["af"] == pytest.approx(1771, abs=2)
    assert body["baseline"]["revenu_disponible"] == pytest.approx(55895, abs=2)


def test_response_echoes_the_modelling_choices(client: TestClient) -> None:
    """A caller reading a benefit figure must be able to tell which wiring produced
    it, without going back to the request they sent."""
    body = client.post("/simulate", json={**SINGLE_30K, "tier": "full"}).json()
    assert body["historique_revenus"] is True     # the default since D-011
    assert body["year"] == 2024
    assert body["tier"] == "full"


def test_income_history_is_reachable_over_http(client: TestClient) -> None:
    """The flag that removes the reference-period defect (D-005) must be on the wire."""
    renter = {
        "household": {
            "adults": [{"salaire_brut_annuel": 30000, "annee_naissance": 1990}],
            "logement": {"statut": "locataire_vide", "loyer_mensuel": 600, "zone_apl": 2},
        },
        "year": 2024,
        "tier": "full",
    }
    naive = client.post("/simulate", json={**renter, "historique_revenus": False}).json()
    honest = client.post("/simulate", json=renter).json()
    assert naive["historique_revenus"] is False
    assert honest["historique_revenus"] is True
    assert naive["baseline"]["aide_logement"] > 1900
    assert honest["baseline"]["aide_logement"] == 0.0


def test_lone_parent_claims_case_t_by_default(client: TestClient) -> None:
    """Two parts, not one and a half — see docs/DECISIONS.md D-006."""
    lone = {
        "household": {
            "adults": [{"salaire_brut_annuel": 40000, "annee_naissance": 1985}],
            "children": [{"annee_naissance": 2015}],
        },
        "year": 2024,
        "tier": "light",
    }
    inferred = client.post("/simulate", json=lone).json()
    assert inferred["baseline"]["parts_fiscales"] == 2.0

    waived = dict(lone)
    waived["household"] = {**lone["household"], "parent_isole": False}
    assert client.post("/simulate", json=waived).json()["baseline"]["parts_fiscales"] == 1.5


def test_simulate_with_emtr(client: TestClient) -> None:
    body = client.post(
        "/simulate", json={**SINGLE_30K, "tier": "full", "emtr": True}
    ).json()
    assert body["emtr"] == pytest.approx(0.4979, abs=1e-3)
    assert body["timings"]["emtr_ms"] is not None


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #
def _detail(response: Any) -> str:
    return str(response.json()["detail"])


def test_emtr_on_the_light_tier_is_rejected_with_a_reason(client: TestClient) -> None:
    """422 and an explanation, not a silently ignored flag (spec §4)."""
    response = client.post("/simulate", json={**SINGLE_30K, "emtr": True})
    assert response.status_code == 422
    assert "tier='full'" in _detail(response)
    assert "prestations" in _detail(response)


@pytest.mark.parametrize(
    ("payload", "needle"),
    [
        ({"household": {"adults": []}}, "at least 1"),
        (
            {
                "household": {
                    "adults": [
                        {"salaire_brut_annuel": 1, "annee_naissance": 1990},
                        {"salaire_brut_annuel": 1, "annee_naissance": 1990},
                        {"salaire_brut_annuel": 1, "annee_naissance": 1990},
                    ]
                }
            },
            "at most 2",
        ),
        (
            {"household": {"adults": [{"salaire_brut_annuel": -1, "annee_naissance": 1990}]}},
            "greater than or equal to 0",
        ),
        (
            {"household": {"adults": [{"salaire_brut_annuel": 2e7, "annee_naissance": 1990}]}},
            "less than or equal to 10000000",
        ),
        (
            {"household": {"adults": [{"salaire_brut_annuel": 1, "annee_naissance": 1850}]}},
            "greater than or equal to 1920",
        ),
        (
            {
                "household": {
                    "adults": [{"salaire_brut_annuel": 1, "annee_naissance": 1990}],
                    "children": [{"annee_naissance": 2015}] * 9,
                }
            },
            "at most 8",
        ),
        (
            {
                "household": {
                    "adults": [
                        {"salaire_brut_annuel": 1, "annee_naissance": 1990},
                        {"salaire_brut_annuel": 1, "annee_naissance": 1990},
                    ]
                }
            },
            "concubinage",
        ),
        (
            {
                "household": {"adults": [{"salaire_brut_annuel": 1, "annee_naissance": 1990}]},
                "reform": {"ir_bareme": [{"threshold": i * 1000, "rate": 0.1} for i in range(6)]},
            },
            "5 tranches",
        ),
        (
            {
                "household": {"adults": [{"salaire_brut_annuel": 1, "annee_naissance": 1990}]},
                "reform": {"ir_bareme": [{"threshold": 5000, "rate": 0.1},
                                         {"threshold": 9000, "rate": 0.2}]},
            },
            "première tranche",
        ),
        (
            {
                "household": {"adults": [{"salaire_brut_annuel": 1, "annee_naissance": 1990}]},
                "reform": {"ir_bareme": [{"threshold": 0, "rate": 0.1},
                                         {"threshold": 0, "rate": 0.2}]},
            },
            "strictement croissants",
        ),
        (
            {
                "household": {"adults": [{"salaire_brut_annuel": 1, "annee_naissance": 1990}]},
                "reform": {"taxe_habitation": 0.5},
            },
            "Extra inputs",
        ),
        # Case T cannot apply to a couple, and claiming it anyway would silently
        # hand them a half-part they are not entitled to.
        (
            {
                "household": {
                    "adults": [
                        {"salaire_brut_annuel": 1, "annee_naissance": 1990},
                        {"salaire_brut_annuel": 1, "annee_naissance": 1990},
                    ],
                    "children": [{"annee_naissance": 2015}],
                    "couple_marie_ou_pacse": True,
                    "parent_isole": True,
                }
            },
            "adulte seul",
        ),
        # Zone 0 ("non renseigné") parses cleanly and then kills the housing
        # cascade with a ParameterNotFoundError. It must never reach the engine.
        (
            {
                "household": {
                    "adults": [{"salaire_brut_annuel": 1, "annee_naissance": 1990}],
                    "logement": {"statut": "locataire_vide", "loyer_mensuel": 600,
                                 "zone_apl": 0},
                }
            },
            "greater than or equal to 1",
        ),
    ],
)
def test_invalid_requests_are_rejected(client: TestClient, payload: dict, needle: str) -> None:
    """Every rejection carries a message the UI can show verbatim."""
    response = client.post("/simulate", json={"year": 2024, **payload})
    assert response.status_code == 422, response.text
    assert needle in response.text


def test_unknown_reform_knob_is_refused() -> None:
    """The reform surface is a whitelist: raw parameter paths must not get through."""
    with TestClient(app) as client:
        response = client.post(
            "/simulate",
            json={
                "household": {"adults": [{"salaire_brut_annuel": 1, "annee_naissance": 1990}]},
                "reform": {"impot_revenu.bareme_ir_depuis_1945.bareme": 0.9},
            },
        )
        assert response.status_code == 422


# --------------------------------------------------------------------------- #
# budget and the static UI
# --------------------------------------------------------------------------- #
def test_light_request_is_within_budget(client: TestClient, quiet_machine: None) -> None:
    client.post("/simulate", json=SINGLE_30K)  # ensure warm
    started = time.perf_counter()
    client.post("/simulate", json=SINGLE_30K)
    assert time.perf_counter() - started < 1.5


def test_full_request_is_within_budget(client: TestClient, quiet_machine: None) -> None:
    payload = {**SINGLE_30K, "tier": "full"}
    client.post("/simulate", json=payload)
    started = time.perf_counter()
    client.post("/simulate", json=payload)
    assert time.perf_counter() - started < 6.0


def test_root_serves_the_ui(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Couche mécanique (L2)" in response.text


# --------------------------------------------------------------------------- #
# population (L1) — PHASE1_SPEC §6
#
# These need a built population, which CI does not have: the EEC file is 11.7 MB
# and downloading it is not CI's job. They skip cleanly when it is absent, and the
# pipeline itself is covered by tests/test_population.py on the committed fixture.
# --------------------------------------------------------------------------- #
def _population_built() -> bool:
    from impots.population.build import PROCESSED

    return (PROCESSED / "population_2024.parquet").exists() and (
        PROCESSED / "baseline_2024.json"
    ).exists()


needs_population = pytest.mark.skipif(
    not _population_built(),
    reason="no population built — run `impots population build && impots population reconcile`",
)

TOP_RATE_50_REFORM = {"reform": {"ir_bareme": TOP_RATE_50["ir_bareme"]}, "year": 2024,
                      "tier": "quick"}


@needs_population
def test_population_baseline_serves_a_precomputed_file(client: TestClient) -> None:
    """It must not run the engine: a full-tier population run is minutes."""
    body = client.get("/population/baseline").json()
    assert body["meta"]["vintage"] == "2024"
    assert body["meta"]["households"] > 30e6
    assert len(body["deciles"]) == 10
    assert [row["decile"] for row in body["deciles"]] == list(range(1, 11))
    assert body["reconciliation"], "the baseline must carry its own reconciliation"


@needs_population
def test_population_baseline_states_its_limitations(client: TestClient) -> None:
    """D-015: the banner is not optional. A population whose RSA runs at +106 %
    must say so wherever its numbers are shown."""
    meta = client.get("/population/baseline").json()["meta"]
    assert meta["limitations"], "the L1 banner needs something to show"
    joined = " ".join(meta["limitations"]).lower()
    assert "no income is observed" in joined
    assert "take-up" in joined
    assert "reconciliation" in meta["note"].lower()


@needs_population
def test_population_reconciliation_marks_calibrated_lines_as_spent(client: TestClient) -> None:
    """§4.3's rule, visible on the wire: a line the model was tuned to may not be
    presented as evidence that the model is right."""
    lines = client.get("/population/baseline").json()["reconciliation"]
    uses = {line["use"] for line in lines}
    assert "calibration" in uses and "validation" in uses
    for line in lines:
        if line["use"] == "calibration":
            assert line["status"] == "calibrated (spent)"


@needs_population
def test_population_simulate_prices_a_reform(client: TestClient) -> None:
    """A 50 % top rate must raise money, and land on the top decile only."""
    body = client.post("/population/simulate", json=TOP_RATE_50_REFORM).json()
    assert body["meta"]["tier"] == "quick"
    assert body["meta"]["sampled_households"] == 20_000
    assert body["deltas"]["ir"] > 0
    assert body["reform_cost"] < 0, "raising the top rate must raise money"
    deltas = [row["mean_delta"] for row in body["deciles"]]
    assert deltas[-1] < 0, "the top decile must lose"
    assert all(abs(delta) < abs(deltas[-1]) for delta in deltas[:-1]), (
        "a top-rate reform must not touch the lower deciles more than the top one"
    )


@needs_population
def test_population_simulate_says_it_sampled(client: TestClient) -> None:
    """The quick tier answers a different-precision question and must say so."""
    note = client.post("/population/simulate", json=TOP_RATE_50_REFORM).json()["meta"]["note"]
    assert "sous-échantillon" in note
    assert "20 000" in note


@needs_population
def test_population_simulate_refuses_an_empty_reform(client: TestClient) -> None:
    """Without a reform there is nothing to price, and the baseline endpoint already
    serves the levels — running the engine to prove that would be a waste."""
    response = client.post("/population/simulate", json={"reform": {}, "year": 2024})
    assert response.status_code == 422
    assert "réforme est requise" in response.text
