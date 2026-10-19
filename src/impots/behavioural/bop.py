"""Reading Bargain, Orsini and Peichl (2012), IZA DP n° 6735, annex F (Phase 9 M5, D-220).

The labour-supply channel died in D-031 because its two scalars were averages the paper
never states. What the paper does state, for France, is a table per group — married
women, married men, single women, single men — with an own-wage elasticity for 1998
and for 2001 and a standard error under each. This module reads those cells out of the
PDF, so that the store's values can be checked against the file rather than against a
retyping (D-026).

THE COLUMNS ARE FOUND BY THEIR HEADER, never assumed by position. Each table prints a
country row (« AT BE BE DK FI FR FR … ») above a year row (« 98 98 01 … »); France is
the pair (FR, 98) and (FR, 01) read off those two rows.

THE ROWS ARE READ INSIDE THEIR BLOCK. A table is a stack of blocks, each under a title
line: the own-wage elasticity (« Own-wage elasticity » for couples, « Wage elasticity »
for singles), its sub-groups by quintile, the cross-wage elasticity (couples only) and
the income elasticity. Every block but the sub-groups has a « Total hours » line, so a
label is looked for between its block's title and the next title, never past it — or a
missing line would come back as the income elasticity's.

WHAT THE ELASTICITY IS. « Baseline elasticities are calculated by incrementing gross
wages by 1 % » (section 5.2): an elasticity of average hours — participation included —
to the GROSS wage, computed on adults aged 18 to 59 available for the labour market, not
self-employed. The net-wage elasticities are larger, and the paper shows them only in a
figure (Figure 9), which this module does not read.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
SOURCE_FILE = "iza_dp6735_2012_bargain_orsini_peichl_labor_supply.pdf"

#: Group → the table's own title, spaces removed (the extraction splits « W omen »).
TABLES: dict[str, tuple[str, str]] = {
    "femmes_en_couple": ("F.1", "MarriedWomen"),
    "hommes_en_couple": ("F.3", "MarriedMen"),
    "femmes_seules": ("F.5", "SingleWomen"),
    "hommes_seuls": ("F.7", "SingleMen"),
}

#: The own-wage rows each table prints, in order, under its first block.
ROWS = ("Total hours", "Intensive margin (hour)", "Extensive margin (hour)",
        "Extensive margin (particip.)")

#: Block → the title lines that open it. Singles' tables call the own-wage block
#: « Wage elasticity »: there is no partner whose wage it could be confused with.
BLOCKS = {"own": ("Own-wage elasticity", "Wage elasticity"),
          "cross": ("Cross-wage elasticity",)}

#: Every title line a table prints; a block ends at the next one.
TITLES = (*BLOCKS["own"], *BLOCKS["cross"], "Own-wage elasticity (sub-groups)",
          "Income elasticity")

#: The groups whose table has a cross-wage block: the partner's wage moves their hours.
COUPLES = ("femmes_en_couple", "hommes_en_couple")

YEARS = ("98", "01")


class BopError(RuntimeError):
    """The paper cannot be read as expected."""


@dataclass(frozen=True)
class Cell:
    group: str
    year: str
    block: str
    """« own » or « cross »."""
    row: str
    estimate: float
    se: float
    page: int
    """1-based PDF page."""


def _number(token: str) -> float:
    # The extraction renders the minus sign as a soft hyphen (U+00AD).
    return float(token.replace("\u00ad", "-").replace("(", "").replace(")", ""))


@lru_cache(maxsize=2)
def _pages(path: str) -> tuple[tuple[str, ...], ...]:
    import pypdf

    # Labels arrive with non-breaking spaces (« Total\xa0hours »): normalised once here.
    return tuple(tuple(line.replace("\xa0", " ")
                       for line in (page.extract_text() or "").splitlines())
                 for page in pypdf.PdfReader(path).pages)


def _france_columns(lines: tuple[str, ...]) -> dict[str, int]:
    """{year: column index} of France, from the country row and the year row below it."""
    for i, line in enumerate(lines[:-1]):
        countries = line.split()
        if len(countries) > 5 and countries[:2] == ["AT", "BE"]:
            years = lines[i + 1].split()
            if len(years) != len(countries):
                raise BopError(f"{len(countries)} pays et {len(years)} années : en-tête illisible")
            found = {y: k for k, (c, y) in enumerate(zip(countries, years, strict=True))
                     if c == "FR"}
            if sorted(found) != sorted(YEARS):
                raise BopError(f"colonnes France introuvables : {found}")
            return found
    raise BopError("aucune ligne de pays dans le tableau")


def _row(lines: tuple[str, ...], label: str,
         block: str = "own") -> tuple[list[float], list[float]]:
    """(estimates, standard errors) of the row with this label inside this block."""
    flat = [line.replace("\u00ad", "-") for line in lines]
    start = next((i for i, line in enumerate(flat) if line.strip() in BLOCKS[block]), None)
    if start is None:
        raise BopError(f"bloc « {BLOCKS[block][0]} » introuvable")
    stop = next((i for i in range(start + 1, len(flat)) if flat[i].strip() in TITLES),
                len(flat))
    pattern = re.compile(re.escape(label) + r"\s+[.\d-]")
    for i in range(start + 1, min(stop, len(flat) - 1)):
        if pattern.match(flat[i]):
            values = [_number(t) for t in flat[i][len(label):].split()]
            errors = [_number(t) for t in flat[i + 1].split()]
            if len(values) != len(errors):
                raise BopError(f"« {label} » : {len(values)} valeurs, {len(errors)} écarts-types")
            return values, errors
    raise BopError(f"ligne « {label} » introuvable dans « {BLOCKS[block][0]} »")


def load(raw: Path | None = None) -> dict[tuple[str, str, str, str], Cell]:
    """{(group, year, block, row): Cell} for France, every group, both years: every
    own-wage row, and the cross-wage « Total hours » of the two couples' tables."""
    path = (raw or RAW) / SOURCE_FILE
    if not path.exists():
        raise BopError(f"{path} introuvable — téléchargez-le par le manifeste "
                       f"(`impots data fetch {SOURCE_FILE}`)")
    if importlib.util.find_spec("pypdf") is None:  # pragma: no cover - environment
        raise BopError("pypdf est requis pour lire l'article")
    pages = _pages(str(path))
    cells: dict[tuple[str, str, str, str], Cell] = {}
    for group, (number, title) in TABLES.items():
        anchor = f"Table{number}:LaborSupplyElasticities:{title}"
        page = next((k for k, lines in enumerate(pages)
                     if any(line.replace(" ", "") == anchor for line in lines)), None)
        if page is None:
            raise BopError(f"tableau {number} ({title}) introuvable — le document a changé ?")
        lines = pages[page]
        columns = _france_columns(lines)
        wanted = [("own", label) for label in ROWS]
        if group in COUPLES:
            wanted.append(("cross", "Total hours"))
        for block, label in wanted:
            values, errors = _row(lines, label, block)
            for year, k in columns.items():
                cells[(group, year, block, label)] = Cell(
                    group=group, year=year, block=block, row=label, estimate=values[k],
                    se=errors[k], page=page + 1)
    return cells


