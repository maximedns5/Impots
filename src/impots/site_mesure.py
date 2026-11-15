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

from impots import etude

INDEX = "mesure.html"
CSS = "mesure.css"


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


def _source(fichier: str, champ: str, commit: str) -> str:
    return (f'<p class="source">Source : <code>{_e(fichier)}</code> · champ '
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
def barres(ident: str, rows: list[tuple[str, float, str]], titre: str, unite: str,
           echelle: float = 1.0) -> str:
    """Des barres horizontales autour de zéro : (libellé, valeur, texte affiché)."""
    values = [v for _, v, _ in rows] or [0.0]
    ticks = _ticks(min(0.0, *values), max(0.0, *values))
    x0, x1 = 14.0, W - 14.0

    def x(v: float) -> float:
        return x0 + (v - ticks[0]) / (ticks[-1] - ticks[0]) * (x1 - x0)

    corps, y = [], 8.0
    for label, v, texte in rows:
        # Le libellé au-dessus de sa barre : au téléphone, rien ne se chevauche.
        corps.append(_t(x0, y + 12, f"{label} : {texte}", "sm-encre"))
        y += 17
        a, b = sorted((x(0), x(v)))
        cls = "sm-plus" if v >= 0 else "sm-moins"
        corps.append(f'<rect x="{a:.1f}" y="{y:.1f}" width="{max(b - a, 1):.1f}" '
                     f'height="14" class="{cls}"/>')
        y += 22
    corps.append(f'<line x1="{x(0):.1f}" y1="8" x2="{x(0):.1f}" y2="{y:.1f}" class="sm-zero"/>')
    d = _dec(ticks, echelle)
    for t in ticks:
        corps.append(_t(x(t), y + 14, _fr(t * echelle, d), "sm-doux", "middle"))
    corps.append(_t(x1, y + 30, unite, "sm-doux", "end"))
    desc = "; ".join(f"{label} : {texte}" for label, _, texte in rows)
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
                 reperes: list[tuple[int, str]]) -> str:
    """Δ dette année par année, en points de PIB : une ligne par vue, et des repères
    verticaux là où la courbe change de pente pour une raison connue."""
    values = [v * 100 for _, vs, _ in series for v in vs]
    ticks = _ticks(min(0.0, *values), max(0.0, *values))
    top, h, x0, x1 = 30.0, 160.0, 46.0, W - 50.0

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
    corps.append(_t(x1, top + h + 32, "Δ dette, points de PIB", "sm-doux", "end"))
    desc = "; ".join(f"{name} : " + ", ".join(f"{yr} {_fr(v * 100, 2)}"
                                             for yr, v in zip(years, vs, strict=True))
                     for name, vs, _ in series)
    return _svg(ident, top + h + 40, "La dette, année par année", desc, corps)


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
           if k not in AGREGATS and abs(float(v)) >= 1e6]
    return sorted(out, key=lambda kv: -abs(kv[1]))[:8]


# --------------------------------------------------------------------------- #
# la page d'une mesure
# --------------------------------------------------------------------------- #
ETAPES = ("Le texte, traduit en paramètres", "Les ménages touchés", "L'effet mécanique",
          "Les comportements", "L'activité et le bouclage", "Les gagnants et les perdants",
          "Le coût, couche par couche")


