"""Imputing réduction and crédit d'impôt bases onto the synthetic population (B3).

**This is a CALIBRATION act and it spends its source.** The DGFiP publishes, for each
dispositif, the number of foyers claiming it and the total amount, by decile of revenu
fiscal de référence per part. This module reads that table and hands out bases until the
population reproduces it. The national niche total therefore matches DGFiP *by
construction*, and can never afterwards be cited as evidence that anything is right —
`margins.NICHE_CREDITS_BY_DECILE` carries `use="calibration"` for that reason.

What it does buy is real: a niche reform stops costing exactly zero (D-066), the income
tax the population reports stops being a pure barème figure, and the distributional
incidence of a niche reform becomes computable at all.

**Three artefacts a reader must be told about**, because none of them is visible in the
output:

1. **Every claimant in a decile gets the same base.** DGFiP publishes a count and a
   total, so the mean is all there is; no within-decile dispersion is available. A
   reform's incidence therefore comes out as a step function across ten steps, and any
   feature finer than a decile is an artefact of that.
2. **Who claims is a seeded draw**, conditioned only on the decile. Real claiming
   correlates with things the population knows (children, age, home ownership) and this
   uses none of them, so the *identity* of claimants is arbitrary even where their
   number is right.
3. **Roughly 45 % of the niches are still missing.** The five families imputed here are
   about 10.7 bn of the 19.53 bn total.

THE UNIT TRAP, which is the reason `_amounts` asserts rather than trusts: the same
workbook is denominated in THOUSANDS of euros for the 2018-2021 vintages and in EUROS
from 2022. The 2018 sheet reads 4 860 210 where the 2023 sheet reads 6 019 895 605 —
both are about six billion. Reading one with the other's convention is a factor of a
thousand, silently, and it would land inside no test that does not check magnitude.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"

CREDITS_FILE = "dgfip_ir_credits_impot_par_decile_rfr_2024.xlsx"
REDUCTIONS_FILE = "dgfip_ir_reductions_par_decile_rfr.xlsx"

#: The published decile table's own header row and first data row.
HEADER_ROW = 3
FIRST_DECILE_ROW = 4
DECILES = 10

#: Any niche total must land in this band, in euros. It exists to turn the
#: thousands-versus-euros trap into a loud failure: a sheet read with the wrong
#: convention comes out a thousand times too small or too large, and both fall outside.
PLAUSIBLE_TOTAL_EUR = (5.0e7, 5.0e10)


@dataclass(frozen=True)
class Imputable:
    """One niche the population can be given bases for."""

    case: str
    """The déclaration case the base is written to."""
    workbook: str
    column: str
    """The published column header, matched exactly after whitespace normalisation.
    `DONS : PERSONNES EN DIFFICULTE` carries a NON-BREAKING SPACE before its colon in
    the file, which is why matching is on normalised text rather than equality."""
    rate: float
    """The statutory rate, used to turn a published CREDIT back into the BASE the
    déclaration carries. Measured, not tabulated — see `tests/test_niches.py`."""
    label: str


#: What can be imputed, and nothing else. Scolarité is deliberately absent: its
#: déclaration cases are COUNTS of children, and the published column aggregates
#: collège, lycée and supérieur into one amount, so the split cannot be recovered.
IMPUTABLE: tuple[Imputable, ...] = (
    Imputable("f7db", CREDITS_FILE, "CI EMPLOI SALARIE A DOMICILE", 0.50,
              "Emploi d'un salarié à domicile"),
    Imputable("f7ga", CREDITS_FILE, "CI FRAIS DE GARDE JEUNES ENFANTS", 0.50,
              "Frais de garde des jeunes enfants"),
    Imputable("f7ac", CREDITS_FILE, "CI COTISATIONS SYNDICALES", 0.66,
              "Cotisations syndicales"),
    Imputable("f7uf", REDUCTIONS_FILE, "DONS AUX OEUVRES", 0.66,
              "Dons aux œuvres"),
    Imputable("f7ud", REDUCTIONS_FILE, "DONS : PERSONNES EN DIFFICULTE", 0.75,
              "Dons aux personnes en difficulté"),
)

#: Published columns with no openfisca variable to receive them. Recorded rather than
#: dropped: `DONS AIDE AUX VICTIME DE MAYOTTE` is 21 M EUR over 167 467 foyers and has
#: nowhere to go, so the imputed donation total is short by that much on purpose.
UNMAPPABLE = {
    "DONS AIDE AUX VICTIME DE MAYOTTE": (
        "aucune variable openfisca — 21 M EUR restent hors du modèle"),
    "DONS SAUVEGARDE DU PATRIMOINE RELIGIEUX": (
        "la case f7uj existe mais son plafond de 1 000 EUR la rend mal représentée par "
        "un montant moyen de décile ; 44 M EUR laissés de côté"),
}


class NicheImputationError(RuntimeError):
    """The published decile table cannot be read as expected."""


@dataclass(frozen=True)
class Bracket:
    decile: int
    lower: float
    """Lower bound of RFR per part. -inf for the first decile."""
    upper: float
    """Upper bound. +inf for the tenth."""
    claimants: float
    amount_eur: float

    @property
    def mean_credit(self) -> float:
        return self.amount_eur / self.claimants if self.claimants else 0.0


def _sheet(workbook: str, year: int, kind: str, raw: Path | None = None):
    try:
        import openpyxl
    except ModuleNotFoundError as error:  # pragma: no cover - environment
        raise NicheImputationError("openpyxl is required") from error
    path = (raw or RAW) / workbook
    if not path.exists():
        raise NicheImputationError(f"{path} not found — download it and manifest it")
    book = openpyxl.load_workbook(path, data_only=True)
    name = f"{year} {kind}"
    if name not in book.sheetnames:
        raise NicheImputationError(
            f"{workbook} has no sheet {name!r}; has {book.sheetnames}")
    return book[name]


def _normalise(text: object) -> str:
    return " ".join(str(text or "").replace("\xa0", " ").split()).upper()


def _column(sheet, header: str) -> int:
    wanted = _normalise(header)
    for column in range(1, sheet.max_column + 1):
        if _normalise(sheet.cell(HEADER_ROW, column).value) == wanted:
            return column
    raise NicheImputationError(
        f"column {header!r} not found on {sheet.title!r}; the publication may have "
        f"been reorganised — do not fall back to a neighbouring column"
    )


def brackets(niche: Imputable, year: int = 2024, raw: Path | None = None) -> list[Bracket]:
    """The published decile table for one niche, in euros.

    Raises if the total falls outside `PLAUSIBLE_TOTAL_EUR`, which is how the
    thousands-versus-euros change of convention between vintages is caught rather than
    absorbed.
    """
    amounts = _sheet(niche.workbook, year, "montants", raw)
    counts = _sheet(niche.workbook, year, "nombres", raw)
    column = _column(amounts, niche.column)
    count_column = _column(counts, niche.column)

    # The published bounds are NOT exactly contiguous: decile 1 ends at 1 972 while
    # decile 2 begins at 1 972.1667, and there are nine such slivers. Banding on the
    # printed pairs would drop every foyer that falls in one — few, but silently, and
    # the count would then miss its published target for no visible reason. Each band
    # therefore runs from its own lower bound to the NEXT band's lower bound, so the
    # ten cover the line without gap or overlap.
    lowers: list[float] = []
    for index in range(DECILES):
        raw_lower = amounts.cell(FIRST_DECILE_ROW + index, 2).value
        lowers.append(
            float(raw_lower) if raw_lower not in (None, "") else float("-inf"))

    out: list[Bracket] = []
    for index in range(DECILES):
        row = FIRST_DECILE_ROW + index
        upper = lowers[index + 1] if index + 1 < DECILES else float("inf")
        out.append(Bracket(
            decile=index + 1,
            lower=lowers[index],
            upper=upper,
            claimants=float(counts.cell(row, count_column).value or 0.0),
            amount_eur=float(amounts.cell(row, column).value or 0.0),
        ))

    total = sum(bracket.amount_eur for bracket in out)
    low, high = PLAUSIBLE_TOTAL_EUR
    if not low <= total <= high:
        raise NicheImputationError(
            f"{niche.label} ({year}) totals {total:,.0f}, outside the plausible band "
            f"[{low:,.0f}, {high:,.0f}]. The workbook is denominated in THOUSANDS for "
            f"the 2018-2021 vintages and in EUROS from 2022; this looks like the wrong "
            f"convention rather than a surprising figure."
        )
    return out


def impute(
    rfr_per_part: np.ndarray,
    weights: np.ndarray,
    *,
    year: int = 2024,
    seed: int = 20260903,
    raw: Path | None = None,
) -> dict[str, np.ndarray]:
    """Niche bases per foyer, drawn so the population reproduces the published table.

    Returns one array per déclaration case, in euros, aligned with `rfr_per_part`.

    The draw is independent per foyer with probability `claimants / weighted foyers in
    the decile`, so the EXPECTED weighted number of claimants equals the published one
    exactly. It is seeded, and the seed is part of the result: a different seed gives a
    different set of claimants and the same totals.
    """
    if rfr_per_part.shape != weights.shape:
        raise NicheImputationError(
            f"rfr_per_part {rfr_per_part.shape} and weights {weights.shape} differ")
    rng = np.random.default_rng(seed)
    bases: dict[str, np.ndarray] = {}

    for niche in IMPUTABLE:
        table = brackets(niche, year, raw)
        base = np.zeros_like(rfr_per_part, dtype=float)
        for bracket in table:
            in_band = (rfr_per_part >= bracket.lower) & (rfr_per_part < bracket.upper)
            available = float(weights[in_band].sum())
            if available <= 0 or bracket.claimants <= 0:
                continue
            probability = min(bracket.claimants / available, 1.0)
            drawn = in_band & (rng.random(rfr_per_part.shape) < probability)
            # The published amount is a CREDIT; the déclaration carries the BASE.
            base[drawn] = bracket.mean_credit / niche.rate
        bases[niche.case] = base
    return bases


def imputed_total(bases: dict[str, np.ndarray], weights: np.ndarray) -> dict[str, float]:
    """What the imputation actually handed out, in euros of CREDIT.

    Reported so the calibration can be checked against its own target — which is a
    check that the draw worked, not evidence that anything is true.
    """
    by_case = {}
    for niche in IMPUTABLE:
        if niche.case in bases:
            by_case[niche.case] = float(
                (bases[niche.case] * weights).sum() * niche.rate)
    return by_case
