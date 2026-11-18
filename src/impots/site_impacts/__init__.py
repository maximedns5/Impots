"""La page « Ce que ça change » (but 29, volet `tableau`, D-607) : un programme, une
mesure ou une proposition composée par le lecteur, et tout ce qu'elle touche.

    impacts.html   # le choix, la vue d'ensemble, une fiche par dimension
    impacts.js     # le dessin, et le calcul dans la page

LE MÊME CALCUL QUE LE JUMEAU. Les programmes sont calculés une fois, à la construction,
par `navigateur.impacts_json` (le jumeau complet sur la population figée, chaque θ à ½,
60 tirages pour les bandes) et portés dans la page : elle s'affiche sans attendre. Une
mesure seule ou une proposition composée se calcule dans la page, avec le paquet du
jumeau (`jumeau-paquet.json`, `jumeau-donnees.json`, le Worker `jumeau-calcul.js`,
Pyodide vérifié par son empreinte) : le même code, aucun portage.

GÉNÉRIQUE SUR `Dimension`. La page ne connaît aucune dimension par son nom : elle montre
ce que `jumeau.impacts.tableau` rend, chaque fiche avec sa question, son nombre de tête
(le premier indicateur), sa courbe et sa bande, ses groupes s'il en a (un décile, un cas
type, un territoire), son statut, ses sources et ses limites. Une dimension inscrite par
un autre volet s'y montre sans changer ce fichier.

LA VUE D'ENSEMBLE NE SOMME RIEN : chaque dimension garde son unité.

`python -m impots.site_impacts servir` écrit la page et le paquet du jumeau dans un
dossier temporaire et les sert en local (le site entier n'a pas besoin d'être construit).
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

ICI = Path(__file__).resolve().parent
PAGE, SCRIPT = "impacts.html", "impacts.js"
STYLE = (ICI / "impacts.css").read_text(encoding="utf-8")
#: Ce que la page garde d'un calcul précalculé : ce qu'elle dessine.
GARDE = ("mode", "vue", "candidat", "mesure", "annees", "calculees", "refus",
         "avertissements", "dimensions", "ensemble", "modules_en_erreur", "reglage",
         "pourquoi_mode", "composition", "convention", "synthese", "couverture",
         "programme")
#: Le dossier où `servir` écrit la page, hors du dépôt.
LOCAL = Path("/tmp/impots-ce-que-ca-change")


def _e(x: Any) -> str:
    return html.escape(str(x), quote=True)


def _json_script(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def bibliotheque(d: dict[str, Any]) -> dict[str, Any]:
    """Les mesures que le lecteur peut choisir, par candidat ou par texte, chacune avec
    son programme s'il en a un ; les lois hypothétiques ; les bornes des réglages."""
    from impots.jumeau import navigateur
    from impots.jumeau.proposition import DECALAGE_MAX, ECHELLE_MAX

    groupes: dict[str, dict[str, Any]] = {}
    for cle, c in d["candidats"].items():
        g = groupes.setdefault(c["groupe"], {"groupe": c["groupe"], "programme": None,
                                             "mesures": []})
        if cle.endswith("_programme"):
            g["programme"] = cle
        else:
            libelle = c["libelle"].split(" : ", 1)[-1]
            g["mesures"].append({"cle": cle, "libelle": libelle})
    return {"groupes": list(groupes.values()),
            "libelles": {k: c["libelle"] for k, c in d["candidats"].items()},
            "hypotheses": navigateur.HYPOTHESES, "annees": list(navigateur.ANNEES),
            "echelle_max": ECHELLE_MAX, "decalage_max": DECALAGE_MAX}


def precalculer(d: dict[str, Any]) -> dict[str, Any]:
    """Chaque programme, calculé une fois comme la page le calculerait ; et, pour un
    programme que le jumeau complet refuse, le calcul par ses mesures (D-652) sous la clé
    `<programme>@mesures`."""
    from impots.jumeau import navigateur

    s = navigateur.Session(json.loads(json.dumps(d)))
    out = {}
    for cle in d["candidats"]:
        if cle.endswith("_programme"):
            r = json.loads(navigateur.impacts_json(s, json.dumps({"candidat": cle})))
            out[cle] = {k: r.get(k) for k in GARDE}
            if r.get("pourquoi_mode"):
                out[cle + MESURES] = par_mesures(s, d, cle)
    return out


