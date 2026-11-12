"""La dette « si les économies annoncées sont tenues » : une lecture à part (D-319, D-380).

Le chiffrage d'un programme ne voit que sa part chiffrée : une baisse d'impôts entre dans
la dette, et les économies de dépense qui la financent n'y entrent pas, faute pour le
moteur de microsimuler la dépense publique. Cette lecture les montre à côté, sans rien
additionner : la dette de la part chiffrée, telle que le rapport de l'étude la porte,
plus l'effet des économies (et des dépenses) que le candidat chiffre lui-même, lu par la
variante « dépense publique » de Mésange.

CE QUI EST LU. Les mesures refusées par la porte `depense_publique` ou par la porte
`chaine`, et les mesures vagues de la catégorie `depense_publique`, quand le candidat leur
attache un montant annuel (`declare`) dont le sens est une économie de dépense ou une
dépense. Une recette annoncée n'est pas une dépense : la variante ne la lit pas. Un
montant écrit dans le seul paramètre de la mesure, sans `declare`, n'a ni sens ni horizon
déclarés : il est listé, pas lu (aucun paramètre n'est ajouté, D-319). Une économie ou une
dépense annoncée sous une autre porte (retraites, prestations, salaires) relève de sa
porte et de son but : listée, pas lue.

LA RÈGLE, sur la chaîne de la dette (`rejouer.chemin`), sans passe sur la population :

* le montant annoncé, multiplié par la part réalisée (0 à 1, sans valeur par défaut), est
  atteint dès la première année du chemin et tenu en part du PIB de cette année-là ; le
  calendrier que le candidat énonce (« sur cinq ans », « à terme ») est montré, pas lu ;
* en points de la variante (convention expansionniste : une économie est un choc
  négatif), il change le solde primaire de son montant, plus ce que l'activité en rend,
  (solde + 1) · m / c, et le PIB de m, m le multiplicateur de la variante au θ du rapport,
  exactement comme `rejouer.loop` lit un instrument fiscal ;
* ces trois termes s'ajoutent au solde primaire, à la rétroaction et à l'écart de PIB de
  la part chiffrée, année par année ; Mésange est linéaire, et ses variantes se
  superposent (D-230). Une part réalisée nulle redonne la dette du rapport au bit.

CE QUE LA VARIANTE SUPPOSE. Elle est un composite, pas un instrument (D-214, page 106 du
PDF) : 8 % d'investissement public, 25 % de rémunérations publiques, 9 % de prestations en
nature, 12 % de consommations intermédiaires, 46 % de prestations sociales en espèces. La
lire suppose que chaque euro annoncé tombe sur la dépense publique dans ces proportions,
quoi que la mesure dise : un gel d'effectifs pèse sur l'activité comme cette moyenne, pas
comme des rémunérations seules. Les transferts n'ont pas de variante à eux dans Mésange :
une économie sur les prestations lit la même moyenne. Le choc de la variante est en
volume ; l'euro annoncé y est lu comme un point de volume, les prix de la réforme tenus
constants (D-214, condition 4). Sa ligne de solde n'est lisible que sous la dépense gelée
en volume (note 70) : ailleurs, la lecture est refusée.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

from impots.macro import mesange
from impots.predictif import rejouer

VARIANTE = "depense_publique"
#: Les portes dont un montant annoncé est lu, et la catégorie des mesures vagues lues.
PORTES = ("depense_publique", "chaine")
CATEGORIE_VAGUE = "depense_publique"
#: Le signe d'un sens dans la convention expansionniste de Mésange.
SENS: dict[str, float] = {"economie_depense": -1.0, "depense": 1.0}
#: La règle de dépense sous laquelle la ligne de solde se lit (note 70, D-214).
REGLE = "gele_en_volume"

STATUT = ("annoncé par le candidat, non vérifié ; jamais additionné au coût de l'outil ni "
          "au verdict (D-319, D-380)")
COMPOSITE = ("La variante « dépense publique » de Mésange est un composite, pas un "
             "instrument (D-214, page 106 du PDF) : 8 % d'investissement public, 25 % de "
             "rémunérations publiques, 9 % de prestations en nature, 12 % de consommations "
             "intermédiaires, 46 % de prestations sociales en espèces. La lire suppose que "
             "chaque euro annoncé tombe sur la dépense dans ces proportions, quoi que la "
             "mesure dise ; les transferts n'ont pas de variante à eux, et une économie sur "
             "les prestations lit la même moyenne.")
HYPOTHESES = (
    "Montant atteint dès la première année du chemin et tenu en part du PIB de cette "
    "année-là : le calendrier que le candidat énonce est montré, pas lu.",
    "Choc de la variante en volume, lu comme des euros : prix de la réforme tenus "
    "constants (D-214, condition 4).",
    "Ligne de solde lue sous la dépense gelée en volume seule (note 70, D-214).",
    "Variantes superposées : Mésange est linéaire (D-230), et ce qu'annonce le candidat "
    "s'ajoute à la part chiffrée sans interaction.",
)
NON_LUE_RECETTE = ("une recette annoncée n'est pas une dépense : la variante « dépense "
                   "publique » ne la lit pas")
NON_LUE_PORTE = ("hors de la dépense publique : sa porte relève d'un autre module "
                 "(retraites, prestations, salaires, entreprises)")
NON_LUE_SANS_DECLARE = ("un montant par an dans le paramètre, sans sens ni horizon "
                        "déclarés : à porter dans `declare` pour être lu")
#: Un montant annuel écrit dans un paramètre : « 4 Md€ par an », « 160 M€/an ».
PAR_AN = re.compile(r"\d+(?:[,.]\d+)?\s*(?:Md€|M€)\s*(?:/\s*an|par an)")


class AnnonceError(ValueError):
    """La lecture ne se fait pas sur ce rapport, ou avec cette part."""


def mesures(programme: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(les mesures lues, celles qui ne le sont pas avec leur raison)."""
    lues, non_lues = [], []
    for m in programme.mesures:
        porte = m.refus.porte if m.refus is not None else None
        dans = porte in PORTES or (porte == "vague" and m.categorie == CATEGORIE_VAGUE)
        d = m.declare
        if d is None:
            if dans and PAR_AN.search(m.parametre):
                non_lues.append({"id": m.id, "libelle": m.libelle, "porte": porte,
                                 "raison": NON_LUE_SANS_DECLARE})
            continue
        if d.sens not in SENS:
            if dans:
                non_lues.append({"id": m.id, "libelle": m.libelle, "porte": porte,
                                 "raison": NON_LUE_RECETTE})
            continue
        if not dans:
            if m.chiffrage is None:
                non_lues.append({"id": m.id, "libelle": m.libelle, "porte": porte,
                                 "raison": NON_LUE_PORTE})
            continue
        lues.append({"id": m.id, "libelle": m.libelle, "porte": porte, "sens": d.sens,
                     "montant_eur": d.montant_eur, "horizon": d.horizon})
    return lues, non_lues


