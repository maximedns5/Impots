"""La commande des études (but 6, D-301) : une définition, ses passes, sa page.

Chaque définition de `etudes/` est soit préenregistrée et pas lancée (ni rapports ni page),
soit lancée et rendue (ses rapports, et une page qui est exactement leur rendu) : une page
modifiée est refusée, une page sans ses rapports aussi. L'étude du PLFSS 2027 lit les deux
volets de l'art. 74 du PLF en miroir (D-298) : chaque réponse changée de signe, gagnants et
perdants échangés, et les 49 articles du PLFSS avec leur porte. Les rapports de ces tests
sont factices, construits comme ceux de `test_etude_page_plf2027.py`.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from impots import etude, fiche, plf_coverage, preregistration
from impots.population import cli
from impots.predictif import retroaction
from test_etude_page_plf2027 import COMMIT, TEMPLATE, _fan, _households

COSTS = {"plf2027_art_74_ppa": 4.0e8, "plf2027_art_74_apl": 1.2e8}


# --- every page, against its reports ------------------------------------------------


@pytest.mark.parametrize("nom", [s.nom for s in etude.definitions()])
def test_every_study_is_unrun_or_rendered_exactly(nom: str) -> None:
    """The anti-drift guard of every study: no number of a page is typed by hand."""
    assert etude.definition(nom).drift() is None


def test_the_plf_study_is_the_command_s() -> None:
    study = etude.definition("plf2027")
    # In docs/etudes/ with every study since D-304, where the site reads them.
    assert study.page == etude.ROOT / "docs" / "etudes" / "plf2027.md"
    assert study.page.read_text(encoding="utf-8").splitlines()[2] == (
        "<!-- Généré par `impots etude ecrire plf2027` depuis reports/etude_plf2027/ ; ne "
        "pas éditer à la main. -->")


def _copy(study: etude.Etude, tmp_path: Path, change) -> etude.Etude:
    page = tmp_path / "page.md"
    page.write_text(change(study.page.read_text(encoding="utf-8")), encoding="utf-8")
    return etude.replace(study, page=page)


def test_a_modified_page_is_refused(tmp_path) -> None:
    study = etude.definition("plf2027")
    one = _copy(study, tmp_path, lambda text: text.replace("Md€", "M€", 1))
    assert "ligne" in one.drift()
    short = _copy(study, tmp_path, lambda text: text.rsplit("\n", 3)[0])
    assert "lignes au lieu de" in short.drift()


def test_a_page_without_its_reports_and_reports_without_their_page_are_refused(
        tmp_path) -> None:
    study = etude.definition("plf2027")
    alone = etude.replace(study, rapports=tmp_path / "rien")
    assert "sans les rapports" in alone.drift()
    reports = etude.replace(study, page=tmp_path / "absente.md")
    assert "n'existe pas" in reports.drift()


def test_the_command_says_the_drift(tmp_path, monkeypatch, capsys) -> None:
    """`impots etude verifier` exits 1 on a modified page, 0 on the committed one."""
    study = etude.definition("plf2027")
    raw = json.loads((etude.DEFINITIONS / "plf2027.json").read_text(encoding="utf-8"))
    page = tmp_path / "ETUDE_PLF2027.md"
    shutil.copy(study.page, page)
    raw.update(page=str(page), rapports=str(study.rapports))
    (tmp_path / "plf2027.json").write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(etude, "DEFINITIONS", tmp_path)
    assert cli.main(["etude", "verifier", "plf2027"]) == 0
    page.write_text(page.read_text(encoding="utf-8").replace("θ½", "θ⅓", 1),
                    encoding="utf-8")
    assert cli.main(["etude", "verifier", "plf2027"]) == 1
    assert "ligne" in capsys.readouterr().err


# --- a definition says what the page needs ------------------------------------------


GOOD = {"nom": "x", "titre": "X", "texte": "plf2027", "preenregistrement": "D-1",
        "cadre": "central", "millesime_entreprises": "2023",
        "scenarios": [{"scenario": "plf2027_art_2"}]}


@pytest.mark.parametrize("change, needle", [
    ({"autre": 1}, "champs inconnus"),
    ({"cadre": None}, "manquants"),
    ({"nom": "y"}, "nomme l'étude"),
    ({"texte": "plf2026"}, "texte « plf2026 » inconnu"),
    ({"preenregistrement": "289"}, "n'est pas une D-entrée"),
    ({"scenarios": [{"scenario": "a", "sens": 1}]}, "mal dit"),
    ({"scenarios": [{"scenario": "a"}, {"scenario": "a"}]}, "chacun une fois"),
    ({"scenarios": []}, "chacun une fois"),
])
def test_a_definition_that_does_not_say_the_study_is_refused(tmp_path, change,
                                                             needle) -> None:
    raw = {k: v for k, v in {**GOOD, **change}.items() if v is not None}
    (tmp_path / "x.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match=needle):
        etude.definition("x", tmp_path)


def test_a_good_definition_is_read(tmp_path) -> None:
    (tmp_path / "x.json").write_text(json.dumps(GOOD), encoding="utf-8")
    study = etude.definition("x", tmp_path)
    assert study.page == etude.ROOT / "docs" / "etudes" / "x.md"
    assert study.rapports == etude.ROOT / "reports" / "etudes" / "x"
    with pytest.raises(etude.EtudeError, match="aucune étude"):
        etude.definition("absente", tmp_path)


# --- the frame of the studies, in a file of its own (D-336) --------------------------


def test_every_study_reads_the_frame_of_its_own_file() -> None:
    """The studies' hypotheses are no longer the phase 10 IR request's (`etude/ir.json`):
    touching that request for its exploration leaves the ten pages as they are."""
    assert {s.cadre for s in etude.definitions()} == {"central"}
    assert etude.CADRES == etude.ROOT / "etudes" / "cadres"
    assert etude.lire_cadre("central")["theta"] == {"common": 0.5}


def test_the_programmes_hypotheses_are_the_frame_s_numbers() -> None:
    """`programmes/hypotheses/etude.json` says the frame's numbers under other names: the
    fast path of `impots programme` and the studies cannot part. Fails on any drift."""
    cadre = etude.lire_cadre("central")
    hypotheses = json.loads((etude.ROOT / "programmes" / "hypotheses" / "etude.json")
                            .read_text(encoding="utf-8"))

    def numbers(frame: dict) -> dict:
        return {"spending": frame["spending"]["rule"],
                "growth": (frame["growth"]["real"], frame["growth"]["prices"]),
                "rate": frame["rate"]["kind"], "horizon": frame["horizon"],
                "theta": frame["theta"], "wage": frame["uprating"]["wage"],
                "persistence": frame.get("persistence")}

    assert numbers(hypotheses) == numbers(cadre)
    # The comparison sees a drift: a wage of 2 % is refused.
    drifted = {**hypotheses, "uprating": {**hypotheses["uprating"], "wage": 0.02}}
    assert numbers(drifted) != numbers(cadre)


@pytest.mark.parametrize("change, needle", [
    ({"persistance": "tenu"}, "le verdict ne lit que"),
    ({"persistance": "eteint"}, "le verdict ne lit que"),
    ({"taux": "marche"}, "qu'aucune passe ne lit encore"),
    ({"autre": 1}, "champs inconnus"),
    ({"horizon": None}, "manquants"),
])
def test_a_frame_that_says_what_no_pass_reads_is_refused(tmp_path, change, needle) -> None:
    raw = {k: v for k, v in {**etude.lire_cadre("central"), **change}.items()
           if v is not None}
    (tmp_path / "x.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match=needle):
        etude.lire_cadre("x", tmp_path)
    with pytest.raises(etude.EtudeError, match="aucun cadre"):
        etude.lire_cadre("absent", tmp_path)


# --- the PLFSS 2027, in mirror ------------------------------------------------------


@pytest.fixture
def plfss(tmp_path) -> etude.Etude:
    study = etude.definition("plfss2027")
    out = tmp_path / "plfss2027"
    out.mkdir()
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    for name in study.noms:
        kind, endpoint, payload = etude.first_year_payload(name)
        (out / f"premiere_annee_{name}.json").write_text(json.dumps(
            {"scenario": name, "kind": kind, "endpoint": endpoint, "request": payload,
             "response": _households(COSTS[name]), "computed": "2026-10-29",
             "commit": COMMIT, "dirty": False, "where": "ici"}), encoding="utf-8")
        path = copy.deepcopy(template)
        path.update(scenario=name, titre=name, commit=COMMIT, dirty=False, where="ici",
                    annees=None)
        (out / f"predictif_{name}.json").write_text(json.dumps(path), encoding="utf-8")
    return etude.replace(study, rapports=out)


def _section(text: str, volet: str) -> str:
    return text.split(f"\n## Art. 74 du PLF 2027 — {volet}\n")[1].split("\n## ")[0]


def test_the_plfss_study_reads_art_74_in_two_volets_and_says_the_mirror(plfss) -> None:
    text = plfss.render(plfss.load())
    assert "**En miroir.**" in text
    assert "porte 49 articles. Cet outil n'en chiffre aucun" in text
    for volet in ("la prime d'activité", "les aides au logement"):
        assert _section(text, volet).count("### 3. La dette en 2035") == 1
    assert f"| art. 74 du PLF, la prime d'activité | {fiche._eur(-4.0e8)} |" in text


def test_in_mirror_the_cost_and_the_deciles_turn_over(plfss) -> None:
    section = _section(plfss.render(plfss.load()), "la prime d'activité")
    assert f"La mesure rapporte **{fiche._width(-4.0e8)}**" in section
    # The scenario's tenth decile gains 100 € and half of it wins: the measure's loses.
    assert (f"| 10 | {fiche._num(3.1e6)} | {fiche._num(80_000.0)} € | {fiche._eur(-100.0)} "
            f"| {fiche._pct(0.0)} | {fiche._pct(0.5)} |") in section


def test_in_mirror_the_band_and_the_fan_turn_over(plfss) -> None:
    _fan_into(plfss.rapports / "premiere_annee_plf2027_art_74_ppa.json")
    section = _section(plfss.render(plfss.load()), "la prime d'activité")
    cost = 4.0e8
    assert (f"la mesure coûte de {fiche._eur(-1.1 * cost)} à {fiche._eur(-0.9 * cost)}, "
            f"central {fiche._eur(-cost)} (bande **extrapolée** : la réforme sort de "
            f"l'étendue des variations sur lesquelles les élasticités publiées ont été "
            f"estimées), pour "
            f"{fiche._eur(-cost)} sans eux") in section
    assert "* **PIB, à 1 an** : [-3,00 Md€ ; +1,00 Md€], central -1,00 Md€" in section


def _fan_into(path: Path) -> None:
    report = json.loads(path.read_text(encoding="utf-8"))
    _fan(report)
    path.write_text(json.dumps(report), encoding="utf-8")


def test_in_mirror_the_debt_and_its_verdict_turn_over(plfss) -> None:
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    rows = etude.debt(template)
    turned = {"hausse": "baisse", "baisse": "hausse", "dépend de θ": "dépend de θ"}
    text = plfss.render(plfss.load())
    lead = etude._points(-rows[0]["theta"])
    assert (f"| art. 74 du PLF, les aides au logement | {fiche._eur(-1.2e8)} | ") in text
    row = next(line for line in text.splitlines()
               if line.startswith("| art. 74 du PLF, les aides au logement |"))
    assert row.endswith(f"| {lead} | {turned[etude.verdict(rows)]} |")
    corners = rows[3]["corners"]
    assert (f"de {etude._points(-max(corners))} à {etude._points(-min(corners))}"
            in _section(text, "les aides au logement"))


# --- a path written since D-336: « lue », its sensitivities, the Monte-Carlo ----------


#: The distribution a report written since D-336 carries (`montecarlo.run`), by hand.
MONTE = {"objet": "distribution sous des lois déclarées", "lois": "Les lois du test.",
         "rho": 0.8, "tirages": 2000, "graine": 1, "persistence": "lue", "annee": 2035,
         "vues": {view: {"p_hausse": 0.25,
                         "quantiles": {"q05": -0.02, "q50": -0.005, "q95": 0.004},
                         "sobol": {"multiplicateur_macro": {"premier_ordre": 0.6,
                                                            "total": 0.7},
                                   "eti": {"premier_ordre": 0.2, "total": 0.3},
                                   "labour_supply": {"premier_ordre": 0.01,
                                                     "total": 0.05},
                                   "dividends": None}}
                  for view in ("vieillie", "figee")},
         "note": "pas une prévision"}


def _turned(value: float) -> float:
    """« lue » built off « tenu » for the test: every Δb below zero, its order turned over,
    so that the box still holds θ. Under « lue » alone the scenario lowers the debt; read
    with « éteint » and « tenu », whose Δb are above zero, it would depend on θ."""
    assert value > -0.05
    return -value - 0.05


def _with_lue(path: dict, monte: bool = True) -> dict:
    """An older report made a report of D-336: « lue » drawn first, beside « éteint » and
    « tenu », in `side_by_side` and in the box; `rejeu`, and the Monte-Carlo if asked."""
    tenu = next(p for p in path["side_by_side"] if p["persistence"] == "tenu")
    lue = copy.deepcopy(tenu)
    lue.update(persistence="lue", label=retroaction.PERSISTENCE_LABELS["lue"])
    for row, reference in zip(lue["years"], path["years"], strict=True):
        for view in ("aged", "frozen"):
            row[f"delta_{view}"] = _turned(row[f"delta_{view}"])
            row[f"reform_{view}"] = reference["reference"] + row[f"delta_{view}"]
    box = copy.deepcopy(next(p for p in path["theta_box"]["paths"]
                             if p["persistence"] == "tenu"))
    box["persistence"] = "lue"
    for one in box["every_year"].values():
        one["theta"] = _turned(one["theta"])
        one["corners"] = [[label, _turned(value)] for label, value in one["corners"]]
    path["side_by_side"].insert(0, lue)
    path["theta_box"]["paths"].insert(0, box)
    path["rejeu"] = {"de quoi": "refaire la chaîne"}
    if monte:
        path["monte_carlo"] = copy.deepcopy(MONTE)
    return path


@pytest.fixture
def lue(plfss) -> etude.Etude:
    for name in plfss.noms:
        file = plfss.rapports / f"predictif_{name}.json"
        file.write_text(json.dumps(_with_lue(json.loads(file.read_text(encoding="utf-8")))),
                        encoding="utf-8")
    return plfss


def test_a_path_of_d336_reads_its_verdict_under_lue_alone(lue) -> None:
    """D-336, decision 1: the verdict reads « lue » alone, at θ½ and at the corners, in
    both views; « éteint » and « tenu » stand apart, said outside it. Fails if the verdict
    reads every persistence, as it did before: here it would depend on θ."""
    entries = lue.load()
    rows = entries[0]["debt"]
    assert [r["persistence"] for r in rows[::2]] == ["lue", "eteint", "tenu"]
    # In mirror, the scenario's fall is the measure's rise.
    assert etude.verdict(rows) == "hausse"
    every = [{**r, "persistence": "x"} for r in rows]
    assert etude.verdict(every) == "dépend de θ"
    text = lue.render(entries)
    assert "sous la persistance « lue » de l'effet macro de chaque article" in text
    assert "« Éteint » et « tenu » sont des sensibilités, données plus bas, hors du verdict" \
        in text
    row = next(line for line in text.splitlines()
               if line.startswith("| art. 74 du PLF, les aides au logement |"))
    # The rows are the measure's already, turned over by `load`: the lead is +, under « lue ».
    assert rows[0]["theta"] > 0
    assert row.endswith(f"| {etude._points(rows[0]['theta'])} | hausse |")
    section = _section(text, "les aides au logement")
    verdict, _, apart = section.partition("**Les sensibilités, hors du verdict.**")
    assert "Sous cette persistance, elle **augmente la dette** en 2035" in verdict
    assert "Effet macro lu dans Mésange" in verdict and "Effet macro éteint" not in verdict
    assert "Effet macro éteint après trois ans" in apart
    assert "Effet macro tenu au niveau de la troisième année" in apart
    assert "n'entrent pas dans le verdict" in apart


def test_a_path_of_d336_says_its_monte_carlo_apart_from_the_box(lue) -> None:
    """D-336, decision 6: P(hausse en 2035), its quantiles at 5, 50 and 95 %, the two or
    three heaviest Sobol groups, each number with its étage, and the sentence that tells
    the box (not a probability) from the distribution (one, under declared laws). In
    mirror, the measure's: the rise is the scenario's fall, the quantiles turned over."""
    lines, n = lue.lines(lue.load())
    text = "\n".join(n.resolve(line) for line in lines)
    section = _section(text, "les aides au logement")
    assert "ce n'est pas une probabilité. Le Monte-Carlo en est une, sous des lois " \
           "déclarées : Les lois du test." in section
    row = next(line for line in section.splitlines() if line.startswith("| vieillie | 75"))
    assert row == ("| vieillie | 75\u202f% | -0,40 pt | +0,50 pt | +2,00 pt | le "
                   "multiplicateur 0,70, les lignes de `eti.yaml` 0,30, les lignes de "
                   "`labour_supply.yaml` 0,05 |")
    assert "dividends" not in section
    said = {item.texte: item for item in n.items}
    for number in ("75\u202f%", "-0,40 pt", "+2,00 pt", "0,70"):
        assert said[number].etage == "L4" and said[number].conditionnel


def test_a_path_of_d336_without_its_monte_carlo_says_none(plfss) -> None:
    for name in plfss.noms:
        file = plfss.rapports / f"predictif_{name}.json"
        file.write_text(json.dumps(_with_lue(json.loads(file.read_text(encoding="utf-8")),
                                             monte=False)), encoding="utf-8")
    text = plfss.render(plfss.load())
    assert "**Les sensibilités, hors du verdict.**" in text and "Monte-Carlo" not in text


LECTURES = {
    "persistence": "lue", "theta": {},
    "decomposition": {v: {"cout": 0.010, "denominateur": -0.002, "retroaction": -0.003,
                          "total": 0.005} for v in ("vieillie", "figee")},
    "taux_marche": {"taux": 0.035, "vieillie": 0.006, "figee": 0.006},
    "variante_salariale": {
        "sources": {"cotisations_employeurs": "phillips", "taxe_carbone": None},
        "non_variees": ["taxe_carbone"],
        "boite": {v: {"theta": 0.004, "corners": [["a", 0.001], ["b", 0.008]]}
                  for v in ("vieillie", "figee")},
        "monte_carlo": {v: {"p_hausse": 0.97} for v in ("vieillie", "figee")}}}


@pytest.fixture
def lu(lue) -> etude.Etude:
    """A series of but 16: the readings of D-349 on every path, the scenario's debt
    falling in 95 % of the draws, an employer-contribution instrument in the loop."""
    for name in lue.noms:
        file = lue.rapports / f"predictif_{name}.json"
        path = json.loads(file.read_text(encoding="utf-8"))
        path["lectures"] = copy.deepcopy(LECTURES)
        path["monte_carlo"]["vues"]["vieillie"]["p_hausse"] = 0.05
        path["rejeu"]["macro"] = {"instruments": {"cotisations_employeurs": {}}}
        file.write_text(json.dumps(path), encoding="utf-8")
    return lue


def test_a_path_of_d349_says_the_monte_carlo_verdict_and_its_readings(lu) -> None:
    """D-345 and D-349: the verdict reads the distribution (at most 10 % of the scenario's
    draws raise the debt: the measure, in mirror, raises it in at least 90 %), the box
    stands beside it; the decomposition adds up to the headline, the market rate, the wage
    variant and its verdict, the corporate tax and the public sector are said. Every Δb is
    the measure's, turned over."""
    entries = lu.load()
    assert entries[0]["sign"] == -1 and etude.verdict_mc(entries[0]) == "hausse"
    lines, n = lu.lines(entries)
    text = "\n".join(n.resolve(line) for line in lines)
    row = next(line for line in text.splitlines()
               if line.startswith("| art. 74 du PLF, les aides au logement |"))
    # The verdict and its share of draws beside it (D-378), then the θ box's reading.
    assert re.search(r"\| hausse \(\d+\u202f% des tirages en hausse\) \| hausse \|$", row)
    assert "« hausse » quand au moins 90\u202f% des tirages font monter la dette" in text
    section = _section(text, "les aides au logement")
    assert ("**Le verdict**, lu sur le Monte-Carlo (D-345) : elle **augmente la dette** en "
            "2035 dans au moins 90\u202f% des tirages, vue vieillie.") in section
    assert "| vieillie | -1,00 pt | +0,20 pt | +0,30 pt | -0,50 pt |" in section
    assert "Chargée à 3,5\u202f%" in section and "-0,60 pt en vue vieillie, contre -0,50 pt" \
        in section
    assert "| vieillie | -0,40 pt | de -0,80 pt à -0,10 pt | 3\u202f% | baisse |" in section
    assert "pour `taxe_carbone`" in section and "la variante est partielle" in section
    assert "**Brut d'IS.**" in section
    assert "Le secteur public est modélisé statut par statut (D-346)" in text
    said = {item.texte: item for item in n.items}
    assert said["90\u202f%"].etage == "déclaré" and said["3,5\u202f%"].etage == "hypothèse"


