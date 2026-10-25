"""The v1 behavioural channels (PHASE3_SPEC §3).

Each channel is arithmetic over quantities the mechanical runners already produced.
None of them touches the engine, and none of them changes a mechanical number: a
channel reports what the mechanical result would become *if* a response of the
estimated size occurred, and the mechanical figure stays exactly where it was.

**A channel fails loudly when its inputs are missing.** That is the Phase 1 lesson
repaid: pensions and unemployment were computed and then quietly dropped by a wiring
step, every guard stayed green, and RSA came out at three times its published value.
A channel here that cannot find the marginal rates it needs raises; it does not
return a zero that looks like an answer.

**A knob no channel claims produces a sentence, not a zero.** "Mechanical only — no
evidence-based channel wired for this instrument" is a true statement about the state
of the evidence. A silent zero is a false statement about behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from impots.behavioural.store import Store

#: 1 - τ' must stay positive to take a log. French marginal rates above 100 % are
#: real — two tapers overlapping do it — so this floor is reached by genuine
#: households, not only by arithmetic accidents, and the count is reported.
NET_OF_TAX_FLOOR = 0.05


class ChannelInputMissing(RuntimeError):
    """A channel was handed inputs it cannot use."""


def _unsupplied(key: str, label: str, unit: str, needed: str) -> ChannelResult:
    """The caller did not supply this channel's inputs at all.

    Distinct from `ChannelInputMissing`, and the distinction is the whole point. A
    channel that was PROMISED data and handed something empty raises — that is the
    Phase 1 lesson, where inputs were computed and then silently dropped and every
    guard stayed green. A channel whose caller simply did not compute its inputs for
    this run has nothing wrong with it and says so.
    """
    return ChannelResult(
        key=key, label=label, applies=False, unit=unit,
        message=f"Non calculé : ce chiffrage ne fournit pas {needed}.",
    )


@dataclass
class ChannelResult:
    key: str
    label: str
    applies: bool
    """False when no knob in the reform is one this channel prices."""
    draws: np.ndarray | None = None
    """One value per Monte Carlo draw, in euros of revenue (negative = costs the
    state). None when the channel does not apply."""
    unit: str = "EUR"
    in_revenue_band: bool = False
    """Whether this channel's draws are a change in STATE REVENUE that belongs in the
    headline band.

    Declared per channel rather than inferred from the unit, because the unit does not
    settle it. C3 is denominated in euros and must still stay out: it reallocates a
    contribution change between employers and wages, and the mechanical total is
    identical at both ends of its range. Adding it would count the same euros twice.
    C2 is in jobs and C4 in per cent, so those two are excluded twice over."""
    message: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def central(self) -> float | None:
        return None if self.draws is None else float(np.median(self.draws))


def _knobs(reform: Any) -> list[str]:
    """The knob names a reform actually sets."""
    if reform is None:
        return []
    dumped = reform.model_dump(exclude_none=True)
    return sorted(dumped)


def _claimed(store: Store, reform: Any, keys: tuple[str, ...]) -> list[str]:
    """Knobs in this reform that any of `keys` claims to price."""
    return [
        knob for knob in _knobs(reform)
        if any(key in store and store[key].claims(knob) for key in keys)
    ]


# --------------------------------------------------------------------------- #
# C1 — elasticity of taxable income, on income-tax reforms
# --------------------------------------------------------------------------- #
C1_KEYS = ("eti_all", "eti_top_decile")


def elasticity_of_taxable_income(
    store: Store,
    reform: Any,
    *,
    emtr_baseline: np.ndarray,
    emtr_reform: np.ndarray,
    taxable_base: np.ndarray,
    weights: np.ndarray,
    top_decile: np.ndarray,
    draws: int,
    rng: np.random.Generator,
) -> ChannelResult:
    """Revenue returned or lost when taxable income responds to its marginal rate.

    Worked example, derived by hand and pinned in the tests:

        a household with a taxable base of 100 000 EUR whose marginal rate goes from
        41 % to 45 %. The net-of-tax rate falls from 0.59 to 0.55, so
        Δln(1-τ') = ln(0.55) - ln(0.59) = -0.0702043. With e = 0.30,
        Δbase = 0.30 × 100 000 × (-0.0702043) = -2 106.13 EUR, and the revenue offset
        is 0.45 × (-2 106.13) = -947.76 EUR. The mechanical yield of that rate rise on
        this household is 0.04 × 100 000 = 4 000 EUR, so the response gives back 23.7 %
        of it — which is the number this channel exists to show.
    """
    applicable = _claimed(store, reform, C1_KEYS)
    if not applicable:
        return ChannelResult(
            key="c1_eti", label="Réponse du revenu imposable", applies=False,
            message="Mécanique seulement — aucun canal fondé sur des preuves n'est "
                    "câblé pour cet instrument.",
        )
    missing = [key for key in C1_KEYS if key not in store]
    if missing:
        return ChannelResult(
            key="c1_eti", label="Réponse du revenu imposable", applies=False,
            message=f"Aucune élasticité utilisable : {', '.join(missing)} n'a pas "
                    f"survécu à la vérification des sources.",
            diagnostics={"missing_parameters": missing},
        )
    supplied = {"emtr_baseline": emtr_baseline, "emtr_reform": emtr_reform,
                "taxable_base": taxable_base, "weights": weights}
    if all(array is None for array in supplied.values()):
        return _unsupplied("c1_eti", "Réponse du revenu imposable", "EUR",
                           "les taux marginaux des ménages")
    for name, array in supplied.items():
        if array is None or not len(array):
            raise ChannelInputMissing(f"C1 needs {name}; it is empty")

    net_baseline = np.clip(1.0 - emtr_baseline, NET_OF_TAX_FLOOR, None)
    net_reform = np.clip(1.0 - emtr_reform, NET_OF_TAX_FLOOR, None)
    delta_log = np.log(net_reform) - np.log(net_baseline)

    all_draws = store["eti_all"].draw(rng, draws)
    top_draws = store["eti_top_decile"].draw(rng, draws)

    # One elasticity per household per draw, without materialising the outer product:
    # the response is linear in e, so the two groups can be summed separately.
    lower = ~top_decile
    weighted_lower = float(
        np.sum(weights[lower] * taxable_base[lower] * delta_log[lower] * emtr_reform[lower])
    )
    weighted_top = float(
        np.sum(weights[top_decile] * taxable_base[top_decile] * delta_log[top_decile]
               * emtr_reform[top_decile])
    )
    revenue = all_draws * weighted_lower + top_draws * weighted_top

    return ChannelResult(
        key="c1_eti", label="Réponse du revenu imposable", applies=True, draws=revenue,
        in_revenue_band=True,
        message="La base imposable réagit au taux marginal ; l'effet est un retour "
                "(ou une perte) sur le rendement mécanique.",
        diagnostics={
            "knobs": applicable,
            "mean_delta_log_net_of_tax": float(
                np.average(delta_log, weights=weights) if weights.sum() else 0.0
            ),
            "households_at_the_net_of_tax_floor": int(
                np.count_nonzero(1.0 - emtr_reform < NET_OF_TAX_FLOOR)
            ),
        },
    )


# --------------------------------------------------------------------------- #
# C2 — employment at the SMIC, C3 — incidence: wired, and dormant in v1
# --------------------------------------------------------------------------- #
C2_KEYS = (
    "employment_elasticity_smic",
    "employment_elasticity_at_fadeout",
    "employment_fadeout_smic_multiple",
)
C3_KEYS = ("passthrough_benefit_linked", "passthrough_unlinked")

NO_EMPLOYER_KNOB = (
    "Mécanique seulement : aucun paramètre de cotisation patronale n'est bougé par "
    "cette réforme, donc rien ne déclenche ce canal."
)


def employment_elasticity_profile(
    smic_multiple: np.ndarray, at_smic: float, at_fadeout: float, fadeout: float
) -> np.ndarray:
    """Elasticity by wage, in multiples of the SMIC.

    The French evidence gives two points and a direction: an elasticity around −0.43
    at the minimum wage, and a curve that declines to about −0.1 by twice it. **The
    straight line between them is this project's construction, not the
    literature's**, and above the fade-out the response is zero — not a small
    constant. An earlier version carried −0.2 above 2 SMIC on the strength of a
    Swedish study that was never cited and whose downloaded PDF turned out to be a
    different paper; that row is gone, and refusing to extrapolate is what replaced it.
    """
    span = max(fadeout - 1.0, 1e-9)
    fraction = np.clip((smic_multiple - 1.0) / span, 0.0, 1.0)
    interpolated = at_smic + fraction * (at_fadeout - at_smic)
    return np.where(smic_multiple <= fadeout, interpolated, 0.0)


def employment_at_the_smic(
    store: Store,
    reform: Any,
    *,
    smic_multiple: np.ndarray | None = None,
    relative_cost_change: np.ndarray | None = None,
    weights: np.ndarray | None = None,
    draws: int = 1,
    rng: Any = None,
    **_: Any,
) -> ChannelResult:
    """Jobs gained or lost when labour cost moves at and around the minimum wage.

    Worked example, hand-derived and pinned in the tests: one job at the SMIC whose
    labour cost falls 2 %. At an elasticity of −0.43 the response is
    −0.43 × (−0.02) = +0.0086 jobs — 0.86 % of a job, which for a weighted cell of
    100 000 such workers is 860 jobs.

    One round only, and stated: the wage-bill and contribution feedback of those jobs
    is reported, never iterated back into the tax calculation. Iterating is general
    equilibrium and belongs to a layer this project has not built.
    """
    applicable = _claimed(store, reform, C2_KEYS)
    if not applicable:
        return ChannelResult(
            key="c2_employment", label="Emploi au voisinage du SMIC",
            applies=False, unit="emplois", message=NO_EMPLOYER_KNOB,
        )
    missing = [key for key in C2_KEYS if key not in store]
    if missing:
        return ChannelResult(
            key="c2_employment", label="Emploi au voisinage du SMIC",
            applies=False, unit="emplois",
            message=f"Aucune élasticité utilisable : {', '.join(missing)} n'a pas "
                    f"survécu à la vérification des sources.",
            diagnostics={"missing_parameters": missing},
        )
    supplied = {"smic_multiple": smic_multiple,
                "relative_cost_change": relative_cost_change, "weights": weights}
    if all(array is None for array in supplied.values()):
        return _unsupplied("c2_employment", "Emploi au voisinage du SMIC", "emplois",
                           "le profil de salaires ni la variation du coût du travail")
    for name, array in supplied.items():
        if array is None or not len(array):
            raise ChannelInputMissing(f"C2 needs {name}; it is empty")

    fadeout = store["employment_fadeout_smic_multiple"].central
    at_fadeout = store["employment_elasticity_at_fadeout"].central
    smic_draws = store["employment_elasticity_smic"].draw(rng, draws)

    # The response is linear in the SMIC elasticity, so each draw only rescales the
    # part of the profile anchored there. Split it once rather than building a
    # draws x individuals matrix.
    profile_at_one = employment_elasticity_profile(
        smic_multiple, 1.0, 0.0, fadeout)          # weight on the SMIC elasticity
    profile_at_fade = employment_elasticity_profile(
        smic_multiple, 0.0, 1.0, fadeout)          # weight on the fade-out value
    # SIGN, spelled out because it is the easy thing to get backwards. The
    # elasticity is NEGATIVE and a cut makes `relative_cost_change` negative, so
    # their product is positive: cheaper labour, more jobs. There is no extra
    # negation, and a first version that had one reported 99 000 jobs LOST from a
    # 1.5 % cut in labour cost.
    exposure = weights * relative_cost_change
    anchor = float(np.sum(exposure * profile_at_one))
    tail = float(np.sum(exposure * profile_at_fade)) * at_fadeout
    # `+ 0.0` turns a signed zero into zero. With every moved euro above the fade-out,
    # the products sum to +0.0 and the negative elasticity makes it −0.0, which a page
    # prints « −0,00 » emplois (D-252). Exact for any other value.
    jobs = smic_draws * anchor + tail + 0.0

    below = float(weights[smic_multiple <= fadeout].sum() / weights.sum()) if weights.sum() else 0.0
    return ChannelResult(
        key="c2_employment", label="Emploi au voisinage du SMIC", applies=True,
        draws=jobs, unit="emplois",
        message="L'emploi réagit au coût du travail sous deux fois le SMIC ; "
                "au-dessus, aucune réponse n'est appliquée faute de preuve.",
        diagnostics={
            "knobs": applicable,
            "share_of_workers_below_fadeout": round(below, 4),
            "fadeout_smic_multiple": fadeout,
            "interpolation": "linéaire entre le SMIC et le seuil — construction de ce "
                             "projet, pas de la littérature",
        },
    )


#: How a moved contribution is classified for incidence. French maladie and famille
#: contributions are **not** benefit-linked — cover is universal, so a worker's own
#: entitlement does not depend on what was paid — and the réduction générale spans
#: contributions of both kinds at once. So no knob here selects a single class, and
#: C3 reports the RANGE between the two assumptions rather than picking one.
LINKAGE_IS_MIXED = (
    "Aucun de ces leviers ne bouge une cotisation d'une seule classe : la maladie et "
    "la famille sont universelles en France, donc non contributives, et la réduction "
    "générale porte sur des cotisations des deux natures à la fois. La fourchette "
    "couvre les deux hypothèses d'incidence au lieu d'en choisir une."
)


def contribution_incidence(
    store: Store,
    reform: Any,
    *,
    contribution_delta: float = 0.0,
    draws: int = 1,
    rng: Any = None,
    **_: Any,
) -> ChannelResult:
    """Who bears a change in employer contributions — reallocates, never changes totals.

    The band is the incidence uncertainty made visible: at one end the whole change
    reaches wages, at the other it stays with the employer. The mechanical total is
    identical under both, which is exactly why this is a separate line and not an
    adjustment to the revenue figure.
    """
    applicable = _claimed(store, reform, C3_KEYS)
    if not applicable:
        return ChannelResult(
            key="c3_incidence", label="Incidence des cotisations patronales",
            applies=False, unit="EUR", message=NO_EMPLOYER_KNOB,
        )
    missing = [key for key in C3_KEYS if key not in store]
    if missing:
        return ChannelResult(
            key="c3_incidence", label="Incidence des cotisations patronales",
            applies=False, unit="EUR",
            message=f"Aucune élasticité utilisable : {', '.join(missing)} n'a pas "
                    f"survécu à la vérification des sources.",
            diagnostics={"missing_parameters": missing},
        )
    if contribution_delta is None:
        return _unsupplied("c3_incidence", "Incidence des cotisations patronales",
                           "EUR", "la variation mécanique des cotisations patronales")
    if not contribution_delta:
        return ChannelResult(
            key="c3_incidence", label="Incidence des cotisations patronales",
            applies=False, unit="EUR",
            message="Cette réforme ne déplace aucune cotisation patronale : il n'y a "
                    "rien à répartir entre entreprises et salaires.",
        )
    half = max(draws // 2, 1)
    passthrough = np.concatenate([
        store["passthrough_unlinked"].draw(rng, draws - half),
        store["passthrough_benefit_linked"].draw(rng, half),
    ])
    # SIGN: `contribution_delta` is the change in the EMPLOYER's bill, so a cut is
    # negative — and a cut that passes through fully makes wages RISE by its amount.
    # Positive here therefore means workers gain.
    to_wages = -passthrough * contribution_delta
    return ChannelResult(
        key="c3_incidence", label="Incidence des cotisations patronales", applies=True,
        draws=to_wages, unit="EUR",
        message="Part de la variation de cotisations qui atteint les salaires — "
                "positif signifie que les salariés y gagnent. Le "
                "total mécanique est le même aux deux bouts de la fourchette : c'est "
                "la répartition entre entreprises et salariés qui change. "
                + LINKAGE_IS_MIXED,
        diagnostics={
            "knobs": applicable,
            "contribution_delta": contribution_delta,
            "linkage": "mixte — fourchette entre non liée (0,0) et liée (1,0)",
        },
    )


# --------------------------------------------------------------------------- #
# C4 — production taxes and investment: the zero band
# --------------------------------------------------------------------------- #
C4_KEYS = ("production_tax_investment",)


def production_tax_investment(
    store: Store, reform: Any, *, production_tax_baseline: float = 0.0,
    production_tax_reform: float = 0.0, draws: int = 1, rng: Any = None, **_: Any,
) -> ChannelResult:
    """Investment response to a production-tax cut — the band centred on zero.

    Reported in **per cent of corporate investment**, not in euros, and therefore
    never summed into the revenue band. Investment is not revenue: adding the two
    would be a category error that happens to typecheck.

    The driver is the change in the LOG of the production tax, because that is the
    regressor in the study. Keeping it in logs also avoids the conversion that killed
    an earlier version of this row: −0.63 log points is a 47 % cut, not a 63 % one.

    A band centred on zero is not an absence of a finding. It is a serious search that
    turned up nothing robust, and its WIDTH says how much could have been missed —
    which is more informative than silence and quite different from a tight zero.
    """
    applicable = _claimed(store, reform, C4_KEYS)
    if not applicable:
        return ChannelResult(
            key="c4_investment", label="Investissement et impôts de production",
            applies=False, unit="%",
            message="Mécanique seulement — aucun canal fondé sur des preuves n'est "
                    "câblé pour cet instrument.",
        )
    if "production_tax_investment" not in store:
        return ChannelResult(
            key="c4_investment", label="Investissement et impôts de production",
            applies=False, unit="%",
            message="Aucune élasticité utilisable : la ligne n'a pas survécu à la "
                    "vérification des sources.",
        )
    if production_tax_baseline <= 0 or production_tax_reform <= 0:
        raise ChannelInputMissing(
            "C4 needs the production tax before and after, both strictly positive; "
            f"got {production_tax_baseline} and {production_tax_reform}"
        )
    parameter = store["production_tax_investment"]
    delta_log = float(np.log(production_tax_reform / production_tax_baseline))
    response = parameter.draw(rng, draws) * abs(delta_log) * np.sign(-delta_log)
    return ChannelResult(
        key="c4_investment", label="Investissement et impôts de production",
        applies=True, draws=response, unit="%",
        message="Aucune réponse d'investissement robuste n'est détectable ; la bande "
                "porte l'incertitude de l'étude, pas une absence de mesure.",
        diagnostics={
            "knobs": applicable,
            "delta_log_production_tax": round(delta_log, 5),
            "centred_on_zero": parameter.central == 0.0,
        },
    )


# --------------------------------------------------------------------------- #
# C5 — reported wealth and the tax rate: the band that is centred on zero because
#      the study could not detect a response
# --------------------------------------------------------------------------- #
C5_KEYS = ("wealth_tax_rate_elasticity",)


def wealth_rate_response(
    store: Store, reform: Any, *, wealth_base_eur: float = 0.0,
    marginal_rate_baseline: float = 0.0, marginal_rate_reform: float = 0.0,
    draws: int = 1, rng: Any = None, **_: Any,
) -> ChannelResult:
    """Response of REPORTED taxable wealth to the marginal rate.

    Centred on zero, and that is the finding rather than a hedge: Garbinti et al.
    cannot reject the null of no bunching at pure tax kinks, and their four implied
    elasticities are statistically indistinguishable from zero. The band's WIDTH is
    what carries the information — how large a response their data could have missed.

    The driver is the change in the NET-OF-TAX retention rate, (1 - t), in logs, which
    is the object an elasticity of this kind is defined against. Using the change in
    the tax rate itself would be a different quantity that happens to have the same
    sign.
    """
    applicable = _claimed(store, reform, C5_KEYS)
    if not applicable:
        return ChannelResult(
            key="c5_wealth_rate", label="Patrimoine déclaré et taux", applies=False,
            message="Mécanique seulement — aucun canal fondé sur des preuves n'est "
                    "câblé pour cet instrument.",
        )
    if "wealth_tax_rate_elasticity" not in store:
        return ChannelResult(
            key="c5_wealth_rate", label="Patrimoine déclaré et taux", applies=False,
            message="Aucune élasticité utilisable : la ligne n'a pas survécu à la "
                    "vérification des sources.",
        )
    if wealth_base_eur <= 0:
        raise ChannelInputMissing(
            "C5 needs the taxable wealth base in euros, strictly positive; got "
            f"{wealth_base_eur}"
        )
    retention_before = 1.0 - marginal_rate_baseline
    retention_after = 1.0 - marginal_rate_reform
    if retention_before <= 0 or retention_after <= 0:
        raise ChannelInputMissing(
            "C5 needs marginal rates strictly below 1 at both ends; got "
            f"{marginal_rate_baseline} and {marginal_rate_reform}"
        )
    delta_log = float(np.log(retention_after / retention_before))
    parameter = store["wealth_tax_rate_elasticity"]
    # Base moves with the retention rate; revenue is the base change times the rate.
    base_change = parameter.draw(rng, draws) * delta_log * wealth_base_eur
    revenue = base_change * marginal_rate_reform
    return ChannelResult(
        key="c5_wealth_rate", label="Patrimoine déclaré et taux", applies=True,
        draws=revenue, in_revenue_band=True,
        message="Bande centrée sur ZÉRO : l'étude ne détecte aucune réponse du "
                "patrimoine déclaré aux coudes purs du barème. La largeur dit ce "
                "qu'elle aurait pu manquer, pas ce qu'elle a trouvé.",
        diagnostics={
            "knobs": applicable,
            "delta_log_retention": round(delta_log, 6),
            "centred_on_zero": parameter.central == 0.0,
        },
    )


# --------------------------------------------------------------------------- #
# C6 — disclosure requirements: the module's signature, and NOT in euros
# --------------------------------------------------------------------------- #
C6_KEYS = ("wealth_disclosure_growth_effect_pp",)

#: The horizon over which a growth-rate effect is reported. ONE year, stated rather
#: than assumed: the measured object is a change in the annual growth RATE, so its
#: cumulated effect depends entirely on how long it is allowed to run, and this
#: project refuses horizons beyond three years.
DISCLOSURE_HORIZON_YEARS = 1


def disclosure_response(
    store: Store, reform: Any, *, wealth_base_eur: float = 0.0,
    draws: int = 1, rng: Any = None, **_: Any,
) -> ChannelResult:
    """Reported wealth and the disclosure regime — the enforcement dial's channel.

    Reported in **per cent of the reported base over one year**, never in euros of the
    headline band, and the reason is the unit rather than caution. What Garbinti et al.
    measure is a change in the annual GROWTH RATE of reported wealth — 0,28 pp pooled,
    against a 2,2 % control growth. Turning that into a revenue figure requires a
    horizon, and a cumulated growth effect over an unstated horizon is precisely the
    confidently-wrong number this project refuses. The one-year euro equivalent is in
    the diagnostics, with the horizon named.

    THE SIGN IS AN ASSUMPTION AND IS LABELLED ONE. The reform studied LOOSENED
    disclosure and reported wealth fell. We apply the same magnitude with the opposite
    sign to a tightening, because that is the only thing the evidence permits — but the
    study observed only the loosening, and behavioural responses are not obliged to be
    symmetric.

    Why this dial exists at all: the same paper finds responses to disclosure are TEN
    TIMES those to rate kinks. A wealth-tax simulator with a rate dial and no
    enforcement dial would put the small lever in the user's hand and hide the large one.
    """
    applicable = _claimed(store, reform, C6_KEYS)
    if not applicable:
        return ChannelResult(
            key="c6_disclosure", label="Obligations déclaratives", applies=False,
            unit="%",
            message="Mécanique seulement — aucun canal fondé sur des preuves n'est "
                    "câblé pour cet instrument.",
        )
    if "wealth_disclosure_growth_effect_pp" not in store:
        return ChannelResult(
            key="c6_disclosure", label="Obligations déclaratives", applies=False,
            unit="%",
            message="Aucune mesure utilisable : la ligne n'a pas survécu à la "
                    "vérification des sources.",
        )
    direction = _disclosure_direction(reform)
    if direction == 0:
        return ChannelResult(
            key="c6_disclosure", label="Obligations déclaratives", applies=False,
            unit="%", message="Régime déclaratif inchangé.",
        )
    parameter = store["wealth_disclosure_growth_effect_pp"]
    # Percentage points of annual growth, applied over the stated horizon.
    percent = parameter.draw(rng, draws) * direction * DISCLOSURE_HORIZON_YEARS
    equivalent = float(np.median(percent)) / 100.0 * wealth_base_eur
    return ChannelResult(
        key="c6_disclosure", label="Obligations déclaratives", applies=True,
        draws=percent, unit="%",
        message="En POINTS de croissance annuelle du patrimoine déclaré, sur un an, et "
                "jamais en euros de la bande : cumuler un effet de croissance suppose "
                "un horizon. Le signe d'un durcissement est une hypothèse de symétrie "
                "— l'étude n'observe qu'un allègement.",
        diagnostics={
            "knobs": applicable,
            "direction": direction,
            "horizon_years": DISCLOSURE_HORIZON_YEARS,
            "one_year_base_equivalent_eur": round(equivalent, 2),
            "ten_times_the_rate_channel": True,
        },
    )


def _disclosure_direction(reform: Any) -> int:
    """+1 tightening, -1 loosening, 0 unchanged.

    Tightening RAISES reported wealth, which is why it takes the positive sign against
    a measured effect whose own sign was a fall under loosening.
    """
    if reform is None:
        return 0
    value = getattr(reform, "ifi_obligations_declaratives", None)
    return {"renforcees": 1, "allegees": -1}.get(value or "", 0)


# --------------------------------------------------------------------------- #
# C7 — labour supply: the channel D-031 killed, reopened cell by cell (D-220)
# --------------------------------------------------------------------------- #
#: Group (as the population layer assigns it) → the store row that prices it. One row
#: per table of Bargain, Orsini and Peichl's annex F; no average across them.
LABOUR_GROUPS = {
    "femmes_en_couple": "labour_supply_married_women",
    "hommes_en_couple": "labour_supply_married_men",
    "femmes_seules": "labour_supply_single_women",
    "hommes_seuls": "labour_supply_single_men",
}
C7_KEYS = tuple(LABOUR_GROUPS.values())

NO_LABOUR_KNOB = (
    "Aucun levier de cette réforme ne déplace le salaire net horaire par un prélèvement "
    "proportionnel : le canal ne s'ouvre que pour la CSG sur les revenus d'activité. "
    "L'IR relève de C1, dont l'élasticité contient déjà les heures."
)


def labour_supply(
    store: Store,
    reform: Any,
    *,
    labour_group: np.ndarray | None = None,
    labour_earnings: np.ndarray | None = None,
    labour_delta_log_net: np.ndarray | None = None,
    labour_weights: np.ndarray | None = None,
    labour_emtr: np.ndarray | None = None,
    draws: int = 1,
    rng: Any = None,
    **_: Any,
) -> ChannelResult:
    """Receipts from the hours people work when a levy moves their net hourly wage.

    For each person of the estimation sample, the group's elasticity of average hours,
    times the change in log net hourly wage, times their gross earnings, is the change in
    gross earnings; the household's marginal rate on an extra gross euro turns it into
    receipts. Applied at the group's level of earnings, the total-hours elasticity
    carries the participation margin with it, without simulating anyone into work.

    A COUPLE'S ROW IS OWN-WAGE PLUS CROSS-WAGE (D-220): the CSG on earnings moves both
    partners' net wages by the same share, and the paper prices each with the other's held
    fixed. One Δln per person is therefore enough; a reform that moved one partner's wage
    alone would need the two terms apart, and this channel does not open for one.

    Worked example, pinned in the tests: a woman in a couple earning 30 000 EUR whose net
    wage rises 1 % (Δln = 0,01) at the row's centre of 0,09 works enough more to earn
    30 000 × 0,09 × 0,01 = 27 EUR; at a marginal rate of 40 %, 10,80 EUR come back.

    THE LIMITS, stated where the number is made. The elasticity is to the GROSS wage and
    is applied to a NET-wage change: the paper shows the net-wage elasticity larger for
    married women, the only group it shows, so that row understates. Employer
    contributions on the extra earnings are not counted, which understates the receipts.
    The participation share of the response is valued at the household's marginal rate,
    not at a participation tax rate, in a direction nothing here can sign. Earners outside
    the paper's sample are priced at nothing and counted. And the hours never join the
    macro fan's jobs, nor C2's: three counts of work, three different objects (§6, rule 4).
    """
    applicable = _claimed(store, reform, C7_KEYS)
    if not applicable:
        return ChannelResult(key="c7_labour_supply", label="Offre de travail",
                             applies=False, unit="EUR", message=NO_LABOUR_KNOB)
    missing = [key for key in C7_KEYS if key not in store]
    if missing:
        return ChannelResult(
            key="c7_labour_supply", label="Offre de travail", applies=False, unit="EUR",
            message=f"Aucune élasticité utilisable : {', '.join(missing)} n'a pas "
                    f"survécu à la vérification des sources.",
            diagnostics={"missing_parameters": missing})
    supplied = {"labour_group": labour_group, "labour_earnings": labour_earnings,
                "labour_delta_log_net": labour_delta_log_net,
                "labour_weights": labour_weights, "labour_emtr": labour_emtr}
    if all(array is None for array in supplied.values()):
        return _unsupplied("c7_labour_supply", "Offre de travail", "EUR",
                           "les groupes, salaires et taux marginaux des actifs")
    for name, array in supplied.items():
        if array is None or not len(array):
            raise ChannelInputMissing(f"C7 needs {name}; it is empty")

    revenue = np.zeros(draws)
    gross = np.zeros(draws)
    persons: dict[str, int] = {}
    for group, key in LABOUR_GROUPS.items():
        mask = labour_group == group
        persons[group] = int(mask.sum())
        exposure = labour_weights[mask] * labour_earnings[mask] * labour_delta_log_net[mask]
        elasticity = store[key].draw(rng, draws)
        gross = gross + elasticity * float(exposure.sum())
        revenue = revenue + elasticity * float((exposure * labour_emtr[mask]).sum())
    outside = ~np.isin(labour_group, list(LABOUR_GROUPS))
    earnings = labour_weights * labour_earnings
    return ChannelResult(
        key="c7_labour_supply", label="Offre de travail", applies=True, draws=revenue,
        unit="EUR", in_revenue_band=True,
        message="Les heures réagissent au salaire net horaire, par groupe de l'article "
                "(couples et personnes seules, femmes et hommes ; pour un couple, "
                "élasticité au salaire propre plus élasticité croisée). Élasticité au "
                "salaire BRUT appliquée au salaire net ; actifs hors de l'échantillon de "
                "l'article comptés à zéro.",
        diagnostics={
            "knobs": applicable,
            "persons_by_group": persons,
            "persons_outside_the_sample": int(outside.sum()),
            "earnings_outside_the_sample_share": (
                round(float(earnings[outside].sum() / earnings.sum()), 4)
                if earnings.sum() > 0 else 0.0),
            "gross_earnings_change_eur": round(float(np.median(gross)), 2),
            "not_added_to": "les emplois de l'éventail macro et de C2",
        },
    )


# --------------------------------------------------------------------------- #
# C8 — company creations: §6.3, opened on the IPP's own table (D-221)
# --------------------------------------------------------------------------- #
C8_KEYS = ("firm_creation_profit_tax",)
#: Fixed row: points of the paper's joint virtual rate per point of IS normal rate.
C8_CONVERSION = "firm_creation_exposure_per_is_point"

NO_CREATION_KNOB = (
    "Aucun levier de cette réforme ne déplace le taux normal de l'IS : la seule réponse "
    "des créations de sociétés mesurée l'a été sur la baisse de ce taux et sur le PFU."
)


def firm_creations(
    store: Store,
    reform: Any,
    *,
    is_rate_change_points: float | None = None,
    draws: int = 1,
    rng: Any = None,
    **_: Any,
) -> ChannelResult:
    """The change in the annual creation rate of companies, in points, an IS normal-rate
    change would bring if the IPP's estimate held nationwide.

    AN INDEX, NEVER REVENUE, like C4: points of a rate are not euros, and the receipts
    of firms not yet created are nobody's mechanical figure.

    The IPP estimates the joint effect of the IS cut and the flat tax per point of fall in
    the virtual tax rate on profits, across sectors more and less exposed (D-221). A change
    of the IS normal rate reaches that virtual rate through the conversion row — this
    project's derivation: the share of a nominal point the sectors' shareholders saw in
    2018, net of the flat tax the released dividends then pay.

    ILLUSTRATIVE AT ANY SIZE: the estimate is relative between sectors, so the national
    effect is not identified, and the IS is not told apart from the flat tax — hence a
    support of zero and a range down to zero. The figure is the mean of the first six
    years after the cut, of an effect still growing at the end; a rise of the rate
    rests on a symmetry nobody observed.

    Worked example, pinned in the tests: +1 point of normal rate is 1 × 0,4538 = 0,4538
    point of virtual rate, and 0,38 × 0,4538 = 0,1724 point of creation rate lost.
    """
    applicable = _claimed(store, reform, C8_KEYS)
    if not applicable:
        return ChannelResult(key="c8_creations", label="Créations de sociétés",
                             applies=False, unit="points de taux de création",
                             message=NO_CREATION_KNOB)
    missing = [key for key in (*C8_KEYS, C8_CONVERSION) if key not in store]
    if missing:
        return ChannelResult(
            key="c8_creations", label="Créations de sociétés", applies=False,
            unit="points de taux de création",
            message=f"Aucune réponse utilisable : {', '.join(missing)} n'a pas survécu "
                    f"à la vérification des sources.",
            diagnostics={"missing_parameters": missing})
    if is_rate_change_points is None:
        return _unsupplied("c8_creations", "Créations de sociétés",
                           "points de taux de création", "la variation du taux normal de l'IS")
    exposure = -is_rate_change_points * store[C8_CONVERSION].central
    response = store[C8_KEYS[0]].draw(rng, draws) * exposure
    return ChannelResult(
        key="c8_creations", label="Créations de sociétés", applies=True, draws=response,
        unit="points de taux de création",
        message="Indice illustratif : effet relatif entre secteurs, étendu à toute "
                "l'économie, que l'étude n'identifie pas au niveau national et ne sépare "
                "pas du PFU. Moyenne des six premières années ; sociétés seules, hors "
                "entreprises individuelles et auto-entrepreneurs.",
        diagnostics={
            "knobs": applicable,
            "is_rate_change_points": round(is_rate_change_points, 4),
            "virtual_rate_fall_points": round(exposure, 4),
            "rests_on_symmetry": is_rate_change_points > 0,
            "not_added_to": "les emplois de l'éventail macro, de C2 et de C7",
        },
    )


# --------------------------------------------------------------------------- #
# C9 — R&D and the CIR: §6.4, opened on the IPP's credible range (D-222)
# --------------------------------------------------------------------------- #
C9_KEYS = ("rd_cir_multiplier",)

NO_CIR_KNOB = (
    "Aucun levier de cette réforme ne déplace un taux du CIR-recherche : la seule réponse "
    "de la R&D mesurée l'a été sur la réforme de 2008 du crédit."
)


def rd_response(
    store: Store,
    reform: Any,
    *,
    cir_margins: tuple[tuple[float, float], ...] | None = None,
    draws: int = 1,
    rng: Any = None,
    **_: Any,
) -> ChannelResult:
    """The extra private R&D a CIR rate change would bring, and the créance it earns.

    AN INDEX OF R&D, NEVER REVENUE — and the induced créance is reported beside it, never
    in the revenue band: a créance is the CIR's own unit, kept out of `reform_cost` for
    the same reason the mechanical créance is (D-222).

    `cir_margins` is ((Δc, τ), ...) per group of declarants: the créance change at fixed
    R&D, and the rate the group's next euro of research is credited at. The multiplier m
    is per euro of OBSERVED CIR, induced créance included, so the group's extra R&D solves
    R = m (Δc + τ R): R = m Δc / (1 − m τ), with τ R of induced créance.

    Worked example, pinned in the tests: 25 % instead of 30 % for the declarants below the
    threshold is Δc = −1 009,9 M€ at τ = 0,25; at m = 1,1, R = 1,1 × −1 009,9 / (1 −
    0,275) = −1 532,3 M€ of R&D, and −383,1 M€ of induced créance.
    """
    applicable = _claimed(store, reform, C9_KEYS)
    if not applicable:
        return ChannelResult(key="c9_rd", label="R&D et CIR", applies=False,
                             unit="EUR de R&D", message=NO_CIR_KNOB)
    if C9_KEYS[0] not in store:
        return ChannelResult(
            key="c9_rd", label="R&D et CIR", applies=False, unit="EUR de R&D",
            message=f"Aucune réponse utilisable : {C9_KEYS[0]} n'a pas survécu à la "
                    f"vérification des sources.",
            diagnostics={"missing_parameters": list(C9_KEYS)})
    if cir_margins is None:
        return _unsupplied("c9_rd", "R&D et CIR", "EUR de R&D",
                           "la variation de créance du CIR par groupe de déclarants")
    multiplier = store[C9_KEYS[0]].draw(rng, draws)
    worst = max(tau for _, tau in cir_margins) * float(np.max(multiplier))
    if worst >= 1.0:
        return ChannelResult(
            key="c9_rd", label="R&D et CIR", applies=False, unit="EUR de R&D",
            message=f"Taux marginal trop haut pour la formule : m × τ atteint {worst:.2f}. "
                    f"À partir de 1, chaque euro de R&D induite s'autofinancerait par sa "
                    f"propre créance et la réponse serait infinie — refusé, pas tronqué.",
            diagnostics={"m_times_tau": round(worst, 4)})
    rd = np.zeros(draws)
    induced = np.zeros(draws)
    for delta, tau in cir_margins:
        extra = multiplier * delta / (1.0 - multiplier * tau)
        rd = rd + extra
        induced = induced + tau * extra
    return ChannelResult(
        key="c9_rd", label="R&D et CIR", applies=True, draws=rd, unit="EUR de R&D",
        message="Indice illustratif : la R&D des entreprises qui recouraient déjà au CIR, "
                "par euro de créance, sur la seule réforme de 2008 ; taux de recours tenu "
                "fixe. La créance induite est une créance, comptée à part du coût.",
        diagnostics={
            "knobs": applicable,
            "static_creance_change_eur": round(sum(d for d, _ in cir_margins), 2),
            "induced_creance_eur": {
                "p10": round(float(np.percentile(induced, 10)), 2),
                "p50": round(float(np.percentile(induced, 50)), 2),
                "p90": round(float(np.percentile(induced, 90)), 2)},
            "not_counted": "la déduction d'IS sur la R&D induite ; les nouveaux entrants",
        },
    )


CHANNELS = (
    ("c1_eti", C1_KEYS),
    ("c2_employment", C2_KEYS),
    ("c3_incidence", C3_KEYS),
    ("c4_investment", C4_KEYS),
    ("c5_wealth_rate", C5_KEYS),
    ("c6_disclosure", C6_KEYS),
    ("c7_labour_supply", C7_KEYS),
    ("c8_creations", C8_KEYS),
    ("c9_rd", C9_KEYS),
)
