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
  que le modèle refuse ne sont pas calculées, et la page dit pourquoi. Avec la convention
  « parts_premiere_annee » (D-414, `choix["convention"]`, D-419), les années suivantes
  sont ventilées aux parts de la première là où ces parts existent ; chaque année qu'elle
  fait est rendue (`conventions`), et la page la marque à côté de chaque nombre.

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


#: La plage des résultats : tant de tirages des θ selon leurs lois, d'une graine fixée,
#: pour que la page redonne la même plage à chaque visite (D-459).
TIRAGES = 200
#: Les tirages des bandes de la page « Ce que ça change » (D-605) : moins que la plage du
#: jumeau, pour que le calcul dans le navigateur reste de quelques secondes.
TIRAGES_IMPACTS = 60
GRAINE = 20261115

#: D'où vient la loi d'un θ (`a_priori.yaml`, D-424, D-438) : une estimation publiée du
#: paramètre, une loi donnée par construction sur θ, des données fines, ou la loi large
#: de D-417 faute de source ; une ligne du magasin comportemental que porte la mesure
#: n'a pas d'entrée : sa plage est publiée, pas sa loi, elle garde la loi large.
ORIGINES_LOI = {
    "litterature": "une estimation publiée du paramètre",
    "construction": "par construction : la dispersion publiée qui définit θ",
    "donnees_fines": "les données fines du projet, combinées à la littérature",
    "large": "aucune estimation publiée : la loi large, N(½ ; ½)",
    "magasin": "la plage du magasin comportemental, sans loi publiée : la loi large",
}


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
        out = {"year": y["year"], "mechanical_frozen_eur": y["mechanical_frozen_eur"],
               "mechanical_aged_eur": y["mechanical_aged_eur"],
               "statistiques": {v: {"impulses": s.get("impulses"),
                                    "canaux": s.get("canaux")}
                                for v, s in y["statistiques"].items()}}
        if y.get("mechanical_by_layer") is not None:
            # Le coût de la couche des entreprises : les impôts que le canal ne lit plus
            # (D-440), quand le rapport n'en porte pas la somme d'avant (D-443).
            out["mechanical_by_layer"] = y["mechanical_by_layer"]
        return out

    out: dict[str, Any] = {
        "payload": {"rejeu": payload["rejeu"], "years": [ligne(y) for y in payload["years"]],
                    "carry": payload.get("carry"), "horizon": payload.get("horizon"),
                    "commit": payload.get("commit"), "scenario": payload.get("scenario"),
                    "persistence": payload["lectures"]["persistence"]},
        "premiere_annee": None}
    instruments = (payload.get("recalcul") or {}).get("instruments")
    if instruments:
        # La somme d'avant des instruments retirés du canal (D-440), que lit
        # `mesures.prelevements_lus` (D-443).
        out["payload"]["recalcul"] = {"instruments": {
            k: instruments[k] for k in ("retires", "variations_avant")}}
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
        self._mesures: dict[tuple[Any, ...], Any] = {}

    # ---------------------------------------------------------------- mesures
    def mesure(self, cle: str, vue: str, convention: str | None = None) -> Any:
        from impots.jumeau.mesures import Mesure

        if cle not in self.candidats:
            raise NavigateurError(f"candidat « {cle} » inconnu")
        if (cle, vue, convention) not in self._mesures:
            c = self.candidats[cle]
            self._mesures[(cle, vue, convention)] = Mesure.depuis_rapport(
                c["payload"], vue=vue, identifiant=cle, libelle=c["libelle"],
                auteur=c["auteur"], rapport=c["rapport"],
                premiere_annee=c["premiere_annee"], convention=convention)
        return self._mesures[(cle, vue, convention)]

    def mesure_structurel(self, cle: str, vue: str, convention: str | None = None) -> Any:
        """La mesure que lit le mode structurel (D-487) : celle du rapport, sauf une hausse
        du Smic que le bloc `travail` sait lire (`travail.mesure_smic`, D-478) : la passe de
        la première année relève le Smic, ses cotisations des employeurs sont payées par
        des employeurs privés, et elle ne porte pas d'autre prélèvement des entreprises
        (ni PFU ni impôt de la passe des entreprises). Dans la vue vieillie, avec la
        convention demandée seulement : les déciles de la première année sont alors ceux
        de la passe figée, marqués « parts_figee » (D-476). Sinon, la mesure du rapport,
        et ses refus."""
        from impots.jumeau.blocs import travail
        from impots.jumeau.ventilation import CONVENTION_VIEILLIE, COTISATIONS, payeur

        m = self.mesure(cle, vue, convention)
        k = (cle, vue, convention, "structurel")
        if k in self._mesures:
            return self._mesures[k]
        out = m
        pa = self.candidats[cle].get("premiere_annee")
        requete = (pa or {}).get("request") or {}
        smic = "smic_revalorisation" in (requete.get("reform") or {})
        premiere = m.annees[0] if m.annees else None
        autres = {i for i, v in ((m.entreprises or {}).get(premiere) or {}).items()
                  if i != COTISATIONS and abs(float(v)) > 1e-12}
        if (smic and payeur(pa) == "prives" and not autres
                and (vue == "figee" or convention)):
            try:
                out = travail.mesure_smic(m, pa)
            except travail.TravailError:
                out = m
            else:
                if vue != "figee":
                    conv = {axe: dict(a) for axe, a in out.conventions.items()}
                    conv.setdefault("menages", {})[premiere] = CONVENTION_VIEILLIE
                    out = dataclasses.replace(out, conventions=conv)
        seuil = (requete.get("reform") or {}).get("allegement_general_plafond")
        if seuil is not None and not smic and m.annees:
            # D-540 : une mesure qui baisse le seuil de sortie de la réduction générale
            # le déclare au bloc `travail`, qui fait diffuser une hausse du Smic sous le
            # barème de toutes les mesures de l'année ; sa loi reste dans sa passe.
            out = dataclasses.replace(out, travail={
                a: {travail.ALLEGEMENTS: {"plafond": float(seuil)}, "passe": True}
                for a in out.annees})
        if payeur(pa) == "publics":
            # D-500 : les cotisations de la rémunération publique ne sont pas un coût du
            # travail privé ; elles sortent des impulsions que lisent les blocs marchands.
            from impots.jumeau.papillon import remuneration_publique

            out = remuneration_publique(out)
        self._mesures[k] = out
        return out

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

    def structurel(self, cle: str, vue: str, convention: str | None = None
                   ) -> tuple[int, str | None]:
        """Combien d'années le mode structurel calcule pour une mesure d'étude, et le
        premier refus, sans faire un pas (J2, D-469) : les refus de D-412 sont ceux que
        les blocs lèvent en se préparant (`preparer`), avant le premier pas ; on les lève
        ici sur les mêmes années que `_derouler` essaie, de la dernière à la première.
        La page s'en sert pour griser le mode avant le clic ; le calcul reste celui de
        `calculer`, et `test_jumeau_navigateur.py` tient l'égalité des deux."""
        from impots.jumeau.blocs.entreprises import EntreprisesError
        from impots.jumeau.blocs.menages import MenagesError
        from impots.jumeau.pas import Modele

        mesure = self.mesure_structurel(cle, vue, convention)
        _, entrees, blocs, boucles = self._modele("structurel", mesure, cle)
        blocs = Modele(blocs, boucles).blocs
        refus: str | None = None
        for k in range(len(ANNEES), 0, -1):
            try:
                for b in blocs:
                    if hasattr(b, "preparer"):
                        b.preparer(_tronquer(entrees, k), [mesure])
                return k, refus
            except (EntreprisesError, MenagesError) as e:
                refus = refus or str(e)
        return 0, refus

    def thetas(self, mode: str, mesures: Sequence[Any], blocs: Sequence[Any]
               ) -> list[dict[str, Any]]:
        lus = {t for b in blocs for t in b.thetas}
        if any(b.nom == "mesures" for b in blocs):
            lus |= {k for m in mesures for k in (m.lignes or {})}
        appris = (self.donnees.get("juge") or {}).get("thetas", {})
        out = []
        for cle, ligne in thetas.registre(mesures).items():
            loi = loi_de(cle)
            out.append({"cle": cle, "bloc": ligne.bloc, "definition": ligne.definition,
                        "unite": ligne.unite, "a_zero": ligne.a_zero,
                        "a_demi": ligne.a_demi, "a_un": ligne.a_un,
                        "direction": ligne.direction, "source": ligne.source,
                        "verifiee": ligne.verifiee, "lu": cle in lus,
                        "monotone": ligne.monotone,
                        "loi": {"moyenne": loi.moyenne, "ecart_bas": loi.ecart_bas,
                                "ecart_haut": loi.ecart_haut,
                                "origine": origine_loi(cle)},
                        "histoire": appris.get(cle)})
        return out

    def _contexte(self, choix: Mapping[str, Any]) -> dict[str, Any]:
        """Ce que `calculer` et `portee` lisent d'un réglage : la mesure, le modèle, les θ
        du registre et ceux que le réglage donne."""
        from impots.jumeau.mesures import CONVENTION_PARTS

        mode, vue = choix.get("mode", "reduit"), choix.get("vue", "vieillie")
        if mode not in MODES or vue not in VUES:
            raise NavigateurError(f"mode « {mode} » ou vue « {vue} » inconnus")
        convention = choix.get("convention") or None
        if convention not in (None, CONVENTION_PARTS):
            raise NavigateurError(f"convention « {convention} » inconnue "
                                  f"({CONVENTION_PARTS})")
        cle = choix.get("candidat") or None
        composition = choix.get("composition") or None
        if composition:
            # Une proposition composée (D-605) : le mode structurel seul, le cadre commun
            # des rapports (`site_jumeau.donnees` le tient unique).
            if mode != "structurel":
                raise NavigateurError("une proposition composée se calcule dans le mode "
                                      "structurel (D-605)")
            cle = None
        elif not (cle and mode == "structurel"):
            convention = None
        illustratives: dict[str, str] = {}
        avertissements: list[str] = []
        composee: dict[str, Any] | None = None
        if composition:
            mesures, illustratives, avertissements = self.composer(composition, vue,
                                                                   convention)
            mesure = mesures[0]
        elif cle and choix.get("mesures_seules"):
            # D-655 : le programme comme ses mesures chiffrées et leur interaction.
            if mode != "structurel":
                raise NavigateurError("un programme composé de ses mesures se calcule dans "
                                      "le mode structurel (D-655)")
            mesures, composee = self.programme_compose(cle, vue, convention)
            mesure = mesures[0]
        elif cle:
            mesure = (self.mesure_structurel(cle, vue, convention) if mode == "structurel"
                      else self.mesure(cle, vue, convention))
            mesures = [mesure]
        elif choix.get("hypothese"):
            mesure = self.hypothese(choix["hypothese"])
            mesures = [mesure]
            illustratives[mesure.identifiant] = "loi hypothétique, déclarée sans passe"
        else:
            raise NavigateurError("ni candidat, ni loi hypothétique, ni proposition")
        depart, entrees, blocs, boucles = self._modele(mode, mesure, cle)
        registre = self.thetas(mode, mesures, blocs)
        donne = choix.get("theta") or {}
        theta = {t["cle"]: float(donne[t["cle"]]) for t in registre if t["cle"] in donne}
        return {"mode": mode, "vue": vue, "cle": cle, "convention": convention,
                "mesure": mesure, "mesures": mesures, "illustratives": illustratives,
                "composition": composition, "avertissements_composition": avertissements,
                "composee": composee,
                "depart": depart, "entrees": entrees, "blocs": blocs,
                "boucles": boucles, "registre": registre, "theta": theta}

    def _derouler(self, ctx: Mapping[str, Any], theta: Mapping[str, Any]
                  ) -> tuple[Any, str | None]:
        """La trajectoire d'un contexte sous θ (scalaires ou tableaux de tirages), et le
        refus qui a raccourci ses années (D-412), ou None."""
        from impots.jumeau.blocs.entreprises import EntreprisesError
        from impots.jumeau.blocs.menages import MenagesError
        from impots.jumeau.trajectoire import calculer

        refus: str | None = None
        annees, blocs = len(ANNEES), ctx["blocs"]
        while True:
            try:
                traj = calculer(ctx["depart"], entrees=_tronquer(ctx["entrees"], annees),
                                mesures=ctx["mesures"], theta=theta, blocs=blocs,
                                boucles=ctx["boucles"])
                return traj, refus
            except (EntreprisesError, MenagesError) as e:
                # Les refus de D-412 : une année que la mesure ne ventile pas. Les années
                # d'avant se calculent ; celles-ci restent absentes, la raison dite.
                if refus is None:
                    refus = str(e)
                annees -= 1
                if annees == 0:
                    return None, refus
                blocs = self._modele(ctx["mode"], ctx["mesure"], ctx["cle"])[2]
            except ValueError as e:
                return None, f"{type(e).__name__} : {e}"

    def portee(self, choix: Mapping[str, Any], tirages: int = TIRAGES,
               graine: int = GRAINE) -> dict[str, Any]:
        """La portée de chaque curseur et la plage des résultats, pour un réglage (D-459).

        Une seule trajectoire, vectorisée sur l'axe des tirages (CADRE.md §8) : le tirage
        0 est le réglage donné ; puis, pour chaque θ que le modèle lit, les autres à leur
        réglage, lui à chaque point où se lit sa boîte (0 et 1, ou la grille d'une ligne
        non monotone, D-427) ; puis `tirages` tirages de tous les θ ensemble, chacun selon
        sa loi (`a_priori`, D-424, D-438), tronquée à [0 ; 1] par rejet. La portée d'un θ
        est l'écart, à l'horizon, du plus bas et du plus haut de ses points au tirage 0 ;
        la plage d'une série, les quantiles de 5 à 95 % des tirages, chaque année."""
        ctx = self._contexte(choix)
        lus = [t for t in ctx["registre"] if t["lu"]]
        manque = [t["cle"] for t in lus if t["cle"] not in ctx["theta"]]
        if manque:
            raise NavigateurError(f"θ sans réglage : {manque} ; ils n'ont pas de défaut")
        lignes = thetas.registre(ctx["mesures"])
        base = {t["cle"]: ctx["theta"][t["cle"]] for t in lus}
        colonnes: dict[str, list[float]] = {c: [v] for c, v in base.items()}
        points: list[tuple[str, float]] = []
        for t in lus:
            for x in thetas.points_de_boite(lignes[t["cle"]]):
                points.append((t["cle"], float(x)))
                for c in colonnes:
                    colonnes[c].append(float(x) if c == t["cle"] else base[c])
        rng = np.random.default_rng(graine)
        lois = {t["cle"]: loi_de(t["cle"]) for t in lus}
        for c in colonnes:
            colonnes[c].extend(_tirer(lois[c], tirages, rng).tolist())
        theta = {c: np.asarray(v, dtype=float) for c, v in colonnes.items()}
        traj, refus = self._derouler(ctx, theta)
        out: dict[str, Any] = {"mode": ctx["mode"], "vue": ctx["vue"],
                               "candidat": ctx["cle"], "tirages": tirages,
                               "graine": graine, "refus": refus, "annees": list(ANNEES),
                               "calculees": [], "indicateurs": {}, "thetas": []}
        if traj is None:
            return out
        out["calculees"] = list(traj.annees)
        k = len(traj.annees) - 1
        debut = 1 + len(points)
        q = np.array([5, 25, 50, 75, 95], dtype=float)
        for cle, libelle, unite, valeurs in _indicateurs(traj):
            tirs = valeurs[:, debut:]
            out["indicateurs"][cle] = {
                "libelle": libelle, "unite": unite,
                "defaut": [float(x) for x in valeurs[:, 0]],
                "quantiles": [int(x) for x in q],
                "bande": [[float(x) for x in np.percentile(tirs[a], q)]
                          for a in range(len(traj.annees))]}
        for t in lus:
            idx = [1 + i for i, (c, _) in enumerate(points) if c == t["cle"]]
            effets = {}
            for cle, _l, _u, valeurs in _indicateurs(traj):
                lu = valeurs[k, idx] - valeurs[k, 0]
                effets[cle] = {"points": [float(x) for x in lu],
                               "bas": float(lu.min()), "haut": float(lu.max())}
            out["thetas"].append({"cle": t["cle"], "theta": base[t["cle"]],
                                  "points": [x for c, x in points if c == t["cle"]],
                                  "effets": effets})
        return out

    def calculer(self, choix: Mapping[str, Any]) -> dict[str, Any]:
        """La trajectoire d'un réglage : {mode, vue, candidat | hypothese, theta,
        convention}. θ n'a pas de défaut : un θ que le modèle lit et que le réglage ne
        donne pas est refusé (`thetas.lire`), et la page le dit.

        `convention` (« parts_premiere_annee », D-414) ne s'applique qu'au rapport d'un
        candidat dans le mode structurel, le seul qui lise ses ventilations ; le mode
        réduit et une loi hypothétique ne la lisent pas, et `convention` rendu le dit
        (None)."""
        ctx = self._contexte(choix)
        registre, theta, mesures = ctx["registre"], ctx["theta"], ctx["mesures"]
        lignes = thetas.registre(mesures)
        for t in registre:
            t["theta"] = theta.get(t["cle"])
            t["valeur"] = (None if t["theta"] is None else
                           valeur_a(lignes[t["cle"]], t["theta"], mesures))
        out: dict[str, Any] = {
            "mode": ctx["mode"], "vue": ctx["vue"], "candidat": ctx["cle"],
            "mesure": (_decrire_compose(ctx["composee"], mesures) if ctx["composee"]
                       else _decrire(mesures, ctx["composition"])),
            "annees": list(ANNEES), "thetas": registre, "refus": None, "calculees": [],
            "convention": ctx["convention"], "conventions": None}
        if ctx["composition"]:
            out["composition"] = [_une_mesure(m, ctx["illustratives"].get(m.identifiant))
                                  for m in mesures]
        if ctx["composee"]:
            out["composee"] = ctx["composee"]
        traj, out["refus"] = self._derouler(ctx, theta)
        mode, depart = ctx["mode"], ctx["depart"]
        if traj is None:
            out["series"], out["deciles"] = {}, {"absent": out["refus"]}
            out["avertissements"] = [*ctx["avertissements_composition"],
                                     *(m.avertissement for m in mesures if m.avertissement)]
            return out
        out["calculees"] = list(traj.annees)
        out["conventions"] = _conventions_de(mesures, traj.annees)
        out["avertissements"] = [*ctx["avertissements_composition"],
                                 *traj.avertissements]
        out["series"] = _series(traj)
        out["comptes"] = _comptes(traj, len(ANNEES))
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
        if choix.get("dimensions", True):
            out.update(self._dimensions(ctx, traj, int(choix.get("tirages") or 0)))
        return out

    # ---------------------------------------------------------------- but 29
    def reglage_impacts(self, choix: Mapping[str, Any]) -> dict[str, Any]:
        """Le réglage par défaut de la page « Ce que ça change » (D-605), quand le choix
        ne dit pas son mode : le jumeau complet (structurel) sur la population figée, avec
        la convention des parts de la première année (D-414), comme la cascade (D-484) ;
        pour une mesure d'étude qu'il refuse dès la première année, la chaîne des études
        (réduit, vieillie), et `pourquoi_mode` dit pourquoi."""
        from impots.jumeau.mesures import CONVENTION_PARTS

        choix = dict(choix)
        if choix.get("mode"):
            return choix
        choix.setdefault("vue", "figee")
        choix.setdefault("convention", CONVENTION_PARTS)
        choix["mode"] = "structurel"
        cle = choix.get("candidat")
        if cle and not choix.get("composition"):
            k, refus = self.structurel(cle, choix["vue"], choix["convention"])
            info, pas_compose = None, ""
            if not k and cle.startswith("pres2027_") and cle.endswith("_programme"):
                try:
                    _, info = self.programme_compose(cle, choix["vue"],
                                                     choix["convention"])
                except NavigateurError as e:
                    pas_compose = f", et ses mesures chiffrées ne se composent pas ({e})"
            if not k:
                if info is None:
                    choix.update(mode="reduit", vue="vieillie", convention=None,
                                 pourquoi_mode=("le jumeau complet refuse la mesure dès sa "
                                                f"première année ({refus}){pas_compose} : "
                                                "la chaîne des études, sans les ménages ni "
                                                "les entreprises"))
                else:
                    # D-655 : un programme refusé comme un tout se calcule comme ses
                    # mesures chiffrées et leur interaction (D-502), dans le jumeau complet.
                    choix["mesures_seules"] = True
                    choix["pourquoi_mode"] = (
                        f"le jumeau complet refuse le programme comme un tout ({refus}) ; "
                        f"il le calcule comme ses {len(info['mesures'])} mesures chiffrées "
                        f"ensemble, plus leur interaction (D-502, D-655)")
        return choix

    def programme_compose(self, cle: str, vue: str, convention: str | None
                          ) -> tuple[list[Any], dict[str, Any]]:
        """Un programme que le jumeau complet refuse comme un tout (ses prélèvements
        agrégés, D-412), pris comme ses mesures chiffrées ensemble, chacune comme le mode
        structurel la lit, plus la mesure d'interaction de sa passe (la convention
        « mesures_seules », D-502 ; D-655) : la somme de leurs coûts est le coût du
        programme, chaque année. Refusé (NavigateurError) si une mesure ne se calcule pas
        sur toutes les années, ou si la passe ne se sépare pas. Rend les mesures et ce
        que la page en dit (`composee`)."""
        k = (cle, vue, convention, "programme_compose")
        if k not in self._mesures:
            self._mesures[k] = self._programme_compose(cle, vue, convention)
        mesures, info = self._mesures[k]
        return list(mesures), info

    def _programme_compose(self, cle: str, vue: str, convention: str | None
                           ) -> tuple[list[Any], dict[str, Any]]:
        from impots.jumeau import papillon

        if not (cle.startswith("pres2027_") and cle.endswith("_programme")):
            raise NavigateurError(f"« {cle} » n'est pas le programme d'un candidat")
        slug = cle[len("pres2027_"):-len("_programme")]
        _, seules = papillon.cles(self, slug)
        if not seules:
            raise NavigateurError(f"« {cle} » : aucune mesure chiffrée seule")
        refusees = {}
        for c in seules:
            k, refus = self.structurel(c, vue, convention)
            if k < len(ANNEES):
                refusees[c] = refus or f"{k} années calculées sur {len(ANNEES)}"
        if refusees:
            # Une mesure qui manque fausserait l'interaction (le programme moins la
            # somme) : elle serait comptée dans l'interaction, sur le solde seul.
            raise NavigateurError("des mesures refusées : " + " ; ".join(
                f"« {c} » ({r})" for c, r in refusees.items()))
        try:
            mesures = papillon.mesures_seules(self, slug, vue, convention)
        except papillon.PapillonError as e:
            raise NavigateurError(str(e)) from e
        inter = mesures[-1]
        premiere = inter.annees[0]
        info = {
            "programme": cle, "libelle": self.candidats[cle]["libelle"],
            "mesures": [{"identifiant": m.identifiant, "libelle": m.libelle}
                        for m in mesures[:-1]],
            "interaction": {"identifiant": inter.identifiant,
                            "couts": {str(a): float(inter.couts[a]) for a in inter.annees},
                            "cotisations_employeurs": {
                                str(a): float(inter.impulsions[a]["cotisations_employeurs"])
                                for a in inter.annees}},
            "refusees": [], "decision": "D-655"}
        n = len(info["mesures"])

        def md(x: float) -> str:
            return f"{x:+.2f}".replace(".", ",").replace("-", "−")

        info["texte"] = (
            f"Calculé comme la somme de ses {n} mesures chiffrées, chacune avec sa passe, "
            f"plus l'interaction de la passe du programme (son coût en plus de leur somme : "
            f"{md(inter.couts[premiere])} Md€ en {premiere}, sur le solde seul ; l'écart "
            f"de ses cotisations des employeurs, "
            f"{md(inter.impulsions[premiere]['cotisations_employeurs'])} Md€) : le jumeau "
            f"complet refuse le programme comme un tout (sa passe ne ventile pas ses "
            f"prélèvements par impôt). Ne contient pas : la répartition de l'interaction "
            f"entre les ménages (le revenu par décile, le moral, la santé, les territoires "
            f"lisent la somme des passes de ses mesures, faites seules ; « Pour vous » lit le "
            f"programme entier), ni les mesures de son programme qu'aucun rapport ne chiffre. "
            f"Aucune de ses mesures chiffrées n'est refusée (D-502, D-655).")
        return mesures, info

    def composer(self, elements: Sequence[Mapping[str, Any]], vue: str,
                 convention: str | None) -> tuple[list[Any], dict[str, str], list[str]]:
        """Les mesures d'une proposition composée (D-605) : pour chaque élément, une mesure
        d'étude ({candidat, echelle, decalage}) ou une loi hypothétique ({hypothese}).
        Rend les mesures, {identifiant : raison} de celles qui ne sont pas une passe telle
        quelle, et les avertissements de la composition."""
        from impots.jumeau.proposition import PropositionError, transformer

        if not isinstance(elements, Sequence) or not elements:
            raise NavigateurError("une proposition vide : choisir au moins une mesure")
        mesures: list[Any] = []
        illustratives: dict[str, str] = {}
        vus: dict[str, int] = {}
        groupes: dict[str, list[str]] = {}
        for i, e in enumerate(elements):
            if e.get("hypothese"):
                h = self.hypothese(e["hypothese"])
                base = f"hypothese_{e['hypothese']['instrument']}"
                n = vus[base] = vus.get(base, 0) + 1
                m = dataclasses.replace(h, identifiant=base if n == 1 else f"{base}_{n}")
                illustratives[m.identifiant] = "loi hypothétique, déclarée sans passe"
            elif e.get("candidat"):
                cle = e["candidat"]
                m0 = self.mesure_structurel(cle, vue, convention)
                n = vus[cle] = vus.get(cle, 0) + 1
                try:
                    m, raison = transformer(
                        m0, echelle=float(e.get("echelle", 1.0)),
                        decalage=int(e.get("decalage", 0)),
                        identifiant=cle if n == 1 else f"{cle}_{n}", fin=ANNEES[-1])
                except PropositionError as err:
                    raise NavigateurError(str(err)) from err
                if raison:
                    illustratives[m.identifiant] = raison
                groupes.setdefault(self.candidats[cle]["groupe"], []).append(cle)
            else:
                raise NavigateurError(f"élément {i + 1} de la proposition : ni candidat ni "
                                      f"loi hypothétique")
            mesures.append(m)
        avertissements = []
        for groupe, cles in groupes.items():
            prog = [c for c in cles if c.endswith("_programme")]
            if prog and len(cles) > len(prog):
                avertissements.append(
                    f"{groupe} : le programme porte déjà ses mesures chiffrées ; y ajouter "
                    f"l'une d'elles la compte deux fois.")
        if len(mesures) > 1:
            avertissements.append(
                "Proposition composée : chaque mesure garde la passe de son rapport, faite "
                "seule ; leurs interactions statiques (un barème qui en touche un autre) "
                "ne sont pas chiffrées, leurs effets dans l'économie se cumulent dans le "
                "jumeau (D-605).")
        return mesures, illustratives, avertissements

    def _dimensions(self, ctx: Mapping[str, Any], traj: Any, tirages: int
                    ) -> dict[str, Any]:
        """Toutes les dimensions inscrites (`jumeau.impacts`, D-590), sur la trajectoire
        au réglage ; avec `tirages`, la même trajectoire vectorisée sur autant de tirages
        des θ lus, chacun selon sa loi, graine fixée (D-459), pour leurs bandes."""
        from impots.jumeau.impacts import tableau

        t = None
        if tirages > 0:
            rng = np.random.default_rng(GRAINE)
            lus = [x["cle"] for x in ctx["registre"] if x["lu"]]
            theta = {c: _tirer(loi_de(c), tirages, rng) for c in lus}
            t, _ = self._derouler(ctx, theta)
        return tableau.calculer_tout(
            traj.variante, traj.reference, ctx["depart"], self.cellules, trajectoire=traj,
            tirages=t, mesures=list(traj.mesures), illustratives=ctx["illustratives"],
            mode=ctx["mode"], thetas=ctx["registre"], juge=self.donnees.get("juge"),
            annees=tuple(traj.annees), programme=programme_age(ctx),
            composition=ctx.get("composition"), cle=ctx.get("cle"),
            **_options_compose(ctx))


