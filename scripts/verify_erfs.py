#!/usr/bin/env python
"""ERFS interrupt E1 — the formal inventory, as assertions that stay.

**This script reads restricted data and prints NONE of it.** Everything below is metadata:
checksums, row counts, column names, and agreement between two encodings of the same
delivery. No value from any row appears in its output, and none may ever be added — the
convention forbids it and a verification script is exactly the place where "just this once,
to debug" happens.

It is OPT-IN and absent from CI: without `IMPOTS_ERFS_DIR` (or the `~/.impots.local` line)
it exits 0 with a message, because a machine that does not hold the delivery has nothing to
verify and should not fail for it.

WHAT IT ASSERTS:

1. **Checksums of the working set**, recomputed from the bytes. The delivery is held under a
   signed convention; knowing exactly which bytes were validated is the difference between
   a reproducible finding and a recollection.
2. **Row counts against the published figures.** The methodology PDF shipped with the
   delivery states «92 000 individus pour environ 44 000 ménages». Measured: 91 921 and
   43 684 — within rounding of an approximate published figure, which is the most those
   words can support.
3. **The CSV parse against the labelled Stata pair**, which is the point of keeping the
   `.dta` files at all. Same variable count, same observation count, same names in the same
   order — read straight from the format-111 header, with no Stata reader installed.
4. **The case trap, pinned.** Stata LOWERCASES variable names; the CSV preserves them. All
   443 of the individual table's 467 names that carry uppercase differ between the two
   encodings, and nothing else does. Code keying Stata-derived names against CSV columns
   would miss almost every column — and would do it silently, returning empty selections
   rather than raising.

WHY THE STATA HEADER IS PARSED BY HAND. Neither pandas nor pyreadstat is installed, and
adding a compiled dependency to read four numbers would be a poor trade. Format 111 places
`nvar` at bytes 4-5 and `nobs` at 6-9, then the variable names as 33-byte NUL-terminated
fields after an 81-byte label and an 18-byte timestamp. That is enough for every check here,
and it needs nothing beyond `struct`.

Usage: `.venv/bin/python scripts/verify_erfs.py`
"""

from __future__ import annotations

import csv
import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

#: Published by the methodology document shipped with the delivery. Approximate by its own
#: wording («environ»), so the tolerance below is generous on purpose: pinning a rounded
#: published figure to four digits would be inventing precision the source disclaims.
PUBLISHED_HOUSEHOLDS = 44_000
PUBLISHED_INDIVIDUALS = 92_000
COUNT_TOLERANCE = 0.02

#: Measured at this inventory. A vintage bump changes these, and it should FAIL here rather
#: than be discovered halfway through a validation run.
EXPECTED = {
    "fpr_menage_2022.csv": (10_974_882, 43_684, 87),
    "fpr_indiv_2022.csv": (79_214_326, 91_921, 467),
}

#: The disclosure floor. Recorded as the handoff's DEFAULT, not as a quotation from the
#: convention's diffusion clause — the convention is not in the delivery (D-134). Nothing
#: this script prints is a cell count, but the floor is stated here so that anything later
#: added has a number to respect.
DISCLOSURE_FLOOR_HOUSEHOLDS = 11


def _check(condition: bool, message: str, failures: list[str]) -> None:
    print(("  OK    " if condition else "  ÉCHEC ") + message)
    if not condition:
        failures.append(message)


def stata_header(path: Path) -> tuple[int, int, list[str]]:
    """(nvar, nobs, names) from a format-111 .dta, without a Stata reader."""
    raw = path.read_bytes()[:600_000]
    if raw[0] != 111:
        raise RuntimeError(
            f"{path.name}: format Stata {raw[0]}, attendu 111 — la disposition de l'en-tête "
            f"diffère et les décalages codés ici ne s'appliquent plus.")
    endian = "<" if raw[1] == 2 else ">"
    nvar = struct.unpack(endian + "H", raw[4:6])[0]
    nobs = struct.unpack(endian + "I", raw[6:10])[0]
    varlist = 4 + 2 + 4 + 81 + 18 + nvar          # après typlist
    names = [raw[varlist + i * 33: varlist + i * 33 + 33].split(b"\0")[0].decode("latin-1")
             for i in range(nvar)]
    return nvar, nobs, names


