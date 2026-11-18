"""Le moral des gens : la satisfaction dans la vie et les WELLBY (but 29, volet `bienetre`,
D-595 à D-599).

Ce que la trajectoire fait aux ménages, traduit en satisfaction dans la vie (de 0 à 10,
la question de SRCV) et en WELLBY : un point de satisfaction pour une personne pendant un
an (le Green Book britannique). Quatre canaux, chacun avec un coefficient publié et sa
bande (`jumeau/parametres/moral.yaml`, document, page, valeur) :

    revenu         ΔS_d,t = β Δln y_d,t       le revenu disponible réel du décile d :
                   Δln y = ln(RD_v / RD_r) − ln(1 + p̂c_v − p̂c_r), les prix de la
                   consommation du jumeau (D-414) ; β le coefficient du log du revenu
    chômage propre ΔW_t = −δ ΔU_t             chaque chômeur de plus perd δ point par an,
                   au-delà de sa perte de revenu, qui est déjà dans RD ; réparti entre
                   déciles au prorata des chômeurs des cellules (comme `blocs.menages`)
    autour de soi  ΔS_t = −ε Δu_t             chaque adulte, quand le taux de chômage u
                   monte d'un point (la peur du chômage, l'insécurité de l'emploi)
    inflation      ΔS_t = −φ π̄_t             chaque adulte, π̄ l'écart d'inflation de la
                   consommation (points), en moyenne mobile sur trois ans comme DMO

ε et φ sont estimés par Di Tella, MacCulloch et Oswald (DMO) sur une échelle de 1 à 4 ;
ils sont portés sur 0-10 par l'ancrage sur le chômage propre de la même étude :
x = (c / 100) δ / 0,33, c le coefficient du taux (en fraction), 0,33 celui d'un chômeur.
L'insécurité de l'emploi n'est pas un canal de plus : elle passe par ε (Helliwell et
Huang 2014), et la compter à part la compterait deux fois.

LES ADULTES. La satisfaction se mesure à partir de 16 ans ; les cellules portent les
personnes, enfants compris : A_d = a × personnes_d, a la part des 16 ans ou plus (Eurostat),
uniforme entre déciles. WELLBY_t = Σ_d A_d ΔS_d,t (revenu) − δ ΔU_t − (ε Δu_t + φ π̄_t) A.

LA BANDE. Chaque canal est linéaire en son coefficient : sa bande est le canal aux deux
bornes du coefficient ; la bande du total somme les bornes de même sens (l'enveloppe, pas
un intervalle de confiance). L'équivalent monétaire multiplie par la valeur du WELLBY du
Green Book (13 000 £ de 2019, 10 000 à 16 000), une convention, en euros de 2019 au cours
moyen de la BCE.

LE STATUT : « sourcé, non jugé ». Aucun juge aveugle ne chiffre le moral d'une mesure.
Le contrôle de l'état de départ (`controle_depart`) : les écarts de satisfaction que
les coefficients impliquent entre le premier et le dernier quintile de niveau de vie, et
entre chômeurs et personnes en emploi, face à ceux que SRCV publie (D-595, D-596).

Ce module tourne dans le navigateur (D-415) : numpy et yaml, ni polars ni la population.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots.jumeau.impacts import Dimension, Indicateur, Source, inscrire

PARAMETRES = Path(__file__).resolve().parents[1] / "parametres" / "moral.yaml"
N_DECILES = 10
CANAUX = ("revenu", "chomage_propre", "chomage_autour", "inflation")
LIBELLES = {"revenu": "le revenu réel", "chomage_propre": "le chômage (les chômeurs)",
            "chomage_autour": "le chômage autour de soi", "inflation": "l'inflation"}
BORNES = ("centre", "bas", "haut")


class MoralError(ValueError):
    """Une entrée que la dimension du moral refuse."""


@dataclass(frozen=True)
class Coefficients:
    """Les coefficients d'une borne, en points de satisfaction (0-10), en valeur absolue."""

    beta: float
    """par unité de log du revenu réel"""
    delta: float
    """par chômeur de plus et par an"""
    epsilon: float
    """par adulte et par point de taux de chômage"""
    phi: float
    """par adulte et par point d'inflation (moyenne mobile)"""


def charger(chemin: Path = PARAMETRES) -> dict[str, Any]:
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))


def _ancre(p: Mapping[str, Any], c: float) -> float:
    """Un coefficient de DMO (taux en fraction, échelle 1-4) porté en points de 0-10 par
    point de taux : (c / 100) δ / 0,33."""
    return c / 100.0 * float(p["chomage_propre"]["centre"]) / float(
        p["chomage_autour"]["chomeur_dmo"]["valeur"])


