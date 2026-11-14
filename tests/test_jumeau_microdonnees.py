"""But 23, D-425 — les estimateurs des données fines, sur des panneaux synthétiques.

Les estimateurs retrouvent un coefficient connu ; la variance CR1 par projections égale
celle des indicatrices ; le bootstrap sauvage groupé tient sa taille sous H₀ ; les
paramètres du droit sont datés par la base des mesures votées. Les doses réelles se
lisent sur les fichiers manifestés quand ils sont là.
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.dette import comptes
from impots.jumeau import microdonnees as m
from impots.jumeau import votees


def _panneau(beta: float, graine: int, *, regions: int = 12, secteurs: int = 10,
             annees: int = 14, choc: float = 0.05, bruit: float = 0.05):
    """y_rst = a_rs + b_rt + β d_st + e_st + u_rst : la dose varie par secteur et année,
    le choc e_st est commun aux régions d'un secteur (d'où la grappe par secteur)."""
    rng = np.random.default_rng(graine)
    expo = rng.uniform(0.5, 1.5, secteurs)
    chemin = np.r_[np.zeros(annees // 3), np.linspace(-2, -5, annees - annees // 3)]
    d = expo[:, None] * chemin[None, :] + rng.normal(0, 0.3, (secteurs, annees))
    a = rng.normal(0, 1, (regions, secteurs))
    b = rng.normal(0, 0.5, (regions, annees))
    e = rng.normal(0, choc, (secteurs, annees))
    r, s, t = np.meshgrid(range(regions), range(secteurs), range(annees), indexing="ij")
    r, s, t = r.ravel(), s.ravel(), t.ravel()
    y = (a[r, s] + b[r, t] + beta * d[s, t] + e[s, t]
         + rng.normal(0, bruit, r.size))
    return y, d[s, t], [r * 100 + s, r * 100 + t], s


def test_estimer_retrouve_un_coefficient_connu() -> None:
    estimes, se = [], []
    for graine in range(40):
        y, x, effets, grappe = _panneau(0.03, graine)
        r = m.estimer(y, x, ["dose"], effets, grappe, tirages=199, interet=[])
        estimes.append(r.beta[0])
        se.append(r.ligne("dose")["se"])
    estimes = np.array(estimes)
    dispersion = estimes.std(ddof=1)
    assert abs(estimes.mean() - 0.03) < 3 * dispersion / np.sqrt(len(estimes))
    # l'écart-type annoncé est de l'ordre de la dispersion des estimations
    assert 0.6 < np.mean(se) / dispersion < 1.8


def test_le_bootstrap_sauvage_tient_sa_taille_sous_h0() -> None:
    rejets = []
    for graine in range(300, 450):
        y, x, effets, grappe = _panneau(0.0, graine)
        r = m.estimer(y, x, ["dose"], effets, grappe, tirages=199)
        rejets.append(r.p_wcr[0] < 0.10)
    assert np.mean(rejets) < 0.16


def test_un_vrai_effet_est_detecte() -> None:
    y, x, effets, grappe = _panneau(0.10, 7)
    r = m.estimer(y, x, ["dose"], effets, grappe, tirages=999)
    assert r.p_wcr[0] < 0.05 and abs(r.beta[0] - 0.10) < 4 * r.ligne("dose")["se"]


def test_projections_et_cr1_egalent_les_indicatrices() -> None:
    y, x, effets, grappe = _panneau(0.03, 3, regions=4, secteurs=5, annees=6)
    r = m.estimer(y, x, ["dose"], effets, grappe, tirages=99, interet=[])
    D = np.column_stack([x] + [(effets[0] == v).astype(float) for v in np.unique(effets[0])]
                        + [(effets[1] == v).astype(float) for v in np.unique(effets[1])][1:])
    coef, *_ = np.linalg.lstsq(D, y, rcond=None)
    assert abs(coef[0] - r.beta[0]) < 1e-9
    u = y - D @ coef
    A = np.linalg.pinv(D.T @ D)
    G = len(np.unique(grappe))
    S = np.array([D[grappe == g].T @ u[grappe == g] for g in np.unique(grappe)])
    rang = np.linalg.matrix_rank(D)
    n = len(y)
    V = G / (G - 1) * (n - 1) / (n - rang) * A @ S.T @ S @ A
    assert abs(np.sqrt(V[0, 0]) - r.se_cr1[0]) < 1e-9


def test_les_parametres_du_droit_sont_dates_par_la_base_des_mesures() -> None:
    base = {mv.id: mv for mv in votees.mesures()}
    for nom, etapes in m.PARAMETRES.items():
        annees = set()
        for id_ in m.MESURES_DES_PARAMETRES[nom]:
            assert id_ in base, id_
            annees |= set(base[id_].annees_effet)
        assert set(etapes) <= annees, (nom, sorted(set(etapes) - annees))
    assert m.parametre("cice", 2012, 0.0) == 0.0
    assert m.parametre("cice", 2016, 0.0) == 0.06
    assert m.parametre("is_grandes", 2018, m.IS_AVANT) == m.IS_AVANT
    assert m.parametre("is_petites", 2019, m.IS_AVANT) == 28.0


def test_le_bareme_de_la_cvae_est_continu() -> None:
    for seuil in (0.5, 3.0, 10.0, 50.0):
        assert abs(m.taux_cvae(seuil - 1e-9) - m.taux_cvae(seuil + 1e-9)) < 1e-9
    assert m.taux_cvae(0.2) == 0.0 and m.taux_cvae(80) == 0.015


def test_une_reponse_de_la_bdm_se_lit_en_annees_completes() -> None:
    xml = ('<Series REF_AREA="R11" ACTIVITE_CREAT_ENT="FZ" INDICATEUR="TYPE-ENT_PM" '
           'CORRECTION="BRUT" FREQ="T">'
           + "".join(f'<Obs TIME_PERIOD="2015-Q{q}" OBS_VALUE="{q}" OBS_STATUS="A"/>'
                     for q in range(1, 5))
           + '<Obs TIME_PERIOD="2016-Q1" OBS_VALUE="9" OBS_STATUS="A"/></Series>')
    panneau = m.panneau_bdm(xml, "TYPE-ENT_PM", ("FZ",))
    assert panneau == {("R11", "FZ"): {2015: 10.0}}
    with pytest.raises(m.MicrodonneesError):
        m.annuel({"2015-03": 1.0})


def test_la_loi_de_student() -> None:
    assert m.student_bilateral(0.0, 8) == pytest.approx(1.0)
    assert m.student_bilateral(2.306, 8) == pytest.approx(0.05, abs=1e-4)
    assert m.student_bilateral(1.96, 10_000) == pytest.approx(0.05, abs=1e-3)


def test_l_echelle_des_theta() -> None:
    assert m.vers_theta(0.03, 0.006, 0.0, 0.03, 0.06) == {
        "theta": 0.5, "se_theta": pytest.approx(0.1), "identifie": True}
    bas = m.vers_theta(0.31, 0.13, 0.31, 0.44, 0.52)
    assert bas["theta"] == 0.0 and bas["se_theta"] == pytest.approx(0.5)
    assert not bas["identifie"]


@pytest.mark.skipif(not (comptes.RAW / m.ESANE).exists() or not (comptes.RAW / m.SALAIRES)
                    .exists(), reason="Ésane 2023 et l'Insee Première n° 2079 ne sont pas "
                    "dans ce checkout (data/raw est ignoré ; `impots data fetch`)")
def test_les_doses_reelles_sont_nulles_en_2012_et_negatives_ensuite() -> None:
    k = m.constantes()
    assert 0.7 < k.g < 0.8 and 0.3 < k.kappa < 1.0
    for e in m.expositions().values():
        assert all(abs(v) < 1e-12 for n, v in m.doses(e, 2012, k).items())
        for a in (2013, 2016, 2019, 2022, 2024):
            d = m.doses(e, a, k)
            assert d["travail"] < 0 and d["marge"] < 0 and d["taux"] < 0
        assert 0 < e.parts_smic[1.6] < e.parts_smic[2.5] < e.parts_smic[3.5] <= 1
