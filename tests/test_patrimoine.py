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


# --- M1: the household calculator ----------------------------------------------------


class TestHouseholdIfi:
    """Hand-derived goldens at every kink, plus the two engine defects they exposed.

    Every case here carries income. That is not decoration: the plafonnement caps
    IFI-plus-income-tax at 75 % of income, so a foyer with no income owes NO IFI
    whatever its wealth. A golden built without income would price zero and prove
    nothing — the zero-masked comparison, in the module's first test file.
    """

    INCOME = 400_000.0

    @staticmethod
    def bareme(base: float) -> float:
        """The 2024 IFI scale, written out independently of the engine."""
        brackets = ((800_000, 1_300_000, 0.005), (1_300_000, 2_570_000, 0.007),
                    (2_570_000, 5_000_000, 0.010), (5_000_000, 10_000_000, 0.0125),
                    (10_000_000, float("inf"), 0.015))
        return sum(max(0.0, min(base, high) - low) * rate for low, high, rate in brackets)

    def priced(self, base: float, **kwargs):
        from impots.patrimoine.ifi import IfiInputs, price

        return price(IfiInputs(autres_immeubles_batis=base,
                               revenu_imposable=self.INCOME, **kwargs))

    def test_the_plafonnement_abates_everything_at_zero_income(self):
        """Measured, and the reason every other case here carries income."""
        from impots.patrimoine.ifi import IfiInputs, price

        poor = price(IfiInputs(autres_immeubles_batis=2_000_000, revenu_imposable=0.0))
        assert poor.values["isf_ifi_iai"] == pytest.approx(7_400.0)
        assert poor.ifi == pytest.approx(0.0), (
            "a foyer with no income owes no IFI — the plafonnement caps at 75 % of "
            "nothing. Any golden written without income prices zero for this reason "
            "and tests nothing at all."
        )
        assert self.priced(2_000_000).ifi == pytest.approx(7_400.0)

    # 1 300 001 is deliberately absent: it sits INSIDE the décote window, so its tax
    # is not the bare scale. It is covered by the décote test instead.
    @pytest.mark.parametrize("base", [1_500_000, 2_000_000, 2_570_000,
                                      3_000_000, 5_000_000, 8_000_000, 10_000_000])
    def test_every_bareme_kink_matches_hand_arithmetic(self, base):
        """The scale, bracket by bracket, against an independent implementation."""
        result = self.priced(base)
        expected = self.bareme(base)
        assert result.values["isf_ifi_iai"] == pytest.approx(expected, abs=0.01), base
        # And with no décote and no relief above 1.4 M, the tax IS the scale — until
        # the plafonnement bites, which it does not at this income below ~11 M.
        if base <= 10_000_000:
            assert result.ifi == pytest.approx(expected, abs=0.01), base

    @pytest.mark.parametrize(("base", "expected_decote"), [
        (1_300_001, 1_250.0 - 0.0125), (1_350_000, 625.0), (1_400_000, 0.0)])
    def test_the_decote_window_matches_its_formula(self, base, expected_decote):
        """17 500 − 1,25 % × base, over 1,3–1,4 M and nowhere else."""
        result = self.priced(base)
        assert result.decote == pytest.approx(expected_decote, abs=0.02), base
        assert result.ifi == pytest.approx(self.bareme(base) - expected_decote, abs=0.02)

    def test_the_decote_is_absent_outside_its_window(self):
        assert self.priced(1_450_000).decote == pytest.approx(0.0)
        assert self.priced(3_000_000).decote == pytest.approx(0.0)

    def test_the_residence_principale_abattement_is_thirty_percent(self):
        from impots.patrimoine.ifi import IfiInputs, price

        result = price(IfiInputs(residence_principale=3_000_000,
                                 revenu_imposable=self.INCOME))
        assert result.values["isf_ifi_imm_bati"] == pytest.approx(2_100_000.0)
        assert result.ifi == pytest.approx(self.bareme(2_100_000.0), abs=0.01)

    def test_the_passif_is_deducted_from_the_base(self):
        from impots.patrimoine.ifi import IfiInputs, price

        result = price(IfiInputs(autres_immeubles_batis=3_000_000,
                                 passif_deductible=500_000,
                                 revenu_imposable=self.INCOME))
        assert result.assiette == pytest.approx(2_500_000.0)

    def test_the_dons_reduction_is_seventy_five_percent_capped_at_fifty_thousand(self):
        from impots.patrimoine.ifi import IfiInputs, price

        base = 5_000_000
        plain = self.priced(base).ifi
        giving = price(IfiInputs(autres_immeubles_batis=base, revenu_imposable=self.INCOME,
                                 dons_organismes_interet_general=10_000)).ifi
        assert plain - giving == pytest.approx(7_500.0, abs=0.01), "75 % of 10 000"
        # And the cap: a donation big enough to exceed 50 000 of relief is capped.
        huge = price(IfiInputs(autres_immeubles_batis=20_000_000,
                               revenu_imposable=5_000_000,
                               dons_organismes_interet_general=200_000)).ifi
        uncapped = price(IfiInputs(autres_immeubles_batis=20_000_000,
                                   revenu_imposable=5_000_000)).ifi
        assert uncapped - huge == pytest.approx(50_000.0, abs=0.01), "capped at 50 000"

    # --- the two defects the goldens exposed ------------------------------------------

    def test_no_ifi_below_the_liability_threshold_and_the_tax_is_monotone(self):
        """CGI art. 964: liable only above 1,3 M. openfisca charges from 800 k.

        The engine's `isf_ifi_iai` for 2018+ is `bareme.calc(assiette)` with no
        eligibility test, so it charges 500 EUR at 900 000 and 2 500 EUR at 1 299 999.
        The tell that this is a defect and not a reading: it makes the tax
        NON-MONOTONIC — 1 299 999 owing 2 500 EUR while 1 300 000 owes 1 250 EUR,
        because the décote begins only at the threshold. A tax that falls as the base
        rises is not a policy anyone wrote.
        """
        for base in (900_000, 1_200_000, 1_299_999, 1_300_000):
            assert self.priced(base).ifi == pytest.approx(0.0), base
        previous = -1.0
        for base in (1_300_001, 1_350_000, 1_400_000, 1_500_000, 2_000_000, 5_000_000):
            current = self.priced(base).ifi
            assert current >= previous, f"IFI fell between bases at {base}"
            previous = current

    def test_the_engine_alone_would_tax_below_the_threshold(self):
        """The kill test for the guard above: without our gate the defect is there.

        A correction with no demonstration that it corrects something is decoration —
        the standing rule in its final form.
        """
        from openfisca_core.simulations import SimulationBuilder

        # UNCORRECTED: `baseline()` now carries our corrections, so this must reach for
        # the reference implementation explicitly. That it has to is the point — the
        # correction is live on every other path.
        from impots.engine.system import uncorrected_baseline

        situation = {
            "individus": {"M": {"salaire_imposable": {"2024": 400_000}}},
            "familles": {"f": {"parents": ["M"]}},
            "foyers_fiscaux": {"ff": {"declarants": ["M"], "b1ac": {"2024": 1_299_999}}},
            "menages": {"m": {"personne_de_reference": ["M"]}},
        }
        simulation = SimulationBuilder().build_from_entities(
            uncorrected_baseline(), situation)
        raw = -float(simulation.calculate("isf_ifi", "2024")[0])
        # 2 517,48 rather than 2 500, and the difference is instructive: the raw engine
        # ALSO applies the 5 % forfait, which lifts 1 299 999 to 1 364 999 — over the
        # threshold and into the décote window. So the two defects interact, and the
        # uncorrected engine charges a foyer that owes nothing a figure arrived at
        # through a window it should never have entered.
        assert raw == pytest.approx(2_517.48, abs=0.05), (
            "the engine no longer taxes below the threshold — if openfisca has fixed "
            "this, remove our gate rather than keeping a correction that corrects "
            "nothing"
        )
        assert raw > 2_000.0, "the magnitude is the point, not the decimals"

    def test_the_forfait_mobilier_correction_is_switchable_and_quantified(self):
        """The contested one. Ours by default, theirs on request, difference visible.

        openfisca applies a 5 % forfait mobilier to the IFI base, arguing from CGI
        art. 973 (IFI values follow DMTG rules) and art. 764 I-3° (meubles meublants
        floored at 5 %). Our reading: art. 965 puts only immovable property in the
        base, so a furniture-valuation floor has nothing to value. The data leans our
        way — see `test_the_published_data_prefers_the_correction`.
        """
        from impots.patrimoine.ifi import IfiInputs, openfisca_reading, price

        inputs = IfiInputs(autres_immeubles_batis=2_000_000, revenu_imposable=400_000)
        ours, theirs = price(inputs), openfisca_reading(inputs)
        assert ours.assiette == pytest.approx(2_000_000.0)
        assert theirs.assiette == pytest.approx(2_100_000.0), "5 % uplift"
        assert ours.ifi == pytest.approx(7_400.0, abs=0.01)
        assert theirs.ifi == pytest.approx(8_100.0, abs=0.01)
        assert theirs.ifi / ours.ifi - 1 == pytest.approx(0.0946, abs=0.001)

    @needs_files
    def test_the_published_data_prefers_the_correction(self):
        """Not two lawyers arguing: the DGFiP aggregate discriminates.

        Reconstructing the aggregate base from the published per-tranche tax gives
        -6.46 % against the independently published aggregate without the forfait, and
        -10.92 % with it. Every unmodelled relief lowers tax and so pushes the
        reconstruction DOWN, which puts the truth above both — so the reading that
        lands closer from below is the better one.
        """
        from scripts.verify_ifi import barometer, tax_on

        aggregate = ifi_cells.aggregate()
        scale = barometer(ifi_cells.TRANCHE_YEAR)

        def reconstruct(uplift: float) -> float:
            total = 0.0
            for tranche in ifi_cells.tranches():
                low, high = 0.0, 1e9
                for _ in range(200):
                    mid = (low + high) / 2
                    if tax_on(mid * (1 + uplift), scale) < tranche.mean_ifi_eur:
                        low = mid
                    else:
                        high = mid
                total += (low + high) / 2 * tranche.foyers
            return total

        without = reconstruct(0.0) / aggregate.base_eur - 1
        with_forfait = reconstruct(0.05) / aggregate.base_eur - 1
        assert without == pytest.approx(-0.0646, abs=0.002)
        assert with_forfait == pytest.approx(-0.1092, abs=0.002)
        assert without > with_forfait, (
            "the forfait makes the fit worse, and both are below because the "
            "unmodelled reliefs can only reduce tax"
        )


