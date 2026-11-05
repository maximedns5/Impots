"""L'étude du PLF 2027 (D-289) : ce qui est chiffré est ce qui a été enregistré.

Les articles sont les trois que le triage dit chiffrables. Leurs scénarios portent les
réformes que les enregistrements ont chiffrées, l'art. 15 borné à 2027 (D-288). La
première année passe par l'appel du simulateur de sa chaîne ; le chemin annuel reprend la
commande de l'étude, champ pour champ, relue par l'analyseur de la commande. Le lanceur
refuse un `src/` modifié ou un rapport déjà là, avant toute passe.

Depuis D-301, l'étude est celle de la commande, `etudes/plf2027.json` lu par
`impots.etude` ; le script ne garde que le scénario de l'art. 15.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from impots import etude, plf_coverage, preregistration
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


@pytest.fixture(scope="module")
def study():
    return etude.definition("plf2027")


def test_the_articles_are_the_ones_the_triage_says_priceable(study) -> None:
    priceable = [a for a in plf_coverage.ARTICLES_2027 if a.bucket == "priceable_now"]
    assert tuple(Path(a.reforme).stem for a in priceable) == study.noms


def test_the_art_15_scenario_is_the_one_committed(script) -> None:
    committed = json.loads((script.SCENARIOS / "plf2027_art_15.json").read_text(
        encoding="utf-8"))
    assert script.art15().to_dict() == committed
    assert committed["annees"] == [committed["year"]] == [2027]


@pytest.mark.parametrize("name", ["plf2027_art_2", "plf2027_art_3", "plf2027_art_15"])
def test_each_scenario_prices_the_reform_its_registration_priced(script, study,
                                                                 name: str) -> None:
    scenario = scenarios_module.load(name, study.scenarios)
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


def test_the_first_year_goes_to_its_chain_s_simulator() -> None:
    kind, endpoint, payload = etude.first_year_payload("plf2027_art_15")
    assert (kind, endpoint, payload["year"]) == ("entreprises", "/entreprises/simulate", 2027)
    for name in ("plf2027_art_2", "plf2027_art_3"):
        kind, endpoint, payload = etude.first_year_payload(name)
        assert (kind, endpoint) == ("menages", "/population/simulate")
        assert payload["behavioural"] is payload["macro"] is True
        assert payload["year"] == 2026


def test_a_scenario_of_both_chains_is_refused(script, tmp_path) -> None:
    both = scenarios_module.Scenario(**{**vars(script.art15()), "annees": (),
                                        "reform": ReformSpec(decote_taux=0.4)})
    both.save(tmp_path)
    with pytest.raises(etude.EtudeError, match="deux appels"):
        etude.first_year_payload("plf2027_art_15", tmp_path)


def test_a_first_year_the_simulator_refuses_is_not_written(tmp_path) -> None:
    empty = scenarios_module.Scenario(name="plf2027_art_2", reform=ReformSpec(), year=2026,
                                      created="2026-10-28", source="vide")
    empty.save(tmp_path)
    with pytest.raises(etude.EtudeError, match="a rendu 422"):
        etude.first_year("plf2027_art_2", where="ici", scenarios=tmp_path)


def _frame(args) -> dict:
    return {k: v for k, v in vars(args).items()
            if k not in ("scenario", "out_dir", "ou", "func")}


def test_the_annual_paths_take_the_study_s_frame_field_for_field(study) -> None:
    annual = _load("etude_annuelle")
    frame = cli.build_parser().parse_args(annual.argv(study.cadre, where="là",
                                                      requests=etude.CADRES))
    for name in study.noms:
        args = cli.build_parser().parse_args(study.annual_argv(name, where="ici"))
        assert args.func is cli.cmd_predictif and args.scenario == name
        assert args.out_dir == str(study.rapports) and args.ou == "ici"
        assert _frame(args) == {**_frame(frame), "dir": str(study.scenarios)}
        assert args.behavioural and args.macro and args.horizon == 10


#: The entry the study names: D-289 at first, D-338 for but 14, D-350 for but 16.
ENTREE = etude.definition("plf2027").preenregistrement
#: What git says of a commit whose entry is in and which a remote branch carries.
GIT = {("show", "HEAD:docs/DECISIONS.md"): f"## D-288 — x\n## {ENTREE} — L'étude\n",
       ("branch", "-r", "--contains", "HEAD"): "  origin/claude/x\n"}


@pytest.fixture
def launcher(study, monkeypatch, tmp_path):
    out = tmp_path / "etude_plf2027"
    calls: list = []
    envs: list = []
    monkeypatch.setattr(etude.subprocess, "run",
                        lambda command, **kw: calls.append(command) or envs.append(kw["env"])
                        or SimpleNamespace(returncode=0))
    monkeypatch.setattr(recherche, "code_state", lambda root=None: ("c0ffee", False))
    git = dict(GIT)
    monkeypatch.setattr(etude, "_git", lambda *args: git[args])
    return SimpleNamespace(out=out, calls=calls, envs=envs, monkeypatch=monkeypatch,
                           study=etude.replace(study, rapports=out), git=git)


def test_the_launcher_runs_the_first_years_then_the_paths(launcher) -> None:
    assert launcher.study.launch("ici") == 0
    steps = [("premiere", c[c.index("premiere") + 2]) if "premiere" in c
             else ("predictif", c[c.index("predictif") + 1]) for c in launcher.calls]
    assert steps == [("premiere", n) for n in launcher.study.noms] + [
        ("predictif", n) for n in launcher.study.noms]
    assert all(c[c.index("--ou") + 1] == "ici" for c in launcher.calls)


def test_every_pass_is_served_the_real_firm_vintage(launcher) -> None:
    assert launcher.study.launch("ici") == 0
    assert {env["IMPOTS_FIRM_VINTAGE"] for env in launcher.envs} == {"2023"}
    registered = preregistration.load("plf2027_art_15").population_vintage
    assert registered == f"entreprises-{launcher.study.millesime_entreprises}"


def test_every_pass_runs_the_simulator_locally(launcher) -> None:
    """The passes call the simulator in their own process, closed without a key since
    D-295: the launcher opens it for them. The suite's conftest opens it for every test,
    so this one closes it first, as a terminal would have it."""
    launcher.monkeypatch.delenv("IMPOTS_AUTH", raising=False)
    assert launcher.study.launch("ici") == 0
    assert {env["IMPOTS_AUTH"] for env in launcher.envs} == {"aucune"}


def test_a_pass_that_fails_stops_the_ones_after_it(launcher, capsys) -> None:
    codes = iter([0, 3, 0, 0, 0, 0])
    launcher.monkeypatch.setattr(etude.subprocess, "run",
                                 lambda command, **kw: launcher.calls.append(command)
                                 or SimpleNamespace(returncode=next(codes)))
    assert launcher.study.launch("ici") == 3
    assert len(launcher.calls) == 2
    assert "les suivants ne tournent pas" in capsys.readouterr().err


@pytest.mark.parametrize("how, needle", [
    ("dirty", "modifications non commitées"),
    ("there", "un rapport n'est pas écrasé en silence"),
    ("unregistered", f"{ENTREE} n'est pas dans docs/DECISIONS.md au commit"),
    ("unpushed", "aucune branche distante ne porte le commit"),
])
def test_the_launcher_refuses_before_any_pass(launcher, capsys, how: str,
                                              needle: str) -> None:
    launcher.monkeypatch.setattr(recherche, "code_state",
                                 lambda root=None: ("c0ffee", how == "dirty"))
    if how == "there":
        launcher.out.mkdir()
        (launcher.out / "premiere_annee_plf2027_art_2.json").write_text("{}",
                                                                         encoding="utf-8")
    if how == "unregistered":
        # The entry's number in another heading's text is not the entry.
        launcher.git[("show", "HEAD:docs/DECISIONS.md")] = f"## D-288 — avant {ENTREE}\n"
    if how == "unpushed":
        launcher.git[("branch", "-r", "--contains", "HEAD")] = ""
    assert launcher.study.launch("ici") == 1
    assert launcher.calls == [] and needle in capsys.readouterr().err


def _report_on(launcher, name: str, commit: str) -> dict:
    launcher.out.mkdir(exist_ok=True)
    report = {"scenario": name, "commit": commit, "dirty": False, "where": "avant"}
    (launcher.out / f"premiere_annee_{name}.json").write_text(json.dumps(report),
                                                              encoding="utf-8")
    return report


def _steps(launcher) -> list:
    return [("premiere", c[c.index("premiere") + 2]) if "premiere" in c
            else ("predictif", c[c.index("predictif") + 1]) for c in launcher.calls]


def test_an_interrupted_series_resumes_after_the_reports_on_its_commit(launcher,
                                                                       capsys) -> None:
    """D-335 : une série arrêtée après sa première année reprend à la deuxième, sur le
    même commit ; le rapport déjà là n'est pas réécrit."""
    first = launcher.study.noms[0]
    _report_on(launcher, first, "c0ffee")
    assert launcher.study.launch("ici") == 0
    assert _steps(launcher) == [("premiere", n) for n in launcher.study.noms[1:]] + [
        ("predictif", n) for n in launcher.study.noms]
    assert f"premiere_annee_{first}.json : déjà là" in capsys.readouterr().out


def test_a_series_resumes_on_a_commit_a_witness_joins_and_not_on_another(launcher,
                                                                          capsys) -> None:
    first = launcher.study.noms[0]
    report = _report_on(launcher, first, "a" * 40)
    assert launcher.study.launch("ici") == 1
    assert launcher.calls == []
    assert "impots etude temoin plf2027" in capsys.readouterr().err
    (launcher.out / etude.TEMOINS).mkdir()
    (launcher.out / etude.TEMOINS / "c0ffee.json").write_text(json.dumps({
        "passe": f"premiere_annee_{first}.json", "reference": "a" * 40, "commit": "c0ffee",
        "identique": True, "where": "là", "computed": "2026-11-04",
        "rapport": {**report, "commit": "c0ffee", "where": "là"}}), encoding="utf-8")
    assert launcher.study.launch("ici") == 0
    assert _steps(launcher)[0] == ("premiere", launcher.study.noms[1])
