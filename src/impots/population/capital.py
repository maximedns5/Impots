"""Imputing the capital income the PFU taxes onto the synthetic population (F1b, D-248).

**This is a CALIBRATION and it spends its source.** DGFiP Statistiques n° 41 publishes,
in its Tableau 2, the mean « impôt hors barème » per foyer by decile of RFR per part, and
down to the last centième and the last millième. The gate (`docs/F1B_CAPITAL_GATE.md`,
D-097) found that the base is derivable from it: the PFU takes 12,8 % for the income tax,
so the base of a cell is its mean tax over that rate. This module reads the table, turns
the nested top rows into disjoint bands, and hands every foyer of a band its base. The
PFU the population then pays matches n° 41 by construction and can never afterwards be
cited as evidence of anything — `margins.CAPITAL_PFU_BY_FRACTILE` carries
`use="calibration"` for that reason.

WHAT IT BUYS. A proportional tax's yield depends on the base of each cell, never on its
dispersion, so the PFU and the social levies on capital income are priced right at
twelve steps, and the income tax the population reports gains its hors-barème part.

FIVE ARTEFACTS, DECLARED, BECAUSE NONE IS VISIBLE IN THE OUTPUT.

1. **Every foyer of a band gets the same base**, holders and non-holders alike. The table
   gives a mean over all foyers and no count of holders, so the share of foyers with any
   capital income is 100 % by construction. The ERFS measures that share (axis A4 of the
   validation table) and stays a comparator: building on it would spend it (gate, § 8).
2. **The composition is national in every band.** The base is split over dividends (2DC),
   interest (2TR), other distributed income (2TS) and capital gains (3VG) in the shares of
   the national 2042 boxes. The real top is dividend- and gain-heavy, the bottom
   interest-heavy. The PFU and the social levies do not see the split; a response of
   dividends will.
3. **The bands are ranked on the RFR per part before the imputation**, which then moves
   it. DGFiP ranks on an RFR that already holds the capital income. One pass, the ranking
   not recomputed, as for the top-tail rake.
4. **The rest of the hors-barème tax is read as PFU.** The column also holds the life
   insurance levied at 7,5 % and a few other proportional taxes. Divided by 12,8 % the
   whole column gives 80,63 bn; the four national boxes sum to 80,70 bn. The two routes
   agree within 0,1 %, which is what makes the derivation usable rather than plausible.
5. **The count of foyers.** The population holds 35,3 M foyers for 31,0 M ménages; France
   41,6 M for 31,3 M (the reconciliation's « Foyers fiscaux » line, −15 %). The missing
   foyers are not missing people but units the population does not split — a couple
   living together unmarried, a grown child filing alone. A band's mean per DGFiP foyer
   is therefore multiplied by France's foyers per ménage over the population's, ×1,17,
   so that the capital per ménage is France's and the total comes back, as the wage bill
   and the pensions are calibrated on their totals. Without it the PFU lands 15 % short
   (8,79 bn instead of 10,32 on the full population). The ratio is free of scale, so a
   frame that weighs to a share of France gets the same factor.

The CEHR is printed in the same cell, in parentheses: « 2 290 (+ 476) ». It is stripped
before any use. Counted, it would overstate the base by 19 % nationally and by a third in
the last millième (gate, § 2).

The tables are those of the 2024 income. Another year would need the base aged, which is
not done here: it is refused by name.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from impots.donnees import RAW
from impots.population import margins, top_tail

#: DGFiP n° 41, the same workbook the top-tail rake reads.
WORKBOOK = top_tail.WORKBOOK
#: The national 2042 boxes, already in the manifest for D-210.
DECLARATIONS_FILE = "dgfip_ir_2042_nat_export_2026-10-15.csv"
YEAR = 2024
#: The déclaration cases the base is written to, by the national box that weighs each.
CASES: dict[str, str] = {"f2dc": "2DC", "f2tr": "2TR", "f2ts": "2TS", "f3vg": "3VG"}
#: The rate the base is derived with, read from the law rather than typed.
PFU_RATE = ("taxation_capital.prelevement_forfaitaire.partir_2018."
            "taux_prelevement_forfaitaire_rev_capital_eligibles_pfu_interets_dividendes_etc")
#: Tableau 2's rows, and the column « Impôt hors barème (+ CEHR) — Moyenne (en €) ».
FIRST_ROW, LAST_ROW, LABEL_COLUMN, TAX_COLUMN = 5, 16, 2, 10
TOTAL_ROW = 19
#: The nested rows' published amounts in bn, which the means must give back.
AMOUNT_ROWS = {"dernier dixième": 22, "dont dernier centième": 23,
               "dont dernier millième": 24}
NESTED = ("dernier dixième", "dont dernier centième", "dont dernier millième")
#: The means are rounded to the euro and the amounts to ten million: they agree within this.
CROSS_CHECK = 0.01
#: The foyer-count factor of artefact 5. Measured ×1,17; outside this band the population's
#: tax units are not France's at all, and the run stops rather than rescale them.
FACTOR_BOUNDS = (0.8, 1.5)


class CapitalImputationError(RuntimeError):
    """The published tables cannot be read as expected, or the imputation was asked for
    where it cannot stand."""


@dataclass(frozen=True)
class Published:
    tax: dict[str, float]
    """Mean hors-barème tax per foyer, CEHR stripped, by disjoint band of `top_tail.BANDS`."""
    total_eur: float
    """The column's national total, CEHR stripped."""
    cehr_eur: float
    foyers: float = 0.0
    """The foyers the means stand for: the total over the mean per foyer (≈ 41,58 M)."""


