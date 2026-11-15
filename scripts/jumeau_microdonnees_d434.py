"""Le jumeau sur des données fines, le volet `fines` du but 24 : les panneaux de D-434.

    PYTHONPATH=src python scripts/jumeau_microdonnees_d434.py --decrire   # panneaux, doses
    PYTHONPATH=src python scripts/jumeau_microdonnees_d434.py             # les estimations

`--decrire` ne fait aucune régression sur un résultat : il dit les panneaux (tailles,
années, grappes) et la variation des régresseurs qui reste après les effets fixes, ce que
D-434 lit avant tout calcul. Sans option, le script refuse de tourner si D-434 n'est pas
dans `docs/DECISIONS.md` du commit courant, puis écrit
`reports/jumeau/microdonnees_d434.json` : des coefficients, des écarts-types, des tailles,
aucune donnée individuelle.

Quatre familles (D-434) : E2, l'emploi par département × secteur (Urssaf) face à la dose
`travail` de la cellule (η) ; W1, la courbe des salaires sur les mêmes cellules et le
chômage localisé (b) ; K1, l'investissement des branches face au coût du capital de
l'IS et de la CVAE, par la réponse du bloc (ε_K) ; K2, l'accélérateur sur les mêmes
branches (β₀).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Any

import numpy as np

from impots.dette import comptes
from impots.jumeau import a_priori, thetas
from impots.jumeau import microdonnees as m
from impots.jumeau.blocs import investissement, valeurs_entreprises

RACINE = Path(__file__).resolve().parents[1]
RAPPORT = RACINE / "reports" / "jumeau" / "microdonnees_d434.json"
#: La semi-élasticité agrégée du salaire au chômage de Mésange (p. 64), b = 1.
SEMI_ELASTICITE_MESANGE = 0.018

ANS = [*range(2003, 2020), *range(2022, 2026)]
ANS_2019 = list(range(2003, 2020))
PLACEBO = list(range(2003, 2010))
DECALAGE_PLACEBO = 8
#: K1 : les doses de 2017 à 2025 posées sur 2003 à 2011.
PLACEBO_K = list(range(2003, 2012))
DECALAGE_PLACEBO_K = 14
#: Les branches de K1 et K2 : les branches marchandes de D-425 moins l'immobilier, dont
#: la FBCF est surtout le logement des ménages.
BRANCHES_K = tuple(b for b in m.BRANCHES if b != "LZ")


# --------------------------------------------------------------------------- #
# les panneaux
# --------------------------------------------------------------------------- #
def panneau_urssaf(cel: dict, parts: dict, chom: dict, regions: dict, g: float,
                   annees: list[int], y: str, regresseurs: list[tuple[str, int]],
                   effets: tuple[str, ...], tendances: bool = False) -> dict[str, Any]:
    """Les lignes (département, secteur, année). y : « emploi » (log de l'effectif) ou
    « salaire » (log de la masse sur l'effectif). Un régresseur : (« travail » ou
    « chomage », décalage). Une cellule sans effectif positif chaque année de
    l'échantillon, ou sans salaire de référence, est retirée entière."""
    ys, xs, fe, grappe, cell, temps, retirees = [], [], {e: [] for e in effets}, [], [], [], []
    for (d, s), v in sorted(cel.items()):
        if (d, s) not in parts or any(a not in v or v[a][0] <= 0 or v[a][1] <= 0
                                      for a in annees):
            retirees.append(f"{d}-{s}")
            continue
        for a in annees:
            eff, masse = v[a]
            ys.append(np.log(eff) if y == "emploi" else np.log(masse / eff))
            ligne = []
            for nom, dec in regresseurs:
                if nom == "travail":
                    ligne.append(m.dose_travail(parts[(d, s)], a + dec, g))
                else:
                    ligne.append(chom[d][a + dec])
            xs.append(ligne)
            cles = {"cellule": f"{d}|{s}", "dep_annee": f"{d}|{a}", "sect_annee": f"{s}|{a}",
                    "region_annee": f"{regions[d]}|{a}", "annee": str(a)}
            for e in effets:
                fe[e].append(cles[e])
            grappe.append(d)
            cell.append(f"{d}|{s}")
            temps.append(a - annees[0])
    noms = [f"{nom}{'' if dec == 0 else f'_t{dec:+d}'}" for nom, dec in regresseurs]
    return {"y": np.array(ys), "X": np.array(xs), "noms": noms,
            "effets": [fe[e] for e in effets if not (tendances and e == "cellule")],
            "grappe": grappe, "retirees": retirees,
            "tendance": (cell, temps) if tendances else None, "effets_noms": list(effets)}


def panneau_branches(series: dict, annees: list[int], regresseurs: list[tuple[str, int]],
                     y: str, tendances: bool = False) -> dict[str, Any]:
    """Les lignes (branche, année) de K1 et K2. `series` : {nom : {branche : {année :
    valeur}}}, « invest », « va », « dose » ; y : « niveau » (log I/VA) ou « croissance »
    (Δ log I) ; un régresseur : (« dose » ou « dva », décalage)."""
    ys, xs, fe1, fe2, cell, temps = [], [], [], [], [], []
    inv, va, dose = series["invest"], series["va"], series["dose"]
    for b in BRANCHES_K:
        for a in annees:
            if y == "niveau":
                ys.append(np.log(inv[b][a] / va[b][a]))
            else:
                ys.append(np.log(inv[b][a] / inv[b][a - 1]))
            ligne = []
            for nom, dec in regresseurs:
                t = a + dec
                ligne.append(dose[b][t] if nom == "dose"
                             else np.log(va[b][t] / va[b][t - 1]))
            xs.append(ligne)
            fe1.append(b)
            fe2.append(str(a))
            cell.append(b)
            temps.append(a - annees[0])
    noms = [f"{nom}{'' if dec == 0 else f'_t{dec:+d}'}" for nom, dec in regresseurs]
    return {"y": np.array(ys), "X": np.array(xs), "noms": noms,
            "effets": [fe2] if tendances else [fe1, fe2], "grappe": fe1, "retirees": [],
            "tendance": (cell, temps) if tendances else None,
            "effets_noms": ["annee"] if tendances else ["branche", "annee"]}


#: L'année de l'échelle du capital des branches : la dernière où la t. 7.101 publie la
#: consommation de capital fixe des SNF (2023 à 2025 sont vides dans ce millésime).
ANNEE_CAPITAL = 2022
PATRIMOINE_SNF = "insee_cn2024_t8202_patrimoine_snf.xlsx"


def ratio_capital_ccf() -> float:
    """Le capital net des SNF (t. 8.202, N11N) sur leur consommation de capital fixe
    (t. 7.101, P51C), en 2022 : l'échelle, commune aux branches, qui fait de leur CCF un
    capital net (une hypothèse : la même durée de vie moyenne du capital partout)."""
    def lire(fichier: str, feuille: str, code: str) -> float:
        rows = comptes._rows(fichier, feuille)
        col = comptes._year_columns(rows)
        r = next(r for r in rows if r[0] and str(r[0]).strip() == code)
        return float(r[col[ANNEE_CAPITAL]])

    return (lire(PATRIMOINE_SNF, "T_8202", "N11N")
            / lire(m.COMPTE_SNF, "T_7101", "P51C"))


def donnees() -> dict[str, Any]:
    k = m.constantes()
    cel = m.urssaf_departements()
    relatif = m.salaire_relatif(cel)
    salaires = m.distribution_nationale()
    parts = {c: m.parts_sous_seuils(salaires, r, m.SEUILS) for c, r in relatif.items()}
    chom = m.chomage_departements()
    regions = m.regions_departements()
    # les branches
    p = valeurs_entreprises.charger()
    expo = m.expositions(branches=True)
    inv = m.branches_cn(m.FBCF_BRANCHES, "T_6302 en niveau")
    va = m.branches_cn(m.VA_BRANCHES, "T_6202 en niveau")
    ccf = m.branches_cn(m.CCF_BRANCHES, "T_6461")
    ratio = ratio_capital_ccf()
    reponse = investissement.reponse_unitaire(p.rappel_trimestriel, p.retard_trimestriel)
    dose_k: dict[str, dict[int, float]] = {}
    chocs_k: dict[str, dict[int, float]] = {}
    for b in BRANCHES_K:
        capital = ratio * ccf[b][ANNEE_CAPITAL] * 1000.0
        chocs = {a: m.choc_cout_capital(expo[b], a, k, capital, p.taux_cout_usage)
                 for a in range(2000, 2041)}
        chocs_k[b] = chocs
        dose_k[b] = {a: m.dose_cout_capital(chocs, a, reponse) for a in range(2000, 2041)}
    return {"k": k, "cel": cel, "parts": parts, "chom": chom, "regions": regions,
            "branches": {"invest": inv, "va": va, "dose": dose_k}, "chocs_k": chocs_k,
            "ratio_capital_ccf": ratio, "taux_usage": p.taux_cout_usage, "parametres": p}


CELL = ("cellule", "dep_annee", "sect_annee")
SAL = ("cellule", "sect_annee")


def specifications(D: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any], str, int]]:
    """Les spécifications de D-434 : nom → (le θ, le panneau, les poids, le nombre de
    régresseurs d'intérêt, en tête)."""
    g = D["k"].g
    U = lambda an, y, reg, fe, t=False: panneau_urssaf(  # noqa: E731
        D["cel"], D["parts"], D["chom"], D["regions"], g, an, y, reg, fe, t)
    B = lambda an, reg, y, t=False: panneau_branches(D["branches"], an, reg, y, t)  # noqa: E731
    av = [a for a in ANS if a <= 2023]
    tr, ch = "travail", "chomage"
    dva = [("dva", 0), ("dva", -1), ("dva", -2)]
    return {
        "E2": ("emploi", U(ANS, "emploi", [(tr, 0)], CELL), "rademacher", 1),
        "E2_avance": ("emploi", U(av, "emploi", [(tr, 0), (tr, 2)], CELL), "rademacher", 2),
        "E2_placebo": ("emploi", U(PLACEBO, "emploi", [(tr, DECALAGE_PLACEBO)], CELL),
                       "rademacher", 1),
        "E2_tendances": ("emploi", U(ANS, "emploi", [(tr, 0)], CELL, True), "rademacher", 1),
        "E2_2019": ("emploi", U(ANS_2019, "emploi", [(tr, 0)], CELL), "rademacher", 1),
        "E2_sans_secteur_annee": ("emploi", U(ANS, "emploi", [(tr, 0)],
                                              ("cellule", "dep_annee", "annee")),
                                  "rademacher", 1),
        "W1": ("salaires", U(ANS, "salaire", [(ch, 0), (tr, 0)], SAL), "rademacher", 1),
        "W1_avance": ("salaires", U(av, "salaire", [(ch, 0), (ch, 2), (tr, 0)], SAL),
                      "rademacher", 2),
        "W1_retard": ("salaires", U(ANS, "salaire", [(ch, -1), (tr, 0)], SAL), "rademacher", 1),
        "W1_tendances": ("salaires", U(ANS, "salaire", [(ch, 0), (tr, 0)], SAL, True),
                         "rademacher", 1),
        "W1_region_annee": ("salaires", U(ANS, "salaire", [(ch, 0), (tr, 0)],
                                          ("cellule", "sect_annee", "region_annee")),
                            "rademacher", 1),
        "W1_2019": ("salaires", U(ANS_2019, "salaire", [(ch, 0), (tr, 0)], SAL),
                    "rademacher", 1),
        "K1": ("cout_capital", B(ANS, [("dose", 0)], "niveau"), "rademacher", 1),
        "K1_avance": ("cout_capital", B(av, [("dose", 0), ("dose", 2)], "niveau"),
                      "rademacher", 2),
        "K1_placebo": ("cout_capital", B(PLACEBO_K, [("dose", DECALAGE_PLACEBO_K)], "niveau"),
                       "rademacher", 1),
        "K1_tendances": ("cout_capital", B(ANS, [("dose", 0)], "niveau", True),
                         "rademacher", 1),
        "K1_2019": ("cout_capital", B(ANS_2019, [("dose", 0)], "niveau"), "rademacher", 1),
        "K2": ("accelerateur", B(ANS_2019, dva, "croissance"), "rademacher", 1),
        "K2_avance": ("accelerateur", B(list(range(2003, 2018)), [*dva, ("dva", 2)],
                                        "croissance"), "rademacher", 1),
        "K2_2025": ("accelerateur", B([*ANS_2019, 2024, 2025], dva, "croissance"),
                    "rademacher", 1),
        "K2_sans_retards": ("accelerateur", B(ANS_2019, [("dva", 0)], "croissance"),
                            "rademacher", 1),
    }


