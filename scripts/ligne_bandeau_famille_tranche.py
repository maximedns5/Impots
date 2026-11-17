"""La ligne de grille `bandeau_famille_part_2_5_3_5_smic` (but 28, volet `reaction`, D-531).

La part du bandeau famille (la réduction de 1,8 point de la cotisation d'allocations
familiales, CSS art. L241-6-1) que portent les salariés dont la rémunération est
comprise entre 2,5 et 3,5 Smic, sur la population de D-521 ramenée à l'année par les
indices de la grille (`verification._population`), au droit de l'année (openfisca), sans
réforme. Le bandeau étant un taux unique sur toute sa bande, cette part est celle de
l'assiette : une mesure de la densité des salaires au-dessus de 2,5 Smic, qu'aucune
autre ligne ne juge (D-509).

Pour chaque personne : le bandeau de l'année (`allegement_cotisation_allocations_
familiales`, somme des mois), et sa rémunération en multiples du Smic, `assiette_
allegement` sur `smic_proratise` (sommes des mois), les deux variables qu'openfisca
compare au plafond de 3,5. Les ménages sont passés par lots (un crc32 de leur
identifiant), sans repondération : la part est un rapport.

    PYTHONPATH=src python scripts/ligne_bandeau_famille_tranche.py 2022 [--lots 8]
        [--menages N]   (un sous-échantillon, pour un essai)
"""

from __future__ import annotations

import argparse
import gc
import json
import time
import zlib
from pathlib import Path

import numpy as np
import polars as pl

from impots import verification
from impots.engine.system import baseline
from impots.population.runner import subsample
from impots.population.to_openfisca import build_simulation

BANDES = (0.0, 1.6, 2.0, 2.5, 3.0, 3.5)
#: Le complément de la passe de la grille de l'année, que `verification.grille` lit avec
#: elle (D-531).
SORTIE = verification.RAPPORTS / "complement_{annee}.json"
MESURE = "bandeau famille entre 2,5 et 3,5 Smic / bandeau famille"


def passe(annee: int, lots: int, menages: int | None) -> dict:
    frame, record = verification._population(annee)
    if menages is not None:
        frame = subsample(frame, menages)
    frame = frame.sort("person_id")
    lot = frame["household_id"].map_elements(
        lambda k: zlib.crc32(str(k).encode()) % lots, return_dtype=pl.Int64)
    systeme = baseline()
    bandeau, x, poids = [], [], []
    for k in range(lots):
        part = frame.filter(lot == k)
        built = build_simulation(part, systeme, annee)
        b = built.calculate("allegement_cotisation_allocations_familiales", add=True)
        a = built.calculate("assiette_allegement", add=True)
        s = built.calculate("smic_proratise", add=True)
        bandeau.append(np.asarray(b, dtype=float))
        x.append(np.where(s > 0, a / np.maximum(s, 1e-9), 0.0))
        poids.append(part.sort("person_id")["weight"].to_numpy().astype(float))
        del built, part
        gc.collect()
    b, x, w = (np.concatenate(v) for v in (bandeau, x, poids))
    total = float((b * w).sum())
    out = {"annee": annee, "lots": lots, "menages": menages,
           "commit": verification._commit()[0], "vieillissement": record,
           "bandeau_famille_total": total, "par_bande": {}}
    for lo, hi in zip(BANDES, (*BANDES[1:], np.inf), strict=True):
        m = (x > lo) & (x <= hi)
        out["par_bande"][f"{lo}-{hi}"] = {
            "bandeau": float((b * w)[m].sum()),
            "beneficiaires": float(w[m & (b > 0)].sum())}
    haut = (x > 2.5) & (x <= 3.5)
    out["mesures"] = {MESURE: float((b * w)[haut].sum()) / total}
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("annee", type=int)
    p.add_argument("--lots", type=int, default=8)
    p.add_argument("--menages", type=int, default=None)
    p.add_argument("--essai", action="store_true", help="ne pas écrire le rapport")
    a = p.parse_args()
    if not a.essai and verification._commit()[1]:
        raise SystemExit("src ou docs ne sont pas commités : le complément nomme son commit")
    t0 = time.perf_counter()
    out = passe(a.annee, a.lots, a.menages)
    out["secondes"] = round(time.perf_counter() - t0, 1)
    texte = json.dumps(out, ensure_ascii=False, indent=1)
    print(texte)
    if not a.essai:
        chemin = Path(str(SORTIE).format(annee=a.annee))
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
