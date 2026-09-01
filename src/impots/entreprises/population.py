"""The synthetic firm population (§3).

SIRENE gives the skeleton — how many firms exist in each sector × size cell — and
ESANE gives that cell's published totals for turnover, value added and result.
Neither publishes a firm. So every financial here is a **parametric draw inside a
published cell**, and the reconciliation report says so in those words.

## What is calibrated and what is therefore spent (§3.4)

Each cell's **firm count**, **turnover total** and **value-added total** are
reproduced exactly, by construction: the draws set the shape, and a single scale
factor per cell sets the level. Those three are spent and can never be validation.

**Profit is not calibrated to anything**, which is what leaves the IS receipts
line able to say something — with one caveat that has to be stated rather than
buried. The fiscal-to-accounting ratio (§3.3) is derived from published DGFiP
assiette totals, and assiette × rate ≈ receipts. So the IS line is
*semi*-independent, in exactly the way the household module's income-tax line is
semi-independent of a calibrated wage bill. The report says which.

## The two scalars that decide whether any of this means anything

**P(loss)** — a quarter to two fifths of French firms pay no IS in a normal year.
Without it the IS total is fiction, and the effective-rate profile has no left
tail. Applied as a per-cell Bernoulli that zeroes the profit.

**The fiscal-to-accounting ratio** — fiscal result is not accounting result, and
no open source publishes the difference per firm. A single aggregate ratio is the
honest v1, and it dominates the IS residual.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import polars as pl

from impots import guards

SEED = 20260101

#: Dispersion of turnover within a cell, as the sigma of a lognormal. Assumed,
#: not published: ESANE gives cell means and totals, not quantiles, so the shape
#: inside a cell cannot be calibrated and is declared instead. Firm turnover is
#: famously heavy-tailed even within narrow cells, which is why this is large.
TURNOVER_SIGMA = 1.4

#: Correlation between a firm's value-added margin and its profit margin, drawn
#: jointly so the two are not independent. A firm with an unusually high value
#: added for its turnover tends to be more profitable, and drawing them
#: independently would flatten the effective-rate distribution the module exists
#: to show.
MARGIN_CORRELATION = 0.55

#: Synthetic firms per published cell. Enough that a cell's internal distribution
#: is resolved; small enough that the whole population stays a few hundred
#: thousand rows and prices in milliseconds.
FIRMS_PER_CELL = 400


@dataclass(frozen=True)
class Cell:
    """One published sector × size cell — the unit ESANE and SIRENE both report."""

    naf_section: str
    taille: str
    n_firms: float
    turnover_total: float
    value_added_total: float
    result_total: float
    p_loss: float
    """Share of firms in the cell declaring no taxable profit."""


@dataclass
class PopulationStats:
    cells: int
    rows: int
    weighted_firms: float
    weighted_turnover: float
    weighted_value_added: float
    weighted_accounting_result: float
    weighted_taxable_profit: float
    share_loss_making: float
    fiscal_to_accounting: float
    cells_with_va_above_ca: int
    calibration_error: dict[str, float] = field(default_factory=dict)
    """Relative miss against each cell total the build claims to reproduce."""


def _draw_cell(
    cell: Cell, rng: np.random.Generator, firms_per_cell: int
) -> dict[str, np.ndarray]:
    """Draw one cell's firms, then scale each total onto its published value.

    Two steps on purpose. The draw sets the *shape* inside the cell, which nothing
    published constrains. The scale sets the *level*, which is published and which
    the build therefore reproduces exactly rather than approximately — so the
    weight identity around this step is an equality, not a tolerance.
    """
    count = min(firms_per_cell, max(round(cell.n_firms), 1))
    weight = cell.n_firms / count

    turnover = rng.lognormal(0.0, TURNOVER_SIGMA, count)
    turnover *= cell.turnover_total / (turnover.sum() * weight)

    # Value-added and profit margins drawn jointly: the correlation is what gives
    # the effective-rate distribution its spread.
    normals = rng.multivariate_normal(
        mean=[0.0, 0.0],
        cov=[[1.0, MARGIN_CORRELATION], [MARGIN_CORRELATION, 1.0]],
        size=count,
    )
    va_share = np.clip(0.30 + 0.12 * normals[:, 0], 0.02, 0.95)
    # Profit margins for the firms that HAVE a profit. Truncated positive on
    # purpose: loss-making is decided once, by the cell's published P(loss), and a
    # margin draw that also wandered negative would zero a second tranche of firms
    # on top of it. That double-counting pushed the realised loss share to 49 %
    # against a specified 28 % — and the share of firms paying no IS is a
    # validation line, so it would have been measuring this bug rather than the
    # model (§3.4).
    margin = np.clip(0.05 + 0.06 * normals[:, 1], 0.002, None)

    value_added = va_share * turnover
    value_added *= cell.value_added_total / (value_added.sum() * weight)

    loss = rng.random(count) < cell.p_loss
    result = np.where(loss, 0.0, margin * turnover)
    if result.sum() != 0:
        # The published cell result is the net of profits and losses, so scaling
        # the profitable firms onto it is what reproduces the total.
        result *= cell.result_total / (result.sum() * weight)

    return {
        "weight": np.full(count, weight),
        "chiffre_affaires": turnover,
        "valeur_ajoutee": value_added,
        "resultat_comptable": result,
        "loss": loss,
    }


def build_firms(
    cells: list[Cell],
    fiscal_to_accounting: float,
    seed: int = SEED,
    firms_per_cell: int = FIRMS_PER_CELL,
) -> tuple[pl.DataFrame, PopulationStats]:
    """Assemble the firm population from published cells.

    `fiscal_to_accounting` converts accounting result into taxable profit. It is a
    single national scalar in v1 and it dominates the IS residual; §3.3 requires
    its value in the report's method notes, which is why it is a parameter here
    rather than a constant hidden in the module.
    """
    if not cells:
        raise ValueError("no cells: the firm population needs a published skeleton")

    rng = np.random.default_rng(seed)
    frames: list[pl.DataFrame] = []
    for index, cell in enumerate(sorted(cells, key=lambda c: (c.naf_section, c.taille))):
        drawn = _draw_cell(cell, rng, firms_per_cell)
        frames.append(pl.DataFrame({
            "cell": np.full(len(drawn["weight"]), index),
            "naf_section": np.full(len(drawn["weight"]), cell.naf_section),
            "taille": np.full(len(drawn["weight"]), cell.taille),
            **drawn,
        }))

    firms = pl.concat(frames).with_row_index("firm_id")

    # Taxable profit: accounting result, converted to a fiscal basis, floored at
    # zero, and zeroed outright for the cell's loss-makers. There is no
    # carry-forward — it needs firm panels that are not open data — and that
    # biases IS upward, which the report states.
    result = firms["resultat_comptable"].to_numpy()
    loss = firms["loss"].to_numpy()
    taxable = np.where(loss, 0.0, result * fiscal_to_accounting)

    firms = firms.with_columns(
        pl.Series("benefice_imposable", taxable),
        # No open register records the capital conditions of the reduced IS rate.
        pl.lit(True).alias("capital_libere_detenu_personnes_physiques"),
    ).drop("loss")

    weights = firms["weight"].to_numpy()
    published = {
        "n_firms": sum(cell.n_firms for cell in cells),
        "chiffre_affaires": sum(cell.turnover_total for cell in cells),
        "valeur_ajoutee": sum(cell.value_added_total for cell in cells),
    }
    achieved = {
        "n_firms": float(weights.sum()),
        "chiffre_affaires": guards.weighted_total(firms, "chiffre_affaires"),
        "valeur_ajoutee": guards.weighted_total(firms, "valeur_ajoutee"),
    }
    # The three totals this build claims to reproduce, checked rather than assumed.
    # Both Phase 1 weighting defects were exactly this: a step that quietly changed
    # a total while every other guard stayed green.
    errors = {
        name: (achieved[name] / published[name] - 1.0) if published[name] else 0.0
        for name in published
    }
    breached = {name: error for name, error in errors.items() if abs(error) > 1e-9}
    if breached:
        raise guards.WeightIdentityError(
            "the firm build did not reproduce the published cell totals it claims to "
            f"calibrate on: {breached}"
        )

    stats = PopulationStats(
        cells=len(cells),
        rows=firms.height,
        weighted_firms=achieved["n_firms"],
        weighted_turnover=achieved["chiffre_affaires"],
        weighted_value_added=achieved["valeur_ajoutee"],
        weighted_accounting_result=guards.weighted_total(firms, "resultat_comptable"),
        weighted_taxable_profit=guards.weighted_total(firms, "benefice_imposable"),
        share_loss_making=float(weights[taxable <= 0].sum() / weights.sum()),
        fiscal_to_accounting=fiscal_to_accounting,
        cells_with_va_above_ca=guards.not_greater(
            firms["valeur_ajoutee"].to_numpy(), firms["chiffre_affaires"].to_numpy(),
            "valeur_ajoutee <= chiffre_affaires",
        ),
        calibration_error=errors,
    )
    return firms, stats


def stats_as_dict(stats: PopulationStats) -> dict[str, object]:
    return asdict(stats)
