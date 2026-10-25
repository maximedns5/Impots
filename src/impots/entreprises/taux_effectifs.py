"""Phase 11 M3 — the OECD's forward-looking effective tax rates, and the condition M0 set
the national entry index (M0 of Phase 11, R4; D-247).

Da Rin, Di Giacomo and Sembenelli measure firm entry against an effective average tax rate,
not the statutory one. M0 let the national index open only through a method that first
gives back what the OECD publishes for France: « La méthode qui le calcule doit d'abord
redonner le TMEI et le TMEE composites que l'OCDE publie pour la France en 2025, à 0,1
point près, sous les paramètres de l'OCDE. Sinon le canal est refusé. »

This module is that method, the one the OECD's explanatory annex writes (Annex A,
equations A.1 to A.9 and A.14-A.15: the Devereux-Griffith rates in Klemm's permanent
investment, the EMTR tax-exclusive), with its parameters read out of the annex PDF and the
rates the OECD publishes read out of its data (`DSD_ETR@DF_ETR_BASELINE`, France, 2025,
the fixed scenario). Each asset category is priced on the allowance the OECD publishes for
it, so what is tested is the method, not a reading of French depreciation law.

WHAT IT FINDS. Buildings, inventories and software come back within a tenth of a point.
Tangible assets do not: the OECD prices five subgroups, each at its own economic
depreciation, and publishes one allowance, their average. Priced at that average, the
tangibles' EMTR is 12,3 where 9,8 is published, and the composite EMTR misses by more than
half a point. The two gaps stand in the ratio the formulas give for an allowance that
varies from one subgroup to the next (`heterogeneity`), which says the method is not what
fails: the parameters the condition needs are not published. The condition is not met,
and the national entry index stays refused.

The statutory rate is the firm layer's own: the normal rate times one plus the social
contribution, 25,825 % in 2025. The OECD's rates leave out the 2025 exceptional
contribution (annex, § 15), and so does this module.
"""

from __future__ import annotations

import csv
import importlib.util
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
ANNEX_FILE = "oecd_cts_2026_explanatory_annex.pdf"
PUBLISHED_FILE = "oecd_cts_etr_baseline_fra_2025.csv"
COUNTRY, YEAR, SCENARIO = "FRA", "2025", "FIXED"

#: The four categories the composite averages, unweighted (annex, § 18).
CATEGORIES = ("NRS", "TAN", "AWS", "INV")
COMPOSITE = "COMPOSITE"
#: Table A.5's labels, by the category or tangible subgroup they price.
STRUCTURES = "Non-residential Structures"
SOFTWARE = "Acquired Software"
TANGIBLES = ("Air, Rail or Water Transport Vehicles", "Computer Hardware", "Equipment",
             "Industrial Machinery", "Road Transport Vehicles")
#: Inventories valued first in, first out (v = 1 of equation A.14): the published EMTR
#: designates it among the three values the annex allows, and the EATR checks it.
INVENTORY_VALUATION = 1.0
#: Fixed in M0 (R4) before any computation.
TOLERANCE = 0.1
MEASURES = ("EMTR", "EATR")


class EffectiveRateError(RuntimeError):
    """The annex or the OECD's data cannot be read as expected."""


@dataclass(frozen=True)
class Parameters:
    """The annex's fixed scenario and asset parameters, as printed."""

    profit: float
    """Pre-tax rate of return p (§ 8)."""
    real: float
    inflation: float
    nominal: float
    """Table A.2, scenario 1."""
    debt_share: float
    """The 35:65 split of § 18, debt first."""
    depreciation: dict[str, float]
    """Table A.5, by label."""


@dataclass(frozen=True)
class Rates:
    emtr: float
    eatr: float
    cost: float
    """In points: the EMTR and EATR in % of taxable income, the cost of capital in %."""


def _number(token: str) -> float:
    return float(token.replace(",", "."))


@lru_cache(maxsize=2)
def _pages(path: str) -> tuple[str, ...]:
    import pypdf

    return tuple((page.extract_text() or "").replace("\xa0", " ")
                 for page in pypdf.PdfReader(path).pages)


def _page_with(pages: tuple[str, ...], title: str) -> int:
    page = next((k for k, text in enumerate(pages) if title in text), None)
    if page is None:
        raise EffectiveRateError(f"« {title} » introuvable — l'annexe a changé ?")
    return page


