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

THE MECHANICAL VIEW, θ NAMED (D-217). Without behaviour the report lists the θ it was
given, with the chain's statement that nothing reads them, rather than leaving the reader
to wonder at which θ the path was drawn.

BEHAVIOUR AND THE LOOP, YEAR BY YEAR (PHASE10_SPEC §4, D-236). Asked for, each year's pass
carries what the channels read and the reform's macro impulse that year
(`exploration.Priced`). The receipts at θ and their box are evaluated year by year, and
the chain reads one impulse per year — Mésange's shocks superposed, no carry convention.
Past three years with the loop and no persistence named, both persistence scenarios are
drawn side by side from the same passes, neither in the lead (D-230). A year priced
without what was asked of it is refused, never read as a year without behaviour or
without a shock.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from impots.dette.path import BANNER as DEBT_BANNER
from impots.dette.path import DebtError, SpendingScenario
from impots.dette.reference import Start
from impots.dette.scenarios import GrowthScenario, RateScenario
from impots.predictif import chaine, comportement, retroaction
from impots.predictif.exploration import Priced
from impots.predictif.theta import Theta
from impots.uprating import Uprating

VIEWS = ("figee", "vieillie")


@dataclass(frozen=True)
class YearPrice:
    """One year as the engine priced it, in both views. Engine convention: COST POSITIVE."""

    year: int
    basis: str
    frozen_eur: float
    aged_eur: float
    passes: dict[str, Priced] | None = None
    """Each view's whole pass — what the channels read, the impulse — when the command
    asked for behaviour or the loop; None for the mechanical path."""


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


def price_years(years: list[int], price: Callable[[int, str], float | Priced],
                basis_for: Callable[[int], str]) -> list[YearPrice]:
    """Each year in both views. `price(year, view)` is injected: the engine in the CLI, a
    stub in the tests, so the logic here is tested without an hour of passes. It returns
    a cost, or the whole pass when behaviour or the loop was asked for."""
    out = []
    for y in years:
        frozen, aged = price(y, "figee"), price(y, "vieillie")
        whole = isinstance(frozen, Priced) and isinstance(aged, Priced)
        if whole != (isinstance(frozen, Priced) or isinstance(aged, Priced)):
            raise DebtError(f"{y} : une vue chiffrée en entier et l'autre en coût seul")
        out.append(YearPrice(
            year=y, basis=basis_for(y),
            frozen_eur=float(frozen.cost if whole else frozen),
            aged_eur=float(aged.cost if whole else aged),
            passes={"figee": frozen, "vieillie": aged} if whole else None))
    return out


@dataclass(frozen=True)
class Path:
    """One persistence scenario's paths, in both views (D-230)."""

    persistence: str | None
    aged: chaine.Trajectoire
    frozen: chaine.Trajectoire

    @property
    def label(self) -> str | None:
        return (retroaction.PERSISTENCE_LABELS[self.persistence]
                if self.persistence is not None else None)


@dataclass(frozen=True)
class Rapport:
    """The full path in both views, and everything a reader needs to read it. One path,
    or the two persistence scenarios side by side, neither in the lead."""

    scenario: str
    titre: str
    source: str
    reference: str
    computed: str
    start: Start
    prices: tuple[YearPrice, ...]
    paths: tuple[Path, ...]
    uprating_note: str
    behavioural: bool = False
    macro: bool = False

    @property
    def aged(self) -> chaine.Trajectoire:
        """The aged path, when there is one only: two side by side have no lead."""
        if len(self.paths) != 1:
            raise DebtError("deux scénarios de persistance côte à côte : aucun n'est le "
                            "chemin de tête (D-230)")
        return self.paths[0].aged

    @property
    def frozen(self) -> chaine.Trajectoire:
        if len(self.paths) != 1:
            raise DebtError("deux scénarios de persistance côte à côte : aucun n'est le "
                            "chemin de tête (D-230)")
        return self.paths[0].frozen

    def payload(self) -> dict[str, Any]:
        side = len(self.paths) > 1
        lead = self.paths[0]
        rows = []
        for i, price in enumerate(self.prices):
            rows.append({
                "year": price.year, "basis": price.basis,
                "mechanical_frozen_eur": price.frozen_eur,
                "mechanical_aged_eur": price.aged_eur,
                "reference": lead.aged.reference[i],
                "reform_aged": None if side else lead.aged.reform[i],
                "delta_aged": None if side else lead.aged.delta[i],
                "reform_frozen": None if side else lead.frozen.reform[i],
                "delta_frozen": None if side else lead.frozen.delta[i],
            })
        common = [c for c in lead.aged.conventions
                  if all(c in p.aged.conventions for p in self.paths)]
        return {
            "scenario": self.scenario, "titre": self.titre, "source": self.source,
            "reference": self.reference, "computed": self.computed,
            "spending_name": lead.aged.spending_name,
            "growth_name": lead.aged.growth_name, "rate_name": lead.aged.rate_name,
            "start": {"year": self.start.year, "debt_ratio": self.start.debt_ratio,
                      "primary_balance": self.start.primary_balance,
                      "implicit_rate": self.start.implicit_rate,
                      "gdp_eur": self.start.gdp_eur},
            "years": rows,
            "conventions": common,
            "absent": dict(lead.aged.absent),
            "theta": dict(lead.aged.theta), "theta_applied": lead.aged.theta_applied,
            "closed": dict(lead.aged.closed),
            "uprating_note": self.uprating_note,
            "banner": lead.aged.banner, "debt_banner": DEBT_BANNER,
            "behavioural": self.behavioural, "macro": self.macro,
            "persistence": None if side else lead.aged.persistence,
            "side_by_side": [{
                "persistence": p.persistence, "label": p.label,
                "years": [{"year": price.year, "reform_aged": p.aged.reform[i],
                           "delta_aged": p.aged.delta[i],
                           "reform_frozen": p.frozen.reform[i],
                           "delta_frozen": p.frozen.delta[i]}
                          for i, price in enumerate(self.prices)],
                "conventions": [c for c in p.aged.conventions if c not in common],
                "gdp_gap_aged": list(p.aged.gdp_gap or ()),
            } for p in self.paths] if side else [],
        }


