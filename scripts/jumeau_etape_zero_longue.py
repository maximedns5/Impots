"""L'étape zéro de l'histoire longue (D-446) : l'identifiabilité des θ, sans erreur.

    PYTHONPATH=src python scripts/jumeau_etape_zero_longue.py [--sortie ...]

À lancer sur un commit poussé qui porte D-446 et la base des mesures d'avant 2010 ; le
rapport porte son commit et refuse un arbre modifié. Ce qui tourne, comme D-446 § 4 le
préenregistre (et comme D-428 et D-433, dont le code restait hors du dépôt) :

* deux schémas : celui de D-417 (2011 à 2017), avec ses exogènes, le point de
  comparaison ; et `rejeu_histoire.SCHEMA_LONG` (1997 à 2007 et 2011 à 2017), avec les
  siens (la tendance sur ses 18 années notées) ;
* la jacobienne des sorties notées du jumeau (pas des erreurs : aucune valeur publiée de
  cible n'est lue) en θ, divisée par les tolérances de D-417, sur les fenêtres de
  l'estimation ; les créations seulement depuis 2011 (`CREATIONS_DEPUIS`) ;
* huit θ, les sept de `ESTIMES` et ε (`elasticite_creations`), perturbés de 0,001 sur
  l'axe des tirages, les autres θ du registre à ½ ; quatre points : ½ vers le haut et
  vers le bas, le mode de chaque loi de r4 (`a_priori.lois`) ramené dans [0 ; 1] vers le
  haut et vers le bas ;
* l'information diag (JᵀJ), l'écart-type approché √diag (JᵀJ + P)⁻¹ ; à ½, P = 4 I et le
  critère de D-421 (écart-type sous 0,25) ; au mode, P = diag (1 / s²), s l'écart de la loi du côté
  de la perturbation, et le critère du but (écart-type sous s / 2), celui qui décide.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from impots.jumeau import a_priori, thetas, votees
from impots.jumeau import apprentissage as app
from impots.jumeau import rejeu_histoire as rh
from impots.jumeau.blocs.entreprises import population_depuis
from impots.jumeau.cellules import Cellules

RACINE = Path(__file__).resolve().parents[1]
THETAS = (*rh.ESTIMES, "elasticite_creations")
PAS = 0.001
SEUIL_D421 = 0.25


def _commit() -> str:
    sale = subprocess.run(["git", "status", "--porcelain", "--", "src", "scripts"],
                          capture_output=True, text=True, cwd=RACINE, check=True).stdout
    if sale.strip():
        raise SystemExit(f"arbre modifié, le rapport n'aurait pas de commit :\n{sale}")
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                          cwd=RACINE, check=True).stdout.strip()


def sorties(schema: app.Schema, simuler: app.Simulateur, cibles: tuple[app.Cible, ...],
            theta: dict) -> tuple[np.ndarray, list[str]]:
    """Les sorties notées du jumeau sur l'estimation, divisées par les tolérances :
    (tirages, sorties), et le nom de chaque sortie (fenêtre, cible, année)."""
    colonnes, noms = [], []
    for f in schema.fenetres("estimation"):
        trajectoire = simuler(f, theta)
        if tuple(trajectoire.annees) != f.annees:
            raise app.ApprentissageError(f"le simulateur rend {trajectoire.annees}")
        variante = dict(zip(trajectoire.annees, trajectoire.variante, strict=True))
        reference = dict(zip(trajectoire.annees, trajectoire.reference, strict=True))
        repli = app._Repli(rh.etat_publie(f.depart), reference[f.annees[0]])
        for c in cibles:
            for a in f.notees:
                if c.nom == "creations" and a < rh.CREATIONS_DEPUIS:
                    continue
                avant = variante.get(a - 1, repli)
                valeur = np.asarray(c.jumeau(variante[a], avant), dtype=float) + c.ajout
                colonnes.append(valeur.reshape(-1) / c.tolerance)
                noms.append(f"{f.depart}-{f.fin}|{c.nom}|{a}")
    return np.column_stack(np.broadcast_arrays(*colonnes)), noms


def jacobienne(schema: app.Schema, simuler: app.Simulateur, cibles: tuple[app.Cible, ...],
               x: np.ndarray, pas: float) -> tuple[np.ndarray, list[str]]:
    """J (sorties × θ) par différences finies, les huit θ perturbés sur l'axe des tirages
    (le premier tirage au point, les suivants chacun un θ décalé de `pas`)."""
    points = np.vstack([x, x + pas * np.eye(len(x))])
    theta: dict = {k: 0.5 for k in thetas.REGISTRE}
    for i, k in enumerate(THETAS):
        theta[k] = points[:, i]
    s, noms = sorties(schema, simuler, cibles, theta)
    return ((s[1:] - s[0]) / pas).T, noms


def lire_point(j: np.ndarray, p: np.ndarray, noms: list[str]) -> dict:
    jtj = j.T @ j
    sigma = np.sqrt(np.diag(np.linalg.inv(jtj + np.diag(p))))
    fenetres = sorted({n.split("|")[0] for n in noms})
    par_fenetre = {f: dict(zip(THETAS, map(float, np.sum(
        j[[i for i, n in enumerate(noms) if n.startswith(f + "|")]] ** 2, axis=0)),
        strict=True)) for f in fenetres}
    return {"information": dict(zip(THETAS, map(float, np.diag(jtj)), strict=True)),
            "ecart_type": dict(zip(THETAS, map(float, sigma), strict=True)),
            "information_par_fenetre": par_fenetre, "sorties": len(noms)}


def etape_zero(schema: app.Schema, nom: str, base: tuple, cellules: Cellules,
               population: object, lois: dict) -> dict:
    exogenes = rh.exogenes_publies(schema)
    simuler = rh.simulateur(population=population, cellules=cellules, exogenes=exogenes,
                            observateur=rh.etat_publie, votees=base)
    cibles = rh.cibles(100.0 * exogenes.croissance_emploi)
    mode = np.array([min(1.0, max(0.0, lois[k].moyenne)) for k in THETAS])
    demi = np.full(len(THETAS), 0.5)
    out: dict = {"schema": nom, "exogenes": {
        "croissance_tendance": exogenes.croissance_tendance,
        "croissance_emploi": exogenes.croissance_emploi,
        "croissance_demande_mondiale": exogenes.croissance_demande_mondiale},
        "points": {}}
    for point, x, pas in (("demi_haut", demi, PAS), ("demi_bas", demi, -PAS),
                          ("mode_haut", mode, PAS), ("mode_bas", mode, -PAS)):
        j, noms = jacobienne(schema, simuler, cibles, x, pas)
        if point.startswith("demi"):
            s = np.full(len(THETAS), 0.5)
        else:
            s = np.array([lois[k].ecart_haut if pas > 0 else lois[k].ecart_bas
                          for k in THETAS])
        lu = lire_point(j, 1.0 / s ** 2, noms)
        lu["x"] = dict(zip(THETAS, map(float, x), strict=True))
        lu["s"] = dict(zip(THETAS, map(float, s), strict=True))
        lu["requis"] = {k: 3.0 / v ** 2 for k, v in lu["s"].items()}
        seuil = {k: (SEUIL_D421 if point.startswith("demi") else v / 2.0)
                 for k, v in lu["s"].items()}
        lu["seuil"] = seuil
        lu["identifie"] = {k: lu["ecart_type"][k] < seuil[k] for k in THETAS}
        out["points"][point] = lu
    pts = out["points"]
    out["identifies_but"] = [k for k in THETAS if pts["mode_haut"]["identifie"][k]
                             or pts["mode_bas"]["identifie"][k]]
    out["identifies_d421"] = [k for k in THETAS if pts["demi_haut"]["identifie"][k]
                              or pts["demi_bas"]["identifie"][k]]
    out["rapport_au_requis"] = {k: max(pts[p]["information"][k] / pts[p]["requis"][k]
                                       for p in ("mode_haut", "mode_bas")) for k in THETAS}
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sortie", type=Path,
                        default=RACINE / "reports" / "jumeau" / "etape_zero_longue.json")
    args = parser.parse_args()
    commit = _commit()
    base, cellules, population = votees.mesures(), Cellules.lire(), population_depuis()
    lois = a_priori.lois()
    schemas = {"d417": etape_zero(rh.SCHEMA, "D-417, 2011 à 2017", base, cellules,
                                  population, lois),
               "longue": etape_zero(rh.SCHEMA_LONG, "D-446, 1997 à 2007 et 2011 à 2017",
                                    base, cellules, population, lois)}
    court, long_ = schemas["d417"]["points"], schemas["longue"]["points"]
    rapport = {"decision": "D-446", "commit": commit, "thetas": list(THETAS), "pas": PAS,
               "schemas": schemas,
               "multiplicateur": {p: {k: (long_[p]["information"][k]
                                          / court[p]["information"][k]
                                          if court[p]["information"][k] else None)
                                      for k in THETAS} for p in court},
               "atteint": bool(schemas["longue"]["identifies_but"])}
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(json.dumps(rapport, indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(args.sortie)


if __name__ == "__main__":
    main()
