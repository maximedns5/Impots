"""Le bloc `mesures` : les chocs statiques des mesures sur leurs champs (CADRE.md §5).

ÉQUATIONS, pour chaque mesure m et l'année t (Md€) :

* un choc déclaré sur une catégorie du compte des APU, c_{m,i,t} au signe du moteur (un
  coût positif), s'inscrit en −c sur une recette, en +c sur une dépense ;
* le choc d'un rapport, qui ne ventile pas : sur « mesures_non_ventilees »,
  R_m,t(θ) = −coût_m,t + Σ canaux de recettes à θ (`predictif.rejouer.receipts`, les
  statistiques suffisantes de D-336 : C1, C7, C10, C11), au signe d'une recette ;
* l'impulsion sur l'instrument i de Mésange et la variation des prélèvements des
  entreprises et du capital, telles quelles, pour les blocs qui les lisent.

Une première année REPORTÉE (« part_pib_constante », D-343) se tient en part du PIB de
référence : la valeur de l'année t est celle de la première année fois Y_t / Y_premiere,
comme `chaine.run` la reporte.

Les θ des canaux de recettes sont ceux que le rapport réclame (`thetas.registre`) ; un θ
qui manque est refusé, jamais mis à ½.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from impots.jumeau import thetas
from impots.jumeau.champs import DEPENSES, IMPULSIONS, RECETTES
from impots.jumeau.mesures import CATEGORIES, EURO
from impots.jumeau.pas import Contexte
from impots.predictif import rejouer


class Mesures:
    nom = "mesures"
    lit: tuple[str, ...] = ()
    ecrit = (*CATEGORIES, "mesures_non_ventilees", *IMPULSIONS, "prelevements_entreprises")
    thetas: tuple[str, ...] = ()
    """Dynamiques : les lignes que chaque mesure porte."""

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}

        def ajouter(champ: str, mesure: str, valeur: Any) -> None:
            parts = out.setdefault(champ, {})
            parts[mesure] = parts[mesure] + valeur if mesure in parts else valeur

        for m in ctx.mesures:
            if ctx.annee not in m.annees:
                continue
            for categorie, cout in m.chocs.get(ctx.annee, {}).items():
                if categorie in RECETTES:
                    ajouter(categorie, m.identifiant, -float(cout))
                elif categorie in DEPENSES:
                    ajouter(categorie, m.identifiant, float(cout))
            if m.report:
                lue = m.annees[0]
                rang = ctx.k - (ctx.annee - lue)
                echelle = ctx.pib_reference(ctx.k) / ctx.pib_reference(rang)
            else:
                lue, echelle = ctx.annee, 1.0
            if lue in m.couts:
                canaux = m.canaux.get(lue)
                if canaux is None:
                    recettes = -m.couts[lue] * EURO
                else:
                    valeurs = {cle: rejouer.value_at(row, thetas.lire(ctx.theta, cle, ctx.n))
                               for cle, row in m.lignes.items()}
                    recettes = rejouer.receipts(-m.couts[lue] * EURO, canaux, valeurs)
                ajouter("mesures_non_ventilees", m.identifiant,
                        np.asarray(recettes, dtype=float) / EURO * echelle)
            for instrument, valeur in m.impulsions.get(lue, {}).items():
                ajouter(f"impulsion_{instrument}", m.identifiant, valeur * echelle)
            if lue in m.prelevements:
                ajouter("prelevements_entreprises", m.identifiant,
                        m.prelevements[lue] * echelle)
        return out
