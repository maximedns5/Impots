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
    (tmp_path / "src/pkg/sous").mkdir()
    (tmp_path / "src/pkg/sous/__init__.py").write_text("REGLE = 1\n")
    (tmp_path / "src/pkg/sous/mod.py").write_text("")
    (tmp_path / "tests/test_s.py").write_text("import pkg.sous.mod\n")
    graphe = impact.Graphe.lire(tmp_path)
    # Importer `pkg.sous.mod` exécute `pkg/__init__.py` et `pkg/sous/__init__.py`, que rien
    # ne nomme ailleurs.
    assert graphe.fermeture("tests/test_s.py") == {
        "tests/test_s.py", "src/pkg/sous/mod.py", "src/pkg/sous/__init__.py",
        "src/pkg/__init__.py"}
    assert graphe.fermeture("tests/test_f.py") == {
        "tests/test_f.py", "src/pkg/feuille.py", "src/pkg/__init__.py", "src/pkg/socle.py"}
    assert "scripts/outil.py" in graphe.fermeture("tests/test_o.py")


def test_another_library_version_changes_every_fingerprint(tmp_path, monkeypatch) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("")
    dependances = lambda: impact.Dependances(  # noqa: E731
        impact.Graphe.lire(tmp_path), {}, [], impact.Empreintes(tmp_path), ())
    monkeypatch.setattr(impact, "versions", lambda: "openfisca-france==176.0.8")
    avant = dependances().digest("tests/test_x.py")
    monkeypatch.setattr(impact, "versions", lambda: "openfisca-france==177.0.0")
    assert dependances().digest("tests/test_x.py") != avant


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
def projet(pytester, monkeypatch):
    """Un dépôt comme celui-ci : `src/`, `tests/`, un conftest, un résultat en cache.

    Sans bytecode : ces tests modifient un fichier dans la seconde qui suit son import, à
    la même taille, et Python reprendrait le `.pyc` de l'ancien (son en-tête ne porte que
    la seconde et la taille). La sélection rejouait bien le test ; Python exécutait
    l'ancien code."""
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
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
                             "import pkg.autre  # chauffe, comme le moteur du vrai conftest\n"
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


def test_the_conftest_warming_a_module_does_not_make_every_test_depend_on_it(projet) -> None:
    """The real conftest imports the engine to warm it up. A test that computes imports it
    itself; the others do not depend on it for that."""
    _run(projet)
    _edit(projet, "src/pkg/autre.py", "return 1", "return 2")
    assert _ran(_run(projet)) == {"test_autre"}


def test_a_file_read_at_import_reruns_every_test(projet) -> None:
    """Read while modules are imported, before any test: who read it first is an accident
    of order, so it counts for all."""
    _ajouter(projet, "src/pkg/config.py", "import json\nCONF = json.load(open('config.json'))\n")
    _ajouter(projet, "config.json", '{"a": 1}')
    _ajouter(projet, "tests/test_conf.py",
             "from pkg.config import CONF\ndef test_conf():\n    assert CONF['a'] == 1\n")
    _run(projet)
    assert _ran(_run(projet)) == set()
    _ajouter(projet, "config.json", '{"a": 1, "b": 2}')
    assert _ran(_run(projet)) == TOUS | {"test_conf"}


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
    _ajouter(projet, "scripts/outil.py", "VALEUR = 2\n")
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


def test_the_memory_of_a_heavy_test_is_seen_even_after_another_one(pytester) -> None:
    """The process peak climbs once, at the first heavy test, and would hide the next: the
    rise is sampled during each test, from where the test starts: the 300 MB the conftest
    holds are no test's. The record is written after each one, so a worker the kernel kills
    does not take it with it."""
    pytester.makeconftest(f"import sys\nsys.path.insert(0, {str(TESTS)!r})\n"
                          "import memoire\n"
                          "TENU = bytearray(300 * 1024 * 1024)\n"
                          "TENU[::4096] = b'x' * len(TENU[::4096])\n"
                          "def pytest_addoption(parser):\n    memoire.ajouter_options(parser)\n"
                          "def pytest_configure(config):\n    memoire.configurer(config)\n")
    pytester.makepyfile(test_m="import time\n"
                               "def _gros():\n"
                               "    b = bytearray(400 * 1024 * 1024)\n"
                               "    b[::4096] = b'x' * len(b[::4096])\n"
                               "    time.sleep(0.5)\n"
                               "def test_a():\n    _gros()\n"
                               "def test_b():\n    _gros()\n"
                               "def test_c():\n    pass\n"
                               "def test_d():\n"
                               "    import os, signal\n"
                               "    os.kill(os.getpid(), signal.SIGKILL)\n")
    pytester.runpytest_subprocess("-p", "no:cacheprovider", "--memoire")
    import json

    hausses = json.loads((pytester.path / ".cache/impact/memoire.seul.json").read_text())
    assert hausses["test_m.py::test_a"] > 300 and hausses["test_m.py::test_b"] > 300
    assert hausses["test_m.py::test_c"] < 100
    assert "test_m.py::test_d" not in hausses  # killed, and the three before it kept


