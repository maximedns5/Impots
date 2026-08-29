"""M0 reconnaissance gate for the EEC fichier détail (PHASE1_SPEC.md §3).

Answers the one question the Phase 1 spec could not verify remotely — does the
open EEC FD group individuals into households, and does it carry any income? —
and prints the variable inventory the branch decision is made from.

Run:  python scripts/verify_eec.py [--inventory]

Needs `data/raw/FD_EEC_2024.parquet` and `data/raw/Varmod_EEC_2024.csv`; download
them from insee.fr/fr/statistiques/8632441 (Licence Ouverte / Etalab).
Findings are written up in docs/M0_RECON.md.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

import polars as pl

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
FD = RAW / "FD_EEC_2024.parquet"
VARMOD = RAW / "Varmod_EEC_2024.csv"

EXPECTED_ROWS = 353_420
EXPECTED_COLS = 83
#: French population aged 15+, order of magnitude. The spec asks for ±10 %.
POPULATION_15_PLUS = 55_000_000

#: Names that would carry a wage or an income if the FD had one. Checked
#: explicitly rather than by eyeballing the inventory, because "there is no
#: income variable" is the single most consequential finding of M0.
INCOME_LIKE = (
    "SAL", "REV", "RSTG", "MONT", "GAIN", "INC", "PENS", "CHOM_M", "RETR",
    "TRNM", "ZSAL", "SALRED", "SALMEE",
)
#: Names that would group persons into a dwelling or household.
GROUPING_LIKE = ("IDENT", "IDMEN", "IDLOG", "IDANON", "MENAGE", "NOI")


def fail(message: str) -> None:
    print(f"  FAIL  {message}")
    sys.exit(1)


def ok(message: str) -> None:
    print(f"  ok    {message}")


def load_varmod() -> tuple[list[str], dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    """Variable order, per-variable metadata, and per-variable modality labels."""
    order: list[str] = []
    meta: dict[str, dict[str, str]] = {}
    mods: dict[str, dict[str, str]] = defaultdict(dict)
    with VARMOD.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            code = row["COD_VAR"].strip()
            if code not in meta:
                order.append(code)
                meta[code] = {
                    "label": row["LIB_VAR"].strip(),
                    "type": row["TYPE_VAR"].strip(),
                    "length": row["LONG_VAR"].strip(),
                }
            if row["COD_MOD"].strip():
                mods[code][row["COD_MOD"].strip()] = row["LIB_MOD"].strip()
    return order, meta, mods


def main() -> None:
    if not FD.exists():
        fail(f"{FD} missing — download the FD from insee.fr/fr/statistiques/8632441")
    df = pl.read_parquet(FD)
    order, meta, mods = load_varmod()

    print("=== 1. shape and weight ===")
    rows, cols = df.shape
    if rows != EXPECTED_ROWS:
        fail(f"row count {rows:,} != {EXPECTED_ROWS:,} — is this the 2024 vintage?")
    ok(f"row count {rows:,}")
    if cols != EXPECTED_COLS:
        fail(f"column count {cols} != {EXPECTED_COLS}")
    ok(f"column count {cols}")

    if "EXTRIAN" not in df.columns:
        fail("EXTRIAN (the annual weight) is missing")
    weight = df["EXTRIAN"]
    if weight.null_count():
        fail(f"EXTRIAN has {weight.null_count()} nulls")
    if weight.min() <= 0:
        fail(f"EXTRIAN has non-positive values (min {weight.min()})")
    total = weight.sum()
    drift = abs(total - POPULATION_15_PLUS) / POPULATION_15_PLUS
    if drift > 0.10:
        fail(f"EXTRIAN sums to {total:,.0f}, more than 10 % from ~{POPULATION_15_PLUS:,}")
    ok(f"EXTRIAN > 0, sums to {total:,.0f} ({drift:+.1%} vs ~{POPULATION_15_PLUS:,} aged 15+)")
    ok(f"EXTRIAN range [{weight.min():.2f}, {weight.max():.2f}]")

    print("\n=== 2. the gate: is there a household identifier? ===")
    grouping = [c for c in df.columns if any(k in c.upper() for k in GROUPING_LIKE)]
    if not grouping:
        fail("no dwelling/household identifier — branch B (synthetic assembly)")
    ok(f"grouping columns present: {', '.join(grouping)}")

    dwellings = df["IDENT"].n_unique()
    quarters = sorted(df["TRIM"].unique().to_list())
    dwelling_quarters = df.select(["IDENT", "TRIM"]).n_unique()
    ok(f"IDENT: {dwellings:,} distinct dwellings over quarters {quarters}")
    ok(f"IDENT x TRIM: {dwelling_quarters:,} dwelling-quarters (the household unit)")

    per_person = Counter(df.group_by(["IDENT", "NOI"]).len()["len"].to_list())
    ok(f"quarters per person: {dict(sorted(per_person.items()))} — this is a rotating panel")

    sizes = Counter(df.group_by(["IDENT", "TRIM"]).len()["len"].to_list())
    biggest = max(sizes)
    if biggest > 15:
        fail(f"a dwelling-quarter holds {biggest} people — IDENT is not a dwelling")
    ok(f"persons per dwelling-quarter: max {biggest}, "
       f"{sizes[1]:,} singles / {sizes[2]:,} pairs")

    print("\n=== 3. the gate: is there any income? ===")
    income = [c for c in df.columns if any(k in c.upper() for k in INCOME_LIKE)]
    numeric = [c for c, t in zip(df.columns, df.dtypes, strict=True) if t.is_numeric()]
    ok(f"numeric columns: {', '.join(numeric)}")
    if income:
        print(f"  ....  name-matched, checking each: {', '.join(income)}")
        for name in income:
            print(f"          {name}: {meta.get(name, {}).get('label', '?')[:80]}")
    real_income = [c for c in income if c in numeric]
    if real_income:
        ok(f"income variables found: {', '.join(real_income)} — branch A with observed wages")
    else:
        print("  ....  NO income variable. Every euro must be imputed from external")
        print("        distributions; there is no donor pool inside the file to hot-deck from.")

    print("\n=== 4. structural variables the skeleton depends on ===")
    for name in ("AGE6", "SEXE", "TYPLOG5", "COUPL_LOG", "ENFRED", "SO", "METRODOM",
                 "STCOMM2020", "ACTEU"):
        if name not in df.columns:
            fail(f"{name} missing — the skeleton cannot be built as designed")
        n_mods = df[name].n_unique()
        print(f"  {name:12} {n_mods:>3} modalities  {meta.get(name, {}).get('label', '')[:66]}")

    relationship = [c for c in df.columns if any(k in c.upper() for k in ("LPR", "LIEN", "RELA"))]
    if relationship:
        ok(f"relationship-to-reference-person variable: {', '.join(relationship)}")
    else:
        print("  ....  NO link-to-reference-person variable: who is whose partner or child")
        print("        must be inferred from TYPLOG5 + COUPL_LOG + AGE6 within each dwelling.")

    youngest = df["AGE6"].min()
    print(f"  ....  youngest age band present: {youngest} "
          f"({mods.get('AGE6', {}).get(str(youngest), '?')}) — under-15s are out of scope")

    if "--inventory" in sys.argv:
        print("\n=== 5. full variable inventory ===")
        print(f"{'VAR':14} {'TYP':5} {'LEN':>5} {'MODS':>5}  LABEL")
        for code in order:
            info = meta[code]
            print(f"{code:14} {info['type']:5} {info['length']:>5} "
                  f"{len(mods.get(code, {})):>5}  {info['label'][:88]}")

    print("\nEEC reconnaissance complete. Findings and the branch decision: docs/M0_RECON.md")


if __name__ == "__main__":
    main()
