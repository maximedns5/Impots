"""Orchestration: household + year + reform + tier -> normalised results (spec §3.5).

One situation is built, then one `Simulation` per tax-benefit system. Simulations
are single-use snapshots bound to one TBS: a new request always builds a new one,
and a simulation is never carried across systems.

The EMTR has no variable in openfisca — there is no `taux_marginal_imposition`. It
is a finite difference: add 100 EUR/year of gross salary to the first adult and ask
how much of it survives into disposable income.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from openfisca_core.simulation_builder import SimulationBuilder

from impots.engine import outputs, situations
from impots.engine.system import baseline, reform_key, reformed, versions

if TYPE_CHECKING:  # pragma: no cover - typing only
    from impots.api.schemas import HouseholdInput, ReformSpec

Tier = Literal["light", "full"]

#: Gross-salary step of the EMTR finite difference, in EUR per year.
EMTR_STEP = 100.0


@dataclass
class ComputeResult:
    baseline: dict[str, Any]
    tier: Tier
    year: int
    historique_revenus: bool
    timings: dict[str, Any]
    engine: dict[str, str] = field(default_factory=versions)
    reform: dict[str, Any] | None = None
    delta: dict[str, Any] | None = None
    emtr: float | None = None
    emtr_reform: float | None = None


def _build(tax_benefit_system: Any, situation: dict[str, Any], year: int, tier: Tier) -> Any:
    """A simulation with every input set and the RFR of N-2 pinned before anything
    else is asked of it — see `situations.pin_rfr_n_2` (D-177) — and, for the full
    tier, the housing aid pinned month by month (`situations.pin_benefit_history`,
    D-178). The light tier never asks for a benefit and does not pay for the second.
    Nor does a household without housing inputs: it cannot receive housing aid, so it
    has no cascade to pin, and its full-tier request keeps its D-177 cost."""
    simulation = SimulationBuilder().build_from_entities(tax_benefit_system, situation)
    situations.pin_rfr_n_2(simulation, year)
    housed = "statut_occupation_logement" in situation["menages"][situations.MENAGE_ID]
    if tier == "full" and housed:
        situations.pin_benefit_history(simulation, year)
    return simulation


def _delta(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """`reform - baseline`, row by row.

    Signed on purpose: because every amount is a positive magnitude named for what
    it is, `delta["ir"] = +200` reads as "pays 200 EUR more income tax" and
    `delta["revenu_disponible"] = -150` as "150 EUR worse off".
    """
    out: dict[str, Any] = {}
    for key, new in after.items():
        if key == "raw":
            continue
        old = before.get(key)
        out[key] = None if (old is None or new is None) else round(new - old, 2)
    return out


def _emtr(
    tax_benefit_system: Any,
    situation: dict[str, Any],
    year: int,
    base_disposable: float,
) -> float:
    """1 - (share of an extra 100 EUR of gross salary that reaches disposable income).

    Needs the benefits cascade, hence full tier only: the taper of PPA and RSA is a
    large part of the marginal rate at low wages, and ignoring it would understate
    the real figure badly.
    """
    perturbed = situations.perturb_first_adult(situation, year, EMTR_STEP)
    simulation = _build(tax_benefit_system, perturbed, year, "full")
    bumped = float(simulation.calculate("revenu_disponible", str(year))[0])
    return round(1.0 - (bumped - base_disposable) / EMTR_STEP, 4)


def compute(
    household: HouseholdInput,
    year: int,
    reform: ReformSpec | None = None,
    tier: Tier = "light",
    emtr: bool = False,
    historique_revenus: bool = True,
    debug: bool = False,
) -> ComputeResult:
    """Run one household through current law and, optionally, through a reform."""
    if emtr and tier != "full":
        raise ValueError("le calcul du taux marginal effectif exige tier='full'")

    started = time.perf_counter()
    situation = situations.build_situation(household, year, historique_revenus)

    baseline_system = baseline()
    reformed_system = None
    cache_hit: bool | None = None
    if reform is not None and not reform.is_empty():
        key = reform_key(reform, year)
        before = reformed.cache_info().hits
        reformed_system = reformed(key)
        cache_hit = reformed.cache_info().hits > before

    build_ms = (time.perf_counter() - started) * 1000.0

    compute_started = time.perf_counter()
    baseline_rows = outputs.extract(
        _build(baseline_system, situation, year, tier), year, tier, debug)
    reform_rows = (
        outputs.extract(_build(reformed_system, situation, year, tier), year, tier, debug)
        if reformed_system is not None
        else None
    )
    compute_ms = (time.perf_counter() - compute_started) * 1000.0

    emtr_value: float | None = None
    emtr_reform_value: float | None = None
    emtr_ms: float | None = None
    if emtr:
        emtr_started = time.perf_counter()
        emtr_value = _emtr(baseline_system, situation, year, baseline_rows["revenu_disponible"])
        if reformed_system is not None and reform_rows is not None:
            emtr_reform_value = _emtr(
                reformed_system, situation, year, reform_rows["revenu_disponible"]
            )
        emtr_ms = (time.perf_counter() - emtr_started) * 1000.0

    return ComputeResult(
        baseline=baseline_rows,
        reform=reform_rows,
        delta=_delta(baseline_rows, reform_rows) if reform_rows is not None else None,
        emtr=emtr_value,
        emtr_reform=emtr_reform_value,
        tier=tier,
        year=year,
        historique_revenus=historique_revenus,
        timings={
            "build_ms": round(build_ms, 1),
            "compute_ms": round(compute_ms, 1),
            "emtr_ms": None if emtr_ms is None else round(emtr_ms, 1),
            "total_ms": round((time.perf_counter() - started) * 1000.0, 1),
            "reform_cache_hit": cache_hit,
        },
    )


def warm_up() -> float:
    """Build the TBS and run one throwaway light simulation.

    Called from the API startup hook so that the cost of loading 3 142 variables
    and of openfisca's lazy first-compute lands before the first user request
    rather than inside it (spec §7.7).
    """
    from impots.api.schemas import Adult, HouseholdInput

    started = time.perf_counter()
    compute(
        HouseholdInput(adults=[Adult(salaire_brut_annuel=30000.0, annee_naissance=1990)]),
        year=2024,
        tier="light",
    )
    return round((time.perf_counter() - started) * 1000.0, 1)
