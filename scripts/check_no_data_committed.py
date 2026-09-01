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
    return [line for line in out.splitlines() if line.startswith("data/")]


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--staged"
    if mode not in {"--staged", "--tree"}:
        print(f"usage: {Path(__file__).name} [--staged|--tree]", file=sys.stderr)
        return 2

    refused: list[str] = []
    problems: list[str] = []
    for path in candidates(mode):
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
