"""L'effet papillon d'un programme, regardé d'un œil critique (but 27, volet `papillon`,
D-500 à D-503). Le programme regardé est celui de Mélenchon (D-490).

CE QUE CE MODULE AJOUTE AU JUMEAU, et rien d'autre :

1. LA RÉMUNÉRATION PUBLIQUE (D-500, `remuneration_publique`). Une passe d'un point
   d'indice porte, comme toute passe, ses prélèvements en impulsions de Mésange : les
   cotisations des APU employeurs (−12,5 Md€ pour +10 % chez Mélenchon) et les
   cotisations salariales des agents. Le mode structurel les lisait comme une hausse du
   coût du travail privé (bloc `emploi` : −39,5 milliers d'emplois en 2035) et comme un
   coin fiscalo-social du privé (bloc `salaires`). Ce ne sont ni l'un ni l'autre : les
   APU les paient à leurs propres caisses. Elles sortent des impulsions et vont dans
   `Mesure.prelevements_publics`, que seul le compte des sous-secteurs lit (les caisses
   les reçoivent : le partage de D-487 ne bouge pas). Convention nommée
   « remuneration_publique », portée sur chaque année qu'elle touche.

2. LES MESURES SEULES (D-502, `mesures_seules`). Le rapport d'un programme mêle ses
   employeurs (le Smic, la fin des exonérations au-delà de 2 Smic, le point d'indice) :
   le mode structurel le refuse (D-487). La convention « mesures_seules » le fait tourner
   comme ses mesures, chacune avec sa ventilation et sa mesure structurelle (le Smic par
   `travail.mesure_smic`, le point d'indice par la rémunération publique, le PFU par sa
   propre passe), plus une mesure d'interaction : chaque année, ce que la passe du
   programme coûte de plus que la somme de ses mesures, sur le solde (statique, sans
   comportement), et l'écart de ses cotisations des employeurs, privées (le Smic et les
   exonérations au-delà de 2 Smic sur la même base), en impulsion et en impôt des
   entreprises. La somme des coûts des mesures et de l'interaction est le coût du
   programme, au bit (`verifier_somme`).

3. LES VÉRIFICATIONS (D-500, `identites`) : chaque année, la décomposition de Δb9 par
   bloc et par mesure, la récurrence de la dette, la conservation du choc statique.

4. EN REGARD, HORS DE L'ÉTAT (D-501) : le taux de la dette qui monte avec elle
   (`prime_de_risque`, Laubach 2009) ; les dividendes et la suppression du PFU
   (`dividendes_pfu`, Bach et al. 2024, les paramètres du canal C10) ; l'emploi par
   tranche d'une fin des exonérations au-delà de 2 Smic (`emploi_exonerations`,
   Bozio-Wasmer). Comme `travail.emploi_par_tranche` : ils ne changent aucun nombre du
   jumeau, ils se lisent à côté.

5. L'ÉTUDE SIMPLIFIÉE (D-503) : la sensibilité de la dette de 2035 à chaque θ, un à la
   fois (`sensibilites`), et la cascade réduite à quelques flèches (`cascade_simple`).

Le module n'importe au chargement que numpy et yaml : la page du jumeau le lit pour le
texte de ses conventions (`navigateur._conventions`).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import yaml

PARAMETRES = Path(__file__).resolve().parent / "parametres" / "papillon.yaml"

#: Les instruments qu'une passe de la rémunération publique porte sur la paie des agents.
INSTRUMENTS_PAIE = ("cotisations_employeurs", "cotisations_employeurs_ciblees",
                    "cotisations_salaries")
CONVENTION_PUBLIQUE = "remuneration_publique"
CONVENTION_SEULES = "mesures_seules"
TEXTES = {
    CONVENTION_PUBLIQUE: (
        "convention « remuneration_publique » (D-500) : les cotisations prélevées sur la "
        "paie des agents publics (employeurs et salariés) ne sont pas des impulsions sur "
        "le coût du travail privé ; elles ne vont qu'au compte des sous-secteurs"),
    CONVENTION_SEULES: (
        "convention « mesures_seules » (D-502) : le programme tourne comme ses mesures, "
        "chacune avec sa ventilation, plus l'interaction de sa passe (son coût en plus de "
        "la somme des mesures, sur le solde ; l'écart de ses cotisations des employeurs, "
        "privées) ; pas une passe du programme ventilée"),
}


class PapillonError(ValueError):
    """Un programme que la convention ne sait pas séparer."""


def parametres() -> dict[str, Any]:
    return yaml.safe_load(PARAMETRES.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 1. la rémunération publique
# --------------------------------------------------------------------------- #
def remuneration_publique(mesure: Any) -> Any:
    """La mesure d'un point d'indice sans les cotisations de la paie publique dans ses
    impulsions : elles passent dans `prelevements_publics` (D-500)."""
    impulsions, publics = {}, {}
    for a, imp in (mesure.impulsions or {}).items():
        imp = dict(imp)
        paie = {i: float(imp.pop(i)) for i in INSTRUMENTS_PAIE if i in imp}
        impulsions[a] = imp
        if paie:
            publics[a] = paie
    if not publics:
        return mesure
    conventions = {axe: dict(v) for axe, v in (mesure.conventions or {}).items()}
    conventions["impulsions"] = dict.fromkeys(sorted(publics), CONVENTION_PUBLIQUE)
    return dataclasses.replace(mesure, impulsions=impulsions, prelevements_publics=publics,
                               conventions=conventions)


# --------------------------------------------------------------------------- #
# 2. les mesures seules
# --------------------------------------------------------------------------- #
def cles(session: Any, slug: str) -> tuple[str, list[str]]:
    from impots.jumeau.financement.programme import cles_mesures

    return f"pres2027_{slug}_programme", cles_mesures(session, slug)


def _employeurs(imp: Mapping[str, float]) -> float:
    return float(imp.get("cotisations_employeurs", 0.0)
                 + imp.get("cotisations_employeurs_ciblees", 0.0))


def interaction(session: Any, slug: str, vue: str, convention: str | None = None) -> Any:
    """La mesure d'interaction de la passe du programme (D-502) : chaque année, son coût
    moins la somme des coûts de ses mesures (`couts`, sur le solde, sans canal de
    comportement), et l'écart de ses cotisations des employeurs (impulsion uniforme et
    impôt des entreprises : il vient du Smic et des allègements sur la même base,
    privés). Ses ménages ne sont pas portés : l'écart se lit sur le solde seul."""
    from impots.jumeau.mesures import RAPPORT, Mesure

    cle_p, seules = cles(session, slug)
    p = session.mesure(cle_p, vue, convention)
    ms = [session.mesure(c, vue, convention) for c in seules]
    for m in ms:
        if tuple(m.annees) != tuple(p.annees):
            raise PapillonError(f"« {m.identifiant} » sur {m.annees}, le programme sur "
                                f"{p.annees}")
    couts, impulsions, entreprises, prelevements = {}, {}, {}, {}
    for a in p.annees:
        couts[a] = p.couts[a] - sum(m.couts[a] for m in ms)
        de = _employeurs(p.impulsions.get(a, {})) - sum(
            _employeurs(m.impulsions.get(a, {})) for m in ms)
        impulsions[a] = {"cotisations_employeurs": de}
        entreprises[a] = {"cotisations_employeurs": -de}
        prelevements[a] = -de
    return Mesure(
        identifiant=f"pres2027_{slug}_interaction", origine=RAPPORT,
        libelle=f"Interaction de la passe du programme ({slug})", auteur=p.auteur,
        annees=tuple(p.annees), couts=couts, canaux=dict.fromkeys(p.annees),
        impulsions=impulsions, entreprises=entreprises, prelevements=prelevements,
        macro=p.macro, rapport=p.rapport, commit=p.commit,
        conventions={"interaction": dict.fromkeys(p.annees, CONVENTION_SEULES)},
        non_portes={"menages": "l'interaction de la passe ne se ventile pas par décile : "
                               "elle ne se lit que sur le solde"})


