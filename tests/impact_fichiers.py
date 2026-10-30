"""La sélection par impact : ne relancer que les tests dont une dépendance a changé (D-309).

Un test passé est rejoué quand l'un de ses fichiers a changé depuis son dernier passage vert :
- un fichier Python qu'importe son fichier de tests, même indirectement. Le graphe est lu
  dans le source (`ast`), imports dans les fonctions compris, et non dans l'exécution ;
- un fichier qu'il lit (D-entrée, cas préenregistré, scénario, parquet de `data/`), relevé
  pendant son exécution par un crochet d'audit et par les lecteurs de polars ;
- un fichier Python exécuté pendant son passage (un script chargé par son chemin) ;
- les versions des bibliothèques dont le calcul dépend.

Pourquoi le source et pas la couverture : pytest-testmon suit les lignes exécutées, et
manque ce qu'un cache de processus n'exécute qu'une fois. Le système fiscal se construit
une seule fois par processus : réintroduire le bug de D-306 (un second `modify_parameters`
qui défaisait l'âge de 62 ans) ne relançait aucun des sept tests qui l'avaient vu. Un
cache ne retire jamais un import ; le graphe des imports le voit.

Toujours rejoués : un test qui n'a jamais passé, qui a échoué ou qui s'est sauté ; un
fichier de tests qui lance un sous-processus, dont ni l'import ni la lecture ne se voient.
Une lecture faite pendant la collecte (à l'import d'un module) vaut pour tous.

Le conftest compte par son texte et par les modules d'outillage des tests qu'il importe.
Son import du moteur ne sert qu'à le chauffer ; chaque test qui calcule l'importe lui-même.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

import pytest

OPTION = "--impact"
DOSSIER = Path(".cache") / "impact"
COLLECTE = "<collecte>"
IGNORES = (".git", ".cache", ".pytest_cache", ".ruff_cache", "__pycache__", ".venv",
           "node_modules")
#: Où un nom de module se résout dans le dépôt, dans cet ordre.
RACINES_CODE = ("src", "tests", "scripts")
#: Ce que lit pytest lui-même, et qui change tout.
GLOBAUX = ("pyproject.toml",)
#: Les bibliothèques dont le calcul dépend : une autre version, et tout est rejoué.
BIBLIOTHEQUES = ("openfisca-core", "openfisca-france", "numpy", "polars", "pydantic",
                 "pytest", "pyyaml", "pypdf")
LECTEURS_POLARS = ("read_parquet", "scan_parquet", "read_csv", "scan_csv", "read_ipc",
                   "scan_ipc", "read_json", "read_ndjson", "scan_ndjson", "read_excel")


# --- ce qui compte pour une lecture ---------------------------------------------------


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
    if not rel.parts or any(part in IGNORES for part in rel.parts) or rel.suffix == ".pyc":
        return None
    return rel.as_posix()


#: Vrai pendant que le greffon hache un fichier : ses propres lectures ne sont celles
#: d'aucun test, et la collecte les prendrait pour une dépendance de tous.
_HACHAGE = False


def empreinte(chemin: Path) -> list:
    """Taille, date et sha256 : les deux premières évitent de relire un fichier inchangé."""
    global _HACHAGE
    stat = chemin.stat()
    digest = hashlib.sha256()
    _HACHAGE = True
    try:
        with open(chemin, "rb") as flux:
            for bloc in iter(lambda: flux.read(1 << 20), b""):
                digest.update(bloc)
    finally:
        _HACHAGE = False
    return [stat.st_size, stat.st_mtime_ns, digest.hexdigest()]


class Empreintes:
    """Le sha256 de chaque fichier, calculé une fois par session ; un fichier dont la
    taille et la date n'ont pas bougé reprend celui du relevé."""

    def __init__(self, racine: Path, connues: dict[str, list] | None = None) -> None:
        self.racine, self.connues, self.vues = racine, dict(connues or {}), {}

    def sha(self, rel: str) -> str:
        if rel not in self.vues:
            chemin = self.racine / rel
            if not chemin.is_file():
                self.vues[rel] = "absent"
            else:
                stat, connue = chemin.stat(), self.connues.get(rel)
                if connue and [stat.st_size, stat.st_mtime_ns] == connue[:2]:
                    self.vues[rel] = connue[2]
                else:
                    self.connues[rel] = empreinte(chemin)
                    self.vues[rel] = self.connues[rel][2]
        return self.vues[rel]


