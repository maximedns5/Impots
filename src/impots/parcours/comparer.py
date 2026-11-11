"""La page « Comparer deux candidats » du parcours (D-375 ; diagnostic de la démarche, § 5).

Deux candidats se comparent sur ce qui a la même base pour tous : le coût de la première
année et la part du programme qu'il couvre ; la dette sans aucune boucle (le terme « coût »
de la décomposition, la même identité pour tous) ; ce que la boucle macro lit, instrument
par instrument, et ce qu'elle ne lit pas ; le coût d'un euro rendu aux trois premiers
déciles. Le verdict, P(hausse) et la boîte ne se comparent pas (D-356, D-358) : la page le
dit en tête et ne les montre pas.

Chaque nombre est lu à la construction dans les rapports de la série (D-373) et dans les
programmes relevés. Le curseur est deux menus : le script ne fait que choisir deux lignes
d'un tableau construit ici, déjà mis en forme ; il ne calcule rien.
"""

from __future__ import annotations

import json
import math
from typing import Any

from impots import etude as et
from impots import programmes as pg
from impots.parcours import Page, ParcoursError, activite, fichier, lien, source
from impots.parcours.cout import (
    _json_script,
    b,
    commit,
    e,
    lire,
    md,
    menages_entreprises,
    num,
    pct,
    pt,
    tableau,
)

#: Les huit programmes, dans l'ordre où le site les liste.
ETUDES = ("presidentielle_attal", "presidentielle_labib", "presidentielle_le_pen",
          "presidentielle_lisnard", "presidentielle_melenchon", "presidentielle_retailleau",
          "presidentielle_roussel", "presidentielle_tondelier")
#: Ce que la boucle ne lit pas, par famille de `shocks.UNMAPPED`.
FAMILLES = {"transfert": "prestations", "fiscalité des entreprises": "impôts des entreprises",
            "revenus du capital": "prélèvements sur le capital"}
#: Des sources publiques du même engagement, quand celle du programme relevé n'est pas
#: lisible partout : (programme, mesure) → [(url, texte)]. La source relevée reste dans
#: `programmes/*.json` ; une entrée dont la mesure ou la source relevée a changé est refusée.
AUSSI = {
    ("tondelier", "tranche_ir_60"): {
        "releve": "https://francais.rt.com/france/136196-tva-verte-isf-climatique-contribution",
        "pourquoi": "RT en français, la source relevée, est bloqué dans l'Union européenne",
        "sources": (
            ("https://monvote2027.fr/candidat/tondelier",
             "MonVote2027, fiche de Marine Tondelier, qui cite le programme « Pour une "
             "prospérité écologique » (juillet 2026) : « créer une tranche à 60 % au-delà de "
             "250 000 euros annuels »"),
            ("https://lesecologistes.fr/pages/6ImK65GKUnvibm33WGkjkj/projet-2027",
             "Les Écologistes, le projet 2027, la page que cette fiche cite"),
        ),
    },
}
#: Un montant sous ce seuil, en euros, est « rien » : sous la résolution d'une impulsion
#: (`shocks.MINIMUM_IMPULSE_EUR` vaut 100 M€ ; on garde ici le million).
RIEN_EUR = 1e6


def _chemin(nom: str, genre: str) -> str:
    etude_ = lire(f"etudes/{nom}.json")
    (scen,) = [s["scenario"] for s in etude_["scenarios"]]
    return f"reports/etudes/{nom}/{genre}_{scen}.json"


def _instruments(impulses: dict[str, float]) -> str:
    from impots.etude import INSTRUMENTS

    if not impulses:
        return "aucun"
    return " ; ".join(f"{INSTRUMENTS.get(k, k)} {md(v)}"
                      for k, v in sorted(impulses.items(), key=lambda kv: -abs(kv[1])))


