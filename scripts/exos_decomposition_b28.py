"""La fin des exonérations au-delà de 2 Smic : la forme contre le facteur de masse (but 28,
volet `exos`, D-560, D-561).

Le rendement de la mesure (`allegement_general_plafond` 3 → 2, droit de 2026, vue figée)
est, personne par personne, la réduction générale qu'elle retire :

    R = Σ_i Σ_mois w_i · f_i · A_im · 1[2 ≤ x_im < 3]

`A_im` la réduction générale du mois (`taux_allegement_general` × `assiette_allegement`),
`x_im` la rémunération du mois en Smic (`assiette_allegement` sur `smic_proratise`) :
openfisca compare chaque mois à son Smic, et le Smic de 2026 change en juin (D-561, D-562 ;
D-560 lisait l'année). `w_i` le poids du ménage (la moyenne de ses membres, comme le
runner agrège), `f_i` l'extrapolation aux salariés hors de l'enquête (1,0747, un pour les
gérants). Écrit
R = F · M · Σ_k s_k · c_k, bandes k = [2 ; 2,5) et [2,5 ; 3) : M la masse de l'assiette
des salariés (pondérée par f), s_k la part de M dans la bande, c_k le taux moyen de la
réduction dans la bande (Σ A / Σ assiette).

    PYTHONPATH=src python scripts/exos_decomposition_b28.py passe <nom> <population>
        [--echelle k] [--complet] [--sans-menages] [--controle]
    PYTHONPATH=src python scripts/exos_decomposition_b28.py analyser

`--echelle k` multiplie les salaires du champ privé (celui du facteur des salaires
horaires, `incomes._private_field`) par k avant la passe : la population de D-553 ramenée
au facteur de D-521 (k = 1,011732 / 1,022156) a la forme de D-553 et le facteur de masse de
D-521. `--complet` : toute la population, par huit lots (sinon les 20 000 ménages du palier
rapide, le tirage des études). `--controle` : la passe de la réforme aussi, pour vérifier
que le rendement est bien la réduction de la bande (sinon, la passe de référence seule).
Sorties hors git (`SORTIE`) ; seuls des agrégats entrent dans `reports/etudes/suite_b28/`.
"""

from __future__ import annotations

import argparse
import gc
import itertools
import json
import os
import sys
import time
import zlib
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SORTIE = Path(os.environ.get(
    "EXOS28_SORTIE",
    "/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/exos28"))
RAPPORT = ROOT / "reports" / "etudes" / "suite_b28" / "exos_decomposition_d561.json"
ANNEE = 2026
LOTS = 8
#: Les bandes de x (Smic de 2026) ; la mesure retire la réduction de [2 ; 3).
BANDES = (0.0, 1.6, 2.0, 2.5, 3.0, 3.5, np.inf)
#: La grille des heures, en Smic horaire de 2024 (la grandeur de la fonction des salaires) :
#: la part des heures sous chaque point, que l'analyse lit aux bornes des bandes de 2026.
GRILLE_HEURES = tuple(round(1.5 + 0.005 * i, 3) for i in range(441))


def _champ_prive(frame: pl.DataFrame) -> np.ndarray:
    from impots.population import incomes

    emp = (frame["is_salarie"].to_numpy().astype(bool)
           & (frame["statut_activite"].to_numpy() == "employed"))
    w = frame["salaire_brut_annuel"].to_numpy().astype(float)
    return incomes._private_field(frame, emp) & (w > 0)


def echelle(frame: pl.DataFrame, k: float) -> pl.DataFrame:
    """Les salaires du champ privé multipliés par k (le facteur des salaires horaires
    s'applique à eux seuls, `incomes._salaires_horaires_en_smic`)."""
    if k == 1.0:
        return frame
    priv = _champ_prive(frame)
    w = frame["salaire_brut_annuel"].to_numpy().astype(float)
    return frame.with_columns(pl.Series("salaire_brut_annuel", np.where(priv, w * k, w)))