def mesures_seules(session: Any, slug: str, vue: str,
                   convention: str | None = "parts_premiere_annee") -> list[Any]:
    """Le programme en structurel par la convention « mesures_seules » (D-502) : ses
    mesures, chacune comme le mode structurel la lit, puis l'interaction."""
    _, seules = cles(session, slug)
    out = [session.mesure_structurel(c, vue, convention) for c in seules]
    out.append(interaction(session, slug, vue, convention))
    return out


def verifier_somme(session: Any, slug: str, vue: str, convention: str | None = None,
                   tolerance: float = 1e-9) -> dict[int, float]:
    """Σ coûts des mesures + interaction − coût du programme, chaque année (Md€) : nul."""
    cle_p, seules = cles(session, slug)
    p = session.mesure(cle_p, vue, convention)
    i = interaction(session, slug, vue, convention)
    out = {}
    for a in p.annees:
        r = sum(session.mesure(c, vue, convention).couts[a] for c in seules) + i.couts[a]
        out[a] = r - p.couts[a]
        if abs(out[a]) > tolerance:
            raise PapillonError(f"{a} : la somme des mesures et de l'interaction s'écarte "
                                f"du programme de {out[a]:+.3e} Md€")
    return out


# --------------------------------------------------------------------------- #
# les trajectoires
# --------------------------------------------------------------------------- #
def trajectoire(session: Any, mesures: Sequence[Any], *, cle: str, mode: str = "structurel",
                theta: Mapping[str, Any] | None = None) -> tuple[Any, dict[str, Any]]:
    """La trajectoire de `mesures` ensemble ; θ½ pour chaque θ lu, sauf ceux donnés."""
    from impots.jumeau.trajectoire import calculer

    depart, entrees, blocs, boucles = session._modele(mode, mesures[0], cle)
    reg = session.thetas(mode, list(mesures), blocs)
    th: dict[str, Any] = {t["cle"]: 0.5 for t in reg if t["lu"]}
    th |= dict(theta or {})
    traj = calculer(depart, entrees=entrees, mesures=list(mesures), theta=th, blocs=blocs,
                    boucles=boucles)
    return traj, th


