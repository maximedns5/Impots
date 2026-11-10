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

**Self-employment income** (3.87 M people) is drawn by `attach_self_employment`, on the
sector the survey records, from the Insee's published distributions by sector, and
calibrated on the Insee's total (but 19, étape 2): see its docstring.

Not modelled at all, and declared rather than approximated: capital income, and any
income of the 15+ population outside wages, self-employment, pensions and unemployment
benefit.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist

import numpy as np
import polars as pl

from impots.population import logement, margins

SEED = 20240101

#: A frame representing less than this share of the published household count is a
#: sample, not the country, and cannot carry a national calibration target.
#:
#: The bound is loose on purpose. It exists to separate *the country* (the full EEC,
#: which weights to within a percent of `margins.HOUSEHOLDS`) from *a sample* (the
#: committed test fixture, at 0.20 %). Nothing sits between them, and a tighter bound
#: would start refusing vintages over a difference that raking is there to fix.
REPRESENTATIVE_SHARE_MIN = 0.5


class IncomeScaleError(RuntimeError):
    """A national income target was about to be calibrated onto a fraction of France."""


#: Standard normal quantile at 0.9 — the deciles are converted through this.
Z90 = 1.2815515655446004

#: Above the 99th centile the private wages follow a Pareto tail through the published
#: C95 and C99 (Insee Première n° 2079, figure 3 and tableau complémentaire 3).
#: `TAIL_QUANTILE` is the cut of the draw before the étape « haut », kept to replay its
#: stream (`_legacy_tail_size`).
TAIL_QUANTILE = 0.95
TAIL_C95_NET_EQTP_MONTHLY = 5593.0
TAIL_C99_NET_EQTP_MONTHLY = 10261.0

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


#: openfisca's taxable salary over the gross it is handed (`salaire_imposable` over
#: `salaire_de_base` and the traitement), on the whole population: the cotisations and
#: the deductible CSG come off. Measured on 20 000 ménages of the population of the but 19,
#: law of 2024 (étape « ir ») : 919,66 / 1 109,98 Md€. Used twice, to give a gérant
#: majoritaire the gross pay whose taxable part is his declared one, and to set the exempt
#: share of the salaries (`part_salaire_exoneree`) before openfisca has run.
IMPOSABLE_SUR_BRUT = 0.8285

#: The self-employment draw has its own stream, so that adding it moved no wage, pension
#: or unemployment benefit already drawn: the draws of `attach_incomes` before it read
#: `default_rng(seed)` in the same order as they did.
SELF_EMPLOYMENT_STREAM = 2

#: The column `attach_self_employment` hands the gérants' gross salary in, which
#: `attach_incomes` folds into `salaire_brut_annuel` and drops.
GERANT_GROSS_PAY = "salaire_brut_gerant"

#: The column of the income tax's exempt share of a salary, read by engine correction 24.
EXEMPT_SHARE = "part_salaire_exoneree"

#: The survey's agricultural sector (NAF divisions 01 to 03), which has its own tables.
AGRICULTURE = "agriculture"

#: Insee row -> the nature of a micro-entreprise's turnover, which sets its abatement
#: and its versement libératoire: « vente » (marchandises, 71 %), « service » (BIC
#: prestations, 50 %), « bnc » (34 %); for a classique, BIC or BNC. A hypothesis by
#: sector: the Insee does not cross the two. A restaurant sells for consumption on the
#: premises, which is a sale.
NATURE_PAR_SECTEUR: dict[str, str] = {
    "industrie": "vente", "metiers_bouche": "vente", "commerce_auto": "vente",
    "commerce_gros": "vente", "pharmacie": "vente", "detail_magasin": "vente",
    "detail_hors_magasin": "vente", "hebergement_restauration": "vente",
    "construction": "service", "transports": "service", "immobilier": "service",
    "services_administratifs": "service", "services_personnels": "service",
    "ensemble": "service",
    "information_communication": "bnc", "finance": "bnc", "juridique": "bnc",
    "conseil": "bnc", "architecture": "bnc", "autres_specialisees": "bnc",
    "veterinaires": "bnc", "arts": "bnc", "enseignement": "bnc", "medecins": "bnc",
    "paramedicaux": "bnc", "autres_sante": "bnc",
}

