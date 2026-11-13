"""Les graphiques des études (but 22) : du SVG écrit par le code, depuis les seuls rapports.

Chaque page d'étude se lit d'abord en graphiques : la cascade d'un coût, de la première
année à la dette ; la trajectoire de 2026 à 2035 (le solde, la dette, le PIB, par vue et
par persistance, avec la boîte θ en bande) ; la part de chaque décile ; et, pour un
programme, la frise de ses mesures. Décision du propriétaire (but 22) : ni bibliothèque,
ni serveur, ni script. Un graphique est un fichier SVG, écrit à côté de sa page sous
`docs/etudes/graphiques/<étude>/`, et repris tel quel dans la page du site.

RIEN N'EST SAISI. Chaque nombre se lit dans un rapport de l'étude : la première année
(`premiere_annee_*.json`), le chemin annuel (`predictif_*.json`), les points de plage
(`plages/*.json`). La trajectoire année par année et sa bande θ sont le chemin du rapport
rejoué par `impots.predictif.rejouer`, la même arithmétique que la chaîne, sans passe ni
fichier de données ; le rejeu est refusé s'il ne redonne pas, au milliardième de point,
chaque Δb du rapport et chaque coin de sa boîte.

DÉTERMINISTE. Mêmes rapports, mêmes octets : aucune date, chaque coordonnée arrondie au
dixième. `impots etude verifier` et `impots site verifier` refusent un graphique qui ne
redonne pas ses rapports, comme le texte.

LISIBLE AU TÉLÉPHONE. Une viewBox de 360 de large, le texte à 13 au moins, des couleurs
sûres pour les daltoniens (le bleu, l'orange et le vert d'eau de la palette validée, le
bleu et le rouge en divergence), jamais la couleur seule : chaque série a aussi son trait
(plein, tirets, pointillés) et sa légende. Chaque graphique a un titre, des axes nommés
avec leur unité, une légende, et un `<title>`/`<desc>` qui dit ses nombres.
"""

from __future__ import annotations

import html
import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

#: Le module que la légende de chaque graphique nomme.
MODULE = "impots.graphiques"
REJEU = "impots.predictif.rejouer"
LARGEUR = 360
POLICE = 13
#: Le rejeu doit redonner le rapport à ceci près (en part de PIB).
TOLERANCE_REJEU = 1e-9
PERSISTANCES = {"lue": "lue", "eteint": "éteinte", "tenu": "tenue"}
VUES = {"vieillie": "vieillie", "figee": "figée"}
#: Une persistance, sa couleur et son trait ; la vue figée est en traits plus fins.
SERIES = {"lue": ("g-s1", "#2a78d6", ""), "eteint": ("g-s2", "#eb6834", "6 4"),
          "tenu": ("g-s3", "#1baf7a", "2 3")}

STYLE = """
.g-fond{fill:#fcfcfb}.g-encre{fill:#1d1d1b}.g-doux{fill:#52514e}
.g-axe{stroke:#8a877f}.g-grille{stroke:#e4e1da}.g-zero{stroke:#52514e}
.g-s1{stroke:#2a78d6}.g-s2{stroke:#eb6834}.g-s3{stroke:#1baf7a}.g-s4{stroke:#6250d6}
.g-f1{fill:#2a78d6}.g-f2{fill:#eb6834}.g-f3{fill:#1baf7a}.g-f4{fill:#6250d6}
.g-bande{fill:#2a78d6;fill-opacity:.16}.g-plus{fill:#2a78d6}.g-moins{fill:#e34948}
.g-total{fill:#52514e}.g-lien{stroke:#8a877f}.g-sur{fill:#ffffff}
@media (prefers-color-scheme: dark){
.g-fond{fill:#1a1a19}.g-encre{fill:#ece9e2}.g-doux{fill:#c3c2b7}
.g-axe{stroke:#8f8b80}.g-grille{stroke:#33322f}.g-zero{stroke:#c3c2b7}
.g-s1{stroke:#3987e5}.g-s2{stroke:#d95926}.g-s3{stroke:#199e70}.g-s4{stroke:#9085e9}
.g-f1{fill:#3987e5}.g-f2{fill:#d95926}.g-f3{fill:#199e70}.g-f4{fill:#9085e9}
.g-bande{fill:#3987e5;fill-opacity:.24}.g-plus{fill:#3987e5}.g-moins{fill:#e66767}
.g-total{fill:#c3c2b7}.g-lien{stroke:#8f8b80}}
text{font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
"""


class GraphiqueError(ValueError):
    """Le graphique ne redonnerait pas son rapport."""


