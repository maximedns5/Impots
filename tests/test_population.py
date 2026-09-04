"""The population pipeline (PHASE1_SPEC §7).

Runs against `tests/fixtures/eec_sample.parquet` rather than the full EEC, so CI
needs neither network access nor the 11.7 MB file. The fixture is real EEC rows
from whole dwellings, which matters: every failure mode Phase 1 uncovered came
from the shape of the real data.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots.api.schemas import ReformSpec
from impots.population import margins
from impots.population.aggregate import (
    INDIFFERENCE_EUR,
    aggregate,
    consumption_units,
    weighted_decile_index,
    weighted_quantiles,
)
from impots.population.build import SCHEMA
from impots.population.calibrate import (
    MAX_ITERATIONS,
    Margin,
    household_type,
    rake,
    standard_margins,
    with_cells,
)
from impots.population.incomes import attach_incomes, quantile_curve, sample_curve
from impots.population.runner import _pps_certainty_split, run, subsample
from impots.population.skeleton import build_skeleton
from impots.population.to_openfisca import (
    ROLE_VOCABULARY,
    WiringError,
    build_simulation,
    check_role_vocabulary,
)

FIXTURE = Path(__file__).parent / "fixtures" / "eec_sample.parquet"


@pytest.fixture(scope="module")
def population() -> pl.DataFrame:
    """The fixture population, built exactly as `impots population build` does."""
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    frame, _ = build_skeleton(children_per_household=children, source=pl.read_parquet(FIXTURE))
    frame, _ = attach_incomes(frame)
    return frame


# --------------------------------------------------------------------------- #
# the two silent-failure modes
# --------------------------------------------------------------------------- #
def test_role_vocabulary_is_what_we_think() -> None:
    """Silent-failure mode #1. If the subrole keys move, every role becomes null,
    `nbptr` goes to 0 for every foyer, and nothing raises."""
    from impots.engine.system import baseline

    check_role_vocabulary(baseline())
    for entity in baseline().entities:
        if entity.is_person:
            continue
        assert tuple(role.key for role in entity.flattened_roles) == ROLE_VOCABULARY[entity.key]


def test_wrong_roles_are_refused_rather_than_silently_dropped(population: pl.DataFrame) -> None:
    """The intuitive names — `declarant`, `parent` — match nothing and would be
    dropped without a word. They must be caught before the simulation is built."""
    from impots.engine.system import baseline

    broken = population.with_columns(pl.lit("declarant").alias("role_foyer"))
    with pytest.raises(WiringError, match="silently"):
        build_simulation(broken, baseline(), 2024)


def test_nbptr_guard_holds_over_the_population(population: pl.DataFrame) -> None:
    """No foyer may have zero parts — that is what a failed role join looks like."""
    result = run(population, 2024, tier="light")
    assert result.guards["nbptr_min"] >= 1.0


def test_no_nan_anywhere(population: pl.DataFrame) -> None:
    """Zero-income households make openfisca emit divide-by-zero RuntimeWarnings,
    which are expected noise. A NaN is not noise; it is how a wiring bug appears."""
    result = run(population, 2024, tier="full")
    assert result.guards["nan_columns"] == []
    for column in result.households.columns:
        if result.households[column].dtype.is_numeric():
            assert np.isfinite(result.households[column].to_numpy()).all(), column


# --------------------------------------------------------------------------- #
# schema and structure
# --------------------------------------------------------------------------- #
def test_population_matches_the_declared_schema(population: pl.DataFrame) -> None:
    assert set(SCHEMA) <= set(population.columns)
    typed = population.select(list(SCHEMA)).cast(SCHEMA)
    assert typed.height == population.height


def test_roles_use_the_subrole_vocabulary(population: pl.DataFrame) -> None:
    for column, entity in (("role_menage", "menage"), ("role_foyer", "foyer_fiscal"),
                           ("role_famille", "famille")):
        assert set(population[column].unique()) <= set(ROLE_VOCABULARY[entity]), column


def test_every_household_has_exactly_one_reference_person(population: pl.DataFrame) -> None:
    counts = population.group_by("household_id").agg(
        (pl.col("role_menage") == "personne_de_reference").sum().alias("n")
    )
    assert counts["n"].min() == 1
    assert counts["n"].max() == 1


def test_no_household_has_two_partners(population: pl.DataFrame) -> None:
    counts = population.group_by("household_id").agg(
        (pl.col("role_menage") == "conjoint").sum().alias("n")
    )
    assert counts["n"].max() <= 1


def test_every_foyer_has_exactly_one_principal_declarant(population: pl.DataFrame) -> None:
    counts = population.group_by("foyer_id").agg(
        (pl.col("role_foyer") == "declarant_principal").sum().alias("n")
    )
    assert set(counts["n"].unique()) == {1}


def test_parent_isole_only_where_it_can_apply(population: pl.DataFrame) -> None:
    """Case T needs one declarant and at least one dependant (D-006)."""
    claiming = (
        population.filter(pl.col("parent_isole"))
        .group_by("foyer_id")
        .agg(
            (pl.col("role_foyer") == "declarant_principal").sum().alias("declarants"),
            (pl.col("role_foyer") == "personne_a_charge").sum().alias("dependants"),
        )
    )
    if claiming.height:
        assert claiming["declarants"].max() == 1
        assert claiming["dependants"].min() >= 1


def test_synthesised_children_are_all_under_15(population: pl.DataFrame) -> None:
    """The EEC surveys the 15+ population, so everyone younger is invented and
    everyone invented is younger."""
    invented = population.filter(pl.col("synthetic"))
    if invented.height:
        assert invented["age"].max() < 15
        assert (invented["statut_activite"] == "student").all()
    assert population.filter(~pl.col("synthetic"))["age"].min() >= 15


def test_build_is_deterministic() -> None:
    """Same seed, same population — the golden aggregates are asserted to the euro."""
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    source = pl.read_parquet(FIXTURE)
    first, _ = build_skeleton(children_per_household=children, source=source)
    second, _ = build_skeleton(children_per_household=children, source=source)
    assert first.equals(second)


# --------------------------------------------------------------------------- #
# incomes
# --------------------------------------------------------------------------- #
def test_wage_curve_reproduces_published_deciles() -> None:
    """The published quantiles must come back out, or the shape is an invention.

    A single lognormal misses D1 and D9 by about 14 %; interpolating in normal-
    quantile space hits every knot."""
    deciles = margins.WAGE_DECILES_NET_EQTP_MONTHLY
    knots_z, knots_log = quantile_curve({k / 10: v for k, v in deciles.items()})
    rng = np.random.default_rng(0)
    draws = sample_curve(rng.standard_normal(400_000), knots_z, knots_log)
    for decile, published in deciles.items():
        assert np.quantile(draws, decile / 10) == pytest.approx(published, rel=0.02)


def test_wage_bill_is_calibrated(population: pl.DataFrame) -> None:
    """The one calibration on incomes, and therefore spent (§4.3)."""
    weight = population["weight"].to_numpy()
    total = float((population["salaire_brut_annuel"].to_numpy() * weight).sum())
    assert total == pytest.approx(margins.TOTAL_GROSS_WAGES.value, rel=1e-6)


def test_only_employees_earn_wages(population: pl.DataFrame) -> None:
    earners = population.filter(pl.col("salaire_brut_annuel") > 0)
    assert earners["is_salarie"].all()
    assert (earners["statut_activite"] == "employed").all()


def test_pensions_go_to_older_inactive_people_only(population: pl.DataFrame) -> None:
    from impots.population.incomes import RETIREMENT_AGE

    pensioners = population.filter(pl.col("pension_annuelle") > 0)
    if pensioners.height:
        assert pensioners["age"].min() >= RETIREMENT_AGE
        assert (pensioners["statut_activite"] == "inactive").all()


def test_only_renters_pay_rent(population: pl.DataFrame) -> None:
    paying = population.filter(pl.col("loyer_mensuel") > 0)
    assert set(paying["statut_occupation"].unique()) <= {
        "locataire_vide", "locataire_meuble", "locataire_hlm", "locataire_foyer"
    }


# --------------------------------------------------------------------------- #
# sampling and aggregation
# --------------------------------------------------------------------------- #
def test_subsample_preserves_total_weight(population: pl.DataFrame) -> None:
    """PPS selection is self-weighting. Rescaling the original weights instead —
    the obvious move — over-weights the households PPS already over-selected and
    inflated every aggregate by 2.8x before it was caught."""
    households = population["household_id"].n_unique()
    sampled = subsample(population, households // 3)
    assert sampled["household_id"].n_unique() == households // 3
    full_weight = (
        population.group_by("household_id").agg(pl.col("weight").mean())["weight"].sum()
    )
    sampled_weight = (
        sampled.group_by("household_id").agg(pl.col("weight").mean())["weight"].sum()
    )
    assert sampled_weight == pytest.approx(full_weight, rel=1e-9)


def test_subsample_is_unbiased_and_the_old_sampler_was_not() -> None:
    """The guard the total-weight check could not be, with its own kill test built in.

    `test_subsample_preserves_total_weight` holds BY CONSTRUCTION — W_certain plus
    k·(W_rest/k) is W whatever the design does — so it passed throughout the period when
    the sampler was biased. It is a comparison that cannot fail.

    The previous implementation drew with `rng.choice(replace=False, p=w)`, which is not
    PPS: numpy renormalises the remaining probabilities after each draw, so a heavy
    unit's realised inclusion probability saturates towards 1 instead of reaching
    n·w/W, and weighting every survivor at the constant W/n on top of that biases every
    total. On the real population the tell was that the error GREW with the sample: the
    pension mass, which the calibration hits exactly on the full frame, came out at
    +1.12 % at n=20 000, +2.34 % at 50 000 and +6.39 % at 100 000.

    The bias is largest for a variable CORRELATED with the weight, which is why the
    first version of this test — a heavy-tailed variable drawn independently — missed it
    at +0.34 % and had to be thrown away. `y = w` is the sharpest case and the one used
    here.

    The old sampler is reimplemented below as a NEGATIVE CONTROL. A guard that has never
    been shown to fail is a guard nobody has tested.
    """
    size, draw, reps = 200, 60, 1_500
    weights = np.exp(np.random.default_rng(0).standard_normal(size) * 1.2)
    y = weights  # perfectly correlated with the weight: the sharpest case
    truth = float((weights * y).sum())

    def new_estimate(seed: int) -> float:
        certain, sampled = _pps_certainty_split(
            weights, draw, np.random.default_rng(seed))
        rest = weights.sum() - weights[certain].sum()
        per = rest / sampled.size if sampled.size else 0.0
        return float((weights[certain] * y[certain]).sum() + per * y[sampled].sum())

    def old_estimate(seed: int) -> float:
        """`rng.choice(replace=False, p=)` plus a constant W/n weight — the defect."""
        chosen = np.random.default_rng(seed).choice(
            size, size=draw, replace=False, p=weights / weights.sum())
        return float((weights.sum() / draw) * y[chosen].sum())

    new_bias = np.mean([new_estimate(s) for s in range(reps)]) / truth - 1
    old_bias = np.mean([old_estimate(s) for s in range(reps)]) / truth - 1

    assert abs(new_bias) < 0.02, (
        f"the subsample estimates a weight-correlated total at {new_bias:+.2%} of "
        f"truth. The design is meant to be exactly unbiased — a systematic offset means "
        f"the realised inclusion probabilities are not the ones the constant weight "
        f"assumes."
    )
    assert old_bias < -0.05, (
        f"the old sampler came out at {old_bias:+.2%}, which means this test can no "
        f"longer distinguish a biased design from a sound one — fix the test, not the "
        f"assertion"
    )


def test_the_certainty_stratum_takes_units_no_design_could_reach() -> None:
    """A unit with n·w/W >= 1 cannot have that inclusion probability, because it
    exceeds one. Taking it with certainty at its own weight is the only correct move,
    and the loop must iterate: removing heavy units shrinks W and n for the rest, which
    can push further units over the line."""
    weights = np.array([500.0, 400.0, 300.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    certain, sampled = _pps_certainty_split(weights, 4, np.random.default_rng(0))
    assert set(certain.tolist()) == {0, 1, 2}, (
        "the three heavy units must be certainty units — with n=4 and W=1207, "
        "4·500/1207 is 1.66, which is not a probability")
    assert sampled.size == 1
    assert sampled[0] >= 3, "the sampled unit must come from the light remainder"

    # And with no heavy unit there is no certainty stratum at all.
    certain, sampled = _pps_certainty_split(
        np.ones(10), 4, np.random.default_rng(0))
    assert certain.size == 0 and sampled.size == 4


BUILT_POPULATION = (
    Path(__file__).resolve().parents[1] / "data" / "processed" / "population_2024.parquet"
)


@pytest.mark.slow
@pytest.mark.skipif(not BUILT_POPULATION.exists(),
                    reason="no population built — run `impots population build`")
def test_the_subsample_recovers_the_calibrated_masses() -> None:
    """The outcome check on the real frame, which is what found the defect.

    Three income masses are calibrated to hit their published target EXACTLY on the
    full frame, so any residual a subsample shows is the sampler and nothing else. That
    makes them the sharpest available probe, and it is why the reconciliation report's
    calibration lines were reading OFF TARGET.
    """
    # The REAL frame, not the small fixture: these masses are calibrated on the real
    # population and the fixture's are not, so the fixture cannot express the property.
    population = pl.read_parquet(BUILT_POPULATION)
    columns = ("pension_annuelle", "chomage_annuel", "salaire_brut_annuel")

    def mass(frame: pl.DataFrame, column: str) -> float:
        return float(frame.select((pl.col(column) * pl.col("weight")).sum()).item())

    households = population["household_id"].n_unique()
    for column in columns:
        if column not in population.columns:  # pragma: no cover - frame vintage
            continue
        truth = mass(population, column)
        errors = [
            mass(subsample(population, households // 4, seed=seed), column) / truth - 1
            for seed in range(4)
        ]
        assert abs(float(np.mean(errors))) < 0.02, (
            f"{column} comes back at {np.mean(errors):+.2%} of its full-frame mass "
            f"across four seeds. That mass is calibrated exactly, so this is the "
            f"sampler, not the model."
        )


def test_subsample_is_deterministic(population: pl.DataFrame) -> None:
    households = population["household_id"].n_unique()
    assert subsample(population, households // 2).equals(subsample(population, households // 2))


def test_subsample_returns_everything_when_asked_for_more(population: pl.DataFrame) -> None:
    assert subsample(population, 10**9).height == population.height


@pytest.mark.parametrize(
    ("adults", "children", "expected"),
    [(1, 0, 1.0), (2, 0, 1.5), (2, 2, 2.1), (3, 0, 2.0), (1, 1, 1.3), (2, 1, 1.8)],
)
def test_consumption_units(adults: int, children: int, expected: float) -> None:
    """OECD-modified: 1 for the first adult, 0.5 per further person aged 14+,
    0.3 per child under 14. Checked by hand — this scale is what makes our deciles
    comparable with Filosofi's."""
    got = consumption_units(np.array([adults]), np.array([children]))[0]
    assert got == pytest.approx(expected)