#: Les dimensions qui lisent le revenu des ménages par décile, et pas un cas type du
#: programme entier : pour un programme composé de ses mesures (D-655), l'interaction de
#: sa passe n'y est pas répartie. Leur statut passe à « illustratif ».
LISENT_LES_DECILES = ("moral", "sante", "territoires")


def _options_compose(ctx: Mapping[str, Any]) -> dict[str, Any]:
    """Ce que le tableau lit d'un programme composé de ses mesures (D-655) : le statique
    de « Pour vous » est celui du programme entier (`cle_statique`, D-633) ; les
    dimensions qui lisent les déciles sont dites illustratives, avec la raison."""
    c = ctx.get("composee")
    if not c:
        return {}
    raison = ("programme calculé comme ses mesures chiffrées et leur interaction (D-655) : "
              "le revenu par décile est la somme des passes de ses mesures, faites seules ; "
              "l'interaction de la passe du programme n'y est pas répartie")
    return {"cle_statique": c["programme"],
            "degrader": dict.fromkeys(LISENT_LES_DECILES, raison),
            "limite_commune": c["texte"]}


def _decrire_compose(c: Mapping[str, Any], mesures: Sequence[Any]) -> dict[str, Any]:
    """Un programme composé de ses mesures (D-655) se décrit comme le programme."""
    return {"identifiant": c["programme"], "libelle": c["libelle"],
            "auteur": mesures[0].auteur, "origine": "mesures_seules",
            "rapport": None, "commit": None,
            "non_portes": {f"{m.identifiant} · {k}": v for m in mesures
                           for k, v in m.non_portes.items()}}


