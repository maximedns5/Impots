"""La démographie des sociétés (but 23, lot 2, D-407) : `naissances`, `fermetures`,
`productivite`. Elle généralise le canal du but 22 (`predictif.creations`, D-401, D-402),
qui reste au lot 1 sous le nom `creations` (le mode compatible) : les deux portent le
canal « creations_entreprises » et ne tournent jamais ensemble (`canaux`).

NOTATIONS. N₀ le stock de sociétés des cellules (millésime 2023), porté comme celui du
départ ; Y_t le PIB du scénario (`entreprises.pib_scenario`) ; P_{s,m,t} les signaux du
lot 2, Md€, recettes positives ; une clé m est une mesure, la clé « » la référence. Les
valeurs et leurs sources : `jumeau/parametres/entreprises.yaml`.

LA SURVIE (une cohorte, âge a ≥ 0, S(0) = 1) :

    S(a) = S_j^a                     si a ≤ A
    S(a) = S_j^A (1 − h_o)^(a − A)   sinon
    1/e₀ = Σ_{a < A} S_j^a + S_j^A / h_o   (le stock est stationnaire au taux e₀)

S_j(θ_survie) de 0,85 à 0,93, centre 0,90, et A = 5 ans (D-402, SINE, choisis, non
vérifiés) ; e₀ = 7,61 % (Da Rin, Di Giacomo et Sembenelli 2011, tableau 3 p. 39 : la
France) ; h_o s'en calcule, 6,53 % au centre.

1. NAISSANCES (canal « creations_entreprises »). Pour la mesure m :

    Δτ_{m,t} = 100 Σ_{s ∈ N} P_{s,m,t} / (b Y_t)       points de taux apparent
    ΔE_{m,t} = −ε Δτ_{m,t} N₀ / 100                       sociétés créées en plus

   et pour la référence, E_t = (e₀ + δ(θ_idées)) N₀ / 100 ; ΔE_{«»,t} = δ N₀ / 100. ε =
   0,20 (Da Rin et al. 2011, tableau 4 p. 40 et p. 21-22, D-402), b = 0,092 (D-402),
   N les signaux de D-401 : l'IS, la CVAE et la C3S, les cotisations patronales nettes
   (comptées aussi par Mésange quand il tourne : le double compte décidé par le
   propriétaire, D-401), le PFU et les prélèvements sociaux du capital. δ(θ) : θ_idées,
   de −1 à +1 point, choisi, non vérifié.

2. FERMETURES (canal « fermetures_entreprises »). Pour la mesure m et la cellule c :

    Δm_{c,m,t} = −100 Σ_{s ∈ F} P_{s,m,t} π_{s,c} / (w_c s_VA Y_t)   points de marge
    ΔX^ind_{m,t} = Σ_c (e₀/100) β(θ_fermetures) (−Δm_{c,m,t}) N_c     sorties induites
    N_{k,t} = Σ_{u ≤ t} ΔE_{k,u} S(t − u) − Σ_{u ≤ t} ΔX^ind_{k,u} (1 − h_o)^(t − u)
              (+ N₀ pour la référence)
    X_{k,t} = N_{k,t−1} + E_{k,t} − N_{k,t}                         fermetures

   π_{s,c} la part de la cellule dans le choc du signal s : celle que la mesure donne par
   taille, répartie dans la taille selon l'assiette, ou sinon l'assiette (le résultat
   pour l'IS, la valeur ajoutée pour la CVAE et la C3S, la valeur ajoutée moins le
   résultat pour les cotisations) ; w_c la part de la cellule dans la valeur ajoutée ;
   (e₀/100) le hasard moyen des installées à l'état stationnaire. Une sortie induite
   aurait survécu au hasard h_o : elle manque au stock ensuite. β : de 0 à 0,06 par point
   de marge, centre 0,03, choisi, non vérifié. F : l'IS, la CVAE et la C3S, les
   cotisations (pas les prélèvements du capital des ménages).

3. PRODUCTIVITÉ (canal « productivite_demographie »). Pour la clé k :

    v̄_t = s_VA Y_t / N₀                                   valeur ajoutée par société
    ΔVA_{k,t} = v̄_t r c(θ) [Σ_u ΔE_{k,u} S(t − u) min(1, (t − u + 1)/M)
                            − Σ_u ΔX^ind_{k,u} (1 − h_o)^(t − u)]
    ΔY_{k,t} = ΔVA_{k,t} ;  recettes induites = ρ ΔY_{k,t}
    productivité moyenne_t = 1 + Σ_k ΔVA_{k,t} / (s_VA Y_t)

   r(θ_taille) la taille relative à maturité, 0,05 à 0,20, centre 0,10 ; M(θ_montée) la
   montée en charge, 8 à 3 ans, centre 5 (D-402, choisies, non vérifiées) ; s_VA = 0,554,
   la valeur ajoutée des sociétés (S11 + S12) sur le PIB de 2024 (Insee, t. 7.101, 7.201
   et 1.101), au lieu des 0,60 de D-402 ; c(θ) la
   productivité relative des sociétés à la marge, entrantes ou sortantes, de 0 à 1, centre
   0,5 : la ligne θ « productivite_creations » de D-402 (0 : une activité seulement
   déplacée ; 1 : la productivité moyenne). ρ le taux de prélèvements du départ. Avec
   S(a) = S_j^a pour tout âge et sans sortie induite, c'est l'équation de D-402.
   Le bloc écrit ΔY sur les emplois et les revenus non ventilés (un effet d'offre sans
   emploi désigné, dit ; le cadre en ferme le PIB, D-411), ρ ΔY sur l'effet induit sur
   le solde, et l'indice de productivité (non additif).

TOUT EST LINÉAIRE dans les signaux : une hausse et une baisse de même montant donnent des
écarts opposés ; θ ne change que la pente, de façon monotone.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from impots.jumeau.blocs.entreprises import (
    CREATIONS_ROW,
    FERMETURES_ROW,
    IDEES_ROW,
    MONTEE_ROW,
    SURVIE_ROW,
    TAILLE_ROW,
    Parametres,
    Population,
    chemins,
    lire_theta,
    pib_scenario,
    taux_prelevements,
    ventiler,
)
from impots.jumeau.pas import Contexte

TAILLES_ORDRE = ("micro", "PME", "ETI", "GE")


def _base(p: Parametres, pop: Population) -> float:
    """Les créations de la référence au taux e₀, sans θ."""
    return p.taux_entree_base / 100.0 * pop.stock


class Naissances:
    nom = "naissances"
    ecrit = ("creations_societes",)
    thetas = (IDEES_ROW,)
    remplace: tuple[str, ...] = ()
    porte = ("creations_entreprises",)

    def __init__(self, population: Population, parametres: Parametres) -> None:
        self.pop, self.p = population, parametres
        self.lit = tuple(parametres.signaux_naissances)

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        p, n0 = self.p, self.pop.stock
        delta = p.idees.a(lire_theta(ctx, IDEES_ROW))
        out: dict[str, Any] = {"": _base(p, self.pop) + delta / 100.0 * n0}
        y = pib_scenario(ctx, ctx.k)
        for m, chemin in chemins(ctx, self.lit).items():
            taux = 100.0 * chemin[ctx.k] / (p.assiette_part_pib * y)
            out[m] = -p.elasticite.centre * taux * n0 / 100.0
        return {"creations_societes": out}


def ecarts_entrees(ctx: Contexte, p: Parametres, pop: Population
                   ) -> dict[str, list[np.ndarray]]:
    """ΔE_{k,u}, u de 0 à k, par clé : les créations lues, moins la base pour « »."""
    out = chemins(ctx, ("creations_societes",))
    base = _base(p, pop)
    if "" in out:
        out[""] = [v - base for v in out[""]]
    return out


class Fermetures:
    nom = "fermetures"
    ecrit = ("sorties_induites", "stock_societes", "fermetures_societes")
    thetas = (FERMETURES_ROW, SURVIE_ROW)
    remplace: tuple[str, ...] = ()
    porte = ("fermetures_entreprises",)

    def __init__(self, population: Population, parametres: Parametres) -> None:
        self.pop, self.p = population, parametres
        self.lit = (*parametres.signaux_fermetures, "creations_societes")
        self._cles = {s: population.cle(parametres.cles_de_repartition[s])
                      for s in parametres.signaux_fermetures}

    def _repartition(self, mesure: Any, annee: int, signal_: str) -> np.ndarray:
        """π_{s,c} : la part de chaque cellule dans le choc du signal."""
        base = self._cles[signal_]
        tailles = ventiler(mesure, annee, signal_) if mesure is not None else None
        if tailles is None:
            return base / base.sum()
        total = sum(tailles.values())
        if total == 0.0:
            return np.zeros_like(base)
        parts = np.zeros_like(base)
        for taille, montant in tailles.items():
            dans = np.array([t == taille for t in self.pop.taille])
            assiette = base[dans].sum()
            if assiette <= 0.0:
                assiette_va = self.pop.valeur_ajoutee[dans]
                parts[dans] = montant / total * assiette_va / assiette_va.sum()
            else:
                parts[dans] = montant / total * base[dans] / assiette
        return parts

    def induites(self, ctx: Contexte, m: str, j: int, beta: np.ndarray) -> np.ndarray:
        """ΔX^ind_{m,j}, depuis les signaux de l'année j."""
        p, pop = self.p, self.pop
        etat = ctx.passe(j) if j < ctx.k else None
        mesure = next((x for x in ctx.mesures if x.identifiant == m), None)
        annee = ctx.annee - (ctx.k - j)
        va = pop.part_va() * p.part_va_societes_pib * pib_scenario(ctx, j)
        total = np.zeros((len(pop.societes), ctx.n))
        for s in p.signaux_fermetures:
            parts = (etat.par_mesure(s) if etat is not None else ctx.par_mesure(s))
            choc = parts.get(m)
            if choc is None:
                continue
            pi = self._repartition(mesure, annee, s)
            total = total + np.outer(pi / va, choc)
        marge = -100.0 * total
        return (p.taux_entree_base / 100.0) * beta * (-(marge * pop.societes[:, None])
                                                      .sum(axis=0))

    def stock(self, entrees: list[np.ndarray], sorties: list[np.ndarray], t: int,
              sj: np.ndarray) -> np.ndarray:
        p = self.p
        survie_o = 1.0 - p.hasard_installees(sj)
        total = 0.0
        for u in range(t + 1):
            total = (total + entrees[u] * p.survie(t - u, sj)
                     - sorties[u] * survie_o ** (t - u))
        return np.zeros_like(entrees[0]) + total

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        p, pop, k = self.p, self.pop, ctx.k
        beta = p.semi_elasticite_marge.a(lire_theta(ctx, FERMETURES_ROW))
        sj = p.survie_jeunes.a(lire_theta(ctx, SURVIE_ROW))
        entrees = ecarts_entrees(ctx, p, pop)
        signaux = chemins(ctx, p.signaux_fermetures)
        cles = sorted(set(entrees) | set(signaux) | {""})
        zero = np.zeros(ctx.n)
        out: dict[str, dict[str, Any]] = {c: {} for c in self.ecrit}
        for cle in cles:
            de = entrees.get(cle, [zero] * (k + 1))
            dx = ([self.induites(ctx, cle, j, beta) for j in range(k + 1)] if cle in signaux
                  else [zero] * (k + 1))
            maintenant = self.stock(de, dx, k, sj)
            avant = self.stock(de, dx, k - 1, sj) if k else zero
            if cle == "":
                maintenant, avant = maintenant + pop.stock, avant + pop.stock
                creees = de[k] + _base(p, pop)
            else:
                creees = de[k]
            out["sorties_induites"][cle] = dx[k]
            out["stock_societes"][cle] = maintenant
            out["fermetures_societes"][cle] = avant + creees - maintenant
        return out


