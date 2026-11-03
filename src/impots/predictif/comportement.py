"""Phase 9 M2 — the behavioural receipts at θ, and the θ box around them.

The channels of Phase 3 run unchanged on the pinned store (`theta.pinned`): one draw, at
θ, instead of a thousand from the range. What comes back is the receipts total the band
would centre on if the evidence sat exactly there — the mechanical figure plus every
revenue channel at θ.

THE BOX (PHASE9_SPEC §3.5). The rows the reform's knobs claim are moved to 0 and to 1 —
2^K corners, K the number of open rows claimed, a handful at most — and the receipts at
the corners bound the receipts anywhere inside. That reading holds only if each channel is
monotone in its θ (§2.4, guard 7). A cheap check runs every time: the receipts at the θ
asked for must lie inside the corners' bounds, or the box is refused rather than drawn.

RECEIPTS POSITIVE, as `band.compute` returns them — the opposite sign of the engine's cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from impots.behavioural import band as band_module
from impots.behavioural import channels
from impots.behavioural.store import Store, load
from impots.predictif.theta import Theta, ThetaError, corners, pinned

#: Slack for the monotonicity check, in euros: float noise only.
MONOTONE_SLACK_EUR = 1.0


@dataclass(frozen=True)
class AtTheta:
    receipts: float
    """Mechanical plus every revenue channel at θ, RECEIPTS POSITIVE."""
    grade: str
    box: tuple[float, float]
    """Receipts at the box's lowest and highest corner."""
    claimed: tuple[str, ...]
    """The open rows the reform claims — the ones the box moves."""
    statistics: dict[str, Any] | None = None
    """The receipts channels' sufficient statistics, θ-free, by channel, and the share of
    C1 its floored households carry: what a report keeps to replay the receipts at any θ
    or draw without a pass (D-336, decision 6). None where nothing was evaluated."""


#: The channels whose statistics a replay reads: those in the receipts band, and C2, whose
#: jobs C11 prices.
REPLAYED = ("c1_eti", "c2_employment", "c7_labour_supply", "c10_dividendes",
            "c11_autofinancement")


def statistics_of(result: Any) -> dict[str, Any]:
    """The sufficient statistics of every applied channel a replay reads (D-336)."""
    out: dict[str, Any] = {}
    for channel in result.channels:
        if channel["applies"] and channel["key"] in REPLAYED:
            out[channel["key"]] = dict(channel["diagnostics"]["statistics"])
            if channel["key"] == "c1_eti":
                out["c1_floor_share"] = channel["diagnostics"]["share_at_the_net_of_tax_floor"]
    return out


def _run(theta: Theta, *, store: Store, mechanical: float, reform: Any,
         **inputs: Any) -> Any:
    return band_module.compute(mechanical=mechanical, reform=reform,
                               store=pinned(store, theta), draws=1, **inputs)


def receipts_at(theta: Theta, *, store: Store, mechanical: float, reform: Any,
                **inputs: Any) -> tuple[float, str]:
    result = _run(theta, store=store, mechanical=mechanical, reform=reform, **inputs)
    receipts = mechanical if result.band is None else float(result.band.p50)
    return receipts, result.grade


#: The rows a receipts channel reads: C1, C7, C10, C11, and C2, whose jobs C11 prices.
#: Only they enter the box: C3 reallocates euros and C4 moves investment, and neither
#: changes a receipt, so their corners were inert and doubled the box (D-336, decision 5).
REVENUE_ROWS = frozenset((*channels.C1_KEYS, *channels.C2_KEYS, *channels.C7_KEYS,
                          *channels.C10_KEYS, *channels.C11_KEYS))


def claimed_open_rows(store: Store, reform: Any) -> tuple[str, ...]:
    knobs = channels._knobs(reform)
    return tuple(sorted({p.key for knob in knobs for p in store.for_knob(knob)
                         if p.is_open and p.key in REVENUE_ROWS}))


def evaluate(theta: Theta, *, mechanical: float, reform: Any, store: Store | None = None,
             **inputs: Any) -> AtTheta:
    """The receipts at θ and the θ box, for one priced year."""
    store = store if store is not None else load()
    theta.check_known(store)
    receipts, grade = receipts_at(theta, store=store, mechanical=mechanical,
                                  reform=reform, **inputs)
    # The statistics are θ-free: read off the run at θ, one draw (D-336, decision 6).
    statistics = statistics_of(_run(theta, store=store, mechanical=mechanical,
                                    reform=reform, **inputs))
    claimed = claimed_open_rows(store, reform)
    values = [receipts_at(corner, store=store, mechanical=mechanical, reform=reform,
                          **inputs)[0] for corner in corners(claimed, theta)] or [receipts]
    low, high = min(values), max(values)
    if not low - MONOTONE_SLACK_EUR <= receipts <= high + MONOTONE_SLACK_EUR:
        raise ThetaError(
            f"les recettes à θ ({receipts:,.0f} €) sortent des bornes de la boîte "
            f"[{low:,.0f} ; {high:,.0f}] : un canal n'est pas monotone en θ, et lire les "
            f"bornes aux coins serait faux. Refusé plutôt que tracé.")
    return AtTheta(receipts=receipts, grade=grade, box=(low, high), claimed=claimed,
                   statistics=statistics)