#: Le suffixe du calcul d'un programme refusé par ses mesures (D-652).
MESURES = "@mesures"


def par_mesures(s: Any, d: dict[str, Any], programme: str) -> dict[str, Any]:
    """Un programme que le jumeau complet refuse, calculé par le jumeau complet comme la
    proposition composée de ses mesures (D-605, D-652) : chaque mesure sa passe, faite
    seule, sans leurs interactions statiques. Le résultat dit ce qu'il couvre : le coût
    mécanique de la première année du programme et la somme de celui de ses mesures."""
    from impots.jumeau import navigateur

    groupe = d["candidats"][programme]["groupe"]
    mesures = [k for k, c in d["candidats"].items()
               if c["groupe"] == groupe and not k.endswith("_programme")]
    r = json.loads(navigateur.impacts_json(s, json.dumps(
        {"composition": [{"candidat": k} for k in mesures]})))
    out = {k: r.get(k) for k in GARDE}
    prog = s.mesure(programme, "figee")
    a = min(prog.couts)
    out["candidat"] = programme + MESURES
    out["programme"] = programme
    out["mesure"] = {**(out.get("mesure") or {}),
                     "libelle": f"{groupe} : le programme, par ses mesures (jumeau complet)"}
    couts = {k: s.mesure(k, "figee").couts.get(a) for k in mesures}
    sans = [k for k, c in couts.items() if c is None]
    # Une mesure sans coût cette année-là : la somme est absente, pas comptée à zéro.
    out["couverture"] = {
        "annee": a, "programme": prog.couts[a], "nombre": len(mesures),
        "mesures": None if sans else sum(couts.values()), "sans_cout": sans,
        "age": _age_hors_mesures(programme)}
    return out


#: Les cas types de « Pour vous » des programmes précalculés, dans un fichier à part que
#: la page lit quand le lecteur s'en sert (D-630) : ils pèseraient sinon les deux tiers de
#: la page.
POUR_VOUS = "impacts-pour-vous.json"


def _age_hors_mesures(programme: str) -> str | None:
    """L'âge de départ que la santé lit pour le programme entier (`sante.yaml`, D-622) et
    qu'aucune de ses mesures chiffrées ne porte : son texte, ou None."""
    from impots.jumeau.impacts import sante
    from impots.jumeau.navigateur import programme_age

    nom = programme_age({"cle": programme})
    p = sante.charger()["retraite"]["programmes"].get(nom or "")
    return p["texte"] if p and p.get("ages") else None


def separer(pre: dict[str, Any]) -> dict[str, Any]:
    """Retire de chaque programme précalculé les cas types de « Pour vous » ; les rend,
    par programme. La dimension garde `notes.fichier` pour que la page les retrouve."""
    out = {}
    for cle, r in pre.items():
        for d in r.get("dimensions") or []:
            if d.get("cle") == "pour_vous" and isinstance(d.get("notes"), dict) \
                    and "cas" in d["notes"]:
                out[cle] = d["notes"].pop("cas")
                d["notes"]["fichier"] = POUR_VOUS
    return out


def donnees() -> dict[str, Any]:
    from impots import site_jumeau

    d = site_jumeau.donnees()
    pre = precalculer(d)
    cas = separer(pre)
    return {"bibliotheque": bibliotheque(d), "precalcul": pre,
            "defaut": next(iter(pre), None), "pour_vous": cas}