def heures(frame: pl.DataFrame) -> dict[str, Any]:
    """Les heures des salariés du privé par bande de salaire horaire en Smic de 2024 (poids
    × quotité × mois travaillés, la mesure de D-552), et leurs déciles."""
    from impots.population import margins

    priv = _champ_prive(frame)
    w = frame["salaire_brut_annuel"].to_numpy().astype(float)[priv]
    q = frame["quotite_travail"].to_numpy().astype(float)[priv]
    mi = frame["mois_travailles"].to_numpy().astype(np.int64)[priv]
    m = np.array([bin(int(v)).count("1") for v in mi], dtype=float)
    p = frame["weight"].to_numpy().astype(float)[priv]
    h = p * q * m / 12.0
    x = w / (margins.SMIC_ANNUEL_2024 * np.maximum(q * m / 12.0, 1e-9))
    tot = float(h.sum())
    o = np.sort(x)
    cum = np.concatenate([[0.0], np.cumsum(h[np.argsort(x)])]) / tot
    sous = cum[np.searchsorted(o, np.asarray(GRILLE_HEURES), side="left")]
    out: dict[str, Any] = {"grille": list(GRILLE_HEURES), "sous": [float(v) for v in sous]}
    o = np.argsort(x)
    c = np.cumsum(h[o])
    c = (c - h[o] / 2) / c[-1]
    out["deciles"] = [float(v) for v in np.interp(np.arange(1, 10) / 10, c, x[o])]
    return out


def preparer(population: str, k: float, menages: bool, sample: int | None
             ) -> pl.DataFrame:
    from impots.population import menages as menages_module
    from impots.population.runner import subsample

    frame = echelle(pl.read_parquet(population), k)
    if sample is not None:
        frame = subsample(frame, sample)
    frame = frame.sort("person_id")
    if menages:
        frame, _ = menages_module.impute(frame, ANNEE, facteurs={"wage": 1.0, "price": 1.0})
    return frame


def calculer(frame: pl.DataFrame, controle: bool) -> dict[str, np.ndarray]:
    """Par personne et par mois (D-562) : la réduction du mois (`taux_allegement_general`
    × `assiette_allegement`, ce qu'openfisca somme sur l'année quel que soit le mode de
    recouvrement), son assiette et son x du mois ; le poids, celui du ménage (la moyenne
    de ses membres, comme le runner agrège) ; f, l'extrapolation."""
    from impots.api.schemas import ReformSpec
    from impots.engine.system import baseline, reformed_for
    from impots.population import margins
    from impots.population.to_openfisca import build_simulation

    built = build_simulation(frame, baseline(), ANNEE)
    a = np.abs(np.asarray(built.calculate("allegement_general", add=True), dtype=float))
    taux, base, x = [], [], []
    for m in range(1, 13):
        t = np.asarray(built.calculate("taux_allegement_general", month=m), dtype=float)
        b = np.asarray(built.calculate("assiette_allegement", month=m), dtype=float)
        s = np.asarray(built.calculate("smic_proratise", month=m), dtype=float)
        taux.append(t)
        base.append(b)
        x.append(np.where(s > 0, b / np.maximum(s, 1e-9), 0.0))
    del built
    gc.collect()
    taux_m, base_m, x_m = (np.stack(v, axis=1) for v in (taux, base, x))
    brut = (taux_m * base_m).sum(axis=1)
    # Les stagiaires, les apprentis, les exonérations non cumulables : ce qu'openfisca
    # retire du produit, personne par personne.
    garde = np.where(brut > 0, a / np.maximum(brut, 1e-9), 0.0)
    out = {"a": a, "a_m": taux_m * base_m * garde[:, None], "assiette_m": base_m, "x_m": x_m,
           "x": np.where(base_m.sum(axis=1) > 0, base_m.sum(axis=1) / np.maximum(
               (base_m / np.maximum(x_m, 1e-9)).sum(axis=1), 1e-9), 0.0)}
    if controle:
        r = build_simulation(frame, reformed_for(ReformSpec(allegement_general_plafond=2.0),
                                                 ANNEE), ANNEE)
        out["a_reforme"] = np.abs(np.asarray(r.calculate("allegement_general", add=True),
                                             dtype=float))
        del r
        gc.collect()
    gerant = (frame["regime_non_salarie"].is_in(["gerant_bic", "gerant_bnc"])
              .fill_null(False).to_numpy())
    out["f"] = np.where(gerant, 1.0, margins.EXTRAPOLATION_SALARIES.value)
    hw = frame.select(pl.col("weight").mean().over("household_id"))["weight"]
    out["w"] = hw.to_numpy().astype(float)
    return out


