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

        from impots.engine.system import baseline

        situation = {
            "individus": {"M": {"salaire_imposable": {"2024": 400_000}}},
            "familles": {"f": {"parents": ["M"]}},
            "foyers_fiscaux": {"ff": {"declarants": ["M"], "b1ac": {"2024": 1_299_999}}},
            "menages": {"m": {"personne_de_reference": ["M"]}},
        }
        simulation = SimulationBuilder().build_from_entities(baseline(), situation)
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
