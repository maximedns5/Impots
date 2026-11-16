"""Une proposition de Mélenchon sur toute la population de D-521, puis son programme en
interaction (but 27, volet `mesure`, D-507 à D-509).

    python scripts/mesure_melenchon_b27.py passe <nom> <mesures> <palier> <imputations> [pop]
    python scripts/mesure_melenchon_b27.py programme            # les passes rapides, une à une
    python scripts/mesure_melenchon_b27.py analyser             # agrégats, paires, identités

Une passe : la vue figée de 2026 (la population de 2024 telle quelle, la loi de 2026),
comme la première année des études (`mesures.VUE_PREMIERE_ANNEE`). `palier` : « rapide »
(le sous-échantillon déterministe de 20 000 ménages des études) ou « complet » (les
199 451 ménages, par lots, D-362). `imputations` : « propres » (ce que la réforme exige,
comme l'étude) ou « union » (le capital et les données de ménages pour toutes, pour que
toutes les passes partagent la même référence et que les paires se soustraient).

Sorties hors git, dans `SORTIE` : un JSON d'agrégats par passe et, pour les analyses, les
colonnes par ménage (parquet). Seuls des agrégats, des déciles et des cellules entrent
dans `reports/etudes/mesure_melenchon_b27/`.
"""

from __future__ import annotations

import gc
import itertools
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SORTIE = Path(os.environ.get(
    "MESURE27_SORTIE",
    "/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/mesure27"))
ANNEE = 2026
LOTS = 8
PROGRAMME = ROOT / "programmes" / "melenchon.json"
#: Les sept mesures chiffrées du programme, dans l'ordre du rapport (D-500), nom court.
COURTS = {
    "point_indice_10": "pi",
    "indexation_pensions_prestations_10": "idx",
    "smic_1700_net": "smic",
    "garantie_autonomie_jeunes": "gaj",
    "suppression_pfu": "pfu",
    "exonerations_au_dela_2_smic": "exo",
    "defiscalisation_pensions_alimentaires": "pa",
}
#: Les colonnes par ménage gardées pour les analyses (hors git).
COLONNES = ("salaire_brut", "salaire_net", "salaire_super_brut", "cotisations_salariales",
            "cotisations_employeur", "allegement_general", "csg_deductible",
            "csg_imposable", "crds", "csg_retraite", "csg_chomage", "retraite_imposable",
            "prelevements_pensions", "ir", "af", "ppa", "rsa", "aide_logement", "aspa",
            "asf", "cf", "ars", "paje", "garantie_autonomie", "pension_employeur_etat",
            "revenu_disponible", "revenu_disponible_droit", "ppa_droit", "rsa_droit")


def reformes() -> dict[str, dict[str, Any]]:
    """{nom court : la réforme du chiffrage} lues dans `programmes/melenchon.json`."""
    prog = json.loads(PROGRAMME.read_text(encoding="utf-8"))
    out = {}
    for m in prog["mesures"]:
        if m["id"] in COURTS:
            out[COURTS[m["id"]]] = dict(m["chiffrage"]["reforme"])
    if set(out) != set(COURTS.values()):
        raise SystemExit(f"mesures introuvables : {set(COURTS.values()) - set(out)}")
    return out


def reunir(noms: list[str]) -> dict[str, Any]:
    """La réforme de plusieurs mesures : l'union de leurs boutons, refusée s'ils se
    recouvrent (aucun ne se recouvre chez Mélenchon)."""
    r = reformes()
    out: dict[str, Any] = {}
    for n in noms:
        commun = set(out) & set(r[n])
        if commun:
            raise SystemExit(f"boutons communs {commun}")
        out |= r[n]
    return out


