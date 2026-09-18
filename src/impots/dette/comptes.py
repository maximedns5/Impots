"""Phase 8 §6.1 — assembling the REALIZED inputs of the debt identity from published files.

Three manifested sources, each opened through `require_sourced` so a figure can never rest
on a file whose provenance nobody recorded (D-028):

* **the APU account** (INSEE table 7.301, millésime 2025, 1949→2025) — `D41 Intérêts` and
  `B9 Capacité/besoin de financement`;
* **the GDP table** (T_1101 en niveau) — `B1GQ`, the denominator of every ratio here;
* **the Maastricht debt detail** — the end-of-quarter stock and the published ratio.

TWO TRAPS IN THESE FILES, BOTH PINNED BY A CHECK RATHER THAN BY A COMMENT.

1. **`D41` appears TWICE** — once in resources, once in uses. Public administrations both
   receive and pay interest, and the charge that belongs in the debt identity is the NET:
   uses minus resources. Reading the uses row alone overstates it by the resources leg
   (35,8 against 37,6 md€ in 2019, 62,2 against 67,5 in 2025) and inflates `r` by roughly
   8 %. `interest_net_eur` is therefore computed from both rows, and the assembler refuses
   a resources leg that is missing rather than treating it as zero.

2. **The debt stock is in MILLIONS while everything beside it is in milliards.** 2019T4
   reads 2 387 398,96 — which is 2 387,4 md€, not 2,4 million milliards. A misread is a
   factor of a thousand that still parses as a number and still plots as a curve. So the
   unit is not asserted in a comment: `check_units` divides the stock by GDP and requires
   the result to reproduce the PUBLISHED ratio. Off by a thousand, that check fails by a
   thousand. It is the lying-header class again, and it gets the treatment that class gets.

THE STOCK-FLOW ADJUSTMENT IS NOT HERE, AND WILL NEVER BE. The SFA is not an ESA
transaction: it is the bridge between `B.9` and the change in the Maastricht stock, so no
vintage of table 7.301 will ever carry it. `realized_years` takes it as a mandatory
argument and refuses without it — see `path.backtest`, which refuses `None` and refuses an
identically-zero series as the projection default wearing a realized label.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from impots.dette.path import DebtError, RealizedYear

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"

APU_FILE = "insee_cn2025_t7301_compte_administrations_publiques_S13.xlsx"
PIB_FILE = "insee_cn2025_pib_T1101_1103.xlsx"
DETTE_FILE = "insee_dette_maastricht_detail.xlsx"

#: Row labels, matched on the ESA CODE at the start of the label — never on the French
#: wording. The `"IS" in label` incident is on the record.
APU_INTEREST = "D41"
APU_NET_LENDING = "B9"
PIB_CODE = "B1GQ"

#: How closely `stock / PIB` must reproduce the published ratio. Loose enough for the
#: footnote — at Q4 the published ratio uses « le PIB annuel en données brutes », which is
#: not exactly the annual accounts figure — and a thousand times tighter than the unit
#: error it exists to catch.
UNIT_TOLERANCE = 0.005

_YEAR = re.compile(r"(19|20)\d\d(\.0)?")


def _rows(filename: str, sheet: str) -> list[tuple[Any, ...]]:
    """Open a manifested file's sheet. Refuses an unsourced one before reading a byte."""
    import warnings

    import openpyxl

    from impots.population.ingest import require_sourced

    require_sourced(filename)
    path = RAW / filename
    if not path.exists():
        raise DebtError(
            f"{filename} est au manifeste mais absent de {RAW} : voir "
            f"docs/M1_BACKTEST_INPUTS.md pour sa provenance.")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        book = openpyxl.load_workbook(path, data_only=True)
    if sheet not in book.sheetnames:
        raise DebtError(
            f"{filename} : feuille « {sheet} » absente ({book.sheetnames}). Le fichier a "
            f"changé de forme et les repères codés ici ne s'appliquent plus.")
    return list(book[sheet].iter_rows(values_only=True))


def _year_columns(rows: list[tuple[Any, ...]], *, depth: int = 10) -> dict[int, int]:
    """Locate the year header. Years are stored as TEXT in these workbooks."""
    for row in rows[:depth]:
        found = {int(float(str(c).strip())): i for i, c in enumerate(row)
                 if c is not None and _YEAR.fullmatch(str(c).strip())}
        if len(found) > 3:
            return found
    raise DebtError(
        "aucune ligne d'en-tête d'années : sans elle chaque colonne serait lue à "
        "l'aveugle, ce qui produirait une série alignée sur les mauvaises dates.")


