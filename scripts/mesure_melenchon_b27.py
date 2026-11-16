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

ROOT = Path(os.environ.get("MESURE27_RACINE", Path(__file__).resolve().parents[1]))
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


# --------------------------------------------------------------------------- #
# l'analyse : agrégats, déciles, cellules, perdants, paires (aucune passe)
# --------------------------------------------------------------------------- #
ETUDE = ROOT / "reports" / "etudes" / "presidentielle_melenchon"
RAPPORT = ROOT / "reports" / "etudes" / "mesure_melenchon_b27"
LONGS = {v: k for k, v in COURTS.items()}
MD = 1e9


def lire(nom: str) -> dict[str, Any]:
    return json.loads((SORTIE / f"{nom}.json").read_text(encoding="utf-8"))


def etude(court: str | None) -> dict[str, Any]:
    """La réponse de la première année publiée (l'étude, commit 5a68669)."""
    if court is None:
        f = ETUDE / "premiere_annee_pres2027_melenchon_programme.json"
    else:
        n = LONGS[court]
        f = ETUDE / "mesures" / n / f"premiere_annee_pres2027_melenchon_{n}.json"
    return json.loads(f.read_text(encoding="utf-8"))


def md(x: float, d: int = 3) -> float:
    return round(float(x) / MD, d)


def cellules(nom: str) -> dict[str, Any]:
    """Les cas types de la population : la configuration du ménage croisée avec sa
    situation devant la mesure (relevé par la loi, actif non relevé, retraité, ni l'un
    ni l'autre) ; puis les perdants et ce qui les fait perdre. Des cellules pondérées,
    aucune ligne de ménage."""
    import numpy as np
    import polars as pl

    from impots import service

    h = pl.read_parquet(SORTIE / f"{nom}.parquet")
    f = service.population_frame().filter(pl.col("household_id").is_in(h["household_id"]))
    conf = f.group_by("household_id").agg(
        pl.len().alias("n"),
        (pl.col("role_menage") == "conjoint").any().alias("couple"),
        ((pl.col("role_menage") == "enfant") & (pl.col("age") < 25)).any().alias("enfants"),
        (pl.col("role_menage") == "autre").any().alias("autre"))

    def config(r: dict) -> str:
        if r["autre"]:
            return "ménage complexe"
        if r["n"] == 1:
            return "personne seule"
        if r["couple"]:
            return "couple avec enfants" if r["enfants"] else "couple sans enfant"
        return "famille monoparentale" if r["enfants"] else "ménage complexe"

    conf = conf.with_columns(pl.Series("configuration", [config(r) for r in
                                                          conf.to_dicts()]))
    h = h.join(conf.select("household_id", "configuration"), on="household_id",
               how="left")
    def d(c: str) -> Any:
        if f"{c}_reform" in h.columns:
            return (h[f"{c}_reform"] - h[c]).to_numpy()
        return np.zeros(h.height)

    releve = d("salaire_brut") > 1.0
    actif = h["salaire_brut"].to_numpy() > 0
    retraite = h["retraite_imposable"].to_numpy() > 0
    situation = np.where(releve, "salaire relevé par la mesure",
                         np.where(actif, "actif, salaire inchangé",
                                  np.where(retraite, "retraité", "ni salaire ni pension")))
    h = h.with_columns(pl.Series("situation", situation))
    w = h["weight"].to_numpy()
    rd = d("revenu_disponible")
    comp = {c: d(c) for c in ("salaire_net", "ppa", "aide_logement", "rsa", "ir", "aspa",
                              "af", "garantie_autonomie", "csg_chomage", "asf")}
    out: dict[str, Any] = {"par_configuration": [], "par_situation": [], "croise": []}
    for cle, cols in (("par_configuration", ["configuration"]),
                      ("par_situation", ["situation"]),
                      ("croise", ["configuration", "situation"])):
        keys = h.select(cols).unique().sort(cols).to_dicts()
        for k in keys:
            m = np.ones(h.height, bool)
            for c, v in k.items():
                m &= (h[c] == v).to_numpy()
            ww = w[m]
            if ww.sum() == 0:
                continue
            out[cle].append({**k, "menages_m": round(ww.sum() / 1e6, 3),
                             "echantillon": int(m.sum()),
                             "gain_moyen_eur": round(float((rd[m] * ww).sum() / ww.sum()), 1),
                             "total_md": md((rd[m] * ww).sum()),
                             "part_gagnants": round(float(ww[rd[m] > 1].sum() / ww.sum()), 4),
                             "part_perdants": round(float(ww[rd[m] < -1].sum() / ww.sum()),
                                                    4)})
    perd = rd < -1.0
    wp = w[perd]
    out["perdants"] = {
        "menages_m": round(wp.sum() / 1e6, 3), "part": round(wp.sum() / w.sum(), 4),
        "echantillon": int(perd.sum()),
        "perte_moyenne_eur": round(float((rd[perd] * wp).sum() / wp.sum()), 1) if wp.sum()
        else 0.0,
        "total_md": md((rd[perd] * wp).sum()),
        "composantes_moyennes_eur": {c: round(float((v[perd] * wp).sum() / wp.sum()), 1)
                                     for c, v in comp.items()} if wp.sum() else {},
        "par_situation": {s: round(float(wp[situation[perd] == s].sum() / wp.sum()), 4)
                          for s in sorted(set(situation[perd]))},
        "sans_hausse_de_salaire_part": round(
            float(wp[~releve[perd]].sum() / wp.sum()), 4) if wp.sum() else 0.0,
        "dont_par_la_prime_part": round(float(
            wp[comp["ppa"][perd] < -1].sum() / wp.sum()), 4) if wp.sum() else 0.0,
    }
    out["releves"] = {"menages_m": round(w[releve].sum() / 1e6, 3),
                      "gain_moyen_eur": round(float((rd[releve] * w[releve]).sum()
                                                    / w[releve].sum()), 1)}
    return out


