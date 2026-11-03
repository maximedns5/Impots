"""The PFU knob and the household's capital income (D-249, PHASE11_SPEC §6 and §10, 9).

The knob moves one parameter, the income-tax part of the PFU; a household reaches it only
by declaring capital income, which the wire format did not carry before this milestone.
The read-back is guard 9: a knob whose write is not read back is refused, like any knob.
"""

from __future__ import annotations

import pytest

from impots.api.schemas import CAPITAL_CASES, HouseholdInput, ReformSpec
from impots.engine import compute, reforms, system
from impots.engine.situations import build_situation
from impots.population import capital as capital_module

RENTIER = {"adults": [{"salaire_brut_annuel": 30_000, "annee_naissance": 1975}],
           "capital": {"dividendes": 10_000.0}}


def _household(**capital: float) -> HouseholdInput:
    return HouseholdInput.model_validate({**RENTIER, "capital": capital})


def test_the_capital_cases_are_the_imputation_s():
    """The wire format and the imputation write the same four boxes, or a household and
    the population would be taxed on different bases."""
    assert set(CAPITAL_CASES.values()) == set(capital_module.CASES)


def test_capital_is_written_on_every_covered_year():
    situation = build_situation(_household(dividendes=10_000.0, interets=500.0), 2024)
    foyer = next(iter(situation["foyers_fiscaux"].values()))
    assert foyer["f2dc"] == {"2022": 10_000.0, "2023": 10_000.0, "2024": 10_000.0}
    assert foyer["f2tr"] == {"2022": 500.0, "2023": 500.0, "2024": 500.0}
    assert "f3vg" not in foyer and "f2ts" not in foyer


def test_no_capital_block_writes_no_capital_case():
    situation = build_situation(HouseholdInput.model_validate(
        {"adults": RENTIER["adults"]}), 2024)
    foyer = next(iter(situation["foyers_fiscaux"].values()))
    assert not set(CAPITAL_CASES.values()) & set(foyer)


@pytest.mark.slow
def test_household_dividends_are_taxed_at_the_pfu():
    rows = compute(_household(dividendes=10_000.0), 2024, tier="full").baseline
    assert rows["pfu"] == pytest.approx(1_280.0, abs=0.5)
    assert rows["prelevements_sociaux_capital"] == pytest.approx(1_720.0, abs=0.5)


@pytest.mark.slow
def test_the_pfu_knob_moves_the_pfu_and_the_tax():
    household = _household(dividendes=10_000.0)
    result = compute(household, 2024, reform=ReformSpec(pfu_taux=0.20), tier="full")
    assert result.reform["pfu"] == pytest.approx(2_000.0, abs=0.5)
    assert result.reform["ir"] - result.baseline["ir"] == pytest.approx(720.0, abs=1.0)
    # The social levies are not this knob.
    assert result.reform["prelevements_sociaux_capital"] == pytest.approx(
        result.baseline["prelevements_sociaux_capital"])


def test_the_pfu_knob_is_read_back(monkeypatch):
    """Guard 9: the write lands, or the reformed system is refused. A write diverted to a
    neighbouring parameter raises nothing by itself."""
    system.clear_cache()
    diverted = dict(reforms.SCALAR_KNOBS)
    diverted["pfu_taux"] = (
        "taxation_capital", "prelevement_forfaitaire", "partir_2018",
        "taux_prelevement_produits_assurance_vie_non_eligibles_prelevement_forfaitaire_unique")
    monkeypatch.setattr(reforms, "SCALAR_KNOBS", diverted)
    with pytest.raises(AssertionError, match="pfu_taux"):
        system.reformed_for(ReformSpec(pfu_taux=0.20), 2024)
    system.clear_cache()


def test_the_pfu_knob_reads_back_clean():
    system.clear_cache()
    reformed = system.reformed_for(ReformSpec(pfu_taux=0.20), 2024)
    assert capital_module.pfu_rate(2024) == pytest.approx(0.128)
    node = reformed.parameters("2024-01-01")
    for part in capital_module.PFU_RATE.split("."):
        node = getattr(node, part)
    assert float(node) == pytest.approx(0.20)
    system.clear_cache()


