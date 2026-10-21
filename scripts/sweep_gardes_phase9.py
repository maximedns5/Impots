#!/usr/bin/env python3
"""Le balayage des gardes de la phase 9 (PHASE9_SPEC §10, jalon M6 ; D-229).

Une garde livre son kill test vu échouer : la règle vaut au moment où la garde entre, et
rien ne dit qu'elle tient encore six jalons plus tard. Un test réécrit, une condition
déplacée, un refus doublé plus haut qui rend celui-ci inatteignable : la garde est
toujours dans le code, son test toujours vert, et plus rien ne la tient. Ce script le
vérifie garde par garde, par mutation.

**Le catalogue se lit dans le code, il n'est pas tenu à la main.** Chaque `raise` des
périmètres de `SCOPES` devient une mutation : sa condition forcée à faux, son
ré-emballage d'erreur réduit à un `raise` nu, ou, s'il est dans la branche `else` d'un
test ou inconditionnel, remplacé par un `pass` ou un `return None`. Une garde ajoutée demain entre au catalogue d'elle-même ;
`tests/test_gardes_phase9.py` refuse alors un rapport qui ne la nomme pas. Les gardes qui
ne sont pas des `raise` — les gardes 1 et 4 à 7 de §2.4, la page — sont dans `MANUAL`,
chacune avec le texte exact qu'elle mute.

**Deux étages.** Chaque mutation tourne d'abord contre les tests de son périmètre ; une
survivante est rejouée contre toute la suite de la phase 9 (`WIDE`) avant d'être dite
survivante. Une survivante n'est jamais tolérée en silence : elle reçoit un kill test, ou
une équivalence nommée dans `EQUIVALENT`, avec la raison pour laquelle aucun test ne peut
la tuer. Une équivalence qu'un test tue quand même est signalée, pour être retirée.

    python scripts/sweep_gardes_phase9.py            # tout le catalogue, une vingtaine de minutes
    python scripts/sweep_gardes_phase9.py --missing  # les seules mutations absentes du rapport
    python scripts/sweep_gardes_phase9.py --only ID  # une mutation, pour voir son verdict

Le script mute `src/` et `ui/` en place et restaure chaque fichier depuis la mémoire,
quoi qu'il arrive. Il refuse de tourner sur des fichiers modifiés de ces répertoires :
le rapport nomme le commit balayé, et une restauration ne doit jamais écraser du travail.
"""

from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "gardes_phase9.md"

PY = sys.executable
NODE = "node"
TIMEOUT_S = 900


@dataclass(frozen=True)
class Scope:
    """Where Phase 9 guards live, and the tests that must kill them. `functions` None:
    the whole module is Phase 9's. `only`: of those functions, the guards whose
    condition mentions one of these words — the rest predate Phase 9."""

    path: str
    tests: tuple[str, ...]
    functions: tuple[str, ...] | None = None
    only: tuple[str, ...] = ()


