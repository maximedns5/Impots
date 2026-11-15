"""Étape 1 du chemin (but 25, D-451) : d'où viennent les informations.

La page lit le manifeste des fichiers téléchargés (`data/raw/MANIFEST.json`, commité) et
les compte par producteur. Elle ne montre aucune microdonnée : seulement la liste des
fichiers, leur producteur, leur licence et leur empreinte.
"""

from __future__ import annotations

import html
import re
from collections import Counter

from impots import site_composants as c
from impots.parcours import Page, fichier, source
from impots.parcours.chemin import MANIFESTE, _lire

esc = html.escape

#: Les producteurs, par nom de domaine ; le reste est « recherche et autres ».
PRODUCTEURS = (
    ("Insee", ("insee.fr",), "enquête Emploi, comptes nationaux, revenus"),
    ("DGFiP et Bercy", ("impots.gouv.fr", "economie.gouv.fr", "aft.gouv.fr"),
     "impôt sur le revenu par tranche, dette de l'État"),
    ("Parlement", ("assemblee-nationale.fr", "senat.fr"), "textes des projets de loi"),
    ("Sécurité sociale et prestations", ("securite-sociale.fr", "caf.fr", "urssaf.fr",
                                         "drees.solidarites-sante.gouv.fr"),
     "prestations, cotisations, allocataires"),
    ("Europe et international", ("europa.eu", "oecd.org", "ecb.europa.eu"),
     "dette et taux, comparaisons"),
)

USAGES = (
    ("Faire les ménages", "La structure des ménages de l'enquête Emploi, les distributions "
     "de salaires et de pensions.", "#faire"),
    ("Caler et vérifier", "Les totaux des comptes nationaux, de la DGFiP, de la CAF : "
     "quelques-uns imposés, les autres comparés.", "#caler"),
    ("Faire réagir", "Les élasticités des articles publiés, les multiplicateurs de "
     "Mésange : comment les gens et l'économie répondent.", "#reagir"),
)


def producteurs() -> list[tuple[str, int, str]]:
    files = _lire(MANIFESTE)["files"]
    compte: Counter[str] = Counter()
    for v in files.values():
        url = v.get("url") or ""
        if not re.match(r"https?://", url):
            continue
        hote = re.sub(r"^https?://", "", url).split("/")[0]
        nom = next((n for n, domaines, _ in PRODUCTEURS
                    if any(hote == d or hote.endswith("." + d) for d in domaines)),
                   "Recherche et autres")
        compte[nom] += 1
    quoi = {n: q for n, _, q in PRODUCTEURS}
    quoi["Recherche et autres"] = "articles publiés, instituts, notes de conjoncture"
    return [(n, compte[n], quoi[n]) for n in [*quoi] if compte[n]]


def page() -> Page:
    lignes = "".join(f"<tr><td>{esc(n)}</td><td class=\"num\">{k}</td><td>{esc(q)}</td></tr>"
                     for n, k, q in producteurs())
    corps = (
        "<h2 id=\"producteurs\">Qui les publie</h2>"
        "<table><thead><tr><th>producteur</th><th>fichiers</th><th>pour quoi</th></tr>"
        f"</thead><tbody>{lignes}</tbody></table>"
        + c.note_source(f"Compte des entrées de {fichier(MANIFESTE)} dont l'adresse est "
                        "publique, par nom de domaine. Exemple : "
                        + source("https://www.insee.fr/fr/statistiques/8632441",
                                 "Insee, enquête Emploi 2024, fichier détail") + ".")
        + "<h2 id=\"usages\">À quoi ils servent</h2>"
        + c.cartes(*(c.carte(t, esc(d), surtitre=f"usage {i + 1}")
                     for i, (t, d, _) in enumerate(USAGES)))
        + c.garde("Ce qui n'est jamais publié",
                  "<p>Les fichiers individuels (des personnes, des ménages, des foyers) "
                  "restent hors du dépôt et hors du site : secret statistique et licence. "
                  "Le site ne montre que des totaux, des cellules et des ménages types.</p>")
        + "<h2 id=\"empreinte\">Comment on le vérifie</h2>"
        "<p>Chaque fichier a une empreinte (sha256) : si le producteur change son fichier, "
        "un octet de différence suffit pour que l'outil refuse de l'écrire. Le code qui "
        f"télécharge et vérifie : {fichier('src/impots/donnees.py')}.</p>")
    return Page(prouve="chaque nombre de l'outil part de fichiers publics, nommés, "
                       "datés et vérifiés par leur empreinte ; aucun n'est inventé.",
                corps=corps)
