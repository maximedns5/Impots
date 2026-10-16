#!/usr/bin/env python
"""What Mésange's « Solde primaire des APU » row says, read before it is used (D-214).

PHASE9_SPEC §4.1 makes this row the recommended source of the GDP → receipts loop, on
one condition: that M0 first read the document for its sign, its scale and what public
spending does while a variant runs. This script replays that reading.

WHAT IT CHECKS:

1. **The row includes the shock.** For a fiscal variant, the shock costs one point of
   GDP ex ante, net (VAT: 1,18 gross for one net, p113). In the expansionary convention
   `mesange.load` brings every variant to, the balance must therefore lie between −1
   and 0 in the first year: worse than nothing, better than the ex ante cost. A row read
   with the wrong sign, or one that excluded the shock, falls outside. The loop the spec
   wants is the difference, `solde + 1`.
2. **What it is a difference of.** The feedback against the GDP effect, per variant and
   horizon. If the feedback ran only through GDP the ratio would be about constant; it
   is not (employer contributions return more than their GDP effect in year 1), so
   §4.1's proportionality is an approximation, and this prints how far.
3. **What spending does during the run.** Footnote 70 of §3.7.2 (folio 93): in volume,
   only receipts and unemployment benefits react, everything else reacts in prices.
   The quote is checked in the text, because §3.2's scenario choice rests on it.
4. **What the tables do not carry.** The targeted variant has no balance row. No variant
   prints a GDP deflator: the price rows are consumption, production, value added,
   intermediate consumption, exports and imports.

Usage: `.venv/bin/python scripts/verify_mesange_solde.py [raw_dir]` (seconds; needs the
manifested `insee_G2017-04_mesange.pdf`).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FOOTNOTE_70 = ("seules les recettes et les prestations chômage réagissent, "
               "conformément aux stabilisateurs automatiques usuels")
PRICE_ROWS = ("Prix de la consommation des ménages", "Prix de VA marchande")
NO_DEFLATOR = ("Prix du PIB", "Déflateur du PIB")

#: Pinned at D-214: the feedback `solde + 1`, in points of GDP, at 1, 2 and 3 years.
PINS = {
    "impot_sur_le_revenu": (0.19, 0.50, 0.58),
    "csg": (0.19, 0.50, 0.57),
    "cotisations_salaries": (0.27, 0.53, 0.61),
    "cotisations_employeurs": (0.28, 0.58, 0.73),
    "tva": (0.20, 0.64, 0.72),
    "taxe_carbone": (0.32, 0.85, 0.86),
}
HORIZONS = ("1", "2", "3")


def main() -> int:
    from impots.macro import mesange

    raw = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    variants = mesange.load(raw=raw)
    failures: list[str] = []

    print("rétroaction = solde primaire + 1 (pts de PIB), et rapport à l'effet sur le PIB")
    for key, variant in variants.items():
        if variant.spec.targeted:
            if "solde_primaire_pts_pib" in variant.rows:
                failures.append(f"{key} : la variante ciblée porte une ligne de solde")
            print(f"  {key:32s} pas de ligne de solde (variante ciblée)")
            continue
        if variant.spec.basis != "ex_ante_fiscal":
            print(f"  {key:32s} choc en volume, hors du tableau")
            continue
        solde = [variant.at("solde_primaire_pts_pib", h) for h in HORIZONS]
        gdp = [variant.at("gdp", h) for h in HORIZONS]
        if not -1.0 < solde[0] < 0.0:
            failures.append(f"{key} : solde à 1 an {solde[0]} hors de ]−1 ; 0[")
        feedback = tuple(round(s + 1.0, 2) for s in solde)
        ratio = " ".join(f"{f / g:5.2f}" for f, g in zip(feedback, gdp, strict=True))
        print(f"  {key:32s} {feedback}  rapport au PIB {ratio}")
        if key in PINS and feedback != PINS[key]:
            failures.append(f"{key} : {feedback} contre {PINS[key]} épinglé")
    missing = set(PINS) - set(variants)
    if missing:
        failures.append(f"variantes épinglées absentes : {sorted(missing)}")

    # pypdf cuts some words inside («recette s»), so the quote is compared with every
    # space removed; the tables are checked on their own pages, because the model's
    # description elsewhere in the document does mention the GDP deflator.
    path = str((raw or mesange.RAW) / "insee_G2017-04_mesange.pdf")
    pages = dict(mesange._pages(path))
    squeezed = "".join("".join(lines) for lines in pages.values()).replace(" ", "")
    found = FOOTNOTE_70.replace(" ", "") in squeezed
    if not found:
        failures.append("la note 70 sur les dépenses en variante est introuvable")
    for key, variant in variants.items():
        table = " ".join(pages[variant.page])
        for label in NO_DEFLATOR:
            if label in table:
                failures.append(f"{key} : « {label} » est imprimé p. {variant.page}, la "
                                f"conclusion « pas de déflateur » est à relire")
        if not variant.spec.targeted:
            for label in PRICE_ROWS:
                if label not in table:
                    failures.append(f"{key} : ligne « {label} » absente p. {variant.page}")
    print("note 70 :", "trouvée" if found else "ABSENTE")

    for failure in failures:
        print(f"ÉCHEC  {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
