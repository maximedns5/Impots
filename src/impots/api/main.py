"""FastAPI app: the household calculator (Phase 0 §4) and the population (Phase 1 §6).

Five endpoints and a warm-up. The warm-up matters more than it looks: building
the tax-benefit system costs ~3 s and openfisca's first computation in a process
costs ~2 s more, so without it the first user of a fresh server waits five seconds
for a request the spec budgets at 1.5.

Population runs are batch jobs; only the bounded quick tier is reachable over
HTTP, and `GET /population/baseline` reads a precomputed file rather than running
the engine at all.

CORS is wide open because Phase 0 is a local tool and `ui/index.html` is meant to
work when opened straight off the filesystem. That is a deliberate Phase 0 choice
and must not survive contact with a deployment.
"""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from impots.api.schemas import (
    MAX_YEAR,
    MIN_YEAR,
    QUICK_TIER_HOUSEHOLDS,
    DecileRow,
    HealthResponse,
    IRParameters,
    PopulationMeta,
    PopulationResponse,
    PopulationSimulateRequest,
    ReconciliationLine,
    ResultRows,
    SimulateRequest,
    SimulateResponse,
    Timings,
)
from impots.engine import baseline, compute, versions, warm_up
from impots.engine.reforms import read_ir_parameters

UI_FILE = Path(__file__).resolve().parents[3] / "ui" / "index.html"

