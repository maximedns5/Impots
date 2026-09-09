"""F3 M1 — the two references, and the property that proves the second one was needed.

`test_a_freeze_against_current_law_costs_exactly_nothing` is the point of the file. If it
fails, either the barème stopped being frozen (a real event, and this module's premise
would need rewriting) or the reference machinery is not doing what it claims.
"""

from __future__ import annotations

import pytest

from impots import trajectoires as tj

LAW = {
    "bareme": [{"threshold": 0.0, "rate": 0.0},
               {"threshold": 11_600.0, "rate": 0.11},
               {"threshold": 29_579.0, "rate": 0.30},
               {"threshold": 84_577.0, "rate": 0.41},
               {"threshold": 181_917.0, "rate": 0.45}],
    "decote": {"seuil_celib": 897.0, "seuil_couple": 1_486.0},
    "plafond_qf_demi_part": 1_791.0,
}
HYPO = tj.Indexation(rate=0.02, source="2 % ronds, choisis pour être lisibles")


# --------------------------------------------------------------------------- #
# The premise, measured against the real tree
# --------------------------------------------------------------------------- #


def test_the_bareme_is_frozen_from_2026():
    """THE fact this module rests on. Fails the day an LFI indexes again — which is the
    intended behaviour: `LAST_INDEXED_YEAR` would then move, and so would the module."""
    from impots.engine.reforms import read_ir_parameters
    from impots.engine.system import baseline

    tbs = baseline()
    thresholds = {y: [round(b["threshold"])
                      for b in read_ir_parameters(tbs, y)["bareme"]]
                  for y in (2024, 2025, 2026, 2027, 2028)}
    assert thresholds[2024] != thresholds[2025], "2024->2025 devait être indexé"
    assert thresholds[2025] == thresholds[2026] == thresholds[2027] == thresholds[2028]
    assert tj.LAST_INDEXED_YEAR == 2025


def test_a_freeze_against_current_law_costs_exactly_nothing():
    """The falsifiable property the spec demands at M1.

    A barème freeze IS current law from 2026, so pricing it against `reconduit` must
    return exactly zero. That zero is the proof the second reference was necessary rather
    than a refinement: without `indexe` there is no way to put a number on the freeze at
    all.

    Fails if `reconduit` starts silently indexing, or if `price` folds an indexation into
    the reference it was not asked for.
    """
    def run(reform):
        """A stand-in engine whose cost is DERIVED from how far thresholds sit above
        current law — so the zero below is computed, not hard-coded into the stub."""
        if not reform or "ir_bareme" not in reform:
            return 0.0
        shift = (sum(b["threshold"] for b in reform["ir_bareme"])
                 - sum(b["threshold"] for b in LAW["bareme"]))
        return -shift * 1_000.0

    # A «freeze» asks for exactly the thresholds already in force, so the shift is nil.
    freeze = {"ir_bareme": LAW["bareme"]}
    out = tj.price(2028, "reconduit", reform=freeze, law=LAW, run=run)
    assert out.mechanical_eur == 0.0
    assert "rend zéro" in out.caveat and "il n'y a rien à geler" in out.caveat


def test_the_same_freeze_costs_real_money_against_the_indexed_reference():
    """The other half: against `indexe` the freeze is the stealth tax and has a price.

    Fails if `price` does not subtract the indexed reference from the combined run —
    which would fold the entire cost of indexation into every measure priced against it.
    """
    def run(reform):
        # A stand-in engine: cost is proportional to how far thresholds sit above law.
        if not reform or "ir_bareme" not in reform:
            return 0.0
        shift = sum(b["threshold"] for b in reform["ir_bareme"]) - sum(
            b["threshold"] for b in LAW["bareme"])
        return -shift * 1_000.0  # higher thresholds cost the state money

    freeze = {"ir_bareme": LAW["bareme"]}
    out = tj.price(2028, "indexe", reform=freeze, law=LAW, run=run, indexation=HYPO)
    assert out.mechanical_eur > 0, "geler contre une référence indexée doit rapporter"
    assert out.indexation is HYPO


