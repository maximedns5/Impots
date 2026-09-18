"""Phase 8 §2.2 — the aggregate layer, and the four things it refuses to do."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from impots.agregats.engine import (
    ALLOWED_OUTPUTS,
    AggregateError,
    AggregateInstrument,
    DistributionalRefusal,
    RateComponent,
    ReceiptsAnchor,
)
from impots.behavioural.band import Band


@pytest.fixture
def manifest(tmp_path: Path, monkeypatch) -> Path:
    """A manifest this test writes, carrying one sourced and one quarantined file.

    Hermetic on purpose, the lesson `test_an_unsourced_file_cannot_be_opened` already
    paid for: a test keyed to whatever happens to sit in data/raw/ asserts the machine,
    not the behaviour.
    """
    path = tmp_path / "MANIFEST.json"
    path.write_text(json.dumps({"generated": "2026-09-18", "files": {
        "sourced.xlsx": {"url": "https://example.invalid/x.xlsx", "sha256": "a" * 64,
                         "bytes": 1, "downloaded": "2026-09-18", "licence": "Etalab",
                         "description": "", "quarantined": False},
        "quarantined.xlsx": {"url": None, "sha256": "b" * 64, "bytes": 1,
                             "downloaded": "2026-09-18", "licence": "unknown",
                             "description": "", "quarantined": True},
    }}), encoding="utf-8")
    monkeypatch.setattr("impots.population.ingest.MANIFEST_PATH", path)
    return path


def _anchor(file="sourced.xlsx", amount=100e9):
    return ReceiptsAnchor(instrument="TVA", year=2024, amount_eur=amount,
                          manifest_file=file)


#: A sentinel, not None: `components or DEFAULT` silently substitutes the default for an
#: EMPTY tuple, which is falsy — so the "no components" test passed a default and asserted
#: nothing. Caught by that test failing, which is the one way this is ever caught.
_UNSET = object()


def _instrument(*, components=_UNSET, anchor=None, **kw):
    kw.setdefault("elasticity_reason", "aucune ligne de preuve pour cet instrument")
    return AggregateInstrument(
        code="tva", label="Taxe sur la valeur ajoutée",
        anchor=anchor or _anchor(),
        components=(
            RateComponent(code="taux_normal", label="Taux normal", rate=0.20,
                          base_eur=400e9),
            RateComponent(code="taux_reduit", label="Taux réduit", rate=0.055,
                          base_eur=363.636363636e9),
        ) if components is _UNSET else components,
        **kw)


# --------------------------------------------------------------------------- #
# provenance: a number whose file has no URL is not a source
# --------------------------------------------------------------------------- #
def test_an_anchor_on_a_quarantined_file_is_refused(manifest: Path) -> None:
    """D-028 applied where a number ENTERS, not only where a file is opened.

    The implementation that fails this test: taking the anchor's word for it because the
    figure « came from INSEE ». A checksum proves the bytes have not changed; only a URL
    proves where they came from, and a receipts anchor is exactly the kind of number a
    third party must be able to re-fetch.
    """
    with pytest.raises(AggregateError, match="quarantaine"):
        _anchor(file="quarantined.xlsx").verify()


def test_an_anchor_on_a_sourced_file_returns_its_checksum(manifest: Path) -> None:
    assert _anchor().verify() == "a" * 64


def test_an_anchor_on_a_file_nobody_manifested_is_refused(manifest: Path) -> None:
    with pytest.raises(AggregateError, match="n'est pas au manifeste"):
        _anchor(file="invented.xlsx").verify()


def test_a_zero_anchor_is_refused_rather_than_repriced_to_zero() -> None:
    """A null base makes every proportional re-pricing null too, without any error."""
    with pytest.raises(AggregateError, match="ancre de recettes"):
        _anchor(amount=0.0)


# --------------------------------------------------------------------------- #
# THE refusal surface
# --------------------------------------------------------------------------- #
def test_a_decile_split_of_an_aggregate_instrument_is_refused_by_name() -> None:
    """§2.2's kill test: the guard must be SEEN to fire, not merely to exist.

    This is the query a reader makes in good faith, not knowing there is no population
    under the number. Spreading a national total over a population that never produced
    it yields a decile table indistinguishable from a real one.
    """
    with pytest.raises(DistributionalRefusal, match="instrument AGRÉGÉ"):
        _instrument().output("deciles")


def test_every_distributional_output_is_refused_not_just_deciles() -> None:
    from impots.agregats.engine import DISTRIBUTIONAL_OUTPUTS

    instrument = _instrument()
    for name in DISTRIBUTIONAL_OUTPUTS:
        with pytest.raises(DistributionalRefusal):
            instrument.output(name)


def test_the_allowed_outputs_pass() -> None:
    instrument = _instrument()
    for name in ALLOWED_OUTPUTS:
        assert instrument.output(name) == name


def test_an_output_nobody_thought_to_forbid_is_still_refused() -> None:
    """The allowlist's reason for being: a denylist cannot refuse what it never listed."""
    with pytest.raises(AggregateError, match="liste blanche"):
        _instrument().output("carte_par_commune")