def test_weighted_quantiles_match_the_unweighted_case() -> None:
    """With equal weights this must reduce to the Hazen plotting position.

    Not to numpy's default: `weighted_quantiles` places observation *i* at
    `(i + 0.5) / n` of the cumulative weight, which is the convention weighted
    quantiles are normally defined with and which keeps the median of a symmetric
    distribution in the middle. numpy's default `linear` method places it at
    `i / (n - 1)` and disagrees at the tails — 10.9 against 10.5 at the first
    decile of 1..100. `method="hazen"` is the same convention as ours.
    """
    values = np.arange(1.0, 101.0)
    weights = np.ones(100)
    for q in (0.1, 0.25, 0.5, 0.9):
        assert weighted_quantiles(values, weights, np.array([q]))[0] == pytest.approx(
            np.quantile(values, q, method="hazen"), rel=1e-9
        )


def test_deciles_survive_a_tied_ranking_variable() -> None:
    """Value cuts collapse when many households share a value — households living
    on the same benefit land on the same euro — and a whole decile comes out
    empty. Ranking on cumulative weight always yields ten populated groups."""
    values = np.concatenate([np.zeros(600), np.arange(1.0, 401.0)])
    counts = np.bincount(weighted_decile_index(values, np.ones(values.size)), minlength=10)
    assert (counts > 0).all()
    assert counts.sum() == values.size


