"""Phase 10 M3 — behaviour and the loop in the annual path, year by year (PHASE10_SPEC §4).

`impots predictif` priced every year mechanically only (D-216). With `--behavioural` and
`--macro` each year's pass carries what the channels read and the reform's impulse, and
the chain reads one impulse per year, superposed, with no carry convention. What is held
here, without data: the receipts at θ per year and the impulses per year against an
independent construction, both persistence scenarios side by side past three years, the
refusals of a year without what was asked of it, the report the API reads, the command's
own refusals, and its first year equal to the simulator's.
"""

from __future__ import annotations

import dataclasses
import json
from types import SimpleNamespace

import polars as pl
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from exploration_cases import households
from impots import service
from impots.api import main
from impots.api.schemas import PredictifReportResponse, ReformSpec
from impots.dette import reference
from impots.dette.path import SHIPPED, DebtError
from impots.dette.scenarios import GrowthScenario, RateScenario
from impots.population import aggregate, cli, runner
from impots.predictif import annuel, chaine, comportement, exploration, recherche, retroaction
from impots.predictif.exploration import Priced
from impots.predictif.theta import MACRO_ROW, Theta, ThetaError
from macro_cases import synthetic_macro_store

START = reference.Start(year=2025, gdp_eur=3_000e9, receipts_ratio=0.52,
                        spending_ratio=0.55, debt_ratio=1.15, implicit_rate=0.019)
GROWTH = GrowthScenario("Croissance réelle 1 %, prix 2 %", 0.01, 0.02)
HELD = RateScenario("Taux implicite tenu à son niveau de 2025", "implicite_tenu")
FROZEN = SHIPPED["gele_en_volume"]
HALF = Theta(common=0.5)
UPRATING = annuel.uprating_for(GROWTH, wage=0.03, source="3 % ronds", base_year=2024)
#: A top-rate rise: the ETI rows claim `ir_bareme`, so the θ box moves.
REFORM = ReformSpec.model_validate({"ir_bareme": [
    {"threshold": 0, "rate": 0.00}, {"threshold": 11497, "rate": 0.11},
    {"threshold": 29315, "rate": 0.30}, {"threshold": 83823, "rate": 0.41},
    {"threshold": 180294, "rate": 0.50}]})


def _cost(year: int, view: str) -> float:
    """A cost that grows a billion a year — a constant cost would hide a carried year."""
    return (5e9 + 1e9 * (year - 2026)) * (1.0 if view == "vieillie" else 0.9)


def _whole(year: int, view: str, *, behaviour: bool = True, impulse: bool = True) -> Priced:
    cost = _cost(year, view)
    return Priced(cost=cost, inputs=households() if behaviour else None,
                  impulse={"impot_sur_le_revenu": cost} if impulse else None)


def _build(horizon: int = 3, *, price=_whole, behavioural: bool = True, macro: bool = True,
           persistence: str | None = None, spending=FROZEN,
           theta: Theta = HALF) -> annuel.Rapport:
    years = list(range(2026, 2026 + horizon))
    prices = annuel.price_years(years, price, basis_for=lambda y: "legislated")
    return annuel.build(START, prices, scenario="hausse", titre="Hausse du taux marginal",
                        source="test", reference="reconduit", computed="2026-10-21",
                        spending=spending, growth=GROWTH, rate=HELD, theta=theta,
                        uprating=UPRATING, uprating_note="", reform=REFORM,
                        behavioural=behavioural, macro=macro, persistence=persistence,
                        macro_store=synthetic_macro_store())


