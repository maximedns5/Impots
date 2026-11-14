"""Le registre des canaux (CADRE.md §4 bis, D-406) : ce par quoi une mesure agit.

Un canal se porte une seule fois. Le bloc réduit `mesange` porte par ses multiplicateurs
des canaux qu'un bloc structurel porte par ses équations : chaque bloc déclare ceux qu'il
porte (`porte`) et ceux de Mésange qu'il porte à sa place (`remplace`), et le `Modele`
refuse à la construction un canal porté deux fois, en le nommant avec les deux blocs.

Le format est un dict nom → description, une section par lot. Un nom absent du registre
est refusé.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class CanalError(ValueError):
    """Un canal inconnu, ou porté deux fois."""


CANAUX: dict[str, str] = {}

# --------------------------------------------------------------------- lot 2 (D-407)
CANAUX.update({
    "creations_entreprises": (
        "le taux d'entrée des sociétés selon les prélèvements sur les entreprises et le "
        "capital (Da Rin, Di Giacomo et Sembenelli 2011) : le bloc `creations` du lot 1, "
        "ou `naissances` du lot 2"),
    "fermetures_entreprises": (
        "le hasard de sortie des sociétés installées selon leur marge après impôt "
        "(`fermetures`)"),
    "productivite_demographie": (
        "la valeur ajoutée des entrants et des sortants à la marge, à leur productivité "
        "relative, sur le PIB potentiel (`productivite`)"),
    "investissement_cout_du_capital": (
        "l'investissement des entreprises selon le coût d'usage du capital, dont sa "
        "fiscalité : l'équation d'investissement de Mésange, que ses multiplicateurs "
        "portent pour ses instruments (`mesange`), ou le bloc `investissement`"),
    "implantation": (
        "la localisation du capital des multinationales selon le taux effectif moyen "
        "d'imposition (`implantation`)"),
})


def declares(bloc: Any) -> tuple[str, ...]:
    """Les canaux qu'un bloc porte, les siens et ceux de Mésange qu'il remplace."""
    return (*getattr(bloc, "porte", ()), *getattr(bloc, "remplace", ()))


def verifier(blocs: Iterable[Any]) -> dict[str, str]:
    """{canal: bloc} ; refuse un canal inconnu ou porté par deux blocs."""
    porteurs: dict[str, str] = {}
    for bloc in blocs:
        for canal in declares(bloc):
            if canal not in CANAUX:
                raise CanalError(f"bloc « {bloc.nom} » : canal « {canal} » inconnu du "
                                 f"registre (jumeau/canaux.py)")
            if canal in porteurs:
                raise CanalError(f"canal « {canal} » porté deux fois, par "
                                 f"« {porteurs[canal]} » et « {bloc.nom} » : c'est le "
                                 f"double compte (CADRE.md §4 bis)")
            porteurs[canal] = bloc.nom
    return porteurs