def candidat(nom: str) -> dict[str, Any]:
    """Les nombres d'un programme, lus dans ses rapports, et leurs chemins."""
    from impots.macro import shocks

    etude_ = lire(f"etudes/{nom}.json")
    prog = pg.charger(etude_["programme"])
    pa_path, pr_path = _chemin(nom, "premiere_annee"), _chemin(nom, "predictif")
    pa, pr = lire(pa_path), lire(pr_path)
    m, f = menages_entreprises(pa)
    cost_m = float(m["reform_cost"])
    cost_f = float(f["reform_cost"]) if f else 0.0
    cost = cost_m + cost_f
    first = pr["years"][0]
    if not math.isclose(first["mechanical_frozen_eur"], cost, rel_tol=1e-9):
        raise ParcoursError(f"{nom} : le chemin annuel ne part pas du coût de la première "
                            "année.")
    stats = first["statistiques"]["figee"]
    # Est lu ce qui a sa table dans le rapport : `rejouer.loop` ne garde que ces impulsions.
    tables = pr["rejeu"]["macro"]["instruments"]
    impulses = {k: float(v) for k, v in stats["impulses"].items() if k in tables}
    sans_table = {k: float(v) for k, v in stats["impulses"].items()
                  if k not in tables and v}
    lu = sum(impulses.values())
    non_lu = cost - lu
    familles: dict[str, float] = {}
    raisons: dict[str, str] = {}
    for key, v in sans_table.items():
        nom_ = INSTRUMENTS_NON_LUS.get(key, et.INSTRUMENTS.get(key, key))
        familles[nom_] = v
        raisons[nom_] = activite.raison_impulsion(key)
    for key in stats["uncovered"]:
        fam = shocks.UNMAPPED.get(key)
        if fam is None:
            raise ParcoursError(f"{nom} : « {key} » non lu, d'une famille inconnue.")
        familles.setdefault(FAMILLES[fam], 0.0)
    if "impôts des entreprises" in familles:
        familles["impôts des entreprises"] = cost_f
    elif abs(cost_f) > RIEN_EUR:
        raise ParcoursError(f"{nom} : un coût des entreprises que la boucle dirait lire.")
    reste = non_lu - sum(familles.values())
    autres = [k for k in familles if k != "impôts des entreprises" and k not in raisons]
    if len(autres) == 1:
        familles[autres[0]] = reste
    elif abs(reste) > RIEN_EUR:
        raise ParcoursError(f"{nom} : {md(reste)} non lus, sans famille à qui les donner.")
    dec = pr["lectures"]["decomposition"]["vieillie"]
    deciles = sorted(m["deciles"], key=lambda r: r["decile"])
    gains = [r["mean_delta"] * r["n_households"] for r in deciles]
    bas, tous = sum(gains[:3]), sum(gains)
    if cost > 0 and bas > RIEN_EUR:
        par_euro: str | None = f"{num(cost / bas, 1)} €"
        pourquoi = ""
    else:
        par_euro = None
        pourquoi = ("la mesure rapporte au budget" if cost <= 0 else
                    "les trois premiers déciles n'y gagnent rien")
        if cost <= 0 and bas <= RIEN_EUR:
            pourquoi += " et les trois premiers déciles n'y gagnent rien"
    c = prog.couverture()
    return {
        "nom": nom, "slug": prog.slug, "candidat": prog.candidat, "parti": prog.parti,
        "releve": prog.releve.isoformat(), "pa": pa_path, "pr": pr_path,
        "commit": pa["commit"], "computed": pa["computed"],
        "cout": cost, "cout_m": cost_m, "cout_f": cost_f,
        "chiffrees": c["chiffrees"], "parametrees": c["parametrees"], "mesures": c["mesures"],
        "sans_boucle": float(dec["cout"]), "activite": float(dec["denominateur"]
                                                             + dec["retroaction"]),
        "impulses": impulses, "lu": lu, "non_lu": non_lu, "familles": familles,
        "raisons": raisons,
        "bas": bas, "tous": tous, "par_euro": par_euro, "pourquoi": pourquoi,
        "deciles": [r["mean_delta"] for r in deciles[:3]],
        "mesures_chiffrees": [(mm.id, mm.libelle, mm.sources[0].url, mm.sources[0].date)
                              for mm in prog.chiffrees()],
        "aussi": _aussi(prog),
    }


#: Le nom d'une impulsion sans table, sur cette page.
INSTRUMENTS_NON_LUS = {"taxe_carbone": "accises sur l'énergie"}


def _aussi(prog: Any) -> dict[str, list[tuple[str, str]]]:
    """Les sources accessibles d'une mesure chiffrée, en plus de celle relevée."""
    out: dict[str, list[tuple[str, str]]] = {}
    for (slug, mid), entree in AUSSI.items():
        if slug != prog.slug:
            continue
        mesure = next((m for m in prog.chiffrees() if m.id == mid), None)
        if mesure is None or mesure.sources[0].url != entree["releve"]:
            raise ParcoursError(f"{slug}, {mid} : la mesure ou sa source relevée a changé ; "
                                "les sources ajoutées par la page sont à revoir.")
        out[mid] = [(url, texte) for url, texte in entree["sources"]]
        out[mid].insert(0, ("", entree["pourquoi"]))
    return out


