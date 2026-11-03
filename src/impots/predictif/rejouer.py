"""The chain replayed from a report, without a pass (D-336, decision 6).

`annuel.build` writes, per year and per view, what the passes gave the chain: the cost,
the impulse by Mésange instrument with what it could not map, and the sufficient
statistics of the receipts channels (C1: A_bas, A_haut; C7: S_g; C10: B, Δln, τ¹, lost;
C11 and C2: the cut, the value of a job, the Trésor-Éco share, the anchor and tail of the
jobs). Beside them, once: the start, the frame (growth, spending rule, the reference's
rates and the marginal rate), the claimed rows with their published bounds, and the
Mésange and IMK tables of the instruments the loop reads. This module refits the debt,
the GDP → receipts loop and the θ box from those fields alone. It reads no file and runs
no engine: what the page, or the Monte Carlo, can do in a browser.

THE SAME ARITHMETIC AS THE CHAIN, written apart. `chaine.run` and `retroaction.compute`
are the reference; a test holds this module equal to them to 1e-9 on synthetic passes,
under the three persistences and several θ. Every value here is ARRAY-VALUED along a draw
axis, so that one call prices one θ or two thousand draws alike.

THE MULTIPLIER IS A SHIFT z. At θ, z = 2θ − 1 and m = max(0, c + z sd) (D-336, decision
2); a draw takes z from a normal. The feedback is (solde + brut) m / c, bounded by brut.

WHAT IT DOES NOT REPLAY. The first year carried as a share of GDP (the box's
« first_year » reading), which reads the explorer's chain; and a report written before
D-336, which has no statistics — refused by name.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

#: The key of the multiplier's θ, as `theta.MACRO_ROW`.
MACRO_ROW = "multiplicateur_macro"
READ = "lue"
PERSISTENCES = ("lue", "eteint", "tenu")
VIEWS = {"vieillie": "mechanical_aged_eur", "figee": "mechanical_frozen_eur"}


class ReplayError(ValueError):
    """The report does not carry what the replay reads."""


# --------------------------------------------------------------------------- #
# the rows: a value at θ, or drawn
# --------------------------------------------------------------------------- #
def value_at(row: Mapping[str, Any], theta: Any) -> Any:
    """The row's value at θ through its published centre, in its declared direction —
    `theta.value_at`, array-valued."""
    low, centre, high = float(row["low"]), float(row["central"]), float(row["high"])
    if low == high:
        return np.full(np.shape(theta), centre) if np.ndim(theta) else centre
    t = np.asarray(theta, dtype=float) if np.ndim(theta) else float(theta)
    if row["un"] == "low":
        t = 1.0 - t
    lower = centre - (1.0 - 2.0 * t) * (centre - low)
    upper = centre + (2.0 * t - 1.0) * (high - centre)
    return np.where(t <= 0.5, lower, upper) if np.ndim(t) else (lower if t <= 0.5 else upper)


# --------------------------------------------------------------------------- #
# the receipts, from the channels' statistics
# --------------------------------------------------------------------------- #
def receipts(mechanical: float, channels: Mapping[str, Any] | None,
             values: Mapping[str, Any]) -> Any:
    """Mechanical plus every receipts channel, RECEIPTS POSITIVE, at the row values
    `values` (scalars or arrays). In the band's order: C1, C7, C10, C11."""
    if not channels:
        return mechanical
    parts = []
    if "c1_eti" in channels:
        c1 = channels["c1_eti"]
        parts.append(values["eti_all"] * c1["A_bas"] + values["eti_top_decile"] * c1["A_haut"])
    if "c7_labour_supply" in channels:
        total = 0.0
        for key, s in channels["c7_labour_supply"]["S"].items():
            total = total + values[key] * s
        parts.append(total)
    if "c10_dividendes" in channels:
        c10 = channels["c10_dividendes"]
        share = values["dividend_share_firm_owners"]
        owners = values["dividend_elasticity_firm_owners"]
        others = values["dividend_elasticity_other_holders"]
        elasticity = share * owners + (1.0 - share) * others
        induced = elasticity * c10["delta_log"] * c10["B"]
        shifted = (values["dividend_wage_shift_firm_owners"] * share * owners
                   * c10["delta_log"] * c10["B"])
        parts.append(c10["tau1"] * induced - shifted * c10["lost_per_eur"])
    if "c11_autofinancement" in channels:
        c11, c2 = channels["c11_autofinancement"], channels["c2_employment"]
        jobs = values["employment_elasticity_smic"] * c2["anchor"] + c2["tail"] + 0.0
        reading = jobs * c11["value_per_job"] / c11["cut"]
        weight = values["autofinancement_poids_tresor_eco"]
        parts.append(((1.0 - weight) * reading + weight * c11["tresor_eco"]) * c11["cut"])
    if not parts:
        return mechanical
    total = parts[0]
    for part in parts[1:]:
        total = total + part
    return total + mechanical


