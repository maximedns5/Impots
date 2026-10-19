"""Phase 9 M6 §7 — the indices (`predictif.indices`, D-223).

What is held here: the list is closed and an unknown index is refused by name; no index is
added to another, the two employments by their own reason; an index absent says why, and
one computed carries its values inside its θ box; the Mésange rows are hand-derived for a
permanent shock, the three fixed ones unmoved by θ and the jobs moved by it; the
behavioural ones run at θ with the box at their own rows' corners; the chain's interest is
the extra debt's; and the firm layer says it is not computed here.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from impots.behavioural import channels
from impots.behavioural.store import load
from impots.dette import reference, scenarios
from impots.dette.path import SHIPPED
from impots.macro import mesange
from impots.predictif import chaine, indices
from impots.predictif.indices import IndicesError
from impots.predictif.theta import Theta
from macro_cases import index_rows_store

STORE = load()


class Reform:
    def __init__(self, **knobs) -> None:
        self._knobs = knobs

    def model_dump(self, exclude_none: bool = True, **_) -> dict:
        return dict(self._knobs)


def _store():
    return index_rows_store()


GDP = 3_000e9
ONE_POINT_IR = {"impot_sur_le_revenu": 0.01 * GDP}


# --------------------------------------------------------------------------- #
# The closed list, and no sum
# --------------------------------------------------------------------------- #
def test_an_index_outside_the_list_is_refused_by_name() -> None:
    """GUARD. A misspelt key answered with an empty table would read as « nothing moves »."""
    with pytest.raises(IndicesError, match="emploi_total") as error:
        indices.select(["emploi_smic", "emploi_total"])
    assert "emploi_marchand" in str(error.value)
    assert [s.key for s in indices.select(["dette", "emploi_smic"])] == ["emploi_smic",
                                                                        "dette"]
    with pytest.raises(IndicesError, match="vide"):
        indices.select([])


def test_the_two_employments_do_not_add_up() -> None:
    """GUARD. C2 counts persons, Mésange full-time equivalents, and they overlap on the
    low wages: their sum would count the same jobs twice, in two units."""
    smic = indices.Index(spec=indices.KEYS["emploi_smic"], available=True,
                         values={"2026": 12_000.0})
    etp = indices.Index(spec=indices.KEYS["emploi_marchand"], available=True,
                        values={"1": 24.0})
    with pytest.raises(IndicesError, match=r"personnes.*équivalents temps plein"):
        smic + etp
    with pytest.raises(IndicesError, match="aucun indice ne s'additionne"):
        sum([smic, etp])
    deciles = indices.Index(spec=indices.KEYS["revenu_disponible_deciles"], available=True,
                            values={"D1": 100.0})
    income = indices.Index(spec=indices.KEYS["revenu_disponible_reel"], available=True,
                           values={"1": 1.7})
    with pytest.raises(IndicesError, match="deux fois le transfert"):
        deciles + income


def test_an_index_says_why_it_is_absent_and_stays_inside_its_box() -> None:
    spec = indices.KEYS["emploi_smic"]
    with pytest.raises(IndicesError, match="sans raison"):
        indices.Index(spec=spec, available=False)
    with pytest.raises(IndicesError, match="sans valeur"):
        indices.Index(spec=spec, available=True)
    with pytest.raises(IndicesError, match="hors de sa boîte"):
        indices.Index(spec=spec, available=True, values={"2026": 5.0},
                      box={"2026": (6.0, 9.0)})


def test_an_index_off_the_catalogue_or_boxed_on_other_keys_is_refused() -> None:
    """D-229. A spec rebuilt by hand under a catalogue key would carry another unit under
    the catalogue's name; a box on other keys than the values bounds nothing it shows."""
    spec = indices.KEYS["emploi_smic"]
    for stray in (dataclasses.replace(spec, unit="euros"),
                  dataclasses.replace(spec, key="emploi_total")):
        with pytest.raises(IndicesError, match="hors du catalogue"):
            indices.Index(spec=stray, available=False, reason="test")
    with pytest.raises(IndicesError, match="d'autres clés"):
        indices.Index(spec=spec, available=True, values={"2026": 5.0},
                      box={"2027": (4.0, 6.0)})


