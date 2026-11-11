"""Phase 9 M1b — `impots predictif` and the endpoints that read its reports.

The command runs end to end on a tiny population with the engine pass stubbed: what is
held is the command's own wiring — both views priced every year, the report written where
the API reads it, the refusals before any pass. The pass itself has its own tests.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import polars as pl
import pytest
from fastapi.testclient import TestClient

from impots.api import main as api_main
from impots.dette import reference
from impots.population import aggregate, cli, runner

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
ARGS = ["predictif", "gel_bareme", "--reference", "reconduit",
        "--spending", "gele_en_volume",
        "--growth-name", "Croissance réelle 1 %, prix 2 %", "--real", "0.01",
        "--prices", "0.02",
        "--rate-name", "Taux implicite tenu à son niveau de 2025",
        "--rate-kind", "implicite_tenu", "--horizon", "3", "--theta", "0.5",
        "--wage", "0.03", "--hypothesis-source", "test : 2 % de prix, 3 % de salaires"]


@pytest.fixture
def stubbed(monkeypatch, tmp_path) -> dict:
    """A five-person population, a stubbed pass that records what it priced, and a start
    that needs no INSEE file."""
    processed = tmp_path / "processed"
    processed.mkdir()
    pl.DataFrame({"person_id": [1, 2, 3, 4, 5], "salaire_brut_annuel": [30_000.0] * 5,
                  "pension_annuelle": [0.0] * 5, "chomage_annuel": [0.0] * 5,
                  "revenu_non_salarie_annuel": [0.0] * 5,
                  "loyer_mensuel": [500.0] * 5}).write_parquet(
        processed / "population_2024.parquet")
    monkeypatch.setattr(cli, "PROCESSED", processed)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    seen: list = []

    def run(pop, *, year, reform, tier, sample):
        aged = float(pop["salaire_brut_annuel"][0]) > 30_000.0
        seen.append((year, "vieillie" if aged else "figee", sample))
        return SimpleNamespace(households=SimpleNamespace(cost=5e9 * (1.1 if aged else 1.0)))

    monkeypatch.setattr(runner, "run", run)
    monkeypatch.setattr(aggregate, "aggregate",
                        lambda households: SimpleNamespace(reform_cost=households.cost,
                                                           totals={}))
    return {"seen": seen, "out": tmp_path / "reports"}


def test_every_year_is_priced_in_both_views_and_the_report_written(stubbed) -> None:
    code = cli.main([*ARGS, "--out-dir", str(stubbed["out"])])
    assert code == 0
    years = sorted({(y, v) for y, v, _ in stubbed["seen"]})
    assert years == [(y, v) for y in (2026, 2027, 2028) for v in ("figee", "vieillie")]
    assert {s for _, _, s in stubbed["seen"]} == {20_000}
    report = json.loads((stubbed["out"] / "predictif_gel_bareme.json").read_text())
    assert [row["year"] for row in report["years"]] == [2026, 2027, 2028]
    assert report["spending_name"] == "Dépenses gelées en volume"
    assert all(row["delta_aged"] > row["delta_frozen"] > 0 for row in report["years"])


@pytest.mark.parametrize("flag", ["--spending", "--growth-name", "--rate-kind",
                                  "--horizon", "--theta", "--wage",
                                  "--hypothesis-source"])
def test_no_hypothesis_of_the_command_has_a_default(stubbed, flag: str) -> None:
    args = list(ARGS)
    index = args.index(flag)
    del args[index:index + 2]
    with pytest.raises(SystemExit):
        cli.main(args)
    assert stubbed["seen"] == []


def test_a_shipped_rule_refuses_a_name_before_any_pass(stubbed, capsys) -> None:
    code = cli.main([*ARGS, "--spending-name", "Autre", "--out-dir", str(stubbed["out"])])
    assert code == 1 and "ignoré" in capsys.readouterr().err
    assert stubbed["seen"] == []


def test_a_theta_outside_the_unit_interval_is_refused_before_any_pass(
        stubbed, capsys) -> None:
    args = list(ARGS)
    args[args.index("--theta") + 1] = "1.2"
    assert cli.main([*args, "--out-dir", str(stubbed["out"])]) == 1
    assert "écrêté" in capsys.readouterr().err
    assert stubbed["seen"] == []


def test_a_likely_scenario_name_is_refused_before_any_pass(stubbed, capsys) -> None:
    args = list(ARGS)
    args[args.index("--growth-name") + 1] = "Croissance probable"
    assert cli.main([*args, "--out-dir", str(stubbed["out"])]) == 1
    assert "probabilité" in capsys.readouterr().err
    assert stubbed["seen"] == []


# --------------------------------------------------------------------------- #
# GET /predictif — the reports, read and never run
# --------------------------------------------------------------------------- #
@pytest.fixture
def served(stubbed, monkeypatch) -> TestClient:
    assert cli.main([*ARGS, "--out-dir", str(stubbed["out"])]) == 0
    monkeypatch.setattr(api_main, "TRAJECTORIES", stubbed["out"])
    with TestClient(api_main.app) as client:
        yield client


def test_the_report_is_listed_and_served(served) -> None:
    assert served.get("/predictif").json() == {"rapports": ["gel_bareme"]}
    body = served.get("/predictif/gel_bareme").json()
    assert body["rate_name"] == "Taux implicite tenu à son niveau de 2025"
    assert len(body["years"]) == 3 and "rétroaction" in body["absent"]
    assert body["theta_applied"] is False and len(body["theta"]) == 20  # D-252, D-263


def test_an_unknown_report_is_a_404_and_a_path_is_refused(served) -> None:
    assert served.get("/predictif/inconnu").status_code == 404
    assert served.get("/predictif/..%2Fsecret").status_code in (404, 422)


def test_every_name_the_list_gives_reads_back_from_the_committed_reports() -> None:
    """GUARD (D-236). `GET /predictif` lists every `predictif_*.json` under `reports/`, and
    the page opens the first. The snapshot of D-228's worked example was committed as
    `reports/predictif_exemple.json`: listed as « exemple », first in the order, a 500 on
    reading — and the page, finding it unreadable, drew no annual report at all, without a
    word. Every name the list gives must read."""
    with TestClient(api_main.app, raise_server_exceptions=False) as client:
        names = client.get("/predictif").json()["rapports"]
        for name in names:
            response = client.get(f"/predictif/{name}")
            assert response.status_code == 200, (name, response.text[:200])


# --------------------------------------------------------------------------- #
# The CSG path of D-236, served re-priced (D-280, D-281)
# --------------------------------------------------------------------------- #
CSG_D236 = "predictif_csg_deductible_demi_point.json"
FIRST_ROUND = api_main.TRAJECTORIES / "predictif_premier_tour"


FRAME = ("scenario", "titre", "source", "reference", "spending_name", "growth_name",
         "rate_name", "start", "uprating_note", "behavioural", "macro", "persistence")


def _frame(report: dict) -> dict:
    """What a replay keeps of the path it re-prices: the question and its frame, and the
    reference path that frame alone gives; not the figures the code gives."""
    return {
        **{key: report[key] for key in FRAME},
        "years": [(row["year"], row["basis"], row["reference"]) for row in report["years"]],
        "side_by_side": [(path["persistence"], path["label"])
                         for path in report["side_by_side"] or []],
        "theta": set(report["theta"].values()),
    }


def _not_a_replay(original: dict, served: dict) -> list[str]:
    """What keeps `served` from being `original` priced again on later code: the frame
    fields it changes, a provenance it does not give, an original that already had one."""
    found = ["original"] if "commit" in original else []
    if not served.get("commit") or served.get("dirty") is not False or not served.get(
            "where"):
        found.append("provenance")
    before, after = _frame(original), _frame(served)
    return found + [key for key in before if before[key] != after[key]]


def _reports() -> tuple[dict, dict]:
    return (json.loads((FIRST_ROUND / CSG_D236).read_text(encoding="utf-8")),
            json.loads((api_main.TRAJECTORIES / CSG_D236).read_text(encoding="utf-8")))


def test_the_csg_path_of_d236_is_served_re_priced_in_its_own_frame() -> None:
    """GUARD (D-281). D-236's annual CSG path ran under the defect of D-276: its two views
    shared their marginal rates. The report served under its name is its replay on the
    fix, which names the code that priced it; the original stays, unserved, under
    `reports/predictif_premier_tour/`. A replay in another frame would answer another
    question under D-236's name."""
    assert _not_a_replay(*_reports()) == []


