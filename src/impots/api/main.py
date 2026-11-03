"""FastAPI app: the household calculator (Phase 0 §4) and the population (Phase 1 §6).

Five endpoints and a warm-up. The warm-up matters more than it looks: building
the tax-benefit system costs ~3 s and openfisca's first computation in a process
costs ~2 s more, so without it the first user of a fresh server waits five seconds
for a request the spec budgets at 1.5.

Population runs are batch jobs; only the bounded quick tier is reachable over
HTTP, and `GET /population/baseline` reads a precomputed file rather than running
the engine at all.

The security pass (D-295, `impots.api.securite`) sits in front of every route: no
third-party CORS origin unless declared, a key for every computation, a rate per client,
and one population pass at a time. Its defaults are closed; `IMPOTS_AUTH=aucune` opens the
computations for local use.
"""

from __future__ import annotations

import functools
import json
import logging
import math
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from impots import service
from impots.api.schemas import (
    MAX_YEAR,
    MIN_YEAR,
    QUICK_TIER_HOUSEHOLDS,
    DecileRow,
    EmtrCurveListResponse,
    EmtrCurveResponse,
    EmtrDecile,
    ExplorationReport,
    ExplorationReportList,
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
    PredictifReportList,
    PredictifReportResponse,
    PredictifRequest,
    PredictifResponse,
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
from impots.api.securite import Cors, Securite, configuration
from impots.engine import baseline, compute, versions, warm_up
from impots.engine.reforms import read_ir_parameters

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
    """Pay the cold-start cost before the first request rather than inside it.

    The security settings are read first: an unreadable one stops the server here rather
    than closing every request later (D-295)."""
    security = configuration()
    log = logging.getLogger("impots")
    if security.auth == "cle" and not security.cles_sha256:
        log.warning("No access key configured (IMPOTS_CLES_SHA256): every computation "
                    "answers 503. For local use, start with IMPOTS_AUTH=aucune.")
    if security.auth == "aucune" and not _is_loopback_only():
        log.warning("IMPOTS_AUTH=aucune while bound beyond localhost: anyone who can "
                    "reach this server can run computations without a key.")
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
# Outermost last: the CORS answers preflights and labels every response, refusals
# included; the security pass refuses before the body is read and the route runs.
app.add_middleware(Securite)
app.add_middleware(Cors)



def _served(endpoint: Any) -> Any:
    """An endpoint whose service refusals (`service.ServiceError`) are HTTP errors of the
    same status and reason. The service carries no server; the API gives it one."""

    @functools.wraps(endpoint)
    def served(*args: Any, **kwargs: Any) -> Any:
        try:
            return endpoint(*args, **kwargs)
        except service.ServiceError as error:
            raise HTTPException(status_code=error.status_code,
                                detail=error.detail) from error

    return served



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


@app.get("/population/baseline", response_model=PopulationResponse)
@_served
def population_baseline() -> PopulationResponse:
    """Precomputed baseline aggregates, decile table and reconciliation summary.

    Reads a file; never runs the engine. A full-tier population run is minutes.
    """
    summary = service.baseline_summary()
    return PopulationResponse(
        meta=PopulationMeta(
            vintage=summary["vintage"], branch=summary["branch"],
            households=summary["households"], persons=summary["persons"],
            tier="full", sampled_households=summary.get("sampled_households"),
            note=service.POPULATION_NOTE, limitations=summary["limitations"],
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


@app.post("/population/simulate", response_model=PopulationResponse)
@_served
def population_simulate(request: PopulationSimulateRequest) -> PopulationResponse:
    """Price a reform over the synthetic population — quick tier only.

    A deterministic, self-weighting subsample of 20 000 households. The full
    199 451-household run is a batch job and lives in the CLI: putting it behind a
    synchronous HTTP request would be a request that takes minutes (spec §1.1).
    """
    frame = service.population_frame()
    started = time.perf_counter()
    result, agg = service.run_population(request, frame)
    summary = service.baseline_summary()
    behavioural = (
        service.behavioural(request, frame, agg, result)
        if request.behavioural else None
    )
    narrow_band = service.narrow_band(request, result)
    blind_spot = service.niche_blind_spot(request, agg)
    macro = service.macro(request, agg) if getattr(request, "macro", False) else None
    return PopulationResponse(
        meta=PopulationMeta(
            vintage=service.POPULATION_VINTAGE, branch=summary["branch"],
            households=agg.households, persons=agg.persons,
            tier="quick", sampled_households=QUICK_TIER_HOUSEHOLDS,
            note=service.quick_tier_note(), limitations=summary["limitations"],
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


def _firm_response(
    aggregates: Any, year: int, timings: dict[str, float], request: Any = None
) -> FirmResponse:
    from impots.entreprises.build import PROCESSED as FIRM_PROCESSED

    manifest = FIRM_PROCESSED / f"firms_{service.FIRM_VINTAGE}.manifest.json"
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
            vintage=service.FIRM_VINTAGE, year=year, cells_are_synthetic=synthetic,
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
        behavioural=(service.firm_behavioural(request, aggregates) if request is not None
                     and aggregates.deltas else None),
        timings=timings,
    )


@app.get("/entreprises/baseline", response_model=FirmResponse)
@_served
def firms_baseline(year: int = Query(default=2026, ge=2022, le=2030)) -> FirmResponse:
    """Current-law firm aggregates, incidence table and effective-rate profile."""
    from impots.entreprises import aggregate as firm_aggregate
    from impots.entreprises import runner as firm_runner

    started = time.perf_counter()
    result = firm_runner.run(service.firm_population(), year=year)
    aggregates = firm_aggregate.aggregate(result.firms)
    return _firm_response(
        aggregates, year,
        {**result.timings, "total_s": round(time.perf_counter() - started, 3)},
    )


@app.post("/entreprises/simulate", response_model=FirmResponse)
@_served
def firms_simulate(request: FirmSimulateRequest) -> FirmResponse:
    """Price a firm-tax reform. Synchronous: the whole population runs in
    milliseconds, so there is no quick tier here."""
    from impots.entreprises import aggregate as firm_aggregate
    from impots.entreprises import runner as firm_runner

    started = time.perf_counter()
    try:
        result = firm_runner.run(service.firm_population(), year=request.year, reform=request.reform)
    except firm_runner.FirmRunError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    aggregates = firm_aggregate.aggregate(result.firms)
    response = _firm_response(
        aggregates, request.year,
        {**result.timings, "total_s": round(time.perf_counter() - started, 3)},
        request=request,
    )
    response.cir = service.firm_cir(request)
    return response


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


@app.get("/predictif", response_model=PredictifReportList)
def predictif_list() -> PredictifReportList:
    """Precomputed debt paths, every year priced (`impots predictif`). Reads files; never
    runs the engine: ten years in two views is about an hour of population passes."""
    return PredictifReportList(rapports=sorted(
        path.stem.removeprefix("predictif_")
        for path in TRAJECTORIES.glob("predictif_*.json")))


@app.get("/predictif/{name}", response_model=PredictifReportResponse)
def predictif_show(name: str) -> PredictifReportResponse:
    from impots.scenarios import ScenarioError, _check_name

    try:
        _check_name(name)
    except ScenarioError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    path = TRAJECTORIES / f"predictif_{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"trajectoire de dette « {name} » inconnue")
    return PredictifReportResponse.model_validate_json(path.read_text(encoding="utf-8"))


@app.get("/explorations", response_model=ExplorationReportList)
def explorations_list() -> ExplorationReportList:
    """Precomputed searches (`impots exploration`). Reads files; never runs the engine: a
    search is two population passes per bundle (PHASE10_SPEC §3)."""
    return ExplorationReportList(explorations=sorted(
        path.stem.removeprefix("exploration_")
        for path in TRAJECTORIES.glob("exploration_*.json")))


@app.get("/explorations/{name}", response_model=ExplorationReport)
def explorations_show(name: str) -> ExplorationReport:
    from pydantic import ValidationError

    from impots.scenarios import ScenarioError, _check_name

    try:
        _check_name(name)
    except ScenarioError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    path = TRAJECTORIES / f"exploration_{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"exploration « {name} » inconnue")
    try:
        return ExplorationReport.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as error:
        raise HTTPException(
            status_code=500,
            detail=f"exploration « {name} » illisible, refusée plutôt que montrée en "
                   f"partie : {error}") from error


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


@app.post("/predictif/simulate", response_model=PredictifResponse)
@_served
def predictif_simulate(request: PredictifRequest) -> PredictifResponse:
    """The reform's debt path against the reference, under named scenarios (PHASE9_SPEC §3):
    the service's (`service.predictif_simulate`), its refusals given their status."""
    return service.predictif_simulate(request)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve the static UI so the quickstart is one command instead of two.

    Served here, the page and the API share one origin and need no CORS. Opening
    `ui/index.html` straight off the filesystem no longer reaches the API: its origin is
    `null`, which the security pass never allows (D-295).
    """
    if not UI_FILE.exists():  # pragma: no cover - only if the repo is incomplete
        raise HTTPException(status_code=404, detail="ui/index.html introuvable")
    return FileResponse(UI_FILE, media_type="text/html")