INSTR = ("reform_cost", "revenu_disponible", "salaire_brut", "salaire_super_brut",
         "allegement_general", "cotisations_employeur", "cotisations_salariales", "ir",
         "csg_deductible", "csg_retraite", "ppa", "rsa", "aide_logement", "af", "asf",
         "aspa", "garantie_autonomie", "pension_employeur_etat")


def valeurs(p: dict[str, Any]) -> dict[str, float]:
    d = p["deltas"] if "deltas" in p else p["response"]["deltas"]
    c = p["reform_cost"] if "reform_cost" in p else p["response"]["reform_cost"]
    return {k: float(c if k == "reform_cost" else d.get(k, 0.0)) for k in INSTR}


def paires() -> dict[str, Any]:
    """c(P) = Σ c_i + Σ I_ij + R, par instrument ; et l'artefact des imputations."""
    noms = list(COURTS.values())
    seul = {n: valeurs(lire(f"rapide_union_{n}")) for n in noms}
    prog = valeurs(lire("rapide_union_programme"))
    inter_ij: dict[str, dict[str, float]] = {}
    for a, b in itertools.combinations(noms, 2):
        ab = valeurs(lire(f"rapide_union_{a}+{b}"))
        inter_ij[f"{a}+{b}"] = {k: ab[k] - seul[a][k] - seul[b][k] for k in INSTR}
    somme = {k: sum(seul[n][k] for n in noms) for k in INSTR}
    inter = {k: prog[k] - somme[k] for k in INSTR}
    reste = {k: inter[k] - sum(i[k] for i in inter_ij.values()) for k in INSTR}
    propres = {n: valeurs(lire(f"rapide_propres_{n}")) for n in noms}
    pub = {n: valeurs(etude(n)) for n in noms}
    pub_p = valeurs(etude(None))
    rang = sorted(inter_ij, key=lambda k: -abs(inter_ij[k]["reform_cost"]))
    return {
        "seules_union_md": {n: {k: md(v) for k, v in s.items()} for n, s in seul.items()},
        "seules_propres_md": {n: {k: md(v) for k, v in s.items()} for n, s in
                              propres.items()},
        "seules_etude_md": {n: {k: md(v) for k, v in s.items()} for n, s in pub.items()},
        "programme_md": {k: md(v) for k, v in prog.items()},
        "programme_etude_md": {k: md(v) for k, v in pub_p.items()},
        "somme_des_seules_md": {k: md(v) for k, v in somme.items()},
        "interaction_md": {k: md(v) for k, v in inter.items()},
        "paires_md": {k: {x: md(y) for x, y in inter_ij[k].items()} for k in rang},
        "rang_paires": rang,
        "reste_ordre_3_md": {k: md(v, 4) for k, v in reste.items()},
        "interaction_etude_md": {k: md(pub_p[k] - sum(pub[n][k] for n in noms))
                                 for k in INSTR},
        "artefact_imputations_md": {k: md(sum(seul[n][k] - propres[n][k] for n in noms))
                                    for k in INSTR},
    }


