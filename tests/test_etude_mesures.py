"""Chaque mesure d'un programme passe aussi seule (but 22, chantier B) : sa première année
et son chemin annuel, sous `mesures/<id>/`, lus comme ceux de la part chiffrée ; la page
dit chaque mesure, leur somme, la part, et l'interaction (la part moins la somme).

Les rapports des mesures sont factices : ceux de la part chiffrée de Roussel, commités,
mis à l'échelle d'un facteur par mesure, pour que la somme et l'interaction soient
connues d'avance. Aucune passe ne tourne sur la population réelle."""

from __future__ import annotations

import copy
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from impots import etude, fiche
from impots import programmes as pg
from impots import scenarios as scenarios_module

ROOT = Path(__file__).resolve().parents[1]
#: Le facteur de chaque mesure de Roussel : la somme fait 1,1 fois la part, et
#: l'interaction, la part moins la somme, −0,1 fois.
FACTEURS = {"tva_carburants_5_5": 0.6, "smic_plus_15": 0.5}


def _scale_path(path: dict, k: float) -> dict:
    path = copy.deepcopy(path)
    for years in [path["years"], *(p["years"] for p in path.get("side_by_side") or [])]:
        for row in years:
            for key in ("delta_aged", "delta_frozen", "mechanical_aged_eur",
                        "mechanical_frozen_eur"):
                if row.get(key) is not None:
                    row[key] *= k
    for box in (path.get("theta_box") or {}).get("paths", []):
        for reading in box["every_year"].values():
            reading["theta"] *= k
            reading["corners"] = [[label, value * k] for label, value in reading["corners"]]
    return path


def _scale_first(first: dict, k: float) -> dict:
    first = copy.deepcopy(first)
    first["response"]["reform_cost"] *= k
    for row in first["response"]["deciles"]:
        row["mean_delta"] *= k
    return first


def _mesure(study: etude.Etude, seule: etude.MesureSeule, k: float) -> None:
    """Les deux rapports factices de `seule` : ceux de la part, à l'échelle `k`, sur son
    scénario et par l'appel de sa chaîne."""
    part = study.noms[0]
    first = json.loads((study.rapports / f"premiere_annee_{part}.json").read_text("utf-8"))
    path = json.loads((study.rapports / f"predictif_{part}.json").read_text("utf-8"))
    kind, endpoint, payload = etude.first_year_payload(seule.scenario, mixte=True)
    first = {**_scale_first(first, k), "scenario": seule.scenario, "kind": kind,
             "endpoint": endpoint, "request": payload}
    path = {**_scale_path(path, k), "scenario": seule.scenario}
    folder = study.rapports / etude.MESURES / seule.mesure
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"premiere_annee_{seule.scenario}.json").write_text(json.dumps(first),
                                                                  encoding="utf-8")
    (folder / f"predictif_{seule.scenario}.json").write_text(json.dumps(path),
                                                             encoding="utf-8")


@pytest.fixture
def roussel(tmp_path) -> etude.Etude:
    """L'étude de Roussel sur une copie de ses rapports commités, sans mesures seules."""
    study = etude.definition("presidentielle_roussel")
    shutil.copytree(study.rapports, tmp_path / "roussel")
    return etude.replace(study, rapports=tmp_path / "roussel")


@pytest.fixture
def seules(roussel) -> etude.Etude:
    for seule in roussel.mesures:
        _mesure(roussel, seule, FACTEURS[seule.mesure])
    return roussel


