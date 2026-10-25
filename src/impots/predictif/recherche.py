"""Phase 10 M1 — the search for the debt at a fixed θ, from the request to the report.

`explorer.search` searches and `exploration.conditional_debt` evaluates (D-224); this
module joins them to a request (`ExplorationRequest`) and writes what a reader needs to
replay the search. The command `impots exploration` calls it with the population pass of
`/predictif/simulate`; the tests call it with a stub, so that the logic here is held in
seconds (PHASE10_SPEC §2).

THE GRID IS CHECKED BEFORE THE FIRST PASS. Each point becomes a `ReformSpec`, and a point
the schema refuses stops everything in a second rather than after an hour of passes. So
does a grid larger than the cap: refused, never truncated, since a truncated search would
answer « no candidate » for a reason that is not the right one.

ONE PASS PER BUNDLE AND PER VIEW. Past three years with the loop and no persistence named,
the two persistence scenarios are two searches side by side (D-230), and both read the
same passes: the pricing is cached by bundle and view.

EVERY BUNDLE EVALUATED IS IN THE REPORT, not only the candidates, with its first-year
mechanical cost in both views: a debt difference read without what the reform costs is a
number without its scale (D-235). « No candidate » then reads with the bundle closest to
the target, and a reader sees how far the grid was.

A BARÈME ENTERS BY A NAMED TRANSFORMATION (§5, D-237). The grid walks its factor; the
point becomes the reform's knobs from the law in force at the first projected year, read
once by the command, and the report records that law, so that the factor replays.

THE §7 INDICES OF THE NEAREST BUNDLE, per search: the bundle whose Δb_T at θ is closest to
the target, aged view, its indices read off the pass that priced it — no pass more — and
the chain-stage ones off that search's own path (D-237). With them, what that path says is
absent or closed, each with its reason: a loop Mésange has no balance row for is absent,
and must not read as a loop worth nothing (D-238).
"""

from __future__ import annotations

import itertools
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from impots import explorer
from impots.api.schemas import ExplorationRequest, ReformSpec
from impots.dette.path import BANNER as DEBT_BANNER
from impots.dette.reference import Start
from impots.entreprises import system as firm_system
from impots.entreprises.reforms import FirmReformSpec
from impots.predictif import chaine, exploration, retroaction, transformations
from impots.predictif import indices as indices_module
from impots.predictif.exploration import Priced

ROOT = Path(__file__).resolve().parents[3]

#: The default cap on bundles: each is two quick passes of two to four minutes.
MAX_BUNDLES = 12

#: What each view prices, as the report names it.
VIEW_NOTES = {
    "vieillie": "la population de 2024 vieillie jusqu'à la première année projetée, la "
                "vue de tête (D-216, D-226)",
    "figee": "la population de 2024 telle quelle, le droit de l'année appliqué à ses "
             "revenus ; un paquet qui ne tient que là n'est pas un plan (D-155)",
}


class RechercheError(ValueError):
    """The search was asked in a way that would mislead, or would waste an hour."""


def bounds_of(request: ExplorationRequest) -> list[explorer.Bound]:
    return [explorer.Bound(b.knob, b.low, b.high, b.step) for b in request.bounds]


def points(bounds: list[explorer.Bound]) -> list[dict[str, float]]:
    """The grid, in the order `explorer.search` walks it."""
    return [{bound.knob: value for bound, value in zip(bounds, point, strict=True)}
            for point in itertools.product(*(bound.grid() for bound in bounds))]


#: Why the Mésange indices are absent when the search did not load the macro store.
MACRO_UNREAD = ("Magasin macro non lu : la recherche ne le charge qu'avec la boucle, sous "
                "« gele_en_volume » et l'impulsion demandée.")


def reform_of(base: ReformSpec, knobs: dict[str, float],
              law: dict[str, Any] | None = None) -> ReformSpec:
    """The households' part of a bundle: the firm knobs go to `firm_of`."""
    own = {k: v for k, v in knobs.items() if k not in FirmReformSpec.model_fields}
    return ReformSpec.model_validate({**base.model_dump(exclude_none=True, mode="json"),
                                      **transformations.expand(own, law)})


def firm_of(base: FirmReformSpec | None,
            knobs: dict[str, float]) -> FirmReformSpec | None:
    """The firm part of a bundle (PHASE11_SPEC §3), or None when the search has none."""
    own = {k: v for k, v in knobs.items() if k in FirmReformSpec.model_fields}
    fixed = base.model_dump(exclude_none=True, mode="json") if base else {}
    if not own and not fixed:
        return None
    return FirmReformSpec.model_validate({**fixed, **own})


def needs_law(request: ExplorationRequest) -> bool:
    return bool(transformations.used([b.knob for b in request.bounds]))


def law_in_force(year: int) -> dict[str, Any]:
    """The law a transformation reads, as the engine applies it at `year`."""
    from impots.engine.reforms import read_ir_parameters
    from impots.engine.system import baseline

    return read_ir_parameters(baseline(), year)


