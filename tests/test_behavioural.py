"""The behavioural layer (PHASE3_SPEC §8).

The characteristic failure of this phase is that **a band computed from a bad
parameter looks exactly like a band computed from a good one**. Most of what is
tested here is therefore not arithmetic but refusal: that an unverified elasticity
cannot load, that an unclaimed instrument produces a sentence rather than a zero,
and that a reform beyond the evidence cannot come back graded confident.

Worked examples are derived by hand in the docstrings and checked against the code.
An implementation agreeing with itself proves nothing.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from impots.behavioural import band as band_module
from impots.behavioural import channels, grading
from impots.behavioural.store import Parameter, Source, Store, Support, UnverifiedParameter
from impots.behavioural.store import load as load_store

YAML_TEMPLATE = """
thresholds:
  extrapolation_widening: 2.0
parameters:
  {key}:
    value: {{central: {central}, low: {low}, high: {high}, distribution: triangular}}
    applies_to: a test parameter
    responds_to_knobs: [ir_bareme, decote_*]
    support:
      estimated_on: nothing at all
      max_variation_graded_in_support: {support}
    source: {{citation: nobody, url: "http://example.invalid"}}
    verifier: {{verdict: {verdict}, date: 2026-09-02, ref: test}}
    confidence: low
"""


def write_store(tmp_path: Path, *, key: str = "eti_all", central: float = 0.3,
                low: float = 0.1, high: float = 0.5, support: str = "0.05",
                verdict: str = "CONFIRMED") -> Path:
    (tmp_path / f"{key}.yaml").write_text(
        YAML_TEMPLATE.format(key=key, central=central, low=low, high=high,
                             support=support, verdict=verdict),
        encoding="utf-8",
    )
    return tmp_path


def parameter(key: str, central: float, low: float, high: float,
              support: float | None = 0.05, knobs: tuple[str, ...] = ("ir_bareme",),
              verdict: str = "CONFIRMED") -> Parameter:
    from impots.behavioural.store import Verifier

    return Parameter(
        key=key, central=central, low=low, high=high, applies_to="test",
        support=Support(estimated_on="test", max_variation_graded_in_support=support),
        source=Source(citation="test"), verifier=Verifier(verdict=verdict),
        responds_to_knobs=knobs,
    )


class FakeReform:
    """Stands in for a ReformSpec: the channels only ask what knobs it sets."""

    def __init__(self, **knobs: object) -> None:
        self._knobs = knobs

    def model_dump(self, exclude_none: bool = True) -> dict[str, object]:
        return dict(self._knobs)

    def is_empty(self) -> bool:
        return not self._knobs


# --------------------------------------------------------------------------- #
# the store refuses what it cannot vouch for
# --------------------------------------------------------------------------- #
def test_a_parameter_without_a_verdict_cannot_load(tmp_path: Path) -> None:
    """The one hard rule. An unverified elasticity produces a band indistinguishable
    from a verified one, which is this phase's characteristic failure."""
    write_store(tmp_path, verdict="null")
    with pytest.raises(UnverifiedParameter, match="no verifier verdict"):
        load_store(tmp_path)


def test_a_parameter_the_verifier_refuted_cannot_load(tmp_path: Path) -> None:
    write_store(tmp_path, verdict="WRONG")
    with pytest.raises(UnverifiedParameter, match="returned WRONG"):
        load_store(tmp_path)


def test_a_scope_problem_still_loads(tmp_path: Path) -> None:
    """Phase 2 measured what SCOPE_PROBLEM means: citations needing repair while the
    values hold. That is a documentation defect, not a wrong number, and refusing it
    would have thrown away every parameter this project has."""
    store = load_store(write_store(tmp_path, verdict="SCOPE_PROBLEM"))
    assert "eti_all" in store


def test_non_strict_loading_records_why_rather_than_raising(tmp_path: Path) -> None:
    """So a report can say which rows are missing and why, without a band ever being
    produced from a partial store."""
    store = load_store(write_store(tmp_path, verdict="null"), strict=False)
    assert "eti_all" not in store
    assert "no verifier verdict" in store.rejected["eti_all"]


