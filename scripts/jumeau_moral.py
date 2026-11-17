"""Le moral des gens sur trois programmes (but 29, volet `bienetre`, D-597).

Le mode structurel du jumeau, vue vieillie, convention « parts_premiere_annee », θ ½ pour
chaque θ lu ; Mélenchon, que le structurel refuse comme un tout, par ses mesures seules et
leur interaction (`papillon.mesures_seules`, D-502). La dimension « moral » au tirage 0,
écrite dans `reports/jumeau/moral_programmes.json` (des agrégats, aucune donnée
individuelle). Le jumeau tourne en secondes : pas de passe sur la population.

    PYTHONPATH=src python scripts/jumeau_moral.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SORTIE = ROOT / "reports" / "jumeau" / "moral_programmes.json"
PROGRAMMES = ("melenchon", "retailleau", "attal")


def trajectoire(session, slug: str):
    from impots.jumeau import papillon
    from impots.jumeau.navigateur import ANNEES

    cle = f"pres2027_{slug}_programme"
    vue, conv = "vieillie", "parts_premiere_annee"
    n, refus = session.structurel(cle, vue, conv)
    if n == len(ANNEES):
        mesures = [session.mesure_structurel(cle, vue, conv)]
        convention = "programme"
    else:
        mesures = papillon.mesures_seules(session, slug, vue, conv)
        convention = f"mesures_seules (D-502) ; le programme refusé : {refus}"
    traj, _ = papillon.trajectoire(session, mesures, cle=cle)
    return traj, convention


def main() -> int:
    from impots import site_jumeau
    from impots.jumeau.impacts import vers_dict
    from impots.jumeau.impacts.moral import dimension
    from impots.jumeau.navigateur import Session

    session = Session(site_jumeau.donnees())
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=ROOT).stdout.strip()
    out = {"commit": commit, "decision": "D-597", "mode": "structurel", "vue": "vieillie",
           "theta": "½ pour chaque θ lu", "programmes": {}}
    for slug in PROGRAMMES:
        traj, convention = trajectoire(session, slug)
        d = dimension(traj, None, None, session.cellules)
        out["programmes"][slug] = {"convention": convention, **vers_dict(d)}
        w = d.indicateurs[0]
        print(f"{slug:12s} {convention[:40]:40s} WELLBY 2035 {w.valeurs[-1]:9.1f} k "
              f"[{w.bas[-1]:.1f} ; {w.haut[-1]:.1f}]")
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"-> {SORTIE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
