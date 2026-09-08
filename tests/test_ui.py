"""M5 — the single-file UI, checked structurally.

There is no browser here and no intention of adding one. These are static checks on the
source, in the spirit of `test_standing_rules.py`: they pin the properties §4 makes
non-negotiable, and they would each fail on a plausible edit.

The one that matters most is `test_the_fan_cannot_render_without_its_strip`. §4 says the
fan never renders without its assumptions strip, and the cheapest way to violate that is
to move the strip into a `<details>` or an optional branch six months from now.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parents[1] / "ui" / "index.html"


@pytest.fixture(scope="module")
def source() -> str:
    return UI.read_text(encoding="utf-8")


def _function(source: str, name: str) -> str:
    """The body of one top-level JS function, by brace matching."""
    start = source.index(f"function {name}(")
    depth, i = 0, source.index("{", start)
    for end in range(i, len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(f"{name} is not brace-balanced")


# --- the fan exists and is wired ----------------------------------------------------


def test_the_fan_renderer_exists_and_is_called(source: str):
    assert "function renderFan(" in source
    assert "renderFan(data)" in _function(source, "renderPopulation")


def test_the_macro_flag_is_sent(source: str):
    assert 'id="wantMacro"' in source
    assert 'macro: $("wantMacro").checked' in source


def test_the_l4_placeholder_is_gone(source: str):
    """It used to say "à venir · phase 3". The layer exists now."""
    assert "à venir · phase 3" not in source
    assert "<b>L4</b>" in source


# --- what §4 forbids the fan to render without --------------------------------------


@pytest.mark.parametrize("field", [
    "cycle_state", "design", "leakage", "horizons", "parameters_vintage", "grade",
    "covered_share", "simulation_conditions", "banner",
])
def test_the_fan_cannot_render_without_its_strip(source: str, field: str):
    """Every strip field is built in the same expression as the chart, not beside it."""
    body = _function(source, "renderFan")
    assert f"a.{field}" in body, f"the assumptions strip does not show {field}"


def test_the_strip_is_not_hidden_behind_a_disclosure(source: str):
    """A strip inside <details> is a strip the reader can leave closed."""
    body = _function(source, "renderFan")
    strip = body.index('<dl class="strip">')
    first_details = body.index("<details>")
    assert strip < first_details, "the assumptions strip must precede any <details>"


def test_the_fan_never_computes_a_mean(source: str):
    """p10/p50/p90 only. A mean invites being read as the answer."""
    body = _function(source, "renderFan")
    assert "mean" not in body.lower()
    assert "moyenne" not in body.lower()


def test_the_banner_ships_without_a_numeric_factor(source: str):
    """D-057: "un facteur 3 à 5" was not a measurement and must not reappear."""
    assert "facteur 3 à 5" not in source
    assert "facteur de 3 à 5" not in source


def test_leakage_is_shown_as_computed_but_not_applied(source: str):
    body = _function(source, "renderFan")
    assert "leakage_applied" in body
    assert "non appliquée" in body


def test_the_employment_unit_is_named_on_screen(source: str):
    """ETP, not persons — the two coexist in this layer and must not be added."""
    body = _function(source, "renderFan")
    assert "équivalents temps plein" in body


def test_an_unavailable_fan_still_says_why(source: str):
    body = _function(source, "renderFan")
    assert "unavailable_because" in body
    assert "m.available" in body


def test_uncovered_instruments_are_shown_with_reasons(source: str):
    body = _function(source, "renderFan")
    assert "uncovered" in body
    assert "ne décrit pas" in body


def test_the_scenario_refusal_is_surfaced(source: str):
    body = _function(source, "renderFan")
    assert "scenario_available" in body
    assert "scenario_unavailable_because" in body


# --- the layers below must not have changed -----------------------------------------


def test_the_mechanical_presentation_is_unchanged(source: str):
    """§4: mechanical and behavioural presentation unchanged, regression-tested."""
    assert "La réforme coûte" in source and "La réforme rapporte" in source
    assert "Effet au premier jour sur le revenu disponible des ménages, à" in source
    assert "comportement inchangé" in source


def test_the_behavioural_band_is_unchanged(source: str):
    assert "function renderBand(" in source
    body = _function(source, "renderBand")
    # The band is a range AROUND the mechanical figure: both marks still drawn.
    assert 'class="mech"' in body and 'class="span"' in body
    assert "b.mechanical" in body


def test_the_band_still_precedes_the_fan(source: str):
    """L3 is better evidenced than L4 and keeps the higher position on the page."""
    render = _function(source, "renderPopulation")
    assert render.index("renderBand(data)") < render.index("renderFan(data)")


def test_every_renderer_escapes_what_it_prints(source: str):
    """The reasons and caveats are long French sentences from YAML, not from a user —
    but they reach the DOM the same way, and the file's own convention is to escape."""
    body = _function(source, "renderFan")
    interpolations = re.findall(r"\$\{([^}]*)\}", body)
    texty = [x for x in interpolations
             if any(k in x for k in ("_because", "caveats", "why", "banner", "design"))]
    assert texty, "expected some free-text interpolation to check"
    for expression in texty:
        assert "escapeHtml" in expression, f"unescaped free text: {expression}"