# --------------------------------------------------------------------------- #
# Mésange, for a permanent shock
# --------------------------------------------------------------------------- #
def test_a_shock_against_no_gdp_or_a_null_multiplier_is_refused_by_name() -> None:
    """D-229. Points of a GDP of zero, and a ratio to a multiplier of zero, would each
    end in a bare division error, or in an index scaled by nothing."""
    with pytest.raises(IndicesError, match="PIB doit être positif"):
        indices.mesange_fixed(indices.KEYS["revenu_disponible_reel"], ONE_POINT_IR,
                              gdp_eur=0.0, store=_store())
    store = _store()
    table = store.tables["multiplier_by_instrument"]
    row = table.values["impot_sur_le_revenu"]
    store.tables["multiplier_by_instrument"] = dataclasses.replace(
        table, values={**table.values, "impot_sur_le_revenu": (0.0, *row[1:])})
    with pytest.raises(IndicesError, match="aucun multiplicateur lisible"):
        indices.mesange_scaled(indices.KEYS["consommation"], ONE_POINT_IR, gdp_eur=GDP,
                               store=store, theta=0.5)


def test_the_fixed_income_row_is_the_row_times_the_points() -> None:
    """Derived by hand: a one-point income-tax cut is one point of the variant, so the
    index is the row itself — 1,7 · 1,82 · 1,92 %. Half a point of income tax beside the
    targeted variant gives half the row, and the targeted variant, which prints no such
    row (encadré 14), is listed rather than borrowed. A VAT cut of 1,18 points gross is
    one point of its variant (folio 112)."""
    store = _store()
    spec = indices.KEYS["revenu_disponible_reel"]
    result = indices.mesange_fixed(spec, ONE_POINT_IR, gdp_eur=GDP, store=store)
    assert result.values == pytest.approx({"1": 1.7, "2": 1.82, "3": 1.92})
    assert result.box is None and indices.FIXED in result.conventions
    half = indices.mesange_fixed(spec, {"impot_sur_le_revenu": 0.005 * GDP,
                                        "cotisations_employeurs_ciblees": 0.01 * GDP},
                                 gdp_eur=GDP, store=store)
    assert half.values == pytest.approx({"1": 0.85, "2": 0.91, "3": 0.96})
    assert set(half.uncovered) == {"cotisations_employeurs_ciblees"}
    store.tables["real_income_by_instrument"].values["tva"] = (1.1, 1.01, 1.22, 0, 0, 0)
    vat = indices.mesange_fixed(spec, {"tva": 0.0118 * GDP}, gdp_eur=GDP, store=store)
    assert vat.values["1"] == pytest.approx(1.1)


def test_theta_moves_jobs_consumption_and_investment_and_not_income() -> None:
    """GUARD. At θ = 1/2 the multiplier is Mésange's centre, so each scaled index is the
    row itself — jobs 24 · 109 · 174 thousand, consumption 0,81 · 1,66 · 1,9 %. θ moves
    the three; the income row, which holds the shock, is the same at θ = 0 and 1."""
    store = _store()
    printed = {"emploi_marchand": (24.0, 109.0, 174.0),
               "consommation": (0.81, 1.66, 1.9),
               "investissement_entreprises": (0.81, 2.01, 1.98)}
    for key, row in printed.items():
        at = {t: indices.mesange_scaled(indices.KEYS[key], ONE_POINT_IR, gdp_eur=GDP,
                                        store=store, theta=t) for t in (0.0, 0.5, 1.0)}
        assert at[0.5].values == pytest.approx(dict(zip(("1", "2", "3"), row,
                                                         strict=True))), key
        assert at[0.0].values["3"] < at[0.5].values["3"] < at[1.0].values["3"], key
        assert at[0.5].box["3"] == pytest.approx((at[0.0].values["3"],
                                                  at[1.0].values["3"])), key
    computed = {t: indices.compute(
        [indices.KEYS["revenu_disponible_reel"]], trajectory=None, deciles_rows=None,
        impulse=ONE_POINT_IR, gdp_eur=GDP, macro_store=store, theta=Theta(common=t),
        store=STORE, reform=None, mechanical=0.0, inputs=None, year=2026)
        for t in (0.0, 1.0)}
    assert computed[0.0][0].values == computed[1.0][0].values
    without = indices.mesange_scaled(indices.KEYS["consommation"], ONE_POINT_IR,
                                     gdp_eur=GDP, store=store, theta=None)
    assert not without.available and without.reason == indices.NO_MACRO_THETA


