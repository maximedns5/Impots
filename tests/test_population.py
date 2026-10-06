"""The population pipeline (PHASE1_SPEC §7).

Runs against `tests/fixtures/eec_sample.parquet` rather than the full EEC, so CI
needs neither network access nor the 11.7 MB file. The fixture is real EEC rows
from whole dwellings, which matters: every failure mode Phase 1 uncovered came
from the shape of the real data.
"""

from __future__ import annotations

import functools
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest

from impots.api.schemas import HouseholdInput, ReformSpec
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
    RakeDiagnostics,
    RakingRefused,
    check_rake_result,
    household_type,
    rake,
    standard_margins,
    with_cells,
)
from impots.population.incomes import (
    IncomeScaleError,
    attach_incomes,
    household_share_of_france,
    quantile_curve,
    sample_curve,
)
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
    """The fixture population, built as `impots population build` does at 1/500 scale.

    Not *exactly* as `build` does, and the difference is the point. `build` runs on
    the full EEC, whose weights are the country, so it hands `attach_incomes` the
    national wage bill and every household gets a plausible share of it. This frame
    is 400 dwellings weighting to 0.20 % of France, and the same national target
    divided among them made the poorest earner in the test population a millionaire
    (D-149). The targets are scaled to what the frame actually represents.

    Raking is skipped here for a related reason: the household-type margin is an
    absolute published count, unreachable from 400 dwellings, and the build gate
    now refuses the result rather than accepting a fixed point that meets no margin
    (D-150, `test_raking_can_converge_on_a_margin_it_never_reaches`).
    """
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    frame, _ = build_skeleton(children_per_household=children, source=pl.read_parquet(FIXTURE))
    frame, _ = attach_incomes(frame, targets_scale=household_share_of_france(frame))
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


DECLARANT_ROLES = ("declarant_principal", "conjoint")


def test_parent_isole_only_where_it_can_apply(population: pl.DataFrame) -> None:
    """Case T needs one declarant and at least one dependant (D-006).

    One declarant over BOTH declarant roles. A foyer with a `conjoint` is a married or
    PACSed couple, which art. 194, II CGI does not reach, and counting the principal
    declarant alone let 84 of the fixture's couples claim it (D-193, D-195)."""
    claiming = (
        population.filter(pl.col("parent_isole"))
        .group_by("foyer_id")
        .agg(
            pl.col("role_foyer").is_in(DECLARANT_ROLES).sum().alias("declarants"),
            (pl.col("role_foyer") == "personne_a_charge").sum().alias("dependants"),
        )
    )
    assert claiming.height, "no foyer claims case T: the check below would pass on nothing"
    assert (claiming["declarants"] == 1).all(), claiming.filter(pl.col("declarants") != 1)
    assert claiming["dependants"].min() >= 1


def _reference_foyers(population: pl.DataFrame) -> pl.DataFrame:
    """Each reference person's foyer, beside what the survey row says of that person.

    The couple flags come from the EEC, not from the skeleton: `COUPL_LOG` is « En
    couple avec quelqu'un vivant dans le logement », asked of everyone aged 15 or over,
    and `TYPLOG5` types the dwelling (3 and 4 hold a couple). The reference person is
    the lowest `NOI` of the dwelling-quarter (D-013), and the drawn age is checked
    against that row's band, so a broken pairing fails here instead of comparing
    someone else's flag.
    """
    from impots.population.skeleton import AGE_BANDS

    rows = (
        pl.read_parquet(FIXTURE).sort(["IDENT", "TRIM", "NOI"])
        .group_by(["IDENT", "TRIM"], maintain_order=True).first()
        .select(
            pl.concat_str([pl.col("IDENT"), pl.lit("-"), pl.col("TRIM")]).alias("household_id"),
            (pl.col("COUPL_LOG") == "1").alias("in_a_couple"),
            pl.col("TYPLOG5").is_in(["3", "4"]).alias("couple_dwelling"),
            pl.col("AGE6"),
        )
    )
    foyers = population.group_by("foyer_id").agg(
        pl.col("role_foyer").is_in(DECLARANT_ROLES).sum().alias("declarants"),
        (pl.col("role_foyer") == "personne_a_charge").sum().alias("dependants"),
        pl.col("parent_isole").first(),
    )
    references = population.filter(pl.col("role_menage") == "personne_de_reference")
    frame = (
        references.select(["household_id", "foyer_id", "age"])
        .join(rows, on="household_id", how="inner")
        .join(foyers, on="foyer_id", how="inner")
    )
    assert frame.height == references.height == rows.height
    for code, age in frame.select(["AGE6", "age"]).iter_rows():
        low, high = AGE_BANDS[code]
        assert low <= age <= high, (code, age)
    return frame


def test_no_case_t_for_a_declarant_living_in_a_couple(population: pl.DataFrame) -> None:
    """Living in a couple is not living alone, married or not (D-195).

    Art. 194, II CGI gives the half-part to « contribuables célibataires ou divorcés qui
    vivent seuls ». Living alone means « qu'il ne vive pas en couple » (CE, 15 avril
    2016, n° 375682), and « Le contribuable ne doit donc pas vivre en concubinage »
    (BOI-IR-LIQ-10-20-20-10, § 160). Where the skeleton cannot pair a partner — absent
    from the file, or one of more than two coupled persons — the reference person
    declares alone, and claimed case T beside that partner. Read where both signals say
    couple, the person's flag and the dwelling's type, as the skeleton pairs partners.
    """
    frame = _reference_foyers(population).filter(
        pl.col("in_a_couple") & pl.col("couple_dwelling"))
    unpaired = frame.filter((pl.col("declarants") == 1) & (pl.col("dependants") > 0))
    assert unpaired.height, "no unpaired partner with a dependant: the test would be vacuous"
    assert not frame["parent_isole"].any(), frame.filter(pl.col("parent_isole"))


