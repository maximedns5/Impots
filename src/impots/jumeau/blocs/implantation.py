"""Le bloc `implantation` (but 23, lot 2, D-407) : le capital des multinationales sous
contrôle étranger selon le taux effectif moyen d'imposition (TMEE), à la Devereux et
Griffith : la décision discrète de s'implanter lit le taux moyen, pas le taux marginal.

Canal « implantation » : ni Mésange (sans variante d'IS ni d'investissement étranger) ni un
autre bloc ne le porte.

SOURCES [lu] : Devereux et Lockwood (2006), « Taxes and the size of the foreign-owned
capital stock: which tax rates matter? », tableau 2, colonne 1, p. 25 du PDF (19 pays de
l'OCDE, 1985-1998, le capital des filiales américaines) ; Hanappi, Millot et Turban, OCDE
ECO/WKP(2023)18, tableau 1, p. 24 du PDF (la sensibilité au TMEE après 2009) ; OCDE,
Corporate Tax Statistics, France 2025, et la méthode de l'annexe (`entreprises.
taux_effectifs`) ; Insee, Les entreprises en France 2023, fiche 3.2, figure 1.

ÉQUATIONS, pour la mesure m, l'année t, Y_t le PIB du scénario :

    ΔTMEE_{m,t} = κ P_{IS,m,t} / (b Y_t)                     en fraction
    k^f_{m,t} = 0,676 k^f_{m,t−1} − a₁ ΔTMEE_{m,t}           Δ ln K_f (Devereux-Lockwood)
    ΔK_{m,t} = s_f k^f_{m,t} knet_t
    ΔI_{m,t} = ΔK_{m,t} − (1 − δ) ΔK_{m,t−1}
    ΔY_{m,t} = s_K (ΔK_{m,t} / knet_t) Y_t

P_IS la variation de l'IS, de sa contribution sociale et de la CEBGE (le TMEE de l'OCDE ne
porte que l'impôt sur le bénéfice) ; b = 0,092, le profit imposable en part du PIB
(D-402) : le taux apparent tient lieu de taux légal, comme D-402 ; κ = ∂TMEE/∂τ = 0,917,
le TMEE composite de la France calculé à 25,825 % ± 1 point par la méthode de l'OCDE
(les amortissements proportionnels au taux) ; a₁ = 0,478 (θ_implantation : 0, la
sensibilité disparue après 2009 selon Hanappi et al., à 0,730, le centre plus 1,96 écart
type) ; s_f = 0,16, la part de la valeur ajoutée sous contrôle étranger, qui tient lieu
de sa part du capital (choisie, non vérifiée) ; knet, δ, s_K comme `investissement`.

Le bloc écrit ΔI sur la FBCF des SNF et l'investissement des entreprises, ΔY sur les
revenus non ventilés, ΔY − ΔI sur les emplois non ventilés (un effet d'offre sans emploi
désigné, dit), ρ ΔY sur l'effet induit sur le solde ; le cadre ferme le PIB (D-411). Linéaire dans P_IS ; la CVAE, la C3S et les cotisations n'y jouent
pas (dit, et tenu par un test).
"""

from __future__ import annotations

from typing import Any

import numpy as np

from impots.jumeau.blocs.entreprises import (
    IMPLANTATION_ROW,
    Parametres,
    chemins,
    lire_theta,
    part_capital,
    pib_scenario,
    taux_prelevements,
)
from impots.jumeau.pas import Contexte


class Implantation:
    nom = "implantation"
    ecrit = ("fbcf_snf", "investissement_entreprises", "emplois_non_ventiles",
             "revenus_non_ventiles", "solde_induit")
    thetas = (IMPLANTATION_ROW,)
    porte = ("implantation",)
    remplace: tuple[str, ...] = ()

    def __init__(self, parametres: Parametres) -> None:
        self.p = parametres
        self.lit = tuple(parametres.signaux_implantation)

    def capital(self, ctx: Contexte, signaux: list[np.ndarray], a1: np.ndarray
                ) -> list[np.ndarray]:
        """ΔK_{m,t}, t = 0 … k, Md€."""
        p = self.p
        kf = np.zeros(ctx.n)
        out = []
        for t in range(ctx.k + 1):
            y = pib_scenario(ctx, t)
            tmee = p.tmee_par_point_de_taux * signaux[t] / (p.assiette_part_pib * y)
            kf = p.persistance_implantation * kf - a1 * tmee
            out.append(p.part_etrangere * kf * p.capital_part_pib * y)
        return out

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        p, k = self.p, ctx.k
        a1 = p.semi_elasticite_tmee.a(lire_theta(ctx, IMPLANTATION_ROW))
        s_k, rho = part_capital(ctx), taux_prelevements(ctx)
        out: dict[str, dict[str, Any]] = {n: {} for n in self.ecrit}
        for m, signaux in chemins(ctx, self.lit).items():
            dk = self.capital(ctx, signaux, a1)
            di = dk[k] - (1.0 - p.depreciation) * (dk[k - 1] if k else 0.0)
            dy = s_k * dk[k] / p.capital_part_pib
            out["fbcf_snf"][m] = di
            out["investissement_entreprises"][m] = di
            out["emplois_non_ventiles"][m] = dy - di
            out["revenus_non_ventiles"][m] = dy
            out["solde_induit"][m] = rho * dy
        return out
