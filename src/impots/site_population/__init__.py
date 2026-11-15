"""Les pages « La population » du site (but 25, volet `population`, D-453).

Quatre pages, et les cellules en fichiers :

* `population.html` : d'où vient la population (l'enquête, la construction pas à pas,
  le vieillissement jusqu'à l'année simulée), ce qu'elle représente (ce que pèse un
  ménage, sa structure) ;
* `population-france.html` : en quoi elle ressemble à la France et en quoi elle s'en
  écarte (ce qui est calé, ce qui est vérifié, les écarts connus) ;
* `population-comme-moi.html` : « un ménage comme le mien », la cellule et le cas type
  les plus proches de quelques traits que le visiteur donne ; jamais un enregistrement ;
* `cellules.html` : les 50 cellules des ménages et les 57 des entreprises, avec leurs
  définitions et leurs sources, et `cellules-menages.{csv,json}`,
  `cellules-entreprises.{csv,json}` à télécharger.

LES ANCRES SONT STABLES (`ANCRES`) : d'autres pages y renvoient (l'étape « la
population » du chemin). Les renommer casse leurs liens.

LES PAGES NE CALCULENT RIEN. Elles lisent `reports/population/agregats.json`, écrit par
`impots.site_population.agregats` depuis des fichiers qui existent déjà, et
`reports/parcours/menages.json` (les cas types chiffrés d'avance). Une moyenne par ménage
est la somme d'une cellule sur son nombre de ménages, et le dit.
"""

from __future__ import annotations

import csv
import html
import io
import json
from pathlib import Path
from typing import Any

from impots.site_population import agregats as _agregats

ICI = Path(__file__).resolve().parent
ROOT = _agregats.ROOT
DEPOT = "https://github.com/maximedns5/Impots"
MENAGES_TYPES = ROOT / "reports" / "parcours" / "menages.json"

PAGE, FRANCE, COMME_MOI, CELLULES = ("population.html", "population-france.html",
                                     "population-comme-moi.html", "cellules.html")
STYLE, SCRIPT = "population.css", "population-comme-moi.js"
FICHIERS_CELLULES = ("cellules-menages.csv", "cellules-menages.json",
                     "cellules-entreprises.csv", "cellules-entreprises.json")
#: Les points d'entrée que d'autres pages peuvent citer : (page#ancre) → ce qu'on y lit.
ANCRES: dict[str, str] = {
    f"{PAGE}#en-bref": "la population en quatre nombres",
    f"{PAGE}#construction": "la construction pas à pas, de l'enquête aux cellules",
    f"{PAGE}#vieillissement": "le vieillissement jusqu'à l'année simulée",
    f"{PAGE}#poids": "ce que pèse un ménage simulé",
    f"{PAGE}#structure": "âges, types de ménages, activité, logement, territoire, revenus",
    f"{FRANCE}#calee": "ce qui est imposé (calé) et ne prouve rien",
    f"{FRANCE}#verifiee": "ce qui est vérifié contre des totaux publiés",
    f"{FRANCE}#ecarts": "les écarts connus, dits franchement",
    f"{COMME_MOI}#choisir": "un ménage comme le mien",
    f"{CELLULES}#menages": "les 50 cellules des ménages",
    f"{CELLULES}#entreprises": "les 57 cellules des entreprises",
    f"{CELLULES}#telecharger": "les cellules en CSV et en JSON",
}

TYPES = ("seul", "monoparentale", "couple_sans_enfant", "couple_avec_enfants", "complexe")
TYPES_LIBELLES = {"seul": "Personne seule", "monoparentale": "Famille monoparentale",
                  "couple_sans_enfant": "Couple sans enfant",
                  "couple_avec_enfants": "Couple avec enfants",
                  "complexe": "Ménage complexe"}
#: Le cas type de `reports/parcours/menages.json` le plus proche de chaque type.
CAS_TYPES = {"seul": "seul", "monoparentale": "seul_2e", "couple_sans_enfant": "couple_2s",
             "couple_avec_enfants": "couple_2s_2e"}
TAILLES = {"micro": "Microentreprises (moins de 10 salariés)",
           "PME": "PME (10 à 249 salariés)", "ETI": "ETI (250 à 4 999 salariés)",
           "GE": "Grandes entreprises (5 000 salariés et plus)"}
SECTIONS = {"A": "Agriculture, sylviculture, pêche", "B": "Industries extractives",
            "C": "Industrie manufacturière", "D": "Énergie (électricité, gaz)",
            "E": "Eau, déchets, dépollution", "F": "Construction",
            "G": "Commerce, réparation d'automobiles", "H": "Transports et entreposage",
            "I": "Hébergement et restauration", "J": "Information et communication",
            "K": "Activités financières et d'assurance", "L": "Activités immobilières",
            "M": "Activités spécialisées, scientifiques et techniques",
            "N": "Services administratifs et de soutien", "P": "Enseignement",
            "Q": "Santé humaine et action sociale",
            "R": "Arts, spectacles et activités récréatives", "S": "Autres services"}

#: Chaque variable d'une cellule de ménages : (libellé, unité, définition).
VARIABLES: dict[str, tuple[str, str, str]] = {
    "menages": ("Ménages", "ménages", "Nombre de ménages (logements occupés) que la cellule "
                "représente, somme des poids."),
    "personnes": ("Personnes", "personnes", "Personnes vivant dans ces ménages."),
    "uc": ("Unités de consommation", "UC", "Échelle de l'OCDE modifiée : 1 pour le premier "
           "adulte, 0,5 par personne de 14 ans et plus, 0,3 par enfant de moins de 14 ans."),
    "salaire_brut": ("Salaires bruts", "€", "Salaires bruts de l'année."),
    "salaire_net": ("Salaires nets", "€", "Salaires après cotisations, CSG et CRDS."),
    "salaire_super_brut": ("Salaires super-bruts", "€", "Coût du travail : brut plus "
                           "cotisations employeur, après allègements."),
    "salaire_imposable": ("Salaires imposables", "€", "Salaires retenus par l'impôt sur le "
                          "revenu."),
    "cotisations_salariales": ("Cotisations salariales", "€", "Cotisations sociales à la "
                               "charge des salariés."),
    "cotisations_employeur": ("Cotisations employeur", "€", "Cotisations à la charge des "
                              "employeurs, après allègements."),
    "retraite": ("Retraites", "€", "Pensions de retraite imposables."),
    "chomage_brut": ("Allocations chômage", "€", "Allocations chômage brutes."),
    "ir": ("Impôt sur le revenu", "€", "Impôt payé, après réductions et crédits (négatif : "
           "le crédit dépasse l'impôt)."),
    "revenu_disponible": ("Revenu disponible", "€", "Revenus, plus prestations, moins "
                          "impôts directs et cotisations : ce qui reste pour vivre."),
    "consommation": ("Consommation", "€", "Consommation imputée (enquête Budget de famille "
                     "2017, Insee), selon le revenu et le type de ménage."),
    "tva": ("TVA payée", "€", "TVA contenue dans la consommation imputée."),
    "accises": ("Accises sur l'énergie", "€", "Taxes sur les carburants et l'énergie "
                "contenues dans la consommation imputée."),
    "csg_crds_salaires": ("CSG et CRDS sur les salaires", "€", "CSG déductible, imposable "
                          "et CRDS prélevées sur les salaires."),
    "prestations": ("Prestations", "€", "Allocations familiales, RSA, prime d'activité, "
                    "aides au logement, AAH, minimum vieillesse et autres prestations "
                    "sociales (RSA et prime servis en espérance du recours)."),
    "revenus_non_salaries": ("Revenus non salariés", "€", "Revenus des indépendants, "
                             "micro-entrepreneurs, agriculteurs et gérants."),
    "epargne": ("Épargne", "€", "Revenu disponible moins consommation imputée."),
    "en_emploi": ("Personnes en emploi", "personnes", "Personnes en emploi au sens du BIT "
                  "(enquête Emploi)."),
    "salaries": ("Salariés", "personnes", "Personnes en emploi salarié."),
    "chomeurs": ("Chômeurs", "personnes", "Personnes au chômage au sens du BIT."),
}
VARIABLES_FIRMES: dict[str, tuple[str, str, str]] = {
    "naf_section": ("Secteur", "", "Section de la nomenclature d'activités française "
                    "(NAF rév. 2)."),
    "taille": ("Taille", "", "Catégorie d'entreprise au sens de la loi de modernisation "
               "de l'économie (effectif, chiffre d'affaires, bilan)."),
    "n_firms": ("Entreprises", "entreprises", "Entreprises soumises à l'impôt sur les "
                "sociétés que la cellule représente."),
    "turnover_total": ("Chiffre d'affaires", "€", "Chiffre d'affaires total de la cellule."),
    "value_added_total": ("Valeur ajoutée", "€", "Valeur ajoutée totale de la cellule."),
    "result_total": ("Résultat", "€", "Résultat comptable avant impôt total de la cellule."),
    "p_loss": ("Part en perte", "part", "Part des entreprises déficitaires de la taille "
               "(Insee Références, Les entreprises en France 2023, fiche 3.6, données "
               "2021)."),
}


