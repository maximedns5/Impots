"""But 22, chantier C — the company-creations channel in the debt (`predictif.creations`).

The pure function first: symmetric, zero without a levy on firms or capital, monotone in
its θ, of the order of magnitude the research note derives by hand. Then the chain and
the annual report, on the synthetic passes of `test_rejouer`: the debt without the
channel is the debt of today, the replay reads the channel as the chain does, and no
report reads it before its preregistered D-entry.
"""

from __future__ import annotations

import json
from itertools import pairwise

import numpy as np
import polars as pl
import pytest

from exploration_cases import households
from impots import service
from impots.dette.path import DebtError
from impots.predictif import annuel, creations, rejouer
from impots.predictif.exploration import Priced
from impots.predictif.theta import CREATIONS_ROW, MACRO_ROW, Theta
from macro_cases import synthetic_macro_store
from test_rejouer import FROZEN, GROWTH, HELD, IR, START, UPRATING, YEARS, _cost

PARAMS = creations.charger()
GDP = [3_000e9 * 1.0302 ** k for k in range(10)]


def _effet(variation: float, c: float = 0.5, **options):
    return creations.effet([variation * 1.0302 ** k for k in range(10)], GDP, YEARS, c=c,
                           params=PARAMS, receipts_ratio=0.52, **options)


# --------------------------------------------------------------------------- #
# the pure channel
# --------------------------------------------------------------------------- #
def test_a_rise_and_a_cut_of_the_same_size_give_opposite_effects() -> None:
    cut, rise = _effet(-10e9), _effet(+10e9)
    assert np.allclose(cut.pib, -np.array(rise.pib), rtol=0, atol=1e-15)
    assert np.allclose(cut.recettes, -np.array(rise.recettes), rtol=0, atol=1e-15)
    assert all(g > 0 for g in cut.pib) and all(g < 0 for g in rise.pib)


def test_the_channel_reads_the_levies_on_firms_and_capital_only() -> None:
    """No levy on firms or capital: zero, whatever else the reform moves. The employer
    contributions, already in Mésange's loop, and the CDHR are not read."""
    household = {"ir": -30e9, "csg_deductible": 4e9, "employer_contributions": -8e9,
                 "cdhr": -1e9, "tva_menages": 2e9}
    assert creations.prelevements(household, PARAMS) == 0.0
    zero = _effet(0.0)
    assert set(zero.pib) == {0.0} and set(zero.recettes) == {0.0}
    both = {"impot_societes": -2e9, "cvae": -1e9, "pfu": 0.5e9, **household}
    assert creations.prelevements(both, PARAMS) == pytest.approx(-2.5e9)


def test_the_effect_is_monotone_in_its_theta_and_off_at_zero() -> None:
    thetas = np.linspace(0.0, 1.0, 11)
    cs = [creations.productivite_a(t, PARAMS) for t in thetas]
    assert cs[0] == 0.0 and cs[5] == PARAMS.productivite.centre and cs[-1] == 1.0
    assert all(b >= a for a, b in pairwise(cs))
    last = [_effet(-10e9, c=c).pib[-1] for c in cs]
    assert last[0] == 0.0
    assert all(b > a for a, b in pairwise(last))
    with pytest.raises(creations.CreationsError, match="refusé plutôt qu'écrêté"):
        creations.productivite_a(1.2, PARAMS)


def test_the_order_of_magnitude_of_a_ten_billion_cut_of_the_is() -> None:
    """The research note, by hand: 10 Md€ over b Y = 0,092 × 3 000 Md€ is 3,62 points of
    apparent rate, 0,72 point of entry rate; at c = ½ the GDP gap is about 0,05 % in 2030
    and 0,10 % in 2035, and the receipts about 2 Md€ in 2035."""
    cut = _effet(-10e9)
    assert cut.taux_apparent[0] == pytest.approx(-100 * 10e9 / (0.092 * 3_000e9))
    assert cut.taux_entree[0] == pytest.approx(0.20 * 3.6232, rel=1e-4)
    # Cohort sum at 2035, by hand: Σ_k 0,9^k min(1, (k+1)/5) for k = 0..9.
    weights = sum(0.9 ** k * min(1.0, (k + 1) / 5) for k in range(10))
    assert cut.pib[-1] == pytest.approx(cut.taux_entree[0] / 100 * weights * 0.10 * 0.5
                                        * 0.60, rel=1e-9)
    assert 0.0004 < cut.pib[4] < 0.0006 and 0.0009 < cut.pib[-1] < 0.0012
    assert 1.5e9 < cut.recettes[-1] * GDP[-1] < 2.5e9
    # The research's sensitivity on ε moves it, its centre is the headline.
    assert _effet(-10e9, elasticite=0.356).pib[-1] > cut.pib[-1] > _effet(
        -10e9, elasticite=0.043).pib[-1]


