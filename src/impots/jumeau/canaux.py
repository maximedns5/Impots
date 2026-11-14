"""Le registre des canaux de Mésange que les blocs structurels portent (CADRE.md §4 bis).

Un canal est une des voies par lesquelles Mésange fait passer une impulsion au PIB et au
solde. Le bloc `mesange`, réduit, les porte tous à la fois par ses multiplicateurs ; un
bloc structurel en porte certains par ses équations et le déclare (`remplace`). Le
`Modele` refuse à la construction un canal porté deux fois (`verifier`) : c'est le double
compte (D-406). Chaque lot écrit les siens dans sa section, un nom et une description.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

CANAUX: dict[str, str] = {}

# --------------------------------------------------------------------- lot 4, ménages
CANAUX.update({
    "consommation_menages": (
        "la consommation des ménages selon leur revenu disponible, et l'épargne : la ligne "
        "« Consommation des ménages » des variantes de Mésange (bloc `consommation`)"),
    "emploi": (
        "l'emploi salarié marchand selon la valeur ajoutée et le coût du travail, le "
        "chômage : la ligne « Emploi salarié marchand » des variantes (bloc `emploi`)"),
    "salaires": (
        "la formation des salaires (WS) et la masse salariale qui en revient aux ménages "
        "et aux APU (bloc `salaires`)"),
})

#: Le bloc réduit qui porte tous les canaux du registre.
REDUIT = "mesange"


class DoubleCompte(ValueError):
    """Un canal porté par deux blocs du même modèle."""


def portes(bloc: Any) -> frozenset[str]:
    """Les canaux qu'un bloc porte : ceux qu'il déclare remplacer ; tous pour le bloc
    réduit de Mésange ; aucun pour un autre bloc."""
    remplace = getattr(bloc, "remplace", None)
    if remplace is not None:
        inconnus = sorted(set(remplace) - set(CANAUX))
        if inconnus:
            raise DoubleCompte(f"bloc « {bloc.nom} » : canaux inconnus du registre "
                               f"(jumeau/canaux.py) {inconnus}")
        return frozenset(remplace)
    if getattr(bloc, "nom", None) == REDUIT:
        return frozenset(CANAUX)
    return frozenset()


def verifier(blocs: Iterable[Any]) -> None:
    """Refuse un canal porté deux fois, en nommant le canal et les deux blocs."""
    porteur: dict[str, str] = {}
    for bloc in blocs:
        for canal in sorted(portes(bloc)):
            if canal in porteur:
                raise DoubleCompte(
                    f"canal « {canal} » porté deux fois, par « {porteur[canal]} » et par "
                    f"« {bloc.nom} » : le double compte (CADRE.md §4 bis, D-406)")
            porteur[canal] = bloc.nom
