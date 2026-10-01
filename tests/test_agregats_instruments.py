"""Phase 8 §2.3 — the proportional instruments, and the table their numbers come from.

Runs on `tests/fixtures/receipts_anchors_fixture.json`, whose amounts are invented and
whose manifest filenames are real. That split is deliberate: the provenance guard is
the one thing a fixture must not fake, so the rows point at a file that really is
sourced in the real manifest, and the euros are shapes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from impots.agregats.anchors import (
    VINTAGE_CONVENTIONS,
    AnchorTableMissing,
    load_anchors,
)
from impots.agregats.engine import AggregateError, DistributionalRefusal
from impots.agregats.instruments import (
    PROPORTIONAL,
    SCALE_CODE,
    build_all,
    proportional_instrument,
    scale,
)

FIXTURE = Path(__file__).parent / "fixtures" / "receipts_anchors_fixture.json"


@pytest.fixture
def anchors():
    return load_anchors(FIXTURE)


def _rows():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["anchors"]


def _table(tmp_path: Path, rows) -> Path:
    path = tmp_path / "receipts_anchors.json"
    path.write_text(json.dumps({"anchors": rows}), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# the table, and the four ways it refuses
# --------------------------------------------------------------------------- #
def test_an_absent_table_says_what_to_do_rather_than_failing_obscurely(tmp_path) -> None:
    """The expected state of any checkout without data/raw/, so it must READ that way.

    Fails if the table is ever given a default or an empty fallback: an instrument built
    on a placeholder anchor would price a reform and look exactly like one built on the
    published figure.
    """
    with pytest.raises(AnchorTableMissing, match="M2_ANCHORS"):
        load_anchors(tmp_path / "nothing.json")


def test_a_row_without_a_vintage_convention_is_refused(tmp_path) -> None:
    """The kill test for the convention guard. Voies et Moyens columns are BUDGET years,
    and three times already the comparator's calendar WAS the entire error."""
    rows = _rows()
    rows[0] = {**rows[0], "vintage_convention": "annee"}
    with pytest.raises(AggregateError, match="millésime"):
        load_anchors(_table(tmp_path, rows))


def test_every_declared_convention_is_actually_accepted(tmp_path) -> None:
    """The other half: a guard that refused everything would pass the test above while
    making the table unusable."""
    for convention in VINTAGE_CONVENTIONS:
        rows = [{**_rows()[0], "vintage_convention": convention}]
        loaded = load_anchors(_table(tmp_path, rows))
        assert convention in loaded["tsn"].note


def test_two_rows_for_one_instrument_are_refused(tmp_path) -> None:
    """Otherwise one wins by file order — a figure chosen by accident."""
    rows = _rows()
    rows.append({**rows[0], "amount_eur": rows[0]["amount_eur"] * 2})
    with pytest.raises(AggregateError, match="deux lignes"):
        load_anchors(_table(tmp_path, rows))


def test_a_row_pointing_at_an_unmanifested_file_is_refused(tmp_path) -> None:
    """D-028 at the point a number enters, and D-152's trap: « absent » and « not
    reproducible » look the same from a distance and are not the same thing."""
    rows = [{**_rows()[0], "manifest_file": "personne_ne_l_a_manifeste.pdf"}]
    with pytest.raises(AggregateError, match="manifeste"):
        load_anchors(_table(tmp_path, rows))


# --------------------------------------------------------------------------- #
# the instruments
# --------------------------------------------------------------------------- #
def test_the_fixture_builds_every_declared_instrument(anchors) -> None:
    built, missing = build_all(anchors)
    assert not missing
    assert set(built) == {spec.code for spec in PROPORTIONAL}


def test_an_instrument_without_an_anchor_row_is_named_missing_not_invented(anchors) -> None:
    """Coverage counts what EXISTS. A placeholder anchor would make the count a promise."""
    built, missing = build_all({k: v for k, v in anchors.items() if k != "dmto"})
    assert missing == ("dmto",)
    assert "dmto" not in built


def test_the_scale_component_does_not_read_as_a_tax_rate(anchors) -> None:
    """`rate=1.0` on a component is arithmetically right and looks like a 100 % tax.

    Fails the day someone relabels it: the label is the only thing between a reader and
    that misreading, since the engine cannot tell a scale factor from a rate.
    """
    instrument = proportional_instrument(PROPORTIONAL[0], anchors["tsn"])
    component = instrument.components[0]
    assert component.rate == 1.0
    assert "FACTEUR D'ÉCHELLE" in component.label
    assert "pas un taux" in component.label


