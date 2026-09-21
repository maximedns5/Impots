"""Phase 8 §2.4 — the coverage table's claims, checked against the code they describe.

A triage that drifts from the code it describes is worse than no triage: it will be
believed on the day it matters. So every name the table claims the tool carries is
resolved here, and every classification must say the thing its bucket requires.
"""

from __future__ import annotations

import pytest

from impots import instrument_coverage as ic


@pytest.fixture(scope="module")
def knobs():
    from impots.engine.reforms import PLAFOND_KNOBS, SCALAR_KNOBS
    return set(SCALAR_KNOBS), set(PLAFOND_KNOBS)


@pytest.fixture(scope="module")
def firm_fields():
    from impots.api.schemas import FirmReformSpec
    return set(FirmReformSpec.model_fields)


@pytest.fixture(scope="module")
def aggregate_codes():
    from impots.agregats.instruments import PROPORTIONAL
    return {spec.code for spec in PROPORTIONAL}


# --------------------------------------------------------------------------- #
# the table cannot claim what the code does not carry
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("instrument", ic.INVENTORY, ids=lambda i: i.code)
def test_every_name_the_table_claims_resolves(instrument, knobs, firm_fields,
                                              aggregate_codes) -> None:
    """The one that matters. A row naming a knob that does not exist claims the tool
    prices something it cannot, and no reader would catch it."""
    scalar, plafond = knobs
    for name in instrument.prices_with:
        kind, _, value = name.partition(":")
        if kind == "knob":
            assert value in scalar, f"{instrument.code}: knob {value!r} inconnu"
        elif kind == "plafond":
            assert value in plafond, f"{instrument.code}: plafond {value!r} inconnu"
        elif kind == "firm":
            assert value in firm_fields, f"{instrument.code}: champ firme {value!r} inconnu"
        elif kind == "agregats":
            assert value in aggregate_codes, (
                f"{instrument.code}: instrument agrégé {value!r} non déclaré")
        else:
            pytest.fail(f"{instrument.code}: préfixe inconnu dans {name!r}")


def test_the_claim_would_fail_if_a_name_went_stale(knobs, firm_fields,
                                                   aggregate_codes) -> None:
    """The kill half, so the check above is not trusted on faith."""
    scalar, plafond = knobs
    ghost = ic.Instrument("x", "x", "produits", "A", prices_with=("knob:nexistepas",))
    with pytest.raises(AssertionError, match="inconnu"):
        test_every_name_the_table_claims_resolves(ghost, (scalar, plafond), firm_fields,
                                                  aggregate_codes)


# --------------------------------------------------------------------------- #
# every bucket must say the thing its bucket requires
# --------------------------------------------------------------------------- #
def test_every_instrument_is_classified_exactly_once() -> None:
    codes = [i.code for i in ic.INVENTORY]
    assert len(codes) == len(set(codes))
    assert sum(len(ic.by_bucket(b)) for b in ic.BUCKETS) == len(ic.INVENTORY)


@pytest.mark.parametrize("instrument", ic.by_bucket("C"), ids=lambda i: i.code)
def test_a_gated_instrument_names_its_gate(instrument) -> None:
    """« Gated » with no gate named is « not done » with better clothes."""
    assert instrument.gate.strip(), f"{instrument.code}: bucket C sans gate nommé"


@pytest.mark.parametrize("instrument", ic.by_bucket("D"), ids=lambda i: i.code)
def test_a_refusal_carries_its_reason(instrument) -> None:
    """§2.1: refusals are allowlists that SPEAK. A D row with no reason is a silent
    omission wearing a classification."""
    assert len(instrument.reason.strip()) > 40, f"{instrument.code}: refus sans raison"


@pytest.mark.parametrize("instrument", ic.classified_but_unbuilt(), ids=lambda i: i.code)
def test_a_classified_but_unbuilt_instrument_says_what_blocks_it(instrument) -> None:
    """The rows that would otherwise flatter the count: classified A/B, priced by
    nothing. Each must say what is missing."""
    assert instrument.note.strip(), f"{instrument.code}: ni levier ni blocage nommé"


# --------------------------------------------------------------------------- #
# the headline is computed, and it is honest about what it counts
# --------------------------------------------------------------------------- #
def test_classification_is_not_pricing() -> None:
    """The overstatement §2.4 exists to prevent: TVA and the four accises are bucket B
    and priced by nothing, and counting them as priced would inflate the claim."""
    unbuilt = {i.code for i in ic.classified_but_unbuilt()}
    assert "tva" in unbuilt
    assert {"accise_energies", "accise_tabacs", "accise_alcools"} <= unbuilt
    assert unbuilt.isdisjoint({i.code for i in ic.priced()})


def test_the_share_is_computed_not_typed() -> None:
    assert ic.share_priced() == pytest.approx(len(ic.priced()) / len(ic.INVENTORY))


def test_the_nine_new_aggregate_instruments_are_what_phase_8_added(aggregate_codes) -> None:
    """What the phase ADDED, as opposed to what it inherited and re-declared — the
    distinction a coverage claim is worthless without."""
    added = {i.code for i in ic.new_in_phase_8()}
    assert added == aggregate_codes
    assert not any(i.already_live for i in ic.new_in_phase_8())


def test_no_row_carries_a_euro_figure() -> None:
    """§2.4 wants the claim weighed by receipts; this repository has neither the Voies
    et Moyens universe nor a recorded threshold, so the table counts and says so. A
    figure appearing here would be one nobody could source."""
    import re
    for instrument in ic.INVENTORY:
        text = f"{instrument.note} {instrument.reason}"
        money = re.findall(r"\d[\d\s]*(?:md€|Md€|M€|milliards?)", text)
        assert not money, f"{instrument.code}: chiffre de recettes dans la table: {money}"


# --------------------------------------------------------------------------- #
# la garde anti-dérive du document rendu (D-155)
# --------------------------------------------------------------------------- #
def test_the_committed_coverage_document_is_what_the_script_renders() -> None:
    """D-154 retourné contre lui-même : « un triage qui dérive du code qu'il décrit sera
    cru le jour J » vaut aussi pour la page qui le publie.

    La comparaison est inconditionnelle ici, contrairement à celle de
    `test_explorer_example.py` : cette page se rend depuis le code seul, sans lire un
    fichier de données, donc son rendu attendu est le même sur toute machine.

    Tombe dès qu'on édite `docs/COVERAGE_INSTRUMENTS.md` à la main — vérifié.
    """
    import importlib.util
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "write_instrument_coverage.py"
    spec = importlib.util.spec_from_file_location("write_instrument_coverage", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    doc = root / "docs" / "COVERAGE_INSTRUMENTS.md"
    assert doc.read_text(encoding="utf-8") == module.render(), (
        "docs/COVERAGE_INSTRUMENTS.md a dérivé de scripts/write_instrument_coverage.py — "
        "relancer le script plutôt que d'éditer la page.")
