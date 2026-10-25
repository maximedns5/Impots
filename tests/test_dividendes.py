"""Dividends and the PFU: the source, the rows and the channel C10 (D-249, §6).

The reader is held against the PDF of Bach et al., the rows against the reader, and the
channel against a worked example derived by hand.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import polars as pl
import pytest

from impots.behavioural import channels
from impots.behavioural.store import Parameter, Source, Store, Support, Verifier


class Reform:
    """A reform with only the knobs it sets, as `channels._knobs` reads them."""

    def __init__(self, **knobs: float) -> None:
        self._knobs = knobs
        for key, value in knobs.items():
            setattr(self, key, value)

    def model_dump(self, exclude_none: bool = True, **_) -> dict:
        return dict(self._knobs)


PFU_CUT = Reform(pfu_taux=0.118)


def _row(key: str, value: float, support: float | None) -> Parameter:
    return Parameter(
        key=key, central=value, low=value, high=value, applies_to="test",
        support=Support(estimated_on="test", max_variation_graded_in_support=support),
        source=Source(citation="test"), verifier=Verifier(verdict="CONFIRMED"),
        responds_to_knobs=("pfu_taux",))


def _store(owners: float = 2.5, others: float = 0.0, share: float = 0.774) -> Store:
    return Store(parameters={
        channels.C10_ELASTICITIES[0]: _row(channels.C10_ELASTICITIES[0], owners, 0.075),
        channels.C10_ELASTICITIES[1]: _row(channels.C10_ELASTICITIES[1], others, 0.085),
        channels.C10_SHARE: _row(channels.C10_SHARE, share, None)})


INPUTS = {"dividend_base_eur": 50e9, "levy_rate_baseline": 0.30, "levy_rate_reform": 0.29}


# --------------------------------------------------------------------------- #
# The source
# --------------------------------------------------------------------------- #
def _source():
    pytest.importorskip("pypdf")
    from impots.behavioural import dividendes

    if not (dividendes.RAW / dividendes.SOURCE_FILE).exists():
        pytest.skip("data/raw/ n'a pas le document de travail de Bach et al.")
    return dividendes


def test_the_elasticities_and_their_variations_are_the_paper_s() -> None:
    found = _source().elasticities()
    assert (found.owners_2018, found.others_2018) == (2.5, 0.0)
    assert (found.owners_2013, found.others_2013) == (3.2, 2.4)
    assert (found.variation_owners_2018, found.variation_others_2018,
            found.variation_2013) == (0.075, 0.085, 0.06)


def test_figure_2d_is_read_and_holds_against_panel_b_and_the_text() -> None:
    """The reader itself refuses a reading that misses either check; here the values."""
    dividendes = _source()
    figure = dividendes.figure_2d()
    for year, declared in figure.returns.items():
        assert figure.total(year) == pytest.approx(declared, abs=dividendes.MATCH_BN)
    assert figure.total(2018) - figure.total(2017) == pytest.approx(9.0, abs=0.5)
    shares = [round(figure.share_with_control(y), 3) for y in dividendes.PFU_YEARS]
    assert shares == [0.8, 0.78, 0.777, 0.738]
    assert round(figure.share_with_control(2017), 3) == 0.735


def test_a_reading_that_misses_panel_b_is_refused(monkeypatch) -> None:
    """GUARD. The two panels are drawn apart from the same data: a series misread by more
    than the plotting resolution breaks the year's sum, and the reading is refused."""
    dividendes = _source()
    dividendes.figure_2d.cache_clear()
    real = dividendes._panel

    def shifted(form, texts, labels):
        out = real(form, texts, labels)
        if labels == dividendes.SERIES:
            out[labels[0]] = {year: value + 0.2 for year, value in out[labels[0]].items()}
        return out

    monkeypatch.setattr(dividendes, "_panel", shifted)
    with pytest.raises(dividendes.DividendSourceError, match="panneau"):
        dividendes.figure_2d()
    dividendes.figure_2d.cache_clear()


def test_a_reading_that_misses_the_text_s_nine_billion_is_refused(monkeypatch) -> None:
    """GUARD. A legend swapped between two panels would still sum right; the rise the text
    prints from 2017 to 2018 is the second check, and a reading off it is refused."""
    dividendes = _source()
    dividendes.figure_2d.cache_clear()
    monkeypatch.setattr(dividendes, "YEAR_TO_YEAR_BN", 5.0)
    with pytest.raises(dividendes.DividendSourceError, match="9"):
        dividendes.figure_2d()
    dividendes.figure_2d.cache_clear()


