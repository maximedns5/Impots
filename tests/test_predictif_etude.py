"""PHASE10_SPEC §5 — l'étude préenregistrée, et sa page qui ne doit pas dériver (D-237, D-238).

La garde de D-228, appliquée à l'étude : la page commitée est le rendu des fichiers
commités. Et celles du préenregistrement : chaque rapport a joué la requête commitée sous
`etude/`, à l'identique ; chaque instrument du menu a sa requête et son rapport ; tous
viennent d'un même commit, et disent où leurs passes ont tourné. Sur une étude construite,
sans données : ces refus, la réponse par instrument et par persistance, et les coins qui
font baisser la dette. La courbe de 2026, rejouée à part (D-241, D-242), a les siens, et
la réponse à θ = 0 et à θ = 1, lue aux coins de la boîte (D-274), aussi.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from exploration_cases import COMMIT, START
from exploration_cases import exploration_request as _request
from impots import service
from impots.api.schemas import ExplorationRequest, ReformSpec
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
                               hypotheses=service.predictif_hypotheses(request), start=START,
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
    assert script.OUT.read_text(encoding="utf-8") == script.render(*script.study())


def _shows_c2(report: dict) -> bool:
    return any(row["key"] == "emploi_smic" and row["available"]
               for search in report.get("searches", [])
               for row in (search.get("indices") or {}).get("rows", []))


def test_every_c2_figure_counted_before_d255_says_so(script) -> None:
    """D-255, D-269. Every committed report that shows C2's jobs and ran before C2's fix
    is named among the commits whose figure the page marks; each named commit is one of
    them, so a mistyped hash cannot silence the note. The fix came twice: D-255 on main,
    and before it the replays of D-259 to D-262, run with it on 2026-10-25. Those replays
    are the rounds the page renders, so a report ran before the fix exactly when it is
    not one of them; and no C2 figure on the committed page carries the note, every one
    being a replay's. The reconciled replay of D-271 is one of them since D-272."""
    etudes = script.load()
    courbe = script.load_courbe(etudes)
    rendered = ({e["report"]["commit"] for e in etudes}
                | {e["report"]["commit"] for e in courbe}
                | {c["report"]["commit"] for c in script.load_complements(etudes)}
                | {script.load_autofinancement(courbe, replay)["report"]["commit"]
                   for replay in (*script.AUTOFINANCEMENT_MENU, *script.MESURE_MENU)})
    shown = {r["commit"] for r in (json.loads(p.read_text(encoding="utf-8"))
                                   for p in script.REPORTS.rglob("exploration_*.json"))
             if _shows_c2(r)}
    before = shown - rendered
    assert before and before == script.C2_BEFORE_D255
    figures = [line for line in script.OUT.read_text(encoding="utf-8").splitlines()
               if "| Emploi au voisinage du SMIC |" in line and "| absent :" not in line]
    assert figures and not any(script.C2_NOTE in line for line in figures)


@pytest.mark.parametrize("before", [True, False])
def test_the_c2_note_follows_the_commit_of_the_pass(script, before: bool) -> None:
    """The note is the pass's, not the page's: a report run after the fix shows C2's
    figure as it is. And it is C2's: Mésange's jobs, beside it, never carry it."""
    instrument = next(i for i in script.MENU if i.key == "allegements")
    row = {"key": "emploi_smic", "pour": "Les gens", "label": "Emploi au voisinage du SMIC",
           "unit": "emplois", "stage": "comportement", "available": True,
           "values": {"2026": 227.0}, "box": {"2026": [170.0, 270.0]}}
    other = {**row, "key": "emploi_marchand", "label": "Emploi salarié marchand",
             "stage": "macro", "values": {"1": 5.8}, "box": None}
    commit = min(script.C2_BEFORE_D255) if before else "f" * 40
    report = {"commit": commit, "searches": [
        {"indices": {"knobs": {instrument.knob: 3.5}, "rows": [row, other]}}]}
    lines = script._indices({"instrument": instrument, "report": report}, 2035)
    line = next(line for line in lines if "Emploi au voisinage du SMIC" in line)
    assert "+227" in line
    assert (script.C2_NOTE in line) is before
    assert not any(script.C2_NOTE in line for line in lines
                   if "Emploi salarié marchand" in line)


def test_the_committed_study_is_preregistered(script) -> None:
    """Every instrument of the menu has its committed request and the report that played
    it, all from one commit, each saying where its passes ran (`load` refuses otherwise),
    and the page names that commit."""
    etudes = script.load()
    assert [e["instrument"].key for e in etudes] == ["csg", "allegements", "decote", "ir"]
    assert etudes[0]["report"]["commit"] in script.OUT.read_text(encoding="utf-8")
    courbe = script.load_courbe(etudes)
    assert [e["instrument"].key for e in courbe] == ["t_min", "t_delta"]
    assert courbe[0]["report"]["commit"] in script.OUT.read_text(encoding="utf-8")
    # D-251: the wider menu, its four controls each giving its reference back.
    phase11 = script.load_phase11(etudes, script.load_complements(etudes))
    assert [e["instrument"].key for e in phase11["entries"]] == ["is", "pfu"]
    assert phase11["entries"][0]["report"]["commit"] in script.OUT.read_text(
        encoding="utf-8")
    assert all(c["gaps"]["given_back"] for c in phase11["controls"])
    # D-253: the PFU replayed with the wage shift, giving the menu back at no shift.
    salaires = script.load_salaires(phase11)
    assert salaires["control"]["given_back"]
    assert salaires["report"]["commit"] in script.OUT.read_text(encoding="utf-8")
    # D-265, D-267: the curve's knobs replayed with C11, giving it back at full weight.
    for replay in script.AUTOFINANCEMENT_MENU:
        auto = script.load_autofinancement(courbe, replay)
        assert auto["control"]["given_back"]
        assert auto["report"]["commit"] in script.OUT.read_text(encoding="utf-8")


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


def _complement(requests: Path, reports: Path, script, **request_overrides) -> Path:
    """The ceiling replayed after the result, its shock under the uniform variant: the
    preregistered request, renamed, and its report."""
    payload = json.loads((requests / "allegements.json").read_text(encoding="utf-8"))
    payload.update(name="complement_allegements", titre="Le plafond, variante uniforme",
                   question="Le plafond reclassé (D-239) fait-il baisser la dette ?",
                   **request_overrides)
    request = ExplorationRequest.model_validate(payload)
    report = recherche.run(request, price=_price(),
                           hypotheses=service.predictif_hypotheses(request), start=START,
                           macro_store=synthetic_macro_store(), law=LAW,
                           commit="b" * 40, computed="2026-10-21", where=WHERE)
    (requests / "complements").mkdir(exist_ok=True)
    (requests / "complements" / "allegements.json").write_text(json.dumps(payload),
                                                               encoding="utf-8")
    path = reports / "exploration_complement_allegements.json"
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    return path


def test_a_complement_is_rendered_apart_and_said_unregistered(script, tmp_path) -> None:
    """D-239: the ceiling replayed after the result is on the page, apart from the study,
    said to be outside the preregistration, with its own commit."""
    requests, reports = _study(tmp_path, script)
    _complement(requests, reports, script)
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    assert courbe == [] and phase11 is None
    page = script.render(etudes, complements)
    assert [c["instrument"].key for c in complements] == ["allegements"]
    head, _, tail = page.partition("## Complément, hors préenregistrement")
    assert tail and "b" * 40 in tail and "b" * 40 not in head
    assert "Le plafond reclassé (D-239)" in tail


@pytest.mark.parametrize("how, needle", [
    ("grid", "ne rejoue pas la requête préenregistrée"),
    ("cost", "les coûts diffèrent"),
    ("report", "complément sans rapport"),
    ("request", "n'a pas joué sa requête"),
])
def test_a_complement_that_is_not_a_like_for_like_replay_is_refused(script, tmp_path,
                                                                    how: str,
                                                                    needle: str) -> None:
    """Only the shock's classing may change: another grid, a bundle costed otherwise, a
    complement without its report or whose report played another request would no longer
    say what moved, and are refused."""
    requests, reports = _study(tmp_path, script)
    if how == "grid":
        _complement(requests, reports, script,
                    bounds=[{"knob": "allegement_general_plafond", "low": 3.2,
                             "high": 3.4, "step": 0.2}])
    else:
        path = _complement(requests, reports, script)
        report = json.loads(path.read_text(encoding="utf-8"))
        if how == "cost":
            report["searches"][0]["evaluations"][-1]["cost_aged_eur"] += 1.0
            path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        elif how == "report":
            path.unlink()
        else:
            payload = json.loads((requests / "complements" / "allegements.json")
                                 .read_text(encoding="utf-8"))
            payload["question"] = "Une autre question ?"
            (requests / "complements" / "allegements.json").write_text(
                json.dumps(payload), encoding="utf-8")
    with pytest.raises(script.EtudeError, match=needle):
        script.study(requests, reports)


#: Two bundles per knob of the curve, enough to read an answer (D-241).
CURVE_GRIDS = {"allegement_general_t_min": (0.021, 0.024, 0.003),
               "allegement_general_t_delta_moins_de_50": (0.3831, 0.3931, 0.01)}
CURVE_COMMIT = "c" * 40


def _courbe(requests: Path, reports: Path, script, *, key: str | None = None,
            **request_overrides) -> None:
    """The 2026 curve replayed on the study's frame (D-241): for each knob, the allègement
    request with its name, title, question and grid changed, and the report that played
    it; `key`'s request also takes `request_overrides`."""
    frame = json.loads((requests / "allegements.json").read_text(encoding="utf-8"))
    (requests / "courbe").mkdir()
    for instrument in script.COURBE_MENU:
        low, high, step = CURVE_GRIDS[instrument.knob]
        payload = {**frame, "name": f"courbe_{instrument.key}", "titre": instrument.label,
                   "question": f"Le {instrument.key} fait-il baisser la dette ?",
                   "bounds": [{"knob": instrument.knob, "low": low, "high": high,
                               "step": step}]}
        if instrument.key == key:
            payload.update(request_overrides)
        request = ExplorationRequest.model_validate(payload)
        report = recherche.run(request, price=_price(),
                               hypotheses=service.predictif_hypotheses(request), start=START,
                               macro_store=synthetic_macro_store(), law=LAW,
                               commit=CURVE_COMMIT, computed="2026-10-23", where=WHERE)
        (requests / "courbe" / f"{instrument.key}.json").write_text(json.dumps(payload),
                                                                    encoding="utf-8")
        (reports / f"exploration_courbe_{instrument.key}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")


def test_the_curve_is_rendered_apart_and_said_preregistered(script, tmp_path) -> None:
    """D-241: the curve's knobs replayed after the study are on the page in their own
    section, said preregistered apart, with their own commit, each answered under each
    persistence, and the firm size the population lacks said."""
    requests, reports = _study(tmp_path, script)
    _courbe(requests, reports, script)
    etudes, complements, courbe, _ = script.study(requests, reports)
    page = script.render(etudes, complements, courbe)
    assert [e["instrument"].key for e in courbe] == ["t_min", "t_delta"]
    head, _, tail = page.partition("## La courbe de 2026, préenregistrée à part")
    assert tail and CURVE_COMMIT in tail and CURVE_COMMIT not in head
    assert "D-241" in tail and "moins de 50" in tail
    assert "## Ce que l'étude ne dit pas" in tail
    for entry in courbe:
        assert f"### {entry['instrument'].label}" in tail
        assert f"`{entry['instrument'].knob}`" in tail
        for search in entry["report"]["searches"]:
            assert script.verdict(search, entry["instrument"], 0.0) in tail


#: Each way a curve could read as replayed in the study's frame without being so.
CURVE_REFUSALS = [
    ("cadre", "ne tient pas le cadre de l'étude"),
    ("bouton", "parcourt"),
    ("sans_rapport", "de la courbe sans rapport"),
    ("sans_requete", "de la courbe sans requête"),
    ("retouchee", "n'a pas joué sa requête"),
    ("ou", "ne dit pas où"),
    ("commits", "de 2 commits"),
    ("hors_menu", "hors du menu de la courbe"),
]


@pytest.mark.parametrize("how, needle", CURVE_REFUSALS,
                         ids=[how for how, _ in CURVE_REFUSALS])
def test_a_curve_that_is_not_what_was_preregistered_is_refused(script, tmp_path, how: str,
                                                               needle: str) -> None:
    """Another θ than the study's, a request over another knob than its own, a knob
    without its report or its request, a request touched after its passes, a report
    silent on where it ran, reports of two commits, a request the page would not render:
    each would read as the curve replayed in the study's frame, and is refused."""
    requests, reports = _study(tmp_path, script)
    if how == "cadre":
        _courbe(requests, reports, script, key="t_min", theta={"common": 0.25})
    elif how == "bouton":
        _courbe(requests, reports, script, key="t_min", bounds=[
            {"knob": "allegement_general_t_delta_moins_de_50", "low": 0.3831,
             "high": 0.3931, "step": 0.01}])
    else:
        _courbe(requests, reports, script)
    curve_report = reports / "exploration_courbe_t_delta.json"
    if how == "sans_rapport":
        curve_report.unlink()
    elif how == "sans_requete":
        (requests / "courbe" / "t_delta.json").unlink()
    elif how == "retouchee":
        path = requests / "courbe" / "t_delta.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["bounds"][0]["step"] = 0.005
        path.write_text(json.dumps(payload), encoding="utf-8")
    elif how in ("ou", "commits"):
        report = json.loads(curve_report.read_text(encoding="utf-8"))
        report.update({"where": " "} if how == "ou" else {"commit": "d" * 40})
        curve_report.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    elif how == "hors_menu":
        (requests / "courbe" / "puissance.json").write_text(
            (requests / "courbe" / "t_min.json").read_text(encoding="utf-8"),
            encoding="utf-8")
    with pytest.raises(script.EtudeError, match=needle):
        script.study(requests, reports)


