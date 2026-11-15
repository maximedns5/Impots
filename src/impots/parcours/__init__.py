"""Le parcours public (but 20) : huit pages qui refont le chemin d'un nombre publié, de
la source au verdict, et une page qui compare deux candidats sur la même base.

Chaque page prouve une seule chose, montre la donnée qui la prouve avec le lien de sa
source publique et le fichier du dépôt qui la calcule, et donne au lecteur un curseur sur
l'hypothèse qu'elle introduit (la page de l'erreur exceptée : c'est celle qu'on cite).

COMME LE SITE, LE PARCOURS NE CALCULE RIEN DE NEUF. Il lit des fichiers commités : les
rapports des études, la grille de vérification et ses passes, le magasin des élasticités,
les tables de Mésange, les ménages types chiffrés d'avance (`reports/parcours/`). Un
curseur rejoue dans le navigateur une arithmétique que le moteur a déjà (le θ, la boucle,
la dette) ou choisit entre des points chiffrés d'avance ; il ne change aucun nombre
d'étude. Une page qui porte un curseur porte un script ; elle reste lisible sans lui
(D-375).

Chaque page est un module de ce paquet qui expose `page() -> Page`. `build()` les
assemble, les relie entre elles et refuse une page qui ne tient pas ses promesses : sans
source publique, sans fichier du dépôt, ou sans curseur.
"""

from __future__ import annotations

import html
import importlib
import re
from dataclasses import dataclass
from pathlib import Path

from impots import etude

ROOT = etude.ROOT
#: Le dépôt public, où chaque fichier cité se lit (D-365).
DEPOT = "https://github.com/maximedns5/Impots"
#: La branche où les liens vers le code pointent : celle que le site publié reflète.
BRANCHE = "main"
#: Les chiffrages d'avance du parcours, commités comme des rapports.
RAPPORTS = ROOT / "reports" / "parcours"

#: Les dix étapes du chemin (but 25, D-451), dans l'ordre où un nombre se fait, puis la
#: page qui compare deux candidats. (module, nom du fichier publié, titre court) ; les
#: titres longs, les schémas et les chiffres de chaque étape sont dans `chemin.py`.
PAGES: tuple[tuple[str, str, str], ...] = (
    ("sources", "parcours-1-sources.html", "Les sources"),
    ("population", "parcours-2-population.html", "La population"),
    ("france", "parcours-3-calage.html", "Le calage"),
    ("menage", "parcours-4-baremes.html", "Les barèmes"),
    ("cout", "parcours-5-mesure.html", "Une mesure"),
    ("comportements", "parcours-6-comportements.html", "Les comportements"),
    ("activite", "parcours-7-bouclage.html", "Le bouclage"),
    ("dette", "parcours-8-dette.html", "La dette"),
    ("verdict", "parcours-9-verdict.html", "Le verdict"),
    ("erreur", "parcours-10-limites.html", "Ce que le modèle ne sait pas"),
    ("comparer", "comparer-candidats.html", "Comparer deux candidats"),
)
#: Les pages sans curseur, par décision : celle qu'on cite (D-375), et les deux étapes
#: qui décrivent des données plutôt qu'une hypothèse (D-451).
SANS_CURSEUR = {"erreur", "sources", "population"}
#: Les adresses du parcours d'avant (but 20), et l'étape où elles mènent (D-452).
ANCIENNES: dict[str, str] = {
    "parcours-1-menage.html": "parcours-4-baremes.html",
    "parcours-2-france.html": "parcours-3-calage.html",
    "parcours-3-cout.html": "parcours-5-mesure.html",
    "parcours-4-comportements.html": "parcours-6-comportements.html",
    "parcours-5-activite.html": "parcours-7-bouclage.html",
    "parcours-6-dette.html": "parcours-8-dette.html",
    "parcours-7-verdict.html": "parcours-9-verdict.html",
    "parcours-8-erreur.html": "parcours-10-limites.html",
    # La page qui comparait deux candidats est fondue dans celle du volet `mesure` (D-468).
    "parcours-comparer.html": "comparer-candidats.html",
}
#: Le nombre d'étapes du chemin ; la page qui compare vient après.
N_ETAPES = 10


class ParcoursError(ValueError):
    """Une page du parcours ne tient pas ce qu'elle promet."""


@dataclass(frozen=True)
class Page:
    """Ce qu'un module de page rend. `corps` est le HTML de <main>, sans le titre ni la
    navigation, que `build` ajoute. `prouve` est la phrase unique que la page démontre.
    `script` est du JavaScript en ligne, ou vide pour une page sans curseur. `style` est
    du CSS propre à la page, ou vide."""
    prouve: str
    corps: str
    script: str = ""
    style: str = ""


