"""La page de l'étude du PLF 2027 (D-286, but 1) : `docs/ETUDE_PLF2027.md`, depuis les
rapports commités de `reports/etude_plf2027/`.

    python scripts/write_etude_plf2027.py

Pour chacun des articles 2, 3 et 15, les trois réponses : ce qu'il coûte et qui y gagne ;
ce qu'il coûte une fois les comportements et l'économie pris en compte, ou pourquoi la
chaîne ne le dit pas ; ce qu'il fait à la dette en 2035. Puis l'écart au chiffrage officiel,
lu sur l'enregistrement que l'annexe a noté, et les trente autres articles fiscaux avec la
raison de leur refus.

AUCUN NOMBRE N'EST SAISI. Chaque nombre de la page se lit dans un rapport, dans un
enregistrement ou dans le triage. `tests/test_write_etude_plf2027.py` refuse une page qui
n'est pas celle que les rapports donnent, et les rapports qui ne sont pas ceux de l'étude :
un autre scénario, un autre cadre, un `src/` modifié, un lieu non dit, deux commits.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "etude_plf2027"
DOC = ROOT / "docs" / "ETUDE_PLF2027.md"
TITLE = "# Le PLF 2027 en trois réponses"
#: The years the annual paths price: the study's frame, 2026 to 2035 (D-237).
YEARS = list(range(2026, 2036))

sys.path.insert(0, str(ROOT / "src"))


class EtudeError(ValueError):
    """The reports are not the study's, and the page would say what they do not."""


