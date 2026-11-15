"""Les rapports d'études réécrits à l'élasticité déclarée du canal des créations (D-427).

    PYTHONPATH=src python scripts/recaler_creations.py --controle   # rien n'est écrit
    PYTHONPATH=src python scripts/recaler_creations.py              # les rapports réécrits

Sans passe : chaque rapport qui lit le canal est refait depuis ses propres champs
(`predictif.recalcul`), à l'ε de `predictif/parameters/creations_entreprises.yaml`. Le
contrôle refait chaque rapport à l'ε qu'il porte et le compare au fichier commité : à
l'octet près, sauf les champs de `recalcul.AU_PRES`, à `TOLERANCE_AU_PRES` près. Un
rapport dont les prélèvements sur les entreprises et le capital sont nuls ne lit pas ε :
seuls ses paramètres changent. Un rapport déjà à l'ε déclaré n'est pas touché.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from impots.predictif import creations, recalcul

RACINE = Path(__file__).resolve().parents[1]
ETUDES = RACINE / "reports" / "etudes"
DECISION = "D-427"


def rapports() -> list[Path]:
    """Les rapports d'études qui portent le canal des créations."""
    out = []
    for chemin in sorted(ETUDES.glob("**/predictif_*.json")):
        d = json.loads(chemin.read_text(encoding="utf-8"))
        if isinstance(d, dict) and (d.get("rejeu") or {}).get("creations"):
            out.append(chemin)
    return out


def controle(chemin: Path) -> list[str]:
    """Ce que le rapport, refait à son ε, ne redonne pas : vide quand il tient."""
    return [f"{chemin.relative_to(RACINE)} {faute}"
            for faute in recalcul.controle(chemin.read_text(encoding="utf-8"))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--controle", action="store_true")
    args = ap.parse_args()
    cible = vars(creations.charger().elasticite)
    fautes = [f for c in rapports() for f in controle(c)]
    if fautes:
        print("\n".join(fautes[:20]), file=sys.stderr)
        print(f"contrôle refusé : {len(fautes)} écarts", file=sys.stderr)
        return 1
    print(f"contrôle : {len(rapports())} rapports refaits à leur ε")
    if args.controle:
        return 0
    for chemin in rapports():
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        porte = payload["rejeu"]["creations"]["parametres"]["elasticite"]
        if porte == cible:
            continue
        refait = recalcul.recalculer(payload, cible, decision=DECISION,
                                     date=date.today().isoformat())
        chemin.write_text(recalcul.ecrire(refait), encoding="utf-8")
        print(f"  -> {chemin.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