def read_parameters(raw: Path | None = None) -> Parameters:
    path = (raw or RAW) / ANNEX_FILE
    if not path.exists():
        raise EffectiveRateError(f"{path} introuvable — téléchargez-le par le manifeste "
                                 f"(`impots data fetch {ANNEX_FILE}`)")
    if importlib.util.find_spec("pypdf") is None:
        raise EffectiveRateError("pypdf est requis pour lire l'annexe")
    pages = _pages(str(path))
    scenarios = pages[_page_with(pages, "Table A.2. Macroeconomic scenarios")]
    fixed = re.search(r"1 \(fixed across countries\)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
                      scenarios)
    profit = re.search(r"pre-tax rate of return is set to (\d+)%", "\n".join(pages))
    split = re.search(r"using a (\d+):(\d+) split", "\n".join(pages))
    if fixed is None or profit is None or split is None:
        raise EffectiveRateError("scénario fixe, rendement avant impôt ou partage dette et "
                                 "fonds propres introuvable dans l'annexe")
    start = _page_with(pages, "Table A.5. Economic Depreciation by Asset Category")
    table = " ".join(pages[start:start + 2])
    depreciation = {}
    for label in (STRUCTURES, *TANGIBLES, SOFTWARE):
        found = re.search(re.escape(label) + r"(?: \(Tangible Asset\))? (0\.\d+)", table)
        if found is None:
            raise EffectiveRateError(f"dépréciation « {label} » introuvable au tableau A.5")
        depreciation[label] = _number(found.group(1))
    inflation, real, nominal = (_number(g) / 100.0 for g in fixed.groups())
    if abs((1.0 + real) * (1.0 + inflation) - 1.0 - nominal) > 5e-5:
        raise EffectiveRateError(f"taux nominal {nominal} imprimé, Fisher donne "
                                 f"{(1 + real) * (1 + inflation) - 1:.5f} : le scénario fixe "
                                 f"est mal lu")
    debt, equity = (int(g) for g in split.groups())
    return Parameters(profit=_number(profit.group(1)) / 100.0, real=real,
                      inflation=inflation, nominal=nominal,
                      debt_share=debt / (debt + equity), depreciation=depreciation)


def read_published(raw: Path | None = None) -> dict[str, dict[str, float]]:
    """The OECD's rates for France in 2025, fixed scenario: measure → category → value, in
    points (the allowances in % of initial investment)."""
    path = (raw or RAW) / PUBLISHED_FILE
    if not path.exists():
        raise EffectiveRateError(f"{path} introuvable — téléchargez-le par le manifeste "
                                 f"(`impots data fetch {PUBLISHED_FILE}`)")
    out: dict[str, dict[str, float]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row.get("REF_AREA"), row.get("TIME_PERIOD"), row.get("ETR_SCENARIO")) != (
                    COUNTRY, YEAR, SCENARIO):
                continue
            out.setdefault(row["MEASURE"], {})[row["ETR_TAX_TYPE"]] = float(row["OBS_VALUE"])
    needed = {**{m: (*CATEGORIES, COMPOSITE) for m in MEASURES},
              "CAPITAL_ALLOWANCES": ("NRS", "TAN", "AWS")}
    missing = sorted(f"{m}/{c}" for m, cats in needed.items() for c in cats
                     if c not in out.get(m, {}))
    if missing:
        raise EffectiveRateError(f"{PUBLISHED_FILE} : {missing} absents pour {COUNTRY} "
                                 f"{YEAR}, scénario {SCENARIO}")
    return out


def statutory_rate(year: int) -> float:
    """The firm layer's rate: the normal rate, plus the social contribution on it."""
    from impots.entreprises import system

    law = system.baseline().parameters(f"{year}-01-01").impot_societes
    return float(law.taux_normal) * (1.0 + float(law.contribution_sociale.taux))


def rates(depreciation: float, allowance: float, *, params: Parameters, tau: float,
          valuation: float | None = None) -> Rates:
    """One asset's EMTR, EATR and cost of capital, debt and equity weighted by the annex's
    split. `allowance` is A of the annex, the present value of the allowances times the
    rate; `valuation` is v of equation A.14, for inventories only."""
    p, r, pi, i, d = (params.profit, params.real, params.inflation, params.nominal,
                      depreciation)
    weighted = {"emtr": 0.0, "eatr": 0.0, "cost": 0.0}
    for share, debt in ((params.debt_share, True), (1.0 - params.debt_share, False)):
        # A.6: the interest deduction on debt; retained earnings carry none (no ACE).
        financing = i * tau / ((r + d) * (1.0 + pi)) if debt else 0.0
        stock = valuation * tau * pi / (i - pi) if valuation is not None else 0.0
        profit = (p + d) * (1.0 - tau) / (r + d) + allowance - 1.0 - stock + financing
        cost = ((1.0 - allowance) * (r + d) / (1.0 - tau)
                + stock * (r + d) / (1.0 - tau) - financing * (r + d) / (1.0 - tau) - d)
        no_tax = (p - r) / (r + d)
        weighted["eatr"] += share * (no_tax - profit) / (p / (r + d))
        weighted["emtr"] += share * (cost - r) / r
        weighted["cost"] += share * cost
    return Rates(**{k: 100.0 * v for k, v in weighted.items()})


