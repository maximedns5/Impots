"""Weighted firm aggregates and the incidence tables (§4).

Three outputs, and deliberately only three:

  * **totals by instrument** — what a reform raises or costs nationally;
  * **incidence by NAF section × size class** — who bears it;
  * **the effective-rate profile by size** — the shape line, and the firm analogue
    of the household module's interdecile ratio.

No firm-level output and no top-tail table. Every financial in this population is
a parametric draw within a published sector×size cell (§3.2), so a named firm or
a top-1 % figure would be the least reliable number in the model presented as the
most interesting one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

from impots.entreprises.runner import INSTRUMENTS

#: A firm moved by less than this counts as unaffected. Below a hundred euros a
#: year the answer is dominated by the parametric draw that produced the firm, not
#: by the reform.
INDIFFERENCE_EUR = 100.0

#: Size classes, on the INSEE definition by headcount. Reported rather than
#: turnover bands because the published effective-rate profiles use them.
SIZE_ORDER = ("micro", "PME", "ETI", "GE")


@dataclass
class CellRow:
    """One sector × size cell of the incidence table."""

    naf_section: str
    taille: str
    n_firms: float
    turnover: float
    tax_baseline: float
    mean_effective_rate: float
    tax_reform: float | None = None
    mean_delta: float | None = None
    delta_effective_rate: float | None = None
    share_affected: float | None = None


@dataclass
class SizeRow:
    """The effective-rate profile: the firm analogue of D9/D1."""

    taille: str
    n_firms: float
    mean_effective_rate: float
    median_effective_rate: float
    share_zero_tax: float


@dataclass
class FirmAggregates:
    totals: dict[str, float]
    totals_reform: dict[str, float] = field(default_factory=dict)
    deltas: dict[str, float] = field(default_factory=dict)
    cells: list[CellRow] = field(default_factory=list)
    by_size: list[SizeRow] = field(default_factory=list)
    n_firms: float = 0.0
    turnover: float = 0.0
    share_zero_is: float = 0.0
    """Share of firms paying no IS. The scalar that decides whether the IS line
    means anything at all (§3.3)."""
    reform_cost: float | None = None
    """Positive = the reform costs the public finances."""


def _weighted(values: np.ndarray, weights: np.ndarray) -> float:
    return float((values * weights).sum())


def _weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    total = weights.sum()
    return float((values * weights).sum() / total) if total else 0.0


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    if not len(values):
        return 0.0
    order = np.argsort(values, kind="stable")
    ordered_weights = weights[order]
    cumulative = np.cumsum(ordered_weights)
    if cumulative[-1] == 0:
        return 0.0
    position = (cumulative - 0.5 * ordered_weights) / cumulative[-1]
    return float(np.interp(0.5, position, values[order]))


def aggregate(firms: pl.DataFrame) -> FirmAggregates:
    """Weighted totals, the incidence table and the effective-rate profile."""
    weights = firms["weight"].to_numpy().astype(np.float64)
    has_reform = any(column.endswith("_reform") for column in firms.columns)

    totals = {
        name: _weighted(firms[name].to_numpy(), weights)
        for name in INSTRUMENTS
        if name in firms.columns
    }
    totals_reform: dict[str, float] = {}
    deltas: dict[str, float] = {}
    if has_reform:
        for name in totals:
            column = f"{name}_reform"
            if column in firms.columns:
                totals_reform[name] = _weighted(firms[column].to_numpy(), weights)
                deltas[name] = totals_reform[name] - totals[name]

    profit = firms["benefice_imposable"].to_numpy().astype(np.float64)
    baseline_tax = firms["prelevements_entreprise"].to_numpy().astype(np.float64)
    # Effective rate on profit; loss-makers score zero rather than infinity.
    effective = np.where(profit > 0, baseline_tax / np.maximum(profit, 1e-9), 0.0)
    is_paid = firms["impot_societes"].to_numpy().astype(np.float64)

    aggregates = FirmAggregates(
        totals=totals,
        totals_reform=totals_reform,
        deltas=deltas,
        n_firms=float(weights.sum()),
        turnover=_weighted(firms["chiffre_affaires"].to_numpy(), weights),
        share_zero_is=float(weights[is_paid <= 0].sum() / weights.sum()) if weights.sum() else 0.0,
        # A reform that reduces firm tax costs the budget that much.
        reform_cost=-deltas.get("prelevements_entreprise") if deltas else None,
    )

    if "naf_section" not in firms.columns or "taille" not in firms.columns:
        return aggregates

    reform_tax = (
        firms["prelevements_entreprise_reform"].to_numpy().astype(np.float64)
        if "prelevements_entreprise_reform" in firms.columns
        else None
    )
    delta = None if reform_tax is None else reform_tax - baseline_tax

    sections = firms["naf_section"].to_numpy()
    sizes = firms["taille"].to_numpy()

    for section in sorted(set(sections)):
        for size in [s for s in SIZE_ORDER if s in set(sizes)]:
            mask = (sections == section) & (sizes == size)
            if not mask.any():
                continue
            w = weights[mask]
            row = CellRow(
                naf_section=str(section),
                taille=str(size),
                n_firms=float(w.sum()),
                turnover=_weighted(firms["chiffre_affaires"].to_numpy()[mask], w),
                tax_baseline=_weighted(baseline_tax[mask], w),
                mean_effective_rate=_weighted_mean(effective[mask], w),
            )
            if delta is not None and reform_tax is not None:
                reformed_effective = np.where(
                    profit[mask] > 0, reform_tax[mask] / np.maximum(profit[mask], 1e-9), 0.0
                )
                row.tax_reform = _weighted(reform_tax[mask], w)
                row.mean_delta = _weighted_mean(delta[mask], w)
                row.delta_effective_rate = (
                    _weighted_mean(reformed_effective, w) - row.mean_effective_rate
                )
                row.share_affected = float(
                    w[np.abs(delta[mask]) > INDIFFERENCE_EUR].sum() / w.sum()
                )
            aggregates.cells.append(row)

    for size in [s for s in SIZE_ORDER if s in set(sizes)]:
        mask = sizes == size
        w = weights[mask]
        aggregates.by_size.append(SizeRow(
            taille=str(size),
            n_firms=float(w.sum()),
            mean_effective_rate=_weighted_mean(effective[mask], w),
            median_effective_rate=_weighted_median(effective[mask], w),
            share_zero_tax=float(w[is_paid[mask] <= 0].sum() / w.sum()) if w.sum() else 0.0,
        ))

    return aggregates
