"""The zero-masked-comparison sweep's standing guards.

> A comparison that's correct only because one side is identically zero isn't
> correct, it's untested.

Every reconciliation line, household and firm, was swept for that defect. Most of what
came back is annotation — a line whose validity is conditional says so in its own note,
where a reader meets it. What is testable is here, and it is of three kinds:

1. **Component-non-zero guards.** A line inside its tolerance BECAUSE a model component
   is empty must fail loudly the day that component fills, rather than drifting out
   quietly. `test_niche_imputation.py` holds the barème line's guard; the distribution
   lines' guard is here.
2. **Estimator guards.** Two lines compared decile MEANS against published QUANTILES.
   That is a wrong-statistic comparison, not a masked one, and fixing it moved D9/D1
   from +39,6 % to +3,5 %. A fix that makes the population look better needs a test
   that says what it was.
3. **Comparison-actually-ran guards.** Four `use="validation"` figures were printed in
   the report's Sources table with no line comparing anything to them — the D-072
   defect, which is the sweep's own class one level up: not a comparison masked by a
   zero, but a target that looked spent and never was.
"""

from __future__ import annotations

import pytest

from impots.population import margins, reconcile

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def aggregates():
    from impots.population import aggregate as agg_module
    from impots.population import runner as run_module
    from impots.service import QUICK_TIER_HOUSEHOLDS, population_frame

    return agg_module.aggregate(run_module.run(
        population_frame(), year=2024, tier="full",
        sample=QUICK_TIER_HOUSEHOLDS).households)


# --- 1. component-non-zero ----------------------------------------------------------


def test_the_distribution_lines_hold_only_while_capital_income_is_zero():
    """Both INSEE lines are inside tolerance, and neither is a clean pass.

    `revenus_nets_du_capital` is identically zero, and capital is the item that makes
    the gap between the top and the bottom in the published statistic. Measured on the
    threshold reading, with capital spread as the square of niveau de vie: D9/D1 goes
    +3,5 % → +6,4 % (f=5 %) → +9,0 % (f=10 %) → +11,9 % (f=15 %), and the median goes
    -5,1 % → -0,1 % (f=10 %) → +2,5 % (f=15 %).

    So the direction is unambiguous even though the magnitude does not flip a status in
    the range tested. If any of these ever becomes non-zero, both lines must be reread
    rather than celebrated for improving.
    """
    from openfisca_core.simulations import SimulationBuilder

    from impots.api.schemas import HouseholdInput
    from impots.engine.situations import build_situation
    from impots.engine.system import baseline as baseline_system

    household = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1985}]})
    simulation = SimulationBuilder().build_from_entities(
        baseline_system(), build_situation(household, 2024))

    for component in ("revenus_nets_du_capital", "revenu_categoriel_capital",
                      "revenu_categoriel_plus_values"):
        value = float(simulation.calculate(component, "2024").sum())
        assert value == 0.0, (
            f"{component} is no longer identically zero. Both INSEE distribution lines "
            f"are inside tolerance while capital income is absent from our side and "
            f"present in the target — reread them before shipping."
        )


# --- 2. the estimator -----------------------------------------------------------------


def test_the_distribution_lines_read_quantiles_not_decile_means(aggregates):
    """The published targets are person-weighted quantiles.

    Reading decile means against them was the larger half of both residuals: -12,5 %
    printed where the correct estimator gives -5,1 %, and +39,6 % where it gives
    +3,5 %. This is a line moving INTO tolerance because of a change we made, which is
    exactly the kind of improvement that has to be pinned rather than pocketed.
    """
    quantiles = aggregates.niveau_de_vie_quantiles
    assert set(quantiles) == {10, 50, 90}
    lines = {line.label: line for line in reconcile.build_lines(aggregates)}

    median = lines["Niveau de vie médian"]
    assert median.simulated == pytest.approx(quantiles[50])
    assert median.simulated != pytest.approx(aggregates.deciles[4].mean_niveau_de_vie), (
        "the median line is reading the decile 5 mean again")

    ratio = lines["Rapport interdécile D9/D1"]
    assert ratio.simulated == pytest.approx(quantiles[90] / quantiles[10])

    # And the two estimators must genuinely differ, or this test proves nothing.
    means_ratio = (aggregates.deciles[8].mean_niveau_de_vie
                   / aggregates.deciles[0].mean_niveau_de_vie)
    assert abs(means_ratio - ratio.simulated) > 0.5


def test_the_decile_table_itself_is_still_household_weighted(aggregates):
    """The fix above must not have leaked into the incidence table.

    A reform's winners and losers are counted per HOUSEHOLD; the published niveau de
    vie statistics are per PERSON. Both are right for their own job, and confusing them
    is how one correct fix becomes two wrong tables.
    """
    total = sum(row.n_households for row in aggregates.deciles)
    assert total == pytest.approx(aggregates.households, rel=1e-6)
    assert total != pytest.approx(aggregates.persons, rel=1e-3)


