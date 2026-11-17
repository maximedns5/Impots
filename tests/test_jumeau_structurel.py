"""But 23, la jonction des lots 2 à 4 (D-411) : le modèle structurel complet, et les
quatre décisions du cadre.

Sur des données synthétiques (la population d'entreprises de `tests/fixtures/
firm_cells.json`, les cellules de ménages synthétiques du lot 4, le départ des tests du
lot 2) :

1. le modèle structurel complet se construit sans double compte, et `mesange` y est
   refusé ; les canaux se portent par instrument (D-411 b), et le canal des créations
   tourne à côté de Mésange (D-411 c) ;
2. le cadre ferme le PIB d'un bloc structurel comme la somme de ses emplois, et refuse un
   bloc structurel qui l'écrit (D-411 a) ;
3. les identités tiennent à 1e-9 à θ = 0, ½, 1 et sur un axe de tirages, Δb se décompose
   sans reste, et le point fixe converge ;
4. la demande publique d'une mesure entre dans les emplois, euro pour euro.

La chaîne des études, en mode réduit, reste celle de `test_jumeau.py` et de
`test_rejouer.py`, à 1e-9.
"""

from __future__ import annotations

import collections

import numpy as np
import pytest

from impots.jumeau import canaux, identites, thetas
from impots.jumeau.blocs import BOUCLE_STRUCTURELLE, ordre_structurel
from impots.jumeau.blocs.creations import Creations
from impots.jumeau.blocs.entreprises import mesure_entreprises, population_depuis
from impots.jumeau.blocs.mesange import Mesange
from impots.jumeau.blocs.mesures import Mesures
from impots.jumeau.blocs.tendance import Tendance
from impots.jumeau.champs import EMPLOIS, REGISTRE
from impots.jumeau.comparaison import VARIANTES, mesure, reponses
from impots.jumeau.pas import ITERATIONS_MAX, Entrees, Modele, PasError
from impots.jumeau.trajectoire import calculer, depart_depuis_start
from test_jumeau_entreprises import ANNEES, FIXTURE, PARTS, START
from test_jumeau_menages import CELLULES

POPULATION = population_depuis(FIXTURE)


def _entrees() -> Entrees:
    k = len(ANNEES)
    return Entrees(annees=ANNEES, croissance_reelle=(0.01,) * k, prix=(0.018,) * k,
                   regle_depense="gele_en_volume", croissance_depense=None,
                   taux_reference=(0.02,) * k, taux_marginal=0.03, noms={})


def _depart():
    return depart_depuis_start(START, PARTS)


def _mesures(depart, entrees):
    pib = [Tendance(depart).chemin(entrees, k)[0] for k in range(len(ANNEES))]
    baisse_is = mesure_entreprises("baisse_is", "Baisse de l'IS", {
        a: {"impot_societes": -10.0} for a in ANNEES})
    return [*(mesure(v, pib, ANNEES, CELLULES) for v in
              ("impot_sur_le_revenu", "cotisations_employeurs", "depense_publique")),
            baisse_is]


def _calcul(theta, mesures=None, blocs=None):
    depart, entrees = _depart(), _entrees()
    if blocs is None:
        blocs, boucles = ordre_structurel(depart, POPULATION, CELLULES)
    else:
        boucles = [BOUCLE_STRUCTURELLE]
    mesures = _mesures(depart, entrees) if mesures is None else mesures
    return calculer(depart, entrees=entrees, mesures=mesures, theta=theta, blocs=blocs,
                    boucles=boucles)


def _theta(valeur):
    return dict.fromkeys(thetas.REGISTRE, valeur)