def test_aggregate_reports_deciles_and_totals(population: pl.DataFrame) -> None:
    agg = aggregate(run(population, 2024, tier="full").households)
    assert len(agg.deciles) == 10
    assert [row.decile for row in agg.deciles] == list(range(1, 11))
    # niveau de vie must increase across deciles: that is what a decile is
    means = [row.mean_niveau_de_vie for row in agg.deciles]
    assert means == sorted(means)
    assert agg.totals["salaire_brut"] > 0
    assert agg.counts["n_foyers"] > 0


def test_light_tier_has_no_benefit_totals(population: pl.DataFrame) -> None:
    agg = aggregate(run(population, 2024, tier="light").households)
    assert "revenu_disponible" not in agg.totals
    assert agg.deciles == []


# --------------------------------------------------------------------------- #
# reforms over a population
# --------------------------------------------------------------------------- #
def test_reform_moves_tax_and_leaves_a_delta(population: pl.DataFrame) -> None:
    """A 50 % top rate must raise money and produce losers, not winners."""
    reform = ReformSpec.model_validate(
        {"ir_bareme": [
            {"threshold": 0, "rate": 0.00}, {"threshold": 11497, "rate": 0.11},
            {"threshold": 29315, "rate": 0.30}, {"threshold": 83823, "rate": 0.41},
            {"threshold": 180294, "rate": 0.50},
        ]}
    )
    result = run(population, 2024, reform=reform, tier="full")
    agg = aggregate(result.households)
    assert agg.deltas["ir"] > 0, "a higher top rate must raise more income tax"
    assert agg.deltas["revenu_disponible"] < 0
    # nobody gains from a rise in the top rate alone
    for row in agg.deciles:
        assert row.share_winners == 0.0
        assert row.share_losers >= 0.0
    assert agg.deciles[-1].share_losers >= agg.deciles[0].share_losers


