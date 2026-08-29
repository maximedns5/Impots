"""Attach incomes to the skeleton — the largest fidelity cost in branch A' (§4.2).

**The EEC carries no income of any kind** (D-012). So unlike a normal
microsimulation, nothing here is imputation from a donor: there are no donors.
Every euro is *drawn from a published distribution*, conditioned on what the
survey does observe — socio-professional category, sex, age band, part-time rate,
sector — and then rescaled so the weighted total matches a published aggregate.

What that buys and what it does not:

  * the **level** is right by construction, because it is calibrated;
  * the **shape** is as good as the published quantiles and the lognormal-plus-
    Pareto family used to interpolate them;
  * the **joint** structure is wrong wherever it is not carried by the
    conditioning variables. Two earners in a household are drawn independently,
    so assortative mating is absent and couple incomes are less correlated than
    reality. That flattens the top of the household distribution specifically.

Not modelled at all, and declared rather than approximated: capital income, income
from self-employment (3.87 M people), and any income of the 15+ population outside
wages, pensions and unemployment benefit.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import polars as pl

from impots.population import margins

SEED = 20240101

#: Standard normal quantile at 0.9 — the deciles are converted through this.
Z90 = 1.2815515655446004

#: Above this quantile the lognormal understates: real top wages have a Pareto
#: tail. Spliced at the 95th percentile and calibrated on the published C95/C99.
TAIL_QUANTILE = 0.95
TAIL_C95_NET_EQTP_MONTHLY = 5593.0
TAIL_C99_NET_EQTP_MONTHLY = 10260.0

#: Retirement: an inactive person at or above this age is treated as a pensioner.
#: The EEC has no "retired" status — `ACTEU` distinguishes only employment,
#: unemployment and inactivity — so age is the only available proxy.
#:
#: Chosen on ONE criterion: which cut best reproduces the published number of
#: pensioners (DREES, ~17 M). 55 gives 15.96 M, 58 gives 15.23 M, 60 gives
#: 14.73 M, the legal 62 gives 14.24 M — so 55 wins, and France does retire
#: before its legal age through long careers and special schemes.
#:
#: The cut also moves the simulated income tax (+10.5 % against the published
#: barème at 55, +14.0 % at 60), and that must NOT be why it was picked. Income
#: tax is a validation line; choosing a modelling parameter because it improves a
#: validation line silently converts that line into a calibration target and
#: destroys the only thing the reconciliation report is for (§4.3). The criterion
#: above is independent of the tax outturn, and is recorded here so a later reader
#: can check the reasoning ran in that order.
#:
#: The cut still misclassifies: inactive 55-59-year-olds who are not retired at
#: all (long-term sick, homemakers) are given a pension, and it is the least
#: satisfying assumption in the module.
RETIREMENT_AGE = 55

#: Dispersion of the pension distribution. Assumed, not published: DREES
#: publishes the mean pension, not its quantiles, so only the level below is
#: anchored. Recorded here rather than hidden inside a call.
PENSION_SIGMA = 0.55
UNEMPLOYMENT_SIGMA = 0.45

#: Dwelling size, in m², as a function of household size. An assumption — no
#: published surface distribution was used — and the weakest link in the housing
#: benefit chain. See margins.RENT_PER_M2.
SURFACE_BASE_M2 = 30.0
SURFACE_PER_PERSON_M2 = 12.0


@dataclass(frozen=True)
class IncomeStats:
    """What was drawn, and against which target. Feeds the reconciliation report."""

    employees: float
    gross_wages_before_calibration: float
    gross_wages_after_calibration: float
    wage_calibration_factor: float
    pensioners: float
    pensions_total: float
    unemployed: float
    unemployment_total: float
    renters: float
    rent_total: float
    people_without_modelled_income: float


def lognormal_from_deciles(d1: float, median: float, d9: float) -> tuple[float, float]:
    """`(mu, sigma)` of the lognormal matching a published median and D9/D1 spread.

    Kept for the tests that document *why* it is not used for drawing: a single
    lognormal fitted this way reproduces the median exactly and misses D1 and D9
    by about 14 % each, because real wage distributions are less skewed at the
    bottom and heavier at the top than any one lognormal. `quantile_curve` below
    hits every published point instead.
    """
    sigma = np.log(d9 / d1) / (2.0 * Z90)
    return float(np.log(median)), float(sigma)


def quantile_curve(points: dict[float, float]) -> tuple[np.ndarray, np.ndarray]:
    """Knots of a piecewise-lognormal quantile function through published points.

    Interpolating `log(value)` linearly against the *normal quantile* of the
    probability makes every published point exact, keeps the curve smooth, and
    degenerates to an ordinary lognormal when only two points are supplied. It is
    the natural generalisation of "fit a lognormal" to more than two knots.

    Returns `(z_knots, log_value_knots)` for use with `sample_curve`.
    """
    probabilities = sorted(points)
    z = np.array([NormalDist().inv_cdf(p) for p in probabilities], dtype=np.float64)
    log_values = np.array([np.log(points[p]) for p in probabilities], dtype=np.float64)
    return z, log_values


def sample_curve(z: np.ndarray, knots_z: np.ndarray, knots_log: np.ndarray) -> np.ndarray:
    """Evaluate a quantile curve at standard-normal draws, extrapolating linearly.

    `np.interp` clamps outside its range, which would pile every draw below the
    first knot onto exactly D1. The tails are extended with the slope of the
    adjacent segment instead, so the distribution keeps spreading.
    """
    values = np.interp(z, knots_z, knots_log)
    low_slope = (knots_log[1] - knots_log[0]) / (knots_z[1] - knots_z[0])
    high_slope = (knots_log[-1] - knots_log[-2]) / (knots_z[-1] - knots_z[-2])
    below = z < knots_z[0]
    above = z > knots_z[-1]
    values[below] = knots_log[0] + low_slope * (z[below] - knots_z[0])
    values[above] = knots_log[-1] + high_slope * (z[above] - knots_z[-1])
    return np.exp(values)


def _pareto_alpha(c95: float, c99: float) -> float:
    """Tail index from two published upper percentiles.

    Survival at the two points is 0.05 and 0.01, so `(c99/c95)^-alpha = 0.2`.
    """
    return float(np.log(5.0) / np.log(c99 / c95))


def _draw_net_eqtp(frame: pl.DataFrame, rng: np.random.Generator) -> np.ndarray:
    """A net full-time-equivalent monthly wage for every employee."""
    n = frame.height
    draws = np.zeros(n, dtype=np.float64)
    pcs = frame["pcs"].to_numpy()
    normals = rng.standard_normal(n)

    for group, (d1, median, d9) in margins.WAGE_QUANTILES_BY_PCS.items():
        mask = pcs == group
        if not mask.any():
            continue
        knots_z, knots_log = quantile_curve({0.1: d1, 0.5: median, 0.9: d9})
        draws[mask] = sample_curve(normals[mask], knots_z, knots_log)

    # Employees whose PCS is not coded (0.29 M) take the all-employee curve, which
    # has all nine published deciles rather than three.
    unknown = draws == 0
    if unknown.any():
        deciles = margins.WAGE_DECILES_NET_EQTP_MONTHLY
        knots_z, knots_log = quantile_curve({k / 10: v for k, v in deciles.items()})
        draws[unknown] = sample_curve(normals[unknown], knots_z, knots_log)

    # Sex gap, applied *within* PCS: women are both over-represented in lower-paid
    # categories and paid less inside each one, and the PCS draw only carries the first.
    overall = margins.WAGE_MEAN_NET_EQTP_MONTHLY
    sex = frame["sex"].to_numpy()
    for label, mean in margins.WAGE_MEAN_NET_EQTP_BY_SEX.items():
        draws[sex == label] *= mean / overall

    # Age gradient: the under-25 penalty is large and the band identifies it exactly.
    young = frame["age"].to_numpy() < 25
    draws[young] *= margins.WAGE_MEAN_NET_EQTP_BY_AGE["under_25"] / overall

    # Pareto tail. A lognormal fitted to deciles puts the 99th percentile far below
    # the published 10 260 EUR, and the top decile pays two thirds of all income
    # tax — so without this the IR validation line cannot come close.
    alpha = _pareto_alpha(TAIL_C95_NET_EQTP_MONTHLY, TAIL_C99_NET_EQTP_MONTHLY)
    cutoff = np.quantile(draws, TAIL_QUANTILE)
    in_tail = draws > cutoff
    if in_tail.any():
        uniform = rng.uniform(size=int(in_tail.sum()))
        draws[in_tail] = TAIL_C95_NET_EQTP_MONTHLY * (1.0 - uniform) ** (-1.0 / alpha)
    return draws


def attach_incomes(
    frame: pl.DataFrame, seed: int = SEED
) -> tuple[pl.DataFrame, IncomeStats]:
    """Add `salaire_brut_annuel`, `pension_annuelle`, `chomage_annuel`, `loyer_mensuel`."""
    rng = np.random.default_rng(seed)
    n = frame.height
    weight = frame["weight"].to_numpy().astype(np.float64)

    # ---- wages ------------------------------------------------------------
    employee = frame["is_salarie"].to_numpy() & (
        frame["statut_activite"].to_numpy() == "employed"
    )
    net_eqtp = _draw_net_eqtp(frame, rng)
    gross_annual = net_eqtp / margins.NET_TO_GROSS_RATIO.value * 12.0
    gross_annual *= frame["quotite_travail"].to_numpy()
    wages = np.where(employee, gross_annual, 0.0)

    before = float((wages * weight).sum())
    target = margins.TOTAL_GROSS_WAGES.value
    # The one calibration on incomes, and therefore spent: the wage bill can never
    # afterwards appear as a validation line (§4.3).
    factor = target / before if before > 0 else 1.0
    wages = wages * factor

    # ---- pensions ---------------------------------------------------------
    age = frame["age"].to_numpy()
    inactive = frame["statut_activite"].to_numpy() == "inactive"
    pensioner = inactive & (age >= RETIREMENT_AGE)
    pension_draw = np.where(
        pensioner, np.exp(rng.standard_normal(n) * PENSION_SIGMA), 0.0
    )
    pension_mass = float((pension_draw * weight).sum())
    pensions = (
        pension_draw * (margins.DECLARED_PENSIONS.value / pension_mass)
        if pension_mass > 0
        else pension_draw
    )

    # ---- unemployment benefit --------------------------------------------
    unemployed = frame["statut_activite"].to_numpy() == "unemployed"
    chomage_draw = np.where(
        unemployed, np.exp(rng.standard_normal(n) * UNEMPLOYMENT_SIGMA), 0.0
    )
    chomage_mass = float((chomage_draw * weight).sum())
    chomage = (
        chomage_draw * (margins.UNEMPLOYMENT_BENEFIT_SPEND.value / chomage_mass)
        if chomage_mass > 0
        else chomage_draw
    )

    # ---- rent -------------------------------------------------------------
    statut = frame["statut_occupation"].to_numpy()
    household_size = (
        frame.group_by("household_id").agg(pl.len().alias("size"))
        .join(frame.select("household_id"), on="household_id", how="right")["size"]
        .to_numpy()
    )
    surface = SURFACE_BASE_M2 + SURFACE_PER_PERSON_M2 * household_size
    social = statut == "locataire_hlm"
    private = np.isin(statut, ["locataire_vide", "locataire_meuble", "locataire_foyer"])
    rent = np.where(
        social, surface * margins.RENT_PER_M2["social"].value,
        np.where(private, surface * margins.RENT_PER_M2["prive"].value, 0.0),
    )

    enriched = frame.with_columns(
        pl.Series("salaire_brut_annuel", wages),
        pl.Series("pension_annuelle", pensions),
        pl.Series("chomage_annuel", chomage),
        pl.Series("loyer_mensuel", rent),
    )

    no_income = ~(employee | pensioner | unemployed) & (age >= 18)
    stats = IncomeStats(
        employees=float((employee * weight).sum()),
        gross_wages_before_calibration=before,
        gross_wages_after_calibration=float((wages * weight).sum()),
        wage_calibration_factor=factor,
        pensioners=float((pensioner * weight).sum()),
        pensions_total=float((pensions * weight).sum()),
        unemployed=float((unemployed * weight).sum()),
        unemployment_total=float((chomage * weight).sum()),
        renters=float(((rent > 0) * weight).sum()),
        rent_total=float((rent * 12 * weight).sum()),
        people_without_modelled_income=float((no_income * weight).sum()),
    )
    return enriched, stats
