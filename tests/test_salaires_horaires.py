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


def test_le_point_de_l_insee_tient_la_densite_de_2_5_a_3_smic(monkeypatch) -> None:
    """D-552 : un point à 2,5 Smic, ajusté sur le D8 du salaire brut horaire de l'Insee
    (27,2 € en 2022, 2,507 Smic), place 86,4 % des salariés sous 2,5 Smic, contre 82,1 %
    sur la fonction linéaire de la Dares de 2,01 à 3,04 Smic ; moins de salariés de 2,5 à
    3,04 Smic, autant sous 2,01 et sous 3,04."""
    assert margins.SALAIRE_HORAIRE_BRUT_PRIVE_DECILES_2022[0.8] == 27.2
    assert margins.SALAIRE_HORAIRE_PRIVE_D8_INSEE.value == pytest.approx(2.507, abs=5e-4)
    frame = _cadre(n=20000, public=1)
    n = frame.height
    quotite = frame["quotite_travail"].to_numpy()
    horaire = np.random.default_rng(3).uniform(1.0, 3.9, n)
    salaires = horaire * margins.SMIC_ANNUEL_2024 * quotite
    employe, poids = np.ones(n, dtype=bool), frame["weight"].to_numpy()
    poids = np.where(frame["fonction_publique"].is_null().to_numpy(), poids, 0.0)

    def parts(point: bool) -> list[float]:
        # D-580 : les points de l'Urssaf remplacent celui-ci ; il se lit sans eux.
        monkeypatch.setattr(incomes, "POINTS_URSSAF", False)
        monkeypatch.setattr(incomes, "POINT_INSEE", point)
        sortie, f = incomes._salaires_horaires_en_smic(frame, salaires, employe, poids)
        h = sortie / (margins.SMIC_ANNUEL_2024 * quotite) / f
        return [float((poids * (h < x)).sum() / poids.sum()) for x in (2.01, 2.5, 3.04)]

    sans, avec = parts(False), parts(True)
    assert sans[1] == pytest.approx(0.821, abs=0.005)
    assert avec[1] == pytest.approx(0.864, abs=0.005)
    assert avec[0] == pytest.approx(sans[0], abs=0.005)
    assert avec[2] == pytest.approx(sans[2], abs=0.005)


def test_les_points_de_l_urssaf_tiennent_la_forme_de_2_a_3_5_smic(monkeypatch) -> None:
    """D-580 : les ETP de l'Urssaf par 0,1 Smic (CCSS, mai 2024, graphique 3, 2022) font,
    dans ceux de 1 à 3,5 Smic, 11,80 % de 2 à 2,5, 6,37 % de 2,5 à 3 et 3,84 % de 3 à 3,5.
    Les trois points qui en sont tirés placent 85,2, 90,7 et 94,0 % des salariés sous 2,5,
    3 et 3,5 Smic, à la place du point de l'Insee (86,4 % à 2,5) et du D9 de la Dares
    (90 % à 3,04) ; le Q3 de la Dares (75 % à 2,01) reste. Sur le code d'avant (D-553), la
    part sous 3 Smic était 89,7 %, sous 3,5 Smic 94,8 %."""
    etp = margins.SALAIRE_PRIVE_ETP_URSSAF_2022
    total = sum(etp.values())

    def tranche(a: float, b: float) -> float:
        return sum(v for x, v in etp.items() if a - 1e-9 <= x < b - 1e-9) / total

    assert total == pytest.approx(15220, abs=5)
    assert tranche(2.0, 2.5) == pytest.approx(0.1180, abs=5e-4)
    assert tranche(2.5, 3.0) == pytest.approx(0.0637, abs=5e-4)
    assert tranche(3.0, 3.5) == pytest.approx(0.0384, abs=5e-4)

    frame = _cadre(n=20000, public=1)
    n = frame.height
    quotite = frame["quotite_travail"].to_numpy()
    horaire = np.random.default_rng(4).uniform(1.0, 3.99, n)
    salaires = horaire * margins.SMIC_ANNUEL_2024 * quotite
    employe = np.ones(n, dtype=bool)
    poids = np.where(frame["fonction_publique"].is_null().to_numpy(),
                     frame["weight"].to_numpy(), 0.0)

    def parts(urssaf: bool) -> list[float]:
        monkeypatch.setattr(incomes, "POINTS_URSSAF", urssaf)
        monkeypatch.setattr(incomes, "POINT_INSEE", True)
        sortie, f = incomes._salaires_horaires_en_smic(frame, salaires, employe, poids)
        h = sortie / (margins.SMIC_ANNUEL_2024 * quotite) / f
        return [float((poids * (h < x)).sum() / poids.sum())
                for x in (2.01, 2.5, 3.0, 3.04, 3.5)]

    avant, apres = parts(False), parts(True)
    assert apres[1] == pytest.approx(0.852, abs=0.005)
    assert apres[2] == pytest.approx(0.907, abs=0.005)
    assert apres[4] == pytest.approx(0.940, abs=0.005)
    assert apres[0] == pytest.approx(0.75, abs=0.005)
    assert avant[1] == pytest.approx(0.864, abs=0.005)
    assert avant[2] == pytest.approx(0.897, abs=0.005)
    assert avant[3] == pytest.approx(0.90, abs=0.005)
    assert avant[4] == pytest.approx(0.948, abs=0.005)
