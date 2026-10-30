"""La sélection par impact ne rejoue que ce qui a pu changer, et rejoue tout ce qui a pu (D-309).

Un test vert n'est pas rejoué tant que rien de ce dont il dépend n'a bougé : les fichiers
Python qu'il importe, même indirectement, ceux qu'il lit, les bibliothèques. Les derniers
tests le montrent sur un vrai projet, dont le premier cas rejoue le bug de D-306 : un
résultat mis en cache par processus, que la couverture de pytest-testmon ne relançait pas.
"""

from __future__ import annotations

import os
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


def test_a_read_is_named_from_the_root_and_caches_are_not(tmp_path) -> None:
    assert impact.relatif(tmp_path / "docs" / "D.md", tmp_path) == "docs/D.md"
    assert impact.relatif(tmp_path / ".git" / "HEAD", tmp_path) is None
    assert impact.relatif(tmp_path / "x" / "__pycache__" / "m.json", tmp_path) is None
    assert impact.relatif(tmp_path / "src" / "m.pyc", tmp_path) is None
    assert impact.relatif(tmp_path.parent / "ailleurs.json", tmp_path) is None
    assert impact.relatif(3, tmp_path) is None


def test_a_link_is_named_by_the_path_read_not_where_it_points(tmp_path) -> None:
    """`data/` is links to files kept elsewhere: the path the code reads names the
    dependency."""
    cible = tmp_path.parent / f"{tmp_path.name}_cible.parquet"
    cible.write_bytes(b"x")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "p.parquet").symlink_to(cible)
    assert impact.relatif(tmp_path / "data" / "p.parquet", tmp_path) == "data/p.parquet"


def test_a_fingerprint_is_reused_only_for_the_same_size_and_date(tmp_path) -> None:
    fichier = tmp_path / "f.json"
    fichier.write_text("1")
    connue = impact.empreinte(fichier)
    assert impact.Empreintes(tmp_path, {"f.json": connue}).sha("f.json") == connue[2]
    fichier.write_text("2")
    assert impact.Empreintes(tmp_path, {"f.json": connue}).sha("f.json") != connue[2]
    fichier.unlink()
    assert impact.Empreintes(tmp_path, {"f.json": connue}).sha("f.json") == "absent"


# --- le graphe des imports --------------------------------------------------------------


def test_every_import_counts_even_inside_a_function_and_relative() -> None:
    source = ("import a.b\n"
              "from c import d\n"
              "from . import e\n"
              "from ..f import g\n"
              "def h():\n"
              "    from i.j import k\n")
    assert impact.imports(source, "p.q.r", paquet=False) == {
        "a.b", "c", "c.d", "p.q", "p.q.e", "p.f", "p.f.g", "i.j", "i.j.k"}


def test_the_closure_follows_packages_and_submodules(tmp_path) -> None:
    for chemin, texte in {
        "src/pkg/__init__.py": "",
        "src/pkg/socle.py": "import json\n",
        "src/pkg/feuille.py": "from pkg import socle\n",
        "src/pkg/autre.py": "",
        "tests/test_f.py": "def test():\n    from pkg.feuille import x\n",
        "scripts/outil.py": "",
        "tests/test_o.py": "import outil\n",
    }.items():
        (tmp_path / chemin).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / chemin).write_text(texte)
    graphe = impact.Graphe.lire(tmp_path)
    assert graphe.fermeture("tests/test_f.py") == {
        "tests/test_f.py", "src/pkg/feuille.py", "src/pkg/__init__.py", "src/pkg/socle.py"}
    assert "scripts/outil.py" in graphe.fermeture("tests/test_o.py")


# --- le relevé ----------------------------------------------------------------------------


def test_the_latest_record_wins_whatever_worker_wrote_it() -> None:
    ancien = {"passes": {"t::a": ["d1", 10], "t::b": ["d1", 30]}}
    neuf = {"passes": {"t::a": [None, 20], "t::b": ["d2", 20]}}
    assert impact.fusionner(ancien, neuf)["passes"] == {"t::a": [None, 20], "t::b": ["d1", 30]}


