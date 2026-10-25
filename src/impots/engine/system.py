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
    """The current-law tax-benefit system, as WE read the law. Built once (~3 s).

    Not raw openfisca: `patrimoine.corrections` is applied on top, carrying two
    documented departures on the IFI (D-079) — the missing liability threshold, which
    makes openfisca's IFI non-monotonic, and the 5 % forfait mobilier, which is
    contested and labelled so. Each correction ships with a legal citation, a measured
    demonstration and a kill test that fails the day openfisca changes its mind.

    They are applied HERE rather than in the wealth module so there is one IFI figure in
    this codebase rather than a corrected one inside `patrimoine` and a raw one on the
    wire. Both bite only on a foyer declaring real-estate wealth, and nothing else in
    this project declares any, so the blast radius is nil — which the full suite proves
    rather than this docstring asserting.

    `engine.corrections` then carries the benefit-side ones, under the same rules: the
    housing aid's minimum professional-expenses deduction kept within the gross salaries
    it is taken from (D-180), and the majoration pour la vie autonome kept to an AAH at
    its full rate or beside a pension (D-184). Since D-188 it also doubles the abatement
    of art. 157 bis for a couple whose two spouses qualify, in the income tax and in the
    benefits' resources; the population has such couples, over 65. Since D-192 it taxes
    the ASS as a salary, which openfisca leaves out of the income tax; the population
    declares no one in « fin de droits ».
    """
    global _TBS
    if _TBS is None:
        from impots.engine.corrections import apply_to as apply_benefit_corrections
        from impots.patrimoine.corrections import apply_to

        _TBS = apply_benefit_corrections(apply_to(FranceTaxBenefitSystem()))
    return _TBS


def uncorrected_baseline() -> FranceTaxBenefitSystem:
    """Raw openfisca, with none of our corrections. For kill tests and comparisons only.

    Kept as a named function so that any code wanting the reference implementation says
    so out loud, and so the kill tests have something honest to compare against.
    """
    return FranceTaxBenefitSystem()


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
    from impots.engine.reforms import (
        make_reform,
        verify_allegements,
        verify_bareme,
        verify_capital,
    )

    decoded = json.loads(key)
    spec = ReformSpec.model_validate(decoded["spec"])
    reform_class = make_reform(spec, decoded["year"], key)
    system = reform_class(baseline())
    # Read the reformed scale back before anyone computes with it: a barème that
    # silently differs from the one requested is the most dangerous failure mode
    # this wrapper has.
    verify_bareme(system, spec, decoded["year"])
    verify_allegements(system, spec, decoded["year"])
    verify_capital(system, spec, decoded["year"])
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