def test_the_file_stays_single_and_buildless(source: str):
    """It must open from file:// — no bundler, no framework, no external script."""
    assert "<script src=" not in source
    assert "import " not in source.split("<script>")[-1][:2000]


# --- prestations (B1) ---------------------------------------------------------------


@pytest.mark.parametrize("knob", [
    "rsa_montant_de_base", "ppa_montant_de_base", "ppa_pente", "bmaf",
    "af_modulation_taux_tranche_2", "af_modulation_taux_tranche_3",
    "af_plafond_tranche_1_base", "af_plafond_tranche_2_base",
    "al_minoration_forfaitaire",
])
def test_every_exposed_prestation_knob_is_wired(source: str, knob: str):
    assert knob in {entry["knob"] for entry in knob_table(source)}


def test_the_prestations_panel_exists_and_explains_the_ceiling_rule(source: str):
    assert "Prestations</div>" in source
    assert "L'autre moitié du débat" in source
    assert "aucune des\n            deux" in source or "n'est dans aucune des" in source


def test_the_rate_knobs_are_sent_as_fractions(source: str):
    """The panel takes percentages; the API takes fractions. A missing /100 would be a
    silent factor-of-a-hundred reform.

    Read off the knob table, which is now the single source for all three directions —
    so the scale is checked once and applies to sending, resetting and loading alike.
    """
    table = {entry["knob"]: entry for entry in knob_table(source)}
    for knob, field in (("ppa_pente", "ppaPente"),
                        ("af_modulation_taux_tranche_2", "afMod2"),
                        ("af_modulation_taux_tranche_3", "afMod3")):
        assert table[knob]["id"] == field
        assert table[knob]["scale"] == 100, f"{knob} is not divided by 100"


def test_the_amount_knobs_are_not_scaled(source: str):
    """Euros are euros — dividing one of these by 100 would be the mirror mistake."""
    table = {entry["knob"]: entry for entry in knob_table(source)}
    for knob, field in (("rsa_montant_de_base", "rsaBase"), ("bmaf", "bmafIn"),
                        ("al_minoration_forfaitaire", "alMino")):
        assert table[knob]["id"] == field
        assert table[knob]["scale"] == 1, f"{knob} is being scaled and should not be"


# --- IR niches (B3) -----------------------------------------------------------------


@pytest.mark.parametrize("field", [
    "nSaldom", "nSaldomAides", "nDons", "nDonsColuche",
    "nGarde1", "nGarde2", "nGarde3", "nSynd1", "nSynd2",
    "nCollege", "nLycee", "nSup",
])
def test_every_niche_base_input_exists(source: str, field: str):
    assert f'id="{field}"' in source


@pytest.mark.parametrize("knob", [
    "saldom_taux", "saldom_plafond", "gardenf_taux", "gardenf_plafond",
    "dons_taux", "dons_coluche_taux", "cotisations_syndicales_taux",
    "plafond_global_niches",
])
def test_every_exposed_niche_knob_is_wired(source: str, knob: str):
    assert knob in {entry["knob"] for entry in knob_table(source)}