# --------------------------------------------------------------------------- #
# the path: every year its own receipts at θ and its own impulse
# --------------------------------------------------------------------------- #
def test_every_year_reads_its_own_receipts_at_theta_and_its_own_impulse() -> None:
    """D-042: against an independent construction. Each year's receipts at θ are what
    `comportement.evaluate` gives on that year's pass, each year's impulse is that year's,
    and the chain reads them all with no carry — the path is the chain's on exactly
    those inputs, in both views."""
    rapport = _build()
    for view, path in (("vieillie", rapport.aged), ("figee", rapport.frozen)):
        costs = chaine.ReformCosts(
            by_year={y: _cost(y, view) for y in (2026, 2027, 2028)},
            behavioural={y: comportement.evaluate(HALF, mechanical=-_cost(y, view),
                                                  reform=REFORM, **households())
                         for y in (2026, 2027, 2028)},
            impulses={y: {"impot_sur_le_revenu": _cost(y, view)}
                      for y in (2026, 2027, 2028)})
        direct = chaine.run(START, horizon=3, costs=costs, spending=FROZEN, growth=GROWTH,
                            rate=HELD, theta=HALF, macro_store=synthetic_macro_store())
        assert path.delta == pytest.approx(direct.delta, rel=1e-12), view
        assert path.priced_years == (2026, 2027, 2028) and path.carried_years == ()
        assert path.theta_applied and path.gdp_gap is not None
        assert chaine.CARRY_LABEL not in path.conventions
        assert retroaction.LINEAR in path.conventions


def test_a_cost_that_changes_is_superposed_not_carried() -> None:
    """The fast version carries its first year as a share of GDP. The annual path prices
    every year: with a cost that grows, its third year is not the fast version's."""
    rapport = _build()
    fast = chaine.run(START, horizon=3, costs=chaine.ReformCosts(
        by_year={2026: _cost(2026, "vieillie")}, carry=chaine.CARRY,
        behavioural={2026: comportement.evaluate(
            HALF, mechanical=-_cost(2026, "vieillie"), reform=REFORM, **households())},
        impulses={2026: {"impot_sur_le_revenu": _cost(2026, "vieillie")}}),
        spending=FROZEN, growth=GROWTH, rate=HELD, theta=HALF,
        macro_store=synthetic_macro_store())
    assert rapport.aged.delta[0] == pytest.approx(fast.delta[0], rel=1e-12)
    assert abs(rapport.aged.delta[2] - fast.delta[2]) > 1e-5


def test_past_three_years_both_persistences_stand_side_by_side() -> None:
    """D-230 for the annual path: with the loop past three years and none named, both
    scenarios are drawn from the same passes, and the report has no path of its own."""
    rapport = _build(horizon=5)
    assert [p.persistence for p in rapport.paths] == list(retroaction.PERSISTENCE_LABELS)
    for view in ("aged", "frozen"):
        with pytest.raises(DebtError, match="aucun n'est le chemin de tête"):
            getattr(rapport, view)
    payload = rapport.payload()
    assert all(row["delta_aged"] is None for row in payload["years"])
    off, held = payload["side_by_side"]
    assert off["label"] == retroaction.PERSISTENCE_LABELS["eteint"]
    assert off["years"][:3] == held["years"][:3]
    assert off["years"][4]["delta_aged"] != held["years"][4]["delta_aged"]
    assert payload["persistence"] is None and payload["macro"] is True
    PredictifReportResponse.model_validate(payload)


@pytest.mark.parametrize("persistence, horizon, spending, count", [
    ("tenu", 5, FROZEN, 1), (None, 3, FROZEN, 1), (None, 5, SHIPPED["part_pib_constante"], 1),
])
def test_one_path_where_the_simulator_draws_one(persistence, horizon, spending,
                                               count) -> None:
    rapport = _build(horizon=horizon, persistence=persistence, spending=spending)
    assert len(rapport.paths) == count
    payload = rapport.payload()
    assert payload["side_by_side"] == [] and payload["years"][0]["delta_aged"] is not None
    PredictifReportResponse.model_validate(payload)