def test_the_declared_file_names_its_sources_and_no_report_reads_it_before_its_entry() -> None:
    assert PARAMS.elasticite == creations.Plage(centre=0.20, bas=0.043, haut=0.356)
    assert (PARAMS.productivite.bas, PARAMS.productivite.haut) == (0.0, 1.0)
    assert "employer_contributions" not in PARAMS.instruments
    assert creations.depuis(creations.instantane(PARAMS)) == PARAMS
    text = creations.FICHIER.read_text(encoding="utf-8")
    assert "Da Rin, Di Giacomo et Sembenelli" in text and "tableau 4 p. 40" in text
    if PARAMS.preenregistrement is None:
        with pytest.raises(creations.CreationsError, match="D-entrée préenregistrée"):
            creations.charger(exiger_entree=True)


# --------------------------------------------------------------------------- #
# the chain and the report
# --------------------------------------------------------------------------- #
def _price(levies: dict[str, float]):
    def price(year: int, view: str) -> Priced:
        cost = _cost(year, view)
        return Priced(cost=cost, inputs=households(),
                      impulse={"impot_sur_le_revenu": -cost, "csg": -0.25 * cost},
                      prelevements={k: v * (1.0 if view == "vieillie" else 0.92)
                                    for k, v in levies.items()})
    return price


def _build(theta: Theta, levies: dict[str, float], *, channel: bool, persistence="lue"):
    prices = annuel.price_years(YEARS, _price(levies), basis_for=lambda y: "legislated")
    return annuel.build(START, prices, scenario="baisse", titre="Baisse", source="test",
                        reference="reconduit", computed="2026-11-13", spending=FROZEN,
                        growth=GROWTH, rate=HELD, theta=theta, uprating=UPRATING,
                        uprating_note="", reform=IR, behavioural=True, macro=True,
                        persistence=persistence, macro_store=synthetic_macro_store(),
                        creations=PARAMS if channel else None)


CUT = {"impot_societes": -8e9, "cvae": -2e9}
HALF = Theta(common=0.5)


def test_the_debt_without_the_channel_is_the_debt_of_today() -> None:
    """Same passes, same code otherwise: the report that reads the channel carries, beside
    its debt, the very debt the report without it publishes."""
    today = _build(HALF, CUT, channel=False)
    read = _build(HALF, CUT, channel=True)
    for view in ("aged", "frozen"):
        before, after = getattr(today, view), getattr(read, view)
        assert after.delta_sans_creations == pytest.approx(before.delta, abs=1e-15)
        # A cut of the IS makes companies, whose receipts lower the debt.
        assert after.delta[-1] < before.delta[-1]
    payload = json.loads(json.dumps(read.payload()))
    assert payload["lectures"]["creations_sans_canal"]["vieillie"] == pytest.approx(
        today.aged.delta[-1], abs=1e-12)
    chemin = payload["creations"]["chemins"][0]["vieillie"]
    assert chemin["delta_sans_creations"] == pytest.approx(list(today.aged.delta))
    assert payload["creations"]["prelevements_eur"]["vieillie"]["2026"] == -10e9
    assert creations.CONVENTION in payload["conventions"]
    assert "Baisse" not in json.dumps(payload["creations"]["parametres"])


