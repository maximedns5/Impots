"""La table de passage des cellules du jumeau aux territoires (but 29, volet `territoires`,
D-645) : où tombe le gain d'une mesure.

Les cellules du jumeau (`jumeau.cellules`) sont décile de niveau de vie × type de ménage,
sans territoire. Cette table dit, pour chaque cellule, comment ses ménages, ses personnes,
ses unités de consommation et son revenu disponible se répartissent entre des territoires,
sur deux axes :

* **les régions que la population connaît** : la métropole et les quatre départements
  d'outre-mer de l'enquête Emploi (`departement`, tiré sur le recensement, `logement`) ;
  le fichier détail de l'enquête n'a aucune région métropolitaine, et aucune n'est
  inventée ;
* **les types de territoire** : en métropole, le rural (la commune est hors unité urbaine,
  `STCOMM2020` = H, observé dans l'enquête et relu par l'identifiant du ménage,
  `IDENT-TRIM`) ; dans une unité urbaine, la zone APL (tirée, `logement`) : 1,
  l'agglomération parisienne ; 2, les grandes agglomérations ; 3, les villes moyennes et
  petites ; l'outre-mer à part.

Le décile et le type se rangent comme `cellules.construire` les range, sur le revenu
disponible d'une passe de référence déjà faite sur toute la population (aucune passe
n'est lancée ici). Une case (cellule, territoire) de moins de `SEUIL` ménages observés
prend, pour la cellule entière et sur son axe, la répartition de son décile, ou à défaut
la répartition nationale (D-645). Le fichier écrit (`parametres/territoires.json`) est un
agrégat : 50 cellules × 10 territoires, aucune ligne de ménage.

Ce module lit polars : il tourne hors du navigateur. La dimension qui lit la table
(`impacts.territoires`) n'a besoin que de numpy (D-415).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from impots.jumeau.cellules import N_CELLULES, N_DECILES, TYPES

FICHIER = Path(__file__).resolve().parent / "parametres" / "territoires.json"

#: Le seuil de taille d'une case : en dessous, ses parts ne sont pas publiées (D-645).
SEUIL = 30

#: Les deux axes, chacun ses territoires (clé, libellé), dans l'ordre de la page.
AXES: dict[str, tuple[tuple[str, str], ...]] = {
    "regions": (
        ("metropole", "Métropole"),
        ("971", "Guadeloupe"),
        ("972", "Martinique"),
        ("973", "Guyane"),
        ("974", "La Réunion"),
    ),
    "types": (
        ("zone_1", "Agglomération parisienne (zone 1)"),
        ("zone_2", "Grandes agglomérations (zone 2)"),
        ("zone_3", "Villes moyennes et petites (zone 3)"),
        ("rural", "Rural (hors unité urbaine)"),
        ("outre_mer", "Outre-mer"),
    ),
}
#: Ce que la table somme, par case.
SOMMES = ("menages", "personnes", "uc", "revenu_disponible")


class TerritoiresError(ValueError):
    """Une table qui ne se construit pas."""


def territoires_menages(population: Any, eec: Any) -> Any:
    """household_id → région et type de territoire.

    `population` : la population (une ligne par personne) ; `eec` : le fichier détail de
    l'enquête Emploi (IDENT, TRIM, STCOMM2020). Refusé si un ménage de la population n'a
    pas son statut de commune dans l'enquête."""
    import polars as pl

    menages = population.group_by("household_id").agg(
        pl.col("region").first(), pl.col("departement").drop_nulls().first(),
        pl.col("zone_apl").first())
    statut = (eec.with_columns(pl.concat_str([pl.col("IDENT"), pl.lit("-"), pl.col("TRIM")])
                               .alias("household_id"))
              .group_by("household_id").agg(pl.col("STCOMM2020").drop_nulls().first()
                                            .alias("stcomm")))
    m = menages.join(statut, on="household_id", how="left")
    manque = m.filter(pl.col("stcomm").is_null() & (pl.col("region") == "metropole"))
    if manque.height:
        raise TerritoiresError(f"{manque.height} ménages de métropole sans statut de "
                               f"commune dans l'enquête : ce n'est pas la même enquête")
    dom = pl.col("region") == "dom"
    if m.filter(dom & pl.col("departement").is_null()).height:
        raise TerritoiresError("un ménage d'outre-mer sans département")
    return m.select(
        "household_id",
        pl.when(dom).then(pl.col("departement")).otherwise(pl.lit("metropole"))
        .alias("regions"),
        pl.when(dom).then(pl.lit("outre_mer"))
        .when(pl.col("stcomm") == "H").then(pl.lit("rural"))
        .otherwise(pl.col("zone_apl")).alias("types"))


def seuils_deciles(niveau: np.ndarray, poids: np.ndarray, decile: np.ndarray
                   ) -> list[float]:
    """Les neuf seuils : le milieu entre le plus haut niveau de vie d'un décile et le plus
    bas du suivant (le rangement de `weighted_decile_index`)."""
    return [float(0.5 * (niveau[decile == d].max() + niveau[decile == d + 1].min()))
            for d in range(N_DECILES - 1)]


