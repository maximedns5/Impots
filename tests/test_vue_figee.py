"""La vue figée rechiffrée (D-278) : ce qui est rejoué n'est pas choisi à la main.

Le lanceur rejoue, telles quelles, les explorations de l'étude dont la boîte porte une
ligne de C1 ou de C7 : les deux canaux qui lisent les taux marginaux, que la vue figée
lisait sur la vue vieillie (D-276). Le menu se lit sur les rapports commités. Chaque
requête rejouée est celle que le rapport a jouée, et la commande, relue par l'analyseur
de la commande elle-même, ne change que le répertoire de sortie et le lieu. Le lanceur
refuse un `src/` modifié ou un rapport déjà là, avant toute passe.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from impots.api.schemas import ExplorationRequest
from impots.behavioural import channels
from impots.population import cli
from impots.predictif import recherche

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "vue_figee.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load("vue_figee", SCRIPT)


def _rows(report: dict) -> set[str]:
    return {part.split(" = ")[0] for search in report["searches"]
            for evaluation in search["evaluations"]
            for label, _ in evaluation.get("corners") or [] for part in label.split(", ")}


def test_the_menu_is_the_study_s_instruments_whose_box_reads_marginal_rates(script) -> None:
    """Read apart on the committed reports: an instrument is replayed exactly when its box
    carries a row of C1 or C7, in the study's order (D-237)."""
    annual = _load("etude_annuelle", ROOT / "scripts" / "etude_annuelle.py")
    assert script.STUDY == annual.MENU
    rates = set(channels.C1_KEYS) | set(channels.C7_KEYS)
    expected = tuple(key for key in annual.MENU if _rows(json.loads(
        (script.REPORTS / f"exploration_etude_{key}.json").read_text(encoding="utf-8")))
        & rates)
    assert script.menu() == expected == ("csg", "decote", "ir")


def test_an_instrument_whose_box_reads_no_rate_is_not_replayed(script, tmp_path) -> None:
    """The menu follows the reports: a CSG box without its labour-supply rows has nothing
    the defect of D-276 touched, and is not replayed."""
    for key in script.STUDY:
        report = json.loads((script.REPORTS / f"exploration_etude_{key}.json").read_text(
            encoding="utf-8"))
        if key == "csg":
            for search in report["searches"]:
                for evaluation in search["evaluations"]:
                    evaluation["corners"] = [
                        [", ".join(p for p in label.split(", ")
                                   if not p.startswith("labour_supply")), value]
                        for label, value in evaluation["corners"]]
        (tmp_path / f"exploration_etude_{key}.json").write_text(json.dumps(report),
                                                                encoding="utf-8")
    assert script.menu(tmp_path) == ("decote", "ir")


def test_the_command_replays_the_study_s_request_as_it_is(script) -> None:
    """Read back by the command's own parser: the committed request of the study, into the
    replay's directory, with the place said; nothing else."""
    for key in script.menu():
        args = cli.build_parser().parse_args(script.argv(key, where="ici"))
        assert args.func is cli.cmd_exploration
        assert Path(args.request) == script.REQUESTS / f"{key}.json"
        assert args.out_dir == str(script.OUT) and args.ou == "ici"
        assert args.max_paquets == cli.build_parser().parse_args(
            ["exploration", "x.json"]).max_paquets
        played = json.loads((script.REPORTS / f"exploration_etude_{key}.json").read_text(
            encoding="utf-8"))["request"]
        validated = ExplorationRequest.model_validate(played).model_dump(mode="json")
        assert script.request(key) == validated
        assert validated["bounds"] == played["bounds"] and validated["name"] == played["name"]


def test_a_request_that_is_not_the_one_the_report_played_is_refused(script, tmp_path) -> None:
    """The replay is the study's request, unchanged: an edited one would rechiffre another
    exploration under the study's name."""
    request = json.loads((script.REQUESTS / "decote.json").read_text(encoding="utf-8"))
    request["bounds"][0]["low"] = 0.2
    (tmp_path / "decote.json").write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(script.VueFigeeError, match=re.escape("n'est pas celle que")):
        script.argv("decote", where="ici", requests=tmp_path)


@pytest.fixture
def launcher(script, monkeypatch, tmp_path):
    out = tmp_path / "vue_figee"
    monkeypatch.setattr(script, "OUT", out)
    calls: list = []
    monkeypatch.setattr(script.subprocess, "run",
                        lambda command, **kw: calls.append(command)
                        or SimpleNamespace(returncode=0))
    return SimpleNamespace(out=out, calls=calls, monkeypatch=monkeypatch)


def test_the_launcher_replays_the_menu_one_after_the_other(script, launcher) -> None:
    launcher.monkeypatch.setattr(recherche, "code_state", lambda root=None: ("c0ffee", False))
    assert script.launch("ici") == 0
    assert [Path(c[c.index("exploration") + 1]).stem for c in launcher.calls] == [
        "csg", "decote", "ir"]
    assert all(c[c.index("--out-dir") + 1] == str(launcher.out) for c in launcher.calls)
    assert all(c[c.index("--ou") + 1] == "ici" for c in launcher.calls)


def test_a_replay_that_fails_stops_the_ones_after_it(script, launcher, capsys) -> None:
    launcher.monkeypatch.setattr(recherche, "code_state", lambda root=None: ("c0ffee", False))
    codes = iter([0, 3, 0])
    launcher.monkeypatch.setattr(script.subprocess, "run",
                                 lambda command, **kw: launcher.calls.append(command)
                                 or SimpleNamespace(returncode=next(codes)))
    assert script.launch("ici") == 3
    assert len(launcher.calls) == 2
    assert "les suivants ne tournent pas" in capsys.readouterr().err


@pytest.mark.parametrize("how, needle", [
    ("dirty", "modifications non commitées"),
    ("there", "un rapport n'est pas écrasé en silence"),
])
def test_the_launcher_refuses_before_any_pass(script, launcher, capsys, how: str,
                                              needle: str) -> None:
    launcher.monkeypatch.setattr(recherche, "code_state",
                                 lambda root=None: ("c0ffee", how == "dirty"))
    if how == "there":
        launcher.out.mkdir()
        (launcher.out / "exploration_etude_ir.json").write_text("{}", encoding="utf-8")
    assert script.launch("ici") == 1
    assert launcher.calls == [] and needle in capsys.readouterr().err