def test_the_niche_payload_sends_only_what_was_declared(source: str):
    """"Declared nothing" must stay distinguishable from "declared zero"."""
    body = _function(source, "nichesPayload")
    assert "return declared ? niches : null" in body


def test_the_childcare_list_trims_trailing_zeros(source: str):
    """The API maps the list positionally onto 7GA/7GB/7GC, so a trailing zero would
    claim a third child's costs."""
    body = _function(source, "nichesPayload")
    assert "garde.pop()" in body and "syndicales.pop()" in body


def test_the_niche_panel_explains_the_per_child_ceiling(source: str):
    """The measured fact that decided the wire format belongs on screen."""
    assert "par enfant" in source
    assert "1 750" in source and "3 000" in source


def test_the_panel_says_the_credits_are_refundable(source: str):
    """A foyer can leave this panel with a negative tax, and should be told so."""
    assert "impôt négatif" in source


def test_the_blind_spot_renderer_exists_and_runs_before_the_headline(source: str):
    """A warning under a number is a warning the reader reaches too late."""
    assert "function renderNicheBlindSpot(" in source
    render = _function(source, "renderPopulation")
    assert "renderNicheBlindSpot(data)" in render
    assert render.index("renderNicheBlindSpot(data)") < render.index('class="headline"')


def test_the_blind_spot_names_the_stake(source: str):
    body = _function(source, "renderNicheBlindSpot")
    assert "national_niches_eur" in body
    assert "declared_base_eur" in body


# --- Phase 5: the patrimoine tab and the two dials ------------------------------------


def test_the_ifi_row_and_its_inputs_are_wired(source: str):
    """A result row with no way to fill its inputs would print zero forever."""
    assert 'patrimoinePayload()' in source
    assert "household.patrimoine = patrimoine" in source
    for field in ("patRP", "patAutres", "patPassif", "patDons"):
        assert f'id="{field}"' in source, field
    assert '["ifi", "Impôt sur la fortune immobilière", "down"]' in source


def test_the_enforcement_dial_sits_beside_the_rate_dial(source: str):
    """The module's signature, and it has to be VISIBLE beside the rate to do its job.

    The evidence says reported wealth responds to disclosure design roughly ten times
    more than to the rate. A simulator that offered the rate dial and hid the
    enforcement one would put the small lever in the user's hand.
    """
    assert 'id="ifiObligations"' in source
    assert 'value="renforcees"' in source and 'value="allegees"' in source
    dials = source.index("Les deux cadrans")
    rate = source.index('id="ifiPlafTaux"')
    dial = source.index('id="ifiObligations"')
    assert dials < rate < dial, "the two dials must be in one block, rate first"
    assert "dix fois" in source[dials:dial], "the ten-times finding must be on screen"


def test_the_screen_says_the_enforcement_dial_changes_no_mechanical_figure(source: str):
    """Otherwise a user moves it, sees the IFI unchanged, and concludes it is broken."""
    block = source[source.index("Les deux cadrans"):source.index('id="ifiObligations"')]
    assert "ne change rien au calcul mécanique" in block
    assert "points de croissance" in block, "its unit must be named, not implied"


def test_the_zero_income_trap_is_stated_where_the_wealth_is_entered(source: str):
    """The plafonnement abates the whole IFI at zero income, so a wealthy foyer with no
    salary prices zero. A user who met that without warning would read it as a bug."""
    block = source[source.index("Patrimoine — IFI"):source.index('id="patPassif"')]
    assert "sans revenu" in block and "aucun" in block


def test_the_absence_of_financial_wealth_is_explained_not_merely_absent(source: str):
    """There is no field for securities, and that is the tax's definition rather than a
    gap in the form. Saying so is what stops it being read as an omission."""
    block = source[source.index("Patrimoine — IFI"):source.index('id="patRP"')]
    assert "965" in block, "the article that defines the base must be cited"


# --- F2: the knob table, and the three directions derived from it -------------------


