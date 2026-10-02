#!/usr/bin/env python
"""Découpe le texte du PLF en articles, et confronte le découpage au triage du dépôt.

**Ce script existait comme un commentaire bash.** Le runbook PLF 2027 disait « découper le
texte comme en 2026 : les <h6> portent ARTICLE n : intitulé » — c'est-à-dire que l'étape 2,
chiffrée 2 à 4 heures, reposait sur un découpage à refaire à la main le jour même, sous la
pression d'une parution. Répété à blanc sur le texte 2026 (D-162), il devient une commande.

CE QU'IL FAIT, ET CE QU'IL REFUSE DE SUPPOSER.

* Il extrait chaque `<h6>` portant « ARTICLE n : intitulé », puis le corps jusqu'au `<h6>`
  suivant. Le numéro ET l'intitulé, parce que les catégories de `plf_coverage` sont faites
  pour survivre à une renumérotation et que l'intitulé est ce qui permet de les rattacher.
* Il REFUSE un texte où il ne trouve aucun article, et un texte où il en trouve moins que
  `MINIMUM_PLAUSIBLE`. Un extracteur qui rend zéro article sur un PLF réel ne signale rien
  par lui-même : il rend une liste vide, et une liste vide se propage en « rien à chiffrer ».
  C'est la forme du défaut de 2026 où un extracteur ne cherchant que des tableaux a raté
  l'article le plus gros de toute l'annexe.
* En mode `--contre-triage`, il compare les articles trouvés aux catégories que
  `plf_coverage.ARTICLES` porte déjà, et dit trois choses distinctes : ce qui se rattache,
  ce que le texte porte et que le triage ne connaît pas (**décision de triage NEUVE**), et
  ce que le triage connaît et que le texte ne porte plus (mesure retirée, ou renumérotée).

POURQUOI LE RATTACHEMENT SE FAIT SUR L'INTITULÉ ET NON SUR LE NUMÉRO. Entre le dépôt et le
texte voté, les articles sont renumérotés. Un rattachement par numéro se tromperait en
silence et attribuerait le triage d'une mesure à une autre — le pire résultat possible,
puisqu'il produit un chiffrage plausible sur le mauvais article. Le numéro n'est donc que
de l'affichage.

Usage :
    .venv/bin/python scripts/split_plf_articles.py data/raw/plf2026_texte_an_b1906.html
    .venv/bin/python scripts/split_plf_articles.py <fichier> --contre-triage
"""

from __future__ import annotations

import argparse
import html as html_module
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

#: Un PLF porte des dizaines d'articles. En dessous, le format a changé et le découpage
#: rend une liste partielle — qui se lit comme un texte court, pas comme une panne.
MINIMUM_PLAUSIBLE = 20

_H6 = re.compile(r"<h6[^>]*>(.*?)</h6>", re.I | re.S)
_SECTION = re.compile(r"<(h4|h5)[^>]*>(.*?)</\1>", re.I | re.S)

#: La section fiscale, telle que le texte 2026 la titre. Les articles hors de cette
#: section sont des crédits, des garanties, des dotations : ils ne relèvent pas de ce
#: projet, et les compter comme « décisions de triage neuves » noierait les vraies.
SECTION_FISCALE = "impots et ressources autorisees"
#: Le deux-points peut être pleine largeur (U+FF1A) selon l'outil de publication ; il est
#: écrit en échappement pour qu'aucun caractère ambigu ne traîne dans la source.
#:
#: LE PLF 2027 A TORDU CE MOTIF TROIS FOIS (2026-10-02) : « ARTICLE 23 Instauration… »
#: sans deux-points, « ARTICLE 22 : : Renforcement… » avec deux, et une entité `&#xa0;`
#: que `_texte` ne résolvait pas. Trois articles sur 89 sortaient du découpage sans bruit,
#: dont une mesure fiscale. Le deux-points est donc facultatif et répétable, et le suffixe
#: « bis », « ter »… est gardé : le texte voté en insère, et les écarter ne creuserait
#: aucun trou dans la numérotation.
_SUFFIXE = r"bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies"
_TITRE = re.compile(
    rf"^ARTICLE\s+(\d+(?:\s+(?:{_SUFFIXE}))?|liminaire)(?!\w)\s*(?:[:\uff1a]\s*)*(.+)$",
    re.I | re.S)
