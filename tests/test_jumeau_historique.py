"""But 23, lots 1 et 5 — l'état publié de 2010 à 2025 tient les identités du cadre
(CADRE.md §6).

`etat_initial(annee)` lit les tables manifestées de l'Insee et d'Eurostat. Les cinq
identités, celle de la dette comprise, tiennent à 1e-9 du PIB chaque année : de 2021 à
2025 sur la table de passage d'Eurostat, de 2010 à 2020 sur celle de l'Insee (t. 3.105,
lot 5, D-410), qui a fini les refus « sfa ». Chaque écart publié que le cadre nomme est
lu, et ce qui le cause est vérifié ici (D-405, D-410).
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.dette import comptes
from impots.dette.reference import start_from_accounts
from impots.jumeau import historique, identites, series
from impots.jumeau.blocs import ordre_lot1
from impots.jumeau.champs import EMPLOIS_PUBLIES, IMPOTS_3217
from impots.jumeau.pas import Entrees
from impots.jumeau.trajectoire import calculer
from impots.predictif import annuel, rejouer

ANNEES = list(range(2010, 2026))
AVEC_SFA = [2021, 2022, 2023, 2024, 2025]

pytestmark = pytest.mark.skipif(
    not all((comptes.RAW / f).exists() for f in (
        comptes.PIB_FILE, comptes.TOTALS_FILE, comptes.APU_FILE, comptes.DETTE_FILE,
        comptes.SFA_FILE, historique.PIB_REVENUS_FILE, *series.FICHIERS)),
    reason="les tables de l'Insee, d'Eurostat et de la BDM ne sont pas dans ce checkout "
           "(data/raw est ignoré ; `impots data fetch`)")

@pytest.mark.parametrize("annee", ANNEES)
def test_l_etat_publie_tient_les_identites(annee) -> None:
    """Les cinq identités, dette comprise, chaque année de 2010 à 2025 (D-410)."""
    etat = historique.etat_initial(annee)
    residus = identites.verifier(etat)
    assert {r.split(".")[0] for r in residus} >= {"emplois", "revenus", "apu", "dette"}
    assert max(abs(float(r[0])) for r in residus.values()) < 1e-9
    assert etat["pib"][0] > 1_900 and 0.8 < etat["ratio_dette"][0] < 1.2


def test_les_ecarts_publies_sont_ce_qu_ils_disent() -> None:
    """L'arrondi des totaux est sous la moitié du millième de chaque terme imprimé (le
    refus est dans `etat_initial`) ; la ventilation des secteurs ne s'écarte au-delà de
    l'arrondi de ses dix termes qu'en 2023 et 2024 ; l'écart de millésime de la dette ne
    dépasse le millième qu'en 2025, où il est l'écart entre la variation du stock de
    l'Insee et GD_CH d'Eurostat, B9 étant le même."""
    etats = {a: historique.etat_initial(a) for a in ANNEES}
    ventiles = sorted(a for a, e in etats.items()
                      if abs(e["ventilation_emplois"][0]) > 10 * historique.DEMI_MILLIEME)
    assert ventiles == [2023, 2024]
    millesime = sorted(a for a in AVEC_SFA
                       if abs(etats[a]["ecart_millesime_dette"][0]) > 1e-3)
    assert millesime == [2025]
    eurostat = historique._eurostat()[2025]
    assert eurostat["B9_T3"] == pytest.approx(-etats[2025]["b9"][0], abs=1e-9)
    variation = etats[2025]["dette"][0] - etats[2025]["dette_ouverture"][0]
    assert etats[2025]["ecart_millesime_dette"][0] == pytest.approx(
        variation - eurostat["GD_CH"], abs=1e-9)


def test_l_ajustement_de_comptes_est_celui_du_cadre() -> None:
    """ORADJ, le total des ajustements, contient K61 et KX : `comptes.sfa_publie` les
    comptait deux fois (D-405) ; corrigé par D-410, il est F_ASS + ORADJ + YA3, l'ajustement
    du cadre, à 1e-9 près. Sur l'ancienne somme, l'écart valait K61 + KX, de −510 à
    +483,5 M€ selon l'année."""
    publie = comptes.sfa_publie(AVEC_SFA)
    pib = comptes.gdp(AVEC_SFA)
    for annee in AVEC_SFA:
        sfa = historique.etat_initial(annee)["sfa"][0]
        assert publie[annee] * pib[annee] / 1e9 == pytest.approx(sfa, abs=1e-9)


