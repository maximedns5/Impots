#!/usr/bin/env python
"""Phase 7 L1 M0 — the top-tail gate: how thin is the synthetic upper tail, measured.

L1 proposes raking the synthetic income distribution's upper tail to DGFiP n° 41's
published fractiles. Before any of that is built, this gate answers the only question that
decides whether it is worth building: **how far off is the tail today, and at which
fractile does the gap open?**

WHAT IS COMPARED, AND THE TRAP AVOIDED IN NAMING IT.

The comparator is n° 41's Tableau 2, column «RFR par part fiscale — Moyenne (en €)»,
classified by decile of RFR per part, with «dont dernier centième» and «dont dernier
millième» beneath the last decile. Reading the first ten columns of that sheet suggests it
publishes only TAX by fractile — the group header sits one row above the column header, so
the income column looks like a tax column. It is not: the top millième's 916 590 € is a
mean RFR per part. A0's L4 gate had just refused a lever for exactly the shape this
resembles, which made the misreading easy and would have refused L1 wrongly.

**Fractiles are of foyers, weighted, ordered by RFR per part** — the same construction the
publication uses, and the same one `runner._niche_bases` already computes for the niche
imputation. Foyer weight is the MEAN of member weights, not the sum: the survey weights a
dwelling together, and summing would multiply every foyer-level total by foyer size.

WHY THE TAIL IS MEASURED AT SEVERAL SAMPLE SIZES. The top millième of a 4 000-foyer
subsample is four foyers. A0 v2 established, at cost, that quantities of this kind are not
resolvable on a subsample — so the gate measures the ladder at several sizes and REPORTS
the spread rather than quoting one. A single-size reading of a tail is a reading of a draw.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

#: DGFiP Statistiques n° 41 (novembre 2025), Tableau 2, colonne «RFR par part fiscale —
#: Moyenne (en €)». Read from the manifested workbook by `published_ladder`, never typed:
#: a comparator copied by hand is a comparator nobody can re-derive.
WORKBOOK = ROOT / "data" / "raw" / "dgfip_stat_41_ir_2024_tables.xlsx"

#: The first decile is published «n.s.» — not significant. It is excluded from the
#: comparison rather than treated as zero, because a missing comparator and a zero one look
#: identical in a residual column.
NOT_SIGNIFICANT = "n.s."


def published_ladder() -> dict[str, float]:
    """The published mean RFR per part, by fractile."""
    import openpyxl

    book = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    ladder: dict[str, float] = {}
    for row in book["Tableau 2"].iter_rows(min_row=5, max_row=16, max_col=4,
                                           values_only=True):
        label, value = row[1], row[3]
        if not label or value is None:
            continue
        if isinstance(value, str) and NOT_SIGNIFICANT in value:
            continue
        if isinstance(value, (int, float)):
            ladder[" ".join(str(label).split())] = float(value)
    return ladder


def simulated_ladder(sample: int | None) -> dict[str, float]:
    """Our population's mean RFR per part at the same fractiles."""
    import numpy as np
    import polars as pl

    from impots.engine.system import baseline
    from impots.population.build import PROCESSED
    from impots.population.runner import subsample
    from impots.population.to_openfisca import build_simulation

    frame = pl.read_parquet(PROCESSED / "population_2024.parquet")
    if sample is not None:
        frame = subsample(frame, sample)

    # `build_simulation`, not a tier-aware runner pass: RFR is a light-tier variable
    # (engine/outputs.py declares it so), and this gate needs no reform, no second pass
    # and no benefits cascade. One simulation, two calculate() calls.
    simulation = build_simulation(frame, baseline(), 2024).simulation
    rfr = np.asarray(simulation.calculate("rfr", "2024"), dtype=np.float64)
    parts = np.asarray(simulation.calculate("nbptr", "2024"), dtype=np.float64)
    if (parts <= 0).any():
        raise RuntimeError("un foyer déclare zéro part : le RFR par part serait indéfini")
    per_part = rfr / parts
    weights = (frame.group_by("foyer_id").agg(pl.col("weight").mean().alias("weight"))
               .sort("foyer_id")["weight"].to_numpy().astype(np.float64))

    order = np.argsort(per_part)
    per_part, weights = per_part[order], weights[order]
    cumulative = np.cumsum(weights)
    total = cumulative[-1]

    def mean_between(low: float, high: float) -> float:
        """Weighted mean of RFR per part between two cumulative-weight fractions."""
        mask = (cumulative > low * total) & (cumulative <= high * total)
        if not mask.any() or weights[mask].sum() == 0:
            return float("nan")
        return float((per_part[mask] * weights[mask]).sum() / weights[mask].sum())

    ladder = {f"{i + 1}e dixième": mean_between(i / 10, (i + 1) / 10) for i in range(10)}
    ladder["dernier dixième"] = ladder.pop("10e dixième")
    ladder["dont dernier centième"] = mean_between(0.99, 1.0)
    ladder["dont dernier millième"] = mean_between(0.999, 1.0)
    return ladder


def main() -> int:
    import math

    sizes = [4_000, 20_000, None]
    published = published_ladder()
    print(f"comparateur : DGFiP n° 41, Tableau 2 — {len(published)} fractiles publiés\n")

    rows: dict[str, list[float]] = {}
    for size in sizes:
        label = "complète" if size is None else f"n={size}"
        print(f"  passe {label}…", flush=True)
        ladder = simulated_ladder(size)
        for key, value in ladder.items():
            rows.setdefault(key, []).append(value)

    header = "fractile".ljust(24) + "publié".rjust(12) + "".join(
        ("complète" if s is None else f"n={s}").rjust(13) for s in sizes) + "   écart(complet)"
    print("\n" + header)
    print("-" * len(header))
    for key, target in published.items():
        simulated = rows.get(key)
        if simulated is None:
            continue
        cells = "".join(
            ("     n/d" if math.isnan(v) else f"{v:,.0f}".replace(",", " ")).rjust(13)
            for v in simulated)
        full = simulated[-1]
        gap = "  n/d" if math.isnan(full) else f"{full / target - 1:+.1%}"
        print(f"{key:24}{target:12,.0f}".replace(",", " ") + cells + f"   {gap:>12}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
