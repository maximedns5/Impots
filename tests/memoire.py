"""La mémoire de chaque test, pour tenir les lourds à l'écart de la passe parallèle (D-309).

Un passage de 20 000 ménages au palier complet tient plusieurs Go. Deux workers xdist qui en
lancent chacun un ont dépassé les 15 Go de la machine, et le noyau a tué trois workers :
leurs tests sont tombés en échec sans avoir rien testé. Groupés sur un seul worker, ils y
ont accumulé 9 Go, et ce worker a été tué à son tour, à côté des trois autres. `--memoire`
relève, par test, de combien la mémoire résidente du processus est montée au-dessus de ce
qu'elle était au départ du test. Un test qui monte de plus de `SEUIL_LOURD_MO` est lourd :
`tests/lourds.txt` le marque `lourd`, et `make impact` lance ces tests seuls, dans un seul
processus, après la passe parallèle.

La mémoire est échantillonnée pendant le test : le pic du processus (`ru_maxrss`) ne monte
qu'une fois, au premier test lourd, et tairait les suivants. Le relevé s'écrit après chaque
test : un worker tué ne l'emporte pas avec lui.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

OPTION = "--memoire"
FICHIER_LOURDS = Path(__file__).with_name("lourds.txt")
#: Ce qui fait d'un test un lourd : sa hausse de mémoire résidente pendant son passage.
SEUIL_LOURD_MO = 1024
PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
#: Le pas de l'échantillonnage, en secondes.
PERIODE = 0.1


def ajouter_options(parser) -> None:
    parser.addoption(OPTION, action="store_true", default=False,
                     help="relever la hausse de mémoire de chaque test (D-309)")


def lourds() -> frozenset[str]:
    """Les tests rangés lourds, par identifiant pytest ; vide si le fichier manque."""
    if not FICHIER_LOURDS.exists():
        return frozenset()
    lignes = FICHIER_LOURDS.read_text(encoding="utf-8").splitlines()
    return frozenset(ligne.split("#", 1)[0].strip() for ligne in lignes
                     if ligne.split("#", 1)[0].strip())


def grouper(items) -> None:
    """Marque les lourds `lourd`, que `-m` écarte ou choisit. Ils sont aussi dans le groupe
    xdist « lourd » : sous `--dist loadgroup`, une passe parallèle qui les garde les met sur
    un seul worker, l'un après l'autre. Sans xdist, ce groupe ne fait rien."""
    connus = lourds()
    for item in items:
        if item.nodeid in connus:
            item.add_marker(pytest.mark.lourd)
            item.add_marker(pytest.mark.xdist_group("lourd"))


def proposes(hausses: dict[str, float]) -> list[str]:
    """Les tests qu'un relevé range lourds : ceux qui montent de plus de `SEUIL_LOURD_MO`."""
    return sorted(test for test, hausse in hausses.items() if hausse > SEUIL_LOURD_MO)


def residente_mo() -> float:
    """La mémoire résidente du processus maintenant, en Mo."""
    with open("/proc/self/statm", encoding="ascii") as statm:
        return int(statm.read().split()[1]) * PAGE / (1024 * 1024)


class Groupement:
    """Marque les lourds avant que xdist ne lise les groupes. Le
    `pytest_collection_modifyitems` d'un worker xdist lit `xdist_group` sur chaque test ;
    celui d'un conftest passe après lui, et une marque mise là arrivait trop tard : les
    lourds partaient sur tous les workers à la fois."""

    @pytest.hookimpl(tryfirst=True)
    def pytest_collection_modifyitems(self, items) -> None:
        grouper(items)


def configurer(config) -> None:
    config.pluginmanager.register(Groupement(), "memoire-groupement")
    if config.getoption(OPTION):
        config.pluginmanager.register(Releve(config), "memoire")


class Releve:
    def __init__(self, config) -> None:
        # Le nom vient de xdist, pas de l'environnement : un pytest lancé par un test sous
        # xdist hérite de PYTEST_XDIST_WORKER sans être un worker.
        travailleur = getattr(config, "workerinput", {}).get("workerid", "seul")
        racine = Path(str(config.rootpath))
        self.cible = racine / ".cache" / "impact" / f"memoire.{travailleur}.json"
        self.hausses: dict[str, float] = {}
        self.pic = 0.0
        self.arret = threading.Event()
        threading.Thread(target=self._echantillonner, daemon=True).start()

    def _echantillonner(self) -> None:
        while not self.arret.wait(PERIODE):
            self.pic = max(self.pic, residente_mo())

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_protocol(self, item, nextitem):
        depart = residente_mo()
        self.pic = depart
        yield
        self.pic = max(self.pic, residente_mo())
        self.hausses[item.nodeid] = round(self.pic - depart, 1)
        self._ecrire()

    def _ecrire(self) -> None:
        self.cible.parent.mkdir(parents=True, exist_ok=True)
        provisoire = self.cible.with_name(f".{self.cible.name}.{os.getpid()}.tmp")
        try:
            provisoire.write_text(json.dumps(self.hausses, indent=1, sort_keys=True),
                                  encoding="utf-8")
            os.replace(provisoire, self.cible)
        finally:
            provisoire.unlink(missing_ok=True)

    def pytest_sessionfinish(self, session, exitstatus) -> None:
        self.arret.set()


if __name__ == "__main__":
    import sys

    releves: dict[str, float] = {}
    for chemin in sys.argv[1:]:
        releves.update(json.loads(Path(chemin).read_text(encoding="utf-8")))
    for test in proposes(releves):
        print(f"{test}  # {releves[test]:.0f} Mo")
