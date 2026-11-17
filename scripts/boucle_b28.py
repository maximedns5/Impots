"""La boucle population ↔ jumeau (but 28, volet `boucle`, D-545 à D-549).

    PYTHONPATH=src python scripts/boucle_b28.py passe cice|smic   # OpenFisca, détachée
    PYTHONPATH=src python scripts/boucle_b28.py jumeau [pronostic] # le jumeau, en secondes

`passe` : sur le sous-échantillon de 20 000 ménages des études, chaque chômeur de 15 à 64
ans devient salarié dans une copie de son ménage (`jumeau.boucle.variantes`) ; les deux
paires de chômeurs d'un même ménage passent aussi ensemble (le terme d'ordre s²) ; une
passe OpenFisca, tier « full », calcule le tout ; les coefficients par personne-année en
sortent. Le CICE : la population ramenée à 2014 (D-535), la loi de 2014. Le Smic de
Mélenchon : la vue figée de 2026, la loi de la réforme (le monde où les emplois du jumeau
existent), comme la passe de D-508.

`jumeau` : le CICE de D-536 (`juges_passe_b28`) et le Smic de D-534 (`reaction_diffusion_b28`)
avec et sans la boucle, l'itération de la boucle pas à pas (`emploi_impose`), et le
pronostic (`pronostic`, des coefficients écrits à la main dans D-545).

Sorties hors git (`BOUCLE28_SORTIE`).
"""

from __future__ import annotations

import dataclasses
import importlib.util
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
ICI = Path(__file__).resolve().parent
SORTIE = Path(os.environ.get(
    "BOUCLE28_SORTIE",
    "/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f/scratchpad/boucle28"))
MENAGES = int(os.environ.get("BOUCLE28_MENAGES", "20000"))
CLE_SMIC = "pres2027_melenchon_smic_1700_net"
ANNEE_CICE = 2019
FIN = {"financement_a16_part_cnav": 0.5, "financement_compensation": 0.5}
#: Le pronostic de D-545 : les coefficients par personne-année, en part du super-brut
#: moyen par salarié de la passe, estimés à la main sur la population (sans OpenFisca).
PRONOSTIC = {"super_brut": 0.70, "d61": 0.21, "d5": 0.055, "chomage": -0.33,
             "prestations": -0.005, "rd": 0.105}


def _module(nom: str) -> Any:
    spec = importlib.util.spec_from_file_location(nom, ICI / f"{nom}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def ecrire(nom: str, out: dict[str, Any]) -> Path:
    SORTIE.mkdir(parents=True, exist_ok=True)
    dest = SORTIE / f"{nom}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n",
                    encoding="utf-8")
    print(dest, flush=True)
    return dest