def test_a_test_is_heavy_above_the_threshold_only() -> None:
    import memoire

    seuil = memoire.SEUIL_LOURD_MO
    assert memoire.proposes({"a": seuil + 1, "b": seuil, "c": 12.0}) == ["a"]


def test_memory_a_test_keeps_is_seen_even_between_two_samples(pytester) -> None:
    """A cache a short test fills is still held when it ends: the reading taken then sees
    it, whatever the sampler saw."""
    pytester.makeconftest(f"import sys\nsys.path.insert(0, {str(TESTS)!r})\n"
                          "import memoire\nmemoire.PERIODE = 3600\n"
                          "def pytest_addoption(parser):\n    memoire.ajouter_options(parser)\n"
                          "def pytest_configure(config):\n    memoire.configurer(config)\n")
    pytester.makepyfile(test_k="GARDE = []\n"
                               "def test_k():\n"
                               "    b = bytearray(300 * 1024 * 1024)\n"
                               "    b[::4096] = b'x' * len(b[::4096])\n"
                               "    GARDE.append(b)\n")
    pytester.runpytest_subprocess("-p", "no:cacheprovider", "--memoire")
    import json

    hausses = json.loads((pytester.path / ".cache/impact/memoire.seul.json").read_text())
    assert hausses["test_k.py::test_k"] > 250


def test_a_record_written_halfway_keeps_the_previous_one(tmp_path, monkeypatch) -> None:
    import json
    import types

    import memoire

    releve = memoire.Releve(types.SimpleNamespace(rootpath=tmp_path))
    try:
        releve.hausses["t::a"] = 12.0
        releve._ecrire()

        def broken(self, text, *args, **kwargs):
            Path.write_bytes(self, text[:5].encode())
            raise OSError("disque plein")

        monkeypatch.setattr(Path, "write_text", broken)
        releve.hausses["t::b"] = 3.0
        with pytest.raises(OSError, match="disque plein"):
            releve._ecrire()
    finally:
        releve.arret.set()
    assert json.loads(releve.cible.read_bytes()) == {"t::a": 12.0}
    assert [f.name for f in releve.cible.parent.iterdir()] == [releve.cible.name]


def test_a_record_is_replaced_whole_never_rewritten_in_place(tmp_path) -> None:
    """A reader that opened the record before a write still reads the whole of the old one."""
    import json
    import types

    import memoire

    releve = memoire.Releve(types.SimpleNamespace(rootpath=tmp_path))
    try:
        releve.hausses["t::a"] = 12.0
        releve._ecrire()
        with releve.cible.open("rb") as lecteur:
            releve.hausses["t::b"] = 3.0
            releve._ecrire()
            assert json.loads(lecteur.read()) == {"t::a": 12.0}
    finally:
        releve.arret.set()
    assert json.loads(releve.cible.read_bytes()) == {"t::a": 12.0, "t::b": 3.0}



def test_every_test_listed_heavy_still_exists() -> None:
    """A heavy test renamed would leave the list in silence, and run beside another one."""
    import re

    import memoire

    assert memoire.lourds(), "tests/lourds.txt est vide ou absent"
    for test in memoire.lourds():
        fichier, nom = test.split("::")[0], test.split("::")[-1].split("[")[0]
        source = (TESTS.parent / fichier).read_text(encoding="utf-8")
        assert re.search(rf"^def {re.escape(nom)}\(", source, re.M), test


def test_the_heavy_tests_run_on_one_worker_under_xdist(pytester) -> None:
    """xdist reads a test's group in its own `pytest_collection_modifyitems`, which runs
    before a conftest's: a mark added there arrived too late, and the heavy tests went to
    every worker at once. The project's conftest only calls `memoire.configurer`, as here."""
    pytester.makeconftest(f"import sys\nsys.path.insert(0, {str(TESTS)!r})\n"
                          "from pathlib import Path\n"
                          "import memoire\n"
                          "memoire.FICHIER_LOURDS = Path(__file__).with_name('lourds.txt')\n"
                          "def pytest_addoption(parser):\n    memoire.ajouter_options(parser)\n"
                          "def pytest_configure(config):\n    memoire.configurer(config)\n")
    pytester.path.joinpath("lourds.txt").write_text(
        "".join(f"test_g.py::test_lourd_{i}  # 6 000 Mo\n" for i in range(6)), encoding="utf-8")
    corps = ("def test_{0}():\n    import os, time\n    time.sleep(0.2)\n"
             "    open('qui_{0}', 'w').write(os.environ['PYTEST_XDIST_WORKER'])\n")
    pytester.makepyfile(test_g="".join(corps.format(f"{nom}_{i}")
                                       for nom in ("lourd", "leger") for i in range(6)))
    resultat = pytester.runpytest_subprocess("-p", "no:cacheprovider", "-n", "3",
                                             "--dist", "loadgroup")
    resultat.assert_outcomes(passed=12)
    workers = {i: pytester.path.joinpath(f"qui_lourd_{i}").read_text() for i in range(6)}
    assert len(set(workers.values())) == 1, workers
