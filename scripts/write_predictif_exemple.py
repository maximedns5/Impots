#!/usr/bin/env python3
"""Render docs/PREDICTIF_EXEMPLE.md — l'exemple au dossier de PHASE9_SPEC §9.4 (D-228).

Une baisse de l'IR d'environ 5 Md€ : Δb à dix ans à θ = ½, les bornes de la boîte θ, la
décomposition par source, sous deux scénarios de dépense et deux de persistance, avec les
canaux fermés et leur raison. Aucun chiffre n'est saisi dans la page : tout vient de la
machinerie qu'elle illustre, en trois étages.

1. `--price` (lent, `data/` requis) : UNE passe de population de l'échantillon rapide pour
   la première année projetée, sur la population vieillie (la voie rapide de
   `/predictif/simulate`, D-226), comportement et impulsion macro compris. Les recettes à
   θ = ½ et aux coins de la boîte θ des lignes revendiquées se lisent sur cette même
   population. Le résultat va dans `reports/exemple_predictif.json`, bloc
   `premiere_annee`, avec le commit dont le code l'a produit.
2. Par défaut (rapide, comptes APU et document Mésange requis) : la chaîne
   (`chaine.run`) sous chaque scénario, depuis ce bloc, au θ demandé et à chaque coin de
   la boîte. Résultat dans le même fichier, bloc `trajectoires`.
3. `render(snapshot)` : la page, depuis le fichier seul. C'est ce que rejoue le test
   anti-dérive, sur une machine sans `data/` comme sur une autre.

`tests/test_predictif_exemple.py` tient les trois : la page commitée est le rendu du
fichier commité, et le bloc `trajectoires` est ce que la chaîne calcule aujourd'hui depuis
le bloc `premiere_annee`, là où les comptes et Mésange sont lisibles. La passe de
population n'y est pas rejouée — trois minutes — et la page dit de quel commit elle vient.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

from impots import service

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "PREDICTIF_EXEMPLE.md"
SNAPSHOT = ROOT / "reports" / "exemple_predictif.json"

#: §9.4 : « une baisse de l'IR de 5 Md€ ». Un taux de la première tranche plutôt qu'un
#: rabais uniforme, parce qu'une baisse de barème est le cas d'école de C1 : elle
#: revendique les deux lignes d'élasticité du revenu imposable, et la page montre leur θ.
#: Le pas vient d'une passe de calibrage mécanique sur la population vieillie : 11 % → 9 %
#: y coûte 9,71 Md€, un point de la première tranche vaut donc près de 4,9 Md€, et
#: 11 % → 10 % est la baisse d'un point la plus proche de 5 Md€. La page affiche le coût
#: calculé, pas le rond.
FROM_RATE = 0.11
TO_RATE = 0.10
HORIZON = 10

#: Les scénarios de la page. La persistance n'a d'objet que sous « gelées en volume », la
#: seule règle où la rétroaction s'applique (D-218) : sous l'autre règle, la page le dit
#: au lieu d'afficher deux colonnes égales.
SCENARIOS: tuple[tuple[str, str | None], ...] = (
    ("gele_en_volume", "eteint"),
    ("gele_en_volume", "tenu"),
    ("part_pib_constante", None),
)

WAGE_SOURCE = ("hypothèse déclarée de cet exemple : salaire nominal au rythme du PIB "
               "nominal du scénario de croissance")

MACHINERY = ("Cette page illustre la machinerie ; elle ne recommande rien. La réforme est "
             "choisie pour la pédagogie — une baisse de barème touche le plus de canaux "
             "ouverts — et non parce qu'elle serait souhaitable.")


def _scenarios() -> tuple[Any, Any, Any]:
    from impots.dette.scenarios import GrowthScenario, RateScenario
    from impots.predictif.theta import Theta

    return (GrowthScenario("Croissance réelle 1 %, prix 2 %", 0.01, 0.02),
            RateScenario("Taux implicite tenu à son niveau de 2025", "implicite_tenu"),
            Theta(common=0.5))


def _plain(value: Any) -> Any:
    """What the file holds: tuples become lists, as they will once read back."""
    return json.loads(json.dumps(value, ensure_ascii=False))


# --------------------------------------------------------------------------- #
# 1. La passe de population (lente)
# --------------------------------------------------------------------------- #
def _commit() -> str:
    """The commit whose code prices the pass. A dirty `src/` is refused: the snapshot
    would name a commit whose code it did not run."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True,
                              text=True).stdout.strip()

    if git("status", "--porcelain", "--", "src"):
        raise SystemExit("src/ a des modifications non commitées : la passe porterait le "
                         "nom d'un commit dont elle n'a pas fait tourner le code.")
    return git("rev-parse", "HEAD")


