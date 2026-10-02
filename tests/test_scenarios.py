"""F2 — scenarios, A/B comparison, and the budget-neutral solver.

The load-bearing tests here are the REFUSALS. A solver that quietly answers a question it
cannot answer is worse than one that has no answer, because its number carries the same
provenance as a real one. So each refusal has a test that fails if the refusal is removed,
and the two honesty properties — no last iterate as an answer, no differencing of banded
layers — have tests that fail if the code is made to "just return something".
"""

from __future__ import annotations

import json

import pytest

from impots import scenarios as sc
from impots.api.schemas import ReformSpec


def make(**overrides):
    base = dict(name="essai", reform=ReformSpec(decote_taux=0.5), year=2024,
                created="2026-09-08", source="PLF 2027, art. 3")
    return sc.Scenario(**{**base, **overrides})


# --------------------------------------------------------------------------- #
# Provenance is part of the object
# --------------------------------------------------------------------------- #


def test_a_scenario_without_a_source_is_refused():
    """Fails if `source` becomes optional, or defaults to "".

    A scenario exists to pre-register a chiffrage. One that cannot say which article it
    encodes cannot be confronted later with the évaluation préalable or the outturn, so
    it is not a pre-registration — it is a saved slider position.
    """
    with pytest.raises(sc.ScenarioError, match="source"):
        make(source="   ")


def test_a_scenario_without_a_readable_date_is_refused():
    """Fails if `created` is stored as free text instead of parsed."""
    with pytest.raises(sc.ScenarioError, match="préenregistrement"):
        make(created="la semaine dernière")


def test_a_scenario_without_a_name_is_refused():
    with pytest.raises(sc.ScenarioError):
        make(name="  ")


def test_saving_over_an_existing_scenario_is_refused(tmp_path):
    """Fails if `save` overwrites, or gains a `force` flag that callers reach for.

    Overwriting lets a chiffrage be revised after the fact while keeping its original
    date, which is exactly what pre-registration exists to prevent.
    """
    scenario = make()
    scenario.save(tmp_path)
    with pytest.raises(sc.ScenarioError, match="existe déjà"):
        scenario.save(tmp_path)


# --------------------------------------------------------------------------- #
# Round trip
# --------------------------------------------------------------------------- #


def test_a_multi_knob_scenario_round_trips(tmp_path):
    """Fails if `to_dict` drops knobs or `load` rebuilds a partial reform."""
    reform = ReformSpec(decote_taux=0.45, rsa_montant_de_base=700.0,
                        csg_activite_imposable=0.03)
    make(name="multi", reform=reform, note="trois boutons").save(tmp_path)

    back = sc.load("multi", tmp_path)
    assert back.reform.decote_taux == pytest.approx(0.45)
    assert back.reform.rsa_montant_de_base == pytest.approx(700.0)
    assert back.reform.csg_activite_imposable == pytest.approx(0.03)
    assert back.created == "2026-09-08" and back.source == "PLF 2027, art. 3"
    assert back.note == "trois boutons"


def test_a_scenario_whose_knob_no_longer_validates_fails_loudly(tmp_path):
    """Fails if `load` uses `model_construct`, or catches and shrugs.

    A stored knob that no longer validates means it was renamed or its bounds moved.
    Finding that out at load time is the point of going through the wire model; silently
    dropping it would price a reform the file does not describe.
    """
    path = tmp_path / "vieux.json"
    path.write_text(json.dumps({
        "name": "vieux", "year": 2024, "created": "2026-01-01", "source": "s",
        "reform": {"un_bouton_supprime": 0.4},
    }), encoding="utf-8")
    with pytest.raises(sc.ScenarioError, match="ne valide plus"):
        sc.load("vieux", tmp_path)


def test_available_lists_what_was_saved(tmp_path):
    assert sc.available(tmp_path) == []
    make(name="b").save(tmp_path)
    make(name="a").save(tmp_path)
    assert sc.available(tmp_path) == ["a", "b"]


# --------------------------------------------------------------------------- #
# The refusals the solver is built around
# --------------------------------------------------------------------------- #


