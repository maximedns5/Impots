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
import logging
import math
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from impots.api.schemas import (
    MAX_YEAR,
    MIN_YEAR,
    QUICK_TIER_HOUSEHOLDS,
    DecileRow,
    EmtrCurveListResponse,
    EmtrCurveResponse,
    EmtrDecile,
    FirmCell,
    FirmMeta,
    FirmResponse,
    FirmSimulateRequest,
    FirmSizeRow,
    HealthResponse,
    IRParameters,
    PopulationMeta,
    PopulationResponse,
    PopulationSimulateRequest,
    ReconciliationLine,
    ResultRows,
    ScenarioDetail,
    ScenarioListResponse,
    ScenarioSummary,
    SimulateRequest,
    SimulateResponse,
    Timings,
    TrajectoryListResponse,
    TrajectoryResponse,
)
from impots.engine import baseline, compute, versions, warm_up
from impots.engine.reforms import read_ir_parameters
from impots.identifiants import millesime

UI_FILE = Path(__file__).resolve().parents[3] / "ui" / "index.html"

#: Where this running version's Corresponding Source can be obtained.
#:
#: AGPL section 13 obliges anyone who lets users interact with a modified version
#: *over a network* to offer those users its source. A local tool triggers nothing;
#: the moment this is hosted, it does. Reading it from the environment rather than
#: hardcoding a repository URL is the point: a fork that deploys must advertise its
#: own source, not ours.
SOURCE_URL = os.environ.get("IMPOTS_SOURCE_URL") or None
LICENCE = "AGPL-3.0-or-later"

_state: dict[str, Any] = {"warm": False, "warm_up_ms": None}


def _is_loopback_only() -> bool:
    """Whether this process was told to bind to localhost only.

    Best-effort: uvicorn's host is not visible from inside the app, so read the
    same environment variable uvicorn does and treat an unset host as the
    loopback default. Wrong in the safe direction — an unusual launch produces a
    warning that need not have been printed, never silence when one was needed.
    """
    host = os.environ.get("UVICORN_HOST", "127.0.0.1")
    return host in {"127.0.0.1", "localhost", "::1"}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Pay the cold-start cost before the first request rather than inside it."""
    _state["warm_up_ms"] = warm_up()
    _state["warm"] = True
    if SOURCE_URL is None and not _is_loopback_only():
        # Not an abstract worry: this app serves a UI to whoever can reach it, and
        # AGPL section 13 makes offering them the source a condition of doing so.
        logging.getLogger("impots").warning(
            "Bound beyond localhost with no IMPOTS_SOURCE_URL set. AGPL section 13 "
            "requires offering the Corresponding Source to anyone interacting with "
            "this server over a network. Set IMPOTS_SOURCE_URL to a URL serving it."
        )
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

#: The largest legitimate request — one household and a complete reform — is a few
#: kilobytes. Without a limit, a body is read whole into memory whatever its size (D-173).
MAX_BODY_BYTES = 64 * 1024


class BodyLimit:
    """Refuses a request body over `MAX_BODY_BYTES` with a 413, before it is parsed.

    The declared `content-length` is checked first. A body sent without one, or longer
    than it declared, is counted as it arrives and cut off at the limit.
    """

    def __init__(self, app: Any, limit: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.limit = limit

    def _message(self) -> str:
        return f"Corps de requête trop volumineux : au plus {self.limit} octets."

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope.get("headers") or ()).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.limit:
            await JSONResponse({"detail": self._message()}, status_code=413)(
                scope, receive, send)
            return
        seen = 0

        async def counted() -> dict:
            nonlocal seen
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.limit:
                    raise HTTPException(status_code=413, detail=self._message())
            return message

        await self.app(scope, counted, send)


app.add_middleware(BodyLimit)


def _json_safe(value: Any) -> Any:
    """JSON has no infinity, and a 422 echoes the input it refused: refusing `Infinity`
    then crashed while writing the refusal (D-173). Non-finite floats become text."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422,
                        content={"detail": _json_safe(jsonable_encoder(exc.errors()))})
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
        licence=LICENCE,
        source_url=SOURCE_URL,
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
        emtr_deciles=[
            EmtrDecile.model_validate(row) for row in summary.get("emtr_deciles", [])
        ],
        reconciliation=[
            ReconciliationLine.model_validate(line) for line in summary["reconciliation"]
        ],
    )


