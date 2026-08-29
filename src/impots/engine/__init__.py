"""Phase 0 engine: a typed wrapper around openfisca-france.

This is the household-level face of the mechanical layer (L2). Phase 1 reuses it
verbatim over a population, so nothing in here may import FastAPI or assume a
single household is the only caller.

Public surface:
    compute(household, year, reform=None, tier="light", emtr=False) -> ComputeResult
"""

from impots.engine.compute import ComputeResult, compute, warm_up
from impots.engine.system import baseline, reformed, versions

# Note: this rebinds the package attribute `impots.engine.compute` from the
# submodule to the function. Reach for other names in that module via the full
# path (`from impots.engine.compute import EMTR_STEP`), not by attribute access.
__all__ = ["ComputeResult", "baseline", "compute", "reformed", "versions", "warm_up"]
