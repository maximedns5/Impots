"""Les a priori des θ tirés de la littérature publiée (but 23, D-424).

L'histoire budgétaire agrégée n'identifie aucun θ (D-421, D-423) : ce qui les porte est
l'a priori. D-417 en donnait un seul, le même pour tous, gaussien en ½ d'écart-type ½ ;
celui-ci en donne un par θ, pris dans une estimation publiée du paramètre du bloc
(`parametres/a_priori.yaml`, chaque nombre avec sa source, sa page, son tableau).

LA LOI SUR θ. Une estimation m du paramètre, d'écart-type s, passe par l'application
θ → paramètre du bloc, linéaire par morceaux par le centre (bas à θ = 0, centre à ½, haut
à 1, `predictif.theta.value_at`), prolongée au-delà des bornes par la pente de sa
moitié. Son inverse θ(v) donne :

    μ = θ(m),   s₋ = μ − min(θ(m − s), θ(m + s)),   s₊ = max(θ(m − s), θ(m + s)) − μ

et la loi de θ est une normale à deux écarts-types, s₋ sous μ, s₊ au-dessus (exacte quand
m est au centre, où l'application change de pente ; approchée sinon). μ peut sortir de
[0 ; 1] quand la source sort de la plage : la plage ne change pas (les études et les
curseurs la lisent), l'estimation reste dans la boîte, et l'a priori la pousse vers la
borne ; la D-entrée le dit. Un θ sans source garde la loi large de D-417, N(½ ; ½).

Les plages ne sont pas recopiées : `plages` les lit dans les paramètres des blocs.
"""

from __future__ import annotations

import functools
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

FICHIER = Path(__file__).parent / "parametres" / "a_priori.yaml"


class APrioriError(ValueError):
    """Un a priori mal formé, ou un θ du registre sans entrée."""


@dataclass(frozen=True)
class Loi:
    """Une normale à deux écarts-types sur θ."""

    moyenne: float
    ecart_bas: float
    ecart_haut: float
    source: str | None = None
    """None : l'a priori large de D-417, sans source."""

    def __post_init__(self) -> None:
        if not (math.isfinite(self.moyenne) and self.ecart_bas > 0 and self.ecart_haut > 0):
            raise APrioriError(f"loi ({self.moyenne}, {self.ecart_bas}, {self.ecart_haut})")

    @property
    def ecart_type(self) -> float:
        """L'écart-type résumé, la moyenne des deux demi-écarts."""
        return 0.5 * (self.ecart_bas + self.ecart_haut)

    def residu(self, theta: Any) -> np.ndarray:
        """(θ − μ) / s±, le terme de l'a priori dans les moindres carrés."""
        t = np.asarray(theta, dtype=float)
        return (t - self.moyenne) / np.where(t < self.moyenne, self.ecart_bas,
                                             self.ecart_haut)


#: L'a priori de D-417 : gaussien en ½, d'écart-type ½.
LARGE = Loi(0.5, 0.5, 0.5)


def theta_de(valeur: float, plage: tuple[float, float, float]) -> float:
    """L'inverse de l'application θ → paramètre (bas, centre, haut), prolongée au-delà des
    bornes par la pente de la moitié qui y mène. La plage peut décroître (une montée en
    charge plus courte est une réponse plus forte)."""
    bas, centre, haut = plage
    if (valeur - centre) * (haut - centre) >= 0:
        if haut == centre:
            raise APrioriError(f"plage {plage} plate au-dessus du centre")
        return 0.5 + 0.5 * (valeur - centre) / (haut - centre)
    if bas == centre:
        raise APrioriError(f"plage {plage} plate au-dessous du centre")
    return 0.5 - 0.5 * (valeur - centre) / (bas - centre)


def loi_depuis(estimation: float, ecart_type: float, plage: tuple[float, float, float],
               source: str | None = None) -> Loi:
    """La loi de θ d'une estimation publiée du paramètre (docstring du module)."""
    if not ecart_type > 0:
        raise APrioriError(f"écart-type {ecart_type}")
    mu = theta_de(estimation, plage)
    a, b = theta_de(estimation - ecart_type, plage), theta_de(estimation + ecart_type, plage)
    return Loi(mu, mu - min(a, b), max(a, b) - mu, source)


def plages() -> dict[str, tuple[float, float, float]]:
    """La plage (bas, centre, haut) du paramètre de chaque θ estimé sur une source, lue
    dans les paramètres des blocs."""
    from impots.jumeau import thetas
    from impots.jumeau.blocs import commerce, menages, valeurs_entreprises

    c, m, e = commerce.charger(), menages.charger(), valeurs_entreprises.charger()

    def triple(d: Mapping[str, Any]) -> tuple[float, float, float]:
        return (float(d["low"]), float(d["central"]), float(d["high"]))

    def plage(p: Any) -> tuple[float, float, float]:
        return (p.bas, p.centre, p.haut)

    out = {thetas.ELASTICITE_PRIX_EXPORTATIONS.cle: c.bornes_x,
           thetas.ELASTICITE_PRIX_IMPORTATIONS.cle: c.bornes_m,
           thetas.EMPLOI_COUT: triple(m.sigma),
           thetas.SALAIRES_CHOMAGE: triple(m.echelle_chomage),
           "investissement_cout_capital": plage(e.elasticite_cout),
           "investissement_accelerateur": plage(e.accelerateur_contemporain),
           "implantation_tmee": plage(e.semi_elasticite_tmee)}
    for ligne in m.offre.values():
        if ligne["un"] != "high":
            raise APrioriError(f"{ligne['cle']} : θ = 1 n'est pas la borne haute")
        out[ligne["cle"]] = triple(ligne)
    return out


@functools.cache
def lire(chemin: Path = FICHIER) -> dict[str, dict[str, Any]]:
    return yaml.safe_load(chemin.read_text(encoding="utf-8"))


def lois(chemin: Path = FICHIER) -> dict[str, Loi]:
    """Une loi par θ du registre ; un θ du registre sans entrée, ou une entrée hors du
    registre, est refusé par son nom."""
    from impots.jumeau import thetas

    entrees = lire(chemin)
    manquants = sorted(set(thetas.REGISTRE) - set(entrees))
    inconnus = sorted(set(entrees) - set(thetas.REGISTRE))
    if manquants or inconnus:
        raise APrioriError(f"θ sans a priori : {manquants} ; a priori sans θ : {inconnus}")
    bornes = plages()
    out = {}
    for cle, d in entrees.items():
        if "sans_source" in d:
            out[cle] = LARGE
        elif "theta" in d:
            t = d["theta"]
            out[cle] = Loi(float(t["moyenne"]), float(t["ecart_type"]),
                           float(t["ecart_type"]), d["source"])
        else:
            if cle not in bornes:
                raise APrioriError(f"« {cle} » : une estimation, mais aucune plage lue")
            out[cle] = loi_depuis(float(d["estimation"]), float(d["ecart_type"]),
                                  bornes[cle], d["source"])
    return out
