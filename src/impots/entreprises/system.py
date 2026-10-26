"""The firm tax-benefit system: singleton, reform cache, and the read-back guard.

Deliberately the same shape as `impots.engine.system`, because the lessons are the
same. Building the system is cheap here — there is no 3 000-variable legislation
tree to load — but the reform cache still earns its place: a reform is keyed on a
canonical dump of its spec, so the same reform priced twice is built once.

`verify_scales` is D-007 made portable. On the household side, the obvious way to
neutralise surplus barème brackets summed their rates and produced a 120 %
marginal rate with no error anywhere. Nothing here is barème-shaped *yet* — the
CVAE schedule will be — so the read-back exists before the thing it guards.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from openfisca_core.taxbenefitsystems import TaxBenefitSystem

from impots.entreprises.entities import Entreprise
from impots.entreprises.variables import VARIABLES

if TYPE_CHECKING:  # pragma: no cover - typing only
    from impots.entreprises.reforms import FirmReformSpec

PARAMETERS = Path(__file__).resolve().parent / "parameters"

_SYSTEM: TaxBenefitSystem | None = None


class FirmSystem(TaxBenefitSystem):
    """A sibling of openfisca-france on the same engine, with one entity."""

    def __init__(self) -> None:
        super().__init__([Entreprise])
        self.load_parameters(str(PARAMETERS))
        for variable in VARIABLES:
            self.add_variable(variable)


def baseline() -> TaxBenefitSystem:
    """Current law for firms. Built once per process."""
    global _SYSTEM
    if _SYSTEM is None:
        _SYSTEM = FirmSystem()
    return _SYSTEM


def normal_rate(year: int) -> float:
    """The law's IS normal rate for `year`."""
    return float(baseline().parameters(f"{year}-01-01").impot_societes.taux_normal)


def normal_rate_change_points(spec: Any, year: int) -> float | None:
    """The reform's IS normal rate minus the law's for `year`, in points: what C8 reads
    (D-221) and the IS's GDP index (D-246). None when the reform leaves the rate alone."""
    rate = getattr(spec, "is_taux_normal", None) if spec is not None else None
    if rate is None:
        return None
    return 100.0 * (rate - normal_rate(year))


def reform_key(spec: FirmReformSpec, year: int) -> str:
    """Canonical cache key. The year is part of it: the same knobs applied from a
    different date are a different system."""
    payload = spec.model_dump(exclude_none=True, mode="json")
    return json.dumps({"year": year, "spec": payload}, sort_keys=True, separators=(",", ":"))


@lru_cache(maxsize=32)
def reformed(key: str) -> Any:
    """The reformed system for a canonical key, memoised."""
    from impots.entreprises.reforms import FirmReformSpec, make_reform, verify_scales

    decoded = json.loads(key)
    spec = FirmReformSpec.model_validate(decoded["spec"])
    system = make_reform(spec, decoded["year"], key)(baseline())
    # Read the reformed parameters back before anyone computes with them. A tax
    # figure that is wrong but plausible is the worst failure this project can
    # produce, and it has produced one before (D-007).
    verify_scales(system, spec, decoded["year"])
    return system


def reformed_for(spec: FirmReformSpec, year: int) -> Any:
    return reformed(reform_key(spec, year))


def clear_cache() -> None:
    reformed.cache_clear()


def cache_info() -> Any:
    return reformed.cache_info()
