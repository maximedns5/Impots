"""La page « Le jumeau » du site (but 23, lot 7, D-415) : les curseurs, dans le navigateur.

Le jumeau tourne dans la page, tel quel : Pyodide (CPython compilé en WebAssembly) et
numpy, chargés depuis un CDN à une version fixée, exécutent le paquet `impots.jumeau`
servi avec le site. Aucun portage : la page fait tourner le code que les tests font
tourner, et `site verifier` refuse un site dont le paquet n'est plus celui du dépôt.

LE SITE NE CALCULE RIEN DE NEUF, ICI NON PLUS. `construire` écrit quatre fichiers :

* `jumeau.html`, la page, lisible sans script (ce qu'elle fait, d'où viennent ses
  entrées, ce qu'elle ne fait pas) ;
* `jumeau.js`, son script : il charge Pyodide, écrit le paquet dans le système de
  fichiers du navigateur, puis appelle `navigateur.Session.calculer` à chaque réglage ;
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

ICI = Path(__file__).resolve().parent
SRC = ICI.parents[1]
PAGE, SCRIPT, PAQUET, DONNEES = ("jumeau.html", "jumeau.js", "jumeau-paquet.json",
                                 "jumeau-donnees.json")
#: Pyodide 0.29.5 (16 septembre 2026) : CPython 3.13.2, numpy 2.2.5, PyYAML 6.0.2.
PYODIDE = "0.29.5"
PYODIDE_URL = f"https://cdn.jsdelivr.net/pyodide/v{PYODIDE}/full/"
#: L'empreinte de `pyodide.js` (sous-ressource vérifiée, SRI) : un fichier changé sur le
#: CDN n'est pas exécuté.
PYODIDE_SRI = "sha384-VR47TfKeAmT7vMej7bwOVg0tHTQLLGMSIpsXtFMCZG5OpKZSIXoSLtGY//qHcxc6"
PAQUETS_PYODIDE = ("numpy", "pyyaml")
#: Ce que le paquet peut importer hors de la bibliothèque standard.
TIERS = frozenset({"numpy", "yaml"})
CSP = ("default-src 'none'; script-src 'self' https://cdn.jsdelivr.net "
       "'wasm-unsafe-eval'; connect-src 'self' https://cdn.jsdelivr.net; "
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
            "hypotheses": navigateur.HYPOTHESES, "annees": list(navigateur.ANNEES)}


# --------------------------------------------------------------------------- #
# le paquet : ce que la page importe, relevé en la faisant tourner
# --------------------------------------------------------------------------- #
RELEVE = r"""
import json, sys
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
modules = sorted(m.__file__ for n, m in list(sys.modules.items())
                 if n.split(".")[0] == "impots" and getattr(m, "__file__", None))
import sysconfig
sites = {sysconfig.get_paths()[k] for k in ("purelib", "platlib")}
tiers = sorted({n.split(".")[0] for n, m in list(sys.modules.items())
                if any(str(getattr(m, "__file__", None) or "").startswith(p) for p in sites)})
print(json.dumps({"modules": modules, "lus": sorted(lus), "tiers": tiers}))
"""
#: Les réglages qui font passer la page par chacun de ses chemins.
PARCOURS = [
    {"mode": "reduit", "vue": "vieillie", "candidat": "*"},
    {"mode": "structurel", "vue": "figee", "candidat": "*"},
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
def _corps(d: dict[str, Any]) -> str:
    esc = html.escape
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
            f'{esc(lib.split(" : ", 1)[-1])}</option>'
            for s, lib in sorted(groupes[g], key=lambda x: not x[0].endswith("_programme")))
        + "</optgroup>" for g in ordre)
    instruments = "".join(f'<option value="{esc(k)}">{esc(v)}</option>'
                          for k, v in d["hypotheses"].items())
    annees = d["annees"]
    debut = "".join(f'<option{" selected" if a == annees[0] else ""}>{a}</option>'
                    for a in annees)
    fin = "".join(f'<option{" selected" if a == annees[-1] else ""}>{a}</option>'
                  for a in annees)
    sources = "".join(f"<li><strong>{esc(k)}</strong> : {esc(v)}</li>"
                      for k, v in d["entrees"]["sources"].items())
    return f"""<h1>Le jumeau</h1>
