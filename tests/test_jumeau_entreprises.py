"""But 23, lot 2 — les entreprises du jumeau (D-407).

Ce que ces tests tiennent, sur la population synthétique des cellules (`tests/fixtures/
firm_cells.json`) et un départ synthétique :

1. les identités du cadre tiennent avec les blocs du lot 2, sur un axe de tirages et
   plusieurs θ, et le compte des sociétés boucle (N_t = N_{t−1} + créations − fermetures) ;
2. chaque bloc a le signe attendu dans les deux sens, pour l'IS, la CVAE et les
   cotisations patronales, et une hausse est l'opposé exact d'une baisse ; un impôt
   qu'un bloc ne lit pas (les cotisations pour l'investissement, tout sauf l'IS pour
   l'implantation) n'y fait rien ;
3. θ = 0 et θ = 1 bornent chaque bloc, de façon monotone ;
4. un canal porté deux fois est refusé : l'investissement avec `mesange`, les naissances
   avec le `creations` du lot 1 ;
5. l'investissement, linéarisé, à côté de la variante de taux de Mésange : l'écart est
   celui que D-407 écrit ;
6. les valeurs du fichier qui viennent des tables de l'Insee s'y relisent (sautés, avec
   leur raison, sans les tables).
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml

from impots.jumeau import canaux, identites, thetas
from impots.jumeau.blocs.creations import Creations
from impots.jumeau.blocs.demographie import Fermetures, Naissances, Productivite
from impots.jumeau.blocs.entreprises import (
    CELLULES_2023,
    ChocsEntreprises,
    EntreprisesError,
    charger,
    mesure_entreprises,
    ordre_lot2,
    population_depuis,
)
from impots.jumeau.blocs.investissement import Investissement, comparer_mesange
from impots.jumeau.blocs.mesange import Mesange
from impots.jumeau.blocs.mesures import Mesures
from impots.jumeau.blocs.tendance import Tendance
from impots.jumeau.blocs.valeurs_entreprises import FICHIER
from impots.jumeau.mesures import Mesure
from impots.jumeau.pas import Entrees, Modele
from impots.jumeau.trajectoire import calculer, depart_depuis_start
from impots.predictif.theta import CREATIONS_ROW

FIXTURE = Path(__file__).parent / "fixtures" / "firm_cells.json"
PARTS = {"c_menages": 0.52, "c_isbl": 0.02, "c_apu": 0.24, "fbcf_snf": 0.13,
         "fbcf_apu": 0.04, "fbcf_menages": 0.05, "var_stocks": 0.01, "exportations": 0.33,
         "importations": 0.34,
         "remunerations": 0.51, "ebe_revenu_mixte": 0.35, "impots_production": 0.16,
         "subventions": 0.02,
         "apu_r_d2": 0.30, "apu_r_d5": 0.25, "apu_r_d61": 0.33, "apu_r_p11": 0.07,
         "apu_r_d7": 0.05,
         "apu_d_p2": 0.10, "apu_d_d1": 0.22, "apu_d_d62": 0.38, "apu_d_d632": 0.12,
         "apu_d_d3": 0.06, "apu_d_p51g": 0.08, "apu_d_d7": 0.04}
START = {"year": 2025, "gdp_eur": 2.99e12, "receipts_ratio": 0.51, "spending_ratio": 0.53,
         "debt_ratio": 1.15}
ANNEES = tuple(range(2026, 2036))
LOT2 = (CREATIONS_ROW, "idees_creations", "fermetures_marges",
        "investissement_cout_capital", "implantation_tmee", "survie_creations",
        "montee_en_charge_creations", "taille_creations")
#: Les θ dont θ = 0 n'éteint pas le canal : leur borne basse est une valeur publiée ou
#: choisie, pas zéro.
SANS_ZERO = ("investissement_cout_capital", "survie_creations",
             "montee_en_charge_creations", "taille_creations")
INSTRUMENTS = ("impot_societes", "cvae", "cotisations_employeurs")
#: (bloc, champ) : ce que chaque bloc fait, et les impôts qu'il lit.
LECTURES = {"naissances": ("creations_societes", set(INSTRUMENTS)),
            "fermetures": ("sorties_induites", set(INSTRUMENTS)),
            "productivite": ("pib", set(INSTRUMENTS)),
            "investissement": ("pib", {"impot_societes", "cvae"}),
            "implantation": ("pib", {"impot_societes"})}
#: Le signe de l'effet d'une HAUSSE : moins de créations, plus de sorties, moins de PIB.
SIGNE_HAUSSE = {"naissances": -1, "fermetures": 1, "productivite": -1,
                "investissement": -1, "implantation": -1}


@pytest.fixture(scope="module")
def pop():
    return population_depuis(FIXTURE)


def _entrees() -> Entrees:
    k = len(ANNEES)
    return Entrees(annees=ANNEES, croissance_reelle=(0.01,) * k, prix=(0.018,) * k,
                   regle_depense="gele_en_volume", croissance_depense=None,
                   taux_reference=(0.02,) * k, taux_marginal=0.03, noms={})


def _theta(valeur=0.5, **autres):
    theta = {cle: valeur for cle in LOT2}
    theta.update(autres)
    return theta


def _calculer(pop, mesures, theta, blocs=None):
    depart = depart_depuis_start(START, PARTS)
    return calculer(depart, entrees=_entrees(), mesures=mesures, theta=theta,
                    blocs=blocs or ordre_lot2(depart, pop))


def _loi(instrument, montant, identifiant="m"):
    return mesure_entreprises(identifiant, "test", {a: {instrument: montant}
                                                    for a in ANNEES})


def _part(trajectoire, bloc, champ, mesure="m"):
    """La contribution d'un bloc à un champ de la variante, années × tirages."""
    return np.array([e.de(champ).get((bloc, mesure), np.zeros(e.n))
                     for e in trajectoire.variante])


