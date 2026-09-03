"""M4 — validation episodes, and the acceptance gate for the macro layer.

One episode so far: the CICE. The gate is that the employment fan must contain the
range published evaluations span, **and** that its median must land inside that range —
because containment alone is satisfied by any fan wide enough, and a gate that a wider
band always passes is not a gate.

If this fails, the instruction is to stop and understand. Widening a parameter until it
passes is calibrating to the validation line, which §4.3 forbids for the mechanical
layer and which is no more defensible here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from impots.macro import fan, mesange, shocks, store, tes

pytest.importorskip("openpyxl")
pytest.importorskip("pypdf")

EPISODES = Path(__file__).parent / "episodes"

HAVE_SOURCES = (
    (tes.RAW / "insee_TES_symetrique_A38_2023SD.xlsx").exists()
    and (mesange.RAW / mesange.SOURCE_FILE).exists()
)
pytestmark = pytest.mark.skipif(
    not HAVE_SOURCES, reason="data/raw/ has no primary sources — they are not committed"
)

#: Knobs standing for a reform concentrated on low wages, as the CICE was.
TARGETED_KNOBS = ("allegement_general_plafond",)


def _episodes():
    return sorted(EPISODES.glob("*.yaml"))


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _run(episode: dict, variant: str):
    shock = episode["shock"]
    knobs = TARGETED_KNOBS if variant == "targeted" else None
    impulse = shocks.build({shock["delta"]: -float(shock["cost_eur"])},
                           year=int(shock["year"]), knobs=knobs)
    return fan.run(impulse, store.load(), gdp_eur=float(episode["gdp"]["value_eur"]))


@pytest.mark.parametrize("path", _episodes(), ids=lambda p: p.stem)
@pytest.mark.parametrize("variant", ["uniform", "targeted"])
def test_the_employment_fan_contains_the_published_range(path: Path, variant: str):
    """The acceptance gate. Both bracketing variants must pass, not whichever agrees."""
    episode = _load(path)
    if variant not in episode["shock"]["variants"]:
        pytest.skip(f"{episode['name']} does not run the {variant} variant")

    expected = episode["expected"]
    result = _run(episode, variant)
    quantiles = result.jobs_thousands_etp[expected["horizon"]]
    low = float(expected["jobs_thousands_low"])
    high = float(expected["jobs_thousands_high"])

    assert quantiles.p10 <= low, (
        f"{episode['name']} / {variant}: the fan's p10 is {quantiles.p10:,.0f}k, above "
        f"the published low of {low:,.0f}k — the fan excludes the micro-econometric "
        f"estimate. Do not widen a parameter to fix this."
    )
    assert quantiles.p90 >= high, (
        f"{episode['name']} / {variant}: the fan's p90 is {quantiles.p90:,.0f}k, below "
        f"the published high of {high:,.0f}k."
    )


@pytest.mark.parametrize("path", _episodes(), ids=lambda p: p.stem)
@pytest.mark.parametrize("variant", ["uniform", "targeted"])
def test_the_median_lands_inside_the_published_range(path: Path, variant: str):
    """The half that makes containment mean something.

    A fan from minus infinity to plus infinity contains every published estimate. The
    median has to be in the right place too, or the gate measures only width.
    """
    episode = _load(path)
    if variant not in episode["shock"]["variants"]:
        pytest.skip(f"{episode['name']} does not run the {variant} variant")

    expected = episode["expected"]
    result = _run(episode, variant)
    median = result.jobs_thousands_etp[expected["horizon"]].p50
    low = float(expected["jobs_thousands_low"])
    high = float(expected["jobs_thousands_high"])

    assert low <= median <= high, (
        f"{episode['name']} / {variant}: median {median:,.0f}k is outside the published "
        f"{low:,.0f}k-{high:,.0f}k. Containment may still hold, which is exactly why "
        f"this assertion exists."
    )


@pytest.mark.parametrize("path", _episodes(), ids=lambda p: p.stem)
def test_the_targeted_variant_is_the_higher_bracket(path: Path):
    """The CICE sits between the two variants; they must actually bracket it."""
    episode = _load(path)
    if set(episode["shock"]["variants"]) != {"uniform", "targeted"}:
        pytest.skip("episode does not bracket")
    horizon = episode["expected"]["horizon"]
    uniform = _run(episode, "uniform").jobs_thousands_etp[horizon].p50
    targeted = _run(episode, "targeted").jobs_thousands_etp[horizon].p50
    assert targeted > uniform


# --- the episode file has to keep its own provenance --------------------------------


@pytest.mark.parametrize("path", _episodes(), ids=lambda p: p.stem)
def test_the_episode_cites_a_primary_source(path: Path):
    episode = _load(path)
    source = episode["expected"]["source"]
    assert source["citation"].strip() and source["url"].startswith("https://")
    assert source["quote"].strip()


@pytest.mark.parametrize("path", _episodes(), ids=lambda p: p.stem)
def test_the_episode_quotes_are_verbatim(path: Path):
    """Same guard as the parameter store, for the same reason (D-056).

    A validation line taken from a search summary would be a worse failure than a
    parameter taken from one: it decides whether the layer ships.
    """
    import re

    import pypdf

    report = mesange.RAW / "france_strategie_2020_rapport_cice.pdf"
    if not report.exists():
        pytest.skip("the CICE evaluation report is not on disk")
    haystack = " ".join(
        " ".join((page.extract_text() or "").split())
        for page in pypdf.PdfReader(report).pages
    )
    flatten = lambda text: re.sub(r"[^a-zà-ÿ0-9]", "", text.lower())  # noqa: E731

    source = _load(path)["expected"]["source"]
    for key in ("quote", "high_quote"):
        quote = source.get(key, "").strip()
        if quote:
            assert flatten(quote) in flatten(haystack), f"{path.name}: {key} is not verbatim"


@pytest.mark.parametrize("path", _episodes(), ids=lambda p: p.stem)
def test_the_episode_records_that_the_source_disavows_this_use(path: Path):
    """Mésange warns against both halves of what this episode does.

    Note 79 says the targeted variant cannot evaluate actual contribution reliefs, and
    the conclusion says the results are not meant to be transposed to evaluating past
    policies. The episode is a sanity check on the machinery, and saying so in the file
    is what stops it being cited later as evidence the parameters are right.
    """
    text = path.read_text(encoding="utf-8")
    assert "note 79" in text
    assert "politiques économiques passées" in text


def test_the_net_of_financing_figure_is_excluded_and_says_why():
    """160 000 is net of the measure's financing; the fan produces a gross figure.

    Mésange's variants are explicitly unfinanced, so comparing to the net estimate would
    be comparing two different quantities.
    """
    episode = _load(EPISODES / "cice_2013.yaml")
    assert "160 000" in episode["expected"]["note"]
    assert "non financées" in episode["expected"]["note"]
