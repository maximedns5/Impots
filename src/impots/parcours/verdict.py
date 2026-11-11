"""Page 7 du parcours : le verdict.

Un verdict n'est pas un jugement de l'outil : c'est la part des tirages où la dette de
2035 monte, sous des lois écrites, lue contre un seuil fixé avant toute passe (D-345). La
page montre, pour deux études, la boîte θ et le Monte-Carlo côte à côte, tels que leurs
rapports commités les portent (`theta_box`, `monte_carlo`), les lois tirées (le magasin
des élasticités, la copule ρ, le multiplicateur normal censuré), les indices de Sobol, et
le seuil.

Le curseur rejoue le Monte-Carlo dans le navigateur (`js/verdict.js`, sur la dette de
`js/dette.js`), par la même arithmétique que `predictif/montecarlo.py`. Une seule chose
n'est pas refaite dans le navigateur : le générateur de nombres de numpy. Les normales
centrées réduites de la graine du rapport sont tirées ici, à la construction, par numpy,
dans l'ordre de `montecarlo._draw`, et la page les porte ; le reste (ρ, l'écart-type, les lois, la
dette, la part, les quantiles, Sobol) se refait. Au cadre du rapport, la page redonne le
rapport (`tests/test_parcours_verdict.py`).
"""

from __future__ import annotations

import base64
import html
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots.parcours import ROOT, Page, ParcoursError, fichier, lien, source
from impots.parcours.dette import charge, etudes, fr, pct, pt, publique
from impots.predictif import montecarlo, rejouer

JS = Path(__file__).resolve().parent / "js"
MAGASIN = "src/impots/behavioural/parameters"
DISPERSION = "src/impots/macro/parameters/dispersion.yaml"
#: Les études montrées : la plus proche du seuil, puis celle qui ouvre la série.
MONTREES = ("presidentielle_lisnard", "presidentielle_attal")
VUES = (("vieillie", "vue vieillie"), ("figee", "vue figée"))
INSTRUMENTS = {"cotisations_salaries": "cotisations des salariés",
               "cotisations_employeurs": "cotisations des employeurs",
               "cotisations_employeurs_ciblees": "cotisations des employeurs ciblées",
               "impot_sur_le_revenu": "impôt sur le revenu", "csg": "CSG", "tva": "TVA",
               "taxe_carbone": "accises sur l'énergie"}
esc = html.escape


def montrees() -> list[dict[str, Any]]:
    par_nom = {e["nom"]: e for e in etudes()}
    out = []
    for nom in MONTREES:
        if nom not in par_nom:
            raise ParcoursError(f"l'étude {nom} manque.")
        e = par_nom[nom]
        if not e["data"].get("monte_carlo") or not e["data"].get("theta_box"):
            raise ParcoursError(f"{e['chemin']} ne porte pas le Monte-Carlo et la boîte.")
        out.append(e)
    return out


def tirages(monte: dict[str, Any]) -> dict[str, Any]:
    """Les normales centrées réduites de la graine du rapport, dans l'ordre de
    `montecarlo._draw` : l'échantillon A puis B, chacun groupe par groupe ; une colonne
    pour le multiplicateur, une matrice (tirages × lignes) pour un article. En base64,
    flottants de 64 bits petit-boutistes."""
    n = int(monte["tirages"])
    rng = np.random.default_rng(int(monte["graine"]))
    echantillons = []
    for _ in range(2):
        s = {}
        for name, keys in monte["groupes"].items():
            draw = (rng.standard_normal(n) if name == rejouer.MACRO_ROW
                    else rng.standard_normal((n, len(keys))))
            s[name] = base64.b64encode(
                np.ascontiguousarray(draw, dtype="<f8").tobytes()).decode("ascii")
        echantillons.append(s)
    return {"n": n, "groupes": [[k, list(v)] for k, v in monte["groupes"].items()],
            "a": echantillons[0], "b": echantillons[1]}