def test_empty_reform_produces_no_delta(population: pl.DataFrame) -> None:
    result = run(population, 2024, reform=ReformSpec(), tier="light")
    assert not any(column.endswith("_reform") for column in result.households.columns)


def test_indifference_band_is_applied(population: pl.DataFrame) -> None:
    """A household moved by less than 10 EUR a year counts as unaffected: below
    that the answer is dominated by rounding and by the arbitrariness of a
    synthetic income."""
    reform = ReformSpec.model_validate({"decote_seuil_celib": 900.0})
    agg = aggregate(run(population, 2024, reform=reform, tier="full").households)
    for row in agg.deciles:
        assert row.share_winners + row.share_losers + row.share_unaffected == pytest.approx(1.0)
    assert INDIFFERENCE_EUR == 10.0


# --------------------------------------------------------------------------- #
# raking (D-017)
# --------------------------------------------------------------------------- #
def test_raking_converges_and_hits_its_margins() -> None:
    """A synthetic frame deliberately off its margins must be brought onto them."""
    rng = np.random.default_rng(0)
    n = 600
    frame = pl.DataFrame({
        "household_id": [f"h{i}" for i in range(n)],
        "weight": rng.uniform(50, 500, n),
        "hh_type": ["a"] * 400 + ["b"] * 200,
        "age_sex": ["x_male"] * 300 + ["x_female"] * 300,
    })
    margin = Margin("t", "household", "hh_type", {"a": 100_000.0, "b": 100_000.0})
    raked, diagnostics = rake(frame, [margin])

    assert diagnostics.converged
    assert diagnostics.iterations <= MAX_ITERATIONS
    totals = raked.group_by("hh_type").agg(pl.col("weight").sum())
    for row in totals.iter_rows():
        assert row[1] == pytest.approx(100_000.0, rel=1e-6)
    assert max(diagnostics.fit_after.values()) < 1e-6