def test_the_page_says_what_moved_against_the_frozen_series_and_why(lu) -> None:
    """D-350: the previous series frozen once, refused twice; the page of the new one says
    each line then and now, and the corrections that touch it."""
    frozen = lu.figer_avant()
    with pytest.raises(etude.EtudeError, match="déjà figée"):
        lu.figer_avant()
    then = json.loads(frozen.read_text(encoding="utf-8"))
    entry = next(e for e in lu.load() if e["name"].endswith("apl"))
    then["scenarios"][entry["name"]].update(dette=0.012, selon_theta="dépend de θ")
    frozen.write_text(json.dumps(then), encoding="utf-8")
    text = lu.render(lu.load())
    section = text.split("## Ce qui a bougé depuis la série précédente\n")[1].split("\n## ")[0]
    row = next(line for line in section.splitlines()
               if line.startswith("| art. 74 du PLF, les aides au logement |"))
    assert row.endswith(f"| +1,20 pt → {etude._points(entry['debt'][0]['theta'])} | "
                        f"dépend de θ → hausse |")
    assert ("* **art. 74 du PLF, les aides au logement** : le secteur public modélisé "
            "statut par statut (D-346), le verdict lu sur le Monte-Carlo (D-345).") in section


def test_a_study_half_of_d349_is_refused(lu) -> None:
    file = lu.rapports / f"predictif_{lu.noms[0]}.json"
    path = json.loads(file.read_text(encoding="utf-8"))
    del path["lectures"]
    file.write_text(json.dumps(path), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="lectures de D-349"):
        lu.render(lu.load())