# --------------------------------------------------------------------------- #
# guard 9: a year without what was asked of it is refused, never read as zero
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("missing, needle", [
    ("impulse", "entrées des canaux ou impulsion"),
    ("inputs", "entrées des canaux ou impulsion"),
    ("cost only", "n'ont que leur coût"),
])
def test_a_year_without_what_was_asked_of_it_is_refused(missing: str, needle: str) -> None:
    """GUARD 9. The second year's pass without its impulse, or its channel inputs, or with
    its cost alone: read as zero it would be a year without a shock, or without
    behaviour, drawn like the others."""
    def price(year: int, view: str):
        if year != 2027:
            return _whole(year, view)
        if missing == "cost only":
            return _cost(year, view)
        return _whole(year, view, behaviour=missing != "inputs",
                      impulse=missing != "impulse")

    with pytest.raises(DebtError, match=needle):
        if missing == "cost only":
            prices = [annuel.YearPrice(year=y, basis="legislated",
                                       frozen_eur=_cost(y, "figee"),
                                       aged_eur=_cost(y, "vieillie"),
                                       passes=(None if y == 2027 else
                                               {v: _whole(y, v) for v in annuel.VIEWS}))
                      for y in (2026, 2027, 2028)]
            annuel.build(START, prices, scenario="hausse", titre="t", source="test",
                         reference="reconduit", computed="2026-10-21", spending=FROZEN,
                         growth=GROWTH, rate=HELD, theta=HALF, uprating=UPRATING,
                         uprating_note="", reform=REFORM, behavioural=True, macro=True,
                         macro_store=synthetic_macro_store())
        else:
            _build(price=price)


def test_behaviour_or_the_loop_without_a_theta_is_refused() -> None:
    """θ is required, with no default (D-217): the annual path refuses to build without
    it, before any receipts are read at a θ nobody chose."""
    prices = annuel.price_years([2026], _whole, basis_for=lambda y: "legislated")
    with pytest.raises(DebtError, match="sans θ"):
        annuel.build(START, prices, scenario="hausse", titre="t", source="test",
                     reference="reconduit", computed="2026-10-21", spending=FROZEN,
                     growth=GROWTH, rate=HELD, theta=None, uprating=UPRATING,
                     uprating_note="", reform=REFORM, behavioural=True, macro=True,
                     macro_store=synthetic_macro_store())


def test_one_view_priced_whole_and_the_other_by_its_cost_alone_is_refused() -> None:
    with pytest.raises(DebtError, match="une vue chiffrée en entier"):
        annuel.price_years([2026], lambda y, v: _whole(y, v) if v == "figee" else 5e9,
                           basis_for=lambda y: "legislated")


# --------------------------------------------------------------------------- #
# the report the API reads
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("how, needle", [
    ("own path too", "trajectoire en propre ET des scénarios"),
    ("one scenario", "les deux persistances, chacune une fois"),
    ("short", "ne couvre pas toutes les années"),
    ("no path", "sans trajectoire pour certaines années"),
])
def test_a_report_a_reader_would_misread_is_refused(how: str, needle: str) -> None:
    payload = _build(horizon=5).payload()
    if how == "own path too":
        payload["years"][0].update(reform_aged=1.0, delta_aged=0.0, reform_frozen=1.0,
                                   delta_frozen=0.0)
    elif how == "one scenario":
        payload["side_by_side"].pop()
    elif how == "short":
        payload["side_by_side"][1]["years"].pop()
    else:
        payload["side_by_side"] = []
    with pytest.raises(ValidationError, match=needle):
        PredictifReportResponse.model_validate(payload)


# --------------------------------------------------------------------------- #
# the command, through the simulator's own pass
# --------------------------------------------------------------------------- #
ARGS = ["predictif", "gel_bareme", "--reference", "reconduit",
        "--spending", "gele_en_volume",
        "--growth-name", "Croissance réelle 1 %, prix 2 %", "--real", "0.01",
        "--prices", "0.02",
        "--rate-name", "Taux implicite tenu à son niveau de 2025",
        "--rate-kind", "implicite_tenu", "--theta", "0.5",
        "--wage", "0.03", "--hypothesis-source", "3 % ronds"]


