"""C11, the self-financing of a targeted cut of employer contributions, reconciled (D-270).

The channel is D-263's: s = (1 − p) × s_C2 + p × s_TE, its three rows in
`self_financing.yaml`. What D-256 brings to it: C2's jobs valued at what a full-time SMIC
job brings the public finances in the reform's year, measured on the engine, rather than
at the Trésor-Éco's 12 000 € of 2009; and the API's refusals on a targeted cut all the
same. Worked examples are derived by hand in the docstrings; an implementation agreeing
with itself proves nothing.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest

from impots.behavioural import band as band_module
from impots.behavioural import channels
from impots.behavioural.store import Parameter, Source, Store, Support, Verifier
from impots.predictif import comportement
from impots.predictif.theta import Theta

EMPLOYER_KNOBS = ("allegement_general_*", "bandeau_maladie_*", "bandeau_famille_*")


class FakeReform:
    """Stands in for a ReformSpec: the channels only ask what knobs it sets."""

    def __init__(self, **knobs: object) -> None:
        self._knobs = knobs

    def model_dump(self, exclude_none: bool = True, **_: object) -> dict[str, object]:
        return dict(self._knobs)

    def is_empty(self) -> bool:
        return not self._knobs


CUT = FakeReform(allegement_general_t_delta_moins_de_50=0.3831)


def _row(key: str, central: float, low: float, high: float) -> Parameter:
    row = Parameter(
        key=key, central=central, low=low, high=high, applies_to="test",
        support=Support(estimated_on="test", max_variation_graded_in_support=None),
        source=Source(citation="test"), verifier=Verifier(verdict="CONFIRMED"),
        responds_to_knobs=EMPLOYER_KNOBS)
    if low != high:
        row = dataclasses.replace(row, theta_one="high", theta_reason="test")
    return row


def c11_store(weight: float | None = None, *, with_c2: bool = False) -> Store:
    """C11's three rows, the weight open unless pinned to `weight`; C2's on demand."""
    rows = {
        channels.C11_RETURN: _row(channels.C11_RETURN, 12_000.0, 12_000.0, 12_000.0),
        channels.C11_COST: _row(channels.C11_COST, 20_000.0, 20_000.0, 20_000.0),
        channels.C11_WEIGHT: (_row(channels.C11_WEIGHT, 0.5, 0.0, 1.0) if weight is None
                              else _row(channels.C11_WEIGHT, weight, weight, weight)),
    }
    if with_c2:
        rows.update({
            "employment_elasticity_smic": _row(
                "employment_elasticity_smic", -0.43, -0.43, -0.43),
            "employment_elasticity_at_fadeout": _row(
                "employment_elasticity_at_fadeout", -0.1, -0.1, -0.1),
            "employment_fadeout_smic_multiple": _row(
                "employment_fadeout_smic_multiple", 2.0, 2.0, 2.0),
        })
    return Store(parameters=rows)


def _c11(weight: float, **overrides: object) -> channels.ChannelResult:
    arguments = {"jobs": np.array([10_000.0]), "contribution_delta": -1e9,
                 "targets_low_wages": True, "value_per_job": 10_032.0,
                 "rng": np.random.default_rng(0)}
    arguments.update(overrides)
    return channels.targeted_self_financing(c11_store(weight), CUT, **arguments)


# --------------------------------------------------------------------------- #
# C2's jobs at what a job brings, the Trésor-Éco's share untouched
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("weight", "receipts"), [
    (0.0, 0.10032e9), (0.5, 0.35016e9), (1.0, 0.60e9)])
def test_c2_s_jobs_are_valued_at_what_a_job_brings(weight: float, receipts: float) -> None:
    """A 1 bn cut that C2 reads as 10 000 jobs, each bringing 10 032 €: s_C2 = 10 000 ×
    10 032 / 10⁹ = 10,032 %, not the 12 % the Trésor-Éco's 12 000 € would give. The
    Trésor-Éco's share stays its own, 12 000 / 20 000 = 60 %. At p = ½, s = 0,5 × 10,032 %
    + 0,5 × 60 % = 35,016 %."""
    result = _c11(weight)
    assert result.applies and result.in_revenue_band
    assert result.central == pytest.approx(receipts, rel=1e-12)
    assert result.diagnostics["share_c2"] == pytest.approx(0.10032)
    assert result.diagnostics["share_tresor_eco"] == pytest.approx(0.60)
    assert result.diagnostics["return_per_job_eur"] == 10_032.0


def test_the_guard_reads_c2_at_what_a_job_brings() -> None:
    """55 000 jobs for 1 bn: 66 % at the Trésor-Éco's 12 000 €, above its 60 %; 55,2 % at
    10 032 €, below. The guard is on C2's reading as the channel makes it."""
    assert _c11(0.5, jobs=np.array([55_000.0])).applies
    with pytest.raises(channels.SelfFinancingOutOfRange, match="66"):
        _c11(0.5, jobs=np.array([55_000.0]), value_per_job=12_000.0)


