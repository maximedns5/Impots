"""But 23, lot 1 — le cadre du jumeau (`impots.jumeau`, docs/jumeau/CADRE.md §10).

Trois preuves, sur les passes synthétiques de `test_rejouer` et de `test_creations_canal` :

1. les identités du §6 tiennent à chaque pas sous des blocs et des mesures synthétiques,
   sur plusieurs θ et un axe de tirages ; une identité violée, un champ absent, un bloc
   mal déclaré et une boucle qui diverge sont refusés en les nommant ;
2. la chaîne est retrouvée : Δb du jumeau est `rejouer.chemin` à 1e-9, sous les trois
   persistances, plusieurs θ et les deux vues, puis avec le canal des créations ;
3. la part de chaque bloc et de chaque mesure dans Δb₂₀₃₅ se somme à Δb₂₀₃₅.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from impots.dette.path import SHIPPED
from impots.jumeau import identites
from impots.jumeau.blocs import ordre_lot1
from impots.jumeau.blocs.creations import Creations
from impots.jumeau.blocs.mesange import Mesange, MesangeError
from impots.jumeau.blocs.mesures import Mesures
from impots.jumeau.blocs.tendance import Tendance
from impots.jumeau.etat import ChampAbsent, Etat
from impots.jumeau.mesures import Mesure, MesureError
from impots.jumeau.pas import Entrees, Modele, NonConvergence, PasError
from impots.jumeau.thetas import ThetaError
from impots.jumeau.trajectoire import calculer, depart_depuis_start
from impots.predictif import annuel, creations, rejouer, retroaction
from impots.predictif.theta import CREATIONS_ROW, MACRO_ROW, Theta
from macro_cases import synthetic_macro_store
from test_creations_canal import CUT
from test_creations_canal import _build as _build_canal
from test_rejouer import FROZEN, GROWTH, HELD, IR, START, THETAS, YEARS, _build, _price

#: Les parts synthétiques de chaque groupe à l'année de départ (sommes à un).
PARTS = {"c_menages": 0.52, "c_isbl": 0.02, "c_apu": 0.24, "fbcf_snf": 0.13,
         "fbcf_apu": 0.04, "fbcf_menages": 0.05, "var_stocks": 0.01, "exportations": 0.33,
         "importations": 0.34,
         "remunerations": 0.51, "ebe_revenu_mixte": 0.35, "impots_production": 0.16,
         "subventions": 0.02,
         "apu_r_d2": 0.30, "apu_r_d5": 0.25, "apu_r_d61": 0.33, "apu_r_p11": 0.07,
         "apu_r_d7": 0.05,
         "apu_d_p2": 0.10, "apu_d_d1": 0.22, "apu_d_d62": 0.38, "apu_d_d632": 0.12,
         "apu_d_d3": 0.06, "apu_d_p51g": 0.08, "apu_d_d7": 0.04}


def _payload(rapport) -> dict:
    return json.loads(json.dumps(rapport.payload()))


def _jumeau(payload, theta, *, vue, persistance, mesures=None, creations_=False,
            boucle=None):
    rejeu = payload["rejeu"]
    rows = payload["years"]
    horizon = int(payload["horizon"]) if payload.get("carry") else len(rows)
    premiere = int(rows[0]["year"])
    annees = list(range(premiere, premiere + horizon))
    depart = depart_depuis_start(rejeu["start"], PARTS)
    entrees = Entrees.depuis_rejeu(rejeu, annees)
    if mesures is None:
        mesures = [Mesure.depuis_rapport(payload, vue=vue, identifiant="baisse",
                                         libelle="Baisse", auteur="test",
                                         rapport="synthétique", commit="test")]
    blocs = ordre_lot1(depart, persistance=persistance,
                       boucle=rejeu["looped"] if boucle is None else boucle,
                       creations=creations_)
    return calculer(depart, entrees=entrees, mesures=mesures, theta=theta, blocs=blocs)


def _ecart(a, b) -> float:
    return float(np.max(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float))))


# --------------------------------------------------------------------------- #
# 2. la chaîne retrouvée
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("rows", THETAS)
@pytest.mark.parametrize("persistance", retroaction.PERSISTENCE_LABELS)
def test_le_jumeau_redonne_rejouer_a_1e_9(rows, persistance) -> None:
    """Δb, l'écart de PIB et le ratio de référence, chaque année, les deux vues."""
    payload = _payload(_build(Theta(rows=rows, common=0.5), persistence=persistance))
    for vue in rejouer.VIEWS:
        attendu = rejouer.at_theta(payload, rows, view=vue, persistence=persistance)
        jumeau = _jumeau(payload, rows, vue=vue, persistance=persistance)
        assert _ecart(jumeau.delta_b[:, 0], attendu.delta) < 1e-9
        assert _ecart(jumeau.ecart_pib[:, 0], attendu.gdp_gap) < 1e-9
        assert _ecart(jumeau.niveaux("ratio_dette")[0][:, 0], attendu.reference) < 1e-9