@pytest.mark.parametrize(("phases", "issue"), [
    ([("setup", "passed"), ("call", "passed"), ("teardown", "passed")], "vert"),
    ([("setup", "passed"), ("call", "failed"), ("teardown", "passed")], "rouge"),
    ([("setup", "skipped")], "rouge"),
    ([("setup", "passed"), ("call", "passed"), ("teardown", "failed")], "rouge"),
])
def test_only_a_test_green_on_its_three_phases_is_recorded_green(phases, issue) -> None:
    class Rapport:
        def __init__(self, when, outcome):
            self.nodeid, self.when = "t::x", when
            self.passed, self.failed, self.skipped = (outcome == o for o in
                                                      ("passed", "failed", "skipped"))

    releve = impact.Releve(Path("/"))
    for when, outcome in phases:
        releve.noter(Rapport(when, outcome))
    assert releve.issues["t::x"] == issue


# --- sur un vrai projet -------------------------------------------------------------------


@pytest.fixture
def projet(pytester):
    """Un dépôt comme celui-ci : `src/`, `tests/`, un conftest, un résultat en cache."""
    pytester.makeini("[pytest]\npythonpath = src\ntestpaths = tests\n"
                     "markers =\n    lent: lent\n")
    fichiers = {
        "src/pkg/__init__.py": "",
        "src/pkg/socle.py": "import functools\n@functools.cache\n"
                            "def systeme():\n    return {'age': 62}\n",
        "src/pkg/feuille.py": "from pkg.socle import systeme\n"
                              "def age():\n    return systeme()['age']\n",
        "src/pkg/autre.py": "def un():\n    return 1\n",
        "donnees.json": '{"v": 1}',
        "tests/conftest.py": f"import sys\nsys.path.insert(0, {str(TESTS)!r})\n"
                             "import impact_fichiers\n"
                             "def pytest_addoption(parser):\n"
                             "    impact_fichiers.ajouter_options(parser)\n"
                             "def pytest_configure(config):\n"
                             "    impact_fichiers.configurer(config)\n",
        "tests/test_age.py": "from pkg.socle import systeme\n"
                             "def test_age():\n    assert systeme()['age'] == 62\n",
        "tests/test_feuille.py": "from pkg.feuille import age\n"
                                 "def test_feuille():\n    assert age() == 62\n",
        "tests/test_autre.py": "from pkg.autre import un\n"
                               "def test_autre():\n    assert un() == 1\n",
        "tests/test_lit.py": "import json\n"
                             "def test_lit():\n"
                             "    assert json.load(open('donnees.json'))['v'] > 0\n",
        "tests/test_lent.py": "import json, pytest\n"
                              "@pytest.mark.lent\n"
                              "def test_lent():\n"
                              "    assert json.load(open('donnees.json'))['v'] > 0\n",
    }
    for chemin, texte in fichiers.items():
        (pytester.path / chemin).parent.mkdir(parents=True, exist_ok=True)
        (pytester.path / chemin).write_text(texte)
    return pytester


TOUS = {"test_age", "test_feuille", "test_autre", "test_lit", "test_lent"}


def _ran(result) -> set[str]:
    return {line.split("::")[1].split()[0] for line in result.outlines
            if "::" in line and any(w in line for w in ("PASSED", "FAILED", "SKIPPED"))}


def _run(projet, *options):
    return projet.runpytest_subprocess("-v", "-p", "no:cacheprovider", "--impact", *options)


def _edit(projet, chemin, ancien, neuf):
    fichier = projet.path / chemin
    fichier.write_text(fichier.read_text().replace(ancien, neuf))


def _ajouter(projet, chemin, texte):
    (projet.path / chemin).write_text(texte)


def test_a_cached_result_whose_code_changed_reruns_every_test_that_imports_it(projet) -> None:
    """The bug of D-306, in small: the value is built once per process and cached. Its code
    changes; every test that imports it, directly or not, runs again and sees it."""
    assert _ran(_run(projet)) == TOUS
    assert _ran(_run(projet)) == set()
    _edit(projet, "src/pkg/socle.py", "'age': 62", "'age': 64")
    result = _run(projet)
    assert _ran(result) == {"test_age", "test_feuille"}
    result.assert_outcomes(failed=2)