def check_grid(request: ExplorationRequest, *, max_bundles: int = MAX_BUNDLES,
               law: dict[str, Any] | None = None) -> list[dict[str, float]]:
    """Every point of the grid, each a valid reform, and no more of them than the cap."""
    grid = points(bounds_of(request))
    if len(grid) > max_bundles:
        raise RechercheError(
            f"{len(grid)} paquets pour {max_bundles} autorisés, soit {2 * len(grid)} passes "
            f"de deux à quatre minutes. Élargir le pas, resserrer les bornes ou relever "
            f"le plafond : une recherche tronquée rendrait « pas de candidat » pour une "
            f"raison qui n'est pas la bonne.")
    for knobs in grid:
        try:
            reform_of(request.base, knobs, law)
            firm_of(request.firm_base, knobs)
        except transformations.TransformationError as error:
            raise RechercheError(f"paquet {knobs}, avant toute passe : {error}") from error
        except ValidationError as error:
            raise RechercheError(
                f"paquet {knobs} refusé par le schéma de la réforme, avant toute passe : "
                f"{error}") from error
    return grid


def code_state(root: Path = ROOT) -> tuple[str, bool]:
    """The commit the search runs on, and whether `src/` differs from it."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                              check=True).stdout.strip()

    return git("rev-parse", "HEAD"), bool(git("status", "--porcelain", "--", "src"))


def _evaluation(knobs: dict[str, float], evaluation: explorer.Evaluation,
                objective: explorer.Objective, target: float,
                cost: Callable[[dict[str, float], str], float]) -> dict[str, Any]:
    values = [value for _, value in evaluation.corners]
    return {"knobs": dict(knobs), "cost_aged_eur": cost(knobs, "vieillie"),
            "cost_frozen_eur": cost(knobs, "figee"), "delta_aged": evaluation.aged_eur,
            "delta_frozen": evaluation.frozen_eur,
            "corners": [[label, value] for label, value in evaluation.corners],
            "corner_low": min(values), "corner_high": max(values),
            "meets_target": objective.meets(evaluation.aged_eur, target)}


def _nearest(evaluations: list[dict[str, Any]], target: float) -> dict[str, Any]:
    return min(evaluations, key=lambda e: (abs(e["delta_aged"] - target),
                                           sorted(e["knobs"].items())))


def _search(persistence: str | None, seen: list[tuple[dict[str, float], Any]],
            candidates: tuple[explorer.Candidate, ...], log: explorer.SearchLog,
            target: float, cost: Callable[[dict[str, float], str], float],
            indices: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    objective = explorer.OBJECTIVES[explorer.CONDITIONAL]
    evaluations = [_evaluation(knobs, evaluation, objective, target, cost)
                   for knobs, evaluation in seen]
    found = [{"knobs": dict(c.knobs), "delta_aged": c.aged_eur,
              "delta_frozen": c.frozen_eur, "meets_target": c.meets_target,
              "frozen_only": c.frozen_only, "robust": c.robust, "verdict": c.theta_reason}
             for c in candidates]
    nearest = _nearest(evaluations, target)
    closest = None if any(c["meets_target"] for c in found) else nearest
    return {"persistence": persistence,
            "persistence_label": (retroaction.PERSISTENCE_LABELS[persistence]
                                  if persistence is not None else None),
            "digest": log.digest(), "log": log.payload(), "evaluations": evaluations,
            "candidates": found,
            "excluded": [[dict(knobs), reason] for knobs, reason in log.excluded],
            "closest": closest, "indices": indices(nearest)}


def run(request: ExplorationRequest, *, price: Callable[..., Priced],
        hypotheses: Any, start: Start, macro_store: Any = None,
        securities: list[Any] | None = None, max_bundles: int = MAX_BUNDLES,
        law: dict[str, Any] | None = None, commit: str = "", computed: str = "",
        where: str | None = None) -> dict[str, Any]:
    """The search, once per persistence, from one pass per bundle and view; the report.

    `hypotheses` is what `api.main._predictif_hypotheses` builds for the request, and
    `price(reform, view)` is one pass of the first projected year in that view, called
    `price(reform, view, firm)` when the bundle has a firm part. `law` is
    the law in force at that year (`law_in_force`), read when a transformation asks.
    """
    from impots.dette import reference as reference_module

    first = start.year + 1
    if law is not None and law.get("year", first) != first:
        raise RechercheError(
            f"droit en vigueur lu pour {law['year']}, première année projetée {first} : "
            f"le facteur mettrait à l'échelle le barème d'une autre année que celle "
            f"qu'il chiffre.")
    grid = check_grid(request, max_bundles=max_bundles, law=law)
    bounds = bounds_of(request)
    target = request.target.at_most_points / 100
    passes: dict[tuple[tuple[tuple[str, float], ...], str], Priced] = {}

    def priced(knobs: dict[str, float], view: str) -> Priced:
        key = (tuple(sorted(knobs.items())), view)
        if key not in passes:
            # The firm part travels only when there is one: a household search calls
            # `price` exactly as it always did.
            firm = firm_of(request.firm_base, knobs)
            reform = reform_of(request.base, knobs, law)
            passes[key] = (price(reform, view) if firm is None
                           else price(reform, view, firm))
        return passes[key]

    gdp_eur = reference_module.reference_years(
        start, 1, spending=hypotheses.spending, growth=hypotheses.growth)[0].gdp_eur

    def indices_of(persistence: str | None) -> Callable[[dict[str, Any]], dict[str, Any]]:
        def indices(nearest: dict[str, Any]) -> dict[str, Any]:
            knobs = nearest["knobs"]
            reform = reform_of(request.base, knobs, law)
            aged = priced(knobs, exploration.VIEWS[0])
            path = exploration.trajectory(
                hypotheses.theta, aged, reform, start=start, horizon=request.horizon,
                spending=hypotheses.spending, growth=hypotheses.growth,
                rate=hypotheses.rate, store=hypotheses.store, macro_store=macro_store,
                persistence=persistence, securities=securities)
            rows = indices_module.compute(
                indices_module.select(None), trajectory=path,
                deciles_rows=aged.deciles, impulse=aged.impulse, gdp_eur=gdp_eur,
                macro_store=macro_store, macro_reason=MACRO_UNREAD,
                theta=hypotheses.theta, store=hypotheses.store, reform=reform,
                mechanical=-aged.cost, inputs=aged.inputs, year=first,
                firm_reason=(indices_module.FIRM_PENDING
                             if firm_of(request.firm_base, knobs) is not None
                             else indices_module.FIRM_LAYER),
                is_rate_change=firm_system.normal_rate_change_points(
                    firm_of(request.firm_base, knobs), first))
            return {"knobs": dict(knobs), "delta_aged": nearest["delta_aged"],
                    "absent": dict(path.absent), "closed": dict(path.closed),
                    "rows": [row.payload() for row in rows]}
        return indices

    searches = []
    for persistence in hypotheses.persistences:
        evaluate = exploration.conditional_debt(
            price=priced, reform_of=lambda knobs: reform_of(request.base, knobs, law),
            start=start, horizon=request.horizon, spending=hypotheses.spending,
            growth=hypotheses.growth, rate=hypotheses.rate, theta=hypotheses.theta,
            year=request.target.year, store=hypotheses.store, macro_store=macro_store,
            persistence=persistence, securities=securities)
        seen: list[tuple[dict[str, float], Any]] = []

        def recorded(knobs: dict[str, float], evaluate=evaluate, seen=seen) -> Any:
            evaluation = evaluate(knobs)
            seen.append((dict(knobs), evaluation))
            return evaluation

        candidates, log = explorer.search(
            target_eur=target, bounds=bounds, evaluate=recorded,
            quantity=explorer.CONDITIONAL, theta=hypotheses.theta,
            max_evaluations=len(grid))
        searches.append(_search(persistence, seen, candidates, log, target,
                                lambda knobs, view: priced(knobs, view).cost,
                                indices_of(persistence)))

    theta = hypotheses.theta
    return {
        "name": request.name, "titre": request.titre, "question": request.question,
        "computed": computed, "commit": commit, "where": where,
        "request": request.model_dump(mode="json", exclude_none=True),
        "hypotheses": {
            "spending_name": hypotheses.spending.name,
            "growth_name": hypotheses.growth.name, "rate_name": hypotheses.rate.name,
            "horizon": request.horizon,
            "target_year": request.target.year or start.year + request.horizon,
            "target_points": request.target.at_most_points, "target_share": target,
            "theta": {"common": theta.common, "rows": dict(theta.rows)},
            "uprating": {"wage": hypotheses.uprating.wage,
                         "prices": hypotheses.uprating.price,
                         "source": hypotheses.uprating.source},
            "behavioural": request.behavioural, "macro": request.macro,
            "looped": hypotheses.looped,
            "transformations": [
                {"name": t.name, "label": t.label, "writes": list(t.writes),
                 "year": first, "law": {key: law[key] for key in t.reads}}
                for t in transformations.used([b.knob for b in request.bounds])],
        },
        "start": {"year": start.year, "debt_ratio": start.debt_ratio,
                  "primary_balance": start.primary_balance,
                  "implicit_rate": start.implicit_rate, "gdp_eur": start.gdp_eur},
        "unit": "part du PIB : Δb, la dette de la réforme moins celle de la référence ; "
                "négatif, la réforme allège la dette",
        "views": dict(VIEW_NOTES),
        "conventions": [chaine.CARRY_LABEL, exploration.NO_BAND],
        "banner": chaine.BANNER, "debt_banner": DEBT_BANNER,
        "bundles": len(grid), "passes": len(passes), "searches": searches,
    }
