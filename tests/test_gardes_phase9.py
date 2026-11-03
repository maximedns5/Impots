"""The guard sweep of Phase 9 must not rot (D-229).

`scripts/sweep_gardes_phase9.py` mutates every guard of Phase 9 and runs the tests that
must kill it; a full sweep takes about forty minutes and is not replayed here. What is
held here, in seconds: that its catalogue still applies to the code, that no module of
`predictif/` escapes it, and that the generator mutates what it says on any source. The
sweep itself is run on the owner's demand only (D-335): a guard added or rewritten since
the committed report is not required to be in it; `python scripts/sweep_gardes_phase9.py
--missing` runs only those, when asked.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sweep_gardes_phase9.py"


def _module():
    spec = importlib.util.spec_from_file_location("sweep_gardes_phase9", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sweep():
    return _module()


@pytest.fixture(scope="module")
def catalogue(sweep):
    return sweep.catalogue()


#: Les modules écrits après le gel du balayage (D-335 : pas de banc de mutations sans
#: demande). Leurs refus sont tenus par leurs propres tests, pas par le balayage.
AFTER_THE_SWEEP = {"src/impots/predictif/montecarlo.py", "src/impots/predictif/rejouer.py"}


def test_every_module_of_predictif_is_swept(sweep) -> None:
    """A module added to `predictif/` with its own refusals would otherwise sit outside
    the sweep, its guards never mutated."""
    swept = {s.path for s in sweep.SCOPES} | AFTER_THE_SWEEP
    modules = {str(p.relative_to(ROOT)) for p in (ROOT / "src/impots/predictif").glob("*.py")
               if p.name != "__init__.py"}
    assert modules <= swept, sorted(modules - swept)


def test_every_scope_names_files_functions_and_tests_that_exist(sweep, catalogue) -> None:
    import ast

    for scope in sweep.SCOPES:
        tree = ast.parse((ROOT / scope.path).read_text(encoding="utf-8"))
        defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        if scope.functions is not None:
            assert set(scope.functions) <= defined, (scope.path,
                                                      set(scope.functions) - defined)
        assert all((ROOT / t).exists() for t in scope.tests), scope.tests
        assert any(m.path == scope.path for m in catalogue), f"{scope.path} : aucune garde"
    assert all((ROOT / t).exists() for t in sweep.WIDE)


def test_every_mutation_still_applies_once_and_changes_something(catalogue) -> None:
    """A mutation whose text has left the code would be « not applied », and a sweep
    that skipped it would report a guard it never touched."""
    for m in catalogue:
        text = (ROOT / m.path).read_text(encoding="utf-8")
        assert text.count(m.old) == 1, (m.id, text.count(m.old))
        assert m.new != m.old, m.id
        assert all((ROOT / t).exists() for t in m.tests), m.id


def test_every_equivalence_names_a_mutation_and_says_why(sweep, catalogue) -> None:
    ids = {m.id for m in catalogue}
    for key, reason in sweep.EQUIVALENT.items():
        assert key in ids, f"équivalence orpheline : {key}"
        assert len(reason.strip()) > 40, f"{key} : une équivalence se justifie"


def test_the_generator_mutates_conditions_handlers_and_bare_refusals(sweep,
                                                                     tmp_path) -> None:
    """On a module of its own: a condition after non-ASCII text on the same line (the AST
    counts columns in UTF-8 bytes, and a character count would cut the line in the wrong
    place), a condition over two lines, a re-raising handler, a refusal in an `else` (the
    raise removed, not the test forced: forced false it would fire every time), an
    unconditional refusal, and a raise outside the functions asked for."""
    source = tmp_path / "module.py"
    source.write_text(
        'def f(x, y):\n'
        '    label = "θé"; ok = x == "θ" and y\n'
        '    if label == "θé" and not ok: raise ValueError("é")\n'
        '    if (x\n'
        '            and y):\n'
        '        raise KeyError(x)\n'
        '    try:\n'
        '        int(x)\n'
        '    except TypeError as error:\n'
        '        raise ValueError("θ") from error\n'
        '    if x == 1:\n'
        '        pass\n'
        '    else:\n'
        '        raise LookupError(x)\n'
        '\n'
        'class C:\n'
        '    def g(self):\n'
        '        raise RuntimeError("toujours")\n'
        '\n'
        'def h():\n'
        '    raise OSError\n', encoding="utf-8")
    scope = sweep.Scope(str(source), ("tests/test_gardes_phase9.py",), functions=("f", "g"))
    found = {m.id.split(":", 1)[1]: m for m in sweep.generated(scope)}
    assert sorted(found) == sorted([
        "f:si:label == 'θé' and (not ok)", "f:si:x and y", "f:sauf:TypeError",
        "f:sinon:non x == 1", "C.g:toujours:RuntimeError('toujours')"])
    first = found["f:si:label == 'θé' and (not ok)"]
    assert first.new == '    if False: raise ValueError("é")'
    assert found["f:si:x and y"].new == "    if (False):"
    assert found["f:sauf:TypeError"].new == "        raise"
    assert found["f:sinon:non x == 1"].new == "        pass"
    assert found["C.g:toujours:RuntimeError('toujours')"].new == "        return None"
    for m in found.values():
        text = source.read_text(encoding="utf-8")
        assert text.count(m.old) == 1


def test_apply_refuses_a_text_that_is_absent_or_repeated(sweep, tmp_path) -> None:
    target = tmp_path / "twice.py"
    target.write_text("x = 1\nx = 1\n", encoding="utf-8")
    for old in ("x = 1", "y = 2"):
        with pytest.raises(SystemExit, match="apparaît"):
            sweep.apply(sweep.Mutation("t", str(target), old, "x = 2", (), "t"))
    assert target.read_text(encoding="utf-8") == "x = 1\nx = 1\n"
