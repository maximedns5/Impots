"""Les blocs du jumeau (CADRE.md §4). Lot 1 : `tendance`, `mesures`, `mesange`,
`creations`, dans cet ordre (`ordre_lot1`)."""

from __future__ import annotations

from typing import Any


def ordre_lot1(depart: Any, *, persistance: str | None, boucle: bool = True,
               creations: bool = False, variante: str | None = None) -> list[Any]:
    """Les blocs du lot 1 dans l'ordre que leurs lectures imposent. Sans `boucle`, pas
    de Mésange (la règle de dépense n'est pas la sienne, ou la boucle n'est pas
    demandée) ; avec `creations`, le canal du but 22."""
    from impots.jumeau.blocs.creations import Creations
    from impots.jumeau.blocs.mesange import Mesange
    from impots.jumeau.blocs.mesures import Mesures
    from impots.jumeau.blocs.tendance import Tendance

    blocs: list[Any] = [Tendance(depart), Mesures()]
    if boucle:
        blocs.append(Mesange(persistance, variante=variante))
    if creations:
        blocs.append(Creations())
    return blocs
