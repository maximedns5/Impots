"""Phase 9 M2 — the macro response at θ (PHASE9_SPEC §2.1, second class of source).

The same arithmetic as `macro.fan.run`, with the drawn multiplier replaced by the
multiplier at θ: the Mésange centre ∓ one IMK cross-study standard deviation, of the
instrument's family. Employment follows the multiplier proportionally, the assumption
D-059 already makes and names. Horizons 1 to 3 only, the store's `usable_horizons`.

It says what GDP and jobs would be at θ. The debt path does not read it: the loop of M3
(`retroaction`, D-218) applies the same multiplier at θ through its own arithmetic, so
that GDP and the balance come from one variant together.
"""

from __future__ import annotations

from impots.macro import mesange
from impots.macro.fan import MULTIPLIER_FAMILY, FanError, _require
from impots.macro.shocks import Impulse
from impots.macro.store import Store
from impots.predictif.theta import multiplier_at


def at_theta(impulse: Impulse, store: Store, *, gdp_eur: float,
             theta: float) -> dict[str, tuple[float, float]]:
    """{horizon: (GDP effect in euros, jobs in thousands of FTE)} at θ."""
    if not impulse.by_instrument:
        raise FanError("aucun instrument de cette réforme n'a de multiplicateur publié")
    if gdp_eur <= 0:
        raise FanError("le PIB doit être positif pour exprimer un choc en points")
    multipliers = _require(store, "multiplier_by_instrument")
    jobs = _require(store, "employment_by_instrument")
    dispersion = _require(store, "multiplier_dispersion")
    out: dict[str, tuple[float, float]] = {}
    for horizon in multipliers.usable_horizons:
        gdp_effect = jobs_effect = 0.0
        for instrument, amount in impulse.by_instrument.items():
            spec = mesange.VARIANTS[instrument]
            family = MULTIPLIER_FAMILY.get(instrument)
            if family is None:
                raise FanError(f"aucune famille de dispersion pour {instrument!r}")
            centre = multipliers.at(instrument, horizon)
            value = multiplier_at(centre, dispersion.at(family, "all"), theta)
            points = (amount / gdp_eur) * 100.0 / spec.ex_ante_points
            gdp_effect += value * amount / spec.ex_ante_points
            ratio = value / centre if centre else 1.0
            jobs_effect += jobs.at(instrument, horizon) * points * ratio
        out[horizon] = (gdp_effect, jobs_effect)
    return out