# --------------------------------------------------------------------------- #
# la passe
# --------------------------------------------------------------------------- #
def paires(frame: Any, v: Any, liens: Any) -> tuple[Any, list[tuple[str, str, str, str]]]:
    """Les ménages où deux chômeurs passent ensemble : pour chaque ménage d'origine qui en
    a au moins deux, les deux premiers. Rend les ménages et (paire, origine, a, b)."""
    import polars as pl

    from impots.jumeau import boucle

    par = {}
    for hv, ho in zip(liens["household_id"].to_list(), liens["origine"].to_list(),
                      strict=True):
        par.setdefault(ho, []).append(hv)
    morceaux, out = [], []
    sal = dict(zip(liens["household_id"].to_list(), liens["salaire_brut"].to_list(),
                   strict=True))
    for ho, hvs in par.items():
        if len(hvs) < 2:
            continue
        a, b = hvs[:2]
        pid_b = int(b.removeprefix(boucle.PREFIXE).split(":")[0])
        va = v.filter(pl.col("household_id") == a)
        # la personne b dans la variante de a : même rang dans le ménage
        orig = frame.filter(pl.col("household_id") == ho).sort("person_id")
        rang = orig["person_id"].to_list().index(pid_b)
        nouvelle = va.sort("person_id")["person_id"].to_list()[rang]
        tag = "P28:"
        lui = pl.col("person_id") == nouvelle
        morceaux.append(va.with_columns(
            (pl.lit(tag) + pl.col("household_id")).alias("household_id"),
            (pl.lit(tag) + pl.col("foyer_id")).alias("foyer_id"),
            (pl.lit(tag) + pl.col("famille_id")).alias("famille_id"),
            (pl.col("person_id") + 10**12).alias("person_id"),
            pl.when(lui).then(pl.lit("employed")).otherwise(pl.col("statut_activite"))
            .alias("statut_activite"),
            pl.when(lui).then(pl.lit(True)).otherwise(pl.col("is_salarie"))
            .alias("is_salarie"),
            pl.when(lui).then(pl.lit(float(sal[b]))).otherwise(pl.col("salaire_brut_annuel"))
            .alias("salaire_brut_annuel"),
            pl.when(lui).then(pl.lit(0.0)).otherwise(pl.col("chomage_annuel"))
            .alias("chomage_annuel"),
            pl.when(lui).then(pl.lit(0xFFF, dtype=pl.Int64))
            .otherwise(pl.col("mois_travailles")).alias("mois_travailles")))
        out.append((f"{tag}{a}", ho, a, b))
    return (pl.concat(morceaux) if morceaux else v.head(0)), out


