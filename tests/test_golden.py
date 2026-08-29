"""Golden cases (spec §6).

Every value in `tests/golden/*.yaml` was produced by openfisca-france 176.0.8 and
pins *this wrapper against that engine version*. They are regression anchors, not
claims about French tax law. A dependency bump that moves one of them is a finding
for `docs/DECISIONS.md`, not a number to quietly rewrite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from impots.api.schemas import HouseholdInput, ReformSpec
from impots.engine import compute

GOLDEN_DIR = Path(__file__).parent / "golden"
CASES = sorted(GOLDEN_DIR.glob("*.yaml"))

#: Money is checked to ±2 €; counts and rates need to be much tighter, since a
#: half-part or a percentage point is a large error dressed as a small number.
COUNT_TOLERANCE = 0.001
EMTR_TOLERANCE = 0.001


def _load(path: Path) -> dict[str, Any]:
    case = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert case["name"] == path.stem, f"{path.name}: name must match the filename stem"
    return case


def _check(rows: dict[str, Any] | None, expected: dict[str, Any], tolerance: float,
           column: str, case_name: str) -> None:
    assert rows is not None, f"{case_name}: no {column} column was computed"
    for key, want in expected.items():
        assert key in rows, (
            f"{case_name}/{column}: {key!r} is not a registry key — "
            f"available: {sorted(k for k in rows if k != 'raw')}"
        )
        got = rows[key]
        assert got is not None, (
            f"{case_name}/{column}: {key!r} was not computed — is the case's tier too low?"
        )
        tol = COUNT_TOLERANCE if key == "parts_fiscales" else tolerance
        assert abs(got - want) <= tol, (
            f"{case_name}/{column}: {key} = {got}, expected {want} (±{tol})"
        )


@pytest.mark.parametrize("path", CASES, ids=[p.stem for p in CASES])
def test_golden_case(path: Path) -> None:
    case = _load(path)
    household = HouseholdInput.model_validate(case["household"])
    reform = ReformSpec.model_validate(case["reform"]) if case.get("reform") else None
    wants_emtr = "expected_emtr" in case

    result = compute(
        household,
        case["year"],
        reform=reform,
        tier=case["tier"],
        emtr=wants_emtr,
    )

    tolerance = float(case.get("tolerance", 2.0))
    _check(result.baseline, case["expected"], tolerance, "baseline", case["name"])
    if "expected_reform" in case:
        _check(result.reform, case["expected_reform"], tolerance, "reform", case["name"])
    if "expected_delta" in case:
        _check(result.delta, case["expected_delta"], tolerance, "delta", case["name"])
    if wants_emtr:
        assert result.emtr is not None
        assert abs(result.emtr - case["expected_emtr"]) <= EMTR_TOLERANCE, (
            f"{case['name']}: emtr = {result.emtr}, expected {case['expected_emtr']}"
        )


def test_every_golden_case_is_loaded() -> None:
    """Guard against a case file that silently stops being collected."""
    assert {p.stem for p in CASES} == {
        "single_30k",
        "couple_70k_2kids",
        "smic_single",
        "single_240k",
        "single_240k_toprate50",
    }
