"""La grille de vérification (but 18, D-362, D-363) : chaque instrument chiffré, contre un
total publié, sur 2022, 2023 et 2024.

    impots verification passe --annee 2023 [--lots 4]   # une passe, son rapport
    impots verification ecrire                          # la grille et la loi d'erreur

Les lignes, leurs totaux publiés et leurs tolérances sont dans
`docs/verification/lignes.json`, préenregistrés par D-363 avant toute passe ; ce module
les lit et ne les écrit jamais. Une passe prend la loi de l'année et la population de
2024 ramenée à l'année par les indices constatés de l'Insee (D-362), sans imputation : la
population telle que les études la voient par défaut. Les entreprises du millésime 2023,
dont les bénéfices sont ceux de 2024, suivent le PIB nominal des comptes depuis 2024
(D-246 ; but 19, étape 1).

Une ligne refusée (aucun total publié, ou un droit que le moteur ne sert pas) le reste :
la grille dit le trou, elle ne le comble pas.
"""

from __future__ import annotations

import json
import statistics
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LIGNES = ROOT / "docs" / "verification" / "lignes.json"
RAPPORTS = ROOT / "reports" / "verification"
GRILLE = ROOT / "docs" / "verification" / "GRILLE.md"
POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"
#: The firm vintage the studies serve (IMPOTS_FIRM_VINTAGE), its file under its name, and
#: the year of its taxes, 2024, from which the grid ages it (but 19, étape 1 :
#: `predictif.firmes.ANNEE_DES_IMPOTS`). It was 2023 until then, the GDP of 2024 over 2023
#: applied to profits that were already the DGFiP's of 2024.
MILLESIME_FIRMES = "2023"
FIRMES = ROOT / "data" / "processed" / f"firms_{MILLESIME_FIRMES}.parquet"
BASE_MENAGES = 2024
JEU = "insee_constate"
PONT = {"rsa": 1.355, "ppa": 1.725}
"""Le milieu des ponts de non-recours de la Drees (`margins.TAKE_UP_BRIDGE`)."""


def _base_firmes() -> int:
    from impots.predictif import firmes

    return firmes.base_year(MILLESIME_FIRMES)


BASE_FIRMES = _base_firmes()


class VerificationError(RuntimeError):
    """La grille dirait ce que les passes ne disent pas."""


def lignes() -> list[dict[str, Any]]:
    return json.loads(LIGNES.read_text(encoding="utf-8"))["lignes"]


def _commit() -> tuple[str, bool]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "src", "docs"],
                                cwd=ROOT, capture_output=True, text=True,
                                check=True).stdout.strip())
    return head, dirty


#: L'IR net comparable aux émissions publiées (but 19, étape 1 ; proposition A1 du
#: diagnostic `ir_net_et_entreprises.md`) : `ir` (impot_revenu_restant_a_payer, après
#: les seuils de recouvrement) = impôt au barème + PFU + CEHR − réductions − crédits,
#: d'une passe à part, niches et capital imputés, la seule où le modèle porte les quatre
#: termes que la DGFiP additionne. Le PFU et 10,6 des 19,5 Md€ de RICI y sont calés :
#: la ligne le dit. Le capital imputé décrit les revenus de 2024 (n° 41) ; une autre
#: année le vieillit par un indice déclaré (D-249), ici l'impôt hors barème publié de
#: l'année sur celui de 2024 : 7,603 Md€ en 2023 (n° 32, tableau 3, ligne « Total »),
#: 7,505 en 2022 (7,603 moins la variation de 2023, +0,098, n° 41, graphique 1), 10,32 en
#: 2024 (n° 41, tableau 2). Hypothèse déclarée : le PFU de l'année est calé par lui.
HORS_BAREME = {2022: 7.505e9, 2023: 7.602575235e9, 2024: 10.32e9}
IR_NET = "ir, niches et capital imputés"


def indice_capital(annee: int) -> float | None:
    """L'indice qui vieillit le capital imputé de 2024 vers `annee` (`HORS_BAREME`)."""
    if annee == BASE_MENAGES:
        return None
    if annee not in HORS_BAREME:
        raise VerificationError(f"aucun impôt hors barème publié pour {annee}")
    return HORS_BAREME[annee] / HORS_BAREME[BASE_MENAGES]


