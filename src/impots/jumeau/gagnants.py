"""Les gagnants et les perdants, par cellule de ménages et par année (but 23, lot 4, D-409).

Pour chaque année de la trajectoire et chaque cellule (décile de niveau de vie × type de
ménage, `jumeau.cellules`), l'écart du revenu disponible que la variante apporte à la
référence : le choc statique de chaque mesure sur le décile (sa passe sur la population,
CADRE.md §5), réparti entre les cellules du décile au prorata de leurs ménages, plus ce
que la dynamique leur apporte, l'emploi, les salaires et les allocations chômage
(`blocs.menages.revenus_cellules`, la même fonction que le bloc `consommation` : le
revenu par décile que l'état porte est la somme de ses cellules, à l'arrondi près).

Une cellule n'a pas de distribution interne : tous ses ménages y gagnent ou y perdent
autant. La part des gagnants est donc celle des ménages des cellules qui gagnent plus de
`SEUIL` euros par an, ce que dit chaque nombre qui la lit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from impots.jumeau.blocs.menages import Parametres, charger, reference, revenus_cellules, structure
from impots.jumeau.cellules import Cellules
from impots.jumeau.etat import Etat
from impots.population.aggregate import INDIFFERENCE_EUR

#: Le seuil d'indifférence, en euros par ménage et par an, celui des rapports.
SEUIL = INDIFFERENCE_EUR


@dataclass(frozen=True)
class Gagnants:
    annees: tuple[int, ...]
    ecart_md: np.ndarray
    """Md€ courants, forme (années, 50, n), toutes mesures."""
    par_mesure: dict[str, np.ndarray]
    """La même chose, mesure par mesure."""
    menages: np.ndarray
    uc: np.ndarray

    @property
    def par_menage(self) -> np.ndarray:
        """€ par ménage et par an, (années, 50, n)."""
        return self.ecart_md * 1e9 / self.menages[None, :, None]

    @property
    def par_uc(self) -> np.ndarray:
        """€ par unité de consommation et par an : l'écart de niveau de vie."""
        return self.ecart_md * 1e9 / self.uc[None, :, None]

    def part_gagnants(self) -> np.ndarray:
        """La part des ménages des cellules qui gagnent plus que le seuil, (années, n)."""
        gagne = self.par_menage > SEUIL
        return (gagne * self.menages[None, :, None]).sum(axis=1) / self.menages.sum()

    def part_perdants(self) -> np.ndarray:
        perd = self.par_menage < -SEUIL
        return (perd * self.menages[None, :, None]).sum(axis=1) / self.menages.sum()


def gagnants_perdants(trajectoire: Any, depart: Etat, cellules: Cellules,
                      params: Parametres | None = None) -> Gagnants:
    """L'écart du revenu disponible de chaque cellule, chaque année, sur la variante d'une
    trajectoire calculée avec les blocs des ménages."""
    params = params if params is not None else charger()
    st = structure(cellules, params.pib_cellules)
    mesures: Sequence[Any] = trajectoire.mesures
    par_mesure = {m.identifiant: [] for m in mesures}
    for ref_etat, etat in zip(trajectoire.reference, trajectoire.variante, strict=True):
        ref = reference(params, depart, ref_etat["pib"])
        for m in mesures:
            par_mesure[m.identifiant].append(revenus_cellules(etat, m, ref, params, st)[0])
    tableaux = {k: np.array(v) for k, v in par_mesure.items()}
    n = trajectoire.variante[0].n
    total = sum(tableaux.values()) if tableaux else np.zeros(
        (len(trajectoire.annees), len(st.menages), n))
    return Gagnants(annees=tuple(trajectoire.annees), ecart_md=np.asarray(total),
                    par_mesure=tableaux, menages=cellules["menages"], uc=cellules["uc"])
