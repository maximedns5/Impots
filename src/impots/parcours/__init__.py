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

#: Les huit pages, dans l'ordre de la preuve (du plus sûr au moins sûr), puis la page qui
#: compare deux candidats. (module, nom du fichier publié, titre court)
PAGES: tuple[tuple[str, str, str], ...] = (
    ("menage", "parcours-1-menage.html", "Un ménage"),
    ("france", "parcours-2-france.html", "La France simulée"),
    ("cout", "parcours-3-cout.html", "Le coût d'une mesure"),
    ("comportements", "parcours-4-comportements.html", "Les comportements"),
    ("activite", "parcours-5-activite.html", "L'activité"),
    ("dette", "parcours-6-dette.html", "La dette"),
    ("verdict", "parcours-7-verdict.html", "Le verdict"),
    ("erreur", "parcours-8-erreur.html", "Où l'outil se trompe"),
    ("comparer", "parcours-comparer.html", "Comparer deux candidats"),
)
#: La page sans curseur, par décision : c'est celle qu'on cite (D-375).
SANS_CURSEUR = {"erreur"}


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
    return f'<a href="{name}">{html.escape(texte or titre)}</a>'


def _navigation(index: int) -> str:
    items = []
    for i, (_, name, titre) in enumerate(PAGES):
        numero = f"{i + 1}. " if i < 8 else ""
        here = ' aria-current="page"' if i == index else ""
        items.append(f'<li><a href="{name}"{here}>{numero}{html.escape(titre)}</a></li>')
    return '<nav class="parcours"><ol>' + "".join(items) + "</ol></nav>"


def _suivante(index: int) -> str:
    parts = []
    if index > 0:
        _, name, titre = PAGES[index - 1]
        parts.append(f'<a href="{name}">← {html.escape(titre)}</a>')
    if index + 1 < len(PAGES):
        _, name, titre = PAGES[index + 1]
        parts.append(f'<a href="{name}">{html.escape(titre)} →</a>')
    return '<p class="suite">' + " · ".join(parts) + "</p>"


STYLE = """
nav.parcours ol{display:flex;flex-wrap:wrap;gap:.2rem .9rem;padding:0;margin:1rem 0;list-style:none;font:.85rem/1.4 system-ui,sans-serif}
nav.parcours a[aria-current]{font-weight:700;text-decoration:none}
p.prouve{border-left:3px solid var(--l2);padding-left:.8rem;font-style:italic}
p.suite{font-family:system-ui,sans-serif;font-size:.9rem;margin-top:2rem}
a.source::after{content:" ↗";font-size:.8em}
.curseur{display:grid;grid-template-columns:minmax(0,1fr) minmax(8rem,16rem) 7rem;gap:.2rem .8rem;align-items:center;margin:.4rem 0}
.curseur input,.curseur select{width:100%}
.num{text-align:right;font-variant-numeric:tabular-nums}
@media (max-width:560px){.curseur{grid-template-columns:1fr}}
"""


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
    """Les pages du parcours, par nom de fichier publié."""
    from impots import site

    files: dict[str, str] = {}
    for index, (module, name, titre) in enumerate(PAGES):
        page = importlib.import_module(f"impots.parcours.{module}").page()
        _check(module, page)
        numero = f"{index + 1}. " if index < 8 else ""
        main = (_navigation(index) + f"\n<h1>{numero}{html.escape(titre)}</h1>\n"
                f'<p class="prouve">Ce que cette page prouve : {html.escape(page.prouve)}</p>\n'
                + page.corps + "\n" + _suivante(index))
        if page.script:
            main += f"\n<script>\n{page.script}\n</script>"
        text = site._page(f"{titre} — {site.TITLE}", main)
        text = text.replace("</head>", f"<style>{STYLE}{page.style}</style>\n</head>", 1)
        if page.script:
            text = text.replace("rien n'y est calculé, rien n'y tourne.",
                                "rien n'y est calculé ; cette page rejoue dans le navigateur "
                                "une arithmétique que le moteur a déjà.")
        files[name] = text
    return files


def present() -> bool:
    """Le parcours se construit quand chacune de ses pages existe."""
    return all((Path(__file__).parent / f"{module}.py").exists() for module, _, _ in PAGES)
