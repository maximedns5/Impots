"""Run the firm population through current law and, optionally, a reform (§4).

Synchronous, unlike the household side. The whole IS population is about 2 M
firms and this formula set computes 500 000 of them in hundredths of a second, so
there is no quick tier, no subsample machinery, and no batch job — a firm reform
is priced inside an HTTP request.

The guards are the household module's, hardened by its defects. `weight_identity`
is the one that matters: both Phase 1 weighting bugs multiplied every aggregate by
a constant while staying finite, positive and NaN-free, and §3.5 requires the
identity around every weighting step here as a result.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl
from openfisca_core.simulation_builder import SimulationBuilder

from impots import guards
from impots.entreprises.system import baseline, reformed_for

if TYPE_CHECKING:  # pragma: no cover - typing only
    from impots.entreprises.reforms import FirmReformSpec

#: What a run reports per firm, and therefore what the reform panel can move.
INSTRUMENTS = (
    "impot_societes",
    "contribution_sociale_is",
    "cebge",
    "cvae",
    "c3s",
    "prelevements_entreprise",
)

#: Inputs the population must supply. Anything missing is a build error, not a
#: default: a variable that silently takes its default computes a plausible tax
#: forever, which is the failure mode this project keeps finding.
REQUIRED_INPUTS = (
    "chiffre_affaires",
    "benefice_imposable",
    "valeur_ajoutee",
    "capital_libere_detenu_personnes_physiques",
)


class FirmRunError(RuntimeError):
    """The population cannot be run as it stands."""


@dataclass
class FirmRunResult:
    firms: pl.DataFrame
    """One row per firm: identifiers, weight, and each instrument, plus `_reform`
    columns when a reform was priced."""
    year: int
    n_firms: int
    timings: dict[str, float] = field(default_factory=dict)
    guards: dict[str, Any] = field(default_factory=dict)


def _simulate(system: Any, frame: pl.DataFrame, year: int) -> Any:
    builder = SimulationBuilder()
    builder.create_entities(system)
    builder.declare_person_entity("entreprise", np.arange(frame.height))
    simulation = builder.build(system)
    period = str(year)
    for name in REQUIRED_INPUTS:
        column = frame[name]
        values = (
            column.to_numpy().astype(bool)
            if column.dtype == pl.Boolean
            else column.to_numpy().astype(np.float64)
        )
        simulation.set_input(name, period, values)
    # The prior year's IS feeds the CEBGE's two-year average. A single-year run has
    # no memory of the year before, so the population carries it as an input.
    if "is_avant_report" in frame.columns:
        simulation.set_input(
            "is_avant_report", period, frame["is_avant_report"].to_numpy().astype(np.float64)
        )
    return simulation


def _extract(simulation: Any, year: int) -> dict[str, np.ndarray]:
    period = str(year)
    results: dict[str, np.ndarray] = {}
    for name in INSTRUMENTS:
        values = simulation.calculate(name, period).astype(np.float64)
        guards.no_nan(values, name)
        guards.non_negative(values, name)
        results[name] = values
    return results


def run(
    population: pl.DataFrame,
    year: int = 2026,
    reform: FirmReformSpec | None = None,
) -> FirmRunResult:
    """Price current law and, optionally, one reform over the firm population."""
    missing = set(REQUIRED_INPUTS) - set(population.columns)
    if missing:
        raise FirmRunError(f"population is missing required inputs {sorted(missing)}")
    if "weight" not in population.columns:
        raise FirmRunError("population has no weight column")

    diagnostics: dict[str, Any] = {}
    timings: dict[str, float] = {}

    turnover = population["chiffre_affaires"].to_numpy()
    guards.non_negative(turnover, "chiffre_affaires")
    # Value added above turnover is not impossible in published sector aggregates,
    # so it is counted and reported rather than fatal (§3.5).
    diagnostics["va_above_ca"] = guards.not_greater(
        population["valeur_ajoutee"].to_numpy(), turnover, "valeur_ajoutee <= chiffre_affaires"
    )

    started = time.perf_counter()
    columns = _extract(_simulate(baseline(), population, year), year)
    timings["baseline_s"] = round(time.perf_counter() - started, 3)

    if reform is not None and not reform.is_empty():
        started = time.perf_counter()
        reformed = _extract(_simulate(reformed_for(reform, year), population, year), year)
        timings["reform_s"] = round(time.perf_counter() - started, 3)
        for name, values in reformed.items():
            columns[f"{name}_reform"] = values

    keep = [
        name
        for name in ("firm_id", "weight", "naf_section", "taille", "categorie",
                     "chiffre_affaires", "valeur_ajoutee", "benefice_imposable")
        if name in population.columns
    ]
    firms = population.select(keep).with_columns(
        [pl.Series(name, values) for name, values in columns.items()]
    )

    # The weighted firm count and turnover must be exactly what went in: nothing in
    # a run reweights anything, so any drift here is a bug in the run itself.
    guards.weight_identity(
        population.with_columns(pl.lit(1.0).alias("_unit")),
        firms.with_columns(pl.lit(1.0).alias("_unit")),
        ["_unit", "chiffre_affaires"],
        step="firm run",
    )
    diagnostics["weighted_firms"] = float(firms["weight"].sum())
    diagnostics["weighted_turnover"] = guards.weighted_total(firms, "chiffre_affaires")

    return FirmRunResult(
        firms=firms,
        year=year,
        n_firms=firms.height,
        timings=timings,
        guards=diagnostics,
    )
