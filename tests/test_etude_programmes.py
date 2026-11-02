"""Les études des programmes (but 13, D-328) : une par candidat dont une mesure se chiffre,
sur sa part chiffrée, ménages et entreprises ensemble, avec ses plages en trois points."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from impots import etude
from impots import programmes as pg
from impots import scenarios as scenarios_module

ROOT = Path(__file__).resolve().parents[1]


def _script():
    path = ROOT / "scripts" / "preenregistrer_programmes.py"
    spec = importlib.util.spec_from_file_location("preenregistrer_programmes", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _studies() -> list[etude.Etude]:
    return [s for s in etude.definitions() if s.programme is not None]


def test_every_programme_with_a_priced_measure_has_its_study() -> None:
    """GARDE. Huit études, une par candidat dont une mesure se chiffre, et aucune autre."""
    chiffres = sorted(s for s in pg.lister() if pg.charger(s).chiffrees())
    assert sorted(s.programme for s in _studies()) == chiffres
    assert len(chiffres) == 8


def test_the_committed_scenarios_and_studies_are_the_generated_ones() -> None:
    """GARDE. Le scénario d'une part chiffrée est le programme, sans rien d'autre ; sa
    définition, celle du générateur."""
    for slug, scenario, definition in _script().etudes():
        path = ROOT / "scenarios" / f"{scenario['name']}.json"
        assert json.loads(path.read_text(encoding="utf-8")) == scenario, slug
        path = ROOT / "etudes" / f"{definition['nom']}.json"
        assert json.loads(path.read_text(encoding="utf-8")) == definition, slug


def test_the_part_is_every_priced_measure_households_and_firms_together() -> None:
    from impots import consommation

    for study in _studies():
        p = pg.charger(study.programme)
        scenario = scenarios_module.load(study.noms[0])
        menages, entreprises = p.reformes()
        assert scenario.reform == (menages or type(scenario.reform)())
        assert (scenario.firm_reform or None) == entreprises
        assert ("consommation" in scenario.imputations) == consommation.touche(
            scenario.reform)
        assert scenario.year == p.annee


def test_a_study_s_passes_are_its_first_year_its_ranges_then_its_path() -> None:
    study = etude.definition("presidentielle_lisnard")
    reports = [r for r, _ in study.passes("essai")]
    assert reports[0] == "premiere_annee_pres2027_lisnard_programme.json"
    assert reports[-1] == "predictif_pres2027_lisnard_programme.json"
    plages = reports[1:-1]
    assert len(plages) == 3 * sum(len(m.chiffrage.plages)
                                  for m in pg.charger("lisnard").chiffrees())
    assert all(r.startswith("plages/") for r in plages)


def test_a_mixed_first_year_is_two_calls_and_only_in_a_programme_study() -> None:
    """GARDE (D-328). Un texte de loi refuse toujours un scénario des deux chaînes ; une
    étude de programme le chiffre en deux appels."""
    kind, _endpoint, payload = etude.first_year_payload("pres2027_attal_programme",
                                                       mixte=True)
    assert kind == "mixte" and set(payload) == {"menages", "entreprises"}
    assert payload["menages"]["behavioural"] is payload["menages"]["macro"] is True
    assert payload["entreprises"]["reform"] == {"cvae_echelle": 0.0}
    with pytest.raises(etude.EtudeError, match="deux appels"):
        etude.first_year_payload("pres2027_attal_programme")
    assert etude.definition("presidentielle_attal").mixte
    assert not etude.definition("plf2027").mixte


@pytest.mark.parametrize("point, attendu", [("bas", 0.0), ("candidat", 0.055),
                                            ("haut", 0.2)])
def test_a_range_point_is_the_measure_alone_at_its_value(point, attendu) -> None:
    """GARDE (D-328). Le point d'une plage est la mesure seule, ce champ à sa valeur, dans
    le cadre de l'étude, mécanique."""
    r = etude.plage_request("ir", "le_pen", "lp20_tva_energie", "tva_postes.energie", point)
    assert r["reform"] == {"tva_postes": {"energie": attendu}}
    assert r["firm_reform"] is None
    assert r["behavioural"] is r["macro"] is False
    cadre = json.loads((ROOT / "etude" / "ir.json").read_text(encoding="utf-8"))
    for key in ("spending", "growth", "rate", "horizon", "theta", "uprating"):
        assert r[key] == cadre[key]


