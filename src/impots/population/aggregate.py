"""Weighted totals and the distributional table (§4.5).

Two outputs, and deliberately only two:

  * an **aggregate** per instrument — what the reform raises or costs nationally;
  * **deciles of niveau de vie** — who gains and who loses, and by how much.

No top-1 % row. Branch A' has no capital income and a wage distribution drawn
from published margins, so the top of the distribution is a construction; a
top-percentile figure would be the least reliable number in the model presented
as the most interesting one. §4.2 rules it out and this module does not provide it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import polars as pl

#: A reform moves a household by less than this and we call it unaffected. Below
#: about ten euros a year the answer is dominated by rounding inside the engine
#: and by the arbitrariness of a synthetic income, not by the reform.
INDIFFERENCE_EUR = 10.0

N_DECILES = 10

#: Instruments reported as national totals, in the order a reader wants them.
INSTRUMENTS = (
    "salaire_brut", "salaire_super_brut", "salaire_net", "salaire_imposable",
    "cotisations_salariales", "cotisations_employeur",
    "csg_deductible", "csg_imposable", "crds", "ir",
    "af", "ppa", "rsa", "aide_logement", "revenu_disponible",
)

#: Weighted counts rather than euro totals — reported alongside, never summed in.
COUNTS = ("n_foyers", "n_foyers_imposes", "n_persons", "n_dependants")


def consumption_units(n_aged_14_plus: np.ndarray, n_children_under_14: np.ndarray) -> np.ndarray:
    """OECD-modified equivalence scale: 1 for the first adult, 0.5 for each further
    person aged 14 or over, 0.3 for each child under 14.

    This is the scale INSEE uses for "niveau de vie", which is what makes our
    deciles comparable with Filosofi's published ones. A household of one adult
    always scores 1.0 even if the arithmetic is written as `1 + 0.5 x 0`.
    """
    adults = np.maximum(np.asarray(n_aged_14_plus, dtype=np.float64), 1.0)
    children = np.asarray(n_children_under_14, dtype=np.float64)
    return 1.0 + 0.5 * (adults - 1.0) + 0.3 * children


def weighted_quantiles(
    values: np.ndarray, weights: np.ndarray, quantiles: np.ndarray
) -> np.ndarray:
    """Quantiles of a weighted distribution.

    Population quantiles, not sample ones: each household stands for `weight`
    households, so the cumulative weight is what gets cut, using the midpoint
    convention that keeps the median of a symmetric distribution in the middle.
    """
    order = np.argsort(values, kind="stable")
    sorted_values = values[order]
    sorted_weights = weights[order]
    cumulative = np.cumsum(sorted_weights)
    cutpoints = (cumulative - 0.5 * sorted_weights) / cumulative[-1]
    return np.interp(quantiles, cutpoints, sorted_values)


def weighted_decile_index(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """Assign each household to a decile by weighted RANK, not by value cut.

    Cutting on values breaks when the ranking variable has ties, and disposable
    income has plenty: households living on the same benefit land on the same
    euro. With value cuts two adjacent decile boundaries can coincide, and the
    decile between them comes out **empty** — the table silently prints nine rows
    where a reader expects ten. Ranking on cumulative weight always yields ten
    groups of equal weight; tied households are split between deciles in survey
    order, which is arbitrary but unbiased.
    """
    order = np.argsort(values, kind="stable")
    ordered_weights = weights[order]
    cumulative = np.cumsum(ordered_weights)
    position = (cumulative - 0.5 * ordered_weights) / cumulative[-1]
    sorted_decile = np.minimum((position * N_DECILES).astype(np.int64), N_DECILES - 1)
    decile = np.empty_like(sorted_decile)
    decile[order] = sorted_decile
    return decile


@dataclass
class DecileRow:
    decile: int
    n_households: float
    """Weighted count."""
    mean_niveau_de_vie: float
    mean_baseline: float
    mean_reform: float | None
    mean_delta: float | None
    share_winners: float | None
    share_losers: float | None
    share_unaffected: float | None


@dataclass
class Aggregates:
    totals: dict[str, float]
    """Weighted national total per instrument, in EUR."""
    counts: dict[str, float] = field(default_factory=dict)
    """Weighted counts (foyers, foyers imposés, persons, dependants)."""
    totals_reform: dict[str, float] = field(default_factory=dict)
    deltas: dict[str, float] = field(default_factory=dict)
    deciles: list[DecileRow] = field(default_factory=list)
    households: float = 0.0
    persons: float = 0.0
    reform_cost: float | None = None
    """Positive = the reform costs the public finances; negative = it raises money."""


def _total(frame: pl.DataFrame, column: str, weights: np.ndarray) -> float:
    return float((frame[column].to_numpy() * weights).sum())


def aggregate(result_households: pl.DataFrame) -> Aggregates:
    """Weighted totals and the decile table from a `RunResult.households` frame."""
    frame = result_households
    weights = frame["weight"].to_numpy().astype(np.float64)
    has_reform = any(column.endswith("_reform") for column in frame.columns)

    totals = {
        name: _total(frame, name, weights) for name in INSTRUMENTS if name in frame.columns
    }
    counts = {
        name: _total(frame, name, weights) for name in COUNTS if name in frame.columns
    }
    totals_reform: dict[str, float] = {}
    deltas: dict[str, float] = {}
    if has_reform:
        for name in totals:
            reform_column = f"{name}_reform"
            if reform_column in frame.columns:
                totals_reform[name] = _total(frame, reform_column, weights)
                deltas[name] = totals_reform[name] - totals[name]

    units = consumption_units(
        frame["n_aged_14_plus"].to_numpy(), frame["n_children_under_14"].to_numpy()
    )
    # Niveau de vie needs disposable income, which only the full tier computes.
    # Ranking on anything else would silently produce a different distribution.
    if "revenu_disponible" not in frame.columns:
        return Aggregates(
            totals=totals, counts=counts, totals_reform=totals_reform, deltas=deltas,
            households=float(weights.sum()),
            persons=float((frame["n_persons"].to_numpy() * weights).sum()),
            reform_cost=deltas.get("revenu_disponible"),
        )

    baseline = frame["revenu_disponible"].to_numpy().astype(np.float64)
    niveau_de_vie = baseline / units
    decile_index = weighted_decile_index(niveau_de_vie, weights)

    reform_values = (
        frame["revenu_disponible_reform"].to_numpy().astype(np.float64)
        if "revenu_disponible_reform" in frame.columns
        else None
    )
    delta = None if reform_values is None else reform_values - baseline

    rows: list[DecileRow] = []
    for index in range(N_DECILES):
        mask = decile_index == index
        w = weights[mask]
        total_weight = w.sum()
        if total_weight == 0:  # pragma: no cover - only on a degenerate sample
            continue
        row = DecileRow(
            decile=index + 1,
            n_households=float(total_weight),
            mean_niveau_de_vie=float((niveau_de_vie[mask] * w).sum() / total_weight),
            mean_baseline=float((baseline[mask] * w).sum() / total_weight),
            mean_reform=None,
            mean_delta=None,
            share_winners=None,
            share_losers=None,
            share_unaffected=None,
        )
        if delta is not None:
            d = delta[mask]
            row.mean_reform = float((reform_values[mask] * w).sum() / total_weight)
            row.mean_delta = float((d * w).sum() / total_weight)
            row.share_winners = float(w[d > INDIFFERENCE_EUR].sum() / total_weight)
            row.share_losers = float(w[d < -INDIFFERENCE_EUR].sum() / total_weight)
            row.share_unaffected = float(w[np.abs(d) <= INDIFFERENCE_EUR].sum() / total_weight)
        rows.append(row)

    return Aggregates(
        totals=totals,
        counts=counts,
        totals_reform=totals_reform,
        deltas=deltas,
        deciles=rows,
        households=float(weights.sum()),
        persons=float((frame["n_persons"].to_numpy() * weights).sum()),
        # A reform that raises disposable income costs the budget that much.
        reform_cost=deltas.get("revenu_disponible"),
    )
