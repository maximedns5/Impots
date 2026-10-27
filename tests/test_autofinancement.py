"""C11, the self-financing of a targeted cut of employer contributions (D-256).

The owner's choice for R5: θ runs from C2's own reading (θ = 0), its jobs valued one by
one, to the Trésor-Éco n° 97's (θ = 1), through the Trésor-Éco's low end at θ = ½. Worked
examples are derived by hand in the docstrings; an implementation agreeing with itself
proves nothing.
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
from impots.predictif.theta import Theta, pinned, value_at

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


def _row(key: str, central: float, low: float, high: float, *, theta_one: str | None,
         support: float | None = None) -> Parameter:
    return Parameter(
        key=key, central=central, low=low, high=high, applies_to="test",
        support=Support(estimated_on="test", max_variation_graded_in_support=support),
        source=Source(citation="test"), verifier=Verifier(verdict="CONFIRMED"),
        responds_to_knobs=EMPLOYER_KNOBS, theta_one=theta_one, theta_reason="test")


def c11_store(*, with_c2: bool = False) -> Store:
    rows = {channels.C11_ROW: _row(channels.C11_ROW, 0.30, 0.0, 0.60, theta_one="high")}
    if with_c2:
        rows.update({
            "employment_elasticity_smic": _row(
                "employment_elasticity_smic", -0.43, -0.52, -0.31, theta_one="low"),
            "employment_elasticity_at_fadeout": _row(
                "employment_elasticity_at_fadeout", -0.1, -0.1, -0.1, theta_one=None),
            "employment_fadeout_smic_multiple": _row(
                "employment_fadeout_smic_multiple", 2.0, 2.0, 2.0, theta_one=None),
        })
    return Store(parameters=rows)


def _at(theta: float, *, jobs: float = 10_000.0, delta: float = -1e9,
        value: float = 10_000.0) -> float:
    result = channels.targeted_self_financing(
        pinned(c11_store(), Theta(common=theta)), CUT, contribution_delta=delta,
        c2_jobs=np.array([jobs]), value_per_job=value, rng=np.random.default_rng(0))
    assert result.applies and result.in_revenue_band
    return float(result.draws[0])


# --------------------------------------------------------------------------- #
# the reading, by hand
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(("theta", "receipts"), [
    (0.0, 0.10e9), (0.25, 0.20e9), (0.5, 0.30e9), (0.75, 0.45e9), (1.0, 0.60e9)])
def test_the_worked_example(theta: float, receipts: float) -> None:
    """A cut costing 1 bn, for which C2 counts 10 000 jobs, each bringing 10 000 €:
    s_C2 = 10 000 × 10 000 / 10⁹ = 0,10. At θ = ¼ the row reads 0,15, and s = 0,10 +
    (0,15 / 0,30) × (0,30 − 0,10) = 0,20; at θ = ¾ it reads 0,45, its upper half
    untouched. The receipts are s × 1 bn."""
    assert _at(theta) == pytest.approx(receipts)


@pytest.mark.parametrize("theta", [0.0, 0.1, 0.3, 0.5, 0.6, 0.9, 1.0])
def test_the_path_is_value_at_with_c2_for_its_low_end(theta: float) -> None:
    """The owner's choice, exactly: the row read through its centre, in its direction,
    C2's reading standing where the published low end would."""
    reading = 10_000.0 * 7_000.0 / 1e9
    expected = value_at(_row("x", 0.30, reading, 0.60, theta_one="high"), theta)
    assert _at(theta, jobs=7_000.0) == pytest.approx(expected * 1e9)


def test_theta_zero_is_c2_s_reading_whatever_the_row_says() -> None:
    """At θ = 0 the published row reads 0, which is no reading: what comes back is
    C2's jobs, valued."""
    assert _at(0.0, jobs=4_830.0, value=10_032.0) == pytest.approx(4_830.0 * 10_032.0)


def test_a_rise_takes_back_what_the_lost_jobs_brought() -> None:
    """A rise of 1 bn, for which C2 loses 10 000 jobs: the same shares, negative
    receipts."""
    assert _at(0.0, jobs=-10_000.0, delta=1e9) == pytest.approx(-0.10e9)
    assert _at(0.5, jobs=-10_000.0, delta=1e9) == pytest.approx(-0.30e9)


def test_the_channel_draws_the_row_and_c2_draw_by_draw() -> None:
    """Unpinned, the band's draws: each draw of the row maps C2's draw of the same
    index, so the share never leaves [s_C2, 0,60]."""
    jobs = np.linspace(5_000.0, 15_000.0, 200)
    result = channels.targeted_self_financing(
        c11_store(), CUT, contribution_delta=-1e9, c2_jobs=jobs, value_per_job=10_000.0,
        draws=200, rng=np.random.default_rng(1))
    share = result.draws / 1e9
    assert np.all(share >= jobs * 10_000.0 / 1e9 - 1e-12) and np.all(share <= 0.60 + 1e-12)