def _repartir(compte: np.ndarray, observes: np.ndarray, seuil: int
              ) -> tuple[np.ndarray, np.ndarray]:
    """Les parts (50, T) de chaque cellule entre les territoires d'un axe, avec la règle du
    seuil ; et le niveau de regroupement de chaque cellule (0 : la sienne, 1 : son décile,
    2 : nationale)."""
    n_types = len(TYPES)
    total = compte.sum(axis=1, keepdims=True)
    parts = np.divide(compte, total, out=np.zeros_like(compte), where=total > 0)
    dec_c = compte.reshape(N_DECILES, n_types, -1).sum(axis=1)
    dec_o = observes.reshape(N_DECILES, n_types, -1).sum(axis=1)
    national = compte.sum(axis=0) / compte.sum()
    niveau = np.zeros(N_CELLULES, dtype=int)
    for c in range(N_CELLULES):
        if (observes[c] >= seuil).all():
            continue
        d = c // n_types
        if (dec_o[d] >= seuil).all():
            parts[c] = dec_c[d] / dec_c[d].sum()
            niveau[c] = 1
        else:
            parts[c] = national
            niveau[c] = 2
    return parts, niveau


def construire(population: Any, eec: Any, passe: Any, seuil: int = SEUIL,
               meta: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """La table, depuis la population, l'enquête Emploi et une passe de référence
    (`household_id`, `weight`, `n_persons`, `n_aged_14_plus`, `n_children_under_14`, le revenu
    disponible de la référence, `revenu_disponible`)."""
    import polars as pl

    from impots.jumeau.cellules import types_menages
    from impots.population.aggregate import consumption_units, weighted_decile_index

    terr = territoires_menages(population, eec)
    types = types_menages(population)
    menages = (passe.select("household_id", "weight", "n_persons", "n_aged_14_plus",
                            "n_children_under_14", "revenu_disponible")
               .join(types, on="household_id", how="left")
               .join(terr, on="household_id", how="left"))
    if menages.select(pl.col("type").null_count() + pl.col("regions").null_count()).item():
        raise TerritoiresError("des ménages de la passe absents de la population : ce n'est "
                               "pas la population de la passe")
    if menages.height != population["household_id"].n_unique():
        raise TerritoiresError("la passe ne porte pas toute la population")
    poids = menages["weight"].to_numpy().astype(np.float64)
    uc = consumption_units(menages["n_aged_14_plus"].to_numpy(),
                           menages["n_children_under_14"].to_numpy())
    rd = menages["revenu_disponible"].to_numpy().astype(np.float64)
    niveau = rd / uc
    decile = weighted_decile_index(niveau, poids)
    cellule = decile * len(TYPES) + np.array([TYPES.index(t) for t in menages["type"]])
    personnes = menages["n_persons"].to_numpy().astype(np.float64)
    valeurs = {"menages": poids, "personnes": personnes * poids, "uc": uc * poids,
               "revenu_disponible": rd * poids}

    axes: dict[str, Any] = {}
    for axe, territoires in AXES.items():
        cles = [k for k, _ in territoires]
        t = np.array([cles.index(x) for x in menages[axe].to_list()])
        idx = cellule * len(cles) + t
        taille = N_CELLULES * len(cles)

        def somme(w: np.ndarray, idx: np.ndarray = idx, taille: int = taille,
                  n: int = len(cles)) -> np.ndarray:
            return np.bincount(idx, weights=w, minlength=taille).reshape(N_CELLULES, n)

        observes = somme(np.ones_like(poids))
        brutes = {k: somme(v) for k, v in valeurs.items()}
        parts, regroupe = _repartir(brutes["menages"], observes, seuil)
        cases: dict[str, np.ndarray] = {}
        for k in SOMMES:
            total = brutes[k].sum(axis=1, keepdims=True)
            propres = brutes[k]
            # Une cellule regroupée : ses sommes suivent ses ménages, au prorata.
            cases[k] = np.where(regroupe[:, None] > 0, total * parts, propres)
        axes[axe] = {
            "territoires": [{"cle": k, "libelle": lib} for k, lib in territoires],
            **{k: [[round(float(x), 2) for x in ligne] for ligne in cases[k]]
               for k in SOMMES},
            "regroupement": [int(x) for x in regroupe],
        }
    return {
        "decision": "D-645", "annee_revenus": 2024, "seuil_menages_observes": seuil,
        "types": list(TYPES), "deciles": N_DECILES,
        "seuils_niveau_de_vie": [round(x, 2) for x in seuils_deciles(niveau, poids, decile)],
        "axes": axes, "meta": dict(meta or {}),
    }


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def ecrire(table: Mapping[str, Any], chemin: Path = FICHIER) -> Path:
    chemin.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")
    return chemin