def _code_rows(rows: list[tuple[Any, ...]], code: str) -> list[int]:
    """Row indices whose first cells START with the ESA code. Codes, not labels."""
    out = []
    for i, row in enumerate(rows):
        head = " ".join(str(c) for c in row[:2] if c is not None).strip()
        if head.split(" ")[:1] == [code]:
            out.append(i)
    return out


@dataclass(frozen=True)
class ApuYear:
    year: int
    interest_resources_eur: float
    interest_uses_eur: float
    net_lending_eur: float
    """B.9, DEFICIT NEGATIVE as published."""

    @property
    def interest_net_eur(self) -> float:
        return self.interest_uses_eur - self.interest_resources_eur

    @property
    def primary_balance_eur(self) -> float:
        """B.9 plus the interest paid back in — SURPLUS POSITIVE, `path`'s convention."""
        return self.net_lending_eur + self.interest_net_eur


def apu_account(years: list[int]) -> dict[int, ApuYear]:
    """`D41` (both legs) and `B9` per year, in euros."""
    rows = _rows(APU_FILE, "T_7301")
    columns = _year_columns(rows)
    interest = _code_rows(rows, APU_INTEREST)
    lending = _code_rows(rows, APU_NET_LENDING)
    if len(interest) != 2:
        raise DebtError(
            f"{APU_FILE} : {len(interest)} ligne(s) « {APU_INTEREST} », attendu 2 "
            f"(ressources ET emplois). L'intérêt NET est leur différence ; une seule "
            f"ligne signifie que le fichier a changé et que le net serait faux d'une "
            f"jambe entière.")
    if len(lending) != 1:
        raise DebtError(f"{APU_FILE} : {len(lending)} ligne(s) « {APU_NET_LENDING} », "
                        f"attendu 1")
    resources_row, uses_row = interest

    out: dict[int, ApuYear] = {}
    for year in years:
        if year not in columns:
            raise DebtError(
                f"{APU_FILE} : année {year} absente (couverture {min(columns)}–"
                f"{max(columns)}). Un backtest amputé d'une année doit le DIRE, pas "
                f"l'enjamber.")
        index = columns[year]
        values = []
        for row in (resources_row, uses_row, lending[0]):
            cell = rows[row][index]
            if cell is None or isinstance(cell, str):
                raise DebtError(
                    f"{APU_FILE} : valeur manquante ou textuelle en {year} (ligne {row}, "
                    f"« {cell} »). Traitée comme zéro, elle passerait sans erreur.")
            values.append(float(cell) * 1e9)     # le fichier est en MILLIARDS d'euros
        out[year] = ApuYear(year=year, interest_resources_eur=values[0],
                            interest_uses_eur=values[1], net_lending_eur=values[2])
    return out


def gdp(years: list[int]) -> dict[int, float]:
    """Nominal GDP in euros, from `B1GQ`."""
    rows = _rows(PIB_FILE, "T_1101 en niveau")
    columns = _year_columns(rows)
    matches = _code_rows(rows, PIB_CODE)
    if len(matches) != 1:
        raise DebtError(f"{PIB_FILE} : {len(matches)} ligne(s) « {PIB_CODE} », attendu 1")
    row = rows[matches[0]]
    out = {}
    for year in years:
        if year not in columns:
            raise DebtError(f"{PIB_FILE} : année {year} absente")
        out[year] = float(row[columns[year]]) * 1e9
    return out


def debt(years: list[int]) -> dict[int, tuple[float, float]]:
    """(stock in euros, published ratio) at Q4 of each year.

    The stock column is in MILLIONS while its neighbours are in milliards — see the module
    docstring. `check_units` is what proves the conversion, not this comment.
    """
    rows = _rows(DETTE_FILE, "FR")
    header = next((r for r in rows[:10]
                   if sum(1 for c in r if c is not None and
                          re.fullmatch(r"(19|20)\d\dT[1-4]", str(c).strip())) > 3), None)
    if header is None:
        raise DebtError(f"{DETTE_FILE} : aucun en-tête trimestriel repérable")
    quarters = {str(c).strip(): i for i, c in enumerate(header) if c is not None}
    out = {}
    for year in years:
        key = f"{year}T4"
        if key not in quarters:
            raise DebtError(
                f"{DETTE_FILE} : {key} absent. Le stock de fin d'année est le point de "
                f"comparaison du backtest ; l'extrapoler depuis un autre trimestre "
                f"inventerait la grandeur mesurée.")
        index = quarters[key]
        out[year] = (float(rows[6][index]) * 1e6, float(rows[7][index]))
    return out


