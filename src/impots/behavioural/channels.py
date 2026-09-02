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
    """A channel was asked for a response it has no inputs to compute."""


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
    for name, array in (("emtr_baseline", emtr_baseline), ("emtr_reform", emtr_reform),
                        ("taxable_base", taxable_base), ("weights", weights)):
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
C2_KEYS = ("employment_elasticity_smic",)
C3_KEYS = ("passthrough_benefit_linked", "passthrough_unlinked")

#: Why C2 and C3 report nothing in v1, stated once and reused.
#:
#: Both price employer social contributions, and **no reform knob moves one**. The
#: household ReformSpec exposes the barème, the décote, the plafond du quotient
#: familial and the two CSG rates; CSG is an employee contribution, and the spec
#: itself names `csg_activite_*` as the example of a knob no channel claims. So these
#: channels are complete and tested but have nothing to attach to until an
#: employer-contribution knob exists — which is an engine change, not a behavioural
#: one, and is deliberately not smuggled in here.
NO_EMPLOYER_KNOB = (
    "Mécanique seulement : aucun paramètre de cotisation patronale n'est exposé par "
    "le simulateur, donc rien ne déclenche ce canal. Le canal est écrit et testé ; "
    "il attend un levier."
)


def employment_at_the_smic(
    store: Store, reform: Any, **_: Any
) -> ChannelResult:
    """Jobs gained or lost when labour cost moves at and around the minimum wage."""
    applicable = _claimed(store, reform, C2_KEYS)
    return ChannelResult(
        key="c2_employment", label="Emploi au voisinage du SMIC",
        applies=False, unit="emplois",
        message=NO_EMPLOYER_KNOB if not applicable else
                "Élasticité disponible mais aucun coût du travail n'a bougé.",
        diagnostics={"knobs": applicable},
    )


def contribution_incidence(store: Store, reform: Any, **_: Any) -> ChannelResult:
    """Who bears an employer contribution — reallocates, never changes the total."""
    applicable = _claimed(store, reform, C3_KEYS)
    return ChannelResult(
        key="c3_incidence", label="Incidence des cotisations patronales",
        applies=False, unit="EUR",
        message=NO_EMPLOYER_KNOB if not applicable else
                "Élasticité disponible mais aucune cotisation patronale n'a bougé.",
        diagnostics={"knobs": applicable},
    )


# --------------------------------------------------------------------------- #
# C4 — production taxes and investment: the zero band
# --------------------------------------------------------------------------- #
C4_KEYS = ("production_tax_investment",)


def production_tax_investment(
    store: Store, reform: Any, *, mechanical_delta: float, draws: int,
    rng: np.random.Generator, **_: Any,
) -> ChannelResult:
    """Investment response to a production-tax cut — a band centred on zero.

    The best French evidence (IPP's evaluation of the 2021 CVAE/CFE halving) is a
    null. Encoding it as a band centred on zero *with the study's uncertainty* says
    something the absence of a line cannot: not "we did not look", but "it was looked
    for, carefully, and not found — and here is how precisely zero is estimated". A
    null that cannot rule out large effects is a different object from a tight zero,
    and the width of this band is what tells them apart.
    """
    applicable = _claimed(store, reform, C4_KEYS)
    if not applicable:
        return ChannelResult(
            key="c4_investment", label="Investissement et impôts de production",
            applies=False,
            message="Mécanique seulement — aucun canal fondé sur des preuves n'est "
                    "câblé pour cet instrument.",
        )
    if "production_tax_investment" not in store:
        return ChannelResult(
            key="c4_investment", label="Investissement et impôts de production",
            applies=False,
            message="Aucune élasticité utilisable : la ligne n'a pas survécu à la "
                    "vérification des sources.",
        )
    parameter = store["production_tax_investment"]
    response = parameter.draw(rng, draws) * mechanical_delta
    return ChannelResult(
        key="c4_investment", label="Investissement et impôts de production",
        applies=True, draws=response,
        message="Aucune réponse d'investissement détectable ; la bande porte "
                "l'incertitude de l'étude, pas une absence de mesure.",
        diagnostics={"knobs": applicable, "centred_on_zero": parameter.central == 0.0},
    )


CHANNELS = (
    ("c1_eti", C1_KEYS),
    ("c2_employment", C2_KEYS),
    ("c3_incidence", C3_KEYS),
    ("c4_investment", C4_KEYS),
)
