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
from impots.predictif import chaine, exploration, retroaction
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


def reform_of(base: ReformSpec, knobs: dict[str, float]) -> ReformSpec:
    return ReformSpec.model_validate({**base.model_dump(exclude_none=True, mode="json"),
                                      **knobs})


def check_grid(request: ExplorationRequest, *,
               max_bundles: int = MAX_BUNDLES) -> list[dict[str, float]]:
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
            reform_of(request.base, knobs)
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


def _search(persistence: str | None, seen: list[tuple[dict[str, float], Any]],
            candidates: tuple[explorer.Candidate, ...], log: explorer.SearchLog,
            target: float, cost: Callable[[dict[str, float], str], float]) -> dict[str, Any]:
    objective = explorer.OBJECTIVES[explorer.CONDITIONAL]
    evaluations = [_evaluation(knobs, evaluation, objective, target, cost)
                   for knobs, evaluation in seen]
    found = [{"knobs": dict(c.knobs), "delta_aged": c.aged_eur,
              "delta_frozen": c.frozen_eur, "meets_target": c.meets_target,
              "frozen_only": c.frozen_only, "robust": c.robust, "verdict": c.theta_reason}
             for c in candidates]
    closest = (None if any(c["meets_target"] for c in found)
               else min(evaluations, key=lambda e: (abs(e["delta_aged"] - target),
                                                    sorted(e["knobs"].items()))))
    return {"persistence": persistence,
            "persistence_label": (retroaction.PERSISTENCE_LABELS[persistence]
                                  if persistence is not None else None),
            "digest": log.digest(), "log": log.payload(), "evaluations": evaluations,
            "candidates": found,
            "excluded": [[dict(knobs), reason] for knobs, reason in log.excluded],
            "closest": closest}


def run(request: ExplorationRequest, *, price: Callable[[ReformSpec, str], Priced],
        hypotheses: Any, start: Start, macro_store: Any = None,
        securities: list[Any] | None = None, max_bundles: int = MAX_BUNDLES,
        commit: str = "", computed: str = "") -> dict[str, Any]:
    """The search, once per persistence, from one pass per bundle and view; the report.

    `hypotheses` is what `api.main._predictif_hypotheses` builds for the request, and
    `price(reform, view)` is one pass of the first projected year in that view.
    """
    grid = check_grid(request, max_bundles=max_bundles)
    bounds = bounds_of(request)
    target = request.target.at_most_points / 100
    passes: dict[tuple[tuple[tuple[str, float], ...], str], Priced] = {}

    def priced(knobs: dict[str, float], view: str) -> Priced:
        key = (tuple(sorted(knobs.items())), view)
        if key not in passes:
            passes[key] = price(reform_of(request.base, knobs), view)
        return passes[key]

    searches = []
    for persistence in hypotheses.persistences:
        evaluate = exploration.conditional_debt(
            price=priced, reform_of=lambda knobs: reform_of(request.base, knobs),
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
                                lambda knobs, view: priced(knobs, view).cost))

    theta = hypotheses.theta
    return {
        "name": request.name, "titre": request.titre, "question": request.question,
        "computed": computed, "commit": commit,
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
