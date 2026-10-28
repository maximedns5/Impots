"""L'étude sur le chemin annuel (D-275) : ses scénarios et sa commande ne sont pas saisis.

Les scénarios commités sous `etude/annuel/` sont ce que `scripts/etude_annuelle.py`
construit depuis les rapports commités de l'étude : le paquet le plus proche de la cible
de chaque instrument, et pour l'IR la transformation appliquée au barème que le rapport a
lu. La commande que le lanceur fait tourner reprend le cadre de la requête de l'étude,
champ pour champ, relue par l'analyseur de la commande elle-même. Et le lanceur refuse un
`src/` modifié ou un rapport déjà là, avant toute passe.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from impots import scenarios as scenarios_module
from impots.population import cli
from impots.predictif import recherche

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "etude_annuelle.py"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("etude_annuelle", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _report(script, key: str) -> dict:
    return json.loads((script.REPORTS / f"exploration_etude_{key}.json").read_text(
        encoding="utf-8"))


def test_the_committed_scenarios_are_built_from_the_study_s_reports(script) -> None:
    """GUARD. A scenario edited by hand, one more beside them, or a study report re-run
    without its scenario, fails here; each one reads back through the scenario loader."""
    for key in script.MENU:
        built = script.scenario(key)
        path = script.SCENARIOS / f"{script.name(key)}.json"
        assert json.loads(path.read_text(encoding="utf-8")) == built
        loaded = scenarios_module.load(script.name(key), script.SCENARIOS)
        assert loaded.reform.model_dump(exclude_none=True, mode="json") == built["reform"]
    assert sorted(p.name for p in script.SCENARIOS.glob("*.json")) == sorted(
        f"{script.name(key)}.json" for key in script.MENU)


def test_each_scenario_is_the_study_s_nearest_bundle(script) -> None:
    """Built apart: the knob of each scenario is the study's nearest bundle, under both
    persistences; the IR's is each rate of the barème the report read, times its factor,
    the thresholds unchanged."""
    for key in ("csg", "allegements", "decote"):
        report = _report(script, key)
        knobs = {s["closest"]["knobs"] == report["searches"][0]["closest"]["knobs"]
                 for s in report["searches"]}
        assert knobs == {True}
        assert script.scenario(key)["reform"] == report["searches"][0]["closest"]["knobs"]
    report = _report(script, "ir")
    law = report["hypotheses"]["transformations"][0]["law"]["bareme"]
    factor = report["searches"][0]["closest"]["knobs"]["ir_bareme_echelle"]
    bareme = script.scenario("ir")["reform"]["ir_bareme"]
    assert [b["threshold"] for b in bareme] == [b["threshold"] for b in law]
    assert [b["rate"] for b in bareme] == pytest.approx([b["rate"] * factor for b in law],
                                                        rel=1e-12)


def test_a_nearest_bundle_that_differs_between_persistences_is_refused(script) -> None:
    report = _report(script, "csg")
    report["searches"][1]["closest"]["knobs"] = {"csg_activite_deductible": 0.064}
    with pytest.raises(script.EtudeAnnuelleError, match="pas le même"):
        script.closest(report)


def test_the_command_is_the_study_s_frame_field_for_field(script) -> None:
    """Read back by the command's own parser: each field of the study's committed request
    is the command's, and nothing the request does not name is set."""
    for key in script.MENU:
        request = json.loads((script.REQUESTS / f"{key}.json").read_text(encoding="utf-8"))
        args = cli.build_parser().parse_args(script.argv(key, where="ici"))
        assert (args.scenario, args.dir) == (script.name(key), str(script.SCENARIOS))
        assert (args.reference, args.spending) == ("reconduit", request["spending"]["rule"])
        assert (args.growth_name, args.real, args.prices) == (
            request["growth"]["name"], request["growth"]["real"], request["growth"]["prices"])
        assert (args.rate_name, args.rate_kind) == (request["rate"]["name"],
                                                    request["rate"]["kind"])
        assert (args.horizon, args.theta) == (request["horizon"], request["theta"]["common"])
        assert (args.wage, args.hypothesis_source) == (request["uprating"]["wage"],
                                                       request["uprating"]["source"])
        assert (args.behavioural, args.macro) == (request["behavioural"], request["macro"])
        assert args.persistence is None and args.titre is None
        assert (args.ou, args.out_dir) == ("ici", str(script.OUT))


