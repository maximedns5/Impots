"""Phase 10 M4 — the §7 indices of the bundle nearest the target, in the search's report.

PHASE10_SPEC §5: « pour le paquet le plus proche de la cible de chaque instrument, les
indices de §7 tirés de la même passe ». What is held here, without data: the nearest
bundle is the one the report names, its indices come from the passes the search already
ran (no pass more), each search reads the chain-stage indices off its own path, the indices
are the simulator's for the same reform, and a report whose indices name a bundle it did
not evaluate is refused.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from exploration_cases import COMMIT, START, pass_stub, run_search
from exploration_cases import exploration_request as _request
from impots import service
from impots.api import main
from impots.api.schemas import ExplorationReport, ExplorationRequest
from impots.dette import reference
from impots.population import cli
from impots.predictif import indices, recherche
from macro_cases import synthetic_macro_store


def _nearest(search: dict, target: float = 0.0) -> dict:
    return min(search["evaluations"], key=lambda e: (abs(e["delta_aged"] - target),
                                                     sorted(e["knobs"].items())))


@pytest.mark.parametrize("points", [0.0, 5.0])
def test_the_nearest_bundle_carries_its_indices_from_the_passes_already_run(
        points: float) -> None:
    """At a target of 0 the nearest is the smallest cut; at 5 points, which every bundle
    meets, the largest: the nearest to the target, candidate or not."""
    seen: list = []
    report = run_search(_request(persistence="tenu", behavioural=True,
                                 target={"at_most_points": points}), seen=seen)
    assert len(seen) == 2 * report["bundles"]
    (search,) = report["searches"]
    nearest = _nearest(search, points / 100)
    assert nearest == search["evaluations"][0 if points == 0.0 else -1]
    assert search["indices"]["knobs"] == nearest["knobs"]
    assert search["indices"]["delta_aged"] == nearest["delta_aged"]
    assert [row["key"] for row in search["indices"]["rows"]] == [
        spec.key for spec in indices.CATALOGUE]
    debt = next(r for r in search["indices"]["rows"] if r["key"] == "dette")
    assert debt["values"][str(START.year + 5)] == pytest.approx(nearest["delta_aged"])


def test_side_by_side_each_search_reads_the_chain_off_its_own_path() -> None:
    """Past three years, every persistence (« lue », « éteint », « tenu », D-336): the
    mechanical and behavioural indices are the same pass's, the debt is each one's own."""
    report = run_search(_request(behavioural=True))
    rows = {s["persistence"]: s["indices"]["rows"] for s in report["searches"]}
    assert sorted(rows) == ["eteint", "lue", "tenu"]
    eteint, tenu = rows["eteint"], rows["tenu"]

    def own(rows):
        return [r for r in rows if r["stage"] != indices.CHAINE]

    def debt(rows):
        return next(r for r in rows if r["key"] == "dette")["values"]

    assert own(eteint) == own(tenu)
    assert debt(eteint) != debt(tenu)


def _with_deciles(stub):
    def priced(request, **kw):
        first = stub(request, **kw)
        first.deciles = [SimpleNamespace(decile=d, mean_delta=10.0 * d) for d in (1, 2)]
        return first
    return priced


def test_the_indices_are_the_simulators(monkeypatch, tmp_path) -> None:
    """GUARD 6, for the indices: the same reform, hypotheses and stubbed pass give the
    search's indices and `/predictif/simulate`'s, row for row, deciles included."""
    seen: list = []
    monkeypatch.setattr(service, "price_first_year", _with_deciles(pass_stub(seen)))
    monkeypatch.setattr(service, "predictif_macro_store", synthetic_macro_store)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    monkeypatch.setattr(recherche, "code_state", lambda: (COMMIT, False))
    payload = _request(bounds=[{"knob": "decote_taux", "low": 0.45, "high": 0.45,
                                "step": 0.05}], persistence="tenu", behavioural=True)
    path = tmp_path / "requete.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert cli.main(["exploration", str(path), "--out-dir", str(tmp_path)]) == 0
    report = json.loads((tmp_path / "exploration_decote.json").read_text(encoding="utf-8"))
    with TestClient(main.app) as client:
        response = client.post("/predictif/simulate", json={
            key: payload[key] for key in ("spending", "growth", "rate", "horizon", "theta",
                                          "uprating", "behavioural", "macro",
                                          "persistence")} | {
            "reform": {"decote_taux": 0.45}})
    assert response.status_code == 200, response.text
    rows = report["searches"][0]["indices"]["rows"]
    assert rows == response.json()["indices"]
    assert report["searches"][0]["indices"]["absent"] == response.json()["absent"]
    assert report["searches"][0]["indices"]["closed"] == response.json()["closed"]
    assert next(r for r in rows if r["key"] == "revenu_disponible_deciles")["values"] == {
        "D1": 10.0, "D2": 20.0}


@pytest.mark.parametrize("how", ["stranger", "delta"])
def test_indices_of_a_bundle_not_evaluated_are_refused(how: str) -> None:
    report = json.loads(json.dumps(run_search(_request(persistence="tenu"))))
    report.update(commit=COMMIT, computed="2026-10-21")
    named = report["searches"][0]["indices"]
    if how == "stranger":
        named["knobs"] = {"decote_taux": 0.99}
    else:
        named["delta_aged"] += 1.0
    with pytest.raises(ValidationError, match="qui n'est pas un paquet évalué"):
        ExplorationReport.model_validate(report)


def test_a_law_read_for_another_year_is_refused() -> None:
    """The factor scales the barème of the year it prices: a law read for 2027 with a
    first projected year of 2026 would scale the wrong one."""
    request = ExplorationRequest.model_validate(_request(bounds=[
        {"knob": "ir_bareme_echelle", "low": 0.95, "high": 0.95, "step": 0.05}]))
    law = {"year": START.year + 2, "bareme": [{"threshold": 0.0, "rate": 0.0},
                                              {"threshold": 11_600.0, "rate": 0.11}]}
    with pytest.raises(recherche.RechercheError, match="première année projetée"):
        recherche.run(request, price=lambda reform, view: None,
                      hypotheses=service.predictif_hypotheses(request), start=START, law=law)


def test_the_report_says_what_the_chain_lacks() -> None:
    """Without the loop, the chain says the feedback is absent, with why; the report
    carries it with the indices, so that an unmeasured loop never reads as a loop worth
    nothing (D-238). An absence without its reason is refused."""
    report = json.loads(json.dumps(run_search(_request(macro=False))))
    report.update(commit=COMMIT, computed="2026-10-21")
    (search,) = report["searches"]
    assert search["indices"]["absent"]["rétroaction"].strip()
    assert search["indices"]["closed"]
    search["indices"]["absent"]["rétroaction"] = " "
    with pytest.raises(ValidationError, match="absent sans sa raison"):
        ExplorationReport.model_validate(report)