@pytest.fixture
def command(monkeypatch, tmp_path) -> dict:
    """The command with the simulator's pass stubbed one seam below, as the explorer's
    tests stub it (`_price_first_year`), and a start that needs no INSEE file."""
    seen: list = []
    # The mechanical path's pass is stubbed too, on a five-person population: a refusal
    # the guard sweep removes must fail this test in seconds, not run the real
    # population (D-236 — it once did, at 7 Go, and the real run beside it was killed).
    processed = tmp_path / "processed"
    processed.mkdir()
    pl.DataFrame({"person_id": [1, 2, 3, 4, 5], "salaire_brut_annuel": [30_000.0] * 5,
                  "pension_annuelle": [0.0] * 5, "chomage_annuel": [0.0] * 5,
                  "loyer_mensuel": [500.0] * 5}).write_parquet(
        processed / "population_2024.parquet")
    monkeypatch.setattr(cli, "PROCESSED", processed)
    monkeypatch.setattr(runner, "run", lambda pop, **kw: SimpleNamespace(
        households=SimpleNamespace(cost=5e9)))
    monkeypatch.setattr(aggregate, "aggregate",
                        lambda households: SimpleNamespace(reform_cost=households.cost,
                                                           totals={}))

    def stub(request, *, uprating, macro=False, view="vieillie"):
        seen.append((request.year, view, request.behavioural, macro))
        cost = _cost(request.year, view)
        return SimpleNamespace(cost=cost, view=view, note="", deciles=[],
                               inputs=households() if request.behavioural else None,
                               impulse={"impot_sur_le_revenu": cost} if macro else None,
                               uncovered={})

    monkeypatch.setattr(service, "price_first_year", stub)
    monkeypatch.setattr(service, "predictif_macro_store", synthetic_macro_store)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)

    def launch(*extra: str, base: list[str] = ARGS) -> tuple[int, dict | None]:
        code = cli.main([*base, *extra, "--out-dir", str(tmp_path)])
        out = tmp_path / "predictif_gel_bareme.json"
        return code, json.loads(out.read_text(encoding="utf-8")) if out.exists() else None

    return {"seen": seen, "launch": launch, "out": tmp_path, "monkeypatch": monkeypatch}


def test_the_command_prices_every_year_through_the_simulators_pass(command) -> None:
    """Every year and both views through `_price_first_year`, past the API's window: the
    years 2027 to 2029 are not ones a request may ask for (MAX_YEAR), and the command
    prices them anyway, each with its basis, as it always has (D-216)."""
    code, report = command["launch"]("--horizon", "4", "--behavioural", "--macro")
    assert code == 0
    assert sorted(command["seen"]) == sorted(
        (y, v, True, True) for y in (2026, 2027, 2028, 2029) for v in ("vieillie", "figee"))
    assert [p["persistence"] for p in report["side_by_side"]] == ["eteint", "tenu"]
    assert report["behavioural"] and report["macro"] and report["theta_applied"]
    PredictifReportResponse.model_validate(report)


@pytest.mark.parametrize("base, extra, needle", [
    ([a if a != "reconduit" else "indexe" for a in ARGS], ("--macro",),
     "contre la référence « indexe »"),
    (ARGS, ("--behavioural", "--sample", "8000"), "chiffreraient les années"),
    (ARGS, ("--persistence", "tenu"), "sans boucle appliquée"),
])
def test_what_the_whole_pass_cannot_honour_is_refused_before_any_pass(
        command, capsys, base, extra, needle) -> None:
    """Against « indexe » the cost is a difference of two passes, which neither the
    channels' inputs nor the impulse are built for; another sample would price the years
    on another population than the simulator's; and a persistence without the loop would
    be ignored. Each refused before the first pass, nothing written."""
    code, report = command["launch"]("--horizon", "3", *extra, base=base)
    assert code == 1 and report is None and command["seen"] == []
    assert needle in capsys.readouterr().err


