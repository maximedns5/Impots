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

from impots import service
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
{theta}    applies_to: a test parameter
    responds_to_knobs: [ir_bareme, decote_*]
    support:
      estimated_on: nothing at all
      max_variation_graded_in_support: {support}
    source: {{citation: nobody, url: "http://example.invalid"}}
    verifier: {{verdict: {verdict}, date: 2026-09-02, ref: test}}
    confidence: low
"""


#: Every open row declares which end θ = 1 designates (D-217); the fixture does too, as
#: a real row must. `theta=""` writes a row without it, for the guard's own tests.
THETA_HIGH = "    theta: {un: high, raison: une élasticité plus grande est plus forte}\n"


def write_store(tmp_path: Path, *, key: str = "eti_all", central: float = 0.3,
                low: float = 0.1, high: float = 0.5, support: str = "0.05",
                verdict: str = "CONFIRMED", theta: str = THETA_HIGH) -> Path:
    (tmp_path / f"{key}.yaml").write_text(
        YAML_TEMPLATE.format(key=key, central=central, low=low, high=high,
                             support=support, verdict=verdict, theta=theta),
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


def test_an_open_row_without_its_theta_direction_is_refused(tmp_path: Path) -> None:
    """D-217, the kill test of guard 4 (PHASE9_SPEC §2.4): which end θ = 1 designates
    cannot be read from the sign, so a row that does not say is refused, not defaulted."""
    from impots.behavioural.store import UndeclaredTheta

    with pytest.raises(UndeclaredTheta, match="undeclared"):
        load_store(write_store(tmp_path, theta=""))
    store = load_store(write_store(tmp_path, theta=""), strict=False)
    assert "eti_all" not in store and "θ undeclared" in store.rejected["eti_all"]


@pytest.mark.parametrize("theta, needle", [
    ("    theta: {un: middle, raison: x}\n", "undeclared"),
    ("    theta: {un: high}\n", "reason"),
])
def test_a_theta_direction_must_name_an_end_and_give_its_reason(
        tmp_path: Path, theta: str, needle: str) -> None:
    from impots.behavioural.store import UndeclaredTheta

    with pytest.raises(UndeclaredTheta, match=needle):
        load_store(write_store(tmp_path, theta=theta))


def test_a_fixed_row_carries_no_theta_and_still_loads(tmp_path: Path) -> None:
    """low = high: there is nothing for θ to move, and the row says so by being fixed."""
    store = load_store(write_store(tmp_path, central=0.2, low=0.2, high=0.2, theta=""))
    assert "eti_all" in store and not store["eti_all"].is_open


def test_every_open_row_of_the_shipped_store_declares_its_direction() -> None:
    """The shipped YAML, read whole: every open row says which end is the strongest."""
    from impots.behavioural.store import load

    store = load()
    open_rows = [p for p in store.parameters.values() if p.is_open]
    # + labour supply (D-220), creations (D-221), R&D (D-222), the IS on growth (D-246),
    # the three rows of the dividends (D-249), their wage shift (D-252), and the
    # self-financing's weight (D-263)
    assert len(open_rows) == 20
    assert all(p.theta_one in ("low", "high") and p.theta_reason for p in open_rows)
    assert store["employment_elasticity_smic"].theta_one == "low"


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
        emtr_ir_baseline=np.array([0.41]), emtr_ir_reform=np.array([0.45]),
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
        emtr_ir_baseline=np.array([0.45]), emtr_ir_reform=np.array([0.41]),
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
        emtr_ir_baseline=np.array([0.41]), emtr_ir_reform=np.array([0.45]),
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
        emtr_ir_baseline=np.array([0.41]), emtr_ir_reform=np.array([0.45]),
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
        emtr_ir_baseline=np.array([]), emtr_ir_reform=np.array([]),
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
        emtr_ir_baseline=np.array([0.41]), emtr_ir_reform=np.array([0.41]),
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
    assert grading.induced_variation(baseline, reform, weights, np.ones(1000)) == \
        pytest.approx(0.01, abs=1e-6)


def _top_only(n: int = 1000) -> dict[str, np.ndarray]:
    """A rise of the income tax's top rate: 1 % of the households, the top, see their
    income-tax rate go from 45 % to 60 %; nobody else moves. Their total rate goes from
    60 % to 75 %."""
    top = np.arange(n) >= n - 10
    base = np.where(top, 400_000.0, 40_000.0)
    ir0 = np.where(top, 0.45, 0.11)
    total0 = ir0 + 0.15
    return {"emtr_ir_baseline": ir0, "emtr_ir_reform": np.where(top, 0.60, ir0),
            "emtr_baseline": total0, "emtr_reform": np.where(top, 0.75, total0),
            "taxable_base": base, "weights": np.full(n, 1_000.0),
            "top_decile": np.arange(n) >= int(0.9 * n)}


def test_a_reform_of_the_top_alone_is_graded_on_the_top() -> None:
    """D-336, decision 4: C1's support metric is the median of |Δ(1 − τ_IR)| weighted by
    each household's contribution to C1, not the 95th percentile of the households. A
    tranche that moves the top percentile alone left that percentile at zero, and the
    reform C1 bites hardest on came out « in-support » (Tondelier, D-333). Now 0,15, five
    times the top elasticity's support of 0,03: illustrative, and widened."""
    inputs = _top_only()
    assert grading.induced_variation(inputs["emtr_ir_baseline"], inputs["emtr_ir_reform"],
                                     inputs["weights"], inputs["taxable_base"]) == \
        pytest.approx(0.15)
    result = band_module.compute(mechanical=1.0e9, reform=FakeReform(ir_bareme=[]),
                                 store=load_store(), **inputs)
    assert result.grade == "illustrative"
    assert next(c for c in result.channels if c["key"] == "c1_eti")["grade"] == \
        "illustrative"


def test_c1_reads_the_income_tax_s_rate_and_loses_at_the_total_one() -> None:
    """D-336, decision 4: Δln(1 − τ_IR) on the income tax's own rate, the receipt at the
    total rate τ¹. For the top above: ln(0,40 / 0,55) on the IR, against ln(0,25 / 0,40)
    on the total rate before — a smaller response, still lost at 75 %."""
    inputs = _top_only()
    store = Store(parameters={
        "eti_all": parameter("eti_all", 0.02, 0.02, 0.02),
        "eti_top_decile": parameter("eti_top_decile", 0.31, 0.31, 0.31),
    })
    result = channels.elasticity_of_taxable_income(
        store, FakeReform(ir_bareme=[]), draws=1, rng=np.random.default_rng(0), **inputs)
    expected = 0.31 * 10 * 1_000.0 * 400_000.0 * np.log(0.40 / 0.55) * 0.75
    assert result.central == pytest.approx(expected, rel=1e-12)
    assert result.diagnostics["statistics"]["A_haut"] == pytest.approx(expected / 0.31)
    assert result.diagnostics["statistics"]["A_bas"] == 0.0
    # Not the total rate's Δln, which C1 read before: 1,5 times larger here.
    assert abs(expected) < abs(0.31 * 10 * 1_000.0 * 400_000.0 * np.log(0.25 / 0.40) * 0.75)