def test_a_central_value_outside_its_range_is_refused() -> None:
    with pytest.raises(ValueError, match="outside"):
        parameter("bad", central=0.9, low=0.1, high=0.5)


def test_thresholds_live_in_the_store_not_in_code(tmp_path: Path) -> None:
    """§4: tightening the guardrail must be a data change with a diff."""
    store = load_store(write_store(tmp_path))
    assert store.thresholds["extrapolation_widening"] == 2.0


def test_knob_patterns_match_a_family_of_parameters() -> None:
    """`decote_seuil_celib` and `decote_taux` are one instrument to an elasticity."""
    p = parameter("eti_all", 0.3, 0.1, 0.5, knobs=("ir_bareme", "decote_*"))
    assert p.claims("ir_bareme")
    assert p.claims("decote_taux")
    assert not p.claims("csg_activite_imposable")


def test_drawing_never_returns_the_central_value_alone() -> None:
    """The point of the store is that the band, not the point, is the answer."""
    rng = np.random.default_rng(0)
    draws = parameter("eti_all", 0.3, 0.1, 0.5).draw(rng, 500)
    assert draws.min() >= 0.1 and draws.max() <= 0.5
    assert draws.std() > 0.01


# --------------------------------------------------------------------------- #
# C1, against a hand-derived worked example
# --------------------------------------------------------------------------- #
def test_c1_reproduces_the_worked_example() -> None:
    """Derived by hand, not read off the engine.

    A household with a taxable base of 100 000 EUR whose marginal rate goes from 41 %
    to 45 %. The net-of-tax rate falls 0.59 -> 0.55, so
        Δln(1-τ') = ln(0.55) - ln(0.59) = -0.0701950
    With e = 0.30 the base moves by 0.30 × 100 000 × (-0.0702043) = -2 106.13 EUR,
    and the revenue offset is 0.45 × (-2 106.13) = -947.76 EUR — 23.7 % of the
    4 000 EUR the rate rise mechanically yields on this household.
    """
    delta_log = math.log(0.55) - math.log(0.59)
    assert delta_log == pytest.approx(-0.0702043, abs=1e-7)
    expected = 0.30 * 100_000.0 * delta_log * 0.45
    # Pinned as a literal as well as derived: the derivation and the engine could
    # drift together, a hand-checked number cannot drift with them.
    assert expected == pytest.approx(-947.76, abs=0.01)
    assert abs(expected) / (0.04 * 100_000.0) == pytest.approx(0.237, abs=0.001)

    store = Store(parameters={
        # low == high, so the draw is deterministic and the test is about the formula.
        "eti_all": parameter("eti_all", 0.30, 0.30, 0.30),
        "eti_top_decile": parameter("eti_top_decile", 0.30, 0.30, 0.30),
    })
    result = channels.elasticity_of_taxable_income(
        store, FakeReform(ir_bareme=[{"threshold": 0, "rate": 0.45}]),
        emtr_baseline=np.array([0.41]), emtr_reform=np.array([0.45]),
        taxable_base=np.array([100_000.0]), weights=np.array([1.0]),
        top_decile=np.array([False]), draws=16, rng=np.random.default_rng(1),
    )
    assert result.applies
    assert result.central == pytest.approx(expected, rel=1e-9)


def test_c1_returns_revenue_when_a_rate_is_cut() -> None:
    """Sign discipline: cutting the marginal rate grows the base, which returns
    revenue against the mechanical cost rather than adding to it."""
    store = Store(parameters={
        "eti_all": parameter("eti_all", 0.30, 0.30, 0.30),
        "eti_top_decile": parameter("eti_top_decile", 0.30, 0.30, 0.30),
    })
    cut = channels.elasticity_of_taxable_income(
        store, FakeReform(ir_bareme=[]),
        emtr_baseline=np.array([0.45]), emtr_reform=np.array([0.41]),
        taxable_base=np.array([100_000.0]), weights=np.array([1.0]),
        top_decile=np.array([False]), draws=8, rng=np.random.default_rng(1),
    )
    assert cut.central is not None and cut.central > 0


