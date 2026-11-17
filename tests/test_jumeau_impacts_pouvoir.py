"""But 29, volet `pouvoir` (D-591 à D-594) — le pouvoir d'achat et ce qui rapproche ou
sépare, tenus sur leurs nombres.

Le pouvoir d'achat : le gain réel est le gain nominal moins ce que les prix reprennent,
la somme des cellules est l'écart du revenu que `gagnants` porte, l'euro par UC de
l'ensemble est la somme sur les UC. L'entente : un gain nul ne change rien, un gain aux
deux premiers déciles baisse la pauvreté et le Gini, la distribution approchée redonne la
moyenne de chaque cellule, le Gini d'un exemple connu. Et les nombres de tête de D-593 sur
un programme réel (Retailleau), à θ½.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from impots import site_jumeau
from impots.jumeau import navigateur
from impots.jumeau.gagnants import gagnants_perdants
from impots.jumeau.impacts import calculer, dimensions, entente, pouvoir

RETAILLEAU = {"mode": "structurel", "vue": "figee",
              "candidat": "pres2027_retailleau_programme",
              "convention": "parts_premiere_annee"}


@pytest.fixture(scope="module")
def session() -> navigateur.Session:
    return navigateur.Session(json.loads(json.dumps(site_jumeau.donnees())))


def _theta(session, choix) -> dict:
    sortie = session.calculer({**choix, "theta": {}})
    return {t["cle"]: 0.5 for t in sortie["thetas"]}


@pytest.fixture(scope="module")
def retailleau(session):
    choix = {**RETAILLEAU, "theta": _theta(session, RETAILLEAU)}
    traj, depart, refus = pouvoir.trajectoire_tiree(session, choix, tirages=0)
    assert refus is None
    return traj, depart


def test_les_dimensions_s_inscrivent() -> None:
    assert {"pouvoir_achat", "entente"} <= set(dimensions())


def test_le_reel_est_le_nominal_moins_les_prix(session, retailleau) -> None:
    traj, depart = retailleau
    r = pouvoir.revenus(traj, depart, session.cellules)
    g = gagnants_perdants(traj, depart, session.cellules)
    assert np.array_equal(r.dynamique, g.ecart_md)
    assert r.structurel and np.all(r.prix[:, 0] < 0)  # Retailleau baisse les prix
    np.testing.assert_allclose(r.reel, r.dynamique + r.indexation - r.reprise)
    # La reprise est p̂c fois le revenu de référence, l'indexation p̂c fois les prestations.
    np.testing.assert_allclose(r.reprise / r.rd_ref, np.broadcast_to(
        r.prix[:, None, :], r.rd_ref.shape))
    t = pouvoir.tableaux(r)
    ensemble = r.reel[:, :, 0].sum(axis=1) * 1e9 / r.uc.sum() / r.deflateur[:, 0]
    np.testing.assert_allclose(t["reel_uc"]["Ensemble"][:, 0], ensemble)
    np.testing.assert_allclose(t["reel_uc"]["Ensemble"] - t["nominal_uc"]["Ensemble"],
                               -t["reprise_uc"]["Ensemble"])


def test_les_nombres_de_tete_de_retailleau(session, retailleau) -> None:
    """D-593 : Retailleau, θ½, vue figée, la convention de D-414 : +791 € par UC (en €
    de 2025) en 2026, +707 en 2035 ; D1 +5,2 %, D10 +1,1 % en 2026."""
    traj, depart = retailleau
    d = calculer(traj, None, depart, session.cellules, cles=["pouvoir_achat"])[
        "pouvoir_achat"]
    reel = {i.cle: i for i in d.indicateurs}
    assert reel["reel_uc"].valeurs[0] == pytest.approx(790.6, abs=1.0)
    assert reel["reel_uc"].valeurs[-1] == pytest.approx(706.9, abs=1.0)
    assert reel["reel_pct"].par_groupe["D1"][0] == pytest.approx(5.20, abs=0.02)
    assert reel["reel_pct"].par_groupe["D10"][0] == pytest.approx(1.10, abs=0.02)
    assert d.statut == "sourcé, non jugé" and reel["reel_uc"].bas is None


def test_un_gain_nul_ne_change_rien_et_le_bas_rapproche(session) -> None:
    cel = session.cellules
    dist = entente.approchee(cel)
    base = entente.indicateurs(dist.quantiles.reshape(-1), np.repeat(
        cel["personnes"] / dist.rangs.size, dist.rangs.size), None, dist.rangs)

    def calcul(gain_d1: float) -> entente.Calcul:
        nominal = np.zeros((1, 50, 1))
        nominal[0, :10, 0] = gain_d1 * cel["uc"][:10] / 1e9  # € par UC en D1 et D2
        r = pouvoir.Revenus(
            annees=(2026,), menages=cel["menages"], personnes=cel["personnes"],
            uc=cel["uc"], rd_ref=np.ones((1, 50, 1)), dynamique=nominal,
            indexation=np.zeros((1, 50, 1)), reprise=np.zeros((1, 50, 1)),
            prix=np.zeros((1, 1)), deflateur=np.ones((1, 1)), structurel=True)
        return entente.calculer_entente(r, cel, dist, 100.0, np.full((1, 1), 100.0))

    nul = calcul(0.0)
    for c in ("pauvrete", "gini", "d9_d1", "s80_s20", "mediane"):
        assert nul.variante[c][0, 0] == pytest.approx(nul.reference[c][0, 0], abs=1e-12)
    assert nul.reference["pauvrete"][0, 0] == pytest.approx(base["pauvrete"])
    bas = calcul(500.0)
    assert bas.variante["pauvrete"][0, 0] < bas.reference["pauvrete"][0, 0]
    assert bas.variante["gini"][0, 0] < bas.reference["gini"][0, 0]
    assert bas.variante["d9_d1"][0, 0] < bas.reference["d9_d1"][0, 0]


def test_la_distribution_approchee_redonne_la_moyenne_des_cellules(session) -> None:
    cel = session.cellules
    dist = entente.approchee(cel)
    np.testing.assert_allclose(dist.quantiles.mean(axis=1),
                               cel["revenu_disponible"] / cel["uc"], rtol=1e-12)


def test_le_gini_d_un_exemple_connu() -> None:
    assert entente.gini(np.array([0.0, 1.0]), np.array([1.0, 1.0])) == pytest.approx(0.5)
    assert entente.gini(np.array([3.0, 3.0, 3.0]), np.ones(3)) == pytest.approx(0.0)
    x = np.array([1.0, 2.0, 3.0, 4.0])
    attendu = np.abs(x[:, None] - x[None, :]).sum() / (2 * 16 * x.mean())
    assert entente.gini(x, np.ones(4)) == pytest.approx(attendu)
