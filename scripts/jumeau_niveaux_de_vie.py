#!/usr/bin/env python
"""But 29, volet `pouvoir` (D-591) — les niveaux de vie dans chaque cellule, une fois.

La dimension « ce qui rapproche ou sépare » (`jumeau.impacts.entente`) reconstitue la
pauvreté, le Gini et D9/D1 sur les cinquante cellules du jumeau. Ce script lit, sur la
passe de référence même des cellules (même sous-échantillon, même graine, même droit de
2024, mêmes imputations : `scripts/jumeau_cellules.py`), ce que les cellules ne portent
pas : les quantiles du niveau de vie des personnes de chaque cellule, et, par famille de
groupes (l'âge et le statut de la personne de référence, le territoire), les personnes
et leur niveau de vie moyen dans chaque cellule. Et les indicateurs mesurés directement
sur la passe, pour recouper la reconstitution. Des agrégats seulement : aucune ligne de
ménage.

Les règles de secret : une cellule de moins de `MIN_CELLULE` ménages tirés garde la forme
approchée (`entente.approchee`), à sa moyenne ; un groupe de moins de `MIN_GROUPE` ménages
tirés dans une cellule y prend le niveau de vie moyen de la cellule. Se lance détaché,
sous le verrou commun des passes :

    setsid nohup flock <verrou> env PYTHONPATH=src .venv/bin/python \
        scripts/jumeau_niveaux_de_vie.py > /tmp/nv.log 2>&1 &
"""

from __future__ import annotations

import argparse
import datetime as dt
import gc
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import polars as pl  # noqa: E402

from impots.jumeau import cellules as cel  # noqa: E402
from impots.jumeau.impacts import entente  # noqa: E402
from impots.population.runner import SAMPLE_SEED, run, subsample  # noqa: E402

POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"
SORTIE = ROOT / "reports" / "jumeau" / "niveaux_de_vie_cellules.json"
MENAGES = 30_000  # celui des cellules de D-553 (`jumeau_cellules_2024.json`, meta)
RANGS = (np.arange(20) + 0.5) / 20
MIN_CELLULE = 30
MIN_GROUPE = 10
ILE_DE_FRANCE = {"75", "77", "78", "91", "92", "93", "94", "95"}


def quantiles_ponderes(x: np.ndarray, w: np.ndarray, p: np.ndarray) -> np.ndarray:
    o = np.argsort(x, kind="stable")
    xs, ws = x[o], w[o]
    cum = np.cumsum(ws)
    return np.interp(p, (cum - 0.5 * ws) / cum[-1], xs)


def groupes_menages(frame: pl.DataFrame) -> pl.DataFrame:
    """household_id → l'âge, le statut de la personne de référence, le territoire."""
    pr = frame.filter(pl.col("role_menage") == "personne_de_reference").select(
        "household_id", "age", "statut_activite", "pension_annuelle", "region",
        "departement")
    age = (pl.when(pl.col("age") < 30).then(pl.lit("Moins de 30 ans"))
           .when(pl.col("age") < 45).then(pl.lit("30 à 44 ans"))
           .when(pl.col("age") < 60).then(pl.lit("45 à 59 ans"))
           .when(pl.col("age") < 75).then(pl.lit("60 à 74 ans"))
           .otherwise(pl.lit("75 ans et plus")))
    statut = (pl.when(pl.col("statut_activite") == "employed").then(pl.lit("En emploi"))
              .when(pl.col("statut_activite") == "unemployed").then(pl.lit("Au chômage"))
              .when(pl.col("pension_annuelle").fill_null(0.0) > 0).then(pl.lit("Retraité"))
              .otherwise(pl.lit("Autre inactif (études, foyer…)")))
    territoire = (pl.when(pl.col("region") == "dom").then(pl.lit("Outre-mer"))
                  .when(pl.col("departement").cast(pl.Utf8).str.slice(0, 2)
                        .is_in(sorted(ILE_DE_FRANCE))).then(pl.lit("Île-de-France"))
                  .otherwise(pl.lit("Autres régions de métropole")))
    return pr.select("household_id", age.alias("age"), statut.alias("statut"),
                     territoire.alias("territoire"))


