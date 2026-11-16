"""Étape 2 du chemin (but 25, D-451) : comment on fabrique des ménages.

La page dit les trois sortes de nombres de la population (observé, tiré, calé) et renvoie
au détail de l'étape 3 et aux pages de la population. Ses chiffres sont ceux de la grille
de vérification (`reports/verification/grille.json`).
"""

from __future__ import annotations

from impots import site_composants as c
from impots.parcours import Page, fichier, source
from impots.parcours.chemin import ETAPES, renvoi

CALAGE = ETAPES[2].fichier


def page() -> Page:
    sortes = (
        ("Observé", "Qui vit avec qui, l'âge, l'activité, le logement : de vrais ménages "
         "interrogés par l'Insee, avec leur poids.", "#observe"),
        ("Tiré", "Les salaires, les pensions, les loyers : l'enquête ne les donne pas ; ils "
         "sont tirés dans des distributions publiées, selon le profil du ménage.", "#tire"),
        ("Calé", "Quelques totaux de la France, imposés en ajustant les poids. Ils ne "
         "prouvent rien : ils sont justes par construction.", "#cale"),
    )
    corps = (
        "<h2 id=\"trois-sortes\">Trois sortes de nombres</h2>"
        "<p>Un nombre de la population est observé, tiré ou calé. Seuls les deux premiers "
        "peuvent être faux, et c'est sur eux que l'étape 3 la juge.</p>"
        + c.cartes(*(c.carte(t, d, href=CALAGE + ancre, pied="le détail →")
                     for t, d, ancre in sortes))
        + c.note_source(source("https://www.insee.fr/fr/statistiques/8632441",
                               "Insee, enquête Emploi 2024, fichier détail")
                        + " ; le code qui construit la population : "
                        + fichier("src/impots/population/build.py") + ".")
        + c.garde("Ce que la population n'est pas",
                  "<p>Ce ne sont pas des ménages réels : aucun ménage simulé n'est une "
                  "famille qui existe. Un ménage simulé n'a de sens qu'avec son poids, au "
                  "milieu des autres ; un ménage seul ne se lit pas.</p>")
        + f'<p class="boutons">{renvoi("population.html", "Les ménages simulés, en détail")}'
        "</p>")
    return Page(prouve="la population est faite de ménages d'enquête réels, auxquels on "
                       "attribue des revenus tirés dans des distributions publiées ; elle "
                       "représente la France par ses poids, pas ménage par ménage.",
                corps=corps)