#: Insee row -> openfisca's `categorie_non_salarie`, which sets a classique's
#: contributions and, through them, his CSG base. A BNC is a profession libérale; the
#: trades that make or repair are artisans; the rest commerçants. A hypothesis too.
_ARTISANS = {"industrie", "construction", "metiers_bouche", "services_administratifs",
             "services_personnels"}
CATEGORIE_PAR_SECTEUR: dict[str, str] = {
    row: ("profession_liberale" if nature == "bnc"
          else "artisan" if row in _ARTISANS else "commercant")
    for row, nature in NATURE_PAR_SECTEUR.items()
}

#: The micro regime's turnover ceiling and abatement in 2024 (CGI art. 50-0 and 102 ter;
#: openfisca's `regime_micro_bic` and `regime_micro_bnc`). A drawn micro income is
#: capped at the ceiling's, the turnover after abatement: the regime ends there.
MICRO_PLAFONDS_2024: dict[str, tuple[float, float]] = {
    "vente": (188_700.0, 0.71), "service": (77_700.0, 0.50), "bnc": (77_700.0, 0.34),
}

#: The régimes a self-employed person is drawn into, and so the 2042-C-PRO box
#: `to_openfisca` writes: réel BIC or BNC (a gérant majoritaire is wired as one, see
#: `attach_self_employment`), micro with or without the versement libératoire, by
#: nature, and the two agricultural régimes.
REGIMES = ("reel_bic", "reel_bnc", "gerant_bic", "gerant_bnc",
           "micro_vente", "micro_service", "micro_bnc", "vl_vente", "vl_service", "vl_bnc",
           "reel_ba", "micro_ba")

#: The agricultural incomes' shape is not published. The réel farmers take the shape of
#: the non-agricultural classiques (the Insee's « ensemble » row), the micro-BA farmers
#: a lognormal of this dispersion: hypotheses, each rescaled to its published mean.
MICRO_BA_SIGMA = 0.5