def test_c1_publishes_the_share_its_floored_households_carry() -> None:
    """The floor 0,05 stays, and the share of C1 carried by the households at it is
    published (D-336, decision 4). Two households: one floored by the reform (IR rate to
    97 %), one not; the share is the floored one's term over both, at the centres."""
    store = Store(parameters={
        "eti_all": parameter("eti_all", 0.02, 0.02, 0.02),
        "eti_top_decile": parameter("eti_top_decile", 0.31, 0.31, 0.31),
    })
    result = channels.elasticity_of_taxable_income(
        store, FakeReform(ir_bareme=[]), emtr_baseline=np.array([0.5, 0.5]),
        emtr_reform=np.array([0.9, 0.6]), emtr_ir_baseline=np.array([0.4, 0.4]),
        emtr_ir_reform=np.array([0.97, 0.5]), taxable_base=np.array([1e5, 1e5]),
        weights=np.array([1.0, 1.0]), top_decile=np.array([False, False]), draws=1,
        rng=np.random.default_rng(0))
    floored = abs(np.log(0.05 / 0.6) * 0.9)
    other = abs(np.log(0.5 / 0.6) * 0.6)
    assert result.diagnostics["households_at_the_net_of_tax_floor"] == 1
    assert result.diagnostics["share_at_the_net_of_tax_floor"] == pytest.approx(
        floored / (floored + other))


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
        "emtr_ir_baseline": np.full(n, 0.41),
        "emtr_ir_reform": np.full(n, 0.43),
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
    inputs["emtr_ir_reform"] = np.full(len(inputs["weights"]), 0.71)
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


# --------------------------------------------------------------------------- #
# the marginal-rate distribution, golden-pinned per population vintage
# --------------------------------------------------------------------------- #
BASELINE_ARTIFACT = (
    Path(__file__).resolve().parents[1] / "data" / "processed" / "baseline_2024.json"
)

#: Decile medians of the effective marginal rate, 2024 vintage, 20 000-household
#: sample. Pinned because this distribution is a published product: it moves when the
#: engine changes, and it should move for that reason and no other.
EMTR_MEDIANS_2024 = [0.208, 0.317, 0.322, 0.328, 0.377, 0.419, 0.427, 0.431, 0.515, 0.635]


@pytest.mark.skipif(
    not BASELINE_ARTIFACT.exists(), reason="no baseline artifact in this checkout"
)
def test_the_marginal_rate_distribution_is_pinned() -> None:
    import json

    rows = json.loads(BASELINE_ARTIFACT.read_text(encoding="utf-8")).get("emtr_deciles")
    if not rows:
        pytest.skip("baseline artifact carries no EMTR distribution yet")
    assert [row["decile"] for row in rows] == list(range(1, 11))
    for row, expected in zip(rows, EMTR_MEDIANS_2024, strict=True):
        assert row["emtr_median"] == pytest.approx(expected, abs=0.002), (
            f"decile {row['decile']} moved; if that is intended, repin it and say why"
        )


@pytest.mark.skipif(
    not BASELINE_ARTIFACT.exists(), reason="no baseline artifact in this checkout"
)
def test_marginal_rates_rise_across_the_distribution_and_top_out_high() -> None:
    """Two claims about France worth failing on. The distribution is monotone by
    construction (they are deciles of the rate), and its top decile sits above 60 % —
    which is the fact the table exists to show, since those households are not the
    richest but the ones losing benefits as they earn."""
    import json

    rows = json.loads(BASELINE_ARTIFACT.read_text(encoding="utf-8")).get("emtr_deciles")
    if not rows:
        pytest.skip("baseline artifact carries no EMTR distribution yet")
    medians = [row["emtr_median"] for row in rows]
    assert medians == sorted(medians)
    assert medians[-1] > 0.60
    assert all(-0.2 <= m <= 1.5 for m in medians)


# --------------------------------------------------------------------------- #
# C4, revived from the report's own tables (D-037)
# --------------------------------------------------------------------------- #
def production_tax_store() -> Store:
    """The shipped bounds, so a change to the YAML that breaks them fails here."""
    from impots.behavioural.store import load as load_real

    return load_real()


def test_the_c4_band_is_centred_on_zero_and_read_from_the_tables() -> None:
    """The bounds are the union of two published 95 % intervals, each scaled by its
    own first stage. They straddle zero because the two comparisons disagree: the
    larger cut shows a significant positive effect, the smaller an insignificant
    negative one. That disagreement IS the null."""
    parameter = production_tax_store()["production_tax_investment"]
    assert parameter.central == 0.0
    assert parameter.low == pytest.approx(-0.071, abs=0.001)
    assert parameter.high == pytest.approx(0.069, abs=0.001)
    assert parameter.confidence == "low"
    assert parameter.support.max_variation_graded_in_support == pytest.approx(0.6323)
    # The derivation has to stay checkable from the printed coefficients.
    assert pytest.approx(0.069, abs=0.001) == (0.0221 + 1.96 * 0.0110) / 0.6323
    assert pytest.approx(-0.071, abs=0.001) == (-0.0035 - 1.96 * 0.0108) / 0.3491


def test_c4_reports_per_cent_of_investment_not_euros() -> None:
    """Investment is not revenue. A channel that returned euros here would be summed
    into the revenue band by a machine that cannot tell the difference."""
    result = channels.production_tax_investment(
        production_tax_store(), FakeReform(cvae_taux_max=0.0014),
        production_tax_baseline=3.28e9, production_tax_reform=1.64e9,
        draws=4000, rng=np.random.default_rng(1),
    )
    assert result.applies
    assert result.unit == "%"
    assert result.central == pytest.approx(0.0, abs=0.005)
    assert result.diagnostics["delta_log_production_tax"] == pytest.approx(-0.693, abs=0.001)


def test_c4_is_never_summed_into_the_revenue_band() -> None:
    """The category error this guards is one that typechecks."""
    result = band_module.compute(
        mechanical=-4.5e8, reform=FakeReform(cvae_taux_max=0.0014),
        store=production_tax_store(),
        production_tax_baseline=3.28e9, production_tax_reform=1.64e9,
    )
    live = [c for c in result.channels if c["applies"]]
    assert [c["key"] for c in live] == ["c4_investment"]
    assert result.band is None, (
        "a percentage change in investment must not become a euro band"
    )
    assert live[0]["band"] is not None, "the channel still reports its own band"


def test_a_bigger_tax_cut_moves_investment_further() -> None:
    """Linear in the log change, so the response scales with the reform. If it did
    not, the support bound would be meaningless."""
    common = dict(store=production_tax_store(), reform=FakeReform(cvae_taux_max=0.001),
                  draws=2000, rng=None)
    small = channels.production_tax_investment(
        production_tax_baseline=3.0e9, production_tax_reform=2.7e9,
        **{**common, "rng": np.random.default_rng(5)})
    large = channels.production_tax_investment(
        production_tax_baseline=3.0e9, production_tax_reform=1.0e9,
        **{**common, "rng": np.random.default_rng(5)})
    assert np.ptp(large.draws) > 3 * np.ptp(small.draws)