def test_raking_respects_the_weight_ratio_bounds() -> None:
    """An unreachable margin must be clipped, not chased.

    Unbounded raking will happily hand one household a weight of 40 000 to close a
    margin, and that household then dominates every aggregate it appears in.
    """
    frame = pl.DataFrame({
        "household_id": ["h0", "h1"],
        "weight": [100.0, 100.0],
        "hh_type": ["a", "b"],
    })
    # 'a' is asked for 50x its weight; the bound allows 5x.
    margin = Margin("t", "household", "hh_type", {"a": 5_000.0, "b": 100.0})
    raked, diagnostics = rake(frame, [margin], bounds=(0.2, 5.0))

    ratios = raked["weight"].to_numpy() / 100.0
    assert ratios.max() <= 5.0 + 1e-9
    assert ratios.min() >= 0.2 - 1e-9
    assert diagnostics.clipped_households >= 1
    # and the miss is reported rather than hidden
    assert diagnostics.fit_after["t"] > 0.5


def test_raking_keeps_one_weight_per_household() -> None:
    """Every member of a household is scaled by the same factor.

    Letting members of one household drift apart would break every household-level
    aggregate downstream — which is the whole reason the adjustment for a
    person-level margin is averaged over the household in the first place.
    """
    frame = pl.DataFrame({
        "household_id": ["h0", "h0", "h0", "h1", "h1"],
        "weight": [10.0, 10.0, 10.0, 20.0, 20.0],
        "hh_type": ["a", "a", "a", "b", "b"],
    })
    raked, _ = rake(frame, [Margin("t", "household", "hh_type", {"a": 60.0, "b": 20.0})])
    for household in ("h0", "h1"):
        weights = raked.filter(pl.col("household_id") == household)["weight"].to_numpy()
        assert np.allclose(weights, weights[0])