def test_the_indexed_reference_is_not_folded_into_the_measure():
    """A reform that changes NOTHING must cost nothing against `indexe` too.

    This is the subtraction's kill test. If `price` returned the combined run without
    subtracting the indexed reference, a null reform would come back carrying the whole
    cost of indexation — a very large number attributed to a measure that does nothing.
    """
    def run(reform):
        if not reform or "ir_bareme" not in reform:
            return 0.0
        shift = sum(b["threshold"] for b in reform["ir_bareme"]) - sum(
            b["threshold"] for b in LAW["bareme"])
        return -shift * 1_000.0

    out = tj.price(2028, "indexe", reform=None, law=LAW, run=run, indexation=HYPO)
    assert out.mechanical_eur == pytest.approx(0.0, abs=1e-6)


# --------------------------------------------------------------------------- #
# The refusals
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad", ["", "Reconduit", "indexé", "current", "reconduit "])
def test_an_unknown_reference_is_refused(bad):
    """An allowlist, per D-094. A misspelt reference silently answering «reconduit»
    would publish a zero for a freeze and call it a result."""
    with pytest.raises(tj.TrajectoryError, match="inconnue"):
        tj.require_reference(bad)


def test_both_named_references_are_accepted():
    """The kill test for the refusal above."""
    for name in ("reconduit", "indexe"):
        tj.require_reference(name)


def test_the_indexed_reference_demands_a_declared_hypothesis():
    """Fails if `indexe` acquires a default rate — which would be forecasting inflation
    in silence, and phase 4's refusals bind."""
    with pytest.raises(tj.TrajectoryError, match="hypothèse d'indexation déclarée"):
        tj.price(2028, "indexe", reform=None, law=LAW, run=lambda r: 0.0)


def test_an_indexation_without_a_source_is_refused():
    with pytest.raises(tj.TrajectoryError, match="sans source"):
        tj.Indexation(rate=0.02, source="  ")


@pytest.mark.parametrize("rate", [0.9, -0.7, 2.0])
def test_an_implausible_rate_is_refused(rate):
    """50 % a year is not an annual price index; it is a unit error."""
    with pytest.raises(tj.TrajectoryError, match="taux annuel"):
        tj.Indexation(rate=rate, source="s")


# --------------------------------------------------------------------------- #
# The arithmetic
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("year,expected", [
    (2024, 1.0), (2025, 1.0), (2026, 1.02), (2028, 1.02 ** 3),
])
def test_the_uprating_factor_compounds_from_the_last_legislated_year(year, expected):
    """Fails if the factor compounds from the wrong base year — which would shift every
    indexed threshold by a whole year of prices."""
    assert HYPO.factor(year) == pytest.approx(expected)


def test_indexation_moves_thresholds_and_leaves_rates_alone():
    """An indexation moves the brackets, never the rates. Fails if a rate is scaled,
    which would turn a price adjustment into a tax increase."""
    spec = tj.indexation_spec(2028, HYPO, LAW)
    factor = HYPO.factor(2028)
    for got, want in zip(spec["ir_bareme"], LAW["bareme"], strict=True):
        assert got["rate"] == want["rate"]
        assert got["threshold"] == pytest.approx(want["threshold"] * factor, abs=0.01)
    assert spec["decote_seuil_celib"] == pytest.approx(897.0 * factor, abs=0.01)
    assert spec["plafond_qf_demi_part"] == pytest.approx(1_791.0 * factor, abs=0.01)


def test_the_indexed_spec_only_moves_the_knobs_it_declares():
    """`INDEXED_KNOBS` is the stated perimeter, and the caveat calls the result a lower
    bound because a real indexation article moves more. Fails if the two drift apart."""
    spec = tj.indexation_spec(2028, HYPO, LAW)
    assert set(spec) == set(tj.INDEXED_KNOBS)


