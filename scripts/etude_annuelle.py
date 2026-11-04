"""L'étude sur le chemin annuel (D-275) : le paquet de l'étude le plus proche de la cible,
chiffré chaque année de 2026 à 2035 par `impots predictif`, dans le cadre de l'étude.

    python scripts/etude_annuelle.py ecrire               # les scénarios sous etude/annuel/
    python scripts/etude_annuelle.py lancer --ou "..."    # les quatre chemins, l'un après l'autre

L'étude de D-237 chiffre la première année et reporte les suivantes en part de PIB. Le
chemin annuel chiffre chaque année, la population vieillie l'année qu'elle chiffre, la loi
reconduite telle qu'openfisca la porte. Son rapport donne aussi, sur les mêmes passes, la
première année seule reportée comme le fait l'explorateur : l'écart entre les deux est celui
de la convention, sur un même code (D-275).

RIEN N'EST SAISI. `scenario` construit chaque scénario depuis le rapport commité de l'étude :
le paquet le plus proche de la cible, le même sous les deux persistances, et pour l'IR la
transformation appliquée au barème que le rapport a lu. `argv` reprend le cadre de la
requête commitée de l'étude, champ pour champ, et refuse ce que la commande ne saurait pas
porter. `tests/test_etude_annuelle.py` tient l'un et l'autre.

UNE PASSE À LA FOIS. Une année et une vue occupent 6 Go (D-236) : les quatre chemins
tournent l'un après l'autre, chacun dans son processus, et un `src/` modifié est refusé
avant la première passe, le rapport nommant le code qui l'a chiffré.
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
SCENARIOS = REQUESTS / "annuel"
OUT = REPORTS / "etude_annuel"

#: The study's menu (D-237), in its order.
MENU = ("csg", "allegements", "decote", "ir")
CREATED = "2026-10-27"


class EtudeAnnuelleError(ValueError):
    """The annual study would not be the study's bundles, in the study's frame."""


def name(key: str) -> str:
    return f"etude_annuel_{key}"


def closest(report: dict[str, Any]) -> dict[str, float]:
    """The bundle nearest the target, which must be the same under both persistences: two
    would be two studies."""
    knobs = [search["closest"]["knobs"] for search in report["searches"]]
    if any(k != knobs[0] for k in knobs):
        raise EtudeAnnuelleError(f"le paquet le plus proche n'est pas le même sous les deux "
                                 f"persistances : {knobs}. Le chemin annuel en chiffrerait "
                                 f"un seul, et l'autre se lirait reporté.")
    return dict(knobs[0])


def scenario(key: str, reports: Path = REPORTS) -> dict[str, Any]:
    """The scenario of `key`'s nearest bundle, built from the study's committed report."""
    sys.path.insert(0, str(ROOT / "src"))
    from impots.api.schemas import ExplorationRequest, ReformSpec
    from impots.predictif import recherche

    report = json.loads((reports / f"exploration_etude_{key}.json").read_text(
        encoding="utf-8"))
    request = ExplorationRequest.model_validate(report["request"])
    knobs = closest(report)
    laws = [t["law"] for t in report["hypotheses"].get("transformations", [])]
    if len(laws) > 1:
        raise EtudeAnnuelleError(f"{key} : {len(laws)} transformations, une au plus")
    reform = recherche.reform_of(request.base or ReformSpec(), knobs,
                                 laws[0] if laws else None)
    shown = ", ".join(f"{k} = {v:g}" for k, v in knobs.items())
    return {
        "name": name(key), "year": 2026, "created": CREATED,
        "source": (f"l'étude sur le chemin annuel (D-275) : le paquet de « {key} » le plus "
                   f"proche de la cible dans l'étude ({shown}), rapport commité "
                   f"{report['commit']}"),
        "note": "", "tags": ["etude_annuelle"],
        "reform": reform.model_dump(exclude_none=True, mode="json"),
    }


def argv(key: str, *, where: str, requests: Path = REQUESTS,
         scenarios: Path = SCENARIOS, out: Path = OUT) -> list[str]:
    """`impots predictif` for `key`, in the frame of the study's committed request."""
    request = json.loads((requests / f"{key}.json").read_text(encoding="utf-8"))
    theta = request["theta"]
    if theta.get("rows"):
        raise EtudeAnnuelleError(f"{key} : θ par ligne {theta['rows']}, que `--theta` ne "
                                 f"porte pas ; le chemin se lirait à un autre θ.")
    if request["spending"].get("rule") == "personnalise" or request["rate"]["kind"] != (
            "implicite_tenu") or any(request.get(k) for k in ("persistence", "base",
                                                               "firm_base")):
        raise EtudeAnnuelleError(f"{key} : un cadre que ce lanceur ne reprend pas champ pour "
                                 f"champ ; il serait chiffré dans un autre.")
    # The frame of the studies says the persistence its verdict reads (D-336, decision
    # 1): « lue », and only it. The command then draws every persistence side by side,
    # « lue » first: `--persistence lue` would draw it alone, and the page would lose
    # « éteint » and « tenu », which D-336 keeps as sensitivities beside the verdict.
    # Without the loop the command refuses a persistence; a looped frame has all three.
    persistance = request.get("persistance")
    if persistance is not None and (persistance != "lue" or not request.get("macro")):
        raise EtudeAnnuelleError(f"{key} : la persistance « {persistance} » ; le cadre ne "
                                 f"peut dire que « lue », et avec la boucle (D-336).")
    growth, rate, uprating = request["growth"], request["rate"], request["uprating"]
    return [
        "predictif", name(key), "--dir", str(scenarios), "--reference", "reconduit",
        "--spending", request["spending"]["rule"],
        "--growth-name", growth["name"], "--real", repr(growth["real"]),
        "--prices", repr(growth["prices"]),
        "--rate-name", rate["name"], "--rate-kind", rate["kind"],
        "--horizon", str(request["horizon"]), "--theta", repr(theta["common"]),
        "--wage", repr(uprating["wage"]), "--hypothesis-source", uprating["source"],
        *(["--behavioural"] if request.get("behavioural") else []),
        *(["--macro"] if request.get("macro") else []),
        "--out-dir", str(out), "--ou", where,
    ]


def write(scenarios: Path = SCENARIOS, reports: Path = REPORTS) -> list[Path]:
    scenarios.mkdir(parents=True, exist_ok=True)
    written = []
    for key in MENU:
        path = scenarios / f"{name(key)}.json"
        path.write_text(json.dumps(scenario(key, reports), indent=2, ensure_ascii=False)
                        + "\n", encoding="utf-8")
        written.append(path)
    return written


def launch(where: str) -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from impots.predictif import recherche

    _, dirty = recherche.code_state(ROOT)
    if dirty:
        print("src/ a des modifications non commitées : les rapports nommeraient un commit "
              "dont ils n'ont pas chiffré le code. Commiter d'abord.", file=sys.stderr)
        return 1
    there = [p.name for p in OUT.glob("predictif_*.json")] if OUT.exists() else []
    if there:
        print(f"{OUT} porte déjà {there} : un rapport n'est pas écrasé en silence.",
              file=sys.stderr)
        return 1
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    for key in MENU:
        print(f"== {key}", flush=True)
        command = argv(key, where=where, scenarios=SCENARIOS, out=OUT)
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
    sub.add_parser("ecrire")
    run = sub.add_parser("lancer")
    run.add_argument("--ou", required=True, help="where the passes run, which each report says")
    parsed = parser.parse_args(args)
    try:
        if parsed.what == "ecrire":
            for path in write():
                print(f"-> {path}")
            return 0
        return launch(parsed.ou)
    except EtudeAnnuelleError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