def test_person_level_margin_moves_the_right_direction() -> None:
    """A household spanning several cells takes the mean of their factors."""
    frame = pl.DataFrame({
        "household_id": ["h0", "h0", "h1", "h1"],
        "weight": [100.0, 100.0, 100.0, 100.0],
        "age_sex": ["young_male", "young_male", "old_female", "old_female"],
    })
    targets = {"young_male": 400.0, "old_female": 100.0}
    raked, diagnostics = rake(frame, [Margin("a", "person", "age_sex", targets)])
    young = raked.filter(pl.col("age_sex") == "young_male")["weight"].to_numpy()
    old = raked.filter(pl.col("age_sex") == "old_female")["weight"].to_numpy()
    assert young[0] > 100.0, "an under-represented cell must be scaled up"
    assert old[0] < 100.0, "an over-represented cell must be scaled down"
    assert diagnostics.fit_after["a"] < 1e-6


def test_raking_needs_a_margin() -> None:
    with pytest.raises(ValueError, match="at least one margin"):
        rake(pl.DataFrame({"household_id": ["h0"], "weight": [1.0]}), [])


def test_household_typology_matches_insee_categories(population: pl.DataFrame) -> None:
    """Derived from entity roles, not from the EEC's TYPLOG5, so the same margin
    survives the move to ERFS (D-016)."""
    typed = household_type(population)
    assert set(typed["hh_type"].unique()) <= set(margins.HOUSEHOLDS_BY_TYPE)
    counts = typed.group_by("household_id").agg(pl.col("hh_type").n_unique().alias("n"))
    assert counts["n"].max() == 1, "a household has exactly one type"


def test_an_adult_child_at_home_is_not_a_complex_household() -> None:
    """INSEE counts a child of the family at any age; our tax roles stop at
    rattachement age. Conflating the two put 2.6 M households in 'complexe'
    against a census 1.1 M."""
    frame = pl.DataFrame({
        "household_id": ["h"] * 3,
        "weight": [1.0] * 3,
        "age": [58, 56, 30],
        "role_menage": ["personne_de_reference", "conjoint", "autre"],
    })
    assert household_type(frame)["hh_type"][0] == "couple_avec_enfant"


def test_a_lodger_of_similar_age_is_a_complex_household() -> None:
    frame = pl.DataFrame({
        "household_id": ["h"] * 3,
        "weight": [1.0] * 3,
        "age": [58, 56, 61],
        "role_menage": ["personne_de_reference", "conjoint", "autre"],
    })
    assert household_type(frame)["hh_type"][0] == "complexe"