@pytest.mark.parametrize("edit, named", [
    *[(key, key) for key in ("scenario", "titre", "source", "reference", "spending_name",
                             "growth_name", "rate_name", "start", "uprating_note",
                             "behavioural", "macro", "persistence")],
    ("basis", "years"), ("reference_path", "years"), ("theta", "theta"),
    ("side_by_side", "side_by_side"), ("commit", "provenance"), ("dirty", "provenance"),
    ("where", "provenance"), ("original", "original"),
])
def test_a_replay_in_another_frame_is_not_d236_s_path(edit: str, named: str) -> None:
    """Each field, edited alone, is refused under its own name."""
    original, served = _reports()
    other = json.loads(json.dumps(served))
    if edit == "basis":
        other["years"][-1]["basis"] = "legislated"
    elif edit == "reference_path":
        other["years"][-1]["reference"] += 1e-9
    elif edit == "theta":
        other["theta"]["multiplicateur_macro"] = 0.4
    elif edit == "side_by_side":
        other["side_by_side"] = other["side_by_side"][:1]
    elif edit in ("commit", "where"):
        other[edit] = ""
    elif edit == "dirty":
        other["dirty"] = True
    elif edit == "original":
        original = served
    else:
        other[edit] = ("autre", other[edit])
    assert _not_a_replay(original, other) == [named]


def test_every_field_that_differs_is_named() -> None:
    original, served = _reports()
    other = json.loads(json.dumps(served))
    other["titre"], other["growth_name"], other["dirty"] = "autre", "autre", True
    assert _not_a_replay(original, other) == ["provenance", "titre", "growth_name"]