def knob_table(source: str) -> list[dict]:
    """Parse the `KNOBS` table out of the source. Structural, like everything here."""
    block = source[source.index("const KNOBS = ["):]
    block = block[:block.index("\n];")]
    entries = []
    for match in re.finditer(r"\{\s*knob:\s*\"(?P<knob>[a-z0-9_]+)\"\s*,"
                             r"\s*id:\s*\"(?P<id>\w+)\"(?P<rest>[^}]*)\}", block):
        entry = {"knob": match["knob"], "id": match["id"],
                 "law": "law:" in match["rest"]}
        scale = re.search(r"scale:\s*(\d+)", match["rest"])
        entry["scale"] = int(scale.group(1)) if scale else 1
        entries.append(entry)
    return entries


def test_the_knob_table_is_parseable_and_populated(source: str):
    table = knob_table(source)
    assert len(table) > 25, f"only {len(table)} knobs parsed"
    assert {entry["knob"] for entry in table} >= {
        "decote_taux", "rsa_montant_de_base", "plafond_global_niches",
        "ifi_plafonnement_taux"}


def test_every_id_in_the_knob_table_exists_in_the_document(source: str):
    """Fails on a typo'd id, which would otherwise silently drop a knob from the
    payload — the panel would look filled and send nothing."""
    for entry in knob_table(source):
        assert f'id="{entry["id"]}"' in source, f"{entry['knob']} -> #{entry['id']}"


@pytest.mark.parametrize("name", ["reformSpec", "fillLaw", "applyScenario"])
def test_all_three_directions_are_derived_from_the_one_table(source: str, name: str):
    """THE test that makes the scenario loader safe.

    Fails the moment someone writes a second, hand-maintained knob-to-input map. A
    hand-written inverse agrees with its forward map on the day it is written and drifts
    the first time a knob is added — the exact shape of bug this project keeps finding.
    """
    body = _function(source, name)
    assert "of KNOBS" in body, f"{name} does not iterate the knob table"


def test_reset_clears_the_set_if_filled_knobs(source: str):
    """A button that says «réinitialiser au droit courant» must return current law.

    It used to reset the six IR boxes and leave every prestation, employer, niche and
    IFI knob filled, so the panel afterwards was not current law and the dirty counter
    still said so. Fails if `fillLaw` stops clearing the no-`law` knobs.
    """
    body = _function(source, "fillLaw")
    assert 'k.law ? ' in body and '"";' in body, body
    assert "markDirty()" in body, "the dirty counter is not refreshed after a reset"


def test_loading_a_scenario_clears_the_previous_one_first(source: str):
    """Fails if `applyScenario` stops calling `fillLaw`.

    A knob left over from the previously loaded scenario prices a reform nobody asked
    for, and looks exactly like the reform they did ask for.
    """
    body = _function(source, "applyScenario")
    assert body.index("fillLaw()") < body.index("of KNOBS")


def test_a_scenario_the_panel_cannot_represent_is_reported_not_flattened(source: str):
    """One input drives both allègement rates, so some scenarios cannot be shown.

    Fails if `applyScenario` stops re-reading the panel and returning what was lost. A
    picker that quietly mis-loads is worse than no picker.
    """
    body = _function(source, "applyScenario")
    assert "reformSpec()" in body, "the loader does not check itself"
    assert "return { lost, added }" in body, "the check is not two-directional"
    assert "ATTENTION" in source and "n'est PAS celui" in source


def test_the_picker_is_read_only(source: str):
    """Fails the day a «save scenario» button appears in the UI.

    A scenario's value is its date. A date the interface can mint is a date anyone can
    mint, so registration stays in the CLI where it lands in the working tree and gets
    committed (D-092).
    """
    picker = source[source.index("async function loadScenarioList"):]
    picker = picker[:picker.index("async function boot")]
    assert 'method: "POST"' not in picker
    assert "scenarios" in picker
    for verb in ('"POST"', '"PUT"', '"DELETE"', '"PATCH"'):
        assert verb not in picker, f"write verb {verb} in the scenario picker"


