"""L'étude du PLF 2027 (D-286, but 1) : les trois articles chiffrables, en trois réponses.

    python scripts/etude_plf2027.py ecrire               # le scénario de l'art. 15
    python scripts/etude_plf2027.py lancer --ou "..."    # les passes, l'une après l'autre

Pour chacun des articles 2, 3 et 15 : la première année, que chiffre l'appel du simulateur
(le coût, les gagnants et les perdants, la bande des comportements et l'éventail macro) ;
puis le chemin annuel de 2026 à 2035 (`impots predictif`), qui donne la dette en 2035 à θ
et aux coins de la boîte. Les rapports vont sous `reports/etude_plf2027/`, et
`scripts/write_etude_plf2027.py` en fait la page.

RIEN N'EST SAISI. Les articles 2 et 3 sont les scénarios enregistrés le 2026-10-02. Celui
de l'art. 15 est écrit ici depuis `reforms/plf2027_art_15.json`, la réforme que son
enregistrement a chiffrée, et borné à 2027 (D-288) : le texte rétablit la CEBGE pour cet
exercice seul. Le chemin annuel reprend le cadre de la requête de l'étude (D-237) champ pour
champ, par la commande que `scripts/etude_annuelle.py` construit pour elle.

UNE PASSE À LA FOIS. Un chemin annuel occupe 6 Go (D-236) : les passes tournent l'une après
l'autre, chacune dans son processus. Un `src/` modifié et un rapport déjà là sont refusés
avant la première passe.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "scenarios"
REFORMS = ROOT / "reforms"
OUT = ROOT / "reports" / "etude_plf2027"

#: The PLF 2027's priceable articles (`plf_coverage.ARTICLES_2027`), in the text's order.
ARTICLES = ("plf2027_art_2", "plf2027_art_3", "plf2027_art_15")
#: The study request whose frame the annual paths take, field for field (D-237).
FRAME = "ir"
CREATED = "2026-10-28"


class EtudePlf2027Error(ValueError):
    """The study would not price the articles as registered, in the study's frame."""


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def art15(reforms: Path = REFORMS) -> Any:
    """The art. 15 scenario: the firm reform its registration priced, for 2027 alone."""
    sys.path.insert(0, str(ROOT / "src"))
    from impots import scenarios
    from impots.api.schemas import ReformSpec
    from impots.entreprises.reforms import FirmReformSpec

    firm = FirmReformSpec.model_validate(json.loads(
        (reforms / "plf2027_art_15.json").read_text(encoding="utf-8")))
    return scenarios.Scenario(
        name="plf2027_art_15", reform=ReformSpec(), year=2027, created=CREATED,
        source=("PLF 2027 (AN, texte n° 3210), art. 15 — Mise à contribution des grandes "
                "entreprises. Volet chiffré : le troisième exercice de la CEBGE, à 15,7 % "
                "et 31,4 %, seuil de 1,5 Md€ (I de l'article), la réforme que "
                "`reforms/plf2027_art_15.json` porte et que son enregistrement a chiffrée."),
        note=("Ne porte PAS la contribution sur le résultat d'exploitation des transporteurs "
              "maritimes (II). Le texte rétablit la CEBGE pour l'exercice 2027 seul : la "
              "mesure est bornée à cette année (D-288)."),
        firm_reform=firm, annees=(2027,))


def first_year_payload(name: str, scenarios: Path = SCENARIOS) -> tuple[str, str, dict]:
    """(kind, endpoint, payload) of `name`'s first year: the firms' simulator for a firm
    reform alone, the households' otherwise, with behaviour and the loop asked."""
    sys.path.insert(0, str(ROOT / "src"))
    from impots import scenarios as scenarios_module

    scenario = scenarios_module.load(name, scenarios)
    firm = scenario.firm_reform is not None and not scenario.firm_reform.is_empty()
    if firm and not scenario.reform.is_empty():
        raise EtudePlf2027Error(f"{name} : une réforme des ménages et des entreprises, que "
                                f"la première année chiffrerait sur deux appels.")
    if firm:
        return "entreprises", "/entreprises/simulate", {
            "reform": scenario.firm_reform.model_dump(exclude_none=True, mode="json"),
            "year": scenario.year}
    return "menages", "/population/simulate", {
        "year": scenario.year,
        "reform": scenario.reform.model_dump(exclude_none=True, mode="json"),
        "behavioural": True, "macro": True}


def first_year(name: str, *, where: str, scenarios: Path = SCENARIOS) -> dict[str, Any]:
    """The first year's report: the simulator's reply, the code that priced it, where."""
    sys.path.insert(0, str(ROOT / "src"))
    from fastapi.testclient import TestClient

    from impots.api.main import app
    from impots.predictif import recherche

    kind, endpoint, payload = first_year_payload(name, scenarios)
    commit, dirty = recherche.code_state(ROOT)
    reply = TestClient(app).post(endpoint, json=payload)
    if reply.status_code != 200:
        raise EtudePlf2027Error(f"{name} : {endpoint} a rendu {reply.status_code} : "
                                f"{reply.text[:300]}")
    return {"scenario": name, "kind": kind, "endpoint": endpoint, "request": payload,
            "response": reply.json(), "computed": date.today().isoformat(),
            "commit": commit, "dirty": dirty, "where": where}


def annual_argv(name: str, *, where: str, out: Path = OUT) -> list[str]:
    """`impots predictif` for `name`: the study's annual command for the frame's request,
    with this scenario, this directory and this place."""
    command = _load("etude_annuelle").argv(FRAME, where=where, scenarios=SCENARIOS, out=out)
    if command[1] != _load("etude_annuelle").name(FRAME):
        raise EtudePlf2027Error(f"la commande de l'étude ne nomme pas son scénario en "
                                f"deuxième : {command[:3]}")
    return [command[0], name, *command[2:]]


def passes(where: str) -> list[tuple[str, list[str]]]:
    """(report, command): the first years, then the annual paths, in the text's order."""
    script = str(Path(__file__).resolve())
    return ([(f"premiere_annee_{name}.json", [script, "premiere", name, "--ou", where])
             for name in ARTICLES]
            + [(f"predictif_{name}.json",
                ["-m", "impots.population.cli", *annual_argv(name, where=where)])
               for name in ARTICLES])


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
    for report, command in passes(where):
        print(f"== {report}", flush=True)
        code = subprocess.run([sys.executable, *command], cwd=ROOT, env=env).returncode
        if code:
            print(f"{report} : la commande a rendu {code}, les suivants ne tournent pas.",
                  file=sys.stderr)
            return code
    return 0


def main(args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="what", required=True)
    sub.add_parser("ecrire")
    run = sub.add_parser("lancer")
    run.add_argument("--ou", required=True, help="where the passes run, which each report says")
    one = sub.add_parser("premiere")
    one.add_argument("scenario", choices=ARTICLES)
    one.add_argument("--ou", required=True)
    parsed = parser.parse_args(args)
    try:
        if parsed.what == "ecrire":
            print(f"-> {art15().save(SCENARIOS)}")
            return 0
        if parsed.what == "premiere":
            report = first_year(parsed.scenario, where=parsed.ou)
            OUT.mkdir(parents=True, exist_ok=True)
            path = OUT / f"premiere_annee_{parsed.scenario}.json"
            path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8")
            print(f"  -> {path}")
            return 0
        return launch(parsed.ou)
    except EtudePlf2027Error as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
