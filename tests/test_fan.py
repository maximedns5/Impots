"""B3 — the fan, and the second double count it exists to refuse.

The test that matters most here is `test_leakage_is_reported_but_not_applied`. §1 asks
the IO layer to scale the impulse by its domestic share before handing it to B3, and
that instruction is unsafe for a multiplier that already contains import crowding-out.
Mésange's does. Applying it would have removed about a quarter of every effect, silently
and plausibly.
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.macro import fan, io_layer, mesange, shocks, store, tes

pytest.importorskip("openpyxl")
pytest.importorskip("pypdf")

HAVE_SOURCES = (
    (tes.RAW / "insee_TES_symetrique_A38_2023SD.xlsx").exists()
    and (mesange.RAW / mesange.SOURCE_FILE).exists()
)
pytestmark = pytest.mark.skipif(
    not HAVE_SOURCES, reason="data/raw/ has no primary sources — they are not committed"
)


@pytest.fixture(scope="module")
def table():
    return tes.load("2023SD")


@pytest.fixture(scope="module")
def loaded():
    return store.load()


@pytest.fixture(scope="module")
def gdp(table):
    return tes.gdp(table) * 1e6


@pytest.fixture(scope="module")
def composition(table):
    jobs = tes.employment(table.branches, table.base_year)
    impulse = shocks.build({"csg_imposable": -5.0e9}, year=2026)
    return io_layer.composition(table, shocks.allocation(table, impulse), jobs,
                                use="consommation_finale")


def _run(loaded, gdp, deltas, **kwargs):
    impulse = shocks.build(deltas, year=2026, **kwargs)
    return fan.run(impulse, loaded, gdp_eur=gdp)


# --- the double count this module refuses ------------------------------------------


def test_leakage_is_reported_but_not_applied(loaded, gdp, composition):
    """The median must be the central multiplier times the impulse, undiminished.

    Mésange reports its first-year public-investment figure as what survives "l'éviction
    par les importations", and every variant table carries an Importations row. Scaling
    by `1 - leakage` on top would subtract France's import propensity twice. The fan
    therefore computes leakage, shows it, and leaves the impulse whole.
    """
    # More draws than the product uses: the band is wide enough that the median of
    # 1 000 draws wobbles by ~9 %, and this test must discriminate a 27 % effect.
    impulse = shocks.build({"csg_imposable": -5.0e9}, year=2026)
    result = fan.run(impulse, loaded, gdp_eur=gdp, composition=composition, draws=40_000)

    central = loaded.tables["multiplier_by_instrument"].at("csg", "1")
    undiminished = central * 5.0e9
    assert result.gdp_eur["1"].p50 == pytest.approx(undiminished, rel=0.05)

    # And the leakage-applied figure must be visibly different, or the test is vacuous.
    diminished = undiminished * composition.domestic_share
    assert abs(undiminished - diminished) > 0.2 * abs(undiminished)
    assert result.gdp_eur["1"].p50 != pytest.approx(diminished, rel=0.05)

    assert result.assumptions.leakage_applied is False
    assert result.assumptions.leakage == pytest.approx(composition.leakage)


def test_the_assumptions_strip_says_leakage_was_not_applied(loaded, gdp, composition):
    result = fan.run(shocks.build({"ir": -3.0e9}, year=2026), loaded,
                     gdp_eur=gdp, composition=composition)
    assert any("NON APPLIQUÉE" in note for note in result.notes)


# --- never a point estimate ---------------------------------------------------------


def test_the_fan_is_never_a_point(loaded, gdp):
    result = _run(loaded, gdp, {"ir": -3.0e9})
    for horizon, quantiles in result.gdp_eur.items():
        assert quantiles.p10 < quantiles.p50 < quantiles.p90, horizon
        assert quantiles.width > 0


def test_a_parameter_with_no_spread_is_refused():
    """A zero-width draw would render as a point estimate."""
    rng = np.random.default_rng(0)
    with pytest.raises(fan.FanError, match="point estimate"):
        fan._draw_multiplier(rng, 0.4, 0.0, 10)


def test_the_fan_is_reproducible(loaded, gdp):
    first = _run(loaded, gdp, {"ir": -3.0e9})
    second = _run(loaded, gdp, {"ir": -3.0e9})
    assert first.gdp_eur["1"].p50 == second.gdp_eur["1"].p50


def test_a_different_seed_moves_the_quantiles_but_not_the_centre(loaded, gdp):
    impulse = shocks.build({"ir": -3.0e9}, year=2026)
    a = fan.run(impulse, loaded, gdp_eur=gdp, seed=1)
    b = fan.run(impulse, loaded, gdp_eur=gdp, seed=2)
    assert a.gdp_eur["1"].p50 != b.gdp_eur["1"].p50
    assert a.gdp_eur["1"].p50 == pytest.approx(b.gdp_eur["1"].p50, rel=0.10)


# --- scale, sign and the VAT basis --------------------------------------------------


def test_the_response_scales_with_the_impulse(loaded, gdp):
    # Same seed, so the draws are identical and only the scaling differs.
    small = _run(loaded, gdp, {"ir": -1.0e9}).gdp_eur["1"].p50
    large = _run(loaded, gdp, {"ir": -3.0e9}).gdp_eur["1"].p50
    assert large == pytest.approx(3 * small, rel=0.02)


def test_a_tax_rise_contracts(loaded, gdp):
    assert _run(loaded, gdp, {"ir": +3.0e9}).gdp_eur["1"].p50 < 0


def test_the_vat_basis_divides_by_its_own_ex_ante_factor(loaded, gdp):
    """A VAT reform costed gross must not take a multiplier 18 % too large."""
    impulse = shocks.Impulse(year=2026, by_instrument={"tva": 5.0e9})
    result = fan.run(impulse, loaded, gdp_eur=gdp, draws=40_000)
    central = loaded.tables["multiplier_by_instrument"].at("tva", "1")
    assert result.gdp_eur["1"].p50 == pytest.approx(central * 5.0e9 / 1.18, rel=0.05)


def test_a_targeted_allegement_creates_more_jobs_than_a_uniform_one(loaded, gdp):
    """The verification's headline finding, carried all the way to an output."""
    uniform = _run(loaded, gdp, {"employer_contributions": -5.0e9})
    targeted = _run(loaded, gdp, {"employer_contributions": -5.0e9},
                    knobs=("allegement_general_plafond",))
    assert targeted.jobs_thousands_etp["3"].p50 > uniform.jobs_thousands_etp["3"].p50
    ratio = targeted.jobs_thousands_etp["3"].p50 / uniform.jobs_thousands_etp["3"].p50
    assert ratio == pytest.approx(403 / 290, rel=0.05)


