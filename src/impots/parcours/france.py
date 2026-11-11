"""Page 2 du parcours : la France simulée (but 20, D-375).

Elle prouve que la population ressemble à la France sur ce qu'on ne lui a pas imposé, et
dit où elle ne lui ressemble pas. Trois sortes de nombres y sont séparées : ce qui est
observé (la structure des ménages, l'enquête Emploi), ce qui est tiré (les revenus, sur
des distributions publiées), ce qui est calé (des totaux publiés, que le calage
« dépense » : une ligne calée ne prouve rien). Puis la grille de vérification entière, sur
les trois passes commitées de 2022, 2023 et 2024 (`reports/verification/passe_*.json`).

RIEN N'EST CALCULÉ ICI QUE LA GRILLE NE CALCULE DÉJÀ. Les écarts sont ceux de
`verification.grille()`, qui lit `docs/verification/lignes.json` et les passes ; les
totaux calés sont les `Figure` de `population/margins.py` déclarées « calibration ». Le
curseur choisit une année parmi les trois passes : le script montre l'une et cache les
deux autres, il ne fait aucun calcul. Sans lui, les trois années se lisent l'une sous
l'autre.
"""

from __future__ import annotations

import html
import re
from typing import Any

from impots import verification
from impots.parcours import Page, fichier, lien, source

ANNEES = (2022, 2023, 2024)
#: Les lignes de la grille qui comptent des foyers, et non des euros.
_COMPTES = re.compile(r"(^|_)foyers")
#: Les foyers par taux marginal, dans l'ordre du barème.
TMI = ("foyers_tmi_0", "foyers_tmi_1", "foyers_tmi_2", "foyers_tmi_3", "foyers_tmi_4")
#: Le niveau de vie : au plein recours (le concept des lignes de D-363), et avec les
#: prestations pondérées par la probabilité de les demander (D-365, D-366).
NIVEAU_DE_VIE = ("niveau_de_vie_median", "niveau_de_vie_median_servi", "d9_d1",
                 "d9_d1_servi")
#: L'enquête Emploi, fichier détail 2024 (Licence Ouverte), d'où vient la structure des
#: ménages (`scripts/verify_eec.py`).
EEC_URL = "https://www.insee.fr/fr/statistiques/8632441"
#: Des liens de `population/margins.py` qui ne répondent plus (404, relevé le 2026-11-11),
#: et l'adresse que la page affiche à leur place. margins.py n'est pas touché ici.
#: CHILDREN_DISTRIBUTION : le tableau FAM1 du recensement 2023, France entière, qui donne
#: 9 340 128 familles avec au moins un enfant de moins de 25 ans. SICK_PAY_BY_BRANCH : le
#: rapport de mai 2026 de la CCSS, tel que `data/raw/MANIFEST.json` l'a téléchargé.
URL_CORRIGEES = {
    "https://www.insee.fr/fr/statistiques/8268533":
        "https://www.insee.fr/fr/statistiques/9005622?geo=FE-1",
    "https://www.securite-sociale.fr/la-secu-en-detail/comptes-de-la-securite-sociale":
        "https://www.securite-sociale.fr/files/live/sites/SSFR/files/medias/CCSS/2026/"
        "CCSS%20mai%202026_assembl%c3%a9_V2.pdf",
}
#: Pourquoi une ligne est refusée une année, en clair (la remarque de `lignes.json` parle
#: la langue du dépôt). Une ligne absente d'ici garde sa remarque, raccourcie.
REFUS = {
    "ir_bareme": "aucun total publié trouvé pour cette année",
    "rsa_foyers": "pour 2022, seul un arrondi d'un autre champ est publié",
    "rsa_foyers_servis": "pour 2022, seul un arrondi d'un autre champ est publié",
    "cvae": "le barème de la CVAE du moteur ne commence qu'en 2024",
    "tva_menages": "aucun total publié pour les seuls ménages",
    "accises_menages": "aucun total publié pour les seuls ménages",
    "foyers_fiscaux_residents_hors_mayotte": "le fichier de la DGFiP de cette année (IRCOM) "
                                             "n'a pas été relu",
}


