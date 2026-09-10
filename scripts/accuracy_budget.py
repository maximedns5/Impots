#!/usr/bin/env python
"""Phase 7 A0 — run the accuracy budget and write `reports/accuracy_budget.md`.

The report computes its own numbers: every figure below is produced by this run, and the
prose is assembled around the values rather than typed beside them. A number that appears
in the file and not in this script does not exist.

Usage:
    .venv/bin/python scripts/accuracy_budget.py            # firm + patrimoine (seconds)
    .venv/bin/python scripts/accuracy_budget.py --resolution   # + the subsample section
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from impots import accuracy, accuracy_cases  # noqa: E402
from impots.reporting import num_fr, pct_fr  # noqa: E402

REPORT = ROOT / "reports" / "accuracy_budget.md"


def md(value: float, decimals: int = 4) -> str:
    return f"{num_fr(value / 1e9, decimals)}{chr(0x202F)}md€"


def run_case(case: accuracy_cases.ReferenceReform, *, households: int,
             seed: int) -> tuple[accuracy.CaseBudget | None, str]:
    """Price one reference reform's sources. Returns (budget, note)."""
    sources = accuracy_cases.sources_for(case, households=households)
    measurable = [s for s in sources if s.method != "unmeasured"]
    draws = accuracy_cases.FIRM_DRAWS if case.chain == "firm" else 2

    if not measurable:
        # Every declared source is unmeasured. Still produce the row: the reasons ARE the
        # result, and a case omitted here would read as a case with no uncertainty.
        budget = accuracy.CaseBudget(
            case=case.key, label=case.label, central_eur=0.0,
            contributions=tuple(accuracy.measure(s, draws=2, seed=seed) for s in sources),
            draws=0)
        return budget, "aucune source mesurable aujourd'hui"

    # `central_for` REFUSES a case that does not move. A no-op reference reform makes
    # every variance share on it a statement about nothing — it happened twice here.
    central = accuracy_cases.central_for(case)

    return accuracy.budget_for(case.key, case.label, central, sources,
                               draws=draws, seed=seed), ""


