"""But 23, lot 5 — la base des mesures votées et la frise des gouvernements (D-410).

Des faits juridiques versionnés, lus sans données : la base se lit, chaque mesure a son
texte, sa date et son article, et est rangée sous le gouvernement en fonction à la date
de son texte ; aucune ne porte de montant budgétaire ; la frise couvre chaque jour de
2010 à aujourd'hui, sans trou ni chevauchement, et finit sur le mandat de 2027. Chaque
mesure dit si elle est vérifiée sur une source primaire, et laquelle (D-413).
"""

from __future__ import annotations

import datetime as dt

import pytest
import yaml

from impots.jumeau import votees


def test_la_frise_couvre_chaque_jour_de_2010_a_aujourd_hui() -> None:
    jour, fin = dt.date(2010, 1, 1), dt.date.today()
    vus = set()
    while jour <= fin:
        vus.add(votees.gouvernement_au(jour).id)
        votees.president_au(jour)
        jour += dt.timedelta(days=1)
    _, gouvernements, _ = votees.frise()
    assert vus == {g.id for g in gouvernements}
    assert gouvernements[-1].fin is None


def test_la_frise_porte_les_dates_connues() -> None:
    assert votees.gouvernement_au(dt.date(2017, 12, 30)).premier_ministre == (
        "Édouard Philippe")
    assert votees.gouvernement_au(dt.date(2025, 2, 14)).id == "bayrou"
    assert votees.president_au(dt.date(2012, 5, 15)).nom == "François Hollande"
    a_venir = votees.a_venir()
    assert a_venir["premier_jour_du_successeur"] == dt.date(2027, 5, 14)
    assert votees.president_au(dt.date(2027, 5, 13)).nom == "Emmanuel Macron"
    with pytest.raises(votees.VoteesError, match="aucun président"):
        votees.president_au(dt.date(2027, 5, 14))


def test_une_frise_trouee_est_refusee() -> None:
    with pytest.raises(votees.VoteesError, match="un trou ou un chevauchement"):
        votees._contigu([("a", dt.date(2010, 1, 1), dt.date(2010, 6, 30)),
                         ("b", dt.date(2010, 7, 2), None)], "gouvernements")


def test_la_base_se_lit_et_chaque_mesure_a_sa_loi_sa_date_et_son_article() -> None:
    mesures = votees.mesures()
    assert len(mesures) >= 60
    for m in mesures:
        assert m.texte.numero and m.texte.date and m.article.strip(), m.id
        assert votees.gouvernement_au(m.texte.date).id == m.gouvernement, m.id
        assert m.parametres, m.id
    gouvernements = {m.gouvernement for m in mesures}
    assert len(gouvernements) >= 10
    assert {m.id for m in votees.mesures_du_gouvernement("philippe_2")} >= {
        "lfi2018_pfu", "lfi2018_ifi", "lfi2020_th_suppression"}


def test_les_grandes_reformes_que_le_lot_6_rejouera_y_sont() -> None:
    ids = {m.id for m in votees.mesures()}
    assert ids >= {"lfi2013_tranche_45", "lfr2012_3_cice", "lfrss2014_pacte_allegements",
                   "lfi2018_pfu", "lfi2018_ifi", "lfi2020_th_suppression",
                   "lfi2018_is_25", "lfi2021_cvae_regions", "lfi2023_cvae",
                   "lfrss2023_age_64", "lfr2012_3_tva_2014"}


def test_aucune_mesure_ne_porte_de_montant() -> None:
    """La base est le droit voté ; ce qu'il a coûté est le juge du passé (D-359 à D-361),
    que le lot 6 préenregistre avant de l'ouvrir. Le fichier est relu ici, et le
    lecteur refuse un montant budgétaire qu'on y glisserait."""
    brutes = yaml.safe_load(votees.MESURES.read_text(encoding="utf-8"))["mesures"]
    votees._sans_chiffrage(brutes, "mesures")
    for m in brutes:
        assert not set(m) & votees.CLES_INTERDITES, m["id"]
    with pytest.raises(votees.VoteesError, match="montant budgétaire"):
        votees._sans_chiffrage([{"parametres": [{"apres": "un coût de 3 Md€"}]}], "x")
    with pytest.raises(votees.VoteesError, match="clé « cout »"):
        votees._sans_chiffrage({"cout": 1}, "x")


#: Le décompte de D-413 : les 70 mesures de D-410, relues au Journal officiel, et les 25
#: ajoutées, toutes relues au même endroit ; plus, en D-421, le volet des cotisations
#: salariales de la LFSS 2018 (art. 8) sous son instrument. Un ajout ou un déclassement
#: change ce décompte et la D-entrée qui le dit.
VERIFIEES, NON_VERIFIEES = 96, 0


def test_chaque_mesure_dit_sa_verification_et_sa_source() -> None:
    mesures = votees.mesures()
    for m in mesures:
        v = m.verification
        assert v.statut in votees.VERIFICATIONS, m.id
        if v.statut == "vérifiée":
            assert v.sources, m.id
            assert all(u.startswith("https://www.legifrance.gouv.fr/jorf/article_jo/JORFARTI")
                       for u in v.sources), m.id
        else:
            assert v.raison and v.raison.strip(), m.id
    statuts = [m.verification.statut for m in mesures]
    assert (statuts.count("vérifiée"), statuts.count("non vérifiée")) == (
        VERIFIEES, NON_VERIFIEES)


def test_une_verification_incomplete_est_refusee() -> None:
    with pytest.raises(votees.VoteesError, match="vérifiée sans URL"):
        votees._verification({"statut": "vérifiée", "sources": []}, "x")
    with pytest.raises(votees.VoteesError, match="vérifiée sans URL"):
        votees._verification({"statut": "vérifiée", "sources": ["codes.droit.org"]}, "x")
    with pytest.raises(votees.VoteesError, match="sans raison"):
        votees._verification({"statut": "non vérifiée"}, "x")
    with pytest.raises(votees.VoteesError, match="sans statut"):
        votees._verification("mémoire", "x")