def coefficients(p: Mapping[str, Any], borne: str = "centre") -> Coefficients:
    """Les coefficients à une borne (« centre », « bas », « haut »), chacun à la sienne."""
    if borne not in BORNES:
        raise MoralError(f"borne « {borne} » inconnue ({BORNES})")
    autour = p["chomage_autour"]
    eps = {b: _ancre(p, float(autour["coefficient_dmo"][b])) for b in BORNES}
    hh = float(autour["bas_hh"]["equivalent_revenu"]) * 100.0 * float(
        p["revenu"]["centre"]) / 100.0
    eps["bas"] = min(eps["bas"], hh)
    return Coefficients(
        beta=float(p["revenu"][borne]), delta=float(p["chomage_propre"][borne]),
        epsilon=eps[borne], phi=_ancre(p, float(p["inflation"]["coefficient_dmo"][borne])))


def valeur_wellby_euros(p: Mapping[str, Any], borne: str = "centre") -> float:
    """La valeur d'un WELLBY en euros de 2019 (Green Book, cours moyen BCE de 2019)."""
    w = p["wellby"]
    return float(w["livres_2019"][borne]) / float(w["livre_en_euros_2019"]["valeur"])


# --------------------------------------------------------------------------- #
# les entrées
# --------------------------------------------------------------------------- #
def _etats(variante: Any, reference: Any) -> tuple[tuple[int, ...], Sequence[Any],
                                                   Sequence[Any]]:
    """(années, états de la variante, états de la référence) : d'une `Trajectoire` (qui
    porte les deux) ou de deux suites d'états."""
    if hasattr(variante, "variante") and hasattr(variante, "reference"):
        traj = variante
        return tuple(traj.annees), traj.variante, traj.reference
    if reference is None:
        raise MoralError("la variante sans sa référence")
    if hasattr(reference, "variante"):
        reference = reference.reference
    if len(variante) != len(reference):
        raise MoralError(f"{len(variante)} années de variante, {len(reference)} de "
                         f"référence")
    return tuple(int(e.annee) for e in variante), variante, reference


def _lire(etats: Sequence[Any], champ: str, tirage: int) -> np.ndarray | None:
    if not all(e.present(champ) for e in etats):
        return None
    return np.array([float(np.asarray(e[champ])[tirage]) for e in etats])


@dataclass(frozen=True)
class Entrees:
    """Ce que la dimension lit de la trajectoire, écarts variante − référence."""

    annees: tuple[int, ...]
    dln_revenu: np.ndarray
    """(années, 10) : Δln du revenu disponible réel de chaque décile"""
    d_chomeurs: np.ndarray
    """(années,) : chômeurs de plus, en personnes"""
    d_taux: np.ndarray
    """(années,) : l'écart du taux de chômage, en points"""
    d_inflation: np.ndarray
    """(années,) : l'écart d'inflation de la consommation, en points, moyenne mobile"""
    prix_lus: bool
    """faux quand l'état ne porte pas le prix de la consommation : les prix du scénario,
    les mêmes dans les deux trajectoires"""


def lire_entrees(variante: Any, reference: Any = None, *, tirage: int = 0,
                 moyenne_mobile: int = 3) -> Entrees | None:
    """Les écarts que lit la dimension ; None si la trajectoire ne porte pas les ménages
    par décile (le mode réduit)."""
    annees, var, ref = _etats(variante, reference)
    rdb = [f"rdb_d{d:02d}" for d in range(1, N_DECILES + 1)]
    if not all(e.present(c) for e in (*var, *ref) for c in
               (*rdb, "chomage", "population_active")):
        return None
    rv = np.array([[float(np.asarray(e[c])[tirage]) for c in rdb] for e in var])
    rr = np.array([[float(np.asarray(e[c])[tirage]) for c in rdb] for e in ref])
    pv, pr = (_lire(var, "ecart_prix_consommation", tirage),
              _lire(ref, "ecart_prix_consommation", tirage))
    prix_lus = pv is not None and pr is not None
    dp = (pv - pr) if prix_lus else np.zeros(len(annees))
    dln = np.log(rv / rr) - np.log1p(dp)[:, None]
    uv, ur = _lire(var, "chomage", tirage), _lire(ref, "chomage", tirage)
    av, ar = _lire(var, "population_active", tirage), _lire(ref, "population_active",
                                                            tirage)
    inflation = 100.0 * np.diff(np.concatenate([[0.0], dp]))
    return Entrees(annees=annees, dln_revenu=dln, d_chomeurs=1000.0 * (uv - ur),
                   d_taux=100.0 * (uv / av - ur / ar),
                   d_inflation=moyenne(inflation, moyenne_mobile), prix_lus=prix_lus)


