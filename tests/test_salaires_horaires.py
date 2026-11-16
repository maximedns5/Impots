"""Les salaires horaires du privé en parts de Smic, et le rang par statut d'occupation
(but 27, volet grille2, D-497)."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from impots.population import incomes, margins


def _cadre(n: int = 2000, public: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(1)
    return pl.DataFrame({
        "age": np.full(n, 40),
        "quotite_travail": np.where(np.arange(n) % 4 == 0, 0.5, 1.0),
        "fonction_publique": [("etat" if i < public else None) for i in range(n)],
        "particulier_employeur": np.zeros(n, dtype=bool),
        "regime_non_salarie": pl.Series([None] * n, dtype=pl.Utf8),
        "weight": rng.uniform(0.5, 1.5, n),
    })


def test_les_points_de_la_dares_sont_ceux_du_rapport() -> None:
    """Bozio-Wasmer, graphiques 3.8 et 3.9, série 2022 ; fermée à 1 et 4 Smic."""
    points = margins.SALAIRE_HORAIRE_PRIVE_EN_SMIC_2022
    assert points[1.6] == 0.601 and points[1.1] == 0.124 and points[1.43] == 0.50
    assert points[3.04] == 0.90 and points[1.0] == 0.0 and points[4.0] == 1.0
    valeurs = [points[x] for x in sorted(points)]
    assert np.all(np.diff(valeurs) > 0)


def test_les_salaires_horaires_prennent_la_forme_de_la_dares_et_la_masse_reste() -> None:
    """Avant le volet, la fonction n'existait pas : la part sous 1,6 Smic était celle du
    tirage (ici, 30 % sur une loi uniforme de 1 à 3 Smic) ; après, celle de la Dares, au
    facteur de masse près, et la masse privée ne bouge pas."""
    frame = _cadre(public=200)
    n = frame.height
    rng = np.random.default_rng(2)
    quotite = frame["quotite_travail"].to_numpy()
    horaire = rng.uniform(1.0, 3.0, n)
    salaires = horaire * margins.SMIC_ANNUEL_2024 * quotite
    employe = np.ones(n, dtype=bool)
    poids = frame["weight"].to_numpy()
    prive = frame["fonction_publique"].is_null().to_numpy()
    avant = float((poids * prive * (horaire < 1.6)).sum() / (poids * prive).sum())
    assert avant == pytest.approx(0.30, abs=0.03)

    sortie, facteur = incomes._salaires_horaires_en_smic(frame, salaires, employe, poids)
    assert float((sortie * poids)[prive].sum()) == pytest.approx(
        float((salaires * poids)[prive].sum()), rel=1e-12)
    assert np.array_equal(sortie[~prive], salaires[~prive])
    apres = sortie / (margins.SMIC_ANNUEL_2024 * quotite) / facteur
    part = float((poids * prive * (apres < 1.6)).sum() / (poids * prive).sum())
    assert part == pytest.approx(0.601, abs=0.01)
    # Le rang est gardé.
    ordre = np.argsort(horaire[prive], kind="stable")
    assert np.all(np.diff(apres[prive][ordre]) >= -1e-9)


def test_le_facteur_du_statut_d_occupation_est_celui_des_marges() -> None:
    frame = pl.DataFrame({"statut_occupation": ["locataire_hlm", "proprietaire", "autre"]})
    f = incomes._facteur_statut(frame)
    assert f.tolist() == [margins.FACTEUR_STATUT_OCCUPATION["locataire_hlm"],
                          margins.FACTEUR_STATUT_OCCUPATION["proprietaire"], 1.0]
    assert f[0] < f[1]
    assert incomes._facteur_statut(pl.DataFrame({"age": [30]})).tolist() == [1.0]