def test_an_older_path_renders_the_page_it_always_did(plfss) -> None:
    """A report before D-336 (« éteint » and « tenu », no `rejeu`, no `monte_carlo`) is
    read under the frame that now says « lue », and its page has neither sensitivities
    nor distribution: the committed pages stay as they are until the series runs again."""
    assert etude.lire_cadre("central")["persistance"] == "lue"
    text = plfss.render(plfss.load())
    assert "sous la première persistance de l'effet macro" in text
    assert "Sensibilités" not in text and "Monte-Carlo" not in text
    assert "Sur ces passes, " in text


def test_a_new_path_without_lue_and_a_study_of_two_series_are_refused(plfss) -> None:
    first = plfss.noms[0]
    file = plfss.rapports / f"predictif_{first}.json"
    path = json.loads(file.read_text(encoding="utf-8"))
    file.write_text(json.dumps({**path, "rejeu": {}}), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="ne la trace pas"):
        plfss.load()
    file.write_text(json.dumps(_with_lue(path)), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="pas d'une même série"):
        plfss.render(plfss.load())


def test_the_gap_is_the_registration_s_in_the_measure_s_sign(plfss) -> None:
    text = plfss.render(plfss.load())
    for name, volet in (("plf2027_art_74_ppa", "la prime d'activité"),
                        ("plf2027_art_74_apl", "les aides au logement")):
        grade = preregistration.grade(preregistration.load(name))
        assert grade.published_eur < 0 and grade.simulated_eur < 0
        assert (f"soit {fiche._eur(-COSTS[name] - grade.simulated_eur)} de l'enregistrement"
                in _section(text, volet))