def price() -> dict[str, Any]:
    from impots.api.schemas import PopulationSimulateRequest, ReformSpec
    from impots.behavioural.store import load as load_store
    from impots.engine import baseline
    from impots.engine.reforms import read_ir_parameters
    from impots.predictif import annuel, chaine, comportement
    from impots.predictif import theta as theta_module

    growth, _, theta = _scenarios()
    year = chaine.START_YEAR + 1
    bareme = [dict(b) for b in read_ir_parameters(baseline(), year)["bareme"]]
    first_taxed = next(i for i, b in enumerate(bareme) if b["rate"] > 0)
    if bareme[first_taxed]["rate"] != FROM_RATE:
        raise SystemExit(f"la première tranche du barème {year} est à "
                         f"{bareme[first_taxed]['rate']:.2%}, pas à {FROM_RATE:.0%} : "
                         f"l'exemple décrit une réforme qui n'est plus celle-là.")
    bareme[first_taxed]["rate"] = TO_RATE
    reform = ReformSpec(ir_bareme=bareme)
    uprating = annuel.uprating_for(growth, wage=growth.nominal, source=WAGE_SOURCE,
                                   base_year=int(service.POPULATION_VINTAGE))
    commit = _commit()
    first = service.price_first_year(
        PopulationSimulateRequest(reform=reform, year=year, behavioural=True),
        uprating=uprating, macro=True)
    store = load_store()
    mechanical = -first.cost
    at = comportement.evaluate(theta, mechanical=mechanical, reform=reform, store=store,
                               **first.inputs)
    corners = [{"rows": {k: corner.for_row(k) for k in at.claimed},
                "receipts": comportement.receipts_at(
                    corner, store=store, mechanical=mechanical, reform=reform,
                    **first.inputs)[0]}
               for corner in theta_module.corners(at.claimed, theta)]
    return _plain({
        "commit": commit,
        "calcule": date.today().isoformat(),
        "annee": year,
        "bareme_en_vigueur": read_ir_parameters(baseline(), year)["bareme"],
        "reforme": reform.model_dump(exclude_none=True),
        "salaires": {"taux": growth.nominal, "source": WAGE_SOURCE},
        "cout_eur": first.cost,
        "vue": first.view,
        "note": first.note,
        "impulsion": first.impulse,
        "non_couverts": first.uncovered,
        "comportement": {"recettes": at.receipts, "boite": at.box, "grade": at.grade,
                         "lignes": at.claimed, "coins": corners},
    })


