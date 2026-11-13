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


def _chiffrees() -> list[etude.Etude]:
    """Les études de programme dont les passes ont toutes tourné : une étude refusée
    (D-398) n'a pas de chemin annuel, donc pas de page."""
    return [s for s in _studies() if not s.refus]


def test_every_programme_with_a_priced_measure_has_its_study() -> None:
    """GARDE. Seize études, une par candidat dont une mesure se chiffre, et aucune autre
    (D-394) ; une seule est refusée, Dupont-Aignan (D-398)."""
    chiffres = sorted(s for s in pg.lister() if pg.charger(s).chiffrees())
    assert sorted(s.programme for s in _studies()) == chiffres
    assert len(chiffres) == 16
    assert [s.programme for s in _studies() if s.refus] == ["dupont_aignan"]
    # La refusée n'a pas de chemin annuel : ses rapports ne se lisent pas en page.
    refusee = etude.definition("presidentielle_dupont_aignan")
    with pytest.raises(etude.EtudeError, match="predictif_pres2027_dupont_aignan_programme"):
        refusee.load()


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
        reports[mesure, champ, point] = report
        (tmp_path / etude.PLAGES / etude.plage_name(mesure, champ, point)).write_text(
            json.dumps(report), encoding="utf-8")
    # Roussel porte deux mesures chiffrées en plage depuis D-394 : six points.
    assert len(study.points()) == 6
    assert len(study.load_plages()) == len(study.points())
    # A point on another commit is read only if a witness joins it to the first (D-335).
    assert study.commits({"abc"}) == [("abc", None)]
    with pytest.raises(etude.EtudeError, match="impots etude temoin"):
        study.commits({"abc", "autre"})
    mesure, champ, _ = study.points()[0]
    bas = reports[mesure, champ, "bas"]
    faux = {**bas, "request": {**bas["request"], "theta": {"common": 0.9}}}
    (tmp_path / etude.PLAGES / etude.plage_name(mesure, champ, "bas")).write_text(
        json.dumps(faux), encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="pas le point de l'étude"):
        study.load_plages()
    (tmp_path / etude.PLAGES / "en_trop.json").write_text("{}", encoding="utf-8")
    with pytest.raises(etude.EtudeError, match="en_trop"):
        study.load_plages()


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
        refusee = any(s.programme == slug and s.refus for s in _studies())
        assert ("| oui |" in row) == (bool(p.chiffrees()) and not refusee)
        assert ("| refusée |" in row) == refusee
    assert "| refusée |" in next(line for line in text.splitlines()
                                 if line.startswith("| Nicolas Dupont-Aignan ("))
    assert "Md€" not in text


def test_an_amount_on_the_candidates_page_without_its_etage_is_refused(monkeypatch) -> None:
    """GARDE. Un montant que la page cite sans son étage n'atteint ni la page ni le site."""
    monkeypatch.setitem(pg.PORTES, "salaires", "le SMIC à 1 600 €")
    etude.presidentielle(etude.definitions())
    monkeypatch.setattr(etude, "amounts", lambda text, etage, n: text)
    with pytest.raises(etude.EtudeError, match="sans son étage"):
        etude.presidentielle(etude.definitions())


# --- les pages, sur les rapports commités (D-328, D-329) ------------------------------


@pytest.fixture(scope="module")
def pages() -> dict[str, tuple[etude.Etude, str]]:
    return {s.programme: (s, s.render(s.load())) for s in _chiffrees()}


def test_every_page_says_its_debt_is_not_the_programme_s(pages) -> None:
    """GARDE (D-319). La dette d'une page est celle de la part chiffrée, jamais celle du
    programme : l'avertissement est en tête, avec la couverture."""
    for slug, (_, text) in pages.items():
        head = text.split("## En bref")[0]
        assert etude.AVERTISSEMENT_PROGRAMME in head, slug
        c = pg.charger(slug).couverture()
        part = f"{c['part_des_parametrees'] * 100:.0f} %"
        assert (f"| {c['mesures']} | {c['parametrees']} | {c['chiffrees']} | {part} |"
                in head), slug


def test_every_measure_is_on_its_page_with_its_door(pages) -> None:
    for slug, (_, text) in pages.items():
        mesures = text.split("## Le programme, mesure par mesure")[1]
        for m in pg.charger(slug).mesures:
            row = next(line for line in mesures.splitlines() if line.startswith("| ")
                       and m.libelle.split(" ")[0] in line)
            assert row
            if m.refus is not None and m.refus.porte != "vague":
                assert f"refusée : {etude.porte_lue(m.refus.porte)}" in mesures, (slug, m.id)


