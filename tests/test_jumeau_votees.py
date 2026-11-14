"""But 23, lot 5 — la base des mesures votées et la frise des gouvernements (D-410).

Des faits juridiques versionnés, lus sans données : la base se lit, chaque mesure a son
texte, sa date et son article, et est rangée sous le gouvernement en fonction à la date
de son texte ; aucune ne porte de montant budgétaire ; la frise couvre chaque jour de
2010 à aujourd'hui, sans trou ni chevauchement, et finit sur le mandat de 2027.
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
