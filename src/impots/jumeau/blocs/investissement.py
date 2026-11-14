"""Le bloc `investissement` (but 23, lot 2, D-407) : l'investissement des sociétés non
financières par le coût d'usage du capital, avec l'équation estimée de Mésange.

Canal « investissement_cout_du_capital » : `mesange` le porte aussi par ses
multiplicateurs (son équation d'investissement est dans ses variantes), mais pour ses seuls
instruments. Le bloc le porte pour ceux qu'il lit (l'IS, la CVAE et la C3S, que Mésange n'a
pas) : les deux tournent ensemble sans double compte, et un bloc qui lirait les cotisations
employeurs serait refusé avec `mesange` (`canaux`, D-411).

SOURCES : Insee, Mésange (G2017-04) [lu] — le coût d'usage, p. 42 du PDF ; l'équation
d'investissement, p. 44 du PDF (folio 43) ; la variante de taux, p. 134 ; Insee, comptes
de patrimoine 2024, t. 8.202 (knet) ; comptes nationaux 2025, t. 1.101 (PIB, FBCF).

ÉQUATIONS, pour la mesure m, l'année t (k années de trajectoire), Y_t le PIB du scénario :

1. Le coût d'usage (Mésange, p. 42) : ck = pinv + ln(R + tdec + prime + fisca), fisca =
   (D51 + D292 − D39) / knet. L'IS (D51) et les impôts sur la production (D292 : CVAE,
   C3S) y entrent ; les cotisations patronales non (des impôts sur la main-d'œuvre) :

       Δck_{m,t} = Σ_{s ∈ I} P_{s,m,t} / (knet_t u)

   knet_t = κ_K Y_t, κ_K = 3 083,8 / 2 935,2 (knet et PIB de 2024) ; u = R + tdec +
   prime + fisca = 0,01 / 0,065 (p. 134 : 100 points de base de taux font 6,5 % de coût).

2. L'investissement (Mésange, p. 44), trimestriel, l'accélérateur hors du bloc (la valeur
   ajoutée est celle du scénario ; la boucle de la demande est au lot 4) :

       x_q = ie_q − va_q,   Δx_q = 0,22 Δx_{q−2} − 0,06 (x_{q−1} + ε_K Δck_{q−1})

   ε_K = 0,44 (θ_investissement : 0,37, l'estimation libre, à 0,48, Mésange 2010, même
   page). Le choc d'une année tombe au premier trimestre ; la réponse annuelle est la
   moyenne des quatre trimestres, comme la colonne « 1 an » de Mésange. Linéaire :

       ΔI_{m,t} / I_t = −ε_K Σ_{j ≤ t} (Δck_{m,j} − Δck_{m,j−1}) R(t − j)

   R(h) la réponse annuelle à un échelon unitaire de Δck à ε_K = 1 (`reponse_unitaire`) ;
   I_t = (FBCF des SNF / PIB du départ) Y_t.

3. Le capital et le PIB potentiel :

       ΔK_{m,t} = (1 − δ) ΔK_{m,t−1} + ΔI_{m,t}
       ΔY_{m,t} = s_K (ΔK_{m,t} / knet_t) Y_t

   δ = I/K − g_K = 0,1164 − 0,0387 (2024, et la croissance de knet de 2014 à 2024) ; s_K
   la part du capital du départ, EBE et revenu mixte sur eux plus D1 (t. 1.105).

Le bloc écrit ΔI sur la FBCF des SNF et sur l'investissement des entreprises (la
référence, I_t, sous la clé « »), ΔY sur les revenus non ventilés, ΔY − ΔI sur les
emplois non ventilés (l'investissement prend sa place parmi les emplois, à PIB potentiel
donné : le reste est un effet d'offre sans emploi désigné, dit), ρ ΔY sur l'effet induit
sur le solde. Le PIB, ΔI + (ΔY − ΔI), est fermé par le cadre (D-411).

4. L'ACCÉLÉRATEUR (mode structurel, `accelerateur=True`, D-414). La même équation de
   Mésange (p. 44), avec la valeur ajoutée qui bouge :

       Δie_q = 0,22 Δie_{q−2} + β₀ Δva_q + β₁ Δva_{q−1} − 0,06 (ie − va + ε_K ck)_{q−1}

   β₀ = 1,19 (t = 6,9) et β₁ = 0,65 (t = 4,3), θ_accélérateur les déplace ensemble de
   ∓ 1,96 écart type (`entreprises.yaml`). Linéaire : la réponse à un échelon de va au
   premier trimestre est β₀ R₀ + β₁ R₁ + R_ec (`reponse_valeur_ajoutee`), R₀ et R₁ celles
   des deux termes de court terme, R_ec celle de la correction d'erreur, qui tend vers un
   (l'indexation unitaire de long terme) ; la moyenne annuelle redonne la ligne « Valeur
   ajoutée (+1 %) » de la p. 45 : 1,795, 2,011 et 1,381 à 1, 2 et 5 ans contre 1,79,
   2,00 et 1,36. Pour la mesure m :

       ŷ_{m,j} = (ΔPIB_{m,j} − ΔPIB^prix_{m,j}) / Y_j       l'écart du PIB en volume
       ΔI^a_{m,t} = I_t Σ_{j ≤ t} (ŷ_{m,j} − ŷ_{m,j−1}) R_va(t − j)

   la valeur ajoutée des branches marchandes de Mésange lue comme le PIB en volume (une
   approximation, dite) ; ΔPIB^prix le champ `effet_prix_pib` de la boucle prix-salaires.
   En mode structurel, la valeur ajoutée non marchande des APU (`va_non_marchande`, D-418)
   en est retranchée.
   ΔI^a est une demande : il va sur la FBCF des SNF et l'investissement des entreprises,
   et, en revenu, sur l'EBE (une production marchande, dont les salaires se prennent par
   le bloc `salaires`) ; il n'entre pas au capital du PIB potentiel (équation 3) : à court
   terme la production suit la demande, et l'offre qu'il ajouterait serait comptée deux
   fois. Le bloc lit le PIB de l'année : il tourne dans la boucle simultanée
   (`blocs.BOUCLE_STRUCTURELLE`). Canal « investissement_accelerateur », pour tout
   instrument : avec `mesange`, refusé.

COMPARAISON À MÉSANGE (`comparer_mesange`) : sous la variante de taux (+6,5 % de coût du
capital), le bloc donne −ε_K 6,5 R(h) ; Mésange imprime l'investissement des SNF, effet
accélérateur compris. L'écart est dit dans D-407, jamais forcé.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np

from impots.jumeau import canaux
from impots.jumeau.blocs.entreprises import (
    ACCELERATEUR_ROW,
    INVESTISSEMENT_ROW,
    Parametres,
    chemins,
    lire_theta,
    part_capital,
    part_depart,
    pib_scenario,
    taux_prelevements,
)
from impots.jumeau.pas import Contexte

#: Mésange, p. 134 du PDF : l'investissement des SNF et EI sous la hausse permanente de
#: 100 points de base des taux, % d'écart au compte central, à 1, 2, 3, 5 et 10 ans et LT.
MESANGE_TAUX = {"1": -0.58, "2": -2.48, "3": -3.36, "5": -4.07, "10": -5.02, "LT": -6.29}
#: Même page : la valeur ajoutée du secteur marchand (l'accélérateur, à long terme unitaire).
MESANGE_TAUX_VA = {"1": -0.24, "2": -0.79, "3": -1.01, "5": -1.28, "10": -1.97, "LT": -3.98}
HORIZON_MAX = 200


@lru_cache(maxsize=8)
def reponse_unitaire(rappel: float, retard: float, annees: int = HORIZON_MAX
                     ) -> tuple[float, ...]:
    """R(h), h = 0, 1, … : la moyenne annuelle de x pour un échelon Δck = 1 au premier
    trimestre de l'année 0, à ε_K = 1 (x_q tend vers −1)."""
    trimestres = 4 * annees
    x = np.zeros(trimestres + 3)
    for q in range(trimestres):
        i = q + 2
        cout = 1.0 if q >= 1 else 0.0  # le terme de rappel lit Δck_{q−1}
        x[i] = x[i - 1] + retard * (x[i - 2] - x[i - 3]) - rappel * (x[i - 1] + cout)
    serie = x[2:2 + trimestres]
    return tuple(float(serie[4 * h:4 * h + 4].mean()) for h in range(annees))


