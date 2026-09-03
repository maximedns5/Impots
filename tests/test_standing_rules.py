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


# --------------------------------------------------------------------------- #
# update() may never create (D-044)
# --------------------------------------------------------------------------- #
#: Modules that write to a parameter tree to build a reform.
REFORM_MODULES = (
    SRC / "engine" / "reforms.py",
    SRC / "entreprises" / "reforms.py",
)


class DirectParameterWrite(ast.NodeVisitor):
    """Finds `<anything>.update(start=..., value=...)` outside the safe helper."""

    def __init__(self) -> None:
        self.hits: list[tuple[int, str]] = []

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr == "update":
            keywords = {kw.arg for kw in node.keywords}
            if {"start", "value"} <= keywords:
                self.hits.append((node.lineno, "update(start=…, value=…)"))
        self.generic_visit(node)


@pytest.mark.parametrize("module", REFORM_MODULES, ids=lambda p: p.parent.name)
def test_a_reform_module_never_writes_a_parameter_directly(module: Path) -> None:
    """`update()` creates a child that does not exist, silently.

    That is not a small wart. The 2026 refonte replaced
    `entreprises_de_moins_de_50_salaries` with `t_delta_petites_entreprises`; writing
    the old name **succeeded**, the read-back then found exactly the value it had
    itself just written and passed, and labour cost moved by 0.00 — a reform reporting
    success while doing nothing, arriving through the guard built to catch that.

    So reform writes go through `impots.parameters.update_existing`, which checks the
    target against the tree as the year's formula sees it. Creating a parameter is
    still possible through `create_parameter`, which has a different name so that
    doing it is a decision someone typed. This test keeps the door shut."""
    visitor = DirectParameterWrite()
    visitor.visit(ast.parse(module.read_text(encoding="utf-8")))
    assert not visitor.hits, (
        f"{module.parent.name}/{module.name} writes a parameter directly at "
        + ", ".join(f"line {line}" for line, _ in visitor.hits)
        + " — use impots.parameters.update_existing, or create_parameter if creating "
          "is genuinely intended"
    )


def test_the_write_guard_catches_the_defect_it_was_written_for() -> None:
    """A structural test that cannot fail is a comment."""
    bad = "resolve(parameters, path).update(start=start, value=value)\n"
    visitor = DirectParameterWrite()
    visitor.visit(ast.parse(bad))
    assert visitor.hits, "the checker does not catch the defect it exists for"


def test_creating_a_parameter_has_its_own_name() -> None:
    """The point of the split. If both operations shared a name, choosing between
    them would not be visible in a diff."""
    from impots import parameters as parameters_module

    assert hasattr(parameters_module, "update_existing")
    assert hasattr(parameters_module, "create_parameter")
    assert parameters_module.update_existing is not parameters_module.create_parameter


def test_existence_is_read_from_the_evaluated_tree_not_the_editable_one() -> None:
    """An editable node answers `hasattr` for every child defined at ANY date, so
    asking it what exists in 2024 also returns 2025's parameters. That is how a knob
    can write into a year that is not the one being reformed."""
    from impots.engine.system import baseline
    from impots.parameters import exists_at

    path = (
        "prelevements_sociaux", "reductions_cotisations_sociales",
        "allegement_general", "ensemble_des_entreprises",
        "entreprises_de_moins_de_50_salaries",
    )
    parameters = baseline().parameters
    assert exists_at(parameters, path, "2024-01-01")
    assert not exists_at(parameters, path, "2026-01-01"), (
        "the 2026 refonte replaced this parameter; the evaluated tree must say so"
    )
    # The editable tree cannot tell them apart, which is the whole reason for `exists_at`.
    node = parameters
    for part in path[:-1]:
        node = getattr(node, part)
    assert hasattr(node, path[-1]), (
        "if the editable tree ever stops answering for a superseded child, this test "
        "is over-specified and the distinction it guards may have gone away"
    )


# --- every knob must aim at a parameter some FORMULA reads --------------------------

#: Where openfisca-france's formulas live. A parameter node no file here mentions
#: cannot be feeding any calculation.
OPENFISCA_MODEL = (
    Path(__import__("openfisca_france").__file__).parent / "model"
)

#: The trap this rule exists for, and the third of its kind in this project.
#:
#: `impot_revenu.credits_impots.aide_a_domicile` is a COMPLETE PHANTOM TREE for the
#: home-help credit: it cites the same CGI article in its own documentation as the live
#: node, carries the same values at every leaf (taux 0.5, plafond_invalide 20 000,
#: plafond_additionnel 1 500), resolves non-null at 2024-01-01 — and no formula reads
#: it. Its name is the MORE natural one for "home help" than the live
#: `emploi_salarie_domicile`, so it is exactly what a careful implementer would pick.
#:
#: Two earlier shapes of the same failure: `update()` silently creating an absent child
#: (D-044), and published-but-derived plafonds the AF formula never consults (D-062).
#: Resolving non-null is not enough. Being read is the property that matters.
PHANTOM_NODE = ("impot_revenu", "credits_impots", "aide_a_domicile")


def _node_is_referenced(name: str) -> bool:
    """Whether any openfisca model file mentions this parameter node by name."""
    return any(
        name in path.read_text(encoding="utf-8", errors="ignore")
        for path in OPENFISCA_MODEL.rglob("*.py")
    )


def test_every_knob_aims_at_a_node_some_formula_reads() -> None:
    """A knob pointing at a parameter no formula reads writes successfully and moves
    nothing — silently, and with a read-back that confirms it."""
    from impots.engine.reforms import SCALAR_KNOBS

    orphans = []
    for knob, path in sorted(SCALAR_KNOBS.items()):
        # A formula references the containing node, not usually the leaf, so either
        # counts as evidence that this branch of the tree is live.
        if not any(_node_is_referenced(segment) for segment in path[-2:]):
            orphans.append((knob, ".".join(path)))
    assert not orphans, (
        "these knobs aim at parameter nodes no openfisca formula mentions, so a reform "
        f"moving them would change nothing: {orphans}"
    )


def test_the_rule_fires_on_the_phantom_that_motivated_it() -> None:
    """The kill test. `aide_a_domicile` must be invisible to the model, or this rule
    has stopped testing anything."""
    assert not _node_is_referenced(PHANTOM_NODE[-1]), (
        "openfisca now references aide_a_domicile — either it was wired up, in which "
        "case this rule needs a new phantom to prove itself on, or the grep broke"
    )
    assert _node_is_referenced("emploi_salarie_domicile"), (
        "the live home-help node is no longer referenced, which would mean the grep is "
        "finding nothing and the rule above passes vacuously"
    )


def test_the_phantom_is_indistinguishable_by_read_back() -> None:
    """Why a read-back could not have caught it: the values are identical.

    Both trees answer 0.5 for the rate and 20 000 for the invalidity ceiling at
    2024-01-01. A guard that writes a value and reads it back would confirm the write
    to the dead tree exactly as convincingly as to the live one.
    """
    from impots.engine.reforms import resolve
    from impots.engine.system import baseline

    parameters = baseline().parameters
    live = resolve(parameters, ("impot_revenu", "credits_impots",
                                "emploi_salarie_domicile", "taux"))("2024-01-01")
    phantom = resolve(parameters, (*PHANTOM_NODE, "taux"))("2024-01-01")
    assert live == phantom == 0.5
    assert resolve(parameters, (*PHANTOM_NODE, "plafond", "plafond_invalide"))(
        "2024-01-01") == 20_000
