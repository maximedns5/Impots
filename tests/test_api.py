"""HTTP surface (spec §4, §6).

The client is module-scoped so the app's lifespan — and therefore the warm-up —
runs once. A per-test client would pay the 5 s cold start every time and make the
timing assertions meaningless.
"""

from __future__ import annotations

import json
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


def population_test(function):
    """Needs the population, and therefore takes about a minute.

    Composed so the two facts travel together: every test that runs the population is
    also a test the default gate skips, and forgetting the second mark is how a fast
    gate quietly stops being fast."""
    return needs_population(pytest.mark.slow(function))

TOP_RATE_50_REFORM = {"reform": {"ir_bareme": TOP_RATE_50["ir_bareme"]}, "year": 2024,
                      "tier": "quick"}


@population_test
def test_population_baseline_serves_a_precomputed_file(client: TestClient) -> None:
    """It must not run the engine: a full-tier population run is minutes."""
    body = client.get("/population/baseline").json()
    assert body["meta"]["vintage"] == "2024"
    assert body["meta"]["households"] > 30e6
    assert len(body["deciles"]) == 10
    assert [row["decile"] for row in body["deciles"]] == list(range(1, 11))
    assert body["reconciliation"], "the baseline must carry its own reconciliation"


@population_test
def test_population_baseline_states_its_limitations(client: TestClient) -> None:
    """D-015: the banner is not optional. A population whose RSA runs at +106 %
    must say so wherever its numbers are shown."""
    meta = client.get("/population/baseline").json()["meta"]
    assert meta["limitations"], "the L1 banner needs something to show"
    joined = " ".join(meta["limitations"]).lower()
    assert "no income is observed" in joined
    assert "take-up" in joined
    assert "reconciliation" in meta["note"].lower()


@population_test
def test_population_reconciliation_marks_calibrated_lines_as_spent(client: TestClient) -> None:
    """§4.3's rule, visible on the wire: a line the model was tuned to may not be
    presented as evidence that the model is right."""
    lines = client.get("/population/baseline").json()["reconciliation"]
    uses = {line["use"] for line in lines}
    assert "calibration" in uses and "validation" in uses
    for line in lines:
        if line["use"] != "calibration":
            continue
        # NOT "always (spent)". D-072 made calibration lines compare, and a calibration
        # line that MISSES its target must say so — being a calibration explains why
        # hitting it proves little, never why missing it would be fine. The property
        # that matters on the wire is that it is never dressed as validation.
        assert line["status"] in ("calibrated (spent)", "calibrated, OFF TARGET")
        assert not line["status"].startswith("within"), (
            f"{line['label']} is a spent calibration target presented as a validation "
            f"verdict"
        )
    # And on the artefact this endpoint serves, all four should currently be on target.
    # They were not until the sampler was fixed (D-074): the pension line read +2.29 %
    # and the unemployment line -2.40 % against a ±2 % tolerance, and both were the
    # subsample's bias rather than the calibration's error.
    off = [line["label"] for line in lines
           if line["use"] == "calibration" and line["status"] == "calibrated, OFF TARGET"]
    assert not off, f"calibration targets missed: {off}"


@population_test
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


@population_test
def test_population_simulate_says_it_sampled(client: TestClient) -> None:
    """The quick tier answers a different-precision question and must say so."""
    note = client.post("/population/simulate", json=TOP_RATE_50_REFORM).json()["meta"]["note"]
    assert "sous-échantillon" in note
    assert "20 000" in note


@population_test
def test_population_simulate_refuses_an_empty_reform(client: TestClient) -> None:
    """Without a reform there is nothing to price, and the baseline endpoint already
    serves the levels — running the engine to prove that would be a waste."""
    response = client.post("/population/simulate", json={"reform": {}, "year": 2024})
    assert response.status_code == 422
    assert "réforme est requise" in response.text