def identites(p: dict[str, Any]) -> dict[str, float]:
    """Σ des déciles (n × écart moyen) contre Δ revenu disponible ; la somme par ménage
    contre l'agrégat ; le double compte de l'agrégat (D-045)."""
    dec = sum(float(r["mean_delta"]) * float(r["n_households"]) for r in p["deciles"])
    rd = float(p["deltas"]["revenu_disponible"])
    return {"deciles_moins_delta_rd_md": md(dec - rd, 9),
            "menages_moins_delta_rd_md": md(p["delta_rd_somme_menages"] - rd, 9),
            "balance": {k: (md(v, 9) if isinstance(v, (int, float)) else v)
                        for k, v in (p.get("balance") or {}).items()}}


def deciles(p: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"decile": int(r["decile"]), "menages_m": round(r["n_households"] / 1e6, 3),
             "gain_moyen_eur": round(r["mean_delta"], 1),
             "total_md": md(r["mean_delta"] * r["n_households"]),
             "part_gagnants": round(r["share_winners"], 4),
             "part_perdants": round(r["share_losers"], 4)} for r in p["deciles"]]


def analyser() -> None:
    RAPPORT.mkdir(parents=True, exist_ok=True)
    e = etude("smic")
    chaine = {"etude_5a68669": md(e["response"]["reform_cost"]),
              "code_actuel_population_but19_rapide": md(lire("rapide_but19_smic")[
                  "reform_cost"]),
              "population_d521_rapide": md(lire("rapide_propres_smic")["reform_cost"]),
              "population_d521_complet": md(lire("complet_propres_smic")["reform_cost"])}
    smic = lire("complet_propres_smic")
    out = {
        "mesure": "smic_1700_net", "reforme": reformes()["smic"], "vue": "figee 2026",
        "population": "D-521, empreinte 8d42e0d8, 199 451 ménages, huit lots (D-362)",
        "chaine_du_cout_md": chaine,
        "deltas_md": {k: md(v) for k, v in smic["deltas"].items() if abs(v) > 1e6},
        "deltas_etude_md": {k: md(v) for k, v in e["response"]["deltas"].items()
                            if abs(v) > 1e6},
        "cout_md": md(smic["reform_cost"]), "cout_droit_md": md(smic["reform_cost_droit"]),
        "impulsions_md": {k: md(v) for k, v in smic["impulsions"].items()},
        "deciles": deciles(smic), "deciles_etude": deciles(e["response"]),
        "cellules": cellules("complet_propres_smic"),
        "identites": identites(smic),
        "duree_s": smic["duree_s"],
    }
    (RAPPORT / "smic.json").write_text(json.dumps(out, ensure_ascii=False, indent=1)
                                       + "\n", encoding="utf-8")
    pr = paires()
    pr["identites"] = {n: identites(lire(n)) for n in
                       ["rapide_union_programme", *[f"rapide_union_{c}"
                                                    for c in COURTS.values()]]}
    pr["deciles_programme"] = deciles(lire("rapide_union_programme"))
    pr["cellules_programme"] = cellules("rapide_union_programme")
    (RAPPORT / "programme.json").write_text(json.dumps(pr, ensure_ascii=False, indent=1)
                                            + "\n", encoding="utf-8")
    print(RAPPORT)


# --------------------------------------------------------------------------- #
# le jumeau : les mesures de l'étude portées aux nombres des passes (aucune passe)
# --------------------------------------------------------------------------- #
CONVENTION_D521 = "premiere_annee_d521"
FIN = {"financement_a16_part_cnav": 0.5, "financement_compensation": 0.5}


def _ratio(new: float, old: float, defaut: float) -> float:
    return new / old if abs(old) > 1e6 and abs(new) > 1e6 else defaut


