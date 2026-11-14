"""L'état de l'économie pour une année (CADRE.md §2) : les valeurs, le masque des
absents, les contributions par origine et par mesure.

UN CHAMP NON CALCULÉ EST ABSENT, PAS NUL. L'état ne connaît que les champs qu'on y a
écrits ; lire un autre champ lève `ChampAbsent`, qui le nomme. Aucun NaN ne circule.

UNE CONTRIBUTION EST ADDITIVE ET GARDÉE À PART. Un champ additif est la somme de ses
contributions, chacune rangée sous sa clé (origine, mesure) : l'origine est le bloc qui
l'a écrite (ou « depart », « publie »), la mesure son identifiant (« » pour aucune). Un
champ non additif (un ratio, un indice de prix) a une valeur et un seul écrivain.

Chaque valeur est un tableau numpy de forme (n,), n le nombre de tirages.

LA SOMME D'UN CHAMP ADDITIF SE FAIT À LA LECTURE (D-411) : une écriture garde sa
contribution et marque le champ ; sa valeur est recalculée la première fois qu'on la lit,
dans l'ordre des contributions, comme avant (le même nombre au bit près). Les
contributions sont indexées par origine, pour que le point fixe retire celles d'un bloc
sans parcourir tout l'état. C'est de la plomberie : aucun nombre ne change.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

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

    __slots__ = ("_origines", "_sales", "annee", "contributions", "n", "publie", "valeurs")

    def __init__(self, annee: int, n: int, *, publie: bool = False) -> None:
        if n < 1:
            raise EtatError(f"n = {n} tirage(s) : au moins un")
        self.annee = int(annee)
        self.n = int(n)
        self.publie = publie
        """Vrai pour un état lu dans les tables publiées (`historique`)."""
        self.valeurs: dict[str, np.ndarray] = {}
        self.contributions: dict[str, dict[Cle, np.ndarray]] = {}
        self._sales: set[str] = set()
        """Les champs additifs dont la somme est à refaire."""
        self._origines: dict[str, set[str]] = {}
        """origine → les champs où elle a une contribution."""

    # ----------------------------------------------------------------- lecture
    def __getitem__(self, nom: str) -> np.ndarray:
        if nom in self._sales:
            self._sales.discard(nom)
            self.valeurs[nom] = _somme(self.contributions[nom].values(), self.n)
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
        if nom not in self.valeurs:
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
        if type(valeur) is np.ndarray and valeur.dtype == np.float64 \
                and valeur.shape == (self.n,):
            tableau = valeur  # ce que `np.asarray(valeur, dtype=float)` rendrait
        else:
            tableau = np.asarray(valeur, dtype=float)
            if tableau.ndim == 0:
                tableau = np.full(self.n, float(tableau))
            if tableau.shape != (self.n,):
                raise EtatError(f"« {nom} » de forme {tableau.shape}, attendu ({self.n},)")
        if not np.isfinite(tableau).all():
            raise EtatError(f"« {nom} » non fini en {self.annee} : aucun NaN ne circule")
        return tableau

    def ecrire(self, nom: str, cle: Cle, valeur: object) -> None:
        """Ajoute (ou remplace) la contribution `cle` d'un champ additif."""
        if not definition(nom).additif:
            raise EtatError(f"« {nom} » n'est pas additif : `fixer`, pas `ecrire`")
        parts = self.contributions.get(nom)
        if parts is None:
            parts = self.contributions[nom] = {}
        parts[cle] = self._tableau(valeur, nom)
        self._marquer(nom, (cle,))

    def ecrire_origine(self, origine: str, nom: str, parts: Mapping[str, object]) -> list:
        """Les contributions (origine, mesure) d'un champ additif, d'un coup ; rend les
        tableaux écrits, dont l'appelant vérifie qu'ils sont finis (`verifier_finis`) :
        le chemin rapide de `ecrire`, pour un bloc qui écrit tout un champ (D-411)."""
        contributions = self.contributions.get(nom)
        if contributions is None:
            contributions = self.contributions[nom] = {}
        if nom not in self.valeurs:
            self.valeurs[nom] = _VIDE
        self._sales.add(nom)
        champs = self._origines.get(origine)
        if champs is None:
            self._origines[origine] = {nom}
        else:
            champs.add(nom)
        n = (self.n,)
        ecrits = []
        for mesure, valeur in parts.items():
            if type(valeur) is np.ndarray and valeur.dtype == np.float64 \
                    and valeur.shape == n:
                tableau = valeur
            else:
                tableau = np.asarray(valeur, dtype=float)
                if tableau.ndim == 0:
                    tableau = np.full(self.n, float(tableau))
                if tableau.shape != n:
                    raise EtatError(f"« {nom} » de forme {tableau.shape}, attendu "
                                    f"({self.n},)")
            contributions[(origine, mesure)] = tableau
            ecrits.append(tableau)
        return ecrits

    def verifier_finis(self, noms: Sequence[str], tableaux: Sequence[list]) -> None:
        """Aucun NaN ne circule : les tableaux écrits par `ecrire_origine`, d'un seul
        test ; le premier champ fautif nommé."""
        tous = [t for liste in tableaux for t in liste]
        if tous and not np.isfinite(np.concatenate(tous)).all():
            for nom, liste in zip(noms, tableaux, strict=True):
                if any(not np.isfinite(t).all() for t in liste):
                    raise EtatError(f"« {nom} » non fini en {self.annee} : aucun NaN ne "
                                    f"circule")

    def _marquer(self, nom: str, cles: Iterable[Cle]) -> None:
        if nom not in self.valeurs:
            self.valeurs[nom] = _VIDE
        self._sales.add(nom)
        for origine, _ in cles:
            champs = self._origines.get(origine)
            if champs is None:
                self._origines[origine] = {nom}
            else:
                champs.add(nom)

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
        for nom in self._origines.pop(origine, ()):
            parts = self.contributions[nom]
            for c in [c for c in parts if c[0] == origine]:
                del parts[c]
            self._sales.add(nom)

    def fixer(self, nom: str, valeur: object) -> None:
        """La valeur d'un champ non additif."""
        if definition(nom).additif:
            raise EtatError(f"« {nom} » est additif : il s'écrit par contributions")
        self.valeurs[nom] = self._tableau(valeur, nom)

    def copier_contributions(self, nom: str, source: Mapping[Cle, np.ndarray]) -> None:
        ancien = self.contributions.get(nom, {})
        for origine in {c[0] for c in ancien}:
            self._origines.get(origine, set()).discard(nom)
        self.contributions[nom] = {c: v for c, v in source.items()}
        self._marquer(nom, self.contributions[nom])


#: La valeur d'un champ additif écrit, que sa première lecture calculera.
_VIDE = np.zeros(0)


def _somme(valeurs: Iterable[np.ndarray], n: int) -> np.ndarray:
    total = np.zeros(n)
    for v in valeurs:
        total = total + v
    return total
