"""Les identités vérifiées à chaque pas (CADRE.md §6), à 1e-9 du PIB, sur chaque tirage.

1. ``emplois`` — le PIB égale la somme signée de ses emplois (importations en moins),
   l'effet non ventilé, la ventilation et l'arrondi publiés compris ;
2. ``revenus`` — le PIB égale D1 + B2A3G + D2 − D3, l'effet non ventilé et l'arrondi
   publié compris ;
3. ``apu`` — les recettes et les dépenses primaires égalent la somme de leurs catégories,
   B9 = recettes − dépenses primaires − intérêts nets, et le solde primaire = B9 +
   intérêts nets ;
4. ``dette`` — D_t = D_{t−1} − B9_t + SFA_t (+ l'écart de millésime et l'arrondi publiés,
   nuls en projection) ; avec l'état précédent, la dette d'ouverture est sa dette ;
5. ``contributions`` — chaque champ additif égale la somme de ses contributions.

Une identité qui lit un champ absent REFUSE en le nommant (`IdentiteIncalculable`) : elle
ne le remplace pas par zéro. Une identité violée lève `IdentiteViolee`, qui dit laquelle,
l'année, le tirage et l'écart.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from impots.jumeau.champs import DEPENSES, EMPLOIS, RECETTES, REGISTRE, REVENUS
from impots.jumeau.champs import champ as definition
from impots.jumeau.etat import ChampAbsent, Etat

TOLERANCE = 1e-9
"""En part du PIB, sur chaque tirage (§6)."""

IDENTITES = ("emplois", "revenus", "apu", "dette", "contributions")


class IdentiteIncalculable(ValueError):
    """Une identité lit un champ absent."""


class IdentiteViolee(ValueError):
    """Une identité ne tient pas à 1e-9 du PIB."""


def _lire(etat: Etat, nom: str, identite: str) -> np.ndarray:
    try:
        return etat[nom]
    except ChampAbsent:
        raise IdentiteIncalculable(
            f"identité « {identite} » en {etat.annee} : le champ « {nom} » est absent ; "
            f"elle ne le lit pas comme nul") from None


def _signee(etat: Etat, noms: tuple[str, ...], identite: str) -> np.ndarray:
    total = np.zeros(etat.n)
    for nom in noms:
        total = total + definition(nom).signe * _lire(etat, nom, identite)
    return total


def _emplois(etat: Etat) -> dict[str, np.ndarray]:
    return {"emplois": _lire(etat, "pib", "emplois") - _signee(etat, EMPLOIS, "emplois")}


def _revenus(etat: Etat) -> dict[str, np.ndarray]:
    return {"revenus": _lire(etat, "pib", "revenus") - _signee(etat, REVENUS, "revenus")}


def _apu(etat: Etat) -> dict[str, np.ndarray]:
    def lu(nom: str) -> np.ndarray:
        return _lire(etat, nom, "apu")

    recettes, depenses = lu("apu_recettes"), lu("apu_depenses_primaires")
    interets, b9 = lu("interets_nets"), lu("b9")
    return {"apu.recettes": recettes - _signee(etat, RECETTES, "apu"),
            "apu.depenses": depenses - _signee(etat, DEPENSES, "apu"),
            "apu.b9": b9 - (recettes - depenses - interets),
            "apu.solde_primaire": lu("solde_primaire") - (b9 + interets)}


def _dette(etat: Etat, precedent: Etat | None = None) -> dict[str, np.ndarray]:
    def lu(nom: str) -> np.ndarray:
        return _lire(etat, nom, "dette")

    ouverture = lu("dette_ouverture")
    out = {"dette": lu("dette") - (ouverture - lu("b9") + lu("sfa")
                                   + lu("ecart_millesime_dette") + lu("ecart_eurostat"))}
    if precedent is not None:
        out["dette.continuite"] = ouverture - _lire(precedent, "dette", "dette")
    return out


def _contributions(etat: Etat) -> dict[str, np.ndarray]:
    pire = np.zeros(etat.n)
    for nom in etat.champs():
        if not REGISTRE[nom].additif:
            continue
        total = np.zeros(etat.n)
        for valeur in etat.contributions[nom].values():
            total = total + valeur
        pire = np.maximum(pire, np.abs(etat[nom] - total))
    return {"contributions": pire}


_CALCULS: dict[str, Callable[..., dict[str, np.ndarray]]] = {
    "emplois": _emplois, "revenus": _revenus, "apu": _apu, "dette": _dette,
    "contributions": _contributions}


def residus(etat: Etat, precedent: Etat | None = None,
            identites: tuple[str, ...] = IDENTITES) -> dict[str, np.ndarray]:
    """Les résidus, en Md€, par identité et sous-identité, sur chaque tirage."""
    out: dict[str, np.ndarray] = {}
    for nom in identites:
        if nom not in _CALCULS:
            raise ValueError(f"identité « {nom} » inconnue ({IDENTITES})")
        calcul = _CALCULS[nom]
        out.update(calcul(etat, precedent) if nom == "dette" else calcul(etat))
    return out


def verifier(etat: Etat, precedent: Etat | None = None,
             identites: tuple[str, ...] = IDENTITES) -> dict[str, np.ndarray]:
    """Refuse l'état si une identité dépasse 1e-9 du PIB sur un tirage ; rend les résidus
    en part du PIB."""
    pib = _lire(etat, "pib", "toutes")
    if np.any(pib <= 0):
        raise IdentiteViolee(f"PIB non positif en {etat.annee} : aucun ratio n'a de sens")
    relatifs = {nom: r / pib for nom, r in residus(etat, precedent, identites).items()}
    for nom, r in relatifs.items():
        pire = int(np.argmax(np.abs(r)))
        if abs(r[pire]) > TOLERANCE:
            raise IdentiteViolee(
                f"identité « {nom} » violée en {etat.annee}, tirage {pire} : "
                f"{r[pire]:+.3e} du PIB ({r[pire] * pib[pire]:+.6f} Md€), tolérance "
                f"{TOLERANCE:g}")
    return relatifs
