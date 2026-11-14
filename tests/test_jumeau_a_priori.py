"""But 23, D-424 : les a priori des θ tirés de la littérature, sur données SYNTHÉTIQUES.

Aucun test ne fait tourner le jumeau sur une année réelle. On tient :

1. chaque θ du registre a sa loi, et un θ sans source garde celle de D-417 ;
2. la loi de θ est l'estimation publiée passée par l'application θ → paramètre du bloc
   (l'inverse de `commerce.a_theta`, une plage décroissante comprise), à la main ;
3. l'estimation avec les lois : sans données, θ va au mode de sa loi (à la borne quand le
   mode sort de la boîte) ; un θ que les données fixent n'en bouge presque pas ; une loi
   large redonne D-417 au bit près ; un a priori serré n'« identifie » pas à lui seul ;
4. les nombres du YAML sont ceux des fichiers (les PDF, les cellules de Bargain, Orsini et
   Peichl, le chômage de l'Insee).
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from impots.behavioural import bop
from impots.jumeau import a_priori as ap
from impots.jumeau import apprentissage as app
from impots.jumeau import thetas
from impots.jumeau.blocs.commerce import a_theta
from impots.macro import mesange as mesange_pdf

RAW = mesange_pdf.RAW
LOIS = ap.lois()
DOC = ap.lire()


# --------------------------------------------------------------------------- #
# 1. une loi par θ
# --------------------------------------------------------------------------- #
def test_chaque_theta_du_registre_a_sa_loi_et_les_sans_source_gardent_d417():
    assert set(LOIS) == set(thetas.REGISTRE)
    for cle, loi in LOIS.items():
        if "sans_source" in DOC[cle]:
            assert loi == ap.LARGE, cle
        else:
            assert loi.source, cle
    # un θ dont la ligne est « choisie, non vérifiée » n'a pas de loi serrée
    for cle, ligne in thetas.REGISTRE.items():
        if not ligne.verifiee and cle not in (thetas.SALAIRES_CHOMAGE,):
            assert LOIS[cle] == ap.LARGE, cle


def test_un_yaml_sans_un_theta_du_registre_est_refuse(tmp_path):
    chemin = tmp_path / "a_priori.yaml"
    texte = ap.FICHIER.read_text(encoding="utf-8")
    chemin.write_text(texte.replace("implantation_tmee:", "implantation_autre:"),
                      encoding="utf-8")
    with pytest.raises(ap.APrioriError, match="implantation_tmee"):
        ap.lois(chemin)


# --------------------------------------------------------------------------- #
# 2. la loi de θ, à la main
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("plage", [(0.6, 0.73, 1.27), (8.0, 5.0, 3.0), (0.0, 0.478, 0.7298)])
def test_theta_de_inverse_l_application_du_bloc(plage):
    for t in np.linspace(0.0, 1.0, 41):
        v = float(a_theta(np.array(t), plage))
        assert ap.theta_de(v, plage) == pytest.approx(t, abs=1e-12)


def test_les_lois_se_calculent_a_la_main():
    z = 1.0 / (2.0 * 1.96)
    # l'emploi : Lichter et al., 0,246 ± 0,0954, sous la plage (0,31 ; 0,44 ; 0,52)
    loi = LOIS[thetas.EMPLOI_COUT]
    assert loi.moyenne == pytest.approx(0.5 - (0.44 - 0.246) / 0.26, abs=1e-12)
    assert loi.ecart_bas == pytest.approx(0.0954 / 0.26, abs=1e-12)
    assert loi.ecart_haut == pytest.approx(0.0954 / 0.26, abs=1e-12)
    # l'accélérateur : la plage est déjà ∓ 1,96 écart-type de β₀ (1,19 / 6,9)
    loi = LOIS["investissement_accelerateur"]
    assert loi.moyenne == pytest.approx(0.5)
    assert loi.ecart_bas == pytest.approx(z, abs=2e-3)
    assert loi.ecart_haut == pytest.approx(loi.ecart_bas, abs=1e-12)
    # l'implantation : deux pentes, deux écarts
    loi = LOIS["implantation_tmee"]
    s = 0.478 / 3.72
    assert loi.ecart_bas == pytest.approx(s / (2 * 0.478), abs=1e-3)
    assert loi.ecart_haut == pytest.approx(s / (2 * (0.7298 - 0.478)), abs=1e-3)
    # les importations : très serrée au-dessus du centre (FR-BDF à 1,11)
    loi = LOIS[thetas.ELASTICITE_PRIX_IMPORTATIONS.cle]
    assert loi.ecart_haut == pytest.approx(0.0613 / (2 * 0.76), abs=1e-9)
    # le coût du capital : Gechert et al., 0,30, sous la plage, mode à −½
    loi = LOIS["investissement_cout_capital"]
    assert loi.moyenne == pytest.approx(-0.5, abs=1e-12)
    # les salaires : la courbe des salaires, b = 0,4673, mode juste sous 0
    assert LOIS[thetas.SALAIRES_CHOMAGE].moyenne == pytest.approx(0.4673 - 0.5, abs=1e-12)
    # le multiplicateur : par construction, la loi de D-417
    assert LOIS["multiplicateur_macro"].moyenne == 0.5
    assert LOIS["multiplicateur_macro"].ecart_type == 0.5


# --------------------------------------------------------------------------- #
# 3. l'estimation avec les lois, sur une fonction analytique
# --------------------------------------------------------------------------- #
X = np.linspace(0.0, 1.0, 25)


def _fonction(vrai, poids_b=1.0):
    """a fixé par les données, b peu, c pas du tout."""
    def modele(th):
        a, b = (np.atleast_1d(np.asarray(th[k], dtype=float))[:, None] for k in "ab")
        c = np.atleast_1d(np.asarray(th["c"], dtype=float))[:, None]
        return 2.0 * a * X + poids_b * 0.01 * b * X ** 2 + 0.0 * c
    cible = modele(vrai)[0]
    return lambda th: (modele(th) - cible) / 0.1


def test_sans_donnees_theta_va_au_mode_de_sa_loi_et_s_arrete_a_la_borne():
    lois = {"a": ap.LARGE, "b": ap.Loi(0.3, 0.1, 0.2, "s"), "c": ap.Loi(-0.25, 0.4, 0.4, "s")}
    vrai = {"a": 0.7, "b": 0.8, "c": 0.9}
    est = app.estimer(_fonction(vrai), ("a", "b", "c"), {}, lois=lois)
    assert est.theta["a"] == pytest.approx(0.7, abs=5e-3)   # les données le tiennent
    assert est.theta["b"] == pytest.approx(0.3, abs=0.02)   # l'a priori l'emporte
    assert est.theta["c"] == 0.0                            # le mode hors de la boîte
    assert est.identifies == ("a",)
    # sous la loi large de D-417, les mêmes θ vont à ½
    large = app.estimer(_fonction(vrai), ("a", "b", "c"), {})
    assert large.theta["c"] == pytest.approx(0.5, abs=1e-9)


def test_une_loi_large_redonne_d417_au_bit_pres():
    f = _fonction({"a": 0.2, "b": 0.6, "c": 0.4}, poids_b=50.0)
    sans = app.estimer(f, ("a", "b", "c"), {})
    avec = app.estimer(f, ("a", "b", "c"), {}, lois={k: ap.LARGE for k in "abc"})
    assert dict(avec.theta) == dict(sans.theta)
    assert dict(avec.ecarts_types) == dict(sans.ecarts_types)
    assert avec.identifies == sans.identifies


def test_un_a_priori_serre_n_identifie_pas_a_lui_seul():
    """Un θ sans effet sous une loi d'écart-type 0,1 : son écart-type approché est 0,1,
    sous le seuil de 0,25 de D-417 ; il n'est pas identifié pour autant."""
    lois = {"a": ap.LARGE, "b": ap.LARGE, "c": ap.Loi(0.6, 0.1, 0.1, "s")}
    est = app.estimer(_fonction({"a": 0.2, "b": 0.6, "c": 0.4}, poids_b=50.0),
                      ("a", "b", "c"), {}, lois=lois)
    assert est.ecarts_types["c"] == pytest.approx(0.1, rel=1e-6)
    assert est.theta["c"] == pytest.approx(0.6, abs=1e-9)
    assert "c" not in est.identifies and "a" in est.identifies