#: Households the behavioural EMTR runs on. Smaller than the mechanical subsample
#: because a marginal rate costs two full-tier runs, and the band is a range anyway —
#: a band whose sampling noise is well inside its own width loses nothing by being
#: computed on fewer households. The number is reported so nobody has to guess.
BEHAVIOURAL_EMTR_HOUSEHOLDS = 3_000


def _smic_annual(year: int) -> float:
    """The annual SMIC, read from the parameter tree rather than written down."""
    from impots.engine.system import baseline as engine_baseline

    smic = engine_baseline().parameters(f"{year}-01-01").marche_travail.salaire_minimum.smic
    return float(smic.smic_b_horaire) * float(smic.nb_heures_travail_mensuel) * 12.0


def _employer_inputs(request: Any, frame: Any, households: Any, agg: Any) -> dict[str, Any]:
    """What C2 and C3 need, or nothing when the reform moves no employer contribution.

    C2 grades by wage, so the SMIC multiple comes from individual salaries; the change
    in labour cost is only available per household, so every earner in a household
    carries their household's rate. Exact for the single-earner households that are
    most of them, an approximation otherwise, and stated.
    """
    import numpy as np
    import polars as pl

    if "salaire_super_brut_reform" not in households.columns:
        return {}
    cost = households["salaire_super_brut"].to_numpy()
    cost_reform = households["salaire_super_brut_reform"].to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = np.where(cost > 0, (cost_reform - cost) / np.maximum(cost, 1e-9), 0.0)
    if not np.any(np.abs(rate) > 1e-12):
        return {}

    by_household = dict(zip(households["household_id"].to_list(), rate, strict=False))
    earners = frame.filter(pl.col("salaire_brut_annuel") > 0)
    smic = _smic_annual(request.year)
    return {
        "smic_multiple": earners["salaire_brut_annuel"].to_numpy() / max(smic, 1.0),
        "relative_cost_change": np.array(
            [by_household.get(h, 0.0) for h in earners["household_id"].to_list()]
        ),
        "earner_weights": earners["weight"].to_numpy(),
        # NOT deltas["cotisations_employeur"] — that figure is gross of the
        # allègements and reported exactly zero for a reform costing 17.7 bn (D-039).
        "contribution_delta": agg.employer_contribution_delta,
    }


