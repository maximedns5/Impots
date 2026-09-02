"""Structural rules the project has promoted from lessons, enforced on the source.

Each of these exists because it was violated once, at cost, and each is checked
against the code rather than remembered. They are not style rules: every one of them
describes a defect that produced a wrong number while every test stayed green.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "impots"

#: Modules that read published statistical files, where a display label is data.
INGEST_MODULES = (
    SRC / "population" / "ingest.py",
    SRC / "entreprises" / "cells.py",
)


# --------------------------------------------------------------------------- #
# Codes, not labels (D-029)
# --------------------------------------------------------------------------- #
class LabelPredicate(ast.NodeVisitor):
    """Finds `"..." in <something called label / libellé / …>`."""

    SUSPECT_NAMES = ("label", "libelle", "libellé", "intitule", "nom", "titre")

    def __init__(self) -> None:
        self.hits: list[tuple[int, str]] = []

    def visit_Compare(self, node: ast.Compare) -> None:
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            if not isinstance(op, ast.In):
                continue
            target = comparator
            name = ""
            if isinstance(target, ast.Name):
                name = target.id
            elif isinstance(target, ast.Attribute):
                name = target.attr
            elif isinstance(target, ast.Call) and isinstance(target.func, ast.Attribute):
                inner = target.func.value
                name = inner.id if isinstance(inner, ast.Name) else getattr(inner, "attr", "")
            if any(suspect in name.lower() for suspect in self.SUSPECT_NAMES):
                self.hits.append((node.lineno, name))
        self.generic_visit(node)


@pytest.mark.parametrize("module", INGEST_MODULES, ids=lambda p: p.name)
def test_ingest_never_substring_matches_a_display_label(module: Path) -> None:
    """`"IS" in label.upper()` is True for "Nombre d'entreprises à l'IR", because
    ENTREPRISES contains IS. The corporation-tax row was being selected by publication
    order alone, and a reordered sheet would have substituted a 4.7 M count for a
    2.7 M one, moving every level in the firm table with it.

    Substring tests against a French display string are banned in ingest: match a
    code, or compare the whole label. This test caught the first repair, which had
    swapped the vacuous test for a narrower substring instead of for equality."""
    visitor = LabelPredicate()
    visitor.visit(ast.parse(module.read_text(encoding="utf-8")))
    assert not visitor.hits, (
        f"{module.name} substring-matches a display label at "
        + ", ".join(f"line {line} ({name})" for line, name in visitor.hits)
        + " — key on a code, or compare the whole label"
    )


# --------------------------------------------------------------------------- #
# A tolerance on a signed quantity is two-sided, or written on the magnitude
# --------------------------------------------------------------------------- #
def python_sources() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


@pytest.mark.parametrize("module", python_sources(), ids=lambda p: p.name)
def test_a_residual_is_never_compared_one_sidedly_to_a_tolerance(module: Path) -> None:
    """For a COST the published figure is negative, so a simulated value further below
    it is a LARGER miss — while the signed residual reads *more negative* and looks
    like a smaller one. A one-sided test written on the signed residual therefore
    passes exactly the cases it should fail, which is what the barème-indexation
    backtest did until it was measured.

    The rule: any comparison that mentions both a residual and a tolerance must be
    taken on a magnitude — `abs(...)`, or a quantity whose name says so. Deliberately
    narrow, aimed at the bug class rather than at every inequality in the codebase;
    drift and convergence checks take their absolute value where they are computed."""
    source = module.read_text(encoding="utf-8")
    if "residual" not in source or "toleranc" not in source:
        return
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Compare):
            continue
        segment = ast.get_source_segment(source, node) or ""
        flat = " ".join(segment.split())
        if "residual" not in flat or "toleranc" not in flat:
            continue
        if "abs(" in flat or "magnitude" in flat:
            continue
        offenders.append(f"line {node.lineno}: {flat[:90]}")
    assert not offenders, (
        f"{module.name} compares a signed residual against a tolerance without taking "
        f"a magnitude:\n  " + "\n  ".join(offenders)
    )


def test_the_rule_would_catch_the_defect_it_was_written_for() -> None:
    """A structural test that cannot fail is a comment. This runs the checker over
    the exact code that shipped the bug, and requires it to object."""
    bad = "def passes(self, s):\n    return -self.tolerance <= self.residual(s) <= 0.0\n"
    hits = [
        node for node in ast.walk(ast.parse(bad))
        if isinstance(node, ast.Compare)
        and "residual" in (ast.get_source_segment(bad, node) or "")
        and "toleranc" in (ast.get_source_segment(bad, node) or "")
        and "abs(" not in (ast.get_source_segment(bad, node) or "")
        and "magnitude" not in (ast.get_source_segment(bad, node) or "")
    ]
    assert hits, "the checker does not catch the defect it exists for"