def test_the_jobs_index_is_the_macro_layers_own_jobs_at_theta() -> None:
    """D-042: a read-back against an independent construction. `predictif.macro.at_theta`
    computes jobs at θ its own way; the index must land on the same figures."""
    from impots.macro.shocks import Impulse
    from impots.predictif import macro

    store = _store()
    impulse = {"impot_sur_le_revenu": 0.004 * GDP,
               "cotisations_employeurs_ciblees": 0.002 * GDP}
    store.tables["multiplier_by_instrument"].values["cotisations_employeurs_ciblees"] = (
        0.21, 0.58, 0.80, 1.05, 1.43, 1.84)
    for t in (0.0, 0.3, 1.0):
        index = indices.mesange_scaled(indices.KEYS["emploi_marchand"], impulse,
                                       gdp_eur=GDP, store=store, theta=t)
        direct = macro.at_theta(Impulse(year=2026, by_instrument=impulse), store,
                                gdp_eur=GDP, theta=t)
        assert index.values == pytest.approx({h: jobs for h, (_, jobs) in direct.items()})


def test_the_three_rows_are_the_ones_the_pages_print() -> None:
    """The store against the PDF, on figures the adversarial pass read off the rendered
    pages: the income tax (folio 117), VAT turned to a cut (folio 112), employer
    contributions (folio 107); and the targeted variant without the rows (encadré 14)."""
    pytest.importorskip("pypdf")
    if not (mesange.RAW / mesange.SOURCE_FILE).exists():
        pytest.skip("data/raw/ n'a pas le document Mésange")
    from impots.macro import store as macro_store

    tables = macro_store.load().tables
    expected = {
        "consumption_by_instrument": {"impot_sur_le_revenu": (0.81, 1.66, 1.9),
                                      "tva": (0.58, 1.04, 1.14),
                                      "cotisations_employeurs": (0.3, 0.73, 0.92)},
        "investment_by_instrument": {"impot_sur_le_revenu": (0.81, 2.01, 1.98),
                                     "tva": (0.62, 1.77, 1.87),
                                     "cotisations_employeurs": (0.41, 1.33, 1.82)},
        "real_income_by_instrument": {"impot_sur_le_revenu": (1.7, 1.82, 1.92),
                                      "tva": (1.1, 1.01, 1.22),
                                      "cotisations_employeurs": (0.4, 0.65, 0.85)},
    }
    for key, rows in expected.items():
        table = tables[key]
        assert table.usable_horizons == ("1", "2", "3"), key
        assert "cotisations_employeurs_ciblees" not in table.values, key
        for instrument, values in rows.items():
            assert tuple(table.at(instrument, h) for h in ("1", "2", "3")) == values


# --------------------------------------------------------------------------- #
# Behaviour, at θ
# --------------------------------------------------------------------------- #
EMPLOYER = Reform(allegement_general_taux=0.30)
EARNERS = {"smic_multiple": np.array([1.0, 1.3, 1.8, 2.5]),
           "relative_cost_change": np.array([-0.02, -0.015, -0.01, -0.005]),
           "earner_weights": np.array([100.0, 80.0, 60.0, 40.0])}


