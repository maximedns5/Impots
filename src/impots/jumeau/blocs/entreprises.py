"""Les entreprises du jumeau (but 23, lot 2, D-407) : leurs valeurs, leur population, leurs
θ, et le bloc `chocs_entreprises`, qui inscrit les prélèvements par impôt.

CE QUE LE LOT 2 AJOUTE. Cinq blocs structurels, dans cet ordre (`ordre_lot2`) :

* `chocs_entreprises` (ici) : les variations de prélèvements de chaque mesure, par impôt ;
* `naissances`, `fermetures`, `productivite` (`demographie.py`) : le taux d'entrée, le
  hasard de sortie des installées selon leur marge, et la valeur ajoutée de la
  démographie sur le PIB potentiel ;
* `investissement` (`investissement.py`) : l'équation d'investissement de Mésange, par le
  coût d'usage du capital ;
* `implantation` (`implantation.py`) : le capital des multinationales selon le taux
  effectif moyen (Devereux et Lockwood 2006).

Chaque valeur est dans `jumeau/parametres/entreprises.yaml`, avec sa source ; les blocs la
lisent à leur construction (`charger`), jamais dans un pas.

LE BLOC `chocs_entreprises`. ÉQUATION, pour la mesure m, l'année t et le signal s
(`champs.SIGNAUX_ENTREPRISES`) :

    P_{s,m,t} = Σ_{i ∈ s} ΔP_{i,m,t}        Md€, recettes positives (une hausse > 0)

ΔP_{i,m,t} est le choc statique de l'impôt i que la mesure porte (`Mesure.entreprises`,
{année: {impôt: Md€ ou {taille: Md€}}}). Une mesure qui porte des prélèvements agrégés
(`Mesure.prelevements`, le signal du lot 1) sans les ventiler par impôt est REFUSÉE avant
le premier pas : les blocs du lot 2 lisent chaque impôt à part, et un agrégat ne se
ventile pas sans hypothèse.

LA POPULATION. Les cellules secteur × taille de `entreprises.cells` (millésime 2023 :
nombre de sociétés, valeur ajoutée, résultat courant avant impôts), portées telles
quelles comme la structure du départ ; leurs montants sont lus en parts, rapportées à la
valeur ajoutée des sociétés du scénario, s_VA Y_t.

LE PIB DU SCÉNARIO. Les blocs du lot 2 rapportent tout au PIB du scénario,
Y_t = Y_départ Π_{j ≤ t} (1 + g_j), g la croissance nominale des entrées : il est le même
dans la référence et la variante, de sorte que la clé « » (la référence) s'y écrit à
l'identique et que Δ ne lit que les mesures.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from impots.jumeau import thetas
from impots.jumeau.blocs.valeurs_entreprises import (
    FERMETURES_ROW,
    IDEES_ROW,
    IMPLANTATION_ROW,
    INVESTISSEMENT_ROW,
    MONTEE_ROW,
    SURVIE_ROW,
    TAILLE_ROW,
    EntreprisesError,
    Parametres,
    charger,
)
from impots.jumeau.champs import RECETTES, SIGNAUX_ENTREPRISES
from impots.jumeau.mesures import HYPOTHESE, Mesure
from impots.jumeau.pas import Contexte, Entrees
from impots.predictif.theta import CREATIONS_ROW

CELLULES_2023 = Path(__file__).resolve().parents[4] / "data" / "processed" / \
    "firm_cells_2023.json"
TAILLES = ("micro", "PME", "ETI", "GE")
#: L'impôt de la mesure → son signal.
INSTRUMENTS = {i: s for s, (_, _, ins) in SIGNAUX_ENTREPRISES.items() for i in ins}
#: La catégorie du compte des APU où tombe le choc statique de chaque impôt (t. 3.201).
CATEGORIE_APU = {"impot_societes": "apu_r_d5", "contribution_sociale_is": "apu_r_d5",
                 "cebge": "apu_r_d5", "cvae": "apu_r_d2", "c3s": "apu_r_d2",
                 "cotisations_employeurs": "apu_r_d61", "pfu": "apu_r_d5",
                 "prelevements_sociaux_capital": "apu_r_d5"}


def lire_theta(ctx: Contexte, cle: str) -> np.ndarray:
    return thetas.lire(ctx.theta, cle, ctx.n)


# --------------------------------------------------------------------------- #
# la population
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Population:
    """Les cellules secteur × taille, en tableaux alignés."""

    secteur: tuple[str, ...]
    taille: tuple[str, ...]
    societes: np.ndarray
    valeur_ajoutee: np.ndarray
    resultat: np.ndarray
    millesime: str

    def __post_init__(self) -> None:
        if not len(self.secteur) == len(self.taille) == len(self.societes):
            raise EntreprisesError("cellules de longueurs différentes")
        inconnues = sorted(set(self.taille) - set(TAILLES))
        if inconnues:
            raise EntreprisesError(f"tailles inconnues {inconnues}")
        if np.any(self.societes <= 0) or np.any(self.valeur_ajoutee <= 0):
            raise EntreprisesError("une cellule sans société ou sans valeur ajoutée")

    @property
    def stock(self) -> float:
        return float(self.societes.sum())

    def cle(self, nom: str) -> np.ndarray:
        """L'assiette d'un impôt par cellule, positive (un résultat négatif ne paie rien)."""
        if nom == "resultat":
            base = np.maximum(self.resultat, 0.0)
        elif nom == "valeur_ajoutee":
            base = self.valeur_ajoutee
        elif nom == "va_moins_resultat":
            base = np.maximum(self.valeur_ajoutee - np.maximum(self.resultat, 0.0), 0.0)
        else:
            raise EntreprisesError(f"clé de répartition « {nom} » inconnue")
        if base.sum() <= 0:
            raise EntreprisesError(f"clé « {nom} » nulle sur toute la population")
        return base

    def part_va(self) -> np.ndarray:
        return self.valeur_ajoutee / self.valeur_ajoutee.sum()


def population(cellules: Sequence[Mapping[str, Any]], millesime: str) -> Population:
    return Population(
        secteur=tuple(str(c["naf_section"]) for c in cellules),
        taille=tuple(str(c["taille"]) for c in cellules),
        societes=np.array([float(c["n_firms"]) for c in cellules]),
        valeur_ajoutee=np.array([float(c["value_added_total"]) for c in cellules]) / 1e9,
        resultat=np.array([float(c["result_total"]) for c in cellules]) / 1e9,
        millesime=millesime)


def population_depuis(chemin: Path | None = None) -> Population:
    """La table des cellules (`entreprises.cells.write_cell_table`) ; par défaut celle de
    2023, préparée par `make data`. Une table synthétique le dit dans son millésime."""
    chemin = chemin or CELLULES_2023
    if not chemin.exists():
        raise EntreprisesError(f"{chemin} absent : `make data` prépare les cellules")
    d = json.loads(chemin.read_text(encoding="utf-8"))
    millesime = str(d.get("vintage", "?"))
    if d.get("cells_are_synthetic") or "_comment" in d:
        millesime += " (synthétique)"
    return population(d["cells"], millesime)


# --------------------------------------------------------------------------- #
# ce que les blocs du lot 2 partagent
# --------------------------------------------------------------------------- #
def pib_scenario(ctx: Contexte, j: int) -> float:
    """Y_j, le PIB du scénario : le départ, à la croissance nominale des entrées."""
    y = float(ctx.depart["pib"][0])
    for i in range(j + 1):
        y *= 1.0 + ctx.entrees.nominale(i)
    return y


def taux_prelevements(ctx: Contexte) -> float:
    """ρ, les recettes hors intérêts du départ sur son PIB (comme le canal du lot 1)."""
    return sum(float(ctx.depart[n][0]) for n in RECETTES) / float(ctx.depart["pib"][0])


def part_depart(ctx: Contexte, nom: str) -> float:
    return float(ctx.depart[nom][0]) / float(ctx.depart["pib"][0])


def part_capital(ctx: Contexte) -> float:
    """s_K, la part du capital dans le revenu du départ : EBE et revenu mixte sur eux plus
    les rémunérations (t. 1.105). Le revenu mixte porte aussi du travail : dit."""
    ebe, d1 = float(ctx.depart["ebe_revenu_mixte"][0]), float(ctx.depart["remunerations"][0])
    return ebe / (ebe + d1)


def historique(ctx: Contexte, nom: str) -> list[dict[str, np.ndarray]]:
    """Un champ lu, par mesure, des années 0 à k (déclaré dans `lit`)."""
    return ([ctx.passe(j).par_mesure(nom) for j in range(ctx.k)]
            + [ctx.par_mesure(nom)])


def chemins(ctx: Contexte, noms: Sequence[str]) -> dict[str, list[np.ndarray]]:
    """Par mesure, la somme des champs `noms` (déclarés dans `lit`), années 0 à k."""
    hist = [historique(ctx, nom) for nom in noms]
    mesures = sorted({m for h in hist for an in h for m in an})
    zero = np.zeros(ctx.n)
    return {m: [sum((h[j].get(m, zero) for h in hist), zero) for j in range(ctx.k + 1)]
            for m in mesures}


def ventiler(mesure: Any, annee: int, signal_: str) -> dict[str, float] | None:
    """La part par taille d'un signal, si la mesure la donne pour chacun de ses impôts ;
    None si elle ne ventile pas (la clé de répartition s'applique)."""
    chocs = (mesure.entreprises or {}).get(annee, {})
    parts: dict[str, float] = {}
    for instrument, valeur in chocs.items():
        if INSTRUMENTS[instrument] != signal_:
            continue
        if not isinstance(valeur, Mapping):
            return None
        for taille, v in valeur.items():
            parts[taille] = parts.get(taille, 0.0) + float(v)
    return parts or None


# --------------------------------------------------------------------------- #
# le bloc `chocs_entreprises`
# --------------------------------------------------------------------------- #
class ChocsEntreprises:
    nom = "chocs_entreprises"
    lit: tuple[str, ...] = ()
    ecrit = tuple(SIGNAUX_ENTREPRISES)
    thetas: tuple[str, ...] = ()

    def preparer(self, entrees: Entrees, mesures: Sequence[Any]) -> None:
        for m in mesures:
            if m.prelevements and not m.entreprises:
                raise EntreprisesError(
                    f"mesure « {m.identifiant} » : des prélèvements agrégés (le signal du "
                    f"canal du lot 1) sans leur ventilation par impôt ; les blocs du lot 2 "
                    f"lisent chaque impôt et ne devinent pas la ventilation")
            if m.entreprises and m.report:
                raise EntreprisesError(f"mesure « {m.identifiant} » : une première année "
                                       f"reportée n'est pas lue par le lot 2")
            for annee, chocs in (m.entreprises or {}).items():
                for instrument, valeur in chocs.items():
                    if instrument not in INSTRUMENTS:
                        raise EntreprisesError(
                            f"mesure « {m.identifiant} », {annee} : impôt « {instrument} » "
                            f"inconnu ({sorted(INSTRUMENTS)})")
                    if isinstance(valeur, Mapping):
                        inconnues = sorted(set(valeur) - set(TAILLES))
                        if inconnues:
                            raise EntreprisesError(
                                f"mesure « {m.identifiant} », {annee}, {instrument} : "
                                f"tailles inconnues {inconnues}")

    def contribue(self, ctx: Contexte) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {s: {} for s in self.ecrit}
        for m in ctx.mesures:
            for instrument, valeur in (m.entreprises or {}).get(ctx.annee, {}).items():
                total = (sum(float(v) for v in valeur.values())
                         if isinstance(valeur, Mapping) else float(valeur))
                parts = out[INSTRUMENTS[instrument]]
                parts[m.identifiant] = parts.get(m.identifiant, 0.0) + total
        return out


def mesure_entreprises(identifiant: str, libelle: str,
                       chocs: Mapping[int, Mapping[str, Any]], *,
                       auteur: str = "loi hypothétique") -> Mesure:
    """Une loi hypothétique sur les impôts des entreprises et du capital, Md€, RECETTES
    POSITIVES par impôt (une hausse > 0), éventuellement par taille : son choc statique
    sur le compte des APU (la catégorie de chaque impôt, au signe du moteur, un coût > 0)
    et ses signaux pour le lot 2. Chaque nombre qu'elle touche est une hypothèse."""
    if not chocs:
        raise EntreprisesError(f"loi « {identifiant} » sans choc")
    apu: dict[int, dict[str, float]] = {}
    for annee, par_impot in chocs.items():
        for instrument, valeur in par_impot.items():
            if instrument not in CATEGORIE_APU:
                raise EntreprisesError(f"impôt « {instrument} » inconnu")
            total = (sum(float(v) for v in valeur.values())
                     if isinstance(valeur, Mapping) else float(valeur))
            categorie = CATEGORIE_APU[instrument]
            apu.setdefault(annee, {})
            apu[annee][categorie] = apu[annee].get(categorie, 0.0) - total
    return Mesure(identifiant=identifiant, libelle=libelle, auteur=auteur,
                  origine=HYPOTHESE, annees=tuple(sorted(chocs)), chocs=apu,
                  entreprises={a: dict(c) for a, c in chocs.items()})


def ordre_lot2(depart: Any, population_: Population, *, parametres: Parametres | None = None,
               investissement: bool = True, implantation: bool = True) -> list[Any]:
    """Le cadre (`tendance`, `mesures`) et les blocs du lot 2, dans l'ordre de leurs
    lectures : le mode structurel des entreprises, sans Mésange (`canaux`)."""
    from impots.jumeau.blocs.demographie import Fermetures, Naissances, Productivite
    from impots.jumeau.blocs.implantation import Implantation
    from impots.jumeau.blocs.investissement import Investissement
    from impots.jumeau.blocs.mesures import Mesures
    from impots.jumeau.blocs.tendance import Tendance

    p = parametres or charger()
    blocs: list[Any] = [Tendance(depart), Mesures(), ChocsEntreprises(),
                        Naissances(population_, p), Fermetures(population_, p),
                        Productivite(population_, p)]
    if investissement:
        blocs.append(Investissement(p))
    if implantation:
        blocs.append(Implantation(p))
    return blocs


__all__ = ["CREATIONS_ROW", "FERMETURES_ROW", "IDEES_ROW", "IMPLANTATION_ROW",
           "INVESTISSEMENT_ROW", "MONTEE_ROW", "SURVIE_ROW", "TAILLE_ROW",
           "ChocsEntreprises", "Parametres", "Population", "charger", "mesure_entreprises",
           "ordre_lot2", "population_depuis"]
