"""But 24, D-434 — les données fines du volet `fines`, sur des panneaux synthétiques.

La dose `travail` d'une cellule est celle de D-425 ; la projection avec une tendance par
cellule égale la régression sur ses indicatrices et ses pentes ; la dose du coût du
capital est la réponse du bloc ; le critère du but lit le bon côté de la loi ; le chômage
localisé et l'Urssaf se lisent comme publiés.
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.jumeau import a_priori
from impots.jumeau import microdonnees as m


def _exposition(parts: dict[float, float]) -> m.Exposition:
    cat = {c: {"n": 10.0, "eqtp": 100.0, "ca": 1.0, "va": 50.0, "fp": 30.0, "ebe": 15.0}
           for c in m.CATEGORIES}
    return m.Exposition("X", cat, 1.0, parts)


def test_la_dose_travail_d_une_cellule_est_celle_de_d425() -> None:
    parts = {1.6: 0.31, 2.25: 0.52, 2.5: 0.57, 3.3: 0.70, 3.5: 0.72}
    e = _exposition(parts)
    k = m.Constantes(g=0.763, kappa=0.668)
    for annee in range(2010, 2027):
        assert m.dose_travail(parts, annee, k.g) == pytest.approx(
            m.doses(e, annee, k)["travail"], abs=1e-15)
    assert m.dose_travail(parts, 2012, k.g) == 0.0
    # 2016 : trois quarts de l'écart entre 1,6 et 3,5 SMIC
    attendu = -0.763 * (0.06 * 0.57 + 0.018 * (0.31 + 0.75 * (0.72 - 0.31)))
    assert m.dose_travail(parts, 2016, 0.763) == pytest.approx(attendu)


def test_les_tendances_par_cellule_egalent_les_indicatrices() -> None:
    rng = np.random.default_rng(5)
    cellules = np.repeat(np.arange(6), 8)
    annee = np.tile(np.arange(8), 6)
    region = cellules // 3
    x = rng.normal(size=48)
    y = 0.2 * x + 0.1 * cellules * annee + rng.normal(size=48)
    eff_ra = region * 100 + annee
    r = m.estimer(y, x, ["x"], [eff_ra], region * 10 + cellules % 3, tirages=9,
                  interet=[], tendance=(cellules, annee))
    D = [x] + [(cellules == c).astype(float) for c in range(6)]
    D += [(cellules == c) * annee for c in range(6)]
    D += [(eff_ra == v).astype(float) for v in np.unique(eff_ra)]
    coef, *_ = np.linalg.lstsq(np.column_stack(D), y, rcond=None)
    assert abs(coef[0] - r.beta[0]) < 1e-8


def test_la_dose_du_cout_du_capital_est_la_reponse_du_bloc() -> None:
    reponse = [-0.1, -0.4, -0.7, -0.9, -1.0, -1.0, -1.0]
    chocs = {2016: 0.0, 2017: -0.02, 2018: -0.02, 2019: -0.05}
    assert m.dose_cout_capital(chocs, 2016, reponse) == 0.0
    assert m.dose_cout_capital(chocs, 2018, reponse) == pytest.approx(-0.02 * -0.4)
    attendu = -0.02 * reponse[2] + -0.03 * reponse[0]
    assert m.dose_cout_capital(chocs, 2019, reponse) == pytest.approx(attendu)
    with pytest.raises(m.MicrodonneesError):
        m.dose_cout_capital(chocs, 2020, reponse)


def test_le_critere_du_but_lit_le_cote_de_l_estimation() -> None:
    loi = a_priori.Loi(0.5, 0.2, 0.4)
    bas = m.critere_d434(0.30, 0.01, (0.0, 0.44, 0.60), loi)  # θ < ½ : s₋ = 0,2
    assert bas["s_loi"] == 0.2 and bas["seuil"] == pytest.approx(0.1)
    assert bas["se_theta"] == pytest.approx(0.01 / 0.88) and bas["identifie"]
    haut = m.critere_d434(0.55, 0.05, (0.0, 0.44, 0.60), loi)  # θ > ½ : s₊ = 0,4
    assert haut["s_loi"] == 0.4 and haut["se_theta"] == pytest.approx(0.05 / 0.32)
    assert haut["identifie"] and not m.critere_d434(0.55, 0.07, (0.0, 0.44, 0.60),
                                                     loi)["identifie"]


def test_le_chomage_localise_est_la_moyenne_des_trimestres() -> None:
    def serie(zone: str, base: float) -> str:
        obs = "".join(f'<Obs TIME_PERIOD="2015-Q{q}" OBS_VALUE="{base + q}"/>'
                      for q in range(1, 5))
        return (f'<Series REF_AREA="D{zone}" INDICATEUR="TAUX_CHOMAGE_LOCALISE" '
                f'CORRECTION="CVS" FREQ="T">{obs}'
                '<Obs TIME_PERIOD="2016-Q1" OBS_VALUE="3"/></Series>')
    texte = "".join(serie(d, 5.0) for d in m.DEPARTEMENTS) + serie("971", 20.0)
    chom = m.chomage_departements(texte)
    assert set(chom) == set(m.DEPARTEMENTS) and chom["2A"] == {2015: 7.5}
    with pytest.raises(m.MicrodonneesError, match="absent"):
        m.chomage_departements("".join(serie(d, 5.0) for d in m.DEPARTEMENTS[1:]))


def test_l_urssaf_se_lit_par_departement_et_secteur() -> None:
    entete = ("﻿region;ancienne_region;departement;grand_secteur_d_activite;"
              "secteur_na17i;annee;code_region;code_ancienne_region;code_departement;"
              "nombre_d_etablissements;effectifs_salaries_moyens;masse_salariale\n")
    lignes = ["a;b;Ain;GS;IZ Hébergement et restauration;2012;84;82;01;10;100;2000000",
              "a;b;Ain;GS;IZ Hébergement et restauration;2011;84;82;01;10;;2000000",
              "a;b;Ain;GS;MNa Intérimaires;2012;84;82;01;10;100;2000000",
              "a;b;Guadeloupe;GS;IZ Hébergement et restauration;2012;1;1;971;1;5;10",
              "a;b;Ain;GS;\"C2-C5 Fabrication, raffinage\";2012;84;82;01;3;50;3000000"]
    cel = m.urssaf_departements(entete + "\n".join(lignes) + "\n")
    assert cel == {("01", "IZ"): {2012: (100.0, 2_000_000.0)},
                   ("01", "C2-C5"): {2012: (50.0, 3_000_000.0)}}
    rel = m.salaire_relatif(cel, annees=(2012,))
    assert rel[("01", "IZ")] == pytest.approx(20_000 / (5_000_000 / 150))
