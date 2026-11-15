"""Les cellules de ménages du jumeau (but 23, lot 4, D-409) : la population résumée.

POURQUOI DES CELLULES. Le pas du jumeau ne lit aucun fichier et ne relance jamais
OpenFisca (CADRE.md §3, §5) : la population de ménages y entre une fois, résumée. Une
cellule est un groupe de ménages d'un même DÉCILE DE NIVEAU DE VIE et d'un même TYPE DE
MÉNAGE, dix déciles fois cinq types, cinquante cellules :

* le décile, parce que les chocs statiques des mesures viennent par décile (§5, les
  rapports portent `mean_delta` et `n_households` par décile, `aggregate.DecileRow`), que
  la propension à consommer décroît avec le niveau de vie et que les gagnants et les
  perdants se lisent par décile ;
* le type (personne seule, famille monoparentale, couple sans enfant, couple avec
  enfants, ménage complexe), parce que c'est la typologie que l'Insee publie (recensement,
  `margins.HOUSEHOLD_TYPES`), que les élasticités d'offre de travail sont par
  configuration familiale (couples et personnes seules, `labour.groups`) et que
  l'exposition aux prestations et au chômage en dépend. Un découpage plus fin (l'âge, le
  statut d'occupation) multiplierait les cellules vides sur un sous-échantillon.

CE QU'UNE CELLULE PORTE, en euros de 2024, sommes pondérées : ménages, personnes, unités
de consommation ; les revenus (salaires brut, net, super-brut, imposable ; pensions ;
allocations chômage ; revenus non salariés) ; les prélèvements (cotisations salariales
et employeur, CSG et CRDS sur les salaires, impôt sur le revenu) ; les prestations ; le
revenu disponible ; la consommation imputée (enquête Budget de famille 2017, TF106,
`consommation.imputer`), la TVA et les accises qu'elle paie ; l'épargne, revenu
disponible moins consommation ; les personnes en emploi, salariées, au chômage (BIT, au
sens de l'enquête Emploi). En plus, pour toute la population de la passe : les parts de
la masse salariale brute des quatre groupes de l'offre de travail (C7, `labour.groups`).

COMMENT ELLES SE CONSTRUISENT, une fois (`scripts/jumeau_cellules.py`) : une passe
OpenFisca de référence, au droit de 2024, sur un sous-échantillon PPS de la population
(`runner.subsample`, jamais toute la population), avec les imputations des niches, du
capital, des indemnités journalières et de la consommation ; puis `construire`. Le
fichier est écrit hors git (`data/processed/jumeau_cellules_2024.json`) avec son
manifeste (commit, échantillon, empreinte de la population). Chaque total est recoupé à
la passe, à la population entière et à son agrégat publié (`recoupements`).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
FICHIER = ROOT / "data" / "processed" / "jumeau_cellules_2024.json"
ANNEE = 2024

N_DECILES = 10
TYPES = ("seul", "monoparentale", "couple_sans_enfant", "couple_avec_enfants", "complexe")
N_CELLULES = N_DECILES * len(TYPES)

#: Les prestations de la passe sommées en « prestations » (`engine.outputs`, tier full).
PRESTATIONS = ("af", "aeeh", "ppa", "rsa", "ass", "aide_logement", "aah", "mva", "aspa",
               "asi", "cf", "asf", "aefa", "ars", "paje", "ria", "allocation_enfant",
               "garantie_autonomie")
#: Les colonnes de la passe lues telles quelles, par ménage.
COLONNES_PASSE = {
    "salaire_brut": "salaire_brut", "salaire_net": "salaire_net",
    "salaire_super_brut": "salaire_super_brut", "salaire_imposable": "salaire_imposable",
    "cotisations_salariales": "cotisations_salariales",
    "cotisations_employeur": "cotisations_employeur", "retraite": "retraite_imposable",
    "chomage_brut": "chomage_brut", "ir": "ir", "revenu_disponible": "revenu_disponible",
    "consommation": "consommation_imputee", "tva": "tva_menages",
    "accises": "accises_energie",
}
#: Les variables d'une cellule, dans l'ordre du fichier.
VARIABLES = ("menages", "personnes", "uc", *COLONNES_PASSE, "csg_crds_salaires",
             "prestations", "revenus_non_salaries", "epargne", "en_emploi", "salaries",
             "chomeurs")
#: Les groupes de l'offre de travail (C7), dans l'ordre du magasin.
GROUPES_OFFRE = ("femmes_en_couple", "hommes_en_couple", "femmes_seules", "hommes_seuls")


class CellulesError(ValueError):
    """Des cellules qui ne se construisent ou ne se lisent pas."""


def indice(decile: int, type_: str) -> int:
    """La cellule (décile de 1 à 10, type), dans l'ordre décile puis type."""
    return (decile - 1) * len(TYPES) + TYPES.index(type_)


