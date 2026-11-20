"""Les agrégats des pages « La population » (but 25, volet `population`, D-453).

Une commande, une fois, sans passe sur la population :

    PYTHONPATH=src .venv/bin/python -m impots.site_population.agregats

Elle lit des fichiers qui existent déjà et écrit `reports/population/agregats.json`, que
le site lit (`impots site construire` ne lit jamais `data/`) :

* `data/processed/population_2024.parquet` et son manifeste : des sommes pondérées (âges,
  sexe, types de ménages, activité, logement, territoire, masses de revenus) et des
  comptes de ménages de l'échantillon par tranche de poids. AUCUN enregistrement : une
  tranche qui compte moins de `SEUIL` ménages de l'échantillon est fondue dans sa
  voisine ;
* `data/processed/jumeau_cellules_2024.manifest.json` : comment les 50 cellules ont été
  faites (D-409), leur commit, leur échantillon, leurs recoupements ;
* `data/processed/firm_cells_2023.json` : les 57 cellules d'entreprises et leur
  provenance (D-407) ;
* `reports/jumeau/entrees_navigateur.json`, `reports/verification/grille.json` et
  `etudes/cadres/central.json`, commités : les cellules telles que le jumeau les lit, la
  grille de vérification (D-371), les indices du vieillissement.

RIEN N'EST CALCULÉ QUI CONTREDISE UN RAPPORT. Les comptes viennent de la population
publiée par le manifeste (son empreinte est gardée) ; les écarts à la France sont ceux
de la grille commitée, recopiés ; les totaux calés sont ceux de `population.margins`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import date
from itertools import pairwise
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"
POPULATION = PROCESSED / "population_2024.parquet"
MANIFESTE = PROCESSED / "population_2024.manifest.json"
CELLULES_MANIFESTE = PROCESSED / "jumeau_cellules_2024.manifest.json"
FIRMES = PROCESSED / "firm_cells_2023.json"
ENTREES = ROOT / "reports" / "jumeau" / "entrees_navigateur.json"
GRILLE = ROOT / "reports" / "verification" / "grille.json"
CADRE = ROOT / "etudes" / "cadres" / "central.json"
SORTIE = ROOT / "reports" / "population" / "agregats.json"
COMMANDE = "PYTHONPATH=src .venv/bin/python -m impots.site_population.agregats"
#: Le plus petit nombre de ménages de l'échantillon qu'un compte publié porte.
SEUIL = 20
#: Les bornes des tranches de poids d'un ménage (combien de vrais ménages il représente).
BORNES_POIDS = (0, 50, 75, 100, 125, 150, 175, 200, 250, 300, 400, 600, 10_000)
#: Les tranches d'âge de la pyramide.
AGES = tuple(range(0, 100, 5))


class AgregatsError(ValueError):
    """Un agrégat qui ne se calcule pas comme promis."""


def _sha256(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


def _commit() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def _population(frame: Any) -> dict[str, Any]:
    """Les sommes pondérées de la population : jamais une ligne."""
    import numpy as np
    import polars as pl

    from impots.jumeau.cellules import types_menages

    w = frame["weight"]
    menages = (frame.group_by("household_id")
               .agg(pl.col("weight").mean().alias("poids"), pl.len().alias("n"),
                    pl.col("departement").first(), pl.col("region").first())
               .join(types_menages(frame), on="household_id")
               .join(frame.filter(pl.col("role_menage") == "personne_de_reference")
                     .select("household_id", "statut_occupation"), on="household_id"))
    poids = menages["poids"].to_numpy()

    def compte(masque: Any) -> float:
        return float(np.asarray(w.filter(masque).sum()))

    # La pyramide : personnes pondérées par tranche de cinq ans et par sexe.
    age = frame["age"].to_numpy()
    sexe = frame["sex"].to_numpy()
    wp = w.to_numpy()
    pyramide = []
    for a in AGES:
        dans = (age >= a) & (age < a + 5) if a < 95 else age >= a
        pyramide.append({"age": f"{a}-{a + 4}" if a < 95 else "95+",
                         "femmes": float(wp[dans & (sexe == "female")].sum()),
                         "hommes": float(wp[dans & (sexe == "male")].sum())})

    # Le poids : combien de vrais ménages un ménage simulé représente.
    tranches = []
    for bas, haut in pairwise(BORNES_POIDS):
        dans = (poids >= bas) & (poids < haut)
        tranches.append({"de": bas, "a": haut, "menages_echantillon": int(dans.sum()),
                         "menages_representes": float(poids[dans].sum())})
    # Une tranche trop mince est fondue dans sa voisine, du bord vers le centre.
    while any(t["menages_echantillon"] < SEUIL for t in tranches) and len(tranches) > 1:
        i = next(k for k, t in enumerate(tranches) if t["menages_echantillon"] < SEUIL)
        j = i + 1 if i == 0 else i - 1
        a, b = sorted((i, j))
        tranches[a:b + 1] = [{"de": tranches[a]["de"], "a": tranches[b]["a"],
                              "menages_echantillon": tranches[a]["menages_echantillon"]
                              + tranches[b]["menages_echantillon"],
                              "menages_representes": tranches[a]["menages_representes"]
                              + tranches[b]["menages_representes"]}]
    tranches[-1]["a"] = None
    q = np.quantile(poids, [0.1, 0.5, 0.9])

    types = {t: float(menages.filter(pl.col("type") == t)["poids"].sum())
             for t in ("seul", "monoparentale", "couple_sans_enfant",
                       "couple_avec_enfants", "complexe")}
    # La typologie du calage (`calibrate.household_type`, lue sans être modifiée) : un
    # enfant majeur chez ses parents y reste un enfant de la famille. Celle des cellules
    # (`cellules.types_menages`) le range en ménage complexe : les deux sont publiées.
    from impots.population.calibrate import household_type

    cal = (household_type(frame).group_by("household_id")
           .agg(pl.col("hh_type").first(), pl.col("weight").mean()))
    types_calage = {t: float(cal.filter(pl.col("hh_type") == t)["weight"].sum())
                    for t in ("personne_seule", "monoparentale", "couple_sans_enfant",
                              "couple_avec_enfant", "complexe")}
    occupation = {}
    for statut in ("proprietaire", "primo_accedant", "locataire_hlm", "locataire_vide",
                   "locataire_meuble", "loge_gratuitement"):
        occupation[statut] = float(menages.filter(
            pl.col("statut_occupation") == statut)["poids"].sum())
    territoire = {"metropole": float(menages.filter(pl.col("region") == "metropole")
                                     ["poids"].sum())}
    for dep in ("971", "972", "973", "974"):
        territoire[dep] = float(menages.filter(pl.col("departement") == dep)["poids"].sum())

    statut = frame["statut_activite"]
    synth = frame["synthetic"]
    activite = {
        "en_emploi_salarie": compte((statut == "employed") & frame["is_salarie"]),
        "en_emploi_non_salarie": compte((statut == "employed") & ~frame["is_salarie"]),
        "chomeurs": compte(statut == "unemployed"),
        "inactifs_15_ans_et_plus": compte(statut == "inactive"),
        "enfants_crees": compte(synth),
    }
    revenus = {}
    for nom, colonne in (("salaires_bruts", "salaire_brut_annuel"),
                         ("pensions", "pension_annuelle"),
                         ("allocations_chomage", "chomage_annuel"),
                         ("revenus_non_salaries", "revenu_non_salarie_annuel")):
        x = frame[colonne].fill_null(0.0)
        revenus[nom] = {"total": float((x * w).sum()), "personnes": compte(x > 0)}
    return {
        "lignes": frame.height, "menages_echantillon": menages.height,
        "menages": float(poids.sum()), "personnes": float(wp.sum()),
        "personnes_observees": int((~synth).sum()), "enfants_crees_echantillon":
            int(synth.sum()),
        "poids": {"moyen": float(poids.mean()), "d1": float(q[0]), "mediane": float(q[1]),
                  "d9": float(q[2]), "tranches": tranches},
        "taille_moyenne": float(wp.sum() / poids.sum()),
        "pyramide": pyramide, "types": types, "types_calage": types_calage, "occupation": occupation,
        "territoire": territoire, "activite": activite,
        "secteur_public": compte(frame["secteur_public"].fill_null(False)
                                 & (statut == "employed")),
        "revenus": revenus,
    }


def _calees() -> list[dict[str, Any]]:
    """Les totaux publiés que la population reproduit par construction (le calage)."""
    from impots.population import margins

    lignes = [
        ("Ménages, par type", margins.HOUSEHOLD_TYPES, "menages"),
        ("Résidences principales, par statut d'occupation", margins.HOUSEHOLDS_BY_TENURE,
         "menages"),
        ("Masse des salaires bruts (champ de l'enquête)", margins.TOTAL_GROSS_WAGES,
         "salaires_bruts"),
        ("Pensions de retraite déclarées", margins.DECLARED_PENSIONS, "pensions"),
        ("Allocations chômage versées", margins.UNEMPLOYMENT_BENEFIT_SPEND,
         "allocations_chomage"),
        ("Revenus des non-salariés", margins.SELF_EMPLOYMENT_INCOME,
         "revenus_non_salaries"),
    ]
    champ = margins.CHAMP_SALARIES_ENQUETE.value
    out = []
    for libelle, fig, cle in lignes:
        valeur = fig.value * (champ if fig is margins.TOTAL_GROSS_WAGES else 1.0)
        out.append({"ligne": libelle, "cle": cle, "publie": valeur, "annee": fig.year,
                    "source": fig.source, "url": fig.url,
                    "note": (f"D11 × {champ:.4f}, la part des salariés que l'enquête "
                             f"couvre" if fig is margins.TOTAL_GROSS_WAGES else "")})
    return out


def _cibles_types() -> dict[str, Any]:
    from impots.population import margins

    t = margins.HOUSEHOLDS_BY_TYPE
    return {"seul": t["personne_seule"], "monoparentale": t["monoparentale"],
            "couple_sans_enfant": t["couple_sans_enfant"],
            "couple_avec_enfants": t["couple_avec_enfant"], "complexe": t["complexe"],
            "occupation": margins.tenure_targets(),
            "dom": dict(margins.DOM_HOUSEHOLDS_BY_DEPARTEMENT)}


def _grille(annee: int = 2024) -> list[dict[str, Any]]:
    """Les lignes de la grille commitée (D-371), recopiées pour l'année de la population."""
    grille = json.loads(GRILLE.read_text(encoding="utf-8"))
    garder = ("id", "ligne", "publie", "simule", "ecart", "tolerance", "usage", "verdict",
              "source", "url", "remarque", "remplacee_par")
    return [{k: ligne.get(k) for k in garder} for ligne in grille["lignes"]
            if ligne["annee"] == annee]