def passe(cas: str) -> Path:
    import polars as pl

    from impots.jumeau import boucle
    from impots.population import runner

    if cas == "cice":
        jp = _module("juges_passe_b28")
        # La loi de 2014 (l'année de la passe du CICE, D-535) ne passe pas le tier « full »
        # (l'IFI, lu sur l'année et la précédente) : la loi la plus ancienne qu'il calcule,
        # 2019, sur la population ramenée à 2019, avec la bonification de la prime
        # d'activité d'avant le décret n° 2018-1197 (le miroir de D-535) : les transferts
        # de 2016 à 2018. Le RSA activité et la PPE de 2013 à 2015 n'y sont pas (dit).
        from impots.api.schemas import ReformSpec

        annee = ANNEE_CICE
        frame, rec = jp.population(annee)
        runner.reformed_for = jp._miroir_reformed_for(runner.reformed_for)
        kw: dict[str, Any] = {"year": annee, "tier": "full", "reform": ReformSpec(
            ppa_bonification_taux_max=jp.BONIF_2018["taux_bonification_max"])}
        suffixe = "_reform"
    elif cas == "smic":
        from impots import service
        from impots.api.schemas import ReformSpec
        from impots.population import imputations as imp

        mm = _module("mesure_melenchon_b27")
        annee = mm.ANNEE
        reform = ReformSpec(**mm.reunir(["smic"]))
        im = imp.imputations(reform, annee, demandees=[], chemin="le volet boucle")
        kw = dict(year=annee, reform=reform, tier="full", **im.runner(),
                  annee_consommation=int(service.POPULATION_VINTAGE))
        frame, rec = service.population_frame(), {"vue": "figee", "imputations":
                                                    list(im.noms())}
        suffixe = "_reform"
    else:
        raise SystemExit(f"cas « {cas} »")
    sous = runner.subsample(frame, MENAGES).sort("person_id")
    # les taux mensuels tirés sur toute la population (les donneurs), lus pour l'échantillon
    taux = dict(zip(frame["person_id"].to_list(), boucle.taux_mensuels(frame).tolist(),
                    strict=True))
    v, liens = boucle.variantes(sous, taux=taux)
    pv, lp = paires(sous, v, liens)
    # Les variantes pèsent un millionième de leur ménage dans la passe : aucun total de la
    # passe (un garde-fou, une imputation calée) ne les voit ; les coefficients lisent le
    # poids des ménages d'origine.
    v = v.with_columns(pl.col("weight") * 1e-6)
    pv = pv.with_columns(pl.col("weight") * 1e-6)
    tout = pl.concat([sous, v, pv], how="vertical_relaxed").sort("person_id")
    t0 = time.perf_counter()
    res = runner.run(tout, sample=None, **kw)
    duree = time.perf_counter() - t0
    h = res.households
    ids = set(sous["household_id"].unique().to_list())
    orig = h.filter(pl.col("household_id").is_in(list(ids)))
    var = h.filter(pl.col("household_id").str.starts_with(boucle.PREFIXE))
    # W : le super-brut moyen par salarié de la passe (comme β dans le jumeau)
    sb = boucle.grandeurs_menage(orig, suffixe)["super_brut"]
    w = orig["weight"].to_numpy().astype(float)
    salaries = float(sous.filter((pl.col("statut_activite") == "employed")
                                 & pl.col("is_salarie"))["weight"].sum())
    salaire_moyen = float((sb * w).sum()) / salaries
    cellule = boucle.cellules_de(orig, sous)
    poids = dict(zip(orig["household_id"].to_list(), w.tolist(), strict=True))
    coef = boucle.coefficients(orig, var, liens, cellule, salaire_moyen, poids,
                               suffixe=suffixe, annee=annee,
                               meta={"cas": cas, "commit": commit()})
    # le terme d'ordre s² : X(a et b) − X(a) − X(b) + X(aucun), par grandeur
    g_o = {k: dict(zip(orig["household_id"].to_list(), x.tolist(), strict=True))
           for k, x in boucle.grandeurs_menage(orig, suffixe).items()}
    g_v = {k: dict(zip(var["household_id"].to_list(), x.tolist(), strict=True))
           for k, x in boucle.grandeurs_menage(var, suffixe).items()}
    hp = h.filter(pl.col("household_id").str.starts_with("P28:"))
    g_p = {k: dict(zip(hp["household_id"].to_list(), x.tolist(), strict=True))
           for k, x in boucle.grandeurs_menage(hp, suffixe).items()}
    s2 = {}
    for k in boucle.GRANDEURS:
        inter = sum(poids[o] * (g_p[k][p] - g_v[k][a] - g_v[k][b] + g_o[k][o])
                    for p, o, a, b in lp)
        seuls = sum(poids[o] * (g_v[k][a] + g_v[k][b] - 2 * g_o[k][o]) for p, o, a, b in lp)
        s2[k] = {"interaction_md": inter / 1e9, "seuls_md": seuls / 1e9}
    tous = float((np.array([poids[o] for o in liens["origine"].to_list()])).sum())
    out = {
        "cas": cas, "commit": commit(), "annee": annee, "vieillissement": rec,
        "menages_echantillon": MENAGES, "duree_s": round(duree, 1),
        "variantes": v["household_id"].n_unique(), "paires": len(lp),
        "chomeurs_ponderes": tous,
        "chomeurs_en_paire_ponderes": float(sum(2 * poids[o] for _, o, _, _ in lp)),
        "coefficients": {k: getattr(coef, k) for k in
                         ("super_brut", "d61", "d5", "chomage", "prestations", "rd")},
        "rd_cellules": coef.rd_cellules.tolist(), "meta": dict(coef.meta),
        "par_personne_annee_eur": {k: getattr(coef, k) * salaire_moyen for k in
                                   ("super_brut", "d61", "d5", "chomage", "prestations",
                                    "rd")},
        "ordre_deux": s2,
    }
    # le détail des prestations, pour le dire
    from impots.jumeau.cellules import PRESTATIONS
    det = {}
    an = liens["annees"].to_numpy().astype(float)
    wl = np.array([poids[o] for o in liens["origine"].to_list()])
    for c in PRESTATIONS:
        col = f"{c}{suffixe}" if f"{c}{suffixe}" in h.columns else c
        if col not in h.columns:
            continue
        do = dict(zip(orig["household_id"].to_list(), orig[col].to_list(), strict=True))
        dv = dict(zip(var["household_id"].to_list(), var[col].to_list(), strict=True))
        d = np.array([dv[a] - do[b] for a, b in zip(liens["household_id"].to_list(),
                                                     liens["origine"].to_list(), strict=True)])
        det[c] = float((wl * d).sum() / (wl * an).sum())
    out["prestations_eur_par_personne_annee"] = det
    return ecrire(f"passe_{cas}" + ("" if MENAGES == 20_000 else f"_{MENAGES}"), out)