def test_c4_fails_loudly_without_a_production_tax_to_move() -> None:
    with pytest.raises(channels.ChannelInputMissing, match="strictly positive"):
        channels.production_tax_investment(
            production_tax_store(), FakeReform(cvae_taux_max=0.0014),
            production_tax_baseline=0.0, production_tax_reform=1.0,
            draws=4, rng=np.random.default_rng(0),
        )


# --------------------------------------------------------------------------- #
# C2 and C3, awake (D-038)
# --------------------------------------------------------------------------- #
def employer_store() -> Store:
    from impots.behavioural.store import load as load_real

    return load_real()


def test_the_employment_profile_interpolates_between_two_published_points() -> None:
    """−0.43 at the SMIC, −0.1 at twice it, nothing above. The straight line between
    is this project's construction and is labelled as such; the zero above is a
    refusal to extrapolate, replacing a constant −0.2 that rested on an uncited
    Swedish study whose downloaded PDF was a different paper."""
    profile = channels.employment_elasticity_profile(
        np.array([1.0, 1.5, 2.0, 2.5]), -0.43, -0.1, 2.0
    )
    assert profile[0] == pytest.approx(-0.43)
    assert profile[1] == pytest.approx(-0.265)
    assert profile[2] == pytest.approx(-0.10)
    assert profile[3] == 0.0, "no response is applied above the fade-out"


def test_a_labour_cost_cut_creates_jobs() -> None:
    """The sign, pinned. The elasticity is negative and a cut makes the cost change
    negative, so their product is positive. A first version carried an extra negation
    and reported 99 000 jobs LOST from a 1.5 % cut in labour cost.

    Worked example: one job at the SMIC whose labour cost falls 2 %. At −0.43 the
    response is −0.43 × −0.02 = +0.0086 jobs, so a weighted cell of 100 000 such
    workers gains 860."""
    store = Store(parameters={
        "employment_elasticity_smic": parameter(
            "employment_elasticity_smic", -0.43, -0.43, -0.43, knobs=("allegement_general_*",)),
        "employment_elasticity_at_fadeout": parameter(
            "employment_elasticity_at_fadeout", -0.1, -0.1, -0.1, knobs=("allegement_general_*",)),
        "employment_fadeout_smic_multiple": parameter(
            "employment_fadeout_smic_multiple", 2.0, 2.0, 2.0, knobs=("allegement_general_*",)),
    })
    result = channels.employment_at_the_smic(
        store, FakeReform(allegement_general_plafond=1.8),
        smic_multiple=np.array([1.0]), relative_cost_change=np.array([-0.02]),
        weights=np.array([100_000.0]), draws=8, rng=np.random.default_rng(0),
    )
    assert result.applies
    assert result.unit == "emplois"
    assert result.central == pytest.approx(860.0, abs=1.0)


def test_no_employment_response_is_applied_above_the_fade_out() -> None:
    store = Store(parameters={
        "employment_elasticity_smic": parameter(
            "employment_elasticity_smic", -0.43, -0.43, -0.43, knobs=("allegement_general_*",)),
        "employment_elasticity_at_fadeout": parameter(
            "employment_elasticity_at_fadeout", -0.1, -0.1, -0.1, knobs=("allegement_general_*",)),
        "employment_fadeout_smic_multiple": parameter(
            "employment_fadeout_smic_multiple", 2.0, 2.0, 2.0, knobs=("allegement_general_*",)),
    })
    result = channels.employment_at_the_smic(
        store, FakeReform(allegement_general_plafond=1.8),
        smic_multiple=np.array([3.0]), relative_cost_change=np.array([-0.02]),
        weights=np.array([100_000.0]), draws=8, rng=np.random.default_rng(0),
    )
    assert result.central == pytest.approx(0.0, abs=1e-9)


def test_c2_counts_no_jobs_as_zero_not_minus_zero() -> None:
    """D-261. The plafond's shape: an earner at the SMIC whose labour cost does not move,
    and one at 3.2 SMIC, above the fade-out, whose cost falls. No job either way, but
    the products summed to +0.0 and the negative elasticity made it −0.0, which the
    study's page printed « −0,00 » emplois."""
    store = Store(parameters={
        "employment_elasticity_smic": parameter(
            "employment_elasticity_smic", -0.43, -0.43, -0.43, knobs=("allegement_general_*",)),
        "employment_elasticity_at_fadeout": parameter(
            "employment_elasticity_at_fadeout", -0.1, -0.1, -0.1, knobs=("allegement_general_*",)),
        "employment_fadeout_smic_multiple": parameter(
            "employment_fadeout_smic_multiple", 2.0, 2.0, 2.0, knobs=("allegement_general_*",)),
    })
    result = channels.employment_at_the_smic(
        store, FakeReform(allegement_general_plafond=3.5),
        smic_multiple=np.array([1.0, 3.2]), relative_cost_change=np.array([0.0, -0.05]),
        weights=np.array([1_000_000.0, 1_000_000.0]), draws=4, rng=np.random.default_rng(0),
    )
    assert [math.copysign(1.0, d) for d in result.draws] == [1.0] * 4


def test_a_contribution_cut_passed_through_raises_wages() -> None:
    """The other sign. `contribution_delta` is the employer's bill, so a cut is
    negative — and a cut that passes through fully makes wages RISE by its amount."""
    result = channels.contribution_incidence(
        employer_store(), FakeReform(bandeau_famille_taux=0.0),
        contribution_delta=-2.0e9, draws=4000, rng=np.random.default_rng(1),
    )
    assert result.applies
    assert result.central > 0, "workers must gain from a contribution cut"
    assert result.draws.max() <= 2.3e9


def test_c3_spans_both_incidence_assumptions_rather_than_choosing() -> None:
    """No French knob moves a contribution of a single linkage class — maladie and
    famille cover is universal, and the réduction générale spans both kinds — so the
    range IS the answer, and the distributional statement inherits it visibly."""
    result = channels.contribution_incidence(
        employer_store(), FakeReform(bandeau_famille_taux=0.0),
        contribution_delta=-1.0e9, draws=4000, rng=np.random.default_rng(2),
    )
    draws = result.draws
    assert np.percentile(draws, 5) < 0.15e9, "one end must be near no pass-through"
    assert np.percentile(draws, 95) > 0.85e9, "the other must be near full"


def test_c3_is_a_reallocation_and_never_enters_the_revenue_band() -> None:
    """It is denominated in euros and must still stay out: the mechanical total is
    identical at both ends of its range, so adding it counts the same euros twice.
    Membership is declared per channel, never inferred from the unit."""
    result = band_module.compute(
        mechanical=-2.0e9, reform=FakeReform(bandeau_famille_taux=0.0),
        store=employer_store(), contribution_delta=-2.0e9,
    )
    live = {c["key"] for c in result.channels if c["applies"]}
    assert "c3_incidence" in live
    assert result.band is None, "a reallocation must not become a revenue band"


def test_c2_can_never_claim_to_be_in_support() -> None:
    """Two of its three rows cannot say how far they carry — the fade-out point and
    the threshold are descriptive, and the interpolation between them is this
    project's own. So the channel is graded an extrapolation however small the reform,
    which is the guardrail refusing to launder a construction as evidence."""
    result = band_module.compute(
        mechanical=-1.0e8, reform=FakeReform(allegement_general_plafond=1.7),
        store=employer_store(), smic_multiple=np.array([1.1]),
        relative_cost_change=np.array([-0.001]), earner_weights=np.array([1000.0]),
    )
    assert result.channels
    assert result.grade == "illustrative"