def _interet(nom: str, p: dict[str, Any], n: int) -> list[int]:
    """Les régresseurs dont on veut la p-valeur : ceux d'intérêt, plus l'avance de K2."""
    out = list(range(n))
    if nom == "K2_avance":
        out.append(p["noms"].index("dva_t+2"))
    return out


def decrire(D: dict[str, Any], specs: dict | None = None) -> dict[str, Any]:
    specs = specs or specifications(D)
    out: dict[str, Any] = {"g": D["k"].g, "ratio_capital_ccf": D["ratio_capital_ccf"],
                           "taux_usage": D["taux_usage"], "panneaux": {}}
    for nom, (theta, p, _, _n) in specs.items():
        effets = [m._codes(e) for e in p["effets"]]
        if p["tendance"] is None:
            Z = m.projeter(p["X"], effets)
        else:
            Z = m.projeter_tendances(p["X"], effets, m._codes(p["tendance"][0]),
                                     np.asarray(p["tendance"][1], dtype=float))
        out["panneaux"][nom] = {
            "theta": theta, "n": len(p["y"]), "grappes": len(set(p["grappe"])),
            "retirees": len(p["retirees"]), "effets": p["effets_noms"],
            "tendances": p["tendance"] is not None,
            "regresseurs": {p["noms"][j]: {"ecart_type_brut": float(p["X"][:, j].std()),
                                           "ecart_type_apres_effets": float(Z[:, j].std())}
                            for j in range(p["X"].shape[1])}}
    out["doses_branches"] = {b: {str(a): round(D["branches"]["dose"][b][a], 5)
                                 for a in (2017, 2019, 2022, 2025)} for b in BRANCHES_K}
    return out


