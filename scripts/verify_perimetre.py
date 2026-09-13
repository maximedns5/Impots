#!/usr/bin/env python
"""Phase 7 C1 — the industrie/immobilier perimeter diagnostic, as assertions that stay.

The 2026-09-02 addendum offered two cheap mechanical checks for the two red firm lines,
under the standing rule «mechanical before economic». Their conclusion was already written
into `margins.POOLED_SECTORS` as prose. **Nothing verified it**, which is the same state
the REI findings were in before `verify_rei.py`: a measurement made once and trusted
thereafter.

WHAT IT ASSERTS:

1. **Check one, on a quantity the model never touches** — firm counts by sector. Ésane's
   count over DGFiP's runs at 1,90 to 2,22 across the market-champ sectors (the IS-liability
   rate) and **0,48 for activités immobilières**, a fourfold outlier. If two sources
   disagree that badly on a count neither the model nor the reform can move, the residual
   is perimeter, not model.

2. **Check two, decomposing the residual by size class** — 88,4 % of the modelled industrie
   IS sits in ETI and GE. Concentration in the largest firms points at group structure;
   uniformity across sizes would have pointed at base construction instead.

3. **The residual itself** — modelled industrie IS against the published figure, +38,3 %.
   Pinned so that a change in the model or the vintage fails here rather than quietly
   invalidating the diagnosis built on it.

THE SCOPE CORRECTION THIS SCRIPT CARRIES. The recorded claim said the ratio runs 1,90-2,22
«in every sector». It does not: administration reaches 8,94, autres activités 4,33, finance
0,70 and agriculture 0,12. Those four sit OUTSIDE Ésane's «principalement marchands» champ,
which `cells.py` already names — they are not comparable and the original sentence swept
them in. Scoped to the market champ the claim is exact, and immobilier is then the sole
outlier, which is what makes the diagnosis work.

TWO READING TRAPS IN THESE FILES, both silent:

* **Ésane declares no dimensions.** `ws.max_row` is 1 and `calculate_dimension()` returns
  «A1:A1», so `iter_rows` WITHOUT an explicit `max_row` yields nothing at all — an empty
  result that looks like a finding. An earlier run of this very check built an empty dict
  and only failed because `min()` raised on it.
* **Stat 39's count column is headed «en milliers» and holds units.** «Tous secteurs» is
  2 718 376,9, and Graphique 1 independently gives 2,718 MILLION firms. Multiplying by a
  thousand, as the header instructs, puts every ratio at 0,00.

Usage: `.venv/bin/python scripts/verify_perimetre.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ESANE = ROOT / "data" / "raw" / "insee_esane2023_caracteristiques_par_taille.xlsx"
STAT39 = ROOT / "data" / "raw" / "dgfip_stat_39_impot_benefice_2024_donnees.xlsx"
CELLS = ROOT / "data" / "processed" / "firm_cells_2023.json"

#: a10 code -> the Stat 39 sector label it aggregates to.
A10 = {"AZ": "Agriculture, sylviculture et pêche", "BE": "Industrie",
       "FZ": "Construction", "GI": "Commerce, transports, hébergement et restauration",
       "JZ": "Information et communication", "KZ": "Activités financières et d'assurance",
       "LZ": "Activités immobilières",
       "MN": "Activités spécialisées, scientifiques et de soutien",
       "OQ": "Administration, enseignement, santé", "RU": "Autres activités"}

#: The sectors inside Ésane's «principalement marchands» champ. The others are not
#: comparable on a firm count and the original claim's «every sector» swept them in.
MARKET_CHAMP = ("Industrie", "Construction",
                "Commerce, transports, hébergement et restauration",
                "Information et communication",
                "Activités spécialisées, scientifiques et de soutien",
                "Activités immobilières")

RATIO_BAND = (1.85, 2.30)          # measured 1,90-2,22 across the market champ
IMMOBILIER_RATIO = 0.48            # the fourfold outlier
ETI_GE_SHARE = 0.884               # 88,4 % of modelled industrie IS
INDUSTRIE_RESIDUAL = 0.383         # +38,3 % against the published figure
PUBLISHED_INDUSTRIE_IS = 15.229616141e9


def _check(condition: bool, message: str, failures: list[str]) -> None:
    print(("  OK    " if condition else "  ÉCHEC ") + message)
    if not condition:
        failures.append(message)


def main() -> int:
    import openpyxl
    import polars as pl

    for path in (ESANE, STAT39, CELLS):
        if not path.exists():
            print(f"{path} absent — voir data/raw/MANIFEST.json", file=sys.stderr)
            return 1

    failures: list[str] = []

    print("=== 1. effectifs par secteur : une grandeur que le modèle ne touche pas ===")
    sheet = openpyxl.load_workbook(ESANE, read_only=True, data_only=True)[
        "princ_caract_taille"]
    # max_row EXPLICITE: the workbook declares no dimensions (A1:A1), so an unbounded
    # iter_rows returns nothing and the check would pass on an empty set.
    esane: dict[str, float] = {}
    for row in sheet.iter_rows(min_row=13, max_row=4000, max_col=5, values_only=True):
        if (row[0] == "a10" and row[1] in A10 and row[3]
                and str(row[3]).startswith("Ensemble") and isinstance(row[4], (int, float))):
            esane[A10[row[1]]] = esane.get(A10[row[1]], 0.0) + float(row[4])
    _check(len(esane) == len(A10),
           f"{len(esane)} secteurs lus dans Ésane (attendu {len(A10)}) — un max_row "
           f"implicite en rendrait zéro sans erreur", failures)

    table = openpyxl.load_workbook(STAT39, read_only=True, data_only=True)["Tableau 1"]
    # The column is headed «en milliers» and holds UNITS. Not multiplied, deliberately.
    dgfip = {" ".join(str(r[1]).split()): float(r[6])
             for r in table.iter_rows(min_row=3, max_row=16, max_col=7, values_only=True)
             if r[1] and r[6] is not None
             and not str(r[1]).startswith(("Tous", "dont", "Source"))}
    _check(abs(sum(dgfip.values()) / 2_718_376.9 - 1) < 0.01,
           "la colonne « en milliers » porte en fait des UNITÉS : la somme vaut 2,72 M "
           "d'entreprises, ce que le Graphique 1 confirme en millions", failures)

    ratios = {s: esane[s] / dgfip[s] for s in esane if s in dgfip}
    inside = {s: r for s, r in ratios.items()
              if s in MARKET_CHAMP and s != "Activités immobilières"}
    low, high = RATIO_BAND
    _check(all(low <= r <= high for r in inside.values()),
           f"champ marchand hors immobilier : {min(inside.values()):.2f} à "
           f"{max(inside.values()):.2f}, dans [{low}, {high}]", failures)
    immo = ratios["Activités immobilières"]
    _check(abs(immo - IMMOBILIER_RATIO) < 0.02,
           f"activités immobilières : {immo:.2f} — sous 1, donc DGFiP compte PLUS "
           f"d'unités légales qu'Ésane n'a d'entreprises profilées", failures)
    outside = {s: r for s, r in ratios.items() if s not in MARKET_CHAMP}
    _check(any(r > high or r < low for r in outside.values()),
           f"et hors champ marchand le rapport sort de la bande ({', '.join(f'{s[:18]} {r:.2f}' for s, r in sorted(outside.items()))}) "
           f"— c'est la portée que l'énoncé d'origine avait omise", failures)

    print("\n=== 2. décomposition du résidu industrie par taille ===")
    from impots.entreprises import aggregate as aggregate_module  # noqa: F401
    from impots.entreprises import runner as runner_module
    from impots.entreprises.build import load_cells
    from impots.entreprises.population import build_firms

    cells, ratio, _vintage = load_cells(CELLS)
    firms, _stats = build_firms(cells, fiscal_to_accounting=ratio, seed=20260101)
    priced = runner_module.run(firms, year=2026).firms
    column = next(c for c in priced.columns if c.startswith("is_") or c == "impot_societes")
    industrie = priced.filter(pl.col("naf_section").is_in(["B", "C", "D", "E"]))
    total = float((industrie[column] * industrie["weight"]).sum())

    big = industrie.filter(pl.col("taille").is_in(["ETI", "GE"]))
    share = float((big[column] * big["weight"]).sum()) / total
    _check(abs(share - ETI_GE_SHARE) < 0.03,
           f"{share:.1%} de l'IS industrie modélisé est en ETI et GE — concentration "
           f"dans les grandes unités, donc effet de groupe et non construction d'assiette",
           failures)

    print("\n=== 3. le résidu lui-même, épinglé ===")
    residual = total / PUBLISHED_INDUSTRIE_IS - 1
    _check(abs(residual - INDUSTRIE_RESIDUAL) < 0.03,
           f"industrie modélisée {total / 1e9:.3f} md€ contre {PUBLISHED_INDUSTRIE_IS / 1e9:.3f} "
           f"publié, soit {residual:+.1%}", failures)

    print()
    if failures:
        print(f"{len(failures)} assertion(s) en échec :", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print("Périmètre vérifié : le diagnostic industrie/immobilier tient, et sa portée "
          "est celle du champ marchand.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