def boite(data: dict[str, Any]) -> dict[str, Any]:
    """La boîte θ du rapport sous la persistance lue : Δb à θ½, le plus petit et le plus
    grand coin, par vue, et sa lecture (`rejouer.verdict` : un seul signe partout, ou
    non)."""
    path = next((p for p in data["theta_box"]["paths"] if p["persistence"] == rejouer.READ),
                None)
    if path is None:
        raise ParcoursError(f"{data['scenario']} : pas de boîte sous la persistance lue.")
    out: dict[str, Any] = {"lignes": data["theta_box"]["rows"], "vues": {}}
    signes = set()
    for view, _ in VUES:
        read = path["every_year"][view]
        valeurs = [v for _, v in read["corners"]]
        out["vues"][view] = {"theta": read["theta"], "min": min(valeurs), "max": max(valeurs),
                             "coins": len(valeurs)}
        for v in [read["theta"], *valeurs]:
            signes.add(math.copysign(1.0, v) if v else 0.0)
    out["lecture"] = ("hausse" if signes == {1.0} else "baisse" if signes == {-1.0}
                      else "dépend de θ")
    return out


def _article(fichier_yaml: str) -> dict[str, Any]:
    chemin = f"{MAGASIN}/{fichier_yaml}.yaml"
    document = yaml.safe_load((ROOT / chemin).read_text(encoding="utf-8"))
    return {"chemin": chemin, "parametres": document["parameters"]}


def _premiere_phrase(texte: str) -> str:
    phrase = " ".join(texte.split()).split(". ")[0].split(" — ")[0]
    return ", ".join(phrase.split(", ")[:2])


def _lois_html(e: dict[str, Any]) -> str:
    data = e["data"]
    monte = data["monte_carlo"]
    rejeu = data["rejeu"]
    rows = []
    for name, keys in monte["groupes"].items():
        if name == rejouer.MACRO_ROW:
            continue
        article = _article(name)
        for key in keys:
            row = rejeu["lignes"][key]
            yaml_row = article["parametres"][key]
            cite = " ".join(yaml_row["source"]["citation"].split()).split(" — ")[0]
            rows.append(
                f"<tr><td><code>{esc(key)}</code><br>{esc(_premiere_phrase(yaml_row['applies_to']))}"
                f'</td><td class="num">{fr(row["low"], 4)}</td><td class="num">'
                f'{fr(row["central"], 4)}</td><td class="num">{fr(row["high"], 4)}</td>'
                f"<td>{esc({'triangular': 'triangulaire'}.get(row['loi'], row['loi']))}</td>"
                f"<td>{source(yaml_row['source']['url'], cite)} ; "
                f"{fichier(article['chemin'], name + '.yaml')}</td></tr>")
    fixes = [k for k, r in rejeu["lignes"].items() if float(r["low"]) == float(r["high"])]
    lignes = ""
    if rows:
        lignes = ("<table><thead><tr><th>ligne tirée</th><th>bas</th><th>centre</th>"
                  "<th>haut</th><th>loi</th><th>article, fichier du magasin</th></tr></thead>"
                  "<tbody>" + "".join(rows) + "</tbody></table>\n")
    else:
        lignes = ("<p>Aucune ligne de comportement n'est tirée pour cette étude : ses "
                  "mesures n'ouvrent aucun canal revendiqué, et seul le multiplicateur "
                  "varie. La corrélation ρ n'y change donc rien.</p>\n")
    if fixes:
        lignes += (f"<p>Fixées à leur centre, faute de fourchette : "
                   f"{', '.join(f'<code>{esc(k)}</code>' for k in fixes)}.</p>\n")
    macro = rejeu["macro"]
    horizons = [str(h) for h in macro["horizons"]]
    mrows = "".join(
        f"<tr><td>{esc(INSTRUMENTS.get(i, i))}</td>"
        + "".join(f'<td class="num">{fr(t["pib"][h], 2)}</td>' for h in horizons)
        + f'<td class="num">{fr(t["sd"], 2)}</td></tr>'
        for i, t in sorted(macro["instruments"].items()))
    return (
        f"<h3>{esc(e['candidat'])}</h3>\n" + lignes
        + "<table><thead><tr><th>multiplicateur, par instrument</th>"
        + "".join(f"<th>{h} an{'s' if h != '1' else ''}</th>" for h in horizons)
        + "<th>\u03c3</th></tr></thead><tbody>" + mrows + "</tbody></table>\n")


