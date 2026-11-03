"""La commande des études (but 6, D-301) : une définition, ses passes, sa page.

Chaque définition de `etudes/` est soit préenregistrée et pas lancée (ni rapports ni page),
soit lancée et rendue (ses rapports, et une page qui est exactement leur rendu) : une page
modifiée est refusée, une page sans ses rapports aussi. L'étude du PLFSS 2027 lit les deux
volets de l'art. 74 du PLF en miroir (D-298) : chaque réponse changée de signe, gagnants et
perdants échangés, et les 49 articles du PLFSS avec leur porte. Les rapports de ces tests
sont factices, construits comme ceux de `test_write_etude_plf2027.py`.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path

import pytest

from impots import etude, fiche, plf_coverage, preregistration
from impots.population import cli
from test_write_etude_plf2027 import COMMIT, TEMPLATE, _fan, _households

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
    ({"persistance": "lue"}, "qu'aucune passe ne lit encore"),
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
            f"central {fiche._eur(-cost)} (grade **illustrative**), pour "
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
        assert f"| {a.numero} | {a.intitule} | `{kind}` | `{a.porte}` | {why} |" in text
    for porte, numeros in plf_coverage.portes_plfss_2027():
        assert f"* `{porte}`, {len(numeros)} article" in text


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


def test_in_mirror_a_firm_s_tax_turns_over() -> None:
    from impots.api.schemas import FirmResponse
    from test_write_etude_plf2027 import _firms

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
    ("plfss2027", "| art. 74 du PLF, la prime", ["L2", "publié", "L2"]),
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
    assert all(conditional == ("Effet macro" in start or ("art. 74" in start and i == 2))
               for i, (_, conditional) in enumerate(found))


def test_the_difference_shows_where_the_texts_part() -> None:
    """A drift message shows the words that differ, not the start of a long line."""
    committed, built = "x" * 100 + "AAA" + "y" * 10, "x" * 100 + "BBB" + "y" * 10
    where = etude.difference(committed, built)
    assert where.startswith("ligne 1 : ") and "AAA" in where and "BBB" in where
    assert etude.difference("a\nb", "a\nb\nc") == "2 lignes au lieu de 3"
    assert etude.difference("a", "a") is None
