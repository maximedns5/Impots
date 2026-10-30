"""La sélection par impact voit aussi les fichiers que les tests lisent (D-309).

testmon relance un test quand une ligne Python qu'il exécute a changé ; il ne voit pas une
D-entrée, un cas préenregistré ou un parquet de `data/` que ce test lit. `impact_fichiers`
relève ces lectures et rend à la sélection le fichier de tests dont une lecture a changé.
Les derniers tests le montrent sur un vrai projet : testmon seul laisse passer le
changement d'un fichier lu, le greffon le rattrape.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

import impact_fichiers as impact

pytest_plugins = ("pytester",)

TESTS = Path(__file__).resolve().parent


# --- ce qui compte pour une lecture ---------------------------------------------------


@pytest.mark.parametrize(("mode", "flags", "lit"), [
    ("r", None, True), ("rb", None, True), ("w", None, False), ("a", None, False),
    ("r+", None, False), ("xb", None, False), (None, os.O_RDONLY, True),
    (None, os.O_WRONLY | os.O_CREAT, False), (None, os.O_RDWR, False),
])
def test_only_a_read_is_a_dependency(mode, flags, lit) -> None:
    assert impact.en_lecture(mode, flags) is lit


def test_a_read_is_named_from_the_root_and_code_or_caches_are_not(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    assert impact.relatif(tmp_path / "docs" / "D.md", tmp_path) == "docs/D.md"
    assert impact.relatif(tmp_path / "src" / "m.py", tmp_path) is None
    assert impact.relatif(tmp_path / ".git" / "HEAD", tmp_path) is None
    assert impact.relatif(tmp_path / "x" / "__pycache__" / "m.json", tmp_path) is None
    assert impact.relatif(tmp_path.parent / "ailleurs.json", tmp_path) is None
    assert impact.relatif(3, tmp_path) is None


def test_a_link_is_named_by_the_path_read_not_where_it_points(tmp_path) -> None:
    """`data/` is links to files kept elsewhere: the path the code reads is the one that
    names the dependency."""
    cible = tmp_path.parent / f"{tmp_path.name}_cible.parquet"
    cible.write_bytes(b"x")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "p.parquet").symlink_to(cible)
    assert impact.relatif(tmp_path / "data" / "p.parquet", tmp_path) == "data/p.parquet"


def test_a_file_has_changed_only_when_its_content_has(tmp_path) -> None:
    fichier = tmp_path / "f.json"
    fichier.write_text("1")
    connue = impact.empreinte(fichier)
    assert not impact.a_change(fichier, connue)
    os.utime(fichier, ns=(1, 1))  # touched, same content
    assert not impact.a_change(fichier, connue)
    fichier.write_text("2")
    assert impact.a_change(fichier, connue)
    fichier.unlink()
    assert impact.a_change(fichier, connue)


def test_what_is_given_back_to_the_selection(tmp_path) -> None:
    for nom in ("lu.json", "stable.json", "collecte.json"):
        (tmp_path / nom).write_text("v1")
    releve = {"modules": {
        "tests/test_lit.py": {"fichiers": {"lu.json": impact.empreinte(tmp_path / "lu.json")}},
        "tests/test_stable.py": {"fichiers": {
            "stable.json": impact.empreinte(tmp_path / "stable.json")}},
        "tests/test_lance.py": {"fichiers": {}, "sous_processus": True},
    }, "collecte": {"collecte.json": impact.empreinte(tmp_path / "collecte.json")}}
    assert impact.a_relancer(releve, tmp_path) == ({"tests/test_lance.py"}, False)
    (tmp_path / "lu.json").write_text("v2")
    assert impact.a_relancer(releve, tmp_path) == (
        {"tests/test_lit.py", "tests/test_lance.py"}, False)
    (tmp_path / "collecte.json").write_text("v2")
    assert impact.a_relancer(releve, tmp_path)[1] is True


def test_a_module_that_did_not_run_keeps_its_record() -> None:
    ancien = {"modules": {"a": {"fichiers": {"x": [1, 1, "s"]}},
                          "b": {"fichiers": {"y": [1, 1, "s"]}}}, "collecte": {"c": [1, 1, "s"]}}
    neuf = {"modules": {"a": {"fichiers": {}}}, "collecte": {"d": [1, 1, "s"]}}
    fusion = impact.fusionner(ancien, neuf)
    assert fusion["modules"] == {"a": {"fichiers": {}}, "b": {"fichiers": {"y": [1, 1, "s"]}}}
    assert set(fusion["collecte"]) == {"c", "d"}


def test_the_record_attributes_each_read_and_each_subprocess(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    (tmp_path / "a.json").write_text("{}")
    (tmp_path / "b.json").write_text("{}")
    releve = impact.Releve(tmp_path)
    releve.audit("open", (str(tmp_path / "a.json"), "r", 0))
    releve.courant = "tests/test_x.py"
    releve.audit("open", (str(tmp_path / "b.json"), "rb", 0))
    releve.audit("open", (str(tmp_path / "b.json"), "w", 0))
    releve.audit("subprocess.Popen", ("git", ["git", "status"], None, None))
    ecrit = json.loads(releve.ecrire().read_text(encoding="utf-8"))
    assert set(ecrit["collecte"]) == {"a.json"}
    assert set(ecrit["modules"]["tests/test_x.py"]["fichiers"]) == {"b.json"}
    assert ecrit["modules"]["tests/test_x.py"]["sous_processus"] is True


# --- sur un vrai projet, avec testmon --------------------------------------------------


@pytest.fixture
def projet(pytester):
    pytester.makeini("[pytest]\nmarkers =\n    lent: lent\n")
    pytester.makeconftest(
        f"import sys\nsys.path.insert(0, {str(TESTS)!r})\n"
        "from impact_fichiers import ajouter_options, configurer\n"
        "def pytest_addoption(parser):\n    ajouter_options(parser)\n"
        "def pytest_configure(config):\n    configurer(config)\n")
    (pytester.path / "donnees.json").write_text('{"v": 1}')
    pytester.makepyfile(
        test_lit="import json\n"
                 "def test_lit():\n"
                 "    assert json.load(open('donnees.json'))['v'] > 0\n",
        test_ignore="def test_ignore():\n    assert True\n",
        test_lent="import json, pytest\n"
                  "@pytest.mark.lent\n"
                  "def test_lent():\n"
                  "    assert json.load(open('donnees.json'))['v'] > 0\n",
    )
    return pytester


def _ran(result) -> set[str]:
    return {line.split("::")[1].split()[0] for line in result.outlines
            if "::" in line and "PASSED" in line}


def _run(projet, *options):
    return projet.runpytest_subprocess("-v", "-p", "no:cacheprovider", "--testmon",
                                       "--testmon-forceselect", *options)


def test_testmon_alone_misses_a_changed_file_that_a_test_reads(projet) -> None:
    """The blind spot this plugin exists for: testmon reruns nothing when only a data file
    a test reads has changed."""
    assert _ran(_run(projet)) == {"test_lit", "test_ignore", "test_lent"}
    assert _ran(_run(projet)) == set()
    (projet.path / "donnees.json").write_text('{"v": 2}')
    assert _ran(_run(projet)) == set()


def test_the_plugin_gives_back_the_test_that_read_the_changed_file(projet) -> None:
    assert _ran(_run(projet, "--fichiers-lus")) == {"test_lit", "test_ignore", "test_lent"}
    assert _ran(_run(projet, "--fichiers-lus")) == set()
    (projet.path / "donnees.json").write_text('{"v": 2}')
    assert _ran(_run(projet, "--fichiers-lus")) == {"test_lit", "test_lent"}
    assert _ran(_run(projet, "--fichiers-lus")) == set()


def test_a_test_deselected_by_its_marker_stays_deselected(projet) -> None:
    """Given back to testmon's selection, never to `-m`'s: a slow test the gate leaves
    out stays out, whatever it read."""
    _run(projet, "--fichiers-lus")
    (projet.path / "donnees.json").write_text('{"v": 2}')
    assert _ran(_run(projet, "--fichiers-lus", "-m", "not lent")) == {"test_lit"}


def test_a_test_that_starts_a_subprocess_always_runs(projet) -> None:
    projet.makepyfile(test_lance="import subprocess, sys\n"
                                 "def test_lance():\n"
                                 "    subprocess.run([sys.executable, '-c', 'pass'], check=True)\n")
    assert "test_lance" in _ran(_run(projet, "--fichiers-lus"))
    assert _ran(_run(projet, "--fichiers-lus")) == {"test_lance"}


def test_without_the_option_nothing_is_recorded(projet) -> None:
    _run(projet)
    assert not (projet.path / impact.DOSSIER).exists()
    assert sys.audit  # the hook is installed only with the option, never by default


def test_a_parquet_polars_reads_is_seen_too(projet) -> None:
    """polars opens its files in Rust, out of Python's audit hook: its readers are watched
    by name, or a rebuilt population would rerun nothing."""
    import polars as pl

    pl.DataFrame({"v": [1]}).write_parquet(projet.path / "pop.parquet")
    projet.makepyfile(test_pop="import polars as pl\n"
                               "def test_pop():\n"
                               "    assert pl.read_parquet('pop.parquet')['v'][0] > 0\n")
    assert "test_pop" in _ran(_run(projet, "--fichiers-lus"))
    pl.DataFrame({"v": [2]}).write_parquet(projet.path / "pop.parquet")
    assert _ran(_run(projet, "--fichiers-lus")) == {"test_pop"}


# --- les tests lourds, regroupés sous xdist (D-309) ------------------------------------


def test_only_the_tests_listed_heavy_join_the_heavy_group(tmp_path, monkeypatch) -> None:
    import memoire

    liste = tmp_path / "lourds.txt"
    liste.write_text("# mesurés par --memoire\n"
                     "tests/test_a.py::test_lourd  # 5 120 Mo\n\n", encoding="utf-8")
    monkeypatch.setattr(memoire, "FICHIER_LOURDS", liste)

    class Item:
        def __init__(self, nodeid):
            self.nodeid, self.marques = nodeid, []

        def add_marker(self, marque):
            self.marques.append(marque)

    lourd, leger = Item("tests/test_a.py::test_lourd"), Item("tests/test_a.py::test_leger")
    memoire.grouper([lourd, leger])
    assert [(m.name, m.args) for m in lourd.marques] == [("xdist_group", ("lourd",))]
    assert leger.marques == []
    monkeypatch.setattr(memoire, "FICHIER_LOURDS", tmp_path / "absent.txt")
    assert memoire.lourds() == frozenset()
