"""Phase 9 M2 — the coefficients θ (PHASE9_SPEC §2, D-217).

What is held here: θ places each open row INSIDE its published range, through the
published centre, in the direction the row declares; nothing outside [0, 1] is clipped
into it; the pinned store runs the Phase 3 channels unchanged; the Monte Carlo band does
not move by a digit; and every channel is monotone in its θ, which is what lets the θ box
be read at its corners.
"""

from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import numpy as np
import pytest

from impots.behavioural import band, channels
from impots.behavioural.store import load
from impots.predictif import comportement, indices, theta
from impots.predictif.theta import Theta, ThetaError

STORE = load()
OPEN = sorted(k for k, p in STORE.parameters.items() if p.is_open)

#: Guard 6. `band.compute` on the shipped store and the synthetic population below, at the
#: band's own seed, as measured on main BEFORE the pinned view existed. To the last digit.
GOLDEN = (-5002522497.792298, -5002009033.931921, -5001562912.810563, "in-support")


class Reform:
    """A reform reduced to the knobs it sets, as `channels._knobs` reads them."""

    def __init__(self, **knobs) -> None:
        self._knobs = knobs
        for name, value in knobs.items():
            setattr(self, name, value)

    def model_dump(self, exclude_none: bool = True, **_) -> dict:
        return dict(self._knobs)


IR = Reform(ir_bareme=[{"threshold": 0, "rate": 0.0}])


def _households() -> dict:
    rng = np.random.default_rng(7)
    n = 400
    base = rng.uniform(10_000, 120_000, n)
    weights = rng.uniform(50, 150, n)
    emtr0 = rng.uniform(0.2, 0.5, n)
    return {"taxable_base": base, "weights": weights, "emtr_baseline": emtr0,
            "emtr_reform": emtr0 + 0.02, "top_decile": base > np.quantile(base, 0.9)}


# --------------------------------------------------------------------------- #
# §2.1 — the mapping
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("value", [-0.1, 1.2, float("nan")])
def test_a_theta_outside_the_unit_interval_is_refused_not_clipped(value: float) -> None:
    """GUARD 3. θ = 1,2 would place an effect beyond what anyone published; clipping it to
    1 would answer a question the user did not ask."""
    with pytest.raises(ThetaError, match="hors de"):
        theta.value_at(STORE["eti_all"], value)
    with pytest.raises(ThetaError, match="hors de"):
        Theta(common=value)
    with pytest.raises(ThetaError, match="hors de"):
        Theta(rows={"eti_all": value})
    with pytest.raises(ThetaError, match="hors de"):
        theta.multiplier_at(0.41, 0.66, value)


@pytest.mark.parametrize("key", OPEN)
def test_one_half_returns_the_published_centre_of_every_open_row(key: str) -> None:
    """GUARD 5. The report's linear form would put `eti_all` at 0,015 — a value no
    specification of the paper reports — where the centre is 0,02."""
    assert theta.value_at(STORE[key], 0.5) == STORE[key].central


@pytest.mark.parametrize("key", OPEN)
def test_the_ends_are_the_published_bounds_in_the_declared_direction(key: str) -> None:
    parameter = STORE[key]
    strong, weak = ((parameter.high, parameter.low) if parameter.theta_one == "high"
                    else (parameter.low, parameter.high))
    assert theta.value_at(parameter, 1.0) == pytest.approx(strong, abs=1e-15)
    assert theta.value_at(parameter, 0.0) == pytest.approx(weak, abs=1e-15)


def test_theta_one_is_the_strongest_response_even_when_it_is_the_low_end() -> None:
    """The SMIC elasticity runs −0,52 to −0,31: its strongest response is the LOW end,
    which the sign alone would have put at θ = 0."""
    smic = STORE["employment_elasticity_smic"]
    assert theta.value_at(smic, 1.0) == pytest.approx(-0.52)
    assert theta.value_at(smic, 0.0) == pytest.approx(-0.31)
    assert theta.value_at(STORE["eti_top_decile"], 1.0) == pytest.approx(0.50)


def test_an_open_row_without_its_direction_cannot_be_placed() -> None:
    undeclared = dataclasses.replace(STORE["eti_all"], theta_one=None)
    with pytest.raises(ThetaError, match="non déclaré"):
        theta.value_at(undeclared, 0.5)


def test_a_fixed_row_keeps_its_value_at_every_theta() -> None:
    fixed = STORE["employment_fadeout_smic_multiple"]
    assert not fixed.is_open
    assert {theta.value_at(fixed, t) for t in (0.0, 0.3, 1.0)} == {fixed.central}


