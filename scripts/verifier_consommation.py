#!/usr/bin/env python
"""La vérification préenregistrée de la consommation imputée (but 12, D-323, D-324).

Une passe de la population de 2024 (20 000 ménages, la graine par défaut), la consommation
imputée, et ses totaux contre six agrégats publiés et manifestés. Trois ont une tolérance
qui arrête le but si elle n'est pas tenue : la TVA, les carburants, les accises. Les trois
autres sont des mesures, avec leur pronostic. Rien n'est réglé ici après le calcul : les
cibles, les tolérances et les pronostics sont ceux des deux entrées.

Écrit `reports/consommation_verification_2024.json` et `.md`. Se lance détaché, depuis un
worktree figé sur le commit qui porte D-324 :

    setsid nohup python scripts/verifier_consommation.py > verif.log 2>&1 &
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402

ANNEE = 2024
ECHANTILLON = 20_000
RAW = ROOT / "data" / "raw"
DGFIP = RAW / "dgfip_statistiques_37_2025_tva_2024.xlsx"
SDES = RAW / "sdes_bilan_energetique_2024_series_longues.xlsx"
SORTIE = ROOT / "reports" / "consommation_verification_2024"

#: Trésor-Éco n° 371 (septembre 2025) : la part des ménages dans la TVA nette, en 2022.
PART_MENAGES = 0.651
#: Le même, tableaux 1 et 2 : le rendement d'un point de chaque taux en 2025, net de la
#: part payée par les administrations publiques, en euros.
POINT_TRESOR = {0.021: 0.4e9, 0.055: 2.0e9, 0.10: 1.6e9, 0.20: 7.5e9}
BOUTON_DU_TAUX = {0.021: "tva_taux_super_reduit", 0.055: "tva_taux_reduit",
                  0.10: "tva_taux_intermediaire", 0.20: "tva_taux_normal"}
#: Budget vert du PLF 2027, partie II, section C : 39,7 Md€ d'accise sur les énergies en
#: 2025, payée à 60 % par les ménages ; par ménage, D1 490 €, D10 1 005 €.
ACCISES_BUDGET_VERT = 0.60 * 39.7e9
PROFIL_BUDGET_VERT = 1005.0 / 490.0

#: (bas, haut) : la tolérance, qui arrête le but ; le pronostic, qui ne l'arrête pas.
TOLERANCES = {"tva": (-0.30, 0.10), "carburants": (-0.20, 0.20), "accises": (-0.30, 0.30)}
PRONOSTICS = {"couverture": (0.75, 0.92), "tva": (-0.25, -0.05), "largeur_tva": (0.0, 0.08),
              "point": (0.55, 0.95), "carburants": (-0.15, 0.05),
              "accises": (-0.25, 0.05), "profil": (1.5, 2.5)}


def _feuille(path: Path, nom: str) -> list[tuple]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    return [tuple(r) for r in wb[nom].iter_rows(values_only=True)]


def tva_nette_2024() -> float:
    """La ligne « TVA économique totale (e + f) », colonne 2024, en euros."""
    rows = _feuille(DGFIP, "Tableau 1")
    entete = next(r for r in rows if r and "2024" in [str(c).strip() for c in r])
    j = [str(c).strip() for c in entete].index("2024")
    def libelle(r: tuple) -> str:
        return next((str(c).strip() for c in r if c not in (None, "")), "")

    ligne = [r for r in rows if r and libelle(r).startswith("TVA économique totale")]
    if len(ligne) != 1:
        raise SystemExit(f"{DGFIP.name} : {len(ligne)} lignes « TVA économique totale »")
    return float(str(ligne[0][j]).replace(",", ".")) * 1e9


def depense_cn_2024() -> float:
    """La ligne CPDEP (dépense de consommation des ménages), 2024, en euros."""
    from impots.consommation import CN

    rows = _feuille(CN, "MEURcour")
    entete = next(r for r in rows if r and "2017" in [str(c) for c in r])
    j = [str(c) for c in entete].index(str(ANNEE))
    ligne = [r for r in rows if r and str(r[1] or "").strip() == "CPDEP"]
    if len(ligne) != 1:
        raise SystemExit(f"{CN.name} : {len(ligne)} lignes CPDEP")
    return float(ligne[0][j]) * 1e6


def carburants_sdes_2024() -> float:
    """N149MFR (gazole) et N150MFR (supercarburants), dépense des ménages, 2024, en euros."""
    rows = _feuille(SDES, "series_longues")
    entete = rows[0]
    j = [str(c) for c in entete].index(str(ANNEE))
    total = 0.0
    for code in ("N149MFR", "N150MFR"):
        ligne = [r for r in rows if r and str(r[1]) == code]
        if len(ligne) != 1:
            raise SystemExit(f"{SDES.name} : {len(ligne)} lignes {code}")
        total += float(ligne[0][j]) * 1e6
    return total


def ecart(valeur: float, cible: float) -> float:
    return valeur / cible - 1.0


def dans(x: float, bornes: tuple[float, float]) -> bool:
    return bornes[0] <= x <= bornes[1]


def verifier(households) -> dict:
    """Les six vérifications sur les ménages d'une passe qui a imputé la consommation."""
    from impots import consommation as co
    from impots.api.schemas import ReformSpec
    from impots.population.aggregate import weighted_decile_index

    conso, poids, niveau = co.imputer_menages(households, ANNEE)
    w = poids

    def total(x: np.ndarray) -> float:
        return float(w @ x)

    droit = co.Fiscalite.droit(ANNEE)
    base = co.taxes(conso, droit)
    # Ce que la passe a écrit est ce que l'on vérifie, au centime près.
    for colonne, cle in (("tva_menages", "tva"), ("accises_energie", "accises")):
        ecrit = households[colonne].to_numpy().astype(np.float64)
        if not np.allclose(ecrit, base[cle], rtol=1e-12, atol=1e-6):
            raise SystemExit(f"{colonne} : la passe et la vérification ne lisent pas la même "
                             "consommation")
    out: dict = {"annee": ANNEE, "menages_echantillon": len(households),
                 "menages_ponderes": float(w.sum())}

    cn = depense_cn_2024()
    imputee = sum(total(v) for v in conso.values())
    out["couverture"] = {"imputee_eur": imputee, "comptes_eur": cn, "part": imputee / cn,
                         "pronostic": PRONOSTICS["couverture"],
                         "dans_pronostic": dans(imputee / cn, PRONOSTICS["couverture"])}

    cible = PART_MENAGES * tva_nette_2024()
    tva = {b: total(co.taxes(conso, co.Fiscalite.droit(ANNEE, borne=b))["tva"])
           for b in ("taux", "taux_bas", "taux_haut")}
    e = ecart(tva["taux"], cible)
    largeur = (tva["taux_haut"] - tva["taux_bas"]) / cible
    out["tva"] = {"principal_eur": tva["taux"], "bas_eur": tva["taux_bas"],
                  "haut_eur": tva["taux_haut"], "cible_eur": cible, "ecart": e,
                  "ecart_bas": ecart(tva["taux_bas"], cible),
                  "ecart_haut": ecart(tva["taux_haut"], cible),
                  "largeur_points": largeur, "tolerance": TOLERANCES["tva"],
                  "tenue": dans(e, TOLERANCES["tva"]), "pronostic": PRONOSTICS["tva"],
                  "dans_pronostic": dans(e, PRONOSTICS["tva"]) and dans(
                      largeur, PRONOSTICS["largeur_tva"])}

    points = {}
    for taux, bouton in BOUTON_DU_TAUX.items():
        spec = ReformSpec.model_validate({bouton: round(taux + 0.01, 4)})
        plus = total(co.taxes(conso, droit.reformee(spec), reference=droit)["tva"])
        delta = plus - tva["taux"]
        rapport = delta / POINT_TRESOR[taux]
        points[f"{taux:g}"] = {"menages_eur": delta, "tresor_eur": POINT_TRESOR[taux],
                               "rapport": rapport,
                               "dans_pronostic": dans(rapport, PRONOSTICS["point"])}
    out["point"] = {"taux": points, "pronostic": PRONOSTICS["point"]}

    sdes = carburants_sdes_2024()
    carb = total(conso["07221"])
    e = ecart(carb, sdes)
    out["carburants"] = {"imputee_eur": carb, "sdes_eur": sdes, "ecart": e,
                         "tolerance": TOLERANCES["carburants"],
                         "tenue": dans(e, TOLERANCES["carburants"]),
                         "pronostic": PRONOSTICS["carburants"],
                         "dans_pronostic": dans(e, PRONOSTICS["carburants"])}

    acc = total(base["accises"])
    e = ecart(acc, ACCISES_BUDGET_VERT)
    out["accises"] = {"menages_eur": acc, "cible_eur": ACCISES_BUDGET_VERT, "ecart": e,
                      "tolerance": TOLERANCES["accises"],
                      "tenue": dans(e, TOLERANCES["accises"]),
                      "pronostic": PRONOSTICS["accises"],
                      "dans_pronostic": dans(e, PRONOSTICS["accises"])}

    deciles = weighted_decile_index(niveau, w)
    moyennes = [float(np.average(base["accises"][deciles == k], weights=w[deciles == k]))
                for k in range(10)]
    rapport = moyennes[9] / moyennes[0]
    out["profil"] = {"accises_par_decile_eur": moyennes, "rapport_d10_d1": rapport,
                     "budget_vert": PROFIL_BUDGET_VERT, "pronostic": PRONOSTICS["profil"],
                     "dans_pronostic": dans(rapport, PRONOSTICS["profil"])}

    out["verdict"] = ("tenue" if all(out[k]["tenue"] for k in TOLERANCES) else
                      "hors tolérance : le but s'arrête (D-323)")
    return out