class PopulationSiteError(ValueError):
    """Une page de la population qui ne tient pas ses promesses."""


# --------------------------------------------------------------------------- #
# les nombres en français
# --------------------------------------------------------------------------- #
NBSP = "\u202f"


def _entier(x: float) -> str:
    return f"{round(x):,}".replace(",", NBSP).replace("-", "−")


def _dec(x: float, n: int = 1) -> str:
    return (f"{x:,.{n}f}".replace(",", " ").replace(".", ",").replace(" ", NBSP)
            .replace("-", "−"))


def millions(x: float, n: int = 2) -> str:
    return f"{_dec(x / 1e6, n)} millions"


def mds(x: float, n: int = 0) -> str:
    return f"{_dec(x / 1e9, n)}{NBSP}Md€"


def pct(x: float, n: int = 1, signe: bool = False) -> str:
    s = _dec(100 * x, n)
    return ("+" if signe and x > 0 else "") + s + NBSP + "%"


def euros(x: float) -> str:
    return _entier(x) + NBSP + "€"


def e(texte: str) -> str:
    return html.escape(texte, quote=True)


def fichier(chemin: str, texte: str | None = None) -> str:
    if not (ROOT / chemin).exists():
        raise PopulationSiteError(f"la page cite {chemin}, absent du dépôt")
    return (f'<a class="fichier" href="{e(DEPOT)}/blob/main/{e(chemin)}"><code>'
            f"{e(texte or chemin)}</code></a>")


def source(url: str | None, texte: str) -> str:
    if not url:
        return e(texte)
    return f'<a class="source" href="{e(url)}">{e(texte)}</a>'


# --------------------------------------------------------------------------- #
# les composants : des barres et des tableaux en HTML, lisibles sans script
# --------------------------------------------------------------------------- #
def barres(lignes: list[tuple[str, float, float | None]], fmt, titre: str,
           legende_cible: str = "") -> str:
    """Des barres horizontales ; une cible publiée, si donnée, en trait vertical."""
    haut = max(max(v, c or 0) for _, v, c in lignes) or 1.0
    rangs = []
    for libelle, v, cible in lignes:
        trait = (f'<span class="cible" style="left:{100 * cible / haut:.2f}%"></span>'
                 if cible is not None else "")
        dit = (f'<span class="dit"> {e(legende_cible)} : {fmt(cible)}</span>'
               if cible is not None else "")
        rangs.append(f'<div class="barre"><span class="etiquette">{e(libelle)}</span>'
                     f'<span class="piste"><span class="plein" style="width:'
                     f'{100 * v / haut:.2f}%"></span>{trait}</span>'
                     f'<span class="valeur">{fmt(v)}{dit}</span></div>')
    leg = (f'<p class="legende"><span class="cle-plein"></span> la population simulée '
           f'<span class="cle-cible"></span> {e(legende_cible)}</p>' if legende_cible
           else "")
    return (f'<figure class="barres" role="group" aria-label="{e(titre)}">'
            f"<figcaption>{e(titre)}</figcaption>{''.join(rangs)}{leg}</figure>")


def chiffre(valeur: str, libelle: str, note: str = "") -> str:
    return (f'<div class="chiffre"><span class="grand">{valeur}</span>'
            f'<span class="quoi">{libelle}</span>'
            + (f'<span class="note">{note}</span>' if note else "") + "</div>")


def tableau(entetes: list[str], lignes: list[list[str]], legende: str = "",
            classe: str = "") -> str:
    th = "".join(f'<th scope="col">{h}</th>' for h in entetes)
    corps = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in ligne) + "</tr>"
                    for ligne in lignes)
    cap = f"<caption>{legende}</caption>" if legende else ""
    return (f'<div class="defile" tabindex="0"><table class="{classe}">{cap}<thead><tr>'
            f"{th}</tr></thead><tbody>{corps}</tbody></table></div>")


def nav(ici: str) -> str:
    pages = ((PAGE, "D'où elle vient, ce qu'elle représente"),
             (FRANCE, "Ressemble-t-elle à la France ?"),
             (COMME_MOI, "Un ménage comme le mien"),
             (CELLULES, "Les cellules publiées"))
    items = "".join(f'<li><a href="{p}"' + (' aria-current="page"' if p == ici else "")
                    + f">{e(t)}</a></li>" for p, t in pages)
    return f'<nav class="pop-nav" aria-label="La population"><ol>{items}</ol></nav>'


# --------------------------------------------------------------------------- #
# les données
# --------------------------------------------------------------------------- #
def lire() -> dict[str, Any]:
    if not _agregats.SORTIE.exists():
        raise PopulationSiteError(f"{_agregats.SORTIE} absent : `{_agregats.COMMANDE}`")
    return _agregats.lire()


def present() -> bool:
    return _agregats.SORTIE.exists() and MENAGES_TYPES.exists()


def cellules_menages(d: dict[str, Any]) -> list[dict[str, Any]]:
    c = d["cellules_menages"]
    v = c["valeurs"]
    out = []
    for i in range(len(v["menages"])):
        ligne: dict[str, Any] = {"cellule": i + 1, "decile": i // len(c["types"]) + 1,
                                 "type": c["types"][i % len(c["types"])]}
        ligne.update({k: v[k][i] for k in VARIABLES})
        out.append(ligne)
    return out


def _csv(lignes: list[dict[str, Any]]) -> str:
    tampon = io.StringIO()
    w = csv.DictWriter(tampon, fieldnames=list(lignes[0]), lineterminator="\n")
    w.writeheader()
    for ligne in lignes:
        w.writerow({k: (round(x, 2) if isinstance(x, float) else x)
                    for k, x in ligne.items()})
    return tampon.getvalue()


