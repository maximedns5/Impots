"""Une mesure pas à pas, et le résumé des pages d'études (but 25, volet `mesure`, D-456).

    mesure.html                          # le choix : un candidat, puis une de ses mesures
    mesure-<programme>-<mesure>.html     # une mesure suivie de bout en bout, en sept étapes

Le point d'entrée est stable : `lien(programme, mesure)` donne l'adresse de la page d'une
mesure, `mesure.html#<programme>` la liste d'un candidat. Le parcours du site y renvoie.

RIEN N'EST CALCULÉ QUI NE SOIT DANS UN RAPPORT. Chaque nombre se lit dans les deux rapports
commités d'une mesure seule (`premiere_annee_*.json`, `predictif_*.json`), tels que
`Etude.load` les a refusés ou acceptés ; ceux que la page d'étude publie sont repris par la
même fonction (`etude.lecture_seule`) et le même format. Un agrégat dérivé (les ménages
touchés : la part des gagnants et des perdants de chaque décile, fois ses ménages) le dit,
avec les champs qu'il lit. Chaque étape nomme son rapport, son champ et le commit.

Aucun script : des schémas en HTML et en SVG, servis tels quels, lisibles au téléphone.
"""

from __future__ import annotations

import html
from collections.abc import Callable
from typing import Any

from impots import etude, site_composants

INDEX = "mesure.html"


def lien(programme: str, mesure: str) -> str:
    """L'adresse stable de la page d'une mesure (le point d'entrée du parcours)."""
    return f"mesure-{programme}-{mesure}.html"


# --------------------------------------------------------------------------- #
# petits outils
# --------------------------------------------------------------------------- #
def _e(text: Any) -> str:
    return html.escape(str(text), quote=True)


def _eur(value: float | None) -> str:
    from impots import fiche

    return fiche._eur(value)


def _badge(texte: str, etage: str, conditionnel: bool = False) -> str:
    """Un nombre et son étage, comme sur les pages d'études (`site._badge`)."""
    from impots.site import _slug

    label = etage + (", sous hypothèses" if conditionnel else "")
    title = _e(etude.ETAGES.get(etage, etage))
    return (f'<span class="nombre">{_e(texte)}</span><a class="etage e-{_slug(etage)}" '
            f'href="#etage-{_slug(etage)}" title="{title}">{_e(label)}</a>')


def _m(text: str, etage: str = "programme") -> str:
    """Un texte du programme, échappé, chaque montant avec son étage (comme
    `etude.amounts`) ; sans noms de code entre parenthèses."""
    import re

    text = re.sub(r"\s*\(`[^`]*`\)", "", text)
    out, last = [], 0
    for m in etude.AMOUNT.finditer(text):
        out += [_e(text[last:m.start()]), _badge(m[0], etage)]
        last = m.end()
    return "".join(out) + _e(text[last:])


def _source(fichier: str, champ: str, commit: str) -> str:
    return (f'<p class="note-source"><code>{_e(fichier)}</code> · champ '
            f"<code>{_e(champ)}</code> · commit <code>{_e(commit[:7])}</code></p>")


def _fr(value: float, d: int = 0) -> str:
    text = f"{abs(value):,.{d}f}".replace(",", "\u202f").replace(".", ",")
    return ("−" if value < 0 and round(value, d) != 0 else "") + text


def _ticks(low: float, high: float) -> list[float]:
    from impots import graphiques

    return graphiques._ticks(low, high)


def _dec(ticks: list[float], echelle: float = 1.0) -> int:
    from impots import graphiques

    return graphiques.decimales(ticks, echelle)


W = 360


def _svg(ident: str, h: float, titre: str, desc: str, corps: list[str]) -> str:
    return (f'<svg class="sm" viewBox="0 0 {W} {h:.0f}" role="img" '
            f'aria-labelledby="{ident}-t {ident}-d"><title id="{ident}-t">{_e(titre)}</title>'
            f'<desc id="{ident}-d">{_e(desc)}</desc>' + "".join(corps) + "</svg>")


def _t(x: float, y: float, text: str, cls: str = "sm-doux", ancre: str = "start") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" class="{cls}" text-anchor="{ancre}">'
            f"{_e(text)}</text>")


def _figure(svg: str, trace: str, source: str) -> str:
    """Un graphique dit ce qu'il trace, en quelle unité, sur quelle période, et d'où."""
    return (f'<figure class="sm-fig">{svg}<figcaption><strong>Ce qu\'il trace</strong> : '
            f"{trace}<br>{source}</figcaption></figure>")


# --------------------------------------------------------------------------- #
# les graphiques de la page (SVG, couleurs par classes : le thème sombre suit)
# --------------------------------------------------------------------------- #
def barres(ident: str, rows: list[tuple[Any, ...]], titre: str, unite: str,
           echelle: float = 1.0) -> str:
    """Des barres horizontales autour de zéro : (libellé, valeur, texte affiché)."""
    values = [row[1] for row in rows] or [0.0]
    ticks = _ticks(min(0.0, *values), max(0.0, *values))
    x0, x1 = 14.0, W - 14.0

    def x(v: float) -> float:
        return x0 + (v - ticks[0]) / (ticks[-1] - ticks[0]) * (x1 - x0)

    corps, y = [], 8.0
    for row in rows:
        label, v, texte = row[:3]
        # Le libellé au-dessus de sa barre : au téléphone, rien ne se chevauche.
        corps.append(_t(x0, y + 12, f"{label} : {texte}", "sm-encre"))
        y += 17
        a, b = sorted((x(0), x(v)))
        cls = row[3] if len(row) > 3 else "sm-plus" if v >= 0 else "sm-moins"
        corps.append(f'<rect x="{a:.1f}" y="{y:.1f}" width="{max(b - a, 1):.1f}" '
                     f'height="14" class="{cls}"/>')
        y += 22
    corps.append(f'<line x1="{x(0):.1f}" y1="8" x2="{x(0):.1f}" y2="{y:.1f}" class="sm-zero"/>')
    d = _dec(ticks, echelle)
    for t in ticks:
        corps.append(_t(x(t), y + 14, _fr(t * echelle, d), "sm-doux", "middle"))
    corps.append(_t(x1, y + 30, unite, "sm-doux", "end"))
    desc = "; ".join(f"{row[0]} : {row[2]}" for row in rows)
    return _svg(ident, y + 38, titre, desc, corps)


def parts_deciles(ident: str, deciles: list[dict[str, Any]]) -> str:
    """Pour chaque décile de niveau de vie : la part des ménages qui gagnent, qui perdent,
    et que la mesure ne touche pas, en barres empilées à 100 %."""
    x0, x1, corps, y = 40.0, W - 14.0, [], 26.0
    corps.append(_t(x0, 14, "gagnent", "sm-l-plus"))
    corps.append(_t(x0 + 72, 14, "perdent", "sm-l-moins"))
    corps.append(_t(x0 + 144, 14, "pas touchés", "sm-doux"))
    for r in deciles:
        g, p = float(r["share_winners"]), float(r["share_losers"])
        corps.append(_t(x0 - 6, y + 11, f"D{r['decile']}", "sm-encre", "end"))
        x = x0
        for share, cls in ((g, "sm-plus"), (p, "sm-moins"), (1 - g - p, "sm-neutre")):
            w = max(share, 0.0) * (x1 - x0)
            if w > 0.05:
                corps.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="14" '
                             f'class="{cls}"/>')
            x += w
        if g + p > 0.005:
            corps.append(_t(x0 + 3 + (g + p) * (x1 - x0), y + 11,
                            f"{_fr((g + p) * 100)} %", "sm-encre"))
        y += 19
    for t in (0, 0.5, 1):
        corps.append(_t(x0 + t * (x1 - x0), y + 12, f"{int(t * 100)} %", "sm-doux",
                        "middle"))
    corps.append(_t(x1, y + 28, "part des ménages du décile", "sm-doux", "end"))
    desc = "; ".join(f"D{r['decile']} : {_fr(r['share_winners'] * 100)} % gagnent, "
                     f"{_fr(r['share_losers'] * 100)} % perdent" for r in deciles)
    return _svg(ident, y + 36, "Qui la mesure touche, décile par décile", desc, corps)


def colonnes_deciles(ident: str, deciles: list[dict[str, Any]], sign: int) -> str:
    """Le gain moyen par ménage de chaque décile, en euros par an, en colonnes."""
    values = [sign * float(r["mean_delta"]) for r in deciles]
    ticks = _ticks(min(0.0, *values), max(0.0, *values))
    top, h, x0, x1 = 16.0, 150.0, 52.0, W - 10.0

    def y(v: float) -> float:
        return top + h - (v - ticks[0]) / (ticks[-1] - ticks[0]) * h

    corps = []
    d = _dec(ticks)
    for t in ticks:
        corps.append(f'<line x1="{x0}" y1="{y(t):.1f}" x2="{x1}" y2="{y(t):.1f}" '
                     f'class="sm-grille"/>')
        corps.append(_t(x0 - 6, y(t) + 4, _fr(t, d), "sm-doux", "end"))
    step = (x1 - x0) / len(values)
    for i, v in enumerate(values):
        a, b = sorted((y(0), y(v)))
        cls = "sm-plus" if v >= 0 else "sm-moins"
        corps.append(f'<rect x="{x0 + i * step + 3:.1f}" y="{a:.1f}" width="{step - 6:.1f}" '
                     f'height="{max(b - a, 0.8):.1f}" class="{cls}"/>')
        corps.append(_t(x0 + (i + .5) * step, top + h + 16, f"D{i + 1}", "sm-doux",
                        "middle"))
    corps.append(f'<line x1="{x0}" y1="{y(0):.1f}" x2="{x1}" y2="{y(0):.1f}" '
                 f'class="sm-zero"/>')
    corps.append(_t(x1, top + h + 34, "€ par ménage et par an ; D1 = les 10 % les plus "
                    "modestes", "sm-doux", "end"))
    desc = "; ".join(f"D{i + 1} : {_fr(v)} €" for i, v in enumerate(values))
    return _svg(ident, top + h + 42, "Le gain moyen par ménage, décile par décile", desc,
                corps)


