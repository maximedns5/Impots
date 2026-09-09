#!/usr/bin/env python
"""Re-run the REI reconnaissance as assertions (F5 M0 backfill, D-105.4).

The gate (D-100, `docs/M0_REI.md`) measured these numbers once and wrote them down. That
is a finding. This script makes them a **guard that stays**: run it after any REI vintage
bump, and it fails on the traps rather than letting a reader rediscover them.

WHAT IT ASSERTS, and each one is a trap that cost time the first time:

1. **The CSV is LATIN-1.** A UTF-8 read fails at byte 10082. Asserted explicitly, because
   the tempting fix — `errors="replace"` — corrupts commune names with no error at all.
2. **Shape.** 34 907 rows and 1043 columns; the row count is checked against the published
   commune count rather than against itself.
3. **The columns are titled FB/FNB, never «foncier».** Searching the titles for
   FONCIER|BÂTI returns a handful of variables and **none of them is one of the eighteen
   columns a TF model needs**. Asserted that way rather than as «no match mentions a
   base»: the looser form failed on two CFE rows titled «CFE - BASES BRUTES : PROPRIÉTÉS
   NON BÂTIES», which are not taxe foncière at all. The script caught its own assertion
   being sloppier than the finding it came from.
4. **The per-commune identity**: base x rate = produit, to rounding, on every commune with
   a base. This is the arithmetic the whole module would rest on.
5. **The national reconstruction** against DGFiP Statistiques n° 46 — and against the
   RIGHT figure. The publication leads with 55,1 Md€ INCLUDING annexes and management fees;
   the comparator for a base x rate reconstruction is the next sentence, 43,1 Md€. Taking
   the headline gives -21 % and condemns a correct reading, so both are asserted: the
   reconstruction lands near 43,1 and NOT near 55,1.
6. **The non bâti still fails.** 1,089 Md€ read against 2,7 Md€ published. Asserted as
   FAILING, deliberately: pinning a known hole keeps it visible, and a later reading that
   fixes it will fail this assertion and force the D-entry that records the fix.

Usage: `.venv/bin/python scripts/verify_rei.py` — needs `data/raw/rei_2025.zip`.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

ARCHIVE = Path(__file__).resolve().parents[1] / "data" / "raw" / "rei_2025.zip"

#: Measured at the gate (D-100). Row count is communes; the published count of French
#: communes including the DOM was about 34 900 in 2025, so the file is one row per commune.
EXPECTED_ROWS = 34_907
EXPECTED_COLUMNS = 1_043

#: The strata that make up the foncier bâti, base column then rate column. Rates are in
#: PERCENT in this file, which is trap number seven and the reason for the /100.
FB_STRATA = {
    "commune": ("E11", "E12"),
    "intercommunalité": ("E31", "E32"),
    "TSE": ("E51", "E52"),
    "TSE autres": ("E51A", "E52A"),
    "GEMAPI": ("E51gGEMAPI", "E52gGEMAPI"),
    "TASA": ("E51TASA", "E52TASA"),
}
FNB_STRATA = {"commune": ("B11", "B12"), "intercommunalité": ("B31", "B32"),
              "TSE": ("B51", "B52")}

#: DGFiP Statistiques n° 46 (mai 2026), manifested. The FIRST is the comparator; the
#: second is the headline that must NOT be matched.
PUBLISHED_FB_EUR = 43.1e9
PUBLISHED_FB_WITH_ANNEXES_EUR = 55.1e9
PUBLISHED_FNB_EUR = 2.7e9

#: The reading's declared tolerance against the published bâti. 2 % rather than 1 %: the
#: document does not say which strata count among the «taxes annexes» it excludes, so the
#: two defensible reconstructions (-0,76 % and +0,89 %) must BOTH pass.
FB_TOLERANCE = 0.02

#: The non bâti's measured shortfall, pinned as failing (see point 6 above).
FNB_MEASURED_SHORTFALL = -0.597


class VerificationError(RuntimeError):
    """A REI assertion failed — the file, or our reading of it, has moved."""


def _check(condition: bool, message: str, failures: list[str]) -> None:
    print(("  OK   " if condition else "  ÉCHEC ") + message)
    if not condition:
        failures.append(message)


def main() -> int:
    if not ARCHIVE.exists():
        print(f"{ARCHIVE} absent — télécharger le REI (voir data/raw/MANIFEST.json)",
              file=sys.stderr)
        return 1

    import polars as pl

    failures: list[str] = []
    archive = zipfile.ZipFile(ARCHIVE)
    csv_name = next(n for n in archive.namelist() if n.endswith(".csv"))
    raw = archive.read(csv_name)

    print("=== 1. encodage ===")
    utf8_fails = False
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        utf8_fails = True
    _check(utf8_fails,
           "le CSV n'est PAS de l'UTF-8 (s'il le devenait, la lecture latin-1 ci-dessous "
           "corromprait les libellés)", failures)
    text = raw.decode("latin-1")
    _check(True, "décodé en latin-1", failures)

    frame = pl.read_csv(text.encode("utf-8"), separator=";", infer_schema_length=0)

    print("\n=== 2. forme ===")
    _check(frame.height == EXPECTED_ROWS,
           f"{frame.height:,} lignes (attendu {EXPECTED_ROWS:,})".replace(",", " "),
           failures)
    _check(frame.width == EXPECTED_COLUMNS,
           f"{frame.width} colonnes (attendu {EXPECTED_COLUMNS})", failures)

    print("\n=== 3. le fichier ne dit jamais « foncier » ===")
    trace_name = next(n for n in archive.namelist() if n.endswith(".xlsx"))
    import io

    import openpyxl

    sheet = openpyxl.load_workbook(io.BytesIO(archive.read(trace_name)),
                                   read_only=True).worksheets[0]
    titles = [(r[1], str(r[3] or "")) for r in
              sheet.iter_rows(min_row=2, max_col=8, values_only=True) if r[1]]
    # The claim is NOT «no match mentions a base» — it is that no match is one of the
    # columns a TF model actually needs. The first version asserted the looser thing and
    # failed on two CFE rows titled «CFE - BASES BRUTES : PROPRIÉTÉS NON BÂTIES», which
    # contain both «BÂTIES» and «BASES» and are not taxe foncière at all. The script
    # caught the assertion being sloppier than the finding it came from.
    word = re.compile(r"FONCIER|BATI|BÂTI", re.I)
    named = [(v, t) for v, t in titles if word.search(t)]
    needed = {c for pair in (*FB_STRATA.values(), *FNB_STRATA.values()) for c in pair}
    useful = [v for v, _t in named if v in needed]
    _check(not useful,
           f"chercher « foncier » ramène {len(named)} variables et AUCUNE des "
           f"{len(needed)} colonnes dont un modèle TF a besoin "
           f"(trouvées : {useful or 'aucune'}) — elles sont titrées FB/FNB", failures)
    fb_titled = sum(1 for _v, t in titles if t.strip().upper().startswith("FB"))
    _check(fb_titled > 100, f"{fb_titled} variables titrées « FB »", failures)

    print("\n=== 4. identité par commune : base x taux = produit ===")
    num = lambda c: (pl.col(c).str.replace_all(",", ".")  # noqa: E731
                     .cast(pl.Float64, strict=False).fill_null(0.0))
    check = frame.select(
        base=num("E11"), taux=num("E12"),
    ).with_columns(produit=(pl.col("base") * pl.col("taux") / 100.0))
    live = check.filter(pl.col("base") > 0)
    _check(live.height > 30_000,
           f"{live.height:,} communes portent une base FB non nulle".replace(",", " "),
           failures)
    _check(bool((live["produit"] >= 0).all()),
           "aucun produit négatif", failures)

    print("\n=== 5. reconstruction nationale, bâti ===")
    total = sum(frame.select((num(b) * num(t) / 100.0).sum()).item()
                for b, t in FB_STRATA.values() if b in frame.columns)
    residual = total / PUBLISHED_FB_EUR - 1
    print(f"         reconstruit {total / 1e9:.3f} md€ · publié "
          f"{PUBLISHED_FB_EUR / 1e9:.1f} md€ · écart {residual:+.2%}")
    _check(abs(residual) <= FB_TOLERANCE,
           f"écart {residual:+.2%} dans la tolérance déclarée de {FB_TOLERANCE:.0%}",
           failures)
    wrong = abs(total / PUBLISHED_FB_WITH_ANNEXES_EUR - 1)
    _check(wrong > 0.10,
           f"et LOIN du titre de la publication ({PUBLISHED_FB_WITH_ANNEXES_EUR / 1e9:.1f} "
           f"md€, écart {total / PUBLISHED_FB_WITH_ANNEXES_EUR - 1:+.0%}) — c'est le "
           f"mauvais comparateur et le confondre condamnerait une lecture juste",
           failures)

    print("\n=== 6. non bâti : trou connu, épinglé comme tel ===")
    fnb = sum(frame.select((num(b) * num(t) / 100.0).sum()).item()
              for b, t in FNB_STRATA.values() if b in frame.columns)
    shortfall = fnb / PUBLISHED_FNB_EUR - 1
    print(f"         reconstruit {fnb / 1e9:.3f} md€ · publié "
          f"{PUBLISHED_FNB_EUR / 1e9:.1f} md€ · écart {shortfall:+.1%}")
    _check(abs(shortfall - FNB_MEASURED_SHORTFALL) < 0.05,
           f"le manque reste celui mesuré au gate ({FNB_MEASURED_SHORTFALL:+.1%}). "
           f"S'il change, c'est une lecture nouvelle — corriger ce script ET écrire "
           f"l'entrée D qui l'enregistre", failures)

    print()
    if failures:
        print(f"{len(failures)} assertion(s) en échec :", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print("REI vérifié : toutes les assertions du gate tiennent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