# --------------------------------------------------------------------------- #
# What travels with every figure
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("reference", ["reconduit", "indexe"])
def test_every_figure_carries_its_reference_and_the_unaged_population_caveat(reference):
    """M2 does not exist, so a trajectory prices future LAW on a 2024 population. Fails
    if that stops being said on every result rather than in a document nobody opens."""
    out = tj.price(2028, reference, reform=None, law=LAW, run=lambda r: 0.0,
                   indexation=HYPO if reference == "indexe" else None)
    assert out.reference == reference
    assert "population n'est PAS vieillie" in out.caveat
    assert reference in out.line()


def test_the_indexed_caveat_says_it_is_a_lower_bound():
    """A real indexation moves the 10 % déduction floors, the pension abattement and
    several QF caps that this module does not expose. Saying so is the difference between
    a lower bound and a wrong number."""
    out = tj.price(2028, "indexe", reform=None, law=LAW, run=lambda r: 0.0,
                   indexation=HYPO)
    assert "BORNE INFÉRIEURE" in out.caveat


def test_a_sweep_returns_one_point_per_year():
    """Points, never a curve: a smooth line suggests values that were not computed."""
    out = tj.sweep(range(2026, 2030), "reconduit", reform=None,
                   law_for=lambda y: LAW, run_for=lambda y: (lambda r: 0.0))
    assert [t.year for t in out] == [2026, 2027, 2028, 2029]


# --------------------------------------------------------------------------- #
# M3 — the time dimension, and what each year rests on
# --------------------------------------------------------------------------- #


def test_the_last_legislated_year_is_measured_not_declared():
    """Fails the day an LFI legislates further out — which is the intended behaviour.

    `last_legislated_year` walks the known parameter paths and reports the last year at
    which any value changes. Hard-coding 2027 and 2030 would make the module lie the
    first time the tree moves; deriving them means the classification updates itself and
    this pin fails loudly instead.

    Measured today: households 2027 (bmaf, RSA, PPA step once and stop), firms 2030 (the
    CVAE's parameters cease to exist, which is the abolition).
    """
    assert tj.last_legislated_year("menages") == 2027
    assert tj.last_legislated_year("entreprises") == 2030


def test_the_disappearance_of_a_parameter_counts_as_legislation():
    """The CVAE ends in 2030 by ceasing to exist in the tree. That absence IS the
    abolition, not a gap — and treating it as a change is what makes the firm side
    legislated through 2030 rather than through 2029.

    Fails if the walk skips years where the parameter is missing.
    """
    assert tj.basis_for("entreprises", 2029) == "legislated"
    assert tj.basis_for("entreprises", 2030) == "legislated"


@pytest.mark.parametrize("side,year,expected", [
    ("menages", 2026, "legislated"),
    ("menages", 2027, "legislated"),
    ("menages", 2028, "reconducted"),
    ("entreprises", 2028, "legislated"),
    ("entreprises", 2031, "reconducted"),
])
def test_each_year_is_classified_by_what_it_rests_on(side, year, expected):
    assert tj.basis_for(side, year) == expected


def test_a_reconducted_year_says_the_reference_decides_the_answer():
    """The spec's rule: beyond the last legislated year the household figure depends on
    the reference, and saying so is mandatory on every output. Fails if the note goes
    silent."""
    note = tj.basis_note("menages", 2029, "reconduit")
    assert "RECONDUIT" in note
    assert "La référence choisie" in note and "reconduit" in note
    assert "2027" in note, "la note doit dire jusqu'où va la loi"


def test_a_legislated_year_says_it_depends_on_nothing():
    note = tj.basis_note("entreprises", 2029, "reconduit")
    assert "LÉGIFÉRÉ" in note
    assert "ne dépend d'aucune hypothèse" in note


def test_indexing_a_legislated_year_is_flagged_as_overwriting_a_voted_law():
    """The case the spec did not anticipate, and it is a different claim.

    Indexing 2026 — a year the legislator HAS addressed — does not restore a missing
    indexation; it replaces a voted barème with a counterfactual one. Legitimate, and not
    the same statement as indexing 2029. Fails if the two are worded alike.
    """
    note = tj.basis_note("menages", 2026, "indexe")
    assert "ATTENTION" in note
    assert "écraser une loi existante" in note
    beyond = tj.basis_note("menages", 2029, "indexe")
    assert "écraser une loi existante" not in beyond


