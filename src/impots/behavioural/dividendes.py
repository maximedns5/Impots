"""Reading Bach, Bozio, Guillouzouic, Leroy and Malgouyres on dividends and the PFU (D-249).

« Follow the money! Why dividends overreact to flat-tax reforms », PSE Working Paper
n° 2019-70, version 2 (HAL, 2 September 2024): the French evaluation of the 2018 PFU and
of the 2013 end of the PFL, by the IPP's team, on the tax registers of households and
firms joined through ownership. The rank-1 source of PHASE11_SPEC §6 (D-245, R6).

WHAT IT PUBLISHES, AND WHAT THE STORE TAKES.
- The elasticity of dividends received to the net-of-tax rate, by household, in the
  sample of wealth-tax payers (p. 3 and p. 16): 2,5 for firm owners and close to 0 for the
  others after the 2018 cut, which the authors hold « the most informative »; 3,2 and 2,4
  after the 2013 hike, when firm ownership is less well measured. Read from the text.
- The variation that identified them: the net-of-tax rate of the treated rose by 7,5 %
  (firm owners) and 8,5 % (the others) in 2018, and fell by 6 % in 2013 (p. 16). Read from
  the text; it bounds the support.
- The share of declared dividends that goes to households controlling a firm. The
  aggregate elasticity turns on it, and no table prints it for the whole population
  (M0, R6): only Figure 2d draws it, year by year, in four series (wealth-tax payers or
  not, firm control or not). The figure is VECTOR, a Stata export, so its points are read
  from the drawing's own coordinates, not digitised from an image: the axes are
  calibrated on the figure's gridlines and tick labels, and the four series named by the
  legend that draws them. Two checks hold the reading. Their sum gives back, year by
  year, the income-tax-return series of Figure 2b, drawn separately (MATCH_BN); and its
  rise from 2017 to 2018 is the « year-to-year variation of 9 billion euros » the text
  prints (p. 10).

THE AGGREGATE. ε = s ε_owners + (1 − s) ε_others, with s the firm-control share. The store
holds the three as rows, each in its published range, and the dividend channel C10
composes them: that keeps each number tied to the place it is printed.
"""

from __future__ import annotations

import importlib.util
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
SOURCE_FILE = "pse_wp_2019_70_v2_bach_et_al_dividends_flat_tax.pdf"

#: Figure 2 is on this page (1-based), panels (b) and (d) drawn as form XObjects.
FIGURE_PAGE = 35
#: Panel (d)'s legend, as printed: the four series of the figure.
SERIES = ("Not ISF w/ firm control", "ISF w/ firm control",
          "Not ISF without firm control", "ISF without firm control")
WITH_CONTROL = SERIES[:2]
#: Panel (b)'s series of dividends declared on income-tax returns: its legend label.
RETURNS_SERIES = "Dividends received by households in income tax returns aggregates"
#: How closely panel (d)'s four series must sum to panel (b)'s returns series, in bn:
#: both are drawn from the same data, so only the plotting resolution separates them.
MATCH_BN = 0.05
#: « a year-to-year variation of 9 billion euros » (p. 10), within its own rounding.
YEAR_TO_YEAR_BN, YEAR_TO_YEAR_SLACK = 9.0, 0.5
#: The years the PFU has been in force in the figure: the regime a PFU knob moves.
PFU_YEARS = (2018, 2019, 2020, 2021)
#: Stroke width of a plotted series in the figure's own units: the gridlines are thinner.
SERIES_WIDTH = 60.0
GRID_GREY = (0.81569, 0.81569, 0.81569)

ELASTICITY_2018 = re.compile(
    r"implied elasticity to the net-of-tax rate of (\d\.\d) for firm-owners, while it is "
    r"close to (\d) for non-firm owners")
ELASTICITY_2013 = re.compile(
    r"For the 2013 reform, we obtain elasticities of (\d\.\d) for firm owners against "
    r"(\d\.\d) for non-firm owners")
VARIATION_2013 = re.compile(
    r"Treated households see a (\d+(?:\.\d)?)% decrease in their net-of-tax rate after "
    r"the 2013 reform")
VARIATION_2018 = re.compile(
    r"In 2018, treated non firm owners households see an? (\d+(?:\.\d)?)% increase and "
    r"treated firm owners see an? (\d+(?:\.\d)?)% increase in their net-of-tax rate")


class DividendSourceError(RuntimeError):
    """The working paper cannot be read as expected."""


@dataclass(frozen=True)
class Elasticities:
    owners_2018: float
    others_2018: float
    owners_2013: float
    others_2013: float
    variation_owners_2018: float
    variation_others_2018: float
    variation_2013: float
    """Relative changes of the treated's net-of-tax rate, as fractions."""


@dataclass(frozen=True)
class Figure2d:
    series: dict[str, dict[int, float]]
    """Panel (d): bn EUR of dividends by series and year."""
    returns: dict[int, float]
    """Panel (b): bn EUR of dividends on income-tax returns, by year."""

    def total(self, year: int) -> float:
        return sum(self.series[name][year] for name in SERIES)

    def share_with_control(self, year: int) -> float:
        return sum(self.series[name][year] for name in WITH_CONTROL) / self.total(year)


