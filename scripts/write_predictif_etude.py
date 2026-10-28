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

LE `t_delta` ET LE PLANCHER DE LA COURBE sont rejoués avec leur autofinancement, C11
(D-263), chacun préenregistré à part (D-264 à D-267) : la requête de la courbe sous son
propre répertoire, `etude/courbe_autofinancement/` puis
`etude/courbe_autofinancement_plancher/`, nom, titre et question exceptés. Le contrôle est
dans le rejeu : aux coins où le poids de C11 vaut 1, C11 rend la part du Trésor-Éco quelle
que soit l'élasticité de C2, et le rejeu doit y redonner ce qui reste de l'écart de la
courbe ; ses coûts doivent être les siens.

LES DEUX BOUTONS SONT REJOUÉS UNE DERNIÈRE FOIS avec le C11 réconcilié (D-270), ses emplois
valorisés à ce qu'un emploi au SMIC rapporte l'année de la réforme, mesuré sur le moteur :
ensemble, sous `etude/courbe_autofinancement_mesure/`, préenregistrés avant leurs passes
(D-271). Les refus et le contrôle des rejeux valent pour eux, et un refus de plus : des
rapports de deux commits.

LA VUE FIGÉE DES EXPLORATIONS QUI LISENT LES TAUX MARGINAUX est rejouée sur la correction de
D-276, préenregistrée dans D-278 : les rapports de l'étude dont la boîte porte une ligne de
C1 ou de C7, rejoués tels quels par `scripts/vue_figee.py`, en `reports/vue_figee/`. Le
rendu refuse un rejeu qui n'est pas l'exploration de l'étude, ou de deux commits. La vue
vieillie, que le défaut ne touchait pas, en est le contrôle : la page dit son écart.

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
#: The second round, whose C2 read 15 % of the earners (D-259) and lent each its household's
#: cost change (D-261). The third is the second round's commit with C2's fixes alone: it
#: must give the second back figure for figure.
SECOND_ROUND = "etude_second_tour"
#: What a round computes, as against what it reports about it.
FIGURES = ("knobs", "cost_aged_eur", "cost_frozen_eur", "delta_aged", "delta_frozen",
           "corners", "corner_low", "corner_high", "meets_target")
#: Requests replayed after the result, outside the preregistration (D-239): each must be
#: an instrument's preregistered request, with only these fields changed.
COMPLEMENTS = "complements"
COMPLEMENT_FREE = ("name", "titre", "question")
#: The complements' first round, whose C2 read 15 % of the earners (D-259) and lent each its
#: household's cost change (D-261). The rerun corrects C2, which enters no revenue and no
#: debt: it must give the first round back figure for figure (D-262).
COMPLEMENTS_FIRST_ROUND = "complements_premier_tour"
#: The 2026 curve, replayed in the study and preregistered apart (D-241): each request
#: holds the frame of the study's allègement request, only these fields changed.
COURBE = "courbe"
COURBE_FREE = ("name", "titre", "question", "bounds")
#: The curve's first round, on its preregistration's commit, with a C2 that read 15 % of the
#: earners (D-259) and lent each its household's cost change (D-261). The rerun corrects C2,
#: which enters no revenue and no debt: it must give the first round back figure for figure.
COURBE_FIRST_ROUND = "courbe_premier_tour"
#: The wider menu of Phase 11, preregistered apart (D-250): each request holds the frame
#: of the study's IR request, only these fields changed; the study's own four requests
#: are replayed as they are, as controls, under this directory of `reports/`.
PHASE11 = "phase11"
PHASE11_FREE = ("name", "titre", "question", "bounds")
CONTROLS = Path("etude_phase11") / "controles"
#: The PFU of the wider menu replayed with the wages its firm owners shift (D-252): the
#: request holds the PFU's own, only these fields changed; the row the replay adds is
#: varied at its corners, and those where it is 0 are the wider menu's.
SALAIRES = "phase11_salaires"
SALAIRES_FREE = ("name", "titre", "question")
WAGE_SHIFT = "dividend_wage_shift_firm_owners"
#: The curve's knobs replayed with their self-financing, C11 (D-264, D-266): each request
#: holds the curve's own, only these fields changed; C11's weight is varied at its corners,
#: and where it is 1, C11 brings back the Trésor-Éco's share of the cut whatever C2 reads.
#: The `t_delta`'s request is under this directory, and every replay's report is named
#: after it.
AUTOFINANCEMENT = "courbe_autofinancement"
AUTOFINANCEMENT_FREE = ("name", "titre", "question")
SELF_FINANCING_WEIGHT = "autofinancement_poids_tresor_eco"
#: How near a control must give back its reference to be said to: a ten-thousandth of a
#: point of GDP on every Δb and every corner, a euro on every cost (D-250).
CONTROL_SHARE = 1e-6
CONTROL_EUR = 1.0
#: And on an index of §7 a replay leaves alone, in its own unit: jobs, euros, per cent.
CONTROL_INDEX = 1e-6
#: The commits of the committed reports that counted C2's jobs near the SMIC on diluted
#: inputs (D-255): every earner of the whole frame at the frame's weight, a rate only for
#: the households the pass priced. The page says so beside the figure, which no other
#: number reads.
C2_BEFORE_D255 = frozenset({
    "6dab3a404722c57f53f3f2cc60c9cc98b2dc6f7f",
    "e0c3d7fe901b320e9b0b3c8ed1e39f8c678223d5",
    "cacd43af7a5a506d476cfcbc454a58439d1e614b",
    "893e4de1f8908f6b2d15af6192250494e386a065",
    "ca6288d1834bcb816de84f3ff8e9e8a3d6bf6c37",
})
C2_NOTE = ("compté avant D-255, sur des entrées que le sous-échantillon diluait : de 5,8 à "
           "6,5 fois trop bas selon le paquet. La dette n'en dépend pas")


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


@dataclass(frozen=True)
class Replay:
    key: str
    """The curve's knob replayed, as `COURBE_MENU` keys it."""
    directory: str
    """Its request's directory under `etude/`."""
    name: str
    """How the page names the knob, without its article."""
    entry: str
    """The entry that wrote its prognosis before its passes."""
    leaves_out: str = ""
    """What this replay leaves out beyond what every replay does."""
    report: str = AUTOFINANCEMENT
    """Its report's prefix: `reports/exploration_<report>_<key>.json`."""


#: The curve's knobs replayed with their self-financing, in the order preregistered. Each
#: has its own directory: one replay's request beside another's, before its report, would
#: be refused, and the committed page could not be rendered until its passes (D-266).
AUTOFINANCEMENT_MENU: tuple[Replay, ...] = (
    Replay("t_delta", AUTOFINANCEMENT, "`t_delta`", "D-264"),
    Replay("t_min", "courbe_autofinancement_plancher", "plancher `t_min`", "D-266",
           " Le Trésor-Éco n° 97 lit des allègements sur les bas salaires, quand le "
           "plancher porte la baisse jusqu'à 3 SMIC, où C2 ne répond plus dès 2 SMIC : ses "
           "60 % y sont sans doute plus loin encore de ce que la baisse rend, vers une "
           "dette plus basse."),
)

#: The curve's two knobs replayed with the reconciled C11 (D-270), under one directory:
#: preregistered together, before their passes (D-271).
MESURE = "courbe_autofinancement_mesure"
MESURE_MENU: tuple[Replay, ...] = (
    Replay("t_delta", MESURE, "`t_delta`", "D-271", report=MESURE),
    Replay("t_min", MESURE, "plancher `t_min`", "D-271", AUTOFINANCEMENT_MENU[1].leaves_out,
           report=MESURE),
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
                    f"tour n'est plus la seule correction de C2 (D-259, D-261).")
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
                    f"la seule correction de C2 (D-259, D-261).")
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
                    f"second tour n'est plus la seule correction de C2 (D-259, D-261).")
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


def shift_control(report: dict[str, Any], menu: dict[str, Any]) -> dict[str, Any]:
    """The replay where the wage shift is at its low end, 0, against the wider menu: each
    such corner must be the menu's corner with the other rows set alike, and each cost the
    menu's. The largest gap, in share of GDP and in euros, as `control_gaps` reads it."""
    share, eur = 0.0, 0.0
    nil = (WAGE_SHIFT, "0")
    for search, before in zip(report["searches"], menu["searches"], strict=True):
        if search["persistence"] != before["persistence"]:
            raise EtudeError("le rejeu du PFU et le menu élargi n'ont pas les mêmes "
                             "persistances")
        # One request, so one grid, every bundle of which a report carries.
        was = {json.dumps(e["knobs"], sort_keys=True): e for e in before["evaluations"]}
        for e in search["evaluations"]:
            b = was[json.dumps(e["knobs"], sort_keys=True)]
            corners = {frozenset(_settings(label)): v for label, v in b["corners"]}
            for label, value in e["corners"]:
                settings = _settings(label)
                if nil not in settings:
                    continue
                reference = corners.get(frozenset(settings - {nil}))
                if reference is None:
                    raise EtudeError(f"le coin « {label} » du rejeu n'a pas son pendant "
                                     f"dans le menu élargi.")
                share = max(share, abs(value - reference))
            eur = max(eur, abs(e["cost_aged_eur"] - b["cost_aged_eur"]),
                      abs(e["cost_frozen_eur"] - b["cost_frozen_eur"]))
    return {"share": share, "eur": eur,
            "given_back": share <= CONTROL_SHARE and eur <= CONTROL_EUR}