# --- M2: the cells, and the zero-calibration mechanical check -------------------------


class TestCells:
    """All validation, no calibration — and the tests must not quietly create any.

    Every assertion here is against a PUBLISHED number or against an internal property
    nothing forces. If one ever needs a tuned constant to pass, the module's claim is
    gone and the constant is the bug.
    """

    @needs_files
    def test_our_scale_arithmetic_matches_the_engines(self):
        """`bareme.tax_on` reimplements `isf_ifi_iai`; this stops it drifting.

        The duplication is deliberate — inverting a tax takes ~200 evaluations and 200
        simulations per cell is not a thing to do — so the reimplementation is checked
        against the engine over a ladder that crosses every bracket.
        """
        from openfisca_core.simulations import SimulationBuilder

        # The CORRECTED baseline, so the forfait is off and the assiette is the base.
        # This compares the SCALE, and the base convention would otherwise confound it.
        from impots.engine.system import baseline
        from impots.patrimoine import bareme

        scale = bareme.scale_at(2024)
        system = baseline()
        for base in (900_000, 1_299_999, 1_500_000, 2_570_000, 4_000_000,
                     5_000_000, 9_999_999, 12_000_000, 30_000_000):
            situation = {
                "individus": {"M": {"salaire_imposable": {"2024": 10_000_000}}},
                "familles": {"f": {"parents": ["M"]}},
                # b1cg carries the declared furniture, which suppresses the 5 % forfait
                # so this compares the SCALE alone rather than the base convention.
                "foyers_fiscaux": {"ff": {"declarants": ["M"],
                                          "b1ac": {"2024": base},
                                          "b1cg": {"2024": 0.0}}},
                "menages": {"m": {"personne_de_reference": ["M"]}},
            }
            simulation = SimulationBuilder().build_from_entities(system, situation)
            engine = float(simulation.calculate("isf_ifi_iai", "2024")[0])
            assert engine == pytest.approx(bareme.tax_on(base, scale), rel=1e-6), base

    @needs_files
    def test_every_cell_mean_lands_inside_its_own_tranche(self):
        """D-078's first falsifiable property, as the cells' own validation."""
        from impots.patrimoine.cells import mechanical_check

        check = mechanical_check()
        assert check.every_mean_inside_its_tranche
        for cell in check.cells:
            assert cell.tranche.lower_eur <= cell.implied_mean_base_eur <= cell.tranche.upper_eur
            # And strictly inside, not pinned to a bound — a mean sitting exactly on a
            # boundary would mean the inversion saturated rather than solved.
            assert cell.implied_mean_base_eur > cell.tranche.lower_eur, cell.label

    @needs_files
    def test_the_shortfall_has_the_right_sign_and_is_apportioned_not_tolerated(self):
        """The second falsifiable property, plus §2's demand that residuals be
        quantified and explained rather than accepted."""
        from impots.patrimoine.cells import mechanical_check

        check = mechanical_check()
        assert check.shortfall_has_the_right_sign
        assert check.shortfall_share == pytest.approx(0.0646, abs=0.002)
        # Dons: the largest single explanation, and computed from a PUBLISHED total.
        assert check.dons_explains_eur / check.shortfall_eur == pytest.approx(0.58, abs=0.03)
        # Décote: small, and an upper bound by construction.
        assert 0 < check.decote_explains_at_most_eur / check.shortfall_eur < 0.06
        # What is left is named and NOT assigned to the plafonnement by difference.
        assert check.unexplained_eur > 0
        assert check.unexplained_eur / check.shortfall_eur == pytest.approx(0.39, abs=0.04)

    @needs_files
    def test_the_cells_reproduce_the_published_counts_and_tax_exactly(self):
        """Because they are READ from them. This asserts arithmetic, not truth —
        and says so, which is the ledger rule."""
        from impots.patrimoine.cells import mechanical_check

        check = mechanical_check()
        assert sum(c.foyers for c in check.cells) == pytest.approx(
            check.aggregate.exact_foyers, rel=1e-4)
        assert sum(c.published_ifi_eur for c in check.cells) == pytest.approx(
            check.aggregate.ifi_eur, rel=1e-4)

    @needs_files
    def test_nothing_in_the_cells_is_calibrated(self):
        """The module's distinctive property. Name the implementation that fails it.

        A grep for "calibrat" would be defeated by this module's own docstring, which
        uses the word six times to say it does not — the D-071 lesson, that a
        name-based rule loses to name reuse. So the test is behavioural instead.

        The implementation this catches: a factor chosen to close the gap. Anyone who
        fitted one would drive the shortfall to zero, and would break the proportional
        response below, because a fitted constant does not move with its input.
        """
        from impots.patrimoine import bareme, ifi_cells
        from impots.patrimoine.cells import cells, mechanical_check

        check = mechanical_check()
        assert check.shortfall_share > 0.02, (
            "the reconstruction now matches the published aggregate almost exactly. "
            "Nothing in this module should be able to achieve that — if a factor was "
            "introduced to close the gap, the module's zero-calibration claim is gone"
        )

        # And the cells must respond proportionally to their published input. A cell
        # holding a fitted constant would not move when the scale it inverts moves.
        scale = bareme.scale_at(2024)
        doubled = [(threshold, rate * 2) for threshold, rate in scale]
        for cell, tranche in zip(cells(), ifi_cells.tranches(), strict=True):
            halved = bareme.invert(tranche.mean_ifi_eur, doubled)
            assert halved < cell.implied_mean_base_eur, (
                f"{cell.label}: doubling every rate did not lower the implied base — "
                f"it is not being derived from the published tax at all")


