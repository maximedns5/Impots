"""Le CICE de D-535 et D-536 dans le jumeau, à chaque réglage de la boucle prix (but 28,
volet `interaction`, D-540 et suivantes) : un contrôle de non-régression, le juge étant
déjà lu. Les entrées de la passe (`cice_passe.json`) sont gardées ; aucune passe
OpenFisca. Le juge et la tolérance sont ceux de D-535.

    JUGES28_SORTIE=<dossier des entrées> PYTHONPATH=src python \\
        scripts/interaction_cice_b28.py <sortie.json>
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("juges_passe_b28", ICI / "juges_passe_b28.py")
jp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jp)

REGLAGES = ("mesange", "harasztosi_lindner", "diagnostic_juge")


def main(dest: str) -> None:
    from impots.jumeau.apprentissage import Fenetre
    from impots.jumeau.blocs import commerce

    m, info = jp.mesure_cice()
    f = Fenetre(2012, 2017, tuple(jp.TAUX_CICE))
    base = jp._thetas()
    out = {"commit": jp.commit(), "entree": info, "juge": jp.JUGE_CICE, "reglages": {}}
    for nom in REGLAGES:
        with commerce.prix(nom):
            e = jp._effet(f, m, base)
        es = e["emploi_salarie"]
        moyenne = sum(es[1:4]) / 3.0
        out["reglages"][nom] = {
            "effet": e,
            "emploi_2016": es[3], "moyenne_2014_2016": moyenne,
            "rapport_au_juge": moyenne / jp.JUGE_CICE["central_milliers"],
            "dans_la_tolerance": 0.5 <= moyenne / jp.JUGE_CICE["central_milliers"] <= 2.0}
        with commerce.prix(nom):
            out["reglages"][nom]["phi"] = commerce.part_prix()
        print(nom, round(es[3], 1), round(moyenne, 1), flush=True)
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    Path(dest).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1])
