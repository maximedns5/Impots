"""Assembling the band (PHASE3_SPEC §1, §3, §4).

One seed, in one place. Identical inputs give an identical band to the last digit,
which is golden-tested — a band that moved between runs would be indistinguishable
from a band that moved because the evidence changed.

The output's shape is deliberate. The mechanical figure comes first and unmodified;
the band is a *range around* it; and the grade says how much the range is worth. A
reader who takes only the first number is not misled, and a reader who takes all
three knows more.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from impots.behavioural import channels as channel_module
from impots.behavioural import grading as grading_module
from impots.behavioural.store import Store, load

#: One seed, one place (§1). Changing it changes every published band, so it is a
#: constant with a name rather than a default argument in five functions.
SEED = 20260902

#: §8 requires p10/p90 stable to under 1 % between N=1 000 and N=4 000.
DRAWS = 1_000


@dataclass
class Band:
    p10: float
    p50: float
    p90: float
    unit: str = "EUR"

    @classmethod
    def of(cls, draws: np.ndarray, unit: str = "EUR") -> Band:
        p10, p50, p90 = (float(x) for x in np.percentile(draws, [10, 50, 90]))
        return cls(p10=p10, p50=p50, p90=p90, unit=unit)


@dataclass
class BehaviouralResult:
    mechanical: float
    band: Band | None
    grade: str
    grade_reason: str
    channels: list[dict[str, Any]] = field(default_factory=list)
    seed: int = SEED
    draws: int = DRAWS
    parameters_vintage: str = ""
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "mechanical": self.mechanical,
            "band": None if self.band is None else asdict(self.band),
            "grade": self.grade,
            "grade_reason": self.grade_reason,
            "channels": self.channels,
            "seed": self.seed,
            "draws": self.draws,
            "parameters_vintage": self.parameters_vintage,
            "notes": self.notes,
        }


def compute(
    *,
    mechanical: float,
    reform: Any,
    store: Store | None = None,
    emtr_baseline: np.ndarray | None = None,
    emtr_reform: np.ndarray | None = None,
    taxable_base: np.ndarray | None = None,
    weights: np.ndarray | None = None,
    top_decile: np.ndarray | None = None,
    smic_multiple: np.ndarray | None = None,
    relative_cost_change: np.ndarray | None = None,
    earner_weights: np.ndarray | None = None,
    contribution_delta: float | None = None,
    production_tax_baseline: float | None = None,
    production_tax_reform: float | None = None,
    labour_group: np.ndarray | None = None,
    labour_earnings: np.ndarray | None = None,
    labour_delta_log_net: np.ndarray | None = None,
    labour_weights: np.ndarray | None = None,
    labour_emtr: np.ndarray | None = None,
    is_rate_change_points: float | None = None,
    cir_margins: tuple[tuple[float, float], ...] | None = None,
    dividend_base_eur: float | None = None,
    dividend_base_cdhr_eur: float = 0.0,
    levy_rate_baseline: float | None = None,
    levy_rate_reform: float | None = None,
    wage_levy_rate: float | None = None,
    wage_cost_rate: float | None = None,
    corporate_rate: float | None = None,
    self_financing_value_per_job: float | None = None,
    self_financing_refused: str | None = None,
    draws: int = DRAWS,
    seed: int = SEED,
) -> BehaviouralResult:
    """The band around a mechanical figure, with its channels and its grade."""
    store = store if store is not None else load()
    rng = np.random.default_rng(seed)

    results: list[channel_module.ChannelResult] = []
    have_household_inputs = all(
        array is not None for array in (emtr_baseline, emtr_reform, taxable_base, weights)
    )
    if have_household_inputs:
        results.append(channel_module.elasticity_of_taxable_income(
            store, reform, emtr_baseline=emtr_baseline, emtr_reform=emtr_reform,
            taxable_base=taxable_base, weights=weights,
            top_decile=(top_decile if top_decile is not None
                        else np.zeros(len(weights), dtype=bool)),
            draws=draws, rng=rng,
        ))
    results.append(channel_module.employment_at_the_smic(
        store, reform, smic_multiple=smic_multiple,
        relative_cost_change=relative_cost_change, weights=earner_weights,
        draws=draws, rng=rng,
    ))
    results.append(channel_module.contribution_incidence(
        store, reform, contribution_delta=contribution_delta, draws=draws, rng=rng,
    ))
    if production_tax_baseline is not None and production_tax_reform is not None:
        results.append(channel_module.production_tax_investment(
            store, reform, production_tax_baseline=production_tax_baseline,
            production_tax_reform=production_tax_reform, draws=draws, rng=rng,
        ))
    else:
        results.append(channel_module.production_tax_investment(store, reform))
    # C7 last, so that the draws of C1-C4 — and the golden band of D-217 — are untouched.
    results.append(channel_module.labour_supply(
        store, reform, labour_group=labour_group, labour_earnings=labour_earnings,
        labour_delta_log_net=labour_delta_log_net, labour_weights=labour_weights,
        labour_emtr=labour_emtr, draws=draws, rng=rng,
    ))
    # C8 after C7, for the same reason.
    results.append(channel_module.firm_creations(
        store, reform, is_rate_change_points=is_rate_change_points, draws=draws, rng=rng,
    ))
    results.append(channel_module.rd_response(
        store, reform, cir_margins=cir_margins, draws=draws, rng=rng,
    ))
    # C10 last, for the same reason as C7 and C8 (D-249).
    results.append(channel_module.dividend_response(
        store, reform, dividend_base_eur=dividend_base_eur,
        dividend_base_cdhr_eur=dividend_base_cdhr_eur,
        levy_rate_baseline=levy_rate_baseline, levy_rate_reform=levy_rate_reform,
        wage_levy_rate=wage_levy_rate, wage_cost_rate=wage_cost_rate,
        corporate_rate=corporate_rate, draws=draws, rng=rng,
    ))
    # C11 after C10, for the same reason (D-256). Its θ = 0 is C2's jobs, draw by draw.
    jobs = next(r for r in results if r.key == "c2_employment")
    results.append(channel_module.targeted_self_financing(
        store, reform, contribution_delta=contribution_delta,
        c2_jobs=jobs.draws if jobs.applies else None,
        value_per_job=self_financing_value_per_job, not_targeted=self_financing_refused,
        draws=draws, rng=rng,
    ))

    metrics: dict[str, tuple[tuple[str, ...], float]] = {}
    if relative_cost_change is not None and len(relative_cost_change):
        metrics["c2_employment"] = (
            channel_module.C2_KEYS, float(np.max(np.abs(relative_cost_change)))
        )
    if contribution_delta:
        metrics["c3_incidence"] = (channel_module.C3_KEYS, 0.0)
    if have_household_inputs and any(r.key == "c1_eti" and r.applies for r in results):
        metrics["c1_eti"] = (
            channel_module.C1_KEYS,
            grading_module.induced_variation(emtr_baseline, emtr_reform, weights),
        )
    if any(r.key == "c4_investment" and r.applies for r in results):
        metrics["c4_investment"] = (channel_module.C4_KEYS, 0.0)
    if (any(r.key == "c7_labour_supply" and r.applies for r in results)
            and labour_delta_log_net is not None and len(labour_delta_log_net)):
        metrics["c7_labour_supply"] = (
            channel_module.C7_KEYS, float(np.max(np.abs(labour_delta_log_net))))
    if (any(r.key == "c9_rd" and r.applies for r in results)
            and cir_margins is not None):
        metrics["c9_rd"] = (channel_module.C9_KEYS,
                            abs(sum(delta for delta, _ in cir_margins)))
    dividends = next((r for r in results if r.key == "c10_dividendes" and r.applies), None)
    if dividends is not None:
        # In the support's units: the relative change of the net-of-tax rate. The share
        # row is a composition, not a response, and is not graded; the wage shift answers
        # the same variation, measured on the same reforms, and is (D-252).
        metrics["c10_dividendes"] = (
            (*channel_module.C10_ELASTICITIES, channel_module.C10_WAGE_SHIFT),
            abs(dividends.diagnostics["net_of_tax_relative_change"]))
    if any(r.key == "c11_autofinancement" and r.applies for r in results):
        # It rests on C2's jobs at θ = 0, and on C2's rows for its grade: they cannot say
        # how far they carry, so neither can it (D-256).
        metrics["c11_autofinancement"] = (
            (*channel_module.C2_KEYS, *channel_module.C11_KEYS),
            metrics["c2_employment"][1])
    creations = next((r for r in results if r.key == "c8_creations" and r.applies), None)
    if creations is not None:
        # In the driver's units, as the support is: points of the virtual rate.
        metrics["c8_creations"] = (
            channel_module.C8_KEYS, abs(creations.diagnostics["virtual_rate_fall_points"]))

    verdict = grading_module.grade(store, metrics)

    # Only channels that actually move state revenue enter the headline band, and
    # each one says so itself. Inferring it from the unit would put C3 in — it is
    # denominated in euros and reallocates them, so the mechanical total is the same
    # at both ends of its range and adding it would count the same euros twice.
    live = [r for r in results if r.applies and r.draws is not None and r.in_revenue_band]
    band = None
    if live:
        # Channels are summed draw by draw at a shared seed, so their correlation is
        # the one the store implies rather than an artefact of independent sampling.
        total = np.sum([r.draws for r in live], axis=0) + mechanical
        band = Band.of(grading_module.widen(total, verdict.widening))

    return BehaviouralResult(
        mechanical=mechanical,
        band=band,
        grade=verdict.grade,
        grade_reason=verdict.reason,
        channels=[
            {"key": r.key, "label": r.label, "applies": r.applies,
             "central": r.central, "unit": r.unit, "message": r.message,
             # The channel's own band in the channel's own unit: left to the schema's
             # default, C4's percentages and C8's points were labelled euros.
             "band": (None if r.draws is None else
                      {"p10": float(np.percentile(r.draws, 10)),
                       "p50": float(np.percentile(r.draws, 50)),
                       "p90": float(np.percentile(r.draws, 90)),
                       "unit": r.unit}),
             "grade": verdict.per_channel.get(r.key),
             "diagnostics": r.diagnostics}
            for r in results
        ],
        seed=seed, draws=draws,
        parameters_vintage=store.vintage(),
        notes=([] if store.parameters else
               ["Aucune élasticité vérifiée n'est chargée : le chiffre est purement "
                "mécanique."]),
    )
