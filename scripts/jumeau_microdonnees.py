"""Les élasticités du jumeau sur des données fines : les panneaux de D-425, estimés.

    PYTHONPATH=src python scripts/jumeau_microdonnees.py --decrire   # panneaux, doses
    PYTHONPATH=src python scripts/jumeau_microdonnees.py             # les estimations

`--decrire` ne fait aucune régression : il dit les panneaux (tailles, années) et les
doses par secteur, ce que D-425 lit avant tout calcul. Sans option, le script refuse de
tourner si D-425 n'est pas dans `docs/DECISIONS.md` du commit courant, puis écrit
`reports/jumeau/microdonnees.json` : des coefficients, des écarts-types, des tailles,
aucune donnée individuelle.
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

from impots.jumeau import microdonnees as m

RACINE = Path(__file__).resolve().parents[1]
RAPPORT = RACINE / "reports" / "jumeau" / "microdonnees.json"
#: Le taux d'entrée de référence du bloc `naissances` (Da Rin et al. 2011), en %.
E0 = 7.61
#: Les plages des lignes (bas, centre, haut) : `fermetures_marges`, la sensibilité de ε
#: (`naissances.elasticite`, pas une ligne θ), `jumeau_emploi_elasticite_cout`.
PLAGE_BETA = (0.0, 0.03, 0.06)
PLAGE_EPSILON = (0.043, 0.20, 0.356)
PLAGE_ETA = (0.31, 0.44, 0.52)
PLAGE_DELTA = (-1.0, 0.0, 1.0)

ANS_F = [*range(2010, 2020), *range(2022, 2026)]
ANS_C = [*range(2012, 2020), *range(2022, 2026)]
ANS_E = [*range(2003, 2020), *range(2022, 2025)]
PLACEBO = list(range(2003, 2010))
DECALAGE_PLACEBO = 8


def panneau_regional(series: dict, expo: dict, k: m.Constantes, annees: list[int],
                     doses: list[tuple[str, int]], tendances: bool = False
                     ) -> dict[str, Any]:
    """Les lignes (région, secteur, année) : y = log du nombre ; une cellule (région,
    secteur) qui n'a pas un nombre positif chaque année de l'échantillon est retirée
    entière (D-425). `doses` : (nom de la dose, décalage en années)."""
    ys, xs, fe1, fe2, grappe, tend, retirees = [], [], [], [], [], [], []
    for (r, s), v in sorted(series.items()):
        if any(v.get(a, 0.0) <= 0 for a in annees):
            retirees.append(f"{r}-{s}")
            continue
        for a in annees:
            ys.append(np.log(v[a]))
            xs.append([m.doses(expo[s], a + d, k)[nom] for nom, d in doses])
            fe1.append(f"{r}|{s}")
            fe2.append(f"{r}|{a}")
            grappe.append(s)
            tend.append((f"{r}|{s}", a))
    X = np.array(xs)
    noms = [f"{nom}{'' if d == 0 else f'_t{d:+d}'}" for nom, d in doses]
    if tendances:
        # une tendance par cellule, moins celle du premier secteur de chaque région : la
        # somme des tendances d'une région est dans ses effets région×année
        toutes = sorted({c for c, _ in tend})
        premieres = {min(c for c in toutes if c.split("|")[0] == r)
                     for r in {c.split("|")[0] for c in toutes}}
        cellules = [c for c in toutes if c not in premieres]
        T = np.zeros((len(tend), len(cellules)))
        for i, (c, a) in enumerate(tend):
            if c in cellules:
                T[i, cellules.index(c)] = a - annees[0]
        X = np.column_stack([X, T])
        noms += [f"tendance_{c}" for c in cellules]
    return {"y": np.array(ys), "X": X, "noms": noms, "effets": [fe1, fe2],
            "grappe": grappe, "retirees": retirees, "n_doses": len(doses)}


def panneau_emploi(emploi: dict, expo: dict, k: m.Constantes, annees: list[int],
                   doses: list[tuple[str, int]], tendances: bool = False) -> dict[str, Any]:
    ys, xs, fe1, fe2, tend = [], [], [], [], []
    for b, v in sorted(emploi.items()):
        for a in annees:
            if a not in v:
                raise m.MicrodonneesError(f"emploi : {b} {a} absent")
            ys.append(np.log(v[a]))
            xs.append([m.doses(expo[b], a + d, k)[nom] for nom, d in doses])
            fe1.append(b)
            fe2.append(str(a))
            tend.append((b, a))
    X = np.array(xs)
    noms = [f"{nom}{'' if d == 0 else f'_t{d:+d}'}" for nom, d in doses]
    if tendances:
        br = sorted(emploi)
        T = np.zeros((len(tend), len(br)))
        for i, (b, a) in enumerate(tend):
            T[i, br.index(b)] = a - annees[0]
        X = np.column_stack([X, T[:, 1:]])
        noms += [f"tendance_{b}" for b in br[1:]]
    return {"y": np.array(ys), "X": X, "noms": noms, "effets": [fe1, fe2], "grappe": fe1,
            "retirees": [], "n_doses": len(doses)}


def specifications(k: m.Constantes) -> dict[str, tuple[str, dict[str, Any], str]]:
    """Les spécifications de D-425 : nom → (le bloc, le panneau, les poids du bootstrap)."""
    sect = m.expositions()
    br = m.expositions(branches=True)
    dfl = m.defaillances()
    cre = m.creations()
    cre_hae = m.creations(indicateur="TYPE-ENT_HAE", arretee=True)
    emp = m.emploi_branches()
    sans_2023 = [a for a in ANS_C if a != 2023]
    R, E = panneau_regional, panneau_emploi
    return {
        "F1": ("fermetures", R(dfl, sect, k, ANS_F, [("marge", 0)]), "webb"),
        "F1_avance": ("fermetures", R(dfl, sect, k, [a for a in ANS_F if a <= 2023],
                                      [("marge", 0), ("marge", 2)]), "webb"),
        "F1_placebo": ("fermetures", R(dfl, sect, k, PLACEBO,
                                       [("marge", DECALAGE_PLACEBO)]), "webb"),
        "F1_tendances": ("fermetures", R(dfl, sect, k, ANS_F, [("marge", 0)], True), "webb"),
        "F1_2019": ("fermetures", R(dfl, sect, k, list(range(2010, 2020)),
                                    [("marge", 0)]), "webb"),
        "F1_composantes": ("fermetures", R(dfl, sect, k, ANS_F, [("marge_travail", 0),
                                                                ("marge_profit", 0)]),
                           "webb"),
        "C1": ("naissances", R(cre, sect, k, ANS_C, [("taux", 0)]), "webb"),
        "C1_avance": ("naissances", R(cre, sect, k, [a for a in ANS_C if a <= 2023],
                                      [("taux", 0), ("taux", 2)]), "webb"),
        "C1_placebo": ("naissances", R(cre_hae, sect, k, PLACEBO,
                                       [("taux", DECALAGE_PLACEBO)]), "webb"),
        "C1_tendances": ("naissances", R(cre, sect, k, ANS_C, [("taux", 0)], True), "webb"),
        "C1_2019": ("naissances", R(cre, sect, k, list(range(2012, 2020)), [("taux", 0)]),
                    "webb"),
        "C1_sans_2023": ("naissances", R(cre, sect, k, sans_2023, [("taux", 0)]), "webb"),
        "C1_composantes": ("naissances", R(cre, sect, k, ANS_C, [("taux_travail", 0),
                                                                ("taux_profit", 0)]),
                           "webb"),
        "E1": ("emploi", E(emp, br, k, ANS_E, [("travail", 0)]), "rademacher"),
        "E1_avance": ("emploi", E(emp, br, k, [a for a in ANS_E if a <= 2022],
                                  [("travail", 0), ("travail", 2)]), "rademacher"),
        "E1_placebo": ("emploi", E(emp, br, k, PLACEBO, [("travail", DECALAGE_PLACEBO)]),
                       "rademacher"),
        "E1_tendances": ("emploi", E(emp, br, k, ANS_E, [("travail", 0)], True),
                         "rademacher"),
        "E1_2019": ("emploi", E(emp, br, k, list(range(2003, 2020)), [("travail", 0)]),
                    "rademacher"),
    }


def decrire(k: m.Constantes) -> dict[str, Any]:
    sect = m.expositions()
    br = m.expositions(branches=True)
    out: dict[str, Any] = {"g": k.g, "kappa": k.kappa, "smic_net_2024": m.SMIC_NET_2024,
                           "secteurs": {}, "branches": {}}
    for nom, table in (("secteurs", sect), ("branches", br)):
        for u, e in table.items():
            out[nom][u] = {
                "cout_relatif": round(e.cout_relatif, 3),
                "part_sous_2_5_smic": round(e.parts_smic[2.5], 3),
                "fp_sur_va": round(e.total("fp") / e.total("va"), 3),
                "ebe_sur_va": round(e.total("ebe") / e.total("va"), 3),
                **{f"{d}_{a}": round(m.doses(e, a, k)[d], 4)
                   for d in ("travail", "marge", "taux") for a in (2013, 2016, 2019, 2022,
                                                                   2024)}}
    tailles = {}
    for nom, (bloc, p, _) in specifications(k).items():
        tailles[nom] = {"bloc": bloc, "n": len(p["y"]), "grappes": len(set(p["grappe"])),
                        "retirees": p["retirees"]}
    out["panneaux"] = tailles
    return out


def _d425_au_commit() -> None:
    texte = subprocess.run(["git", "show", "HEAD:docs/DECISIONS.md"], cwd=RACINE,
                           capture_output=True, text=True, check=True).stdout
    if "## D-425" not in texte:
        raise SystemExit("D-425 n'est pas au commit courant : rien n'est estimé (CLAUDE.md)")


def estimer_tout(k: m.Constantes) -> dict[str, Any]:
    resultats: dict[str, Any] = {}
    for nom, (bloc, p, poids) in specifications(k).items():
        interet = list(range(p["n_doses"]))
        r = m.estimer(p["y"], p["X"], p["noms"], p["effets"], p["grappe"], poids=poids,
                      interet=interet)
        resultats[nom] = {"bloc": bloc, "n": r.n, "grappes": r.grappes, "k_fe": r.k_fe,
                          "poids": poids, "retirees": p["retirees"],
                          "coefficients": {p["noms"][j]: r.ligne(p["noms"][j])
                                           for j in interet}}
        print(nom, {n: round(v["coef"], 5) for n, v in
                    resultats[nom]["coefficients"].items()}, file=sys.stderr)
    return resultats


def traduire(res: dict[str, Any]) -> dict[str, Any]:
    """Les coefficients principaux sur l'échelle des paramètres du jumeau et de θ."""
    f = res["F1"]["coefficients"]["marge"]
    c = res["C1"]["coefficients"]["taux"]
    e = res["E1"]["coefficients"]["travail"]
    beta, se_beta = f["coef"], f["se"]
    eps, se_eps = -E0 * c["coef"], E0 * c["se"]
    eta, se_eta = -e["coef"], e["se"]
    return {
        "fermetures_marges": {"beta": beta, "se": se_beta,
                              **m.vers_theta(beta, se_beta, *PLAGE_BETA),
                              "plage": PLAGE_BETA},
        "naissances_elasticite": {"epsilon": eps, "se": se_eps,
                                  **m.vers_theta(eps, se_eps, *PLAGE_EPSILON),
                                  "plage": PLAGE_EPSILON,
                                  "note": "pas une ligne θ : la plage de sensibilité"},
        "jumeau_emploi_elasticite_cout": {"eta": eta, "se": se_eta,
                                          **m.vers_theta(eta, se_eta, *PLAGE_ETA),
                                          "plage": PLAGE_ETA},
    }


