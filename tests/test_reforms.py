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
        # A sixth wakes the first dormant bracket of the scale (D-320).
        [(0, 0.00), (11497, 0.11), (29315, 0.30), (83823, 0.41), (180294, 0.45),
         (250000, 0.60)],
    ],
    ids=["2-bracket", "3-bracket", "4-bracket", "5-bracket", "6-bracket"],
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


def test_bareme_over_six_brackets_is_rejected() -> None:
    """Six since D-320, by the owner's goal 11 (a sixth bracket in the programmes of
    2027); five before. One dormant bracket can be woken, not two."""
    with pytest.raises(ValueError, match="6 tranches"):
        ReformSpec.model_validate(
            {"ir_bareme": [{"threshold": i * 10000, "rate": 0.1 * i} for i in range(7)]}
        )


def test_a_sixth_bracket_taxes_above_it_and_nothing_below() -> None:
    """60 % above 250 000 EUR (D-320): the top earner pays more, the median one the same."""
    bareme = [{"threshold": 0, "rate": 0.0}, {"threshold": 11_600, "rate": 0.11},
              {"threshold": 29_579, "rate": 0.30}, {"threshold": 84_577, "rate": 0.41},
              {"threshold": 181_917, "rate": 0.45}, {"threshold": 250_000, "rate": 0.60}]
    spec = ReformSpec.model_validate({"ir_bareme": bareme})
    for salaire, hausse in ((600_000, True), (40_000, False)):
        h = HouseholdInput.model_validate(
            {"adults": [{"salaire_brut_annuel": salaire, "annee_naissance": 1975}]})
        result = compute(h, 2026, reform=spec, tier="light")
        moved = result.reform["ir"] - result.baseline["ir"]
        assert (moved > 1_000) if hausse else (moved == pytest.approx(0.0)), (salaire, moved)


def test_only_the_first_dormant_bracket_can_be_woken() -> None:
    from openfisca_core import periods
    from openfisca_france import FranceTaxBenefitSystem

    from impots.parameters import ParameterWriteError, reactivate_bracket

    tbs = FranceTaxBenefitSystem()
    node = resolve(tbs.parameters, PATH_BAREME)
    start = periods.instant("2026-01-01")
    with pytest.raises(ParameterWriteError, match="seule la première tranche dormante"):
        reactivate_bracket(node, 6, active=5, start=start, rate=0.6, threshold=300_000)
    with pytest.raises(ParameterWriteError, match="seule la première tranche dormante"):
        reactivate_bracket(node, 4, active=5, start=start, rate=0.6, threshold=300_000)


def test_the_retirement_contribution_factor_is_read_back() -> None:
    """A factor the tree does not carry is refused before anyone computes (D-320)."""
    from impots.engine.reforms import ECHELLE_KNOBS, verify_echelles

    spec = ReformSpec.model_validate({"cotisations_salariales_retraite_echelle": 0.5})
    system = reformed_for(spec, 2026)
    verify_echelles(system, baseline(), spec, 2026)
    path = ECHELLE_KNOBS["cotisations_salariales_retraite_echelle"][0]
    got = [float(r) for r in resolve(system.parameters, path)("2026-01-01").rates]
    base = [float(r) for r in resolve(baseline().parameters, path)("2026-01-01").rates]
    assert got == pytest.approx([0.5 * r for r in base]) and base[0] > 0
    with pytest.raises(AssertionError, match="cotisations_salariales_retraite_echelle"):
        verify_echelles(baseline(), baseline(), spec, 2026)