def tables(store: Any = None) -> dict[str, Any]:
    """Les lignes de la variante que la lecture lit, depuis le magasin macro : le PIB et le
    solde primaire aux horizons que la boucle lit, l'écart-type IMK de sa famille."""
    from impots.macro import store as store_module
    from impots.macro.fan import MULTIPLIER_FAMILY, _require
    from impots.predictif import retroaction

    store = store or store_module.load()
    read = retroaction.read_horizons(store)
    pib = _require(store, retroaction.MULTIPLIER_TABLE)
    solde = _require(store, retroaction.BALANCE_TABLE)
    first = solde.at(VARIANTE, "1")
    if not -1.0 < first < 0.0:
        raise AnnonceError(f"solde de la variante « {VARIANTE} » à un an : {first}, hors de "
                           f"]−1 ; 0[ : la ligne doit contenir le choc et en rendre une part")
    return {"horizons": list(read), "court": retroaction.short_horizon(store),
            "pib": {str(h): pib.at(VARIANTE, str(h)) for h in read},
            "solde": {str(h): solde.at(VARIANTE, str(h)) for h in read},
            "sd": _require(store, "multiplier_dispersion").at(
                MULTIPLIER_FAMILY[VARIANTE], "all"),
            "page": mesange.load()[VARIANTE].page}