def taux_entree() -> dict[str, Any]:
    """La lecture de niveau de δ (D-425) : les créations de sociétés de France entière
    sur le nombre d'entreprises à l'IS de la DGFiP (2024, et 2023 par sa variation)."""
    from impots.dette import comptes

    texte = m._texte(m.BDM_CREATIONS)
    fe = [obs for a, obs in m.series_bdm(texte) if a.get("REF_AREA") == "FE"
          and a.get("ACTIVITE_CREAT_ENT") == "ENS" and a.get("INDICATEUR") == "TYPE-ENT_PM"]
    if len(fe) != 1:
        raise m.MicrodonneesError(f"{len(fe)} séries de sociétés pour la France entière")
    annees = m.annuel(fe[0])
    rows = comptes._rows(m.DGFIP_IS, "Tableau 2")
    stock = next(float(r[6]) for r in rows if r[1] and str(r[1]).startswith("Nombre"))
    var = next(float(r[6]) for r in rows if r[1] and str(r[1]).startswith("Variation du n"))
    stocks = {2024: stock, 2023: stock / (1 + var / 100)}
    taux = {a: 100 * annees[a] / s for a, s in stocks.items()}
    return {"creations_societes": {a: annees[a] for a in stocks}, "stock_is": stocks,
            "taux_entree": taux, "delta": {a: t - E0 for a, t in taux.items()},
            "plage": PLAGE_DELTA}


def main() -> int:
    warnings.simplefilter("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--decrire", action="store_true")
    args = ap.parse_args()
    k = m.constantes()
    if args.decrire:
        print(json.dumps(decrire(k), indent=1, ensure_ascii=False))
        return 0
    _d425_au_commit()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=RACINE, capture_output=True,
                            text=True, check=True).stdout.strip()
    res = estimer_tout(k)
    rapport = {"cas": "microdonnees_d425", "commit": commit, "decision": "D-425",
               "constantes": {"g": k.g, "kappa": k.kappa, "e0": E0},
               "specifications": res, "theta": traduire(res), "delta": taux_entree(),
               "description": decrire(k)}
    RAPPORT.write_text(json.dumps(rapport, indent=1, ensure_ascii=False, default=float)
                       + "\n", encoding="utf-8")
    print(json.dumps(rapport["theta"], indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