# --------------------------------------------------------------------------- #
# the loop
# --------------------------------------------------------------------------- #
def _interpolated(row: Mapping[str, float], horizon: int, read: Sequence[int]) -> float:
    if horizon in read:
        return float(row[str(horizon)])
    below = max(h for h in read if h < horizon)
    above = min(h for h in read if h > horizon)
    low, high = float(row[str(below)]), float(row[str(above)])
    return low + (horizon - below) / (above - below) * (high - low)


def _read_horizon(horizon: int, persistence: str | None, read: Sequence[int],
                  short: int) -> int | None:
    if persistence == READ:
        if horizon > read[-1]:
            raise ReplayError(f"horizon de {horizon} ans au-delà de {read[-1]} : refusé")
        return horizon
    if horizon <= short:
        return horizon
    if persistence is None:
        raise ReplayError(f"au-delà de {short} ans sans persistance nommée")
    return None if persistence == "eteint" else short


def loop(impulses: Sequence[Mapping[str, float]], gdp: Sequence[float],
         macro: Mapping[str, Any], z: Any, persistence: str | None) -> tuple[list, list]:
    """(y_t, φ_t), year by year, at the multiplier shift z — `retroaction.compute`."""
    read = [int(h) for h in macro["horizons"]]
    short = int(macro["court"])
    tables = macro["instruments"]
    covered = sorted({i for year in impulses for i, v in year.items() if v} & set(tables))
    units = {i: [year.get(i, 0.0) * 100.0 / (tables[i]["brut"] * y)
                 for year, y in zip(impulses, gdp, strict=True)] for i in covered}
    gap, balance = [], []
    for k in range(len(impulses)):
        y_k = phi_k = 0.0
        for instrument in covered:
            table = tables[instrument]
            path = units[instrument]
            for j in range(k + 1):
                step = path[j] - (path[j - 1] if j else 0.0)
                if not step:
                    continue
                at = _read_horizon(k - j + 1, persistence, read, short)
                if at is None:
                    continue
                centre = _interpolated(table["pib"], at, read)
                m = np.maximum(0.0, centre + z * table["sd"])
                gross = table["brut"]
                f = np.minimum((_interpolated(table["solde"], at, read) + gross) * m / centre,
                               gross)
                y_k = y_k + step * m / 100.0
                phi_k = phi_k + step * f / 100.0
        gap.append(y_k)
        balance.append(phi_k)
    return gap, balance


# --------------------------------------------------------------------------- #
# the debt
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Chemin:
    """One view's paths: the reference, and the difference the reform makes."""

    years: tuple[int, ...]
    reference: tuple[float, ...]
    delta: Any
    """Δb_t, one entry per year, each a float or an array along the draws."""
    gdp_gap: Any
    feedback: Any


def reference_path(rejeu: Mapping[str, Any], start: Mapping[str, Any],
                   horizon: int) -> tuple[list[float], list[float], float]:
    """(GDP Y_t, the reference ratio b_t, nominal growth) — `reference.reference_years`
    and `path.project`."""
    cadre = rejeu["cadre"]
    real, prices = cadre["growth"]["real"], cadre["growth"]["prices"]
    nominal = (1.0 + real) * (1.0 + prices) - 1.0
    rule = cadre["spending"]["rule"]
    if rule == "part_pib_constante":
        factor = 1.0
    elif rule == "gele_en_volume":
        factor = (1.0 + prices) / (1.0 + nominal)
    elif rule == "personnalise":
        factor = (1.0 + cadre["spending"]["growth"]) / (1.0 + nominal)
    else:
        raise ReplayError(f"règle de dépense inconnue : {rule}")
    rates = cadre["taux"]["reference"]
    product, share, ratio = start["gdp_eur"], start["spending_ratio"], start["debt_ratio"]
    gdp, refs = [], []
    for k in range(horizon):
        product *= 1.0 + nominal
        share *= factor
        ratio = ratio * (1.0 + rates[k]) / (1.0 + nominal) - (start["receipts_ratio"] - share)
        gdp.append(product)
        refs.append(ratio)
    return gdp, refs, nominal


