"""Pour vous sur trois programmes et trois cas types (but 29, volet `cas`, D-633).

Comme le moral (D-597) et la santé (D-622) : le mode structurel du jumeau, vue vieillie,
convention « parts_premiere_annee », θ ½ pour chaque θ lu, tirage 0 ; un programme que le
structurel refuse comme un tout, par ses mesures seules (D-502), son statique étant alors
celui du programme entier (`cle_statique`). La dimension « pour vous » pour les cas types
de `CAS`, écrite dans `reports/jumeau/pour_vous_programmes.json` (des cas types). Le jumeau
tourne en secondes ; le tableau d'OpenFisca est celui que `impots.cas_types` a commité.

    PYTHONPATH=src python scripts/jumeau_pour_vous.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SORTIE = ROOT / "reports" / "jumeau" / "pour_vous_programmes.json"
PROGRAMMES = ("melenchon", "retailleau", "attal")
CAS = {
    "seul-0-smic-locataire-30_49": "seul, au Smic, locataire, 30-49 ans",
    "couple-2-median-proprietaire-30_49": "couple, deux enfants, deux salaires médians, "
                                          "propriétaire, 30-49 ans",
    "couple-0-retraite-proprietaire-62_plus": "couple de retraités, propriétaire",
    "seul-0-median-locataire-50_61": "seul, salaire médian, locataire, 50-61 ans (l'âge "
                                     "de départ)",
}


def main() -> int:
    from impots import site_jumeau
    from impots.jumeau.impacts import pour_vous
    from impots.jumeau.navigateur import Session
    from jumeau_sante import trajectoire

    session = Session(site_jumeau.donnees())
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=ROOT).stdout.strip()
    out = {"commit": commit, "decision": "D-633", "mode": "structurel", "vue": "vieillie",
           "theta": "½ pour chaque θ lu", "tableau": pour_vous.charger()["commit"],
           "cas": CAS, "programmes": {}}
    for slug in PROGRAMMES:
        traj, convention = trajectoire(session, slug)
        cle = f"pres2027_{slug}_programme"
        d = pour_vous.pour_vous(traj.variante, traj.reference, None, session.cellules,
                                mesures=list(traj.mesures), programme=slug,
                                cle_statique=cle)
        n = d.notes
        out["programmes"][slug] = {
            "convention": convention, "annees": list(d.annees),
            "economie": n["economie"], "cas": {k: n["cas"][k] for k in CAS}}
        for k in CAS:
            x = n["cas"][k]
            print(f"{slug:11s} {k:40s} statique {x['statique'][-1]:7.0f} réel 2035 "
                  f"{x['reel'][-1]:7.0f} ({100 * x['reel'][-1] / x['rd']:+.2f} %) risque {x['risque'][-1]:+.2f}"
                  f" sat {x['sat'][-1]:+.3f} ev {x['ev'][-1]:+.2f} mois")
    SORTIE.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"-> {SORTIE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