# --- decomposition and what is unavailable ------------------------------------------


def test_the_scenario_dimension_refuses_itself_with_a_reason(loaded, gdp):
    """The cycle toggle contributes zero, and must say why rather than look like zero."""
    result = _run(loaded, gdp, {"ir": -3.0e9})
    decomposition = result.decomposition["1"]
    assert decomposition.scenario == 0.0
    assert decomposition.scenario_available is False
    assert "DÉPENSE" in decomposition.scenario_unavailable_because
    assert decomposition.parameter_share == 1.0


def test_the_parameter_spread_is_the_reported_width(loaded, gdp):
    result = _run(loaded, gdp, {"ir": -3.0e9})
    assert result.decomposition["1"].parameter == pytest.approx(
        result.gdp_eur["1"].width, rel=1e-9)


def test_there_is_no_revenue_feedback_and_the_fan_says_so(loaded, gdp):
    result = _run(loaded, gdp, {"ir": -3.0e9})
    assert any("retour de recettes" in note for note in result.notes)
    assert "revenue_gdp_elasticity" not in loaded.tables


# --- refusals -----------------------------------------------------------------------


def test_a_reform_with_no_mapped_instrument_has_no_fan(loaded, gdp):
    impulse = shocks.build({"rsa": 1.0e9}, year=2026)
    with pytest.raises(fan.FanError, match=r"no macro path|no instrument"):
        fan.run(impulse, loaded, gdp_eur=gdp)


def test_a_missing_row_kills_the_fan_with_its_reason(gdp, tmp_path):
    empty = store.Store()
    with pytest.raises(fan.FanError, match="multiplier_by_instrument"):
        fan.run(shocks.build({"ir": -1.0e9}, year=2026), empty, gdp_eur=gdp)


def test_a_nonsense_gdp_is_refused(loaded):
    with pytest.raises(fan.FanError, match="GDP must be positive"):
        fan.run(shocks.build({"ir": -1.0e9}, year=2026), loaded, gdp_eur=0.0)


# --- the strip ----------------------------------------------------------------------


