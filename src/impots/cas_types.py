"""Les cas types de « Pour vous » (but 29, volet `cas`, D-630 à D-634), chiffrés d'avance.

Le lecteur dit sa situation ; la page lui montre ce qu'une mesure change pour un ménage
comme le sien. Elle tourne dans le navigateur, sans OpenFisca (D-415) : ce module chiffre
d'avance, pour chaque cas type de la grille et chaque scénario de la bibliothèque (les
programmes, leurs mesures, les volets des textes), le ménage passé par OpenFisca au droit
de 2026, avant et après la réforme du scénario, et écrit le tableau que lit la dimension
`jumeau.impacts.pour_vous` (`jumeau/parametres/cas_types.json`, commité : des cas types,
aucune personne).

LE CALCUL. Tous les ménages de la grille dans une seule simulation, par scénario (les
identifiants préfixés : les entités ne se mêlent pas), chaque ligne du registre du moteur
(`engine.outputs`), le revenu disponible lu par ménage. La commande refuse d'écrire si un
ménage pris seul (`engine.compute`) ne redonne pas le même revenu disponible, à un euro près.

* Une réforme des salaires (`population.salaires`) : le Smic relevé relève le salaire du
  cas type pris entre l'ancien et le nouveau Smic (la loi du premier jour), et au-dessus la
  diffusion que le scénario déclare ; l'arbre porte le nouveau Smic ; les années d'avant
  gardent leurs salaires. Le point d'indice ne touche pas ces cas types : des salariés du
  privé (dit).
* Une indexation des pensions multiplie la pension, comme `engine.compute`.
* La TVA et les accises (`consommation`) : la dépense du décile de niveau de vie du cas
  type (sa cellule), au prorata de ses unités de consommation sur la moyenne du décile
  (celle des cellules), à volumes constants, la taxe répercutée en entier.

LES NIVEAUX viennent de la population de D-553 (`niveaux`) : les salaires en multiples du
Smic de 2024, portés au Smic de 2026 ; les pensions, les allocations chômage et les loyers
en euros de 2024, tels quels en 2026 (une approximation, dite).

    PYTHONPATH=src python -m impots.cas_types            # le tableau (un quart d'heure)
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
FICHIER = Path(__file__).resolve().parent / "jumeau" / "parametres" / "cas_types.json"
POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"
COMMANDE = "PYTHONPATH=src .venv/bin/python -m impots.cas_types"
ANNEE = 2026
ANNEE_POPULATION = 2024

FOYERS = ("seul", "couple")
ENFANTS = (0, 1, 2, 3)
#: Les situations d'activité : celles qu'OpenFisca chiffre, et l'indépendant, que le moteur
#: des ménages ne sait pas décrire (la cellule, D-630).
ACTIVITES = ("smic", "median", "eleve", "chomeur", "retraite", "independant")
ACTIVITES_OPENFISCA = ("smic", "median", "eleve", "chomeur", "retraite")
LOGEMENTS = ("locataire", "proprietaire")
#: La classe d'âge et l'âge du cas type ; un retraité a 70 ans, un actif n'a pas 62 ans.
AGES = {"moins_30": 27, "30_49": 40, "50_61": 55, "62_plus": 70}
AGES_ACTIFS = ("moins_30", "30_49", "50_61")
#: L'âge des enfants selon celui des parents (les aînés d'abord).
AGES_ENFANTS = {27: (5, 3, 1), 40: (12, 9, 6), 55: (17, 15, 13)}
LIBELLES = {
    "seul": "Seul", "couple": "En couple (les deux adultes dans la même situation)",
    "smic": "Salarié au Smic, à temps complet", "median": "Salarié au salaire médian",
    "eleve": "Salaire élevé (cadre, le neuvième décile)", "chomeur": "Au chômage, indemnisé",
    "retraite": "Retraité", "independant": "Indépendant",
    "locataire": "Locataire du parc privé", "proprietaire": "Propriétaire",
    "moins_30": "Moins de 30 ans", "30_49": "30 à 49 ans", "50_61": "50 à 61 ans",
    "62_plus": "62 ans ou plus",
}
#: Les prestations que le registre du moteur sépare, comptées ensemble (« prestations »).
PRESTATIONS = ("af", "aeeh", "ppa", "rsa", "ass", "aide_logement", "reduction_loyer_solidarite",
               "aah", "mva", "aspa", "asi", "aefa", "cf", "asf", "ars", "paje", "ria",
               "allocation_enfant", "garantie_autonomie", "garantie_jeunes")
PRELEVEMENTS_TRAVAIL = ("cotisations_salariales", "csg_deductible", "csg_imposable", "crds")
CRDS_PRESTATIONS = ("crds_pfam", "crds_logement", "crds_mini")


class CasTypesError(ValueError):
    """Un cas type ou un tableau que la commande refuse."""


@dataclass(frozen=True)
class Cas:
    foyer: str
    enfants: int
    activite: str
    logement: str
    age: str

    @property
    def cle(self) -> str:
        return cle(self.foyer, self.enfants, self.activite, self.logement, self.age)


def cle(foyer: str, enfants: int, activite: str, logement: str, age: str) -> str:
    return f"{foyer}-{int(enfants)}-{activite}-{logement}-{age}"


def grille(activites: Sequence[str] = ACTIVITES_OPENFISCA) -> tuple[Cas, ...]:
    """Les cas types : un retraité a 62 ans ou plus et aucun enfant à charge ; un actif
    a moins de 62 ans."""
    out = []
    for f in FOYERS:
        for a in activites:
            ages = ("62_plus",) if a == "retraite" else AGES_ACTIFS
            enfants = (0,) if a == "retraite" else ENFANTS
            for e in enfants:
                for lg in LOGEMENTS:
                    for g in ages:
                        out.append(Cas(f, e, a, lg, g))
    return tuple(out)


def choisir(foyer: str, enfants: int, activite: str, logement: str, age: str) -> str:
    """La clé du cas type de la grille pour ce que le lecteur dit (la même règle que la
    page) : un retraité a 62 ans ou plus et ses enfants ne sont plus à charge ; un actif de
    62 ans ou plus est pris à 50-61 ans."""
    if activite == "retraite":
        return cle(foyer, 0, activite, logement, "62_plus")
    return cle(foyer, enfants, activite, logement, "50_61" if age == "62_plus" else age)


# --------------------------------------------------------------------------- niveaux
def _quantile(x: np.ndarray, w: np.ndarray, p: float) -> float:
    o = np.argsort(x)
    c = np.cumsum(w[o]) / w.sum()
    return float(x[o][np.searchsorted(c, p)])


def niveaux(chemin: Path = POPULATION) -> dict[str, Any]:
    """Les niveaux des cas types, lus dans la population (D-553) ; avec l'empreinte."""
    import polars as pl

    from impots.population.salaires import smic_horaire

    df = pl.read_parquet(chemin)
    empreinte = hashlib.sha256(chemin.read_bytes()).hexdigest()
    tp = df.filter(pl.col("is_salarie") & (pl.col("quotite_travail") >= 0.99)
                   & (pl.col("mois_travailles") >= 12) & (pl.col("salaire_brut_annuel") > 0))
    sb, w = tp["salaire_brut_annuel"].to_numpy(), tp["weight"].to_numpy()
    smic24 = smic_horaire(ANNEE_POPULATION) * 151.67 * 12
    smic26 = smic_horaire(ANNEE) * 151.67 * 12
    r = df.filter((pl.col("pension_annuelle") > 0) & (pl.col("age") >= 65))
    u = df.filter((pl.col("chomage_annuel") > 0) & (pl.col("statut_activite") == "unemployed"))
    lo = df.filter((pl.col("loyer_mensuel") > 0) & (pl.col("role_menage") ==
                                                    "personne_de_reference")
                   & pl.col("statut_occupation").is_in(["locataire_vide", "locataire_meuble"]))
    # Le loyer selon la taille du ménage : la médiane des locataires du privé, par nombre de
    # personnes (une, deux, trois, quatre, cinq ou plus).
    taille = df.group_by("household_id").agg(pl.len().alias("n"))
    lo = lo.join(taille, on="household_id")
    par_taille = {}
    for n in range(1, 6):
        x = lo.filter(pl.col("n") == n if n < 5 else pl.col("n") >= 5)
        par_taille[n] = round(_quantile(x["loyer_mensuel"].to_numpy().astype(float),
                                        x["weight"].to_numpy().astype(float), 0.5))
    return {
        "source": f"population de D-553 ({chemin.name}, sha256 {empreinte[:16]}…), "
                  f"pondérée",
        "smic_annuel_brut_2024": round(smic24, 2), "smic_annuel_brut_2026": round(smic26, 2),
        "salaire_median_brut_2024": round(_quantile(sb, w, 0.5)),
        "salaire_d9_brut_2024": round(_quantile(sb, w, 0.9)),
        "salaires_definition": "salariés à temps complet toute l'année (quotité 1, douze mois "
                               "travaillés), salaire brut annuel",
        "pension_mediane_2024": round(_quantile(r["pension_annuelle"].to_numpy(),
                                                r["weight"].to_numpy(), 0.5)),
        "pension_definition": "pension de retraite des 65 ans ou plus qui en ont une",
        "chomage_median_2024": round(_quantile(u["chomage_annuel"].to_numpy(),
                                               u["weight"].to_numpy(), 0.5)),
        "chomage_definition": "allocation chômage annuelle brute des chômeurs BIT qui en ont "
                              "une",
        "loyer_median_par_taille_2024": par_taille,
        "loyer_definition": "loyer mensuel des personnes de référence locataires du parc "
                            "privé (vide ou meublé), médiane par nombre de personnes du "
                            "ménage (5 : cinq ou plus)",
    }


