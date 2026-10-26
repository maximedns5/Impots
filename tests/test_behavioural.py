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
    # the three rows of the dividends (D-249) and their wage shift (D-252)
    assert len(open_rows) == 19
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


def _employer_case(monkeypatch, frame, run) -> dict:
    """C2's inputs off a hand-built frame and run, the SMIC at 20 000 € a year."""
    from types import SimpleNamespace

    import polars as pl

    from impots.api import main

    monkeypatch.setattr(main, "_smic_annual", lambda year: 20_000.0)
    return main._employer_inputs(
        SimpleNamespace(year=2026), pl.DataFrame(frame), pl.DataFrame(run),
        SimpleNamespace(employer_contribution_delta=-1_000.0))


def test_c2_counts_the_run_s_households_at_the_run_s_weights(monkeypatch) -> None:
    """The pass priced 1 household of the frame's 3, and weighted it for all three: 300
    against 100 in the frame. Its two earners, at 1,25 and 2 SMIC, each carry its rate,
    (99 000 − 100 000) / 100 000 = −0,01, at 300: Σ w × Δc/c = −6. Earners of the
    households the pass never priced have no rate, not a zero one; counted at 0 with the
    frame's weights they gave −2, a jobs figure diluted by the subsample (D-255)."""
    inputs = _employer_case(
        monkeypatch,
        frame={"household_id": [1, 1, 2, 3],
               "salaire_brut_annuel": [25_000.0, 40_000.0, 30_000.0, 28_000.0],
               "weight": [100.0, 100.0, 100.0, 100.0]},
        run={"household_id": [1], "weight": [300.0],
             "salaire_super_brut": [100_000.0], "salaire_super_brut_reform": [99_000.0]},
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
    100, at 300: 360 and 240, what the subsampled frame itself carries. The household's
    300 for each would count one earner a sixth too few and the other a quarter too many."""
    inputs = _employer_case(
        monkeypatch,
        frame={"household_id": [1, 1], "salaire_brut_annuel": [25_000.0, 40_000.0],
               "weight": [120.0, 80.0]},
        run={"household_id": [1], "weight": [300.0],
             "salaire_super_brut": [100_000.0], "salaire_super_brut_reform": [99_000.0]},
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
    sub = subsample(frame, 30)
    run = (sub.group_by("household_id").agg(pl.col("weight").mean())
           .with_columns(salaire_super_brut=pl.lit(100_000.0),
                         salaire_super_brut_reform=pl.lit(99_000.0)))
    inputs = _employer_case(monkeypatch, frame.to_dict(as_series=False),
                            run.to_dict(as_series=False))
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
    for reforme in reformes:
        emtr.cached(pl.DataFrame(), "2024", reform=reforme)
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
    monkeypatch.setattr(emtr, "_rate", lambda *args, **kwargs: np.zeros(1))
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
    monkeypatch.setattr(emtr, "_rate", lambda *args, **kwargs: np.zeros(1))
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

    before = json.dumps({"vintage": "2024", "year": 2026, "sample": None, "reform": None,
                         "wiring": to_openfisca.WIRING}, sort_keys=True, default=str)
    assert emtr.cache_key("2024", 2026) == hashlib.sha256(before.encode()).hexdigest()[:16]
