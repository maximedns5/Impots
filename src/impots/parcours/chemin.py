"""Le chemin de pensée (but 25, D-451) : les dix étapes du parcours, dans l'ordre où un
nombre se fait, chacune avec son schéma (ce qui entre, ce qui est fait, ce qui sort), ses
chiffres sourcés et l'étape qui suit.

Ce module ne calcule rien. Chaque chiffre est lu dans un rapport commité par les fonctions
des pages du parcours, mis en forme comme elles le mettent, et sa provenance le dit. Le
fil rouge est la part chiffrée du programme de Gabriel Attal, l'étude que les pages du
coût et de la dette suivent déjà.
"""

from __future__ import annotations

import html
import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from impots import site_composants as c
from impots.site_composants import Provenance

esc = html.escape

MANIFESTE = "data/raw/MANIFEST.json"
GRILLE = "reports/verification/grille.json"
ATTAL_PA = "reports/etudes/presidentielle_attal/premiere_annee_pres2027_attal_programme.json"
ATTAL_PRED = "reports/etudes/presidentielle_attal/predictif_pres2027_attal_programme.json"
MENAGES = "reports/parcours/menages.json"
CROSSCHECK = "tests/golden/CROSSCHECK.md"


@dataclass(frozen=True)
class Etape:
    module: str
    fichier: str
    court: str       # dans la barre d'étapes
    titre: str       # le titre de la page : la question à laquelle l'étape répond
    chapeau: str     # deux phrases au plus (HTML)
    famille: str
    entre: tuple[c.Boite, ...]
    fait: tuple[c.Boite, ...]
    sort: tuple[c.Boite, ...]
    resume: str      # une ligne, sur la page du chemin (HTML)