def build(start: Start, prices: list[YearPrice], *, scenario: str, titre: str,
          source: str, reference: str, computed: str, spending: SpendingScenario,
          growth: GrowthScenario, rate: RateScenario, theta: Theta | None,
          uprating: Uprating, uprating_note: str,
          securities: list[Any] | None = None, reform: Any = None,
          behavioural: bool = False, macro: bool = False, persistence: str | None = None,
          store: Any = None, macro_store: Any = None) -> Rapport:
    """The debt paths from the priced years. No carry: every year must be priced.

    With `behavioural` or `macro`, every year must carry its whole pass (`YearPrice.passes`)
    and `reform` the reform the channels claim knobs from."""
    check_coherence(uprating, growth)
    if not prices:
        raise DebtError("aucune année chiffrée : un rapport sans chiffrage n'a rien à dire")
    whole = behavioural or macro
    if whole:
        bare = [p.year for p in prices if p.passes is None]
        if bare:
            raise DebtError(
                f"comportement ou boucle demandés, et les années {bare} n'ont que leur coût :"
                f" elles se liraient comme des années sans comportement ni choc.")
        if theta is None:
            raise DebtError("comportement ou boucle sans θ : aucun défaut (D-217)")
    looped = macro and spending.rule == retroaction.SPENDING_RULE
    persistences: list[str | None] = (
        [persistence] if persistence is not None
        else list(retroaction.PERSISTENCE_LABELS)
        if looped and len(prices) > retroaction.MAX_HORIZON else [None])

    def costs(view: str) -> chaine.ReformCosts:
        attribute = "aged_eur" if view == "vieillie" else "frozen_eur"
        by_year = {p.year: getattr(p, attribute) for p in prices}
        if not whole:
            return chaine.ReformCosts(by_year=by_year)
        passes = {p.year: p.passes[view] for p in prices}
        missing = sorted(y for y, one in passes.items()
                         if (behavioural and one.inputs is None)
                         or (macro and one.impulse is None))
        if missing:
            raise DebtError(
                f"vue « {view} » : les passes de {missing} n'ont pas ce qui était demandé "
                f"(entrées des canaux ou impulsion) — une année sans elles se lirait comme "
                f"une année sans comportement ou sans choc.")
        at = ({y: comportement.evaluate(theta, mechanical=-by_year[y], reform=reform,
                                        store=store, **dict(one.inputs))
               for y, one in passes.items()} if behavioural else None)
        uncovered: dict[str, str] = {}
        for one in passes.values():
            uncovered.update(one.uncovered)
        return chaine.ReformCosts(
            by_year=by_year, behavioural=at,
            impulses=({y: dict(one.impulse) for y, one in passes.items()} if macro
                      else None),
            uncovered=uncovered)

    def path(view: str, persistence: str | None) -> chaine.Trajectoire:
        return chaine.run(start, horizon=len(prices), costs=costs(view), spending=spending,
                          growth=growth, rate=rate, theta=theta, securities=securities,
                          store=store, persistence=persistence, macro_store=macro_store)

    return Rapport(scenario=scenario, titre=titre, source=source, reference=reference,
                   computed=computed, start=start, prices=tuple(prices),
                   paths=tuple(Path(persistence=p, aged=path("vieillie", p),
                                    frozen=path("figee", p)) for p in persistences),
                   uprating_note=uprating_note, behavioural=behavioural, macro=macro)
