"""Les fichiers que les tests lisent hors du code Python, pour la sélection par impact (D-309).

pytest-testmon sait quelles lignes Python chaque test exécute, et ne relance que les tests
dont ces lignes ont changé. Il ne voit pas les fichiers qu'ils lisent : les D-entrées, les
cas préenregistrés, les scénarios, les pages rendues, les PDF et les parquets de `data/`.
Ce greffon, activé par `--fichiers-lus`, les relève pendant l'exécution, par fichier de
tests et avec leur empreinte. À la sélection suivante, un fichier de tests dont une
lecture a changé est rendu à la sélection tout entier.

Ce qui reste hors de vue est dit, pas deviné :
- un fichier de tests qui lance un sous-processus est toujours relancé : ni testmon ni ce
  relevé ne voient ce qui s'y exécute ou s'y lit ;
- une lecture faite pendant la collecte (à l'import d'un module) vaut pour tous les
  fichiers de tests : qui l'a faite en premier n'est qu'un accident d'ordre.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

OPTION = "--fichiers-lus"
DOSSIER = Path(".cache") / "impact"
#: Les lectures faites hors d'un test (à la collecte) : elles valent pour tous.
COLLECTE = "<collecte>"
#: Ce qui n'est jamais une dépendance de données : le code (testmon le suit), les caches.
IGNORES = (".git", ".cache", ".pytest_cache", ".ruff_cache", "__pycache__", ".venv")
SUFFIXES_CODE = (".py", ".pyc")
#: Les lecteurs de polars ouvrent le fichier en Rust, hors du crochet d'audit de Python.
LECTEURS_POLARS = ("read_parquet", "scan_parquet", "read_csv", "scan_csv", "read_ipc",
                   "scan_ipc", "read_json", "read_ndjson", "scan_ndjson", "read_excel")


def en_lecture(mode: object, flags: object) -> bool:
    """Une ouverture qui ne fait que lire : `open()` donne un mode, `os.open` des drapeaux."""
    if isinstance(mode, str):
        return not any(c in mode for c in "wax+")
    if isinstance(flags, int):
        return not flags & (os.O_WRONLY | os.O_RDWR)
    return True


def relatif(chemin: object, racine: Path) -> str | None:
    """Le chemin d'une lecture, relatif à la racine du dépôt ; None s'il n'en est pas.

    Sans résoudre les liens : `data/` est fait de liens vers des fichiers tenus ailleurs,
    et c'est le chemin que le code lit qui compte, pas celui où il pointe."""
    if isinstance(chemin, int):
        return None
    try:
        absolu = Path(os.path.abspath(os.fsdecode(os.fspath(chemin))))
        rel = absolu.relative_to(racine)
    except (TypeError, ValueError):
        return None
    if any(part in IGNORES for part in rel.parts):
        return None
    if rel.suffix in SUFFIXES_CODE:
        return None
    return rel.as_posix()


def empreinte(chemin: Path) -> list:
    """Taille, date et sha256 : les deux premières évitent de relire un fichier inchangé."""
    stat = chemin.stat()
    digest = hashlib.sha256()
    with open(chemin, "rb") as flux:
        for bloc in iter(lambda: flux.read(1 << 20), b""):
            digest.update(bloc)
    return [stat.st_size, stat.st_mtime_ns, digest.hexdigest()]


def a_change(chemin: Path, connue: list) -> bool:
    """Le fichier n'est plus celui que le test a lu : absent, ou d'un autre contenu."""
    if not chemin.is_file():
        return True
    stat = chemin.stat()
    if [stat.st_size, stat.st_mtime_ns] == connue[:2]:
        return False
    return empreinte(chemin)[2] != connue[2]


def a_relancer(releve: dict, racine: Path) -> tuple[set[str], bool]:
    """Les fichiers de tests à rendre à la sélection, et si tous doivent l'être.

    Un fichier de tests est rendu quand une lecture qu'il a faite a changé depuis, ou
    quand il lance un sous-processus. Tous le sont quand une lecture de la collecte a
    changé."""
    modules: set[str] = set()
    for module, entree in releve.get("modules", {}).items():
        if entree.get("sous_processus") or any(
                a_change(racine / chemin, connue)
                for chemin, connue in entree.get("fichiers", {}).items()):
            modules.add(module)
    tout = any(a_change(racine / chemin, connue)
               for chemin, connue in releve.get("collecte", {}).items())
    return modules, tout


def fusionner(ancien: dict, neuf: dict) -> dict:
    """Le relevé d'une exécution remplace, module par module, celui de la précédente ; un
    module qui n'a pas tourné garde le sien. La collecte s'additionne."""
    modules = dict(ancien.get("modules", {}))
    modules.update(neuf.get("modules", {}))
    collecte = dict(ancien.get("collecte", {}))
    collecte.update(neuf.get("collecte", {}))
    return {"version": 1, "modules": modules, "collecte": collecte}


