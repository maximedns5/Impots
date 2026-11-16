"""La page d'accueil du site (but 25, D-450) : ce qu'est le site, ce qu'on y fait, par où
commencer, en une demi-minute.

Elle ne calcule rien. Ses trois chiffres sont ceux du fil rouge du chemin (la part chiffrée
du programme de Gabriel Attal), lus par `parcours.chemin` dans les rapports commités, et
chacun ouvre sa provenance.
"""

from __future__ import annotations

import html

from impots import site_composants as c

esc = html.escape


def _etudes(studies: list, presentes: set[str]) -> str:
    cartes = []
    for s in studies:
        if s.refus or f"{s.nom}.html" not in presentes:
            continue
        titre, _, reste = s.titre.partition(" : ")
        cartes.append(c.carte(titre, esc(reste or "l'étude, en trois réponses"),
                              href=f"{s.nom}.html",
                              surtitre="programme 2027" if s.programme else "projet de loi"))
    return c.cartes(*cartes)


def accueil(studies: list, presentes: set[str]) -> str:
    from impots.parcours import chemin

    a = chemin._attal()
    cout = c.chiffre(chemin._md(a["cout"]), c.Provenance(
        "Coût de la première année de la part chiffrée du programme de Gabriel Attal, à "
        "comportements inchangés.", rapport=chemin.ATTAL_PA, champ="response",
        commit=a["commit"], calcul="impots.parcours.cout.cout_total",
        etage="L2 : simulation mécanique"), cle="accueil")
    dette = chemin._deco("total", "Écart de dette publique en 2035, en points de PIB, une "
                         "fois les comportements et l'activité bouclés (vue vieillie, θ½).")
    rendu = chemin._deco("retroaction", "Ce que l'activité rend au budget, accumulé "
                         "jusqu'en 2035, en points de PIB (vue vieillie, θ½).")
    accumule = chemin._deco("cout", "Le coût accumulé jusqu'en 2035, en points de PIB, "
                            "avant ce que l'activité rend (vue vieillie, θ½).")
    part = c.chiffre(f"{a['p_hausse'] * 100:.0f} %", c.Provenance(
        "Part des tirages du Monte-Carlo où la dette de 2035 monte ; entre 10 % et 90 %, le "
        "verdict est « dépend ».", rapport=chemin.ATTAL_PRED,
        champ="monte_carlo.vues.vieillie.p_hausse", commit=a["pred_commit"],
        etage="L4, sous hypothèses"))
    # Les trois réponses de docs/BUT.md, dans les mots des études et de la méthode (R1,
    # D-469) : le coût ; le coût avec les comportements et l'économie ; la dette.
    reponses = (
        ("1", "Ce qu'elle coûte, et qui y gagne", cout, "la première année, à "
         "comportements inchangés ; qui y gagne, décile par décile, sur la page de "
         "l'étude", "parcours-5-mesure.html"),
        ("2", "Ce qu'elle coûte avec les comportements et l'économie", rendu,
         f"rendus au budget par l'activité d'ici 2035, sur {accumule} de coût accumulé. "
         "Aucune réaction des gens n'est chiffrée pour ces mesures : la bande des "
         "comportements est absente (pas nulle), et l'étude dit pourquoi",
         "parcours-7-bouclage.html"),
        ("3", "Ce qu'elle fait à la dette en 2035", dette, f"de dette en 2035. Verdict "
         f"« dépend » : {part} des tirages la font monter : trop pour « baisse », trop peu pour « hausse »",
         "parcours-8-dette.html"),
    )
    tuiles = "".join(
        f'<article class="carte"><p class="surtitre">réponse {n}</p><h3>'
        f'<a class="carte-lien" href="{href}">{esc(t)}</a></h3>'
        f'<p class="stat-v" style="font:700 1.9rem/1.1 var(--serif);color:var(--encre)">{v}'
        f'</p><p>{leg}</p></article>'
        for n, t, v, leg, href in reponses)
    commencer = c.cartes(
        c.carte("Comprendre comment on chiffre", "Dix étapes, des fichiers publics au "
                "verdict, chacune avec son schéma.", href="chemin.html",
                surtitre="le chemin", pied="commencer →"),
        c.carte("Lire le chiffrage d'un candidat", "Les programmes de 2027 et les lois de "
                "finances, en trois réponses.", href="etudes.html", surtitre="les études",
                pied="les études →"),
        c.carte("Jouer avec les hypothèses", "Un curseur par paramètre incertain, de 2026 à "
                "2035, et ce qu'il change.", href="jumeau.html", surtitre="le jumeau",
                pied="le jumeau →") if "jumeau.html" in presentes else "",
        c.carte("Savoir ce que l'outil ne sait pas", "Où il se trompe, de combien, et ce "
                "qu'il ne chiffre pas.", href="parcours-10-limites.html",
                surtitre="les limites", pied="les limites →"))
    return (
        '<section class="une"><p class="surtitre">Un outil public de chiffrage</p>'
        "<h1>Ce que coûte une réforme, à qui, et ce qu'elle fait à la dette</h1>"
        '<p class="chapeau">Le site simule la France ménage par ménage, applique la loi, '
        "puis la loi changée, et suit l'écart jusqu'à la dette de 2035. Chaque nombre "
        "s'ouvre sur sa provenance : le rapport, le champ, le commit, la source.</p>"
        '<p class="boutons"><a class="bouton plein" href="chemin.html">Suivre le chemin en '
        'dix étapes</a><a class="bouton" href="etudes.html">Voir les études</a></p>'
        "</section>"
        "<h2>Trois réponses par réforme</h2>"
        "<p>Exemple : la part chiffrée du programme de Gabriel Attal. Touchez un nombre pour "
        "voir d'où il vient.</p>"
        f'<div class="cartes">{tuiles}</div>' + c.echelle() +
        "<h2>Comment ça marche</h2>"
        + c.flux([("Des fichiers publics", "Insee, DGFiP, CAF, textes de loi, recherche")],
                 [("Une France simulée", "des ménages d'enquête, calés sur les totaux"),
                  ("La loi, puis la réforme", "deux calculs, la différence"),
                  ("Les réactions", "des gens et de l'économie, lues dans la recherche")],
                 [("Le coût", "première année, par décile"),
                  ("La dette en 2035", "et un verdict")],
                 legende='Le détail, étape par étape : <a href="chemin.html">le chemin</a>.')
        + "<h2>Par où commencer</h2>" + commencer
        + c.garde("Ce que ce site n'est pas",
                  "<p>Ni une prévision, ni un avis sur un programme. Un programme n'est "
                  "chiffré qu'en partie, et la part chiffrée est dite sur chaque page. Les "
                  "nombres dépendent d'hypothèses nommées, et le site dit lesquelles.</p>")
        + "<h2>Les études</h2>" + _etudes(studies, presentes)
        + '<p><a href="etudes.html">Toutes les études, avec leurs réponses et leurs '
          "commits →</a></p>")
