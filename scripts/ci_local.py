#!/usr/bin/env python
"""Rejoue la CI dans un ENVIRONNEMENT NEUF, sur cette machine, sans une minute de runner.

POURQUOI CE SCRIPT EXISTE. `make full` vérifie la correction ; il ne peut pas vérifier
l'ENVIRONNEMENT, parce qu'il tourne dans celui du propriétaire. `pypdf` a survécu à quinze
passes locales vertes : il n'était déclaré nulle part, n'arrivait par aucune transitive, et
n'existait que sur cette machine, installé à la main il y a longtemps. Le store macro était
donc cassé sur CHAQUE runner — et son message, « pypdf is required », se lit comme un défaut
de données, si bien qu'il a été classé parmi les rouges « fichiers manquants » (D-161).

Ce que la CI apporte d'irremplaçable est donc exactement cela : un arbre propre, un venv
reconstruit depuis le seul `pyproject.toml`, un `data/raw/` ne contenant que ce que git
suit. Tout cela se reproduit ici. Le dépôt est PRIVÉ, donc les minutes Actions sont
facturées et se sont épuisées en pleine revue ; cette vérification-là ne doit pas dépendre
d'un quota.

DEUX MODES.

* `--deps` (≈ 2 min) : worktree jetable, venv neuf, installation depuis `pyproject.toml`
  SEUL, puis tentative d'import de chaque module tiers que `src/`, `tests/` et `scripts/`
  nomment. C'est le mode qui attrape la classe `pypdf`, et il est assez court pour tourner
  souvent.
* défaut (≈ 15 min) : tout ce qui précède, plus la chaîne de données complète (fetch,
  construction, préflight) et le sous-ensemble rapide `-m "not slow"` — c'est-à-dire les
  étapes du job `fast` de la CI, dans l'ordre.

CE QU'IL NE FAIT PAS. Il ne touche jamais au worktree principal : le worktree jetable est
créé par `git worktree add` sur HEAD, et retiré à la fin, y compris en cas d'échec. Les
téléchargements du mode complet vont dans le `data/raw/` du worktree, jamais dans celui du
dépôt.

Usage :
    make ci-local          # mode complet
    make ci-deps           # mode --deps
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))


class EchecEtape(RuntimeError):
    """Une étape de la chaîne a échoué. Le worktree est retiré quand même."""


def _run(commande: list[str], *, cwd: Path, env_venv: Path | None = None,
         journal: Path | None = None) -> tuple[int, str]:
    """Lance une commande, rend (code, sortie). Ne lève pas : l'appelant décide."""
    if env_venv is not None:
        commande = [str(env_venv / "bin" / commande[0]), *commande[1:]]
    acheve = subprocess.run(commande, cwd=str(cwd), capture_output=True, text=True)
    sortie = acheve.stdout + acheve.stderr
    if journal is not None:
        journal.write_text(sortie, encoding="utf-8")
    return acheve.returncode, sortie


def _venv_neuf(worktree: Path) -> Path:
    """Un venv reconstruit depuis zéro, SANS les paquets du système.

    Jamais `--system-site-packages` : c'est l'héritage des paquets de l'hôte qui rendrait
    ce script incapable de voir ce qu'il existe pour voir.
    """
    venv = worktree / ".venv"
    if shutil.which("uv"):
        code, sortie = _run(["uv", "venv", str(venv), "--python", "3.11"], cwd=worktree)
        if code != 0:
            raise EchecEtape(f"uv venv a échoué :\n{sortie[-800:]}")
    else:
        code, sortie = _run([sys.executable, "-m", "venv", str(venv)], cwd=worktree)
        if code != 0:
            raise EchecEtape(f"python -m venv a échoué :\n{sortie[-800:]}")
    return venv


def _installer(worktree: Path, venv: Path) -> None:
    """Installe depuis `pyproject.toml` SEUL — aucune liste de paquets écrite ici.

    Un `pip install pypdf` ajouté à la main dans ce script masquerait exactement le défaut
    qu'il cherche. La seule source de vérité est le `pyproject.toml` du worktree.
    """
    uv = shutil.which("uv")
    if uv:
        # CHEMIN ABSOLU et environnement réel. Une première version passait un PATH
        # restreint pour « isoler », et `uv` n'y était pas — FileNotFoundError. L'isolation
        # qui compte est celle du VENV, pas celle du PATH : c'est `VIRTUAL_ENV` qui décide
        # où les paquets atterrissent.
        import os

        env = {**os.environ, "VIRTUAL_ENV": str(venv)}
        env.pop("PYTHONPATH", None)          # ne pas laisser fuiter le src/ de l'hôte
        acheve = subprocess.run([uv, "pip", "install", "-e", ".[dev]"],
                                cwd=str(worktree), capture_output=True, text=True, env=env)
        code, sortie = acheve.returncode, acheve.stdout + acheve.stderr
    else:
        code, sortie = _run(["pip", "install", "-e", ".[dev]"], cwd=worktree, env_venv=venv)
    if code != 0:
        raise EchecEtape(f"l'installation depuis pyproject.toml a échoué :\n{sortie[-1200:]}")


