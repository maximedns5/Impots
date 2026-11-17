"""Le papillon de Mélenchon (but 27, D-500 à D-503) : les nombres que le volet change ou
établit, sur le jumeau seul (aucune passe), à θ½."""

from __future__ import annotations

import pytest

from impots.jumeau import papillon as pa

P = "pres2027_melenchon_"


@pytest.fixture(scope="module")
def session():
    from impots import site_jumeau
    from impots.jumeau import navigateur

    return navigateur.Session(site_jumeau.donnees())


def _dette_emploi(session, mesures, cle):
    traj, _ = pa.trajectoire(session, mesures, cle=cle)
    e = pa.ecarts(traj)
    return traj, e["dette_pts"][-1], e["emploi_total"][-1]


def test_point_indice_ne_renchérit_plus_le_travail_prive(session):
    # D-500 : avant, −39,5 milliers d'emplois en 2035 et +2,765 pt (figée) ; les
    # cotisations de la paie publique lues comme un coût du travail privé.
    m = session.mesure_structurel(P + "point_indice_10", "figee", "parts_premiere_annee")
    assert "cotisations_employeurs" not in m.impulsions[2026]
    assert m.prelevements_publics[2026]["cotisations_employeurs"] == pytest.approx(-12.526,
                                                                                    abs=1e-3)
    assert m.conventions["impulsions"][2026] == pa.CONVENTION_PUBLIQUE
    _, dette, emploi = _dette_emploi(session, [m], P + "point_indice_10")
    # D-567 : les cellules du jumeau refaites sur la population de D-521 (D-512, f382efe),
    # puis de D-553 (e4a635c) : emploi 33,654 → 33,628 → 33,628 milliers, dette 2,0423
    # → 2,0521 → 2,0517 pt (D-500 : 33,7 et 2,042, sur la population du but 19).
    assert emploi == pytest.approx(33.63, abs=0.05)
    assert dette == pytest.approx(2.052, abs=5e-4)


def test_melenchon_tourne_en_structurel_par_les_mesures_seules(session):
    # D-502 : refusé avant (D-489) ; la somme des coûts tient au bit.
    assert all(v == 0.0 for v in pa.verifier_somme(
        session, "melenchon", "figee", "parts_premiere_annee").values())
    ms = pa.mesures_seules(session, "melenchon", "figee")
    assert ms[-1].impulsions[2026]["cotisations_employeurs"] == pytest.approx(1.333, abs=1e-3)
    traj, dette, emploi = _dette_emploi(session, ms, P + "programme")
    # D-567 : D-502 tenait 12,306 pt et 186,1 milliers (cellules du but 19). Les cellules
    # de D-521 (D-512, f382efe) : 12,365 et 187,1 ; l'incidence pondérée et le choc
    # combiné (D-540, D-541, 1f9ded0) : 12,375 et 188,2 ; la diffusion recentrée par défaut
    # (D-551, 013d1ea) : 10,613 et 50,6 ; les cellules de D-553 (e4a635c) : 10,612, 50,7.
    assert dette == pytest.approx(10.612, abs=5e-4)
    assert emploi == pytest.approx(50.7, abs=0.05)
    assert max(pa.identites(traj, ms).values()) < 1e-12
    c = pa.cascade_simple(traj)
    assert abs(c["residu"]) < 1e-9
    # Les mêmes étapes : statique 23,725 → 23,724 → 23,724 → 23,689 → 23,688 Md€ ; prime
    # de risque 1,555 → 1,561 → 1,562 → 1,330 → 1,3295 pt.
    assert c["fleches"]["statique"] == pytest.approx(23.688, abs=5e-4)
    assert pa.prime_de_risque(traj, session._modele("structurel", ms[0], P + "programme")[1],
                              0.5)["dette_pts"][-1] == pytest.approx(1.3295, abs=5e-4)


def test_le_pfu_supprime_se_retourne_sur_les_dividendes():
    # D-501 : au centre de C10, un euro de dividende d'un foyer à 45 % rapporte moins
    # après la suppression qu'avant ; la recette mécanique est de +11,1 centimes.
    t45 = pa.dividendes_pfu(0.5)[-1]
    assert t45["recette_mecanique"] == pytest.approx(0.1114, abs=1e-4)
    assert t45["recette_avec_reponse"] == pytest.approx(-0.0058, abs=1e-4)


def test_exonerations_par_tranche():
    # D-501 : Bozio-Wasmer, la fin de la RGDU au-delà de 2 Smic, θ½.
    assert pa.emploi_exonerations(2.0, 0.5)["dln_emploi_total"] == pytest.approx(
        -0.00153, abs=1e-5)


def test_les_payeurs_des_prestations_viennent_des_fiches(session):
    # D-510 : avant, la clé des dépenses (19 % aux APUL) pour les deux prestations, et les
    # parts de D1 pour le point d'indice (APUL −17,39 Md€ et État −26,79 en 2026, figée).
    from impots.jumeau.financement import comptes

    assert comptes.cle_reste(P + "point_indice_10", "depenses") == {
        "etat": 0.765, "asso.maladie": pytest.approx(0.235)}
    assert comptes.cle_reste(P + "garantie_autonomie_jeunes", "depenses") == {"etat": 1.0}
    cle = comptes.cle_reste(P + "indexation_pensions_prestations_10", "depenses")
    assert "apul" not in cle and cle["etat"] == pytest.approx(0.1921, abs=1e-4)
    ms = pa.mesures_seules(session, "melenchon", "figee")
    traj, th = pa.trajectoire(session, ms, cle=P + "programme", theta={
        "financement_a16_part_cnav": 0.5, "financement_compensation": 0.5})
    res = comptes.resume(comptes.decomposer(traj, ms, th))["sous_secteurs"]
    # D-551 : la diffusion recentrée par défaut ; sous l'ancienne forme, −55,81 et 1,48.
    assert res["etat"]["b9"]["ecart"][0] == pytest.approx(-54.92, abs=0.01)
    assert res["apul"]["b9"]["ecart"][0] == pytest.approx(1.545, abs=0.01)