# --------------------------------------------------------------------------- #
# 1. les identités
# --------------------------------------------------------------------------- #
def test_les_identites_tiennent_avec_le_lot_2_sur_un_axe_de_tirages(pop) -> None:
    """n = 5 tirages, chaque θ sur l'axe ; trois mesures, l'une ventilée par taille."""
    axe = np.array([0.0, 0.2, 0.5, 0.8, 1.0])
    theta = {cle: np.roll(axe, i) for i, cle in enumerate(LOT2)}
    mesures = [_loi("impot_societes", 8.0, "is"), _loi("cotisations_employeurs", -6.0, "cot"),
               mesure_entreprises("cvae", "CVAE par taille",
                                  {a: {"cvae": {"PME": -1.0, "ETI": -2.0}, "c3s": 0.5}
                                   for a in ANNEES})]
    traj = _calculer(pop, mesures, theta)
    for serie in (traj.reference, traj.variante):
        precedent = None
        for etat in serie:
            for nom, residu in identites.residus(etat, precedent).items():
                assert np.all(np.abs(residu) <= 1e-9 * etat["pib"]), (nom, etat.annee)
            avant = (precedent["stock_societes"] if precedent is not None
                     else np.full(5, pop.stock))
            ecart = avant + etat["creations_societes"] - etat["fermetures_societes"]
            assert np.max(np.abs(ecart - etat["stock_societes"])) < 1e-6
            precedent = etat


def test_sans_mesure_la_reference_est_stationnaire_a_theta_idees_un_demi(pop) -> None:
    """Le hasard des installées se calcule pour tenir le stock au taux e₀, quelle que
    soit la survie des jeunes."""
    traj = _calculer(pop, [], _theta(survie_creations=np.array([0.0, 0.5, 1.0])))
    stock = traj.niveaux("stock_societes")[0]
    assert np.max(np.abs(stock - pop.stock)) < 1e-6
    traj = _calculer(pop, [], _theta())
    p = charger()
    assert np.allclose(traj.niveaux("creations_societes")[0][:, 0],
                       p.taux_entree_base / 100 * pop.stock)
    assert np.allclose(traj.niveaux("productivite_moyenne")[0], 1.0)


