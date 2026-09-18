"""Loading published source data, behind a checksum manifest.

`data/raw/MANIFEST.json` records every input file with its URL, licence, download
date and sha256. Loaders refuse unmanifested or altered files: a population built
from a silently different vintage would still produce plausible numbers, and
plausible-but-wrong is this project's named worst failure (D-007).

No DVC in Phase 1. For a solo project with a handful of published files, a
manifest of checksums is the whole of what DVC would buy us.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

RAW = Path(__file__).resolve().parents[3] / "data" / "raw"
MANIFEST_PATH = RAW / "MANIFEST.json"

EEC_PARQUET = "FD_EEC_2024.parquet"
EEC_VARMOD = "Varmod_EEC_2024.csv"


class UnmanifestedInput(RuntimeError):
    """A pipeline input is missing from the manifest, or no longer matches it."""


@dataclass(frozen=True)
class ManifestEntry:
    filename: str
    url: str | None
    sha256: str
    bytes: int
    downloaded: str
    licence: str
    description: str
    quarantined: bool = False
    """True when the file has no recorded source and has been moved out of the way
    (D-028). Its checksum is still tracked; it just cannot back a published figure."""
    capture: str | None = None
    """For a page captured rather than downloaded as a file: how and when. A web page
    has no stable bytes, so the capture IS the provenance."""
    provenance: str | None = None
    """A route that is not a URL — a delivery, a hand copy. Carried rather than dropped
    because « d'où vient ce fichier » has an answer here even when no URL does."""


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict[str, ManifestEntry]:
    if not MANIFEST_PATH.exists():
        raise UnmanifestedInput(
            f"{MANIFEST_PATH} is missing. Run `impots population manifest` after downloading "
            "the raw files, or see docs/M0_RECON.md for where they come from."
        )
    raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {name: ManifestEntry(filename=name, **entry) for name, entry in raw["files"].items()}


#: Where a raw file with no recorded source is kept. Its manifest entry stays — the
#: checksum still proves the file has not changed — but its presence in the tree can
#: no longer be mistaken for provenance, which is the confusion D-028 closes.
QUARANTINE = RAW / "_unsourced"


def require_sourced(filename: str) -> None:
    """Refuse to open a raw input that has no recorded source (D-028).

    A checksum without a URL proves a file has not changed; it does not prove where
    it came from, so nothing computed from it is reproducible by anyone else. An
    audit found this true of the pipeline already — no unsourced file was reachable
    from `src/`. This makes it true by construction instead, which is the difference
    between a fact and a property.
    """
    manifest = load_manifest()
    entry = manifest.get(filename)
    if entry is None:
        raise UnmanifestedInput(
            f"{filename} is not in {MANIFEST_PATH.name}; add it with "
            "`impots population manifest` so the vintage it came from is on record."
        )
    if not entry.url:
        raise UnmanifestedInput(
            f"{filename} has no source URL in {MANIFEST_PATH.name}, so nothing computed "
            "from it is reproducible by a third party. Record its canonical URL in "
            "KNOWN_SOURCES and re-run `impots population manifest` (D-028)."
        )


def verified_path(filename: str) -> Path:
    """The path to a raw input, after checking it against the manifest.

    Checking the digest on every load is cheap next to what it prevents: the EEC
    file is 11 MB and hashes in well under a second, and a vintage swap that goes
    unnoticed would invalidate every golden aggregate downstream.
    """
    manifest = load_manifest()
    if filename not in manifest:
        raise UnmanifestedInput(
            f"{filename} is not in {MANIFEST_PATH.name}; add it with `impots population manifest` "
            "so the vintage it came from is on record."
        )
    require_sourced(filename)
    entry = manifest[filename]
    path = RAW / filename
    if not path.exists():
        raise UnmanifestedInput(f"{path} is manifested but missing. Re-download from {entry.url}")
    actual = sha256_of(path)
    if actual != entry.sha256:
        raise UnmanifestedInput(
            f"{filename} does not match the manifest.\n"
            f"  manifested {entry.sha256}\n  on disk     {actual}\n"
            "Either the file changed or the manifest is stale — resolve it deliberately, "
            "and record a decision if the vintage moved (D-004's policy)."
        )
    return path


def write_manifest(entries: list[dict[str, Any]]) -> Path:
    """(Re)write the manifest from files present in data/raw/."""
    files: dict[str, Any] = {}
    for entry in entries:
        path = Path(entry.get("path") or (RAW / entry["filename"]))
        files[entry["filename"]] = {
            "url": entry.get("url"),
            "quarantined": entry.get("quarantined", False),
            "sha256": sha256_of(path),
            "bytes": path.stat().st_size,
            "downloaded": entry.get("downloaded", date.today().isoformat()),
            "licence": entry["licence"],
            "description": entry["description"],
        }
    MANIFEST_PATH.write_text(
        json.dumps({"generated": date.today().isoformat(), "files": files},
                   indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return MANIFEST_PATH


# --------------------------------------------------------------------------- #
# loaders
# --------------------------------------------------------------------------- #
def load_eec() -> pl.DataFrame:
    """The EEC fichier détail: 353 420 individuals aged 15+, 83 variables.

    One row per person-quarter — the survey rotates, so a person appears in up to
    four quarters. `EXTRIAN` is an annual weight summed over the whole file, not
    per quarter (M0_RECON §1).
    """
    return pl.read_parquet(verified_path(EEC_PARQUET))


def load_varmod() -> pl.DataFrame:
    """Variable and modality labels for the EEC."""
    # Every column is read as text on purpose. Modality codes are zero-padded
    # ("01", "09") and LONG_VAR mixes integers with decimals ("12.9" for EXTRIAN);
    # inferring either would corrupt the join keys the labels are looked up by.
    return pl.read_csv(
        verified_path(EEC_VARMOD), separator=";", encoding="utf8-lossy",
        infer_schema=False,
    )


def modality_labels(varmod: pl.DataFrame | None = None) -> dict[str, dict[str, str]]:
    """`{variable: {code: label}}` — used to make reports readable."""
    frame = varmod if varmod is not None else load_varmod()
    labels: dict[str, dict[str, str]] = {}
    for code, modality, label in frame.select(["COD_VAR", "COD_MOD", "LIB_MOD"]).iter_rows():
        if modality is not None and str(modality).strip():
            labels.setdefault(code.strip(), {})[str(modality).strip()] = (label or "").strip()
    return labels
