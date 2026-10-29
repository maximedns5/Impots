"""C1 sur quatre échantillons (D-285) : les rapports de l'étude que C1 chiffre, rejoués tels
quels sur la méthode de D-284.

    python scripts/c1_quatre.py lancer --ou "..."    # les explorations, puis les chemins

D-283 a mesuré le bruit de C1 d'un échantillon des taux marginaux à l'autre, et D-284 lui
fait lire quatre échantillons, mis en commun. Les rapports commités de l'étude où C1
chiffre ont été écrits sur un seul : les explorations de la décote et du barème, et leurs
chemins annuels (D-277).

RIEN N'EST CHOISI À LA MAIN. `menu` lit les rapports commités de l'étude, et retient ceux
dont la boîte porte une ligne de C1, dans l'ordre de l'étude (D-237). Chaque exploration
rejoue la requête commitée telle que son rapport l'a jouée, chaque chemin la commande que
`scripts/etude_annuelle.py` construit pour lui. Les rapports vont sous
`reports/c1_quatre/` ; ceux de l'étude ne bougent pas.

UNE PASSE À LA FOIS. Un chemin annuel occupe 6 Go (D-236) : les rejeux tournent l'un après
l'autre, chacun dans son processus. Un `src/` modifié et un rapport déjà là sont refusés
avant la première passe.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "etude"
REPORTS = ROOT / "reports"
OUT = REPORTS / "c1_quatre"

#: The study's menu (D-237), in its order.
STUDY = ("csg", "allegements", "decote", "ir")


class C1QuatreError(ValueError):
    """The replay would not be the study's report, as it was played."""


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _report(key: str, reports: Path) -> dict[str, Any]:
    return json.loads((reports / f"exploration_etude_{key}.json").read_text(encoding="utf-8"))


def _rows(report: dict[str, Any]) -> set[str]:
    return {part.split(" = ")[0] for search in report["searches"]
            for evaluation in search["evaluations"]
            for label, _ in evaluation.get("corners") or [] for part in label.split(", ")}


def menu(reports: Path = REPORTS) -> tuple[str, ...]:
    """The study's instruments whose box carries a row of C1, in the study's order."""
    sys.path.insert(0, str(ROOT / "src"))
    from impots.behavioural import channels

    return tuple(key for key in STUDY if _rows(_report(key, reports)) & set(channels.C1_KEYS))


def _validated(payload: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    from impots.api.schemas import ExplorationRequest

    return ExplorationRequest.model_validate(payload).model_dump(mode="json")


def exploration_argv(key: str, *, where: str, requests: Path = REQUESTS,
                     reports: Path = REPORTS, out: Path = OUT) -> list[str]:
    """`impots exploration` for `key`: the study's committed request, which must be the
    one its report played."""
    request = json.loads((requests / f"{key}.json").read_text(encoding="utf-8"))
    if _validated(request) != _validated(_report(key, reports)["request"]):
        raise C1QuatreError(f"{key} : la requête sous {requests} n'est pas celle que le "
                            f"rapport de l'étude a jouée ; le rejeu chiffrerait une autre "
                            f"exploration sous son nom.")
    return ["exploration", str(requests / f"{key}.json"), "--out-dir", str(out),
            "--ou", where]


def annual_argv(key: str, *, where: str, out: Path = OUT) -> list[str]:
    """`impots predictif` for `key`'s annual path: the command the study's annual launcher
    builds, into this replay's directory."""
    return _load("etude_annuelle").argv(key, where=where, out=out)


def replays(where: str) -> list[tuple[str, list[str]]]:
    """(name, command): the explorations first, then the annual paths."""
    keys = menu()
    return ([(f"exploration_etude_{key}.json", exploration_argv(key, where=where))
             for key in keys]
            + [(f"predictif_etude_annuel_{key}.json", annual_argv(key, where=where))
               for key in keys])


def launch(where: str) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from impots.predictif import recherche

    _, dirty = recherche.code_state(ROOT)
    if dirty:
        print("src/ a des modifications non commitées : les rapports nommeraient un commit "
              "dont ils n'ont pas chiffré le code. Commiter d'abord.", file=sys.stderr)
        return 1
    there = [p.name for p in OUT.glob("*.json")] if OUT.exists() else []
    if there:
        print(f"{OUT} porte déjà {there} : un rapport n'est pas écrasé en silence.",
              file=sys.stderr)
        return 1
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    for name, command in replays(where):
        print(f"== {name}", flush=True)
        code = subprocess.run([sys.executable, "-m", "impots.population.cli", *command],
                              cwd=ROOT, env=env).returncode
        if code:
            print(f"{name} : la commande a rendu {code}, les suivants ne tournent pas.",
                  file=sys.stderr)
            return code
    return 0


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="what", required=True)
    run = sub.add_parser("lancer")
    run.add_argument("--ou", required=True, help="where the passes run, which each report says")
    parsed = parser.parse_args(args)
    try:
        return launch(parsed.ou)
    except C1QuatreError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