# --------------------------------------------------------------------------- #
# 2. les signes, dans les deux sens
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("instrument", INSTRUMENTS)
def test_chaque_bloc_a_le_signe_attendu_dans_les_deux_sens(pop, instrument) -> None:
    hausse = _calculer(pop, [_loi(instrument, 10.0)], _theta())
    baisse = _calculer(pop, [_loi(instrument, -10.0)], _theta())
    for bloc, (champ, lus) in LECTURES.items():
        h, b = _part(hausse, bloc, champ), _part(baisse, bloc, champ)
        if instrument not in lus:
            assert not np.any(h) and not np.any(b), (bloc, instrument)
            continue
        assert np.all(np.sign(h) == SIGNE_HAUSSE[bloc]), (bloc, instrument, h)
        assert np.all(np.sign(b) == -SIGNE_HAUSSE[bloc]), (bloc, instrument, b)
        assert np.allclose(h, -b, rtol=1e-12, atol=0.0), (bloc, instrument)
    # La dette : une hausse rapporte, moins ce que l'activité perdue retire. La dette et
    # le PIB sont linéaires dans le choc ; leur ratio ne l'est pas, à l'ordre deux près.
    assert np.all(hausse.delta_b < 0) and np.all(baisse.delta_b > 0)
    for champ in ("dette", "pib"):
        assert np.allclose(hausse.difference(champ), -baisse.difference(champ),
                           rtol=1e-9, atol=1e-9), champ


def test_une_mesure_ventilee_par_taille_change_les_sorties_pas_les_creations(pop) -> None:
    """Le même montant, sur les micro ou sur les grandes : les créations lisent le taux
    apparent national, les sorties les marges de chaque cellule."""
    lois = [mesure_entreprises(t, t, {a: {"cvae": {t: 5.0}} for a in ANNEES}, )
            for t in ("micro", "GE")]
    micro, ge = (_calculer(pop, [loi], _theta()) for loi in lois)
    assert np.allclose(micro.difference("creations_societes"),
                       ge.difference("creations_societes"))
    sorties_micro = micro.difference("sorties_induites")
    sorties_ge = ge.difference("sorties_induites")
    assert np.all(sorties_micro > sorties_ge) and np.all(sorties_ge > 0)


# --------------------------------------------------------------------------- #
# 3. θ = 0 et θ = 1 bornent
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("cle,bloc,champ", [
    (CREATIONS_ROW, "productivite", "pib"),
    ("fermetures_marges", "fermetures", "sorties_induites"),
    ("investissement_cout_capital", "investissement", "pib"),
    ("implantation_tmee", "implantation", "pib"),
    ("survie_creations", "productivite", "pib"),
    ("survie_creations", "fermetures", "stock_societes"),
    ("montee_en_charge_creations", "productivite", "pib"),
    ("taille_creations", "productivite", "pib"),
])
def test_theta_zero_et_un_bornent_chaque_bloc(pop, cle, bloc, champ) -> None:
    grille = np.linspace(0.0, 1.0, 9)
    traj = _calculer(pop, [_loi("impot_societes", 10.0)], _theta(**{cle: grille}))
    effet = np.abs(_part(traj, bloc, champ))  # années × θ
    assert np.all(np.diff(effet, axis=1) >= -1e-12), "monotone en θ"
    assert np.all(effet[:, 1:-1] <= effet[:, [-1]] + 1e-12)
    assert np.all(effet[:, 1:-1] >= effet[:, [0]] - 1e-12)
    if cle not in SANS_ZERO:
        assert not np.any(effet[:, 0]), "θ = 0 éteint le canal"


