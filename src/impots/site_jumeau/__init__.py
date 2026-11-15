"""La page « Le jumeau » du site (but 23, lot 7, D-415) : les curseurs, dans le navigateur.

Le jumeau tourne dans la page, tel quel : Pyodide (CPython compilé en WebAssembly) et
numpy, chargés depuis un CDN à une version fixée, exécutent le paquet `impots.jumeau`
servi avec le site. Aucun portage : la page fait tourner le code que les tests font
tourner, et `site verifier` refuse un site dont le paquet n'est plus celui du dépôt.

LE SITE NE CALCULE RIEN DE NEUF, ICI NON PLUS. `construire` écrit cinq fichiers :

* `jumeau.html`, la page, lisible sans script (ce qu'elle fait, d'où viennent ses
  entrées, ce qu'elle ne fait pas) ;
* `jumeau.js`, son script : il vérifie `pyodide.js` par son empreinte et lance le calcul
  dans un Web Worker, puis dessine ce qu'il rend à chaque réglage (D-419) ;
* `jumeau-calcul.js`, le script du Worker : il charge Pyodide, écrit le paquet dans le
  système de fichiers du navigateur, puis appelle `navigateur.Session.calculer` ;
* `jumeau-paquet.json`, les sources des modules de `impots` que la page importe et les
  fichiers de paramètres qu'ils lisent, relevés en faisant tourner la page en Python
  (`paquet`) ; un module qui importerait autre chose que numpy et yaml est refusé ;
* `jumeau-donnees.json`, les entrées : `reports/jumeau/entrees_navigateur.json` et, de
  chaque rapport d'étude commité, ce que `Mesure.depuis_rapport` en lit (`alleger`).

LA SÉCURITÉ (D-295). Aucune exécution côté serveur : le site reste statique. Aucune
donnée personnelle : les cellules sont des sommes pondérées de cinquante groupes de
ménages et de 57 groupes d'entreprises. Le code tiers est Pyodide, à une version fixée,
`pyodide.js` vérifié par son empreinte (SRI) ; les paquets sont vérifiés par Pyodide
contre les empreintes de son fichier de verrouillage. La page déclare une politique de
sécurité du contenu : elle ne se connecte qu'à elle-même et au CDN, et n'envoie rien.
"""

from __future__ import annotations

import html
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from impots import etude
from impots.jumeau.navigateur import TIRAGES

ICI = Path(__file__).resolve().parent
SRC = ICI.parents[1]
PAGE, SCRIPT, CALCUL, PAQUET, DONNEES = ("jumeau.html", "jumeau.js", "jumeau-calcul.js",
                                         "jumeau-paquet.json", "jumeau-donnees.json")
#: Pyodide 0.29.5 (16 septembre 2026) : CPython 3.13.2, numpy 2.2.5, PyYAML 6.0.2.
PYODIDE = "0.29.5"
PYODIDE_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE}/full/"
#: L'empreinte de `pyodide.js` (sous-ressource vérifiée, SRI) : un fichier changé sur le
#: CDN n'est pas exécuté.
PYODIDE_SRI = "sha384-VR47TfKeAmT7vMej7bwOVg0tHTQLLGMSIpsXtFMCZG5OpKZSIXoSLtGY//qHcxc6"
PAQUETS_PYODIDE = ("numpy", "pyyaml")
#: Ce que le paquet peut importer hors de la bibliothèque standard.
TIERS = frozenset({"numpy", "yaml"})
#: `worker-src blob:` : le Worker du calcul naît d'un Blob que le script de la page
#: compose (`pyodide.js` vérifié, puis `jumeau-calcul.js`), et hérite ainsi de cette
#: politique ; aucun autre Worker, aucun cadre.
CSP = ("default-src 'none'; script-src 'self' https://cdn.jsdelivr.net "
       "'wasm-unsafe-eval'; worker-src blob:; connect-src 'self' https://cdn.jsdelivr.net; "
       "style-src 'self' 'unsafe-inline'; img-src 'self' data:; base-uri 'none'; "
       "form-action 'none'")


class JumeauSiteError(ValueError):
    """La page du jumeau ne se construit pas comme elle le promet."""


# --------------------------------------------------------------------------- #
# les entrées
# --------------------------------------------------------------------------- #
def candidats() -> dict[str, dict[str, Any]]:
    """Chaque rapport d'étude commité qu'une page du site lit : un programme, une mesure
    seule, ou un volet d'un texte. {scénario : {libellé, auteur, groupe, rapport, …}}."""
    from impots import programmes
    from impots.jumeau.navigateur import alleger

    out: dict[str, dict[str, Any]] = {}

    def ajouter(scenario: str, chemin: Path, libelle: str, auteur: str, groupe: str) -> None:
        if not chemin.exists():
            return
        premiere = chemin.with_name(chemin.name.replace("predictif_", "premiere_annee_"))
        payload = json.loads(chemin.read_text(encoding="utf-8"))
        prem = (json.loads(premiere.read_text(encoding="utf-8")) if premiere.exists()
                else None)
        out[scenario] = {"libelle": libelle, "auteur": auteur, "groupe": groupe,
                         "rapport": etude._relative(chemin), **alleger(payload, prem)}

    for study in etude.definitions():
        if study.refus or not study.page.exists():
            continue
        base = study.rapports
        if study.programme:
            p = programmes.charger(study.programme)
            scenario = study.volets[0].scenario
            ajouter(scenario, base / f"predictif_{scenario}.json",
                    f"{p.candidat} : le programme (sa part chiffrée)", p.candidat,
                    p.candidat)
            libelles = {m.id: m.libelle for m in p.chiffrees()}
            for m in study.mesures:
                ajouter(m.scenario, base / "mesures" / m.mesure / f"predictif_{m.scenario}"
                        f".json", f"{p.candidat} : {libelles.get(m.mesure, m.mesure)}",
                        p.candidat, p.candidat)
        else:
            for v in study.volets:
                miroir = " (chiffrée en miroir, D-298)" if v.miroir else ""
                ajouter(v.scenario, base / f"predictif_{v.scenario}.json",
                        f"{study.titre} : {v.titre or v.scenario}{miroir}", study.titre,
                        study.titre)
    return out


