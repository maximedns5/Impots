"""PHASE10_SPEC §5 — l'étude préenregistrée, et sa page qui ne doit pas dériver (D-237, D-238).

La garde de D-228, appliquée à l'étude : la page commitée est le rendu des fichiers
commités. Et celles du préenregistrement : chaque rapport a joué la requête commitée sous
`etude/`, à l'identique ; chaque instrument du menu a sa requête et son rapport ; tous
viennent d'un même commit, et disent où leurs passes ont tourné. Sur une étude construite,
sans données : ces refus, la réponse par instrument et par persistance, et les coins qui
font baisser la dette.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from exploration_cases import COMMIT, START
from exploration_cases import exploration_request as _request
from impots.api import main
from impots.api.schemas import ExplorationRequest
from impots.predictif import recherche
from macro_cases import synthetic_macro_store

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "write_predictif_etude.py"
LAW = {"year": 2026, "bareme": [{"threshold": 0.0, "rate": 0.0},
                                {"threshold": 11_600.0, "rate": 0.11},
                                {"threshold": 29_579.0, "rate": 0.30}]}
GRIDS = {"csg_activite_deductible": (0.058, 0.064, 0.003),
         "allegement_general_plafond": (3.2, 3.4, 0.1),
         "decote_taux": (0.30, 0.40, 0.05), "ir_bareme_echelle": (0.94, 0.98, 0.02)}
WHERE = "dans le conteneur de la session, en tâche de fond"


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location("write_predictif_etude", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _price():
    """A pass, stubbed: each bundle 1 Md€ more than the last one priced, 90 % frozen, its
    cost as an income-tax impulse."""
    order: dict[str, int] = {}

    def price(reform, view):
        key = json.dumps(reform.model_dump(exclude_none=True, mode="json"), sort_keys=True)
        cost = 1e9 * (1 + order.setdefault(key, len(order)))
        cost *= 1.0 if view == "vieillie" else 0.9
        return SimpleNamespace(cost=cost, inputs=None, impulse={"impot_sur_le_revenu": cost},
                               uncovered={}, deciles=None)
    return price


def _study(tmp_path: Path, script, **report_overrides) -> tuple[Path, Path]:
    requests, reports = tmp_path / "etude", tmp_path / "reports"
    requests.mkdir()
    reports.mkdir()
    for instrument in script.MENU:
        low, high, step = GRIDS[instrument.knob]
        payload = _request(name=f"etude_{instrument.key}", titre=instrument.label,
                           bounds=[{"knob": instrument.knob, "low": low, "high": high,
                                    "step": step}])
        request = ExplorationRequest.model_validate(payload)
        report = recherche.run(request, price=_price(),
                               hypotheses=main._predictif_hypotheses(request), start=START,
                               macro_store=synthetic_macro_store(), law=LAW, commit=COMMIT,
                               computed="2026-10-21", where=WHERE)
        report.update(report_overrides)
        (requests / f"{instrument.key}.json").write_text(json.dumps(payload),
                                                          encoding="utf-8")
        (reports / f"exploration_etude_{instrument.key}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return requests, reports


# --------------------------------------------------------------------------- #
# the study as committed
# --------------------------------------------------------------------------- #
def test_the_committed_page_is_what_the_script_renders(script) -> None:
    """GUARD (D-228). A page regenerated from the committed reports and requests is the
    committed page, byte for byte: a figure edited by hand, or a report re-run without
    the page, fails here."""
    assert script.OUT.read_text(encoding="utf-8") == script.render(script.load())


def test_the_committed_study_is_preregistered(script) -> None:
    """Every instrument of the menu has its committed request and the report that played
    it, all from one commit, each saying where its passes ran (`load` refuses otherwise),
    and the page names that commit."""
    etudes = script.load()
    assert [e["instrument"].key for e in etudes] == ["csg", "allegements", "decote", "ir"]
    assert etudes[0]["report"]["commit"] in script.OUT.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# a study built here
# --------------------------------------------------------------------------- #
def test_the_page_answers_each_instrument_under_each_persistence(script, tmp_path) -> None:
    etudes = script.load(*_study(tmp_path, script))
    page = script.render(etudes)
    for entry in etudes:
        assert f"### {entry['instrument'].label}" in page
        for search in entry["report"]["searches"]:
            assert script.verdict(search, entry["instrument"], 0.0) in page
    assert "Effet macro éteint après trois ans" in page
    assert "Effet macro tenu au niveau de la troisième année" in page
    assert "Elle ne recommande rien" in page and "Ce n'est pas une prévision" in page
    assert "L'IS n'y entre pas" in page
    assert WHERE in page and COMMIT in page


@pytest.mark.parametrize("how, needle", [
    ("retouchee", "n'a pas joué la requête commitée"),
    ("sans_rapport", "sans rapport"),
    ("sans_requete", "sans requête"),
    ("autre_bouton", "parcourt"),
])
def test_a_study_that_is_not_what_was_preregistered_is_refused(script, tmp_path, how: str,
                                                               needle: str) -> None:
    """A request touched after its passes, an instrument dropped from the reports or from
    the menu, a request over another knob than its instrument's: each would read as the
    preregistered study, and is refused."""
    requests, reports = _study(tmp_path, script)
    if how == "retouchee":
        payload = json.loads((requests / "csg.json").read_text(encoding="utf-8"))
        payload["bounds"][0]["step"] = 0.002
        (requests / "csg.json").write_text(json.dumps(payload), encoding="utf-8")
    elif how == "sans_rapport":
        (reports / "exploration_etude_decote.json").unlink()
    elif how == "sans_requete":
        (requests / "ir.json").unlink()
    else:
        for path in (requests / "csg.json", requests / "decote.json"):
            path.rename(path.with_suffix(".tmp"))
        (requests / "csg.tmp").rename(requests / "decote.json")
        (requests / "decote.tmp").rename(requests / "csg.json")
        for name in ("csg", "decote"):
            path = reports / f"exploration_etude_{name}.json"
            path.rename(path.with_suffix(".tmp"))
        (reports / "exploration_etude_csg.tmp").rename(
            reports / "exploration_etude_decote.json")
        (reports / "exploration_etude_decote.tmp").rename(
            reports / "exploration_etude_csg.json")
    with pytest.raises(script.EtudeError, match=needle):
        script.load(requests, reports)


@pytest.mark.parametrize("overrides, needle", [
    ({"where": None}, "ne dit pas où"),
    ({"where": "  "}, "ne dit pas où"),
])
def test_a_report_that_does_not_say_where_it_ran_is_refused(script, tmp_path,
                                                            overrides: dict,
                                                            needle: str) -> None:
    with pytest.raises(script.EtudeError, match=needle):
        script.load(*_study(tmp_path, script, **overrides))


def test_reports_of_two_commits_are_refused(script, tmp_path) -> None:
    requests, reports = _study(tmp_path, script)
    path = reports / "exploration_etude_ir.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["commit"] = "f" * 40
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(script.EtudeError, match="2 commits"):
        script.load(requests, reports)


def test_falling_names_what_every_falling_corner_shares(script) -> None:
    """« Pour quels θ » : the corners where Δb meets the target, and the θ settings all of
    them share; none when no corner lowers the debt."""
    evaluation = {"corners": [["a = 0, multiplicateur_macro = 0", 0.01],
                              ["a = 0, multiplicateur_macro = 1", -0.002],
                              ["a = 1, multiplicateur_macro = 0", 0.008],
                              ["a = 1, multiplicateur_macro = 1", -0.001]]}
    assert script.falling(evaluation, 0.0) == (2, {("multiplicateur_macro", "1")})
    assert script.falling(evaluation, -0.01) == (0, set())
    assert script.falling(evaluation, 0.02) == (4, set())


def test_a_loop_the_chain_lacks_is_said_absent_on_the_page(script, tmp_path) -> None:
    """D-238: Mésange prints no balance row for the targeted employer-contribution variant,
    so the loop is ABSENT for the allègements, not zero. The page says so where it
    answers, and lists the reason; the closed channels ride with theirs."""
    requests, reports = _study(tmp_path, script)
    path = reports / "exploration_etude_allegements.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    reason = ("aucun instrument de cette réforme n'a de ligne de solde dans Mésange : il "
              "n'y a pas de rétroaction à lire")
    for search in report["searches"]:
        search["indices"]["absent"] = {"rétroaction": reason}
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    etudes = script.load(requests, reports)
    page = script.render(etudes)
    entry = next(e for e in etudes if e["instrument"].key == "allegements")
    for search in entry["report"]["searches"]:
        assert "la boucle PIB → recettes est absente" in script.verdict(
            search, entry["instrument"], 0.0)
    assert reason in page
    for name, why in etudes[0]["report"]["searches"][0]["indices"]["closed"].items():
        assert f"{name} : {why}" in page


def _first_round(reports: Path, *, move: str | None = None) -> None:
    """The first round as it ran: on the preregistration's commit, without what the
    chain lacks; `move` shifts one figure of that instrument's report."""
    first = reports / "etude_premier_tour"
    first.mkdir()
    for path in reports.glob("exploration_etude_*.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        report["commit"] = "a" * 40
        for search in report["searches"]:
            search["indices"].pop("absent")
            search["indices"].pop("closed")
        if move and path.name == f"exploration_etude_{move}.json":
            report["searches"][1]["evaluations"][-1]["delta_aged"] += 1e-9
        (first / path.name).write_text(json.dumps(report, ensure_ascii=False),
                                       encoding="utf-8")


def test_the_first_round_is_named_and_given_back_figure_for_figure(script,
                                                                    tmp_path) -> None:
    requests, reports = _study(tmp_path, script)
    _first_round(reports)
    page = script.render(script.load(requests, reports))
    assert "a" * 40 in page and "chiffre pour chiffre" in page


@pytest.mark.parametrize("how, needle", [("moved", "ne redonne pas le premier"),
                                         ("missing", "premier tour sans")])
def test_a_second_round_that_is_not_the_first_is_refused(script, tmp_path, how: str,
                                                         needle: str) -> None:
    """D-238: the second round only adds what the chain lacks. One figure moved by a
    billionth of a point, or an instrument missing from the first round, and the rerun is
    no longer a field added: refused."""
    requests, reports = _study(tmp_path, script)
    _first_round(reports, move="decote" if how == "moved" else None)
    if how == "missing":
        (reports / "etude_premier_tour" / "exploration_etude_ir.json").unlink()
    with pytest.raises(script.EtudeError, match=needle):
        script.load(requests, reports)


def test_a_loop_that_misses_only_some_instruments_is_not_said_absent(script,
                                                                     tmp_path) -> None:
    """The CSG's loop runs; only the benefits it moves have no Mésange variant. The page
    lists those, grouped by their one reason, and does not call the loop absent."""
    requests, reports = _study(tmp_path, script)
    path = reports / "exploration_etude_csg.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    why = "Mésange ne publie pas de variante de transfert : un canal qui meurt."
    for search in report["searches"]:
        search["indices"]["absent"] = {
            "rétroaction, instruments non couverts": f"af : {why} ; ppa : {why} ; rsa : {why}"}
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    etudes = script.load(requests, reports)
    page = script.render(etudes)
    entry = next(e for e in etudes if e["instrument"].key == "csg")
    for search in entry["report"]["searches"]:
        assert "est absente" not in script.verdict(search, entry["instrument"], 0.0)
    assert f"af, ppa, rsa : {why}" in page and page.count(why) == 1


def test_the_answer_says_for_which_theta_the_debt_falls(script, tmp_path) -> None:
    """The question's second half, in the answer itself: under « tenu », the corners where
    the debt falls, with the θ they all share; under « éteint », none."""
    etudes = script.load(*_study(tmp_path, script))
    eteint, tenu = etudes[0]["report"]["searches"]
    instrument = etudes[0]["instrument"]
    assert "ne baisse à aucun coin" in script.verdict(eteint, instrument, 0.0)
    said = script.verdict(tenu, instrument, 0.0)
    assert "à chaque paquet" in said and "multiplicateur_macro = 1" in said