class TestPlacement:
    """The bracket over placements the published data permits.

    The property that makes this trustworthy is that it produces ZERO width where
    placement cannot matter. A bracket that is always wide is not measuring anything.
    """

    @needs_files
    def test_no_published_tranche_contains_a_bareme_kink(self):
        """The structural fact the whole class rests on.

        Published tranches are 1,3-2,57 / 2,57-5 / 5-10 / 10-∞; barème thresholds are
        0,8 / 1,3 / 2,57 / 5 / 10. They coincide, so tax is AFFINE inside every cell and
        E[f(W)] = f(E[W]) exactly. If DGFiP ever re-cuts its tranches this fails, and it
        should: the baseline would then carry placement uncertainty it does not have now.
        """
        from impots.patrimoine import bareme, placement
        from impots.patrimoine.cells import cells

        scale = bareme.scale_at(2024)
        for cell in cells():
            assert not placement.has_interior_kink(cell, scale), cell.label

    @needs_files
    def test_the_baseline_band_is_a_point_not_an_interval(self):
        """Zero width where placement cannot matter — the anti-theatre check."""
        from impots.patrimoine import bareme, placement
        from impots.patrimoine.cells import cells

        scale = bareme.scale_at(2024)
        for cell in cells()[:-1]:  # the open cell is handled separately
            low, high = placement.band(cell, scale)
            assert high - low == pytest.approx(0.0, abs=1.0), (
                f"{cell.label}: the bracket invented {high - low:,.0f} EUR of width on a "
                f"tranche the scale does not cut"
            )

    @needs_files
    def test_both_placements_reproduce_the_published_mean(self):
        """What makes them consistent with the publication rather than alternatives.

        A uniform placement — which PHASE5_SPEC §2 proposes — would NOT: uniform on
        [1,3 M, 2,57 M] has mean 1,935 M against the implied 1,7052 M, so it contradicts
        the published tax it is supposed to respect.
        """
        from impots.patrimoine import placement
        from impots.patrimoine.cells import cells

        for cell in cells()[:-1]:
            for built in (placement.point_mass(cell),
                          placement.extremal(cell)):
                assert built.mean() == pytest.approx(cell.implied_mean_base_eur, rel=1e-9)
                assert sum(share for _, share in built.points) == pytest.approx(1.0)
        # And the uniform mean really does differ, which is why it was not used.
        first = cells()[0]
        uniform_mean = (first.tranche.lower_eur + first.tranche.upper_eur) / 2
        assert abs(uniform_mean - first.implied_mean_base_eur) > 200_000

    @needs_files
    def test_a_reform_that_cuts_a_tranche_opens_a_real_band(self):
        """And the width is a fact about the publication, not a modelling choice.

        Moving the seuil to 2 M puts a kink inside the first tranche. At the point
        placement every foyer sits at 1,7052 M and nobody pays; at the mean-preserving
        spread some sit at 2,57 M and do. The published numbers cannot distinguish these,
        so the answer is an interval and saying otherwise would be inventing a density.
        """
        from impots.patrimoine import placement
        from impots.patrimoine.cells import cells

        moved = [(2_000_000.0, 0.007), (2_570_000.0, 0.01),
                 (5_000_000.0, 0.0125), (10_000_000.0, 0.015)]
        first = cells()[0]
        assert placement.has_interior_kink(first, moved)
        low, high = placement.band(first, moved)
        assert low == pytest.approx(0.0, abs=1.0), "point placement sits below the seuil"
        assert high > 100e6, "the spread placement puts real mass above it"

    @needs_files
    def test_the_open_top_cell_refuses_an_invented_ceiling(self):
        """The finding that decides whether a Zucman floor is priceable here at all.

        The last tranche runs from 10 M with no published ceiling, so the maximising
        placement can put mass arbitrarily high and no upper bound exists. Supplying a
        convenient default would be exactly the invented density this class refuses.
        """
        from impots.patrimoine import bareme, placement
        from impots.patrimoine.cells import cells

        top = cells()[-1]
        assert top.tranche.upper_eur == float("inf")
        with pytest.raises(placement.PlacementError, match="open at the top"):
            placement.extremal(top)
        # With a sourced ceiling it prices, and the answer MOVES with the ceiling —
        # which is the point: the number is a function of an assumption, not a fact.
        scale = bareme.scale_at(2024)
        _, high_50 = placement.band(top, scale, ceiling=50e6)
        _, high_200 = placement.band(top, scale, ceiling=200e6)
        assert high_200 > high_50

    @needs_files
    def test_the_reform_band_prices_both_sides_under_the_same_placement(self):
        """Otherwise the band would carry a placement difference as if it were policy."""
        from impots.patrimoine import bareme, placement
        from impots.patrimoine.cells import cells

        scale = bareme.scale_at(2024)
        doubled = [(t, r * 2) for t, r in scale]
        band = placement.reform_band(cells(), scale, doubled)
        # Rates only, no kink moved: the band must be a point despite a huge reform.
        assert band.is_a_point, (
            f"doubling every rate opened a {band.width_eur:,.0f} EUR band, but it moves "
            f"no threshold — the width would be placement leaking into policy"
        )
        assert band.low_eur > 1e9
        assert band.open_cell_excluded is True, "the top cell has no bounded spread"