# --------------------------------------------------------------------------- #
# Les nombres, à la française
# --------------------------------------------------------------------------- #

def pct(x: float | None, chiffres: int = 1) -> str:
    """Un écart relatif signé : « −8,2 % »."""
    if x is None:
        return "—"
    return f"{x * 100:+.{chiffres}f} %".replace(".", ",").replace("-", "−")


def _groupe(x: float, chiffres: int = 0) -> str:
    return f"{x:,.{chiffres}f}".replace(",", "\u202f").replace(".", ",")


def valeur(ligne_id: str, x: float | None) -> str:
    """Un total de la grille, dans son unité : des foyers, des euros par an et par unité
    de consommation, un rapport, ou des milliards d'euros."""
    if x is None:
        return "—"
    if _COMPTES.search(ligne_id):
        return f"{_groupe(x / 1e6, 2)} M"
    if ligne_id.startswith("niveau_de_vie"):
        return f"{_groupe(x)} €"
    if ligne_id.startswith("d9_d1"):
        return _groupe(x, 2)
    return f"{_groupe(x / 1e9, 1)} Md€"


def _figure(fig: Any) -> str:
    """La valeur d'une `Figure` de `margins.py`, dans son unité."""
    v, unit = fig.value, fig.unit
    if unit == "EUR":
        return f"{_groupe(v / 1e9, 2)} Md€" if abs(v) >= 1e9 else f"{_groupe(v)} €"
    if unit == "count":
        return f"{_groupe(v / 1e6, 2)} M" if v >= 1e6 else _groupe(v)
    if unit == "ratio":
        return _groupe(v, 3)
    if unit == "EUR_per_m2_per_month":
        return f"{_groupe(v, 2)} €/m²/mois"
    return f"{_groupe(v, 2)} {html.escape(unit)}"


def _court(texte: str, n: int = 80) -> str:
    """Le début d'une description de périmètre, jusqu'à sa première incise."""
    tete = re.split(r" — |; | \(|: ", texte, maxsplit=1)[0].strip().rstrip(",")
    return tete if len(tete) <= n else tete[: n - 1].rstrip() + "…"


def lien_source(url: str | None, texte: str, titre: str = "") -> str:
    """Une source publique, avec sa localisation au survol ; `source()` du parcours,
    plus le titre."""
    if not url:
        return ""
    a = source(URL_CORRIGEES.get(url, url), texte)
    return a.replace(">", f' title="{html.escape(titre)}">', 1) if titre else a


def _editeur(src: str | None) -> str:
    """Le nom court d'une source : « Insee », « DGFiP », « Cnaf »…"""
    if not src:
        return "source"
    tete = re.split(r"[,(«/]", src, maxsplit=1)[0].strip()
    return tete if len(tete) <= 28 else tete[:27].rstrip() + "…"


# --------------------------------------------------------------------------- #
# La grille, lue
# --------------------------------------------------------------------------- #

def grille() -> list[dict[str, Any]]:
    """Les lignes de la grille, chacune avec son simulé, son écart et son verdict, depuis
    les trois passes commitées (`verification.grille`)."""
    return verification.grille()