SCOPES: tuple[Scope, ...] = (
    Scope("src/impots/predictif/annuel.py",
          ("tests/test_predictif_annuel.py", "tests/test_cli_predictif.py",
           "tests/test_predictif_annuel_boucle.py")),
    Scope("src/impots/predictif/chaine.py", ("tests/test_predictif.py",)),
    Scope("src/impots/predictif/comportement.py",
          ("tests/test_theta.py", "tests/test_predictif.py")),
    Scope("src/impots/predictif/exploration.py",
          ("tests/test_exploration.py", "tests/test_recherche_indices.py")),
    Scope("src/impots/predictif/indices.py", ("tests/test_indices.py",)),
    Scope("src/impots/predictif/macro.py", ("tests/test_theta.py", "tests/test_indices.py")),
    Scope("src/impots/predictif/retroaction.py", ("tests/test_retroaction.py",)),
    Scope("src/impots/predictif/theta.py", ("tests/test_theta.py",)),
    Scope("src/impots/predictif/validation.py", ("tests/test_validation_predictif.py",)),
    Scope("src/impots/dette/scenarios.py",
          ("tests/test_dette_reference.py", "tests/test_predictif.py")),
    Scope("src/impots/dette/reference.py", ("tests/test_dette_reference.py",),
          functions=("reference_years", "start_from_accounts")),
    Scope("src/impots/explorer.py", ("tests/test_explorer.py", "tests/test_exploration.py"),
          functions=("refuse_theta_as_knob", "search"),
          only=("theta", "conditional", "corners", "named")),
    Scope("src/impots/api/main.py", ("tests/test_api_predictif.py", "tests/test_recherche.py",
                                     "tests/test_explorations_api.py"),
          functions=("predictif_simulate", "_predictif_macro_store", "_price_first_year",
                     "predictif_show", "predictif_list", "_predictif_hypotheses",
                     "explorations_show", "explorations_list")),
    Scope("src/impots/population/cli.py",
          ("tests/test_cli_predictif.py", "tests/test_recherche.py",
           "tests/test_predictif_annuel_boucle.py", "tests/test_transformations.py", "tests/test_recherche_indices.py"),
          functions=("cmd_predictif", "cmd_exploration", "_whole_pass_refusals")),
    # Phase 10 M1 (D-234): the explorer made askable, its request and its command.
    Scope("src/impots/predictif/recherche.py", ("tests/test_recherche.py", "tests/test_transformations.py", "tests/test_recherche_indices.py")),
    # Phase 10 M4 (D-237): the named transformation, and the indices of the nearest bundle.
    Scope("src/impots/predictif/transformations.py", ("tests/test_transformations.py",)),
    Scope("src/impots/api/schemas.py",
          ("tests/test_recherche.py", "tests/test_explorations_api.py",
           "tests/test_predictif_annuel_boucle.py", "tests/test_transformations.py", "tests/test_recherche_indices.py"),
          functions=("_check_exploration_bounds", "_check_exploration_search",
                     "_check_exploration_report", "_check_report_paths",
                     "_check_exploration_indices")),
)

#: The whole Phase 9 suite, the second tier for a survivor.
WIDE: tuple[str, ...] = (
    "tests/test_predictif.py", "tests/test_predictif_annuel.py",
    "tests/test_api_predictif.py", "tests/test_cli_predictif.py", "tests/test_theta.py",
    "tests/test_indices.py", "tests/test_explorer.py", "tests/test_exploration.py",
    "tests/test_retroaction.py", "tests/test_macro_parameters.py",
    "tests/test_validation_predictif.py", "tests/test_predictif_exemple.py",
    "tests/test_dette_reference.py", "tests/test_behavioural.py",
    "tests/test_offre_travail.py", "tests/test_creations.py", "tests/test_cir.py",
    "tests/test_recherche.py", "tests/test_explorations_api.py",
    "tests/test_predictif_annuel_boucle.py", "tests/test_transformations.py", "tests/test_recherche_indices.py",
)

UI_CHECK = "ui/check.mjs"


@dataclass(frozen=True)
class Mutation:
    id: str
    path: str
    old: str
    new: str
    tests: tuple[str, ...]
    guard: str
    """What the guard refuses, in a few words, for the report."""