def _label(text: object) -> str:
    return " ".join(str(text or "").split())


def _euros(text: str) -> float:
    return float(re.sub(r"[\s\u00a0\u202f]", "", text).replace(",", "."))


def _split(cell: object) -> tuple[float, float]:
    """« 2 290  (+ 476) » → (2 290, 476): the tax, then the CEHR printed beside it."""
    if isinstance(cell, (int, float)):
        return float(cell), 0.0
    found = re.fullmatch(r"\s*([\d\s\u00a0\u202f,.]+?)\s*\(\+\s*([\d\s\u00a0\u202f,.]+)\)\s*",
                         str(cell or ""))
    if found is None:
        raise CapitalImputationError(
            f"cellule « {cell} » illisible : n° 41 imprime l'impôt hors barème puis la "
            f"CEHR entre parenthèses, et l'un sans l'autre n'est pas l'assiette du PFU")
    return _euros(found.group(1)), _euros(found.group(2))


def published(workbook: Path | None = None) -> Published:
    """Tableau 2's hors-barème column, CEHR stripped, as disjoint bands."""
    import openpyxl

    path = Path(workbook or WORKBOOK)
    if not path.exists():
        raise CapitalImputationError(
            f"{path} introuvable — `impots data fetch {path.name}` le télécharge depuis "
            f"son entrée de manifeste")
    sheet = openpyxl.load_workbook(path, read_only=True, data_only=True)["Tableau 2"]
    rows = {r: row for r, row in enumerate(sheet.iter_rows(
        min_row=1, max_row=max(AMOUNT_ROWS.values()), values_only=True), 1)}
    by_label = {_label(rows[r][LABEL_COLUMN - 1]): _split(rows[r][TAX_COLUMN - 1])
                for r in range(FIRST_ROW, LAST_ROW + 1)}
    deciles = [label for label, *_ in top_tail.BANDS[:9]]
    missing = [label for label in (*deciles, *NESTED) if label not in by_label]
    if missing:
        raise CapitalImputationError(
            f"n° 41, tableau 2 : {missing} introuvables — le millésime a changé de forme")
    tax = {label: by_label[label][0] for label in deciles}
    decile, centieme, millieme = (by_label[label][0] for label in NESTED)
    # The nested-to-disjoint step, as `top_tail.published_targets` writes it.
    tax["99,9–100 %"] = millieme
    tax["99–99,9 %"] = (centieme * 0.010 - millieme * 0.001) / 0.009
    tax["90–99 %"] = (decile * 0.100 - centieme * 0.010) / 0.090
    if min(tax.values()) < 0:
        raise CapitalImputationError(f"bande négative après le passage aux bandes "
                                     f"disjointes : {tax} — les lignes emboîtées sont mal lues")
    total, cehr = (value * 1e9 for value in _split(rows[TOTAL_ROW][TAX_COLUMN - 1]))
    # GUARD on the reading: the nested rows' means, times their foyers, give back the
    # amounts printed below them. The foyers are the total's, read from the means.
    foyers = total / sum(tax[label] * (high - low) for label, low, high in top_tail.BANDS)
    for label, share in zip(NESTED, (0.1, 0.01, 0.001), strict=True):
        printed = _split(rows[AMOUNT_ROWS[label]][TAX_COLUMN - 1])[0] * 1e9
        computed = by_label[label][0] * share * foyers
        if abs(computed / printed - 1.0) > CROSS_CHECK:
            raise CapitalImputationError(
                f"« {label} » : {computed / 1e9:.2f} md des moyennes contre "
                f"{printed / 1e9:.2f} md imprimés — le tableau ne se recoupe pas")
    return Published(tax=tax, total_eur=total, cehr_eur=cehr, foyers=foyers)


