"""Phase 10 M2 — `GET /explorations`, the searches read back (PHASE10_SPEC §3).

A search runs as a command and writes a report; the API only reads it. What is held here:
that the report the command writes is the one the API reads, field for field; that the
schema refuses a report a reader would misread — a candidate without its θ verdict, or
not among the bundles evaluated, a bundle missing, « none » without the closest, two
searches under one persistence; and that every report committed under `reports/` still
reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from exploration_cases import COMMIT, run_search
from exploration_cases import exploration_request as _request
from impots.api import main
from impots.api.schemas import ExplorationReport

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def _report(**overrides) -> dict:
    report = run_search(_request(**overrides))
    report.update(commit=COMMIT, computed="2026-10-21")
    return json.loads(json.dumps(report))


@pytest.fixture
def reports(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "TRAJECTORIES", tmp_path)

    def write(name: str, report: dict) -> None:
        (tmp_path / f"exploration_{name}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")

    return write


def test_the_report_the_command_writes_is_the_one_the_api_reads(client, reports) -> None:
    """The writer and the reader define the same report: both persistence searches, every
    bundle with its first-year cost in both views, read back without a field lost."""
    report = _report()
    reports("decote", report)
    assert client.get("/explorations").json() == {"explorations": ["decote"]}
    response = client.get("/explorations/decote")
    assert response.status_code == 200, response.text
    assert response.json() == report
    first = response.json()["searches"][0]["evaluations"][1]
    assert first["knobs"] == {"decote_taux": 0.45}
    assert first["cost_aged_eur"] == pytest.approx(7e9)
    assert first["cost_frozen_eur"] == pytest.approx(6.3e9)


def test_a_name_the_report_guard_refuses_is_a_422_and_an_unknown_one_a_404(
        client, reports) -> None:
    """GUARD 8. The same name guard as every other report."""
    assert client.get("/explorations/a%0Ab").status_code == 422
    response = client.get("/explorations/inconnue")
    assert response.status_code == 404 and "inconnue" in response.json()["detail"]


def _break(report: dict, how: str) -> dict:
    search = report["searches"][0]
    if how == "verdict":
        search["candidates"][0]["verdict"] = ""
    elif how == "robust":
        search["candidates"][0]["robust"] = None
    elif how == "stranger":
        search["candidates"][0]["knobs"] = {"decote_taux": 0.99}
    elif how == "corners":
        search["evaluations"][0]["corner_high"] += 1.0
    elif how == "closest":
        search["candidates"] = []
        search["closest"] = None
    elif how == "bundle":
        report["bundles"] += 1
    elif how == "persistence":
        report["searches"][1]["persistence"] = search["persistence"]
    elif how == "commit":
        report["commit"] = " "
    return report


@pytest.mark.parametrize("how, needle", [
    ("verdict", "sans verdict θ"),
    ("robust", "sans verdict θ"),
    ("stranger", "absent des paquets évalués"),
    ("corners", "n'est pas celle de ses coins"),
    ("closest", "aucun paquet le plus proche"),
    ("bundle", "chaque paquet figure au rapport"),
    ("persistence", "chacun une fois"),
    ("commit", "rapport sans commit"),
])
def test_a_report_a_reader_would_misread_is_refused(client, reports, how: str,
                                                    needle: str) -> None:
    """GUARD 7. Each a report the page would draw wrong: a candidate read as robust for
    want of its verdict, one whose cost and corners are nowhere, an extent the corners do
    not give, « none » with no distance, a bundle dropped, one persistence twice, or no
    commit to replay it from. Refused, by the schema and by the API, rather than shown in
    part."""
    report = _break(_report(target={"at_most_points": 5.0}), how)
    with pytest.raises(ValidationError, match=needle):
        ExplorationReport.model_validate(report)
    reports("cassee", report)
    response = client.get("/explorations/cassee")
    assert response.status_code == 500 and needle in response.json()["detail"]


def test_every_committed_exploration_report_still_reads() -> None:
    """A report committed under `reports/` that the schema has since outgrown would fail
    only when someone opened the page. It fails here instead: re-run the search."""
    found = sorted((ROOT / "reports").glob("exploration_*.json"))
    assert found, "aucun rapport d'exploration commité : la garde ne garderait rien"
    for path in found:
        ExplorationReport.model_validate_json(path.read_text(encoding="utf-8"))