def _sobol_rows(e: dict[str, Any]) -> str:
    vues = e["data"]["monte_carlo"]["vues"]
    rows = []
    for name in e["data"]["monte_carlo"]["groupes"]:
        label = ("le multiplicateur" if name == rejouer.MACRO_ROW
                 else f"les lignes de {name}.yaml")
        cells = "".join(
            f'<td class="num">{fr(vues[v]["sobol"][name]["premier_ordre"], 3)}</td>'
            f'<td class="num">{fr(vues[v]["sobol"][name]["total"], 3)}</td>'
            for v, _ in VUES)
        rows.append(f"<tr><td>{esc(e['candidat'])}</td><td>{esc(label)}</td>{cells}</tr>")
    return "".join(rows)


def _cote_a_cote(liste: list[dict[str, Any]], seuil: float) -> str:
    rows = []
    for e in liste:
        b = boite(e["data"])
        monte = e["data"]["monte_carlo"]
        for view, nom_vue in VUES:
            bv, mv = b["vues"][view], monte["vues"][view]
            verdict = (montecarlo.verdict(monte, view=view)
                       if view == "vieillie" else "—")
            rows.append(
                f"<tr><td>{esc(e['candidat'])}</td><td>{esc(nom_vue)}</td>"
                f'<td class="num">{pt(bv["theta"])}</td>'
                f'<td class="num">{pt(bv["min"])} à {pt(bv["max"])}</td>'
                f'<td class="num">{pct(mv["p_hausse"], 2)}</td>'
                f'<td class="num">{pt(mv["quantiles"]["q05"])} · {pt(mv["quantiles"]["q50"])}'
                f' · {pt(mv["quantiles"]["q95"])}</td>'
                f"<td>{esc(verdict)}</td>"
                f"<td>{esc(b['lecture']) if view == 'vieillie' else '—'}</td></tr>")
    e0 = liste[0]
    b0, m0 = boite(e0["data"]), e0["data"]["monte_carlo"]
    return (
        '<h2 id="cote-a-cote">Deux objets, côte à côte</h2>\n'
        "<p>Chaque étude publie deux lectures de la même incertitude, et ne les mélange "
        "pas.</p>\n<ul>\n"
        "<li><strong>La boîte θ</strong> place chaque réponse revendiquée, et le "
        "multiplicateur, à chaque bout de sa fourchette publiée, et lit la dette de 2035 "
        f"à tous les coins ({b0['vues']['vieillie']['coins']} pour "
        f"{esc(e0['candidat'])}). Elle dit jusqu'où le nombre bouge. Elle ne dit pas "
        "avec quelle probabilité : un coin, où tout tombe du même côté à la fois, n'est "
        "pas plus probable que le milieu. Sa lecture, « selon θ », est « hausse » ou "
        "« baisse » si tous les coins et le milieu ont le même signe, dans les deux vues, "
        "et « dépend de θ » sinon.</li>\n"
        "<li><strong>Le Monte-Carlo</strong> tire chaque réponse selon une loi écrite, "
        f"{fr(m0['tirages'], 0)} fois, et compte les tirages où la dette monte. C'est une "
        "probabilité, mais sous ces lois-là : changer une loi change la réponse, et la "
        "page le montre plus bas.</li>\n</ul>\n"
        "<table><thead><tr><th>étude</th><th>vue</th><th>Δb à θ½</th>"
        "<th>boîte : du plus bas au plus haut coin</th><th>P(hausse)</th>"
        "<th>quantiles 5 · 50 · 95 %</th><th>verdict</th><th>selon θ</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>\n"
        f"<p>Δb en {m0['annee']}, en points de PIB, persistance « lue ». Lu dans "
        "<code>theta_box</code> et <code>monte_carlo</code> des rapports ("
        + ", ".join(fichier(e["chemin"], e["candidat"]) for e in liste) + "). Le verdict "
        "se lit vue vieillie (D-349) ; la boîte, dans les deux vues.</p>\n"
        + _queues(liste))


def _part_multiplicateur(liste: list[dict[str, Any]]) -> float:
    """La plus petite part de variance que le multiplicateur porte (Sobol total)."""
    return min(e["data"]["monte_carlo"]["vues"][v]["sobol"][rejouer.MACRO_ROW]["total"]
               for e in liste for v, _ in VUES)