# --------------------------------------------------------------------------- #
# refusals
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("jobs", [30_000.0, 45_000.0, -1_000.0])
def test_a_c2_reading_outside_the_lower_half_is_refused(jobs: float) -> None:
    """At or above the centre, s(θ) would fall from θ = 0 to θ = ½, and the box read at
    its corners would be wrong; below zero, C2 would say the cut destroys jobs."""
    with pytest.raises(channels.ChannelInputMissing, match="outside"):
        _at(0.5, jobs=jobs)


@pytest.mark.parametrize("value", [0.0, -1.0])
def test_a_job_that_brings_nothing_is_refused(value: float) -> None:
    with pytest.raises(channels.ChannelInputMissing, match="SMIC job"):
        _at(0.5, value=value)


def _closed(**overrides: object) -> channels.ChannelResult:
    arguments = {"contribution_delta": -1e9, "c2_jobs": np.array([10_000.0]),
                 "value_per_job": 10_000.0, "rng": np.random.default_rng(0)}
    arguments.update(overrides)
    store = arguments.pop("store", c11_store())
    reform = arguments.pop("reform", CUT)
    result = channels.targeted_self_financing(store, reform, **arguments)
    assert not result.applies and result.draws is None
    return result


def test_it_stays_shut_without_an_employer_knob() -> None:
    assert _closed(reform=FakeReform(ir_bareme=1.0)).message == channels.NO_EMPLOYER_KNOB


def test_it_stays_shut_without_its_row() -> None:
    """Its row is what claims the knobs: without it, C2's rows still say the reform moves
    an employer contribution, and the message says the row is missing, not the knob."""
    store = c11_store(with_c2=True)
    store = Store(parameters={k: v for k, v in store.parameters.items()
                              if k != channels.C11_ROW})
    assert channels.C11_ROW in _closed(store=store).message
    assert _closed(store=Store()).message == channels.NO_EMPLOYER_KNOB


def test_it_says_why_a_reform_is_not_a_targeted_cut() -> None:
    assert _closed(not_targeted="pas une baisse ciblée").message == "pas une baisse ciblée"


def test_it_stays_shut_without_c2_s_jobs() -> None:
    """Not priced at zero: θ = 0 has no reading."""
    assert "θ = 0 n'a pas de lecture" in _closed(c2_jobs=None).message


def test_it_stays_shut_when_no_contribution_moves() -> None:
    assert "aucune cotisation patronale" in _closed(contribution_delta=0.0).message


def test_it_says_its_inputs_were_not_computed() -> None:
    assert _closed(value_per_job=None).message.startswith("Non calculé")


# --------------------------------------------------------------------------- #
# in the band, and at θ
# --------------------------------------------------------------------------- #
C2_INPUTS = {"smic_multiple": np.array([1.0]), "relative_cost_change": np.array([-0.01]),
             "earner_weights": np.array([1e6])}


def _band(theta: float, **extra: object) -> band_module.BehaviouralResult:
    return band_module.compute(
        mechanical=-1e9, reform=CUT, store=pinned(c11_store(with_c2=True), Theta(
            common=theta)), contribution_delta=-1e9, self_financing_value_per_job=10_000.0,
        draws=1, **C2_INPUTS, **extra)


def test_the_band_reads_c2_s_jobs_at_theta_zero() -> None:
    """C2 at θ = 0 is its weakest elasticity, −0,31: 0,31 × 10⁶ × 0,01 = 3 100 jobs,
    worth 31 M€ at 10 000 € each. The receipts are the cost less them; C2 itself, in jobs,
    never enters."""
    result = _band(0.0)
    assert result.band.p50 == pytest.approx(-1e9 + 3_100 * 10_000.0)
    channel = next(c for c in result.channels if c["key"] == "c11_autofinancement")
    assert channel["diagnostics"]["c2_jobs"]["p50"] == pytest.approx(3_100.0)


def test_the_band_at_theta_half_is_the_trésor_éco_s_low_end() -> None:
    assert _band(0.5).band.p50 == pytest.approx(-1e9 + 0.30e9)


def test_it_is_graded_as_c2_is() -> None:
    """C2's rows cannot say how far they carry: neither can a channel standing on them."""
    result = _band(0.5)
    channel = next(c for c in result.channels if c["key"] == "c11_autofinancement")
    assert channel["grade"] == "illustrative"


def test_the_refusal_reaches_the_band() -> None:
    result = band_module.compute(
        mechanical=-1e9, reform=CUT, store=pinned(c11_store(with_c2=True), Theta(common=0.5)),
        contribution_delta=-1e9, self_financing_refused="non ciblée", draws=1, **C2_INPUTS)
    channel = next(c for c in result.channels if c["key"] == "c11_autofinancement")
    assert not channel["applies"] and channel["message"] == "non ciblée"
    assert result.band is None


