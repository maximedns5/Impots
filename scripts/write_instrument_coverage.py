#!/usr/bin/env python3
"""Render docs/COVERAGE_INSTRUMENTS.md from impots.instrument_coverage.

Every number in the output is computed from the table. None is typed — the same rule
scripts/write_plf_coverage.py follows, and for the same reason: a coverage document
that drifts from the code it describes will be believed on the day it matters.
"""

from __future__ import annotations

from pathlib import Path

from impots import instrument_coverage as ic

OUT = Path("docs/COVERAGE_INSTRUMENTS.md")

FAMILIES = (("produits", "§2.3.1 — Produits"),
            ("personnes", "§2.3.2 — Personnes"),
            ("entreprises", "§2.3.3 — Entreprises"))

BUCKET_MEANING = {
    "A": "chiffré sur la couche microsimulation",
    "B": "chiffré sur la couche agrégée (§2.2)",
    "C": "sous gate — le gate est nommé",
    "D": "refusé — la raison est affichée",
}


def _row(i: ic.Instrument) -> str:
    if i.bucket in ("A", "B"):
        what = ", ".join(f"`{n}`" for n in i.prices_with) if i.prices_with else "—"
    elif i.bucket == "C":
        what = f"gate : {i.gate}"
    else:
        what = "refus"
    live = " *(déjà en place)*" if i.already_live else ""
    detail = i.reason or i.note
    return f"| {i.label}{live} | **{i.bucket}** | {what} | {detail} |"


def render() -> str:
    priced, unbuilt = ic.priced(), ic.classified_but_unbuilt()
    added = ic.new_in_phase_8()
    lines = [
        "# Couverture des instruments — ce que ce laboratoire sait chiffrer",
        "",
        "**Généré depuis `src/impots/instrument_coverage.py` par "
        "`scripts/write_instrument_coverage.py`.** Chaque nombre est calculé "
        "depuis la table ; aucun n'est saisi. Et chaque nom que la table prononce — "
        "un bouton, un champ de `FirmReformSpec`, un instrument agrégé — est résolu "
        "contre le code réel par `tests/test_instrument_coverage.py` : une ligne qui "
        "prétend chiffrer ce que l'outil ne chiffre pas est le défaut que ce document "
        "existe pour empêcher, et celui qu'aucun lecteur ne rattraperait.",
        "",
        f"Inventaire transcrit de {ic.SPEC}.",
        "",
        "## Le chiffre",
        "",
        f"Sur **{len(ic.INVENTORY)} instruments** de l'inventaire, **{len(priced)}** "
        f"sont chiffrés aujourd'hui — soit **{ic.share_priced():.0%}**. "
        f"**{len(added)}** l'ont été par cette phase ; le reste était déjà en place.",
        "",
        f"**{len(unbuilt)} lignes sont classées sans être chiffrées**, et c'est la "
        f"distinction qui décide si ce document dit la vérité. Classer la TVA et les "
        f"quatre accises en seau B dit où elles iront, pas qu'elles y sont : leurs "
        f"assiettes ne sont pas au manifeste (`docs/M2_ANCHORS.md`). Les compter comme "
        f"chiffrées gonflerait la revendication de {ic.share_priced():.0%} à "
        f"{(len(priced) + len(unbuilt)) / len(ic.INVENTORY):.0%}, ce qui est exactement "
        f"la surestimation que §2.4 existe pour empêcher.",
        "",
        "## Ce que ce chiffre ne dit pas, et pourquoi",
        "",
        "§2.4 veut la couverture pesée contre l'univers des Voies et Moyens tome I "
        "au-dessus d'un seuil de recettes. Ce document compte des LIGNES, pas des "
        "euros, pour deux raisons qui sont toutes deux des manques et non des choix :",
        "",
        "1. **Le seuil n'a jamais été enregistré.** §9 l'attend comme entrée du journal "
        "des décisions — « Threshold for the §2.4 coverage universe » — et il n'y en a "
        "aucune, ni dans `M0_PHASE8.md` ni dans `DECISIONS.md`. Sans seuil, il n'y a "
        "pas d'univers, et sans univers la revendication n'est pas auditable.",
        "2. **Les recettes par ligne viennent des Voies et Moyens**, que ce dépôt ne "
        "porte pas.",
        "",
        "Compter des lignes met un droit de timbre au même poids qu'une contribution à "
        "quatre milliards. `PLF2027_COVERAGE.md` publie deux titres qui se contredisent "
        "pour cette raison exacte ; la même correction est due ici et ne peut pas "
        "encore être faite.",
        "",
        "## Par bucket",
        "",
        "| bucket | sens | lignes |",
        "|---|---|---|",
    ]
    for bucket in ic.BUCKETS:
        lines.append(f"| **{bucket}** | {BUCKET_MEANING[bucket]} | "
                     f"{len(ic.by_bucket(bucket))} |")
    for family, title in FAMILIES:
        rows = [i for i in ic.INVENTORY if i.family == family]
        lines += ["", f"## {title}", "",
                  "| instrument | bucket | chiffré par / gate | détail |",
                  "|---|---|---|---|"]
        lines += [_row(i) for i in rows]
    lines += ["", "---", "",
              "Les refus ne sont jamais des omissions : ils sont listés ci-dessus avec "
              "leur raison, parce qu'un instrument absent d'un tableau se lit comme un "
              "instrument oublié."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT} — {len(ic.INVENTORY)} instruments, "
          f"{len(ic.priced())} priced ({ic.share_priced():.0%})")
