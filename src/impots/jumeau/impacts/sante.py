"""La santé et le temps de vie (but 29, volet `sante`, D-620 à D-624).

Ce que la trajectoire fait aux ménages, traduit en années de vie, en décès (un ordre de
grandeur), en santé déclarée, en renoncement aux soins et, quand un programme touche à
l'âge de départ, en années de retraite sans limitation d'activité. Cinq canaux, chacun avec
un coefficient publié et sa bande (`jumeau/parametres/sante.yaml`, document, page, valeur) :

    revenu → durée de vie   ΔEV_d = s g Δln y_d     l'espérance de vie du décile d si l'écart
                            de revenu réel durait ; g l'ASSOCIATION de l'Insee (années par
                            unité de log du niveau de vie, moyenne des deux sexes), s sa part
                            causale (0 à 1/6, Cesarini et al.) ; les décès : Δln μ_d =
                            −ΔEV_d / e†, décès évités = D_d (1 − exp Δln μ_d), années de vie
                            = décès × e† (e† : les années perdues en moyenne à un décès)
    chômage → mortalité     décès = −ΔU m r         m le taux de décès des 25-64 ans, r le
                            surcroît relatif de risque d'un chômeur (Sullivan et von Wachter) ;
                            années de vie = décès × années restantes à un décès de 25-64 ans
    chômage → santé         Δ(bonne santé) = −ΔU (e − u) c      e − u l'écart brut de santé
                            déclarée entre emploi et chômage (SRCV), c sa part causale
    revenu → renoncement    Δ(renoncements)_d = −k b Δln y_d A_d     b la pente, par unité
                            de log, de la part qui renonce à un examen (médical, dentaire)
                            parce qu'il est trop cher, entre Q1 et Q5 ; k sa part causale
    âge de départ           Δ(années de retraite)_t = −τ Δa_t N       Δa l'écart d'âge légal
                            du programme (une entrée : le jumeau ne règle pas l'âge), τ ce
                            qu'en suit l'âge effectif, N une génération ; dont sans
                            limitation d'activité × λ ; années de vie = τ Δa N v, v de −0,1 à
                            +0,1 an par personne et par an de départ plus tardif, centre 0

LA BANDE. Chaque canal est linéaire en son coefficient (la conversion en décès est presque
linéaire) : sa bande est le canal aux deux bornes ; celle du total somme les bornes de même
sens (l'enveloppe, pas un intervalle de confiance).

LE STATUT : « illustratif ». Les coefficients sont publiés, mais les centres des parts
causales sont choisis dans leur bande (D-620) ; le gradient de l'Insee est une association.

Le contrôle de l'état de départ (`controle_depart`) : l'écart d'espérance de vie entre le
dixième et le premier décile de niveau de vie que g implique sur les cellules, face au
fichier de l'Insee Première n° 1687 (D-620, D-621).

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
from impots.jumeau.impacts.moral import Entrees, _etats, lire_entrees

PARAMETRES = Path(__file__).resolve().parents[1] / "parametres" / "sante.yaml"
N_DECILES = 10
BORNES = ("centre", "bas", "haut")
CANAUX_VIE = ("revenu", "chomage", "retraite")
LIBELLES = {"revenu": "le revenu réel", "chomage": "le chômage",
            "retraite": "l'âge de départ"}


class SanteError(ValueError):
    """Une entrée que la dimension de la santé refuse."""


def charger(chemin: Path = PARAMETRES) -> dict[str, Any]:
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# les coefficients
# --------------------------------------------------------------------------- #
def gradient(p: Mapping[str, Any], sexe: str | None = None) -> float:
    """g : années d'espérance de vie par unité de log du niveau de vie (l'association des
    deux vingtiles extrêmes de l'Insee) ; la moyenne des deux sexes si `sexe` est None."""
    r = p["revenu_vie"]
    ln = np.log(float(r["niveau_de_vie"]["haut"]) / float(r["niveau_de_vie"]["bas"]))
    if sexe is None:
        return 0.5 * (gradient(p, "hommes") + gradient(p, "femmes"))
    return (float(r[sexe]["haut"]) - float(r[sexe]["bas"])) / float(ln)