@dataclass(frozen=True)
class SelfEmploymentStats:
    """What `attach_self_employment` drew, and against which target."""

    self_employed: float
    micro_entrepreneurs: float
    agricoles: float
    gerants: float
    share_zero: float
    total_before_calibration: float
    total_after_calibration: float
    calibration_factor: float
    gerants_taxable_pay: float = 0.0
    """What the gérants majoritaires are paid as a salary, its taxable part (1GB)."""


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
    targets_scale: float = 1.0
    """What the four national targets were multiplied by before calibration.

    1.0 for the country. Anything else says the frame is a sample and the totals
    below are that sample's share of the national figure, not the figure itself.
    """
    self_employment: SelfEmploymentStats | None = None
    gerants_gross_pay: float = 0.0
    """The gérants majoritaires' gross salary, taken out of the employees' share of D11."""
    exempt_wage_share: float = 0.0
    """The share of each employee's taxable salary the income tax exempts (D11 against the
    declared salaries, `margins.DECLARED_TAXABLE_WAGES`)."""


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
    """A net full-time-equivalent monthly wage for every employee.

    **The rank** comes from the survey: a draw on the published curve of the person's
    PCS (D1, median, D9), times a factor for his age band and sex. **The value** of the
    upper half comes from the publications: each employee's weighted rank among the
    employees of his sector is read on the published curve of that sector, the Insee
    Première n° 2079 centiles for the private sector (a Pareto tail above the 99th), the
    Siasp median, third quartile and ninth decile for each versant of the fonction
    publique. The lower half keeps the shape of the draw, scaled to meet the published
    median: below it the EQTP distribution is not the annual one (part-year work is not
    modelled), and the RSA and the prime d'activité, recalibrated on this lower half
    (D-366), are left where they were. The age and sex factors are fitted so that the
    private employees' mean in each of the ten published cells (`margins.
    WAGE_MEAN_NET_EQTP_BY_AGE_SEX`), relative to the private mean, is the published one;
    the fonction publique takes the same factors, a hypothesis.

    **Why** (but 19, étape « haut »). The draw before it spliced its Pareto tail on the
    5 % of *rows* above an unweighted cut, children and inactive people included: 6.5 %
    of the employees were in it, the 95th and 99th centiles came out 10 and 8 % above the
    published ones before the wage-bill calibration and 17 and 15 % after; it gave the
    private sector's shape to the fonction publique, whose D9/D1 is 2.3 and not 2.9; and
    it applied no age gradient after 25, so the 25-39-year-olds, more often single, came
    out 12 % above their published mean and the 55 and over 17 % below it. The foyers at
    41 and 45 % were 31 and 72 % above the DGFiP's count.
    """
    n = frame.height
    score = np.zeros(n, dtype=np.float64)
    pcs = frame["pcs"].to_numpy()
    normals = rng.standard_normal(n)

    for group, (d1, median, d9) in margins.WAGE_QUANTILES_BY_PCS.items():
        mask = pcs == group
        if not mask.any():
            continue
        knots_z, knots_log = quantile_curve({0.1: d1, 0.5: median, 0.9: d9})
        score[mask] = sample_curve(normals[mask], knots_z, knots_log)

    # Employees whose PCS is not coded (0.29 M) take the all-employee curve, which
    # has all nine published deciles rather than three.
    unknown = score == 0
    if unknown.any():
        deciles = margins.WAGE_DECILES_NET_EQTP_MONTHLY
        knots_z, knots_log = quantile_curve({k / 10: v for k, v in deciles.items()})
        score[unknown] = sample_curve(normals[unknown], knots_z, knots_log)

    # The stream. The draw before the étape « haut » took one uniform for each row of its
    # tail; they are drawn and discarded, so that the pensions and the unemployment
    # benefit, which read the same generator after the wages, are the ones drawn before.
    rng.uniform(size=_legacy_tail_size(frame, score))

    employee = frame["is_salarie"].to_numpy().astype(bool) & (
        frame["statut_activite"].to_numpy() == "employed")
    weight = frame["weight"].to_numpy().astype(np.float64)
    versant = frame["fonction_publique"].to_numpy()
    groups = [(employee & np.array([v is None for v in versant]), _private_curve)]
    groups += [(employee & (versant == name), _fp_curve(points))
               for name, points in margins.WAGE_QUANTILES_FP_NET_EQTP_MONTHLY.items()]

    age = frame["age"].to_numpy()
    female = frame["sex"].to_numpy() == "female"
    cells = []
    for low, high, women, men in margins.WAGE_MEAN_NET_EQTP_BY_AGE_SEX:
        band = (age >= low) & (age < high)
        cells += [(band & female, women), (band & ~female, men)]
    private = groups[0][0]
    factor = np.ones(n, dtype=np.float64)
    # The fit is on the cells' means *relative to each other*: the level of the private
    # sector is the published curve's, and the published means, weighted by the survey's
    # mix of ages and sexes, need not average to it exactly.
    masses = [float(weight[cell & private].sum()) for cell, _ in cells]
    total = sum(masses)
    expected = sum(m * mean for m, (_, mean) in zip(masses, cells, strict=True)) / total
    for _ in range(AGE_SEX_ITERATIONS):
        draws = _map_upper_half(score * factor, weight, groups)
        level = float((draws * weight)[private].sum()) / total if total > 0 else 0.0
        for (cell, mean), mass in zip(cells, masses, strict=True):
            if mass > 0:
                got = float((draws * weight)[cell & private].sum()) / mass
                factor[cell] *= mean * level / expected / got
    return _map_upper_half(score * factor, weight, groups)


#: Rounds of the age and sex fit (the largest miss is under 0.1 % after six, on the
#: test frame).
AGE_SEX_ITERATIONS = 12


def _legacy_tail_size(frame: pl.DataFrame, score: np.ndarray) -> int:
    """How many uniforms the draw before the étape « haut » took for its Pareto tail."""
    overall = margins.WAGE_MEAN_NET_EQTP_MONTHLY
    legacy = score.copy()
    sex = frame["sex"].to_numpy()
    for label, mean in margins.WAGE_MEAN_NET_EQTP_BY_SEX.items():
        legacy[sex == label] *= mean / overall
    legacy[frame["age"].to_numpy() < 25] *= margins.WAGE_MEAN_NET_EQTP_BY_AGE["under_25"] / overall
    return int((legacy > np.quantile(legacy, TAIL_QUANTILE)).sum())


def _normal_quantile(p: np.ndarray) -> np.ndarray:
    inverse = NormalDist().inv_cdf
    return np.array([inverse(x) for x in p], dtype=np.float64)


def _private_curve(p: np.ndarray) -> np.ndarray:
    """The published private-sector curve at probabilities `p` of 0.5 or more."""
    points = margins.WAGE_CENTILES_PRIVATE_NET_EQTP_MONTHLY
    values = sample_curve(_normal_quantile(p), *quantile_curve(points))
    top = max(points)
    above = p > top
    alpha = _pareto_alpha(TAIL_C95_NET_EQTP_MONTHLY, TAIL_C99_NET_EQTP_MONTHLY)
    values[above] = points[top] * ((1.0 - top) / (1.0 - p[above])) ** (1.0 / alpha)
    return values