def charger(racine: Path) -> dict:
    """Tous les relevés du dépôt, un par processus (le maître et chaque worker xdist)."""
    total: dict = {}
    for fichier in sorted((racine / DOSSIER).glob("fichiers_lus.*.json")):
        try:
            total = fusionner(total, json.loads(fichier.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return total


@dataclass
class Releve:
    """Ce que ce processus a vu lire : par fichier de tests, et pendant la collecte."""

    racine: Path
    courant: str = COLLECTE
    lectures: dict[str, set[str]] = field(default_factory=dict)
    sous_processus: set[str] = field(default_factory=set)
    actif: bool = True

    def lire(self, chemin: object) -> None:
        if not self.actif:
            return
        rel = relatif(chemin, self.racine)
        if rel is not None:
            self.lectures.setdefault(self.courant, set()).add(rel)

    def audit(self, evenement: str, args: tuple) -> None:
        if evenement == "open" and len(args) >= 3 and en_lecture(args[1], args[2]):
            self.lire(args[0])
        elif evenement == "subprocess.Popen" and self.courant != COLLECTE:
            self.sous_processus.add(self.courant)

    def ecrire(self) -> Path:
        self.actif = False
        def figer(chemins: set[str]) -> dict:
            out = {}
            for chemin in sorted(chemins):
                fichier = self.racine / chemin
                if fichier.is_file():
                    out[chemin] = empreinte(fichier)
            return out
        modules = {module: {"fichiers": figer(chemins),
                            "sous_processus": module in self.sous_processus}
                   for module, chemins in self.lectures.items() if module != COLLECTE}
        for module in self.sous_processus - set(modules):
            modules[module] = {"fichiers": {}, "sous_processus": True}
        neuf = {"modules": modules, "collecte": figer(self.lectures.get(COLLECTE, set()))}
        travailleur = os.environ.get("PYTEST_XDIST_WORKER", "maitre")
        cible = self.racine / DOSSIER / f"fichiers_lus.{travailleur}.json"
        cible.parent.mkdir(parents=True, exist_ok=True)
        ancien = json.loads(cible.read_text(encoding="utf-8")) if cible.exists() else {}
        provisoire = cible.with_name(f".{cible.name}.{os.getpid()}.tmp")
        provisoire.write_text(json.dumps(fusionner(ancien, neuf), indent=1, sort_keys=True),
                              encoding="utf-8")
        os.replace(provisoire, cible)
        return cible


def ajouter_options(parser) -> None:
    parser.addoption(OPTION, action="store_true", default=False,
                     help="relever les fichiers non Python que lit chaque fichier de tests, "
                          "et rendre à la sélection de testmon ceux dont une lecture a "
                          "changé (D-309)")


def configurer(config) -> None:
    """Appelé par le `pytest_configure` du conftest, qui a déjà le sien."""
    if config.getoption(OPTION):
        config.pluginmanager.register(Greffon(config), "impact_fichiers")


class Greffon:
    def __init__(self, config) -> None:
        self.config = config
        self.racine = Path(str(config.rootpath))
        self.releve = Releve(self.racine)
        self.modules, self.tout = a_relancer(charger(self.racine), self.racine)
        self.retires: set[str] = set()
        sys.addaudithook(self.releve.audit)
        import polars

        for nom in LECTEURS_POLARS:
            original = getattr(polars, nom, None)
            if original is not None and not getattr(original, "_releve", False):
                setattr(polars, nom, self._espion(original))

    def _espion(self, original):
        releve = self.releve

        def lecteur(source=None, *args, **kwargs):
            if isinstance(source, (str, os.PathLike)):
                releve.lire(source)
            return original(source, *args, **kwargs)

        lecteur._releve = True
        lecteur.__wrapped__ = original
        return lecteur

    def _selectionne(self) -> bool:
        testmon = getattr(self.config, "testmon_config", None)
        return bool(testmon is not None and getattr(testmon, "select", False))

    def _rendu(self, module: str) -> bool:
        return self.tout or module in self.modules

    @pytest.hookimpl(tryfirst=True)
    def pytest_ignore_collect(self, collection_path, config):
        # Un fichier de tests seulement : forcer un dossier passerait outre `.venv` et
        # `norecursedirs`, que pytest règle par ce même crochet.
        chemin = Path(str(collection_path))
        if (not self._selectionne() or chemin.suffix != ".py"
                or not chemin.name.startswith("test_")):
            return None
        rel = Path(os.path.relpath(chemin, self.racine)).as_posix()
        return False if self._rendu(rel) else None

    def pytest_deselected(self, items) -> None:
        self.retires.update(getattr(item, "nodeid", "") for item in items)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_collection_modifyitems(self, session, config, items):
        avant = list(items)
        yield
        if not self._selectionne():
            return
        gardes = {item.nodeid for item in items}
        for item in avant:
            module = item.nodeid.split("::", 1)[0]
            if (item.nodeid not in gardes and item.nodeid not in self.retires
                    and self._rendu(module)):
                items.append(item)

    # Seules les trois phases du test comptent. Entre elles, les rapports font tourner le
    # code des greffons : testmon y lance `git ls-files`, qui n'est pas au test.
    def _phase(self, item):
        self.releve.courant = item.nodeid.split("::", 1)[0]
        try:
            yield
        finally:
            self.releve.courant = COLLECTE

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(self, item):
        yield from self._phase(item)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        yield from self._phase(item)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(self, item, nextitem):
        yield from self._phase(item)

    def pytest_sessionfinish(self, session, exitstatus) -> None:
        self.releve.ecrire()