def ecarts(traj: Any, tirage: int = 0) -> dict[str, list[float]]:
    """Les écarts d'une trajectoire, par année : dette (points de PIB), B9 (Md€), PIB (%),
    emploi (milliers), quand le mode les porte."""
    out = {"dette_pts": [100 * float(x) for x in traj.difference("ratio_dette")[:, tirage]],
           "b9": [float(x) for x in traj.difference("b9")[:, tirage]],
           "pib_pct": [100 * float(x) for x in traj.ecart_pib[:, tirage]]}
    for c in ("emploi_total", "c_menages"):
        if traj.variante[0].present(c):
            out[c] = [float(x) for x in traj.difference(c)[:, tirage]]
    return out


def par_bloc(traj: Any, champ: str, k: int = -1, tirage: int = 0
             ) -> dict[tuple[str, str], float]:
    """L'écart d'un champ additif de l'année k, par (bloc, mesure)."""
    v, r = traj.variante[k].de(champ), traj.reference[k].de(champ)
    out = {}
    for c in sorted(set(v) | set(r)):
        x = float(np.asarray(v.get(c, 0.0)).reshape(-1)[tirage]
                  - np.asarray(r.get(c, 0.0)).reshape(-1)[tirage])
        if abs(x) > 1e-12:
            out[c] = x
    return out


