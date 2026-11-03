"""Phase 7 A0 v2 — attributing the behavioural band's WIDTH to individual parameters.

A0 v1 left the behavioural store UNMEASURED with a stated reason: attributing it per
parameter needs the household arrays that only a full-tier engine pass produces, and the
cost is **one pass per case, not per draw**. This module pays that cost once, then does the
attribution entirely inside the Monte Carlo, which is cheap.

WHAT IS ATTRIBUTED, AND WHY IT IS A WIDTH RATHER THAN A VARIANCE.

The first draft of this module attributed *variance*, reading the per-channel draws off the
result. **`BehaviouralResult` does not expose them.** It carries `band` as three percentiles
and `channels` as dicts of three percentiles each; the draw arrays are local to `compute`
and die with it. Summing per-channel percentiles is not a thing one may do — percentiles do
not add — so a variance decomposition is not available through the public API, and reaching
into the channel internals to fake one would make the attribution depend on private shape.

So the attributed quantity is **the width of the published band, p90 − p10**. That is a
deliberate choice with two things to recommend it: it is available honestly, and it is the
number a reader of a fiche actually sees. It is NOT a variance decomposition and this module
never calls it one — the contributions are width reductions, they are not required to sum,
and the gap is reported.

THE COMPARISON IS REFUSED WHEN THE GRADE MOVES, and that guard is the point of the design.
`compute` applies `grading.widen` to the draws before the band is taken: a channel graded
*illustrative* has its band stretched about its median by a factor of two. If pinning a
parameter changes the grade, then the full and pinned widths differ by a post-hoc stretch as
well as by the parameter, and their difference would be the sum of two unrelated things
presented as one. Standing question four, in the place it would have done the most damage.
`attribute` therefore records the grade at each evaluation and refuses any row where it
moved.

ONLY THREE ROWS CAN MOVE A EURO, measured rather than assumed. The store carries ten
parameters; two are degenerate (`low == high`, so `draw` returns a constant and pinning them
cannot change anything); and `in_revenue_band=True` appears exactly twice in `channels.py`,
on C1 (ETI) and C5 (wealth). Everything else is denominated in jobs or percent, or — C3's
case — is deliberately excluded from the headline band because it reallocates euros rather
than creating them. A «Sobol over the store» is therefore a three-parameter study for a
household reform, and saying so is part of the result rather than a caveat on it.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any

#: Draws per band evaluation. The engine pass is paid once; every evaluation after it is
#: pure Monte Carlo. Matched to `band.DRAWS` so the attribution is measured at the same
#: resolution as the bands this project publishes.
DRAWS = 1000

#: Pinning a row must be able to change the sample, or the attribution measures nothing.
#: A degenerate row (low == high) cannot, by construction: `Parameter.draw` returns a
#: constant array for it. Those rows are excluded and NAMED rather than silently scoring
#: zero, because a zero in a ranking reads as «measured, and it does not matter».
DEGENERATE_NOTE = "low == high : ligne constante, l'épingler ne peut rien changer"


class AttributionError(RuntimeError):
    """An attribution was asked for in a way that would produce a meaningless share."""


@dataclass(frozen=True)
class ParameterContribution:
    """One row's first-order effect on the published band width."""

    key: str
    width_removed_eur: float
    """width(full) - width(pinned). Negative values are Monte Carlo noise about zero and
    are reported as measured rather than clipped: clipping would turn noise into a floor
    of zeros that reads as «small but real»."""
    share_of_width: float
    grade_moved: bool = False
    """True when pinning changed the grade, so the two widths are not comparable."""


@dataclass(frozen=True)
class Attribution:
    case: str
    full_width_eur: float
    grade: str
    contributions: tuple[ParameterContribution, ...]
    unexplained_eur: float
    """width(full) - sum(contributions). Joint effects. Reported, never normalised away:
    it is precisely the term that says whether a one-at-a-time reading can be trusted."""
    degenerate: tuple[str, ...]
    channels_in_band: tuple[str, ...]
    draws: int

    def ranked(self) -> tuple[ParameterContribution, ...]:
        """Largest width reduction first, refusals excluded from the ordering."""
        usable = [c for c in self.contributions if not c.grade_moved]
        return tuple(sorted(usable, key=lambda c: c.width_removed_eur, reverse=True))

    @property
    def refused(self) -> tuple[ParameterContribution, ...]:
        return tuple(c for c in self.contributions if c.grade_moved)


def band_width(result: Any) -> float:
    """p90 - p10 of the published band, in euros. Zero when no band was produced."""
    if result.band is None:
        return 0.0
    return float(result.band.p90 - result.band.p10)


