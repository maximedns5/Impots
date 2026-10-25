"""Reading Gechert and Heimberger's meta-analysis of corporate taxes and growth (Phase 11, D-246).

IMK Working Paper n° 210 (2021): 441 estimates from 42 studies of how a point of
statutory corporate tax moves the annual GDP growth rate. Table 2 prints, row « β0 [mean
beyond bias] », the raw unweighted average of the standardised coefficients (column 1)
and the means beyond publication bias (columns 2 to 5). M0 of Phase 11 (R1, D-245) fixes
the range on two of them, as condition 2 of PHASE11_SPEC §2 writes for a meta-analysis
that publishes both: the raw centre and the centre corrected for publication bias, θ = ½
at their midpoint. This module reads the row out of the PDF, so that the store's values
are checked against the file rather than a retyping (D-026).

THE SIGN, spelled out because it is the easy thing to get backwards. The paper's
coefficient is the change in growth for a one-point RISE in the rate: −0,019 means a rise
slows growth. The store's row is per point of CUT, the direction of the owner's question,
so both centres change sign: 0,019 at the top, and the corrected 0,0001 becomes −0,0001
at the bottom — a cut that, beyond the bias, moves nothing.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
SOURCE_FILE = "gechert_heimberger_2021_imk_wp210_corporate_tax_growth.pdf"
TABLE_TITLE = "Table 2: Linear funnel asymmetry and precision"
ROW = "β0 [mean beyond bias]"
N_ROW = "N "
#: Table 2's columns, in the order printed.
COLUMNS = ("unw_avg", "wls_base", "median", "iv", "pcc")
RAW_COLUMN, CORRECTED_COLUMN = "unw_avg", "wls_base"


class GechertError(RuntimeError):
    """The working paper cannot be read as expected."""


@dataclass(frozen=True)
class Coefficient:
    estimate: float
    se: float


@dataclass(frozen=True)
class Reading:
    beyond_bias: dict[str, Coefficient]
    """Row β0, by column of `COLUMNS`: per point of RISE in the rate, as printed."""
    n: dict[str, int]
    table_page: int
    """1-based PDF page of Table 2."""


@dataclass(frozen=True)
class Range:
    low: float
    central: float
    high: float


def _number(token: str) -> float:
    # The paper prints U+2212 for minus and U+2217 for its significance stars.
    cleaned = (token.replace("\u2212", "-").replace("\u2217", "").replace("*", "")
               .replace("(", "").replace(")", ""))
    return float(cleaned)


@lru_cache(maxsize=2)
def _pages(path: str) -> tuple[str, ...]:
    import pypdf

    return tuple((page.extract_text() or "").replace("\xa0", " ")
                 for page in pypdf.PdfReader(path).pages)


def _row(lines: list[str], label: str) -> tuple[list[str], int]:
    for i, line in enumerate(lines):
        if line.strip().startswith(label):
            return line.strip()[len(label):].split(), i
    raise GechertError(f"ligne « {label.strip()} » introuvable dans le tableau 2")


def load(raw: Path | None = None) -> Reading:
    path = (raw or RAW) / SOURCE_FILE
    if not path.exists():
        raise GechertError(f"{path} introuvable — téléchargez-le par le manifeste "
                           f"(`impots data fetch {SOURCE_FILE}`)")
    if importlib.util.find_spec("pypdf") is None:  # pragma: no cover - environment
        raise GechertError("pypdf est requis pour lire le document de travail")
    pages = _pages(str(path))
    page = next((k for k, text in enumerate(pages) if TABLE_TITLE in text), None)
    if page is None:
        raise GechertError(f"« {TABLE_TITLE} » introuvable — le document a changé ?")
    lines = pages[page].splitlines()
    tokens, at = _row(lines, ROW)
    errors = lines[at + 1].split()
    if len(tokens) != len(COLUMNS) or len(errors) != len(COLUMNS):
        raise GechertError(f"ligne β0 : {len(tokens)} estimations et {len(errors)} "
                           f"écarts-types, {len(COLUMNS)} colonnes attendues")
    counts, _ = _row(lines, N_ROW)
    if len(counts) != len(COLUMNS):
        raise GechertError(f"ligne N : {len(counts)} effectifs, {len(COLUMNS)} attendus")
    return Reading(
        beyond_bias={c: Coefficient(_number(e), _number(s))
                     for c, e, s in zip(COLUMNS, tokens, errors, strict=True)},
        n={c: int(v) for c, v in zip(COLUMNS, counts, strict=True)},
        table_page=page + 1)


def convention(reading: Reading) -> Range:
    """The store row of D-246, per point of IS CUT: the corrected centre at the bottom,
    the raw centre at the top, their midpoint in the middle (§2, condition 2)."""
    top = -reading.beyond_bias[RAW_COLUMN].estimate
    bottom = -reading.beyond_bias[CORRECTED_COLUMN].estimate
    if not bottom < top:
        raise GechertError(f"centre corrigé {bottom} au-dessus du centre brut {top} pour "
                           f"une baisse : la plage serait à l'envers")
    return Range(low=bottom, central=(bottom + top) / 2.0, high=top)
