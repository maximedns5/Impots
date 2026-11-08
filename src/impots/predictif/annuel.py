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

THE θ BOX, AND THE FIRST YEAR CARRIED BESIDE IT (D-275). With behaviour or the loop, the
report gives Δb at its last year at θ and at every corner of the box — each row the
reform claims, and the multiplier when the loop runs, at 0 or 1 — in both views and under
each persistence. Twice: every year priced, and the first year alone carried as a share
of GDP, the explorer's convention, on the same pass. No pass more: the corners re-read
the passes already made. Δb at θ outside its corners says an effect is not monotone in
its θ, and the report is refused rather than drawn with a box that does not hold it.

A FIRM REFORM ALONE, BEHAVIOUR ASKED (D-273). Its passes carry no channel inputs, for
no household channel reads a firm knob, and say so (`Priced.behaviour_asked`, D-268):
such a year is priced, and the band and the θ line say why they are absent, as the
chain does for the first year. A pass without inputs that does not say it is still a
year without what was asked of it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from impots.dette.path import BANNER as DEBT_BANNER
from impots.dette.path import DebtError, SpendingScenario
from impots.dette.reference import Start
from impots.dette.scenarios import GrowthScenario, RateScenario
from impots.predictif import chaine, comportement, exploration, retroaction
from impots.predictif import theta as theta_module
from impots.predictif.exploration import MONOTONE_SLACK, Priced
from impots.predictif.theta import MACRO_ROW, Theta, ThetaError
from impots.uprating import Uprating

VIEWS = ("figee", "vieillie")


@dataclass(frozen=True)
class Layered:
    """A year's mechanical cost with its layers, when a firm reform is priced beside the
    households' (D-246). The layers sum to the cost, or the year is refused."""

    cost: float
    layers: dict[str, float]

    def __post_init__(self) -> None:
        if abs(sum(self.layers.values()) - self.cost) > max(1.0, 1e-9 * abs(self.cost)):
            raise DebtError(f"coût {self.cost:.0f} € qui n'est pas la somme de ses couches "
                            f"{self.layers} (PHASE11_SPEC §10)")


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
    layers: dict[str, dict[str, float]] | None = None
    """By view, the cost by layer, when a firm reform is priced (D-246); None otherwise."""


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


def _cost(one: float | Layered | Priced) -> float:
    return float(one.cost if isinstance(one, (Layered, Priced)) else one)


def _layers(one: float | Layered | Priced) -> dict[str, float] | None:
    layers = getattr(one, "layers", None)
    return dict(layers) if layers else None