_state: dict[str, Any] = {"warm": False, "warm_up_ms": None}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Pay the cold-start cost before the first request rather than inside it."""
    _state["warm_up_ms"] = warm_up()
    _state["warm"] = True
    yield


app = FastAPI(
    title="Impôts — calculateur de foyer (phase 0)",
    description=(
        "Couche mécanique (L2) : effet au premier jour, à droit constant, sans réaction "
        "comportementale. Un foyer, une réforme, des montants exacts."
    ),
    version="0.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    engine = versions()
    return HealthResponse(
        status="ok",
        openfisca_france=engine["openfisca_france"],
        openfisca_core=engine["openfisca_core"],
        warm=bool(_state["warm"]),
    )


@app.get("/parameters/ir", response_model=IRParameters)
def parameters_ir(
    year: int = Query(default=2024, ge=MIN_YEAR, le=MAX_YEAR),
) -> IRParameters:
    """Current law behind the whitelisted knobs, read live from the parameter tree.

    The UI prefills its reform panel from here. Hardcoding these values would let
    the panel drift away from the law the engine is actually applying — the user
    would edit a barème that is not the one they are being compared against.
    """
    return IRParameters.model_validate(read_ir_parameters(baseline(), year))


@app.post("/simulate", response_model=SimulateResponse)
def simulate(request: SimulateRequest) -> SimulateResponse:
    """One household, current law and optionally one reform, side by side."""
    try:
        result = compute(
            request.household,
            request.year,
            reform=request.reform,
            tier=request.tier,
            emtr=request.emtr,
            historique_revenus=request.historique_revenus,
            debug=request.debug,
        )
    except ValueError as error:
        # A rejected input that pydantic could not have caught on its own —
        # surface it as a 422 with the engine's own wording.
        raise HTTPException(status_code=422, detail=str(error)) from error
    except AssertionError as error:
        # An internal invariant broke (e.g. the reformed barème read back wrong).
        # Refusing loudly beats answering with a number we do not trust.
        raise HTTPException(status_code=500, detail=str(error)) from error

    return SimulateResponse(
        baseline=ResultRows.model_validate(result.baseline),
        reform=ResultRows.model_validate(result.reform) if result.reform else None,
        delta=ResultRows.model_validate(result.delta) if result.delta else None,
        emtr=result.emtr,
        emtr_reform=result.emtr_reform,
        tier=result.tier,
        year=result.year,
        historique_revenus=result.historique_revenus,
        timings=Timings.model_validate(result.timings),
        engine=result.engine,
    )


# --------------------------------------------------------------------------- #
# Population (L1)
# --------------------------------------------------------------------------- #
POPULATION_VINTAGE = "2024"

#: Said on every population response and printed in the UI banner. The population
#: is a construction and the numbers it produces are worth what the reconciliation
#: report says they are worth.
POPULATION_NOTE = (
    "Population synthétique construite à partir de données ouvertes : structure des "
    "ménages observée dans l'enquête Emploi, revenus entièrement simulés à partir de "
    "distributions publiées. Les écarts aux totaux publiés sont dans "
    "reports/reconciliation.md. Les niveaux de RSA, de prime d'activité et de la "
    "distribution des niveaux de vie ne sont pas publiables en l'état (D-015) ; les "
    "écarts entre droit courant et réforme le sont."
)


def _baseline_summary() -> dict[str, Any]:
    """The precomputed baseline aggregates, written by `impots population reconcile`."""
    from impots.population.build import PROCESSED

    path = PROCESSED / f"baseline_{POPULATION_VINTAGE}.json"
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="Aucune population n'a encore été construite. Lancez "
                   "`impots population build` puis `impots population reconcile`.",
        )
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _population_frame() -> Any:
    """The population parquet, loaded once. ~420 000 rows, a few hundred MB in the
    engine but only tens of MB as a frame."""
    import polars as pl

    from impots.population.build import PROCESSED

    path = PROCESSED / f"population_{POPULATION_VINTAGE}.parquet"
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="Aucune population n'a encore été construite. Lancez "
                   "`impots population build`.",
        )
    return pl.read_parquet(path)


@app.get("/population/baseline", response_model=PopulationResponse)
def population_baseline() -> PopulationResponse:
    """Precomputed baseline aggregates, decile table and reconciliation summary.

    Reads a file; never runs the engine. A full-tier population run is minutes.
    """
    summary = _baseline_summary()
    return PopulationResponse(
        meta=PopulationMeta(
            vintage=summary["vintage"], branch=summary["branch"],
            households=summary["households"], persons=summary["persons"],
            tier="full", sampled_households=summary.get("sampled_households"),
            note=POPULATION_NOTE, limitations=summary["limitations"],
        ),
        totals=summary["totals"],
        deciles=[DecileRow.model_validate(row) for row in summary["deciles"]],
        reconciliation=[
            ReconciliationLine.model_validate(line) for line in summary["reconciliation"]
        ],
    )


@app.post("/population/simulate", response_model=PopulationResponse)
def population_simulate(request: PopulationSimulateRequest) -> PopulationResponse:
    """Price a reform over the synthetic population — quick tier only.

    A deterministic, self-weighting subsample of 20 000 households. The full
    199 451-household run is a batch job and lives in the CLI: putting it behind a
    synchronous HTTP request would be a request that takes minutes (spec §1.1).
    """
    from impots.population import aggregate as aggregate_module
    from impots.population.runner import run as population_run
    from impots.population.to_openfisca import WiringError

    frame = _population_frame()
    started = time.perf_counter()
    try:
        result = population_run(
            frame, year=request.year, reform=request.reform, tier="full",
            sample=QUICK_TIER_HOUSEHOLDS,
        )
    except WiringError as error:  # pragma: no cover - guarded upstream
        raise HTTPException(status_code=500, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    agg = aggregate_module.aggregate(result.households)
    summary = _baseline_summary()
    return PopulationResponse(
        meta=PopulationMeta(
            vintage=POPULATION_VINTAGE, branch=summary["branch"],
            households=agg.households, persons=agg.persons,
            tier="quick", sampled_households=QUICK_TIER_HOUSEHOLDS,
            note=POPULATION_NOTE
            + f" Ce résultat porte sur un sous-échantillon déterministe de "
              f"{QUICK_TIER_HOUSEHOLDS:,} ménages repondérés"
              .replace(",", " ")
            + ", pas sur la population complète : attendez-vous à un bruit "
              "d'échantillonnage de l'ordre du pour cent sur les agrégats.",
            limitations=summary["limitations"],
        ),
        totals=agg.totals, totals_reform=agg.totals_reform, deltas=agg.deltas,
        reform_cost=agg.reform_cost,
        deciles=[DecileRow.model_validate(vars(row)) for row in agg.deciles],
        reconciliation=[
            ReconciliationLine.model_validate(line) for line in summary["reconciliation"]
        ],
        timings={
            **{k: float(v) for k, v in result.timings.items()},
            "total_s": round(time.perf_counter() - started, 2),
        },
    )


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve the static UI so the quickstart is one command instead of two.

    Opening `ui/index.html` straight off the filesystem works just as well; that is
    what the permissive CORS policy above is for.
    """
    if not UI_FILE.exists():  # pragma: no cover - only if the repo is incomplete
        raise HTTPException(status_code=404, detail="ui/index.html introuvable")
    return FileResponse(UI_FILE, media_type="text/html")
