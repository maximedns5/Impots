"""Le contrôle des programmes composés de leurs mesures (but 29, volet `refuses`, D-656).

Pour Mélenchon et Tondelier, que le jumeau complet refuse comme un tout : la composition
de la page (D-655 : ses mesures chiffrées et leur interaction, structurel, figée, parts
de la première année, θ à ½) contre le chemin des études (le programme, réduit, vieillie,
θ à ½), sur ce que les deux partagent. Les lignes, leur tolérance et leur pronostic sont
ceux de D-656, écrits avant le premier calcul :

* C1 : Σ coûts des mesures et de l'interaction − coût du programme, chaque année, figée et
  vieillie ; 1e-6 Md€ ;
* C2 : le coût statique de 2026, composition (figée) / programme (vieillie) ; 2 % ;
* C3 : la part statique de ΔB9 2026 (le bloc `mesures`) ; 5 % ;
* C4 : ΔB9 2026 entier ; 10 %.

Les écarts relatifs se prennent sur le chemin des études. Le jumeau seul, aucune passe.
Écrit `reports/jumeau/programmes_composes.json`.

    PYTHONPATH=src python scripts/jumeau_programmes_composes.py
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from impots import site_jumeau
from impots.jumeau import navigateur, papillon

ROOT = Path(__file__).resolve().parents[1]
SORTIE = ROOT / "reports" / "jumeau" / "programmes_composes.json"
PROGRAMMES = ("melenchon", "tondelier")
CONVENTION = "parts_premiere_annee"
#: D-656, écrites avant le premier calcul ; jamais changées après.
TOLERANCES = {"C1": 1e-6, "C2": 0.02, "C3": 0.05, "C4": 0.10}
PREMIERE = navigateur.ANNEES[0]


def _trajectoire(s: navigateur.Session, choix: dict[str, Any]) -> Any:
    ctx = s._contexte({**choix, "theta": {}})
    theta = {t["cle"]: 0.5 for t in ctx["registre"] if t["lu"]}
    traj, refus = s._derouler(ctx, theta)
    if traj is None or refus:
        raise SystemExit(f"{choix} : {refus}")
    return traj


def _b9(traj: Any, k: int = 0) -> tuple[float, float]:
    """ΔB9 de l'année k, et la part du bloc `mesures` (Md€)."""
    statique = sum(x for (bloc, _), x in papillon.par_bloc(traj, "b9", k).items()
                   if bloc == "mesures")
    return float(traj.difference("b9")[k, 0]), float(statique)


def _ligne(nom: str, compose: float, etudes: float) -> dict[str, Any]:
    ecart = (compose - etudes) / abs(etudes) if etudes else float("nan")
    return {"composition": compose, "etudes": etudes, "ecart_relatif": ecart,
            "tolerance": TOLERANCES[nom], "tenu": abs(ecart) <= TOLERANCES[nom]}


def controler(s: navigateur.Session, slug: str) -> dict[str, Any]:
    cle = f"pres2027_{slug}_programme"
    out: dict[str, Any] = {}
    # C1 : la composition porte le coût du programme, chaque année.
    pire = 0.0
    for vue in ("figee", "vieillie"):
        mesures, _ = s.programme_compose(cle, vue, CONVENTION)
        p = s.mesure(cle, vue, CONVENTION)
        for a in p.annees:
            pire = max(pire, abs(sum(m.couts.get(a, 0.0) for m in mesures) - p.couts[a]))
    out["C1"] = {"pire_ecart_md": pire, "tolerance": TOLERANCES["C1"],
                 "tenu": pire <= TOLERANCES["C1"]}
    # C2 : le coût statique de la première année, d'un chemin à l'autre.
    mesures, info = s.programme_compose(cle, "figee", CONVENTION)
    compose = sum(m.couts.get(PREMIERE, 0.0) for m in mesures)
    etudes = s.mesure(cle, "vieillie").couts[PREMIERE]
    out["C2"] = _ligne("C2", compose, etudes)
    # C3, C4 : la première année du solde.
    reglage = s.reglage_impacts({"candidat": cle})
    if not reglage.get("mesures_seules"):
        raise SystemExit(f"{cle} : la page ne le compose pas ({reglage.get('pourquoi_mode')})")
    reglage.pop("pourquoi_mode", None)
    t_comp = _trajectoire(s, reglage)
    t_etud = _trajectoire(s, {"candidat": cle, "mode": "reduit", "vue": "vieillie"})
    (b_c, st_c), (b_e, st_e) = _b9(t_comp), _b9(t_etud)
    out["C3"] = _ligne("C3", st_c, st_e)
    out["C4"] = _ligne("C4", b_c, b_e)
    out["dynamique_2026"] = {"composition": b_c - st_c, "etudes": b_e - st_e}
    out["interaction"] = info["interaction"]
    out["mesures"] = [m["identifiant"] for m in info["mesures"]]
    return out


def main() -> None:
    s = navigateur.Session(json.loads(json.dumps(site_jumeau.donnees())))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=ROOT).stdout.strip()
    out = {"decision": "D-656", "commit": commit, "tolerances": TOLERANCES,
           "composition": {"mode": "structurel", "vue": "figee", "convention": CONVENTION},
           "etudes": {"mode": "reduit", "vue": "vieillie"}, "theta": 0.5,
           "programmes": {slug: controler(s, slug) for slug in PROGRAMMES}}
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for slug, r in out["programmes"].items():
        for c in ("C1", "C2", "C3", "C4"):
            print(slug, c, {k: (round(v, 4) if isinstance(v, float) else v)
                            for k, v in r[c].items()})
    print(SORTIE)


if __name__ == "__main__":
    main()
