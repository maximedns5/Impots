#!/usr/bin/env python3
"""Refuse data files in the repository (D-016, PHASE1C_ERFS §5).

Run over the staged changes as a pre-commit hook, or over the whole tree in CI:

    python scripts/check_no_data_committed.py --staged
    python scripts/check_no_data_committed.py --tree

Why it exists. ERFS microdata arrives under a signed agreement forbidding
redistribution and re-identification. A compliance rule that exists only as prose
in a decision log is one distracted `git add -A` away from being fiction, and the
person it will catch is a future maintainer who never read the log.

The allowlist is deliberately short. `baseline_*.json` is on it because
`GET /population/baseline` serves it and it holds only national aggregates and
decile means — but that is a property to re-check rather than assume, so it is
checked here rather than trusted.
"""

from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Paths under data/ that may be committed, and why.
ALLOWED = {
    "data/**/.gitkeep": "keeps the empty directory in the tree",
    "data/raw/MANIFEST.json": "checksums and provenance of the raw inputs — no data",
    "data/processed/baseline_*.json": (
        "national aggregates and decile means only, served by GET /population/baseline"
    ),
}

#: Keys that would betray per-household or per-person rows in an aggregates file.
MICRODATA_KEYS = ("household_id", "person_id", "foyer_id", "famille_id", "IDENT", "NOI")

#: An aggregates summary has no business being large.
MAX_AGGREGATE_BYTES = 1_000_000

# ---------------------------------------------------------------- the ERFS extension
#
# E0(3) of the ERFS interrupt. The delivery (Quetelet-Progedo/ADISP lil-1696, millésime
# 2022, version FPR) lives OUTSIDE this tree at the owner's instruction, and the code
# reaches it through an untracked local config. Two things are refused here.

#: Name patterns that betray an ERFS artefact anywhere in the tree — not only under data/,
#: because a fixture in tests/ or a golden in reports/ would be exactly as forbidden and
#: exactly as easy to add by accident.
ERFS_NAME_PATTERNS = ("erfs", "fpr_", "lil-" "1696")

#: Tracked files whose NAME matches above and which are legitimate: project documents that
#: DISCUSS ERFS. They carry variable names and plans, never values. Listed one by one —
#: a pattern-shaped exemption would let a real offender in behind a plausible filename.
ERFS_NAME_ALLOWED = {
    "docs/OPUS_HANDOFF_NO_ERFS.md": "handoff prose, written when the posture was no-ERFS",
    "docs/PHASE1C_ERFS.md": "the branch-C plan: variable names and method, no values",
    "docs/M0_PHASE8.md": "recon report, metadata only",
    "scripts/verify_erfs.py": (
        "the E1 inventory: checksums, counts, column names and format agreement. "
        "Reads the delivery, prints no value from any row, and is opt-in."),
}

#: The absolute workspace path must never be hardcoded in CODE. Documents may state where
#: the delivery lives — the review file's ruling does, and that is a matter of record —
#: but a path literal in src/, tests/ or scripts/ is the thing E0(1) forbids: it would make
#: the code work on one machine and silently fail, or silently read nothing, on any other.
WORKSPACE_DIR_NAME = "lil-" "1696"
CODE_ROOTS = ("src/", "tests/", "scripts/", "Makefile", "pyproject.toml")

#: This script must NAME the patterns it refuses, so it necessarily contains them. Excluded
#: by exact path rather than by a rule, so the exclusion cannot widen: a second file wanting
#: the same exemption has to be added here deliberately.
GUARD_ITSELF = "scripts/check_no_data_committed.py"


def erfs_name_offenders(paths: list[str]) -> list[str]:
    """Tracked paths whose name says ERFS and which are not on the short allowlist."""
    out = []
    for path in paths:
        if path == GUARD_ITSELF or path in ERFS_NAME_ALLOWED:
            continue
        lowered = path.lower()
        if any(pattern in lowered for pattern in ERFS_NAME_PATTERNS):
            out.append(path)
    return out