def test_les_corrections_de_d413_tiennent() -> None:
    """Les articles et les paramètres corrigés sur le Journal officiel (D-413)."""
    par_id = {m.id: m for m in votees.mesures()}
    assert par_id["lfi2014_plafond_qf"].article == "3"
    assert par_id["lfr2022_audiovisuel"].article == "6"
    assert par_id["lfss2026_suspension_retraites"].article == "105"
    revalo = par_id["lfss2019_revalorisation_0_3"].parametres[0]["apres"]
    assert "2019" in revalo and "2020" not in revalo
    carbone = par_id["lfi2018_composante_carbone"].parametres[0]
    assert "gazole" in carbone["quoi"] and "44,60" not in carbone["apres"]
    assert "29,101 %" in par_id["decret_2018_prime_activite"].parametres[0]["apres"]
    assert "0,4 %" in par_id["lfr2012_ttf"].parametres[0]["apres"]


def test_les_ajouts_de_d413_y_sont() -> None:
    par_id = {m.id: m for m in votees.mesures()}
    csg = par_id["lfss2026_csg_patrimoine"]
    assert (csg.texte.numero, csg.article) == ("2025-1403", "12")
    assert csg.parametres[0]["avant"] == "9,2 %" and csg.parametres[0]["apres"] == "10,6 %"
    assert par_id["lfss2019_csg_patrimoine"].suite == "lfss2026_csg_patrimoine"
    # La chaîne des barèmes de l'impôt sur le revenu, de 2010 à 2026, sans trou.
    suivant, vus = "bareme_2010", []
    while suivant is not None:
        vus.append(suivant)
        suivant = par_id[suivant].suite
    assert vus[-1] == "bareme_2026" and par_id["bareme_2026"].statut == "en_vigueur"
    assert {par_id[i].annee_effet for i in vus} == set(range(2010, 2027)) - {2012, 2013}
    assert {"chomage_2019", "chomage_2023", "aah_deconjugalisation",
            "lfss2015_modulation_af", "lfi2026_holdings", "lfi2026_cdhr"} <= set(par_id)


def test_les_mesures_etalees_portent_chacune_de_leurs_annees() -> None:
    """D-421 : chaque année où la loi change le droit appliqué, lue au JO ; une étape
    entrée en vigueur après le 1er janvier compte aussi l'année qui suit."""
    par_id = {m.id: m for m in votees.mesures()}
    assert par_id["lfi2018_is_25"].annees_effet == (2018, 2019, 2020, 2021, 2022)
    assert par_id["lfi2018_th_degrevement"].annees_effet == (2018, 2019, 2020)
    assert par_id["lfi2020_th_suppression"].annees_effet == (2020, 2021, 2022, 2023)
    assert par_id["lfi2018_cice_6_suppression"].annees_effet == (2018, 2019)
    assert par_id["lfss2018_cotisations_salariales"].annees_effet == (2018, 2019)
    assert par_id["lfss2018_cice_allegements"].annees_effet == (2019, 2020)
    assert par_id["lfi2023_cvae"].annees_effet == (2023,)
    # Le CICE est un instrument à part, et sa conversion reste aux cotisations patronales.
    assert {m.id for m in votees.mesures() if m.instrument == "cice"} == {
        "lfr2012_3_cice", "lfi2017_cice_7", "lfi2018_cice_6_suppression"}
    assert par_id["lfss2018_cice_allegements"].instrument == "cotisations_employeurs"


def test_des_etapes_mal_datees_sont_refusees() -> None:
    base = {"annee_effet": 2018}
    with pytest.raises(votees.VoteesError, match="non strictement croissantes"):
        votees._etapes([{"date": dt.date(2019, 1, 1), "quoi": "b"},
                        {"date": dt.date(2018, 1, 1), "quoi": "a"}], base, "x")
    with pytest.raises(votees.VoteesError, match="année d'effet"):
        votees._etapes([{"date": dt.date(2019, 1, 1), "quoi": "a"}], base, "x")
    with pytest.raises(votees.VoteesError, match="date_effet"):
        votees._etapes([{"date": dt.date(2018, 1, 1), "quoi": "a"}],
                       {**base, "date_effet": dt.date(2018, 10, 1)}, "x")
    with pytest.raises(votees.VoteesError, match="quoi non vide"):
        votees._etapes([{"date": dt.date(2018, 1, 1), "quoi": " "}], base, "x")


def test_chaque_mesure_d_un_prelevement_dit_son_sens() -> None:
    """D-421 amendé : le sens, lu dans les paramètres ; une fin de contribution est une
    baisse ; un barème indexé est neutre."""
    par_id = {m.id: m for m in votees.mesures()}
    for m in par_id.values():
        if m.instrument in votees.PRELEVEMENTS:
            assert m.sens in votees.SENS, m.id
    assert par_id["lfi2018_is_25"].sens_en(2022) == {"baisse"}
    assert par_id["bareme_2023"].sens_en(2023) == {"neutre"}
    contribution = par_id["lfi2014_contribution_is_10_7"]
    assert contribution.sens_en(2014) == {"hausse"}
    assert contribution.sens_en(2016) == contribution.sens_en(2017) == {"baisse"}
    assert par_id["lfi2018_cice_6_suppression"].sens_en(2019) == {"hausse"}
    with pytest.raises(votees.VoteesError, match="sens"):
        votees._etapes([{"date": dt.date(2018, 1, 1), "quoi": "a", "sens": "plus"}],
                       {"annee_effet": 2018}, "x")