def test_case_t_wherever_a_lone_declarant_lives_alone_with_a_dependant(
    population: pl.DataFrame,
) -> None:
    """The other half: sharing the dwelling is not living in a couple (D-195).

    « la simple cohabitation de deux personnes [...] ne suffit pas à caractériser le
    concubinage » (BOI-IR-LIQ-10-20-20-10, § 170), and an unrelated adult at the same
    address does not establish it either (CE, 15 avril 2016, n° 375682). A parent who
    shares the dwelling with an adult child, a grandparent or a flatmate keeps case T.
    """
    frame = _reference_foyers(population).filter(
        ~pl.col("in_a_couple") & (pl.col("declarants") == 1) & (pl.col("dependants") > 0)
    )
    assert frame.height, "no lone declarant with a dependant: the test would be vacuous"
    assert frame["parent_isole"].all(), frame.filter(~pl.col("parent_isole"))
    parents = frame.select("household_id", pl.col("foyer_id").alias("parent_foyer"))
    sharing = population.join(parents, on="household_id").filter(
        pl.col("foyer_id") != pl.col("parent_foyer"))
    assert sharing.height, "no parent shares the dwelling: an over-broad rule would go unseen"


#: One hand-made dwelling per shape: TYPLOG5, then (NOI, AGE6, ACTEU, COUPL_LOG) per
#: person, then whether art. 194, II reaches its reference person. The children are
#: 15 to 24 and inactive, hence dependants; no under-15 is synthesised.
CASE_T_SHAPES: dict[str, tuple[str, list[tuple[str, str, str, str]], bool]] = {
    "SEUL0001": ("2", [("01", "25", "1", "2"), ("02", "15", "3", "2")], True),
    # an adult child at home, aged 25 to 49 and in work: a foyer of their own
    "FAMILLE1": ("2", [("01", "50", "1", "2"), ("02", "15", "3", "2"),
                       ("03", "25", "1", "2")], True),
    # the same parent beside a couple, her son and his partner: a couple in the
    # dwelling that is not hers
    "FAMILLE2": ("2", [("01", "50", "1", "2"), ("02", "15", "3", "2"),
                       ("03", "25", "1", "1"), ("04", "25", "1", "1")], True),
    # a mother and her child beside her brother's couple, in a dwelling typed as a
    # couple: the couple is not hers either
    "FAMILLE3": ("4", [("01", "25", "1", "2"), ("02", "15", "3", "2"),
                       ("03", "25", "1", "1"), ("04", "25", "1", "1")], True),
    "COUPLE01": ("4", [("01", "25", "1", "1"), ("02", "25", "1", "1"),
                       ("03", "15", "3", "2")], False),
    # the partner is not in the file: the reference alone says « en couple »
    "ABSENT01": ("4", [("01", "25", "1", "1"), ("03", "15", "3", "2")], False),
    # two couples: four coupled persons, so no pair is resolved
    "DEUXCPL1": ("4", [("01", "50", "1", "1"), ("02", "50", "1", "1"),
                       ("03", "15", "3", "2"), ("04", "25", "1", "1"),
                       ("05", "25", "1", "1")], False),
    # the survey's two signals disagree: a « famille monoparentale » whose reference
    # says « en couple ». Case T is left as main had it, the owner's call (D-195)
    "CONFLIT1": ("2", [("01", "25", "1", "1"), ("02", "15", "3", "2")], True),
}


def _eec_rows(shapes: dict[str, tuple[str, list[tuple[str, str, str, str]], bool]]
              ) -> pl.DataFrame:
    """EEC rows for `CASE_T_SHAPES`, typed as the fixture's columns are."""
    source = pl.read_parquet(FIXTURE)
    rows = []
    for ident, (typlog, persons, _) in shapes.items():
        for noi, age6, acteu, couple in persons:
            working = acteu == "1"
            rows.append({
                "IDENT": ident, "TRIM": "1", "NOI": noi, "EXTRIAN": 1_000.0,
                "AGE6": age6, "SEXE": "2", "ACTEU": acteu, "TYPLOG5": typlog,
                "COUPL_LOG": couple, "SO": "4", "METRODOM": "1", "STCOMM2020": "C",
                "STATUT": "2" if working else None, "PCS1Q": "51" if working else None,
                "PUB3FP": "4" if working else None, "TPPRED": "1" if working else None,
                "TXTPPRED": None,
            })
    columns = list(rows[0])
    return pl.DataFrame(rows, schema={column: source.schema[column] for column in columns})


def test_case_t_follows_the_couple_not_the_dwelling() -> None:
    """Eight dwellings, the answer written beside each (D-195).

    The fixture holds unpaired partners of one shape only, absent from the file. Two
    couples in one dwelling — the residue the module docstring names — is the other.
    A parent beside an adult child, that child's couple or a brother's couple is the
    shape an over-broad rule would hit. The last is not the law's answer but the
    owner's pending one, pinned so that changing it is a decision.
    """
    frame, _ = build_skeleton(children_per_household=None, source=_eec_rows(CASE_T_SHAPES))
    unit = frame.filter(pl.col("foyer_id").str.ends_with("#0")).group_by("household_id").agg(
        pl.col("role_foyer").is_in(DECLARANT_ROLES).sum().alias("declarants"),
        (pl.col("role_foyer") == "personne_a_charge").sum().alias("dependants"),
        pl.col("parent_isole").first(),
    )
    shapes = {household.split("-")[0]: row for household, *row in unit.iter_rows()}
    # the shapes are what the table says they are, or the answers below prove nothing
    assert set(shapes) == set(CASE_T_SHAPES)
    assert all(dependants >= 1 for _, dependants, _ in shapes.values())
    assert {ident for ident, (declarants, _, _) in shapes.items() if declarants == 2} == {
        "COUPLE01"}
    assert {ident: claimed for ident, (_, _, claimed) in shapes.items()} == {
        ident: expected for ident, (_, _, expected) in CASE_T_SHAPES.items()}