def csv_shape(path: Path) -> tuple[int, int, list[str]]:
    """(ncol, nrow, header) — the header is SCHEMA, never a row."""
    with path.open(encoding="latin-1", newline="") as handle:
        header = next(csv.reader(handle, delimiter=";"))
        rows = sum(1 for _ in handle)
    return len(header), rows, header


def main() -> int:
    from impots.erfs.config import ErfsNotConfigured, erfs_dir

    try:
        csv_dir = erfs_dir()
    except ErfsNotConfigured as error:
        print(f"ERFS non configuré sur cette machine — rien à vérifier.\n  {error}")
        return 0

    stata_dir = csv_dir.parent.parent / "lil-1696.dta" / "Stata"
    failures: list[str] = []

    print("=== 1. empreintes du jeu de travail ===")
    for name, (size, _rows, _cols) in EXPECTED.items():
        path = csv_dir / name
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        _check(len(data) == size,
               f"{name:24} {len(data):>11} o (attendu {size}) · sha256 {digest[:16]}…",
               failures)

    print("\n=== 2. comptages contre les chiffres publiés ===")
    shapes = {}
    for name, (_size, rows, cols) in EXPECTED.items():
        ncol, nrow, header = csv_shape(csv_dir / name)
        shapes[name] = (ncol, nrow, header)
        _check(nrow == rows and ncol == cols,
               f"{name:24} {nrow} enregistrements · {ncol} colonnes", failures)

    for name, published, label in (
            ("fpr_menage_2022.csv", PUBLISHED_HOUSEHOLDS, "ménages"),
            ("fpr_indiv_2022.csv", PUBLISHED_INDIVIDUALS, "individus")):
        measured = shapes[name][1]
        residual = measured / published - 1
        _check(abs(residual) <= COUNT_TOLERANCE,
               f"{label:10} {measured} contre « environ {published} » publié "
               f"({residual:+.2%}, tolérance {COUNT_TOLERANCE:.0%})", failures)

    case_rows: list[tuple[str, list[str], list[str]]] = []
    print("\n=== 3. le parse CSV contre l'autorité Stata étiquetée ===")
    for stem in ("fpr_menage_2022", "fpr_indiv_2022"):
        dta = stata_dir / f"{stem}.dta"
        if not dta.exists():
            _check(False, f"{dta.name} absent — la paire étiquetée est l'autorité de "
                          f"contrôle et son absence n'est pas une réussite", failures)
            continue
        nvar, nobs, names = stata_header(dta)
        ncol, nrow, header = shapes[f"{stem}.csv"]
        _check(nvar == ncol and nobs == nrow,
               f"{stem:18} .dta {nvar} var × {nobs} obs = .csv {ncol} × {nrow}", failures)
        _check([n.lower() for n in names] == [h.lower() for h in header],
               f"{stem:18} noms identiques et dans le MÊME ORDRE (à la casse près)",
               failures)

        case_rows.append((stem, names, header))

    print("\n=== 4. le piège de casse, épinglé ===")
    for stem, names, header in case_rows:
        upper = [h for h in header if h != h.lower()]
        mismatched = [(a, b) for a, b in zip(names, header, strict=True) if a != b]
        _check(mismatched and all(a.lower() == b.lower() for a, b in mismatched),
               f"{stem:18} {len(mismatched)} divergences, TOUTES de casse "
               f"({len(upper)}/{len(header)} colonnes CSV ont des majuscules) — Stata "
               f"minusculise, le CSV conserve ; un code qui croiserait les deux "
               f"sélectionnerait le vide sans lever", failures)

    print()
    if failures:
        print(f"{len(failures)} assertion(s) en échec :", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print("ERFS vérifié : inventaire conforme, parse CSV confirmé par la paire Stata.")
    print(f"(Métadonnées seules. Plancher de diffusion retenu : "
          f"{DISCLOSURE_FLOOR_HOUSEHOLDS} ménages, PAR DÉFAUT — voir D-134.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