def price_years(years: list[int],
                price: Callable[[int, str], float | Layered | Priced],
                basis_for: Callable[[int], str]) -> list[YearPrice]:
    """Each year in both views. `price(year, view)` is injected: the engine in the CLI, a
    stub in the tests, so the logic here is tested without an hour of passes. It returns
    a cost — with its layers when a firm reform is priced — or the whole pass when
    behaviour or the loop was asked for."""
    out = []
    for y in years:
        frozen, aged = price(y, "figee"), price(y, "vieillie")
        whole = isinstance(frozen, Priced) and isinstance(aged, Priced)
        if whole != (isinstance(frozen, Priced) or isinstance(aged, Priced)):
            raise DebtError(f"{y} : une vue chiffrée en entier et l'autre en coût seul")
        layers = {"figee": _layers(frozen), "vieillie": _layers(aged)}
        if (layers["figee"] is None) != (layers["vieillie"] is None):
            raise DebtError(f"{y} : une vue chiffrée par couche et l'autre non")
        out.append(YearPrice(
            year=y, basis=basis_for(y), frozen_eur=_cost(frozen), aged_eur=_cost(aged),
            passes={"figee": frozen, "vieillie": aged} if whole else None,
            layers=layers if layers["figee"] is not None else None))
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
    firm_note: str | None = None
    """The firm layer's conventions, when the reform has one (D-246)."""
    theta_box: dict[str, Any] | None = None
    """Δb at the last year at θ and at the box's corners, every year priced and the first
    year carried, by persistence and view (D-275); None without behaviour or the loop."""
    commit: str | None = None
    dirty: bool | None = None
    where: str | None = None
    """The code that priced the report, whether `src/` differed from it, and where the
    passes ran (D-275); None where the caller did not say."""
    annees: tuple[int, ...] = ()
    """The years the text applies the measure in, when it names them; the reform is
    empty the others (D-288). Empty, every year."""
    statistiques: dict[int, dict[str, Any]] | None = None
    """By year and view, what the chain read of each pass: the impulse by instrument,
    what it could not map, the receipts channels' sufficient statistics and the share of
    C1 at the floor (D-336, decision 6); None without behaviour or the loop."""
    rejeu: dict[str, Any] | None = None
    """What a replay reads besides them, once: the frame's numbers, the reference's
    rates and the marginal rate, the claimed rows with their bounds, the Mésange and IMK
    tables of the instruments the loop reads, the box's rows (`rejouer`)."""
    monte_carlo: dict[str, Any] | None = None
    """The distribution of Δb at the last year under declared laws, beside the box
    (D-336, decision 6, `montecarlo`); None without behaviour or the loop."""

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
            row = {
                "year": price.year, "basis": price.basis,
                "mechanical_frozen_eur": price.frozen_eur,
                "mechanical_aged_eur": price.aged_eur,
                "reference": lead.aged.reference[i],
                "reform_aged": None if side else lead.aged.reform[i],
                "delta_aged": None if side else lead.aged.delta[i],
                "reform_frozen": None if side else lead.frozen.reform[i],
                "delta_frozen": None if side else lead.frozen.delta[i],
            }
            # Only with a firm reform: a household report reads as it always did.
            if price.layers is not None:
                row["mechanical_by_layer"] = {v: dict(c) for v, c in price.layers.items()}
            # Only with behaviour or the loop: what a replay reads (D-336, decision 6).
            if self.statistiques is not None:
                row["statistiques"] = self.statistiques[price.year]
            rows.append(row)
        common = [c for c in lead.aged.conventions
                  if all(c in p.aged.conventions for p in self.paths)]
        extra: dict[str, Any] = {}
        if self.rejeu is not None:
            extra["rejeu"] = self.rejeu
        if self.monte_carlo is not None:
            extra["monte_carlo"] = self.monte_carlo
        return {
            **extra,
            "scenario": self.scenario, "titre": self.titre, "source": self.source,
            "reference": self.reference, "computed": self.computed,
            "spending_name": lead.aged.spending_name,
            "growth_name": lead.aged.growth_name, "rate_name": lead.aged.rate_name,
            "start": {"year": self.start.year, "debt_ratio": self.start.debt_ratio,
                      "primary_balance": self.start.primary_balance,
                      "implicit_rate": self.start.implicit_rate,
                      "gdp_eur": self.start.gdp_eur},
            "years": rows,
            "conventions": common + ([self.firm_note] if self.firm_note else [])
            + ([annees_note(self.annees)] if self.annees else []),
            "absent": dict(lead.aged.absent),
            "theta": dict(lead.aged.theta), "theta_applied": lead.aged.theta_applied,
            "closed": dict(lead.aged.closed),
            "uprating_note": self.uprating_note,
            "banner": lead.aged.banner, "debt_banner": DEBT_BANNER,
            "behavioural": self.behavioural, "macro": self.macro,
            "theta_box": self.theta_box,
            "commit": self.commit, "dirty": self.dirty, "where": self.where,
            "annees": list(self.annees) or None,
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
          store: Any = None, macro_store: Any = None,
          firm_note: str | None = None, commit: str | None = None,
          dirty: bool | None = None, where: str | None = None,
          annees: tuple[int, ...] = ()) -> Rapport:
    """The debt paths from the priced years. No carry: every year must be priced.

    With `behavioural` or `macro`, every year must carry its whole pass (`YearPrice.passes`)
    and `reform` the reform the channels claim knobs from. With a firm layer, `firm_note`
    names how it was priced, and is refused without one."""
    check_coherence(uprating, growth)
    if not prices:
        raise DebtError("aucune année chiffrée : un rapport sans chiffrage n'a rien à dire")
    layered = any(p.layers is not None for p in prices)
    if layered and not firm_note:
        raise DebtError("couche entreprises sans sa note : la vue vieillie et la vue figée "
                        "se liraient sans dire ce qu'elles chiffrent (D-246)")
    if firm_note and not layered:
        raise DebtError("note des entreprises sans couche entreprises : un rapport des "
                        "ménages dirait chiffrer ce qu'il ne chiffre pas")
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
        if looped and len(prices) > retroaction.max_horizon(macro_store) else [None])

    claimed_store = store if store is not None else comportement.load()

    def receipts_at(at: Theta, cost: float, one: Priced) -> comportement.AtTheta:
        """A corner's receipts, its box collapsed to them, as the explorer reads one."""
        receipts, grade = comportement.receipts_at(
            at, store=claimed_store, mechanical=-cost, reform=reform, **dict(one.inputs))
        return comportement.AtTheta(
            receipts=receipts, grade=grade, box=(receipts, receipts),
            claimed=comportement.claimed_open_rows(claimed_store, reform))

    def costs(view: str, at: Theta | None = None) -> chaine.ReformCosts:
        """The view's costs, the receipts at θ with their box; at `at`, a corner's."""
        attribute = "aged_eur" if view == "vieillie" else "frozen_eur"
        by_year = {p.year: getattr(p, attribute) for p in prices}
        if not whole:
            return chaine.ReformCosts(by_year=by_year)
        passes = {p.year: p.passes[view] for p in prices}
        # A firm reform alone: no household channel reads it, and its pass says so.
        unread = sorted(y for y, one in passes.items()
                        if behavioural and one.inputs is None
                        and getattr(one, "behaviour_asked", False))
        missing = sorted(y for y, one in passes.items()
                         if (behavioural and one.inputs is None and y not in unread)
                         or (macro and one.impulse is None))
        if missing:
            raise DebtError(
                f"vue « {view} » : les passes de {missing} n'ont pas ce qui était demandé "
                f"(entrées des canaux ou impulsion) — une année sans elles se lirait comme "
                f"une année sans comportement ou sans choc.")
        if unread and len(unread) != len(passes):
            raise DebtError(
                f"vue « {view} » : les années {unread} sont d'une réforme des seules "
                f"entreprises, que ne lit aucun canal des ménages, et les autres portent "
                f"les entrées des canaux. Une même réforme ne change pas de nature d'une "
                f"année à l'autre : la bande ne couvrirait qu'une partie du chemin.")
        if not behavioural or unread:
            behaviour = None
        elif at is None:
            behaviour = {y: comportement.evaluate(theta, mechanical=-by_year[y],
                                                  reform=reform, store=store,
                                                  **dict(one.inputs))
                         for y, one in passes.items()}
        else:
            behaviour = {y: receipts_at(at, by_year[y], one) for y, one in passes.items()}
        uncovered: dict[str, str] = {}
        for one in passes.values():
            uncovered.update(one.uncovered)
        return chaine.ReformCosts(
            by_year=by_year, behavioural=behaviour,
            impulses=({y: dict(one.impulse) for y, one in passes.items()} if macro
                      else None),
            uncovered=uncovered, behaviour_asked=bool(unread))

    central: dict[str, chaine.ReformCosts] = {}

    def at_theta(view: str) -> chaine.ReformCosts:
        """The view's costs at θ, evaluated once for every persistence and the replay."""
        if view not in central:
            central[view] = costs(view)
        return central[view]

    def path(view: str, persistence: str | None) -> chaine.Trajectoire:
        return chaine.run(start, horizon=len(prices), costs=at_theta(view), spending=spending,
                          growth=growth, rate=rate, theta=theta, securities=securities,
                          store=store, persistence=persistence, macro_store=macro_store)

    paths = tuple(Path(persistence=p, aged=path("vieillie", p), frozen=path("figee", p))
                  for p in persistences)
    at_corner: dict[tuple[Any, ...], chaine.ReformCosts] = {}

    def debt(at: Theta, view: str, persistence: str | None, carried: bool) -> float:
        """Δb at the last year at `at`: every year priced, or the first year carried."""
        if carried:
            return exploration.trajectory(
                at, prices[0].passes[view], reform, start=start, horizon=len(prices),
                spending=spending, growth=growth, rate=rate, store=claimed_store,
                macro_store=macro_store, persistence=persistence,
                securities=securities).delta[-1]
        # A corner's costs do not depend on the persistence: priced once per view.
        key = (view, tuple(sorted(at.rows.items())), at.common)
        if key not in at_corner:
            at_corner[key] = costs(view, at)
        return chaine.run(start, horizon=len(prices), costs=at_corner[key],
                          spending=spending, growth=growth, rate=rate, theta=at,
                          securities=securities, store=claimed_store,
                          persistence=persistence, macro_store=macro_store).delta[-1]

    box = None
    if whole:
        # A firm reform alone claims no household row: its households' reform is empty.
        keys = (list(comportement.claimed_open_rows(claimed_store, reform)) if behavioural
                else [])
        if macro and looped:
            keys.append(MACRO_ROW)
        if keys:
            box = _theta_box(keys, paths, year=prices[-1].year, theta=theta, debt=debt)
    statistiques = rejeu = monte = None
    if whole:
        statistiques = _statistics(prices, {v: at_theta(v) for v in VIEWS})
        rejeu = _replay_frame(
            start, prices, spending=spending, growth=growth, rate=rate,
            securities=securities, looped=looped, behavioural=behavioural,
            claimed=(comportement.claimed_open_rows(claimed_store, reform)
                     if behavioural else ()),
            store=claimed_store, macro_store=macro_store, statistiques=statistiques,
            box_rows=box["rows"] if box else [])
        if box:
            from impots.predictif import montecarlo

            monte = montecarlo.run({"years": [{"year": p.year, "basis": p.basis,
                                                "mechanical_frozen_eur": p.frozen_eur,
                                                "mechanical_aged_eur": p.aged_eur,
                                                "statistiques": statistiques[p.year]}
                                               for p in prices],
                                    "rejeu": rejeu})
    return Rapport(scenario=scenario, titre=titre, source=source, reference=reference,
                   computed=computed, start=start, prices=tuple(prices), paths=paths,
                   uprating_note=uprating_note, behavioural=behavioural, macro=macro,
                   firm_note=firm_note, theta_box=box, commit=commit, dirty=dirty,
                   where=where, annees=tuple(annees), statistiques=statistiques,
                   rejeu=rejeu, monte_carlo=monte)


