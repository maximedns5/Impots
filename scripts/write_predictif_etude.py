#!/usr/bin/env python3
"""Render docs/PREDICTIF_ETUDE.md — l'étude de la phase 10 (PHASE10_SPEC §5, D-237, D-238).

« Quelles baisses d'impôt font baisser la dette en 2035, et pour quels θ ? »

PRÉENREGISTRÉE. Les requêtes sont sous `etude/`, une par instrument du menu, commitées
avant toute passe avec le pronostic de D-237. Chacune est jouée par `impots exploration`,
qui écrit `reports/exploration_etude_<instrument>.json` en nommant le commit qui l'a
chiffrée et où ses passes ont tourné. Ce script refuse un rapport qui n'a pas joué la
requête commitée, un instrument sans rapport, des rapports de deux commits, et un rapport
qui ne dit pas où il a tourné.

LA COURBE DE 2026 est rejouée à part, préenregistrée elle aussi (D-241, D-242) : une
requête par bouton de la courbe sous `etude/courbe/`, qui tient le cadre de l'étude champ
pour champ, jouée en `reports/exploration_courbe_<bouton>.json`. Les mêmes refus valent
pour elle, et un de plus : une requête hors de son menu.

LE MENU ÉLARGI DE LA PHASE 11 est préenregistré à part (D-250, D-251) : l'IS et le PFU
sous `etude/phase11/`, joués en `reports/exploration_phase11_<instrument>.json`, avec les
refus de la courbe. Les quatre requêtes de l'étude y sont rejouées telles quelles, pour
contrôle, en `reports/etude_phase11/controles/`. Un contrôle qui ne rejoue pas la requête
de l'étude est refusé ; un contrôle qui ne redonne pas sa référence ne l'est pas : la page
le dit, avec son écart, parce que c'est un résultat.

AUCUN CHIFFRE N'EST SAISI DANS LA PAGE : tout vient des rapports. `render(études)` est ce
que rejoue `tests/test_predictif_etude.py`, sans `data/` : la page commitée est le rendu
des fichiers commités (la garde de D-228).

    python scripts/write_predictif_etude.py
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "PREDICTIF_ETUDE.md"
REQUESTS = ROOT / "etude"
REPORTS = ROOT / "reports"
#: The first round, on the preregistration's own commit, before the reports carried what
#: the chain lacks (D-238). The second round must give it back figure for figure.
FIRST_ROUND = "etude_premier_tour"
#: The second round, whose C2 read 15 % of the earners (D-252) and lent each its household's
#: cost change (D-254). The third is the second round's commit with C2's fixes alone: it
#: must give the second back figure for figure.
SECOND_ROUND = "etude_second_tour"
#: What a round computes, as against what it reports about it.
FIGURES = ("knobs", "cost_aged_eur", "cost_frozen_eur", "delta_aged", "delta_frozen",
           "corners", "corner_low", "corner_high", "meets_target")
#: Requests replayed after the result, outside the preregistration (D-239): each must be
#: an instrument's preregistered request, with only these fields changed.
COMPLEMENTS = "complements"
COMPLEMENT_FREE = ("name", "titre", "question")
#: The complements' first round, whose C2 read 15 % of the earners (D-252) and lent each its
#: household's cost change (D-254). The rerun corrects C2, which enters no revenue and no
#: debt: it must give the first round back figure for figure (D-255).
COMPLEMENTS_FIRST_ROUND = "complements_premier_tour"
#: The 2026 curve, replayed in the study and preregistered apart (D-241): each request
#: holds the frame of the study's allègement request, only these fields changed.
COURBE = "courbe"
COURBE_FREE = ("name", "titre", "question", "bounds")
#: The curve's first round, on its preregistration's commit, with a C2 that read 15 % of the
#: earners (D-252) and lent each its household's cost change (D-254). The rerun corrects C2,
#: which enters no revenue and no debt: it must give the first round back figure for figure.
COURBE_FIRST_ROUND = "courbe_premier_tour"
#: The wider menu of Phase 11, preregistered apart (D-250): each request holds the frame
#: of the study's IR request, only these fields changed; the study's own four requests
#: are replayed as they are, as controls, under this directory of `reports/`.
PHASE11 = "phase11"
PHASE11_FREE = ("name", "titre", "question", "bounds")
CONTROLS = Path("etude_phase11") / "controles"
#: How near a control must give back its reference to be said to: a ten-thousandth of a
#: point of GDP on every Δb and every corner, a euro on every cost (D-250).
CONTROL_SHARE = 1e-6
CONTROL_EUR = 1.0


class EtudeError(ValueError):
    """The study's files do not say what the page would say."""


def _pct(x: float) -> str:
    return f"{x * 100:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " %"


