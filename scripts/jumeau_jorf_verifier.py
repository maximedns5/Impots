"""Recoupe la base des mesures votées contre l'extrait du Journal officiel (D-413).

Après `scripts/jumeau_jorf_extraire.py` (sa docstring dit où prendre l'archive de la DILA
et où la poser) :

    PYTHONPATH=src .venv/bin/python scripts/jumeau_jorf_verifier.py data/interim/jorf.jsonl

Pour chaque mesure « vérifiée », chaque URL de source doit désigner un article de
l'extrait ; le premier doit appartenir au texte cité, avec le même numéro, la même date
de signature et la même nature. Le script imprime les écarts et sort en erreur s'il y en
a. Il ne relit pas les paramètres : ceux-ci se relisent à l'œil dans l'article, que
`--article NUM ART` ou `--cherche NUM MOTIF` (NUM « * » pour tous les textes) affichent.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from impots.jumeau import votees

NATURES = {"LOI": "loi", "DECRET": "décret", "ORDONNANCE": "ordonnance"}


def charger(extrait: Path) -> list[dict]:
    with extrait.open(encoding="utf-8") as f:
        return [json.loads(ligne) for ligne in f]


def recouper(enregistrements: list[dict]) -> list[str]:
    articles = {r["id"]: r for r in enregistrements if r["type"] == "article"}
    ecarts = []
    for m in votees.mesures():
        if m.verification.statut != "vérifiée":
            continue
        lus = []
        for url in m.verification.sources:
            aid = url.rsplit("/", 1)[1]
            if aid not in articles:
                ecarts.append(f"{m.id} : {aid} absent de l'extrait")
            else:
                lus.append(articles[aid])
        if lus:
            a = lus[0]
            attendu = (m.texte.numero, m.texte.date.isoformat(), m.texte.nature)
            lu = (a["num"], a["date"], NATURES.get(a["nature"], a["nature"]))
            if lu != attendu:
                ecarts.append(f"{m.id} : la base dit {attendu}, le JO {lu}")
    return ecarts


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("extrait", type=Path)
    p.add_argument("--article", nargs=2, metavar=("NUM", "ART"))
    p.add_argument("--cherche", nargs=2, metavar=("NUM", "MOTIF"))
    a = p.parse_args()
    enregistrements = charger(a.extrait)
    if a.article or a.cherche:
        num = (a.article or a.cherche)[0]
        for r in enregistrements:
            if r["type"] != "article" or (num != "*" and r["num"] != num):
                continue
            if a.article and r["article"].strip() == a.article[1]:
                print(f"== {r['num']} art. {r['article']} {r['id']}\n{r['texte']}\n")
            elif a.cherche and (t := re.search(a.cherche[1], r["texte"])):
                debut = max(0, t.start() - 250)
                print(f"{r['num']} art. {r['article']} {r['id']} … "
                      f"{r['texte'][debut:t.end() + 250]}\n")
        return
    ecarts = recouper(enregistrements)
    for e in ecarts:
        print(e)
    n = sum(m.verification.statut == "vérifiée" for m in votees.mesures())
    print(f"{n} mesures vérifiées recoupées, {len(ecarts)} écart(s)")
    sys.exit(1 if ecarts else 0)


if __name__ == "__main__":
    main()
