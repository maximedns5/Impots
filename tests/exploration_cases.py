"""Phase 10 — what the tests of `impots exploration` share (`test_recherche`,
`test_explorations_api`): a start constructed, a request over the décote's rate, and the
population pass stubbed one seam below the command, where `/predictif/simulate`'s tests
stub it too (`_price_first_year`).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from impots import service
from impots.api.schemas import ExplorationRequest
from impots.dette import reference
from impots.predictif import recherche
from impots.predictif.exploration import Priced
from macro_cases import synthetic_macro_store

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = {"name": "Croissance réelle 1 %, prix 2 %", "real": 0.01, "prices": 0.02}
HELD = {"name": "Taux implicite tenu à son niveau de 2025", "kind": "implicite_tenu"}
WAGES = {"wage": 0.03, "source": "3 % ronds, le rythme du PIB nominal du scénario"}
#: Three bundles: the décote's rate at 40, 45 and 50 %. It claims the two ETI rows.
DECOTE = [{"knob": "decote_taux", "low": 0.40, "high": 0.50, "step": 0.05}]
COMMIT = "0123456789abcdef0123456789abcdef01234567"


def exploration_request(**overrides) -> dict:
    payload = {"name": "decote", "titre": "La décote",
               "question": "Une décote plus généreuse baisse-t-elle la dette en 2030 ?",
               "bounds": DECOTE, "target": {"at_most_points": 0.0},
               "spending": {"rule": "gele_en_volume"}, "growth": GROWTH, "rate": HELD,
               "horizon": 5, "theta": {"common": 0.5}, "uprating": WAGES, "macro": True}
    payload.update(overrides)
    return payload


def households() -> dict:
    """What `band.compute` reads for C1: forty households whose marginal rate rises."""
    rng = np.random.default_rng(3)
    base = rng.uniform(10_000, 200_000, 40)
    emtr = rng.uniform(0.1, 0.45, 40)
    return {"taxable_base": base, "weights": np.full(40, 1_000.0), "emtr_baseline": emtr,
            "emtr_reform": emtr + 0.03, "emtr_ir_baseline": emtr,
            "emtr_ir_reform": emtr + 0.03, "top_decile": base > np.quantile(base, 0.9)}


def cost_of(reform, view: str) -> float:
    """A cut that costs 2 Md€ at 40 % and 1 Md€ more per point, 90 % of it when frozen."""
    rate = reform.model_dump(exclude_none=True)["decote_taux"]
    return (2e9 + 1e11 * (rate - 0.40)) * (1.0 if view == "vieillie" else 0.9)


def pass_stub(seen: list):
    """`_price_first_year`, stubbed: the cost above, the households when behaviour is
    asked for, the cost as an income-tax impulse when the loop is."""
    def stub(request, *, uprating, macro=False, view="vieillie"):
        seen.append((request.reform.model_dump(exclude_none=True), view))
        cost = cost_of(request.reform, view)
        return SimpleNamespace(cost=cost, view=view, note="", deciles=[],
                               inputs=households() if request.behavioural else None,
                               impulse={"impot_sur_le_revenu": cost} if macro else None,
                               uncovered={})
    return stub


def run_search(payload: dict, *, seen: list | None = None, max_bundles: int = 12) -> dict:
    """`recherche.run` with the request's own hypotheses and a pass that records."""
    seen = [] if seen is None else seen
    request = ExplorationRequest.model_validate(payload)
    stub = pass_stub(seen)

    def price(reform, view):
        first = stub(SimpleNamespace(reform=reform, behavioural=request.behavioural),
                     uprating=None, macro=request.macro, view=view)
        return Priced(cost=first.cost, inputs=first.inputs, impulse=first.impulse)

    return recherche.run(request, price=price,
                         hypotheses=service.predictif_hypotheses(request), start=START,
                         macro_store=synthetic_macro_store(), max_bundles=max_bundles)