# --------------------------------------------------------------------------- #
# 3. les identités, écrites
# --------------------------------------------------------------------------- #
def identites(traj: Any, mesures: Sequence[Any], tolerance: float = 1e-9
              ) -> dict[str, float]:
    """Le plus grand résidu, en part du PIB, sur toutes les années, de quatre identités
    que l'écart (variante − référence) doit tenir, au-delà de celles que le cadre vérifie
    à chaque pas (`identites`, sur les niveaux) :

    * « b9_par_bloc » : ΔB9_t = Σ_(bloc, mesure) ΔB9_t ; la cascade se somme au solde ;
    * « dette_recurrence » : ΔD_t = ΔD_{t−1} − ΔB9_t + ΔSFA_t ; aucun flux hors du solde ;
    * « ratio_par_cle » : Δb_t = Σ_clé decomposition_t ; la dette en points se décompose ;
    * « statique » : la contribution du bloc `mesures` au solde primaire de chaque mesure
      (B9 la porte aussi, avec les intérêts de la dette qu'elle a faite) égale son
      choc lu (−coût + recettes des canaux, et ses chocs déclarés) : aucune mesure n'est
      comptée deux fois, ni oubliée. Le choc lu est relu à θ par `blocs.mesures`.

    Rend les résidus ; refuse au-delà de la tolérance."""
    from impots.jumeau.blocs.mesures import Mesures
    from impots.jumeau.pas import Contexte

    pire = {"b9_par_bloc": 0.0, "dette_recurrence": 0.0, "ratio_par_cle": 0.0,
            "statique": 0.0}
    n = traj.reference[0].n
    for k, annee in enumerate(traj.annees):
        var, ref = traj.variante[k], traj.reference[k]
        pib = var["pib"]
        d_b9 = var["b9"] - ref["b9"]
        cles = set(var.de("b9")) | set(ref.de("b9"))
        z = np.zeros(n)
        somme = sum((var.de("b9").get(c, z) - ref.de("b9").get(c, z) for c in cles), z)
        pire["b9_par_bloc"] = max(pire["b9_par_bloc"], float(np.max(np.abs(
            (d_b9 - somme) / pib))))
        d_d = var["dette"] - ref["dette"]
        d_prec = (traj.variante[k - 1]["dette"] - traj.reference[k - 1]["dette"]) if k else z
        flux = sum(((var[c] - ref[c]) for c in ("sfa", "ecart_millesime_dette",
                                                 "ecart_eurostat") if var.present(c)), z)
        pire["dette_recurrence"] = max(pire["dette_recurrence"], float(np.max(np.abs(
            (d_d - (d_prec - d_b9 + flux)) / pib))))
        dec = sum(traj.decomposition(annee).values(), z)
        pire["ratio_par_cle"] = max(pire["ratio_par_cle"], float(np.max(np.abs(
            dec - traj.delta_b[k]))))
        # le choc statique relu, mesure par mesure
        ctx = Contexte(annee=annee, k=k, n=n, theta=traj.theta, entrees=None, prec=None,
                       courant=None, historique=list(traj.variante[:k]),
                       reference=list(traj.reference), mesures=list(mesures),
                       depart=traj.reference[0])
        lus = Mesures().contribue(ctx)
        for m in mesures:
            attendu = z.copy()
            for champ, parts in lus.items():
                if champ.startswith("impulsion_") or champ == "prelevements_entreprises":
                    continue
                if m.identifiant in parts:
                    from impots.jumeau.champs import DEPENSES

                    signe = -1.0 if champ in DEPENSES else 1.0
                    attendu = attendu + signe * parts[m.identifiant]
            # le solde primaire : B9 porte aussi, sous la même clé, les intérêts de la
            # dette que ce choc a faite les années d'avant
            dans = (var.de("solde_primaire").get(("mesures", m.identifiant), z)
                    - ref.de("solde_primaire").get(("mesures", m.identifiant), z))
            pire["statique"] = max(pire["statique"], float(np.max(np.abs(
                (dans - attendu) / pib))))
    for nom, r in pire.items():
        if r > tolerance:
            raise PapillonError(f"identité « {nom} » : résidu {r:.3e} du PIB")
    return pire


# --------------------------------------------------------------------------- #
# 4. en regard, hors de l'état
# --------------------------------------------------------------------------- #
def _par_morceaux(theta: float, bas: float, centre: float, haut: float) -> float:
    t = float(theta)
    return bas + 2 * t * (centre - bas) if t <= 0.5 else centre + (2 * t - 1) * (haut - centre)


