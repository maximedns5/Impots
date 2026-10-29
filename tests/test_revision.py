"""Une révision écrite après l'annexe (D-292) : un nouveau cas, sur la base du publié, compté
à part.

L'art. 2 a été enregistré en année pleine et noté contre l'effet budgétaire de 2027 que
l'annexe publie : une discordance de base (D-204, D-291). La révision ne change que la
base, par `impots.pas`, sur le chiffre enregistré lui-même. Elle garde sa tolérance et son
comparateur, porte le cas qu'elle révise et le dit écrite après l'ouverture de l'annexe ;
le rapport la compte hors des cas aveugles. L'enregistrement d'origine ne bouge pas.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from impots import preregistration as ch

TOLERANCE = ch.Tolerance(relative=0.20, absolute_eur=200e6, rationale="essai")


def _comparator(**overrides) -> ch.Comparator:
    base = dict(published_eur=4.2e9, source="annexe, art. 2", vintage="PLF 2027",
                perimeter="le volet barème", net_of="avis 2026 et PAS 2027", sign="cost",
                basis="premiere-annee", retrieved="2026-10-14")
    return ch.Comparator(**{**base, **overrides})


@pytest.fixture
def repo(tmp_path, monkeypatch):
    def run(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True,
                       text=True)
    run("init", "-q")
    run("config", "user.email", "t@t")
    run("config", "user.name", "t")
    monkeypatch.setattr(ch, "head_commit", lambda: "c0ffee")
    cases, scenarios = tmp_path / "chiffrages", tmp_path / "scenarios"
    scenarios.mkdir()
    (scenarios / "art2.json").write_text(json.dumps({
        "name": "art2", "year": 2026, "created": "2026-10-02", "source": "PLF 2027, art. 2",
        "note": "", "tags": [], "reform": {"decote_seuil_celib": 915.0}}), encoding="utf-8")
    original = ch.Chiffrage(
        case="art2", pre_registered="2026-10-14T15:47:18+00:00", commit="b24de21",
        population_vintage="2024", sample=20_000, engine={"openfisca_france": "176.0.8"},
        mechanical_eur=3.0e9, tolerance=TOLERANCE, scenario="art2",
        comparator=_comparator())
    ch.save(original, cases)
    run("add", "-A")
    run("commit", "-q", "-m", "enregistrement")
    return {"run": run, "cases": cases, "scenarios": scenarios}


def _revise(repo, **overrides):
    kwargs = dict(year=2027, raison="la base de l'annexe", directory=repo["cases"],
                  scenarios_dir=repo["scenarios"], now="2026-10-29T09:00:00+00:00")
    return ch.revise_to_budget_year("art2", "art2_base2027", **{**kwargs, **overrides})


def test_the_revision_changes_the_basis_and_nothing_else(repo) -> None:
    _revise(repo)
    original, revised = ch.load("art2", repo["cases"]), ch.load("art2_base2027", repo["cases"])
    assert revised.mechanical_eur == pytest.approx(4.0e9)
    assert revised.tolerance == original.tolerance
    assert revised.comparator == original.comparator
    assert (revised.scenario, revised.sample, revised.engine) == (
        original.scenario, original.sample, original.engine)
    assert (revised.pre_registered, revised.commit) == ("2026-10-29T09:00:00+00:00", "c0ffee")
    assert revised.revision["de"] == "art2" and revised.revision["apres_annexe"] is True
    assert revised.revision["annee_pleine_eur"] == original.mechanical_eur
    assert revised.revision["annee_budgetaire"] == 2027
    assert original.mechanical_eur == 3.0e9 and original.revision is None


def test_a_case_without_a_revision_writes_none() -> None:
    plain = ch.Chiffrage(case="x", pre_registered="t", commit="c", population_vintage="2024",
                         sample=1, engine={}, mechanical_eur=1.0, tolerance=TOLERANCE,
                         scenario="s")
    assert "revision" not in plain.to_dict()


@pytest.mark.parametrize("change, needle", [
    (dict(comparator=None), "pas de comparateur"),
    (dict(comparator=_comparator(basis="annee-pleine")), "année pleine"),
    (dict(scenario=None, reform={"chaine": "entreprises"}), "impôt sur le revenu"),
])
def test_a_case_the_basis_cannot_be_revised_on_is_refused(repo, change, needle) -> None:
    base = ch.load("art2", repo["cases"])
    import dataclasses
    other = dataclasses.replace(base, case="autre", **change)
    ch.save(other, repo["cases"])
    with pytest.raises(ch.ChiffrageError, match=needle):
        ch.revise_to_budget_year("autre", "autre_rev", year=2027, raison="r",
                                 directory=repo["cases"], scenarios_dir=repo["scenarios"])


def test_a_budget_year_before_the_measure_s_second_is_refused(repo) -> None:
    with pytest.raises(ch.ChiffrageError, match="2026"):
        _revise(repo, year=2026)


def test_a_revision_is_never_written_over(repo) -> None:
    _revise(repo)
    with pytest.raises(ch.ChiffrageError, match="existe déjà"):
        _revise(repo)


def test_the_report_counts_the_revision_apart_from_the_blind_cases(repo) -> None:
    _revise(repo)
    repo["run"]("add", "-A")
    repo["run"]("commit", "-q", "-m", "révision")
    text = ch.report(repo["cases"])
    head, _, revisions = text.partition("## Révisions, écrites après l'annexe")
    assert "| art2 |" in head and "art2_base2027" not in head
    assert "**0 sur 1 dans la tolérance déclarée.**" in head
    rows = [line for line in revisions.splitlines() if line.startswith("|")]
    assert all(row.endswith("|") and row.count("|") == rows[0].count("|") for row in rows)
    assert "révise" in rows[0] and rows[-1].startswith("| art2_base2027 |")
    assert rows[-1].endswith("| art2 |")
    assert "**1 sur 1 dans la tolérance, hors du compte des cas aveugles.**" in revisions


def test_a_report_without_revisions_reads_as_before(repo) -> None:
    text = ch.report(repo["cases"])
    assert "Révisions" not in text and "**0 sur 1 dans la tolérance déclarée.**" in text


def test_an_unreadable_scenario_is_a_registry_refusal(repo) -> None:
    (repo["scenarios"] / "art2.json").write_text("{", encoding="utf-8")
    with pytest.raises(ch.ChiffrageError, match="scénario ne se lit pas"):
        _revise(repo)


def test_the_command_revises_into_the_named_case(repo, capsys, monkeypatch) -> None:
    from impots import scenarios as scenarios_module
    from impots.population import cli

    real = scenarios_module.load
    monkeypatch.setattr(scenarios_module, "load",
                        lambda name, directory=None: real(name, repo["scenarios"]))
    argv = ["chiffrage", "revise", "art2", "--as", "art2_base2027", "--annee", "2027",
            "--raison", "la base", "--dir", str(repo["cases"])]
    assert cli.main(argv) == 0
    assert "+4.000 md" in capsys.readouterr().out
    assert ch.load("art2_base2027", repo["cases"]).revision["raison"] == "la base"
    assert cli.main(argv) == 1
    assert "existe déjà" in capsys.readouterr().err


def test_a_revision_outside_its_tolerance_is_counted_outside(repo) -> None:
    import dataclasses
    small = dataclasses.replace(ch.load("art2", repo["cases"]), case="petit",
                                mechanical_eur=1.0e9)
    ch.save(small, repo["cases"])
    ch.revise_to_budget_year("petit", "petit_rev", year=2027, raison="r",
                             directory=repo["cases"], scenarios_dir=repo["scenarios"])
    repo["run"]("add", "-A")
    repo["run"]("commit", "-q", "-m", "révision hors tolérance")
    revisions = ch.report(repo["cases"]).partition("## Révisions, écrites après l'annexe")[2]
    assert "**0 sur 1 dans la tolérance, hors du compte des cas aveugles.**" in revisions