# --------------------------------------------------------------------------- #
# Firms (spec §4)
#
# These do NOT skip in CI. The firm population is built from
# `tests/fixtures/firm_cells.json`, which is invented and committed, so the whole
# chain — cells, draw, engine, HTTP — runs on every machine. That is the payoff of
# putting the cell table behind a JSON seam rather than behind a download.
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module", autouse=True)
def firm_population() -> None:
    """Build the firm population from the committed fixture if it is not there."""
    from impots.entreprises.build import FIXTURE_CELLS, PROCESSED, build

    if not (PROCESSED / "firms_fixture.parquet").exists():
        build(FIXTURE_CELLS)


IS_30_REFORM = {"reform": {"is_taux_normal": 0.30}, "year": 2026}


def test_firm_baseline_serves_the_synthetic_population(client: TestClient) -> None:
    body = client.get("/entreprises/baseline").json()
    assert body["meta"]["n_firms"] > 1e6
    assert body["meta"]["turnover"] > 1e12
    assert body["totals"]["impot_societes"] > 0
    assert body["totals"]["c3s"] > 0
    assert len(body["by_size"]) == 4
    assert body["deltas"] == {}, "a baseline has nothing to compare itself to"
    assert body["reform_cost"] is None


def test_firm_baseline_admits_the_cells_are_invented(client: TestClient) -> None:
    """The fixture cells are made up. A run on them that did not say so would be
    the single most misleading thing this module could publish."""
    meta = client.get("/entreprises/baseline").json()["meta"]
    assert meta["cells_are_synthetic"] is True
    assert "synthétique" in meta["note"]


def test_firm_baseline_states_its_limitations(client: TestClient) -> None:
    """Same rule as the household banner (D-015): the gaps travel with the numbers."""
    limitations = client.get("/entreprises/baseline").json()["meta"]["limitations"]
    joined = " ".join(limitations).lower()
    assert "report déficitaire" in joined, "the loss carry-forward gap biases IS upward"
    assert "intégration fiscale" in joined
    assert "ratio fiscal/comptable" in joined, "the scalar that dominates the IS residual"
    assert "cfe" in client.get("/entreprises/baseline").json()["meta"]["note"].lower()


def test_firm_reform_is_priced_synchronously(client: TestClient) -> None:
    """No sampling, no quick tier, no batch job (§4). If this ever needs a tier, the
    test should fail rather than the endpoint quietly grow one."""
    started = time.perf_counter()
    response = client.post("/entreprises/simulate", json=IS_30_REFORM)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert elapsed < 2.0, f"a firm reform took {elapsed:.2f}s"
    assert "sampled" not in response.text


def test_firm_reform_raises_money_and_lands_on_the_largest(client: TestClient) -> None:
    body = client.post("/entreprises/simulate", json=IS_30_REFORM).json()
    assert body["deltas"]["impot_societes"] > 0
    assert body["reform_cost"] < 0, "raising the IS rate must raise money"
    by_size = {row["taille"]: row for row in body["by_size"]}
    cells = {(c["naf_section"], c["taille"]): c for c in body["cells"]}
    ge = [c for key, c in cells.items() if key[1] == "GE"]
    micro = [c for key, c in cells.items() if key[1] == "micro"]
    assert min(c["mean_delta"] for c in ge) > max(c["mean_delta"] for c in micro), (
        "a rise in the normal rate must hit large firms harder than micro ones"
    )
    assert by_size["GE"]["mean_effective_rate"] > by_size["micro"]["mean_effective_rate"]


def test_c3s_is_a_turnover_tax_and_its_abattement_shows(client: TestClient) -> None:
    """The mechanical point of carrying C3S separately: it is levied on turnover
    above a 19 M EUR abattement, so it behaves nothing like the IS.

    Two consequences, both asserted here because both are load-bearing for the
    incidence table. It reaches firms that owe no income tax at all — no IS rate
    change can do that. And the abattement makes the share of firms touched rise
    monotonically with size: micro firms are shielded outright, GE firms are all
    caught. If a future refactor drops the abattement, this profile flattens and
    this test is what notices."""
    body = client.post(
        "/entreprises/simulate", json={"reform": {"c3s_taux": 0.0032}, "year": 2026}
    ).json()
    assert body["deltas"]["c3s"] > 0
    assert body["deltas"]["impot_societes"] == pytest.approx(0.0), (
        "C3S is not modelled as deductible from the IS base, so it must not move IS"
    )
    assert client.get("/entreprises/baseline").json()["meta"]["share_zero_is"] > 0.2, (
        "a population with no loss-makers cannot show what C3S does"
    )
    affected: dict[str, list[float]] = {}
    for cell in body["cells"]:
        affected.setdefault(cell["taille"], []).append(cell["share_affected"])
    assert max(affected["micro"]) == 0.0, "no micro firm reaches the 19 M EUR abattement"
    assert min(affected["GE"]) > 0.95, "large firms are all above it"
    reach = [max(affected[size]) for size in ("micro", "PME", "ETI", "GE")]
    assert reach == sorted(reach), f"C3S reach must rise with size, got {reach}"


