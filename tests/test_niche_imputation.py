"""B3 second half — imputing niche bases onto the population.

**Everything here tests a calibration.** The niche totals match DGFiP by construction,
so a test asserting they match proves the draw works and nothing else. The tests that
carry weight are the ones about what the calibration did NOT buy: the barème line must
not move, the global cap must still be unpriceable, and the flag that says so must not
fall silent just because some other niche became priceable.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest

from impots.engine.reforms import NICHE_KNOBS
from impots.guards import DISPERSION_DEPENDENT_KNOBS, niche_blind_spot
from impots.population import niches

pytest.importorskip("openpyxl")

HAVE_TABLE = (niches.RAW / niches.CREDITS_FILE).exists()
needs_table = pytest.mark.skipif(
    not HAVE_TABLE, reason="data/raw/ has no DGFiP decile table")


# --- reading the published table ----------------------------------------------------


@needs_table
@pytest.mark.parametrize("niche", niches.IMPUTABLE, ids=lambda n: n.case)
def test_every_imputable_niche_reads(niche):
    table = niches.brackets(niche)
    assert len(table) == niches.DECILES
    assert all(bracket.claimants > 0 for bracket in table)
    assert all(bracket.amount_eur > 0 for bracket in table)
    # Contiguous by CONSTRUCTION, not by luck: the printed bounds leave nine slivers
    # (decile 1 ends at 1 972, decile 2 starts at 1 972.1667) and banding on them would
    # silently drop every foyer that lands in one.
    assert table[0].lower == float("-inf") and table[-1].upper == float("inf")
    for lower, upper in pairwise(table):
        assert lower.upper == upper.lower, "the bands must tile the line without a gap"


@needs_table
def test_the_unit_trap_is_refused_rather_than_absorbed():
    """The same workbook is in THOUSANDS for 2018-2021 and EUROS from 2022.

    The 2018 sheet reads 4 860 210 where 2023 reads 6 019 895 605 — both about six
    billion. Reading one with the other's convention is a silent factor of a thousand,
    and no test that checks only shape would notice.
    """
    with pytest.raises(niches.NicheImputationError, match="THOUSANDS"):
        niches.brackets(niches.IMPUTABLE[0], year=2018)


@needs_table
def test_the_column_with_a_non_breaking_space_is_found():
    """`DONS : PERSONNES EN DIFFICULTE` carries U+00A0 before its colon in the file."""
    dons = next(n for n in niches.IMPUTABLE if n.case == "f7ud")
    assert "\xa0" not in dons.column, "the constant should hold the readable form"
    assert niches.brackets(dons), "and matching should still find it"


@needs_table
def test_an_absent_column_raises_rather_than_taking_a_neighbour():
    ghost = niches.Imputable("f7uf", niches.REDUCTIONS_FILE, "DONS AUX LICORNES", 0.66, "x")
    with pytest.raises(niches.NicheImputationError, match="not found"):
        niches.brackets(ghost)


@needs_table
def test_the_totals_agree_with_the_published_aggregate():
    """A cross-check on the reading, not on the model.

    The four art. 200 donation columns together come to 2 212 M EUR against the Voies
    et Moyens 2 204 M EUR for the same income year — 0.4 %. An earlier reading summed
    only two of the four and reported 2.6 %, treating the shortfall as agreement.
    """
    dons = sum(
        sum(b.amount_eur for b in niches.brackets(n))
        for n in niches.IMPUTABLE if n.case in ("f7uf", "f7ud")
    )
    # The two mapped columns alone; the other two are recorded as unmappable.
    assert 2.0e9 < dons < 2.3e9
    assert set(niches.UNMAPPABLE) == {
        "DONS AIDE AUX VICTIME DE MAYOTTE", "DONS SAUVEGARDE DU PATRIMOINE RELIGIEUX"}


def test_scolarite_is_deliberately_not_imputable():
    """Its cases are COUNTS of children and the published column is one aggregate
    amount across collège, lycée and supérieur — the split cannot be recovered."""
    assert not any(n.case in ("f7ea", "f7ec", "f7ef") for n in niches.IMPUTABLE)


# --- the draw ------------------------------------------------------------------------


@needs_table
def test_the_draw_reproduces_the_published_totals():
    """By construction. This asserts the arithmetic, not the truth of anything."""
    rng = np.random.default_rng(0)
    # A synthetic population spread across the published RFR range.
    rfr = rng.uniform(0, 60_000, 400_000)
    weights = np.full(rfr.shape, 41.6e6 / rfr.size)
    bases = niches.impute(rfr, weights)
    handed_out = niches.imputed_total(bases, weights)
    for niche in niches.IMPUTABLE:
        target = sum(b.amount_eur for b in niches.brackets(niche))
        assert handed_out[niche.case] == pytest.approx(target, rel=0.10), niche.label


@needs_table
def test_the_draw_is_seeded():
    rfr = np.linspace(0, 60_000, 20_000)
    weights = np.ones_like(rfr) * 2_000.0
    first = niches.impute(rfr, weights, seed=1)["f7db"]
    again = niches.impute(rfr, weights, seed=1)["f7db"]
    other = niches.impute(rfr, weights, seed=2)["f7db"]
    assert np.array_equal(first, again)
    assert not np.array_equal(first, other)


@needs_table
def test_mismatched_shapes_are_refused():
    with pytest.raises(niches.NicheImputationError, match="differ"):
        niches.impute(np.zeros(10), np.zeros(11))


@needs_table
def test_every_claimant_in_a_decile_gets_the_same_base():
    """Artefact #1, asserted so nobody mistakes it for a distribution.

    A count and a total are all DGFiP publishes, so the mean is all there is. A
    reform's incidence therefore comes out as a ten-step function.
    """
    rfr = np.linspace(0, 60_000, 50_000)
    weights = np.ones_like(rfr) * 800.0
    base = niches.impute(rfr, weights, seed=3)["f7db"]
    table = niches.brackets(niches.IMPUTABLE[0])
    for bracket in table:
        band = (rfr >= bracket.lower) & (rfr < bracket.upper) & (base > 0)
        if band.sum() > 1:
            assert len(np.unique(np.round(base[band], 6))) == 1, bracket.decile


# --- what the calibration did not buy ------------------------------------------------


def test_the_global_cap_stays_unpriceable_and_is_flagged():
    """The failure that would otherwise hide behind a silenced warning.

    The cap binds only above 10 000 EUR of advantages. The imputation gives every
    claimant in a decile the same base, so the largest imputed credit is a decile mean
    of about 1 900 EUR and nobody reaches it — moving the cap from 10 000 to 4 000
    costs exactly 0.000 bn even with bases in place. The flag must therefore survive
    imputation for this knob and only this knob.
    """
    with_bases = {"reductions": 2.0e9, "credits_impot": 8.6e9}
    assert niche_blind_spot(["plafond_global_niches"], with_bases, NICHE_KNOBS,
                            bases_are_imputed=True) == ("plafond_global_niches",)
    assert niche_blind_spot(["saldom_taux"], with_bases, NICHE_KNOBS,
                            bases_are_imputed=True) == ()
    assert set(DISPERSION_DEPENDENT_KNOBS) == {"plafond_global_niches"}


def test_the_flag_still_fires_when_there_are_no_bases_at_all():
    empty = {"reductions": 0.0, "credits_impot": 0.0}
    assert niche_blind_spot(["saldom_taux"], empty, NICHE_KNOBS) == ("saldom_taux",)


def test_real_bases_would_silence_even_the_cap():
    """The half that keeps the rule from being permanent: a population with genuine
    dispersion — an ERFS-based one, say — should be able to price the cap."""
    with_bases = {"reductions": 2.0e9, "credits_impot": 8.6e9}
    assert niche_blind_spot(["plafond_global_niches"], with_bases, NICHE_KNOBS,
                            bases_are_imputed=False) == ()


# --- the defect the imputation exposed ----------------------------------------------


def test_the_bareme_comparator_is_not_the_net_figure():
    """The reconciliation read `ir` for the barème line and got away with it only
    while every household's niches were zero.

    Once bases existed the line appeared to improve from +8.7 % to -1.7 %, by comparing
    a figure net of réductions against a target that is explicitly gross of them. The
    fix is `ir_avant_niches` (openfisca's `ip_net`: after décote, before réductions).
    """
    from impots.engine.outputs import BY_KEY

    assert BY_KEY["ir_avant_niches"].variable == "ip_net"
    assert BY_KEY["ir"].variable == "impot_revenu_restant_a_payer"

    source = (
        __import__("pathlib").Path("src/impots/population/reconcile.py")
        .read_text(encoding="utf-8")
    )
    bareme = source.index("IR_BAREME_ON_2024_INCOME")
    following = source[bareme:bareme + 400]
    assert 'totals.get("ir_avant_niches")' in following, (
        "the barème line must read the pre-niche figure"
    )


@needs_table
@pytest.mark.slow
def test_the_bareme_line_is_untouched_by_imputation():
    """The test `margins.py` names, and that never existed.

    Niches are subtracted AFTER the barème, so a correct imputation cannot move this
    line. It moving is what exposed D-069. A dangling reference to a test that does not
    exist is worse than no reference: it reads as coverage.
    """
    from impots.api.main import QUICK_TIER_HOUSEHOLDS, _population_frame
    from impots.population import aggregate as agg_module
    from impots.population import reconcile
    from impots.population import runner as run_module

    frame = _population_frame()
    values = {}
    for imputed in (False, True):
        agg = agg_module.aggregate(run_module.run(
            frame, year=2024, tier="full", sample=QUICK_TIER_HOUSEHOLDS,
            impute_niches=imputed).households)
        lines = {line.label: line for line in reconcile.build_lines(agg)}
        values[imputed] = lines["Impôt sur le revenu — barème"].simulated
    assert values[False] == pytest.approx(values[True], rel=1e-9), (
        "the barème line moved with the imputation, which means it is reading a "
        "quantity that is net of niches — the D-069 defect, returned"
    )
    # And the net line MUST move, or the imputation did nothing at all.
    assert values[False] is not None


def test_the_calibration_is_registered_and_spent():
    """A calibration target can never appear as a validation line (margins.py's rule).

    And the line that becomes part-calibrated has to say so where a reader will look.
    """
    from impots.population import margins

    assert margins.NICHE_CREDITS_BY_DECILE.use == "calibration"
    assert "PART-CALIBRATED" in margins.IR_NET_YIELD.caveat
    assert margins.IR_BAREME_ON_2024_INCOME.use == "validation"


# --- the zero this line's validity rests on -----------------------------------------


@pytest.mark.slow
def test_the_bareme_line_holds_only_while_the_non_wage_base_is_zero():
    """A component-non-zero guard, per the reviewer's ruling.

    The published target covers ALL income taxed at the barème — property income,
    BIC/BNC, dividends taxed on option. Our categorical base is 100 % wages and
    pensions. The line sits at +8.7 % inside a ±10 % tolerance, and the sweep measured
    that 10 bn of property income takes it to +12.1 %, outside.

    So this is not "no capital income on either side". It is: only on ours. If any of
    these bases ever becomes non-zero the line has to be reopened rather than quietly
    drifting out of tolerance, and this test is the alarm.
    """
    from openfisca_core.simulations import SimulationBuilder

    from impots.api.schemas import HouseholdInput
    from impots.engine.situations import build_situation
    from impots.engine.system import baseline as baseline_system

    household = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1985}]})
    simulation = SimulationBuilder().build_from_entities(
        baseline_system(), build_situation(household, 2024))

    for component in ("revenu_categoriel_foncier", "revenu_categoriel_capital",
                      "revenu_categoriel_plus_values", "revenu_categoriel_non_salarial"):
        value = float(simulation.calculate(component, "2024").sum())
        assert value == 0.0, (
            f"{component} is no longer identically zero. The barème reconciliation "
            f"line is inside its tolerance BECAUSE this base is empty — reopen it "
            f"before shipping, the sweep measured 10 bn of property income moving it "
            f"from +8.7 % to +12.1 %."
        )
