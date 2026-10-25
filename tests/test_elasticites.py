"""Phase 11 M2 — the elasticity loop for the IS, and the cross-check that refuses it (D-246).

What is held here: the Commission's France rows are read out of the PDF, and the three
tables give each other back by the authors' own formulas; the loop's two readings are
0,585 and 0,630 per point of GDP gap; the cross-check against Mésange, variant by
variant and horizon by horizon, refuses the loop on the real store, and lets it through
only on a store whose ratios it reproduces (§10, guard 6); the loop is never asked for
an instrument Mésange covers (guard 5); and the chain's reason for the firm taxes names
the refusal the code computes.
"""

from __future__ import annotations

import dataclasses

import pytest

from impots.macro.store import Store
from impots.predictif import elasticites as el
from macro_cases import _table


def _paper() -> el.Reading:
    pytest.importorskip("pypdf")
    if not (el.RAW / el.SOURCE_FILE).exists():
        pytest.skip("data/raw/ n'a pas la DP 098 — les sources primaires ne sont pas "
                    "versionnées")
    return el.load()


def _mesange():
    from impots.api import main

    try:
        return main._predictif_macro_store()
    except main.MacroSourceError:
        pytest.skip("data/raw/ n'a pas le document de Mésange")


# --------------------------------------------------------------------------- #
# The paper
# --------------------------------------------------------------------------- #
def test_the_france_rows_are_read_as_printed() -> None:
    """Pinned by eye off Tables I.1 to I.3 (PDF pp. 41 to 43)."""
    reading = _paper()
    assert reading.pages == {"elasticities": 41, "shares": 42, "decomposition": 43}
    assert reading.elasticities == {
        "impot_revenu": 1.86, "impot_societes": 2.76, "cotisations_sociales": 0.63,
        "impots_indirects": 1.00, "recettes_non_fiscales": 0.00, "chomage": -3.23,
        "autres_depenses": 0.00}
    assert reading.shares["impot_revenu"] == 18.73 and reading.shares["chomage"] == 3.34
    assert reading.decomposition == {"a": 1.01, "b": -0.11, "c": 0.01, "d": -1.11,
                                     "e": 51.99, "f": 56.50, "g": 0.004, "h": -0.626,
                                     "i": 0.630}


def test_the_two_readings_of_the_loop() -> None:
    """In euros over GDP, 1,0088 × 0,5199 + 0,1079 × 0,5650 = 0,585; as the balance
    ratio's semi-elasticity, 0,630, which adds the denominator on a 4,51-point deficit."""
    shares = el.loop_shares(_paper())
    assert shares[el.EUROS] == pytest.approx(0.5854, abs=5e-5)
    assert shares[el.RATIO] == 0.630


def test_a_reading_the_tables_do_not_give_back_is_refused() -> None:
    reading = _paper()
    shifted = dataclasses.replace(reading, elasticities={
        **reading.elasticities, "impot_revenu": 2.76, "impot_societes": 1.86})
    with pytest.raises(el.ElasticityError, match="ne se recoupent pas"):
        el.check(shifted)


# --------------------------------------------------------------------------- #
# The cross-check, and the two guards
# --------------------------------------------------------------------------- #
def test_the_loop_is_refused_against_mesange_at_every_horizon() -> None:
    """The verdict, computed: the employer contributions miss at one, two and three
    years whichever reading, 34 to 58 % away; so do the VAT's, against 1,18 gross."""
    verdict = el.cross_check(_paper(), _mesange())
    assert not verdict.passes and verdict.passing == ()
    for reading in (el.EUROS, el.RATIO):
        missed = {(r.instrument, r.horizon) for r in verdict.failures(reading)}
        assert {("cotisations_employeurs", h) for h in el.HORIZONS} <= missed
        assert {("tva", h) for h in el.HORIZONS} <= missed
    employer = {r.horizon: r for r in verdict.rows if r.instrument == "cotisations_employeurs"}
    assert employer["1"].mesange == pytest.approx(1.40, abs=0.005)
    assert employer["1"].gaps[el.EUROS] == pytest.approx(-0.58, abs=0.005)
    assert employer["3"].gaps[el.RATIO] == pytest.approx(-0.34, abs=0.005)
    assert "refusée" in verdict.reason() and "cotisations_employeurs" in verdict.reason()


def _store_at(ratio: float) -> Store:
    """Every variant's φ/y at `ratio`: a multiplier of 1 and a balance of ratio − cost."""
    from impots.macro import mesange

    multipliers = {i: (1.0,) * 6 for i in el.VARIANTS}
    balance = {i: (ratio - mesange.VARIANTS[i].ex_ante_points,) * 6 for i in el.VARIANTS}
    return Store(tables={
        "multiplier_by_instrument": _table("multiplier_by_instrument", multipliers),
        "primary_balance_by_instrument": _table("primary_balance_by_instrument", balance)})


def test_the_loop_passes_only_where_mesange_is_reproduced() -> None:
    """Guard 6: the refusal is the cross-check's, not a hard-coded no. A store whose
    ratios both readings reproduce lets the loop through; one only the ratio reading
    reproduces lets that reading alone; one neither does refuses it."""
    reading = _paper()
    assert el.elasticity_loop("impot_societes", reading=reading,
                              store=_store_at(0.60)) == {el.EUROS: pytest.approx(0.5854,
                                                                                 abs=5e-5),
                                                         el.RATIO: 0.630}
    assert set(el.elasticity_loop("impot_societes", reading=reading,
                                  store=_store_at(0.80))) == {el.RATIO}
    with pytest.raises(el.ElasticityLoopRefused, match="refusée"):
        el.elasticity_loop("impot_societes", reading=reading, store=_store_at(1.40))


@pytest.mark.parametrize("instrument", ["impot_sur_le_revenu", "csg", "tva"])
def test_the_loop_is_never_asked_where_mesange_prints(instrument: str) -> None:
    """Guard 5: where Mésange prints its balance row, it comes first."""
    with pytest.raises(el.ElasticityLoopRefused, match="garde 5"):
        el.elasticity_loop(instrument, reading=_paper(), store=_store_at(0.60))


def test_the_chains_reason_for_the_firm_taxes_is_the_computed_refusal() -> None:
    """Anti-drift: the reason the chain prints for the IS is held against the verdict.
    Should the cross-check ever pass, this fails and the text must be rewritten."""
    from impots.api import main

    with pytest.raises(el.ElasticityLoopRefused):
        el.elasticity_loop("impot_societes", reading=_paper(), store=_mesange())
    for needle in ("sans variante dans Mésange", "DP 098", "refusée", "D-246", "D-218"):
        assert needle in main.FIRM_NO_VARIANT