def ligne_annees(ident: str, years: list[int], series: list[tuple[str, list[float], str]],
                 reperes: list[tuple[int, str]], bande: list[tuple[float, float]] | None = None,
                 titre: str = "La dette, année par année",
                 unite: str = "Δ dette, points de PIB") -> str:
    """Δ dette année par année, en points de PIB : une ligne par vue, et des repères
    verticaux là où la courbe change de pente pour une raison connue."""
    values = [v * 100 for _, vs, _ in series for v in vs]
    values += [v * 100 for lo_hi in bande or [] for v in lo_hi]
    ticks = _ticks(min(0.0, *values), max(0.0, *values))
    top, h, x0, x1 = 44.0, 150.0, 46.0, W - 50.0

    def x(yr: int) -> float:
        return x0 + (yr - years[0]) / max(years[-1] - years[0], 1) * (x1 - x0)

    def y(v: float) -> float:
        return top + h - (v - ticks[0]) / (ticks[-1] - ticks[0]) * h

    corps = []
    d = _dec(ticks)
    for t in ticks:
        corps.append(f'<line x1="{x0}" y1="{y(t):.1f}" x2="{x1}" y2="{y(t):.1f}" '
                     f'class="sm-grille"/>')
        corps.append(_t(x0 - 6, y(t) + 4, _fr(t, d), "sm-doux", "end"))
    corps.append(f'<line x1="{x0}" y1="{y(0):.1f}" x2="{x1}" y2="{y(0):.1f}" '
                 f'class="sm-zero"/>')
    if bande:
        haut = " ".join(f"{x(yr):.1f},{y(hi * 100):.1f}" for yr, (_, hi) in zip(years, bande,
                                                                              strict=True))
        bas = " ".join(f"{x(yr):.1f},{y(lo * 100):.1f}" for yr, (lo, _) in
                       reversed(list(zip(years, bande, strict=True))))
        corps.append(f'<polygon points="{haut} {bas}" class="sm-bande"/>')
    for k, (yr, label) in enumerate(reperes):
        corps.append(f'<line x1="{x(yr):.1f}" y1="{top - 4}" x2="{x(yr):.1f}" '
                     f'y2="{top + h}" class="sm-repere"/>')
        corps.append(_t(x(yr), top - 8 - 11 * (k % 2), label, "sm-doux", "middle"))
    for _name, vs, cls in series:
        pts = " ".join(f"{x(yr):.1f},{y(v * 100):.1f}" for yr, v in zip(years, vs,
                                                                          strict=True))
        corps.append(f'<polyline points="{pts}" class="{cls}" fill="none"/>')
        corps.append(_t(x1 + 4, y(vs[-1] * 100) + 4, f"{_fr(vs[-1] * 100, 2)}", "sm-encre"))
    for yr in (years[0], (years[0] + years[-1]) // 2, years[-1]):
        corps.append(_t(x(yr), top + h + 16, str(yr), "sm-doux", "middle"))
    corps.append(_t(x1, top + h + 32, unite, "sm-doux", "end"))
    corps.insert(0, _t(4, 12, titre, "sm-encre"))
    if len(series) > 1:
        for k, (name, _, cls) in enumerate(series):
            ly = top + h + 48 + 16 * k
            corps.append(f'<line x1="8" y1="{ly}" x2="30" y2="{ly}" class="{cls}"/>')
            corps.append(_t(36, ly + 4, name, "sm-doux"))
    desc = "; ".join(f"{name} : " + ", ".join(f"{yr} {_fr(v * 100, 2)}"
                                             for yr, v in zip(years, vs, strict=True))
                     for name, vs, _ in series)
    return _svg(ident, top + h + (40 + 16 * len(series) if len(series) > 1 else 40), titre,
                desc, corps)


def plage(ident: str, rows: list[tuple[str, float, float, float, str]], unite: str,
          echelle: float) -> str:
    """Des intervalles p10–p90 et leur médiane : (libellé, p10, p50, p90, texte)."""
    values = [v for _, a, b, c, _ in rows for v in (a, b, c)]
    ticks = _ticks(min(0.0, *values), max(0.0, *values))
    x0, x1 = 92.0, W - 14.0

    def x(v: float) -> float:
        return x0 + (v - ticks[0]) / (ticks[-1] - ticks[0]) * (x1 - x0)

    corps, y = [], 18.0
    for label, a, b, c, texte in rows:
        corps.append(_t(x0 - 6, y + 4, label, "sm-encre", "end"))
        corps.append(f'<line x1="{x(a):.1f}" y1="{y:.1f}" x2="{x(c):.1f}" y2="{y:.1f}" '
                     f'class="sm-intervalle"/>')
        corps.append(f'<circle cx="{x(b):.1f}" cy="{y:.1f}" r="4" class="sm-point"/>')
        corps.append(_t(x(b), y - 8, texte, "sm-encre", "middle"))
        y += 34
    corps.append(f'<line x1="{x(0):.1f}" y1="4" x2="{x(0):.1f}" y2="{y - 14:.1f}" '
                 f'class="sm-zero"/>')
    d = _dec(ticks, echelle)
    for t in ticks:
        corps.append(_t(x(t), y, _fr(t * echelle, d), "sm-doux", "middle"))
    corps.append(_t(x1, y + 16, unite, "sm-doux", "end"))
    desc = "; ".join(f"{label} : de {_fr(a * echelle, 1)} à {_fr(c * echelle, 1)}, "
                     f"médiane {texte}" for label, a, b, c, texte in rows)
    return _svg(ident, y + 24, "L'activité, horizon par horizon", desc, corps)


# --------------------------------------------------------------------------- #
# les nombres d'une mesure seule, lus dans ses rapports
# --------------------------------------------------------------------------- #
INSTRUMENTS_LUS = {
    "impot_sur_le_revenu": "impôt sur le revenu", "tva": "TVA", "csg": "CSG",
    "cotisations_employeurs": "cotisations des employeurs",
    "cotisations_salariales": "cotisations des salariés", "impot_societes": "impôt sur "
    "les sociétés", "prestations": "prestations", "taxe_carbone": "accises sur l'énergie",
}
CHAMPS_LUS = {
    "ir": "impôt sur le revenu", "af": "allocations familiales", "ppa": "prime d'activité",
    "rsa": "RSA", "aide_logement": "aides au logement", "csg_deductible": "CSG déductible",
    "csg_imposable": "CSG imposable", "crds": "CRDS", "cotisations_salariales":
    "cotisations des salariés", "cotisations_employeur": "cotisations des employeurs",
    "aspa": "minimum vieillesse", "paje": "PAJE", "cvec": "CVEC", "ars": "allocation de "
    "rentrée", "cf": "complément familial", "asf": "soutien familial",
    "allegement_general": "allègement général", "prelevements_pensions": "prélèvements "
    "sur les pensions", "csg_retraite": "CSG des retraités",
}
#: Des totaux qui somment d'autres champs : la page ne les montre pas comme des modules.
AGREGATS = {"revenu_disponible", "revenu_disponible_droit", "ir_avant_niches",
            "salaire_super_brut", "salaire_net", "salaire_imposable", "rsa_droit",
            "ppa_droit", "aefa_droit", "crds_mini_droit"}


def _menages(first: dict[str, Any]) -> dict[str, Any] | None:
    r = first["response"]
    return r.get("menages") if first.get("kind") == "mixte" else (
        r if first.get("kind") == "menages" else None)


def _entreprises(first: dict[str, Any]) -> dict[str, Any] | None:
    r = first["response"]
    return r.get("entreprises") if first.get("kind") == "mixte" else (
        r if first.get("kind") == "entreprises" else None)


def _lue(path: dict[str, Any]) -> dict[str, Any] | None:
    for p in path.get("side_by_side") or []:
        if p["persistence"] == etude.LUE:
            return p
    return None


def _modules(menages: dict[str, Any] | None) -> list[tuple[str, float]]:
    """Les champs du ménage que la mesure change, en euros, hors des totaux."""
    if menages is None:
        return []
    out = [(k, float(v)) for k, v in (menages.get("deltas") or {}).items()
           if k not in AGREGATS and not k.endswith("_droit") and abs(float(v)) >= 1e6]
    return sorted(out, key=lambda kv: -abs(kv[1]))[:8]


# --------------------------------------------------------------------------- #
# la page d'une mesure
# --------------------------------------------------------------------------- #
ETAPES = ("Le texte, traduit en paramètres", "Les ménages touchés", "L'effet mécanique",
          "Les comportements", "L'activité et le bouclage", "Les gagnants et les perdants",
          "Le coût, couche par couche")


def _provenance(corps: str) -> str:
    """Ce qui ne sert qu'au relecteur (rapports, champs, commits, noms de code) sort du
    texte et se replie en fin d'étape : « D'où viennent ces nombres » (but 25, D-457)."""
    import re

    sources = re.findall(r'<p class="note-source">.*?</p>', corps, re.S)
    if not sources:
        return corps
    corps = re.sub(r'<p class="note-source">.*?</p>', "", corps, flags=re.S)
    corps = corps.replace("<br></figcaption>", "</figcaption>")
    return (corps + '<details class="sm-prov"><summary>D\'où viennent ces nombres</summary>'
            + "".join(sources) + "</details>")


FLECHE = f'<div class="flux-fleche">{site_composants._FLECHE}</div>'
HAUT = '<p class="sm-haut"><a href="#contenu">↑ Retour en haut</a></p>'


def _etape(k: int, corps: str, phrase: str) -> str:
    return (f'<section class="sm-etape" id="etape-{k}"><h2><span class="etape-n">{k}</span>'
            f"{_e(ETAPES[k - 1])}</h2><p class=\"sm-phrase\">{phrase}</p>"
            f"{_provenance(corps)}{HAUT}</section>")


def page_mesure(study: etude.Etude, m: Any, seule: dict[str, Any], programme: Any,
                entry: dict[str, Any]) -> tuple[str, str]:
    """(titre, corps HTML) de la page d'une mesure."""
    first, path, commit_a = seule["first"], seule["path"], seule["first"]["commit"]
    commit_b = path["commit"]
    dossier = f"{etude._relative(study.rapports)}/{study.dossier(seule['name'])}"
    fa = f"{dossier}premiere_annee_{seule['name']}.json"
    fb = f"{dossier}predictif_{seule['name']}.json"
    lu = etude.lecture_seule(seule)
    year = seule["scenario"].year
    menages, ent = _menages(first), _entreprises(first)
    out: list[str] = []
    titre = f"{m.libelle} — {programme.candidat}"
    out.append(f'<p class="sm-fil"><a href="{INDEX}">Une mesure pas à pas</a> &rsaquo; '
               f'<a href="{INDEX}#{programme.slug}">{_e(programme.candidat)}</a></p>')
    out.append(f"<h1>{_m(m.libelle)}</h1>")
    out.append(f'<p class="chapeau">Une mesure du programme de {_e(programme.candidat)}'
               f", suivie de son texte au coût qu'en publie l'étude, en sept étapes. Chaque "
               f"nombre dit son étage de confiance et sa source : le rapport, le champ, le "
               f"commit.</p>")
    # Le résultat d'abord, puis le chemin.
    out.append('<div class="sm-cartes">'
               f'<div class="sm-carte"><span>coût {year}, mécanique</span>'
               f'{_badge(_eur(lu["figee"]), "L2")}</div>'
               f'<div class="sm-carte"><span>dette en {etude.LAST_YEAR}, à θ½</span>'
               f'{_badge(etude._points(lu["dette"]), lu["etage"], True)}</div>'
               + ("" if lu["bas"] is None else
                  f'<div class="sm-carte"><span>gain des 30 % les plus modestes</span>'
                  f'{_badge(_eur(lu["bas"]), "L2")}</div>')
               + "</div>")
    out.append('<ol class="sm-sommaire">' + "".join(
        f'<li><a href="#etape-{k}">{_e(t)}</a></li>' for k, t in enumerate(ETAPES, 1))
        + "</ol>")

    # 1. Le texte -> les paramètres.
    ch = m.chiffrage
    citations = "".join(
        f'<blockquote class="sm-cite"><p>{_m(_guillemets(s.citation))}</p><footer>{_e(s.type)}, '
        f'{_e(s.date)} · <a href="{_e(s.url)}">la source</a></footer></blockquote>'
        for s in m.sources[:2])
    feuilles = _feuilles(ch.reforme)
    params = "".join(
        f"<li>{_badge(etude.valeur_lue(champ, v), 'programme')}"
        + (f" (réglage {k})" if len(feuilles) > 1 else "") + "</li>"
        for k, (champ, v) in enumerate(feuilles, 1))
    plages = "".join(
        f"<li>de {_badge(etude.valeur_lue(p.champ, p.min), 'hypothèse')} à "
        f"{_badge(etude.valeur_lue(p.champ, p.max), 'hypothèse')}</li>" for p in ch.plages)
    codes = "; ".join(f"<code>{_e(champ)}</code> = {_e(etude.valeur_lue(champ, v))}"
                      for champ, v in feuilles)
    schema = (
        '<figure class="flux"><div class="flux-grille">'
        '<div class="flux-col flux-entree"><p class="flux-col-titre">Ce que dit le candidat'
        f'</p><div class="flux-boite"><b>{_m(m.parametre)}</b>{citations}</div></div>'
        + FLECHE +
        '<div class="flux-col flux-fait"><p class="flux-col-titre">Le réglage du moteur</p>'
        f'<div class="flux-boite"><ul>{params}</ul>'
        + (f'<p class="sm-petit">Plage réglable : </p><ul>{plages}</ul>' if plages else "")
        + "</div></div>" + FLECHE +
        '<div class="flux-col flux-sortie"><p class="flux-col-titre">La couche qu\'il '
        "touche</p><div class=\"flux-boite\">"
        f"<b>{'les ménages' if ch.couche == 'menages' else 'les entreprises'}"
        f"</b><span>dès {year}"
        + (f", les années {', '.join(map(str, path['annees']))}" if path.get("annees")
           else f", jusqu'en {etude.LAST_YEAR}") + "</span></div></div></div></figure>")
    note = (f'<p class="sm-note"><strong>La traduction</strong> : {_m(ch.note, "hypothèse")}</p>'
            if ch.note else "")
    out.append(_etape(1, schema + note + (
        f'<p class="note-source"><code>programmes/{_e(programme.slug)}.json</code> · '
        f"mesure <code>{_e(m.id)}</code> · relevé du {_e(programme.releve)} · les "
        f"réglages, par leur nom dans le moteur : {codes}</p>"),
        "Le texte du candidat devient un ou deux nombres que le moteur sait lire. Tout ce "
        "qui n'a pas de bouton reste hors du chiffrage, et la note le dit."))

    # 2. Les ménages touchés.
    if menages and menages.get("deciles"):
        deciles = menages["deciles"]
        touches = sum(float(r["n_households"]) * (float(r["share_winners"])
                                                  + float(r["share_losers"]))
                      for r in deciles)
        total = sum(float(r["n_households"]) for r in deciles)
        meta = menages.get("meta") or {}
        corps = (
            f'<p class="sm-gros">{_fr(touches / 1e6, 1)} million{"s" if touches >= 2e6 else ""}'
            f" de ménages sur {_fr(total / 1e6, 1)} voient leur revenu changer.</p>"
            + _figure(parts_deciles(f"{m.id}-touches", deciles),
                      f"pour chaque dixième des ménages, rangés par niveau de vie, la part qui "
                      f"gagne, qui perd et que la mesure ne touche pas ; en {year}, vue figée.",
                      f"Le nombre de ménages touchés est un agrégat dérivé : la part des "
                      f"gagnants et des perdants de chaque décile (<code>share_winners</code>, "
                      f"<code>share_losers</code>) fois ses ménages "
                      f"(<code>n_households</code>). La population compte "
                      f"{_fr(float(meta.get('sampled_households', 0)))} ménages simulés, "
                      f"chacun pesant pour d'autres ; elle en représente "
                      f"{_fr(float(meta.get('households', total)) / 1e6, 1)} millions.")
            + _source(fa, "response.deciles" if first["kind"] == "menages"
                      else "response.menages.deciles", commit_a))
    else:
        corps = ('<p class="sm-gros">Aucun ménage directement : la mesure touche les '
                 "entreprises.</p>")
    out.append(_etape(2, corps, "On applique la loi modifiée à chaque ménage de la "
                      "population, puis on compare son revenu à celui de la loi en vigueur."))

    # 3. L'effet mécanique.
    rows = [(CHAMPS_LUS.get(k, k.replace("_", " ")), v, _eur(v))
            for k, v in _modules(menages)]
    if ent is not None and abs(float(ent.get("reform_cost") or 0)) >= 1e6:
        rows.append(("entreprises", -float(ent["reform_cost"]),
                     _eur(-float(ent["reform_cost"]))))
    corps = ""
    if rows:
        corps += _figure(
            barres(f"{m.id}-modules", rows, "Ce que la mesure change, module par module",
                   "milliards d'euros", 1e-9),
            f"l'écart, en milliards d'euros de {year}, entre la loi modifiée et la loi en "
            f"vigueur, pour chaque module du moteur que la mesure change ; un impôt qui "
            f"baisse est négatif, une prestation qui monte positive. Personne ne change "
            f"de comportement.",
            "")
        corps += _source(fa, "response.deltas" if first["kind"] == "menages"
                         else "response.menages.deltas", commit_a)
    corps += ('<div class="sm-deux">'
              f'<div><span>vue figée : la population de 2024 au droit de {year}</span>'
              f'{_badge(_eur(lu["figee"]), "L2")}'
              + _source(fa, "response.reform_cost", commit_a) + "</div>"
              f'<div><span>vue vieillie : la population vieillie jusqu\'en {year}</span>'
              f'{_badge(_eur(lu["vieillie"]), "L2")}'
              + _source(fb, "years[0].mechanical_aged_eur", commit_b) + "</div></div>")
    out.append(_etape(3, corps, "Le coût mécanique : ce que l'État perd ou gagne si personne "
                      "ne change rien à sa vie. Deux vues, parce que la population date de "
                      "2024 ; l'écart entre elles est celui du vieillissement."))

    # 4. Les comportements.
    beh = (menages or {}).get("behavioural") or {}
    band = beh.get("band")
    canaux = [c for c in beh.get("channels") or [] if c.get("applies")]
    if band:
        rows = [("mécanique", -float(beh["mechanical"]), _eur(-float(beh["mechanical"])))]
        rows += [(c["label"], -float(c["central"] or 0), _eur(-float(c["central"] or 0)))
                 for c in canaux]
        rows.append(("après comportements", -float(band["p50"]), _eur(-float(band["p50"]))))
        corps = _figure(
            barres(f"{m.id}-comportements", rows, "Le coût, avant et après les "
                   "comportements", "milliards d'euros", 1e-9),
            f"le coût de la première année ({year}), en milliards d'euros : mécanique, ce que "
            f"chaque canal de comportement en rend ou en ajoute, et le coût central qui en "
            f"résulte. Le signe est celui d'un coût : la recette perdue du rapport, "
            f"inversée.", "")
        corps += (f'<p class="sm-note">L\'étendue : de {_badge(_eur(-float(band["p90"])), "L3")}'
                  f' à {_badge(_eur(-float(band["p10"])), "L3")} (p10 à p90 des élasticités). '
                  f"{_e(beh.get('grade_reason', ''))}</p>")
    else:
        corps = (f'<p class="sm-gros">Aucun canal de comportement ne couvre cette mesure : '
                 f"le coût reste mécanique.</p><p class=\"sm-note\">"
                 f"{_e(beh.get('grade_reason') or 'La mesure ne touche pas les ménages.')}"
                 "</p>")
    corps += _source(fa, "response.behavioural" if first["kind"] == "menages"
                     else "response.menages.behavioural", commit_a)
    out.append(_etape(4, corps, "Les ménages réagissent : ils travaillent un peu plus ou "
                      "un peu moins, déclarent autrement. Chaque canal vient d'une élasticité "
                      "publiée ; sans elle, rien n'est ajouté."))

    # 5. L'activité et le bouclage.
    macro = (menages or {}).get("macro") or {}
    corps = ""
    if macro.get("available") and macro.get("jobs"):
        rows5 = []
        for h, v in sorted(macro["jobs"].items(), key=lambda kv: int(kv[0])):
            rows5.append((f"{h} an{'s' if int(h) > 1 else ''}", float(v["p10"]),
                          float(v["p50"]), float(v["p90"]), f"{_fr(float(v['p50']), 1)}"))
        corps += _figure(
            plage(f"{m.id}-emplois", rows5, "milliers d'emplois (équivalents temps plein)",
                  1.0),
            "les emplois en plus ou en moins, en milliers d'équivalents temps plein, 1, 2 "
            "et 3 ans après la mesure : le point est la médiane, le trait va du p10 au p90 "
            "des multiplicateurs publiés.",
            "")
        corps += _source(fa, "response.macro.jobs", commit_a)
    dec = ((path.get("lectures") or {}).get("decomposition") or {}).get("vieillie")
    if dec:
        rows6 = [("le coût seul", float(dec["cout"]), etude._points(dec["cout"])),
                 ("le PIB qui change", float(dec["denominateur"]),
                  etude._points(dec["denominateur"])),
                 ("les recettes induites", float(dec["retroaction"]),
                  etude._points(dec["retroaction"])),
                 ("Δ dette", float(dec["total"]), etude._points(dec["total"]))]
        corps += _figure(
            barres(f"{m.id}-bouclage", rows6, "Du coût à la dette de 2035", "points de PIB",
                   100.0),
            f"la dette en {etude.LAST_YEAR}, en points de PIB, vue vieillie, à θ½ : ce que "
            f"le coût y ajoute seul, puis ce qu'y changent le PIB plus grand ou plus petit et "
            f"les recettes que l'activité induit. Les trois premières barres somment à la "
            f"dernière.", "")
        corps += _source(fb, "lectures.decomposition.vieillie", commit_b)
    if not corps:
        corps = '<p class="sm-gros">Pas de bouclage macro lu pour cette mesure.</p>'
    out.append(_etape(5, corps, "Ce que la mesure fait à l'activité, lu dans Mésange, le "
                      "modèle de l'Insee et de la DG Trésor, puis rendu au budget : plus "
                      "d'activité, plus de recettes."))

    # 6. Gagnants et perdants.
    if menages and menages.get("deciles"):
        corps = _figure(colonnes_deciles(f"{m.id}-deciles", menages["deciles"],
                                         seule["sign"]),
                        f"le gain moyen par ménage de chaque décile de niveau de vie, en "
                        f"euros par an, en {year}, vue figée ; tous les ménages du décile "
                        f"comptent, touchés ou non.", "")
        if lu["bas"] is not None:
            corps += (f'<p class="sm-note">Les trois premiers déciles y gagnent en tout '
                      f'{_badge(_eur(lu["bas"]), "L2")}, sur '
                      f'{_badge(_eur(lu["menages"]), "L2")} pour tous les ménages.</p>')
        corps += _source(fa, "response.deciles[].mean_delta" if first["kind"] == "menages"
                         else "response.menages.deciles[].mean_delta", commit_a)
    else:
        corps = '<p class="sm-gros">Une mesure des seules entreprises : pas de déciles.</p>'
    out.append(_etape(6, corps, "Qui y gagne : les ménages rangés du plus modeste au plus "
                      "aisé, dix groupes de même taille."))

    # 7. Le coût couche par couche.
    out.append(_etape(7, _couches(seule, lu, fa, fb, year, path), "Chaque couche ajoute "
                      "quelque chose à la précédente et dit d'où elle le lit. Le verdict se "
                      "lit sur la dernière, sous ses hypothèses."))
    out.append(f'<p class="sm-retour"><a href="{study.nom}.html#chaque-mesure-seule-et-leur-'
               f'interaction">Cette mesure dans l\'étude de {_e(programme.candidat)}</a> · '
               f'<a href="{INDEX}#{programme.slug}">ses autres mesures</a></p>')
    return titre, "\n".join(out)


def _guillemets(text: str) -> str:
    text = text.strip()
    return text if text.startswith("«") else f"« {text} »"


def _feuilles(d: dict[str, Any], prefix: str = "") -> list[tuple[str, float]]:
    out = []
    for k, v in d.items():
        if isinstance(v, dict):
            out += _feuilles(v, f"{prefix}{k}.")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append((f"{prefix}{k}", float(v)))
    return out


def _couches(seule: dict[str, Any], lu: dict[str, Any], fa: str, fb: str, year: int,
             path: dict[str, Any]) -> str:
    first = seule["first"]
    menages = _menages(first) or {}
    band = (menages.get("behavioural") or {}).get("band")
    mc = ((path.get("monte_carlo") or {}).get("vues") or {}).get("vieillie")
    pre = "response." if first["kind"] == "menages" else "response.menages."
    rows = [
        ("L2", "mécanique, vue figée", f"coût {year}", _badge(_eur(lu["figee"]), "L2"),
         _source(fa, "response.reform_cost", first["commit"])),
        ("L2", "mécanique, vue vieillie", f"coût {year}", _badge(_eur(lu["vieillie"]), "L2"),
         _source(fb, "years[0].mechanical_aged_eur", path["commit"])),
        ("L3", "avec les comportements", f"coût {year}",
         _badge(_eur(-float(band["p50"])), "L3") if band else "rien n'est ajouté",
         _source(fa, f"{pre}behavioural.band.p50", first["commit"])),
        (lu["etage"], "la dette, avec la boucle macro", f"Δ dette {etude.LAST_YEAR}, à θ½",
         _badge(etude._points(lu["dette"]), lu["etage"], True),
         _source(fb, "side_by_side[lue].years[-1].delta_aged", path["commit"])),
    ]
    if mc:
        rows.append(("MC", "les tirages du Monte-Carlo", "dette en hausse",
                     f'<span class="nombre">{_fr(float(mc["p_hausse"]) * 100)} % des '
                     f"tirages</span>",
                     _source(fb, "monte_carlo.vues.vieillie.p_hausse", path["commit"])))
    items = "".join(
        f'<li class="sm-couche"><span class="sm-niv">{_e(niv)}</span><div><strong>'
        f"{_e(quoi)}</strong> <span class=\"sm-petit\">{_e(lequel)}</span><div>{val}</div>"
        f"{src}</div></li>" for niv, quoi, lequel, val, src in rows)
    serie = _lue(path)
    graph = ""
    if serie:
        years = [int(r["year"]) for r in serie["years"]]
        aged = [float(r["delta_aged"]) for r in serie["years"]]
        frozen = [float(r["delta_frozen"]) for r in serie["years"]]
        reperes, pourquoi = reperes_trajectoire(path, years)
        graph = _figure(
            ligne_annees(f"{seule['mesure']}-dette", years,
                         [("vue vieillie", aged, "sm-l1"), ("vue figée", frozen, "sm-l2")],
                         reperes),
            f"l'écart de dette à la référence, en points de PIB, chaque année de "
            f"{years[0]} à {years[-1]}, à θ½, sous la persistance « lue » ; trait plein : "
            f"vue vieillie, tirets : vue figée. {pourquoi}",
            _source(fb, "side_by_side[lue].years[].delta_aged, delta_frozen",
                    path["commit"]))
    return f'<ol class="sm-couches">{items}</ol>{graph}'


def reperes_trajectoire(path: dict[str, Any], years: list[int]
                        ) -> tuple[list[tuple[int, str]], str]:
    """Où une courbe de dette change de pente pour une raison connue, et la phrase qui le
    dit : une mesure qui entre une année, les horizons de Mésange entre lesquels l'effet
    macro est interpolé, la persistance « éteinte » qui le coupe après trois ans."""
    reperes: list[tuple[int, str]] = []
    phrases = []
    annees = path.get("annees") or []
    if annees:
        reperes.append((min(annees), "la mesure entre"))
        phrases.append(f"La mesure ne s'applique qu'en {', '.join(map(str, annees))}.")
    macro = (path.get("rejeu") or {}).get("macro") or {}
    horizons = [int(h) for h in macro.get("horizons") or []]
    dans = [years[0] + h - 1 for h in horizons if years[0] < years[0] + h - 1 < years[-1]]
    if horizons:
        for yr in dans:
            reperes.append((yr, f"{yr - years[0] + 1} ans"))
        phrases.append(
            f"L'effet sur l'activité est lu dans Mésange à {', '.join(map(str, horizons))} "
            f"ans et interpolé en ligne droite entre eux : la pente change à ces horizons "
            f"({', '.join(map(str, dans))}), pas à cause du bruit.")
    phrases.append("La pente qui reste vient des intérêts : chaque année, la dette de "
                   "l'année d'avant porte intérêt.")
    return reperes, " ".join(phrases)


# --------------------------------------------------------------------------- #
# l'index, le résumé d'une étude, la note des courbes
# --------------------------------------------------------------------------- #
def mesures_de(study: etude.Etude, entries: list[dict[str, Any]]
               ) -> list[tuple[Any, dict[str, Any]]]:
    """(la mesure du programme, son entrée seule) pour chaque mesure seule chiffrée."""
    if study.programme is None or not entries:
        return []
    from impots import programmes as pg

    p = pg.charger(study.programme)
    if not entries[0].get("mesures"):
        # A programme of one priced measure: its part is that measure alone.
        if len(p.chiffrees()) == 1 and entries[0].get("mesures_absentes") is None:
            return [(p.chiffrees()[0], {**entries[0], "mesure": p.chiffrees()[0].id})]
        return []
    by_id = {m.id: m for m in p.chiffrees()}
    return [(by_id[s["mesure"]], s) for s in entries[0]["mesures"]]


def pages(study: etude.Etude, entries: list[dict[str, Any]],
          page: Callable[[str, str], str]) -> dict[str, str]:
    """Les pages des mesures d'une étude, par nom de fichier."""
    out = {}
    from impots import programmes as pg

    if study.programme is None:
        return out
    p = pg.charger(study.programme)
    for m, seule in mesures_de(study, entries):
        titre, corps = page_mesure(study, m, seule, p, entries[0])
        out[lien(p.slug, m.id)] = page(titre, corps)
    return out


def index(listes: list[tuple[Any, etude.Etude, list[tuple[Any, dict[str, Any]]]]]) -> str:
    """Le choix : un candidat, puis une de ses mesures."""
    out = ["<h1>Une mesure pas à pas</h1>",
           '<p class="chapeau">Choisissez un candidat, puis une de ses mesures : sa page '
           "la suit de ce que dit le texte au coût qu'en publie l'étude, en sept étapes, "
           "chacune avec son schéma et sa source. Seules les mesures chiffrées seules, avec "
           "leurs deux rapports, y sont.</p>",
           f'<p class="sm-petit"><a href="{COMPARER}">Comparer les candidats</a></p>',
           '<ol class="sm-sommaire sm-apercu">' + "".join(f"<li>{_e(t)}</li>" for t in ETAPES)
           + "</ol>"]
    for p, study, mesures in listes:
        items = "".join(
            f'<li><div class="sm-nom"><strong>{_m(m.libelle)}</strong>'
            f'<span>{_m(m.parametre)}</span>'
            f'<a href="{lien(p.slug, m.id)}">La suivre pas à pas →</a></div>'
            f'<span class="sm-cout">{_badge(_eur(etude.lecture_seule(s)["figee"]), "L2")}'
            f"</span></li>" for m, s in mesures)
        out.append(f'<section class="sm-candidat" id="{p.slug}"><h2>{_e(p.candidat)}</h2>'
                   f'<p class="sm-petit">{_e(p.parti)} · <a href="{study.nom}.html">'
                   f"l'étude</a></p><ul class=\"sm-mesures\">{items}</ul></section>")
    return "\n".join(out)


def _cellules(line: str) -> list[str]:
    return [c.strip() for c in line.strip()[1:-1].split("|")]


def resume(study: etude.Etude, entries: list[dict[str, Any]], lines: list[str],
           n: etude.Nombres, text: Callable[[str, etude.Nombres], str],
           body: Callable[[list[str], etude.Nombres], str]) -> str:
    """Le résumé lisible d'une étude, avant son détail : le verdict et le coût (le
    tableau « En bref », ses cellules en cartes), pour qui (son graphique des déciles),
    puis chaque mesure avec le lien de sa page pas à pas."""
    start = lines.index("## En bref")
    stop = next((i for i, ln in enumerate(lines[start + 1:]) if ln.startswith("## ")),
                len(lines))
    table = [ln for ln in lines[start + 1:start + 1 + stop] if ln.startswith("|")]
    out = ['<section class="sm-resume" id="en-resume"><h2>En résumé</h2>']
    if len(table) >= 3:
        head = _cellules(table[0])
        for row in table[2:]:
            cells = _cellules(row)
            # Le verdict d'abord, puis le coût, la dette : l'ordre du lecteur.
            paires = sorted(((h, c) for h, c in zip(head[1:], cells[1:], strict=False)
                             if c not in ("—", "")), key=lambda hc: hc[0] != "verdict")
            cartes = "".join(
                f'<div class="sm-carte{" sm-verdict" if h == "verdict" else ""}">'
                f"<span>{text(h, n)}</span>{text(c, n)}</div>"
                for h, c in paires)
            out.append(f'<div class="sm-ligne"><h3>{text(cells[0], n)}</h3>'
                       f'<div class="sm-cartes">{cartes}</div></div>')
    out.append(part_chiffree(study))
    if study.programme is not None:
        out.append(f'<p class="sm-petit"><a href="{COMPARER}">Comparer aux autres '
                   "candidats</a> : ce qui se compare, et ce qui ne se compare pas.</p>")
    gdp = float((entries[0]["path"].get("start") or {}).get("gdp_eur") or 0)
    if gdp:
        out.append(f'<p class="sm-note"><strong>Pour lire les points de PIB</strong> : un '
                   f"point de PIB, c'est environ {_badge(f'{_fr(gdp / 100 / 1e9)} Md€', 'publié')}"
                   f" (le PIB de {entries[0]['path']['start']['year']}, divisé par cent)."
                   "</p>")
    # Pour qui : le graphique des déciles de la première ligne, avec sa légende.
    name = entries[0]["name"]
    for i, ln in enumerate(lines):
        if ln.startswith("![") and f"{name}-deciles" in ln:
            # The same figure as the detail's, its ids made the summary's own.
            figure = body(lines[i:i + 3], n).replace(f"{name}-deciles",
                                                     f"resume-{name}-deciles")
            out.append('<h3 id="pour-qui">Pour qui</h3>' + figure)
            break
    out.append("</section>")
    return "\n".join(out)


def lire_courbes(main: str, entries: list[dict[str, Any]]) -> str:
    """Sous chaque trajectoire d'une page d'étude, pourquoi ses courbes bougent."""
    for entry in entries:
        ident = f'id="{entry["name"]}-trajectoire'
        at = main.find(ident)
        if at < 0:
            continue
        end = main.find("</figure>", at)
        serie = _lue(entry["path"]) or {"years": entry["path"]["years"]}
        years = [int(r["year"]) for r in serie["years"]]
        _, pourquoi = reperes_trajectoire(entry["path"], years)
        court = ((entry["path"].get("rejeu") or {}).get("macro") or {}).get("court")
        if court:
            pourquoi += (f" La persistance « éteinte » coupe l'effet sur l'activité après "
                         f"{court} ans : sa courbe saute en {years[0] + int(court)}, par "
                         f"convention. La bande, la boîte θ, s'élargit parce que "
                         f"l'incertitude de chaque année s'ajoute dans la dette.")
        note = f'<p class="sm-lire"><strong>Pourquoi ça bouge</strong> : {_e(pourquoi)}</p>'
        main = main[:end] + note + main[end:]
    return main


# --------------------------------------------------------------------------- #
# la page d'une étude, refaite (but 25, D-457) : le résumé, le chemin du coût à la dette,
# la dette année par année, mesure par mesure, les plages ; le reste en provenance
# --------------------------------------------------------------------------- #
PERSISTANCES = {"lue": "lu dans Mésange", "eteint": "éteint après 3 ans",
                "tenu": "tenu au niveau de la 3e année"}
SECTIONS = (("en-resume", "En résumé"), ("quel-cout", "Quel coût ?"),
            ("pour-qui", "Pour qui"), ("cout-dette", "Du coût à la dette"),
            ("dette-annees", "La dette, année par année"),
            ("mesure-par-mesure", "Mesure par mesure"), ("plages", "Les réglages"),
            ("provenance", "Pour le relecteur"))


def _section(ident: str, corps: str) -> str:
    titre = dict(SECTIONS)[ident]
    return (f'<section class="sm-bloc" id="{ident}"><h2>{_e(titre)}</h2>{corps}{HAUT}'
            "</section>")


def _instrument(nom: str) -> str:
    return INSTRUMENTS_LUS.get(nom, nom.replace("_", " "))


def _freinent(entry: dict[str, Any]) -> list[str]:
    """Les instruments dont la boucle lit un PIB plus bas la première année : l'impulsion
    du chemin (`years[0].statistiques.vieillie.impulses`) fois le multiplicateur de PIB de
    Mésange à un an (`rejeu.macro.instruments`), négatif."""
    path = entry["path"]
    impulses = ((path["years"][0].get("statistiques") or {}).get("vieillie") or {}).get(
        "impulses") or {}
    tables = ((path.get("rejeu") or {}).get("macro") or {}).get("instruments") or {}
    out = []
    for nom, impulse in impulses.items():
        pib = (tables.get(nom) or {}).get("pib") or {}
        if isinstance(impulse, (int, float)) and pib.get("1") is not None and (
                entry["sign"] * float(impulse) * float(pib["1"]) < 0):
            out.append(_instrument(nom))
    return out


def cascade_etude(entry: dict[str, Any], ident: str) -> str:
    """Le coût de la première année, en milliards d'euros, puis le pont vers la dette de
    la dernière année, en points de PIB, chaque marche de sa couleur."""
    from impots import graphiques

    c = graphiques.cascade_nombres(entry)
    if c is None:
        return ""
    etage = etude.debt_etage(entry["path"])
    cls = {"comportements": "sm-c-comp"}
    rows1 = [(lab, v, _eur(v), cls.get(lab, "sm-c-cout")) for lab, v in c["cout"]]
    if len(rows1) > 1:
        rows1.append(("coût de la première année", c["cout_total"], _eur(c["cout_total"]),
                      "sm-c-total"))
    sans, pib, induites = (v for _, v in c["dette"])
    rows2 = [("le coût seul, sans effet sur l'activité", sans, etude._points(sans),
              "sm-c-cout"),
             ("le PIB qui change (le dénominateur)", pib, etude._points(pib), "sm-c-act"),
             ("les recettes que l'activité induit", induites, etude._points(induites),
              "sm-c-act2"),
             (f"Δ dette {c['annee']}", c["dette_total"], etude._points(c["dette_total"]),
              "sm-c-total")]
    out = [_figure(barres(f"{ident}-c1", rows1, f"Le coût de {c['premiere']}",
                          f"milliards d'euros de {c['premiere']}", 1e-9),
                   f"le coût de la première année ({c['premiere']}), en milliards d'euros "
                   f"de {c['premiere']} : mécanique, puis ce que les comportements y "
                   f"changent quand une étude publiée le permet.", "")]
    out.append(
        f'<div class="encadre"><b class="encadre-tag">Le pont</b> Ce coût, chaque année de '
        f"{c['premiere']} à {c['annee']}, s'ajoute à la dette ; rapporté au PIB de "
        f"{c['annee']}, il la monterait de {_badge(etude._points(sans), etage, True)} "
        f"si l'activité ne bougeait pas. C'est la première marche ci-dessous.</div>")
    out.append(_figure(barres(f"{ident}-c2", rows2, f"La dette de {c['annee']}",
                              f"points de PIB de {c['annee']}", 100.0),
                       f"l'écart de dette en {c['annee']}, en points de PIB, vue vieillie, "
                       f"à θ½, persistance « lue » : le coût seul (bleu), puis ce que "
                       f"l'activité y change (vert : le PIB plus grand ou plus petit ; "
                       f"violet : les recettes qu'elle induit), et la dette qui en "
                       f"résulte (noir). Les trois premières barres somment à la dernière.",
                       ""))
    act = pib + induites
    if act > 0:
        freinent = _freinent(entry)
        phrase = (f"<strong>Ici, l'activité fait monter la dette</strong>, de "
                  f"{_badge(etude._points(act), etage, True)} : la boucle lit un PIB plus "
                  f"bas qu'en référence, donc moins de recettes et un dénominateur plus "
                  f"petit.")
        if freinent:
            phrase += (f" Les prélèvements qu'elle lit comme freinant l'activité la "
                       f"première année : {_e(', '.join(freinent))} (une hausse de "
                       f"prélèvement, dans Mésange, réduit le PIB).")
    else:
        part = -act / sans if sans else 0.0
        phrase = (f"<strong>L'activité rend une part du coût</strong> : "
                  f"{_badge(etude._points(-act), etage, True)} sur "
                  f"{_badge(etude._points(sans), etage, True)}"
                  + (", plus de la moitié" if part > 0.5 else "") + ".")
    out.append(f'<p class="sm-note">{phrase}</p>')
    rows = {(r["persistence"], r["view"]): r for r in entry["debt"]}
    lue = rows.get(("lue", "vieillie"))
    juger = []
    for pers in ("eteint", "tenu"):
        r = rows.get((pers, "vieillie"))
        if r is not None:
            juger.append(f"si l'effet sur l'activité est {PERSISTANCES[pers]}, "
                         f"{_badge(etude._points(r['theta']), etage, True)}")
    if lue is not None and lue["corners"]:
        juger.append(f"aux deux bouts des fourchettes publiées (la boîte θ), de "
                     f"{_badge(etude._points(min(lue['corners'])), etage, True)} à "
                     f"{_badge(etude._points(max(lue['corners'])), etage, True)}")
    if juger:
        out.append('<p class="sm-note"><strong>Pour juger ce chiffre</strong> : la même '
                   "dette " + " ; ".join(juger) + ". Le chiffre de tête lit Mésange à ses "
                   "horizons, au milieu des fourchettes.</p>")
    out.append(_source(f"predictif_{entry['name']}.json",
                       "lectures.decomposition.vieillie ; side_by_side ; theta_box",
                       entry["path"]["commit"]))
    return "".join(out)


def trajectoire_etude(entry: dict[str, Any], ident: str) -> str:
    """La dette et le PIB de 2026 à 2035 en trois petits panneaux, deux ou trois séries
    chacun : les vues, les persistances, le PIB ; la bande θ derrière la série lue."""
    from impots import graphiques

    if not graphiques.rejouable(entry["path"]):
        return ""
    t = graphiques.trajectoire_nombres(entry)
    years, s = t["annees"], t["series"]
    reperes, pourquoi = reperes_trajectoire(entry["path"], years)
    panneaux = []
    a = [("vue vieillie", s[("lue", "vieillie")]["dette"], "sm-l1")]
    if ("lue", "figee") in s:
        a.append(("vue figée", s[("lue", "figee")]["dette"], "sm-l2"))
    panneaux.append(_figure(
        ligne_annees(f"{ident}-ta", years, a, reperes, bande=t["bande"]["dette"],
                     titre="La dette", unite="Δ dette, points de PIB"),
        f"l'écart de dette à la référence, en points de PIB, de {years[0]} à {years[-1]}, "
        f"à θ½, effet sur l'activité lu dans Mésange ; trait plein : la population "
        f"vieillie chaque année, tirets : figée en 2024 ; la bande : la boîte θ, du plus "
        f"bas au plus haut coin. {pourquoi} La bande s'élargit parce que l'incertitude "
        f"de chaque année s'ajoute dans la dette.", ""))
    b = [(PERSISTANCES[p], s[(p, "vieillie")]["dette"], cls)
         for p, cls in (("lue", "sm-l1"), ("eteint", "sm-l3"), ("tenu", "sm-l4"))
         if (p, "vieillie") in s]
    if len(b) > 1:
        court = ((entry["path"].get("rejeu") or {}).get("macro") or {}).get("court") or 3
        panneaux.append(_figure(
            ligne_annees(f"{ident}-tb", years, b, [(years[0] + int(court), "3 ans")],
                         titre="Si l'effet sur l'activité dure ou s'éteint",
                         unite="Δ dette, points de PIB"),
            f"la même dette, vue vieillie, sous trois conventions pour l'effet sur "
            f"l'activité : lu dans Mésange (le chiffre de tête), éteint après {court} ans, "
            f"tenu à son niveau de la 3e année. La courbe « éteint » quitte les autres en "
            f"{years[0] + int(court)} : c'est la convention, pas du bruit.", ""))
    pib = s[("lue", "vieillie")]["pib"]
    if any(abs(v) > 1e-9 for v in pib):
        panneaux.append(_figure(
            ligne_annees(f"{ident}-tc", years, [("PIB", pib, "sm-l1")], reperes,
                         bande=t["bande"]["pib"], titre="Le PIB",
                         unite="écart au PIB de référence, %"),
            f"l'écart du PIB à la référence, en pour cent, de {years[0]} à {years[-1]}, "
            f"vue vieillie, à θ½ ; la bande : la boîte θ.", ""))
    return ('<div class="sm-multiples">' + "".join(panneaux) + "</div>"
            + _source(f"predictif_{entry['name']}.json, rejoué par "
                      "impots.predictif.rejouer", "side_by_side ; theta_box",
                      entry["path"]["commit"]))


def plages_etude(study: etude.Etude, entries: list[dict[str, Any]]) -> str:
    """Chaque réglage d'une mesure : son coût au bas, à la valeur du candidat et au haut
    de sa plage (mécanique, 2026, vue vieillie), sur une ligne, nommé par la mesure."""
    from impots import programmes as pg

    plages = entries[0].get("plages") or []
    if not plages or study.programme is None:
        return ""
    by = {(r["mesure"], r["champ"], r["point"]): r for r in plages}
    p = pg.charger(study.programme)
    out = []
    for m in p.chiffrees():
        for k, plage_ in enumerate(m.chiffrage.plages, 1):
            pts = []
            for point in etude.POINTS:
                r = by.get((m.id, plage_.champ, point))
                if r is None:
                    break
                v = (pg._lire(m.chiffrage.reforme, plage_.champ) if point == "candidat"
                     else plage_.min if point == "bas" else plage_.max)
                pts.append((point, etude.valeur_lue(plage_.champ, v), v,
                            float(r["response"]["mechanical_first_year_eur"])))
            if len(pts) < 3:
                continue
            nom = m.libelle + (f", réglage {k}" if len(m.chiffrage.plages) > 1 else "")
            bout = ""
            if pts[1][2] in (pts[0][2], pts[2][2]):
                bout = (" La valeur du candidat est un bout de la plage : la plage va de "
                        "la mesure retirée à la mesure, ou de la mesure au plus loin "
                        "qu'on la pousse.")
            out.append(_figure(
                reglage(f"{m.id}-plage-{k}", nom, pts),
                f"le coût de la première année (2026), en milliards d'euros, mécanique, "
                f"population vieillie, quand on règle la mesure de {_badge(pts[0][1], 'hypothèse')} à "
                f"{_badge(pts[2][1], 'hypothèse')} ; le point plein est la valeur du candidat.{bout}",
                _source(f"plages/{m.id}__{plage_.champ}__*.json", "response."
                        "mechanical_first_year_eur", by[(m.id, plage_.champ,
                                                         "candidat")]["commit"])))
    if not out:
        return ""
    return ('<p class="sm-phrase">Ce que coûte chaque mesure si on la règle autrement. '
            "Chaque point est la mesure seule, sans comportements ni boucle.</p>"
            '<div class="sm-multiples">' + "".join(out) + "</div>")


def _lu(texte: str) -> str:
    """Une valeur de réglage telle que le programme la lit (`etude.valeur_lue`)."""
    return texte


def reglage(ident: str, nom: str, pts: list[tuple[str, str, float, float]]) -> str:
    """Trois lignes, le bas, le candidat, le haut : la valeur du réglage à gauche, son
    coût en point sur un axe commun."""
    values = [c for *_, c in pts]
    ticks = _ticks(min(0.0, *values), max(0.0, *values))
    x0, x1 = 150.0, W - 16.0

    def x(v: float) -> float:
        return x0 + (v - ticks[0]) / (ticks[-1] - ticks[0]) * (x1 - x0)

    lignes = _couper(nom, 46)
    corps = [_t(4, 14 + 15 * k, ligne, "sm-encre") for k, ligne in enumerate(lignes)]
    y = 26.0 + 15 * len(lignes)
    noms = {"bas": "le bas", "candidat": "le candidat", "haut": "le haut"}
    for point, lu, _, c in pts:
        cls = "sm-point-plein" if point == "candidat" else "sm-point"
        corps.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x1}" y2="{y:.1f}" '
                     f'class="sm-grille"/>')
        corps.append(_t(4, y + 4, f"{noms[point]} : {_lu(lu)}",
                        "sm-encre" if point == "candidat" else "sm-doux"))
        corps.append(f'<circle cx="{x(c):.1f}" cy="{y:.1f}" r="5" class="{cls}"/>')
        corps.append(_t(min(x(c) + 8, x1 - 30), y - 7, _fr(c / 1e9, 1), "sm-doux"))
        y += 24
    corps.append(f'<line x1="{x(0):.1f}" y1="{y - 84:.1f}" x2="{x(0):.1f}" y2="{y - 12:.1f}" '
                 f'class="sm-zero"/>')
    d = _dec(ticks, 1e-9)
    for t in ticks:
        corps.append(_t(x(t), y + 4, _fr(t / 1e9, d), "sm-doux", "middle"))
    corps.append(_t(x1, y + 20, "coût 2026, milliards d'euros", "sm-doux", "end"))
    desc = "; ".join(f"{noms[pt]} {_lu(lu)} : {_fr(c / 1e9, 2)} Md€" for pt, lu, _, c in pts)
    return _svg(ident, y + 28, nom, desc, corps)