def test_le_jumeau_part_de_2025_comme_la_chaine() -> None:
    """La référence du jumeau depuis l'état publié de 2025 est celle de `rejouer`
    depuis `start_from_accounts(2025)`, à 1e-9 : même départ, mêmes règles."""
    depart = historique.etat_initial(2025)
    start = start_from_accounts(2025)
    annees = list(range(2026, 2036))
    rejeu = {"start": annuel._start(start),
             "cadre": {"growth": {"real": 0.01, "prices": 0.02},
                       "spending": {"rule": "gele_en_volume", "growth": None},
                       "taux": {"kind": "implicite_tenu", "market_rate": None,
                                "reference": [start.implicit_rate] * 10,
                                "marginal": start.implicit_rate}}}
    _, attendu, _ = rejouer.reference_path(rejeu, rejeu["start"], len(annees))
    jumeau = calculer(depart, entrees=Entrees.depuis_rejeu(rejeu, annees), mesures=[],
                      theta={}, blocs=ordre_lot1(depart, persistance="lue", boucle=False))
    reference, _ = jumeau.niveaux("ratio_dette")
    assert np.max(np.abs(reference[:, 0] - np.array(attendu))) < 1e-9


def test_l_ajustement_d_avant_2021_est_celui_de_l_insee() -> None:
    """De 2010 à 2020, l'ajustement est la somme des groupes (1) à (5) de la t. 3.105, la
    table somme exactement (écart interne nul), et l'écart à la dette de l'Insee est
    l'arrondi au dixième de la table, sauf en 2014 : −0,64 Md€, où la variation de la
    table et celle du stock divergent. C'est un constat de ce millésime (D-410)."""
    sfa = series.lire("sfa_insee")
    etats = {a: historique.etat_initial(a) for a in range(2010, 2021)}
    for annee, etat in etats.items():
        assert etat["sfa"][0] == pytest.approx(sfa[annee], abs=1e-12)
        assert abs(etat["ecart_eurostat"][0]) < 1e-9
    hors_arrondi = sorted(a for a, e in etats.items()
                          if abs(e["ecart_millesime_dette"][0]) > 0.1)
    assert hors_arrondi == [2014]
    assert etats[2014]["ecart_millesime_dette"][0] == pytest.approx(-0.638, abs=0.001)


def test_les_prix_et_le_volume_sont_ceux_des_tables() -> None:
    """Chaque emploi a son prix (l'indice de la t. 1.103 sur celui de l'année d'avant),
    sauf la variation des stocks, qui n'a pas d'indice publié : absente, pas 1. La
    croissance du PIB en volume est celle de la t. 1.102 (2020 : −7,44 %)."""
    etat = historique.etat_initial(2020)
    for nom, _, _, _ in EMPLOIS_PUBLIES:
        assert etat.present(f"prix_{nom}") == (nom != "var_stocks")
    assert etat["croissance_volume_pib"][0] == pytest.approx(-0.0744, abs=5e-5)
    indice = series.lire("indice_prix_c_menages")
    assert historique.etat_initial(2023)["prix_c_menages"][0] == pytest.approx(
        indice[2023] / indice[2022], abs=1e-12)


def test_les_impots_de_la_t3217_sont_dans_l_etat_et_absents_quand_ils_n_existent_pas() -> None:
    """Les principaux impôts de la t. 3.217 sont des sous-champs de l'état publié ; la
    contribution à l'audiovisuel public, supprimée en 2022, y est absente ensuite."""
    for annee in (2010, 2025):
        etat = historique.etat_initial(annee)
        presents = {nom for nom, _ in IMPOTS_3217 if etat.present(f"impot_{nom}")}
        attendus = {nom for nom, _ in IMPOTS_3217} - ({"audiovisuel"} if annee == 2025
                                                      else set())
        assert presents == attendus
    assert historique.etat_initial(2021).present("impot_audiovisuel")
    assert not historique.etat_initial(2022).present("impot_audiovisuel")