def _proche(e: dict[str, Any], seuil: float) -> str:
    """« la plus proche du seuil » quand elle l'est, parmi toutes les études."""
    ecart = {x["nom"]: abs(x["data"]["monte_carlo"]["vues"]["vieillie"]["p_hausse"] - seuil)
             for x in etudes()}
    if ecart[e["nom"]] == min(ecart.values()):
        return "de toutes les études la plus proche du seuil"
    return "proche du seuil"


def _queues(liste: list[dict[str, Any]]) -> str:
    """Ce que le Monte-Carlo voit et que la boîte ne voit pas : les quantiles hors des
    coins, et une lecture de la boîte qui diffère du verdict."""
    out = []
    for e in liste:
        b = boite(e["data"])
        monte = e["data"]["monte_carlo"]
        bv, q = b["vues"]["vieillie"], monte["vues"]["vieillie"]["quantiles"]
        hors = []
        if q["q05"] < bv["min"]:
            hors.append(f"le quantile à 5 % ({pt(q['q05'])}) est sous le plus bas coin "
                        f"({pt(bv['min'])})")
        if q["q95"] > bv["max"]:
            hors.append(f"le quantile à 95 % ({pt(q['q95'])}) est au-dessus du plus haut "
                        f"({pt(bv['max'])})")
        if not hors:
            continue
        texte = f"Pour {esc(e['candidat'])}, vue vieillie, " + " et ".join(hors) + "."
        mc = montecarlo.verdict(monte)
        if b["lecture"] != mc:
            texte += (f" C'est pourquoi la boîte lit « {esc(b['lecture'])} » quand le "
                      f"verdict lit « {esc(mc)} » : tous les coins font monter la dette, "
                      f"mais {pct(1 - monte['vues']['vieillie']['p_hausse'], 2)} des "
                      "tirages la font baisser : ceux où le multiplicateur dépasse son centre "
                      "Mésange de plus d'un écart-type, plus loin que le coin de la boîte "
                      "(θ = 1 l'y place).") if b["lecture"] == "hausse" else (
                      f" La boîte lit « {esc(b['lecture'])} », le verdict « {esc(mc)} ».")
        out.append(texte)
    if not out:
        return ""
    return ("<p>Le Monte-Carlo n'est pas borné par la boîte : la loi normale du "
            "multiplicateur a des queues que les coins ne parcourent pas. "
            + " ".join(out) + "</p>")


def _lois(liste: list[dict[str, Any]]) -> str:
    m0 = liste[0]["data"]["monte_carlo"]
    return (
        '<h2 id="lois">Les lois, écrites</h2>\n'
        f"<p>Le rapport les écrit en une phrase : « {esc(m0['lois'])} » Elles sont "
        f"déclarées dans {fichier('src/impots/predictif/montecarlo.py')}, et nulle part "
        "ailleurs.</p>\n<ul>\n"
        "<li><strong>Chaque réponse revendiquée</strong> suit sa loi du magasin des "
        "élasticités : triangulaire sur (bas, centre, haut), les trois nombres de "
        f"l'article qui la publie (page {lien('comportements')}).</li>\n"
        "<li><strong>Les lignes d'un même article bougent ensemble</strong> : une copule "
        f"gaussienne de corrélation ρ = {fr(m0['rho'], 1)} les lie ; deux articles sont "
        f"indépendants. La clé d'un article est {esc(m0['cle_copule'])}. "
        f"<strong>ρ = {fr(m0['rho'], 1)} n'a pas de source</strong> : c'est un choix "
        "(D-336), et le curseur plus bas le fait varier.</li>\n"
        "<li><strong>Le multiplicateur</strong> vaut, à chaque horizon, le centre de "
        f"Mésange plus z fois \u03c3, z normal centré réduit, « {esc(m0['multiplicateur']['loi'])} »"
        " : un multiplicateur négatif n'est dans aucune étude, il est ramené à zéro. Le "
        f"centre vient de Mésange ({publique('insee_G2017-04_mesange.pdf', 'Insee, G2017/04')}"
        "), \u03c3 de l'écart entre les études que rassemble une méta-analyse "
        f"({publique('imk_wp117_2013_gechert_meta_regression.pdf', 'Gechert, IMK WP 117, tableau 1')} ; "
        f"{fichier(DISPERSION)}). \u03c3 n'est pas une erreur d'estimation : c'est la "
        f"dispersion des multiplicateurs publiés (page {lien('activite')}).</li>\n"
        f"<li><strong>{fr(m0['tirages'], 0)} tirages, graine {m0['graine']}</strong> : "
        "le même calcul redonne le même nombre, au tirage près.</li>\n</ul>\n"
        + "".join(_lois_html(e) for e in liste)
        + "<p>Lu dans <code>rejeu.lignes</code> et <code>rejeu.macro</code> des rapports ; "
        "le multiplicateur aux horizons 1, 2, 3, 5 et 10 ans est la ligne de PIB de "
        "Mésange que la boucle lit, interpolée entre eux.</p>")