def _start(start: Start) -> dict[str, Any]:
    return {"year": start.year, "debt_ratio": start.debt_ratio,
            "primary_balance": start.primary_balance, "implicit_rate": start.implicit_rate,
            "gdp_eur": start.gdp_eur, "receipts_ratio": start.receipts_ratio,
            "spending_ratio": start.spending_ratio}


def _statistics(prices: list[YearPrice],
                at_theta: dict[str, chaine.ReformCosts]) -> dict[int, dict[str, Any]]:
    """By year and view, what the chain read of each pass (D-336, decision 6)."""
    out: dict[int, dict[str, Any]] = {}
    for price in prices:
        out[price.year] = {}
        for view, costs in at_theta.items():
            one = price.passes[view]
            at = costs.behavioural[price.year] if costs.behavioural else None
            stats = dict(at.statistics or {}) if at is not None else None
            floor = stats.pop("c1_floor_share", None) if stats is not None else None
            out[price.year][view] = {
                "cost_eur": float(one.cost),
                "impulses": ({k: float(v) for k, v in one.impulse.items()}
                             if one.impulse is not None else None),
                "uncovered": dict(one.uncovered),
                "canaux": stats,
                "c1_floor_share": floor,
            }
    return out


def _replay_frame(start: Start, prices: list[YearPrice], *, spending: SpendingScenario,
                  growth: GrowthScenario, rate: RateScenario, securities: list[Any] | None,
                  looped: bool, behavioural: bool, claimed: tuple[str, ...], store: Any,
                  macro_store: Any, statistiques: dict[int, dict[str, Any]],
                  box_rows: list[str]) -> dict[str, Any]:
    """What `rejouer` reads besides the years' statistics: the frame's numbers, the
    reference's rates and the marginal rate, the claimed rows with their bounds and the
    file each comes from, and the tables of the instruments the loop reads."""
    from impots.dette.reference import reference_years
    from impots.predictif import montecarlo

    reference = reference_years(start, len(prices), spending=spending, growth=growth)
    rates, marginal, _ = chaine._rate_path(start, rate, reference, spending, growth,
                                           securities)
    files = montecarlo.row_files()
    lignes = {key: {"low": store[key].low, "central": store[key].central,
                    "high": store[key].high, "un": store[key].theta_one,
                    "loi": store[key].distribution, "fichier": files.get(key, key)}
              for key in claimed}
    macro: dict[str, Any] | None = None
    if looped:
        macro_store = macro_store if macro_store is not None else chaine_macro_store()
        instruments = sorted({i for year in statistiques.values() for view in year.values()
                              for i, v in (view["impulses"] or {}).items() if v})
        macro = retroaction.replay_tables(macro_store, instruments)
    return {
        "version": 1, "start": _start(start),
        "cadre": {"growth": {"real": growth.real, "prices": growth.prices},
                  "spending": {"rule": spending.rule, "growth": spending.growth},
                  "taux": {"kind": rate.kind, "market_rate": rate.market_rate,
                           "reference": list(rates), "marginal": marginal}},
        "looped": looped, "behavioural": behavioural, "lignes": lignes,
        "macro": macro, "box_rows": list(box_rows),
    }


