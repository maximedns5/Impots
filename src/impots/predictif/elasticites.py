"""Phase 11 M2 — the elasticity loop for the IS, and the cross-check that refuses it (D-246).

Mésange has no IS variant (D-214), so the GDP → receipts loop of `retroaction` cannot be
read for a corporate-tax reform. PHASE11_SPEC §4 named a candidate: the European
Commission's cycle elasticities, receipt by receipt (Mourre, Poissonnier and Lausegger,
European Economy Discussion Paper 098, 2019). It would enter on one condition: applied
to the variants where Mésange prints its balance, it must « redonner la boucle de
Mésange », at a tolerance fixed before computing it. M0 of Phase 11 (R2, D-245) fixed
it: a quarter of Mésange's own ratio, for each variant the spec names, at each of the
horizons 1, 2 and 3. This module reads the Commission's France rows out of the PDF,
computes both readings of the loop, and runs that cross-check.

TWO READINGS OF THE LOOP, and the question left open. In euros over GDP the loop is the
receipts' elasticity times their weight plus the unemployment spending's, 0,585 per
point of GDP gap. The semi-elasticity of the balance ratio, 0,630, adds the denominator's
effect on a deficit of 4,51 points. Mésange's balance row is in points of GDP — a ratio —
so the like-for-like figure would be 0,630; the spec and M0's first version argued
0,585. The verdict does not depend on the choice, so the cross-check runs both, and the
loop passes only if every variant at every horizon falls within the tolerance under ONE
of them.

THE VERDICT, AS IT STANDS. The elasticity loop gives one ratio for every instrument;
Mésange prints one per instrument. For the employer contributions it prints 1,40, 1,05
and 0,96 at one, two and three years, 34 to 58 % away from either reading. The loop is
refused, and the IS's loop stays absent, said so. Two guards hold it (§10, 5 and 6): the
loop is never asked for an instrument Mésange covers — Mésange comes first where it
prints — and never given without its cross-check passing.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from impots.macro import mesange
from impots.macro.fan import _require
from impots.macro.store import Store
from impots.predictif import retroaction

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
SOURCE_FILE = "ec_dp098_2019_semi_elasticities_budget_balance.pdf"
COUNTRY = "FR"
TABLES = {"elasticities": "Table I.1. Elasticities",
          "shares": "Table I.2. Updated shares",
          "decomposition": "Decomposition of the semi-elasticity"}
#: Table I.1's and I.2's columns, (A) to (G) and (H) to (N), in the order printed.
ITEMS = ("impot_revenu", "impot_societes", "cotisations_sociales", "impots_indirects",
         "recettes_non_fiscales", "chomage", "autres_depenses")
REVENUES = ITEMS[:5]
SPENDING = ITEMS[5:]
#: Table I.3's columns: (a), (b), c = a − 1, d = b − 1, (e), (f), g = c·e, h = d·f, i = g − h.
DECOMPOSITION = ("a", "b", "c", "d", "e", "f", "g", "h", "i")

#: The variants PHASE11_SPEC §4 names for the cross-check: IR, CSG, contributions, VAT.
#: The carbon tax is out, as D-218 puts it out of the loop: its gap is not activity.
VARIANTS = ("impot_sur_le_revenu", "csg", "cotisations_salaries",
            "cotisations_employeurs", "tva")
HORIZONS = ("1", "2", "3")
#: Fixed in M0 (R2, D-245) before any computation: a quarter of Mésange's own ratio.
TOLERANCE = 0.25
EUROS, RATIO = "euros", "ratio"
#: How closely the authors' formulas must give back their own Table I.3 from Tables I.1
#: and I.2: the printed cells carry two decimals, the semi-elasticities three.
READ_SLACK = 0.006


class ElasticityError(RuntimeError):
    """The working paper cannot be read as expected."""


class ElasticityLoopRefused(ValueError):
    """The elasticity loop was asked for where it may not stand (§10, guards 5 and 6)."""


@dataclass(frozen=True)
class Reading:
    elasticities: dict[str, float]
    """Table I.1, France, by item of `ITEMS`."""
    shares: dict[str, float]
    """Table I.2, France, in % of total revenue (the first five) or expenditure."""
    decomposition: dict[str, float]
    """Table I.3, France, by column of `DECOMPOSITION`; weights in % of GDP."""
    pages: dict[str, int]
    """1-based PDF page of each table."""


def _number(token: str) -> float:
    return float(token.replace(",", "."))


@lru_cache(maxsize=2)
def _pages(path: str) -> tuple[str, ...]:
    import pypdf

    return tuple((page.extract_text() or "").replace("\xa0", " ")
                 for page in pypdf.PdfReader(path).pages)


def _country_row(text: str, width: int) -> list[float]:
    for line in text.splitlines():
        tokens = line.split()
        if tokens and tokens[0] == COUNTRY:
            if len(tokens) - 1 != width:
                raise ElasticityError(f"ligne {COUNTRY} : {len(tokens) - 1} cellules, "
                                      f"{width} attendues")
            return [_number(t) for t in tokens[1:]]
    raise ElasticityError(f"ligne {COUNTRY} introuvable")


def load(raw: Path | None = None) -> Reading:
    path = (raw or RAW) / SOURCE_FILE
    if not path.exists():
        raise ElasticityError(f"{path} introuvable — téléchargez-le par le manifeste "
                              f"(`impots data fetch {SOURCE_FILE}`)")
    if importlib.util.find_spec("pypdf") is None:  # pragma: no cover - environment
        raise ElasticityError("pypdf est requis pour lire le document")
    pages = _pages(str(path))
    found = {}
    for name, title in TABLES.items():
        # The list of tables carries the titles too: the table is the page that also
        # prints a France row.
        page = next((k for k, text in enumerate(pages) if title in text
                     and any(line.split()[:1] == [COUNTRY] for line in text.splitlines())),
                    None)
        if page is None:
            raise ElasticityError(f"« {title} » introuvable — le document a changé ?")
        found[name] = page
    reading = Reading(
        elasticities=dict(zip(ITEMS, _country_row(pages[found["elasticities"]],
                                                  len(ITEMS)), strict=True)),
        shares=dict(zip(ITEMS, _country_row(pages[found["shares"]], len(ITEMS)),
                        strict=True)),
        decomposition=dict(zip(DECOMPOSITION,
                               _country_row(pages[found["decomposition"]],
                                            len(DECOMPOSITION)), strict=True)),
        pages={name: page + 1 for name, page in found.items()})
    check(reading)
    return reading


def aggregates(reading: Reading) -> tuple[float, float]:
    """(a) and (b) by the authors' own formulas under Table I.3, from Tables I.1-I.2."""
    e, s = reading.elasticities, reading.shares
    return (sum(e[i] * s[i] for i in REVENUES) / 100.0,
            sum(e[i] * s[i] for i in SPENDING) / 100.0)