def test_an_unreadable_scenario_is_named_rather_than_hidden(source: str):
    """Fails if the picker starts dropping scenarios that no longer validate.

    One that silently vanishes is a chiffrage that silently stops being confrontable.
    """
    assert "unreadable" in source
    assert "illisibles, non proposés" in source


def test_the_script_block_parses(source: str, tmp_path):
    """The file is buildless and there is no browser here, so nothing else would catch a
    syntax error before it reached a user as a blank panel.

    Skipped rather than failed where node is absent: a missing tool is not a broken UI.
    """
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node absent")
    blocks = re.findall(r"<script>(.*?)</script>", source, re.S)
    assert blocks, "no script block"
    script = tmp_path / "ui.js"
    script.write_text("\n".join(blocks), encoding="utf-8")
    done = subprocess.run([node, "--check", str(script)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


# --- the UI's own logic, actually executed ------------------------------------------


ROUND_TRIP_HARNESS = """
const lawParams = JSON.parse(require("fs").readFileSync(process.argv[2], "utf8"));
let brackets = [];
const inputs = {};
const $ = (id) => (inputs[id] ||= { value: "" });
const document = { getElementById: (id) => (id === "ifiObligations" ? $(id) : null) };
function renderBrackets() {}
function markDirty() {}
%(table)s
%(fillLaw)s
%(reformSpec)s
%(applyScenario)s

const out = {};
fillLaw();
out.after_reset = reformSpec();

const scenario = {
  decote_taux: 0.4523, rsa_montant_de_base: 700, csg_activite_imposable: 0.0305,
  af_modulation_taux_tranche_2: 0.29, plafond_global_niches: 8000,
  ifi_plafonnement_taux: 0.72, ppa_pente: 0.61,
};
out.load = applyScenario(scenario);
out.round_trip = reformSpec();
out.shown = { dTaux: $("dTaux").value, csgI: $("csgI").value,
              ppaPente: $("ppaPente").value, rsaBase: $("rsaBase").value };

applyScenario({ decote_taux: 0.45 });
out.after_second_load = reformSpec();
// The three cases the adversarial review of 2026-09-08 turned up.
out.equals_law = applyScenario({
  plafond_qf_demi_part: lawParams.plafond_qf_demi_part, rsa_montant_de_base: 700 });
out.shared_field = applyScenario({ allegement_general_taux_moins_de_50: 0.30 });
out.no_field = applyScenario({ rsa_montant_de_base: 700, af_taux_2_enfants: 0.40 });
console.log(JSON.stringify(out));
"""


def _js_function(source: str, name: str) -> str:
    return _function(source, name)


@pytest.fixture(scope="module")
def ui_round_trip(source: str, tmp_path_factory):
    """Run the panel's three derived functions in node, against REAL law parameters.

    The rest of this file reads the source; this one executes it. It exists because the
    knob table is the single point where a wrong id or a wrong scale silently mis-sends a
    reform — a factor of a hundred on a rate, or a knob that never reaches the API — and
    no amount of grepping catches that.
    """
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        pytest.skip("node absent")
    from impots.engine import baseline
    from impots.engine.reforms import read_ir_parameters

    tmp = tmp_path_factory.mktemp("ui")
    law = tmp / "law.json"
    law.write_text(json.dumps(read_ir_parameters(baseline(), 2024)), encoding="utf-8")

    table = source[source.index("const KNOBS = ["):]
    table = table[:table.index("\n];") + 3]
    script = tmp / "probe.js"
    script.write_text(ROUND_TRIP_HARNESS % {
        "table": table,
        "fillLaw": _js_function(source, "fillLaw"),
        "reformSpec": _js_function(source, "reformSpec"),
        "applyScenario": _js_function(source, "applyScenario"),
    }, encoding="utf-8")
    done = subprocess.run([node, str(script), str(law)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_a_reset_panel_reports_no_reform(ui_round_trip):
    """Current law in every box must read as current law.

    Fails if `fillLaw` and `reformSpec` disagree about a value by so much as a rounding
    digit — the panel would then announce a reform nobody made, and price it.
    """
    assert ui_round_trip["after_reset"] is None


def test_a_loaded_scenario_survives_the_round_trip(ui_round_trip):
    """Load a scenario, read the panel back: same knobs, same values.

    Seven knobs across both modes and both scales. Fails on an inverted multiply or an
    id that points at the wrong input.

    WHAT IT CANNOT CATCH, verified by breaking it: a scale that is WRONG BUT CONSISTENT.
    `applyScenario` multiplies by the scale and `reformSpec` divides by it, so deleting
    `scale: 100` from a knob round-trips perfectly while showing 0.61 on screen where the
    user should read 61 %. That is what
    `test_the_panel_shows_rates_as_percentages_and_euros_as_euros` is for, and why the
    two tests are not redundant.
    """
    expected = {
        "decote_taux": 0.4523, "rsa_montant_de_base": 700.0,
        "csg_activite_imposable": 0.0305, "af_modulation_taux_tranche_2": 0.29,
        "plafond_global_niches": 8000.0, "ifi_plafonnement_taux": 0.72,
        "ppa_pente": 0.61,
    }
    assert ui_round_trip["load"] == {"lost": [], "added": []}
    back = ui_round_trip["round_trip"]
    for knob, value in expected.items():
        assert back[knob] == pytest.approx(value), knob


def test_the_panel_shows_rates_as_percentages_and_euros_as_euros(ui_round_trip):
    """The scale, seen from the user's side. 0.4523 is 45.23 % on screen; 700 € is 700."""
    shown = ui_round_trip["shown"]
    assert float(shown["dTaux"]) == pytest.approx(45.23)
    assert float(shown["csgI"]) == pytest.approx(3.05)
    assert float(shown["ppaPente"]) == pytest.approx(61.0)
    assert float(shown["rsaBase"]) == pytest.approx(700.0)


def test_loading_a_second_scenario_leaves_nothing_of_the_first(ui_round_trip):
    """Fails if `applyScenario` stops clearing. A knob left over from the previous
    scenario prices a reform nobody asked for and looks exactly like one they did."""
    assert set(ui_round_trip["after_second_load"]) == {"decote_taux"}


def test_a_scenario_value_equal_to_current_law_is_not_called_unrepresentable(
        ui_round_trip):
    """Fails if the loader goes back to checking itself against `reformSpec()`.

    A scenario that sets `plafond_qf_demi_part` to the 2024 law value loads perfectly:
    the box shows it. `reformSpec` rightly omits it, because it is not a CHANGE — and
    the old check read that omission as a failure to load and cried wolf. Comparing
    against what the input actually holds is the question we meant to ask.
    """
    assert ui_round_trip["equals_law"] == {"lost": [], "added": []}


def test_a_shared_field_is_reported_as_a_knob_the_panel_ADDS(ui_round_trip):
    """One box drives both allègement rates, so loading one sends two.

    The old check was one-directional and said nothing at all here — the user got a
    silently different reform. Fails if `added` stops being computed.
    """
    assert ui_round_trip["shared_field"]["lost"] == []
    assert ui_round_trip["shared_field"]["added"] == ["allegement_general_taux_50_et_plus"]


def test_a_knob_with_no_field_says_so_rather_than_blaming_a_shared_field(ui_round_trip):
    """Each knob carries ITS OWN reason.

    The warning used to print one hard-coded cause — "un même champ pilote plusieurs
    boutons" — for every case, which is simply wrong for a knob that has no box at all.
    This repo's own `scenarios/rsa_700_af_40.json` is exactly that case.
    """
    lost = ui_round_trip["no_field"]["lost"]
    assert [item["knob"] for item in lost] == ["af_taux_2_enfants"]
    assert lost[0]["why"] == "pas de champ dans le panneau"
    assert ui_round_trip["no_field"]["added"] == []


def test_the_warning_does_not_hard_code_a_single_cause(source: str):
    """Fails if the note goes back to appending one fixed explanation to every knob."""
    picker = source[source.index("document.getElementById(\"scenarioLoad\")"):]
    picker = picker[:picker.index("\nasync function boot")]
    assert "item.why" in picker, "the note does not use each knob's own reason"
    assert "AJOUTE" in picker, "the note never mentions added knobs"
