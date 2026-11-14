"""But 23, le bloc d'emploi public (D-418) : les emplois que font les rémunérations des APU
d'une mesure, leur revenu aux ménages et leurs prélèvements.

Sur les données synthétiques des tests du modèle structurel (`test_jumeau_structurel`) :

1. le bloc, à la main : ΔE_pub = s ΔD1 / (r W), l'emploi total et salarié qui montent et
   le chômage qui baisse d'autant, la population active intacte, la part des emplois et
   des traitements qui somme ΔD1, les prélèvements aux taux des cellules ;
2. le sens : plus de rémunérations en postes, plus d'emploi et moins de chômage, et θ qui
   borne ; une mesure qui porte sa part ne lit pas θ (des postes, un point d'indice) ;
3. pas de double compte : le canal porté une fois et refusé à côté de `mesange` ; le bloc
   n'écrit ni le PIB ni les rémunérations, que `demande_publique` porte ; l'activité que
   lisent les blocs marchands retranche la valeur ajoutée non marchande, l'emploi marchand
   l'emploi public ;
4. les identités à 1e-9 à θ = 0, ½, 1 et sur un axe de cinq tirages, Δb décomposé à 1e-12.

Le mode réduit (`test_jumeau`, `test_rejouer`) et le déterminisme
(`test_jumeau_determinisme`, dont les mesures portent la dépense publique) tiennent à côté.
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.jumeau import canaux, identites, thetas
from impots.jumeau.blocs import ordre_structurel
from impots.jumeau.blocs.menages import (
    EmploiPublic,
    charger,
    ecarts,
    reference,
    remunerations_publiques_cellules,
    structure,
)
from impots.jumeau.blocs.mesange import Mesange
from impots.jumeau.blocs.tendance import Tendance
from impots.jumeau.comparaison import mesure
from impots.jumeau.mesures import Mesure, MesureError
from impots.jumeau.pas import Modele
from test_jumeau_menages import CELLULES
from test_jumeau_structurel import ANNEES, POPULATION, _calcul, _depart, _entrees

PARAMS = charger()
PART = thetas.EMPLOI_PUBLIC_PART
D1 = 6.0
"""Md€ de rémunérations des APU par an, la loi hypothétique des tests."""


def _theta(valeur, part=None):
    theta = dict.fromkeys(thetas.REGISTRE, valeur)
    if part is not None:
        theta[PART] = part
    return theta


def _remunerations(identifiant="postes", part=None):
    return Mesure.hypothese(identifiant, "Rémunérations publiques",
                            chocs={a: {"apu_d_d1": D1} for a in ANNEES},
                            part_emplois_publics=None if part is None
                            else dict.fromkeys(ANNEES, part))


def _pib():
    depart, entrees = _depart(), _entrees()
    return [Tendance(depart).chemin(entrees, k)[0] for k in range(len(ANNEES))]


def _du_bloc(etat, champ, m):
    return etat.de(champ).get(("emploi_public", m))


# --------------------------------------------------------------------------- #
# 1. le bloc, à la main
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("part", [0.0, 0.5, 1.0])
def test_le_bloc_fait_les_emplois_au_salaire_public(part) -> None:
    m = _remunerations()
    traj = _calcul(_theta(0.5, part), mesures=[m])
    st = structure(CELLULES, PARAMS.pib_cellules)
    depart = _depart()
    for k, etat in enumerate(traj.variante):
        ref = reference(PARAMS, depart, traj.reference[k]["pib"])
        d_pub = part * D1 * 1e9 / (PARAMS.remuneration_publique_relative * ref.salaire) / 1e3
        assert _du_bloc(etat, "emploi_public", "postes") == pytest.approx(d_pub, rel=1e-12)
        for champ, signe in (("emploi_salarie", 1.0), ("emploi_total", 1.0),
                             ("chomage", -1.0)):
            assert _du_bloc(etat, champ, "postes") == pytest.approx(signe * d_pub,
                                                                   rel=1e-12, abs=1e-12)
        assert ("emploi_public", "postes") not in etat.de("population_active")
        emplois = _du_bloc(etat, "remunerations_publiques_emplois", "postes")
        traitements = _du_bloc(etat, "remunerations_publiques_traitements", "postes")
        assert emplois + traitements == pytest.approx(D1, rel=1e-12)
        assert emplois == pytest.approx(part * D1, rel=1e-12, abs=1e-12)
        d1_c = remunerations_publiques_cellules(st, emplois, traitements)
        assert d1_c.sum() == pytest.approx(D1, rel=1e-12)
        assert _du_bloc(etat, "apu_r_d61", "postes") == pytest.approx(st.taux_d61 @ d1_c)
        assert _du_bloc(etat, "apu_r_d5", "postes") == pytest.approx(st.taux_d5 @ d1_c)
        # La référence : l'emploi non marchand du jumeau, (1 − π) E_sal.
        assert etat.de("emploi_public")[("emploi_public", "")] == pytest.approx(
            (1.0 - PARAMS.part_marchande) * ref.emploi_salarie)


def test_le_salaire_public_est_celui_des_comptes() -> None:
    """r = W_pub / W de 2024 : D11 par tête des branches OZ, PZ, QA, QB (t. 6.205, 6.210)
    au rapport D1 / D11 des APU (t. 7.301), sur D1 / E_sal (t. 1.105, 6.210)."""
    w_pub = (295.056e9 / 8312.3e3) * (363.038 / 245.586)
    w = 1505.528e9 / 27181.7e3
    assert PARAMS.remuneration_publique_relative == pytest.approx(w_pub / w, abs=5e-6)
    assert PARAMS.part_emplois_publics == {"low": 0.0, "central": 0.5, "high": 1.0,
                                           "un": "high"}


# --------------------------------------------------------------------------- #
# 2. le sens, θ qui borne, la part portée par la mesure
# --------------------------------------------------------------------------- #
def test_plus_de_postes_plus_d_emploi_moins_de_chomage() -> None:
    """Un axe de trois tirages du seul θ de la part : 0, ½, 1. L'emploi total et salarié
    montent, le chômage et son taux baissent, à chaque année, et ½ est entre les deux."""
    m = _remunerations()
    theta = _theta(0.5, np.array([0.0, 0.5, 1.0]))
    traj = _calcul(theta, mesures=[m])
    for champ, signe in (("emploi_total", 1.0), ("emploi_salarie", 1.0),
                         ("chomage", -1.0)):
        ecart = signe * traj.difference(champ)
        assert np.all(np.diff(ecart, axis=1) > 0.0), champ
    u_r, u_v = traj.niveaux("chomage")
    pa_r, pa_v = traj.niveaux("population_active")
    taux = u_v / pa_v - u_r / pa_r
    assert np.all(np.diff(taux, axis=1) < 0.0)
    assert np.all(traj.difference("emploi_public")[:, 0] == 0.0)
    assert np.all(traj.difference("emploi_public")[:, 2] > 0.0)


def test_une_mesure_qui_porte_sa_part_ne_lit_pas_theta() -> None:
    """Des créations de postes (part 1) et un point d'indice (part 0) : θ ne joue pas, et
    la part portée donne ce que θ donnerait à la même valeur."""
    postes, indice = _remunerations("postes", 1.0), _remunerations("indice", 0.0)
    for valeur in (0.0, 1.0):
        traj = _calcul(_theta(0.5, valeur), mesures=[postes, indice])
        for etat in traj.variante:
            assert _du_bloc(etat, "emploi_public", "postes") > 0.0
            assert _du_bloc(etat, "emploi_public", "indice") == 0.0
            assert _du_bloc(etat, "remunerations_publiques_traitements", "indice") == D1
    seule = _calcul(_theta(0.5, 1.0), mesures=[_remunerations("postes")])
    portee = _calcul(_theta(0.5, 0.0), mesures=[postes])
    assert np.array_equal(seule.difference("emploi_total"),
                          portee.difference("emploi_total"))


def test_une_part_hors_de_zero_un_ou_sans_remunerations_est_refusee() -> None:
    with pytest.raises(MesureError, match=r"hors de \[0 ; 1\]"):
        _remunerations(part=1.5)
    with pytest.raises(MesureError, match="sans rémunérations des APU"):
        Mesure.hypothese("x", "x", chocs={ANNEES[0]: {"apu_d_p2": 1.0}},
                         part_emplois_publics={ANNEES[0]: 1.0})


# --------------------------------------------------------------------------- #
# 3. sans double compte
# --------------------------------------------------------------------------- #
def test_le_canal_est_porte_une_fois_et_refuse_a_cote_de_mesange() -> None:
    blocs, boucles = ordre_structurel(_depart(), POPULATION, CELLULES)
    modele = Modele(blocs, boucles)
    assert modele.canaux[("emploi_public", canaux.TOUS)] == "emploi_public"
    assert "emploi_public" in canaux.DE_MESANGE
    with pytest.raises(canaux.DoubleCompte, match="« emploi_public »"):
        canaux.verifier([Mesange("lue"), EmploiPublic(CELLULES, PARAMS)])


def test_ni_pib_ni_remunerations_deux_fois() -> None:
    """Le bloc n'écrit ni le PIB ni les rémunérations : ΔD1 y est une fois, par
    `demande_publique`, qui l'écrit aussi en valeur ajoutée non marchande."""
    m = _remunerations()
    traj = _calcul(_theta(0.5), mesures=[m])
    for etat in traj.variante:
        assert not [c for c in etat.de("pib") if c[0] == "emploi_public"]
        assert {c for c in etat.de("remunerations") if c[1] == "postes"} <= {
            ("demande_publique", "postes"), ("salaires", "postes")}
        assert etat.de("remunerations")[("demande_publique", "postes")] == D1
        assert etat.de("va_non_marchande")[("demande_publique", "postes")] == D1