def fichiers_cellules(d: dict[str, Any]) -> dict[str, str]:
    """Les cellules en CSV et en JSON, chaque JSON avec ses définitions et sa source."""
    menages = cellules_menages(d)
    c = d["cellules_menages"]
    f = d["cellules_entreprises"]
    firmes = [dict(cel) for cel in f["cellules"]]
    meta_m = {
        "titre": "Les 50 cellules de ménages du jumeau (D-409)",
        "annee": c["annee"], "unite": "sommes pondérées sur la cellule, euros de l'année",
        "decoupage": "décile de niveau de vie (1 à 10) × type de ménage (5 types)",
        "types": {t: TYPES_LIBELLES[t] for t in TYPES},
        "variables": {k: {"libelle": a, "unite": u, "definition": dfn}
                      for k, (a, u, dfn) in VARIABLES.items()},
        "source": (f"Population de ménages 2024 du dépôt (enquête Emploi 2024 de l'Insee, "
                   f"revenus tirés et calés), passe de référence au droit de "
                   f"{c['annee']} sur {c['echantillon']} ménages (commit "
                   f"{c['commit'][:7]}, {c['construites']}) ; {c['source']}"),
        "cellules": menages}
    meta_f = {
        "titre": "Les 57 cellules d'entreprises (D-407)",
        "millesime": f["millesime"], "unite": "sommes sur la cellule, euros",
        "decoupage": "section NAF × catégorie d'entreprise ; les cellules que le secret "
                     "statistique supprime sont absentes ou complétées",
        "variables": {k: {"libelle": a, "unite": u, "definition": dfn}
                      for k, (a, u, dfn) in VARIABLES_FIRMES.items()},
        "sources": f["sources"], "cellules_secretisees": f["cellules_secretisees"],
        "cellules": firmes}
    return {"cellules-menages.csv": _csv(menages),
            "cellules-menages.json": json.dumps(meta_m, ensure_ascii=False, indent=1) + "\n",
            "cellules-entreprises.csv": _csv(firmes),
            "cellules-entreprises.json": json.dumps(meta_f, ensure_ascii=False, indent=1)
            + "\n"}


# --------------------------------------------------------------------------- #
# population.html
# --------------------------------------------------------------------------- #
def _etape(n: int, titre: str, grand: str, texte: str, source_html: str) -> str:
    return (f'<li class="etape"><span class="num" aria-hidden="true">{n}</span>'
            f'<div><h3>{titre}</h3><p class="grand-etape">{grand}</p><p>{texte}</p>'
            f'<p class="note-source">{source_html}</p></div></li>')


def _deciles(d: dict[str, Any]) -> str:
    c = d["cellules_menages"]["valeurs"]
    n = len(TYPES)
    lignes: list[tuple[str, float, float | None]] = []
    for k in range(10):
        s = slice(k * n, (k + 1) * n)
        rd, uc = sum(c["revenu_disponible"][s]), sum(c["uc"][s])
        lignes.append((f"{k + 1}{'er' if k == 0 else 'e'} dixième", rd / uc, None))
    return (barres(lignes, lambda x: euros(x) + " par an", "Niveau de vie moyen de chaque "
                   "dixième des ménages (revenu disponible par unité de consommation)")
            + '<p class="note-source">Somme du revenu disponible des cinq cellules d\'un '
            "dixième, sur leurs unités de consommation : "
            f'<a href="{CELLULES}#menages">les cellules</a>, droit de 2024.</p>')


def _frise(v: dict[str, Any]) -> str:
    """Vieillir, en image : un même ménage, ses revenus dans les deux vues."""
    de, w, pr = v["de"], v["salaires"], v["prix"]
    annees = (de, de + 3, de + 6, de + 11)
    salaire, pension = 30_000.0, 18_000.0

    def case(a: int, vieillie: bool) -> str:
        n = a - de if vieillie else 0
        return (f'<td><span class="foyer">2 personnes</span>'
                f"<span>salaire {euros(salaire * (1 + w) ** n)}</span>"
                f"<span>retraite {euros(pension * (1 + pr) ** n)}</span></td>")

    tete = "".join(f'<th scope="col">{a}</th>' for a in annees)
    rangs = (f'<tr><th scope="row">Vue vieillie</th>{"".join(case(a, True) for a in annees)}'
             f'</tr><tr><th scope="row">Vue figée</th>'
             f'{"".join(case(a, False) for a in annees)}</tr>')
    return (f'<figure class="frise"><figcaption>Un même ménage (un salarié, un retraité), '
            f"d'année en année : les mêmes personnes, le même poids ; seul l'argent "
            f"change, et seulement dans la vue vieillie</figcaption><div class=\"defile\" "
            f'tabindex="0"><table><thead><tr><th></th>{tete}</tr></thead><tbody>{rangs}'
            f"</tbody></table></div><p class=\"note-source\">Un exemple de lecture, pas un "
            f"ménage de la population : salaire +{_dec(100 * w, 0)} % par an, retraite "
            f"+{_dec(100 * pr, 0)} % par an. Les études donnent les deux vues ; la vieillie "
            f"est celle des nombres de tête.</p></figure>")