def test_un_axe_de_tirages_redonne_chaque_theta() -> None:
    """θ en tableau : chaque tirage est le jumeau, et `rejouer`, à son θ."""
    payload = _payload(_build(Theta(common=0.5), persistence="lue"))
    axe = {cle: np.array([r[cle] for r in THETAS]) for cle in THETAS[0]}
    jumeau = _jumeau(payload, axe, vue="vieillie", persistance="lue")
    assert jumeau.delta_b.shape == (len(YEARS), len(THETAS))
    for i, rows in enumerate(THETAS):
        attendu = rejouer.at_theta(payload, rows, view="vieillie", persistence="lue")
        assert _ecart(jumeau.delta_b[:, i], attendu.delta) < 1e-9
    valeurs = {cle: rejouer.value_at(row, axe[cle])
               for cle, row in payload["rejeu"]["lignes"].items()}
    vectorise = rejouer.chemin(payload, view="vieillie", values=valeurs,
                               z=2.0 * axe[MACRO_ROW] - 1.0, persistence="lue")
    assert _ecart(jumeau.delta_b, np.array(vectorise.delta)) < 1e-9


def test_sans_la_boucle_et_a_un_taux_marginal_de_marche() -> None:
    """Le comportement seul ; la boucle absente sous une autre règle de dépense ; la
    dette ajoutée chargée à 3,5 % quand la référence l'est à son taux implicite (le
    taux marginal du rapport remplacé dans une copie : le scénario « marché » lit les
    encours de l'AFT, que ce test ne charge pas)."""
    rows = {"eti_all": 0.3, "eti_top_decile": 0.8, MACRO_ROW: 0.6}
    for macro, spending, lue in ((False, FROZEN, None),
                                 (True, SHIPPED["part_pib_constante"], None),
                                 (True, FROZEN, "lue")):
        payload = _payload(_build(Theta(rows=rows, common=0.5), macro=macro,
                                  spending=spending, persistence=lue))
        assert payload["rejeu"]["looped"] == (lue is not None)
        payload["rejeu"]["cadre"]["taux"]["marginal"] = 0.035
        attendu = rejouer.at_theta(payload, rows, view="vieillie", persistence=lue)
        jumeau = _jumeau(payload, rows, vue="vieillie", persistance=lue)
        assert _ecart(jumeau.delta_b[:, 0], attendu.delta) < 1e-9


def test_la_boucle_refuse_une_autre_regle_de_depense() -> None:
    payload = _payload(_build(Theta(common=0.5), spending=SHIPPED["part_pib_constante"]))
    with pytest.raises(MesangeError, match="part_pib_constante"):
        _jumeau(payload, THETAS[0], vue="vieillie", persistance="lue", boucle=True)


@pytest.mark.parametrize("rows", THETAS)
@pytest.mark.parametrize("persistance", retroaction.PERSISTENCE_LABELS)
def test_la_premiere_annee_reportee_est_rejouer(rows, persistance) -> None:
    """Une première année tenue en part du PIB (D-343), comme les plages."""
    payload = json.loads(json.dumps(annuel.carried_payload(
        START, _price(2026, "vieillie"), IR, spending=FROZEN, growth=GROWTH, rate=HELD,
        theta=Theta(rows=rows, common=0.5), horizon=len(YEARS),
        macro_store=synthetic_macro_store())))
    attendu = rejouer.at_theta(payload, rows, view="vieillie", persistence=persistance)
    jumeau = _jumeau(payload, rows, vue="vieillie", persistance=persistance)
    assert jumeau.annees == tuple(YEARS)
    assert _ecart(jumeau.delta_b[:, 0], attendu.delta) < 1e-9