def test_a_failed_test_runs_again_until_it_is_green(projet) -> None:
    _run(projet)
    _edit(projet, "src/pkg/socle.py", "'age': 62", "'age': 64")
    _run(projet)
    assert _ran(_run(projet)) == {"test_age", "test_feuille"}
    _edit(projet, "src/pkg/socle.py", "'age': 64", "'age': 62")
    assert _ran(_run(projet)) == {"test_age", "test_feuille"}
    assert _ran(_run(projet)) == set()


def test_a_changed_file_reruns_the_tests_that_read_it(projet) -> None:
    _run(projet)
    (projet.path / "donnees.json").write_text('{"v": 2}')
    assert _ran(_run(projet)) == {"test_lit", "test_lent"}
    assert _ran(_run(projet)) == set()


def test_a_test_deselected_by_its_marker_stays_deselected(projet) -> None:
    _run(projet)
    (projet.path / "donnees.json").write_text('{"v": 2}')
    assert _ran(_run(projet, "-m", "not lent")) == {"test_lit"}
    assert _ran(_run(projet)) == {"test_lent"}


def test_a_skipped_test_is_never_taken_for_green(projet) -> None:
    _ajouter(projet, "tests/test_saute.py",
             "import pytest\ndef test_saute():\n    pytest.skip('donnee absente')\n")
    assert "test_saute" in _ran(_run(projet))
    assert _ran(_run(projet)) == {"test_saute"}


def test_a_test_that_starts_a_subprocess_always_runs(projet) -> None:
    _ajouter(projet, "tests/test_lance.py",
             "import subprocess, sys\ndef test_lance():\n"
             "    subprocess.run([sys.executable, '-c', 'pass'], check=True)\n")
    assert "test_lance" in _ran(_run(projet))
    assert _ran(_run(projet)) == {"test_lance"}


def test_a_parquet_polars_reads_is_seen_too(projet) -> None:
    """polars opens its files in Rust, out of Python's audit hook: its readers are watched
    by name, or a rebuilt population would rerun nothing."""
    import polars as pl

    pl.DataFrame({"v": [1]}).write_parquet(projet.path / "pop.parquet")
    _ajouter(projet, "tests/test_pop.py",
             "import polars as pl\ndef test_pop():\n"
             "    assert pl.read_parquet('pop.parquet')['v'][0] > 0\n")
    _run(projet)
    pl.DataFrame({"v": [2]}).write_parquet(projet.path / "pop.parquet")
    assert _ran(_run(projet)) == {"test_pop"}


def test_a_script_loaded_by_its_path_is_a_dependency(projet) -> None:
    """`impots.etude` loads `scripts/<nom>.py` by its path: no import names it, its
    execution does."""
    (projet.path / "scripts").mkdir()
    _ajouter(projet, "scripts/outil.py", "VALEUR = 1\n")
    _ajouter(projet, "tests/test_charge.py",
             "import importlib.util\ndef test_charge():\n"
             "    spec = importlib.util.spec_from_file_location('outil', 'scripts/outil.py')\n"
             "    m = importlib.util.module_from_spec(spec)\n"
             "    spec.loader.exec_module(m)\n"
             "    assert m.VALEUR == 1\n")
    _run(projet)
    # Une autre taille : à la même seconde et à la même taille, Python reprendrait son
    # bytecode en cache, et le test ne verrait pas le changement que la sélection a vu.
    _ajouter(projet, "scripts/outil.py", "VALEUR = 22\n")
    result = _run(projet)
    assert _ran(result) == {"test_charge"}
    result.assert_outcomes(failed=1)


def test_without_the_option_nothing_is_selected_or_recorded(projet) -> None:
    projet.runpytest_subprocess("-p", "no:cacheprovider")
    assert not (projet.path / impact.DOSSIER).exists()


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
