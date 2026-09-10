"""S7 — the maintenance charter, checked against the repository it describes.

A charter is infrastructure: it prescribes rituals that will be followed, by someone who
may not have written it, possibly a year from now. So it gets the measurement-infrastructure
treatment — every claim it makes about the repo is verified here, because a charter that
describes a repository that no longer exists is worse than none: it will be followed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHARTER = ROOT / "docs" / "CHARTER.md"


@pytest.fixture(scope="module")
def text() -> str:
    return CHARTER.read_text(encoding="utf-8")


def test_the_charter_exists_and_is_one_page(text: str):
    """One page, as ordered. Fails if it grows into a manual nobody reads."""
    assert 100 < len(text.splitlines()) < 200


def test_every_verify_script_it_relies_on_exists(text: str):
    """The bump ritual says «re-run the verify_* scripts». Fails if it names a ritual
    whose instruments are gone."""
    assert "verify_*.py" in text
    scripts = sorted((ROOT / "scripts").glob("verify_*.py"))
    assert len(scripts) >= 5, f"seulement {len(scripts)} scripts de vérification"


def test_the_refresh_calendar_names_sources_the_manifest_actually_carries(text: str):
    """Fails if the calendar drifts from the manifest — a refresh calendar pointing at
    sources nobody manifests would be followed into nothing."""
    manifest = json.loads((ROOT / "data" / "raw" / "MANIFEST.json")
                          .read_text(encoding="utf-8"))["files"]
    names = " ".join(manifest).lower()
    descriptions = " ".join(entry.get("description", "") for entry in manifest.values()).lower()
    haystack = names + " " + descriptions
    for token in ("rei", "ifi", "filosofi", "resf"):
        assert token in haystack, f"le calendrier cite {token}, absent du manifeste"


def test_the_upstream_artefact_count_matches_the_dossier_itself(text: str):
    """Seven upstream artefacts: six in openfisca-france, one in core. Fails if the dossier
    gains or loses a row without the charter following.

    THE FIRST VERSION OF THIS TEST COULD NOT FAIL, and the charter it guarded was wrong.
    It asserted only that six cited D-entries EXISTED in the log — which they did, while
    three of them (D-044, D-062, D-071) had nothing to do with upstream artefacts: D-062 is
    the prestations knobs. Existence is not membership. The register is the dossier's own
    table, so that is what this reads."""
    dossier = (ROOT / "docs" / "UPSTREAM_ISSUE_DRAFT.md").read_text(encoding="utf-8")
    table = dossier[dossier.index("| # | Constat"):dossier.index("**Un septième")]
    rows = [line for line in table.splitlines() if re.match(r"^\| \d+ \|", line)]
    assert len(rows) == 6, f"{len(rows)} constats france au dossier, la charte en dit six"
    assert "openfisca-core" in dossier, "le septième, côté core, a disparu du dossier"
    assert "UPSTREAM_ISSUE_DRAFT.md" in text, (
        "la charte doit POINTER le registre plutôt qu'en recopier une liste, qui diverge")
    decisions = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    for entry in ("D-064", "D-075", "D-079", "D-081", "D-090", "D-091"):
        assert entry in text, f"{entry} mesure un artefact amont et manque de la charte"
        assert f"## {entry}" in decisions, f"{entry} cité, absent du journal"


def test_the_standing_questions_are_the_ones_the_decisions_record(text: str):
    """Five questions, each traceable to the incident that produced it. Fails if one is
    added without its D-entry or dropped without one."""
    decisions = (ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    for entry in ("D-093", "D-094", "D-095", "D-098"):
        assert entry in text, f"{entry} manquant de la charte"
        assert f"## {entry}" in decisions, f"{entry} cité, absent du journal"
    # Scoped to the section: the bump ritual and the LF cycle are numbered too, and the
    # first version counted nine by sweeping the whole file.
    section = text[text.index("## 5. Les questions permanentes"):text.index("## 6.")]
    questions = re.findall(r"^\d\. \*\*", section, re.M)
    assert len(questions) == 5, f"{len(questions)} questions permanentes, attendu 5"


def test_the_full_pass_rule_states_the_skip_caveat(text: str):
    """The timing tests skip under load, so a gate run alongside other work reports
    «5 skipped» rather than «2» — and that is NOT green in the same sense. Fails if the
    charter stops saying so, because the difference is invisible in the log line."""
    assert "5 skipped" in text and "2" in text
    assert "pas vert au même sens" in text


def test_the_never_list_forbids_widening_a_tolerance(text: str):
    """The one prohibition that would undo the most: a tolerance widened after the fact
    leaves a file indistinguishable from an honest one."""
    assert "Élargir une tolérance" in text
    assert "indiscernable" in text or "identique à un fichier honnête" in text


def test_the_charter_forbids_publishing(text: str):
    """Owner-gated throughout the project, and a maintenance document is exactly where
    that could be forgotten."""
    assert "Publier quoi que ce soit" in text
    assert "gelée par le propriétaire" in text