def test_two_declarants_never_claim_case_t_whatever_the_couple_flag_says() -> None:
    """A conjoint is a second declarant, and art. 194, II reaches only « célibataires ou
    divorcés »: no case T for the foyer, with or without a couple flag (D-195).

    Every partner the skeleton pairs today is flagged « en couple », so the couple test
    alone would exclude the pair, and `build_skeleton` cannot tell the two rules apart.
    The role assignment is called directly here, on a pair the survey does not flag.
    """
    from impots.population.skeleton import _assign_units

    people = pl.DataFrame(
        {
            "household_id": ["H-1", "H-1", "H-1"],
            "noi": ["01", "02", "03"],
            "is_reference": [True, False, False],
            "is_conjoint": [False, True, False],
            "is_child": [False, False, True],
            "is_extra": [False, False, False],
            "couple_flag": [None, None, "2"],
            "hh_type": ["4", "4", "4"],
        },
        schema_overrides={"couple_flag": pl.String},
    )
    frame = _assign_units(people)
    assert frame["foyer_id"].n_unique() == 1
    assert frame["role_foyer"].to_list() == [
        "declarant_principal", "conjoint", "personne_a_charge"]
    assert not frame["parent_isole"].any()


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
    """The one calibration on incomes, and therefore spent (§4.3).

    The target is the national wage bill scaled to the share of France this frame
    represents. On the full EEC that scale is 1.0 and this is the national figure.
    """
    weight = population["weight"].to_numpy()
    total = float((population["salaire_brut_annuel"].to_numpy() * weight).sum())
    share = household_share_of_france(population)
    assert total == pytest.approx(margins.TOTAL_GROSS_WAGES.value * share, rel=1e-6)


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


# --- D-093: the identity near a root ------------------------------------------------


def test_an_offsetting_reform_is_not_accused_of_an_imbalance() -> None:
    """The regression F2's solver found. Fails if the gross allowance is removed.

    Measured, at the third evaluation of `impots scenario solve csg_activite_imposable
    --on rsa_700`: prélèvements +3.726 bn, transferts +3.673 bn, cost -52.9 M, and an
    unexplained 305 719 EUR that is the RSA arm's leakage — the same 305 000 EUR the
    RSA reform carries on its own, where it is 0.009 % and passes. It does not shrink
    because a second arm cancels the headline; only the denominator does.
    """
    from impots.guards import sector_balance

    deltas = {"csg_imposable": 3.726241248e9, "rsa": 3.673019346e9}
    balance = sector_balance(deltas, reform_cost=-52.916184e6)
    assert balance["unexplained"] == pytest.approx(305.7e3, rel=0.05)


def test_a_sector_that_moved_without_entering_the_cost_is_caught_at_a_zero_net() -> None:
    """THE kill test for the fix: the allowance must not be a licence.

    Same offsetting shape, same near-zero net, but a whole billion of transfers left out
    of the reported cost. Fails if the gross allowance is set loose enough to swallow a
    real omission — which is the only way this fix could be wrong.
    """
    from impots.guards import SectorBalanceError, sector_balance

    deltas = {"csg_imposable": 3.726241248e9, "rsa": 3.673019346e9}
    with pytest.raises(SectorBalanceError, match="du brut"):
        sector_balance(deltas, reform_cost=-52.916184e6 + 1.0e9)


def test_the_gross_allowance_is_tighter_than_the_net_one() -> None:
    """It is a SECOND allowance, not a replacement. Fails if someone raises
    BALANCE_GROSS_RTOL above BALANCE_RTOL, which would silently relax every reform the
    net test used to judge — since gross is never smaller than net."""
    from impots.guards import BALANCE_GROSS_RTOL, BALANCE_RTOL

    assert BALANCE_GROSS_RTOL < BALANCE_RTOL


def test_both_gross_allowances_are_pinned_to_their_measurements() -> None:
    """Fails on ANY change to either constant, which is the point.

    The first version asserted only `gross < net`, so 9.9e-4 — tripling the household
    guard's real tolerance — left the whole suite green. A tolerance that can be widened
    without a test noticing is a tolerance nobody is defending.

    Household 3e-4: 3.5x the worst ratio measured over five reforms (8.55e-05, the RSA
    arm's leakage through unreported instruments). Firm 1e-6: ~18x the worst measured
    over four firm reforms (5.43e-08, which is float accumulation and nothing else,
    because the firm identity sanctions no leakage). Both tables are in D-093. Changing
    either means re-measuring and rewriting that decision, not editing a number.
    """
    from impots.guards import BALANCE_GROSS_RTOL, FIRM_BALANCE_GROSS_RTOL

    assert BALANCE_GROSS_RTOL == 3e-4
    assert FIRM_BALANCE_GROSS_RTOL == 1e-6
    assert FIRM_BALANCE_GROSS_RTOL < BALANCE_GROSS_RTOL


def test_gross_sums_the_movements_not_the_buckets() -> None:
    """THE bug in the first version of the D-093 fix, found by adversarial review.

    `abs(receipts) + abs(transfers)` sums each BUCKET first, so a reform whose two arms
    sit in the same bucket — RSA up, AF down, both transfers — has them cancel before the
    abs() runs. It read 3.0 M against a true movement of 7.34 bn: 0.04 % of the truth,
    and the guard refused a correct run at "10 % of gross". The fix agreed with the one
    shape it had been tested on and failed the shape it was written for.

    Fails if the bucket form comes back.
    """
    from impots.guards import sector_balance

    # Both arms in STATE_TRANSFERS, netting to 3 M on 7.34 bn of movement, plus the same
    # 305 719 EUR leakage the CSG-financed run carries.
    deltas = {"rsa": 3.673019346e9, "af": -3.670e9}
    balance = sector_balance(deltas, reform_cost=3.019346e6 + 305_719)
    assert balance["unexplained"] == pytest.approx(305_719, rel=0.01)


def test_an_omission_is_caught_when_both_arms_share_a_bucket() -> None:
    """The kill test for the test above: the corrected gross must not be a licence."""
    from impots.guards import SectorBalanceError, sector_balance

    deltas = {"rsa": 3.673019346e9, "af": -3.670e9}
    with pytest.raises(SectorBalanceError):
        sector_balance(deltas, reform_cost=3.019346e6 + 1.0e9)


def test_the_firm_guard_does_not_buy_allowance_with_movement_it_cannot_see() -> None:
    """The firm residual measures movement OUTSIDE FIRM_COMPONENTS, so scaling it by
    movement INSIDE them buys indulgence against exactly what it cannot detect.

    With the household constant (3e-4) a 40 bn offsetting firm reform bought 12 M EUR of
    allowance and swallowed a genuine 5 M EUR instrument leaking outside the perimeter —
    which the old net-scaled guard caught. Fails if FIRM_BALANCE_GROSS_RTOL is raised to
    the household value.
    """
    from impots.guards import SectorBalanceError, firm_balance

    deltas = {"impot_societes": -20.0e9, "cvae": 20.0e9}
    with pytest.raises(SectorBalanceError):
        firm_balance(deltas, reform_cost=-5.0e6)
    # And the measured float noise on that same reform still passes: 5.43e-08 x 40 bn.
    firm_balance(deltas, reform_cost=-2_172.0)