def test_every_range_point_is_on_the_page(pages) -> None:
    for slug, (study, text) in pages.items():
        plages = text.split("## Ce que bouge chaque paramètre")[1].split("## Le programme")[0]
        for m in pg.charger(slug).chiffrees():
            for plage in m.chiffrage.plages:
                assert f"| `{plage.champ}` |" in plages, (slug, plage.champ)
        rows = [line for line in plages.splitlines()
                if line.startswith(("| le bas |", "| le candidat |", "| le haut |"))]
        assert len(rows) == len(study.points()), slug


def test_a_programme_page_says_measures_not_articles(pages) -> None:
    """D-336 : un programme a des mesures ; la loi seule a des articles."""
    for slug, (_, text) in pages.items():
        assert "l'effet macro de chaque mesure" in text, slug
        assert "chaque article" not in text, slug


def test_the_announced_layer_stays_apart(pages) -> None:
    """La couche annoncée a sa section, et ni l'en-bref ni la part chiffrée ne la lisent."""
    for slug, (_, text) in pages.items():
        assert "## Ce que le candidat annonce, à part" in text
        part = text.split("## La part chiffrée")[1].split("## Ce que bouge")[0]
        # La dette « si les économies annoncées sont tenues » a sa sous-section, à côté de
        # la dette (D-380) : la part chiffrée ne lit l'annonce nulle part ailleurs.
        titre = "### La dette en 2035, si les économies annoncées sont tenues"
        if titre in part:
            debut = part.index(titre)
            part = part[:debut] + part[part.index("### L'écart", debut):]
        assert "annonc" not in part.lower(), slug


def test_a_mixed_part_shows_both_layers(pages) -> None:
    for slug in ("attal", "lisnard", "retailleau"):
        text = pages[slug][1]
        assert "pour les ménages, sur la population de 2024" in text
        assert "| taille | entreprises | touchées | impôt en plus |" in text
        assert "La bande et l'éventail ne lisent que la part des ménages" in text


def test_the_debt_without_activity_is_the_cost_without_the_loop(pages) -> None:
    """But 19, étape 1. « Sans aucun effet sur l'activité » lit la marche « le coût, sans
    boucle » de la décomposition (D-349), pas le coin θ = 0 de la boîte, qui met le
    multiplicateur au bas de sa fourchette publiée et non à zéro : chez Attal, 18,30
    points à l'étape 1, quand le coin en donnait 13,95 ; 20,28 sur les rapports de la
    série du but 19 (D-373), au coût de 65,69 Md€ ; 20,45 sur ceux du but 21 (D-397), au
    coût de 66,18 Md€, les pensions alimentaires s'ajoutant."""
    study, text = pages["attal"]
    path = json.loads(next(study.rapports.glob("predictif_*.json")).read_text("utf-8"))
    cout = path["lectures"]["decomposition"]["vieillie"]["cout"]
    assert f"{cout * 100:.2f}" == "20.45"
    head = text.split("## En bref")[0]
    assert "Sans aucun effet sur l'activité, la dette serait plus haute de 20,45 points" in head
    assert "13,95" not in head
    for slug, (_, page) in pages.items():
        assert "Sans aucun effet sur l'activité" in page.split("## En bref")[0], slug


def test_the_employees_contributions_say_the_model_s_choice_not_a_missing_study(
        pages) -> None:
    """But 19, étape 1. Une baisse des cotisations des salariés n'a pas de bande parce que
    le modèle n'ouvre l'offre de travail qu'à la CSG (D-220), pas faute d'étude publiée."""
    for slug in ("attal", "retailleau"):
        text = pages[slug][1]
        head = text.split("## En bref")[0]
        assert "aucune étude publiée ne le permet ici" not in head, slug
        assert "un choix du modèle" in head, slug
        assert etude.RAISON_OFFRE_DE_TRAVAIL in text, slug
    for slug in ("labib", "roussel", "le_pen"):
        assert etude.RAISON_OFFRE_DE_TRAVAIL not in pages[slug][1], slug


