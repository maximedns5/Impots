"""Le jumeau dans le navigateur (but 23, lot 7, D-415) : ce que la page « Le jumeau » fait
tourner, tel quel, dans Pyodide.

LE MÊME CODE DES DEUX CÔTÉS. La page charge Pyodide et numpy, écrit ce paquet (les modules
de `impots` que ce fichier importe, et les fichiers de paramètres qu'ils lisent) dans le
système de fichiers du navigateur, puis appelle `Session.calculer`. Les tests appellent la
même fonction en Python, et la page doit afficher les nombres de `trajectoire.calculer` :
aucun portage, donc aucune dérive quand les équations changent.

CE QUE CE MODULE NE FAIT PAS : lire un fichier de données. Ses entrées sont un seul
dictionnaire, que le site précalcule (`impots.site_jumeau`) depuis des fichiers commités :

* `entrees` (`reports/jumeau/entrees_navigateur.json`, écrit une fois depuis les données
  hors git par `python -m impots.jumeau.navigateur ecrire`, comme D-399 l'a fait pour la
  variante de dépense publique) : l'état publié de 2025, les cinquante cellules de ménages
  de 2024 et les cellules d'entreprises de 2023 (des sommes pondérées, aucune donnée
  individuelle), les tables de Mésange des instruments d'une loi hypothétique ;
* `candidats` : pour chaque rapport d'étude commité, ce que `Mesure.depuis_rapport` en
  lit, et rien d'autre (`alleger`).

LES DEUX MODES.

* RÉDUIT : les blocs du lot 1 (`ordre_lot1`), depuis le point de départ des rapports
  (`depart_depuis_start`), le cadre, la persistance et le canal des créations que le
  rapport porte. C'est la chaîne des études : à θ½, Δb₂₀₃₅ est celui qu'elles publient.
* STRUCTUREL : le modèle complet (`ordre_structurel`), depuis l'état publié de 2025, sous
  le même cadre. Un rapport ne ventile que sa première année figée (D-412) : les années
  que le modèle refuse ne sont pas calculées, et la page dit pourquoi.

Un champ qu'aucun bloc n'écrit dans un mode est absent : `None`, jamais zéro.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from impots.jumeau import thetas
from impots.jumeau.champs import DEPENSES, EMPLOIS, RECETTES, REGISTRE, REVENUS
from impots.jumeau.etat import Etat

ROOT = Path(__file__).resolve().parents[3]
FICHIER = ROOT / "reports" / "jumeau" / "entrees_navigateur.json"
VERSION = 1
ANNEES = tuple(range(2026, 2036))
MODES = ("reduit", "structurel")
VUES = ("vieillie", "figee")

#: Les lois hypothétiques : les cinq variantes que Mésange publie (`comparaison`), un
#: montant en Md€ par an, signe du moteur (un coût pour les APU est positif : une baisse
#: d'impôt ou une hausse de dépense).
HYPOTHESES = {
    "impot_sur_le_revenu": "Impôt sur le revenu",
    "tva": "TVA",
    "cotisations_employeurs": "Cotisations sociales employeurs",
    "investissement_public": "Investissement public",
    "depense_publique": "Dépense publique (composée comme Mésange)",
}

#: Les séries que la page trace : (champ, libellé, unité, échelle). L'écart est
#: variante − référence ; le PIB et la dette ont leur forme propre (`_series`).
SERIES = (
    ("dette", "Dette publique", "points de PIB"),
    ("solde", "Solde des APU (B9)", "Md€"),
    ("pib", "PIB", "% du PIB de référence"),
    ("emploi_total", "Emploi intérieur total", "milliers"),
    ("creations_societes", "Créations de sociétés", "sociétés"),
    ("fermetures_societes", "Fermetures de sociétés", "sociétés"),
    ("exportations", "Exportations", "Md€"),
    ("importations", "Importations", "Md€"),
)


class NavigateurError(ValueError):
    """Une entrée que la page ne peut pas faire tourner."""


# --------------------------------------------------------------------------- #
# l'état, en JSON, au bit
# --------------------------------------------------------------------------- #
def etat_vers_dict(etat: Etat) -> dict[str, Any]:
    """Un état d'un tirage, champ par champ dans son ordre, chaque contribution d'un champ
    additif dans le sien : relu par `etat_depuis_dict`, il redonne chaque somme au bit."""
    if etat.n != 1:
        raise NavigateurError(f"un état de {etat.n} tirages : la page part d'un seul")
    champs = []
    for nom in etat.champs():
        if REGISTRE[nom].additif:
            champs.append([nom, [[o, m, float(v[0])] for (o, m), v in etat.de(nom).items()]])
        else:
            champs.append([nom, float(etat[nom][0])])
    return {"annee": etat.annee, "publie": etat.publie, "champs": champs}


def etat_depuis_dict(d: Mapping[str, Any]) -> Etat:
    etat = Etat(int(d["annee"]), 1, publie=bool(d["publie"]))
    for nom, valeur in d["champs"]:
        if not REGISTRE[nom].additif:
            etat.fixer(nom, valeur)
        elif not valeur:
            etat.declarer(nom)
        else:
            for origine, mesure, v in valeur:
                etat.ecrire(nom, (origine, mesure), v)
    return etat


def parts(etat: Etat) -> dict[str, float]:
    """Les parts de chaque groupe dans l'état publié, pour `depart_depuis_start` : les
    emplois et les revenus sur le PIB, les recettes et les dépenses primaires sur leurs
    totaux. Un champ absent de l'état n'a pas de part."""
    out: dict[str, float] = {}
    for noms, total in ((EMPLOIS, "pib"), (REVENUS, "pib"), (RECETTES, "apu_recettes"),
                        (DEPENSES, "apu_depenses_primaires")):
        t = float(etat[total][0])
        for c in noms:
            if etat.present(c):
                out[c] = float(etat[c][0]) / t
    return out


# --------------------------------------------------------------------------- #
# les entrées de la page
# --------------------------------------------------------------------------- #
def alleger(payload: Mapping[str, Any], premiere: Mapping[str, Any] | None
            ) -> dict[str, Any]:
    """Ce que `Mesure.depuis_rapport` et le mode réduit lisent d'un rapport du chemin
    annuel et de sa première année, et rien d'autre."""
    def ligne(y: Mapping[str, Any]) -> dict[str, Any]:
        return {"year": y["year"], "mechanical_frozen_eur": y["mechanical_frozen_eur"],
                "mechanical_aged_eur": y["mechanical_aged_eur"],
                "statistiques": {v: {"impulses": s.get("impulses"),
                                     "canaux": s.get("canaux")}
                                 for v, s in y["statistiques"].items()}}

    out: dict[str, Any] = {
        "payload": {"rejeu": payload["rejeu"], "years": [ligne(y) for y in payload["years"]],
                    "carry": payload.get("carry"), "horizon": payload.get("horizon"),
                    "commit": payload.get("commit"), "scenario": payload.get("scenario"),
                    "persistence": payload["lectures"]["persistence"]},
        "premiere_annee": None}
    if premiere is not None:
        def reponse(r: Mapping[str, Any]) -> dict[str, Any]:
            deciles = r.get("deciles")
            return {"reform_cost": r["reform_cost"], "deltas": r.get("deltas"),
                    "deciles": None if deciles is None else [
                        {k: d.get(k) for k in ("decile", "mean_delta", "n_households")}
                        for d in deciles]}

        kind = premiere.get("kind")
        if kind == "mixte":
            rep = {k: reponse(premiere["response"][k]) for k in ("menages", "entreprises")}
        else:
            rep = reponse(premiere["response"])
        out["premiere_annee"] = {"kind": kind, "commit": premiere.get("commit"),
                                 "scenario": premiere.get("scenario"),
                                 "request": premiere["request"], "response": rep}
    return out