def _couper(texte: str, largeur: int) -> list[str]:
    mots, lignes, cur = texte.split(), [], ""
    for m in mots:
        if cur and len(cur) + 1 + len(m) > largeur:
            lignes.append(cur)
            cur = m
        else:
            cur = f"{cur} {m}".strip()
    return [*lignes, cur][:3]


def quel_cout(study: etude.Etude, entry: dict[str, Any]) -> str:
    """Les coûts qu'un lecteur croise pour la même part, chacun nommé : sa vue, son année,
    sa couche (P3 du lecteur novice)."""
    lu = etude.lecture_seule(entry)
    year = entry["scenario"].year
    items = [(f"<strong>Le coût</strong>, celui du résumé : {year}, mécanique, la "
              f"population de 2024 au droit de {year} (vue figée)",
              _badge(_eur(lu["figee"]), "L2"))]
    if entry["kind"] == "mixte":
        sign = entry["sign"]
        items.append(("dont les ménages (leur revenu disponible)",
                      _badge(_eur(sign * float(entry["response"].reform_cost)), "L2")))
        items.append(("dont les entreprises",
                      _badge(_eur(sign * float(entry["firms"].reform_cost)), "L2")))
    items.append((f"le même coût sur la population vieillie jusqu'en {year} (vue "
                  f"vieillie), la première année du chemin vers la dette",
                  _badge(_eur(lu["vieillie"]), "L2")))
    deltas = getattr(entry["response"], "deltas", None) or {}
    gros = sorted(((k, float(v)) for k, v in dict(deltas).items()
                   if k not in AGREGATS and not k.endswith("_droit")
                   and abs(float(v)) >= 5e9),
                  key=lambda kv: -abs(kv[1]))[:2]
    for k, v in gros:
        sens = "en moins" if entry["sign"] * v < 0 else "en plus"
        items.append((f"un seul module, « {CHAMPS_LUS.get(k, k.replace('_', ' '))} », "
                      f"{sens} pour les ménages ; ce n'est pas le coût, les autres modules "
                      f"le compensent en partie",
                      _badge(_eur(abs(v)).replace("+", ""), "L2")))
    lis = "".join(f'<li><span>{a}</span><span class="sm-v">{b}</span></li>'
                  for a, b in items)
    return (f'<ul class="sm-couts">{lis}</ul><p class="sm-petit">Ailleurs sur le site, '
            f"d'autres coûts de la même part se lisent par la même règle : l'année pleine "
            f"(la mesure appliquée toute une année, {year + 1}), la valeur du candidat sur "
            f"un réglage (une mesure seule, vue vieillie), ce que la boucle lit la première "
            f"année (les prélèvements qu'elle sait lire). Chacun dit sa vue, son année et sa "
            f"couche ; « le » coût est le premier de cette liste.</p>")