def test_every_plfss_article_is_listed_with_its_door(plfss) -> None:
    text = plfss.render(plfss.load())
    assert "## Les 49 articles du PLFSS" in text
    for a in plf_coverage.ARTICLES_PLFSS_2027:
        kind, why = etude.refusal(a.raison)
        assert (f"| {a.numero} | {a.intitule} | {etude.case_lue(kind)} | "
                f"{etude.porte_lue(a.porte)} | {why} |") in text
    for porte, numeros in plf_coverage.portes_plfss_2027():
        assert f"* {etude.porte_lue(porte)}, {len(numeros)} article" in text


def test_a_volet_read_against_its_registration_s_sense_is_refused(plfss) -> None:
    flat = etude.replace(plfss, volets=tuple(
        etude.Volet(v.scenario, v.titre, miroir=False) for v in plfss.volets))
    with pytest.raises(etude.EtudeError, match="miroir"):
        flat.load()


def test_a_plfss_volet_without_a_title_is_refused(plfss) -> None:
    bare = etude.replace(plfss, volets=tuple(
        etude.Volet(v.scenario, None, v.miroir) for v in plfss.volets))
    with pytest.raises(etude.EtudeError, match="sans titre"):
        bare.load()


# --- several commits, joined by a witness pass (D-335, D-336) ------------------------