def test_sweeping_a_knob_carries_a_basis_on_every_year():
    """Fails if any year comes back without saying what it rests on."""
    out = tj.sweep_knob("decote_taux", "menages", range(2026, 2030),
                        reference="reconduit",
                        run_for=lambda y: (lambda r: -1.0e9))
    assert [k.year for k in out] == [2026, 2027, 2028, 2029]
    assert [k.basis for k in out] == ["legislated", "legislated",
                                      "reconducted", "reconducted"]
    for k in out:
        assert k.note and k.reference == "reconduit"
        assert k.basis in tj.BASES


def test_an_unknown_side_is_refused():
    with pytest.raises(tj.TrajectoryError, match="côté inconnu"):
        tj.basis_for("particuliers", 2028)
    with pytest.raises(tj.TrajectoryError, match="côté inconnu"):
        tj.sweep_knob("x", "particuliers", range(2026, 2027), reference="reconduit",
                      run_for=lambda y: (lambda r: 0.0))


def test_a_sweep_still_refuses_an_unknown_reference():
    with pytest.raises(tj.TrajectoryError, match="inconnue"):
        tj.sweep_knob("x", "menages", range(2026, 2027), reference="courant",
                      run_for=lambda y: (lambda r: 0.0))


# --------------------------------------------------------------------------- #
# M4 (S1) — the band year by year, classes kept apart
# --------------------------------------------------------------------------- #


class _Band:
    def __init__(self, p10, p90):
        self.p10, self.p90 = p10, p90


class _Behavioural:
    def __init__(self, band, grade, reason=""):
        self.band, self.grade, self.grade_reason = band, grade, reason


def test_the_uprating_class_is_measured_by_the_frozen_aged_pair():
    """The class this milestone names, measured rather than assumed.

    M2's real numbers: the 2028 barème freeze prices at -7,073 md€ on a frozen 2024
    population and -8,339 md€ on an aged one. That 1,27 md€ IS the uprating uncertainty
    for that reform in that year — larger than many behavioural bands, and invisible
    unless named. Fails if the width stops being derived from the pair.
    """
    u = tj.year_uncertainty(2028, basis="reconducted", frozen_eur=-7.073e9,
                            aged_eur=-8.339e9, base_year=2026)
    assert u.uprating_eur == (-7.073e9, -8.339e9)
    assert u.uprating_width_eur == pytest.approx(1.266e9, abs=1e6)
    assert u.mechanical_eur == -8.339e9, "le titre est le chiffre vieilli, le plus complet"


def test_the_two_classes_are_never_merged_into_one_band():
    """THE rule of the milestone. Fails the day a `total` or combined band appears.

    Adding the classes would assert an independence nobody established and destroy the
    only actionable information: which of the two is doing the work. On the 2028 freeze
    the uprating class is the larger one, and a merged interval would hide that.
    """
    u = tj.year_uncertainty(2028, basis="reconducted", frozen_eur=-7.073e9,
                            aged_eur=-8.339e9, base_year=2026,
                            behavioural=_Behavioural(_Band(-8.9e9, -7.8e9), "illustrative"))
    assert not hasattr(u, "total"), "une bande combinée est apparue"
    assert not hasattr(u, "combined_eur")
    assert set(tj.UNCERTAINTY_CLASSES) == {"uprating", "behavioural"}
    # Both survive to the rendered line, separately named.
    line = u.line()
    assert "vieillissement" in line and "comportement" in line


def test_the_uprating_class_can_be_the_larger_one():
    """The reason for keeping them apart, made concrete: on this reform the price
    hypothesis moves the figure more than behaviour does."""
    u = tj.year_uncertainty(2028, basis="reconducted", frozen_eur=-7.073e9,
                            aged_eur=-8.339e9, base_year=2026,
                            behavioural=_Behavioural(_Band(-8.6e9, -8.1e9), "illustrative"))
    behavioural_width = abs(u.behavioural_eur[1] - u.behavioural_eur[0])
    assert u.uprating_width_eur > behavioural_width