def _firmes() -> dict[str, Any]:
    import json as _json

    d = _json.loads(FIRMES.read_text(encoding="utf-8"))
    manifeste = _json.loads((ROOT / "data" / "raw" / "MANIFEST.json").read_text(
        encoding="utf-8"))
    fichiers = manifeste.get("files", manifeste)
    sources = {cle: {"fichier": nom, "url": fichiers.get(nom, {}).get("url"),
                     "licence": fichiers.get(nom, {}).get("licence")}
               for cle, nom in d["provenance"]["sources"].items()}
    garder = ("naf_section", "taille", "n_firms", "turnover_total", "value_added_total",
              "result_total", "p_loss")
    prov = d["provenance"]
    return {"millesime": d["vintage"], "synthetiques": d["cells_are_synthetic"],
            "cellules": [{k: c.get(k) for k in garder} for c in d["cells"]],
            "sources": sources, "fiscal_sur_comptable": prov["fiscal_to_accounting"],
            "entreprises_esane": prov["esane_firms"],
            "entreprises_is": prov["is_liable_firms"],
            "part_is_par_taille": prov["is_share_by_size"],
            "cellules_secretisees": prov["suppressed_cells"],
            "p_perte_source": prov["p_loss_source"],
            "empreinte": _sha256(FIRMES)}