# --------------------------------------------------------------------------- ménages
def menage(cas: Cas, n: Mapping[str, Any]) -> Any:
    """Le `HouseholdInput` du cas type."""
    from impots.api.schemas import Adult, Child, HouseholdInput, Logement

    age = AGES[cas.age]
    naissance = ANNEE - age
    smic = float(n["smic_annuel_brut_2026"]) / float(n["smic_annuel_brut_2024"])
    revenus: dict[str, float] = {"salaire_brut_annuel": 0.0}
    if cas.activite == "smic":
        revenus["salaire_brut_annuel"] = float(n["smic_annuel_brut_2026"])
    elif cas.activite == "median":
        revenus["salaire_brut_annuel"] = float(n["salaire_median_brut_2024"]) * smic
    elif cas.activite == "eleve":
        revenus["salaire_brut_annuel"] = float(n["salaire_d9_brut_2024"]) * smic
    elif cas.activite == "chomeur":
        revenus["chomage_brut_annuel"] = float(n["chomage_median_2024"])
    elif cas.activite == "retraite":
        revenus["pension_annuelle"] = float(n["pension_mediane_2024"])
    else:
        raise CasTypesError(f"« {cas.activite} » : le moteur des ménages ne le décrit pas")
    adultes = [Adult(annee_naissance=naissance, **revenus)]
    if cas.foyer == "couple":
        adultes.append(Adult(annee_naissance=naissance, **revenus))
    enfants = [Child(annee_naissance=ANNEE - a) for a in AGES_ENFANTS.get(age, ())[
        :cas.enfants]]
    personnes = len(adultes) + len(enfants)
    if cas.logement == "locataire":
        loyers = n["loyer_median_par_taille_2024"]
        loyer = float(loyers.get(min(personnes, 5), loyers.get(str(min(personnes, 5)))))
        logement = Logement(statut="locataire_vide", loyer_mensuel=loyer, zone_apl=2)
    else:
        logement = Logement(statut="proprietaire", loyer_mensuel=0.0, zone_apl=2)
    return HouseholdInput(adults=adultes, children=enfants,
                          couple_marie_ou_pacse=cas.foyer == "couple", logement=logement)