#: Written out rather than read from `BANDED_QUANTITIES`, and that is the whole point.
#: The first version parametrized over `sorted(sc.BANDED_QUANTITIES)` — so deleting an
#: entry from the dict deleted its own test case, and the suite went from 35 green to 33
#: green while the solver happily answered `quantity="cell_bound"` with a number. A check
#: derived from the thing it checks cannot fail when that thing is wrong; this is the
#: D-044 shape, and it had got into the test guarding F2's headline refusal.
BANDED_BY_NAME = ("behavioural", "macro", "cell_bound", "composition")


@pytest.mark.parametrize("quantity", BANDED_BY_NAME)
def test_the_solver_refuses_every_banded_quantity(quantity):
    """THE headline refusal of F2. Fails if `refuse_banded` becomes a no-op, if an entry
    is dropped from `BANDED_QUANTITIES`, or if a caller can pass `quantity="behavioural"`
    and get a number.

    Root-finding on an interval is not well posed: every knob value whose interval
    straddles zero answers "which value makes this zero", and the solver would return
    whichever the search reached first.
    """
    with pytest.raises(sc.ScenarioError, match="MÉCANIQUE"):
        sc.solve_budget_neutral("decote_taux", lambda x: x - 0.5,
                                bracket=(0.0, 1.0), quantity=quantity)


def test_the_named_banded_quantities_are_all_still_declared():
    """Fails if an entry is removed from BANDED_QUANTITIES without a decision.

    The parametrized test above would then refuse it anyway — via the allowlist — but
    with the generic "unknown quantity" message instead of the reason that quantity is an
    interval. This test is what keeps the reasons alive.
    """
    assert set(BANDED_BY_NAME) == set(sc.BANDED_QUANTITIES)


@pytest.mark.parametrize("quantity", [
    "behavioral", "Behavioural", "BEHAVIOURAL", "cell-bound", "macro ", "",
    "comportemental", "bande", "nonsense", "Mechanical", "mechanical ",
])
def test_a_quantity_that_is_not_exactly_mechanical_is_refused(quantity):
    """The solver takes an ALLOWLIST, not a denylist.

    Fails if `refuse_banded` goes back to `if quantity in BANDED_QUANTITIES`. Under that
    version every string here — an English spelling, a capital, a hyphen, a trailing
    space, the empty string — sailed through and came back
    `converged=True, value=0.5`, indistinguishable from a legitimate answer. A denylist
    refuses what it recognises, and the caller who most needs refusing is the one who
    typed the name slightly wrong.
    """
    with pytest.raises(sc.ScenarioError):
        sc.solve_budget_neutral("k", lambda x: (x - 0.5) * 1e12,
                                bracket=(0.0, 1.0), quantity=quantity,
                                tolerance_eur=1e6)


def test_the_refusal_names_the_quantity_and_says_why():
    """Fails if the message becomes generic. A refusal a caller cannot act on is a
    refusal they will work around."""
    with pytest.raises(sc.ScenarioError) as caught:
        sc.solve_budget_neutral("x", lambda v: v, bracket=(0, 1), quantity="macro")
    message = str(caught.value)
    assert "macro" in message
    assert "intervalle" in message


def test_the_mechanical_layer_is_accepted():
    """The kill test for the refusal above: if this failed too, the refusal would be
    proving nothing about banded quantities in particular."""
    result = sc.solve_budget_neutral("x", lambda v: (v - 0.5) * 1e12,
                                     bracket=(0.0, 1.0), quantity="mechanical")
    assert result.converged and result.value == pytest.approx(0.5)


def test_a_non_scalar_knob_cannot_be_solved():
    """Fails if `knob_pricer` stops checking, and the solver starts passing floats to a
    field that wants a list of brackets."""
    with pytest.raises(sc.ScenarioError, match="scalaire"):
        sc.knob_pricer("ir_bareme", year=2024)


def test_an_unknown_knob_is_refused_before_any_engine_run():
    with pytest.raises(sc.ScenarioError, match="n'est pas un bouton"):
        sc.knob_pricer("taux_magique", year=2024)


def test_scalar_knobs_is_derived_from_the_wire_model():
    """Fails if `scalar_knobs` becomes a hand-maintained list that drifts.

    Derived means a knob added to ReformSpec is solvable the day it lands.
    """
    known = set(sc.scalar_knobs())
    assert "decote_taux" in known and "rsa_montant_de_base" in known
    assert "ir_bareme" not in known
    assert "ifi_obligations_declaratives" not in known, "a regime is not a scalar"
    assert known <= set(ReformSpec.model_fields)
    assert len(known) > 30