def test_c1_uses_the_top_decile_elasticity_where_it_belongs() -> None:
    """The two groups are the whole reason C1 has two parameters."""
    store = Store(parameters={
        "eti_all": parameter("eti_all", 0.05, 0.05, 0.05),
        "eti_top_decile": parameter("eti_top_decile", 0.50, 0.50, 0.50),
    })
    common = dict(
        emtr_baseline=np.array([0.41]), emtr_reform=np.array([0.45]),
        taxable_base=np.array([100_000.0]), weights=np.array([1.0]),
        draws=8, rng=np.random.default_rng(1),
    )
    lower = channels.elasticity_of_taxable_income(
        store, FakeReform(ir_bareme=[]), top_decile=np.array([False]), **common)
    top = channels.elasticity_of_taxable_income(
        store, FakeReform(ir_bareme=[]), top_decile=np.array([True]), **common)
    assert abs(top.central) == pytest.approx(10 * abs(lower.central), rel=1e-9)


def test_c1_says_so_when_no_elasticity_survived_verification() -> None:
    """A row that dies leaves its channel reporting no usable evidence — never an
    international guess inherited quietly to keep a number on the screen."""
    store = Store(parameters={"eti_all": parameter("eti_all", 0.05, 0.05, 0.05)})
    result = channels.elasticity_of_taxable_income(
        store, FakeReform(ir_bareme=[]),
        emtr_baseline=np.array([0.41]), emtr_reform=np.array([0.45]),
        taxable_base=np.array([100.0]), weights=np.array([1.0]),
        top_decile=np.array([False]), draws=4, rng=np.random.default_rng(0),
    )
    assert not result.applies
    assert "vérification des sources" in result.message
    assert result.diagnostics["missing_parameters"] == ["eti_top_decile"]


def test_c1_fails_loudly_on_missing_inputs() -> None:
    """The Phase 1 lesson: pensions were computed and then silently dropped, every
    guard stayed green, and RSA came out at three times its published value."""
    store = Store(parameters={
        "eti_all": parameter("eti_all", 0.3, 0.3, 0.3),
        "eti_top_decile": parameter("eti_top_decile", 0.3, 0.3, 0.3),
    })
    with pytest.raises(channels.ChannelInputMissing, match="emtr_baseline"):
        channels.elasticity_of_taxable_income(
            store, FakeReform(ir_bareme=[]),
            emtr_baseline=np.array([]), emtr_reform=np.array([]),
            taxable_base=np.array([]), weights=np.array([]),
            top_decile=np.array([]), draws=4, rng=np.random.default_rng(0),
        )


def test_an_unclaimed_knob_yields_a_sentence_not_a_zero() -> None:
    """A silent zero is a false statement about behaviour; the sentence is a true
    statement about the evidence."""
    store = Store(parameters={
        "eti_all": parameter("eti_all", 0.3, 0.3, 0.3, knobs=("ir_bareme",)),
        "eti_top_decile": parameter("eti_top_decile", 0.3, 0.3, 0.3, knobs=("ir_bareme",)),
    })
    result = channels.elasticity_of_taxable_income(
        store, FakeReform(csg_activite_imposable=0.1),
        emtr_baseline=np.array([0.41]), emtr_reform=np.array([0.41]),
        taxable_base=np.array([100.0]), weights=np.array([1.0]),
        top_decile=np.array([False]), draws=4, rng=np.random.default_rng(0),
    )
    assert not result.applies
    assert result.draws is None
    assert "Mécanique seulement" in result.message


def test_c2_and_c3_report_that_they_have_no_lever() -> None:
    """Both price employer social contributions, and no reform knob moves one. The
    channels are written and tested; saying so beats shipping a dead zero."""
    for channel in (channels.employment_at_the_smic, channels.contribution_incidence):
        result = channel(Store(), FakeReform(ir_bareme=[]))
        assert not result.applies
        assert "cotisation patronale" in result.message


