"""La récolte des nombres cités, et leur relecture dans les documents (D-491, D-492).

Trois familles de nombres cités, chacune lue là où le dépôt la garde, sans la recopier :

* **la grille** de vérification (`docs/verification/lignes.json`, D-363) : chaque total
  publié, son document (URL et empreinte), sa localisation ;
* **les marges** de la population (`population/margins.py`) : chaque `Figure` et chaque
  constante numérique, avec sa source et le commentaire qui la précède ;
* **les paramètres** des YAML du jumeau, des comportements, de la macro et du prédictif :
  chaque nombre, avec la `source` la plus proche qui le couvre.

Chaque nombre est ensuite cherché dans son document, sur la page ou la feuille dite
(`texte.trouver`). Le statut dit ce qui a été fait, sans deviner :

* `retrouvée` : le nombre est sur la page ou la feuille dite (ou dans le document, s'il
  n'en dit pas) ; `retrouvée, arrondie` : à l'arrondi du nombre cité ;
* `retrouvée ailleurs` : dans le document, pas sur la page dite ;
* `introuvable` : le document est lu, le nombre n'y est pas, à aucune des échelles
  essayées ; `introuvable (calculée)` quand la source dit un calcul (une somme, un
  rapport, une moyenne) : le nombre n'est pas imprimé, ses termes le sont peut-être ;
* `choisie` : la source dit une valeur choisie, une convention ou une décision ;
* `source secondaire, à vérifier` : la citation dit elle-même que le nombre n'est lu que
  dans une reprise (presse, note de tiers), la publication d'origine n'ayant pas été lue ;
* `non relue` : pas de document identifié, document absent de `data/raw/` ou hors
  manifeste, format non lu, ou nombre trop court pour une recherche sans page.

Une valeur introuvable porte, quand il y en a un, le nombre lu le plus proche (à moins de
5 %) sur la page dite : une piste d'écart, à juger à l'œil, pas un verdict.
"""

from __future__ import annotations

import ast
import contextlib
import itertools
import json
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

from impots.donnees import RAW, ROOT
from impots.sources import texte as T

DOSSIER = Path(__file__).resolve().parent
REGISTRE = DOSSIER / "registre.jsonl"
DOCUMENTS = DOSSIER / "documents.jsonl"
MANIFESTE = RAW / "MANIFEST.json"
LIGNES = ROOT / "docs" / "verification" / "lignes.json"
MARGES = ROOT / "src" / "impots" / "population" / "margins.py"
#: Les YAML de paramètres récoltés, par préfixe d'identifiant. Les fiches de transmission
#: (`jumeau/transmission/`) et les barèmes légaux (`entreprises/parameters/`) n'y sont pas
#: (D-493).
YAMLS = (
    ("jumeau", "src/impots/jumeau/parametres"),
    ("comportements", "src/impots/behavioural/parameters"),
    ("macro", "src/impots/macro/parameters"),
    ("predictif", "src/impots/predictif/parameters"),
)

#: Des documents nommés sans leur nom de fichier, par les YAML et les marges.
ALIAS: tuple[tuple[str, str], ...] = (
    (r"Mésange|G2017[-/]04", "insee_G2017-04_mesange.pdf"),
    (r"t\. ?302\b", "insee_eec2025_t302_chomage_bit.xlsx"),
    (r"IZA DP (n° )?6735|Bargain, Orsini et Peichl", "iza_dp6735_2012_bargain_orsini_peichl_labor_supply.pdf"),
    (r"IZA DP (n° )?7958|Lichter, Peichl et Siegloch", "iza_dp7958_2014_lichter_peichl_siegloch_labor_demand.pdf"),
    (r"IZA DP (n° )?7698", "iza_dp7698_2013_bargain_peichl_labor_supply_survey.pdf"),
    (r"Nijkamp et Poot", "tinbergen_dp02029_2002_nijkamp_poot_wage_curve.pdf"),
    (r"Da Rin", "da_rin_di_giacomo_sembenelli_2011_aam_firm_entry.pdf"),
    (r"Devereux et Lockwood", "devereux_lockwood_2006_foreign_owned_capital.pdf"),
    (r"Hanappi", "hanappi_millot_turban_2023_oecd_eco_wp1765_investment.pdf"),
    (r"CCSS mai 2026|Commission des comptes de la sécurité sociale, mai 2026",
     "ccss_mai2026_comptes_secu_resultats2025.pdf"),
    (r"Bozio-Wasmer|Bozio et Wasmer", "bozio_wasmer_2024_exonerations_rapport_final.pdf"),
    (r"Insee Première n° 2079", "insee_ip2079_salaires_prive_2024.xlsx"),
    (r"IPP n° 47|rapport IPP 47", "ipp_rapport_47_2023_bach_et_al_creations_entreprises.pdf"),
    (r"Corporate Tax Statistics", "oecd_cts_2026_explanatory_annex.pdf"),
)

