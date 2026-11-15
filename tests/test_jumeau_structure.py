"""But 23 (D-414) — le mode structurel complété : l'accélérateur, la boucle prix-salaires,
l'IS sur les profits induits.

Sur les données synthétiques des tests du modèle structurel (`test_jumeau_structurel`) :

1. l'accélérateur redonne la ligne « Valeur ajoutée (+1 %) » de Mésange (p. 45) ; une
   relance monte l'investissement par lui, une restriction le baisse, et θ le borne ;
2. la boucle prix-salaires : une relance monte le prix de valeur ajoutée, celui de la
   consommation et les salaires, une baisse des cotisations baisse les prix ; les prix
   suivent les coûts d'autant plus vite que θ est haut ; les prestations hors chômage
   suivent le prix de la consommation ;
3. l'IS induit est le taux apparent fois le profit induit, à 1e-12, et ne lit pas le PIB
   potentiel que d'autres blocs taxent déjà ;
4. chaque nouveau canal est porté une fois, et refusé à côté de `mesange` ;
5. les identités tiennent à 1e-9, sur un axe de tirages et à θ = 0, ½, 1.

La chaîne des études, en mode réduit, reste celle de `test_jumeau.py` et de
`test_rejouer.py` ; le déterminisme, `test_jumeau_determinisme.py`.
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.jumeau import canaux, identites, thetas
from impots.jumeau.blocs import ordre_structurel
from impots.jumeau.blocs.commerce import charger as charger_commerce
from impots.jumeau.blocs.entreprises import ACCELERATEUR_ROW, ChocsEntreprises, charger
from impots.jumeau.blocs.investissement import (
    HORIZON_MAX,
    Investissement,
    reponse_valeur_ajoutee,
)
from impots.jumeau.blocs.mesange import Mesange
from impots.jumeau.blocs.mesures import Mesures
from impots.jumeau.blocs.recettes_induites import RecettesInduites
from impots.jumeau.blocs.recettes_induites import charger as charger_recettes
from impots.jumeau.blocs.tendance import Tendance
from impots.jumeau.comparaison import mesure
from impots.jumeau.pas import Modele
from test_jumeau_menages import CELLULES
from test_jumeau_structurel import ANNEES, POPULATION, _calcul, _depart, _entrees

P = charger()


def _theta(valeur=0.5, **autres):
    theta = dict.fromkeys(thetas.REGISTRE, valeur)
    theta.update(autres)
    return theta


def _variante(nom, signe=1.0):
    """La variante de Mésange d'un point de PIB, ou son opposée (`signe = −1`)."""
    depart, entrees = _depart(), _entrees()
    pib = [signe * Tendance(depart).chemin(entrees, k)[0] for k in range(len(ANNEES))]
    m = mesure(nom, pib, ANNEES, CELLULES)
    return m


def _de(traj, champ_, origine, m):
    return np.array([e.de(champ_).get((origine, m), np.zeros(e.n))[0]
                     for e in traj.variante])


def _par_mesure(traj, champ_, m):
    return np.array([e.par_mesure(champ_).get(m, np.zeros(e.n))[0] for e in traj.variante])


# --------------------------------------------------------------------------- #
# 1. l'accélérateur
# --------------------------------------------------------------------------- #
def test_l_accelerateur_redonne_la_ligne_de_la_valeur_ajoutee_de_mesange() -> None:
    """Mésange, p. 45 : 1,79, 2,00, 1,36 et 1,00 à 1, 2, 5 ans et à long terme ; le bloc
    les redonne au centième près (la moyenne annuelle de l'équation trimestrielle)."""
    r0, r1, rec = (np.array(r) for r in reponse_valeur_ajoutee(
        P.rappel_trimestriel, P.retard_trimestriel))
    r = (P.accelerateur_contemporain.centre * r0 + P.accelerateur_retarde.centre * r1
         + rec)
    for h, attendu in ((1, 1.79), (2, 2.00), (5, 1.36)):
        assert r[h - 1] == pytest.approx(attendu, abs=0.025), h
    assert r[HORIZON_MAX - 1] == pytest.approx(1.0, abs=1e-6)
    assert abs(r0[-1]) < 1e-6 and abs(r1[-1]) < 1e-6