def _non_lu(c: dict[str, Any]) -> str:
    if not c["familles"] and abs(c["non_lu"]) <= RIEN_EUR:
        return "rien"
    parts = " ; ".join(f"{k} {md(v)}" + (f", une impulsion sans table : {c['raisons'][k]}"
                                          if k in c["raisons"] else "")
                       for k, v in c["familles"].items())
    return f"{md(c['non_lu'])} ({parts})" if parts else md(c["non_lu"])


def _part(c: dict[str, Any]) -> str:
    """La couverture, à côté de chaque coût : de quoi il est le coût."""
    return (f"{c['chiffrees']} mesure{'s' if c['chiffrees'] > 1 else ''} sur "
            f"{c['parametrees']}")


def _cellules(c: dict[str, Any]) -> dict[str, str]:
    """Les cellules d'un candidat, en texte simple : ce que le script recopie."""
    return {
        "nom": f"{c['candidat']} ({c['parti']})",
        "cout": f"{md(c['cout'])}, pour {_part(c)}",
        "couches": (f"ménages {md(c['cout_m'])} ; entreprises {md(c['cout_f'])}"
                    if c["cout_f"] else "ménages seuls"),
        "couverture": (f"{c['chiffrees']} mesures chiffrées sur {c['parametrees']} "
                       f"paramétrées ({c['mesures']} relevées)"),
        "sans_boucle": pt(c["sans_boucle"]),
        "lu": _instruments(c["impulses"]),
        "non_lu": _non_lu(c),
        "activite": pt(c["activite"]),
        "bas": (f"{md(c['bas'])} sur {md(c['tous'])} rendus aux ménages"
                if abs(c["tous"]) > RIEN_EUR else "rien"),
        "par_euro": c["par_euro"] or f"ne se lit pas : {c['pourquoi']}",
    }


#: Les lignes du tableau des deux candidats : (clé, ce qu'elle dit, étage).
LIGNES = (
    ("cout", "Le coût de la première année, et pour combien des mesures paramétrées",
     "L2"),
    ("couches", "dont ménages, entreprises", "L2"),
    ("couverture", "La part du programme chiffrée", "programme"),
    ("sans_boucle", "La dette en 2035, sans aucune boucle", "L2"),
    ("lu", "Ce que la boucle macro lit, la première année", "L2"),
    ("non_lu", "Ce qu'elle ne lit pas", "L2"),
    ("activite", "Ce que l'activité change à la dette en 2035, à θ½ (ne se compare pas)",
     "L4"),
    ("bas", "Ce que gagnent les trois premiers déciles, par an", "L2"),
    ("par_euro", "Le coût d'un euro rendu aux trois premiers déciles", "L2"),
)

SCRIPT = """
(function () {
  var D = __DONNEES__;
  var a = document.getElementById("candidat-a");
  var b = document.getElementById("candidat-b");
  if (!a || !b) { return; }
  function montrer() {
    var cles = __CLES__;
    for (var i = 0; i < cles.length; i++) {
      document.getElementById("cmp-a-" + cles[i]).textContent = D[a.value][cles[i]];
      document.getElementById("cmp-b-" + cles[i]).textContent = D[b.value][cles[i]];
    }
  }
  a.addEventListener("change", montrer);
  b.addEventListener("change", montrer);
  montrer();
})();
"""


def _sources_aussi(c: dict[str, Any], mid: str) -> str:
    if mid not in c["aussi"]:
        return ""
    (_, pourquoi), *autres = c["aussi"][mid]
    return (f"<br><small>{e(pourquoi)} ; le même engagement, ailleurs : "
            + " ; ".join(source(url, texte) for url, texte in autres) + "</small>")


def _menus(cands: list[dict[str, Any]], cells: dict[str, dict[str, str]],
           a: str, b_: str) -> str:
    def menu(ident: str, choisi: str, titre: str) -> str:
        opts = "".join(f'<option value="{c["nom"]}"'
                       f'{" selected" if c["nom"] == choisi else ""}>{e(c["candidat"])}'
                       "</option>" for c in cands)
        return (f'<div class="curseur"><label for="{ident}">{titre}</label>'
                f'<select id="{ident}">{opts}</select><span></span></div>')

    rows = "".join(
        f"<tr><th scope=\"row\">{e(titre)} {b('', etage)}</th>"
        f'<td id="cmp-a-{k}">{e(cells[a][k])}</td><td id="cmp-b-{k}">{e(cells[b_][k])}</td>'
        "</tr>" for k, titre, etage in LIGNES)
    return (menu("candidat-a", a, "Premier candidat") + menu("candidat-b", b_,
                                                              "Second candidat")
            + '<table class="deux"><thead><tr><th></th><th>premier</th><th>second</th></tr>'
            f"</thead><tbody>{rows}</tbody></table>"
            "<noscript><p>Sans JavaScript, les menus ne changent pas ce tableau : les huit "
            "programmes sont tous dans les tableaux ci-dessous.</p></noscript>")


