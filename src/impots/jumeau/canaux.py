"""Le registre des canaux (CADRE.md §4 bis, D-406, D-411) : ce par quoi une mesure agit.

UN CANAL SE PORTE PAR INSTRUMENT (D-411). Le double compte se juge sur la paire (canal,
instrument) : le bloc réduit `mesange` porte par ses multiplicateurs les canaux de Mésange
(`DE_MESANGE`), mais pour ses seuls instruments, ceux dont il publie une variante
(`INSTRUMENTS_MESANGE`, les clés de `macro.mesange.VARIANTS`). Un bloc structurel porte
les siens par ses équations, pour les instruments qu'il lit (`instruments`, {canal :
instruments}) ou pour tous (`TOUS`, le défaut : un bloc de la demande répond à tout ce
qui la déplace). Chaque bloc déclare ceux qu'il porte (`porte`) et ceux de Mésange qu'il
porte à sa place (`remplace`) ; le `Modele` refuse à la construction une paire portée deux
fois, en nommant le canal, l'instrument et les deux blocs (`verifier`). Ainsi
l'investissement par l'IS ne se heurte pas à `mesange`, qui n'a pas de variante d'IS ; il
se heurterait à lui s'il lisait les cotisations employeurs.

Le format est un dict nom → description, une section par lot ; un canal que Mésange porte
s'inscrit aussi dans `DE_MESANGE`. Un nom absent du registre est refusé.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from impots.macro.mesange import VARIANTS


class CanalError(ValueError):
    """Un canal inconnu, ou porté deux fois."""


class CanalInconnu(CanalError):
    """Un canal que le registre ne connaît pas."""


class DoubleCompte(CanalError):
    """Une paire (canal, instrument) portée par deux blocs du même modèle."""


#: Un bloc qui porte un canal pour tout instrument.
TOUS = "*"

#: Les blocs réduits : leurs multiplicateurs n'impriment que la ligne du PIB, et ils
#: l'écrivent eux-mêmes (D-405). Le PIB de tout autre bloc qui porte un canal, un bloc
#: structurel, est fermé par le cadre, comme la somme de ses emplois (D-411).
REDUITS = frozenset({"mesange", "creations"})


def structurel(bloc: Any) -> bool:
    """Un bloc structurel : il porte un canal, et n'est pas un bloc réduit."""
    return bloc.nom not in REDUITS and bool(declares(bloc))


#: Les instruments de Mésange : ceux dont il publie une variante (G2017-04, §4).
INSTRUMENTS_MESANGE: tuple[str, ...] = tuple(VARIANTS)

#: Les instruments que Mésange n'a pas, que lisent les blocs du lot 2.
AUTRES_INSTRUMENTS: dict[str, str] = {
    "impot_societes": "l'IS, sa contribution sociale et la CEBGE (D51)",
    "impots_production_entreprises": "la CVAE et la C3S (D29)",
    "capital_menages": "le PFU et les prélèvements sociaux du capital (D5)",
}
INSTRUMENTS: frozenset[str] = frozenset({*INSTRUMENTS_MESANGE, *AUTRES_INSTRUMENTS})

#: Les signaux du lot 2 (`champs.SIGNAUX_ENTREPRISES`) et les instruments qu'ils portent :
#: les cotisations patronales sont celles des deux variantes de Mésange.
DES_SIGNAUX: dict[str, tuple[str, ...]] = {
    "prelevements_is": ("impot_societes",),
    "prelevements_production": ("impots_production_entreprises",),
    "cotisations_patronales": ("cotisations_employeurs", "cotisations_employeurs_ciblees"),
    "prelevements_capital_menages": ("capital_menages",),
}


def des_signaux(signaux: Iterable[str]) -> tuple[str, ...]:
    """Les instruments que portent des signaux du lot 2."""
    return tuple(sorted({i for s in signaux for i in DES_SIGNAUX[s]}))


CANAUX: dict[str, str] = {}

#: Les canaux que les multiplicateurs de Mésange portent (le bloc réduit `mesange`). La
#: démographie des entreprises et l'implantation n'y sont pas : Mésange n'a ni stock de
#: sociétés ni capital étranger. Le canal des créations (lot 1, D-401) lit donc les
#: cotisations patronales à côté de la variante cotisations de Mésange sans double
#: compte : ce n'est pas le même canal (D-411, comme D-401).
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