ETAPES: tuple[Etape, ...] = (
    Etape("sources", "parcours-1-sources.html", "Sources",
          "D'où viennent les informations",
          "Rien n'est inventé : chaque fichier vient d'un producteur public, est téléchargé "
          "tel quel et reçoit une empreinte. Ces fichiers servent à trois choses : faire les "
          "ménages, les caler sur la France, et dire comment les gens et l'économie "
          "réagissent.", "donnees",
          (("Statistique publique", "Insee, DGFiP, Drees, CAF, Urssaf"),
           ("Textes de loi", "projets de loi, barèmes, Journal officiel"),
           ("Recherche publiée", "articles qui mesurent les réactions")),
          (("Télécharger tel quel", "une empreinte sha256 par fichier"),
           ("Noter la licence", "et le producteur, dans le manifeste")),
          (("Le manifeste", "la liste de chaque fichier et de sa source"),
           ("Trois usages", "faire, caler, faire réagir")),
          "Chaque fichier, son producteur, sa licence et son empreinte."),
    Etape("population", "parcours-2-population.html", "Population",
          "Comment on fabrique des ménages",
          "Personne ne peut publier les vrais ménages français. L'outil part de ceux d'une "
          "enquête publique, garde ce qu'elle observe (qui vit avec qui, l'âge, le travail) "
          "et leur attribue des revenus tirés dans des distributions publiées.",
          "donnees",
          (("Enquête Emploi 2024", "Insee : la structure de vrais ménages"),
           ("Distributions de revenus", "publiées par l'Insee et la DGFiP")),
          (("Observer", "garder la composition, l'âge, l'activité"),
           ("Tirer", "un salaire, une pension, un loyer, selon les distributions")),
          (("Des ménages simulés", "chacun pèse un nombre de ménages réels"),),
          "Des ménages d'enquête, des revenus tirés : une France de synthèse."),
    Etape("france", "parcours-3-calage.html", "Calage",
          "Est-ce que cette France ressemble à la vraie",
          "On ajuste le poids des ménages pour que quelques totaux tombent juste. Puis on "
          "compare la population à tout ce qu'on ne lui a pas imposé : c'est là qu'on voit "
          "si elle ressemble à la France, et où elle s'en écarte.", "donnees",
          (("Les ménages simulés", "étape 2"),
           ("Des totaux publiés", "comptes nationaux, DGFiP, CAF")),
          (("Caler", "ajuster les poids sur quelques totaux"),
           ("Vérifier", "comparer le reste, ligne par ligne, sur trois ans")),
          (("Une grille", "chaque ligne dans sa tolérance, ou non"),),
          "Quelques totaux imposés, le reste vérifié sur trois ans."),
    Etape("menage", "parcours-4-baremes.html", "Barèmes",
          "Comment on calcule l'impôt d'un ménage",
          "Pour chaque ménage, la loi est appliquée ligne à ligne : cotisations, CSG, impôt "
          "sur le revenu, prestations. La somme sur tous les ménages, chacun avec son poids, "
          "donne les totaux de la France.", "calcul",
          (("Un ménage", "salaire, situation, enfants, loyer"),
           ("La loi codée", "OpenFisca-France, barèmes de l'année")),
          (("Appliquer la loi", "cotisations, CSG, IR, prestations"),
           ("Contrôler", "contre le simulateur de la DGFiP")),
          (("Ce que le ménage paie et reçoit", "et son revenu disponible"),),
          "La loi appliquée à un ménage, contrôlée à l'euro sur deux cas."),
    Etape("cout", "parcours-5-mesure.html", "Mesure",
          "Ce que coûte une mesure, à comportements inchangés",
          "Une mesure se chiffre en faisant tourner deux fois la même population : une fois "
          "avec la loi, une fois avec la loi changée. Le coût est la différence, ménage par "
          "ménage, puis sommée.", "calcul",
          (("La population calée", "étape 3"), ("La loi, puis la loi changée", "le scénario")),
          (("Deux passes", "sur les mêmes ménages"), ("La différence", "ménage par ménage")),
          (("Le coût de la première année", "et qui y gagne, par décile"),),
          "Deux passes, une différence : le coût mécanique."),
    Etape("comportements", "parcours-6-comportements.html", "Comportements",
          "Ce que changent les réactions des gens",
          "Quand l'impôt change, les gens déclarent ou travaillent un peu autrement. L'outil "
          "n'estime pas ces réactions : il les lit dans des articles publiés et en donne une "
          "fourchette, θ allant du bas au haut de ce que la recherche a mesuré.",
          "economie",
          (("Le coût mécanique", "étape 5"), ("Des élasticités publiées", "un article par ligne")),
          (("Ouvrir un canal", "seulement si la mesure touche ce qu'il mesure"),
           ("Multiplier", "une somme sur la population × l'élasticité")),
          (("Le coût après comportements", "une bande, de θ = 0 à θ = 1"),),
          "Des réactions lues dans la recherche, en fourchette."),
    Etape("activite", "parcours-7-bouclage.html", "Bouclage",
          "Ce que l'économie rend au budget",
          "Une mesure qui rend de l'argent aux ménages fait monter l'activité, et l'activité "
          "fait rentrer des impôts. Le jumeau lit cette boucle, impôt par impôt et année par "
          "année, dans le modèle Mésange de l'Insee et de la DG Trésor.", "economie",
          (("Le coût, impôt par impôt", "étapes 5 et 6"),
           ("Les multiplicateurs publiés", "Mésange, et l'écart entre études")),
          (("Boucler, an par an", "l'activité rend une part du coût"),),
          (("Le solde, de 2026 à 2035", "ce qui reste au budget chaque année"),),
          "L'activité rend une part du coût, lue dans Mésange."),
    Etape("dette", "parcours-8-dette.html", "Dette",
          "Ce que la mesure fait à la dette en 2035",
          "La dette n'est pas un modèle : c'est une identité comptable. On part de la dette "
          "publiée pour 2025, on ajoute chaque année le solde changé par la mesure et les "
          "intérêts, et on lit l'écart en 2035.", "economie",
          (("Le solde, an par an", "étape 7"), ("La dette de 2025", "publiée par l'Insee"),
           ("Un cadre", "croissance, prix, taux d'intérêt")),
          (("Additionner", "solde et intérêts, chaque année"),),
          (("L'écart de dette en 2035", "en points de PIB"),),
          "Une identité comptable, du coût à l'écart de dette."),
    Etape("verdict", "parcours-9-verdict.html", "Verdict",
          "Hausse, baisse, ou ça dépend",
          "Le dernier mot n'est pas une opinion. On tire des milliers de fois les paramètres "
          "incertains, selon des lois écrites, et l'on compte la part des tirages où la dette "
          "monte. Le seuil qui fait dire « hausse » est fixé avant le calcul.", "verdict",
          (("L'écart de dette", "étape 8"), ("Les incertitudes", "chacune avec sa loi écrite")),
          (("Tirer 2 000 fois", "et compter les hausses"),
           ("Comparer au seuil", "fixé avant le calcul")),
          (("Un verdict", "« hausse », « baisse » ou « dépend »"),),
          "Une part de tirages, comparée à un seuil fixé d'avance."),
    Etape("erreur", "parcours-10-limites.html", "Limites",
          "Ce que le modèle ne sait pas",
          "L'outil se trompe, et il le dit : l'écart de chaque total à son total publié, les "
          "chiffrages officiels qu'il manque, et ce qu'il ne sait pas chiffrer du tout.",
          "limite",
          (("La grille", "étape 3"), ("Les chiffrages officiels", "les juges")),
          (("Mesurer l'erreur", "étage par étage"),),
          (("Ce que l'on sait mal", "et ce que l'on ne sait pas"),),
          "L'erreur mesurée, bornée, dite."),
)
NUMERO = {e.module: i + 1 for i, e in enumerate(ETAPES)}