@pytest.mark.parametrize("c", [0.0, 0.3, 0.5, 1.0])
@pytest.mark.parametrize("persistance", retroaction.PERSISTENCE_LABELS)
def test_avec_le_canal_des_creations(c, persistance) -> None:
    """Le canal du but 22 en bloc : Δb avec et sans lui, à plusieurs θ du canal."""
    payload = _payload(_build_canal(Theta(common=0.5), CUT, channel=True,
                                    persistence=persistance))
    rows = {"eti_all": 0.4, "eti_top_decile": 0.6, MACRO_ROW: 0.7, CREATIONS_ROW: c}
    for vue in rejouer.VIEWS:
        avec = rejouer.at_theta(payload, rows, view=vue, persistence=persistance)
        sans = rejouer.at_theta(payload, rows, view=vue, persistence=persistance,
                                creations=False)
        jumeau = _jumeau(payload, rows, vue=vue, persistance=persistance, creations_=True)
        assert _ecart(jumeau.delta_b[:, 0], avec.delta) < 1e-9
        assert _ecart(jumeau.ecart_pib[:, 0], avec.gdp_gap) < 1e-9
        hors = _jumeau(payload, rows, vue=vue, persistance=persistance, creations_=False)
        assert _ecart(hors.delta_b[:, 0], sans.delta) < 1e-9


def test_un_theta_manquant_est_refuse() -> None:
    payload = _payload(_build(Theta(common=0.5), persistence="lue"))
    with pytest.raises(ThetaError, match="multiplicateur_macro"):
        _jumeau(payload, {"eti_all": 0.5, "eti_top_decile": 0.5}, vue="vieillie",
                persistance="lue")
    with pytest.raises(ThetaError, match="eti_top_decile"):
        _jumeau(payload, {"eti_all": 0.5, MACRO_ROW: 0.5}, vue="vieillie",
                persistance="lue")


# --------------------------------------------------------------------------- #
# 3. le nombre décomposé
# --------------------------------------------------------------------------- #
def _trois_mesures(payload_canal):
    """Deux mesures de rapport (l'une avec ses prélèvements) et une loi hypothétique."""
    tables = payload_canal["rejeu"]["macro"]
    hausse = Mesure.hypothese(
        "hausse_d61", "Hausse des cotisations", auteur="test",
        chocs={a: {"apu_r_d61": -4.0, "apu_d_d62": 1.5} for a in YEARS},
        impulsions={a: {"csg": -3.0} for a in YEARS[2:]},
        prelevements={a: 2.0 for a in YEARS[1:]}, macro=tables,
        creations=creations.instantane(creations.charger()))
    return [
        Mesure.depuis_rapport(payload_canal, vue="vieillie", identifiant="canal",
                              libelle="Baisse de l'IS", auteur="test", rapport="synth",
                              commit="test"),
        Mesure.depuis_rapport(_payload(_build(Theta(common=0.5), persistence="lue")),
                              vue="figee", identifiant="ir", libelle="Baisse de l'IR",
                              auteur="test", rapport="synth", commit="test"),
        hausse]


def test_la_decomposition_par_bloc_et_par_mesure_se_somme_a_delta_b() -> None:
    payload = _payload(_build_canal(Theta(common=0.5), CUT, channel=True))
    mesures = _trois_mesures(payload)
    axe = {"eti_all": np.array([0.1, 0.5, 0.9]), "eti_top_decile": np.array([0.2, 0.5, 1.0]),
           MACRO_ROW: np.array([0.0, 0.5, 1.0]), CREATIONS_ROW: np.array([1.0, 0.5, 0.0])}
    jumeau = _jumeau(payload, axe, vue="vieillie", persistance="lue", mesures=mesures,
                     creations_=True)
    for annee in (YEARS[0], YEARS[-1]):
        parts = jumeau.decomposition(annee)
        total = sum(parts.values())
        assert _ecart(total, jumeau.delta_b[jumeau.annees.index(annee)]) < 1e-12
    parts = jumeau.decomposition(2035)
    origines = {c for c, v in parts.items() if np.any(np.abs(v) > 1e-15)}
    assert origines == {(b, m) for m in ("canal", "ir", "hausse_d61")
                        for b in ("mesures", "mesange", "creations")} - {("creations", "ir")}
    assert jumeau.avertissements and "hausse_d61" in jumeau.avertissements[0]