LATER = "b" * 40


def _on(path: Path, commit: str, **changes) -> dict:
    report = json.loads(path.read_text(encoding="utf-8"))
    report.update(commit=commit, **changes)
    path.write_text(json.dumps(report), encoding="utf-8")
    return report


def _witness(study: etude.Etude, report: dict, identique: bool = True) -> Path:
    path = study.rapports / etude.TEMOINS / f"{LATER[:7]}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({
        "etude": study.nom, "passe": study.witness_pass(), "reference": COMMIT,
        "commit": LATER, "dirty": False, "where": "là", "computed": "2026-11-04",
        "identique": identique, "ecarts": [], "rapport": report}), encoding="utf-8")
    return path


def _replayed(study: etude.Etude, **changes) -> dict:
    """The witness pass's report as a replay on LATER gives it: another day, another place,
    the same request and reply unless `changes` says otherwise."""
    report = json.loads((study.rapports / study.witness_pass()).read_text(encoding="utf-8"))
    return {**report, "commit": LATER, "computed": "2026-11-04", "where": "là", **changes}


def test_a_second_commit_without_its_witness_is_refused_with_the_command(plfss) -> None:
    _on(plfss.rapports / "predictif_plf2027_art_74_apl.json", LATER)
    with pytest.raises(etude.EtudeError, match="sont sur 2 commits") as error:
        plfss.load()
    assert f"impots etude temoin {plfss.nom}" in str(error.value)


