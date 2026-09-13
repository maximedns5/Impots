#!/usr/bin/env python
"""Phase 8 §3.2 — the AFT per-line parse, as assertions that stay.

The addendum ruled it: the parse (ISIN, coupon, échéance, encours) lives HERE, in a verify
script with kill tests, never inline in the engine — the `verify_rei.py` shape. A parse of a
published document is a reading, and a reading that nothing re-checks rots silently when the
vintage moves.

WHAT IT ASSERTS, AND WHAT EACH ONE COST TO LEARN:

1. **The bulletin's per-line table reconstructs the bulletin's own published totals.** This
   is Block 1's kill test from §3.2, and it is the only one that tests anything: Block 1 +
   Block 2 = APU total holds BY CONSTRUCTION of Block 2 as a residual, so the real test is
   Block 1 alone against the AFT's own CT+MLT figures. Measured: total −0,003 %.

2. **The thousands separator is the NARROW NO-BREAK SPACE (U+202F), sometimes followed by
   an ordinary space — and an ordinary space alone is a COLUMN BOUNDARY, not a separator.**
   Three conventions appear in one document. Treating a plain space as a separator fuses
   the encours with the démembré column that follows it: FR0000571218 read as
   44 514 880 458 968 967 100 instead of 44 514 880 458, which is 4 × 10¹⁰ times its true
   value and still parses as an integer. The first version of this parse did exactly that.

3. **The date is stripped before any number is read.** «24 septembre 2026 24 030 000 000»
   otherwise lets the year join the encours.

4. **The HTML page « Encours détaillé des OAT » carries NOMINAL OAT ONLY** — 59 lines, no
   OATi, no OAT€i. The indexed lines are ~313 md€, near 11 % of the negotiable stock, and a
   Block 1 built from the HTML alone would silently omit them. The bulletin is therefore the
   complete per-line source and the HTML pages are a cross-check, not the input. Asserted so
   that a future vintage adding indexed lines to the page is noticed rather than absorbed.

Usage: `.venv/bin/python scripts/verify_aft.py`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BULLETIN = ROOT / "data" / "raw" / "aft_bulletin_mensuel_435_aout_2026.pdf"
OAT_PAGE = ROOT / "data" / "raw" / "aft_encours_detaille_oat_2026-09-13.html"
BTF_PAGE = ROOT / "data" / "raw" / "aft_encours_detaille_btf_2026-09-13.html"

MOIS = ("janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre"
        "|décembre")
DATE = re.compile(rf"\b\d{{1,2}}\s+(?:{MOIS})\s+\d{{4}}\b")

#: The separator REQUIRES a narrow (or non-breaking) space. A plain space may follow it, but
#: a plain space ALONE separates columns. See point 2 of the module docstring: confusing the
#: two produced an encours 4e10 times too large that still parsed as a valid integer.
NUMBER = re.compile("\\d{1,3}(?:[\u202f\u00a0] ?\\d{3})+")

#: Published by the bulletin itself, at 31 July 2026, in md€. The comparator for point 1.
PUBLISHED_MLT = 2662.0
PUBLISHED_CT = 220.0
PUBLISHED_TOTAL = 2882.0
PUBLISHED_INDEXED = 313.0

#: Measured at this implementation, recorded rather than chosen. The CT line is the loosest
#: at 0,163 %, which is rounding on figures the bulletin prints to the unit md€.
TOLERANCE = 0.005


def _check(condition: bool, message: str, failures: list[str]) -> None:
    print(("  OK    " if condition else "  ÉCHEC ") + message)
    if not condition:
        failures.append(message)


def bulletin_lines() -> list[tuple[str, str, int]]:
    """(ISIN, type, encours) per security, from the bulletin's own per-line tables."""
    import pypdf

    reader = pypdf.PdfReader(BULLETIN)
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    rows: list[tuple[str, str, int]] = []
    for match in re.finditer(
            r"^(FR[0-9A-Z]{10})\s+(OAT€i|OATi|OAT|BTF)\s+(.+)$", text, re.M):
        rest = match.group(3)
        found = DATE.search(rest)
        # The date goes FIRST, or its year joins the encours behind it.
        tail = rest[found.end():] if found else rest
        numbers = [int(re.sub(r"[^\d]", "", n)) for n in NUMBER.findall(tail)]
        encours = [n for n in numbers if n >= 1_000_000]
        if encours:
            rows.append((match.group(1), match.group(2), encours[0]))
    return rows