def _narrow_band(request: Any, households: Any, frame: Any = None) -> Any:
    """How much of this reform's movement comes from near its own thresholds.

    Measured per threshold FAMILY against the income each family is defined on — the
    barème and décote on taxable salary, the allègement plafonds on gross wage — and
    the largest share wins. Comparing a SMIC multiple against taxable income would
    put every threshold in the wrong place on the axis.
    """
    import numpy as np

    from impots import narrow_band as narrow_band_module
    from impots.api.schemas import NarrowBandFlag

    if "revenu_disponible_reform" not in households.columns:
        return None
    smic = _smic_annual(request.year)
    spec = request.reform.model_dump(exclude_none=True)

    taxable_knobs = {"ir_bareme", "decote_seuil_celib", "decote_seuil_couple",
                     "plafond_qf_demi_part"}
    wage_knobs = {"allegement_general_plafond", "bandeau_maladie_plafond",
                  "bandeau_famille_plafond"}

    weights = households["weight"].to_numpy()
    disposable_move = (
        households["revenu_disponible_reform"].to_numpy()
        - households["revenu_disponible"].to_numpy()
    )
    cost_move = (
        households["salaire_super_brut_reform"].to_numpy()
        - households["salaire_super_brut"].to_numpy()
        if "salaire_super_brut_reform" in households.columns
        else np.zeros(len(weights))
    )

    # The wage family is measured PER EARNER, not per household. A plafond is an
    # individual threshold: a two-earner household at 1.5 SMIC each has a household
    # gross of 3 SMIC and sits inside a 3.3-SMIC window while neither earner is
    # anywhere near it. Measured at household level the cliff case scored 56 % against
    # a 50 % bar — the right side of the line, for the wrong reason and by too little.
    wage_income, wage_move, wage_weights = (
        households["salaire_brut"].to_numpy(), cost_move, weights
    )
    if frame is not None:
        import polars as pl

        earners = frame.filter(pl.col("salaire_brut_annuel") > 0)
        by_household = dict(zip(households["household_id"].to_list(), cost_move,
                                strict=False))
        counts = (
            earners.group_by("household_id").len()
            .rename({"len": "n"}).to_dicts()
        )
        per_household_count = {row["household_id"]: row["n"] for row in counts}
        ids = earners["household_id"].to_list()
        wage_income = earners["salaire_brut_annuel"].to_numpy()
        # Each earner carries their household's movement, split evenly among them.
        wage_move = np.array([
            by_household.get(h, 0.0) / max(per_household_count.get(h, 1), 1) for h in ids
        ])
        wage_weights = earners["weight"].to_numpy()

    families = [
        ({k: v for k, v in spec.items() if k in taxable_knobs},
         households["salaire_imposable"].to_numpy(), disposable_move, weights),
        ({k: v for k, v in spec.items() if k in wage_knobs},
         wage_income, wage_move, wage_weights),
    ]
    best = None
    for subset, income, movement, group_weights in families:
        if not subset:
            continue
        thresholds = narrow_band_module.household_thresholds(
            type(request.reform).model_validate(subset), smic
        )
        result = narrow_band_module.measure(income, movement, group_weights, thresholds)
        if best is None or result.share > best.share:
            best = result
    if best is None:
        return None
    return NarrowBandFlag(
        share=best.share, flagged=best.flagged, window=best.window,
        share_threshold=best.share_threshold, thresholds=best.thresholds,
        caveat=best.caveat,
    )


def _niche_blind_spot(request: Any, agg: Any) -> Any:
    """Flag a niche reform the population cannot price, or return None.

    Never raises: the rest of the reform may be perfectly answerable, and refusing the
    whole request over one blind knob would hide a valid mechanical figure.
    """
    from impots.api.schemas import NicheBlindSpot
    from impots.engine.reforms import NICHE_KNOBS
    from impots.guards import niche_blind_spot

    knobs = tuple(request.reform.model_dump(exclude_none=True))
    imputed = getattr(request, "impute_niches", False)
    blind = niche_blind_spot(knobs, agg.totals, NICHE_KNOBS, bases_are_imputed=imputed)
    if not blind:
        return None
    if imputed:
        return NicheBlindSpot(
            knobs=list(blind), declared_base_eur=float(
                agg.totals.get("reductions", 0.0) + agg.totals.get("credits_impot", 0.0)),
            message=(
                f"Les bases sont imputées, mais {', '.join(blind)} ne peut toujours pas "
                "être chiffré : le plafond global ne mord que sur les foyers cumulant "
                "plus de 10 000 € d'avantages, or l'imputation donne à chaque "
                "bénéficiaire d'un décile le MÊME montant — un décile n'a ni queue ni "
                "dispersion. Le crédit imputé le plus élevé avoisine 1 900 €, personne "
                "n'atteint le plafond, et un coût nul ici ne dit rien du dispositif."
            ),
        )
    return NicheBlindSpot(
        knobs=list(blind),
        declared_base_eur=0.0,
        message=(
            "Cette population ne déclare AUCUNE réduction ni crédit d'impôt : les "
            f"leviers {', '.join(blind)} n'ont donc rien sur quoi s'appliquer et leur "
            "coût affiché est nul par absence de base, non par absence d'effet. "
            "Nationalement ces dispositifs représentent 19,53 Md€ contre un barème de "
            "98,84 Md€ (DGFiP). Le calculateur foyer par foyer, lui, les chiffre "
            "exactement dès que la dépense est saisie."
        ),
    )


