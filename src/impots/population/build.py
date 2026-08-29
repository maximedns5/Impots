"""Build the population parquet: skeleton + children + incomes, deterministically.

One entry point so that "the population" is a single reproducible artefact rather
than a sequence of notebook cells. Same seed and same manifested inputs must give
the same file, byte for byte, because the golden aggregates are asserted to the
euro (§5).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from impots.population import margins
from impots.population.incomes import attach_incomes
from impots.population.ingest import load_manifest
from impots.population.skeleton import SEED, build_skeleton

PROCESSED = Path(__file__).resolve().parents[3] / "data" / "processed"

#: The parquet contract every later stage codes against (§4.1).
SCHEMA: dict[str, pl.DataType] = {
    "person_id": pl.Int64,
    "household_id": pl.String,
    "foyer_id": pl.String,
    "famille_id": pl.String,
    "weight": pl.Float64,
    "age": pl.Int64,
    "sex": pl.String,
    "region": pl.String,
    "role_menage": pl.String,
    "role_foyer": pl.String,
    "role_famille": pl.String,
    "statut_activite": pl.String,
    "statut_occupation": pl.String,
    "zone_apl": pl.String,
    "is_salarie": pl.Boolean,
    "pcs": pl.String,
    "secteur_public": pl.Boolean,
    "quotite_travail": pl.Float64,
    "parent_isole": pl.Boolean,
    "synthetic": pl.Boolean,
    "salaire_brut_annuel": pl.Float64,
    "pension_annuelle": pl.Float64,
    "chomage_annuel": pl.Float64,
    "loyer_mensuel": pl.Float64,
}


def build(vintage: str = "2024", seed: int = SEED) -> tuple[Path, dict]:
    """Build the population and write it, with a manifest of what went into it."""
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    frame, skeleton_stats = build_skeleton(children_per_household=children, seed=seed)
    frame, income_stats = attach_incomes(frame, seed=seed)

    missing = set(SCHEMA) - set(frame.columns)
    if missing:
        raise RuntimeError(f"population frame is missing columns {sorted(missing)}")
    frame = frame.select(list(SCHEMA)).cast(SCHEMA)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    path = PROCESSED / f"population_{vintage}.parquet"
    frame.write_parquet(path)

    provenance = {
        "vintage": vintage,
        "built": date.today().isoformat(),
        "seed": seed,
        "rows": frame.height,
        "households": frame["household_id"].n_unique(),
        "branch": "A' — EEC household structure, synthetic incomes (D-012)",
        "inputs": {
            name: {"sha256": entry.sha256, "url": entry.url}
            for name, entry in load_manifest().items()
        },
        "skeleton": asdict(skeleton_stats),
        "incomes": asdict(income_stats),
    }
    (PROCESSED / f"population_{vintage}.manifest.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path, provenance