def rendre(r: dict) -> str:
    def md(x: float) -> str:
        return f"{x / 1e9:,.1f}".replace(",", " ").replace(".", ",")

    def pc(x: float) -> str:
        return f"{x * 100:+.1f} %".replace(".", ",")

    t, c, a, p, cv = r["tva"], r["carburants"], r["accises"], r["profil"], r["couverture"]
    lignes = [
        "# La consommation imputée contre les agrégats publiés, 2024 (D-323, D-324)", "",
        f"Passe de la population de {r['annee']}, {r['menages_echantillon']:,} ménages "
        f"tirés.".replace(",", " "),
        "", f"**Verdict : {r['verdict']}.**", "",
        "| vérification | moteur (Md€) | cible (Md€) | écart | tolérance | pronostic |",
        "|---|---:|---:|---:|---|---|",
        f"| TVA des ménages, taux principal | {md(t['principal_eur'])} | "
        f"{md(t['cible_eur'])} | {pc(t['ecart'])} | "
        f"{'tenue' if t['tenue'] else '**hors**'} | "
        f"{'dans' if t['dans_pronostic'] else 'hors'} |",
        f"| TVA, postes mêlés au plus bas | {md(t['bas_eur'])} | | {pc(t['ecart_bas'])} | | |",
        f"| TVA, postes mêlés au plus haut | {md(t['haut_eur'])} | | {pc(t['ecart_haut'])} "
        "| | |",
        f"| carburants | {md(c['imputee_eur'])} | {md(c['sdes_eur'])} | {pc(c['ecart'])} | "
        f"{'tenue' if c['tenue'] else '**hors**'} | "
        f"{'dans' if c['dans_pronostic'] else 'hors'} |",
        f"| accises sur l'énergie | {md(a['menages_eur'])} | {md(a['cible_eur'])} | "
        f"{pc(a['ecart'])} | {'tenue' if a['tenue'] else '**hors**'} | "
        f"{'dans' if a['dans_pronostic'] else 'hors'} |",
        f"| consommation imputée / comptes | {md(cv['imputee_eur'])} | {md(cv['comptes_eur'])} "
        f"| {cv['part']:.1%} de la cible | mesure | "
        f"{'dans' if cv['dans_pronostic'] else 'hors'} |",
        "", "Le rendement d'un point de TVA, ménages contre Trésor-Éco n° 371 (net des APU) :",
        "", "| taux | ménages (Md€) | Trésor (Md€) | rapport | pronostic 0,55–0,95 |",
        "|---:|---:|---:|---:|---|"]
    for taux, v in r["point"]["taux"].items():
        lignes.append(f"| {taux} | {md(v['menages_eur'])} | {md(v['tresor_eur'])} | "
                      f"{v['rapport']:.2f} | {'dans' if v['dans_pronostic'] else 'hors'} |")
    lignes += ["", f"Le profil des accises : D10 / D1 = {p['rapport_d10_d1']:.2f} (Budget vert "
               f"{p['budget_vert']:.2f}, pronostic 1,5–2,5 : "
               f"{'dans' if p['dans_pronostic'] else 'hors'}). Par décile, en euros par "
               "ménage : " + ", ".join(f"{x:.0f}" for x in p["accises_par_decile_eur"]) + ".",
               ""]
    return "\n".join(lignes)


def main() -> int:
    import polars as pl

    from impots.population.build import PROCESSED
    from impots.population.runner import run

    frame = pl.read_parquet(PROCESSED / f"population_{ANNEE}.parquet")
    resultat = run(frame, year=ANNEE, reform=None, tier="full", sample=ECHANTILLON,
                   impute_consommation=True)
    r = verifier(resultat.households)
    SORTIE.parent.mkdir(exist_ok=True)
    SORTIE.with_suffix(".json").write_text(json.dumps(r, indent=2, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    SORTIE.with_suffix(".md").write_text(rendre(r), encoding="utf-8")
    print(rendre(r))
    return 0 if r["verdict"] == "tenue" else 2


if __name__ == "__main__":
    raise SystemExit(main())