@lru_cache(maxsize=8)
def reponse_valeur_ajoutee(rappel: float, retard: float, annees: int = HORIZON_MAX
                           ) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """(R₀, R₁, R_ec), h = 0, 1, … : les moyennes annuelles de ie pour un échelon va = 1 au
    premier trimestre de l'année 0, par terme de l'équation (β₀ Δva_q, β₁ Δva_{q−1}, la
    correction d'erreur −rappel (ie − va)_{q−1}) ; la réponse est β₀ R₀ + β₁ R₁ + R_ec."""
    trimestres = 4 * annees
    out = []
    for terme in range(3):
        ie = np.zeros(trimestres + 3)
        for q in range(trimestres):
            i = q + 3
            forcage = (1.0 if (terme == 0 and q == 0) or (terme == 1 and q == 1) else 0.0)
            va_prec = 1.0 if (terme == 2 and q >= 1) else 0.0
            ie[i] = (ie[i - 1] + retard * (ie[i - 2] - ie[i - 3]) + forcage
                     - rappel * (ie[i - 1] - va_prec))
        serie = ie[3:3 + trimestres]
        out.append(tuple(float(serie[4 * h:4 * h + 4].mean()) for h in range(annees)))
    return out[0], out[1], out[2]


def comparer_mesange(p: Parametres, theta: float = 0.5) -> dict[str, dict[str, float]]:
    """Le bloc, linéarisé, sous la variante de taux de Mésange : la réponse de
    l'investissement (%), celle de Mésange, et celle de Mésange moins sa valeur ajoutée
    (l'accélérateur à élasticité unitaire retiré, une approximation)."""
    r = reponse_unitaire(p.rappel_trimestriel, p.retard_trimestriel)
    eps = float(p.elasticite_cout.a(np.array([theta]))[0])
    choc = 100.0 * p.hausse_cout_par_point_de_taux
    out: dict[str, dict[str, float]] = {}
    for h in MESANGE_TAUX:
        rang = HORIZON_MAX - 1 if h == "LT" else int(h) - 1
        out[h] = {"jumeau": eps * choc * r[rang],
                  "mesange": MESANGE_TAUX[h],
                  "mesange_hors_va": MESANGE_TAUX[h] - MESANGE_TAUX_VA[h]}
    return out