def test_c2_fails_loudly_without_a_wage_profile() -> None:
    with pytest.raises(channels.ChannelInputMissing, match="smic_multiple"):
        channels.employment_at_the_smic(
            employer_store(), FakeReform(allegement_general_plafond=1.8),
            smic_multiple=np.array([]), relative_cost_change=np.array([]),
            weights=np.array([]), draws=4, rng=np.random.default_rng(0),
        )


def _run(frame, cost_cut: float = 0.0):
    """What `runner.run` hands back for `frame`, without the engine. Its persons, each
    with a labour cost equal to their gross that falls by `cost_cut`, or by their own
    `cut` when the frame carries one; and one row per household at the MEAN of its
    members' weights, as the runner aggregates, with its persons' costs summed."""
    from types import SimpleNamespace

    import polars as pl

    cut = pl.col("cut") if "cut" in frame.columns else pl.lit(cost_cut)
    persons = frame.select(
        "person_id", "household_id", "salaire_brut_annuel", "weight",
        pl.col("salaire_brut_annuel").alias("salaire_super_brut"),
        (pl.col("salaire_brut_annuel") * (1.0 - cut)).alias("salaire_super_brut_reform"))
    households = (
        frame.group_by("household_id").agg(pl.col("weight").mean())
        .join(persons.group_by("household_id").agg(
            pl.col("salaire_super_brut").sum(), pl.col("salaire_super_brut_reform").sum()),
            on="household_id")
        .sort("household_id"))
    return SimpleNamespace(households=households, persons=persons)