def _lire(chemin: str):
    from impots import etude

    return json.loads((etude.ROOT / chemin).read_text(encoding="utf-8"))


# --- Les chiffres de chaque étape, lus dans les rapports ------------------------------

def _manifeste() -> tuple[int, int, list[tuple[str, int]]]:
    files = _lire(MANIFESTE)["files"]
    familles = {"insee.fr": "Insee", "bdm.insee.fr": "Insee", "impots.gouv.fr": "DGFiP",
                "data.economie.gouv.fr": "Bercy", "tresor.economie.gouv.fr": "Bercy",
                "aft.gouv.fr": "Bercy", "assemblee-nationale.fr": "Parlement",
                "www2.assemblee-nationale.fr": "Parlement", "senat.fr": "Parlement"}
    compte: Counter[str] = Counter()
    publics = 0
    for v in files.values():
        url = v.get("url") or ""
        if not re.match(r"https?://", url):
            continue
        publics += 1
        hote = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        compte[familles.get(hote, "autres")] += 1
    return len(files), publics, compte.most_common()


def _grille() -> tuple[list[dict], dict[str, dict]]:
    rows = _lire(GRILLE)["lignes"]
    return rows, {r["id"]: r for r in rows if r["annee"] == 2024}


def _attal() -> dict:
    from impots.parcours import cout

    pa, pred = _lire(ATTAL_PA), _lire(ATTAL_PRED)
    deco = pred["lectures"]["decomposition"]["vieillie"]
    return {"cout": cout.cout_total(pa), "commit": pa["commit"], "pred_commit": pred["commit"],
            "deco": deco, "p_hausse": pred["monte_carlo"]["vues"]["vieillie"]["p_hausse"],
            "tirages": pred["monte_carlo"]["tirages"]}


def _pt(x: float, signe: bool = True) -> str:
    s = f"{x * 100:+.2f}" if signe else f"{x * 100:.2f}"
    return s.replace("-", "−").replace(".", ",") + " pt"


def _md(x: float) -> str:
    return f"{x / 1e9:+.2f}".replace("-", "−").replace(".", ",") + " Md€"


ATTAL_PAGE = "presidentielle_attal.html"


def _chiffres_sources() -> str:
    total, publics, familles = _manifeste()
    pv = Provenance("Les fichiers que le manifeste du dépôt consigne, chacun avec son URL, "
                    "son empreinte et sa licence.", rapport=MANIFESTE, champ="files",
                    calcul="nombre d'entrées ; « publics » : celles dont l'URL est une "
                           "adresse web (les autres sont des pièces livrées à part)")
    top = [(nom, n) for nom, n in familles if nom != "autres"][:3]
    tuiles = [c.stat(str(total), "fichiers consignés dans le manifeste", pv),
              c.stat(str(publics), "téléchargés depuis une adresse publique", pv)]
    tuiles += [c.stat(str(n), f"de {nom}", Provenance(
        f"Les fichiers du manifeste dont l'adresse est chez {nom}.", rapport=MANIFESTE,
        champ="files.*.url", calcul="compte par nom de domaine, regroupé par producteur"))
        for nom, n in top[:2]]
    return c.chiffres(*tuiles)