def test_firm_response_carries_no_firm_level_output(client: TestClient) -> None:
    """§4: sector x size only. Every financial is a draw inside a published cell, so
    a named firm or a top-tail row would be the least reliable number in the model
    dressed up as the most interesting one."""
    body = client.post("/entreprises/simulate", json=IS_30_REFORM).json()
    assert set(body) == {
        "meta", "totals", "totals_reform", "deltas", "reform_cost",
        "cells", "by_size", "behavioural", "timings",
    }
    assert all(set(cell) >= {"naf_section", "taille", "n_firms"} for cell in body["cells"])
    raw = client.post("/entreprises/simulate", json=IS_30_REFORM).text
    assert "firm_id" not in raw, "no firm identifier may reach the client"


def test_firm_simulate_refuses_an_empty_reform(client: TestClient) -> None:
    response = client.post("/entreprises/simulate", json={"reform": {}, "year": 2026})
    assert response.status_code == 422
    assert "réforme est requise" in response.text


def test_unknown_firm_knob_is_refused(client: TestClient) -> None:
    """Same posture as the household side: a misspelt knob must not be a no-op that
    silently prices current law and calls it a reform."""
    response = client.post(
        "/entreprises/simulate",
        json={"reform": {"is_taux_norml": 0.30}, "year": 2026},
    )
    assert response.status_code == 422
    assert "is_taux_norml" in response.text


# --------------------------------------------------------------------------- #
# The behavioural band (Phase 3, §7)
#
# Opt-in, because the marginal rates it needs are two more full-tier runs. These
# tests use the same module-scoped client, so the band is paid for once.
# --------------------------------------------------------------------------- #
@population_test
def test_the_band_is_absent_unless_asked_for(client: TestClient) -> None:
    """The mechanical answer stays fast by default; nothing about it changes."""
    body = client.post("/population/simulate", json=TOP_RATE_50_REFORM).json()
    assert body["behavioural"] is None


@population_test
def test_the_band_never_moves_the_mechanical_number(client: TestClient) -> None:
    """The layer boundary, asserted over HTTP. A reader taking only the mechanical
    figure must get exactly what they would have got without Phase 3."""
    without = client.post("/population/simulate", json=TOP_RATE_50_REFORM).json()
    with_band = client.post(
        "/population/simulate", json={**TOP_RATE_50_REFORM, "behavioural": True}
    ).json()
    assert with_band["reform_cost"] == without["reform_cost"]
    assert with_band["totals"] == without["totals"]
    assert with_band["deltas"] == without["deltas"]
    assert with_band["behavioural"]["mechanical"] == pytest.approx(
        -without["reform_cost"]
    )


@population_test
def test_the_band_prices_the_response_to_a_top_rate_rise(client: TestClient) -> None:
    """A 45 % -> 50 % top rate. The mechanical yield is positive; the taxable-income
    response gives part of it back, so the band must sit BELOW the mechanical figure
    and still be positive — a response that reversed the sign of a five-point rate
    rise would be a modelling error, not a finding."""
    body = client.post(
        "/population/simulate", json={**TOP_RATE_50_REFORM, "behavioural": True}
    ).json()
    behavioural = body["behavioural"]
    band = behavioural["band"]
    assert band is not None, "the store has verified elasticities; a band must appear"
    assert band["p10"] < band["p50"] < band["p90"]
    assert band["p50"] < behavioural["mechanical"]
    assert band["p10"] > 0