def verifier_imports(worktree: Path, venv: Path) -> list[str]:
    """Essaie d'importer chaque module tiers que le code nomme. Rend les manquants.

    La liste vient de `impots.dependances`, lue dans le WORKTREE et non dans le dépôt
    courant : c'est l'arbre publié qui est jugé.
    """
    programme = (
        "import importlib, sys\n"
        "sys.path.insert(0, 'src')\n"
        "from impots.dependances import modules_a_importer\n"
        "manquants = []\n"
        "for m in modules_a_importer():\n"
        "    try:\n"
        "        importlib.import_module(m)\n"
        "    except Exception as e:\n"
        "        manquants.append(f'{m} ({type(e).__name__})')\n"
        "print('MANQUANTS:' + ','.join(manquants))\n"
    )
    _, sortie = _run(["python", "-c", programme], cwd=worktree, env_venv=venv)
    # Le code de retour n'est pas lu : le sous-programme sort à 0 même quand des imports
    # manquent, parce que la liste des manquants EST son résultat. Un code non nul
    # signifierait que le programme lui-même n'a pas tourné, et c'est l'absence de la
    # ligne « MANQUANTS: » qui le dit.
    ligne = next((x for x in sortie.splitlines() if x.startswith("MANQUANTS:")), None)
    if ligne is None:
        raise EchecEtape(f"la vérification d'imports n'a rien rendu :\n{sortie[-800:]}")
    reste = ligne.removeprefix("MANQUANTS:").strip()
    return [x for x in reste.split(",") if x]


ETAPES_CHAINE = (
    ("contrôle des épinglages", ["python", "scripts/verify_openfisca.py"]),
    ("lint", ["ruff", "check", "src", "tests", "scripts"]),
    ("fetch des sources", ["impots", "data", "fetch", "--profile", "tests"]),
    ("construction cellules", ["impots", "entreprises", "cells"]),
    ("construction population", ["impots", "population", "build"]),
    ("préflight", ["impots", "data", "check", "--profile", "tests"]),
)

#: La commande de test du job `fast`, MOT POUR MOT. `python -m pytest` met la racine du
#: dépôt sur `sys.path`, le `pytest` nu de la CI non : avec la première, ce script a
#: rejoué la CI en résolvant un import qu'elle ne résout pas (D-171). Un test la compare
#: au workflow.
COMMANDE_TESTS = ["pytest", "-q", "-m", "not slow"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deps", action="store_true",
                        help="s'arrêter après la vérification des imports (≈ 2 min)")
    parser.add_argument("--garder", action="store_true",
                        help="ne pas retirer le worktree, pour inspecter après un échec")
    parser.add_argument("--ref", default="HEAD",
                        help="la référence à juger (défaut HEAD). Sert à éprouver une "
                             "branche avant de la fusionner — et à vérifier que cette "
                             "vérification sait échouer, sur une branche jetable")
    args = parser.parse_args()

    base = Path(tempfile.mkdtemp(prefix="impots-ci-"))
    worktree = base / "arbre"
    debut = time.time()
    echecs: list[str] = []

    def dire(etat: str, quoi: str, detail: str = "") -> None:
        marque = {"ok": "  OK   ", "ko": "  ÉCHEC", "..": "  ···  "}[etat]
        print(f"{marque} {quoi}" + (f"  {detail}" if detail else ""), flush=True)

    try:
        print("=== CI locale : environnement NEUF, aucune minute de runner ===")
        code, sortie = _run(["git", "worktree", "add", "--detach", str(worktree),
                             args.ref], cwd=RACINE)
        if code != 0:
            print(f"  ÉCHEC création du worktree :\n{sortie[-600:]}", file=sys.stderr)
            return 1
        dire("ok", f"worktree jetable sur « {args.ref} »", str(worktree))
        suivis = sorted(p.name for p in (worktree / "data" / "raw").glob("*"))
        dire("ok", "data/raw ne contient que ce que git suit", str(suivis))

        venv = _venv_neuf(worktree)
        dire("ok", "venv neuf, sans les paquets du système")
        _installer(worktree, venv)
        dire("ok", "installé depuis pyproject.toml seul")

        manquants = verifier_imports(worktree, venv)
        if manquants:
            dire("ko", "imports tiers", f"MANQUANTS : {manquants}")
            echecs.append("dépendances non déclarées : " + ", ".join(manquants))
        else:
            dire("ok", "chaque module tiers nommé par le code s'importe")

        if not args.deps and not echecs:
            for nom, commande in ETAPES_CHAINE:
                code, sortie = _run(commande, cwd=worktree, env_venv=venv,
                                    journal=base / f"{nom.replace(' ', '_')}.log")
                if code == 0:
                    dire("ok", nom)
                else:
                    dire("ko", nom, f"code {code} — voir {base}")
                    echecs.append(f"{nom} (code {code})")
                    break
            if not echecs:
                dire("..", "sous-ensemble rapide `-m \"not slow\"` (≈ 11 min)")
                code, _ = _run(COMMANDE_TESTS,
                               cwd=worktree, env_venv=venv, journal=base / "pytest.log")
                resume = (base / "pytest.log").read_text(encoding="utf-8").splitlines()
                derniere = next((x for x in reversed(resume)
                                 if "passed" in x or "failed" in x), "")
                if code == 0:
                    dire("ok", "sous-ensemble rapide", derniere.strip())
                else:
                    dire("ko", "sous-ensemble rapide", derniere.strip() or f"code {code}")
                    echecs.append("sous-ensemble rapide")
    except EchecEtape as erreur:
        dire("ko", "chaîne interrompue", str(erreur)[:300])
        echecs.append(str(erreur)[:120])
    finally:
        if args.garder:
            print(f"\nworktree conservé : {worktree}")
        else:
            _run(["git", "worktree", "remove", "--force", str(worktree)], cwd=RACINE)
            shutil.rmtree(base, ignore_errors=True)

    duree = int(time.time() - debut)
    print(f"\n{duree // 60} min {duree % 60:02d} s")
    if echecs:
        print(f"{len(echecs)} étape(s) en échec :", file=sys.stderr)
        for e in echecs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("CI locale verte — ce qu'un runner aurait vérifié, vérifié ici.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