def _ligne(r: dict, quoi: str) -> Provenance:
    return Provenance(quoi, rapport=GRILLE, champ=f"lignes[id={r['id']}, annee=2024]",
                      commit=r.get("commit", ""), source=(r["source"][:90], r["url"])
                      if r.get("url") else None)


def _chiffres_population() -> str:
    from impots.parcours import france

    _, l24 = _grille()
    f = l24["foyers_fiscaux"]
    nv = l24["niveau_de_vie_median"]
    return c.chiffres(
        c.stat(france.valeur("foyers_fiscaux", f["simule"]),
               "foyers fiscaux simulés en 2024", _ligne(f, "Foyers fiscaux de la population "
                                                       "simulée, en 2024 (champ simule).")),
        c.stat(france.valeur("foyers_fiscaux", f["publie"]), "foyers fiscaux publiés (DGFiP)",
               _ligne(f, "Foyers fiscaux publiés par la DGFiP pour 2024 (champ publie).")),
        c.stat(france.valeur("niveau_de_vie_median", nv["simule"]),
               "niveau de vie médian simulé, par an",
               _ligne(nv, "Niveau de vie médian de la population simulée (champ simule) ; "
                          "publié : " + france.valeur("niveau_de_vie_median", nv["publie"])
                      + " (ERFS).")))


def _chiffres_calage() -> str:
    from impots.parcours import france

    rows, l24 = _grille()
    t24, n24 = france.compte(rows, 2024)
    t, n = france.compte(rows)
    ir = l24["ir_bareme"]
    pv = Provenance("Les lignes de la grille de vérification dans leur tolérance, parmi les "
                    "lignes notées (hors calées, refusées et de contexte).", rapport=GRILLE,
                    champ="lignes[].verdict", commit=france.commits(rows)[0],
                    calcul="impots.parcours.france.compte")
    return c.chiffres(
        c.stat(f"{t24} sur {n24}", "lignes dans leur tolérance en 2024", pv),
        c.stat(f"{t} sur {n}", "sur les trois années 2022 à 2024", pv),
        c.stat(france.valeur("ir_bareme", ir["simule"]),
               "impôt sur le revenu au barème, simulé, 2024 ; publié "
               + france.valeur("ir_bareme", ir["publie"]),
               _ligne(ir, "L'impôt sur le revenu au barème de la population simulée, contre "
                          "son total publié : dans la tolérance.")))


def _chiffres_baremes() -> str:
    from impots.parcours import menage

    d = menage.dgfip()
    cas = d["single_30k"]
    pv = Provenance("L'impôt sur le revenu d'une personne seule à 30 000 € de salaire brut, "
                    "tel que le simulateur officiel de la DGFiP le calcule, et que le moteur "
                    "retrouve à l'euro.", rapport=CROSSCHECK, champ="single_30k",
                    etage="L0 : la loi, contrôlée",
                    autres=(("Relevé", f"sur le simulateur de la DGFiP, le {esc(d['date'])}"),))
    return c.chiffres(
        c.stat(menage.eur(cas["ir"]), "d'impôt sur le revenu : seul, 30 000 € brut", pv),
        c.stat("2 sur 2", "ménages retrouvés à l'euro contre la DGFiP",
               Provenance("Les deux ménages types contrôlés contre le simulateur de la "
                          "DGFiP.", rapport=CROSSCHECK, champ="single_30k, couple_70k_2kids",
                          etage="L0 : la loi, contrôlée")))