@dataclass(frozen=True)
class Line:
    category: str
    computed: Rates
    published: Rates

    def gap(self, measure: str) -> float:
        return getattr(self.computed, measure.lower()) - getattr(self.published,
                                                                 measure.lower())


@dataclass(frozen=True)
class Reproduction:
    lines: tuple[Line, ...]
    """The four categories, then the composite."""
    tau: float
    tolerance: float = TOLERANCE

    def line(self, category: str) -> Line:
        return next(x for x in self.lines if x.category == category)

    @property
    def failures(self) -> tuple[str, ...]:
        composite = self.line(COMPOSITE)
        return tuple(m for m in MEASURES if abs(composite.gap(m)) > self.tolerance)

    @property
    def passes(self) -> bool:
        return not self.failures

    def reason(self) -> str:
        if self.passes:
            return ""
        composite = self.line(COMPOSITE)
        missed = " et ".join(
            f"{'TMEI' if m == 'EMTR' else 'TMEE'} composite {_fr(getattr(composite.computed, m.lower()))} "
            f"contre {_fr(getattr(composite.published, m.lower()))} publié"
            for m in self.failures)
        return (f"méthode de l'OCDE, France 2025, scénario fixe : {missed}, au-delà de "
                f"{_fr(self.tolerance, 1)} point (M0, R4) ; les biens corporels n'ont qu'une "
                f"valeur d'amortissement publiée, moyenne de leurs cinq sous-groupes")


def _fr(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _published(published: dict[str, dict[str, float]], category: str) -> Rates:
    return Rates(emtr=published["EMTR"][category], eatr=published["EATR"][category],
                 cost=published.get("PBAR", {}).get(category, float("nan")))


def reproduce(params: Parameters, published: dict[str, dict[str, float]],
              tau: float) -> Reproduction:
    """Each category priced on the allowance the OECD publishes for it."""
    allowance = {c: published["CAPITAL_ALLOWANCES"][c] / 100.0 for c in ("NRS", "TAN", "AWS")}
    computed = {
        "NRS": rates(params.depreciation[STRUCTURES], allowance["NRS"], params=params,
                     tau=tau),
        "AWS": rates(params.depreciation[SOFTWARE], allowance["AWS"], params=params,
                     tau=tau),
        "INV": rates(0.0, 0.0, params=params, tau=tau, valuation=INVENTORY_VALUATION),
    }
    subgroups = [rates(params.depreciation[g], allowance["TAN"], params=params, tau=tau)
                 for g in TANGIBLES]
    computed["TAN"] = _average(subgroups)
    lines = [Line(c, computed[c], _published(published, c)) for c in CATEGORIES]
    lines.append(Line(COMPOSITE, _average([computed[c] for c in CATEGORIES]),
                      _published(published, COMPOSITE)))
    return Reproduction(lines=tuple(lines), tau=tau)


def _average(items: list[Rates]) -> Rates:
    return Rates(**{k: sum(getattr(x, k) for x in items) / len(items)
                    for k in ("emtr", "eatr", "cost")})


def heterogeneity(reproduction: Reproduction, params: Parameters) -> tuple[float, float]:
    """The tangibles' EMTR gap over their EATR gap, observed, and the ratio the formulas
    give when only the subgroups' allowances depart from their average: an allowance moves
    each subgroup's EMTR by (r + δ)/((1 − τ) r) and its EATR by (r + δ)/p, so whatever the
    allowances, the two gaps stand in the ratio p/((1 − τ) r)."""
    tangibles = reproduction.line("TAN")
    expected = params.profit / ((1.0 - reproduction.tau) * params.real)
    return tangibles.gap("EMTR") / tangibles.gap("EATR"), expected


def condition(raw: Path | None = None, year: int = int(YEAR)) -> Reproduction:
    """M0's condition on the national entry index, as it stands on the files."""
    return reproduce(read_parameters(raw), read_published(raw), statutory_rate(year))
