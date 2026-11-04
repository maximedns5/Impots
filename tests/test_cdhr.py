"""The CDHR in the ledger, and out of C10's base (D-250).

Since 2025 openfisca takes the contribution différentielle sur les hauts revenus out of
disposable income (`impots_directs`), but not out of `impot_revenu_restant_a_payer`, the
project's `ir`. Without capital income no foyer of the population reached it. With the
imputation of D-248 it takes back part of any PFU cut, and the ledger of `sector_balance`
refused the pass: the cost by disposable income was not what the instruments said moved.
"""

from __future__ import annotations

import polars as pl
import pytest

from impots import guards, service
from impots.api.schemas import HouseholdInput, ReformSpec
from impots.engine import compute
from impots.engine.outputs import REGISTRY
from impots.macro import shocks
from impots.population import aggregate

#: A foyer whose tax, PFU and CEHR included, stays under 20 % of a RFR above 250 000 €.
RENTIER = {"adults": [{"salaire_brut_annuel": 30_000, "annee_naissance": 1975}],
           "capital": {"dividendes": 1_000_000.0}}


def test_a_pfu_cut_under_the_cdhr_is_taken_back_whole():
    """The PFU point cut is 10 000 € off the income tax; the CDHR, which tops the foyer's
    tax up to 20 % of its RFR, takes the 10 000 € back, and the disposable income does not
    move. Before D-250 the household could not see the CDHR at all."""
    result = compute(HouseholdInput.model_validate(RENTIER), 2026,
                     reform=ReformSpec(pfu_taux=0.118), tier="full")
    before, after = result.baseline, result.reform
    assert before["cdhr"] > 0
    assert after["ir"] - before["ir"] == pytest.approx(-10_000.0, rel=1e-3)
    assert after["cdhr"] - before["cdhr"] == pytest.approx(10_000.0, rel=1e-3)
    assert after["revenu_disponible"] - before["revenu_disponible"] == pytest.approx(
        0.0, abs=1.0)


def test_the_cdhr_is_a_row_an_instrument_and_a_receipt():
    row = next(r for r in REGISTRY if r.key == "cdhr")
    assert row.variable == "contribution_differentielle_hauts_revenus"
    assert row.entity == "foyer_fiscal" and row.negate
    assert "cdhr" in aggregate.INSTRUMENTS and "cdhr" in guards.STATE_RECEIPTS


def test_the_ledger_counts_what_the_cdhr_takes_back():
    """GUARD (D-250). The measured shape of a PFU point cut in 2026: the income tax falls
    by 842 M€, the CDHR rises by 149 M€, and the disposable income moves by 693 M€. Without
    the CDHR among the receipts the identity refused by 17,7 %."""
    guards.sector_balance({"ir": -842e6, "cdhr": 149e6}, reform_cost=693e6)
    with pytest.raises(guards.SectorBalanceError):
        guards.sector_balance({"ir": -842e6}, reform_cost=693e6)


def test_the_impulse_nets_the_cdhr_against_the_income_tax():
    """The CDHR is levied with the income tax, on the same declaration: Mésange's income-tax
    variant reads the net, 693 M€, not the gross 842 M€ that would lend the loop a cut
    the households never got."""
    built = shocks.build({"ir": -842e6, "cdhr": 149e6}, year=2026, reform_cost=693e6,
                         knobs=("pfu_taux",))
    assert shocks.INSTRUMENT_MAP["cdhr"] == "impot_sur_le_revenu"
    assert built.by_instrument["impot_sur_le_revenu"] == pytest.approx(693e6)


@pytest.fixture
def _levies(monkeypatch):
    from impots.population import capital as capital_module

    monkeypatch.setattr(capital_module, "social_levy_rate", lambda year: 0.186)
    monkeypatch.setattr(capital_module, "wage_wedge", lambda year: (1.14, 1.66))


def test_c10_leaves_out_the_dividends_the_cdhr_holds(_levies):
    """A household the CDHR holds, before or after the reform, does not see the net-of-tax
    rate the reform writes: the CDHR takes the cut back. Its dividends leave C10's base and
    are named apart; the others respond as in D-249."""
    from types import SimpleNamespace


    households = pl.DataFrame({
        "weight": [2.0, 3.0, 1.0], "dividendes": [10_000.0, 1_000_000.0, 400_000.0],
        "cdhr": [0.0, 46_000.0, 0.0], "cdhr_reform": [0.0, 56_000.0, 2_000.0]})
    request = SimpleNamespace(reform=ReformSpec(pfu_taux=0.118), year=2026)
    inputs = service.dividend_inputs(request, households)
    assert inputs["dividend_base_eur"] == pytest.approx(20_000.0)
    assert inputs["dividend_base_cdhr_eur"] == pytest.approx(3_400_000.0)


def test_c10_names_the_dividends_it_left_to_the_cdhr():
    import numpy as np

    from impots.behavioural import channels
    from impots.behavioural.store import load

    result = channels.dividend_response(
        load(), ReformSpec(pfu_taux=0.118), dividend_base_eur=40e9,
        dividend_base_cdhr_eur=13e9, levy_rate_baseline=0.314, levy_rate_reform=0.304,
        wage_levy_rate=1.14, wage_cost_rate=1.66, corporate_rate=0.25,
        rng=np.random.default_rng(0))
    assert result.applies
    assert result.diagnostics["dividends_held_by_cdhr_eur"] == pytest.approx(13e9)
    assert "CDHR" in result.diagnostics["not_counted"]


def test_without_a_cdhr_column_c10_reads_the_base_as_before(_levies):
    """A run without the row — the light tier of a year before 2025 — keeps D-249's base."""
    from types import SimpleNamespace


    households = pl.DataFrame({"weight": [2.0], "dividendes": [10_000.0]})
    inputs = service.dividend_inputs(
        SimpleNamespace(reform=ReformSpec(pfu_taux=0.118), year=2026), households)
    assert inputs["dividend_base_eur"] == pytest.approx(20_000.0)
    assert inputs["dividend_base_cdhr_eur"] == 0.0