_TABLEAU_CN = re.compile(r"\bt\. ?(\d)\.(\d{3})|\bT_?(\d)(\d{3})\b|tableau (\d)\.?(\d{3})\b|"
                         r"(?<=, )(\d)\.(\d{3})(?![\d,.])|(?<=et )(\d)\.(\d{3})(?![\d,.])")
_CHOISIE = re.compile(r"choisie?,? non vérifiée?|choisie? :|choix du propriétaire|"
                      r"décision du propriétaire|non sourcée?|aucune source|sans source|"
                      r"hypothèse non validée", re.I)
_SECONDAIRE = re.compile(r"source secondaire", re.I)
_CALCULEE = re.compile(r"\d\s*[/×÷]\s*\d|\d\s+[−+]\s+\d|recomput|recalcul|computed|"
                       r"\bsoit\b|moyenne|somme|calcul|rapport de|divis|résidu|produit de|"
                       r"pondér|interpol|\bmoins\b|\bplus\b", re.I)
_PAGE = re.compile(r"\bp(?:age|\.)\s*(\d{1,4})(?:\s*(?:-|–|à)\s*(\d{1,4}))?", re.I)
_LOCALISATION = re.compile(
    r"((?:tableau|tableaux|t\.|figure|fiche|feuille|onglet|annexe|graphique|encadré|"
    r"section|§)\s*(?:n°\s*)?(?:[A-Z]?_?\d[\w.\-]*|« [^»]{1,40} »)|"
    r"(?:ligne|colonne)s?\s+« [^»]{1,40} »)", re.I)
_SKIP_CLES = {"date", "vintage", "preenregistrement", "ref", "version"}


# --------------------------------------------------------------------------- #
# lectures communes
# --------------------------------------------------------------------------- #
def manifeste() -> dict[str, dict[str, Any]]:
    return json.loads(MANIFESTE.read_text(encoding="utf-8"))["files"]


def _resoudre(texte: str, url: str | None, man: dict[str, dict[str, Any]],
              sha256: str | None = None) -> list[str]:
    """Les fichiers du manifeste que la citation désigne, dans l'ordre où elle les nomme."""
    trouves: list[tuple[int, str]] = []
    if sha256:
        trouves += [(-2, k) for k, v in man.items() if v.get("sha256") == sha256]
    if url:
        trouves += [(-1, k) for k, v in man.items() if v.get("url") == url]
        # Une page d'accueil (« /statistiques/8988833 », « /dataset/ir-declarations-2042-nat/ »)
        # désigne les fichiers servis sous le même identifiant.
        segment = [s for s in re.sub(r"[?#].*$", "", url).split("/") if s][-1:]
        if (segment and url.startswith("http") and len(segment[0]) >= 6
                and (re.search(r"\d", segment[0]) or segment[0].count("-") >= 2)):
            seg = segment[0]
            trouves += [(len(texte) + 1, k) for k, v in man.items()
                        if isinstance(v.get("url"), str) and v.get("url") != url
                        and re.search(r"[/=]" + re.escape(seg) + r"(?:[/&.]|$)", v["url"])]
    for k in man:
        i = texte.find(k)
        if i >= 0:
            trouves.append((i, k))
    # Un nom de fichier tel que l'éditeur le sert (« TCRD_022.xlsx », « IP2114.xlsx ») :
    # le fichier du manifeste qui finit par lui, ou dont l'URL finit par lui.
    for m in re.finditer(r"([\w\-]+\.(?:xlsx|xls|pdf|csv|zip))\b", texte):
        nom = m.group(1).lower()
        for k, v in man.items():
            url_k = (v.get("url") or "").lower() if isinstance(v.get("url"), str) else ""
            if k.lower() != nom and (k.lower().endswith("_" + nom) or url_k.endswith("/" + nom)):
                trouves.append((m.start(), k))
    for motif, fichier in ALIAS:
        m = re.search(motif, texte)
        if m and fichier in man:
            trouves.append((m.start(), fichier))
    # Les tableaux des comptes nationaux de l'Insee, « t. 3.201 » ou « T_7401 » : le
    # fichier du manifeste qui porte leur numéro, du millésime le plus récent d'abord.
    for m in _TABLEAU_CN.finditer(texte):
        g = [x for x in m.groups() if x]
        numero = g[0] + g[1]
        motif = re.compile(r"(?<![0-9])t_?" + numero + r"(?![0-9])", re.I)
        for k in sorted((k for k in man if k.startswith("insee") and motif.search(k)),
                        reverse=True):
            trouves.append((m.start(), k))
    out: list[str] = []
    for _, k in sorted(trouves):
        if k not in out:
            out.append(k)
    return out


