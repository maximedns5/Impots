"""La page 1 du parcours, « Un ménage » (D-375) : elle montre les nombres du fichier
chiffré d'avance et ceux du contrôle DGFiP, et le fichier tient les valeurs d'or.

Léger : rien n'y lance le moteur. Le fichier se refait par la commande de la docstring de
`impots.parcours.menage`."""

from __future__ import annotations

import json
import re

import pytest

from impots.parcours import _check, menage


@pytest.fixture(scope="module")
def page():
    return menage.page()


@pytest.fixture(scope="module")
def donnees():
    return menage.donnees()


def test_la_page_tient_les_regles_du_parcours(page):
    _check("menage", page)


def test_le_controle_dgfip_est_lu_et_retrouve_a_l_euro(page, donnees):
    ref = menage.dgfip()
    # Les montants relevés sur le simulateur, tels que CROSSCHECK.md les écrit.
    assert (ref["single_30k"]["ir"], ref["couple_70k_2kids"]["ir"]) == (812, 1274)
    for nom in menage.CONTROLES:
        valeurs = donnees["types"][nom]["valeurs"]
        assert round(valeurs["ir"]) == ref[nom]["ir"]
        assert round(valeurs["revenu_fiscal_reference"]) == ref[nom]["revenu_fiscal_reference"]
        assert round(valeurs["ir_avant_reductions"]) == ref[nom]["droits_simples"]
        assert valeurs["parts_fiscales"] == ref[nom]["parts_fiscales"]
        assert menage.eur(ref[nom]["ir"]) in page.corps
    assert ref["date"] in page.corps
    assert "à l'euro près" in page.prouve


def test_le_fichier_tient_les_valeurs_d_or(donnees):
    for nom in menage.TYPES:
        for key, want in menage.golden(nom)["expected"].items():
            if key in donnees["types"][nom]["valeurs"]:
                assert donnees["types"][nom]["valeurs"][key] == pytest.approx(want, abs=2)
    reforme = donnees["reforme"]
    assert reforme["ecart"]["ir"] == pytest.approx(
        menage.golden(menage.REFORME)["expected_delta"]["ir"], abs=2)


def test_la_page_montre_les_nombres_du_fichier(page, donnees):
    for nom in menage.TYPES:
        valeurs = donnees["types"][nom]["valeurs"]
        for key in ("ir", "salaire_net", "revenu_disponible"):
            assert menage.eur(valeurs[key]) in page.corps, (nom, key)
    assert menage.eur(donnees["reforme"]["ecart"]["ir"]) in page.corps
    assert donnees["commit"][:10] in page.corps and donnees["date"] in page.corps
    # Le tableau sans script porte chaque point de la grille.
    noscript = page.corps[page.corps.index("<noscript>"):]
    for situation in donnees["situations"]:
        for valeurs in situation["valeurs"]:
            assert menage.eur(valeurs["revenu_disponible"]) in noscript


def test_le_script_porte_chaque_point_de_la_grille(page, donnees):
    blob = json.loads(re.search(r"var D = (\{.*?\});\n", page.script)[1])
    assert blob["lignes"] == [key for key, _, _ in menage.LIGNES]
    i = blob["lignes"].index("revenu_disponible")
    for situation in donnees["situations"]:
        points = blob["points"][situation["cle"]]
        assert len(points) == len(donnees["salaires"])
        for cellules, valeurs in zip(points, situation["valeurs"], strict=True):
            assert cellules[i] == menage.eur(valeurs["revenu_disponible"])


def test_les_lignes_retombent_sur_le_revenu_disponible(donnees):
    """La commande le refuse à l'écriture ; le fichier commité le tient encore."""
    points = [v for s in donnees["situations"] for v in s["valeurs"]]
    points += [t["valeurs"] for t in donnees["types"].values()]
    for v in points:
        assert v["revenu_disponible"] == pytest.approx(
            v["salaire_net"] + v["prestations"] - v["ir"], abs=1.0)


def test_la_phrase_prouvee_ne_depasse_pas_le_controle(page):
    """Relecture adverse : le contrôle DGFiP part du salaire imposable du moteur et ne
    porte que sur l'impôt de deux ménages ; la page dit ce qu'il ne prouve pas."""
    assert ":" not in page.prouve  # précédée de « Ce que cette page prouve : »
    assert "la loi est codée juste" not in page.prouve
    assert "deux ménages" in page.prouve and "ne sont pas contrôlées" in page.prouve
    assert "Ce qu'il ne prouve pas." in page.corps


def test_la_phrase_prouvee_dit_ce_que_les_deux_menages_ne_testent_pas(page):
    """Seconde relecture adverse : les deux ménages contrôlés sont en décote, sous la
    tranche à 45 % et loin du plafonnement du quotient familial ; la phrase le dit."""
    assert "tous deux en décote" in page.prouve
    assert "tranche à 45\u202f%" in page.prouve
    assert "plafonnement du quotient familial" in page.prouve


def test_l_abattement_est_dit_plafonne_au_plafond_des_parametres(page, donnees):
    """Le célibataire à 240 000 € est plafonné : 198 726 − 14 426 = 184 300 €, et le
    libellé du revenu fiscal donne ce plafond, lu dans les paramètres d'OpenFisca."""
    taux, plafond = menage.abattement(donnees)
    assert (taux, plafond) == (0.1, 14_426)
    assert "plafonné à " + menage.eur(plafond) in page.corps
    assert "après l&#x27;abattement de 10\u202f%)" not in page.corps