@pytest.mark.parametrize("knob", [
    "af_plafond_tranche_2_base", "ifi_decote_taux", "ifi_decote_parametre",
    "ifi_decote_borne_superieure",
])
def test_a_knob_with_a_cross_field_validator_is_still_scalar(knob: str):
    """Fails if `scalar_knobs` goes back to probing with a value instead of reading the
    annotation.

    These four take a single number, but their validators are CROSS-FIELD — tranche 2's
    ceiling must sit above tranche 1's, and the three IFI décote parameters are coupled —
    so a probe of `{knob: 0.5}` alone is rejected. The first version of `scalar_knobs`
    read that rejection as "not a scalar" and refused to solve them, with a message that
    named the wrong problem.
    """
    assert knob in sc.scalar_knobs()
    sc.knob_pricer(knob, year=2024)  # must not raise


# --------------------------------------------------------------------------- #
# The root-finder
# --------------------------------------------------------------------------- #


def test_the_solver_finds_a_known_root():
    """Cost is -3 bn at 0 and +7 bn at 1, so neutral at 0.30 exactly."""
    result = sc.solve_budget_neutral("decote_taux", lambda x: -3e9 + 10e9 * x,
                                     bracket=(0.0, 1.0), tolerance_eur=1e6)
    assert result.converged
    assert result.value == pytest.approx(0.30, abs=1e-4)
    assert abs(result.cost_at_value) <= 1e6


def test_the_solver_hits_a_non_zero_target():
    """Budget neutrality is the default question, not the only one: a reform may be
    meant to raise 2 bn. Fails if `target_eur` is ignored."""
    result = sc.solve_budget_neutral("k", lambda x: 10e9 * x,
                                     bracket=(0.0, 1.0), target_eur=2e9,
                                     tolerance_eur=1e6)
    assert result.converged and result.value == pytest.approx(0.2, abs=1e-4)


def test_a_cost_that_never_changes_sign_returns_no_answer():
    """Fails if the solver returns a bracket end, or extrapolates outside the bracket.

    No value of this knob neutralises this reform. Saying so is the answer.
    """
    result = sc.solve_budget_neutral("k", lambda x: 1e9 + x, bracket=(0.0, 1.0))
    assert not result.converged
    assert result.value is None
    assert "DEUX BORNES" in result.message


def test_a_run_that_does_not_converge_does_not_return_its_last_iterate():
    """The honesty property, and the one most likely to be "fixed" away.

    Fails the moment the final return becomes `SolverResult(knob, x1, f1, ...)`. A
    solver that hands back its last try presents an unconverged guess with exactly the
    provenance of a converged answer.
    """
    result = sc.solve_budget_neutral("k", lambda x: (x - 0.3) ** 3 * 1e12,
                                     bracket=(0.0, 0.5), max_iterations=4,
                                     tolerance_eur=1.0)
    assert not result.converged
    assert result.value is None and result.cost_at_value is None
    assert "PAS rendue" in result.message


def test_the_solver_never_evaluates_outside_its_bracket():
    """Fails if the secant fallback is removed and it extrapolates.

    Knob bounds are not decoration: ReformSpec would reject an out-of-range value, and
    a solver that wanders outside the bracket spends a population run to find that out.
    """
    seen = []

    def price(x):
        seen.append(x)
        # Nearly flat then steep: the shape that makes a naive secant overshoot.
        return -1e9 + 1e9 * (x ** 8)

    sc.solve_budget_neutral("k", price, bracket=(0.0, 1.2), max_iterations=10,
                            tolerance_eur=1e5)
    assert seen, "le solveur n'a rien évalué"
    assert min(seen) >= 0.0 and max(seen) <= 1.2, f"sorti de l'intervalle : {seen}"


def test_the_solver_respects_its_evaluation_cap():
    """Each evaluation is a population run, so the cap is minutes of wall clock.

    Fails if `max_iterations` stops bounding the loop.
    """
    seen = []

    def price(x):
        seen.append(x)
        return (x - 0.31415926) * 1e12

    sc.solve_budget_neutral("k", price, bracket=(0.0, 1.0), max_iterations=5,
                            tolerance_eur=1e-9)
    assert len(seen) <= 5


