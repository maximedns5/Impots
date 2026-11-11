"""Page 6 du parcours : la dette.

La dette d'une étude est une identité comptable, pas un modèle : chaque année, la dette
ajoutée par la réforme croît de son taux, se dilue dans la croissance nominale, et reçoit
le solde primaire de la réforme et les recettes que l'activité induit ; le ratio se lit
sur un PIB que la réforme déplace. Ses hypothèses se nomment une à une : le départ de
2025 (publié), la croissance, les prix, la règle de dépense, le taux.

La page lit les rapports prédictifs commités des huit études présidentielles
(`reports/etudes/presidentielle_*/predictif_*.json`) : leur départ (`rejeu.start`), leur
trajectoire de référence (`years[].reference`), Δb chaque année sous la persistance lue
(`side_by_side`), la décomposition en trois marches et le taux de marché
(`lectures`, D-349). Le curseur rejoue la chaîne d'un rapport dans le navigateur
(`js/dette.js`, la même arithmétique que `predictif/rejouer.py`) sur un cadre que le
lecteur change. Rien n'est chiffré de neuf : au cadre central, le rejeu redonne le rapport
(`tests/test_parcours_dette.py`).
"""

from __future__ import annotations

import html
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from impots.parcours import ROOT, Page, ParcoursError, fichier, lien, source

JS = Path(__file__).resolve().parent / "js"
ETUDES = ROOT / "etudes"
RAPPORTS = ROOT / "reports" / "etudes"
MANIFEST = ROOT / "data" / "raw" / "MANIFEST.json"
CADRE = "etudes/cadres/central.json"
#: L'étude montrée d'abord : celle dont la page d'étude ouvre la série.
PREMIERE = "presidentielle_attal"
LUE = "lue"
#: Les hypothèses que le gouvernement publie pour 2025 à 2029 : le rapport économique,
#: social et financier annexé au PLF 2026, tableau 1 p. 64 (« Principaux indicateurs du
#: scénario économique 2025-2029 »), le dernier du manifeste des données. Écrites ici,
#: le PDF n'étant pas dans le dépôt ; `tests/test_parcours_dette.py` les relit dans le
#: PDF quand il est là. Le curseur avertit quand le cadre en sort.
RESF = {
    "fichier": "resf_2026.pdf", "page": 64,
    "annees": (2025, 2026, 2027, 2028, 2029),
    "pib_volume": (0.007, 0.010, 0.012, 0.013, 0.013),
    "deflateur": (0.015, 0.015, 0.016, 0.016, 0.016),
}
#: Le rapport économique annexé au PLF 2027 n'est pas au manifeste des données : les
#: plages pluriannuelles sont donc celles du PLF 2026. Ce que le texte du PLF 2027 publie,
#: lui, pour 2025 à 2027 : l'article liminaire (dette au sens de Maastricht, évolution de
#: la dépense publique hors crédits d'impôt en volume) et l'exposé général des motifs
#: (croissance du PIB). Écrits ici, le texte n'étant pas dans le dépôt ;
#: `tests/test_parcours_dette.py` les relit dans le texte quand il est là.
PLF2027 = {
    "fichier": "plf2027_texte_an_b3210.html",
    "annees": (2025, 2026, 2027),
    "dette": (1.157, 1.193, 1.217),
    "depense_volume": (0.016, 0.007, 0.006),
    "croissance": {2026: 0.005, 2027: 0.010},
}
#: Les bornes des curseurs, en pour cent : au-delà, la trajectoire de référence (la
#: dépense gelée en volume, les recettes tenues en part du PIB) part loin de tout ce que
#: publient les comptes, et le coût, qui ne bouge pas avec elle, n'a plus de sens.
BORNES = {"croissance": (-0.5, 2.0), "prix": (0.0, 3.0)}
VUES = (("vieillie", "delta_aged", "vue vieillie"), ("figee", "delta_frozen", "vue figée"))
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


def pct(x: float, d: int = 2, signe: bool = False) -> str:
    """Une part (0,0188) en pour cent (1,88 %)."""
    return fr(100 * x, d, signe) + "\u202f%"