def _etape(k: int, corps: str, phrase: str) -> str:
    return (f'<section class="sm-etape" id="etape-{k}"><h2><span class="sm-num">{k}</span>'
            f"{_e(ETAPES[k - 1])}</h2><p class=\"sm-phrase\">{phrase}</p>{corps}</section>")


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
    out.append(f"<h1>{_e(m.libelle)}</h1>")
    out.append(f'<p class="sm-chapeau">Une mesure du programme de {_e(programme.candidat)}'
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
        f'<blockquote class="sm-cite"><p>{_e(_guillemets(s.citation))}</p><footer>{_e(s.type)}, '
        f'{_e(s.date)} · <a href="{_e(s.url)}">la source</a></footer></blockquote>'
        for s in m.sources[:2])
    params = "".join(
        f"<li><code>{_e(champ)}</code> = {_e(etude.valeur_lue(champ, v))}</li>"
        for champ, v in _feuilles(ch.reforme))
    plages = "".join(
        f"<li><code>{_e(p.champ)}</code> : de {_e(etude.valeur_lue(p.champ, p.min))} à "
        f"{_e(etude.valeur_lue(p.champ, p.max))}</li>" for p in ch.plages)
    schema = (
        '<div class="sm-flux">'
        f'<div class="sm-boite"><span class="sm-tag">ce que dit le candidat</span>'
        f"<strong>{_e(m.parametre)}</strong>{citations}</div>"
        '<div class="sm-fleche" aria-hidden="true">→</div>'
        f'<div class="sm-boite"><span class="sm-tag">ce que le moteur reçoit</span>'
        f"<ul>{params}</ul>"
        + (f'<p class="sm-petit">Plage réglable : </p><ul>{plages}</ul>' if plages else "")
        + "</div>"
        '<div class="sm-fleche" aria-hidden="true">→</div>'
        f'<div class="sm-boite"><span class="sm-tag">la couche qu\'il touche</span>'
        f"<strong>{'les ménages' if ch.couche == 'menages' else 'les entreprises'}"
        f"</strong><p class=\"sm-petit\">dès {year}"
        + (f", les années {', '.join(map(str, path['annees']))}" if path.get("annees")
           else f", jusqu'en {etude.LAST_YEAR}") + "</p></div></div>")
    note = (f'<p class="sm-note"><strong>La traduction</strong> : {_e(ch.note)}</p>'
            if ch.note else "")
    out.append(_etape(1, schema + note + (
        f'<p class="source">Source : <code>programmes/{_e(programme.slug)}.json</code> · '
        f"mesure <code>{_e(m.id)}</code> · relevé du {_e(programme.releve)}</p>"),
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
    if study.programme is None or not entries or not entries[0].get("mesures"):
        return []
    from impots import programmes as pg

    p = pg.charger(study.programme)
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
           '<p class="sm-chapeau">Choisissez un candidat, puis une de ses mesures : sa page '
           "la suit de ce que dit le texte au coût qu'en publie l'étude, en sept étapes, "
           "chacune avec son schéma et sa source. Seules les mesures chiffrées seules, avec "
           "leurs deux rapports, y sont.</p>",
           '<ol class="sm-sommaire sm-apercu">' + "".join(f"<li>{_e(t)}</li>" for t in ETAPES)
           + "</ol>"]
    for p, study, mesures in listes:
        items = "".join(
            f'<li><a href="{lien(p.slug, m.id)}"><strong>{_e(m.libelle)}</strong>'
            f'<span>{_e(m.parametre)}</span></a>'
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
    # Pour qui : le graphique des déciles de la première ligne, avec sa légende.
    name = entries[0]["name"]
    for i, ln in enumerate(lines):
        if ln.startswith("![") and f"{name}-deciles" in ln:
            # The same figure as the detail's, its ids made the summary's own.
            figure = body(lines[i:i + 3], n).replace(f"{name}-deciles",
                                                     f"resume-{name}-deciles")
            out.append("<h3>Pour qui</h3>" + figure)
            break
    mesures = mesures_de(study, entries)
    if mesures:
        from impots import programmes as pg

        p = pg.charger(study.programme)
        items = "".join(
            f'<li><a href="{lien(p.slug, m.id)}"><strong>{_e(m.libelle)}</strong>'
            f'<span>pas à pas →</span></a><span class="sm-cout">'
            f'{_badge(_eur(etude.lecture_seule(s)["figee"]), "L2")}</span></li>'
            for m, s in mesures)
        out.append(f"<h3>Mesure par mesure</h3><p class=\"sm-petit\">Le coût de la première "
                   f"année, mécanique, de chaque mesure seule ; sa page la suit en sept "
                   f"étapes.</p><ul class=\"sm-mesures\">{items}</ul>")
    gdp = float((entries[0]["path"].get("start") or {}).get("gdp_eur") or 0)
    if gdp:
        out.append(f'<p class="sm-note"><strong>Pour lire les points de PIB</strong> : un point '
                   f"de PIB, c'est environ {_badge(f'{_fr(gdp / 100 / 1e9)} Md€', 'publié')} (le PIB de "
                   f"{entries[0]['path']['start']['year']}, <code>start.gdp_eur</code> du "
                   f"chemin annuel, divisé par cent).</p>")
    out.append('<p class="sm-note"><strong>Quel coût ?</strong> « La première année » est '
               "le coût mécanique de 2026, vue figée (la population de 2024 au droit de "
               "2026) : c'est celui de la page. Plus bas, la vue vieillie (la population "
               "vieillie jusqu'en 2026), le coût avec les comportements, les plages et les "
               "mesures seules en donnent d'autres : chacun dit sa vue, son année et sa "
               "couche.</p>")
    out.append('<p class="sm-petit"><a href="#le-detail">Le détail de l\'étude</a>, tel '
               "qu'elle l'écrit, suit, replié.</p></section>")
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


STYLE = """\
:root { --sm-plus: #1f6fb2; --sm-moins: #c2502d; --sm-neutre: #d9d5cc;
  --sm-carte: #f3f1ec; --sm-accent: #1f4e8c; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --sm-plus: #6aa8e0; --sm-moins: #e8845f; --sm-neutre: #45423c; --sm-carte: #26241f;
  --sm-accent: #8fb3e6; } }
:root[data-theme="dark"] { --sm-plus: #6aa8e0; --sm-moins: #e8845f; --sm-neutre: #45423c;
  --sm-carte: #26241f; --sm-accent: #8fb3e6; }
.sm-chapeau { font-size: 1.08rem; color: var(--doux); }
.sm-fil { font: .85rem system-ui, sans-serif; color: var(--doux); }
.sm-cartes { display: grid; grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr));
  gap: .6rem; margin: 1rem 0; }
.sm-carte { background: var(--sm-carte); border-radius: .5rem; padding: .7rem .8rem; }
.sm-carte > span:first-child { display: block; font: .8rem/1.3 system-ui, sans-serif;
  color: var(--doux); margin-bottom: .3rem; }
.sm-verdict { grid-column: 1 / -1; font: 600 1.15rem/1.4 system-ui, sans-serif; }
.sm-carte .nombre { font: 600 1.25rem/1.2 system-ui, sans-serif; }
.sm-sommaire { font: .92rem system-ui, sans-serif; columns: 2 14rem; padding-left: 1.4rem; }
.sm-etape { border-left: 3px solid var(--trait); padding: .2rem 0 1rem 1rem;
  margin: 2rem 0 0; }
.sm-etape h2 { display: flex; gap: .6rem; align-items: center; margin-top: 0; }
.sm-num { flex: none; width: 1.9rem; height: 1.9rem; border-radius: 50%; display: grid;
  place-items: center; background: var(--sm-accent); color: var(--fond); font-size: 1rem; }
.sm-phrase { color: var(--doux); }
.sm-gros { font: 600 1.15rem/1.35 system-ui, sans-serif; }
.sm-flux { display: grid; grid-template-columns: 1fr auto 1fr auto 1fr; gap: .5rem;
  align-items: stretch; }
.sm-boite { background: var(--sm-carte); border-radius: .5rem; padding: .7rem; }
.sm-boite ul { padding-left: 1.1rem; margin: .3rem 0; }
.sm-tag { display: block; font: .75rem system-ui, sans-serif; text-transform: uppercase;
  letter-spacing: .04em; color: var(--doux); margin-bottom: .3rem; }
.sm-fleche { align-self: center; font-size: 1.4rem; color: var(--doux); }
.sm-cite { margin: .5rem 0 0; font-size: .9rem; }
.sm-cite footer { font: .78rem system-ui, sans-serif; }
.sm-petit { font: .85rem/1.4 system-ui, sans-serif; color: var(--doux); }
.sm-note { font-size: .95rem; }
.sm-deux { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem; }
.sm-deux > div { background: var(--sm-carte); border-radius: .5rem; padding: .7rem; }
.sm-deux span { display: block; font: .82rem system-ui, sans-serif; color: var(--doux); }
p.source { font: .78rem/1.4 system-ui, sans-serif; color: var(--doux); margin: .4rem 0; }
.sm-fig { margin: 1rem 0; }
.sm-fig figcaption, .sm-lire { font: .85rem/1.45 system-ui, sans-serif; color: var(--doux);
  max-width: 36rem; }
svg.sm { display: block; width: 100%; max-width: 36rem; height: auto;
  font: 13px system-ui, sans-serif; }
.sm-encre { fill: var(--texte); paint-order: stroke; stroke: var(--fond);
  stroke-width: 3px; } .sm-doux { fill: var(--doux); font-size: 12px; }
.sm-sur { fill: #fff; font-weight: 600; }
.sm-plus { fill: var(--sm-plus); } .sm-moins { fill: var(--sm-moins); }
.sm-neutre { fill: var(--sm-neutre); }
.sm-l-plus { fill: var(--sm-plus); font-weight: 600; }
.sm-l-moins { fill: var(--sm-moins); font-weight: 600; }
.sm-zero { stroke: var(--texte); stroke-width: 1.2; }
.sm-grille { stroke: var(--trait); stroke-width: .8; }
.sm-repere { stroke: var(--doux); stroke-dasharray: 2 3; }
.sm-l1 { stroke: var(--sm-plus); stroke-width: 3; }
.sm-l2 { stroke: var(--sm-moins); stroke-width: 2; stroke-dasharray: 6 4; }
.sm-intervalle { stroke: var(--sm-plus); stroke-width: 3; stroke-linecap: round; }
.sm-point { fill: var(--fond); stroke: var(--sm-plus); stroke-width: 2.5; }
.sm-couches { list-style: none; padding: 0; }
.sm-couche { display: grid; grid-template-columns: 3rem 1fr; gap: .7rem;
  padding: .6rem 0; border-bottom: 1px solid var(--trait); }
.sm-niv { font: 600 .85rem system-ui, sans-serif; background: var(--sm-carte);
  border-radius: .3rem; text-align: center; padding: .3rem 0; align-self: start; }
.sm-mesures { list-style: none; padding: 0; }
.sm-mesures li { display: flex; justify-content: space-between; gap: .8rem;
  align-items: center; padding: .6rem .2rem; border-bottom: 1px solid var(--trait); }
.sm-mesures a { text-decoration: none; display: grid; }
.sm-mesures a span { font: .85rem system-ui, sans-serif; color: var(--doux); }
.sm-mesures a:hover strong, .sm-mesures a:focus strong { text-decoration: underline; }
.sm-cout { flex: none; }
.sm-resume { border: 1px solid var(--trait); border-radius: .6rem; padding: .2rem 1rem 1rem;
  margin: 1rem 0 2rem; }
.sm-ligne h3 { font-size: 1rem; margin-bottom: 0; }
.sm-retour { margin-top: 2rem; font-family: system-ui, sans-serif; }
@media (max-width: 640px) {
  .sm-flux { grid-template-columns: 1fr; }
  .sm-fleche { transform: rotate(90deg); justify-self: center; }
  .sm-deux { grid-template-columns: 1fr; }
  .sm-sommaire { columns: 1; } }
"""
