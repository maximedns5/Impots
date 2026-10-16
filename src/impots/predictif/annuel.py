"""Phase 9 M1b — the full path, every year priced by the engine (the command, not the request).

`POST /predictif/simulate` prices one year and carries it as a share of GDP, because ten
years priced one by one take about an hour (M0, R3). This module is the other half: the
batch job that prices every year, twice — on the 2024 population as it is (« figée ») and
on the population aged to that year (« vieillie ») — and builds the debt path from each.
The command `impots predictif` writes the result as a report that the page reads; the API
never runs it.

THE AGED VIEW IS THE HEADLINE, the frozen one stands beside it, as in `trajectoires`: the
gap between them is the uprating class of uncertainty, measured rather than assumed.

ONE COHERENCE GUARD. The population is aged with a price index, and the debt path grows
GDP with the growth scenario's prices. If the two differed, the reform's euros and the
GDP they are divided by would inflate at different rates, and every ratio would drift by
the gap without a line saying so. `check_coherence` refuses that, and `uprating_for`
builds the uprating from the growth scenario so the CLI cannot get it wrong.

NO CARRY CONVENTION. Every year of the horizon is priced, so the chain is called without
one; a missing year is refused there, by the chain's own guard.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from impots.dette.path import BANNER as DEBT_BANNER
from impots.dette.path import DebtError, SpendingScenario
from impots.dette.reference import Start
from impots.dette.scenarios import GrowthScenario, RateScenario
from impots.predictif import chaine
from impots.uprating import Uprating

VIEWS = ("figee", "vieillie")


@dataclass(frozen=True)
class YearPrice:
    """One year as the engine priced it, in both views. Engine convention: COST POSITIVE."""

    year: int
    basis: str
    frozen_eur: float
    aged_eur: float


def uprating_for(growth: GrowthScenario, *, wage: float, source: str,
                 base_year: int) -> Uprating:
    """The population's uprating, its price index taken from the growth scenario."""
    return Uprating(wage=wage, price=growth.prices, source=source, base_year=base_year)


def check_coherence(uprating: Uprating, growth: GrowthScenario) -> None:
    if uprating.price != growth.prices:
        raise DebtError(
            f"la population vieillit avec des prix à {uprating.price:.2%} par an et le PIB "
            f"croît avec des prix à {growth.prices:.2%} : les euros de la réforme et le PIB "
            f"qui les divise gonfleraient à des rythmes différents, et chaque ratio "
            f"dériverait de l'écart sans le dire.")


def price_years(years: list[int], price: Callable[[int, str], float],
                basis_for: Callable[[int], str]) -> list[YearPrice]:
    """Each year in both views. `price(year, view)` is injected: the engine in the CLI, a
    stub in the tests, so the logic here is tested without an hour of passes."""
    return [YearPrice(year=y, basis=basis_for(y), frozen_eur=float(price(y, "figee")),
                      aged_eur=float(price(y, "vieillie"))) for y in years]


@dataclass(frozen=True)
class Rapport:
    """The full path in both views, and everything a reader needs to read it."""

    scenario: str
    titre: str
    source: str
    reference: str
    computed: str
    start: Start
    prices: tuple[YearPrice, ...]
    aged: chaine.Trajectoire
    frozen: chaine.Trajectoire
    uprating_note: str

    def payload(self) -> dict[str, Any]:
        rows = []
        for i, price in enumerate(self.prices):
            rows.append({
                "year": price.year, "basis": price.basis,
                "mechanical_frozen_eur": price.frozen_eur,
                "mechanical_aged_eur": price.aged_eur,
                "reference": self.aged.reference[i],
                "reform_aged": self.aged.reform[i], "delta_aged": self.aged.delta[i],
                "reform_frozen": self.frozen.reform[i],
                "delta_frozen": self.frozen.delta[i],
            })
        return {
            "scenario": self.scenario, "titre": self.titre, "source": self.source,
            "reference": self.reference, "computed": self.computed,
            "spending_name": self.aged.spending_name,
            "growth_name": self.aged.growth_name, "rate_name": self.aged.rate_name,
            "start": {"year": self.start.year, "debt_ratio": self.start.debt_ratio,
                      "primary_balance": self.start.primary_balance,
                      "implicit_rate": self.start.implicit_rate,
                      "gdp_eur": self.start.gdp_eur},
            "years": rows,
            "conventions": list(self.aged.conventions),
            "absent": dict(self.aged.absent),
            "uprating_note": self.uprating_note,
            "banner": self.aged.banner, "debt_banner": DEBT_BANNER,
        }


def build(start: Start, prices: list[YearPrice], *, scenario: str, titre: str,
          source: str, reference: str, computed: str, spending: SpendingScenario,
          growth: GrowthScenario, rate: RateScenario, uprating: Uprating,
          uprating_note: str, securities: list[Any] | None = None) -> Rapport:
    """Both debt paths from the priced years. No carry: every year must be priced."""
    check_coherence(uprating, growth)
    if not prices:
        raise DebtError("aucune année chiffrée : un rapport sans chiffrage n'a rien à dire")

    def path(attribute: str) -> chaine.Trajectoire:
        costs = chaine.ReformCosts(by_year={p.year: getattr(p, attribute) for p in prices})
        return chaine.run(start, horizon=len(prices), costs=costs, spending=spending,
                          growth=growth, rate=rate, securities=securities)

    return Rapport(scenario=scenario, titre=titre, source=source, reference=reference,
                   computed=computed, start=start, prices=tuple(prices),
                   aged=path("aged_eur"), frozen=path("frozen_eur"),
                   uprating_note=uprating_note)