def extraire() -> dict[str, Any]:
    import polars as pl

    for chemin in (POPULATION, MANIFESTE, CELLULES_MANIFESTE, FIRMES, ENTREES, GRILLE):
        if not chemin.exists():
            raise AgregatsError(f"{chemin} absent : `make data`, ou le relier depuis un "
                                f"checkout qui l'a")
    manifeste = json.loads(MANIFESTE.read_text(encoding="utf-8"))
    frame = pl.read_parquet(POPULATION)
    if frame.height != manifeste["rows"]:
        raise AgregatsError(f"{POPULATION.name} : {frame.height} lignes, le manifeste en "
                            f"dit {manifeste['rows']}")
    cel = json.loads(CELLULES_MANIFESTE.read_text(encoding="utf-8"))
    empreinte = _sha256(POPULATION)
    if cel.get("population_sha256") not in (None, empreinte):
        raise AgregatsError("les cellules n'ont pas été faites sur cette population")
    entrees = json.loads(ENTREES.read_text(encoding="utf-8"))
    cadre = json.loads(CADRE.read_text(encoding="utf-8"))
    eec = manifeste["inputs"]["FD_EEC_2024.parquet"]
    return {
        "version": 1,
        "commande": COMMANDE,
        "commit": _commit(),
        "date": date.today().isoformat(),
        "population_fichier": POPULATION.name,
        "population_sha256": empreinte,
        "construction": {
            "millesime": manifeste["vintage"], "construite": manifeste["built"],
            "graine": manifeste["seed"], "branche": manifeste["branch"],
            "enquete_url": eec["url"], "squelette": manifeste["skeleton"],
            "revenus": manifeste["incomes"], "calage": manifeste["raking"],
            "familles_jeunes": manifeste.get("familles_jeunes"),
            "mois_travailles": manifeste.get("mois_travailles"),
            "sources": len(manifeste["inputs"]),
        },
        "vieillissement": {"de": int(manifeste["vintage"]),
                           "salaires": cadre["uprating"]["wage"],
                           "prix": cadre["growth"]["prices"],
                           "source": cadre["uprating"]["source"],
                           "horizon": cadre["horizon"], "cadre": "etudes/cadres/central.json"},
        "population": _population(frame),
        "cibles": _cibles_types(),
        "calees": _calees(),
        "grille": _grille(),
        "cellules_menages": {
            "source": "reports/jumeau/entrees_navigateur.json",
            "annee": entrees["cellules"]["annee"], "types": entrees["cellules"]["types"],
            "valeurs": entrees["cellules"]["valeurs"],
            "construites": cel["construit"], "commit": cel["commit"],
            "echantillon": cel["menages_echantillon"], "graine": cel["graine"],
            "imputations": cel["passe"]["imputations"],
            "recoupements": cel["recoupements"]},
        "cellules_entreprises": _firmes(),
    }


def ecrire(chemin: Path = SORTIE) -> Path:
    contenu = extraire()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, indent=1, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    return chemin


def lire(chemin: Path = SORTIE) -> dict[str, Any]:
    return json.loads(chemin.read_text(encoding="utf-8"))


if __name__ == "__main__":
    print(f"-> {ecrire().relative_to(ROOT)}")