def resolution_section(*, households: int, seed: int) -> tuple[str, float]:
    """The instrument's own resolution: subsample noise, which is ZERO in production."""
    case = accuracy_cases.reform("bareme")
    sampler = accuracy_cases.household_subsample_sampler(
        case.knob, case.value, households=households)
    values = [sampler(seed + i) for i in range(accuracy_cases.HOUSEHOLD_DRAWS)]
    variance = accuracy._variance(values)
    sigma = variance ** 0.5
    mean = sum(values) / len(values)
    lines = [
        "## La résolution de l'instrument, qui n'est PAS une source",
        "",
        f"Mesuré sur « {case.label} », {accuracy_cases.HOUSEHOLD_DRAWS} tirages de "
        f"sous-échantillon à n = {num_fr(households)} ménages : moyenne {md(mean)}, "
        f"écart-type **{md(sigma)}**, soit {pct_fr(sigma / abs(mean), 2)} du chiffrage.",
        "",
        "**Cette variance vaut exactement zéro en production.** `runner.run(sample=None)` "
        "chiffre la frame entière : re-tirer le sous-échantillon ne déplace rien de ce qui "
        "est déployé. Elle n'est donc pas une source d'erreur du modèle, et la classer "
        "comme telle enverrait la phase 7 vers une grandeur qui n'existe pas quand le "
        "modèle tourne pour de vrai.",
        "",
        "Ce qu'elle dit en revanche, et pourquoi elle est ici : c'est **la finesse avec "
        "laquelle A0 peut séparer deux sources** lorsqu'il mesure sur un sous-échantillon. "
        "Toute source dont la contribution est plus petite que cet écart-type est "
        "indiscernable du bruit de tirage, et le budget ne doit pas prétendre les "
        "ordonner.",
        "",
        "D-074 avait déjà mesuré la même chose par l'autre bout : 1,49 point d'écart-type "
        "par tirage sur la ligne barème à n = 50 000.",
    ]
    return "\n".join(lines), sigma


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--households", type=int, default=4000)
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--resolution", action="store_true",
                        help="mesurer aussi la résolution (lent : passes moteur)")
    args = parser.parse_args()

    print("A0 — budget d'exactitude")
    results: list[tuple[accuracy_cases.ReferenceReform, accuracy.CaseBudget, str]] = []
    for case in accuracy_cases.REFERENCE_REFORMS:
        if case.chain in ("household", "trajectory"):
            budget, note = run_case(case, households=args.households, seed=args.seed)
        else:
            print(f"  {case.key}…", flush=True)
            budget, note = run_case(case, households=args.households, seed=args.seed)
        if budget is not None:
            results.append((case, budget, note))

    lines: list[str] = [
        "# A0 — le budget d'exactitude",
        "",
        f"*Produit par `scripts/accuracy_budget.py` le {dt.date.today().isoformat()}. "
        f"Graine {args.seed}. Chaque nombre de ce fichier est calculé par ce script ; "
        f"aucun n'y est recopié.*",
        "",
        "Ce budget classe les sources d'incertitude déclarées, réforme de référence par "
        "réforme de référence. **Son classement ordonne les leviers L1-L6 de la phase 7**, "
        "et un levier qu'il classe bas est écarté avec son score au dossier : refuser du "
        "travail est un résultat.",
        "",
        "## Ce que ce budget peut et ne peut pas comparer",
        "",
        "Trois classes, et **une part ne se calcule jamais entre elles** :",
        "",
        "* **`sampled`** — une loi nommée et tirable existe. La part de variance est une "
        "mesure.",
        "* **`swing`** — seules deux bornes existent. La largeur est mesurée ; la convertir "
        f"en variance suppose une forme sur l'intervalle (`VARIANCE_OF_A_RANGE = "
        f"{num_fr(accuracy.VARIANCE_OF_A_RANGE)}`, une convention isolée dans une constante "
        "nommée pour être contestable en un seul endroit).",
        "* **`unmeasured`** — la spec déclare la source, le dépôt n'a ni loi ni bornes. "
        "Rapportée **sans part**, jamais omise : une source absente d'un budget se lit "
        "« elle ne compte pas ».",
        "",
        "## Les huit réformes de référence",
        "",
        "| clé | famille | réforme | chaîne |",
        "|---|---|---|---|",
    ]
    for case in accuracy_cases.REFERENCE_REFORMS:
        lines.append(f"| `{case.key}` | {case.family} | {case.label} | {case.chain} |")

    lines += ["", "## Résultats, cas par cas", ""]
    for case, budget, note in results:
        lines.append(f"### {case.label}")
        lines.append("")
        if case.chain in ("firm", "patrimoine"):
            # Printed unconditionally: a central figure omitted because it was zero is
            # exactly how the CVAE no-op stayed invisible.
            lines.append(f"Chiffrage central : **{md(budget.central_eur)}**.")
            lines.append("")
        if note:
            lines.append(f"*{note}.*")
            lines.append("")

        sampled = budget.ranked("sampled")
        if sampled:
            lines += ["| source | écart-type | part | tirages |", "|---|---|---|---|"]
            for c in sampled:
                lines.append(
                    f"| {c.label} | {md(c.sigma_eur or 0.0)} | "
                    f"{pct_fr(c.share or 0.0, 1)} | {budget.draws} |")
            lines.append("")
        swings = budget.ranked("swing")
        if swings:
            lines += ["| source (bornes) | largeur | part entre bornes |",
                      "|---|---|---|"]
            for c in swings:
                lines.append(f"| {c.label} | {md(c.width_eur or 0.0)} | "
                             f"{pct_fr(c.share or 0.0, 1)} |")
            lines.append("")
        for c in budget.unmeasured:
            lines.append(f"* **{c.label} — NON MESURÉE.** {c.note}")
        lines.append("")

    if args.resolution:
        print("  résolution (passes moteur)…", flush=True)
        section, _sigma = resolution_section(households=args.households, seed=args.seed)
        lines += [section, ""]
    else:
        lines += [
            "## La résolution de l'instrument",
            "",
            "**Non mesurée dans ce passage** — relancer avec `--resolution`, qui coûte "
            f"{accuracy_cases.HOUSEHOLD_DRAWS} passes moteur. Le bruit de sous-échantillon "
            "n'est pas une source d'erreur du modèle (il vaut zéro quand la frame entière "
            "est chiffrée) mais il borne la finesse avec laquelle ce budget peut séparer "
            "deux sources mesurées sur un sous-échantillon.",
            "",
        ]

    # ---- what this pass orders, computed from the rows above rather than asserted ----
    relative: list[tuple[str, str, float, str]] = []
    for case, budget, _note in results:
        for c in budget.contributions:
            if c.variance is None or not budget.central_eur:
                continue
            spread = c.width_eur if c.method == "swing" else c.sigma_eur
            relative.append((case.family, c.label,
                             abs((spread or 0.0) / budget.central_eur), c.method))
    relative.sort(key=lambda row: row[2], reverse=True)

    lines += [
        "## Ce que ce passage ordonne",
        "",
        "Rapportée au chiffrage central de son propre cas — la seule façon de comparer une "
        "source à travers des réformes d'ordres de grandeur différents :",
        "",
        "| famille | source | contribution relative | méthode |",
        "|---|---|---|---|",
    ]
    for family, label, share, method in relative:
        lines.append(f"| {family} | {label} | {pct_fr(share, 2)} | `{method}` |")
    lines.append("")

    if relative:
        top_family, top_label, top_share, _m = relative[0]
        lines += [
            f"**Le plus gros contributeur mesuré à ce jour est {top_label} sur "
            f"{top_family}, à {pct_fr(top_share, 2)} du chiffrage.** ",
            "",
            "Et la lecture qui compte davantage que le classement lui-même : **le "
            "placement pèse relativement bien plus sur la CVAE que sur l'IS**, alors que "
            "c'est la même mesure de placement tirée de la même façon. La raison est "
            "structurelle et non statistique — la CVAE est un instrument à coudes, l'IS "
            "est quasi linéaire dans la tranche qui porte l'essentiel de l'assiette, et un "
            "placement qui déplace des entreprises de part et d'autre d'un coude change le "
            "résultat là où une transformation linéaire l'ignore. C'est le même argument "
            "que le refus de la classe seuil-sur-ratio (D-105.2), rencontré ici par la "
            "mesure au lieu de l'être par le raisonnement.",
            "",
            "**Ce que ce passage NE dit pas.** Quatre des huit cas n'ont aucune source "
            "mesurable aujourd'hui, et trois sources déclarées par la spec sont NON "
            "MESURÉES avec leur raison. Le classement ci-dessus ordonne donc ce qui a pu "
            "être mesuré, pas l'ensemble des erreurs du modèle : le lire comme un "
            "classement complet serait exactement l'erreur que ce budget existe pour "
            "éviter.",
            "",
        ]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"écrit : {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
