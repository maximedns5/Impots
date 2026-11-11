"""Phase 11 M2 — the firm layer's two views, and the annual path with a firm reform (D-246).

What is held here: the aged view is the vintage's cost times the scenario's nominal GDP
over the vintage's, the accounts up to the chain's start year and the scenario beyond; a
vintage without a year, a year before the vintage and an aged view without a growth
scenario are refused by name; the annual path carries the cost by layer, and refuses a
year whose layers do not sum to its cost, in the path and in the report; a scenario
carries a firm reform and leaves the files written before it unchanged; and the command
prices a firm-only scenario year by year, both views, by layer.
"""

from __future__ import annotations

import json

import polars as pl
import pytest
from pydantic import ValidationError

from impots import scenarios as scenarios_module
from impots import service
from impots.api.schemas import PredictifReportYear
from impots.dette import reference
from impots.dette import scenarios as debt_scenarios
from impots.dette.path import SHIPPED, DebtError
from impots.entreprises.reforms import FirmReformSpec
from impots.population import aggregate, cli, runner
from impots.predictif import annuel, firmes
from impots.predictif.theta import Theta

GROWTH = debt_scenarios.GrowthScenario("Croissance réelle 1 %, prix 2 %", 0.01, 0.02)
HELD = debt_scenarios.RateScenario("Taux implicite tenu à son niveau de 2025",
                                   "implicite_tenu")
#: GDP of the accounts, in euros, for the years a test reads.
ACCOUNTS = {2023: 2_800e9, 2024: 2_900e9, 2025: 3_000e9}


def _gdp(years: list[int]) -> dict[int, float]:
    return {y: ACCOUNTS[y] for y in years}


# --------------------------------------------------------------------------- #
# The aged view's factor
# --------------------------------------------------------------------------- #
def test_the_aged_factor_is_nominal_gdp_over_the_vintages() -> None:
    """The accounts up to 2025, the scenario's nominal growth beyond, as the debt's
    denominator grows: 2026 is 3 000 × 1,0302 over the GDP of the vintage's year."""
    assert firmes.aging_factor(2024, GROWTH, "2024", _gdp) == 1.0
    assert firmes.aging_factor(2025, GROWTH, "2024", _gdp) == pytest.approx(3_000 / 2_900)
    assert firmes.aging_factor(2026, GROWTH, "2024", _gdp) == pytest.approx(
        3_000 * 1.01 * 1.02 / 2_900)
    assert firmes.aging_factor(2028, GROWTH, "2024", _gdp) == pytest.approx(
        3_000 * (1.01 * 1.02) ** 3 / 2_900)


def test_the_vintage_2023_is_aged_from_the_year_of_its_profits() -> None:
    """But 19, étape 1. The vintage « 2023 » has the Ésane 2023's shape and the DGFiP's
    profits of 2024 (`entreprises/margins.TAXABLE_PROFIT`): it is aged from 2024. Aged
    from 2023, as until then, 2026 took 3 000 × 1,0302 / 2 800, the GDP of 2024 over
    2023 once too many."""
    assert firmes.base_year("2023") == 2024
    assert firmes.aging_factor(2024, GROWTH, "2023", _gdp) == 1.0
    assert firmes.aging_factor(2026, GROWTH, "2023", _gdp) == pytest.approx(
        3_000 * 1.01 * 1.02 / 2_900)
    assert "depuis 2024, l'année de ses bénéfices" in firmes.convention("2023")
    from impots import verification

    assert verification.BASE_FIRMES == 2024
    assert verification.FIRMES.name == "firms_2023.parquet"


@pytest.mark.parametrize("year, growth, vintage, needle", [
    (2026, GROWTH, "fixture", "n'a pas d'année"),
    (2022, GROWTH, "2023", "précède le millésime"),
    (2023, GROWTH, "2023", "précède le millésime"),
    (2026, None, "2023", "sans scénario de croissance"),
], ids=["sans-annee", "avant-le-millesime", "avant-ses-benefices", "sans-croissance"])
def test_an_aged_view_it_cannot_compute_is_refused(year, growth, vintage, needle) -> None:
    with pytest.raises(firmes.FirmViewError, match=needle):
        firmes.aging_factor(year, growth, vintage, _gdp)


