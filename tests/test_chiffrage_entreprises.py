"""Pre-registering a FIRM chiffrage — the path the runbook assumed and nobody built.

Step 4 of `docs/PLF2027_RUNBOOK.md` registers through `chiffrage register --scenario`, and
a scenario is a household `ReformSpec`. The CEBGE — the one article the September triage
marked `priceable_now`, and the largest quantified figure of the 2026 annex — had no way
into the registry at all. Found on publication day (2026-10-02), before any figure was
computed, which is the only moment finding it is worth anything.
"""

from __future__ import annotations

import json

import pytest

from impots import preregistration as ch
from impots.entreprises.reforms import FirmReformSpec

#: PLF 2027, art. 15: the third exercice of the CEBGE, at 15,7 % and 31,4 %.
PROROGATION_2027 = {
    "cebge_seuils_et_taux": [{"seuil_ca": 1.5e9, "taux": 0.157},
                             {"seuil_ca": 3e9, "taux": 0.314}],
    "cebge_prorogation_largeur": 1e8,
}


@pytest.fixture(scope="module")
def fixture_firms():
    from impots.entreprises.build import FIXTURE_CELLS, load_cells
    from impots.entreprises.population import build_firms

    cells, ratio, _ = load_cells(FIXTURE_CELLS)
    firms, _ = build_firms(cells, fiscal_to_accounting=ratio)
    return firms


def _tolerance() -> ch.Tolerance:
    return ch.Tolerance(relative=0.30, absolute_eur=200e6,
                        rationale="test : la valeur ne compte pas ici")


def test_a_firm_reform_is_priced_by_the_run_and_registered(tmp_path, monkeypatch,
                                                           fixture_firms) -> None:
    """The figure in the file is the run's, never a number handed in."""
    from impots.entreprises import aggregate, runner

    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    spec = FirmReformSpec.model_validate(PROROGATION_2027)
    ch.register_firm("plf2027_art_15_essai", spec=spec, year=2027, frame=fixture_firms,
                     tolerance=_tolerance(), population_vintage="entreprises-fixture",
                     directory=tmp_path)

    case = ch.load("plf2027_art_15_essai", tmp_path)
    assert case.reform == {"chaine": "entreprises", "annee": 2027,
                           "spec": spec.model_dump(exclude_none=True, mode="json")}
    expected = aggregate.aggregate(
        runner.run(fixture_firms, year=2027, reform=spec).firms).reform_cost
    assert case.mechanical_eur == pytest.approx(expected)
    assert case.mechanical_eur < 0, "a revived contribution raises revenue: a negative cost"
    assert case.commit == "abc1234"


def _population_on_disk(tmp_path, firms, *, synthetic: bool) -> None:
    firms.write_parquet(tmp_path / "firms_essai.parquet")
    (tmp_path / "firms_essai.manifest.json").write_text(
        json.dumps({"cells_are_synthetic": synthetic}), encoding="utf-8")


def _cli(tmp_path, reform_file, *extra: str) -> int:
    from impots.population import cli

    return cli.main([
        "chiffrage", "register-entreprises", "plf2027_art_15_cli",
        "--reform", str(reform_file), "--year", "2027", "--vintage", "essai",
        "--tolerance-relative", "0.30", "--tolerance-absolute", "200e6",
        "--tolerance-rationale", "test", "--dir", str(tmp_path / "cas"), *extra])


def test_the_cli_refuses_a_population_built_on_synthetic_cells(tmp_path, monkeypatch,
                                                               capsys, fixture_firms) -> None:
    """A chiffrage on test cells says nothing about France, and a registry that took one
    would put it on the scoreboard beside the real ones, indistinguishable."""
    import impots.entreprises.build as firm_build

    monkeypatch.setattr(firm_build, "PROCESSED", tmp_path)
    _population_on_disk(tmp_path, fixture_firms, synthetic=True)
    reform_file = tmp_path / "reforme.json"
    reform_file.write_text(json.dumps(PROROGATION_2027), encoding="utf-8")

    assert _cli(tmp_path, reform_file) == 1
    assert "synthétique" in capsys.readouterr().err
    assert not (tmp_path / "cas").exists() or not list((tmp_path / "cas").iterdir())


def test_the_cli_refuses_a_population_without_a_manifest(tmp_path, monkeypatch, capsys,
                                                         fixture_firms) -> None:
    """No manifest, no claim of being real: the API reads a missing manifest as synthetic
    (D-173), and the registry must not be the one place that reads it the other way."""
    import impots.entreprises.build as firm_build

    monkeypatch.setattr(firm_build, "PROCESSED", tmp_path)
    fixture_firms.write_parquet(tmp_path / "firms_essai.parquet")
    reform_file = tmp_path / "reforme.json"
    reform_file.write_text(json.dumps(PROROGATION_2027), encoding="utf-8")

    assert _cli(tmp_path, reform_file) == 1
    assert "synthétique" in capsys.readouterr().err


def test_the_cli_registers_on_a_population_declared_real(tmp_path, monkeypatch,
                                                         fixture_firms) -> None:
    """The twin: the refusal is about the declaration, not about the command."""
    import impots.entreprises.build as firm_build

    monkeypatch.setattr(firm_build, "PROCESSED", tmp_path)
    monkeypatch.setattr(ch, "head_commit", lambda: "abc1234")
    _population_on_disk(tmp_path, fixture_firms, synthetic=False)
    reform_file = tmp_path / "reforme.json"
    reform_file.write_text(json.dumps(PROROGATION_2027), encoding="utf-8")

    assert _cli(tmp_path, reform_file) == 0
    case = ch.load("plf2027_art_15_cli", tmp_path / "cas")
    assert case.population_vintage == "entreprises-essai"
    assert case.reform["annee"] == 2027


def test_the_cli_refuses_a_reform_file_that_is_not_a_firm_reform(tmp_path, monkeypatch,
                                                                 capsys, fixture_firms) -> None:
    """A household knob in a firm file is refused by the wire model, before any run."""
    import impots.entreprises.build as firm_build

    monkeypatch.setattr(firm_build, "PROCESSED", tmp_path)
    _population_on_disk(tmp_path, fixture_firms, synthetic=False)
    reform_file = tmp_path / "reforme.json"
    reform_file.write_text(json.dumps({"decote_taux": 0.5}), encoding="utf-8")

    assert _cli(tmp_path, reform_file) == 1
    assert "decote_taux" in capsys.readouterr().err