def _pages_dites(texte: str) -> list[str]:
    out: list[str] = []
    for m in _PAGE.finditer(texte):
        a = int(m.group(1))
        b = int(m.group(2)) if m.group(2) else a
        if b < a or b - a > 10:
            b = a
        out += [str(p) for p in range(a, b + 1)]
    return out


def localisation(texte: str) -> str:
    morceaux = [m.group(1).strip() for m in _LOCALISATION.finditer(texte)]
    pages = _PAGE.findall(texte)
    morceaux += [f"p. {a}" + (f"-{b}" if b else "") for a, b in pages]
    vus: list[str] = []
    for m in morceaux:
        if m not in vus:
            vus.append(m)
    return " ; ".join(vus[:8])


def _nombre(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _liste_nombres(v: Any) -> bool:
    return isinstance(v, (list, tuple)) and len(v) > 0 and all(_nombre(x) for x in v)


# --------------------------------------------------------------------------- #
# la grille
# --------------------------------------------------------------------------- #
def citations_grille() -> Iterator[dict[str, Any]]:
    for ligne in json.loads(LIGNES.read_text(encoding="utf-8"))["lignes"]:
        if ligne.get("publie") is None:
            continue
        texte = " ".join(str(ligne.get(k) or "") for k in ("source", "localisation"))
        yield {
            "id": f"grille.{ligne['id']}.{ligne['annee']}",
            "valeur": ligne["publie"],
            "unite": "€" if ligne["publie"] > 1e8 else "",
            "annee": ligne["annee"],
            "source": texte,
            "url": ligne.get("url"),
            "sha256": ligne.get("sha256"),
            "cite_par": {"fichier": "docs/verification/lignes.json", "id": ligne["id"],
                         "annee": ligne["annee"], "champ": "publie"},
        }


# --------------------------------------------------------------------------- #
# les marges
# --------------------------------------------------------------------------- #
def _commentaires(lignes: list[str], debut: int) -> str:
    """Le bloc de commentaires juste au-dessus d'une affectation (lignes 1-indexées)."""
    out: list[str] = []
    i = debut - 2
    while i >= 0 and lignes[i].lstrip().startswith("#"):
        s = lignes[i].lstrip("# :").rstrip()
        if not set(s) <= {"-", " "}:
            out.append(s)
        i -= 1
    return " ".join(reversed(out))


#: Au-delà de ce nombre de lignes, l'en-tête de section ne vaut plus pour une constante.
SECTION_MAX = 40


def _section(lignes: list[str], debut: int) -> str:
    """Les commentaires de la section d'une affectation : de l'en-tête « # ---- » qui la
    précède jusqu'à elle. Ils nomment souvent le fichier que les constantes lisent."""
    i = debut - 2
    while i >= 0 and not lignes[i].startswith("# ----"):
        i -= 1
    if i < 0 or debut - i > SECTION_MAX:
        return ""  # trop loin : la section d'avant parlerait d'autre chose
    while i > 0 and lignes[i - 1].startswith("#"):
        i -= 1
    return " ".join(x.strip().lstrip("#: ").rstrip() for x in lignes[max(i, 0):debut - 1]
                    if x.strip().startswith("#"))


def _feuilles(v: Any, chemin: tuple[Any, ...]) -> Iterator[tuple[tuple[Any, ...], Any]]:
    from impots.reporting import Figure

    if isinstance(v, Figure) or _nombre(v) or _liste_nombres(v):
        yield chemin, v
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from _feuilles(x, (*chemin, k))
    elif isinstance(v, (list, tuple)):
        for i, x in enumerate(v):
            yield from _feuilles(x, (*chemin, i))


def _id_chemin(chemin: tuple[Any, ...]) -> str:
    return "".join(f"[{k}]" for k in chemin)


def citations_marges() -> Iterator[dict[str, Any]]:
    from impots.population import margins
    from impots.reporting import Figure

    source = MARGES.read_text(encoding="utf-8")
    lignes = source.splitlines()
    arbre = ast.parse(source)
    urls: list[tuple[str, str]] = []
    for noeud in arbre.body:
        cible = None
        if isinstance(noeud, ast.Assign) and len(noeud.targets) == 1:
            cible = noeud.targets[0]
        elif isinstance(noeud, ast.AnnAssign):
            cible = noeud.target
        if not isinstance(cible, ast.Name) or not cible.id.isupper():
            continue
        nom = cible.id
        valeur = getattr(margins, nom, None)
        if nom.endswith("_URL") and isinstance(valeur, str):
            urls.append((nom, valeur))
            continue
        commentaire = _commentaires(lignes, noeud.lineno)
        section = _section(lignes, noeud.lineno)
        # L'URL d'une constante : celle d'un `*_URL` que son affectation nomme ; sinon
        # aucune (une URL de la section voisine désignait le mauvais document).
        noms = {n.id for n in ast.walk(noeud) if isinstance(n, ast.Name)}
        url_proche = next((u for n, u in urls if n in noms), None)
        for chemin, v in _feuilles(valeur, ()):
            ident = f"marges.{nom}{_id_chemin(chemin)}"
            cite = {"fichier": "src/impots/population/margins.py", "nom": nom,
                    "chemin": list(chemin)}
            if isinstance(v, Figure):
                cite["champ"] = "value"
                yield {"id": ident, "valeur": v.value, "unite": v.unit, "annee": v.year,
                       "usage": v.use,
                       "source": " ; ".join(x for x in (v.source, v.scope, v.caveat,
                                                       commentaire) if x),
                       "url": v.url or url_proche, "sha256": None, "cite_par": cite,
                       "entete": section}
            else:
                v = list(v) if isinstance(v, tuple) else v
                yield {"id": ident, "valeur": v, "unite": "", "annee": None,
                       "usage": "constante",
                       "source": commentaire,
                       "url": url_proche, "sha256": None, "cite_par": cite,
                       "entete": section}


# --------------------------------------------------------------------------- #
# les YAML de paramètres
# --------------------------------------------------------------------------- #
def _texte_source(v: Any) -> str:
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return " ".join(_texte_source(x) for x in v.values())
    if isinstance(v, list):
        return " ".join(_texte_source(x) for x in v)
    return ""


def _cle_source(k: Any) -> bool:
    return isinstance(k, str) and (k.startswith("source") or k in ("citation", "sources"))


def _parcourir(noeud: Any, chemin: tuple[Any, ...], herite: tuple[str, str | None]
               ) -> Iterator[tuple[tuple[Any, ...], Any, str, str | None]]:
    if isinstance(noeud, dict):
        propres = [_texte_source(v) for k, v in noeud.items() if _cle_source(k)]
        texte, url = herite
        if propres:
            texte = " ".join(propres)
            url = next((v.get("url") for k, v in noeud.items()
                        if _cle_source(k) and isinstance(v, dict) and v.get("url")),
                       noeud.get("url") if isinstance(noeud.get("url"), str) else None)
        for k, v in noeud.items():
            if _cle_source(k) or (isinstance(k, str) and k in _SKIP_CLES):
                continue
            if _nombre(v) or _liste_nombres(v):
                yield (*chemin, k), v, texte, url
            elif isinstance(v, (dict, list)):
                yield from _parcourir(v, (*chemin, k), (texte, url))
    elif isinstance(noeud, list):
        for i, v in enumerate(noeud):
            if isinstance(v, (dict, list)):
                yield from _parcourir(v, (*chemin, i), herite)


def citations_yaml() -> Iterator[dict[str, Any]]:
    for prefixe, dossier in YAMLS:
        for chemin_fichier in sorted((ROOT / dossier).glob("*.yaml")):
            rel = str(chemin_fichier.relative_to(ROOT))
            doc = yaml.safe_load(chemin_fichier.read_text(encoding="utf-8"))
            entete = "".join(x for x in chemin_fichier.read_text(encoding="utf-8")
                             .splitlines(keepends=True)[:40] if x.startswith("#"))
            for chemin, v, texte, url in _parcourir(doc, (), ("", None)):
                yield {"id": f"{prefixe}.{chemin_fichier.stem}." + ".".join(map(str, chemin)),
                       "valeur": list(v) if isinstance(v, tuple) else v, "unite": "",
                       "annee": None, "usage": "parametre", "source": texte, "url": url,
                       "sha256": None, "entete_fichier": entete,
                       "cite_par": {"fichier": rel, "chemin": list(chemin)}}


# --------------------------------------------------------------------------- #
# la relecture
# --------------------------------------------------------------------------- #
_PAGES: dict[str, T.Index | str] = {}


def _contenu(fichier: str) -> T.Index | str:
    """L'index des nombres du document, ou la raison pour laquelle il n'est pas lu."""
    if fichier not in _PAGES:
        try:
            _PAGES[fichier] = T.Index(T.pages(fichier))
        except FileNotFoundError:
            _PAGES[fichier] = "document absent de data/raw/"
        except T.TexteError as e:
            _PAGES[fichier] = f"non lu : {e}"
    return _PAGES[fichier]


def _feuilles_dites(texte: str, contenu: T.Index) -> list[str]:
    out = []
    for etiquette in contenu.etiquettes:
        nom = etiquette.split(":")[-1]
        nommee = len(nom) >= 2 and not nom.isdigit() and re.search(
            r"(?<![\w])" + re.escape(nom) + r"(?![\w])", texte)
        annee = nom.isdigit() and len(nom) == 4 and re.search(r"[Oo]nglet « ?" + nom, texte)
        if nommee or annee:
            out.append(etiquette)
    return out


def _trivial(v: float) -> bool:
    return v in (0, 1, -1) or (float(v).is_integer() and 1900 <= v <= 2100)


def _relire_un(v: float, texte: str, fichiers: list[str]) -> dict[str, Any]:
    """Cherche un nombre dans les documents de sa citation, chacun sur ses pages dites
    d'abord ; introuvable seulement si aucun ne le porte."""
    raisons = []
    if _trivial(v):
        return {"statut": "non relue", "note": "nombre trivial (0, 1, une année)"}
    lus: list[tuple[str, T.Index, list[str]]] = []
    for fichier in fichiers:
        contenu = _contenu(fichier)
        if isinstance(contenu, str):
            raisons.append(f"{fichier} : {contenu}")
            continue
        dites = [e for e in _pages_dites(texte) if e in contenu.etiquettes]
        if not dites and not fichier.lower().endswith(".pdf"):
            dites = _feuilles_dites(texte, contenu)
        if not dites and T.chiffres_significatifs(v) < 3:
            raisons.append(f"{fichier} : nombre trop court pour une recherche sans page")
            continue
        lus.append((fichier, contenu, dites))
    for fichier, contenu, dites in lus:
        ici = T.trouver(v, contenu, pages_dites=dites or None)
        if ici:
            t = ici[0]
            return {"statut": "retrouvée" if t.exact else "retrouvée, arrondie",
                    "document": fichier, "page": t.page, "lu": t.lu, "echelle": t.echelle}
    # Ailleurs dans le document : souvent une page citée au folio imprimé, pas à la page
    # du PDF. Deux chiffres significatifs suffisent ici : le nombre est cherché à la seule
    # échelle 1, dans le document que la citation nomme.
    if T.chiffres_significatifs(v) >= 2:
        for fichier, contenu, dites in lus:
            if not dites:
                continue
            ailleurs = T.trouver(v, contenu, echelles=T.ECHELLES if
                                 T.chiffres_significatifs(v) >= 3 else (1.0,))
            if ailleurs:
                t = ailleurs[0]
                return {"statut": "retrouvée ailleurs", "document": fichier,
                        "page": t.page, "lu": t.lu, "echelle": t.echelle,
                        "pages_dites": dites}
    if not lus:
        return {"statut": "non relue", "note": " ; ".join(raisons)}
    fichier, contenu, dites = lus[0]
    r: dict[str, Any] = {"statut": "introuvable", "document": fichier, "pages_dites": dites}
    if len(lus) > 1:
        r["documents_lus"] = [f for f, _, _ in lus]
    piste = T.voisin(v, contenu, dites or None) if dites else None
    if piste:
        r["voisin"] = {"page": piste.page, "lu": piste.lu, "echelle": piste.echelle}
    return r


#: Une somme écrite dans la citation : « 10,720 + 2,687 + 2,262 + 0,935 », « 41635259 −
#: 298023 », chaque terme suivi ou non de « Md€ ».
_TERME = r"(\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:,\d+)?|\d+(?:,\d+)?)(\s*Md\s?€)?"
_SOMME = re.compile(_TERME + r"(?:\s*;?\s*[+−]\s*(?:[^\d+−;]{0,80}?)" + _TERME + r")+")


def _calcul(v: float, texte: str, fichiers: list[str]) -> dict[str, Any] | None:
    """Si la citation écrit une somme qui redonne la valeur (à son arrondi), et que chacun
    de ses termes est dans un des documents, la valeur est « retrouvée (calculée) »."""
    texte = re.sub(r"\bmoins\b", "−", texte)
    for m in _SOMME.finditer(texte):
        brut = m.group(0)
        termes = list(re.finditer(_TERME, brut))
        # « 10,720 + 2,687 + 0,935 Md€ » : l'unité du dernier terme vaut pour les autres.
        unite_finale = bool(termes[-1].group(2))
        signes = [1.0] + [(-1.0 if re.search(r"[−-]\s*[^\d]*$", brut[a.end():b.start()])
                           else 1.0) for a, b in itertools.pairwise(termes)]
        valeurs = []
        for s, x in zip(signes, termes, strict=True):
            n = float(re.sub(r"[ \u00a0\u202f]", "", x.group(1)).replace(",", "."))
            md = bool(x.group(2)) or (unite_finale and n < 1e4)
            valeurs.append(s * n * (1e9 if md else 1.0))
        total = sum(valeurs)
        if total == 0 or not any(T.correspond(v, T.Nombre(abs(total), 6, ""), e)[0]
                                 or abs(abs(total) / (abs(v) * e) - 1) < 5e-4
                                 for e in T.ECHELLES if v):
            continue
        manquants = []
        for x in valeurs:
            if not any(not isinstance(c := _contenu(f), str) and T.trouver(abs(x), c)
                       for f in fichiers):
                manquants.append(x)
        return {"statut": "retrouvée (calculée)" if not manquants else
                "calculée, termes introuvables",
                "calcul": brut[:200], "termes_introuvables": manquants[:10]}
    return None


def relire(c: dict[str, Any], man: dict[str, dict[str, Any]]) -> dict[str, Any]:
    texte = c.get("source") or ""
    fichiers = _resoudre(texte, c.get("url"), man, c.get("sha256"))
    if not fichiers and not texte.strip() and c.get("entete_fichier"):
        # Un nombre sans citation propre : l'en-tête du YAML nomme peut-être son document.
        c["entete"] = c["entete_fichier"]
    if not fichiers and c.get("entete") and not c.get("url"):
        # La citation ne nomme pas son document ; l'en-tête du fichier ou de la section le
        # nomme peut-être. Le texte de recherche des pages devient alors les deux.
        fichiers = _resoudre(c["entete"], None, man)
        if fichiers:
            texte = texte + " " + c["entete"]
    c["documents"] = fichiers
    c["localisation"] = localisation(c.get("source") or "")
    if _SECONDAIRE.search(texte):
        # Lu dans une reprise, pas dans la publication : aucun document ne le relit, et
        # un fichier du manifeste que la citation nommerait en passant n'est pas le sien.
        c["documents"] = []
        return {"statut": "source secondaire, à vérifier",
                "note": "la publication d'origine n'a pas été lue"}
    if not fichiers:
        if _CHOISIE.search(texte):
            return {"statut": "choisie"}
        if c.get("url") or re.search(r"https?://", texte):
            return {"statut": "non relue", "note": "document hors manifeste"}
        if not texte.strip():
            return {"statut": "non relue", "note": "aucune source écrite à côté"}
        return {"statut": "non relue", "note": "document non identifié dans la citation"}
    valeurs = c["valeur"] if isinstance(c["valeur"], list) else [c["valeur"]]
    elements = [_relire_un(float(x), texte, fichiers) for x in valeurs]
    if len(elements) == 1:
        r = elements[0]
    else:
        # Un élément non relu (un 1,0 de long terme, trivial) ne compte ni pour ni contre.
        statuts = [e["statut"] for e in elements if e["statut"] != "non relue"]
        ok = sum(s.startswith("retrouvée") for s in statuts)
        r = {"statut": ("non relue" if not statuts else
                        "retrouvée" if ok == len(statuts) else
                        f"en partie ({ok}/{len(statuts)})" if ok else "introuvable"),
             "elements": elements}
    if r["statut"] == "introuvable" and not isinstance(c["valeur"], list):
        calcul = _calcul(float(c["valeur"]), texte, fichiers)
        if calcul:
            r = {**r, **calcul}
    if r["statut"] == "introuvable" and _CALCULEE.search(texte):
        r["statut"] = "introuvable (calculée)"
    if r["statut"] in ("introuvable", "non relue") and _CHOISIE.search(texte):
        r["statut"] = "choisie"
    return r


# --------------------------------------------------------------------------- #
# l'écriture
# --------------------------------------------------------------------------- #
def citations() -> list[dict[str, Any]]:
    return [*citations_grille(), *citations_marges(), *citations_yaml()]


def _anciennes() -> dict[str, dict[str, Any]]:
    if not REGISTRE.exists():
        return {}
    return {e["id"]: e for e in map(json.loads, REGISTRE.read_text(encoding="utf-8")
                                    .splitlines()) if e}


def recolter(*, ecrire: bool = True) -> list[dict[str, Any]]:
    """Récolte les citations, les relit, écrit le registre ; garde la relecture d'avant
    d'une entrée dont le document n'est pas là et dont la valeur n'a pas changé."""
    man = manifeste()
    avant = _anciennes()
    out = []
    for c in citations():
        r = relire(c, man)
        ancien = avant.get(c["id"])
        if (r["statut"] == "non relue" and "absent" in r.get("note", "")
                and ancien and ancien["valeur"] == c["valeur"]):
            r = ancien["relecture"]
        doc = r.get("document") or next(
            (x.get("document") for x in r.get("elements", []) if x.get("document")),
            c["documents"][0] if c["documents"] else None)
        out.append({
            "id": c["id"], "valeur": c["valeur"], "unite": c["unite"],
            "annee": c["annee"], "usage": c.get("usage", "grille" if c["id"].startswith(
                "grille.") else ""),
            "document": doc or c.get("url"),
            "sha256": (man[doc]["sha256"] if doc else c.get("sha256")),
            "localisation": c["localisation"],
            "source": re.sub(r"\s+", " ", c["source"]).strip()[:400],
            "cite_par": c["cite_par"], "relecture": r,
        })
    if ecrire:
        REGISTRE.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in out),
                            encoding="utf-8")
    return out