def test_the_original_failure_still_breaches_under_the_gross_scale() -> None:
    """The 17.7 bn labour-cost reform whose public cost read zero. Fails if the gross
    allowance is what lets it through — the whole point is that it cannot."""
    from impots.guards import SectorBalanceError, sector_balance

    deltas = {"revenu_disponible": 0.0, "ir": 0.0, "salaire_super_brut": -17.68e9}
    with pytest.raises(SectorBalanceError, match="coût annoncé"):
        sector_balance(deltas, reform_cost=0.0, employer_contribution_delta=-17.68e9)


def test_the_firm_identity_carries_its_own_allowance_not_the_household_one() -> None:
    """A firm reform that raises one instrument to pay for cutting another has a
    near-zero net and billions of gross, exactly like the household case — so it needs a
    gross allowance too. But a much SMALLER one, and the reason is what each side
    tolerates rather than a preference.

    The household identity sanctions leakage: `revenu_disponible` runs through a cascade
    wider than the reported instruments, measured at up to 8.55e-05 of gross. The firm
    identity sanctions none: FIRM_COMPONENTS is a second independent route to the same
    OpenFisca total, so an instrument in one and not the other IS the bug. Measured, the
    firm residual is 5.43e-08 of gross — float accumulation, four orders smaller.

    This case is exactly neutral (net zero, 8 bn of gross), so the gross allowance of
    8 000 EUR is what binds, not the floor-derived net allowance of 5 000.
    """
    from impots.guards import SectorBalanceError, firm_balance

    deltas = {"impot_societes": -4.0e9, "cvae": 4.0e9}
    firm_balance(deltas, reform_cost=6_000.0)  # float noise on 8 bn: passes
    with pytest.raises(SectorBalanceError):
        firm_balance(deltas, reform_cost=500e3)  # half a million: does not
# --------------------------------------------------------------------------- #
# what a population-scale check is worth if it cannot fail (D-149, D-150)
# --------------------------------------------------------------------------- #
def _skeleton() -> pl.DataFrame:
    """The fixture skeleton, before any income is attached."""
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    frame, _ = build_skeleton(children_per_household=children, source=pl.read_parquet(FIXTURE))
    return frame


def test_a_sample_cannot_silently_carry_the_national_wage_bill() -> None:
    """The kill test for D-149.

    `attach_incomes` divides a published national total among whatever weights it
    is handed. Handed 0.2 % of France, it used to make 0.2 % of France rich, and
    said nothing.
    """
    with pytest.raises(IncomeScaleError, match=re.escape("0.20%")):
        attach_incomes(_skeleton())


def test_the_country_itself_is_never_refused() -> None:
    """The other half: the refusal must not fire on the frame `build` actually uses.

    The full EEC weights to within a percent of the published household count. This
    stands in for it by inflating the fixture's weights onto that count — the same
    shape, at the country's size — and asserts both that it passes and that it gets
    the national target rather than a scaled one.
    """
    frame = _skeleton()
    frame = frame.with_columns(
        pl.col("weight") / household_share_of_france(frame)
    )
    assert household_share_of_france(frame) == pytest.approx(1.0, rel=1e-9)

    scaled, stats = attach_incomes(frame)
    assert stats.targets_scale == 1.0
    weighted = float(
        (scaled["salaire_brut_annuel"].to_numpy() * scaled["weight"].to_numpy()).sum()
    )
    assert weighted == pytest.approx(margins.TOTAL_GROSS_WAGES.value, rel=1e-6)


def test_the_unscaled_sample_is_kept_as_the_defect_it_was() -> None:
    """What shipped until D-149, reproduced on demand and pinned.

    Every earner a millionaire, which is not a curiosity: it moves the whole test
    population into one corner of the tax code. Kept because the numbers are the
    argument for the scaling, and a reader who removes it should have to delete
    this.
    """
    frame, _ = attach_incomes(_skeleton(), targets_scale=1.0)
    wages = frame["salaire_brut_annuel"].to_numpy()
    earners = wages[wages > 0]
    assert earners.min() > 3_000_000.0
    assert earners.mean() > 20_000_000.0


def test_the_scaled_population_has_plausible_wages(population: pl.DataFrame) -> None:
    """And what it looks like once the target matches the frame.

    The band is wide — this is 400 dwellings, and the point is the order of
    magnitude, not the euro. INSEE's mean private gross annual wage is ~40 k€.
    """
    wages = population["salaire_brut_annuel"].to_numpy()
    earners = wages[wages > 0]
    assert 25_000.0 < earners.mean() < 60_000.0
    assert earners.min() < 100_000.0


def test_the_scaled_population_reaches_the_bottom_of_the_distribution(
    population: pl.DataFrame,
) -> None:
    """The test that would have caught D-149, stated as what the fixture must exercise.

    A population of millionaires exercises the top bracket and nothing else: the
    prime d'activité came out identically zero, so every assertion that could have
    been made about it here was vacuous, and 397 of 439 foyers paid the contribution
    exceptionnelle sur les hauts revenus, which starts at 250 000 € of revenu fiscal
    de référence for a single person.
    """
    result = run(population, 2024, tier="full")
    totals = aggregate(result.households).totals
    assert totals["ppa"] > 0.0, "no household is poor enough to claim the prime d'activité"
    assert totals["af"] > 0.0
    assert totals["rsa"] > 0.0

    from impots.engine.system import baseline

    simulation = build_simulation(population, baseline(), 2024)
    cehr = simulation.calculate("contribution_exceptionnelle_hauts_revenus", 2024)
    ip_net = simulation.calculate("ip_net", 2024)
    assert (cehr != 0).mean() < 0.05, "the CEHR is not a mass tax"
    assert (ip_net == 0).mean() > 0.20, "nobody sits below the entry into the barème"


