"""Les composants du site (but 25, D-450) : de petites fonctions qui rendent du HTML.

Chaque page du site les reprend plutôt que d'écrire son propre habillage. Leur rendu, leurs
classes et quand s'en servir sont décrits dans `docs/site/DESIGN.md` ; leur style est dans
`site_textes/style.css`. Aucun composant ne demande de script : le chiffre sourcé s'ouvre
par l'attribut `popover` du navigateur, le détail par `<details>`.

LES COMPOSANTS NE CALCULENT RIEN. Un nombre passé à `chiffre` est déjà mis en forme par la
page, qui le lit dans un rapport commité ; le composant n'en montre que la provenance.
"""

from __future__ import annotations

import hashlib
import html
from dataclasses import dataclass, field

esc = html.escape

#: Les familles d'étape, et la couleur qui les dit (`--famille-*` de la feuille).
FAMILLES = ("donnees", "calcul", "economie", "verdict", "limite")


@dataclass(frozen=True)
class Provenance:
    """D'où vient un nombre : ce qu'il mesure, le rapport et le champ qui le portent, le
    commit qui l'a calculé, la source publique qu'il reprend ou à laquelle il se compare,
    et comment il est tiré du rapport quand il n'y est pas tel quel."""
    quoi: str
    rapport: str = ""
    champ: str = ""
    commit: str = ""
    source: tuple[str, str] | None = None  # (texte, url)
    calcul: str = ""
    etage: str = ""
    autres: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def _depot(chemin: str) -> str:
    from impots import parcours

    return (f'<a href="{esc(parcours.DEPOT)}/blob/{parcours.BRANCHE}/{esc(chemin)}">'
            f"<code>{esc(chemin)}</code></a>")


def chiffre(valeur: str, p: Provenance, cle: str = "") -> str:
    """Un nombre cliquable qui ouvre sa provenance. `valeur` est le texte affiché, déjà
    formé (« 12,4 Md€ ») ; `cle` distingue deux occurrences du même nombre sur une page."""
    ident = "pv-" + hashlib.sha1("|".join(
        (valeur, p.quoi, p.rapport, p.champ, cle)).encode()).hexdigest()[:10]
    lignes = []
    if p.rapport:
        lignes.append(("Rapport", _depot(p.rapport)))
    if p.champ:
        lignes.append(("Champ", f"<code>{esc(p.champ)}</code>"))
    if p.calcul:
        lignes.append(("Calcul", esc(p.calcul)))
    if p.commit:
        lignes.append(("Commit", f"<code>{esc(p.commit[:7])}</code>"))
    if p.etage:
        lignes.append(("Étage", esc(p.etage)))
    if p.source:
        texte, url = p.source
        lignes.append(("Source publique",
                       f'<a class="source" href="{esc(url)}">{esc(texte)}</a>'))
    lignes += [(esc(k), v) for k, v in p.autres]
    corps = "".join(f'<span class="provenance-ligne"><span>{k}</span><span>{v}</span></span>'
                    for k, v in lignes)
    return (f'<span class="chiffre"><button type="button" class="chiffre-v" '
            f'popovertarget="{ident}" aria-haspopup="dialog">{esc(valeur)}</button>'
            f'<span class="provenance" id="{ident}" popover role="dialog" '
            f'aria-label="D\'où vient ce nombre">'
            f'<button type="button" class="provenance-fermer" popovertarget="{ident}" '
            f'popovertargetaction="hide" aria-label="Fermer">×</button>'
            f'<span class="provenance-titre">D\'où vient ce nombre</span>'
            f'<span class="provenance-valeur">{esc(valeur)}</span>'
            f'<span class="provenance-quoi">{esc(p.quoi)}</span>{corps}</span></span>')


def stat(valeur: str, legende: str, p: Provenance | None = None) -> str:
    """Un chiffre clé : grand, avec sa légende ; sourcé s'il a une provenance."""
    v = chiffre(valeur, p) if p else esc(valeur)
    return (f'<div class="stat"><span class="stat-v">{v}</span>'
            f'<span class="stat-l">{esc(legende)}</span></div>')


def chiffres(*tuiles: str) -> str:
    return '<div class="chiffres">' + "".join(tuiles) + "</div>"


