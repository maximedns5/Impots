"""Dividends and the PFU: the source, the rows and the channel C10 (D-249, §6).

The reader is held against the PDF of Bach et al., the rows against the reader, and the
channel against a worked example derived by hand.
"""

from __future__ import annotations

import dataclasses
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


def _store(owners: float = 2.5, others: float = 0.0, share: float = 0.774,
           shift: float = 0.0, shift_support: float = 0.06) -> Store:
    """The four rows of C10. No wage shift by default, so that D-249's worked examples
    keep their numbers; the shift has its own (D-252)."""
    return Store(parameters={
        channels.C10_ELASTICITIES[0]: _row(channels.C10_ELASTICITIES[0], owners, 0.075),
        channels.C10_ELASTICITIES[1]: _row(channels.C10_ELASTICITIES[1], others, 0.085),
        channels.C10_SHARE: _row(channels.C10_SHARE, share, None),
        channels.C10_WAGE_SHIFT: _row(channels.C10_WAGE_SHIFT, shift, shift_support)})


#: A euro of net taxable wage: its levies, its cost to the employer, and the IS rate on
#: the profit it becomes when it is no longer paid (D-252).
WEDGE = {"wage_levy_rate": 1.14, "wage_cost_rate": 1.66, "corporate_rate": 0.25}
INPUTS = {"dividend_base_eur": 50e9, "levy_rate_baseline": 0.30, "levy_rate_reform": 0.29,
          **WEDGE}


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


PANEL_B = {"dividends": (-0.00673, -0.00709, 0.00351, 0.00324),
           "dividends_se": (0.00018, 0.00018, 0.00016, 0.00015),
           "wages": (0.00033, -0.00002, -0.00046, -0.00100),
           "wages_se": (0.00012, 0.00014, 0.00012, 0.00013)}


def test_table_2b_panel_b_is_the_paper_s() -> None:
    """Columns (1) to (4): 2013 in the short run and over all years, then 2018."""
    table = _source().table_2b()
    assert dataclasses.asdict(table) == PANEL_B


def test_a_panel_b_looked_for_on_another_page_is_refused(monkeypatch) -> None:
    """GUARD. A page without the panel gives no numbers, and the reader says so."""
    dividendes = _source()
    monkeypatch.setattr(dividendes, "TABLE_PAGE", dividendes.TABLE_PAGE - 1)
    with pytest.raises(dividendes.DividendSourceError, match="tableau 2"):
        dividendes.table_2b()


def test_a_panel_b_with_its_reforms_crossed_is_refused(monkeypatch) -> None:
    """GUARD. The 2013 reform raised the tax and the 2018 one cut it: the dividends fall
    in columns (1) and (2) and rise in (3) and (4). Read with the two reforms crossed,
    they would not, and the reading is refused."""
    dividendes = _source()
    real = dividendes._text
    printed = "-0.00673*** -0.00709*** 0.00351*** 0.00324***"
    crossed = "0.00351*** 0.00324*** -0.00673*** -0.00709***"

    def swapped(page):
        text = real(page)
        return text.replace(printed, crossed) if printed in text else text

    monkeypatch.setattr(dividendes, "_text", swapped)
    with pytest.raises(dividendes.DividendSourceError, match="2013"):
        dividendes.table_2b()


def test_the_wage_shift_is_the_ratio_of_the_two_coefficients() -> None:
    """By hand: 0,00100 / 0,00324 = 0,309 at the centre; at the top, 2020 and 2021, twice
    col. 4 less col. 3, (2 × 0,00100 − 0,00046) / (2 × 0,00324 − 0,00351) = 0,519; 0 at the
    bottom, the 2013 wage having not moved."""
    from impots.behavioural import dividendes

    shift = dividendes.wage_shift(dividendes.Table2B(**PANEL_B))
    assert (shift.low, shift.central, shift.high) == (0.0, 0.309, 0.519)


def test_a_2013_wage_that_moved_is_not_read_as_no_shift() -> None:
    """GUARD. The low end is 0 because over all years the 2013 wage coefficient is
    −0,00002 for a standard error of 0,00014. Had it left its 95 % interval around zero,
    0 would not be its reading: the convention refuses rather than keep it."""
    from impots.behavioural import dividendes

    moved = dataclasses.replace(dividendes.Table2B(**PANEL_B),
                                wages=(0.00033, 0.00040, -0.00046, -0.00100))
    with pytest.raises(dividendes.DividendSourceError, match="2013"):
        dividendes.wage_shift(moved)