#: Le juge de l'histoire que la page dit (D-439) : le quatrième rejeu noté.
JUGE = etude.ROOT / "reports" / "jumeau" / "rejeu_histoire_r4.json"
CIBLES = {"pib_volume": "PIB en volume", "emploi": "Emploi", "chomage": "Chômage",
          "exportations": "Exportations", "importations": "Importations",
          "recettes_d2": "Impôts sur la production et les produits (D2)",
          "recettes_d5": "Impôts sur le revenu et le patrimoine (D5)",
          "recettes_d61": "Cotisations sociales (D61)", "recettes": "Recettes des APU",
          "solde": "Solde des APU", "dette": "Dette publique",
          "creations": "Créations d'entreprises"}
#: La lecture de D-439 : le rapport compte les importations parmi les θ identifiés,
#: « un artefact de la règle écrite, à dire et à ne pas compter ». La page le dit.
ARTEFACTS_D439 = {
    "commerce_elasticite_prix_importations": (
        "le rapport le compte identifié, un artefact de la règle écrite (D-439) : du côté "
        "de la jacobienne, son écart-type n'est pas sous la moitié de celui de sa loi"),
}
#: Ce qui identifie b : les données fines, pas l'histoire (D-435, D-438, D-439).
PAR_DONNEES_FINES = {
    "jumeau_salaires_chomage": ("par les données fines : la courbe des salaires du panneau "
                                "W1 (Urssaf, chômage localisé de l'Insee), D-435, D-438 ; "
                                "l'histoire seule ne le déplace pas de sa loi (D-439)"),
}


def juge(chemin: Path = JUGE) -> dict[str, Any]:
    """Ce que le juge de l'histoire dit du jumeau (D-439), lu dans son rapport commité :
    chaque cible du test, sa tolérance, l'erreur du jumeau et celle des deux naïfs ; les
    θ que l'histoire estime, et s'ils sont identifiés, à la lecture de D-439."""
    r = json.loads(chemin.read_text(encoding="utf-8"))
    test, sans = r["notes"]["test"], r["notes"]["test_sans_2023"]
    inconnues = sorted({ligne["cible"] for ligne in test["lignes"]} - set(CIBLES))
    if inconnues:
        raise JumeauSiteError(f"cibles du juge sans libellé : {inconnues}")
    lignes = [{"cible": ligne["cible"], "libelle": CIBLES[ligne["cible"]],
               **{k: ligne[k] for k in ("tolerance", "reqm", "reqm_naif", "reqm_mecanique",
                                        "tenue", "bat_naif", "bat_mecanique")}}
              for ligne in test["lignes"]]
    thetas = {}
    for cle, t in r["critere_but"]["thetas"].items():
        identifie = bool(t["identifie"]) and cle not in ARTEFACTS_D439
        thetas[cle] = {"theta": t["theta"], "ecart_type": t["ecart_type"],
                       "identifie": identifie,
                       "par": PAR_DONNEES_FINES.get(cle) if identifie else None,
                       "note": ARTEFACTS_D439.get(cle)}
    return {"rapport": etude._relative(chemin), "commit": r["commit"], "decision": "D-439",
            "cibles": test["cibles"], "tenues": test["tenues"],
            "naif_tenues": test["naif_tenues"], "mecanique_tenues": test["mecanique_tenues"],
            "battues": test["battues"], "battues_mecanique": test["battues_mecanique"],
            "sans_2023": {k: sans[k] for k in ("tenues", "battues", "battues_mecanique")},
            "non_notees": test["non_notees"], "lignes": lignes, "thetas": thetas}


def donnees() -> dict[str, Any]:
    from impots.jumeau import navigateur

    cands = candidats()
    if not cands:
        raise JumeauSiteError("aucun rapport d'étude commité : la page n'a rien à lire")
    cadres = {json.dumps([c["payload"]["rejeu"]["start"], c["payload"]["rejeu"]["cadre"],
                          c["payload"]["persistence"]], sort_keys=True)
              for c in cands.values()}
    if len(cadres) != 1:
        raise JumeauSiteError(f"les rapports portent {len(cadres)} cadres : une loi "
                              f"hypothétique ne saurait lequel prendre")
    premier = next(iter(cands.values()))["payload"]
    cadre = {"start": premier["rejeu"]["start"], "cadre": premier["rejeu"]["cadre"],
             "persistence": premier["persistence"]}
    return {"entrees": navigateur.lire(), "cadre": cadre, "candidats": cands,
            "hypotheses": navigateur.HYPOTHESES, "annees": list(navigateur.ANNEES),
            "juge": juge(), "origines_loi": navigateur.ORIGINES_LOI}


