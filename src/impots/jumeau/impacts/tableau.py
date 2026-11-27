"""Le tableau des dimensions (but 29, volet `tableau`, D-605) : toutes les dimensions
inscrites, calculées sur une trajectoire, et la vue d'ensemble.

GÉNÉRIQUE. Le tableau ne connaît que l'interface (`impacts.Dimension`) : `charger`
importe chaque module du paquet `impots.jumeau.impacts` (ceux des volets `pouvoir`,
`bienetre`, `productivite` et les deux du tableau, `comptes` et `economie`), ce qui les
inscrit ; une dimension ajoutée demain se montre sans changer ce fichier ni la page.

RIEN N'EST MASQUÉ. Un module qui ne s'importe pas, une dimension qui lève, sont rendus
avec leur erreur, à leur place : la page dit « non calculée » et pourquoi ; les autres
se calculent. Un nombre non fini devient None (absent), jamais zéro.

LA VUE D'ENSEMBLE NE SOMME RIEN. Les dimensions n'ont pas d'unité commune (des Md€, des
points de PIB, des milliers d'emplois, des WELLBY…) : la vue d'ensemble pose côte à côte
le nombre de tête de chacune (son premier indicateur, la convention de D-605), à la
première année calculée et à l'horizon, avec son sens (mieux, moins bien, ni l'un ni
l'autre) et son statut ; aucun total, aucune note, aucun poids.
"""

from __future__ import annotations

import importlib
import math
import pkgutil
from collections.abc import Mapping, Sequence
from typing import Any

from impots.jumeau import impacts

#: L'ordre de la page : celui du but 29 (D-590), puis le reste, par nom de module.
ORDRE = ("pouvoir", "pouvoir_achat", "entente", "bienetre", "moral", "productivite",
         "economie", "comptes")
#: Ce qui n'est pas une dimension : le tableau, et le paragraphe « En bref » (D-650).
HORS = {"tableau", "synthese"}


def charger() -> dict[str, str]:
    """Importe chaque module de dimension ; rend {module : erreur} pour ceux qui ne
    s'importent pas."""
    noms = sorted((m.name for m in pkgutil.iter_modules(impacts.__path__)
                   if not m.name.startswith("_") and m.name not in HORS),
                  key=_rang)
    erreurs: dict[str, str] = {}
    for nom in noms:
        try:
            importlib.import_module(f"{impacts.__name__}.{nom}")
        except Exception as e:  # dit à la page, pas avalé
            erreurs[nom] = f"{type(e).__name__} : {e}"
    return erreurs


def _rang(nom: str) -> tuple[int, str]:
    return (ORDRE.index(nom) if nom in ORDRE else len(ORDRE), nom)


def ordonnees() -> list[str]:
    """Les dimensions inscrites dans l'ordre de la page, celui de leur module : pas celui
    de l'inscription, qui suit la première importation dans le processus (un test, ou
    `site_impacts` qui lit la santé avant de calculer) ; la page en dépendait (D-698)."""
    inscrites = list(impacts.dimensions())
    return sorted(inscrites, key=lambda c: (
        _rang(impacts._REGISTRE[c].__module__.rpartition(".")[2]), inscrites.index(c)))


def propre(x: Any) -> Any:
    """Le JSON de la page : un nombre non fini est absent (None)."""
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, Mapping):
        return {k: propre(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [propre(v) for v in x]
    return x


def calculer_tout(variante: Sequence[Any], reference: Sequence[Any], depart: Any,
                  cellules: Any, **options: Any) -> dict[str, Any]:
    """Chaque dimension inscrite, dans l'ordre, sous sa forme JSON, ou son erreur ; la vue
    d'ensemble ; les modules qui ne se sont pas importés."""
    erreurs = charger()
    # D-655 : un programme composé de ses mesures. `degrader` : {dimension : raison} des
    # dimensions qui passent à « illustratif » ; `limite_commune` : la limite que chaque
    # fiche dit en tête de ses limites.
    degrader = dict(options.pop("degrader", None) or {})
    commune = options.pop("limite_commune", None)
    dims: list[dict[str, Any]] = []
    for cle in ordonnees():
        try:
            d = impacts.calculer(variante, reference, depart, cellules, cles=[cle],
                                 **options)[cle]
            dims.append(propre(impacts.vers_dict(d)))
        except Exception as e:  # dit à la page, pas avalé
            dims.append({"cle": cle, "erreur": f"{type(e).__name__} : {e}"})
            continue
        x = dims[-1]
        if cle in degrader:
            if x["statut"] != "illustratif":
                x["statut_sans_composition"] = x["statut"]
                x["statut"], x["juge"] = "illustratif", None
            x["limites"] = [f"Illustratif : {degrader[cle]}.", *x.get("limites", [])]
        if commune:
            x["limites"] = [commune, *x.get("limites", [])]
    return {"dimensions": dims, "ensemble": ensemble(dims),
            "modules_en_erreur": erreurs}


def _signe(x: float | None, sens: int) -> str | None:
    if x is None:
        return None
    if abs(x) < 1e-9:
        return "nul"
    if sens == 0:
        return "neutre"
    return "mieux" if x * sens > 0 else "moins bien"


def ensemble(dims: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Une ligne par dimension : son nombre de tête à la première année calculée et à
    l'horizon, son sens et son statut ; jamais de somme entre dimensions."""
    out = []
    for d in dims:
        if "erreur" in d:
            out.append({"cle": d["cle"], "erreur": d["erreur"]})
            continue
        ind = (d.get("indicateurs") or [None])[0]
        ligne: dict[str, Any] = {"cle": d["cle"], "titre": d["titre"],
                                 "question": d["question"], "statut": d["statut"],
                                 "juge": d.get("juge"), "tete": None}
        if ind is not None:
            valeurs = ind["valeurs"] or []
            annees = d["annees"] or []
            k = [i for i, x in enumerate(valeurs) if x is not None]
            if k:
                debut, fin = k[0], k[-1]

                def point(i: int, ind: Mapping[str, Any] = ind,
                          annees: Sequence[int] = annees) -> dict[str, Any]:
                    return {"annee": annees[i] if i < len(annees) else None,
                            "valeur": ind["valeurs"][i],
                            "bas": (ind["bas"] or [None] * (i + 1))[i],
                            "haut": (ind["haut"] or [None] * (i + 1))[i],
                            "signe": _signe(ind["valeurs"][i], ind["sens"])}

                ligne["tete"] = {"cle": ind["cle"], "libelle": ind["libelle"],
                                 "unite": ind["unite"], "sens": ind["sens"],
                                 "debut": point(debut), "horizon": point(fin)}
        out.append(ligne)
    return out