def unites_consommation(cas: Cas) -> float:
    """L'échelle de l'OCDE modifiée (`population.aggregate.consumption_units`)."""
    age = AGES[cas.age]
    enfants = AGES_ENFANTS.get(age, ())[:cas.enfants]
    adultes = 2 if cas.foyer == "couple" else 1
    grands = sum(1 for a in enfants if a >= 14)
    return 1.0 + 0.5 * (adultes - 1 + grands) + 0.3 * (len(enfants) - grands)


# --------------------------------------------------------------------------- simulation
_ENTITES = ("individus", "foyers_fiscaux", "familles", "menages")


def fusionner(situations: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], list[int]]:
    """Une situation qui porte tous les ménages, chaque identifiant préfixé par son rang ;
    et le nombre de personnes de chacun (dans l'ordre)."""
    out: dict[str, dict[str, Any]] = {e: {} for e in _ENTITES}
    personnes = []
    for k, s in enumerate(situations):
        p = f"c{k}_"
        if any(len(s[e]) != 1 for e in _ENTITES[1:]):
            raise CasTypesError(f"cas {k} : plus d'un foyer, d'une famille ou d'un ménage")
        for nom, v in s["individus"].items():
            out["individus"][p + nom] = v
        personnes.append(len(s["individus"]))
        for e in _ENTITES[1:]:
            for nom, v in s[e].items():
                out[e][p + nom] = {r: ([p + x for x in val] if isinstance(val, list) else val)
                                   for r, val in v.items()}
    return out, personnes


