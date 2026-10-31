#!/usr/bin/env python
"""L'écart du volet prime d'activité de l'art. 74, mesuré contre la Cnaf (but 9, D-315).

D-300 a noté le cas à +167 %, +67 % à mois et taux égaux, et dit où chercher : qui touche
la prime, avec quelle famille, et où au regard du forfait. Ce script le mesure sur la
population du cas (20 000 ménages, le tirage de `runner`, 2024), au palier complet.

Pour une année, trois passes, l'une après l'autre :

* **la référence** : la prime de décembre et de l'année, par famille, avec ce qui la
  compose en novembre (forfait, ressources, forfait logement, bonifications) ;
* **le forfait à +1 %** pour toute l'année (`ppa_revalorisation_portee` à 1,01, le bouton
  porté de D-301, que la bonification et le forfait logement suivent) : la hausse de la
  prime pour un point de forfait, ce que la Cnaf appelle l'élasticité ;
* **les salaires à +1 %** (2024 seulement) : l'élasticité aux revenus d'activité, que la
  Cnaf publie aussi.

En 2026, l'année que le cas chiffre, les deux premières seulement : elles relient la base
mesurée au cas et à la fiche.

Usage :
  `.venv/bin/python scripts/verify_ecart_ppa.py --annee 2024` (puis `--annee 2026`), qui
  écrit `reports/ecart_ppa_<annee>.json` ; puis `--rendre`, qui écrit
  `reports/ecart_ppa.md` depuis les deux rapports et les deux publications de la Cnaf.
Chaque passe tient quelque 3 Go ; deux années ne tournent jamais ensemble.
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"
REPORTS = ROOT / "reports"
SAMPLE = 20_000
POINT = 1.01
DECEMBRE, NOVEMBRE = 12, 11


def _report(annee: int) -> Path:
    return REPORTS / f"ecart_ppa_{annee}.json"


def familles(frame: pl.DataFrame, built) -> pl.DataFrame:
    """Une ligne par famille, dans l'ordre d'openfisca : son poids (celui de son ménage,
    la moyenne des poids de ses membres) et son demandeur."""
    from impots.population.runner import _household_index

    weights = (frame.group_by("household_id").agg(pl.col("weight").mean())
               .sort("household_id")["weight"].to_numpy().astype(np.float64))
    position = _household_index(frame, "famille_id", built.household_ids)
    demandeurs = frame.filter(pl.col("role_famille") == "demandeur").sort("famille_id")
    ids = demandeurs["famille_id"].to_numpy().astype(str)
    if ids.size != built.famille_ids.size or not (ids == built.famille_ids).all():
        raise RuntimeError("chaque famille n'a pas exactement un demandeur, dans l'ordre "
                           "d'openfisca")
    return pl.DataFrame({"famille_id": ids, "poids": weights[position],
                         "age": demandeurs["age"].to_numpy(),
                         "sexe": demandeurs["sex"].to_numpy()})


def par_famille(frame: pl.DataFrame, built, persons) -> np.ndarray:
    """Une variable des personnes sommée dans leur famille."""
    index = np.searchsorted(built.famille_ids, frame["famille_id"].to_numpy().astype(str))
    return np.bincount(index, weights=persons.astype(np.float64),
                       minlength=built.famille_ids.size)


def mesurer(annee: int) -> dict[str, object]:
    from impots.api.schemas import ReformSpec
    from impots.engine.system import baseline, reformed_for
    from impots.population import ecart_ppa
    from impots.population.runner import subsample
    from impots.population.to_openfisca import build_simulation
    from impots.predictif import recherche

    commit, dirty = recherche.code_state(ROOT)
    frame = subsample(pl.read_parquet(POPULATION), SAMPLE).sort("person_id")
    timings: dict[str, float] = {}

    started = time.perf_counter()
    built = build_simulation(frame, baseline(), annee)
    fam = familles(frame, built)
    cols: dict[str, np.ndarray] = {
        "prime": built.calculate("ppa", month=DECEMBRE),
        "prime_annuelle": built.calculate("ppa", add=True),
        "n_parents": built.calculate("nb_parents", month=DECEMBRE),
        "n_enfants": built.calculate("rsa_nb_enfants", month=DECEMBRE),
        "rsa": built.calculate("rsa", month=DECEMBRE),
        "majoree": built.calculate("rsa_majore_eligibilite", month=DECEMBRE),
        "forfait": built.calculate("ppa_fictive_montant_forfaitaire", month=NOVEMBRE),
        "ressources": built.calculate("ppa_base_ressources", month=NOVEMBRE),
        "forfait_logement": built.calculate("ppa_forfait_logement", month=NOVEMBRE),
        "revenu_activite": built.calculate("ppa_revenu_activite", month=NOVEMBRE),
        "bonification": par_famille(frame, built,
                                    built.calculate("ppa_bonification", month=NOVEMBRE)),
    }
    smic = built.simulation.tax_benefit_system.parameters(
        f"{annee}-{NOVEMBRE:02d}").marche_travail.salaire_minimum.smic.smic_b_horaire
    smic_mensuel = float(smic) * 35 * 52 / 12
    del built
    gc.collect()
    timings["reference_s"] = round(time.perf_counter() - started, 1)

    started = time.perf_counter()
    reformed = build_simulation(
        frame, reformed_for(ReformSpec(ppa_revalorisation_portee=POINT), annee), annee)
    cols["prime_forfait"] = reformed.calculate("ppa", month=DECEMBRE)
    cols["prime_forfait_annuelle"] = reformed.calculate("ppa", add=True)
    del reformed
    gc.collect()
    timings["forfait_s"] = round(time.perf_counter() - started, 1)

    if annee == 2024:
        started = time.perf_counter()
        richer = frame.with_columns(pl.col("salaire_brut_annuel") * POINT)
        salaries = build_simulation(richer, baseline(), annee)
        cols["prime_salaire"] = salaries.calculate("ppa", month=DECEMBRE)
        cols["prime_salaire_annuelle"] = salaries.calculate("ppa", add=True)
        del salaries
        gc.collect()
        timings["salaires_s"] = round(time.perf_counter() - started, 1)

    w = fam["poids"].to_numpy()
    prime, forfait_up = cols["prime"], cols["prime_forfait"]
    beneficiaire = prime > ecart_ppa.SEUIL
    # Au-dessus du forfait, le forfait ne s'annule pas dans la formule et un point de
    # forfait ajoute un point de (forfait − forfait logement) ; en dessous, seule la
    # bonification bouge (`ppa_fictive`).
    au_dessus = cols["ressources"] + cols["forfait_logement"] > cols["forfait"]
    analytique = np.where(beneficiaire,
                          (au_dessus * (cols["forfait"] - cols["forfait_logement"])
                           + cols["bonification"]) * (POINT - 1), 0.0)

    def decoupe(groupe, cles):
        cells = ecart_ppa.cellules(groupe, w, prime, forfait_up, cles)
        return {k: {"beneficiaires": c.beneficiaires, "depense": c.depense,
                    "hausse": c.hausse, "montant_moyen": c.montant_moyen,
                    "elasticite": c.elasticite} for k, c in cells.items()}

    config = ecart_ppa.configuration(cols["n_parents"], cols["n_enfants"],
                                     fam["sexe"].to_numpy())
    sous = {
        "bonification": cols["bonification"] > 0,
        "cumul_rsa": cols["rsa"] > ecart_ppa.SEUIL,
        "majoration_isolement": cols["majoree"].astype(bool),
    }
    out: dict[str, object] = {
        "annee": annee, "commit": commit, "dirty": dirty, "echantillon": SAMPLE,
        "point": POINT, "smic_brut_mensuel": smic_mensuel, "timings": timings,
        "totaux": {
            "beneficiaires": float(w[beneficiaire].sum()),
            "depense": float((w * prime).sum()),
            "hausse": float((w * (forfait_up - prime)).sum()),
            "hausse_analytique": float((w * analytique).sum()),
            "entrants": float(w[(~beneficiaire) & (forfait_up > ecart_ppa.SEUIL)].sum()),
            "depense_annuelle": float((w * cols["prime_annuelle"]).sum()),
            "hausse_annuelle": float((w * (cols["prime_forfait_annuelle"]
                                           - cols["prime_annuelle"])).sum()),
        },
        "configurations": decoupe(config, ecart_ppa.CONFIGURATIONS),
        "ages": decoupe(ecart_ppa.age_band(fam["age"].to_numpy()), ecart_ppa.AGES),
        "tranches_revenu": decoupe(
            ecart_ppa.tranche_revenu(cols["revenu_activite"], smic_mensuel),
            tuple(code for _, code in ecart_ppa.TRANCHES_REVENU)),
        "tranches_montant": decoupe(ecart_ppa.tranche_montant(prime),
                                    tuple(code for _, code in ecart_ppa.TRANCHES_MONTANT)),
        "position": decoupe(np.where(au_dessus, "au_dessus", "en_dessous").astype(object),
                            ("au_dessus", "en_dessous")),
        "sous_populations": {
            k: {"beneficiaires": float(w[beneficiaire & m].sum()),
                "depense": float((w * prime)[beneficiaire & m].sum())}
            for k, m in sous.items()},
    }
    if "prime_salaire" in cols:
        out["totaux"]["baisse_salaire"] = float((w * (cols["prime_salaire"] - prime)).sum())
        out["totaux"]["baisse_salaire_annuelle"] = float(
            (w * (cols["prime_salaire_annuelle"] - cols["prime_annuelle"])).sum())
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--annee", type=int, choices=(2024, 2026))
    group.add_argument("--rendre", action="store_true")
    args = parser.parse_args()
    if args.rendre:
        from impots.population import ecart_ppa, ppa_cnaf

        reports = {a: json.loads(_report(a).read_text(encoding="utf-8")) for a in (2024, 2026)}
        text = ecart_ppa.rendre(reports[2024], reports[2026], ppa_cnaf.conjoncture(),
                                ppa_cnaf.elasticites())
        (REPORTS / "ecart_ppa.md").write_text(text, encoding="utf-8")
        print(f"-> {REPORTS / 'ecart_ppa.md'}")
        return 0
    found = mesurer(args.annee)
    _report(args.annee).write_text(json.dumps(found, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
    print(f"-> {_report(args.annee)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