def test_standard_margins_hold_age_sex_as_a_drift_constraint(population: pl.DataFrame) -> None:
    """Its targets are the population's own 15+ totals, because EXTRIAN is already
    calibrated on sex and age: the instruction is 'do not move these'."""
    framed = with_cells(population)
    margin_list = standard_margins(framed)
    names = {margin.name for margin in margin_list}
    assert names == {"household_type", "age_sex"}

    age_sex = next(m for m in margin_list if m.name == "age_sex")
    assert all(not cell.startswith("under_15") for cell in age_sex.targets), (
        "synthesised children were never in EXTRIAN's calibration and must not be pinned"
    )
    weight = framed["weight"].to_numpy()
    cells = framed["age_sex"].to_numpy()
    for cell, target in age_sex.targets.items():
        assert float(weight[cells == cell].sum()) == pytest.approx(target, rel=1e-12)


def test_household_margins_sum_to_the_published_total() -> None:
    """Raking to components that do not add up to their own total makes IPF chase a
    contradiction it can never close."""
    assert sum(margins.HOUSEHOLDS_BY_TYPE.values()) == pytest.approx(
        margins.HOUSEHOLDS.value, abs=1.0
    )


def test_a_margin_the_model_is_fitted_to_is_marked_spent() -> None:
    """D-014's rule, enforced rather than remembered: the household count became a
    calibration target the moment raking started aiming at it, and presenting it as
    validation would be claiming credit for hitting what we tuned to."""
    assert margins.HOUSEHOLDS.use == "calibration"
    assert margins.TOTAL_GROSS_WAGES.use == "calibration"
    assert margins.IR_BAREME_ON_2024_INCOME.use == "validation"


# --------------------------------------------------------------------------- #
# The public cost has two sides (D-039)
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_an_employer_contribution_reform_has_a_cost_at_all() -> None:
    """Found while building the behavioural layer, and it was a mechanical bug.

    `reform_cost` was Δ household disposable income alone. An employer-contribution
    reform changes what the state COLLECTS without moving disposable income — the
    gain lands on the firm — so extending the réduction générale from 1.6 to 2 SMIC
    reported a cost of exactly **zero** while cutting labour cost by 17.7 bn.

    Note which quantity is used: `cotisations_employeur` is gross of the allègements
    and does not move when one changes, so the delta comes from
    Δ(salaire_super_brut − salaire_brut), which is what is actually paid.
    """
    import polars as pl

    from impots.api.schemas import ReformSpec
    from impots.population.build import PROCESSED
    from impots.population.runner import run as population_run

    population = PROCESSED / "population_2024.parquet"
    if not population.exists():
        pytest.skip("no population built in this checkout")

    result = population_run(
        pl.read_parquet(population), year=2024,
        reform=ReformSpec.model_validate({"allegement_general_plafond": 2.0}),
        tier="full", sample=20_000,
    )
    from impots.population import aggregate as aggregate_module

    aggregates = aggregate_module.aggregate(result.households)

    assert aggregates.employer_contribution_delta < -1e9, (
        "extending the réduction générale must reduce employer contributions paid"
    )
    assert aggregates.reform_cost is not None and aggregates.reform_cost > 1e9, (
        "a reform that cuts labour cost by billions cannot cost the state nothing"
    )
    assert aggregates.reform_cost == pytest.approx(
        -aggregates.employer_contribution_delta, rel=0.05
    ), "with disposable income unmoved, the cost IS the contribution loss"
    # The bug hid because the gross measure genuinely does not move.
    assert abs(aggregates.deltas.get("cotisations_employeur", 0.0)) < 1e6


@pytest.mark.slow
def test_a_household_reform_is_unaffected_by_the_employer_term() -> None:
    """The correction must not move any number it has no business moving: an income
    tax reform touches no employer contribution, so its cost is what it always was."""
    import polars as pl

    from impots.api.schemas import ReformSpec
    from impots.population.build import PROCESSED
    from impots.population.runner import run as population_run

    population = PROCESSED / "population_2024.parquet"
    if not population.exists():
        pytest.skip("no population built in this checkout")

    result = population_run(
        pl.read_parquet(population), year=2024,
        reform=ReformSpec.model_validate({"plafond_qf_demi_part": 1000.0}),
        tier="full", sample=20_000,
    )
    from impots.population import aggregate as aggregate_module

    aggregates = aggregate_module.aggregate(result.households)
    assert aggregates.employer_contribution_delta == pytest.approx(0.0, abs=1e6)
    assert aggregates.reform_cost == pytest.approx(
        aggregates.deltas["revenu_disponible"], rel=1e-9
    )


