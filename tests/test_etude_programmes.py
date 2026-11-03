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
    generated = _script().etudes()
    assert sorted(d["nom"] for _, _, d in generated) == sorted(s.nom for s in _studies())
    for slug, scenario, definition in generated:
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
    r = etude.plage_request("central", "le_pen", "lp20_tva_energie", "tva_postes.energie", point)
    assert r["reform"] == {"tva_postes": {"energie": attendu}}
    assert r["firm_reform"] is None
    assert r["behavioural"] is r["macro"] is False
    cadre = etude.lire_cadre("central")
    for key in ("spending", "growth", "rate", "horizon", "theta", "uprating"):
        assert r[key] == cadre[key]


def test_a_range_point_outside_the_programme_is_refused() -> None:
    with pytest.raises(etude.EtudeError, match="pas de plage"):
        etude.plage_request("central", "le_pen", "lp20_tva_energie", "tva_taux_normal", "bas")
    with pytest.raises(etude.EtudeError, match="pas de plage"):
        etude.plage_request("central", "le_pen", "lp20_tva_energie", "tva_postes.energie",
                            "milieu")


def test_a_firm_law_that_moves_in_the_horizon_has_its_debt_said_absent() -> None:
    """GARDE (D-328). La CVAE change de droit en 2028 : le chemin reporté la refuse
    (D-254), et le point dit pourquoi sa dette manque, au lieu de la reporter."""
    r = etude.plage_request("central", "attal", "a18_suppression_cvae", "cvae_echelle", "bas")
    assert "D-254" in etude.dette_absente(r)
    r = etude.plage_request("central", "le_pen", "lp20_tva_energie", "tva_postes.energie", "bas")
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
                  "request": etude.plage_request("central", "roussel", mesure, champ, point)}
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


def test_the_candidates_page_lists_the_24_with_their_coverage() -> None:
    """La page des 24 candidats : chacun avec sa couverture, ses portes, et son étude s'il
    en a une ; aucun chiffre de coût pour ceux dont rien ne se chiffre."""
    lines, n = etude.presidentielle(etude.definitions())
    text = "\n".join(n.resolve(line) for line in lines)
    for slug in pg.lister():
        p = pg.charger(slug)
        row = next(line for line in text.splitlines() if line.startswith(f"| {p.candidat} ("))
        c = p.couverture()
        assert f"| {c['mesures']} | {c['parametrees']} | {c['chiffrees']} |" in row
        assert ("| oui |" in row) == bool(p.chiffrees())
    assert "Md€" not in text


def test_an_amount_on_the_candidates_page_without_its_etage_is_refused(monkeypatch) -> None:
    """GARDE. Un montant que la page cite sans son étage n'atteint ni la page ni le site."""
    monkeypatch.setitem(pg.PORTES, "salaires", "le SMIC à 1 600 €")
    etude.presidentielle(etude.definitions())
    monkeypatch.setattr(etude, "amounts", lambda text, etage, n: text)
    with pytest.raises(etude.EtudeError, match="sans son étage"):
        etude.presidentielle(etude.definitions())


def test_a_pass_of_the_path_frees_what_the_years_before_kept() -> None:
    """GARDE (D-330). Un chemin de dix ans gardait les systèmes réformés de chaque année et
    les arbres de la référence à chaque instant : celui d'Attal montait de 2 Go par passe et
    était tué dans sa deuxième année. Chaque passe libère ce que la suivante ne lit pas."""
    import inspect

    from impots.api.schemas import ReformSpec
    from impots.engine import system
    from impots.entreprises import system as firm_system
    from impots.entreprises.reforms import FirmReformSpec
    from impots.population import cli

    system.reformed_for(ReformSpec(decote_taux=0.4), 2026)
    firm_system.reformed_for(FirmReformSpec(c3s_taux=0.001), 2026)
    assert system.reformed.cache_info().currsize >= 1
    assert firm_system.reformed.cache_info().currsize >= 1
    base = system.baseline()
    base.get_parameters_at_instant("2026-01-01")
    before = base.get_parameters_at_instant
    cli._liberer()
    assert system.reformed.cache_info().currsize == 0
    assert firm_system.reformed.cache_info().currsize == 0
    assert base.get_parameters_at_instant is not before
    assert base.get_parameters_at_instant("2026-01-01") is not None
    # Structural: the whole pass of the path frees before it prices.
    source = inspect.getsource(cli.cmd_predictif)
    assert source.index("passe du simulateur") < source.index("_liberer()") < source.index(
        "api._price_first_year,")