_BALISE = re.compile(r"<[^>]+>")


def _texte(html: str) -> str:
    """Balises retirées, TOUTES les entités résolues, espaces normalisés.

    `html.unescape` et non une liste d'entités choisies : la liste ne connaissait pas
    `&#xa0;`, que le PLF 2027 met dans trois titres d'articles.
    """
    return " ".join(html_module.unescape(_BALISE.sub(" ", html)).split())


def normaliser(intitule: str) -> str:
    """Forme comparable d'un intitulé : sans accent, sans ponctuation, en minuscules.

    Les apostrophes typographiques et droites alternent d'une publication à l'autre, et
    « d'aide » contre « d’aide » suffirait à casser un rattachement par égalité stricte.
    """
    sans = "".join(c for c in unicodedata.normalize("NFD", intitule.lower())
                   if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", sans).split())


@dataclass(frozen=True)
class Article:
    numero: str
    intitule: str
    corps: str
    section: str = ""

    @property
    def fiscal(self) -> bool:
        # `in`, pas `startswith` : le titre normalisé commence par le chiffre romain
        # (« i impots et ressources autorisees »), et un startswith rendait ZÉRO article
        # fiscal sur 82 — visiblement faux, donc attrapé tout de suite.
        return SECTION_FISCALE in normaliser(self.section)

    @property
    def cle(self) -> str:
        return normaliser(self.intitule)


def decouper(html: str) -> list[Article]:
    """Les articles du texte, dans l'ordre de publication."""
    entetes: list[tuple[int, int, str]] = []
    for m in _H6.finditer(html):
        entetes.append((m.start(), m.end(), _texte(m.group(1))))

    # Le titre de section (h4) qui précède chaque position. Sans ce bornage, les ~53
    # articles de crédits et de garanties remontent comme « inconnus du triage » et
    # noient les rares vraies décisions neuves.
    sections = [(m.start(), _texte(m.group(2))) for m in _SECTION.finditer(html)
                if m.group(1).lower() == "h4"]

    def section_de(position: int) -> str:
        courante = ""
        for debut, titre in sections:
            if debut < position:
                courante = titre
            else:
                break
        return courante

    articles: list[Article] = []
    for i, (_debut, fin, titre) in enumerate(entetes):
        trouve = _TITRE.match(titre)
        if not trouve:
            continue
        suivant = entetes[i + 1][0] if i + 1 < len(entetes) else len(html)
        articles.append(Article(numero=" ".join(trouve.group(1).lower().split()),
                                intitule=" ".join(trouve.group(2).split()),
                                corps=_texte(html[fin:suivant]),
                                section=section_de(entetes[i][0])))

    if not articles:
        raise SystemExit(
            "aucun article trouvé : les <h6> ne portent plus « ARTICLE n : intitulé ». Le "
            "format a changé et ce découpage rendrait une liste VIDE, qui se lit comme "
            "« rien à chiffrer » au lieu d'une panne. Corriger le motif, pas le seuil.")
    if len(articles) < MINIMUM_PLAUSIBLE:
        raise SystemExit(
            f"{len(articles)} articles seulement, minimum plausible {MINIMUM_PLAUSIBLE} : le "
            f"découpage est partiel. Un PLF en porte des dizaines ; une liste tronquée "
            f"laisserait croire que les articles manquants n'existent pas.")
    # LE TROU DANS LA NUMÉROTATION, seule trace d'un titre qui a changé de forme : 86
    # articles passent le plancher aussi bien que 89, et rien ne disait que trois
    # manquaient au PLF 2027. Un texte déposé ou voté est numéroté sans trou.
    numeros = {int(re.match(r"\d+", a.numero).group()) for a in articles
               if a.numero != "liminaire"}
    manquants = sorted(set(range(min(numeros), max(numeros) + 1)) - numeros) if numeros else []
    if manquants:
        raise SystemExit(
            f"numérotation trouée : article(s) {manquants} absent(s) du découpage, entre "
            f"{min(numeros)} et {max(numeros)}. Un titre a changé de forme et l'article a "
            f"été écarté sans bruit ; corriger le motif, pas la liste.")
    return articles


def contre_triage(tous: list[Article]) -> int:
    """Compare au triage du dépôt. Rend le nombre de décisions NEUVES à prendre.

    Borné à la section fiscale : le triage ne couvre qu'elle, et compter les articles de
    crédits comme des décisions manquantes inventerait du travail.
    """
    from impots.plf_coverage import ARTICLES as TRIES

    articles = [a for a in tous if a.fiscal]
    print(f"\n  section fiscale : {len(articles)} articles sur {len(tous)} "
          f"(les autres sont crédits, garanties, dotations)")

    # LE RATTACHEMENT SE FAIT PAR PRÉFIXE, PAS PAR ÉGALITÉ. `plf_coverage` stocke des
    # intitulés TRONQUÉS (une centaine de caractères), si bien qu'une égalité stricte
    # échouait sur sept articles — dont la CEBGE, que le texte porte en article 4 et que
    # la confrontation annonçait à la fois « absente du texte » et « inconnue du triage ».
    # Deux erreurs opposées sur la même mesure : la répétition à blanc l'a montrée parce
    # qu'elle tournait contre une réponse connue.
    connus = {normaliser(a.intitule): a for a in TRIES}
    vus = {a.cle: a for a in articles}

    def apparie(cle_triee: str) -> str | None:
        if cle_triee in vus:
            return cle_triee
        for cle_texte in vus:
            if cle_texte.startswith(cle_triee) or cle_triee.startswith(cle_texte):
                return cle_texte
        return None

    paires = {c: apparie(c) for c in connus}
    rattaches = sorted(v for v in paires.values() if v)
    neufs = [vus[c] for c in vus if c not in rattaches]
    disparus = [connus[c] for c, v in paires.items() if v is None]
    # pour l'affichage : du côté texte vers le côté trié
    texte_vers_trie = {v: connus[c] for c, v in paires.items() if v}

    print(f"\n=== confrontation au triage de plf_coverage ({len(TRIES)} articles triés) ===")
    print(f"  rattachés par intitulé : {len(rattaches)}")
    for c in rattaches:
        print(f"    art. {vus[c].numero:<4} → {texte_vers_trie[c].bucket:<16} "
              f"{vus[c].intitule[:52]}")

    if disparus:
        print(f"\n  triés mais ABSENTS du texte : {len(disparus)}")
        for a in disparus:
            print(f"    {a.categorie[:44]:<44} ({a.bucket})")
        print("    → mesure retirée du texte, ou intitulé remanié. À vérifier une par une :")
        print("      un rattachement manqué prive la mesure de son triage.")

    print(f"\n  portés par le texte et INCONNUS du triage : {len(neufs)}")
    for a in neufs[:12]:
        print(f"    art. {a.numero:<4} {a.intitule[:64]}")
    if len(neufs) > 12:
        print(f"    … et {len(neufs) - 12} autres")
    print("    → CHACUN est une décision de triage NEUVE, à prendre et à dater du jour même.")
    print("      Un refus préenregistré est une limite ; un refus improvisé est une excuse,")
    print("      et la mention de la date est la seule différence visible.")
    return len(neufs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fichier", type=Path)
    parser.add_argument("--contre-triage", action="store_true",
                        help="confronter le découpage aux catégories de plf_coverage")
    parser.add_argument("--corps", type=int, default=0,
                        help="afficher les N premiers caractères du corps de chaque article")
    args = parser.parse_args()

    if not args.fichier.exists():
        raise SystemExit(f"{args.fichier} absent — voir data/raw/MANIFEST.json")

    articles = decouper(args.fichier.read_text(encoding="utf-8", errors="replace"))
    numerotes = [a for a in articles if a.numero != "liminaire"]
    print(f"=== {args.fichier.name}")
    print(f"  {len(articles)} articles, dont {len(numerotes)} numérotés "
          f"(art. {numerotes[0].numero} → {numerotes[-1].numero})")
    vides = [a.numero for a in articles if len(a.corps) < 40]
    if vides:
        print(f"  corps quasi vide pour : {vides} — à vérifier, un corps vide ne se chiffre pas")

    if args.corps:
        for a in articles[:6]:
            print(f"\n  art. {a.numero} — {a.intitule[:70]}")
            print(f"    {a.corps[:args.corps]}…")

    if getattr(args, "contre_triage", False):
        contre_triage(articles)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