#: The guards that are not a `raise`: each with the exact text it mutates.
MANUAL: tuple[Mutation, ...] = (
    Mutation("G1-schema-theta", "src/impots/api/schemas.py",
             "    theta: PredictifTheta\n    uprating: PredictifUprating\n",
             "    theta: PredictifTheta = Field(default_factory=lambda: "
             "PredictifTheta(common=0.5))\n    uprating: PredictifUprating\n",
             ("tests/test_api_predictif.py",),
             "garde 1 : pas de θ par défaut dans la requête"),
    Mutation("G1-schema-uprating", "src/impots/api/schemas.py",
             "    theta: PredictifTheta\n    uprating: PredictifUprating\n",
             "    theta: PredictifTheta\n    uprating: PredictifUprating = Field("
             "default_factory=lambda: PredictifUprating(wage=0.03, source='défaut'))\n",
             ("tests/test_api_predictif.py",),
             "l'indice des salaires est requis, avec sa source (D-226)"),
    Mutation("G1-commande-theta", "src/impots/population/cli.py",
             '    predictif.add_argument("--theta", type=float, required=True,',
             '    predictif.add_argument("--theta", type=float, default=0.5,',
             ("tests/test_cli_predictif.py",),
             "garde 1 : `impots predictif` refuse de tourner sans θ"),
    Mutation("G1-page-theta", "ui/index.html",
             '  if (theta === "") missing.push("un θ, de 0 à 1");',
             '  if (false) missing.push("un θ, de 0 à 1");',
             (UI_CHECK,), "garde 1 : la page n'envoie rien sans θ"),
    Mutation("G4-sens", "src/impots/behavioural/store.py",
             '    if parameter.theta_one not in ("low", "high"):\n        return (f"θ undeclared',
             '    if False:\n        return (f"θ undeclared',
             ("tests/test_theta.py", "tests/test_behavioural.py"),
             "garde 4 : une ligne ouverte sans sens de θ ne charge pas"),
    Mutation("G4-chargement", "src/impots/behavioural/store.py",
             "            problem = _theta_problem(parameter)\n            if problem:",
             "            problem = _theta_problem(parameter)\n            if False:",
             ("tests/test_theta.py", "tests/test_behavioural.py"),
             "garde 4 : le magasin refuse de charger la ligne, il ne la lit pas en silence"),
    Mutation("transferts-chargement", "src/impots/macro/store.py",
             "            problem = _transfer_problem(body)\n            if problem:",
             "            problem = _transfer_problem(body)\n            if False:",
             ("tests/test_macro_parameters.py",),
             "une ligne de transfert sans grade ne charge pas (D-219)"),
    Mutation("G4-raison", "src/impots/behavioural/store.py",
             "    if not parameter.theta_reason:",
             "    if False:",
             ("tests/test_theta.py", "tests/test_behavioural.py"),
             "garde 4 : un sens de θ sans sa raison ne charge pas"),
    Mutation("G5-centre", "src/impots/predictif/theta.py",
             "        return centre - (1.0 - 2.0 * t) * (centre - low)",
             "        return low + t * (high - low)",
             ("tests/test_theta.py",),
             "garde 5 : θ = ½ rend le centre publié, au dernier chiffre"),
    Mutation("G6-vue-epinglee", "src/impots/predictif/theta.py",
             "    return Store(parameters=parameters, thresholds=dict(store.thresholds),",
             "    store.parameters.update(parameters)\n"
             "    return Store(parameters=parameters, thresholds=dict(store.thresholds),",
             ("tests/test_theta.py",),
             "garde 6 : la vue épinglée ne touche pas la bande de Monte-Carlo"),
    Mutation("G7-monotonie", "src/impots/predictif/theta.py",
             "    return centre + (2.0 * t - 1.0) * (high - centre)",
             "    return centre + 4.0 * (2.0 * t - 1.0) * (1.0 - t) * (high - centre)",
             ("tests/test_theta.py",),
             "garde 7 : chaque canal est monotone en son θ"),
    Mutation("chaine-absent-retroaction", "src/impots/predictif/chaine.py",
             "    feedback_reason = ABSENT_FEEDBACK\n",
             '    feedback_reason = ""\n',
             ("tests/test_predictif.py",),
             "une boucle non demandée est dite absente, avec sa raison"),
    Mutation("chaine-bande-absente", "src/impots/predictif/chaine.py",
             "        absent.update({\"bande\": ABSENT_BAND,",
             "        absent.update({\"bande\": \"\",",
             ("tests/test_predictif.py",),
             "un comportement non demandé est dit absent, avec sa raison"),
    Mutation("D230-api-les-deux", "src/impots/api/main.py",
             "        else list(retroaction.PERSISTENCE_LABELS)",
             '        else ["tenu"]',
             ("tests/test_api_predictif.py", "tests/test_recherche.py"),
             "sans persistance nommée, les deux scénarios sont calculés (D-230)"),
    Mutation("D230-schema-en-tete", "src/impots/api/schemas.py",
             "        if any(v is not None for v in own) or self.slices:",
             "        if False:",
             ("tests/test_api_predictif.py",),
             "côte à côte, la réponse ne porte aucune trajectoire en tête (D-230)"),
    Mutation("D230-schema-les-deux", "src/impots/api/schemas.py",
             '        if sorted(p.persistence for p in self.side_by_side) != ["eteint", "tenu"]:',
             "        if False:",
             ("tests/test_api_predictif.py",),
             "côte à côte, ce sont les deux scénarios, chacun une fois (D-230)"),
    Mutation("D230-schema-une-trajectoire", "src/impots/api/schemas.py",
             "            if self.reform is None or self.delta is None or self.delta_primary is None:",
             "            if False:",
             ("tests/test_api_predictif.py",),
             "une réponse porte une trajectoire, ou les deux côte à côte (D-230)"),
    Mutation("D230-page-cote-a-cote", "ui/index.html",
             "  const each = d.side_by_side.map((p) => {",
             "  const each = d.side_by_side.slice(0, 1).map((p) => {",
             (UI_CHECK,), "la page dessine les deux scénarios, aucun en tête (D-230)"),
    Mutation("page-vue-population", "ui/index.html",
             "Population : <b>",
             "Population&nbsp;: <b>",
             (UI_CHECK,), "la page nomme la vue de population au-dessus du tableau (D-225)"),
    # Phase 10 M1 (D-234): the guards of `impots exploration` that return rather than raise.
    Mutation("P10-schema-theta", "src/impots/api/schemas.py",
             "    uprating: PredictifUprating\n    theta: PredictifTheta\n",
             "    uprating: PredictifUprating\n    theta: PredictifTheta = Field("
             "default_factory=lambda: PredictifTheta(common=0.5))\n",
             ("tests/test_recherche.py",),
             "garde 1 : pas de θ par défaut dans une exploration non plus"),
    Mutation("P10-schema-uprating", "src/impots/api/schemas.py",
             "    uprating: PredictifUprating\n    theta: PredictifTheta\n",
             "    uprating: PredictifUprating = Field(default_factory=lambda: "
             "PredictifUprating(wage=0.03, source='défaut'))\n    theta: PredictifTheta\n",
             ("tests/test_recherche.py",),
             "l'indice des salaires est requis dans une exploration, avec sa source"),
    Mutation("P10-arbre-modifie", "src/impots/population/cli.py",
             '    if dirty:\n        print("src/ a des modifications non commitées',
             '    if False:\n        print("src/ a des modifications non commitées',
             ("tests/test_recherche.py",),
             "un src/ modifié est refusé : le rapport nomme son code (garde 4)"),
    Mutation("P10-deux-vues", "src/impots/population/cli.py",
             "            uprating=hypotheses.uprating, macro=request.macro, view=view)",
             '            uprating=hypotheses.uprating, macro=request.macro, view="vieillie")',
             ("tests/test_recherche.py",),
             "chaque paquet est chiffré dans ses deux vues, par la passe du simulateur"),
    Mutation("P10-un-seul-chiffrage", "src/impots/population/cli.py",
             "                                      behavioural=request.behavioural),",
             "                                      behavioural=False),",
             ("tests/test_recherche.py",),
             "l'explorateur chiffre ce que chiffre le simulateur (garde 6)"),
    Mutation("P10-une-passe-par-paquet", "src/impots/predictif/recherche.py",
             "        if key not in passes:",
             "        if True:",
             ("tests/test_recherche.py",),
             "une passe par paquet et par vue, les deux persistances comprises (garde 3)"),
    # Phase 10 M2 (D-235): the page's panel of explorations.
    Mutation("P10-page-question", "ui/index.html",
             '    <p class="pquestion"><b>Question :</b> ${escapeHtml(r.question)}</p>',
             '    <p class="pquestion"></p>',
             (UI_CHECK,), "la question ouvre l'exploration (PHASE10_SPEC §3)"),
    Mutation("P10-page-cote-a-cote", "ui/index.html",
             '    ${side}${r.searches.map((s) => explorationSearch(r, s)).join("")}',
             '    ${side}${r.searches.slice(0, 1).map((s) => explorationSearch(r, s)).join("")}',
             (UI_CHECK,), "les deux recherches de persistance sont dessinées (D-230)"),
    Mutation("P10-page-cout", "ui/index.html",
             "      <td>${knobsFr(e.knobs)}</td><td>${mdFr(e.cost_aged_eur)}</td>",
             "      <td>${knobsFr(e.knobs)}</td><td></td>",
             (UI_CHECK,), "chaque paquet montre son coût de première année (D-235)"),
    Mutation("P10-page-fige", "ui/index.html",
             '  if (c.frozen_only) return "ne tient qu\'en vue figée : pas un plan (D-155)";',
             '  if (false) return "ne tient qu\'en vue figée : pas un plan (D-155)";',
             (UI_CHECK,), "un paquet qui ne tient qu'en vue figée n'est pas un plan"),
    Mutation("P10-page-plus-proche", "ui/index.html",
             '  const none = plans.length ? "" :',
             '  const none = true ? "" :',
             (UI_CHECK,), "sans candidat, la page nomme le paquet le plus proche"),
    Mutation("P10-page-commit", "ui/index.html",
             "      <code>${escapeHtml(r.commit.slice(0, 8))}</code>",
             "      <code></code>",
             (UI_CHECK,), "la page nomme le commit de l'exploration"),
    Mutation("P10-page-refus", "ui/index.html",
             '  if (!response.ok) {\n    let detail = "";',
             '  if (false) {\n    let detail = "";',
             (UI_CHECK,), "un rapport refusé par l'API est dit refusé, jamais laissé vide"),
    # Phase 10 M3 (D-236): every annual report drawn, side by side when two paths.
    Mutation("P10-page-tous-les-rapports", "ui/index.html",
             "  for (const name of names) {",
             "  for (const name of names.slice(0, 1)) {",
             (UI_CHECK,), "chaque rapport annuel listé est dessiné, pas seulement le premier"),
    Mutation("P10-page-refus-annuel", "ui/index.html",
             '    if (!one.ok) {\n      let detail = "";',
             '    if (false) {\n      let detail = "";',
             (UI_CHECK,), "un rapport annuel refusé est dit refusé, sans cacher les autres"),
    Mutation("P10-page-annuel-cote-a-cote", "ui/index.html",
             "  if (paths.length) {",
             "  if (false) {",
             (UI_CHECK,), "les deux persistances du chemin annuel, côte à côte (D-230)"),
    Mutation("P10-le-plus-proche", "src/impots/predictif/recherche.py",
             "    closest = None if any(c[\"meets_target\"] for c in found) else nearest",
             "    closest = None if True else nearest",
             ("tests/test_recherche.py",),
             "sans candidat, le rapport nomme le paquet le plus proche (garde 7)"),
    # Phase 10 M4 (D-237): the transformation and the indices, where nothing raises.
    Mutation("P10-echelle-taux", "src/impots/predictif/transformations.py",
             "\"rate\": float(b[\"rate\"]) * value}",
             "\"rate\": float(b[\"rate\"])}",
             ("tests/test_transformations.py",),
             "l'échelle multiplie chaque taux du barème en vigueur"),
    Mutation("P10-droit-lu-si-demande", "src/impots/population/cli.py",
             "law = recherche.law_in_force(year) if recherche.needs_law(request) else None",
             "law = recherche.law_in_force(year)",
             ("tests/test_transformations.py",),
             "le droit en vigueur n'est lu que si une transformation le demande"),
    Mutation("P10-droit-de-l-annee", "src/impots/population/cli.py",
             "law = recherche.law_in_force(year) if",
             "law = recherche.law_in_force(year + 1) if",
             ("tests/test_transformations.py",),
             "le facteur met à l'échelle le barème de la première année projetée"),
    Mutation("P10-indices-meme-passe", "src/impots/predictif/recherche.py",
             "            aged = priced(knobs, exploration.VIEWS[0])",
             "            aged = price(reform, exploration.VIEWS[0])",
             ("tests/test_recherche_indices.py",),
             "les indices du paquet le plus proche viennent de sa passe, sans passe de plus"),
    Mutation("P10-indices-deciles", "src/impots/population/cli.py",
             "uncovered=dict(first.uncovered), deciles=list(first.deciles))",
             "uncovered=dict(first.uncovered))",
             ("tests/test_recherche_indices.py",),
             "les indices lisent les déciles de la passe, comme le simulateur"),
    Mutation("P10-indices-chemin-propre", "src/impots/predictif/recherche.py",
             "                persistence=persistence, securities=securities)\n"
             "            rows = indices_module.compute(",
             "                persistence=\"tenu\", securities=securities)\n"
             "            rows = indices_module.compute(",
             ("tests/test_recherche_indices.py",),
             "côte à côte, chaque recherche lit la chaîne sur son propre chemin"),
    Mutation("P10-indices-le-plus-proche", "src/impots/predictif/recherche.py",
             "\"closest\": closest, \"indices\": indices(nearest)}",
             "\"closest\": closest, \"indices\": indices(evaluations[0])}",
             ("tests/test_recherche_indices.py",),
             "les indices sont ceux du paquet le plus proche de la cible"),
    # D-238: what the chain lacks rides with the indices, never read as zero.
    Mutation("P10-absences-portees", "src/impots/predictif/recherche.py",
             "\"absent\": dict(path.absent), \"closed\": dict(path.closed),",
             "\"absent\": {}, \"closed\": dict(path.closed),",
             ("tests/test_recherche_indices.py",),
             "ce qui manque à la chaîne est porté au rapport, avec sa raison (D-238)"),
)