def pin(store: Any, key: str) -> Any:
    """A copy of `store` with one parameter pinned to its central value.

    `dataclasses.replace` and a fresh parameter dict rather than mutation. The store is
    shared and memoised by `load()`; mutating it would silently change every later
    evaluation in the process — the trap that made a live knob look dead in D-095, where a
    memoised baseline was compared against itself.
    """
    parameter = store.parameters[key]
    if parameter.low == parameter.high:
        raise AttributionError(f"{key} : {DEGENERATE_NOTE}")
    pinned = dataclasses.replace(parameter, low=parameter.central, high=parameter.central)
    clone = dataclasses.replace(store, parameters=dict(store.parameters))
    clone.parameters[key] = pinned
    return clone


def attribute(case: str, inputs: dict[str, Any], *, store: Any = None,
              draws: int = DRAWS) -> Attribution:
    """Attribute the band width of one already-priced reform across the store's rows.

    `inputs` is everything `band.compute` needs for this reform — mechanical figure, the
    reform spec, and whichever household or employer arrays apply. Building it costs the
    engine pass; this function never runs the engine, which is why the attribution is
    affordable at all.
    """
    from impots.behavioural import band as band_module
    from impots.behavioural.store import load

    store = store if store is not None else load()
    if not store.parameters:
        raise AttributionError(
            "store vide : aucune élasticité vérifiée n'est chargée, et une attribution "
            "sur zéro paramètre rendrait des parts de rien")

    full = band_module.compute(store=store, draws=draws, **inputs)
    full_width = band_width(full)
    in_band = tuple(
        entry["key"] for entry in full.channels
        if entry.get("band") is not None and entry.get("applies"))

    if full_width <= 0.0:
        raise AttributionError(
            f"{case} : la bande publiée est de largeur nulle — aucun canal de revenu ne "
            f"s'applique à cette réforme, et attribuer zéro entre des paramètres "
            f"produirait un classement de rien. Grade : {full.grade}.")

    contributions: list[ParameterContribution] = []
    degenerate: list[str] = []
    for key, parameter in sorted(store.parameters.items()):
        if parameter.low == parameter.high:
            degenerate.append(key)
            continue
        pinned = band_module.compute(store=pin(store, key), draws=draws, **inputs)
        moved = pinned.grade != full.grade
        removed = full_width - band_width(pinned)
        contributions.append(ParameterContribution(
            key=key, width_removed_eur=removed,
            share_of_width=removed / full_width, grade_moved=moved))

    explained = sum(c.width_removed_eur for c in contributions if not c.grade_moved)
    return Attribution(
        case=case, full_width_eur=full_width, grade=full.grade,
        contributions=tuple(contributions), unexplained_eur=full_width - explained,
        degenerate=tuple(degenerate), channels_in_band=in_band, draws=draws)


@dataclass(frozen=True)
class _Request:
    """The three fields `api.main._employer_inputs` reads off a request.

    A shim rather than a copy of that function: duplicating forty lines of array assembly
    would let A0's inputs drift away from the ones the API actually prices, and an
    attribution computed on inputs nobody serves would be measuring a private fiction.
    """

    year: int
    reform: Any


def inputs_for(reform_spec: Any, *, year: int = 2024, households: int = 4000,
               frame: Any = None) -> dict[str, Any]:
    """Everything `band.compute` needs for one reform. **This is the engine pass.**

    Two runs: the population at full tier (for the aggregates and the employer arrays) and
    the EMTR pass (for C1's baseline/reform marginal rates). Full tier is not negotiable —
    the PPA and RSA tapers are most of the marginal rate at low wages, and a light-tier
    EMTR would be tidy and wrong exactly where the ETI channel bites.
    """
    import polars as pl

    from impots.api import main as api_main
    from impots.behavioural import emtr as emtr_module
    from impots.behavioural.eti import eti_inputs
    from impots.population import aggregate as aggregate_module
    from impots.population.build import PROCESSED
    from impots.population.runner import run as population_run

    frame = frame if frame is not None else pl.read_parquet(
        PROCESSED / "population_2024.parquet")
    request = _Request(year=year, reform=reform_spec)

    run = population_run(frame, year=year, reform=reform_spec, tier="full",
                         sample=households)
    agg = aggregate_module.aggregate(run.households)
    if agg.reform_cost is None:
        raise AttributionError("la réforme de référence ne rend aucun coût")

    employer = api_main._employer_inputs(request, run, agg)
    emtr_result = emtr_module.cached(frame, "a0", year=year, reform=reform_spec,
                                     sample=households)
    priced = emtr_result.with_earnings

    inputs: dict[str, Any] = {"mechanical": float(agg.reform_cost),
                              "reform": reform_spec, **employer}
    if priced.is_empty() or "emtr_reform" not in priced.columns:
        return inputs

    # The chain's own C1 inputs, built in one place (D-336): rates total and of the IR.
    inputs.update(eti_inputs(frame, priced))
    return inputs