def prime_de_risque(traj: Any, entrees: Any, theta: float = 0.5,
                    params: Mapping[str, Any] | None = None, tirage: int = 0
                    ) -> dict[str, Any]:
    """Le taux de la dette qui monte avec elle (D-501), en regard de la trajectoire.

    Le jumeau charge la dette d'une mesure au taux marginal du scénario, fixe (comme
    Mésange : « à taux d'intérêt réels constants », p. 101). Ici, chaque point de dette
    en plus relève le taux de marché de β(θ) points de base (Laubach 2009 ; Furceri,
    Gonçalves et Li 2025), et ce taux ne gagne la dette qu'à mesure qu'elle se
    refinance : la part r_t = min(1, t / M) du stock de référence, M la durée de vie
    moyenne de la dette négociable (AFT). Pour l'année t (rang k, la dette d'ouverture) :

        ΔI_t = β Δb_{t−1} r_t D^ref_{t−1} + ρ ΔI-dette_{t−1}
        ΔD^p_t = (1 + ρ) ΔD^p_{t−1} + β Δb_{t−1} r_t D^ref_{t−1}

    ρ le taux marginal du scénario, Δb_{t−1} l'écart de dette en points de la
    trajectoire augmenté de ΔD^p (le canal se nourrit de lui-même). Le PIB n'en est pas
    changé : des intérêts versés aux créanciers, sans canal de demande (dit)."""
    p = (params or parametres())["prime_de_risque"]
    beta = _par_morceaux(theta, *(float(p["beta_pb"][c]["valeur"])
                                  for c in ("bas", "centre", "haut"))) * 1e-4
    m_ans = float(p["duree_vie_moyenne_ans"]["valeur"])
    rho = float(entrees.taux_marginal)
    dp = 0.0
    extra_d, extra_pts = [], []
    for k in range(len(traj.annees)):
        ref = traj.reference[k]
        pib_v = float(traj.variante[k]["pib"][tirage])
        if k == 0:
            db_prec, d_ref_prec = 0.0, float(ref["dette_ouverture"][tirage])
        else:
            pv = traj.variante[k - 1]
            db_prec = 100 * (float(pv["ratio_dette"][tirage])
                             - float(traj.reference[k - 1]["ratio_dette"][tirage])) \
                + 100 * dp / float(pv["pib"][tirage])
            d_ref_prec = float(traj.reference[k - 1]["dette"][tirage])
        part = min(1.0, (k + 1) / m_ans)
        dp = (1.0 + rho) * dp + beta * db_prec * part * d_ref_prec
        extra_d.append(dp)
        extra_pts.append(100 * dp / pib_v)
    return {"theta": theta, "beta_pb": beta * 1e4, "duree_vie_moyenne_ans": m_ans,
            "taux_marginal": rho, "dette_md": extra_d, "dette_pts": extra_pts}