def test_the_macro_multiplier_moves_by_one_published_sd_and_not_the_draw_width() -> None:
    """Centre ∓ ONE standard deviation: the triangular draw's ± sd·√6 is a shape
    convention (D-059), not something a study published."""
    assert theta.multiplier_at(0.41, 0.66, 0.5) == 0.41
    assert theta.multiplier_at(0.41, 0.66, 1.0) == pytest.approx(1.07)
    assert theta.multiplier_at(0.41, 0.66, 0.0) == pytest.approx(-0.25)
    with pytest.raises(ThetaError, match="dispersion"):
        theta.multiplier_at(0.41, 0.0, 0.5)


# --------------------------------------------------------------------------- #
# §2.3 — the object: no default, no unknown row
# --------------------------------------------------------------------------- #
def test_no_theta_at_all_is_refused_rather_than_given_one_half() -> None:
    with pytest.raises(ThetaError, match="Aucun défaut"):
        Theta()


def test_a_row_with_neither_its_own_theta_nor_a_common_one_is_refused() -> None:
    partial = Theta(rows={"eti_all": 0.3})
    assert partial.for_row("eti_all") == 0.3
    with pytest.raises(ThetaError, match="refusé"):
        partial.for_row("eti_top_decile")


@pytest.mark.parametrize("key", ["eti_al", "employment_fadeout_smic_multiple"])
def test_a_theta_for_an_unknown_or_fixed_row_is_refused_by_name(key: str) -> None:
    """A typo would otherwise apply the common θ in silence."""
    with pytest.raises(ThetaError, match=key):
        Theta(rows={key: 0.2}, common=0.5).check_known(STORE)


def test_the_table_lists_every_open_row_even_when_set_together() -> None:
    table = Theta(rows={"eti_all": 0.2}, common=0.7).table(STORE)
    assert sorted(table) == OPEN
    assert table["eti_all"] == 0.2 and table["eti_top_decile"] == 0.7


def test_the_corners_move_only_the_rows_named_and_keep_the_rest() -> None:
    base = Theta(rows={"passthrough_unlinked": 0.3}, common=0.6)
    found = theta.corners(["eti_top_decile", "eti_all"], base)
    assert len(found) == 4
    assert {(c.for_row("eti_all"), c.for_row("eti_top_decile")) for c in found} == {
        (0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)}
    assert all(c.for_row("passthrough_unlinked") == 0.3 for c in found)
    assert all(c.for_row("wealth_tax_rate_elasticity") == 0.6 for c in found)


# --------------------------------------------------------------------------- #
# The pinned view, and the band it must not move
# --------------------------------------------------------------------------- #
def test_the_pinned_store_draws_the_value_at_theta_and_leaves_the_store_alone() -> None:
    store = load()
    at_one = theta.pinned(store, Theta(common=1.0))
    rng = np.random.default_rng(0)
    for key in OPEN:
        expected = theta.value_at(store[key], 1.0)
        assert np.array_equal(at_one[key].draw(rng, 5), np.full(5, expected))
    assert store["eti_all"].low == 0.01 and store["eti_all"].high == 0.02


def test_the_monte_carlo_band_does_not_move_by_a_digit() -> None:
    """GUARD 6. The pinned view is a new store, never an edit of the one the band draws
    from: the band is computed AFTER a pinning, on the original, and must match the
    figure measured before the view existed."""
    store = load()
    theta.pinned(store, Theta(common=1.0))
    result = band.compute(mechanical=-5e9, reform=IR, store=store, **_households())
    assert (result.band.p10, result.band.p50, result.band.p90, result.grade) == GOLDEN


# --------------------------------------------------------------------------- #
# GUARD 7 — every channel monotone in its θ, on a grid of eleven points
# --------------------------------------------------------------------------- #
GRID = np.linspace(0.0, 1.0, 11)
EMPLOYER = Reform(allegement_general_taux=0.30)
EARNERS = {"smic_multiple": np.array([1.0, 1.3, 1.8, 2.5]),
           "relative_cost_change": np.array([-0.02, -0.015, -0.01, -0.005]),
           "weights": np.array([100.0, 80.0, 60.0, 40.0])}

#: One earner per labour-supply group, a 2 % fall in the net wage (a CSG rise).
LABOUR = {"labour_group": np.array(sorted(channels.LABOUR_GROUPS)),
          "labour_earnings": np.array([30_000.0, 25_000.0, 35_000.0, 20_000.0]),
          "labour_delta_log_net": np.full(4, -0.02),
          "labour_weights": np.full(4, 100.0),
          "labour_emtr": np.array([0.40, 0.35, 0.45, 0.30])}