def test_raking_can_converge_on_a_margin_it_never_reaches() -> None:
    """The kill test for D-150, run on the committed fixture rather than a mock.

    Two margins that cannot both hold — an absolute published household count, and
    a drift constraint pinning the frame's own person totals — and IPF settles at a
    fixed point meeting neither. `converged` says True the whole way.
    """
    frame = with_cells(_skeleton())
    _, diagnostics = rake(frame, standard_margins(frame))

    assert diagnostics.converged
    assert diagnostics.max_change < 1e-6
    assert diagnostics.clipped_households == 0
    assert diagnostics.fit_after["household_type"] > 0.9

    with pytest.raises(RakingRefused, match="coming to rest"):
        check_rake_result(diagnostics)


def test_a_raking_that_did_reach_its_margins_is_accepted() -> None:
    """The other half. A fit inside the bound passes, and a non-converged one does not."""
    good = RakeDiagnostics(
        converged=True, iterations=25, max_change=1e-9, clipped_households=0,
        weight_ratio_range=(0.84, 1.81), effective_sample_size=143_973.0,
        fit_before={"household_type": 0.415}, fit_after={"household_type": 0.0084},
    )
    check_rake_result(good)

    with pytest.raises(RakingRefused, match="did not converge"):
        check_rake_result(replace(good, converged=False))


# --------------------------------------------------------------------------- #
# pensions — the CSG spiral (docs/DECISIONS.md D-176)
# --------------------------------------------------------------------------- #
def _pensioners_only() -> pl.DataFrame:
    """Three pensioner ménages and nothing else: owners, no wage, no unemployment
    benefit, so that no other spiral of the cascade is in play — the fixture
    population carries two more (D-176), which this test is not about."""
    return pl.DataFrame({
        "person_id": [0, 1, 2, 3],
        "household_id": ["h0", "h1", "h2", "h2"],
        "foyer_id": ["h0#0", "h1#0", "h2#0", "h2#0"],
        "famille_id": ["h0#0", "h1#0", "h2#0", "h2#0"],
        "weight": [1.0, 1.0, 1.0, 1.0],
        "age": [69, 69, 69, 67],
        "role_menage": ["personne_de_reference", "personne_de_reference",
                        "personne_de_reference", "conjoint"],
        "role_foyer": ["declarant_principal", "declarant_principal",
                       "declarant_principal", "conjoint"],
        "role_famille": ["demandeur", "demandeur", "demandeur", "conjoint"],
        "salaire_brut_annuel": [0.0, 0.0, 0.0, 0.0],
        "pension_annuelle": [50_000.0, 15_000.0, 25_000.0, 25_000.0],
        "chomage_annuel": [0.0, 0.0, 0.0, 0.0],
        "statut_occupation": ["proprietaire"] * 4,
        "zone_apl": ["zone_2"] * 4,
        "loyer_mensuel": [0.0, 0.0, 0.0, 0.0],
        "parent_isole": [False, False, False, False],
    })


def test_a_pensioners_disposable_income_does_not_depend_on_evaluation_order() -> None:
    """The population wiring, in the two orders it is read in: the runner's (the
    reconciliation report, every chiffrage) and `revenu_disponible` first (the
    population EMTR, `behavioural.emtr._disposable`).

    Measured on the code before D-176: -2 065 EUR on the 50 000 EUR pensioner, +75 on
    the 15 000 one, -2 478 on the couple. On the 400-dwelling fixture, 164 ménages
    moved and the median niveau de vie fell 1.7 %."""
    from impots.engine.system import baseline

    frame = _pensioners_only()
    runner = run(frame, 2024, tier="full").households
    built = build_simulation(frame, baseline(), 2024)
    first = built.calculate("revenu_disponible")
    np.testing.assert_allclose(first, runner["revenu_disponible"].to_numpy(), atol=0.5)
    taxable = built.calculate("retraite_imposable", add=True)
    np.testing.assert_allclose(taxable, frame["pension_annuelle"].to_numpy(), atol=0.5)


# --------------------------------------------------------------------------- #
# unemployment benefit — the same spiral, and the RFR of N-2 (D-177)
# --------------------------------------------------------------------------- #
def _unemployed() -> pl.DataFrame:
    """Unemployment benefit above the SMIC floor (30 000 and 40 000 EUR), beside a
    salary, below the floor (18 000) and beside a pension. Owners, no rent: the
    benefits cascade has spirals of its own (D-176), which this test is not about."""
    rows = [
        ("h0", 45, "personne_de_reference", "declarant_principal", "demandeur", 0, 0, 30_000),
        ("h1", 45, "personne_de_reference", "declarant_principal", "demandeur", 0, 0, 40_000),
        ("h2", 50, "personne_de_reference", "declarant_principal", "demandeur", 35_000, 0, 0),
        ("h2", 48, "conjoint", "conjoint", "conjoint", 0, 0, 25_000),
        ("h3", 45, "personne_de_reference", "declarant_principal", "demandeur", 0, 0, 18_000),
        ("h4", 70, "personne_de_reference", "declarant_principal", "demandeur", 0, 22_000, 0),
        ("h4", 62, "conjoint", "conjoint", "conjoint", 0, 0, 7_000),
    ]
    return pl.DataFrame({
        "person_id": list(range(len(rows))),
        "household_id": [row[0] for row in rows],
        "foyer_id": [f"{row[0]}#0" for row in rows],
        "famille_id": [f"{row[0]}#0" for row in rows],
        "weight": [1.0] * len(rows),
        "age": [row[1] for row in rows],
        "role_menage": [row[2] for row in rows],
        "role_foyer": [row[3] for row in rows],
        "role_famille": [row[4] for row in rows],
        "salaire_brut_annuel": [float(row[5]) for row in rows],
        "pension_annuelle": [float(row[6]) for row in rows],
        "chomage_annuel": [float(row[7]) for row in rows],
        "statut_occupation": ["proprietaire"] * len(rows),
        "zone_apl": ["zone_2"] * len(rows),
        "loyer_mensuel": [0.0] * len(rows),
        "parent_isole": [False] * len(rows),
    })


