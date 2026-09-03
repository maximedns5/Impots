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
    assert f'put("{knob}"' in source


def test_the_prestations_panel_exists_and_explains_the_ceiling_rule(source: str):
    assert "Prestations</div>" in source
    assert "L'autre moitié du débat" in source
    assert "aucune des\n            deux" in source or "n'est dans aucune des" in source


def test_the_rate_knobs_are_sent_as_fractions(source: str):
    """The panel takes percentages; the API takes fractions. A missing /100 would be a
    silent factor-of-a-hundred reform."""
    for knob, field in (("ppa_pente", "ppaPente"),
                        ("af_modulation_taux_tranche_2", "afMod2"),
                        ("af_modulation_taux_tranche_3", "afMod3")):
        assert f'put("{knob}",' in source
        line = next(ln for ln in source.splitlines() if f'put("{knob}"' in ln)
        assert f'filled("{field}", 100)' in line, f"{knob} is not divided by 100"


def test_the_amount_knobs_are_not_scaled(source: str):
    """Euros are euros — dividing one of these by 100 would be the mirror mistake."""
    for knob, field in (("rsa_montant_de_base", "rsaBase"), ("bmaf", "bmafIn"),
                        ("al_minoration_forfaitaire", "alMino")):
        line = next(ln for ln in source.splitlines() if f'put("{knob}"' in ln)
        assert f'filled("{field}")' in line, f"{knob} is being scaled and should not be"