def _chapeau(lines: list[str], n: etude.Nombres,
             text: Callable[[str, etude.Nombres], str]) -> str:
    """Les premières phrases de « Ce que dit cette étude » : le coût, qui y gagne, la
    dette, le verdict. Le paragraphe entier reste dans la provenance."""
    import re

    start = lines.index("## Ce que dit cette étude")
    para = next((ln for ln in lines[start + 1:] if ln.strip()), "")
    phrases = re.split(r"(?<=[.;]) (?=[A-ZÀ-Ý])", para)
    garde = []
    for ph in phrases:
        garde.append(ph)
        if "conclut" in ph or "verdict" in ph or len(garde) >= 5:
            break
    return f'<p class="chapeau">{text(" ".join(garde), n)}</p>'


def part_chiffree(study: etude.Etude) -> str:
    """La part du programme que le verdict couvre, en barre : chiffrées, refusées,
    vagues, sur les mesures relevées (Me6)."""
    if study.programme is None:
        return ""
    from impots import programmes as pg

    p = pg.charger(study.programme)
    total = len(p.mesures)
    ch = len(p.chiffrees())
    vagues = sum(1 for m in p.mesures if m.precision == "vague")
    autres = total - ch - vagues
    w = [ch / total * 100, autres / total * 100, vagues / total * 100]
    barre = ('<div class="sm-part" role="img" aria-label="'
             f'{ch} mesures chiffrées, {autres} refusées, {vagues} vagues, sur {total}">'
             f'<span class="sm-p-ch" style="width:{w[0]:.1f}%"></span>'
             f'<span class="sm-p-ref" style="width:{w[1]:.1f}%"></span>'
             f'<span class="sm-p-vag" style="width:{w[2]:.1f}%"></span></div>')
    return (f'<aside class="garde" role="note"><b>Ce verdict ne porte que sur {ch} mesure'
            f'{"s" if ch > 1 else ""} sur {total}.</b>{barre}<span class="legende">'
            f'<i class="sm-p-ch"></i> chiffrées ({ch}) <i class="sm-p-ref"></i> refusées '
            f'par l\'outil ({autres}) <i class="sm-p-vag"></i> sans montant ({vagues})'
            f"</span>Il ne dit pas ce que le programme entier fait à la dette : les "
            f"mesures refusées n'y sont pas, et elles peuvent la faire monter ou baisser."
            f"</aside>")