def test_theta_idees_deplace_la_reference_pas_la_mesure_seule(pop) -> None:
    """δ(θ) est dans la référence comme dans la variante : il borne les niveaux de 0 à 1,
    et ne fait presque rien à l'écart des créations (le PIB du scénario les met à
    l'échelle, pas la référence)."""
    traj = _calculer(pop, [_loi("impot_societes", 10.0)],
                     _theta(idees_creations=np.array([0.0, 0.5, 1.0])))
    creations = traj.niveaux("creations_societes")[0]
    assert np.all(creations[:, 0] < creations[:, 1]) and np.all(creations[:, 1] < creations[:, 2])
    pib = traj.niveaux("pib")[0]
    assert np.all(pib[:, 0] < pib[:, 1]) and np.all(pib[:, 1] < pib[:, 2])
    ecart = traj.difference("creations_societes")
    assert np.allclose(ecart[:, 0], ecart[:, 2])


# --------------------------------------------------------------------------- #
# 4. le double compte
# --------------------------------------------------------------------------- #
def test_un_canal_porte_deux_fois_est_refuse(pop) -> None:
    depart = depart_depuis_start(START, PARTS)
    p = charger()
    # Par instrument (D-411) : Mésange n'a pas de variante d'IS, de CVAE ni de C3S, et
    # l'investissement par ces impôts tourne avec lui ; lu sur les cotisations
    # employeurs, que Mésange porte, il est refusé.
    ensemble = Modele([Tendance(depart), Mesures(), Mesange("lue"), ChocsEntreprises(),
                       Investissement(p)])
    assert ensemble.canaux[("investissement_cout_du_capital", "impot_societes")] == \
        "investissement"
    assert ensemble.canaux[("investissement_cout_du_capital", "tva")] == "mesange"
    sur_cotisations = replace(p, signaux_investissement=("cotisations_patronales",))
    with pytest.raises(canaux.DoubleCompte, match=r"investissement_cout_du_capital.*"
                       r"cotisations_employeurs"):
        Modele([Tendance(depart), Mesures(), Mesange("lue"), ChocsEntreprises(),
                Investissement(sur_cotisations)])
    with pytest.raises(canaux.CanalError, match="creations_entreprises"):
        Modele([Tendance(depart), Mesures(), Creations(), ChocsEntreprises(),
                Naissances(pop, p)])
    # Mésange et la démographie ne portent pas le même canal.
    modele = Modele([Tendance(depart), Mesures(), Mesange("lue"), ChocsEntreprises(),
                     Naissances(pop, p), Fermetures(pop, p), Productivite(pop, p)])
    assert modele.canaux[("investissement_cout_du_capital", "cotisations_employeurs")] \
        == "mesange"
    assert modele.canaux[("creations_entreprises", canaux.TOUS)] == "naissances"


def test_un_canal_inconnu_est_refuse() -> None:
    class Bloc:
        nom, lit, ecrit, thetas, porte = "x", (), (), (), ("inconnu",)

    with pytest.raises(canaux.CanalError, match="inconnu"):
        canaux.verifier([Bloc()])


# --------------------------------------------------------------------------- #
# 5. Mésange
# --------------------------------------------------------------------------- #
#: D-407 : la réponse de l'investissement (%) sous la variante de taux de Mésange (+6,5 %
#: de coût du capital), le bloc à θ½ et Mésange (p. 134 du PDF), à 1, 2, 3, 5, 10 ans, LT.
D407_JUMEAU = {"1": -0.26, "2": -0.94, "3": -1.49, "5": -2.16, "10": -2.73, "LT": -2.86}


def test_l_investissement_linearise_a_cote_de_la_variante_de_taux_de_mesange() -> None:
    table = comparer_mesange(charger())
    for h, ligne in table.items():
        assert round(ligne["jumeau"], 2) == D407_JUMEAU[h], h
        # Le bloc n'a pas l'accélérateur : sa réponse est plus faible que celle de Mésange.
        assert abs(ligne["jumeau"]) < abs(ligne["mesange"]), h
    assert abs(table["LT"]["jumeau"] - (-0.44 * 6.5)) < 1e-6


