"""But 29, volet `territoires` (D-645 à D-648) : la table de passage des cellules aux
territoires, son contrôle préenregistré, et la dimension « territoires ».

Les nombres tenus : le résultat du contrôle (D-647) lu sur la table commitée ; la moyenne
nationale de la dimension égale au gain des cellules du jumeau ; les nombres de tête de
D-648 (Retailleau, θ à ½). Sans navigateur : `navigateur.Session`, le code de la page.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from impots import site_jumeau
from impots.jumeau import navigateur
from impots.jumeau.cellules import N_CELLULES, TYPES
from impots.jumeau.impacts import territoires as T
from impots.jumeau.table_territoires import SEUIL, _repartir


# ------------------------------------------------------------------ la table, le contrôle
def test_la_table_est_un_agregat_par_cellule() -> None:
    t = T.table()
    assert t["seuil_menages_observes"] == SEUIL == 30
    assert len(t["seuils_niveau_de_vie"]) == 9
    assert np.all(np.diff(t["seuils_niveau_de_vie"]) > 0)
    for nom in ("regions", "types"):
        a = T.axe(t, nom)
        assert a["menages"].shape == (N_CELLULES, 5)
        # Les deux axes répartissent les mêmes ménages, cellule par cellule.
        assert np.allclose(a["menages"].sum(axis=1),
                           T.axe(t, "regions")["menages"].sum(axis=1), rtol=1e-6)
    assert t["meta"]["population_sha256"].startswith("5ace8bb6")


def test_le_controle_de_d647() -> None:
    """D-646 préenregistré, D-647 : L1 manquée (0,817 contre 0,737 ± 0,05), L2 tenue
    (−4,0 points contre −4,9 ± 3), sur la table seule."""
    t = T.table()
    med_m = T.quantile(t, "regions", "metropole", 0.5)
    med_r = T.quantile(t, "regions", "974", 0.5)
    assert med_m == pytest.approx(24_680.3, abs=1)
    assert med_r == pytest.approx(20_170.7, abs=1)
    assert med_r / med_m == pytest.approx(0.8173, abs=1e-4)
    assert abs(med_r / med_m - 19_110 / 25_920) > 0.05  # manquée
    seuil = 0.6 * med_m
    ecart = 100 * (T.part_sous(t, "types", "rural", seuil)
                   - T.part_sous(t, "regions", "metropole", seuil))
    assert ecart == pytest.approx(-4.03, abs=0.01)
    assert abs(ecart - (10.5 - 15.4)) <= 3  # tenue


def test_l_interpolation_entre_les_deciles() -> None:
    """Une répartition uniforme : le quantile tombe au seuil attendu ; le premier et le
    dernier décile n'ont pas de borne."""
    n_t = len(TYPES)
    pers = np.zeros((N_CELLULES, 1))
    pers[::n_t, 0] = 1.0  # une personne par décile
    t = {"deciles": 10, "types": list(TYPES),
         "seuils_niveau_de_vie": [float(10 * (k + 1)) for k in range(9)],
         "axes": {"x": {"territoires": [{"cle": "a", "libelle": "A"}],
                        "menages": pers.tolist(), "personnes": pers.tolist(),
                        "uc": pers.tolist(), "revenu_disponible": pers.tolist()}}}
    assert T.quantile(t, "x", "a", 0.5) == pytest.approx(50.0)
    assert T.quantile(t, "x", "a", 0.25) == pytest.approx(25.0)
    assert T.quantile(t, "x", "a", 0.05) is None
    assert T.quantile(t, "x", "a", 0.95) is None
    assert T.part_sous(t, "x", "a", 35.0) == pytest.approx(0.35)
    assert T.part_sous(t, "x", "a", 5.0) is None


def test_une_case_trop_petite_prend_son_decile() -> None:
    compte = np.ones((N_CELLULES, 2)) * 100.0
    observes = np.ones((N_CELLULES, 2)) * 50
    compte[0] = [90.0, 10.0]
    observes[0] = [45, 5]  # sous le seuil
    parts, niveau = _repartir(compte, observes, 30)
    assert niveau[0] == 1 and niveau[1:].sum() == 0
    dec = compte[:5].sum(axis=0)
    assert np.allclose(parts[0], dec / dec.sum())
    observes[:5, 1] = 1  # tout le décile sous le seuil : la répartition nationale
    parts, niveau = _repartir(compte, observes, 30)
    assert (niveau[:5] == 2).all()
    assert np.allclose(parts[0], compte.sum(axis=0) / compte.sum())