CSG = Reform(csg_activite_deductible=0.088)

def _is_growth(store, reform, *, draws, rng, rate_change_points):
    """The IS's GDP index read as a channel (D-246): its row has no channel, the index
    is what reads it, and the guard holds it there."""
    index = indices.is_growth(indices.KEYS["pib_is"], theta=Theta(common=0.5), store=store,
                              rate_change_points=rate_change_points, years=[2026])
    return SimpleNamespace(applies=index.available, message=index.reason,
                           draws=[index.values.get("2026", 0.0)] * draws)


#: Row → (channel, reform, inputs, index of the row's draw in the channel's output).
CASES = {
    "eti_all": (channels.elasticity_of_taxable_income, IR, _households(), 0),
    "eti_top_decile": (channels.elasticity_of_taxable_income, IR, _households(), 0),
    "employment_elasticity_smic": (channels.employment_at_the_smic, EMPLOYER, EARNERS, 0),
    "passthrough_unlinked": (channels.contribution_incidence, EMPLOYER,
                             {"contribution_delta": -2e9}, 0),
    "passthrough_benefit_linked": (channels.contribution_incidence, EMPLOYER,
                                   {"contribution_delta": -2e9}, 1),
    "production_tax_investment": (channels.production_tax_investment,
                                  Reform(cvae_taux_max=0.0),
                                  {"production_tax_baseline": 10e9,
                                   "production_tax_reform": 8e9}, 0),
    "wealth_tax_rate_elasticity": (channels.wealth_rate_response,
                                   Reform(ifi_bareme=[]),
                                   {"wealth_base_eur": 400e9, "marginal_rate_baseline": 0.01,
                                    "marginal_rate_reform": 0.012}, 0),
    "wealth_disclosure_growth_effect_pp": (channels.disclosure_response,
                                           Reform(ifi_obligations_declaratives="renforcees"),
                                           {"wealth_base_eur": 400e9}, 0),
    **{key: (channels.labour_supply, CSG, LABOUR, 0) for key in channels.C7_KEYS},
    "firm_creation_profit_tax": (channels.firm_creations, Reform(is_taux_normal=0.27),
                                 {"is_rate_change_points": 2.0}, 0),
    "rd_cir_multiplier": (channels.rd_response, Reform(cir_taux=0.25),
                          {"cir_margins": ((-1_009.9e6, 0.25), (-105e6, 0.05))}, 0),
    "is_croissance_pib": (_is_growth, None, {"rate_change_points": -1.0}, 0),
    **{key: (channels.dividend_response, Reform(pfu_taux=0.118),
             {"dividend_base_eur": 50e9, "levy_rate_baseline": 0.30,
              "levy_rate_reform": 0.29}, 0)
       for key in channels.C10_KEYS},
    # D-256: a 1 bn cut that C2 reads as 10 000 jobs, 12 %, against the Trésor-Éco's 60 %.
    "autofinancement_poids_tresor_eco": (channels.targeted_self_financing, EMPLOYER,
                                         {"jobs": np.full(2, 10_000.0),
                                          "contribution_delta": -1e9,
                                          "targets_low_wages": True}, 0),
}


def test_every_open_row_has_a_monotonicity_case() -> None:
    assert sorted(CASES) == OPEN


@pytest.mark.parametrize("key", OPEN)
def test_each_channel_is_monotone_in_its_theta(key: str) -> None:
    """If a channel were not, the box's bounds could not be read at its corners (§3.5),
    and this test says which one."""
    channel, reform, inputs, index = CASES[key]
    effects = []
    for t in GRID:
        store = theta.pinned(STORE, Theta(rows={key: float(t)}, common=0.5))
        result = channel(store, reform, draws=2, rng=np.random.default_rng(0), **inputs)
        assert result.applies, result.message
        effects.append(float(result.draws[index]))
    steps = np.diff(effects)
    assert np.all(steps >= -1e-9) or np.all(steps <= 1e-9), (key, effects)
    assert effects[0] != effects[-1], f"{key} ne bouge pas avec θ"