def test_the_first_year_is_the_simulators(command) -> None:
    """ONE PRICING PATH, again. The same reform, the same hypotheses, the same stubbed
    pass: the annual path's first year is the debt gap `/predictif/simulate` returns for
    its first year, behaviour and loop included. The years after differ — one priced,
    the other carried — and that is the point of the annual path."""
    code, report = command["launch"]("--horizon", "3", "--behavioural", "--macro")
    assert code == 0
    scenario = json.loads((cli.Path(cli.__file__).resolve().parents[3] / "scenarios"
                           / "gel_bareme.json").read_text(encoding="utf-8"))
    with TestClient(main.app) as client:
        response = client.post("/predictif/simulate", json={
            "reform": scenario["reform"], "spending": {"rule": "gele_en_volume"},
            "growth": {"name": "Croissance réelle 1 %, prix 2 %", "real": 0.01,
                       "prices": 0.02},
            "rate": {"name": "Taux implicite tenu à son niveau de 2025",
                     "kind": "implicite_tenu"},
            "horizon": 3, "theta": {"common": 0.5},
            "uprating": {"wage": 0.03, "source": "3 % ronds"},
            "behavioural": True, "macro": True})
    assert response.status_code == 200, response.text
    assert report["years"][0]["delta_aged"] == pytest.approx(response.json()["delta"][0],
                                                             rel=1e-12)


# --------------------------------------------------------------------------- #
# a firm reform alone, behaviour asked: priced, and said unread (D-268, D-273)
# --------------------------------------------------------------------------- #
FIRM_NOTE = "La couche entreprises, ses cellules et sa convention (test)."


def _firm_alone(year: int, view: str, *, asked: bool = True, macro: bool = True) -> Priced:
    """What the simulator's pass gives for a firm reform alone: no population pass, so
    no channel inputs; the firm layer's cost; and, behaviour asked, the flag that says
    no household channel reads it (D-268)."""
    cost = _cost(year, view)
    return Priced(cost=cost, inputs=None, impulse={} if macro else None,
                  uncovered={"cvae": service.FIRM_NO_VARIANT} if macro else {},
                  layers={"menages": 0.0, "entreprises": cost}, behaviour_asked=asked)


def _build_firm(price, *, behavioural: bool = True, macro: bool = True) -> annuel.Rapport:
    prices = annuel.price_years([2026, 2027, 2028], price, basis_for=lambda y: "legislated")
    return annuel.build(START, prices, scenario="cvae_moitie", titre="La CVAE à moitié",
                        source="test", reference="reconduit", computed="2026-10-27",
                        spending=FROZEN, growth=GROWTH, rate=HELD, theta=HALF,
                        uprating=UPRATING, uprating_note="", reform=ReformSpec(),
                        behavioural=behavioural, macro=macro, firm_note=FIRM_NOTE,
                        macro_store=synthetic_macro_store())


@pytest.mark.parametrize("macro", [True, False])
def test_a_firm_reform_alone_with_behaviour_asked_is_priced_and_said_unread(
        macro: bool) -> None:
    """D-273. The annual path refused a firm reform alone with behaviour asked: its years
    have no channel inputs, and read as missing they were. The pass says behaviour was
    asked (D-268): the path is priced, every year, and the band and the θ line say no
    household channel reads a firm knob — not « non demandé », and not zero either. The
    path is the mechanical one: no channel adds anything."""
    rapport = _build_firm(lambda y, v: _firm_alone(y, v, macro=macro), macro=macro)
    payload = rapport.payload()
    assert payload["behavioural"] is True
    assert payload["absent"]["bande"] == chaine.NO_HOUSEHOLD_CHANNEL
    assert payload["absent"]["θ"] == chaine.THETA_NO_HOUSEHOLD_CHANNEL
    # The command's own lines say it too: not « vue mécanique ».
    line = next(x for x in rapport.paths[0].aged.lines() if x.startswith("  θ : "))
    assert line.endswith("(non lus : aucun canal des ménages ne lit la réforme)")
    # The same reform without behaviour: its whole pass for the loop, its cost alone else.
    mechanical = _build_firm(
        (lambda y, v: _firm_alone(y, v, asked=False)) if macro
        else (lambda y, v: annuel.Layered(cost=_cost(y, v), layers={
            "menages": 0.0, "entreprises": _cost(y, v)})),
        behavioural=False, macro=macro)
    assert rapport.aged.delta == mechanical.aged.delta
    assert rapport.frozen.delta == mechanical.frozen.delta
    assert [row["mechanical_by_layer"]["vieillie"]["entreprises"]
            for row in payload["years"]] == [_cost(y, "vieillie") for y in (2026, 2027, 2028)]
    PredictifReportResponse.model_validate(payload)