def test_the_convention_is_the_published_ranges() -> None:
    dividendes = _source()
    rows = dividendes.convention(dividendes.elasticities(), dividendes.figure_2d(),
                                 dividendes.table_2b())
    owners = rows["dividend_elasticity_firm_owners"]
    others = rows["dividend_elasticity_other_holders"]
    share = rows["dividend_share_firm_owners"]
    shift = rows["dividend_wage_shift_firm_owners"]
    assert (owners.low, owners.central, owners.high) == (2.5, 2.5, 3.2)
    assert (others.low, others.central, others.high) == (0.0, 0.0, 2.4)
    assert (share.low, share.central, share.high) == (0.738, 0.774, 0.8)
    assert (shift.low, shift.central, shift.high) == (0.0, 0.309, 0.519)


def test_the_store_rows_are_the_reading() -> None:
    """The store against the PDF (D-026): each range as the convention builds it, and
    each response's support the smaller of the two variations that identified it, a
    rise of the net-of-tax rate and a fall having each been seen at one size only. The
    wage shift rests on both reforms, as the owners' elasticity does (D-252)."""
    from impots.behavioural.store import load

    dividendes = _source()
    found = dividendes.elasticities()
    store = load()
    rows = dividendes.convention(found, dividendes.figure_2d(), dividendes.table_2b())
    assert channels.C10_WAGE_SHIFT in rows
    for key, expected in rows.items():
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
        "dividend_share_firm_owners": None,
        "dividend_wage_shift_firm_owners": min(found.variation_owners_2018,
                                               found.variation_2013)}
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


def test_c10_takes_back_the_wages_the_owners_stop_paying_themselves() -> None:
    """By hand, on the worked example (D-252). The owners' induced dividends, 1,3724 bn,
    come with 0,309 × 1,3724 = 0,4241 bn of net taxable wage they no longer pay
    themselves. That wage brought 1,14 euro of levies per euro and cost the firm 1,66: its
    levies are lost, its cost becomes a profit taxed at 25 %. The offset is 0,4241 ×
    (1,14 − 0,25 × 1,66) = 0,3074 bn, and C10 brings back 0,3980 − 0,3074 = 0,0905 bn."""
    result = channels.dividend_response(_store(shift=0.309), PFU_CUT, draws=1,
                                        rng=np.random.default_rng(0), **INPUTS)
    induced = 1.935 * np.log(0.71 / 0.70) * 50e9
    shifted = 0.309 * induced
    offset = shifted * (1.14 - 0.25 * 1.66)
    assert result.diagnostics["wage_shift_eur"]["p50"] == pytest.approx(shifted, abs=1)
    assert result.diagnostics["wage_shift_offset_eur"]["p50"] == pytest.approx(offset,
                                                                               abs=1)
    assert result.diagnostics["wage_wedge"] == {
        "levies_per_eur": 1.14, "cost_per_eur": 1.66, "corporate_rate": 0.25,
        "lost_per_eur": pytest.approx(0.725)}
    assert result.draws[0] == pytest.approx(0.29 * induced - offset, rel=1e-12)
    assert result.draws[0] == pytest.approx(0.0905e9, abs=0.0005e9)
    assert "tableau 2 B" not in result.diagnostics["not_counted"]


def test_c10_shifts_the_owners_wages_only() -> None:
    """The others control no firm: they have no wage of their own to turn into a
    dividend, and their response carries no offset."""
    result = channels.dividend_response(
        _store(owners=3.2, others=2.4, share=0.8, shift=0.309), PFU_CUT, draws=1,
        rng=np.random.default_rng(0), **INPUTS)
    delta = np.log(0.71 / 0.70)
    owners = 0.8 * 3.2 * delta * 50e9
    induced = (0.8 * 3.2 + 0.2 * 2.4) * delta * 50e9
    assert result.draws[0] == pytest.approx(
        0.29 * induced - 0.309 * owners * (1.14 - 0.25 * 1.66), rel=1e-12)


@pytest.mark.parametrize("wedge", [
    {"wage_levy_rate": None}, {"wage_cost_rate": None}, {"corporate_rate": None},
    {"wage_levy_rate": 0.0}, {"wage_levy_rate": 1.66}, {"corporate_rate": 1.0},
    {"corporate_rate": -0.1}])
def test_c10_refuses_a_wedge_it_cannot_price_the_shift_on(wedge) -> None:
    """GUARD. The shift is priced on a euro of wage: what it brings the state, which is
    positive, and what it costs the firm, which is more — or nothing would be left to the
    employee. And on a corporate rate below one."""
    with pytest.raises(channels.ChannelInputMissing, match="C10"):
        channels.dividend_response(_store(shift=0.309), PFU_CUT, **{**INPUTS, **wedge})


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
                                   levy_rate_baseline=before, levy_rate_reform=after,
                                   **WEDGE)