def test_the_passes_list_each_measure_alone_after_the_part(roussel) -> None:
    """Après les passes de la part, la première année puis le chemin de chaque mesure,
    chacune dans son dossier, le chemin écrit là."""
    passes = roussel.passes("essai")
    reports = [r for r, _ in passes]
    assert [m.mesure for m in roussel.mesures] == list(FACTEURS)
    neuves = reports[-4:]
    assert neuves == [f"mesures/{m}/premiere_annee_pres2027_roussel_{m}.json"
                      for m in FACTEURS] + [
        f"mesures/{m}/predictif_pres2027_roussel_{m}.json" for m in FACTEURS]
    assert reports[-5] == "predictif_pres2027_roussel_programme.json"
    assert not any(r.startswith("mesures/") for r in reports[:-4])
    command = dict(passes)[neuves[-1]]
    assert command[command.index("--out-dir") + 1] == str(
        roussel.rapports / "mesures" / "smic_plus_15")
    assert dict(passes)[neuves[0]][-6:] == ["etude", "premiere", roussel.nom,
                                            "pres2027_roussel_tva_carburants_5_5", "--ou",
                                            "essai"]


def test_the_sum_and_the_interaction_are_the_part_minus_the_measures(seules) -> None:
    entries = seules.load()
    part = etude.lecture_seule(entries[0])
    lues = [etude.lecture_seule(e) for e in entries[0]["mesures"]]
    for key in ("figee", "vieillie", "dette", "bas", "menages"):
        somme = sum(x[key] for x in lues)
        assert somme == pytest.approx(1.1 * part[key], rel=1e-9), key
        assert part[key] - somme == pytest.approx(-0.1 * part[key], rel=1e-6), key
    text = seules.render(entries)
    section = text.split("## Chaque mesure seule, et leur interaction")[1].split("\n## ")[0]
    rows = {line.split(" | ")[0]: line for line in section.splitlines()
            if line.startswith("| **")}
    assert f"| {fiche._eur(1.1 * part['figee'])} |" in rows["| **somme des mesures**"]
    assert f"| {fiche._eur(part['figee'])} |" in rows["| **la part chiffrée**"]
    interaction = rows["| **interaction**, la part moins la somme"]
    assert f"| {fiche._eur(-0.1 * part['figee'])} |" in interaction
    assert f"| {etude._points(-0.1 * part['dette'])} |" in interaction
    # Chaque mesure a sa ligne, et chaque ligne ses deux rapports.
    for m in pg.charger("roussel").chiffrees():
        assert f"mesures/{m.id}/predictif_pres2027_roussel_{m.id}.json" in section
    assert "n'a pas tourné" not in section


def test_a_measure_s_report_that_is_not_its_scenario_s_is_refused(seules) -> None:
    seule = seules.mesures[0]
    folder = seules.rapports / etude.MESURES / seule.mesure
    file = folder / f"premiere_annee_{seule.scenario}.json"
    report = json.loads(file.read_text(encoding="utf-8"))
    # La première année de l'autre mesure, sous le nom de celle-ci.
    autre = seules.mesures[1].scenario
    _, _, payload = etude.first_year_payload(autre, mixte=True)
    file.write_text(json.dumps({**report, "request": payload}), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="n'a pas chiffré le scénario"):
        seules.load()
    file.write_text(json.dumps(report), encoding="utf-8")
    path = folder / f"predictif_{seule.scenario}.json"
    path.write_text(json.dumps({**json.loads(path.read_text(encoding="utf-8")),
                                "scenario": autre}), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="dans le cadre de l'étude, sur son scénario"):
        seules.load()


def test_a_page_without_the_measures_reports_says_them_absent_with_the_command(
        roussel) -> None:
    """Décidé au but 22 : une étude dont la série n'a pas passé ses mesures seules (celles
    du but 21) se lit, et sa page dit qu'elles manquent et la commande qui les lance."""
    entries = roussel.load()
    assert entries[0]["mesures"] is None
    text = roussel.render(entries)
    section = text.split("## Chaque mesure seule, et leur interaction")[1].split("\n## ")[0]
    assert "**Les mesures seules : absentes, et la raison est donnée.**" in section
    assert f"`impots etude lancer {roussel.nom}`" in section
    assert "| **interaction**" not in section


def test_a_series_half_run_is_refused(roussel) -> None:
    _mesure(roussel, roussel.mesures[0], 0.6)
    with pytest.raises(etude.EtudeError, match="impots etude lancer"):
        roussel.load()