def check(reading: Reading) -> None:
    """GUARD on the reading: the three tables must agree as the authors say they do. A
    row read from another country, or a column shifted, stops here."""
    a, b = aggregates(reading)
    d = reading.decomposition
    for name, computed, printed in (("a", a, d["a"]), ("b", b, d["b"]),
                                    ("i", d["g"] - d["h"], d["i"])):
        if abs(computed - printed) > READ_SLACK:
            raise ElasticityError(f"({name}) recalculée {computed:.4f}, imprimée "
                                  f"{printed} : les tableaux I.1 à I.3 ne se recoupent pas")
    if abs(sum(reading.shares[i] for i in REVENUES) - 100.0) > 0.05:
        raise ElasticityError("les parts des recettes ne font pas 100 %")


def loop_shares(reading: Reading) -> dict[str, float]:
    """The loop per point of GDP gap, in points of GDP, under both readings: in euros
    over GDP (receipts and unemployment spending), and as the balance-ratio
    semi-elasticity the authors print."""
    a, b = aggregates(reading)
    e = reading.decomposition["e"] / 100.0
    f = reading.decomposition["f"] / 100.0
    return {EUROS: a * e - b * f, RATIO: reading.decomposition["i"]}


def mesange_ratio(store: Store, instrument: str, horizon: str) -> float:
    """φ/y of Mésange: the feedback on the balance per point of GDP the variant moves,
    against the gross cost the chain counts, as `retroaction` reads it."""
    multipliers = _require(store, "multiplier_by_instrument")
    balance = _require(store, retroaction.BALANCE_TABLE)
    gross = mesange.VARIANTS[instrument].ex_ante_points
    return (balance.at(instrument, horizon) + gross) / multipliers.at(instrument, horizon)


