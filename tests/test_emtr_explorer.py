"""F6 / Phase 6 S5 — the EMTR explorer.

**No new model claims**, so there are no model tests here. What is tested is that the
sweep is what it says it is: a ruler and not a sample, the full tier and not the light
one, and a cliff marked as a cliff rather than plotted as a rate somebody faces.
"""

from __future__ import annotations

import pytest

from impots import emtr_explorer as ex


def test_the_offered_household_types_are_complete_specifications():
    """An EMTR is a property of a HOUSEHOLD, not of an income: at 24 000 EUR a single
    tenant and a couple with two children sit on different parts of the landscape.

    Fails if a type is added without the fields that make it a household.
    """
    assert ex.HOUSEHOLD_TYPES
    for key, spec in ex.HOUSEHOLD_TYPES.items():
        for field in ("label", "adults", "children", "loyer_mensuel",
                      "statut_occupation", "zone_apl"):
            assert field in spec, f"{key} sans {field}"
        assert spec["label"].strip(), key


def test_an_unknown_household_type_is_refused():
    with pytest.raises(ex.ExplorerError, match="type de ménage inconnu"):
        ex.sweep_frame("cadre_supérieur", (10_000.0,))


def test_an_empty_income_range_is_refused():
    with pytest.raises(ex.ExplorerError, match="aucune courbe"):
        ex.sweep_frame("celibataire_locataire", ())


def test_the_sweep_frame_is_a_ruler_not_a_sample():
    """Every row weighted 1 and flagged synthetic. Reading a distribution off a sweep
    would be reading one off a ruler, and the weights are what would let someone try."""
    frame = ex.sweep_frame("celibataire_locataire", (10_000.0, 20_000.0))
    assert set(frame["weight"].to_list()) == {1.0}
    assert all(frame["synthetic"].to_list())
    assert frame["household_id"].n_unique() == 2


def test_the_frame_carries_the_household_type_faithfully():
    """Fails if a type's children or second adult are dropped — which would silently
    price a different household than the label claims."""
    single = ex.sweep_frame("celibataire_locataire", (10_000.0,))
    couple = ex.sweep_frame("couple_2_enfants", (10_000.0,))
    assert single.height == 1
    assert couple.height == 4, "deux adultes et deux enfants"
    assert couple["role_menage"].to_list().count("conjoint") == 1
    assert couple["role_famille"].to_list().count("enfant") == 2

    isole = ex.sweep_frame("parent_isole_2_enfants", (10_000.0,))
    assert all(isole["parent_isole"].to_list())
    assert not any(single["parent_isole"].to_list())


def test_only_the_first_adult_carries_the_swept_income():
    """The finite difference bumps the first adult, so a sweep that also paid the
    partner would be measuring a different thing than it reports."""
    frame = ex.sweep_frame("couple_2_enfants", (30_000.0,))
    salaries = frame["salaire_brut_annuel"].to_list()
    assert salaries.count(30_000.0) == 1
    assert salaries.count(0.0) == 3


def test_the_income_grid_starts_above_zero_and_is_regular():
    grid = ex.incomes(step=500.0, maximum=2_000.0)
    assert grid == (500.0, 1_000.0, 1_500.0, 2_000.0)
    with pytest.raises(ex.ExplorerError):
        ex.incomes(step=0.0)


# --- the cliff honesty ---------------------------------------------------------------


def test_a_rate_above_one_is_named_a_cliff_not_a_peak():
    """AN EMTR ABOVE 100 % MEANS AN EXTRA EURO LEAVES THE HOUSEHOLD WORSE OFF, and its
    HEIGHT is an artefact of the 100 EUR finite-difference step: a cliff withdrawing
    47 EUR reads as 147 %, and the same cliff over 500 EUR would read 109 %.

    Measured on the real curve: the single tenant has a cliff at 8 000 EUR reading
    147,3 %. Fails if cliffs stop being separable from tapers, which would let a reader
    quote «147 %» as a rate somebody faces.
    """
    curve = ex.Curve(
        household_type="celibataire_locataire", label="x", year=2024,
        points=(ex.CurvePoint(4_000.0, 0.52), ex.CurvePoint(8_000.0, 1.473),
                ex.CurvePoint(24_000.0, 0.635)))
    assert [p.salaire_brut_annuel for p in curve.cliffs] == [8_000.0]
    assert curve.peak.salaire_brut_annuel == 8_000.0, "le pic brut EST la falaise"
    below = max((p for p in curve.points if p.emtr <= 1.0), key=lambda p: p.emtr)
    assert below.emtr == pytest.approx(0.635), "et le pic hors falaise est autre chose"


def test_crossings_report_the_income_after_the_crossing():
    """The first income at which a reader would actually face the new rate."""
    curve = ex.Curve(
        household_type="x", label="x", year=2024,
        points=(ex.CurvePoint(10_000.0, 0.30), ex.CurvePoint(12_000.0, 0.62),
                ex.CurvePoint(14_000.0, 0.61), ex.CurvePoint(16_000.0, 0.32)))
    assert curve.crossings(0.5) == (12_000.0, 16_000.0)


# --- the end-to-end curve, on the real engine ----------------------------------------


@pytest.mark.slow
def test_the_curve_reproduces_the_63_5_per_cent_finding():
    """D-033's finding, arrived at from the other direction.

    The population's tenth decile of marginal rates has a median EMTR of 63,5 %, and its
    households are poor rather than rich. A single tenant swept across the income range
    sits at 63,5-63,6 % between 24 000 and 28 000 EUR — the same number, from one
    constructed household instead of a population decile. That agreement is the whole
    point of the explorer: the decile statistic becomes a place on a curve.
    """
    curve = ex.curve("celibataire_locataire", 2024, step=2_000.0, maximum=30_000.0)
    assert len(curve.points) == 15
    at_24k = next(p for p in curve.points if p.salaire_brut_annuel == 24_000.0)
    assert at_24k.emtr == pytest.approx(0.635, abs=0.01)
    # And the low-income cliff is present, which a light tier would have missed entirely.
    assert curve.cliffs, "aucune falaise : le tier complet n'a probablement pas tourné"


@pytest.mark.slow
def test_the_curve_refuses_a_short_sweep_rather_than_dropping_points():
    """A curve with holes would be read as a curve. Fails if the length check goes."""
    curve = ex.curve("celibataire_proprietaire", 2024, step=5_000.0, maximum=20_000.0)
    assert len(curve.points) == 4
    assert [p.salaire_brut_annuel for p in curve.points] == [5_000.0, 10_000.0,
                                                             15_000.0, 20_000.0]