def test_without_what_a_job_brings_it_says_it_was_not_computed() -> None:
    result = _c11(0.5, value_per_job=None)
    assert not result.applies and result.draws is None
    assert result.message.startswith("Non calculé") and "SMIC" in result.message


@pytest.mark.parametrize("value", [0.0, -1.0])
def test_a_job_that_brings_nothing_is_refused(value: float) -> None:
    with pytest.raises(channels.ChannelInputMissing, match="SMIC job"):
        _c11(0.5, value_per_job=value)


def test_a_refusal_shuts_a_targeted_cut() -> None:
    result = _c11(0.5, refused="la boucle porte ces emplois")
    assert not result.applies and result.draws is None
    assert result.message == "la boucle porte ces emplois"


def test_an_untargeted_cut_says_so_before_any_refusal() -> None:
    """Under the uniform variant the loop carries the return (D-263): that is the reason,
    whatever else the caller found."""
    result = _c11(0.5, targets_low_wages=False, refused="autre chose")
    assert result.message == channels.NOT_TARGETED


# --------------------------------------------------------------------------- #
# in the band, and at θ
# --------------------------------------------------------------------------- #
C2_INPUTS = {"smic_multiple": np.array([1.0]), "relative_cost_change": np.array([-0.01]),
             "earner_weights": np.array([1e6]), "contribution_delta": -1e9,
             "targets_low_wages": True}


def test_the_band_hands_c11_what_a_job_brings() -> None:
    """One cell at the SMIC, 10⁶ weighted, whose labour cost falls 1 %: C2 counts
    0,43 × 10⁶ × 0,01 = 4 300 jobs, worth 4 300 × 10 032 / 10⁹ = 4,31376 % of the cut. At
    p = ½, s = 32,15688 %."""
    result = band_module.compute(
        mechanical=-1e9, reform=CUT, store=c11_store(0.5, with_c2=True), draws=1,
        self_financing_value_per_job=10_032.0, **C2_INPUTS)
    channel = next(c for c in result.channels if c["key"] == "c11_autofinancement")
    assert channel["central"] == pytest.approx(0.3215688e9, rel=1e-12)


def test_the_refusal_reaches_the_band() -> None:
    result = band_module.compute(
        mechanical=-1e9, reform=CUT, store=c11_store(0.5, with_c2=True), draws=1,
        self_financing_value_per_job=10_032.0, self_financing_refused="non lue",
        **C2_INPUTS)
    channel = next(c for c in result.channels if c["key"] == "c11_autofinancement")
    assert not channel["applies"] and channel["message"] == "non lue"


def test_the_theta_box_runs_from_c2_at_what_a_job_brings_to_the_tresor_eco() -> None:
    """The same cell: from 4,31376 % at p = 0 to 60 % at p = 1, 32,15688 % at θ = ½."""
    at = comportement.evaluate(
        Theta(rows={}, common=0.5), mechanical=-1e9, reform=CUT,
        store=c11_store(with_c2=True), self_financing_value_per_job=10_032.0, **C2_INPUTS)
    assert at.receipts == pytest.approx(-1e9 + 0.3215688e9, rel=1e-9)
    assert at.box == pytest.approx((-1e9 + 0.0431376e9, -1e9 + 0.60e9), rel=1e-9)


# --------------------------------------------------------------------------- #
# the API's inputs (D-256)
# --------------------------------------------------------------------------- #
def _request(year: int, **knobs: object) -> SimpleNamespace:
    return SimpleNamespace(year=year, reform=FakeReform(**knobs))


@pytest.fixture
def a_job_brings(monkeypatch):
    from impots.behavioural import autofinancement

    monkeypatch.setattr(autofinancement, "job_value", lambda year: 10_032.0)


def _macro_with(monkeypatch, tables: dict) -> None:
    from impots.macro import store as macro_store

    monkeypatch.setattr(macro_store, "load", lambda: macro_store.Store(tables=tables))


@pytest.fixture
def no_targeted_balance_row(monkeypatch):
    """Mésange's balance rows as the store has them: none for the targeted variant."""
    from impots.predictif.retroaction import BALANCE_TABLE

    _macro_with(monkeypatch, {BALANCE_TABLE: SimpleNamespace(
        values={"impot_sur_le_revenu": {}, "cotisations_employeurs": {}})})


def test_a_curve_cut_gets_what_a_job_brings(a_job_brings, no_targeted_balance_row) -> None:
    from impots.api import main

    inputs = main._self_financing_inputs(
        _request(2026, allegement_general_t_delta_moins_de_50=0.3831))
    assert inputs == {"self_financing_value_per_job": 10_032.0}