@dataclass(frozen=True)
class Coefficients:
    """Les coefficients d'une borne ; chacun à la borne qui va dans le même sens (une borne
    « haut » est celle où une hausse du revenu ou une baisse du chômage fait le plus)."""

    s: float
    """part causale du gradient revenu → durée de vie"""
    r: float
    """surcroît relatif de risque de décès d'un chômeur"""
    c: float
    """part causale de l'écart de santé déclarée emploi − chômage"""
    k: float
    """part causale du gradient de renoncement aux soins"""
    tau: float
    """âge effectif par an d'âge légal"""
    lam: float
    """part des années de retraite (60-64 ans) sans limitation d'activité"""
    v: float
    """années de vie par personne et par an de départ plus tardif"""


def coefficients(p: Mapping[str, Any], borne: str = "centre") -> Coefficients:
    if borne not in BORNES:
        raise SanteError(f"borne « {borne} » inconnue ({BORNES})")
    re = p["retraite"]
    return Coefficients(
        s=float(p["revenu_vie"]["part_causale"][borne]),
        r=float(p["chomage_mortalite"][borne]),
        c=float(p["chomage_sante"]["part_causale"][borne]),
        k=float(p["renoncement"]["part_causale"][borne]),
        tau=float(re["transmission"][borne]), lam=float(re["sans_limitation"][borne]),
        v=float(re["vie"][borne]))


# --------------------------------------------------------------------------- #
# l'âge de départ
# --------------------------------------------------------------------------- #
def _chemin(ages: Mapping[Any, Any], annees: Sequence[int],
            avant: np.ndarray | None = None) -> np.ndarray:
    """L'âge par année : en ligne droite entre deux années données, constant après la
    dernière ; avant la première, `avant` (la référence)."""
    if not ages:
        if avant is None:
            raise SanteError("un chemin d'âge vide sans référence")
        return np.asarray(avant, float).copy()
    xs = np.array(sorted(int(a) for a in ages), float)
    ys = np.array([float(ages[int(a)] if int(a) in ages else ages[str(int(a))])
                   for a in xs])
    t = np.asarray(annees, float)
    out = np.interp(t, xs, ys)
    if avant is not None:
        out = np.where(t < xs[0], avant, out)
    return out


def ecart_age_legal(p: Mapping[str, Any], programme: str | None,
                    annees: Sequence[int]) -> np.ndarray:
    """Δa_t : l'âge légal du programme moins celui de la référence, par année (zéro pour un
    programme sans âge dans `sante.yaml`)."""
    re = p["retraite"]
    ref = _chemin(re["reference"]["ages"], annees)
    if programme is None or programme not in re["programmes"]:
        return np.zeros(len(annees))
    var = _chemin(re["programmes"][programme]["ages"], annees, avant=ref)
    return var - ref