def test_the_convention_is_the_published_ranges() -> None:
    dividendes = _source()
    rows = dividendes.convention(dividendes.elasticities(), dividendes.figure_2d())
    owners = rows["dividend_elasticity_firm_owners"]
    others = rows["dividend_elasticity_other_holders"]
    share = rows["dividend_share_firm_owners"]
    assert (owners.low, owners.central, owners.high) == (2.5, 2.5, 3.2)
    assert (others.low, others.central, others.high) == (0.0, 0.0, 2.4)
    assert (share.low, share.central, share.high) == (0.738, 0.774, 0.8)


def test_the_store_rows_are_the_reading() -> None:
    """The store against the PDF (D-026): each range as the convention builds it, and
    each elasticity's support the smaller of the two variations that identified it, a
    rise of the net-of-tax rate and a fall having each been seen at one size only."""
    from impots.behavioural.store import load

    dividendes = _source()
    found = dividendes.elasticities()
    store = load()
    for key, expected in dividendes.convention(found, dividendes.figure_2d()).items():
        row = store[key]
        assert (row.low, row.central, row.high) == (expected.low, expected.central,
                                                    expected.high), key
        assert row.theta_one == "high" and row.rank.level == 1
        assert row.rank.channel == "dividendes_pfu" and row.claims("pfu_taux")
    supports = {
        "dividend_elasticity_firm_owners": min(found.variation_owners_2018,
                                               found.variation_2013),
        "dividend_elasticity_other_holders": min(found.variation_others_2018,
                                                 found.variation_2013),
        "dividend_share_firm_owners": None}
    for key, bound in supports.items():
        assert store[key].support.max_variation_graded_in_support == bound, key


# --------------------------------------------------------------------------- #
# The channel
# --------------------------------------------------------------------------- #
def test_c10_reproduces_the_worked_example() -> None:
    """By hand: Δln(1 − τ) = ln(0,71 / 0,70); ε = 0,774 × 2,5 + 0,226 × 0 = 1,935; the
    dividends rise by 1,935 × 0,0141846 × 50 bn = 1,3724 bn, taxed at 0,29."""
    result = channels.dividend_response(_store(), PFU_CUT, draws=1,
                                        rng=np.random.default_rng(0), **INPUTS)
    assert result.applies and result.in_revenue_band
    delta = np.log(0.71 / 0.70)
    assert result.diagnostics["delta_log_net_of_tax"] == pytest.approx(delta, abs=1e-8)
    induced = 1.935 * delta * 50e9
    assert result.diagnostics["induced_dividends_eur"]["p50"] == pytest.approx(induced, abs=1)
    assert result.draws[0] == pytest.approx(0.29 * induced, rel=1e-12)
    assert result.draws[0] == pytest.approx(0.398e9, abs=0.001e9)


def test_c10_composes_the_two_groups_by_the_share() -> None:
    at_hike = channels.dividend_response(
        _store(owners=3.2, others=2.4, share=0.8), PFU_CUT, draws=1,
        rng=np.random.default_rng(0), **INPUTS)
    epsilon = 0.8 * 3.2 + 0.2 * 2.4
    assert at_hike.draws[0] == pytest.approx(
        0.29 * epsilon * np.log(0.71 / 0.70) * 50e9, rel=1e-12)


def test_c10_is_silent_without_the_pfu_knob() -> None:
    result = channels.dividend_response(_store(), Reform(decote_taux=0.3), **INPUTS)
    assert not result.applies and result.message == channels.NO_PFU_KNOB


def test_c10_says_not_computed_without_capital_income() -> None:
    """A population run without the imputation has no dividends: the channel says so,
    and does not price a response on nothing."""
    result = channels.dividend_response(_store(), PFU_CUT)
    assert not result.applies and "Non calculé" in result.message
    assert "imputation des revenus du capital" in result.message


def test_c10_refuses_a_promised_base_that_is_empty() -> None:
    with pytest.raises(channels.ChannelInputMissing, match="dividends"):
        channels.dividend_response(_store(), PFU_CUT, **{**INPUTS,
                                                         "dividend_base_eur": 0.0})