def ecrire(chemin: Path = FICHIER) -> Path:
    """Les entrées hors rapports, depuis les données hors git (`make data`,
    `scripts/jumeau_cellules.py`) : écrites une fois, commitées, relues par le site."""
    import subprocess

    from impots.jumeau.blocs.entreprises import CELLULES_2023
    from impots.jumeau.cellules import FICHIER as CELLULES
    from impots.jumeau.cellules import Cellules
    from impots.jumeau.historique import etat_initial
    from impots.macro import store
    from impots.predictif import retroaction

    entreprises = json.loads(CELLULES_2023.read_text(encoding="utf-8"))
    cellules = json.loads(CELLULES.read_text(encoding="utf-8"))
    Cellules.lire()                                    # ses refus, avant d'écrire
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.strip()
    contenu = {
        "version": VERSION,
        "commit": commit,
        "sources": {
            "depart_publie": "jumeau.historique.etat_initial(2025) : Insee, comptes "
                             "nationaux annuels base 2020 (t. 1.101, 1.105, 3.201, "
                             "6.208, 6.210), Eurostat, séries de `jumeau.series` (D-412)",
            "cellules": f"{CELLULES.name} (D-409), commit {cellules['meta'].get('commit')}",
            "entreprises": f"{CELLULES_2023.name}, millésime {entreprises.get('vintage')}",
            "mesange": "retroaction.replay_tables : Insee, Mésange (G2017-04) ; IMK WP 117",
        },
        "depart_publie": etat_vers_dict(etat_initial(2025)),
        "cellules": {k: cellules[k] for k in ("annee", "types", "deciles", "valeurs",
                                              "parts_offre")},
        "entreprises": {"vintage": entreprises.get("vintage"),
                        "cells_are_synthetic": entreprises.get("cells_are_synthetic"),
                        "cells": [{k: c[k] for k in ("naf_section", "taille", "n_firms",
                                                     "value_added_total", "result_total")}
                                  for c in entreprises["cells"]]},
        "mesange": retroaction.replay_tables(store.load(), sorted(HYPOTHESES)),
    }
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    return chemin


