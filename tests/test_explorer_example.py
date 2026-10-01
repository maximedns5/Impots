"""Le document de §4.4 ne doit pas pouvoir dériver du code qu'il illustre.

C'est la leçon de D-154, appliquée à une page qui porte des euros : un document généré
qui s'écarte du code est plus dangereux qu'un document absent, parce qu'il sera cru. Le
test rejoue le rendu et le compare à ce qui est commité.

Il vérifie aussi que les bannières d'honnêteté sont là — « illustration, pas
recommandation », et l'encadré des montants inventés quand la table d'ancres réelle
n'est pas sur la machine. Une page de chiffres qui perd son encadré ne perd pas une
décoration : elle devient un chiffrage.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from impots.agregats.anchors import ANCHOR_TABLE

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "EXPLORER_EXAMPLE.md"
SCRIPT = ROOT / "scripts" / "write_explorer_example.py"


def _module():
    spec = importlib.util.spec_from_file_location("write_explorer_example", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rendered() -> str:
    return _module().render()


def test_the_committed_document_is_what_the_script_renders(rendered: str) -> None:
    """La garde anti-dérive. Elle tombe dès qu'on édite la page à la main.

    Ne s'applique que sur une machine SANS table d'ancres réelle : ailleurs le rendu
    porte les montants publiés, et exiger l'égalité avec la version fixture ferait
    échouer le test précisément là où le document est le plus juste.
    """
    if ANCHOR_TABLE.exists():
        pytest.skip("table d'ancres réelle présente : le rendu attendu n'est pas "
                    "celui qui est commité, et c'est normal")
    assert DOC.read_text(encoding="utf-8") == rendered, (
        "docs/EXPLORER_EXAMPLE.md a dérivé de scripts/write_explorer_example.py — "
        "relancer le script plutôt que d'éditer la page.")


def test_the_page_says_it_illustrates_a_machine_and_not_a_policy(rendered: str) -> None:
    assert "illustre une MACHINE, pas une politique" in rendered
    assert "Ce n'est pas une recommandation" in rendered
    assert "jamais « voici l'optimum »" in rendered


def test_the_invented_amounts_warning_rides_with_the_fixture(rendered: str) -> None:
    """La bannière suit la SOURCE, elle n'est pas écrite en dur.

    Sur une copie sans `data/raw/`, l'encadré doit être là ; le jour où la table réelle
    existe, il doit disparaître de lui-même. Une bannière codée en dur mentirait dans
    l'un des deux cas, et ce serait celui où la page dit vrai.
    """
    if ANCHOR_TABLE.exists():
        assert "LES MONTANTS CI-DESSOUS SONT INVENTÉS" not in rendered
        assert "provenance vérifiée" in rendered
    else:
        assert "LES MONTANTS CI-DESSOUS SONT INVENTÉS" in rendered
        assert "ne dit quoi que ce soit sur la France" in rendered


def test_the_page_carries_the_spending_scenario_refusal(rendered: str) -> None:
    """§3.5 : la trajectoire ne s'affiche jamais sans le nom du scénario de dépense.

    Et la page doit dire POURQUOI le refus n'est pas une formalité — l'écart entre les
    deux scénarios y pèse plus lourd que le paquet fiscal exploré.
    """
    assert "refuse de rendre une trajectoire sans scénario de dépense nommé" in rendered
    assert "pèse plus, sur la trajectoire, que le paquet fiscal" in rendered
    assert "ne sont PAS microsimulées" in rendered


def test_the_page_shows_both_displays_and_names_the_anti_fooling_rule(rendered: str
                                                                     ) -> None:
    """« Cette loi, sur la France d'aujourd'hui, avec l'argent de demain. »"""
    assert "Δ vieilli" in rendered and "Δ gelé" in rendered
    assert "n'est pas un plan" in rendered


def test_the_page_shows_the_fragility_flag_BOTH_raised_and_not(rendered: str) -> None:
    """Un drapeau qui s'allume toujours est un drapeau qu'on apprend à ignorer.

    La première version de la page posait une bande absolue de 0,6 md€ sur une cible de
    0,62 md€ et marquait les 2 442 candidats fragiles. Le test l'aurait attrapée.
    """
    assert "FRAGILE : la bande" in rendered
    assert "entièrement" in rendered and "de marge" in rendered
    assert "L'absence de drapeau" in rendered


def test_the_page_states_that_the_zero_residual_is_not_a_validation(rendered: str
                                                                   ) -> None:
    """D-153, rappelé là où le zéro s'affiche — sinon il se lit comme un contrôle passé."""
    assert "n'est pas une validation" in rendered
    assert "D-153" in rendered


def test_the_unreachable_target_is_explained_by_arithmetic_not_by_search(rendered: str
                                                                        ) -> None:
    """La distinction que `ceiling_eur` existe pour rendre lisible, épinglée dans la page.

    Sans elle, « 0 candidat » accuse la recherche, et le lecteur conclut qu'un meilleur
    optimiseur trouverait — alors que la cible vaut dix-neuf fois le plafond.
    """
    assert "plafond arithmétique" in rendered
    assert "pas un échec de la recherche" in rendered