def page_population(d: dict[str, Any]) -> str:
    p = d["population"]
    cons = d["construction"]
    sq = cons["squelette"]
    rev = cons["revenus"]
    cal = cons["calage"]
    v = d["vieillissement"]
    poids = p["poids"]
    m = p["menages"]
    logements = 80_171  # skeleton.py : les ménages-trimestres de 80 171 logements
    out = [nav(PAGE), "<h1>La population simulée</h1>",
           "<p class=\"chapeau\">Pour chiffrer une réforme, l'outil applique la loi à des "
           "ménages. Pas à la France entière, ni à de vraies personnes : à un échantillon "
           "de ménages construit à partir d'une enquête publique, dont chacun représente "
           "plusieurs dizaines ou centaines de ménages réels. Cette page dit d'où il vient "
           "et à quoi il ressemble.</p>",
           '<section id="en-bref"><h2>En bref</h2><div class="chiffres">',
           chiffre(_entier(p["menages_echantillon"]), "ménages simulés",
                   f"{_entier(p['lignes'])} personnes"),
           chiffre(millions(m), "de ménages représentés",
                   f"{millions(p['personnes'], 1)} de personnes"),
           chiffre(f"≈{NBSP}{_entier(poids['moyen'])}", "vrais ménages derrière chaque "
                   "ménage simulé, en moyenne", f"8 sur 10 entre {_entier(poids['d1'])} et "
                   f"{_entier(poids['d9'])}"),
           chiffre(str(cons["millesime"]), "l'année de la population",
                   "vieillie ensuite jusqu'à l'année chiffrée"),
           "</div></section>"]

    etapes = [
        _etape(1, "L'enquête Emploi de l'Insee",
               f"{_entier(sq['persons_observed'])} personnes observées",
               f"Le fichier détail de l'enquête Emploi {cons['millesime']} (Insee, licence "
               f"ouverte) dit qui vit avec qui, l'âge par tranches, le sexe, l'activité, le "
               f"logement. Un même logement est interrogé jusqu'à quatre trimestres : chaque "
               f"passage compte comme un ménage, {_entier(sq['households'])} en tout pour "
               f"{_entier(logements)} logements, au même poids total. L'enquête ne dit "
               f"<strong>aucun revenu</strong>.",
               source(cons["enquete_url"], "Insee, enquête Emploi 2024, fichier détail")),
        _etape(2, "Les enfants de moins de 15 ans",
               f"{_entier(sq['children_synthesised'])} enfants créés",
               "L'enquête n'interroge que les 15 ans et plus. Les plus jeunes sont ajoutés "
               "aux familles selon les nombres d'enfants par famille que publie le "
               "recensement ; leur âge est tiré au hasard.",
               fichier("src/impots/population/skeleton.py", "population/skeleton.py")),
        _etape(3, "Les revenus, tirés puis calés",
               f"{mds(rev['gross_wages_after_calibration'])} de salaires bruts",
               "Chaque salaire, pension, allocation chômage et revenu d'indépendant est "
               "tiré dans une distribution publiée (selon la catégorie, le sexe, l'âge, le "
               "temps partiel, le secteur), puis toute la masse est ramenée sur son total "
               f"publié : les salaires d'un facteur {_dec(rev['wage_calibration_factor'], 3)}"
               f", les revenus des indépendants de "
               f"{_dec(rev['self_employment']['calibration_factor'], 3)}.",
               fichier("src/impots/population/incomes.py", "population/incomes.py")),
        _etape(4, "Le calage des poids",
               f"écart de structure {pct(cal['fit_before']['household_type'], 0)} → "
               f"{pct(cal['fit_after']['household_type'])}",
               f"Les poids sont ajustés ensemble ({cal['iterations']} itérations) pour que "
               f"les ménages par type, par statut d'occupation, et les personnes par âge et "
               f"sexe retombent sur le recensement. Aucun poids n'est multiplié par plus de "
               f"{_dec(cal['weight_ratio_range'][1], 2)} ni par moins de "
               f"{_dec(cal['weight_ratio_range'][0], 2)}.",
               fichier("src/impots/population/calibrate.py", "population/calibrate.py")),
        _etape(5, "Ce qu'une réforme demande en plus",
               "niches, capital, indemnités, consommation",
               "Selon la réforme chiffrée, une passe ajoute des données que l'enquête n'a "
               "pas : les bases des réductions d'impôt, les revenus du capital, les "
               "indemnités journalières, la consommation (pour la TVA), les heures "
               "supplémentaires… Chacune est calée sur un total publié, et le dit.",
               fichier("src/impots/population/imputations.py",
                       "population/imputations.py")),
        _etape(6, "Le vieillissement jusqu'à l'année simulée",
               f"salaires +{_dec(100 * v['salaires'], 0)}{NBSP}%, prix "
               f"+{_dec(100 * v['prix'], 0)}{NBSP}% par an",
               f"La population est de {v['de']}. Pour chiffrer 2027 ou 2035, ses revenus "
               f"sont relevés chaque année (salaires et chômage avec les salaires, pensions "
               f"et loyers avec les prix) ; les ménages, leurs âges et leurs poids ne "
               f"bougent pas : c'est la France de {v['de']} avec l'argent de l'année "
               f"chiffrée.",
               fichier("src/impots/uprating.py", "uprating.py") + " · "
               + fichier(v["cadre"], "le cadre des études")),
        _etape(7, "Les cellules du jumeau",
               "50 cellules de ménages, 57 d'entreprises",
               "Pour tourner dans le navigateur, le jumeau résume la population en "
               "cinquante groupes : dix tranches de niveau de vie fois cinq types de "
               "ménages. Les entreprises viennent à part, des tableaux publiés de l'Insee "
               "(Ésane), en 57 groupes par secteur et par taille.",
               f'<a href="{CELLULES}">les cellules publiées</a>'),
    ]
    out += ['<section id="construction"><h2>Comment elle est faite, pas à pas</h2>',
            "<p>Sept étapes, de l'enquête aux cellules. Chacune dit sa source et le "
            "fichier du dépôt qui la fait.</p>",
            f'<ol class="flux">{"".join(etapes)}</ol>',
            f'<p id="vieillissement" class="encadre"><strong>Le vieillissement.</strong> '
            f"Les études publiées vieillissent la population de {v['de']} jusqu'à "
            f"{v['de'] + v['horizon'] + 1} au plus : {e(v['source'])}. Ce sont des "
            f"hypothèses déclarées, pas des prévisions. Ce qui ne vieillit pas : personne "
            f"ne naît, ne meurt, ne se sépare ; les poids restent ceux de {v['de']}, et la "
            f"population vieillie n'est plus calée sur rien.</p>", _frise(v),
            "</section>"]

    tranches = poids["tranches"]
    haut = max(t["menages_echantillon"] for t in tranches)
    cols = []
    for t in tranches:
        lib = f"{t['de']}–{t['a']}" if t["a"] else f"{t['de']}+"
        cols.append(f'<div class="col"><span class="n">{_entier(t["menages_echantillon"])}'
                    f'</span><span class="baton" style="height:'
                    f'{100 * t["menages_echantillon"] / haut:.1f}%"></span>'
                    f'<span class="lib">{lib}</span></div>')
    out += ['<section id="poids"><h2>Ce que pèse un ménage simulé</h2>',
            f"<p>Un ménage simulé n'est pas un vrai ménage : c'est un ménage de l'enquête "
            f"qui en représente d'autres, qui lui ressemblent. Son <strong>poids</strong> "
            f"dit combien : {_entier(poids['moyen'])} en moyenne, {_entier(poids['mediane'])}"
            f" pour le ménage du milieu. Quand une réforme fait gagner 100 € à un ménage "
            f"de poids 150, le coût compte 15 000 €.</p>",
            f'<p class="encadre"><strong>Et les « 20 000 ménages » ?</strong> Pour aller '
            f"vite, une étude n'applique pas la loi aux {_entier(p['menages_echantillon'])} "
            f"ménages : elle en tire 20 000 au hasard, et agrandit leurs poids d'autant. "
            f"Chacun représente alors environ {_entier(m / 20_000)} vrais ménages, et "
            f"ensemble toujours {millions(m)}. Les cellules du jumeau sont faites de même, "
            f"sur {_entier(d['cellules_menages']['echantillon'])} ménages.</p>",
            '<figure class="colonnes" role="group" aria-label="Ménages simulés selon leur '
            'poids"><figcaption>Combien de ménages simulés (en haut de chaque bâton) '
            "représentent chacun entre tant et tant de vrais ménages (en bas)</figcaption>"
            f'<div class="cols">{"".join(cols)}</div></figure>',
            f"<p class=\"note-source\">Les poids viennent de l'enquête (l'Insee les cale "
            f"sur l'âge et le sexe), puis du calage de l'étape 4. Une tranche de moins de "
            f"{_agregats.SEUIL} ménages de l'échantillon serait fondue dans sa voisine. "
            f"{fichier('reports/population/agregats.json')}</p></section>"]

    pyr = p["pyramide"]
    haut = max(max(r["femmes"], r["hommes"]) for r in pyr)
    rangs = "".join(
        f'<div class="rang"><span class="g"><span style="width:'
        f'{100 * r["hommes"] / haut:.1f}%"></span></span><span class="age">{r["age"]}'
        f'</span><span class="d"><span style="width:{100 * r["femmes"] / haut:.1f}%">'
        f"</span></span></div>" for r in reversed(pyr))
    pyramide = ('<figure class="pyramide" role="img" aria-label="Pyramide des âges de la '
                'population simulée, hommes à gauche, femmes à droite"><figcaption>'
                f"Pyramide des âges, par tranche de cinq ans : hommes à gauche "
                f"({millions(sum(r['hommes'] for r in pyr), 1)}), femmes à droite "
                f"({millions(sum(r['femmes'] for r in pyr), 1)})</figcaption>"
                f"{rangs}</figure>")
    tc = p["types_calage"]
    ci = d["cibles"]
    types = barres([("Personne seule", tc["personne_seule"], ci["seul"]),
                    ("Couple sans enfant", tc["couple_sans_enfant"], ci["couple_sans_enfant"]),
                    ("Couple avec enfants", tc["couple_avec_enfant"],
                     ci["couple_avec_enfants"]),
                    ("Famille monoparentale", tc["monoparentale"], ci["monoparentale"]),
                    ("Ménage complexe", tc["complexe"], ci["complexe"])],
                   millions, "Ménages par type", "recensement 2023")
    a = p["activite"]
    activite = barres([("En emploi, salariés", a["en_emploi_salarie"], None),
                       ("En emploi, indépendants", a["en_emploi_non_salarie"], None),
                       ("Au chômage", a["chomeurs"], None),
                       ("Inactifs de 15 ans et plus", a["inactifs_15_ans_et_plus"], None),
                       ("Enfants de moins de 15 ans", a["enfants_crees"], None)],
                      millions, "Personnes, selon leur situation d'activité")
    o = p["occupation"]
    oc = ci["occupation"]
    occupation = barres([
        ("Propriétaires (dont accédants)", o["proprietaire"] + o["primo_accedant"],
         oc["proprietaire"]),
        ("Locataires HLM", o["locataire_hlm"], oc["locataire_hlm"]),
        ("Autres locataires", o["locataire_vide"] + o["locataire_meuble"],
         oc["locataire_autre"]),
        ("Logés gratuitement", o["loge_gratuitement"], oc["loge_gratuitement"])],
        millions, "Ménages, selon leur logement", "recensement 2023")
    t = p["territoire"]
    noms = {"971": "Guadeloupe", "972": "Martinique", "973": "Guyane", "974": "La Réunion"}
    territoire = barres([(noms[k], t[k], ci["dom"][k]) for k in noms],
                        lambda x: f"{_entier(x / 1000)}{NBSP}000",
                        f"Ménages des départements d'outre-mer (métropole : "
                        f"{millions(t['metropole'])})", "recensement 2023")
    r = p["revenus"]
    revenus = barres([("Salaires bruts", r["salaires_bruts"]["total"], None),
                      ("Pensions de retraite", r["pensions"]["total"], None),
                      ("Revenus des indépendants", r["revenus_non_salaries"]["total"], None),
                      ("Allocations chômage", r["allocations_chomage"]["total"], None)],
                     mds, "Les revenus que la population porte, par an")
    out += ['<section id="structure"><h2>Ce qu\'elle représente</h2>',
            f"<p>{millions(m)} de ménages, {millions(p['personnes'], 1)} de personnes, "
            f"{_dec(p['taille_moyenne'], 2)} personnes par ménage. Le trait foncé marque, "
            f"quand il existe, le nombre que publie le recensement.</p>",
            '<div class="grille-2">', pyramide, types, "</div>",
            '<p class="note-source">Les âges sont observés par tranches dans l\'enquête, '
            "puis tirés dans la tranche : une pyramide à l'année près n'aurait pas de sens "
            "ici, une par cinq ans en a.</p>",
            '<div class="grille-2">', activite, occupation, "</div>",
            '<div class="grille-2">', territoire, revenus, "</div>",
            f'<p class="note-source">L\'enquête ne dit pas la région en métropole : la '
            f"population distingue seulement la métropole et quatre départements "
            f"d'outre-mer (Mayotte est hors champ). {_entier(p['secteur_public'] / 1e3)}"
            f"{NBSP}000 personnes en emploi travaillent dans le secteur public.</p>",
            "<h3>Le niveau de vie, par dixième des ménages</h3>", _deciles(d),
            "</section>",
            f'<p class="suite">Suite : <a href="{FRANCE}">ressemble-t-elle à la France ?</a>'
            f' · <a href="{COMME_MOI}">un ménage comme le mien</a></p>']
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# population-france.html
# --------------------------------------------------------------------------- #
ECHELLE = 0.6
"""La piste des écarts va de −60 % à +60 % ; au-delà, le point reste au bord."""
ENTREPRISES = ("is", "c3s", "cvae", "contribution_sociale_is")
#: Pourquoi une ligne est hors de sa tolérance, en clair (D-363 à D-371).
CAUSES = {
    "rsa_foyers": "Trop de foyers ont droit au RSA : la loi codée donne un droit, et des "
                  "ressources manquent à certains ménages (AAH, ASS), ce qui en rend "
                  "éligibles qui ne le sont pas. Le montant servi, lui, tient.",
    "ppa_foyers": "Trop de foyers ont droit à la prime d'activité, pour la même raison de "
                  "droit théorique ; le montant servi est calé sur les recourants de la "
                  "Drees.",
    "cotisations_employeurs": "Les cotisations des employeurs de cette ligne ne comptent "
                              "pas les mêmes choses que le modèle ; comptées au sens D121 "
                              "des comptes nationaux, l'écart tombe à +3 % (D-371).",
    "aide_logement_montant": "Les aides au logement manquent : les foyers, les résidences, "
                             "les accédants et une part des hébergés sont hors de la "
                             "population.",
    "bandeau_famille": "Trop de salaires horaires entre 1,6 et 3,5 SMIC, pas assez "
                       "dessous : la forme du bas des salaires horaires n'est pas publiée.",
    "reduction_generale": "La même forme du bas des salaires horaires, dans l'autre sens.",
    "ppa_montant": "Calée sur les recourants de la Drees ; la Cnaf en compte 17 à 27 % de "
                   "plus. Un choix de cible, dit.",
    "cotisations_salariales": "Au bord de sa tolérance.",
    "ppa_montant_servi": "Le recours est calé sur les recourants de la Drees ; la Cnaf en "
                         "compte 17 à 27 % de plus. Un choix de cible, dit.",
    "ppa_foyers_servis": "La même cible de recours, la Drees plutôt que la Cnaf.",
}


