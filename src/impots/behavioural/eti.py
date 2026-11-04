"""C1's inputs, built once (D-336, decision 4).

The households' marginal rates before and after the reform, their base, their weights and
the top-decile split. Written once here and read by the API's pass and by the accuracy
attribution, which each kept a copy (audit of goal 14, § 4.3 f): a correction to one
would not have reached the other.

TWO RATES PER HOUSEHOLD. C1 reads the response to the income tax's own marginal rate,
τ_IR — Cabannes, Houdré and Landais estimate the elasticity on it — measured by the same
finite difference as the total rate, in the same simulations (`emtr._rate`). The receipts
lost are counted at the TOTAL rate τ¹: what the State loses. The base stays the salary,
and the page says so.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from impots.behavioural.channels import ChannelInputMissing

#: The columns of the EMTR pass C1 reads, and the input each one becomes.
COLUMNS = {"emtr": "emtr_baseline", "emtr_reform": "emtr_reform",
           "emtr_ir": "emtr_ir_baseline", "emtr_ir_reform": "emtr_ir_reform"}


def eti_inputs(frame: Any, households: Any) -> dict[str, Any]:
    """C1's inputs: the households' marginal rates, total and of the income tax alone,
    before and after the reform, their taxable base, their weights and the top-decile
    split. `households` are the EMTR pass's households with earnings, `frame` the
    population their rates were computed on. Read apart by the measure of C1's noise
    (`scripts/bruit_c1.py`, D-282), so that it prices C1 exactly as the chain does."""
    import polars as pl

    missing = sorted(set(COLUMNS) - set(households.columns))
    if missing:
        raise ChannelInputMissing(
            f"C1 lit les taux marginaux totaux et de l'IR seul (D-336) ; la passe des taux "
            f"n'a pas {missing}. Un cache d'avant D-336 ne les porte pas, et se recalcule.")
    weights = households["weight"].to_numpy()
    # Taxable base per household: what C1's response applies to. Deciles of it give
    # the top-decile split the two ETI parameters need.
    frame_base = (
        frame.group_by("household_id")
        .agg(pl.col("salaire_brut_annuel").sum().alias("base"))
        .sort("household_id")
    )
    lookup = dict(zip(frame_base["household_id"].to_list(),
                      frame_base["base"].to_list(), strict=False))
    base = np.array([lookup.get(h, 0.0) for h in households["household_id"].to_list()])
    order = np.argsort(base)
    cumulative = np.cumsum(weights[order])
    top = np.zeros(len(base), dtype=bool)
    if cumulative[-1] > 0:
        top[order[cumulative >= 0.9 * cumulative[-1]]] = True
    return {
        **{name: households[column].to_numpy() for column, name in COLUMNS.items()},
        "taxable_base": base, "weights": weights, "top_decile": top,
    }


def pooled_eti_inputs(frame: Any, samples: list[Any]) -> dict[str, Any]:
    """C1's inputs over several samples of households, each weighed by the share of the
    samples it is (D-284). Each sample keeps its own top-decile split, so that C1 on the
    pool is the mean of C1 on each sample, to the rounding."""
    parts = [eti_inputs(frame, households) for households in samples]
    pooled = {key: np.concatenate([part[key] for part in parts]) for key in parts[0]}
    pooled["weights"] = pooled["weights"] / len(parts)
    return pooled
