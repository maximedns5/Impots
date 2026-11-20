"""Le registre des sources : chaque nombre que le dépôt cite, lu une fois (but 27, D-491).

Le dépôt lit des documents publics (Insee, DGFiP, Drees, Cnaf, Urssaf, DSS, COR, Unédic,
Mésange, articles) et en cite les nombres dans la grille de vérification, les marges de la
population et les YAML de paramètres. Jusqu'ici chaque passe, chaque agent rouvrait les PDF
pour les retrouver. Le registre les garde, une ligne par nombre :

* `src/impots/sources/registre.jsonl` (versionné) : l'identifiant, la valeur citée, son
  unité et son année, le document (nom au manifeste, ou URL s'il n'y est pas), son
  empreinte, la localisation (page, tableau, feuille), la citation, l'endroit du dépôt qui
  la cite (`cite_par`) et la relecture (le nombre retrouvé, où, ou pourquoi pas) ;
* `src/impots/sources/documents.jsonl` (versionné) : l'inventaire des documents, avec
  éditeur, date, empreinte, millésime et fichiers qui les citent ;
* `data/interim/sources/texte/` (hors git) : le texte de chaque document, page par page,
  reconstruit par `python -m impots.sources texte`.

Lire un nombre : `valeur("jumeau.menages.emploi.part_qualifies.valeur")`. Chercher :
`chercher("Mésange p. 48")`. Vérifier que le dépôt cite encore ce que le registre garde :
`verifier()`. Le registre ne remplace pas les fichiers qui citent (les modules ne sont
pas encore branchés sur lui, D-493) : il les tient.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any

import yaml

from impots.donnees import ROOT

DOSSIER = Path(__file__).resolve().parent
REGISTRE = DOSSIER / "registre.jsonl"
DOCUMENTS = DOSSIER / "documents.jsonl"


class SourceInconnue(KeyError):
    """L'identifiant n'est pas au registre."""


@functools.lru_cache(maxsize=1)
def registre() -> dict[str, dict[str, Any]]:
    """Toutes les entrées, par identifiant."""
    lignes = REGISTRE.read_text(encoding="utf-8").splitlines()
    return {e["id"]: e for e in map(json.loads, lignes) if e}


@functools.lru_cache(maxsize=1)
def documents() -> dict[str, dict[str, Any]]:
    lignes = DOCUMENTS.read_text(encoding="utf-8").splitlines()
    return {e["document"]: e for e in map(json.loads, lignes) if e}


def entree(identifiant: str) -> dict[str, Any]:
    try:
        return registre()[identifiant]
    except KeyError:
        proches = [k for k in registre() if identifiant.split(".")[-1] in k][:5]
        raise SourceInconnue(f"{identifiant} n'est pas au registre"
                             + (f" ; proches : {', '.join(proches)}" if proches else "")
                             ) from None


def valeur(identifiant: str) -> Any:
    """La valeur citée (un nombre, ou une liste de nombres pour un profil)."""
    return entree(identifiant)["valeur"]


def chercher(motif: str, *, champ: str | None = None) -> list[dict[str, Any]]:
    """Les entrées dont l'identifiant, le document ou la citation contiennent tous les mots
    du motif (sans casse)."""
    mots = [m.lower() for m in motif.split()]
    out = []
    for e in registre().values():
        texte = (str(e.get(champ, "")) if champ else
                 " ".join(str(e.get(k) or "") for k in ("id", "document", "source",
                                                        "localisation"))).lower()
        if all(m in texte for m in mots):
            out.append(e)
    return out


# --------------------------------------------------------------------------- #
# la vérification
# --------------------------------------------------------------------------- #
def _suivre(noeud: Any, chemin: list[Any]) -> Any:
    for k in chemin:
        noeud = noeud[k]
    return noeud


@functools.cache
def _yaml(fichier: str) -> Any:
    return yaml.safe_load((ROOT / fichier).read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=1)
def _lignes() -> dict[tuple[str, int], dict[str, Any]]:
    lu = json.loads((ROOT / "docs/verification/lignes.json").read_text(encoding="utf-8"))
    return {(x["id"], x["annee"]): x for x in lu["lignes"]}


def cite_aujourd_hui(e: dict[str, Any]) -> Any:
    """La valeur que le dépôt cite aujourd'hui à l'endroit que l'entrée nomme."""
    c = e["cite_par"]
    if c["fichier"] == "docs/verification/lignes.json":
        return _lignes()[(c["id"], c["annee"])][c["champ"]]
    if c["fichier"].endswith("margins.py"):
        from impots.population import margins

        v = _suivre(getattr(margins, c["nom"]), c["chemin"])
        v = getattr(v, c["champ"]) if c.get("champ") else v
        return list(v) if isinstance(v, tuple) else v
    v = _suivre(_yaml(c["fichier"]), c["chemin"])
    return list(v) if isinstance(v, tuple) else v


def _egal(a: Any, b: Any) -> bool:
    if isinstance(a, list) or isinstance(b, list):
        return (isinstance(a, list) and isinstance(b, list) and len(a) == len(b)
                and all(_egal(x, y) for x, y in zip(a, b, strict=True)))
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return a == b


def verifier(fichier: str | None = None, *, documents_aussi: bool = True) -> list[str]:
    """Les écarts entre le registre et le dépôt : une valeur citée qui n'est plus celle du
    registre, un endroit cité qui n'existe plus, un document dont l'empreinte au manifeste
    a changé. Vide si tout tient. Ne lit aucun document (rapide, sans données).
    `fichier` restreint aux entrées citées par ce fichier (chemin relatif au dépôt)."""
    entrees = [e for e in registre().values()
               if fichier is None or e["cite_par"]["fichier"] == fichier]
    ecarts = []
    for e in entrees:
        try:
            v = cite_aujourd_hui(e)
        except (KeyError, IndexError, TypeError, AttributeError) as x:
            ecarts.append(f"{e['id']} : l'endroit cité n'existe plus ({x!r})")
            continue
        if not _egal(v, e["valeur"]):
            ecarts.append(f"{e['id']} : le dépôt cite {v!r}, le registre garde "
                          f"{e['valeur']!r} ({e['cite_par']['fichier']})")
    if documents_aussi:
        from impots.sources.recolte import manifeste

        man = manifeste()
        for e in entrees:
            d = e.get("document")
            if d and d in man and e.get("sha256") and man[d]["sha256"] != e["sha256"]:
                ecarts.append(f"{e['id']} : {d} a changé au manifeste (relire)")
    return ecarts