# --------------------------------------------------------------------------- #
# The receipts at θ and the box (§3.5)
# --------------------------------------------------------------------------- #
def test_the_box_is_found_at_the_known_corners_of_a_hand_built_case() -> None:
    """C1 is linear in both elasticities and the rates rise, so the receipts fall most at
    θ = 1 on both rows and least at θ = 0: the bounds are those two corners, by hand."""
    households = _households()
    net0 = np.log(1.0 - households["emtr_baseline"])
    net1 = np.log(1.0 - households["emtr_reform"])
    exposure = (households["weights"] * households["taxable_base"] * (net1 - net0)
                * households["emtr_reform"])
    top = households["top_decile"]
    lower, upper = float(exposure[~top].sum()), float(exposure[top].sum())
    at = comportement.evaluate(Theta(common=0.5), mechanical=-5e9, reform=IR,
                               store=STORE, **households)
    assert at.claimed == ("eti_all", "eti_top_decile")
    assert at.box[0] == pytest.approx(-5e9 + 0.02 * lower + 0.50 * upper, rel=1e-12)
    assert at.box[1] == pytest.approx(-5e9 + 0.01 * lower + 0.15 * upper, rel=1e-12)
    assert at.receipts == pytest.approx(-5e9 + 0.02 * lower + 0.31 * upper, rel=1e-12)


def test_receipts_outside_their_box_are_refused_rather_than_drawn(monkeypatch) -> None:
    """The cheap monotonicity check that runs on every request: a channel that peaked
    inside the box would put the receipts at θ above every corner."""
    def peaked(at, **_):
        inside = all(at.for_row(k) not in (0.0, 1.0) for k in ("eti_all", "eti_top_decile"))
        return (10.0 if inside else 0.0), "in-support"

    monkeypatch.setattr(comportement, "receipts_at", peaked)
    with pytest.raises(ThetaError, match="monotone"):
        comportement.evaluate(Theta(common=0.5), mechanical=0.0, reform=IR, store=STORE,
                              **_households())


def test_a_reform_no_open_row_claims_has_a_box_of_its_mechanical_figure() -> None:
    at = comportement.evaluate(Theta(common=0.5), mechanical=-1e9,
                               reform=Reform(abattement_pensions_plafond=0.0), store=STORE)
    assert at.claimed == () and at.box == (-1e9, -1e9) and at.receipts == -1e9


# --------------------------------------------------------------------------- #
# The macro response at θ (needs the primary sources, like the fan's own tests)
# --------------------------------------------------------------------------- #
def _macro():
    pytest.importorskip("pypdf")
    from impots.macro import imk, mesange, shocks
    from impots.macro import store as macro_store

    if not ((mesange.RAW / mesange.SOURCE_FILE).exists()
            and (imk.RAW / imk.DOCUMENTS["wp117"]).exists()):
        pytest.skip("data/raw/ has no Mésange or IMK document — primary sources are not "
                    "committed")
    return SimpleNamespace(store=macro_store.load(), shocks=shocks,
                           ex_ante=lambda i: mesange.VARIANTS[i].ex_ante_points)


def test_the_macro_response_at_theta_sits_inside_the_fan() -> None:
    from impots.macro import fan
    from impots.predictif import macro

    loaded = _macro()
    impulse = loaded.shocks.build({"csg_imposable": -5.0e9}, year=2026)
    drawn = fan.run(impulse, loaded.store, gdp_eur=2.9e12)
    low, mid, high = (macro.at_theta(impulse, loaded.store, gdp_eur=2.9e12, theta=t)
                      for t in (0.0, 0.5, 1.0))
    centre = loaded.store.tables["multiplier_by_instrument"].at("csg", "1")
    assert mid["1"][0] == pytest.approx(centre * 5e9 / loaded.ex_ante("csg"))
    for horizon, quantiles in drawn.gdp_eur.items():
        assert quantiles.p10 < low[horizon][0] < mid[horizon][0] < high[horizon][0]
        assert high[horizon][0] < quantiles.p90


def test_the_macro_response_refuses_no_instrument_no_gdp_and_no_family(
        monkeypatch) -> None:
    """D-229. An impulse with no instrument would answer zero GDP and zero jobs — a
    measured nothing where nothing was measured; a GDP of zero would end in a bare
    division; and a variant without a dispersion family would have no range for θ."""
    from impots.macro.fan import MULTIPLIER_FAMILY, FanError
    from impots.macro.shocks import Impulse
    from impots.predictif import macro
    from macro_cases import index_rows_store

    store = index_rows_store()
    with pytest.raises(FanError, match="aucun instrument"):
        macro.at_theta(Impulse(year=2026, by_instrument={}), store, gdp_eur=3e12,
                       theta=0.5)
    income_tax = Impulse(year=2026, by_instrument={"impot_sur_le_revenu": 5e9})
    with pytest.raises(FanError, match="PIB doit être positif"):
        macro.at_theta(income_tax, store, gdp_eur=0.0, theta=0.5)
    monkeypatch.delitem(MULTIPLIER_FAMILY, "impot_sur_le_revenu")
    with pytest.raises(FanError, match="aucune famille"):
        macro.at_theta(income_tax, store, gdp_eur=3e12, theta=0.5)
