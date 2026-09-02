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
    jobs = smic_draws * anchor + tail

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


CHANNELS = (
    ("c1_eti", C1_KEYS),
    ("c2_employment", C2_KEYS),
    ("c3_incidence", C3_KEYS),
    ("c4_investment", C4_KEYS),
)
