"""Ce que le code importe contre ce que le projet déclare (D-161, D-165).

Un import non déclaré fonctionne tant que l'environnement le porte par accident. `pypdf`
a survécu ainsi des semaines, cassé sur chaque runner, en signalant « pypdf is required »
— un message qui se lit comme un défaut de DONNÉES.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from impots import dependances as dep


def _projet(tmp_path: Path, dependances: list[str], source: str) -> Path:
    """Un mini-dépôt : un pyproject et un fichier src/ qui importe quelque chose."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'x'\nversion = '0'\ndependencies = "
        + json.dumps(dependances) + "\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "m.py").write_text(source, encoding="utf-8")
    return tmp_path


# --------------------------------------------------------------------------- #
# la propriété, sur le vrai dépôt
# --------------------------------------------------------------------------- #
def test_the_repository_declares_everything_it_imports() -> None:
    """Sur src/, tests/ ET scripts/ : un import non déclaré casse la CI où qu'il soit."""
    manquantes = dep.non_declarees()
    assert not manquantes, (
        f"importées mais absentes de pyproject.toml : {manquantes}. Elles marchent tant "
        f"que l'environnement les porte par accident, et cassent sur un arbre neuf.")


def test_pypdf_is_declared_since_it_was_the_one_that_broke_ci() -> None:
    """Épinglé nommément : c'est la dépendance qui manquait, et son retrait doit rougir."""
    assert "pypdf" in dep.declarees()
    assert "numpy" in dep.declarees()


# --------------------------------------------------------------------------- #
# le test de mise à mort
# --------------------------------------------------------------------------- #
def test_an_undeclared_import_is_reported_with_the_file_that_makes_it(tmp_path) -> None:
    """LE test de mise à mort, sur un dépôt fabriqué plutôt qu'en mutant le vrai."""
    racine = _projet(tmp_path, ["polars"], "import polars\nimport pypdf\n")
    manquantes = dep.non_declarees(racines=("src",), racine=racine)
    assert manquantes == {"pypdf": "src/m.py"}


def test_a_declared_import_is_not_reported(tmp_path) -> None:
    """Le jumeau : une garde qui accuse aussi le cas correct n'est pas une garde."""
    racine = _projet(tmp_path, ["polars", "pypdf"], "import polars\nimport pypdf\n")
    assert dep.non_declarees(racines=("src",), racine=racine) == {}


# --------------------------------------------------------------------------- #
# les deux pièges de nommage, chacun ayant fait accuser un paquet innocent
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("importe, distribution", [
    ("openfisca_core", "openfisca-core"),
    ("openfisca_france", "openfisca-france"),
])
def test_underscores_and_hyphens_are_the_same_package(tmp_path, importe, distribution) -> None:
    """PEP 503. La première version de cette garde accusait ces deux-là, parfaitement
    déclarés, parce qu'elle comparait le nom d'import au nom de distribution."""
    racine = _projet(tmp_path, [distribution], f"import {importe}\n")
    assert dep.non_declarees(racines=("src",), racine=racine) == {}


def test_a_distribution_whose_import_name_differs_is_matched_by_the_explicit_table(
        tmp_path) -> None:
    """`import yaml` vient de `pyyaml`. La table est EXPLICITE : deviner est ce qui a
    laissé passer `pypdf`."""
    racine = _projet(tmp_path, ["pyyaml"], "import yaml\n")
    assert dep.non_declarees(racines=("src",), racine=racine) == {}


def test_the_modules_to_import_are_import_names_not_distribution_names() -> None:
    """C'est `import yaml` qui échoue dans un environnement neuf, pas « import pyyaml ».
    `ci_local` essaie ces noms-là, donc la table est lue à l'envers."""
    noms = dep.modules_a_importer()
    assert "yaml" in noms and "pyyaml" not in noms
    assert "openfisca_france" in noms and "openfisca-france" not in noms


def test_local_modules_are_named_one_by_one_never_matched_by_pattern(tmp_path) -> None:
    """Les scripts du dépôt importés après un `sys.path.insert` ne sont pas des paquets.

    Un motif (« tout ce qui ressemble à un script ») écarterait aussi une vraie
    distribution du même nom. La table les nomme donc un par un, et ce test le fige.
    """
    assert "verify_aft" in dep.MODULES_LOCAUX
    assert "knob_cases" in dep.MODULES_LOCAUX
    racine = _projet(tmp_path, [], "import verify_aft\n")
    assert dep.non_declarees(racines=("src",), racine=racine) == {}