def test_unemployment_benefit_prices_the_same_whatever_is_computed_first() -> None:
    """The runner's order against `revenu_disponible` first, as for pensions in D-176.

    Measured on the code before D-177: 4 ménages of 5 moved, by up to 1 262 EUR. The
    30 000 EUR chômeur kept 28 112.34 EUR in the runner's order and 28 412.00 EUR
    computed first, and the CSG and CRDS owed on it reached neither."""
    from impots.engine.system import baseline

    frame = _unemployed()
    runner = run(frame, 2024, tier="full").households
    built = build_simulation(frame, baseline(), 2024)
    first = built.calculate("revenu_disponible")
    np.testing.assert_allclose(first, runner["revenu_disponible"].to_numpy(), atol=0.5)


def test_unemployment_benefit_is_taxed_and_levied_net_of_its_csg() -> None:
    """By hand, on the 30 000 EUR chômeur. The CSG on unemployment benefit is assessed
    on 98.25 % of it (the 1.75 % abatement): 3.8 % deductible, 2.4 % not, and 0.5 % of
    CRDS. Above the SMIC floor all three are due, and the income tax is assessed on the
    benefit net of the deductible part — read here off a simulation where that net
    amount is an INPUT, which no spiral can reach.

    Before D-177 the runner's income tax was 1 588 EUR, assessed on the gross 30 000;
    on the net it is 1 426 EUR."""
    from impots.engine.system import baseline

    frame = _unemployed()
    households = run(frame, 2024, tier="full").households
    h0 = households.filter(pl.col("household_id") == "h0")
    assiette = 30_000 * 0.9825
    net_taxable = 30_000 - 0.038 * assiette

    oracle = build_simulation(frame, baseline(), 2024)
    taxable = frame["chomage_annuel"].to_numpy() / 12.0
    taxable[0] = net_taxable / 12.0
    for month in range(1, 13):
        oracle.simulation.set_input("chomage_imposable", f"2024-{month:02d}", taxable)
    ir_on_net = -oracle.calculate("impot_revenu_restant_a_payer")[0]

    assert h0["ir"][0] == pytest.approx(ir_on_net, abs=0.5)
    levies = (0.038 + 0.024 + 0.005) * assiette
    assert h0["revenu_disponible"][0] == pytest.approx(30_000 - levies - h0["ir"][0], abs=1.0)


# --------------------------------------------------------------------------- #
# one household, two paths: the calculator and a population frame (D-183)
# --------------------------------------------------------------------------- #
#: name -> (people as (age, salary, pension, unemployment benefit), statut, rent, zone).
#: Unemployment benefit above the SMIC floor and below it, beside a salary of one's own,
#: a partner's salary and a partner's pension; and a pensioner alone, because the pension
#: field made the same promise (D-175) and nothing held it to it. A statut of None types
#: no dwelling into the calculator, whose full tier then pins nothing but the RFR of N-2
#: (D-179); the population has to carry a statut, and an owner's is the one that pays
#: no housing aid either.
TWO_PATHS = {
    "chomeur": ([(45, 0, 0, 30_000)], "proprietaire", 0.0, 2),
    "chomeur_sans_logement": ([(45, 0, 0, 30_000)], None, 0.0, 2),
    "chomeur_locataire": ([(45, 0, 0, 12_000)], "locataire_vide", 500.0, 2),
    "activite_reduite": ([(45, 6_000, 0, 9_000)], "locataire_vide", 600.0, 2),
    "salarie_et_chomeur": ([(50, 35_000, 0, 0), (48, 0, 0, 25_000)], "locataire_vide", 900.0, 1),
    "retraite_et_chomeur": ([(70, 0, 22_000, 0), (62, 0, 0, 7_000)], "proprietaire", 0.0, 2),
    "retraite": ([(69, 0, 50_000, 0)], "proprietaire", 0.0, 2),
}
TWO_PATHS_ROLES = (("personne_de_reference", "declarant_principal", "demandeur"),
                   ("conjoint", "conjoint", "conjoint"))


@functools.cache
def _population_side() -> dict[str, dict[str, Any]]:
    """Every household of `TWO_PATHS` as population rows, in one frame, run once."""
    rows: list[dict[str, Any]] = []
    for name, (people, statut, loyer, zone) in TWO_PATHS.items():
        for index, (age, salary, pension, chomage) in enumerate(people):
            roles = TWO_PATHS_ROLES[index]
            rows.append({
                "person_id": len(rows), "household_id": name, "foyer_id": f"{name}#0",
                "famille_id": f"{name}#0", "weight": 1.0, "age": age,
                "role_menage": roles[0], "role_foyer": roles[1], "role_famille": roles[2],
                "salaire_brut_annuel": float(salary), "pension_annuelle": float(pension),
                "chomage_annuel": float(chomage),
                "statut_occupation": statut or "proprietaire",
                "zone_apl": f"zone_{zone}", "loyer_mensuel": loyer, "parent_isole": False,
            })
    households = run(pl.DataFrame(rows), 2024, tier="full").households
    return {row["household_id"]: row for row in households.iter_rows(named=True)}


def _calculator_side(name: str) -> dict[str, Any]:
    """The same household typed into the calculator. A replacement income is sent only
    when there is one, as a client leaving a field at its default would."""
    from impots.engine import compute

    people, statut, loyer, zone = TWO_PATHS[name]
    adults = []
    for age, salary, pension, chomage in people:
        adult: dict[str, Any] = {"salaire_brut_annuel": salary, "annee_naissance": 2024 - age}
        if pension:
            adult["pension_annuelle"] = pension
        if chomage:
            adult["chomage_brut_annuel"] = chomage
        adults.append(adult)
    household: dict[str, Any] = {"adults": adults, "couple_marie_ou_pacse": len(adults) == 2}
    if statut is not None:
        household["logement"] = {"statut": statut, "loyer_mensuel": loyer, "zone_apl": zone}
    return compute(HouseholdInput.model_validate(household), 2024, tier="full").baseline