# --------------------------------------------------------------------------- #
# l'estimation et la traduction
# --------------------------------------------------------------------------- #
def _d434_au_commit() -> None:
    texte = subprocess.run(["git", "show", "HEAD:docs/DECISIONS.md"], cwd=RACINE,
                           capture_output=True, text=True, check=True).stdout
    if "## D-434" not in texte:
        raise SystemExit("D-434 n'est pas au commit courant : rien n'est estimé (CLAUDE.md)")


def estimer_tout(specs: dict) -> dict[str, Any]:
    res: dict[str, Any] = {}
    for nom, (theta, p, poids, n_int) in specs.items():
        interet = _interet(nom, p, n_int)
        r = m.estimer(p["y"], p["X"], p["noms"], p["effets"], p["grappe"], poids=poids,
                      interet=interet, tendance=p["tendance"])
        res[nom] = {"theta": theta, "n": r.n, "grappes": r.grappes, "k_fe": r.k_fe,
                    "poids": poids, "retirees": len(p["retirees"]),
                    "effets": p["effets_noms"], "tendances": p["tendance"] is not None,
                    "coefficients": {p["noms"][j]: r.ligne(p["noms"][j]) for j in interet}}
        print(nom, {n: round(v["coef"], 5) for n, v in res[nom]["coefficients"].items()},
              file=sys.stderr, flush=True)
    return res


