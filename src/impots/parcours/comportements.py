"""Page 4 du parcours : les comportements.

Une bande comportementale vient d'un article publié, pas de l'outil : la page montre chaque
canal, les lignes du magasin qu'il lit (`behavioural/parameters/*.yaml`) avec leur article,
leur page et leur fourchette, la règle qui l'ouvre et la phrase du code quand il reste
fermé, les canaux ouverts ou fermés dans chaque étude publiée, et les lignes mortes avec
leur raison. Le curseur donne un θ par élasticité, au lieu du θ commun de l'explorateur,
et l'applique aux statistiques des canaux qu'un rapport d'étude porte : la recette d'un
canal est l'élasticité fois une somme que la passe a écrite (`rejouer.receipts`). Le
script (`js/comportements.js`, sur `js/activite.js`) rejoue cette arithmétique, et la dette
avec elle ; rien n'est chiffré de neuf.
"""

from __future__ import annotations

import html
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots import etude
from impots.behavioural import channels, store
from impots.parcours import ROOT, Page, ParcoursError, activite, fichier, lien, source
from impots.parcours.activite import fr, md, pt
from impots.predictif import rejouer

JS = Path(__file__).resolve().parent / "js"
PARAMETRES = "src/impots/behavioural/parameters"
VUE = "vieillie"
esc = html.escape

#: Les canaux dont la recette entre dans la dette, dans l'ordre de `rejouer.receipts`.
#: C2 n'y entre que par C11 ; un test tient cette liste contre la fonction du moteur.
RECETTES = ("c1_eti", "c7_labour_supply", "c10_dividendes", "c11_autofinancement")

#: Ce que fait chaque canal qui n'entre pas dans la dette, tel que `channels.py` le dit.
ROLES = {
    "c1_eti": "rend une recette, comptée dans la dette",
    "c2_employment": "compte des emplois, en personnes : un indice, qui n'entre dans la recette "
                     "que par C11",
    "c3_incidence": "partage une variation de cotisations entre salaires et employeurs ; le total "
                    "ne bouge pas, rien n'entre dans la dette",
    "c4_investment": "une bande d'investissement centrée sur zéro, hors de la dette",
    "c5_wealth_rate": "décroché : la population ne porte aucun patrimoine (D-336, décision 5)",
    "c6_disclosure": "décroché : la population ne porte aucun patrimoine (D-336, décision 5)",
    "c7_labour_supply": "rend une recette, comptée dans la dette",
    "c8_creations": "un indice de la couche entreprises, jamais une recette",
    "c9_rd": "un indice de la couche entreprises, jamais une recette",
    "c10_dividendes": "rend une recette, comptée dans la dette",
    "c11_autofinancement": "rend une recette, comptée dans la dette",
}


def _numero(cle: str) -> str:
    return "C" + cle.split("_")[0][1:]


# --------------------------------------------------------------------------- #
# le magasin
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def magasin() -> dict[str, Any]:
    """Les lignes du magasin, fichier par fichier, et les lignes retirées avec leur raison.
    Chaque ligne affichée est une ligne que `store.load` charge : sinon, refusé."""
    charge = store.load()
    lignes: dict[str, dict[str, Any]] = {}
    mortes: list[dict[str, str]] = []
    for path in sorted((ROOT / PARAMETRES).glob("*.yaml")):
        chemin = str(path.relative_to(ROOT))
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key, raw in (doc.get("parameters") or {}).items():
            if key not in charge:
                raise ParcoursError(f"{key} ({chemin}) n'est pas chargée par le magasin : la page "
                                    f"ne montre que ce qui se charge.")
            p = charge[key]
            lignes[key] = {"fichier": chemin, "p": p,
                           "page": " ".join(str((raw.get("source") or {}).get("citation", "")).split())}
        for key, reason in (doc.get("removed") or {}).items():
            mortes.append({"cle": key, "fichier": chemin, "raison": " ".join(str(reason).split())})
    return {"lignes": lignes, "mortes": mortes}


