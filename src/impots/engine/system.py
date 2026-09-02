"""TBS singleton and reform cache (spec §3.1).

Constructing a FranceTaxBenefitSystem costs ~3 s and applying a Reform ~0.5 s, so
both are done once and kept: the baseline is a module-level singleton, reformed
systems are memoised on a canonical hash of the ReformSpec.

Never hand the mutable parameter tree of `baseline()` to anything. `Reform(tbs)`
clones the tree, which is why the baseline survives a reform — `test_no_mutation`
keeps us honest about that.
"""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.metadata import version
from typing import TYPE_CHECKING, Any

from openfisca_france import FranceTaxBenefitSystem

if TYPE_CHECKING:  # pragma: no cover - typing only
    from impots.api.schemas import ReformSpec

_TBS: FranceTaxBenefitSystem | None = None


def baseline() -> FranceTaxBenefitSystem:
    """The current-law tax-benefit system. Built once per process (~3 s)."""
    global _TBS
    if _TBS is None:
        _TBS = FranceTaxBenefitSystem()
    return _TBS


def reform_key(spec: ReformSpec, year: int) -> str:
    """Canonical cache key for a reform.

    The year is part of the key because every parameter update starts at
    `{year}-01-01`: the same knobs applied to a different year are a different
    reformed system.
    """
    payload = spec.model_dump(exclude_none=True, mode="json")
    return json.dumps({"year": year, "spec": payload}, sort_keys=True, separators=(",", ":"))


@lru_cache(maxsize=32)
def reformed(key: str) -> Any:
    """The reformed tax-benefit system for a canonical `reform_key`.

    Memoised: two identical ReformSpecs return the *same object* (spec §6,
    `test_reform_cache`). Imports are deferred to keep the module import graph
    acyclic — `reforms` needs the pydantic wire models, which live in the API layer.
    """
    from impots.api.schemas import ReformSpec
    from impots.engine.reforms import make_reform, verify_allegements, verify_bareme

    decoded = json.loads(key)
    spec = ReformSpec.model_validate(decoded["spec"])
    reform_class = make_reform(spec, decoded["year"], key)
    system = reform_class(baseline())
    # Read the reformed scale back before anyone computes with it: a barème that
    # silently differs from the one requested is the most dangerous failure mode
    # this wrapper has.
    verify_bareme(system, spec, decoded["year"])
    verify_allegements(system, spec, decoded["year"])
    return system


def reformed_for(spec: ReformSpec, year: int) -> Any:
    """Convenience wrapper: cache-aware reformed system for a spec."""
    return reformed(reform_key(spec, year))


def cache_info() -> Any:
    """lru_cache statistics for the reform cache (used by tests and /health)."""
    return reformed.cache_info()


def clear_cache() -> None:
    """Drop every memoised reformed system. Tests use this; the API does not."""
    reformed.cache_clear()


def versions() -> dict[str, str]:
    """Installed engine versions — echoed in every API response (spec §4)."""
    return {
        "openfisca_france": version("openfisca-france"),
        "openfisca_core": version("openfisca-core"),
    }