#: Mutations no test can kill, each with why. An entry here is a finding of D-229, not
#: a tolerance: the behaviour the guard protects is tested, and holds without it.
EQUIVALENT: dict[str, str] = {
    "predictif/retroaction:compute:si:not 0.0 <= theta <= 1.0": (
        "sans elle, le même θ est refusé quelques lignes plus loin par "
        "`theta.multiplier_at` (garde 3, `_check`), avec la même erreur et le même refus "
        "d'écrêter ; le test passe par l'une ou l'autre. Celle-ci refuse avant de lire "
        "la ligne de solde : un ordre, pas un comportement."),
}


# --------------------------------------------------------------------------- #
# the catalogue, read from the code
# --------------------------------------------------------------------------- #
def _offset(lines: list[bytes], line: int, col: int) -> int:
    """Byte offset of an AST position (1-based line, UTF-8 byte column)."""
    return sum(len(x) for x in lines[:line - 1]) + col


def _slug(text: str) -> str:
    """A condition as an id: one line, no table pipe, at most 70 characters."""
    text = re.sub(r"\s+", " ", text).strip().replace("|", "¦").replace("`", "'")
    return text if len(text) <= 70 else text[:67] + "..."


def generated(scope: Scope) -> list[Mutation]:
    """One mutation per guard of the scope: per `if` that raises, per handler that
    re-raises, per unconditional raise. Ids hold the function and the condition's text,
    never a line number, so that an edit elsewhere in the file leaves them alone."""
    source = (ROOT / scope.path).read_text(encoding="utf-8")
    raw = source.encode("utf-8")
    lines = raw.splitlines(keepends=True)
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def function_of(node: ast.AST) -> tuple[str, str]:
        """(function, Class.function): the scope filters on the first, the id carries
        the second, so that two `__post_init__` in one module stay apart."""
        node = parents.get(node)
        while node is not None and not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            node = parents.get(node)
        if node is None:
            return "-", "-"
        owner = parents.get(node)
        qualified = f"{owner.name}.{node.name}" if isinstance(owner, ast.ClassDef) else node.name
        return node.name, qualified

    seen: set[int] = set()
    out: list[Mutation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise):
            continue
        function, qualified = function_of(node)
        if scope.functions is not None and function not in scope.functions:
            continue
        child, holder = node, parents.get(node)
        while holder is not None and not isinstance(
                holder, ast.If | ast.While | ast.ExceptHandler | ast.FunctionDef
                | ast.AsyncFunctionDef):
            child, holder = holder, parents.get(holder)
        if isinstance(holder, ast.If) and child in holder.orelse:
            # A refusal in the `else` of a test: forcing the test false would fire it
            # every time; the guard removed is the raise itself.
            target, replacement, kind = node, b"pass", "sinon"
            text = "non " + ast.unparse(holder.test)
        elif isinstance(holder, ast.If | ast.While):
            target, replacement, kind = holder.test, b"False", "si"
            text = ast.unparse(holder.test)
        elif isinstance(holder, ast.ExceptHandler):
            target, replacement, kind = node, b"raise", "sauf"
            text = ast.unparse(holder.type) if holder.type else "tout"
        else:
            target, replacement, kind = node, b"return None", "toujours"
            text = ast.unparse(node.exc)[:60] if node.exc else "raise"
        if scope.only and not any(word in text for word in scope.only):
            continue
        if id(target) in seen:
            continue
        seen.add(id(target))
        start = _offset(lines, target.lineno, target.col_offset)
        end = _offset(lines, target.end_lineno, target.end_col_offset)
        # `old`/`new` carry the whole enclosing line(s), widened line by line until the
        # text is unique in the file, so that `apply` mutates this guard and no twin.
        line_start = raw.rfind(b"\n", 0, start) + 1
        line_end = raw.find(b"\n", end)
        line_end = len(raw) if line_end < 0 else line_end
        while raw.count(raw[line_start:line_end]) > 1 and line_end < len(raw):
            following = raw.find(b"\n", line_end + 1)
            line_end = len(raw) if following < 0 else following
        old = raw[line_start:line_end].decode("utf-8")
        new = (raw[line_start:start] + replacement + raw[end:line_end]).decode("utf-8")
        module = scope.path.removeprefix("src/impots/").removesuffix(".py")
        out.append(Mutation(f"{module}:{qualified}:{kind}:{_slug(text)}", scope.path, old,
                            new, scope.tests, f"{qualified} — {kind} {_slug(text)}"))
    return out