def test_the_command_reads_each_field_off_the_request_not_off_the_study_s_values(
        script, tmp_path) -> None:
    """The committed requests share their values, so a value written into the launcher
    would pass the test above: a request whose every field differs is read back too."""
    request = json.loads((script.REQUESTS / "csg.json").read_text(encoding="utf-8"))
    request["growth"] = {"name": "Croissance réelle 1,5 %, prix 1,8 %", "real": 0.015,
                         "prices": 0.018}
    request["rate"]["name"] = "Un autre taux tenu"
    request["horizon"], request["theta"] = 7, {"common": 0.25}
    request["uprating"] = {"wage": 0.027, "source": "une autre source"}
    request["spending"] = {"rule": "part_pib_constante"}
    request["behavioural"], request["macro"] = False, True
    (tmp_path / "csg.json").write_text(json.dumps(request), encoding="utf-8")
    args = cli.build_parser().parse_args(script.argv("csg", where="ici", requests=tmp_path))
    assert (args.growth_name, args.real, args.prices) == (
        "Croissance réelle 1,5 %, prix 1,8 %", 0.015, 0.018)
    assert args.rate_name == "Un autre taux tenu" and args.spending == "part_pib_constante"
    assert (args.horizon, args.theta, args.wage) == (7, 0.25, 0.027)
    assert args.hypothesis_source == "une autre source"
    assert (args.behavioural, args.macro) == (False, True)


@pytest.mark.parametrize("how, needle", [
    ("theta_rows", "θ par ligne"),
    ("marche", "un cadre que ce lanceur ne reprend pas"),
    ("base", "un cadre que ce lanceur ne reprend pas"),
    ("persistence", "un cadre que ce lanceur ne reprend pas"),
])
def test_a_frame_the_launcher_does_not_carry_is_refused(script, tmp_path, how: str,
                                                        needle: str) -> None:
    """θ by row, the market rate, a base reform or a persistence named: the command would
    run in another frame than the request's, and the launcher refuses rather than drops."""
    request = json.loads((script.REQUESTS / "csg.json").read_text(encoding="utf-8"))
    if how == "theta_rows":
        request["theta"]["rows"] = {"eti_all": 1.0}
    elif how == "marche":
        request["rate"]["kind"] = "marche"
    elif how == "base":
        request["base"] = {"decote_taux": 0.4}
    else:
        request["persistence"] = "tenu"
    (tmp_path / "csg.json").write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises(script.EtudeAnnuelleError, match=re.escape(needle)):
        script.argv("csg", where="ici", requests=tmp_path)


@pytest.fixture
def launcher(script, monkeypatch, tmp_path):
    out = tmp_path / "etude_annuel"
    monkeypatch.setattr(script, "OUT", out)
    calls: list = []
    monkeypatch.setattr(script.subprocess, "run",
                        lambda command, **kw: calls.append(command)
                        or SimpleNamespace(returncode=0))
    return SimpleNamespace(out=out, calls=calls, monkeypatch=monkeypatch)


def test_the_launcher_runs_the_four_paths_one_after_the_other(script, launcher) -> None:
    """In the study's order (D-237), each into the study's own directory."""
    launcher.monkeypatch.setattr(recherche, "code_state", lambda root=None: ("c0ffee", False))
    assert script.launch("ici") == 0
    assert [c[c.index("predictif") + 1] for c in launcher.calls] == [
        "etude_annuel_csg", "etude_annuel_allegements", "etude_annuel_decote",
        "etude_annuel_ir"]
    assert all(c[c.index("--out-dir") + 1] == str(launcher.out) for c in launcher.calls)


def test_a_path_that_fails_stops_the_ones_after_it(script, launcher, capsys) -> None:
    """A failed path is said, and the paths after it do not run: four reports of which one
    is missing would read as a study whose instrument had nothing to say."""
    launcher.monkeypatch.setattr(recherche, "code_state", lambda root=None: ("c0ffee", False))
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
    """A modified `src/` would let the reports name a commit whose code they did not
    price; a report already there would be overwritten. Both refused before any pass."""
    launcher.monkeypatch.setattr(recherche, "code_state",
                                 lambda root=None: ("c0ffee", how == "dirty"))
    if how == "there":
        launcher.out.mkdir()
        (launcher.out / "predictif_etude_annuel_csg.json").write_text("{}", encoding="utf-8")
    assert script.launch("ici") == 1
    assert launcher.calls == [] and needle in capsys.readouterr().err