# --- le graphe des imports --------------------------------------------------------------


def imports(source: str, module: str, paquet: bool) -> set[str]:
    """Les modules qu'un fichier importe, où que soit l'import (fonctions comprises).
    `from a import b` donne `a` et `a.b`, qui peut être un sous-module."""
    noms: set[str] = set()
    base = module if paquet else module.rpartition(".")[0]
    for noeud in ast.walk(ast.parse(source)):
        if isinstance(noeud, ast.Import):
            noms.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            if noeud.level:
                parts = base.split(".") if base else []
                if noeud.level > 1:
                    parts = parts[: len(parts) - (noeud.level - 1)]
                origine = ".".join(parts + ([noeud.module] if noeud.module else []))
            else:
                origine = noeud.module or ""
            if origine:
                noms.add(origine)
                noms.update(f"{origine}.{alias.name}" for alias in noeud.names)
    return noms


@dataclass
class Graphe:
    """Les fichiers Python du dépôt, et ce que chacun importe dans le dépôt."""

    racine: Path
    fichiers: dict[str, str] = field(default_factory=dict)  # module -> chemin relatif
    aretes: dict[str, set[str]] = field(default_factory=dict)  # chemin -> chemins

    @classmethod
    def lire(cls, racine: Path) -> Graphe:
        graphe = cls(racine)
        for base in RACINES_CODE:
            dossier = racine / base
            if not dossier.is_dir():
                continue
            for fichier in sorted(dossier.rglob("*.py")):
                rel = fichier.relative_to(dossier)
                if any(part in IGNORES for part in rel.parts):
                    continue
                parts = list(rel.with_suffix("").parts)
                if parts[-1] == "__init__":
                    parts.pop()
                if parts:
                    graphe.fichiers.setdefault(".".join(parts),
                                               fichier.relative_to(racine).as_posix())
        for module, chemin in list(graphe.fichiers.items()):
            fichier = racine / chemin
            try:
                noms = imports(fichier.read_text(encoding="utf-8"), module,
                               fichier.name == "__init__.py")
            except (SyntaxError, UnicodeDecodeError):
                noms = set()
            graphe.aretes[chemin] = {c for nom in noms for c in graphe._resoudre(nom)}
        return graphe

    def _resoudre(self, nom: str) -> set[str]:
        """Un nom importé et les paquets qui le contiennent : importer `a.b` exécute `a`."""
        parts = nom.split(".")
        return {self.fichiers[".".join(parts[:i])] for i in range(1, len(parts) + 1)
                if ".".join(parts[:i]) in self.fichiers}

    def fermeture(self, depart: str) -> set[str]:
        vus, pile = set(), [depart]
        while pile:
            chemin = pile.pop()
            if chemin not in vus:
                vus.add(chemin)
                pile.extend(self.aretes.get(chemin, ()))
        return vus


def versions() -> str:
    out = []
    for nom in BIBLIOTHEQUES:
        try:
            out.append(f"{nom}=={metadata.version(nom)}")
        except metadata.PackageNotFoundError:
            out.append(f"{nom}==absent")
    return ";".join(out)


# --- le relevé, d'une exécution à l'autre ----------------------------------------------


def _recent(a: dict, b: dict) -> dict:
    """Clé par clé, l'entrée la plus récente : un test passe sur un worker puis sur un
    autre, et c'est son dernier passage qui compte. Une entrée est `[valeur, instant]`."""
    out = dict(a)
    for cle, entree in b.items():
        if cle not in out or entree[1] >= out[cle][1]:
            out[cle] = entree
    return out


def fusionner(ancien: dict, neuf: dict) -> dict:
    """Le plus récent l'emporte, module par module et test par test. Un test rejoué sans
    passer laisse une entrée vide : il sera rejoué encore."""
    empreintes = dict(ancien.get("empreintes", {}))
    empreintes.update(neuf.get("empreintes", {}))
    return {"version": 2,
            "modules": _recent(ancien.get("modules", {}), neuf.get("modules", {})),
            "passes": _recent(ancien.get("passes", {}), neuf.get("passes", {})),
            "collecte": sorted(set(ancien.get("collecte", [])) | set(neuf.get("collecte", []))),
            "empreintes": empreintes}