def test_l_activite_marchande_ne_lit_pas_la_valeur_ajoutee_des_apu() -> None:
    """ŷ = (ΔPIB − ΔPIB^prix − ΔVA_nm) / Y et ê = (ΔE_sal − ΔE_pub) / E_sm : sans quoi un
    emploi que ΔD1 paie serait aussi un emploi marchand que la production appelle."""
    m = mesure("depense_publique", _pib(), ANNEES, CELLULES)
    traj = _calcul(_theta(0.5), mesures=[m])
    depart = _depart()
    for k, etat in enumerate(traj.variante):
        ref = reference(PARAMS, depart, traj.reference[k]["pib"])
        ec = ecarts(etat, m.identifiant, ref, PARAMS)
        de = {c: etat.par_mesure(c)[m.identifiant] for c in
              ("pib", "effet_prix_pib", "va_non_marchande", "emploi_salarie",
               "emploi_public")}
        assert de["va_non_marchande"] == pytest.approx(
            m.chocs[ANNEES[k]]["apu_d_d1"], rel=1e-12)
        assert ec.y == pytest.approx(
            (de["pib"] - de["effet_prix_pib"] - de["va_non_marchande"]) / ref.pib, rel=1e-12)
        assert ec.e == pytest.approx(
            (de["emploi_salarie"] - de["emploi_public"]) / ref.emploi_marchand, rel=1e-12)
        # L'emploi salarié marchand est celui que le bloc `emploi` écrit.
        assert de["emploi_salarie"] - de["emploi_public"] == pytest.approx(
            etat.de("emploi_salarie")[("emploi", m.identifiant)], rel=1e-12)


# --------------------------------------------------------------------------- #
# 4. les identités
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theta", [0.0, 0.5, 1.0, np.array([0.0, 0.25, 0.5, 0.75, 1.0])])
def test_les_identites_tiennent_avec_l_emploi_public(theta) -> None:
    mesures = [mesure("depense_publique", _pib(), ANNEES, CELLULES),
               _remunerations("postes", 1.0), _remunerations("indice", 0.0),
               _remunerations("convention")]
    traj = _calcul(_theta(theta), mesures=mesures)
    prec = None
    for etat in traj.variante:
        assert etat.n == np.size(theta)
        residus = identites.verifier(etat, prec)
        assert max(float(np.max(np.abs(r))) for r in residus.values()) < 1e-9
        prec = etat
    parts = traj.decomposition(ANNEES[-1])
    assert np.max(np.abs(sum(parts.values()) - traj.delta_b[-1])) < 1e-12