def chemin(payload: Mapping[str, Any], *, view: str, values: Mapping[str, Any],
           z: Any, persistence: str | None) -> Chemin:
    """One view's Δb path at the row values `values` and the multiplier shift `z`."""
    rejeu = _rejeu(payload)
    rows = payload["years"]
    years = tuple(int(r["year"]) for r in rows)
    gdp, refs, nominal = reference_path(rejeu, rejeu["start"], len(rows))
    marginal = rejeu["cadre"]["taux"]["marginal"]
    stats = [r["statistiques"][view] for r in rows]
    cost = [float(r[VIEWS[view]]) for r in rows]
    if rejeu["behavioural"] and all(s.get("canaux") is not None for s in stats):
        primary = [receipts(-c, s["canaux"], values) / y
                   for c, s, y in zip(cost, stats, gdp, strict=True)]
    else:
        primary = [-c / y for c, y in zip(cost, gdp, strict=True)]
    if rejeu["looped"]:
        gap, phi = loop([s["impulses"] for s in stats], gdp, rejeu["macro"], z, persistence)
    else:
        gap = phi = [0.0] * len(rows)
    debt = 0.0
    delta = []
    for k in range(len(rows)):
        debt = debt * (1.0 + marginal) / (1.0 + nominal) - (primary[k] + phi[k])
        delta.append((refs[k] + debt) / (1.0 + gap[k]) - refs[k])
    return Chemin(years=years, reference=tuple(refs), delta=delta, gdp_gap=gap,
                  feedback=phi)


def _rejeu(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    rejeu = payload.get("rejeu")
    if not rejeu:
        raise ReplayError("rapport sans champ « rejeu » : écrit avant D-336, il ne porte ni "
                          "les impulsions ni les statistiques des canaux")
    return rejeu


# --------------------------------------------------------------------------- #
# θ, and the box
# --------------------------------------------------------------------------- #
def theta_values(payload: Mapping[str, Any], theta: Mapping[str, float]) -> tuple[dict, float]:
    """(row values, multiplier shift z) at a θ by row; `theta[MACRO_ROW]` for the
    multiplier, every claimed row named."""
    rejeu = _rejeu(payload)
    values = {key: value_at(row, theta[key]) for key, row in rejeu["lignes"].items()}
    z = 2.0 * float(theta[MACRO_ROW]) - 1.0 if MACRO_ROW in theta else 0.0
    return values, z


def at_theta(payload: Mapping[str, Any], theta: Mapping[str, float], *, view: str,
             persistence: str | None) -> Chemin:
    """The view's path at θ by row."""
    values, z = theta_values(payload, theta)
    return chemin(payload, view=view, values=values, z=z, persistence=persistence)


def box(payload: Mapping[str, Any], theta: Mapping[str, float], *, view: str,
        persistence: str | None) -> dict[str, Any]:
    """Δb at the last year at θ and at every corner of the box over the report's box
    rows — `annuel._theta_box`, the « every_year » reading."""
    import itertools

    rows = list(_rejeu(payload)["box_rows"])
    corners = []
    for combo in itertools.product((0.0, 1.0), repeat=len(rows)):
        corner = {**theta, **dict(zip(rows, combo, strict=True))}
        label = ", ".join(f"{key} = {corner[key]:g}" for key in rows)
        corners.append([label, at_theta(payload, corner, view=view,
                                        persistence=persistence).delta[-1]])
    return {"theta": at_theta(payload, theta, view=view, persistence=persistence).delta[-1],
            "corners": corners}


def verdict(payload: Mapping[str, Any], theta: Mapping[str, float],
            persistence: str | None = READ) -> str:
    """« hausse », « baisse » or « dépend de θ » under ONE persistence — « lue » by
    default, the one the verdict reads (D-336, decision 1): Δb at the last year at θ and
    at every corner, in both views, all of one sign or not."""
    signs = set()
    for view in VIEWS:
        read = box(payload, theta, view=view, persistence=persistence)
        for value in [read["theta"], *(v for _, v in read["corners"])]:
            signs.add(math.copysign(1.0, value) if value else 0.0)
    if signs == {1.0}:
        return "hausse"
    if signs == {-1.0}:
        return "baisse"
    return "dépend de θ"
