"""Phase 7 A0 — the accuracy budget's kill tests, written before any real case was priced.

The spec's ordering is deliberate and this file is the reason for it: A0's ranking decides
which lever Phase 7 spends its sessions on, so a ranker that cannot be shown to fail would
not produce a wrong number, it would produce a wasted phase.

The governing rule here is D-044's, arrived at five times in this project: **a check
derived from the thing it checks cannot fail when that thing is wrong.** So the synthetic
case's answer is fixed by hand — three spreads in a 100 : 10 : 1 ratio — and never read
back from `budget_for`. And the dominant source is MOVED between tests, because a ranker
that returns a constant order passes any single arrangement.
"""

from __future__ import annotations

import math

import pytest

from impots import accuracy

# ---------------------------------------------------------------- the kill test itself

@pytest.mark.parametrize("loudest", ["loud", "middle", "quiet"])
def test_the_budget_ranks_the_known_dominant_source_first(loudest: str) -> None:
    """A0's completion condition, and it is parametrized over WHICH source dominates.

    Parametrizing over the answer rather than over the code's own output is the whole
    point: the expected winner is `loudest`, chosen here, and `synthetic_case` is told to
    make that source the loud one. A ranker hard-wired to return the first source, or the
    declaration order, or alphabetical order, fails at least one arrangement.
    """
    sources = accuracy.synthetic_case(dominant=loudest)
    budget = accuracy.budget_for("synthetique", "cas synthétique", 10e9, sources, draws=64)

    dominant = budget.dominant("sampled")
    assert dominant is not None
    assert dominant.source == loudest, (
        f"la source dominante construite est {loudest!r} et le budget classe "
        f"{dominant.source!r} en tête")


@pytest.mark.parametrize("loudest", ["loud", "middle", "quiet"])
def test_the_ranking_recovers_the_full_known_order(loudest: str) -> None:
    """Not just the winner — the whole order, since a lever ranked second still gets built.

    With spreads at 100 : 10 : 1 the variances stand at 10 000 : 100 : 1, so the order is
    unambiguous and hand-checkable.
    """
    sources = accuracy.synthetic_case(dominant=loudest)
    names = [s.key for s in sources]
    rotation = names.index(loudest)
    expected = [names[(rotation + i) % len(names)] for i in range(len(names))]

    ranked = accuracy.budget_for("s", "s", 10e9, sources, draws=96).ranked("sampled")
    assert [c.source for c in ranked] == expected


def test_the_shares_of_one_method_sum_to_one_and_the_loud_one_dominates() -> None:
    """The share is the number a reader acts on, so it gets its own assertion.

    100 : 10 : 1 spreads mean the loud source should carry the overwhelming majority of the
    variance. The threshold is set at 0,95 rather than at the exact 0,9901 the ratio
    implies, because 64 draws of a bounded pseudo-draw carry sampling noise and a test
    pinned to four decimals would be pinning the noise.
    """
    budget = accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=96)
    ranked = budget.ranked("sampled")
    assert sum(c.share or 0.0 for c in ranked) == pytest.approx(1.0)
    assert (ranked[0].share or 0.0) > 0.95


# --------------------------------------------------- the refusals, each with its kill

def test_a_sampled_source_without_a_sampler_is_refused() -> None:
    """«sampled» is a claim that a real law exists. Without one it is a bound wearing a
    distribution's clothes, and its variance share would be a convention presented as a
    measurement."""
    with pytest.raises(accuracy.AccuracyError, match="sans échantillonneur"):
        accuracy.Source(key="k", label="l", method="sampled")


def test_a_swing_must_name_both_endpoints() -> None:
    """The endpoints are NAMED because a swing has to say what it is the difference of.

    This is the uprating trap in test form: `(frozen, aged)` is a difference between doing
    the uprating and not doing it, and a source that could not be made to name its
    endpoints could smuggle that in as a low bound.
    """
    with pytest.raises(accuracy.AccuracyError, match="sans fonction ou sans bornes"):
        accuracy.Source(key="k", label="l", method="swing", swing=lambda _n: 0.0)