def test_a_second_commit_with_an_identical_witness_is_read_and_said(plfss) -> None:
    """Fails on the code before D-335's rule: two commits were refused, witness or not."""
    assert plfss.witness_pass() == "premiere_annee_plf2027_art_74_ppa.json"
    _on(plfss.rapports / "predictif_plf2027_art_74_apl.json", LATER)
    _witness(plfss, _replayed(plfss))
    entries = plfss.load()
    assert entries[0]["commits"][0] == (COMMIT, None)
    assert [c for c, _ in entries[0]["commits"]] == [COMMIT, LATER]
    text = plfss.render(entries)
    assert "Les passes ont tourné sur 2 commits, ici" in text
    assert f"* `{COMMIT[:7]}`, le premier." in text
    assert (f"* `{LATER[:7]}`, rejoint par `{etude._relative(plfss.rapports)}/temoins/"
            f"{LATER[:7]}.json`, témoin du 2026-11-04.") in text


@pytest.mark.parametrize("how", ["autre-cout", "dit-different", "autre-passe",
                                 "autre-reference", "rapport-sur-un-autre-commit"])
def test_a_witness_that_does_not_give_the_report_again_is_refused(plfss, how) -> None:
    """A witness is compared anew, not believed: one that says « identique » over another
    reply, or names another pass or another first commit, joins nothing."""
    _on(plfss.rapports / "predictif_plf2027_art_74_apl.json", LATER)
    report = _replayed(plfss)
    if how == "autre-cout":
        report["response"] = {**report["response"],
                              "reform_cost": report["response"]["reform_cost"] + 1.0}
    if how == "rapport-sur-un-autre-commit":
        report["commit"] = COMMIT
    path = _witness(plfss, report, identique=how != "dit-different")
    witness = json.loads(path.read_text(encoding="utf-8"))
    if how == "autre-passe":
        witness["passe"] = "premiere_annee_plf2027_art_74_apl.json"
    if how == "autre-reference":
        witness["reference"] = "c" * 40
    path.write_text(json.dumps(witness), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="n'a pas de passe témoin"):
        plfss.load()