def test_a_year_without_inputs_nor_the_flag_is_still_refused() -> None:
    """GUARD 9 holds: a firm reform's year whose pass does not say behaviour was asked is
    a year without what was asked of it, refused as before."""
    with pytest.raises(DebtError, match="entrées des canaux ou impulsion"):
        _build_firm(lambda y, v: _firm_alone(y, v, asked=y != 2027))


def test_years_of_a_household_reform_and_of_a_firm_reform_alone_are_refused() -> None:
    """One scenario, one reform: a year flagged as a firm reform alone beside years that
    carry the channels' inputs is not a path, and is refused rather than drawn with a
    band over some years only."""
    def price(year: int, view: str) -> Priced:
        if year == 2027:
            return _firm_alone(year, view)
        whole = _whole(year, view)
        return Priced(cost=whole.cost, inputs=whole.inputs, impulse=whole.impulse,
                      layers={"menages": 0.0, "entreprises": whole.cost})

    with pytest.raises(DebtError, match="seules entreprises"):
        _build_firm(price)


def test_the_command_carries_the_flag_from_the_simulators_pass(command) -> None:
    """D-273, through the command: the CVAE at half its schedule, a firm reform alone,
    with `--behavioural` and `--macro`. The stubbed pass says behaviour was asked, as the
    simulator's does (D-268); the command carries it, and the report says no household
    channel reads the reform instead of refusing it."""
    seen = command["seen"]

    def stub(request, *, uprating, macro=False, view="vieillie", firm_reform=None,
             growth=None):
        seen.append((request.year, view, request.behavioural, macro))
        cost = _cost(request.year, view)
        return SimpleNamespace(
            cost=cost, view=view, note="", deciles=[], inputs=None,
            impulse={} if macro else None,
            uncovered={"cvae": service.FIRM_NO_VARIANT} if macro else {},
            layers={"menages": 0.0, "entreprises": cost},
            behaviour_asked=bool(request.behavioural) and request.reform.is_empty())

    command["monkeypatch"].setattr(service, "price_first_year", stub)
    command["monkeypatch"].setattr(service, "firm_report_note", lambda *a, **k: FIRM_NOTE)
    base = ["predictif", "cvae_moitie_2026", *ARGS[2:]]
    code = cli.main([*base, "--horizon", "3", "--behavioural", "--macro",
                     "--out-dir", str(command["out"])])
    assert code == 0
    report = json.loads((command["out"] / "predictif_cvae_moitie_2026.json").read_text(
        encoding="utf-8"))
    assert sorted(seen) == sorted((y, v, True, True) for y in (2026, 2027, 2028)
                                  for v in ("vieillie", "figee"))
    assert report["absent"]["bande"] == chaine.NO_HOUSEHOLD_CHANNEL
    assert report["absent"]["θ"] == chaine.THETA_NO_HOUSEHOLD_CHANNEL
    PredictifReportResponse.model_validate(report)


# --------------------------------------------------------------------------- #
# the θ box of the annual path, and the first year carried beside it (D-275)
# --------------------------------------------------------------------------- #
VIEW_KEYS = ("vieillie", "figee")


def _diagonal(corners: list, side: int) -> float:
    """Built apart from the code: the one corner whose every row is at `side`."""
    [value] = [v for label, v in corners
               if all(part.endswith(f" = {side}") for part in label.split(", "))]
    return value


