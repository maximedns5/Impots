"""La cascade d'une mesure (but 26, volet `cascade`, D-484) : l'effet papillon, en graphe.

Ce module lit une trajectoire du jumeau et en tire un graphe en couches, que la page
« cascade » dessine et qu'un test pourra relire à l'identique :

    la mesure → qui paie ou reçoit d'abord → les canaux → les agrégats

* LES NŒUDS. La mesure ; les payeurs (les ménages, les entreprises, les administrations
  publiques), lus dans ce que la mesure porte (`Mesure.menages`, `Mesure.entreprises`,
  les chocs et les impulsions que le bloc `mesures` écrit) ; un nœud par bloc du modèle
  qui porte un canal (`canaux.declares`), avec ses canaux et leur description du
  registre ; les agrégats (PIB, emploi, solde des APU, dette).
* LES ARÊTES, chacune avec son montant année par année, son unité, sa raison en une ligne
  et sa source :
  - la mesure vers ses payeurs : le choc statique de chaque année ;
  - un payeur vers un canal : un champ que le bloc `mesures` (ou `chocs_entreprises`)
    écrit et que le bloc du canal lit (`lit`), ou le choc que le bloc lit dans la
    mesure elle-même (`LIT_LA_MESURE`) ;
  - un canal vers un canal : un champ qu'un bloc écrit (sa contribution, non nulle) et
    qu'un autre lit ; une arête qui remonte l'ordre du pas est une boucle (`boucle`), que
    le point fixe de Gauss-Seidel résout ;
  - un canal vers un agrégat : la contribution du bloc au PIB, à l'emploi, au solde, à la
    dette (la décomposition par bloc que le cadre garantit, CADRE.md §1).

RIEN N'EST CODÉ EN DUR PAR MESURE NI PAR CANAL. Les nœuds des canaux sont les blocs du
modèle qui tournent ; leurs arêtes, leurs `lit` et leurs contributions. Un canal qu'un
volet ajoute au registre (`canaux.CANAUX`) et qu'un bloc porte apparaît sans retouche.
Un canal attendu (par la fiche de transmission de la mesure, D-471, ou faute de fiche par
les familles de `FAMILLES`) qu'aucun bloc du modèle ne porte est un nœud « pas encore
modélisé », sans nombre : jamais un nombre inventé.

Ce module n'importe que numpy et la bibliothèque standard (et `impots.jumeau`) : la page
le fait tourner dans Pyodide quand le lecteur bouge θ, comme la page du jumeau.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from impots.jumeau import canaux as registre_canaux
from impots.jumeau.champs import REGISTRE

VERSION = 1

#: Les blocs qui ne portent pas de comportement : la tendance (la référence), le choc de
#: la mesure, la ventilation des chocs des entreprises. Ils font les payeurs, pas les
#: canaux.
INFRASTRUCTURE = frozenset({"tendance", "mesures", "chocs_entreprises"})
#: Les blocs qui écrivent le choc de la mesure (la couche des payeurs).
CHOC = frozenset({"mesures", "chocs_entreprises"})

#: Le nom d'un bloc, en mots de tous les jours (les mêmes que la page du jumeau). Un bloc
#: absent d'ici garde son nom de code : une présentation, pas une liste fermée.
NOMS_BLOCS = {
    "mesange": "Multiplicateurs de Mésange", "creations": "Créations d'entreprises",
    "recettes_induites": "Recettes induites", "demande_publique": "Demande publique",
    "consommation": "Consommation des ménages", "investissement": "Investissement",
    "commerce": "Prix et commerce extérieur", "emploi": "Emploi",
    "emploi_public": "Emploi public", "salaires": "Salaires",
    "naissances": "Naissances d'entreprises", "fermetures": "Fermetures d'entreprises",
    "productivite": "Productivité des entrantes",
    "implantation": "Implantation des multinationales",
}

#: Les blocs qui lisent un choc dans la mesure elle-même, pas dans un champ de l'état
#: (CADRE.md §5) : {bloc: ((clé du choc, payeur, raison), …)}. Un bloc peut déclarer
#: les siens par un attribut `lit_la_mesure` du même format.
LIT_LA_MESURE: dict[str, tuple[tuple[str, str, str], ...]] = {
    "consommation": (("deciles", "menages",
                      "le revenu disponible de chaque décile, que la mesure change : les "
                      "ménages en consomment une part (Mésange p. 30 à 34)"),),
    "salaires": (("smic", "menages",
                  "le Smic réel de la mesure, qui se diffuse aux salaires (Mésange p. 65)"),),
}

#: Le payeur de chaque instrument d'impulsion (`blocs.mesures.IMPULSIONS`) et des signaux
#: des entreprises (`champs.SIGNAUX_ENTREPRISES`) : qui le paie ou le reçoit d'abord.
PAYEUR_INSTRUMENT = {
    "cotisations_employeurs": "entreprises", "cotisations_employeurs_ciblees": "entreprises",
    "cotisations_salaries": "menages", "csg": "menages", "impot_sur_le_revenu": "menages",
    "tva": "menages", "taxe_carbone": "menages", "depense_publique": "apu",
    "investissement_public": "apu", "prelevements_is": "entreprises",
    "prelevements_production": "entreprises", "cotisations_patronales": "entreprises",
    "prelevements_capital_menages": "menages", "prelevements_entreprises": "entreprises",
}
PAYEURS = {
    "menages": ("Les ménages",
                "ce que la mesure change à leur revenu disponible l'année où elle entre, "
                "par la passe sur la population (gain positif)"),
    "entreprises": ("Les entreprises",
                    "ce que la mesure change aux prélèvements qu'elles paient (une baisse "
                    "est un gain, positif ici)"),
    "apu": ("Les administrations publiques",
            "le coût statique de la mesure pour l'État, la Sécurité sociale et les "
            "collectivités : ce qu'elles perdent en recettes ou paient en plus, avant "
            "tout effet sur l'activité (négatif : le solde se creuse)"),
}

#: Les agrégats : (clé, libellé, unité, raison).
AGREGATS = (
    ("pib", "PIB", "% du PIB",
     "la richesse produite dans l'année, avec la mesure, en % de celle sans elle"),
    ("emploi_total", "Emploi", "milliers",
     "le nombre de personnes en emploi, avec la mesure moins sans elle"),
    ("b9", "Solde des APU", "Md€",
     "les recettes moins les dépenses des administrations publiques (B9) ; négatif : "
     "le déficit se creuse"),
    ("dette", "Dette publique", "points de PIB",
     "la dette des administrations publiques en points de PIB, avec la mesure moins sans "
     "elle ; elle cumule les soldes, et le PIB plus haut la dilue"),
)
#: Le solde par sous-secteur (État, Sécurité sociale, collectivités) : les champs du
#: registre de ce groupe, quand un volet les y écrit ; « pas encore modélisé » sinon.
GROUPE_SOUS_SECTEURS = "sous_secteurs"

#: Les familles de canaux que le lecteur attend (le propriétaire, D-471) quand la mesure
#: n'a pas encore de fiche de transmission : (clé, libellé, préfixes des canaux du
#: registre qui la portent). Une famille qu'aucun bloc structurel ne porte est un nœud
#: « pas encore modélisé ». Ce n'est pas une liste des canaux : ceux-ci viennent des
#: blocs ; c'est la liste de ce qu'une page doit dire absent.
FAMILLES = (
    ("cout_du_travail", "Coût du travail (Smic, allègements, incidence des cotisations)",
     ("cout_du_travail", "cout_travail", "smic", "allegement", "incidence")),
    ("emploi", "Emploi", ("emploi",)),
    ("salaires", "Salaires", ("salaires",)),
    ("consommation", "Consommation", ("consommation",)),
    ("prix", "Prix", ("prix",)),
    ("entreprises", "Entreprises (créations, investissement, implantation)",
     ("creations", "fermetures", "productivite", "investissement", "implantation")),
    ("commerce", "Commerce extérieur", ("exportations", "importations")),
    ("comptes_sociaux", "Comptes sociaux et financement (par sous-secteur)",
     ("financement", "sous_secteur", "compensation", "securite_sociale")),
)

#: Le champ que le nœud d'un bloc affiche d'abord, s'il l'écrit ; sinon le premier de son
#: `ecrit` que la mesure touche. Une préférence de présentation, pas une liste fermée.
PRINCIPAL = ("c_menages", "emploi_total", "remunerations", "fbcf_snf", "exportations",
             "creations_societes", "fermetures_societes", "apu_r_d5", "pib")
#: Les champs qui ne font pas d'arête entre canaux : les totaux que le cadre ferme, et le
#: PIB, que tous lisent (il passe par le nœud de l'agrégat, et son retour est une boucle).
HORS_ARETES = frozenset({"pib", "b9", "solde_primaire", "dette", "apu_recettes",
                         "apu_depenses_primaires", "interets_nets", "ratio_dette",
                         "croissance_volume_pib", "emplois_non_ventiles",
                         "revenus_non_ventiles", "solde_induit"})

#: Les fiches de transmission (D-471), écrites par le volet `carte`.
TRANSMISSION = Path(__file__).resolve().parent / "transmission"


class CascadeError(ValueError):
    """Une trajectoire dont on ne sait pas tirer la cascade."""


# --------------------------------------------------------------------------- #
# petits outils
# --------------------------------------------------------------------------- #
def _f(x: Any) -> float:
    return float(np.asarray(x, dtype=float).reshape(-1)[0])


def _arrondi(x: float | None) -> float | None:
    return None if x is None else float(f"{x:.6g}")


def _serie(valeurs: Sequence[float | None], longueur: int) -> list[float | None]:
    v = [_arrondi(x) for x in valeurs]
    return v + [None] * (longueur - len(v))


def _non_nulle(valeurs: Sequence[float | None], seuil: float = 1e-9) -> bool:
    return any(x is not None and abs(x) > seuil for x in valeurs)


def _contribution(traj: Any, champ: str, bloc: str) -> list[float]:
    """L'écart variante − référence de la contribution d'un bloc à un champ additif, par
    année (toutes mesures du bloc sommées)."""
    out = []
    for r, v in zip(traj.reference, traj.variante, strict=True):
        if not (r.present(champ) and v.present(champ)):
            out.append(0.0)
            continue
        dr, dv = r.de(champ), v.de(champ)
        x = sum(_f(val) for (o, _m), val in dv.items() if o == bloc)
        x -= sum(_f(val) for (o, _m), val in dr.items() if o == bloc)
        out.append(x)
    return out


def _ecart(traj: Any, champ: str) -> list[float | None]:
    out: list[float | None] = []
    for r, v in zip(traj.reference, traj.variante, strict=True):
        out.append(_f(v[champ]) - _f(r[champ]) if r.present(champ) and v.present(champ)
                   else None)
    return out


def _libelle_champ(champ: str) -> str:
    c = REGISTRE.get(champ)
    return c.libelle if c is not None else champ


def _unite_champ(champ: str) -> str:
    c = REGISTRE.get(champ)
    if c is None:
        return ""
    return {"Md€ courants": "Md€", "€ courants": "€"}.get(c.unite, c.unite)


def _canaux_du_bloc(bloc: Any) -> list[str]:
    return list(dict.fromkeys((*getattr(bloc, "porte", ()), *getattr(bloc, "remplace", ()))))


# --------------------------------------------------------------------------- #
# la fiche de transmission (D-471), ou son adaptateur
# --------------------------------------------------------------------------- #
def lire_fiche(candidat: str | None, mesure: str | None,
               dossier: Path = TRANSMISSION) -> dict[str, Any] | None:
    """La fiche de transmission d'une mesure (`transmission/<candidat>/<mesure>.yaml`),
    telle quelle, ou None si le volet `carte` ne l'a pas encore écrite. Ses clés sont
    celles de D-471 ; on ne les interprète pas ici."""
    if not (candidat and mesure):
        return None
    chemin = dossier / candidat / f"{mesure}.yaml"
    if not chemin.exists():
        return None
    import yaml

    fiche = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    if not isinstance(fiche, dict):
        raise CascadeError(f"{chemin} : une fiche de transmission est un dictionnaire")
    fiche["_chemin"] = f"src/impots/jumeau/transmission/{candidat}/{mesure}.yaml"
    return fiche


def canaux_attendus(fiche: Mapping[str, Any] | None) -> list[str] | None:
    """Les noms de canaux qu'une fiche cite (sa clé `canaux` : une liste de noms, ou de
    dictionnaires avec `nom`), ou None sans fiche."""
    if not fiche or fiche.get("canaux") is None:
        return None
    out = []
    for c in fiche["canaux"] or []:
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, Mapping) and (c.get("nom") or c.get("canal")):
            out.append(str(c.get("nom") or c.get("canal")))
    return out


# --------------------------------------------------------------------------- #
# le graphe
# --------------------------------------------------------------------------- #
def graphe(traj: Any, mesure: Any, blocs: Sequence[Any], *, annees: Sequence[int],
           thetas: Sequence[Mapping[str, Any]] = (), attendus: Sequence[str] | None = None,
           mode: str = "structurel") -> dict[str, Any]:
    """Le graphe de la cascade d'une trajectoire à une mesure (voir la docstring du
    module). `blocs` dans l'ordre du pas ; `thetas`, le registre des θ que rend
    `navigateur.Session.thetas` (avec, si on l'a, la valeur de chacun) ; `attendus`, les
    canaux que la fiche de transmission cite (None : les familles de `FAMILLES`)."""
    n = len(annees)
    noeuds: list[dict[str, Any]] = []
    aretes: list[dict[str, Any]] = []
    par_id: dict[str, dict[str, Any]] = {}

    def noeud(**k: Any) -> dict[str, Any]:
        k.setdefault("detail", [])
        k.setdefault("statut", "calcule")
        noeuds.append(k)
        par_id[k["id"]] = k
        return k

    def arete(de: str, vers: str, valeurs: Sequence[float | None], unite: str, raison: str,
              source: str, sorte: str, champ: str | None = None) -> None:
        aretes.append({"de": de, "vers": vers, "valeurs": _serie(valeurs, n), "unite": unite,
                       "raison": raison, "source": source, "sorte": sorte, "champ": champ})

    # ------------------------------------------------------------ la mesure
    b9_choc = [sum(c) for c in zip(*(_contribution(traj, "b9", b)
                                      for b in CHOC), strict=True)]
    noeud(id="mesure", type="mesure", couche=0, libelle=mesure.libelle,
          valeurs=_serie(b9_choc, n), unite="Md€",
          pourquoi=("son coût statique pour les administrations publiques chaque année, "
                    "avant tout effet sur l'activité (négatif : le solde se creuse)"),
          source=(f"{mesure.rapport}" if getattr(mesure, "rapport", None) else
                  "une loi hypothétique, au montant dit"))

    # ------------------------------------------------------------ les payeurs
    payeurs: dict[str, dict[str, Any]] = {}

    def payeur(cle: str) -> dict[str, Any]:
        if cle not in payeurs:
            lib, pq = PAYEURS[cle]
            payeurs[cle] = noeud(id=f"payeur:{cle}", type="payeur", couche=1, libelle=lib,
                                 valeurs=[None] * n, unite="Md€", pourquoi=pq,
                                 source="le bloc `mesures` du jumeau, depuis le rapport de "
                                        "la mesure")
        return payeurs[cle]

    def ajouter_valeur(p: dict[str, Any], valeurs: Sequence[float | None]) -> None:
        p["valeurs"] = [(_arrondi((a or 0.0) + (b or 0.0)) if (a is not None or b is not None)
                         else None) for a, b in zip(p["valeurs"], _serie(valeurs, n),
                                                    strict=True)]

    # Les ménages : le choc par décile que la mesure porte.
    deciles = []
    for a in annees[:len(traj.annees)]:
        choc = ((getattr(mesure, "menages", None) or {}).get(a) or {}).get("deciles")
        deciles.append(None if choc is None else float(np.sum(np.asarray(choc, dtype=float))))
    if _non_nulle(deciles):
        p = payeur("menages")
        ajouter_valeur(p, deciles)
        p["detail"].append({"libelle": "revenu disponible, tous déciles", "unite": "Md€",
                            "valeurs": _serie(deciles, n)})
        arete("mesure", p["id"], deciles, "Md€", "le revenu disponible des ménages que la "
              "mesure change, l'année où elle entre (passe sur la population)",
              getattr(mesure, "rapport", None) or "", "choc")
    smic = []
    for a in annees[:len(traj.annees)]:
        x = ((getattr(mesure, "menages", None) or {}).get(a) or {}).get("smic")
        smic.append(None if x is None else 100.0 * float(x))
    # Les entreprises : les prélèvements que la mesure change (une baisse : un gain).
    ent = []
    for a in annees[:len(traj.annees)]:
        chocs = (getattr(mesure, "entreprises", None) or {}).get(a)
        ent.append(None if not chocs else -float(sum(float(v) for v in chocs.values())))
    if _non_nulle(ent):
        p = payeur("entreprises")
        ajouter_valeur(p, ent)
        arete("mesure", p["id"], ent, "Md€", "les prélèvements des entreprises que la "
              "mesure change (une baisse est un gain)", getattr(mesure, "rapport", None)
              or "", "choc")
    # Les administrations publiques : le coût statique.
    if _non_nulle(b9_choc):
        p = payeur("apu")
        ajouter_valeur(p, b9_choc)
        arete("mesure", p["id"], b9_choc, "Md€", "ce que la mesure coûte aux comptes "
              "publics, avant tout effet sur l'activité", getattr(mesure, "rapport", None)
              or "", "choc", "b9")

    # Les champs que la couche du choc écrit : impulsions, signaux, chocs par catégorie.
    ecrits_choc: dict[str, list[float]] = {}
    for b in blocs:
        if b.nom not in CHOC:
            continue
        for champ in getattr(b, "ecrit", ()):
            if champ in REGISTRE and REGISTRE[champ].additif:
                v = _contribution(traj, champ, b.nom)
                if _non_nulle(v):
                    ecrits_choc[champ] = v

    def payeur_du_champ(champ: str) -> str:
        instrument = champ.removeprefix("impulsion_")
        return PAYEUR_INSTRUMENT.get(instrument, "apu")

    # Chaque champ du choc, au signe du payeur : une impulsion est un coût pour les APU
    # (signe du moteur), donc un gain pour qui la reçoit ; un signal des entreprises est
    # une recette, donc un coût pour qui le paie.
    gains: dict[str, list[float]] = {}
    for champ, v in ecrits_choc.items():
        if champ.startswith("impulsion_"):
            gains[champ] = list(v)
        elif REGISTRE[champ].groupe == "signaux":
            gains[champ] = [-x for x in v]
    sans_choc = {"menages": not _non_nulle(deciles), "entreprises": not _non_nulle(ent)}
    for champ, v in gains.items():
        cle = payeur_du_champ(champ)
        if cle == "apu":
            continue
        p = payeur(cle)
        p["detail"].append({"libelle": _libelle_champ(champ), "unite": "Md€",
                            "valeurs": _serie(v, n), "champ": champ})
        if sans_choc.get(cle) and champ.startswith("impulsion_"):
            # Sans choc par décile ni par impôt, le payeur se lit dans ses impulsions.
            ajouter_valeur(p, v)
    for cle in ("menages", "entreprises"):
        if sans_choc[cle] and cle in payeurs and _non_nulle(payeurs[cle]["valeurs"]):
            arete("mesure", payeurs[cle]["id"], payeurs[cle]["valeurs"], "Md€",
                  "ce que la mesure change aux prélèvements de ce payeur (ses impulsions, "
                  "un gain positif)", getattr(mesure, "rapport", None) or "", "choc")

    # ------------------------------------------------------------ les canaux
    canaux_blocs = [b for b in blocs if b.nom not in INFRASTRUCTURE]
    rang = {b.nom: i for i, b in enumerate(blocs)}
    ecrits: dict[str, dict[str, list[float]]] = {}
    for b in canaux_blocs:
        e: dict[str, list[float]] = {}
        for champ in getattr(b, "ecrit", ()):
            if champ not in REGISTRE:
                continue
            if REGISTRE[champ].additif:
                v = _contribution(traj, champ, b.nom)
            else:
                v = [x or 0.0 for x in _ecart(traj, champ)]
            if _non_nulle(v):
                e[champ] = v
        ecrits[b.nom] = e
    portes: set[str] = set()
    for b in canaux_blocs:
        nom = b.nom
        e = ecrits[nom]
        noms_canaux = _canaux_du_bloc(b)
        portes.update(noms_canaux)
        principal = next((c for c in PRINCIPAL if c in e), None) or next(iter(e), None)
        reduit = nom in registre_canaux.REDUITS
        nd = noeud(
            id=f"canal:{nom}", type="canal", couche=2, bloc=nom,
            libelle=NOMS_BLOCS.get(nom, nom),
            statut=("calcule" if e else "sans_effet"),
            reduit=reduit,
            valeurs=_serie(e[principal], n) if principal else [None] * n,
            unite=_unite_champ(principal) if principal else "",
            champ=principal, libelle_champ=_libelle_champ(principal) if principal else None,
            pourquoi=("; ".join(registre_canaux.CANAUX[c] for c in noms_canaux
                                if c in registre_canaux.CANAUX)
                      if not reduit else
                      "les multiplicateurs publiés de Mésange impriment l'effet sur le PIB "
                      "et le solde, sans le détailler canal par canal : "
                      + ", ".join(sorted(noms_canaux))),
            canaux=[{"nom": c, "description": registre_canaux.CANAUX.get(c, "")}
                    for c in noms_canaux],
            thetas=[{k: t.get(k) for k in ("cle", "definition", "source", "direction",
                                           "verifiee", "theta", "valeur")}
                    for t in thetas if t.get("bloc") == nom],
            source="src/impots/jumeau/blocs (le bloc « " + nom + " ») ; jumeau/canaux.py")
        for champ, v in e.items():
            nd["detail"].append({"libelle": _libelle_champ(champ), "unite": _unite_champ(champ),
                                 "valeurs": _serie(v, n), "champ": champ})

    # Les arêtes du choc vers les canaux : un champ du choc qu'un canal lit.
    for b in canaux_blocs:
        lit = set(getattr(b, "lit", ()))
        for champ, v in ecrits_choc.items():
            if champ in lit:
                cle = payeur_du_champ(champ)
                if cle in payeurs:
                    arete(payeurs[cle]["id"], f"canal:{b.nom}", gains.get(champ, v), "Md€",
                          f"{_libelle_champ(champ)} : le bloc « {b.nom} » le lit",
                          REGISTRE[champ].source, "choc", champ)
        for cle_choc, cle_payeur, raison in (getattr(b, "lit_la_mesure", None)
                                             or LIT_LA_MESURE.get(b.nom, ())):
            serie = {"deciles": deciles, "smic": smic}.get(cle_choc)
            if serie is None or not _non_nulle(serie):
                continue
            unite = "Md€" if cle_choc != "smic" else "% du Smic"
            if cle_payeur not in payeurs:
                payeur(cle_payeur)
            arete(payeurs[cle_payeur]["id"], f"canal:{b.nom}", serie, unite, raison,
                  getattr(mesure, "rapport", None) or "", "choc", cle_choc)
    # Les arêtes entre canaux : un champ qu'un bloc écrit et qu'un autre lit.
    for a in canaux_blocs:
        for b in canaux_blocs:
            if a is b:
                continue
            lit = set(getattr(b, "lit", ()))
            communs = [c for c in ecrits[a.nom] if c in lit and c not in HORS_ARETES]
            if not communs:
                continue
            # Le champ le plus gros en Md€ porte le nombre de l'arête ; les autres vont au
            # détail de la raison.
            communs.sort(key=lambda c, e=ecrits[a.nom]: (_unite_champ(c) == "Md€",
                                                          max(abs(x) for x in e[c])),
                         reverse=True)
            c0 = communs[0]
            sorte = "boucle" if rang[b.nom] < rang[a.nom] else "canal"
            raison = (f"{_libelle_champ(c0)} : « {a.nom} » l'écrit, « {b.nom} » le lit"
                      + ("" if len(communs) == 1 else
                         " (et " + ", ".join(_libelle_champ(c) for c in communs[1:]) + ")")
                      + (" ; une boucle, que le pas résout par point fixe"
                         if sorte == "boucle" else ""))
            arete(f"canal:{a.nom}", f"canal:{b.nom}", ecrits[a.nom][c0], _unite_champ(c0),
                  raison, REGISTRE[c0].source, sorte, c0)

    # ------------------------------------------------------------ attendus, non modélisés
    structurels = {c for b in canaux_blocs if b.nom not in registre_canaux.REDUITS
                   for c in _canaux_du_bloc(b)}
    if attendus is not None:
        manquants = [(c, c, registre_canaux.CANAUX.get(c, "")) for c in attendus
                     if c not in structurels]
        origine = "la fiche de transmission de la mesure cite ce canal"
    else:
        manquants = [(cle, lib, "") for cle, lib, prefixes in FAMILLES
                     if not any(c.startswith(prefixes) for c in structurels)]
        origine = ("une famille de canaux que la cascade d'une mesure doit dire, faute de "
                   "fiche de transmission")
    prefixes_de = {cle: prefixes for cle, _l, prefixes in FAMILLES}
    for cle, lib, desc in manquants:
        dans_reduit = any(c.startswith(prefixes_de.get(cle, (cle,)))
                          for c in portes - structurels)
        noeud(id=f"absent:{cle}", type="canal", couche=2, libelle=lib,
              statut="reduit" if dans_reduit else "non_modelise",
              valeurs=[None] * n, unite="",
              pourquoi=(("pas encore modélisé dans le jumeau" if not dans_reduit else
                         "porté en bloc par les multiplicateurs de Mésange, sans détail")
                        + (f" : {desc}" if desc else "") + f" ({origine})"),
              source="jumeau/canaux.py : aucun bloc de ce mode ne le porte")

    # ------------------------------------------------------------ les agrégats
    pib_ref = [_f(e["pib"]) for e in traj.reference]
    for cle, lib, unite, pq in AGREGATS:
        if cle == "pib":
            vals = [100.0 * _f(x) for x in traj.ecart_pib]
        elif cle == "dette":
            vals = [100.0 * _f(x) for x in traj.delta_b]
        else:
            vals = _ecart(traj, cle)
        absent = all(x is None for x in vals)
        noeud(id=f"agregat:{cle}", type="agregat", couche=3, libelle=lib,
              statut="non_modelise" if absent else "calcule",
              valeurs=_serie(vals, n), unite=unite,
              pourquoi=pq if not absent else (pq + " : aucun bloc de ce mode ne l'écrit, il "
                                              "est absent, pas nul"),
              source="le cadre du jumeau ferme les comptes (CADRE.md §3.4)")
    sous = sorted(c.nom for c in REGISTRE.values() if c.groupe == GROUPE_SOUS_SECTEURS)
    if not sous:
        noeud(id="agregat:sous_secteurs", type="agregat", couche=3,
              libelle="Solde par sous-secteur (État, Sécurité sociale, collectivités)",
              statut="non_modelise", valeurs=[None] * n, unite="",
              pourquoi="pas encore modélisé dans le jumeau : le solde n'y est que celui de "
                       "l'ensemble des administrations publiques",
              source="jumeau/champs.py : aucun champ de ce groupe")
    else:
        for champ in sous:
            vals = _ecart(traj, champ)
            noeud(id=f"agregat:{champ}", type="agregat", couche=3,
                  libelle=_libelle_champ(champ),
                  statut="calcule" if _non_nulle(vals) else "sans_effet",
                  valeurs=_serie(vals, n), unite=_unite_champ(champ),
                  pourquoi=REGISTRE[champ].source, source="jumeau/champs.py")

    # Les arêtes vers les agrégats : la contribution de chaque bloc.
    decompo = []
    for a in traj.annees:
        d: dict[str, float] = {}
        for (o, _m), x in traj.decomposition(a).items():
            d[o] = d.get(o, 0.0) + 100.0 * _f(x)
        decompo.append(d)
    for b in [*(x for x in blocs if x.nom in CHOC), *canaux_blocs]:
        source_id = "payeur:apu" if b.nom in CHOC else f"canal:{b.nom}"
        if source_id not in par_id:
            continue
        pib = [100.0 * x / y for x, y in zip(_contribution(traj, "pib", b.nom), pib_ref,
                                             strict=True)]
        for cle, vals, unite, raison in (
                ("pib", pib, "% du PIB", "sa contribution au PIB"),
                ("emploi_total", _contribution(traj, "emploi_total", b.nom), "milliers",
                 "sa contribution à l'emploi"),
                ("b9", _contribution(traj, "b9", b.nom), "Md€",
                 "sa contribution au solde des APU"),
                ("dette", [d.get(b.nom, 0.0) for d in decompo], "points de PIB",
                 "sa contribution à la dette (la décomposition du cadre)")):
            if b.nom in CHOC and cle not in ("b9", "dette"):
                continue
            if _non_nulle(vals):
                arete(source_id, f"agregat:{cle}", vals, unite,
                      f"{NOMS_BLOCS.get(b.nom, PAYEURS['apu'][0] if b.nom in CHOC else b.nom)}"
                      f" : {raison}", "la décomposition par bloc du jumeau (CADRE.md §1)",
                      "agregat", cle)
    # Les retours : un canal qui lit le PIB (l'activité) le reçoit de l'agrégat.
    for b in canaux_blocs:
        if "pib" in set(getattr(b, "lit", ())) and par_id[f"canal:{b.nom}"]["statut"] != (
                "sans_effet"):
            arete("agregat:pib", f"canal:{b.nom}", [100.0 * _f(x) for x in traj.ecart_pib],
                  "% du PIB", f"l'activité : « {b.nom} » lit le PIB, que les autres canaux "
                  "font ; une boucle, que le pas résout par point fixe",
                  "le cadre du jumeau (CADRE.md §3.3)", "boucle", "pib")

    return {"version": VERSION, "mode": mode, "annees": list(annees),
            "calculees": list(traj.annees), "noeuds": noeuds, "aretes": aretes,
            "couches": ["La mesure", "Qui paie ou reçoit d'abord", "Les canaux",
                        "Les agrégats"]}


# --------------------------------------------------------------------------- #
# depuis la session de la page (navigateur), en Python et dans Pyodide
# --------------------------------------------------------------------------- #
def calculer(session: Any, choix: Mapping[str, Any],
             attendus: Sequence[str] | None = None) -> dict[str, Any]:
    """La cascade d'un réglage de la page du jumeau (`Session._contexte`) : {mode, vue,
    candidat | hypothese, convention, theta}. Un θ seul (`theta_commun`) vaut pour tous
    les θ que le modèle lit, à la place de `theta` : θ = 1 est partout la réponse la plus
    forte de l'économie (`thetas`)."""
    from impots.jumeau import navigateur

    choix = dict(choix)
    ctx = session._contexte({**choix, "theta": {}})
    if "theta_commun" in choix:
        t = float(choix["theta_commun"])
        choix["theta"] = {r["cle"]: t for r in ctx["registre"]}
    ctx = session._contexte(choix)
    traj, refus = session._derouler(ctx, ctx["theta"])
    registre = ctx["registre"]
    for t in registre:
        t["theta"] = ctx["theta"].get(t["cle"])
    if traj is None:
        return {"version": VERSION, "mode": ctx["mode"], "refus": refus,
                "annees": list(navigateur.ANNEES), "calculees": [], "noeuds": [],
                "aretes": []}
    from impots.jumeau.pas import Modele

    blocs = Modele(ctx["blocs"], ctx["boucles"]).blocs
    g = graphe(traj, ctx["mesure"], blocs, annees=navigateur.ANNEES, thetas=registre,
               attendus=attendus, mode=ctx["mode"])
    g["refus"] = refus
    g["convention"] = ctx["convention"]
    g["conventions"] = navigateur._conventions(ctx["mesure"], traj.annees)
    g["vue"] = ctx["vue"]
    return g


def calculer_json(session: Any, texte: str) -> str:
    """L'entrée de la page : un réglage en JSON (avec `attendus` au besoin), le graphe en
    JSON."""
    choix = json.loads(texte)
    attendus = choix.pop("attendus", None)
    return json.dumps(calculer(session, choix, attendus), ensure_ascii=False)