def _macro(request: Any, agg: Any) -> Any:
    """The L4 fan, or a block explaining why there is not one.

    Never raises. A reform with no published multiplier, or a checkout without the
    primary sources on disk, both produce `available: false` with a reason — the fan
    being unavailable is the designed outcome for most reforms, not an error.
    """
    from impots.api.schemas import (
        Macro,
        MacroAssumptions,
        MacroBranch,
        MacroDecomposition,
        MacroQuantiles,
    )
    from impots.macro import fan as fan_module
    from impots.macro import io_layer, shocks
    from impots.macro import store as store_module
    from impots.macro import tes as tes_module

    knobs = tuple(request.reform.model_dump(exclude_none=True))
    try:
        impulse = shocks.build(
            agg.deltas, year=request.year, reform_cost=agg.reform_cost, knobs=knobs)
    except shocks.ShockError as error:
        return Macro(available=False, unavailable_because=str(error))

    uncovered = {name: reason for name, reason in impulse.reasons().items()}
    if not impulse.by_instrument:
        return Macro(
            available=False, uncovered=uncovered,
            unavailable_because=(
                "Aucun instrument de cette réforme n'a de multiplicateur publié : il n'y "
                "a pas de trajectoire macro à tracer."
            ),
        )

    try:
        table = tes_module.load()
        jobs = tes_module.employment(table.branches, table.base_year)
        store = store_module.load()
        composition = io_layer.composition(
            table, shocks.allocation(table, impulse), jobs, use="consommation_finale")
        result = fan_module.run(
            impulse, store, gdp_eur=tes_module.gdp(table) * 1e6, composition=composition)
    except (tes_module.TesError, io_layer.IoLayerError, fan_module.FanError,
            store_module.MissingSourceTable, RuntimeError) as error:
        return Macro(available=False, uncovered=uncovered,
                     unavailable_because=f"Couche macro indisponible : {error}")

    strip = result.assumptions
    branches = sorted(
        range(table.n), key=lambda i: composition.output_shares[i], reverse=True)[:12]
    return Macro(
        available=True,
        uncovered=uncovered,
        gdp={h: MacroQuantiles(p10=q.p10, p50=q.p50, p90=q.p90, unit="EUR")
             for h, q in result.gdp_eur.items()},
        jobs={h: MacroQuantiles(p10=q.p10, p50=q.p50, p90=q.p90, unit="milliers ETP")
              for h, q in result.jobs_thousands_etp.items()},
        decomposition=[
            MacroDecomposition(
                horizon=h, parameter=d.parameter, scenario=d.scenario,
                scenario_available=d.scenario_available,
                scenario_unavailable_because=d.scenario_unavailable_because)
            for h, d in result.decomposition.items()
        ],
        composition=[
            MacroBranch(
                code=table.branches[i], label=table.labels[i].title(),
                output_share=float(composition.output_shares[i]),
                employment_share=float(composition.employment_shares[i]))
            for i in branches
        ],
        assumptions=MacroAssumptions(
            cycle_state=strip.cycle_state, design=strip.design,
            leakage=None if math.isnan(strip.leakage) else strip.leakage,
            leakage_applied=strip.leakage_applied, horizons=list(strip.horizons),
            parameters_vintage=strip.parameters_vintage, grade=strip.grade,
            covered_share=strip.covered_share, instruments=list(strip.instruments),
            simulation_conditions=strip.simulation_conditions,
            caveats=list(strip.caveats), banner=strip.banner,
        ),
        notes=list(result.notes),
    )


