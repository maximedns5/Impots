"""La dimension « comptes publics » (but 29, volet `tableau`, D-606) : ce que la mesure
fait au solde, à la dette, aux recettes et aux dépenses des administrations publiques.

Ce sont les nombres que la page du jumeau montre déjà (`navigateur._series`,
`navigateur._comptes`), lus dans le même état : le solde B9 en Md€, la dette en points de
PIB (Δb, D-459), les recettes hors intérêts reçus et les dépenses primaires en Md€. Le
départ est l'état publié de 2025 (D-412) ; le choc, la passe de la mesure sur la
population (son rapport) ; la suite, les blocs du jumeau (D-414).
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

CLE = "comptes_publics"

SOURCES = (
    Source("Insee, comptes nationaux annuels base 2020, t. 3.201 (compte des APU) ; "
           "Eurostat, dette de Maastricht", "l'état publié de 2025, "
           "`jumeau.historique.etat_initial` (D-412)",
           "le départ : recettes, dépenses, solde, dette et PIB de 2025"),
    Source("Les rapports d'étude commités : une passe OpenFisca par mesure sur la "
           "population de D-553", "le rapport de chaque mesure (`Mesure.rapport`)",
           "le coût mécanique de chaque année et les recettes de comportement (D-336)"),
    Source("Insee, Mésange (G2017-04), et les blocs du jumeau", "CADRE.md ; D-409, D-414",
           "ce que l'activité, l'emploi et les prix rendent en recettes, année par année"),
)


def _ratio(reference: Any, variante: Any) -> np.ndarray | None:
    r, v = niveaux(reference, "ratio_dette"), niveaux(variante, "ratio_dette")
    return None if r is None or v is None else 100.0 * (v - r)


@inscrire(CLE)
def comptes_publics(variante: Any, reference: Any, depart: Any, cellules: Any,
                    **options: Any) -> Dimension:
    indicateurs = []
    for cle, libelle, unite, sens, f in (
            ("solde", "Solde des administrations publiques (B9)", "Md€", 1,
             lambda r, v: ecart(r, v, "b9")),
            ("dette", "Dette publique", "points de PIB", -1, _ratio),
            ("recettes", "Recettes des administrations publiques", "Md€", 0,
             lambda r, v: ecart(r, v, "apu_recettes")),
            ("depenses", "Dépenses primaires des administrations publiques", "Md€", 0,
             lambda r, v: ecart(r, v, "apu_depenses_primaires"))):
        s = serie(f, options, reference, variante)
        if s is not None:
            indicateurs.append(Indicateur(cle, libelle, unite, *s, sens=sens))
    statut_, limites = statut(options)
    limites += [
        "Écart à la trajectoire sans la mesure, pas un niveau : un solde de −10 Md€ veut "
        "dire 10 Md€ de déficit en plus que sans elle.",
        "Le coût de la première année d'une mesure a été confronté à des chiffrages "
        "officiels sur quelques cas seulement (D-300 : trois sur cinq dans leur "
        "tolérance) ; les années suivantes et la dette ne l'ont jamais été.",
    ]
    juge = options.get("juge")
    if juge:
        limites.append(
            f"Le juge de l'histoire (D-439) rejoue les années passées : le jumeau y tient "
            f"{juge.get('tenues')} cibles sur {juge.get('cibles')} (le solde, la dette et "
            f"les recettes en sont) ; c'est un test du jumeau, pas de cette mesure.")
    sans = thetas_sans_source(options)
    if sans:
        limites.append(f"θ lus sans estimation publiée, à la loi large (D-417) : "
                       f"{', '.join(sans)}.")
    limites.append(limite_bande(options))
    if options.get("mode") == "reduit":
        limites.append("Mode réduit : la chaîne des études, sans les blocs des ménages ni "
                       "des entreprises.")
    return Dimension(
        cle=CLE, titre="Les comptes publics",
        question="Combien la mesure coûte-t-elle, ou rapporte-t-elle, à l'État et à la "
                 "Sécurité sociale, et que devient la dette ?",
        annees=tuple(int(a) for a in options.get("annees") or ()),
        indicateurs=tuple(indicateurs), statut=statut_, sources=SOURCES,
        limites=tuple(limites), notes={"decision": "D-606"})