def test_un_theta_estime_sans_loi_est_refuse():
    with pytest.raises(app.ApprentissageError, match="sans loi a priori : \\['c'\\]"):
        app.estimer(_fonction({"a": 0.2, "b": 0.6, "c": 0.4}), ("a", "b", "c"), {},
                    lois={"a": ap.LARGE, "b": ap.LARGE})


def test_les_lois_du_registre_entrent_dans_l_estimation():
    """Les sept θ que le rejeu de l'histoire estime (D-417), sans aucune donnée qui les
    fixe : chacun va au mode de sa loi, ramené dans la boîte."""
    from impots.jumeau import rejeu_histoire as rh

    def nulle(th):
        n = max(np.size(v) for v in th.values())
        return np.zeros((n, 3))
    est = app.estimer(nulle, rh.ESTIMES, {}, lois=LOIS)
    for k in rh.ESTIMES:
        assert est.theta[k] == pytest.approx(min(1.0, max(0.0, LOIS[k].moyenne)), abs=1e-6)
    assert not est.identifies


# --------------------------------------------------------------------------- #
# 4. les nombres du YAML sont ceux des fichiers
# --------------------------------------------------------------------------- #
def _texte(fichier, page):
    return "".join("".join(li.split()) for li in dict(mesange_pdf._pages(str(fichier)))[page])


