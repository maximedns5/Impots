"""C1 sur quatre échantillons (D-285) : ce qui est rejoué n'est pas choisi à la main.

Le lanceur rejoue, telles quelles, les explorations de l'étude dont la boîte porte une
ligne de C1, puis leurs chemins annuels (D-277), sur la méthode de D-284. Le menu se lit
sur les rapports commités. Chaque commande, relue par l'analyseur de la commande, ne
change que le répertoire de sortie et le lieu. Le lanceur refuse un `src/` modifié ou un
rapport déjà là, avant toute passe.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from impots.behavioural import channels
from impots.population import cli
from impots.predictif import recherche

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load("c1_quatre")


def _rows(report: dict) -> set[str]:
    return {part.split(" = ")[0] for search in report["searches"]
            for evaluation in search["evaluations"]
            for label, _ in evaluation.get("corners") or [] for part in label.split(", ")}


def test_the_menu_is_the_study_s_instruments_whose_box_reads_c1(script) -> None:
    annual = _load("etude_annuelle")
    assert script.STUDY == annual.MENU
    expected = tuple(key for key in annual.MENU if _rows(json.loads(
        (script.REPORTS / f"exploration_etude_{key}.json").read_text(encoding="utf-8")))
        & set(channels.C1_KEYS))
    assert script.menu() == expected == ("decote", "ir")


def test_an_instrument_whose_box_reads_no_c1_row_is_not_replayed(script, tmp_path) -> None:
    for key in script.STUDY:
        report = json.loads((script.REPORTS / f"exploration_etude_{key}.json").read_text(
            encoding="utf-8"))
        if key == "decote":
            for search in report["searches"]:
                for evaluation in search["evaluations"]:
                    evaluation["corners"] = [
                        [", ".join(p for p in label.split(", ") if not p.startswith("eti_")),
                         value] for label, value in evaluation["corners"]]
        (tmp_path / f"exploration_etude_{key}.json").write_text(json.dumps(report),
                                                                encoding="utf-8")
    assert script.menu(tmp_path) == ("ir",)


def test_the_explorations_replay_the_study_s_requests_as_they_are(script) -> None:
    for key in script.menu():
        args = cli.build_parser().parse_args(script.exploration_argv(key, where="ici"))
        assert args.func is cli.cmd_exploration
        assert Path(args.request) == script.REQUESTS / f"{key}.json"
        assert args.out_dir == str(script.OUT) and args.ou == "ici"
        assert args.max_paquets == cli.build_parser().parse_args(
            ["exploration", "x.json"]).max_paquets


def test_the_annual_paths_are_the_study_s_launcher_s_into_this_directory(script) -> None:
    annual = _load("etude_annuelle")
    for key in script.menu():
        command = script.annual_argv(key, where="ici")
        assert command == annual.argv(key, where="ici", out=script.OUT)
        args = cli.build_parser().parse_args(command)
        assert args.func is cli.cmd_predictif and args.scenario == annual.name(key)
        assert args.out_dir == str(script.OUT) and args.ou == "ici"


def test_a_request_that_is_not_the_one_the_report_played_is_refused(script, tmp_path) -> None:
    request = json.loads((script.REQUESTS / "decote.json").read_text(encoding="utf-8"))
    request["bounds"][0]["low"] = 0.2
    (tmp_path / "decote.json").write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(script.C1QuatreError, match=re.escape("n'est pas celle que")):
        script.exploration_argv("decote", where="ici", requests=tmp_path)


@pytest.fixture
def launcher(script, monkeypatch, tmp_path):
    out = tmp_path / "c1_quatre"
    monkeypatch.setattr(script, "OUT", out)
    calls: list = []
    monkeypatch.setattr(script.subprocess, "run",
                        lambda command, **kw: calls.append(command)
                        or SimpleNamespace(returncode=0))
    monkeypatch.setattr(recherche, "code_state", lambda root=None: ("c0ffee", False))
    return SimpleNamespace(out=out, calls=calls, monkeypatch=monkeypatch)


def test_the_launcher_replays_the_explorations_then_the_paths(script, launcher) -> None:
    assert script.launch("ici") == 0
    kinds = [(c[c.index("-m") + 2], Path(c[c.index("-m") + 3]).stem) for c in launcher.calls]
    assert kinds == [("exploration", "decote"), ("exploration", "ir"),
                     ("predictif", "etude_annuel_decote"), ("predictif", "etude_annuel_ir")]
    assert all(c[c.index("--ou") + 1] == "ici" for c in launcher.calls)


def test_a_replay_that_fails_stops_the_ones_after_it(script, launcher, capsys) -> None:
    codes = iter([0, 3, 0, 0])
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
        (launcher.out / "predictif_etude_annuel_ir.json").write_text("{}", encoding="utf-8")
    assert script.launch("ici") == 1
    assert launcher.calls == [] and needle in capsys.readouterr().err