def test_jobs_near_the_smic_run_at_theta_with_the_box_at_their_own_corners() -> None:
    """At θ the channel draws once, at the row's value; the box is the channel at θ = 0
    and 1 of its own row. θ = 1 is the strongest response, the LOW end of the
    elasticity (−0,52), so it gives the most jobs."""
    spec = indices.KEYS["emploi_smic"]
    at = {t: indices.behaviour(spec, theta=Theta(common=t), store=STORE, reform=EMPLOYER,
                               mechanical=-1e9, inputs=EARNERS, year=2026)
          for t in (0.0, 0.5, 1.0)}
    low, high = at[0.5].box["2026"]
    assert (low, high) == pytest.approx((at[0.0].values["2026"], at[1.0].values["2026"]))
    assert low < at[0.5].values["2026"] < high
    direct = channels.employment_at_the_smic(
        STORE, EMPLOYER, smic_multiple=EARNERS["smic_multiple"],
        relative_cost_change=EARNERS["relative_cost_change"],
        weights=EARNERS["earner_weights"], draws=1, rng=np.random.default_rng(0))
    assert direct.draws is not None
    quiet = indices.behaviour(spec, theta=Theta(common=0.5), store=STORE,
                              reform=Reform(ir_bareme=[]), mechanical=-1e9,
                              inputs=EARNERS, year=2026)
    assert not quiet.available
    unasked = indices.behaviour(spec, theta=Theta(common=0.5), store=STORE,
                                reform=EMPLOYER, mechanical=-1e9, inputs=None, year=2026)
    assert unasked.reason == indices.NO_BEHAVIOUR


# --------------------------------------------------------------------------- #
# The chain, the mechanical deciles and the firm layer
# --------------------------------------------------------------------------- #
START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = scenarios.GrowthScenario("Croissance réelle 1 %, prix 2 %", 0.01, 0.02)
HELD = scenarios.RateScenario("Taux implicite tenu à son niveau de 2025", "implicite_tenu")


def test_the_interest_is_the_extra_debts_own() -> None:
    """Derived by hand: the extra debt of year t − 1 at the marginal rate, over the year's
    growth — ΔD_{t−1} × m / (1 + g), in points of the reference's GDP; nothing the first
    year, when there is no extra debt yet."""
    result = chaine.run(START, horizon=4, costs=chaine.ReformCosts(
        by_year={2026: 6e9}, carry=chaine.CARRY), spending=SHIPPED["gele_en_volume"],
        growth=GROWTH, rate=HELD, theta=Theta(common=0.5))
    m, g = START.implicit_rate, GROWTH.nominal
    assert result.delta_interest[0] == 0.0
    assert list(result.delta_interest[1:]) == pytest.approx(
        [d * m / (1 + g) for d in result.delta[:-1]])
    index = indices.chain(indices.KEYS["charge_interets"], result)
    assert list(index.values) == ["2026", "2027", "2028", "2029"]


def test_the_firm_layer_is_listed_and_not_computed_here() -> None:
    computed = indices.compute(
        [s for s in indices.CATALOGUE if s.stage == indices.FIRMES], trajectory=None,
        deciles_rows=None, impulse=None, gdp_eur=GDP, macro_store=None,
        theta=Theta(common=0.5), store=STORE, reform=None, mechanical=0.0, inputs=None,
        year=2026)
    assert [i.spec.key for i in computed] == ["charge_fiscale_production",
                                              "creations_societes", "depense_rd"]
    assert all(not i.available and i.reason == indices.FIRM_LAYER for i in computed)


def test_every_index_has_a_unit_a_stage_and_a_source() -> None:
    assert len(indices.KEYS) == len(indices.CATALOGUE)
    for spec in indices.CATALOGUE:
        assert spec.unit and spec.source and spec.stage in (
            indices.MECANIQUE, indices.COMPORTEMENT, indices.MACRO, indices.CHAINE,
            indices.FIRMES), spec.key
        assert all(k in STORE or k == indices.MACRO_ROW for k in spec.theta), spec.key
    assert set(indices.MESANGE_FIXED.values()) == {"real_income_by_instrument"}
    assert set(indices.MESANGE_SCALED.values()) == {
        "consumption_by_instrument", "investment_by_instrument",
        "employment_by_instrument"}
    assert mesange.ROWS["consommation"] == "Consommation des ménages"