@lru_cache(maxsize=1)
def canaux() -> list[dict[str, Any]]:
    """Les onze canaux : leur clé, leur nom et leur phrase quand aucun levier ne les ouvre,
    tels que le code les rend à une réforme vide ; les lignes qu'ils lisent."""
    s = store.load()
    fonctions = {
        "c1_eti": lambda: channels.elasticity_of_taxable_income(
            s, None, emtr_baseline=None, emtr_reform=None, taxable_base=None, weights=None,
            top_decile=None, draws=1, rng=None),
        "c2_employment": lambda: channels.employment_at_the_smic(s, None),
        "c3_incidence": lambda: channels.contribution_incidence(s, None),
        "c4_investment": lambda: channels.production_tax_investment(s, None),
        "c5_wealth_rate": lambda: channels.wealth_rate_response(s, None),
        "c6_disclosure": lambda: channels.disclosure_response(s, None),
        "c7_labour_supply": lambda: channels.labour_supply(s, None),
        "c8_creations": lambda: channels.firm_creations(s, None),
        "c9_rd": lambda: channels.rd_response(s, None),
        "c10_dividendes": lambda: channels.dividend_response(s, None),
        "c11_autofinancement": lambda: channels.targeted_self_financing(s, None),
    }
    out = []
    for key, keys in channels.CHANNELS:
        if key not in fonctions:
            raise ParcoursError(f"canal {key} inconnu de la page")
        result = fonctions[key]()
        if result.key != key or result.applies:
            raise ParcoursError(f"{key} : la réforme vide l'ouvre, ou rend {result.key}")
        out.append({"cle": key, "numero": _numero(key), "label": result.label,
                    "ferme": result.message, "lignes": list(keys), "role": ROLES[key]})
    return out