def _smic(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " SMIC"


def _factor(x: float) -> str:
    return "× " + f"{x:.3f}".rstrip("0").rstrip(".").replace(".", ",")


@dataclass(frozen=True)
class Instrument:
    key: str
    label: str
    knob: str
    show: Callable[[float], str]


#: The menu of §5, in its order. The IS is not on it: the chain prices the population's
#: reforms, and the IS is not one (D-228).
MENU: tuple[Instrument, ...] = (
    Instrument("csg", "La CSG déductible sur les revenus d'activité",
               "csg_activite_deductible", _pct),
    Instrument("allegements", "Le plafond de la réduction générale des cotisations "
               "employeurs", "allegement_general_plafond", _smic),
    Instrument("decote", "Le taux de la décote de l'IR", "decote_taux", _pct),
    Instrument("ir", "Les taux du barème de l'IR, mis à l'échelle", "ir_bareme_echelle",
               _factor),
)

#: The knobs of the 2026 curve (D-240). The population carries no firm size, so every
#: employee is in a firm under 50, whose `t_delta` is everyone's there (D-241).
COURBE_MENU: tuple[Instrument, ...] = (
    Instrument("t_min", "Le plancher t_min de la réduction générale de 2026",
               "allegement_general_t_min", _pct),
    Instrument("t_delta", "Le t_delta de la réduction générale de 2026",
               "allegement_general_t_delta_moins_de_50", _pct),
)

#: The two instruments Phase 11 adds to the menu (D-250). The CVAE is not one: the law
#: abolishes it in 2030, which the first year's carry would not see.
PHASE11_MENU: tuple[Instrument, ...] = (
    Instrument("is", "Le taux normal de l'IS", "is_taux_normal", _pct),
    Instrument("pfu", "Le taux du PFU, part impôt sur le revenu", "pfu_taux", _pct),
)


def _fr(x: float, decimals: int = 2, *, sign: bool = True) -> str:
    text = f"{x:+.{decimals}f}" if sign else f"{x:.{decimals}f}"
    return text.replace("-", "−").replace(".", ",")


def _pt(share: float) -> str:
    """A share of GDP, in points."""
    return _fr(share * 100) + " pt"


def _md(eur: float) -> str:
    return _fr(eur / 1e9, sign=False) + " Md€"


# --------------------------------------------------------------------------- #
# the files
# --------------------------------------------------------------------------- #
def same_figures(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Whether two rounds of one request computed the same: every bundle, every corner,
    every candidate, under each persistence."""
    def figures(report: dict[str, Any]) -> list[Any]:
        return [(s["persistence"], [{k: e[k] for k in FIGURES} for e in s["evaluations"]],
                 s["candidates"]) for s in report["searches"]]
    return first["request"] == second["request"] and figures(first) == figures(second)


def load(requests: Path = REQUESTS, reports: Path = REPORTS) -> list[dict[str, Any]]:
    """Each instrument's committed request and the report that played it, checked; and,
    when a first round is kept, the same figures in it."""
    sys.path.insert(0, str(ROOT / "src"))
    from impots.api.schemas import ExplorationReport, ExplorationRequest

    out = []
    for instrument in MENU:
        request_path = requests / f"{instrument.key}.json"
        report_path = reports / f"exploration_etude_{instrument.key}.json"
        if not request_path.exists():
            raise EtudeError(f"instrument « {instrument.key} » sans requête sous etude/ : "
                             f"le menu préenregistré n'est pas entier.")
        if not report_path.exists():
            raise EtudeError(f"instrument « {instrument.key} » sans rapport : l'étude se "
                             f"lirait sans lui, comme s'il n'était pas au menu.")
        request = ExplorationRequest.model_validate_json(
            request_path.read_text(encoding="utf-8"))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        ExplorationReport.model_validate(report)
        if report["request"] != request.model_dump(mode="json", exclude_none=True):
            raise EtudeError(
                f"{report_path.name} n'a pas joué la requête commitée {request_path.name} : "
                f"une requête retouchée après coup n'est plus préenregistrée.")
        if [b.knob for b in request.bounds] != [instrument.knob]:
            raise EtudeError(f"etude/{instrument.key}.json parcourt "
                             f"{[b.knob for b in request.bounds]}, pas {instrument.knob}.")
        if not (report.get("where") or "").strip():
            raise EtudeError(f"{report_path.name} ne dit pas où ses passes ont tourné "
                             f"(PHASE10_SPEC §5).")
        out.append({"instrument": instrument, "report": report})
    commits = sorted({e["report"]["commit"] for e in out})
    if len(commits) != 1:
        raise EtudeError(f"rapports de {len(commits)} commits {commits} : l'étude se "
                         f"chiffre sur un code, celui du préenregistrement.")
    first_round = reports / FIRST_ROUND
    if first_round.exists():
        for entry in out:
            path = first_round / f"exploration_etude_{entry['instrument'].key}.json"
            if not path.exists():
                raise EtudeError(f"premier tour sans {path.name} : la comparaison des "
                                 f"deux tours ne porterait pas sur tout le menu.")
            first = json.loads(path.read_text(encoding="utf-8"))
            ExplorationReport.model_validate(first)
            if not same_figures(first, entry["report"]):
                raise EtudeError(
                    f"le second tour de « {entry['instrument'].key} » ne redonne pas le "
                    f"premier : un chiffre a bougé entre les deux commits, et l'écart au "
                    f"préenregistrement n'est plus un champ ajouté.")
            entry["first_commit"] = first["commit"]
        if len({e["first_commit"] for e in out}) != 1:
            raise EtudeError("premier tour de plusieurs commits.")
    second_round = reports / SECOND_ROUND
    if second_round.exists():
        for entry in out:
            path = second_round / f"exploration_etude_{entry['instrument'].key}.json"
            if not path.exists():
                raise EtudeError(f"second tour sans {path.name} : la comparaison des deux "
                                 f"derniers tours ne porterait pas sur tout le menu.")
            second = json.loads(path.read_text(encoding="utf-8"))
            ExplorationReport.model_validate(second)
            if not same_figures(second, entry["report"]):
                raise EtudeError(
                    f"le troisième tour de « {entry['instrument'].key} » ne redonne pas le "
                    f"second : un chiffre a bougé entre les deux commits, et le troisième "
                    f"tour n'est plus la seule correction de C2 (D-252, D-254).")
            entry["second_commit"] = second["commit"]
        if len({e["second_commit"] for e in out}) != 1:
            raise EtudeError("second tour de plusieurs commits.")
    return out


def load_complements(etudes: list[dict[str, Any]], requests: Path = REQUESTS,
                     reports: Path = REPORTS) -> list[dict[str, Any]]:
    """Each complement under `etude/complements/`, checked to be a like-for-like replay
    of its instrument's preregistered request: same grid and hypotheses, same costs."""
    from impots.api.schemas import ExplorationReport, ExplorationRequest

    directory = requests / COMPLEMENTS
    if not directory.exists():
        return []
    by_knob = {e["instrument"].knob: e for e in etudes}
    out = []
    for path in sorted(directory.glob("*.json")):
        request = ExplorationRequest.model_validate_json(path.read_text(encoding="utf-8"))
        dump = request.model_dump(mode="json", exclude_none=True)
        knobs = [b.knob for b in request.bounds]
        entry = by_knob.get(knobs[0]) if len(knobs) == 1 else None
        if entry is None:
            raise EtudeError(f"complément {path.name} sur {knobs} : aucun instrument de "
                             f"l'étude ne parcourt ce bouton.")

        def held(payload: dict[str, Any]) -> dict[str, Any]:
            return {k: v for k, v in payload.items() if k not in COMPLEMENT_FREE}

        if held(dump) != held(entry["report"]["request"]):
            raise EtudeError(
                f"complément {path.name} : il ne rejoue pas la requête préenregistrée de "
                f"« {entry['instrument'].key} ». Seuls {list(COMPLEMENT_FREE)} peuvent "
                f"différer, sans quoi l'écart ne dirait plus ce qui a changé.")
        report_path = reports / f"exploration_{request.name}.json"
        if not report_path.exists():
            raise EtudeError(f"complément sans rapport : {report_path.name}.")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        ExplorationReport.model_validate(report)
        if report["request"] != dump:
            raise EtudeError(f"{report_path.name} n'a pas joué sa requête, {path.name}.")
        if not (report.get("where") or "").strip():
            raise EtudeError(f"{report_path.name} ne dit pas où ses passes ont tourné.")

        def costs(r: dict[str, Any]) -> list[Any]:
            return [[(e["knobs"], e["cost_aged_eur"], e["cost_frozen_eur"])
                     for e in s["evaluations"]] for s in r["searches"]]

        if costs(report) != costs(entry["report"]):
            raise EtudeError(
                f"{report_path.name} : les coûts diffèrent de ceux de l'étude. Le "
                f"complément ne change que le classement du choc macro ; un coût qui "
                f"bouge dit qu'autre chose a bougé.")
        complement = {"instrument": entry["instrument"], "report": report,
                      "study": entry["report"]}
        first_round = reports / COMPLEMENTS_FIRST_ROUND
        if first_round.exists():
            first_path = first_round / report_path.name
            if not first_path.exists():
                raise EtudeError(f"premier tour des compléments sans {first_path.name} : "
                                 f"la comparaison des deux tours ne porterait pas sur "
                                 f"tous les compléments.")
            first = json.loads(first_path.read_text(encoding="utf-8"))
            ExplorationReport.model_validate(first)
            if not same_figures(first, report):
                raise EtudeError(
                    f"le second tour de {report_path.name} ne redonne pas le premier : un "
                    f"chiffre a bougé entre les deux commits, et le second tour n'est plus "
                    f"la seule correction de C2 (D-252, D-254).")
            complement["first_commit"] = first["commit"]
        out.append(complement)
    return out


def load_courbe(etudes: list[dict[str, Any]], requests: Path = REQUESTS,
                reports: Path = REPORTS) -> list[dict[str, Any]]:
    """Each knob of the curve's committed request under `etude/courbe/` and the report that
    played it, checked: the study's frame held, the knob of its instrument, one commit."""
    from impots.api.schemas import ExplorationReport, ExplorationRequest

    directory = requests / COURBE
    if not directory.exists():
        return []
    known = {f"{instrument.key}.json" for instrument in COURBE_MENU}
    strays = sorted(p.name for p in directory.glob("*.json") if p.name not in known)
    if strays:
        raise EtudeError(f"etude/{COURBE}/ porte {strays}, hors du menu de la courbe : une "
                         f"requête que la page ne rendrait pas se lirait comme non jouée.")
    frame = next(e for e in etudes if e["instrument"].key == "allegements")["report"]

    def held(payload: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in payload.items() if k not in COURBE_FREE}

    out = []
    for instrument in COURBE_MENU:
        request_path = directory / f"{instrument.key}.json"
        report_path = reports / f"exploration_{COURBE}_{instrument.key}.json"
        if not request_path.exists():
            raise EtudeError(f"bouton « {instrument.key} » de la courbe sans requête sous "
                             f"etude/{COURBE}/ : le menu préenregistré n'est pas entier.")
        if not report_path.exists():
            raise EtudeError(f"bouton « {instrument.key} » de la courbe sans rapport : "
                             f"{report_path.name}.")
        request = ExplorationRequest.model_validate_json(
            request_path.read_text(encoding="utf-8"))
        dump = request.model_dump(mode="json", exclude_none=True)
        if held(dump) != held(frame["request"]):
            raise EtudeError(
                f"etude/{COURBE}/{request_path.name} ne tient pas le cadre de l'étude : seuls "
                f"{list(COURBE_FREE)} peuvent différer de la requête des allègements, sans "
                f"quoi la courbe ne se lirait plus à côté de l'étude.")
        if [b.knob for b in request.bounds] != [instrument.knob]:
            raise EtudeError(f"etude/{COURBE}/{request_path.name} parcourt "
                             f"{[b.knob for b in request.bounds]}, pas {instrument.knob}.")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        ExplorationReport.model_validate(report)
        if report["request"] != dump:
            raise EtudeError(f"{report_path.name} n'a pas joué sa requête, "
                             f"etude/{COURBE}/{request_path.name}.")
        if not (report.get("where") or "").strip():
            raise EtudeError(f"{report_path.name} ne dit pas où ses passes ont tourné.")
        out.append({"instrument": instrument, "report": report})
    commits = sorted({e["report"]["commit"] for e in out})
    if len(commits) != 1:
        raise EtudeError(f"rapports de la courbe de {len(commits)} commits {commits} : elle "
                         f"se chiffre sur un code, celui de son préenregistrement.")
    first_round = reports / COURBE_FIRST_ROUND
    if first_round.exists():
        for entry in out:
            path = first_round / f"exploration_{COURBE}_{entry['instrument'].key}.json"
            if not path.exists():
                raise EtudeError(f"premier tour de la courbe sans {path.name} : la "
                                 f"comparaison des deux tours ne porterait pas sur tout "
                                 f"son menu.")
            first = json.loads(path.read_text(encoding="utf-8"))
            ExplorationReport.model_validate(first)
            if not same_figures(first, entry["report"]):
                raise EtudeError(
                    f"le second tour de la courbe « {entry['instrument'].key} » ne redonne "
                    f"pas le premier : un chiffre a bougé entre les deux commits, et le "
                    f"second tour n'est plus la seule correction de C2 (D-252, D-254).")
            entry["first_commit"] = first["commit"]
        if len({e["first_commit"] for e in out}) != 1:
            raise EtudeError("premier tour de la courbe de plusieurs commits.")
    return out


def control_gaps(report: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    """How far a control is from its reference: the largest gap on a Δb or a corner, in
    share of GDP, and on a cost, in euros, bundle by bundle and persistence by persistence;
    and whether every bundle meets the target, or not, as it did."""
    share, eur, same = 0.0, 0.0, True
    for search, before in zip(report["searches"], reference["searches"], strict=True):
        if search["persistence"] != before["persistence"]:
            raise EtudeError("un contrôle et sa référence n'ont pas les mêmes persistances")
        was = {json.dumps(e["knobs"], sort_keys=True): e for e in before["evaluations"]}
        for e in search["evaluations"]:
            b = was.get(json.dumps(e["knobs"], sort_keys=True))
            if b is None:
                raise EtudeError(f"un contrôle chiffre {e['knobs']}, que sa référence n'a "
                                 f"pas : ce n'est pas la même grille.")
            corners = dict(b["corners"])
            share = max([share, *(abs(e[k] - b[k]) for k in
                                  ("delta_aged", "delta_frozen", "corner_low",
                                   "corner_high")),
                         *(abs(v - corners[label]) for label, v in e["corners"])])
            eur = max(eur, abs(e["cost_aged_eur"] - b["cost_aged_eur"]),
                      abs(e["cost_frozen_eur"] - b["cost_frozen_eur"]))
            same = same and e["meets_target"] == b["meets_target"]
    return {"share": share, "eur": eur, "same_verdicts": same,
            "given_back": same and share <= CONTROL_SHARE and eur <= CONTROL_EUR}


def load_phase11(etudes: list[dict[str, Any]], complements: list[dict[str, Any]],
                 requests: Path = REQUESTS, reports: Path = REPORTS) -> dict[str, Any] | None:
    """The wider menu of Phase 11 under `etude/phase11/` and the reports that played it,
    checked like the curve; and the study's four requests replayed as controls, each with
    its gap to its reference — the study's report, or the complement that replayed it
    after its instrument was reclassified (D-239). One commit for all."""
    from impots.api.schemas import ExplorationReport, ExplorationRequest

    directory = requests / PHASE11
    if not directory.exists():
        return None
    known = {f"{instrument.key}.json" for instrument in PHASE11_MENU}
    strays = sorted(p.name for p in directory.glob("*.json") if p.name not in known)
    if strays:
        raise EtudeError(f"etude/{PHASE11}/ porte {strays}, hors du menu de la phase 11 : "
                         f"une requête que la page ne rendrait pas se lirait comme non "
                         f"jouée.")
    frame = next(e for e in etudes if e["instrument"].key == "ir")["report"]["request"]

    def held(payload: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in payload.items() if k not in PHASE11_FREE}

    def played(path: Path, dump: dict[str, Any], what: str) -> dict[str, Any]:
        report = json.loads(path.read_text(encoding="utf-8"))
        ExplorationReport.model_validate(report)
        if report["request"] != dump:
            raise EtudeError(f"{path.name} n'a pas joué sa requête, {what}.")
        if not (report.get("where") or "").strip():
            raise EtudeError(f"{path.name} ne dit pas où ses passes ont tourné.")
        return report

    entries = []
    for instrument in PHASE11_MENU:
        request_path = directory / f"{instrument.key}.json"
        report_path = reports / f"exploration_{PHASE11}_{instrument.key}.json"
        if not request_path.exists():
            raise EtudeError(f"instrument « {instrument.key} » de la phase 11 sans requête "
                             f"sous etude/{PHASE11}/ : le menu préenregistré n'est pas "
                             f"entier.")
        if not report_path.exists():
            raise EtudeError(f"instrument « {instrument.key} » de la phase 11 sans "
                             f"rapport : {report_path.name}.")
        request = ExplorationRequest.model_validate_json(
            request_path.read_text(encoding="utf-8"))
        dump = request.model_dump(mode="json", exclude_none=True)
        if held(dump) != held(frame):
            raise EtudeError(
                f"etude/{PHASE11}/{request_path.name} ne tient pas le cadre de l'étude : "
                f"seuls {list(PHASE11_FREE)} peuvent différer de sa requête de l'IR, sans "
                f"quoi le menu élargi ne se lirait plus à côté de l'étude.")
        if [b.knob for b in request.bounds] != [instrument.knob]:
            raise EtudeError(f"etude/{PHASE11}/{request_path.name} parcourt "
                             f"{[b.knob for b in request.bounds]}, pas {instrument.knob}.")
        entries.append({"instrument": instrument, "report": played(
            report_path, dump, f"etude/{PHASE11}/{request_path.name}")})
    reclassified = {c["instrument"].key: c["report"] for c in complements}
    controls = []
    for entry in etudes:
        key = entry["instrument"].key
        path = reports / CONTROLS / f"exploration_etude_{key}.json"
        if not path.exists():
            raise EtudeError(f"contrôle « {key} » sans rapport : {CONTROLS / path.name}. "
                             f"Sans lui, rien ne dit que le code du menu élargi chiffre "
                             f"encore l'étude comme elle a été chiffrée.")
        report = played(path, entry["report"]["request"], f"etude/{key}.json")
        reference = reclassified.get(key, entry["report"])
        controls.append({"instrument": entry["instrument"], "report": report,
                         "against": "D-239" if key in reclassified else "D-238",
                         "gaps": control_gaps(report, reference)})
    commits = sorted({e["report"]["commit"] for e in entries + controls})
    if len(commits) != 1:
        raise EtudeError(f"rapports de la phase 11 de {len(commits)} commits {commits} : le "
                         f"menu élargi et ses contrôles se chiffrent sur un code, celui de "
                         f"leur préenregistrement.")
    return {"entries": entries, "controls": controls}


def study(requests: Path = REQUESTS,
          reports: Path = REPORTS) -> tuple[list, list, list, dict[str, Any] | None]:
    """The study, its complements, the curve replayed and the wider menu of Phase 11,
    all checked: what the page renders."""
    etudes = load(requests, reports)
    complements = load_complements(etudes, requests, reports)
    return (etudes, complements, load_courbe(etudes, requests, reports),
            load_phase11(etudes, complements, requests, reports))


# --------------------------------------------------------------------------- #
# the reading
# --------------------------------------------------------------------------- #
def _settings(label: str) -> set[tuple[str, str]]:
    return {tuple(part.split(" = ")) for part in label.split(", ") if " = " in part}


def falling(evaluation: dict[str, Any], target: float) -> tuple[int, set[tuple[str, str]]]:
    """How many corners meet the target, and the θ settings all of them share."""
    labels = [label for label, value in evaluation["corners"] if value <= target]
    if not labels:
        return 0, set()
    shared = _settings(labels[0])
    for label in labels[1:]:
        shared &= _settings(label)
    return len(labels), shared


def theta_text(common: float) -> str:
    return "½" if common == 0.5 else _fr(common, sign=False)


#: The chain's key when the whole loop is absent; « rétroaction, instruments non
#: couverts » only names the instruments it could not read, the loop running for the rest.
NO_LOOP = "rétroaction"


def loop_absent(search: dict[str, Any]) -> bool:
    """Whether the chain says the GDP → receipts loop is absent for the nearest bundle."""
    return NO_LOOP in ((search.get("indices") or {}).get("absent") or {})


def compact(text: str) -> str:
    """« af : r ; ppa : r » as « af, ppa : r »: the chain repeats one reason per instrument.
    Left as it is when its items are not « name : reason »."""
    items = [item.partition(" : ") for item in text.split(" ; ")]
    if not all(sep and name and " " not in name for name, sep, _ in items):
        return text
    grouped: dict[str, list[str]] = {}
    for name, _, why in items:
        grouped.setdefault(why, []).append(name)
    return " ; ".join(f"{', '.join(names)} : {why}" for why, names in grouped.items())


LOOP_ABSENT = (" Attention : la boucle PIB → recettes est absente pour ce paquet, non "
               "nulle ; voir ce qui manque à la chaîne.")


def verdict(search: dict[str, Any], instrument: Instrument, target: float,
            theta: str = "½") -> str:
    """One sentence: does a cut lower the debt at θ, robustly, or not, and how close; and
    whether the loop was there to say so."""
    return (_verdict(search, instrument, target, theta) + which_theta(search, target)
            + (LOOP_ABSENT if loop_absent(search) else ""))


def which_theta(search: dict[str, Any], target: float) -> str:
    """For which θ the debt falls: the corners that meet the target, bundle by bundle,
    and the θ settings every one of them shares."""
    found = [falling(e, target) for e in search["evaluations"]]
    if not any(n for n, _ in found):
        return " Elle ne baisse à aucun coin de la boîte θ."
    shared = set.intersection(*(s for n, s in found if n))
    common = (" : ceux où " + ", ".join(f"{k} = {v}" for k, v in sorted(shared))
              if shared else "")
    counts = sorted({n for n, _ in found if n})
    total = len(search["evaluations"][0]["corners"])
    where = ("à chaque paquet" if all(n for n, _ in found)
             else f"à {sum(1 for n, _ in found if n)} paquets sur {len(found)}")
    many = (f"{counts[0]} coins sur {total}" if len(counts) == 1
            else f"de {counts[0]} à {counts[-1]} coins sur {total}")
    return f" Elle baisse à {many}, {where}{common}."


def _verdict(search: dict[str, Any], instrument: Instrument, target: float,
             theta: str) -> str:
    plans = [c for c in search["candidates"] if c["meets_target"]]
    frozen = [c for c in search["candidates"] if c["frozen_only"]]
    if plans:
        robust = [c for c in plans if c["robust"]]
        names = ", ".join(instrument.show(c["knobs"][instrument.knob]) for c in plans)
        return (f"oui à θ = {theta} : {names} ; "
                + (f"{len(robust)} robuste(s) aux coins de la boîte θ."
                   if robust else "aucune n'est robuste, chacune dépend de θ."))
    nearest = search["closest"]
    text = (f"non à θ = {theta} : le paquet le plus proche, "
            f"{instrument.show(nearest['knobs'][instrument.knob])}, laisse "
            f"Δb = {_pt(nearest['delta_aged'])}")
    if frozen:
        text += (f" ; {len(frozen)} paquet(s) ne tiennent la cible qu'en vue figée, ce qui "
                 f"n'est pas un plan (D-155)")
    return text + "."


def _corners(evaluation: dict[str, Any], target: float) -> str:
    n, shared = falling(evaluation, target)
    total = len(evaluation["corners"])
    if not n:
        return f"aucun des {total}"
    common = ", ".join(f"{k} = {v}" for k, v in sorted(shared)) or "aucun réglage commun"
    return f"{n} sur {total} ({common})"


def _search_table(search: dict[str, Any], instrument: Instrument, target: float, *,
                  first_year: int, target_year: int, theta: str) -> list[str]:
    lines = [f"| Paquet | Coût {first_year}, vieillie | Coût {first_year}, figée "
             f"| Δb {target_year} à θ = {theta}, vieillie | Δb {target_year}, figée "
             f"| Boîte θ, vieillie | Coins où la dette baisse |",
             "|---|---|---|---|---|---|---|"]
    for e in search["evaluations"]:
        lines.append(
            f"| {instrument.show(e['knobs'][instrument.knob])} | {_md(e['cost_aged_eur'])} "
            f"| {_md(e['cost_frozen_eur'])} | {_pt(e['delta_aged'])} "
            f"| {_pt(e['delta_frozen'])} "
            f"| [{_pt(e['corner_low'])} ; {_pt(e['corner_high'])}] "
            f"| {_corners(e, target)} |")
    return lines


def _number(x: float) -> str:
    """Two decimals below a hundred; above, whole and in thousands, as French writes it."""
    if abs(x) < 100:
        return _fr(x)
    return f"{x:+,.0f}".replace(",", " ").replace("-", "−")


def _key(key: str) -> str:
    """A Mésange horizon (« 1 », « 2 », « 3 ») as the years it is; any other key as it is."""
    return {"1": "à 1 an", "2": "à 2 ans", "3": "à 3 ans"}.get(key, key)


#: The two firm indices of the wider menu (D-250), a few hundredths at most: shown to the
#: thousandth, where two decimals would print an IS cut's GDP gap as « +0,02 ».
FINE = ("pib_is", "creations_societes")


def _value(row: dict[str, Any], key: str) -> str:
    value = row["values"][key]
    share = row["unit"].startswith("pts d")

    def shown(x: float) -> str:
        return _fr(x, 3) if row["key"] in FINE else _number(x)

    text = _fr(value * 100, 3) + " pt" if share else shown(value)
    box = (row.get("box") or {}).get(key)
    if box is not None and box[0] != box[1]:
        text += f" [{shown(box[0])} ; {shown(box[1])}]"
    return text


def _indices(entry: dict[str, Any], target_year: int) -> list[str]:
    instrument, report = entry["instrument"], entry["report"]
    searches = report["searches"]
    lines = []
    first = searches[0]["indices"]
    lines.append(f"Paquet le plus proche de la cible : "
                 f"**{instrument.show(first['knobs'][instrument.knob])}**"
                 + ("" if all(s["indices"]["knobs"] == first["knobs"] for s in searches)
                    else " (le plus proche diffère selon la persistance : voir chaque "
                         "ligne de la chaîne)") + ".")
    lines += ["", "| Pour | Indice | Unité | Valeur à θ [boîte θ] |", "|---|---|---|---|"]
    for row in first["rows"]:
        if row["stage"] == "chaîne":
            continue
        if not row["available"]:
            lines.append(f"| {row['pour']} | {row['label']} | {row['unit']} "
                         f"| absent : {row['reason']} |")
            continue
        shown = " ; ".join(f"{_key(k)} : {_value(row, k)}" for k in row["values"])
        lines.append(f"| {row['pour']} | {row['label']} | {row['unit']} | {shown} |")
    for search in searches:
        for row in search["indices"]["rows"]:
            if row["stage"] == "chaîne" and row["available"]:
                key = str(target_year)
                lines.append(f"| {row['pour']} | {row['label']}, "
                             f"{search['persistence_label'].lower()} | {row['unit']} "
                             f"| {key} : {_value(row, key)} |")
    return lines


def _complement_section(complements: list[dict[str, Any]], target: float,
                        first_year: int, target_year: int, theta: str) -> list[str]:
    out = ["", "## Complément, hors préenregistrement", "",
           "Joué après le résultat de l'étude, et hors de son préenregistrement. Chaque "
           "complément rejoue à l'identique la requête préenregistrée de son instrument, "
           "nom, titre et question exceptés, et ses coûts sont ceux de l'étude, paquet "
           "pour paquet : seul le classement du choc macro a changé (D-239)."]
    for c in complements:
        instrument, r = c["instrument"], c["report"]
        out += ["", f"### {r['titre']}", "", r["question"], "",
                f"Commit `{r['commit']}`, le {r['computed']}, ici : {r['where']}."]
        if c.get("first_commit"):
            out += ["", f"Un premier tour a tourné sur `{c['first_commit']}`. Son emploi au "
                        f"voisinage du SMIC (C2) ne lisait que 15 % des salariés (D-252), et "
                        f"prêtait à chacun le changement du coût du travail de son ménage "
                        f"(D-254). Le second tour, sur le code du premier et les seules "
                        f"corrections de C2, corrige les deux. C2 n'entre ni dans les "
                        f"recettes ni dans "
                        f"la dette, et le second tour redonne le premier chiffre pour "
                        f"chiffre sur les coûts, les Δb et les coins de la boîte θ : "
                        f"`reports/{COMPLEMENTS_FIRST_ROUND}/` le garde, et le rendu refuse "
                        f"de tourner si un seul chiffre diffère."]
        for search, before in zip(r["searches"], c["study"]["searches"], strict=True):
            near = min(search["evaluations"], key=lambda e: abs(e["delta_aged"] - target))
            was = next(e for e in before["evaluations"] if e["knobs"] == near["knobs"])
            out += ["", f"**{search['persistence_label']}.** "
                        f"{verdict(search, instrument, target, theta)} Dans l'étude, le "
                        f"même paquet laissait Δb = {_pt(was['delta_aged'])}.", ""]
            out += _search_table(search, instrument, target, first_year=first_year,
                                 target_year=target_year, theta=theta)
        lacks = {f"{name} : {compact(why)}"
                 for s in r["searches"] for name, why in s["indices"]["absent"].items()}
        if lacks:
            out += ["", "**Ce qui manque à la chaîne**, pour le paquet le plus proche :", ""]
            out += [f"- {line}" for line in sorted(lacks)]
    return out


def _menu_row(entry: dict[str, Any]) -> str:
    instrument, r = entry["instrument"], entry["report"]
    evaluations = r["searches"][0]["evaluations"]
    costs = [e["cost_aged_eur"] for e in evaluations]
    grid = ", ".join(instrument.show(e["knobs"][instrument.knob]) for e in evaluations)
    return (f"| {instrument.label} | `{instrument.knob}` | {grid} "
            f"| de {_md(min(costs))} à {_md(max(costs))} |")


def _answer_table(entries: list[dict[str, Any]], target: float, theta: str) -> list[str]:
    searches = entries[0]["report"]["searches"]
    lines = ["| Instrument | " + " | ".join(s["persistence_label"] for s in searches) + " |",
             "|---|" + "---|" * len(searches)]
    for entry in entries:
        instrument, r = entry["instrument"], entry["report"]
        lines.append(f"| {instrument.label} | " + " | ".join(
            verdict(s, instrument, target, theta) for s in r["searches"]) + " |")
    return lines


def _entry_section(entry: dict[str, Any], target: float, *, first_year: int,
                   target_year: int, theta: str) -> list[str]:
    """One instrument: its question, each persistence's verdict and table, what the
    chain lacks, and the indices of the nearest bundle."""
    instrument, r = entry["instrument"], entry["report"]
    out = ["", f"### {instrument.label}", "", r["question"]]
    for search in r["searches"]:
        out += ["", f"**{search['persistence_label']}.** "
                    f"{verdict(search, instrument, target, theta)}", ""]
        out += _search_table(search, instrument, target, first_year=first_year,
                             target_year=target_year, theta=theta)
    lacks: dict[str, list[str]] = {}
    for search in r["searches"]:
        for name, why in search["indices"]["absent"].items():
            lacks.setdefault(f"{name} : {compact(why)}", []).append(
                search["persistence_label"])
    if lacks:
        out += ["", "**Ce qui manque à la chaîne**, pour le paquet le plus proche : "
                    "absent, et non nul.", ""]
        out += [f"- {line}" + ("" if len(labels) == len(r["searches"])
                               else f" ({', '.join(labels).lower()})")
                for line, labels in lacks.items()]
    out += ["", "**Les indices de §7, pour le paquet le plus proche de la cible**, "
                "vue vieillie, tirés de la passe qui l'a chiffré.", ""]
    return out + _indices(entry, target_year)


def _courbe_section(courbe: list[dict[str, Any]], target: float, first_year: int,
                    target_year: int, theta: str) -> list[str]:
    report = courbe[0]["report"]
    out = ["", "## La courbe de 2026, préenregistrée à part", "",
           "Depuis la refonte de 2026, la réduction générale est une courbe, et l'étude "
           "n'en chiffrait que le plafond, qui n'est plus que son seuil de sortie (D-239). "
           "Les boutons de la courbe (D-240) sont rejoués ici, après l'étude, et "
           f"préenregistrés à part : les requêtes sous `etude/{COURBE}/` ont été commitées "
           "avant toute passe, avec le pronostic écrit dans D-241. Chacune tient le cadre "
           "de l'étude champ pour champ ; seuls son nom, son titre, sa question et sa "
           "grille diffèrent. Chaque rapport a joué sa requête, à l'identique, sur le même "
           f"commit : `{report['commit']}`, le {report['computed']}. Les passes ont tourné "
           f"ici : {report['where']}.",
           *(["", f"Un premier tour a tourné sur le commit du préenregistrement, "
                  f"`{courbe[0]['first_commit']}`. Son emploi au voisinage du SMIC (C2) "
                  f"ne lisait que 15 % des salariés (D-252), et prêtait à chacun le "
                  f"changement du coût du travail de son ménage (D-254). Le second tour "
                  f"corrige les deux. "
                  f"C2 n'entre ni dans les recettes ni dans la dette, et le second tour "
                  f"redonne le premier chiffre pour chiffre sur les coûts, les Δb et les "
                  f"coins de la boîte θ : `reports/{COURBE_FIRST_ROUND}/` le garde, et le "
                  f"rendu refuse de tourner si un seul chiffre diffère."]
              if courbe[0].get("first_commit") else []),
           "",
           f"| Instrument | Bouton | Grille | Coût {first_year}, vieillie |",
           "|---|---|---|---|"]
    out += [_menu_row(entry) for entry in courbe]
    out += ["", "La population ne porte pas d'effectif d'entreprise : chaque salarié y est "
                "rangé dans une entreprise de moins de 50, dont le `t_delta` est donc celui "
                "de tous. Chaque paquet chiffre ainsi une hausse des deux `t_delta` du même "
                "nombre de points (D-241).",
            "", "### La réponse de la courbe", ""]
    out += _answer_table(courbe, target, theta)
    for entry in courbe:
        out += _entry_section(entry, target, first_year=first_year,
                              target_year=target_year, theta=theta)
    return out


#: What each instrument of the wider menu leaves out, on the page beside its answer
#: (D-250). Text, no figure: the figures are the reports'.
PHASE11_LEAVES_OUT = {
    "is": ("Le report tient le coût de la première année dix ans, et celui de 2026 compte "
           "la CEBGE, assise sur l'IS, que le droit éteint en 2027 : l'écart est surestimé "
           "d'environ un dixième. L'effet de l'IS sur le PIB reste hors de la dette, faute "
           "de boucle (D-218, D-246). L'un et l'autre vont vers une dette plus haute."),
    "pfu": ("La part de 12,8 % du PFU est l'impôt sur le revenu, et la baisse tombe dans la "
            "variante de l'IR de Mésange, qui la répartit sur tous les ménages quand elle "
            "va aux plus hauts déciles : la boucle rend sans doute trop. C10 ne compte pas "
            "le salaire que les propriétaires de firme se versent en moins, 0,31 € par euro "
            "de dividende en plus (tableau 2 B de Bach et al.), ni l'IS que l'entreprise "
            "paie sur le profit qu'il devient, ni les plus-values futures. Ces trois termes "
            "vont vers une dette plus haute : un écart qui ne passe sous zéro que de "
            "quelques centièmes de point peut s'y retourner (D-250). La CDHR reprend une "
            "part de la baisse aux foyers qu'elle tient, et leurs dividendes sortent de "
            "l'assiette de C10 : leur taux net ne bouge pas (D-250)."),
}


def _control_row(control: dict[str, Any]) -> str:
    gaps = control["gaps"]
    said = ("la redonne" if gaps["given_back"] else
            "ne la redonne pas" + ("" if gaps["same_verdicts"]
                                   else ", et un paquet change de verdict"))
    return (f"| {control['instrument'].label} | {control['against']} "
            f"| {_fr(gaps['share'] * 100, 6, sign=False)} pt "
            f"| {_fr(gaps['eur'], 0, sign=False)} € | {said} |")


def _phase11_section(phase11: dict[str, Any], target: float, first_year: int,
                     target_year: int, theta: str) -> list[str]:
    entries, controls = phase11["entries"], phase11["controls"]
    report = entries[0]["report"]
    out = ["", "## Le menu élargi de la phase 11, préenregistré à part", "",
           "La phase 11 fait entrer les entreprises et le capital dans la chaîne, et repose "
           "la question de l'étude sur le menu élargi (PHASE11_SPEC §8). Les requêtes sous "
           f"`etude/{PHASE11}/` ont été commitées avant toute passe, avec le pronostic écrit "
           "dans D-250. Chacune tient le cadre de l'étude champ pour champ ; seuls son nom, "
           "son titre, sa question et sa grille diffèrent. Chaque rapport a joué sa requête, "
           f"à l'identique, sur le même commit : `{report['commit']}`, le "
           f"{report['computed']}. Les passes ont tourné ici : {report['where']}.",
           "",
           f"| Instrument | Bouton | Grille | Coût {first_year}, vieillie |",
           "|---|---|---|---|"]
    out += [_menu_row(entry) for entry in entries]
    out += ["", "Deux instruments du §8 n'y entrent pas (D-250). La CVAE : le droit l'abroge "
                "en 2030, et le report du coût de la première année chiffrerait six années "
                "d'un impôt qui n'existe plus ; son seul bouton de taux ne règle de plus que "
                "la tranche au-dessus de 50 M€. Le `t_delta` avec son autofinancement : M5 "
                "attend le choix du propriétaire, et sans lui la courbe rejouée ci-dessus "
                "redonnerait D-242.",
            "", "### La réponse du menu élargi", ""]
    out += _answer_table(entries, target, theta)
    for entry in entries:
        out += _entry_section(entry, target, first_year=first_year,
                              target_year=target_year, theta=theta)
        out += ["", f"**Ce que ce chiffre ne compte pas.** "
                    f"{PHASE11_LEAVES_OUT[entry['instrument'].key]}"]
    out += ["", "### Les contrôles", "",
            "Les quatre requêtes de l'étude, rejouées telles quelles sur le même commit. "
            "Chacune doit redonner sa référence au dix-millième de point sur chaque écart et "
            "chaque coin, et à l'euro sur chaque coût, sous chaque persistance et dans "
            "chaque vue : l'étude de D-238, ou le complément de D-239 pour l'instrument "
            "reclassé depuis. L'écart est le plus grand, paquet par paquet.",
            "",
            "| Instrument | Référence | Écart sur Δb et les coins | Écart sur les coûts "
            "| Le contrôle |",
            "|---|---|---|---|---|"]
    out += [_control_row(c) for c in controls]
    return out


def render(etudes: list[dict[str, Any]],
           complements: list[dict[str, Any]] | tuple = (),
           courbe: list[dict[str, Any]] | tuple = (),
           phase11: dict[str, Any] | None = None) -> str:
    report = etudes[0]["report"]
    h = report["hypotheses"]
    target, target_year = h["target_share"], h["target_year"]
    first_year = report["start"]["year"] + 1
    lacking = ", ".join(e["instrument"].label[0].lower() + e["instrument"].label[1:]
                        for e in etudes if any(loop_absent(s)
                                               for s in e["report"]["searches"]))
    theta = theta_text(h["theta"]["common"])
    unit = report["unit"][0].upper() + report["unit"][1:]
    out = [
        "# L'étude : quelles baisses d'impôt font baisser la dette en 2035, et pour "
        "quels θ ?",
        "",
        "> Généré par `scripts/write_predictif_etude.py` depuis `etude/*.json` et "
        "`reports/exploration_etude_*.json`. Ne pas éditer à la main : "
        "`tests/test_predictif_etude.py` tient que cette page est le rendu de ces "
        "fichiers.",
        "",
        f"> {report['banner']}",
        "",
        f"> {report['debt_banner']}",
        "",
        "## Préenregistrée",
        "",
        "Les quatre requêtes, une par instrument, sont sous `etude/`. Elles ont été "
        "commitées avant toute passe, avec le pronostic écrit dans D-237. Chaque rapport "
        "a joué la requête commitée, à l'identique, sur le même commit : "
        f"`{report['commit']}`, le {report['computed']}. Les passes ont tourné ici : "
        f"{report['where']}.",
        *(["", f"Un premier tour a tourné sur le commit du préenregistrement, "
               f"`{etudes[0]['first_commit']}`. Ses rapports ne portaient pas ce qui manque "
               f"à la chaîne" + (f" : la boucle absente pour {lacking} s'y serait lue "
                                 f"comme nulle (D-238)" if lacking else "")
           + ". Le second tour le porte, et redonne le premier chiffre pour chiffre : "
             f"`reports/{FIRST_ROUND}/` le garde, et le rendu refuse de tourner si un "
             f"seul chiffre diffère."]
           if etudes[0].get("first_commit") else []),
        *(["", f"Un troisième tour a tourné sur `{report['commit']}` : le commit du second "
               f"tour, `{etudes[0]['second_commit']}`, avec les seules corrections de C2. "
               f"L'emploi au voisinage du SMIC du second tour ne lisait que 15 % des "
               f"salariés (D-252), et prêtait à chacun le changement du coût du travail de "
               f"son ménage (D-254). C2 n'entre ni dans les recettes ni dans la dette, et le "
               f"troisième tour redonne le second chiffre pour chiffre sur les coûts, les Δb "
               f"et les coins de la boîte θ : `reports/{SECOND_ROUND}/` le garde, et le "
               f"rendu refuse de tourner si un seul chiffre diffère. Les rapports lus ici "
               f"sont ceux du troisième tour."]
           if etudes[0].get("second_commit") else []),
        "",
        "## Le cadre",
        "",
        f"- Dépense : {h['spending_name']}. C'est la seule règle où la boucle PIB → "
        "recettes s'applique (D-218).",
        f"- Croissance : {h['growth_name']}. Taux : {h['rate_name']}.",
        f"- Salaires : {_pct(h['uprating']['wage'])} par an, prix "
        f"{_pct(h['uprating']['prices'])} ({h['uprating']['source']}).",
        f"- θ = {theta} partout. Comportement et boucle "
        "chiffrés, les deux persistances de l'effet macro côte à côte (D-230).",
        f"- Cible : Δb {target_year} ≤ {_pt(target)}, la dette de la réforme sous celle "
        f"de la référence en {target_year}. {unit}.",
        f"- Vues : vieillie, {report['views']['vieillie']} ; figée, "
        f"{report['views']['figee']}.",
        *[f"- Convention : {c}." for c in report["conventions"]],
        "",
        "## Le menu",
        "",
        "Les baisses que la population chiffre et que la chaîne porte, de un à une dizaine "
        "de milliards. L'IS n'y entre pas : la chaîne chiffre les réformes de la "
        "population, et le taux de l'IS n'en est pas une (D-228). La couche entreprises "
        "dit ses indices à part.",
        "",
        f"| Instrument | Bouton | Grille | Coût {first_year}, vieillie |",
        "|---|---|---|---|",
    ]
    out += [_menu_row(entry) for entry in etudes]
    for entry in etudes:
        for t in entry["report"]["hypotheses"]["transformations"]:
            rates = ", ".join(_pct(b["rate"]) for b in t["law"]["bareme"])
            out += ["", f"`{t['name']}` : {t['label']}. Le barème en vigueur qu'elle met "
                        f"à l'échelle est celui de {t['year']}, ses taux {rates}."]
    out += ["", "## La réponse", ""]
    out += _answer_table(etudes, target, theta)
    for entry in etudes:
        out += _entry_section(entry, target, first_year=first_year,
                              target_year=target_year, theta=theta)
    if complements:
        out += _complement_section(list(complements), target, first_year, target_year,
                                   theta)
    if courbe:
        out += _courbe_section(list(courbe), target, first_year, target_year, theta)
    if phase11:
        out += _phase11_section(phase11, target, first_year, target_year, theta)
    out += ["", "## Ce que l'étude ne dit pas", "",
            "- Ce n'est pas une prévision. Chaque chiffre dépend des scénarios nommés et de "
            "θ ; un autre scénario donne une autre réponse.",
            f"- Une seule valeur de θ, {theta}, et ses coins. La boîte θ est l'étendue aux coins, "
            "ni une somme de tranches ni un intervalle de probabilité.",
            "- La première année est chiffrée, les suivantes reportées en part de PIB : une "
            "convention, que `impots predictif` lève année par année (D-236).",
            ("- Dans l'étude de D-237, ni l'IS, ni les dividendes, ni la couche entreprises : "
             "la chaîne ne les portait pas, et le menu élargi de la phase 11 les y fait "
             "entrer. Ce qu'elle fermait alors, et pourquoi :" if phase11 else
             "- Ni l'IS, ni les dividendes, ni la couche entreprises : la chaîne ne les "
             "porte pas. Ce qu'elle ferme, et pourquoi :"),
            *[f"  - {name} : {why}"
              for name, why in report["searches"][0]["indices"]["closed"].items()],
            "- Elle ne recommande rien. Elle dit ce que la machine répond, sous ces "
            "hypothèses, à la question posée."]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    try:
        etudes, complements, courbe, phase11 = study()
    except EtudeError as error:
        print(str(error), file=sys.stderr)
        return 1
    OUT.write_text(render(etudes, complements, courbe, phase11), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