def test_c4_is_a_band_centred_on_zero() -> None:
    """A null that cannot rule out large effects is a different object from a tight
    zero, and the width of this band is what tells them apart."""
    store = Store(parameters={"production_tax_investment": parameter(
        "production_tax_investment", 0.0, -0.05, 0.05, knobs=("cvae_*",))})
    result = channels.production_tax_investment(
        store, FakeReform(cvae_taux_max=0.005), mechanical_delta=1.0e9,
        draws=2000, rng=np.random.default_rng(3),
    )
    assert result.applies
    assert result.central == pytest.approx(0.0, abs=2e7)
    assert result.draws is not None and result.draws.std() > 1e6


# --------------------------------------------------------------------------- #
# the Lucas guardrail
# --------------------------------------------------------------------------- #
def test_a_reform_inside_the_evidence_is_graded_in_support() -> None:
    store = Store(parameters={"eti_all": parameter("eti_all", 0.3, 0.1, 0.5, support=0.05)})
    assert grading.grade_channel(store, ("eti_all",), 0.03)[0] == "in-support"


def test_a_reform_beyond_the_evidence_is_graded_illustrative() -> None:
    store = Store(parameters={"eti_all": parameter("eti_all", 0.3, 0.1, 0.5, support=0.05)})
    assert grading.grade_channel(store, ("eti_all",), 0.20)[0] == "illustrative"


def test_the_boundary_itself_counts_as_in_support() -> None:
    store = Store(parameters={"eti_all": parameter("eti_all", 0.3, 0.1, 0.5, support=0.05)})
    assert grading.grade_channel(store, ("eti_all",), 0.05)[0] == "in-support"


def test_an_ungradeable_support_is_not_a_permissive_one() -> None:
    """If the literature cannot say how far an estimate carries, the channel resting
    on it can never claim to be in support. Silence is not permission."""
    store = Store(parameters={"eti_all": parameter("eti_all", 0.3, 0.1, 0.5, support=None)})
    assert grading.grade_channel(store, ("eti_all",), 0.0001)[0] == "illustrative"


def test_a_channel_with_no_parameters_grades_no_evidence() -> None:
    assert grading.grade_channel(Store(), ("eti_all",), 0.01)[0] == "no-evidence"


def test_the_overall_grade_is_the_weakest_channel_not_the_average() -> None:
    """Averaging would let a well-supported small channel launder a badly-supported
    large one."""
    store = Store(parameters={
        "eti_all": parameter("eti_all", 0.3, 0.1, 0.5, support=0.05),
        "production_tax_investment": parameter(
            "production_tax_investment", 0.0, -0.05, 0.05, support=0.5),
    })
    verdict = grading.grade(store, {
        "c1_eti": (("eti_all",), 0.50),
        "c4_investment": (("production_tax_investment",), 0.01),
    })
    assert verdict.grade == "illustrative"
    assert verdict.per_channel == {"c1_eti": "illustrative", "c4_investment": "in-support"}


def test_the_induced_variation_is_robust_to_a_single_household() -> None:
    """A guardrail that always fires is a guardrail nobody reads. One household at an
    extreme must not grade the whole country as an extrapolation."""
    baseline = np.zeros(1000)
    reform = np.full(1000, 0.01)
    reform[0] = 5.0
    weights = np.ones(1000)
    assert grading.induced_variation(baseline, reform, weights) == pytest.approx(0.01, abs=1e-6)


def test_widening_stretches_about_the_median_without_moving_it() -> None:
    draws = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    widened = grading.widen(draws, 2.0)
    assert np.median(widened) == pytest.approx(np.median(draws))
    assert widened.max() - widened.min() == pytest.approx(
        2.0 * (draws.max() - draws.min())
    )