def charger(racine: Path) -> dict:
    """Tous les relevés du dépôt, un par processus qui a fait tourner des tests."""
    total: dict = {}
    for fichier in sorted((racine / DOSSIER).glob("selection.*.json")):
        try:
            donnees = json.loads(fichier.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if donnees.get("version") == 2:
            total = fusionner(total, donnees)
    return total


@dataclass
class Dependances:
    """L'empreinte de ce dont dépend chaque fichier de tests, telle qu'elle est maintenant."""

    graphe: Graphe
    lectures: dict[str, list[str]]  # fichier de tests -> fichiers lus
    collecte: list[str]
    empreintes: Empreintes
    conftests: tuple[str, ...]
    _cache: dict[str, str] = field(default_factory=dict)

    def fichiers(self, module: str) -> set[str]:
        """Les fichiers dont dépend un fichier de tests : ses imports, les conftests et
        l'outillage des tests qu'ils importent, ses lectures, la collecte, les globaux."""
        out = set(GLOBAUX) | self.graphe.fermeture(module) | set(self.collecte)
        for conftest in self.conftests:
            out |= {c for c in self.graphe.fermeture(conftest) if c.startswith("tests/")}
        out |= set(self.lectures.get(module, ()))
        return out

    def digest(self, module: str) -> str:
        if module not in self._cache:
            h = hashlib.sha256(versions().encode())
            for chemin in sorted(self.fichiers(module)):
                h.update(f"\n{chemin}\0{self.empreintes.sha(chemin)}".encode())
            self._cache[module] = h.hexdigest()
        return self._cache[module]


def lectures_de(releve: dict) -> dict[str, list[str]]:
    return {module: entree[0]["fichiers"] for module, entree in releve.get("modules", {}).items()}


def toujours(releve: dict) -> set[str]:
    return {module for module, entree in releve.get("modules", {}).items()
            if entree[0].get("sous_processus")}


@dataclass
class Releve:
    """Ce que ce processus a vu : lectures par fichier de tests, sous-processus, issues."""

    racine: Path
    #: Le fichier de tests en cours, COLLECTE pendant la collecte, None ailleurs : entre
    #: deux tests, les rapports de pytest lisent pour eux-mêmes, pas pour un test.
    courant: str | None = COLLECTE
    lectures: dict[str, set[str]] = field(default_factory=dict)
    sous_processus: set[str] = field(default_factory=set)
    issues: dict[str, str] = field(default_factory=dict)  # nodeid -> "vert" | "rouge"
    actif: bool = True

    def lire(self, chemin: object, code: bool = False) -> None:
        if not self.actif or self.courant is None or _HACHAGE:
            return
        rel = relatif(chemin, self.racine)
        if rel is None:
            return
        if code and not (rel.endswith(".py") and (self.racine / rel).is_file()):
            return  # le code d'un `exec("…")`, `<string>` : pas un fichier
        if rel.endswith(".py") and (not code or self.courant == COLLECTE):
            return  # les imports de la collecte sont au graphe, pas au relevé
        self.lectures.setdefault(self.courant, set()).add(rel)

    def audit(self, evenement: str, args: tuple) -> None:
        if evenement == "open" and len(args) >= 3 and en_lecture(args[1], args[2]):
            self.lire(args[0])
        elif evenement == "exec" and args and hasattr(args[0], "co_filename"):
            self.lire(args[0].co_filename, code=True)
        elif evenement == "subprocess.Popen" and self.courant not in (None, COLLECTE):
            self.sous_processus.add(self.courant)

    def noter(self, report) -> None:
        """Vert sur ses trois phases, ou rouge : un échec ou un saut, à n'importe laquelle."""
        if report.failed or report.skipped:
            self.issues[report.nodeid] = "rouge"
        elif report.when == "call" and self.issues.get(report.nodeid) != "rouge":
            self.issues[report.nodeid] = "vert"


# --- le greffon ---------------------------------------------------------------------------


def ajouter_options(parser) -> None:
    parser.addoption(OPTION, action="store_true", default=False,
                     help="ne lancer que les tests dont un fichier importé ou lu a changé "
                          "depuis leur dernier passage vert, et relever ce qu'ils lisent "
                          "(D-309)")


def configurer(config) -> None:
    """Appelé par le `pytest_configure` du conftest, qui a déjà le sien. Le maître de
    xdist ne fait tourner aucun test : il ne sélectionne ni ne relève rien."""
    maitre_xdist = (getattr(config.option, "dist", "no") != "no"
                    and not hasattr(config, "workerinput"))
    if config.getoption(OPTION) and not maitre_xdist:
        config.pluginmanager.register(Greffon(config), "impact_fichiers")


def module_de(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


class Greffon:
    def __init__(self, config) -> None:
        self.racine = Path(str(config.rootpath))
        self.ancien = charger(self.racine)
        self.graphe = Graphe.lire(self.racine)
        self.conftests = tuple(sorted(
            p.relative_to(self.racine).as_posix() for p in self.racine.glob("tests/**/conftest.py")
            if not any(part in IGNORES for part in p.parts)))
        self.empreintes = Empreintes(self.racine, self.ancien.get("empreintes", {}))
        self.dependances = Dependances(self.graphe, lectures_de(self.ancien),
                                       self.ancien.get("collecte", []), self.empreintes,
                                       self.conftests)
        self.toujours = toujours(self.ancien)
        self.releve = Releve(self.racine)
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

    def a_jour(self, nodeid: str) -> bool:
        """Le dernier passage vert de ce test vaut encore : rien de ce dont il dépend n'a
        bougé depuis."""
        module = module_de(nodeid)
        passe = self.ancien.get("passes", {}).get(nodeid)
        return (module not in self.toujours and passe is not None and passe[0] is not None
                and passe[0] == self.dependances.digest(module))

    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, session, config, items):
        gardes, ecartes = [], []
        for item in items:
            (ecartes if self.a_jour(item.nodeid) else gardes).append(item)
        if ecartes:
            items[:] = gardes
            config.hook.pytest_deselected(items=ecartes)

    # Seules les trois phases du test comptent. Entre elles, les rapports font tourner le
    # code des greffons, qui n'est pas au test.
    def pytest_collection_finish(self, session) -> None:
        self.releve.courant = None

    def _phase(self, item):
        self.releve.courant = module_de(item.nodeid)
        try:
            yield
        finally:
            self.releve.courant = None

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(self, item):
        yield from self._phase(item)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        yield from self._phase(item)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_teardown(self, item, nextitem):
        yield from self._phase(item)

    def pytest_runtest_logreport(self, report) -> None:
        self.releve.noter(report)

    def pytest_sessionfinish(self, session, exitstatus) -> None:
        """L'empreinte d'un test vert se prend après le passage, ses lectures comprises :
        c'est elle que le prochain passage comparera."""
        releve = self.releve
        releve.actif = False
        maintenant = time.time_ns()
        modules = {m: [{"fichiers": sorted(c), "sous_processus": m in releve.sous_processus},
                       maintenant]
                   for m, c in releve.lectures.items() if m != COLLECTE}
        for m in releve.sous_processus - set(modules):
            modules[m] = [{"fichiers": [], "sous_processus": True}, maintenant]
        tout = fusionner(self.ancien, {"modules": modules,
                                       "collecte": sorted(releve.lectures.get(COLLECTE, ()))})
        apres = Dependances(self.graphe, lectures_de(tout), tout["collecte"],
                            Empreintes(self.racine, self.empreintes.connues), self.conftests)
        passes = {nodeid: [apres.digest(module_de(nodeid)) if issue == "vert" else None,
                           maintenant]
                  for nodeid, issue in releve.issues.items()}
        lus = {c for m in modules.values() for c in m[0]["fichiers"]} | set(tout["collecte"])
        neuf = {"version": 2, "modules": modules, "passes": passes,
                "collecte": tout["collecte"],
                "empreintes": {c: v for c, v in apres.empreintes.connues.items() if c in lus}}
        travailleur = os.environ.get("PYTEST_XDIST_WORKER", "seul")
        cible = self.racine / DOSSIER / f"selection.{travailleur}.json"
        cible.parent.mkdir(parents=True, exist_ok=True)
        try:
            ancien = json.loads(cible.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            ancien = {}
        provisoire = cible.with_name(f".{cible.name}.{os.getpid()}.tmp")
        provisoire.write_text(json.dumps(fusionner(ancien, neuf), indent=1, sort_keys=True),
                              encoding="utf-8")
        os.replace(provisoire, cible)
