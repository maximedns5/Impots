"""Reading the IPP's report n° 47 on firm creations (Phase 9 M5, D-221).

Bach, Bozio, Fize, Guillouzouic and Malgouyres compare, across 643 fine sectors, the
creation rate of companies before and after the 2018 capital-tax reforms, against how
much each sector's shareholders gained from them. Tableau 2.2 holds the static
difference-in-differences estimates; its panel (b), « Exposition linéaire aux
réformes », row IS-PFU, is the joint effect of the corporate-tax cut and the flat tax per
point of fall in the virtual tax rate on profits. This module reads those four cells, and
the three figures of the text the channel's conversion rests on, out of the PDF — so
that the store's values are checked against the file rather than a retyping (D-026).

THE ROW IS READ INSIDE ITS PANEL. Each of the table's four panels has an IS-PFU row; the
one wanted lies between the title of panel (b) and the title of panel (c). The cells
are sparse — the row fills four of twelve columns — and the text extraction does not
keep their positions, so no column number is claimed here: the four estimates are read
in order, and the one the authors quote in their text is found among them by value.
"""

from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
SOURCE_FILE = "ipp_rapport_47_2023_bach_et_al_creations_entreprises.pdf"
#: The committee's final report states the statutory cut the IPP report does not.
FS_FILE = "france_strategie_2023_fiscalite_capital_rapport_final.pdf"
FS_PAGE_HINT = 238

TABLE_TITLE = "TABLEAU 2.2"
PANEL = "(b) Exposition linéaire aux réformes"
NEXT_PANEL = "(c) Exposition"
ROW = "IS-PFU"

#: The sentences of the text the channel rests on, each with the figure it carries.
QUOTED = re.compile(r"hausse de (\d,\d+) point du taux de création non pondéré")
MEAN_IS_EXPOSURE = re.compile(
    r"baisse moyenne à travers les secteurs est de (\d,\d) % pour l.IS")
STATUTORY_CUT = re.compile(
    r"baisse du taux de l.IS de (\d+,\d+) % à (\d+) % entre (\d{4}) et (\d{4})")
PFU_RATE = re.compile(
    r"taux uniforme à (\d+) % \((\d+,\d) % d.impôt sur le revenu et (\d+,\d) % de "
    r"prélèvements sociaux\)")


class IppError(RuntimeError):
    """The report cannot be read as expected."""


@dataclass(frozen=True)
class Coefficient:
    estimate: float
    se: float


@dataclass(frozen=True)
class Reading:
    joint: tuple[Coefficient, ...]
    """Panel (b), row IS-PFU, in the order printed."""
    quoted: float
    """The joint effect the authors give in their text, « 0,38 »."""
    mean_is_exposure: float
    """Points: the sectors' mean fall in the virtual IS rate from the 2018 cut."""
    pfu_rate: float
    """The flat tax, as a fraction: 12,8 % of income tax and 17,2 % of social levies."""
    table_page: int
    """1-based PDF page of Tableau 2.2."""


def _number(token: str) -> float:
    return float(token.replace("*", "").replace("(", "").replace(")", "").replace(",", "."))


@lru_cache(maxsize=2)
def _reader(path: str) -> object:
    import pypdf

    return pypdf.PdfReader(path)


@lru_cache(maxsize=512)
def _page(path: str, k: int) -> str:
    """One page's text, extracted once: the figures wanted sit in the first half of a
    136-page report, and extracting it whole doubles the cost for nothing."""
    return (_reader(path).pages[k].extract_text() or "").replace("\xa0", " ")


def _pages(path: str):
    return (_page(path, k) for k in range(len(_reader(path).pages)))


def _joint(lines: list[str]) -> tuple[Coefficient, ...]:
    start = next((i for i, line in enumerate(lines) if PANEL in line), None)
    if start is None:
        raise IppError(f"panneau « {PANEL} » introuvable dans le tableau 2.2")
    stop = next((i for i in range(start + 1, len(lines)) if NEXT_PANEL in lines[i]),
                len(lines))
    for i in range(start + 1, min(stop, len(lines) - 1)):
        tokens = lines[i].split()
        if tokens and tokens[0] == ROW:
            estimates = [_number(t) for t in tokens[1:]]
            errors = [_number(t) for t in lines[i + 1].split()]
            if not estimates or len(estimates) != len(errors):
                raise IppError(f"ligne {ROW} : {len(estimates)} estimations, "
                               f"{len(errors)} écarts-types")
            return tuple(Coefficient(e, s) for e, s in zip(estimates, errors, strict=True))
    raise IppError(f"ligne {ROW} introuvable dans « {PANEL} »")