def programme_age(ctx: Mapping[str, Any]) -> str | None:
    """Le programme dont la santé lit l'âge légal (`impacts.sante`, D-622) : le nom du
    candidat d'un programme entier (« pres2027_<nom>_programme »), aucun pour une mesure
    seule ou une proposition composée (la page le dit : l'âge n'y est pas porté)."""
    cle = ctx.get("cle") or ""
    if ctx.get("composition") or not (cle.startswith("pres2027_")
                                      and cle.endswith("_programme")):
        return None
    return cle[len("pres2027_"):-len("_programme")]


def loi_de(cle: str) -> Any:
    """La loi de θ (D-424) ; la loi large de D-417 pour une ligne hors du registre."""
    from impots.jumeau import a_priori

    return a_priori.lois().get(cle, a_priori.LARGE)


def origine_loi(cle: str) -> str:
    """Une clé de `ORIGINES_LOI`."""
    from impots.jumeau import a_priori

    d = a_priori.lire().get(cle)
    if d is None:
        return "magasin"
    if "sans_source" in d:
        return "large"
    if "theta" in d:
        return "construction"
    return "donnees_fines" if "panel" in d else "litterature"


def _tirer(loi: Any, n: int, rng: Any) -> np.ndarray:
    """n tirages de la normale à deux écarts-types de `loi`, tronquée à [0 ; 1] par
    rejet ; refusé plutôt qu'écrêté si la loi tombe presque toute hors de la plage."""
    out = np.empty(0)
    for _ in range(200):
        z = rng.standard_normal(4 * n)
        x = loi.moyenne + z * np.where(z < 0, loi.ecart_bas, loi.ecart_haut)
        out = np.concatenate([out, x[(x >= 0.0) & (x <= 1.0)]])
        if out.size >= n:
            return out[:n]
    raise NavigateurError(f"loi {loi} : presque toute hors de [0 ; 1]")


