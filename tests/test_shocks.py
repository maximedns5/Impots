"""B1 — shock construction, double entry, and the instruments that have no multiplier.

The interesting tests here are the refusals. A macro layer that quietly borrows a
neighbouring multiplier for an instrument nobody measured produces a number for every
reform, which is worse than producing one for some of them.
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.macro import mesange, shocks, tes

pytest.importorskip("openpyxl")

HAVE_TES = (tes.RAW / "insee_TES_symetrique_A38_2023SD.xlsx").exists()
needs_tes = pytest.mark.skipif(not HAVE_TES, reason="data/raw/ has no INSEE table")


@pytest.fixture(scope="module")
def table():
    return tes.load("2023SD")


# --- mapping and its sign ----------------------------------------------------------


def test_a_tax_cut_is_an_expansionary_impulse():
    """Deltas arrive receipts-positive; the impulse convention is expansionary."""
    impulse = shocks.build({"ir": -3.0e9}, year=2026)
    assert impulse.by_instrument["impot_sur_le_revenu"] == pytest.approx(+3.0e9)
    rise = shocks.build({"ir": +3.0e9}, year=2026)
    assert rise.by_instrument["impot_sur_le_revenu"] == pytest.approx(-3.0e9)


def test_the_three_csg_lines_land_on_one_instrument():
    impulse = shocks.build(
        {"csg_imposable": -4.0e9, "csg_deductible": -1.0e9, "crds": -0.5e9}, year=2026)
    assert set(impulse.by_instrument) == {"csg"}
    assert impulse.by_instrument["csg"] == pytest.approx(5.5e9)


def test_every_mapped_instrument_has_a_published_variant():
    """The mapping cannot name a variant `mesange` does not parse."""
    assert set(shocks.INSTRUMENT_MAP.values()) <= set(mesange.VARIANTS)
    assert set(shocks.ALLOCATION_BASIS) <= set(mesange.VARIANTS)


# --- targeted versus uniform, the pass's most exploitable finding -------------------


def test_an_allegement_routes_to_the_targeted_variant():
    """Phase 3's whole allègements work moves these knobs.

    Routed to the uniform variant it would have understated employment by 39 % at three
    years. The deltas cannot tell the two apart — the population layer reports one
    employer-contribution total either way — so the decision is made from the knobs.
    """
    for knob in ("allegement_general_plafond", "bandeau_maladie_taux",
                 "bandeau_famille_plafond"):
        impulse = shocks.build({"employer_contributions": -5.0e9}, year=2026,
                               knobs=(knob,))
        assert set(impulse.by_instrument) == {"cotisations_employeurs_ciblees"}, knob


def test_a_uniform_contribution_reform_keeps_the_uniform_variant():
    impulse = shocks.build({"employer_contributions": -5.0e9}, year=2026,
                           knobs=("cotisation_maladie_taux",))
    assert set(impulse.by_instrument) == {"cotisations_employeurs"}


def test_no_knobs_means_uniform():
    """The conservative default: an unlabelled reform does not claim targeting."""
    impulse = shocks.build({"employer_contributions": -5.0e9}, year=2026)
    assert set(impulse.by_instrument) == {"cotisations_employeurs"}


def test_the_targeted_route_does_not_change_the_amount():
    """Routing picks a multiplier, never rescales the impulse."""
    uniform = shocks.build({"employer_contributions": -5.0e9}, year=2026)
    targeted = shocks.build({"employer_contributions": -5.0e9}, year=2026,
                            knobs=("allegement_general_plafond",))
    assert uniform.total == targeted.total == pytest.approx(5.0e9)


def test_an_unrecognised_delta_raises_rather_than_vanishing():
    """Kill test: a silently dropped delta makes the shock smaller than the reform."""
    with pytest.raises(shocks.ShockError, match="neither mapped"):
        shocks.build({"taxe_sur_les_licornes": -1.0e9}, year=2026)


# --- what has no multiplier ---------------------------------------------------------


@pytest.mark.parametrize("delta", ["af", "ppa", "rsa", "aide_logement"])
def test_transfers_get_no_multiplier_and_say_why(delta):
    impulse = shocks.build({delta: 1.0e9}, year=2026)
    assert impulse.by_instrument == {}
    assert delta in impulse.unmapped
    reason = impulse.reasons()[delta]
    assert "0,39" in reason and "composite" in reason.lower()
    # The measured composition, added after the adversarial pass read p106.
    assert "46 %" in reason


@pytest.mark.parametrize("delta", ["impot_societes", "cvae", "c3s", "cebge"])
def test_firm_instruments_do_not_borrow_the_employer_multiplier(delta):
    impulse = shocks.build({delta: -1.0e9}, year=2026)
    assert "cotisations_employeurs" not in impulse.by_instrument
    assert "coût du capital" in impulse.reasons()[delta]


def test_coverage_uses_gross_magnitudes_not_signed_totals():
    """Kill test for a real bug: signed unmapped totals cancel and flatter coverage.

    A 2 bn benefit rise and a 1 bn corporate tax cut are 3 bn of uncovered movement.
    Netting them to 1 bn reported 75 % coverage where the honest figure is 50 %.
    """
    impulse = shocks.build(
        {"ir": -3.0e9, "rsa": 2.0e9, "impot_societes": -1.0e9}, year=2026)
    assert impulse.covered_share == pytest.approx(0.5)


def test_a_fully_uncovered_reform_reports_zero_coverage():
    assert shocks.build({"rsa": 1.0e9}, year=2026).covered_share == 0.0


# --- double entry -------------------------------------------------------------------


def test_a_balanced_shock_passes():
    impulse = shocks.build({"csg_imposable": -5.0e9}, year=2026, reform_cost=-5.0e9)
    shocks.assert_balanced(impulse, -5.0e9)


def test_an_unbalanced_shock_dies():
    """The kill test §1 asks for by name."""
    impulse = shocks.build({"csg_imposable": -5.0e9}, year=2026)
    with pytest.raises(shocks.ShockError, match="does not reconstitute"):
        shocks.assert_balanced(impulse, -8.0e9)


def test_the_balance_check_is_on_magnitude_not_a_signed_residual():
    """A one-sided bound on a signed residual passes exactly what it should fail.

    For a cost, a bigger miss reads as a smaller number. This repository shipped that
    mistake once; both directions must fail here.
    """
    impulse = shocks.build({"csg_imposable": -5.0e9}, year=2026)
    for wrong_cost in (-8.0e9, -2.0e9):
        with pytest.raises(shocks.ShockError):
            shocks.assert_balanced(impulse, wrong_cost)


def test_unmapped_deltas_still_count_towards_the_balance():
    """They have no multiplier, but they are still money the reform moved."""
    impulse = shocks.build({"ir": -3.0e9, "rsa": 2.0e9}, year=2026)
    shocks.assert_balanced(impulse, -1.0e9)
    with pytest.raises(shocks.ShockError):
        shocks.assert_balanced(impulse, -3.0e9)


# --- allocation ---------------------------------------------------------------------


@needs_tes
def test_the_allocation_totals_the_impulse(table):
    impulse = shocks.build({"ir": -3.0e9}, year=2026)
    demand = shocks.allocation(table, impulse)
    assert demand.sum() == pytest.approx(3.0e9, rel=1e-9)
    assert (demand >= 0).all()


@needs_tes
def test_instruments_allocate_on_different_bases(table):
    """An employer-contribution cut is not spent like an income-tax cut."""
    household = shocks.allocation(table, shocks.build({"ir": -1.0e9}, year=2026))
    firm = shocks.allocation(
        table, shocks.build({"employer_contributions": -1.0e9}, year=2026))
    assert not np.allclose(household, firm)
    branches = list(table.branches)
    assert firm[branches.index("FZ")] > household[branches.index("FZ")]


@needs_tes
def test_a_mixed_sign_impulse_is_refused(table):
    """Netting would allocate the residual on a mix belonging to neither instrument."""
    impulse = shocks.build({"ir": -3.0e9, "csg_imposable": +1.0e9}, year=2026)
    with pytest.raises(shocks.ShockError, match="opposite directions"):
        shocks.allocation(table, impulse)


@needs_tes
def test_a_reform_with_no_mapped_instrument_has_no_macro_path(table):
    impulse = shocks.build({"rsa": 1.0e9}, year=2026)
    with pytest.raises(shocks.ShockError, match="no macro path"):
        shocks.allocation(table, impulse)