#: Ce qu'un écart fait au coût d'une mesure qui porte sur la ligne (au premier ordre, le
#: coût d'une mesure proportionnelle suit la base que la population porte).
ETUDES = {
    "rsa_foyers": "une mesure sur le RSA se chiffre sur le montant servi en espérance du "
                  "recours, qui tient, pas sur ce compte d'ayants droit.",
    "ppa_foyers": "une mesure sur la prime se chiffre sur le montant servi en espérance "
                  "(ci-dessous), pas sur ce compte d'ayants droit.",
    "ppa_montant": "les études ne servent plus la prime par ce pont mais en espérance du "
                   "recours : la ligne qui compte est le montant servi en espérance.",
    "ppa_montant_servi": "une mesure qui relève la prime d'activité en proportion est "
                         "sous-chiffrée d'environ un quart.",
    "ppa_foyers_servis": "le nombre de foyers qu'une mesure sur la prime touche est "
                         "sous-compté d'environ un quart.",
    "aide_logement_montant": "une mesure proportionnelle sur les aides au logement est "
                             "sous-chiffrée d'environ un quart.",
    "cotisations_employeurs": "une mesure sur les cotisations employeurs passe par les "
                              "allègements, dont les deux lignes suivantes disent l'écart.",
    "reduction_generale": "une mesure sur la réduction générale est sous-chiffrée d'environ "
                          "un sixième.",
    "bandeau_famille": "une mesure sur le bandeau famille est surchiffrée d'environ un "
                       "cinquième.",
    "cotisations_salariales": "une mesure proportionnelle sur ces cotisations est "
                              "sous-chiffrée d'environ un dixième.",
}


def _vaut(tenues: int, n: int) -> str:
    return (f'<p class="encadre"><strong>Est-ce bon ?</strong> {tenues} sur {n}, cela veut '
            "dire que la plupart des impôts, des cotisations et des prestations de la "
            "population tombent à quelques pour cent de ce que la France paie et reçoit, "
            "sans qu'on les y ait forcés. La tolérance de chaque ligne est écrite avant le "
            "calcul, selon ce qu'on peut attendre d'une population sans revenus observés "
            "(±10 % pour un impôt, ±25 % pour une prestation, par exemple). Une ligne hors "
            "de sa tolérance ne rend pas une étude fausse : elle dit l'écart dont hérite "
            "une mesure qui porte sur ce poste, et la page de l'étude le dit à côté de son "
            "nombre.</p>")