# --- M3: regimes, corrections, and the floor that cannot be priced --------------------


class TestRegimes:
    """The ISF revival, and the silent-failure API it had to route around."""

    def test_the_isf_and_ifi_parameters_are_identical(self):
        """The finding that shapes the whole regime switch.

        Every ISF-2017 parameter equals its IFI-2024 counterpart — barème, décote,
        plafonnement, abattement, forfait. So an ISF revival is not a different schedule:
        it is the same schedule on a WIDER BASE. If this ever stops being true the
        regime module's premise is gone and it must be rewritten, not patched.
        """
        from openfisca_france import FranceTaxBenefitSystem

        system = FranceTaxBenefitSystem()

        def read(node, year, path):
            current = system.get_parameters_at_instant(f"{year}-01-01").taxation_capital
            for part in (node + "." + path).split("."):
                current = getattr(current, part)
            return current

        isf, ifi = "impot_solidarite_fortune_isf_1989_2017", \
                   "impot_fortune_immobiliere_ifi_partir_2018"
        old, new = read(isf, 2017, "bareme"), read(ifi, 2024, "bareme")
        assert list(old.thresholds) == list(new.thresholds)
        assert list(old.rates) == list(new.rates)
        for path in ("decote.borne_inferieure_decote", "decote.taux_decote",
                     "decote.parametre_calcul_decote", "plaf.plafonnement_taux_imposition",
                     "reduc_exo.abattement_residence_principale",
                     "forfait_mobilier.majoration_forfaitaire"):
            assert read(isf, 2017, path) == read(ifi, 2024, path), path

    def test_the_financial_base_is_retired_at_2017_and_the_revival_lifts_it(self):
        """And the baseline must be untouched afterwards."""
        from openfisca_france import FranceTaxBenefitSystem

        from impots.engine.system import baseline
        from impots.patrimoine.regimes import RETIRED_AT_2017, is_revived, isf_1989_2017

        raw = FranceTaxBenefitSystem()
        for name in RETIRED_AT_2017:
            assert str(raw.get_variable(name).end) == "2017-12-31", name
        assert not is_revived(baseline())
        assert is_revived(isf_1989_2017(baseline()))
        assert not is_revived(baseline()), "the revival mutated the shared baseline"

    def test_update_variable_would_have_failed_silently(self):
        """The kill test for choosing `replace_variable`, and a documented API trap.

        `update_variable` keeps every attribute the new class does not override — the
        core's own docstring says so — so redefining the variable without an `end` leaves
        the 2017 end date in place, raises nothing, and prices unchanged. That is the
        read-back-blind class in the variable API rather than the parameter tree.
        """
        from openfisca_core.reforms import Reform
        from openfisca_core.variables import Variable
        from openfisca_france.model.prelevements_obligatoires import isf as module

        from impots.engine.system import baseline

        class NaiveRevival(Reform):
            def apply(self) -> None:
                original = module.isf_droits_sociaux
                namespace = {k: v for k, v in vars(original).items()
                             if not k.startswith("__")}
                namespace.pop("end", None)
                self.update_variable(type("isf_droits_sociaux", (Variable,), namespace))

        naive = NaiveRevival(baseline())
        assert str(naive.get_variable("isf_droits_sociaux").end) == "2017-12-31", (
            "update_variable now clears an inherited end date — if core changed this, "
            "the docstring in patrimoine.regimes is stale and replace_variable may no "
            "longer be necessary"
        )

    def test_financial_wealth_is_taxed_under_isf_and_ignored_under_ifi(self):
        """The regime difference, priced end to end on one household."""
        from openfisca_core.simulations import SimulationBuilder

        from impots.api.schemas import HouseholdInput
        from impots.engine.situations import build_situation
        from impots.engine.system import baseline
        from impots.patrimoine.regimes import isf_1989_2017

        household = HouseholdInput.model_validate({
            "adults": [{"salaire_brut_annuel": 1_200_000, "annee_naissance": 1970}],
            "patrimoine": {"autres_immeubles_batis": 2_000_000,
                           "valeurs_mobilieres": 2_500_000}})
        situation = build_situation(household, 2024)

        def priced(system):
            simulation = SimulationBuilder().build_from_entities(system, situation)
            return (float(simulation.calculate("assiette_isf_ifi", "2024")[0]),
                    -float(simulation.calculate("isf_ifi", "2024")[0]))

        ifi_base, ifi_tax = priced(baseline())
        isf_base, isf_tax = priced(isf_1989_2017(baseline()))
        assert ifi_base == pytest.approx(2_000_000.0), "financial wealth is dropped"
        assert isf_base == pytest.approx(4_500_000.0), "and revived"
        assert isf_tax > ifi_tax * 3