def extraire(simulation: Any, annee: int, personnes: Sequence[int]) -> list[dict[str, float]]:
    """Chaque ligne du registre (tier « full »), par ménage, signée comme l'API."""
    from impots.engine.outputs import rows_for

    periode = str(annee)
    variables = simulation.tax_benefit_system.variables
    debuts = np.concatenate([[0], np.cumsum(personnes)[:-1]]).astype(int)
    n = len(personnes)
    out: list[dict[str, float]] = [{} for _ in range(n)]
    for row in rows_for("full"):
        if row.projet and row.variable not in variables:
            vals = np.zeros(n)
        else:
            arr = sum((simulation.calculate_add(nom, periode) if row.period == "month"
                       else simulation.calculate(nom, periode))
                      for nom in (row.variable, *row.extra))
            arr = np.asarray(arr, dtype=float)
            vals = np.add.reduceat(arr, debuts) if row.entity == "individu" else arr
            if len(vals) != n:
                raise CasTypesError(f"{row.key} : {len(vals)} valeurs pour {n} ménages")
        for k in range(n):
            v = -float(vals[k]) if row.negate else float(vals[k])
            out[k][row.key] = round(v, 2) + 0.0
    return out


def _simulation(systeme: Any, situation: Mapping[str, Any], annee: int) -> Any:
    """Comme `engine.compute._build` au tier « full » : le RFR de N-2, puis l'aide au
    logement mois par mois (chaque cas type a un logement)."""
    from openfisca_core.simulation_builder import SimulationBuilder

    from impots.engine import situations

    simulation = SimulationBuilder().build_from_entities(systeme, dict(situation))
    situations.pin_rfr_n_2(simulation, annee)
    situations.pin_benefit_history(simulation, annee)
    return simulation


def resume(lignes: Mapping[str, float]) -> dict[str, float]:
    """Ce que la page montre d'un ménage : le revenu disponible et ses grandes parts."""
    return {
        "revenu_disponible": lignes["revenu_disponible"],
        "salaire_net": lignes["salaire_net"],
        "pensions_chomage": lignes["retraite_imposable"] + lignes["chomage_brut"],
        "impot_revenu": lignes["ir"],
        "prelevements_travail": sum(lignes[k] for k in PRELEVEMENTS_TRAVAIL),
        "prestations": sum(lignes.get(k) or 0.0 for k in PRESTATIONS)
        - sum(lignes.get(k) or 0.0 for k in CRDS_PRESTATIONS),
        "salaire_brut": lignes["salaire_brut"],
    }