# --------------------------------------------------------------------------- #
# les nombres, à la française
# --------------------------------------------------------------------------- #
def fr(value: float, decimales: int = 2, *, signe: bool = True) -> str:
    """Un nombre à la française : virgule décimale, espace fine insécable entre les
    milliers, le moins typographique."""
    text = f"{abs(value):,.{decimales}f}".replace(",", " ").replace(".", ",")
    if round(value, decimales) == 0:
        return text
    return ("−" if value < 0 else "+" if signe else "") + text


def points(value: float) -> str:
    """Une part de PIB en points : 0,0428 → « +4,28 pt »."""
    return f"{fr(value * 100)} pt"


def milliards(value: float) -> str:
    return f"{fr(value / 1e9)} Md€"


def euros(value: float) -> str:
    return f"{fr(value, 0)} €"


def _c(value: float) -> str:
    """Une coordonnée, arrondie au dixième : les mêmes nombres donnent les mêmes octets."""
    text = f"{value:.1f}"
    return "0" if text in ("0.0", "-0.0") else text.removesuffix(".0")


def _e(text: str) -> str:
    return html.escape(text, quote=True)


def _ticks(low: float, high: float, count: int = 4) -> list[float]:
    """Des graduations rondes qui couvrent [low, high], zéro compris quand il y est."""
    if high <= low:
        high, low = low + 1e-12, low - 1e-12
    raw = (high - low) / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    first = math.floor(low / step + 1e-9) * step
    out, k = [], 0
    while first + k * step <= high + step * 1e-9 or len(out) < 2:
        out.append(round(first + k * step, 12))
        k += 1
    if out[-1] < high:
        out.append(round(out[-1] + step, 12))
    return out


@dataclass
class Echelle:
    """Une échelle linéaire, du domaine aux pixels."""

    d0: float
    d1: float
    p0: float
    p1: float

    def __call__(self, value: float) -> float:
        if self.d1 == self.d0:
            return (self.p0 + self.p1) / 2
        return self.p0 + (value - self.d0) / (self.d1 - self.d0) * (self.p1 - self.p0)


# --------------------------------------------------------------------------- #
# un graphique
# --------------------------------------------------------------------------- #
@dataclass
class Graphique:
    """Un graphique : son nom de fichier, ce que la page en dit, son SVG, ses nombres."""

    fichier: str
    titre: str
    source: str
    svg: str
    #: Les nombres tracés, par nom : ce qu'un test tient contre le rapport.
    nombres: dict[str, Any] = field(default_factory=dict)

    def legende(self) -> str:
        """La ligne de la page sous le graphique : sa source et le module qui le trace."""
        return f"*Source du graphique : {self.source} ; tracé par `{MODULE}`.*"


def _svg(ident: str, hauteur: float, titre: str, desc: str, corps: list[str]) -> str:
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {LARGEUR} {_c(hauteur)}" '
        f'width="{LARGEUR}" height="{_c(hauteur)}" role="img" '
        f'aria-labelledby="{ident}-t {ident}-d" font-size="{POLICE}">',
        f'<title id="{ident}-t">{_e(titre)}</title>',
        f'<desc id="{ident}-d">{_e(desc)}</desc>',
        f"<style>{STYLE.strip()}</style>",
        f'<rect class="g-fond" fill="#fcfcfb" x="0" y="0" width="{LARGEUR}" '
        f'height="{_c(hauteur)}"/>',
        *corps, "</svg>", ""])


def _texte(x: float, y: float, text: str, *, ancre: str = "start", classe: str = "g-encre",
           taille: int = POLICE, gras: bool = False) -> str:
    fill = {"g-doux": "#52514e", "g-sur": "#ffffff"}.get(classe, "#1d1d1b")
    weight = ' font-weight="600"' if gras else ""
    size = "" if taille == POLICE else f' font-size="{taille}"'
    return (f'<text class="{classe}" fill="{fill}" x="{_c(x)}" y="{_c(y)}" '
            f'text-anchor="{ancre}"{size}{weight}>{_e(text)}</text>')


def _ligne(x1: float, y1: float, x2: float, y2: float, classe: str, couleur: str,
           epaisseur: float = 1, tirets: str = "") -> str:
    dash = f' stroke-dasharray="{tirets}"' if tirets else ""
    return (f'<line class="{classe}" stroke="{couleur}" stroke-width="{_c(epaisseur)}"'
            f'{dash} x1="{_c(x1)}" y1="{_c(y1)}" x2="{_c(x2)}" y2="{_c(y2)}"/>')


def _titre(corps: list[str], titre: str, sous_titre: str | None = None) -> float:
    """Le titre en haut, coupé en lignes de 40 signes au plus ; rend la hauteur prise."""
    y = 20.0
    for line in _couper(titre, 42):
        corps.append(_texte(12, y, line, gras=True, taille=15))
        y += 19
    if sous_titre:
        for line in _couper(sous_titre, 50):
            corps.append(_texte(12, y, line, classe="g-doux"))
            y += 17
    return y + 4


