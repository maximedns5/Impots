"""Une revalorisation, sur un chemin de plusieurs années (D-301).

L'art. 74 du PLF 2027 suspend la revalorisation d'avril de la prime d'activité et celle
d'octobre des aides au logement. La première année, le coefficient s'écrit à sa date
légale ; les années suivantes, le niveau qu'il laisse demeure, de janvier à décembre. Un
chemin qui récrirait chaque année le coefficient d'avril ne porterait la mesure que d'avril
à décembre, chaque année : une dent de scie que la loi ne connaît pas. `Scenario.reform_in`
donne la réforme de chaque année, et `impots predictif` la chiffre.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import polars as pl
import pytest

from impots import scenarios as sc
from impots.api.schemas import ReformSpec
from impots.dette import reference
from impots.engine import reforms
from impots.population import aggregate, cli, runner

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
ARGS = ["predictif", "art74", "--reference", "reconduit", "--spending", "gele_en_volume",
        "--growth-name", "Croissance réelle 1 %, prix 2 %", "--real", "0.01",
        "--prices", "0.02", "--rate-name", "Taux implicite tenu à son niveau de 2025",
        "--rate-kind", "implicite_tenu", "--horizon", "3", "--theta", "0.5",
        "--wage", "0.03", "--hypothesis-source", "test : 2 % de prix, 3 % de salaires"]


def make(reform: ReformSpec, **overrides) -> sc.Scenario:
    base = dict(name="art74", reform=reform, year=2026, created="2026-10-29",
                source="PLF 2027, art. 74")
    return sc.Scenario(**{**base, **overrides})


def test_every_dated_knob_has_a_carried_one_with_the_same_amount():
    for dated, carried in reforms.PORTEE.items():
        assert dated in reforms.REVALORISATION_KNOBS
        assert carried in reforms.REVALORISATION_KNOBS
        assert reforms.REVALORISATION_KNOBS[carried] == reforms.REVALORISATION_KNOBS[dated]
        assert reforms.revalorisation_paths(dated, 2026) == reforms.revalorisation_paths(
            carried, 2027)


def test_the_first_year_keeps_the_legal_date_and_the_years_after_carry_the_level():
    scenario = make(ReformSpec(ppa_revalorisation_avril=1.021, al_revalorisation_octobre=1.02,
                               rsa_montant_de_base=700.0))
    assert scenario.reform_in(2026) == scenario.reform
    for year in (2027, 2030):
        assert scenario.reform_in(year).model_dump(exclude_none=True) == {
            "ppa_revalorisation_portee": 1.021, "al_revalorisation_portee": 1.02,
            "rsa_montant_de_base": 700.0}


def test_a_reform_without_a_dated_knob_is_the_same_every_year():
    scenario = make(ReformSpec(rsa_montant_de_base=700.0))
    assert all(scenario.reform_in(y) == scenario.reform for y in (2026, 2027, 2035))


@pytest.fixture
def stubbed(monkeypatch, tmp_path) -> SimpleNamespace:
    """A five-person population and a household pass that records the reform it priced."""
    processed = tmp_path / "processed"
    processed.mkdir()
    pl.DataFrame({"person_id": [1, 2, 3, 4, 5], "salaire_brut_annuel": [30_000.0] * 5,
                  "pension_annuelle": [0.0] * 5, "chomage_annuel": [0.0] * 5,
                  "loyer_mensuel": [500.0] * 5}).write_parquet(
        processed / "population_2024.parquet")
    monkeypatch.setattr(cli, "PROCESSED", processed)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    priced: list = []

    def run(pop, *, year, reform, tier, sample):
        priced.append((year, reform.model_dump(exclude_none=True)))
        return SimpleNamespace(households=SimpleNamespace(cost=1e9))

    monkeypatch.setattr(runner, "run", run)
    monkeypatch.setattr(aggregate, "aggregate",
                        lambda households: SimpleNamespace(reform_cost=households.cost))
    scenarios = tmp_path / "scenarios"
    make(ReformSpec(ppa_revalorisation_avril=1.021)).save(scenarios)
    return SimpleNamespace(priced=priced, scenarios=scenarios, out=tmp_path / "reports")


def test_the_annual_path_prices_the_date_then_the_carried_level(stubbed) -> None:
    """Fails if `impots predictif` prices `scenario.reform` every year: the April
    coefficient would be written again each year, and Jan to March left out each year."""
    assert cli.main([*ARGS, "--dir", str(stubbed.scenarios), "--out-dir",
                     str(stubbed.out)]) == 0
    by_year = {}
    for year, spec in stubbed.priced:
        by_year.setdefault(year, set()).update(spec)
    assert by_year == {2026: {"ppa_revalorisation_avril"},
                       2027: {"ppa_revalorisation_portee"},
                       2028: {"ppa_revalorisation_portee"}}
    report = json.loads((stubbed.out / "predictif_art74.json").read_text(encoding="utf-8"))
    assert [row["year"] for row in report["years"]] == [2026, 2027, 2028]


def _by_year(priced) -> dict[int, set[str]]:
    by_year: dict[int, set[str]] = {}
    for year, spec in priced:
        by_year.setdefault(year, set()).update(spec)
    return by_year


def test_the_whole_pass_prices_the_date_then_the_carried_level(stubbed, monkeypatch) -> None:
    """The same on the simulator's pass, which `--behavioural` and `--macro` take."""
    from impots.api import main as api_main

    seen: list = []

    def first(request, *, uprating, macro, view, **firm_part):
        seen.append((request.year, request.reform.model_dump(exclude_none=True)))
        return SimpleNamespace(cost=1e9, inputs={}, impulse={} if macro else None,
                               uncovered={}, layers=None, behaviour_asked=False)

    monkeypatch.setattr(api_main, "_price_first_year", first)
    assert cli.main([*ARGS, "--dir", str(stubbed.scenarios), "--out-dir", str(stubbed.out),
                     "--macro"]) == 0
    assert _by_year(seen) == {2026: {"ppa_revalorisation_avril"},
                              2027: {"ppa_revalorisation_portee"},
                              2028: {"ppa_revalorisation_portee"}}


def test_the_trajectory_prices_the_date_then_the_carried_level(stubbed, monkeypatch,
                                                                tmp_path) -> None:
    """And on `impots trajectoire`, whose report goes beside the code: the test moves the
    code's place so that the report lands in the test's directory."""
    monkeypatch.setattr(cli, "__file__", str(tmp_path / "a" / "b" / "c" / "cli.py"))
    assert cli.main(["trajectoire", "art74", "--dir", str(stubbed.scenarios),
                     "--start", "2026", "--end", "2028", "--reference", "reconduit",
                     "--wage", "0.03", "--price", "0.02",
                     "--hypothesis-source", "test"]) == 0
    assert _by_year(stubbed.priced) == {2026: {"ppa_revalorisation_avril"},
                                        2027: {"ppa_revalorisation_portee"},
                                        2028: {"ppa_revalorisation_portee"}}
    assert (tmp_path / "reports" / "trajectoire_art74.json").exists()
