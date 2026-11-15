"""Extrait de l'archive du Journal officiel les articles qui vérifient les mesures votées
(D-413).

Légifrance refuse les sessions de travail (403) ; la DILA publie la même base, le texte
publié au JO article par article, sous les mêmes identifiants (JORFTEXT…, JORFARTI…).
La vérification de `jumeau/historique/mesures_votees.yaml` se refait ainsi :

1. Télécharger l'archive complète du 8 novembre 2026 (1,75 Go, Licence Ouverte) :

       curl -o data/raw/Freemium_jorf_global_20261108-140000.tar.gz \\
         https://echanges.dila.gouv.fr/OPENDATA/JORF/Freemium_jorf_global_20261108-140000.tar.gz

   Elle est manifestée dans `data/raw/MANIFEST.json` (sha256 6e09df41…eb1a,
   1 754 209 938 octets) ; elle n'entre pas dans git. La DILA remplace l'archive
   complète chaque semaine : une archive plus récente se lit de même, mais n'est pas
   celle que D-413 a lue.

2. En extraire les articles (une vingtaine de minutes, une lecture en flux) :

       .venv/bin/python -I scripts/jumeau_jorf_extraire.py \\
         data/raw/Freemium_jorf_global_20261108-140000.tar.gz data/interim/jorf.jsonl

   Sont gardés : les textes et articles des lois signées depuis le 1er juin 2009, et des
   décrets et ordonnances dont le titre nomme l'assurance chômage, la prime d'activité,
   le RSA, l'AAH, le minimum vieillesse ou le prélèvement à la source, plus les numéros
   passés par `--numeros`. D-413 en a tiré 29 593 enregistrements.

   L'histoire longue (D-446) recule la borne : `--depuis 1994-06-01 --jusqua 2009-06-01`
   garde les lois de cette période, et les décrets et ordonnances dont le titre nomme
   une cotisation, la CSG ou la CRDS (`MOTS_AVANT_2009`), vers un autre extrait.

3. Recouper la base : `scripts/jumeau_jorf_verifier.py` (voir sa docstring).

Une ligne par enregistrement, en JSON : `type` (« texte » ou « article »), `cid`
(JORFTEXT), `nature`, `num`, `date` (signature), et pour un article son `id`
(JORFARTI), `publi`, `article` (numéro) et `texte` (le corps, sans balises).
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from pathlib import Path

DEPUIS = "2009-06-01"
MOTS = ("assurance chômage", "prime d'activité", "revenu de solidarité active",
        "allocation aux adultes handicapés", "minimum vieillesse",
        "allocation de solidarité aux personnes âgées", "prélèvement à la source")
CONTEXTE = re.compile(rb'<TEXTE cid="(JORFTEXT\d+)" date_publi="([^"]*)" '
                      rb'date_signature="([^"]*)" nature="([^"]*)" nor="[^"]*" '
                      rb'num="([^"]*)"')
#: Les mots d'un titre de décret ou d'ordonnance gardé avant 2009 (D-446).
MOTS_AVANT_2009 = ("cotisation", "contribution sociale généralisée",
                   "remboursement de la dette sociale")
TITRE_TXT = re.compile(rb"<TITRE_TXT[^>]*>(.*?)</TITRE_TXT>", re.S)


def _champ(balise: bytes, contenu: bytes) -> str:
    m = re.search(rb"<" + balise + rb">(.*?)</" + balise + rb">", contenu, re.S)
    return m.group(1).decode() if m else ""


def garder(nature: str, numero: str, date: str, titre: str, numeros: set[str],
           depuis: str = DEPUIS, jusqua: str | None = None) -> bool:
    if jusqua is not None and not date < jusqua:
        return numero in numeros
    if nature == "LOI":
        return date >= depuis
    if nature in ("DECRET", "ORDONNANCE"):
        if depuis != DEPUIS:
            titre, mots = titre.lower(), MOTS_AVANT_2009
        else:
            mots = MOTS
        return numero in numeros or (date >= depuis and any(m in titre for m in mots))
    return False


def extraire(archive: Path, sortie: Path, numeros: set[str], depuis: str = DEPUIS,
             jusqua: str | None = None) -> tuple[int, int]:
    lus = gardes = 0
    sortie.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r|gz") as tar, sortie.open("w", encoding="utf-8") as f:
        for membre in tar:
            if not membre.isfile():
                continue
            lus += 1
            est_article = "/article/" in membre.name
            if not (est_article or "/texte/version/" in membre.name):
                continue
            contenu = tar.extractfile(membre).read()  # type: ignore[union-attr]
            if not est_article:
                nature, numero = _champ(b"NATURE", contenu), _champ(b"NUM", contenu)
                date, titre = _champ(b"DATE_TEXTE", contenu), _champ(b"TITREFULL", contenu)
                if garder(nature, numero, date, titre, numeros, depuis, jusqua):
                    f.write(json.dumps({"type": "texte", "cid": _champ(b"ID", contenu),
                                        "nature": nature, "num": numero, "date": date,
                                        "titre": titre}, ensure_ascii=False) + "\n")
                    gardes += 1
                continue
            ctx = CONTEXTE.search(contenu)
            if not ctx:
                continue
            cid, publi, date, nature, numero = (x.decode() for x in ctx.groups())
            t = TITRE_TXT.search(contenu)
            if not garder(nature, numero, date, t.group(1).decode() if t else "", numeros,
                          depuis, jusqua):
                continue
            corps = re.sub(r"<[^>]+>", " ", _champ(b"BLOC_TEXTUEL", contenu))
            f.write(json.dumps({"type": "article", "cid": cid, "id": _champ(b"ID", contenu),
                                "nature": nature, "num": numero, "date": date,
                                "publi": publi, "article": _champ(b"NUM", contenu),
                                "texte": re.sub(r"\s+", " ", corps).strip()},
                               ensure_ascii=False) + "\n")
            gardes += 1
    return lus, gardes


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("archive", type=Path)
    p.add_argument("sortie", type=Path)
    p.add_argument("--numeros", default="2017-1390,2018-1197",
                   help="décrets ou ordonnances à garder quel que soit leur titre")
    p.add_argument("--depuis", default=DEPUIS, help="première date de signature gardée")
    p.add_argument("--jusqua", default=None, help="date de signature exclue (D-446)")
    a = p.parse_args()
    lus, gardes = extraire(a.archive, a.sortie, set(a.numeros.split(",")), a.depuis,
                           a.jusqua)
    print(f"{lus} fichiers lus, {gardes} enregistrements gardés dans {a.sortie}")


if __name__ == "__main__":
    main()