def test_c2_counts_the_population_s_jobs_on_a_quick_tier_pass() -> None:
    """D-259. The quick tier prices 20 000 of the 199 451 households, reweighted to the
    population; `_employer_inputs` read every earner of the WHOLE frame at the frame's
    weight, and gave a cost change only to those whose household the run had priced.
    The others counted at zero, and the survivors at their own weight, not the
    subsample's: C2 counted 15 % of the earners, and 1 558 jobs for 1 Md€ of
    `t_delta` where the same pass holds 9 960.

    Worked example: 1 000 households of two, one earner at 1.2 SMIC and one adult
    without a wage, each person weighing 25 000. Their labour cost falls 1 %. At
    1.2 SMIC the profile gives −0.43 + 0.2 × (−0.1 + 0.43) = −0.364, so
    25 M earners × 0.364 × 0.01 = 91 000 jobs. A tenth of the households, drawn by
    the runner's own `subsample`, must give the same 91 000; the bug gave 9 100.
    """
    from types import SimpleNamespace

    import polars as pl

    from impots.population.runner import subsample

    smic = service.smic_annual(2026)
    n = 1_000
    frame = pl.DataFrame({
        "household_id": np.repeat(np.arange(n), 2),
        "person_id": np.arange(2 * n),
        "salaire_brut_annuel": np.tile([1.2 * smic, 0.0], n),
        "weight": np.full(2 * n, 25_000.0),
    })
    reform = FakeReform(allegement_general_t_min=0.03)
    request = SimpleNamespace(year=2026, reform=reform)
    agg = SimpleNamespace(employer_contribution_delta=-1.0e9)
    store = Store(parameters={
        "employment_elasticity_smic": parameter(
            "employment_elasticity_smic", -0.43, -0.43, -0.43, knobs=("allegement_general_*",)),
        "employment_elasticity_at_fadeout": parameter(
            "employment_elasticity_at_fadeout", -0.1, -0.1, -0.1, knobs=("allegement_general_*",)),
        "employment_fadeout_smic_multiple": parameter(
            "employment_fadeout_smic_multiple", 2.0, 2.0, 2.0, knobs=("allegement_general_*",)),
    })

    def jobs(run) -> float:
        inputs = service.employer_inputs(request, run, agg)
        return channels.employment_at_the_smic(
            store, reform, smic_multiple=inputs["smic_multiple"],
            relative_cost_change=inputs["relative_cost_change"],
            weights=inputs["earner_weights"], draws=1, rng=np.random.default_rng(0),
        ).central

    full = jobs(_run(frame, 0.01))
    quick = jobs(_run(subsample(frame, n // 10), 0.01))
    assert full == pytest.approx(91_000.0, rel=1e-9)
    assert quick == pytest.approx(91_000.0, rel=1e-9), (
        "the quick tier must count the jobs of the population it was reweighted to")


def test_c2_gives_each_earner_their_own_cost_change() -> None:
    """D-261. Every earner carried their household's change in labour cost, so an earner
    at the SMIC took a share of a partner's cut at 3 SMIC. Raising the plafond relieves
    only wages above 3 SMIC, where C2 does not respond, and C2 still counted 1 317 jobs
    for its first bundle of the study: every one of them from a household with an earner
    above 3 SMIC.

    Worked example, two households weighing 1 000 000 each. In the first, an earner at the
    SMIC whose labour cost does not move, and a partner at 3.2 SMIC whose cost falls 5 %,
    the plafond's shape. In the second, one earner at the SMIC whose cost falls 1 %. Each
    on their own change: the partner is above the fade-out and the first earner has
    nothing to respond to, so the jobs are the second household's,
    1 000 000 × 0.43 × 0.01 = 4 300. The household's rate lent the first earner
    0.05 × 3.2 / 4.2 = 3.81 % of a cut that was not theirs: 16 381 jobs more.
    """
    from types import SimpleNamespace

    import polars as pl


    smic = service.smic_annual(2026)
    frame = pl.DataFrame({
        "household_id": [0, 0, 1],
        "person_id": [0, 1, 2],
        "salaire_brut_annuel": [smic, 3.2 * smic, smic],
        "weight": [1_000_000.0] * 3,
        "cut": [0.0, 0.05, 0.01],
    })
    reform = FakeReform(allegement_general_plafond=3.5)
    request = SimpleNamespace(year=2026, reform=reform)
    agg = SimpleNamespace(employer_contribution_delta=-1.0e9)
    store = Store(parameters={
        "employment_elasticity_smic": parameter(
            "employment_elasticity_smic", -0.43, -0.43, -0.43, knobs=("allegement_general_*",)),
        "employment_elasticity_at_fadeout": parameter(
            "employment_elasticity_at_fadeout", -0.1, -0.1, -0.1, knobs=("allegement_general_*",)),
        "employment_fadeout_smic_multiple": parameter(
            "employment_fadeout_smic_multiple", 2.0, 2.0, 2.0, knobs=("allegement_general_*",)),
    })
    inputs = service.employer_inputs(request, _run(frame), agg)
    jobs = channels.employment_at_the_smic(
        store, reform, smic_multiple=inputs["smic_multiple"],
        relative_cost_change=inputs["relative_cost_change"],
        weights=inputs["earner_weights"], draws=1, rng=np.random.default_rng(0),
    ).central
    assert jobs == pytest.approx(4_300.0, rel=1e-9), (
        "an earner must respond to their own labour cost, not to their household's")

def _employer_case(monkeypatch, persons: dict, households: dict) -> dict:
    """C2's inputs off a hand-built run, its persons and its households, the SMIC at
    20 000 € a year. The run's persons are its own since D-261: the households it priced,
    each person at the weight the run gave them."""
    from types import SimpleNamespace

    import polars as pl


    monkeypatch.setattr(service, "smic_annual", lambda year: 20_000.0)
    return service.employer_inputs(
        SimpleNamespace(year=2026, reform=FakeReform(allegement_general_t_min=0.03)),
        SimpleNamespace(persons=pl.DataFrame(persons), households=pl.DataFrame(households)),
        SimpleNamespace(employer_contribution_delta=-1_000.0))


def test_c2_counts_the_run_s_households_at_the_run_s_weights(monkeypatch) -> None:
    """The pass priced 1 household of the frame's 3, and weighted it for all three: 300
    against 100 in the frame. Its two earners, at 1,25 and 2 SMIC, each carry a rate of
    −0,01, at 300: Σ w × Δc/c = −6. Earners of the households the pass never priced have
    no rate, not a zero one; counted at 0 with the frame's weights they gave −2, a jobs
    figure diluted by the subsample (D-255). The run's persons are its own (D-261): the
    unpriced households are not in them."""
    inputs = _employer_case(
        monkeypatch,
        persons={"person_id": [1, 2], "household_id": [1, 1],
                 "salaire_brut_annuel": [25_000.0, 40_000.0], "weight": [300.0, 300.0],
                 "salaire_super_brut": [50_000.0, 50_000.0],
                 "salaire_super_brut_reform": [49_500.0, 49_500.0]},
        households={"household_id": [1], "weight": [300.0]},
    )
    order = np.argsort(inputs["smic_multiple"])
    assert inputs["smic_multiple"][order] == pytest.approx([1.25, 2.0])
    assert inputs["relative_cost_change"][order] == pytest.approx([-0.01, -0.01])
    assert inputs["earner_weights"][order] == pytest.approx([300.0, 300.0])
    assert float(np.sum(inputs["earner_weights"] * inputs["relative_cost_change"])) \
        == pytest.approx(-6.0)


def test_c2_keeps_each_earner_s_weight_as_the_subsample_scales_it(monkeypatch) -> None:
    """The subsample scales every member of a household by the same factor, the run's
    household weight over the frame's mean (`runner.subsample`). Here 120 and 80, mean
    100, at 300: 360 and 240, what the subsampled frame itself carries, and the run's
    persons with it. The household's 300 for each would count one earner a sixth too few
    and the other a quarter too many (D-255, D-259)."""
    inputs = _employer_case(
        monkeypatch,
        persons={"person_id": [1, 2], "household_id": [1, 1],
                 "salaire_brut_annuel": [25_000.0, 40_000.0], "weight": [360.0, 240.0],
                 "salaire_super_brut": [50_000.0, 50_000.0],
                 "salaire_super_brut_reform": [49_500.0, 49_500.0]},
        households={"household_id": [1], "weight": [300.0]},
    )
    order = np.argsort(inputs["smic_multiple"])
    assert inputs["earner_weights"][order] == pytest.approx([360.0, 240.0])


def test_c2_s_weights_are_the_subsampled_frame_s(monkeypatch) -> None:
    """Against `runner.subsample` itself, on a frame whose weights are skewed as PPS
    draws them and unequal inside a household: the earners are those of the subsampled
    frame, and their weights sum to what they weigh there."""
    import polars as pl

    from impots.population.runner import subsample

    rng = np.random.default_rng(3)
    ids = np.repeat(np.arange(200), 2)
    frame = pl.DataFrame({
        "household_id": ids,
        "salaire_brut_annuel": rng.choice([0.0, 22_000.0, 35_000.0], size=ids.size),
        "weight": np.repeat(rng.lognormal(5.0, 0.8, size=200), 2)
        * rng.choice([0.8, 1.0, 1.2], size=ids.size),
    })
    sub = subsample(frame, 30).with_columns(person_id=pl.int_range(pl.len()))
    # The run's persons as the runner builds them from the subsampled frame, each with
    # their own weight and a labour cost that falls 1 %; its households at the mean.
    persons = sub.with_columns(salaire_super_brut=pl.lit(50_000.0),
                               salaire_super_brut_reform=pl.lit(49_500.0))
    households = sub.group_by("household_id").agg(pl.col("weight").mean())
    inputs = _employer_case(monkeypatch, persons.to_dict(as_series=False),
                            households.to_dict(as_series=False))
    earners = sub.filter(pl.col("salaire_brut_annuel") > 0)
    assert len(inputs["earner_weights"]) == earners.height
    assert float(inputs["earner_weights"].sum()) == pytest.approx(
        float(earners["weight"].sum()), rel=1e-12)


def test_the_reform_cache_keeps_a_bounded_number_of_files(tmp_path, monkeypatch):
    """Every distinct reform priced with the behavioural band wrote one parquet into
    data/processed, and nothing ever removed one: whoever chose reforms over HTTP chose
    the disk used (D-173). The newest are kept."""
    import polars as pl

    from impots.api.schemas import ReformSpec
    from impots.behavioural import emtr

    monkeypatch.setattr(emtr, "PROCESSED", tmp_path)
    monkeypatch.setattr(emtr, "CACHE_MAX", 3, raising=False)
    monkeypatch.setattr(emtr, "compute", lambda population, **k: emtr.EmtrResult(
        households=pl.DataFrame({"x": [1]}), year=k.get("year", 2024)))
    reformes = [ReformSpec(decote_taux=0.10 + i / 100) for i in range(6)]
    # A population, which `cached` reads for the fingerprint its files carry (D-276).
    frame = pl.DataFrame({"person_id": [0], "household_id": ["h0"], "weight": [1.0],
                          "salaire_brut_annuel": [30_000.0]})
    for reforme in reformes:
        emtr.cached(frame, "2024", reform=reforme)
    assert len(list(tmp_path.glob("emtr_2024_*.parquet"))) == 3
    derniere = emtr.cache_key("2024", 2024, reformes[-1], None)
    assert (tmp_path / f"emtr_2024_{derniere}.parquet").exists()


def test_the_emtr_caches_do_not_outlive_a_change_of_population_wiring(tmp_path, monkeypatch):
    """Both EMTR caches were keyed on vintage, year, sample, step and reform — never on
    what the population wiring computes. D-176 changed that for every pensioner: a file
    written before it would have been served after it, a baseline rate of one regime
    beside a reform rate of the other, and nothing would have said so."""
    import polars as pl

    from impots.behavioural import emtr
    from impots.population import to_openfisca

    monkeypatch.setattr(emtr, "PROCESSED", tmp_path)
    frame = pl.DataFrame({"person_id": [0], "household_id": ["h0"], "weight": [1.0],
                          "salaire_brut_annuel": [30_000.0]})

    # The baseline rates, memoised inside `compute`.
    monkeypatch.setattr(emtr, "_rate", lambda *args, **kwargs: (np.zeros(1), np.zeros(1)))
    monkeypatch.setattr(to_openfisca, "WIRING", "before", raising=False)
    emtr.compute(frame, vintage="2024")
    monkeypatch.setattr(to_openfisca, "WIRING", "after", raising=False)
    assert "baseline_cached" not in emtr.compute(frame, vintage="2024").guards

    # The whole result, memoised by `cached`.
    monkeypatch.setattr(emtr, "compute", lambda population, **k: emtr.EmtrResult(
        households=pl.DataFrame({"x": [1]}), year=k.get("year", 2024)))
    monkeypatch.setattr(to_openfisca, "WIRING", "before", raising=False)
    emtr.cached(frame, "2024")
    monkeypatch.setattr(to_openfisca, "WIRING", "after", raising=False)
    assert emtr.cached(frame, "2024").guards.get("cached") is not True


def test_the_emtr_caches_do_not_serve_the_vintage_s_rates_to_an_aged_population(
        tmp_path, monkeypatch):
    """An aged population has the vintage's rows, weights and households, so the baseline
    cache's height check cannot see it, and neither key named it. `/population/simulate`
    caches the vintage as built; `/predictif/simulate` prices the same reform, year and
    sample on the population aged to the year (D-226). Each must read its own file. And
    the vintage's own keys must not move, or every file already on disk is recomputed."""
    import hashlib
    import json

    import polars as pl

    from impots.behavioural import emtr
    from impots.population import to_openfisca
    from impots.uprating import Uprating

    monkeypatch.setattr(emtr, "PROCESSED", tmp_path)
    frame = pl.DataFrame({"person_id": [0], "household_id": ["h0"], "weight": [1.0],
                          "salaire_brut_annuel": [30_000.0]})
    aged = Uprating(wage=0.03, price=0.02, source="une source", base_year=2024).key()
    assert aged == Uprating(wage=0.03, price=0.02, source="une autre",
                            base_year=2024).key(), "the source is a label, not a rate"

    # The baseline rates, memoised inside `compute`.
    monkeypatch.setattr(emtr, "_rate", lambda *args, **kwargs: (np.zeros(1), np.zeros(1)))
    emtr.compute(frame, year=2026, vintage="2024")
    assert "baseline_cached" not in emtr.compute(
        frame, year=2026, vintage="2024", uprating_key=aged).guards
    assert emtr.compute(frame, year=2026, vintage="2024").guards["baseline_cached"]

    # The whole result, memoised by `cached`.
    monkeypatch.setattr(emtr, "compute", lambda population, **k: emtr.EmtrResult(
        households=pl.DataFrame({"x": [1]}), year=k.get("year", 2024)))
    emtr.cached(frame, "2024", year=2026)
    assert emtr.cached(frame, "2024", year=2026,
                       uprating_key=aged).guards.get("cached") is not True
    assert emtr.cached(frame, "2024", year=2026).guards.get("cached") is True

    # Since D-336 the files carry the income tax's own rate, and the key says so.
    before = json.dumps({"vintage": "2024", "year": 2026, "sample": None, "reform": None,
                         "wiring": to_openfisca.WIRING, "columns": emtr.COLUMNS_VERSION},
                        sort_keys=True, default=str)
    assert emtr.cache_key("2024", 2026) == hashlib.sha256(before.encode()).hexdigest()[:16]


def test_an_emtr_cache_serves_only_the_frame_it_was_computed_on(tmp_path, monkeypatch):
    """The keys name the vintage, the year, the sample, the reform and the uprating, not
    the frame itself. The frozen view of `impots predictif` priced the vintage under the
    aged view's key: the view priced first wrote the rates both views then read, and the
    frozen view's reform rates sat beside an aged baseline, which moved the marginal rate
    of 98 % of the households under a décote (D-276). A file computed on another frame,
    or written before it said which, is recomputed, not served."""
    import polars as pl

    from impots.behavioural import emtr
    from impots.population import to_openfisca
    from impots.uprating import Uprating

    monkeypatch.setattr(emtr, "PROCESSED", tmp_path)
    aged = Uprating(wage=0.03, price=0.02, source="une source", base_year=2024).key()

    def frame(salary: float) -> pl.DataFrame:
        return pl.DataFrame({"person_id": [0], "household_id": ["h0"], "weight": [1.0],
                             "salaire_brut_annuel": [salary]})

    vintage, priced = frame(30_000.0), frame(31_827.0)
    # A rate that says which frame it was computed on.
    monkeypatch.setattr(emtr, "_rate", lambda frame, *args, **kwargs: (np.array(
        [frame["salaire_brut_annuel"][0] / 1e6]),) * 2)

    # The baseline rates, memoised inside `compute`.
    emtr.compute(vintage, year=2026, vintage="2024", uprating_key=aged)
    other = emtr.compute(priced, year=2026, vintage="2024", uprating_key=aged)
    assert "baseline_cached" not in other.guards
    assert other.households["emtr"].to_list() == [0.031827]
    assert emtr.compute(priced, year=2026, vintage="2024",
                        uprating_key=aged).guards["baseline_cached"]

    # The whole result, memoised by `cached`.
    emtr.cached(vintage, "2024", year=2026, uprating_key=aged)
    served = emtr.cached(priced, "2024", year=2026, uprating_key=aged)
    assert served.guards.get("cached") is not True
    assert served.households["emtr"].to_list() == [0.031827]
    again = emtr.cached(priced, "2024", year=2026, uprating_key=aged)
    assert again.guards.get("cached") is True
    assert again.households.columns == served.households.columns

    # Files written before the files said their frame.
    pl.DataFrame({"emtr": [0.5]}).write_parquet(
        tmp_path / f"emtr_baseline_2024_2027_full_100_{to_openfisca.WIRING}_{aged}.parquet")
    old = emtr.compute(priced, year=2027, vintage="2024", uprating_key=aged)
    assert "baseline_cached" not in old.guards
    assert old.households["emtr"].to_list() == [0.031827]
    key = emtr.cache_key("2024", 2028, None, None, aged)
    pl.DataFrame({"household_id": ["h0"], "weight": [1.0], "n_earners": [1],
                  "emtr": [0.5]}).write_parquet(tmp_path / f"emtr_2024_{key}.parquet")
    old = emtr.cached(priced, "2024", year=2028, uprating_key=aged)
    assert old.guards.get("cached") is not True
    assert old.households["emtr"].to_list() == [0.031827]



# --------------------------------------------------------------------------- #
# C11 — the self-financing of a targeted contribution cut (M5, D-263)
# --------------------------------------------------------------------------- #
def _c11_store(weight: float = 0.5, *, open_weight: bool = False) -> Store:
    """C2's three rows and C11's three, each at one value; the weight open on demand."""
    import dataclasses

    knobs = ("allegement_general_*", "bandeau_maladie_*", "bandeau_famille_*")
    rows = {
        "employment_elasticity_smic": parameter(
            "employment_elasticity_smic", -0.43, -0.43, -0.43, knobs=knobs),
        "employment_elasticity_at_fadeout": parameter(
            "employment_elasticity_at_fadeout", -0.1, -0.1, -0.1, knobs=knobs),
        "employment_fadeout_smic_multiple": parameter(
            "employment_fadeout_smic_multiple", 2.0, 2.0, 2.0, knobs=knobs),
        "autofinancement_retour_par_emploi": parameter(
            "autofinancement_retour_par_emploi", 12_000.0, 12_000.0, 12_000.0, knobs=knobs),
        "autofinancement_cout_par_emploi": parameter(
            "autofinancement_cout_par_emploi", 20_000.0, 20_000.0, 20_000.0, knobs=knobs),
        "autofinancement_poids_tresor_eco": (
            dataclasses.replace(parameter("autofinancement_poids_tresor_eco", 0.5, 0.0, 1.0,
                                          knobs=knobs), theta_one="high",
                                theta_reason="le poids 1 est la réponse la plus forte")
            if open_weight else parameter("autofinancement_poids_tresor_eco", weight,
                                          weight, weight, knobs=knobs)),
    }
    return Store(parameters=rows)


def _c11(store: Store, **inputs) -> channels.ChannelResult:
    """The Trésor-Éco's 12 000 € a job, for C2's jobs too, unless a case says otherwise:
    these examples were worked by hand at that value (D-270)."""
    inputs.setdefault("value_per_job", 12_000.0)
    return channels.targeted_self_financing(
        store, FakeReform(allegement_general_t_delta_moins_de_50=0.40),
        draws=1, rng=np.random.default_rng(0), **inputs)


def test_c11_brings_back_a_share_of_the_cut_between_c2_and_the_tresor_eco() -> None:
    """D-263, the owner's choice on R5. Worked example: a 1 bn cut that C2 reads as
    10 000 jobs. C2's own reading is 10 000 × 12 000 / 1 bn = 12 %; the Trésor-Éco's is
    12 000 / 20 000 = 60 %. At p = ½, s = 0,5 × 12 % + 0,5 × 60 % = 36 %: 0,36 bn comes
    back. At p = 0 it is C2's 0,12 bn, at p = 1 the Trésor-Éco's 0,60 bn."""
    inputs = {"jobs": np.array([10_000.0]), "contribution_delta": -1.0e9,
              "targets_low_wages": True}
    half = _c11(_c11_store(0.5), **inputs)
    assert half.applies and half.in_revenue_band and half.unit == "EUR"
    assert half.central == pytest.approx(0.36e9, rel=1e-12)
    assert _c11(_c11_store(0.0), **inputs).central == pytest.approx(0.12e9, rel=1e-12)
    assert _c11(_c11_store(1.0), **inputs).central == pytest.approx(0.60e9, rel=1e-12)
    rise = _c11(_c11_store(0.5), **{**inputs, "jobs": np.array([-10_000.0]),
                                    "contribution_delta": 1.0e9})
    assert rise.central == pytest.approx(-0.36e9, rel=1e-12), "a rise loses as much"


def test_c11_never_carries_a_return_the_loop_already_carries() -> None:
    """D-263. Where the shock builder routes the cut to Mésange's uniform variant — the
    ceiling from 2026 (D-239) — its balance row is the loop, and C11 would count the same
    return twice: the channel does not open, and says why."""
    result = _c11(_c11_store(0.5), jobs=np.array([10_000.0]), contribution_delta=-1.0e9,
                  targets_low_wages=False)
    assert not result.applies and result.draws is None
    assert "variante uniforme" in result.message


def test_c11_refuses_a_c2_reading_above_the_tresor_eco() -> None:
    """D-263. θ = 1 designates the strongest response only while C2 reads less than the
    Trésor-Éco. C2 counts persons and 12 000 € is a full-time job's return, so a cut on
    part-time earners could read above 60 %: refused rather than boxed at the wrong
    corners. 60 000 jobs for 1 bn is 72 %."""
    with pytest.raises(channels.SelfFinancingOutOfRange, match="72"):
        _c11(_c11_store(0.5), jobs=np.array([60_000.0]), contribution_delta=-1.0e9,
             targets_low_wages=True)


def test_c11_says_it_was_not_computed_without_its_inputs() -> None:
    result = _c11(_c11_store(0.5))
    assert not result.applies and "Non calculé" in result.message


def test_c11_enters_the_band_on_c2_s_own_draws_and_moves_no_other_channel() -> None:
    """D-263. C11 reads C2's draws of the jobs rather than drawing them again, and comes
    last, so every other channel's draws are the ones they were. One earner cell at the
    SMIC, 1 000 000 weighted, whose labour cost falls 1 %, on a 1 bn cut: C2 counts
    1 000 000 × 0,43 × 0,01 = 4 300 jobs, read as 4 300 × 12 000 / 1 bn = 5,16 %; at
    p = ½, s = 32,58 % and 0,3258 bn comes back."""
    inputs = {"smic_multiple": np.array([1.0]), "relative_cost_change": np.array([-0.01]),
              "earner_weights": np.array([1_000_000.0]), "contribution_delta": -1.0e9}
    reform = FakeReform(allegement_general_t_delta_moins_de_50=0.40)
    store = _c11_store(0.5)
    with_c11 = band_module.compute(mechanical=-1.0e9, reform=reform, store=store,
                                   targets_low_wages=True, draws=1,
                                   self_financing_value_per_job=12_000.0, **inputs)
    without = band_module.compute(mechanical=-1.0e9, reform=reform, store=store,
                                  targets_low_wages=False, draws=1,
                                  self_financing_value_per_job=12_000.0, **inputs)
    by_key = {c["key"]: c for c in with_c11.channels}
    assert by_key["c2_employment"]["central"] == pytest.approx(4_300.0, rel=1e-12)
    assert by_key["c11_autofinancement"]["central"] == pytest.approx(0.3258e9, rel=1e-12)
    assert with_c11.band is not None
    assert with_c11.band.p50 == pytest.approx(-1.0e9 + 0.3258e9, rel=1e-9)
    others = {c["key"]: c["central"] for c in without.channels}
    assert {k: c["central"] for k, c in by_key.items() if k != "c11_autofinancement"} \
        == {k: v for k, v in others.items() if k != "c11_autofinancement"}


def test_the_employer_inputs_say_whether_the_cut_is_targeted_as_the_shocks_do(
        monkeypatch) -> None:
    """D-263. C11 opens on the shock builder's own test, `shocks.targets_low_wages`, so the
    loop and C11 never both carry the return: the `t_delta` is targeted in 2026, the
    ceiling is not from 2026 (D-239), and was before."""
    from types import SimpleNamespace

    import polars as pl

    from impots.api.schemas import ReformSpec
    from impots.behavioural import autofinancement

    # What a job brings is measured on the engine (D-256, D-270); not this case's question.
    monkeypatch.setattr(autofinancement, "job_value", lambda year: 10_032.0)

    frame = pl.DataFrame({"household_id": [0], "person_id": [0],
                          "salaire_brut_annuel": [25_000.0], "weight": [1.0],
                          "cut": [0.01]})
    agg = SimpleNamespace(employer_contribution_delta=-1.0e9)

    def targeted(year: int, **knobs) -> bool:
        request = SimpleNamespace(year=year, reform=ReformSpec(**knobs))
        return service.employer_inputs(request, _run(frame), agg)["targets_low_wages"]

    assert targeted(2026, allegement_general_t_delta_moins_de_50=0.40) is True
    assert targeted(2026, allegement_general_plafond=3.5) is False
    assert targeted(2025, allegement_general_plafond=1.8) is True


def test_c11_moves_the_receipts_at_theta_and_its_row_opens_the_box() -> None:
    """D-263. In the predictive chain, the receipts at θ carry C11, and the weight row is
    one the reform claims, so the θ box runs from C2's reading (θ = 0) to the
    Trésor-Éco's (θ = 1). Same cell as above, a 1 bn cut: 5,16 %, 32,58 % and 60 %."""
    from impots.predictif import comportement
    from impots.predictif.theta import Theta

    inputs = {"smic_multiple": np.array([1.0]), "relative_cost_change": np.array([-0.01]),
              "earner_weights": np.array([1_000_000.0]), "contribution_delta": -1.0e9,
              "targets_low_wages": True, "self_financing_value_per_job": 12_000.0}
    at = comportement.evaluate(Theta(rows={}, common=0.5), mechanical=-1.0e9,
                               reform=FakeReform(allegement_general_t_delta_moins_de_50=0.40),
                               store=_c11_store(open_weight=True), **inputs)
    assert at.claimed == ("autofinancement_poids_tresor_eco",)
    assert at.receipts == pytest.approx(-1.0e9 + 0.3258e9, rel=1e-9)
    assert at.box == pytest.approx((-1.0e9 + 0.0516e9, -1.0e9 + 0.60e9), rel=1e-9)


def test_c11_refuses_a_negative_c2_reading() -> None:
    """D-263, from the verifier's pass. A reform that cuts at the SMIC and raises above it
    can leave the employers' bill higher while C2 still counts jobs: C2's reading is then
    negative, and θ = 1 (60 % of a rise, a loss) is no longer the strongest response.
    Refused, as a reading above the Trésor-Éco's is."""
    with pytest.raises(channels.SelfFinancingOutOfRange, match="négatif"):
        _c11(_c11_store(0.5), jobs=np.array([10_000.0]), contribution_delta=0.2e9,
             targets_low_wages=True)


def test_c11_comes_last_and_leaves_every_other_channel_s_draws_as_they_were() -> None:
    """D-263, on the shipped store, whose rows are ranges: C11 draws its weight from the
    shared generator, so it comes after every other channel and the draws of C1 to C10 —
    and the golden band of D-217 — are the ones they were without it. The same cell as
    above, a 1 bn cut, a thousand draws."""
    inputs = {"smic_multiple": np.array([1.0]), "relative_cost_change": np.array([-0.01]),
              "earner_weights": np.array([1_000_000.0]), "contribution_delta": -1.0e9}
    reform = FakeReform(allegement_general_t_delta_moins_de_50=0.40)
    with_c11 = band_module.compute(mechanical=-1.0e9, reform=reform, store=employer_store(),
                                   targets_low_wages=True, draws=1000,
                                   self_financing_value_per_job=12_000.0, **inputs)
    without = band_module.compute(mechanical=-1.0e9, reform=reform, store=employer_store(),
                                  targets_low_wages=False, draws=1000,
                                  self_financing_value_per_job=12_000.0, **inputs)
    live = {c["key"]: c for c in with_c11.channels if c["applies"]}
    assert "c11_autofinancement" in live and "c3_incidence" in live
    for channel in without.channels:
        if channel["key"] != "c11_autofinancement" and channel["applies"]:
            assert live[channel["key"]]["band"] == channel["band"], channel["key"]


def test_another_seed_is_another_sample_cached_apart(tmp_path, monkeypatch):
    """C1 reads several samples of the same size (D-284): another seed draws other
    households, and its rates are cached apart. The study's sample keeps its keys and
    its file names, so that the files already written still serve it."""
    import polars as pl

    from impots.behavioural import emtr
    from impots.population.runner import SAMPLE_SEED

    monkeypatch.setattr(emtr, "PROCESSED", tmp_path)
    frame = pl.DataFrame({
        "person_id": list(range(40)), "household_id": [f"h{i:02d}" for i in range(40)],
        "weight": [1.0 + i for i in range(40)],
        "salaire_brut_annuel": [20_000.0 + 1_000.0 * i for i in range(40)]})

    def rate(priced, *args, **kwargs):
        return (priced.group_by("household_id").agg(pl.col("salaire_brut_annuel").sum())
                .sort("household_id")["salaire_brut_annuel"].to_numpy() / 1e6,) * 2

    monkeypatch.setattr(emtr, "_rate", rate)
    assert emtr.C1_SAMPLES[0] == SAMPLE_SEED and len(set(emtr.C1_SAMPLES)) == 4
    assert emtr.cache_key("2024", 2026, None, 10, seed=SAMPLE_SEED) == emtr.cache_key(
        "2024", 2026, None, 10)
    assert emtr.cache_key("2024", 2026, None, 10, seed=1) != emtr.cache_key(
        "2024", 2026, None, 10)

    study = emtr.compute(frame, year=2026, sample=10, vintage="2024")
    other = emtr.compute(frame, year=2026, sample=10, vintage="2024", seed=1)
    assert "baseline_cached" not in other.guards
    assert set(study.households["household_id"]) != set(other.households["household_id"])
    names = sorted(p.name for p in tmp_path.glob("emtr_baseline_*.parquet"))
    assert len(names) == 2 and sum(name.endswith("_g1_ir.parquet") for name in names) == 1

    first = emtr.cached(frame, "2024", year=2026, sample=10, seed=1)
    assert first.households["household_id"].to_list() == \
        other.households["household_id"].to_list()
    study_cached = emtr.cached(frame, "2024", year=2026, sample=10)
    assert study_cached.guards.get("cached") is not True
    assert study_cached.households["household_id"].to_list() == \
        study.households["household_id"].to_list()
    again = emtr.cached(frame, "2024", year=2026, sample=10, seed=1)
    assert again.guards.get("cached") is True
    assert again.households["household_id"].to_list() == \
        first.households["household_id"].to_list()

    # A frame that differs only in a household of the other sample: its file names the
    # frame of its own sample, not the study's, and is not served (D-276).
    only = sorted(set(other.households["household_id"]) - set(study.households["household_id"]))
    changed = frame.with_columns(
        pl.when(pl.col("household_id") == only[0])
        .then(pl.col("salaire_brut_annuel") + 7.0)
        .otherwise(pl.col("salaire_brut_annuel")).alias("salaire_brut_annuel"))
    stale = emtr.cached(changed, "2024", year=2026, sample=10, seed=1)
    assert stale.guards.get("cached") is not True


def test_the_frame_fingerprint_runs_on_the_installed_polars() -> None:
    """GARDE (D-328). polars 2 a retiré trois des quatre graines de `hash_rows` : toute passe
    avec comportements tombait sur l'empreinte du cache des taux marginaux. L'empreinte
    tient toujours à chaque ligne, chaque colonne, dans l'ordre."""
    import polars as pl

    from impots.behavioural import emtr

    frame = pl.DataFrame({"a": [1, 2, 3], "b": [0.5, 1.5, 2.5]})
    print_ = emtr.fingerprint(frame)
    assert print_ == emtr.fingerprint(frame.clone())
    assert print_ != emtr.fingerprint(frame.with_columns(pl.col("a") + 1))
    assert print_ != emtr.fingerprint(frame.reverse())
    assert print_ != emtr.fingerprint(frame.rename({"b": "c"}))