def catalogue() -> list[Mutation]:
    mutations = [m for scope in SCOPES for m in generated(scope)] + list(MANUAL)
    ids = [m.id for m in mutations]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    if duplicated:
        raise SystemExit(f"identifiants de mutation en double : {duplicated}")
    return mutations


# --------------------------------------------------------------------------- #
# the run
# --------------------------------------------------------------------------- #
def _dirty() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--", "src", "ui"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout.strip()


def _run(tests: tuple[str, ...]) -> tuple[bool, str]:
    """(killed, by what). Each runner returns non-zero when a test fails."""
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    pytest_files = [t for t in tests if t.endswith(".py")]
    if UI_CHECK in tests:
        done = subprocess.run([NODE, UI_CHECK], cwd=ROOT, capture_output=True, text=True,
                              timeout=TIMEOUT_S)
        if done.returncode != 0:
            failed = [line for line in done.stdout.splitlines() if "✗" in line or "FAIL" in line]
            return True, f"{UI_CHECK} : {(failed or ['échec'])[0].strip()[:100]}"
    if pytest_files:
        done = subprocess.run([PY, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider",
                               *pytest_files], cwd=ROOT, env=env, capture_output=True,
                              text=True, timeout=TIMEOUT_S)
        if done.returncode == 5:
            raise SystemExit(f"aucun test collecté dans {pytest_files}")
        if done.returncode != 0:
            failed = re.findall(r"^(?:FAILED|ERROR) (\S+)", done.stdout, re.MULTILINE)
            return True, (failed or ["échec à la collecte"])[0]
    return False, ""


