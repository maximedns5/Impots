"""Le registre des canaux (CADRE.md §4 bis, D-406) : ce par quoi une mesure agit.

Un canal se porte une seule fois. Le bloc réduit `mesange` porte par ses multiplicateurs
les canaux de Mésange (`DE_MESANGE`) ; un bloc structurel porte les siens par ses
équations. Chaque bloc déclare ceux qu'il porte (`porte`) et ceux de Mésange qu'il porte
à sa place (`remplace`), et le `Modele` refuse à la construction un canal porté deux fois,
en le nommant avec ses deux blocs (`verifier`) : c'est le double compte.

Le format est un dict nom → description, une section par lot ; un canal que Mésange porte
s'inscrit aussi dans `DE_MESANGE`. Un nom absent du registre est refusé.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class CanalError(ValueError):
    """Un canal inconnu, ou porté deux fois."""


class CanalInconnu(CanalError):
    """Un canal que le registre ne connaît pas."""


class DoubleCompte(CanalError):
    """Un canal porté par deux blocs du même modèle."""


CANAUX: dict[str, str] = {}

#: Les canaux que les multiplicateurs de Mésange portent (le bloc réduit `mesange`). La
#: démographie des entreprises et l'implantation n'y sont pas : Mésange n'a ni stock de
#: sociétés ni capital étranger.
DE_MESANGE: set[str] = set()

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
DE_MESANGE.add("investissement_cout_du_capital")

# --------------------------------------------------------------------- lot 3 (D-408)
CANAUX.update({
    "exportations": "le volume des exportations : demande mondiale adressée à la France "
                    "et compétitivité-prix (Mésange G2017-04, §3.6.1)",
    "importations": "le volume des importations : demande intérieure et compétitivité-"
                    "prix intérieure (Mésange G2017-04, §3.6.2)",
    "prix_echanges": "les prix des exportations et des importations, ancrés sur les prix "
                     "de production et les prix étrangers (Mésange G2017-04, §3.6.3-4)",
})
DE_MESANGE.update({"exportations", "importations", "prix_echanges"})


def declares(bloc: Any) -> tuple[str, ...]:
    """Les canaux qu'un bloc porte, les siens et ceux de Mésange qu'il remplace ; un nom
    inconnu du registre, ou un `remplace` qui n'est pas un canal de Mésange, refusé."""
    porte = tuple(getattr(bloc, "porte", ()))
    remplace = tuple(getattr(bloc, "remplace", ()))
    inconnus = sorted(set(porte + remplace) - set(CANAUX))
    if inconnus:
        raise CanalInconnu(f"bloc « {bloc.nom} » : canaux {inconnus} inconnus du "
                           f"registre (jumeau/canaux.py)")
    etrangers = sorted(set(remplace) - DE_MESANGE)
    if etrangers:
        raise CanalInconnu(f"bloc « {bloc.nom} » : {etrangers} remplacés, mais Mésange ne "
                           f"les porte pas (jumeau/canaux.py, DE_MESANGE)")
    return (*porte, *remplace)


def verifier(blocs: Iterable[Any]) -> dict[str, str]:
    """{canal: bloc} ; refuse un canal inconnu ou porté par deux blocs."""
    porteurs: dict[str, str] = {}
    for bloc in blocs:
        for canal in declares(bloc):
            if canal in porteurs:
                raise DoubleCompte(f"canal « {canal} » porté deux fois, par "
                                   f"« {porteurs[canal]} » et « {bloc.nom} » : c'est le "
                                   f"double compte (CADRE.md §4 bis)")
            porteurs[canal] = bloc.nom
    return porteurs