# --------------------------------------------------------------------------- #
# From the cells to a row of the store: the convention of D-220
# --------------------------------------------------------------------------- #
#: Every estimate and standard error is printed to two decimals: the true figure lies
#: within half a unit of the last digit of the printed one.
ROUNDING = 0.005
Z95 = 1.96


@dataclass(frozen=True)
class Range:
    low: float
    central: float
    high: float


def convention(cells: dict[tuple[str, str, str, str], Cell], group: str) -> Range:
    """One store row from the cells of one group, by the convention of D-220.

    PER YEAR, the elasticity of the group's hours to a change in EVERY net wage of the
    household — the own-wage elasticity, plus for a couple the cross-wage one, since the
    CSG on earnings moves both partners' wages and the paper prices each with the other's
    held fixed. The covariance of the two is not printed, so the standard error of their
    sum is bounded by the sum of theirs (Var(a + b) ≤ (s_a + s_b)²). And each printed
    figure, estimate or error, is widened by `ROUNDING`.

    THE CENTRE is the mean of the two years. Pooling them, the paper finds for France
    « very similar elasticities for the two years, which broadly correspond to the average
    of the two elasticities obtained from independent estimations » (appendix G): the gap
    between 1998 and 2001 is identification, not a change in preferences.

    THE RANGE is the envelope of the two years' 95 % intervals.
    """
    blocks = ("own", "cross") if group in COUPLES else ("own",)
    lows, highs, centres = [], [], []
    for year in YEARS:
        parts = [cells[(group, year, block, "Total hours")] for block in blocks]
        estimate = sum(c.estimate for c in parts)
        slack = ROUNDING * len(parts)
        half = Z95 * (sum(c.se for c in parts) + slack)
        centres.append(estimate)
        lows.append(estimate - slack - half)
        highs.append(estimate + slack + half)
    return Range(low=round(min(lows), 10), central=round(sum(centres) / len(centres), 10),
                 high=round(max(highs), 10))
