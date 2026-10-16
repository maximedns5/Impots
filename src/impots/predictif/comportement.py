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


def receipts_at(theta: Theta, *, store: Store, mechanical: float, reform: Any,
                **inputs: Any) -> tuple[float, str]:
    result = band_module.compute(mechanical=mechanical, reform=reform,
                                 store=pinned(store, theta), draws=1, **inputs)
    receipts = mechanical if result.band is None else float(result.band.p50)
    return receipts, result.grade


def claimed_open_rows(store: Store, reform: Any) -> tuple[str, ...]:
    knobs = channels._knobs(reform)
    return tuple(sorted({p.key for knob in knobs for p in store.for_knob(knob)
                         if p.is_open}))


def evaluate(theta: Theta, *, mechanical: float, reform: Any, store: Store | None = None,
             **inputs: Any) -> AtTheta:
    """The receipts at θ and the θ box, for one priced year."""
    store = store if store is not None else load()
    theta.check_known(store)
    receipts, grade = receipts_at(theta, store=store, mechanical=mechanical,
                                  reform=reform, **inputs)
    claimed = claimed_open_rows(store, reform)
    values = [receipts_at(corner, store=store, mechanical=mechanical, reform=reform,
                          **inputs)[0] for corner in corners(claimed, theta)] or [receipts]
    low, high = min(values), max(values)
    if not low - MONOTONE_SLACK_EUR <= receipts <= high + MONOTONE_SLACK_EUR:
        raise ThetaError(
            f"les recettes à θ ({receipts:,.0f} €) sortent des bornes de la boîte "
            f"[{low:,.0f} ; {high:,.0f}] : un canal n'est pas monotone en θ, et lire les "
            f"bornes aux coins serait faux. Refusé plutôt que tracé.")
    return AtTheta(receipts=receipts, grade=grade, box=(low, high), claimed=claimed)
