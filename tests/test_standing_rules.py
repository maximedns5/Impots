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


# --- every knob must MOVE AN OUTCOME ------------------------------------------------
#
# This replaced a grep rule, and the replacement is the point.
#
# The old rule required a knob's parameter node to appear somewhere in openfisca's model
# source. It passed `af_cm.modulation.taux_tranche_1`: a parameter that resolves to 1.0,
# that the AF formula never reads — `taux_helper` hardcodes the full rate as
# `(base_ressources <= plafond1) * 1` — and whose leaf name occurs in the source anyway,
# under `af_maj_dom.majoration_premier_enfant`, an unrelated parameter reusing it.
#
# So a name cannot settle it. Three earlier shapes of the same class were a silently
# created child (D-044), a derived parameter the formula recomputes (D-062) and a
# duplicate tree for the same article (D-064); this is the fourth, a parameter
# superseded by a literal. Every one of them resolves non-null, and every one of them
# would pass a read-back. Running a household is the only check that does not.


def test_every_knob_either_moves_an_outcome_or_says_why_not() -> None:
    """No knob may ship without a household on which it demonstrably moves something."""
    import knob_cases
    from impots.engine.reforms import (
        ECHELLE_KNOBS,
        PLAFOND_KNOBS,
        REVALORISATION_KNOBS,
        SCALAR_KNOBS,
    )

    # PLAFOND_KNOBS autant que SCALAR_KNOBS, depuis D-151. Ne quantifier que sur les
    # leviers scalaires laissait les deux plafonds de bandeau hors de toute règle de
    # couverture du dépôt : ce sont des champs de ReformSpec, atteignables par l'API, et
    # les seuls tests qui les nomment relisent l'arbre de paramètres ou vérifient quels
    # enfants ont été écrits — précisément la propriété dont D-071 a établi qu'elle ne
    # peut pas détecter un levier mort.
    # Et REVALORISATION_KNOBS depuis D-298 : un troisième registre, que la leçon de D-151
    # interdit de laisser hors de la règle.
    # Et ECHELLE_KNOBS depuis D-320 : un quatrième, vu absent de ces deux tests le jour
    # où il est entré.
    knobs = (set(SCALAR_KNOBS) | set(PLAFOND_KNOBS) | set(REVALORISATION_KNOBS)
             | set(ECHELLE_KNOBS))
    covered = set(knob_cases.CASES) | set(knob_cases.EXEMPT)
    missing = sorted(knobs - covered)
    assert not missing, (
        f"these knobs have neither an outcome case nor a recorded exemption: {missing}. "
        f"A knob with no case is a knob nobody has watched move."
    )
    stale = sorted(covered - knobs)
    assert not stale, f"cases for knobs that no longer exist: {stale}"


def test_every_exemption_carries_a_real_reason() -> None:
    """An unexplained exemption is where a dead knob would hide."""
    import knob_cases

    for knob, reason in knob_cases.EXEMPT.items():
        assert len(reason) > 200, f"{knob} is exempt without a checkable reason"
        assert "Vérifié" in reason, (
            f"{knob}'s exemption must record what was MEASURED, not merely argued"
        )


def test_the_dead_modulation_rate_is_not_a_knob() -> None:
    """`taux_tranche_1` resolves to 1.0 and no formula reads it.

    Kept as a regression because it is the most inviting of the four: the other two
    modulation rates ARE knobs, so the missing third looks like an oversight rather
    than a finding.
    """
    from impots.engine.reforms import SCALAR_KNOBS, resolve
    from impots.engine.system import baseline

    assert "af_modulation_taux_tranche_1" not in SCALAR_KNOBS
    path = ("prestations_sociales", "prestations_familiales", "prestations_generales",
            "af", "af_cm", "modulation", "taux_tranche_1")
    assert resolve(baseline().parameters, path)("2024-01-01") == 1.0, (
        "it still resolves, which is exactly why resolving is not the test"
    )