def test_the_theta_box_is_read_at_its_corners() -> None:
    """Monotone in both rows it rests on, so the box holds the receipts at θ = ½: from
    the corner where both are at 0 (C2 at −0,31, s = 0,031) to the one where the row is
    at 1 (s = 0,60, whatever C2 says)."""
    at = comportement.evaluate(
        Theta(common=0.5), mechanical=-1e9, reform=CUT, store=c11_store(with_c2=True),
        contribution_delta=-1e9, self_financing_value_per_job=10_000.0, **C2_INPUTS)
    assert at.receipts == pytest.approx(-0.70e9)
    assert at.box[0] == pytest.approx(-1e9 + 3_100 * 10_000.0)
    assert at.box[1] == pytest.approx(-0.40e9)
    assert channels.C11_ROW in at.claimed


# --------------------------------------------------------------------------- #
# the row, the API's inputs, what a job brings
# --------------------------------------------------------------------------- #
def test_the_row_is_the_one_the_channel_maps() -> None:
    """The channel maps the row's lower half onto C2's segment, and must know where it
    ends: 0 at the low end, the Trésor-Éco's 30 % at the centre, its 60 % at the top."""
    from impots.behavioural.store import load

    row = load()[channels.C11_ROW]
    assert (row.low, row.central, row.high) == (0.0, channels.C11_CENTRE, 0.60)
    assert row.theta_one == "high"
    for knob in ("allegement_general_t_min", "allegement_general_t_delta_moins_de_50",
                 "allegement_general_plafond", "bandeau_maladie_taux"):
        assert row.claims(knob)


def _request(year: int, **knobs: object) -> SimpleNamespace:
    return SimpleNamespace(year=year, reform=FakeReform(**knobs))


@pytest.fixture
def a_job_brings(monkeypatch):
    from impots.behavioural import autofinancement

    monkeypatch.setattr(autofinancement, "job_value", lambda year: 10_032.0)


def test_a_curve_cut_gets_what_a_job_brings(a_job_brings) -> None:
    from impots.api import main

    inputs = main._self_financing_inputs(
        _request(2026, allegement_general_t_delta_moins_de_50=0.3831))
    assert inputs == {"self_financing_value_per_job": 10_032.0}


def test_the_plafond_from_2026_is_not_a_targeted_cut(a_job_brings) -> None:
    """D-239: from 2026 the plafond relieves the wages above 3 SMIC."""
    from impots.api import main

    inputs = main._self_financing_inputs(_request(2026, allegement_general_plafond=3.5))
    assert "`allegement_general_plafond`" in inputs["self_financing_refused"]
    assert "2026" in inputs["self_financing_refused"]
    assert main._self_financing_inputs(_request(2025, allegement_general_plafond=1.7)) == {
        "self_financing_value_per_job": 10_032.0}


def test_a_targeted_cut_mixed_with_the_plafond_is_refused(a_job_brings) -> None:
    """The employer delta is one total: no share of it can be said to be the curve's."""
    from impots.api import main

    inputs = main._self_financing_inputs(_request(
        2026, allegement_general_t_min=0.021, allegement_general_plafond=3.5))
    assert "self_financing_refused" in inputs


def test_no_employer_knob_no_inputs(a_job_brings) -> None:
    from impots.api import main

    assert main._self_financing_inputs(_request(2026, ir_bareme=1.0)) == {}


def _macro_with(monkeypatch, tables: dict) -> None:
    from impots.macro import store as macro_store

    monkeypatch.setattr(macro_store, "load", lambda: macro_store.Store(tables=tables))


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


def test_the_employer_inputs_carry_c11_s(a_job_brings, monkeypatch) -> None:
    """Merged with C2's, so every caller of `_employer_inputs` hands them to the band."""
    import polars as pl

    from impots.api import main

    monkeypatch.setattr(main, "_smic_annual", lambda year: 20_000.0)
    _macro_with(monkeypatch, {"primary_balance_by_instrument": SimpleNamespace(
        values={"impot_sur_le_revenu": {}})})
    inputs = main._employer_inputs(
        _request(2026, allegement_general_t_min=0.021),
        pl.DataFrame({"household_id": [1], "salaire_brut_annuel": [20_000.0],
                      "weight": [100.0]}),
        pl.DataFrame({"household_id": [1], "weight": [100.0],
                      "salaire_super_brut": [21_000.0],
                      "salaire_super_brut_reform": [20_900.0]}),
        SimpleNamespace(employer_contribution_delta=-1e4))
    assert inputs["self_financing_value_per_job"] == 10_032.0


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


def test_the_store_counts_the_row_open() -> None:
    from impots.behavioural.store import load

    assert load()[channels.C11_ROW].is_open
    assert dataclasses.replace(load()[channels.C11_ROW], low=0.3, high=0.3,
                               central=0.3).is_open is False