@dataclass
class Chiffreur:
    """Les ménages de la grille, construits une fois ; une réforme les chiffre ensemble."""

    cas: tuple[Cas, ...]
    niveaux: Mapping[str, Any]
    annee: int = ANNEE

    def __post_init__(self) -> None:
        from impots.engine import situations
        from impots.engine.system import baseline

        self.menages = [menage(c, self.niveaux) for c in self.cas]
        self.situations = [situations.build_situation(h, self.annee, True)
                           for h in self.menages]
        self.situation, self.personnes = fusionner(self.situations)
        sim = _simulation(baseline(), self.situation, self.annee)
        self.base = extraire(sim, self.annee, self.personnes)

    def verifier(self, rangs: Iterable[int], reforme: Any = None,
                 lignes: Sequence[Mapping[str, float]] | None = None) -> None:
        """Le ménage pris seul (`engine.compute`) redonne le revenu disponible, à 1 €."""
        from impots.engine.compute import compute

        for k in rangs:
            r = compute(self.menages[k], self.annee, reform=reforme, tier="full")
            seul = (r.reform or r.baseline)["revenu_disponible"]
            ici = (lignes or self.base)[k]["revenu_disponible"]
            if abs(seul - ici) > 1.0:
                raise CasTypesError(f"{self.cas[k].cle} : {ici:.2f} dans la simulation "
                                    f"commune, {seul:.2f} seul")

    def chiffrer(self, reforme: Any) -> list[dict[str, float]]:
        """Les lignes de chaque ménage sous `reforme` (une `ReformSpec`)."""
        from impots import consommation
        from impots.engine.boutons_programmes import facteur_pensions
        from impots.engine.system import baseline, reformed_for
        from impots.population import salaires

        arbre = consommation.sans_consommation(reforme)
        situation = self.situation
        if salaires.touche(arbre):
            arbre_seul = salaires.sans_salaires(arbre)
            systeme = baseline() if arbre_seul.is_empty() else reformed_for(arbre_seul,
                                                                            self.annee)
            if arbre.smic_revalorisation is not None:
                systeme = salaires.reforme_smic(systeme, arbre.smic_revalorisation,
                                                self.annee)
                situation = self._smic(arbre)
        elif arbre.is_empty():
            systeme = baseline()
        else:
            systeme = reformed_for(arbre, self.annee)
        facteur = facteur_pensions(arbre, self.annee)
        if facteur != 1.0:
            situation = self._pensions(situation, facteur)
        sim = _simulation(systeme, situation, self.annee)
        return extraire(sim, self.annee, self.personnes)

    def _smic(self, spec: Any) -> dict[str, Any]:
        """La situation dont le salaire de l'année est relevé comme `salaires.appliquer`."""
        from impots.population import salaires

        coef = float(spec.smic_revalorisation)
        avant = salaires.smic_horaire(self.annee) * 151.67 * 12
        sit = json.loads(json.dumps(self.situation))
        for ind in sit["individus"].values():
            sb = ind.get("salaire_de_base")
            if not sb:
                continue
            mois = [f"{self.annee}-{m:02d}" for m in range(1, 13)]
            annuel = sum(float(sb.get(m, 0.0)) for m in mois)
            if annuel <= 0:
                continue
            ratio = annuel / avant
            facteur = coef if ratio < 1.0 else (coef / ratio if ratio < coef else 1.0)
            if spec.smic_diffusion_profil is not None and ratio >= 1.0:
                echelle = 1.0 if spec.smic_diffusion_echelle is None else float(
                    spec.smic_diffusion_echelle)
                e = float(salaires.diffusion(np.array([ratio]), spec.smic_diffusion_profil,
                                             echelle)[0])
                facteur = max(facteur, 1.0 + e * (coef - 1.0))
            for m in mois:
                if m in sb:
                    sb[m] = float(sb[m]) * facteur
        return sit

    def _pensions(self, situation: Mapping[str, Any], facteur: float) -> dict[str, Any]:
        sit = json.loads(json.dumps(situation))
        for ind in sit["individus"].values():
            for nom in ("retraite_brute", "pensions_retraite", "retraite_imposable"):
                if nom in ind:
                    ind[nom] = {p: float(v) * facteur for p, v in ind[nom].items()}
        return sit


