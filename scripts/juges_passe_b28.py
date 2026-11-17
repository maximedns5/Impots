"""Les juges du passé de la réaction (but 28, volet `passe`, D-535 à D-539).

Deux mesures passées rejouées, préenregistrées dans D-535 avant tout calcul :

* le CICE de 2013 à 2017 : le crédit d'une année de salaires calculé par openfisca sur la
  population de D-521 ramenée à 2014 (indices constatés de l'Insee, D-362), porté aux
  autres années au taux de la loi et à la masse des rémunérations publiée ; puis le jumeau
  structurel depuis l'état publié de 2012 (`rejeu_histoire.simulateur`), la mesure seule ;
* la revalorisation exceptionnelle de la prime d'activité de 2019 (la bonification
  individuelle, décret n° 2018-1197) : la loi de 2019 contre la même loi à la
  bonification de 2018 (miroir, D-298), sur la population ramenée à 2019 ; le recours en
  espérance (`population.recours`), les déciles ; le jumeau depuis l'état de 2018, sans
  juge.

    PYTHONPATH=src python scripts/juges_passe_b28.py cice_passe|ppa_passe|jumeau|rapport

Les sorties détaillées vont hors git (`JUGES28_SORTIE`) ; `rapport` écrit les agrégats
dans `reports/verification/juges_passe_b28/`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SORTIE = Path(os.environ.get(
    "JUGES28_SORTIE",
    "/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/passe28"))
RAPPORT = ROOT / "reports" / "verification" / "juges_passe_b28"
POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"
JEU, BASE = "insee_constate", 2024
MENAGES = 20_000
#: Le taux du CICE par année de salaires (CGI, art. 244 quater C) : 4 % en 2013, 6 % de
#: 2014 à 2016, 7 % en 2017 ; assiette, les rémunérations jusqu'à 2,5 Smic.
TAUX_CICE = {2013: 0.04, 2014: 0.06, 2015: 0.06, 2016: 0.06, 2017: 0.07}
ANNEE_CICE = 2014
#: La bonification de la prime d'activité avant le décret n° 2018-1197 (openfisca-france,
#: `ppa.pa_m.bonification`, valeurs de 2016) : le miroir.
BONIF_2018 = {"taux_bonification_max": 0.12782, "seuil_max_bonification": 95}
PLAFOND_CIBLE = 1.6
EURO = 1e9


def commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def population(annee: int) -> tuple[Any, dict[str, Any]]:
    import polars as pl

    from impots import hypotheses
    from impots import uprating as up

    u, rec = hypotheses.vieillissement_menages(JEU, BASE, annee)
    return up.uprate(pl.read_parquet(POPULATION), annee, u), rec


def ecrire(nom: str, out: dict[str, Any]) -> Path:
    SORTIE.mkdir(parents=True, exist_ok=True)
    dest = SORTIE / f"{nom}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n",
                    encoding="utf-8")
    print(dest, flush=True)
    return dest


# --------------------------------------------------------------------------- #
# le CICE : la passe
# --------------------------------------------------------------------------- #
def cice_passe() -> Path:
    from impots.engine.system import baseline
    from impots.population.runner import subsample
    from impots.population.to_openfisca import build_simulation

    frame, rec = population(ANNEE_CICE)
    frame = subsample(frame, MENAGES).sort("person_id")
    t0 = time.perf_counter()
    b = build_simulation(frame, baseline(), ANNEE_CICE)
    cice = b.calculate("credit_impot_competitivite_emploi", add=True).astype(float)
    assiette = b.calculate("assiette_allegement", add=True).astype(float)
    smic = b.calculate("smic_proratise", add=True).astype(float)
    w = frame["weight"].to_numpy().astype(float)
    x = np.divide(assiette, smic, out=np.full_like(assiette, np.inf), where=smic > 0)
    cible = x <= PLAFOND_CIBLE
    out = {
        "commit": commit(), "annee": ANNEE_CICE, "vieillissement": rec,
        "menages_echantillon": MENAGES, "duree_s": round(time.perf_counter() - t0, 1),
        "cice_md": float((cice * w).sum()) / EURO,
        "cice_cible_md": float((cice * w * cible).sum()) / EURO,
        "assiette_md": float((assiette * w).sum()) / EURO,
        "assiette_sous_2_5_md": float((assiette * w * (x <= 2.5)).sum()) / EURO,
        "beneficiaires": float((w * (cice > 0)).sum()),
    }
    return ecrire("cice_passe", out)


# --------------------------------------------------------------------------- #
# la prime d'activité de 2019 : la passe
# --------------------------------------------------------------------------- #
def _miroir_reformed_for(orig: Any) -> Any:
    from openfisca_core import periods
    from openfisca_core.reforms import Reform

    def reformed_for(spec: Any, year: int) -> Any:
        system = orig(spec, year)

        class Miroir(Reform):
            def apply(self) -> None:
                def modifier(p: Any) -> Any:
                    node = (p.prestations_sociales.solidarite_insertion.minima_sociaux.ppa
                            .pa_m.bonification)
                    for cle, valeur in BONIF_2018.items():
                        getattr(node, cle).update(
                            start=periods.instant(f"{year - 1}-01-01"),
                            stop=periods.instant(f"{year + 1}-12-31"), value=valeur)
                    return p
                self.modify_parameters(modifier_function=modifier)
        return Miroir(system)
    return reformed_for


def _nv_deciles(h: Any, rd: np.ndarray) -> np.ndarray:
    """Le décile de niveau de vie de chaque ménage, pondéré personne."""
    uc = (1.0 + 0.5 * np.maximum(h["n_aged_14_plus"].to_numpy() - 1, 0)
          + 0.3 * h["n_children_under_14"].to_numpy())
    nv = rd / uc
    wp = h["weight"].to_numpy() * h["n_persons"].to_numpy()
    o = np.argsort(nv, kind="stable")
    cum = np.cumsum(wp[o]) / wp.sum()
    d = np.empty(len(nv), dtype=int)
    d[o] = np.minimum((cum * 10).astype(int), 9)
    return d


def ppa_passe() -> Path:
    from impots.api.schemas import ReformSpec
    from impots.population import aggregate as agg_mod
    from impots.population import runner

    frame, rec = population(2019)
    runner.reformed_for = _miroir_reformed_for(runner.reformed_for)
    spec = ReformSpec(ppa_bonification_taux_max=BONIF_2018["taux_bonification_max"])
    t0 = time.perf_counter()
    h = runner.run(frame, year=2019, reform=spec, tier="full", sample=MENAGES).households
    duree = time.perf_counter() - t0
    agg = agg_mod.aggregate(h)
    w = h["weight"].to_numpy().astype(float)

    def tot(c: str) -> float:
        return float((h[c].to_numpy() * w).sum())

    # « avec » : la loi de 2019 (la mesure) ; « sans » : le miroir (la bonification de
    # 2018). Le gain de la mesure = avec − sans.
    cols = sorted(c for c in h.columns if "ppa" in c and not c.endswith("_reform"))
    totaux = {c: {"avec": tot(c), "sans": tot(f"{c}_reform")} for c in cols
              if f"{c}_reform" in h.columns}
    gain = (h["revenu_disponible"] - h["revenu_disponible_reform"]).to_numpy()
    d = _nv_deciles(h, h["revenu_disponible_reform"].to_numpy())
    par_decile = []
    for k in range(10):
        s = d == k
        par_decile.append({"decile": k + 1, "gain_md": float((gain * w * s).sum()) / EURO,
                           "menages": float(w[s].sum()),
                           "gain_moyen_menage": float((gain * w * s).sum() / w[s].sum())})
    total = sum(x["gain_md"] for x in par_decile)
    for x in par_decile:
        x["part"] = x["gain_md"] / total
    out = {
        "commit": commit(), "annee": 2019, "vieillissement": rec,
        "menages_echantillon": MENAGES, "duree_s": round(duree, 1),
        "reform_cost_miroir_md": agg.reform_cost / EURO,
        "cout_mesure_md": -agg.reform_cost / EURO,
        "totaux": totaux, "deciles": par_decile, "gain_total_md": total,
        "gagnants": float(w[gain > 1.0].sum()), "perdants": float(w[gain < -1.0].sum()),
        "counts": {k: v for k, v in agg.counts.items() if "ppa" in k},
    }
    return ecrire("ppa_passe", out)


# --------------------------------------------------------------------------- #
# le jumeau
# --------------------------------------------------------------------------- #
def _simuler(fenetre: Any, mesures: list[Any], theta: dict[str, float]) -> Any:
    from impots.jumeau import rejeu_histoire as rh
    from impots.jumeau.blocs.entreprises import population_depuis
    from impots.jumeau.cellules import Cellules

    orig = rh.chocs_observes
    rh.chocs_observes = lambda *a, **k: list(mesures)
    try:
        sim = rh.simulateur(population=population_depuis(), cellules=Cellules.lire(),
                            exogenes=rh.exogenes_publies(), observateur=rh.etat_publie,
                            votees=[])
        return sim(fenetre, theta)
    finally:
        rh.chocs_observes = orig


def _effet(fenetre: Any, m: Any, theta: dict[str, float]) -> dict[str, list[float]]:
    """La variante avec la mesure moins la variante sans : la mesure seule (la demande
    mondiale observée est dans les deux)."""
    a, b = _simuler(fenetre, [m], theta), _simuler(fenetre, [], theta)
    out: dict[str, list[float]] = {}
    for c in ("emploi_salarie", "emploi_total", "salaire_moyen", "pib", "b9", "c_menages",
              "remunerations", "chomage"):
        if a.variante[0].present(c):
            out[c] = [float(np.asarray(x[c]).reshape(-1)[0]
                            - np.asarray(y[c]).reshape(-1)[0])
                      for x, y in zip(a.variante, b.variante, strict=True)]
    out["annees"] = list(fenetre.annees)
    return out


def _thetas() -> dict[str, float]:
    from impots.jumeau import thetas

    return {k: 0.5 for k in thetas.REGISTRE}


def mesure_cice() -> tuple[Any, dict[str, Any]]:
    from impots.jumeau import rejeu_histoire as rh
    from impots.jumeau.mesures import HYPOTHESE, Mesure

    p = json.loads((SORTIE / "cice_passe.json").read_text(encoding="utf-8"))
    d1 = {a: float(np.asarray(rh.etat_publie(a)["remunerations"]).reshape(-1)[0])
          for a in (ANNEE_CICE, *TAUX_CICE)}
    part_cible = p["cice_cible_md"] / p["cice_md"]
    credit = {a: p["cice_md"] * TAUX_CICE[a] / TAUX_CICE[ANNEE_CICE] * d1[a] / d1[ANNEE_CICE]
              for a in TAUX_CICE}
    annees = tuple(TAUX_CICE)
    m = Mesure(
        identifiant="cice_2013_2017", libelle="CICE, années de salaires 2013 à 2017",
        auteur="LFR 2012 (loi n° 2012-1510), art. 66", origine=HYPOTHESE, annees=annees,
        chocs={a: {"apu_d_d3": credit[a]} for a in annees},
        impulsions={a: {"cotisations_employeurs_ciblees": credit[a] * part_cible,
                        "cotisations_employeurs": credit[a] * (1 - part_cible)}
                    for a in annees},
        entreprises={a: {"cotisations_employeurs": -credit[a]} for a in annees})
    return m, {"credit_md": credit, "part_cible": part_cible, "d1": d1}


def mesure_ppa() -> tuple[Any, dict[str, Any]]:
    from impots.jumeau.mesures import HYPOTHESE, Mesure

    p = json.loads((SORTIE / "ppa_passe.json").read_text(encoding="utf-8"))
    cout = p["cout_mesure_md"]
    deciles = [x["gain_md"] for x in p["deciles"]]
    m = Mesure(identifiant="ppa_2019", libelle="Prime d'activité, bonification de 2019",
               auteur="décret n° 2018-1197", origine=HYPOTHESE, annees=(2019,),
               chocs={2019: {"apu_d_d62": cout}},
               menages={2019: {"deciles": deciles}})
    return m, {"cout_md": cout, "deciles_md": deciles}


def jumeau() -> Path:
    from impots.jumeau.apprentissage import Fenetre

    out: dict[str, Any] = {"commit": commit()}
    m, info = mesure_cice()
    f = Fenetre(2012, 2017, tuple(TAUX_CICE))
    base = _thetas()
    out["cice"] = {"entree": info, "theta_demi": _effet(f, m, base), "sensibilites": {}}
    for cle in ("travail_incidence", "jumeau_emploi_elasticite_cout",
                "jumeau_salaires_chomage", "multiplicateur_macro"):
        for t in (0.0, 1.0):
            if cle in base:
                out["cice"]["sensibilites"][f"{cle}={t}"] = _effet(f, m, {**base, cle: t})
    mp, infop = mesure_ppa()
    fp = Fenetre(2018, 2019, (2019,))
    try:
        out["ppa"] = {"entree": infop, "theta_demi": _effet(fp, mp, base)}
    except Exception as err:  # dit, pas masqué
        out["ppa"] = {"entree": infop, "refus": f"{type(err).__name__}: {err}"}
    return ecrire("jumeau", out)


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"cice_passe": cice_passe, "ppa_passe": ppa_passe, "jumeau": jumeau}[cmd]()
