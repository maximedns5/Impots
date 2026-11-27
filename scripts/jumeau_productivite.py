"""La dimension « productivité » sur les programmes chiffrés (but 29, D-627).

Pour chaque programme (ou texte) dont un rapport d'étude est commité : la trajectoire du
mode structurel (convention « parts_premiere_annee », D-414), θ à ½ au tirage 0, puis
`TIRAGES` tirages de tous les θ que le modèle lit, chacun selon sa loi (`a_priori`,
D-424), de la graine du navigateur (D-459) ; la dimension (`jumeau.impacts.
productivite`) en lit le tirage 0 et la bande de 5 à 95 % des autres. Un programme que
le mode structurel refuse (ses prélèvements agrégés, D-412) est pris comme la trajectoire
de ses mesures ensemble, chacune qui se calcule sur les dix ans ; celles qui ne le font
pas sont nommées. Écrit `reports/jumeau/productivite_programmes.json`.

    PYTHONPATH=src python scripts/jumeau_productivite.py [--tirages 200]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots import site_jumeau
from impots.jumeau import navigateur
from impots.jumeau.impacts import productivite as P
from impots.jumeau.impacts import vers_dict
from impots.jumeau.trajectoire import calculer

ROOT = Path(__file__).resolve().parents[1]
SORTIE = ROOT / "reports" / "jumeau" / "productivite_programmes.json"
FICHES = ROOT / "src" / "impots" / "jumeau" / "transmission"
PROGRAMMES = ("melenchon", "retailleau", "attal", "roussel", "ruffin", "tondelier",
              "kazib", "bouamrane", "lisnard", "philippe", "le_pen")
CONVENTION = "parts_premiere_annee"


def _mesure(s: navigateur.Session, cle: str) -> Any:
    return s.mesure_structurel(cle, "vieillie", CONVENTION)


def _theta(s: navigateur.Session, mesures: list[Any], blocs: Any, tirages: int
           ) -> dict[str, Any]:
    lus = [t["cle"] for t in s.thetas("structurel", mesures, blocs) if t["lu"]]
    if tirages == 0:
        return dict.fromkeys(lus, 0.5)
    rng = np.random.default_rng(navigateur.GRAINE)
    return {c: np.concatenate([[0.5], navigateur._tirer(navigateur.loi_de(c), tirages, rng)])
            for c in lus}


def _trajectoire(s: navigateur.Session, cles: list[str], tirages: int) -> Any:
    mesures = [_mesure(s, c) for c in cles]
    depart, entrees, blocs, boucles = s._modele("structurel", mesures[0], cles[0])
    theta = _theta(s, mesures, blocs, tirages)
    return calculer(depart, entrees=entrees, mesures=mesures, theta=theta, blocs=blocs,
                    boucles=boucles), depart


def _complet(s: navigateur.Session, cles: list[str]) -> bool:
    try:
        traj, _ = _trajectoire(s, cles, 0)
    except ValueError:
        return False
    return len(traj.annees) == len(navigateur.ANNEES)


def composer(s: navigateur.Session, nom: str) -> dict[str, Any]:
    """Les clés de la trajectoire d'un programme : lui-même, ou ses mesures."""
    if nom.startswith("plf"):
        cles = [k for k in s.candidats if k.startswith(nom)]
        bonnes = [k for k in cles if _complet(s, [k])]
        return {"forme": "volets composés", "cles": bonnes,
                "refusees": sorted(set(cles) - set(bonnes))}
    prog = f"pres2027_{nom}_programme"
    if _complet(s, [prog]):
        return {"forme": "programme", "cles": [prog], "refusees": []}
    mesures = [k for k in s.candidats if k.startswith(f"pres2027_{nom}_") and k != prog]
    bonnes = [k for k in mesures if _complet(s, [k])]
    return {"forme": "mesures composées (le programme est refusé en structurel)",
            "cles": bonnes, "refusees": sorted(set(mesures) - set(bonnes))}


def cir_des_fiches(nom: str) -> tuple[dict[int, float], list[str]]:
    """{année : Md€} : la variation de la créance de CIR que les fiches de transmission
    d'un candidat chiffrent (une mesure dont le levier est l'art. 244 quater B du CGI),
    hors de ses mesures chiffrées : l'annonce, de `debut` à `fin`, signe d'une baisse de
    la créance quand la mesure rapporte (recette, économie)."""
    out: dict[int, float] = {}
    lues = []
    for f in sorted((FICHES / nom).glob("*.yaml")) if (FICHES / nom).exists() else ():
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        if "244 quater B" not in str((d.get("levier") or {}).get("texte", "")):
            continue
        m = d["montant"]
        a = m["annonce"]
        signe = -1.0 if a["sens"] in ("recette", "economie_depense") else 1.0
        for annee in range(int(m["debut"]), int(m["fin"]) + 1):
            out[annee] = out.get(annee, 0.0) + signe * float(a["montant_md"])
        lues.append(f"{d['mesure']} : {signe * float(a['montant_md']):+.3f} Md€ par an, "
                    f"{m['debut']}-{m['fin']} ({d['libelle']})")
    return out, lues


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tirages", type=int, default=navigateur.TIRAGES)
    args = ap.parse_args()
    s = navigateur.Session(json.loads(json.dumps(site_jumeau.donnees())))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=ROOT).stdout.strip()
    out: dict[str, Any] = {
        "decision": "D-627", "commit": commit, "mode": "structurel", "vue": "vieillie",
        "convention": CONVENTION, "tirages": args.tirages, "graine": navigateur.GRAINE,
        "theta_tirage_0": 0.5, "programmes": {}}
    for nom in (*PROGRAMMES, "plf2027_art_74"):
        t0 = time.time()
        comp = composer(s, nom)
        if not comp["cles"]:
            out["programmes"][nom] = {**comp, "refus": "aucune trajectoire complète"}
            print(nom, "aucune trajectoire", flush=True)
            continue
        traj, depart = _trajectoire(s, comp["cles"], args.tirages)
        cir, lues = cir_des_fiches(nom)
        dim = P.calculer(traj, None, depart, cir=cir or None)
        out["programmes"][nom] = {**comp, "cir_fiches": lues, "dimension": vers_dict(dim)}
        print(nom, comp["forme"], len(comp["cles"]), f"{time.time() - t0:.0f} s",
              flush=True)
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    print(SORTIE)


if __name__ == "__main__":
    main()
