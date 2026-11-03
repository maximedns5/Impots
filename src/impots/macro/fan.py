"""B3 — the fan (PHASE4_SPEC §1).

Monte Carlo over the parameters that survived M1's verification, reporting p10/p50/p90
per indicator per horizon, with the spread decomposed into parameter and scenario
contributions. Never a point estimate.

**A SECOND DOUBLE COUNT, CAUGHT HERE.** §1 asks the IO layer to supply "the
import-leakage correction to the impulse, which scales the aggregate impulse handed to
B3". That instruction is safe only for a multiplier that does not already contain
leakage. Mésange's does: p104 reports the first-year figure of 1.31 as what survives
after "l'éviction par les importations", and every variant table carries an Importations
row. Scaling the impulse by `1 - leakage` before applying such a multiplier would
subtract France's import propensity twice, quietly removing about a quarter of every
effect.

So leakage is **computed, reported, and not applied** — the same shape as the Type I
rule one level down. B2's shares already exclude the directly imported part of final
demand, which is where the measurement legitimately does its work; the aggregate path
takes the impulse whole.

What the verification left standing, and what it did not:

* multipliers and employment, per instrument, at 1, 2 and 3 years — the long horizons
  are refused, since they are set by a specification choice rather than measured;
* a width for the multiplier, from cross-study dispersion, whose scope problem rides on
  every number it produces;
* NO revenue-feedback loop: the elasticity row came back WRONG, so Δdeficit stops at
  mechanical plus behavioural and this layer does not close the public balance;
* NO usable cycle scenario: the regime effect is established on the spending side, and
  the instruments this repository simulates are fiscal, so the toggle exists and refuses
  to apply itself rather than silently contributing zero.

The last two are why the decomposition normally reports all of the spread as parameter
uncertainty. That is a fact about the evidence, not a property of the method, and the
assumptions strip has to say so.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from impots.macro import mesange
from impots.macro.io_layer import Composition
from impots.macro.shocks import Impulse
from impots.macro.store import Store, TableParameter

#: Distinct from the behavioural band's seed: two fans that moved together whenever one
#: was reseeded would look like agreement.
SEED = 20260903
DRAWS = 1_000

#: Reported quantiles. Deliberately not a mean — a mean invites being read as the
#: answer, which is the one reading this layer must not support.
QUANTILES = (10, 50, 90)

#: Half-width of the triangular draw, as a multiple of the published standard deviation.
#: A symmetric triangular on [c-a, c+a] has variance a²/6, so a = sd·√6 makes the drawn
#: dispersion equal the measured one.
#:
#: The shape is a CONVENTION and the sources refute the alternatives: Gechert reports
#: the multiplier distributions as "by and large not normally distributed" and
#: multimodal. Nothing available characterises the shape, so this reproduces the one
#: moment that is published and claims nothing about the rest.
TRIANGULAR_HALF_WIDTH = np.sqrt(6.0)

#: Mésange instrument to IMK impulse family, for the width.
#:
#: Every fiscal instrument maps to TAX because the meta-analysis pools them: "We do not
#: distinguish between the various types of taxation", and its TAX column is defined as
#: "tax reliefs to private sector". The width is therefore COMMON where the centre is
#: specific — VAT and income tax get the same band around different centres. Recorded
#: rather than hidden, since it is the sharpest limit on what the fan's width means.
MULTIPLIER_FAMILY = {
    "impot_sur_le_revenu": "TAX",
    "csg": "TAX",
    "cotisations_salaries": "TAX",
    "cotisations_employeurs": "TAX",
    "cotisations_employeurs_ciblees": "TAX",
    "tva": "TAX",
    "taxe_carbone": "TAX",
    "investissement_public": "INVEST",
    "depense_publique": "GSPEND",
}

#: The L4 banner, in the spirit §4 requires and with the factor removed. D-057: "un
#: facteur 3 à 5" was a ratio of raw subsample means the same paper's controlled
#: estimate contradicts, and nothing in the literature yields 5.
BANNER = (
    "Couche macro (L4) : ordre de grandeur et composition, pas une prévision. "
    "L'éventail des estimations crédibles pour un même choc est large — la dispersion "
    "entre études publiées est du même ordre que la valeur centrale elle-même. C'est "
    "une propriété de la littérature, pas de ce modèle."
)


class FanError(RuntimeError):
    """The fan was asked for something the evidence does not support."""


@dataclass(frozen=True)
class Quantiles:
    p10: float
    p50: float
    p90: float

    @property
    def width(self) -> float:
        return self.p90 - self.p10

    def __str__(self) -> str:
        return f"[{self.p10:,.0f} … {self.p50:,.0f} … {self.p90:,.0f}]"


@dataclass(frozen=True)
class Decomposition:
    """Where the spread comes from, reported separately as §1 requires."""

    parameter: float
    scenario: float
    scenario_available: bool
    scenario_unavailable_because: str = ""

    @property
    def parameter_share(self) -> float:
        total = self.parameter + self.scenario
        return self.parameter / total if total > 0 else 1.0


@dataclass(frozen=True)
class Assumptions:
    """Everything the fan may not render without (§4)."""

    cycle_state: str
    design: str
    leakage: float
    leakage_applied: bool
    horizons: tuple[str, ...]
    parameters_vintage: str
    grade: str
    covered_share: float
    instruments: tuple[str, ...]
    simulation_conditions: str
    caveats: tuple[str, ...] = ()
    banner: str = BANNER


@dataclass(frozen=True)
class FanResult:
    gdp_eur: dict[str, Quantiles]
    jobs_thousands_etp: dict[str, Quantiles]
    decomposition: dict[str, Decomposition]
    assumptions: Assumptions
    composition: Composition | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def horizons(self) -> tuple[str, ...]:
        return tuple(self.gdp_eur)


def _quantiles(draws: np.ndarray) -> Quantiles:
    p10, p50, p90 = np.percentile(draws, QUANTILES)
    return Quantiles(float(p10), float(p50), float(p90))


def _draw_multiplier(rng: np.random.Generator, centre: float, spread: float,
                     draws: int) -> np.ndarray:
    if spread <= 0:
        raise FanError(
            "a multiplier with no sourced spread would render as a point estimate, "
            "which this layer must never produce"
        )
    half = spread * TRIANGULAR_HALF_WIDTH
    return rng.triangular(centre - half, centre, centre + half, draws)


def _grade(impulse_points: float, support: float | None) -> str:
    """Applicability grading, as in Phase 3: how far outside its evidence this runs."""
    if support is None:
        return "no-evidence"
    if impulse_points <= support:
        return "in-support"
    return "illustrative"


def run(impulse: Impulse, store: Store, *, gdp_eur: float,
        composition: Composition | None = None,
        cycle_state: str = "normal", draws: int = DRAWS,
        seed: int = SEED) -> FanResult:
    """The fan, for one impulse.

    `gdp_eur` is needed only for the employment arm and for grading: the multiplier is a
    GDP response per point of GDP of impulse, so applied to an impulse in euros the
    level cancels. The employment coefficients are published per point of GDP and do
    not cancel, which is why the caller must say what a point is worth.
    """
    multipliers = _require(store, "multiplier_by_instrument")
    jobs = _require(store, "employment_by_instrument")
    dispersion = _require(store, "multiplier_dispersion")

    if not impulse.by_instrument:
        raise FanError(
            "no instrument in this reform has a published multiplier; there is no "
            "macro path to fan, and the caller must say so rather than draw a zero"
        )
    if gdp_eur <= 0:
        raise FanError("GDP must be positive to express an impulse in points of it")

    rng = np.random.default_rng(seed)
    # The horizons both rows read: the multiplier's reach 5 and 10 years for the loop's
    # « lue » persistence (D-336), the jobs' stop at three.
    horizons = tuple(h for h in multipliers.usable_horizons if h in jobs.usable_horizons)
    gdp_draws = {h: np.zeros(draws) for h in horizons}
    job_draws = {h: np.zeros(draws) for h in horizons}
    caveats: list[str] = []

    for instrument, amount in impulse.by_instrument.items():
        spec = mesange.VARIANTS[instrument]
        family = MULTIPLIER_FAMILY.get(instrument)
        if family is None:
            raise FanError(f"no dispersion family declared for {instrument!r}")
        spread = dispersion.at(family, "all")
        # The impulse in points of GDP, on the basis the variant was actually run: the
        # VAT variant costs 1.18 points ex ante for one point net, so a reform costed
        # gross must be divided by that or it takes a multiplier 18 % too large.
        points = (amount / gdp_eur) * 100.0 / spec.ex_ante_points
        if spec.caveat:
            caveats.append(f"{instrument} : {spec.caveat}")

        for horizon in horizons:
            centre = multipliers.at(instrument, horizon)
            drawn = _draw_multiplier(rng, centre, spread, draws)
            # NO leakage factor here. See the module docstring: Mésange's multiplier is
            # already net of import crowding-out.
            gdp_draws[horizon] += drawn * amount / spec.ex_ante_points
            # Employment carries the multiplier's uncertainty proportionally: within a
            # variant, jobs and output move together at the model's own calibration, and
            # no source gives employment a dispersion of its own. An assumption, and the
            # only one available.
            ratio = np.divide(drawn, centre, out=np.ones_like(drawn), where=centre != 0)
            job_draws[horizon] += jobs.at(instrument, horizon) * points * ratio

    support = multipliers.support.max_variation_graded_in_support
    total_points = sum(
        abs(v / mesange.VARIANTS[k].ex_ante_points) for k, v in impulse.by_instrument.items()
    ) / gdp_eur * 100.0
    grade = _grade(total_points, support)

    scenario_reason = _scenario_unavailable(store, impulse)
    decomposition = {
        h: Decomposition(
            parameter=float(np.percentile(gdp_draws[h], 90) - np.percentile(gdp_draws[h], 10)),
            scenario=0.0,
            scenario_available=not scenario_reason,
            scenario_unavailable_because=scenario_reason,
        )
        for h in horizons
    }

    return FanResult(
        gdp_eur={h: _quantiles(gdp_draws[h]) for h in horizons},
        jobs_thousands_etp={h: _quantiles(job_draws[h]) for h in horizons},
        decomposition=decomposition,
        composition=composition,
        assumptions=Assumptions(
            cycle_state=cycle_state,
            design="Type I + multiplicateur de littérature ; propagation sectorielle et "
                   "multiplicateur agrégé ont des rôles disjoints",
            leakage=composition.leakage if composition else float("nan"),
            leakage_applied=False,
            horizons=horizons,
            parameters_vintage=store.vintage(),
            grade=grade,
            covered_share=impulse.covered_share,
            instruments=tuple(sorted(impulse.by_instrument)),
            simulation_conditions=mesange.SIMULATION_CONDITIONS,
            caveats=tuple(caveats),
        ),
        notes=(
            "Fuite à l'importation calculée et AFFICHÉE, mais NON APPLIQUÉE : le "
            "multiplicateur Mésange est déjà net de l'éviction par les importations.",
            "Pas de boucle de retour de recettes : la ligne d'élasticité est morte "
            "(verdict WRONG), donc cette couche ne boucle pas le solde public.",
            "Emploi en ÉQUIVALENTS TEMPS PLEIN, à ne pas additionner aux personnes "
            "comptées par la couche entrées-sorties.",
        ),
    )


def _require(store: Store, key: str) -> TableParameter:
    if key not in store.tables:
        reason = store.removed.get(key) or store.rejected.get(key) or "absent"
        raise FanError(f"the fan needs {key!r}, which did not load: {reason[:200]}")
    return store.tables[key]


def _scenario_unavailable(store: Store, impulse: Impulse) -> str:
    """Why the cycle scenario cannot be varied for this reform, if it cannot.

    §1 requires the cycle state to be a user-visible scenario, never estimated. The
    sourced magnitude for the gap between two states exists — but the meta-regression
    establishes it on the SPENDING side only, and the instruments this repository
    simulates are fiscal. Applying it to them would contradict the paper that supplies
    it, so the toggle refuses instead of contributing zero silently.
    """
    shift = store.tables.get("multiplier_regime_shift")
    if shift is None:
        return "la ligne de régime conjoncturel n'est pas chargée"
    if not shift.responds_to_knobs:
        fiscal = sorted(
            i for i in impulse.by_instrument if MULTIPLIER_FAMILY.get(i) == "TAX"
        )
        if fiscal:
            return (
                "l'effet de régime n'est établi que du côté DÉPENSE (Gechert et "
                "Rannenberg, tableau 4 : haut de cycle non significatif), et les "
                f"instruments de cette réforme sont fiscaux ({', '.join(fiscal)}). "
                "Le décalage n'est donc pas applicable ici."
            )
    return ""