def test_an_unmeasured_source_must_carry_its_reason() -> None:
    """A source absent from a budget reads as a source that does not matter."""
    with pytest.raises(accuracy.AccuracyError, match="UNMEASURED sans raison"):
        accuracy.Source(key="k", label="l", method="unmeasured")


def test_an_unmeasured_source_is_reported_and_given_no_share() -> None:
    """It must appear, and it must not score. Both halves matter: dropping it hides it,
    scoring it invents a measurement that does not exist."""
    sources = [
        *accuracy.synthetic_case(),
        accuracy.Source(key="cell_bound", label="placement intra-cellule",
                        method="unmeasured",
                        unmeasured_reason="aucune graine seconde n'a jamais été tirée"),
    ]
    budget = accuracy.budget_for("s", "s", 10e9, sources, draws=32)

    unmeasured = budget.unmeasured
    assert [c.source for c in unmeasured] == ["cell_bound"]
    assert unmeasured[0].variance is None
    assert unmeasured[0].share is None
    assert unmeasured[0].note
    # And it did not distort the measured family's shares.
    assert sum(c.share or 0.0 for c in budget.ranked("sampled")) == pytest.approx(1.0)


def test_a_single_draw_is_refused_rather_than_scored_as_zero() -> None:
    """One draw gives variance 0,0, which a ranking reads as «this source does not
    matter» — the exact opposite of what one draw licenses."""
    with pytest.raises(accuracy.AccuracyError, match="un tirage unique"):
        accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=1)


def test_an_empty_source_list_is_refused() -> None:
    with pytest.raises(accuracy.AccuracyError, match="aucune source déclarée"):
        accuracy.budget_for("s", "s", 10e9, [])


# ------------------------------------------- the classes are never mixed, and that is a test

def test_shares_are_computed_within_a_method_and_never_across() -> None:
    """The design's load-bearing refusal.

    A swing's pseudo-variance passes through `VARIANCE_OF_A_RANGE`, an assumed uniform
    shape; a sampled variance passes through no such assumption. Ranking them together
    would rank the conventions. So each family's shares sum to one on their own.
    """
    swing = accuracy.Source(
        key="uprating", label="hypothèse d'uprating", method="swing",
        swing=lambda name: {"bas": 9.0e9, "haut": 11.0e9}[name],
        endpoints=("bas", "haut"),
        note="bornes déclarées par l'appelant, jamais prévues")
    budget = accuracy.budget_for("s", "s", 10e9, [*accuracy.synthetic_case(), swing],
                                 draws=48)

    assert sum(c.share or 0.0 for c in budget.ranked("sampled")) == pytest.approx(1.0)
    assert sum(c.share or 0.0 for c in budget.ranked("swing")) == pytest.approx(1.0)
    assert [c.source for c in budget.ranked("swing")] == ["uprating"]


def test_a_swing_reports_its_width_because_that_needs_no_assumption() -> None:
    """The width is the honest headline for a bounded source: it is what was measured,
    before any shape was assumed over the interval."""
    swing = accuracy.Source(
        key="u", label="u", method="swing",
        swing=lambda name: {"bas": 9.0e9, "haut": 11.0e9}[name], endpoints=("bas", "haut"))
    contribution = accuracy.measure(swing, draws=2, seed=1)

    assert contribution.width_eur == pytest.approx(2.0e9)
    assert contribution.variance == pytest.approx(4.0e18 / accuracy.VARIANCE_OF_A_RANGE)
    assert contribution.sigma_eur == pytest.approx(math.sqrt(4.0e18 / 12.0))


def test_the_range_to_variance_convention_is_a_named_constant() -> None:
    """It is a convention and not a measurement, so it must be arguable in ONE place
    rather than audited across expressions."""
    assert accuracy.VARIANCE_OF_A_RANGE == 12.0


