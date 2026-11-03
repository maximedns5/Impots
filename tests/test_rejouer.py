"""D-336, decision 6 — the report keeps enough to replay the chain, and the replay is the
chain's (`predictif.rejouer`, `predictif.montecarlo`).

On synthetic passes (`exploration_cases.households`, an income-tax rise, and a CSG
change for C7), `annuel.build` writes the impulses and the channels' statistics per year
and view; `rejouer` refits the debt, the loop and the box from the payload alone, and must
give the chain's own numbers to 1e-9, under the three persistences and several θ.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from exploration_cases import households
from impots.api.schemas import PredictifReportResponse, ReformSpec
from impots.dette import reference
from impots.dette.path import SHIPPED
from impots.dette.scenarios import GrowthScenario, RateScenario
from impots.predictif import annuel, montecarlo, rejouer, retroaction
from impots.predictif.exploration import Priced
from impots.predictif.theta import MACRO_ROW, Theta
from macro_cases import synthetic_macro_store

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = GrowthScenario("Croissance réelle 1 %, prix 2 %", 0.01, 0.02)
HELD = RateScenario("Taux implicite tenu à son niveau de 2025", "implicite_tenu")
MARKET = RateScenario("Dette ajoutée au taux de marché, 3,5 %", "marche", 0.035)
FROZEN = SHIPPED["gele_en_volume"]
UPRATING = annuel.uprating_for(GROWTH, wage=0.03, source="3 % ronds", base_year=2024)
IR = ReformSpec.model_validate({"ir_bareme": [
    {"threshold": 0, "rate": 0.00}, {"threshold": 11497, "rate": 0.11},
    {"threshold": 29315, "rate": 0.30}, {"threshold": 83823, "rate": 0.41},
    {"threshold": 180294, "rate": 0.50}]})
YEARS = list(range(2026, 2036))


def _cost(year: int, view: str) -> float:
    """A cut that grows, then stops growing: the impulse changes, then holds."""
    return -(20e9 + 3e9 * min(year - 2026, 4)) * (1.0 if view == "vieillie" else 0.92)


def _price(year: int, view: str) -> Priced:
    cost = _cost(year, view)
    return Priced(cost=cost, inputs=households(), impulse={"impot_sur_le_revenu": -cost,
                                                           "csg": -0.25 * cost})


def _build(theta: Theta, *, persistence=None, macro=True, spending=FROZEN, rate=HELD):
    def price(year: int, view: str) -> Priced:
        whole = _price(year, view)
        return whole if macro else Priced(cost=whole.cost, inputs=whole.inputs)

    prices = annuel.price_years(YEARS, price, basis_for=lambda y: "legislated")
    return annuel.build(START, prices, scenario="baisse", titre="Baisse", source="test",
                        reference="reconduit", computed="2026-11-03", spending=spending,
                        growth=GROWTH, rate=rate, theta=theta, uprating=UPRATING,
                        uprating_note="", reform=IR, behavioural=True, macro=macro,
                        persistence=persistence, macro_store=synthetic_macro_store())


THETAS = [
    {"eti_all": 0.5, "eti_top_decile": 0.5, MACRO_ROW: 0.5},
    {"eti_all": 0.2, "eti_top_decile": 0.9, MACRO_ROW: 0.0},
    {"eti_all": 1.0, "eti_top_decile": 0.3, MACRO_ROW: 1.0},
    {"eti_all": 0.7, "eti_top_decile": 0.0, MACRO_ROW: 0.35},
]


@pytest.mark.parametrize("rows", THETAS)
@pytest.mark.parametrize("persistence", retroaction.PERSISTENCE_LABELS)
def test_the_replay_is_the_chain_to_1e_9(rows, persistence) -> None:
    """Every year, both views: Δb, the GDP gap and the feedback, from the payload alone
    — after a JSON round trip, as a page would read it."""
    theta = Theta(rows=rows, common=0.5)
    rapport = _build(theta, persistence=persistence)
    payload = json.loads(json.dumps(rapport.payload()))
    for view, drawn in (("vieillie", rapport.aged), ("figee", rapport.frozen)):
        replayed = rejouer.at_theta(payload, rows, view=view, persistence=persistence)
        assert np.max(np.abs(np.array(replayed.delta) - np.array(drawn.delta))) < 1e-9
        assert np.max(np.abs(np.array(replayed.gdp_gap) - np.array(drawn.gdp_gap))) < 1e-9
        assert np.max(np.abs(np.array(replayed.feedback)
                             - np.array(drawn.feedback_primary))) < 1e-9
        assert replayed.reference == pytest.approx(drawn.reference, abs=1e-12)


def test_the_replay_is_the_box_under_each_persistence() -> None:
    """The three persistences side by side, from one report: Δb at θ and at every corner
    of the box, every year priced, as `annuel._theta_box` wrote them."""
    half = {"eti_all": 0.5, "eti_top_decile": 0.5, MACRO_ROW: 0.5}
    payload = json.loads(json.dumps(_build(Theta(common=0.5)).payload()))
    PredictifReportResponse.model_validate(payload)
    assert [p["persistence"] for p in payload["theta_box"]["paths"]] == list(
        retroaction.PERSISTENCE_LABELS)
    for path in payload["theta_box"]["paths"]:
        for view in rejouer.VIEWS:
            written = path["every_year"][view]
            replayed = rejouer.box(payload, half, view=view, persistence=path["persistence"])
            assert abs(replayed["theta"] - written["theta"]) < 1e-9
            assert [label for label, _ in replayed["corners"]] == [
                label for label, _ in written["corners"]]
            for (_, mine), (_, theirs) in zip(replayed["corners"], written["corners"],
                                              strict=True):
                assert abs(mine - theirs) < 1e-9


def test_the_replay_holds_without_the_loop_and_at_a_market_rate() -> None:
    """Behaviour alone, and the extra debt charged at another rate than the reference's."""
    rows = {"eti_all": 0.3, "eti_top_decile": 0.8}
    for macro, spending, rate in ((False, FROZEN, HELD),
                                  (True, SHIPPED["part_pib_constante"], HELD)):
        rapport = _build(Theta(rows=rows, common=0.5), macro=macro, spending=spending,
                         rate=rate)
        payload = json.loads(json.dumps(rapport.payload()))
        replayed = rejouer.at_theta(payload, rows, view="vieillie", persistence=None)
        assert np.max(np.abs(np.array(replayed.delta) - np.array(rapport.aged.delta))) < 1e-9


