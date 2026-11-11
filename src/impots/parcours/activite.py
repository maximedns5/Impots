"""Page 5 du parcours : l'activité.

Ce que la croissance rend à la dette tient à un seul nombre par instrument et par horizon,
lu dans une table de Mésange : la page montre la table telle que la boucle la lit (dans
les rapports commités des études, `rejeu.macro`), l'écart-type des méta-analyses d'IMK et
ce qu'il est, la part rendue à dix ans, la linéarité dans la taille du choc et les
instruments que la boucle ne lit pas. Le curseur rejoue la chaîne d'un rapport
(`rejouer.chemin`) dans le navigateur, par `js/activite.js` : θ du multiplicateur, les
trois persistances (D-336, D-337), la variante salariale (D-349). Rien n'est chiffré de
neuf ; les nombres sont ceux des rapports, ou leur rejeu par la fonction pure du moteur.
"""

from __future__ import annotations

import html
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from impots import etude
from impots.macro import fan, mesange, shocks
from impots.parcours import ROOT, Page, ParcoursError, fichier, lien, source
from impots.predictif import rejouer, retroaction

JS = Path(__file__).resolve().parent / "js"
ETUDES = ROOT / "reports" / "etudes"
MANIFEST = ROOT / "data" / "raw" / "MANIFEST.json"
DISPERSION = "src/impots/macro/parameters/dispersion.yaml"
MULTIPLIERS = "src/impots/macro/parameters/multipliers.yaml"
WP117 = "imk_wp117_2013_gechert_meta_regression.pdf"
WP139 = "imk_wp139_2014_gechert_rannenberg_regime_dependent.pdf"
VUE = "vieillie"
HORIZONS = ("1", "2", "3", "5", "10")
esc = html.escape


# --------------------------------------------------------------------------- #
# les nombres, en français
# --------------------------------------------------------------------------- #
def fr(x: float, d: int = 2, signe: bool = False) -> str:
    """Un nombre à la française : virgule, espace fine insécable, signe moins typographique."""
    texte = f"{abs(x):,.{d}f}".replace(",", "\u202f").replace(".", ",")
    if round(abs(x), d) == 0:
        return texte
    if x < 0:
        return "−" + texte
    return ("+" + texte) if signe else texte


def md(x: float) -> str:
    return fr(x / 1e9, 2, signe=True) + "\u00a0Md€"


def pt(x: float) -> str:
    return fr(x * 100, 2, signe=True) + "\u00a0pt"


# --------------------------------------------------------------------------- #
# les rapports des études
# --------------------------------------------------------------------------- #
def _nom(data: dict[str, Any]) -> str:
    """Le nom d'une étude comme un lecteur le dit : le candidat, ou l'article et sa mesure."""
    tete = data["source"].split(" — ")[0]
    if tete.startswith("PLF"):
        return f"{tete.split(' (')[0]}, {tete.split('), ')[-1]} ({data['scenario'].rsplit('_', 1)[-1].upper()})"
    return tete.split(" (")[0]