def test_a_reform_without_a_levy_on_firms_or_capital_has_no_channel() -> None:
    today = _build(HALF, {}, channel=False)
    read = _build(HALF, {}, channel=True)
    assert read.aged.delta == pytest.approx(today.aged.delta, abs=1e-15)
    assert set(read.aged.creations["pib"]) == {0.0}


def test_a_rise_lifts_the_debt_a_cut_lowers_it_by_the_same_channel() -> None:
    """The channel's share of Δb, symmetric to first order (the GDP divides the debt, so
    exactly opposite only in the receipts)."""
    rise = {k: -v for k, v in CUT.items()}
    up, down = _build(HALF, rise, channel=True).aged, _build(HALF, CUT, channel=True).aged
    lift = up.delta[-1] - up.delta_sans_creations[-1]
    fall = down.delta[-1] - down.delta_sans_creations[-1]
    assert lift > 0 > fall
    assert lift == pytest.approx(-fall, rel=0.02)


def test_the_box_carries_the_channel_s_theta_and_the_replay_is_the_chain() -> None:
    read = _build(HALF, CUT, channel=True)
    payload = json.loads(json.dumps(read.payload()))
    assert CREATIONS_ROW in payload["theta_box"]["rows"]
    assert CREATIONS_ROW in payload["rejeu"]["box_rows"]
    rows = {"eti_all": 0.5, "eti_top_decile": 0.5, MACRO_ROW: 0.5, CREATIONS_ROW: 0.5}
    for view, drawn in (("vieillie", read.aged), ("figee", read.frozen)):
        replayed = rejouer.at_theta(payload, rows, view=view, persistence="lue")
        assert np.max(np.abs(np.array(replayed.delta) - np.array(drawn.delta))) < 1e-9
        without = rejouer.at_theta(payload, rows, view=view, persistence="lue",
                                   creations=False)
        assert np.max(np.abs(np.array(without.delta)
                             - np.array(drawn.delta_sans_creations))) < 1e-9
    box = payload["creations"]["chemins"][0]["vieillie"]["boite"]
    assert box["c1"] < box["theta"] < box["c0"]
    assert box["c0"] == pytest.approx(read.aged.delta_sans_creations[-1], abs=1e-15)
    # Δb at the channel's θ, every other row held, falls as θ rises: monotone.
    seq = [rejouer.at_theta(payload, {**rows, CREATIONS_ROW: t}, view="vieillie",
                            persistence="lue").delta[-1] for t in np.linspace(0, 1, 6)]
    assert all(b < a for a, b in pairwise(seq))


def test_a_pass_without_its_levies_is_refused_not_read_as_zero() -> None:
    def price(year: int, view: str) -> Priced:
        return Priced(cost=_cost(year, view), inputs=households(),
                      impulse={"impot_sur_le_revenu": -_cost(year, view)})

    prices = annuel.price_years(YEARS, price, basis_for=lambda y: "legislated")
    with pytest.raises(DebtError, match="ne portent pas leurs prélèvements"):
        annuel.build(START, prices, scenario="s", titre="s", source="t", reference="r",
                     computed="2026-11-13", spending=FROZEN, growth=GROWTH, rate=HELD,
                     theta=HALF, uprating=UPRATING, uprating_note="", reform=IR,
                     behavioural=True, macro=True, persistence="lue",
                     macro_store=synthetic_macro_store(), creations=PARAMS)


def test_the_service_reads_the_levies_reform_minus_baseline() -> None:
    frame = pl.DataFrame({"weight": [2.0, 3.0], "pfu": [100.0, 0.0],
                          "pfu_reform": [130.0, 10.0],
                          "prelevements_sociaux_capital": [50.0, 50.0],
                          "prelevements_sociaux_capital_reform": [50.0, 50.0],
                          "ir": [1000.0, 0.0], "ir_reform": [0.0, 0.0]})
    assert service.creations_household_levies(frame) == {"pfu": pytest.approx(90.0)}
    firm = {"impot_societes": -3e9, "cebge": 0.0, "prelevements_entreprise": -3e9}
    assert service.creations_firm_levies(firm) == {"impot_societes": -3e9}
    # A pass that kept no household frame is not read, rather than read as no levy.
    assert service.creations_household_levies(None) is None
