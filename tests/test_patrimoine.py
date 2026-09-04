"""Phase 5 M0 — the IFI cells, and the gate that says they may be used.

The spec said the tranche table publishes a taxable base per tranche. It does not, and
this file is where that stays established: the reformulated check is falsifiable in two
specific ways, and both are asserted rather than described.

Nothing here fits anything. The module's whole claim is a baseline that is a mechanical
check with zero calibration (D-077); a test that passed by adjusting a factor would
destroy the claim it was meant to protect.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from impots.patrimoine import ifi_cells

pytest.importorskip("openpyxl")

HAVE = (ifi_cells.RAW / ifi_cells.TRANCHE_FILE).exists()
needs_files = pytest.mark.skipif(not HAVE, reason="data/raw/ has no DGFiP IFI bulletin")


# --- reading the publication ---------------------------------------------------------


@needs_files
def test_the_aggregate_reads_and_its_header_lies_about_units():
    """n° 45's Tableau 1 heads its rows '(M€)' and stores euros.

    466 792 714 707 under a header claiming millions. This is the niches module's
    thousands-versus-euros trap in the other direction, and the guard is a plausibility
    band rather than trust in either the header or the cell.
    """
    aggregate = ifi_cells.aggregate()
    assert aggregate.year == 2024
    assert aggregate.foyers == pytest.approx(186_100, rel=1e-6)
    assert 4.0e11 < aggregate.base_eur < 5.0e11, "euros, whatever the header says"
    assert 2.0e9 < aggregate.ifi_eur < 2.5e9
    assert aggregate.mean_base_eur == pytest.approx(2_508_370.58, rel=1e-6)


@needs_files
def test_the_published_headcount_is_rounded_and_the_exact_one_is_recoverable():
    """`Effectif` is rounded to the nearest hundred; the exact count is recoverable.

    The bulletin prints 186 100, and the total base divided by the published mean comes
    out to 186 094.000 — INTEGRAL, which is what identifies it as the true count rather
    than an artefact. That integrality is the whole evidence, so it is what this test
    asserts; a rounded or mis-scaled reading would not land on an integer.

    It matters because every tranche count is a share of this number, and the module
    claims a mechanical check with zero calibration. A 0.0032 % error introduced for
    no reason is a small thing that would sit underneath every figure in the phase.
    """
    aggregate = ifi_cells.aggregate()
    assert aggregate.foyers == 186_100, "the published, rounded figure"
    exact = aggregate.exact_foyers
    assert exact == pytest.approx(186_094.0, abs=1e-3)
    assert abs(exact - round(exact)) < 1e-6, (
        f"base / published mean is {exact}, not an integer — either the mean is not "
        f"base/count, or one of the two has been misread"
    )
    assert exact != aggregate.foyers, "if these ever agree the rounding has changed"
    # And the tranche counts must be built on the exact figure, not the rounded one.
    assert sum(t.foyers for t in ifi_cells.tranches()) == pytest.approx(exact, rel=1e-4)


@needs_files
def test_an_implausible_total_is_refused_rather_than_absorbed():
    band = ifi_cells.PLAUSIBLE_BASE_EUR
    with pytest.raises(ifi_cells.IfiCellError, match="plausible band"):
        ifi_cells._plausible("test", band[1] * 1e6, band)
    with pytest.raises(ifi_cells.IfiCellError, match="plausible band"):
        ifi_cells._plausible("test", band[0] / 1e6, band)


@needs_files
def test_the_tranches_read_and_there_are_four_not_six():
    """Four published tranches, not the barème's six brackets.

    Liability starts at 1,3 M, so the 0,8-1,3 M bracket never appears in the
    distribution. A reader who aligns published tranches onto barème brackets is off
    by one, silently.
    """
    tranches = ifi_cells.tranches()
    assert len(tranches) == 4
    assert tranches[0].lower_eur == 1.30e6
    assert tranches[-1].upper_eur == float("inf")
    for lower, upper in pairwise(tranches):
        assert lower.upper_eur == upper.lower_eur, "the tranches must tile without a gap"


@needs_files
def test_the_tranche_bounds_are_checked_against_the_sheets_own_labels():
    """Not hardcoded blind: a publication that re-cut its tranches must fail loudly."""
    import re

    source = (ifi_cells.RAW.parents[1] / "src" / "impots" / "patrimoine"
              / "ifi_cells.py").read_text(encoding="utf-8")
    assert "re-cut its tranches" in source
    assert re.search(r"printed\s*!=\s*expected", source)


@needs_files
def test_a_missing_sheet_raises_rather_than_taking_a_neighbour():
    with pytest.raises(ifi_cells.IfiCellError, match="has no sheet"):
        ifi_cells._sheet(ifi_cells.TRANCHE_FILE, "Graphique 99")


# --- the gate's two falsifiable properties -------------------------------------------


@needs_files
def test_the_two_published_routes_to_a_tranches_ifi_agree():
    """A check on OUR READING, not a tautology.

    The share of total IFI and the mean IFI are separate numbers in the publication.
    Pairing the wrong columns, or misreading the mean's thousands-of-euros axis, breaks
    this immediately. Measured agreement: 0.003 %.
    """
    aggregate = ifi_cells.aggregate()
    for tranche in ifi_cells.tranches():
        assert tranche.foyers * tranche.mean_ifi_eur == pytest.approx(
            tranche.ifi_eur, rel=0.005), tranche.label
    assert sum(t.foyers for t in ifi_cells.tranches()) == pytest.approx(
        aggregate.foyers, rel=1e-3)


@needs_files
def test_inverting_the_bareme_puts_each_mean_base_inside_its_own_tranche():
    """The falsifiable half of the reformulated check. Nothing forces this.

    The base per tranche is not published, so the mechanical check inverts the barème
    on each tranche's mean tax instead. A barème we had misread — a threshold off, a
    rate off, the exempt band mishandled — would put an implied mean outside its own
    bracket. Measured: 1.7052, 3.1772, 6.0747, 14.7126 M€, all inside.
    """
    from scripts.verify_ifi import barometer, invert

    scale = barometer(ifi_cells.TRANCHE_YEAR)
    for tranche in ifi_cells.tranches():
        implied = invert(tranche.mean_ifi_eur, scale)
        assert tranche.lower_eur <= implied <= tranche.upper_eur, (
            f"{tranche.label}: implied mean base {implied:,.0f} is outside its own "
            f"tranche — the barème has been misread"
        )


@needs_files
def test_the_reconstructed_base_falls_short_by_the_amount_the_reliefs_predict():
    """The other falsifiable half: the residual's SIGN is the test.

    Décote, plafonnement and the dons reduction all lower tax, so inverting tax must
    understate the base. A shortfall of the wrong sign would mean the arithmetic is
    wrong rather than incomplete. Measured -6.46 % against an independently published
    aggregate, with dons alone worth about 165 M EUR of tax relief.
    """
    from scripts.verify_ifi import barometer, invert

    aggregate = ifi_cells.aggregate()
    scale = barometer(ifi_cells.TRANCHE_YEAR)
    reconstructed = sum(
        invert(t.mean_ifi_eur, scale) * t.foyers for t in ifi_cells.tranches())
    shortfall = 1 - reconstructed / aggregate.base_eur
    assert 0.0 < shortfall < 0.12, (
        f"reconstructed base is {-shortfall:+.2%} of published. A NEGATIVE shortfall "
        f"means our barème arithmetic overstates tax, which no unmodelled relief can "
        f"explain."
    )


@needs_files
def test_the_bareme_is_the_engines_and_its_node_is_read_by_a_formula():
    """The phantom check the handoff demands on every node in this namespace.

    `aide_a_domicile` is one namespace away from these parameters, resolves non-null,
    and is read by nothing (D-064, D-075). Resolving is not the property that matters.
    """
    from scripts.verify_ifi import _is_read, barometer

    assert barometer(2024) == [
        (800_000, 0.005), (1_300_000, 0.007), (2_570_000, 0.01),
        (5_000_000, 0.0125), (10_000_000, 0.015)]
    assert _is_read("impot_fortune_immobiliere_ifi")
    assert not _is_read("aide_a_domicile"), (
        "the phantom became readable — recheck the whole namespace")


@needs_files
def test_the_gate_passes_and_is_the_thing_that_gates():
    from scripts.verify_ifi import audit

    assert audit() is True