def test_the_differences_are_value_and_type_outside_date_commit_and_place() -> None:
    a = {"commit": "x", "computed": "1", "where": "ici", "dirty": False,
         "response": {"cost": 3, "rows": [1.0, 2.0]}}
    assert etude.ecarts(a, {**a, "commit": "y", "computed": "2", "where": "là"}) == []
    assert etude.ecarts(a, {**a, "response": {"cost": 3.0, "rows": [1.0, 2.0]}}) == [
        "/response/cost"]
    assert etude.ecarts(a, {**a, "response": {"cost": 3, "rows": [1.0]}}) == [
        "/response/rows (2 éléments au lieu de 1)"]
    assert etude.ecarts(a, {**a, "extra": 1}) == ["/extra"]


@pytest.fixture
def witnessing(plfss, monkeypatch):
    """`impots etude temoin` on LATER, its pass replayed by a stand-in that writes the
    report `replay` holds where the command says."""
    from impots.predictif import recherche

    replay: dict = {"report": _replayed(plfss)}
    commands: list = []

    def run(command, **kw):
        commands.append(command)
        out = Path(command[command.index("--sortie") + 1])
        out.write_text(json.dumps(replay["report"]), encoding="utf-8")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(etude.subprocess, "run", run)
    monkeypatch.setattr(recherche, "code_state", lambda root=None: (LATER, False))
    return SimpleNamespace(study=plfss, replay=replay, commands=commands,
                           out=plfss.rapports / etude.TEMOINS / f"{LATER[:7]}.json")


def test_the_witness_replays_the_shortest_pass_and_says_identical(witnessing) -> None:
    assert witnessing.study.witness("là") == 0
    command = witnessing.commands[0]
    assert command[command.index("etude") + 1:command.index("etude") + 4] == [
        "premiere", "plfss2027", "plf2027_art_74_ppa"]
    witness = json.loads(witnessing.out.read_text(encoding="utf-8"))
    assert witness["identique"] is True and witness["ecarts"] == []
    assert (witness["reference"], witness["commit"]) == (COMMIT, LATER)
    # The committed report is not touched; a second witness is not written over the first.
    assert json.loads((witnessing.study.rapports / witnessing.study.witness_pass())
                      .read_text(encoding="utf-8"))["commit"] == COMMIT
    assert witnessing.study.witness("là") == 1


def test_a_witness_that_differs_is_written_as_such_and_fails(witnessing, capsys) -> None:
    report = witnessing.replay["report"]
    report["response"] = {**report["response"],
                          "reform_cost": report["response"]["reform_cost"] * 2}
    assert witnessing.study.witness("là") == 1
    witness = json.loads(witnessing.out.read_text(encoding="utf-8"))
    assert witness["identique"] is False and witness["ecarts"] == ["/response/reform_cost"]
    assert "n'est PAS redonné à l'identique" in capsys.readouterr().err


@pytest.mark.parametrize("how, needle", [
    ("dirty", "modifications non commitées"),
    ("same", "est déjà sur le commit"),
    ("absent", "le témoin rejoue une passe déjà faite"),
])
def test_the_witness_refuses_before_its_pass(witnessing, monkeypatch, capsys, how,
                                             needle) -> None:
    from impots.predictif import recherche

    if how == "dirty":
        monkeypatch.setattr(recherche, "code_state", lambda root=None: (LATER, True))
    if how == "same":
        monkeypatch.setattr(recherche, "code_state", lambda root=None: (COMMIT, False))
    if how == "absent":
        for path in witnessing.study.rapports.glob("premiere_annee_*.json"):
            path.unlink()
    assert witnessing.study.witness("là") == 1
    assert witnessing.commands == [] and needle in capsys.readouterr().err
    assert not witnessing.out.exists()


def test_in_mirror_a_firm_s_tax_turns_over() -> None:
    from impots.api.schemas import FirmResponse
    from test_etude_page_plf2027 import _firms

    response = FirmResponse.model_validate(_firms(-7.1e9))
    plain = {taille: delta for taille, *_, delta in etude.Etude._sizes(response, 1)}
    turned = {taille: delta for taille, *_, delta in etude.Etude._sizes(response, -1)}
    assert plain["GE"] == pytest.approx(7.1e9)
    assert turned == {taille: -delta for taille, delta in plain.items()}


def test_a_first_year_of_a_scenario_outside_the_study_is_refused(tmp_path) -> None:
    # Its reports go to the test's directory: under a mutation, the pass would write one.
    study = etude.replace(etude.definition("plfss2027"), rapports=tmp_path)
    with pytest.raises(etude.EtudeError, match="n'est pas un scénario de l'étude"):
        study.write_first_year("plf2027_art_2", where="ici")