# --------------------------------------------------------------------------- #
# les refus
# --------------------------------------------------------------------------- #
def test_un_agregat_non_ventile_est_refuse(pop) -> None:
    agregat = Mesure.hypothese("agr", "agrégat", chocs={2026: {"apu_r_d5": -10.0}},
                               prelevements={2026: 10.0})
    with pytest.raises(EntreprisesError, match="ventilation par impôt"):
        _calculer(pop, [agregat], _theta())
    with pytest.raises(EntreprisesError, match="inconnu"):
        mesure_entreprises("x", "x", {2026: {"taxe_inconnue": 1.0}})
    taille = mesure_entreprises("t", "t", {2026: {"cvae": {"geantes": 1.0}}})
    with pytest.raises(EntreprisesError, match="tailles inconnues"):
        _calculer(pop, [taille], _theta())


def test_les_lignes_theta_du_lot_2_sont_au_registre() -> None:
    for cle in LOT2:
        assert cle in thetas.REGISTRE
    for cle in ("idees_creations", "fermetures_marges", "survie_creations",
                "montee_en_charge_creations", "taille_creations"):
        assert not thetas.REGISTRE[cle].verifiee  # choisies, non vérifiées


# --------------------------------------------------------------------------- #
# 6. les valeurs relues sur les tables (sautés, avec leur raison, sans elles)
# --------------------------------------------------------------------------- #
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
T8202 = RAW / "insee_cn2024_t8202_patrimoine_snf.xlsx"


@pytest.mark.skipif(not T8202.exists(), reason="la t. 8.202 de l'Insee n'est pas dans ce "
                    "checkout (data/raw est ignoré ; `impots data fetch`)")
def test_le_capital_net_se_relit_sur_la_table_8202() -> None:
    import openpyxl

    feuille = openpyxl.load_workbook(T8202, read_only=True, data_only=True).worksheets[1]
    lignes = list(feuille.iter_rows(values_only=True))
    annees = lignes[3]
    n11n = dict(zip(annees, next(r for r in lignes if r[0] == "N11N"), strict=True))
    valeurs = yaml.safe_load(FICHIER.read_text(encoding="utf-8"))["investissement"]
    assert n11n["2024"] == valeurs["capital_net_2024"]["valeur"]
    assert n11n["2014"] == valeurs["capital_net_2014"]["valeur"]


T7101 = RAW / "insee_cn2025_t7101_compte_snf.xlsx"
T7201 = RAW / "insee_cn2025_t7201_compte_sf_en.xlsx"


@pytest.mark.skipif(not (T7101.exists() and T7201.exists()), reason="les comptes des "
                    "sociétés de l'Insee (t. 7.101, 7.201) ne sont pas dans ce checkout "
                    "(data/raw est ignoré ; `impots data fetch`)")
def test_la_part_des_societes_dans_le_pib_se_relit_sur_les_comptes_de_secteur() -> None:
    import openpyxl

    def b1g_2024(chemin):
        lignes = list(openpyxl.load_workbook(chemin, read_only=True, data_only=True)
                      .worksheets[1].iter_rows(values_only=True))
        annees = lignes[3]
        return dict(zip(annees, next(r for r in lignes if r[0] == "B1G"),
                        strict=True))["2024"]

    valeurs = yaml.safe_load(FICHIER.read_text(encoding="utf-8"))["naissances"]
    assert b1g_2024(T7101) == valeurs["valeur_ajoutee_s11_2024"]["valeur"]
    assert b1g_2024(T7201) == valeurs["valeur_ajoutee_s12_2024"]["valeur"]
    assert abs(charger().part_va_societes_pib - 0.5539) < 1e-4


@pytest.mark.skipif(not CELLULES_2023.exists(), reason="les cellules de 2023 ne sont pas "
                    "préparées dans ce checkout (`make data`)")
def test_la_population_de_2023_porte_les_signes() -> None:
    reelle = population_depuis()
    assert "synthétique" not in reelle.millesime
    assert json.loads(CELLULES_2023.read_text())["vintage"] == "2023"
    traj = _calculer(reelle, [_loi("cotisations_employeurs", 10.0)], _theta())
    assert np.all(traj.difference("sorties_induites") > 0)
    assert np.all(traj.difference("stock_societes") < 0)