# --------------------------------------------------------------------------- #
# le jumeau
# --------------------------------------------------------------------------- #
def lire_coef(cas: str) -> Any:
    from impots.jumeau import boucle

    p = json.loads((SORTIE / f"passe_{cas}.json").read_text(encoding="utf-8"))
    return boucle.Coefficients(**p["coefficients"], rd_cellules=np.array(p["rd_cellules"]),
                               annee=p["annee"], meta=p["meta"])


def coef_pronostic(st: Any) -> Any:
    """Les coefficients du pronostic, la répartition du revenu comme le forfait."""
    from impots.jumeau import boucle

    f = boucle.forfait(st)
    part = np.asarray(st.part_chomeurs, dtype=float)
    return dataclasses.replace(f, **{k: v for k, v in PRONOSTIC.items() if k != "rd"},
                               rd=PRONOSTIC["rd"], rd_cellules=PRONOSTIC["rd"] * part,
                               meta={"pronostic": True})


def _structure() -> Any:
    from impots.jumeau.blocs.menages import charger, structure
    from impots.jumeau.cellules import Cellules

    return structure(Cellules.lire(), charger().pib_cellules)


def _champs(traj: Any) -> dict[str, list[float]]:
    out = {}
    for c in ("emploi_salarie", "emploi_total", "c_menages", "b9", "remunerations",
              "apu_r_d61", "apu_r_d5", "apu_r_d2", "apu_d_d62", "pib"):
        if traj.variante[0].present(c):
            out[c] = [round(float(x), 4) for x in traj.difference(c)[:, 0]]
    if traj.variante[0].present("ratio_dette"):
        out["dette_pts"] = [round(100 * float(x), 4)
                            for x in traj.difference("ratio_dette")[:, 0]]
    out["annees"] = list(traj.annees)
    return out


def _emploi_marchand(traj: Any) -> dict[int, float]:
    e = traj.difference("emploi_salarie")[:, 0]
    if traj.variante[0].present("emploi_public"):
        e = e - traj.difference("emploi_public")[:, 0]
    return {a: float(x) for a, x in zip(traj.annees, e, strict=True)}


def iterer(calcul: Any, coef: Any, n: int = 8) -> list[dict[str, Any]]:
    """La boucle pas à pas : l'emploi de l'itération d'avant imposé à la correction."""
    traj = calcul(None)
    e = _emploi_marchand(traj)
    suite = [{"iteration": 0, "emploi": e, "b9": [float(x) for x in
                                                  traj.difference("b9")[:, 0]]}]
    for i in range(1, n + 1):
        traj = calcul(dataclasses.replace(coef, emploi_impose=e))
        e2 = _emploi_marchand(traj)
        ecart = max(abs(e2[a] - e[a]) for a in e)
        suite.append({"iteration": i, "emploi": e2, "ecart_max_milliers": ecart,
                      "b9": [float(x) for x in traj.difference("b9")[:, 0]]})
        e = e2
        if ecart < 1e-6:
            break
    return suite


def cice(coef: Any | None, theta: dict[str, float] | None = None) -> Any:
    from impots.jumeau.apprentissage import Fenetre

    jp = _module("juges_passe_b28")
    jp.SORTIE = Path("/tmp/claude-0/-home-user-Impots/8c1eda0e-eb4f-5530-a9a9-deab4a4ca18f"
                     "/scratchpad/passe28")
    m, _ = jp.mesure_cice()
    if coef is not None:
        m = dataclasses.replace(m, boucle=coef)
    f = Fenetre(2012, 2017, tuple(jp.TAUX_CICE))
    th = theta or jp._thetas()
    a, b = jp._simuler(f, [m], th), jp._simuler(f, [], th)

    class Diff:  # la variante avec la mesure moins celle sans, comme `_effet`
        annees = tuple(f.annees)
        variante = a.variante

        @staticmethod
        def difference(c: str) -> np.ndarray:
            return np.array([np.asarray(x[c]).reshape(-1) - np.asarray(y[c]).reshape(-1)
                             for x, y in zip(a.variante, b.variante, strict=True)])
    return Diff


