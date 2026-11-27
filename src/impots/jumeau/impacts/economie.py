"""La dimension « économie » (but 29, volet `tableau`, D-606) : ce que la mesure fait à
l'activité, à l'emploi, au chômage, aux prix et à la rémunération réelle par salarié.

Les nombres sont ceux que la page du jumeau montre déjà, lus dans le même état : le PIB
en % de celui de la référence (`navigateur._series`), l'emploi intérieur et les chômeurs
BIT en milliers (`_series`, `_comptes`) ; s'y ajoutent deux champs que le mode
structurel écrit (D-414) : l'écart du prix de la consommation des ménages (l'équation
(PC) de Mésange) et la rémunération moyenne par salarié (D1 par tête, D-412), qu'on
déflate par ce prix pour la dire réelle.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from impots.jumeau.impacts import Dimension, Indicateur, Source, inscrire
from impots.jumeau.impacts._commun import (
    ecart,
    limite_bande,
    niveaux,
    serie,
    statut,
    thetas_sans_source,
)

CLE = "economie"

SOURCES = (
    Source("Insee, comptes nationaux annuels base 2020, t. 1.101, 1.105, 6.208, 6.210 ; "
           "Eurostat une_rt_a", "l'état publié de 2025 (D-412)",
           "le départ : PIB, rémunérations, emploi, chômeurs, salaire moyen"),
    Source("Insee, Mésange (G2017-04)", "p. 22 à 24, 44, 70 à 72 ; CADRE.md, D-414",
           "l'accélérateur, la boucle prix-salaires, le prix de la consommation"),
    Source("Les blocs des ménages du jumeau", "D-409, `jumeau/parametres/menages.yaml`",
           "l'emploi, les salaires et la consommation par cellule de ménages"),
)


def _pib(reference: Any, variante: Any) -> np.ndarray | None:
    r, v = niveaux(reference, "pib"), niveaux(variante, "pib")
    return None if r is None or v is None else 100.0 * (v / r - 1.0)


def _pib_volume(reference: Any, variante: Any) -> np.ndarray | None:
    """Le PIB en volume (D-639) : l'écart du PIB moins l'effet des prix du PIB que le
    jumeau écrit (`effet_prix_pib`, Md€), sur le PIB de la référence ; la formule du
    socle de la productivité (`impacts/productivite.socle`)."""
    r, v = niveaux(reference, "pib"), niveaux(variante, "pib")
    dp = ecart(reference, variante, "effet_prix_pib")
    if r is None or v is None or dp is None:
        return None
    return 100.0 * (v - r - dp) / r


def _sans_prix(reference: Any, variante: Any) -> bool:
    """Aucun état ne porte l'effet des prix du PIB : la chaîne des études (le mode
    réduit, D-670), où l'écart du PIB est celui des variantes de Mésange, « PIB en
    volume » (G2017-04, la première ligne de chaque tableau de variante), et du canal
    des créations (une valeur ajoutée, sans prix). Aucun prix n'y bouge : l'écart est
    un volume, et non une valeur."""
    return not any(e.present("effet_prix_pib") for e in (*reference, *variante))


def _prix(reference: Any, variante: Any) -> np.ndarray | None:
    e = ecart(reference, variante, "ecart_prix_consommation")
    return None if e is None else 100.0 * e


def _salaire_reel(reference: Any, variante: Any) -> np.ndarray | None:
    r, v = niveaux(reference, "salaire_moyen"), niveaux(variante, "salaire_moyen")
    p = ecart(reference, variante, "ecart_prix_consommation")
    if r is None or v is None or p is None:
        return None
    return 100.0 * ((v / r) / (1.0 + p) - 1.0)


def _bas(libelles: list[str]) -> str:
    return ", ".join(x if x.startswith("PIB") else x[:1].lower() + x[1:] for x in libelles)


@inscrire(CLE)
def economie(variante: Any, reference: Any, depart: Any, cellules: Any,
             **options: Any) -> Dimension:
    indicateurs = []
    # Sans prix (la chaîne des études, D-670), l'écart du PIB est un volume : il prend
    # la place et le nom du PIB en volume, et il n'y a pas de PIB en valeur à côté.
    # Avant D-670, le même nombre s'y disait « PIB en valeur (nominal) », sans sens.
    sans_prix = _sans_prix(reference, variante)
    pibs = ((("pib_volume", "PIB en volume", "% du PIB sans la mesure", 1, _pib),)
            if sans_prix else
            # En tête le PIB en volume, l'activité (D-639) ; le PIB en valeur à côté,
            # sans sens : il monte aussi quand seuls les prix montent.
            (("pib_volume", "PIB en volume", "% du PIB sans la mesure", 1, _pib_volume),
             ("pib", "PIB en valeur (nominal)", "% du PIB sans la mesure", 0, _pib)))
    for cle, libelle, unite, sens, f in (
            *pibs,
            ("emploi", "Emploi intérieur", "milliers d'emplois", 1,
             lambda r, v: ecart(r, v, "emploi_total")),
            ("chomage", "Chômeurs (BIT)", "milliers de personnes", -1,
             lambda r, v: ecart(r, v, "chomage")),
            ("prix", "Prix de la consommation des ménages", "%", 0, _prix),
            ("salaire_reel", "Rémunération réelle moyenne par salarié", "%", 1,
             _salaire_reel)):
        s = serie(f, options, reference, variante)
        if s is not None:
            indicateurs.append(Indicateur(cle, libelle, unite, *s, sens=sens))
    statut_, limites = statut(options)
    limites += [
        "Écarts à la trajectoire sans la mesure, pas des niveaux.",
        ("Le PIB est celui que Mésange publie, en volume (la ligne « PIB en volume » de "
         "ses variantes, G2017-04), plus le canal des créations : la chaîne des études "
         "ne fait bouger aucun prix, il n'y a pas de PIB en valeur à part (D-670)."
         if sans_prix else
         "Le PIB en volume dit l'activité ; le PIB en valeur (celui de la page du jumeau) "
         "y ajoute l'écart des prix du PIB : il n'est ni mieux ni moins bien en soi "
         "(D-639)."),
        "La rémunération par salarié est D1 par tête : cotisations des employeurs "
        "comprises. Une mesure qui baisse ces cotisations la fait baisser alors que le "
        "salaire net monte ; le net des ménages se lit dans le pouvoir d'achat.",
        "Le prix est celui de la consommation des ménages dans le jumeau (la boucle "
        "prix-salaires de Mésange, D-414), pas l'indice des prix de l'Insee.",
    ]
    juge = options.get("juge")
    if juge:
        lignes = {x["cible"]: x for x in juge.get("lignes") or ()}
        tenues = [x["libelle"] for c, x in lignes.items()
                  if c in ("pib_volume", "emploi", "chomage") and x.get("tenue")]
        manquees = [x["libelle"] for c, x in lignes.items()
                    if c in ("pib_volume", "emploi", "chomage") and not x.get("tenue")]
        limites.append(
            "Le juge de l'histoire (D-439) rejoue les années passées : "
            + (f"tenu pour {_bas(tenues)}" if tenues else "rien de tenu")
            + (f", manqué pour {_bas(manquees)}" if manquees else "")
            + " ; c'est un test du jumeau, pas de cette mesure.")
    sans = thetas_sans_source(options)
    if sans:
        limites.append(f"θ lus sans estimation publiée, à la loi large (D-417) : "
                       f"{', '.join(sans)}.")
    limites.append(limite_bande(options))
    if not any(i.cle == "emploi" for i in indicateurs):
        limites.append("L'emploi, le chômage, les prix et les salaires ne sont écrits que "
                       "par le mode structurel : absents ici, pas nuls.")
    return Dimension(
        cle=CLE, titre="L'économie en général",
        question="La mesure fait-elle grandir l'économie, créer des emplois, monter les "
                 "prix, et les salaires suivent-ils ?",
        annees=tuple(int(a) for a in options.get("annees") or ()),
        indicateurs=tuple(indicateurs), statut=statut_, sources=SOURCES,
        limites=tuple(limites), notes={"decision": "D-606"})
