"""Reform mechanics (spec §3.1, §3.4, §6).

Three things must hold and are easy to get wrong:
  * a reform never mutates the baseline parameter tree;
  * identical reforms hit the cache, different ones do not;
  * a barème with fewer than five brackets collapses onto the top one correctly.
The last is checked against arithmetic done by hand, not against the engine's own
answer, because "the engine agrees with itself" would pass even if the wrapper
wrote the brackets in the wrong order.
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.api.schemas import HouseholdInput, ReformSpec
from impots.engine import baseline, compute
from impots.engine.reforms import PATH_BAREME, active_bracket_count, read_ir_parameters, resolve
from impots.engine.system import clear_cache, reform_key, reformed, reformed_for

TOP_RATE_50 = ReformSpec.model_validate(
    {
        "ir_bareme": [
            {"threshold": 0, "rate": 0.00},
            {"threshold": 11497, "rate": 0.11},
            {"threshold": 29315, "rate": 0.30},
            {"threshold": 83823, "rate": 0.41},
            {"threshold": 180294, "rate": 0.50},
        ]
    }
)

RICH_SINGLE = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 240000, "annee_naissance": 1980}]}
)
# 26 k€ gross: owes ~340 € of income tax, squarely inside the décote's range, so
# both décote knobs move it. At 18 k€ the décote has already zeroed the tax and no
# reform to it can show up.
MODEST_SINGLE = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 26000, "annee_naissance": 1990}]}
)
MODEST_COUPLE = HouseholdInput.model_validate(
    {
        "adults": [
            {"salaire_brut_annuel": 28000, "annee_naissance": 1985},
            {"salaire_brut_annuel": 26000, "annee_naissance": 1987},
        ],
        "couple_marie_ou_pacse": True,
    }
)
RICH_FAMILY = HouseholdInput.model_validate(
    {
        "adults": [
            {"salaire_brut_annuel": 100000, "annee_naissance": 1980},
            {"salaire_brut_annuel": 50000, "annee_naissance": 1982},
        ],
        "children": [{"annee_naissance": 2012}, {"annee_naissance": 2015}],
        "couple_marie_ou_pacse": True,
    }
)


def _scale(tax_benefit_system: object, year: int = 2024) -> object:
    return resolve(tax_benefit_system.parameters, PATH_BAREME)(f"{year}-01-01")


def test_no_mutation() -> None:
    """Applying a reform must never change what current law computes.

    `Reform(tbs)` clones the parameter tree, so this holds — but it holds by
    virtue of a library implementation detail, which is exactly the kind of thing
    that deserves a standing test rather than a comment.
    """
    before = compute(RICH_SINGLE, 2024, tier="light").baseline
    reformed_result = compute(RICH_SINGLE, 2024, reform=TOP_RATE_50, tier="light")
    after = compute(RICH_SINGLE, 2024, tier="light").baseline

    assert reformed_result.reform["ir"] != before["ir"], "the reform did not bite at all"
    assert after == before, "the baseline moved after a reform was applied"
    assert _scale(baseline()).rates[-1] == 0.45, "the baseline parameter tree was mutated"


def test_reform_cache() -> None:
    """Identical specs share one reformed system; a different spec builds another."""
    clear_cache()
    first = reformed_for(TOP_RATE_50, 2024)
    second = reformed_for(TOP_RATE_50.model_copy(deep=True), 2024)
    assert first is second, "an identical ReformSpec missed the cache"

    other = reformed_for(ReformSpec(decote_taux=0.30), 2024)
    assert other is not first

    # The year is part of the key: the same knobs at a different start date are a
    # different reformed system.
    assert reformed_for(TOP_RATE_50, 2025) is not first

    info = reformed.cache_info()
    assert info.hits >= 1 and info.misses >= 3


def test_reform_cache_hit_is_reported() -> None:
    clear_cache()
    first = compute(RICH_SINGLE, 2024, reform=TOP_RATE_50, tier="light")
    second = compute(RICH_SINGLE, 2024, reform=TOP_RATE_50, tier="light")
    assert first.timings["reform_cache_hit"] is False
    assert second.timings["reform_cache_hit"] is True


def test_reform_key_is_canonical() -> None:
    """Field order must not create two cache entries for one reform."""
    a = ReformSpec.model_validate({"decote_taux": 0.3, "csg_activite_imposable": 0.05})
    b = ReformSpec.model_validate({"csg_activite_imposable": 0.05, "decote_taux": 0.3})
    assert reform_key(a, 2024) == reform_key(b, 2024)


def test_empty_reform_is_treated_as_no_reform() -> None:
    """An all-null ReformSpec must not cost 0.5 s cloning the parameter tree."""
    result = compute(RICH_SINGLE, 2024, reform=ReformSpec(), tier="light")
    assert result.reform is None
    assert result.delta is None
    assert result.timings["reform_cache_hit"] is None


THREE_BRACKETS = ReformSpec.model_validate(
    {
        "ir_bareme": [
            {"threshold": 0, "rate": 0.00},
            {"threshold": 15000, "rate": 0.20},
            {"threshold": 60000, "rate": 0.40},
        ]
    }
)


@pytest.mark.parametrize(
    "brackets",
    [
        [(0, 0.00), (30000, 0.30)],
        [(0, 0.00), (15000, 0.20), (60000, 0.40)],
        [(0, 0.00), (12000, 0.10), (40000, 0.30), (150000, 0.45)],
        [(0, 0.00), (11497, 0.11), (29315, 0.30), (83823, 0.41), (180294, 0.50)],
    ],
    ids=["2-bracket", "3-bracket", "4-bracket", "5-bracket"],
)
def test_user_bareme_is_applied_exactly(brackets: list[tuple[float, float]]) -> None:
    """Whatever the user asks for, the evaluated scale must be exactly that.

    Fewer than five brackets means surplus active brackets have to be neutralised,
    and the obvious way to do it is wrong — see `test_surplus_brackets_do_not_sum`.
    """
    spec = ReformSpec.model_validate(
        {"ir_bareme": [{"threshold": t, "rate": r} for t, r in brackets]}
    )
    scale = _scale(reformed_for(spec, 2024))
    assert [float(t) for t in scale.thresholds] == [float(t) for t, _ in brackets]
    assert [round(float(r), 10) for r in scale.rates] == [r for _, r in brackets]


def test_surplus_brackets_do_not_sum() -> None:
    """Regression: the ParameterScale -> MarginalRateTaxScale conversion merges
    brackets that share a threshold by *summing* their rates.

    Giving each surplus bracket the top threshold and the top rate — the obvious
    reading of "make them no-ops" — turned three 40 % brackets into one 120 %
    bracket, and taxed a 240 k€ household 158 160 € instead of 58 720 €, silently.
    The top marginal rate here must be 0.40, never 1.20.
    """
    scale = _scale(reformed_for(THREE_BRACKETS, 2024))
    assert len(scale.rates) == 3
    assert scale.rates[-1] == pytest.approx(0.40)


def test_bareme_collapse_is_arithmetically_correct() -> None:
    """A three-bracket barème taxes like a three-bracket barème.

    Checked against tax computed by hand from the scale, not against the engine's
    own answer — "the engine agrees with itself" would have passed while the top
    rate was 120 %.
    """
    result = compute(RICH_SINGLE, 2024, reform=THREE_BRACKETS, tier="light")
    rni = result.baseline["revenu_fiscal_reference"]  # nbptr = 1, no décote at this income

    # By hand: nothing on the first 15 000, 20 % on the next 45 000, 40 % above.
    expected = 0.20 * (60000 - 15000) + 0.40 * (rni - 60000)
    assert abs(result.reform["ir_avant_reductions"] - expected) <= 2.0

    # The same barème with the padding written out explicitly must agree.
    padded = ReformSpec.model_validate(
        {
            "ir_bareme": [
                {"threshold": 0, "rate": 0.00},
                {"threshold": 15000, "rate": 0.20},
                {"threshold": 60000, "rate": 0.40},
                {"threshold": 60001, "rate": 0.40},
                {"threshold": 60002, "rate": 0.40},
            ]
        }
    )
    assert abs(
        compute(RICH_SINGLE, 2024, reform=padded, tier="light").reform["ir"]
        - result.reform["ir"]
    ) <= 2.0


def test_verify_bareme_rejects_a_mismatched_scale() -> None:
    """The read-back guard must actually fire when the scale is wrong."""
    from impots.engine.reforms import verify_bareme

    with pytest.raises(AssertionError, match="ne correspond pas"):
        verify_bareme(baseline(), THREE_BRACKETS, 2024)


def test_top_rate_delta_is_checkable_by_hand() -> None:
    """+5 points above 180 294 € on a base of ~184 300 € is ~200 €."""
    result = compute(RICH_SINGLE, 2024, reform=TOP_RATE_50, tier="light")
    above_threshold = result.baseline["revenu_fiscal_reference"] - 180294
    assert abs(result.delta["ir_avant_reductions"] - 0.05 * above_threshold) <= 1.0
    assert abs(result.delta["ir"] - 200.0) <= 2.0


def test_active_bracket_count_is_five_in_2024() -> None:
    """The scale holds 14 historical brackets; five carry a value at a 2024 instant."""
    from openfisca_core import periods

    node = resolve(baseline().parameters, PATH_BAREME)
    assert len(node.brackets) == 14
    assert active_bracket_count(node, periods.instant("2024-01-01")) == 5


def test_bareme_scale_calc_matches_engine() -> None:
    """The evaluated scale, applied to `rni`, reproduces `ir_plaf_qf` for a single
    with no quotient-familial advantage — the anchor the collapse test relies on."""
    scale = _scale(baseline())
    result = compute(RICH_SINGLE, 2024, tier="light")
    rni = result.baseline["revenu_fiscal_reference"]
    by_hand = float(scale.calc(np.array([rni]))[0])
    assert abs(by_hand - result.baseline["ir_avant_reductions"]) <= 0.5


@pytest.mark.parametrize(
    ("knob", "value", "household", "row", "should_fall"),
    [
        # A more generous décote wipes out more of a modest household's tax. The
        # household has to owe some tax for this to be visible at all: below about
        # 24 k€ gross a single already pays nothing and the knob moves nothing.
        ("decote_seuil_celib", 2000.0, MODEST_SINGLE, "ir", True),
        ("decote_seuil_couple", 3000.0, MODEST_COUPLE, "ir", True),
        # `taux` is subtracted: décote = seuil - taux x IR. Raising it shrinks the
        # décote and so *raises* the tax — the opposite of the other two knobs.
        ("decote_taux", 0.90, MODEST_SINGLE, "ir", False),
        # A higher cap on the half-part advantage lets a well-off family keep more of it.
        ("plafond_qf_demi_part", 4000.0, RICH_FAMILY, "ir", True),
        # More CSG withheld means a smaller net salary.
        ("csg_activite_imposable", 0.10, MODEST_SINGLE, "salaire_net", True),
        ("csg_activite_deductible", 0.15, MODEST_SINGLE, "salaire_net", True),
    ],
)
def test_every_scalar_knob_bites(
    knob: str, value: float, household: HouseholdInput, row: str, should_fall: bool
) -> None:
    """Each whitelisted knob must measurably move a result in the expected direction.

    A knob whose parameter path silently stopped resolving would otherwise look
    exactly like a reform the user asked for and got.
    """
    spec = ReformSpec.model_validate({knob: value})
    result = compute(household, 2024, reform=spec, tier="light")
    delta = result.delta[row]
    assert delta != 0, f"{knob} moved nothing — has its parameter path drifted?"
    direction = "a fall" if should_fall else "a rise"
    assert (delta < 0) == should_fall, (
        f"{knob} moved {row} by {delta:+.2f}, expected {direction}"
    )


def test_read_ir_parameters_matches_current_law() -> None:
    """The UI prefills from this; it must read the tree, not a hardcoded copy."""
    params = read_ir_parameters(baseline(), 2024)
    assert [b["threshold"] for b in params["bareme"]] == [0, 11497, 29315, 83823, 180294]
    assert [b["rate"] for b in params["bareme"]] == [0, 0.11, 0.30, 0.41, 0.45]
    assert params["decote"] == {"seuil_celib": 889.0, "seuil_couple": 1470.0, "taux": 0.4525}
    assert params["plafond_qf_demi_part"] == 1791.0
    assert params["csg_activite"]["imposable"] == pytest.approx(0.024)
    assert params["csg_activite"]["deductible"] == pytest.approx(0.068)


def test_bareme_over_five_brackets_is_rejected() -> None:
    with pytest.raises(ValueError, match="5 tranches"):
        ReformSpec.model_validate(
            {"ir_bareme": [{"threshold": i * 10000, "rate": 0.1 * i} for i in range(6)]}
        )


# --------------------------------------------------------------------------- #
# Employer social contributions (D-038)
#
# The knobs C2 and C3 were written against in Phase 3 and that the ReformSpec did
# not have. Every case here is hand-derivable: the two bandeaux are flat rates above
# a cliff, so their effect on labour cost is a multiplication anyone can check.
# --------------------------------------------------------------------------- #
from impots.engine.reforms import (  # noqa: E402
    BANDEAU_PLAFOND_CHILDREN,
    PATH_BANDEAU_FAMILLE,
    PATH_BANDEAU_MALADIE,
    plafond_children,
    verify_allegements,
)

#: Well above every allègement cliff in 2024 — 60 000 EUR is about 2.83 SMIC — so the
#: réduction générale and both bandeaux are exhausted and the arithmetic is clean.
HIGH_SALARY = 60_000.0


def labour_cost(salary: float, reform: dict | None, year: int = 2024) -> tuple[float, float]:
    """(baseline, reformed) annual labour cost for one single-adult household."""
    household = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": salary, "annee_naissance": 1990}]}
    )
    spec = None if reform is None else ReformSpec.model_validate(reform)
    result = compute(household, year, reform=spec, tier="light")
    reformed = result.baseline if spec is None else result.reform
    return result.baseline["salaire_super_brut"], reformed["salaire_super_brut"]


def test_removing_the_famille_bandeau_costs_exactly_its_rate() -> None:
    """The bandeau famille is a flat 1.8 % of gross below its cliff. Above the cliff
    it is nothing; below it, removing it raises labour cost by 1.8 % of gross and by
    nothing else. 0.018 x 60 000 = 1 080 EUR, checkable on paper."""
    base, reformed = labour_cost(HIGH_SALARY, {"bandeau_famille_taux": 0.0})
    assert reformed - base == pytest.approx(0.018 * HIGH_SALARY, abs=1.0)


def test_extending_the_maladie_bandeau_saves_exactly_its_rate() -> None:
    """The maladie bandeau is a flat 6 % below a cliff that sits at about 2.5 SMIC in
    2024. A worker at 2.83 SMIC is above it and gets nothing; moving the cliff to
    3 SMIC brings them inside, worth 0.06 x 60 000 = 3 600 EUR."""
    base, reformed = labour_cost(HIGH_SALARY, {"bandeau_maladie_plafond": 3.0})
    assert base - reformed == pytest.approx(0.06 * HIGH_SALARY, abs=1.0)


def test_the_reduction_generale_reaches_only_below_its_plafond() -> None:
    """Its whole design. A worker at 2.83 SMIC is far above the 1.6 SMIC ceiling, so
    neither its rate nor its ceiling can touch them — and a knob that moved labour
    cost there would mean the allègement was being applied where it does not exist."""
    for reform in ({"allegement_general_taux_moins_de_50": 0.40},
                   {"allegement_general_plafond": 2.0}):
        base, reformed = labour_cost(HIGH_SALARY, reform)
        assert reformed == pytest.approx(base, abs=1.0), reform


def test_raising_the_plafond_helps_where_raising_the_rate_barely_does() -> None:
    """The two knobs are not interchangeable, and a reform panel that treated them as
    one lever would mislead. Just above the ceiling (1.65 SMIC) the réduction is
    nearly exhausted, so extending the ceiling is worth several times more than
    raising the rate; well below it (1.2 SMIC) the ranking reverses."""
    just_above_base, just_above_plafond = labour_cost(30_000, {"allegement_general_plafond": 2.0})
    _, just_above_taux = labour_cost(30_000, {"allegement_general_taux_moins_de_50": 0.40})
    assert (just_above_base - just_above_plafond) > 3 * (just_above_base - just_above_taux)

    well_below_base, well_below_plafond = labour_cost(21_600, {"allegement_general_plafond": 2.0})
    _, well_below_taux = labour_cost(21_600, {"allegement_general_taux_moins_de_50": 0.40})
    assert (well_below_base - well_below_taux) > 10 * (well_below_base - well_below_plafond)


@pytest.mark.parametrize(
    ("year", "expected"),
    [
        (2023, ("plafond",)),
        (2024, ("plafond_smic_courant", "plafond_smic_2023_12_31")),
        (2025, ("plafond_smic_2025_01_01",)),
    ],
)
def test_the_plafond_knob_writes_where_that_year_reads(
    year: int, expected: tuple[str, ...]
) -> None:
    """The node's shape moves under the knob. In 2024 the formula takes a MAX over two
    children, so writing one alone leaves the other winning and the reform doing
    nothing at all — with no error anywhere. The knob writes every child the year
    actually reads, and none that it does not."""
    spec = ReformSpec.model_validate({"bandeau_maladie_plafond": 3.0})
    node = resolve(reformed_for(spec, year).parameters, PATH_BANDEAU_MALADIE)(f"{year}-01-01")
    assert set(plafond_children(node)) == set(expected)
    for name in expected:
        assert float(getattr(node, name)) == pytest.approx(3.0)


def test_the_plafond_knob_does_not_write_into_another_year() -> None:
    """`update()` CREATES a child that did not exist, so asking the editable tree
    which plafonds exist returns every one ever defined — including next year's. A
    2024 reform must not silently move the 2025 ceiling."""
    spec = ReformSpec.model_validate({"bandeau_famille_plafond": 4.0})
    node = resolve(reformed_for(spec, 2024).parameters, PATH_BANDEAU_FAMILLE)("2024-01-01")
    written = set(plafond_children(node))
    assert "plafond_smic_2025_01_01" not in written
    assert written <= set(BANDEAU_PLAFOND_CHILDREN)


def test_the_read_back_refuses_a_reform_that_did_not_take() -> None:
    """D-007, on the knob whose node changes shape. The read-back compares the tree
    against what was asked; a spec claiming a value the system does not carry must be
    refused rather than served."""
    applied = ReformSpec.model_validate({"bandeau_maladie_plafond": 3.0})
    system = reformed_for(applied, 2024)
    verify_allegements(system, applied, 2024)  # the honest case passes

    claimed = ReformSpec.model_validate({"bandeau_maladie_plafond": 9.0})
    with pytest.raises(AssertionError, match=r"plafond effectif est un max|demandé 9\.0"):
        verify_allegements(system, claimed, 2024)
