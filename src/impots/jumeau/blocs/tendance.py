"""Le bloc `tendance` : la trajectoire de référence (CADRE.md §4), sans comportement.

ÉQUATIONS, celles de `dette.reference` (la convention « prélèvements constants en % du
PIB », D-213, D-215), année k = 1, 2, … après le départ :

    Y_k = Y_{k−1} (1 + g_k),   1 + g_k = (1 + croissance réelle_k)(1 + prix_k)
    s_k = s_{k−1} f_k,         f_k = 1 (part_pib_constante),
                               (1 + prix_k)/(1 + g_k) (gele_en_volume),
                               (1 + c)/(1 + g_k) (personnalise, c la croissance dite)
    recettes de la catégorie i = R Y_k a_i,     dépenses primaires j = s_k Y_k d_j
    emploi e = Y_k u_e,   revenu v = Y_k w_v,   déflateur de chaque emploi = 1 + prix_k

R, s_0 et les parts a_i, d_j, u_e, w_v sont celles de l'état de départ : R les recettes
hors intérêts sur le PIB, s_0 les dépenses primaires sur le PIB, chaque part rapportée à
la somme de son groupe (signée pour les emplois), de sorte que les parts somment à un et
que les identités tiennent sans l'écart de publication du départ. Les champs que la
référence n'a pas (l'effet non ventilé, les écarts de publication, l'ajustement
flux-stocks, le choc des mesures, l'effet induit) valent zéro : calculés nuls, pas
absents — une convention, dite, pour l'ajustement flux-stocks (§2).

Les intérêts, la dette, B9 et les ratios ne sont pas ici : le cadre les ferme (§3.4).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from impots.jumeau.champs import DEPENSES, EMPLOIS, EMPLOIS_EN_VOLUME, RECETTES, REGISTRE, REVENUS
from impots.jumeau.etat import Etat
from impots.jumeau.pas import Contexte

#: Ce que la référence écrit nul : ni effet induit, ni mesure, ni écart publié.
NULS = ("emplois_non_ventiles", "ventilation_emplois", "arrondi_emplois",
        "revenus_non_ventiles", "arrondi_revenus", "solde_induit", "mesures_non_ventilees",
        "sfa", "ecart_millesime_dette", "ecart_eurostat")


def _parts(etat: Etat, noms: tuple[str, ...]) -> tuple[dict[str, float], float]:
    """Les parts de chaque champ dans la somme signée du groupe, et cette somme."""
    valeurs = {n: float(etat[n][0]) for n in noms if n not in NULS}
    total = sum(REGISTRE[n].signe * v for n, v in valeurs.items())
    if total <= 0:
        raise ValueError(f"somme du groupe non positive au départ : {total}")
    return {n: v / total for n, v in valeurs.items()}, total


class Tendance:
    nom = "tendance"
    lit: tuple[str, ...] = ()
    ecrit = (*EMPLOIS, "pib", *REVENUS, *RECETTES, *DEPENSES,
             *(f"prix_{n}" for n in EMPLOIS_EN_VOLUME),
             "sfa", "ecart_millesime_dette", "ecart_eurostat")
    thetas: tuple[str, ...] = ()

    def __init__(self, depart: Etat, *, laisse: tuple[str, ...] = ()) -> None:
        # Les déflateurs qu'un autre bloc écrit (le commerce, pour les prix des
        # échanges) : un champ non additif n'a qu'un écrivain.
        etrangers = sorted(set(laisse) - {f"prix_{n}" for n in EMPLOIS_EN_VOLUME})
        if etrangers:
            raise ValueError(f"la tendance ne laisse que des déflateurs : {etrangers}")
        self.laisse = tuple(laisse)
        self.ecrit = tuple(c for c in Tendance.ecrit if c not in self.laisse)
        if depart.n != 1 and not all(np.all(depart[n] == depart[n][0])
                                     for n in ("pib", *RECETTES, *DEPENSES)):
            raise ValueError("un départ qui varie selon les tirages n'est pas une référence")
        self.annee = depart.annee
        self.pib = float(depart["pib"][0])
        self.emplois, _ = _parts(depart, EMPLOIS)
        self.revenus, _ = _parts(depart, REVENUS)
        self.recettes, recettes = _parts(depart, RECETTES)
        self.depenses, depenses = _parts(depart, DEPENSES)
        self.taux_prelevements = recettes / self.pib
        self.part_depense = depenses / self.pib

    def chemin(self, entrees: Any, k: int) -> tuple[float, float]:
        """(Y_k, s_k), le produit pris dans l'ordre de `dette.reference`."""
        produit, part = self.pib, self.part_depense
        for j in range(k + 1):
            produit *= 1.0 + entrees.nominale(j)
            part *= entrees.facteur_depense(j)
        return produit, part

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        if ctx.k == 0 and ctx.annee != self.annee + 1:
            raise ValueError(f"la référence part de {self.annee}, la trajectoire de "
                             f"{ctx.annee}")
        y, s = self.chemin(ctx.entrees, ctx.k)
        out: dict[str, dict[str, Any]] = {"pib": {"": y}}
        out.update({n: {"": y * p} for n, p in self.emplois.items()})
        out.update({n: {"": y * p} for n, p in self.revenus.items()})
        out.update({n: {"": self.taux_prelevements * y * p}
                    for n, p in self.recettes.items()})
        out.update({n: {"": s * y * p} for n, p in self.depenses.items()})
        prix = 1.0 + ctx.entrees.prix[ctx.k]
        out.update({f"prix_{n}": {"": prix} for n in EMPLOIS_EN_VOLUME
                    if f"prix_{n}" not in self.laisse})
        out.update({n: {"": 0.0} for n in NULS})
        return out
