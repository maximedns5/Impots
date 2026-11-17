"""Le juge du pouvoir d'achat et de ce qui rapproche ou sépare (but 29, `pouvoir`, D-591).

Deux mesures passées, préenregistrées dans D-591 avant tout calcul et avant d'ouvrir la
publication du juge (Insee, *France, portrait social*) :

* la revalorisation exceptionnelle de la prime d'activité de 2019 (la bonification
  individuelle, décret n° 2018-1197), la passe de D-535 refaite (`juges_passe_b28`), les
  niveaux de vie des ménages gardés cette fois (hors git) ;
* la baisse de l'impôt sur le revenu de 2020 (loi de finances pour 2020, art. 2 : la
  tranche à 14 % ramenée à 11 %, le seuil de la tranche à 30 % abaissé, la décote
  resserrée) : la loi de 2020 contre la même loi au barème et à la décote de 2019
  revalorisés comme le seuil de la dernière tranche (+0,2 %), sur la population ramenée à
  2020.

Pour chacune : le gain par décile de niveau de vie (pondéré personne, rang sans la
mesure), le taux de pauvreté à 60 % du médian, le Gini et D9/D1 avec et sans la mesure,
mesurés sur les ménages de la passe ; puis les mêmes indicateurs reconstitués sur les
cellules du jumeau (`jumeau.impacts.entente`), depuis les seuls chocs par décile, comme
la dimension les lit pour une étude.

    PYTHONPATH=src python scripts/juges_pouvoir_b29.py ppa_passe|ir_passe|rapport
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import juges_passe_b28 as j28  # noqa: E402

SORTIE = Path(os.environ.get(
    "JUGES29_SORTIE",
    "/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/"
    "pouvoir/passes"))
RAPPORT = ROOT / "reports" / "verification" / "juges_pouvoir_b29"
MENAGES = j28.MENAGES
#: Le contrefactuel de 2020 : le barème et la décote des revenus de 2019 (openfisca-
#: france, `impot_revenu.bareme_ir_depuis_1945.bareme` et `…plaf_qf.decote` au
#: 2019-01-01), revalorisés comme le seuil de la dernière tranche, que la loi n'a pas
#: touché (157 806 → 158 122 €, +0,2 %).
INDEXATION_2020 = 158122 / 157806
BAREME_2019 = ((0, 0.0), (10064, 0.14), (27794, 0.30), (74517, 0.41), (157806, 0.45))
DECOTE_2019 = {"decote_seuil_celib": 1208.0, "decote_seuil_couple": 1990.0,
               "decote_taux": 0.75}
COLONNES = ("weight", "n_persons", "n_aged_14_plus", "n_children_under_14",
            "revenu_disponible", "revenu_disponible_reform")


def _garder(nom: str, h: Any, extra: dict[str, Any]) -> Path:
    SORTIE.mkdir(parents=True, exist_ok=True)
    h.select([c for c in COLONNES if c in h.columns]).write_parquet(SORTIE / f"{nom}.parquet")
    (SORTIE / f"{nom}.json").write_text(json.dumps(extra, ensure_ascii=False, indent=1,
                                                   default=float) + "\n", encoding="utf-8")
    print(SORTIE / f"{nom}.parquet", flush=True)
    return SORTIE / f"{nom}.parquet"


def ppa_passe() -> Path:
    """La passe de D-535 : « avec » la loi de 2019 (la passe de référence), « sans » le
    miroir à la bonification de 2018 (la réforme)."""
    from impots.api.schemas import ReformSpec
    from impots.population import runner

    frame, rec = j28.population(2019)
    runner.reformed_for = j28._miroir_reformed_for(runner.reformed_for)
    spec = ReformSpec(ppa_bonification_taux_max=j28.BONIF_2018["taux_bonification_max"])
    t0 = time.perf_counter()
    h = runner.run(frame, year=2019, reform=spec, tier="full", sample=MENAGES).households
    return _garder("ppa_2019", h, {"commit": j28.commit(), "annee": 2019,
                                   "vieillissement": rec, "menages": MENAGES,
                                   "duree_s": round(time.perf_counter() - t0, 1),
                                   "sens": "gain = revenu_disponible − revenu_disponible_"
                                           "reform (la mesure, moins le miroir)"})


def ir_passe() -> Path:
    """La loi de 2020 (la passe de référence) contre le contrefactuel (la réforme)."""
    from impots.api.schemas import IRBracket, ReformSpec
    from impots.population import runner

    frame, rec = j28.population(2020)
    bareme = [IRBracket(threshold=round(s * INDEXATION_2020), rate=t)
              for s, t in BAREME_2019]
    spec = ReformSpec(ir_bareme=bareme, **{k: round(v * INDEXATION_2020) if k != "decote_taux"
                                           else v for k, v in DECOTE_2019.items()})
    t0 = time.perf_counter()
    h = runner.run(frame, year=2020, reform=spec, tier="full", sample=MENAGES).households
    return _garder("ir_2020", h, {"commit": j28.commit(), "annee": 2020,
                                  "vieillissement": rec, "menages": MENAGES,
                                  "contrefactuel": spec.model_dump(exclude_none=True),
                                  "duree_s": round(time.perf_counter() - t0, 1),
                                  "sens": "gain = revenu_disponible − revenu_disponible_"
                                          "reform (la loi de 2020, moins le contrefactuel)"})


# --------------------------------------------------------------------------- #
# les indicateurs
# --------------------------------------------------------------------------- #
def mesurer(nom: str) -> dict[str, Any]:
    """Sur les ménages de la passe, puis sur les cellules du jumeau."""
    import polars as pl

    from impots.jumeau.cellules import N_DECILES, TYPES, Cellules
    from impots.jumeau.impacts import entente
    from impots.population.aggregate import consumption_units, weighted_decile_index

    h = pl.read_parquet(SORTIE / f"{nom}.parquet")
    w = h["weight"].to_numpy().astype(float)
    wp = w * h["n_persons"].to_numpy().astype(float)
    uc = consumption_units(h["n_aged_14_plus"].to_numpy(),
                           h["n_children_under_14"].to_numpy())
    avec = h["revenu_disponible"].to_numpy().astype(float) / uc
    sans = h["revenu_disponible_reform"].to_numpy().astype(float) / uc
    gain = avec - sans
    # Les déciles des personnes, rang sans la mesure (D-535).
    o = np.argsort(sans, kind="stable")
    cum = np.cumsum(wp[o]) / wp.sum()
    d = np.empty(sans.size, dtype=int)
    d[o] = np.minimum((cum * 10).astype(int), 9)
    gain_nv = np.array([float((gain * wp)[d == k].sum() / wp[d == k].sum())
                        for k in range(10)])
    zeros = np.zeros(sans.size, dtype=int)
    un = np.array([0.5])
    i_avec = entente.indicateurs(avec, wp, zeros, un)
    i_sans = entente.indicateurs(sans, wp, zeros, un)
    pauv_avec = float(wp[avec < i_avec["seuil"]].sum() / wp.sum())
    pauv_sans = float(wp[sans < i_sans["seuil"]].sum() / wp.sum())
    micro = {
        "cout_md": float((gain * uc * w).sum() / 1e9),
        "gain_nv_par_decile": gain_nv.tolist(),
        "parts_deciles": (gain_nv / gain_nv.sum()).tolist(),
        "gain_nv_moyen": float((gain * wp).sum() / wp.sum()),
        "decile_max": int(np.argmax(gain_nv)) + 1,
        "pauvrete_sans": pauv_sans, "pauvrete_avec": pauv_avec,
        "pauvrete_points": 100.0 * (pauv_avec - pauv_sans),
        "gini_points": 100.0 * (i_avec["gini"] - i_sans["gini"]),
        "d9_d1": i_avec["d9_d1"] - i_sans["d9_d1"],
        "mediane_sans": i_sans["mediane"],
    }
    # Les cellules : les chocs par décile des ménages (pondéré ménage, rang sans la mesure,
    # comme les rapports, `aggregate`), ramenés aux euros des cellules par le rapport des
    # médianes, puis la dimension.
    dm = weighted_decile_index(sans, w)
    chocs = np.array([float((gain * uc * w)[dm == k].sum()) for k in range(N_DECILES)])
    cel = Cellules.lire()
    dist = entente.lire() or entente.approchee(cel)
    base = entente.indicateurs(dist.quantiles.reshape(-1), np.repeat(
        cel["personnes"] / dist.rangs.size, dist.rangs.size), None, dist.rangs)
    echelle = base["mediane"] / i_sans["mediane"]
    menages_d = cel.par_decile("menages")
    par_cellule = (chocs * echelle)[cel.deciles] * cel["menages"] / menages_d[cel.deciles]
    resultats = {}
    for nom_dist, dd in (("mesuree", dist), ("approchee", entente.approchee(cel))):
        resultats[nom_dist] = _cellules(cel, dd, par_cellule)
    k = len(TYPES)
    gain_uc_d = (par_cellule.reshape(N_DECILES, k).sum(axis=1)
                 / cel.par_decile("uc") / echelle)
    return {"micro": micro, "cellules": resultats,
            "cellules_gain_uc_par_decile_euros_de_l_annee": gain_uc_d.tolist(),
            "chocs_par_decile_md": (chocs / 1e9).tolist(), "echelle": echelle,
            "distribution": dist.source}


def _cellules(cel: Any, dist: Any, par_cellule: np.ndarray) -> dict[str, float]:
    from impots.jumeau.impacts import entente, pouvoir

    z = np.zeros((1, 50, 1))
    r = pouvoir.Revenus(annees=(0,), menages=cel["menages"], personnes=cel["personnes"],
                        uc=cel["uc"], rd_ref=np.ones((1, 50, 1)),
                        dynamique=(par_cellule / 1e9)[None, :, None], indexation=z,
                        reprise=z, prix=np.zeros((1, 1)), deflateur=np.ones((1, 1)),
                        structurel=False)
    c = entente.calculer_entente(r, cel, dist, 1.0, np.ones((1, 1)))
    return {"pauvrete_points": 100.0 * float(c.variante["pauvrete"][0, 0]
                                             - c.reference["pauvrete"][0, 0]),
            "gini_points": 100.0 * float(c.variante["gini"][0, 0] - c.reference["gini"][0, 0]),
            "d9_d1": float(c.variante["d9_d1"][0, 0] - c.reference["d9_d1"][0, 0]),
            "pauvrete_reference": float(c.reference["pauvrete"][0, 0])}


def rapport() -> Path:
    out = {"decisions": ["D-591", "D-592"], "menages_echantillon": MENAGES}
    for nom in ("ppa_2019", "ir_2020"):
        if (SORTIE / f"{nom}.parquet").exists():
            out[nom] = {**json.loads((SORTIE / f"{nom}.json").read_text()), **mesurer(nom)}
    RAPPORT.mkdir(parents=True, exist_ok=True)
    dest = RAPPORT / "modele.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n",
                    encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1, default=float))
    return dest


if __name__ == "__main__":
    commandes = {"ppa_passe": ppa_passe, "ir_passe": ir_passe, "rapport": rapport}
    if len(sys.argv) != 2 or sys.argv[1] not in commandes:
        sys.exit(f"usage : {sys.argv[0]} {'|'.join(commandes)}")
    print(commandes[sys.argv[1]]())