def _chiffres_mesure() -> str:
    a = _attal()
    pv = Provenance("Le coût de la première année de la part chiffrée du programme de "
                    "Gabriel Attal : la somme, ménages et entreprises, des différences "
                    "entre les deux passes.", rapport=ATTAL_PA, champ="response",
                    commit=a["commit"], calcul="impots.parcours.cout.cout_total",
                    etage="L2 : simulation mécanique",
                    autres=(("Étude", f'<a href="{ATTAL_PAGE}">la page de l\'étude</a>'),))
    return c.chiffres(c.stat(_md(a["cout"]), "la première année : le fil rouge, la part "
                             "chiffrée du programme de Gabriel Attal", pv))


def _deco(cle: str, quoi: str) -> str:
    a = _attal()
    return c.chiffre(_pt(a["deco"][cle]), Provenance(
        quoi, rapport=ATTAL_PRED, champ=f"lectures.decomposition.vieillie.{cle}",
        commit=a["pred_commit"], etage="L4, sous hypothèses",
        autres=(("Étude", f'<a href="{ATTAL_PAGE}">la page de l\'étude</a>'),)))


def _chiffres_bouclage() -> str:
    return ('<div class="chiffres">'
            '<div class="stat"><span class="stat-v">'
            + _deco("cout", "Le coût accumulé jusqu'en 2035, en points de PIB, avant ce que "
                    "l'activité rend (vue vieillie, θ½).")
            + '</span><span class="stat-l">de dette par le coût seul, en 2035</span></div>'
            '<div class="stat"><span class="stat-v">'
            + _deco("retroaction", "Ce que l'activité rend au budget, accumulé jusqu'en "
                    "2035, en points de PIB (vue vieillie, θ½).")
            + '</span><span class="stat-l">rendus par l\'activité</span></div></div>')


def _chiffres_dette() -> str:
    return ('<div class="chiffres"><div class="stat"><span class="stat-v">'
            + _deco("total", "L'écart de dette en 2035, en points de PIB : coût, plus ce que "
                    "l'activité rend, plus l'effet du PIB plus haut sur le ratio (vue "
                    "vieillie, θ½).")
            + '</span><span class="stat-l">de dette en 2035 : le fil rouge, Gabriel Attal'
            "</span></div></div>")


def _chiffres_verdict() -> str:
    a = _attal()
    p = f"{a['p_hausse'] * 100:.0f} %"
    pv = Provenance("La part des tirages du Monte-Carlo où la dette de 2035 monte (vue "
                    "vieillie). Sous 90 %, et au-dessus de 10 %, le verdict est « dépend ».",
                    rapport=ATTAL_PRED, champ="monte_carlo.vues.vieillie.p_hausse",
                    commit=a["pred_commit"], etage="L4, sous hypothèses",
                    autres=(("Tirages", str(a["tirages"])),))
    return c.chiffres(c.stat(p, "des tirages font monter la dette : « dépend » (Attal)", pv))


CHIFFRES: dict[str, Callable[[], str]] = {
    "sources": _chiffres_sources, "population": _chiffres_population,
    "france": _chiffres_calage, "menage": _chiffres_baremes, "cout": _chiffres_mesure,
    "activite": _chiffres_bouclage, "dette": _chiffres_dette, "verdict": _chiffres_verdict,
}

#: Les pages d'un autre volet qu'une étape annonce ; montrées quand elles existent. La
#: première est le bouton ; les suivantes, des pastilles vers leurs sections (D-468).
RENVOIS: dict[str, tuple[tuple[str, str], ...]] = {
    "population": (
        ("population.html#en-bref", "Qui sont les ménages simulés, en détail"),
        ("population.html#construction", "Comment elle est construite"),
        ("population.html#poids", "Ce que pèse un ménage"),
        ("population-france.html#calee", "Ce qui est calé"),
        ("population-france.html#ecarts", "Où elle s'écarte de la France"),
        ("population-comme-moi.html#choisir", "Un ménage comme le mien"),
        ("cellules.html", "Les cellules publiées")),
    "cout": (
        ("mesure.html", "Une mesure pas à pas, de bout en bout"),
        ("mesure-attal-a16_droit_au_brut.html", "Le fil rouge : le « droit au brut » "
         "d'Attal, pas à pas")),
    "activite": (("jumeau.html", "Le jumeau : faire tourner la boucle soi-même"),),
    "dette": (("jumeau.html", "Le jumeau : changer le cadre, de 2026 à 2035"),),
}


