"""Le pic de mémoire de chaque test, pour regrouper les lourds sous xdist (D-309).

Un passage de 20 000 ménages au palier complet tient plusieurs Go. Quatre workers xdist
qui en lancent chacun un dépassent la machine, et le noyau tue un worker. `--memoire`
relève, par test, de combien il a fait monter le pic du processus : un test qui monte de
plus de `SEUIL_LOURD_MO` est lourd, et `tests/lourds.txt` le range dans le groupe xdist
« lourd », qu'un seul worker exécute.
"""

from __future__ import annotations

import json
import os
import resource
from pathlib import Path

import pytest

OPTION = "--memoire"
FICHIER_LOURDS = Path(__file__).with_name("lourds.txt")
#: Ce qui fait d'un test un lourd : la hausse du pic du processus pendant son passage.
SEUIL_LOURD_MO = 1024


def ajouter_options(parser) -> None:
    parser.addoption(OPTION, action="store_true", default=False,
                     help="relever la hausse du pic de mémoire de chaque test (D-309)")


def lourds() -> frozenset[str]:
    """Les tests rangés lourds, par identifiant pytest ; vide si le fichier manque."""
    if not FICHIER_LOURDS.exists():
        return frozenset()
    lignes = FICHIER_LOURDS.read_text(encoding="utf-8").splitlines()
    return frozenset(ligne.split("#", 1)[0].strip() for ligne in lignes
                     if ligne.split("#", 1)[0].strip())


def grouper(items) -> None:
    """Range les lourds dans le groupe « lourd » : sous `--dist loadgroup`, un seul worker
    les exécute, l'un après l'autre. Sans xdist, la marque ne fait rien."""
    connus = lourds()
    for item in items:
        if item.nodeid in connus:
            item.add_marker(pytest.mark.xdist_group("lourd"))


def pic_mo() -> float:
    """Le pic de mémoire résidente du processus, en Mo (Linux compte en Ko)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def configurer(config) -> None:
    if config.getoption(OPTION):
        config.pluginmanager.register(Releve(config), "memoire")


class Releve:
    def __init__(self, config) -> None:
        self.racine = Path(str(config.rootpath))
        self.hausses: dict[str, float] = {}

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        avant = pic_mo()
        yield
        hausse = pic_mo() - avant
        if hausse > 0:
            self.hausses[item.nodeid] = round(hausse, 1)

    def pytest_sessionfinish(self, session, exitstatus) -> None:
        travailleur = os.environ.get("PYTEST_XDIST_WORKER", "maitre")
        cible = self.racine / ".cache" / "impact" / f"memoire.{travailleur}.json"
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(json.dumps(self.hausses, indent=1, sort_keys=True),
                         encoding="utf-8")