# --------------------------------------------------------------------------- #
# The capital in another year than the table's (D-249)
# --------------------------------------------------------------------------- #
def test_another_year_imputes_the_2024_table_times_the_declared_index(monkeypatch):
    """The foyers are ranked on the year's RFR per part; the bands' 2024 bases are
    multiplied by the index. The table is read as 2024's whatever the run's year."""
    import types

    import numpy as np
    import polars as pl

    from impots.population import runner

    simulation = types.SimpleNamespace(calculate=lambda name, period: {
        "rfr": np.array([30_000.0]), "nbptr": np.array([1.0])}[name])
    frame = pl.DataFrame({"foyer_id": ["a"], "household_id": ["m"], "weight": [10.0]})
    seen = {}

    def spy(per_part, weights, menages, year):
        seen["year"] = year
        return {"f2dc": np.array([1_000.0]), "f2tr": np.array([200.0])}

    monkeypatch.setattr(capital_module, "impute", spy)
    bases = runner._impute_capital(types.SimpleNamespace(simulation=simulation), frame,
                                   2026, 1.0609)
    assert seen["year"] == capital_module.YEAR
    assert bases["f2dc"] == pytest.approx([1_060.9]) and bases["f2tr"] == pytest.approx(
        [212.18])


@pytest.mark.parametrize("kwargs, needle", [
    ({"capital_index": 1.06}, "ne se donne qu'avec l'imputation"),
    ({"impute_capital": True, "capital_index": 0.0}, "strictement positif"),
    ({"impute_capital": True, "year": 2026}, "capital_index"),
], ids=["indice-seul", "indice-nul", "sans-indice"])
def test_the_index_is_refused_where_it_cannot_stand(monkeypatch, kwargs, needle):
    import polars as pl

    from impots.population import runner

    def no_pass(*args, **kw):
        raise AssertionError("aucune passe ne devait tourner")

    monkeypatch.setattr(runner, "build_simulation", no_pass)
    with pytest.raises(ValueError, match=needle):
        runner.run(pl.DataFrame({"person_id": [1]}), **{"year": 2024, **kwargs})


def test_a_pfu_reform_imputes_the_capital_it_bites_on():
    """Without the capital the PFU knob would cost exactly zero, and say nothing."""
    from types import SimpleNamespace

    from impots.api import main

    assert main.imputes_capital(SimpleNamespace(reform=ReformSpec(pfu_taux=0.2),
                                                impute_capital=False))
    assert not main.imputes_capital(SimpleNamespace(reform=ReformSpec(decote_taux=0.3),
                                                    impute_capital=False))
    assert main.imputes_capital(SimpleNamespace(reform=ReformSpec(decote_taux=0.3),
                                                impute_capital=True))
    assert not reforms.moves_capital(None)


@pytest.mark.parametrize("view, expected", [("vieillie", 1.03 ** 2), ("figee", 1.0)])
def test_the_first_year_ages_the_capital_with_the_frame(monkeypatch, view, expected):
    """The aged view's capital follows the wage index from the vintage; the frozen view's
    frame is the vintage's, and so is its capital."""
    from types import SimpleNamespace

    from impots import uprating as uprating_module
    from impots.api import main

    seen = {}

    def run_population(request, frame, capital_index=None):
        seen["index"] = capital_index
        raise RuntimeError("arrêt après le passage de l'indice")

    monkeypatch.setattr(main, "_run_population", run_population)
    monkeypatch.setattr(main, "_population_frame", lambda: "frame")
    monkeypatch.setattr(uprating_module, "uprate", lambda frame, year, uprating: frame)
    uprating = uprating_module.Uprating(wage=0.03, price=0.02, source="test",
                                        base_year=2024)
    request = SimpleNamespace(year=2026, reform=ReformSpec(pfu_taux=0.2))
    with pytest.raises(RuntimeError, match="arrêt"):
        main._price_households(request, uprating=uprating, macro=False,
                               view=main.FIRST_YEAR_VIEW if view == "vieillie"
                               else main.FROZEN_VIEW)
    assert seen["index"] == pytest.approx(expected)