def mesures_etude(study: etude.Etude, entries: list[dict[str, Any]]) -> str:
    """Chaque mesure chiffrée : ce que dit le candidat, sur qui, combien, et sa page pas à
    pas ; puis les mesures refusées, repliées, chacune avec sa raison."""
    from impots import programmes as pg

    if study.programme is None:
        return ""
    p = pg.charger(study.programme)
    cartes = []
    for m, seule in mesures_de(study, entries):
        lu = etude.lecture_seule(seule)
        qui = "les ménages" if m.chiffrage.couche == "menages" else "les entreprises"
        cartes.append(
            f'<article class="sm-mcarte"><h3>{_m(m.libelle)}</h3>'
            f"<dl><dt>Le candidat</dt><dd>{_m(m.parametre)}</dd>"
            f"<dt>Sur qui</dt><dd>{qui}</dd><dt>Coût {seule['scenario'].year}</dt><dd>"
            f'{_badge(_eur(lu["figee"]), "L2")}</dd><dt>Dette {etude.LAST_YEAR}</dt><dd>'
            f'{_badge(etude._points(lu["dette"]), lu["etage"], True)}</dd></dl>'
            f'<a class="sm-suivre" href="{lien(p.slug, m.id)}">La suivre pas à pas →</a>'
            "</article>")
    refus = [m for m in p.mesures if m.chiffrage is None]
    lignes = "".join(
        f"<li><strong>{_m(m.libelle)}</strong> — "
        + (_e("vague : elle n'énonce ni taux ni montant") if m.refus is None
           or m.refus.porte == "vague" else _m(etude.porte_lue(m.refus.porte)))
        + "</li>" for m in refus)
    return ('<p class="sm-phrase">Le coût de chaque mesure seule ; leur somme n\'est pas '
            "le coût de la part, deux mesures se rencontrant dans le barème et dans la "
            "dette.</p>"
            f'<div class="sm-mcartes">{"".join(cartes)}</div>'
            + (f'<details class="detail"><summary>Les {len(refus)} mesures que l\'outil ne '
               f"chiffre pas, et pourquoi</summary><div class=\"detail-corps\">"
               f'<ul class="sm-refus">{lignes}</ul></div></details>' if refus else ""))