def test_the_series_resumes_after_the_measures_already_there(roussel, monkeypatch) -> None:
    """La reprise : les rapports déjà là sont sautés, mesures comprises ; un fichier qui
    n'est pas une passe est refusé avant toute passe."""
    from impots.predictif import recherche

    first = json.loads((roussel.rapports / roussel.witness_pass()).read_text("utf-8"))
    _mesure(roussel, roussel.mesures[0], 0.6)
    monkeypatch.setattr(recherche, "code_state", lambda root: (first["commit"], False))
    monkeypatch.setattr(etude.Etude, "preregistered", lambda self: None)
    ran = []
    monkeypatch.setattr(etude.subprocess, "run",
                        lambda command, **_: ran.append(command) or
                        type("R", (), {"returncode": 0})())
    assert roussel.launch("essai") == 0
    autre = roussel.mesures[1].scenario
    assert len(ran) == 2
    assert autre in ran[0] and "premiere" in ran[0]
    assert autre in ran[1] and "predictif" in ran[1]
    (roussel.rapports / etude.MESURES / "en_trop.json").write_text("{}", encoding="utf-8")
    ran.clear()
    assert roussel.launch("essai") == 1
    assert ran == []


def _definition(tmp_path, **change) -> etude.Etude:
    raw = json.loads((ROOT / "etudes" / "presidentielle_roussel.json").read_text("utf-8"))
    (tmp_path / "presidentielle_roussel.json").write_text(json.dumps({**raw, **change}),
                                                         encoding="utf-8")
    return etude.definition("presidentielle_roussel", tmp_path)


def test_a_definition_whose_measures_are_not_the_programme_s_is_refused(tmp_path) -> None:
    good = [{"mesure": m, "scenario": f"pres2027_roussel_{m}"} for m in FACTEURS]
    assert len(_definition(tmp_path, mesures=good).mesures) == 2
    with pytest.raises(etude.EtudeError, match="dans son ordre"):
        _definition(tmp_path, mesures=good[::-1])
    with pytest.raises(etude.EtudeError, match="dans son ordre"):
        _definition(tmp_path, mesures=good[:1])
    with pytest.raises(etude.EtudeError, match="scénario de son cas"):
        _definition(tmp_path, mesures=[{**good[0], "scenario": "pres2027_roussel_programme"},
                                       good[1]])
    raw = json.loads((ROOT / "etudes" / "presidentielle_kazib.json").read_text("utf-8"))
    (tmp_path / "presidentielle_kazib.json").write_text(json.dumps(
        {**raw, "mesures": [{"mesure": "smic_2000", "scenario": "pres2027_kazib_smic_2000"}]}),
        encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="une seule mesure chiffrée"):
        etude.definition("presidentielle_kazib", tmp_path)
    raw = json.loads((ROOT / "etudes" / "plf2027.json").read_text("utf-8"))
    (tmp_path / "plf2027.json").write_text(json.dumps({**raw, "mesures": good}),
                                           encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="seule une étude de programme"):
        etude.definition("plf2027", tmp_path)


def test_the_measures_scenarios_are_the_generated_ones() -> None:
    """GARDE. Les études qui passent leurs mesures seules : celles de plus d'une mesure,
    hors Dupont-Aignan, refusée (D-398) ; le scénario seul d'une mesure des entreprises
    est celui du générateur, sa seule réforme."""
    spec = importlib.util.spec_from_file_location(
        "preenregistrer_programmes", ROOT / "scripts" / "preenregistrer_programmes.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for doc in module.scenarios_des_mesures_entreprises():
        path = ROOT / "scenarios" / f"{doc['name']}.json"
        assert json.loads(path.read_text(encoding="utf-8")) == doc
        scenario = scenarios_module.load(doc["name"])
        assert scenario.reform.is_empty() and not scenario.firm_reform.is_empty()
    avec = {s.programme: len(s.mesures) for s in etude.definitions() if s.mesures}
    assert "dupont_aignan" not in avec
    assert all(len(pg.charger(slug).chiffrees()) == count for slug, count in avec.items())
    assert sum(avec.values()) == 35
