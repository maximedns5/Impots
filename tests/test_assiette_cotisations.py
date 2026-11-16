"""La part du brut hors de l'assiette des cotisations : la prime de partage de la valeur et
l'épargne salariale (but 27, volet grille3, D-499, correction 27 du moteur).

Avant, tout D11 cotisait : le modèle portait 780 à 805 Md€ d'assiette privée contre environ
750 à la CCSS. Le test du moteur est vu échouer sur le code d'avant (la colonne n'était pas
câblée : les cotisations ne bougeaient pas) ; celui de la population aussi (la fonction
n'existait pas).
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl
import pytest

from impots.engine import system
from impots.population import incomes, margins
from impots.population.to_openfisca import build_simulation
from tests.test_allegements import _frame

YEAR = 2024


def _calcul(frame: pl.DataFrame, variables: tuple[str, ...]) -> dict[str, np.ndarray]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sim = build_simulation(frame, system.baseline(), YEAR).simulation
        return {v: np.asarray(sim.calculate_add(v, str(YEAR))) for v in variables}


def test_le_total_est_celui_de_l_urssaf_et_de_la_dares() -> None:
    """30,66 Md€ en 2024 : PPV du privé 3 462 M€, épargne salariale 27,2 Md€."""
    assert margins.REMUNERATION_HORS_ASSIETTE_COTISATIONS.value == pytest.approx(30.662e9)


def test_la_part_fait_le_total_et_ne_touche_ni_le_smic_ni_le_public() -> None:
    n = 3000
    rng = np.random.default_rng(3)
    quotite = np.where(np.arange(n) % 4 == 0, 0.5, 1.0)
    frame = pl.DataFrame({
        "age": np.full(n, 40), "quotite_travail": quotite,
        "fonction_publique": [("etat" if i < 300 else None) for i in range(n)],
        "particulier_employeur": np.arange(n) % 50 == 7,
        "regime_non_salarie": pl.Series([None] * n, dtype=pl.Utf8),
    })
    salaires = rng.uniform(1.0, 4.0, n) * margins.SMIC_ANNUEL_2024 * quotite
    salaires[10:20] = margins.SMIC_ANNUEL_2024 * quotite[10:20] * 0.9  # sous le Smic
    poids = np.full(n, 1e4)
    part, taux = incomes._part_hors_assiette(frame, salaires, np.ones(n, dtype=bool), poids,
                                             targets_scale=1.0)
    total = float((part * salaires * poids).sum())
    assert total == pytest.approx(margins.REMUNERATION_HORS_ASSIETTE_COTISATIONS.value)
    assert np.all(part[:300] == 0.0) and np.all(part[np.arange(n) % 50 == 7] == 0.0)
    assert np.all(part[10:20] == 0.0)
    # Ce qui reste dans l'assiette ne passe jamais sous le Smic de la quotité.
    prive = part > 0
    reste = salaires * (1 - part)
    assert np.all(reste[prive] >= margins.SMIC_ANNUEL_2024 * quotite[prive] - 1e-6)
    assert 0 < taux < 1


def test_le_moteur_retire_la_part_des_cotisations_et_pas_de_la_csg() -> None:
    """Deux salariés à 3 000 € par mois (sous le plafond), l'un avec une part de 10 % hors
    assiette : ses cotisations salariales sont 10 % plus basses, sa CSG la même, son brut
    le même."""
    frame = _frame([36_000.0, 36_000.0]).with_columns(
        pl.Series("part_salaire_hors_assiette_cotisations", [0.0, 0.10]))
    r = _calcul(frame, ("cotisations_salariales", "csg_deductible_salaire",
                        "salaire_de_base", "assiette_cotisations_sociales"))
    assert r["salaire_de_base"][1] == pytest.approx(r["salaire_de_base"][0])
    assert r["assiette_cotisations_sociales"][1] == pytest.approx(
        0.9 * r["assiette_cotisations_sociales"][0], rel=1e-6)
    assert r["cotisations_salariales"][1] == pytest.approx(
        0.9 * r["cotisations_salariales"][0], rel=1e-3)
    assert r["csg_deductible_salaire"][1] == pytest.approx(r["csg_deductible_salaire"][0])
