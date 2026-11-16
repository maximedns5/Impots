"""Les pages « cascade » du site (but 26, volet `cascade`, D-484) : l'effet papillon d'une
mesure, de son levier aux agrégats, année par année.

    cascade.html                    # le choix : un candidat, puis une mesure ou le programme
    cascade-<candidat>.html         # un programme (sa part chiffrée), comme un tout
    cascade-<candidat>-<mesure>.html  # une mesure seule
    cascade-<scénario>.html         # un volet d'un texte (PLF, PLFSS)
    cascade.js                      # le dessin, et le calcul quand le lecteur bouge θ

LE GRAPHE EST CELUI DU JUMEAU. Chaque page porte, en JSON, le graphe que
`jumeau.cascade.calculer` tire de la trajectoire de la mesure à θ½ (le même que la page du
jumeau fait tourner), dans le mode qui la calcule : le mode structurel quand il calcule au
moins une année (sur la population figée, avec la convention des parts de la première
année, D-414), sinon la chaîne des études (le mode réduit, sur la vieillie), et la page
dit pourquoi. Quand le lecteur bouge θ, la page charge Pyodide et le paquet du jumeau
(`jumeau-paquet.json`, `jumeau-donnees.json`, le Worker `jumeau-calcul.js`) et refait le
graphe avec le même code : aucun portage.

CE QUE LA PAGE AJOUTE AU GRAPHE, sans calcul : le texte de la mesure et sa source
(`programmes/<candidat>.json`), sa fiche de transmission si le volet `carte` l'a écrite
(D-471), et les premiers chiffres de la passe sur la population (le rapport de première
année commité). Un canal que la mesure devrait ouvrir et qu'aucun bloc ne porte est dit
« pas encore modélisé », sans nombre.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from impots import etude

ICI = Path(__file__).resolve().parent
INDEX, SCRIPT = "cascade.html", "cascade.js"
#: Le premier exemple du but 26 (D-471), en tête de la liste et dans le chemin.
EXEMPLE = "pres2027_attal_a16_droit_au_brut"
#: Les champs de la passe sur la population, en mots, en plus de ceux de la page d'une
#: mesure (`site_mesure.CHAMPS_LUS`).
CHAMPS = {"salaire_net": "salaires nets", "salaire_super_brut": "coût du travail "
          "(super-brut)", "salaire_imposable": "salaires imposables",
          "revenu_disponible": "revenu disponible des ménages",
          "prelevements_salaires_d291": "taxe sur les salaires",
          "pension_employeur_etat": "pensions des fonctionnaires (part employeur)",
          "csg_chomage": "CSG des chômeurs"}
#: Des totaux de la passe qui en somment d'autres, et les droits (avant non-recours).
TOTAUX = {"revenu_disponible_droit", "ir_avant_niches", "rsa_droit", "ppa_droit",
          "aefa_droit", "crds_mini_droit"}


class CascadeSiteError(ValueError):
    """Les pages de la cascade ne se construisent pas comme elles le promettent."""


def _e(x: Any) -> str:
    return html.escape(str(x), quote=True)


# --------------------------------------------------------------------------- #
# les pages : un scénario de rapport, son adresse, sa mesure
# --------------------------------------------------------------------------- #
def nom_page(scenario: str, slug: str | None, mesure: str | None) -> str:
    if slug and mesure:
        return f"cascade-{slug}-{mesure}.html"
    if slug:
        return f"cascade-{slug}.html"
    return f"cascade-{scenario}.html"


def lien(scenario: str) -> str:
    """L'adresse de la cascade d'un scénario de rapport (le `name` d'une mesure seule ou
    d'un programme) : la page d'une mesure s'en sert, sous `si-page`."""
    return entrees().get(scenario, {}).get("page", "")


def entrees() -> dict[str, dict[str, Any]]:
    """{scénario : {page, candidat, slug, mesure, mesures}} pour chaque rapport que la
    page du jumeau lit (`site_jumeau.candidats`), dans le même ordre."""
    from impots import programmes

    out: dict[str, dict[str, Any]] = {}
    for study in etude.definitions():
        if study.refus or not study.page.exists():
            continue
        if study.programme:
            p = programmes.charger(study.programme)
            chiffrees = p.chiffrees()
            seule = chiffrees[0].id if len(chiffrees) == 1 else None
            sc = study.volets[0].scenario
            out[sc] = {"page": nom_page(sc, p.slug, None), "candidat": p.candidat,
                       "slug": p.slug, "mesure": seule,
                       "mesures": [m.id for m in chiffrees], "etude": study.nom}
            for m in study.mesures:
                out[m.scenario] = {"page": nom_page(m.scenario, p.slug, m.mesure),
                                   "candidat": p.candidat, "slug": p.slug,
                                   "mesure": m.mesure, "mesures": [m.mesure],
                                   "etude": study.nom}
        else:
            for v in study.volets:
                out[v.scenario] = {"page": nom_page(v.scenario, None, None),
                                   "candidat": study.titre, "slug": None, "mesure": None,
                                   "mesures": [], "etude": study.nom}
    return out


def _mesure_programme(slug: str | None, ident: str | None) -> dict[str, Any] | None:
    """Le texte d'une mesure dans son programme : libellé, paramètre, levier (les
    paramètres du moteur), note et sources."""
    if not (slug and ident):
        return None
    chemin = etude.ROOT / "programmes" / f"{slug}.json"
    if not chemin.exists():
        return None
    p = json.loads(chemin.read_text(encoding="utf-8"))
    m = next((x for x in p["mesures"] if x.get("id") == ident), None)
    if m is None:
        return None
    ch = m.get("chiffrage") or {}
    return {"id": ident, "libelle": m.get("libelle"), "parametre": m.get("parametre"),
            "levier": ch.get("reforme"), "couche": ch.get("couche"), "note": ch.get("note"),
            "sources": [{"citation": s.get("citation"), "url": s.get("url"),
                         "date": s.get("date")} for s in (m.get("sources") or [])[:2]],
            "fichier": f"programmes/{slug}.json"}


def _premiere(c: dict[str, Any], rapport: str) -> list[dict[str, Any]]:
    """Les premiers chiffres de la passe sur la population (le rapport de première année
    commité) : les huit plus gros champs changés, en Md€, avec leur libellé."""
    from impots.site_mesure import CHAMPS_LUS

    pa = c.get("premiere_annee")
    if not pa:
        return []
    rep = pa["response"]
    parts = ({"menages": rep} if pa.get("kind") == "menages" else
             {"entreprises": rep} if pa.get("kind") == "entreprises" else rep)
    out = []
    for qui, r in parts.items():
        for k, v in (r.get("deltas") or {}).items():
            if v is None or k in TOTAUX or k.endswith("_droit") or abs(float(v)) < 5e7:
                continue
            out.append({"qui": qui, "champ": k, "libelle": CHAMPS.get(k, CHAMPS_LUS.get(
                k, k.replace("_", " "))), "md": float(v) / 1e9})
    out.sort(key=lambda d: -abs(d["md"]))
    rapport_pa = rapport.replace("predictif_", "premiere_annee_")
    return [{**d, "source": f"{rapport_pa}, response.deltas.{d['champ']}",
             "commit": pa.get("commit")} for d in out[:8]]


# --------------------------------------------------------------------------- #
# le calcul, une fois, à θ½
# --------------------------------------------------------------------------- #
def reglage(session: Any, cle: str) -> tuple[dict[str, Any], str | None]:
    """Le réglage d'une cascade : le mode structurel s'il calcule une année au moins (sur
    la figée, avec la convention de D-414), sinon la chaîne des études ; et pourquoi."""
    from impots import site_jumeau
    from impots.jumeau.mesures import CONVENTION_PARTS

    k, _refus = session.structurel(cle, "figee", CONVENTION_PARTS)
    if k:
        return ({"mode": "structurel", "vue": "figee", "candidat": cle,
                 "convention": CONVENTION_PARTS}, None)
    raison = site_jumeau.raison_structurel(session.mesure(cle, "figee", CONVENTION_PARTS),
                                           "figee")
    return {"mode": "reduit", "vue": "vieillie", "candidat": cle}, raison


def donnees() -> dict[str, dict[str, Any]]:
    """Pour chaque scénario : le réglage, le graphe à θ½, la mesure, sa fiche, ses premiers
    chiffres."""
    from impots import site_jumeau
    from impots.jumeau import cascade, navigateur

    d = site_jumeau.donnees()
    session = navigateur.Session(json.loads(json.dumps(d)))
    pages = entrees()
    out: dict[str, dict[str, Any]] = {}
    for cle, c in d["candidats"].items():
        e = pages.get(cle)
        if e is None:
            continue
        fiche = cascade.lire_fiche(e["slug"], e["mesure"])
        attendus = cascade.canaux_attendus(fiche)
        choix, pourquoi = reglage(session, cle)
        g = cascade.calculer(session, {**choix, "theta_commun": 0.5}, attendus)
        if not g["noeuds"]:
            raise CascadeSiteError(f"{cle} : aucune année calculée ({g.get('refus')})")
        out[cle] = {**e, "scenario": cle, "libelle": c["libelle"], "rapport": c["rapport"],
                    "choix": choix, "pourquoi_mode": pourquoi, "attendus": attendus,
                    "graphe": g, "fiche": fiche,
                    "mesure_texte": _mesure_programme(e["slug"], e["mesure"]),
                    "mesures_texte": [x for x in (_mesure_programme(e["slug"], i)
                                                  for i in e["mesures"]) if x]
                    if e["mesure"] is None else [],
                    "premiere": _premiere(c, c["rapport"])}
    return out


# --------------------------------------------------------------------------- #
# le HTML
# --------------------------------------------------------------------------- #
def _json_script(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _fr(x: float, d: int = 1) -> str:
    s = f"{abs(x):,.{d}f}".replace(",", " ").replace(".", ",")
    return ("−" if x < 0 and float(f"{abs(x):.{d}f}") else "+" if x > 0 else "") + s


def _tableau(g: dict[str, Any]) -> str:
    """Les agrégats, en tableau : lisible sans script, et au lecteur d'écran."""
    annees = g["annees"]
    tete = "".join(f"<th scope=\"col\">{a}</th>" for a in annees)
    lignes = []
    for nd in g["noeuds"]:
        if nd["type"] not in ("mesure", "agregat") or nd["statut"] != "calcule":
            continue
        dec = 0 if nd["unite"] == "milliers" else 2 if nd["unite"] in (
            "% du PIB", "points de PIB") else 1
        cells = "".join(f"<td>{'' if v is None else _fr(v, dec)}</td>"
                        for v in nd["valeurs"])
        lib = "Coût statique de la mesure" if nd["type"] == "mesure" else nd["libelle"]
        lignes.append(f'<tr><th scope="row">{_e(lib)} <small>({_e(nd["unite"])})</small>'
                      f"</th>{cells}</tr>")
    return ('<div class="defile"><table class="cascade-table"><thead><tr><th></th>'
            f"{tete}</tr></thead><tbody>{''.join(lignes)}</tbody></table></div>")


def _titre(x: dict[str, Any]) -> str:
    """Le nom court de la mesure : son libellé jusqu'au premier deux-points."""
    lib = (x["mesure_texte"]["libelle"] if x["mesure_texte"] else
           x["libelle"].split(" : ", 1)[-1])
    if x["mesure_texte"] is None and x["scenario"].endswith("_programme"):
        return f"le programme de {x['candidat']}"
    court = lib.split(" : ", 1)[0].strip()
    return court if court.startswith("«") else f"« {court} »"


def corps(x: dict[str, Any]) -> str:
    from impots import site_composants as sc
    from impots import site_jumeau

    g = x["graphe"]
    mode = ("le jumeau complet (mode structurel), sur la population figée" if
            x["choix"]["mode"] == "structurel" else
            "la chaîne des études (mode réduit), sur la population vieillie")
    pourquoi = (f'<p class="cascade-mode-raison"><b>Pourquoi pas le jumeau complet :</b> '
                f'{_e(x["pourquoi_mode"])}. Les canaux qu\'il détaillerait sont dits en gris.'
                f"</p>" if x["pourquoi_mode"] else "")
    mt = x["mesure_texte"]
    levier = ""
    if mt:
        src = mt["sources"][0] if mt["sources"] else None
        levier = (f'<p class="cascade-levier"><b>Ce que dit la mesure :</b> '
                  f'{_e(mt["parametre"])}'
                  + (f' — <a href="{_e(src["url"])}">sa source</a>' if src and src.get("url")
                     else "") + "</p>")
    fil = (f'<p class="sm-fil"><a href="{INDEX}">L\'effet papillon</a> &rsaquo; '
           f'{_e(x["candidat"])}</p>')
    mesure_page = (f'<span class="si-page" data-page="mesure-{_e(x["slug"])}-'
                   f'{_e(x["mesure"])}.html"> · <a href="mesure-{_e(x["slug"])}-'
                   f'{_e(x["mesure"])}.html">la mesure pas à pas</a></span>'
                   if x["slug"] and x["mesure"] else "")
    statique = {k: x[k] for k in ("scenario", "page", "candidat", "libelle", "rapport",
                                   "choix", "attendus", "mesure_texte", "mesures_texte",
                                   "premiere", "pourquoi_mode")}
    statique["fiche"] = x["fiche"]
    return f"""{fil}
<h1>Que déclenche {_e(_titre(x))} ?</h1>
<p class="chapeau">De gauche à droite : la mesure, qui paie ou reçoit d'abord, les canaux
par lesquels l'effet passe, puis ce qu'il fait au PIB, à l'emploi, au solde et à la dette.
Chaque flèche porte son nombre ; un clic sur une case dit pourquoi, et d'où vient le
nombre.</p>
{levier}
<div class="cascade-commandes" id="commandes" hidden>
  <div class="cascade-annees" role="group" aria-label="L'année">
    <button type="button" id="jouer" class="cascade-jouer" aria-label="Faire défiler les
années">▶</button>
    <div id="frise" class="cascade-frise"></div>
  </div>
  <div class="cascade-theta">
    <label for="theta">Combien l'économie répond : <output id="theta-v">½</output></label>
    <input type="range" id="theta" min="0" max="1" step="0.05" value="0.5"
      aria-describedby="theta-aide">
    <p id="theta-aide" class="cascade-aide">Tous les paramètres incertains ensemble, de la
réponse la plus faible (0) à la plus forte (1) que leurs sources publient ; ½ : leur
centre. Bouger le curseur charge le jumeau dans la page (une fois, quelques secondes).</p>
  </div>
  <label class="cascade-boucles"><input type="checkbox" id="boucles"> montrer les
boucles (les retours que le pas annuel résout)</label>
</div>
<p class="etat" id="etat" role="status" aria-live="polite"></p>
<div class="cascade-vue">
  <figure class="cascade-graphe" id="graphe" aria-label="La cascade, en graphe"></figure>
  <aside class="cascade-panneau" id="panneau" aria-live="polite" tabindex="-1">
    <p class="cascade-aide">Cliquer sur une case ou une flèche : son pourquoi, sa
source, ses nombres année par année.</p>
  </aside>
</div>
<div class="cascade-liste" id="liste"></div>
<noscript><p class="absent">Le graphe se dessine avec un script ; sans lui, les agrégats
sont dans le tableau ci-dessous.</p></noscript>
<p class="cascade-mode">Calculé par {mode}, à θ½, avec le code du dépôt ; rapport :
<code>{_e(x["rapport"])}</code>.{mesure_page} ·
<a href="jumeau.html">le jumeau, tous ses curseurs</a></p>
{pourquoi}
{sc.detail("Les agrégats en tableau, année par année", _tableau(g))}
{sc.detail("Ce que la cascade ne dit pas", _limites(x))}
<script type="application/json" id="cascade-graphe">{_json_script(g)}</script>
<script type="application/json" id="cascade-statique">{_json_script(statique)}</script>
<script src="{SCRIPT}" data-pyodide="{site_jumeau.PYODIDE_URL}"
  data-sri="{site_jumeau.PYODIDE_SRI}" data-calcul="{site_jumeau.CALCUL}"
  data-paquets="{" ".join(site_jumeau.PAQUETS_PYODIDE)}"></script>"""


def _limites(x: dict[str, Any]) -> str:
    fiche = ("" if x["fiche"] else
             "<li>La fiche de transmission de cette mesure (D-471 : son levier, ses payeurs, "
             "l'incidence à terme, son financement, ses hypothèses) n'est pas encore écrite ; "
             "les canaux attendus sont ceux de familles communes à toutes les mesures.</li>")
    return ("<ul>" + fiche +
            "<li>Les nombres sont ceux du jumeau, pas ceux que publie l'étude : la page de "
            "l'étude garde son chiffrage (D-469, R15).</li>"
            "<li>Un canal en gris n'a aucun nombre : il n'est pas dans le modèle, ou pas dans "
            "ce mode. Rien n'est estimé à sa place.</li>"
            "<li>Les flèches qui remontent (les boucles) sont résolues ensemble, chaque année, "
            "par le pas du jumeau : leurs nombres sont ceux du point fixe.</li></ul>")


STYLE = (ICI / "cascade.css").read_text(encoding="utf-8")


def page(x: dict[str, Any]) -> str:
    from impots import site, site_jumeau

    text = site._page(f"Que déclenche {_titre(x)} ? — {site.TITLE}", corps(x),
                      large=True)
    return (text.replace("</head>", f'<meta http-equiv="Content-Security-Policy" '
                                    f'content="{site_jumeau.CSP}">\n<style>{STYLE}</style>\n'
                                    "</head>", 1)
            .replace("rien n'y est calculé, rien n'y tourne.",
                     "rien n'y est calculé, sauf quand on bouge θ : le jumeau tourne alors "
                     "dans le navigateur."))


def index(tout: dict[str, dict[str, Any]]) -> str:
    from impots import site

    groupes: dict[str, list[dict[str, Any]]] = {}
    for x in tout.values():
        groupes.setdefault(x["candidat"], []).append(x)
    exemple = tout.get(EXEMPLE)
    items = []
    for cand, xs in groupes.items():
        xs.sort(key=lambda x: (x["mesure"] is not None and len(x["mesures"]) == 1
                               and x["scenario"].endswith("_programme"),
                               x["scenario"].endswith("_programme") is False))
        liens = "".join(
            f'<li><a href="{_e(x["page"])}">'
            + (_e("le programme, comme un tout") if x["scenario"].endswith("_programme")
               and len(x["mesures"]) != 1 else _e(x["mesure_texte"]["libelle"]
                                                  if x["mesure_texte"] else _titre(x)))
            + "</a></li>" for x in xs)
        items.append(f"<li><b>{_e(cand)}</b><ul>{liens}</ul></li>")
    tete = (f'<p class="boutons"><a class="bouton" href="{_e(exemple["page"])}">Le premier '
            f"exemple : le « droit au brut » de Gabriel Attal →</a></p>" if exemple else "")
    main = f"""<h1>Que déclenche une mesure ?</h1>
<p class="chapeau">Une mesure ne s'arrête pas à sa première ligne. Une cotisation en moins
monte le salaire net ; le net en plus se consomme ; la consommation fait de l'activité, de
l'emploi, des recettes ; le salaire brut se renégocie. Chaque page suit ce fil, année par
année, avec le jumeau.</p>
{tete}
<ul class="cascade-index">{"".join(items)}</ul>"""
    return site._page(f"L'effet papillon — {site.TITLE}", main, large=True)


def build() -> dict[str, str]:
    tout = donnees()
    files = {INDEX: index(tout), SCRIPT: (ICI / "page.js").read_text(encoding="utf-8")}
    for x in tout.values():
        files[x["page"]] = page(x)
    return files


def present() -> bool:
    from impots import site_jumeau

    return site_jumeau.present()