@lru_cache(maxsize=1)
def rapports() -> tuple[dict[str, Any], ...]:
    """Les rapports annuels des études publiées (`reports/etudes/*/predictif_*.json`)."""
    out = []
    for path in sorted(ETUDES.glob("*/predictif_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        dossier = path.parent.name
        page = ROOT / "site" / f"{dossier}.html"
        out.append({"nom": _nom(data), "chemin": str(path.relative_to(ROOT)),
                    "page": page.name if page.exists() else None, "data": data})
    if not out:
        raise ParcoursError("aucun rapport d'étude sous reports/etudes : la page n'a rien à lire.")
    return tuple(out)


def charge(data: dict[str, Any]) -> dict[str, Any]:
    """Ce que `rejouer.chemin` lit d'un rapport, et rien d'autre : le rejeu, et par année le
    coût des deux vues avec les impulsions et les statistiques des canaux."""
    rejeu = {k: data["rejeu"][k] for k in ("start", "cadre", "looped", "behavioural", "lignes",
                                            "macro", "box_rows")}
    years = []
    for row in data["years"]:
        stats = {vue: {"impulses": s.get("impulses") or {}, "canaux": s.get("canaux")}
                 for vue, s in row["statistiques"].items()}
        years.append({"year": row["year"], "mechanical_aged_eur": row["mechanical_aged_eur"],
                      "mechanical_frozen_eur": row["mechanical_frozen_eur"],
                      "statistiques": stats})
    return {"rejeu": rejeu, "years": years}


def theta_demi(data: dict[str, Any], macro: float = 0.5) -> dict[str, float]:
    """Toutes les lignes du rapport à ½, le multiplicateur à `macro`."""
    return {**dict.fromkeys(data["rejeu"]["lignes"], 0.5), rejouer.MACRO_ROW: macro}


def dernier(data: dict[str, Any], *, macro: float = 0.5, persistence: str = rejouer.READ,
            variante: str | None = None) -> float:
    """Δb de la dernière année, vue vieillie, comportements à ½, par la fonction du moteur."""
    return float(rejouer.at_theta(data, theta_demi(data, macro), view=VUE,
                                  persistence=persistence, variante=variante).delta[-1])


def temoin(data: dict[str, Any], persistence: str = rejouer.READ) -> float:
    """Le nombre du rapport à θ½ sous une persistance (`side_by_side`), vue vieillie."""
    lu = next(p for p in data["side_by_side"] if p["persistence"] == persistence)
    return float(lu["years"][-1]["delta_aged"])


def boucles(rapports_: tuple[dict[str, Any], ...] | None = None) -> list[dict[str, Any]]:
    """Les rapports dont la boucle lit au moins un instrument : ceux que le curseur rejoue."""
    return [r for r in (rapports_ or rapports())
            if r["data"]["rejeu"]["looped"] and r["data"]["rejeu"]["macro"]["instruments"]]


# --------------------------------------------------------------------------- #
# la table de Mésange, telle que la boucle la lit
# --------------------------------------------------------------------------- #
def tables() -> dict[str, dict[str, Any]]:
    """Par instrument, la table que les rapports portent, et les rapports qui la portent.
    Deux rapports qui porteraient deux tables différentes pour un instrument : refusé."""
    out: dict[str, dict[str, Any]] = {}
    for r in rapports():
        macro = r["data"]["rejeu"]["macro"]
        if [int(h) for h in macro["horizons"]] != [int(h) for h in HORIZONS]:
            raise ParcoursError(f"{r['chemin']} : horizons {macro['horizons']}, la page lit "
                                f"{HORIZONS}")
        for instrument, table in macro["instruments"].items():
            if table["brut"] != 1.0:
                # La page écrit la part rendue (solde + 1) × m / c : un coût brut d'un point.
                raise ParcoursError(f"{r['chemin']} : « {instrument} » a un coût brut de "
                                    f"{table['brut']} point, la page suppose 1")
            seen = out.setdefault(instrument, {"table": table, "rapports": []})
            if seen["table"] != table:
                raise ParcoursError(f"la table de « {instrument} » diffère entre "
                                    f"{seen['rapports'][0]} et {r['chemin']}")
            seen["rapports"].append(r["chemin"])
    return out


def part_rendue(table: dict[str, Any], horizon: str = "10", theta: float = 0.5) -> float:
    """La part du coût brut que la recette induite rend à un horizon, pour un choc
    permanent, à θ : ce que `rejouer.loop` compte pour une marche d'impulsion."""
    centre = float(table["pib"][horizon])
    m = max(0.0, centre + (2.0 * theta - 1.0) * float(table["sd"]))
    return min((float(table["solde"][horizon]) + table["brut"]) * m / centre,
               table["brut"]) / table["brut"]


def multiplicateur(table: dict[str, Any], horizon: str, theta: float) -> float:
    return max(0.0, float(table["pib"][horizon]) + (2.0 * theta - 1.0) * float(table["sd"]))


def _instrument(nom: str) -> str:
    return etude.INSTRUMENTS.get(nom, nom)


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]


def _titre(fichier_source: str) -> str:
    """La référence d'une source telle que le manifeste la décrit, jusqu'à son contenu."""
    texte = _manifest()[fichier_source]["description"]
    for coupure in (". Section", ". Tableau"):
        texte = texte.split(coupure)[0]
    return texte


def _url(fichier_source: str) -> str:
    entry = _manifest().get(fichier_source)
    if not entry or not entry.get("url"):
        raise ParcoursError(f"{fichier_source} n'a pas d'URL dans data/raw/MANIFEST.json")
    return entry["url"]


def _yaml(chemin: str) -> dict[str, Any]:
    return yaml.safe_load((ROOT / chemin).read_text(encoding="utf-8"))


def impulsions_max(data: dict[str, Any]) -> tuple[float, str, int]:
    """La plus grande impulsion d'un instrument lu par la boucle, en points de PIB de son
    année : (points, instrument, année). Chaque variante de Mésange est d'un point."""
    gdp, _, _ = rejouer.reference_path(data["rejeu"], data["rejeu"]["start"], len(data["years"]))
    lues = data["rejeu"]["macro"]["instruments"]
    best, instrument, year = 0.0, "", int(data["years"][0]["year"])
    for row, y in zip(data["years"], gdp, strict=True):
        for i, v in (row["statistiques"][VUE]["impulses"] or {}).items():
            if i in lues and abs(v / y * 100.0) > abs(best):
                best, instrument, year = v / y * 100.0, i, int(row["year"])
    return best, instrument, year


def non_lus(data: dict[str, Any]) -> list[str]:
    """Les postes qu'une étude déplace et que la boucle ne lit pas, sur toutes ses années."""
    seen: dict[str, None] = {}
    for row in data["years"]:
        for name in (row["statistiques"][VUE].get("uncovered") or {}):
            seen[name] = None
    return list(seen)


# --------------------------------------------------------------------------- #
# la page
# --------------------------------------------------------------------------- #
def _table_mesange(t: dict[str, dict[str, Any]]) -> str:
    head = "".join(f"<th>{h} an{'s' if h != '1' else ''}</th>" for h in HORIZONS)
    rows = []
    for instrument, entry in t.items():
        table = entry["table"]
        nom = esc(_instrument(instrument))
        n = len(entry["rapports"])
        cellule = fichier(entry["rapports"][0], f"{n} rapport{'s' if n > 1 else ''}")
        rows.append(f'<tr><th rowspan="3">{nom}<br><small>{cellule}</small></th><td>PIB (c)</td>'
                    + "".join(f'<td class="num">{fr(table["pib"][h])}</td>' for h in HORIZONS)
                    + "</tr>")
        rows.append("<tr><td>solde</td>" + "".join(
            f'<td class="num">{fr(table["solde"][h])}</td>' for h in HORIZONS) + "</tr>")
        if "pib_salariale" in table:
            rows.append("<tr><td>PIB, variante salariale</td>" + "".join(
                f'<td class="num">{fr(table["pib_salariale"][h])}'
                f'{"" if h in ("1", "5", "10") else "*"}</td>' for h in HORIZONS) + "</tr>")
        else:
            rows.append('<tr><td>PIB, variante salariale</td><td colspan="5">aucune ligne '
                        "imprimée : la ligne centrale reste</td></tr>")
    return ("<table><thead><tr><th>instrument</th><th>ligne</th>" + head
            + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def _table_rendu(t: dict[str, dict[str, Any]]) -> str:
    rows = []
    for instrument, entry in t.items():
        table = entry["table"]
        rows.append(f"<tr><td>{esc(_instrument(instrument))}</td>"
                    f'<td class="num">{fr(table["solde"]["10"])}</td>'
                    f'<td class="num"><strong>{fr(part_rendue(table))}</strong></td>'
                    f'<td class="num">{fr(part_rendue(table, theta=0.0))}</td>'
                    f'<td class="num">{fr(part_rendue(table, theta=1.0))}</td></tr>')
    groupes: dict[str, list[str]] = {}
    for nom, groupe in shocks.UNMAPPED.items():
        groupes.setdefault(groupe, []).append(nom)
    for groupe, noms in groupes.items():
        rows.append(f"<tr><td>{esc(groupe)} : <small>{esc(', '.join(noms))}</small></td>"
                    '<td class="num">—</td><td class="num"><strong>0</strong></td>'
                    '<td class="num">0</td><td class="num">0</td></tr>')
    return ("<table><thead><tr><th>instrument</th><th>solde à 10 ans</th>"
            "<th>part rendue, θ½</th><th>θ = 0</th><th>θ = 1</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table>")


def _table_sigma(t: dict[str, dict[str, Any]]) -> str:
    rows = []
    for instrument, entry in t.items():
        table = entry["table"]
        cells = "".join(f'<td class="num">{fr(multiplicateur(table, h, th))}</td>'
                        for h in ("1", "10") for th in (0.0, 0.5, 1.0))
        rows.append(f"<tr><td>{esc(_instrument(instrument))}</td>"
                    f'<td>{esc(fan.MULTIPLIER_FAMILY.get(instrument, "?"))}</td>'
                    f'<td class="num">{fr(table["sd"])}</td>{cells}</tr>')
    return ("<table><thead><tr><th rowspan=\"2\">instrument</th><th rowspan=\"2\">famille IMK"
            "</th><th rowspan=\"2\">&sigma;</th><th colspan=\"3\">m à 1 an</th><th colspan=\"3\">"
            "m à 10 ans</th></tr><tr><th>θ = 0</th><th>θ½</th><th>θ = 1</th><th>θ = 0</th>"
            "<th>θ½</th><th>θ = 1</th></tr></thead><tbody>" + "".join(rows)
            + "</tbody></table>")


def _table_taille() -> str:
    rows = []
    for r in boucles():
        best, instrument, year = impulsions_max(r["data"])
        rows.append(f"<tr><td>{esc(r['nom'])}</td><td>{esc(_instrument(instrument))}</td>"
                    f"<td class=\"num\">{fr(best, 2, True)}</td><td>{year}</td></tr>")
    return ("<table><thead><tr><th>étude</th><th>instrument</th><th>plus grande impulsion, "
            "en points de PIB</th><th>année</th></tr></thead><tbody>" + "".join(rows)
            + "</tbody></table>")


def _table_lus() -> str:
    rows = []
    for r in rapports():
        lus = [_instrument(i) for i in r["data"]["rejeu"]["macro"]["instruments"]]
        absents = non_lus(r["data"])
        rows.append(f"<tr><td>{esc(r['nom'])}</td><td>{esc(', '.join(lus) or 'aucun')}</td>"
                    f"<td>{esc(', '.join(absents) or 'aucun')}</td></tr>")
    return ("<table><thead><tr><th>étude</th><th>lu par la boucle</th><th>non lu : va à la "
            "dette entier</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def _table_statique() -> str:
    """Δb de la dernière année, vue vieillie : les nombres des rapports (θ½, trois
    persistances, variante) et le rejeu du moteur aux bouts de θ."""
    rows = []
    for r in boucles():
        d = r["data"]
        an = d["years"][-1]["year"]
        variante = d["lectures"]["variante_salariale"]["boite"][VUE]["theta"]
        rows.append(
            f"<tr><td>{esc(r['nom'])} ({an})</td>"
            + "".join(f'<td class="num">{pt(temoin(d, p))}</td>' for p in rejouer.PERSISTENCES)
            + f'<td class="num">{pt(dernier(d, macro=0.0))}</td>'
            f'<td class="num">{pt(dernier(d, macro=1.0))}</td>'
            f'<td class="num">{pt(variante)}</td></tr>')
    return ("<table><thead><tr><th>étude</th><th>lue, θ½</th><th>éteinte, θ½</th><th>tenue, "
            "θ½</th><th>lue, θ = 0</th><th>lue, θ = 1</th><th>variante salariale, lue, θ½"
            "</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def donnees() -> dict[str, Any]:
    """Ce que le script lit : par étude dont la boucle lit un instrument, la charge du
    rejeu et le témoin du rapport."""
    return {"etudes": [{"nom": r["nom"], "payload": charge(r["data"]),
                        "temoin": temoin(r["data"])} for r in boucles()]}


def _curseurs() -> str:
    options = "".join(f'<option value="{i}">{esc(r["nom"])}</option>'
                      for i, r in enumerate(boucles()))
    persistances = "".join(
        f'<option value="{p}">{esc(retroaction.PERSISTENCE_LABELS[p])}</option>'
        for p in rejouer.PERSISTENCES)
    return (
        '<section id="a-curseurs">'
        f'<div class="curseur"><label for="a-etude">L\'étude</label><select id="a-etude">'
        f"{options}</select><span></span></div>"
        '<div class="curseur"><label for="a-theta">θ du multiplicateur : 0, le bas de '
        "l'écart-type ; 1, le haut</label>"
        '<input type="range" id="a-theta" min="0" max="1" step="0.05" value="0.5">'
        '<output id="a-theta-v" class="num">0,50</output></div>'
        '<div class="curseur"><label for="a-persistance">La persistance</label>'
        f'<select id="a-persistance">{persistances}</select><span></span></div>'
        '<div class="curseur"><label for="a-variante">La formation des salaires</label>'
        '<select id="a-variante"><option value="centrale">spécification centrale de Mésange'
        '</option><option value="salariale">variante salariale de Mésange (D-349)</option>'
        "</select><span></span></div></section>\n"
        '<section id="a-resultat"><noscript><p>Sans script, le curseur ne tourne pas ; le '
        "tableau ci-dessous donne les mêmes nombres aux réglages qui comptent.</p>"
        "</noscript></section>\n")


def page() -> Page:
    t = tables()
    mesange_url = _url(mesange.SOURCE_FILE)
    wp117, wp139 = _url(WP117), _url(WP139)
    disp = _yaml(DISPERSION)
    mult = _yaml(MULTIPLIERS)
    sd = sorted({e["table"]["sd"] for e in t.values()})
    cot = t.get("cotisations_salaries")
    hors = [k for k in mesange.VARIANTS if k not in t]
    attal = next((r for r in boucles() if "attal" in r["chemin"]), None)
    exemple = ""
    premier = min(int(r["data"]["years"][0]["year"]) for r in boucles())
    fin = max(int(r["data"]["years"][-1]["year"]) for r in boucles())
    if cot is not None:
        exemple = (f" Pour une baisse de cotisations des salariés, le solde à dix ans vaut "
                   f"{fr(cot['table']['solde']['10'])} : un euro rendu en revient "
                   f"{fr(part_rendue(cot['table']))} par la croissance.")
    taille = ""
    if attal is not None:
        best, instrument, year = impulsions_max(attal["data"])
        taille = (f" La part chiffrée de {esc(attal['nom'])} pousse {esc(_instrument(instrument))} "
                  f"de {fr(best, 2)} points de PIB en {year} ; rien dans le calcul ne tient "
                  "compte de cette taille.")
    corps = (
        "<h2>La boucle, en une ligne</h2>\n"
        "<p>Une mesure qui rend de l'argent aux ménages fait monter l'activité ; l'activité "
        "plus haute fait rentrer des impôts et sortir moins d'allocations chômage. L'outil ne "
        "calcule pas cette réaction lui-même : il la lit, instrument par instrument, dans les "
        "variantes du modèle Mésange, publiées par l'Insee et la DG Trésor "
        f"({source(mesange_url, _titre(mesange.SOURCE_FILE))}, section 4). "
        "Chaque variante dit, pour une baisse d'un point de PIB d'un impôt, de combien le PIB "
        "monte (c) et de combien le solde public se dégrade (solde), à 1, 2, 3, 5 et 10 ans.</p>\n"
        "<p>Pour chaque année et chaque marche de l'impulsion, la boucle prend le multiplicateur "
        "<em>m</em> = max(0, <em>c</em>(<em>h</em>) + (2θ − 1) &sigma;) et rend au budget "
        "(solde(<em>h</em>) + 1) × <em>m</em> / <em>c</em>(<em>h</em>) du coût, jamais plus que "
        "le coût lui-même (D-336). À θ½, <em>m</em> = <em>c</em> et la part rendue est "
        "simplement 1 + solde : <strong>un seul nombre de la table par horizon</strong>."
        f"{exemple} Le calcul est dans {fichier('src/impots/predictif/rejouer.py')} "
        f"(<code>loop</code>), égal à {fichier('src/impots/predictif/retroaction.py')} ; la "
        f"table est tirée du PDF par {fichier('src/impots/macro/mesange.py')}, jamais "
        "recopiée à la main.</p>\n"
        "<h2>La table, instrument par instrument</h2>\n"
        "<p>Réponse du PIB (en %) et du solde primaire (en points de PIB) à un choc permanent "
        "d'un point de PIB, telle que la boucle la lit dans les rapports des études : chaque "
        "instrument porte la même table dans tous les rapports qui le lisent, sinon la page "
        "refuse de se construire. La variante salariale n'est imprimée qu'à 1, 5 et 10 ans ; "
        "l'astérisque marque les horizons interpolés (D-349).</p>\n"
        + _table_mesange(t)
        + "<p>Mésange imprime ces chocs « de façon permanente, à taux d'intérêt réels "
        "constants et à taux de change nominaux constants », sans réaction de la politique "
        f"budgétaire ni monétaire ({fichier(MULTIPLIERS)}). Ses autres variantes, que "
        "l'outil lit dans le PDF mais qu'aucune étude publiée ne fait tourner, ne sont pas "
        "dans un fichier commité et ne sont pas montrées ici : "
        + esc(" ; ".join(mesange.VARIANTS[k].shock for k in hors)) + ".</p>\n"
        "<h2>La part rendue à dix ans</h2>\n"
        "<p>Pour un choc permanent, la part du coût que la croissance rend au bout de dix "
        "ans. Aux bouts de θ, le multiplicateur se déplace d'un écart-type et la part avec "
        "lui, bornée à zéro et au coût. Ce que la boucle ne lit pas rend zéro, quel que soit "
        f"θ : les postes sans variante dans Mésange ({fichier('src/impots/macro/shocks.py')}, "
        "<code>UNMAPPED</code>).</p>\n"
        + _table_rendu(t)
        + "<p>C'est ce zéro qui fait qu'un euro d'impôt sur les sociétés rendu pèse plus sur la "
        "dette qu'un euro de cotisations : l'outil ne mesure pas que l'IS ne rapporte pas de "
        "croissance, il ne sait pas le lire (D-356). Les raisons, telles que le code les "
        "donne :</p>\n<ul>"
        + "".join(f"<li><strong>{esc(g)}</strong> — {esc(r)}</li>"
                  for g, r in shocks.UNMAPPED_REASONS.items())
        + "</ul>\n"
        "<h2>&sigma;, l'écart-type des méta-analyses d'IMK</h2>\n"
        f"<p>Mésange ne publie aucun intervalle. La largeur vient de deux méta-analyses de "
        f"l'institut IMK : {source(wp117, _titre(WP117))} et "
        f"{source(wp139, _titre(WP139))}. Le fichier "
        f"les cite ainsi : « {esc(' '.join(disp['source_table']['citation'].split()))} » "
        f"&sigma; = {esc(' ; '.join(fr(s) for s in sd))} est l'écart-type des multiplicateurs "
        "rapportés pour les baisses d'impôt (la famille « TAX », qui ne distingue pas l'IR de "
        "la TVA ni des cotisations).</p>\n"
        "<p><strong>Ce n'est pas l'erreur d'estimation du multiplicateur français.</strong> "
        "C'est une dispersion entre études : d'autres pays, d'autres horizons confondus, "
        "d'autres méthodes. Le fichier qui la porte le dit en tête "
        f"({fichier(DISPERSION)}) ; l'auteur aussi : « "
        f"{esc(' '.join(disp['source_table']['quote'].split()))} » θ = 0 retire un &sigma; au "
        "centre de Mésange, θ = 1 l'ajoute ; un multiplicateur négatif n'étant dans aucune "
        f"étude, il est borné à zéro. Lu par {fichier('src/impots/macro/imk.py')}.</p>\n"
        + _table_sigma(t)
        + "<h2>Linéaire dans la taille du choc</h2>\n"
        "<p>Les variantes de Mésange sont d'un point de PIB. La boucle divise l'impulsion de "
        "chaque année par le PIB de l'année et multiplie : un choc de trois points y rend "
        f"trois fois ce que rend un choc d'un point.{taille} Mésange est un modèle linéaire, "
        f"sans état du cycle ; c'est la source qui le dit ({fichier('src/impots/macro/mesange.py')}"
        "), pas une mesure qu'on aurait faite sur de grands chocs.</p>\n"
        + _table_taille()
        + "<h2>Ce que la boucle lit, étude par étude</h2>\n"
        "<p>Un poste que la boucle ne lit pas n'a ni effet sur le PIB ni recette induite : son "
        "coût va à la dette entier. Les verdicts des études ne se comparent donc pas d'un "
        "candidat à l'autre tant que la boucle ne lit pas les impôts des entreprises "
        f"(D-358) ; la page {lien('comparer')} le dit.</p>\n"
        + _table_lus()
        + "<h2>Faire varier le multiplicateur</h2>\n"
        f"<p>Le curseur rejoue la dette d'une étude, de {premier} à {fin}, depuis son rapport : les "
        "coûts de chaque année, les impulsions par instrument, et la table ci-dessus. "
        "Trois réglages : θ du multiplicateur ; la <strong>persistance</strong>, « lue » "
        "(Mésange à 1, 2, 3, 5 et 10 ans, interpolé entre eux : celle du verdict), « éteinte » "
        "(rien après trois ans) ou « tenue » (le niveau de la troisième année ensuite), les "
        "deux dernières publiées comme sensibilités (D-336, D-337) ; la <strong>variante "
        "salariale</strong>, où Mésange forme les salaires autrement et où seul le centre du "
        "multiplicateur bouge, le solde restant proportionnel au PIB, ce qui est une "
        "hypothèse (D-349). Les comportements restent à θ½ ; ils ont leur page, "
        f"{lien('comportements')}. La dette elle-même a la sienne, {lien('dette')}.</p>\n"
        + _curseurs()
        + "<p>Les mêmes nombres, sans script : la dette de la dernière année, en points de PIB, "
        "vue vieillie. Les colonnes à θ½ sont celles des rapports ; les colonnes aux bouts de "
        "θ sont le rejeu des rapports par la fonction du moteur, comportements à θ½.</p>\n"
        + _table_statique()
        + "<h2>Ce qui n'est pas vérifié</h2>\n"
        "<p>Aucune évaluation après coup d'une baisse de cotisations des salariés n'a été "
        "confrontée à la boucle ; la seule porte est celle du CICE, sur l'éventail d'emplois "
        f"(README, phase 4). Les multiplicateurs sont ceux d'un modèle réestimé en "
        f"{esc(str(mult['source_table']['vintage']))}, et la boucle les prend tels quels "
        "jusqu'au bout de l'horizon. "
        f"{lien('erreur', 'Où l’outil se trompe')} range cette absence à son étage.</p>\n"
    )
    script = ("window.PARCOURS_ACTIVITE = "
              + json.dumps(donnees(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
              + ";\n" + (JS / "activite.js").read_text(encoding="utf-8"))
    return Page(
        prouve=("ce que la croissance rend à la dette tient, pour chaque impôt et chaque "
                "horizon, à un seul nombre d'une table de Mésange (Insee et DG Trésor), "
                "élargi d'un écart-type entre études ; il vaut zéro pour ce que Mésange ne "
                "porte pas."),
        corps=corps, script=script,
        style="#a-resultat .note{color:var(--doux);font-size:.9rem}")