def _quoted_among(quoted: float, joint: tuple[Coefficient, ...]) -> float:
    """The authors' « 0,38 » must be one of the cells read: a reading that drifted to
    another panel, or a table that changed, stops here."""
    if quoted not in {round(c.estimate, 2) for c in joint}:
        raise IppError(f"le texte cite {quoted}, qu'aucune cellule IS-PFU du panneau (b) "
                       f"ne donne : {[c.estimate for c in joint]}")
    return quoted


def _search(path: str, pattern: re.Pattern[str], hint: int | None = None) -> re.Match[str]:
    order = _pages(path) if hint is None else (
        _page(path, k) for k in (hint, *range(len(_reader(path).pages))))
    for text in order:
        match = pattern.search(re.sub(r"\s+", " ", text))
        if match:
            return match
    raise IppError(f"phrase introuvable dans le rapport : {pattern.pattern}")


def load(raw: Path | None = None) -> Reading:
    path = (raw or RAW) / SOURCE_FILE
    if not path.exists():
        raise IppError(f"{path} introuvable — téléchargez-le par le manifeste "
                       f"(`impots data fetch {SOURCE_FILE}`)")
    if importlib.util.find_spec("pypdf") is None:  # pragma: no cover - environment
        raise IppError("pypdf est requis pour lire le rapport")
    path = str(path)
    page = next((k for k, text in enumerate(_pages(path)) if TABLE_TITLE in text), None)
    if page is None:
        raise IppError(f"{TABLE_TITLE} introuvable — le document a changé ?")
    joint = _joint(_page(path, page).splitlines())
    quoted = _quoted_among(_number(_search(path, QUOTED).group(1)), joint)
    pfu = _search(path, PFU_RATE)
    total, income, social = (_number(g) for g in pfu.groups())
    if abs(income + social - total) > 1e-9:
        raise IppError(f"PFU : {income} + {social} ne font pas {total}")
    return Reading(joint=joint, quoted=quoted,
                   mean_is_exposure=_number(_search(path, MEAN_IS_EXPOSURE).group(1)),
                   pfu_rate=total / 100.0, table_page=page + 1)


def statutory_cut(raw: Path | None = None) -> tuple[float, float]:
    """(before, after), in points: the IS normal rate the 2018 reform cut from and to, as
    the committee's report states it (« de 33,33 % à 25 % entre 2019 et 2022 »)."""
    path = (raw or RAW) / FS_FILE
    if not path.exists():
        raise IppError(f"{path} introuvable — téléchargez-le par le manifeste "
                       f"(`impots data fetch {FS_FILE}`)")
    match = _search(str(path), STATUTORY_CUT, hint=FS_PAGE_HINT)
    return _number(match.group(1)), _number(match.group(2))


def exposure_per_is_point(reading: Reading, cut: tuple[float, float]) -> float:
    """Points of the paper's joint virtual rate per point of IS normal rate — THIS
    PROJECT'S DERIVATION, not a figure of the paper (D-221).

    The sectors' mean fall in the virtual IS rate (5,4 points) over the statutory cut
    (33,33 − 25 = 8,33 points) is the share of a nominal point that reached
    shareholders; the joint measure counts the flat tax the released dividends then pay
    (« la baisse de l'IS augmente les dividendes versés et donc augmente à la marge le
    rendement du PFU », p. 56), so a point of IS alone moves it by that share times
    (1 − 30 %). 5,4 / 8,33 × 0,7 = 0,4538.
    """
    before, after = cut
    return reading.mean_is_exposure / (before - after) * (1.0 - reading.pfu_rate)


#: Every cell is printed to three decimals: the true figure lies within half a unit of
#: the last digit of the printed one.
ROUNDING = 0.0005
Z95 = 1.96


@dataclass(frozen=True)
class Range:
    low: float
    central: float
    high: float


def convention(reading: Reading) -> Range:
    """The store row of D-221, from the cells.

    THE CENTRE is the estimate the authors quote in their text, 0,38 (column 6: IS-PFU
    with the IFI as control). THE TOP is the highest end of the four IS-PFU columns' 95 %
    intervals, each printed figure widened by `ROUNDING`. THE BOTTOM IS ZERO, not the
    lowest interval's end: the joint coefficient prices a point of IS like a point of
    flat tax, and the paper cannot tell them apart — the IS alone, with the flat tax
    controlled, is 0,123 (0,188) and 0,315 (0,207), both indistinguishable from zero.
    """
    high = max(c.estimate + ROUNDING + Z95 * (c.se + ROUNDING) for c in reading.joint)
    return Range(low=0.0, central=reading.quoted, high=round(high, 10))