def _reader(raw: Path | None):
    path = (raw or RAW) / SOURCE_FILE
    if not path.exists():
        raise DividendSourceError(f"{path} introuvable — téléchargez-le par le manifeste "
                                  f"(`impots data fetch {SOURCE_FILE}`)")
    if importlib.util.find_spec("pypdf") is None:  # pragma: no cover - environment
        raise DividendSourceError("pypdf est requis pour lire le document de travail")
    import pypdf

    return pypdf.PdfReader(str(path))


def _text(page) -> str:
    # NFKC: the PDF sets « firm » and « effect » with ligatures no pattern matches.
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", page.extract_text() or ""))


def elasticities(raw: Path | None = None) -> Elasticities:
    """The four elasticities and the three variations, from the paper's own sentences."""
    text = " ".join(_text(page) for page in _reader(raw).pages[:30])
    found = {}
    for name, pattern in (("2018", ELASTICITY_2018), ("2013", ELASTICITY_2013),
                          ("v2013", VARIATION_2013), ("v2018", VARIATION_2018)):
        match = pattern.search(text)
        if match is None:
            raise DividendSourceError(
                f"la phrase « {pattern.pattern[:60]}… » est introuvable : le document a "
                f"changé, ou ce n'est pas la version 2")
        found[name] = tuple(float(group) for group in match.groups())
    return Elasticities(
        owners_2018=found["2018"][0], others_2018=found["2018"][1],
        owners_2013=found["2013"][0], others_2013=found["2013"][1],
        variation_others_2018=found["v2018"][0] / 100,
        variation_owners_2018=found["v2018"][1] / 100,
        variation_2013=found["v2013"][0] / 100)


def _forms(reader) -> dict[tuple[float, float], object]:
    """Figure 2's panels, keyed by where the page draws each."""
    page = reader.pages[FIGURE_PAGE - 1]
    content = page.get_contents().get_data().decode("latin-1")
    xobjects = page["/Resources"]["/XObject"]
    placed = {}
    for match in re.finditer(r"1 0 0 1 ([-\d.]+) ([-\d.]+) cm\s+q\s+[\d.]+ 0 0 [\d.]+ 0 0 "
                             r"cm\s+q\s+1 0 0 1 0 0 cm\s+/(Im\d+) Do", content):
        placed[(round(float(match.group(1)), 1), round(float(match.group(2)), 1))] = (
            xobjects[f"/{match.group(3)}"].get_object())
    return placed


def _texts(reader) -> dict[tuple[float, float], list[tuple[float, float, str]]]:
    """Every text a panel prints, in the panel's own coordinates, by panel placement."""
    found: dict[tuple[float, float], list[tuple[float, float, str]]] = {}
    pending: list[tuple[float, float, str]] = []

    # pypdf visits a panel's texts one by one, in the panel's coordinates under its inner
    # scaling and with no translation, then once more as a single block whose matrix
    # carries the panel's placement: that block names the panel the pieces before it
    # belong to. A page text, whose matrix is the identity, separates two panels.
    def visit(text, cm, tm, *_):
        if not text.strip():
            return
        if list(cm) == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]:
            pending.clear()
        elif (cm[4], cm[5]) == (0.0, 0.0):
            pending.append((round(tm[4], 1), round(tm[5], 1), text.strip()))
        else:
            found[(round(cm[4], 1), round(cm[5], 1))] = list(pending)
            pending.clear()

    reader.pages[FIGURE_PAGE - 1].extract_text(visitor_text=visit)
    return found


def _strokes(form) -> list[tuple[tuple[float, ...], float, list[tuple[float, float]]]]:
    """(colour, width, points) for every stroked path of a panel."""
    colour, width, points, strokes = (), 0.0, [], []
    for token in form.get_data().decode("latin-1").split("\n"):
        token = token.strip()
        if m := re.fullmatch(r"([\d.]+) ([\d.]+) ([\d.]+) RG", token):
            colour = tuple(float(x) for x in m.groups())
        elif m := re.fullmatch(r"([\d.]+) w", token):
            width = float(m.group(1))
        elif m := re.fullmatch(r"([-\d.]+) ([-\d.]+) ([ml])", token):
            point = (float(m.group(1)), float(m.group(2)))
            points = [point] if m.group(3) == "m" else [*points, point]
        elif token == "S" and points:
            strokes.append((colour, width, points))
            points = []
    return strokes


