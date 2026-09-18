"""Provenance as a property of the tree, not a fact about it (D-028).

An audit on 2026-09-02 found that no unsourced file in `data/raw/` was reachable
from any code under `src/`. That was true, and being true by audit is worth less
than being true by construction — an audit is a statement about one afternoon.
These tests make it a property.

They also enforce the second rule the same review promoted: **codes, not labels.**
`"IS" in label.upper()` matched the *income*-tax row because ENTREPRISES contains
IS, and the corporation-tax row was being selected by publication order alone.
Ingest logic keys on codes; a French display string is data, never a predicate.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from impots.population.ingest import (
    MANIFEST_PATH,
    QUARANTINE,
    RAW,
    UnmanifestedInput,
    require_sourced,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "impots"

#: Modules that open published statistical files. Anything they name must be sourced.
INGEST_MODULES = (
    SRC / "population" / "ingest.py",
    SRC / "entreprises" / "cells.py",
)

needs_manifest = pytest.mark.skipif(
    not MANIFEST_PATH.exists(), reason="no data/raw/MANIFEST.json in this checkout"
)


def manifest() -> dict[str, dict]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))["files"]


# --------------------------------------------------------------------------- #
# provenance
# --------------------------------------------------------------------------- #
def test_an_unsourced_file_cannot_be_opened(tmp_path: Path, monkeypatch) -> None:
    """The assertion itself, against a manifest this test writes.

    Hermetic on purpose. An earlier version called `require_sourced` on a made-up
    name and matched the resulting message — which passes locally, where the manifest
    exists, and fails on a clean checkout, where the manifest is absent and a
    different error fires first. So the test was asserting the environment, not the
    behaviour. It now builds both cases it cares about.
    """
    manifest = tmp_path / "MANIFEST.json"
    manifest.write_text(json.dumps({"generated": "2026-09-03", "files": {
        "sourced.xlsx": {"url": "https://example.invalid/x.xlsx", "sha256": "a" * 64,
                         "bytes": 1, "downloaded": "2026-09-03", "licence": "Etalab",
                         "description": "", "quarantined": False},
        "unsourced.xlsx": {"url": None, "sha256": "b" * 64, "bytes": 1,
                           "downloaded": "2026-09-03", "licence": "unknown",
                           "description": "", "quarantined": True},
    }}), encoding="utf-8")
    monkeypatch.setattr("impots.population.ingest.MANIFEST_PATH", manifest)

    require_sourced("sourced.xlsx")  # a URL on record: allowed
    with pytest.raises(UnmanifestedInput, match="no source URL"):
        require_sourced("unsourced.xlsx")
    with pytest.raises(UnmanifestedInput, match="not in MANIFEST"):
        require_sourced("a-file-nobody-recorded.xlsx")


@needs_manifest
def test_every_file_a_pipeline_module_names_is_sourced() -> None:
    """The property the audit could only assert for one afternoon.

    Filenames reach the readers as module-level constants, so they can be recovered
    statically: anything that looks like a data file and is assigned a name in an
    ingest module must carry a URL in the manifest.
    """
    recorded = manifest()
    suffixes = (".xlsx", ".csv", ".parquet", ".pdf", ".xls", ".zip")
    for module in INGEST_MODULES:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            name = node.value
            if not name.endswith(suffixes) or "/" in name:
                continue
            assert name in recorded, f"{module.name} names {name}, which is unmanifested"
            assert recorded[name]["url"], (
                f"{module.name} opens {name}, which has no source URL — nothing "
                f"computed from it is reproducible by a third party (D-028)"
            )
            assert not recorded[name]["quarantined"], f"{name} is quarantined but used"


@needs_manifest
def test_the_raw_tree_separates_sourced_from_unsourced() -> None:
    """A file with no recorded source lives under `_unsourced/`, so that its presence
    in the tree can never be read as provenance."""
    recorded = manifest()
    for file in RAW.iterdir():
        if not file.is_file() or file.name == MANIFEST_PATH.name:
            continue
        assert recorded.get(file.name, {}).get("url"), (
            f"{file.name} sits in data/raw/ with no source URL; it belongs in "
            f"data/raw/_unsourced/ (run `impots population manifest`)"
        )
    if QUARANTINE.exists():
        for file in QUARANTINE.iterdir():
            if file.is_file():
                assert recorded.get(file.name, {}).get("quarantined") is True, (
                    f"{file.name} is quarantined on disk but not in the manifest"
                )


@needs_manifest
def test_a_quarantined_file_still_carries_its_checksum() -> None:
    """Quarantine removes provenance, not tracking. The checksum still says whether
    the file changed; it just cannot back a published figure."""
    quarantined = [entry for entry in manifest().values() if entry.get("quarantined")]
    if not quarantined:
        pytest.skip("nothing quarantined in this checkout")
    for entry in quarantined:
        assert entry["sha256"] and entry["bytes"] > 0
        assert entry["url"] is None


@needs_manifest
def test_the_real_manifest_loads_through_the_loader_production_uses() -> None:
    """THE check that was missing, and that a 69-minute pass found instead of a test.

    Every other assertion in this file reads `MANIFEST.json` as raw JSON via the local
    `manifest()` helper. None of them ever constructed a `ManifestEntry`. So eighteen
    hand-added entries — Phase 8's AFT/dette files and the ERFS documentation — sat in
    the file for days writing `retrieved` where the generator writes `downloaded`, and
    nothing noticed until `require_sourced()` raised `TypeError` from deep inside
    `tests/test_cells.py`, eight failures at once and an hour into the gate.

    **A manifest that parses as JSON is not a manifest that loads.** The tests checked
    the first and production needs the second. That is the D-044 shape: a check taking a
    different route than the thing it protects, so the thing can break while the check
    stays green.

    The implementation that fails this test: adding an entry by hand in a shape the
    dataclass does not accept — which is exactly what happened, and what the kill test
    below reproduces deliberately.
    """
    from impots.population.ingest import load_manifest

    loaded = load_manifest()
    raw = manifest()
    assert set(loaded) == set(raw), (
        "le chargeur et le JSON brut ne voient pas les mêmes fichiers")
    assert loaded, "un manifeste vide se chargerait sans erreur et ne prouverait rien"


def test_an_entry_in_an_unknown_shape_is_refused_rather_than_ignored(
        tmp_path: Path, monkeypatch) -> None:
    """The kill test for the assertion above, and the regression it reproduces.

    `retrieved` is the field the eighteen hand-written entries used. Loading must FAIL
    on it rather than skip the entry: an unknown field silently dropped would mean a
    file whose provenance nobody recorded is read as one whose provenance is fine.
    """
    from impots.population.ingest import load_manifest

    bad = tmp_path / "MANIFEST.json"
    bad.write_text(json.dumps({"generated": "2026-09-18", "files": {
        "hand_written.xlsx": {"url": "https://example.invalid/x.xlsx",
                              "sha256": "c" * 64, "bytes": 1,
                              "retrieved": "2026-09-18", "description": ""},
    }}), encoding="utf-8")
    monkeypatch.setattr("impots.population.ingest.MANIFEST_PATH", bad)

    with pytest.raises(TypeError, match="retrieved"):
        load_manifest()