def apply(mutation: Mutation) -> str:
    """Write the mutation; return the original text to restore."""
    path = ROOT / mutation.path
    original = path.read_text(encoding="utf-8")
    if original.count(mutation.old) != 1:
        raise SystemExit(f"{mutation.id} : le texte à muter apparaît "
                         f"{original.count(mutation.old)} fois dans {mutation.path}")
    path.write_text(original.replace(mutation.old, mutation.new), encoding="utf-8")
    return original


def sweep(mutation: Mutation) -> dict[str, str]:
    original = apply(mutation)
    try:
        killed, by = _run(mutation.tests)
        tier = "ciblé"
        if not killed:
            killed, by = _run(tuple(t for t in WIDE if t not in mutation.tests))
            tier = "large"
    finally:
        (ROOT / mutation.path).write_text(original, encoding="utf-8")
    if killed:
        verdict = "tuée" if mutation.id not in EQUIVALENT else "équivalence à retirer"
    else:
        verdict = "équivalente" if mutation.id in EQUIVALENT else "SURVIVANTE"
        by, tier = EQUIVALENT.get(mutation.id, "aucun test"), "—"
    return {"id": mutation.id, "guard": mutation.guard, "verdict": verdict, "by": by,
            "tier": tier}


# --------------------------------------------------------------------------- #
# the report
# --------------------------------------------------------------------------- #
ROW = re.compile(r"^\| `(?P<id>[^`]+)` \| (?P<guard>.*) \| (?P<verdict>[^|]+) \| "
                 r"(?P<tier>[^|]+) \| (?P<by>.*) \|$")