@pytest.mark.parametrize("change", [{"theta": 0.3}, {"macro": False},
                                    {"behavioural": False}])
def test_a_frame_that_is_not_d_289_s_is_refused_by_the_page(plfss, monkeypatch,
                                                           change) -> None:
    entries = plfss.load()
    frame = plfss.frame()
    monkeypatch.setattr(etude.Etude, "frame", lambda self: {**frame, **change})
    with pytest.raises(etude.EtudeError, match="n'est pas celui de D-289"):
        plfss.render(entries)


# --- every number says what it rests on (D-304) -------------------------------------


def test_an_amount_without_its_etage_is_refused(monkeypatch) -> None:
    """Fails if an article's title or a triage's reason could quote an amount the page
    shows bare: the art. 3's title quotes 3 000 €."""
    monkeypatch.setattr(etude, "amounts", lambda text, etage, n: text)
    study = etude.definition("plf2027")
    with pytest.raises(etude.EtudeError, match="sans son étage"):
        study.lines(study.load())


def test_a_number_of_an_unknown_etage_is_refused() -> None:
    with pytest.raises(etude.EtudeError, match="sans étage connu"):
        etude.Nombres()("1 €", "L9")


@pytest.mark.parametrize("report, expected", [
    ("reports/etude_plf2027/predictif_plf2027_art_2.json", "L4"),
    ("reports/etude_plf2027/predictif_plf2027_art_3.json", "L4"),
    ("reports/etude_plf2027/predictif_plf2027_art_15.json", "L2"),
    ("reports/etudes/plfss2027/predictif_plf2027_art_74_ppa.json", "L2"),
    ("reports/etudes/plfss2027/predictif_plf2027_art_74_apl.json", "L2"),
])
def test_the_debt_rests_on_the_highest_layer_that_entered(report, expected) -> None:
    path = json.loads((etude.ROOT / report).read_text(encoding="utf-8"))
    assert etude.debt_etage(path) == expected


def test_a_debt_with_a_channel_and_no_loop_rests_on_l3() -> None:
    from impots.predictif.chaine import MACRO_CHANNELS
    from impots.predictif.theta import MACRO_ROW

    closed = {channel: "absente" for channel in MACRO_CHANNELS}
    assert etude.debt_etage({"closed": closed,
                             "theta_box": {"rows": ["eti_all", MACRO_ROW]}}) == "L3"
    assert etude.debt_etage({"closed": closed, "theta_box": {"rows": [MACRO_ROW]}}) == "L2"


def _etages(study: etude.Etude, start: str) -> list[tuple[str, bool]]:
    """(étage, conditional) of each number on the page's first line opening with `start`."""
    lines, n = study.lines(study.load())
    line = next(text for text in lines if text.startswith(start))
    return [(n.items[int(i)].etage, n.items[int(i)].conditionnel)
            for i in re.findall("(\\d+)", line)]


@pytest.mark.parametrize("nom, start, expected", [
    ("plfss2027", "| 1 | ", ["L1", "L1", "L2", "L2", "L2"]),
    # The cost, the published figure, the figure noted when preregistered (D-378), the
    # debt and the share of draws in which it rises.
    ("plfss2027", "| art. 74 du PLF, la prime", ["L2", "publié", "L2", "L2", "L2"]),
    ("plfss2027", "Enregistré le", ["L2", "publié", "publié", "L2", "L2", "déclaré"]),
    ("plfss2027", "| Effet macro éteint après trois ans | figée", ["L2", "L2", "L2"]),
    ("plfss2027", "Le projet de loi", ["texte", "texte"]),
    ("plf2027", "**Une fois les comportements", ["L3", "L3", "L3", "L2"]),
    ("plf2027", "* **PIB, à 1 an**", ["L4"]),
    ("plf2027", "| Effet macro éteint après trois ans | figée", ["L4", "L4", "L4"]),
    ("plf2027", "## Art. 3 ", ["texte"]),
])
def test_each_answer_says_its_layer(nom, start, expected) -> None:
    found = _etages(etude.definition(nom), start)
    assert [etage for etage, _ in found] == expected
    # Only a gap in the debt is conditional, and each of its numbers is.
    assert all(conditional == ("Effet macro" in start or ("art. 74" in start and i >= 3))
               for i, (_, conditional) in enumerate(found))


def test_the_difference_shows_where_the_texts_part() -> None:
    """A drift message shows the words that differ, not the start of a long line."""
    committed, built = "x" * 100 + "AAA" + "y" * 10, "x" * 100 + "BBB" + "y" * 10
    where = etude.difference(committed, built)
    assert where.startswith("ligne 1 : ") and "AAA" in where and "BBB" in where
    assert etude.difference("a\nb", "a\nb\nc") == "2 lignes au lieu de 3"
    assert etude.difference("a", "a") is None