def _indicateurs(traj: Any) -> list[tuple[str, str, str, np.ndarray]]:
    """Les résultats principaux, de forme (années, tirages), sur la convention de
    `_series` : la dette en points de PIB, le solde en Md€, le PIB en % de celui de la
    référence, l'emploi en milliers quand le mode l'écrit."""
    out = [("dette", "Dette publique", "points de PIB", 100.0 * np.asarray(traj.delta_b)),
           ("solde", "Solde des APU (B9)", "Md€", np.asarray(traj.difference("b9"))),
           ("pib", "PIB", "% du PIB de référence", 100.0 * np.asarray(traj.ecart_pib))]
    if all(e.present("emploi_total") for e in (*traj.reference, *traj.variante)):
        out.append(("emploi_total", "Emploi intérieur total", "milliers",
                    np.asarray(traj.difference("emploi_total"))))
    return out


def _conventions(mesure: Any, calculees: Sequence[int]) -> dict[str, Any] | None:
    """Les années calculées qu'une convention nommée a ventilées, par axe, et sa
    définition : la page les marque à côté de chaque nombre de ces années (D-414)."""
    from impots.jumeau.blocs.travail import CONVENTION_SMIC, TEXTE_SMIC
    from impots.jumeau.papillon import TEXTES as TEXTES_PAPILLON
    from impots.jumeau.ventilation import TEXTES

    textes = {**TEXTES, CONVENTION_SMIC: TEXTE_SMIC, **TEXTES_PAPILLON}
    axes = {axe: sorted(a for a in annees if a in calculees)
            for axe, annees in (mesure.conventions or {}).items()}
    axes = {axe: a for axe, a in axes.items() if a}
    if not axes:
        return None
    noms = sorted({mesure.conventions[axe][a] for axe, a_ in axes.items() for a in a_})
    # Deux conventions nommées : « parts_premiere_annee » (D-414) dans la vue figée,
    # « parts_figee » (D-476) dans la vue vieillie ; chacune dit sa définition.
    return {"noms": noms, "definition": " ; ".join(textes[n] for n in noms), "axes": axes,
            "annees": sorted({a for a_ in axes.values() for a in a_})}


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
            # Δb = (ΔD − b^r ΔY) / Y : la dette ajoutée, et ce que le PIB plus haut retire
            # au ratio comme dénominateur (D-459). Les deux se somment à l'écart.
            s["effets"] = {"dette_ajoutee": [], "denominateur": []}
            for e_r, e_v in zip(traj.reference, traj.variante, strict=True):
                y, b_r = _nombre(e_v["pib"]), _nombre(e_r["dette"]) / _nombre(e_r["pib"])
                s["effets"]["dette_ajoutee"].append(
                    100.0 * (_nombre(e_v["dette"]) - _nombre(e_r["dette"])) / y)
                s["effets"]["denominateur"].append(
                    -100.0 * b_r * (_nombre(e_v["pib"]) - _nombre(e_r["pib"])) / y)
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


