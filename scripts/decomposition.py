"""La décomposition de D-354 : ce que pèsent E1 et E2 dans les études qu'elles touchent.

    python scripts/decomposition.py lancer --ou "..."   # les cinq passes, l'une après l'autre
    python scripts/decomposition.py lire                # avant, après, sans E1, sans E2

La série de D-352 a tourné E1 (le secteur public, D-346) et E2 (la CVAE et la C3S déduites
de l'IS, D-347) ensemble. Chaque passe ici refait la première année et le chemin annuel
d'une étude avec une correction coupée (`IMPOTS_SANS`, `impots.decomposition`), et écrit
ses rapports sous `reports/decomposition/<étude>/sans_<correction>/`, à part de ceux de
l'étude. Attal et Retailleau sont touchés par les deux ; Mélenchon par E1 seule, et sa
passe sans E1 doit redonner la série d'avant : c'est le contrôle de l'interrupteur.

Une passe à la fois, chacune dans son processus ; `src/` modifié ou D-354 absente du commit
sont refusés avant la première. La série reprend après les rapports déjà écrits.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from impots import decomposition, etude  # noqa: E402

OUT = ROOT / "reports" / "decomposition"
PREENREGISTREMENT = "D-354"
PASSES = (("presidentielle_melenchon", "E1"), ("presidentielle_attal", "E1"),
          ("presidentielle_attal", "E2"), ("presidentielle_retailleau", "E1"),
          ("presidentielle_retailleau", "E2"))


def dossier(nom: str, sans: str) -> Path:
    return OUT / nom / f"sans_{sans.lower()}"


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True)


def lancer(where: str) -> int:
    if _git("status", "--porcelain", "--", "src", "scripts").strip():
        print("src/ ou scripts/ modifiés : commiter d'abord.", file=sys.stderr)
        return 1
    if f"## {PREENREGISTREMENT} " not in _git("show", "HEAD:docs/DECISIONS.md"):
        print(f"{PREENREGISTREMENT} n'est pas dans le commit : préenregistrer d'abord.",
              file=sys.stderr)
        return 1
    for nom, sans in PASSES:
        study = etude.definition(nom)
        out = dossier(nom, sans)
        out.mkdir(parents=True, exist_ok=True)
        apart = dataclasses.replace(study, rapports=out)
        env = {**study._env(), decomposition.VARIABLE: sans}
        cli = ["-m", "impots.population.cli"]
        for name in study.noms:
            for report, command in (
                    (f"premiere_annee_{name}.json",
                     [*cli, "etude", "premiere", nom, name, "--ou", where,
                      "--sortie", str(out / f"premiere_annee_{name}.json")]),
                    (f"predictif_{name}.json", [*cli, *apart.annual_argv(name, where=where)])):
                if (out / report).exists():
                    print(f"== {nom} sans {sans} {report} : déjà là", flush=True)
                    continue
                print(f"== {nom} sans {sans} {report}", flush=True)
                code = subprocess.run([sys.executable, *command], cwd=ROOT, env=env).returncode
                if code:
                    print(f"{report} : la commande a rendu {code}.", file=sys.stderr)
                    return code
    return 0


def _ligne(entry: dict) -> tuple[float, float]:
    return entry["cost"], entry["debt"][0]["theta"]


def lire() -> int:
    for nom in dict.fromkeys(nom for nom, _ in PASSES):
        study = etude.definition(nom)
        avant = json.loads((study.rapports / etude.AVANT).read_text(encoding="utf-8"))
        for entry in study.load():
            then = avant["scenarios"][entry["name"]]
            rows = {"avant": (then["cout"], then["dette"]), "après": _ligne(entry)}
            for _, sans in (p for p in PASSES if p[0] == nom):
                rows[f"sans {sans}"] = _ligne(next(
                    e for e in study.load(dossier(nom, sans), plages=False) if e["name"] == entry["name"]))
            print(json.dumps({"etude": nom, "scenario": entry["name"], **{
                k: {"cout": c, "dette": d} for k, (c, d) in rows.items()}},
                ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("lancer").add_argument("--ou", required=True)
    actions.add_parser("lire")
    args = parser.parse_args()
    return lancer(args.ou) if args.action == "lancer" else lire()


if __name__ == "__main__":
    sys.exit(main())