# --------------------------------------------------------------------------- #
# the base split must reproduce the published anchor
# --------------------------------------------------------------------------- #
def test_a_base_split_that_misses_the_anchor_refuses_to_reprice() -> None:
    """The AFT Block-1 discipline: reconstruct the published total, or do not proceed.

    The implementation that fails this test: warning and carrying on. Re-pricing off an
    unvalidated split produces a figure exactly as clean-looking as a correct one.
    """
    wrong = (RateComponent(code="taux_normal", label="Taux normal", rate=0.20,
                           base_eur=200e9),)
    with pytest.raises(AggregateError, match="ventilation d'assiette"):
        _instrument(components=wrong).reprice({"taux_normal": 0.21})


def test_a_split_inside_tolerance_is_accepted_and_returns_its_residual() -> None:
    residual = _instrument().check_base_split()
    assert abs(residual) < 0.01


# --------------------------------------------------------------------------- #
# mechanical re-pricing
# --------------------------------------------------------------------------- #
def test_repricing_at_the_enacted_rates_reproduces_the_baseline_exactly() -> None:
    """The no-op case, asserted because a re-pricing that moves when nothing changed is
    broken in a way every other test would still pass through."""
    result = _instrument().reprice({})
    assert result.delta_eur == pytest.approx(0.0, abs=1.0)


def test_a_rate_for_an_unknown_component_is_refused_not_ignored() -> None:
    """Silently dropped, it would price the reform as a no-op: a confident zero."""
    with pytest.raises(AggregateError, match="composants inconnus"):
        _instrument().reprice({"taux_intermediaire": 0.10})


def test_a_rate_rise_prices_as_rate_times_base() -> None:
    result = _instrument().reprice({"taux_normal": 0.21})
    assert result.delta_eur == pytest.approx(0.01 * 400e9, rel=1e-9)


# --------------------------------------------------------------------------- #
# behaviour: absent is said, never shown as zero
# --------------------------------------------------------------------------- #
def test_a_missing_elasticity_says_so_rather_than_showing_zero() -> None:
    note = _instrument().band_note()
    assert "aucune réponse comportementale modélisée" in note
    assert "0" not in note.replace("comportementale", "")


def test_an_instrument_without_a_band_must_say_why() -> None:
    with pytest.raises(AggregateError, match="aucune bande et aucune raison"):
        _instrument(elasticity_reason="  ")


def test_a_band_carrying_the_no_evidence_grade_is_refused() -> None:
    """A band with no evidence behind it will be read as measured."""
    with pytest.raises(AggregateError, match="no-evidence"):
        _instrument(elasticity=Band(p10=-1.0, p50=0.0, p90=1.0),
                    elasticity_grade="no-evidence")