def test_an_empty_bracket_is_refused():
    with pytest.raises(sc.ScenarioError, match="intervalle vide"):
        sc.solve_budget_neutral("k", lambda x: x, bracket=(1.0, 1.0))


def test_a_bracket_end_that_is_already_neutral_is_reported_as_such():
    """Fails if the solver iterates from an answer it already has."""
    result = sc.solve_budget_neutral("k", lambda x: x * 1e12, bracket=(0.0, 1.0),
                                     tolerance_eur=1e6)
    assert result.converged and result.value == 0.0
    assert "borne basse" in result.message


# --------------------------------------------------------------------------- #
# A/B comparison
# --------------------------------------------------------------------------- #


def test_comparison_differences_the_mechanical_layer_and_only_that():
    """Fails if `compare` starts differencing the behavioural band or the macro fan.

    The difference of two intervals is an interval. Printing a single number for it
    would invent precision neither scenario has — the same category error the reports
    already refuse.
    """
    priced = {
        "a": {"mechanical": -1.2e9, "behavioural": (-1.5e9, -0.9e9), "macro": (0.0, 0.2)},
        "b": {"mechanical": 3.4e9, "behavioural": (2.8e9, 4.1e9), "macro": (-0.1, 0.3)},
    }
    a, b = make(name="a"), make(name="b")
    comparison = sc.compare(a, b, lambda s: priced[s.name])

    by_layer = {layer.layer: layer for layer in comparison.layers}
    assert by_layer["mechanical"].comparable is True
    assert by_layer["behavioural"].comparable is False
    assert by_layer["macro"].comparable is False
    assert comparison.mechanical_gap == pytest.approx(4.6e9)


def test_a_banded_layer_still_shows_both_sides():
    """Not comparable is not the same as not shown. Fails if the banded layers are
    dropped instead of displayed side by side."""
    comparison = sc.compare(
        make(name="a"), make(name="b"),
        lambda s: {"mechanical": 1.0, "behavioural": (0.0, 2.0)})
    banded = next(layer for layer in comparison.layers if layer.layer == "behavioural")
    assert banded.a == (0.0, 2.0) and banded.b == (0.0, 2.0)
    assert "non différencié" in banded.note


def test_a_missing_mechanical_layer_yields_no_gap():
    """Fails if `mechanical_gap` coerces None to zero — a comparison that could not be
    made reading as a comparison that found no difference."""
    comparison = sc.compare(make(name="a"), make(name="b"), lambda s: {})
    assert comparison.mechanical_gap is None


# --------------------------------------------------------------------------- #
# End to end, on the real population
# --------------------------------------------------------------------------- #


@pytest.mark.slow
def test_the_solver_neutralises_a_real_reform_on_the_population(tmp_path):
    """The whole chain: a scenario that costs money, and the CSG rate that pays for it.

    Slow because each evaluation is a population run. Fails if `knob_pricer` returns a
    sign-flipped cost, if the run is not deterministic across calls (the root-finder
    would chase sampling noise), or if the wiring drifts.
    """
    pytest.importorskip("polars")
    from pathlib import Path

    frame_path = Path("data/processed/population_2024.parquet")
    if not frame_path.exists():
        pytest.skip("population non construite")

    import polars as pl
    frame = pl.read_parquet(frame_path)

    costly = ReformSpec(rsa_montant_de_base=700.0)
    price = sc.knob_pricer("csg_activite_imposable", year=2024, base=costly,
                           frame=frame, households=5_000)

    # Determinism first: the same knob value must give the same cost twice, or the
    # root-finder is chasing the draw rather than the reform.
    baseline_rate = 0.024
    assert price(baseline_rate) == pytest.approx(price(baseline_rate), rel=1e-9)

    result = sc.solve_budget_neutral(
        "csg_activite_imposable", price, bracket=(0.024, 0.20),
        max_iterations=8, tolerance_eur=200e6)
    assert result.converged, result.message
    assert 0.024 < result.value < 0.20


# --------------------------------------------------------------------------- #
# The HTTP surface: read only, on purpose
# --------------------------------------------------------------------------- #