def renvoi(page: str, texte: str) -> str:
    """Un lien vers la page d'un autre volet, que le site retire si elle n'est pas
    construite (`site.build`). `page` peut porter une ancre."""
    return (f'<span class="si-page" data-page="{esc(page.split("#")[0])}"><a class="bouton" '
            f'href="{esc(page)}">{esc(texte)} →</a></span>')


def renvois(module: str) -> str:
    """Le bouton d'une étape vers la page d'un autre volet, et ses sections en pastilles."""
    liens = RENVOIS.get(module, ())
    if not liens:
        return ""
    out = f'<p class="boutons">{renvoi(*liens[0])}</p>'
    if len(liens) > 1:
        out += ('<nav class="pastilles" aria-label="Pour aller plus loin"><ol>'
                + "".join(f'<li><span class="si-page" data-page="{esc(p.split("#")[0])}">'
                          f'<a href="{esc(p)}">{esc(t)}</a></span></li>' for p, t in liens[1:])
                + "</ol></nav>")
    return out


# --- Ce que build() met autour de chaque page ---------------------------------------

def barre(index: int) -> str:
    items = []
    for i, e in enumerate(ETAPES):
        cls = f"f-{e.famille}" + (" fait" if i < index else "")
        ici = ' aria-current="step"' if i == index else ""
        items.append(f'<li class="{cls}"><a href="{e.fichier}"{ici} title="{esc(e.titre)}">'
                     f"{i + 1}<span>{esc(e.court)}</span></a></li>")
    return ('<nav class="chemin-barre" aria-label="Les étapes du chemin"><ol>'
            + "".join(items) + "</ol></nav>")


def tete(index: int, prouve: str) -> str:
    e = ETAPES[index]
    return (barre(index)
            + f'<p class="surtitre">Étape {index + 1} sur {len(ETAPES)} · {esc(e.court)}</p>'
            + f"<h1>{esc(e.titre)}</h1>"
            + f'<p class="chapeau">{e.chapeau}</p>'
            + c.flux(list(e.entre), list(e.fait), list(e.sort))
            + (CHIFFRES[e.module]() if e.module in CHIFFRES else "")
            + (c.echelle() if e.module in ("cout", "dette") else "")
            + c.garde("En une phrase", f"<p>{esc(prouve)}</p>")
            + renvois(e.module))


def suite(index: int) -> str:
    parts = []
    if index > 0:
        p = ETAPES[index - 1]
        parts.append(f'<a class="avant" href="{p.fichier}"><small>← Étape {index}</small>'
                     f"<b>{esc(p.titre)}</b></a>")
    if index + 1 < len(ETAPES):
        n = ETAPES[index + 1]
        parts.append(f'<a class="apres" href="{n.fichier}"><small>Étape {index + 2} →</small>'
                     f"<b>{esc(n.titre)}</b></a>")
    else:
        parts.append('<a class="apres" href="comparer-candidats.html"><small>Et ensuite →'
                     "</small><b>Comparer deux candidats</b></a>")
    return '<nav class="suite" aria-label="Étape suivante">' + "".join(parts) + "</nav>"