# --------------------------------------------------------------------------- #
# Employer social contributions (D-038)
#
# The knobs C2 and C3 were written against in Phase 3 and that the ReformSpec did
# not have. Every case here is hand-derivable: the two bandeaux are flat rates above
# a cliff, so their effect on labour cost is a multiplication anyone can check.
# --------------------------------------------------------------------------- #
from impots.engine.reforms import (  # noqa: E402
    BANDEAU_PLAFOND_CHILDREN,
    PATH_ALLEGEMENT_GENERAL,
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


def test_a_knob_is_refused_where_its_parameter_no_longer_exists() -> None:
    """The silent no-op, and the reason read-back alone is not enough.

    The 2026 refonte does not reparameterise the allègements — it REPLACES them. Both
    bandeaux vanish and the réduction générale becomes a power function
    (`puissance`, `t_min`, `t_delta_*`) reaching 3 SMIC. Writing the old child name
    there still *succeeds*, because `update()` creates a child that does not exist;
    the read-back then finds exactly the value it just wrote and passes; and labour
    cost moves by 0.00. The reform reports success and does nothing.

    So existence is checked BEFORE the write, against the node as the year's formula
    sees it — and the message names what replaced the parameter."""
    for knob, value in (("allegement_general_taux_moins_de_50", 0.45),
                        ("bandeau_famille_taux", 0.0),
                        ("bandeau_maladie_plafond", 2.5)):
        with pytest.raises(ValueError, match=r"n'existe pas|aucun plafond"):
            reformed_for(ReformSpec.model_validate({knob: value}), 2026)


def test_the_refusal_names_what_replaced_the_parameter() -> None:
    """A refusal that only says 'no' sends the reader hunting. This one says where
    the instrument went, and since D-240 which knob now moves it."""
    with pytest.raises(ValueError, match=r"t_delta_petites_entreprises.*"
                                         r"allegement_general_t_delta_moins_de_50"):
        reformed_for(
            ReformSpec.model_validate({"allegement_general_taux_moins_de_50": 0.45}), 2026
        )


#: The 2026 curve's knobs (D-240), and the tree's child each one writes.
CURVE_KNOBS = {"allegement_general_t_min": ("t_min", 0.03),
               "allegement_general_t_delta_moins_de_50": ("t_delta_petites_entreprises",
                                                           0.40),
               "allegement_general_t_delta_50_et_plus": ("t_delta_grandes_entreprises",
                                                          0.41)}


@pytest.mark.parametrize("knob", sorted(CURVE_KNOBS))
def test_the_2026_curve_knobs_write_the_curve(knob: str) -> None:
    """Each knob writes its child of the 2026 réduction générale, read back by the
    engine's own guard and here once more; the baseline tree is left alone."""
    child, value = CURVE_KNOBS[knob]
    system = reformed_for(ReformSpec.model_validate({knob: value}), 2026)
    node = resolve(system.parameters, PATH_ALLEGEMENT_GENERAL)("2026-01-01")
    assert float(getattr(node, child)) == pytest.approx(value)
    base = resolve(baseline().parameters, PATH_ALLEGEMENT_GENERAL)("2026-01-01")
    assert float(getattr(base, child)) != pytest.approx(value)


@pytest.mark.parametrize("knob", sorted(CURVE_KNOBS))
def test_the_curve_knobs_are_refused_before_the_refonte(knob: str) -> None:
    """Before 2026 the curve does not exist: writing it would create a child no
    formula reads (D-042). Refused, and the refusal names the rates that then govern."""
    _, value = CURVE_KNOBS[knob]
    with pytest.raises(ValueError, match=r"n'existe pas.*allegement_general_taux_"):
        reformed_for(ReformSpec.model_validate({knob: value}), 2025)


def test_a_curve_knob_the_system_did_not_take_is_caught_by_the_read_back() -> None:
    system = reformed_for(ReformSpec.model_validate({"allegement_general_t_min": 0.03}),
                          2026)
    verify_allegements(system, ReformSpec(allegement_general_t_min=0.03), 2026)
    with pytest.raises(AssertionError, match=r"allegement_general_t_min : demandé 0\.04"):
        verify_allegements(system, ReformSpec(allegement_general_t_min=0.04), 2026)


def test_the_curve_knobs_move_labour_cost_where_the_curve_says() -> None:
    """In 2026: the floor `t_min` lowers labour cost at every wage below the 3 SMIC
    ceiling, near the SMIC and at 2,5 SMIC alike; `t_delta` lowers it most at the SMIC,
    and almost nothing at 2,9 SMIC, where its term has all but faded; neither moves a
    wage above the ceiling."""
    from impots.api.main import _smic_annual

    smic = _smic_annual(2026)

    def saving(salary: float, reform: dict) -> float:
        before, after = labour_cost(salary, reform, year=2026)
        return before - after

    floor = {"allegement_general_t_min": 0.03}
    delta = {"allegement_general_t_delta_moins_de_50": 0.40}
    assert saving(1.05 * smic, floor) > 0 and saving(2.5 * smic, floor) > 0
    assert saving(1.05 * smic, delta) > 10 * saving(2.5 * smic, delta) >= 0
    assert 0 <= saving(2.9 * smic, delta) < 0.01 * saving(1.05 * smic, delta)
    for reform in (floor, delta):
        assert saving(3.5 * smic, reform) == pytest.approx(0.0, abs=0.5)


def test_knobs_that_survive_the_refonte_still_work() -> None:
    """The refusal must be surgical. The réduction générale's plafond outlives the
    2026 rewrite — the concept survives even though the rate parameters do not — so
    refusing it too would be over-correcting."""
    system = reformed_for(ReformSpec.model_validate({"allegement_general_plafond": 2.5}), 2026)
    node = resolve(
        system.parameters,
        ("prelevements_sociaux", "reductions_cotisations_sociales",
         "allegement_general", "ensemble_des_entreprises"),
    )("2026-01-01")
    assert float(node.plafond) == pytest.approx(2.5)


def test_the_2025_refonte_step_is_expressible() -> None:
    """The re-sweep's own precondition (D-036's standing rule). LFSS 2025 lowered the
    maladie ceiling from 2.5 to 2.25 SMIC and the famille one from 3.5 to 3.3, and
    both are knobs — so the article can be replayed against 2024 law, which is what a
    backtest case needs."""
    system = reformed_for(
        ReformSpec.model_validate(
            {"bandeau_maladie_plafond": 2.25, "bandeau_famille_plafond": 3.3}
        ),
        2024,
    )
    maladie = resolve(system.parameters, PATH_BANDEAU_MALADIE)("2024-01-01")
    famille = resolve(system.parameters, PATH_BANDEAU_FAMILLE)("2024-01-01")
    assert {float(getattr(maladie, n)) for n in plafond_children(maladie)} == {2.25}
    assert {float(getattr(famille, n)) for n in plafond_children(famille)} == {3.3}


# --------------------------------------------------------------------------- #
# PLF 2027, art. 3 — le plafond de l'abattement de 10 % sur les pensions
# --------------------------------------------------------------------------- #
#: Un retraité seul dont l'abattement de 10 % dépasse le plafond légal : c'est sur ce
#: foyer, et sur lui seul, qu'un plafond abaissé mord.
RETRAITE_AISE = {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1955,
                             "pension_annuelle": 50_000}]}


