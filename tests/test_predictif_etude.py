"""PHASE10_SPEC §5 — l'étude préenregistrée, et sa page qui ne doit pas dériver (D-237, D-238).

La garde de D-228, appliquée à l'étude : la page commitée est le rendu des fichiers
commités. Et celles du préenregistrement : chaque rapport a joué la requête commitée sous
`etude/`, à l'identique ; chaque instrument du menu a sa requête et son rapport ; tous
viennent d'un même commit, et disent où leurs passes ont tourné. Sur une étude construite,
sans données : ces refus, la réponse par instrument et par persistance, et les coins qui
font baisser la dette. La courbe de 2026, rejouée à part (D-241, D-242), a les siens.
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
                           hypotheses=main._predictif_hypotheses(request), start=START,
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
                               hypotheses=main._predictif_hypotheses(request), start=START,
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
                               hypotheses=main._predictif_hypotheses(request), start=START,
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
    section, _, rest = tail.partition("## Ce que l'étude ne dit pas")
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
    # The page before the section is the page without it.
    (tmp_path / "avant").mkdir()
    before = script.render(*script.study(*_with_autofinancement(
        tmp_path / "avant", script, "t_delta", "t_min")))
    assert before == head + "## Ce que l'étude ne dit pas" + rest


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