def dividendes_pfu(theta: float = 0.5, tmi: Sequence[float] = (0.30, 0.41, 0.45),
                   params: Mapping[str, Any] | None = None) -> list[dict[str, float]]:
    """La suppression du PFU sur un euro de dividende d'un foyer à la tranche `tmi`, avec
    la réponse des dividendes du canal C10 (D-501), hors de la passe.

    τ_0 = PFU + prélèvements sociaux ; au barème, τ_1 = PS + TMI (1 − abattement −
    CSG déductible), l'abattement de 40 % (CGI, art. 158, 3-2°) et 6,8 points de CSG
    déductibles (CGI, art. 154 quinquies). La réponse, celle du canal C10
    (`behavioural.channels.dividend_response`) : ε = s ε_p + (1 − s) ε_a, aux θ de
    `dividends.yaml`, et D_1 = D_0 ((1 − τ_1)/(1 − τ_0))^ε, forme à élasticité
    constante (le canal linéarise ; au-delà de la variation de 6 % que Bach et al. ont
    observée, l'une et l'autre extrapolent, dit). Rend, par euro de dividende d'avant :
    la recette mécanique τ_1 − τ_0, la recette avec réponse τ_1 D_1 − τ_0, et le salaire
    que les propriétaires se reversent (le déplacement de D-252, de sens contraire), qui
    n'est pas valorisé ici. La CEHR n'est pas comptée."""
    from impots.predictif.rejouer import value_at

    p = (params or parametres())["pfu"]
    div = yaml.safe_load((Path(__file__).resolve().parents[1] / "behavioural" / "parameters"
                          / "dividends.yaml").read_text(encoding="utf-8"))["parameters"]

    def ligne(cle: str) -> float:
        v = div[cle]["value"]
        return float(value_at({"low": v["low"], "central": v["central"], "high": v["high"],
                               "un": div[cle]["theta"]["un"]}, theta))

    s = ligne("dividend_share_firm_owners")
    eps = s * ligne("dividend_elasticity_firm_owners") + (1 - s) * ligne(
        "dividend_elasticity_other_holders")
    ps, pfu = float(p["prelevements_sociaux"]["valeur"]), float(p["taux_ir"]["valeur"])
    abat, csgd = float(p["abattement"]["valeur"]), float(p["csg_deductible"]["valeur"])
    t0 = ps + pfu
    out = []
    for t in tmi:
        t1 = ps + t * (1.0 - abat - csgd)
        d1 = ((1 - t1) / (1 - t0)) ** eps
        out.append({"tmi": t, "tau_0": t0, "tau_1": t1, "elasticite": eps,
                    "dividendes_apres": d1, "recette_mecanique": t1 - t0,
                    "recette_avec_reponse": t1 * d1 - t0,
                    "taux_laffer": 1.0 / (1.0 + eps)})
    return out


def emploi_exonerations(plafond: float = 2.0, theta: float = 0.5,
                        emploi_marchand_milliers: float | None = None) -> dict[str, Any]:
    """La fin de la RGDU au-delà de `plafond` Smic, par tranche, avec la matrice de
    Bozio-Wasmer (tableau 4.1, `travail.yaml`), en regard du bloc `emploi` (D-501) :
    ΔS_t / S_t la hausse du coût de chaque tranche (l'allègement perdu des postes payés
    au-delà du plafond), E_t = Σ_s ε_ts ΔS_s / S_s à long terme, mis à l'échelle de θ."""
    from impots.jumeau.blocs import travail

    p = travail.charger()
    m = p.multiples
    a = m * travail.rgdu(p, m) * (m >= plafond)
    s = m * (1.0 + p.tau_e) - m * travail.rgdu(p, m)
    ds, st, eff = (np.zeros(travail.N_TRANCHES) for _ in range(3))
    np.add.at(ds, p.tranche, a * p.effectifs)
    np.add.at(st, p.tranche, s * p.effectifs)
    np.add.at(eff, p.tranche, p.effectifs)
    choc = ds / st
    echelle = _par_morceaux(theta, p.echelle["bas"], p.echelle["centre"], p.echelle["haut"])
    lt = (p.matrice @ choc) * echelle
    out = {"tranches": list(p.noms), "hausse_cout": choc.tolist(),
           "dln_emploi": lt.tolist(), "parts_eqtp": (eff / eff.sum()).tolist(),
           "dln_emploi_total": float((lt * eff).sum() / eff.sum()),
           "part_cout_masse": float(ds.sum() / st.sum())}
    if emploi_marchand_milliers is not None:
        out["emploi_milliers"] = out["dln_emploi_total"] * emploi_marchand_milliers
    return out


