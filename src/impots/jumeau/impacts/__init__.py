"""Ce qu'une mesure change pour les gens : l'interface commune des dimensions (but 29, D-590).

Chaque dimension (le pouvoir d'achat, l'entente, le moral, la productivité…) s'inscrit
ici par `inscrire` : une fonction qui lit la trajectoire de la variante, celle de la
référence, l'état de départ et les cellules de ménages, et rend une `Dimension`. Le
tableau (`tableau`, l'API et la page « Ce que ça change ») ne connaît que cette
interface : il appelle `calculer` et montre chaque dimension avec sa bande, sa source et
son statut.

Ce module tourne dans le navigateur (D-415) : numpy seulement, ni polars ni la
population. Une dimension qui a besoin de la population passe par ce que les cellules
(`jumeau.cellules`) ou les entrées commitées en portent.

Le statut dit ce qu'on peut croire : « jugé » (un chiffrage officiel fait après coup,
préenregistré, l'a confrontée : la D-entrée est dans `juge`), « sourcé, non jugé » (chaque
coefficient a sa source publiée, aucun juge aveugle connu), « illustratif » (un ordre de
grandeur dont la chaîne n'est pas entièrement sourcée). Une dimension sans juge n'est
jamais présentée comme une prévision vérifiée.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

STATUTS = ("jugé", "sourcé, non jugé", "illustratif")


@dataclass(frozen=True)
class Source:
    """Une source publiée : le document, la page ou le tableau, et ce qu'on en tire."""

    document: str
    lieu: str
    valeur: str


@dataclass(frozen=True)
class Indicateur:
    """Un nombre de la dimension, année par année, avec sa bande.

    `valeurs`, `bas` et `haut` ont la forme (années,) ; `par_groupe`, s'il est là,
    associe à chaque groupe (un décile, un cas type, un territoire) une série de la même
    forme. Le sens dit ce qui est mieux : +1 si plus haut est mieux, −1 sinon, 0 si
    l'indicateur n'a pas de sens moral (une part, un écart).
    """

    cle: str
    libelle: str
    unite: str
    valeurs: np.ndarray
    bas: np.ndarray | None = None
    haut: np.ndarray | None = None
    par_groupe: Mapping[str, np.ndarray] | None = None
    sens: int = 1


@dataclass(frozen=True)
class Dimension:
    cle: str
    titre: str
    question: str
    """La question, en français simple, à laquelle la dimension répond."""
    annees: tuple[int, ...]
    indicateurs: tuple[Indicateur, ...]
    statut: str
    sources: tuple[Source, ...]
    limites: tuple[str, ...] = ()
    juge: str | None = None
    """La D-entrée du jugement, si la dimension est jugée."""
    notes: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.statut not in STATUTS:
            raise ValueError(f"statut inconnu : {self.statut!r}")
        if self.statut == "jugé" and not self.juge:
            raise ValueError(f"{self.cle} : une dimension jugée nomme sa D-entrée")
        if not self.sources:
            raise ValueError(f"{self.cle} : une dimension sans source")


Calcul = Callable[..., Dimension]
"""calcul(variante, reference, depart, cellules, **options) -> Dimension."""

_REGISTRE: dict[str, Calcul] = {}


def inscrire(cle: str) -> Callable[[Calcul], Calcul]:
    def deco(f: Calcul) -> Calcul:
        if cle in _REGISTRE and _REGISTRE[cle] is not f:
            raise ValueError(f"dimension déjà inscrite : {cle}")
        _REGISTRE[cle] = f
        return f

    return deco


def dimensions() -> tuple[str, ...]:
    return tuple(_REGISTRE)


def calculer(variante: Any, reference: Any, depart: Any, cellules: Any,
             cles: Sequence[str] | None = None, **options: Any) -> dict[str, Dimension]:
    """Toutes les dimensions inscrites (ou celles de `cles`), dans l'ordre d'inscription."""
    choisies = list(_REGISTRE) if cles is None else list(cles)
    return {c: _REGISTRE[c](variante, reference, depart, cellules, **options)
            for c in choisies}


def vers_dict(d: Dimension) -> dict[str, Any]:
    """La forme JSON d'une dimension, pour l'API et la page."""

    def liste(a: np.ndarray | None) -> list[float] | None:
        return None if a is None else [float(x) for x in np.asarray(a).ravel()]

    return {
        "cle": d.cle, "titre": d.titre, "question": d.question,
        "annees": list(d.annees), "statut": d.statut, "juge": d.juge,
        "sources": [s.__dict__ for s in d.sources], "limites": list(d.limites),
        "indicateurs": [{
            "cle": i.cle, "libelle": i.libelle, "unite": i.unite, "sens": i.sens,
            "valeurs": liste(i.valeurs), "bas": liste(i.bas), "haut": liste(i.haut),
            "par_groupe": None if i.par_groupe is None
            else {g: liste(v) for g, v in i.par_groupe.items()},
        } for i in d.indicateurs],
        "notes": dict(d.notes),
    }
