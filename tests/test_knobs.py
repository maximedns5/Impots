"""Every reform knob, run on a household, watched moving.

`test_standing_rules.py` asserts that the registry covers every knob. This runs it. The
two together are the guard: a complete registry nobody executes proves nothing, and an
executed registry with holes in it proves nothing about the holes.

Four parameters in this project have resolved non-null, accepted a write, and moved
nothing — a silently created child (D-044), a derived plafond the formula recomputes
(D-062), a duplicate tree for the same article (D-064), and a rate superseded by a
literal in the formula. Every one would have passed a read-back. This is the test that
would have caught all four.
"""

from __future__ import annotations

import pytest

from impots.api.schemas import HouseholdInput, ReformSpec
from impots.engine import compute
from impots.engine.reforms import SCALAR_KNOBS
from knob_cases import CASES, EXEMPT

pytestmark = pytest.mark.slow


def _rows(household: dict, niches: dict | None, reform: ReformSpec | None):
    payload = dict(household)
    if niches is not None:
        payload["niches"] = niches
    result = compute(HouseholdInput.model_validate(payload), 2024,
                     reform=reform, tier="full")
    return result.reform if reform is not None else result.baseline


@pytest.mark.parametrize("knob", sorted(CASES))
def test_each_knob_moves_its_output(knob: str):
    household, niches, output, value, sign = CASES[knob]
    before = _rows(household, niches, None)[output]
    after = _rows(household, niches, ReformSpec(**{knob: value}))[output]
    moved = after - before
    assert abs(moved) > 0.5, (
        f"{knob} moved nothing: {output} stayed at {before}. Either the household does "
        f"not exercise it, or the parameter is one the formula never reads."
    )
    assert moved * sign > 0, (
        f"{knob} moved the wrong way: {output} went {before} -> {after}, expected "
        f"{'up' if sign > 0 else 'down'}"
    )


@pytest.mark.parametrize("knob", sorted(CASES))
def test_each_knob_leaves_the_baseline_alone(knob: str):
    """`Reform(tbs)` clones the tree; this is the standing proof per knob."""
    household, niches, output, value, _ = CASES[knob]
    before = _rows(household, niches, None)[output]
    _rows(household, niches, ReformSpec(**{knob: value}))
    assert _rows(household, niches, None)[output] == pytest.approx(before)


@pytest.mark.parametrize("knob", sorted(EXEMPT))
def test_each_exempt_knob_really_cannot_be_moved(knob: str):
    """The exemption has to be true, not merely claimed.

    `allegement_general_taux_50_et_plus` governs employers of fifty or more, and
    `HouseholdInput` cannot express one — the engine reads every foyer as a small
    employer. If that ever changes this test fails, which is the correct moment to
    turn the exemption into a case.
    """
    if knob != "allegement_general_taux_50_et_plus":
        pytest.skip(f"no negative check written for {knob}")
    smic = {"adults": [{"salaire_brut_annuel": 22_000, "annee_naissance": 1990}]}
    before = _rows(smic, None, None)["allegement_general"]
    after = _rows(smic, None, ReformSpec(**{knob: 0.40}))["allegement_general"]
    assert after == pytest.approx(before), (
        "the ≥50-employee rate now moves a household — the wire format must have "
        "gained an effectif, so replace the exemption with a real case"
    )


def test_the_registry_and_the_knob_list_agree():
    """`PLAFOND_KNOBS` autant que `SCALAR_KNOBS`, depuis D-151 — et cette copie-ci a été
    oubliée au premier passage, ce qui est la remarque de D-151 retournée contre elle.

    Deux tests portent le même contrat : celui-ci et
    `test_standing_rules.py::test_every_knob_either_moves_an_outcome_or_says_why_not`.
    Élargir le second sans le premier a fait tomber celui-ci en CI — parce que ce module
    porte `pytestmark = pytest.mark.slow` et que la porte locale (`-m 'not slow'`) ne le
    voit pas. Deux registres d'un seul contrat, dont un invisible à la porte : c'est
    exactement la forme décrite par D-151, rencontrée en la corrigeant.
    """
    from impots.engine.reforms import PLAFOND_KNOBS

    assert set(CASES) | set(EXEMPT) == set(SCALAR_KNOBS) | set(PLAFOND_KNOBS)


def test_the_allegement_rows_exist_because_the_gross_row_hides_them():
    """`cotisations_employeur` is GROSS of the allègements.

    Three employer knobs were briefly read as dead because they were watched on that
    row, which does not move. The reductions land in `salaire_super_brut`; the three
    dedicated rows are what make them visible.
    """
    smic = {"adults": [{"salaire_brut_annuel": 22_000, "annee_naissance": 1990}]}
    before = _rows(smic, None, None)
    after = _rows(smic, None, ReformSpec(allegement_general_plafond=1.8))
    assert after["cotisations_employeur"] == pytest.approx(
        before["cotisations_employeur"]), "the gross row should not move"
    assert after["allegement_general"] > before["allegement_general"]
    assert after["salaire_super_brut"] < before["salaire_super_brut"]