@pytest.fixture()
def client_with_scenarios(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from impots.api.main import app

    monkeypatch.setattr(sc, "SCENARIOS", tmp_path)
    make(name="alpha", source="PLF 2027, art. 3").save(tmp_path)
    return TestClient(app), tmp_path


def test_scenarios_can_be_listed_and_read(client_with_scenarios):
    client, _ = client_with_scenarios
    listing = client.get("/scenarios").json()
    assert [row["name"] for row in listing["scenarios"]] == ["alpha"]
    assert listing["scenarios"][0]["knobs"] == ["decote_taux"]
    assert listing["unreadable"] == {}

    detail = client.get("/scenarios/alpha").json()
    assert detail["reform"]["decote_taux"] == pytest.approx(0.5)
    assert detail["source"] == "PLF 2027, art. 3"


@pytest.mark.parametrize("content", [
    '{"name": "tronque", "year": 2024,',
    "<<<<<<< HEAD",
    '{"name": "x", "year": 2024, "source": "s", "reform": {}}',
])
def test_one_malformed_file_does_not_take_down_the_whole_listing(
        client_with_scenarios, content):
    """Fails if `load` stops wrapping everything, or if the handler stops catching.

    A truncated write, an unresolved merge marker or a missing `created` used to escape
    as a raw JSONDecodeError or KeyError and 500 the entire GET /scenarios — so ONE bad
    file hid every good one. The bad row is named; the good rows still list.
    """
    client, directory = client_with_scenarios
    (directory / "casse.json").write_text(content, encoding="utf-8")
    response = client.get("/scenarios")
    assert response.status_code == 200
    body = response.json()
    assert [row["name"] for row in body["scenarios"]] == ["alpha"]
    assert "casse" in body["unreadable"]
    assert client.get("/scenarios/casse").status_code == 422


def test_an_unreadable_scenario_is_listed_with_its_reason_not_hidden(
        client_with_scenarios):
    """Fails if `scenarios_list` swallows the broken one.

    A scenario that silently vanishes from the picker is a chiffrage that silently
    stops being confrontable — the failure mode is invisible, which is the worst kind.
    """
    client, directory = client_with_scenarios
    (directory / "casse.json").write_text(json.dumps({
        "name": "casse", "year": 2024, "created": "2026-01-01", "source": "s",
        "reform": {"bouton_disparu": 1.0},
    }), encoding="utf-8")
    listing = client.get("/scenarios").json()
    assert [row["name"] for row in listing["scenarios"]] == ["alpha"]
    assert "casse" in listing["unreadable"]
    assert "ne valide plus" in listing["unreadable"]["casse"]
    assert client.get("/scenarios/casse").status_code == 422


def test_there_is_no_way_to_register_a_scenario_over_http(client_with_scenarios):
    """Fails the day someone adds POST /scenarios.

    A scenario's value is its date. A date the HTTP surface can mint is a date anyone
    can mint, so registration stays in the CLI where it lands in the working tree and
    gets committed (D-092).
    """
    client, _ = client_with_scenarios
    assert client.post("/scenarios", json={"name": "x"}).status_code == 405
    routes = {
        (route.path, method)
        for route in client.app.routes
        for method in getattr(route, "methods", set())
    }
    writes = {(path, method) for path, method in routes
              if path.startswith("/scenarios") and method in {"POST", "PUT", "DELETE",
                                                              "PATCH"}}
    assert not writes, f"surface d'écriture apparue : {writes}"


def test_an_unknown_scenario_is_a_404(client_with_scenarios):
    client, _ = client_with_scenarios
    assert client.get("/scenarios/jamais_vu").status_code == 404


# --- what the adversarial review of 2026-09-08 found -------------------------------


@pytest.mark.parametrize("name", ["../evade", "a/b", "..", ".", "/abs", "x" * 65,
                                  "-leading", " space", "plf2027\n"])
def test_a_scenario_name_that_is_a_path_is_refused(name):
    """Fails if `save` goes back to `directory / f"{name}.json"` unguarded.

    `Scenario(name="../plf2027").save(d)` wrote OUTSIDE the scenario directory, where
    `available()` never lists it: a chiffrage that looks registered and is not. Refused
    rather than sanitised — silently renaming what someone asked for is its own surprise.
    The trailing newline passed `re.match` with `$`, which matches before a final `\n`
    (D-173).
    """
    with pytest.raises(sc.ScenarioError):
        make(name=name)


def test_a_saved_scenario_lands_inside_its_directory(tmp_path):
    """The positive half: the guard must not have broken ordinary names."""
    path = make(name="plf2027.art3-v2").save(tmp_path)
    assert path.parent == tmp_path
    assert sc.available(tmp_path) == ["plf2027.art3-v2"]


def test_saving_refuses_to_write_through_a_planted_link(tmp_path):
    """Fails if `save` goes back to `exists()` then `write_text`.

    A dangling link answers False to `exists()`, and `write_text` follows it: the
    scenario lands wherever the link points, outside the directory the listing reads
    (D-173). Exclusive creation refuses a link, dangling or not, in one system call.
    """
    dossier = tmp_path / "scenarios"
    dossier.mkdir()
    dehors = tmp_path / "dehors.json"
    (dossier / "essai.json").symlink_to(dehors)
    with pytest.raises(sc.ScenarioError):
        make().save(dossier)
    assert not dehors.exists()


def test_loading_refuses_a_scenario_that_is_a_link(tmp_path):
    """The read half: a link in the directory serves a file that lives elsewhere."""
    ailleurs = tmp_path / "ailleurs"
    ailleurs.mkdir()
    make().save(ailleurs)
    dossier = tmp_path / "scenarios"
    dossier.mkdir()
    (dossier / "essai.json").symlink_to(ailleurs / "essai.json")
    with pytest.raises(sc.ScenarioError, match="lien"):
        sc.load("essai", dossier)


@pytest.mark.parametrize("content,fragment", [
    ('{"name": "x", "year": 2024,', "illisible"),
    ("pas du json du tout", "illisible"),
    ("[1, 2, 3]", "objet JSON"),
    ('{"name": "x", "year": 2024, "source": "s", "reform": {}}', "incomplet"),
    ('{"name": "x", "year": "pas un entier", "created": "2026-01-01",'
     ' "source": "s", "reform": {}}', "incomplet"),
    # D-173: a non-string field escaped as AttributeError and 500'd the listing; a
    # string of tags became one tag per letter; the name inside the file chose the
    # name of every output derived from it; an infinite threshold validated.
    ('{"name": "casse", "year": 2024, "created": "2026-01-01", "source": 7,'
     ' "reform": {}}', "incomplet"),
    ('{"name": "casse", "year": 2024, "created": "2026-01-01", "source": "s",'
     ' "note": 7, "reform": {}}', "incomplet"),
    ('{"name": "casse", "year": 2024, "created": "2026-01-01", "source": "s",'
     ' "tags": "abc", "reform": {}}', "incomplet"),
    ('{"name": "autre", "year": 2024, "created": "2026-01-01", "source": "s",'
     ' "reform": {}}', "déclare"),
    ('{"name": "casse", "year": 2024, "created": "2026-01-01", "source": "s",'
     ' "reform": {"ir_bareme": [{"threshold": 0, "rate": 0.1},'
     ' {"threshold": Infinity, "rate": 0.5}]}}', "ne valide plus"),
])
def test_every_way_a_file_can_be_wrong_is_a_scenario_error(tmp_path, content, fragment):
    """Fails if `load` wraps only the ReformSpec validation, as the first version did.

    A truncated write, a merge-conflict marker or a missing `created` then escaped as a
    raw JSONDecodeError or KeyError — which tracebacked `impots scenario list` and 500'd
    GET /scenarios, taking every OTHER scenario down with the one bad file.
    """
    (tmp_path / "casse.json").write_text(content, encoding="utf-8")
    with pytest.raises(sc.ScenarioError, match=fragment):
        sc.load("casse", tmp_path)


def test_one_bad_file_does_not_hide_the_good_ones(tmp_path):
    """The property that matters downstream: a listing survives a broken row."""
    make(name="bon").save(tmp_path)
    (tmp_path / "aaa.json").write_text('{"name": "aaa",', encoding="utf-8")
    assert sc.available(tmp_path) == ["aaa", "bon"]
    sc.load("bon", tmp_path)  # must not raise
    with pytest.raises(sc.ScenarioError):
        sc.load("aaa", tmp_path)


def test_both_bracket_ends_are_validated_before_any_evaluation():
    """Fails if the solver stops calling `price.validate` on the bracket ends.

    Without it, `price(low)` completes — minutes of population run — and then
    `price(high)` raises a raw pydantic ValidationError that escapes the solver and the
    CLI as a traceback. `ifi_decote_taux` is the live case: declared `ge=0, le=1` but
    cross-field-rejected above 0.0125, so bracketing at the declared range is a
    reasonable thing to do and deserves an answer in milliseconds.
    """
    seen = []

    def price(value):
        seen.append(value)
        return value - 0.5

    def validate(value):
        if value > 1.0:
            raise sc.ScenarioError(f"{value} hors bornes")

    price.validate = validate
    with pytest.raises(sc.ScenarioError, match="hors bornes"):
        sc.solve_budget_neutral("k", price, bracket=(0.0, 1.5))
    assert seen == [], f"le solveur a évalué avant de valider : {seen}"


def test_the_real_pricer_validates_a_cross_field_bound_without_running_anything():
    """The same property against the real ReformSpec, no population involved."""
    price = sc.knob_pricer("ifi_decote_taux", year=2024)
    price.validate(0.01)  # inside the cross-field bound: fine
    with pytest.raises(sc.ScenarioError, match="refusé par le modèle"):
        price.validate(1.0)


def test_a_cap_below_two_evaluations_is_refused():
    """Bracketing needs two evaluations, so a cap of 1 cannot be honoured.

    Fails if the solver silently exceeds the cap instead — it used to return
    `iterations=2` for `max_iterations=1`, which is a cap that does not cap.
    """
    with pytest.raises(sc.ScenarioError, match="minimum"):
        sc.solve_budget_neutral("k", lambda x: x - 0.3, bracket=(0.0, 1.0),
                                max_iterations=1)


def test_no_sign_change_does_not_claim_no_root_exists():
    """Two endpoint samples cannot support a universal claim.

    This cost has roots at 0.30 AND 0.70, both strictly inside the bracket, so both ends
    are positive. The old message said "aucune valeur de ce bouton n'y neutralise la
    réforme", which is simply false here. Fails if that wording comes back.
    """
    result = sc.solve_budget_neutral("k", lambda x: (x - 0.3) * (x - 0.7) * 1e12,
                                     bracket=(0.0, 1.0), tolerance_eur=1e6)
    assert not result.converged and result.value is None
    assert "Aucune valeur" not in result.message
    assert "deux racines" in result.message


def test_the_no_sign_change_message_is_stated_against_the_target():
    """With a non-zero target the two printed costs can have opposite signs while the
    GAPS to the target do not. Fails if the message goes back to saying the costs
    themselves do not change sign, which contradicts the numbers beside it."""
    result = sc.solve_budget_neutral("k", lambda x: -1e9 + 3e9 * x, bracket=(0.0, 1.0),
                                     target_eur=5e9)
    assert not result.converged
    assert "écart à la cible de même signe" in result.message


# --- the command line, where the refusals have to arrive before the cost ------------


def run_cli(argv, monkeypatch=None):
    from impots.population import cli

    return cli.main(argv)


def test_the_cli_refuses_a_banded_quantity_before_touching_the_population(
        monkeypatch, capsys, tmp_path):
    """Fails if `cmd_scenario_solve` goes back to refusing AFTER building the pricer.

    The module makes `refuse_banded` public precisely so a caller can ask the question
    without paying for the answer. The first version read the parquet, built the pricer
    and only then let the solver refuse — which is the cost the refusal exists to avoid.
    Any read of the population here is the failure.
    """
    import polars as pl

    def forbidden(*args, **kwargs):
        raise AssertionError("la population a été lue avant le refus")

    monkeypatch.setattr(pl, "read_parquet", forbidden)
    code = run_cli(["scenario", "solve", "decote_taux", "--low", "0", "--high", "1",
                    "--quantity", "macro", "--dir", str(tmp_path)])
    assert code == 1
    assert "MÉCANIQUE" in capsys.readouterr().err


def test_the_cli_refuses_an_unrecognised_quantity_too(monkeypatch, capsys, tmp_path):
    """The allowlist, reachable from the command line."""
    import polars as pl

    monkeypatch.setattr(pl, "read_parquet",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("lu")))
    code = run_cli(["scenario", "solve", "decote_taux", "--low", "0", "--high", "1",
                    "--quantity", "behavioral", "--dir", str(tmp_path)])
    assert code == 1
    assert "Grandeur inconnue" in capsys.readouterr().err


