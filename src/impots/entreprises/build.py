"""Build the firm population parquet from a manifested cell table.

The cell table is the seam. Locally it comes from SIRENE × ESANE; in CI it comes
from `tests/fixtures/firm_cells.json`, which is invented. Either way the build
reads the same JSON shape, so nothing downstream knows or cares which it got —
and the raw statistical files never enter the repository, which the data-commit
guard enforces.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

import polars as pl

from impots.entreprises.population import SEED, Cell, build_firms

PROCESSED = Path(__file__).resolve().parents[3] / "data" / "processed"
FIXTURE_CELLS = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "firm_cells.json"

#: The parquet contract every later stage codes against.
SCHEMA: dict[str, pl.DataType] = {
    "firm_id": pl.UInt32,
    "cell": pl.Int64,
    "naf_section": pl.String,
    "taille": pl.String,
    "weight": pl.Float64,
    "chiffre_affaires": pl.Float64,
    "valeur_ajoutee": pl.Float64,
    "resultat_comptable": pl.Float64,
    "benefice_imposable": pl.Float64,
    "capital_libere_detenu_personnes_physiques": pl.Boolean,
}


def load_cells(path: Path) -> tuple[list[Cell], float, str]:
    """Read a cell table. Returns the cells, the fiscal ratio, and the vintage."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    cells = [Cell(**cell) for cell in raw["cells"]]
    return cells, float(raw["fiscal_to_accounting"]), str(raw.get("vintage", "unknown"))


def build(cells_path: Path | None = None, seed: int = SEED) -> tuple[Path, dict]:
    """Build the firm population and write it with a provenance manifest."""
    path = cells_path or FIXTURE_CELLS
    cells, ratio, vintage = load_cells(path)
    firms, stats = build_firms(cells, fiscal_to_accounting=ratio, seed=seed)

    missing = set(SCHEMA) - set(firms.columns)
    if missing:
        raise RuntimeError(f"firm frame is missing columns {sorted(missing)}")
    firms = firms.select(list(SCHEMA)).cast(SCHEMA)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / f"firms_{vintage}.parquet"
    firms.write_parquet(out)

    provenance = {
        "vintage": vintage,
        "built": date.today().isoformat(),
        "seed": seed,
        "cells_from": str(path.name),
        "cells_are_synthetic": path == FIXTURE_CELLS,
        "population": asdict(stats),
    }
    (PROCESSED / f"firms_{vintage}.manifest.json").write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return out, provenance