def _fp_curve(points: dict[float, float]):
    def curve(p: np.ndarray) -> np.ndarray:
        return sample_curve(_normal_quantile(p), *quantile_curve(points))
    return curve


def _map_upper_half(score: np.ndarray, weight: np.ndarray, groups) -> np.ndarray:
    """Each group's upper half read on its published curve; the lower half scaled to meet it."""
    out = score.copy()
    for mask, curve in groups:
        here = np.flatnonzero(mask)
        if here.size == 0:
            continue
        order = here[np.argsort(score[here], kind="stable")]
        cumulative = np.cumsum(weight[order])
        rank = (cumulative - weight[order] / 2.0) / cumulative[-1]
        upper = rank >= 0.5
        if not upper.any():
            continue
        out[order[upper]] = curve(rank[upper])
        median_draw = score[order[upper][0]]
        median = curve(np.array([0.5]))[0]
        out[order[~upper]] = score[order[~upper]] * median / median_draw
    return out


def household_share_of_france(frame: pl.DataFrame) -> float:
    """What fraction of the published household count this frame's weights represent.

    Household weight is the mean of the members' weights, matching `calibrate.py`
    and `runner.py`: the survey weights a whole dwelling together.
    """
    households = (
        frame.group_by("household_id").agg(pl.col("weight").mean())["weight"].sum()
    )
    return float(households) / margins.HOUSEHOLDS.value


def _sector_cells(naf88: np.ndarray, pcs: np.ndarray) -> np.ndarray:
    """The survey's sector, read as the Insee's tables: one cell per person.

    The NAF division the survey records, and in two places the PCS: in health care
    (division 86) it tells the doctor (cadres et professions intellectuelles
    supérieures, PCS 31) from the paramedical professions (professions intermédiaires,
    PCS 43), in retail the pharmacist (PCS 31). Retail is one division and two Insee
    rows (`_CELL_ROWS`). An unknown sector takes the all-sector row, « ensemble ».
    """
    division = np.array([int(c) if isinstance(c, str) and c.isdigit() else 0
                         for c in naf88], dtype=np.int64)
    cadre, intermediaire = pcs == "cadre", pcs == "profession_intermediaire"
    rules = [
        ((division >= 1) & (division <= 3), AGRICULTURE),
        (np.isin(division, (10, 11)), "metiers_bouche"),
        ((division >= 5) & (division <= 39), "industrie"),
        ((division >= 41) & (division <= 43), "construction"),
        (division == 45, "commerce_auto"),
        (division == 46, "commerce_gros"),
        ((division == 47) & cadre, "pharmacie"),
        (division == 47, "detail"),
        ((division >= 49) & (division <= 53), "transports"),
        (np.isin(division, (55, 56)), "hebergement_restauration"),
        ((division >= 58) & (division <= 63), "information_communication"),
        ((division >= 64) & (division <= 66), "finance"),
        (division == 68, "immobilier"),
        (division == 69, "juridique"),
        (division == 70, "conseil"),
        (division == 71, "architecture"),
        (division == 75, "veterinaires"),
        ((division >= 72) & (division <= 74), "autres_specialisees"),
        ((division >= 77) & (division <= 82), "services_administratifs"),
        (division == 85, "enseignement"),
        ((division == 86) & cadre, "medecins"),
        ((division == 86) & intermediaire, "paramedicaux"),
        (np.isin(division, (86, 87, 88)), "autres_sante"),
        ((division >= 90) & (division <= 93), "arts"),
        ((division >= 94) & (division <= 99), "services_personnels"),
    ]
    cells = np.full(division.size, "ensemble", dtype=object)
    assigned = np.zeros(division.size, dtype=bool)
    for mask, cell in rules:
        take = mask & ~assigned
        cells[take] = cell
        assigned |= take
    return cells


#: A survey cell -> the Insee rows it stands for, when it is not one row of its name.
_CELL_ROWS: dict[str, tuple[str, ...]] = {
    "detail": ("detail_magasin", "detail_hors_magasin"),
}