def carried_payload(start: Start, priced: Any, reform: Any, *, spending: SpendingScenario,
                    growth: GrowthScenario, rate: RateScenario, theta: Theta, horizon: int,
                    store: Any = None, macro_store: Any = None,
                    securities: list[Any] | None = None) -> dict[str, Any]:
    """What `rejouer` reads of ONE first-year pass carried as a share of GDP (D-343): the
    year's cost, impulses and channel statistics, the frame, the claimed rows and the box
    rows — the convention of the plages and of `POST /predictif/simulate`, in the shape of
    an annual report's `years` and `rejeu`, one year long, with `carry` and `horizon`."""
    claimed_store = store if store is not None else comportement.load()
    first = start.year + 1
    behavioural = priced.inputs is not None
    at = (comportement.evaluate(theta, mechanical=-priced.cost, reform=reform,
                                store=claimed_store, **dict(priced.inputs))
          if behavioural else None)
    stats = dict(at.statistics or {}) if at is not None else None
    floor = stats.pop("c1_floor_share", None) if stats is not None else None
    statistiques = {first: {"vieillie": {
        "cost_eur": float(priced.cost),
        "impulses": ({k: float(v) for k, v in priced.impulse.items()}
                     if priced.impulse is not None else None),
        "uncovered": dict(priced.uncovered), "canaux": stats, "c1_floor_share": floor}}}
    looped = priced.impulse is not None and spending.rule == retroaction.SPENDING_RULE
    claimed = comportement.claimed_open_rows(claimed_store, reform) if behavioural else ()
    rejeu = _replay_frame(
        start, list(range(horizon)), spending=spending, growth=growth, rate=rate,
        securities=securities, looped=looped, behavioural=behavioural, claimed=claimed,
        store=claimed_store, macro_store=macro_store, statistiques=statistiques,
        box_rows=[*claimed, *([MACRO_ROW] if looped else [])])
    return {"carry": chaine.CARRY, "horizon": horizon,
            "years": [{"year": first, "mechanical_aged_eur": float(priced.cost),
                       "statistiques": statistiques[first]}],
            "rejeu": rejeu}