def load_salaires(phase11: dict[str, Any] | None, requests: Path = REQUESTS,
                  reports: Path = REPORTS) -> dict[str, Any] | None:
    """The PFU of the wider menu replayed with the wage shift under `etude/phase11_salaires/`,
    and the report that played it, checked like the menu; with its control, the corners
    where the shift is 0 against the menu's (D-252)."""
    from impots.api.schemas import ExplorationReport, ExplorationRequest

    directory = requests / SALAIRES
    if not directory.exists():
        return None
    if phase11 is None:
        raise EtudeError(f"etude/{SALAIRES}/ rejoue le PFU d'un menu élargi que le dépôt "
                         f"n'a pas.")
    strays = sorted(p.name for p in directory.glob("*.json") if p.name != "pfu.json")
    if strays:
        raise EtudeError(f"etude/{SALAIRES}/ porte {strays} : seul le PFU s'y rejoue, et "
                         f"une requête que la page ne rendrait pas se lirait comme non "
                         f"jouée.")
    request_path = directory / "pfu.json"
    report_path = reports / f"exploration_{SALAIRES}_pfu.json"
    if not request_path.exists():
        raise EtudeError(f"etude/{SALAIRES}/ sans la requête du PFU.")
    if not report_path.exists():
        raise EtudeError(f"le rejeu du PFU sans rapport : {report_path.name}.")
    menu = next(e for e in phase11["entries"] if e["instrument"].key == "pfu")
    request = ExplorationRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    dump = request.model_dump(mode="json", exclude_none=True)

    def held(payload: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in payload.items() if k not in SALAIRES_FREE}

    if held(dump) != held(menu["report"]["request"]):
        raise EtudeError(f"etude/{SALAIRES}/pfu.json ne rejoue pas la requête du PFU du "
                         f"menu élargi : seuls {list(SALAIRES_FREE)} peuvent différer.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    ExplorationReport.model_validate(report)
    if report["request"] != dump:
        raise EtudeError(f"{report_path.name} n'a pas joué sa requête, "
                         f"etude/{SALAIRES}/pfu.json.")
    if not (report.get("where") or "").strip():
        raise EtudeError(f"{report_path.name} ne dit pas où ses passes ont tourné.")
    unshifted = [label for s in report["searches"] for e in s["evaluations"]
                 for label, _ in e["corners"]
                 if WAGE_SHIFT not in {name for name, _ in _settings(label)}]
    if unshifted:
        raise EtudeError(f"{report_path.name} ne fait pas varier {WAGE_SHIFT} à ses coins "
                         f"(« {unshifted[0]} ») : il n'a pas tourné avec les salaires "
                         f"déplacés.")
    return {"instrument": menu["instrument"], "report": report, "menu": menu["report"],
            "control": shift_control(report, menu["report"])}


def tresor_eco_share() -> float:
    """C11's share at θ = 1, read off the store as the channel reads it (D-263)."""
    from impots.behavioural import channels
    from impots.behavioural.store import load as load_store

    store = load_store()
    return store[channels.C11_RETURN].central / store[channels.C11_COST].central


def _non_chain(search: dict[str, Any]) -> dict[str, Any]:
    """The nearest bundle's indices outside the chain's own rows, by key: what C11 reads
    or leaves alone, never the balance, the debt or the interest it moves."""
    return {row["key"]: (row["values"], row.get("box")) for row in search["indices"]["rows"]
            if row["available"] and row["stage"] != "chaîne"}


def self_financing_control(report: dict[str, Any], courbe: dict[str, Any],
                           share: float, key: str) -> dict[str, Any]:
    """The replay where C11's weight is 1, against the curve: each such corner must be the
    curve's corner with the other rows set alike, times what C11 leaves of the cut; each
    cost the curve's; and the nearest bundle's indices outside the chain the curve's. The
    largest gap, in share of GDP, in euros, and on an index, as `control_gaps` reads it."""
    gap, eur, indices = 0.0, 0.0, 0.0
    full = (SELF_FINANCING_WEIGHT, "1")
    for search, before in zip(report["searches"], courbe["searches"], strict=True):
        if search["persistence"] != before["persistence"]:
            raise EtudeError(f"le rejeu du {key} et la courbe n'ont pas les mêmes "
                             f"persistances")
        # One request, so one grid, every bundle of which a report carries.
        was = {json.dumps(e["knobs"], sort_keys=True): e for e in before["evaluations"]}
        for e in search["evaluations"]:
            b = was[json.dumps(e["knobs"], sort_keys=True)]
            corners = {frozenset(_settings(label)): v for label, v in b["corners"]}
            for label, value in e["corners"]:
                settings = _settings(label)
                if full not in settings:
                    continue
                reference = corners.get(frozenset(settings - {full}))
                if reference is None:
                    raise EtudeError(f"le coin « {label} » du rejeu n'a pas son pendant "
                                     f"dans la courbe.")
                gap = max(gap, abs(value - (1 - share) * reference))
            eur = max(eur, abs(e["cost_aged_eur"] - b["cost_aged_eur"]),
                      abs(e["cost_frozen_eur"] - b["cost_frozen_eur"]))
        now, then = _non_chain(search), _non_chain(before)
        if now.keys() != then.keys():
            raise EtudeError(f"le rejeu du {key} et la courbe n'ont pas les mêmes indices "
                             f"hors de la chaîne : {sorted(now.keys() ^ then.keys())}.")
        for row, (values, box) in now.items():
            values_then, box_then = then[row]
            if values.keys() != values_then.keys():
                raise EtudeError(f"l'indice « {row} » du rejeu n'a pas les années de la "
                                 f"courbe.")
            spans = [(values[k], values_then[k]) for k in values]
            spans += [(v, w) for k in (box or {}) for v, w in
                      zip(box[k], (box_then or {}).get(k, (None, None)), strict=True)]
            if any(w is None for _, w in spans):
                raise EtudeError(f"l'indice « {row} » du rejeu a une boîte que la courbe "
                                 f"n'a pas.")
            indices = max(indices, *(abs(v - w) for v, w in spans))
    return {"share": gap, "eur": eur, "indices": indices,
            "given_back": gap <= CONTROL_SHARE and eur <= CONTROL_EUR
            and indices <= CONTROL_INDEX}


def load_autofinancement(courbe: list[dict[str, Any]], replay: Replay,
                         requests: Path = REQUESTS,
                         reports: Path = REPORTS) -> dict[str, Any] | None:
    """One knob of the curve replayed with its self-financing under its directory, and the
    report that played it, checked like the curve; with its control, the corners where
    C11's weight is 1 against the curve's (D-264, D-266)."""
    from impots.api.schemas import ExplorationReport, ExplorationRequest

    key, where = replay.key, replay.directory
    directory = requests / where
    if not directory.exists():
        return None
    knob = next((e for e in courbe if e["instrument"].key == key), None)
    if knob is None:
        raise EtudeError(f"etude/{where}/ rejoue le {key} d'une courbe que le dépôt n'a "
                         f"pas.")
    menu = sorted(r.key for r in (*AUTOFINANCEMENT_MENU, *MESURE_MENU) if r.directory == where)
    strays = sorted(p.name for p in directory.glob("*.json")
                    if p.name not in {f"{k}.json" for k in menu})
    if strays:
        who = (f"seul le {key} s'y rejoue" if len(menu) == 1
               else f"seuls {' et '.join(menu)} s'y rejouent")
        raise EtudeError(f"etude/{where}/ porte {strays} : {who}, et une requête que la page "
                         f"ne rendrait pas se lirait comme non jouée.")
    request_path = directory / f"{key}.json"
    report_path = reports / f"exploration_{replay.report}_{key}.json"
    if not request_path.exists():
        raise EtudeError(f"etude/{where}/ sans la requête du {key}.")
    if not report_path.exists():
        raise EtudeError(f"le rejeu du {key} sans rapport : {report_path.name}.")
    request = ExplorationRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    dump = request.model_dump(mode="json", exclude_none=True)

    def held(payload: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in payload.items() if k not in AUTOFINANCEMENT_FREE}

    if held(dump) != held(knob["report"]["request"]):
        raise EtudeError(f"etude/{where}/{key}.json ne rejoue pas la requête du {key} de la "
                         f"courbe : seuls {list(AUTOFINANCEMENT_FREE)} peuvent différer.")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    ExplorationReport.model_validate(report)
    if report["request"] != dump:
        raise EtudeError(f"{report_path.name} n'a pas joué sa requête, "
                         f"etude/{where}/{key}.json.")
    if not (report.get("where") or "").strip():
        raise EtudeError(f"{report_path.name} ne dit pas où ses passes ont tourné.")
    unweighted = [label for s in report["searches"] for e in s["evaluations"]
                  for label, _ in e["corners"]
                  if SELF_FINANCING_WEIGHT not in {name for name, _ in _settings(label)}]
    if unweighted:
        raise EtudeError(f"{report_path.name} ne fait pas varier {SELF_FINANCING_WEIGHT} à "
                         f"ses coins (« {unweighted[0]} ») : il n'a pas tourné avec C11.")
    share = tresor_eco_share()
    return {"instrument": knob["instrument"], "replay": replay, "report": report,
            "courbe": knob["report"], "share": share,
            "control": self_financing_control(report, knob["report"], share, key)}


def study(requests: Path = REQUESTS,
          reports: Path = REPORTS) -> tuple[list, list, list, dict[str, Any] | None]:
    """The study, its complements, the curve with its knobs replayed with their
    self-financing, and the wider menu of Phase 11 with its PFU replayed, all checked, the
    box of each bundle read at θ = 0 and θ = 1 among them, and the study's bundles priced
    every year when their reports are there: what the page renders."""
    etudes = load(requests, reports)
    complements = load_complements(etudes, requests, reports)
    phase11 = load_phase11(etudes, complements, requests, reports)
    salaires = load_salaires(phase11, requests, reports)
    if salaires is not None:
        phase11["salaires"] = salaires
    courbe = load_courbe(etudes, requests, reports)
    for replay in AUTOFINANCEMENT_MENU:
        autofinancement = load_autofinancement(courbe, replay, requests, reports)
        if autofinancement is not None:
            next(e for e in courbe
                 if e["instrument"].key == replay.key)["autofinancement"] = autofinancement
    mesure = [(replay, load_autofinancement(courbe, replay, requests, reports))
              for replay in MESURE_MENU]
    commits = {auto["report"]["commit"] for _, auto in mesure if auto is not None}
    if len(commits) > 1:
        raise EtudeError(f"les rejeux sous etude/{MESURE}/ ont tourné sur {sorted(commits)} : "
                         f"préenregistrés ensemble, ils tournent sur un seul commit.")
    for replay, auto in mesure:
        if auto is not None:
            next(e for e in courbe if e["instrument"].key == replay.key)["mesure"] = auto
    theta_rows(etudes, complements, courbe, phase11)
    annual = load_annuel(etudes, requests, reports, complements)
    if annual is not None:
        for entry in etudes:
            entry["annuel"] = annual[entry["instrument"].key]
    figee = load_vue_figee(etudes, reports)
    for key, replay in (figee or {}).items():
        next(e for e in etudes if e["instrument"].key == key)["vue_figee"] = replay
    return etudes, complements, courbe, phase11


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
        if row["key"] == "emploi_smic" and report["commit"] in C2_BEFORE_D255:
            shown += f" ; {C2_NOTE}"
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
                        f"voisinage du SMIC (C2) ne lisait que 15 % des salariés (D-259), et "
                        f"prêtait à chacun le changement du coût du travail de son ménage "
                        f"(D-261). Le second tour, sur le code du premier et les seules "
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
    if entry.get("vue_figee"):
        out += ["", f"La colonne « Δb {target_year}, figée » lisait les taux marginaux de la "
                    f"vue vieillie (D-276) : elle est rechiffrée plus bas, dans « La vue "
                    f"figée, rechiffrée »."]
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
                  f"ne lisait que 15 % des salariés (D-259), et prêtait à chacun le "
                  f"changement du coût du travail de son ménage (D-261). Le second tour "
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


#: What the PFU replayed with the wage shift still leaves out (D-252).
SALAIRES_LEAVES_OUT = (
    "Les plus-values futures dont les dividendes induits sont tirés, taxées plus bas que "
    "le dividende : vers une dette plus haute. Le salaire déplacé est mesuré sur le cas de "
    "la figure A2 de Bach et al., un salarié célibataire à six plafonds de la sécurité "
    "sociale ; un gérant majoritaire de SARL, travailleur non salarié, cotise moins, et "
    "chaque euro qu'il déplace reprend moins : vers une dette plus basse. Le canal compte "
    "le déplacement dès la première année, quand les auteurs ne le trouvent qu'à partir de "
    "la deuxième, et les droits à retraite que les cotisations perdues ouvraient sont hors "
    "de l'horizon. La variante de l'IR de Mésange et la CDHR, comme au menu élargi.")


def _salaires_section(salaires: dict[str, Any], target: float, first_year: int,
                      target_year: int, theta: str) -> list[str]:
    instrument, r, menu = salaires["instrument"], salaires["report"], salaires["menu"]
    control = salaires["control"]
    out = ["", "## Le PFU rejoué avec les salaires déplacés", "",
           "Le menu élargi laissait hors de C10 le salaire que les propriétaires de firme "
           "cessent de se verser quand leurs dividendes montent, et le disait à côté de son "
           "chiffre. D-252 le fait entrer : 0,309 € de salaire imposable par euro de "
           "dividende en plus, de 0 à 0,519 (tableau 2 B de Bach et al.), et sur chaque "
           "euro déplacé, ce qu'il rapportait moins l'IS que l'entreprise paie sur le profit "
           f"qu'il devient. La requête sous `etude/{SALAIRES}/` rejoue celle du PFU du menu "
           "élargi champ pour champ ; seuls son nom, son titre et sa question diffèrent. "
           "Elle a été commitée avant sa passe, avec le pronostic écrit dans D-252. Le "
           f"rapport a joué sa requête, à l'identique, sur le commit `{r['commit']}`, le "
           f"{r['computed']}. La passe a tourné ici : {r['where']}.",
           "", r["question"]]
    for search, before in zip(r["searches"], menu["searches"], strict=True):
        was = {json.dumps(e["knobs"], sort_keys=True): e for e in before["evaluations"]}
        then = " ; ".join(
            f"{instrument.show(e['knobs'][instrument.knob])}, "
            f"{_pt(was[json.dumps(e['knobs'], sort_keys=True)]['delta_aged'])}"
            for e in search["evaluations"])
        out += ["", f"**{search['persistence_label']}.** "
                    f"{verdict(search, instrument, target, theta)} Sans les salaires "
                    f"déplacés, au menu élargi, Δb valait, vue vieillie : {then}.", ""]
        out += _search_table(search, instrument, target, first_year=first_year,
                             target_year=target_year, theta=theta)
    said = ("les redonne" if control["given_back"] else "ne les redonne pas")
    out += ["", f"**Le contrôle.** Aux coins où le déplacement vaut 0, le rejeu doit redonner "
                f"ceux du menu élargi, et ses coûts les siens : il {said}. L'écart le plus "
                f"grand vaut {_fr(control['share'] * 100, 6, sign=False)} pt sur les coins "
                f"et {_fr(control['eur'], 0, sign=False)} € sur les coûts.",
            "", f"**Ce que ce chiffre ne compte pas.** {SALAIRES_LEAVES_OUT}"]
    return out


#: What every knob replayed with its self-financing leaves out, and which way (D-264).
AUTOFINANCEMENT_LEAVES_OUT = (
    "C2 compte des personnes, au coût annuel de leur propre travail, quand les 12 000 € du "
    "Trésor-Éco n° 97 sont le retour d'un emploi à temps plein : à θ = 0, la part est sans "
    "doute trop haute. θ = 1 lit le bas du coût brut par emploi des allègements de 1993 à "
    "1997, 20 000 € sur 20 000 à 40 000 €, et la note envisage elle-même un coût doublé "
    "pour la seconde vague. Les deux vont vers une dette plus basse. Les 12 000 € sont de "
    "2009, tenus tels : au SMIC de 2026, la réduction générale laisse peu de cotisations "
    "patronales, et le RSA a été revalorisé, dans un sens que le projet ne mesure pas. C11 "
    "ne compte ni l'impôt sur le revenu des emplois créés, ni leurs autres prestations, ni "
    "l'allocation chômage évitée au-delà du RSA, ni l'effet sur le PIB, que Mésange ne "
    "chiffre pas pour sa variante ciblée : vers une dette plus haute. Un tour seulement : "
    "les recettes de C11 ne relancent rien.")


def _autofinancement_section(auto: dict[str, Any], target: float, first_year: int,
                             target_year: int, theta: str) -> list[str]:
    instrument, r, courbe = auto["instrument"], auto["report"], auto["courbe"]
    control, share, replay = auto["control"], auto["share"], auto["replay"]
    out = ["", f"## Le {replay.name} de la courbe rejoué avec son autofinancement", "",
           f"La courbe rejouée plus haut chiffrait le {replay.name} sans rien de ce qu'une "
           "baisse ciblée rend : Mésange n'a pas de ligne de solde pour sa variante ciblée, et "
           "les emplois de C2 n'entraient pas dans les recettes. D-263 y fait entrer C11 : "
           "une part de la baisse revient, de la lecture de C2, ses emplois valorisés à "
           f"12 000 € l'un, à θ = 0, à {_pct(share)} à θ = 1, celle du Trésor-Éco n° 97. "
           f"La requête sous `etude/{replay.directory}/` rejoue celle du {replay.name} de la "
           "courbe champ pour champ ; seuls son nom, son titre et sa question diffèrent. Elle "
           f"a été commitée avant ses passes, avec le pronostic écrit dans {replay.entry}. Le "
           f"rapport a joué sa requête, à l'identique, sur le commit `{r['commit']}`, le "
           f"{r['computed']}. Les passes ont tourné ici : {r['where']}.",
           "", r["question"]]
    for search, before in zip(r["searches"], courbe["searches"], strict=True):
        was = {json.dumps(e["knobs"], sort_keys=True): e for e in before["evaluations"]}
        then = " ; ".join(
            f"{instrument.show(e['knobs'][instrument.knob])}, "
            f"{_pt(was[json.dumps(e['knobs'], sort_keys=True)]['delta_aged'])}"
            for e in search["evaluations"])
        out += ["", f"**{search['persistence_label']}.** "
                    f"{verdict(search, instrument, target, theta)} Sans l'autofinancement, "
                    f"à la courbe, Δb valait, vue vieillie : {then}.", ""]
        out += _search_table(search, instrument, target, first_year=first_year,
                             target_year=target_year, theta=theta)
    lacks = {f"{name} : {compact(why)}"
             for s in r["searches"] for name, why in s["indices"]["absent"].items()}
    if lacks:
        out += ["", "**Ce qui manque à la chaîne**, pour le paquet le plus proche : absent, "
                    "et non nul.", ""]
        out += [f"- {line}" for line in sorted(lacks)]
    said = "les redonne" if control["given_back"] else "ne les redonne pas"
    out += ["", f"**Le contrôle.** Aux coins où le poids de C11 vaut 1, C11 rend "
                f"{_pct(share)} de la baisse quelle que soit l'élasticité de C2 : le rejeu "
                f"doit y redonner {_fr(1 - share, sign=False)} fois l'écart de la courbe, ses "
                f"coûts les siens, et les indices du paquet le plus proche hors de la chaîne, "
                f"l'emploi de C2 et de Mésange compris, les siens. Il {said}. L'écart le plus "
                f"grand vaut {_fr(control['share'] * 100, 6, sign=False)} pt sur les coins, "
                f"{_fr(control['eur'], 0, sign=False)} € sur les coûts et "
                f"{_fr(control['indices'], 6, sign=False)} sur les indices, dans leur unité.",
            "", f"**Ce que ce chiffre ne compte pas.** {AUTOFINANCEMENT_LEAVES_OUT}"
                f"{replay.leaves_out}"]
    return out


#: What the curve replayed with the reconciled C11 leaves out, and which way (D-271).
MESURE_LEAVES_OUT = (
    "C2 compte des personnes, au coût annuel de leur propre travail, chacune à la valeur "
    "d'un emploi à temps plein au SMIC : à θ = 0, la part est sans doute trop haute. θ = 1 "
    "lit le bas du coût brut par emploi des allègements de 1993 à 1997, 20 000 € sur 20 000 "
    "à 40 000 €, et la note envisage elle-même un coût doublé pour la seconde vague. Les deux "
    "vont vers une dette plus basse. La valeur d'un emploi est celle d'un célibataire sans "
    "enfant ni loyer : C11 ne compte ni les prestations d'un autre ménage, ni l'allocation "
    "chômage évitée au-delà du RSA, ni l'effet sur le PIB, que Mésange ne chiffre pas pour sa "
    "variante ciblée, vers une dette plus haute. Un tour seulement : les recettes de C11 ne "
    "relancent rien.")


def tresor_eco_return() -> float:
    """What the Trésor-Éco n° 97 says a job brings, read off the store (D-263)."""
    from impots.behavioural import channels
    from impots.behavioural.store import load as load_store

    return load_store()[channels.C11_RETURN].central


def returned_share(search: dict[str, Any], before: dict[str, Any]) -> float:
    """What C11 brings back of the nearest bundle's cut at θ, in the aged view, read off
    the two Δb: the chain is linear in the cost, so s = 1 − Δb / Δb of the curve (D-271)."""
    return 1 - (search["evaluations"][0]["delta_aged"]
                / before["evaluations"][0]["delta_aged"])


#: C2's index, as the reports label it: what D-269's weights move (D-272).
C2_INDEX_LABEL = "Emploi au voisinage du SMIC"


def index_gaps(report: dict[str, Any], courbe: dict[str, Any]) -> list[tuple[str, str, float]]:
    """The nearest bundle's indices outside the chain that are not the curve's: (label,
    unit, largest gap over the searches, the values and the box), in the report's order.
    `self_financing_control` has already refused rows, years or boxes the curve lacks."""
    gaps: dict[str, tuple[str, str, float]] = {}
    for search, before in zip(report["searches"], courbe["searches"], strict=True):
        then = {row["key"]: row for row in before["indices"]["rows"]}
        for row in search["indices"]["rows"]:
            if not row["available"] or row["stage"] == "chaîne":
                continue
            was = then[row["key"]]
            spans = [(row["values"][k], was["values"][k]) for k in row["values"]]
            spans += [(v, w) for k in (row.get("box") or {})
                      for v, w in zip(row["box"][k], was["box"][k], strict=True)]
            gap = max((abs(v - w) for v, w in spans), default=0.0)
            if gap > CONTROL_INDEX:
                label, unit, before_gap = gaps.get(row["key"], (row["label"], row["unit"], 0.0))
                gaps[row["key"]] = (label, unit, max(before_gap, gap))
    return list(gaps.values())


def _listed(instrument: Instrument, search: dict[str, Any], other: dict[str, Any]) -> str:
    """Each bundle of `search`, with the Δb another search gave it, in the aged view."""
    by = {json.dumps(e["knobs"], sort_keys=True): e for e in other["evaluations"]}
    return " ; ".join(
        f"{instrument.show(e['knobs'][instrument.knob])}, "
        f"{_pt(by[json.dumps(e['knobs'], sort_keys=True)]['delta_aged'])}"
        for e in search["evaluations"])


def _mesure_section(entries: list[dict[str, Any]], target: float, first_year: int,
                    target_year: int, theta: str) -> list[str]:
    first = entries[0]["mesure"]
    r, share, replay = first["report"], first["share"], first["replay"]
    euros = f"{tresor_eco_return():,.0f} €".replace(",", " ")
    earlier = any(e.get("autofinancement") for e in entries)
    out = ["", "## La courbe rejouée avec l'autofinancement réconcilié", "",
           f"{'Les rejeux qui précèdent valorisaient' if earlier else 'C11 valorisait'} les "
           f"emplois de C2 à {euros} l'un, le retour d'un emploi selon le Trésor-Éco n° 97, en "
           "euros de 2009. D-270 réconcilie C11 : ses emplois y valent ce qu'un emploi au "
           "SMIC rapporte aux finances publiques l'année de la réforme, mesuré sur le moteur "
           "(D-256), ses cotisations, sa CSG, sa CRDS, son impôt sur le revenu et le RSA qu'il "
           "évite, moins la prime d'activité qu'il ouvre. θ = 1 reste la part du Trésor-Éco, "
           f"{_pct(share)}. Les requêtes sous `etude/{replay.directory}/` rejouent celles de la "
           "courbe champ pour champ ; seuls leurs noms, leurs titres et leurs questions "
           "diffèrent. Elles ont été commitées avant leurs passes, avec le pronostic écrit "
           f"dans {replay.entry}. Les rapports ont joué leurs requêtes, à l'identique, sur le "
           f"commit `{r['commit']}`, le {r['computed']}. Les passes ont tourné ici : "
           f"{r['where']}."]
    for entry in entries:
        auto, old = entry["mesure"], entry.get("autofinancement")
        instrument, report, courbe = auto["instrument"], auto["report"], auto["courbe"]
        control, replay = auto["control"], auto["replay"]
        said = (f"À θ = {theta}, en vue vieillie, C11 rend "
                f"{_pct(returned_share(report['searches'][0], courbe['searches'][0]))} de la "
                f"baisse de chaque paquet")
        if old is not None:
            said += (f", contre "
                     f"{_pct(returned_share(old['report']['searches'][0], courbe['searches'][0]))}"
                     f" à {euros} l'emploi ({old['replay'].entry})")
        out += ["", f"### Le {replay.name}", "", report["question"], "", f"{said}."]
        olds = old["report"]["searches"] if old is not None else [None] * len(courbe["searches"])
        for search, before, was_old in zip(report["searches"], courbe["searches"], olds,
                                           strict=True):
            line = (f"**{search['persistence_label']}.** "
                    f"{verdict(search, instrument, target, theta)} Sans l'autofinancement, à "
                    f"la courbe, Δb valait, vue vieillie : {_listed(instrument, search, before)}.")
            if was_old is not None:
                line += f" À {euros} l'emploi : {_listed(instrument, search, was_old)}."
            out += ["", line, ""]
            out += _search_table(search, instrument, target, first_year=first_year,
                                 target_year=target_year, theta=theta)
        lacks = {f"{name} : {compact(why)}"
                 for s in report["searches"] for name, why in s["indices"]["absent"].items()}
        if lacks:
            out += ["", "**Ce qui manque à la chaîne**, pour le paquet le plus proche : "
                        "absent, et non nul.", ""]
            out += [f"- {line}" for line in sorted(lacks)]
        given = ("les redonne" if control["share"] <= CONTROL_SHARE
                 and control["eur"] <= CONTROL_EUR else "ne les redonne pas")
        gaps = index_gaps(report, courbe)
        if gaps:
            moved = " ; ".join(f"{label}, de {_fr(gap, 2, sign=False)} {unit}"
                               for label, unit, gap in gaps)
            indices = (f"Hors de la chaîne, les indices du paquet le plus proche sont ceux de "
                       f"la courbe, sauf : {moved}, au plus.")
            if any(label == C2_INDEX_LABEL for label, _, _ in gaps):
                indices += (" C2 y compte chacun à son propre poids dans la passe (D-269), "
                            "quand la courbe le comptait au poids moyen de son ménage.")
        else:
            indices = ("Hors de la chaîne, les indices du paquet le plus proche sont ceux de "
                       "la courbe.")
        out += ["", f"**Le contrôle.** Aux coins où le poids de C11 vaut 1, C11 rend "
                    f"{_pct(auto['share'])} de la baisse quelle que soit la valeur d'un emploi "
                    f"et l'élasticité de C2 : le rejeu doit y redonner "
                    f"{_fr(1 - auto['share'], sign=False)} fois l'écart de la courbe, et ses "
                    f"coûts les siens. Il {given} : l'écart le plus grand vaut "
                    f"{_fr(control['share'] * 100, 6, sign=False)} pt sur les coins et "
                    f"{_fr(control['eur'], 0, sign=False)} € sur les coûts. {indices}",
                "", f"**Ce que ce chiffre ne compte pas.** {MESURE_LEAVES_OUT}"
                    f"{replay.leaves_out}"]
    return out


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


# --------------------------------------------------------------------------- #
# θ = 0 and θ = 1, read off the box (D-274)
# --------------------------------------------------------------------------- #
#: Δb at θ is said between Δb at θ = 0 and θ = 1, or the same at both, to this share of
#: GDP: the corners and the value at θ come from runs of the chain apart.
THETA_SLACK = 1e-12


def diagonal(evaluation: dict[str, Any]) -> tuple[float, float]:
    """Δb at θ = 0 and at θ = 1, aged view: the corner of the box where every row is at 0,
    and the one where every row is at 1. The box moves every θ the aged view reads
    (D-274); a box of one corner, θ as asked, is a bundle nothing moves. Corners that do
    not all name the same rows, or without one of each, are refused rather than read."""
    from impots.predictif.exploration import NO_KEY

    if [label for label, _ in evaluation["corners"]] == [NO_KEY]:
        value = evaluation["corners"][0][1]
        return value, value
    corners = [(_settings(label), value) for label, value in evaluation["corners"]]
    rows = {frozenset(key for key, _ in settings) for settings, _ in corners}
    where = f"le paquet {json.dumps(evaluation['knobs'], sort_keys=True)}"
    if len(rows) != 1 or not next(iter(rows)):
        raise EtudeError(f"{where} : ses coins ne nomment pas tous les mêmes lignes de la "
                         f"boîte θ, et Δb à θ = 0 ou à θ = 1 ne s'y lit pas. Refusé plutôt "
                         f"que lu.")
    at = []
    for side in ("0", "1"):
        found = [value for settings, value in corners
                 if all(v == side for _, v in settings)]
        if len(found) != 1:
            raise EtudeError(f"{where} : sa boîte θ a {len(found)} coin(s) où chaque ligne "
                             f"vaut {side}, et non un. Refusé plutôt que lu.")
        at.append(found[0])
    return at[0], at[1]


def rendered(etudes: list[dict[str, Any]], complements: list[dict[str, Any]] | tuple = (),
             courbe: list[dict[str, Any]] | tuple = (),
             phase11: dict[str, Any] | None = None) -> list[tuple[str, dict[str, Any]]]:
    """Every report the page renders, in its order, with the name the θ section gives it."""
    out = [(e["instrument"].label, e["report"]) for e in etudes]
    out += [(f"{c['instrument'].label}, en complément hors préenregistrement", c["report"])
            for c in complements]
    out += [(e["instrument"].label, e["report"]) for e in courbe]
    if phase11:
        out += [(e["instrument"].label, e["report"]) for e in phase11["entries"]]
        if phase11.get("salaires"):
            salaires = phase11["salaires"]
            out.append((f"{salaires['instrument'].label}, avec les salaires déplacés",
                        salaires["report"]))
    for menu, field, how in ((AUTOFINANCEMENT_MENU, "autofinancement",
                              "avec son autofinancement"),
                             (MESURE_MENU, "mesure", "avec l'autofinancement réconcilié")):
        for replay in menu:
            for e in courbe:
                if e["instrument"].key == replay.key and e.get(field):
                    out.append((f"{e['instrument'].label}, rejoué {how} ({replay.entry})",
                                e[field]["report"]))
    return out


def _frame(report: dict[str, Any]) -> tuple[Any, list[str]]:
    return report["hypotheses"]["theta"], [s["persistence"] for s in report["searches"]]


def theta_rows(etudes: list[dict[str, Any]], complements: list[dict[str, Any]] | tuple = (),
               courbe: list[dict[str, Any]] | tuple = (),
               phase11: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """For each search the page renders, Δb at θ = 0, at the study's θ and at θ = 1, bundle
    by bundle. A report run at another θ, or under other persistences, than the study's
    would put its figures in the wrong column, and is refused."""
    frame = _frame(etudes[0]["report"])
    rows = []
    for name, report in rendered(etudes, complements, courbe, phase11):
        if _frame(report) != frame:
            raise EtudeError(f"{name} : son θ et ses persistances, {_frame(report)}, ne "
                             f"sont pas ceux de l'étude, {frame} ; ses Δb ne se lisent pas "
                             f"dans les mêmes colonnes. Refusé.")
        for search in report["searches"]:
            at = [diagonal(e) for e in search["evaluations"]]
            rows.append({"name": name, "persistence": search["persistence"],
                         "absent": loop_absent(search), "zero": [low for low, _ in at],
                         "theta": [e["delta_aged"] for e in search["evaluations"]],
                         "one": [high for _, high in at]})
    return rows


def _span(values: list[float]) -> str:
    return f"{_fr(min(values) * 100)} à {_pt(max(values))}"


def _lower(text: str) -> str:
    return text[0].lower() + text[1:]


def _falls(rows: list[dict[str, Any]], column: str, side: str, target: float,
           persistences: dict[str, str]) -> list[str]:
    found = [(row, sum(x <= target for x in row[column])) for row in rows]
    found = [(row, n) for row, n in found if n]
    if not found:
        return [f"**À θ = {side}**, la dette ne baisse à aucun paquet, sous aucune "
                f"persistance."]
    out = [f"**À θ = {side}**, la dette baisse :", ""]
    for persistence, label in persistences.items():
        here = [f"{_lower(row['name'])} ({n} paquet{'s' if n > 1 else ''} sur "
                f"{len(row[column])})" for row, n in found if row["persistence"] == persistence]
        if here:
            out.append(f"- {label} : " + " ; ".join(here) + ".")
    return out


def _listing(rows: list[dict[str, Any]], persistences: dict[str, str]) -> list[str]:
    """The renders named, those of every persistence first, then persistence by persistence."""
    under: dict[str, set[str]] = {}
    for row in rows:
        under.setdefault(row["name"], set()).add(row["persistence"])
    every = [name for name, these in under.items() if these == set(persistences)]
    out = [f"- Sous chaque persistance : {' ; '.join(_lower(n) for n in every)}."] if every else []
    for persistence, label in persistences.items():
        some = [name for name, these in under.items()
                if name not in every and persistence in these]
        if some:
            out.append(f"- {label} : {' ; '.join(_lower(n) for n in some)}.")
    return out


def _theta_section(rows: list[dict[str, Any]], persistences: dict[str, str], target: float,
                   target_year: int, theta: str) -> list[str]:
    out = ["", "## La réponse à θ = 0 et à θ = 1", "",
           "Sans passe nouvelle. À chaque paquet, la boîte θ met à 0 ou à 1 chaque ligne que "
           "le paquet revendique, et le multiplicateur quand la boucle tourne. Son coin où "
           "toutes valent 0 est Δb à θ = 0, celui où toutes valent 1 est Δb à θ = 1 : chaque "
           "ligne qu'un canal lit répond aux mêmes boutons que les autres lignes de son canal, "
           "et la chaîne ne lit pas d'autre θ que celui du multiplicateur (D-274). Chaque case "
           f"va du plus bas des Δb {target_year} des paquets du rendu à son plus haut, en "
           "points de PIB, vue vieillie."]
    for persistence, label in persistences.items():
        out += ["", f"**{label}.**", "",
                f"| Rendu | Δb {target_year} à θ = 0 | à θ = {theta} | à θ = 1 "
                f"| Paquets où la dette baisse, à θ = 0, {theta}, 1 |",
                "|---|---|---|---|---|"]
        for row in rows:
            if row["persistence"] == persistence:
                counts = ", ".join(str(sum(x <= target for x in row[column]))
                                   for column in ("zero", "theta", "one"))
                out.append(f"| {row['name']}{' †' if row['absent'] else ''} "
                           f"| {_span(row['zero'])} | {_span(row['theta'])} "
                           f"| {_span(row['one'])} | {counts} sur {len(row['theta'])} |")
    if any(row["absent"] for row in rows):
        out += ["", "† La boucle PIB → recettes est absente pour ce rendu, non nulle : voir ce "
                    "qui manque à la chaîne dans sa section."]
    for column, side in (("zero", "0"), ("theta", theta), ("one", "1")):
        out += ["", *_falls(rows, column, side, target, persistences)]

    flat = [row for row in rows
            if all(abs(a - b) <= THETA_SLACK for a, b in zip(row["zero"], row["one"], strict=True))]
    if flat:
        out += ["", f"Δb est le même à θ = 0, à θ = {theta} et à θ = 1, à chaque paquet :", ""]
        out += _listing(flat, persistences)
    outside = [row for row in rows
               if any(not min(a, b) - THETA_SLACK <= x <= max(a, b) + THETA_SLACK
                      for a, x, b in zip(row["zero"], row["theta"], row["one"], strict=True))]
    if outside:
        out += ["", f"Δb à θ = {theta} n'est pas entre Δb à θ = 0 et Δb à θ = 1, à un paquet "
                    f"au moins : leurs lignes ne poussent pas toutes du même côté.", ""]
        out += _listing(outside, persistences)
    else:
        out += ["", f"À chaque paquet, Δb à θ = {theta} est entre Δb à θ = 0 et Δb à θ = 1."]
    out += ["", f"**Ce que cette lecture ne dit pas.** La vue figée n'a pas de coins : elle "
                f"n'est lue qu'à θ = {theta}, comme les indices hors de la chaîne. θ = 0 et "
                f"θ = 1 sont deux coins de la boîte, ceux d'un θ commun à toutes ses lignes ; "
                f"la boîte, qui les croise, en reste l'étendue. Aucune passe n'a tourné : "
                f"chaque chiffre vient d'un rapport commité, au commit qu'il nomme."]
    return out


# --------------------------------------------------------------------------- #
# the study on the annual path (D-275, D-276)
# --------------------------------------------------------------------------- #
#: The scenarios under `etude/`, the reports under `reports/` (D-275).
ANNUEL = "annuel"
ANNUEL_REPORTS = "etude_annuel"
#: The population year the command ages from, its default, which the launcher keeps.
ANNUEL_BASE_YEAR = 2024
#: The commit of the preregistration (D-275), whose passes found the defect of D-276.
ANNUEL_PREREGISTERED = "46c0a5ebef92bf6c49d1db122c686bf21e5f214c"
_LAUNCHER: list[Any] = []


# --------------------------------------------------------------------------- #
# the frozen view, priced again on D-276's fix (D-278)
# --------------------------------------------------------------------------- #
#: The study's explorations whose box reads marginal rates, replayed on the fix, under
#: this directory of `reports/` (D-278).
VUE_FIGEE = "vue_figee"
_VUE_FIGEE_LAUNCHER: list[Any] = []


def vue_figee_launcher() -> Any:
    """`scripts/vue_figee.py`, which chose the replays: the page reads its menu and its
    validation of a request through it, never through a copy of its logic."""
    if not _VUE_FIGEE_LAUNCHER:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            VUE_FIGEE, Path(__file__).resolve().parent / f"{VUE_FIGEE}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _VUE_FIGEE_LAUNCHER.append(module)
    return _VUE_FIGEE_LAUNCHER[0]


def _bundles(report: dict[str, Any]) -> list[tuple[str, list[dict[str, float]]]]:
    return [(s["persistence"], [e["knobs"] for e in s["evaluations"]])
            for s in report["searches"]]


def vue_figee_control(name: str, report: dict[str, Any],
                      study: dict[str, Any]) -> dict[str, float]:
    """The aged view, which did not read the defect, against the study's: its costs in
    both views, and Δb at θ and at each corner."""
    eur, aged = [0.0], [0.0]
    for new, old in zip(report["searches"], study["searches"], strict=True):
        for a, b in zip(new["evaluations"], old["evaluations"], strict=True):
            eur += [abs(a["cost_aged_eur"] - b["cost_aged_eur"]),
                    abs(a["cost_frozen_eur"] - b["cost_frozen_eur"])]
            aged.append(abs(a["delta_aged"] - b["delta_aged"]))
            corners = dict(b["corners"])
            if sorted(corners) != sorted(label for label, _ in a["corners"]):
                raise EtudeError(f"{name} : sa boîte ne porte pas les coins de l'étude, pour "
                                 f"{a['knobs']}.")
            aged += [abs(value - corners[label]) for label, value in a["corners"]]
    return {"eur": max(eur), "aged": max(aged)}


def _carry(report: dict[str, Any], annual: dict[str, Any] | None) -> float | None:
    """How far the nearest bundle's replayed frozen Δb is from the first year the annual
    path carries in the frozen view, priced on the same fix; None without the path."""
    if annual is None:
        return None
    return max(abs(_nearest(search)["delta_frozen"] - path["first_year"]["figee"]["theta"])
               for search, path in zip(report["searches"],
                                       annual["report"]["theta_box"]["paths"], strict=True))


def load_vue_figee(etudes: list[dict[str, Any]],
                   reports: Path = REPORTS) -> dict[str, dict[str, Any]] | None:
    """The study's explorations whose box reads the marginal rates, replayed as they are on
    D-276's fix (D-278), checked: one per instrument the launcher's menu names, nothing
    beside them; each the study's request, its bundles under its persistences, its box's
    corners; of one commit, not the study's, whose code it priced; and where it ran. Without
    them, the replay is preregistered and not yet played: no section."""
    out_dir = reports / VUE_FIGEE
    if not out_dir.exists():
        return None
    run = vue_figee_launcher()
    menu = run.menu(reports)
    there = sorted(p.name for p in out_dir.glob("exploration_*.json"))
    wanted = sorted(f"exploration_etude_{key}.json" for key in menu)
    if there != wanted:
        raise EtudeError(f"`reports/{VUE_FIGEE}/` porte {there} : un rapport par exploration "
                         f"de l'étude dont la boîte lit les taux marginaux, ni plus ni moins, "
                         f"{wanted}.")
    commits: set[str] = set()
    out: dict[str, dict[str, Any]] = {}
    for key in menu:
        entry = next(e for e in etudes if e["instrument"].key == key)
        study = entry["report"]
        path = out_dir / f"exploration_etude_{key}.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        if run._validated(report["request"]) != run._validated(study["request"]):
            raise EtudeError(f"{path.name} n'a pas rejoué la requête de l'étude, telle "
                             f"qu'elle l'a jouée.")
        if not report.get("commit"):
            raise EtudeError(f"{path.name} ne nomme pas le commit qui l'a chiffré.")
        if not (report.get("where") or "").strip():
            raise EtudeError(f"{path.name} ne dit pas où ses passes ont tourné.")
        if report["commit"] == study["commit"]:
            raise EtudeError(f"{path.name} a tourné sur le commit de l'étude, "
                             f"`{study['commit'][:7]}`, avant la correction de D-276.")
        if _bundles(report) != _bundles(study):
            raise EtudeError(f"{path.name} ne chiffre pas les paquets de l'étude, sous ses "
                             f"persistances.")
        commits.add(report["commit"])
        out[key] = {"instrument": entry["instrument"], "report": report, "study": study,
                    "control": vue_figee_control(path.name, report, study),
                    "carry": _carry(report, entry.get("annuel"))}
    if len(commits) != 1:
        raise EtudeError(f"la vue figée a été rejouée sur {sorted(commits)} : préenregistrée "
                         f"ensemble, elle tourne sur un seul commit.")
    return out


def _alone(report: dict[str, Any], target: float) -> tuple[int, int]:
    """The readings, one bundle under one persistence, whose frozen view alone holds the
    target, and how many there are."""
    readings = [e for s in report["searches"] for e in s["evaluations"]]
    return (sum(e["delta_aged"] > target and e["delta_frozen"] <= target for e in readings),
            len(readings))


def _vue_figee_section(entries: list[dict[str, Any]], target: float, first_year: int,
                       target_year: int, theta: str) -> list[str]:
    head = entries[0]["report"]
    labels = ", ".join(_lower(e["instrument"].label) for e in entries)
    eur = max(e["control"]["eur"] for e in entries)
    aged = max(e["control"]["aged"] for e in entries)
    carry = [e["carry"] for e in entries if e["carry"] is not None]
    out = ["", "## La vue figée, rechiffrée", "",
           "Jusqu'à D-276, la vue figée prenait la clé des taux marginaux de la vue vieillie. "
           "L'explorateur chiffre la vue vieillie d'abord : sa vue figée lisait donc les taux "
           "du cadre vieilli, avec l'assiette du cadre figé. Seuls C1, la réponse du revenu "
           "imposable, et C7, l'offre de travail, lisent ces taux. Les explorations de "
           f"l'étude dont la boîte porte une de leurs lignes, pour {labels}, ont été rejouées "
           "telles quelles sur la correction. Le rejeu a été préenregistré dans D-278 avant "
           f"ses passes, et `scripts/{VUE_FIGEE}.py` l'a lancé. Les rapports ont tourné sur le "
           f"commit `{head['commit']}`, le {head['computed']}, ici : {head['where']}. Ils sont "
           f"sous `reports/{VUE_FIGEE}/` ; ceux de l'étude ne bougent pas, et les tables plus "
           "haut gardent leurs chiffres.",
           "",
           "**Le contrôle.** La vue vieillie ne lisait pas le défaut. Rejouée, elle se compare "
           f"à l'étude. Ses coûts s'en écartent de {_fr(eur, 0, sign=False)} € au plus, dans "
           f"les deux vues, et Δb à θ et à chaque coin, en vue vieillie, de "
           f"{_fr(aged * 100, 6, sign=False)} point au plus."
           + (f" Pour le paquet le plus proche, la vue figée rechiffrée est celle que le "
              f"chemin annuel reporte sur sa passe de {first_year}, à "
              f"{_fr(max(carry) * 100, 6, sign=False)} point près." if carry else ""),
           "", f"**Δb {target_year} à θ = {theta}, vue figée.**", "",
           "| Instrument | Paquet | Persistance | Dans l'étude | Rechiffrée | Écart |",
           "|---|---|---|---|---|---|"]
    for e in entries:
        instrument = e["instrument"]
        for new, old in zip(e["report"]["searches"], e["study"]["searches"], strict=True):
            for a, b in zip(new["evaluations"], old["evaluations"], strict=True):
                out.append(f"| {instrument.label} "
                           f"| {instrument.show(b['knobs'][instrument.knob])} "
                           f"| {_lower(old['persistence_label'])} | {_pt(b['delta_frozen'])} "
                           f"| {_pt(a['delta_frozen'])} "
                           f"| {_fr((a['delta_frozen'] - b['delta_frozen']) * 100, 3)} pt |")
    replayed = [_alone(e["report"], target) for e in entries]
    studied = [_alone(e["study"], target) for e in entries]
    n_new, m = sum(n for n, _ in replayed), sum(k for _, k in replayed)
    n_old = sum(n for n, _ in studied)
    out += ["", "La vue figée n'entre dans aucun verdict de la cible : elle dit seulement si "
                "un paquet la tiendrait dans la vue figée seule. Rechiffrée, la vue figée "
                f"seule tiendrait la cible à {n_new or 'aucune'} des {m} lectures d'un paquet "
                f"sous une persistance ; dans l'étude, à {n_old or 'aucune'}."]
    return out


def launcher() -> Any:
    """`scripts/etude_annuelle.py`, which built the scenarios: the page reads them back
    through it, never through a copy of its logic."""
    if not _LAUNCHER:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "etude_annuelle", Path(__file__).resolve().parent / "etude_annuelle.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _LAUNCHER.append(module)
    return _LAUNCHER[0]


def _nearest(search: dict[str, Any]) -> dict[str, Any]:
    return next(e for e in search["evaluations"] if e["knobs"] == search["closest"]["knobs"])


def _rows(evaluation: dict[str, Any]) -> list[str]:
    return [part.split(" = ")[0] for part in evaluation["corners"][0][0].split(", ")]


def annual_frame(report: dict[str, Any], study: dict[str, Any]) -> list[str]:
    """The fields of the study's frame the annual report does not hold, by name."""
    from impots import uprating as up
    from impots.dette.scenarios import GrowthScenario
    from impots.predictif import annuel as annuel_module

    h, request = study["hypotheses"], study["request"]
    first = study["start"]["year"] + 1
    years = list(range(first, first + h["horizon"]))
    uprating = annuel_module.uprating_for(
        GrowthScenario(h["growth_name"], request["growth"]["real"],
                       request["growth"]["prices"]),
        wage=h["uprating"]["wage"], source=h["uprating"]["source"],
        base_year=ANNUEL_BASE_YEAR)
    held = {
        "reference": report["reference"] == "reconduit",
        "spending_name": report["spending_name"] == h["spending_name"],
        "growth_name": report["growth_name"] == h["growth_name"],
        "rate_name": report["rate_name"] == h["rate_name"],
        "years": [y["year"] for y in report["years"]] == years,
        "theta": (not h["theta"]["rows"]
                  and set(report["theta"].values()) == {h["theta"]["common"]}),
        "behavioural": report["behavioural"] == h["behavioural"],
        "macro": report["macro"] == h["macro"],
        "persistences": [p["persistence"] for p in report["side_by_side"]]
        == [s["persistence"] for s in study["searches"]],
        "uprating_note": report["uprating_note"] == up.caveat(years[-1], uprating),
    }
    return [name for name, ok in held.items() if not ok]


def annual_control(report: dict[str, Any], reference: dict[str, Any]) -> dict[str, float]:
    """The first year carried on the annual path's own pass, against the bundle as the
    page reads it: its costs; Δb at θ and at each corner in the aged view, a corner of the
    annual box read at the one of the reference that sets its rows alike; Δb at θ in the
    frozen view, apart, since the frozen view of a reference priced before D-276 read its
    aged view's marginal rates (D-275, 1). And how far the rows the reference did not have
    move Δb: the largest gap between two corners that differ on those rows only."""
    first = report["years"][0]
    rows = _rows(_nearest(reference["searches"][0]))
    eur: list[float] = []
    aged: list[float] = []
    frozen: list[float] = []
    extra: list[float] = [0.0]
    for search, path in zip(reference["searches"], report["theta_box"]["paths"],
                            strict=True):
        evaluation = _nearest(search)
        eur += [abs(first["mechanical_aged_eur"] - evaluation["cost_aged_eur"]),
                abs(first["mechanical_frozen_eur"] - evaluation["cost_frozen_eur"])]
        carried = path["first_year"]
        aged.append(abs(carried["vieillie"]["theta"] - evaluation["delta_aged"]))
        frozen.append(abs(carried["figee"]["theta"] - evaluation["delta_frozen"]))
        corners = {_on(label, rows): value for label, value in evaluation["corners"]}
        by_shared: dict[tuple[tuple[str, str], ...], list[float]] = {}
        for label, value in carried["vieillie"]["corners"]:
            aged.append(abs(value - corners[_on(label, rows)]))
        for reading in ("every_year", "first_year"):
            for one in path[reading].values():
                by_shared.clear()
                for label, value in one["corners"]:
                    by_shared.setdefault(_on(label, rows), []).append(value)
                extra += [max(values) - min(values) for values in by_shared.values()]
    return {"eur": max(eur), "aged": max(aged), "frozen": max(frozen), "extra": max(extra)}


def _on(label: str, rows: list[str]) -> tuple[tuple[str, str], ...]:
    """A corner's settings on `rows` alone, in their order."""
    settings = dict(part.split(" = ") for part in label.split(", "))
    return tuple((row, settings[row]) for row in rows)


def load_annuel(etudes: list[dict[str, Any]], requests: Path = REQUESTS,
                reports: Path = REPORTS,
                complements: list[dict[str, Any]] | tuple = ()
                ) -> dict[str, dict[str, Any]] | None:
    """The study's nearest bundles priced every year (D-275), checked: the scenarios the
    launcher builds from the study's reports, nothing beside them; their reports, of one
    commit whose `src/` they priced, in the study's frame, with a box that has at least
    the rows of the bundle as the page reads it; and their control, the first year carried
    on the same pass against that reading. The page reads a bundle off its complement
    where it has one, the study's bundle replayed under another macro classing (D-239);
    off the study elsewhere. Without reports, the scenarios are preregistered and not yet
    played: no section."""
    from impots.api.schemas import PredictifReportResponse

    out_dir = reports / ANNUEL_REPORTS
    if not out_dir.exists():
        return None
    run = launcher()
    names = {e["instrument"].key: run.name(e["instrument"].key) for e in etudes}
    scenarios = requests / ANNUEL
    there = sorted(p.name for p in scenarios.glob("*.json")) if scenarios.exists() else []
    if there != sorted(f"{n}.json" for n in names.values()):
        raise EtudeError(f"etude/{ANNUEL}/ porte {there} : le chemin annuel rejoue un paquet "
                         f"par instrument de l'étude, ni plus ni moins.")
    played = sorted(p.name for p in out_dir.glob("*.json"))
    if played != sorted(f"predictif_{n}.json" for n in names.values()):
        raise EtudeError(f"reports/{ANNUEL_REPORTS}/ porte {played} : un rapport par "
                         f"scénario du chemin annuel, ni plus ni moins.")
    out, commits = {}, set()
    for entry in etudes:
        key, study = entry["instrument"].key, entry["report"]
        name = names[key]
        scenario = json.loads((scenarios / f"{name}.json").read_text(encoding="utf-8"))
        if scenario != run.scenario(key, reports):
            raise EtudeError(f"etude/{ANNUEL}/{name}.json n'est pas le paquet de l'étude que "
                             f"le lanceur construit : un scénario retouché, ou un rapport de "
                             f"l'étude rejoué sans lui.")
        path = out_dir / f"predictif_{name}.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        PredictifReportResponse.model_validate(report)
        if report["scenario"] != name:
            raise EtudeError(f"{path.name} chiffre « {report['scenario']} », pas {name}.")
        if not report.get("commit") or report.get("dirty") is not False:
            raise EtudeError(f"{path.name} ne nomme pas un commit dont il a chiffré le code "
                             f"(commit {report.get('commit')}, src/ modifié : "
                             f"{report.get('dirty')}).")
        if not (report.get("where") or "").strip():
            raise EtudeError(f"{path.name} ne dit pas où ses passes ont tourné.")
        missing = annual_frame(report, study)
        if missing:
            raise EtudeError(f"{path.name} n'a pas tourné dans le cadre de l'étude : "
                             f"{missing} diffèrent.")
        complement = next((c for c in complements
                           if c["instrument"].key == entry["instrument"].key), None)
        reference = complement["report"] if complement else study
        rows = _rows(_nearest(reference["searches"][0]))
        box = report.get("theta_box")
        if box is None or not set(rows) <= set(box["rows"]):
            raise EtudeError(f"{path.name} : sa boîte θ ne porte pas les lignes de la "
                             f"lecture de la page, {rows}.")
        commits.add(report["commit"])
        out[key] = {"instrument": entry["instrument"], "report": report, "study": study,
                    "reference": reference, "complement": complement is not None,
                    "extra_rows": [row for row in box["rows"] if row not in rows],
                    "control": annual_control(report, reference)}
    if len(commits) != 1:
        raise EtudeError(f"le chemin annuel a tourné sur {sorted(commits)} : préenregistré "
                         f"ensemble, il tourne sur un seul commit.")
    return out


def _ratio(value: float, reference: float) -> str:
    return _fr(value / reference, 3, sign=False) if abs(reference) > 1e-9 else "—"


def _box_row(name: str, reading: dict[str, Any], target: float) -> str:
    corners = reading["corners"]
    low, high = (min(v for _, v in corners), max(v for _, v in corners))
    return (f"| {name} | {_pt(diagonal({'knobs': {}, 'corners': corners})[0])} "
            f"| {_pt(reading['theta'])} | {_pt(diagonal({'knobs': {}, 'corners': corners})[1])} "
            f"| [{_pt(low)} ; {_pt(high)}] "
            f"| {_corners({'corners': corners}, target)} |")


def _references(entries: list[dict[str, Any]]) -> str:
    """Which reading of each bundle the page compares the annual path to."""
    studies = [e for e in entries if not e["complement"]]
    complements = [e for e in entries if e["complement"]]
    parts = []
    if studies:
        commit = studies[0]["reference"]["commit"]
        parts.append(f"l'étude, au commit `{commit[:7]}`, pour "
                     + ", ".join(_lower(e["instrument"].label) for e in studies))
    for e in complements:
        parts.append(f"son complément, au commit `{e['reference']['commit'][:7]}`, pour "
                     f"{_lower(e['instrument'].label)} : la page le lit sous le classement du "
                     f"choc macro que le complément a rejoué")
    return "La référence de chaque paquet est sa dernière lecture sur la page : " + " ; ".join(
        parts) + "."


def _annuel_section(entries: list[dict[str, Any]], target: float, theta: str) -> list[str]:
    head = entries[0]["report"]
    years = [y["year"] for y in head["years"]]
    first, last = years[0], years[-1]
    study = entries[0]["study"]
    growth = study["request"]["growth"]
    nominal = (1 + growth["real"]) * (1 + growth["prices"])
    eur = max(e["control"]["eur"] for e in entries)
    aged = max(e["control"]["aged"] for e in entries)
    frozen = max(e["control"]["frozen"] for e in entries)
    out = ["", "## Le chemin annuel : chaque année chiffrée", "",
           f"L'étude chiffre la première année et reporte les suivantes en part de PIB. Le "
           f"chemin annuel, `impots predictif`, chiffre chaque année de {first} à {last}, "
           f"sur la population vieillie l'année qu'il chiffre et sous la loi reconduite. "
           f"Pour chaque instrument, il rejoue le paquet que la page lit déjà, le plus proche "
           f"de la cible, dans le cadre de l'étude champ pour champ. Il a été préenregistré "
           f"dans D-275 avant ses passes : les scénarios sont sous `etude/{ANNUEL}/`, "
           f"construits depuis les rapports de l'étude par `scripts/etude_annuelle.py`, et les "
           f"rapports sous `reports/{ANNUEL_REPORTS}/`. Ils ont tourné sur le commit "
           f"`{head['commit']}`, le {head['computed']}, ici : {head['where']}."
           + ("" if head["commit"] == ANNUEL_PREREGISTERED else
              f" Ce n'est pas le commit du préenregistrement, `{ANNUEL_PREREGISTERED[:7]}` : "
              f"ses passes ont trouvé un défaut, les deux vues partageant leurs taux "
              f"marginaux, et le chemin a tourné de nouveau sur sa correction, sans rien "
              f"changer d'autre (D-276)."),
           "",
           f"Chaque rapport donne aussi, sur la passe de {first}, la première année seule "
           f"reportée comme le fait l'explorateur. L'écart entre ce report et chaque année "
           f"chiffrée est celui de la convention, sur un même code ; l'écart entre ce report "
           f"et sa référence est celui du code depuis le commit de la référence.",
           "",
           _references(entries),
           "",
           f"**Le contrôle.** Sur la passe de {first}, la première année reportée se compare "
           f"à sa référence. Ses coûts s'en écartent de {_fr(eur, 0, sign=False)} € au plus ; "
           f"en vue vieillie, Δb à θ et à chaque coin, de "
           f"{_fr(aged * 100, 6, sign=False)} point au plus ; en vue figée, Δb à θ, de "
           f"{_fr(frozen * 100, 6, sign=False)} point au plus. La vue figée d'une référence "
           f"chiffrée avant D-276 lisait les taux marginaux de sa vue vieillie : son écart "
           f"est aussi celui-là."]
    for view, field, title in (("vieillie", "delta_aged", "vue vieillie"),
                               ("figee", "delta_frozen", "vue figée")):
        out += ["", f"**Δb {last} à θ = {theta}, {title}.**", "",
                "| Instrument | Paquet | Persistance | La référence | Reporté, même passe "
                "| Chaque année | Chaque année / reporté |",
                "|---|---|---|---|---|---|---|"]
        for e in entries:
            instrument = e["instrument"]
            for search, path in zip(e["reference"]["searches"],
                                    e["report"]["theta_box"]["paths"], strict=True):
                nearest = _nearest(search)
                carried = path["first_year"][view]["theta"]
                every = path["every_year"][view]["theta"]
                out.append(f"| {instrument.label} "
                           f"| {instrument.show(nearest['knobs'][instrument.knob])} "
                           f"| {_lower(search['persistence_label'])} | {_pt(nearest[field])} "
                           f"| {_pt(carried)} | {_pt(every)} | {_ratio(every, carried)} |")
    for e in entries:
        instrument, report = e["instrument"], e["report"]
        nearest = _nearest(e["reference"]["searches"][0])
        rows = report["years"]
        growth_share = {v: (rows[-1][f] / rows[0][f]) / nominal ** (last - first)
                        if rows[0][f] else None
                        for v, f in (("vieillie", "mechanical_aged_eur"),
                                     ("figee", "mechanical_frozen_eur"))}
        out += ["", f"### {instrument.label}, chaque année chiffrée", "",
                f"Le paquet : {instrument.show(nearest['knobs'][instrument.knob])}. Son coût, "
                f"vue vieillie, vaut {_md(rows[0]['mechanical_aged_eur'])} en {first} et "
                f"{_md(rows[-1]['mechanical_aged_eur'])} en {last} ; vue figée, "
                f"{_md(rows[0]['mechanical_frozen_eur'])} puis "
                f"{_md(rows[-1]['mechanical_frozen_eur'])}. Rapportée au PIB de la "
                f"référence, sa part de {last} vaut "
                f"{_fr(growth_share['vieillie'], 3, sign=False)} fois celle de {first} en vue "
                f"vieillie, et {_fr(growth_share['figee'], 3, sign=False)} fois en vue figée. "
                f"Reportée sur la passe de {first}, la première année s'écarte de sa "
                f"référence de {_fr(e['control']['aged'] * 100, 6, sign=False)} point au plus "
                f"en vue vieillie, à θ et à chaque coin, et de "
                f"{_fr(e['control']['frozen'] * 100, 6, sign=False)} point en vue figée, "
                f"à θ."]
        if e["extra_rows"]:
            out += ["", f"Sa boîte porte aussi {', '.join(f'`{r}`' for r in e['extra_rows'])}, "
                        f"que la référence n'avait pas : à leurs coins, Δb ne bouge pas de plus "
                        f"de {_fr(e['control']['extra'] * 100, 6, sign=False)} point."]
        for search, path in zip(e["reference"]["searches"], report["theta_box"]["paths"],
                                strict=True):
            every = path["every_year"]["vieillie"]
            n, _ = falling({"corners": every["corners"]}, target)
            falls = every["theta"] <= target
            out += ["", f"**{search['persistence_label']}.** Chaque année chiffrée, la dette "
                        f"{'baisse' if falls else 'ne baisse pas'} en {last} à θ = {theta}, "
                        f"vue vieillie ; elle "
                        f"{f'baisse à {n}' if n else 'ne baisse à aucun'} des "
                        f"{len(every['corners'])} coins de la "
                        f"boîte θ.", "",
                    f"| Lecture, vue vieillie | Δb {last} à θ = 0 | à θ = {theta} | à θ = 1 "
                    f"| Boîte θ | Coins où la dette baisse |",
                    "|---|---|---|---|---|---|",
                    _box_row(f"La référence (`{e['reference']['commit'][:7]}`), reportée",
                             {"theta": _nearest(search)["delta_aged"],
                              "corners": _nearest(search)["corners"]}, target),
                    _box_row("Reportée, sur la passe du chemin annuel",
                             path["first_year"]["vieillie"], target),
                    _box_row("Chaque année chiffrée", every, target)]
            frozen = path["every_year"]["figee"]
            out += ["", f"Vue figée, chaque année chiffrée : {_pt(frozen['theta'])} à θ = "
                        f"{theta}, de {_pt(min(v for _, v in frozen['corners']))} à "
                        f"{_pt(max(v for _, v in frozen['corners']))} aux coins ; reportée, "
                        f"{_pt(path['first_year']['figee']['theta'])}."]
    out += ["", "**Ce que ce chemin ne dit pas.**", "",
            "- La loi reconduite garde à sa dernière valeur connue ce que la loi revoit chaque "
            "année. Le chemin chiffre « cette loi, sur la France d'aujourd'hui, avec l'argent "
            "de demain » (F3 M2), non une prévision : son écart au report est pour partie "
            "celui de cette convention.",
            "- La population vieillie ne change ni de structure, ni de poids, ni d'âge.",
            "- Les indices hors de la chaîne ne sont pas sur le chemin annuel (D-236).",
            "- Le report est la convention de l'explorateur ; ni l'un ni l'autre n'est le vrai "
            "chemin, et leur écart dit ce que la convention de l'étude pèse."]
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
               f"salariés (D-259), et prêtait à chacun le changement du coût du travail de "
               f"son ménage (D-261). C2 n'entre ni dans les recettes ni dans la dette, et le "
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
    if phase11 and phase11.get("salaires"):
        out += _salaires_section(phase11["salaires"], target, first_year, target_year,
                                 theta)
    replayed = {e["instrument"].key: e["autofinancement"] for e in courbe
                if e.get("autofinancement")}
    for replay in AUTOFINANCEMENT_MENU:
        if replay.key in replayed:
            out += _autofinancement_section(replayed[replay.key], target, first_year,
                                            target_year, theta)
    measured = [e for replay in MESURE_MENU for e in courbe
                if e["instrument"].key == replay.key and e.get("mesure")]
    if measured:
        out += _mesure_section(measured, target, first_year, target_year, theta)
    out += _theta_section(theta_rows(etudes, complements, courbe, phase11),
                          {s["persistence"]: s["persistence_label"]
                           for s in report["searches"]}, target, target_year, theta)
    annual = [e["annuel"] for e in etudes if e.get("annuel")]
    if annual:
        out += _annuel_section(annual, target, theta)
    figee = [e["vue_figee"] for e in etudes if e.get("vue_figee")]
    if figee:
        out += _vue_figee_section(figee, target, first_year, target_year, theta)
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