def test_the_box_at_theta_is_the_report_s_own_path() -> None:
    """Every year priced: Δb at θ in the box, at its last year, is the path the report
    draws, in both views and under each persistence. Its rows are those the reform claims
    and the multiplier's, and each reading has every corner."""
    payload = _build(horizon=5).payload()
    box = payload["theta_box"]
    assert box["year"] == 2030
    assert box["rows"] == ["eti_all", "eti_top_decile", MACRO_ROW]
    drawn = {p["persistence"]: p["years"][-1] for p in payload["side_by_side"]}
    assert [p["persistence"] for p in box["paths"]] == ["eteint", "tenu"]
    for path in box["paths"]:
        last = drawn[path["persistence"]]
        assert path["every_year"]["vieillie"]["theta"] == pytest.approx(last["delta_aged"],
                                                                        rel=1e-12)
        assert path["every_year"]["figee"]["theta"] == pytest.approx(last["delta_frozen"],
                                                                     rel=1e-12)
        for reading in ("every_year", "first_year"):
            for view in VIEW_KEYS:
                values = [v for _, v in path[reading][view]["corners"]]
                assert len(values) == 8 and min(values) < max(values)
    PredictifReportResponse.model_validate(payload)


def test_the_box_s_diagonal_is_the_path_at_theta_zero_and_one() -> None:
    """Built apart: the report drawn at θ = 0, then at θ = 1, gives the box's corner where
    every row is at 0, then at 1, in both views and under each persistence."""
    box = _build(horizon=5).payload()["theta_box"]
    for side in (0, 1):
        drawn = {p["persistence"]: p["years"][-1] for p in _build(
            horizon=5, theta=Theta(common=float(side))).payload()["side_by_side"]}
        for path in box["paths"]:
            last = drawn[path["persistence"]]
            corners = path["every_year"]
            assert _diagonal(corners["vieillie"]["corners"], side) == pytest.approx(
                last["delta_aged"], rel=1e-12)
            assert _diagonal(corners["figee"]["corners"], side) == pytest.approx(
                last["delta_frozen"], rel=1e-12)


def test_the_first_year_carried_is_the_explorer_s_own_reading() -> None:
    """The convention the study ran on, on the same passes: the first year alone, carried,
    gives what the explorer's evaluator gives for that year's pass — at θ in both views,
    and at each corner of its box, aged. With a cost that grows, it is not the path."""
    box = _build(horizon=5).payload()["theta_box"]
    for path in box["paths"]:
        evaluation = exploration.conditional_debt(
            price=lambda knobs, view: _whole(2026, view), reform_of=lambda knobs: REFORM,
            start=START, horizon=5, spending=FROZEN, growth=GROWTH, rate=HELD,
            theta=HALF, macro_store=synthetic_macro_store(),
            persistence=path["persistence"])({})
        first = path["first_year"]
        assert first["vieillie"]["theta"] == pytest.approx(evaluation.aged_eur, rel=1e-12)
        assert first["figee"]["theta"] == pytest.approx(evaluation.frozen_eur, rel=1e-12)
        assert [label for label, _ in first["vieillie"]["corners"]] == [
            label for label, _ in evaluation.corners]
        assert [v for _, v in first["vieillie"]["corners"]] == pytest.approx(
            [v for _, v in evaluation.corners], rel=1e-12)
        assert abs(first["vieillie"]["theta"] - path["every_year"]["vieillie"]["theta"]) > 1e-5


def test_a_box_reads_only_what_the_report_asked_for() -> None:
    """Mechanical, there is no box; without the loop, the multiplier is not one of its
    rows, and one path stands where the simulator draws one."""
    assert _build(behavioural=False, macro=False).payload()["theta_box"] is None
    box = _build(horizon=5, spending=SHIPPED["part_pib_constante"]).payload()["theta_box"]
    assert box["rows"] == ["eti_all", "eti_top_decile"]
    assert [p["persistence"] for p in box["paths"]] == [None]
    assert all(len(p["every_year"][v]["corners"]) == 4 for p in box["paths"]
               for v in VIEW_KEYS)
    assert _build(horizon=5, behavioural=False).payload()["theta_box"]["rows"] == [
        MACRO_ROW]


