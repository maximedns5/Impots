"""Les blocs du jumeau (CADRE.md §4). Lot 1 : `tendance`, `mesures`, `mesange`,
`creations`, dans cet ordre (`ordre_lot1`). Lot 2, les entreprises (D-407) :
`chocs_entreprises`, `naissances`, `fermetures`, `productivite`, `investissement`,
`implantation` (`entreprises.ordre_lot2`). Lot 3 : `commerce`. Lot 4 : `consommation`,
`emploi`, `salaires`. Le modèle structurel complet, sans Mésange : `ordre_structurel`
(D-411)."""

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


#: La boucle simultanée du modèle structurel : l'investissement suit la valeur ajoutée
#: (l'accélérateur), la consommation fait le PIB, le PIB l'emploi, l'emploi et les
#: salaires le revenu, la demande les importations, qui retranchent au PIB que la
#: consommation lit, et le commerce fait les prix que les salaires, la consommation et
#: l'emploi lisent (la boucle prix-salaires) (D-411, D-414).
BOUCLE_STRUCTURELLE = ("investissement", "consommation", "emploi", "salaires", "commerce")


def ordre_structurel(depart: Any, population: Any, cellules: Any, *,
                     entreprises: Any | None = None, menages: Any | None = None,
                     commerce: Any | None = None) -> tuple[list[Any], list[tuple[str, ...]]]:
    """Le modèle structurel complet (D-411, complété par D-414) : `tendance` (qui laisse au
    commerce les prix des échanges et de la consommation), `mesures`, la demande publique,
    les blocs des entreprises (lot 2), puis la boucle de l'investissement (l'accélérateur),
    des ménages (lot 4) et du commerce (lot 3, la boucle prix-salaires), et les recettes
    induites sur les profits. Sans `mesange` : chaque canal est porté une fois, par une
    équation. Rend les blocs et leur boucle. Un `commerce` donné doit porter la boucle
    prix-salaires (`Commerce(boucle_prix=...)`)."""
    from impots.jumeau.blocs.commerce import Commerce
    from impots.jumeau.blocs.demande_publique import DemandePublique
    from impots.jumeau.blocs.demographie import Fermetures, Naissances, Productivite
    from impots.jumeau.blocs.entreprises import ChocsEntreprises
    from impots.jumeau.blocs.entreprises import charger as charger_entreprises
    from impots.jumeau.blocs.implantation import Implantation
    from impots.jumeau.blocs.investissement import Investissement
    from impots.jumeau.blocs.menages import blocs_menages
    from impots.jumeau.blocs.menages import charger as charger_menages
    from impots.jumeau.blocs.mesures import Mesures
    from impots.jumeau.blocs.recettes_induites import RecettesInduites
    from impots.jumeau.blocs.tendance import Tendance

    p = entreprises if entreprises is not None else charger_entreprises()
    pm = menages if menages is not None else charger_menages()
    du_menage, _ = blocs_menages(cellules, pm, prix=True)
    commerce = commerce if commerce is not None else Commerce(
        boucle_prix=pm.part_marchande)
    if getattr(commerce, "boucle", None) is None:
        raise ValueError("le modèle structurel complet lit la boucle prix-salaires : "
                         "`Commerce(boucle_prix=...)` (D-414)")
    blocs: list[Any] = [
        Tendance(depart, laisse=commerce.prix), Mesures(), DemandePublique(),
        ChocsEntreprises(), Naissances(population, p), Fermetures(population, p),
        Productivite(population, p), Implantation(p),
        Investissement(p, accelerateur=True, prix=True), *du_menage, commerce,
        RecettesInduites()]
    return blocs, [BOUCLE_STRUCTURELLE]