def test_a_pension_is_taxed_as_declared() -> None:
    """Le format d'entrée n'avait pas de pension : tout retraité était un foyer sans
    revenu, et un levier qui ne mord que sur les pensions ne pouvait être vu bouger sur
    aucun ménage exprimable (D-081).

    ET LA PENSION SAISIE EST IMPOSÉE TELLE QUELLE, ce qui n'allait pas de soi.
    `retraite_imposable` vaut `retraite_brute + csg_deductible_retraite`, mais le taux de
    cette CSG lit le RFR de N-2, et la spirale d'openfisca sur cette dépendance la
    laissait à zéro ou à −5,9 % selon ce qui était calculé en premier. D-175 avait
    épinglé cet effet d'ORDRE ; D-176 l'a mesuré puis supprimé : le montant DÉCLARÉ, comme
    la pension de la population, calée sur les pensions déclarées à la DGFiP, est écrit
    sur `retraite_imposable` (case 1AS) autant que sur `retraite_brute`. Ce test tient
    donc désormais par construction, dans tout ordre ; les gardes de l'ordre sont dans
    `test_engine.py` et `test_population.py`."""
    rows = compute(HouseholdInput.model_validate(RETRAITE_AISE), 2024, tier="light").baseline
    assert rows["retraite_imposable"] == pytest.approx(50_000, abs=0.5)
    assert rows["ir"] > 0


def test_lowering_the_pension_cap_taxes_the_difference_at_the_marginal_rate() -> None:
    """L'arithmétique de l'article, sur un foyer où elle se lit à la main.

    En 2024, le plafond vaut 4 399 EUR et 10 % de la pension imposable du foyer
    dépassent 4 700 EUR : l'abattement est plafonné. Le ramener à 3 000 EUR ajoute
    1 399 EUR au revenu imposable, qui est dans la tranche à 30 % — soit environ 420 EUR
    d'impôt, à l'arrondi près."""
    foyer = HouseholdInput.model_validate(RETRAITE_AISE)
    avant = compute(foyer, 2024, tier="light").baseline["ir"]
    apres = compute(foyer, 2024, tier="light",
                    reform=ReformSpec(abattement_pensions_plafond=3_000.0)).reform["ir"]
    assert apres - avant == pytest.approx(1_399 * 0.30, abs=2.0)


def test_the_pension_cap_spares_a_pensioner_below_it() -> None:
    """Le jumeau : à 20 000 EUR de pension, 10 % font moins de 3 000 EUR, et le
    plafond abaissé ne change rien. Un levier qui bougerait ici écrirait au mauvais
    endroit."""
    foyer = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1955,
                     "pension_annuelle": 20_000}]})
    avant = compute(foyer, 2024, tier="light").baseline["ir"]
    apres = compute(foyer, 2024, tier="light",
                    reform=ReformSpec(abattement_pensions_plafond=3_000.0)).reform["ir"]
    assert apres == pytest.approx(avant)


def test_a_factor_on_a_scale_with_no_active_bracket_is_refused() -> None:
    """The AGFF was folded into Agirc-Arrco in 2019: a factor on it would land nowhere."""
    from openfisca_core import periods
    from openfisca_france import FranceTaxBenefitSystem

    from impots.engine.reforms import _apply_echelle

    tbs = FranceTaxBenefitSystem()
    path = ("prelevements_sociaux", "regimes_complementaires_retraite_secteur_prive", "agff",
            "salarie", "noncadre", "agff")
    with pytest.raises(ValueError, match="aucune tranche active"):
        _apply_echelle(tbs.parameters.clone(), (path,), 0.5, periods.instant("2026-01-01"),
                       "2026-01-01")


def test_the_engine_wakes_one_dormant_bracket_not_two() -> None:
    """Behind the schema's limit, the engine's own: seven brackets on a five-bracket year."""
    from openfisca_core import periods
    from openfisca_france import FranceTaxBenefitSystem

    from impots.api.schemas import IRBracket
    from impots.engine.reforms import _apply_bareme

    brackets = [IRBracket(threshold=i * 50_000.0, rate=0.05 * i) for i in range(7)]
    with pytest.raises(ValueError, match="une seule tranche dormante"):
        _apply_bareme(FranceTaxBenefitSystem().parameters.clone(), brackets,
                      periods.instant("2026-01-01"))