def test_une_mesure_seule_porte_ses_interets() -> None:
    """La part d'une mesure dans la décomposition est, au premier ordre, Δb de la mesure
    seule : sa dette ajoutée porte ses propres intérêts au taux marginal."""
    payload = _payload(_build_canal(Theta(common=0.5), CUT, channel=True))
    mesures = _trois_mesures(payload)
    rows = {"eti_all": 0.5, "eti_top_decile": 0.5, MACRO_ROW: 0.5, CREATIONS_ROW: 0.5}
    ensemble = _jumeau(payload, rows, vue="vieillie", persistance="lue", mesures=mesures,
                       creations_=True)
    seule = _jumeau(payload, rows, vue="vieillie", persistance="lue", mesures=mesures[2:],
                    creations_=True)
    parts = ensemble.decomposition(2035)
    dette = sum(v for (o, m), v in parts.items() if m == "hausse_d61")
    # Le seul terme qui ne se sépare pas : le PIB des autres mesures au dénominateur.
    assert dette[0] == pytest.approx(seule.delta_b[-1, 0], rel=0.02)


# --------------------------------------------------------------------------- #
# 1. les identités, sous des blocs synthétiques
# --------------------------------------------------------------------------- #
class Demande:
    """Une boucle synthétique : la consommation répond au PIB que la production en
    tire, c = a (Y − Y_autres) + G, G porté par la mesure « relance »."""

    nom, lit, ecrit, thetas = "demande", ("pib",), ("c_menages",), ("alpha",)

    def __init__(self, g: float) -> None:
        self.g = g

    def contribue(self, ctx):
        alpha = 0.5 * ctx.theta["alpha"] if np.ndim(ctx.theta["alpha"]) else 0.5 * float(
            ctx.theta["alpha"])
        if not any(m.identifiant == "relance" for m in ctx.mesures):
            return {}
        autres = sum(v for (o, _), v in ctx.courant.de("pib").items() if o != "production")
        induit = ctx.lire("pib") - autres
        return {"c_menages": {"relance": alpha * induit + self.g}}


class Production:
    nom, lit = "production", ("c_menages",)
    ecrit, thetas = ("pib", "revenus_non_ventiles"), ()

    def contribue(self, ctx):
        demande = ctx.courant.de("c_menages").get(("demande", "relance"))
        if demande is None:
            return {}
        return {"pib": {"relance": demande}, "revenus_non_ventiles": {"relance": demande}}


class Divergente(Demande):
    nom = "demande"

    def contribue(self, ctx):
        out = super().contribue(ctx)
        if out:
            out["c_menages"]["relance"] = 3.0 * out["c_menages"]["relance"]
        return out


class PibSeul:
    """Un bloc fautif : du PIB sans emploi ni revenu."""

    nom, lit, ecrit, thetas = "fautif", (), ("pib",), ()

    def contribue(self, ctx):
        return {"pib": {"": 1.0}}


def _synthetique(blocs, mesures, theta, boucles=()):
    payload = _payload(_build(Theta(common=0.5), persistence="lue"))
    rejeu = payload["rejeu"]
    depart = depart_depuis_start(rejeu["start"], PARTS)
    entrees = Entrees.depuis_rejeu(rejeu, YEARS)
    return calculer(depart, entrees=entrees, mesures=mesures, theta=theta,
                    blocs=[Tendance(depart), Mesures(), *blocs], boucles=boucles), payload


def _relance(tables):
    return Mesure.hypothese("relance", "Relance", chocs={a: {"apu_d_p2": 5.0} for a in YEARS},
                            impulsions={a: {"impot_sur_le_revenu": 6.0} for a in YEARS},
                            macro=tables)