def read_report(path: Path = REPORT) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROW.match(line)
        if match:
            rows[match["id"]] = {k: v.strip() for k, v in match.groupdict().items()}
    return rows


def _n(count: int, word: str) -> str:
    """« 1 tuée », « 0 survivante », « 98 tuées » : the plural from two on."""
    return f"{count} {word}{'s' if count > 1 else ''}"


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def write_report(rows: dict[str, dict[str, str]], mutations: list[Mutation],
                 commit: str) -> None:
    order = [m.id for m in mutations]
    counts = {v: sum(r["verdict"] == v for r in rows.values())
              for v in ("tuée", "équivalente", "SURVIVANTE", "équivalence à retirer")}
    out = [
        "# Le balayage des gardes de la phase 9",
        "",
        "<!-- Écrit par scripts/sweep_gardes_phase9.py. Ne pas éditer à la main : "
        "tests/test_gardes_phase9.py refuse un rapport qui ne nomme pas chaque garde du "
        "catalogue. -->",
        "",
        f"Balayé le {date.today().isoformat()} sur le commit `{commit[:12]}` (D-229). "
        f"Chaque garde est mutée — sa condition forcée à faux, son refus remplacé — et "
        f"doit faire échouer un test : d'abord ceux de son périmètre (« ciblé »), puis "
        f"toute la suite de la phase 9 (« large »).",
        "",
        f"**{len(rows)} mutations** : {_n(counts['tuée'], 'tuée')}, "
        f"{_n(counts['équivalente'], 'équivalente')} avec sa raison, "
        f"{_n(counts['SURVIVANTE'], 'survivante')}"
        + (f", {_n(counts['équivalence à retirer'], 'équivalence')} qu'un test tue "
           f"désormais" if counts["équivalence à retirer"] else "") + ".",
        "",
        "| Mutation | Garde | Verdict | Étage | Tuée par |",
        "|---|---|---|---|---|",
    ]
    for key in sorted(rows, key=lambda k: (order.index(k) if k in order else len(order), k)):
        r = rows[key]
        out.append(f"| `{r['id']}` | {_cell(r['guard'])} | {r['verdict']} | {r['tier']} | "
                   f"{_cell(r['by'])} |")
    REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--missing", action="store_true",
                        help="ne balayer que les mutations absentes du rapport")
    parser.add_argument("--only", action="append", default=[],
                        help="ne balayer que cette mutation (répétable)")
    parser.add_argument("--list", action="store_true", help="lister le catalogue et sortir")
    args = parser.parse_args(argv)
    mutations = catalogue()
    if args.list:
        for m in mutations:
            print(m.id)
        return 0
    if _dirty():
        raise SystemExit("src/ ou ui/ a des modifications non commitées : le balayage les "
                         "écraserait en restaurant, et le rapport nommerait un commit dont "
                         "il n'a pas balayé le code.")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    rows = read_report() if (args.missing or args.only) else {}
    known = {m.id for m in mutations}
    rows = {k: v for k, v in rows.items() if k in known}
    todo = [m for m in mutations
            if (not args.only or m.id in args.only)
            and (not args.missing or m.id not in rows)]
    unknown = sorted(set(args.only) - known)
    if unknown:
        raise SystemExit(f"mutations inconnues : {unknown}")
    started = time.time()
    for n, mutation in enumerate(todo, 1):
        row = sweep(mutation)
        rows[mutation.id] = row
        print(f"[{n}/{len(todo)} {time.time() - started:4.0f} s] {row['verdict']:<11} "
              f"{mutation.id} — {row['by']}", flush=True)
        write_report(rows, mutations, commit)
    write_report(rows, mutations, commit)
    survivors = [r["id"] for r in rows.values()
                 if r["verdict"] in ("SURVIVANTE", "équivalence à retirer")]
    print(f"{len(rows)} mutations, {len(survivors)} à traiter : {survivors}")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