def passe(nom: str, noms: list[str], palier: str, imputations: str,
          population: str | None = None) -> Path:
    import numpy as np
    import polars as pl

    from impots import service
    from impots.api.schemas import QUICK_TIER_HOUSEHOLDS, ReformSpec
    from impots.macro import shocks
    from impots.population import aggregate as agg_mod
    from impots.population import imputations as imp
    from impots.population.runner import households_par_lots, run

    dest = SORTIE / f"{nom}.json"
    if dest.exists():
        print(f"déjà fait : {dest}", flush=True)
        return dest
    reform = ReformSpec(**reunir(noms))
    voulues = [imp.CAPITAL, imp.MENAGES] if imputations == "union" else []
    im = imp.imputations(reform, ANNEE, demandees=voulues, chemin="le volet mesure")
    kw: dict[str, Any] = dict(year=ANNEE, reform=reform, tier="full", **im.runner(),
                              annee_consommation=int(service.POPULATION_VINTAGE))
    if im.capital:
        kw["capital_index"] = 1.0  # la vue figée (service.price_households)
    if im.menages:
        kw["menages_facteurs"] = {"wage": 1.0, "price": 1.0}
    frame = (pl.read_parquet(population) if population else service.population_frame())
    t0 = time.perf_counter()
    if palier == "rapide":
        households = run(frame, sample=QUICK_TIER_HOUSEHOLDS, **kw).households
    elif palier == "complet":
        households = households_par_lots(frame, LOTS, **kw)
    else:
        raise SystemExit(f"palier « {palier} »")
    duree = time.perf_counter() - t0
    agg = agg_mod.aggregate(households)
    built = shocks.build(
        shocks.instrument_deltas(agg.deltas,
                                 employer_contribution_delta=agg.employer_contribution_delta),
        year=ANNEE, reform_cost=agg.reform_cost,
        knobs=tuple(reform.model_dump(exclude_none=True)))
    w = households["weight"].to_numpy()
    rd = (households["revenu_disponible_reform"] - households["revenu_disponible"]).to_numpy()
    out = {
        "nom": nom, "mesures": noms, "palier": palier, "imputations": list(im.noms()),
        "population": population or "data/processed/population_2024.parquet",
        "annee": ANNEE, "vue": "figee", "duree_s": round(duree, 1),
        "menages_echantillon": int(households.height),
        "reform_cost": agg.reform_cost, "reform_cost_droit": agg.reform_cost_droit,
        "employer_contribution_delta": agg.employer_contribution_delta,
        "deltas": agg.deltas, "balance": agg.balance,
        "deciles": [d.__dict__ if hasattr(d, "__dict__") else dict(d) for d in agg.deciles],
        "impulsions": dict(built.by_instrument),
        "delta_rd_somme_menages": float((rd * w).sum()),
        "gagnants": float(w[rd > 1.0].sum()), "perdants": float(w[rd < -1.0].sum()),
        "menages": float(w.sum()),
    }
    SORTIE.mkdir(parents=True, exist_ok=True)
    garder = ["household_id", "weight", "n_persons", "n_aged_14_plus",
              "n_children_under_14", "n_dependants"]
    for c in COLONNES:
        for s in ("", "_reform"):
            if f"{c}{s}" in households.columns:
                garder.append(f"{c}{s}")
    for c in households.columns:
        if c.startswith("salaires_payes") or c.startswith("salaire_paye"):
            garder.append(c)
    households.select(garder).write_parquet(SORTIE / f"{nom}.parquet")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n",
                    encoding="utf-8")
    print(f"{nom} : coût {agg.reform_cost / 1e9:+.3f} Md€ en {duree:.0f} s", flush=True)
    del households
    gc.collect()
    _ = np
    return dest


def programme() -> None:
    """Les passes rapides du programme, une à une, dans un seul processus : les sept
    mesures avec leurs propres imputations (comme l'étude), puis avec l'union ; les 21
    paires ; le programme entier."""
    noms = list(COURTS.values())
    for n in noms:
        passe(f"rapide_propres_{n}", [n], "rapide", "propres")
    for n in noms:
        passe(f"rapide_union_{n}", [n], "rapide", "union")
    for a, b in itertools.combinations(noms, 2):
        passe(f"rapide_union_{a}+{b}", [a, b], "rapide", "union")
    passe("rapide_union_programme", noms, "rapide", "union")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    if cmd == "passe":
        nom, mesures, palier, imputations, *pop = args
        passe(nom, mesures.split(","), palier, imputations, *(pop or [None]))
    elif cmd == "programme":
        programme()
    else:
        raise SystemExit(f"commande « {cmd} »")