def page_etude(study: etude.Etude, entries: list[dict[str, Any]], lines: list[str],
               n: etude.Nombres, text: Callable[[str, etude.Nombres], str],
               body: Callable[[list[str], etude.Nombres], str]) -> str:
    """La page d'une étude : le résumé, puis le chemin, puis mesure par mesure ; tout ce
    que l'étude écrit, nombres compris, reste dans « Pour le relecteur », replié."""
    full = lire_courbes(body(lines, n), entries)
    cut = full.find("</h1>") + len("</h1>")
    out = [full[:cut], _chapeau(lines, n, text)]
    mesures = mesures_de(study, entries)
    presentes = {"en-resume", "pour-qui", "cout-dette", "dette-annees", "provenance"}
    if study.programme is not None:
        presentes |= {"quel-cout"}
    if mesures:
        presentes |= {"mesure-par-mesure"}
    plages = plages_etude(study, entries)
    if plages:
        presentes.add("plages")
    out.append('<nav class="pastilles" aria-label="Sur cette page"><ol>' + "".join(
        f'<li><a href="#{i}">{_e(t)}</a></li>' for i, t in SECTIONS if i in presentes)
        + "</ol></nav>")
    out.append(resume(study, entries, lines, n, text, body))
    if "quel-cout" in presentes:
        out.append(_section("quel-cout", quel_cout(study, entries[0])))
    plusieurs = len(entries) > 1
    for key, fn in (("cout-dette", cascade_etude), ("dette-annees", trajectoire_etude)):
        corps = "".join(
            (f"<h3>{text(study.texte_lu().label(entry), n)}</h3>" if plusieurs else "")
            + fn(entry, f"sm-{entry['name']}") for entry in entries)
        if key == "cout-dette":
            corps = ('<p class="sm-phrase">Le coût d\'une année est en euros ; la dette, '
                     "dix ans plus tard, en points de PIB. Le pont entre les deux, puis ce "
                     "que l'activité y change.</p>" + corps)
        out.append(_section(key, _provenance(corps)))
    if mesures:
        out.append(_section("mesure-par-mesure", mesures_etude(study, entries)))
    if plages:
        out.append(_section("plages", _provenance(plages)))
    out.append(_section("provenance", '<p class="sm-phrase">Tout ce que l\'étude écrit, '
                        "tableau par tableau, avec ses rapports, ses commits et ses "
                        "décisions : aucun nombre de la page n'est perdu.</p>"
                        '<details class="detail sm-tout"><summary>Le texte complet de '
                        "l'étude</summary><div class=\"detail-corps\">"
                        f"{full[cut:]}</div></details>"))
    return "\n".join(out)