def test_the_note_says_which_view() -> None:
    assert "×1,0800" in firmes.note(firmes.AGED, "2023", 2026, 1.08)
    assert firmes.note(firmes.FROZEN, "2023", 2026, None).startswith("vue figée")
    convention = firmes.convention("2023")
    for named in ("millésime 2023", "Vue figée", "vue vieillie", "PIB nominal",
                  "à l'exercice"):
        assert named in convention, named


# --------------------------------------------------------------------------- #
# The annual path, by layer
# --------------------------------------------------------------------------- #
def _layered(year: int, view: str) -> annuel.Layered:
    firms = 3e9 * (1.05 if view == "vieillie" else 1.0)
    return annuel.Layered(cost=1e9 + firms, layers={"menages": 1e9, "entreprises": firms})


def test_the_years_carry_their_layers_and_the_report_shows_them() -> None:
    prices = annuel.price_years([2026, 2027], _layered, basis_for=lambda y: "test")
    assert prices[0].aged_eur == pytest.approx(4.15e9)
    assert prices[0].layers == {"figee": {"menages": 1e9, "entreprises": 3e9},
                                "vieillie": {"menages": 1e9,
                                             "entreprises": pytest.approx(3.15e9)}}
    plain = annuel.price_years([2026], lambda y, v: 1e9, basis_for=lambda y: "test")
    assert plain[0].layers is None


def test_a_year_whose_layers_do_not_sum_to_its_cost_is_refused() -> None:
    with pytest.raises(DebtError, match="somme de ses couches"):
        annuel.Layered(cost=5e9, layers={"menages": 1e9, "entreprises": 3e9})

    def half(year: int, view: str):
        return _layered(year, view) if view == "vieillie" else 4e9

    with pytest.raises(DebtError, match="par couche et l'autre non"):
        annuel.price_years([2026], half, basis_for=lambda y: "test")


def _report(prices, firm_note=None) -> annuel.Rapport:
    uprating = annuel.uprating_for(GROWTH, wage=0.03, source="test", base_year=2024)
    return annuel.build(START, prices, scenario="test", titre="Test", source="test",
                        reference="reconduit", computed="2026-10-25",
                        spending=SHIPPED["gele_en_volume"], growth=GROWTH, rate=HELD,
                        theta=Theta(common=0.5), uprating=uprating, uprating_note="note",
                        firm_note=firm_note)


def test_a_report_names_its_firm_layer_exactly_when_it_has_one() -> None:
    """A report with a firm layer says how it was priced — the vintage, both views, the
    IS by exercise — and one without says nothing of it, so a household report reads as
    it always did. Either half missing is refused before the chain is asked."""
    layered = annuel.price_years([2026, 2027], _layered, basis_for=lambda y: "test")
    note = firmes.convention("2023")
    assert _report(layered, firm_note=note).payload()["conventions"][-1] == note
    with pytest.raises(DebtError, match="sans sa note"):
        _report(layered)
    plain = annuel.price_years([2026, 2027], lambda y, v: 1e9, basis_for=lambda y: "test")
    assert note not in _report(plain).payload()["conventions"]
    with pytest.raises(DebtError, match="sans couche entreprises"):
        _report(plain, firm_note=note)


ROW = {"year": 2026, "basis": "test", "mechanical_frozen_eur": 4e9,
       "mechanical_aged_eur": 4.15e9, "reference": 1.16, "reform_aged": 1.17,
       "delta_aged": 0.01, "reform_frozen": 1.17, "delta_frozen": 0.01}


def test_the_report_refuses_a_year_whose_layers_are_not_its_cost() -> None:
    """PHASE11_SPEC §10, guard 8, on the annual report too."""
    good = {"figee": {"menages": 1e9, "entreprises": 3e9},
            "vieillie": {"menages": 1e9, "entreprises": 3.15e9}}
    assert PredictifReportYear.model_validate({**ROW, "mechanical_by_layer": good})
    assert PredictifReportYear.model_validate(ROW).mechanical_by_layer is None
    for bad, needle in (
            ({**good, "vieillie": {"menages": 1e9, "entreprises": 3e9}}, "somme"),
            ({"figee": good["figee"]}, "les vues sont"),
            ({**good, "figee": {"menages": 1e9, "etat": 3e9}}, "somme")):
        with pytest.raises(ValidationError, match=needle):
            PredictifReportYear.model_validate({**ROW, "mechanical_by_layer": bad})