# --------------------------------------------------------------------------- #
# codes, not labels
# --------------------------------------------------------------------------- #
def test_duplicate_component_codes_are_refused() -> None:
    dupes = (RateComponent(code="t", label="A", rate=0.2, base_eur=1e9),
             RateComponent(code="t", label="B", rate=0.1, base_eur=1e9))
    with pytest.raises(AggregateError, match=r"doublon|double"):
        _instrument(components=dupes)


def test_a_component_without_a_code_is_refused() -> None:
    with pytest.raises(AggregateError, match="sans code"):
        RateComponent(code="  ", label="Taux normal", rate=0.2, base_eur=1e9)


def test_an_instrument_with_no_components_is_refused() -> None:
    with pytest.raises(AggregateError, match="aucun composant"):
        _instrument(components=())


# --------------------------------------------------------------------------- #
# M2 DoD — the double-entry identity, extended and tested against a broken ledger
# --------------------------------------------------------------------------- #
def test_a_mixed_micro_and_aggregate_scenario_balances() -> None:
    """A bundle spanning both layers must close across both."""
    from impots import guards

    result = guards.sector_balance({"ir": 1e9}, reform_cost=-3e9,
                                   aggregate_deltas={"tva": 2e9})
    assert result["unexplained"] == pytest.approx(0.0, abs=1.0)
    assert result["aggregate"] == pytest.approx(2e9)


def test_the_identity_fires_on_a_deliberately_broken_ledger() -> None:
    """M2's DoD, stated as such: tested against a ledger broken ON PURPOSE.

    The TVA moved 2 md€ and the headline reports only the IR. That is exactly the shape
    of the bug the original guard was written for — one sector moving without entering
    the reported cost — now reproduced across the aggregate layer.
    """
    from impots import guards

    with pytest.raises(guards.SectorBalanceError, match="ne correspond pas"):
        guards.sector_balance({"ir": 1e9}, reform_cost=-1e9,
                              aggregate_deltas={"tva": 2e9})


def test_the_aggregate_term_is_load_bearing_and_not_derived_from_the_headline() -> None:
    """THE test the first double-entry guard's history demands.

    That guard wrote the state's side in terms of the firm's, so removing the firm term
    moved both sides together and the identity balanced at zero — it could not catch the
    bug it existed for. So the extension must be shown to be INDEPENDENT of the headline:
    take a scenario that balances WITH the aggregate term, drop only that argument, and
    the identity must break. An implementation that reconstructed the aggregate side from
    `reform_cost` would keep passing here, and that is the implementation being excluded.
    """
    from impots import guards

    guards.sector_balance({"ir": 1e9}, reform_cost=-3e9, aggregate_deltas={"tva": 2e9})
    with pytest.raises(guards.SectorBalanceError, match="ne correspond pas"):
        guards.sector_balance({"ir": 1e9}, reform_cost=-3e9)


def test_an_instrument_on_both_sides_is_refused_as_a_double_count() -> None:
    """The risk the extension creates, guarded where it is created.

    Counted twice, the identity would demand a headline that double-counts it too — and
    would then blame the breach on the headline, sending the reader to fix the one thing
    that was right.
    """
    from impots import guards

    with pytest.raises(guards.SectorBalanceError, match="DEUX FOIS"):
        guards.sector_balance({"ir": 1e9}, reform_cost=-2e9,
                              aggregate_deltas={"ir": 1e9})


def test_an_aggregate_receipts_rise_is_a_gain_to_the_state() -> None:
    """Sign convention, asserted in both directions — a sign error here inverts the
    whole bundle while still balancing internally."""
    from impots import guards

    guards.sector_balance({}, reform_cost=-2e9, aggregate_deltas={"tva": 2e9})
    guards.sector_balance({}, reform_cost=2e9, aggregate_deltas={"tva": -2e9})
    with pytest.raises(guards.SectorBalanceError):
        guards.sector_balance({}, reform_cost=2e9, aggregate_deltas={"tva": 2e9})