# --------------------------------------------------------------------------- #
# le calcul
# --------------------------------------------------------------------------- #
def niveau_de_vie_log(cellules: Any) -> tuple[np.ndarray, np.ndarray]:
    """(moyenne du log du niveau de vie par décile pondérée par les personnes, personnes par
    décile) ; le niveau de vie d'une cellule : revenu disponible sur unités de
    consommation."""
    nv = np.asarray(cellules["revenu_disponible"], float) / np.asarray(cellules["uc"], float)
    pers = np.asarray(cellules["personnes"], float)
    dec = np.repeat(np.arange(N_DECILES), len(nv) // N_DECILES)
    ln = np.where(pers > 0, np.log(np.where(nv > 0, nv, 1.0)), 0.0)
    out = np.array([(pers * ln)[dec == d].sum() / pers[dec == d].sum()
                    for d in range(N_DECILES)])
    return out, np.array([pers[dec == d].sum() for d in range(N_DECILES)])


def pente_renoncement(p: Mapping[str, Any], ln_dec: np.ndarray, poste: str) -> float:
    """b : points de pourcentage de renoncement par unité de log du niveau de vie, de Q1
    (déciles 1-2) à Q5 (déciles 9-10) des cellules ; positif (le renoncement baisse avec le
    revenu)."""
    r = p["renoncement"][poste]
    lnq1, lnq5 = ln_dec[:2].mean(), ln_dec[-2:].mean()
    return (float(r["q1"]) - float(r["q5"])) / float(lnq5 - lnq1)


@dataclass(frozen=True)
class Sante:
    """Le résultat à une borne des coefficients, écarts variante − référence."""

    annees: tuple[int, ...]
    esperance: np.ndarray
    """(années, 10) : Δ espérance de vie à la naissance si l'écart durait, années"""
    deces_revenu: np.ndarray
    """(années, 10) : décès évités par le revenu (positif = moins de décès)"""
    vie: Mapping[str, np.ndarray]
    """canal → (années,) : années de vie gagnées par an"""
    deces: Mapping[str, np.ndarray]
    """« revenu », « chomage » → (années,) : décès évités par an"""
    bonne_sante: np.ndarray
    """(années,) : personnes de plus en bonne ou très bonne santé déclarée"""
    renoncements: np.ndarray
    """(années, 10) : renoncements à un examen (médical + dentaire) évités"""
    retraite: np.ndarray
    """(années,) : années-personnes de retraite de plus par an"""
    retraite_sans_limitation: np.ndarray
    """(années,) : dont sans limitation d'activité"""

    @property
    def vie_totale(self) -> np.ndarray:
        return sum(self.vie.values())

    @property
    def deces_total(self) -> np.ndarray:
        return sum(self.deces.values())


def calculer_sante(e: Entrees, cellules: Any, p: Mapping[str, Any], borne: str = "centre",
                   ecart_age: np.ndarray | None = None) -> Sante:
    k = coefficients(p, borne)
    t = p["table"]
    edag = float(t["disparite"])
    g = gradient(p)
    ln_dec, pers = niveau_de_vie_log(cellules)
    # les décès de 2024 entre déciles : selon les personnes et le gradient
    ev_rel = g * (ln_dec - (pers * ln_dec).sum() / pers.sum())
    poids = pers * np.exp(-ev_rel / edag)
    deces_dec = float(t["deces_2024"]) * poids / poids.sum()
    # revenu → durée de vie
    d_ev = k.s * g * e.dln_revenu
    dlnmu = -d_ev / edag
    deces_rev = deces_dec[None, :] * (1.0 - np.exp(dlnmu))
    # chômage → mortalité et santé
    deces_chom = -e.d_chomeurs * float(t["taux_deces_25_64"]) * k.r
    cs = p["chomage_sante"]
    bonne = -e.d_chomeurs * (float(cs["emploi"]) - float(cs["chomeurs"])) / 100.0 * k.c
    # revenu → renoncement
    adultes = float(p["adultes"]["part"]) * pers
    b = sum(pente_renoncement(p, ln_dec, poste) for poste in ("medical", "dentaire"))
    renonc = k.k * b / 100.0 * e.dln_revenu * adultes[None, :]
    # âge de départ
    da = np.zeros(len(e.annees)) if ecart_age is None else np.asarray(ecart_age, float)
    n_gen = float(t["generation_62_64"])
    retraite = -k.tau * da * n_gen
    vie_retraite = k.tau * da * n_gen * k.v
    vie = {"revenu": deces_rev.sum(axis=1) * edag,
           "chomage": deces_chom * float(t["annees_perdues_25_64"]),
           "retraite": vie_retraite}
    return Sante(annees=e.annees, esperance=d_ev, deces_revenu=deces_rev, vie=vie,
                 deces={"revenu": deces_rev.sum(axis=1), "chomage": deces_chom},
                 bonne_sante=bonne, renoncements=renonc, retraite=retraite,
                 retraite_sans_limitation=retraite * k.lam)


def enveloppe(resultats: Sequence[Sante], lire: Any) -> tuple[np.ndarray, np.ndarray]:
    """(bas, haut) d'une grandeur sur les bornes, élément par élément."""
    pile = np.array([lire(r) for r in resultats])
    return pile.min(axis=0), pile.max(axis=0)


def enveloppe_retraite(p: Mapping[str, Any], da: np.ndarray
                       ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(bas, haut) des années de retraite sans limitation et des années de vie du canal de
    l'âge de départ : le minimum et le maximum sur toutes les combinaisons des bornes de τ,
    λ et v, parce que l'écart d'âge change de signe d'un programme à l'autre et que v va
    dans les deux sens."""
    re, n = p["retraite"], float(p["table"]["generation_62_64"])
    da = np.asarray(da, float)
    taus = [float(re["transmission"][b]) for b in ("bas", "haut")]
    lams = [float(re["sans_limitation"][b]) for b in ("bas", "haut")]
    vs = [float(re["vie"][b]) for b in ("bas", "haut")]
    rt = np.array([-t * da * n * lam for t in taus for lam in lams])
    vr = np.array([t * da * n * v for t in taus for v in vs])
    return rt.min(axis=0), rt.max(axis=0), vr.min(axis=0), vr.max(axis=0)


# --------------------------------------------------------------------------- #
# le contrôle de l'état de départ (D-620)
# --------------------------------------------------------------------------- #
def controle_depart(cellules: Any, p: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """L'écart d'espérance de vie à la naissance entre le dixième et le premier décile de
    niveau de vie que g implique sur les cellules de départ, pour chaque sexe et en moyenne,
    et l'écart de chaque décile au premier (D-620)."""
    p = p if p is not None else charger()
    ln_dec, _ = niveau_de_vie_log(cellules)
    ecart = float(ln_dec[-1] - ln_dec[0])
    out: dict[str, Any] = {"ecart_ln_d10_d1": ecart}
    for sexe in ("hommes", "femmes"):
        g = gradient(p, sexe)
        out[sexe] = {"gradient": g, "d10_d1": g * ecart,
                     "par_decile": [float(g * (x - ln_dec[0])) for x in ln_dec]}
    out["deux_sexes_d10_d1"] = gradient(p) * ecart
    return out


# --------------------------------------------------------------------------- #
# la dimension
# --------------------------------------------------------------------------- #
def sources(p: Mapping[str, Any]) -> tuple[Source, ...]:
    doc = p["documents"]
    rv, re = p["revenu_vie"], p["retraite"]
    cs, rn, t = p["chomage_sante"], p["renoncement"], p["table"]
    return (
        Source(doc["IP1687"], rv["lieu"],
               f"g = {gradient(p, 'hommes'):.2f} ans (hommes) et "
               f"{gradient(p, 'femmes'):.2f} (femmes) d'espérance de vie par unité de log "
               "du niveau de vie, une association"),
        Source(doc["CLOW"], rv["part_causale"]["lieu"],
               f"part causale s = {rv['part_causale']['centre']:.3f} (bande 0 à 1/6), le "
               "centre choisi"),
        Source(doc["SVW"], p["chomage_mortalite"]["lieu"],
               f"r = {p['chomage_mortalite']['centre']:g} (bande "
               f"{p['chomage_mortalite']['bas']:g} à {p['chomage_mortalite']['haut']:g})"),
        Source(doc["SILC1"], cs["lieu_ecart"],
               f"bonne ou très bonne santé : {cs['emploi']:g} % en emploi, "
               f"{cs['chomeurs']:g} % au chômage ; part causale {cs['part_causale']['centre']:g}"
               f" (bande 0 à {cs['part_causale']['haut']:g}, Schmitz 2011 au bas)"),
        Source(doc["SILC8"], rn["lieu"],
               f"renoncement pour le prix : examen médical {rn['medical']['q1']:g} % (Q1) "
               f"contre {rn['medical']['q5']:g} % (Q5), dentaire {rn['dentaire']['q1']:g} % "
               f"contre {rn['dentaire']['q5']:g} % ; part causale "
               f"{rn['part_causale']['centre']:g}, choisie"),
        Source(doc["COR2"], re["transmission"]["lieu"],
               f"τ = {re['transmission']['centre']:g} an d'âge effectif par an d'âge légal "
               f"(bande {re['transmission']['bas']:g} à {re['transmission']['haut']:g})"),
        Source(doc["COR1"], re["sans_limitation"]["lieu"],
               f"part des années de 60-64 ans sans limitation : "
               f"{re['sans_limitation']['centre']:g} (sans limitation sévère : "
               f"{re['sans_limitation']['haut']:g})"),
        Source(doc["BGP"], re["vie"]["lieu"],
               f"années de vie par an de départ plus tardif : {re['vie']['centre']:g} "
               f"(bande {re['vie']['bas']:g} à {re['vie']['haut']:g})"),
        Source(doc["TABLE"], t["lieu"],
               f"e0 = {t['e0']:g} ans, e† = {t['disparite']:g} ans, {t['deces_2024']:,} décès "
               f"en 2024, taux de décès des 25-64 ans {t['taux_deces_25_64']:g}, "
               f"{t['annees_perdues_25_64']:g} ans perdus à un décès de cet âge, une "
               f"génération de 62-64 ans : {t['generation_62_64']:,}"),
    )


LIMITES = (
    "La bande est l'enveloppe des bornes publiées des coefficients, canal par canal "
    "(celle du total somme les bornes de même sens) : ni un intervalle de confiance, ni "
    "des tirages des θ du jumeau, qui sont lus au réglage.",
    "Corrélation contre causalité, surtout : le gradient de l'Insee (13 ans d'écart "
    "d'espérance de vie chez les hommes entre les 5 % les plus aisés et les 5 % les plus "
    "modestes) est une association ; le diplôme, le métier, la santé dès l'enfance font à "
    "la fois le revenu et la durée de vie, et la mauvaise santé fait baisser le revenu. "
    "Les loteries suédoises (Cesarini et al. 2016) excluent un effet causal de la richesse "
    "sur la mortalité d'un sixième du gradient ; la dimension en garde au plus un sixième, "
    "au centre un douzième. Aux États-Unis (Chetty et al. 2016), l'écart est aussi une "
    "association.",
    "L'espérance de vie par décile est celle qu'aurait le décile si l'écart de revenu de "
    "l'année durait toute la vie ; les décès évités de l'année la traduisent par la "
    "disparité de la durée de vie (e†), comme si la mortalité de tous les âges bougeait "
    "d'un même facteur. L'effet du revenu sur la santé met des années à venir ; il est "
    "compté l'année même.",
    "Le chômage : Sullivan et von Wachter mesurent la perte d'emploi d'hommes anciens dans "
    "leur entreprise, aux États-Unis ; leur effet dure vingt ans après le retour à "
    "l'emploi, ce qui n'est pas compté ici (un bas), mais un chômeur du stock n'est pas "
    "toujours dans sa première année (le centre de 0,30 est choisi). La santé déclarée des "
    "chômeurs est moins bonne surtout par sélection (Schmitz 2011).",
    "Le renoncement aux soins pour raison de prix est déclaratif et sa mesure dépend de la "
    "question ; un même ménage peut renoncer à un examen médical et à un examen dentaire : "
    "ce sont des renoncements, pas des personnes. La couverture (complémentaire santé "
    "solidaire, 100 % santé) n'est pas lue.",
    "L'âge de départ n'est pas dans le jumeau (la population ne vieillit pas) : l'écart "
    "d'âge légal est une entrée lue dans le texte du programme, avec un calendrier choisi ; "
    "l'âge effectif en suit une part τ. La littérature ne trouve pas d'effet d'un départ "
    "plus tardif sur la mortalité en France (Bozio, Garrouste et Perdrix 2021) ; Kuhn et "
    "al. 2020 trouvent qu'une sortie anticipée raccourcit la vie des hommes, Hallberg et al. "
    "2015 le contraire : la bande va dans les deux sens. Le report de 2010 a augmenté les "
    "arrêts maladie et la consommation de soins après 60 ans (Caroli, Pollak et Roger 2023), "
    "la bascule vers l'invalidité et le chômage : non chiffrés ici.",
    "Les années de retraite sans limitation d'activité sont du temps libre en bonne santé, "
    "pas une durée de vie : un départ plus tardif en retire, sans changer la longévité au "
    "centre. La part sans limitation est celle des 60-64 ans de tous statuts (COR).",
    "Les déciles n'ont ni âge ni sexe : les décès sont répartis selon les personnes et le "
    "gradient, pas selon l'âge des membres de chaque décile.",
    "Ce qui n'est pas lu : le temps de travail (35 h, 32 h, 28 h), les conditions de travail "
    "et la pénibilité, l'offre de soins et les dépenses de santé publiques (hôpital, 100 % "
    "Sécu), le logement, la pollution, la santé des enfants.",
)


@inscrire("sante")
def dimension(variante: Any, reference: Any = None, depart: Any = None,
              cellules: Any = None, *, tirage: int = 0, programme: str | None = None,
              ecart_age: Sequence[float] | None = None,
              params: Mapping[str, Any] | None = None, **_: Any) -> Dimension:
    """La dimension de la santé. `variante` est la `Trajectoire` (qui porte la référence) ou
    la suite des états de la variante, `reference` alors celle de la référence ; les
    cellules sont celles du jumeau. L'écart d'âge légal vient de `ecart_age` (par année) ou,
    à défaut, du `programme` (`retraite.programmes` de `sante.yaml`) ; zéro sinon."""
    p = params if params is not None else charger()
    titre = "La santé et le temps de vie"
    question = ("Les gens en vivent-ils plus longtemps, en meilleure santé, et combien de "
                "temps de retraite en bonne santé y gagnent-ils ou y perdent-ils ?")
    if cellules is None:
        raise SanteError("la dimension de la santé lit les cellules de ménages")
    annees = _etats(variante, reference)[0]
    if ecart_age is not None:
        da = np.asarray(ecart_age, float)
        if da.shape != (len(annees),):
            raise SanteError(f"écart d'âge de forme {da.shape}, {len(annees)} années")
    else:
        da = ecart_age_legal(p, programme, annees)
    e = lire_entrees(variante, reference, tirage=tirage, moyenne_mobile=1)
    if e is None:
        return Dimension(
            cle="sante", titre=titre, question=question, annees=annees, indicateurs=(),
            statut="illustratif", sources=sources(p), limites=LIMITES,
            notes={"absent": "la trajectoire ne porte ni le revenu par décile ni le "
                             "chômage : la santé se lit dans le mode structurel"})
    res = {b: calculer_sante(e, cellules, p, b, da) for b in BORNES}
    c = res["centre"]
    r = list(res.values())
    vie_env = {k: enveloppe(r, lambda x, k=k: x.vie[k]) for k in CANAUX_VIE}
    dec_env = {k: enveloppe(r, lambda x, k=k: x.deces[k]) for k in ("revenu", "chomage")}
    ev_bas, ev_haut = enveloppe(r, lambda x: x.esperance)
    ren_bas, ren_haut = enveloppe(r, lambda x: x.renoncements.sum(axis=1))
    bs_bas, bs_haut = enveloppe(r, lambda x: x.bonne_sante)
    rt_bas, rt_haut, vr_bas, vr_haut = enveloppe_retraite(p, da)
    vie_env["retraite"] = (vr_bas, vr_haut)
    vie_bas = sum(v[0] for v in vie_env.values())
    vie_haut = sum(v[1] for v in vie_env.values())
    _, pers = niveau_de_vie_log(cellules)
    ev_moy = (c.esperance * pers).sum(axis=1) / pers.sum()
    indicateurs = (
        Indicateur("annees_de_vie", "Années de vie gagnées dans l'année, tous canaux",
                   "milliers d'années de vie par an", c.vie_totale / 1e3,
                   bas=vie_bas / 1e3, haut=vie_haut / 1e3,
                   par_groupe={LIBELLES[k]: c.vie[k] / 1e3 for k in CANAUX_VIE}),
        Indicateur("deces_evites", "Décès évités dans l'année (revenu et chômage), un ordre "
                   "de grandeur", "décès par an", c.deces_total,
                   bas=dec_env["revenu"][0] + dec_env["chomage"][0],
                   haut=dec_env["revenu"][1] + dec_env["chomage"][1],
                   par_groupe={LIBELLES[k]: c.deces[k] for k in ("revenu", "chomage")}),
        Indicateur("deces_evites_revenu", "Dont décès évités par le revenu réel, par décile "
                   "de niveau de vie", "décès par an", c.deces["revenu"],
                   bas=dec_env["revenu"][0], haut=dec_env["revenu"][1],
                   par_groupe={f"D{d}": c.deces_revenu[:, d - 1]
                               for d in range(1, N_DECILES + 1)}),
        Indicateur("esperance_de_vie", "Espérance de vie à la naissance si l'écart de "
                   "revenu durait, par décile de niveau de vie", "mois", 12.0 * ev_moy,
                   bas=12.0 * (ev_bas * pers).sum(axis=1) / pers.sum(),
                   haut=12.0 * (ev_haut * pers).sum(axis=1) / pers.sum(),
                   par_groupe={f"D{d}": 12.0 * c.esperance[:, d - 1]
                               for d in range(1, N_DECILES + 1)}),
        Indicateur("bonne_sante", "Personnes de plus en bonne ou très bonne santé déclarée "
                   "(le chômage)", "milliers de personnes", c.bonne_sante / 1e3,
                   bas=bs_bas / 1e3, haut=bs_haut / 1e3),
        Indicateur("renoncements_evites", "Renoncements à un examen médical ou dentaire "
                   "pour le prix, évités, par décile", "milliers par an",
                   c.renoncements.sum(axis=1) / 1e3, bas=ren_bas / 1e3, haut=ren_haut / 1e3,
                   par_groupe={f"D{d}": c.renoncements[:, d - 1] / 1e3
                               for d in range(1, N_DECILES + 1)}),
        Indicateur("retraite_sans_limitation", "Années de retraite sans limitation "
                   "d'activité gagnées (l'âge de départ)", "milliers d'années-personnes "
                   "par an", c.retraite_sans_limitation / 1e3, bas=rt_bas / 1e3,
                   haut=rt_haut / 1e3,
                   par_groupe={"toutes les années de retraite": c.retraite / 1e3}),
    )
    k = coefficients(p)
    notes = {
        "coefficients": {"g_hommes": gradient(p, "hommes"), "g_femmes": gradient(p, "femmes"),
                         "g": gradient(p), "s": k.s, "r": k.r, "c": k.c, "k": k.k,
                         "tau": k.tau, "lambda": k.lam, "v": k.v},
        "annees_de_vie_cumulees_milliers": float(c.vie_totale.sum() / 1e3),
        "annees_de_vie_cumulees_bande_milliers": [float(vie_bas.sum() / 1e3),
                                                  float(vie_haut.sum() / 1e3)],
        "deces_evites_cumules": float(c.deces_total.sum()),
        "retraite_sans_limitation_cumulee_milliers": float(
            c.retraite_sans_limitation.sum() / 1e3),
        "ecart_age_legal": [float(x) for x in da],
        "programme_age": programme,
        "prix_lus": e.prix_lus,
        "entrees": {"chomeurs_de_plus_milliers": [float(x) for x in e.d_chomeurs / 1e3]},
        "tirage": tirage,
        "decisions": "D-620 à D-624",
    }
    return Dimension(cle="sante", titre=titre, question=question, annees=e.annees,
                     indicateurs=indicateurs, statut="illustratif", sources=sources(p),
                     limites=LIMITES, notes=notes)