def _behavioural(request: Any, frame: Any, agg: Any, run_households: Any = None) -> Any:
    """The band for a household reform, or a mechanical-only answer with its reason."""
    import numpy as np

    from impots.api.schemas import Behavioural
    from impots.behavioural import band as band_module
    from impots.behavioural import emtr as emtr_module

    mechanical = -(agg.reform_cost or 0.0)
    employer = _employer_inputs(request, frame, run_households, agg) if run_households is not None else {}
    emtr_result = emtr_module.cached(
        frame, POPULATION_VINTAGE, year=request.year, reform=request.reform,
        sample=BEHAVIOURAL_EMTR_HOUSEHOLDS,
    )
    households = emtr_result.with_earnings
    if households.is_empty() or "emtr_reform" not in households.columns:
        computed = band_module.compute(
            mechanical=mechanical, reform=request.reform, **employer)
        return Behavioural(**computed.as_dict())

    weights = households["weight"].to_numpy()
    # Taxable base per household: what C1's response applies to. Deciles of it give
    # the top-decile split the two ETI parameters need.
    base = households["n_earners"].to_numpy() * 0.0
    frame_base = (
        frame.group_by("household_id")
        .agg(__import__("polars").col("salaire_brut_annuel").sum().alias("base"))
        .sort("household_id")
    )
    lookup = dict(zip(frame_base["household_id"].to_list(),
                      frame_base["base"].to_list(), strict=False))
    base = np.array([lookup.get(h, 0.0) for h in households["household_id"].to_list()])
    order = np.argsort(base)
    cumulative = np.cumsum(weights[order])
    top = np.zeros(len(base), dtype=bool)
    if cumulative[-1] > 0:
        top[order[cumulative >= 0.9 * cumulative[-1]]] = True

    computed = band_module.compute(
        mechanical=mechanical, reform=request.reform,
        **employer,
        emtr_baseline=households["emtr"].to_numpy(),
        emtr_reform=households["emtr_reform"].to_numpy(),
        taxable_base=base, weights=weights, top_decile=top,
    )
    payload = computed.as_dict()
    payload["emtr_households"] = int(households.height)
    return Behavioural(**payload)


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
            impute_niches=getattr(request, "impute_niches", False),
        )
    except WiringError as error:  # pragma: no cover - guarded upstream
        raise HTTPException(status_code=500, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    agg = aggregate_module.aggregate(result.households)
    summary = _baseline_summary()
    behavioural = (
        _behavioural(request, frame, agg, result.households)
        if request.behavioural else None
    )
    narrow_band = _narrow_band(request, result.households, frame)
    blind_spot = _niche_blind_spot(request, agg)
    macro = _macro(request, agg) if getattr(request, "macro", False) else None
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
        reform_cost=agg.reform_cost, behavioural=behavioural,
        narrow_band=narrow_band, macro=macro, niche_blind_spot=blind_spot,
        deciles=[DecileRow.model_validate(vars(row)) for row in agg.deciles],
        reconciliation=[
            ReconciliationLine.model_validate(line) for line in summary["reconciliation"]
        ],
        timings={
            **{k: float(v) for k, v in result.timings.items()},
            "total_s": round(time.perf_counter() - started, 2),
        },
    )


# --------------------------------------------------------------------------- #
# Firms (L0/L2 for entreprises)
# --------------------------------------------------------------------------- #
# It names the parquet read below, so it takes the vintage rule (D-173).
FIRM_VINTAGE = millesime(os.environ.get("IMPOTS_FIRM_VINTAGE", "fixture"))

FIRM_NOTE = (
    "Population d'entreprises synthétique : effectifs et agrégats par secteur × taille "
    "issus de sources publiques, financiers de chaque entreprise tirés paramétriquement "
    "à l'intérieur de sa cellule. Résultats au niveau secteur × taille uniquement — "
    "aucun résultat par entreprise, aucune affirmation sur le haut de la distribution. "
    "La CFE n'est pas simulée : elle dépend de valeurs locatives communales et de "
    "milliers de taux locaux, et une imitation plausible serait pire qu'un trou déclaré."
)