# --------------------------------------------------------------------------- #
# le paquet : ce que la page importe, relevé en la faisant tourner
# --------------------------------------------------------------------------- #
RELEVE = r"""
import json, sys
# Ce que l'interpréteur a chargé avant la page n'est pas importé par elle : un `.pth` de
# site-packages (le `_distutils_hack` de setuptools) charge son module au démarrage.
au_demarrage = set(sys.modules)
lus = set()
def regarder(evenement, args):
    if evenement == "open" and args and isinstance(args[0], str):
        lus.add(args[0])
sys.addaudithook(regarder)
from impots.jumeau import navigateur
s = navigateur.Session(json.load(sys.stdin))
premier = next(iter(s.candidats))
for choix in json.loads(sys.argv[1]):
    if choix.get("candidat") == "*":
        choix["candidat"] = premier
    out = s.calculer({**choix, "theta": {}})
    out = s.calculer({**choix, "theta": {t["cle"]: 0.5 for t in out["thetas"]}})
    s.portee({**choix, "theta": {t["cle"]: 0.5 for t in out["thetas"]}}, tirages=20)
modules = sorted(m.__file__ for n, m in list(sys.modules.items())
                 if n.split(".")[0] == "impots" and getattr(m, "__file__", None))
import sysconfig
sites = {sysconfig.get_paths()[k] for k in ("purelib", "platlib")}
tiers = sorted({n.split(".")[0] for n, m in list(sys.modules.items())
                if n not in au_demarrage and any(str(getattr(m, "__file__", None) or "").startswith(p) for p in sites)})
print(json.dumps({"modules": modules, "lus": sorted(lus), "tiers": tiers}))
"""
#: Les réglages qui font passer la page par chacun de ses chemins.
PARCOURS = [
    {"mode": "reduit", "vue": "vieillie", "candidat": "*"},
    {"mode": "structurel", "vue": "figee", "candidat": "*"},
    {"mode": "structurel", "vue": "figee", "candidat": "*",
     "convention": "parts_premiere_annee"},
    {"mode": "reduit", "hypothese": {"instrument": "impot_sur_le_revenu", "montant": 10,
                                     "debut": 2026, "fin": 2035}},
    {"mode": "structurel", "hypothese": {"instrument": "depense_publique", "montant": 10,
                                         "debut": 2026, "fin": 2035}},
    {"mode": "structurel", "hypothese": {"instrument": "cotisations_employeurs",
                                         "montant": 10, "debut": 2026, "fin": 2030}},
]


def paquet(d: dict[str, Any] | None = None) -> dict[str, Any]:
    """Les fichiers que la page écrit dans Pyodide : chaque module de `impots` importé et
    chaque fichier du paquet lu en faisant tourner la page en Python, dans un processus
    neuf ; refusé si ce processus importe autre chose que numpy et yaml hors de la
    bibliothèque standard, ou lit un fichier hors du paquet."""
    d = donnees() if d is None else d
    env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONHASHSEED": "0"}
    fait = subprocess.run([sys.executable, "-c", RELEVE, json.dumps(PARCOURS)],
                          input=json.dumps(d), capture_output=True, text=True, env=env,
                          check=False)
    if fait.returncode:
        raise JumeauSiteError(f"la page ne tourne pas en Python : {fait.stderr[-2000:]}")
    releve = json.loads(fait.stdout)
    tiers = set(releve["tiers"]) - TIERS - {"_yaml"}
    if tiers:
        raise JumeauSiteError(f"le paquet du jumeau importe {sorted(tiers)} : la page ne "
                              f"charge que numpy et yaml (D-415)")
    fichiers: dict[str, str] = {}
    for chemin in releve["modules"]:
        p = Path(chemin).resolve()
        fichiers[p.relative_to(SRC).as_posix()] = p.read_text(encoding="utf-8")
    for chemin in releve["lus"]:
        p = Path(chemin).resolve()
        if p.suffix in (".py", ".pyc") or "__pycache__" in p.parts:
            continue
        if not p.is_relative_to(SRC / "impots"):
            if p.is_relative_to(etude.ROOT):
                raise JumeauSiteError(f"la page lit {etude._relative(p)} : ses entrées "
                                      f"viennent de {DONNEES}, pas d'un fichier")
            continue
        fichiers[p.relative_to(SRC).as_posix()] = p.read_text(encoding="utf-8")
    return {"pyodide": PYODIDE, "fichiers": dict(sorted(fichiers.items()))}


