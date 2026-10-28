"""L'étude du PLF 2027 (D-289) : ce qui est chiffré est ce qui a été enregistré.

Les articles sont les trois que le triage dit chiffrables. Leurs scénarios portent les
réformes que les enregistrements ont chiffrées, l'art. 15 borné à 2027 (D-288). La
première année passe par l'appel du simulateur de sa chaîne ; le chemin annuel reprend la
commande de l'étude, champ pour champ, relue par l'analyseur de la commande. Le lanceur
refuse un `src/` modifié ou un rapport déjà là, avant toute passe.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from impots import plf_coverage, preregistration
from impots import scenarios as scenarios_module
from impots.api.schemas import ReformSpec
from impots.entreprises.reforms import FirmReformSpec
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
    return _load("etude_plf2027")


def test_the_articles_are_the_ones_the_triage_says_priceable(script) -> None:
    priceable = [a for a in plf_coverage.ARTICLES_2027 if a.bucket == "priceable_now"]
    assert tuple(Path(a.reforme).stem for a in priceable) == script.ARTICLES


def test_the_art_15_scenario_is_the_one_committed(script) -> None:
    committed = json.loads((script.SCENARIOS / "plf2027_art_15.json").read_text(
        encoding="utf-8"))
    assert script.art15().to_dict() == committed
    assert committed["annees"] == [committed["year"]] == [2027]


@pytest.mark.parametrize("name", ["plf2027_art_2", "plf2027_art_3", "plf2027_art_15"])
def test_each_scenario_prices_the_reform_its_registration_priced(script, name: str) -> None:
    scenario = scenarios_module.load(name, script.SCENARIOS)
    case = preregistration.load(name)
    reform = json.loads((script.REFORMS / f"{name}.json").read_text(encoding="utf-8"))
    if case.scenario is None:
        assert case.reform["chaine"] == "entreprises"
        assert scenario.firm_reform == FirmReformSpec.model_validate(case.reform["spec"])
        assert scenario.firm_reform == FirmReformSpec.model_validate(reform)
        assert scenario.year == case.reform["annee"] and scenario.reform.is_empty()
    else:
        assert case.scenario == name and scenario.firm_reform is None
        assert scenario.reform == ReformSpec.model_validate(reform)


def test_the_first_year_goes_to_its_chain_s_simulator(script) -> None:
    kind, endpoint, payload = script.first_year_payload("plf2027_art_15")
    assert (kind, endpoint, payload["year"]) == ("entreprises", "/entreprises/simulate", 2027)
    for name in ("plf2027_art_2", "plf2027_art_3"):
        kind, endpoint, payload = script.first_year_payload(name)
        assert (kind, endpoint) == ("menages", "/population/simulate")
        assert payload["behavioural"] is payload["macro"] is True
        assert payload["year"] == 2026


def test_a_scenario_of_both_chains_is_refused(script, tmp_path) -> None:
    both = scenarios_module.Scenario(**{**vars(script.art15()), "annees": (),
                                        "reform": ReformSpec(decote_taux=0.4)})
    both.save(tmp_path)
    with pytest.raises(script.EtudePlf2027Error, match="deux appels"):
        script.first_year_payload("plf2027_art_15", tmp_path)


def test_a_first_year_the_simulator_refuses_is_not_written(script, tmp_path) -> None:
    empty = scenarios_module.Scenario(name="plf2027_art_2", reform=ReformSpec(), year=2026,
                                      created="2026-10-28", source="vide")
    empty.save(tmp_path)
    with pytest.raises(script.EtudePlf2027Error, match="a rendu 422"):
        script.first_year("plf2027_art_2", where="ici", scenarios=tmp_path)


def _frame(args) -> dict:
    return {k: v for k, v in vars(args).items()
            if k not in ("scenario", "out_dir", "ou", "func")}


def test_the_annual_paths_take_the_study_s_frame_field_for_field(script) -> None:
    annual = _load("etude_annuelle")
    study = cli.build_parser().parse_args(annual.argv(script.FRAME, where="là"))
    for name in script.ARTICLES:
        args = cli.build_parser().parse_args(script.annual_argv(name, where="ici"))
        assert args.func is cli.cmd_predictif and args.scenario == name
        assert args.out_dir == str(script.OUT) and args.ou == "ici"
        assert _frame(args) == {**_frame(study), "dir": str(script.SCENARIOS)}
        assert args.behavioural and args.macro and args.horizon == 10


@pytest.fixture
def launcher(script, monkeypatch, tmp_path):
    out = tmp_path / "etude_plf2027"
    monkeypatch.setattr(script, "OUT", out)
    calls: list = []
    monkeypatch.setattr(script.subprocess, "run",
                        lambda command, **kw: calls.append(command)
                        or SimpleNamespace(returncode=0))
    monkeypatch.setattr(recherche, "code_state", lambda root=None: ("c0ffee", False))
    return SimpleNamespace(out=out, calls=calls, monkeypatch=monkeypatch)


def test_the_launcher_runs_the_first_years_then_the_paths(script, launcher) -> None:
    assert script.launch("ici") == 0
    steps = [("premiere", c[c.index("premiere") + 1]) if "premiere" in c
             else ("predictif", c[c.index("predictif") + 1]) for c in launcher.calls]
    assert steps == [("premiere", n) for n in script.ARTICLES] + [
        ("predictif", n) for n in script.ARTICLES]
    assert all(c[c.index("--ou") + 1] == "ici" for c in launcher.calls)


def test_a_pass_that_fails_stops_the_ones_after_it(script, launcher, capsys) -> None:
    codes = iter([0, 3, 0, 0, 0, 0])
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
        (launcher.out / "premiere_annee_plf2027_art_2.json").write_text("{}",
                                                                         encoding="utf-8")
    assert script.launch("ici") == 1
    assert launcher.calls == [] and needle in capsys.readouterr().err