def redimensionner(S: Any, cle: str, p: dict[str, Any]) -> dict[str, float]:
    """Le candidat `cle` de la session porté aux nombres de la passe `p` (convention
    « premiere_annee_d521 ») : chaque année et chaque vue, le coût fois k = c_passe /
    c_étude (vue figée de 2026) ; chaque impulsion fois son propre rapport de 2026
    (k quand l'une des deux est nulle) ; les variations du canal des créations fois le
    rapport des cotisations des employeurs (la PFU : de l'impôt sur le revenu ; sinon k) ;
    la réponse de la première année remplacée (coût, écarts, déciles). Les canaux de
    comportement et le reste du rapport ne bougent pas. Remplacé en place, la session
    vidée de ses mesures : les clés des fiches (payeurs, D-510) restent celles du
    candidat."""
    import copy

    c = copy.deepcopy(S.candidats[cle])
    pay, pa = c["payload"], c["premiere_annee"]
    vieux = pa["response"]
    k = float(p["reform_cost"]) / float(vieux["reform_cost"])
    imp0 = pay["years"][0]["statistiques"]["figee"]["impulses"] or {}
    ki = {i: _ratio(float(p["impulsions"].get(i, 0.0)), float(v), k)
          for i, v in imp0.items()}
    if "cotisations_employeurs" in ki and abs(imp0["cotisations_employeurs"]) > 1e8:
        kv = ki["cotisations_employeurs"]
    elif "pfu_supprime" in (pa["request"].get("reform") or {}):
        kv = _ratio(p["deltas"].get("ir", 0.0), vieux["deltas"].get("ir", 0.0), k)
    else:
        kv = k
    for y in pay["years"]:
        for champ in ("mechanical_frozen_eur", "mechanical_aged_eur"):
            y[champ] = float(y[champ]) * k
        for st in y["statistiques"].values():
            if st.get("cost_eur") is not None:
                st["cost_eur"] = float(st["cost_eur"]) * k
            if st.get("impulses"):
                st["impulses"] = {i: float(v) * ki.get(i, k)
                                  for i, v in st["impulses"].items()}
    cr = (pay.get("rejeu") or {}).get("creations")
    if cr:
        cr["variations"] = {v: [float(x) * kv for x in xs]
                            for v, xs in cr["variations"].items()}
    vieux.update(reform_cost=p["reform_cost"], deltas=p["deltas"], deciles=p["deciles"])
    c["convention"] = CONVENTION_D521
    S.candidats[cle] = c
    S._mesures.clear()
    return {"k_cout": k, "k_creations": kv, **{f"k_{i}": v for i, v in ki.items()}}


def session() -> Any:
    from impots import site_jumeau
    from impots.jumeau import navigateur

    return navigateur.Session(site_jumeau.donnees())


def r3(x: float, d: int = 3) -> float:
    return round(float(x), d)


def court_(e: dict[str, list[float]]) -> dict[str, float]:
    out = {"b9_2026": r3(e["b9"][0], 2), "b9_2035": r3(e["b9"][-1], 2),
           "dette_2035": r3(e["dette_pts"][-1]), "pib_2035": r3(e["pib_pct"][-1])}
    if "emploi_total" in e:
        out["emploi_2026"] = r3(e["emploi_total"][0], 1)
        out["emploi_2035"] = r3(e["emploi_total"][-1], 1)
    if "c_menages" in e:
        out["consommation_2035"] = r3(e["c_menages"][-1], 2)
    return out