@population_test
def test_the_band_reports_its_grade_and_its_provenance(client: TestClient) -> None:
    """§4 and §7: the grade is data, not decoration, and a band must be traceable to
    the evidence that produced it."""
    behavioural = client.post(
        "/population/simulate", json={**TOP_RATE_50_REFORM, "behavioural": True}
    ).json()["behavioural"]
    assert behavioural["grade"] in {"in-support", "illustrative", "no-evidence"}
    assert behavioural["grade_reason"]
    assert behavioural["seed"] and behavioural["draws"]
    assert "eti_all" in behavioural["parameters_vintage"]
    assert behavioural["emtr_households"] > 0


@population_test
def test_a_dead_channel_says_so_rather_than_reporting_zero(client: TestClient) -> None:
    """C2 and C3 have no lever, and C4's only dimensionally-valid row died under
    verification. All three must say so — a zero would be a false claim about
    behaviour, where the sentence is a true claim about the evidence."""
    channels = {
        c["key"]: c for c in client.post(
            "/population/simulate", json={**TOP_RATE_50_REFORM, "behavioural": True}
        ).json()["behavioural"]["channels"]
    }
    for key in ("c2_employment", "c3_incidence", "c4_investment"):
        assert channels[key]["applies"] is False
        assert channels[key]["central"] is None
        assert channels[key]["message"], f"{key} reports nothing at all"
    assert "cotisation patronale" in channels["c2_employment"]["message"]


@population_test
def test_a_cliff_reform_is_flagged_and_a_broad_one_is_not(client: TestClient) -> None:
    """The two backtest cases, as the flag's specification (D-046).

    The 2025 allègements step moves two cliffs and overshoots its published cost by
    107 %; the barème indexation moves the whole scale and overshoots by 10 %. The
    flag must separate them, because the difference is exactly the thing it points at.
    """
    cliff = client.post("/population/simulate", json={
        "reform": {"bandeau_maladie_plafond": 2.25, "bandeau_famille_plafond": 3.3},
        "year": 2024, "tier": "quick",
    }).json()["narrow_band"]
    assert cliff["flagged"], f"the cliff case must flag; share was {cliff['share']}"
    assert cliff["share"] > 0.7, "and not marginally"
    assert "D-015" in cliff["caveat"]

    bareme = client.post("/population/simulate", json={
        "reform": {"ir_bareme": [
            {"threshold": 0, "rate": 0.00}, {"threshold": 10777, "rate": 0.11},
            {"threshold": 27478, "rate": 0.30}, {"threshold": 78570, "rate": 0.41},
            {"threshold": 168994, "rate": 0.45}],
            "decote_seuil_celib": 833, "decote_seuil_couple": 1378,
            "decote_taux": 0.4525, "plafond_qf_demi_part": 1678},
        "year": 2024, "tier": "quick",
    }).json()["narrow_band"]
    assert not bareme["flagged"], f"the barème case must not; share was {bareme['share']}"
    assert bareme["caveat"] == ""


@population_test
def test_the_flag_does_not_touch_the_mechanical_number(client: TestClient) -> None:
    """Metadata, never an adjustment. The flag is computed from the same run and must
    leave every figure exactly where it was."""
    body = client.post("/population/simulate", json={
        "reform": {"bandeau_maladie_plafond": 2.25}, "year": 2024, "tier": "quick",
    }).json()
    assert body["narrow_band"]["flagged"]
    # The cost is the double-entry-checked one, untouched by the flag.
    assert body["reform_cost"] is not None
    assert abs(body["reform_cost"]) > 1e8


def test_a_non_finite_threshold_is_refused_before_any_simulation(client: TestClient) -> None:
    """`Infinity` is JSON to Python's parser and was a valid float to the schema: an
    infinite IR threshold reached the engine, failed its read-back and came out as a
    500 (D-173). Sent as raw bytes, because a well-behaved client cannot even encode it.
    """
    reform = {"ir_bareme": [{"threshold": 0, "rate": 0.1},
                            {"threshold": float("inf"), "rate": 0.5}]}
    response = client.post("/simulate", content=json.dumps({**SINGLE_30K, "reform": reform}),
                           headers={"content-type": "application/json"})
    assert response.status_code == 422