def passe(nom: str, population: str, k: float, complet: bool, menages: bool,
          controle: bool) -> Path:
    from impots.api.schemas import QUICK_TIER_HOUSEHOLDS

    dest = SORTIE / f"{nom}.json"
    if dest.exists():
        print(f"déjà fait : {dest}", flush=True)
        return dest
    t0 = time.perf_counter()
    frame = preparer(population, k, menages, None if complet else QUICK_TIER_HOUSEHOLDS)
    if complet:
        lot = frame["household_id"].map_elements(
            lambda h: zlib.crc32(str(h).encode()) % LOTS, return_dtype=pl.Int64)
        parts = [calculer(frame.filter(lot == i), controle) for i in range(LOTS)]
        v = {c: np.concatenate([p[c] for p in parts]) for c in parts[0]}
    else:
        v = calculer(frame, controle)
    pf = v["w"] * v["f"]
    pfm = pf[:, None] * np.ones((1, 12))
    xm = v["x_m"]
    dans = (xm >= 2.0) & (xm < 3.0)
    xa = v["x"]
    out: dict[str, Any] = {
        "nom": nom, "population": population, "echelle": k, "complet": complet,
        "menages": menages, "annee": ANNEE, "menages_echantillon": int(
            frame["household_id"].n_unique()),
        "methode": "D-562 : x du mois, poids du ménage",
        "rendement": float((pfm * v["a_m"] * dans).sum()),
        "rendement_x_annuel": float((pf * v["a"] * ((xa >= 2.0) & (xa < 3.0))).sum()),
        "masse_assiette": float((pfm * v["assiette_m"]).sum()),
        "reduction_totale": float((pf * v["a"]).sum()),
        "reduction_totale_mois": float((pfm * v["a_m"]).sum()),
        "bandes": {},
    }
    if controle:
        out["rendement_controle"] = float((pf * (v["a"] - v["a_reforme"])).sum())
    for lo, hi in itertools.pairwise(BANDES):
        m = (xm >= lo) & (xm < hi) & (v["assiette_m"] > 0)
        out["bandes"][f"{lo}-{hi}"] = {
            "masse": float((pfm * v["assiette_m"])[m].sum()),
            "reduction": float((pfm * v["a_m"])[m].sum()),
            "personnes_mois": float((v["w"][:, None] * m).sum() / 12.0),
        }
    out["heures"] = heures(frame)
    out["duree_s"] = round(time.perf_counter() - t0, 1)
    SORTIE.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{nom} : R {out['rendement'] / 1e9:.3f} Md€ (contrôle "
          f"{out.get('rendement_controle', float('nan')) / 1e9:.3f}) en {out['duree_s']} s",
          flush=True)
    return dest


# --------------------------------------------------------------------------- #
# l'analyse (aucune passe)
# --------------------------------------------------------------------------- #
MD = 1e9
A, B = "2.0-2.5", "2.5-3.0"


def termes(p: dict[str, Any]) -> dict[str, float]:
    """M, s_a, s_b, c_a, c_b et R de la formule (M en Md€ d'assiette, F inclus)."""
    b = p["bandes"]
    m = p["masse_assiette"]
    t = {"M": m / MD, "R": p["rendement"] / MD}
    for k, n in ((A, "a"), (B, "b")):
        t[f"s_{n}"] = b[k]["masse"] / m
        t[f"c_{n}"] = b[k]["reduction"] / b[k]["masse"]
    return t


def decomposer(x: dict[str, float], y: dict[str, float]) -> dict[str, float]:
    """R(y) − R(x) en Md€ par terme : la masse M (log), puis la forme, partagée entre
    les parts et les taux des deux bandes au prorata de leur log (indice de Montgomery,
    exact : les parts somment l'écart)."""
    def lm(a: float, b: float) -> float:
        return (a - b) / np.log(a / b) if a != b else a

    out: dict[str, float] = {}
    for n in ("a", "b"):
        ry = y["M"] * y[f"s_{n}"] * y[f"c_{n}"]
        rx = x["M"] * x[f"s_{n}"] * x[f"c_{n}"]
        w = lm(ry, rx)
        out[f"M_{n}"] = w * np.log(y["M"] / x["M"])
        out[f"s_{n}"] = w * np.log(y[f"s_{n}"] / x[f"s_{n}"])
        out[f"c_{n}"] = w * np.log(y[f"c_{n}"] / x[f"c_{n}"])
    out["M"] = out.pop("M_a") + out.pop("M_b")
    out["total"] = sum(out.values())
    out["ecart_R"] = y["R"] - x["R"]
    return {k: round(float(v), 4) for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("passe")
    p.add_argument("nom")
    p.add_argument("population")
    p.add_argument("--echelle", type=float, default=1.0)
    p.add_argument("--complet", action="store_true")
    p.add_argument("--sans-menages", action="store_true")
    p.add_argument("--controle", action="store_true")
    sub.add_parser("analyser")
    a = ap.parse_args()
    if a.cmd == "passe":
        passe(a.nom, a.population, a.echelle, a.complet, not a.sans_menages, a.controle)
        return 0
    lus = {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in SORTIE.glob("*.json")}
    t = {n: termes(v) for n, v in lus.items()}
    print(json.dumps(t, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
