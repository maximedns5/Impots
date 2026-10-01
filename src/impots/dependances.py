"""Quelles distributions le code IMPORTE, et lesquelles le projet DÉCLARE (D-161, D-165).

Un import non déclaré fonctionne tant que l'environnement le porte par accident, et casse
le jour où il est neuf — c'est-à-dire sur un runner. `pypdf` a vécu ainsi des semaines : il
n'était déclaré nulle part, n'arrivait par aucune transitive, et n'existait que sur la
machine du propriétaire. Le store macro était donc cassé sur CHAQUE runner, et son message
— « pypdf is required » — se lit comme un défaut de données.

**Ce module existe pour qu'il n'y ait qu'UNE copie de cette logique.** Le test qui garde la
propriété et le script `ci_local.py` qui la vérifie en environnement neuf lisent tous deux
d'ici. Deux copies dériveraient, et la forme est déjà au dossier : un contrat porté par deux
endroits n'est pas élargi tant que les deux ne le sont pas (D-151).

Les deux tables d'exception sont EXPLICITES et nommées une par une. Une normalisation qui
devinerait le nom de distribution depuis le nom d'import est précisément ce qui a laissé
passer `pypdf`.
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

#: Distributions dont le nom d'import diffère du nom de paquet.
ALIAS: dict[str, str] = {"yaml": "pyyaml", "sklearn": "scikit-learn"}

#: Modules qui ne sont pas des distributions : le paquet lui-même, et les scripts du dépôt
#: importés après un `sys.path.insert`. Nommés un par un, jamais par motif.
MODULES_LOCAUX: frozenset[str] = frozenset({
    "impots",
    # scripts du dépôt, importés après un `sys.path.insert(str(RACINE / "scripts"))`
    "verify_aft", "split_plf_articles", "write_plf_coverage", "ci_local",
    # PAS `scripts` : ce n'est pas un paquet. `from scripts.x import …` ne se résout que
    # sous `python -m pytest`, qui met la racine sur `sys.path` ; le `pytest` nu de la CI
    # ne l'y met pas (D-171). Absent d'ici, la garde des imports le signale.
    # aide de test vivant dans tests/ : `tests/knob_cases.py`, importé par test_knobs
    "knob_cases",
})

#: Les racines que l'on scanne par défaut. `src/` est le minimum ; `tests/` et `scripts/`
#: comptent aussi, parce qu'un import non déclaré y casse la CI tout autant.
RACINES_PAR_DEFAUT: tuple[str, ...] = ("src", "tests", "scripts")


def normaliser(nom: str) -> str:
    """PEP 503 : minuscules, et `-`, `_`, `.` équivalents.

    Sans cela `openfisca_core` (nom d'IMPORT) ne correspond pas à `openfisca-core` (nom de
    DISTRIBUTION), et la garde accuse des paquets parfaitement déclarés. Elle l'a fait.
    """
    return re.sub(r"[-_.]+", "-", nom.lower())


def declarees(racine: Path | None = None) -> set[str]:
    """Les distributions déclarées par `pyproject.toml`, normalisées."""
    chemin = (racine or RACINE) / "pyproject.toml"
    projet = tomllib.loads(chemin.read_text(encoding="utf-8"))["project"]
    lignes = list(projet.get("dependencies", []))
    for groupe in projet.get("optional-dependencies", {}).values():
        lignes.extend(groupe)
    return {normaliser(re.split(r"[<>=!\[ ]", ligne)[0]) for ligne in lignes}


def importees(racines: tuple[str, ...] = RACINES_PAR_DEFAUT,
              racine: Path | None = None) -> dict[str, str]:
    """Distribution tierce → premier fichier qui l'importe.

    Le module de tête seulement : `openfisca_france.model.x` compte pour
    `openfisca-france`. La bibliothèque standard et les modules locaux sont écartés.
    """
    base = racine or RACINE
    trouvees: dict[str, str] = {}
    for nom_racine in racines:
        for fichier in sorted((base / nom_racine).rglob("*.py")):
            try:
                arbre = ast.parse(fichier.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Import):
                    noms = [alias.name for alias in noeud.names]
                elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
                    noms = [noeud.module]
                else:
                    continue
                for nom in noms:
                    tete = nom.split(".")[0]
                    if not tete or tete in sys.stdlib_module_names or tete in MODULES_LOCAUX:
                        continue
                    distribution = normaliser(ALIAS.get(tete, tete))
                    trouvees.setdefault(distribution,
                                        str(fichier.relative_to(base)))
    return trouvees


def non_declarees(racines: tuple[str, ...] = RACINES_PAR_DEFAUT,
                  racine: Path | None = None) -> dict[str, str]:
    """Ce que le code importe et que `pyproject.toml` ne déclare pas."""
    connues = declarees(racine)
    return {d: f for d, f in importees(racines, racine).items() if d not in connues}


def modules_a_importer(racines: tuple[str, ...] = RACINES_PAR_DEFAUT,
                       racine: Path | None = None) -> list[str]:
    """Les noms d'IMPORT à essayer dans un environnement neuf.

    On rend les noms d'import, pas les noms de distribution : c'est `import yaml` qui
    échoue, pas « import pyyaml ». La table `ALIAS` est donc lue à l'envers.
    """
    inverse = {normaliser(v): k for k, v in ALIAS.items()}
    return sorted({inverse.get(d, d.replace("-", "_"))
                   for d in importees(racines, racine)})
