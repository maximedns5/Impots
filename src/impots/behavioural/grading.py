"""Applicability grading — the Lucas guardrail, in code (PHASE3_SPEC §4).

An elasticity is not a constant of nature. It is a number measured on the reforms
that happened, over the range of variation those reforms produced. Applied to a
reform ten times larger, it is an extrapolation, and the honest thing is to say so
*on the number* rather than in a footnote nobody reads.

So every band carries a grade:

* **in-support** — the reform's induced variation sits inside the range the estimate
  was identified on. The band means what it says.
* **illustrative** — beyond that range. The band is widened and labelled an
  extrapolation. Not suppressed: a reader asking "what if the response were of the
  measured order?" deserves an answer, but not a confident one.
* **no-evidence** — no channel claims this instrument. Mechanical only, and the
  reason said out loud.

The thresholds live in the parameter store, not here, so tightening the guardrail is
a data change with a diff rather than an edit to a conditional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from impots.behavioural.store import Store

Grade = Literal["in-support", "illustrative", "no-evidence"]

#: Multiplier applied to a band's half-width when the reform runs past the evidence.
#: Doubling is a convention, not a measurement, and it is named as one wherever it
#: appears — a widened band is a statement that the number is unreliable, not a
#: quantification of how unreliable.
DEFAULT_EXTRAPOLATION_WIDENING = 2.0


@dataclass
class Grading:
    grade: Grade
    metric: float | None = None
    """The reform's induced variation, in the channel's own units."""
    supported_up_to: float | None = None
    widening: float = 1.0
    reason: str = ""
    per_channel: dict[str, Grade] = field(default_factory=dict)

    @property
    def is_extrapolation(self) -> bool:
        return self.grade == "illustrative"


def induced_variation(
    emtr_ir_baseline: np.ndarray, emtr_ir_reform: np.ndarray, weights: np.ndarray,
    taxable_base: np.ndarray,
) -> float:
    """C1's metric: how far the reform moves the net-of-income-tax marginal rate WHERE C1
    IS MADE (D-336, decision 4).

    The median of |Δ(1 − τ_IR)| weighted by each household's contribution to C1, its
    weight × base × |Δln(1 − τ_IR)|. Before, the 95th percentile of the households: a
    tranche that touched the last percentile left it at zero, and the reform C1 bites
    hardest on was graded in support (Tondelier, D-333). Weighted by contribution, a
    reform of the top alone is graded on the top, where its C1 is; and a household with no
    contribution weighs nothing, so a single extreme rate still cannot grade a reform.
    """
    from impots.behavioural.channels import NET_OF_TAX_FLOOR

    if not len(emtr_ir_baseline):
        return 0.0
    net_baseline = np.clip(1.0 - emtr_ir_baseline, NET_OF_TAX_FLOOR, None)
    net_reform = np.clip(1.0 - emtr_ir_reform, NET_OF_TAX_FLOOR, None)
    contribution = weights * taxable_base * np.abs(np.log(net_reform) - np.log(net_baseline))
    carries = contribution > 0
    if not carries.any():
        return 0.0
    moved = np.abs(emtr_ir_reform - emtr_ir_baseline)[carries]
    order = np.argsort(moved, kind="stable")
    cumulative = np.cumsum(contribution[carries][order])
    return float(np.interp(0.5 * cumulative[-1], cumulative, moved[order]))


def grade_channel(store: Store, keys: tuple[str, ...], metric: float) -> tuple[Grade, float | None]:
    """Grade one channel against the tightest support among the rows it rests on."""
    bounds = [
        store[key].support.max_variation_graded_in_support
        for key in keys
        if key in store
    ]
    if not bounds:
        return "no-evidence", None
    # An ungradeable support is not a permissive one. If any row the channel rests on
    # cannot say how far it may be carried, the channel cannot claim to be in support.
    if any(bound is None for bound in bounds):
        return "illustrative", None
    tightest = min(bound for bound in bounds if bound is not None)
    return ("in-support" if metric <= tightest else "illustrative"), tightest


def grade(
    store: Store,
    channel_metrics: dict[str, tuple[tuple[str, ...], float]],
) -> Grading:
    """The reform's overall grade: the weakest of the channels that actually fired.

    Weakest, not average. A band whose largest component is an extrapolation is an
    extrapolation, and averaging grades would let a well-supported small channel
    launder a badly-supported large one.
    """
    if not channel_metrics:
        return Grading(
            grade="no-evidence",
            reason="Aucun canal fondé sur des preuves ne couvre cet instrument : "
                   "le chiffre reste purement mécanique.",
        )
    per_channel: dict[str, Grade] = {}
    worst: Grade = "in-support"
    metric_reported: float | None = None
    supported: float | None = None
    ranking: dict[Grade, int] = {"in-support": 0, "illustrative": 1, "no-evidence": 2}
    for channel, (keys, metric) in channel_metrics.items():
        channel_grade, bound = grade_channel(store, keys, metric)
        per_channel[channel] = channel_grade
        if ranking[channel_grade] >= ranking[worst]:
            worst = channel_grade
            metric_reported, supported = metric, bound

    widening = store.thresholds.get(
        "extrapolation_widening", DEFAULT_EXTRAPOLATION_WIDENING
    )
    if worst == "in-support":
        reason = (
            "La variation induite par cette réforme reste dans l'intervalle sur lequel "
            "les élasticités ont été estimées."
        )
        widening = 1.0
    elif worst == "illustrative":
        reason = (
            "Cette réforme est plus grande que celles sur lesquelles les élasticités "
            "ont été estimées : la bande est une extrapolation, élargie et signalée "
            "comme telle."
        )
    else:
        reason = (
            "Aucun canal fondé sur des preuves ne couvre cet instrument : "
            "le chiffre reste purement mécanique."
        )
        widening = 1.0
    return Grading(
        grade=worst, metric=metric_reported, supported_up_to=supported,
        widening=widening, reason=reason, per_channel=per_channel,
    )


def widen(draws: np.ndarray, factor: float) -> np.ndarray:
    """Stretch a sample about its median without moving the median."""
    if factor == 1.0:
        return draws
    centre = np.median(draws)
    return centre + (draws - centre) * factor