def _load(name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _frame() -> dict[str, Any]:
    """What the annual report says of the frame the study's request names (D-237)."""
    from impots.dette.path import SHIPPED

    launcher = _load("etude_plf2027")
    request = _read(ROOT / "etude" / f"{launcher.FRAME}.json")
    return {"spending_name": SHIPPED[request["spending"]["rule"]].name,
            "growth_name": request["growth"]["name"], "rate_name": request["rate"]["name"],
            "behavioural": request["behavioural"], "macro": request["macro"],
            "theta": request["theta"]["common"]}


def load(reports: Path = REPORTS) -> list[dict[str, Any]]:
    """Each article's two reports, refused unless they are the study's, as it was set."""
    from impots import plf_coverage, preregistration
    from impots import scenarios as scenarios_module
    from impots.api.schemas import FirmResponse, PopulationResponse, PredictifReportResponse

    launcher = _load("etude_plf2027")
    wanted = {f"{kind}_{name}.json" for name in launcher.ARTICLES
              for kind in ("premiere_annee", "predictif")}
    there = {p.name for p in reports.glob("*.json")} if reports.exists() else set()
    if there != wanted:
        raise EtudeError(f"l'étude porte une première année et un chemin par article : "
                         f"il manque {sorted(wanted - there)}, et {sorted(there - wanted)} "
                         f"n'en est pas.")
    frame = _frame()
    articles = {Path(a.reforme).stem: a for a in plf_coverage.ARTICLES_2027 if a.reforme}
    entries, commits = [], set()
    for name in launcher.ARTICLES:
        first = _read(reports / f"premiere_annee_{name}.json")
        path = _read(reports / f"predictif_{name}.json")
        for label, report in (("la première année", first), ("le chemin", path)):
            if not report.get("commit") or report.get("dirty") is not False:
                raise EtudeError(f"{name}, {label} : ne nomme pas un commit dont il a "
                                 f"chiffré le code.")
            if not report.get("where"):
                raise EtudeError(f"{name}, {label} : ne dit pas où ses passes ont tourné.")
            commits.add(report["commit"])
        kind, endpoint, payload = launcher.first_year_payload(name)
        if (first.get("scenario"), first.get("kind"), first.get("endpoint"),
                first.get("request")) != (name, kind, endpoint, payload):
            raise EtudeError(f"{name} : la première année n'a pas chiffré le scénario de "
                             f"l'étude, par l'appel de sa chaîne.")
        response = (FirmResponse if kind == "entreprises" else PopulationResponse
                    ).model_validate(first["response"])
        if response.reform_cost is None:
            raise EtudeError(f"{name} : la première année n'a pas de coût.")
        if kind == "entreprises" and (response.meta.vintage != launcher.FIRM_VINTAGE
                                      or response.meta.cells_are_synthetic):
            raise EtudeError(f"{name} : la première année n'a pas tourné sur les entreprises "
                             f"de {launcher.FIRM_VINTAGE}, leurs cellules réelles "
                             f"(millésime « {response.meta.vintage} »).")
        try:
            PredictifReportResponse.model_validate(path)
        except ValueError as error:
            raise EtudeError(f"{name} : le chemin ne valide pas : {error}") from error
        scenario = scenarios_module.load(name, launcher.SCENARIOS)
        said = {k: path.get(k) for k in ("spending_name", "growth_name", "rate_name",
                                         "behavioural", "macro")}
        if (path.get("scenario") != name or said != {k: frame[k] for k in said}
                or set(path["theta"].values()) != {frame["theta"]}
                or [row["year"] for row in path["years"]] != YEARS
                or (path.get("annees") or []) != list(scenario.annees)):
            raise EtudeError(f"{name} : le chemin n'a pas tourné dans le cadre de l'étude, "
                             f"sur son scénario.")
        case = preregistration.load(name)
        entries.append({"name": name, "article": articles[name], "scenario": scenario,
                        "kind": kind, "first": first, "response": response, "path": path,
                        "case": case, "grade": preregistration.grade(case)})
    if len(commits) != 1:
        raise EtudeError(f"les rapports de l'étude sont sur {len(commits)} commits "
                         f"({sorted(c[:7] for c in commits)}) : une seule étude se lit sur "
                         f"un seul code.")
    return entries


# --------------------------------------------------------------------------- #
# The reading
# --------------------------------------------------------------------------- #


def _points(value: float) -> str:
    return f"{value * 100:+.2f} pt".replace(".", ",")


def debt(path: dict[str, Any]) -> list[dict[str, Any]]:
    """Δb in the last year, at θ and at the box's corners, by persistence and view."""
    year = path["years"][-1]["year"]
    box = {p["persistence"]: p["every_year"]
           for p in (path.get("theta_box") or {}).get("paths", [])}
    if path.get("side_by_side"):
        drawn = [(p["persistence"], p["label"], p["years"][-1]) for p in path["side_by_side"]]
    else:
        drawn = [(path.get("persistence"), None, path["years"][-1])]
    rows = []
    for persistence, label, last in drawn:
        for view, key in (("vieillie", "delta_aged"), ("figee", "delta_frozen")):
            reading = (box.get(persistence) or {}).get(view)
            corners = [value for _, value in reading["corners"]] if reading else []
            if reading and abs(reading["theta"] - last[key]) > 1e-12:
                raise EtudeError(f"Δb {year} à θ ({last[key]:+.6f}) n'est pas celui de la "
                                 f"boîte ({reading['theta']:+.6f}), vue « {view} ».")
            rows.append({"persistence": persistence, "label": label, "view": view,
                         "theta": last[key], "corners": corners})
    return rows


def verdict(rows: list[dict[str, Any]]) -> str:
    """« hausse » or « baisse » when Δb has one sign at θ and at every corner, in both
    views and under each persistence; « dépend de θ » otherwise."""
    values = [v for row in rows for v in (row["theta"], *row["corners"])]
    if all(v > 0 for v in values):
        return "hausse"
    if all(v < 0 for v in values):
        return "baisse"
    return "dépend de θ"


VIEWS = {"vieillie": "vieillie", "figee": "figée"}

VERDICTS = {
    "hausse": "elle **augmente la dette** en 2035, à θ½ comme à chaque coin de la boîte, "
              "dans les deux vues",
    "baisse": "elle **baisse la dette** en 2035, à θ½ comme à chaque coin de la boîte, "
              "dans les deux vues",
    "dépend de θ": "son effet sur la dette en 2035 **dépend de θ** : son signe change d'un "
                   "coin de la boîte, ou d'une vue, à l'autre",
}


# --------------------------------------------------------------------------- #
# The page
# --------------------------------------------------------------------------- #


def _sizes(response: Any) -> list[tuple[str, float, float, float]]:
    """(taille, firms, firms affected, total delta) of a firm reply's cells."""
    out: dict[str, list[float]] = {}
    for cell in response.cells:
        row = out.setdefault(cell.taille, [0.0, 0.0, 0.0])
        row[0] += cell.n_firms
        row[1] += cell.n_firms * (cell.share_affected or 0.0)
        row[2] += cell.n_firms * (cell.mean_delta or 0.0)
    return [(taille, *row) for taille, row in out.items()]


def _first(w: Any, entry: dict[str, Any]) -> None:
    from impots import fiche

    response, year = entry["response"], entry["scenario"].year
    cost = float(response.reform_cost)
    sense = "coûte" if cost > 0 else "rapporte"
    if entry["kind"] == "entreprises":
        w(f"La mesure {sense} **{fiche._width(cost)}** en {year}, sur les entreprises "
          f"de {response.meta.vintage} au droit de {year}.")
        w("")
        w("| taille | entreprises | touchées | effet total |")
        w("|---|---|---|---|")
        for taille, n, touched, delta in _sizes(response):
            w(f"| {taille} | {fiche._num(n)} | {fiche._num(touched)} | {fiche._eur(delta)} |")
        w("")
        w(response.meta.note)
    else:
        w(f"La mesure {sense} **{fiche._width(cost)}** la première année (revenus "
          f"{year}), sur la population de {response.meta.vintage} au droit de {year}.")
        w("")
        fiche._deciles(w, response)


def _second(w: Any, entry: dict[str, Any]) -> None:
    from impots import fiche

    response = entry["response"]
    behavioural = response.behavioural
    if behavioural is None:
        w("**Bande comportementale : aucune.** " + (
            "Aucun canal des ménages ne lit une réforme des seules entreprises, et la "
            "chaîne des entreprises n'en calcule pas." if entry["kind"] == "entreprises"
            else "Aucune réponse comportementale n'a été calculée."))
    elif behavioural.band is None:
        w(f"**Bande comportementale : aucune, et la raison est donnée.** "
          f"{behavioural.grade_reason or 'non précisée'}")
    else:
        band = behavioural.band
        # The band is about the budget balance, the mechanical figure repeated in its
        # sign; the page reads costs. Turned over only once checked (D-289).
        if band.unit != "EUR" or abs(behavioural.mechanical + response.reform_cost) > 1.0:
            raise EtudeError(f"{entry['name']} : la bande n'est pas en euros autour du solde "
                             f"de la mesure ({behavioural.mechanical:+.0f} pour un coût de "
                             f"{response.reform_cost:+.0f}) ; la page la lirait à l'envers.")
        w(f"**Une fois les comportements pris en compte**, la mesure coûte de "
          f"{fiche._eur(-band.p90)} à {fiche._eur(-band.p10)}, central "
          f"{fiche._eur(-band.p50)} (grade **{behavioural.grade}**), pour "
          f"{fiche._eur(response.reform_cost)} sans eux.")
        if behavioural.grade_reason:
            w("")
            w(f"*{behavioural.grade_reason}*")
    w("")
    macro = getattr(entry["response"], "macro", None)
    if macro is not None and macro.available:
        for label, series in (("PIB", macro.gdp), ("emploi", macro.jobs)):
            for horizon, q in sorted(series.items()):
                w(f"* **{label}, {horizon}** : {fiche._band(q.p10, q.p50, q.p90, q.unit)}")
        w("")
    elif macro is not None:
        w(f"**Éventail macro : refusé.** {macro.unavailable_because}")
        w("")
    closed = entry["path"].get("closed") or {}
    if closed:
        w("Ce que la chaîne ne lit pas, et pourquoi :")
        w("")
        for what, why in closed.items():
            w(f"* **{what}** — {why.split(' ; ')[0].split('. ')[0].rstrip('.')}.")
        w("")


def _third(w: Any, entry: dict[str, Any]) -> None:
    path = entry["path"]
    rows = debt(path)
    year = path["years"][-1]["year"]
    if path.get("annees"):
        w(f"La mesure ne s'applique qu'en {', '.join(map(str, path['annees']))} : le chemin "
          f"la chiffre cette année-là et ne lui prête rien les autres (D-288).")
        w("")
    w(f"| persistance | vue | Δ dette {year}, à θ½ | aux coins de la boîte |")
    w("|---|---|---|---|")
    for row in rows:
        corners = (f"de {_points(min(row['corners']))} à {_points(max(row['corners']))}"
                   if row["corners"] else "—")
        w(f"| {row['label'] or '—'} | {VIEWS[row['view']]} | {_points(row['theta'])} | "
          f"{corners} |")
    w("")
    w(f"En points de PIB de {year}, la dette avec la mesure moins la dette sans elle. La "
      f"vue vieillie fait vieillir la population chaque année avec les salaires ; la vue "
      f"figée la garde telle qu'elle est. Sur ces passes, {VERDICTS[verdict(rows)]}.")
    w("")


def _official(w: Any, entry: dict[str, Any]) -> None:
    from impots import fiche

    case, grade = entry["case"], entry["grade"]
    rel = "n. d." if grade.relative_gap is None else (
        f"{grade.relative_gap:+.1%}".replace(".", ","))
    within = "**dans la tolérance**" if grade.verdict == "within" else (
        "**hors de la tolérance**")
    w(f"Enregistré le {case.pre_registered[:10]}, sur le commit `{case.commit[:7]}`, avant "
      f"l'ouverture de l'annexe : simulé {fiche._eur(grade.simulated_eur)}, publié "
      f"{fiche._eur(grade.published_eur)} ({case.comparator.source}). Écart "
      f"{fiche._eur(grade.gap_eur)} ({rel}), pour une tolérance déclarée de "
      f"{fiche._width(grade.allowed_eur)} : {within}.")
    w("")
    now = float(entry["response"].reform_cost)
    w(f"La première année de cette étude, sur le code de l'étude, chiffre "
      f"{fiche._eur(now)}, soit {fiche._eur(now - grade.simulated_eur)} de "
      f"l'enregistrement. Le chiffre noté reste celui de l'enregistrement : c'est lui qui a "
      f"été préenregistré.")
    w("")


def render(entries: list[dict[str, Any]]) -> str:
    from impots import fiche, plf_coverage

    lines: list[str] = []
    w = lines.append
    every = plf_coverage.ARTICLES_2027
    w(TITLE)
    w("")
    w("<!-- Généré par scripts/write_etude_plf2027.py depuis reports/etude_plf2027/ ; "
      "ne pas éditer à la main. -->")
    w("")
    w(f"Le projet de loi de finances pour 2027 porte {len(every)} articles fiscaux. Cet "
      f"outil en chiffre {len(entries)}, et dit pourquoi il ne chiffre pas les autres. "
      f"Pour chacun des {len(entries)}, trois réponses : ce qu'il coûte et qui y gagne ; ce "
      f"qu'il coûte une fois les comportements et l'économie pris en compte ; ce qu'il fait "
      f"à la dette en 2035. Puis l'écart au chiffrage du gouvernement, l'évaluation "
      f"préalable publiée avec le texte.")
    w("")
    w("Chaque nombre dépend de ce qui est dit à côté de lui. Le coût de la première année "
      "est mécanique : personne ne change de comportement. La bande dit ce que les "
      "comportements y changent quand une étude publiée permet de le dire. La dette en 2035 "
      "dépend d'hypothèses de croissance, de taux et de dépenses nommées en bas de page, et "
      "de θ, la position de chaque réponse dans sa fourchette publiée : θ½ est le milieu, "
      "les coins de la boîte en sont les extrêmes.")
    w("")
    w("## En bref")
    w("")
    w("| article | la première année | le chiffrage officiel | dette en 2035, à θ½ |"
      " selon θ |")
    w("|---|---|---|---|---|")
    for entry in entries:
        rows = debt(entry["path"])
        lead = rows[0]
        grade = entry["grade"]
        mark = "dans" if grade.verdict == "within" else "hors de"
        w(f"| art. {entry['article'].numero} | {fiche._eur(entry['response'].reform_cost)} | "
          f"{fiche._eur(grade.published_eur)}, {mark} la tolérance | "
          f"{_points(lead['theta'])} | {verdict(rows)} |")
    w("")
    w("Un coût positif coûte au budget, un coût négatif lui rapporte. La dette est en "
      "points de PIB, dans la vue vieillie et sous la première persistance de l'effet "
      "macro de chaque article ; « selon θ » lit toutes les vues et toutes les "
      "persistances.")
    w("")
    for entry in entries:
        article = entry["article"]
        w(f"## Art. {article.numero} — {article.intitule}")
        w("")
        w(f"*{entry['scenario'].source}*")
        w("")
        if entry["scenario"].note:
            w(entry["scenario"].note)
            w("")
        w("### 1. Ce qu'il coûte, et qui y gagne")
        w("")
        _first(w, entry)
        w("")
        w("### 2. Avec les comportements et l'économie")
        w("")
        _second(w, entry)
        w("### 3. La dette en 2035")
        w("")
        _third(w, entry)
        w("### L'écart au chiffrage officiel")
        w("")
        _official(w, entry)
    refused = [a for a in every if a.bucket != "priceable_now"]
    w(f"## Les {len(refused)} autres articles")
    w("")
    w("Un article refusé n'est pas un article à zéro. Le refus est pris sur le texte, avant "
      "tout chiffrage, et sa raison est dite : hors du périmètre (`scope`), hors de la "
      "structure du modèle (`structure`), ou hors de ses données (`data`).")
    w("")
    w("| art. | intitulé | raison |")
    w("|---|---|---|")
    for a in refused:
        w(f"| {a.numero} | {a.intitule} | {a.raison.split('.')[0]} |")
    w("")
    w("## D'où viennent ces nombres")
    w("")
    path = entries[0]["path"]
    first = entries[0]["first"]
    w(f"Les passes ont tourné sur le commit `{first['commit'][:7]}`, {first['where']}. "
      f"Cadre du chemin annuel : {path['growth_name']} ; {path['rate_name']} ; "
      f"{path['spending_name']} ; droit reconduit tel qu'openfisca le porte ; θ½ sur "
      f"toutes les lignes ; comportements et boucle macro appliqués.")
    w("")
    w(f"*{path['uprating_note']}*")
    w("")
    for entry in entries:
        w(f"* `reports/etude_plf2027/premiere_annee_{entry['name']}.json`, "
          f"`reports/etude_plf2027/predictif_{entry['name']}.json`, "
          f"`chiffrages_preregistres/{entry['name']}.yaml`")
    w("")
    return "\n".join(lines)


def main() -> int:
    try:
        text = render(load())
    except EtudeError as error:
        print(str(error), file=sys.stderr)
        return 1
    DOC.write_text(text, encoding="utf-8")
    print(f"-> {DOC} ({len(text.splitlines())} lignes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