def _couper(text: str, width: int) -> list[str]:
    lines, current = [], ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    return [*lines, current] if current else lines


def _court(text: str, width: int) -> str:
    return text if len(text) <= width else text[:width - 1].rstrip() + "…"


# --------------------------------------------------------------------------- #
# 1. la cascade : du coût de la première année à la dette
# --------------------------------------------------------------------------- #
def cascade_nombres(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Les marches de la cascade, telles que la page les dit.

    La première année, en euros : le coût mécanique (ménages et entreprises quand la
    ligne a les deux), ce que les comportements y changent (la bande centrale moins la
    part mécanique des ménages, quand la bande existe), le coût après comportements. La
    dette de la dernière année, en part de PIB, à θ½, vue vieillie, persistance « lue » :
    le coût sans boucle, le PIB comme dénominateur, les recettes induites, Δb (D-349).
    None quand le rapport n'a pas la décomposition (une série d'avant D-349)."""
    path, sign = entry["path"], entry["sign"]
    decomposition = ((path.get("lectures") or {}).get("decomposition") or {}).get("vieillie")
    if decomposition is None:
        return None
    response = entry["response"]
    marches: list[tuple[str, float]] = []
    if entry["kind"] == "mixte":
        menages = sign * float(response.reform_cost)
        marches += [("ménages, mécanique", menages),
                    ("entreprises, mécan.", sign * float(entry["firms"].reform_cost))]
    elif entry["kind"] == "entreprises":
        menages = None
        marches.append(("entreprises, mécan.", entry["cost"]))
    else:
        menages = entry["cost"]
        marches.append(("coût mécanique", menages))
    behavioural = getattr(response, "behavioural", None) if menages is not None else None
    if behavioural is not None and behavioural.band is not None:
        central = -behavioural.band.p50 if sign == 1 else behavioural.band.p50
        marches.append(("comportements", float(central) - menages))
    cout_final = sum(v for _, v in marches)
    dette = [("le coût, sans boucle", sign * decomposition["cout"]),
             ("le PIB, dénominateur", sign * decomposition["denominateur"]),
             ("les recettes induites", sign * decomposition["retroaction"])]
    total = sign * decomposition["total"]
    if abs(sum(v for _, v in dette) - total) > TOLERANCE_REJEU:
        raise GraphiqueError(f"{entry['name']} : les marches de la dette ne somment pas à "
                             f"Δb ({sum(v for _, v in dette):+.9f} pour {total:+.9f}).")
    return {"cout": marches, "cout_total": cout_final, "dette": dette, "dette_total": total,
            "annee": path["years"][-1]["year"], "premiere": path["years"][0]["year"]}


def _cascade_panneau(corps: list[str], y: float, titre: str, marches: list[tuple[str, float]],
                     total: tuple[str, float], format_: Any, unite: str) -> float:
    """Une cascade horizontale : chaque marche part où la précédente s'arrête ; la
    dernière barre, le total, part de zéro."""
    corps.append(_texte(12, y + 14, titre, gras=True))
    y += 24
    cumul, bornes = 0.0, [0.0]
    for _, value in marches:
        cumul += value
        bornes.append(cumul)
    bornes.append(total[1])
    ticks = _ticks(min(bornes), max(bornes))
    x = Echelle(ticks[0], ticks[-1], 156, LARGEUR - 18)
    rang, haut = 30, 18
    hauteur = rang * (len(marches) + 1)
    for t in ticks:
        corps.append(_ligne(x(t), y, x(t), y + hauteur, "g-grille", "#e4e1da"))
    corps.append(_ligne(x(0), y - 2, x(0), y + hauteur, "g-zero", "#52514e", 1.2))
    cumul = 0.0
    rows = [*((label, value, cumul_) for (label, value), cumul_ in
              zip(marches, itertools.accumulate([0.0] + [v for _, v in marches]),
                  strict=False))]
    for k, (label, value, depart) in enumerate([*rows, (total[0], total[1], 0.0)]):
        top = y + k * rang + (rang - haut) / 2
        a, b = x(depart), x(depart + value)
        last = k == len(rows)
        classe = "g-total" if last else ("g-plus" if value >= 0 else "g-moins")
        couleur = "#52514e" if last else ("#2a78d6" if value >= 0 else "#e34948")
        corps.append(f'<rect class="{classe}" fill="{couleur}" x="{_c(min(a, b))}" '
                     f'y="{_c(top)}" width="{_c(max(abs(b - a), 1.5))}" height="{haut}" '
                     f'rx="2"><title>{_e(label)} : {_e(format_(value))}</title></rect>')
        if not last and k + 1 <= len(rows):
            nxt = depart + value
            corps.append(_ligne(x(nxt), top + haut, x(nxt), top + rang, "g-lien", "#8a877f",
                                1, "2 2"))
        corps.append(_texte(10, top + 13, _court(label, 22), gras=last))
        valeur = format_(value)
        right, left, size = max(a, b), min(a, b), 7.0 * len(valeur)
        if right + 6 + size <= LARGEUR - 4:
            corps.append(_texte(right + 4, top + 13, valeur, classe="g-doux", taille=12))
        elif right - left >= size + 8:
            corps.append(_texte(right - 4, top + 13, valeur, ancre="end", classe="g-sur",
                                taille=12, gras=True))
        elif left - 6 - size >= 156:
            corps.append(_texte(left - 4, top + 13, valeur, ancre="end", classe="g-doux",
                                taille=12))
        else:
            corps.append(_texte(LARGEUR - 4, top + 13, valeur, ancre="end",
                                classe="g-doux", taille=12))
    y += hauteur + 4
    corps.append(_ligne(x(ticks[0]), y, x(ticks[-1]), y, "g-axe", "#8a877f"))
    pas = ticks[1] - ticks[0]
    echelle = 1e9 if format_ is milliards else 100.0
    decimales = 0 if pas * (1 / 1e9 if format_ is milliards else 100) >= 1 else 1
    for t in ticks[:: 2 if len(ticks) > 5 else 1]:
        texte = fr(t / echelle if format_ is milliards else t * echelle, decimales)
        corps.append(_texte(x(t), y + 15, texte.replace("+", ""), ancre="middle",
                            classe="g-doux", taille=12))
    corps.append(_texte(LARGEUR - 10, y + 31, unite, ancre="end", classe="g-doux", taille=12))
    return y + 40


def cascade(entry: dict[str, Any], *, ident: str, source: str) -> Graphique | None:
    nombres = cascade_nombres(entry)
    if nombres is None:
        return None
    titre = f"Du coût de {nombres['premiere']} à la dette de {nombres['annee']}"
    corps: list[str] = []
    y = _titre(corps, titre, "Chaque barre part où la précédente s'arrête ; la barre grise "
                             "est le total.")
    y = _cascade_panneau(corps, y, f"Le coût de {nombres['premiere']}", nombres["cout"],
                         (f"total {nombres['premiere']}", nombres["cout_total"]),
                         milliards, f"milliards d'euros de {nombres['premiere']}")
    y = _cascade_panneau(corps, y, f"La dette en {nombres['annee']}, à θ½, vue vieillie",
                         nombres["dette"], (f"Δ dette {nombres['annee']}",
                                            nombres["dette_total"]),
                         points, f"points de PIB de {nombres['annee']}")
    desc = (f"Le coût de {nombres['premiere']} : "
            + " ; ".join(f"{label} {milliards(v)}" for label, v in nombres["cout"])
            + f" ; total {milliards(nombres['cout_total'])}. La dette en "
            f"{nombres['annee']}, à θ½, vue vieillie, persistance lue : "
            + " ; ".join(f"{label} {points(v)}" for label, v in nombres["dette"])
            + f" ; Δ dette {points(nombres['dette_total'])}.")
    return Graphique(f"{ident}.svg", titre, source, _svg(ident, y, titre, desc, corps),
                     nombres)


# --------------------------------------------------------------------------- #
# 2. la trajectoire : le solde, la dette et le PIB, de 2026 à 2035
# --------------------------------------------------------------------------- #
INDICATEURS = (("solde", "Le solde public", "points de PIB, + l'améliore"),
               ("dette", "La dette (Δb)", "points de PIB"),
               ("pib", "Le PIB", "écart au PIB de référence, en %"))


def trajectoire_nombres(entry: dict[str, Any],
                        annonce: Sequence[float] | None = None) -> dict[str, Any]:
    """Année par année, par vue et par persistance : le solde (primaire et ce que la
    boucle en rend), la dette (Δb) et l'écart de PIB, au θ du rapport ; et la bande θ, du
    plus bas au plus haut coin de la boîte chaque année, vue vieillie, persistance
    « lue ». Le rejeu est refusé s'il ne redonne pas chaque Δb du rapport et chaque coin
    de sa boîte. En miroir, la mesure : chaque nombre changé de signe."""
    from impots.predictif import rejouer

    path, sign = entry["path"], entry["sign"]
    theta = dict(path["theta"])
    rows = list(rejouer._rejeu(path)["box_rows"])
    keys = {"vieillie": "delta_aged", "figee": "delta_frozen"}
    years = [int(r["year"]) for r in path["years"]]
    series: dict[tuple[str, str], dict[str, list[float]]] = {}
    box = {p["persistence"]: p["every_year"]
           for p in (path.get("theta_box") or {}).get("paths", [])}
    for drawn in path.get("side_by_side") or []:
        persistence = drawn["persistence"]
        for view, key in keys.items():
            if key not in drawn["years"][0]:
                continue
            c = rejouer.at_theta(path, theta, view=view, persistence=persistence)
            for k, row in enumerate(drawn["years"]):
                if abs(float(c.delta[k]) - row[key]) > TOLERANCE_REJEU:
                    raise GraphiqueError(f"{entry['name']} : le rejeu ne redonne pas Δb "
                                         f"{row['year']} du rapport (vue {view}, "
                                         f"persistance {persistence}).")
            series[(persistence, view)] = {
                "dette": [sign * float(v) for v in c.delta],
                "solde": [sign * float(p + f) for p, f in zip(c.primary, c.feedback,
                                                              strict=True)],
                "pib": [sign * float(g) for g in c.gdp_gap]}
    if ("lue", "vieillie") not in series:
        raise GraphiqueError(f"{entry['name']} : le chemin ne trace pas la persistance "
                             f"« lue » en vue vieillie.")
    coins = []
    for combo in itertools.product((0.0, 1.0), repeat=len(rows)):
        corner = {**theta, **dict(zip(rows, combo, strict=True))}
        coins.append(rejouer.at_theta(path, corner, view="vieillie", persistence="lue"))
    said = [v for _, v in box["lue"]["vieillie"]["corners"]] if "lue" in box else []
    for got, want in zip((c.delta[-1] for c in coins), said, strict=True):
        if abs(float(got) - want) > TOLERANCE_REJEU:
            raise GraphiqueError(f"{entry['name']} : le rejeu ne redonne pas un coin de la "
                                 f"boîte du rapport ({float(got):+.9f} pour {want:+.9f}).")
    bande = {}
    for name in ("solde", "dette", "pib"):
        per = []
        for c in coins:
            values = {"dette": c.delta, "pib": c.gdp_gap,
                      "solde": [p + f for p, f in zip(c.primary, c.feedback, strict=True)]}
            per.append([sign * float(v) for v in values[name]])
        bande[name] = [(min(col), max(col)) for col in zip(*per, strict=True)]
    out = {"annees": years, "series": series, "bande": bande, "coins": len(coins),
           "annonce": None}
    if annonce is not None:
        if len(annonce) != len(years):
            raise GraphiqueError(f"{entry['name']} : la dette annoncée n'a pas une valeur "
                                 f"par année du chemin.")
        out["annonce"] = [float(v) for v in annonce]
    return out


def trajectoire(entry: dict[str, Any], *, ident: str, source: str,
                annonce: Sequence[float] | None = None) -> Graphique:
    nombres = trajectoire_nombres(entry, annonce)
    years = nombres["annees"]
    first, last = years[0], years[-1]
    titre = f"Le solde, la dette et le PIB, de {first} à {last}"
    corps: list[str] = []
    y = _titre(corps, titre, "À θ½ ; la bande est la boîte θ, vue vieillie, persistance "
                             "« lue ». Trait épais : vue vieillie ; fin : vue figée.")
    # La légende, une fois, en haut.
    legende = [(PERSISTANCES[p], *SERIES[p]) for p in PERSISTANCES
               if (p, "vieillie") in nombres["series"]]
    x0 = 12.0
    for label, classe, couleur, tirets in legende:
        corps.append(_ligne(x0, y + 6, x0 + 22, y + 6, classe, couleur, 3, tirets))
        corps.append(_texte(x0 + 26, y + 10, f"persistance {label}"))
        x0 += 34 + 7.0 * len(f"persistance {label}")
        if x0 > LARGEUR - 100:
            x0, y = 12.0, y + 18
    y += 22
    corps.append(f'<rect class="g-bande" fill="#2a78d6" fill-opacity=".16" x="12" y="{_c(y)}"'
                 ' width="22" height="10"/>')
    corps.append(_texte(38, y + 10, "boîte θ, du plus bas au plus haut coin"))
    y += 18
    if nombres["annonce"] is not None:
        corps.append(_ligne(12, y + 6, 34, y + 6, "g-s4", "#6250d6", 3, "8 3 2 3"))
        corps.append(_texte(38, y + 10, "si les économies annoncées sont tenues"))
        y += 18
    y += 6
    x = Echelle(first, last, 52, LARGEUR - 14)
    for name, label, unite in INDICATEURS:
        lignes = {k: v[name] for k, v in nombres["series"].items()}
        valeurs = [v * (100 if name != "pib" else 100) for s in lignes.values() for v in s]
        valeurs += [v * 100 for lo_hi in nombres["bande"][name] for v in lo_hi]
        if name == "dette" and nombres["annonce"] is not None:
            valeurs += [v * 100 for v in nombres["annonce"]]
        ticks = _ticks(min([0.0, *valeurs]), max([0.0, *valeurs]))
        corps.append(_texte(12, y + 14, label, gras=True))
        corps.append(_texte(LARGEUR - 12, y + 14, unite, ancre="end", classe="g-doux",
                            taille=12))
        top, height = y + 24, 112
        s = Echelle(ticks[0], ticks[-1], top + height, top)
        for t in ticks:
            corps.append(_ligne(52, s(t), LARGEUR - 14, s(t), "g-grille", "#e4e1da"))
            corps.append(_texte(46, s(t) + 4, fr(t, 2 if abs(ticks[1] - ticks[0]) < 0.1
                                                  else 1).replace("+", ""),
                                ancre="end", classe="g-doux", taille=12))
        corps.append(_ligne(52, s(0), LARGEUR - 14, s(0), "g-zero", "#52514e", 1.2))
        bande = nombres["bande"][name]
        haut_ = " ".join(f"{_c(x(a))},{_c(s(hi * 100))}" for a, (_, hi)
                         in zip(years, bande, strict=True))
        bas_ = " ".join(f"{_c(x(a))},{_c(s(lo * 100))}" for a, (lo, _)
                        in reversed(list(zip(years, bande, strict=True))))
        corps.append(f'<polygon class="g-bande" fill="#2a78d6" fill-opacity=".16" '
                     f'points="{haut_} {bas_}"/>')
        for (persistence, view), serie in sorted(
                lignes.items(), key=lambda kv: (kv[0][1] == "vieillie", kv[0][0] == "lue")):
            classe, couleur, tirets = SERIES[persistence]
            pts = " ".join(f"{_c(x(a))},{_c(s(v * 100))}" for a, v in
                           zip(years, serie, strict=True))
            width = 2.5 if view == "vieillie" else 1.2
            dash = f' stroke-dasharray="{tirets}"' if tirets else ""
            corps.append(f'<polyline class="{classe}" stroke="{couleur}" fill="none" '
                         f'stroke-width="{width}"{dash} stroke-linejoin="round" '
                         f'points="{pts}"><title>{_e(label)}, vue {VUES[view]}, '
                         f'persistance {PERSISTANCES[persistence]}, {last} : '
                         f'{_e(_valeur(name, serie[-1]))}</title></polyline>')
        if name == "dette" and nombres["annonce"] is not None:
            pts = " ".join(f"{_c(x(a))},{_c(s(v * 100))}" for a, v in
                           zip(years, nombres["annonce"], strict=True))
            corps.append(f'<polyline class="g-s4" stroke="#6250d6" fill="none" '
                         f'stroke-width="2.5" stroke-dasharray="8 3 2 3" points="{pts}">'
                         f"<title>Si les économies annoncées sont tenues, {last} : "
                         f"{_e(points(nombres['annonce'][-1]))}</title></polyline>")
        tete = lignes[("lue", "vieillie")][-1]
        corps.append(f'<circle class="g-f1" fill="#2a78d6" cx="{_c(x(last))}" '
                     f'cy="{_c(s(tete * 100))}" r="4"/>')
        corps.append(_texte(x(last) - 6, (s(tete * 100) - 8) if tete >= 0 or s(tete * 100)
                            > top + height - 12 else s(tete * 100) + 18,
                            _valeur(name, tete), ancre="end", gras=True, taille=12))
        y = top + height
        corps.append(_ligne(52, y, LARGEUR - 14, y, "g-axe", "#8a877f"))
        for a in years:
            if (a - first) % 3 == 0 or a == last:
                corps.append(_texte(x(a), y + 18, str(a), ancre="middle", classe="g-doux",
                                    taille=12))
        y += 34
    corps.append(_texte(LARGEUR - 12, y - 4, "année", ancre="end", classe="g-doux",
                        taille=12))
    y += 4
    tete = nombres["series"][("lue", "vieillie")]
    desc = (f"De {first} à {last}, à θ½, vue vieillie, persistance lue. "
            + " ".join(f"{label} : {_valeur(name, tete[name][0])} en {first}, "
                       f"{_valeur(name, tete[name][-1])} en {last}, la boîte θ de "
                       f"{_valeur(name, nombres['bande'][name][-1][0])} à "
                       f"{_valeur(name, nombres['bande'][name][-1][1])} en {last}."
                       for name, label, _ in INDICATEURS)
            + " Δ dette en " + str(last) + ", par persistance et vue : "
            + " ; ".join(f"{PERSISTANCES[p]}, {VUES[v]} {points(serie['dette'][-1])}"
                         for (p, v), serie in nombres["series"].items())
            + ("." if nombres["annonce"] is None else
               f". Si les économies annoncées sont tenues : "
               f"{points(nombres['annonce'][-1])} en {last}."))
    return Graphique(f"{ident}.svg", titre, source, _svg(ident, y, titre, desc, corps),
                     nombres)


def _valeur(name: str, value: float) -> str:
    return points(value) if name != "pib" else f"{fr(value * 100)} %"


# --------------------------------------------------------------------------- #
# 3. la part de chaque décile
# --------------------------------------------------------------------------- #
def deciles_nombres(entry: dict[str, Any]) -> list[tuple[int, float]] | None:
    """(décile, gain moyen par ménage, en euros par an) de la première année, la mesure
    lue : en miroir, chaque delta changé de signe, comme la table de la page."""
    rows = getattr(entry["response"], "deciles", None) if entry["kind"] != "entreprises" \
        else None
    if not rows:
        return None
    return [(int(r.decile), entry["sign"] * float(r.mean_delta)) for r in rows]


def deciles(entry: dict[str, Any], *, ident: str, source: str) -> Graphique | None:
    nombres = deciles_nombres(entry)
    if nombres is None:
        return None
    year = entry["scenario"].year
    titre = f"Ce que chaque décile y gagne ou y perd en {year}"
    corps: list[str] = []
    y = _titre(corps, titre, "Le revenu disponible moyen par ménage, avec la mesure moins "
                             "sans elle ; les déciles du niveau de vie.")
    corps.append(f'<rect class="g-plus" fill="#2a78d6" x="12" y="{_c(y)}" width="14" '
                 'height="12" rx="2"/>')
    corps.append(_texte(30, y + 11, "gain"))
    corps.append(f'<rect class="g-moins" fill="#e34948" x="80" y="{_c(y)}" width="14" '
                 'height="12" rx="2"/>')
    corps.append(_texte(98, y + 11, "perte"))
    y += 24
    values = [v for _, v in nombres]
    ticks = _ticks(min(0.0, *values), max(0.0, *values))
    x = Echelle(ticks[0], ticks[-1], 46, LARGEUR - 16)
    rang, haut = 24, 14
    hauteur = rang * len(nombres)
    for t in ticks:
        corps.append(_ligne(x(t), y, x(t), y + hauteur, "g-grille", "#e4e1da"))
    for k, (decile, value) in enumerate(nombres):
        top = y + k * rang + (rang - haut) / 2
        a, b = x(0), x(value)
        classe, couleur = ("g-plus", "#2a78d6") if value >= 0 else ("g-moins", "#e34948")
        corps.append(f'<rect class="{classe}" fill="{couleur}" x="{_c(min(a, b))}" '
                     f'y="{_c(top)}" width="{_c(max(abs(b - a), 1))}" height="{haut}" '
                     f'rx="2"><title>D{decile} : {_e(euros(value))} par ménage</title></rect>')
        corps.append(_texte(40, top + 12, f"D{decile}", ancre="end", classe="g-doux",
                            taille=12))
        label = euros(value)
        room = (LARGEUR - 4 - max(a, b)) if value >= 0 else (min(a, b) - 46)
        if room >= 7.2 * len(label) + 6:
            corps.append(_texte(max(a, b) + 4 if value >= 0 else min(a, b) - 4, top + 12,
                                label, ancre="start" if value >= 0 else "end", taille=12))
        else:
            corps.append(_texte(max(a, b) - 4 if value >= 0 else min(a, b) + 4, top + 12,
                                label, ancre="end" if value >= 0 else "start", taille=12,
                                classe="g-encre"))
    corps.append(_ligne(x(0), y - 2, x(0), y + hauteur, "g-zero", "#52514e", 1.2))
    y += hauteur + 4
    corps.append(_ligne(x(ticks[0]), y, x(ticks[-1]), y, "g-axe", "#8a877f"))
    for t in ticks:
        corps.append(_texte(x(t), y + 15, fr(t, 0).replace("+", ""), ancre="middle",
                            classe="g-doux", taille=12))
    corps.append(_texte(LARGEUR - 12, y + 31, f"euros par ménage et par an, {year}",
                        ancre="end", classe="g-doux", taille=12))
    y += 52
    corps.append(_texte(12, y - 4, "D1 : le dixième le plus modeste ; D10 : le plus aisé.",
                        classe="g-doux", taille=12))
    y += 6
    desc = (f"Le gain moyen par ménage en {year}, par décile de niveau de vie : "
            + " ; ".join(f"D{d} {euros(v)}" for d, v in nombres) + ".")
    return Graphique(f"{ident}.svg", titre, source, _svg(ident, y, titre, desc, corps),
                     {"deciles": nombres})


# --------------------------------------------------------------------------- #
# 4. la frise des mesures d'un programme
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Plage:
    champ: str
    #: (point, la valeur lue, le coût mécanique de la première année, en euros)
    points: tuple[tuple[str, str, float], ...]


@dataclass(frozen=True)
class Mesure:
    libelle: str
    annees: tuple[int, ...]
    plages: tuple[Plage, ...]


def frise(mesures: Sequence[Mesure], *, debut: int, fin: int, ident: str,
          source: str) -> Graphique | None:
    """Une ligne par mesure chiffrée : les années où elle s'applique, de l'année du
    scénario à la fin du chemin, ou ses seules `annees` ; et, sous elle, chaque plage, ses
    trois points (bas, candidat, haut) avec leur coût de la première année."""
    if not mesures:
        return None
    titre = "Les mesures chiffrées dans le temps, et leurs plages"
    corps: list[str] = []
    y = _titre(corps, titre, f"La barre : les années où la mesure s'applique, de {debut} "
                             f"à {fin}. Dessous : le coût de {debut} de chaque point de "
                             f"plage.")
    corps.append(f'<circle class="g-f2" fill="#eb6834" cx="18" cy="{_c(y + 6)}" r="4"/>')
    corps.append(_texte(26, y + 10, "bas, haut"))
    corps.append(f'<rect class="g-f1" fill="#2a78d6" x="92" y="{_c(y + 1)}" width="10" '
                 'height="10" transform="rotate(0)"/>')
    corps.append(_texte(106, y + 10, "valeur du candidat"))
    y += 24
    x = Echelle(debut - 0.5, fin + 0.5, 14, LARGEUR - 14)
    for a in range(debut, fin + 1):
        if (a - debut) % 3 == 0 or a == fin:
            corps.append(_texte(x(a), y + 10, str(a), ancre="middle", classe="g-doux",
                                taille=12))
    y += 18
    nombres = []
    for mesure in mesures:
        y += 4
        lignes = _couper(mesure.libelle, 50)
        if len(lignes) > 2:
            lignes = [lignes[0], _court(lignes[1] + " " + lignes[2], 50)]
        for line in lignes:
            corps.append(_texte(12, y + 12, line, gras=True))
            y += 16
        annees = mesure.annees or tuple(range(debut, fin + 1))
        for a in range(debut, fin + 1):
            on = a in annees
            corps.append(f'<rect class="{"g-f1" if on else "g-grille"}" '
                         f'fill="{"#2a78d6" if on else "#e4e1da"}" x="{_c(x(a - 0.46))}" '
                         f'y="{_c(y + 2)}" width="{_c(x(a + 0.46) - x(a - 0.46))}" '
                         f'height="10" rx="2"><title>{a} : '
                         f'{"s" if on else "ne s"}\'applique{"" if on else " pas"}'
                         f'</title></rect>')
        y += 18
        for plage in mesure.plages:
            couts = [c for _, _, c in plage.points]
            lo, hi = min(couts), max(couts)
            pad = (hi - lo) * 0.08 or max(abs(hi), 1e8) * 0.1
            s = Echelle(lo - pad, hi + pad, 60, LARGEUR - 60)
            corps.append(_texte(12, y + 12, _court(f"plage « {plage.champ} »", 48),
                                classe="g-doux", taille=12))
            y += 16
            corps.append(_ligne(s(lo), y + 8, s(hi), y + 8, "g-axe", "#8a877f", 2))
            for k, (point, valeur, cout) in enumerate(plage.points):
                if point == "candidat":
                    corps.append(f'<rect class="g-f1" fill="#2a78d6" x="{_c(s(cout) - 5)}" '
                                 f'y="{_c(y + 3)}" width="10" height="10"><title>candidat '
                                 f'({_e(valeur)}) : {_e(milliards(cout))}</title></rect>')
                else:
                    corps.append(f'<circle class="g-f2" fill="#eb6834" cx="{_c(s(cout))}" '
                                 f'cy="{_c(y + 8)}" r="5"><title>{point} ({_e(valeur)}) : '
                                 f'{_e(milliards(cout))}</title></circle>')
                corps.append(_texte(s(cout), y + 28 + 14 * (k % 2), milliards(cout),
                                    ancre="middle", taille=12,
                                    classe="g-encre" if point == "candidat" else "g-doux"))
            nombres.append((mesure.libelle, plage.champ, plage.points))
            y += 50
    corps.append(_texte(LARGEUR - 12, y + 4, f"coût de {debut}, milliards d'euros",
                        ancre="end", classe="g-doux", taille=12))
    y += 14
    desc = "Les mesures chiffrées : " + " ; ".join(
        f"{m.libelle}, de {min(m.annees or (debut,))} à {max(m.annees or (fin,))}"
        + "".join(f", plage {p.champ} : " + ", ".join(
            f"{point} {valeur} {milliards(cout)}" for point, valeur, cout in p.points)
            for p in m.plages) for m in mesures) + "."
    return Graphique(f"{ident}.svg", titre, source, _svg(ident, y, titre, desc, corps),
                     {"mesures": nombres})