def carte(titre: str, texte: str, href: str = "", surtitre: str = "",
          pied: str = "") -> str:
    """Une carte : un titre, deux lignes, un lien qui couvre toute la carte. `texte` est du
    HTML déjà échappé."""
    t = (f'<a class="carte-lien" href="{esc(href)}">{esc(titre)}</a>' if href
         else esc(titre))
    return ('<article class="carte">'
            + (f'<p class="surtitre">{esc(surtitre)}</p>' if surtitre else "")
            + f"<h3>{t}</h3><p>{texte}</p>"
            + (f'<p class="carte-pied">{esc(pied)}</p>' if pied else "") + "</article>")


def cartes(*items: str) -> str:
    return '<div class="cartes">' + "".join(items) + "</div>"


def etape(numero: int | str, titre: str, texte: str, href: str = "",
          famille: str = "donnees", source: str = "", ici: bool = False) -> str:
    """Une étape numérotée d'un parcours, dans un `etapes(...)`. `texte` et `source` sont
    du HTML déjà échappé."""
    assert famille in FAMILLES, famille
    t = f'<a href="{esc(href)}">{esc(titre)}</a>' if href else esc(titre)
    courant = ' aria-current="step"' if ici else ""
    return (f'<li class="etape f-{famille}"{courant}><span class="etape-n" aria-hidden="true">'
            f'{esc(str(numero))}</span><div class="etape-corps"><h3>{t}</h3><p>{texte}</p>'
            + (f'<p class="etape-source">{source}</p>' if source else "") + "</div></li>")


def etapes(*items: str) -> str:
    return '<ol class="etapes">' + "".join(items) + "</ol>"


Boite = tuple[str, str]  # (titre, détail en HTML déjà échappé)

_FLECHE = ('<svg viewBox="0 0 40 16" aria-hidden="true" focusable="false">'
           '<path d="M2 8h32m-6-6 6 6-6 6" fill="none" stroke="currentColor" '
           'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def flux(entre: list[Boite], fait: list[Boite], sort: list[Boite], legende: str = "",
         titres: tuple[str, str, str] = ("Ce qui entre", "Ce qui est fait",
                                         "Ce qui sort")) -> str:
    """Le schéma d'une étape : ce qui entre, ce qui est fait, ce qui sort. Trois colonnes
    reliées par des flèches sur ordinateur, une pile au téléphone. `legende` est du HTML."""
    def col(cls: str, titre: str, boites: list[Boite]) -> str:
        return (f'<div class="flux-col {cls}"><p class="flux-col-titre">{esc(titre)}</p>'
                + "".join(f'<div class="flux-boite"><b>{esc(t)}</b><span>{d}</span></div>'
                          for t, d in boites) + "</div>")
    fleche = f'<div class="flux-fleche">{_FLECHE}</div>'
    return ('<figure class="flux"><div class="flux-grille">'
            + col("flux-entree", titres[0], entre) + fleche
            + col("flux-fait", titres[1], fait) + fleche
            + col("flux-sortie", titres[2], sort) + "</div>"
            + (f'<figcaption class="note-source">{legende}</figcaption>' if legende else "")
            + "</figure>")


def curseur(ident: str, libelle: str, mini: float, maxi: float, pas: float, valeur: float,
            change: str, ne_change_pas: str, plage: tuple[float, float] | None = None,
            plage_texte: str = "", bornes: tuple[str, str] = ("", ""),
            sortie: str = "") -> str:
    """Un curseur avec sa portée : ce qu'il change, ce qu'il ne change pas, et la plage
    publiée (de la littérature, d'une source) dessinée sous la piste. `change`,
    `ne_change_pas` et `plage_texte` sont du HTML. Le script de la page écrit la valeur
    dans `<output id="{ident}-v">`."""
    style = ""
    if plage is not None:
        de = (plage[0] - mini) / (maxi - mini) * 100
        a = (plage[1] - mini) / (maxi - mini) * 100
        style = f' style="--de:{de:.1f}%;--a:{a:.1f}%"'
    return (f'<div class="curseur-bloc"><div class="curseur-tete">'
            f'<label for="{esc(ident)}">{esc(libelle)}</label>'
            f'<output id="{esc(ident)}-v" for="{esc(ident)}">{esc(sortie)}</output></div>'
            f'<div class="curseur-piste">'
            + (f'<span class="curseur-plage"{style} aria-hidden="true"></span>'
               if plage else "")
            + f'<input type="range" id="{esc(ident)}" min="{mini:g}" max="{maxi:g}" '
            f'step="{pas:g}" value="{valeur:g}"></div>'
            f'<div class="curseur-bornes"><span>{esc(bornes[0])}</span>'
            + (f"<span>{plage_texte}</span>" if plage_texte else "")
            + f"<span>{esc(bornes[1])}</span></div>"
            f'<div class="curseur-portee"><div><b>Ce qu\'il change</b>{change}</div>'
            f'<div class="ne-change-pas"><b>Ce qu\'il ne change pas</b>{ne_change_pas}'
            "</div></div></div>")