# --------------------------------------------------------------------------- #
# l'inventaire des documents
# --------------------------------------------------------------------------- #
EDITEURS = (
    ("insee.fr", "Insee"), ("impots.gouv.fr", "DGFiP"), ("securite-sociale.fr", "DSS (CCSS)"),
    ("caf.fr", "Cnaf"), ("urssaf.fr", "Urssaf"), ("drees", "Drees"),
    ("cor-retraites.fr", "COR"), ("unedic.org", "Unédic"), ("banque-france.fr", "Banque de France"),
    ("ecb.europa.eu", "BCE"), ("europa.eu", "Commission européenne / Eurostat"),
    ("oecd", "OCDE"), ("iza.org", "IZA (article)"), ("assemblee-nationale.fr", "Assemblée nationale"),
    ("senat.fr", "Sénat"), ("legifrance", "DILA"), ("echanges.dila", "DILA"),
    ("aft.gouv.fr", "AFT"), ("ccomptes.fr", "Cour des comptes"), ("budget.gouv.fr", "Direction du budget"),
    ("economie.gouv.fr", "Bercy (DGFiP, DG Trésor)"), ("tresor.economie", "DG Trésor"),
    ("strategie", "France Stratégie"), ("statistiques.developpement-durable", "SDES"),
    ("enseignementsup-recherche", "MESR-SIES"), ("dares", "Dares"), ("ipp.eu", "IPP"),
    ("hcfp.fr", "HCFP"), ("cae-eco.fr", "CAE"),
)
_PREFIXES = (("dgfip", "DGFiP"), ("ircom", "DGFiP"), ("insee", "Insee"), ("cnaf", "Cnaf"),
             ("drees", "Drees"), ("urssaf", "Urssaf"), ("ccss", "DSS (CCSS)"), ("cor_", "COR"),
             ("unedic", "Unédic"), ("erfs", "Insee"), ("bdf", "Banque de France"),
             ("bce", "BCE"), ("iza", "IZA (article)"), ("plf", "Direction du budget"),
             ("aft", "AFT"), ("cerfa", "DGFiP"), ("FD_EEC", "Insee"), ("TD_", "Insee"))