class TestCorrections:
    """Every departure from openfisca carries its citation and its kill test."""

    def test_each_correction_names_a_kill_test_that_exists(self):
        """A correction whose kill test does not exist cannot be retired when openfisca
        fixes the thing it corrects, so it would live forever."""
        from pathlib import Path

        from impots.patrimoine.corrections import CORRECTIONS

        source = Path("tests/test_patrimoine.py").read_text(encoding="utf-8")
        assert CORRECTIONS
        for correction in CORRECTIONS:
            assert correction.citation.startswith("CGI art."), correction.name
            assert correction.decision.startswith("D-0"), correction.name
            assert f"def {correction.kill_test}" in source, (
                f"{correction.name} names kill test {correction.kill_test}, which does "
                f"not exist — the correction could never be retired"
            )

    def test_the_corrected_baseline_is_what_every_path_uses(self):
        """One IFI figure in the codebase, not a corrected one and a raw one."""
        from impots.api.schemas import HouseholdInput
        from impots.engine import compute
        from impots.patrimoine.ifi import IfiInputs, price

        wire = compute(HouseholdInput.model_validate({
            "adults": [{"salaire_brut_annuel": 1_200_000, "annee_naissance": 1970}],
            "patrimoine": {"autres_immeubles_batis": 2_000_000}}), 2024, tier="full")
        module = price(IfiInputs(autres_immeubles_batis=2_000_000,
                                 revenu_imposable=1_200_000 * 0.78))
        assert wire.baseline["ifi"] == pytest.approx(7_400.0, abs=0.01)
        assert module.ifi == pytest.approx(wire.baseline["ifi"], abs=0.01)


class TestZucmanFloor:
    """A refusal with its reasons is a result."""

    @needs_files
    def test_the_floor_is_refused_and_says_why(self):
        from impots.patrimoine import bareme, zucman
        from impots.patrimoine.cells import cells

        with pytest.raises(zucman.ZucmanAnchorError) as raised:
            zucman.price_floor(cells(), bareme.scale_at(2024), threshold_eur=100e6,
                               rate=0.02, assumed_ceiling_eur=500e6)
        message = str(raised.value)
        assert "CONSTRUCTION" in message
        assert "ouverte" in message.lower()
        assert "revenu" in message.lower(), "the income-tax credit reason must be given"

    def test_the_requirements_are_data_so_the_refusal_cannot_drift(self):
        from impots.patrimoine.zucman import REQUIREMENTS, why_not_priceable

        missing = [what for what, have, _ in REQUIREMENTS if not have]
        assert len(missing) == 3, "three independent reasons, not one"
        text = why_not_priceable()
        for what in missing:
            assert what in text
        # And the one thing we DO have is recorded, so the list is not just a complaint.
        assert any(have for _, have, _ in REQUIREMENTS)