def test_a_debt_at_theta_outside_its_box_is_refused(monkeypatch) -> None:
    """GUARD. The corners bound Δb only if each effect is monotone in its θ. A multiplier
    whose feedback at θ = ½ outruns both its ends would put Δb at θ outside the box, and
    the report is refused rather than drawn with a box that does not hold it."""
    real = retroaction.compute

    def bump(*args, theta, **kwargs):
        out = real(*args, theta=theta, **kwargs)
        if theta == 0.5:
            out = dataclasses.replace(out, balance=tuple(3 * b for b in out.balance))
        return out

    monkeypatch.setattr(retroaction, "compute", bump)
    with pytest.raises(ThetaError, match="sort de sa boîte"):
        _build(horizon=5)


def _box_payload() -> dict:
    return _build(horizon=5).payload()


@pytest.mark.parametrize("how, needle", [
    ("persistances", "persistances de la boîte"),
    ("coin manquant", "coins pour"),
    ("libellés", "ne nomment pas"),
    ("hors de la boîte", "sort de sa boîte"),
    ("pas le chemin", "n'est pas le chemin"),
    ("année", "dernière année"),
    ("sans lignes", "sans ligne"),
    ("vue manquante", "il en faut deux"),
    ("coin doublé", "chacun une fois"),
    ("ordre", "dans le même ordre"),
])
def test_a_box_a_reader_would_misread_is_refused(how: str, needle: str) -> None:
    """The report's schema holds the box to the paths: its persistences, every corner of
    its rows in each reading, the same corners throughout, Δb at θ inside them and, every
    year priced, the path itself, at the last year."""
    payload = _box_payload()
    box = payload["theta_box"]
    one = box["paths"][0]["every_year"]["vieillie"]
    if how == "persistances":
        box["paths"].pop()
    elif how == "coin manquant":
        box["paths"][1]["first_year"]["figee"]["corners"].pop()
    elif how == "libellés":
        corners = box["paths"][0]["first_year"]["figee"]["corners"]
        corners[0] = ["eti_all = 0, eti_top_decile = 0, autre = 0", corners[0][1]]
    elif how == "hors de la boîte":
        box["paths"][0]["first_year"]["vieillie"]["theta"] = 1.0
    elif how == "pas le chemin":
        values = [v for _, v in one["corners"]]
        one["theta"] = (min(values) + max(values)) / 2 + 1e-7
    elif how == "année":
        box["year"] = 2029
    elif how == "vue manquante":
        del box["paths"][1]["first_year"]["figee"]
    elif how == "coin doublé":
        one["corners"][1] = [one["corners"][0][0], one["corners"][1][1]]
    elif how == "ordre":
        corners = box["paths"][1]["first_year"]["vieillie"]["corners"]
        corners[0], corners[1] = corners[1], corners[0]
    else:
        box["rows"] = []
    with pytest.raises(ValidationError, match=needle):
        PredictifReportResponse.model_validate(payload)


def test_the_command_names_its_commit_and_where_its_passes_ran(command) -> None:
    """The report names the code that priced it, whether `src/` differed from that commit,
    and where the passes ran, as an exploration report does (PHASE10_SPEC §5)."""
    command["monkeypatch"].setattr(recherche, "code_state", lambda: ("c0ffee", True))
    code, report = command["launch"]("--horizon", "5", "--behavioural", "--macro",
                                     "--ou", "dans le conteneur, en tâche de fond")
    assert code == 0
    assert (report["commit"], report["dirty"], report["where"]) == (
        "c0ffee", True, "dans le conteneur, en tâche de fond")
    assert report["theta_box"]["rows"][-1] == MACRO_ROW
    PredictifReportResponse.model_validate(report)


def test_a_firm_reform_alone_has_only_the_multiplier_in_its_box() -> None:
    """No household channel reads a firm reform alone: its box has the multiplier's row
    only, and with no Mésange variant to read, nothing moves at its corners."""
    box = _build_firm(_firm_alone).payload()["theta_box"]
    assert box["rows"] == [MACRO_ROW]
    for path in box["paths"]:
        for reading in ("every_year", "first_year"):
            values = {v for _, v in path[reading]["vieillie"]["corners"]}
            assert len(values) == 1