def pt(x: float, d: int = 2) -> str:
    """Un écart de ratio (0,0421) en points de PIB (+4,21 pt)."""
    return fr(100 * x, d, signe=True) + "\u202fpt"


def mds(x: float, d: int = 0) -> str:
    return fr(x / 1e9, d) + "\u202fMd€"


# --------------------------------------------------------------------------- #
# les fichiers lus
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def manifeste() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]


def publique(nom: str, texte: str) -> str:
    """Le lien public d'un fichier du manifeste des données, par son URL relevée."""
    entree = manifeste().get(nom)
    if not entree or not entree.get("url"):
        raise ParcoursError(f"{nom} n'a pas d'URL au manifeste des données.")
    return source(entree["url"], texte)


def lire(chemin: str) -> Any:
    return json.loads((ROOT / chemin).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def etudes() -> tuple[dict[str, Any], ...]:
    """Les études présidentielles et leur rapport prédictif commité, Attal d'abord."""
    out = []
    for definition in sorted(ETUDES.glob("presidentielle_*.json")):
        etude = json.loads(definition.read_text(encoding="utf-8"))
        nom = etude["nom"]
        for scenario in etude["scenarios"]:
            chemin = f"reports/etudes/{nom}/predictif_{scenario['scenario']}.json"
            if not (ROOT / chemin).exists():
                raise ParcoursError(f"{nom} : {chemin} manque ; la page ne lit que des "
                                    f"rapports commités.")
            data = lire(chemin)
            if not data.get("rejeu") or not data.get("lectures"):
                raise ParcoursError(f"{chemin} ne porte ni `rejeu` ni `lectures` : écrit "
                                    f"avant D-349, il ne se rejoue pas ici.")
            out.append({"nom": nom, "candidat": etude["titre"].split(" :")[0],
                        "chemin": chemin, "page": f"{nom}.html", "data": data})
    out.sort(key=lambda e: (e["nom"] != PREMIERE, e["nom"]))
    if not out or out[0]["nom"] != PREMIERE:
        raise ParcoursError(f"l'étude {PREMIERE} manque.")
    return tuple(out)


def lue(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Δb chaque année sous la persistance lue, le chiffre de tête (D-336)."""
    for path in data["side_by_side"]:
        if path["persistence"] == LUE:
            return path["years"]
    raise ParcoursError(f"{data['scenario']} : aucun chemin sous la persistance « lue ».")


def depart() -> dict[str, float]:
    """Le départ de 2025, le même pour toutes les études ; refusé s'il ne l'est pas."""
    starts = {json.dumps(e["data"]["rejeu"]["start"], sort_keys=True) for e in etudes()}
    if len(starts) != 1:
        raise ParcoursError("les études ne partent pas du même 2025 : la série est mêlée.")
    return etudes()[0]["data"]["rejeu"]["start"]


def charge(data: dict[str, Any]) -> dict[str, Any]:
    """Ce que le rejeu lit d'un rapport, et rien d'autre : `rejeu`, puis par année le coût
    des deux vues, les canaux et les impulsions (`rejouer.chemin`)."""
    rejeu = {k: data["rejeu"][k] for k in ("start", "cadre", "looped", "behavioural",
                                          "lignes", "macro", "box_rows")}
    years = []
    for row in data["years"]:
        stats = {view: {"canaux": row["statistiques"][view].get("canaux"),
                        "impulses": row["statistiques"][view]["impulses"]}
                 for view in ("vieillie", "figee")}
        years.append({"year": row["year"], "mechanical_aged_eur": row["mechanical_aged_eur"],
                      "mechanical_frozen_eur": row["mechanical_frozen_eur"],
                      "statistiques": stats})
    return {"rejeu": rejeu, "years": years}


def central(data: dict[str, Any]) -> dict[str, Any]:
    """Les nombres du rapport au cadre central, que la page affiche et que le rejeu doit
    redonner : Δb par année et par vue, la décomposition, le taux de marché."""
    rows = lue(data)
    lectures = data["lectures"]
    if lectures["persistence"] != LUE:
        raise ParcoursError(f"{data['scenario']} : lectures sous « {lectures['persistence']} ».")
    dernier = rows[-1]
    for view, key, _ in VUES:
        if dernier[key] != lectures["decomposition"][view]["total"]:
            raise ParcoursError(f"{data['scenario']} : la décomposition ne redonne pas Δb "
                                f"({view}) ; le rapport n'est pas d'une seule passe.")
    return {"annees": [r["year"] for r in rows],
            "delta": {view: [r[key] for r in rows] for view, key, _ in VUES},
            "reference": [r["reference"] for r in data["years"]],
            "decomposition": lectures["decomposition"],
            "taux_marche": lectures["taux_marche"]}


# --------------------------------------------------------------------------- #
# la page
# --------------------------------------------------------------------------- #
REGLES = {"gele_en_volume": "gelée en volume : elle suit les prix, pas la croissance réelle",
          "part_pib_constante": "constante en part du PIB",
          "personnalise": "une croissance nominale choisie"}


def _depart_html(start: dict[str, float], data: dict[str, Any]) -> str:
    rows = [
        ("la dette publique (au sens de Maastricht)", pct(start["debt_ratio"]) + " du PIB",
         publique("insee_dette_maastricht_detail.xlsx", "Insee, dette de Maastricht des APU")),
        ("le PIB en valeur", mds(start["gdp_eur"]),
         publique("insee_cn2025_pib_T1101_1103.xlsx", "Insee, comptes nationaux, T_1101")),
        ("le taux implicite net : les intérêts nets payés en 2025 sur la dette de fin 2024",
         pct(start["implicit_rate"], 3),
         publique("insee_cn2025_t7301_compte_administrations_publiques_S13.xlsx",
                  "Insee, compte des APU, tableau 7.301 (D41)")),
        ("les recettes primaires (hors intérêts reçus)", pct(start["receipts_ratio"]) + " du PIB",
         publique("insee_cn2025_t3201_depenses_recettes_APU_S13.xlsx",
                  "Insee, dépenses et recettes des APU, tableau 3.201")),
        ("les dépenses primaires (hors intérêts payés)", pct(start["spending_ratio"]) + " du PIB",
         publique("insee_cn2025_t3201_depenses_recettes_APU_S13.xlsx",
                  "Insee, tableau 3.201")),
        ("le solde primaire : recettes moins dépenses", pct(start["primary_balance"], 2, True)
         + " du PIB", "la différence des deux lignes au-dessus"),
    ]
    body = "".join(f'<tr><td>{esc(a)}</td><td class="num">{b}</td><td>{c}</td></tr>'
                   for a, b, c in rows)
    return (f'<h2 id="depart">Le départ : {start["year"]}, publié</h2>\n'
            "<p>Toute trajectoire part de la dernière année que les comptes nationaux ont "
            "publiée. Rien n'y est prévu ni extrapolé : ce sont des comptes.</p>\n"
            "<table><thead><tr><th>en " + str(start["year"]) + "</th><th>valeur</th>"
            "<th>source publique</th></tr></thead><tbody>" + body + "</tbody></table>\n"
            f"<p>Ces nombres sont lus par {fichier('src/impots/dette/reference.py')} "
            f"(<code>start_from_accounts</code>) dans les fichiers que "
            f"{fichier('src/impots/dette/comptes.py')} ouvre ; ils sont écrits dans chaque "
            f"rapport d'étude (<code>rejeu.start</code>, par exemple "
            f"{fichier(etudes()[0]['chemin'], 'le rapport d’Attal')}). Le taux implicite "
            "est un taux net : les intérêts que les administrations publiques paient, moins "
            "ceux qu'elles reçoivent, sur la dette de fin d'année précédente.</p>")


def _formule_html() -> str:
    return (
        '<h2 id="formule">La formule, en une ligne</h2>\n'
        "<p>Chaque année <var>t</var>, en part du PIB :</p>\n"
        '<p class="formule"><code>d(t) = d(t−1) × (1 + r) / (1 + g) − (s(t) + φ(t))</code>'
        '<br><code>Δb(t) = (b(t) + d(t)) / (1 + y(t)) − b(t)</code></p>\n'
        "<ul>\n"
        "<li><code>d</code> est la dette que la réforme ajoute, nulle avant elle ;</li>\n"
        "<li><code>r</code> est le taux auquel cette dette ajoutée est payée ;</li>\n"
        "<li><code>g</code> est la croissance nominale : (1 + croissance réelle) × "
        "(1 + prix) − 1 ;</li>\n"
        "<li><code>s</code> est le solde primaire de la réforme : les recettes qu'elle "
        "apporte moins ce qu'elle coûte, après les comportements, rapporté au PIB de "
        "l'année ;</li>\n"
        "<li><code>φ</code> est ce que l'activité rend au solde : les recettes induites "
        "quand le PIB monte, lues dans le modèle Mésange de l'Insee "
        f"({publique('insee_G2017-04_mesange.pdf', 'Insee, document de travail G2017/04')}"
        f", page {lien('activite')}) ;</li>\n"
        "<li><code>y</code> est l'écart de PIB que la réforme crée : le ratio se lit sur "
        "un PIB plus haut, c'est le dénominateur ;</li>\n"
        "<li><code>b</code> est la dette de référence, sans la réforme, qui suit la même "
        "identité : <code>b(t) = b(t−1) × (1 + r) / (1 + g) − (recettes − dépenses "
        "primaires)</code>.</li>\n"
        "</ul>\n"
        f"<p>C'est tout. La formule est dans {fichier('src/impots/predictif/rejouer.py')} "
        "(<code>chemin</code> et <code>reference_path</code>), écrite à part de la chaîne "
        f"qui fait les études ({fichier('src/impots/predictif/chaine.py')}) et tenue égale "
        "à elle par les tests (D-337). Aucune de ces lignes ne contient de "
        "comportement caché : le modèle est dans <code>s</code> (les comportements, page "
        f"{lien('comportements')}) et dans <code>φ</code> et <code>y</code> (l'activité), "
        "pas dans la dette.</p>")


def _reference_html(e: dict[str, Any], cadre: dict[str, Any], c: dict[str, Any]) -> str:
    data = e["data"]
    rejeu = data["rejeu"]["cadre"]
    rows = "".join(
        f'<tr><td>{y}</td><td class="num">{pct(b)}</td></tr>'
        for y, b in zip(c["annees"], c["reference"], strict=True))
    return (
        '<h2 id="reference">La trajectoire de référence, sans réforme</h2>\n'
        "<p>Les études chiffrent un écart à une trajectoire sans réforme. Celle-ci "
        "suit quatre hypothèses déclarées dans le cadre commun des études "
        f"({fichier(CADRE)}) :</p>\n<ul>\n"
        f"<li>croissance réelle {pct(rejeu['growth']['real'], 1)} et prix "
        f"{pct(rejeu['growth']['prices'], 1)} par an ;</li>\n"
        f"<li>dépense primaire {esc(REGLES[rejeu['spending']['rule']])} ;</li>\n"
        "<li>recettes constantes en part du PIB ;</li>\n"
        f"<li>taux implicite tenu à son niveau de {data['start']['year']}, "
        f"{pct(rejeu['taux']['marginal'], 3)}, pour toute la dette.</li>\n</ul>\n"
        "<p>Ces valeurs sont <strong>déclarées, pas prévues</strong> : aucune n'est lue "
        "dans une prévision officielle. Le gouvernement publie les siennes avec le projet "
        f"de loi de finances ({publique('plf2027_texte_an_b3210.html', 'PLF 2027, texte n° 3210')}"
        ") ; elles ne nourrissent pas la référence, qui leur est comparée plus bas, et le "
        "curseur permet de mettre les vôtres. Sous ce cadre, la dépense gelée en "
        "volume perd chaque année sa part de croissance réelle, et la dette de référence "
        "baisse :</p>\n"
        "<table><thead><tr><th>année</th><th>dette de référence, en % du PIB</th></tr>"
        f"</thead><tbody>{rows}</tbody></table>\n"
        f"<p>Lue dans la trajectoire de référence du rapport ({fichier(e['chemin'])})"
        " ; c'est la même pour toutes les études, qui partagent ce cadre.</p>\n"
        + _gouvernement_html(data, c))


def _gouvernement_html(data: dict[str, Any], c: dict[str, Any]) -> str:
    """La référence contre la trajectoire que le gouvernement publie avec le PLF 2027."""
    g = PLF2027
    ref = dict(zip(c["annees"], c["reference"], strict=True))
    communes = [y for y in g["annees"] if y in ref]
    if not communes:
        raise ParcoursError("la référence et le PLF 2027 n'ont aucune année commune.")
    gov = dict(zip(g["annees"], g["dette"], strict=True))
    vol = dict(zip(g["annees"], g["depense_volume"], strict=True))
    start = data["start"]
    if abs(start["debt_ratio"] - gov[start["year"]]) > 0.0006:
        raise ParcoursError("le départ des études n'est plus la dette de 2025 du PLF 2027.")
    comparaison = " ; ".join(
        f"en {y}, {pct(gov[y])} pour le gouvernement, {pct(ref[y])} pour la référence, "
        f"{fr((gov[y] - ref[y]) * 100, 1)} points de moins" for y in communes)
    texte = publique(g["fichier"], "PLF 2027, texte n° 3210, article liminaire et exposé "
                                   "général des motifs")
    return (
        "<p><strong>Un cadre déclaré, plus favorable que celui du gouvernement.</strong> "
        f"Partant du même {pct(start['debt_ratio'])} de {start['year']}, le gouvernement "
        f"prévoit une dette qui monte ({texte}) : {comparaison}. La référence ne lui "
        "ressemble pas parce qu'elle gèle la dépense primaire en volume, quand le PLF 2027 "
        "prévoit une dépense publique (hors crédits d'impôt) en hausse en volume de "
        + " et ".join(f"{pct(vol[y], 1)} en {y}" for y in communes)
        + " ; et elle suppose une croissance réelle de "
        f"{pct(data['rejeu']['cadre']['growth']['real'], 1)} par an, quand le PLF 2027 en "
        "prévoit "
        + " et ".join(f"{pct(v, 1)} en {y}" for y, v in g["croissance"].items())
        + ". Le gouvernement ne publie pas, avec ce texte, de trajectoire au-delà de "
        f"{g['annees'][-1]}. La référence n'est pas une prévision : elle fixe le niveau "
        "dont part chaque étude, et ne touche l'écart qu'une étude chiffre que par le "
        "dénominateur (le PIB que la réforme fait bouger, appliqué à une dette de "
        "référence plus basse).</p>\n")


def _marches_html() -> str:
    taux = central(etudes()[0]["data"])["taux_marche"]["taux"]
    head = ("<tr><th>étude</th><th>Δb en 2035 sans boucle : le coût, sans effet sur "
            "l'activité</th><th>le dénominateur</th><th>les recettes induites</th>"
            f"<th>Δb en 2035 avec la boucle, à θ½</th><th>dette ajoutée à {pct(taux, 1)}</th></tr>")
    rows = []
    for e in etudes():
        c = central(e["data"])
        d = c["decomposition"]["vieillie"]
        rows.append(
            f'<tr><td><a href="{esc(e["page"])}">{esc(e["candidat"])}</a></td>'
            f'<td class="num"><strong>{pt(d["cout"])}</strong></td>'
            f'<td class="num">{pt(d["denominateur"])}</td>'
            f'<td class="num">{pt(d["retroaction"])}</td><td class="num"><strong>'
            f'{pt(d["total"])}</strong></td>'
            f'<td class="num">{pt(c["taux_marche"]["vieillie"])}</td></tr>')
    attal = central(etudes()[0]["data"])["decomposition"]["vieillie"]
    return (
        '<h2 id="marches">Trois marches, du coût à la dette</h2>\n'
        "<p>L'écart de dette en 2035 se lit en trois marches qui s'additionnent "
        "exactement (D-349). <strong>Le coût</strong> : la dette qu'ajoute la réforme, "
        "comportements compris, si l'activité ne bougeait pas. <strong>Le "
        "dénominateur</strong> : la même dette rapportée à un PIB que la réforme a fait "
        "monter (ou baisser). <strong>Les recettes induites</strong> : ce que ce PIB plus "
        "haut rend en impôts et cotisations, chaque année, et qui ne s'emprunte donc pas. "
        f"Pour {esc(etudes()[0]['candidat'])}, {pt(attal['cout'])} de coût deviennent "
        f"{pt(attal['total'])} : l'écart entre les deux nombres tient entier à l'effet "
        "sur l'activité, le maillon le moins sûr de la chaîne.</p>\n"
        "<table><thead>" + head + "</thead><tbody>" + "".join(rows) + "</tbody></table>\n"
        "<p>Les deux nombres en gras se lisent ensemble : le premier ne dépend d'aucun "
        "modèle de l'activité, le second dépend de Mésange et de θ. Vue vieillie, θ½ (chaque réponse au milieu de sa fourchette publiée), "
        "persistance « lue ». La dernière colonne charge la seule dette ajoutée au "
        f"taux de {pct(taux, 1)} au lieu du taux implicite. Lu dans "
        "<code>lectures.decomposition</code> et <code>lectures.taux_marche</code> de "
        "chaque rapport, que "
        f"{fichier('src/impots/predictif/annuel.py')} écrit par "
        "<code>rejouer.decomposition</code>. Le coût seul se compare d'une étude à "
        "l'autre : c'est la même identité pour toutes. Les deux marches suivantes "
        "dépendent des instruments que la boucle sait lire (page "
        f"{lien('activite')}).</p>")


def plage(cle: str) -> tuple[float, float]:
    """La plage que le PLF 2026 publie pour 2025 à 2029, du plus bas au plus haut."""
    return min(RESF[cle]), max(RESF[cle])


def _plages_html(cadre: dict[str, Any]) -> str:
    g, p = plage("pib_volume"), plage("deflateur")
    real, prices = cadre["growth"]["real"], cadre["growth"]["prices"]
    hors = []
    if not g[0] <= real <= g[1]:
        hors.append(f"la croissance réelle ({pct(real, 1)})")
    if not p[0] <= prices <= p[1]:
        hors.append(f"les prix ({pct(prices, 1)})")
    centre = ("Le cadre des études est dans ces plages." if not hors else
              "Le cadre des études lui-même en sort par " + " et ".join(hors) + " : c'est "
              "une hypothèse déclarée (D-289), pas une prévision, et la page le dit.")
    return (
        "<p><strong>Les plages publiées.</strong> Le rapport économique annexé au PLF 2027 "
        "n'est pas dans les données du dépôt (le manifeste, "
        f"{fichier('data/raw/MANIFEST.json')}, ne le porte pas) ; le texte du PLF 2027 ne "
        "donne la croissance que pour 2026 et 2027 (plus haut). Les plages "
        "pluriannuelles les plus récentes que le dépôt lit sont donc celles du PLF 2026. "
        "Le gouvernement y publie "
        f"une croissance du PIB en volume de {pct(g[0], 1)} à {pct(g[1], 1)} par an et un "
        f"déflateur du PIB de {pct(p[0], 1)} à {pct(p[1], 1)} pour {RESF['annees'][0]} à "
        f"{RESF['annees'][-1]} ("
        + publique(RESF["fichier"], f"rapport économique, social et financier 2026, tableau 1 "
                                    f"p. {RESF['page']}")
        + f"). {centre} Le curseur va de {fr(BORNES['croissance'][0], 1)} à "
        f"{fr(BORNES['croissance'][1], 1)} % pour la croissance et de "
        f"{fr(BORNES['prix'][0], 1)} à {fr(BORNES['prix'][1], 1)} % pour les prix ; hors des "
        "plages publiées, la page le signale. Loin d'elles, la dette de référence "
        "change beaucoup (la dépense gelée en volume perd ou gagne sa part de croissance "
        "chaque année), quand le coût de la mesure, lui, ne bouge pas : le rejeu ne refait "
        "pas le vieillissement des revenus de la passe.</p>\n")


def _curseurs_html(e0: dict[str, Any], c0: dict[str, Any]) -> str:
    cadre = e0["data"]["rejeu"]["cadre"]
    real, prices = cadre["growth"]["real"], cadre["growth"]["prices"]
    taux = c0["taux_marche"]["taux"]
    options = "".join(
        f'<option value="{i}"{" selected" if i == 0 else ""}>{esc(e["candidat"])}</option>'
        for i, e in enumerate(etudes()))
    regles = "".join(
        f'<option value="{k}"{" selected" if k == cadre["spending"]["rule"] else ""}>'
        f"{esc(v)}</option>" for k, v in REGLES.items())

    def curseur(ident: str, texte: str, mini: float, maxi: float, valeur: float) -> str:
        return (f'<div class="curseur"><label for="{ident}">{esc(texte)}</label>'
                f'<input type="range" id="{ident}" min="{mini}" max="{maxi}" step="0.1" '
                f'value="{round(100 * valeur, 6)}"><output id="{ident}-v" for="{ident}">'
                f"{pct(valeur, 1)}</output></div>")

    return (
        '<h2 id="curseurs">À vous : changer le cadre</h2>\n'
        "<p>Le navigateur rejoue ici la chaîne d'un rapport, année par année, par la même "
        f"arithmétique que {fichier('src/impots/predictif/rejouer.py')} "
        f"({fichier('src/impots/parcours/js/dette.js')}). Aux valeurs de départ, il "
        "redonne les nombres du tableau au-dessus ; un test le vérifie pour chaque "
        "étude.</p>\n"
        + _plages_html(cadre)
        + "<noscript><p><strong>Sans JavaScript</strong>, les curseurs ne bougent pas : les "
        "tableaux de cette page sont ceux des rapports, au cadre central.</p></noscript>\n"
        '<div id="d-curseurs">\n'
        f'<div class="curseur"><label for="d-etude">l\'étude</label><select id="d-etude">'
        f"{options}</select><span></span></div>\n"
        + curseur("d-croissance", "la croissance réelle, par an", *BORNES["croissance"], real)
        + "\n"
        + curseur("d-prix", "les prix, par an", *BORNES["prix"], prices) + "\n"
        + '<div class="curseur"><label for="d-taux">le taux de la dette ajoutée</label>'
        '<select id="d-taux">'
        f'<option value="implicite" selected>implicite de 2025, '
        f'{pct(cadre["taux"]["marginal"], 2)}</option>'
        f'<option value="marche">taux de marché déclaré, {pct(taux, 1)}</option>'
        "</select><span></span></div>\n"
        '<div class="curseur"><label for="d-regle">la dépense primaire</label>'
        f'<select id="d-regle">{regles}</select><span></span></div>\n'
        + curseur("d-depense", "sa croissance nominale, si elle est choisie", 0, 6, prices)
        + "\n"
        '<p><button type="button" id="d-retour">revenir au cadre des études</button></p>\n'
        '<p id="d-tete" aria-live="polite"></p>\n'
        '<p id="d-alerte" role="status"></p>\n'
        '<table><thead><tr><th>marche, vue vieillie, 2035</th><th>ce cadre</th>'
        '<th>le rapport</th></tr></thead><tbody id="d-marches"></tbody></table>\n'
        '<table><thead><tr><th>année</th><th>PIB</th><th>dette de référence</th>'
        '<th>Δb, vue vieillie</th><th>Δb, vue figée</th></tr></thead>'
        '<tbody id="d-annees"></tbody></table>\n'
        "</div>\n")


def _limites_html(e0: dict[str, Any], c0: dict[str, Any]) -> str:
    data = e0["data"]
    cadre = lire(CADRE)
    taux = c0["taux_marche"]["taux"]
    return (
        '<h2 id="ce-que-le-curseur-ne-refait-pas">Ce que le curseur ne refait pas</h2>\n'
        "<ul>\n"
        "<li><strong>Changer la croissance ou les prix ne refait pas le vieillissement des "
        "revenus de la passe.</strong> Le coût de chaque année, en euros, vient de la "
        "simulation de la population, où les salaires ont été vieillis à "
        f"{pct(cadre['uprating']['wage'], 0)} par an sous la loi reconduite : "
        f"« {esc(data['uprating_note'].split('. ')[0])}. » Le curseur change le PIB qui "
        "divise ce coût, la dette de référence et l'intérêt de la dette ajoutée ; il ne "
        "refait pas la population. Une croissance plus forte devrait aussi grossir les "
        "revenus taxés, et donc le coût d'une baisse d'impôt : la page ne le fait pas, et "
        "le nombre qu'elle donne loin du cadre central est donc un ordre de grandeur.</li>\n"
        "<li><strong>Le taux de marché est déclaré, pas lu.</strong> Les études gardent le "
        "taux implicite de 2025 pour la dette ajoutée (D-336). Le "
        f"{pct(taux, 1)} est une sensibilité déclarée (D-349), un ordre de grandeur de "
        "l'OAT à dix ans que le dépôt ne lit dans aucun fichier de taux. L'Agence France "
        f"Trésor publie les taux et la dette négociable "
        f"({publique('aft_bulletin_mensuel_435_aout_2026.pdf', 'AFT, bulletins mensuels')}"
        ") ; un taux de marché sur toute la dette demande l'échéancier des titres, que le "
        "rapport ne porte pas. Le curseur ne charge que la dette ajoutée à ce taux, comme "
        "la lecture du rapport ; la dette de référence garde l'implicite.</li>\n"
        "<li><strong>Rien ne réagit à la dette.</strong> La dépense suit sa règle, quelle "
        "que soit la dette ; aucun taux ne monte quand la dette monte.</li>\n"
        "<li><strong>θ et l'activité restent au centre.</strong> Les comportements sont "
        "au milieu de leur fourchette, le multiplicateur à son centre Mésange ; les faire "
        f"varier, c'est la page {lien('verdict')}.</li>\n"
        "</ul>")


def page() -> Page:
    liste = etudes()
    start = depart()
    e0 = liste[0]
    c0 = central(e0["data"])
    cadre = lire(CADRE)
    donnees = {
        "taux_marche": c0["taux_marche"]["taux"],
        "plages": {"croissance": plage("pib_volume"), "prix": plage("deflateur"),
                   "annees": [RESF["annees"][0], RESF["annees"][-1]]},
        "etudes": [{"candidat": e["candidat"], "chemin": e["chemin"],
                    "payload": charge(e["data"]), "rapport": central(e["data"])}
                   for e in liste],
    }
    corps = "\n".join([
        f"<p>La dette en 2035 est le dernier des trois nombres de chaque étude, et le "
        "moins sûr. Pourtant le calcul qui la fait n'est pas un modèle : c'est une identité "
        "comptable, la même pour toutes les études, sous des hypothèses qu'on peut nommer "
        "une à une. Cette page la montre sur les rapports commités des "
        f"{len(liste)} études présidentielles, {esc(e0['candidat'])} d'abord.</p>",
        _depart_html(start, e0["data"]),
        _formule_html(),
        _reference_html(e0, cadre, c0),
        _marches_html(),
        _curseurs_html(e0, c0),
        _limites_html(e0, c0),
    ])
    script = ("var PARCOURS_DETTE = "
              + json.dumps(donnees, ensure_ascii=False).replace("<", "\\u003c") + ";\n"
              + (JS / "dette.js").read_text(encoding="utf-8"))
    return Page(prouve="la dette est une identité comptable, et chacune de ses hypothèses "
                       "se nomme.",
                corps=corps, script=script,
                style="p.formule code{font-size:1em}#d-tete{font-weight:600}")