class Investissement:
    nom = "investissement"
    ecrit = ("fbcf_snf", "investissement_entreprises", "emplois_non_ventiles",
             "revenus_non_ventiles", "solde_induit")
    thetas = (INVESTISSEMENT_ROW,)
    porte: tuple[str, ...] = ()
    remplace = ("investissement_cout_du_capital",)

    def __init__(self, parametres: Parametres, *, accelerateur: bool = False,
                 prix: bool = False) -> None:
        self.p = parametres
        self.signaux = tuple(parametres.signaux_investissement)
        self.lit = self.signaux
        self.instruments = {"investissement_cout_du_capital": canaux.des_signaux(self.lit)}
        self.r = np.array(reponse_unitaire(parametres.rappel_trimestriel,
                                           parametres.retard_trimestriel))
        self.accelerateur = accelerateur
        if accelerateur:
            # La valeur ajoutée de l'année : le PIB, et sa part prix si la boucle
            # prix-salaires tourne (D-414).
            self.lit = (*self.signaux, "pib",
                        *(("effet_prix_pib", "va_non_marchande") if prix else ()))
            self.ecrit = (*Investissement.ecrit, "ebe_revenu_mixte")
            self.thetas = (INVESTISSEMENT_ROW, ACCELERATEUR_ROW)
            self.remplace = (*Investissement.remplace, "investissement_accelerateur")
            self.r_va = tuple(np.array(r) for r in reponse_valeur_ajoutee(
                parametres.rappel_trimestriel, parametres.retard_trimestriel))
        self.prix = prix
        self._passe: dict[tuple[int, str], np.ndarray] = {}

    def volume(self, ctx: Contexte, j: int, m: str) -> np.ndarray:
        """ŷ_{m,j} : l'écart du PIB en volume de la mesure m à l'année j, part du PIB de
        référence. Une année passée ne change plus : gardée le temps d'une trajectoire."""
        if j < ctx.k and (j, m) in self._passe:
            return self._passe[(j, m)]
        etat = ctx.courant if j == ctx.k else ctx.passe(j)
        pib = etat.par_mesure("pib").get(m, 0.0)
        prix = (etat.par_mesure("effet_prix_pib").get(m, 0.0)
                if self.prix and etat.present("effet_prix_pib") else 0.0)
        # La valeur ajoutée marchande : sans celle des APU (D-418).
        nm = (etat.par_mesure("va_non_marchande").get(m, 0.0)
              if self.prix and etat.present("va_non_marchande") else 0.0)
        y = np.zeros(ctx.n) + (pib - prix - nm) / ctx.pib_reference(j)
        if j < ctx.k:
            self._passe[(j, m)] = y
        return y

    def accelere(self, ctx: Contexte, m: str, beta0: np.ndarray, beta1: np.ndarray
                 ) -> np.ndarray:
        """ΔI^a_{m,k}, Md€ : la réponse de l'investissement à la valeur ajoutée."""
        k = ctx.k
        if k >= len(self.r_va[0]):
            raise ValueError(f"trajectoire de {k + 1} ans au-delà de {len(self.r_va[0])}")
        r0, r1, rec = self.r_va
        total = np.zeros(ctx.n)
        precedent: Any = 0.0
        for j in range(k + 1):
            y = self.volume(ctx, j, m)
            h = k - j
            total = total + (y - precedent) * (beta0 * r0[h] + beta1 * r1[h] + rec[h])
            precedent = y
        return total * part_depart(ctx, "fbcf_snf") * pib_scenario(ctx, k)

    def chemin(self, ctx: Contexte, signaux: list[np.ndarray], eps: np.ndarray
               ) -> tuple[list[np.ndarray], list[np.ndarray]]:
        """(ΔI_t, ΔK_t), t = 0 … k, Md€."""
        p, k = self.p, ctx.k
        if k >= len(self.r):
            raise ValueError(f"trajectoire de {k + 1} ans au-delà de {len(self.r)}")
        part_i = part_depart(ctx, "fbcf_snf")
        cout = [signaux[j] / (p.capital_part_pib * pib_scenario(ctx, j) * p.taux_cout_usage)
                for j in range(k + 1)]
        di, dk = [], []
        capital = np.zeros(ctx.n)
        for t in range(k + 1):
            x = np.zeros(ctx.n)
            for j in range(t + 1):
                pas_ = cout[j] - (cout[j - 1] if j else 0.0)
                x = x + pas_ * self.r[t - j]
            x = eps * x  # R est à ε_K = 1, et négatif : un coût plus haut, moins d'investissement
            investi = x * part_i * pib_scenario(ctx, t)
            capital = (1.0 - p.depreciation) * capital + investi
            di.append(investi)
            dk.append(capital.copy())
        return di, dk

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        p, k = self.p, ctx.k
        if k == 0:
            self._passe.clear()
        eps = p.elasticite_cout.a(lire_theta(ctx, INVESTISSEMENT_ROW))
        y = pib_scenario(ctx, k)
        s_k, rho = part_capital(ctx), taux_prelevements(ctx)
        out: dict[str, dict[str, Any]] = {n: {} for n in self.ecrit}
        out["investissement_entreprises"][""] = part_depart(ctx, "fbcf_snf") * y
        for m, signaux in chemins(ctx, self.signaux).items():
            di, dk = self.chemin(ctx, signaux, eps)
            dy = s_k * dk[k] / (p.capital_part_pib * y) * y
            out["fbcf_snf"][m] = di[k]
            out["investissement_entreprises"][m] = di[k]
            out["emplois_non_ventiles"][m] = dy - di[k]
            out["revenus_non_ventiles"][m] = dy
            out["solde_induit"][m] = rho * dy
        if self.accelerateur:
            t = lire_theta(ctx, ACCELERATEUR_ROW)
            beta0, beta1 = p.accelerateur_contemporain.a(t), p.accelerateur_retarde.a(t)
            for m in ctx.mesures:
                ident = m.identifiant
                da = self.accelere(ctx, ident, beta0, beta1)
                for nom in ("fbcf_snf", "investissement_entreprises"):
                    out[nom][ident] = out[nom].get(ident, 0.0) + da
                out["ebe_revenu_mixte"][ident] = da
        return out
