"""Une mesure bornée aux années que le texte nomme (D-288).

L'art. 15 du PLF 2027 rétablit la CEBGE pour 2027 seulement. Un scénario porte alors
`annees` : le chemin annuel chiffre la mesure ces années-là et une réforme vide les
autres, et son rapport le dit. Les commandes qui chiffrent une année ou une plage sans
lire `annees` refusent les années que le texte ne couvre pas. Le scénario sans `annees`
s'écrit et se relit comme avant, à l'octet.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import polars as pl
import pytest

from impots import scenarios as sc
from impots import service
from impots.api.schemas import ReformSpec
from impots.dette import reference
from impots.entreprises.reforms import FirmReformSpec
from impots.population import aggregate, cli, runner

CEBGE = {"cebge_seuils_et_taux": [{"seuil_ca": 1_500_000_000, "taux": 0.157},
                                  {"seuil_ca": 3_000_000_000, "taux": 0.314}],
         "cebge_prorogation_largeur": 100_000_000}


def make(**overrides) -> sc.Scenario:
    base = dict(name="art15", reform=ReformSpec(), year=2027, created="2026-10-28",
                source="PLF 2027, art. 15", firm_reform=FirmReformSpec(**CEBGE),
                annees=(2027,))
    return sc.Scenario(**{**base, **overrides})


def test_the_years_are_written_and_read_back(tmp_path) -> None:
    path = make().save(tmp_path)
    assert json.loads(path.read_text(encoding="utf-8"))["annees"] == [2027]
    assert sc.load("art15", tmp_path).annees == (2027,)


def test_a_scenario_without_years_writes_none() -> None:
    assert "annees" not in make(annees=()).to_dict()


@pytest.mark.parametrize("annees, needle", [
    ((2028,), "commence"),
    ((2027, 2027), "croissantes"),
    ((2028, 2027), "croissantes"),
])
def test_years_that_do_not_start_at_the_scenario_s_year_or_repeat_are_refused(
        annees: tuple, needle: str) -> None:
    with pytest.raises(sc.ScenarioError, match=needle):
        make(annees=annees)


@pytest.mark.parametrize("annees", [2027, "2027", [2027.0], [True], ["2027"]])
def test_years_that_are_not_whole_years_do_not_load(tmp_path, annees) -> None:
    raw = make().to_dict() | {"annees": annees}
    (tmp_path / "art15.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(sc.ScenarioError, match="annees"):
        sc.load("art15", tmp_path)


def test_a_year_the_text_does_not_cover_is_named_and_refused() -> None:
    make().check_years([2027])
    make(annees=()).check_years([2026, 2027, 2028])
    with pytest.raises(sc.ScenarioError, match=r"\[2026, 2028\]"):
        make().check_years([2026, 2027, 2028])


START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
ARGS = ["predictif", "art15", "--reference", "reconduit", "--spending", "gele_en_volume",
        "--growth-name", "Croissance réelle 1 %, prix 2 %", "--real", "0.01",
        "--prices", "0.02", "--rate-name", "Taux implicite tenu à son niveau de 2025",
        "--rate-kind", "implicite_tenu", "--horizon", "3", "--theta", "0.5",
        "--wage", "0.03", "--hypothesis-source", "test : 2 % de prix, 3 % de salaires"]


@pytest.fixture
def stubbed(monkeypatch, tmp_path) -> SimpleNamespace:
    """A five-person population, firm and household passes that record what they priced,
    and a start that needs no INSEE file."""
    processed = tmp_path / "processed"
    processed.mkdir()
    pl.DataFrame({"person_id": [1, 2, 3, 4, 5], "salaire_brut_annuel": [30_000.0] * 5,
                  "pension_annuelle": [0.0] * 5, "chomage_annuel": [0.0] * 5,
                  "loyer_mensuel": [500.0] * 5}).write_parquet(
        processed / "population_2024.parquet")
    monkeypatch.setattr(cli, "PROCESSED", processed)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    households: list = []
    firms: list = []

    def run(pop, *, year, reform, tier, sample):
        households.append(year)
        return SimpleNamespace(households=SimpleNamespace(cost=5e9))

    def firm_year(firm_reform, year, *, view, growth=None):
        firms.append((year, view))
        return SimpleNamespace(cost=-7e9 * (1.1 if view == "vieillie" else 1.0))

    monkeypatch.setattr(runner, "run", run)
    monkeypatch.setattr(aggregate, "aggregate",
                        lambda households: SimpleNamespace(reform_cost=households.cost,
                                                           totals={}))
    monkeypatch.setattr(service, "firm_first_year", firm_year)
    monkeypatch.setattr(service, "firm_report_note", lambda reform, years: "la note")
    scenarios = tmp_path / "scenarios"
    make().save(scenarios)
    return SimpleNamespace(households=households, firms=firms, scenarios=scenarios,
                           out=tmp_path / "reports")


def _main(stubbed, *extra: str) -> int:
    return cli.main([*ARGS, "--dir", str(stubbed.scenarios), "--out-dir",
                     str(stubbed.out), *extra])


def test_the_path_prices_the_measure_in_its_years_only(stubbed) -> None:
    assert _main(stubbed) == 0
    assert sorted(stubbed.firms) == [(2027, "figee"), (2027, "vieillie")]
    report = json.loads((stubbed.out / "predictif_art15.json").read_text(encoding="utf-8"))
    costs = {row["year"]: (row["mechanical_frozen_eur"], row["mechanical_aged_eur"])
             for row in report["years"]}
    assert costs == {2026: (0.0, 0.0), 2027: (-7e9, -7e9 * 1.1), 2028: (0.0, 0.0)}
    assert report["annees"] == [2027]
    assert any("2027" in line and "la réforme est vide" in line
               for line in report["conventions"])


def test_a_path_without_years_prices_every_year(stubbed) -> None:
    sc.Scenario(**{**vars(make()), "name": "toujours", "annees": ()}).save(stubbed.scenarios)
    assert cli.main([*ARGS[:1], "toujours", *ARGS[2:], "--dir", str(stubbed.scenarios),
                     "--out-dir", str(stubbed.out)]) == 0
    assert sorted({y for y, _ in stubbed.firms}) == [2026, 2027, 2028]
    report = json.loads((stubbed.out / "predictif_toujours.json").read_text(
        encoding="utf-8"))
    assert report["annees"] is None


def test_the_whole_pass_runs_in_the_measure_s_years_only(stubbed, monkeypatch) -> None:
    seen: list = []

    def first(request, *, uprating, macro, view, **firm_part):
        seen.append((request.year, view, bool(firm_part)))
        cost = -7e9
        return SimpleNamespace(cost=cost, inputs=None, impulse={} if macro else None,
                               uncovered={"cebge": "aucune variante"},
                               layers={"menages": 0.0, "entreprises": cost},
                               behaviour_asked=True)

    monkeypatch.setattr(service, "price_first_year", first)
    assert _main(stubbed, "--behavioural") == 0
    assert sorted(seen) == [(2027, "figee", True), (2027, "vieillie", True)]
    report = json.loads((stubbed.out / "predictif_art15.json").read_text(encoding="utf-8"))
    assert [row["mechanical_aged_eur"] for row in report["years"]] == [0.0, -7e9, 0.0]


def test_a_household_measure_bounded_in_years_is_refused_before_any_pass(
        stubbed, capsys) -> None:
    sc.Scenario(**{**vars(make()), "name": "menages",
                   "reform": ReformSpec(decote_taux=0.4)}).save(stubbed.scenarios)
    assert cli.main([*ARGS[:1], "menages", *ARGS[2:], "--dir", str(stubbed.scenarios),
                     "--out-dir", str(stubbed.out)]) == 1
    assert stubbed.households == [] and stubbed.firms == []
    assert "seules entreprises" in capsys.readouterr().err


def test_years_outside_the_path_are_refused_before_any_pass(stubbed, capsys) -> None:
    args = [a if a != "3" else "1" for a in ARGS]
    assert cli.main([*args, "--dir", str(stubbed.scenarios), "--out-dir",
                     str(stubbed.out)]) == 1
    assert stubbed.firms == [] and "[2027]" in capsys.readouterr().err


def test_the_fiche_refuses_a_year_the_text_does_not_cover(stubbed, capsys) -> None:
    assert cli.main(["fiche", "art15", "--dir", str(stubbed.scenarios),
                     "--year", "2026"]) == 1
    assert "[2026]" in capsys.readouterr().err


def test_the_trajectory_refuses_years_the_text_does_not_cover(stubbed, capsys) -> None:
    assert cli.main(["trajectoire", "art15", "--dir", str(stubbed.scenarios),
                     "--start", "2027", "--end", "2028", "--reference", "reconduit",
                     "--wage", "0.03", "--price", "0.02",
                     "--hypothesis-source", "test"]) == 1
    assert stubbed.households == [] and "[2028]" in capsys.readouterr().err