class TestIfiBareme:
    """The scale knob, and the silent merge the validator exists to prevent."""

    def test_the_merge_is_real_and_sums_the_rates(self):
        """Measured on the engine, not assumed. This is the kill test for the validator.

        Writing bracket 0's threshold onto bracket 1's makes openfisca collapse the two
        and SUM their rates: five brackets become four and the head rate becomes 0,012,
        which is 0,005 + 0,007. Nothing raises. The 1,3-2,57 M band silently doubles.

        The engine's own surplus-bracket trick depends on this merge — with a rate of
        ZERO, where summing is harmless — so it cannot simply be forbidden in the write
        path. The protection has to sit where the whole scale is visible, which is the
        spec validator.
        """
        from openfisca_core.reforms import Reform

        from impots.engine.system import baseline

        instant = "2024-01-01"

        def scale_of(system):
            node = (system.get_parameters_at_instant(instant).taxation_capital
                    .impot_fortune_immobiliere_ifi_partir_2018.bareme)
            return list(zip(node.thresholds, node.rates, strict=True))

        class Collide(Reform):
            def apply(self) -> None:
                def modify(parameters):
                    brackets = (parameters.taxation_capital
                                .impot_fortune_immobiliere_ifi_partir_2018.bareme.brackets)
                    brackets[0].threshold.update(start=instant, value=1_300_000.0)
                    return parameters

                self.modify_parameters(modifier_function=modify)

        assert len(scale_of(baseline())) == 5
        merged = scale_of(Collide(baseline()))
        assert len(merged) == 4, "the merge no longer happens — the validator may be moot"
        assert merged[0] == (1_300_000.0, pytest.approx(0.012)), "0,005 + 0,007"

    def test_the_validator_refuses_equal_thresholds(self):
        import pydantic

        from impots.api.schemas import ReformSpec

        with pytest.raises(pydantic.ValidationError, match="FUSIONNÉES"):
            ReformSpec(ifi_bareme=[{"threshold": 1_300_000, "rate": 0.005},
                                   {"threshold": 1_300_000, "rate": 0.007}])
        # And a legitimate scale is accepted, so the guard is not simply refusing.
        ReformSpec(ifi_bareme=[{"threshold": 1_300_000, "rate": 0.01},
                               {"threshold": 5_000_000, "rate": 0.02}])

    def test_the_first_threshold_is_not_forced_to_zero_unlike_the_ir_scale(self):
        """The IFI exempts everything below 800 000 by having NO bracket there.

        The IR validator requires a first threshold of 0 because a marginal scale must
        cover every euro of income. Copying that rule here would forbid the actual legal
        scale, whose first bracket starts at 800 000.
        """
        import pydantic

        from impots.api.schemas import ReformSpec

        ReformSpec(ifi_bareme=[{"threshold": 800_000, "rate": 0.005},
                               {"threshold": 1_300_000, "rate": 0.007}])
        with pytest.raises(pydantic.ValidationError):
            ReformSpec(ir_bareme=[{"threshold": 800_000, "rate": 0.005},
                                  {"threshold": 1_300_000, "rate": 0.007}])

    def test_the_scale_knob_prices_end_to_end_and_matches_hand_arithmetic(self):
        from impots.api.schemas import HouseholdInput, ReformSpec
        from impots.engine import compute

        household = HouseholdInput.model_validate({
            "adults": [{"salaire_brut_annuel": 5_000_000, "annee_naissance": 1970}],
            "patrimoine": {"autres_immeubles_batis": 20_000_000}})
        two_brackets = ReformSpec.model_validate({"ifi_bareme": [
            {"threshold": 1_300_000, "rate": 0.01},
            {"threshold": 5_000_000, "rate": 0.02}]})
        result = compute(household, 2024, reform=two_brackets, tier="full")
        # 3,7 M at 1 % plus 15 M at 2 %, by hand.
        expected = (5_000_000 - 1_300_000) * 0.01 + (20_000_000 - 5_000_000) * 0.02
        assert expected == pytest.approx(337_000.0)
        assert result.reform["ifi"] == pytest.approx(expected, abs=0.01)
        assert result.baseline["ifi"] == pytest.approx(248_190.0, abs=0.01)

    def test_replacing_five_brackets_with_two_does_not_leave_a_live_surplus(self):
        """The surplus-collapse trick, checked on the IFI scale rather than assumed.

        Leftover active brackets take the top threshold and a rate of ZERO. If they took
        a non-zero rate the merge would MULTIPLY the top rate instead of leaving it
        alone, and the answer above would be wrong by exactly that factor.
        """
        from impots.api.schemas import ReformSpec
        from impots.engine.reforms import make_reform
        from impots.engine.system import baseline

        spec = ReformSpec.model_validate({"ifi_bareme": [
            {"threshold": 1_300_000, "rate": 0.01},
            {"threshold": 5_000_000, "rate": 0.02}]})
        reformed = make_reform(spec, 2024, "test-ifi-scale")(baseline())
        node = (reformed.get_parameters_at_instant("2024-01-01").taxation_capital
                .impot_fortune_immobiliere_ifi_partir_2018.bareme)
        scale = list(zip(node.thresholds, node.rates, strict=True))
        assert scale[0] == (1_300_000.0, pytest.approx(0.01))
        assert scale[-1][1] == pytest.approx(0.02), (
            "the top rate was multiplied by the collapsed surplus brackets")


# --- M4: the composition scaling ------------------------------------------------------


class TestComposition:
    """Banded, flat, and refusing the per-tranche factor the spec asked for."""

    SOURCE = ifi_cells.RAW / "insee_rpm2023_patrimoine_composition.html"

    @pytest.mark.skipif(not SOURCE.exists(), reason="INSEE source not downloaded")
    def test_the_p99_composition_matches_the_published_row(self):
        """The transcription, checked letter by letter against the manifested file.

        D-026: a figure this project uses comes from the file, not from prose about the
        file. The row is «Supérieur à P99» in figure 1 and reads 27 36 5 29 3 -4 -3.
        """
        import re

        from impots.patrimoine.composition import P99_COMPOSITION

        text = self.SOURCE.read_text(encoding="utf-8", errors="ignore")
        label = "Supérieur à P99"
        index = text.find(label)
        assert index > 0, "the published row is no longer in the file"
        # AFTER the label: "P99" itself contains a 99 that would be read as the first
        # column. The first version of this test asserted 99 == 27 and was right to.
        after = text[index + len(label):index + len(label) + 400]
        block = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", after))
        numbers = [float(n) for n in re.findall(r"-?\d+", block)[:7]]
        assert numbers[:5] == [27.0, 36.0, 5.0, 29.0, 3.0], block[:160]
        assert P99_COMPOSITION["financier"] == 27.0
        assert P99_COMPOSITION["immobilier"] == 36.0
        assert (P99_COMPOSITION["professionnel"]
                + P99_COMPOSITION["professionnel_entreprise"]) == 34.0

    def test_professional_wealth_is_excluded_because_the_isf_exempted_it(self):
        """The legal point worth 34 points of base.

        Biens professionnels were outside the ISF base (CGI arts. 885 N-R, per the last
        paragraph of art. 885 A). Counting them would make the factor 100/36 = 2,78
        instead of 66/36 = 1,83 — a 34-point error in every ISF figure the module could
        produce, resting on a legal fact rather than on arithmetic.
        """
        from impots.patrimoine.composition import (
            ISF_TAXABLE_COMPONENTS,
            P99_COMPOSITION,
            raw_ratio,
        )

        assert "professionnel" not in ISF_TAXABLE_COMPONENTS
        assert "professionnel_entreprise" not in ISF_TAXABLE_COMPONENTS
        assert raw_ratio() == pytest.approx(66.0 / 36.0, rel=1e-9)
        naive = sum(v for v in P99_COMPOSITION.values() if v > 0) / P99_COMPOSITION["immobilier"]
        assert naive == pytest.approx(100.0 / 36.0, rel=1e-9)
        assert naive - raw_ratio() > 0.9, "the mistake this test exists to prevent"

    def test_the_factor_is_a_band_and_never_a_point(self):
        from impots.patrimoine.composition import factor

        band = factor()
        assert band.width > 0.15, "a band this narrow would be pretending to precision"
        assert band.low < band.central < band.high
        low, high = band.scale(466.79e9)
        assert high > low
        assert 800e9 < low < 900e9 and 900e9 < high < 1_000e9

    def test_the_per_tranche_factor_is_refused_with_its_reason(self):
        """One published fractile above D9, four tranches. The refusal is the result."""
        from impots.patrimoine import composition

        with pytest.raises(composition.CompositionError) as raised:
            composition.per_tranche_factor()
        message = str(raised.value)
        assert "PAR TRANCHE" in message
        assert "P99" in message
        assert "top 5" in message, "the BdF limitation must be cited, not just implied"

    def test_the_banque_de_france_source_states_its_own_limit(self):
        """Manifested for its limitation, not its numbers — so the limitation is checked.

        The handoff named the DWA as the composition source. Its methodology says it
        cannot go finer than the top 10 % or top 5 %, and IFI redevables are the top
        0,45 %. That sentence is why this module reads INSEE instead.
        """
        source = ifi_cells.RAW / "bdf_comptes_distributionnels_methodologie_2024.pdf"
        if not source.exists():
            pytest.skip("BdF methodology not downloaded")
        pypdf = pytest.importorskip("pypdf")
        import re

        text = "\n".join(page.extract_text() or ""
                         for page in pypdf.PdfReader(str(source)).pages)
        flat = re.sub(r"\s+", " ", text)
        assert "ne permettent pas pour le moment d’aller plus finement que le top 10%" in flat

    def test_the_degraded_mode_is_available_and_assumes_nothing(self):
        """Degraded-but-true beats confidently scaled, by standing ruling."""
        from impots.patrimoine.composition import IFI_BASE_LOWER_BOUND

        low, high = IFI_BASE_LOWER_BOUND.scale(466.79e9)
        assert low == high == pytest.approx(466.79e9)
        assert IFI_BASE_LOWER_BOUND.width == 0.0

    def test_the_vintages_are_stated_and_are_three_different_years(self):
        from impots.patrimoine.composition import VINTAGES

        assert set(VINTAGES) == {"composition", "cells", "law_priced"}
        assert "2020-2021" in VINTAGES["composition"]
        assert "2024" in VINTAGES["cells"]