def _sobol(liste: list[dict[str, Any]]) -> str:
    return (
        '<h2 id="sobol">Ce qui fait varier le résultat</h2>\n'
        "<p>Les indices de Sobol partagent la variance de la dette de 2035 entre les "
        "entrées tirées : un article (ses lignes ensemble, puisqu'elles sont corrélées) ou "
        "le multiplicateur. Le premier ordre est la part qu'une entrée explique seule ; "
        "le total, la part qu'elle explique avec ses interactions. Ce sont des "
        "estimations sur les tirages : un premier ordre un peu au-dessus de 1 ou sous 0 "
        "est du bruit d'estimation, pas une erreur.</p>\n"
        "<table><thead><tr><th>étude</th><th>entrée</th><th>premier ordre, vieillie</th>"
        "<th>total, vieillie</th><th>premier ordre, figée</th><th>total, figée</th></tr>"
        "</thead><tbody>" + "".join(_sobol_rows(e) for e in liste) + "</tbody></table>\n"
        "<p>Lu dans <code>monte_carlo.vues[…].sobol</code> des rapports (échantillonnage "
        "de Saltelli, estimateur total de Jansen, "
        f"{fichier('src/impots/predictif/montecarlo.py')}). Le multiplicateur porte au "
        f"moins {pct(_part_multiplicateur(liste), 0)} de la variance (indice total, dans "
        "chaque étude et chaque vue) : la dette de 2035 est incertaine d'abord parce que "
        "l'effet de la mesure sur l'activité l'est.</p>")


def _seuil(seuil: float) -> str:
    return (
        '<h2 id="seuil">Le seuil, fixé avant le calcul</h2>\n'
        "<p>Le verdict est « hausse » si au moins "
        f"{pct(seuil, 0)} des tirages font monter la dette de 2035, vue vieillie ; "
        f"« baisse » si au plus {pct(1 - seuil, 0)} le font ; « dépend » entre les deux. "
        "Ces seuils ont été fixés par le propriétaire du dépôt avant toute passe de la "
        "série, et ne bougent plus (D-345). Ils sont dans "
        f"{fichier('src/impots/predictif/montecarlo.py')} (<code>SEUIL_VERDICT</code>). "
        "Un seuil n'est pas un fait : c'est le degré d'accord qu'on exige des tirages "
        "avant de dire qu'une mesure fait monter la dette. Le curseur plus bas montre "
        "combien le mot dépend de ce choix.</p>")


