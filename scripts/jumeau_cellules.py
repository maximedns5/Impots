#!/usr/bin/env python
"""But 23, lot 4 — construire les cellules de ménages du jumeau, une fois (D-409).

Une passe OpenFisca de référence au droit de 2024 sur un sous-échantillon PPS de la
population (jamais toute la population), avec les imputations des niches, du capital, des
indemnités journalières et de la consommation ; puis `jumeau.cellules.construire`, les
recoupements, et le fichier hors git avec son manifeste. Se lance détaché :

    setsid nohup env PYTHONPATH=src .venv/bin/python scripts/jumeau_cellules.py \
        --menages 20000 > /tmp/cellules.log 2>&1 &
"""

from __future__ import annotations

import argparse
import datetime as dt
import gc
import hashlib
import json
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import polars as pl  # noqa: E402

from impots.jumeau import cellules as cel  # noqa: E402
from impots.population.runner import SAMPLE_SEED, run, subsample  # noqa: E402

POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"


def _memoire_go() -> float:
    """Le pic de mémoire résidente du processus, en Go (ru_maxrss est en kio)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 ** 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--menages", type=int, default=20_000)
    parser.add_argument("--sortie", type=Path, default=cel.FICHIER)
    args = parser.parse_args()

    debut = time.perf_counter()
    frame = pl.read_parquet(POPULATION)
    population = cel.totaux_population(frame)
    echantillon = subsample(frame, args.menages)
    del frame
    gc.collect()
    print(f"sous-échantillon : {echantillon['household_id'].n_unique():,} ménages, "
          f"{echantillon.height:,} personnes ; mémoire {_memoire_go():.2f} Go", flush=True)

    passe = run(echantillon, year=cel.ANNEE, tier="full", impute_niches=True,
                impute_capital=True, impute_ij=True, impute_consommation=True)
    print(f"passe : {passe.timings} ; mémoire {_memoire_go():.2f} Go", flush=True)
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    meta = {
        "construit": dt.date.today().isoformat(), "commit": commit,
        "population": POPULATION.name,
        "population_sha256": hashlib.sha256(POPULATION.read_bytes()).hexdigest(),
        "menages_echantillon": args.menages, "graine": SAMPLE_SEED,
        "passe": {"annee": cel.ANNEE, "tier": "full", "imputations":
                  ["niches", "capital", "ij", "consommation"], "timings": passe.timings},
        "totaux_population": population,
    }
    cellules = cel.construire(passe.households, passe.persons, echantillon, meta)
    lignes = cel.recoupements(cellules, population)
    meta["recoupements"] = [
        {"ligne": r.ligne, "cellules": r.cellules, "reference": r.reference,
         "ecart": r.ecart, "tolerance": r.tolerance, "tient": r.tient, "source": r.source}
        for r in lignes]
    meta["duree_s"] = round(time.perf_counter() - debut, 1)
    meta["memoire_pic_go"] = round(_memoire_go(), 2)
    cellules = cel.Cellules(valeurs=cellules.valeurs, parts_offre=cellules.parts_offre,
                            meta=meta)
    chemin = cellules.ecrire(args.sortie)
    manifeste = chemin.with_suffix(".manifest.json")
    manifeste.write_text(json.dumps(
        {k: v for k, v in meta.items() if k != "totaux_population"}, indent=1,
        ensure_ascii=False) + "\n", encoding="utf-8")
    for r in lignes:
        verdict = {None: "dit", True: "tient", False: "HORS TOLÉRANCE"}[r.tient]
        print(f"  {r.ligne:<48} {r.ecart:+.4f}  ({verdict})")
    print(f"écrit {chemin} en {meta['duree_s']} s, pic {meta['memoire_pic_go']} Go")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