def composition(raw: Path | None = None, year: int = YEAR) -> dict[str, float]:
    """Each case's share of the base, from the national 2042 boxes of `year`."""
    path = (raw or RAW) / DECLARATIONS_FILE
    if not path.exists():
        raise CapitalImputationError(f"{path} introuvable — `impots data fetch "
                                     f"{DECLARATIONS_FILE}` le télécharge")
    amounts: dict[str, float] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            if row["Année"] == str(year) and row["Nom"] in CASES.values():
                amounts[row["Nom"]] = float(row["Montant"])
    missing = sorted(set(CASES.values()) - set(amounts))
    if missing:
        raise CapitalImputationError(f"{DECLARATIONS_FILE} : cases {missing} absentes "
                                     f"pour {year}")
    total = sum(amounts.values())
    return {case: amounts[box] / total for case, box in CASES.items()}


def national_boxes_eur(raw: Path | None = None, year: int = YEAR) -> float:
    """The four boxes' national total: the second route to the base (artefact 4)."""
    path = (raw or RAW) / DECLARATIONS_FILE
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sum(float(row["Montant"]) for row in csv.DictReader(handle, delimiter=";")
                   if row["Année"] == str(year) and row["Nom"] in CASES.values())


def pfu_rate(year: int = YEAR) -> float:
    from impots.engine.system import baseline

    node = baseline().parameters(f"{year}-01-01")
    for part in PFU_RATE.split("."):
        node = getattr(node, part)
    return float(node)


def bases(table: Published, rate: float) -> dict[str, float]:
    """The base per foyer of each band: its mean tax over the PFU's income-tax rate."""
    if not 0.0 < rate < 1.0:
        raise CapitalImputationError(f"taux du PFU {rate} : la base ne se dérive pas")
    return {label: tax / rate for label, tax in table.tax.items()}


def foyer_factor(table: Published, foyers: float, menages: float) -> float:
    """France's foyers per ménage over the population's (artefact 5)."""
    if foyers <= 0 or menages <= 0:
        raise CapitalImputationError(f"{foyers} foyers et {menages} ménages pondérés : "
                                     f"aucun rapport ne se calcule")
    factor = (table.foyers / margins.HOUSEHOLDS.value) / (foyers / menages)
    low, high = FACTOR_BOUNDS
    if not low <= factor <= high:
        raise CapitalImputationError(
            f"facteur de foyers {factor:.2f} hors de [{low}, {high}] : la population ne "
            f"découpe pas ses ménages en foyers comme la France, et la recaler ainsi "
            f"inventerait du capital plutôt que de le répartir")
    return factor


def bands(rfr_per_part: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Each foyer's band index in `top_tail.BANDS`, by weighted rank of RFR per part."""
    order = np.argsort(rfr_per_part, kind="stable")
    cumulative = np.cumsum(weights[order])
    total = cumulative[-1]
    out = np.full(rfr_per_part.shape, -1, dtype=np.int64)
    for index, (_, low, high) in enumerate(top_tail.BANDS):
        mask = (cumulative > low * total) & (cumulative <= high * total)
        out[order[mask]] = index
    return out


def impute(rfr_per_part: np.ndarray, weights: np.ndarray, *, menages: float,
           year: int = YEAR, raw: Path | None = None,
           workbook: Path | None = None) -> dict[str, np.ndarray]:
    """The capital-income cases per foyer, in euros, aligned with `rfr_per_part`.

    No draw: every foyer of a band gets the band's base (artefact 1), times the
    foyer-count factor (artefact 5), split in the national shares (artefact 2).
    `menages` is the population's weighted count of ménages, which the factor needs and
    which has no default: a guessed count would be a guessed factor."""
    if year != YEAR:
        raise CapitalImputationError(
            f"imputation des revenus du capital pour {year} : n° 41 décrit les revenus "
            f"{YEAR}, et une autre année demanderait de vieillir l'assiette, ce que cette "
            f"imputation ne fait pas")
    if rfr_per_part.shape != weights.shape:
        raise CapitalImputationError(
            f"rfr_per_part {rfr_per_part.shape} et weights {weights.shape} diffèrent")
    table = published(workbook)
    per_band = bases(table, pfu_rate(year))
    factor = foyer_factor(table, float(weights.sum()), menages)
    base = np.array([per_band[label] * factor for label, *_ in top_tail.BANDS])
    index = bands(rfr_per_part, weights)
    if (index < 0).any():
        raise CapitalImputationError(f"{int((index < 0).sum())} foyers hors de toute bande")
    per_foyer = base[index]
    return {case: per_foyer * share for case, share in composition(raw, year).items()}


def imputed_total(cases: dict[str, np.ndarray], weights: np.ndarray) -> float:
    """What the imputation handed out, in euros of base: a check that it worked, not
    evidence that anything is true."""
    return float(sum((values * weights).sum() for values in cases.values()))