# --- M4: the behavioural channels and the enforcement dial ----------------------------


class TestWealthChannels:
    """Two channels, deliberately different units, and a dial that moves no parameter."""

    @staticmethod
    def _store():
        from impots.behavioural import store

        return store.load()

    def test_the_brief_s_three_figures_are_not_in_the_paper(self):
        """0-for-3, and the store records the refusals rather than hiding them.

        The brief asserted "~0.05", "~0.55" and "Spain 0.64". Verified against the PDF:
        0.05 and 0.64 have zero occurrences, and 0.55 appears twice as a 2010 marginal
        RATE and an appendix cell. A row that quietly vanished would make a channel
        narrow with no visible cause.
        """
        store = self._store()
        assert "wealth_elasticity_spain_benchmark" in store.rejected
        assert "0.64" in store.rejected["wealth_elasticity_spain_benchmark"]
        assert "wealth_migration_response" in store.rejected
        assert "wealth_elasticity_spain_benchmark" not in store.parameters

    def test_the_rate_elasticity_is_centred_on_zero_and_covers_its_standard_errors(self):
        """Central zero is the paper's conclusion, not a hedge.

        And the ceiling is the largest estimate plus two standard errors — 0,14 + 2 ×
        0,11 — because a band narrower than its own source's sampling uncertainty would
        be more wrong than no band at all.
        """
        parameter = self._store()["wealth_tax_rate_elasticity"]
        assert parameter.central == 0.0
        assert parameter.low == 0.0
        assert parameter.high == pytest.approx(0.36, abs=0.001)
        assert parameter.high > 0.14 + 0.11, "must cover more than one standard error"

    def test_the_disclosure_row_is_not_an_elasticity(self):
        """Its unit is percentage points of annual growth. Multiplying it by a rate
        change would be a category error that happens to typecheck."""
        parameter = self._store()["wealth_disclosure_growth_effect_pp"]
        assert parameter.key.endswith("_pp")
        assert parameter.low >= 0.13 and parameter.high <= 0.50
        assert parameter.central == pytest.approx(0.28)
        assert "élasticité" in parameter.applies_to.lower()
        assert "jamais" in parameter.applies_to.lower(), "the warning must be in the row"

    def test_the_two_channels_are_disjoint(self):
        """A rate reform must not fire the enforcement channel, and vice versa."""
        import numpy as np

        from impots.api.schemas import ReformSpec
        from impots.behavioural import channels

        store = self._store()
        rate = ReformSpec.model_validate({"ifi_bareme": [
            {"threshold": 1_300_000, "rate": 0.01},
            {"threshold": 5_000_000, "rate": 0.02}]})
        dial = ReformSpec(ifi_obligations_declaratives="renforcees")

        assert channels.wealth_rate_response(
            store, rate, wealth_base_eur=466e9, marginal_rate_baseline=0.007,
            marginal_rate_reform=0.02, draws=64, rng=np.random.default_rng(0)).applies
        assert not channels.disclosure_response(store, rate, wealth_base_eur=466e9).applies
        assert channels.disclosure_response(
            store, dial, wealth_base_eur=466e9, draws=64,
            rng=np.random.default_rng(0)).applies
        assert not channels.wealth_rate_response(
            store, dial, wealth_base_eur=466e9, marginal_rate_baseline=0.007,
            marginal_rate_reform=0.007).applies

    def test_the_disclosure_channel_stays_out_of_the_revenue_band(self):
        """Because its unit is a growth rate, and cumulating one needs a horizon.

        The one-year euro equivalent is offered in the diagnostics with the horizon
        named, which is the honest half of the trade.
        """
        import numpy as np

        from impots.api.schemas import ReformSpec
        from impots.behavioural import channels

        result = channels.disclosure_response(
            self._store(), ReformSpec(ifi_obligations_declaratives="renforcees"),
            wealth_base_eur=466.79e9, draws=256, rng=np.random.default_rng(1))
        assert result.unit == "%"
        assert result.in_revenue_band is False
        assert result.diagnostics["horizon_years"] == 1
        assert result.diagnostics["one_year_base_equivalent_eur"] > 0

    def test_tightening_and_loosening_have_opposite_signs(self):
        """And the symmetry is an ASSUMPTION, said so in the row and here.

        The study observed a loosening. Applying the same magnitude to a tightening is
        the only thing the evidence permits, and it is not a measurement.
        """
        import numpy as np

        from impots.api.schemas import ReformSpec
        from impots.behavioural import channels

        store = self._store()
        tighten = channels.disclosure_response(
            store, ReformSpec(ifi_obligations_declaratives="renforcees"),
            wealth_base_eur=466e9, draws=256, rng=np.random.default_rng(2))
        loosen = channels.disclosure_response(
            store, ReformSpec(ifi_obligations_declaratives="allegees"),
            wealth_base_eur=466e9, draws=256, rng=np.random.default_rng(2))
        assert tighten.central > 0 > loosen.central
        assert tighten.central == pytest.approx(-loosen.central, rel=1e-9)
        assert "hypothèse de symétrie" in tighten.message

    def test_the_enforcement_dial_moves_no_mechanical_output(self):
        """The only lever here that changes nothing in the calculation.

        Disclosure requirements are not a parameter of the tax code, so this dial acts
        on the behavioural band alone. It is therefore deliberately NOT in SCALAR_KNOBS,
        whose standing rule is that every knob moves an output — a rule this dial would
        fail for the right reason.
        """
        from impots.api.schemas import HouseholdInput, ReformSpec
        from impots.engine import compute
        from impots.engine.reforms import SCALAR_KNOBS

        assert "ifi_obligations_declaratives" not in SCALAR_KNOBS
        household = HouseholdInput.model_validate({
            "adults": [{"salaire_brut_annuel": 1_200_000, "annee_naissance": 1970}],
            "patrimoine": {"autres_immeubles_batis": 3_000_000}})
        result = compute(household, 2024,
                         reform=ReformSpec(ifi_obligations_declaratives="renforcees"),
                         tier="full")
        assert result.reform["ifi"] == pytest.approx(result.baseline["ifi"], abs=0.01)