def moyenne(x: np.ndarray, n: int) -> np.ndarray:
    """La moyenne mobile sur n années, l'année et les n − 1 d'avant, zéro avant la
    première (l'écart de la mesure est nul avant elle)."""
    x = np.asarray(x, dtype=float)
    pad = np.concatenate([np.zeros(n - 1), x])
    return np.array([pad[k:k + n].mean() for k in range(len(x))])


# --------------------------------------------------------------------------- #
# le calcul
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Moral:
    """Le résultat à une borne des coefficients."""

    annees: tuple[int, ...]
    satisfaction: np.ndarray
    """(années, 10) : l'écart moyen de satisfaction d'un adulte de chaque décile, points"""
    revenu: np.ndarray
    """(années, 10) : sa part qui vient du revenu réel"""
    wellby: Mapping[str, np.ndarray]
    """canal → (années,) : WELLBY par an"""
    adultes: np.ndarray
    """(10,)"""

    @property
    def total(self) -> np.ndarray:
        return sum(self.wellby.values())

    @property
    def moyenne(self) -> np.ndarray:
        """(années,) : l'écart moyen de satisfaction d'un adulte, points."""
        return self.total / self.adultes.sum()


def adultes_par_decile(cellules: Any, p: Mapping[str, Any]) -> np.ndarray:
    return float(p["adultes"]["part"]) * np.asarray(cellules.par_decile("personnes"),
                                                     dtype=float)


def calculer_moral(e: Entrees, cellules: Any, p: Mapping[str, Any],
                   borne: str = "centre") -> Moral:
    k = coefficients(p, borne)
    adultes = adultes_par_decile(cellules, p)
    chomeurs = np.asarray(cellules.par_decile("chomeurs"), dtype=float)
    part_chom = chomeurs / chomeurs.sum()
    revenu = k.beta * e.dln_revenu
    propre_d = -k.delta * e.d_chomeurs[:, None] * part_chom[None, :] / adultes[None, :]
    commun = -k.epsilon * e.d_taux - k.phi * e.d_inflation
    wellby = {"revenu": (revenu * adultes[None, :]).sum(axis=1),
              "chomage_propre": -k.delta * e.d_chomeurs,
              "chomage_autour": -k.epsilon * e.d_taux * adultes.sum(),
              "inflation": -k.phi * e.d_inflation * adultes.sum()}
    return Moral(annees=e.annees, satisfaction=revenu + propre_d + commun[:, None],
                 revenu=revenu, wellby=wellby, adultes=adultes)


