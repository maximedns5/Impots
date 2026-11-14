"""Le bloc `creations` : le canal des créations d'entreprises du but 22, tel quel.

`predictif.creations` en bloc (D-401, D-402), vectorisé sur l'axe des tirages ; le lot 2
le remplacera. HYPOTHÈSE NON VALIDÉE, dite par `predictif.creations.CONVENTION`. Sources
et paramètres : `docs/diagnostics/creations_entreprises.md`, D-402.

ÉQUATIONS, pour la mesure m et l'année k (années s = 0 à k de la trajectoire) :

    Δτ_s = 100 ΔP_s / (b Y_s)            points de taux apparent, ΔP en Md€ (recettes +)
    Δe_s = −ε Δτ_s                        points de taux d'entrée
    y_k = s_VA r c Σ_{s ≤ k} Δe_s/100 S^(k−s) min(1, (k − s + 1)/M)
    recettes induites_k = ρ y_k

b l'assiette (part du PIB), ε la pente de Da Rin, Di Giacomo et Sembenelli (2011), S la
survie annuelle, M la montée en charge, r la taille relative, s_VA la part des sociétés
dans le PIB, ρ le taux de prélèvements du départ, c la productivité relative à θ :
c = centre − (1 − 2θ)(centre − 0) si θ ≤ ½, centre + (2θ − 1)(1 − centre) sinon
(`creations.productivite_a`). Le bloc écrit y_k Y_k sur le PIB et les emplois et revenus
non ventilés, ρ y_k Y_k sur l'effet induit sur le solde. Les paramètres sont ceux que le
rapport de la mesure porte (`instantane`), ou ceux donnés au bloc.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from impots.jumeau import thetas
from impots.jumeau.champs import RECETTES
from impots.jumeau.pas import Contexte
from impots.predictif import creations as canal
from impots.predictif.theta import CREATIONS_ROW


class CreationsError(ValueError):
    """Le canal ne se lit pas comme demandé."""


def productivite(theta: np.ndarray, params: canal.Parametres) -> np.ndarray:
    """c à θ, par le centre déclaré : `creations.productivite_a`, sur un tableau."""
    p = params.productivite
    return np.where(theta <= 0.5, p.centre - (1.0 - 2.0 * theta) * (p.centre - p.bas),
                    p.centre + (2.0 * theta - 1.0) * (p.haut - p.centre))


class Creations:
    nom = "creations"
    lit = ("prelevements_entreprises",)
    ecrit = ("pib", "emplois_non_ventiles", "revenus_non_ventiles", "solde_induit")
    thetas = (CREATIONS_ROW,)

    def __init__(self, parametres: canal.Parametres | None = None) -> None:
        self.parametres = parametres

    def _params(self, mesure: Any) -> canal.Parametres:
        if mesure.creations is not None:
            return canal.depuis(mesure.creations)
        if self.parametres is None:
            raise CreationsError(f"mesure « {mesure.identifiant} » : des prélèvements et "
                                 f"aucun paramètre du canal")
        return self.parametres

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        k = ctx.k
        passes = [ctx.passe(j).par_mesure("prelevements_entreprises") for j in range(k)]
        passes.append(ctx.par_mesure("prelevements_entreprises"))
        pib = [ctx.pib_reference(j) for j in range(k + 1)]
        depart = ctx.depart
        rho = sum(float(depart[n][0]) for n in RECETTES) / float(depart["pib"][0])
        out: dict[str, dict[str, Any]] = {c: {} for c in self.ecrit}
        for m in ctx.mesures:
            chemin = [an.get(m.identifiant) for an in passes]
            if all(v is None or not np.any(v) for v in chemin):
                continue
            params = self._params(m)
            c = productivite(thetas.lire(ctx.theta, CREATIONS_ROW, ctx.n), params)
            pente = params.elasticite.centre
            part = 0.0
            for s in range(k + 1):
                if chemin[s] is None:
                    continue
                taux = 100.0 * chemin[s] / (params.assiette_part_pib * pib[s])
                entree = -pente * taux
                part = part + (entree / 100.0 * params.survie_annuelle ** (k - s)
                               * min(1.0, (k - s + 1) / params.montee_en_charge_ans))
            y_k = part * (params.taille_relative * c) * params.part_va_societes_pib
            out["pib"][m.identifiant] = y_k * pib[k]
            out["emplois_non_ventiles"][m.identifiant] = y_k * pib[k]
            out["revenus_non_ventiles"][m.identifiant] = y_k * pib[k]
            out["solde_induit"][m.identifiant] = y_k * rho * pib[k]
        return out
