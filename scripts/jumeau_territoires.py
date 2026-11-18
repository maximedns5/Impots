"""La table de passage des cellules du jumeau aux territoires (D-645), écrite une fois.

    PYTHONPATH=src python scripts/jumeau_territoires.py --passe <passe>.parquet

`--passe` : les ménages d'une passe de référence déjà faite sur toute la population de
D-553 (`household_id`, `weight`, `n_persons`, `n_aged_14_plus`, `n_children_under_14`,
`revenu_disponible`), par exemple celle d'une étude au palier complet ; aucune passe n'est
lancée ici. Écrit `src/impots/jumeau/parametres/territoires.json` (un agrégat, commité).
"""

from __future__ import annotations

import argparse
import subprocess
from datetime import date
from pathlib import Path

import polars as pl

from impots.jumeau import table_territoires as tt

ROOT = Path(__file__).resolve().parents[1]
POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"
EEC = ROOT / "data" / "raw" / "FD_EEC_2024.parquet"


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--passe", type=Path, required=True)
    a.add_argument("--sortie", type=Path, default=tt.FICHIER)
    args = a.parse_args()
    population = pl.read_parquet(POPULATION, columns=[
        "person_id", "household_id", "region", "departement", "zone_apl", "role_menage"])
    eec = pl.read_parquet(EEC, columns=["IDENT", "TRIM", "STCOMM2020"])
    passe = pl.read_parquet(args.passe)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True, check=False).stdout.strip()
    meta = {"construit": date.today().isoformat(), "commit": commit,
            "population": POPULATION.name, "population_sha256": tt.empreinte(POPULATION),
            "eec": EEC.name, "eec_sha256": tt.empreinte(EEC),
            "passe": args.passe.name, "passe_sha256": tt.empreinte(args.passe),
            "passe_menages": passe.height,
            "commande": "PYTHONPATH=src python scripts/jumeau_territoires.py --passe <passe>"}
    table = tt.construire(population, eec, passe, meta=meta)
    print(tt.ecrire(table, args.sortie))


if __name__ == "__main__":
    main()