# --------------------------------------------------------------------------- #
# 1. sans double compte, par instrument
# --------------------------------------------------------------------------- #
def test_le_modele_structurel_complet_se_construit_sans_double_compte() -> None:
    depart = _depart()
    blocs, boucles = ordre_structurel(depart, POPULATION, CELLULES)
    modele = Modele(blocs, boucles)
    portes = {c for c, _ in modele.canaux}
    # D-481 (D-566) : trois canaux du registre n'ont pas de bloc, par construction. Les
    # deux comptables (`canaux.COMPTABLES`) sont calculés après la trajectoire
    # (`financement.comptes`, D-487) ; le financement annoncé entre comme des lois
    # hypothétiques (`financement.annonce`, D-482). Avant 2308bbd, le registre n'avait
    # que des canaux portés par un bloc.
    sans_bloc = canaux.COMPTABLES | {"financement_annonce"}
    assert sans_bloc == {"financement_sous_secteurs", "compensation_exonerations",
                         "financement_annonce"}
    assert not portes & sans_bloc
    assert portes == set(canaux.CANAUX) - sans_bloc, \
        "chaque canal du registre, hors les trois sans bloc, est porté une fois"
    assert all(i == canaux.TOUS or c == "investissement_cout_du_capital"
               for c, i in modele.canaux)
    assert "mesange" not in {b.nom for b in blocs}
    with pytest.raises(canaux.DoubleCompte, match=r"canal « \w+ » porté deux fois"):
        Modele([*blocs[:2], Mesange("lue"), *blocs[2:]], boucles)


def test_le_canal_des_creations_tourne_a_cote_de_mesange() -> None:
    """D-411 c : Mésange ne porte pas la démographie des entreprises ; le canal des
    créations lit les cotisations à côté de sa variante cotisations, sans double compte."""
    modele = Modele([Tendance(_depart()), Mesures(), Mesange("lue"), Creations()])
    assert modele.canaux[("creations_entreprises", canaux.TOUS)] == "creations"
    assert modele.canaux[("emploi", "cotisations_employeurs")] == "mesange"
    assert "creations_entreprises" not in canaux.DE_MESANGE
    assert ("emploi", "impot_societes") not in modele.canaux


def test_un_instrument_inconnu_est_refuse() -> None:
    class Bloc:
        nom, lit, ecrit, thetas = "x", (), (), ()
        remplace = ("emploi",)

        @property
        def instruments(self):
            return {"emploi": ("teleportation",)}

    with pytest.raises(canaux.CanalInconnu, match="teleportation"):
        canaux.verifier([Bloc()])


# --------------------------------------------------------------------------- #
# 2. le PIB fermé par le cadre
# --------------------------------------------------------------------------- #
def test_un_bloc_structurel_qui_ecrit_le_pib_est_refuse() -> None:
    class Fautif:
        nom, lit, thetas = "fautif", (), ()
        ecrit = ("c_menages", "pib")
        remplace = ("consommation_menages",)

        def contribue(self, ctx):
            return {}

    with pytest.raises(PasError, match="bloc structurel « fautif » : écrit « pib »"):
        Modele([Tendance(_depart()), Mesures(), Fautif()])


def test_le_pib_d_un_bloc_structurel_est_la_somme_de_ses_emplois() -> None:
    traj = _calcul(_theta(0.5))
    depart = _depart()
    blocs, _ = ordre_structurel(depart, POPULATION, CELLULES)
    structurels = {b.nom for b in blocs if canaux.structurel(b)}
    vus = set()
    for etat in traj.variante:
        pib = etat.de("pib")
        sommes: dict = collections.defaultdict(float)
        for nom in EMPLOIS:
            for (o, m), v in etat.de(nom).items():
                if o in structurels:
                    sommes[(o, m)] = sommes[(o, m)] + REGISTRE[nom].signe * v
        for cle, v in sommes.items():
            assert np.max(np.abs(pib[cle] - v)) <= 1e-12 * etat["pib"][0]
            vus.add(cle[0])
        assert not {o for o, _ in pib} & (structurels - vus)
    assert {"consommation", "commerce", "investissement", "implantation", "productivite",
            "demande_publique"} <= vus