def hub() -> str:
    """La page du chemin : les dix étapes, d'un coup d'œil."""
    items = [c.etape(i + 1, e.titre, e.resume, e.fichier, e.famille)
             for i, e in enumerate(ETAPES)]
    a = _attal()
    fil = (f"La part chiffrée du programme de Gabriel Attal coûte "
           f"{c.chiffre(_md(a['cout']), Provenance('Coût de la première année.', rapport=ATTAL_PA, champ='response', commit=a['commit'], etage='L2'))}"
           f" la première année (étape 5) ; une fois les comportements et l'activité "
           f"bouclés, la dette de 2035 est plus haute de "
           f"{_deco('total', 'Écart de dette en 2035, vue vieillie, θ½.')} (étape 8) ; et "
           f"{a['p_hausse'] * 100:.0f} % des tirages la font monter : « dépend » (étape 9).")
    return ('<p class="surtitre">Le chemin de pensée</p>'
            "<h1>Comment une réforme devient un nombre</h1>"
            '<p class="chapeau">Dix étapes, des fichiers publics au verdict. Chacune dit ce '
            "qui y entre, ce qui y est fait, ce qui en sort, et d'où vient chaque nombre.</p>"
            + c.flux([("Sources publiques", "étape 1")],
                     [("Population et calage", "étapes 2 et 3"),
                      ("Barèmes et mesure", "étapes 4 et 5"),
                      ("Comportements et activité", "étapes 6 et 7")],
                     [("Dette et verdict", "étapes 8 et 9")],
                     legende="L'étape 10 dit ce que chaque étape ne sait pas.")
            + f'<p class="boutons"><a class="bouton plein" href="{ETAPES[0].fichier}">'
            "Commencer à l'étape 1 →</a></p>"
            + "<h2>Les dix étapes</h2>" + c.etapes(*items)
            + "<h2>Le fil rouge</h2>"
            + f"<p>Un même exemple traverse les étapes : {fil}</p>"
            + c.note_source(f'Les chiffres s\'ouvrent sur leur provenance ; l\'étude entière : '
                            f'<a href="{ATTAL_PAGE}">Gabriel Attal</a>.'))


# --- Les sections à curseur, dites pour un débutant (D-452) ---------------------------

def _portee(change: str, ne_change_pas: str) -> str:
    return ('<div class="curseur-portee"><div><b>Ce que le réglage change</b>' + change
            + '</div><div class="ne-change-pas"><b>Ce qu\'il ne change pas</b>'
            + ne_change_pas + "</div></div>")


def _reference_2026() -> str:
    pred = _lire(ATTAL_PRED)
    r = pred["years"][0]
    d = pred["rejeu"]["start"]
    depart = c.chiffre(f"{d['debt_ratio'] * 100:.2f} %".replace(".", ","), Provenance(
        "La dette publique de 2025, au sens de Maastricht, en part du PIB : le départ de "
        "toutes les études.", rapport=ATTAL_PRED, champ="rejeu.start.debt_ratio",
        commit=pred["commit"], source=("Insee, dette de Maastricht des APU",
                                       "https://www.insee.fr/fr/statistiques/fichier/"
                                       "9035065/dette.xlsx")))
    ref = c.chiffre(f"{r['reference'] * 100:.2f} %".replace(".", ","), Provenance(
        f"La dette de référence de {r['year']}, sans réforme : celle de 2025 portée un an "
        "par l'identité comptable (intérêts au taux de 2025, croissance et prix du cadre, "
        "solde primaire de 2025 avec la dépense gelée en volume).", rapport=ATTAL_PRED,
        champ="years[0].reference", commit=pred["commit"]))
    return depart, ref


