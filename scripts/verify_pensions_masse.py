#!/usr/bin/env python
"""The 400,4 Md€ pension target, decomposed box by box, and art. 3 without what is not a retirement (D-210).

D-209 left the level as the remaining suspect: the population draws the DGFiP's whole
« pensions et rentes » (Stat 41, tableau 1) onto retirees. The DGFiP's national 2042
aggregates give the same total box by box, so the split is a reading, not an estimate.

WHAT IT MEASURES:

1. **The decomposition.** Section 1's pension and annuity boxes for 2024 incomes, grouped:
   retirement (1AS-1DS), invalidity (1AZ-1DZ), alimony received (1AO-1DO), foreign-source
   pensions, capital, life annuities. Their sum must land on the calibration target
   (`margins.DECLARED_PENSIONS`) within 0,2 %, or the boxes are not the target's parts.
2. **The counts.** « Nombre » counts filled boxes, so persons: 1AS is the first
   declarant, 1BS the second. The annex's 13,4 M foyers with a retirement pension cannot
   be fewer than the 1AS count, which is the coherence check.
3. **Art. 3 through the engine**, every pension scaled to the retirement boxes' share of
   the target, and the whole 10 % abatement on 2024 incomes under the same scaling,
   against the Voies et moyens line D-207 used.

Scaling every pension is the crudest correction: it keeps who is a pensioner and the
shape of the draw, and moves only the level. That is the point — it isolates the level.

Usage: `.venv/bin/python scripts/verify_pensions_masse.py` (about five minutes; needs
`data/processed/population_2024.parquet` and the manifested 2042 export).
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"
EXPORT = ROOT / "data" / "raw" / "dgfip_ir_2042_nat_export_2026-10-15.csv"

GROUPS = {
    "retraites (1AS-1DS)": "S",
    "invalidité (1AZ-1DZ)": "Z",
    "pensions alimentaires (1AO-1DO)": "O",
    "source étrangère (1AM-1DM)": "M",
    "CI = IR français, non-résidents (1AL-1DL)": "L",
    "exonérées étrangères (1AH-1DH)": "H",
    "capital à 7,5 % (1AT-1DT)": "T",
    "capital des nouveaux PER (1AI-1DI)": "I",
    "rentes viagères à titre onéreux (1AW-1DW)": "W",
    "rentes étrangères (1AR-1DR)": "R",
}
ANNEX_FOYERS_RETRAITE = 13.4e6
ANNEX_GAIN = 1.1e9
VM_120401_REVENUS_2024 = 5.322e9

#: Pinned at D-210.
PINS = {
    "retraites": (374.366e9, 0.001),
    "somme": (400.942e9, 0.001),
    "art3": (1.119e9, 0.01),
    "abattement": (5.273e9, 0.01),
}


def main() -> int:
    from impots import scenarios
    from impots.api.schemas import ReformSpec
    from impots.population import aggregate, margins, runner

    for path in (POPULATION, EXPORT):
        if not path.exists():
            print(f"{path} absent", file=sys.stderr)
            return 1
    failures: list[str] = []

    def pin(name: str, value: float) -> None:
        expected, tolerance = PINS[name]
        if abs(value / expected - 1) > tolerance:
            failures.append(f"{name} : {value:,.0f} contre {expected:,.0f} épinglé")

    boxes = pl.read_csv(EXPORT, separator=";", infer_schema=False, encoding="utf8")
    boxes = boxes.rename({c: c.lstrip("﻿") for c in boxes.columns}).with_columns(
        pl.col("Nombre").cast(pl.Float64), pl.col("Montant").cast(pl.Float64))
    year = boxes.filter(pl.col("Année") == "2024")

    def group(letter: str) -> pl.DataFrame:
        return year.filter(pl.col("Nom").is_in([f"1{d}{letter}" for d in "ABCD"]))

    # 1. The decomposition.
    target = margins.DECLARED_PENSIONS.value
    total = 0.0
    print("1. « pensions et rentes », revenus 2024, case par case :")
    for label, letter in GROUPS.items():
        part = group(letter)
        if part.height != 4:
            failures.append(f"{label} : {part.height} cases au lieu de 4")
        total += part["Montant"].sum()
        print(f"   {label:44s} {part['Montant'].sum() / 1e9:8.3f} Md€ "
              f"{part['Nombre'].sum() / 1e6:6.3f} M cases")
    retraites = group("S")["Montant"].sum()
    print(f"   somme {total / 1e9:.3f} Md€ contre la cible {target / 1e9:.3f} "
          f"({total / target - 1:+.2%}) ; les retraites en font {retraites / target:.1%}")
    if abs(total / target - 1) > 0.002:
        failures.append("les cases ne retombent pas sur la cible de calage")
    pin("retraites", retraites)
    pin("somme", total)

    # 2. The counts.
    first = group("S").filter(pl.col("Nom") == "1AS")["Nombre"].sum()
    holders = group("S").filter(pl.col("Nom").is_in(["1AS", "1BS"]))["Nombre"].sum()
    frame = pl.read_parquet(POPULATION)
    pensioners = frame.filter(pl.col("pension_annuelle") > 0)["weight"].sum()
    print(f"2. déclarants titulaires d'une retraite : {holders / 1e6:.2f} M (1AS "
          f"{first / 1e6:.2f} M) ; pensionnés de la population {pensioners / 1e6:.2f} M")
    print(f"   par personne : {retraites / holders:,.0f} EUR dans les cases, "
          f"{target / pensioners:,.0f} EUR dans la population")
    if first > ANNEX_FOYERS_RETRAITE:
        failures.append("plus de premiers déclarants retraités que de foyers retraités")

    # 3. The engine, every pension scaled to the retirement boxes.
    factor = retraites / target
    scaled = frame.with_columns(pl.col("pension_annuelle") * factor)
    scenario = scenarios.load("plf2027_art_3")
    result = runner.run(scaled, year=scenario.year, reform=scenario.reform, tier="full",
                        sample=20_000)
    gain = -float(aggregate.aggregate(result.households).reform_cost)
    print(f"3. pensions × {factor:.4f} : art. 3 {gain / 1e9:.3f} Md€ contre "
          f"{ANNEX_GAIN / 1e9:.1f} ({gain / ANNEX_GAIN - 1:+.1%})")
    pin("art3", gain)
    result = runner.run(scaled, year=2024, tier="full", sample=20_000,
                        reform=ReformSpec(abattement_pensions_plafond=0.0))
    whole = -float(aggregate.aggregate(result.households).reform_cost)
    print(f"   l'abattement entier, revenus 2024 : {whole / 1e9:.3f} Md€ contre "
          f"{VM_120401_REVENUS_2024 / 1e9:.3f} (VM 120401, toutes pensions)")
    pin("abattement", whole)

    for failure in failures:
        print(f"ÉCHEC  {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