# --------------------------------------------------------------------------- #
# The scenario, and the command
# --------------------------------------------------------------------------- #
def _scenario(name: str, firm: dict | None):
    from impots.api.schemas import ReformSpec

    return scenarios_module.Scenario(
        name=name, reform=ReformSpec(), year=2026, created="2026-10-25",
        source="test : un point d'IS en moins",
        firm_reform=FirmReformSpec.model_validate(firm) if firm else None)


def test_a_scenario_carries_its_firm_reform_and_old_files_are_unchanged(tmp_path) -> None:
    _scenario("is_24", {"is_taux_normal": 0.24}).save(tmp_path)
    back = scenarios_module.load("is_24", tmp_path)
    assert back.firm_reform == FirmReformSpec(is_taux_normal=0.24)
    raw = json.loads((tmp_path / "is_24.json").read_text(encoding="utf-8"))
    assert raw["firm_reform"] == {"is_taux_normal": 0.24}
    _scenario("rien", None).save(tmp_path)
    assert "firm_reform" not in json.loads((tmp_path / "rien.json").read_text())
    assert scenarios_module.load("rien", tmp_path).firm_reform is None
    for name in ("gel_bareme", "rsa_700"):
        committed = scenarios_module.load(name)
        assert committed.firm_reform is None and "firm_reform" not in committed.to_dict()


START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)


def test_the_command_prices_a_firm_scenario_by_layer_in_both_views(monkeypatch,
                                                                   tmp_path) -> None:
    from impots.entreprises import aggregate as firm_aggregate
    from impots.entreprises import runner as firm_runner
    from impots.entreprises.build import FIXTURE_CELLS, PROCESSED, build

    if not (PROCESSED / "firms_fixture.parquet").exists():
        build(FIXTURE_CELLS)
    processed = tmp_path / "processed"
    processed.mkdir()
    pl.DataFrame({"person_id": [1], "salaire_brut_annuel": [30_000.0],
                  "pension_annuelle": [0.0], "chomage_annuel": [0.0],
                  "loyer_mensuel": [500.0],
                  # Every monetary column the ageing reads (étape 2 of but 19 added it).
                  "revenu_non_salarie_annuel": [0.0]}).write_parquet(
        processed / "population_2024.parquet")
    monkeypatch.setattr(cli, "PROCESSED", processed)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    monkeypatch.setattr(service, "firm_aging_factor", lambda year, growth: 1.1)

    def no_household_pass(*args, **kwargs):
        raise AssertionError("une réforme des seules entreprises ne lance aucune passe "
                             "de population")

    monkeypatch.setattr(runner, "run", no_household_pass)
    monkeypatch.setattr(aggregate, "aggregate", no_household_pass)
    _scenario("is_24", {"is_taux_normal": 0.24}).save(tmp_path / "scen")
    code = cli.main(["predictif", "is_24", "--dir", str(tmp_path / "scen"),
                     "--reference", "reconduit", "--spending", "gele_en_volume",
                     "--growth-name", GROWTH.name, "--real", "0.01", "--prices", "0.02",
                     "--rate-name", "Taux implicite tenu à son niveau de 2025",
                     "--rate-kind", "implicite_tenu", "--horizon", "2", "--theta", "0.5",
                     "--wage", "0.03", "--hypothesis-source", "test",
                     "--out-dir", str(tmp_path / "out")])
    assert code == 0
    report = json.loads((tmp_path / "out" / "predictif_is_24.json").read_text())
    firm = float(firm_aggregate.aggregate(firm_runner.run(
        service.firm_population(), year=2026,
        reform=FirmReformSpec(is_taux_normal=0.24)).firms).reform_cost)
    first = report["years"][0]
    assert first["mechanical_by_layer"] == {
        "figee": {"menages": 0.0, "entreprises": pytest.approx(firm)},
        "vieillie": {"menages": 0.0, "entreprises": pytest.approx(firm * 1.1)}}
    assert first["mechanical_aged_eur"] == pytest.approx(firm * 1.1)
    assert first["delta_aged"] > first["delta_frozen"] > 0
    note = report["conventions"][-1]
    assert note == service.firm_report_note()
    assert "cellules synthétiques" in note and "vue vieillie" in note


def test_unreadable_accounts_are_a_named_refusal() -> None:
    def broken(years):
        raise DebtError("insee_cn2025_pib_T1101_1103.xlsx : année absente")

    with pytest.raises(firmes.FirmViewError, match="illisible"):
        firmes.aging_factor(2026, GROWTH, "2023", broken)
