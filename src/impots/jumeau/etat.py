"""L'état de l'économie pour une année (CADRE.md §2) : les valeurs, le masque des
absents, les contributions par origine et par mesure.

UN CHAMP NON CALCULÉ EST ABSENT, PAS NUL. L'état ne connaît que les champs qu'on y a
écrits ; lire un autre champ lève `ChampAbsent`, qui le nomme. Aucun NaN ne circule.

UNE CONTRIBUTION EST ADDITIVE ET GARDÉE À PART. Un champ additif est la somme de ses
contributions, chacune rangée sous sa clé (origine, mesure) : l'origine est le bloc qui
l'a écrite (ou « depart », « publie »), la mesure son identifiant (« » pour aucune). Un
champ non additif (un ratio, un indice de prix) a une valeur et un seul écrivain.

Chaque valeur est un tableau numpy de forme (n,), n le nombre de tirages.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

import numpy as np

from impots.jumeau.champs import champ as definition

Cle = tuple[str, str]
"""(origine, mesure)."""


class ChampAbsent(KeyError):
    """Un champ que personne n'a écrit, lu comme s'il existait."""

    def __str__(self) -> str:
        return str(self.args[0]) if self.args else "champ absent"


class EtatError(ValueError):
    """Une écriture que l'état refuse."""


class Etat:
    """Une année de l'économie, sur n tirages."""

    __slots__ = ("annee", "contributions", "n", "publie", "valeurs")

    def __init__(self, annee: int, n: int, *, publie: bool = False) -> None:
        if n < 1:
            raise EtatError(f"n = {n} tirage(s) : au moins un")
        self.annee = int(annee)
        self.n = int(n)
        self.publie = publie
        """Vrai pour un état lu dans les tables publiées (`historique`)."""
        self.valeurs: dict[str, np.ndarray] = {}
        self.contributions: dict[str, dict[Cle, np.ndarray]] = {}

    # ----------------------------------------------------------------- lecture
    def __getitem__(self, nom: str) -> np.ndarray:
        try:
            return self.valeurs[nom]
        except KeyError:
            definition(nom)
            raise ChampAbsent(f"champ « {nom} » absent en {self.annee} : personne ne l'a "
                              f"écrit, et il n'est pas nul") from None

    def present(self, nom: str) -> bool:
        return nom in self.valeurs

    def de(self, nom: str) -> dict[Cle, np.ndarray]:
        """Les contributions d'un champ additif, par (origine, mesure)."""
        self[nom]
        if not definition(nom).additif:
            raise EtatError(f"« {nom} » n'est pas additif : il n'a pas de contributions")
        return self.contributions[nom]

    def par_mesure(self, nom: str) -> dict[str, np.ndarray]:
        """Les contributions d'un champ sommées par mesure, toutes origines."""
        out: dict[str, np.ndarray] = {}
        for (_, mesure), valeur in self.de(nom).items():
            out[mesure] = out[mesure] + valeur if mesure in out else valeur
        return out

    def champs(self) -> tuple[str, ...]:
        return tuple(self.valeurs)

    # ----------------------------------------------------------------- écriture
    def _tableau(self, valeur: object, nom: str) -> np.ndarray:
        tableau = np.asarray(valeur, dtype=float)
        if tableau.ndim == 0:
            tableau = np.full(self.n, float(tableau))
        if tableau.shape != (self.n,):
            raise EtatError(f"« {nom} » de forme {tableau.shape}, attendu ({self.n},)")
        if not np.all(np.isfinite(tableau)):
            raise EtatError(f"« {nom} » non fini en {self.annee} : aucun NaN ne circule")
        return tableau

    def ecrire(self, nom: str, cle: Cle, valeur: object) -> None:
        """Ajoute (ou remplace) la contribution `cle` d'un champ additif."""
        if not definition(nom).additif:
            raise EtatError(f"« {nom} » n'est pas additif : `fixer`, pas `ecrire`")
        parts = self.contributions.setdefault(nom, {})
        parts[cle] = self._tableau(valeur, nom)
        self.valeurs[nom] = _somme(parts.values(), self.n)

    def declarer(self, nom: str) -> None:
        """Rend présent un champ additif qu'un bloc écrit sans contribution cette année :
        calculé nul, pas absent (le bloc a tourné)."""
        if nom not in self.valeurs:
            if not definition(nom).additif:
                raise EtatError(f"« {nom} » n'est pas additif")
            self.contributions[nom] = {}
            self.valeurs[nom] = np.zeros(self.n)

    def retirer(self, origine: str) -> None:
        """Retire toutes les contributions d'une origine (une itération du point fixe)."""
        for nom, parts in self.contributions.items():
            cles = [c for c in parts if c[0] == origine]
            if cles:
                for c in cles:
                    del parts[c]
                self.valeurs[nom] = _somme(parts.values(), self.n)

    def fixer(self, nom: str, valeur: object) -> None:
        """La valeur d'un champ non additif."""
        if definition(nom).additif:
            raise EtatError(f"« {nom} » est additif : il s'écrit par contributions")
        self.valeurs[nom] = self._tableau(valeur, nom)

    def copier_contributions(self, nom: str, source: Mapping[Cle, np.ndarray]) -> None:
        self.contributions[nom] = {c: v for c, v in source.items()}
        self.valeurs[nom] = _somme(self.contributions[nom].values(), self.n)


def _somme(valeurs: Iterable[np.ndarray], n: int) -> np.ndarray:
    total = np.zeros(n)
    for v in valeurs:
        total = total + v
    return total