def test_a_proportional_reprice_is_exactly_the_factor(anchors) -> None:
    instrument = proportional_instrument(PROPORTIONAL[0], anchors["tsn"])
    result = instrument.reprice(scale(1.10))
    assert result.baseline_eur == pytest.approx(anchors["tsn"].amount_eur)
    assert result.reformed_eur == pytest.approx(anchors["tsn"].amount_eur * 1.10)
    assert result.delta_eur == pytest.approx(anchors["tsn"].amount_eur * 0.10)


def test_the_split_check_is_exact_and_proves_nothing(anchors) -> None:
    """Residual 0 by construction, because the split IS the anchor.

    Pinned so nobody later reads a proportional instrument's clean residual as a
    validation — the check has nothing independent to compare against here.
    """
    instrument = proportional_instrument(PROPORTIONAL[1], anchors["ttf"])
    assert instrument.check_base_split() == pytest.approx(0.0, abs=1e-12)


def test_every_instrument_refuses_a_decile_split(anchors) -> None:
    """The refusal surface survives construction — asserted on the built objects, not on
    a hand-made one, because it is the built ones a user will meet."""
    built, _ = build_all(anchors)
    for instrument in built.values():
        with pytest.raises(DistributionalRefusal, match="AGRÉGÉ"):
            instrument.output("deciles")


def test_every_instrument_says_why_it_has_no_band(anchors) -> None:
    """« aucune réponse comportementale modélisée » must carry its reason. A band of
    zero and a band nobody measured render identically without it."""
    built, _ = build_all(anchors)
    for code, instrument in built.items():
        note = instrument.band_note()
        assert note.startswith("aucune réponse comportementale modélisée"), code
        assert len(note) > 60, f"{code}: reason too thin to be a reason"


def test_the_reform_argument_is_keyed_to_the_one_component_code(anchors) -> None:
    """`scale()` and the component must agree, or a reform would be priced at zero.

    The engine refuses an unknown code rather than ignoring it, so a drift between the
    two would raise — but it would raise at the first reform somebody prices, not here.
    """
    instrument = proportional_instrument(PROPORTIONAL[2], anchors["taxe_sur_les_salaires"])
    assert instrument.components[0].code == SCALE_CODE
    assert set(scale(1.0)) == {SCALE_CODE}
    assert instrument.reprice(scale(1.0)).delta_eur == pytest.approx(0.0)


def test_no_money_figure_is_written_into_the_instrument_module() -> None:
    """The rule this module exists for: the euros come from the table, never the code.

    Fails the day someone writes an amount into `instruments.py` — which is exactly how
    a recollection gets a source's clothes. Money-shaped literals only: `1.0` is the
    scale factor and has to stay.
    """
    source = Path("src/impots/agregats/instruments.py").read_text(encoding="utf-8")
    money = re.findall(r"\b\d[\d_]{3,}(?:\.\d+)?\b|\b\d+(?:\.\d+)?e\d+\b", source)
    assert not money, f"figures written into the module instead of the table: {money}"
    assert "amount_eur=" not in source


# --------------------------------------------------------------------------- #
# §2.2 — a Bucket B instrument enters the reform-cost identity, built as shipped
# --------------------------------------------------------------------------- #
def test_a_built_instrument_enters_the_double_entry_identity(anchors) -> None:
    """§2.2 requires it of EVERY aggregate instrument, so assert it on a built one.

    `test_agregats.py` proves the guard works on a hand-made instrument; this proves the
    instruments actually shipped reach it, with the delta the engine computed rather
    than a number written beside it.
    """
    from impots import guards

    built, _ = build_all(anchors)
    dmto = built["dmto"]
    delta = dmto.reprice(scale(1.10)).delta_eur
    assert delta > 0

    result = guards.sector_balance({}, reform_cost=-delta,
                                   aggregate_deltas={"dmto": delta})
    assert result["unexplained"] == pytest.approx(0.0, abs=1.0)
    assert result["aggregate"] == pytest.approx(delta)


def test_the_identity_breaks_when_a_built_instrument_moves_unreported(anchors) -> None:
    """The kill half: the instrument moves and the headline does not say so."""
    from impots import guards

    built, _ = build_all(anchors)
    delta = built["dmto"].reprice(scale(1.10)).delta_eur
    with pytest.raises(guards.SectorBalanceError):
        guards.sector_balance({}, reform_cost=0.0, aggregate_deltas={"dmto": delta})