def lire(chemin: Path = FICHIER) -> dict[str, Any]:
    if not chemin.exists():
        raise NavigateurError(f"{chemin} absent : `python -m impots.jumeau.navigateur "
                              f"ecrire`, là où les données sont")
    return json.loads(chemin.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# la session : les entrées lues une fois, une trajectoire par réglage
# --------------------------------------------------------------------------- #
_NOMBRE = re.compile(r"^\s*([−-]?\d+(?:[.,]\d+)?)(?![\d.,])")


def _ancre(texte: str) -> float | None:
    """Le nombre seul d'une valeur publiée (« 0,44 (Mésange) » → 0,44), sinon None."""
    m = _NOMBRE.match(texte)
    if m is None or ";" in texte:
        return None
    return float(m[1].replace("−", "-").replace(",", "."))


def valeur_a(ligne: thetas.Ligne, theta: float, mesures: Sequence[Any]) -> float | None:
    """La valeur du paramètre à θ, quand ses trois ancres publiées sont des nombres :
    linéaire par morceaux par le centre, la convention de chaque ligne du registre
    (CADRE.md §7). Une ligne du comportement se lit sur sa ligne du rapport."""
    from impots.predictif import rejouer

    for m in mesures:
        row = (m.lignes or {}).get(ligne.cle)
        if row is not None:
            return float(rejouer.value_at(row, theta))
    a = [_ancre(x) for x in (ligne.a_zero, ligne.a_demi, ligne.a_un)]
    if any(x is None for x in a):
        return None
    bas, centre, haut = a
    if theta <= 0.5:
        return centre - (1.0 - 2.0 * theta) * (centre - bas)
    return centre + (2.0 * theta - 1.0) * (haut - centre)


class Session:
    """Les entrées de la page, lues une fois ; `calculer` à chaque réglage."""

    def __init__(self, donnees: Mapping[str, Any]) -> None:
        from impots.jumeau.blocs.entreprises import population
        from impots.jumeau.cellules import Cellules

        entrees = donnees["entrees"]
        self.donnees = donnees
        self.publie = etat_depuis_dict(entrees["depart_publie"])
        self.parts = parts(self.publie)
        c = entrees["cellules"]
        self.cellules = Cellules(valeurs={k: np.asarray(v, dtype=float)
                                          for k, v in c["valeurs"].items()},
                                 parts_offre=c["parts_offre"], annee=int(c["annee"]))
        e = entrees["entreprises"]
        millesime = str(e.get("vintage", "?")) + (" (synthétique)"
                                                  if e.get("cells_are_synthetic") else "")
        self.population = population(e["cells"], millesime)
        self.tables = entrees["mesange"]
        self.candidats = donnees["candidats"]
        self.cadre = donnees["cadre"]
        self._mesures: dict[tuple[str, str], Any] = {}

    # ---------------------------------------------------------------- mesures
    def mesure(self, cle: str, vue: str) -> Any:
        from impots.jumeau.mesures import Mesure

        if cle not in self.candidats:
            raise NavigateurError(f"candidat « {cle} » inconnu")
        if (cle, vue) not in self._mesures:
            c = self.candidats[cle]
            self._mesures[(cle, vue)] = Mesure.depuis_rapport(
                c["payload"], vue=vue, identifiant=cle, libelle=c["libelle"],
                auteur=c["auteur"], rapport=c["rapport"],
                premiere_annee=c["premiere_annee"])
        return self._mesures[(cle, vue)]

    def hypothese(self, spec: Mapping[str, Any]) -> Any:
        """Une loi hypothétique : un instrument, un montant (Md€ par an, coût pour les
        APU positif), ses années. Ses chocs sont ceux de la variante de Mésange de
        l'instrument (`comparaison`), au montant dit ; son choc aux ménages, au prorata
        des cellules ; son impulsion, quand la boucle des études lit l'instrument."""
        from impots.jumeau.comparaison import COMPOSITION_DEPENSE, _parts
        from impots.jumeau.mesures import Mesure

        instrument = spec["instrument"]
        if instrument not in HYPOTHESES:
            raise NavigateurError(f"instrument « {instrument} » inconnu ({sorted(HYPOTHESES)})")
        v = float(spec["montant"])
        debut, fin = int(spec["debut"]), int(spec["fin"])
        if not (ANNEES[0] <= debut <= fin <= ANNEES[-1]):
            raise NavigateurError(f"années {debut} à {fin} hors de {ANNEES[0]}–{ANNEES[-1]}")
        annees = range(debut, fin + 1)
        cel = self.cellules
        menages = entreprises = None
        if instrument == "impot_sur_le_revenu":
            choc = {"apu_r_d5": v}
            cle = _parts(cel.par_decile("ir"))
            menages = {a: {"deciles": [v * x for x in cle]} for a in annees}
        elif instrument == "tva":
            choc = {"apu_r_d2": v}
            cle = _parts(cel.par_decile("tva"))
            menages = {a: {"deciles": [v * x for x in cle]} for a in annees}
        elif instrument == "cotisations_employeurs":
            choc = {"apu_r_d61": v}
            entreprises = {a: {"cotisations_employeurs": -v} for a in annees}
        elif instrument == "investissement_public":
            choc = {"apu_d_p51g": v}
        else:
            choc = {c: p * v for c, p in COMPOSITION_DEPENSE.items()}
            cle = _parts(sum(cel.par_decile(n) for n in
                             ("retraite", "chomage_brut", "prestations")))
            menages = {a: {"deciles": [COMPOSITION_DEPENSE["apu_d_d62"] * v * x
                                       for x in cle]} for a in annees}
        couvert = instrument in self.tables["instruments"]
        tables = ({"horizons": self.tables["horizons"], "court": self.tables["court"],
                   "instruments": {instrument: self.tables["instruments"][instrument]}}
                  if couvert else None)
        libelle = (f"{HYPOTHESES[instrument]} : {v:+g} Md€ par an de coût pour les APU, "
                   f"{debut} à {fin}")
        m = Mesure.hypothese(
            "hypothese", libelle, chocs={a: dict(choc) for a in annees},
            impulsions=({a: {instrument: v} for a in annees} if couvert else None),
            macro=tables)
        return dataclasses.replace(m, menages=menages, entreprises=entreprises)

    # ---------------------------------------------------------------- modèle
    def _modele(self, mode: str, mesure: Any, cle: str | None) -> tuple[Any, ...]:
        from impots.jumeau.blocs import ordre_lot1, ordre_structurel
        from impots.jumeau.pas import Entrees
        from impots.jumeau.trajectoire import depart_depuis_start

        payload = self.candidats[cle]["payload"] if cle else None
        rejeu = payload["rejeu"] if payload else self.cadre
        entrees = Entrees.depuis_rejeu(rejeu, ANNEES)
        if mode == "reduit":
            depart = depart_depuis_start(rejeu["start"], self.parts)
            persistance = payload["persistence"] if payload else self.cadre["persistence"]
            blocs = ordre_lot1(depart, persistance=persistance,
                               boucle=rejeu["looped"] if payload else True,
                               creations=bool(rejeu.get("creations")) if payload else False)
            return depart, entrees, blocs, ()
        depart = self.publie
        blocs, boucles = ordre_structurel(depart, self.population, self.cellules)
        return depart, entrees, blocs, boucles

    def thetas(self, mode: str, mesures: Sequence[Any], blocs: Sequence[Any]
               ) -> list[dict[str, Any]]:
        lus = {t for b in blocs for t in b.thetas}
        if any(b.nom == "mesures" for b in blocs):
            lus |= {k for m in mesures for k in (m.lignes or {})}
        return [{"cle": cle, "bloc": ligne.bloc, "definition": ligne.definition,
                 "unite": ligne.unite, "a_zero": ligne.a_zero, "a_demi": ligne.a_demi,
                 "a_un": ligne.a_un, "direction": ligne.direction, "source": ligne.source,
                 "verifiee": ligne.verifiee, "lu": cle in lus}
                for cle, ligne in thetas.registre(mesures).items()]

    def calculer(self, choix: Mapping[str, Any]) -> dict[str, Any]:
        """La trajectoire d'un réglage : {mode, vue, candidat | hypothese, theta}. θ n'a
        pas de défaut : un θ que le modèle lit et que le réglage ne donne pas est refusé
        (`thetas.lire`), et la page le dit."""
        from impots.jumeau.blocs.entreprises import EntreprisesError
        from impots.jumeau.blocs.menages import MenagesError
        from impots.jumeau.trajectoire import calculer

        mode, vue = choix.get("mode", "reduit"), choix.get("vue", "vieillie")
        if mode not in MODES or vue not in VUES:
            raise NavigateurError(f"mode « {mode} » ou vue « {vue} » inconnus")
        cle = choix.get("candidat") or None
        if cle:
            mesure = self.mesure(cle, vue)
        elif choix.get("hypothese"):
            mesure = self.hypothese(choix["hypothese"])
        else:
            raise NavigateurError("ni candidat ni loi hypothétique")
        depart, entrees, blocs, boucles = self._modele(mode, mesure, cle)
        registre = self.thetas(mode, [mesure], blocs)
        donne = choix.get("theta") or {}
        theta = {t["cle"]: float(donne[t["cle"]]) for t in registre if t["cle"] in donne}
        lignes = thetas.registre([mesure])
        for t in registre:
            t["theta"] = theta.get(t["cle"])
            t["valeur"] = (None if t["theta"] is None else
                           valeur_a(lignes[t["cle"]], t["theta"], [mesure]))
        out: dict[str, Any] = {
            "mode": mode, "vue": vue, "candidat": cle, "mesure": {
                "identifiant": mesure.identifiant, "libelle": mesure.libelle,
                "auteur": mesure.auteur, "origine": mesure.origine,
                "rapport": mesure.rapport, "commit": mesure.commit,
                "non_portes": dict(mesure.non_portes)},
            "annees": list(ANNEES), "thetas": registre, "refus": None, "calculees": []}
        annees = len(ANNEES)
        while True:
            try:
                traj = calculer(depart, entrees=_tronquer(entrees, annees), mesures=[mesure],
                                theta=theta, blocs=blocs, boucles=boucles)
                break
            except (EntreprisesError, MenagesError) as refus:
                # Les refus de D-412 : une année que la mesure ne ventile pas. Les années
                # d'avant se calculent ; celles-ci restent absentes, la raison dite.
                if out["refus"] is None:
                    out["refus"] = str(refus)
                annees -= 1
                if annees == 0:
                    traj = None
                    break
                blocs = self._modele(mode, mesure, cle)[2]
            except ValueError as refus:
                out["refus"] = f"{type(refus).__name__} : {refus}"
                traj = None
                break
        if traj is None:
            out["series"], out["deciles"] = {}, {"absent": out["refus"]}
            out["avertissements"] = [a for a in (mesure.avertissement,) if a]
            return out
        out["calculees"] = list(traj.annees)
        out["avertissements"] = list(traj.avertissements)
        out["series"] = _series(traj)
        # Les années refusées sont absentes : None, sur toute la longueur de la page.
        manque = [None] * (len(ANNEES) - len(traj.annees))
        for serie in out["series"].values():
            for nom in ("reference", "variante", "ecart"):
                serie[nom] = serie[nom] + manque
            serie["decomposition"] = {c: v + manque for c, v in
                                      serie["decomposition"].items()}
        out["deciles"] = (_deciles(traj, depart, self.cellules)
                          if mode == "structurel" else
                          {"absent": "le mode réduit ne porte pas les ménages par cellule : "
                                     "les gagnants et les perdants se lisent dans le mode "
                                     "structurel"})
        return out


def _tronquer(entrees: Any, k: int) -> Any:
    if k == len(entrees.annees):
        return entrees
    return dataclasses.replace(entrees, annees=entrees.annees[:k],
                               croissance_reelle=entrees.croissance_reelle[:k],
                               prix=entrees.prix[:k], taux_reference=entrees.taux_reference[:k])


def _nombre(x: Any) -> float:
    return float(np.asarray(x, dtype=float).reshape(-1)[0])


def _etiquette(cle: tuple[str, str]) -> str:
    origine, mesure = cle
    return origine if not mesure else f"{origine} · {mesure}"


def _additif(traj: Any, champ: str, echelle: Sequence[float] | None = None
             ) -> dict[str, Any]:
    """Les deux niveaux, l'écart et sa décomposition par (bloc, mesure) d'un champ
    additif ; None les années où il est absent, d'un côté ou de l'autre."""
    ref: list[float | None] = []
    var: list[float | None] = []
    ecart: list[float | None] = []
    par_annee: list[dict[str, float] | None] = []
    for k, (r, v) in enumerate(zip(traj.reference, traj.variante, strict=True)):
        if not (r.present(champ) and v.present(champ)):
            ref.append(None)
            var.append(None)
            ecart.append(None)
            par_annee.append(None)
            continue
        e = 1.0 if echelle is None else echelle[k]
        ref.append(_nombre(r[champ]))
        var.append(_nombre(v[champ]))
        ecart.append(_nombre((v[champ] - r[champ]) * e))
        dr, dv = r.de(champ), v.de(champ)
        zero = np.zeros(v.n)
        par_annee.append({_etiquette(c): _nombre((dv.get(c, zero) - dr.get(c, zero)) * e)
                          for c in sorted(set(dr) | set(dv))})
    cles = sorted({c for d in par_annee if d for c, x in d.items() if x != 0.0})
    parts = {c: [None if d is None else d.get(c, 0.0) for d in par_annee] for c in cles}
    return {"reference": ref, "variante": var, "ecart": ecart, "decomposition": parts}


def _series(traj: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for champ, libelle, unite in SERIES:
        if champ == "dette":
            r, v = traj.niveaux("ratio_dette")
            s: dict[str, Any] = {"reference": [100.0 * _nombre(x) for x in r],
                                 "variante": [100.0 * _nombre(x) for x in v],
                                 "ecart": [100.0 * _nombre(x) for x in traj.delta_b]}
            parts: dict[str, list[float]] = {}
            for k, annee in enumerate(traj.annees):
                for c, x in traj.decomposition(annee).items():
                    parts.setdefault(_etiquette(c), [0.0] * len(traj.annees))[k] = (
                        100.0 * _nombre(x))
            s["decomposition"] = {c: v for c, v in parts.items() if any(v)}
            s["niveaux"] = "% du PIB"
        elif champ == "pib":
            pib_ref = [_nombre(e["pib"]) for e in traj.reference]
            s = _additif(traj, "pib", [100.0 / y for y in pib_ref])
            s["ecart"] = [100.0 * _nombre(x) for x in traj.ecart_pib]
            s["niveaux"] = "Md€"
        elif champ == "solde":
            s = _additif(traj, "b9")
            s["niveaux"] = "Md€"
        else:
            s = _additif(traj, champ)
            s["niveaux"] = REGISTRE[champ].unite
        s.update(champ=champ, libelle=libelle, unite=unite)
        if all(x is None for x in s["ecart"]):
            s["absent"] = ("aucun bloc de ce mode n'écrit ce champ : il est absent, pas "
                           "nul")
        out[champ] = s
    return out


def _deciles(traj: Any, depart: Etat, cellules: Any) -> dict[str, Any]:
    """Par année et par décile : l'écart moyen du revenu disponible par ménage (€ par
    an), sa part statique (le choc de la mesure sur le décile) et sa part dynamique
    (l'emploi, les salaires, le chômage), les parts de ménages gagnants et perdants."""
    from impots.jumeau.blocs.menages import choc_menages
    from impots.jumeau.cellules import N_DECILES, TYPES
    from impots.jumeau.gagnants import SEUIL, gagnants_perdants

    g = gagnants_perdants(traj, depart, cellules)
    menages = np.asarray(cellules["menages"], dtype=float)
    par_decile = menages.reshape(N_DECILES, len(TYPES)).sum(axis=1)
    annees: dict[str, Any] = {}
    for k, annee in enumerate(traj.annees):
        total = g.ecart_md[k, :, 0].reshape(N_DECILES, len(TYPES)).sum(axis=1)
        statique = np.zeros(N_DECILES)
        for m in traj.mesures:
            choc = choc_menages(m, annee).get("deciles")
            if choc is not None:
                statique = statique + np.asarray(choc, dtype=float)
        pm = g.par_menage[k, :, 0]
        gagne = ((pm > SEUIL) * menages).reshape(N_DECILES, len(TYPES)).sum(axis=1)
        perd = ((pm < -SEUIL) * menages).reshape(N_DECILES, len(TYPES)).sum(axis=1)
        annees[str(annee)] = {
            "euros_par_menage": [float(x) for x in total * 1e9 / par_decile],
            "statique": [float(x) for x in statique * 1e9 / par_decile],
            "dynamique": [float(x) for x in (total - statique) * 1e9 / par_decile],
            "part_gagnants": [float(x) for x in gagne / par_decile],
            "part_perdants": [float(x) for x in perd / par_decile]}
    return {"seuil": SEUIL, "annees": annees}


def calculer_json(session: Session, texte: str) -> str:
    """L'entrée de la page : un réglage en JSON, le résultat en JSON."""
    return json.dumps(session.calculer(json.loads(texte)), ensure_ascii=False)


if __name__ == "__main__":
    import sys

    if sys.argv[1:] != ["ecrire"]:
        sys.exit("usage : python -m impots.jumeau.navigateur ecrire")
    print(f"-> {ecrire()}")