# --------------------------------------------------------------------------- #
# Double entry (D-045)
# --------------------------------------------------------------------------- #
def test_the_identity_kills_the_seventeen_billion_bug() -> None:
    """The regression test the guard exists for.

    Before D-039, `reform_cost` was Δ household disposable income alone, so extending
    the réduction générale reported a public cost of exactly zero while moving 17.7 bn
    of labour cost. Re-express that here by feeding the guard the old, household-only
    cost: it must refuse.
    """
    from impots.guards import SectorBalanceError, sector_balance

    # As measured: households unmoved, employers paying 17.68 bn less.
    deltas = {"revenu_disponible": 0.0, "ir": 0.0, "salaire_super_brut": -17.68e9}
    employer_delta = -17.68e9

    # Today's cost passes.
    balance = sector_balance(deltas, reform_cost=17.68e9,
                             employer_contribution_delta=employer_delta)
    assert balance["unexplained"] == pytest.approx(0.0, abs=1e6)

    # The pre-D-039 cost does not.
    with pytest.raises(SectorBalanceError, match="coût annoncé"):
        sector_balance(deltas, reform_cost=0.0,
                       employer_contribution_delta=employer_delta)


def test_the_identity_is_surgical_about_which_reforms_it_refuses() -> None:
    """A guard that fired on everything would be noise. An income-tax reform has no
    employer term, so the household-only cost was always right for it and must still
    pass — the guard refuses the omission, not the shape."""
    from impots.guards import sector_balance

    deltas = {"revenu_disponible": -0.662e9, "ir": 0.662e9}
    balance = sector_balance(deltas, reform_cost=-0.662e9, employer_contribution_delta=0.0)
    assert balance["unexplained"] == pytest.approx(0.0, abs=1e6)


def test_the_identity_tolerates_only_unreported_benefit_leakage() -> None:
    """The floor is 0.1 %, set from a measurement rather than a preference: a 10.4 bn
    CSG reform leaks 0.066 % through family benefits and minima that have no row of
    their own. Twice that leakage must still pass; a hundred times it must not."""
    from impots.guards import SectorBalanceError, sector_balance

    deltas = {"revenu_disponible": -10.4451e9, "csg_imposable": 10.8194e9,
              "ppa": 0.3531e9, "rsa": 0.0072e9, "af": 0.0067e9}
    sector_balance(deltas, reform_cost=-10.4451e9)  # 0.066 %: passes

    deltas_worse = dict(deltas, revenu_disponible=-9.4e9)
    with pytest.raises(SectorBalanceError):
        sector_balance(deltas_worse, reform_cost=-9.4e9)


@pytest.mark.skipif(
    not (Path(__file__).resolve().parents[1] / "data" / "processed"
         / "population_2024.parquet").exists(),
    reason="no population built in this checkout",
)
@pytest.mark.slow
def test_every_reform_shape_balances_on_the_real_population() -> None:
    """Four reforms across three instrument families, on the real population. The
    guard runs inside `aggregate`, so this asserts it did not raise and that the
    reconstituted cost is the reported one."""
    import polars as pl

    from impots.api.schemas import ReformSpec
    from impots.population import aggregate as aggregate_module
    from impots.population.build import PROCESSED
    from impots.population.runner import run as population_run

    frame = pl.read_parquet(PROCESSED / "population_2024.parquet")
    for reform in (
        {"plafond_qf_demi_part": 1000.0},
        {"decote_taux": 0.50},
        {"csg_activite_imposable": 0.034},
        {"allegement_general_plafond": 2.0},
    ):
        aggregates = aggregate_module.aggregate(
            population_run(frame, year=2024, reform=ReformSpec.model_validate(reform),
                           tier="full", sample=20_000).households
        )
        assert aggregates.balance, reform
        assert aggregates.balance["reform_cost"] == pytest.approx(
            aggregates.balance["expected_cost"],
            rel=1e-3, abs=5e6,
        ), reform
