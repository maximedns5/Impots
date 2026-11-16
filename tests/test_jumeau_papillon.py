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
    assert emploi == pytest.approx(33.7, abs=0.05)
    assert dette == pytest.approx(2.042, abs=5e-4)


def test_melenchon_tourne_en_structurel_par_les_mesures_seules(session):
    # D-502 : refusé avant (D-489) ; la somme des coûts tient au bit.
    assert all(v == 0.0 for v in pa.verifier_somme(
        session, "melenchon", "figee", "parts_premiere_annee").values())
    ms = pa.mesures_seules(session, "melenchon", "figee")
    assert ms[-1].impulsions[2026]["cotisations_employeurs"] == pytest.approx(1.333, abs=1e-3)
    traj, dette, emploi = _dette_emploi(session, ms, P + "programme")
    assert dette == pytest.approx(12.306, abs=5e-4)
    assert emploi == pytest.approx(186.1, abs=0.05)
    assert max(pa.identites(traj, ms).values()) < 1e-12
    c = pa.cascade_simple(traj)
    assert abs(c["residu"]) < 1e-9
    assert c["fleches"]["statique"] == pytest.approx(23.725, abs=5e-4)
    assert pa.prime_de_risque(traj, session._modele("structurel", ms[0], P + "programme")[1],
                              0.5)["dette_pts"][-1] == pytest.approx(1.555, abs=5e-4)


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
    assert res["etat"]["b9"]["ecart"][0] == pytest.approx(-55.81, abs=0.01)
    assert res["apul"]["b9"]["ecart"][0] == pytest.approx(1.48, abs=0.01)