def _curseurs(liste: list[dict[str, Any]], seuil: float) -> str:
    options = "".join(f'<option value="{i}"{" selected" if i == 0 else ""}>'
                      f"{esc(e['candidat'])}</option>" for i, e in enumerate(liste))
    m0 = liste[0]["data"]["monte_carlo"]

    def curseur(ident: str, texte: str, mini: float, maxi: float, pas: float,
                valeur: float, affiche: str) -> str:
        return (f'<div class="curseur"><label for="{ident}">{esc(texte)}</label>'
                f'<input type="range" id="{ident}" min="{mini}" max="{maxi}" step="{pas}" '
                f'value="{valeur}"><output id="{ident}-v" for="{ident}">{affiche}</output>'
                "</div>")

    return (
        '<h2 id="curseurs">À vous : le seuil, ρ et \u03c3</h2>\n'
        "<p>Le navigateur refait ici le Monte-Carlo du rapport, tirage par tirage, par la "
        f"même arithmétique que {fichier('src/impots/predictif/montecarlo.py')} "
        f"({fichier('src/impots/parcours/js/verdict.js')}, sur la dette de "
        f"{fichier('src/impots/parcours/js/dette.js')}). Une seule chose n'y est pas "
        "refaite : le générateur de nombres aléatoires de numpy, que le navigateur n'a "
        f"pas. Les normales de la graine {m0['graine']} sont tirées par numpy à la "
        "construction de la page, dans l'ordre du calcul, et la page les porte ; le "
        "navigateur leur applique ρ, \u03c3 et les lois. Aux valeurs du rapport, il redonne "
        "ses nombres au tirage près ; un test le vérifie.</p>\n"
        "<noscript><p><strong>Sans JavaScript</strong>, les curseurs ne bougent pas : les "
        "tableaux de cette page sont ceux des rapports, aux lois et au seuil "
        "déclarés.</p></noscript>\n"
        '<div id="v-curseurs">\n'
        f'<div class="curseur"><label for="v-etude">l\'étude</label><select id="v-etude">'
        f"{options}</select><span></span></div>\n"
        + curseur("v-seuil", "le seuil du verdict", 0.5, 0.99, 0.01, seuil, pct(seuil, 0))
        + "\n"
        + curseur("v-rho", "ρ, la corrélation des lignes d'un article", 0, 0.95, 0.05,
                  m0["rho"], fr(m0["rho"], 2))
        + "\n"
        + curseur("v-sigma", "\u03c3 du multiplicateur, multiplié par", 0, 2, 0.05, 1.0,
                  "×\u202f" + fr(1.0, 2))
        + "\n"
        '<p><button type="button" id="v-retour">revenir aux lois et au seuil déclarés'
        "</button></p>\n"
        '<p id="v-verdict" aria-live="polite"></p>\n'
        '<p id="v-pourquoi"></p>\n'
        '<table><thead><tr><th>vue</th><th>P(hausse)</th><th>quantiles 5 · 50 · 95 %</th>'
        '</tr></thead><tbody id="v-vues"></tbody></table>\n'
        '<table><thead><tr><th>entrée</th><th>premier ordre, vieillie</th>'
        '<th>total, vieillie</th></tr></thead><tbody id="v-sobol"></tbody></table>\n'
        "</div>\n")


def page() -> Page:
    liste = montrees()
    seuil = montecarlo.SEUIL_VERDICT
    donnees = {
        "seuil": seuil,
        "etudes": [{"candidat": e["candidat"], "chemin": e["chemin"],
                    "payload": charge(e["data"]), "tirages": tirages(e["data"]["monte_carlo"]),
                    "rho": e["data"]["monte_carlo"]["rho"],
                    "rapport": e["data"]["monte_carlo"]["vues"],
                    "annee": e["data"]["monte_carlo"]["annee"]}
                   for e in liste],
    }
    corps = "\n".join([
        "<p>Chaque étude finit par un mot : « hausse », « baisse » ou « dépend ». Ce mot "
        "n'est pas une opinion de l'outil. C'est une part de tirages, sous des lois "
        "écrites, comparée à un seuil écrit avant le calcul. Cette page montre les trois : "
        f"les lois, la part, le seuil, sur deux études : {esc(liste[0]['candidat'])}, "
        f"{_proche(liste[0], seuil)}, et {esc(liste[1]['candidat'])}, dont la page "
        f"{lien('dette')} suit la dette pas à pas.</p>",
        _cote_a_cote(liste, seuil),
        _lois(liste),
        _sobol(liste),
        _seuil(seuil),
        _curseurs(liste, seuil),
    ])
    script = ("var PARCOURS_VERDICT = "
              + json.dumps(donnees, ensure_ascii=False).replace("<", "\\u003c") + ";\n"
              + (JS / "dette.js").read_text(encoding="utf-8") + "\n"
              + (JS / "verdict.js").read_text(encoding="utf-8"))
    return Page(prouve="un verdict est une probabilité sous des lois écrites, comparée à un "
                       "seuil écrit d'avance ; ce n'est pas un jugement.",
                corps=corps, script=script, style="#v-verdict{font-weight:600}")