# --------------------------------------------------------------------------- #
# la page
# --------------------------------------------------------------------------- #
def _juge_html(j: dict[str, Any]) -> str:
    """Le juge de l'histoire, dit simplement (D-439) : écrit dans la page, sans script."""
    esc = html.escape

    def nombre(x: float, d: int = 2) -> str:
        return f"{x:.{d}f}".replace(".", ",")

    def oui(b: bool) -> str:
        return ('<td class="oui">oui</td>' if b else '<td class="non">non</td>')

    lignes = "".join(
        f'<tr data-cible="{esc(x["cible"])}"><th scope="row">{esc(x["libelle"])}</th>'
        f'<td class="v">{nombre(x["tolerance"], 1)}</td><td class="v">{nombre(x["reqm"])}</td>'
        f'<td class="v">{nombre(x["reqm_mecanique"])}</td>{oui(x["tenue"])}'
        f'{oui(x["bat_mecanique"])}</tr>' for x in j["lignes"])
    n_id = sum(1 for t in j["thetas"].values() if t["identifie"])
    def bas(lib: str) -> str:
        return lib if lib.startswith("PIB") else lib[0].lower() + lib[1:]

    mieux = ", ".join(bas(x["libelle"]) for x in j["lignes"] if x["bat_mecanique"])
    moins = ", ".join(bas(x["libelle"]) for x in j["lignes"] if not x["bat_mecanique"])
    nommes = {"jumeau_salaires_chomage": "la réponse des salaires au chômage (b)"}
    fines = "".join(f"<li><strong>{esc(nommes.get(k, k))}</strong>, identifiée {esc(t['par'])}.</li>"
                    for k, t in j["thetas"].items() if t["identifie"] and t["par"])
    return f"""<section id="juge" class="j-section" aria-labelledby="titre-juge">
<h2 id="titre-juge"><span class="num">5</span> Ce que le jumeau sait, et ne sait pas</h2>
<p class="lead">On l'a fait rejouer l'histoire : parti des comptes publiés, il prédit
chaque année de 2018 à 2024 (hors 2020 et 2021) sans la connaître, et on compare. Deux
adversaires simples : le <em>naïf</em> (l'année suivante ressemble à la dernière) et le
<em>naïf mécanique</em> (le même, plus l'effet comptable des mesures votées, sans aucun
comportement).</p>
<div class="chiffres">
<div class="stat"><span class="stat-v">{j["tenues"]} sur {j["cibles"]}</span><span class="stat-l">cibles tenues dans leur
tolérance écrite d'avance (le naïf mécanique : {j["mecanique_tenues"]})</span></div>
<div class="stat"><span class="stat-v">{j["battues_mecanique"]} sur {j["cibles"]}</span><span class="stat-l">cibles où il fait
mieux que le naïf mécanique : la dynamique n'apporte quelque chose que là</span></div>
<div class="stat"><span class="stat-v">{n_id} curseur{"s" if n_id > 1 else ""}</span><span class="stat-l">identifié{"s" if n_id > 1 else ""}, et par des
données fines, pas par l'histoire ; aucun n'est appris de l'histoire seule</span></div>
</div>
<p><strong>Mieux que le naïf mécanique</strong> : {esc(mieux)}.
<strong>Moins bien que lui</strong> : {esc(moins)} ; l'activité, l'emploi et le chômage
surtout, que le jumeau devrait apporter et n'apporte pas encore. La victoire sur les
créations ne tient qu'à 0,04 point sur une tolérance de 10 (D-439). Sans 2023, il tient
{j["sans_2023"]["tenues"]} cibles et bat le naïf mécanique sur
{j["sans_2023"]["battues_mecanique"]}.</p>
<ul>{fines}</ul>
<p class="note">Les curseurs que l'histoire ne fixe pas gardent la loi de la
littérature : c'est elle qui donne leur plage, et la plage des courbes plus haut.</p>
<details><summary>Les douze cibles</summary>
<table class="juge"><thead><tr><th>cible (erreur quadratique moyenne, en points)</th>
<th>tolérance</th><th>jumeau</th><th>naïf mécanique</th><th>tenue</th><th>mieux que le
naïf mécanique</th></tr></thead><tbody>{lignes}</tbody></table>
<p class="note">Rapport <code>{esc(j["rapport"])}</code>, passe sur le commit
<code>{esc(j["commit"][:7])}</code> ; la lecture et ses réserves : {esc(j["decision"])}.
Non notées : {esc("; ".join(f"{k}, {v}" for k, v in j["non_notees"].items()))}.</p>
</details>
</section>"""