def main() -> int:
    from impots.population.aggregate import consumption_units, weighted_decile_index

    parser = argparse.ArgumentParser()
    parser.add_argument("--menages", type=int, default=MENAGES)
    parser.add_argument("--sortie", type=Path, default=SORTIE)
    args = parser.parse_args()
    debut = time.perf_counter()
    frame = pl.read_parquet(POPULATION)
    echantillon = subsample(frame, args.menages)
    del frame
    gc.collect()
    passe = run(echantillon, year=cel.ANNEE, tier="full", impute_niches=True,
                impute_capital=True, impute_ij=True, impute_consommation=True)
    print(f"passe : {passe.timings}", flush=True)

    h = passe.households.join(cel.types_menages(echantillon), on="household_id",
                              how="left").join(groupes_menages(echantillon),
                                               on="household_id", how="left")
    poids = h["weight"].to_numpy().astype(float)
    uc = consumption_units(h["n_aged_14_plus"].to_numpy(),
                           h["n_children_under_14"].to_numpy())
    nv = h["revenu_disponible"].to_numpy().astype(float) / uc
    decile = weighted_decile_index(nv, poids)
    cellule = decile * len(cel.TYPES) + np.array([cel.TYPES.index(t) for t in h["type"]])
    wp = poids * h["n_persons"].to_numpy().astype(float)

    # Le recoupement : les ménages de chaque cellule, contre les cellules du jumeau.
    cellules = cel.Cellules.lire()
    menages = np.bincount(cellule, weights=poids, minlength=cel.N_CELLULES)
    ecart_menages = float(np.max(np.abs(menages / cellules["menages"] - 1.0)))
    print(f"ménages par cellule, écart relatif maximal aux cellules : {ecart_menages:.2e}")

    approchee = entente.approchee(cellules)
    q = np.empty((cel.N_CELLULES, RANGS.size))
    tires = np.bincount(cellule, minlength=cel.N_CELLULES)
    approchees = []
    for c in range(cel.N_CELLULES):
        s = cellule == c
        if tires[c] < MIN_CELLULE:
            moyenne = float((nv[s] * wp[s]).sum() / wp[s].sum()) if s.any() else 0.0
            forme = np.interp(RANGS, approchee.rangs, approchee.quantiles[c])
            q[c] = forme * (moyenne / forme.mean() if forme.mean() else 1.0)
            approchees.append(c)
        else:
            q[c] = quantiles_ponderes(nv[s], wp[s], RANGS)

    groupes: dict[str, dict[str, dict[str, list[float]]]] = {}
    for famille, col in (("Âge de la personne de référence", "age"),
                         ("Statut de la personne de référence", "statut"),
                         ("Territoire", "territoire")):
        valeurs = h[col].to_numpy()
        groupes[famille] = {}
        for g in sorted(set(valeurs.tolist())):
            s = valeurs == g
            pers = np.bincount(cellule[s], weights=wp[s], minlength=cel.N_CELLULES)
            somme = np.bincount(cellule[s], weights=(wp * nv)[s], minlength=cel.N_CELLULES)
            n_tires = np.bincount(cellule[s], minlength=cel.N_CELLULES)
            moy_cellule = (np.bincount(cellule, weights=wp * nv, minlength=cel.N_CELLULES)
                           / np.bincount(cellule, weights=wp, minlength=cel.N_CELLULES))
            moy = np.where(n_tires >= MIN_GROUPE, np.divide(
                somme, pers, out=np.zeros_like(somme), where=pers > 0), moy_cellule)
            groupes[famille][g] = {"personnes": [float(x) for x in pers],
                                   "niveau_de_vie": [float(x) for x in moy]}

    # Les indicateurs mesurés sur la passe, pondérés personne.
    ind = entente.indicateurs(nv, wp, np.zeros(nv.size, dtype=int), np.array([0.5]))
    seuil = ind["seuil"]
    pauvres = nv < seuil
    typ = np.array([cel.TYPES.index(t) for t in h["type"]])
    reference = {
        "pauvrete": float(wp[pauvres].sum() / wp.sum()), "gini": ind["gini"],
        "d9_d1": ind["d9_d1"], "s80_s20": ind["s80_s20"], "mediane": ind["mediane"],
        "moyenne": ind["moyenne"],
        **{f"pauvrete_{t}": float(wp[pauvres & (typ == i)].sum() / wp[typ == i].sum())
           for i, t in enumerate(cel.TYPES)}}
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    sortie = {
        "types": list(cel.TYPES), "deciles": cel.N_DECILES, "annee": cel.ANNEE,
        "rangs": [float(x) for x in RANGS],
        "quantiles": [[float(x) for x in ligne] for ligne in q],
        "source": (f"mesurée : les quantiles du niveau de vie des personnes de chaque "
                   f"cellule, passe de référence des cellules ({args.menages} ménages, "
                   f"droit de {cel.ANNEE}, population {POPULATION.name})"),
        "groupes": groupes, "reference": reference,
        "meta": {"construit": dt.date.today().isoformat(), "commit": commit,
                 "population_sha256": hashlib.sha256(POPULATION.read_bytes()).hexdigest(),
                 "menages_echantillon": args.menages, "graine": SAMPLE_SEED,
                 "ecart_menages_cellules": ecart_menages,
                 "cellules_approchees": approchees, "min_cellule": MIN_CELLULE,
                 "min_groupe": MIN_GROUPE, "tires_par_cellule": [int(x) for x in tires],
                 "duree_s": round(time.perf_counter() - debut, 1)}}
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n",
                           encoding="utf-8")
    print(f"écrit {args.sortie} ; référence mesurée : {reference}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
