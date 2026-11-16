"""`python -m impots.sources <action>` : texte, recolter, verifier, valeur, chercher, bilan."""

from __future__ import annotations

import argparse
import collections
import json
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m impots.sources")
    a = p.add_subparsers(dest="action", required=True)
    a.add_parser("texte", help="extraire une fois le texte de chaque document de data/raw/")
    a.add_parser("recolter", help="récolter et relire les nombres cités ; écrire le registre "
                 "et l'inventaire")
    v = a.add_parser("verifier", help="le dépôt cite-t-il encore ce que garde le registre ?")
    v.add_argument("fichier", nargs="?")
    x = a.add_parser("valeur", help="la valeur et la source d'un identifiant")
    x.add_argument("identifiant")
    c = a.add_parser("chercher", help="les entrées qui contiennent tous les mots du motif")
    c.add_argument("motif", nargs="+")
    a.add_parser("bilan", help="les comptes par famille et par statut de relecture")
    args = p.parse_args(argv)

    if args.action == "texte":
        from impots.sources import texte
        from impots.sources.recolte import manifeste

        for fichier, e in sorted(manifeste().items()):
            if e.get("quarantined") or not (texte.RAW / fichier).exists():
                continue
            try:
                n = len(texte.pages(fichier))
                print(f"{fichier} : {n} pages")
            except texte.TexteError as err:
                print(f"{fichier} : non lu ({err})")
        return 0
    if args.action == "recolter":
        from impots.sources import recolte

        reg = recolte.recolter()
        docs = recolte.inventaire(reg)
        print(f"{len(reg)} valeurs, {len(docs)} documents")
        return 0
    if args.action == "verifier":
        from impots.sources import verifier

        ecarts = verifier(args.fichier)
        print("\n".join(ecarts) or "le registre et le dépôt citent les mêmes valeurs")
        return 1 if ecarts else 0
    if args.action == "valeur":
        from impots.sources import entree

        print(json.dumps(entree(args.identifiant), ensure_ascii=False, indent=1))
        return 0
    if args.action == "chercher":
        from impots.sources import chercher

        for e in chercher(" ".join(args.motif)):
            r = e["relecture"]
            print(f"{e['id']} = {e['valeur']} {e['unite']} | {e['document']} "
                  f"{e['localisation']} | {r['statut']} {r.get('page', '')}")
        return 0
    if args.action == "bilan":
        from impots.sources import registre

        par = collections.Counter()
        for e in registre().values():
            par[(e["id"].split(".")[0], e["relecture"]["statut"])] += 1
        for (fam, st), n in sorted(par.items()):
            print(f"{fam:14} {st:28} {n}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