def check_units(years: list[int]) -> dict[int, float]:
    """Stock ÷ GDP against the PUBLISHED ratio — which is what pins the million/milliard.

    Returns the residual per year. A stock read as milliards instead of millions fails
    this by a factor of a thousand; a comment asserting the unit would not have.
    """
    stocks = debt(years)
    product = gdp(years)
    residuals = {}
    for year in years:
        stock, published = stocks[year]
        computed = stock / product[year]
        residual = computed / published - 1.0
        if abs(residual) > UNIT_TOLERANCE:
            raise DebtError(
                f"{year} : dette/PIB reconstruit {computed:.4f} contre {published:.4f} "
                f"publié ({residual:+.2%}, tolérance {UNIT_TOLERANCE:.1%}). Les unités ne "
                f"concordent pas — le stock est en MILLIONS d'euros et le PIB en "
                f"milliards, et une confusion vaut un facteur mille qui se trace encore "
                f"comme une courbe.")
        residuals[year] = residual
    return residuals


class ImpliedSfa(float):
    """An SFA DERIVED from the identity the backtest is supposed to test.

    A float subclass rather than a plain value, so that `realized_years` can REFUSE it by
    type. The refusal has to be mechanical: this is the most tempting shortcut on the
    board, the derivation takes one line, and the resulting backtest reports a perfect
    match — which is exactly why it must be impossible rather than discouraged.
    """


def sfa_implied_by_identity(years: list[int]) -> dict[int, ImpliedSfa]:
    """The SFA as the residual `Δdette − déficit`, in points of GDP.

    **NEVER usable as an input to the backtest, and the type enforces it.** The backtest
    asks whether the identity reproduces the published debt path. Feeding it an SFA
    derived from that same path closes the identity BY CONSTRUCTION: the residual is zero
    by arithmetic, no model error can ever show, and the test reports a perfect score
    while measuring nothing. That is the D-044 shape in its purest form — a check derived
    from the thing it checks cannot fail when that thing is wrong.

    What it IS for: cross-checking the PUBLISHED series once it is manifested. Agreement
    validates the extraction; disagreement localises a perimeter difference. Both are
    findings. Neither is a backtest.
    """
    span = [years[0] - 1, *years]
    stocks = debt(span)
    accounts = apu_account(years)
    product = gdp(years)
    return {y: ImpliedSfa(((stocks[y][0] - stocks[y - 1][0])
                           + accounts[y].net_lending_eur) / product[y])
            for y in years}


def realized_years(years: list[int], *, sfa: dict[int, float]) -> list[RealizedYear]:
    """Assemble §6.1's realized inputs. **`sfa` is mandatory and must cover every year.**

    `r` is the implicit rate on the OPENING stock — the year's net interest over the
    previous year's debt — so the first year needs its predecessor, which is read here
    rather than requested from the caller.
    """
    if not years:
        raise DebtError("aucune année demandée")
    ordered = sorted(years)
    derived = sorted(y for y, v in sfa.items() if isinstance(v, ImpliedSfa))
    if derived:
        raise DebtError(
            f"ajustement flux-stocks DÉRIVÉ fourni pour {derived} : refusé. Il a été "
            f"calculé comme le résidu « Δdette − déficit », c'est-à-dire depuis la "
            f"trajectoire même que le backtest doit reproduire. L'identité se refermerait "
            f"PAR CONSTRUCTION, le résidu serait nul par arithmétique, aucune erreur de "
            f"modèle ne pourrait jamais apparaître — et le test rendrait un score parfait "
            f"en ne mesurant rien. Il faut la série PUBLIÉE (notification EDP, Eurostat "
            f"gov_10dd_edpt1) ; `sfa_implied_by_identity` ne sert qu'à la recouper.")

    missing = [y for y in ordered if y not in sfa]
    if missing:
        raise DebtError(
            f"ajustement flux-stocks absent pour {missing} : il est OBLIGATOIRE, et il "
            f"ne viendra d'aucun millésime de la table 7.301 — le SFA n'est pas une "
            f"opération du SEC mais le pont entre B.9 et la variation du stock. Sources : "
            f"tableaux de notification EDP, ou Eurostat gov_10dd_edpt1. Voir "
            f"docs/M1_BACKTEST_INPUTS.md §3.")

    span = [ordered[0] - 1, *ordered]
    check_units(span)
    accounts = apu_account(ordered)
    product = gdp(span)
    stocks = debt(span)

    out = []
    for year in ordered:
        account = accounts[year]
        opening_stock, _ = stocks[year - 1]
        out.append(RealizedYear(
            year=year,
            r=account.interest_net_eur / opening_stock,
            g=product[year] / product[year - 1] - 1.0,
            primary_balance=account.primary_balance_eur / product[year],
            sfa=sfa[year],
            published_ratio=stocks[year][1],
        ))
    return out


def opening_ratio(first_year: int) -> float:
    """The b0 the backtest starts from: the published ratio at the end of the prior year."""
    return debt([first_year - 1])[first_year - 1][1]
