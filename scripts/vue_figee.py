"""La vue figée rechiffrée (D-278) : les explorations de l'étude dont la boîte lit les taux
marginaux, rejouées telles quelles sur la correction de D-276.

    python scripts/vue_figee.py lancer --ou "..."    # les explorations, l'une après l'autre

Jusqu'à D-276, la vue figée prenait la clé des taux marginaux de la vue vieillie. Dans
l'explorateur, qui chiffre la vue vieillie d'abord, la vue figée lisait donc les taux du
cadre vieilli. Seuls C1, la réponse du revenu imposable, et C7, l'offre de travail, lisent
ces taux : les explorations de l'étude dont la boîte n'en porte aucune ligne n'ont rien
que le défaut touche.

RIEN N'EST CHOISI À LA MAIN. `menu` lit les rapports commités de l'étude, et retient ceux
dont la boîte porte une ligne de C1 ou de C7, dans l'ordre de l'étude (D-237). `argv`
rejoue la requête commitée telle que le rapport l'a jouée, et la refuse si elle diffère.
Les rapports vont sous `reports/vue_figee/`, à côté de ceux de l'étude, qui ne bougent pas.
`tests/test_vue_figee.py` tient l'un et l'autre.

UNE PASSE À LA FOIS. Les explorations tournent l'une après l'autre, chacune dans son
processus, et un `src/` modifié est refusé avant la première passe, le rapport nommant le
code qui l'a chiffré.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUESTS = ROOT / "etude"
REPORTS = ROOT / "reports"
OUT = REPORTS / "vue_figee"

#: The study's menu (D-237), in its order.
STUDY = ("csg", "allegements", "decote", "ir")


class VueFigeeError(ValueError):
    """The replay would not be the study's exploration, as it was played."""


def _report(key: str, reports: Path) -> dict[str, Any]:
    return json.loads((reports / f"exploration_etude_{key}.json").read_text(encoding="utf-8"))


def _rows(report: dict[str, Any]) -> set[str]:
    return {part.split(" = ")[0] for search in report["searches"]
            for evaluation in search["evaluations"]
            for label, _ in evaluation.get("corners") or [] for part in label.split(", ")}


def menu(reports: Path = REPORTS) -> tuple[str, ...]:
    """The study's instruments whose box carries a row of C1 or C7, the two channels that
    read the marginal rates, in the study's order."""
    sys.path.insert(0, str(ROOT / "src"))
    from impots.behavioural import channels

    rates = set(channels.C1_KEYS) | set(channels.C7_KEYS)
    return tuple(key for key in STUDY if _rows(_report(key, reports)) & rates)


def _validated(payload: dict[str, Any]) -> dict[str, Any]:
    """A request as the explorer validates it: the fields the schema gained since a report
    was written take their defaults, so that the two are compared field for field."""
    sys.path.insert(0, str(ROOT / "src"))
    from impots.api.schemas import ExplorationRequest

    return ExplorationRequest.model_validate(payload).model_dump(mode="json")


def request(key: str, requests: Path = REQUESTS) -> dict[str, Any]:
    """The committed request of `key`, as the explorer validates it."""
    return _validated(json.loads((requests / f"{key}.json").read_text(encoding="utf-8")))


def argv(key: str, *, where: str, requests: Path = REQUESTS, reports: Path = REPORTS,
         out: Path = OUT) -> list[str]:
    """`impots exploration` for `key`: the study's committed request, which must be the
    one its report played."""
    if request(key, requests) != _validated(_report(key, reports)["request"]):
        raise VueFigeeError(f"{key} : la requête sous {requests} n'est pas celle que le "
                            f"rapport de l'étude a jouée ; le rejeu chiffrerait une autre "
                            f"exploration sous son nom.")
    return ["exploration", str(requests / f"{key}.json"), "--out-dir", str(out),
            "--ou", where]


def launch(where: str) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from impots.predictif import recherche

    _, dirty = recherche.code_state(ROOT)
    if dirty:
        print("src/ a des modifications non commitées : les rapports nommeraient un commit "
              "dont ils n'ont pas chiffré le code. Commiter d'abord.", file=sys.stderr)
        return 1
    there = [p.name for p in OUT.glob("exploration_*.json")] if OUT.exists() else []
    if there:
        print(f"{OUT} porte déjà {there} : un rapport n'est pas écrasé en silence.",
              file=sys.stderr)
        return 1
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    for key in menu():
        print(f"== {key}", flush=True)
        command = argv(key, where=where, out=OUT)
        code = subprocess.run([sys.executable, "-m", "impots.population.cli", *command],
                              cwd=ROOT, env=env).returncode
        if code:
            print(f"{key} : la commande a rendu {code}, les suivants ne tournent pas.",
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
    except VueFigeeError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