def _corps(d: dict[str, Any]) -> str:
    esc = html.escape
    from impots.jumeau.mesures import CONVENTION_PARTS

    groupes: dict[str, list[tuple[str, str]]] = {}
    for scenario, c in d["candidats"].items():
        groupes.setdefault(c["groupe"], []).append((scenario, c["libelle"]))
    # Les programmes d'abord, puis les textes ; dans un groupe, le programme en tête.
    ordre = sorted(groupes, key=lambda g: (not any(s.endswith("_programme")
                                                   for s, _ in groupes[g]), g))
    premier = next(s for s, _ in groupes[ordre[0]])
    options = "".join(
        f'<optgroup label="{esc(g)}">' + "".join(
            f'<option value="{esc(s)}"{" selected" if s == premier else ""}>'
            f'{esc(g)} — {esc(lib.split(" : ", 1)[-1])}</option>'
            for s, lib in sorted(groupes[g], key=lambda x: not x[0].endswith("_programme")))
        + "</optgroup>" for g in ordre)
    instruments = "".join(
        f'<option value="{esc(k)}"{" selected" if k == "depense_publique" else ""}>'
        f'{esc(v)}</option>' for k, v in d["hypotheses"].items())
    annees = d["annees"]
    debut = "".join(f'<option{" selected" if a == annees[0] else ""}>{a}</option>'
                    for a in annees)
    fin = "".join(f'<option{" selected" if a == annees[-1] else ""}>{a}</option>'
                  for a in annees)
    sources = "".join(f"<li><strong>{esc(k)}</strong> : {esc(v)}</li>"
                      for k, v in d["entrees"]["sources"].items())
    return f"""<h1>Le jumeau</h1>
<p class="chapeau">Une économie de la France écrite en comptes nationaux, qui avance d'une
année à la fois, de 2026 à 2035. On y fait entrer une mesure : il calcule l'économie
avec et sans elle, et montre ce que la mesure fait passer d'un bloc à l'autre. Il tourne
ici, dans ce navigateur, avec le code du dépôt.</p>
<noscript><p class="absent">Cette page calcule dans le navigateur : sans script, elle ne
montre que son mode d'emploi et le juge de l'histoire, plus bas. Les études restent
lisibles sur leurs pages.</p></noscript>
<ol class="sommaire"><li><a href="#pas">Le pas annuel</a></li><li><a href="#resultats">Ce
que la mesure fait</a></li><li><a href="#portee">La portée des curseurs</a></li><li><a
href="#qui">Qui y gagne</a></li><li><a href="#juge">Ce qu'il sait</a></li></ol>
<form id="reglages" class="jumeau-reglages">
<fieldset class="entree"><legend>Ce qui entre</legend>
<p class="bascule"><label><input type="radio" name="entree" value="hypothese"
id="entree-hypothese" checked> une loi simple, pour voir</label>
<label><input type="radio" name="entree" value="candidat" id="entree-candidat"> une mesure
chiffrée d'une étude</label></p>
<p id="bloc-candidat" hidden><label for="candidat" class="cache">Le programme ou la
mesure</label> <select id="candidat">{options}</select></p>
<div id="bloc-hypothese">
<p><label for="h-instrument">Impôt ou dépense</label>
<select id="h-instrument">{instruments}</select>
<label for="h-montant">Md€ par an</label>
<input id="h-montant" type="number" step="0.5" value="10">
<label for="h-debut">de</label> <select id="h-debut">{debut}</select>
<label for="h-fin">à</label> <select id="h-fin">{fin}</select></p>
<p class="note">Un montant positif coûte aux administrations publiques (APU) : une baisse
d'impôt ou une hausse de dépense ; négatif, l'inverse. Une loi simple n'est pas chiffrée
sur la population : elle porte les chocs de la variante de <a class="terme"
href="methode.html#mesange">Mésange</a> de l'instrument, au montant dit.</p>
</div>
</fieldset>
<fieldset class="modele"><legend>Le modèle</legend>
<p class="bascule"><label><input type="radio" name="mode" value="structurel"
id="mode-structurel" checked> le jumeau (structurel)</label> <label><input type="radio"
name="mode" value="reduit" id="mode-reduit"> la chaîne des études (réduit)</label></p>
<p><label for="vue">Population</label> <select id="vue"><option value="figee"
selected>figée en 2026</option><option value="vieillie">vieillie à chaque
année</option></select>
<span id="bloc-convention" hidden><label><input type="checkbox" id="convention"
value="{CONVENTION_PARTS}" checked> au-delà de 2026, la convention
« {CONVENTION_PARTS} »</label></span></p>
</fieldset>
</form>
<p id="etat" class="etat" role="status">Chargement de Python dans le navigateur…</p>
<section id="messages" class="messages"></section>

<section id="pas" class="j-section" aria-labelledby="titre-pas">
<h2 id="titre-pas"><span class="num">1</span> Le pas annuel : ce qui passe d'un bloc à
l'autre</h2>
<p class="lead">Chaque année, le jumeau fait tourner ses blocs dans un ordre fixe, puis
ferme les comptes. La mesure entre par les administrations publiques ; ce qu'elle change
se propage, par des canaux nommés, aux ménages, aux entreprises, au reste du monde, et
revient en recettes. Chaque flèche porte l'écart de l'année entre l'économie avec la
mesure et sans elle.</p>
<div class="annee-choix"><button type="button" id="jouer" aria-pressed="false">▶ faire
tourner</button> <label for="annee">Année</label> <input type="range" id="annee" min="0"
max="{len(annees) - 1}" step="1" value="0"> <output id="annee-v">{annees[0]}</output></div>
<div id="schema" class="schema"></div>
<div id="comptes" class="comptes"></div>
</section>

<section id="resultats" class="j-section" aria-labelledby="titre-resultats">
<h2 id="titre-resultats"><span class="num">2</span> Ce que la mesure fait, année par
année</h2>
<p class="lead">Chaque courbe trace un <strong>écart</strong> : l'économie avec la mesure
moins l'économie sans elle, la même année, sous les mêmes hypothèses. La bande grise est
la plage de 90 % que donnent les lois des curseurs ; le trait est le réglage choisi, le
pointillé le réglage par défaut (chaque curseur à ½).</p>
<div id="series-principales" class="series"></div>
<details class="autres-series"><summary>Les autres séries, et les nombres de
chaque courbe</summary><section id="series" class="series"></section></details>
<details class="diagnostic" id="diagnostic"><summary>Pourquoi les courbes bougeaient
tant</summary>
<ul>
<li><strong>Les échelles.</strong> Chaque graphique se recalait sur ses propres valeurs à
chaque calcul : un écart de 0,003 point remplissait le cadre comme un écart de 3, et
bouger un curseur faisait sauter l'axe. L'échelle tient désormais la plage de la mesure,
et ne bouge plus quand on règle un curseur dans cette plage.</li>
<li><strong>Le dénominateur.</strong> La dette se lit en points de PIB : une mesure qui
relève le PIB fait baisser le ratio sans toucher la dette. Les premières années, cet
effet peut l'emporter ; la courbe de la dette dit les deux parts.</li>
<li><strong>Les recettes induites.</strong> L'activité qu'une mesure crée rapporte des
recettes, qui montent en quelques années (le profil de Mésange) : l'écart de solde est
grand la première année et se resserre ensuite, sans que le coût de la mesure change.</li>
<li><strong>La première année et la convention.</strong> Un rapport d'étude ne ventile,
par impôt et par décile, que sa première année (D-412). Le jumeau ne calcule donc les
années suivantes qu'avec la convention « {CONVENTION_PARTS} » (D-414), marquée
<span class="conv">c</span>, ou pas du tout : une courbe qui s'arrête en 2026 n'est pas
un effet nul.</li>
<li><strong>Ce qui n'est pas du bruit.</strong> Le jumeau n'a pas de hasard : à réglage
égal, il redonne le même nombre au bit. La plage grise vient des curseurs, tirés selon
leurs lois, pas d'un bruit de simulation.</li>
<li><strong>La grille.</strong> Un curseur dont l'effet n'est pas monotone (le profil de
la consommation) se lit sur neuf points de 0 à 1, pas à ses deux bouts (D-427).</li>
</ul></details>
</section>

<section id="portee" class="j-section" aria-labelledby="titre-portee">
<h2 id="titre-portee"><span class="num">3</span> La portée de chaque curseur</h2>
<p class="lead">Un curseur règle un paramètre incertain, de 0 (la réponse la plus faible
de l'économie) à 1 (la plus forte) ; ½ est le centre publié. Pour chacun : sa plage, d'où
vient sa loi, si les données le fixent, et de combien il déplace le résultat quand on le
pousse d'un bout à l'autre, les autres restant à leur réglage.</p>
<p class="portee-choix"><label for="indicateur">Résultat mesuré</label> <select
id="indicateur"></select> <span id="portee-etat" class="etat"></span></p>
<p id="ecart-defaut" class="ecart-defaut" aria-live="polite"></p>
<div id="axe-portee" class="axe-portee"></div>
<div id="thetas" class="thetas"></div>
<details class="non-lus"><summary>Les curseurs que ce modèle ne lit pas</summary>
<div id="thetas-non-lus" class="thetas"></div></details>
</section>

<section id="qui" class="j-section" aria-labelledby="titre-qui">
<h2 id="titre-qui"><span class="num">4</span> Qui y gagne : par décile de niveau de
vie</h2>
<section id="deciles" class="deciles"></section>
</section>

{_juge_html(d["juge"])}

<details class="apropos"><summary>D'où viennent les entrées, ce que la page ne fait
pas</summary>
<p>Deux modèles. <strong>La chaîne des études</strong> (réduit) : la mesure, ses
comportements et des multiplicateurs publiés (Mésange) ; à θ½, elle redonne la dette que
publie la page de chaque étude. <strong>Le jumeau</strong> (structurel) : les ménages en
cinquante cellules, les entreprises en cellules, le commerce extérieur et les APU, chacun
un bloc avec ses équations, depuis les comptes publiés de 2025. Un champ qu'aucun bloc
n'écrit est dit absent, jamais dessiné à zéro.</p>
<ul>{sources}</ul>
<p>Les rapports des études, commités, pour chaque mesure ; le code de
<code>impots.jumeau</code>, servi avec la page (<code>{PAQUET}</code>) ; Python et numpy,
par Pyodide {PYODIDE}, chargé depuis <code>cdn.jsdelivr.net</code> et vérifié par son
empreinte, dans un fil de calcul à part (un Web Worker) : la page ne fige pas pendant un
calcul. La portée des curseurs et la plage des courbes sont une seule trajectoire
vectorisée sur {TIRAGES} tirages des curseurs (D-459). Rien ne quitte la page : ni réglage,
ni nombre.</p>
</details>
"""