# --------------------------------------------------------------------------- #
# 5. l'étude simplifiée
# --------------------------------------------------------------------------- #
def sensibilites(session: Any, mesures: Sequence[Any], *, cle: str,
                 mode: str = "structurel", annee_index: int = -1,
                 theta: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    """La dette de 2035 (points de PIB) quand chaque θ lu va à 0 puis à 1, les autres à ½,
    en une seule trajectoire vectorisée (tirage 0 : tous à ½). Rangé par portée."""
    from impots.jumeau.trajectoire import calculer

    depart, entrees, blocs, boucles = session._modele(mode, mesures[0], cle)
    reg = [t for t in session.thetas(mode, list(mesures), blocs) if t["lu"]]
    base = {t["cle"]: 0.5 for t in reg} | dict(theta or {})
    noms = [t["cle"] for t in reg]
    cols = {c: [base[c]] for c in noms}
    for c in noms:
        for x in (0.0, 1.0):
            for d in noms:
                cols[d].append(x if d == c else base[d])
    th = {c: np.asarray(v, dtype=float) for c, v in cols.items()}
    traj = calculer(depart, entrees=entrees, mesures=list(mesures), theta=th, blocs=blocs,
                    boucles=boucles)
    db = 100 * traj.difference("ratio_dette")[annee_index]
    b9 = traj.difference("b9")[annee_index]
    emploi = (traj.difference("emploi_total")[annee_index]
              if traj.variante[0].present("emploi_total") else None)
    out = []
    for i, c in enumerate(noms):
        a0, a1 = 1 + 2 * i, 2 + 2 * i
        ligne = next(t for t in reg if t["cle"] == c)
        out.append({"cle": c, "bloc": ligne["bloc"], "centre": float(db[0]),
                    "a_zero": float(db[a0]), "a_un": float(db[a1]),
                    "portee": float(abs(db[a1] - db[a0])),
                    "b9_centre": float(b9[0]), "b9_a_zero": float(b9[a0]),
                    "b9_a_un": float(b9[a1]),
                    "emploi_centre": None if emploi is None else float(emploi[0]),
                    "emploi_a_zero": None if emploi is None else float(emploi[a0]),
                    "emploi_a_un": None if emploi is None else float(emploi[a1])})
    return sorted(out, key=lambda r: -r["portee"])


#: Les flèches de la cascade simplifiée (D-503) : chaque bloc du mode structurel rangé
#: dans l'une d'elles, par ce qu'il fait au solde.
FLECHES = {
    "statique": ("mesures",),
    "consommation": ("consommation",),
    "travail_salaires_emploi": ("travail", "salaires", "emploi", "emploi_public"),
    "commerce_prix": ("commerce",),
    "entreprises_investissement": ("investissement", "implantation", "chocs_entreprises",
                                   "naissances", "fermetures", "productivite",
                                   "recettes_induites"),
    "demande_publique": ("demande_publique",),
    "mesange_et_creations": ("mesange", "creations"),
    "interets_et_pib": (),
}


def cascade_simple(traj: Any, annee: int | None = None, tirage: int = 0
                   ) -> dict[str, Any]:
    """Δb de l'année (points de PIB) rangé en flèches (`FLECHES`) : la décomposition de la
    trajectoire (`Trajectoire.decomposition`, intérêts et dénominateur compris, par bloc
    qui les porte), sommée par flèche ; ce qui n'est porté par aucun bloc nommé va à
    « interets_et_pib » (la référence, le dénominateur). La somme est Δb, au bit près."""
    annee = annee if annee is not None else traj.annees[-1]
    dec = traj.decomposition(annee)
    vers = {b: f for f, blocs in FLECHES.items() for b in blocs}
    out = dict.fromkeys(FLECHES, 0.0)
    par_mesure: dict[str, float] = {}
    for (origine, mesure), v in dec.items():
        x = 100 * float(np.asarray(v).reshape(-1)[tirage])
        out[vers.get(origine, "interets_et_pib")] += x
        if mesure:
            par_mesure[mesure] = par_mesure.get(mesure, 0.0) + x
    total = 100 * float(traj.delta_b[traj.annees.index(annee), tirage])
    return {"annee": annee, "fleches": out, "par_mesure": par_mesure, "total": total,
            "residu": total - sum(out.values())}


__all__ = [
    "CONVENTION_PUBLIQUE",
    "CONVENTION_SEULES",
    "TEXTES",
    "cascade_simple",
    "dividendes_pfu",
    "emploi_exonerations",
    "identites",
    "interaction",
    "mesures_seules",
    "prime_de_risque",
    "remuneration_publique",
    "sensibilites",
    "trajectoire",
    "verifier_somme",
]