def test_a_cut_the_shocks_do_not_target_gets_nothing(a_job_brings,
                                                     no_targeted_balance_row) -> None:
    """D-239: from 2026 the plafond relieves the wages above 3 SMIC, under the uniform
    variant; C11 says so itself (`NOT_TARGETED`). Before 2026 it was targeted."""
    from impots.api import main

    assert main._self_financing_inputs(_request(2026, allegement_general_plafond=3.5)) == {}
    assert main._self_financing_inputs(_request(2026, ir_bareme=1.0)) == {}
    assert main._self_financing_inputs(_request(2025, allegement_general_plafond=1.7)) == {
        "self_financing_value_per_job": 10_032.0}


def test_a_targeted_cut_mixed_with_the_plafond_is_refused(a_job_brings,
                                                          no_targeted_balance_row) -> None:
    """The shocks route the whole employer delta to the targeted variant as soon as one
    knob is targeted, but the delta is one total: no share of it can be said to be the
    curve's, and the plafond's is not the Trésor-Éco's."""
    from impots.api import main

    inputs = main._self_financing_inputs(_request(
        2026, allegement_general_t_min=0.021, allegement_general_plafond=3.5))
    assert "`allegement_general_plafond`" in inputs["self_financing_refused"]
    assert "2026" in inputs["self_financing_refused"]


def test_a_balance_row_for_the_targeted_variant_shuts_c11(a_job_brings, monkeypatch) -> None:
    """Were Mésange's targeted variant to gain a balance row, the loop would count the
    same jobs: C11 is refused, not added."""
    from impots.api import main
    from impots.predictif.retroaction import BALANCE_TABLE

    _macro_with(monkeypatch, {BALANCE_TABLE: SimpleNamespace(
        values={"cotisations_employeurs_ciblees": {}, "impot_sur_le_revenu": {}})})
    inputs = main._self_financing_inputs(_request(2026, allegement_general_t_min=0.021))
    assert inputs == {"self_financing_refused": main.LOOP_AND_C11}


def test_an_unread_balance_table_shuts_c11(a_job_brings, monkeypatch) -> None:
    from impots.api import main
    from impots.macro import store as macro_store

    def unreadable():
        raise macro_store.MissingSourceTable("le classeur de Mésange")

    monkeypatch.setattr(macro_store, "load", unreadable)
    inputs = main._self_financing_inputs(_request(2026, allegement_general_t_min=0.021))
    assert "le classeur de Mésange" in inputs["self_financing_refused"]
    _macro_with(monkeypatch, {})
    inputs = main._self_financing_inputs(_request(2026, allegement_general_t_min=0.021))
    assert "la table est absente" in inputs["self_financing_refused"]


def test_the_employer_inputs_carry_c11_s(a_job_brings, no_targeted_balance_row,
                                         monkeypatch) -> None:
    """Merged with C2's, so every caller of `_employer_inputs` hands them to the band."""
    import polars as pl

    from impots.api import main

    monkeypatch.setattr(main, "_smic_annual", lambda year: 20_000.0)
    persons = pl.DataFrame({"person_id": [1], "household_id": [1],
                            "salaire_brut_annuel": [20_000.0], "weight": [100.0],
                            "salaire_super_brut": [21_000.0],
                            "salaire_super_brut_reform": [20_900.0]})
    inputs = main._employer_inputs(
        _request(2026, allegement_general_t_min=0.021), SimpleNamespace(persons=persons),
        SimpleNamespace(employer_contribution_delta=-1e4))
    assert inputs["targets_low_wages"] is True
    assert inputs["self_financing_value_per_job"] == 10_032.0


# --------------------------------------------------------------------------- #
# what a job brings, measured (D-256)
# --------------------------------------------------------------------------- #
def test_what_a_smic_job_brings_in_2026_is_measured() -> None:
    """The note 5 case on the engine: a single person at a full-time SMIC against the RSA.
    22 239 € of cost, 12 207 € more disposable income: 10 032 €."""
    from impots.behavioural import autofinancement

    autofinancement.job_value.cache_clear()
    assert autofinancement.job_value(2026) == pytest.approx(10_032.0, abs=1.0)


def test_a_job_value_outside_its_bounds_is_refused(monkeypatch) -> None:
    from impots.behavioural import autofinancement
    from impots.engine import compute as engine_compute  # noqa: F401

    class Fake:
        def __init__(self, cost: float, disposable: float) -> None:
            self.baseline = {"salaire_super_brut": cost, "revenu_disponible": disposable}

    calls = iter([Fake(20_000.0, 30_000.0), Fake(0.0, 5_000.0)])
    monkeypatch.setattr("impots.engine.compute", lambda *a, **k: next(calls))
    autofinancement.job_value.cache_clear()
    try:
        with pytest.raises(autofinancement.JobValueError, match="hors de"):
            autofinancement.job_value(2031)
    finally:
        autofinancement.job_value.cache_clear()