def effet(points: float, years: int, variante: Mapping[str, Any], z: Any,
          persistence: str | None) -> dict[str, list]:
    """Ce qu'un choc permanent de `points` points de PIB de la variante (expansionniste
    positif) fait chaque année : au solde primaire, directement et par l'activité, et au
    PIB. En parts de PIB, comme `rejouer.chemin` les compte."""
    read = [int(h) for h in variante["horizons"]]
    short = int(variante["court"])
    primaire, retro, pib = [], [], []
    for k in range(years):
        primaire.append(-points / 100.0)
        at = rejouer._read_horizon(k + 1, persistence, read, short)
        if at is None or not points:
            retro.append(0.0)
            pib.append(0.0)
            continue
        centre = rejouer._interpolated(variante["pib"], at, read)
        m = np.maximum(0.0, centre + z * variante["sd"])
        f = np.minimum((rejouer._interpolated(variante["solde"], at, read) + 1.0) * m / centre,
                       1.0)
        retro.append(points * f / 100.0)
        pib.append(points * m / 100.0)
    return {"primaire": primaire, "retroaction": retro, "pib": pib}


def lire(payload: Mapping[str, Any], programme: Any, part: float, *,
         variante: Mapping[str, Any], theta: Mapping[str, float] | None = None,
         persistence: str = rejouer.READ,
         views: Sequence[str] = tuple(rejouer.VIEWS)) -> dict[str, Any]:
    """La dette de la part chiffrée du rapport `payload`, et la même si une part `part`
    des économies et des dépenses que le candidat annonce est réalisée, par vue.

    `part` n'a pas de valeur par défaut (D-319). `variante` est `tables()`, ou des chiffres
    types. θ est celui du rapport sauf s'il est donné."""
    if not 0.0 <= part <= 1.0:
        raise AnnonceError(f"part réalisée {part} : elle se lit dans [0, 1]")
    rejeu = rejouer._rejeu(payload)
    regle = rejeu["cadre"]["spending"]["rule"]
    if regle != REGLE:
        raise AnnonceError(f"règle de dépense « {regle} » : la ligne de solde de la variante "
                           f"ne se lit que sous « {REGLE} » (note 70, D-214)")
    if not rejeu["looped"]:
        raise AnnonceError("rapport sans boucle macro : la part chiffrée n'y lit pas "
                           "Mésange, et la variante n'y serait qu'à moitié")
    if payload.get("carry"):
        raise AnnonceError("rapport reporté : la lecture se fait sur le calcul complet")
    lues, non_lues = mesures(programme)
    theta = dict(payload["theta"] if theta is None else theta)
    values, z = rejouer.theta_values(payload, theta)
    rows = payload["years"]
    years = [int(r["year"]) for r in rows]
    gdp, _, _ = rejouer.reference_path(rejeu, rejeu["start"], len(years))
    annuel = part * sum(SENS[m["sens"]] * m["montant_eur"] for m in lues)
    # En points de la variante : le montant en part du PIB de la première année.
    points = annuel / gdp[0] * 100.0
    ajout = effet(points, len(years), variante, z, persistence)
    vues = {}
    for view in views:
        if rejouer.VIEWS[view] not in rows[0]:
            continue
        seule = rejouer.chemin(payload, view=view, values=values, z=z,
                               persistence=persistence)
        avec = rejouer.chemin(payload, view=view, values=values, z=z,
                              persistence=persistence, ajout=ajout)
        vues[view] = {"part_chiffree": [float(v) for v in seule.delta],
                      "avec_annonce": [float(v) for v in avec.delta]}
    return {
        "part": part, "statut": STATUT, "variante": VARIANTE, "composite": COMPOSITE,
        "hypotheses": list(HYPOTHESES), "page_mesange": variante.get("page"),
        "mesures": lues, "non_lues": non_lues,
        # Le solde annoncé, positif quand il améliore les comptes, sens de D-319.
        "solde_annonce_eur": -annuel, "points_variante": points,
        "theta": theta.get(rejouer.MACRO_ROW), "persistence": persistence,
        "annees": years, "vues": vues,
    }