# --- M5: the reconciliation section ---------------------------------------------------


class TestPatrimoineReconciliation:
    """All validation or context — the ledger property, asserted rather than claimed."""

    @needs_files
    def test_the_calibration_table_is_empty_and_that_is_the_point(self):
        """The module's distinctive property, visible on the page.

        DGFiP publishes the population, so the cells are read rather than fitted and
        there is no margin to spend. The household report has four calibration lines;
        this one must have none. The empty table IS the proof, and it stops being proof
        the moment anyone adds a row to it.
        """
        from impots.patrimoine import reconcile

        lines = reconcile.build_lines()
        assert lines, "a section with no lines proves nothing either"
        assert not [line for line in lines if line.use == "calibration"]
        report = reconcile.render()
        table = report[report.index("## Calibration targets (spent)"):
                       report.index("## Validation lines")]
        assert "|---|" in table, "the header must still render"
        assert table.count("\n|") == 2, "header and separator only — no data rows"

    @needs_files
    def test_the_model_is_not_judged_against_the_budget_line(self):
        """The spec said to, and following it would have printed accounting as error.

        Line 1406 books 2 739 M EUR for exécution 2024; the statistical bulletin reports
        2 159 M EUR for the same assessment year. The +26,9 % between them is basis, not
        model: the budget line is cash collection including prior-year recovery and
        contrôle fiscal, and the bulletin is émissions, which is what the engine computes.
        """
        from impots.patrimoine import reconcile

        budget = next(line for line in reconcile.build_lines() if "1406" in line.label)
        assert budget.use == "context"
        assert budget.simulated is None, "scoring it would be the mistake"
        assert budget.status == "not modelled"
        ratio = reconcile.IFI_LIGNE_BUDGETAIRE.value / reconcile.IFI_EMISSIONS.value - 1
        assert ratio == pytest.approx(0.269, abs=0.005)

    @needs_files
    def test_dgfip_itself_says_the_two_series_differ(self):
        """Not our inference — the publisher of both, in the bulletin the cells come from.

        Checked against the manifested file so the claim cannot outlive the sentence.
        """
        import re

        source = ifi_cells.RAW / "dgfip_stats_33_ifi_2024.pdf"
        if not source.exists():
            pytest.skip("n° 33 not downloaded")
        pypdf = pytest.importorskip("pypdf")
        text = "\n".join(page.extract_text() or ""
                         for page in pypdf.PdfReader(str(source)).pages)
        flat = re.sub(r"\s+", " ", text)
        assert ("Les données budgétaires publiées par ailleurs peuvent donc être "
                "différentes des montants présentés dans cette publication") in flat

    @needs_files
    def test_the_tautological_line_is_labelled_context_not_validation(self):
        """The cells are read from the publication, so their sum reproduces it.

        Presenting that as validation would be the zero-masked class in its purest form:
        a comparison that cannot fail, printed as though it could.
        """
        from impots.patrimoine import reconcile

        line = next(x for x in reconcile.build_lines() if "pour mémoire" in x.label)
        assert line.use == "context"
        assert line.residual == pytest.approx(0.0, abs=1e-4)
        # The load-bearing claim, not a word I expected to find: the cells are READ from
        # this publication, so the note must say so where a reader meets the zero.
        note = line.note or ""
        assert "LUES" in note and "pas validation" in note

    @needs_files
    def test_the_falsifiable_line_carries_its_decomposition(self):
        """§2 asks that the residual be quantified, not tolerated."""
        from impots.patrimoine import reconcile

        line = next(x for x in reconcile.build_lines() if "inversé" in x.label)
        assert line.use == "validation"
        assert line.residual == pytest.approx(-0.0646, abs=0.002)
        note = line.note or ""
        for fragment in ("dons", "décote", "plafonnement", "nommé et non attribué"):
            assert fragment in note, fragment