def _point(ligne: dict[str, Any]) -> str:
    ec, tol = ligne["ecart"], ligne["tolerance"]
    x = 50 + 50 * max(-1.0, min(1.0, ec / ECHELLE))
    bande = (f'<span class="bande" style="left:{50 - 50 * tol / ECHELLE:.2f}%;width:'
             f'{100 * tol / ECHELLE:.2f}%"></span>' if tol else "")
    tient = ligne["verdict"] == "dans la tolérance"
    classe = "tient" if tient else "hors"
    deborde = " deborde" if abs(ec) > ECHELLE else ""
    return (f'<div class="ecart"><span class="etiquette">{e(ligne["ligne"])}</span>'
            f'<span class="piste">{bande}<span class="zero"></span><span class="point '
            f'{classe}{deborde}" style="left:{x:.2f}%"></span></span>'
            f'<span class="valeur {classe}">{pct(ec, 0, True)}'
            f'<span class="dit"> {"dans" if tient else "hors de"} ±{pct(tol, 0)}</span>'
            f"</span></div>")


def page_france(d: dict[str, Any]) -> str:
    p = d["population"]
    tot = {"menages": p["menages"], **{k: x["total"] for k, x in p["revenus"].items()}}

    def gros(x: float) -> str:
        return mds(x) if x > 1e9 else millions(x)

    calees = [[e(c["ligne"]), gros(c["publie"]), gros(tot[c["cle"]]),
               pct(tot[c["cle"]] / c["publie"] - 1, 1, True),
               source(c["url"], f"{c['source']} ({c['annee']})")
               + (f" — {e(c['note'])}" if c["note"] else "")] for c in d["calees"]]
    grille = [x for x in d["grille"] if x["usage"] == "validation" and x["ecart"] is not None
              and x["tolerance"]]
    tenues = sum(x["verdict"] == "dans la tolérance" for x in grille)
    menages_g = [x for x in grille if x["id"] not in ENTREPRISES]
    firmes_g = [x for x in grille if x["id"] in ENTREPRISES]
    out = [nav(FRANCE), "<h1>Ressemble-t-elle à la France ?</h1>",
           "<p class=\"chapeau\">Oui sur ce qu'on lui a imposé, ce qui ne prouve rien. "
           "Assez, sur la plupart de ce qu'on ne lui a pas imposé. Non sur quelques points, "
           "dits ici avec leur cause.</p>",
           '<section id="calee"><h2>Ce qui est imposé : le calage</h2>',
           "<p>Ces totaux sont <strong>atteints par construction</strong> : la population "
           "a été ajustée pour les reproduire. Les retrouver montre que l'ajustement a "
           "tourné, rien de plus. Ils ne comptent jamais comme une vérification.</p>",
           tableau(["Total", "Publié", "Population", "Écart", "Source"], calees,
                   "Les totaux calés, sur la population entière de 2024", "chiffres"),
           '<p class="note-source">L\'écart sur les ménages vient de ce qu\'un ménage est '
           "ici un logement interrogé un trimestre, pour l'Insee un logement. "
           f"{fichier('src/impots/population/margins.py', 'population/margins.py')}</p>"
           "</section>",
           '<section id="verifiee"><h2>Ce qui est vérifié : la grille</h2>',
           f"<p>{len(grille)} totaux publiés de 2024 que la population n'a pas visés, "
           f"comparés à ce qu'elle donne une fois la loi appliquée. Chacun a une tolérance "
           f"écrite <strong>avant</strong> le calcul. <strong>{tenues} sur {len(grille)}"
           f"</strong> la tiennent.</p>",
           '<p class="legende"><span class="cle-bande"></span> la tolérance '
           '<span class="point tient statique"></span> dans la tolérance '
           '<span class="point hors statique"></span> hors de la tolérance. '
           "La piste va de −60 % à +60 % ; un point collé au bord va plus loin.</p>",
           '<figure class="ecarts" role="group" aria-label="Écarts des ménages">'
           "<figcaption>Les ménages : impôts, cotisations, prestations, foyers</figcaption>",
           "".join(_point(x) for x in menages_g), "</figure>",
           '<figure class="ecarts" role="group" aria-label="Écarts des entreprises">'
           "<figcaption>Les entreprises</figcaption>",
           "".join(_point(x) for x in firmes_g), "</figure>",
           f'<p class="note-source">La grille de D-371, sur la population entière : '
           f"{fichier('reports/verification/grille.json')}. Avec 2022 et 2023 : "
           f"<a href=\"parcours-2-france.html\">la France simulée</a>.</p></section>"]
    hors = sorted((x for x in grille if x["verdict"] != "dans la tolérance"),
                  key=lambda x: -abs(x["ecart"]))
    cal = d["construction"]["calage"]
    tc = p["types_calage"]
    out[-1] = out[-1].replace("</p></section>", "</p>" + _vaut(tenues, len(grille))
                              + "</section>")
    out += ['<section id="ecarts"><h2>Où elle s\'écarte, et pourquoi</h2>',
            "<p>Ce que la population fait mal, ou ne sait pas faire. Rien de ceci n'est "
            "corrigé en retouchant un total : on effacerait la ligne qui le montre.</p>",
            "<h3>Les lignes hors de leur tolérance</h3><ul class=\"ecarts-dits\">"]
    for x in hors:
        out.append(f"<li><strong>{e(x['ligne'])}</strong> <span class=\"hors\">"
                   f"{pct(x['ecart'], 0, True)}</span> — "
                   + (e(CAUSES[x["id"]]) if x["id"] in CAUSES else
                      'sa cause : <a href="parcours-2-france.html">la France simulée</a>.')
                   + (f' <span class="aux-etudes">Pour les études : {e(ETUDES[x["id"]])}'
                      "</span>" if x["id"] in ETUDES else "") + "</li>")
    out += ["</ul><h3>Les limites de construction</h3><ul class=\"ecarts-dits\">",
            "<li><strong>Aucun revenu n'est observé.</strong> Chaque euro est tiré d'une "
            "distribution publiée et calé sur un total : le niveau est juste par "
            "construction, la forme vaut ce que valent les distributions publiées.</li>",
            "<li><strong>Les deux revenus d'un couple sont tirés indépendamment.</strong> "
            "Les couples aisés le sont moins que dans la réalité : le haut de la "
            "distribution des ménages est aplati.</li>",
            "<li><strong>Les âges sont observés par tranches</strong> et les enfants de "
            "moins de 15 ans sont créés : un seuil d'âge qui ne tombe pas sur une limite "
            "de tranche n'est juste qu'en moyenne.</li>",
            "<li><strong>Pas de région en métropole.</strong> Une mesure régionale ne se "
            "chiffre pas ; les zones des aides au logement sont tirées.</li>",
            f"<li><strong>Le vieillissement est mécanique.</strong> Personne ne naît ni ne "
            f"meurt ; les poids de {d['vieillissement']['de']} restent : une mesure dont le "
            f"coût suit le nombre de retraités est sous-estimée à long terme.</li>",
            f"<li><strong>Deux façons de compter les ménages complexes.</strong> Le calage "
            f"compte un enfant majeur chez ses parents comme un enfant de la famille "
            f"({millions(tc['complexe'])} de ménages complexes, comme le recensement) ; les "
            f"cellules du jumeau le comptent comme un adulte de plus "
            f"({millions(p['types']['complexe'])}). Les familles monoparentales et les "
            f"couples avec enfants des cellules sont moins nombreux d'autant.</li>",
            f"<li><strong>L'échantillon est grand, pas infini.</strong> Après calage, il "
            f"vaut {_entier(cal['effective_sample_size'])} ménages indépendants : un "
            f"groupe rare (les très hauts revenus, un département d'outre-mer) repose sur "
            f"peu de ménages.</li></ul>",
            f'<p class="note-source">Les causes : les entrées de décision D-363 à D-371, '
            f"et {fichier('reports/reconciliation.md')}.</p></section>",
            f'<p class="suite">Suite : <a href="{COMME_MOI}">un ménage comme le mien</a> · '
            f'<a href="{CELLULES}">les cellules publiées</a></p>']
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# population-comme-moi.html
# --------------------------------------------------------------------------- #
def donnees_comme_moi(d: dict[str, Any]) -> dict[str, Any]:
    c = d["cellules_menages"]["valeurs"]
    garder = ("menages", "personnes", "uc", "salaire_brut", "retraite", "chomage_brut",
              "revenus_non_salaries", "prestations", "cotisations_salariales",
              "csg_crds_salaires", "ir", "tva", "accises", "revenu_disponible",
              "consommation", "en_emploi")
    m = json.loads(MENAGES_TYPES.read_text(encoding="utf-8"))
    cas = {}
    for s in m["situations"]:
        if s["cle"] in CAS_TYPES.values():
            cas[s["cle"]] = {"libelle": s["libelle"], "points": [
                {k: round(x.get(k, 0.0), 2) for k in (
                    "salaire_brut", "cotisations_salariales", "csg_deductible",
                    "csg_imposable", "crds", "ir", "prestations", "revenu_disponible")}
                for x in s["valeurs"]]}
    return {"types": list(TYPES), "libelles": TYPES_LIBELLES, "cas_types": CAS_TYPES,
            "cellules": {k: [round(x, 2) for x in c[k]] for k in garder},
            "salaires": m["salaires"], "cas": cas, "annee": m["annee"]}