# --- les pages, sur les rapports commités (D-328, D-329) ------------------------------


@pytest.fixture(scope="module")
def pages() -> dict[str, tuple[etude.Etude, str]]:
    return {s.programme: (s, s.render(s.load())) for s in _studies()}


def test_every_page_says_its_debt_is_not_the_programme_s(pages) -> None:
    """GARDE (D-319). La dette d'une page est celle de la part chiffrée, jamais celle du
    programme : l'avertissement est en tête, avec la couverture."""
    for slug, (_, text) in pages.items():
        head = text.split("## En bref")[0]
        assert etude.AVERTISSEMENT_PROGRAMME in head, slug
        c = pg.charger(slug).couverture()
        assert f"porte {c['mesures']} mesures, dont {c['parametrees']} énoncent" in head


def test_every_measure_is_on_its_page_with_its_door(pages) -> None:
    for slug, (_, text) in pages.items():
        mesures = text.split("## Le programme, mesure par mesure")[1]
        for m in pg.charger(slug).mesures:
            row = next(line for line in mesures.splitlines() if line.startswith("| ")
                       and m.libelle.split(" ")[0] in line)
            assert row
            if m.refus is not None and m.refus.porte != "vague":
                assert f"porte `{m.refus.porte}`" in mesures, (slug, m.id)


def test_every_range_point_is_on_the_page(pages) -> None:
    for slug, (study, text) in pages.items():
        plages = text.split("## Ce que bouge chaque paramètre")[1].split("## Le programme")[0]
        for m in pg.charger(slug).chiffrees():
            for plage in m.chiffrage.plages:
                assert f"| `{plage.champ}` |" in plages, (slug, plage.champ)
        rows = [line for line in plages.splitlines()
                if line.startswith(("| le bas |", "| le candidat |", "| le haut |"))]
        assert len(rows) == len(study.points()), slug


def test_the_announced_layer_stays_apart(pages) -> None:
    """La couche annoncée a sa section, et ni l'en-bref ni la part chiffrée ne la lisent."""
    for slug, (_, text) in pages.items():
        assert "## Ce que le candidat annonce, à part" in text
        assert "annonc" not in text.split("## La part chiffrée")[1].split(
            "## Ce que bouge")[0].lower(), slug


def test_a_mixed_part_shows_both_layers(pages) -> None:
    for slug in ("attal", "lisnard", "retailleau"):
        text = pages[slug][1]
        assert "pour les ménages, sur la population de 2024" in text
        assert "| taille | entreprises | touchées | impôt en plus |" in text
        assert "La bande et l'éventail ne lisent que la part des ménages" in text


def test_a_pass_of_the_path_runs_in_a_process_of_its_own() -> None:
    """GARDE (D-331). Une passe du chemin prend jusqu'à dix gigaoctets, qu'un processus ne
    rend pas tous : les chemins de Tondelier et de Lisnard étaient tués. Chaque passe
    tourne dans un processus neuf, qui rend tout en finissant, et sa valeur revient."""
    import inspect
    import os

    from impots.population import cli

    assert cli._isole(os.getpid) != os.getpid()
    assert cli._isole(divmod, 17, 5) == (3, 2)
    source = inspect.getsource(cli.cmd_predictif)
    assert "_isole(\n                api._price_first_year," in source
