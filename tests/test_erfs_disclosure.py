"""ERFS — the disclosure guard, and the two ways it must be able to refuse."""

from __future__ import annotations

import pytest

from impots.erfs import disclosure as d


def test_the_floor_has_no_default_and_must_be_stated() -> None:
    """The convention states NO number, so any number is somebody's choice. Forcing the
    caller to pass it keeps it a choice rather than a constant nobody re-examines."""
    import inspect

    assert inspect.signature(d.check).parameters["floor"].default is inspect.Parameter.empty


def test_a_thin_cell_refuses_the_WHOLE_table() -> None:
    """Dropping one cell from a table whose margins are published lets the dropped value be
    recovered by subtraction. Suppression that arithmetic can undo is not suppression."""
    cells = [d.Cell("Q1", 400), d.Cell("Q2", 7), d.Cell("Q3", 900)]
    with pytest.raises(d.DisclosureRefused, match="Le tableau ENTIER est refusé"):
        d.check(cells, floor=50)


def test_a_table_above_the_floor_passes() -> None:
    """The kill for the refusal above: a guard that refused everything would satisfy the
    previous test and protect nothing."""
    d.check([d.Cell("Q1", 163), d.Cell("Q2", 400)], floor=50)


def test_a_floor_below_one_is_itself_refused() -> None:
    """A floor of 0 forbids nothing while reading, to anyone downstream, as a guarantee."""
    with pytest.raises(d.DisclosureRefused, match="n'interdit rien"):
        d.check([d.Cell("x", 5)], floor=0)


def test_the_E2_tables_would_have_passed_a_floor_far_above_the_fallback() -> None:
    """The argument that makes the missing number unimportant: the thinnest cell actually
    published by E2 held 163 unweighted households, so 11, 50 and 100 all change nothing."""
    published = [d.Cell("Q4 Autre", 163), d.Cell("Q4 Monoparentale", 406)]
    for floor in (11, 50, 100):
        d.check(published, floor=floor)
    assert d.minimum(published) == 163


def test_the_convention_is_named_and_states_no_threshold() -> None:
    """The reference is recorded so a compliance rule can be checked by someone else. And
    the module says plainly that no number was quoted, because pretending one exists would
    be worse than admitting none does."""
    assert "38715" in d.CONVENTION
    assert "aucun seuil chiffré" in d.check.__doc__ or "aucun seuil chiffré" in (
        d.__doc__ or "") or "states no number" in (d.__doc__ or "").lower()