def fichier(chemin: str, texte: str | None = None) -> str:
    """Un lien vers un fichier du dépôt public, qui doit exister ici."""
    if not (ROOT / chemin).exists():
        raise ParcoursError(f"le parcours cite {chemin}, qui n'existe pas dans le dépôt.")
    url = f"{DEPOT}/blob/{BRANCHE}/{chemin}"
    return (f'<a class="fichier" href="{html.escape(url)}"><code>'
            f"{html.escape(texte or chemin)}</code></a>")


def source(url: str, texte: str) -> str:
    """Un lien vers une source publique, hors du dépôt."""
    if not re.match(r"https?://", url):
        raise ParcoursError(f"« {texte} » : une source publique est une URL, pas {url!r}.")
    return f'<a class="source" href="{html.escape(url)}">{html.escape(texte)}</a>'


def nom_publie(module: str) -> str:
    return next(name for mod, name, _ in PAGES if mod == module)


def lien(module: str, texte: str | None = None) -> str:
    """Un lien vers une autre page du parcours."""
    _, name, titre = next(p for p in PAGES if p[0] == module)
    if texte and re.fullmatch(r"(la )?page \d", texte):
        # Les pages d'avant se citaient par leur numéro ; le chemin a renuméroté (D-451).
        numero = [m for m, _, _ in PAGES].index(module) + 1
        texte = ("l'" if texte.startswith("la ") else "") + f"étape {numero}"
    return f'<a href="{name}">{html.escape(texte or titre)}</a>'


STYLE = """
p.prouve{border-left:3px solid var(--l2);padding-left:.8rem;font-style:italic}
.curseur{display:grid;grid-template-columns:minmax(0,1fr) minmax(8rem,16rem) 7rem;gap:.2rem .8rem;align-items:center;margin:.4rem 0}
.curseur input,.curseur select{width:100%}
.num{text-align:right;font-variant-numeric:tabular-nums}
.a-vous{--papier:var(--surface);background:var(--surface);border:1px solid var(--trait);border-radius:var(--rayon);padding:.2rem 1rem 1rem;margin:1.5rem 0}
.a-vous>h2:first-child{margin-top:1rem}
@media (max-width:560px){.curseur{grid-template-columns:1fr}}
"""

_H2 = re.compile(r"(?=<h2[\s>])")


def _mots(texte: str) -> int:
    texte = re.sub(r"<(script|svg|style)\b.*?</\1>", " ", texte, flags=re.S)
    return len(re.sub(r"<[^>]+>", " ", texte).split())


_PROSE = re.compile(r"(?<!<noscript>)<p\b[^>]*>.*?</p>", flags=re.S)


def _a_vous(s: str, debut: int, a_vous: tuple[str, str] | None) -> str:
    """Une section à curseur, pour un débutant (D-452) : un titre et l'idée en mots
    d'abord, la portée du curseur ; la prose de calcul d'avant (formules, fichiers),
    repliée sous les réglages. Les éléments que le script lit gardent leur place."""
    from impots import site_composants as c

    if a_vous is None:
        return f'<section class="a-vous">{s}</section>'
    titre, intro = a_vous
    tete, reste = s[:debut], s[debut:]
    premier = re.search(r"<input|<select", reste)
    avant, apres = (reste[:premier.start()], reste[premier.start():]) if premier else (
        reste, "")
    pliees: list[str] = []

    def plier(m: re.Match) -> str:
        bloc = m[0]
        if re.search(r'\bid="|<input|<select|<output|<button', bloc):
            return bloc
        pliees.append(bloc)
        return ""

    avant = _PROSE.sub(plier, avant)
    # Après les réglages aussi, la prose sans cible du script et les listes se replient.
    apres = _PROSE.sub(plier, apres)
    apres = re.sub(r"<(ul|ol)\b(?![^>]*\bid=)[^>]*>.*?</\1>", plier, apres, flags=re.S)
    h2 = re.match(r"<h2([^>]*)>", tete)
    return ('<section class="a-vous">' + f"<h2{h2[1] if h2 else ''}>{html.escape(titre)}</h2>"
            + intro + avant + apres
            + (c.detail("Comment ce calcul est fait", "".join(pliees)) if pliees else "")
            + "</section>")