#: Les comptes de l'année que la page montre autour du schéma du pas annuel (D-459) :
#: les emplois du PIB par grand poste, le compte des APU, la dette. (clé, libellé, champs)
POSTES_EMPLOIS = (
    ("c_menages", "Consommation des ménages", ("c_menages",)),
    ("c_apu", "Consommation des APU", ("c_apu",)),
    ("fbcf", "Investissement (FBCF)", ("fbcf_snf", "fbcf_sf", "fbcf_apu", "fbcf_menages",
                                       "fbcf_isbl")),
    ("exportations", "Exportations", ("exportations",)),
    ("importations", "Importations (en moins)", ("importations",)),
    ("non_ventile", "Effet sur le PIB non ventilé", ("emplois_non_ventiles",)),
    ("autres", "Autres emplois (ISBLSM, stocks, objets de valeur)",
     ("c_isbl", "var_stocks", "objets_valeur", "ventilation_emplois", "arrondi_emplois")),
)
COMPTES = (("pib", "PIB"), ("apu_recettes", "Recettes des APU"),
           ("apu_depenses_primaires", "Dépenses primaires des APU"),
           ("interets_nets", "Intérêts nets"), ("b9", "Solde (B9)"),
           ("dette_ouverture", "Dette en début d'année"), ("sfa", "Ajustement stock-flux"),
           ("dette", "Dette en fin d'année"), ("remunerations", "Rémunérations (D1)"),
           ("emploi_total", "Emploi (milliers)"), ("chomage", "Chômeurs (milliers)"))


