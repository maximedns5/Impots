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
import os
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
    SimulateRequest,
    SimulateResponse,
    Timings,
)
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


def _behavioural(request: Any, frame: Any, agg: Any) -> Any:
    """The band for a household reform, or a mechanical-only answer with its reason."""
    import numpy as np

    from impots.api.schemas import Behavioural
    from impots.behavioural import band as band_module
    from impots.behavioural import emtr as emtr_module

    mechanical = -(agg.reform_cost or 0.0)
    emtr_result = emtr_module.cached(
        frame, POPULATION_VINTAGE, year=request.year, reform=request.reform,
        sample=BEHAVIOURAL_EMTR_HOUSEHOLDS,
    )
    households = emtr_result.with_earnings
    if households.is_empty() or "emtr_reform" not in households.columns:
        computed = band_module.compute(mechanical=mechanical, reform=request.reform)
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
        )
    except WiringError as error:  # pragma: no cover - guarded upstream
        raise HTTPException(status_code=500, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    agg = aggregate_module.aggregate(result.households)
    summary = _baseline_summary()
    behavioural = _behavioural(request, frame, agg) if request.behavioural else None
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
FIRM_VINTAGE = os.environ.get("IMPOTS_FIRM_VINTAGE", "fixture")

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


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Serve the static UI so the quickstart is one command instead of two.

    Opening `ui/index.html` straight off the filesystem works just as well; that is
    what the permissive CORS policy above is for.
    """
    if not UI_FILE.exists():  # pragma: no cover - only if the repo is incomplete
        raise HTTPException(status_code=404, detail="ui/index.html introuvable")
    return FileResponse(UI_FILE, media_type="text/html")
