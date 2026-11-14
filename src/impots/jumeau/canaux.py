"""Le registre des canaux de Mésange (CADRE.md §4 bis, D-406) : un canal, un porteur.

Le bloc réduit `mesange` porte TOUS les canaux du registre par ses multiplicateurs, qui
ne se décomposent pas. Un bloc structurel déclare ceux qu'il porte à sa place
(`remplace`, des noms de ce registre). Le `Modele` refuse à la construction un canal porté
deux fois : c'est le double compte (`portes`).

Chaque lot écrit sa section : nom → description, rien d'autre.
"""

from __future__ import annotations

from typing import Any

CANAUX: dict[str, str] = {}

#: Les blocs réduits, qui portent tous les canaux du registre.
REDUITS: dict[str, str] = {
    "mesange": "les multiplicateurs par instrument de Mésange (G2017-04) portent chaque "
               "canal à la fois : ils ne se décomposent pas"}


class CanalInconnu(KeyError):
    """Un canal que le registre ne connaît pas."""


# --------------------------------------------------------------------- lot 3, commerce
CANAUX.update({
    "exportations": "le volume des exportations : demande mondiale adressée à la France "
                    "et compétitivité-prix (Mésange G2017-04, §3.6.1)",
    "importations": "le volume des importations : demande intérieure et compétitivité-"
                    "prix intérieure (Mésange G2017-04, §3.6.2)",
    "prix_echanges": "les prix des exportations et des importations, ancrés sur les prix "
                     "de production et les prix étrangers (Mésange G2017-04, §3.6.3-4)",
})


def portes(bloc: Any) -> tuple[str, ...]:
    """Les canaux qu'un bloc porte : tous pour un bloc réduit, ceux de son `remplace`
    sinon ; un nom inconnu du registre est refusé."""
    if bloc.nom in REDUITS:
        return tuple(CANAUX)
    remplace = tuple(getattr(bloc, "remplace", ()))
    inconnus = sorted(set(remplace) - set(CANAUX))
    if inconnus:
        raise CanalInconnu(f"bloc « {bloc.nom} » : canaux {inconnus} inconnus du registre "
                           f"(jumeau/canaux.py)")
    return remplace