# --------------------------------------------------------------------------- #
# 2. La chaîne (rapide)
# --------------------------------------------------------------------------- #
def trajectories(first: dict[str, Any], *, start: Any, macro_store: Any,
                 store: Any = None) -> list[dict[str, Any]]:
    """Every scenario's paths from the priced first year: at θ, without the loop, and at
    each corner of the θ box — the claimed rows, and the multiplier where the loop
    applies. The corners are read as `exploration.conditional_debt` reads them, and a Δb
    at θ outside their range is refused for the same reason."""
    from impots.behavioural.store import load as load_store
    from impots.dette.path import SHIPPED
    from impots.predictif import chaine, exploration, retroaction
    from impots.predictif import theta as theta_module
    from impots.predictif.comportement import AtTheta
    from impots.predictif.theta import MACRO_ROW, ThetaError

    growth, rate, theta = _scenarios()
    store = store if store is not None else load_store()
    year = int(first["annee"])
    behaviour = first["comportement"]
    claimed = tuple(behaviour["lignes"])

    def at(receipts: float, box: tuple[float, float] | None = None) -> AtTheta:
        return AtTheta(receipts=receipts, grade=behaviour["grade"],
                       box=box or (receipts, receipts), claimed=claimed)

    def receipts_at(corner: Any) -> float:
        rows = {k: corner.for_row(k) for k in claimed}
        (match,) = [c["receipts"] for c in behaviour["coins"] if c["rows"] == rows]
        return float(match)

    def run(at_theta: Any, behaved: AtTheta, *, loop: bool, spending: Any,
            persistence: str | None) -> Any:
        costs = chaine.ReformCosts(
            by_year={year: float(first["cout_eur"])}, carry=chaine.CARRY,
            behavioural={year: behaved},
            impulses={year: dict(first["impulsion"])} if loop else None,
            uncovered=dict(first["non_couverts"]))
        return chaine.run(start, horizon=HORIZON, costs=costs, spending=spending,
                          growth=growth, rate=rate, theta=at_theta, store=store,
                          persistence=persistence, macro_store=macro_store)

    central = at(float(behaviour["recettes"]), tuple(behaviour["boite"]))
    out = []
    for rule, persistence in SCENARIOS:
        spending = SHIPPED[rule]
        looped = rule == retroaction.SPENDING_RULE
        full = run(theta, central, loop=True, spending=spending, persistence=persistence)
        unlooped = run(theta, central, loop=False, spending=spending, persistence=None)
        keys = [*claimed, *((MACRO_ROW,) if looped else ())]
        corners = [(exploration.corner_label(corner, keys),
                    run(corner, at(receipts_at(corner)), loop=True, spending=spending,
                        persistence=persistence).delta[-1])
                   for corner in theta_module.corners(keys, theta)]
        low, high = min(v for _, v in corners), max(v for _, v in corners)
        if not low - exploration.MONOTONE_SLACK <= full.delta[-1] <= (
                high + exploration.MONOTONE_SLACK):
            raise ThetaError(f"{spending.name} : Δb à θ sort des coins — un effet n'est "
                             f"pas monotone en son θ, et la boîte ne se lit pas aux coins.")
        out.append({
            "regle": rule, "depense": spending.name, "persistance": persistence,
            "persistance_libelle": retroaction.PERSISTENCE_LABELS.get(persistence or ""),
            "annees": full.years, "reference": full.reference, "reforme": full.reform,
            "delta": full.delta, "delta_mecanique": full.delta_mechanical,
            "delta_sans_retroaction": unlooped.delta, "ecart_pib": full.gdp_gap,
            "tranches": [{"source": s.source, "label": s.label, "computed": s.computed,
                          "reason": s.reason, "low": s.low, "high": s.high}
                         for s in full.decomposition.slices],
            "coins": [{"label": label, "delta": value} for label, value in corners],
            "theta": full.theta, "conventions": full.conventions, "absent": full.absent,
            "fermes": full.closed,
        })
    return _plain(out)


def _start() -> Any:
    from impots.dette import reference
    from impots.predictif import chaine

    return reference.start_from_accounts(chaine.START_YEAR)


def _macro_store() -> Any:
    from impots.macro import store

    return store.load()


# --------------------------------------------------------------------------- #
# 3. La page (depuis le fichier seul)
# --------------------------------------------------------------------------- #
#: One pass, so that the thousands' comma, the decimal point and the minus never step on
#: each other's replacement.
_FRENCH = str.maketrans({",": "\u202f", ".": ",", "-": "\u2212"})


def _fr(x: float, decimals: int = 2, *, sign: bool = True) -> str:
    """Un NOMBRE en écriture française, jamais une phrase (la leçon de
    `write_explorer_example._fr`)."""
    return f"{x:{'+' if sign else ''},.{decimals}f}".translate(_FRENCH)


def _pt(x: float, decimals: int = 2) -> str:
    """Un ratio au PIB, en points."""
    return _fr(x * 100, decimals) + "\u00a0pt"


def _pc(x: float, decimals: int = 1) -> str:
    return _fr(x * 100, decimals, sign=False) + "\u00a0%"


def _md(x: float, decimals: int = 2, *, sign: bool = False) -> str:
    return _fr(x / 1e9, decimals, sign=sign) + "\u00a0Md€"


def _name(t: dict[str, Any]) -> str:
    if t["persistance"] is None:
        return f"{t['depense']} (sans boucle : persistance sans objet)"
    return f"{t['depense']} · {t['persistance_libelle'].lower()}"


def _holders(convention: str, paths: list[dict[str, Any]]) -> str:
    """Where a convention applies: everywhere, under a whole spending rule, or under the
    scenarios named one by one."""
    holders = [t for t in paths if convention in t["conventions"]]
    if len(holders) == len(paths):
        return ""
    rules = {t["depense"] for t in holders}
    if all(t in holders for t in paths if t["depense"] in rules):
        return ", sous " + " et ".join(f"« {r} »" for r in sorted(rules))
    return ", sous " + " et ".join(f"« {_name(t)} »" for t in holders)