def chaine_macro_store() -> Any:
    from impots.macro import store as macro_store_module

    return macro_store_module.load()


def annees_note(annees: tuple[int, ...]) -> str:
    """The convention of a measure the text bounds to its years (D-288)."""
    years = ", ".join(str(y) for y in annees)
    return (f"La mesure ne s'applique qu'en {years}, les années que le texte nomme : les "
            f"autres années, la réforme est vide et ne coûte rien. La première année "
            f"seule reportée ne dit donc rien d'une mesure qui ne commence pas la "
            f"première année du chemin.")


def _theta_box(keys: list[str], paths: tuple[Path, ...], *, year: int, theta: Theta,
               debt: Callable[[Theta, str, str | None, bool], float]) -> dict[str, Any]:
    """Δb at the last year, at θ and at every corner of the box over `keys`, every year
    priced and the first year carried, by persistence and view. Every year priced, Δb at
    θ is the path the report draws; a value at θ outside its corners is refused."""
    corners = theta_module.corners(keys, theta)
    labels = [exploration.corner_label(corner, keys) for corner in corners]
    out = []
    for path in paths:
        readings: dict[str, dict[str, Any]] = {}
        for reading, carried in (("every_year", False), ("first_year", True)):
            readings[reading] = {}
            for view, drawn in (("vieillie", path.aged), ("figee", path.frozen)):
                at = (debt(theta, view, path.persistence, True) if carried
                      else drawn.delta[-1])
                values = [debt(corner, view, path.persistence, carried)
                          for corner in corners]
                if not min(values) - MONOTONE_SLACK <= at <= max(values) + MONOTONE_SLACK:
                    raise ThetaError(
                        f"vue « {view} », {reading}, persistance {path.persistence} : Δb "
                        f"{year} à θ ({at:+.5f}) sort de sa boîte "
                        f"[{min(values):+.5f} ; {max(values):+.5f}] — un effet n'est pas "
                        f"monotone en son θ, et relire la boîte à ses coins serait faux. "
                        f"Refusé plutôt que tracé.")
                readings[reading][view] = {
                    "theta": at, "corners": [[label, value] for label, value
                                             in zip(labels, values, strict=True)]}
        out.append({"persistence": path.persistence, **readings})
    return {"year": year, "rows": list(keys), "paths": out}
