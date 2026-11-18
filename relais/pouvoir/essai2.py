import json
import sys

import numpy as np

from impots import site_jumeau
from impots.jumeau import navigateur
from impots.jumeau.impacts import entente, pouvoir

s = navigateur.Session(json.loads(json.dumps(site_jumeau.donnees())))
tir = int(sys.argv[1]) if len(sys.argv) > 1 else 0
GR = ["D1", "D2", "D5", "D9", "D10"]


def montrer(d):
    for i in d.indicateurs:
        b = None if i.bas is None else (np.round(i.bas[[0, -1]], 2), np.round(i.haut[[0, -1]], 2))
        print(" ", i.cle, i.unite, np.round(i.valeurs, 2), b)
        if i.par_groupe:
            for g, v in i.par_groupe.items():
                if g in GR or not g.startswith("D"):
                    print("     ", g, np.round(v[[0, -1]], 2))


for cle in sys.argv[2:]:
    if cle == "melenchon":
        c = "pres2027_melenchon_programme"
        ch = pouvoir.chocs_du_rapport(s.candidats[c]["premiere_annee"])
        print("melenchon chocs", {a: np.round(v, 2) for a, v in ch.items()},
              sum(list(ch.values())[0]))
        rv = pouvoir.revenus_statiques(ch, s.cellules)
        d = pouvoir.pouvoir_achat(None, None, None, s.cellules, revenus=rv, annee_euros=2024)
        e = entente.entente(None, None, None, s.cellules, revenus=rv)
    else:
        choix = {"mode": "structurel", "vue": "figee", "candidat": cle,
                 "convention": "parts_premiere_annee"}
        out = s.calculer({**choix, "theta": {}})
        th = {t["cle"]: 0.5 for t in out["thetas"]}
        traj, dep, refus = pouvoir.trajectoire_tiree(s, {**choix, "theta": th}, tirages=tir)
        d = pouvoir.pouvoir_achat(traj, None, dep, s.cellules)
        e = entente.entente(traj, None, dep, s.cellules)
    print("=====", cle)
    montrer(d)
    print("  bornes", {k: {c_: round(v[0]) for c_, v in d_.items()}
                       for k, d_ in d.notes["types_bornes_repartition"].items()})
    print("  entente", e.notes["distribution"][:40], e.notes["reference"])
    montrer(e)