def test_the_fan_says_what_the_debt_does_not_read(pages) -> None:
    """But 20. Un éventail qui prête un multiplicateur publié aux accises sur l'énergie,
    que la boucle de la dette ne lit pas, le dit à côté de lui, avec leur part de la
    première année. Depuis la série du but 21 (D-397), l'éventail de Labib est refusé : son
    SMIC pousse les cotisations des employeurs en sens contraire de ses baisses, et aucune
    page commitée ne porte plus le paragraphe. Il est tenu sur le rapport commité de
    Labib, lu par un éventail qui compterait toutes ses mesures."""
    import types

    study, text = pages["labib"]
    section = text.split("### 2.")[1].split("### 3.")[0]
    assert "**Éventail macro : refusé.**" in section
    for slug, (_, page) in pages.items():
        assert "que la dette ne lit pas" not in page, slug
    path = json.loads(next(study.rapports.glob("predictif_*.json")).read_text("utf-8"))
    entry = {"path": path}
    impulses, _ = study._impulses(entry)
    n = etude.Nombres()
    paragraph = n.resolve(study._eventail_hors_boucle(
        n, entry, types.SimpleNamespace(instruments=list(impulses))))
    assert paragraph.startswith("**Ce que l'éventail compte et que la dette ne lit pas.**")
    assert "les accises sur l'énergie, 15,75 Md€ des 62,46 Md€" in paragraph
    assert study._eventail_hors_boucle(
        n, entry, types.SimpleNamespace(instruments=["tva"])) == ""


def test_the_employees_contributions_say_the_bias_beside_the_headline(pages) -> None:
    """But 20. Quand la boucle lit les cotisations des salariés, la page dit le sens du
    biais de la variante de Mésange, et met en regard la dette sans boucle et la variante
    salariale, des nombres du rapport."""
    for slug in ("attal", "retailleau"):
        study, text = pages[slug]
        path = json.loads(next(study.rapports.glob("predictif_*.json")).read_text("utf-8"))
        theta = path["lectures"]["variante_salariale"]["boite"]["vieillie"]["theta"]
        variante = f"{abs(theta) * 100:.2f}".replace(".", ",")
        for part in (text.split("## En bref")[0], text.split("### 3.")[1]):
            assert "(G2017/04, folio 110)" in part, slug
            assert "probablement surestimé" in part, slug
            assert f"la dette serait plus haute de {variante} points" in part, slug
        cout = path["lectures"]["decomposition"]["vieillie"]["cout"]
        assert (f"sans aucun effet sur l'activité, la dette serait plus haute de "
                f"{cout * 100:.2f}".replace(".", ",") in text.split("### 3.")[1]), slug
    assert "folio 110" not in pages["lisnard"][1]


def test_the_taxable_income_and_the_income_tax_loop_say_a_double_count(pages) -> None:
    """But 20. C1 ouvert et la boucle qui lit l'impôt sur le revenu : la page dit que la
    même réaction peut être comptée deux fois, et que l'outil ne le mesure pas."""
    for slug in ("tondelier", "lisnard"):
        assert "comptée deux fois" in pages[slug][1].split("## En bref")[0], slug
    for slug in ("attal", "retailleau", "labib", "roussel"):
        assert "comptée deux fois" not in pages[slug][1], slug


def test_a_measure_priced_in_part_says_it_in_its_row(pages) -> None:
    mesures = pages["retailleau"][1].split("## Le programme, mesure par mesure")[1]
    row = next(line for line in mesures.splitlines()
               if line.startswith("| Suppression de la C3S et de la CVAE ; forfait social"))
    assert "| chiffrée en partie |" in row


def test_the_announced_share_is_not_called_rho(pages) -> None:
    """But 20. ρ est la corrélation de la copule du Monte-Carlo ; la part réalisée des
    montants annoncés porte un autre nom."""
    for slug, (_, text) in pages.items():
        annonce = text.split("## Ce que le candidat annonce, à part")[1].split("\n## ")[0]
        assert "ρ" not in annonce, slug


def test_a_pass_run_in_a_process_of_its_own_gives_its_value_back() -> None:
    """D-331 : chaque passe du chemin tourne dans un processus neuf, et le nombre qu'elle
    chiffre en revient tel quel. Que `cmd_predictif` l'y fasse tourner est de la plomberie,
    qui n'a plus de test qui lit le source (D-335, D-336)."""
    import os

    from impots.population import cli

    assert cli._isole(os.getpid) != os.getpid()
    assert cli._isole(divmod, 17, 5) == (3, 2)