class Productivite:
    nom = "productivite"
    ecrit = ("emplois_non_ventiles", "revenus_non_ventiles", "solde_induit",
             "productivite_moyenne")
    lit = ("creations_societes", "sorties_induites")
    thetas = (CREATIONS_ROW, SURVIE_ROW, MONTEE_ROW, TAILLE_ROW)
    remplace: tuple[str, ...] = ()
    porte = ("productivite_demographie",)

    def __init__(self, population: Population, parametres: Parametres) -> None:
        self.pop, self.p = population, parametres

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        p, pop, k = self.p, self.pop, ctx.k
        c = lire_theta(ctx, CREATIONS_ROW)  # c de D-402 : 0 à 1, centre ½ (bas 0, haut 1)
        y = pib_scenario(ctx, k)
        va_societes = p.part_va_societes_pib * y
        par_societe = va_societes / pop.stock
        rho = taux_prelevements(ctx)
        sj = p.survie_jeunes.a(lire_theta(ctx, SURVIE_ROW))
        montee = p.montee_en_charge_ans.a(lire_theta(ctx, MONTEE_ROW))
        taille = p.taille_relative.a(lire_theta(ctx, TAILLE_ROW))
        entrees = ecarts_entrees(ctx, p, pop)
        sorties = chemins(ctx, ("sorties_induites",))
        survie_o = 1.0 - p.hasard_installees(sj)
        out: dict[str, dict[str, Any]] = {n: {} for n in self.ecrit}
        total = np.zeros(ctx.n)
        zero = np.zeros(ctx.n)
        for cle in sorted(set(entrees) | set(sorties)):
            de = entrees.get(cle, [zero] * (k + 1))
            dx = sorties.get(cle, [zero] * (k + 1))
            poids = zero
            for u in range(k + 1):
                rampe = np.minimum(1.0, (k - u + 1) / montee)
                poids = (poids + de[u] * p.survie(k - u, sj) * rampe
                         - dx[u] * survie_o ** (k - u))
            dva = par_societe * taille * c * poids
            if not np.any(dva) and cle == "":
                continue
            out["emplois_non_ventiles"][cle] = dva
            out["revenus_non_ventiles"][cle] = dva
            out["solde_induit"][cle] = rho * dva
            total = total + dva
        out["productivite_moyenne"] = {"": 1.0 + total / va_societes}
        return out
