"""Ce qui devient un morceau de chemin : le millésime (D-173).

Un nom de scénario est un identifiant depuis D-094. Le millésime ne l'était pas : six
sites l'interpolent dans un nom de fichier, et l'un d'eux le lit DANS le fichier qu'on
lui donne — c'est alors le contenu d'une table de cellules qui choisit où l'on écrit.
"""

from __future__ import annotations

import json

import pytest

from impots.identifiants import IdentifiantError, millesime


@pytest.mark.parametrize("valeur", ["../x", "a/b", "..", "2024\n", "", " 2024", "x" * 33,
                                    "fix.ture"])
def test_a_vintage_that_could_be_a_path_is_refused(valeur):
    with pytest.raises(IdentifiantError):
        millesime(valeur)


@pytest.mark.parametrize("valeur", ["2024", "2023", "fixture", 2024])
def test_the_vintages_in_use_still_pass(valeur):
    assert millesime(valeur) == str(valeur)


def test_the_cli_refuses_a_path_as_a_vintage():
    """Refusé à l'analyse des arguments, avant tout travail : argparse sort en 2."""
    from impots.population import cli

    with pytest.raises(SystemExit) as fin:
        cli.main(["population", "build", "--vintage", "../evade"])
    assert fin.value.code == 2


def test_a_cell_table_cannot_choose_where_it_is_written(tmp_path, monkeypatch):
    from impots.entreprises import build as fb

    monkeypatch.setattr(fb, "PROCESSED", tmp_path / "processed")
    brut = json.loads(fb.FIXTURE_CELLS.read_text(encoding="utf-8"))
    brut["vintage"] = "../evade"
    cellules = tmp_path / "cellules.json"
    cellules.write_text(json.dumps(brut), encoding="utf-8")
    with pytest.raises(IdentifiantError):
        fb.build(cellules)
    assert not list(tmp_path.rglob("firms_*"))


def test_a_cell_table_is_synthetic_unless_it_says_otherwise(tmp_path, monkeypatch):
    """Le drapeau suivait le CHEMIN du fichier, pas son contenu : une copie de la
    fixture, ou une table tierce qui se déclarait `"vintage": "fixture"`, écrasait la
    population que l'API sert par défaut et lui retirait son avertissement « cellules
    synthétiques ». Synthétique, sauf déclaration contraire de la table elle-même."""
    from impots.entreprises import build as fb

    monkeypatch.setattr(fb, "PROCESSED", tmp_path)
    copie = tmp_path / "cellules.json"
    copie.write_text(fb.FIXTURE_CELLS.read_text(encoding="utf-8"), encoding="utf-8")
    _, provenance = fb.build(copie)
    assert provenance["cells_are_synthetic"] is True