def corps(x: dict[str, Any]) -> str:
    from impots import site_jumeau

    b = x["bibliotheque"]
    programmes = "".join(
        f'<option value="{_e(g["programme"])}">{_e(g["groupe"])}</option>'
        for g in b["groupes"] if g["programme"])
    mesures = "".join(
        f'<optgroup label="{_e(g["groupe"])}">'
        + "".join(f'<option value="{_e(m["cle"])}">{_e(m["libelle"])}</option>'
                  for m in g["mesures"]) + "</optgroup>"
        for g in b["groupes"] if g["mesures"])
    defaut = x["precalcul"].get(x["defaut"]) or {}
    lignes = "".join(
        f"<tr><th scope=\"row\">{_e(e.get('titre', e['cle']))}</th>"
        + (f"<td>{_e(e['tete']['libelle'])}</td><td>{e['tete']['horizon']['valeur']:+.2f} "
           f"{_e(e['tete']['unite'])} en {e['tete']['horizon']['annee']}</td>"
           f"<td>{_e(e['statut'])}</td>" if e.get("tete") else
           f"<td colspan=\"3\">non calculée : {_e(e.get('erreur', ''))}</td>") + "</tr>"
        for e in defaut.get("ensemble") or [])
    bref = " ".join(p["texte"] for p in (defaut.get("synthese") or {}).get("phrases") or [])
    sans_script_bref = f"<p><b>En bref.</b> {_e(bref)}</p>" if bref else ""
    sans_script = (f"<noscript><p>Sans script, la page ne montre que le premier programme "
                   f"de la liste, {_e((defaut.get('mesure') or {}).get('libelle', ''))} :"
                   f"</p>{sans_script_bref}<table class=\"i-table\"><thead><tr><th>dimension</th><th>nombre"
                   f"</th><th>à l'horizon</th><th>statut</th></tr></thead><tbody>{lignes}"
                   f"</tbody></table></noscript>")
    return f"""<h1>Ce que ça change</h1>
<p class="chapeau">Une proposition ne se mesure pas qu'en milliards. Choisissez un
programme, une mesure, ou composez la vôtre : la page dit ce qu'elle change pour les
comptes publics, pour l'économie, et pour tout ce que le jumeau sait mesurer d'autre,
année par année, avec ce qu'on peut en croire.</p>
<section class="i-choix" aria-labelledby="titre-choix">
<h2 id="titre-choix" class="i-cache">Le choix</h2>
<div class="i-onglets" role="tablist" aria-label="Ce qu'on mesure">
  <button type="button" role="tab" id="o-programme" aria-controls="p-programme"
    aria-selected="true">Un programme</button>
  <button type="button" role="tab" id="o-mesure" aria-controls="p-mesure"
    aria-selected="false">Une mesure</button>
  <button type="button" role="tab" id="o-composer" aria-controls="p-composer"
    aria-selected="false">Composer la mienne</button>
  <button type="button" role="tab" id="o-comparer" aria-controls="p-comparer"
    aria-selected="false">Comparer</button>
</div>
<div role="tabpanel" id="p-programme" aria-labelledby="o-programme" class="i-panneau">
  <label for="programme">Le programme d'un candidat (sa part chiffrée)</label>
  <select id="programme">{programmes}</select>
</div>
<div role="tabpanel" id="p-mesure" aria-labelledby="o-mesure" class="i-panneau" hidden>
  <label for="mesure">Une mesure seule</label>
  <select id="mesure">{mesures}</select>
</div>
<div role="tabpanel" id="p-composer" aria-labelledby="o-composer" class="i-panneau" hidden>
  <p class="i-aide">Prenez des mesures de candidats différents, réglez leur intensité
  (×1 : la mesure telle que chiffrée) et leur année d'entrée, ajoutez une loi simple
  (un montant sur un impôt ou une dépense). Le jumeau calcule l'ensemble comme un
  programme.</p>
  <ol id="composition" class="i-composition"></ol>
  <div class="i-boutons">
    <button type="button" id="ajouter-mesure">+ une mesure</button>
    <button type="button" id="ajouter-loi">+ une loi simple</button>
    <button type="button" id="calculer" class="i-principal">Calculer</button>
  </div>
</div>
<div role="tabpanel" id="p-comparer" aria-labelledby="o-comparer" class="i-panneau" hidden>
  <p class="i-aide">Les programmes côte à côte, dimension par dimension : le même nombre,
  la même année, la bande et le statut de chacun. Une mesure ou une proposition que vous
  calculez dans la page s'y ajoute.</p>
</div>
<p class="etat" id="etat" role="status" aria-live="polite"></p>
</section>
{sans_script}
<section id="resultat" class="i-resultat" aria-live="polite">
<h2 id="titre-resultat"></h2>
<p id="reglage" class="i-reglage"></p>
<div id="avertissements"></div>
<section id="en-bref" class="i-bref" aria-labelledby="titre-bref">
<h2 id="titre-bref">En bref</h2>
<div id="bref"></div>
<p class="i-aide" id="bref-avert"></p>
</section>
<h2>D'un coup d'œil</h2>
<p class="i-aide">Un nombre par dimension, à l'horizon, avec sa bande. <b>Ils ne
s'additionnent pas</b> : chacun a son unité, et aucun n'est converti dans celle d'un
autre.</p>
<div id="ensemble" class="i-ensemble"></div>
<section id="pour-vous" class="i-pourvous" aria-labelledby="titre-pourvous">
<h2 id="titre-pourvous">Pour vous</h2>
<p class="i-aide">Dites votre situation : la page montre ce que la mesure change pour un
ménage comme le vôtre, année par année. Un cas type, pas vous : ses revenus sont des
médianes de la population, et le calcul le dit quand il n'est qu'une approximation.</p>
<div class="i-situation">
  <label>Foyer <select id="pv-foyer"><option value="seul">seul</option>
    <option value="couple">en couple</option></select></label>
  <label>Enfants <select id="pv-enfants"><option value="0">aucun</option>
    <option value="1">un</option><option value="2">deux</option>
    <option value="3">trois</option></select></label>
  <label>Activité <select id="pv-activite"><option value="smic">salarié au Smic</option>
    <option value="median">salaire médian</option>
    <option value="eleve">salaire élevé (cadre)</option>
    <option value="chomeur">au chômage</option><option value="retraite">retraité</option>
    <option value="independant">indépendant</option></select></label>
  <label>Logement <select id="pv-logement"><option value="locataire">locataire</option>
    <option value="proprietaire">propriétaire</option></select></label>
  <label>Âge <select id="pv-age"><option value="moins_30">moins de 30 ans</option>
    <option value="30_49" selected>30 à 49 ans</option>
    <option value="50_61">50 à 61 ans</option>
    <option value="62_plus">62 ans ou plus</option></select></label>
</div>
<div id="pv-resultat" aria-live="polite"></div>
</section>
<h2>Dimension par dimension</h2>
<div id="fiches"></div>
</section>
<section id="comparer" class="i-comparer" aria-labelledby="titre-comparer" hidden>
<h2 id="titre-comparer">Comparer</h2>
<div class="i-cmp-reglages">
  <label>Dimension <select id="cmp-dimension"></select></label>
  <label>Nombre <select id="cmp-indicateur"></select></label>
  <label>Année <select id="cmp-annee"></select></label>
  <label>Ordre <select id="cmp-tri">
    <option value="haut">du plus haut au plus bas</option>
    <option value="bas">du plus bas au plus haut</option>
    <option value="net">le plus net d'abord</option>
    <option value="nom">par nom</option></select></label>
</div>
<p id="cmp-question" class="i-question"></p>
<div id="cmp-liste" class="i-cmp-liste" role="list"></div>
<p class="i-aide">Le point : le nombre au réglage ; le trait clair : sa bande. Une bande
qui reste d'un côté du zéro est un sens sûr ; une bande qui le franchit, non. Les
nombres de deux dimensions ne s'additionnent pas.</p>
<div id="cmp-refus"></div>
<h3>Tous les nombres de tête</h3>
<p class="i-aide">Le premier nombre de chaque dimension, à l'année choisie. Choisir un
titre de colonne range les programmes selon ce nombre.</p>
<div class="i-defile"><table id="cmp-table" class="i-table i-cmp-table"></table></div>
</section>
<details class="i-methode"><summary>Comment c'est calculé</summary>
<ul>
<li>Chaque programme et chaque mesure viennent d'une passe sur la population (OpenFisca,
la population synthétique du projet), puis du jumeau de l'économie, année par année
(<a href="jumeau.html">la page du jumeau</a>, <a href="cascade.html">l'effet
papillon</a>).</li>
<li>Par défaut, le jumeau complet, sur la population figée de 2026, chaque paramètre
incertain au centre de sa plage (θ = ½). Deux sortes de bandes, que chaque fiche dit
dans « Ce qu'il faut savoir » : pour les comptes et l'économie, de 5 à 95 % de tirages de
ces paramètres (l'incertitude des réactions de l'économie, pas celle du chiffrage) ; pour
le moral, la santé, « Pour vous » et les canaux de la productivité, l'enveloppe des bornes
publiées de leurs coefficients, pas un intervalle de confiance.</li>
<li>Le statut de chaque dimension dit ce qu'on peut en croire : <b>jugé</b> (un chiffrage
officiel fait après coup l'a confrontée), <b>sourcé, non jugé</b> (chaque coefficient a
sa source publiée, aucun juge connu), <b>illustratif</b> (un ordre de grandeur : une loi
déclarée, une mesure mise à l'échelle). Une dimension non jugée n'est jamais une
prévision vérifiée.</li>
<li>Pour vous : chaque cas type passe par OpenFisca avant et après chaque mesure de la
liste (impôts, cotisations, prestations, TVA), au droit de 2026 ; puis le jumeau y ajoute
les salaires, l'indexation et les prix. Un indépendant, une loi simple, une mesure hors de
la liste prennent le gain moyen d'un ménage de leur décile : une approximation, dite.
La satisfaction et la santé reprennent les coefficients publiés des fiches du moral et de
la santé (D-630 à D-633).</li>
<li>« En bref » est écrit par des règles (D-650), pas par un modèle de langue : une
phrase par nombre, qui cite sa dimension et dit sa certitude ; « probablement » seulement
quand la bande reste d'un côté de zéro, « un ordre de grandeur » pour une dimension
illustrative ; jamais de total entre dimensions ni de verdict d'ensemble.</li>
<li>Comparer : Jean-Luc Mélenchon et Marine Tondelier ont deux lignes, parce que le
jumeau complet refuse leur programme entier (la page dit pourquoi) : la chaîne des
études sur le programme entier, et le jumeau complet sur leurs mesures composées
(D-652).</li>
<li>Composer : une mesure à ×2 double chaque montant de sa passe, au premier ordre, sans
refaire la passe ; une entrée plus tardive décale ses années. Les interactions entre
mesures d'une même proposition ne sont pas chiffrées (D-605).</li>
</ul></details>
<script type="application/json" id="impacts-donnees">{_json_script(x)}</script>
<script src="{SCRIPT}" data-pyodide="{site_jumeau.PYODIDE_URL}"
  data-sri="{site_jumeau.PYODIDE_SRI}" data-calcul="{site_jumeau.CALCUL}"
  data-paquets="{" ".join(site_jumeau.PAQUETS_PYODIDE)}"></script>"""