STYLE = """
:root{--j-mesure:var(--ocre,#b5532a);--j-apu:var(--accent,#2a6fb0);--j-men:var(--vert,#3d8f5a);--j-ent:var(--violet,#8a5cb8);--j-ext:var(--serie-3,#4a8a98);--j-dette:var(--rouge,#a33b52);--j-bande:rgba(120,115,105,.22)}
@media (prefers-color-scheme: dark){:root{--j-bande:rgba(200,195,185,.22)}}
.chapeau{margin:.2rem 0 .8rem;font-size:1.08rem;max-width:44rem}
.sommaire{display:flex;flex-wrap:wrap;gap:.2rem 1.1rem;padding:0;margin:.4rem 0 1rem;list-style:none;counter-reset:s;font:.9rem system-ui,sans-serif}
.sommaire li{counter-increment:s}
.sommaire li::before{content:counter(s) " ";font-weight:700;color:var(--doux)}
.jumeau-reglages{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:.4rem .9rem;position:sticky;top:0;z-index:2;background:var(--fond);padding:.3rem 0;border-bottom:1px solid var(--trait)}
.jumeau-reglages fieldset{border:1px solid var(--trait);border-radius:.4rem;margin:0;padding:.15rem .7rem;min-width:0;font-size:.9rem}
.jumeau-reglages legend{font:600 .8rem system-ui,sans-serif;color:var(--doux)}
.jumeau-reglages p{margin:.3rem 0}
.jumeau-reglages label{margin-right:.5rem}
.jumeau-reglages select,.jumeau-reglages input[type=number]{max-width:100%}
.jumeau-reglages .note{font-size:.78rem;margin:.2rem 0}
#candidat{width:100%}
#h-montant{width:4.5rem}
.cache{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
.etat{font-family:system-ui,sans-serif;font-size:.82rem;color:var(--doux);margin:.3rem 0}
body.calcule #series-principales,body.calcule .schema{opacity:.6;transition:opacity .2s .2s}
.j-section{margin:2rem 0 1rem;border-top:2px solid var(--trait);padding-top:.6rem}
.j-section h2{margin:.2rem 0 .4rem;font-size:1.3rem}
.num{display:inline-block;min-width:1.6rem;height:1.6rem;line-height:1.6rem;text-align:center;border-radius:50%;background:var(--texte);color:var(--fond);font:700 .9rem system-ui,sans-serif;margin-right:.35rem;vertical-align:.12rem}
.lead{max-width:46rem;margin:.2rem 0 .8rem}
.messages{font-size:.86rem}
.messages p{border-left:3px solid var(--l3);padding-left:.6rem;margin:.3rem 0}
.messages p.note{border-left:0;padding-left:0}
.messages .refus{border-left-color:var(--j-dette);background:var(--l4);padding:.3rem .6rem}
.messages details{margin:.3rem 0}
.messages p.convention{border-left-color:var(--l1)}
.conv{font:600 .7rem/1 system-ui,sans-serif;padding:0 .2rem;border-radius:.2rem;background:var(--l1);color:var(--texte);text-decoration:none}
sup .conv{margin-left:.1rem}
.annee-choix{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;font:.9rem system-ui,sans-serif;margin:.3rem 0}
.annee-choix input{flex:1 1 10rem;max-width:24rem}
.annee-choix output{font:700 1.1rem system-ui,sans-serif;font-variant-numeric:tabular-nums}
.annee-choix button,.portee-choix select{font:inherit;padding:.2rem .6rem;border:1px solid var(--trait);border-radius:.3rem;background:var(--fond);color:var(--texte);cursor:pointer}
.schema svg{display:block;width:100%;height:auto;max-width:56rem;font-family:system-ui,sans-serif}
.schema .bloc rect{fill:var(--fond);stroke-width:2}
.schema .bloc.inerte{opacity:.38}
.schema .canal path{fill:none;stroke-linecap:round}
.schema .canal.inerte{opacity:.18}
.schema .canal.vif path.flux{stroke-dasharray:4 10;animation:flux 1.2s linear infinite}
@keyframes flux{to{stroke-dashoffset:-14}}
@media (prefers-reduced-motion:reduce){.schema .canal.vif path.flux{animation:none}}
.schema-legende{font:.8rem system-ui,sans-serif;color:var(--doux);margin:.2rem 0}
.comptes{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,17rem),1fr));gap:.6rem 1rem;margin:.6rem 0}
.compte{border:1px solid var(--trait);border-radius:.4rem;padding:.4rem .7rem;font:.84rem/1.35 system-ui,sans-serif}
.compte h3{font-size:.9rem;margin:.1rem 0 .3rem}
.compte table{width:100%;border-collapse:collapse}
.compte td{padding:.05rem 0}
.compte td.v{text-align:right;padding-left:.6rem}
.compte tr.total td{border-top:1px solid currentColor;font-weight:700}
.compte .verif{color:var(--doux);font-size:.76rem;margin:.25rem 0 0}
.series{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,21rem),1fr));gap:.6rem 1.4rem}
.serie{margin:.3rem 0;min-width:0}
.serie h3{font-size:1rem;margin:.3rem 0 .1rem}
.serie .trace{font:.8rem/1.3 system-ui,sans-serif;color:var(--doux);margin:0 0 .2rem}
.serie .fin{font:.86rem system-ui,sans-serif;font-variant-numeric:tabular-nums;margin:.1rem 0}
.serie .fin b{font-size:1.15rem}
.serie .pourquoi{font:.8rem/1.35 system-ui,sans-serif;margin:.2rem 0;border-left:3px solid var(--trait);padding-left:.5rem}
.serie svg,.deciles svg{display:block;width:100%;height:auto}
.deciles svg{max-width:44rem}
.legende{display:flex;flex-wrap:wrap;gap:.1rem .7rem;font:.74rem/1.3 system-ui,sans-serif;padding:0;margin:.2rem 0;list-style:none;overflow-wrap:anywhere}
.legende i{display:inline-block;width:.8rem;height:.7rem;margin-right:.25rem;vertical-align:-.05rem}
.legende i.trait{background:currentColor;height:.15rem;vertical-align:.2rem}
.legende i.tirets{border-top:2px dashed currentColor;height:0;vertical-align:.2rem}
.legende i.bande{background:var(--j-bande)}
.legende i.point{background:currentColor;border-radius:50%;width:.45rem;height:.45rem;vertical-align:.05rem}
.serie details summary,.deciles details summary,.autres-series>summary,.diagnostic>summary,.non-lus>summary{font:.84rem system-ui,sans-serif;cursor:pointer;margin:.4rem 0}
.serie table,.deciles table{font-size:.76rem}
.serie details{overflow-x:auto}
td.v{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.abs{color:var(--doux);font-style:italic}
.diagnostic ul{font-size:.88rem;max-width:48rem}
.portee-choix{font:.9rem system-ui,sans-serif;display:flex;gap:.5rem;align-items:center;flex-wrap:wrap}
.ecart-defaut{font:.9rem system-ui,sans-serif;min-height:1.3em;margin:.3rem 0 .6rem}
.ecart-defaut b{font-variant-numeric:tabular-nums}
.ecart-defaut button{font:inherit;font-size:.8rem;margin-left:.4rem;cursor:pointer}
.thetas{display:grid;gap:.1rem}
.theta{display:grid;grid-template-columns:minmax(0,15rem) minmax(0,1fr);gap:.2rem 1rem;padding:.5rem 0;border-top:1px solid var(--trait);font-size:.86rem;line-height:1.3}
.theta .nom{font-weight:600}
.theta .badges{display:flex;flex-wrap:wrap;gap:.2rem;margin:.2rem 0}
.badge{font:600 .68rem/1.4 system-ui,sans-serif;padding:0 .35rem;border-radius:.6rem;border:1px solid currentColor;white-space:nowrap}
.badge.b-litterature{color:var(--j-apu)}
.badge.b-donnees_fines{color:var(--j-men);background:var(--l2)}
.badge.b-construction{color:var(--j-apu)}
.badge.b-large,.badge.b-magasin{color:var(--doux)}
.badge.b-identifie{color:var(--j-men)}
.badge.b-non-identifie{color:var(--doux)}
.theta .barre svg{display:block;width:100%;height:1.6rem}
.theta .effet{font:.76rem system-ui,sans-serif;color:var(--doux);font-variant-numeric:tabular-nums}
.theta .curseur{display:grid;grid-template-columns:minmax(0,1fr) 7.5rem;gap:.5rem;align-items:center;margin-top:.15rem}
.theta input{width:100%;margin:0}
.theta output{font:.8rem system-ui,sans-serif;font-variant-numeric:tabular-nums}
.theta .plage{font:.76rem system-ui,sans-serif;color:var(--doux);overflow-wrap:anywhere}
.theta .detail summary{font:.74rem system-ui,sans-serif;color:var(--doux);cursor:pointer}
.theta small{display:block;color:var(--doux);font-size:.76rem;overflow-wrap:anywhere;margin:.15rem 0}
.theta.change{background:var(--l3)}
.axe-portee{display:grid;grid-template-columns:minmax(0,15rem) minmax(0,1fr);gap:1rem;font:.74rem system-ui,sans-serif;color:var(--doux)}
.axe-portee svg{display:block;width:100%;height:1.2rem}
table.juge{font-size:.8rem}
td.oui{color:var(--j-men);font-weight:600}
td.non{color:var(--doux)}
.titre-mesure{font:700 1.05rem/1.3 system-ui,sans-serif;margin:.4rem 0;border:0!important;padding:0!important}
.titre-mesure span{display:block;font-weight:400;font-size:.8rem;color:var(--doux)}
.messages .refus{border-left:3px solid var(--j-dette);background:var(--l4);padding:.3rem .7rem;margin:.4rem 0}
.messages .refus p{border:0;padding:0}
.messages p.comparaison{border-left-color:var(--j-apu);background:var(--l1);padding:.4rem .7rem}
.pastille{display:inline-block;width:.6rem;height:.6rem;border-radius:.15rem;margin-right:.2rem;vertical-align:-.02rem}
.theta.sans-effet .barre{opacity:.35}
@media (max-width:48rem){.ecart-defaut{position:sticky;top:0;z-index:1;background:var(--fond);padding:.3rem 0;border-bottom:1px solid var(--trait)}}
.apropos{margin:1.5rem 0;font-size:.9rem}
.apropos summary{font:600 .95rem system-ui,sans-serif;cursor:pointer}
.note{color:var(--doux);font-size:.85rem}
@media (max-width:48rem){
.jumeau-reglages{grid-template-columns:minmax(0,1fr);position:static}
.theta,.axe-portee{grid-template-columns:minmax(0,1fr)}
.axe-portee>span:first-child{display:none}
}
"""