def editeur(fichier: str, url: str | None) -> str:
    hote = re.sub(r"^https?://", "", url or "").split("/")[0].lower()
    if hote:
        for motif, nom in EDITEURS:
            if motif in hote:
                return nom
    for prefixe, nom in _PREFIXES:
        if fichier.lower().startswith(prefixe.lower()):
            return nom
    return hote or "non dit"


_FIXE = re.compile(r"iza|nber|_wp|wp\d|_dp|dp\d|journal|article|jpube|G2017|cae_note|bozio|"
                   r"ipp\.eu|ipp_|econstor|hal\.science|boeckler|unito|cae-eco|oxfordtax|"
                   r"meta-analysis|tepp|doi\.org|repec|zucman|tinbergen|pse_wp|"
                   r"devereux|da_rin|lockwood|kleven|saez|_20\d\d_[a-z]+_[a-z]+_\d{4}|"
                   r"working|cepii|ofce_wp|imk", re.I)
_SERIE = re.compile(r"/exports/|/api/|open\.urssaf|bdm|webstat|data-api|_cn20\d\d_|"
                    r"t_\d{4}|T_\d{4}|series_longues|serie|bce_|eurostat", re.I)


def millesime(fichier: str, url: str | None) -> str:
    cle = f"{fichier} {url or ''}"
    if _FIXE.search(cle):
        return "fixe"
    if _SERIE.search(cle):
        return "série révisée"
    return "édition datée"