def test_l_accelerateur_a_le_sens_de_l_activite_et_theta_le_borne() -> None:
    """Une relance (l'IR baisse) monte l'investissement par l'accélérateur, la hausse
    opposée le baisse ; la première année, θ = 0 et θ = 1 bornent la réponse."""
    hausse, baisse = _variante("impot_sur_le_revenu"), _variante("impot_sur_le_revenu", -1)
    relance = _calcul(_theta(), mesures=[hausse])
    restriction = _calcul(_theta(), mesures=[baisse])
    a_plus = _de(relance, "ebe_revenu_mixte", "investissement", hausse.identifiant)
    a_moins = _de(restriction, "ebe_revenu_mixte", "investissement", baisse.identifiant)
    assert np.all(a_plus > 0.0) and np.all(a_moins < 0.0)
    premiere = [float(_de(_calcul(_theta(**{ACCELERATEUR_ROW: t}), mesures=[hausse]),
                          "ebe_revenu_mixte", "investissement", hausse.identifiant)[0])
                for t in (0.0, 0.5, 1.0)]
    assert premiere[0] < premiere[1] < premiere[2]


def test_l_accelerateur_est_refuse_a_cote_de_mesange() -> None:
    """Mésange porte l'accélérateur dans ses multiplicateurs : pour un même instrument,
    les deux ensemble sont le double compte ; sans l'accélérateur, l'investissement par
    l'IS tourne toujours à côté de Mésange (D-411)."""
    depart = _depart()
    with pytest.raises(canaux.DoubleCompte, match="investissement_accelerateur"):
        Modele([Tendance(depart), Mesures(), Mesange("lue"),
                Investissement(P, accelerateur=True)])
    Modele([Tendance(depart), Mesures(), Mesange("lue"), ChocsEntreprises(),
            Investissement(P)])


# --------------------------------------------------------------------------- #
# 2. la boucle prix-salaires
# --------------------------------------------------------------------------- #
def test_une_relance_monte_les_prix_et_les_salaires_une_restriction_les_baisse() -> None:
    hausse, baisse = _variante("depense_publique"), _variante("depense_publique", -1)
    for m, signe in ((hausse, 1.0), (baisse, -1.0)):
        traj = _calcul(_theta(), mesures=[m])
        for champ_ in ("ecart_prix_valeur_ajoutee", "ecart_prix_consommation",
                       "salaire_moyen"):
            v = _par_mesure(traj, champ_, m.identifiant)
            assert np.all(signe * v[1:] > 0.0), (champ_, signe)
        # Les prestations hors chômage suivent le prix de la consommation.
        pc = _par_mesure(traj, "ecart_prix_consommation", m.identifiant)
        indexees = _de(traj, "apu_d_d62", "consommation", m.identifiant)
        assert np.all(signe * indexees[1:] > 0.0)
        np.testing.assert_allclose(indexees / pc, indexees[0] / pc[0] * np.array(
            [e["pib"][0] for e in traj.reference]) / traj.reference[0]["pib"][0],
            rtol=1e-9)


def test_une_baisse_des_cotisations_baisse_les_prix() -> None:
    m = _variante("cotisations_employeurs")
    traj = _calcul(_theta(), mesures=[m])
    for champ_ in ("ecart_prix_valeur_ajoutee", "ecart_prix_consommation"):
        assert np.all(_par_mesure(traj, champ_, m.identifiant) < 0.0), champ_
    # Le prix des exportations baisse, leur volume monte.
    assert np.all(traj.variante[-1]["prix_exportations"] < traj.reference[-1][
        "prix_exportations"])


def test_les_prix_suivent_les_couts_d_autant_plus_vite_que_theta_est_haut() -> None:
    """La première année d'une baisse des cotisations, le prix de valeur ajoutée baisse
    d'autant plus que la diffusion est rapide : θ = 0 et θ = 1 bornent θ½."""
    m = _variante("cotisations_employeurs")
    premiere = [float(_par_mesure(_calcul(_theta(**{thetas.PRIX_DIFFUSION.cle: t}),
                                          mesures=[m]),
                                  "ecart_prix_valeur_ajoutee", m.identifiant)[0])
                for t in (0.0, 0.5, 1.0)]
    assert premiere[0] > premiere[1] > premiere[2]