# --------------------------------------------------------------------------- consommation
def taxes_consommation(cas: Sequence[Cas], deciles: Sequence[int], uc_moyenne: Sequence[float],
                       reforme: Any = None) -> list[tuple[float, float]]:
    """(TVA et accises de référence, sous la réforme) de chaque cas type, en euros de 2026."""
    from impots import consommation, hypotheses

    prix = dict(hypotheses.jeu("plf2027").prix)
    facteurs = consommation.croissance(ANNEE, prix)
    tf = consommation.tf106()
    conso = {code: np.array([v[d - 1] * unites_consommation(c) / uc_moyenne[d - 1]
                             for c, d in zip(cas, deciles, strict=True)]) * facteurs[code]
             for code, v in tf.items()}
    droit = consommation.Fiscalite.droit(ANNEE, annee_prix=ANNEE, prix_au_dela=prix)
    base = consommation.taxes(conso, droit)
    b = base["tva"] + base["accises"]
    if reforme is None or not consommation.touche(reforme):
        return [(float(x), float(x)) for x in b]
    r = consommation.taxes(conso, droit.reformee(reforme), reference=droit)
    a = r["tva"] + r["accises"]
    return [(float(x), float(y)) for x, y in zip(b, a, strict=True)]


# --------------------------------------------------------------------------- cellules
def cellule(cas: Cas, revenu_disponible: float, cellules: Any, deflateur: float
            ) -> tuple[int, str]:
    """(décile 1-10, type) de la cellule du jumeau la plus proche : le type de ménage, et
    le décile dont le cas type passe le seuil, les seuils à mi-chemin (en log) des niveaux
    de vie moyens des déciles des cellules (euros de 2024 ; le cas type y est ramené par
    `deflateur`)."""
    from impots.jumeau.cellules import N_DECILES, TYPES

    nv = np.asarray(cellules["revenu_disponible"], float)
    uc = np.asarray(cellules["uc"], float)
    k = len(TYPES)
    moy = np.array([(nv[d * k:(d + 1) * k]).sum() / uc[d * k:(d + 1) * k].sum()
                    for d in range(N_DECILES)])
    seuils = np.exp(0.5 * (np.log(moy[1:]) + np.log(moy[:-1])))
    x = revenu_disponible / unites_consommation(cas) / deflateur
    decile = int(np.searchsorted(seuils, x)) + 1
    if cas.foyer == "seul":
        type_ = "seul" if cas.enfants == 0 else "monoparentale"
    else:
        type_ = "couple_sans_enfant" if cas.enfants == 0 else "couple_avec_enfants"
    return decile, type_


# --------------------------------------------------------------------------- le tableau
def scenarios_bibliotheque() -> list[str]:
    """Les scénarios de la bibliothèque de la page (`site_jumeau.candidats`), sans lire de
    rapport : ceux qu'un rapport d'étude commité porte."""
    from impots import site_jumeau

    return list(site_jumeau.candidats())