FIRM_LIMITATIONS = [
    "**Le niveau de l'IS est calibré, son taux ne l'est pas.** Le ratio "
    "fiscal/comptable de la table de cellules est calculé pour reproduire exactement "
    "le bénéfice imposable publié par la DGFiP : atteindre le total d'IS publié est "
    "donc de l'arithmétique. Ce qui reste libre — et ce qu'il faut lire — est le taux "
    "moyen produit par le barème sur une distribution synthétique, et les lignes par "
    "secteur (D-027).",
    "**Trois des six lignes sectorielles sont hors tolérance** : industrie +74 %, "
    "activités immobilières −91 %, information et communication −70 %. Deux "
    "hypothèses sont consignées, aucune n'a été testée.",
    "**Aucun financier d'entreprise n'est observé.** SIRENE donne les effectifs par "
    "cellule, ESANE les agrégats ; ni l'un ni l'autre ne publie une entreprise. Tout "
    "montant individuel est un tirage paramétrique dans une cellule publiée.",
    "**Pas de report déficitaire.** Les déficits d'une vraie entreprise réduisent son "
    "impôt les années suivantes ; il faudrait des panels d'entreprises qui ne sont pas "
    "en accès libre. Ce biais pousse l'IS simulé vers le haut, mécaniquement.",
    "**Pas d'intégration fiscale.** Les groupes sont modélisés comme des unités légales "
    "indépendantes, ce qui surestime le nombre d'entreprises au taux réduit.",
    "**Pas de crédits d'impôt** (CIR et autres) : l'IS simulé est un IS avant créances.",
    "**Le ratio fiscal/comptable est un scalaire national unique.** Le résultat fiscal "
    "n'est pas le résultat comptable, et aucune source ouverte ne publie l'écart par "
    "entreprise. Ce seul choix domine l'écart sur l'IS.",
    "**Exercices supposés calendaires.** SIRENE et ESANE ne portent pas de dates "
    "d'exercice, alors que le taux normal bascule sur les exercices *ouverts* et la "
    "tranche à taux réduit sur les exercices *clos* (D-020).",
    "**L'assiette de CVAE est approchée par la valeur ajoutée comptable.** Les loyers, "
    "le crédit-bail et la location-gérance sont des consommations intermédiaires en "
    "comptabilité mais ne sont pas déductibles de la valeur ajoutée fiscale : la CVAE "
    "simulée est donc sous-estimée, d'autant plus que l'entreprise loue ses actifs. Le "
    "biais est corrélé au secteur, il ne se corrige donc pas par un facteur global "
    "(D-021).",
    "**La C3S est assise sur le chiffre d'affaires de l'année précédente**, que la "
    "population n'a pas : elle est donc calculée sur celui de l'année simulée. La C3S "
    "simulée est surestimée d'environ une année de croissance nominale du chiffre "
    "d'affaires, et les entreprises ayant franchi l'abattement de 19 M€ en cours "
    "d'année sont placées du mauvais côté (D-021).",
    "**La CEBGE est calculée sur un seul exercice.** Son assiette légale est la moyenne "
    "de l'IS de deux exercices et ses seuils se testent sur deux années ; la population "
    "n'a qu'une année, donc l'exercice précédent est supposé identique. Les entrées et "
    "sorties de champ créées par le seuil de 1,5 Md€ du second exercice — précisément là "
    "où le rendement 2026 se joue — ne sont pas représentées (D-022).",
]


@lru_cache(maxsize=1)
def _firm_population() -> Any:
    import polars as pl

    from impots.entreprises.build import PROCESSED as FIRM_PROCESSED

    path = FIRM_PROCESSED / f"firms_{FIRM_VINTAGE}.parquet"
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail="Aucune population d'entreprises n'a été construite. Lancez "
                   "`impots entreprises build`.",
        )
    return pl.read_parquet(path)