def test_le_prix_de_la_consommation_est_l_equation_de_mesange() -> None:
    """(PC), Mésange p. 24, sans taxe : p̂c = (1 − μ_C) p^D + μ_C P^M ; le déflateur de la
    consommation des ménages porte les écarts de toutes les mesures."""
    m = _variante("impot_sur_le_revenu")
    traj = _calcul(_theta(), mesures=[m])
    pc = _par_mesure(traj, "ecart_prix_consommation", m.identifiant)
    prix = [e["prix_c_menages"][0] for e in traj.variante]
    ref = [e["prix_c_menages"][0] for e in traj.reference]
    niveau = np.cumprod(prix) / np.cumprod(ref) - 1.0
    np.testing.assert_allclose(niveau, pc, rtol=1e-9, atol=1e-15)
    assert 0.0 < charger_commerce().contenus["consommation_finale_menages"] < 1.0


# --------------------------------------------------------------------------- #
# 3. l'IS sur les profits induits
# --------------------------------------------------------------------------- #
def test_l_is_induit_est_le_taux_apparent_sur_le_profit_induit() -> None:
    valeurs = charger_recettes()
    assert valeurs["taux"] == pytest.approx(69.121 / 1036.606, abs=5e-6)
    # Le PIB potentiel de l'investissement, de l'implantation et de la démographie porte
    # déjà ρ ΔY : il n'est pas dans la base.
    assert "investissement" not in valeurs["origines"]["revenus_non_ventiles"]
    for o in ("implantation", "productivite"):
        assert all(o not in v for v in valeurs["origines"].values())
    for nom in ("depense_publique", "impot_sur_le_revenu"):
        m = _variante(nom)
        traj = _calcul(_theta(), mesures=[m])
        base = sum(_de(traj, c, o, m.identifiant) for c, os in valeurs["origines"].items()
                   for o in os)
        np.testing.assert_allclose(
            _de(traj, "apu_r_d5", "recettes_induites", m.identifiant),
            valeurs["taux"] * base, rtol=1e-12, atol=1e-12)


def test_l_is_induit_a_le_sens_du_profit_induit() -> None:
    """La première année d'une relance, le profit induit monte, et l'IS avec lui ; la
    restriction opposée le baisse."""
    for signe in (1.0, -1.0):
        m = _variante("depense_publique", signe)
        traj = _calcul(_theta(), mesures=[m])
        assert signe * _de(traj, "apu_r_d5", "recettes_induites", m.identifiant)[0] > 0.0


def test_les_recettes_induites_sont_refusees_a_cote_de_mesange() -> None:
    with pytest.raises(canaux.DoubleCompte, match="recettes_induites_profits"):
        Modele([Tendance(_depart()), Mesures(), Mesange("lue"), RecettesInduites()])


# --------------------------------------------------------------------------- #
# 4. et 5. les canaux, les identités
# --------------------------------------------------------------------------- #
def test_les_nouveaux_canaux_sont_portes_une_fois() -> None:
    blocs, boucles = ordre_structurel(_depart(), POPULATION, CELLULES)
    modele = Modele(blocs, boucles)
    porteurs = {c: b for (c, _), b in modele.canaux.items()}
    assert porteurs["investissement_accelerateur"] == "investissement"
    assert porteurs["prix_production"] == "commerce"
    assert porteurs["recettes_induites_profits"] == "recettes_induites"
    assert {"investissement_accelerateur", "prix_production",
            "recettes_induites_profits"} <= canaux.DE_MESANGE


@pytest.mark.parametrize("theta", [0.0, 0.5, 1.0, np.array([0.0, 0.3, 0.5, 0.8, 1.0])])
def test_les_identites_tiennent_avec_les_trois_mecanismes(theta) -> None:
    mesures = [_variante("depense_publique"), _variante("cotisations_employeurs")]
    traj = _calcul(_theta(theta), mesures=mesures)
    prec = None
    for etat in traj.variante:
        residus = identites.verifier(etat, prec)
        assert max(float(np.max(np.abs(r))) for r in residus.values()) < 1e-9
        prec = etat
    parts = traj.decomposition(ANNEES[-1])
    assert np.max(np.abs(sum(parts.values()) - traj.delta_b[-1])) < 1e-12