def test_les_champs_des_lots_2_a_4_que_les_series_portent_sont_ecrits() -> None:
    """D-412 : l'emploi, le chômage, la population active, la rémunération moyenne (D1
    par salarié, la définition du lot 4), le solde des échanges et la contribution du
    solde extérieur sont écrits depuis les séries publiées ; les créations de sociétés,
    les fermetures, la FBCF des seules SNF et le reste du monde hors échanges restent
    absents ; les séries sans champ exact sont au groupe « histoire »."""
    etat = historique.etat_initial(2024)
    assert etat["emploi_total"][0] == pytest.approx(30591.9, abs=1e-9)
    assert etat["emploi_salarie"][0] == pytest.approx(27181.7, abs=1e-9)
    # Eurostat, 15-74 ans ; l'enquête Emploi (t. 302, la référence du lot 4) en compte
    # 2 342,8 milliers : 11,8 milliers d'écart entre les deux publications, dit.
    assert etat["chomage"][0] == pytest.approx(2331.0, abs=1e-9)
    assert etat["population_active"][0] == pytest.approx(30591.9 + 2331.0, abs=1e-9)
    assert etat["salaire_moyen"][0] == pytest.approx(
        etat["remunerations"][0] * 1e6 / 27181.7, rel=1e-12)
    assert etat["salaire_brut_moyen"][0] == pytest.approx(
        series.lire("salaire_moyen")[2024], rel=1e-12)
    assert etat["salaire_brut_moyen"][0] < etat["salaire_moyen"][0]
    assert etat["solde_exterieur"][0] == pytest.approx(
        etat["exportations"][0] - etat["importations"][0], abs=1e-12)
    for nom in ("creations_societes", "fermetures_societes", "stock_societes",
                "investissement_entreprises", "demande_mondiale", "prix_relatifs",
                "solde_courant"):
        assert not etat.present(nom), nom
    assert etat["creations_entreprises"][0] == pytest.approx(1_111_238, abs=1e-9)
    assert etat["defaillances"][0] == pytest.approx(66_106, abs=1e-9)
    assert etat["volume_exportations"][0] == pytest.approx(
        series.lire("volume_exportations")[2024], abs=1e-12)


@pytest.mark.parametrize("annee", [2010, 2020, 2024])
def test_la_contribution_du_solde_exterieur_est_celle_des_volumes_publies(annee) -> None:
    """La formule du bloc `commerce` sur la t. 1.101 et la t. 1.103 redonne la variation
    des volumes de la t. 1.102 aux prix de l'année d'avant, à l'arrondi des indices
    (au plus 2e-6 du PIB de 2010 à 2025)."""
    etat = historique.etat_initial(annee)
    vol = {n: series.lire(f"volume_{n}") for n in ("exportations", "importations")}
    ind = {n: series.lire(f"indice_prix_{n}") for n in ("exportations", "importations")}
    pib = series.lire("pib")
    attendu = sum(s * (vol[n][annee] - vol[n][annee - 1]) * ind[n][annee - 1] / 100
                  for n, s in (("exportations", 1), ("importations", -1))) / pib[annee - 1]
    assert etat["contribution_solde_exterieur"][0] == pytest.approx(attendu, abs=5e-6)


@pytest.mark.parametrize("annee", [1996, 1999, 2003, 2007])
def test_l_histoire_longue_tient_les_identites(annee) -> None:
    """D-446 : de 1996 à 2009, l'état publié tient les cinq identités à 1e-9 ; son
    ajustement flux-stocks est la variation de la dette moins le déficit, sans écart ;
    les créations et les défaillances n'y sont pas."""
    etat = historique.etat_initial(annee)
    residus = identites.verifier(etat)
    assert max(abs(float(r[0])) for r in residus.values()) < 1e-9
    calcul = historique.sfa_calcule(annee)
    assert float(etat["sfa"][0]) == calcul["sfa"]
    assert float(etat["ecart_eurostat"][0]) == 0.0
    assert abs(float(etat["ecart_millesime_dette"][0])) < 1e-9
    assert not etat.present("creations_classiques") and etat.present("taux_oat_10ans")
    assert 0.55 < etat["ratio_dette"][0] < 0.7


def test_l_ajustement_calcule_recoupe_la_t3105() -> None:
    """D-446 : la variation de la dette moins le déficit redonne la t. 3.105 à 0,1 Md€
    près de 2010 à 2020, sauf 2014 (−0,63 Md€, l'écart de millésime de D-410)."""
    t3105 = series.lire("sfa_insee")
    ecarts = {a: historique.sfa_calcule(a)["sfa"] - t3105[a] for a in range(2010, 2021)}
    assert abs(ecarts.pop(2014) + 0.638) < 0.01
    assert max(abs(e) for e in ecarts.values()) < 0.1
    with pytest.raises(historique.HistoriqueError):
        historique.etat_initial(1995)