def smic_session() -> Any:
    mm = _module("mesure_melenchon_b27")
    S = mm.session()
    mm.redimensionner(S, CLE_SMIC, mm.lire("complet_propres_smic"))
    return S


def smic(S: Any, coef: Any | None, diffusion: float = 0.5) -> Any:
    from impots.jumeau import papillon as pa

    m = S.mesure_structurel(CLE_SMIC, "figee", "parts_premiere_annee")
    if coef is not None:
        m = dataclasses.replace(m, boucle=coef)
    tr, _ = pa.trajectoire(S, [m], cle=CLE_SMIC,
                           theta={**FIN, "travail_smic_diffusion": diffusion})
    return tr


def jumeau(mode: str = "passes") -> Path:
    st = _structure()
    from impots.jumeau import boucle

    out: dict[str, Any] = {"commit": commit(), "mode": mode,
                           "forfait": {k: getattr(boucle.forfait(st), k) for k in
                                       ("super_brut", "d61", "d5", "chomage", "prestations",
                                        "rd")}}
    if mode == "pronostic":
        cc = cs = coef_pronostic(st)
    else:
        cc, cs = lire_coef("cice"), lire_coef("smic")
    out["coefficients"] = {"cice": {k: getattr(cc, k) for k in out["forfait"]},
                           "smic": {k: getattr(cs, k) for k in out["forfait"]}}
    t0 = time.perf_counter()
    out["cice"] = {"sans": _champs(cice(None)), "avec": _champs(cice(cc)),
                   "iterations": iterer(cice, cc)}
    S = smic_session()
    out["smic"] = {}
    for d in (0.0, 0.5, 1.0):
        out["smic"][str(d)] = {"sans": _champs(smic(S, None, d)),
                               "avec": _champs(smic(S, cs, d))}
    out["smic"]["iterations_0.0"] = iterer(lambda c: smic(S, c, 0.0), cs)
    out["duree_s"] = round(time.perf_counter() - t0, 1)
    return ecrire(f"jumeau_{mode}", out)


RAPPORT = ROOT / "reports" / "etudes" / "boucle_b28"


def rapport() -> Path:
    """Les agrégats des passes et du jumeau (aucune microdonnée) dans le dépôt."""
    out: dict[str, Any] = {"decisions": ["D-545", "D-546"]}
    for cas in ("cice", "smic"):
        p = json.loads((SORTIE / f"passe_{cas}.json").read_text(encoding="utf-8"))
        out[f"passe_{cas}"] = {k: p[k] for k in (
            "commit", "annee", "menages_echantillon", "duree_s", "variantes", "paires",
            "coefficients", "par_personne_annee_eur", "prestations_eur_par_personne_annee",
            "ordre_deux")}
        out[f"passe_{cas}"]["meta"] = {k: v for k, v in p["meta"].items() if k != "commit"}
    for mode in ("pronostic", "passes"):
        f = SORTIE / f"jumeau_{mode}.json"
        if f.exists():
            out[f"jumeau_{mode}"] = json.loads(f.read_text(encoding="utf-8"))
    RAPPORT.mkdir(parents=True, exist_ok=True)
    dest = RAPPORT / "resultats.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=float) + "\n",
                    encoding="utf-8")
    print(dest)
    return dest


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "passe":
        passe(sys.argv[2])
    elif cmd == "rapport":
        rapport()
    elif cmd == "jumeau":
        jumeau(sys.argv[2] if len(sys.argv) > 2 else "passes")
    else:
        raise SystemExit(f"commande « {cmd} »")