def smic_jumeau(S: Any) -> dict[str, Any]:
    """Le Smic seul dans le jumeau : structurel figée et vieillie, θ½ ; la cascade ; les
    sensibilités θ par θ ; la trajectoire de l'emploi et du solde."""
    from impots.jumeau import papillon as pa

    c = "pres2027_melenchon_smic_1700_net"
    out: dict[str, Any] = {}
    for vue in ("figee", "vieillie"):
        m = S.mesure_structurel(c, vue, "parts_premiere_annee")
        tr, _ = pa.trajectoire(S, [m], cle=c, theta=FIN)
        e = pa.ecarts(tr)
        V = {"court": court_(e), "serie": {k: [r3(x) for x in v] for k, v in e.items()},
             "cascade": pa.cascade_simple(tr),
             "reprise_2035": r3(1 - e["b9"][-1] / e["b9"][0])}
        try:
            mr = S.mesure(c, vue)
            trr, _ = pa.trajectoire(S, [mr], cle=c, mode="reduit")
            V["reduit"] = court_(pa.ecarts(trr))
        except Exception as err:  # dit, pas masqué
            V["reduit"] = f"refusé : {err}"
        if vue == "figee":
            V["sensibilites"] = [{k: (r3(v, 2) if isinstance(v, float) else v)
                                  for k, v in x.items()}
                                 for x in pa.sensibilites(S, [m], cle=c, theta=FIN)]
            V["diffusion"] = {}
            for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                tr_, _ = pa.trajectoire(S, [m], cle=c,
                                        theta={**FIN, "travail_smic_diffusion": t})
                V["diffusion"][str(t)] = court_(pa.ecarts(tr_))
            # le coin des θ qui décident du signe de l'emploi : les trois du travail
            coins = {}
            for d_ in (0.0, 0.5, 1.0):
                for inc in (0.0, 0.5, 1.0):
                    for el in (0.0, 0.5, 1.0):
                        tr_, _ = pa.trajectoire(S, [m], cle=c, theta={
                            **FIN, "travail_smic_diffusion": d_, "travail_incidence": inc,
                            "jumeau_emploi_elasticite_cout": el})
                        e_ = pa.ecarts(tr_)
                        coins[f"{d_}/{inc}/{el}"] = {
                            "emploi_2035": r3(e_["emploi_total"][-1], 1),
                            "b9_2035": r3(e_["b9"][-1], 2)}
            V["coins_travail"] = coins
        out[vue] = V
    return out


def programme_jumeau(S: Any) -> dict[str, Any]:
    """Le programme par ses mesures seules (D-502), ses mesures une à une, figée."""
    from impots.jumeau import papillon as pa

    cle_p, seules = pa.cles(S, "melenchon")
    out: dict[str, Any] = {}
    for vue in ("figee", "vieillie"):
        ms = pa.mesures_seules(S, "melenchon", vue)
        tr, _ = pa.trajectoire(S, ms, cle=cle_p, theta=FIN)
        V = {"ensemble": court_(pa.ecarts(tr)), "identites": pa.identites(tr, ms),
             "cascade": pa.cascade_simple(tr), "mesures": {}}
        somme: dict[str, float] = {}
        for m, c_ in zip(ms, [*seules, cle_p], strict=True):
            t_, _ = pa.trajectoire(S, [m], cle=c_, theta=FIN)
            k = court_(pa.ecarts(t_))
            V["mesures"][m.identifiant.removeprefix("pres2027_melenchon_")] = k
            for x, v in k.items():
                somme[x] = somme.get(x, 0.0) + v
        V["somme"] = {x: r3(v) for x, v in somme.items()}
        V["ensemble_moins_somme"] = {x: r3(V["ensemble"][x] - somme[x])
                                     for x in V["ensemble"] if x in somme}
        out[vue] = V
    return out


def jumeau() -> None:
    from impots.jumeau import papillon as pa

    RAPPORT.mkdir(parents=True, exist_ok=True)
    avant = session()
    apres = session()
    k = redimensionner(apres, "pres2027_melenchon_smic_1700_net",
                       lire("complet_propres_smic"))
    out = {"convention": CONVENTION_D521, "rapports": k,
           "smic_etude": smic_jumeau(avant), "smic_d521": smic_jumeau(apres)}
    prog = session()
    cle_p, seules = pa.cles(prog, "melenchon")
    ks = {}
    for c_ in seules:
        n = COURTS[c_.removeprefix("pres2027_melenchon_")]
        ks[n] = redimensionner(prog, c_, lire(f"rapide_union_{n}"))
    ks["programme"] = redimensionner(prog, cle_p, lire("rapide_union_programme"))
    out["programme_rapports"] = ks
    out["programme_etude"] = programme_jumeau(avant)
    out["programme_d521"] = programme_jumeau(prog)
    (RAPPORT / "jumeau.json").write_text(json.dumps(out, ensure_ascii=False, indent=1,
                                                    default=float) + "\n",
                                         encoding="utf-8")
    print(RAPPORT / "jumeau.json")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    if cmd == "passe":
        nom, mesures, palier, imputations, *pop = args
        passe(nom, mesures.split(","), palier, imputations, *(pop or [None]))
    elif cmd == "programme":
        programme()
    elif cmd == "analyser":
        analyser()
    elif cmd == "jumeau":
        jumeau()
    else:
        raise SystemExit(f"commande « {cmd} »")