COMPARER = "comparer-candidats.html"


def _bref_cellules(lines: list[str]) -> dict[str, str]:
    """La première ligne du tableau « En bref », par en-tête."""
    start = lines.index("## En bref")
    table = []
    for ln in lines[start + 1:]:
        if ln.startswith("## "):
            break
        if ln.startswith("|"):
            table.append(ln)
    if len(table) < 3:
        return {}
    return dict(zip(_cellules(table[0]), _cellules(table[2]), strict=False))


def comparer(etudes_: list[tuple[etude.Etude, list[dict[str, Any]], list[str], etude.Nombres]],
             text: Callable[[str, etude.Nombres], str]) -> str:
    """Les candidats côte à côte (P11 du lecteur novice) : ce que chacun chiffre, ce que
    cette part coûte et fait à la dette, et ce qui ne se compare pas."""
    from impots import programmes as pg

    rangs = []
    for study, entries, lines, n in etudes_:
        if study.programme is None:
            continue
        p = pg.charger(study.programme)
        lu = etude.lecture_seule(entries[0])
        rangs.append((p, study, lu, _bref_cellules(lines), n))
    rangs.sort(key=lambda r: -r[2]["dette"])
    rows = [(r[0].candidat, r[2]["dette"], etude._points(r[2]["dette"]),
             "sm-plus" if r[2]["dette"] < 0 else "sm-moins") for r in rangs]
    figure = _figure(
        barres("cmp-dette", rows, "La dette en 2035, part chiffrée de chaque programme",
               "points de PIB de 2035", 100.0),
        "l'écart de dette en 2035, en points de PIB, à θ½, vue vieillie, de la seule part "
        "chiffrée de chaque programme ; rouge : elle monte, bleu : elle baisse. Chaque "
        "barre porte sur une part différente : voir la colonne « chiffrées ».", "")
    lignes = []
    for p, study, lu, cells, n in rangs:
        total, ch = len(p.mesures), len(p.chiffrees())
        verdict = text(cells.get("verdict", "—"), n)
        lignes.append(
            f'<tr><th scope="row"><a href="{study.nom}.html">{_e(p.candidat)}</a></th>'
            f'<td><span class="sm-frac">{ch} sur {total}</span><span class="sm-part" '
            f'aria-hidden="true"><span class="sm-p-ch" style="width:{ch / total * 100:.1f}%">'
            f"</span></span></td><td>{_badge(_eur(lu['figee']), 'L2')}</td>"
            f"<td>{_badge(etude._points(lu['dette']), lu['etage'], True)}</td>"
            f"<td>{verdict}</td></tr>")
    table = ('<div class="defile"><table><thead><tr><th>candidat</th><th>mesures '
             "chiffrées</th><th>coût 2026</th><th>dette 2035, à θ½</th><th>verdict</th>"
             f"</tr></thead><tbody>{''.join(lignes)}</tbody></table></div>")
    garde = ('<aside class="garde" role="note"><b>Ce qui ne se compare pas.</b>'
             "<ul><li>Chaque ligne porte sur la seule part chiffrée d'un programme : "
             "quelques mesures pour l'un, davantage pour l'autre. Un programme peu chiffré "
             "n'est pas un programme peu coûteux.</li><li>L'effet sur l'activité n'est lu "
             "que pour les prélèvements que la boucle sait lire : deux mesures de même "
             "coût peuvent peser différemment sur la dette.</li><li>Les études n'ont pas "
             "toutes tourné sur le même code : chaque page dit le sien.</li></ul></aside>")
    return ("<h1>Comparer les candidats</h1>"
            '<p class="chapeau">Ce que chaque étude chiffre d\'un programme, ce que '
            "cette part coûte la première année et ce qu'elle fait à la dette en 2035. "
            "Ce qui se compare : le sens et l'ordre de grandeur, pour la part chiffrée. "
            "Ce qui ne se compare pas est dit juste dessous.</p>"
            + garde + figure + table
            + f'<p class="sm-petit">Le chemin d\'une mesure : <a href="{INDEX}">une mesure '
            "pas à pas</a>.</p>")


# Les composants de ces pages sont dans la feuille commune (D-468) :
# src/impots/site_textes/style.css, décrite dans docs/site/DESIGN.md.