def test_the_report_writes_what_the_replay_reads() -> None:
    """Per year and view: the impulse by instrument, the uncovered, C1's A_bas and
    A_haut, the share of C1 at the floor; once: the frame and the tables."""
    payload = _build(Theta(common=0.5)).payload()
    first = payload["years"][0]["statistiques"]["vieillie"]
    assert set(first) == {"cost_eur", "impulses", "uncovered", "canaux", "c1_floor_share"}
    assert first["impulses"] == {"impot_sur_le_revenu": 20e9, "csg": 5e9}
    assert set(first["canaux"]["c1_eti"]) == {"A_bas", "A_haut"}
    assert 0.0 <= first["c1_floor_share"] <= 1.0
    rejeu = payload["rejeu"]
    assert set(rejeu["lignes"]) == {"eti_all", "eti_top_decile"}
    assert rejeu["lignes"]["eti_top_decile"]["fichier"] == "eti"
    assert set(rejeu["macro"]["instruments"]) == {"csg", "impot_sur_le_revenu"}
    assert rejeu["macro"]["horizons"] == [1, 2, 3, 5, 10] and rejeu["macro"]["court"] == 3
    assert rejeu["box_rows"] == ["eti_all", "eti_top_decile", MACRO_ROW]


def test_a_report_without_the_statistics_is_refused() -> None:
    payload = _build(Theta(common=0.5)).payload()
    del payload["rejeu"]
    with pytest.raises(rejouer.ReplayError, match="avant D-336"):
        rejouer.at_theta(payload, THETAS[0], view="vieillie", persistence="lue")


# --------------------------------------------------------------------------- #
# the Monte Carlo
# --------------------------------------------------------------------------- #
def test_the_monte_carlo_is_written_beside_the_box_and_reproducible() -> None:
    """Under « lue », per view: the share of draws where the debt rises, its quantiles,
    and Sobol indices by article; at a fixed seed, the same to the last digit."""
    payload = json.loads(json.dumps(_build(Theta(common=0.5)).payload()))
    monte = payload["monte_carlo"]
    assert monte["persistence"] == "lue" and monte["tirages"] == montecarlo.DRAWS
    assert monte["groupes"] == {"eti": ["eti_all", "eti_top_decile"],
                                MACRO_ROW: [MACRO_ROW]}
    for view in rejouer.VIEWS:
        read = monte["vues"][view]
        assert 0.0 <= read["p_hausse"] <= 1.0
        q = read["quantiles"]
        assert q["q05"] <= q["q50"] <= q["q95"]
        for indices in read["sobol"].values():
            assert -0.05 <= indices["premier_ordre"] <= indices["total"] + 0.05
    again = montecarlo.run(payload)
    assert again["vues"] == monte["vues"]


def test_the_copula_ties_an_article_and_the_laws_are_the_store_s() -> None:
    """ρ = 0,8 between the rows of one file, the triangular quantile function of the
    store's law: its median, and its bounds."""
    rejeu = {"lignes": {
        "a": {"low": 0.0, "central": 0.2, "high": 1.0, "loi": "triangular", "fichier": "x"},
        "b": {"low": 0.0, "central": 0.5, "high": 1.0, "loi": "uniform", "fichier": "x"},
        "c": {"low": -1.0, "central": 0.0, "high": 1.0, "loi": "normal", "fichier": "y"}},
        "looped": False}
    groups = montecarlo._groups(rejeu)
    assert groups == {"x": ["a", "b"], "y": ["c"]}
    drawn = montecarlo._draw(rejeu, groups, 20_000, np.random.default_rng(0), 0.8)
    assert np.corrcoef(drawn["a"], drawn["b"])[0, 1] > 0.7
    assert abs(np.corrcoef(drawn["a"], drawn["c"])[0, 1]) < 0.03
    assert drawn["a"].min() >= 0.0 and drawn["a"].max() <= 1.0
    # Triangular (0 ; 0,2 ; 1): the median is 1 − √(0,4), the normal's 90 % is [−1 ; 1].
    assert np.median(drawn["a"]) == pytest.approx(1 - np.sqrt(0.4), abs=0.01)
    assert np.mean(np.abs(drawn["c"]) <= 1.0) == pytest.approx(0.90, abs=0.01)


def test_the_verdict_reads_one_persistence() -> None:
    """« lue » alone can give the verdict (D-336, decision 1)."""
    payload = json.loads(json.dumps(_build(Theta(common=0.5)).payload()))
    half = {"eti_all": 0.5, "eti_top_decile": 0.5, MACRO_ROW: 0.5}
    reading = rejouer.verdict(payload, half)
    assert reading in ("hausse", "baisse", "dépend de θ")
    values = [rejouer.box(payload, half, view=v, persistence="lue") for v in rejouer.VIEWS]
    every = [x for v in values for x in (v["theta"], *(c for _, c in v["corners"]))]
    assert reading == ("hausse" if min(every) > 0 else "baisse" if max(every) < 0
                       else "dépend de θ")