def page() -> Page:
    cands = [candidat(n) for n in ETUDES]
    cells = {c["nom"]: _cellules(c) for c in cands}
    commits = {c["commit"] for c in cands}
    if len(commits) != 1:
        raise ParcoursError("les huit programmes ne viennent pas d'une même série.")
    serie = cands[0]
    par_nom = {c["nom"]: c for c in cands}
    attal = par_nom["presidentielle_attal"]

    t1 = tableau(
        ["candidat", "coût de la première année, pour combien de mesures paramétrées",
         "dette 2035 sans boucle", "€ par euro aux 3 premiers déciles"],
        [[f'<a href="{c["nom"]}.html">{e(c["candidat"])}</a>',
          b(md(c["cout"]), "L2") + " pour " + b(_part(c), "programme"),
          b(pt(c["sans_boucle"]), "L2", True),
          (b(c["par_euro"], "L2") if c["par_euro"] else e(f"— ({c['pourquoi']})"))]
         for c in cands])
    t2 = tableau(
        ["candidat", "lu par la boucle", "non lu", "l'activité, en 2035 à θ½"],
        [[e(c["candidat"]), e(cells[c["nom"]]["lu"]), e(cells[c["nom"]]["non_lu"]),
          b(pt(c["activite"]), "L4", True)] for c in cands])
    t3 = tableau(
        ["candidat", "ce que gagnent les déciles 1, 2 et 3, par ménage et par an",
         "le total des trois", "la part du gain des ménages"],
        [[e(c["candidat"]),
          " ; ".join(b(f"{num(x, 0)} €", "L2") for x in c["deciles"]),
          b(md(c["bas"]), "L2"),
          (b(pct(c["bas"] / c["tous"], 0, signed=False), "L2")
           if c["tous"] > RIEN_EUR else "—")] for c in cands])
    sources = tableau(
        ["candidat", "les mesures chiffrées, à la source relevée", "les rapports"],
        [[f'<a href="{c["nom"]}.html">{e(c["candidat"])}</a>, relevé le {e(c["releve"])}',
          "<br>".join(source(url, f"{lib} ({d})") + _sources_aussi(c, mid)
                      for mid, lib, url, d in c["mesures_chiffrees"]),
          fichier(c["pa"], "première année") + "<br>" + fichier(c["pr"], "chemin annuel")
          + "<br>" + fichier(f"programmes/{c['slug']}.json", "programme")]
         for c in cands])

    corps = f"""
<h2 id="ce-qui-ne-se-compare-pas">Ce qui ne se compare pas</h2>
<p><strong>Le verdict sur la dette, la probabilité qu'elle monte et la boîte θ ne se
comparent pas d'un candidat à l'autre.</strong> La boucle macro, qui fait l'essentiel de
l'incertitude, ne lit que les instruments dont le rapport porte la table, tirée d'une
variante du modèle Mésange : les cotisations, l'impôt sur le revenu, la CSG, la TVA. Pas les
accises sur l'énergie : Mésange a une variante « taxe carbone », mais son solde contient la
baisse de l'assiette énergie, qui n'est pas un effet de l'activité, et la boucle ne la lit
pas ({lien("activite", "page 5")}). Un euro de cotisation rendu
passe par elle et revient en partie par la croissance ; un euro d'impôt des entreprises ou
de prestation va à la dette entier, faute de mesure, pas parce qu'il ne rapporterait rien
({fichier("src/impots/macro/shocks.py")}, {fichier("docs/DECISIONS.md", "D-356 et D-358")}).
Deux verdicts mesurent donc en partie l'instrument, pas la mesure. Ne se compare pas non
plus un programme pris entier : l'outil n'en chiffre qu'une part, différente pour chacun.
Les verdicts restent sur la page de chaque candidat, avec ce qu'ils lisent.</p>
<p>Ce qui se compare a la même base pour tous : la même population, la même loi, la même
arithmétique (la série du {e(serie["computed"])}, commit {commit(serie["commit"])}).</p>
<p><strong>Une asymétrie du modèle, qui ne se voit pas dans les coûts.</strong> Le canal de
l'offre de travail, qui rend une recette quand le salaire net monte, ne s'ouvre que pour la
CSG, pas pour les cotisations des salariés : « {e(et.RAISON_OFFRE_DE_TRAVAIL)} »
({lien("comportements", "page 4")}). Un programme qui baisse la CSG, comme celui de
{e(par_nom["presidentielle_lisnard"]["candidat"])}, reçoit donc cette recette ; un programme
qui rend le même salaire net par les cotisations, comme ceux de
{e(attal["candidat"])} et de {e(par_nom["presidentielle_retailleau"]["candidat"])}, ne la
reçoit pas. Sur la dette, la comparaison avantage le premier par construction.</p>

<h2 id="deux-candidats">Deux candidats, côte à côte</h2>
{_menus(cands, cells, "presidentielle_attal", "presidentielle_retailleau")}
<p>Le coût est celui de la première année : la population de 2024 au droit de 2026, la
prestation perçue (non-recours compté), avant tout comportement. Une même mesure porte
d'autres nombres sous d'autres conventions (le droit, la vue vieillie, l'année pleine, le
chiffre préenregistré) : la {lien("cout", "page 3")} les range dans un tableau de passage.
Chaque coût est dit avec sa couverture, parce qu'il n'est le coût que de ces mesures-là. La couverture dit de quoi il est le coût : les
mesures que l'outil chiffre, sur celles du programme qui énoncent un paramètre
({fichier("src/impots/programmes.py")}). La dette sans boucle est la première marche de la
décomposition : la dette de 2035 si le coût n'avait aucun effet sur l'activité, dans la vue
vieillie, la même identité pour tous ({lien("dette", "page 6")}). Pour Attal :
{b(md(attal["cout"]), "L2")} la première année, {b(pt(attal["sans_boucle"]), "L2", True)}
de dette en 2035 sans boucle.</p>

<h2 id="les-huit">Les huit programmes</h2>
{t1}
<p>Le coût d'un euro rendu aux trois premiers déciles divise le coût de la première année
par ce que gagnent, ensemble, les ménages des trois premiers dixièmes de niveau de vie. Il
ne demande aucun calcul neuf : les déciles sont ceux des rapports. Deux réserves, lues dans
les mêmes rapports. Le coût compte la part des entreprises, que les déciles ne voient pas.
Et les déciles ne portent pas l'extrapolation aux salariés absents de l'enquête, que les
totaux portent ({fichier("docs/DECISIONS.md", "D-368")}) : pour une mesure sur les salaires,
ce que gagnent les ménages est un peu sous-estimé, et le coût par euro un peu
surestimé. La part des trois premiers déciles dans le gain des ménages, au tableau suivant,
n'a pas ce biais.</p>
{t3}

<h2 id="la-boucle">Ce que la boucle lit, et ce qu'elle ne lit pas</h2>
<p>La première année, le coût se partage entre les instruments que la boucle lit et le
reste, qu'elle ne lit pas. « Non lu » n'est pas « nul » : l'outil n'en sait pas l'effet sur
l'activité, et la dette le porte entier. La dernière colonne dit ce que l'activité change à
la dette de 2035 à θ½ (le PIB plus haut et les recettes qu'il rend) : elle dépend de ce que
la boucle lit, et c'est pourquoi elle ne se compare pas ({lien("activite", "page 5")}). Est
lue une impulsion dont le rapport porte la table (<code>rejeu.macro</code>) ; une impulsion
sans table et un poste sans variante ne le sont pas, et la cellule dit pourquoi. Les
impulsions et les instruments non couverts sont ceux du chemin annuel, la première année,
dans la vue figée ; la part « prestations » est le reste, à l'arrondi de la double entrée
près.</p>
{t2}

<h2 id="sources">D'où viennent ces nombres</h2>
{sources}
"""
    keys = [k for k, _, _ in LIGNES]
    script = (SCRIPT.replace("__DONNEES__", _json_script(cells))
              .replace("__CLES__", json.dumps(keys)))
    return Page(prouve="deux candidats se comparent sur la même base : le coût de la "
                       "première année et sa couverture, la dette sans boucle, ce que la "
                       "boucle lit ; pas sur le verdict.",
                corps=corps, script=script,
                style="table.deux th[scope=row]{font-weight:400}")
