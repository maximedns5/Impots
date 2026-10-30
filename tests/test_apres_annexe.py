"""Un cas neuf écrit après l'annexe, et un scénario qui demande ses IJ (D-306).

Le volet IJ de l'art. 2 du PLF 2027 n'a jamais eu de cas aveugle : il s'enregistre après la
lecture de l'annexe, comme une révision au sens de D-292, comptée à part. Son scénario
demande à la population ses IJ (D-305) ; seul le chiffrage mécanique les impute, et un
chemin qui ne le ferait pas refuse le scénario par son nom.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from impots import preregistration as ch
from impots import scenarios as sc
from impots.api.schemas import ReformSpec

TOLERANCE = ch.Tolerance(relative=0.25, absolute_eur=50e6, rationale="essai")


def _scenario(**overrides) -> sc.Scenario:
    base = dict(name="ij_essai", reform=ReformSpec(csg_ij_taux=0.092), year=2024,
                created="2026-10-30", source="PLF 2027, art. 2", imputations=("ij",))
    return sc.Scenario(**{**base, **overrides})


# --- le scénario et ses imputations ----------------------------------------------------


def test_the_imputations_go_and_come_back_with_the_file(tmp_path) -> None:
    _scenario().save(tmp_path)
    assert json.loads((tmp_path / "ij_essai.json").read_text())["imputations"] == ["ij"]
    assert sc.load("ij_essai", tmp_path).imputations == ("ij",)


def test_a_scenario_without_imputations_writes_none() -> None:
    assert "imputations" not in _scenario(imputations=()).to_dict()


def test_an_unknown_imputation_is_refused() -> None:
    with pytest.raises(sc.ScenarioError, match="inconnues"):
        _scenario(imputations=("epargne",))


def test_a_path_that_would_not_impute_refuses_the_scenario() -> None:
    with pytest.raises(sc.ScenarioError, match="seul le chiffrage mécanique"):
        _scenario().reform_in(2025)
    assert _scenario(imputations=()).reform_in(2024) == ReformSpec(csg_ij_taux=0.092)


def test_the_mechanical_pricing_hands_the_population_its_ij(monkeypatch) -> None:
    from impots.population import aggregate, runner

    seen = {}

    class _Result:
        households = None

    def run(frame, **kwargs):
        seen.update(kwargs)
        return _Result()

    class _Agg:
        reform_cost = -1.0
        deltas = {}

    monkeypatch.setattr(runner, "run", run)
    monkeypatch.setattr(aggregate, "aggregate", lambda households: _Agg())
    sc.mechanical_price(_scenario(), frame=object(), households=10)
    assert seen["impute_ij"] is True
    sc.mechanical_price(_scenario(imputations=()), frame=object(), households=10)
    assert seen["impute_ij"] is False


# --- l'enregistrement après l'annexe ---------------------------------------------------


@pytest.fixture
def repo(tmp_path, monkeypatch):
    def run(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True,
                       text=True)
    run("init", "-q")
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    monkeypatch.setattr(ch, "head_commit", lambda: "c0ffee")
    return {"run": run, "cases": tmp_path / "chiffrages"}


def test_a_case_written_after_the_annex_is_a_revision_of_nothing(repo) -> None:
    ch.register("ij_csg", mechanical_eur=-470e6, tolerance=TOLERANCE,
                population_vintage="2024", sample=20_000, scenario="ij_csg",
                apres_annexe="le volet IJ n'avait pas de cas aveugle",
                directory=repo["cases"], now="2026-10-30T09:00:00+00:00")
    case = ch.load("ij_csg", repo["cases"])
    assert case.revision == {"de": None, "apres_annexe": True,
                             "raison": "le volet IJ n'avait pas de cas aveugle"}


def test_a_blind_registration_carries_no_revision(repo) -> None:
    ch.register("aveugle", mechanical_eur=-1e9, tolerance=TOLERANCE,
                population_vintage="2024", sample=20_000, scenario="aveugle",
                directory=repo["cases"], now="2026-10-30T09:00:00+00:00")
    assert ch.load("aveugle", repo["cases"]).revision is None


def test_a_case_after_the_annex_without_its_reason_is_refused(repo) -> None:
    with pytest.raises(ch.ChiffrageError, match="sans dire pourquoi"):
        ch.register("ij_csg", mechanical_eur=-470e6, tolerance=TOLERANCE,
                    population_vintage="2024", sample=20_000, scenario="ij_csg",
                    apres_annexe="  ", directory=repo["cases"])


def test_the_report_counts_it_apart_from_the_blind_cases(repo) -> None:
    ch.register("ij_csg", mechanical_eur=-470e6, tolerance=TOLERANCE,
                population_vintage="2024", sample=20_000, scenario="ij_csg",
                apres_annexe="le volet IJ n'avait pas de cas aveugle",
                directory=repo["cases"], now="2026-10-30T09:00:00+00:00")
    case = ch.load("ij_csg", repo["cases"])
    comparator = ch.Comparator(
        published_eur=-540e6, source="annexe, art. 2, p. 30", vintage="PLF 2027",
        perimeter="CSG des IJ maladie et AT-MP", net_of="droits constatés 2027",
        sign="yield", basis="premiere-annee", retrieved="2026-10-30")
    repo["run"]("add", "-A")
    repo["run"]("commit", "-q", "-m", "cas")
    # The comparator enters the case file once read, its tolerance untouched (D-292).
    import dataclasses

    import yaml

    path = repo["cases"] / "ij_csg.yaml"
    path.write_text(yaml.safe_dump(dataclasses.replace(case, comparator=comparator).to_dict(),
                                   allow_unicode=True, sort_keys=False), encoding="utf-8")
    repo["run"]("commit", "-qam", "comparateur")
    text = ch.report(repo["cases"])
    blind, revisions = text.split("## Révisions, écrites après l'annexe")
    assert "ij_csg" not in blind
    assert "**0 sur 0 dans la tolérance déclarée.**" in blind
    assert "aucun, cas neuf |" in revisions
    assert "**1 sur 1 dans la tolérance, hors du compte des cas aveugles.**" in revisions