def enveloppe(resultats: Sequence[Moral]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Par canal, (bas, haut) sur les bornes ; pour le total, la somme des bas et celle
    des hauts (chaque canal est linéaire en son coefficient)."""
    out = {}
    for c in CANAUX:
        pile = np.array([r.wellby[c] for r in resultats])
        out[c] = (pile.min(axis=0), pile.max(axis=0))
    out["total"] = (sum(out[c][0] for c in CANAUX), sum(out[c][1] for c in CANAUX))
    return out


# --------------------------------------------------------------------------- #
# le contrôle de l'état de départ (D-595)
# --------------------------------------------------------------------------- #
def controle_depart(cellules: Any, p: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Les écarts de satisfaction que les coefficients impliquent dans les cellules de
    départ : entre le 5e et le 1er quintile de niveau de vie (déciles 9-10 et 1-2), entre
    le 10e et le 1er décile, et entre chômeurs et personnes en emploi (δ plus β fois
    l'écart de log du niveau de vie). Le niveau de vie d'une cellule est son revenu
    disponible sur ses unités de consommation ; la moyenne des log est pondérée par les
    personnes (les quintiles d'Eurostat sont de personnes), par les chômeurs ou par les
    personnes en emploi."""
    p = p if p is not None else charger()
    nv = np.asarray(cellules["revenu_disponible"], float) / np.asarray(cellules["uc"],
                                                                       float)
    ln = np.log(nv)
    pers = np.asarray(cellules["personnes"], float)
    dec = np.repeat(np.arange(1, N_DECILES + 1), len(nv) // N_DECILES)

    def moy(poids: np.ndarray, masque: np.ndarray | None = None) -> float:
        w = poids if masque is None else poids * masque
        return float((w * ln).sum() / w.sum())

    q1, q5 = moy(pers, dec <= 2), moy(pers, dec >= 9)
    d1, d10 = moy(pers, dec == 1), moy(pers, dec == 10)
    chom = moy(np.asarray(cellules["chomeurs"], float))
    emp = moy(np.asarray(cellules["en_emploi"], float))
    out: dict[str, Any] = {"ecart_ln_q5_q1": q5 - q1, "ecart_ln_d10_d1": d10 - d1,
                           "ecart_ln_emploi_chomage": emp - chom}
    for b in BORNES:
        k = coefficients(p, b)
        out[b] = {"q5_q1": k.beta * (q5 - q1), "d10_d1": k.beta * (d10 - d1),
                  "emploi_chomage": k.delta + k.beta * (emp - chom)}
    return out


# --------------------------------------------------------------------------- #
# la dimension
# --------------------------------------------------------------------------- #
def sources(p: Mapping[str, Any]) -> tuple[Source, ...]:
    doc = p["documents"]
    k = coefficients(p)
    au = p["chomage_autour"]
    return (
        Source(doc["GBF"], p["revenu"]["lieu"],
               f"β = {k.beta:g} par unité de log du revenu (bande "
               f"{p['revenu']['bas']:g} à {p['revenu']['haut']:g})"),
        Source(doc["GB"], p["chomage_propre"]["lieu"],
               f"δ = {k.delta:g} point par chômeur et par an (bande "
               f"{p['chomage_propre']['bas']:g} à {p['chomage_propre']['haut']:g})"),
        Source(doc["DMO"], au["coefficient_dmo"]["lieu"] + " ; " + au["chomeur_dmo"]["lieu"],
               f"ε = {k.epsilon:.4f} point par adulte et par point de chômage (ancré sur "
               f"δ ; bande {coefficients(p, 'bas').epsilon:.4f} à "
               f"{coefficients(p, 'haut').epsilon:.4f})"),
        Source(doc["HH"], au["bas_hh"]["lieu"],
               "la borne basse de ε : 2,4 % du revenu par point de chômage, fois β"),
        Source(doc["DMO"], p["inflation"]["coefficient_dmo"]["lieu"],
               f"φ = {k.phi:.4f} point par adulte et par point d'inflation (bande "
               f"{coefficients(p, 'bas').phi:.4f} à {coefficients(p, 'haut').phi:.4f})"),
        Source(p["adultes"]["document"], p["adultes"]["lieu"],
               f"part des 16 ans ou plus : {p['adultes']['part']:g}"),
        Source(doc["GB"], p["wellby"]["livres_2019"]["lieu"],
               f"un WELLBY vaut {p['wellby']['livres_2019']['centre']:,} £ de 2019 "
               f"({valeur_wellby_euros(p):,.0f} € de 2019), une convention"),
        Source(p["wellby"]["livre_en_euros_2019"]["document"], "moyenne de 2019",
               f"1 € = {p['wellby']['livre_en_euros_2019']['valeur']:g} £"),
    )


LIMITES = (
    "L'adaptation hédonique : l'effet du revenu s'estompe en partie avec le temps (Clark "
    "et al. 2018 trouvent 0,13 en panel contre 0,35 à 0,50 pour un revenu exogène de long "
    "terme) ; l'effet d'une hausse durable est compté chaque année, sans adaptation. Le "
    "chômage, lui, ne s'adapte pas (Green Book, p. 14).",
    "La comparaison sociale : la satisfaction dépend en partie du revenu relatif ; une "
    "hausse de tous les revenus vaut moins que la même hausse pour un seul (le paradoxe "
    "d'Easterlin). Le coefficient β est individuel : appliqué à une hausse générale, il "
    "surestime l'effet du revenu, non borné ici.",
    "Les coefficients sont britanniques, européens (1975-1991) et américains ; aucun n'est "
    "estimé sur la France. L'ancrage de ε et φ sur le chômage propre suppose que le "
    "rapport des effets de DMO vaut sur l'échelle de 0 à 10.",
    "Un décile n'a pas de distribution interne : tous ses adultes gagnent le même log du "
    "revenu ; la perte des chômeurs est répartie entre déciles au prorata des chômeurs "
    "des cellules de 2024.",
    "La part des adultes (16 ans ou plus) est uniforme entre déciles : les déciles du bas, "
    "qui ont plus d'enfants, sont un peu surpondérés.",
    "L'inflation : l'effet de DMO est au-delà du revenu ; la perte de pouvoir d'achat, "
    "elle, est dans le canal du revenu (revenu réel). L'insécurité de l'emploi passe par "
    "le chômage autour de soi, pas comptée à part.",
    "La valeur monétaire d'un WELLBY (Green Book) se fonde sur un coefficient du revenu de "
    "1,96, pas sur β : l'équivalent monétaire du canal du revenu n'est pas le revenu "
    "gagné, il en est environ un cinquième ; c'est une convention de lecture, pas un "
    "montant.",
    "Ce qui n'est pas lu : la santé, le logement, le temps libre, les services publics, la "
    "confiance ; le moral des moins de 16 ans.",
)


@inscrire("moral")
def dimension(variante: Any, reference: Any = None, depart: Any = None,
              cellules: Any = None, *, tirage: int = 0,
              params: Mapping[str, Any] | None = None, **_: Any) -> Dimension:
    """La dimension du moral. `variante` est la `Trajectoire` (qui porte la référence) ou
    la suite des états de la variante, `reference` alors celle de la référence. `depart`
    n'est pas lu. Les cellules sont celles du jumeau (`jumeau.cellules.Cellules`)."""
    p = params if params is not None else charger()
    titre = "Le moral des gens"
    question = ("La vie que mènent les gens en est-elle plus ou moins satisfaisante, "
                "et de combien ?")
    if cellules is None:
        raise MoralError("la dimension du moral lit les cellules de ménages")
    e = lire_entrees(variante, reference, tirage=tirage,
                     moyenne_mobile=int(p["inflation"]["moyenne_mobile"]))
    if e is None:
        annees = _etats(variante, reference)[0]
        return Dimension(
            cle="moral", titre=titre, question=question, annees=annees, indicateurs=(),
            statut="sourcé, non jugé", sources=sources(p), limites=LIMITES,
            notes={"absent": "la trajectoire ne porte ni le revenu par décile ni le "
                             "chômage : le moral se lit dans le mode structurel"})
    res = {b: calculer_moral(e, cellules, p, b) for b in BORNES}
    c = res["centre"]
    env = enveloppe(list(res.values()))
    deciles = {f"D{d}": c.satisfaction[:, d - 1] for d in range(1, N_DECILES + 1)}
    v = {b: valeur_wellby_euros(p, b) for b in BORNES}
    tot_bas, tot_haut = env["total"]
    produits = np.array([x * y for x in (tot_bas, tot_haut) for y in (v["bas"], v["haut"])])
    adultes = c.adultes.sum()
    indicateurs = (
        Indicateur("wellby", "Satisfaction gagnée, toutes personnes de 16 ans ou plus",
                   "milliers de WELLBY par an", c.total / 1e3,
                   bas=tot_bas / 1e3, haut=tot_haut / 1e3,
                   par_groupe={LIBELLES[k]: c.wellby[k] / 1e3 for k in CANAUX}),
        Indicateur("satisfaction", "Écart de satisfaction d'un adulte, par décile de "
                   "niveau de vie", "points sur 10", c.moyenne,
                   bas=tot_bas / adultes, haut=tot_haut / adultes, par_groupe=deciles),
        Indicateur("satisfaction_revenu", "Dont le revenu réel, par décile",
                   "points sur 10", (c.revenu * c.adultes).sum(axis=1) / adultes,
                   bas=env["revenu"][0] / adultes, haut=env["revenu"][1] / adultes,
                   par_groupe={f"D{d}": c.revenu[:, d - 1] for d in range(1, 11)}),
        Indicateur("equivalent_monetaire", "Équivalent monétaire (valeur du WELLBY du "
                   "Green Book, une convention)", "Md€ de 2019 par an",
                   c.total * v["centre"] / 1e9, bas=produits.min(axis=0) / 1e9,
                   haut=produits.max(axis=0) / 1e9),
    )
    k = coefficients(p)
    notes = {
        "coefficients": {"beta": k.beta, "delta": k.delta, "epsilon": k.epsilon,
                         "phi": k.phi},
        "adultes_millions": adultes / 1e6,
        "valeur_wellby_euros_2019": v["centre"],
        "wellby_cumules_milliers": float(c.total.sum() / 1e3),
        "wellby_cumules_bande_milliers": [float(tot_bas.sum() / 1e3),
                                          float(tot_haut.sum() / 1e3)],
        "prix_lus": e.prix_lus,
        "entrees": {"chomeurs_de_plus_milliers": [float(x) for x in e.d_chomeurs / 1e3],
                    "taux_de_chomage_points": [float(x) for x in e.d_taux],
                    "inflation_points_mm3": [float(x) for x in e.d_inflation]},
        "tirage": tirage,
        "decisions": "D-595 à D-599",
    }
    return Dimension(cle="moral", titre=titre, question=question, annees=e.annees,
                     indicateurs=indicateurs, statut="sourcé, non jugé",
                     sources=sources(p), limites=LIMITES, notes=notes)