def workspace_path_offenders(paths: list[str]) -> list[str]:
    """Tracked CODE carrying the delivery's absolute path as a literal."""
    out = []
    for path in paths:
        if path == GUARD_ITSELF or not path.startswith(CODE_ROOTS):
            continue
        full = ROOT / path
        if not full.exists() or full.stat().st_size > 2_000_000:
            continue
        try:
            text = full.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if f"/{WORKSPACE_DIR_NAME}" in text:
            out.append(path)
    return out


def allowed(path: str) -> str | None:
    for pattern, reason in ALLOWED.items():
        if fnmatch.fnmatch(path, pattern):
            return reason
    return None


def aggregates_only(path: str) -> list[str]:
    """Confirm an allowlisted JSON really is aggregates. Returns problems found."""
    full = ROOT / path
    if not full.exists():
        return []
    problems: list[str] = []
    size = full.stat().st_size
    if size > MAX_AGGREGATE_BYTES:
        problems.append(f"{path}: {size:,} bytes — too large to be aggregates only")
    try:
        text = full.read_text(encoding="utf-8")
        json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError):
        problems.append(f"{path}: allowlisted as JSON aggregates but is not readable JSON")
        return problems
    for key in MICRODATA_KEYS:
        if f'"{key}"' in text:
            problems.append(
                f"{path}: contains {key!r} — that is a row identifier, not an aggregate"
            )
    return problems


def candidates(mode: str) -> list[str]:
    command = (
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
        if mode == "--staged"
        else ["git", "ls-files"]
    )
    out = subprocess.run(
        command, capture_output=True, text=True, check=True, cwd=ROOT
    ).stdout
    return out.splitlines()


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--staged"
    if mode not in {"--staged", "--tree"}:
        print(f"usage: {Path(__file__).name} [--staged|--tree]", file=sys.stderr)
        return 2

    tracked = candidates(mode)

    erfs_named = erfs_name_offenders(tracked)
    hardcoded = workspace_path_offenders(tracked)
    if erfs_named or hardcoded:
        print("Refusing: the ERFS compliance rails (E0).", file=sys.stderr)
        for path in erfs_named:
            print(f"  ERFS-named in the tree: {path}", file=sys.stderr)
        for path in hardcoded:
            print(f"  workspace path hardcoded: {path}", file=sys.stderr)
        print(
            "\nERFS 2022 FPR (lil-" "1696) is held under a signed convention: nothing "
            "ERFS-derived\nenters git — files, fixtures, goldens and test data included — "
            "and the delivery path\nis reached through an untracked local config, never a "
            "literal. A document may STATE\nwhere the data lives; code may not embed it.",
            file=sys.stderr)
        return 1

    refused: list[str] = []
    problems: list[str] = []
    for path in tracked:
        if not path.startswith("data/"):
            continue
        reason = allowed(path)
        if reason is None:
            refused.append(path)
        elif path.endswith(".json") and "baseline" in path:
            problems.extend(aggregates_only(path))

    if refused:
        print("Refusing: data files may not be committed (D-016).", file=sys.stderr)
        for path in refused:
            print(f"  {path}", file=sys.stderr)
        print(
            "\nERFS microdata is not redistributable, and neither is a habit of "
            "committing whatever\nis under data/. Raw inputs are recovered by the "
            "downloads in the README; derived files\nby `impots population build`."
            "\n\nAllowed under data/:",
            file=sys.stderr,
        )
        for pattern, why in ALLOWED.items():
            print(f"  {pattern:38} {why}", file=sys.stderr)
        print(
            "\nIf a new file genuinely belongs in the repository, add it to ALLOWED in "
            "this script\nwith the reason — deliberately, in its own commit.",
            file=sys.stderr,
        )
        return 1

    if problems:
        print("Refusing: an allowlisted file no longer looks like aggregates.", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        print(
            "\nGET /population/baseline may only ever serve aggregates. If the "
            "population moves to\nERFS (D-016), this is the check that stops "
            "restricted microdata reaching the repository.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
