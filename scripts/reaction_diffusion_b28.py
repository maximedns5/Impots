"""Le Smic de Mélenchon dans le jumeau, selon la diffusion (but 28, volet `reaction`, D-534).

La mesure de D-508 et D-509 (le Smic à 1 700 € net, portée aux nombres de la passe
complète de D-521, convention « premiere_annee_d521 », `mesure_melenchon_b27`), en
structurel, vue figée et vieillie, θ de financement à ½ : l'emploi, le solde et la dette
de 2035 à θ de diffusion 0, ¼, ½, ¾ et 1, avec les paramètres du bloc `travail` du
commit. Aucune passe : le jumeau seul, en secondes.

    PYTHONPATH=src python scripts/reaction_diffusion_b28.py <sortie.json>
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("mesure_melenchon_b27",
                                               ICI / "mesure_melenchon_b27.py")
mm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mm)

CLE = "pres2027_melenchon_smic_1700_net"
THETAS = (0.0, 0.25, 0.5, 0.75, 1.0)


def mesurer() -> dict:
    from impots.jumeau import papillon as pa
    from impots.jumeau.blocs import travail

    S = mm.session()
    k = mm.redimensionner(S, CLE, mm.lire("complet_propres_smic"))
    p = travail.charger()
    out = {"convention": mm.CONVENTION_D521, "rapports": k,
           "diffusion_bas": p.diffusion.get("bas", [0.0] * 5).tolist()
           if hasattr(p.diffusion.get("bas"), "tolist") else [0.0] * 5}
    for vue in ("figee", "vieillie"):
        m = S.mesure_structurel(CLE, vue, "parts_premiere_annee")
        out[vue] = {}
        for t in THETAS:
            tr, _ = pa.trajectoire(S, [m], cle=CLE,
                                   theta={**mm.FIN, "travail_smic_diffusion": t})
            out[vue][str(t)] = mm.court_(pa.ecarts(tr))
    return out


if __name__ == "__main__":
    res = mesurer()
    texte = json.dumps(res, ensure_ascii=False, indent=1) + "\n"
    Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[1]).write_text(texte, encoding="utf-8")
    print(texte)