def par_ligne(rows: list[dict[str, Any]]) -> dict[str, dict[int, dict[str, Any]]]:
    """Les lignes par identifiant, puis par année, dans l'ordre de `lignes.json`."""
    out: dict[str, dict[int, dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["id"], {})[r["annee"]] = r
    return out


def notees(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rows if r["usage"] == "validation" and r.get("ecart") is not None]


def compte(rows: list[dict[str, Any]], annee: int | None = None) -> tuple[int, int]:
    """(tenues, notées), sur toutes les années ou sur une."""
    n = [r for r in notees(rows) if annee is None or r["annee"] == annee]
    return sum(r["verdict"] == "dans la tolérance" for r in n), len(n)


def commits(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({r["commit"][:7] for r in rows if r.get("commit")})


_ETAT = {"dans la tolérance": ("tenue", "tenue"), "hors de la tolérance": ("hors", "hors"),
         "contexte": ("contexte", "contexte"), "calibration": ("calee", "calée, dépensée"),
         "refusée": ("refusee", "refusée")}


def _cellule(r: dict[str, Any] | None) -> str:
    if r is None:
        return '<td class="vide">—</td>'
    cls, mot = _ETAT.get(r["verdict"], ("", r["verdict"]))
    annee = r["annee"]
    titre = " — ".join(x for x in (r.get("source"), r.get("localisation")) if x)
    if r["verdict"] == "refusée":
        raison = REFUS.get(r["id"]) or _court(r.get("remarque") or "", 90)
        corps = (f'<span class="etat">refusée</span><br><small>'
                 f'{html.escape(raison)}</small>')
    else:
        corps = (f'<span class="num">{pct(r["ecart"])}</span> <span class="etat">{mot}'
                 f"</span><br><small>{valeur(r['id'], r['simule'])} contre "
                 f"{valeur(r['id'], r['publie'])}</small>")
    lien_ = lien_source(r.get("url"), _editeur(r.get("source")), titre)
    return (f'<td class="{cls}" data-annee="{annee}">{corps}'
            + (f"<br><small>{lien_}</small>" if lien_ else "") + "</td>")


def table_grille(rows: list[dict[str, Any]]) -> str:
    """La grille entière : une ligne par instrument, une colonne par année, chaque total
    publié avec le lien de sa source et, au survol, l'onglet et la ligne lus."""
    head = ("<tr><th>ligne</th><th>tolérance</th>"
            + "".join(f'<th data-annee="{a}">{a}</th>' for a in ANNEES) + "</tr>")
    body = []
    for ident, ans in par_ligne(rows).items():
        premier = next(iter(ans.values()))
        tol = premier.get("tolerance")
        tol_txt = "—" if tol is None else f"±{tol * 100:.0f} %"
        body.append(f'<tr id="ligne-{ident}"><th scope="row">{html.escape(premier["ligne"])}'
                    f"</th><td>{tol_txt}</td>"
                    + "".join(_cellule(ans.get(a)) for a in ANNEES) + "</tr>")
    return (f'<table class="grille" data-choisie="">\n<thead>{head}</thead>\n<tbody>\n'
            + "\n".join(body) + "\n</tbody></table>")


# --------------------------------------------------------------------------- #
# Les vues d'une année
# --------------------------------------------------------------------------- #

def _barres_tmi(lignes: dict[str, dict[int, dict[str, Any]]], annee: int,
                plus_grand: float) -> str:
    rangs = []
    for ident in TMI:
        r = lignes[ident].get(annee)
        if r is None or r.get("simule") is None:
            continue
        taux = re.search(r"(\d+) %", r["ligne"])
        pub, sim = r["publie"], r["simule"]
        rangs.append(
            f'<div class="tmi"><span class="taux">{taux[1] if taux else "?"} %</span>'
            f'<span class="b"><i class="pub" style="width:{100 * pub / plus_grand:.1f}%">'
            f'</i><i class="sim" style="width:{100 * sim / plus_grand:.1f}%"></i></span>'
            f'<span class="num">{valeur(ident, pub)}<br>{valeur(ident, sim)}</span>'
            f'<span class="num {_ETAT[r["verdict"]][0]}">{pct(r["ecart"])}</span></div>')
    return ('<div class="barres" role="group" aria-label="Foyers par taux marginal, '
            f'{annee}"><div class="tmi legende"><span></span><span>'
            '<i class="pub"></i> DGFiP <i class="sim"></i> simulé</span>'
            "<span>DGFiP<br>simulé</span><span>écart</span></div>" + "".join(rangs)
            + "</div>")


def _niveau_de_vie(lignes: dict[str, dict[int, dict[str, Any]]], annee: int) -> str:
    rows = []
    for ident in NIVEAU_DE_VIE:
        r = lignes[ident].get(annee)
        if r is None:
            continue
        rows.append(f"<tr><td>{html.escape(r['ligne'])}</td>"
                    f'<td class="num">{valeur(ident, r["simule"])}</td>'
                    f'<td class="num">{valeur(ident, r["publie"])}</td>'
                    f'<td class="num {_ETAT[r["verdict"]][0]}">{pct(r["ecart"])}</td>'
                    f"<td>±{r['tolerance'] * 100:.0f} %</td></tr>")
    src = lignes["niveau_de_vie_median"][annee]
    return ("<table><thead><tr><th></th><th>simulé</th><th>publié (ERFS)</th>"
            "<th>écart</th><th>tolérance</th></tr></thead><tbody>" + "".join(rows)
            + "</tbody></table><p><small>Source de l'année : "
            + lien_source(src["url"], src["source"], src.get("localisation") or "")
            + ".</small></p>")


def _hors(rows: list[dict[str, Any]], annee: int) -> str:
    items = [f'<li><a href="#ligne-{r["id"]}">{html.escape(r["ligne"])}</a> : '
             f'<span class="num">{pct(r["ecart"])}</span>, pour ±'
             f"{r['tolerance'] * 100:.0f} %</li>"
             for r in notees(rows)
             if r["annee"] == annee and r["verdict"] == "hors de la tolérance"]
    return "<ul>" + "".join(items) + "</ul>"


def vue_annee(rows: list[dict[str, Any]], annee: int, plus_grand: float) -> str:
    lignes = par_ligne(rows)
    tenues, n = compte(rows, annee)
    return (f'<section class="vue-annee" data-annee="{annee}" aria-live="polite">\n'
            f"<h3>{annee}</h3>\n"
            f'<p><strong><span class="num">{tenues}</span> lignes sur '
            f'<span class="num">{n}</span></strong> tiennent leur tolérance en {annee}. '
            f"La population est celle de 2024, ramenée à {annee} par les prix et les "
            f"salaires constatés ; la loi est celle de {annee}.</p>\n"
            f"<h4>Les foyers par taux marginal d'imposition, simulés contre la DGFiP</h4>\n"
            + _barres_tmi(lignes, annee, plus_grand)
            + "\n<h4>Le niveau de vie médian et le rapport D9/D1</h4>\n"
            + _niveau_de_vie(lignes, annee)
            + f"\n<h4>Les lignes hors de leur tolérance en {annee}</h4>\n"
            + _hors(rows, annee) + "\n</section>")


# --------------------------------------------------------------------------- #
# Observé, tiré, calé
# --------------------------------------------------------------------------- #

def _calees() -> list[Any]:
    from impots.population import margins

    return list(margins.figures_by_use("calibration").items())


def table_calees(rows: list[dict[str, Any]]) -> str:
    out = []
    for name, fig in _calees():
        out.append(f"<tr><td>{html.escape(_court(fig.scope))}</td>"
                   f'<td class="num">{_figure(fig)}</td><td>{fig.year}</td>'
                   f"<td>{lien_source(fig.url, _editeur(fig.source), fig.source)}</td>"
                   f"<td><code>{html.escape(name)}</code></td></tr>")
    for r in rows:
        if r["usage"] == "calibration":
            out.append(f"<tr><td>{html.escape(r['ligne'])} (ligne de la grille, "
                       f"{r['annee']})</td>"
                       f'<td class="num">{valeur(r["id"], r["publie"])}</td>'
                       f"<td>{r['annee']}</td>"
                       f"<td>{lien_source(r.get('url'), _editeur(r.get('source')), r.get('localisation') or '')}</td>"
                       f"<td>retrouvée à {pct(r['ecart'])} : <em>dépensée</em></td></tr>")
    return ("<table><thead><tr><th>ce qui est calé</th><th>total</th><th>année</th>"
            "<th>source</th><th>son nom dans margins.py</th></tr></thead><tbody>"
            + "".join(out) + "</tbody></table>")


def _salaires() -> str:
    from impots.population import margins

    c = margins.WAGE_CENTILES_PRIVATE_NET_EQTP_MONTHLY
    return (f"la moitié des salariés du privé gagne moins de "
            f"<span class=\"num\">{_groupe(c[0.50])} €</span> net par mois en équivalent "
            f"temps plein, un sur dix plus de <span class=\"num\">{_groupe(c[0.90])} €"
            f"</span>")


def salaires_declares(lignes: dict[str, dict[int, dict[str, Any]]]) -> str:
    """Pourquoi la ligne « Salaires déclarés » de la grille n'est pas un total calé, et en
    quoi elle n'est pas indépendante du calage (D-366)."""
    from impots.population import margins

    salaries = margins.DECLARED_TAXABLE_WAGES
    gerants = margins.GERANTS_REMUNERATION
    r = lignes["salaires_declares"][salaries.year]
    cale = salaries.value + gerants.value
    return (
        f"<p><strong>La ligne « {html.escape(r['ligne'])} » de la grille n'est pas un de "
        f"ces totaux, mais elle n'en est pas indépendante.</strong> La population est calée "
        f"sur les salaires imposables des salariés ({_figure(salaries)}) et sur ceux des "
        f"gérants ({_figure(gerants)}) : ensemble "
        f"<span class=\"num\">{_groupe(cale / 1e9, 2)} Md€</span> en {salaries.year}. La "
        f"population simulée en déclare <span class=\"num\">{valeur(r['id'], r['simule'])}"
        f"</span> : à peu près ce qu'on lui a imposé. Le total publié auquel la grille la "
        f"compare, <span class=\"num\">{valeur(r['id'], r['publie'])}</span>, est la ligne "
        f"« traitements et salaires » de la DGFiP, d'un périmètre plus large : il compte "
        f"aussi les allocations chômage et les heures supplémentaires, que les deux totaux "
        f"calés ne comptent pas (D-366). L'écart de {pct(r['ecart'])} mesure donc surtout "
        f"cette différence de périmètre, pas la ressemblance de la population : la ligne est "
        f"notée telle qu'elle a été préenregistrée, mais elle tient sa tolérance de ±10 % "
        f"aussi longtemps que ce qui sort du périmètre calé pèse moins de 10 % du total "
        f"publié, quelle que soit la population.</p>")


def foyers_identiques(lignes: dict[str, dict[int, dict[str, Any]]]) -> str:
    """Le nombre de foyers simulés, s'il est le même les trois années : la preuve à l'œil
    que la population est la même."""
    ans = lignes.get("foyers_fiscaux", {})
    simules = {round(r["simule"]) for r in ans.values() if r.get("simule") is not None}
    if len(ans) != len(ANNEES) or len(simules) != 1:
        return ""
    return (f" Les foyers fiscaux simulés en donnent la mesure : "
            f"<span class=\"num\">{valeur('foyers_fiscaux', simules.pop())}</span> en "
            f"2022, en 2023 et en 2024, le même nombre, parce que ce sont les mêmes foyers.")


GLOSSAIRE = """<p><strong>Les mots de la grille.</strong> Les libellés viennent du fichier
des lignes ; trois d'entre eux demandent une traduction.</p>
<ul>
<li><strong>Bandeau maladie, bandeau famille</strong> : deux baisses de cotisations
patronales, l'une sur l'assurance maladie (7 % au lieu de 13 %), l'autre sur les
allocations familiales (3,45 % au lieu de 5,25 %), pour les salaires sous un plafond
(2,5 et 3,5 SMIC en 2024). La « réduction générale » est l'allègement dégressif qui
s'annule à 1,6 SMIC.</li>
<li><strong>Servi en espérance</strong> : chaque foyer reçoit son droit au RSA ou à la
prime d'activité multiplié par la probabilité qu'il le demande. C'est ainsi que les
études comptent le non-recours.</li>
<li><strong>Pont de non-recours</strong> : l'ancienne façon de le compter, un seul
coefficient de la Drees (1,355 pour le RSA, 1,725 pour la prime) qui divise le total des
droits pour retrouver le total versé. Les lignes « pont » restent notées telles qu'elles
ont été préenregistrées.</li>
</ul>"""


# --------------------------------------------------------------------------- #
# La page
# --------------------------------------------------------------------------- #

SCRIPT = """\
(function () {
  var choix = document.getElementById("choix-annee");
  var menu = document.getElementById("annee");
  if (!choix || !menu) { return; }
  choix.hidden = false;
  var vues = document.querySelectorAll("section.vue-annee");
  var tables = document.querySelectorAll("table.grille");
  function montre() {
    var a = menu.value;
    for (var i = 0; i < vues.length; i++) {
      vues[i].hidden = vues[i].getAttribute("data-annee") !== a;
    }
    for (var j = 0; j < tables.length; j++) {
      tables[j].setAttribute("data-choisie", a);
    }
  }
  menu.addEventListener("change", montre);
  montre();
})();
"""

STYLE = """
.num{white-space:nowrap}
.barres{font:.85rem/1.3 system-ui,sans-serif;margin:.6rem 0}
.tmi{display:grid;grid-template-columns:3.2rem minmax(0,1fr) 5.2rem 4.2rem;gap:.2rem .5rem;align-items:center;margin:.25rem 0}
.tmi .b{display:flex;flex-direction:column;gap:2px}
.tmi i{display:block;height:.55rem;min-width:1px}
.tmi.legende{color:var(--doux);font-size:.75rem}
.tmi.legende i{display:inline-block;width:.8rem;height:.55rem;vertical-align:middle}
i.pub{background:var(--doux)}
i.sim{background:var(--texte)}
td.tenue .etat,.num.tenue{color:inherit}
td.hors,.num.hors{background:var(--l4)}
td.refusee,td.vide{color:var(--doux)}
td.contexte .etat,td.calee .etat{font-style:italic}
table.grille small{color:var(--doux)}
table.grille[data-choisie="2022"] [data-annee="2022"],
table.grille[data-choisie="2023"] [data-annee="2023"],
table.grille[data-choisie="2024"] [data-annee="2024"]{outline:2px solid var(--trait);outline-offset:-2px}
@media (max-width:560px){.tmi{grid-template-columns:2.6rem minmax(0,1fr) 4.6rem 3.8rem}}
"""


def page() -> Page:
    rows = grille()
    lignes = par_ligne(rows)
    tenues, n = compte(rows)
    hors = n - tenues
    refusees = sum(r["verdict"] == "refusée" for r in rows)
    contexte = sum(r["verdict"] == "contexte" for r in rows)
    calees = len(_calees()) + sum(r["usage"] == "calibration" for r in rows)
    plus_grand = max(max(r["publie"], r["simule"] or 0.0)
                     for ident in TMI for r in lignes[ident].values()
                     if r.get("simule") is not None)
    par_annee = " ; ".join(f"{a} : {compte(rows, a)[0]} sur {compte(rows, a)[1]}"
                           for a in ANNEES)
    vues = "\n".join(vue_annee(rows, a, plus_grand) for a in ANNEES)
    options = "".join(f'<option value="{a}"{" selected" if a == ANNEES[-1] else ""}>{a}'
                      "</option>" for a in ANNEES)
    commit = ", ".join(f"<code>{c}</code>" for c in commits(rows))

    corps = f"""
<p>Une réforme se chiffre en faisant tourner la loi sur une population : des ménages
qui ressemblent aux ménages français, avec leurs salaires, leurs retraites, leurs
enfants et leurs loyers. Personne ne peut publier les vrais ménages ; l'outil en
construit d'autres. Cette page dit comment, et surtout comment savoir s'ils ressemblent
à la France. Les nombres y sont de trois sortes, et elles ne prouvent pas la même
chose.</p>

<h2 id="observe">Observé : la structure des ménages</h2>
<p>Qui vit dans quel logement, le sexe, l'âge (par tranches), l'activité, le statut
d'occupation du logement et le type de commune viennent de l'enquête Emploi de l'Insee,
un fichier public sous Licence Ouverte
({source(EEC_URL, "Insee, enquête Emploi 2024, fichier détail")}). Pour chaque personne en
emploi, l'enquête dit aussi si elle est salariée ou indépendante, sa catégorie
socioprofessionnelle (cadre, profession intermédiaire, employé, ouvrier), son temps de
travail et son employeur (le privé, ou l'un des trois versants de la fonction publique).
Ce sont de vrais ménages, interrogés, pondérés par l'Insee. L'enquête ne donne en revanche
<strong>aucun revenu</strong>, ni salaire, ni tranche de salaire ; elle n'interroge pas les
enfants de moins de 15 ans ; elle ne dit ni la région, ni qui est le conjoint ou l'enfant
de qui. Tout cela est construit : les liens sont déduits de la composition du logement,
les jeunes enfants et les revenus sont tirés. Le code :
{fichier("src/impots/population/skeleton.py")}.</p>

<h2 id="tire">Tiré : les revenus</h2>
<p>Chaque salaire est tiré sur les centiles publiés par l'Insee : {_salaires()}
({source("https://www.insee.fr/fr/statistiques/fichier/8657156/ip2079.xlsx",
"Insee Première n° 2079")}, et les déciles de la fonction publique,
{source("https://www.insee.fr/fr/statistiques/fichier/8733095/ECRT2026_F29.xlsx",
"Insee, Siasp 2024")}). Le tirage se fait en deux temps. D'abord un salaire provisoire,
tiré au hasard sur la courbe publiée de la catégorie socioprofessionnelle de la personne,
corrigé de son âge et de son sexe : ce que l'enquête observe ne fixe pas le salaire, il
fixe seulement la courbe sur laquelle on tire. Ce tirage range chaque salarié parmi ceux
de son secteur ; le montant qu'il reçoit est lu, à ce rang, sur les centiles publiés du
secteur, puis réduit par son temps de travail. Les revenus des indépendants suivent l'{source(
"https://www.insee.fr/fr/statistiques/9013403", "Insee Première n° 2114")}. Les
distributions et leurs sources sont dans {fichier("src/impots/population/margins.py")} ;
le tirage, dans {fichier("src/impots/population/incomes.py")}. Un revenu tiré n'est pas
observé : il a la forme publiée, mais il n'est celui de personne.</p>

<h2 id="cale">Calé : les totaux, dépensés</h2>
<p>Les poids des ménages sont ensuite ajustés pour que la population retrouve
<span class="num">{calees}</span> totaux publiés : la masse des salaires, le nombre de
ménages, les retraites déclarées, les locataires… Une population calée sur un total le
retrouve <em>parce qu'on l'y a forcée</em>. Ce total est <strong>dépensé</strong> : il ne
peut plus servir à vérifier quoi que ce soit, et la grille ci-dessous n'en note aucun.</p>
{table_calees(rows)}
{salaires_declares(lignes)}

<h2 id="grille">Ce qui se vérifie : la grille, sur trois ans</h2>
<p>Restent les totaux que personne n'a imposés à la population : l'impôt qu'elle paie,
les foyers à chaque taux du barème, les prestations qu'elle touche, son niveau de vie.
Chacun est comparé à son total publié, pour 2022, 2023 et 2024, avec une tolérance
écrite <em>avant</em> le calcul (préenregistrée dans les D-363 et D-366 de
{fichier("docs/DECISIONS.md")}). Sur trois ans, <strong><span class="num">{tenues}</span>
lignes notées sur <span class="num">{n}</span></strong> tiennent leur tolérance,
<span class="num">{hors}</span> n'y tiennent pas ({par_annee}). À côté,
<span class="num">{refusees}</span> lignes sont refusées, faute d'un total publié ou d'un
droit que le moteur sert, et <span class="num">{contexte}</span> sont données pour
contexte, sans tolérance.</p>
<p><strong>Ces trois années ne sont pas trois épreuves.</strong> Il n'y a qu'une
population, celle de 2024. Pour 2022 et 2023, elle est ramenée en arrière par des indices
constatés (les prix et les salaires par tête), sans qu'un ménage change ni que son poids
bouge ; seule la loi est celle de l'année (D-362).{foyers_identiques(lignes)} Le compte de
<span class="num">{tenues}</span> sur <span class="num">{n}</span> compte donc la même
population trois fois, contre trois années de totaux publiés : il ne vaut pas
<span class="num">{n}</span> vérifications indépendantes.</p>
<p>Les totaux publiés, leurs sources et leurs tolérances sont dans
{fichier("docs/verification/lignes.json")} ; les trois passes, une par année, dans
{fichier("reports/verification/passe_2022.json", "passe_2022.json")},
{fichier("reports/verification/passe_2023.json", "passe_2023.json")} et
{fichier("reports/verification/passe_2024.json", "passe_2024.json")} (commit {commit}) ;
l'écart est calculé par {fichier("src/impots/verification.py")} et la grille écrite dans
{fichier("docs/verification/GRILLE.md")}.</p>

<div class="curseur" id="choix-annee" hidden>
<label for="annee">L'année de la passe</label>
<select id="annee">{options}</select>
<span></span>
</div>
<noscript><p>Sans script, les trois années se lisent l'une sous l'autre ; avec lui, un
menu choisit l'année. Il ne calcule rien : les trois passes sont déjà faites.</p></noscript>

{vues}

<p>D'une année à l'autre, les écarts bougent de quelques points. Ce n'est pas une
confirmation : la population est la même les trois années, et une erreur qui tient à sa
structure se retrouve forcément trois fois. La stabilité dit seulement que ramener la
population en arrière par les indices ne déforme pas l'erreur, et que les totaux publiés
de trois années la voient du même côté. {lien("erreur", "La page 8")} range chaque écart
ligne par ligne, avec sa cause.</p>

{GLOSSAIRE}

<h3 id="grille-entiere">La grille entière</h3>
<p>Chaque cellule dit l'écart au total publié, le simulé contre le publié, et le lien de
la source de l'année ; l'onglet et la ligne lus s'affichent au survol du lien. Une ligne
« contexte » n'est pas notée ; une ligne « calée » est dépensée ; une ligne refusée dit
pourquoi.</p>
{table_grille(rows)}

<h2 id="ou-elle-ne-ressemble-pas">Où elle ne ressemble pas à la France</h2>
<p>Les foyers fiscaux sont un peu trop peu nombreux ; il manque des salaires horaires
près du SMIC et il y en a trop un peu plus haut, ce que disent la réduction générale (trop
basse) et la baisse de cotisation d'allocations familiales jusqu'à 3,5 SMIC (trop haute) ;
la prime d'activité est calée sur les allocataires que compte la Drees, sous ce que la
Cnaf verse ; les aides au logement n'ont pas les foyers, les résidences et les
accédants que la Cnaf paie. Chaque écart, sa cause et ce qu'il touche sont sur
{lien("erreur", "la page de l'erreur")}. Le coût d'une réforme se lit sur
{lien("cout", "la page suivante")} : c'est la différence de deux passes sur cette même
population.</p>
"""
    return Page(prouve="la population ressemble à la France sur ce qu'on ne lui a pas "
                       "imposé, et l'on sait, ligne par ligne, où elle ne lui ressemble pas.",
                corps=corps, script=SCRIPT, style=STYLE)