# --------------------------------------------------------------------------- #
# les études : quels canaux s'ouvrent
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def ouvertures() -> list[dict[str, Any]]:
    """Par étude et par côté (ménages, entreprises), chaque canal ouvert ou fermé et sa
    phrase, la note de support et sa raison, lus dans le rapport de la première année."""
    out = []
    for path in sorted(activite.ETUDES.glob("*/premiere_annee_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        predictif = path.with_name(path.name.replace("premiere_annee_", "predictif_"))
        nom = (activite._nom(json.loads(predictif.read_text(encoding="utf-8")))
               if predictif.exists() else data["scenario"])
        r = data["response"]
        cotes = {"": r} if "behavioural" in r else {c: r[c] for c in ("menages", "entreprises")
                                                     if c in r}
        for cote, reponse in cotes.items():
            b = reponse["behavioural"]
            out.append({"nom": nom + (f" ({'ménages' if cote == 'menages' else cote})"
                                      if cote else ""),
                        "chemin": str(path.relative_to(ROOT)), "grade": b["grade"],
                        "raison": b["grade_reason"],
                        "canaux": {c["key"]: {"ouvert": bool(c["applies"]),
                                              "message": " ".join(c["message"].split())}
                                   for c in b["channels"]}})
    return out


# --------------------------------------------------------------------------- #
# les études dont le rapport porte les statistiques des canaux
# --------------------------------------------------------------------------- #
def avec_canaux() -> list[dict[str, Any]]:
    return [r for r in activite.rapports()
            if r["data"]["rejeu"]["behavioural"] and r["data"]["rejeu"]["lignes"]
            and all(y["statistiques"][VUE].get("canaux") for y in r["data"]["years"])]


def parts(row: dict[str, Any], values: dict[str, Any], vue: str = VUE) -> dict[str, float]:
    """La recette de chaque canal d'une année, par `rejouer.receipts` canal par canal, et
    les emplois de C2 ; la somme des recettes plus le mécanique est `rejouer.receipts`."""
    stats = row["statistiques"][vue]["canaux"] or {}
    out = {}
    for key in RECETTES:
        if key in stats:
            sous = {key: stats[key]}
            if key == "c11_autofinancement":
                sous["c2_employment"] = stats["c2_employment"]
            out[key] = float(rejouer.receipts(0.0, sous, values))
    if "c2_employment" in stats:
        c2 = stats["c2_employment"]
        out["emplois_c2"] = float(values["employment_elasticity_smic"] * c2["anchor"]
                                  + c2["tail"] + 0.0)
    return out


def _valeurs(data: dict[str, Any], theta: float) -> dict[str, Any]:
    values, _ = rejouer.theta_values(data, {**dict.fromkeys(data["rejeu"]["lignes"], theta),
                                            rejouer.MACRO_ROW: 0.5})
    return values


def apres(row: dict[str, Any], values: dict[str, Any], vue: str = VUE) -> float:
    """Le coût après comportements d'une année : le mécanique moins les recettes."""
    cout = float(row[rejouer.VIEWS[vue]])
    return -float(rejouer.receipts(-cout, row["statistiques"][vue]["canaux"], values))


# --------------------------------------------------------------------------- #
# la page
# --------------------------------------------------------------------------- #
def _fourchette(p: store.Parameter) -> str:
    if not p.is_open:
        return f"{fr(p.central, 4).rstrip('0').rstrip(',')}, fixe"
    vals = [fr(v, 4).rstrip("0").rstrip(",") for v in (p.low, p.central, p.high)]
    return " ; ".join(vals)


def _ligne(key: str, entry: dict[str, Any]) -> str:
    p: store.Parameter = entry["p"]
    citation = entry["page"].rstrip(". ")
    article = (source(p.source.url, citation) if p.source.url
               else f"<em>pas d'article</em> : {esc(citation)}")
    theta = ("" if not p.is_open else
             f" θ = 1 au {'haut' if p.theta_one == 'high' else 'bas'} : "
             f"{esc(p.theta_reason)}")
    leviers = ", ".join(p.responds_to_knobs) or "aucun"
    return (f'<li><p><code>{esc(key)}</code> — <strong class="num">{_fourchette(p)}</strong> '
            f"(bas ; centre ; haut).{theta}</p>"
            f"<p>{article}. Vérification adverse : {esc(p.verifier.verdict or '')} "
            f"({esc(p.verifier.date)}). Leviers qui l'ouvrent : <code>{esc(leviers)}</code>. "
            f"{fichier(entry['fichier'])}</p>"
            f"<details><summary>Ce qu'elle mesure, et sa limite</summary>"
            f"<p>{esc(' '.join(p.applies_to.split()))}</p>"
            + (f"<p>{esc(' '.join(p.note.split()))}</p>" if p.note else "")
            + "</details></li>")


def _magasin() -> str:
    m = magasin()
    lignes = m["lignes"]
    vus: set[str] = set()
    blocs = []
    for c in canaux():
        presentes = [k for k in c["lignes"] if k in lignes]
        vus.update(presentes)
        blocs.append(f"<h3>{c['numero']} — {esc(c['label'])}</h3>"
                     f"<p>Ce canal {esc(c['role'])}.</p>"
                     + ("<ul class=\"lignes\">" + "".join(_ligne(k, lignes[k]) for k in presentes)
                        + "</ul>" if presentes else "<p>Aucune ligne chargée.</p>"))
    reste = [k for k in lignes if k not in vus]
    if reste:
        blocs.append("<h3>Hors des canaux</h3><p>Ces lignes nourrissent les indices de la "
                     f"couche entreprises ({fichier('src/impots/predictif/indices.py')}), "
                     "affichés à part, jamais ajoutés à la dette.</p><ul class=\"lignes\">"
                     + "".join(_ligne(k, lignes[k]) for k in reste) + "</ul>")
    return "".join(blocs)


def _matrice() -> str:
    cs = canaux()
    ouv = ouvertures()
    messages: dict[str, int] = {}
    for o in ouv:
        for c in cs:
            etat = o["canaux"].get(c["cle"])
            if etat and not etat["ouvert"]:
                messages.setdefault(etat["message"], len(messages) + 1)
    present = [c for c in cs if any(c["cle"] in o["canaux"] for o in ouv)]
    tete = "".join(f'<th title="{esc(c["label"])}">{c["numero"]}</th>' for c in present)
    rows = []
    for o in ouv:
        cells = []
        for c in present:
            etat = o["canaux"].get(c["cle"])
            if etat is None:
                cells.append("<td>—</td>")
            elif etat["ouvert"]:
                cells.append("<td><strong>ouvert</strong></td>")
            else:
                cells.append(f'<td>fermé <sup>{messages[etat["message"]]}</sup></td>')
        rows.append(f"<tr><td>{esc(o['nom'])}<br><small>{fichier(o['chemin'], 'rapport')}"
                    f"</small></td>" + "".join(cells) + f"<td>{esc(o['grade'])}</td></tr>")
    notes = "".join(f"<li value=\"{n}\">{esc(m)}</li>" for m, n in messages.items())
    return ("<table><thead><tr><th>étude</th>" + tete + "<th>note de support</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table>"
            "<p>Pourquoi un canal reste fermé, dans les mots du rapport :</p><ol>" + notes
            + "</ol>")


def _regles() -> str:
    lignes = magasin()["lignes"]
    items = []
    for c in canaux():
        leviers = sorted({k for key in c["lignes"] if key in lignes
                          for k in lignes[key]["p"].responds_to_knobs})
        quand = (f"s'ouvre quand la réforme bouge <code>{esc(', '.join(leviers))}</code>"
                 if leviers else "ne s'ouvre pour aucun levier")
        items.append(f"<li><strong>{c['numero']}</strong>, {esc(c['label'])} : {quand}. "
                     f"Sinon : « {esc(' '.join(c['ferme'].split()))} »</li>")
    return "<ul>" + "".join(items) + "</ul>"


def _mortes() -> str:
    return ("<ul>" + "".join(f"<li><code>{esc(m['cle'])}</code> ({fichier(m['fichier'])}) : "
                             f"{esc(m['raison'])}</li>" for m in magasin()["mortes"]) + "</ul>")


def _libelle_ligne(key: str) -> str:
    c = next((c for c in canaux() if key in c["lignes"]), None)
    return f"{c['numero']}, {key}" if c else key


def _curseurs() -> tuple[str, list[dict[str, Any]]]:
    etudes = avec_canaux()
    if not etudes:
        raise ParcoursError("aucun rapport d'étude ne porte les statistiques des canaux.")
    # Tondelier d'abord, s'il est là : un seul canal, C1, et l'exemple de D-373.
    options = "".join(f'<option value="{i}"'
                      f'{" selected" if "tondelier" in r["chemin"] else ""}>{esc(r["nom"])}</option>'
                      for i, r in enumerate(etudes))
    cles: dict[str, list[int]] = {}
    for i, r in enumerate(etudes):
        for key in r["data"]["rejeu"]["lignes"]:
            cles.setdefault(key, []).append(i)
    lignes = magasin()["lignes"]
    rows = []
    for key in cles:
        p = lignes[key]["p"] if key in lignes else None
        fourchette = f" ({_fourchette(p)})" if p is not None else ""
        rows.append(f'<div class="curseur"><label for="t-{key}">{esc(_libelle_ligne(key))}'
                    f"{fourchette}</label>"
                    f'<input type="range" id="t-{key}" data-ligne="{key}" min="0" max="1" '
                    f'step="0.05" value="0.5"><output id="v-{key}" class="num"></output></div>')
    html_ = ('<section id="c-curseurs"><div class="curseur"><label for="c-etude">L\'étude'
             f'</label><select id="c-etude">{options}</select><span></span></div>'
             + "".join(rows) + "</section>\n"
             '<section id="c-resultat"><noscript><p>Sans script, les curseurs ne tournent pas ; '
             "les tableaux ci-dessous donnent les mêmes nombres, toutes les lignes ensemble à "
             "θ = 0, ½ et 1.</p></noscript></section>\n")
    return html_, etudes


def _statique(etudes: list[dict[str, Any]]) -> str:
    blocs = []
    for r in etudes:
        d = r["data"]
        par_theta = {th: _valeurs(d, th) for th in (0.0, 0.5, 1.0)}
        cles = [k for k in RECETTES if any(k in parts(y, par_theta[0.5]) for y in d["years"])]
        emplois = any("emplois_c2" in parts(y, par_theta[0.5]) for y in d["years"])
        tete = ("<th>année</th><th>coût mécanique</th>"
                + "".join(f"<th>recette {_numero(k)}, θ 0 / ½ / 1</th>" for k in cles)
                + ("<th>emplois C2, θ 0 / ½ / 1</th>" if emplois else "")
                + "<th>coût après comportements, θ½</th>")
        rows = []
        for y in d["years"]:
            ps = {th: parts(y, v) for th, v in par_theta.items()}
            cells = "".join("<td class=\"num\">" + " / ".join(md(ps[th][k]) for th in par_theta)
                            + "</td>" for k in cles)
            if emplois:
                cells += ("<td class=\"num\">" + " / ".join(fr(ps[th]["emplois_c2"], 0, True)
                                                            for th in par_theta) + "</td>")
            rows.append(f"<tr><td>{y['year']}</td><td class=\"num\">"
                        f"{md(float(y[rejouer.VIEWS[VUE]]))}</td>{cells}"
                        f"<td class=\"num\">{md(apres(y, par_theta[0.5]))}</td></tr>")
        blocs.append(f"<h3>{esc(r['nom'])}</h3><p>Rapport : {fichier(r['chemin'])}. Dette en "
                     f"{d['years'][-1]['year']} à θ½, le nombre du rapport : "
                     f"<strong>{pt(activite.temoin(d))}</strong>.</p>"
                     f"<table><thead><tr>{tete}</tr></thead><tbody>{''.join(rows)}</tbody>"
                     "</table>")
    return "".join(blocs)


def donnees(etudes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"etudes": [{"nom": r["nom"], "payload": activite.charge(r["data"]),
                        "temoin": activite.temoin(r["data"])} for r in etudes],
            "canaux": {k: c["cle"] for c in canaux() for k in c["lignes"]}}


def page() -> Page:
    curseurs, etudes = _curseurs()
    eti = magasin()["lignes"].get("eti_top_decile")
    exemple = ""
    if eti is not None:
        p = eti["p"]
        exemple = (f"<p>Un exemple. Quand une réforme bouge le barème de l'impôt sur le revenu, "
                   f"le revenu imposable du dixième le plus aisé répond avec une élasticité de "
                   f"{fr(p.central, 2)}, entre {fr(p.low, 2)} et {fr(p.high, 2)} : ces trois "
                   f"nombres sont ceux de {source(p.source.url, eti['page'].rstrip('. '))}, cités dans "
                   f"{fichier(eti['fichier'])}. La passe sur la population calcule une seule "
                   "somme, A_haut : ce que la recette perdrait si l'élasticité valait un. La "
                   "recette du canal est l'élasticité fois cette somme. Changer d'article change "
                   "la bande ; changer l'outil ne change que A_haut.</p>\n")
    corps = (
        "<h2>D'où vient une bande</h2>\n"
        f"<p>Le coût d'une mesure se chiffre d'abord à comportements inchangés (page "
        f"{lien('cout')}). "
        "Les comportements y ajoutent des recettes ou en retirent : un revenu imposable qui "
        "baisse quand l'impôt monte, des heures travaillées qui montent quand le salaire net "
        "monte. L'outil n'estime aucune de ces réactions. Il les lit dans un magasin de lignes "
        "(les élasticités), chacune tirée d'un article publié, avec sa page, sa fourchette "
        "publiée, et le verdict d'une relecture adverse ; une ligne sans verdict ne se charge "
        f"pas ({fichier('src/impots/behavioural/store.py')}).</p>\n"
        + exemple
        + "<p>θ choisit un point dans chaque fourchette : 0 le bas, ½ le centre publié, 1 le "
        "haut, en ligne droite par le centre. Le sens est déclaré ligne par ligne : θ = 1 est "
        "toujours la réaction la plus forte de l'économie, et pour l'emploi au SMIC c'est le "
        "bas de la fourchette, la plus négative. Le calcul est dans "
        f"{fichier('src/impots/predictif/rejouer.py')} (<code>value_at</code>, "
        f"<code>receipts</code>) et {fichier('src/impots/behavioural/channels.py')}.</p>\n"
        "<h2>Les canaux et leurs articles</h2>\n"
        f"<p>Le magasin nourrit {len(canaux())} canaux ; {len(RECETTES)} rendent une recette que "
        "la dette compte, les autres comptent "
        "des emplois, partagent un coût sans le changer, ou sont des indices. Chaque ligne "
        "dit sa fourchette, l'article et la page d'où elle vient, et le sens de θ.</p>\n"
        + _magasin()
        + "<h2>Quand un canal s'ouvre</h2>\n"
        "<p>Un canal s'ouvre quand la réforme bouge un levier qu'une de ses lignes revendique. "
        "Sinon il reste fermé, et le dit par une phrase, jamais par un zéro silencieux.</p>\n"
        + _regles()
        + "<p>Dans les études publiées :</p>\n"
        + _matrice()
        + "<p>La note de support dit si la réforme reste dans l'étendue des réformes qui ont "
        "servi à estimer l'élasticité ; « illustrative » veut dire qu'elle en sort : la bande "
        "de la première année est alors élargie et signalée comme une extrapolation. "
        "« no-evidence » veut dire qu'aucun canal ne couvre la mesure, qui reste mécanique.</p>\n"
        "<p>Pourquoi l'offre de travail ne s'ouvre pas pour les cotisations des salariés : "
        f"« {esc(etude.RAISON_OFFRE_DE_TRAVAIL)} »</p>\n"
        "<h2>Les lignes mortes</h2>\n"
        "<p>Une ligne qui ne résiste pas à la relecture est retirée, pas adoucie, et reste dans "
        "son fichier avec sa raison : un canal qui rétrécit montre pourquoi.</p>\n"
        + _mortes()
        + "<h2>Un θ par élasticité</h2>\n"
        "<p>Les pages d'étude donnent un seul θ à tous les comportements. Ici chaque ligne a le "
        "sien, "
        "sur les études dont le rapport porte les statistiques des canaux (les sommes que la "
        "passe a écrites, année par année). La recette de C1 est ε<sub>tous</sub> × A_bas + "
        "ε<sub>haut</sub> × A_haut ; celle de C7, la somme des ε<sub>g</sub> × S<sub>g</sub> "
        "des groupes de l'article ; C2 compte ε × ancre + queue emplois. Vue vieillie ; la dette suit, "
        f"multiplicateur à θ½ et persistance lue (le multiplicateur a sa page, {lien('activite')}"
        "). Un coût positif coûte au budget ; une recette positive lui rapporte.</p>\n"
        + curseurs
        + _statique(etudes)
        + "<h2>Ce que les comportements ne font pas</h2>\n"
        "<p>Aucun canal pour les transferts. Rien pour l'impôt sur les sociétés dans la dette : "
        "C8 et C9 sont des indices, jamais des recettes. Pas d'élasticité du revenu du capital, "
        "la mieux identifiée en France : la population n'en porte pas, et toute bande sur une "
        "réforme du haut de la distribution en est sous-estimée. Les erreurs de l'outil sont "
        f"rangées à leur étage dans {lien('erreur', 'Où l’outil se trompe')}.</p>\n"
    )
    script = ("window.PARCOURS_COMPORTEMENTS = "
              + json.dumps(donnees(etudes), ensure_ascii=False,
                           separators=(",", ":")).replace("</", "<\\/")
              + ";\n" + (JS / "activite.js").read_text(encoding="utf-8")
              + "\n" + (JS / "comportements.js").read_text(encoding="utf-8"))
    return Page(
        prouve=("une bande comportementale vient d'un article publié, pas de l'outil : l'outil "
                "ne calcule qu'une somme sur la population, que l'élasticité de l'article "
                "multiplie."),
        corps=corps, script=script,
        style=("ul.lignes{padding-left:1.1rem}ul.lignes li{margin:.6rem 0}"
               "ul.lignes p{margin:.2rem 0}#c-curseurs .curseur[hidden]{display:none}"))


# Pour les tests : les valeurs d'un rapport à un θ par ligne.
def valeurs(data: dict[str, Any], theta: dict[str, float]) -> dict[str, Any]:
    values, _ = rejouer.theta_values(data, {**theta, rejouer.MACRO_ROW: 0.5})
    return {k: float(np.asarray(v)) for k, v in values.items()}