@dataclass(frozen=True)
class Cellules:
    """Les cinquante cellules : chaque variable, un tableau de forme (50,)."""

    valeurs: Mapping[str, np.ndarray]
    parts_offre: Mapping[str, float]
    """La part de chaque groupe de C7 dans la masse salariale brute de la passe ; le reste,
    hors de l'échantillon de l'article, n'a pas d'élasticité."""
    annee: int = ANNEE
    meta: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        manquantes = sorted(set(VARIABLES) - set(self.valeurs))
        if manquantes:
            raise CellulesError(f"variables absentes des cellules : {manquantes}")
        for nom, v in self.valeurs.items():
            if np.shape(v) != (N_CELLULES,):
                raise CellulesError(f"« {nom} » de forme {np.shape(v)}, attendu "
                                    f"({N_CELLULES},)")
            if not np.all(np.isfinite(v)):
                raise CellulesError(f"« {nom} » non fini")
        inconnus = sorted(set(self.parts_offre) - set(GROUPES_OFFRE))
        if inconnus:
            raise CellulesError(f"groupes d'offre inconnus {inconnus}")
        if not 0.0 <= sum(self.parts_offre.values()) <= 1.0 + 1e-12:
            raise CellulesError("parts de l'offre de travail hors de [0 ; 1]")

    def __getitem__(self, nom: str) -> np.ndarray:
        if nom not in self.valeurs:
            raise CellulesError(f"variable « {nom} » inconnue des cellules")
        return np.asarray(self.valeurs[nom], dtype=float)

    @property
    def deciles(self) -> np.ndarray:
        """Le décile (0 à 9) de chaque cellule."""
        return np.repeat(np.arange(N_DECILES), len(TYPES))

    def par_decile(self, nom: str) -> np.ndarray:
        """La variable sommée par décile, forme (10,)."""
        return self[nom].reshape(N_DECILES, len(TYPES)).sum(axis=1)

    def total(self, nom: str) -> float:
        return float(self[nom].sum())

    # ------------------------------------------------------------- le fichier
    def ecrire(self, chemin: Path = FICHIER) -> Path:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        contenu = {"annee": self.annee, "types": list(TYPES), "deciles": N_DECILES,
                   "valeurs": {k: [float(x) for x in self[k]] for k in VARIABLES},
                   "parts_offre": dict(self.parts_offre), "meta": dict(self.meta or {})}
        chemin.write_text(json.dumps(contenu, indent=1, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        return chemin

    @classmethod
    def lire(cls, chemin: Path = FICHIER) -> Cellules:
        if not chemin.exists():
            raise CellulesError(f"{chemin} absent : construire les cellules une fois "
                                f"(`scripts/jumeau_cellules.py`, D-409)")
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        if tuple(contenu["types"]) != TYPES or contenu["deciles"] != N_DECILES:
            raise CellulesError(f"{chemin.name} : un autre découpage que celui du code")
        return cls(valeurs={k: np.asarray(v, dtype=float)
                            for k, v in contenu["valeurs"].items()},
                   parts_offre=contenu["parts_offre"], annee=int(contenu["annee"]),
                   meta=contenu.get("meta"))


# --------------------------------------------------------------------------- #
# la construction, depuis une passe
# --------------------------------------------------------------------------- #
def types_menages(frame: Any) -> Any:
    """household_id → type, des rôles dans le ménage (`role_menage`) : un « autre » fait
    un ménage complexe ; sinon un conjoint fait un couple, avec ou sans enfant ; sinon un
    enfant fait une famille monoparentale ; sinon une personne seule. C'est la typologie
    de l'Insee, lue sur les rôles comme `margins.HOUSEHOLD_TYPES` (un enfant majeur reste
    un enfant du ménage)."""
    import polars as pl

    roles = frame.group_by("household_id").agg(
        (pl.col("role_menage") == "autre").any().alias("_autre"),
        (pl.col("role_menage") == "conjoint").any().alias("_conjoint"),
        (pl.col("role_menage") == "enfant").any().alias("_enfant"))
    type_ = (pl.when(pl.col("_autre")).then(pl.lit("complexe"))
             .when(pl.col("_conjoint") & pl.col("_enfant")).then(pl.lit("couple_avec_enfants"))
             .when(pl.col("_conjoint")).then(pl.lit("couple_sans_enfant"))
             .when(pl.col("_enfant")).then(pl.lit("monoparentale"))
             .otherwise(pl.lit("seul")))
    return roles.select("household_id", type_.alias("type"))


def construire(households: Any, persons: Any, frame: Any,
               meta: Mapping[str, Any] | None = None) -> Cellules:
    """Les cellules d'une passe de référence (`RunResult.households` et `.persons`) sur
    `frame`, la population (ou le sous-échantillon) qu'elle a calculée.

    Le décile est celui du niveau de vie de la passe (revenu disponible par unité de
    consommation, échelle de l'OCDE modifiée), rangé sur le poids des ménages
    (`aggregate.weighted_decile_index`), comme les rapports le rangent. Les comptes de
    personnes sont pondérés par le poids de chaque personne dans la passe."""
    from impots.behavioural.labour import groups
    from impots.population.aggregate import consumption_units, weighted_decile_index

    manquantes = sorted({*COLONNES_PASSE.values(), "weight", "n_persons", "n_aged_14_plus",
                         "n_children_under_14", "csg_deductible", "csg_imposable", "crds"}
                        - set(households.columns))
    if manquantes:
        raise CellulesError(f"la passe n'a pas {manquantes} : une passe de tier « full » "
                            f"avec la consommation imputée")
    types = types_menages(frame)
    menages = households.join(types, on="household_id", how="left")
    if menages["type"].null_count():
        raise CellulesError("des ménages de la passe sans type : la population n'est pas "
                            "celle de la passe")
    poids = menages["weight"].to_numpy().astype(np.float64)
    uc = consumption_units(menages["n_aged_14_plus"].to_numpy(),
                           menages["n_children_under_14"].to_numpy())
    rd = menages["revenu_disponible"].to_numpy().astype(np.float64)
    decile = weighted_decile_index(rd / uc, poids)
    cellule = decile * len(TYPES) + np.array([TYPES.index(t) for t in menages["type"]])

    def somme(par_menage: np.ndarray, w: np.ndarray = poids, c: np.ndarray = cellule
              ) -> np.ndarray:
        return np.bincount(c, weights=par_menage * w, minlength=N_CELLULES)

    out: dict[str, np.ndarray] = {
        "menages": somme(np.ones_like(poids)),
        "personnes": somme(menages["n_persons"].to_numpy().astype(np.float64)),
        "uc": somme(uc)}
    for nom, colonne in COLONNES_PASSE.items():
        out[nom] = somme(menages[colonne].to_numpy().astype(np.float64))
    out["csg_crds_salaires"] = somme(sum(menages[c].to_numpy().astype(np.float64)
                                         for c in ("csg_deductible", "csg_imposable", "crds")))
    out["prestations"] = somme(sum(menages[c].to_numpy().astype(np.float64)
                                   for c in PRESTATIONS if c in menages.columns))
    out["epargne"] = out["revenu_disponible"] - out["consommation"]

    # Les personnes : leur poids dans la passe, leur ménage, leur statut dans la population.
    vers_cellule = dict(zip(menages["household_id"].to_list(), cellule.tolist(),
                            strict=True))
    gens = persons.select("person_id", "household_id", "weight").join(
        frame.select("person_id", "statut_activite", "is_salarie",
                     "revenu_non_salarie_annuel"), on="person_id", how="left")
    c_p = np.array([vers_cellule[h] for h in gens["household_id"].to_list()])
    w_p = gens["weight"].to_numpy().astype(np.float64)
    statut = gens["statut_activite"].to_numpy()
    emploi = statut == "employed"
    out["revenus_non_salaries"] = somme(
        gens["revenu_non_salarie_annuel"].fill_null(0.0).to_numpy().astype(np.float64),
        w_p, c_p)
    out["en_emploi"] = somme(emploi.astype(float), w_p, c_p)
    out["salaries"] = somme((emploi & gens["is_salarie"].to_numpy()).astype(float), w_p, c_p)
    out["chomeurs"] = somme((statut == "unemployed").astype(float), w_p, c_p)

    # Les parts de la masse salariale des groupes de C7, sur les personnes de la passe.
    g = groups(frame).join(persons.select("person_id", "weight"), on="person_id",
                           how="inner")
    masse = (g["salaire_brut_annuel"] * g["weight"]).to_numpy()
    total = float(masse.sum())
    if total <= 0:
        raise CellulesError("aucune masse salariale dans la passe")
    noms = g["group"].to_numpy()
    parts = {grp: float(masse[noms == grp].sum() / total) for grp in GROUPES_OFFRE}
    return Cellules(valeurs=out, parts_offre=parts, meta=dict(meta or {}))


# --------------------------------------------------------------------------- #
# les recoupements
# --------------------------------------------------------------------------- #
#: Les tolérances, écrites AVANT le premier calcul des cellules (D-409) et jamais
#: retouchées : celles de `population.reconcile.TOLERANCE` pour les lignes publiées (2 %
#: pour une marge de calibration, 15 % pour une statistique de distribution), et, contre
#: la population entière, l'erreur d'un sous-échantillon : 2 % pour une masse ou un
#: compte large, 8 % pour le chômage, ses allocations et les revenus non salariés,
#: portés par dix fois moins de ménages.
TOLERANCE_PASSE = 1e-9
TOLERANCE_POPULATION = {"salaire_brut": 0.02, "retraite": 0.02, "menages": 0.02,
                        "personnes": 0.02, "en_emploi": 0.02, "salaries": 0.02,
                        "chomage_brut": 0.08, "chomeurs": 0.08,
                        "revenus_non_salaries": 0.08}
TOLERANCE_PUBLIEE = {"calibration": 0.02, "distribution": 0.15}


@dataclass(frozen=True)
class Recoupement:
    ligne: str
    cellules: float
    reference: float
    source: str
    tolerance: float | None
    """None : l'écart est dit, sans verdict (une ligne que la population ne cale pas et
    dont l'écart est le sien, pas celui des cellules)."""

    @property
    def ecart(self) -> float:
        return self.cellules / self.reference - 1.0

    @property
    def tient(self) -> bool | None:
        return None if self.tolerance is None else abs(self.ecart) <= self.tolerance


def totaux_population(frame: Any) -> dict[str, float]:
    """Les totaux de la population entière que les cellules recoupent sans passe : ses
    revenus bruts et ses comptes, pondérés (le poids d'un ménage est la moyenne de ses
    membres, comme `runner.run`)."""
    import polars as pl

    w = frame["weight"]
    statut = frame["statut_activite"]
    emploi = statut == "employed"
    return {
        "salaire_brut": float((frame["salaire_brut_annuel"] * w).sum()),
        "retraite": float((frame["pension_annuelle"] * w).sum()),
        "chomage_brut": float((frame["chomage_annuel"] * w).sum()),
        "revenus_non_salaries": float((frame["revenu_non_salarie_annuel"] * w).sum()),
        "personnes": float(w.sum()),
        "menages": float(frame.group_by("household_id").agg(pl.col("weight").mean())
                         ["weight"].sum()),
        "en_emploi": float(w.filter(emploi).sum()),
        "salaries": float(w.filter(emploi & frame["is_salarie"]).sum()),
        "chomeurs": float(w.filter(statut == "unemployed").sum()),
    }


def mediane_niveau_de_vie(cellules: Cellules) -> float:
    """La médiane du niveau de vie, lue sur les cellules : la frontière des déciles 5 et 6
    approchée par le milieu des niveaux de vie moyens des deux déciles (une cellule n'a
    pas de distribution interne)."""
    rd = cellules.par_decile("revenu_disponible")
    uc = cellules.par_decile("uc")
    return float(0.5 * (rd[4] / uc[4] + rd[5] / uc[5]))


def recoupements(cellules: Cellules, population: Mapping[str, float] | None = None
                 ) -> list[Recoupement]:
    """Chaque total des cellules contre la population entière (si donnée) et contre son
    agrégat publié (`population.margins`), avec sa tolérance écrite d'avance."""
    from impots.population import margins

    out: list[Recoupement] = []
    for nom, tol in TOLERANCE_POPULATION.items():
        if population is not None:
            out.append(Recoupement(f"{nom} / population entière", cellules.total(nom),
                                   population[nom], "population_2024.parquet", tol))
    cal = TOLERANCE_PUBLIEE["calibration"]
    champ = margins.CHAMP_SALARIES_ENQUETE.value
    out += [
        Recoupement("salaire_brut / D11 au champ de l'enquête", cellules.total(
            "salaire_brut"), margins.TOTAL_GROSS_WAGES.value * champ,
            f"{margins.TOTAL_GROSS_WAGES.source} × {champ:.4f} "
            f"(`margins.CHAMP_SALARIES_ENQUETE`)", cal),
        Recoupement("retraite / pensions déclarées", cellules.total("retraite"),
                    margins.DECLARED_PENSIONS.value, margins.DECLARED_PENSIONS.source, cal),
        Recoupement("chomage_brut / Unédic", cellules.total("chomage_brut"),
                    margins.UNEMPLOYMENT_BENEFIT_SPEND.value,
                    margins.UNEMPLOYMENT_BENEFIT_SPEND.source, cal),
        Recoupement("revenus_non_salaries / Insee Première 2114",
                    cellules.total("revenus_non_salaries"),
                    margins.SELF_EMPLOYMENT_INCOME.value,
                    margins.SELF_EMPLOYMENT_INCOME.source, cal),
        Recoupement("menages / recensement", cellules.total("menages"),
                    margins.HOUSEHOLDS.value, margins.HOUSEHOLDS.source, cal),
        Recoupement("en_emploi / enquête Emploi 2024", cellules.total("en_emploi"),
                    29_187_000.0, "Insee, ECRT 2026, fiche 2.1, figure 1 (2024)", cal),
        Recoupement("mediane du niveau de vie / Filosofi 2023",
                    mediane_niveau_de_vie(cellules), margins.NIVEAU_DE_VIE_MEDIAN.value,
                    margins.NIVEAU_DE_VIE_MEDIAN.source, TOLERANCE_PUBLIEE["distribution"]),
        Recoupement("ir / recettes nettes", cellules.total("ir"),
                    margins.IR_NET_YIELD.value, margins.IR_NET_YIELD.source, None),
        Recoupement("chomeurs / BIT 2024", cellules.total("chomeurs"), 2_342_800.0,
                    "Insee, enquête Emploi, séries longues, t. 302 (2024)", None),
    ]
    return out