def page(x: dict[str, Any]) -> str:
    from impots import site, site_jumeau

    text = site._page(f"Ce que ça change — {site.TITLE}", corps(x), large=True)
    return (text.replace("</head>", f'<meta http-equiv="Content-Security-Policy" '
                                    f'content="{site_jumeau.CSP}">\n<style>{STYLE}</style>\n'
                                    "</head>", 1)
            .replace("rien n'y est calculé, rien n'y tourne.",
                     "rien n'y est calculé, sauf une mesure seule ou une proposition "
                     "composée : le jumeau tourne alors dans le navigateur."))


def build() -> dict[str, str]:
    x = donnees()
    cas = x.pop("pour_vous")
    return {PAGE: page(x), SCRIPT: (ICI / "page.js").read_text(encoding="utf-8"),
            POUR_VOUS: json.dumps(cas, ensure_ascii=False, separators=(",", ":"))}


def present() -> bool:
    from impots import site_jumeau

    return site_jumeau.present()


def ecrire(dossier: Path = LOCAL) -> Path:
    """La page, le paquet du jumeau et la feuille de style dans `dossier`, la navigation
    réduite aux pages écrites."""
    from impots import site, site_jumeau

    dossier.mkdir(parents=True, exist_ok=True)
    fichiers = {**site_jumeau.build(), **build(), "style.css": site.STYLE}
    for nom, texte in fichiers.items():
        if nom.endswith(".html"):
            texte = texte.replace(site._NAV, site.navigation(nom, set(fichiers)))
        (dossier / nom).write_text(texte, encoding="utf-8")
    return dossier / PAGE


def servir(dossier: Path = LOCAL, port: int = 8001) -> None:
    """`ecrire`, puis le dossier servi sur http://localhost:port."""
    import functools
    import http.server

    ecrire(dossier)
    gestion = functools.partial(http.server.SimpleHTTPRequestHandler, directory=dossier)
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), gestion) as serveur:
        print(f"-> http://localhost:{port}/{PAGE}  (Ctrl-C pour arrêter)", flush=True)
        serveur.serve_forever()