SOURCES = {
    "iza_dp7958_2014_lichter_peichl_siegloch_labor_demand.pdf": (22, ("is-0.246",
                                                                      "[-0.072;-0.446]")),
    # le tableau 4 (−0,077, 0,006, s = 0,070) a une police qui ne s'extrait pas : lu sur
    # l'image de la p. 33 ; le texte de la p. 22 redonne −0,077
    "tinbergen_dp02029_2002_nijkamp_poot_wage_curve.pdf": (22, ("isnow-0.077",)),
    "gechert_havranek_irsova_kolcunova_2021_capital_labor_substitution.pdf": (
        35, ("Bestpractice0.30(-0.01,0.60)",)),
    "imbs_mejean_2010_trade_elasticities.pdf": (35, ("France-3.4930.059-3.8210.088",)),
    "iza_dp7698_2013_bargain_peichl_labor_supply_survey.pdf": (10, ("meanvaluesof:43",)),
    "devereux_lockwood_2006_foreign_owned_capital.pdf": (25, ("-0.478", "3.72")),
}


@pytest.mark.parametrize("fichier", sorted(SOURCES))
def test_les_estimations_sont_celles_des_pdf(fichier):
    chemin = RAW / fichier
    if not chemin.exists():
        pytest.skip(f"data/raw/{fichier} absent : `make data` le prépare")
    page, attendus = SOURCES[fichier]
    texte = _texte(chemin, page)
    for a in attendus:
        assert a in texte, (fichier, a)


def test_les_ecarts_types_derivent_des_estimations_publiees():
    """Les calculs du YAML, refaits."""
    e = {k: d for k, d in DOC.items() if "estimation" in d}
    assert e[thetas.EMPLOI_COUT]["ecart_type"] == pytest.approx(
        (0.446 - 0.072) / (2 * 1.96), abs=1e-4)
    assert e["investissement_cout_capital"]["ecart_type"] == pytest.approx(
        0.61 / (2 * 1.96), abs=1e-4)
    assert e["investissement_accelerateur"]["ecart_type"] == pytest.approx(1.19 / 6.9,
                                                                           abs=1e-4)
    assert e["implantation_tmee"]["ecart_type"] == pytest.approx(0.478 / 3.72, abs=1e-4)
    assert e[thetas.ELASTICITE_PRIX_EXPORTATIONS.cle]["ecart_type"] == pytest.approx(
        0.73 / 5.5, abs=1e-4)
    imp = (0.64 * 0.44 / 6.5 + 0.20 * 0.29 / 3.6) * 0.35 / (0.64 * 0.44 + 0.20 * 0.29)
    assert e[thetas.ELASTICITE_PRIX_IMPORTATIONS.cle]["ecart_type"] == pytest.approx(
        imp, abs=1e-4)


T302 = RAW / "insee_eec2025_t302_chomage_bit.xlsx"


@pytest.mark.skipif(not T302.exists(), reason="data/raw/insee_eec2025_t302_chomage_bit"
                    ".xlsx absent : `make data` le prépare")
def test_le_facteur_des_salaires_vient_du_chomage_de_l_insee():
    import openpyxl

    feuille = openpyxl.load_workbook(T302, read_only=True, data_only=True)["TXCHOM"]
    lignes = list(feuille.iter_rows(values_only=True))
    annees = next(r for r in lignes if r and r[1] == "Annuel")
    total = next(r for r in lignes if r and r[0] == "Total" and r[1] == "Total")
    taux = [float(v) for a, v in zip(annees[2:], total[2:], strict=False)
            if 1989 <= int(a) <= 2014]
    u = sum(taux) / len(taux)
    assert len(taux) == 26 and u == pytest.approx(9.154, abs=5e-4)
    d = DOC[thetas.SALAIRES_CHOMAGE]
    assert d["estimation"] == pytest.approx(0.077 / u / 0.018, abs=1e-4)
    assert d["ecart_type"] == pytest.approx(math.hypot(0.006, 0.070) / u / 0.018, abs=1e-4)


BOP = RAW / "iza_dp6735_2012_bargain_orsini_peichl_labor_supply.pdf"


@pytest.mark.skipif(not BOP.exists(), reason="data/raw/iza_dp6735_2012_bargain_orsini_"
                    "peichl_labor_supply.pdf absent : `make data` le prépare")
def test_l_offre_de_travail_vient_des_cellules_de_bargain_orsini_peichl():
    cellules = bop.load()
    groupes = {"femmes_en_couple": "labour_supply_married_women",
               "hommes_en_couple": "labour_supply_married_men",
               "femmes_seules": "labour_supply_single_women",
               "hommes_seuls": "labour_supply_single_men"}
    for groupe, cle in groupes.items():
        blocs = ("own", "cross") if groupe in bop.COUPLES else ("own",)
        e, s = [], []
        for annee in bop.YEARS:
            parts = [cellules[(groupe, annee, b, "Total hours")] for b in blocs]
            e.append(sum(c.estimate for c in parts))
            s.append(sum(c.se for c in parts))
        ecart = math.sqrt((s[0] ** 2 + s[1] ** 2) / 2 + ((e[0] - e[1]) / 2) ** 2)
        assert DOC[cle]["estimation"] == pytest.approx(sum(e) / 2, abs=1e-9), cle
        assert DOC[cle]["ecart_type"] == pytest.approx(ecart, abs=1e-4), cle
        assert ap.plages()[cle][1] == pytest.approx(sum(e) / 2, abs=1e-9), cle