@pytest.mark.parametrize("rates", [(None, 0.29), (0.30, None), (1.0, 0.29), (0.30, 1.2)])
def test_c10_refuses_rates_it_cannot_take_a_log_of(rates) -> None:
    before, after = rates
    with pytest.raises(channels.ChannelInputMissing, match="C10"):
        channels.dividend_response(_store(), PFU_CUT, dividend_base_eur=50e9,
                                   levy_rate_baseline=before, levy_rate_reform=after)


def test_c10_says_which_row_is_missing() -> None:
    store = _store()
    del store.parameters[channels.C10_SHARE]
    result = channels.dividend_response(store, PFU_CUT, **INPUTS)
    assert not result.applies and channels.C10_SHARE in result.message


def test_the_band_carries_c10_and_grades_it_on_its_support() -> None:
    """A one-point cut moves the net-of-tax rate by 1,4 %: in support (7,5 %). The PFU at
    zero moves it by 18,3 %: an extrapolation, said so."""
    from impots.behavioural import band

    small = band.compute(mechanical=-0.8e9, reform=PFU_CUT, store=_store(), draws=1,
                         **INPUTS)
    row = next(c for c in small.channels if c["key"] == "c10_dividendes")
    assert row["applies"] and row["grade"] == "in-support"
    assert small.band.p50 == pytest.approx(-0.8e9 + 0.29 * 1.935 * np.log(0.71 / 0.7)
                                           * 50e9, rel=1e-9)
    large = band.compute(mechanical=-10e9, reform=Reform(pfu_taux=0.0), store=_store(),
                         draws=1, dividend_base_eur=50e9, levy_rate_baseline=0.30,
                         levy_rate_reform=0.172)
    row = next(c for c in large.channels if c["key"] == "c10_dividendes")
    assert row["grade"] == "illustrative" and large.grade == "illustrative"


def test_the_share_row_is_not_graded() -> None:
    """A composition has no support: grading on it would make C10 illustrative always."""
    from impots.behavioural import band

    result = band.compute(mechanical=-0.8e9, reform=PFU_CUT, store=_store(), draws=1,
                          **INPUTS)
    assert result.grade == "in-support"


# --------------------------------------------------------------------------- #
# The API's inputs
# --------------------------------------------------------------------------- #
def _request(**knobs):
    from impots.api.schemas import ReformSpec

    return SimpleNamespace(reform=ReformSpec(**knobs), year=2024)


@pytest.fixture
def _loaded(monkeypatch):
    """The store as the API loads it, with the three rows of `_store` in it."""
    import impots.behavioural.store as store_module

    monkeypatch.setattr(store_module, "load", lambda *a, **k: _store())


def test_the_api_gives_c10_the_run_s_dividends_and_both_rates(_loaded, monkeypatch) -> None:
    from impots.api import main
    from impots.population import capital as capital_module

    monkeypatch.setattr(capital_module, "social_levy_rate", lambda year: 0.172)
    households = pl.DataFrame({"weight": [2.0, 3.0], "dividendes": [10_000.0, 5_000.0]})
    inputs = main._dividend_inputs(_request(pfu_taux=0.20), households)
    assert inputs["dividend_base_eur"] == pytest.approx(35_000.0)
    assert inputs["levy_rate_baseline"] == pytest.approx(0.128 + 0.172)
    assert inputs["levy_rate_reform"] == pytest.approx(0.20 + 0.172)


def test_the_api_gives_c10_nothing_without_imputed_capital(_loaded) -> None:
    from impots.api import main

    nothing = pl.DataFrame({"weight": [2.0], "dividendes": [0.0]})
    some = pl.DataFrame({"weight": [2.0], "dividendes": [10_000.0]})
    assert main._dividend_inputs(_request(pfu_taux=0.20), nothing) == {}
    assert main._dividend_inputs(_request(pfu_taux=0.20), None) == {}
    assert main._dividend_inputs(_request(decote_taux=0.3), some) == {}


def test_the_social_levies_are_measured_on_the_engine() -> None:
    """17,2 % in 2024; 18,6 % from 2026, when the CSG on capital income rises. A sum of
    2024 parameters would have missed the second."""
    from impots.population import capital as capital_module

    assert capital_module.social_levy_rate(2024) == pytest.approx(0.172, abs=1e-6)
    assert capital_module.social_levy_rate(2026) == pytest.approx(0.186, abs=1e-6)