def _comptes(traj: Any, longueur: int) -> dict[str, Any]:
    """Par année, l'écart variante − référence des comptes du pas : chaque poste des
    emplois du PIB (Md€, signé comme dans l'identité : les importations en moins), le
    compte des APU et la dette ; None quand un champ est absent d'un côté. L'identité
    des emplois (leur somme est l'écart du PIB) se lit dans `residu_emplois`."""
    def ecart(r: Etat, v: Etat, champ: str) -> float | None:
        if not (r.present(champ) and v.present(champ)):
            return None
        return _nombre(v[champ] - r[champ])

    manque = [None] * (longueur - len(traj.annees))
    postes: dict[str, list[float | None]] = {c: [] for c, _l, _ch in POSTES_EMPLOIS}
    comptes: dict[str, list[float | None]] = {c: [] for c, _l in COMPTES}
    residu: list[float | None] = []
    for r, v in zip(traj.reference, traj.variante, strict=True):
        somme = 0.0
        for cle, _l, champs in POSTES_EMPLOIS:
            x = [ecart(r, v, c) for c in champs]
            x = [y * REGISTRE[c].signe for y, c in zip(x, champs, strict=True)
                 if y is not None]
            postes[cle].append(sum(x) if x else None)
            somme += sum(x)
        for cle, _l in COMPTES:
            comptes[cle].append(ecart(r, v, cle))
        residu.append(None if comptes["pib"][-1] is None else comptes["pib"][-1] - somme)
    return {"postes": {c: v + manque for c, v in postes.items()},
            "libelles_postes": {c: lib for c, lib, _ch in POSTES_EMPLOIS},
            "comptes": {c: v + manque for c, v in comptes.items()},
            "libelles": dict(COMPTES), "residu_emplois": residu + manque}


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


