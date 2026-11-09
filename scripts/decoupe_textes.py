#!/usr/bin/env python
"""Découpe un PLF ou un PLFSS déposé en articles, l'exposé des motifs montants masqués (D-359).

Le but 18 trie les textes de 2021 à 2025 avant d'ouvrir leurs évaluations préalables. Le
dispositif d'un article se lit en clair : ses paramètres sont nécessaires au codage. Son
exposé des motifs annonce parfois le rendement que l'annexe chiffre : il se lit montants
masqués (D-175), chaque montant en euros remplacé par `[montant masqué]` avant toute
lecture. Le texte général d'avant le premier article (le sommaire, l'exposé général) n'est
pas repris, sauf les intitulés du sommaire.

Il refuse un texte où il trouve moins de `MINIMUM_PLAUSIBLE` articles : un découpage qui
rend une liste courte se lirait comme un texte court.

Usage :
    .venv/bin/python scripts/decoupe_textes.py data/raw/plf2021_texte_an_b3360.html ...
Écrit data/interim/textes_retro/<clé>.json et <clé>.md (hors de git).
"""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SORTIE = ROOT / "data" / "interim" / "textes_retro"
MINIMUM_PLAUSIBLE = 20
MASQUE = "[montant masqué]"

#: A euro amount, in figures or words: « 1,2 milliard d'euros », « 300 M€ », « 45 € ».
MONTANT = re.compile(
    r"(?:environ |près de |plus de |moins de )?\d[\d\s\u202f\xa0.,]*"
    r"(?:\s*(?:milliards?|millions?|mds?|md|m|k|mille))?\s*(?:d[’']\s*)?(?:euros?|€)",
    re.IGNORECASE)
#: A count in millions or billions, in figures or words, money or not: over-masking a
#: head count costs nothing, and « 500 millions » alone is often euros.
GRAND = re.compile(
    r"(?:(?:plus |moins |près )?d[’']un |(?:environ |près de |plus de |moins de )?"
    r"(?:\d[\d\s\u202f\xa0.,]*|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|"
    r"quelques|plusieurs|dizaines? de|centaines? de)\s*)(?:milliards?|millions?)"
    r"(?:\s*(?:d[’']\s*)?(?:euros?|€))?|\d[\d,.]*\s*c€(?:/\w+)*", re.IGNORECASE)
ARTICLE = re.compile(r"^Article\s+(liminaire|premier|1\s*er|\d+(?:\s*(?:bis|ter|quater))?)"
                     r"\s*(?::\s*(.*))?$", re.IGNORECASE)


def lignes(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    text = re.sub(r"<(br|p|div|h\d|tr|li|table)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = html_module.unescape(re.sub(r"<[^>]+>", " ", text))
    out = [re.sub(r"[ \t\xa0\u202f]+", " ", line).strip() for line in text.split("\n")]
    return [line for line in out if line]


def numero(raw: str) -> str:
    raw = re.sub(r"\s+", " ", raw.strip().lower())
    return "1" if raw in ("premier", "1 er", "1er") else raw


def masquer(text: str) -> tuple[str, int]:
    count = len(MONTANT.findall(text))
    text = MONTANT.sub(MASQUE, text)
    count += len(GRAND.findall(text))
    return GRAND.sub(MASQUE, text), count


def decouper(path: Path) -> list[dict]:
    rows = lignes(path)
    titres: dict[str, str] = {}
    starts = []
    for i, line in enumerate(rows):
        m = ARTICLE.match(line)
        if not m:
            continue
        num, titre = numero(m[1]), (m[2] or "").strip()
        # The table of contents names each article with its title and a page number.
        if titre and re.search(r"\s\d{1,4}$", titre) and num not in titres:
            titres[num] = re.sub(r"\s\d{1,4}$", "", titre).strip()
            continue
        starts.append((i, num))
    articles = []
    for k, (i, num) in enumerate(starts):
        end = starts[k + 1][0] if k + 1 < len(starts) else len(rows)
        body = rows[i + 1:end]
        cut = next((j for j, line in enumerate(body)
                    if line.lower().startswith("exposé des motifs")), None)
        dispositif = body if cut is None else body[:cut]
        expose = [] if cut is None else body[cut + 1:]
        masque, n = masquer("\n".join(expose))
        articles.append({"numero": num, "intitule": titres.get(num, ""),
                         "dispositif": "\n".join(dispositif), "expose_masque": masque,
                         "montants_masques": n})
    # A table of contents without page numbers repeats each « Article n » with nothing
    # under it; the article is its last occurrence that carries a text.
    kept: dict[str, dict] = {}
    for a in articles:
        if a["dispositif"].strip() or a["expose_masque"].strip():
            kept[a["numero"]] = a
    articles = sorted(kept.values(), key=lambda a: (
        -1 if a["numero"] == "liminaire" else int(re.match(r"\d+", a["numero"])[0])
        if re.match(r"\d+", a["numero"]) else 10**6, a["numero"]))
    for a in articles:
        first = a["dispositif"].split("\n", 1)[0]
        if not a["intitule"] and first and not re.match(r"^(I+\.|[A-Z]\.|\d+°|«)", first):
            a["intitule"] = first[:200]
    if len(articles) < MINIMUM_PLAUSIBLE:
        raise SystemExit(f"{path.name} : {len(articles)} articles trouvés, moins de "
                         f"{MINIMUM_PLAUSIBLE} : le découpage a manqué le format.")
    return articles


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("textes", nargs="+", type=Path)
    args = parser.parse_args()
    SORTIE.mkdir(parents=True, exist_ok=True)
    for path in args.textes:
        key = path.name.split("_texte_")[0]
        articles = decouper(path)
        (SORTIE / f"{key}.json").write_text(json.dumps(
            {"texte": path.name, "articles": articles}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        md = [f"# {key} — {path.name}", ""]
        for a in articles:
            md += [f"## Article {a['numero']} : {a['intitule']}", "", "### Dispositif", "",
                   a["dispositif"], "", "### Exposé des motifs (montants masqués)", "",
                   a["expose_masque"] or "(aucun)", ""]
        (SORTIE / f"{key}.md").write_text("\n".join(md), encoding="utf-8")
        masked = sum(a["montants_masques"] for a in articles)
        print(f"{key} : {len(articles)} articles, {masked} montants masqués")
    return 0


if __name__ == "__main__":
    sys.exit(main())