def _micro_in_field(row: str) -> tuple[float, float]:
    """(count in thousands, mean monthly income) of a row's micro-entrepreneurs whose
    main job is not salaried: the survey's field. Those principally salaried (28 % of
    all, 250 € a month) leave, sector by sector in proportion to its pluriactive share."""
    if row not in margins.MICRO_PAR_SECTEUR:
        return 0.0, 0.0
    count, mean, pluriactive = margins.MICRO_PAR_SECTEUR[row]
    share, income = margins.MICRO_PRINCIPALEMENT_SALARIES
    salaried = share / margins.MICRO_PAR_SECTEUR["ensemble"][2] * pluriactive / 100.0
    return count * (1.0 - salaried), (mean - salaried * income) / (1.0 - salaried)


def attach_self_employment(
    frame: pl.DataFrame, seed: int = SEED, targets_scale: float = 1.0
) -> tuple[pl.DataFrame, SelfEmploymentStats]:
    """Add `revenu_non_salarie_annuel`, `regime_non_salarie`, `secteur_non_salarie`.

    **Who.** Everyone in employment the survey does not record as an employee: 3.87 M
    people whose main job is self-employed. Until but 19 they had no income at all, and
    the model read them as destitute: 45 % of its RSA households, half its bottom
    decile, and none of the income tax on 70 to 110 bn € of base (D-365).

    **What is published, and drawn.** The Insee Première n° 2114 and its tables give,
    for 2024 and by sector: the counts of classiques and of micro-entrepreneurs, their
    mean incomes, the classiques' share of nil or loss-making years and the quartiles
    and deciles of their positive incomes, the share of gérants majoritaires; for the
    micro-entrepreneurs, their dispersion across sectors only; for farmers, counts,
    means and the nil share by régime. So, per person:

      1. the sector, from the survey's NAF division (`_sector_cells`);
      2. micro-entrepreneur or classique, at the sector's published odds once the
         micro-entrepreneurs whose main job is salaried — whom the survey counts as
         employees — are taken out; a farmer, micro-BA or réel at theirs;
      3. a nil income at the published share, else a positive one through the
         published quantiles (`quantile_curve`, exact at each of the five points);
      4. women's incomes 30 % (classiques) and 14 % (micro) below men's of the same
         sector, as published; then each sector and status rescaled to its published
         mean, nil incomes included, which moves the drawn quantiles by under 10 %;
      5. a classique's gérance, a micro-entrepreneur's versement libératoire, at the
         published shares (Insee; DGFiP, 2042-C-PRO) — the latter drawn and, for an
         openfisca defect, not yet wired (`to_openfisca.SELF_EMPLOYMENT_INPUTS`); a micro
         income is capped at its regime's ceiling;
      6. ONE factor on everyone but the gérants majoritaires, so that the weighted total
         is `SELF_EMPLOYMENT_INCOME` (hors gérants) times `targets_scale`, as the wage bill
         is calibrated; the gérants' drawn income becomes a salary, below.

    **What it is not.** The nature of a micro-entrepreneur's turnover and the
    contributions category follow the sector, by hypothesis (`NATURE_PAR_SECTEUR`).

    **A gérant majoritaire is paid a salary** (but 19, étape « ir »). The tax code taxes his
    pay as one (art. 62 of the CGI, box 1GB), and D11, onto which the wage bill is
    calibrated, already counts it: wired as a réel BIC or BNC beside it, as étape 2 did, it
    was counted twice (43.8 bn €, seven points of income tax). His drawn income is scaled so
    that the gérants' taxable pay is the declared one (`GERANTS_REMUNERATION`, 30.7 bn €:
    the Insee's 43.8 also counts dividends above 10 % of the capital), turned into a gross
    salary by `IMPOSABLE_SUR_BRUT`, and handed to `attach_incomes` in `GERANT_GROSS_PAY`,
    which takes it out of the employees' share of D11. His contributions and CSG are then an
    employee's, where the SSI levies his; his RSA and prime read a salary, where the Caf
    reads a self-employed income: the same amount. His `regime_non_salarie` stays, to name
    him, and his `revenu_non_salarie_annuel` is nil. Age is not conditioned on. Aides familiaux, whom the survey records as
    self-employed too, draw an income like the rest. A loss is a nil income, as in the
    published means: no deficit is set against other income.

    The draw reads its own stream (`SELF_EMPLOYMENT_STREAM`), every uniform and normal
    for every row in a fixed order: the wages, pensions and unemployment benefit of
    `attach_incomes` are the ones drawn before it existed.
    """
    rng = np.random.default_rng([seed, SELF_EMPLOYMENT_STREAM])
    n = frame.height
    weight = frame["weight"].to_numpy().astype(np.float64)
    self_employed = (
        (frame["statut_activite"].to_numpy() == "employed")
        & ~frame["is_salarie"].to_numpy().astype(bool)
    )
    female = frame["sex"].to_numpy() == "female"
    cells = _sector_cells(frame["naf88"].to_numpy(), frame["pcs"].to_numpy())
    u_row, u_status, u_zero, u_gerant, u_vl = (rng.uniform(size=n) for _ in range(5))
    z = rng.standard_normal(n)

    row = np.full(n, None, dtype=object)
    regime = np.full(n, None, dtype=object)
    micro = np.zeros(n, dtype=bool)
    monthly = np.zeros(n, dtype=np.float64)

    # ---- the sector row and the status ------------------------------------------
    for cell in sorted(set(cells[self_employed])):
        here = np.flatnonzero(self_employed & (cells == cell))
        if cell == AGRICULTURE:
            row[here] = AGRICULTURE
            reel, micro_ba = (margins.AGRICOLES[k][0] for k in ("reel", "micro_ba"))
            regime[here] = np.where(u_status[here] < micro_ba / (reel + micro_ba),
                                    "micro_ba", "reel_ba")
            continue
        rows = _CELL_ROWS.get(cell, (cell,))
        sizes = np.array([margins.CLASSIQUES_PAR_SECTEUR[r][0] + _micro_in_field(r)[0]
                          for r in rows])
        pick = np.searchsorted(np.cumsum(sizes) / sizes.sum(), u_row[here], side="right")
        for k, r in enumerate(rows):
            mine = here[np.minimum(pick, len(rows) - 1) == k]
            row[mine] = r
            classiques, in_field = margins.CLASSIQUES_PAR_SECTEUR[r][0], _micro_in_field(r)[0]
            micro[mine] = u_status[mine] < in_field / (classiques + in_field)

    # ---- the incomes, row by row, and the régime -------------------------------
    p = (0.1, 0.25, 0.5, 0.75, 0.9)
    ensemble_curve = quantile_curve(
        dict(zip(p, margins.CLASSIQUES_PAR_SECTEUR["ensemble"][2:7], strict=True)))
    micro_curve = quantile_curve(dict(zip(p, margins.MICRO_QUANTILES, strict=True)))
    groups: dict[tuple[str, str], tuple[np.ndarray, float]] = {}
    for r in sorted({str(x) for x in row[self_employed]}):
        here = self_employed & (row == r)
        if r == AGRICULTURE:
            for name, key in (("reel_ba", "reel"), ("micro_ba", "micro_ba")):
                mask = here & (regime == name)
                _, mean, zero = margins.AGRICOLES[key]
                draw = (sample_curve(z[mask], *ensemble_curve) if name == "reel_ba"
                        else np.exp(MICRO_BA_SIGMA * z[mask]))
                monthly[mask] = np.where(u_zero[mask] < zero / 100.0, 0.0, draw)
                groups[(r, name)] = (mask, mean)
            continue
        nature = NATURE_PAR_SECTEUR[r]
        _, zero, *quantiles, mean, gerants = margins.CLASSIQUES_PAR_SECTEUR[r]
        mask = here & ~micro
        draw = sample_curve(z[mask], *quantile_curve(dict(zip(p, quantiles, strict=True))))
        draw *= np.where(female[mask], 1.0 - margins.ECART_FEMMES_CLASSIQUES, 1.0)
        monthly[mask] = np.where(u_zero[mask] < zero / 100.0, 0.0, draw)
        base = "bnc" if nature == "bnc" else "bic"
        regime[mask] = np.where(u_gerant[mask] < gerants / 100.0,
                                f"gerant_{base}", f"reel_{base}")
        groups[(r, "classique")] = (mask, mean)

        mask = here & micro
        if mask.any():
            draw = sample_curve(z[mask], *micro_curve)
            draw *= np.where(female[mask], 1.0 - margins.ECART_FEMMES_MICRO, 1.0)
            monthly[mask] = np.where(u_zero[mask] < margins.MICRO_PART_NULLE / 100.0,
                                     0.0, draw)
            with_vl, without = margins.VERSEMENT_LIBERATOIRE[nature]
            regime[mask] = np.where(u_vl[mask] < with_vl / (with_vl + without),
                                    f"vl_{nature}", f"micro_{nature}")
            groups[(r, "micro")] = (mask, _micro_in_field(r)[1])

    # Each sector and status to its published mean, nil incomes included.
    for mask, mean in groups.values():
        drawn = float((monthly[mask] * weight[mask]).sum())
        if drawn > 0:
            monthly[mask] *= mean * float(weight[mask].sum()) / drawn

    # The micro regime ends at its ceiling.
    for nature, (ceiling, abatement) in MICRO_PLAFONDS_2024.items():
        capped = np.isin(regime, (f"micro_{nature}", f"vl_{nature}"))
        monthly[capped] = np.minimum(monthly[capped], ceiling * (1.0 - abatement) / 12.0)

    annual = monthly * 12.0
    # A gérant majoritaire is paid a salary (art. 62 of the CGI), which D11 already counts:
    # his drawn income becomes a gross salary whose taxable part makes the declared boxes
    # (`margins.GERANTS_REMUNERATION`), and no profit. The others are calibrated alone.
    gerant = np.isin(regime, ("gerant_bic", "gerant_bnc"))
    drawn_gerants = float((annual * weight)[gerant].sum())
    taxable_pay = (annual * (margins.GERANTS_REMUNERATION.value * targets_scale / drawn_gerants)
                   if drawn_gerants > 0 else np.zeros(n))
    gross_pay = np.where(gerant, taxable_pay / IMPOSABLE_SUR_BRUT, 0.0)
    annual = np.where(gerant, 0.0, annual)
    before = float((annual * weight).sum())
    target = margins.SELF_EMPLOYMENT_INCOME.value * targets_scale
    # The second calibration on incomes, spent like the wage bill (§4.3).
    factor = target / before if before > 0 else 1.0
    annual = annual * factor

    enriched = frame.with_columns(
        pl.Series("revenu_non_salarie_annuel", annual),
        pl.Series("regime_non_salarie", regime.tolist(), dtype=pl.String),
        pl.Series("secteur_non_salarie", row.tolist(), dtype=pl.String),
        pl.Series(GERANT_GROSS_PAY, gross_pay),
    )
    total_weight = float(weight[self_employed].sum())
    stats = SelfEmploymentStats(
        self_employed=total_weight,
        micro_entrepreneurs=float(weight[self_employed & micro].sum()),
        agricoles=float(weight[self_employed & (row == AGRICULTURE)].sum()),
        gerants=float(weight[np.isin(regime, ("gerant_bic", "gerant_bnc"))].sum()),
        share_zero=(float(weight[self_employed & (annual == 0)].sum()) / total_weight
                    if total_weight > 0 else 0.0),
        total_before_calibration=before,
        total_after_calibration=float((annual * weight).sum()),
        calibration_factor=factor,
        gerants_taxable_pay=float((gross_pay * weight).sum()) * IMPOSABLE_SUR_BRUT,
    )
    return enriched, stats