def _firm_response(
    aggregates: Any, year: int, timings: dict[str, float], request: Any = None
) -> FirmResponse:
    from impots.entreprises.build import PROCESSED as FIRM_PROCESSED

    manifest = FIRM_PROCESSED / f"firms_{FIRM_VINTAGE}.manifest.json"
    synthetic = True
    if manifest.exists():
        synthetic = bool(json.loads(manifest.read_text(encoding="utf-8"))["cells_are_synthetic"])
    note = FIRM_NOTE
    if synthetic:
        note = (
            "ATTENTION : population construite à partir de cellules synthétiques de test, "
            "pas de SIRENE × ESANE. Rien de ce qui suit n'est une affirmation sur la "
            "France. " + note
        )
    return FirmResponse(
        meta=FirmMeta(
            vintage=FIRM_VINTAGE, year=year, cells_are_synthetic=synthetic,
            n_firms=aggregates.n_firms, turnover=aggregates.turnover,
            share_zero_is=aggregates.share_zero_is,
            note=note, limitations=FIRM_LIMITATIONS,
        ),
        totals=aggregates.totals,
        totals_reform=aggregates.totals_reform,
        deltas=aggregates.deltas,
        reform_cost=aggregates.reform_cost,
        cells=[FirmCell.model_validate(vars(cell)) for cell in aggregates.cells],
        by_size=[FirmSizeRow.model_validate(vars(row)) for row in aggregates.by_size],
        behavioural=(_firm_behavioural(request, aggregates) if request is not None
                     and aggregates.deltas else None),
        timings=timings,
    )


@app.get("/entreprises/baseline", response_model=FirmResponse)
def firms_baseline(year: int = Query(default=2026, ge=2022, le=2030)) -> FirmResponse:
    """Current-law firm aggregates, incidence table and effective-rate profile."""
    from impots.entreprises import aggregate as firm_aggregate
    from impots.entreprises import runner as firm_runner

    started = time.perf_counter()
    result = firm_runner.run(_firm_population(), year=year)
    aggregates = firm_aggregate.aggregate(result.firms)
    return _firm_response(
        aggregates, year,
        {**result.timings, "total_s": round(time.perf_counter() - started, 3)},
    )


def _firm_behavioural(request: Any, agg: Any) -> Any:
    """The investment band for a production-tax reform, reported in per cent.

    Never folded into the revenue figures: investment is not revenue, and the band is
    centred on zero because the evaluation behind it found nothing robust (D-037).
    """
    from impots.api.schemas import Behavioural
    from impots.behavioural import band as band_module

    baseline_tax = agg.totals.get("cvae", 0.0)
    reformed_tax = agg.totals_reform.get("cvae", baseline_tax)
    computed = band_module.compute(
        mechanical=-(agg.reform_cost or 0.0), reform=request.reform,
        production_tax_baseline=baseline_tax, production_tax_reform=reformed_tax,
    )
    return Behavioural(**computed.as_dict())


@app.post("/entreprises/simulate", response_model=FirmResponse)
def firms_simulate(request: FirmSimulateRequest) -> FirmResponse:
    """Price a firm-tax reform. Synchronous: the whole population runs in
    milliseconds, so there is no quick tier here."""
    from impots.entreprises import aggregate as firm_aggregate
    from impots.entreprises import runner as firm_runner

    started = time.perf_counter()
    try:
        result = firm_runner.run(_firm_population(), year=request.year, reform=request.reform)
    except firm_runner.FirmRunError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    aggregates = firm_aggregate.aggregate(result.firms)
    return _firm_response(
        aggregates, request.year,
        {**result.timings, "total_s": round(time.perf_counter() - started, 3)},
        request=request,
    )