def page(d: dict[str, Any]) -> str:
    from impots import site

    corps = _corps(d)
    main = (corps + f'\n<script src="{SCRIPT}" data-pyodide="{PYODIDE_URL}" '
            f'data-sri="{PYODIDE_SRI}" data-calcul="{CALCUL}" '
            f'data-paquets="{" ".join(PAQUETS_PYODIDE)}"></script>')
    text = site._page(f"Le jumeau — {site.TITLE}", main, large=True)
    return (text.replace("</head>", f'<meta http-equiv="Content-Security-Policy" '
                                    f'content="{CSP}">\n<style>{STYLE}</style>\n</head>', 1)
            .replace("rien n'y est calculé, rien n'y tourne.",
                     "rien n'y est calculé, sauf sur cette page, où le jumeau tourne dans "
                     "le navigateur."))


def build() -> dict[str, str]:
    """Les fichiers de la page, par nom publié."""
    d = donnees()
    texte = json.dumps(d, ensure_ascii=False, separators=(",", ":"))
    return {PAGE: page(d), SCRIPT: (ICI / "page.js").read_text(encoding="utf-8"),
            CALCUL: (ICI / "calcul.js").read_text(encoding="utf-8"),
            PAQUET: json.dumps(paquet(d), ensure_ascii=False, separators=(",", ":")),
            DONNEES: texte}


def present() -> bool:
    from impots.jumeau import navigateur

    return navigateur.FICHIER.exists()