@pytest.mark.parametrize("name", sorted(TWO_PATHS))
def test_a_household_prices_the_same_in_the_calculator_and_in_a_population(name: str) -> None:
    """The same people, typed into the calculator and written as population rows, compared
    on every row both report. Each replacement income the calculator takes promises it is
    written "exactly as the population build writes" its own; this is what keeps the
    promise. Both builders pin the RFR of N-2. The population pins the housing aid always,
    the calculator only where there is a cascade to close: the case without a dwelling
    checks that skipping it changes nothing."""
    calculator = _calculator_side(name)
    population = _population_side()[name]
    shared = [key for key, value in calculator.items()
              if value is not None and key in population]
    assert {"ir", "revenu_disponible", "revenu_fiscal_reference", "chomage_brut",
            "retraite_imposable", "aide_logement", "ppa", "rsa"} <= set(shared)
    for key in shared:
        assert calculator[key] == pytest.approx(population[key], abs=0.5), key


def test_the_population_declares_no_one_in_fin_de_droits_and_its_ass_is_zero() -> None:
    """`to_openfisca` writes no `ass_precondition_remplie`: nobody in the population is « en
    fin de droits », so the `ass` column the runner reads off the registry, like every row of
    the full tier, is zero, the chômeurs of the two-paths frame included (D-189)."""
    households = _population_side()
    assert [households[name]["ass"] for name in sorted(TWO_PATHS)] == [0.0] * len(TWO_PATHS)


def test_the_population_s_income_tax_never_computes_the_ass() -> None:
    """The income tax reads the ASS since D-192, but only where someone meets the ASS's work
    condition that year, and nobody in the population does. Its RFR of N-2, which the build
    pins, and its fiscal block, which the light tier, the rake and the niche imputation read,
    compute no ASS: they cost what they cost before."""
    from impots.engine.system import baseline

    built = build_simulation(_unemployed(), baseline(), 2024)
    built.calculate("impot_revenu_restant_a_payer")
    built.calculate("rfr")
    assert not built.benefits_pinned
    assert not list(built.simulation.get_holder("ass").get_known_periods())


# --------------------------------------------------------------------------- #
# the benefits cascade — housing aid and the RSA, month by month (D-178)
# --------------------------------------------------------------------------- #
def _renters() -> pl.DataFrame:
    """Single renters at 9 500 EUR (RSA and prime d'activité) and 17 000 EUR (prime
    d'activité), and a fixture household: a couple with three children on one salary
    of 26 892 EUR, 792 EUR of rent. Nothing else, so the housing cascade is the only
    spiral in play."""
    rows = [
        ("h0", 40, "personne_de_reference", "declarant_principal", "demandeur", 9_500.0, 700.0),
        ("h1", 40, "personne_de_reference", "declarant_principal", "demandeur", 17_000.0, 700.0),
        ("h2", 38, "personne_de_reference", "declarant_principal", "demandeur", 26_892.0, 792.0),
        ("h2", 42, "conjoint", "conjoint", "conjoint", 0.0, 792.0),
        ("h2", 1, "enfant", "personne_a_charge", "enfant", 0.0, 792.0),
        ("h2", 6, "enfant", "personne_a_charge", "enfant", 0.0, 792.0),
        ("h2", 8, "enfant", "personne_a_charge", "enfant", 0.0, 792.0),
    ]
    return pl.DataFrame({
        "person_id": list(range(len(rows))),
        "household_id": [row[0] for row in rows],
        "foyer_id": [f"{row[0]}#0" for row in rows],
        "famille_id": [f"{row[0]}#0" for row in rows],
        "weight": [1.0] * len(rows),
        "age": [row[1] for row in rows],
        "role_menage": [row[2] for row in rows],
        "role_foyer": [row[3] for row in rows],
        "role_famille": [row[4] for row in rows],
        "salaire_brut_annuel": [row[5] for row in rows],
        "pension_annuelle": [0.0] * len(rows),
        "chomage_annuel": [0.0] * len(rows),
        "statut_occupation": ["locataire_vide"] * len(rows),
        "zone_apl": ["zone_2"] * len(rows),
        "loyer_mensuel": [row[6] for row in rows],
        "parent_isole": [False] * len(rows),
    })


def test_a_renters_disposable_income_does_not_depend_on_evaluation_order() -> None:
    """The runner's order against `revenu_disponible` first — the order the population
    EMTR, and so the EMTR explorer's curves, are computed in.

    Measured on the code before D-178: on the 400-dwelling fixture, 12 renter ménages
    moved, by up to 352 EUR, all through the prime d'activité of January to March,
    whose reference quarter had lost the housing aid of N-1 to a cut."""
    from impots.engine.system import baseline

    frame = _renters()
    runner = run(frame, 2024, tier="full").households
    first = build_simulation(frame, baseline(), 2024).calculate("revenu_disponible")
    np.testing.assert_allclose(first, runner["revenu_disponible"].to_numpy(), atol=0.5)


# --------------------------------------------------------------------------- #
# case T on the years behind N — the parts the CSG reads (D-199)
# --------------------------------------------------------------------------- #
def test_case_t_and_its_parts_are_on_every_year_the_household_builder_writes(
    population: pl.DataFrame,
) -> None:
    """Case T on N-2, N-1 and N, the years the household builder writes it (D-199).

    The CSG on a replacement income takes its rate from the RFR of « l'avant-dernière
    année », against thresholds « pour la première part de quotient familial, majorés [...]
    pour chaque demi-part supplémentaire » (CSS art. L. 136-8, III), and « il est tenu
    compte du nombre de parts fiscales de chaque année » (DSS, letter of 23 November 2023).
    Written on N alone, case T gave a lone parent's foyer its half-part in the income tax of
    N and not in the rate of the CSG on its pension or its unemployment benefit. On `main`,
    the 43 foyers of the fixture that claim it had half a part less on N-2 and N-1 than on N,
    and no other foyer differed. The population sees one year: like the builder, it assumes
    the foyer was the same at 1 January of N-2 and N-1 (CGI art. 196 bis)."""
    from impots.engine.situations import build_situation
    from impots.engine.system import baseline

    lone_parent = HouseholdInput.model_validate({
        "adults": [{"annee_naissance": 1984, "salaire_brut_annuel": 30_000}],
        "children": [{"annee_naissance": 2014}]})
    years = sorted(build_situation(lone_parent, 2024)["foyers_fiscaux"]["ff_0"]["caseT"])
    assert years == ["2022", "2023", "2024"]

    built = build_simulation(population, baseline(), 2024)
    claimed = dict(
        population.group_by("foyer_id").agg(pl.col("parent_isole").first()).iter_rows())
    expected = np.array([claimed[foyer] for foyer in built.foyer_ids])
    assert 0 < expected.sum() < expected.size, "no contrast: the check would prove nothing"
    parts = built.simulation.calculate("nbptr", "2024")
    for year in years:
        np.testing.assert_array_equal(
            built.simulation.calculate("caseT", year), expected, err_msg=f"case T of {year}")
        np.testing.assert_array_equal(
            built.simulation.calculate("nbptr", year), parts, err_msg=f"parts of {year}")