def test_an_oversized_body_is_refused_before_it_is_parsed(client: TestClient) -> None:
    """No limit existed: the body was read whole into memory, whatever its size (D-173).
    The largest legitimate request — a household and a full reform — is a few kilobytes.
    """
    corps = b'{"padding": "' + b"a" * 100_000 + b'"}'
    response = client.post("/simulate", content=corps,
                           headers={"content-type": "application/json"})
    assert response.status_code == 413


def test_every_model_the_api_accepts_refuses_non_finite_numbers() -> None:
    """Derived from the routes, never listed by hand: a hand-written list of models is a
    second copy of the API's surface, and two copies drift (D-151, D-160). Fails if a
    model reachable from any request body lets `Infinity` or `NaN` through (D-173)."""
    import inspect
    import typing

    import pydantic

    def types(annotation):
        yield annotation
        for argument in typing.get_args(annotation):
            yield from types(argument)

    seen: set[type] = set()

    def walk(model: type) -> None:
        if model in seen:
            return
        seen.add(model)
        for field in model.model_fields.values():
            for kind in types(field.annotation):
                if inspect.isclass(kind) and issubclass(kind, pydantic.BaseModel):
                    walk(kind)

    for route in app.routes:
        body = getattr(route, "body_field", None)
        if body is not None:
            for kind in types(body.field_info.annotation):
                if inspect.isclass(kind) and issubclass(kind, pydantic.BaseModel):
                    walk(kind)
    assert len(seen) >= 10, f"the walk found too few input models to be trusted: {seen}"
    lenient = sorted(m.__name__ for m in seen if m.model_config.get("allow_inf_nan", True))
    assert not lenient, f"accept Infinity/NaN: {lenient}"



def test_a_disability_reaches_the_engine_and_its_rows_come_back(client: TestClient) -> None:
    """The AAH and the MVA have rows of their own on the wire (D-184): a benefit inside
    `revenu_disponible` with no row is one a reader cannot see."""
    request = {
        "household": {
            "adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1980,
                        "handicap": {"taux_incapacite": 0.8}}],
            "logement": {"statut": "locataire_vide", "loyer_mensuel": 500, "zone_apl": 2},
        },
        "year": 2024,
        "tier": "full",
    }
    response = client.post("/simulate", json=request)
    assert response.status_code == 200, response.text
    rows = response.json()["baseline"]
    assert rows["aah"] == pytest.approx(3 * 971.37 + 9 * 1_016.05, abs=0.05)
    assert rows["mva"] == pytest.approx(12 * 104.77, abs=0.05)


def test_an_aah_recipient_past_62_is_priced_not_refused(client: TestClient) -> None:
    """D-184 refused this request because the engine paid the AAH and the ASPA in full;
    D-185 corrects the engine and lifts the refusal. Aged 66, 80 %, nothing else: the AAH."""
    request = {
        "household": {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1958,
                                  "handicap": {"taux_incapacite": 0.8}}]},
        "year": 2024,
        "tier": "full",
    }
    response = client.post("/simulate", json=request)
    assert response.status_code == 200, response.text
    rows = response.json()["baseline"]
    assert rows["aah"] == pytest.approx(3 * 971.37 + 9 * 1_016.05, abs=0.05)
    assert rows["revenu_disponible"] == pytest.approx(rows["aah"], abs=0.05)


def test_an_invalidity_pension_reaches_the_engine_and_the_asi_comes_back(client: TestClient) -> None:
    """The invalidity pension and the ASI it opens have rows of their own on the wire (D-190):
    6 000 EUR alone, topped up to the ASI's ceiling by 4 676.11 EUR over 2024."""
    request = {
        "household": {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1980,
                                  "pension_invalidite_annuelle": 6_000}]},
        "year": 2024,
        "tier": "full",
    }
    response = client.post("/simulate", json=request)
    assert response.status_code == 200, response.text
    rows = response.json()["baseline"]
    assert rows["pension_invalidite"] == pytest.approx(6_000, abs=0.5)
    assert rows["asi"] == pytest.approx(4_676.11, abs=0.05)
    assert rows["revenu_disponible"] == pytest.approx(10_676.11, abs=0.05)