def a_vous(module: str) -> tuple[str, str] | None:
    """Le titre et l'introduction en mots de la section à curseur d'une étape."""
    if module == "france":
        from impots.parcours import france

        rows, _ = _grille()
        t, n = france.compte(rows, 2024)
        return ("À vous : la France simulée contre la vraie",
                "<p>Chaque ligne compare un total de la population simulée (l'impôt qu'elle "
                "paie, les foyers de chaque tranche, les prestations, le niveau de vie) à son "
                "total publié. L'écart admis, la <strong>tolérance</strong>, est écrit avant "
                f"le calcul. En 2024, {t} lignes sur {n} tiennent la leur. Choisissez une "
                "année pour la voir.</p>"
                + _portee("l'année montrée : 2022, 2023 ou 2024", "la population : il n'y "
                          "en a qu'une, celle de 2024, ramenée en arrière pour 2022 et 2023")
                + '<p class="boutons">'
                + renvoi("population-france.html", "La population face à la France, en détail")
                + "</p>")
    if module == "menage":
        return ("À vous : un salaire, une situation",
                "<p>Choisissez une situation et un salaire : le tableau suit la loi de 2024 "
                "ligne par ligne, du coût pour l'employeur au revenu disponible du ménage. "
                "Chaque point du curseur a été calculé d'avance par le moteur.</p>"
                + _portee("le ménage montré", "la loi, celle de 2024"))
    if module == "cout":
        return ("À vous : tourner un bouton",
                "<p>Une mesure est souvent un bouton qu'on tourne : la part des cotisations "
                "de retraite qu'on garde, le taux de TVA sur l'énergie. Chaque position du "
                "curseur est un calcul déjà fait sur toute la population ; le coût affiché "
                "est celui des ménages en 2026, la population vieillie à cette année.</p>"
                + _portee("le coût pour les ménages, à chaque position chiffrée", "le reste "
                          "de la loi ; les réactions des gens et de l'économie (étapes 6 et 7)"))
    if module == "comportements":
        return ("À vous : la force de chaque réaction",
                "<p>Chaque curseur règle une réaction mesurée par un article publié : à "
                "gauche, le bas de la fourchette que l'article donne ; à droite, le haut ; "
                "au milieu, sa valeur centrale. Le tableau dit, année par année, ce que la "
                "réaction ajoute au budget ou lui retire. Une <strong>recette positive "
                "réduit le coût</strong> : si l'impôt baisse et que les gens déclarent un "
                "peu plus de revenu, une partie de la baisse revient au budget.</p>"
                + _portee("le coût après comportements de l'étude choisie, et sa dette en "
                          "2035", "le coût mécanique (étape 5) ; ce que l'activité rend, "
                          "tenu au milieu de sa fourchette (étape 7)"))
    if module == "activite":
        return ("À vous : la force du multiplicateur",
                "<p>Une baisse d'impôt relance un peu l'activité, et l'activité plus haute "
                "rend une partie du coût en impôts. Combien ? Le modèle Mésange de l'Insee "
                "et de la DG Trésor donne une valeur centrale ; les autres études publiées "
                "s'en écartent. Le curseur va du bas de cet écart (θ = 0) à son haut "
                "(θ = 1). La <strong>persistance</strong> dit combien de temps l'effet "
                "dure : lu dans Mésange jusqu'à dix ans (le réglage des études), éteint "
                "après trois ans, ou tenu à son niveau de la troisième année.</p>"
                + _portee("ce que l'activité rend chaque année, donc la dette de 2035 de "
                          "l'étude choisie", "le coût de chaque année (étape 5) ; les "
                          "réactions des gens, tenues au milieu (étape 6)"))
    if module == "dette":
        depart, ref = _reference_2026()
        return ("À vous : changer le cadre économique",
                "<p>La dette se compte en part du PIB : un PIB qui grandit plus vite la "
                "fait baisser. Les curseurs changent la croissance et les prix des dix "
                "années ; le gouvernement publie, pour 2025 à 2029, une croissance de 0,7 à "
                "1,3 % par an et des prix de 1,5 à 1,6 % (PLF 2026), et la page signale "
                f"quand on en sort. La dette de référence, sans réforme, part de la dette "
                f"publiée de 2025, {depart} du PIB, et vaut {ref} en 2026.</p>"
                + _portee("la dette de référence, et l'écart de dette que la mesure y "
                          "ajoute, année par année", "le coût de la mesure chaque année, "
                          "calculé une fois sur la population (étape 5)"))
    if module == "verdict":
        return ("À vous : le seuil et les hypothèses du tirage",
                "<p>Le verdict compte, sur 2 000 tirages des paramètres incertains, la part "
                "où la dette de 2035 monte. Trois réglages. <strong>Le seuil</strong> : à "
                "90 %, il faut neuf tirages sur dix dans le même sens pour dire « hausse » "
                "ou « baisse » ; sinon, « dépend ». <strong>La corrélation</strong> des "
                "réactions tirées d'un même article : à 0,8, elles bougent presque "
                "ensemble (si l'une tombe haut, l'autre aussi) ; à 0, chacune de son côté. "
                "<strong>L'incertitude du multiplicateur</strong> : × 1, l'écart entre les "
                "études publiées ; × 2, deux fois plus large. Le tableau dit aussi quelle "
                "hypothèse pèse le plus : la part de la variation du résultat qui vient "
                "d'elle seule (« premier ordre ») ou d'elle avec les autres "
                "(« total »).</p>"
                + _portee("la part des tirages en hausse, le verdict et la fourchette de la "
                          "dette de l'étude choisie", "le coût et la dette au centre ; "
                          "les tirages eux-mêmes, faits une fois avec la même graine"))
    return None