#: Two lone parents, each with a child of ten, owners: a declared pension and gross
#: unemployment benefit, 25 000 EUR each. Under 65, so that art. 157 bis leaves their RFR of
#: N-2 alone: 22 500 EUR either way, after the 10 % deduction, between the thresholds of the
#: reduced rate at 1.5 and at 2 parts.
LONE_PARENTS = {"retraite": (63, 25_000.0, 0.0), "chomeur": (40, 0.0, 25_000.0)}
CHILD_ROLES = ("enfant", "personne_a_charge", "enfant")


def _lone_parents() -> pl.DataFrame:
    """`LONE_PARENTS` as population rows: the parent, then the child, case T on both."""
    rows: list[dict[str, Any]] = []
    for name, (age, pension, chomage) in LONE_PARENTS.items():
        for person_age, roles, own in ((age, TWO_PATHS_ROLES[0], True), (10, CHILD_ROLES, False)):
            rows.append({
                "person_id": len(rows), "household_id": name, "foyer_id": f"{name}#0",
                "famille_id": f"{name}#0", "weight": 1.0, "age": person_age,
                "role_menage": roles[0], "role_foyer": roles[1], "role_famille": roles[2],
                "salaire_brut_annuel": 0.0, "pension_annuelle": pension if own else 0.0,
                "chomage_annuel": chomage if own else 0.0, "statut_occupation": "proprietaire",
                "zone_apl": "zone_2", "loyer_mensuel": 0.0, "parent_isole": True,
            })
    return pl.DataFrame(rows)


def test_a_lone_parent_s_replacement_income_is_levied_at_the_rate_of_two_parts() -> None:
    """By hand, with the thresholds of 2024 in the tree, those of the DSS's letter of 23
    November 2023: the reduced rate up to 15 988 EUR plus 4 269 EUR per extra half-part. An
    RFR of N-2 of 22 500 EUR is under it at 2 parts (24 526) and over it at 1.5 (20 257). At
    2 parts: 3.8 % of CSG, all deductible, the CRDS, no CASA. At 1.5: 6.6 % on the pension,
    under 24 813 + 6 623 = 31 436 EUR, of which 4.2 points deductible, and 0.3 % of CASA; 6.2 %
    on the benefit, of which 3.8 points deductible. The benefit's levies are assessed on
    98.25 % of it, the pension's on all of it.

    On `main` the parts of N-2 were 1.5, and the pension paid 1 050 EUR of deductible CSG,
    600 EUR not deductible and 75 EUR of CASA, the benefit 589.50 EUR not deductible."""
    from impots.engine.system import baseline

    built = build_simulation(_lone_parents(), baseline(), 2024)
    simulation = built.simulation
    assert list(built.foyer_ids) == ["chomeur#0", "retraite#0"]
    np.testing.assert_allclose(simulation.calculate("rfr", "2022"), [22_500.0] * 2, atol=0.01)
    np.testing.assert_array_equal(simulation.calculate("nbptr", "2022"), [2.0, 2.0])

    def levy(variable: str, person: int) -> float:
        return -float(simulation.calculate_add(variable, "2024")[person])

    pensioner, chomeur = 0, 2
    assert levy("csg_deductible_retraite", pensioner) == pytest.approx(0.038 * 25_000, abs=0.01)
    assert levy("csg_imposable_retraite", pensioner) == pytest.approx(0.0, abs=0.01)
    assert levy("casa", pensioner) == pytest.approx(0.0, abs=0.01)
    assert levy("crds_retraite", pensioner) == pytest.approx(0.005 * 25_000, abs=0.01)
    assiette = 0.9825 * 25_000
    assert levy("csg_deductible_chomage", chomeur) == pytest.approx(0.038 * assiette, abs=0.01)
    assert levy("csg_imposable_chomage", chomeur) == pytest.approx(0.0, abs=0.01)
    assert levy("crds_chomage", chomeur) == pytest.approx(0.005 * assiette, abs=0.01)


@functools.cache
def _lone_parents_population_side() -> dict[str, dict[str, Any]]:
    """`LONE_PARENTS` through the runner's full tier, once."""
    households = run(_lone_parents(), 2024, tier="full").households
    return {row["household_id"]: row for row in households.iter_rows(named=True)}


@pytest.mark.parametrize("name", sorted(LONE_PARENTS))
def test_a_lone_parent_prices_the_same_in_the_calculator_and_in_a_population(name: str) -> None:
    """The same lone parent typed into the calculator, which writes case T on N-2 to N, and
    written as population rows, compared on every row both report (D-199).

    On `main` the population's revenu disponible was 675.00 EUR lower on the pension, its CSG
    not deductible and its CASA, and 589.50 EUR lower on the benefit, its CSG not
    deductible."""
    from impots.engine import compute

    age, pension, chomage = LONE_PARENTS[name]
    adult: dict[str, Any] = {"salaire_brut_annuel": 0, "annee_naissance": 2024 - age}
    if pension:
        adult["pension_annuelle"] = pension
    if chomage:
        adult["chomage_brut_annuel"] = chomage
    calculator = compute(HouseholdInput.model_validate({
        "adults": [adult], "children": [{"annee_naissance": 2014}],
        "logement": {"statut": "proprietaire", "loyer_mensuel": 0.0, "zone_apl": 2},
    }), 2024, tier="full").baseline
    population = _lone_parents_population_side()[name]
    shared = [key for key, value in calculator.items()
              if value is not None and key in population]
    assert {"ir", "parts_fiscales", "revenu_disponible", "asf"} <= set(shared)
    for key in shared:
        assert calculator[key] == pytest.approx(population[key], abs=0.5), key