def _population(annee: int) -> tuple[Any, dict[str, Any]]:
    """La population de 2024 ramenée à `annee` par les indices constatés (D-362)."""
    import polars as pl

    from impots import hypotheses
    from impots import uprating as up

    frame = pl.read_parquet(POPULATION)
    record: dict[str, Any] = {"de": BASE_MENAGES, "vers": annee}
    if annee != BASE_MENAGES:
        uprating, record = hypotheses.vieillissement_menages(JEU, BASE_MENAGES, annee)
        frame = up.uprate(frame, annee, uprating)
    return frame, record


def employeurs(t: dict[str, float]) -> dict[str, float]:
    """Les cotisations des employeurs au sens D121, et ce qui les sépare du super-brut
    moins le brut, chacun à part (but 19, étape 1) : les prélèvements que l'Insee classe
    en impôts sur les salaires (D291), la contribution de l'État aux pensions de ses
    titulaires et militaires (cotisation imputée, D122), l'indemnité de résidence et le
    SFT (des salaires, D11). La mesure de D-363 reste, telle qu'elle était."""
    d291, etat, hors_brut = (t["prelevements_salaires_d291"], t["pension_employeur_etat"],
                             t["remuneration_hors_brut"])
    return {
        "salaire_super_brut - salaire_brut - D291 - pension de l'État - hors brut":
            t["salaire_super_brut"] - t["salaire_brut"] - d291 - etat - hors_brut,
        "prelevements_salaires_d291": d291,
        "pension_employeur_etat": etat,
        "remuneration_hors_brut": hors_brut,
    }


def mesures_ir_net(frame: Any, annee: int, lots: int) -> dict[str, float]:
    """L'IR net d'une passe à part, niches et capital imputés (`IR_NET`), et ses termes.

    Par lots, comme la passe des ménages (D-362), mais chaque lot pèse la France entière
    le temps de son imputation : `niches.impute` tire chaque foyer avec la probabilité
    « foyers bénéficiaires publiés / foyers pondérés de la tranche », et un lot qui ne
    pèse qu'un quart de la France en tirerait quatre fois trop (bornés à tous). Le poids
    de chaque lot est multiplié par le poids total sur le sien, et ses totaux divisés
    d'autant ; le capital imputé ne dépend pas de l'échelle (`population.capital`, 5).
    `households_par_lots` ne le fait pas : la réconciliation qui impute les niches par
    lots en tire trop (but 19, étape 1, rapport)."""
    import gc
    import zlib

    import polars as pl

    from impots.population import aggregate
    from impots.population.runner import run

    keys = ("ir", "ir_avant_niches", "reductions", "credits_impot")
    totals = dict.fromkeys(keys, 0.0)
    lot = frame["household_id"].map_elements(
        lambda key: zlib.crc32(str(key).encode()) % max(lots, 1), return_dtype=pl.Int64)
    poids = frame.group_by("household_id").agg(pl.col("weight").mean())["weight"].sum()
    for k in range(max(lots, 1)):
        part = frame.filter(lot == k)
        facteur = poids / part.group_by("household_id").agg(
            pl.col("weight").mean())["weight"].sum()
        part = part.with_columns(pl.col("weight") * facteur)
        t = aggregate.aggregate(run(part, year=annee, tier="light", impute_niches=True,
                                    impute_capital=True,
                                    capital_index=indice_capital(annee)).households).totals
        for key in keys:
            totals[key] += t[key] / facteur
        del part
        gc.collect()
    return {IR_NET: totals["ir"],
            "ir_avant_niches, niches et capital imputés": totals["ir_avant_niches"],
            "reductions + credits_impot, imputés": totals["reductions"]
            + totals["credits_impot"]}


