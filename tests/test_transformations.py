"""Phase 10 M4 — the named transformation that lets the IR scale into a search (§5).

The barème is not a scalar, and the grid walks only numbers (D-234). It enters the study by
`ir_bareme_echelle`: every rate of the barème in force multiplied by one factor, the
thresholds unchanged. What is held here: the arithmetic, on the law as the engine reads it;
the engine applying exactly that scale; the refusals before any pass (no law read, a scale
the reform refuses, a barème also fixed in the base); and the report naming the
transformation with the law it read, so that « 0,95 » replays.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from exploration_cases import COMMIT, START, run_search
from exploration_cases import exploration_request as _request
from impots import service
from impots.api.schemas import ExplorationReport, ExplorationRequest, ReformSpec
from impots.dette import reference
from impots.population import cli
from impots.predictif import recherche, transformations
from macro_cases import synthetic_macro_store

#: The 2026 barème as `read_ir_parameters` returns it, in miniature: three brackets.
LAW = {"year": 2026, "bareme": [{"threshold": 0.0, "rate": 0.0},
                                {"threshold": 11_600.0, "rate": 0.11},
                                {"threshold": 29_579.0, "rate": 0.30}]}
SCALE = [{"knob": "ir_bareme_echelle", "low": 0.90, "high": 1.0, "step": 0.05}]


def test_the_scale_multiplies_every_rate_and_keeps_every_threshold() -> None:
    written = transformations.expand({"ir_bareme_echelle": 0.9, "decote_taux": 0.4}, LAW)
    assert written["decote_taux"] == 0.4
    assert [b["threshold"] for b in written["ir_bareme"]] == [0.0, 11_600.0, 29_579.0]
    assert [b["rate"] for b in written["ir_bareme"]] == pytest.approx([0.0, 0.099, 0.27])
    assert transformations.expand({"ir_bareme_echelle": 1.0}, LAW)["ir_bareme"] == \
        LAW["bareme"]


def test_the_engine_applies_the_scaled_bareme_of_the_year() -> None:
    """On the real tree: the law the command reads for 2026, scaled by 0,95, is the scale
    the reformed system computes with, bracket for bracket, read back by the engine's own
    guard (`verify_bareme`) and here once more."""
    from impots.engine.reforms import PATH_BAREME, resolve
    from impots.engine.system import reformed_for

    law = recherche.law_in_force(2026)
    spec = ReformSpec.model_validate(
        transformations.expand({"ir_bareme_echelle": 0.95}, law))
    scale = resolve(reformed_for(spec, 2026).parameters, PATH_BAREME)("2026-01-01")
    assert [float(t) for t in scale.thresholds] == [b["threshold"] for b in law["bareme"]]
    assert [float(r) for r in scale.rates] == pytest.approx(
        [0.95 * b["rate"] for b in law["bareme"]], abs=1e-12)


def test_a_scale_without_the_law_in_force_is_refused() -> None:
    """« 0,95 » of what? Without the barème it scales, the factor means nothing, and an
    empty one would scale nothing and price a zero."""
    with pytest.raises(transformations.TransformationError, match="sans le droit"):
        transformations.expand({"ir_bareme_echelle": 0.95}, None)
    with pytest.raises(transformations.TransformationError, match="sans barème"):
        transformations.expand({"ir_bareme_echelle": 0.95}, {"year": 2026, "bareme": []})


@pytest.mark.parametrize("overrides, needle", [
    ({"bounds": SCALE, "base": {"ir_bareme": LAW["bareme"]}}, "fixé aussi dans la base"),
    ({"bounds": [{"knob": "ir_bareme_facteur", "low": 0.9, "high": 1, "step": 0.1}]},
     "inconnu"),
])
def test_a_transformation_the_request_cannot_honour_is_refused(overrides: dict,
                                                               needle: str) -> None:
    """GUARD 1, for a transformation: a barème fixed in the base would be overwritten by
    the scale, and a name outside the closed list is not a knob."""
    with pytest.raises(ValidationError, match=needle):
        ExplorationRequest.model_validate(_request(**overrides))


def test_a_scaled_rate_the_reform_refuses_stops_before_the_first_pass() -> None:
    """GUARD 2: a 45 % rate scaled by 2,5 is above 100 %. Refused by the reform's schema
    when the grid is checked, before any pass; and so is a grid with no law to scale."""
    law = {"year": 2026, "bareme": [*LAW["bareme"], {"threshold": 90_000.0, "rate": 0.45}]}
    request = ExplorationRequest.model_validate(_request(bounds=[
        {"knob": "ir_bareme_echelle", "low": 2.5, "high": 2.5, "step": 0.1}]))
    with pytest.raises(recherche.RechercheError, match="avant toute passe"):
        recherche.check_grid(request, law=law)
    with pytest.raises(recherche.RechercheError, match="sans le droit"):
        recherche.check_grid(request)


def _cost(reform, view: str) -> float:
    """A scale that costs 40 Md€ per unit below one, 90 % of it when frozen; any other
    reform 1 Md€."""
    knobs = reform.model_dump(exclude_none=True)
    if "ir_bareme" not in knobs:
        return 1e9
    rate = knobs["ir_bareme"][1]["rate"]
    return 4e10 * (1 - rate / 0.11) * (1.0 if view == "vieillie" else 0.9) + 1e8


def test_the_report_names_the_transformation_and_the_law_it_read() -> None:
    """The bundle reads « 0,95 » and the report says of what: the transformation, what it
    writes, and the barème in force it scaled, the year's. A report that drops them is
    refused, since its knobs would no longer replay."""
    seen: list = []

    def price(reform, view):
        seen.append((reform.model_dump(exclude_none=True), view))
        return SimpleNamespace(cost=_cost(reform, view), inputs=None, impulse=None,
                               uncovered={}, deciles=None)

    request = ExplorationRequest.model_validate(_request(bounds=SCALE, macro=False))
    report = recherche.run(request, price=price,
                           hypotheses=service.predictif_hypotheses(request), start=START,
                           law=LAW, commit=COMMIT, computed="2026-10-21")
    (named,) = report["hypotheses"]["transformations"]
    assert named["name"] == "ir_bareme_echelle" and named["writes"] == ["ir_bareme"]
    assert named["year"] == 2026 and named["law"] == {"bareme": LAW["bareme"]}
    assert [e["knobs"] for e in report["searches"][0]["evaluations"]] == [
        {"ir_bareme_echelle": 0.9}, {"ir_bareme_echelle": 0.95},
        {"ir_bareme_echelle": 1.0}]
    assert seen[0][0]["ir_bareme"][1]["rate"] == pytest.approx(0.099)
    ExplorationReport.model_validate(json.loads(json.dumps(report)))
    report["hypotheses"]["transformations"] = []
    with pytest.raises(ValidationError, match="sans le droit qu'elle a lu"):
        ExplorationReport.model_validate(json.loads(json.dumps(report)))


def test_the_command_reads_the_law_of_the_first_projected_year(monkeypatch,
                                                                tmp_path) -> None:
    """The command scales the barème of the year it prices, the first projected one, and
    reads the law only when a transformation asks for it."""
    years: list = []
    seen: list = []

    def law_in_force(year):
        years.append(year)
        return LAW

    def stub(request, *, uprating, macro=False, view="vieillie"):
        seen.append(request.reform.model_dump(exclude_none=True))
        return SimpleNamespace(cost=_cost(request.reform, view), view=view, note="",
                               deciles=[], inputs=None, impulse=None, uncovered={})

    monkeypatch.setattr(service, "price_first_year", stub)
    monkeypatch.setattr(service, "predictif_macro_store", synthetic_macro_store)
    monkeypatch.setattr(reference, "start_from_accounts", lambda year: START)
    monkeypatch.setattr(recherche, "code_state", lambda: (COMMIT, False))
    monkeypatch.setattr(recherche, "law_in_force", law_in_force)
    for name, bounds in (("echelle", SCALE), ("decote", None)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(_request(name=name, macro=False,
                                            **({"bounds": bounds} if bounds else {}))),
                        encoding="utf-8")
        assert cli.main(["exploration", str(path), "--out-dir", str(tmp_path)]) == 0
    assert years == [START.year + 1]
    assert seen[0]["ir_bareme"] == transformations.expand(
        {"ir_bareme_echelle": 0.9}, LAW)["ir_bareme"]
    assert run_search(_request())["hypotheses"]["transformations"] == []
