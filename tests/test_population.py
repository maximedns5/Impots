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
from impots.population.incomes import attach_incomes, quantile_curve, sample_curve
from impots.population.runner import run, subsample
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