def mesures_menages(annee: int, lots: int) -> tuple[dict[str, float], dict[str, Any]]:
    """Les totaux et les comptes de la passe des ménages de `annee`, puis l'IR net de sa
    passe imputée."""
    from impots.population import aggregate
    from impots.population.runner import households_par_lots

    frame, record = _population(annee)
    households = households_par_lots(frame, lots, year=annee, tier="full")
    agg = aggregate.aggregate(households)
    del households
    # The existing lines read the full-take-up entitlement and its niveau de vie, as they
    # were preregistered (D-363); the expected payments of the take-up layer (but 19,
    # étape 4) are measured beside them, under names no line reads until one is
    # preregistered.
    t, c = agg.totals, agg.counts
    q, servi = agg.niveau_de_vie_quantiles_droit, agg.niveau_de_vie_quantiles
    m = {
        "cotisations_salariales": t["cotisations_salariales"],
        "salaire_super_brut - salaire_brut": t["salaire_super_brut"] - t["salaire_brut"],
        **employeurs(t),
        "allegement_general": t["allegement_general"],
        "allegement_bandeau_maladie": t["allegement_bandeau_maladie"],
        "allegement_bandeau_famille": t["allegement_bandeau_famille"],
        "csg_deductible + csg_imposable": t["csg_deductible"] + t["csg_imposable"],
        # The CSG on activity income with the self-employed's (but 19, étape 2): what the
        # published total counts. Read once `lignes.json` names it, preregistered.
        "csg_deductible + csg_imposable + csg_non_salarie":
            t["csg_deductible"] + t["csg_imposable"] + t["csg_non_salarie"],
        "revenus_non_salaries_hors_gerants": t["revenus_non_salaries_hors_gerants"],
        "csg_retraite + csg_chomage": t["csg_retraite"] + t["csg_chomage"],
        "ir_avant_niches": t["ir_avant_niches"],
        "salaire_imposable": t["salaire_imposable"],
        "retraite_imposable": t["retraite_imposable"],
        "rsa / 1,355": t["rsa_droit"] / PONT["rsa"],
        "ppa / 1,725": t["ppa_droit"] / PONT["ppa"],
        "rsa servi en espérance": t["rsa"],
        "ppa servie en espérance": t["ppa"],
        "niveau de vie médian servi, pondéré personne": servi[50],
        "D9/D1 servi, pondéré personne": servi[90] / servi[10],
        "aide_logement": t["aide_logement"], "af": t["af"],
        "niveau de vie médian, pondéré personne": q[50],
        "D9/D1, pondéré personne": q[90] / q[10],
        **{k: c[k] for k in c},
        **mesures_ir_net(frame, annee, lots),
    }
    return m, record


def mesures_firmes(annee: int) -> tuple[dict[str, float], dict[str, Any]]:
    """Les totaux de la couche entreprises de `annee`, vieillis par le PIB."""
    import polars as pl

    from impots import hypotheses
    from impots.entreprises import aggregate as firm_aggregate
    from impots.entreprises import runner as firm_runner

    result = firm_runner.run(pl.read_parquet(FIRMES), year=annee)
    totals = firm_aggregate.aggregate(result.firms).totals
    if annee == BASE_FIRMES:
        facteur, record = 1.0, {"de": BASE_FIRMES, "vers": annee, "facteur": 1.0}
    else:
        facteur, record = hypotheses.vieillissement_entreprises(JEU, BASE_FIRMES, annee)
    names = {"IS de la couche entreprises": "impot_societes",
             "contribution sociale sur l'IS": "contribution_sociale_is",
             "C3S": "c3s", "CVAE": "cvae"}
    return {label: facteur * totals.get(key, 0.0) for label, key in names.items()}, record


