"""Phase 9 M6 §8 — what the explorer reads for `dette_conditionnelle` (D-224).

The explorer of Phase 8 searches a grid of knob bundles and asks an evaluator for each.
This module builds that evaluator for the conditional debt: for one bundle, Δb_T — the
reform's debt ratio minus the reference's at year T — at the θ the request fixed, under its
named scenarios, in BOTH views, and at every corner of the θ box.

WHERE THE NUMBERS COME FROM. `price(knobs, view)` is the caller's: one population pass of
the first projected year, on the population aged to that year (« vieillie », the headline)
or as it is (« figee »), with what the behavioural channels read and the reform's macro
impulse when those were asked for. The path is the fast version's: the first year priced,
the rest carried as a share of GDP (`chaine.CARRY`), a convention the result names.

THE θ BOX. Its keys are the open rows the bundle's knobs claim — read only when behaviour
was priced — and the multiplier's θ when the GDP → receipts loop applies, that is with an
impulse under « gele_en_volume » (D-218). The corners move those keys to 0 and 1 and leave
every other row at the θ asked for (`theta.corners`). At θ and at each corner the receipts
are read directly (`comportement.receipts_at`), and the chain's central path gives Δb_T:
the corners ARE the box, so the receipts' own box is not recomputed at each of them.
Reading the box at its corners assumes each effect monotone in its θ; Δb_T at θ outside
the corners' range would say it is not, and is refused rather than read.

NO BAND. At a fixed θ the path is a number; its spread is the θ box, read through
« robuste » or « dépend de θ ». The evaluation says so in place of a band, so that the
explorer's « fragile » flag is not raised, nor its absence mistaken for a measurement.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from impots.behavioural.store import Store
from impots.behavioural.store import load as load_store
from impots.dette.path import DebtError, SpendingScenario
from impots.dette.reference import Start
from impots.dette.scenarios import GrowthScenario, RateScenario
from impots.explorer import Evaluation
from impots.predictif import chaine, comportement, retroaction
from impots.predictif import theta as theta_module
from impots.predictif.theta import MACRO_ROW, Theta, ThetaError

VIEWS = ("vieillie", "figee")

NO_BAND = ("à θ fixé, la trajectoire est un nombre : sa dispersion est la boîte θ, relue "
           "aux coins (« robuste » ou « dépend de θ »)")
NO_KEY = "θ tel que demandé : aucune ligne ni boucle ne déplace ce paquet"

#: Slack for the monotonicity check, in points of GDP: float noise only.
MONOTONE_SLACK = 1e-9


@dataclass(frozen=True)
class Priced:
    """One view of one bundle's first projected year, as the population pass priced it."""

    cost: float
    """The engine's cost, COST POSITIVE."""
    inputs: Mapping[str, Any] | None = None
    """What `band.compute` reads, when behaviour was priced; None for the mechanical view."""
    impulse: Mapping[str, float] | None = None
    """The macro impulse by Mésange variant, EXPANSIONARY-POSITIVE, when the loop is asked."""
    uncovered: Mapping[str, str] = field(default_factory=dict)
    deciles: Sequence[Any] | None = None
    """The pass's decile rows, which the §7 indices read; None when not kept."""


def trajectory(at: Theta, priced: Priced, reform: Any, *, start: Start, horizon: int,
               spending: SpendingScenario, growth: GrowthScenario, rate: RateScenario,
               store: Store, macro_store: Any = None, persistence: str | None = None,
               securities: list[Any] | None = None) -> Any:
    """The chain's path for one view of one bundle at `at`: the first year priced, the
    rest carried. The evaluator reads Δb_T off it; the search, the §7 indices."""
    first = start.year + 1
    behaviour = None
    if priced.inputs is not None:
        receipts, grade = comportement.receipts_at(
            at, store=store, mechanical=-priced.cost, reform=reform, **priced.inputs)
        behaviour = {first: comportement.AtTheta(
            receipts=receipts, grade=grade, box=(receipts, receipts),
            claimed=comportement.claimed_open_rows(store, reform))}
    costs = chaine.ReformCosts(
        by_year={first: priced.cost}, carry=chaine.CARRY, behavioural=behaviour,
        impulses=({first: dict(priced.impulse)} if priced.impulse is not None else None),
        uncovered=dict(priced.uncovered))
    return chaine.run(start, horizon=horizon, costs=costs, spending=spending,
                      growth=growth, rate=rate, theta=at, securities=securities,
                      store=store, persistence=persistence, macro_store=macro_store)


def corner_label(corner: Theta, keys: list[str]) -> str:
    if not keys:
        return NO_KEY
    return ", ".join(f"{key} = {corner.for_row(key):g}" for key in keys)


def conditional_debt(*, price: Callable[[dict[str, float], str], Priced],
                     reform_of: Callable[[dict[str, float]], Any], start: Start,
                     horizon: int, spending: SpendingScenario, growth: GrowthScenario,
                     rate: RateScenario, theta: Theta, year: int | None = None,
                     store: Store | None = None, macro_store: Any = None,
                     persistence: str | None = None, securities: list[Any] | None = None,
                     ) -> Callable[[dict[str, float]], Evaluation]:
    """The explorer's evaluator for `dette_conditionnelle`: Δb at `year` (the horizon's
    last by default), a share of GDP, negative when the reform lowers the debt."""
    store = store if store is not None else load_store()
    theta.check_known(store)
    first = start.year + 1
    last = first + horizon - 1
    target = last if year is None else year
    if not first <= target <= last:
        raise DebtError(f"année cible {target} hors de l'horizon {first}–{last}")
    looped = spending.rule == retroaction.SPENDING_RULE

    def delta(at: Theta, priced: Priced, reform: Any) -> float:
        result = trajectory(at, priced, reform, start=start, horizon=horizon,
                            spending=spending, growth=growth, rate=rate, store=store,
                            macro_store=macro_store, persistence=persistence,
                            securities=securities)
        return result.delta[result.years.index(target)]

    def evaluate(knobs: dict[str, float]) -> Evaluation:
        reform = reform_of(knobs)
        aged, frozen = (price(knobs, view) for view in VIEWS)
        keys = (list(comportement.claimed_open_rows(store, reform))
                if aged.inputs is not None else [])
        if aged.impulse is not None and looped:
            keys.append(MACRO_ROW)
        at_theta = delta(theta, aged, reform)
        corners = tuple((corner_label(corner, keys), delta(corner, aged, reform))
                        for corner in theta_module.corners(keys, theta))
        low = min(v for _, v in corners)
        high = max(v for _, v in corners)
        if not low - MONOTONE_SLACK <= at_theta <= high + MONOTONE_SLACK:
            raise ThetaError(
                f"paquet {knobs} : l'écart de dette à θ ({at_theta:+.5f}) sort des coins "
                f"[{low:+.5f} ; {high:+.5f}] — un effet n'est pas monotone en son θ, et "
                f"relire la boîte à ses coins serait faux. Refusé plutôt que classé.")
        return Evaluation(aged_eur=at_theta, frozen_eur=delta(theta, frozen, reform),
                          band=None, band_reason=NO_BAND, corners=corners)

    return evaluate