def test_le_seuil_des_gagnants_est_celui_du_jumeau() -> None:
    from impots.jumeau.gagnants import SEUIL as SEUIL_JUMEAU

    assert T.SEUIL_GAGNANT == SEUIL_JUMEAU


# ------------------------------------------------------------------ la dimension
@pytest.fixture(scope="module")
def session() -> navigateur.Session:
    return navigateur.Session(json.loads(json.dumps(site_jumeau.donnees())))


def _dimension(session, cle: str) -> dict:
    out = json.loads(navigateur.impacts_json(session, json.dumps({"candidat": cle})))
    dims = out["dimensions"]
    return next(d for d in dims if d["cle"] == "territoires") if isinstance(dims, list) \
        else dims["territoires"]


@pytest.fixture(scope="module")
def retailleau(session) -> dict:
    return _dimension(session, "pres2027_retailleau_programme")


def test_la_moyenne_nationale_est_le_gain_des_cellules(session, retailleau) -> None:
    """L'ensemble de chaque axe redonne le gain moyen par ménage des cellules du jumeau,
    et la moyenne des territoires pondérée par leurs ménages aussi."""
    from impots.jumeau.gagnants import gagnants_perdants
    from impots.jumeau.mesures import CONVENTION_PARTS

    choix = {"candidat": "pres2027_retailleau_programme", "mode": "structurel",
             "vue": "figee", "convention": CONVENTION_PARTS}
    ctx = session._contexte({**choix, "theta": {}})
    theta = {t["cle"]: 0.5 for t in ctx["registre"]}
    ctx = session._contexte({**choix, "theta": theta})
    traj, _ = session._derouler(ctx, theta)
    g = gagnants_perdants(traj, ctx["depart"], session.cellules)
    attendu = g.ecart_md[:, :, 0].sum(axis=1) * 1e9 / g.menages.sum()
    ind = {i["cle"]: i for i in retailleau["indicateurs"]}
    for axe in ("types", "regions"):
        assert np.allclose(ind[f"euros_{axe}"]["valeurs"], attendu, rtol=1e-9)
        a = T.axe(T.table(), axe)
        w = (T.parts(a) * g.menages[:, None]).sum(axis=0)
        moyenne = sum(w[j] * np.asarray(v) for j, v in
                      enumerate(ind[f"euros_{axe}"]["par_groupe"].values())) / w.sum()
        assert np.allclose(moyenne, attendu, rtol=1e-9)


def test_les_nombres_de_tete_de_d648(retailleau) -> None:
    """Retailleau, 2035, θ à ½ (D-648) : le gain en % du revenu, l'ensemble, le rural et
    l'outre-mer ; « illustratif »."""
    assert retailleau["statut"] == "illustratif"
    ind = {i["cle"]: i for i in retailleau["indicateurs"]}
    pct = ind["pct_types"]
    assert pct["valeurs"][-1] == pytest.approx(2.077, abs=1e-3)
    assert pct["par_groupe"]["Rural (hors unité urbaine)"][-1] == pytest.approx(1.953,
                                                                                abs=1e-3)
    assert pct["par_groupe"]["Outre-mer"][-1] == pytest.approx(2.302, abs=1e-3)
    assert ind["euros_regions"]["valeurs"][-1] == pytest.approx(1241.3, abs=0.1)


def test_le_mode_reduit_sans_deciles_est_dit(session) -> None:
    """Mélenchon (la chaîne des études, vue vieillie) : pas de choc par décile ; la
    dimension n'est pas calculée et dit pourquoi, jamais zéro."""
    d = _dimension(session, "pres2027_melenchon_programme")
    assert "TerritoiresAbsents" in (d.get("erreur") or "")
    assert not d.get("indicateurs")
