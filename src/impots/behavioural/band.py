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
    results.append(channel_module.employment_at_the_smic(store, reform))
    results.append(channel_module.contribution_incidence(store, reform))
    results.append(channel_module.production_tax_investment(
        store, reform, mechanical_delta=mechanical, draws=draws, rng=rng,
    ))

    metrics: dict[str, tuple[tuple[str, ...], float]] = {}
    if have_household_inputs and any(r.key == "c1_eti" and r.applies for r in results):
        metrics["c1_eti"] = (
            channel_module.C1_KEYS,
            grading_module.induced_variation(emtr_baseline, emtr_reform, weights),
        )
    if any(r.key == "c4_investment" and r.applies for r in results):
        metrics["c4_investment"] = (channel_module.C4_KEYS, 0.0)

    verdict = grading_module.grade(store, metrics)

    live = [r for r in results if r.applies and r.draws is not None]
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