<p>Le jumeau numérique de la France avance l'économie année par année, de 2026 à 2035,
avec et sans une mesure, et montre la différence. Chaque paramètre incertain est un
curseur θ, de 0 à 1 : θ = 1 est partout la réponse la plus forte de l'économie, θ = ½ le
centre publié. Les nombres sont calculés ici, dans ce navigateur, par le code même du
dépôt (<code>impots.jumeau</code>), à chaque mouvement d'un curseur.</p>
<p>Deux modes. Le mode <strong>réduit</strong> est la chaîne des études : à θ½, il redonne
la dette que publie la page de chaque étude. Le mode <strong>structurel</strong> est le
jumeau : les entreprises, le commerce extérieur, les ménages, depuis l'état publié de
2025. Un rapport d'étude ne ventile, par impôt et par décile, que sa première année et sa
vue figée : au-delà, le mode structurel refuse plutôt que de lire un zéro, et la page le
dit. Un champ qu'aucun bloc n'écrit est dit absent, jamais dessiné à zéro.</p>
<noscript><p class="absent">Cette page calcule dans le navigateur : sans script, elle ne
montre rien. Les études restent lisibles sur leurs pages.</p></noscript>
<form id="reglages" class="jumeau-reglages">
<fieldset><legend>Ce qui entre</legend>
<p><label><input type="radio" name="entree" value="candidat" id="entree-candidat" checked>
une mesure chiffrée par une étude</label>
<label><input type="radio" name="entree" value="hypothese" id="entree-hypothese">
une loi hypothétique</label></p>
<p id="bloc-candidat"><label for="candidat">Le programme ou la mesure</label>
<select id="candidat">{options}</select></p>
<div id="bloc-hypothese" hidden>
<p><label for="h-instrument">Impôt ou dépense</label>
<select id="h-instrument">{instruments}</select></p>
<p><label for="h-montant">Coût pour les APU, Md€ par an (négatif : une hausse d'impôt ou une
baisse de dépense)</label> <input id="h-montant" type="number" step="0.5" value="10"></p>
<p><label for="h-debut">De</label> <select id="h-debut">{debut}</select>
<label for="h-fin">à</label> <select id="h-fin">{fin}</select></p>
<p class="note">Une loi hypothétique est déclarée, pas chiffrée sur la population : ses
chocs sont ceux de la variante de Mésange de l'instrument, au montant dit, répartis entre
les déciles au prorata des cellules de ménages.</p>
</div>
</fieldset>
<fieldset><legend>Le modèle</legend>
<p><label><input type="radio" name="mode" value="reduit" id="mode-reduit" checked> réduit
(les études)</label> <label><input type="radio" name="mode" value="structurel"
id="mode-structurel"> structurel (le jumeau)</label></p>
<p><label for="vue">Population</label> <select id="vue"><option value="vieillie">vieillie
à chaque année</option><option value="figee">figée en 2026</option></select></p>
</fieldset>
</form>
<p id="etat" class="etat" role="status">Chargement de Python dans le navigateur…</p>
<section id="messages"></section>
<h2>Les θ</h2>
<p>Chaque curseur dit sa définition, sa source et sa valeur au réglage ; un θ que le mode
choisi ne lit pas est grisé.</p>
<section id="thetas" class="thetas"></section>
<h2>La trajectoire</h2>
<p>Chaque graphique trace l'écart entre la variante et la référence, chaque année, et sa
décomposition par bloc et par mesure ; le tableau sous lui donne les nombres exacts et les
deux niveaux.</p>
<section id="series"></section>
<h2>Gagnants et perdants, par décile de niveau de vie</h2>
<section id="deciles"></section>
<h2>D'où viennent les entrées</h2>
<ul>{sources}</ul>
<p>Les rapports des études, commités, pour chaque mesure ; le code de
<code>impots.jumeau</code>, servi avec la page (<code>{PAQUET}</code>) ; Python et numpy,
par Pyodide {PYODIDE}, chargé depuis <code>cdn.jsdelivr.net</code> et vérifié par son
empreinte. Rien ne quitte la page : ni réglage, ni nombre.</p>
"""


STYLE = """
.jumeau-reglages fieldset{border:1px solid var(--trait);border-radius:.3rem;margin:.8rem 0;padding:.3rem .8rem;min-width:0}
#candidat,#h-instrument{width:100%}
.jumeau-reglages label{margin-right:.8rem}
.jumeau-reglages select,.jumeau-reglages input[type=number]{max-width:100%}
.etat{font-family:system-ui,sans-serif;font-size:.9rem;color:var(--doux)}
.thetas{display:grid;gap:.5rem}
.theta{border-top:1px solid var(--trait);padding-top:.4rem}
.theta.non-lu{opacity:.5}
.theta .ligne{display:grid;grid-template-columns:minmax(0,1fr) minmax(7rem,14rem) 6.5rem;gap:.2rem .8rem;align-items:center}
.theta input{width:100%}
.theta small{display:block;color:var(--doux);font-size:.8rem;overflow-wrap:anywhere}
.serie{margin:1.2rem 0}
.serie svg,.deciles svg{display:block;width:100%;height:auto;max-width:40rem}
.legende{display:flex;flex-wrap:wrap;gap:.2rem .8rem;font:.78rem/1.3 system-ui,sans-serif;padding:0;list-style:none}
.legende i{display:inline-block;width:.7rem;height:.7rem;margin-right:.25rem;vertical-align:-.05rem}
.serie table,.deciles table{font-size:.8rem}
td.v{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
td.abs{color:var(--doux);font-style:italic}
.messages p{border-left:3px solid var(--l3);padding-left:.6rem}
.note{color:var(--doux);font-size:.9rem}
@media (max-width:560px){.theta .ligne{grid-template-columns:1fr}}
"""


def page(d: dict[str, Any]) -> str:
    from impots import site

    corps = _corps(d)
    main = (corps + f'\n<script src="{PYODIDE_URL}pyodide.js" integrity="{PYODIDE_SRI}" '
            f'crossorigin="anonymous"></script>\n'
            f'<script src="{SCRIPT}" data-pyodide="{PYODIDE_URL}" '
            f'data-paquets="{" ".join(PAQUETS_PYODIDE)}"></script>')
    text = site._page(f"Le jumeau — {site.TITLE}", main)
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
            PAQUET: json.dumps(paquet(d), ensure_ascii=False, separators=(",", ":")),
            DONNEES: texte}


def present() -> bool:
    from impots.jumeau import navigateur

    return navigateur.FICHIER.exists()