def replier(corps: str, a_vous: tuple[str, str] | None = None) -> str:
    """Le corps d'une page d'avant, rangé (D-451) : les sections qui donnent la main au
    lecteur (un curseur, un choix) restent ouvertes, réécrites pour un débutant quand
    l'étape donne `a_vous` (titre, introduction en HTML) ; les autres se replient, chacune
    sous son titre, avec son temps de lecture. Rien n'est retiré : tout se lit en un clic,
    et chaque ancre reste celle de la section."""
    from impots import site_composants as c

    morceaux = _H2.split(corps)
    tete, sections = morceaux[0], morceaux[1:]
    ouvertes, repliees = [], []
    if tete.strip():
        repliees.append(c.detail("Pour commencer", tete,
                                 note=f"{max(1, round(_mots(tete) / 220))} min"))
    premier = True
    for s in sections:
        m = re.match(r'<h2(?: id="([^"]*)")?[^>]*>(.*?)</h2>', s, flags=re.S)
        interactif = re.search(r'<input[^>]*type="range"|<select', s) is not None
        if m is None or interactif:
            if interactif and m is not None:
                ouvertes.append(_a_vous(s, m.end(), a_vous if premier else None))
                premier = False
            else:
                ouvertes.append(f'<section class="a-vous">{s}</section>' if interactif else s)
            continue
        titre = html.unescape(re.sub(r"<[^>]+>", "", m[2]))
        bloc = c.detail(titre, s[m.end():], note=f"{max(1, round(_mots(s) / 220))} min")
        if m[1]:
            bloc = bloc.replace('<details class="detail"', f'<details class="detail" id="{m[1]}"', 1)
        repliees.append(bloc)
    return ("".join(ouvertes)
            + ('<h2 id="le-detail">Le détail de l\'étape</h2>' if repliees else "")
            + "".join(repliees))


def _check(module: str, page: Page) -> None:
    if 'class="source"' not in page.corps:
        raise ParcoursError(f"{module} : aucune source publique, la page ne prouve rien.")
    if 'class="fichier"' not in page.corps:
        raise ParcoursError(f"{module} : aucun fichier du dépôt, le calcul n'est pas montré.")
    curseur = re.search(r"<input[^>]*type=\"range\"|<select", page.corps) is not None
    if module in SANS_CURSEUR:
        if page.script:
            raise ParcoursError(f"{module} : la page de l'erreur ne porte pas de script.")
    elif not (curseur and page.script):
        raise ParcoursError(f"{module} : une page du parcours donne un curseur au lecteur.")
    if page.script and "<noscript>" not in page.corps:
        raise ParcoursError(f"{module} : une page à script se lit aussi sans lui "
                            f"(<noscript>).")
    if "<script" in page.corps.lower():
        raise ParcoursError(f"{module} : le script va dans `Page.script`, pas dans le corps.")


def build() -> dict[str, str]:
    """Les pages du parcours, par nom de fichier publié, et la page du chemin."""
    from impots import site
    from impots.parcours import chemin

    files: dict[str, str] = {}
    for index, (module, name, titre) in enumerate(PAGES):
        page = importlib.import_module(f"impots.parcours.{module}").page()
        _check(module, page)
        if index < N_ETAPES:
            assert chemin.ETAPES[index].fichier == name, name
            main = (chemin.tete(index, page.prouve)
                    + replier(page.corps, chemin.a_vous(module))
                    + chemin.suite(index))
        else:
            # « Comparer deux candidats » n'est plus une page : son tableau à deux choix
            # va dans `comparer-candidats.html`, la page du volet `mesure` (D-468).
            continue
        if page.script:
            main += f"\n<script>\n{page.script}\n</script>"
        text = site._page(f"{titre} — {site.TITLE}", main, large=True)
        text = text.replace("</head>", f"<style>{STYLE}{page.style}</style>\n</head>", 1)
        if page.script:
            text = text.replace("rien n'y est calculé, rien n'y tourne.",
                                "rien n'y est calculé ; cette page rejoue dans le navigateur "
                                "une arithmétique que le moteur a déjà.")
        files[name] = text
    files[CHEMIN] = site._page(f"Le chemin — {site.TITLE}", chemin.hub(), large=True)
    return files


def comparer_section() -> tuple[str, str]:
    """Le tableau « deux candidats, côte à côte » et son script, pour la page qui compare
    les candidats (`site_mesure.COMPARER`), et sa feuille (D-468)."""
    page = importlib.import_module("impots.parcours.comparer").page()
    _check("comparer", page)
    main = (chemin_garde(page.prouve) + replier(page.corps)
            + (f"\n<script>\n{page.script}\n</script>" if page.script else ""))
    return main, STYLE + page.style


def chemin_garde(prouve: str) -> str:
    from impots.parcours import chemin

    return chemin.c.garde("Ce que ce tableau établit", f"<p>{html.escape(prouve)}</p>")


#: La page qui montre les dix étapes d'un coup d'œil.
CHEMIN = "chemin.html"


def present() -> bool:
    """Le parcours se construit quand chacune de ses pages existe."""
    return all((Path(__file__).parent / f"{module}.py").exists() for module, _, _ in PAGES)