def plage_accelerateur(p: Any) -> tuple[float, float, float]:
    """La réponse annuelle de l'investissement, l'année d'un échelon de la valeur ajoutée,
    à θ = 0, ½ et 1 : β₀ R₀(0) + β₁ R₁(0) + R_ec(0) (`reponse_valeur_ajoutee`)."""
    r0, r1, rec = investissement.reponse_valeur_ajoutee(p.rappel_trimestriel,
                                                        p.retard_trimestriel)
    out = []
    for t in (0.0, 0.5, 1.0):
        b0 = float(p.accelerateur_contemporain.a(np.array([t]))[0])
        b1 = float(p.accelerateur_retarde.a(np.array([t]))[0])
        out.append(b0 * r0[0] + b1 * r1[0] + rec[0])
    return (out[0], out[1], out[2])


def traduire(res: dict[str, Any], p: Any) -> dict[str, Any]:
    """Les coefficients principaux sur l'échelle des paramètres et de θ, et le critère du
    but 24 contre la loi de D-424 (`a_priori.lois`)."""
    lois, plages = a_priori.lois(), a_priori.plages()
    e = res["E2"]["coefficients"]["travail"]
    w = res["W1"]["coefficients"]["chomage"]
    c = res["K1"]["coefficients"]["dose"]
    a = res["K2"]["coefficients"]["dva"]
    sorties = {
        thetas.EMPLOI_COUT: ("eta", -e["coef"], e["se"], plages[thetas.EMPLOI_COUT]),
        thetas.SALAIRES_CHOMAGE: ("b", -w["coef"] / SEMI_ELASTICITE_MESANGE,
                                  w["se"] / SEMI_ELASTICITE_MESANGE,
                                  plages[thetas.SALAIRES_CHOMAGE]),
        "investissement_cout_capital": ("epsilon_K", c["coef"], c["se"],
                                        plages["investissement_cout_capital"]),
        "investissement_accelerateur": ("reponse_annee_0", a["coef"], a["se"],
                                        plage_accelerateur(p)),
    }
    out = {}
    for cle, (nom, v, se, plage) in sorties.items():
        loi = lois[cle]
        out[cle] = {nom: v, "se": se, "plage": plage,
                    "loi_d424": {"moyenne": loi.moyenne, "ecart_bas": loi.ecart_bas,
                                 "ecart_haut": loi.ecart_haut},
                    **m.critere_d434(v, se, plage, loi)}
    return out


def main() -> int:
    warnings.simplefilter("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--decrire", action="store_true")
    args = ap.parse_args()
    D = donnees()
    specs = specifications(D)
    if args.decrire:
        print(json.dumps(decrire(D, specs), indent=1, ensure_ascii=False))
        return 0
    _d434_au_commit()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RACINE, capture_output=True,
                            text=True, check=True).stdout.strip()
    res = estimer_tout(specs)
    rapport = {"cas": "microdonnees_d434", "commit": commit, "decision": "D-434",
               "constantes": {"g": D["k"].g, "kappa": D["k"].kappa,
                              "ratio_capital_ccf": D["ratio_capital_ccf"],
                              "taux_usage": D["taux_usage"],
                              "semi_elasticite_mesange": SEMI_ELASTICITE_MESANGE},
               "specifications": res, "theta": traduire(res, D["parametres"]),
               "description": decrire(D, specs)}
    RAPPORT.write_text(json.dumps(rapport, indent=1, ensure_ascii=False, default=float)
                       + "\n", encoding="utf-8")
    print(json.dumps(rapport["theta"], indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
