#!/usr/bin/env python
"""Phase 7 L4 M0 — the Stat 39 gate, as assertions that stay.

The gate asked two questions the spec could not answer from the desk, one of them carrying
an explicit UNMEASURED label. This script is the answers made re-runnable, so a vintage bump
fails on the traps instead of letting a reader rediscover them.

WHAT IT ASSERTS, AND WHY EACH ONE COST SOMETHING TO LEARN:

1. **Tableau 1's ten sectors sum to «Tous secteurs», exactly.** The table also carries a
   «dont industrie manufacturière» line, which is a SUBSET of Industrie: adding it would
   double-count 31,4 md€. The sum is asserted with that line excluded, and the exactness of
   the match is what proves the exclusion is the right one.

2. **IS brut / résultat fiscal is NOT an effective rate**, and the file proves it on its own
   numbers: the aggregate ratio is 40,1 % against a 25 % statutory rate, and «Autres
   activités» reaches 125,8 %. A tax cannot exceed its base. Asserted as ABOVE the statutory
   rate — deliberately, because the day it falls below, the two columns would have become
   comparable and that is a change worth failing on.

3. **The reason, from the file's own sheets**: résultat fiscal = bénéfice imposable +
   déficit. 283,62 − 111,9 = 171,72 against 172,0 published. Résultat fiscal is NET of
   deficits; IS is levied on the POSITIVE base. Two perimeters, one ratio, and the ratio is
   meaningless.

4. **On the right denominator the rate is sane**: IS / bénéfice imposable = 24,35 %, against
   the publication's own «taux moyen d'imposition» of 24,26 % — 0,09 point apart, and just
   under the 25 % statutory rate exactly as the 15 % reduced-rate slice implies.

5. **The déficit series is a FLOW, not a STOCK.** This is the spec's UNMEASURED item.
   Graphique 2 carries the déficit IMPUTED each year (-111,9 md€ in 2024), which is what was
   absorbed, not what remains to be absorbed. Stat 39 does not carry the stock of déficits
   reportables. Asserted by shape: a stock would not swing year to year the way this does.

Usage: `.venv/bin/python scripts/verify_stat39.py` — needs the manifested Stat 39 data file.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "data" / "raw" / "dgfip_stat_39_impot_benefice_2024_donnees.xlsx"

#: The statutory normal rate in 2024. A ratio of tax to its own base cannot exceed it.
IS_TAUX_NORMAL = 0.25

#: Measured at the gate, to be failed on if the file moves.
EXPECTED_SECTORS = 10
AGGREGATE_RATIO = 0.4014          # IS brut / résultat fiscal — the WRONG denominator
EFFECTIVE_RATE = 0.2435           # IS brut / bénéfice imposable — the right one
PUBLISHED_MEAN_RATE = 0.2426      # the publication's own «taux moyen d'imposition»
DEFICIT_2024_MDE = -111.9


def _check(condition: bool, message: str, failures: list[str]) -> None:
    print(("  OK    " if condition else "  ÉCHEC ") + message)
    if not condition:
        failures.append(message)


def main() -> int:
    if not WORKBOOK.exists():
        print(f"{WORKBOOK} absent — voir data/raw/MANIFEST.json", file=sys.stderr)
        return 1

    import openpyxl

    failures: list[str] = []
    book = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)

    print("=== 1. Tableau 1 : les secteurs somment au total ===")
    rows = [(str(r[1]).strip(), r[2], r[5])
            for r in book["Tableau 1"].iter_rows(min_row=3, max_row=16, max_col=6,
                                                 values_only=True)
            if r[1] and r[2] is not None]
    total_rf = next(v for n, v, _i in rows if n.startswith("Tous"))
    total_is = next(i for n, _v, i in rows if n.startswith("Tous"))
    # «dont industrie manufacturière» is a SUBSET of Industrie. Including it would
    # double-count 31,4 md€, and the sum below would miss by exactly that.
    parts = [(n, v, i) for n, v, i in rows if not n.startswith(("Tous", "dont", "Source"))]
    _check(len(parts) == EXPECTED_SECTORS,
           f"{len(parts)} secteurs hors total et hors « dont » (attendu "
           f"{EXPECTED_SECTORS})", failures)
    residual = sum(v for _n, v, _i in parts) / total_rf - 1
    _check(abs(residual) < 1e-6,
           f"somme des résultats fiscaux = total à {residual:+.2e} près — la ligne "
           f"« dont » est donc bien exclue", failures)

    print("\n=== 2. IS/résultat fiscal N'EST PAS un taux effectif ===")
    ratio = total_is / total_rf
    worst = max(i / v for _n, v, i in parts)
    _check(ratio > IS_TAUX_NORMAL,
           f"rapport agrégé {ratio:.1%} > taux normal {IS_TAUX_NORMAL:.0%} : un impôt ne "
           f"peut pas dépasser sa base, donc les deux colonnes ne partagent pas de "
           f"périmètre", failures)
    _check(worst > 1.0,
           f"et un secteur atteint {worst:.1%} — au-dessus de 100 %, ce qui est "
           f"arithmétiquement impossible pour un taux effectif", failures)
    # Pinned to the gate's measurement, not merely documented: a constant that nothing
    # reads is decoration, and this project has already shipped one (UNEXPLAINED_TOLERANCE,
    # defined and never read, D-111's module).
    _check(abs(ratio - AGGREGATE_RATIO) < 0.005,
           f"rapport agrégé {ratio:.2%} ≈ la valeur du gate ({AGGREGATE_RATIO:.2%})",
           failures)

    print("\n=== 3. la raison : résultat fiscal = bénéfice imposable + déficit ===")
    # TWO TRAPS IN ONE SHEET, both silent if guessed at. The row LABELS sit in column 1,
    # not column 0 — the chart data starts at row 21, under a title block. And every value
    # is stored as a STRING ('18.223428762'), so an isinstance(x, float) filter yields an
    # empty series and a sum of zero rather than an error. Same class as the REI's
    # comma-decimal columns and the YAML that read 6e-05 as text.
    def numeric(value: Any) -> float | None:
        try:
            return float(str(value).replace(",", "."))
        except (TypeError, ValueError):
            return None

    graph: dict[str, list[float]] = {}
    for row in book["Graphique 2"].iter_rows(min_row=21, max_row=30, max_col=9,
                                             values_only=True):
        if row[1] is None:
            continue
        values = [v for v in (numeric(c) for c in row[2:]) if v is not None]
        if values:
            graph[str(row[1]).strip()] = values

    if not graph:
        raise RuntimeError("Graphique 2 n'a rendu aucune série : la forme du fichier a bougé")
    bi = sum(series[-1] for key, series in graph.items() if key.startswith("B.I."))
    deficit = graph["Déficit"][-1]
    reconstructed = bi + deficit
    _check(abs(reconstructed / (total_rf / 1e9) - 1) < 0.01,
           f"B.I. {bi:.2f} + déficit {deficit:.1f} = {reconstructed:.2f} md€ contre "
           f"{total_rf / 1e9:.1f} publié ({reconstructed / (total_rf / 1e9) - 1:+.2%})",
           failures)

    print("\n=== 4. sur le bon dénominateur, le taux est sain ===")
    effective = (total_is / 1e9) / bi
    _check(effective < IS_TAUX_NORMAL,
           f"IS / bénéfice imposable = {effective:.2%}, SOUS le taux normal de "
           f"{IS_TAUX_NORMAL:.0%} — comme la tranche à 15 % l'implique", failures)
    _check(abs(effective - EFFECTIVE_RATE) < 0.005,
           f"taux effectif {effective:.2%} ≈ la valeur du gate ({EFFECTIVE_RATE:.2%})",
           failures)
    _check(abs(effective - PUBLISHED_MEAN_RATE) < 0.005,
           f"et à {abs(effective - PUBLISHED_MEAN_RATE) * 100:.2f} point du « taux moyen "
           f"d'imposition » publié ({PUBLISHED_MEAN_RATE:.2%})", failures)

    print("\n=== 5. le déficit est un FLUX, pas un STOCK (l'item NON MESURÉ de la spec) ===")
    series = graph["Déficit"]
    swing = max(series) / min(series)
    _check(abs(deficit - DEFICIT_2024_MDE) < 1.0,
           f"déficit imputé 2024 = {deficit:.1f} md€ (mesuré au gate "
           f"{DEFICIT_2024_MDE})", failures)
    _check(swing < 0.7,
           f"la série varie de {min(series):.1f} à {max(series):.1f} md€ sur "
           f"{len(series)} ans : c'est ce qui a été IMPUTÉ chaque année, pas ce qui reste "
           f"à imputer. **Stat 39 ne porte pas le stock de déficits reportables.**",
           failures)

    print()
    if failures:
        print(f"{len(failures)} assertion(s) en échec :", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print("Stat 39 vérifié : les constats du gate L4 tiennent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