# ------------------------------------------------------------------ determinism

def test_the_same_seed_gives_the_same_budget() -> None:
    """A ranking that moved between runs could not order a phase."""
    a = accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=32, seed=7)
    b = accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=32, seed=7)
    assert [(c.source, c.variance) for c in a.contributions] == \
           [(c.source, c.variance) for c in b.contributions]


def test_a_different_seed_moves_the_variances_but_not_the_ranking() -> None:
    """The estimate is noisy; the ORDER, at 100 : 10 : 1, must not be.

    If this ever fails, the draw count is too low for the ratio being separated — which is
    a finding about the budget's resolution, not a test to relax.
    """
    a = accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=64, seed=11)
    b = accuracy.budget_for("s", "s", 10e9, accuracy.synthetic_case(), draws=64, seed=99)
    assert [c.source for c in a.ranked("sampled")] == [c.source for c in b.ranked("sampled")]
    assert a.ranked("sampled")[0].variance != b.ranked("sampled")[0].variance


# --------------------------------------------------- the reference cases (A0's design points)

def test_there_is_exactly_one_reference_reform_per_declared_family() -> None:
    """Eight families, eight cases. Fails if a family is dropped or doubled — a budget
    missing a family reads as a family with no uncertainty."""
    from impots import accuracy_cases

    families = [c.family for c in accuracy_cases.REFERENCE_REFORMS]
    assert len(families) == len(set(families)) == 8, families
    assert set(families) == {"barème", "allègements", "prestations", "niches",
                             "IS", "CVAE", "IFI", "trajectoire"}


def test_a_reference_reform_that_does_not_move_is_refused() -> None:
    """The guard that CVAE's no-op produced.

    `cvae_taux_max = 0,0028` is the value in force, so that case priced at -0,0000 md€ and
    its placement variance was exactly zero — which the report rendered as «placement
    contributes 0,0 % to CVAE», a sentence about a reform that did nothing.
    """
    from impots import accuracy_cases

    noop = accuracy_cases.ReferenceReform(
        key="noop", label="no-op", family="CVAE", chain="firm",
        knob="cvae_taux_max", value=0.0028)
    with pytest.raises(ValueError, match="n'est pas une réforme"):
        accuracy_cases.central_for(noop)


def test_every_cheap_reference_reform_actually_moves() -> None:
    """The positive half: each firm/patrimoine case clears the threshold.

    Both halves are needed. A refusal test alone would pass on a module that refused
    everything, and this project has shipped a denylist-shaped refusal before.
    """
    from impots import accuracy_cases

    for case in accuracy_cases.REFERENCE_REFORMS:
        if case.chain in ("firm", "patrimoine"):
            assert abs(accuracy_cases.central_for(case)) > \
                accuracy_cases.MOVES_EPSILON_EUR, case.key


def test_the_ifi_placement_bound_is_open_because_the_reform_cuts_a_tranche() -> None:
    """At an unchanged barème this bound is a POINT by construction — the patrimoine tests
    assert that zero width themselves. A0's first IFI case used the unchanged barème and
    would have reported a rigorous zero about a case built so it could not move."""
    from impots import accuracy_cases

    swing = accuracy_cases.ifi_cell_bound_swing()
    low, high = swing("concentre"), swing("extremal")
    assert abs(high - low) > 100e6, (
        f"largeur {abs(high - low):,.0f} EUR : la réforme de référence ne coupe aucune "
        f"tranche, et l'encadrement ne mesure rien")


def test_every_unmeasured_source_names_why() -> None:
    """Three of the spec's declared sources have neither a law nor bounds today. Each must
    say so in its own words — an UNMEASURED row without a reason is an oversight."""
    from impots import accuracy_cases

    for case in accuracy_cases.REFERENCE_REFORMS:
        for source in accuracy_cases.sources_for(case, households=1000):
            if source.method == "unmeasured":
                assert len(source.unmeasured_reason) > 60, (case.key, source.key)
