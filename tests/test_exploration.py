"""Phase 9 M6 §8 — the evaluator of the conditional debt (`predictif.exploration`, D-224).

The population passes are stubbed: what is held here is the evaluator's own logic — Δb_T
read off the chain at θ and in both views, the θ box's keys (the claimed rows, the
multiplier's θ when the loop applies), its corners labelled in order, the monotonicity
refusal — and its use by the explorer, end to end.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

from impots import explorer
from impots.behavioural import channels
from impots.behavioural.store import load as load_store
from impots.dette import reference, scenarios
from impots.dette.path import SHIPPED, DebtError
from impots.predictif import chaine, comportement, exploration
from impots.predictif.exploration import Priced
from impots.predictif.theta import MACRO_ROW, Theta, ThetaError
from macro_cases import synthetic_macro_store

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = scenarios.GrowthScenario("Croissance réelle 1 %, prix 2 %", 0.01, 0.02)
HELD = scenarios.RateScenario("Taux implicite tenu à son niveau de 2025", "implicite_tenu")
FROZEN = SHIPPED["gele_en_volume"]
HALF = Theta(common=0.5)


class Reform:
    def __init__(self, **knobs) -> None:
        self._knobs = knobs

    def model_dump(self, exclude_none: bool = True, **_) -> dict:
        return dict(self._knobs)


def _households() -> dict:
    """Forty households whose marginal rate rises: C1 opens for an income-tax reform."""
    rng = np.random.default_rng(3)
    base = rng.uniform(10_000, 200_000, 40)
    emtr = rng.uniform(0.1, 0.45, 40)
    return {"taxable_base": base, "weights": np.full(40, 1_000.0), "emtr_baseline": emtr,
            "emtr_reform": emtr + 0.03, "top_decile": base > np.quantile(base, 0.9)}


def _ir(knobs):
    return Reform(ir_bareme=[{"threshold": 0, "rate": knobs["ir"]}])


def _price(*, behaviour: bool = False, impulse: bool = False, frozen_share: float = 0.9,
           seen: list | None = None):
    """A tax rise yielding 5 Md€ per point of the knob in the aged view, `frozen_share` of
    it in the frozen one; the impulse is the yield as a contraction."""
    def price(knobs, view):
        if seen is not None:
            seen.append((dict(knobs), view))
        yield_eur = 5e9 * knobs["ir"] * 100 * (1.0 if view == "vieillie" else frozen_share)
        return Priced(cost=-yield_eur, inputs=_households() if behaviour else None,
                      impulse={"impot_sur_le_revenu": -yield_eur} if impulse else None)
    return price


def _evaluator(horizon: int = 4, **kwargs):
    options = {"price": _price(), "reform_of": _ir, "start": START, "horizon": horizon,
               "spending": FROZEN, "growth": GROWTH, "rate": HELD, "theta": HALF}
    options.update(kwargs)
    return exploration.conditional_debt(**options)


def test_a_mechanical_bundle_reads_the_chains_own_difference() -> None:
    """D-042: against an independent construction. Without behaviour or loop, Δb_T is the
    chain's difference at the last year, the frozen view on its own pass, and the box has
    one corner — θ as asked, which nothing moves."""
    seen: list = []
    evaluation = _evaluator(price=_price(seen=seen))({"ir": 0.01})
    direct = chaine.run(START, horizon=4, costs=chaine.ReformCosts(
        by_year={2026: -5e9}, carry=chaine.CARRY), spending=FROZEN, growth=GROWTH,
        rate=HELD, theta=HALF)
    assert evaluation.aged_eur == pytest.approx(direct.delta[-1])
    assert evaluation.frozen_eur == pytest.approx(0.9 * direct.delta[-1])
    assert [view for _, view in seen] == ["vieillie", "figee"]
    assert evaluation.corners == ((exploration.NO_KEY, evaluation.aged_eur),)
    assert evaluation.band is None and evaluation.band_reason == exploration.NO_BAND
    second = _evaluator(year=2027)({"ir": 0.01})
    assert second.aged_eur == pytest.approx(direct.delta[1])


def test_behaviour_puts_the_claimed_rows_in_the_box() -> None:
    """The income-tax knob claims both C1 rows: four corners, in the box's own order,
    labelled, and the value at θ = ½ inside them."""
    evaluation = _evaluator(price=_price(behaviour=True))({"ir": 0.01})
    labels = [label for label, _ in evaluation.corners]
    assert labels == ["eti_all = 0, eti_top_decile = 0", "eti_all = 0, eti_top_decile = 1",
                      "eti_all = 1, eti_top_decile = 0", "eti_all = 1, eti_top_decile = 1"]
    values = [v for _, v in evaluation.corners]
    assert min(values) <= evaluation.aged_eur <= max(values)
    assert min(values) < max(values)


def test_the_loop_adds_the_multipliers_theta_only_where_it_applies() -> None:
    """Under « gele_en_volume » the impulse runs the loop, and the multiplier's θ joins
    the box; under a GDP-share rule the loop is absent, and so is its θ."""
    store = synthetic_macro_store()
    looped = _evaluator(horizon=4, price=_price(impulse=True), persistence="tenu",
                        macro_store=store)({"ir": 0.01})
    assert [label for label, _ in looped.corners] == [f"{MACRO_ROW} = 0",
                                                      f"{MACRO_ROW} = 1"]
    assert looped.corners[0][1] != looped.corners[1][1]
    unlooped = _evaluator(horizon=4, price=_price(impulse=True),
                          spending=SHIPPED["part_pib_constante"],
                          macro_store=store)({"ir": 0.01})
    assert [label for label, _ in unlooped.corners] == [exploration.NO_KEY]


def test_the_boxs_diagonal_corners_are_the_debt_at_theta_zero_and_one() -> None:
    """D-274. The corner where every key of the box is at 0 is Δb_T at θ = 0, and the one
    where every key is at 1 is Δb_T at θ = 1: the box moves every θ the aged view reads.
    The study reads the debt at θ = 0 and θ = 1 off the committed corners on this."""
    options = {"price": _price(behaviour=True, impulse=True), "persistence": "tenu",
               "macro_store": synthetic_macro_store()}
    corners = _evaluator(**options)({"ir": 0.01}).corners
    at = {}
    for value in (0, 1):
        at[value] = _evaluator(theta=Theta(common=float(value)), **options)({"ir": 0.01})
        [diagonal] = [v for label, v in corners
                      if all(part.endswith(f" = {value}") for part in label.split(", "))]
        assert at[value].aged_eur == pytest.approx(diagonal, rel=1e-12)
    assert at[0].aged_eur != at[1].aged_eur
    mechanical = _evaluator()({"ir": 0.01})
    for value in (0, 1):
        assert _evaluator(theta=Theta(common=float(value)))({"ir": 0.01}).aged_eur == (
            pytest.approx(dict(mechanical.corners)[exploration.NO_KEY], rel=1e-12))


def test_every_row_a_channel_reads_answers_to_the_same_knobs() -> None:
    """D-274, on the shipped store. A channel opens when one of its rows claims a knob of
    the reform, and reads them all; the box moves the claimed rows only. Two rows of one
    channel answering to different knobs would leave one at the base θ in every corner,
    and the diagonal corners would no longer be Δb at θ = 0 and θ = 1."""
    store = load_store()
    names = sorted(n for n in dir(channels) if re.fullmatch(r"C\d+_KEYS", n))
    assert len(names) >= 11
    for name in names:
        knobs = {frozenset(store[key].responds_to_knobs) for key in getattr(channels, name)
                 if key in store and store[key].is_open}
        assert len(knobs) == 1, (name, knobs)


def test_a_non_monotone_effect_is_refused_rather_than_read_at_its_corners(
        monkeypatch) -> None:
    """GUARD. The corners bound the box only if each effect is monotone in its θ: Δb_T at
    θ outside the corners' range says one is not, and the bundle is refused."""
    def bump(theta, *, store, mechanical, reform, **inputs):
        at_half = theta.for_row("eti_all") == 0.5
        return (mechanical + (3e9 if at_half else 0.0)), "in-support"

    monkeypatch.setattr(comportement, "receipts_at", bump)
    with pytest.raises(ThetaError, match="monotone"):
        _evaluator(price=_price(behaviour=True))({"ir": 0.01})


