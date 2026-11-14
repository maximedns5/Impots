"""But 23, lot 5 — les séries publiées de 2010 à 2025 se lisent et recoupent leur total.

Chaque série de `jumeau.series` a sa source manifestée et son code ; chacune est lue sur
toutes les années, et recoupe un total publié à l'arrondi imprimé près. Un écart au-delà
de l'arrondi est un constat de ce millésime, figé ici tel qu'il a été lu la première fois
(D-410) : s'il change, le millésime a changé, et le constat se réécrit sur une D-entrée.
"""

from __future__ import annotations

import pytest

from impots.dette import comptes
from impots.jumeau import series

pytestmark = pytest.mark.skipif(
    not all((comptes.RAW / f).exists() for f in series.FICHIERS),
    reason="les tables de l'Insee, d'Eurostat et de la BDM ne sont pas dans ce checkout "
           "(data/raw est ignoré ; `impots data fetch`)")


@pytest.fixture(scope="module")
def recoupements() -> dict[str, dict[int, float]]:
    return series.recoupements()


def test_chaque_serie_a_sa_source_manifestee_et_toutes_ses_annees() -> None:
    from impots.population.ingest import load_manifest

    manifeste = load_manifest()
    for nom, serie in series.SERIES.items():
        assert manifeste[serie.fichier].url, nom
        assert serie.code and serie.producteur and serie.unite, nom
        valeurs = serie.lire()
        if nom.startswith("impot_"):
            continue                       # un impôt n'existe pas toutes les années
        assert set(series.ANNEES) <= set(valeurs), nom


def test_les_impots_qui_naissent_ou_meurent_sont_absents_hors_de_leur_vie() -> None:
    """La contribution à l'audiovisuel public s'arrête en 2021 (supprimée en 2022)."""
    assert sorted(series.lire("impot_audiovisuel")) == list(range(2010, 2022))


def _arrondi(valeur: float, volume: float, demi: float = 0.0005) -> float:
    """La borne d'arrondi de 100 V / L, V et L imprimés au millième, l'indice aussi."""
    return demi + 100 * demi * (1 + abs(valeur) / volume) / volume


def test_les_indices_de_prix_sont_la_valeur_sur_le_volume(recoupements) -> None:
    """t. 1.103 = 100 × t. 1.101 / t. 1.102, à l'arrondi des trois tables près, sauf pour
    les APU : leur consommation en 2023 et 2024 (+0,004 et −0,067 point d'indice) et leur
    investissement en 2023 et 2024 (+0,096 et +0,486), les années où les secteurs de la
    t. 1.101 ne somment pas à leurs totaux (D-405) ; et leur consommation de 2015, à
    −0,0007 pour une borne de 0,00066, au bord de l'arrondi. Constat du premier calcul."""
    hors = {}
    for nom, _, _ in series.EMPLOIS_SERIES:
        valeur, volume = series.lire(nom), series.lire(f"volume_{nom}")
        for annee, ecart in recoupements[f"indice_prix_{nom}"].items():
            if abs(ecart) > _arrondi(valeur[annee], volume[annee]):
                hors[(nom, annee)] = round(ecart, 4)
    assert hors == {("c_apu", 2015): -0.0007, ("c_apu", 2023): 0.0037,
                    ("c_apu", 2024): -0.0665, ("fbcf_apu", 2023): 0.0961,
                    ("fbcf_apu", 2024): 0.4859}


def test_les_impots_de_la_t3217_somment_au_compte_des_apu(recoupements) -> None:
    """D5 et D91 de la t. 3.217 sont ceux de la t. 3.201 au millième ; le D2, moins les
    impôts de l'Union européenne, aussi depuis 2019. De 2010 à 2018, la t. 3.217 dépasse
    la t. 3.201 de 54 à 67 millions : un écart de ce millésime, lu, non expliqué."""
    assert max(abs(e) for e in recoupements["t3217_d5"].values()) < 1e-3
    assert max(abs(e) for e in recoupements["t3217_d91"].values()) < 1e-3
    d2 = recoupements["t3217_d2_moins_ue"]
    assert all(abs(d2[a]) < 1e-3 for a in range(2019, 2026))
    assert all(0.053 <= d2[a] <= 0.068 for a in range(2010, 2019)), d2


def test_la_t3105_somme_et_recoupe_la_t3201_et_eurostat(recoupements) -> None:
    """La variation de la dette est le déficit plus les cinq groupes ; le déficit est −B9
    de la t. 3.201 à l'arrondi au dixième ; l'ajustement est celui d'Eurostat de 2021 à
    2025 à l'arrondi de cinq groupes au dixième (0,25 Md€)."""
    assert max(abs(e) for e in recoupements["t3105_variation"].values()) < 1e-9
    assert max(abs(e) for e in recoupements["t3105_deficit"].values()) <= 0.05
    eurostat = recoupements["t3105_eurostat"]
    assert sorted(eurostat) == [2021, 2022, 2023, 2024, 2025]
    assert max(abs(e) for e in eurostat.values()) <= 0.25


def test_l_emploi_et_les_salaires_somment_leurs_cinq_branches(recoupements) -> None:
    """Le total des branches contre les cinq grandes branches (A5), imprimées au dixième
    de millier (emploi) et au millième de milliard (salaires)."""
    for nom in ("emploi_total", "emploi_salarie"):
        assert max(abs(e) for e in recoupements[nom].values()) <= 6 * 0.05 + 1e-9, nom
    assert max(abs(e) for e in recoupements["salaires_bruts"].values()) <= 6 * 0.0005
    salaire = series.lire("salaire_moyen")
    assert 30_000 < salaire[2010] < salaire[2025] < 45_000


def test_le_chomage_et_l_oat_recoupent_leurs_totaux(recoupements) -> None:
    """Hommes plus femmes égalent l'ensemble au millier près (trois arrondis à l'unité) ;
    la moyenne annuelle de l'OAT est celle de ses douze mois aux deux arrondis du centième,
    sauf 2025 (−0,016 point) : la table annuelle date de février 2026, la mensuelle de
    novembre, et les mois de 2025 ont été révisés entre les deux."""
    assert max(abs(e) for e in recoupements["chomeurs"].values()) <= 1.5
    oat = recoupements["taux_oat_10ans"]
    assert [a for a, e in oat.items() if abs(e) > 0.01] == [2025]
    assert oat[2025] == pytest.approx(-0.016, abs=0.001)
    taux = series.lire("taux_chomage")
    assert min(taux.values()) > 7 and max(taux.values()) < 11


def test_les_creations_et_les_defaillances_recoupent_leurs_totaux(recoupements) -> None:
    """Les créations : micro-entrepreneurs plus entreprises classiques égalent l'ensemble,
    exactement. Les défaillances : le total dépasse la somme des onze secteurs de 66 à
    431 par an, moins de 1 % : les entreprises dont le secteur n'est pas connu."""
    assert all(e == 0 for e in recoupements["creations_entreprises"].values())
    total = series.lire("defaillances")
    ecarts = recoupements["defaillances"]
    assert all(0 < ecarts[a] < 0.01 * total[a] for a in series.ANNEES), ecarts
    assert total[2021] < 30_000 < 60_000 < total[2025]