def attach_incomes(
    frame: pl.DataFrame, seed: int = SEED, targets_scale: float | None = None
) -> tuple[pl.DataFrame, IncomeStats]:
    """Add `salaire_brut_annuel`, `pension_annuelle`, `chomage_annuel`, `loyer_mensuel`,
    `part_salaire_exoneree`, and the self-employment columns of `attach_self_employment`.

    `targets_scale` multiplies the four national calibration targets — the wage
    bill, the self-employment income, the pension mass and the unemployment mass —
    before they are imposed on
    this frame. It exists because **the calibration divides a national total among
    whatever weights it is handed**, and says nothing about whether those weights
    are the country. Handed a sample, it makes the sample rich: the committed
    400-household fixture came out with a mean annual salary of 20.6 M€ and a
    minimum of 3.0 M€, which put 397 of its 439 foyers into the contribution
    exceptionnelle sur les hauts revenus and left the prime d'activité identically
    zero (D-149).

    Left as `None` on a frame that is the country, it is 1.0 and nothing changes.
    Left as `None` on a sample, this raises rather than quietly producing
    millionaires. A caller who genuinely wants the national target on a sample —
    reproducing the pre-D-149 vintage — passes `1.0` explicitly and says so.
    """
    share = household_share_of_france(frame)
    if targets_scale is None:
        if share < REPRESENTATIVE_SHARE_MIN:
            published = f"{margins.HOUSEHOLDS.value:,.0f}".replace(",", " ")
            bill = f"{margins.TOTAL_GROSS_WAGES.value / 1e9:,.0f}".replace(",", " ")
            raise IncomeScaleError(
                f"this frame's weights represent {share:.2%} of the published "
                f"household count ({published}), so calibrating the national wage "
                f"bill onto it would divide {bill} bn € among a sample and make "
                "every household in it rich. Pass `targets_scale=` — "
                f"{share:.6f} scales the targets to this frame — or 1.0 to insist."
            )
        targets_scale = 1.0

    rng = np.random.default_rng(seed)
    n = frame.height
    weight = frame["weight"].to_numpy().astype(np.float64)

    # The self-employed first, on their own stream: the gérants majoritaires among them are
    # paid out of D11, so their gross salary must be known before the employees' share is.
    frame, self_employment = attach_self_employment(frame, seed, targets_scale)
    gerant_gross = frame[GERANT_GROSS_PAY].to_numpy().astype(np.float64)
    frame = frame.drop(GERANT_GROSS_PAY)

    # ---- wages ------------------------------------------------------------
    employee = frame["is_salarie"].to_numpy() & (
        frame["statut_activite"].to_numpy() == "employed"
    )
    net_eqtp = _draw_net_eqtp(frame, rng)
    gross_annual = net_eqtp / margins.NET_TO_GROSS_RATIO.value * 12.0
    gross_annual *= frame["quotite_travail"].to_numpy()
    wages = np.where(employee, gross_annual, 0.0)

    before = float((wages * weight).sum())
    gerants_gross = float((gerant_gross * weight).sum())
    target = margins.TOTAL_GROSS_WAGES.value * targets_scale - gerants_gross
    # The one calibration on incomes, and therefore spent: the wage bill can never
    # afterwards appear as a validation line (§4.3). D11 holds the gérants' pay too.
    factor = target / before if before > 0 else 1.0
    wages = np.where(employee, wages * factor, gerant_gross)

    # The share of an employee's taxable salary the income tax exempts: D11 holds overtime,
    # apprentices' pay, placed profit-sharing and the rest the declarations do not, so its
    # taxable part runs above the salaries declared. One share for every employee, set so
    # that their taxable salaries make `DECLARED_TAXABLE_WAGES` (a hypothesis on who: the
    # breakdown is not published); read by the income tax only (engine correction 24).
    employees_taxable = IMPOSABLE_SUR_BRUT * float((np.where(employee, wages, 0.0)
                                                    * weight).sum())
    exempt_share = (max(0.0, 1.0 - margins.DECLARED_TAXABLE_WAGES.value * targets_scale
                        / employees_taxable) if employees_taxable > 0 else 0.0)

    # ---- pensions ---------------------------------------------------------
    age = frame["age"].to_numpy()
    inactive = frame["statut_activite"].to_numpy() == "inactive"
    pensioner = inactive & (age >= RETIREMENT_AGE)
    pension_draw = np.where(
        pensioner, np.exp(rng.standard_normal(n) * PENSION_SIGMA), 0.0
    )
    pension_mass = float((pension_draw * weight).sum())
    pensions = (
        pension_draw * (margins.DECLARED_PENSIONS.value * targets_scale / pension_mass)
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
        chomage_draw
        * (margins.UNEMPLOYMENT_BENEFIT_SPEND.value * targets_scale / chomage_mass)
        if chomage_mass > 0
        else chomage_draw
    )

    # ---- rent: by tenure, zone and size (`logement`, étape al) -------------
    rent = logement.monthly_rent(frame["statut_occupation"].to_numpy(),
                                 frame["zone_apl"].to_numpy(), logement.household_size(frame))

    enriched = frame.with_columns(
        pl.Series("salaire_brut_annuel", wages),
        pl.Series(EXEMPT_SHARE, np.where(employee & (wages > 0), exempt_share, 0.0)),
        pl.Series("pension_annuelle", pensions),
        pl.Series("chomage_annuel", chomage),
        pl.Series("loyer_mensuel", rent),
    )
    self_employed = enriched["regime_non_salarie"].is_not_null().to_numpy()

    no_income = ~(employee | pensioner | unemployed | self_employed) & (age >= 18)
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
        targets_scale=targets_scale,
        self_employment=self_employment,
        gerants_gross_pay=gerants_gross,
        exempt_wage_share=exempt_share,
    )
    return enriched, stats