def passe(annee: int, lots: int = 4) -> Path:
    """Une passe de l'année, écrite dans reports/verification/passe_<annee>.json."""
    if annee not in (2022, 2023, 2024):
        raise VerificationError(f"la grille porte 2022, 2023 et 2024, pas {annee} (D-362)")
    commit, dirty = _commit()
    if dirty:
        raise VerificationError("src ou docs ne sont pas commités : une passe de la grille "
                                "tourne sur un commit, pour que son rapport le nomme.")
    menages, vieillissement = mesures_menages(annee, lots)
    firmes, firmes_record = mesures_firmes(annee)
    RAPPORTS.mkdir(parents=True, exist_ok=True)
    out = RAPPORTS / f"passe_{annee}.json"
    out.write_text(json.dumps({
        "annee": annee, "commit": commit, "lots": lots, "jeu": JEU,
        "vieillissement_menages": vieillissement, "vieillissement_firmes": firmes_record,
        "mesures": {**menages, **firmes}}, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def grille() -> list[dict[str, Any]]:
    """Chaque ligne, son simulé, son écart, son verdict ; refusée si elle l'est."""
    passes = {int(p.stem.split("_")[1]): json.loads(p.read_text(encoding="utf-8"))
              for p in sorted(RAPPORTS.glob("passe_*.json"))}
    out = []
    for ligne in lignes():
        row = dict(ligne)
        p = passes.get(ligne["annee"])
        if ligne["publie"] is None:
            row.update(simule=None, ecart=None, verdict="refusée")
        elif p is None:
            row.update(simule=None, ecart=None, verdict="pas de passe")
        else:
            if ligne["modele"] not in p["mesures"]:
                raise VerificationError(f"{ligne['id']} {ligne['annee']} : la passe ne "
                                        f"mesure pas « {ligne['modele']} »")
            sim = p["mesures"][ligne["modele"]]
            ecart = sim / ligne["publie"] - 1.0
            tol = ligne["tolerance"]
            verdict = (ligne["usage"] if ligne["usage"] != "validation" else
                       # Inclusive, and in floating point: 110/100 − 1 is 0,1000…01.
                       "dans la tolérance" if abs(ecart) <= tol + 1e-12
                       else "hors de la tolérance")
            row.update(simule=sim, ecart=ecart, verdict=verdict, commit=p["commit"])
        out.append(row)
    return out


def loi_d_erreur(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Par ligne notée, sur ses années : le biais (moyenne des écarts), l'étendue, le
    nombre d'années, et combien tiennent leur tolérance."""
    par: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        if r["usage"] == "validation" and r.get("ecart") is not None:
            par.setdefault(r["id"], []).append(r)
    return {k: {"ligne": v[0]["ligne"], "annees": [r["annee"] for r in v],
                "biais": statistics.fmean(r["ecart"] for r in v),
                "min": min(r["ecart"] for r in v), "max": max(r["ecart"] for r in v),
                "tenues": sum(r["verdict"] == "dans la tolérance" for r in v)}
            for k, v in par.items()}


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:+.1f} %".replace(".", ",")


def _val(x: float | None) -> str:
    if x is None:
        return "—"
    if abs(x) >= 1e9:
        return f"{x / 1e9:,.2f} Md€".replace(",", " ").replace(".", ",")
    if abs(x) >= 1e4:
        return f"{x:,.0f}".replace(",", " ")
    return f"{x:.2f}".replace(".", ",")


def ecrire() -> Path:
    rows = grille()
    loi = loi_d_erreur(rows)
    RAPPORTS.mkdir(parents=True, exist_ok=True)
    (RAPPORTS / "grille.json").write_text(json.dumps({"lignes": rows, "loi": loi},
                                                     ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    w = ["# La grille de vérification (but 18)", "",
         "<!-- Généré par `impots verification ecrire` depuis reports/verification/ ; ne "
         "pas éditer à la main. -->", "",
         "Chaque instrument que les études chiffrent, contre un total publié, sur 2022, "
         "2023 et 2024 (D-362). Les lignes, leurs sources et leurs tolérances sont "
         "préenregistrées dans D-363 et `lignes.json`. La population de 2024 est ramenée à "
         "chaque année par les indices constatés de l'Insee ; sa structure reste celle de "
         "2024.", "",
         "## La loi d'erreur, par ligne notée", "",
         "| ligne | années | biais | de | à | tenues |", "|---|---|---|---|---|---|"]
    for v in loi.values():
        w.append(f"| {v['ligne']} | {', '.join(map(str, v['annees']))} | {_pct(v['biais'])} "
                 f"| {_pct(v['min'])} | {_pct(v['max'])} | {v['tenues']}/{len(v['annees'])} |")
    for annee in (2022, 2023, 2024):
        w += ["", f"## {annee}", "",
              "| ligne | simulé | publié | écart | tolérance | verdict |",
              "|---|---|---|---|---|---|"]
        for r in (r for r in rows if r["annee"] == annee):
            tol = "—" if r["tolerance"] is None else f"±{r['tolerance'] * 100:.0f} %"
            verdict = r["verdict"] + ("" if r["verdict"] != "refusée" else
                                      f" : {r['remarque']}")
            w.append(f"| {r['ligne']} | {_val(r['simule'])} | {_val(r['publie'])} | "
                     f"{_pct(r['ecart'])} | {tol} | {verdict} |")
    GRILLE.write_text("\n".join(w) + "\n", encoding="utf-8")
    return GRILLE


def main_args(action: str, annee: int | None = None, lots: int = 4) -> int:
    import sys

    try:
        path = passe(annee, lots) if action == "passe" else ecrire()
    except VerificationError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"-> {path}")
    return 0