def _first_bracket(first: dict[str, Any]) -> tuple[float, float]:
    """The first taxed bracket's rate, in force and reformed, read from the FILE: the
    page describes the reform that was priced, not the one the constants now name."""
    law, reform = first["bareme_en_vigueur"], first["reforme"]["ir_bareme"]
    i = next(i for i, b in enumerate(law) if b["rate"] > 0)
    return law[i]["rate"], reform[i]["rate"]


def render(snapshot: dict[str, Any]) -> str:
    from impots.dette.path import BANNER as DEBT_BANNER
    from impots.predictif.chaine import BANNER

    first = snapshot["premiere_annee"]
    paths = snapshot["trajectoires"]
    start = snapshot["depart"]
    hyp = snapshot["hypotheses"]
    behaviour = first["comportement"]
    year, last = first["annee"], paths[0]["annees"][-1]
    looped = [t for t in paths if t["persistance"] is not None]
    lines: list[str] = []
    add = lines.append

    add(f"# Exemple prédictif : une baisse de l'IR d'environ 5 Md€, sa dette à {HORIZON} ans")
    add("")
    add("<!-- Généré par scripts/write_predictif_exemple.py depuis "
        "reports/exemple_predictif.json. Ne pas éditer à la main : "
        "tests/test_predictif_exemple.py refuse une page qui dérive. -->")
    add("")
    add(f"> **{MACHINERY}**")
    add(">")
    add(f"> {BANNER}")
    add(">")
    add(f"> {DEBT_BANNER}")
    add("")
    add("L'exemple que PHASE9_SPEC §9.4 met au dossier, et D-228 le consigne. Chaque nombre "
        "ci-dessous sort de la chaîne de la phase 9 telle qu'elle est : rien n'est saisi, "
        "et le script qui écrit cette page la réécrit à l'identique ou le test échoue.")
    add("")

    # --- la réforme ------------------------------------------------------------- #
    add("## La réforme et sa première année")
    add("")
    was, now = _first_bracket(first)
    add(f"Le taux de la première tranche du barème de l'IR passe de {_pc(was, 0)} à "
        f"{_pc(now, 0)}, les seuils et les autres taux inchangés, à partir de {year}.")
    add("")
    add("| Tranche à partir de | Taux en vigueur | Taux de la réforme |")
    add("|---:|---:|---:|")
    for old, new in zip(first["bareme_en_vigueur"], first["reforme"]["ir_bareme"],
                        strict=True):
        add(f"| {_fr(old['threshold'], 0, sign=False)}\u00a0€ | {_pc(old['rate'], 0)} | "
            f"{_pc(new['rate'], 0)} |")
    add("")
    add(f"- **Coût mécanique de {year}** : {_md(first['cout_eur'])}, une passe de "
        f"l'échantillon rapide, vue « {first['vue']} ». {first['note']}")
    add(f"- **Comportement à θ = ½** : la réforme coûte {_md(-behaviour['recettes'], 3)} "
        f"une fois les réponses comptées ; boîte θ de la première année "
        f"{_md(-behaviour['boite'][1], 3)} à {_md(-behaviour['boite'][0], 3)}, aux coins des "
        f"lignes revendiquées ({', '.join(f'`{k}`' for k in behaviour['lignes'])}). "
        f"Grade : {behaviour['grade']}.")
    impulse = ", ".join(f"{k} {_md(v, sign=True)}" for k, v in first["impulsion"].items())
    add(f"- **Impulsion macro**, par variante de Mésange, expansionniste positive : "
        f"{impulse}.")
    if first["non_couverts"]:
        add("- **Sans impulsion** : " + " ; ".join(
            f"{k} — {v}" for k, v in sorted(first["non_couverts"].items())) + ".")
    add(f"- **Calcul** : passe du {first['calcule']}, commit `{first['commit'][:12]}`. "
        f"La chaîne porte ce coût en part de PIB constante au-delà de {year} (la version "
        f"rapide de `/predictif/simulate`) : les années suivantes sont une convention, "
        f"pas un chiffrage.")
    add("")

    # --- les hypothèses --------------------------------------------------------- #
    add("## Les hypothèses nommées")
    add("")
    add(f"- Croissance : {hyp['croissance']}. Taux : {hyp['taux']}.")
    add(f"- Salaires de la population vieillie : {_pc(first['salaires']['taux'], 2)} par "
        f"an, {first['salaires']['source']}.")
    rows = ", ".join(f"`{k}`" for k in looped[0]["theta"])
    add(f"- θ = ½ sur chaque ligne ouverte, le centre publié de chacune ({rows}). La "
        f"boîte θ déplace à 0 et à 1 les seules lignes que la réforme revendique, et le "
        f"multiplicateur là où la boucle s'applique ; les autres θ ne sont lus par aucun "
        f"canal de cette réforme.")
    add(f"- Départ : comptes APU {start['annee']}, dette {_pc(start['dette'])} du PIB, "
        f"solde primaire {_fr(start['solde_primaire'] * 100, 1)}\u00a0% du PIB, taux "
        f"implicite {_pc(start['taux_implicite'], 2)}, PIB {_md(start['pib_eur'])}.")
    add("")

    # --- le chiffre --------------------------------------------------------------- #
    add(f"## Δb en {last}, à θ = ½, et la boîte θ")
    add("")
    add("Δb est la dette de la réforme moins celle de la référence, en points de PIB, sous "
        "les mêmes scénarios : positif, la réforme alourdit la dette.")
    add("")
    add(f"| Scénario | Δb {last} à θ = ½ | Boîte θ, aux coins | Le signe tient-il ? |")
    add("|---|---:|---:|---|")
    for t in paths:
        values = [c["delta"] for c in t["coins"]]
        held = (all(v > 0 for v in values) or all(v < 0 for v in values))
        add(f"| {_name(t)} | {_pt(t['delta'][-1])} | {_pt(min(values))} à "
            f"{_pt(max(values))} | {'oui, à chaque coin' if held else 'non : dépend de θ'} |")
    add("")
    add("La boîte est l'étendue de Δb quand chaque θ revendiqué parcourt [0 ; 1], lue aux "
        "coins après contrôle de monotonie : ni un intervalle de probabilité, ni une somme "
        "de tranches.")
    add("")
    for t in paths:
        ranked = sorted(t["coins"], key=lambda c: c["delta"])
        if ranked[0]["delta"] < 0 < ranked[-1]["delta"]:
            add(f"Sous « {_name(t)} », le signe de Δb change d'un coin à l'autre : "
                f"{_pt(ranked[0]['delta'])} au coin ({ranked[0]['label']}), "
                f"{_pt(ranked[-1]['delta'])} au coin ({ranked[-1]['label']}). La réforme y "
                f"alourdit ou allège la dette selon où l'on place les effets dans leurs "
                f"fourchettes publiées : la chaîne ne tranche pas, et le dit.")
            add("")

    # --- la décomposition --------------------------------------------------------- #
    add(f"## La décomposition par source, en {last}")
    add("")
    add("Le chiffre central se décompose dans l'ordre où la chaîne l'assemble : le coût "
        "mécanique seul, puis les recettes à θ = ½ du comportement, puis la boucle "
        "PIB → recettes en ses deux termes — le solde primaire que Mésange rend, recettes "
        "et dépenses induites, et le PIB de la réforme, qui divise sa dette et pèse donc à "
        "proportion du ratio de dette lui-même. Chaque terme est la différence entre deux "
        "étapes de la chaîne, et la somme tombe juste ; dans un autre ordre, les termes ne "
        "pèseraient pas tout à fait pareil.")
    add("")
    add("| Scénario | Mécanique | Comportement | Rétroaction : solde | Rétroaction : PIB "
        "| Δb |")
    add("|---|---:|---:|---:|---:|---:|")
    for t in paths:
        mechanical, unlooped, delta = (t["delta_mecanique"][-1],
                                       t["delta_sans_retroaction"][-1], t["delta"][-1])
        if t["ecart_pib"] is None:
            balance = denominator = "absente"
        else:
            # The reform's ratio is (reference + extra debt) / (1 + y): the extra debt
            # with the loop's balance, before the GDP divides it, is reform × (1 + y) −
            # reference, and the GDP's own share is what the division takes off.
            raw = t["reforme"][-1] * (1.0 + t["ecart_pib"][-1]) - t["reference"][-1]
            balance, denominator = _pt(raw - unlooped), _pt(delta - raw)
        add(f"| {_name(t)} | {_pt(mechanical)} | {_pt(unlooped - mechanical)} | "
            f"{balance} | {denominator} | {_pt(delta)} |")
    add("")
    add("Les tranches de la chaîne, chacune sur son seul axe, au même horizon — à ne pas "
        "additionner (`dette.decomposition`) :")
    add("")
    for t in paths:
        add(f"- **{_name(t)}**")
        for s in t["tranches"]:
            if s["computed"]:
                add(f"  - {s['label']} : dette de la réforme de {_pc(s['low'][-1], 2)} à "
                    f"{_pc(s['high'][-1], 2)} du PIB.")
            else:
                add(f"  - {s['label']} : non calculée. {s['reason']}")
    add("")

    # --- les coins -------------------------------------------------------------- #
    add("## Les coins de la boîte θ")
    add("")
    for t in paths:
        add(f"- **{_name(t)}** : " + " ; ".join(
            f"{c['label']} → {_pt(c['delta'])}" for c in t["coins"]) + ".")
    add("")

    # --- année par année ---------------------------------------------------------- #
    add("## Année par année, à θ = ½")
    add("")
    add("| Année | " + " | ".join(_name(t) for t in paths) + " |")
    add("|---|" + "---:|" * len(paths))
    for i, y in enumerate(paths[0]["annees"]):
        tag = "" if y == year else " *(report)*"
        add(f"| {y}{tag} | " + " | ".join(_pt(t["delta"][i], 3) for t in paths) + " |")
    add("")
    add(f"Les niveaux, en {last} : " + " ; ".join(
        f"{_name(t)}, référence {_pc(t['reference'][-1])} et réforme "
        f"{_pc(t['reforme'][-1])} du PIB" for t in paths) + ". Le niveau dépend de "
        "scénarios que personne ne peut sourcer ; l'écart en dépend beaucoup moins, et "
        "c'est lui le chiffre.")
    add("")

    # --- ce qui manque ------------------------------------------------------------ #
    add("## Les canaux fermés, et pourquoi")
    add("")
    closed = {k: v for t in looped for k, v in t["fermes"].items()}
    for name, reason in closed.items():
        add(f"- **{name}** : {reason}")
    unlooped_only = {k: v for t in paths if t["persistance"] is None
                     for k, v in t["fermes"].items() if k not in closed}
    for name, reason in unlooped_only.items():
        add(f"- **{name}**, sous « {paths[-1]['depense']} » seulement : {reason}")
    add("")
    add("## Ce qui est absent, et les conventions")
    add("")
    for t in paths:
        for name, reason in t["absent"].items():
            add(f"- Absent, {_name(t)} — {name} : {reason}")
    for convention in dict.fromkeys(c for t in paths for c in t["conventions"]):
        add(f"- Convention{_holders(convention, paths)} : {convention}")
    add("")

    # --- refaire ------------------------------------------------------------------ #
    add("## Refaire le calcul")
    add("")
    add("- `python scripts/write_predictif_exemple.py --price` : la passe de population "
        "(trois minutes, `data/` requis), puis la chaîne et la page.")
    add("- `python scripts/write_predictif_exemple.py` : la chaîne et la page depuis la "
        "première année du fichier (comptes APU et document Mésange requis).")
    add("- La même réforme sous d'autres scénarios ou un autre θ : `POST /predictif/simulate`"
        " ou le panneau prédictif de la page ; chaque autre combinaison est un autre "
        "calcul, sous ses propres noms.")
    add("")
    return "\n".join(lines)


def build(first: dict[str, Any]) -> dict[str, Any]:
    growth, rate, _ = _scenarios()
    start = _start()
    return _plain({
        "premiere_annee": first,
        "hypotheses": {"croissance": growth.name, "taux": rate.name, "horizon": HORIZON},
        "depart": {"annee": start.year, "dette": start.debt_ratio,
                   "solde_primaire": start.primary_balance,
                   "taux_implicite": start.implicit_rate, "pib_eur": start.gdp_eur},
        "trajectoires": trajectories(first, start=start, macro_store=_macro_store()),
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--price", action="store_true",
                        help="refaire la passe de population (lente, data/ requis)")
    args = parser.parse_args(argv)
    if args.price:
        first = price()
    else:
        first = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["premiere_annee"]
    snapshot = build(first)
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    OUT.write_text(render(snapshot), encoding="utf-8")
    print(f"écrit {SNAPSHOT.relative_to(ROOT)} et {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