def page_comme_moi(d: dict[str, Any]) -> str:
    opts = "".join(f'<option value="{t}"' + (" selected" if t == "couple_avec_enfants"
                                              else "") + f">{e(TYPES_LIBELLES[t])}</option>"
                   for t in TYPES)
    donnees = json.dumps(donnees_comme_moi(d), ensure_ascii=False,
                         separators=(",", ":")).replace("</", "<\\/")
    return "\n".join([
        nav(COMME_MOI), "<h1>Un ménage comme le mien</h1>",
        "<p class=\"chapeau\">Dites, à grands traits, qui vit chez vous et ce que le ménage "
        "a pour vivre chaque mois. La page cherche le groupe de ménages simulés qui vous "
        "ressemble le plus, dit combien de vrais ménages il représente, ce qu'ils paient "
        "et ce qu'ils reçoivent en moyenne. Rien n'est envoyé : le calcul se fait dans "
        "votre navigateur. Vous ne voyez jamais un ménage, seulement les moyennes de "
        "groupes de dizaines ou de centaines de milliers de ménages.</p>",
        '<section id="choisir"><h2>Vos traits</h2><form class="traits" '
        'onsubmit="return false">',
        f'<label for="type">Qui vit chez vous ?</label><select id="type">{opts}</select>',
        '<label for="enfants" id="enfants-l">Enfants de moins de 14 ans</label>'
        '<input id="enfants" type="number" min="0" max="6" value="2" inputmode="numeric">',
        '<label for="revenu">Ce que le ménage a pour vivre, par mois <span class="aide">'
        "(après impôts, allocations comprises)</span></label>"
        '<div class="curseur"><input id="revenu" type="range" min="500" max="15000" '
        'step="100" value="3500"><output id="revenu-dit" for="revenu">3 500 € par mois'
        "</output></div></form>",
        '<div id="resultat" aria-live="polite"><p class="sans-script">Cette partie '
        "demande JavaScript. Sans lui, les 50 groupes se lisent dans "
        f'<a href="{CELLULES}#menages">le tableau des cellules</a>.</p></div></section>',
        '<section id="comment"><h2>Comment la page vous range</h2>',
        "<p>Votre <strong>niveau de vie</strong> est ce que le ménage a pour vivre, divisé "
        "par ses unités de consommation (1 pour le premier adulte, 0,5 par autre adulte, "
        "0,3 par enfant de moins de 14 ans ; un ménage complexe compte ici trois adultes). "
        "Parmi les dix dixièmes de ménages de votre type, la page prend celui dont le "
        "niveau de vie moyen est le plus proche du vôtre, en proportion. C'est une "
        "approximation : une cellule n'a qu'une moyenne, pas de bornes.</p>",
        "<p>Le <strong>cas type</strong> est un ménage chiffré d'avance par le moteur, "
        "salarié, au droit de 2024 : il dit ce que la loi fait à ce ménage précis. La "
        "cellule dit ce que vivent en moyenne des ménages réels, avec leurs retraites, "
        "leur chômage, leurs revenus d'indépendant.</p>",
        f'<p class="note-source">Les cellules : '
        f'{fichier("reports/jumeau/entrees_navigateur.json")} ; les cas types : '
        f"{fichier('reports/parcours/menages.json')}.</p></section>",
        f'<script type="application/json" id="donnees-comme-moi">{donnees}</script>',
        f'<script src="{SCRIPT}"></script>'])


# --------------------------------------------------------------------------- #
# cellules.html
# --------------------------------------------------------------------------- #
def _chaleur(valeurs: list[float], fmt, titre: str) -> str:
    haut = max(valeurs) or 1.0
    tete = "".join(f'<th scope="col">{e(TYPES_LIBELLES[t])}</th>' for t in TYPES)
    rangs = []
    for k in range(10):
        cases = []
        for j in range(len(TYPES)):
            x = valeurs[k * len(TYPES) + j]
            part = max(0.0, x / haut)
            cases.append(f'<td style="--p:{100 * part:.0f}%"'
                         + (' class="fonce"' if part > 0.55 else "") + f">{fmt(x)}</td>")
        rangs.append(f'<tr><th scope="row">{k + 1}</th>{"".join(cases)}</tr>')
    return (f'<div class="defile" tabindex="0"><table class="chaleur"><caption>{e(titre)}'
            f'</caption><thead><tr><th scope="col">Dixième</th>{tete}</tr></thead><tbody>'
            f'{"".join(rangs)}</tbody></table></div>')