def note_source(html_: str) -> str:
    """Une note de source sous un tableau, un schéma ou un graphique (HTML déjà échappé)."""
    return f'<p class="note-source">{html_}</p>'


def garde(titre: str, html_: str) -> str:
    """Une mise en garde : ce qu'un lecteur pourrait conclure à tort."""
    return f'<aside class="garde" role="note"><b>{esc(titre)}</b>{html_}</aside>'


def detail(titre: str, corps: str, ouvert: bool = False, note: str = "") -> str:
    """Un détail replié : ce qui se lit si on veut, pas avant."""
    o = " open" if ouvert else ""
    n = f"<small>{esc(note)}</small>" if note else ""
    return (f'<details class="detail"{o}><summary>{esc(titre)}{n}</summary>'
            f'<div class="detail-corps">{corps}</div></details>')


def echelle() -> str:
    """L'échelle de lecture (D-451, D-452) : ce que vaut un point de PIB en euros, pour
    juger si un nombre est grand. 2025 : le PIB que l'Insee publie, départ de toutes les
    études. 2035 : ce PIB porté dix ans au rythme nominal du cadre des études, la même
    arithmétique que le rejeu de la dette (`referencePath` de `parcours/js/dette.js`)."""
    from impots.parcours import dette

    e = dette.etudes()[0]
    d = e["data"]["rejeu"]["start"]
    g = e["data"]["rejeu"]["cadre"]["growth"]
    annees = len(e["data"]["years"])
    nominal = (1 + g["real"]) * (1 + g["prices"]) - 1
    pib = d["gdp_eur"]
    pib_fin = pib * (1 + nominal) ** annees
    fin = 2025 + annees

    def md(x: float) -> str:
        return f"{x / 100 / 1e9:.0f} Md€"

    pv = Provenance("Un centième du PIB de 2025 publié par l'Insee, le départ de toutes "
                    "les études.", rapport=e["chemin"], champ="rejeu.start.gdp_eur",
                    calcul=f"{pib / 1e9:,.0f} Md€ ÷ 100".replace(",", " "),
                    source=("Insee, comptes nationaux, T_1101",
                            "https://www.insee.fr/fr/statistiques/fichier/8988797/"
                            "T_1101_1103_fr.xlsx"))
    q = Provenance(f"Un centième du PIB de {fin} dans le cadre des études : le PIB de 2025 "
                   f"porté {annees} ans à la croissance réelle de {g['real'] * 100:.0f} % et "
                   f"aux prix de {g['prices'] * 100:.0f} % par an, comme le rejeu de la "
                   "dette le porte.", rapport=e["chemin"],
                   champ="rejeu.start.gdp_eur, rejeu.cadre.growth",
                   calcul=f"{pib / 1e9:,.0f} Md€ × {1 + nominal:.4f}^{annees} ÷ 100"
                   .replace(",", " "),
                   autres=(("Le cadre", "<code>etudes/cadres/central.json</code>"),))
    return ('<aside class="echelle" role="note"><b>Pour lire les nombres</b>'
            '<span class="echelle-regle"><span>1 point de PIB</span>'
            '<span class="echelle-barre"></span>'
            f"<span>≈ {chiffre(md(pib), pv)} en 2025, ≈ {chiffre(md(pib_fin), q)} en {fin}"
            "</span></span>"
            '<span class="echelle-plus">La dette publique de 2025 : '
            f'{d["debt_ratio"] * 100:.0f} points de PIB ; un écart de dette de 1 point en '
            f"{fin}, c'est environ " + chiffre(md(pib_fin), q, cle="2")
            + " de dette en plus.</span></aside>")
