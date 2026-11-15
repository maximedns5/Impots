"""But 23 (D-412) — une trajectoire du jumeau est la même au bit d'un processus à l'autre.

La fermeture des comptes sommait les contributions de B9 et de la dette dans l'ordre d'un
ensemble Python, qui change avec `PYTHONHASHSEED` : le dernier bit de B9, de la dette et
du ratio changeait d'un processus à l'autre (D-411). Elle somme désormais dans l'ordre
trié des clés. Le test fait tourner le modèle structurel complet (les données
synthétiques de `test_jumeau_structurel.py`, quatre mesures, θ½) dans trois
sous-processus de graines différentes, et compare chaque champ de chaque état, et la
décomposition de Δb, au bit. Sur l'ancien code, les trois empreintes différaient.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]

PROGRAMME = """
import hashlib, sys
sys.path.insert(0, "tests")
from test_jumeau_structurel import ANNEES, _calcul, _theta
t = _calcul(_theta(0.5))
morceaux = []
for etat in (*t.reference, *t.variante):
    for nom in sorted(etat.champs()):
        morceaux.append(nom + ":" + ",".join(float(v).hex() for v in etat[nom]))
for cle, v in sorted(t.decomposition(ANNEES[-1]).items()):
    morceaux.append(str(cle) + ":" + ",".join(float(x).hex() for x in v))
print(hashlib.sha256("|".join(morceaux).encode()).hexdigest(), len(morceaux))
"""


def _empreinte(graine: str) -> str:
    env = {**os.environ, "PYTHONHASHSEED": graine,
           "PYTHONPATH": os.pathsep.join([str(RACINE / "src"),
                                          os.environ.get("PYTHONPATH", "")])}
    sortie = subprocess.run([sys.executable, "-c", PROGRAMME], cwd=RACINE, env=env,
                            capture_output=True, text=True, timeout=300, check=True)
    return sortie.stdout.strip()


def test_la_trajectoire_ne_depend_pas_de_la_graine_des_ensembles() -> None:
    empreintes = {g: _empreinte(g) for g in ("0", "1", "2")}
    assert len(set(empreintes.values())) == 1, empreintes
    assert int(empreintes["0"].split()[1]) > 1000