# --------------------------------------------------------------------------- #
# 3. les identités, sur un axe et à trois θ, et le point fixe
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("theta", [0.0, 0.5, 1.0, np.array([0.0, 0.25, 0.5, 0.75, 1.0])])
def test_les_identites_tiennent_et_db_se_decompose(theta) -> None:
    traj = _calcul(_theta(theta))
    n = np.size(theta)
    prec = None
    for etat in traj.variante:
        assert etat.n == n
        residus = identites.verifier(etat, prec)
        assert max(float(np.max(np.abs(r))) for r in residus.values()) < 1e-9
        prec = etat
    parts = traj.decomposition(ANNEES[-1])
    assert np.max(np.abs(sum(parts.values()) - traj.delta_b[-1])) < 1e-12
    # Le sens se lit sur le PIB en volume : depuis la boucle prix-salaires (D-414), le PIB
    # nominal porte l'effet des prix, et une baisse des cotisations, qui baisse les prix,
    # peut baisser le PIB nominal en montant son volume.
    fin = traj.variante[-1]
    for v in ("impot_sur_le_revenu", "cotisations_employeurs", "depense_publique"):
        assert np.all(fin.par_mesure("pib")[v] - fin.par_mesure("effet_prix_pib")[v] > 0.0)
    # Une baisse d'IS à θ = 0 ne fait rien depuis D-427 : l'élasticité des créations et
    # celle de l'investissement au coût du capital y valent 0, comme l'implantation et les
    # fermetures ; ailleurs, son volume monte.
    volume = fin.par_mesure("pib")["baisse_is"] - fin.par_mesure("effet_prix_pib")["baisse_is"]
    nul = np.broadcast_to(np.asarray(theta) == 0.0, np.shape(volume))
    assert np.all(volume[nul] == 0.0) and np.all(volume[~nul] > 0.0)


def test_le_point_fixe_converge() -> None:
    depart = _depart()
    blocs, _ = ordre_structurel(depart, POPULATION, CELLULES)
    commerce = next(b for b in blocs if b.nom == "commerce")
    appels: collections.Counter = collections.Counter()
    contribue = commerce.contribue

    def compte(ctx):
        appels[(ctx.reference is None, ctx.annee)] += 1
        return contribue(ctx)

    commerce.contribue = compte
    _calcul(_theta(0.5), blocs=blocs)
    assert set(appels) == {(r, a) for r in (True, False) for a in ANNEES}
    assert all(2 <= c < ITERATIONS_MAX for c in appels.values())
    assert max(appels.values()) > 2, "la variante itère : la boucle est simultanée"


# --------------------------------------------------------------------------- #
# 4. la demande publique, et les variantes de la comparaison
# --------------------------------------------------------------------------- #
def test_la_demande_publique_entre_dans_les_emplois() -> None:
    depart, entrees = _depart(), _entrees()
    pib = [Tendance(depart).chemin(entrees, k)[0] for k in range(len(ANNEES))]
    m = mesure("investissement_public", pib, ANNEES, CELLULES)
    traj = _calcul(_theta(0.5), mesures=[m])
    for k, etat in enumerate(traj.variante):
        assert etat.de("fbcf_apu")[("demande_publique", m.identifiant)][0] == \
            pytest.approx(0.01 * pib[k], rel=1e-12)
    assert np.all(traj.ecart_pib[:, 0] > 0.0)


def test_les_variantes_de_la_comparaison_ont_le_sens_de_mesange() -> None:
    """Le sens seulement : les niveaux sont dits dans D-411, à côté de Mésange."""
    depart, entrees = _depart(), _entrees()
    pib = [Tendance(depart).chemin(entrees, k)[0] for k in range(len(ANNEES))]
    for v in VARIANTES:
        r = reponses(_calcul(_theta(0.5), mesures=[mesure(v, pib, ANNEES, CELLULES)]))
        assert np.all(r["pib"] > 0.0), v
        assert np.all(r["solde"] < 0.0), v