def _une_mesure(m: Any, raison: str | None = None) -> dict[str, Any]:
    return {"identifiant": m.identifiant, "libelle": m.libelle, "auteur": m.auteur,
            "origine": m.origine, "rapport": m.rapport, "commit": m.commit,
            "non_portes": dict(m.non_portes), "annees": list(m.annees),
            "transformee": raison}


def _decrire(mesures: Sequence[Any], composition: Any) -> dict[str, Any]:
    """La mesure du réglage ; une proposition composée se décrit par ses mesures."""
    if not composition:
        d = _une_mesure(mesures[0])
        return {k: d[k] for k in ("identifiant", "libelle", "auteur", "origine", "rapport",
                                  "commit", "non_portes")}
    return {"identifiant": "proposition",
            "libelle": "Proposition composée : " + " ; ".join(m.libelle for m in mesures),
            "auteur": "le lecteur", "origine": "composition", "rapport": None,
            "commit": None,
            "non_portes": {f"{m.identifiant} · {k}": v for m in mesures
                           for k, v in m.non_portes.items()}}


def _conventions_de(mesures: Sequence[Any], calculees: Sequence[int]
                    ) -> dict[str, Any] | None:
    """`_conventions` sur plusieurs mesures : l'union de leurs axes et de leurs noms."""
    parts = [c for c in (_conventions(m, calculees) for m in mesures) if c]
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    axes: dict[str, set[int]] = {}
    for c in parts:
        for axe, a in c["axes"].items():
            axes.setdefault(axe, set()).update(a)
    noms = sorted({n for c in parts for n in c["noms"]})
    definitions = list(dict.fromkeys(c["definition"] for c in parts))
    return {"noms": noms, "definition": " ; ".join(definitions),
            "axes": {axe: sorted(a) for axe, a in axes.items()},
            "annees": sorted({a for c in parts for a in c["annees"]})}