# --------------------------------------------------------------------------- #
# the band
# --------------------------------------------------------------------------- #
def household_store() -> Store:
    return Store(
        parameters={
            "eti_all": parameter("eti_all", 0.05, 0.00, 0.15, support=0.05),
            "eti_top_decile": parameter("eti_top_decile", 0.30, 0.15, 0.50, support=0.05),
        },
        thresholds={"extrapolation_widening": 2.0},
    )


def household_inputs(n: int = 500) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(7)
    return {
        "emtr_baseline": np.full(n, 0.41),
        "emtr_reform": np.full(n, 0.43),
        "taxable_base": rng.uniform(20_000, 90_000, n),
        "weights": np.full(n, 1_000.0),
        "top_decile": np.arange(n) >= int(0.9 * n),
    }


def test_the_band_is_deterministic_to_the_last_digit() -> None:
    """One seed in one place. A band that moved between runs would be
    indistinguishable from a band that moved because the evidence changed."""
    kwargs = dict(mechanical=1.0e9, reform=FakeReform(ir_bareme=[]),
                  store=household_store(), **household_inputs())
    first = band_module.compute(**kwargs)
    second = band_module.compute(**kwargs)
    assert first.band is not None
    assert (first.band.p10, first.band.p50, first.band.p90) == (
        second.band.p10, second.band.p50, second.band.p90
    )


def test_the_band_converges_between_one_and_four_thousand_draws() -> None:
    """§8: p10 and p90 stable to under 1 %."""
    kwargs = dict(mechanical=1.0e9, reform=FakeReform(ir_bareme=[]),
                  store=household_store(), **household_inputs())
    small = band_module.compute(draws=1_000, **kwargs).band
    large = band_module.compute(draws=4_000, **kwargs).band
    assert small is not None and large is not None
    for a, b in ((small.p10, large.p10), (small.p90, large.p90)):
        assert abs(a - b) / abs(b) < 0.01


def test_widening_a_parameter_range_cannot_narrow_the_band() -> None:
    """Monotonicity. If more uncertainty about an input could produce more confidence
    in the output, the machinery would be lying somewhere."""
    tight = household_store()
    wide = Store(
        parameters={
            "eti_all": parameter("eti_all", 0.05, -0.10, 0.25, support=0.05),
            "eti_top_decile": parameter("eti_top_decile", 0.30, 0.05, 0.60, support=0.05),
        },
        thresholds=tight.thresholds,
    )
    inputs = household_inputs()
    narrow = band_module.compute(mechanical=1.0e9, reform=FakeReform(ir_bareme=[]),
                                 store=tight, draws=4_000, **inputs).band
    broad = band_module.compute(mechanical=1.0e9, reform=FakeReform(ir_bareme=[]),
                                store=wide, draws=4_000, **inputs).band
    assert narrow is not None and broad is not None
    assert (broad.p90 - broad.p10) > (narrow.p90 - narrow.p10)


def test_a_reform_beyond_the_evidence_comes_back_widened_and_labelled() -> None:
    inputs = household_inputs()
    inputs["emtr_reform"] = np.full(len(inputs["weights"]), 0.71)  # +30 points
    result = band_module.compute(mechanical=1.0e9, reform=FakeReform(ir_bareme=[]),
                                 store=household_store(), **inputs)
    assert result.grade == "illustrative"
    assert "extrapolation" in result.grade_reason


def test_the_mechanical_number_is_never_modified() -> None:
    """The layer boundary, asserted. The band is a range *around* the mechanical
    figure; a reader who takes only the first number is not misled."""
    mechanical = 1.234e9
    result = band_module.compute(mechanical=mechanical, reform=FakeReform(ir_bareme=[]),
                                 store=household_store(), **household_inputs())
    assert result.mechanical == mechanical
    assert result.band is not None
    assert result.band.p10 < mechanical or result.band.p90 > mechanical


def test_an_empty_store_yields_a_mechanical_only_answer() -> None:
    result = band_module.compute(mechanical=1.0e9, reform=FakeReform(ir_bareme=[]),
                                 store=Store(), **household_inputs())
    assert result.band is None
    assert result.grade == "no-evidence"
    assert result.notes