def page_cellules(d: dict[str, Any]) -> str:
    cm = d["cellules_menages"]
    v = cm["valeurs"]
    lignes = cellules_menages(d)
    moy = [v["revenu_disponible"][i] / v["menages"][i] for i in range(len(v["menages"]))]
    defs = "".join(f"<dt>{e(a)} <code>{k}</code></dt><dd>{e(dfn)}"
                   + (" En euros par an." if u == "€" else "") + "</dd>"
                   for k, (a, u, dfn) in VARIABLES.items())
    corps = [[str(x["cellule"]), str(x["decile"]), e(TYPES_LIBELLES[x["type"]]),
              _entier(x["menages"]), _entier(x["personnes"]),
              euros(x["revenu_disponible"] / x["menages"]),
              euros(x["salaire_brut"] / x["menages"]), euros(x["retraite"] / x["menages"]),
              euros(x["prestations"] / x["menages"]), euros(x["ir"] / x["menages"]),
              euros(x["tva"] / x["menages"])] for x in lignes]
    rec = [x for x in cm["recoupements"] if "population entière" not in x["ligne"]]
    recoup = [[e(x["ligne"]), pct(x["ecart"], 1, True),
               ("±" + pct(x["tolerance"], 0)) if x["tolerance"] else "dit, sans verdict",
               e(x["source"])] for x in rec]
    f = d["cellules_entreprises"]
    fc = sorted(f["cellules"], key=lambda c: (c["naf_section"],
                                              list(TAILLES).index(c["taille"])))
    corps_f = [[f"{c['naf_section']} · {e(SECTIONS.get(c['naf_section'], ''))}",
                e(c["taille"]), _entier(c["n_firms"]), mds(c["turnover_total"], 1),
                mds(c["value_added_total"], 1), mds(c["result_total"], 2),
                pct(c["p_loss"], 0)] for c in fc]
    va: dict[str, float] = {}
    for c in f["cellules"]:
        va[c["naf_section"]] = va.get(c["naf_section"], 0.0) + c["value_added_total"]
    par_section = barres(sorted(((f"{s} · {SECTIONS[s]}", x, None) for s, x in va.items()),
                                key=lambda t: -t[1]), mds,
                         "Valeur ajoutée des cellules, par secteur")
    par_taille = barres([(TAILLES[t], sum(c["n_firms"] for c in f["cellules"]
                                          if c["taille"] == t), None) for t in TAILLES],
                        _entier, "Entreprises, par taille")
    srcs = " ; ".join(source(s["url"], s["fichier"]) for s in f["sources"].values())
    defs_f = "".join(f"<dt>{e(a)} <code>{k}</code></dt><dd>{e(dfn)}</dd>"
                     for k, (a, u, dfn) in VARIABLES_FIRMES.items())
    return "\n".join([
        nav(CELLULES), "<h1>Les cellules publiées</h1>",
        "<p class=\"chapeau\">Le jumeau ne lit pas la population ménage par ménage : il la "
        "lit résumée en 50 groupes de ménages et 57 groupes d'entreprises, les "
        "<strong>cellules</strong>. Les voici toutes, avec ce que chacune contient, sa "
        "définition et sa source. Ce sont des sommes sur des dizaines de milliers de "
        "ménages ou sur des entreprises regroupées, jamais un enregistrement.</p>",
        '<section id="menages"><h2>Les 50 cellules des ménages</h2>',
        "<p>Une cellule réunit les ménages d'un même <strong>dixième de niveau de "
        "vie</strong> (le 1<sup>er</sup> est le plus modeste) et d'un même <strong>type"
        "</strong>. Dix dixièmes fois cinq types : cinquante cellules. Le dixième, parce "
        "que les gagnants et les perdants d'une mesure se lisent ainsi ; le type, parce "
        "que c'est la typologie de l'Insee et que les comportements de travail en "
        "dépendent.</p>",
        _chaleur(v["menages"], lambda x: f"{_entier(x / 1000)}{NBSP}k",
                 "Combien de ménages dans chaque cellule (en milliers)"),
        _chaleur(moy, lambda x: f"{_entier(x / 1000)}{NBSP}k€",
                 "Revenu disponible moyen d'un ménage de la cellule (milliers d'euros par an)"),
        "<h3>Les 50 cellules, ligne à ligne</h3>",
        "<p>Les montants sont des moyennes par ménage : la somme de la cellule sur son "
        "nombre de ménages. Toutes les variables, en sommes, sont dans les fichiers à "
        '<a href="#telecharger">télécharger</a>.</p>',
        tableau(["n°", "Dixième", "Type", "Ménages", "Personnes", "Revenu disponible",
                 "Salaires bruts", "Retraites", "Prestations", "Impôt sur le revenu",
                 "TVA"], corps, "Par ménage, euros de 2024 par an", "chiffres serre"),
        "<h3>Ce que chaque variable veut dire</h3>", f"<dl class=\"definitions\">{defs}</dl>",
        "<h3>D'où elles viennent</h3>",
        f"<p>Une passe de la loi de {cm['annee']} sur {_entier(cm['echantillon'])} ménages "
        f"tirés de la population (graine {cm['graine']}), avec les imputations "
        f"{e(', '.join(cm['imputations']))}, faite le {cm['construites']} au commit "
        f"<code>{cm['commit'][:7]}</code> (D-409). Chaque total est recoupé aux totaux "
        "publiés, avec une tolérance écrite avant :</p>",
        tableau(["Recoupement", "Écart", "Tolérance", "Source"], recoup, "", "chiffres"),
        f'<p class="note-source">'
        f'{fichier("src/impots/jumeau/cellules.py", "jumeau/cellules.py")}'
        f" · {fichier('reports/jumeau/entrees_navigateur.json')}</p></section>",
        '<section id="entreprises"><h2>Les 57 cellules des entreprises</h2>',
        f"<p>Les entreprises soumises à l'impôt sur les sociétés, millésime {f['millesime']}, "
        f"rangées par <strong>secteur</strong> (section NAF) et par <strong>taille</strong>. "
        f"Elles viennent des tableaux publiés de l'Insee (Ésane) et de la DGFiP, pas de "
        f"fichiers d'entreprises : {_entier(f['entreprises_is'])} entreprises soumises à "
        f"l'IS, sur les {_entier(f['entreprises_esane'])} d'Ésane. Les "
        f"{len(f['cellules_secretisees'])} cases que le secret statistique supprime sont "
        f"absentes ou complétées, et dites dans le fichier JSON.</p>",
        '<div class="grille-2">', par_section, par_taille, "</div>",
        tableau(["Secteur", "Taille", "Entreprises", "Chiffre d'affaires", "Valeur ajoutée",
                 "Résultat", "Part en perte"], corps_f, "Les 57 cellules", "chiffres serre"),
        f"<dl class=\"definitions\">{defs_f}</dl>",
        f'<p class="note-source">Sources : {srcs}. Le résultat fiscal vaut '
        f"{_dec(f['fiscal_sur_comptable'], 2)} fois le résultat comptable, en moyenne. "
        f"{fichier('src/impots/jumeau/blocs/entreprises.py', 'jumeau/blocs/entreprises.py')}"
        "</p></section>",
        '<section id="telecharger"><h2>Télécharger</h2><ul class="telecharger">',
        '<li><a href="cellules-menages.csv" download>Les 50 cellules des ménages (CSV)</a> '
        "— une ligne par cellule, toutes les variables, en sommes</li>",
        '<li><a href="cellules-menages.json" download>Les 50 cellules des ménages (JSON)</a> '
        "— avec les définitions et la source</li>",
        '<li><a href="cellules-entreprises.csv" download>Les 57 cellules des entreprises '
        "(CSV)</a></li>",
        '<li><a href="cellules-entreprises.json" download>Les 57 cellules des entreprises '
        "(JSON)</a> — avec les définitions, les sources et les cases secrétisées</li>",
        "</ul><p class=\"note-source\">Les données dérivent de sources publiques sous "
        "licence ouverte (Etalab 2.0).</p></section>"])


# --------------------------------------------------------------------------- #
# l'assemblage
# --------------------------------------------------------------------------- #
#: Les pages qui portent un script (le site refuse un script ailleurs).
SCRIPTEES = frozenset({COMME_MOI})


def build() -> dict[str, str]:
    """Les pages, la feuille de style, le script et les fichiers des cellules."""
    from impots import site

    d = lire()
    pages = {PAGE: ("La population simulée", page_population(d)),
             FRANCE: ("Ressemble-t-elle à la France ?", page_france(d)),
             COMME_MOI: ("Un ménage comme le mien", page_comme_moi(d)),
             CELLULES: ("Les cellules publiées", page_cellules(d))}
    pied = (f"<p>Agrégats écrits par <code>{e(d['commande'])}</code> le {d['date']}, au "
            f"commit <code>{d['commit'][:7]}</code>, sur "
            f"<code>{e(d['population_fichier'])}</code> (empreinte "
            f"<code>{d['population_sha256'][:12]}</code>), sans passe.</p>")
    files = {}
    for nom, (titre, main) in pages.items():
        texte = site._page(f"{titre} — {site.TITLE}", main, pied, liens=False)
        # La légende des étages de confiance parle des nombres d'étude : ces pages n'en
        # portent pas.
        texte = texte.replace(f"\n{site._legend()}\n", "\n")
        files[nom] = texte.replace('<link rel="stylesheet" href="style.css">',
                                   '<link rel="stylesheet" href="style.css">\n'
                                   f'<link rel="stylesheet" href="{STYLE}">')
    files[STYLE] = (ICI / "population.css").read_text(encoding="utf-8")
    files[SCRIPT] = (ICI / "comme_moi.js").read_text(encoding="utf-8")
    files.update(fichiers_cellules(d))
    return files
