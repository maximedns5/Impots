"""Le registre des θ (CADRE.md §7) : chaque paramètre incertain, une ligne.

Une ligne porte sa clé, sa DÉFINITION mathématique (l'équation où elle entre), son unité,
ses valeurs à θ = 0, ½ et 1, sa direction et sa source, au format de `predictif.theta` :
la valeur passe par le centre publié, θ = 1 est partout la réponse la plus forte de
l'économie. Une valeur choisie sans source le dit (« choisie, non vérifiée »).

θ se règle de 0 à 1 et n'a AUCUN défaut : un θ que le calcul lit et que l'appel ne donne
pas est refusé par son nom. Un θ peut être un scalaire ou un tableau sur l'axe des
tirages (Monte-Carlo, curseurs).

Les lignes des blocs du lot 1 sont écrites ici ; celles du comportement des ménages
viennent des mesures, qui les portent depuis leur rapport (`predictif.rejouer`,
`rejeu.lignes`) : `registre(mesures)` les joint, et refuse deux bornes différentes sous
une même clé.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from impots.predictif.theta import CREATIONS_ROW, MACRO_ROW


class ThetaError(ValueError):
    """Un θ manquant, hors de [0 ; 1], ou deux définitions d'une même ligne."""


@dataclass(frozen=True)
class Ligne:
    cle: str
    bloc: str
    definition: str
    unite: str
    a_zero: str
    a_demi: str
    a_un: str
    direction: str
    source: str
    verifiee: bool


MULTIPLICATEUR = Ligne(
    cle=MACRO_ROW, bloc="mesange",
    definition=("m_i(h) = max(0, c_i(h) + (2θ − 1) sd_i) : le multiplicateur de "
                "l'instrument i à l'horizon h, c_i(h) la ligne du PIB de Mésange, sd_i "
                "l'écart-type inter-études de l'IMK ; la rétroaction sur le solde le suit "
                "en proportion, bornée par le coût brut (`retroaction`, D-336)"),
    unite="% du PIB par point de PIB de variante",
    a_zero="max(0, c_i(h) − sd_i)", a_demi="c_i(h), le centre de Mésange",
    a_un="c_i(h) + sd_i",
    direction="θ = 1 : l'activité répond le plus",
    source=("Insee, Mésange (G2017-04), tableaux des variantes ; IMK WP 117 (2013), "
            "dispersion par famille d'instrument (D-218, D-336)"),
    verifiee=True)

PRODUCTIVITE_CREATIONS = Ligne(
    cle=CREATIONS_ROW, bloc="creations",
    definition=("c dans y_t = s_VA r c Σ_s Δe_s/100 S^(t−s) min(1, (t−s+1)/M) : la "
                "productivité d'une société nouvelle rapportée à la moyenne "
                "(`predictif.creations`)"),
    unite="sans dimension", a_zero="0 (le canal éteint)", a_demi="0,5", a_un="1",
    direction="θ = 1 : les entrants aussi productifs que la moyenne",
    source=("choisie, non vérifiée : aucune source ne la chiffre pour des entrants "
            "marginaux (D-402) ; borne haute, Foster, Haltiwanger et Syverson (AER 2008)"),
    verifiee=False)

REGISTRE: dict[str, Ligne] = {MULTIPLICATEUR.cle: MULTIPLICATEUR,
                              PRODUCTIVITE_CREATIONS.cle: PRODUCTIVITE_CREATIONS}


def ligne_comportement(cle: str, row: Mapping[str, Any]) -> Ligne:
    """Une ligne du comportement des ménages, telle qu'un rapport la porte."""
    return Ligne(
        cle=cle, bloc="mesures",
        definition=("p(θ) = centre − (1 − 2t)(centre − bas) si t ≤ ½, centre + (2t − 1)"
                    "(haut − centre) sinon, t = θ ou 1 − θ selon la direction : le "
                    "paramètre du canal de recettes (`predictif.theta.value_at`)"),
        unite="celle de la ligne du magasin comportemental",
        a_zero=str(row["low"] if row["un"] == "high" else row["high"]),
        a_demi=str(row["central"]),
        a_un=str(row["high"] if row["un"] == "high" else row["low"]),
        direction=f"θ = 1 : la borne « {row['un']} »",
        source=("magasin comportemental (`impots.behavioural`), fichier "
                f"« {row.get('fichier', cle)} », lu dans le rapport de la mesure"),
        verifiee=True)


def registre(mesures: Iterable[Any] = ()) -> dict[str, Ligne]:
    """Les lignes des blocs, plus celles que les mesures portent."""
    out = dict(REGISTRE)
    bornes: dict[str, tuple[Any, ...]] = {}
    for mesure in mesures:
        for cle, row in (mesure.lignes or {}).items():
            vu = (row["low"], row["central"], row["high"], row["un"])
            if cle in bornes and bornes[cle] != vu:
                raise ThetaError(f"θ « {cle} » porté avec deux définitions : {bornes[cle]} "
                                 f"et {vu}")
            bornes[cle] = vu
            out[cle] = ligne_comportement(cle, row)
    return out


def lire(theta: Mapping[str, Any], cle: str, n: int) -> np.ndarray:
    """θ d'une ligne, en tableau de forme (n,) ; refusé s'il manque ou sort de [0 ; 1]."""
    if cle not in theta:
        raise ThetaError(f"aucun θ pour « {cle} » : il n'a pas de défaut, il est refusé")
    valeur = np.asarray(theta[cle], dtype=float)
    if valeur.ndim == 0:
        valeur = np.full(n, float(valeur))
    if valeur.shape != (n,):
        raise ThetaError(f"θ « {cle} » de forme {valeur.shape}, attendu ({n},)")
    if np.any((valeur < 0.0) | (valeur > 1.0)):
        raise ThetaError(f"θ « {cle} » hors de [0 ; 1] : refusé plutôt qu'écrêté")
    return valeur


def tirages(theta: Mapping[str, Any]) -> int:
    """n, la longueur commune des θ donnés en tableau (1 s'ils sont tous scalaires)."""
    longueurs = {np.size(v) for v in theta.values() if np.ndim(v)}
    if len(longueurs) > 1:
        raise ThetaError(f"θ sur des axes de tirages de longueurs {sorted(longueurs)}")
    return longueurs.pop() if longueurs else 1


# --------------------------------------------------------------------- lot 2 (D-407)
from impots.jumeau.blocs.valeurs_entreprises import lignes as _lignes_lot2  # noqa: E402

REGISTRE.update(_lignes_lot2(Ligne))