def test_a_range_point_outside_the_programme_is_refused() -> None:
    with pytest.raises(etude.EtudeError, match="pas de plage"):
        etude.plage_request("ir", "le_pen", "lp20_tva_energie", "tva_taux_normal", "bas")
    with pytest.raises(etude.EtudeError, match="pas de plage"):
        etude.plage_request("ir", "le_pen", "lp20_tva_energie", "tva_postes.energie",
                            "milieu")


def test_a_firm_law_that_moves_in_the_horizon_has_its_debt_said_absent() -> None:
    """GARDE (D-328). La CVAE change de droit en 2028 : le chemin reporté la refuse
    (D-254), et le point dit pourquoi sa dette manque, au lieu de la reporter."""
    r = etude.plage_request("ir", "attal", "a18_suppression_cvae", "cvae_echelle", "bas")
    assert "D-254" in etude.dette_absente(r)
    r = etude.plage_request("ir", "le_pen", "lp20_tva_energie", "tva_postes.energie", "bas")
    assert etude.dette_absente(r) is None


@pytest.mark.parametrize("change, match", [
    ({"programme": "absent_du_depot"}, "ne se lit pas"),
    ({"texte": "plf2027"}, "nomme son programme"),
    ({"scenarios": [{"scenario": "pres2027_le_pen_lp20_tva_energie"}]}, "un scénario"),
])
def test_a_programme_study_that_does_not_say_its_programme_is_refused(
        tmp_path, change, match) -> None:
    raw = json.loads((ROOT / "etudes" / "presidentielle_le_pen.json").read_text(
        encoding="utf-8"))
    (tmp_path / "presidentielle_le_pen.json").write_text(
        json.dumps({**raw, **change}), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match=match):
        etude.definition("presidentielle_le_pen", tmp_path)


def test_a_law_study_that_names_a_programme_is_refused(tmp_path) -> None:
    raw = json.loads((ROOT / "etudes" / "plf2027.json").read_text(encoding="utf-8"))
    (tmp_path / "plf2027.json").write_text(json.dumps({**raw, "programme": "le_pen"}),
                                           encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="nomme son programme"):
        etude.definition("plf2027", tmp_path)


def test_a_range_report_that_is_not_the_study_s_is_refused(tmp_path) -> None:
    """GARDE (D-328). Un point d'une autre requête, d'un autre commit, ou sans lieu, n'est
    pas lu."""
    study = etude.replace(etude.definition("presidentielle_roussel"), rapports=tmp_path)
    (tmp_path / etude.PLAGES).mkdir()
    reports = {}
    for mesure, champ, point in study.points():
        report = {"programme": "roussel", "mesure": mesure, "champ": champ,
                  "point": point, "commit": "abc", "dirty": False, "where": "essai",
                  "request": etude.plage_request("ir", "roussel", mesure, champ, point)}
        reports[point] = report
        (tmp_path / etude.PLAGES / etude.plage_name(mesure, champ, point)).write_text(
            json.dumps(report), encoding="utf-8")
    assert len(study.load_plages("abc")) == 3
    with pytest.raises(etude.EtudeError, match="sur son commit"):
        study.load_plages("autre")
    mesure, champ, _ = study.points()[0]
    faux = {**reports["bas"], "request": {**reports["bas"]["request"], "theta":
                                          {"common": 0.9}}}
    (tmp_path / etude.PLAGES / etude.plage_name(mesure, champ, "bas")).write_text(
        json.dumps(faux), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="pas le point de l'étude"):
        study.load_plages("abc")
    (tmp_path / etude.PLAGES / "en_trop.json").write_text("{}", encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="en_trop"):
        study.load_plages("abc")