def _panel(form, texts: list[tuple[float, float, str]], labels: tuple[str, ...]
           ) -> dict[str, dict[int, float]]:
    """The named series of one panel, in bn, calibrated on its own gridlines and ticks."""
    strokes = _strokes(form)
    grid = sorted({points[0][1] for colour, _, points in strokes
                   if colour == GRID_GREY and points[0][1] == points[-1][1]})
    columns = sorted({points[0][0] for colour, _, points in strokes
                      if colour == GRID_GREY and points[0][0] == points[-1][0]})
    ticks = [float(t) for _, _, t in texts if re.fullmatch(r"\d+", t)]
    years = [int(y) for _, _, line in texts for y in line.split()
             if re.fullmatch(r"20\d\d", y)]
    # The axis ticks are 0, step, ..., top; every tick but 0 has its gridline.
    values = [t for t in ticks if t < 1000][1:]
    if len(values) != len(grid) or len(years) != len(columns) or len(grid) < 2:
        raise DividendSourceError(
            f"axes illisibles : {len(grid)} lignes de grille pour les graduations "
            f"{values}, {len(columns)} colonnes pour les années {years}")
    step = (grid[-1] - grid[0]) / (values[-1] - values[0])

    def bn(y: float) -> float:
        return values[0] + (y - grid[0]) / step

    spacing = (columns[-1] - columns[0]) / (len(columns) - 1)

    def year_at(x: float) -> int:
        # A point sits on its year's gridline to within a unit of the drawing (9135
        # against 9136); a point between two would be a misreading.
        index = min(range(len(columns)), key=lambda i: abs(columns[i] - x))
        if abs(columns[index] - x) > 0.05 * spacing:
            raise DividendSourceError(f"un point en x = {x} ne tombe sur aucune année")
        return years[index]

    series = [(colour, points) for colour, width, points in strokes
              if width > SERIES_WIDTH and len(points) == len(columns)]
    legend = [(colour, points[0]) for colour, width, points in strokes
              if width > SERIES_WIDTH and len(points) == 2]
    out: dict[str, dict[int, float]] = {}
    for label in labels:
        anchor = next(((x, y) for x, y, line in texts if line == label), None)
        if anchor is None:
            raise DividendSourceError(f"la légende « {label} » est introuvable")
        # The legend's sample line sits on the label's row, to its left.
        sample = min((c for c, (x, y) in legend if x < anchor[0]),
                     key=lambda c: min(abs(y - anchor[1]) + (anchor[0] - x)
                                       for cc, (x, y) in legend if cc == c),
                     default=None)
        line = next((points for colour, points in series if colour == sample), None)
        if line is None:
            raise DividendSourceError(f"aucune série tracée pour « {label} »")
        out[label] = {year_at(x): round(bn(y), 3) for x, y in line}
    return out


@lru_cache(maxsize=2)
def figure_2d(raw: Path | None = None) -> Figure2d:
    """Panels (d) and (b) of Figure 2, read from the drawing, with the two checks."""
    reader = _reader(raw)
    forms, texts = _forms(reader), _texts(reader)
    panel_d = next((key for key, lines in texts.items()
                    if any(line == SERIES[0] for _, _, line in lines)), None)
    panel_b = next((key for key, lines in texts.items()
                    if any(line == RETURNS_SERIES for _, _, line in lines)), None)
    if panel_d not in forms or panel_b not in forms:
        raise DividendSourceError("les panneaux (b) et (d) de la figure 2 sont introuvables")
    series = _panel(forms[panel_d], texts[panel_d], SERIES)
    returns = _panel(forms[panel_b], texts[panel_b], (RETURNS_SERIES,))[RETURNS_SERIES]
    figure = Figure2d(series=series, returns=returns)
    for year, declared in returns.items():
        if abs(figure.total(year) - declared) > MATCH_BN:
            raise DividendSourceError(
                f"{year} : les quatre séries du panneau (d) font {figure.total(year):.2f} "
                f"Md€, le panneau (b) {declared:.2f} : la lecture est fausse")
    rise = figure.total(2018) - figure.total(2017)
    if abs(rise - YEAR_TO_YEAR_BN) > YEAR_TO_YEAR_SLACK:
        raise DividendSourceError(
            f"de 2017 à 2018 la figure monte de {rise:.2f} Md€, le texte en imprime 9")
    return figure


@dataclass(frozen=True)
class Range:
    low: float
    central: float
    high: float


def convention(found: Elasticities, figure: Figure2d) -> dict[str, Range]:
    """The three store rows of D-249, from the readings.

    - Firm owners: 2,5 (2018, the authors' preferred) to 3,2 (2013), centred on 2,5.
    - The others: 0 (2018) to 2,4 (2013), centred on 0 — the 2013 figure is the one the
      authors say measurement error inflates.
    - The firm-control share: the four PFU years of Figure 2d, from the lowest to the
      highest, centred on their mean.
    """
    shares = [figure.share_with_control(year) for year in PFU_YEARS]
    return {
        "dividend_elasticity_firm_owners": Range(
            low=found.owners_2018, central=found.owners_2018, high=found.owners_2013),
        "dividend_elasticity_other_holders": Range(
            low=found.others_2018, central=found.others_2018, high=found.others_2013),
        "dividend_share_firm_owners": Range(
            low=round(min(shares), 3), central=round(sum(shares) / len(shares), 3),
            high=round(max(shares), 3)),
    }
