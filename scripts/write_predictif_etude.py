#!/usr/bin/env python3
"""Render docs/PREDICTIF_ETUDE.md — l'étude de la phase 10 (PHASE10_SPEC §5, D-237, D-238).

« Quelles baisses d'impôt font baisser la dette en 2035, et pour quels θ ? »

PRÉENREGISTRÉE. Les requêtes sont sous `etude/`, une par instrument du menu, commitées
avant toute passe avec le pronostic de D-237. Chacune est jouée par `impots exploration`,
qui écrit `reports/exploration_etude_<instrument>.json` en nommant le commit qui l'a
chiffrée et où ses passes ont tourné. Ce script refuse un rapport qui n'a pas joué la
requête commitée, un instrument sans rapport, des rapports de deux commits, et un rapport
qui ne dit pas où il a tourné.

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
#: What a round computes, as against what it reports about it.
FIGURES = ("knobs", "cost_aged_eur", "cost_frozen_eur", "delta_aged", "delta_frozen",
           "corners", "corner_low", "corner_high", "meets_target")


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
    return out


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


def _value(row: dict[str, Any], key: str) -> str:
    value = row["values"][key]
    share = row["unit"].startswith("pts d")
    text = _fr(value * 100, 3) + " pt" if share else _number(value)
    box = (row.get("box") or {}).get(key)
    if box is not None and box[0] != box[1]:
        text += f" [{_number(box[0])} ; {_number(box[1])}]"
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


def render(etudes: list[dict[str, Any]]) -> str:
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
    for entry in etudes:
        instrument, r = entry["instrument"], entry["report"]
        evaluations = r["searches"][0]["evaluations"]
        costs = [e["cost_aged_eur"] for e in evaluations]
        grid = ", ".join(instrument.show(e["knobs"][instrument.knob]) for e in evaluations)
        out.append(f"| {instrument.label} | `{instrument.knob}` | {grid} "
                   f"| de {_md(min(costs))} à {_md(max(costs))} |")
    for entry in etudes:
        for t in entry["report"]["hypotheses"]["transformations"]:
            rates = ", ".join(_pct(b["rate"]) for b in t["law"]["bareme"])
            out += ["", f"`{t['name']}` : {t['label']}. Le barème en vigueur qu'elle met "
                        f"à l'échelle est celui de {t['year']}, ses taux {rates}."]
    out += ["", "## La réponse", "",
            "| Instrument | " + " | ".join(
                s["persistence_label"] for s in report["searches"]) + " |",
            "|---|" + "---|" * len(report["searches"])]
    for entry in etudes:
        instrument, r = entry["instrument"], entry["report"]
        out.append(f"| {instrument.label} | " + " | ".join(
            verdict(s, instrument, target, theta) for s in r["searches"]) + " |")
    for entry in etudes:
        instrument, r = entry["instrument"], entry["report"]
        out += ["", f"### {instrument.label}", "", r["question"]]
        for search in r["searches"]:
            out += ["", f"**{search['persistence_label']}.** "
                        f"{verdict(search, instrument, target, theta)}", ""]
            out += _search_table(search, instrument, target, first_year=first_year,
                                 target_year=target_year, theta=theta)
        lacks = {}
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
        out += _indices(entry, target_year)
    out += ["", "## Ce que l'étude ne dit pas", "",
            "- Ce n'est pas une prévision. Chaque chiffre dépend des scénarios nommés et de "
            "θ ; un autre scénario donne une autre réponse.",
            f"- Une seule valeur de θ, {theta}, et ses coins. La boîte θ est l'étendue aux coins, "
            "ni une somme de tranches ni un intervalle de probabilité.",
            "- La première année est chiffrée, les suivantes reportées en part de PIB : une "
            "convention, que `impots predictif` lève année par année (D-236).",
            "- Ni l'IS, ni les dividendes, ni la couche entreprises : la chaîne ne les "
            "porte pas. Ce qu'elle ferme, et pourquoi :",
            *[f"  - {name} : {why}"
              for name, why in report["searches"][0]["indices"]["closed"].items()],
            "- Elle ne recommande rien. Elle dit ce que la machine répond, sous ces "
            "hypothèses, à la question posée."]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    try:
        etudes = load()
    except EtudeError as error:
        print(str(error), file=sys.stderr)
        return 1
    OUT.write_text(render(etudes), encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