def _fichiers_suivis() -> dict[str, str]:
    sortie = subprocess.run(["git", "ls-files", "src", "scripts", "etudes", "Makefile",
                             "docs/verification"], cwd=ROOT, capture_output=True, text=True,
                            check=True).stdout.split()
    out = {}
    for f in sortie:
        if f.endswith((".py", ".yaml", ".yml", ".json", ".md", ".mk", "Makefile", ".mjs")):
            if f.startswith("src/impots/sources/"):
                continue
            with contextlib.suppress(UnicodeDecodeError, FileNotFoundError):
                out[f] = (ROOT / f).read_text(encoding="utf-8")
    return out


def inventaire(registre: list[dict[str, Any]], *, ecrire: bool = True) -> list[dict[str, Any]]:
    man = manifeste()
    suivis = _fichiers_suivis()
    usages: dict[str, int] = {}
    for e in registre:
        if e["document"]:
            usages[e["document"]] = usages.get(e["document"], 0) + 1
    out = []
    for k, v in man.items():
        url = v.get("url") if isinstance(v.get("url"), str) and v["url"].startswith(
            "http") else None
        cite = sorted(f for f, t in suivis.items() if k in t or (url and url in t))
        out.append({"document": k, "url": v.get("url"), "sha256": v.get("sha256"),
                    "octets": v.get("bytes"), "telecharge": v.get("downloaded"),
                    "editeur": editeur(k, url), "millesime": millesime(k, url),
                    "quarantaine": bool(v.get("quarantined")), "cite_par": cite,
                    "valeurs": usages.get(k, 0),
                    "description": (v.get("description") or "")[:200]})
    # Les documents cités par une URL que le manifeste ne porte pas.
    hors = sorted({e["document"] for e in registre
                   if e["document"] and e["document"].startswith("http")})
    for url in hors:
        out.append({"document": url, "url": url, "sha256": None, "octets": None,
                    "telecharge": None, "editeur": editeur("", url),
                    "millesime": millesime("", url), "quarantaine": False,
                    "cite_par": sorted(f for f, t in suivis.items() if url in t),
                    "valeurs": usages.get(url, 0), "description": "hors manifeste"})
    if ecrire:
        DOCUMENTS.write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in out),
                             encoding="utf-8")
    return out