def impacts_json(session: Session, texte: str) -> str:
    """L'entrée de la page « Ce que ça change » (D-605) : un réglage en JSON (un candidat,
    une loi hypothétique ou une `composition`, et `tirages`), le résultat avec toutes les
    dimensions, en JSON strict (un nombre non fini est absent)."""
    from impots.jumeau.impacts.tableau import propre

    choix = {"tirages": TIRAGES_IMPACTS, **session.reglage_impacts(json.loads(texte)),
             "dimensions": True}
    pourquoi = choix.pop("pourquoi_mode", None)
    if not choix.get("theta"):
        # Chaque θ à ½, le centre de sa boîte : le défaut de la page (D-605), dit.
        registre = session._contexte({**choix, "theta": {}})["registre"]
        choix["theta"] = {t["cle"]: 0.5 for t in registre}
    out = session.calculer(choix)
    out["reglage"] = {k: choix.get(k) for k in ("mode", "vue", "convention", "tirages")}
    out["pourquoi_mode"] = pourquoi
    return json.dumps(propre(out), ensure_ascii=False)


def portee_json(session: Session, texte: str) -> str:
    """La portée des curseurs d'un réglage, en JSON (D-459)."""
    return json.dumps(session.portee(json.loads(texte)), ensure_ascii=False)


def calculer_json(session: Session, texte: str) -> str:
    """L'entrée de la page : un réglage en JSON, le résultat en JSON."""
    return json.dumps(session.calculer(json.loads(texte)), ensure_ascii=False)


if __name__ == "__main__":
    import sys

    if sys.argv[1:] != ["ecrire"]:
        sys.exit("usage : python -m impots.jumeau.navigateur ecrire")
    print(f"-> {ecrire()}")