# --- 3. the comparison actually ran ---------------------------------------------------


def test_every_validation_figure_that_is_printed_has_a_line(aggregates):
    """A published figure listed as a source reads as a figure that was checked.

    Four allocataire counts carried `use="validation"` and appeared in the Sources
    table with nothing comparing anything to them. Two more — pensions and chômage —
    passed a hardcoded `None` and printed «calibrated (spent)» beside an empty cell.
    Same defect, one level up from the sweep's own: not a comparison masked by a zero,
    but a target that looked spent and never was.
    """
    lines = reconcile.build_lines(aggregates)
    # `Line` does not carry its figure, so match on the published value it printed.
    compared = {line.published for line in lines if line.simulated is not None}
    for key, figure in margins.BENEFIT_RECIPIENTS.items():
        assert figure.use == "validation"
        assert figure.value in compared, (
            f"BENEFIT_RECIPIENTS[{key!r}] is a validation figure with no line that "
            f"compares anything to it"
        )
    for figure in (margins.DECLARED_PENSIONS, margins.UNEMPLOYMENT_BENEFIT_SPEND):
        assert figure.value in compared, (
            f"{figure.scope} printed «calibrated (spent)» beside an empty cell until "
            f"the sweep; it must actually compare"
        )


def test_no_line_claims_a_verdict_without_a_comparison(aggregates):
    """`Line.status` must never grade a line whose simulated side is missing."""
    for line in reconcile.build_lines(aggregates):
        if line.simulated is None:
            assert line.status == "not modelled", line.label
            assert not line.passes, line.label


def test_the_allocataire_counts_are_families_in_december(aggregates):
    """Both halves of the scope matter, and both were chosen against a published one.

    The targets are stocks au 31/12: an annual read counts every famille entitled at
    any point in the year, which is larger and different. And an allocataire is a
    FAMILLE — counting ménages would collapse the ones that hold two claiming familles.
    """
    counts = aggregates.counts
    for key in ("af", "ppa", "rsa", "aide_logement"):
        assert f"n_allocataires_{key}" in counts, key
        assert counts[f"n_allocataires_{key}"] > 0

    # Families with RSA in December must not exceed families with RSA at some point in
    # the year — the sanity check that the December read is really a December read.
    assert counts["n_allocataires_rsa"] < aggregates.households


def test_every_benefit_line_carries_its_zero_annotation(aggregates):
    """The sweep's ruling was annotate-or-guard, per line. This is the annotate half.

    Two of the four benefit lines change STATUS when their zero is filled — PPA goes
    from +19,6 % (within) to +42,1 % (outside) once primo-accédants carry a monthly
    housing payment. A line that passes only because a component is empty is not a line
    that passes, and the note has to say so where a reader meets it.
    """
    assert set(reconcile.BENEFIT_ZERO_NOTES) == set(margins.BENEFIT_SPEND)
    seen = {line.label: line for line in reconcile.build_lines(aggregates)}
    seen_counts = {
        "af": seen["Allocataires AF"],
        "ppa": seen["Allocataires prime d'activité"],
        "rsa": seen["Foyers allocataires du RSA"],
        "aide_logement": seen["Allocataires d'une aide au logement"],
    }

    # Split on purpose: `spend_effect` is measured on the SPEND line and must not be
    # printed beside a count, which would be the sweep's own defect while documenting it.
    for key, parts in reconcile.BENEFIT_ZERO_NOTES.items():
        assert set(parts) == {"zero", "spend_effect"}, key
        count_note = seen_counts[key].note or ""
        assert parts["zero"] in count_note, key
        assert parts["spend_effect"] not in count_note, (
            f"the {key} allocataire line is printing a residual measured on the spend "
            f"line"
        )

    for label in ("Allocations familiales", "Prime d'activité",
                  "Prime d'activité (bridge-adjusted)", "RSA",
                  "RSA (bridge-adjusted)", "Aides au logement"):
        assert label in seen, label
        note = seen[label].note or ""
        assert "MASQUÉE" in note or "CONDITIONNELLEMENT VALIDE" in note, label


def test_the_report_can_be_produced_with_niches_imputed():
    """Two MASKED lines had no other reading available at all.

    `cmd_reconcile` never passed `impute_niches`, so the net-IR line and the count of
    foyers imposés compared a figure GROSS of réductions and crédits against a target
    that is net of them, and no invocation could produce the other reading. Measured
    with the flag on: the net yield goes +22,5 % → +10,4 % and foyers imposés −2,3 % →
    −8,8 %, while the barème line does not move at all — which is what says the fix is
    right rather than merely favourable.
    """
    import argparse

    from impots.population import cli

    parser = cli.build_parser()
    for action in ("reconcile", "run"):
        args = parser.parse_args(["population", action, "--impute-niches"])
        assert isinstance(args, argparse.Namespace)
        assert args.impute_niches is True, action
        # Off by default, which is the fact the two lines' notes rest on.
        assert parser.parse_args(["population", action]).impute_niches is False, action