@pytest.mark.parametrize("key", [channels.C10_SHARE, channels.C10_WAGE_SHIFT])
def test_c10_says_which_row_is_missing(key) -> None:
    store = _store()
    del store.parameters[key]
    result = channels.dividend_response(store, PFU_CUT, **INPUTS)
    assert not result.applies and key in result.message


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
                         levy_rate_reform=0.172, **WEDGE)
    row = next(c for c in large.channels if c["key"] == "c10_dividendes")
    assert row["grade"] == "illustrative" and large.grade == "illustrative"


def test_the_band_takes_the_wage_shift_off_c10() -> None:
    from impots.behavioural import band

    result = band.compute(mechanical=-0.8e9, reform=PFU_CUT, store=_store(shift=0.309),
                          draws=1, **INPUTS)
    induced = 1.935 * np.log(0.71 / 0.7) * 50e9
    assert result.band.p50 == pytest.approx(
        -0.8e9 + 0.29 * induced - 0.309 * induced * (1.14 - 0.25 * 1.66), rel=1e-9)


def test_the_wage_shift_is_graded_with_the_elasticities() -> None:
    """The shift answers the same variation of the net-of-tax rate, measured on the same
    two reforms: a cut that overruns its support makes C10 an extrapolation (D-252)."""
    from impots.behavioural import band

    result = band.compute(mechanical=-0.8e9, reform=PFU_CUT,
                          store=_store(shift=0.309, shift_support=0.01), draws=1, **INPUTS)
    row = next(c for c in result.channels if c["key"] == "c10_dividendes")
    assert row["grade"] == "illustrative" and result.grade == "illustrative"


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
    """The store as the API loads it, with the rows of `_store` in it, and the wage wedge
    as the engine would measure it, without running it."""
    import impots.behavioural.store as store_module
    from impots.population import capital as capital_module

    monkeypatch.setattr(store_module, "load", lambda *a, **k: _store())
    monkeypatch.setattr(capital_module, "wage_wedge", lambda year: (1.14, 1.66))


def test_the_api_gives_c10_the_run_s_dividends_and_both_rates(_loaded, monkeypatch) -> None:
    from impots.api import main
    from impots.population import capital as capital_module

    monkeypatch.setattr(capital_module, "social_levy_rate", lambda year: 0.172)
    households = pl.DataFrame({"weight": [2.0, 3.0], "dividendes": [10_000.0, 5_000.0]})
    inputs = main._dividend_inputs(_request(pfu_taux=0.20), households)
    assert inputs["dividend_base_eur"] == pytest.approx(35_000.0)
    assert inputs["levy_rate_baseline"] == pytest.approx(0.128 + 0.172)
    assert inputs["levy_rate_reform"] == pytest.approx(0.20 + 0.172)


def test_the_api_gives_c10_the_wage_wedge_and_the_corporate_rate(_loaded,
                                                                  monkeypatch) -> None:
    """The wedge as measured, and the IS rate the profit pays: the law's for the year, or
    the reform's when it sets one (D-252)."""
    from impots.api import main
    from impots.entreprises.reforms import FirmReformSpec
    from impots.population import capital as capital_module

    monkeypatch.setattr(capital_module, "social_levy_rate", lambda year: 0.172)
    households = pl.DataFrame({"weight": [2.0], "dividendes": [10_000.0]})
    inputs = main._dividend_inputs(_request(pfu_taux=0.20), households)
    assert (inputs["wage_levy_rate"], inputs["wage_cost_rate"]) == (1.14, 1.66)
    assert inputs["corporate_rate"] == pytest.approx(0.25)
    request = SimpleNamespace(reform=_request(pfu_taux=0.20).reform, year=2024,
                              firm_reform=FirmReformSpec(is_taux_normal=0.22))
    assert main._dividend_inputs(request, households)["corporate_rate"] == pytest.approx(
        0.22)


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


def test_the_wage_wedge_is_measured_on_the_engine() -> None:
    """Figure A2's case in 2026, six PASS of gross wage: a euro of net taxable wage brings
    1,14 euro of levies and costs the employer 1,66 (D-252). Measured at the margin, on
    the last thousand euros: an average would count the bands below the PASS."""
    from impots.population import capital as capital_module

    levy, cost = capital_module.wage_wedge(2026)
    assert levy == pytest.approx(1.1406, abs=5e-4)
    assert cost == pytest.approx(1.6559, abs=5e-4)