@dataclass(frozen=True)
class Row:
    instrument: str
    horizon: str
    mesange: float
    gaps: dict[str, float]
    """By reading: the loop over Mésange's ratio, minus one."""


@dataclass(frozen=True)
class Verdict:
    rows: tuple[Row, ...]
    shares: dict[str, float]
    tolerance: float

    def failures(self, reading: str) -> tuple[Row, ...]:
        return tuple(r for r in self.rows if abs(r.gaps[reading]) > self.tolerance)

    @property
    def passing(self) -> tuple[str, ...]:
        """The readings under which every variant at every horizon is within tolerance."""
        return tuple(k for k in self.shares if not self.failures(k))

    @property
    def passes(self) -> bool:
        return bool(self.passing)

    def reason(self) -> str:
        if self.passes:
            return ""
        worst = []
        for reading in self.shares:
            rows = self.failures(reading)
            named = ", ".join(f"{r.instrument} à {r.horizon} an(s) "
                              f"({100 * r.gaps[reading]:+.0f} %)" for r in rows)
            worst.append(f"lecture « {reading} » ({self.shares[reading]:.3f}".replace(".", ",")
                         + f") : {named}")
        return ("boucle par élasticités (CE, DP 098) refusée : appliquée aux variantes où "
                "Mésange imprime son solde, elle ne redonne pas sa boucle à "
                f"{100 * self.tolerance:.0f} % près (PHASE11_SPEC §4, M0 R2) — "
                + " ; ".join(worst))


def cross_check(reading: Reading, store: Store, *, variants: Iterable[str] = VARIANTS,
                horizons: Iterable[str] = HORIZONS,
                tolerance: float = TOLERANCE) -> Verdict:
    """§10, guard 6: the loop against Mésange, variant by variant, horizon by horizon."""
    shares = loop_shares(reading)
    rows = []
    for instrument in variants:
        for horizon in horizons:
            ratio = mesange_ratio(store, instrument, horizon)
            rows.append(Row(instrument=instrument, horizon=horizon, mesange=ratio,
                            gaps={k: v / ratio - 1.0 for k, v in shares.items()}))
    return Verdict(rows=tuple(rows), shares=shares, tolerance=tolerance)


def covered_by_mesange(store: Store, instrument: str) -> bool:
    return (retroaction.is_fiscal(instrument)
            and instrument in _require(store, retroaction.BALANCE_TABLE).values)


def elasticity_loop(instrument: str, *, reading: Reading, store: Store,
                    verdict: Verdict | None = None) -> Mapping[str, float]:
    """The loop's share for `instrument`, or a refusal (§10, guards 5 and 6).

    Never for an instrument Mésange prints a balance row for: there Mésange comes first,
    and the elasticity loop does not stand in for it. And never without the cross-check
    passing; the shares it returns are the readings under which it passed."""
    if covered_by_mesange(store, instrument):
        raise ElasticityLoopRefused(
            f"Mésange imprime sa ligne de solde pour « {instrument} » : elle prime, et la "
            f"boucle par élasticités ne s'y substitue pas (PHASE11_SPEC §10, garde 5)")
    verdict = verdict if verdict is not None else cross_check(reading, store)
    if not verdict.passes:
        raise ElasticityLoopRefused(verdict.reason())
    return {k: verdict.shares[k] for k in verdict.passing}