@pytest.mark.parametrize("payload,fragment", [
    (None, "illisible"),
    ('{"decote_taux": 5.0}', "ne valide pas"),
    ("pas du json", "pas du JSON"),
])
def test_the_cli_turns_a_bad_reform_file_into_a_refusal(tmp_path, capsys, payload,
                                                        fragment):
    """Fails if `_load_reform` is called unguarded again.

    A missing file gave a FileNotFoundError traceback and an out-of-range knob gave a
    raw pydantic ValidationError — and the `if reform is None` guard below the call was
    unreachable, since the call raised before it.
    """
    if payload is None:
        path = str(tmp_path / "absent.json")
    else:
        path = str(tmp_path / "r.json")
        (tmp_path / "r.json").write_text(payload, encoding="utf-8")
    code = run_cli(["scenario", "save", "essai", "--reform", path,
                    "--source", "PLF 2027 art. 3", "--dir", str(tmp_path)])
    assert code == 1
    assert fragment in capsys.readouterr().err


def test_the_cli_lists_around_a_malformed_file(tmp_path, capsys):
    """Fails if `list` aborts on the first bad row again.

    A truncated `aaa.json` used to kill the command with a JSONDecodeError before
    `rsa_700` was ever printed — every scenario sorting after the bad one vanished.
    """
    make(name="bon").save(tmp_path)
    (tmp_path / "aaa.json").write_text('{"name": "aaa", "year": 2024,', encoding="utf-8")
    assert run_cli(["scenario", "list", "--dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "aaa" in out and "ILLISIBLE" in out
    assert "bon" in out, "le bon scénario a disparu derrière le mauvais"


# --- F3 M5 (S2): the trajectory endpoints -------------------------------------------


def test_the_trajectory_endpoints_are_read_only(client_with_scenarios):
    """A trajectory is N population runs twice over — minutes per year — so it is
    produced by the CLI and only READ over HTTP. Fails the day a POST appears."""
    client, _ = client_with_scenarios
    routes = {(r.path, m) for r in client.app.routes
              for m in getattr(r, "methods", set())}
    writes = {(p, m) for p, m in routes
              if p.startswith("/trajectoires") and m in {"POST", "PUT", "DELETE", "PATCH"}}
    assert not writes, f"surface d'écriture apparue : {writes}"


def test_an_unknown_trajectory_is_a_404(client_with_scenarios):
    client, _ = client_with_scenarios
    assert client.get("/trajectoires/jamais_vue").status_code == 404


@pytest.mark.parametrize("name", ["%2E%2E", "alpha%0A"])
def test_a_trajectory_name_that_is_a_path_is_refused(client_with_scenarios, name):
    """The name reaches a file path, so it takes the same identifier rule as scenarios
    and chiffrages (D-094). Fails if it is interpolated unguarded.

    Exactly 422, through forms the router lets reach the handler. The first version
    sent `..%2F..%2Fetc`, which the router answers itself with a 404 before the handler
    runs, and it accepted 404 — so deleting the guard left it green (D-173). The
    trailing newline is the form that passed `re.match` with `$`.
    """
    client, _ = client_with_scenarios
    assert client.get(f"/trajectoires/{name}").status_code == 422


def test_the_committed_trajectory_artefact_validates(client_with_scenarios):
    """The worked example on disk must parse through the wire model — a artefact the UI
    cannot read is an artefact that will fail silently in a browser."""
    from pathlib import Path

    from impots.api.schemas import TrajectoryResponse

    path = Path(__file__).resolve().parents[1] / "reports" / "trajectoire_gel_bareme.json"
    if not path.exists():
        pytest.skip("trajectoire non calculée")
    payload = TrajectoryResponse.model_validate_json(path.read_text(encoding="utf-8"))
    assert payload.years, "artefact vide"
    assert payload.banner.startswith("Ce qui est chiffré")
    bases = {y.basis for y in payload.years}
    assert bases <= {"legislated", "reconducted"}
    # The uprating class must widen with the horizon — the fact M5 asks to make visible.
    widths = [abs(y.uprating_aged_eur - y.uprating_frozen_eur) for y in payload.years]
    assert widths[-1] > widths[0], "la classe vieillissement doit s'élargir avec l'horizon"