def _courbe_first_round(reports: Path, *, move: str | None = None) -> None:
    """The curve's first round as it ran: on the preregistration's commit, with the C2 that
    read 15 % of the earners (D-259), here its indices changed; `move` shifts one figure of
    that knob's report."""
    first = reports / "courbe_premier_tour"
    first.mkdir()
    for path in reports.glob("exploration_courbe_*.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        report["commit"] = "e" * 40
        for search in report["searches"]:
            search["indices"].pop("absent", None)
            search["indices"].pop("closed", None)
        if move and path.name == f"exploration_courbe_{move}.json":
            report["searches"][0]["evaluations"][-1]["delta_aged"] += 1e-9
        (first / path.name).write_text(json.dumps(report, ensure_ascii=False),
                                       encoding="utf-8")


def test_the_curve_s_first_round_is_named_and_given_back_figure_for_figure(
        script, tmp_path) -> None:
    """D-261: the curve replayed after C2's fix. Its indices may differ from the first
    round's, which is the point; its costs, its Δb and its corners may not, and the page
    names the first commit and why it was replayed."""
    requests, reports = _study(tmp_path, script)
    _courbe(requests, reports, script)
    _courbe_first_round(reports)
    etudes, complements, courbe, _ = script.study(requests, reports)
    page = script.render(etudes, complements, courbe)
    _, _, tail = page.partition("## La courbe de 2026, préenregistrée à part")
    assert "e" * 40 in tail and CURVE_COMMIT in tail
    assert "chiffre pour chiffre" in tail and "D-259" in tail
    assert "courbe_premier_tour" in tail


@pytest.mark.parametrize("how, needle", [("moved", "ne redonne pas le premier"),
                                         ("missing", "premier tour de la courbe sans")])
def test_a_curve_rerun_that_moves_a_figure_is_refused(script, tmp_path, how: str,
                                                      needle: str) -> None:
    """D-261: the rerun only corrects C2, which enters no revenue and no debt. One figure
    moved by a billionth of a point, or a knob missing from the first round, and the
    rerun is no longer that: refused."""
    requests, reports = _study(tmp_path, script)
    _courbe(requests, reports, script)
    _courbe_first_round(reports, move="t_min" if how == "moved" else None)
    if how == "missing":
        (reports / "courbe_premier_tour" / "exploration_courbe_t_delta.json").unlink()
    with pytest.raises(script.EtudeError, match=needle):
        script.study(requests, reports)


def _second_round(reports: Path, *, move: str | None = None) -> None:
    """The study's second round as it ran: with the C2 that read 15 % of the earners
    (D-259), here its indices changed; `move` shifts one figure of that instrument's
    report."""
    second = reports / "etude_second_tour"
    second.mkdir()
    for path in reports.glob("exploration_etude_*.json"):
        report = json.loads(path.read_text(encoding="utf-8"))
        report["commit"] = "f" * 40
        for search in report["searches"]:
            search["indices"].pop("closed", None)
        if move and path.name == f"exploration_etude_{move}.json":
            report["searches"][1]["evaluations"][-1]["delta_aged"] += 1e-9
        (second / path.name).write_text(json.dumps(report, ensure_ascii=False),
                                        encoding="utf-8")


def test_the_second_round_is_named_and_given_back_figure_for_figure(script,
                                                                     tmp_path) -> None:
    """D-261: the study replayed on its second round's code with C2's fix alone. Its
    indices may differ from the second round's, which is the point; its costs, its Δb and
    its corners may not, and the page names the second commit and why it was replayed."""
    requests, reports = _study(tmp_path, script)
    _first_round(reports)
    _second_round(reports)
    page = script.render(script.load(requests, reports))
    head, _, _ = page.partition("## Le cadre")
    assert "f" * 40 in head and "a" * 40 in head and COMMIT in head
    assert "D-259" in head and "etude_second_tour" in head
    assert head.count("chiffre pour chiffre") == 2


@pytest.mark.parametrize("how, needle", [("moved", "ne redonne pas le second"),
                                         ("missing", "second tour sans")])
def test_a_third_round_that_is_not_the_second_is_refused(script, tmp_path, how: str,
                                                         needle: str) -> None:
    """D-261: the third round only corrects C2, which enters no revenue and no debt. One
    figure moved by a billionth of a point, or an instrument missing from the second
    round, and the replay is no longer that: refused."""
    requests, reports = _study(tmp_path, script)
    _second_round(reports, move="decote" if how == "moved" else None)
    if how == "missing":
        (reports / "etude_second_tour" / "exploration_etude_ir.json").unlink()
    with pytest.raises(script.EtudeError, match=needle):
        script.load(requests, reports)


def _complement_first_round(reports: Path, *, move: bool = False) -> None:
    """The complement's first round as it ran: with the C2 that D-259 and D-261 corrected,
    here its indices changed; `move` shifts one of its figures."""
    first = reports / "complements_premier_tour"
    first.mkdir()
    path = reports / "exploration_complement_allegements.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["commit"] = "9" * 40
    for search in report["searches"]:
        search["indices"].pop("closed", None)
    if move:
        report["searches"][1]["evaluations"][-1]["delta_aged"] += 1e-9
    (first / path.name).write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")


def test_the_complement_s_first_round_is_named_and_given_back_figure_for_figure(
        script, tmp_path) -> None:
    """D-262: the complement replayed on its own commit with C2's fixes alone. Its indices
    may differ from the first round's; its costs, its Δb and its corners may not, and the
    page names the first commit and why it was replayed."""
    requests, reports = _study(tmp_path, script)
    _complement(requests, reports, script)
    _complement_first_round(reports)
    etudes, complements, _, _ = script.study(requests, reports)
    page = script.render(etudes, complements)
    _, _, tail = page.partition("## Complément, hors préenregistrement")
    assert "9" * 40 in tail and "b" * 40 in tail
    assert "chiffre pour chiffre" in tail and "D-259" in tail
    assert "complements_premier_tour" in tail


@pytest.mark.parametrize("how, needle", [("moved", "ne redonne pas le premier"),
                                         ("missing", "premier tour des compléments sans")])
def test_a_complement_rerun_that_moves_a_figure_is_refused(script, tmp_path, how: str,
                                                           needle: str) -> None:
    """D-262: the rerun only corrects C2, which enters no revenue and no debt. One figure
    moved by a billionth of a point, or the complement missing from its first round, and
    the rerun is no longer that: refused."""
    requests, reports = _study(tmp_path, script)
    _complement(requests, reports, script)
    _complement_first_round(reports, move=how == "moved")
    if how == "missing":
        (reports / "complements_premier_tour"
         / "exploration_complement_allegements.json").unlink()


# --------------------------------------------------------------------------- #
# the wider menu of Phase 11, preregistered apart (D-250, D-251)
# --------------------------------------------------------------------------- #
#: Two bundles per instrument of the wider menu, enough to read an answer.
PHASE11_GRIDS = {"is_taux_normal": (0.24, 0.245, 0.005), "pfu_taux": (0.108, 0.118, 0.01)}
PHASE11_COMMIT = "e" * 40


def _price_with_firms():
    """`_price`, which also takes the firm part a search over a firm knob hands it."""
    inner = _price()

    def price(reform, view, firm=None):
        if firm is None:
            return inner(reform, view)
        return inner(reform.model_copy(update={"decote_taux": firm.is_taux_normal}), view)
    return price


def _phase11(requests: Path, reports: Path, script, *, key: str | None = None,
             **request_overrides) -> None:
    """The wider menu on the study's frame: for each instrument, the study's IR request
    with its name, title, question and grid changed, and the report that played it; then
    the study's four reports replayed as controls, on the same commit. `key`'s request
    also takes `request_overrides`."""
    frame = json.loads((requests / "ir.json").read_text(encoding="utf-8"))
    (requests / "phase11").mkdir()
    for instrument in script.PHASE11_MENU:
        low, high, step = PHASE11_GRIDS[instrument.knob]
        payload = {**frame, "name": f"phase11_{instrument.key}", "titre": instrument.label,
                   "question": f"Le {instrument.key} fait-il baisser la dette ?",
                   "bounds": [{"knob": instrument.knob, "low": low, "high": high,
                               "step": step}]}
        if instrument.key == key:
            payload.update(request_overrides)
        request = ExplorationRequest.model_validate(payload)
        report = recherche.run(request, price=_price_with_firms(),
                               hypotheses=service.predictif_hypotheses(request), start=START,
                               macro_store=synthetic_macro_store(), law=LAW,
                               commit=PHASE11_COMMIT, computed="2026-10-25", where=WHERE)
        (requests / "phase11" / f"{instrument.key}.json").write_text(json.dumps(payload),
                                                                     encoding="utf-8")
        (reports / f"exploration_phase11_{instrument.key}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")
    controls = reports / script.CONTROLS
    controls.mkdir(parents=True)
    for instrument in script.MENU:
        name = f"exploration_etude_{instrument.key}.json"
        report = json.loads((reports / name).read_text(encoding="utf-8"))
        report.update(commit=PHASE11_COMMIT, computed="2026-10-25")
        (controls / name).write_text(json.dumps(report, ensure_ascii=False),
                                     encoding="utf-8")


def test_the_wider_menu_is_rendered_apart_with_its_controls(script, tmp_path) -> None:
    """D-250: the IS and the PFU are on the page in their own section, said preregistered
    apart, with their own commit, each answered under each persistence with what its
    figure leaves out; the study's four requests replayed beside them give it back."""
    requests, reports = _study(tmp_path, script)
    _phase11(requests, reports, script)
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    page = script.render(etudes, complements, courbe, phase11)
    head, _, tail = page.partition("## Le menu élargi de la phase 11, préenregistré à part")
    assert tail and PHASE11_COMMIT in tail and PHASE11_COMMIT not in head
    assert "D-250" in tail and "La CVAE" in tail and "`t_delta`" in tail
    for entry in phase11["entries"]:
        assert f"### {entry['instrument'].label}" in tail
        assert f"`{entry['instrument'].knob}`" in tail
        for search in entry["report"]["searches"]:
            assert script.verdict(search, entry["instrument"], 0.0) in tail
    assert tail.count("**Ce que ce chiffre ne compte pas.**") == 2
    assert "0,31 €" in tail and "CEBGE" in tail
    assert [c["instrument"].key for c in phase11["controls"]] == [
        "csg", "allegements", "decote", "ir"]
    assert all(c["gaps"]["given_back"] and c["against"] == "D-238"
               for c in phase11["controls"])
    assert tail.count("| la redonne |") == 4
    assert "Dans l'étude de D-237, ni l'IS" in tail


def test_a_control_that_does_not_give_its_reference_back_is_said_so(script,
                                                                     tmp_path) -> None:
    """D-250: a control off by more than a ten-thousandth of a point is a result, not a
    refusal. The page says it does not give its reference back, and by how much."""
    requests, reports = _study(tmp_path, script)
    _phase11(requests, reports, script)
    path = reports / script.CONTROLS / "exploration_etude_decote.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    search = report["searches"][0]
    other = next(e for e in search["evaluations"]
                 if e["knobs"] != search["indices"]["knobs"])
    other["delta_frozen"] += 3e-6
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    control = next(c for c in phase11["controls"] if c["instrument"].key == "decote")
    assert control["gaps"]["share"] == pytest.approx(3e-6)
    assert not control["gaps"]["given_back"] and control["gaps"]["same_verdicts"]
    page = script.render(etudes, complements, courbe, phase11)
    assert page.count("| la redonne |") == 3 and "| ne la redonne pas |" in page


def test_the_reclassified_instrument_is_controlled_against_its_complement(script,
                                                                          tmp_path) -> None:
    """D-239 reclassified the ceiling after the study: its control is read against the
    complement that replayed it, not against the study."""
    requests, reports = _study(tmp_path, script)
    _complement(requests, reports, script)
    _phase11(requests, reports, script)
    _, _, _, phase11 = script.study(requests, reports)
    against = {c["instrument"].key: c["against"] for c in phase11["controls"]}
    assert against == {"csg": "D-238", "allegements": "D-239", "decote": "D-238",
                       "ir": "D-238"}
    # The complement moved a figure the study had: a control that gives the study back
    # does not give the complement back, and is read against the latter.
    path = reports / "exploration_complement_allegements.json"
    complement = json.loads(path.read_text(encoding="utf-8"))
    search = complement["searches"][0]
    other = next(e for e in search["evaluations"]
                 if e["knobs"] != search["indices"]["knobs"])
    other["delta_frozen"] += 5e-6
    path.write_text(json.dumps(complement, ensure_ascii=False), encoding="utf-8")
    _, _, _, phase11 = script.study(requests, reports)
    ceiling = next(c for c in phase11["controls"] if c["instrument"].key == "allegements")
    assert ceiling["gaps"]["share"] == pytest.approx(5e-6)
    assert not ceiling["gaps"]["given_back"]


#: Each way the wider menu could read as preregistered in the study's frame without being so.
PHASE11_REFUSALS = [
    ("cadre", "ne tient pas le cadre de l'étude"),
    ("bouton", "parcourt"),
    ("sans_rapport", "de la phase 11 sans rapport"),
    ("sans_requete", "de la phase 11 sans requête"),
    ("retouchee", "n'a pas joué sa requête"),
    ("ou", "ne dit pas où"),
    ("commits", "de 2 commits"),
    ("hors_menu", "hors du menu de la phase 11"),
    ("controle_sans_rapport", "contrôle « ir » sans rapport"),
    ("controle_autre_requete", "n'a pas joué sa requête, etude/csg.json"),
    ("controle_commit", "de 2 commits"),
]


@pytest.mark.parametrize("how, needle", PHASE11_REFUSALS,
                         ids=[how for how, _ in PHASE11_REFUSALS])
def test_a_wider_menu_that_is_not_what_was_preregistered_is_refused(script, tmp_path,
                                                                    how: str,
                                                                    needle: str) -> None:
    """Another θ than the study's, a request over another knob than its own, an
    instrument without its report or its request, a request touched after its passes, a
    report silent on where it ran, reports of two commits, a request the page would not
    render, a control without its report or that replayed another request: each would
    read as the wider menu played in the study's frame, and is refused."""
    requests, reports = _study(tmp_path, script)
    if how == "cadre":
        _phase11(requests, reports, script, key="pfu", theta={"common": 0.25})
    elif how == "bouton":
        _phase11(requests, reports, script, key="pfu", bounds=[
            {"knob": "decote_taux", "low": 0.30, "high": 0.40, "step": 0.05}])
    else:
        _phase11(requests, reports, script)
    pfu_report = reports / "exploration_phase11_pfu.json"
    control = reports / script.CONTROLS / "exploration_etude_csg.json"
    if how == "sans_rapport":
        pfu_report.unlink()
    elif how == "sans_requete":
        (requests / "phase11" / "pfu.json").unlink()
    elif how == "retouchee":
        path = requests / "phase11" / "pfu.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["bounds"][0]["step"] = 0.005
        path.write_text(json.dumps(payload), encoding="utf-8")
    elif how in ("ou", "commits"):
        report = json.loads(pfu_report.read_text(encoding="utf-8"))
        report.update({"where": " "} if how == "ou" else {"commit": "d" * 40})
        pfu_report.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    elif how == "hors_menu":
        (requests / "phase11" / "cvae.json").write_text(
            (requests / "phase11" / "pfu.json").read_text(encoding="utf-8"),
            encoding="utf-8")
    elif how == "controle_sans_rapport":
        (reports / script.CONTROLS / "exploration_etude_ir.json").unlink()
    elif how in ("controle_autre_requete", "controle_commit"):
        report = json.loads(control.read_text(encoding="utf-8"))
        if how == "controle_commit":
            report["commit"] = "d" * 40
        else:
            report["request"]["horizon"] = 9
        control.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(script.EtudeError, match=needle):
        script.study(requests, reports)


# --------------------------------------------------------------------------- #
# the PFU of the wider menu, replayed with the wages its owners shift (D-252)
# --------------------------------------------------------------------------- #
SALAIRES_COMMIT = "f" * 40
#: What the wage shift adds to a corner where it is at its high end, in share of GDP.
SHIFTED = 4e-4


def _salaires(requests: Path, reports: Path, script, **request_overrides) -> None:
    """The wider menu's PFU replayed: its request with name, title and question changed,
    and a report whose corners vary the wage shift — at 0 the menu's own, at 1 higher."""
    payload = json.loads((requests / "phase11" / "pfu.json").read_text(encoding="utf-8"))
    payload.update(name="phase11_salaires_pfu", titre="Le PFU, avec les salaires déplacés",
                   question="Avec les salaires déplacés, le PFU fait-il baisser la dette ?")
    payload.update(request_overrides)
    (requests / script.SALAIRES).mkdir()
    (requests / script.SALAIRES / "pfu.json").write_text(json.dumps(payload),
                                                         encoding="utf-8")
    report = json.loads((reports / "exploration_phase11_pfu.json").read_text(
        encoding="utf-8"))
    report.update(name=payload["name"], titre=payload["titre"],
                  question=payload["question"], commit=SALAIRES_COMMIT,
                  computed="2026-10-26",
                  request=ExplorationRequest.model_validate(payload).model_dump(
                      mode="json", exclude_none=True))
    for search in report["searches"]:
        # The shift raises Δb at θ = ½ too, wherever the report carries it.
        for e in (*search["evaluations"], *search["candidates"], search["indices"],
                  search["closest"] or {}):
            if "delta_aged" in e:
                e["delta_aged"] += SHIFTED / 2
        for e in search["evaluations"]:
            e["corners"] = [pair for label, value in e["corners"] for pair in (
                [f"{label}, {script.WAGE_SHIFT} = 0", value],
                [f"{label}, {script.WAGE_SHIFT} = 1", value + SHIFTED])]
            e["corner_high"] = max(value for _, value in e["corners"])
    (reports / f"exploration_{script.SALAIRES}_pfu.json").write_text(
        json.dumps(report, ensure_ascii=False), encoding="utf-8")


def _with_salaires(tmp_path: Path, script, **request_overrides) -> tuple[Path, Path]:
    requests, reports = _study(tmp_path, script)
    _phase11(requests, reports, script)
    _salaires(requests, reports, script, **request_overrides)
    return requests, reports


def test_the_pfu_replayed_with_the_wage_shift_is_rendered_apart(script, tmp_path) -> None:
    """D-252: the replay has its own section after the wider menu's, with its commit, its
    answer under each persistence beside the menu's, and its control: at a wage shift of
    0, every corner and every cost the menu's."""
    requests, reports = _with_salaires(tmp_path, script)
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    salaires = phase11["salaires"]
    assert salaires["control"] == {"share": 0.0, "eur": 0.0, "given_back": True}
    page = script.render(etudes, complements, courbe, phase11)
    menu, _, tail = page.partition("## Le PFU rejoué avec les salaires déplacés")
    assert tail and SALAIRES_COMMIT in tail and SALAIRES_COMMIT not in menu
    assert "## Le menu élargi de la phase 11" in menu and "D-252" in tail
    for search in salaires["report"]["searches"]:
        assert script.verdict(search, salaires["instrument"], 0.0) in tail
    assert tail.count("Sans les salaires déplacés, au menu élargi") == 2
    # Beside each verdict, the menu's Δb, not the replay's.
    for search, before in zip(salaires["report"]["searches"],
                              salaires["menu"]["searches"], strict=True):
        line = next(x for x in tail.splitlines()
                    if x.startswith(f"**{search['persistence_label']}.**"))
        then = line.partition("Sans les salaires déplacés")[2]
        for e in before["evaluations"]:
            assert script._pt(e["delta_aged"]) in then
        assert all(script._pt(e["delta_aged"]) not in then
                   for e in search["evaluations"])
    assert "il les redonne" in tail and "**Ce que ce chiffre ne compte pas.**" in tail
    assert "figure A2" in tail


def test_a_replay_that_does_not_give_the_menu_back_at_no_shift_is_said_so(script,
                                                                          tmp_path) -> None:
    """D-252: a corner at no shift off the menu's by more than a ten-thousandth of a point
    is a result, said with its gap, not a refusal."""
    requests, reports = _with_salaires(tmp_path, script)
    path = reports / f"exploration_{script.SALAIRES}_pfu.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["searches"][1]["evaluations"][0]["corners"][0][1] += 3e-6
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    control = phase11["salaires"]["control"]
    assert control["share"] == pytest.approx(3e-6) and not control["given_back"]
    assert "il ne les redonne pas" in script.render(etudes, complements, courbe, phase11)


#: Each way a replay could read as the wider menu's PFU played with the wage shift
#: without being so.
SALAIRES_REFUSALS = [
    ("cadre", "ne rejoue pas la requête du PFU"),
    ("grille", "ne rejoue pas la requête du PFU"),
    ("sans_rapport", "le rejeu du PFU sans rapport"),
    ("sans_requete", "sans la requête du PFU"),
    ("retouchee", "n'a pas joué sa requête, etude/phase11_salaires"),
    ("ou", "ne dit pas où"),
    ("hors_menu", "seul le PFU s'y rejoue"),
    ("sans_salaires", "ne fait pas varier"),
    ("sans_menu", "que le dépôt n'a pas"),
    ("pendant", "n'a pas son pendant"),
    ("persistances", "pas les mêmes persistances"),
]


@pytest.mark.parametrize("how, needle", SALAIRES_REFUSALS,
                         ids=[how for how, _ in SALAIRES_REFUSALS])
def test_a_replay_that_is_not_the_menu_s_pfu_with_the_shift_is_refused(script, tmp_path,
                                                                       how: str,
                                                                       needle: str) -> None:
    """Another frame or grid than the menu's PFU, a replay without its report or its
    request, a request touched after its pass, a report silent on where it ran, a request
    the page would not render, corners that do not vary the shift, a replay of a menu the
    repository does not have, a corner the menu has no counterpart for, or persistences
    out of order: each would read as the PFU replayed with the wage shift, and is
    refused. A bundle the menu lacks cannot be: one request is one grid, and the schema
    has a report carry each of its bundles."""
    overrides = {"cadre": {"horizon": 9},
                 "grille": {"bounds": [{"knob": "pfu_taux", "low": 0.098, "high": 0.118,
                                        "step": 0.01}]}}.get(how, {})
    requests, reports = _with_salaires(tmp_path, script, **overrides)
    path = reports / f"exploration_{script.SALAIRES}_pfu.json"
    request_path = requests / script.SALAIRES / "pfu.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if how == "sans_rapport":
        path.unlink()
    elif how == "sans_requete":
        request_path.unlink()
    elif how == "retouchee":
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        payload["question"] = payload["question"] + " (retouchée)"
        payload["titre"] = "retouchée"
        request_path.write_text(json.dumps(payload), encoding="utf-8")
    elif how == "hors_menu":
        (requests / script.SALAIRES / "is.json").write_text(
            request_path.read_text(encoding="utf-8"), encoding="utf-8")
    elif how == "sans_menu":
        import shutil

        shutil.rmtree(requests / "phase11")
    if how in ("ou", "sans_salaires", "pendant", "persistances"):
        evaluation = report["searches"][0]["evaluations"][0]
        if how == "ou":
            report["where"] = " "
        elif how == "sans_salaires":
            evaluation["corners"] = [[label.split(f", {script.WAGE_SHIFT}")[0], value]
                                     for label, value in evaluation["corners"]]
        elif how == "pendant":
            label, value = evaluation["corners"][0]
            evaluation["corners"][0] = [f"{label}, une_autre_ligne = 0", value]
        else:
            report["searches"].reverse()
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(script.EtudeError, match=needle):
        script.study(requests, reports)


# --------------------------------------------------------------------------- #
# the curve's knobs, replayed with their self-financing (D-264, D-266)
# --------------------------------------------------------------------------- #
AUTO_COMMIT = "a" * 40
#: Each replay its own commit, as each ran on its own preregistration's.
AUTO_COMMITS = {"t_delta": AUTO_COMMIT, "t_min": "b" * 40}
#: A one-bundle grid of each knob, other than the curve's.
OTHER_GRIDS = {"t_delta": {"knob": "allegement_general_t_delta_moins_de_50",
                           "low": 0.3931, "high": 0.3931, "step": 0.01},
               "t_min": {"knob": "allegement_general_t_min", "low": 0.024,
                         "high": 0.024, "step": 0.003}}
#: C11's share at θ = ½ in the replay built here: what comes back of the cut.
AUTO_HALF = 0.38
#: C11's share at θ = 0, where the weight is 0 and C2 reads its weakest elasticity.
AUTO_LOW = 0.12


def _replay(script, key: str):
    return next(r for r in script.AUTOFINANCEMENT_MENU if r.key == key)


def _autofinancement(requests: Path, reports: Path, script, key: str = "t_delta", *,
                     replay=None, half: float = AUTO_HALF, low: float = AUTO_LOW,
                     commit: str | None = None, **request_overrides) -> None:
    """One knob of the curve replayed: its request with name, title and question changed,
    and a report whose corners vary C11's weight — at 1 what the Trésor-Éco's share leaves
    of the curve's Δb, at 0 what C2's reading leaves. The first replays' by default; the
    reconciled one's with `replay` (D-271)."""
    replay = replay or _replay(script, key)
    payload = json.loads((requests / "courbe" / f"{key}.json").read_text(encoding="utf-8"))
    payload.update(name=f"{replay.report}_{key}",
                   titre=f"Le {key}, avec son autofinancement",
                   question=f"Avec son autofinancement, le {key} fait-il baisser la dette ?")
    payload.update(request_overrides)
    directory = requests / replay.directory
    directory.mkdir(exist_ok=True)
    (directory / f"{key}.json").write_text(json.dumps(payload), encoding="utf-8")
    report = json.loads((reports / f"exploration_courbe_{key}.json").read_text(
        encoding="utf-8"))
    report.update(name=payload["name"], titre=payload["titre"],
                  question=payload["question"], commit=commit or AUTO_COMMITS[key],
                  computed="2026-10-26",
                  request=ExplorationRequest.model_validate(payload).model_dump(
                      mode="json", exclude_none=True))
    share = script.tresor_eco_share()
    for search in report["searches"]:
        # C11 lowers Δb at θ = ½ too, wherever the report carries it.
        for e in (*search["evaluations"], *search["candidates"], search["indices"],
                  search["closest"] or {}):
            for delta in ("delta_aged", "delta_frozen"):
                if delta in e:
                    e[delta] *= 1 - half
        for e in search["evaluations"]:
            e["corners"] = [pair for label, value in e["corners"] for pair in (
                [f"{label}, {script.SELF_FINANCING_WEIGHT} = 0", value * (1 - low)],
                [f"{label}, {script.SELF_FINANCING_WEIGHT} = 1", value * (1 - share)])]
            e["corner_low"] = min(value for _, value in e["corners"])
            e["corner_high"] = max(value for _, value in e["corners"])
    (reports / f"exploration_{replay.report}_{key}.json").write_text(
        json.dumps(report, ensure_ascii=False), encoding="utf-8")


def _courbe_jobs(reports: Path, key: str = "t_delta") -> None:
    """One knob of the curve with C2's jobs among its indices, as the passes carry them: the
    stubbed pass reads no behaviour, and a control on the indices needs one."""
    path = reports / f"exploration_courbe_{key}.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    for search in report["searches"]:
        row = next(r for r in search["indices"]["rows"] if r["key"] == "emploi_smic")
        row.update(available=True, values={"2026": 13_408.0},
                   box={"2026": [9_840.0, 16_083.0]})
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")


def _with_autofinancement(tmp_path: Path, script, *keys: str,
                          **request_overrides) -> tuple[Path, Path]:
    """The study and its curve, with each of `keys` replayed (the `t_delta` alone by
    default); `request_overrides` go to every replay's request."""
    requests, reports = _study(tmp_path, script)
    _courbe(requests, reports, script)
    for key in keys or ("t_delta",):
        _courbe_jobs(reports, key)
        _autofinancement(requests, reports, script, key, **request_overrides)
    return requests, reports


def test_the_t_delta_replayed_with_its_self_financing_is_rendered_apart(script,
                                                                        tmp_path) -> None:
    """D-264: the replay has its own section, with its commit, its answer under each
    persistence beside the curve's, and its control: where C11's weight is 1, every corner
    what the Trésor-Éco's share leaves of the curve's; every cost and index the curve's."""
    requests, reports = _with_autofinancement(tmp_path, script)
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    auto = next(e for e in courbe if e["instrument"].key == "t_delta")["autofinancement"]
    assert auto["share"] == pytest.approx(0.6)
    assert auto["control"] == {"share": 0.0, "eur": 0.0, "indices": 0.0,
                               "given_back": True}
    page = script.render(etudes, complements, courbe, phase11)
    head, _, tail = page.partition("## Le `t_delta` de la courbe rejoué avec son "
                                   "autofinancement")
    assert tail and AUTO_COMMIT in tail and AUTO_COMMIT not in head
    assert "## La courbe de 2026, préenregistrée à part" in head
    assert "D-264" in tail and "## Ce que l'étude ne dit pas" in tail
    for search in auto["report"]["searches"]:
        assert script.verdict(search, auto["instrument"], 0.0) in tail
    assert tail.count("Sans l'autofinancement, à la courbe") == 2
    # Beside each verdict, the curve's Δb, not the replay's.
    for search, before in zip(auto["report"]["searches"], auto["courbe"]["searches"],
                              strict=True):
        line = next(x for x in tail.splitlines()
                    if x.startswith(f"**{search['persistence_label']}.**"))
        then = line.partition("Sans l'autofinancement")[2]
        for e in before["evaluations"]:
            assert script._pt(e["delta_aged"]) in then
        assert all(script._pt(e["delta_aged"]) not in then
                   for e in search["evaluations"])
    assert "60 %" in tail and "0,40 fois l'écart de la courbe" in tail
    assert "Il les redonne." in tail and "**Ce que ce chiffre ne compte pas.**" in tail
    assert "temps plein" in tail
    # The control read C2's jobs, which the curve carries and the replay must give back.
    assert "emploi_smic" in script._non_chain(auto["report"]["searches"][0])
    # The verdict points to what the chain lacks: the section says it.
    lacks = auto["report"]["searches"][0]["indices"]["absent"]
    assert lacks and "**Ce qui manque à la chaîne**" in tail
    assert all(f"- {name} : " in tail for name in lacks)


@pytest.mark.parametrize("how", ["coin", "cout", "indice"])
def test_a_replay_that_does_not_give_the_curve_back_at_full_weight_is_said_so(
        script, tmp_path, how: str) -> None:
    """D-264: a corner at full weight off the curve's share by more than a ten-thousandth
    of a point, a cost off by more than a euro, or an index off: a result, said with its
    gap, not a refusal."""
    requests, reports = _with_autofinancement(tmp_path, script)
    path = reports / f"exploration_{script.AUTOFINANCEMENT}_t_delta.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    search = report["searches"][1]
    if how == "coin":
        search["evaluations"][0]["corners"][1][1] += 3e-6
    elif how == "cout":
        search["evaluations"][0]["cost_frozen_eur"] += 2.0
    else:
        row = next(r for r in search["indices"]["rows"]
                   if r["available"] and r["stage"] != "chaîne" and r["values"])
        key = next(iter(row["values"]))
        row["values"][key] += 1.0
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    control = next(e for e in courbe if e.get("autofinancement"))["autofinancement"][
        "control"]
    gap = {"coin": ("share", 3e-6), "cout": ("eur", 2.0), "indice": ("indices", 1.0)}[how]
    assert control[gap[0]] == pytest.approx(gap[1]) and not control["given_back"]
    assert "Il ne les redonne pas." in script.render(etudes, complements, courbe, phase11)


#: Each way a replay could read as a knob of the curve played with C11 without being so;
#: `{key}` and `{directory}` are the replay's.
AUTOFINANCEMENT_REFUSALS = [
    ("cadre", "ne rejoue pas la requête du {key}"),
    ("grille", "ne rejoue pas la requête du {key}"),
    ("sans_rapport", "le rejeu du {key} sans rapport"),
    ("sans_requete", "sans la requête du {key}"),
    ("retouchee", "n'a pas joué sa requête, etude/{directory}/"),
    ("ou", "ne dit pas où"),
    ("hors_menu", "seul le {key} s'y rejoue"),
    ("sans_poids", "ne fait pas varier"),
    ("sans_courbe", "rejoue le {key} d'une courbe que le dépôt n'a pas"),
    ("pendant", "n'a pas son pendant"),
    ("persistances", "le rejeu du {key} et la courbe n'ont pas les mêmes persistances"),
    ("indices", "le rejeu du {key} et la courbe n'ont pas les mêmes indices"),
    ("annees", "n'a pas les années"),
    ("boite", "a une boîte que la courbe n'a pas"),
]


@pytest.mark.parametrize("key", ["t_delta", "t_min"])
@pytest.mark.parametrize("how, needle", AUTOFINANCEMENT_REFUSALS,
                         ids=[how for how, _ in AUTOFINANCEMENT_REFUSALS])
def test_a_replay_that_is_not_the_curve_s_knob_with_c11_is_refused(script, tmp_path,
                                                                   how: str, needle: str,
                                                                   key: str) -> None:
    """Another frame or grid than the curve's knob, a replay without its report or its
    request, a request touched after its passes, a report silent on where it ran, a
    request the page would not render, corners that do not vary C11's weight, a replay of
    a curve the repository does not have, a corner the curve has no counterpart for,
    persistences out of order, or indices that are not the curve's to compare: each would
    read as the knob replayed with its self-financing, and is refused — for the `t_delta`
    and for the floor alike."""
    overrides = {"cadre": {"horizon": 9},
                 "grille": {"bounds": [OTHER_GRIDS[key]]}}.get(how, {})
    requests, reports = _with_autofinancement(tmp_path, script, key, **overrides)
    directory = _replay(script, key).directory
    path = reports / f"exploration_{script.AUTOFINANCEMENT}_{key}.json"
    request_path = requests / directory / f"{key}.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if how == "sans_rapport":
        path.unlink()
    elif how == "sans_requete":
        request_path.unlink()
    elif how == "retouchee":
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        payload["titre"] = "retouchée"
        request_path.write_text(json.dumps(payload), encoding="utf-8")
    elif how == "hors_menu":
        other = "t_min" if key == "t_delta" else "t_delta"
        (requests / directory / f"{other}.json").write_text(
            request_path.read_text(encoding="utf-8"), encoding="utf-8")
    elif how == "sans_courbe":
        import shutil

        shutil.rmtree(requests / "courbe")
    search = report["searches"][0]
    evaluation = search["evaluations"][0]
    rows = [r for r in search["indices"]["rows"]
            if r["available"] and r["stage"] != "chaîne"]
    if how == "ou":
        report["where"] = " "
    elif how == "sans_poids":
        evaluation["corners"] = [
            [label.split(f", {script.SELF_FINANCING_WEIGHT}")[0], value]
            for label, value in evaluation["corners"]]
    elif how == "pendant":
        label, value = evaluation["corners"][1]
        evaluation["corners"][1] = [f"{label}, une_autre_ligne = 0", value]
    elif how == "persistances":
        report["searches"].reverse()
    elif how == "indices":
        rows[0]["available"] = False
    elif how == "annees":
        row = next(r for r in rows if r["values"])
        row["values"]["2099"] = 0.0
    elif how == "boite":
        row = next(r for r in rows if r["values"])
        row["box"]["2027"] = [0.0, 0.0]
    if how in ("ou", "sans_poids", "pendant", "persistances", "indices", "annees",
               "boite"):
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(script.EtudeError, match=needle.format(key=key, directory=directory)):
        script.study(requests, reports)


def test_the_floor_replayed_with_its_self_financing_has_its_own_section(script,
                                                                        tmp_path) -> None:
    """D-266: the floor's replay, under its own directory, has its own section after the
    `t_delta`'s, with its own commit and entry, and what it leaves out beyond what both
    do; the `t_delta`'s section does not change for it."""
    requests, reports = _with_autofinancement(tmp_path, script, "t_delta", "t_min")
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    replays = {e["instrument"].key: e["autofinancement"] for e in courbe}
    assert all(a["control"]["given_back"] for a in replays.values())
    page = script.render(etudes, complements, courbe, phase11)
    t_delta_title = "## Le `t_delta` de la courbe rejoué avec son autofinancement"
    floor_title = "## Le plancher `t_min` de la courbe rejoué avec son autofinancement"
    assert page.index(t_delta_title) < page.index(floor_title)
    t_delta, _, floor = page.partition(floor_title)
    t_delta = t_delta.partition(t_delta_title)[2]
    assert AUTO_COMMITS["t_min"] in floor and AUTO_COMMITS["t_min"] not in t_delta
    assert AUTO_COMMITS["t_delta"] in t_delta and AUTO_COMMITS["t_delta"] not in floor
    assert "D-266" in floor and "`etude/courbe_autofinancement_plancher/`" in floor
    assert "dès 2 SMIC" in floor and "dès 2 SMIC" not in t_delta
    for search in replays["t_min"]["report"]["searches"]:
        assert script.verdict(search, replays["t_min"]["instrument"], 0.0) in floor
    # The t_delta's section is what it was without the floor's replay.
    (tmp_path / "seul").mkdir()
    alone = _with_autofinancement(tmp_path / "seul", script)
    before = script.render(*script.study(*alone))
    assert t_delta_title + t_delta in before


# --------------------------------------------------------------------------- #
# the curve replayed with the reconciled C11 (D-270, D-271)
# --------------------------------------------------------------------------- #
MESURE_COMMIT = "7" * 40
#: C11's share at θ = ½ and at θ = 0 with the reconciled value of a job: lower than the
#: first replays', C2's jobs being worth less.
MESURE_HALF, MESURE_LOW = 0.367, 0.10
MESURE_TITLE = "## La courbe rejouée avec l'autofinancement réconcilié"
THETA_TITLE = "## La réponse à θ = 0 et à θ = 1"
NOT_SAID = "## Ce que l'étude ne dit pas"


def _mesure(script, key: str):
    return next(r for r in script.MESURE_MENU if r.key == key)


def _with_mesure(tmp_path: Path, script, *, earlier: bool = True,
                 **request_overrides) -> tuple[Path, Path]:
    """The study and its curve, both knobs replayed first (unless not `earlier`), then both
    replayed with the reconciled C11 on one commit."""
    if earlier:
        requests, reports = _with_autofinancement(tmp_path, script, "t_delta", "t_min")
    else:
        requests, reports = _study(tmp_path, script)
        _courbe(requests, reports, script)
        for key in ("t_delta", "t_min"):
            _courbe_jobs(reports, key)
    for key in ("t_delta", "t_min"):
        _autofinancement(requests, reports, script, key, replay=_mesure(script, key),
                         half=MESURE_HALF, low=MESURE_LOW, commit=MESURE_COMMIT,
                         **request_overrides)
    return requests, reports


def test_the_curve_replayed_with_the_reconciled_c11_is_rendered_apart(script,
                                                                      tmp_path) -> None:
    """D-271: both knobs under one section after the first replays', with their commit,
    each knob's share at θ = ½ beside the first replay's, and beside each verdict the
    curve's Δb and the first replay's; the page before it does not change."""
    requests, reports = _with_mesure(tmp_path, script)
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    measured = {e["instrument"].key: e["mesure"] for e in courbe}
    assert all(m["control"]["given_back"] for m in measured.values())
    page = script.render(etudes, complements, courbe, phase11)
    floor_title = "## Le plancher `t_min` de la courbe rejoué avec son autofinancement"
    assert page.index(floor_title) < page.index(MESURE_TITLE)
    head, _, tail = page.partition(MESURE_TITLE)
    section, _, rest = tail.partition(THETA_TITLE)
    assert MESURE_COMMIT in section and MESURE_COMMIT not in head + rest
    assert "D-271" in section and "`etude/courbe_autofinancement_mesure/`" in section
    assert "Les rejeux qui précèdent valorisaient les emplois de C2 à 12 000 €" in section
    t_delta, _, floor = section.partition("### Le plancher `t_min`")
    assert "### Le `t_delta`" in t_delta and floor
    for key, part in (("t_delta", t_delta), ("t_min", floor)):
        auto = measured[key]
        first = next(e for e in courbe if e["instrument"].key == key)["autofinancement"]
        now = script.returned_share(auto["report"]["searches"][0],
                                    auto["courbe"]["searches"][0])
        then = script.returned_share(first["report"]["searches"][0],
                                     auto["courbe"]["searches"][0])
        assert now == pytest.approx(MESURE_HALF) and then == pytest.approx(AUTO_HALF)
        assert (f"C11 rend {script._pct(now)} de la baisse de chaque paquet, contre "
                f"{script._pct(then)} à 12 000 € l'emploi ({first['replay'].entry})") in part
        for search, before, old in zip(auto["report"]["searches"],
                                       auto["courbe"]["searches"],
                                       first["report"]["searches"], strict=True):
            assert script.verdict(search, auto["instrument"], 0.0) in part
            line = next(x for x in part.splitlines()
                        if x.startswith(f"**{search['persistence_label']}.**"))
            at_curve, _, at_old = line.partition("À 12 000 € l'emploi")
            assert all(script._pt(e["delta_aged"]) in at_curve.partition(
                "Sans l'autofinancement")[2] for e in before["evaluations"])
            assert all(script._pt(e["delta_aged"]) in at_old for e in old["evaluations"])
        assert "Il les redonne :" in part and "**Ce que ce chiffre ne compte pas.**" in part
        assert "les indices du paquet le plus proche sont ceux de la courbe." in part
        assert "célibataire sans enfant ni loyer" in part
    assert "dès 2 SMIC" in floor and "dès 2 SMIC" not in t_delta
    # The page before the section is the page without it, the θ section aside: that one
    # reads every report the page renders, this replay's among them (D-274).
    (tmp_path / "avant").mkdir()
    before = script.render(*script.study(*_with_autofinancement(
        tmp_path / "avant", script, "t_delta", "t_min")))
    above, _, below = before.partition(THETA_TITLE)
    assert above == head
    assert below.partition(NOT_SAID)[2] == rest.partition(NOT_SAID)[2]
    replayed = "rejoué avec l'autofinancement réconcilié (D-271)"
    assert replayed in rest.partition(NOT_SAID)[0] and replayed not in below


def test_the_reconciled_replay_without_the_first_says_so(script, tmp_path) -> None:
    """Without the first replays, the section neither says they came before nor sets a
    share beside its own."""
    requests, reports = _with_mesure(tmp_path, script, earlier=False)
    page = script.render(*script.study(requests, reports))
    section = page.partition(MESURE_TITLE)[2].partition("## Ce que l'étude ne dit pas")[0]
    assert section.count("### Le ") == 2
    assert "C11 valorisait les emplois de C2 à 12 000 €" in section
    assert "Les rejeux qui précèdent" not in section
    assert " l'emploi (D-26" not in section and "À 12 000 € l'emploi" not in section


def test_a_reconciled_replay_off_the_curve_at_full_weight_is_said_so(script,
                                                                     tmp_path) -> None:
    requests, reports = _with_mesure(tmp_path, script)
    path = reports / f"exploration_{script.MESURE}_t_min.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["searches"][0]["evaluations"][0]["corners"][1][1] += 3e-6
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    measured = next(e for e in courbe if e["instrument"].key == "t_min")["mesure"]
    assert not measured["control"]["given_back"]
    section = script.render(etudes, complements, courbe, phase11).partition(
        "### Le plancher `t_min`")[2]
    assert "Il ne les redonne pas :" in section.partition("## Ce que l'étude ne dit pas")[0]


#: The first replays' refusals hold for the reconciled one, with its own directory and its
#: own reports; one of them, a request beside its own, reads otherwise under a directory
#: two knobs share.
MESURE_REFUSALS = [
    (how, {"hors_menu": "seuls t_delta et t_min s'y rejouent",
           "sans_courbe": "etude/{directory}/ rejoue le t_delta d'une courbe que le dépôt "
                          "n'a pas"}.get(how, needle))
    for how, needle in AUTOFINANCEMENT_REFUSALS]


@pytest.mark.parametrize("key", ["t_delta", "t_min"])
@pytest.mark.parametrize("how, needle", MESURE_REFUSALS,
                         ids=[how for how, _ in MESURE_REFUSALS])
def test_a_reconciled_replay_that_is_not_the_curve_s_knob_with_c11_is_refused(
        script, tmp_path, how: str, needle: str, key: str) -> None:
    overrides = {"cadre": {"horizon": 9},
                 "grille": {"bounds": [OTHER_GRIDS[key]]}}.get(how, {})
    # Without the curve, the first replays would be refused first: here they are not.
    requests, reports = _with_mesure(tmp_path, script, earlier=how != "sans_courbe")
    if overrides:
        # One knob's request out of the curve's frame or grid, the other left as it was.
        _autofinancement(requests, reports, script, key, replay=_mesure(script, key),
                         half=MESURE_HALF, low=MESURE_LOW, commit=MESURE_COMMIT,
                         **overrides)
    directory = script.MESURE
    path = reports / f"exploration_{script.MESURE}_{key}.json"
    request_path = requests / directory / f"{key}.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if how == "sans_rapport":
        path.unlink()
    elif how == "sans_requete":
        request_path.unlink()
    elif how == "retouchee":
        payload = json.loads(request_path.read_text(encoding="utf-8"))
        payload["titre"] = "retouchée"
        request_path.write_text(json.dumps(payload), encoding="utf-8")
    elif how == "hors_menu":
        (requests / directory / "pfu.json").write_text(
            request_path.read_text(encoding="utf-8"), encoding="utf-8")
    elif how == "sans_courbe":
        import shutil

        shutil.rmtree(requests / "courbe")
    search = report["searches"][0]
    evaluation = search["evaluations"][0]
    rows = [r for r in search["indices"]["rows"]
            if r["available"] and r["stage"] != "chaîne"]
    if how == "ou":
        report["where"] = " "
    elif how == "sans_poids":
        evaluation["corners"] = [
            [label.split(f", {script.SELF_FINANCING_WEIGHT}")[0], value]
            for label, value in evaluation["corners"]]
    elif how == "pendant":
        label, value = evaluation["corners"][1]
        evaluation["corners"][1] = [f"{label}, une_autre_ligne = 0", value]
    elif how == "persistances":
        report["searches"].reverse()
    elif how == "indices":
        rows[0]["available"] = False
    elif how == "annees":
        row = next(r for r in rows if r["values"])
        row["values"]["2099"] = 0.0
    elif how == "boite":
        row = next(r for r in rows if r["values"])
        row["box"]["2027"] = [0.0, 0.0]
    if how in ("ou", "sans_poids", "pendant", "persistances", "indices", "annees",
               "boite"):
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(script.EtudeError, match=needle.format(key=key, directory=directory)):
        script.study(requests, reports)


def test_reconciled_replays_of_two_commits_are_refused(script, tmp_path) -> None:
    """Preregistered together, the two knobs run on one commit (D-271)."""
    requests, reports = _with_mesure(tmp_path, script)
    path = reports / f"exploration_{script.MESURE}_t_min.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    report["commit"] = "d" * 40
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(script.EtudeError, match="un seul commit"):
        script.study(requests, reports)


@pytest.mark.parametrize("row, why, part", [("emploi_smic", True, "values"),
                                            ("emploi_smic", True, "box"),
                                            (None, False, "values")])
def test_a_reconciled_replay_s_indices_off_the_curve_are_named(script, tmp_path,
                                                                row: str | None,
                                                                why: bool, part: str) -> None:
    """D-272: the reconciled replay's indices are not held to the curve's as its corners
    and costs are: C2 counts each earner at their own weight since D-269. The page names
    each index off the curve, with its largest gap, on its values or its θ box, and says
    D-269's reason for C2's only."""
    requests, reports = _with_mesure(tmp_path, script)
    if row is None:
        # Mésange's jobs, which the stubbed pass leaves empty: given alike to the curve and
        # to both its replays, so that only the reconciled one is moved below.
        row = "emploi_marchand"
        for name in ("courbe", script.AUTOFINANCEMENT, script.MESURE):
            at = reports / f"exploration_{name}_t_delta.json"
            payload = json.loads(at.read_text(encoding="utf-8"))
            for search in payload["searches"]:
                marchand = next(r for r in search["indices"]["rows"] if r["key"] == row)
                marchand.update(available=True, values={"1": 3.28, "2": 9.17}, box=None)
            at.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    path = reports / f"exploration_{script.MESURE}_t_delta.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    for search in report["searches"]:
        moved = next(r for r in search["indices"]["rows"] if r["key"] == row)
        year = next(iter(moved["values"]))
        if part == "values":
            moved["values"][year] -= 40.0
        else:
            moved["box"][year][1] -= 40.0
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    auto = next(e for e in courbe if e["instrument"].key == "t_delta")["mesure"]
    label = next(r["label"] for r in auto["report"]["searches"][0]["indices"]["rows"]
                 if r["key"] == row)
    assert script.index_gaps(auto["report"], auto["courbe"])[0][::2] == (label, 40.0)
    section = script.render(etudes, complements, courbe, phase11).partition(
        MESURE_TITLE)[2].partition("### Le plancher `t_min`")[0]
    assert "Il les redonne :" in section
    assert f"sauf : {label}, de 40,00 " in section
    assert ("C2 y compte chacun à son propre poids dans la passe (D-269)" in section) is why


# --------------------------------------------------------------------------- #
# θ = 0 and θ = 1, read off the box (D-274)
# --------------------------------------------------------------------------- #
def _at(evaluation: dict, side: str) -> float:
    """Built apart from the script: the one corner that sets no row to the other side."""
    other = "1" if side == "0" else "0"
    [value] = [v for label, v in evaluation["corners"] if f" = {other}" not in label]
    return value


def _theta_section(page: str) -> str:
    return page.partition(THETA_TITLE)[2].partition(NOT_SAID)[0]


def _table(section: str, label: str) -> str:
    return section.partition(f"**{label}.**")[2].partition("**")[0]


def _set_corners(evaluation: dict, corners: list) -> None:
    """New corners, and the box shown with them: the report's schema holds them equal."""
    values = [v for _, v in corners]
    evaluation.update(corners=corners, corner_low=min(values), corner_high=max(values))


def test_the_theta_section_reads_each_bundle_at_its_diagonal_corners(script,
                                                                    tmp_path) -> None:
    """Each instrument under each persistence: Δb at θ = 0, at θ = ½ and at θ = 1, from
    its lowest bundle to its highest, and how many bundles meet the target at each, in the
    table of its persistence; the section after every other, before what the study does
    not say."""
    etudes = script.load(*_study(tmp_path, script))
    page = script.render(etudes)
    section = _theta_section(page)
    assert section and page.index(THETA_TITLE) < page.index(NOT_SAID)
    assert page.index(THETA_TITLE) > page.index(f"### {etudes[-1]['instrument'].label}")
    target = etudes[0]["report"]["hypotheses"]["target_share"]
    moved = False
    for entry in etudes:
        for search in entry["report"]["searches"]:
            columns = [[_at(e, "0") for e in search["evaluations"]],
                       [e["delta_aged"] for e in search["evaluations"]],
                       [_at(e, "1") for e in search["evaluations"]]]
            moved |= columns[0] != columns[2]
            counts = ", ".join(str(sum(x <= target for x in c)) for c in columns)
            row = (f"| {entry['instrument'].label} | "
                   + " | ".join(f"{script._fr(min(c) * 100)} à {script._pt(max(c))}"
                                for c in columns)
                   + f" | {counts} sur {len(columns[1])} |")
            assert row in _table(section, search["persistence_label"])
    assert moved
    assert "†" not in section
    assert "À chaque paquet, Δb à θ = ½ est entre Δb à θ = 0 et Δb à θ = 1." in section
    assert "Δb est le même" not in section
    assert "La vue figée n'a pas de coins" in section


def test_the_theta_section_says_at_which_theta_the_debt_falls(script, tmp_path) -> None:
    """Under « tenu », the multiplier at 1 makes every bundle meet the target, and at 0
    none: the section says so for θ = 1 and θ = 0, by persistence and with its count."""
    etudes = script.load(*_study(tmp_path, script))
    section = _theta_section(script.render(etudes))
    target = etudes[0]["report"]["hypotheses"]["target_share"]
    tenu = etudes[0]["report"]["searches"][1]
    assert not any(_at(e, "0") <= target for entry in etudes
                   for s in entry["report"]["searches"] for e in s["evaluations"])
    assert "**À θ = 0**, la dette ne baisse à aucun paquet, sous aucune persistance." in section
    falls = section.partition("**À θ = 1**, la dette baisse :")[2].partition("\n\n")[2]
    line = next(x for x in falls.splitlines() if x.startswith(f"- {tenu['persistence_label']}"))
    for entry in etudes:
        search = entry["report"]["searches"][1]
        n = sum(_at(e, "1") <= target for e in search["evaluations"])
        label = entry["instrument"].label
        said = f"{label[0].lower() + label[1:]} ({n} paquet"
        assert (said in line) is bool(n)


def test_a_bundle_nothing_moves_and_one_off_its_diagonal_are_named(script, tmp_path) -> None:
    """Where every corner gives the same Δb, the section says Δb the same at θ = 0, ½ and
    1, under every persistence or under the one it holds for; where Δb at θ = ½ leaves the
    interval of θ = 0 and θ = 1, it names the instrument instead of saying it never does."""
    requests, reports = _study(tmp_path, script)
    path = reports / "exploration_etude_decote.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    for search in report["searches"]:
        for e in search["evaluations"]:
            _set_corners(e, [[label, e["delta_aged"]] for label, _ in e["corners"]])
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    path = reports / "exploration_etude_ir.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    tenu = report["searches"][1]
    for e in tenu["evaluations"]:
        _set_corners(e, [[label, e["delta_aged"]] for label, _ in e["corners"]])
    eteint = report["searches"][0]["evaluations"][0]
    _set_corners(eteint, [[label, eteint["delta_aged"] - (1 + i) * 1e-3]
                          for i, (label, _) in enumerate(eteint["corners"])])
    # One bundle of four that nothing moves does not make the instrument one.
    still = report["searches"][0]["evaluations"][1]
    _set_corners(still, [[label, still["delta_aged"]] for label, _ in still["corners"]])
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    etudes = script.load(requests, reports)
    section = _theta_section(script.render(etudes))
    decote, ir = (next(e["instrument"].label for e in etudes if e["instrument"].key == k)
                  for k in ("decote", "ir"))
    same = section.partition("Δb est le même à θ = 0, à θ = ½ et à θ = 1")[2]
    same = same.partition("\n\n")[2].partition("\n\n")[0]
    assert f"- Sous chaque persistance : {decote[0].lower() + decote[1:]}." in same
    assert f"- {tenu['persistence_label']} : {ir[0].lower() + ir[1:]}." in same
    outside = section.partition("n'est pas entre Δb à θ = 0 et Δb à θ = 1")[2]
    outside = outside.partition("\n\n")[2].partition("\n\n")[0]
    assert outside == (f"- {report['searches'][0]['persistence_label']} : "
                       f"{ir[0].lower() + ir[1:]}.")
    assert "À chaque paquet, Δb à θ = ½ est entre" not in section


def test_an_absent_loop_is_marked_in_the_theta_section(script, tmp_path) -> None:
    """D-238: Δb that θ does not move because the loop is absent is not Δb that θ cannot
    move; the row says it."""
    requests, reports = _study(tmp_path, script)
    path = reports / "exploration_etude_allegements.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    for search in report["searches"]:
        search["indices"]["absent"] = {"rétroaction": "pas de ligne de solde"}
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    etudes = script.load(requests, reports)
    section = _theta_section(script.render(etudes))
    label = next(e["instrument"].label for e in etudes if e["instrument"].key == "allegements")
    for search in report["searches"]:
        assert f"| {label} † |" in _table(section, search["persistence_label"])
    assert section.count(" † |") == 2
    assert "† La boucle PIB → recettes est absente pour ce rendu, non nulle" in section


def test_a_box_of_one_corner_reads_the_same_at_theta_zero_and_one(script) -> None:
    """θ as asked, nothing moving the bundle: Δb at θ = 0 and at θ = 1 is that corner's."""
    from impots.predictif.exploration import NO_KEY

    assert script.diagonal({"knobs": {}, "corners": [[NO_KEY, 0.01]]}) == (0.01, 0.01)


def _corners(how: str):
    def edit(corners: list) -> list:
        if how == "sans_coin":
            return [c for c in corners if not c[0].endswith(" = 0")]
        if how == "deux_coins":
            return [*corners, next(c for c in corners if c[0].endswith(" = 1"))]
        if how == "autres_lignes":
            return [["eti_all = 0", corners[0][1]], *corners[1:]]
        return [["θ quelconque", corners[0][1]]]
    return edit


@pytest.mark.parametrize("how, needle", [
    ("sans_coin", "a 0 coin(s) où chaque ligne vaut 0, et non un"),
    ("deux_coins", "a 2 coin(s) où chaque ligne vaut 1, et non un"),
    ("autres_lignes", "ne nomment pas tous les mêmes lignes"),
    ("sans_ligne", "ne nomment pas tous les mêmes lignes"),
    ("autre_theta", "son θ et ses persistances"),
    ("autres_persistances", "son θ et ses persistances"),
])
def test_a_box_that_does_not_give_theta_zero_and_one_is_refused(script, tmp_path, how: str,
                                                                 needle: str) -> None:
    """GUARD. A box without a corner of each, with two, or whose corners do not name the same
    rows, does not say Δb at θ = 0 and θ = 1; a report run at another θ, or under other
    persistences, would put its Δb in the wrong column. Each is refused, not read."""
    requests, reports = _study(tmp_path, script)
    path = reports / "exploration_etude_decote.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if how == "autre_theta":
        report["hypotheses"]["theta"]["common"] = 0.4
    elif how == "autres_persistances":
        report["searches"].reverse()
    else:
        evaluation = report["searches"][1]["evaluations"][2]
        _set_corners(evaluation, _corners(how)(evaluation["corners"]))
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(script.EtudeError, match=re.escape(needle)):
        script.study(requests, reports)


def test_the_committed_theta_section_reads_every_report_the_page_renders(script) -> None:
    """On the committed reports: the fourteen the page renders, each read at the corners
    built apart here, and named in the table of each persistence."""
    etudes, complements, courbe, phase11 = script.study()
    named = script.rendered(etudes, complements, courbe, phase11)
    loaded = ([e["report"] for e in etudes] + [c["report"] for c in complements]
              + [e["report"] for e in courbe]
              + [e["report"] for e in phase11["entries"]] + [phase11["salaires"]["report"]]
              + [e[k]["report"] for k in ("autofinancement", "mesure") for e in courbe])
    assert len(named) == len(loaded) == 14
    assert {id(r) for _, r in named} == {id(r) for r in loaded}
    rows = script.theta_rows(etudes, complements, courbe, phase11)
    assert len(rows) == 28
    section = _theta_section(script.OUT.read_text(encoding="utf-8"))
    for (name, report), pair in zip(named, zip(rows[::2], rows[1::2], strict=True),
                                    strict=True):
        for search, row in zip(report["searches"], pair, strict=True):
            assert row["name"] == name and row["persistence"] == search["persistence"]
            assert row["zero"] == [_at(e, "0") for e in search["evaluations"]]
            assert row["one"] == [_at(e, "1") for e in search["evaluations"]]
            assert f"| {name}" in _table(section, search["persistence_label"])


# --------------------------------------------------------------------------- #
# the study on the annual path (D-275, D-276)
# --------------------------------------------------------------------------- #
ANNUEL_COMMIT = "9" * 40
ANNUEL_TITLE = "## Le chemin annuel : chaque année chiffrée"
#: The aged cost of each later year grows by this much a year; the frozen one stays.
GROW = 1.02


def _nearest(search: dict) -> dict:
    return next(e for e in search["evaluations"] if e["knobs"] == search["closest"]["knobs"])


def _annual(requests: Path, reports: Path, script, *, edit=None) -> None:
    """The four scenarios the launcher builds, and their reports, built by `annuel.build`
    on passes stubbed so that the first year is the study's nearest bundle — its costs and
    its impulse, as the study's stubbed pass gave them — and the aged cost then grows."""
    from impots.dette.scenarios import GrowthScenario
    from impots.predictif import annuel
    from impots.predictif.exploration import Priced
    from impots.uprating import caveat

    run = script.launcher()
    (requests / "annuel").mkdir()
    (reports / "etude_annuel").mkdir()
    for instrument in script.MENU:
        key = instrument.key
        scenario = run.scenario(key, reports)
        (requests / "annuel" / f"{run.name(key)}.json").write_text(
            json.dumps(scenario, ensure_ascii=False), encoding="utf-8")
        study = json.loads((reports / f"exploration_etude_{key}.json").read_text(
            encoding="utf-8"))
        request = ExplorationRequest.model_validate(study["request"])
        hyp = service.predictif_hypotheses(request)
        nearest = _nearest(study["searches"][0])

        def price(year, view, nearest=nearest):
            cost = nearest["cost_aged_eur" if view == "vieillie" else "cost_frozen_eur"]
            cost *= GROW ** (year - 2026) if view == "vieillie" else 1.0
            return Priced(cost=cost, inputs=None, impulse={"impot_sur_le_revenu": cost})

        years = list(range(2026, 2026 + request.horizon))
        uprating = annuel.uprating_for(
            GrowthScenario(request.growth.name, request.growth.real, request.growth.prices),
            wage=request.uprating.wage, source=request.uprating.source, base_year=2024)
        rapport = annuel.build(
            START, annuel.price_years(years, price, basis_for=lambda y: "legislated"),
            scenario=run.name(key), titre=instrument.label, source="test",
            reference="reconduit", computed="2026-10-28", spending=hyp.spending,
            growth=hyp.growth, rate=hyp.rate, theta=hyp.theta, uprating=uprating,
            uprating_note=caveat(years[-1], uprating),
            reform=ReformSpec.model_validate(scenario["reform"]),
            behavioural=request.behavioural, macro=request.macro,
            macro_store=synthetic_macro_store(), commit=ANNUEL_COMMIT, dirty=False,
            where=WHERE)
        payload = rapport.payload()
        if edit is not None:
            edit(key, payload)
        (reports / "etude_annuel" / f"predictif_{run.name(key)}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_the_annual_path_is_rendered_after_the_theta_section(script, tmp_path) -> None:
    """D-276: each instrument's nearest bundle, Δb at the horizon in both views under each
    persistence — the study's, the first year carried on the annual pass, every year
    priced, and their ratio — then each one's box; the commit and where they ran; the
    control, which the stubbed passes give back exactly; and the page before it."""
    requests, reports = _study(tmp_path, script)
    _annual(requests, reports, script)
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    page = script.render(etudes, complements, courbe, phase11)
    assert page.index(THETA_TITLE) < page.index(ANNUEL_TITLE) < page.index(NOT_SAID)
    section = page.partition(ANNUEL_TITLE)[2].partition(NOT_SAID)[0]
    assert ANNUEL_COMMIT in section and WHERE in section and "D-275" in section
    assert ("Ses coûts s'en écartent de 0 € au plus ; en vue vieillie, Δb à θ et à chaque "
            "coin, de 0,000000 point au plus ; en vue figée, Δb à θ, de 0,000000 point au "
            "plus.") in section
    for entry in etudes:
        instrument, report = entry["instrument"], entry["annuel"]["report"]
        drawn = {p["persistence"]: p["years"][-1] for p in report["side_by_side"]}
        for search in entry["report"]["searches"]:
            nearest = _nearest(search)
            every = drawn[search["persistence"]]["delta_aged"]
            row = (f"| {instrument.label} | {instrument.show(nearest['knobs'][instrument.knob])}"
                   f" | {search['persistence_label'][0].lower()}"
                   f"{search['persistence_label'][1:]} | {script._pt(nearest['delta_aged'])} "
                   f"| {script._pt(nearest['delta_aged'])} | {script._pt(every)} "
                   f"| {script._fr(every / nearest['delta_aged'], 3, sign=False)} |")
            assert row in section, row
        horizon = len(report["years"]) - 1
        aged = GROW ** horizon / (1.01 * 1.02) ** horizon
        frozen = 1 / (1.01 * 1.02) ** horizon
        assert (f"{script._fr(aged, 3, sign=False)} fois celle de 2026 en vue vieillie, et "
                f"{script._fr(frozen, 3, sign=False)} fois en vue figée") in section
        assert f"### {instrument.label}, chaque année chiffrée" in section
    # The page before the section is the page without it.
    (tmp_path / "avant").mkdir()
    before = script.render(*script.study(*_study(tmp_path / "avant", script)))
    head, _, tail = page.partition(ANNUEL_TITLE)
    assert before == head + NOT_SAID + tail.partition(NOT_SAID)[2]


@pytest.mark.parametrize("what, needle", [
    ("coût vieilli", "Ses coûts s'en écartent de 1234 € au plus ;"),
    ("coût figé", "Ses coûts s'en écartent de 1234 € au plus ;"),
    ("θ vieilli", "en vue vieillie, Δb à θ et à chaque coin, de 0,050000 point au plus ;"),
    ("θ figé", "en vue figée, Δb à θ, de 0,050000 point au plus."),
    ("coin", "en vue vieillie, Δb à θ et à chaque coin, de 0,050000 point au plus ;"),
])
def test_a_carry_that_does_not_give_the_study_back_is_said_with_its_gap(
        script, tmp_path, what: str, needle: str) -> None:
    """The control is said, not refused: a first year whose cost, Δb at θ in either view,
    or one corner is not the study's shows its gap, in euros or in points, each view apart
    — the frozen view of a reference priced before D-276 read its aged view's rates — and
    in the instrument's own section."""
    requests, reports = _study(tmp_path, script)

    def move(key, payload):
        if key != "decote":
            return
        carried = payload["theta_box"]["paths"][1]["first_year"]
        if what == "coût vieilli":
            payload["years"][0]["mechanical_aged_eur"] += 1234.0
        elif what == "coût figé":
            payload["years"][0]["mechanical_frozen_eur"] += 1234.0
        elif what == "θ vieilli":
            values = [v for _, v in carried["vieillie"]["corners"]]
            up = carried["vieillie"]["theta"] + 5e-4 <= max(values)
            carried["vieillie"]["theta"] += 5e-4 if up else -5e-4
        elif what == "θ figé":
            carried["figee"]["corners"] = [[label, v + 5e-4] for label, v
                                           in carried["figee"]["corners"]]
            carried["figee"]["theta"] += 5e-4
        else:
            label, value = carried["vieillie"]["corners"][0]
            carried["vieillie"]["corners"][0] = [label, value - 5e-4]
            low = min(v for _, v in carried["vieillie"]["corners"])
            carried["vieillie"]["theta"] = max(carried["vieillie"]["theta"], low)

    _annual(requests, reports, script, edit=move)
    etudes = script.study(requests, reports)[0]
    section = script.render(etudes).partition(ANNUEL_TITLE)[2]
    assert needle in section
    own = section.partition("### Le taux de la décote de l'IR")[2].partition("\n### ")[0]
    aged, frozen = (("0,050000", "0,000000") if what in ("θ vieilli", "coin")
                    else ("0,000000", "0,050000") if what == "θ figé"
                    else ("0,000000", "0,000000"))
    assert (f"s'écarte de sa référence de {aged} point au plus en vue vieillie, à θ et à "
            f"chaque coin, et de {frozen} point en vue figée, à θ.") in own


def test_each_instrument_s_box_is_read_off_its_report(script, tmp_path) -> None:
    """Built apart: under each persistence, the row of every year priced gives Δb at
    θ = 0, at θ and at θ = 1, the box's ends and the corners where the debt falls, from the
    report's own box; and the sentence says whether the debt falls at θ."""
    requests, reports = _study(tmp_path, script)
    _annual(requests, reports, script)
    etudes = script.study(requests, reports)[0]
    section = script.render(etudes).partition(ANNUEL_TITLE)[2]
    target = etudes[0]["report"]["hypotheses"]["target_share"]
    for entry in etudes:
        instrument, report = entry["instrument"], entry["annuel"]["report"]
        part = section.partition(f"### {instrument.label}, chaque année chiffrée")[2]
        part = part.partition("### ")[0]
        for search, path in zip(entry["report"]["searches"], report["theta_box"]["paths"],
                                strict=True):
            every = path["every_year"]["vieillie"]
            values = [v for _, v in every["corners"]]
            falls = sum(v <= target for v in values)
            row = (f"| Chaque année chiffrée | {script._pt(_at(every, '0'))} "
                   f"| {script._pt(every['theta'])} | {script._pt(_at(every, '1'))} "
                   f"| [{script._pt(min(values))} ; {script._pt(max(values))}] |")
            block = part.partition(f"**{search['persistence_label']}.**")[2]
            assert row in block, row
            said = "baisse en" if every["theta"] <= target else "ne baisse pas en"
            assert said in block.partition("\n")[0]
            said = f"elle baisse à {falls} des" if falls else "elle ne baisse à aucun des"
            assert f"{said} {len(values)} coins" in block.partition("\n")[0]


PREREGISTERED = "46c0a5ebef92bf6c49d1db122c686bf21e5f214c"


@pytest.mark.parametrize("commit, said", [(ANNUEL_COMMIT, True), (PREREGISTERED, False)])
def test_a_path_run_off_the_preregistration_commit_says_why(script, tmp_path, commit: str,
                                                            said: bool) -> None:
    """D-276: the passes of D-275's commit found a defect, and the four paths ran again on
    its fix. A page whose reports name another commit than the preregistration's says so,
    and why; one on the preregistration's commit has nothing to say."""
    requests, reports = _study(tmp_path, script)

    def name(key, payload):
        payload["commit"] = commit

    _annual(requests, reports, script, edit=name)
    section = script.render(script.study(requests, reports)[0]).partition(ANNUEL_TITLE)[2]
    sentence = ("Ce n'est pas le commit du préenregistrement, `46c0a5e` : ses passes ont "
                "trouvé un défaut, les deux vues partageant leurs taux marginaux, et le "
                "chemin a tourné de nouveau sur sa correction, sans rien changer d'autre "
                "(D-276).")
    assert (sentence in section) is said
    assert f"Ils ont tourné sur le commit `{commit}`" in section


ANNUEL_REFUSALS = [
    ("scenario retouché", "n'est pas le paquet de l'étude que le lanceur construit"),
    ("scenario de plus", "un paquet par instrument de l'étude, ni plus ni moins"),
    ("rapport manquant", "un rapport par scénario du chemin annuel"),
    ("autre scénario", "chiffre « autre »"),
    ("src modifié", "ne nomme pas un commit dont il a chiffré le code"),
    ("sans lieu", "ne dit pas où ses passes ont tourné"),
    ("deux commits", "sur un seul commit"),
    ("cadre", "n'a pas tourné dans le cadre de l'étude : ['spending_name']"),
    ("θ", "n'a pas tourné dans le cadre de l'étude : ['theta']"),
    ("vieillissement", "n'a pas tourné dans le cadre de l'étude : ['uprating_note']"),
    ("référence", "n'a pas tourné dans le cadre de l'étude : ['reference']"),
    ("croissance", "n'a pas tourné dans le cadre de l'étude : ['growth_name']"),
    ("taux", "n'a pas tourné dans le cadre de l'étude : ['rate_name']"),
    ("comportement", "n'a pas tourné dans le cadre de l'étude : ['behavioural']"),
    ("boucle", "n'a pas tourné dans le cadre de l'étude : ['macro']"),
    ("années", "n'a pas tourné dans le cadre de l'étude : ['years']"),
    ("persistances", "n'a pas tourné dans le cadre de l'étude : ['persistences']"),
    ("sans boîte", "sa boîte θ ne porte pas les lignes de la lecture de la page"),
    ("autres lignes", "sa boîte θ ne porte pas les lignes de la lecture de la page"),
]


@pytest.mark.parametrize("how, needle", ANNUEL_REFUSALS)
def test_an_annual_path_that_is_not_the_study_s_is_refused(script, tmp_path, how: str,
                                                           needle: str) -> None:
    """GUARD. A scenario touched or added, a report missing, of another scenario, of a
    modified `src/`, that does not say where it ran, of another commit, in another frame
    or without the study's box: each would read as the study priced every year."""
    requests, reports = _study(tmp_path, script)

    def edit(key, payload):
        if key != "ir":
            return
        if how == "autre scénario":
            payload["scenario"] = "autre"
        elif how == "src modifié":
            payload["dirty"] = True
        elif how == "sans lieu":
            payload["where"] = None
        elif how == "deux commits":
            payload["commit"] = "8" * 40
        elif how == "cadre":
            payload["spending_name"] = "Une autre dépense"
        elif how == "θ":
            payload["theta"] = {k: 0.4 for k in payload["theta"]}
        elif how == "vieillissement":
            payload["uprating_note"] += " (retouchée)"
        elif how == "sans boîte":
            payload["theta_box"] = None
        elif how == "référence":
            payload["reference"] = "indexe"
        elif how == "croissance":
            payload["growth_name"] = "Une autre croissance"
        elif how == "taux":
            payload["rate_name"] = "Un autre taux"
        elif how == "comportement":
            payload["behavioural"] = not payload["behavioural"]
        elif how == "boucle":
            payload["macro"] = not payload["macro"]
        elif how == "années":
            for row in payload["years"]:
                row["year"] += 1
            for path in payload["side_by_side"]:
                for row in path["years"]:
                    row["year"] += 1
            payload["theta_box"]["year"] += 1
        elif how == "persistances":
            payload["side_by_side"].reverse()
            payload["theta_box"]["paths"].reverse()
        elif how == "autres lignes":
            box = payload["theta_box"]
            box["rows"] = ["eti_all"]
            for path in box["paths"]:
                for reading in ("every_year", "first_year"):
                    for one in path[reading].values():
                        one["corners"] = [[label.replace("multiplicateur_macro", "eti_all"), v]
                                          for label, v in one["corners"]]

    _annual(requests, reports, script, edit=edit)
    run = script.launcher()
    if how == "scenario retouché":
        path = requests / "annuel" / f"{run.name('csg')}.json"
        scenario = json.loads(path.read_text(encoding="utf-8"))
        scenario["reform"] = {"csg_activite_deductible": 0.061}
        path.write_text(json.dumps(scenario), encoding="utf-8")
    elif how == "scenario de plus":
        (requests / "annuel" / "etude_annuel_pfu.json").write_text("{}", encoding="utf-8")
    elif how == "rapport manquant":
        (reports / "etude_annuel" / f"predictif_{run.name('ir')}.json").unlink()
    with pytest.raises(script.EtudeError, match=re.escape(needle)):
        script.study(requests, reports)


def test_the_reference_is_the_complement_where_the_page_has_one(script, tmp_path) -> None:
    """D-239 replayed the ceiling under another macro classing, and the page reads it off
    that complement: the annual path is compared to the complement there, named with its
    commit, and to the study elsewhere."""
    requests, reports = _study(tmp_path, script)
    path = _complement(requests, reports, script)
    complement = json.loads(path.read_text(encoding="utf-8"))
    for search in complement["searches"]:
        if search.get("indices"):
            search["indices"]["delta_aged"] *= 0.9
        for e in [*search["evaluations"], search["closest"]]:
            for field in ("delta_aged", "delta_frozen"):
                e[field] *= 0.9
            if "corners" in e:
                e["corners"] = [[label, v * 0.9] for label, v in e["corners"]]
                values = [v for _, v in e["corners"]]
                e.update(corner_low=min(values), corner_high=max(values))
    path.write_text(json.dumps(complement, ensure_ascii=False), encoding="utf-8")
    _annual(requests, reports, script)
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    section = script.render(etudes, complements, courbe, phase11).partition(
        ANNUEL_TITLE)[2]
    assert "son complément, au commit `bbbbbbb`, pour le plafond" in section
    assert f"l'étude, au commit `{COMMIT[:7]}`, pour la CSG" in section
    entry = next(e for e in etudes if e["instrument"].key == "allegements")
    nearest = _nearest(entry["report"]["searches"][0])
    row = (f"| {entry['instrument'].label} "
           f"| {entry['instrument'].show(nearest['knobs'][entry['instrument'].knob])} "
           f"| {entry['report']['searches'][0]['persistence_label'][0].lower()}")
    line = next(x for x in section.splitlines() if x.startswith(row))
    assert f"| {script._pt(0.9 * nearest['delta_aged'])} |" in line
    ceiling = section.partition("### Le plafond de la réduction générale")[2].partition(
        "\n### ")[0]
    assert "| La référence (`bbbbbbb`), reportée |" in ceiling
    assert f"`{COMMIT[:7]}`" not in ceiling
    aged = max([0.1 * abs(_nearest(s)["delta_aged"]) for s in entry["report"]["searches"]]
               + [0.1 * abs(v) for s in entry["report"]["searches"]
                  for _, v in _nearest(s)["corners"]])
    frozen = max(0.1 * abs(_nearest(s)["delta_frozen"]) for s in entry["report"]["searches"])
    assert (f"en vue vieillie, Δb à θ et à chaque coin, de "
            f"{script._fr(aged * 100, 6, sign=False)} point au plus ; en vue figée, Δb à θ, "
            f"de {script._fr(frozen * 100, 6, sign=False)} point au plus.") in section


@pytest.mark.parametrize("shift, said, readings", [
    (0.0, "0,000000", ("every_year", "first_year")),
    (1e-4, "0,010000", ("every_year",)),
    (1e-4, "0,010000", ("first_year",)),
])
def test_a_row_the_reference_did_not_have_is_named_with_what_it_moves(
        script, tmp_path, shift: float, said: str, readings: tuple[str, ...]) -> None:
    """C11 claims the ceiling's knob since D-263, and the study's box did not have it: the
    annual box may carry a row its reference lacks, named, with how far Δb moves at its
    corners in either reading; a reference row it lacks is refused (above). The control
    reads each carried corner at the reference's corner that sets its rows alike, so a
    corner the row moves is a gap to the reference."""
    requests, reports = _study(tmp_path, script)
    extra = "autofinancement_poids_tresor_eco"

    def add_row(key, payload):
        if key != "allegements":
            return
        box = payload["theta_box"]
        box["rows"] = [extra, *box["rows"]]
        for path in box["paths"]:
            for reading in ("every_year", "first_year"):
                moved = shift if reading in readings else 0.0
                for one in path[reading].values():
                    one["corners"] = [[f"{extra} = {w}, {label}", v + (moved if w else 0.0)]
                                      for w in (0, 1) for label, v in one["corners"]]

    _annual(requests, reports, script, edit=add_row)
    etudes = script.study(requests, reports)[0]
    section = script.render(etudes).partition(ANNUEL_TITLE)[2]
    part = section.partition("### Le plafond de la réduction générale")[2]
    assert (f"Sa boîte porte aussi `{extra}`, que la référence n'avait pas : à leurs coins, "
            f"Δb ne bouge pas de plus de {said} point.") in part
    assert "Sa boîte porte aussi" not in section.partition("### Le plafond")[0]
    control = "0,010000" if shift and "first_year" in readings else "0,000000"
    assert f"en vue vieillie, Δb à θ et à chaque coin, de {control} point au plus" in section


# --------------------------------------------------------------------------- #
# the frozen view, priced again on D-276's fix (D-278, D-279)
# --------------------------------------------------------------------------- #
VUE_FIGEE_COMMIT = "8" * 40
VUE_FIGEE_TITLE = "## La vue figée, rechiffrée"
RATE_ROW = "eti_all"
READS_RATES = ("csg", "decote", "ir")


def _pointer(etudes: list[dict]) -> str:
    year = etudes[0]["report"]["hypotheses"]["target_year"]
    return (f"La colonne « Δb {year}, figée » lisait les taux marginaux de la vue vieillie "
            f"(D-276) : elle est rechiffrée plus bas, dans « La vue figée, rechiffrée ».")


def _figures(search: dict) -> list[dict]:
    """Every bundle a search writes down: its evaluations, its candidates, its closest."""
    return [*search["evaluations"], *search["candidates"],
            *([search["closest"]] if search.get("closest") else [])]


def _with_rate_row(reports: Path, keys: tuple[str, ...] = READS_RATES) -> None:
    """The stubbed study's boxes carry the multiplier alone: give those of `keys` a row of
    C1 that moves nothing, so that they read the marginal rates as the study's do."""
    for key in keys:
        path = reports / f"exploration_etude_{key}.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        for search in report["searches"]:
            for figure in _figures(search):
                if figure.get("corners"):
                    figure["corners"] = [[f"{RATE_ROW} = {w}, {label}", value]
                                         for w in (0, 1) for label, value in figure["corners"]]
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")


def _vue_figee(reports: Path, *, shift: float = -1e-3, edit=None) -> None:
    """The replays of D-278: each study report whose box reads the marginal rates, as the
    explorer writes it again on the fix: the aged view the same, the frozen one moved."""
    out = reports / "vue_figee"
    out.mkdir()
    for key in READS_RATES:
        report = json.loads((reports / f"exploration_etude_{key}.json").read_text(
            encoding="utf-8"))
        report.update(commit=VUE_FIGEE_COMMIT, computed="2026-10-28", where=WHERE)
        for search in report["searches"]:
            for figure in _figures(search):
                figure["delta_frozen"] += shift
        if edit is not None:
            edit(key, report)
        (out / f"exploration_etude_{key}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")


def _replayed(tmp_path: Path, script, **kwargs) -> tuple[str, list[dict]]:
    requests, reports = _study(tmp_path, script)
    _with_rate_row(reports)
    _vue_figee(reports, **kwargs)
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    return script.render(etudes, complements, courbe, phase11), etudes


def test_the_replayed_frozen_view_is_rendered_bundle_by_bundle(script, tmp_path) -> None:
    """D-278: after the θ section, each bundle of each study exploration whose box reads
    the marginal rates, its frozen Δb in the study and replayed, and the gap; the commit and
    where the replays ran; the aged control, which they give back exactly. The page before
    is the page without the replays, but for the pointers."""
    page, etudes = _replayed(tmp_path, script)
    assert page.index(THETA_TITLE) < page.index(VUE_FIGEE_TITLE) < page.index(NOT_SAID)
    section = page.partition(VUE_FIGEE_TITLE)[2].partition(NOT_SAID)[0]
    assert VUE_FIGEE_COMMIT in section and WHERE in section and "D-278" in section
    labels = [e["instrument"].label for e in etudes if e["instrument"].key in READS_RATES]
    assert (f"pour {script._lower(labels[0])}, {script._lower(labels[1])} et "
            f"{script._lower(labels[2])}, ont été rejouées") in section
    assert ("Ses coûts s'en écartent de 0 € au plus, dans les deux vues, et Δb à θ et à "
            "chaque coin, en vue vieillie, de 0,000000 point au plus.") in section
    for entry in etudes:
        instrument = entry["instrument"]
        for search in entry["report"]["searches"]:
            for e in search["evaluations"]:
                row = (f"| {instrument.label} | {instrument.show(e['knobs'][instrument.knob])} "
                       f"| {script._lower(search['persistence_label'])} "
                       f"| {script._pt(e['delta_frozen'])} "
                       f"| {script._pt(e['delta_frozen'] - 1e-3)} | −0,1000 pt |")
                assert (row in section) is (instrument.key in READS_RATES), row
    (tmp_path / "avant").mkdir()
    requests, reports = _study(tmp_path / "avant", script)
    _with_rate_row(reports)
    before = script.render(*script.study(requests, reports))
    head, _, tail = page.partition(VUE_FIGEE_TITLE)
    assert before == (head + NOT_SAID + tail.partition(NOT_SAID)[2]).replace(
        "\n\n" + _pointer(etudes), "")


def test_each_instrument_whose_frozen_view_was_replayed_points_to_it(script, tmp_path) -> None:
    """Above, the study's tables keep their figures; each instrument replayed says that its
    frozen column read the aged view's rates, and where it is priced again; the others do
    not, and nothing says so without the replays."""
    page, etudes = _replayed(tmp_path, script)
    for entry in etudes:
        label = entry["instrument"].label
        own = page.partition(f"\n### {label}\n")[2].partition("\n### ")[0]
        assert own and (_pointer(etudes) in own) is (
            entry["instrument"].key in READS_RATES), label
    (tmp_path / "avant").mkdir()
    requests, reports = _study(tmp_path / "avant", script)
    _with_rate_row(reports)
    assert "La colonne « Δb" not in script.render(*script.study(requests, reports))


@pytest.mark.parametrize("what, needle", [
    ("coût vieilli", "Ses coûts s'en écartent de 1234 € au plus"),
    ("coût figé", "Ses coûts s'en écartent de 1234 € au plus"),
    ("θ vieilli", "en vue vieillie, de 0,050000 point au plus"),
    ("coin", "en vue vieillie, de 0,050000 point au plus"),
])
def test_a_replay_that_does_not_give_the_aged_view_back_is_said_with_its_gap(
        script, tmp_path, what: str, needle: str) -> None:
    """The aged view did not read the defect: the replay must give it back. It is a
    result, said with its gap rather than refused."""

    def move(key, report):
        if key != "decote":
            return
        evaluation = report["searches"][1]["evaluations"][2]
        if what == "coût vieilli":
            evaluation["cost_aged_eur"] += 1234.0
        elif what == "coût figé":
            evaluation["cost_frozen_eur"] += 1234.0
        elif what == "θ vieilli":
            evaluation["delta_aged"] += 5e-4
        else:
            label, value = evaluation["corners"][0]
            evaluation["corners"][0] = [label, value - 5e-4]

    page, _ = _replayed(tmp_path, script, edit=move)
    assert needle in page.partition(VUE_FIGEE_TITLE)[2]


VUE_FIGEE_REFUSALS = [
    ("rapport de plus", "un rapport par exploration de l'étude dont la boîte lit les taux"),
    ("rapport manquant", "un rapport par exploration de l'étude dont la boîte lit les taux"),
    ("requête", "n'a pas rejoué la requête de l'étude"),
    ("sans commit", "ne nomme pas le commit qui l'a chiffré"),
    ("sans lieu", "ne dit pas où ses passes ont tourné"),
    ("commit de l'étude", "a tourné sur le commit de l'étude"),
    ("paquet", "ne chiffre pas les paquets de l'étude"),
    ("persistances", "ne chiffre pas les paquets de l'étude"),
    ("deux commits", "sur un seul commit"),
    ("coins", "sa boîte ne porte pas les coins de l'étude"),
]


@pytest.mark.parametrize("how, needle", VUE_FIGEE_REFUSALS)
def test_a_replay_that_is_not_the_study_s_exploration_is_refused(script, tmp_path, how: str,
                                                                needle: str) -> None:
    requests, reports = _study(tmp_path, script)
    _with_rate_row(reports)

    def edit(key, report):
        if key != "ir":
            return
        if how == "requête":
            report["request"]["bounds"][0]["low"] += report["request"]["bounds"][0]["step"]
        elif how == "sans commit":
            report["commit"] = ""
        elif how == "sans lieu":
            report["where"] = "  "
        elif how == "commit de l'étude":
            report["commit"] = COMMIT
        elif how == "paquet":
            first = report["searches"][0]["evaluations"][0]
            first["knobs"] = {k: v + 0.001 for k, v in first["knobs"].items()}
        elif how == "persistances":
            report["searches"].reverse()
        elif how == "deux commits":
            report["commit"] = "7" * 40
        elif how == "coins":
            evaluation = report["searches"][0]["evaluations"][0]
            evaluation["corners"] = [[label.replace(RATE_ROW, "eti_top_decile"), value]
                                     for label, value in evaluation["corners"]]

    _vue_figee(reports, edit=edit)
    out = reports / "vue_figee"
    if how == "rapport de plus":
        (out / "exploration_etude_allegements.json").write_text(
            (reports / "exploration_etude_allegements.json").read_text(encoding="utf-8"),
            encoding="utf-8")
    elif how == "rapport manquant":
        (out / "exploration_etude_ir.json").unlink()
    with pytest.raises(script.EtudeError, match=re.escape(needle)):
        script.study(requests, reports)


@pytest.mark.parametrize("shift, aged_too", [(-1e-3, False), (-1.0, False), (-1.0, True)])
def test_the_bundles_the_frozen_view_alone_would_hold_are_counted(script, tmp_path,
                                                                  shift: float,
                                                                  aged_too: bool) -> None:
    """The frozen view enters no verdict of the target; it says only whether a bundle
    would hold the target in the frozen view alone, under each persistence: a reading
    the aged view holds too is not one. Counted on the replay, and in the study, read
    apart off the files."""

    def hold(key, report):
        if aged_too and key == "decote":
            report["searches"][0]["evaluations"][0]["delta_aged"] = -1.0

    page, etudes = _replayed(tmp_path, script, shift=shift, edit=hold)
    target = etudes[0]["report"]["hypotheses"]["target_share"]

    def count(directory: Path) -> tuple[str, int]:
        readings = [e for key in READS_RATES
                    for search in json.loads((directory / f"exploration_etude_{key}.json")
                                             .read_text(encoding="utf-8"))["searches"]
                    for e in search["evaluations"]]
        n = sum(e["delta_aged"] > target and e["delta_frozen"] <= target for e in readings)
        return (str(n) if n else "aucune"), len(readings)

    reports = tmp_path / "reports"
    (replayed, readings), (studied, _) = count(reports / "vue_figee"), count(reports)
    assert readings and (replayed != studied or shift > -0.5)
    section = page.partition(VUE_FIGEE_TITLE)[2].partition(NOT_SAID)[0]
    holds = "tiendrait" if replayed != "aucune" else "ne tiendrait"
    assert (f"Rechiffrée, la vue figée seule {holds} la cible à {replayed} des "
            f"{readings} lectures d'un paquet sous une persistance ; dans l'étude, à "
            f"{studied}.") in section


@pytest.mark.parametrize("gap, said", [(-1e-3, "−0,1000 pt"), (-4e-7, "0,0000 pt"),
                                       (4e-7, "0,0000 pt"), (6e-7, "+0,0001 pt")])
def test_a_gap_is_written_to_the_ten_thousandth_without_a_signed_zero(script, gap: float,
                                                                      said: str) -> None:
    """A gap the rounding takes to zero is zero, not « −0,0000 »."""
    assert script._gap(gap) == said


def test_the_nearest_bundle_s_replay_is_the_annual_path_s_carry(script, tmp_path) -> None:
    """Where the annual path is on the page, its first year carried in the frozen view is
    the nearest bundle's frozen Δb, priced on the same fix: said, with its gap."""
    requests, reports = _study(tmp_path, script)
    _with_rate_row(reports)
    # The nearest bundle is not the grid's first, so that reading the first would show.
    for key in READS_RATES:
        path = reports / f"exploration_etude_{key}.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        for search in report["searches"]:
            search["evaluations"].reverse()
            assert search["evaluations"][0]["knobs"] != search["closest"]["knobs"]
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

    def add_row(key, payload):
        if key not in READS_RATES:
            return
        box = payload["theta_box"]
        box["rows"] = [RATE_ROW, *box["rows"]]
        for path in box["paths"]:
            for reading in ("every_year", "first_year"):
                for one in path[reading].values():
                    one["corners"] = [[f"{RATE_ROW} = {w}, {label}", v]
                                      for w in (0, 1) for label, v in one["corners"]]

    _annual(requests, reports, script, edit=add_row)
    carried = {}
    for key in READS_RATES:
        report = json.loads((reports / "etude_annuel" / f"predictif_etude_annuel_{key}.json")
                            .read_text(encoding="utf-8"))
        carried[key] = [p["first_year"]["figee"]["theta"] for p in report["theta_box"]["paths"]]

    def match(key, report):
        for search, value in zip(report["searches"], carried[key], strict=True):
            for figure in _figures(search):
                if figure["knobs"] == search["closest"]["knobs"]:
                    figure["delta_frozen"] = value + (2e-4 if key == "ir" else 0.0)

    _vue_figee(reports, edit=match)
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    section = script.render(etudes, complements, courbe, phase11).partition(
        VUE_FIGEE_TITLE)[2].partition(NOT_SAID)[0]
    assert ("Pour le paquet le plus proche, la vue figée rechiffrée est celle que le chemin "
            "annuel reporte sur sa passe de 2026, à 0,020000 point près.") in section


# --------------------------------------------------------------------------- #
# C1 on four samples of the marginal rates (D-284, D-285)
# --------------------------------------------------------------------------- #
C1_QUATRE_COMMIT = "9" * 40
C1_QUATRE_TITLE = "## C1 sur quatre échantillons"
C1_READS = ("decote", "ir")
C1_POINTER = ("C1, la réponse du revenu imposable, est lu ici sur un seul échantillon des "
              "taux marginaux, dont le bruit va jusqu'à 0,09 point (D-283) : ces paquets "
              "sont rechiffrés sur quatre plus bas, dans « C1 sur quatre échantillons ».")


def _c1_annual(requests: Path, reports: Path, script) -> None:
    """D-277's annual paths, their boxes carrying the C1 row the study's do."""

    def add_row(key, payload):
        if key not in C1_READS:
            return
        box = payload["theta_box"]
        box["rows"] = [RATE_ROW, *box["rows"]]
        for path in box["paths"]:
            for reading in ("every_year", "first_year"):
                for one in path[reading].values():
                    one["corners"] = [[f"{RATE_ROW} = {w}, {label}", v]
                                      for w in (0, 1) for label, v in one["corners"]]

    _annual(requests, reports, script, edit=add_row)


#: C1 on the study's sample in D-283's stub, in points of Δb.
BASE = 0.05


def _bruit(reports: Path, *, shift: float, off: float = 0.0) -> None:
    """D-283's replications, as far as the page reads them: C1 on the study's sample at
    `BASE`, and on the three others so that their mean moves Δb by `shift` (+ `off`). Not
    at nought: a prediction that forgot to take the first sample off would read the same."""
    from impots.behavioural.emtr import C1_SAMPLES
    from impots.population.runner import SAMPLE_SEED

    out = reports / "bruit_c1"
    out.mkdir()
    for view in ("vieillie", "figee"):
        for seed in C1_SAMPLES:
            bundles = []
            for key in C1_READS:
                report = json.loads((reports / f"exploration_etude_{key}.json").read_text(
                    encoding="utf-8"))
                for e in report["searches"][0]["evaluations"]:
                    points = BASE + (0.0 if seed == SAMPLE_SEED
                                     else (shift + off) * 100 * len(C1_SAMPLES) / 3)
                    bundles.append({"instrument": key, "knobs": e["knobs"],
                                    "c1_points": points})
            (out / f"c1_{view}_{seed}_100.json").write_text(
                json.dumps({"bundles": bundles}), encoding="utf-8")


def _c1_quatre(reports: Path, script, *, shift: float = -1e-3, edit=None) -> None:
    """The replays of D-285: the study's explorations and annual paths that C1 prices, as
    the commands write them again on four samples: every Δb moved by `shift`."""
    out = reports / "c1_quatre"
    out.mkdir()
    run = script.launcher()
    for key in C1_READS:
        report = json.loads((reports / f"exploration_etude_{key}.json").read_text(
            encoding="utf-8"))
        report.update(commit=C1_QUATRE_COMMIT, computed="2026-10-29", where=WHERE)
        for search in report["searches"]:
            for figure in _figures(search):
                figure["delta_aged"] += shift
                figure["delta_frozen"] += shift
        if edit is not None:
            edit(key, "exploration", report)
        (out / f"exploration_etude_{key}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")
        annual = json.loads((reports / "etude_annuel" / f"predictif_{run.name(key)}.json")
                            .read_text(encoding="utf-8"))
        annual.update(commit=C1_QUATRE_COMMIT, where=WHERE)
        for path in annual["side_by_side"]:
            for year in path["years"]:
                for field in ("delta_aged", "delta_frozen", "reform_aged", "reform_frozen"):
                    if year.get(field) is not None:
                        year[field] += shift
        for path in annual["theta_box"]["paths"]:
            for reading in ("every_year", "first_year"):
                for one in path[reading].values():
                    one["theta"] += shift
                    one["corners"] = [[label, v + shift] for label, v in one["corners"]]
        if edit is not None:
            edit(key, "annual", annual)
        (out / f"predictif_{run.name(key)}.json").write_text(
            json.dumps(annual, ensure_ascii=False), encoding="utf-8")


def _quatre(tmp_path: Path, script, *, bruit: float | None = -1e-3, **kwargs):
    requests, reports = _study(tmp_path, script)
    _with_rate_row(reports, keys=C1_READS)
    _c1_annual(requests, reports, script)
    if bruit is not None:
        _bruit(reports, shift=bruit)
    _c1_quatre(reports, script, **kwargs)
    etudes, complements, courbe, phase11 = script.study(requests, reports)
    return script.render(etudes, complements, courbe, phase11), etudes, (requests, reports)


def test_the_c1_replay_is_rendered_bundle_by_bundle(script, tmp_path) -> None:
    """D-285: after the annual path, each bundle of each study exploration whose box
    carries a C1 row, its Δb on one sample and on four, in both views, and the gap; each
    annual path the same; the commit and where they ran; the control, costs untouched and
    each gap the one D-283's replications predict. The page before is the page without
    the replays, but for the pointers."""
    page, etudes, _ = _quatre(tmp_path, script)
    assert page.index(ANNUEL_TITLE) < page.index(C1_QUATRE_TITLE) < page.index(NOT_SAID)
    section = page.partition(C1_QUATRE_TITLE)[2].partition(NOT_SAID)[0]
    assert C1_QUATRE_COMMIT in section and WHERE in section and "D-285" in section
    assert ("Les coûts des paquets s'écartent de ceux de l'étude de 0 € au plus, dans les "
            "deux vues, et ceux des chemins annuels de 0 € au plus. À θ, l'écart de chaque "
            "paquet est celui que prévoient les réplications de D-283, la moyenne de leurs "
            "quatre premiers échantillons moins le premier, à 0,000000 point près.") in section
    assert "**Les verdicts.** Aucun ne change" in section
    for entry in etudes:
        instrument = entry["instrument"]
        for search in entry["report"]["searches"]:
            for e in search["evaluations"]:
                shown = instrument.show(e["knobs"][instrument.knob])
                persistence = script._lower(search["persistence_label"])
                rows = [f"| {instrument.label} | {shown} | {persistence} | vieillie "
                        f"| {script._pt(e['delta_aged'])} "
                        f"| {script._pt(e['delta_aged'] - 1e-3)} | −0,1000 pt |",
                        f"| {instrument.label} | {shown} | {persistence} | figée (l'étude) "
                        f"| {script._pt(e['delta_frozen'])} "
                        f"| {script._pt(e['delta_frozen'] - 1e-3)} | −0,1000 pt |"]
                for row in rows:
                    assert (row in section) is (instrument.key in C1_READS), row
        if instrument.key in C1_READS:
            annual = entry["annuel"]["report"]
            for path in annual["theta_box"]["paths"]:
                before = path["every_year"]["vieillie"]["theta"]
                label = next(s["persistence_label"] for s in entry["report"]["searches"]
                             if s["persistence"] == path["persistence"])
                assert (f"| {instrument.label} | {script._lower(label)} | vieillie "
                        f"| {script._pt(before)} | {script._pt(before - 1e-3)} "
                        f"| −0,1000 pt |") in section
    (tmp_path / "avant").mkdir()
    requests, reports = _study(tmp_path / "avant", script)
    _with_rate_row(reports, keys=C1_READS)
    _c1_annual(requests, reports, script)
    before = script.render(*script.study(requests, reports))
    head, _, tail = page.partition(C1_QUATRE_TITLE)
    assert before == (head + NOT_SAID + tail.partition(NOT_SAID)[2]).replace(
        "\n\n" + C1_POINTER, "")


def test_each_instrument_c1_prices_points_to_its_replay(script, tmp_path) -> None:
    page, etudes, _ = _quatre(tmp_path, script)
    for entry in etudes:
        label = entry["instrument"].label
        own = page.partition(f"\n### {label}\n")[2].partition("\n### ")[0]
        assert own and (C1_POINTER in own) is (entry["instrument"].key in C1_READS), label


def test_without_d283_s_replications_the_prediction_is_not_said(script, tmp_path) -> None:
    page, _, _ = _quatre(tmp_path, script, bruit=None)
    section = page.partition(C1_QUATRE_TITLE)[2].partition(NOT_SAID)[0]
    assert "chemins annuels de 0 € au plus." in section
    assert "réplications de D-283" not in section


@pytest.mark.parametrize("what, needle", [
    ("coût", "s'écartent de ceux de l'étude de 1234 € au plus"),
    ("coût annuel", "et ceux des chemins annuels de 1234 € au plus"),
    ("écart", "moins le premier, à 0,050000 point près"),
])
def test_a_replay_c1_alone_does_not_explain_is_said_with_its_gap(script, tmp_path,
                                                                 what: str, needle: str) -> None:
    """Only C1 changes: the costs must be the study's, and each gap the one D-283
    predicts. It is a result, said with its gap rather than refused."""

    def move(key, kind, report):
        if key != "decote":
            return
        if kind == "exploration" and what == "coût":
            report["searches"][1]["evaluations"][2]["cost_frozen_eur"] += 1234.0
        if kind == "exploration" and what == "écart":
            report["searches"][0]["evaluations"][1]["delta_aged"] += 5e-4
        if kind == "annual" and what == "coût annuel":
            report["years"][3]["mechanical_aged_eur"] += 1234.0

    page, _, _ = _quatre(tmp_path, script, edit=move)
    assert needle in page.partition(C1_QUATRE_TITLE)[2]


def test_the_frozen_view_reads_against_its_last_corrected_reading(script, tmp_path) -> None:
    """Where D-279 priced the frozen view again on its own rates, the replay's frozen
    view is read against it, not against the study's, which read the aged view's rates."""
    requests, reports = _study(tmp_path, script)
    _with_rate_row(reports, keys=C1_READS)
    _c1_annual(requests, reports, script)
    out = reports / "vue_figee"
    out.mkdir()
    for key in C1_READS:
        report = json.loads((reports / f"exploration_etude_{key}.json").read_text(
            encoding="utf-8"))
        report.update(commit=VUE_FIGEE_COMMIT, computed="2026-10-28", where=WHERE)
        for search in report["searches"]:
            for figure in _figures(search):
                figure["delta_frozen"] += 2e-3
        (out / f"exploration_etude_{key}.json").write_text(
            json.dumps(report, ensure_ascii=False), encoding="utf-8")
    # The prediction holds in the aged view: only a frozen gap read against D-279, not
    # against the study, leaves 0,2 point between it and the replay.
    _bruit(reports, shift=-1e-3)
    _c1_quatre(reports, script)
    etudes = script.study(requests, reports)[0]
    section = script.render(etudes).partition(C1_QUATRE_TITLE)[2]
    entry = next(e for e in etudes if e["instrument"].key == "ir")
    e = entry["report"]["searches"][0]["evaluations"][0]
    instrument = entry["instrument"]
    assert (f"| {instrument.label} | {instrument.show(e['knobs'][instrument.knob])} "
            f"| {script._lower(entry['report']['searches'][0]['persistence_label'])} "
            f"| figée (D-279) | {script._pt(e['delta_frozen'] + 2e-3)} "
            f"| {script._pt(e['delta_frozen'] - 1e-3)} | −0,3000 pt |") in section
    assert "moins le premier, à 0,200000 point près" in section


def test_a_verdict_that_changes_is_named(script, tmp_path) -> None:
    def hold(key, kind, report):
        if key == "ir" and kind == "exploration":
            for search in report["searches"]:
                for evaluation in search["evaluations"]:
                    evaluation["corners"] = [[label, -1.0]
                                             for label, _ in evaluation["corners"]]

    page, etudes, _ = _quatre(tmp_path, script, edit=hold)
    label = next(e["instrument"].label for e in etudes if e["instrument"].key == "ir")
    assert (f"**Les verdicts.** Ils changent pour {script._lower(label)} :"
            in page.partition(C1_QUATRE_TITLE)[2])


C1_QUATRE_REFUSALS = [
    ("rapport de plus", "une exploration et un chemin annuel par instrument"),
    ("rapport manquant", "une exploration et un chemin annuel par instrument"),
    ("requête", "n'a pas rejoué la requête de l'étude"),
    ("sans commit", "ne nomme pas un commit dont il a chiffré le code"),
    ("modifié", "ne nomme pas un commit dont il a chiffré le code"),
    ("sans lieu", "ne dit pas où ses passes ont tourné"),
    ("commit de l'étude", "a tourné sur le commit de l'étude"),
    ("paquet", "ne chiffre pas les paquets de l'étude"),
    ("coins", "sa boîte ne porte pas les coins de l'étude"),
    ("scénario", "le chemin annuel de ir chiffre"),
    ("cadre", "n'a pas tourné dans le cadre de l'étude"),
    ("deux commits", "sur un seul commit"),
]


@pytest.mark.parametrize("how, needle", C1_QUATRE_REFUSALS)
def test_a_c1_replay_that_is_not_the_study_s_report_is_refused(script, tmp_path, how: str,
                                                              needle: str) -> None:
    requests, reports = _study(tmp_path, script)
    _with_rate_row(reports, keys=C1_READS)
    _c1_annual(requests, reports, script)

    def edit(key, kind, report):
        if key != "ir":
            return
        if kind == "exploration":
            if how == "requête":
                report["request"]["bounds"][0]["low"] += report["request"]["bounds"][0]["step"]
            elif how == "sans commit":
                report["commit"] = ""
            elif how == "sans lieu":
                report["where"] = "  "
            elif how == "commit de l'étude":
                report["commit"] = COMMIT
            elif how == "paquet":
                first = report["searches"][0]["evaluations"][0]
                first["knobs"] = {k: v + 0.001 for k, v in first["knobs"].items()}
            elif how == "coins":
                evaluation = report["searches"][0]["evaluations"][0]
                evaluation["corners"] = [[label.replace(RATE_ROW, "eti_top_decile"), v]
                                         for label, v in evaluation["corners"]]
        elif how == "modifié":
            report["dirty"] = True
        elif how == "scénario":
            report["scenario"] = "autre"
        elif how == "cadre":
            report["growth_name"] = "Une autre croissance"
        elif how == "deux commits":
            report["commit"] = "7" * 40

    _c1_quatre(reports, script, edit=edit)
    out = reports / "c1_quatre"
    if how == "rapport de plus":
        (out / "exploration_etude_csg.json").write_text(
            (reports / "exploration_etude_csg.json").read_text(encoding="utf-8"),
            encoding="utf-8")
    elif how == "rapport manquant":
        (out / f"predictif_{script.launcher().name('ir')}.json").unlink()
    with pytest.raises(script.EtudeError, match=re.escape(needle)):
        script.study(requests, reports)