@app.get("/scenarios", response_model=ScenarioListResponse)
def scenarios_list() -> ScenarioListResponse:
    """The registered scenarios (F2). Reads files; never runs the engine.

    Read only, and there is no POST. A scenario's value is its DATE, and a date the HTTP
    surface can mint is a date anyone can mint — registration belongs in the CLI, where
    it lands in the working tree and gets committed (D-092).
    """
    from impots import scenarios as scenarios_module

    summaries, unreadable = [], {}
    for name in scenarios_module.available():
        try:
            scenario = scenarios_module.load(name)
        except scenarios_module.ScenarioError as error:
            unreadable[name] = str(error)
            continue
        summaries.append(_scenario_summary(scenario))
    return ScenarioListResponse(scenarios=summaries, unreadable=unreadable)


@app.get("/scenarios/{name}", response_model=ScenarioDetail)
def scenarios_show(name: str) -> ScenarioDetail:
    """One scenario with its reform, so the UI can load it into the knob panel."""
    from impots import scenarios as scenarios_module

    if name not in scenarios_module.available():
        raise HTTPException(status_code=404, detail=f"scénario « {name} » inconnu")
    try:
        scenario = scenarios_module.load(name)
    except scenarios_module.ScenarioError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return ScenarioDetail(reform=scenario.reform, **vars(_scenario_summary(scenario)))


def _scenario_summary(scenario: Any) -> ScenarioSummary:
    return ScenarioSummary(
        name=scenario.name, year=scenario.year, created=scenario.created,
        source=scenario.source, note=scenario.note, tags=list(scenario.tags),
        knobs=sorted(scenario.reform.model_dump(exclude_none=True)),
    )


TRAJECTORIES = Path(__file__).resolve().parents[3] / "reports"


@app.get("/trajectoires", response_model=TrajectoryListResponse)
def trajectoires_list() -> TrajectoryListResponse:
    """Precomputed trajectories. Reads files; never runs the engine.

    A trajectory is N population runs twice over — one per year for the frozen and the
    aged population — so it is a batch job and lives in the CLI, like every other
    population run (§1.1).
    """
    return TrajectoryListResponse(trajectoires=sorted(
        path.stem.removeprefix("trajectoire_")
        for path in TRAJECTORIES.glob("trajectoire_*.json")))


@app.get("/trajectoires/{name}", response_model=TrajectoryResponse)
def trajectoires_show(name: str) -> TrajectoryResponse:
    from impots.scenarios import ScenarioError, _check_name

    try:
        _check_name(name)
    except ScenarioError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    path = TRAJECTORIES / f"trajectoire_{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"trajectoire « {name} » inconnue")
    return TrajectoryResponse.model_validate_json(path.read_text(encoding="utf-8"))


@app.get("/emtr", response_model=EmtrCurveListResponse)
def emtr_list() -> EmtrCurveListResponse:
    """Precomputed EMTR sweeps. Reads files; never runs the engine (four full-tier runs)."""
    return EmtrCurveListResponse(courbes=sorted(
        path.stem.removeprefix("emtr_") for path in TRAJECTORIES.glob("emtr_*.json")))


@app.get("/emtr/{name}", response_model=EmtrCurveResponse)
def emtr_show(name: str) -> EmtrCurveResponse:
    from impots.scenarios import ScenarioError, _check_name

    try:
        _check_name(name)
    except ScenarioError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    path = TRAJECTORIES / f"emtr_{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"courbe « {name} » inconnue")
    return EmtrCurveResponse.model_validate_json(path.read_text(encoding="utf-8"))


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve the static UI so the quickstart is one command instead of two.

    Opening `ui/index.html` straight off the filesystem works just as well; that is
    what the permissive CORS policy above is for.
    """
    if not UI_FILE.exists():  # pragma: no cover - only if the repo is incomplete
        raise HTTPException(status_code=404, detail="ui/index.html introuvable")
    return FileResponse(UI_FILE, media_type="text/html")
