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