@pytest.mark.parametrize("alpha", [0.0, 0.6, np.array([0.1, 0.5, 0.95, 0.3])])
def test_les_identites_tiennent_a_chaque_pas_sous_une_boucle(alpha) -> None:
    """Les blocs du lot 1 et une boucle demande ↔ production, résolue par point fixe :
    chaque pas vérifie le §6 (il refuserait sinon) ; on relit les résidus, et le point
    fixe est G / (1 − a/2)."""
    payload = _payload(_build(Theta(common=0.5), persistence="lue"))
    theta = {"alpha": alpha, MACRO_ROW: np.full(np.size(alpha), 0.4) if np.ndim(alpha)
             else 0.4, "eti_all": 0.5, "eti_top_decile": 0.5}
    mesures = [_relance(payload["rejeu"]["macro"]),
               Mesure.depuis_rapport(payload, vue="vieillie", identifiant="ir",
                                     libelle="IR", auteur="t", rapport="s", commit="t")]
    jumeau, _ = _synthetique([Mesange("lue"), Demande(10.0), Production()], mesures,
                             theta, boucles=[("demande", "production")])
    prec = None
    for etat in jumeau.variante:
        residus = identites.verifier(etat, prec)
        assert max(float(np.max(np.abs(r))) for r in residus.values()) < 1e-9
        prec = etat
    induit = jumeau.variante[-1].de("pib")[("production", "relance")]
    assert _ecart(induit, 10.0 / (1.0 - 0.5 * np.asarray(alpha))) < 1e-8


def test_une_boucle_qui_diverge_est_refusee_en_nommant_bloc_et_champ() -> None:
    payload = _payload(_build(Theta(common=0.5), persistence="lue"))
    with pytest.raises(NonConvergence, match=r"bloc « (demande|production) », champ"):
        _synthetique([Divergente(10.0), Production()], [_relance(payload["rejeu"]["macro"])],
                     {"alpha": 1.0}, boucles=[("demande", "production")])


def test_une_identite_violee_arrete_le_pas() -> None:
    with pytest.raises(identites.IdentiteViolee, match="emplois"):
        _synthetique([PibSeul()], [], {})


def test_une_identite_qui_lit_un_absent_refuse() -> None:
    etat = Etat(2026, 1)
    etat.ecrire("pib", ("x", ""), 100.0)
    with pytest.raises(identites.IdentiteIncalculable, match="c_menages"):
        identites.verifier(etat, identites=("emplois",))
    with pytest.raises(ChampAbsent, match="dette"):
        etat["dette"]


def test_un_modele_mal_declare_est_refuse_a_la_construction() -> None:
    payload = _payload(_build(Theta(common=0.5), persistence="lue"))
    depart = depart_depuis_start(payload["rejeu"]["start"], PARTS)
    with pytest.raises(PasError, match=r"mesange.*impulsion_"):
        Modele([Tendance(depart), Mesange("lue")])
    with pytest.raises(PasError, match=r"demande.*pib"):
        Modele([Demande(1.0), Tendance(depart)])

    class Chomage:
        nom, lit, ecrit, thetas = "chomage", ("chomage",), ("c_menages",), ()

    with pytest.raises(PasError, match="lit « chomage »"):
        Modele([Tendance(depart), Chomage()])

    class Ferme:
        nom, lit, ecrit, thetas = "ferme", (), ("dette",), ()

    with pytest.raises(PasError, match="cadre seul"):
        Modele([Tendance(depart), Ferme()])
    assert Modele([Tendance(depart), Mesures(), Mesange("lue"), Creations()]).groupes


def test_une_mesure_de_rapport_porte_son_rapport_et_son_commit() -> None:
    payload = _payload(_build(Theta(common=0.5), persistence="lue"))
    with pytest.raises(MesureError, match="commit"):
        Mesure.depuis_rapport(payload, vue="vieillie", identifiant="x", libelle="x",
                              auteur="x", rapport="r")
    with pytest.raises(MesureError, match="inconnues"):
        Mesure.hypothese("x", "x", chocs={2026: {"tva": 1.0}})