def html_isins(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return re.findall(r"\bFR[0-9A-Z]{10}\b", text)


def main() -> int:
    for path in (BULLETIN, OAT_PAGE, BTF_PAGE):
        if not path.exists():
            print(f"{path} absent — voir data/raw/MANIFEST.json", file=sys.stderr)
            return 1

    failures: list[str] = []
    rows = bulletin_lines()

    print("=== 1. le parc, ligne à ligne ===")
    _check(len(rows) == 103,
           f"{len(rows)} titres extraits du bulletin (attendu 103)", failures)
    _check(all(e > 0 for _i, _k, e in rows),
           "aucun encours nul ou manquant — une ligne sans encours se sommerait à zéro "
           "sans erreur", failures)

    print("\n=== 2. Bloc 1 reproduit les totaux publiés par l'AFT (§3.2) ===")
    mlt = sum(e for _i, k, e in rows if k != "BTF") / 1e9
    ct = sum(e for _i, k, e in rows if k == "BTF") / 1e9
    indexed = sum(e for _i, k, e in rows if k in ("OATi", "OAT€i")) / 1e9
    for label, got, want in (("MLT", mlt, PUBLISHED_MLT), ("court terme", ct, PUBLISHED_CT),
                             ("total négociable", mlt + ct, PUBLISHED_TOTAL),
                             ("dont indexés", indexed, PUBLISHED_INDEXED)):
        residual = got / want - 1
        _check(abs(residual) <= TOLERANCE,
               f"{label:18} {got:8.1f} md€ contre {want:7.1f} publié "
               f"({residual:+.3%}, tolérance {TOLERANCE:.1%})", failures)

    print("\n=== 3. la page HTML des OAT ne porte QUE du nominal ===")
    page = OAT_PAGE.read_text(encoding="utf-8", errors="replace")
    # The LIBELLÉ cells, not the whole document: "OATi" also appears in the site
    # navigation, and asserting on the page would test the menu rather than the data —
    # the mistake verify_rei.py made in its first version, on CFE rows.
    libelles = [" ".join(re.sub(r"<[^>]+>", " ", cell).split())
                for cell in re.findall(r'views-field-title">(.*?)</td>', page, re.S)]
    indexed_rows = [x for x in libelles if x.startswith(("OATi", "OAT€i"))]
    _check(not indexed_rows,
           f"aucune des {len(libelles)} lignes de la page OAT n'est indexée — les "
           f"~313 md€ d'OATi/OAT€i n'y sont pas, donc un Bloc 1 bâti sur cette page "
           f"seule les omettrait en silence ; le bulletin est la source complète "
           f"(trouvées : {indexed_rows[:3]})", failures)
    _check(len(set(html_isins(OAT_PAGE))) == 59,
           f"{len(set(html_isins(OAT_PAGE)))} ISIN distincts sur la page OAT (attendu 59)",
           failures)
    _check(len(set(html_isins(BTF_PAGE))) == 30,
           f"{len(set(html_isins(BTF_PAGE)))} ISIN distincts sur la page BTF (attendu 30)",
           failures)

    print("\n=== 4. le séparateur de milliers, épinglé ===")
    # If the parse ever admits a plain space as a separator again, this line reads
    # 44 514 880 458 968 967 100 — an integer, silently, 4e10 times too large.
    fused = [(i, e) for i, _k, e in rows if e > 200_000_000_000]
    _check(not fused,
           f"aucun encours au-dessus de 200 md€ — une espace ordinaire prise pour un "
           f"séparateur fusionnerait l'encours et le démembré (trouvés : {fused})",
           failures)

    print()
    if failures:
        print(f"{len(failures)} assertion(s) en échec :", file=sys.stderr)
        for line in failures:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print("AFT vérifié : le parc par ligne reproduit les totaux publiés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
