"""M1 — the macro parameter store, its refusals, and the kill tests for both.

Two things are pinned here that matter more than the values. First, the store refuses
every row that no verifier has passed — which today is all of them, and the suite says
so out loud rather than letting an unverified band look like a verified one. Second,
the multiplier values live in the PDF and not in the YAML, so the test that would catch
a transcription error is the one asserting there is nothing to transcribe.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from impots.behavioural.store import UnverifiedParameter
from impots.macro import mesange, store

pytest.importorskip("pypdf")

HAVE_SOURCE = (mesange.RAW / mesange.SOURCE_FILE).exists()
needs_source = pytest.mark.skipif(
    not HAVE_SOURCE,
    reason="data/raw/ has no Mésange document — primary sources are not committed",
)

VERIFIED = {
    "value": {"central": 1.0, "low": 0.5, "high": 1.5},
    "applies_to": "a row that passed",
    "support": {"estimated_on": "somewhere"},
    "source": {"citation": "a paper"},
    "verifier": {"verdict": "CONFIRMED", "date": "2026-09-03", "ref": "wf_test"},
}


# --- the refusal, and the proof it is not simply refusing everything ---------------


def test_the_store_refuses_every_row_today():
    """M1's honest state: located and parsed, not yet independently verified."""
    with pytest.raises(UnverifiedParameter, match="verdict None"):
        store.load()


def test_non_strict_reports_what_is_missing_instead_of_raising():
    reported = store.load(strict=False)
    assert reported.parameters == {} and reported.tables == {}
    assert set(reported.rejected) == {
        "multiplier_by_instrument", "employment_by_instrument", "revenue_gdp_elasticity",
    }
    for reason in reported.rejected.values():
        assert "CONFIRMED" in reason


def test_a_verified_row_loads(tmp_path: Path):
    """The other half of the refusal: a passed verdict must actually get through."""
    (tmp_path / "x.yaml").write_text(
        yaml.safe_dump({"parameters": {"ok": VERIFIED}}), encoding="utf-8")
    loaded = store.load(tmp_path)
    assert loaded["ok"].central == 1.0


@pytest.mark.parametrize("verdict", [None, "WRONG", "PENDING", ""])
def test_only_the_two_loadable_verdicts_pass(tmp_path: Path, verdict):
    body = {**VERIFIED, "verifier": {**VERIFIED["verifier"], "verdict": verdict}}
    (tmp_path / "x.yaml").write_text(
        yaml.safe_dump({"parameters": {"ok": body}}), encoding="utf-8")
    with pytest.raises(UnverifiedParameter):
        store.load(tmp_path)


# --- the values are not in the file that declares them -----------------------------


def test_the_multiplier_yaml_contains_no_multipliers():
    """D-026 in the form a test can check: nothing to transcribe, nothing to drift."""
    document = yaml.safe_load(
        (store.PARAMETERS / "multipliers.yaml").read_text(encoding="utf-8"))
    for key, body in document["parameters"].items():
        value = body["value"]
        assert "from_source_table" in value, f"{key} declares a literal value"
        assert not any(isinstance(v, (int, float)) for v in value.values()), key


@needs_source
def test_table_values_are_the_parsed_ones(tmp_path: Path):
    document = yaml.safe_load(
        (store.PARAMETERS / "multipliers.yaml").read_text(encoding="utf-8"))
    body = document["parameters"]["multiplier_by_instrument"]
    body["verifier"] = dict(VERIFIED["verifier"])
    (tmp_path / "m.yaml").write_text(
        yaml.safe_dump({"parameters": {"multiplier_by_instrument": body},
                        "source_table": document["source_table"]}), encoding="utf-8")
    loaded = store.load(tmp_path)
    table = loaded.tables["multiplier_by_instrument"]
    assert table.at("impot_sur_le_revenu", "1") == pytest.approx(0.41)
    assert table.profile("investissement_public") == mesange.load()["investissement_public"].multiplier


# --- the parse itself --------------------------------------------------------------


@needs_source
def test_all_eight_variants_parse_with_the_published_values():
    variants = mesange.load()
    assert set(variants) == set(mesange.VARIANTS)
    # Spot values read off the published tables, pinned so a re-parse cannot drift.
    assert variants["investissement_public"].multiplier[:3] == (1.31, 1.38, 1.22)
    assert variants["cotisations_employeurs"].jobs[:3] == (83.0, 210.0, 290.0)
    assert variants["depense_publique"].at("gdp", "LT") == pytest.approx(0.16)


@needs_source
def test_the_sign_convention_reverses_the_whole_shock_not_part_of_it():
    """A VAT cut raises GDP *and* costs the budget; both, or the row is incoherent."""
    tva = mesange.load()["tva"]
    assert tva.published_sign == -1
    assert tva.multiplier[0] > 0, "a VAT cut must raise GDP in the expansionary convention"
    assert tva.rows["solde_primaire_pts_pib"][0] < 0, "and must cost the primary balance"
    assert tva.jobs[0] > 0


@needs_source
def test_an_instrument_without_a_published_variant_raises(tmp_path: Path):
    """It must not borrow a neighbour's multiplier."""
    document = yaml.safe_load(
        (store.PARAMETERS / "multipliers.yaml").read_text(encoding="utf-8"))
    body = document["parameters"]["multiplier_by_instrument"]
    body["verifier"] = dict(VERIFIED["verifier"])
    (tmp_path / "m.yaml").write_text(
        yaml.safe_dump({"parameters": {"multiplier_by_instrument": body},
                        "source_table": document["source_table"]}), encoding="utf-8")
    table = store.load(tmp_path).tables["multiplier_by_instrument"]
    with pytest.raises(KeyError, match="impot_societes"):
        table.at("impot_societes", "1")


@needs_source
def test_a_revised_document_raises_rather_than_guessing(monkeypatch):
    """Kill test: if INSEE reprints the variant, the parser must stop, not approximate."""
    monkeypatch.setitem(mesange.VARIANTS, "tva", ("Hausse de la TVA de 2 % du PIB", -1))
    with pytest.raises(mesange.MesangeError, match="not found"):
        mesange.load()


@needs_source
def test_a_row_with_the_wrong_column_count_raises(monkeypatch):
    """Kill test: a table whose horizons changed must not be read as if they had not."""
    monkeypatch.setattr(mesange, "HORIZONS", ("1", "2", "3", "5", "10", "LT", "extra"))
    with pytest.raises(mesange.MesangeError, match="expected 7"):
        mesange.load()


def test_an_absent_source_file_kills_the_row_loudly(tmp_path: Path):
    with pytest.raises(mesange.MesangeError, match="not found"):
        mesange.load(raw=tmp_path)


# --- dead rows are visible, with reasons -------------------------------------------


@pytest.mark.parametrize("key", [
    "multiplier_slack_state",
    "multiplier_confidence_band",
    "multiplier_impot_societes",
    "revenue_elasticity_by_cycle_state",
    "mpc_by_income_position",
])
def test_every_dead_row_says_why(key):
    """A channel that shrinks must show why — not merely have fewer inputs."""
    reason = store.load(strict=False).why_removed(key)
    assert len(reason) > 200, f"{key} was removed without a real reason"


def test_the_two_seeds_the_spec_supplied_are_both_dead_or_sourced():
    """The spec's 1.3-2.5 slack seed and its MPC row: neither survived M1."""
    reported = store.load(strict=False)
    assert "Mésange est un modèle linéaire" in reported.removed["multiplier_slack_state"]
    assert "PATRIMOINE" in reported.removed["mpc_by_income_position"]