def construire(cles: Sequence[str] | None = None, verifier: int = 3,
               dossier: Path | None = None) -> dict[str, Any]:
    """Le tableau des cas types : chaque cas au droit de 2026, et ses écarts sous chaque
    scénario de `cles` (lus dans `dossier`, le dossier des scénarios par défaut ; celui
    d'une proposition du lecteur, D-660)."""
    from impots import scenarios
    from impots.jumeau.cellules import N_DECILES, TYPES
    from impots.jumeau.navigateur import lire

    t0 = time.time()
    n = niveaux()
    cas = grille()
    ch = Chiffreur(cas, n)
    ch.verifier(range(0, len(cas), max(1, len(cas) // verifier)))
    cel = lire()["cellules"]["valeurs"]
    deflateur = float(n["smic_annuel_brut_2026"]) / float(n["smic_annuel_brut_2024"])
    cellules_cas = [cellule(c, b["revenu_disponible"], cel, deflateur)
                    for c, b in zip(cas, ch.base, strict=True)]
    k = len(TYPES)
    uc_moy = [sum(cel["uc"][d * k:(d + 1) * k]) / sum(cel["menages"][d * k:(d + 1) * k])
              for d in range(N_DECILES)]
    deciles = [d for d, _ in cellules_cas]
    tc_base = taxes_consommation(cas, deciles, uc_moy)
    out_cas = {}
    for c, b, (d, t), (tb, _) in zip(cas, ch.base, cellules_cas, tc_base, strict=True):
        r = resume(b)
        r["taxes_consommation"] = round(tb, 2)
        out_cas[c.cle] = {"foyer": c.foyer, "enfants": c.enfants, "activite": c.activite,
                          "logement": c.logement, "age": c.age, "age_ans": AGES[c.age],
                          "uc": unites_consommation(c), "decile": d, "type": t,
                          "reference": r}
    # L'indépendant : la cellule du salarié médian de même foyer, enfants, logement, âge.
    for c in grille(("independant",)):
        jumeau = out_cas[cle(c.foyer, c.enfants, "median", c.logement, c.age)]
        out_cas[c.cle] = {"foyer": c.foyer, "enfants": c.enfants, "activite": c.activite,
                          "logement": c.logement, "age": c.age, "age_ans": AGES[c.age],
                          "uc": unites_consommation(c), "decile": jumeau["decile"],
                          "type": jumeau["type"], "reference": None,
                          "cellule_de": "le salarié médian de même foyer, mêmes enfants, "
                                        "même logement et même âge (approximation)"}
    out_mesures: dict[str, Any] = {}
    verifie = None
    for sc in (cles if cles is not None else scenarios_bibliotheque()):
        s = scenarios.load(sc, dossier)
        if s.reform is None or s.reform.is_empty():
            out_mesures[sc] = {"annee": s.year, "vide": True}
            continue
        lignes = ch.chiffrer(s.reform)
        if not verifie and not _salaires_ou_consommation(s.reform):
            ch.verifier(range(0, len(cas), max(1, len(cas) // verifier)), s.reform, lignes)
            verifie = sc
        tc = taxes_consommation(cas, deciles, uc_moy, s.reform)
        ecarts = {}
        for c, b, a, (tb, ta) in zip(cas, ch.base, lignes, tc, strict=True):
            rb, ra = resume(b), resume(a)
            e = {x: round(ra[x] - rb[x], 2) for x in rb}
            e["taxes_consommation"] = round(ta - tb, 2)
            # Compact : seuls les écarts non nuls ; un cas absent n'a rien de changé.
            e = {x: v for x, v in e.items() if abs(v) >= 0.005}
            if e:
                ecarts[c.cle] = e
        out_mesures[sc] = {"annee": s.year, "ecarts": ecarts,
                           "note": "un cas type absent d'« ecarts », ou une ligne absente, "
                                   "vaut zéro"}
        print(f"  {sc} ({time.time() - t0:.0f} s)", file=sys.stderr, flush=True)
    return {
        "version": 1, "annee": ANNEE, "commit": _commit(), "commande": COMMANDE,
        "decisions": "D-630 à D-634", "niveaux": n,
        "grille": {"foyers": list(FOYERS), "enfants": list(ENFANTS),
                   "activites": list(ACTIVITES), "logements": list(LOGEMENTS),
                   "ages": AGES, "libelles": LIBELLES},
        "verification": {"reference": "engine.compute, ménage seul, à 1 €",
                         "reforme": verifie},
        "cas": out_cas, "mesures": out_mesures,
        "duree_s": round(time.time() - t0),
    }


def _salaires_ou_consommation(spec: Any) -> bool:
    from impots import consommation
    from impots.population import salaires

    return salaires.touche(spec) or consommation.touche(spec)


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True,
                              capture_output=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "inconnu"


def ecrire(tableau: Mapping[str, Any], chemin: Path = FICHIER) -> Path:
    chemin.write_text(json.dumps(tableau, ensure_ascii=False, separators=(",", ":"),
                                 sort_keys=False) + "\n", encoding="utf-8")
    return chemin


if __name__ == "__main__":
    cles_demandees = sys.argv[1:] or None
    print(ecrire(construire(cles_demandees)))