def test_the_strip_carries_everything_section_four_requires(loaded, gdp, composition):
    result = fan.run(shocks.build({"ir": -3.0e9}, year=2026), loaded,
                     gdp_eur=gdp, composition=composition)
    strip = result.assumptions
    assert strip.cycle_state == "normal"
    assert "Type I" in strip.design
    assert 0.0 < strip.leakage < 1.0
    assert strip.horizons == ("1", "2", "3")
    assert "rows" in strip.parameters_vintage
    assert strip.grade in {"in-support", "illustrative", "no-evidence"}
    assert strip.covered_share == 1.0
    assert "taux d'intérêt réels constants" in strip.simulation_conditions


def test_the_banner_no_longer_claims_a_factor(loaded, gdp):
    """D-057: "un facteur 3 à 5" was not a measurement and must not return."""
    banner = _run(loaded, gdp, {"ir": -3.0e9}).assumptions.banner
    assert "pas une prévision" in banner
    assert "3 à 5" not in banner and "facteur" not in banner


def test_an_oversized_reform_grades_illustrative(loaded, gdp):
    """Beyond one point of GDP the model is being extrapolated, not read."""
    modest = _run(loaded, gdp, {"ir": -3.0e9})
    huge = _run(loaded, gdp, {"ir": -60.0e9})
    assert modest.assumptions.grade == "in-support"
    assert huge.assumptions.grade == "illustrative"


# --- the API block ------------------------------------------------------------------


def _request(**knobs):
    import types

    from impots.api.schemas import ReformSpec

    return types.SimpleNamespace(reform=ReformSpec(**knobs), year=2024, macro=True)


class _Agg:
    def __init__(self, deltas, cost):
        self.deltas, self.reform_cost = deltas, cost


def test_the_api_block_carries_the_whole_strip():
    """§4 forbids the fan to render without it, so the schema requires it."""
    from impots.api import main

    block = main._macro(_request(csg_activite_imposable=0.08),
                        _Agg({"csg_imposable": -5.0e9}, -5.0e9))
    assert block.available
    strip = block.assumptions
    assert strip is not None
    for field in ("cycle_state", "design", "horizons", "parameters_vintage", "grade",
                  "covered_share", "simulation_conditions", "banner"):
        assert getattr(strip, field) not in (None, "", [])
    assert strip.leakage_applied is False
    assert strip.horizons == ["1", "2", "3"]


def test_the_api_block_reports_uncovered_instruments_with_reasons():
    from impots.api import main

    block = main._macro(_request(csg_activite_imposable=0.08),
                        _Agg({"csg_imposable": -5.0e9, "rsa": 1.0e9}, -4.0e9))
    assert "rsa" in block.uncovered
    assert "0,39" in block.uncovered["rsa"]
    assert block.assumptions.covered_share < 1.0


def test_a_reform_with_no_macro_path_is_unavailable_not_an_error():
    """Most reforms this repository can express have no multiplier. That is designed."""
    from impots.api import main

    block = main._macro(_request(csg_activite_imposable=0.08),
                        _Agg({"rsa": 1.0e9}, 1.0e9))
    assert block.available is False
    assert "multiplicateur publié" in block.unavailable_because
    assert "rsa" in block.uncovered


def test_an_allegement_reform_routes_to_the_targeted_variant_through_the_api():
    """The knobs reach the router, which is the only place the targeting is visible."""
    from impots.api import main

    uniform = main._macro(_request(csg_activite_imposable=0.08),
                          _Agg({"employer_contributions": -5.0e9}, -5.0e9))
    targeted = main._macro(_request(allegement_general_plafond=1.8),
                           _Agg({"employer_contributions": -5.0e9}, -5.0e9))
    assert uniform.assumptions.instruments == ["cotisations_employeurs"]
    assert targeted.assumptions.instruments == ["cotisations_employeurs_ciblees"]
    assert targeted.jobs["3"].p50 > uniform.jobs["3"].p50


def test_the_api_block_never_raises_on_a_missing_source(tmp_path, monkeypatch):
    """A checkout without the primary sources gets a reason, not a 500."""
    from impots.api import main
    from impots.macro import tes as tes_module

    monkeypatch.setattr(tes_module, "RAW", tmp_path)
    block = main._macro(_request(csg_activite_imposable=0.08),
                        _Agg({"csg_imposable": -5.0e9}, -5.0e9))
    assert block.available is False
    assert "indisponible" in block.unavailable_because
