"""Phase 10 M1 — `impots exploration`, the conditional explorer made askable (PHASE10_SPEC §2).

The population pass is stubbed one seam below the command, where `/predictif/simulate`'s
tests stub it too (`_price_first_year`). What is held here, in seconds and without data:
the request's refusals, the grid checked before the first pass, one pass per bundle and
view, both persistence scenarios read from those passes, every bundle in the report, the
one pricing path shared with the simulator, and the report naming the code it ran on.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import polars as pl
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from exploration_cases import COMMIT, START, pass_stub, run_search
from exploration_cases import exploration_request as _request
from impots.api import main
from impots.api.schemas import ExplorationRequest
from impots.dette import reference
from impots.population import cli
from impots.predictif import recherche, retroaction
from macro_cases import synthetic_macro_store


# --------------------------------------------------------------------------- #
# the request, refused before anything runs
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("overrides, needle", [
    ({"bounds": [{"knob": "ir_bareme", "low": 0, "high": 1, "step": 1}]},
     "pas un nombre"),
    ({"bounds": [{"knob": "ifi_obligations_declaratives", "low": 0, "high": 1,
                  "step": 1}]}, "pas un nombre"),
    ({"bounds": [{"knob": "theta_eti", "low": 0, "high": 1, "step": 0.5}]}, "inconnu"),
    ({"base": {"decote_taux": 0.45}}, "fixé aussi dans la base"),
    ({"question": "  "}, "sans question"),
])
def test_a_bound_that_is_not_a_number_unknown_or_fixed_in_the_base_is_refused(
        overrides: dict, needle: str) -> None:
    """GUARD 1. A barème is not a scalar, a name outside the reform is not a knob, and a
    knob also fixed in the base would be overwritten by the grid under a base the report
    shows. And a table of bundles without its question reads as a recommendation."""
    with pytest.raises(ValidationError, match=needle):
        ExplorationRequest.model_validate(_request(**overrides))


@pytest.mark.parametrize("missing", ["theta", "uprating"])
def test_an_exploration_without_theta_or_wage_index_is_refused(missing: str) -> None:
    """Every hypothesis is named, as in the simulator: no θ by default, not even 1/2
    (D-217), and no wage index without its source (D-226)."""
    payload = _request()
    del payload[missing]
    with pytest.raises(ValidationError, match=missing):
        ExplorationRequest.model_validate(payload)


def test_a_grid_point_the_reform_refuses_stops_before_the_first_pass() -> None:
    """GUARD 2. A rate of 110 % is out of the schema's bounds: found in a second, not after
    the passes of the points before it."""
    seen: list = []
    with pytest.raises(recherche.RechercheError, match="avant toute passe"):
        run_search(_request(bounds=[{"knob": "decote_taux", "low": 0.9, "high": 1.1,
                               "step": 0.1}]), seen=seen)
    assert seen == []


def test_a_grid_larger_than_the_cap_is_refused_not_truncated() -> None:
    """GUARD 5. Three bundles for two allowed: refused, with the passes it would cost."""
    seen: list = []
    with pytest.raises(recherche.RechercheError, match="3 paquets pour 2 autorisés"):
        run_search(_request(), seen=seen, max_bundles=2)
    assert seen == []


# --------------------------------------------------------------------------- #
# the search, from one pass per bundle and view
# --------------------------------------------------------------------------- #
def test_both_persistences_are_two_searches_from_the_same_passes() -> None:
    """GUARD 3. Past three years with the loop and none named, « éteint » and « tenu » are
    searched side by side (D-230), from six passes — three bundles, two views — not
    twelve. The two differ past the third year, which is the point of showing both."""
    seen: list = []
    report = run_search(_request(), seen=seen)
    assert len(seen) == 6 and report["passes"] == 6
    assert sorted(map(str, seen)) == sorted(
        str(({"decote_taux": r}, v)) for r in (0.40, 0.45, 0.50) for v in ("vieillie", "figee"))
    persistences = [s["persistence"] for s in report["searches"]]
    assert persistences == list(retroaction.PERSISTENCE_LABELS)
    off, held = (s["evaluations"] for s in report["searches"])
    assert [e["knobs"] for e in off] == [e["knobs"] for e in held]
    assert all(a["delta_aged"] != b["delta_aged"] for a, b in zip(off, held, strict=True))
    assert report["searches"][0]["persistence_label"] == retroaction.PERSISTENCE_LABELS[
        "eteint"]


@pytest.mark.parametrize("overrides, expected", [
    ({"persistence": "tenu"}, ["tenu"]),
    ({"horizon": 3}, [None]),
    ({"spending": {"rule": "part_pib_constante"}}, [None]),
])
def test_one_search_where_the_simulator_draws_one_path(overrides: dict,
                                                       expected: list) -> None:
    """A named persistence, an horizon within the loop's three years, or a spending rule
    without the loop: one path in the simulator, so one search here."""
    report = run_search(_request(**overrides))
    assert [s["persistence"] for s in report["searches"]] == expected


def test_every_bundle_is_in_the_report_and_no_candidate_names_the_closest() -> None:
    """GUARD 7. A target out of reach — the debt down five points — leaves no candidate.
    The report still holds the three bundles, each inside its own corners, and names the
    one closest to the target, so that « none » says how far the grid was."""
    report = run_search(_request(target={"at_most_points": -5.0}, persistence="tenu"))
    (search,) = report["searches"]
    assert search["candidates"] == []
    evaluations = search["evaluations"]
    assert [e["knobs"]["decote_taux"] for e in evaluations] == [0.40, 0.45, 0.50]
    assert all(e["corner_low"] <= e["delta_aged"] <= e["corner_high"]
               for e in evaluations)
    assert all(not e["meets_target"] for e in evaluations)
    closest = min(evaluations, key=lambda e: abs(e["delta_aged"] + 0.05))
    assert search["closest"] == closest
    assert report["bundles"] == 3 and report["hypotheses"]["target_share"] == -0.05


def test_a_candidate_reads_robust_or_dependent_on_theta() -> None:
    """The verdict travels into the report. A target the first bundle meets at θ but not
    at its highest corner makes it « dépend de θ », named by that corner; a target above
    every corner makes it « robuste »."""
    first = run_search(_request(persistence="tenu"))["searches"][0]["evaluations"][0]
    assert first["corner_low"] < first["delta_aged"] < first["corner_high"]
    between = (first["delta_aged"] + first["corner_high"]) / 2 * 100
    found = run_search(_request(persistence="tenu", target={"at_most_points": between}))
    candidate = next(c for c in found["searches"][0]["candidates"]
                     if c["knobs"] == first["knobs"])
    assert candidate["meets_target"] and candidate["robust"] is False
    assert candidate["verdict"].startswith("dépend de θ : au coin multiplicateur_macro")
    above = first["corner_high"] * 100 + 1.0
    found = run_search(_request(persistence="tenu", target={"at_most_points": above}))
    candidate = next(c for c in found["searches"][0]["candidates"]
                     if c["knobs"] == first["knobs"])
    assert candidate["robust"] is True and candidate["verdict"].startswith("robuste")


# --------------------------------------------------------------------------- #
# the command: the simulator's seams, and the code it ran on
# --------------------------------------------------------------------------- #
@pytest.fixture
def command(monkeypatch, tmp_path) -> dict:
    """The command with its pass stubbed, the start constructed and the tree clean."""
    seen: list = []
    monkeypatch.setattr(main, "_price_first_year", pass_stub(seen))
    monkeypatch.setattr(main, "_predictif_macro_store", synthetic_macro_store)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    monkeypatch.setattr(recherche, "code_state", lambda: (COMMIT, False))

    def launch(payload: dict) -> tuple[int, dict | None]:
        path = tmp_path / "requete.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        code = cli.main(["exploration", str(path), "--out-dir", str(tmp_path)])
        out = tmp_path / f"exploration_{payload['name']}.json"
        return code, json.loads(out.read_text(encoding="utf-8")) if out.exists() else None

    return {"seen": seen, "launch": launch, "monkeypatch": monkeypatch}


def test_the_command_prices_both_views_and_names_its_commit(command) -> None:
    code, report = command["launch"](_request(persistence="tenu"))
    assert code == 0
    assert report["commit"] == COMMIT and report["question"].startswith("Une décote")
    assert sorted(v for _, v in command["seen"]) == ["figee"] * 3 + ["vieillie"] * 3
    assert report["hypotheses"]["spending_name"] == "Dépenses gelées en volume"
    assert report["views"] == recherche.VIEW_NOTES


def test_a_tree_whose_source_differs_from_its_commit_is_refused(command) -> None:
    """GUARD 4. The report names the commit it ran on: with `src/` modified, that name
    would be false. Refused before any pass, and nothing is written."""
    command["monkeypatch"].setattr(recherche, "code_state", lambda: (COMMIT, True))
    code, report = command["launch"](_request(persistence="tenu"))
    assert code == 1 and report is None and command["seen"] == []


def test_the_explorer_prices_what_the_simulator_prices(command) -> None:
    """GUARD 6, ONE PRICING PATH. The same reform, the same hypotheses and the same stubbed
    pass: the debt difference the search reads for the bundle is the one
    `/predictif/simulate` returns, behaviour, loop and persistence included. An explorer
    that built its scenarios, or priced its first year, its own way would part here."""
    payload = _request(bounds=[{"knob": "decote_taux", "low": 0.45, "high": 0.45,
                                "step": 0.05}], persistence="tenu", behavioural=True)
    code, report = command["launch"](payload)
    assert code == 0
    with TestClient(main.app) as client:
        response = client.post("/predictif/simulate", json={
            key: payload[key] for key in ("spending", "growth", "rate", "horizon", "theta",
                                          "uprating", "behavioural", "macro",
                                          "persistence")} | {
            "reform": {"decote_taux": 0.45}})
    assert response.status_code == 200, response.text
    (evaluation,) = report["searches"][0]["evaluations"]
    assert evaluation["delta_aged"] == pytest.approx(response.json()["delta"][-1],
                                                     rel=1e-12)


# --------------------------------------------------------------------------- #
# the frozen view, through the simulator's own seam
# --------------------------------------------------------------------------- #
def test_the_frozen_view_is_priced_on_the_population_as_it_is(monkeypatch) -> None:
    """The real `_price_first_year`, its pass stubbed one layer down: « figee » hands the
    pass the 2024 population untouched and says so in its note; « vieillie » ages it, as
    the simulator always has (D-226); any other name is refused rather than read as one
    of them."""
    from impots.api.schemas import PopulationSimulateRequest

    population = pl.DataFrame({
        "person_id": [0], "household_id": ["h0"], "weight": [500.0], "age": [40],
        "salaire_brut_annuel": [30_000.0], "chomage_annuel": [0.0],
        "pension_annuelle": [0.0], "loyer_mensuel": [600.0]})
    passed: list = []

    def run(request, frame):
        passed.append(frame)
        return (SimpleNamespace(households=None),
                SimpleNamespace(reform_cost=1e9, deciles=[]))

    monkeypatch.setattr(main, "_population_frame", lambda: population)
    monkeypatch.setattr(main, "_run_population", run)
    request = PopulationSimulateRequest(reform={"decote_taux": 0.45}, year=2026)
    hypotheses = main._predictif_hypotheses(ExplorationRequest.model_validate(_request()))
    frozen = main._price_first_year(request, uprating=hypotheses.uprating, view="figee")
    aged = main._price_first_year(request, uprating=hypotheses.uprating)
    assert passed[0].equals(population)
    assert passed[1]["salaire_brut_annuel"].to_list() == pytest.approx([30_000 * 1.03 ** 2])
    assert frozen.view == "figee" and "Vue « figée »" in frozen.note
    assert aged.view == "vieillie" and "Vue « vieillie »" in aged.note
    with pytest.raises(ValueError, match="vue « gelee » inconnue"):
        main._price_first_year(request, uprating=hypotheses.uprating, view="gelee")