# --------------------------------------------------------------------- lot 4 (D-409)
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
DE_MESANGE.update({"consommation_menages", "emploi", "salaires"})

# --------------------------------------------------------------------- jonction (D-411)
CANAUX.update({
    "demande_publique": (
        "les achats des APU d'une mesure dans les emplois du PIB : les variantes de dépense "
        "de Mésange (investissement public, dépense publique), ou le bloc comptable "
        "`demande_publique`"),
})
DE_MESANGE.add("demande_publique")

# --------------------------------------------------------------------- mode structurel (D-414)
CANAUX.update({
    "investissement_accelerateur": (
        "l'investissement des entreprises selon la valeur ajoutée, l'effet accélérateur et "
        "l'indexation de long terme : l'équation d'investissement de Mésange, p. 44 (bloc "
        "`investissement`, mode structurel)"),
    "prix_production": (
        "les prix de production et de consommation selon les coûts salariaux unitaires et "
        "la demande, et leur retour sur les salaires, la consommation réelle et la "
        "compétitivité : la boucle prix-salaires de Mésange (bloc `commerce`, mode "
        "structurel)"),
    "recettes_induites_profits": (
        "l'impôt sur les sociétés sur les profits que l'activité induite fait (bloc "
        "`recettes_induites`)"),
})
DE_MESANGE.update({"investissement_accelerateur", "prix_production",
                   "recettes_induites_profits"})

# --------------------------------------------------------------------- emploi public (D-418)
CANAUX.update({
    "emploi_public": (
        "les emplois publics que font les rémunérations des APU d'une mesure, leur revenu "
        "aux ménages et leurs prélèvements : la variante de dépense publique de Mésange, "
        "la moitié de ses rémunérations en emplois (p. 106, note 75), ou le bloc "
        "`emploi_public`"),
})
DE_MESANGE.add("emploi_public")


def declares(bloc: Any) -> tuple[tuple[str, str], ...]:
    """Les paires (canal, instrument) qu'un bloc porte : les siennes et celles de Mésange
    qu'il remplace ; `mesange`, ses canaux pour ses seuls instruments. Refusés : un canal
    inconnu du registre, un `remplace` qui n'est pas un canal de Mésange, un instrument
    inconnu."""
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
    instruments: Mapping[str, Iterable[str]] = getattr(bloc, "instruments", None) or {}
    hors = sorted(set(instruments) - set(porte + remplace))
    if hors:
        raise CanalInconnu(f"bloc « {bloc.nom} » : des instruments pour {hors}, qu'il ne "
                           f"porte pas")
    paires: list[tuple[str, str]] = []
    for canal in (*porte, *remplace):
        liste = tuple(instruments.get(canal, (TOUS,)))
        faux = sorted(set(liste) - INSTRUMENTS - {TOUS})
        if faux:
            raise CanalInconnu(f"bloc « {bloc.nom} », canal « {canal} » : instruments "
                               f"{faux} inconnus (jumeau/canaux.py)")
        paires.extend((canal, i) for i in liste)
    return tuple(paires)


def _rencontre(a: str, b: str) -> bool:
    return a == b or TOUS in (a, b)


def verifier(blocs: Iterable[Any]) -> dict[tuple[str, str], str]:
    """{(canal, instrument): bloc} ; refuse un canal inconnu, ou une paire portée par deux
    blocs (un bloc qui porte un canal pour `TOUS` les instruments rencontre chaque
    instrument de ce canal)."""
    porteurs: dict[tuple[str, str], str] = {}
    for bloc in blocs:
        for canal, instrument in declares(bloc):
            for (c, i), autre in porteurs.items():
                if c == canal and _rencontre(i, instrument):
                    commun = instrument if i == TOUS else i
                    raise DoubleCompte(
                        f"canal « {canal} » porté deux fois, pour l'instrument "
                        f"« {commun} », par « {autre} » et « {bloc.nom} » : c'est le "
                        f"double compte (CADRE.md §4 bis, D-411)")
            porteurs[(canal, instrument)] = bloc.nom
    return porteurs