# --- the fan's horizon, refused per year ---------------------------------------------


def test_the_macro_horizon_is_read_from_the_store():
    """Derived, not written: `usable_horizons` is ["1","2","3"] in multipliers.yaml,
    capped at three for two independent converging reasons. Reading it means a store
    that narrows narrows the trajectory too.

    Fails if it becomes a constant — and would have failed on the first version, which
    read `store.parameters` while every multiplier lives in `store.tables`, and so
    claimed no horizon was usable when three were.
    """
    assert tj.max_fan_horizon_years() == 3


@pytest.mark.parametrize("year,allowed", [
    (2026, True), (2027, True), (2029, True), (2030, False), (2032, False),
])
def test_the_horizon_refusal_binds_per_year_not_per_reform(year, allowed):
    """A 2024-2030 trajectory is not «inside» or «outside» the horizon as a whole: 2027
    is one year out and 2032 is six. Showing one fan for the reform would silently
    stretch a three-year multiplier across six.

    Fails if the check moves to the reform level.
    """
    got, note = tj.fan_note_for(year, base_year=2026, horizon=3)
    assert got is allowed
    assert str(year) in note
    if not allowed:
        assert "PAR ANNÉE et non par réforme" in note


def test_a_year_past_the_horizon_drops_its_fan_even_when_one_is_supplied():
    """The kill test for the refusal: supplying a fan must not defeat it."""
    u = tj.year_uncertainty(2032, basis="reconducted", frozen_eur=-1e9, aged_eur=-1e9,
                            base_year=2026, horizon=3, fan=object())
    assert u.fan is None
    assert "au-delà de l'horizon" in u.fan_note


def test_permitted_and_present_are_distinguished():
    """«The horizon allows a fan» and «a fan was computed» are different claims, and the
    first version printed the second while meaning the first — a reader saw «l'éventail
    est montré» beside «pas d'éventail»."""
    absent = tj.year_uncertainty(2028, basis="reconducted", frozen_eur=-1e9,
                                 aged_eur=-1e9, base_year=2026, horizon=3, fan=None)
    assert "aucun éventail n'a été calculé" in absent.fan_note
    present = tj.year_uncertainty(2028, basis="reconducted", frozen_eur=-1e9,
                                  aged_eur=-1e9, base_year=2026, horizon=3, fan=object())
    assert "l'éventail est montré" in present.fan_note


# --- applicability, graded per year --------------------------------------------------


def test_the_behavioural_grade_is_taken_per_year_not_carried_forward():
    """A reform in support in 2026 can be out of support by 2030 as uprated incomes drift
    from the range the elasticities were estimated on. Measure, don't assume.

    Fails if the grade is fixed once for the reform: each year's own behavioural block
    supplies its own verdict, and the two years below disagree on purpose.
    """
    early = tj.year_uncertainty(2026, basis="legislated", frozen_eur=-1e9, aged_eur=-1e9,
                                base_year=2026,
                                behavioural=_Behavioural(_Band(-1.1e9, -0.9e9),
                                                         "in-support"))
    late = tj.year_uncertainty(2030, basis="reconducted", frozen_eur=-1e9,
                               aged_eur=-1.4e9, base_year=2026,
                               behavioural=_Behavioural(None, "illustrative",
                                                        "hors du support en 2030"))
    assert early.behavioural_grade == "in-support"
    assert late.behavioural_grade == "illustrative"
    assert late.behavioural_eur is None
    assert "hors du support" in late.behavioural_note


def test_a_year_without_a_behavioural_block_says_so_rather_than_implying_zero():
    u = tj.year_uncertainty(2028, basis="reconducted", frozen_eur=-1e9, aged_eur=-1e9,
                            base_year=2026)
    assert u.behavioural_eur is None
    assert u.behavioural_grade == "aucune bande"
    assert "comportement : aucune bande" in u.line()