def test_a_target_year_outside_the_horizon_is_refused() -> None:
    with pytest.raises(DebtError, match="hors de l'horizon"):
        _evaluator(horizon=4, year=2031)


def test_the_explorer_classes_bundles_by_their_theta_box_end_to_end() -> None:
    """End to end: a grid of income-tax rises against a debt target at the horizon. The
    explorer returns those that meet it at θ = ½, each « robuste » or « dépend de θ » by
    its four corners, and the journal carries the θ."""
    evaluate = _evaluator(price=_price(behaviour=True))
    values = {f: evaluate({"ir": f}) for f in (0.004, 0.006, 0.008)}
    target = values[0.006].aged_eur
    candidates, log = explorer.search(
        target_eur=target, bounds=[explorer.Bound("ir", 0.004, 0.008, 0.002)],
        evaluate=evaluate, quantity=explorer.CONDITIONAL, theta=HALF)
    assert sorted(c.knobs["ir"] for c in candidates) == [0.006, 0.008]
    by_knob = {c.knobs["ir"]: c for c in candidates}
    assert by_knob[0.006].robust is False and "dépend de θ" in by_knob[0.006].theta_reason
    assert by_knob[0.008].robust is True
    assert log.payload()["theta"] == {"rows": [], "common": 0.5}
