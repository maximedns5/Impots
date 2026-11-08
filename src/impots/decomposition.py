"""One correction of but 16 switched off, to weigh it (D-354).

The series of D-352 ran E1 (the public sector, D-346) and E2 (the CVAE and the C3S
deducted from the IS base, D-347) together; a study touched by both cannot say what each
weighs. `IMPOTS_SANS=E1` or `IMPOTS_SANS=E2` reruns its passes without one of them, and
`scripts/decomposition.py` writes those passes apart from the study's reports. Unset, it
changes nothing: the studies, the grid and the API run with every correction."""

from __future__ import annotations

import os

CORRECTIONS = ("E1", "E2")
VARIABLE = "IMPOTS_SANS"


class DecompositionError(ValueError):
    pass


def sans(correction: str) -> bool:
    """Whether the run leaves `correction` out; an unknown value is refused, not read as
    every correction on."""
    if correction not in CORRECTIONS:
        raise DecompositionError(f"{correction} : pas une correction du but 16 {CORRECTIONS}")
    value = os.environ.get(VARIABLE, "")
    if value and value not in CORRECTIONS:
        raise DecompositionError(f"{VARIABLE}={value} : attendu l'une de {CORRECTIONS}")
    return value == correction
