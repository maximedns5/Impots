"""Les données de ménages qui manquent aux mesures des programmes (but 21, étape 4).

La population est construite sans heures supplémentaires, sans frais de trajet, sans
pensions alimentaires, sans frais de garde et sans intérêts d'emprunt : une mesure qui
porte sur l'une d'elles (une exonération des heures supplémentaires, un crédit d'impôt sur
les trajets, des pensions perçues défiscalisées, un plafond de frais de garde relevé, une
réduction d'impôt sur les intérêts de la résidence principale) ne bougerait rien. Ce
module les impute, chacune calée sur un total publié qu'elle nomme (`margins`), quand une
passe demande l'imputation « menages » (`population.imputations`).

**C'est une calibration, et elle dépense ses sources.** Chaque total imputé est celui de sa
source par construction (au tirage près pour les nombres) : il ne prouve rien, et chaque
`Figure` porte `use="calibration"`. Ce qu'il achète : qu'une mesure sur ces données ne
coûte plus un zéro confiant, et que son incidence se calcule. Ce qu'il ne dit pas : qui en
a vraiment. Chaque règle de répartition est une hypothèse, dite dans la `Figure` et ici.

LES SEPT DONNÉES, et ce que la passe en fait :

1. **Les heures supplémentaires exonérées** (cases 1GH à 1JH, 21,83 Md€, 12,85 M lignes).
   Un tirage uniforme parmi les salariés hors gérants (aucune ventilation publiée par
   catégorie), au champ de l'enquête ; un montant au prorata du salaire horaire et de la
   quotité, plafonné à 7 500 € (CGI art. 81 quater), donc des heures communes ; les heures
   en sont déduites (majoration de 25 %, net imposable). Le montant est pris dans la part
   exonérée des salaires (correction 24) qui le portait uniformément : le total exonéré
   ne bouge pas, il se déplace vers ceux qui font des heures. Les salaires ne bougent pas :
   D11 les contenait déjà.
2. **Les frais de trajet et les frais réels** (cases 1AK à 1DK, 35,31 Md€, 5,87 M lignes).
   Chaque salarié a des frais de trajet tirés d'une loi log-normale, au prorata du temps
   travaillé ; il les déclare en frais réels quand ils dépassent sa déduction de 10 %. Les
   deux paramètres de la loi sont fixés pour que les déclarants et leurs frais refassent
   les deux totaux. Hypothèse : les frais réels sont des frais de trajet. Openfisca lit
   `frais_reels`.
3. **Les pensions alimentaires perçues** (1AO à 1DO, 5,55 Md€) : à un parent isolé qui a un
   enfant à charge, au prorata de ses enfants. Openfisca lit `pensions_alimentaires_percues`.
4. **Les pensions alimentaires versées** (6GU et 6GP, 4,84 Md€ ; 6EL, 6EM, 6GI, 6GJ,
   4,24 Md€) : par une personne seule de 25 à 64 ans sans personne à charge, et par un
   déclarant de 45 à 70 ans sans personne à charge. Openfisca lit `f6gu` et `f6el`.
5. **Les frais de garde des moins de six ans** (7GA à 7GG, 4,61 Md€, 2,33 M enfants) : à un
   enfant de moins de six ans à charge dont tous les adultes du foyer travaillent, des frais
   tirés d'une loi gamma de forme 2. Openfisca lit `f7ga`, `f7gb`, `f7gc`, à la place de la
   case 7GA que l'imputation des niches tire par décile sans regarder l'âge des enfants.
6. **Les intérêts d'emprunt de la résidence principale** (compte du logement 2024,
   18,64 Md€) : à chaque ménage accédant, au prorata de son revenu et décroissant avec
   l'âge de sa personne de référence. Aucune variable d'openfisca ne les lit : la réduction
   d'impôt qui en dépendait a pris fin ; une mesure qui la rétablit les trouvera ici.
7. **L'emploi à domicile** (7DB, 15,37 Md€) n'est pas imputé ici : `niches` le fait déjà,
   sur la table par décile de la DGFiP. `ecart_emploi_domicile` compare cette table au
   total de la 2042, deux publications indépendantes.

Les montants sont ceux de 2024. Une autre année demanderait de les vieillir, ce qui n'est
pas fait : elle est refusée par son nom, comme les IJ (D-305).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import polars as pl

from impots.donnees import RAW
from impots.population import margins
from impots.reporting import Figure

YEAR = 2024
DECLARATIONS_FILE = "dgfip_ir_2042_nat_export_2026-10-15.csv"
SEED = 20261112

#: Les cases de la 2042 de chaque donnée : (cases du montant, cases du nombre).
CASES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "heures_sup": (("1GH", "1HH", "1IH", "1JH"), ("1GH", "1HH", "1IH", "1JH")),
    "frais_reels": (("1AK", "1BK", "1CK", "1DK"), ("1AK", "1BK", "1CK", "1DK")),
    "pensions_percues": (("1AO", "1BO", "1CO", "1DO"), ("1AO", "1BO")),
    "pensions_versees_mineurs": (("6GU", "6GP"), ("6GU", "6GP")),
    "pensions_versees_majeurs": (("6EL", "6EM", "6GI", "6GJ"), ("6EL", "6GI")),
    "frais_garde": (("7GA", "7GB", "7GC", "7GE", "7GF", "7GG"),
                    ("7GA", "7GB", "7GC", "7GE", "7GF", "7GG")),
}
#: La `Figure` de chaque donnée ; `declare` refuse un export qui ne la refait pas.
FIGURES: dict[str, Figure] = {
    "heures_sup": margins.HEURES_SUP_DECLAREES,
    "frais_reels": margins.FRAIS_REELS_DECLARES,
    "pensions_percues": margins.PENSIONS_ALIMENTAIRES_PERCUES,
    "pensions_versees_mineurs": margins.PENSIONS_ALIMENTAIRES_VERSEES["mineurs"],
    "pensions_versees_majeurs": margins.PENSIONS_ALIMENTAIRES_VERSEES["majeurs"],
    "frais_garde": margins.FRAIS_GARDE_DECLARES,
}

#: Les colonnes que l'imputation ajoute. Les montants sont annuels, en euros ; ceux d'un
#: foyer sont portés par son déclarant principal, ceux d'un ménage par sa personne de
#: référence, les frais de garde par l'enfant gardé.
HEURES_SUP = "heures_sup_annuel"
HEURES_SUP_HEURES = "heures_sup_heures"
FRAIS_TRAJET = "frais_trajet_annuel"
FRAIS_REELS = "frais_reels_annuel"
PENSION_PERCUE = "pension_alimentaire_percue_annuel"
PENSION_VERSEE_MINEURS = "pension_alimentaire_versee_mineurs_annuel"
PENSION_VERSEE_MAJEURS = "pension_alimentaire_versee_majeurs_annuel"
FRAIS_GARDE = "frais_garde_annuel"
INTERETS_EMPRUNT = "interets_emprunt_rp_annuel"
COLONNES = (HEURES_SUP, HEURES_SUP_HEURES, FRAIS_TRAJET, FRAIS_REELS, PENSION_PERCUE,
            PENSION_VERSEE_MINEURS, PENSION_VERSEE_MAJEURS, FRAIS_GARDE, INTERETS_EMPRUNT)

#: Ce qu'openfisca lit des colonnes : (variable, entité où la colonne vit). Les intérêts
#: d'emprunt, les frais de trajet et les heures n'ont pas de variable : la part exonérée
#: porte les heures supplémentaires (correction 24), les frais réels portent les trajets
#: déclarés.
ENTREES_OPENFISCA: dict[str, tuple[str, str]] = {
    FRAIS_REELS: ("frais_reels", "individu"),
    PENSION_PERCUE: ("pensions_alimentaires_percues", "individu"),
    PENSION_VERSEE_MINEURS: ("f6gu", "foyer_fiscal"),
    PENSION_VERSEE_MAJEURS: ("f6el", "foyer_fiscal"),
}
#: Les cases des frais de garde, enfant par enfant, dans l'ordre des `person_id`.
CASES_GARDE = ("f7ga", "f7gb", "f7gc")
#: Les cases de l'imputation des niches que celle-ci remplace quand les deux tournent.
REMPLACE_NICHES = frozenset({"f7ga"})

#: Le plafond d'exonération des heures supplémentaires, par an et par personne (CGI art.
#: 81 quater, I, depuis 2019).
PLAFOND_HEURES_SUP = 7_500.0
#: La majoration légale des huit premières heures (C. trav. art. L. 3121-36).
MAJORATION_HEURES_SUP = 1.25
#: Le net imposable d'une heure supplémentaire sur son brut : les cotisations salariales de
#: retraite en sont réduites (CSS art. L. 241-17) et la CSG déductible (6,8 % sur 98,25 %)
#: seule en sort.
HEURES_SUP_IMPOSABLE_SUR_BRUT = 1.0 - 0.068 * 0.9825
#: Les heures d'un temps plein par mois, celles du SMIC mensuel.
HEURES_MENSUELLES = 151.67
#: La déduction forfaitaire de 10 % des salaires, revenus 2024 (CGI art. 83, 3°) : taux,
#: minimum et maximum par personne, relus dans l'arbre d'openfisca par le test.
DEDUCTION_TAUX, DEDUCTION_MIN, DEDUCTION_MAX = 0.10, 504.0, 14_426.0
#: Les âges des personnes qui versent une pension, par groupe (hypothèses).
AGES_VERSE_MINEURS = (25, 64)
AGES_VERSE_MAJEURS = (45, 70)
#: Les enfants gardés : moins de six ans au 1er janvier.
AGE_GARDE = 6
#: La forme de la loi gamma des frais de garde (une hypothèse : aucune dispersion publiée).
FORME_GARDE = 2.0
#: Le plafond des frais de garde retenus par enfant, revenus 2024 (CGI art. 200 quater B).
PLAFOND_GARDE = 3_500.0
#: L'âge où un prêt de résidence principale est supposé remboursé, et le plancher de la
#: part restante (hypothèses : aucune distribution publiée des intérêts par âge).
AGE_FIN_EMPRUNT, DUREE_EMPRUNT, PART_MIN_EMPRUNT = 65.0, 35.0, 0.1
#: L'écart toléré entre un total imputé et sa cible : la calibration est exacte, aux
#: bissections près (les nombres, eux, sont au tirage près).
TOLERANCE_MONTANT = 1e-3


class MenagesError(ValueError):
    """La source ne se lit pas comme attendu, ou l'imputation ne refait pas ses totaux."""


@dataclass(frozen=True)
class Composante:
    """Une donnée imputée contre son total publié."""

    nom: str
    source: str
    url: str
    cible_montant: float
    montant: float
    cible_nombre: float | None = None
    nombre: float | None = None
    depense: bool = True
    """Vrai quand le total est la cible de la calibration : son écart ne prouve rien."""
    note: str = ""

    @property
    def ecart_montant(self) -> float:
        return self.montant / self.cible_montant - 1.0 if self.cible_montant else 0.0

    @property
    def ecart_nombre(self) -> float | None:
        if self.cible_nombre in (None, 0) or self.nombre is None:
            return None
        return self.nombre / self.cible_nombre - 1.0


@dataclass(frozen=True)
class Stats:
    composantes: tuple[Composante, ...] = field(default_factory=tuple)

    def par_nom(self) -> dict[str, Composante]:
        return {c.nom: c for c in self.composantes}


def declare(nom: str, raw: Path | None = None) -> tuple[float, float]:
    """(nombre, montant) des cases de `nom` dans l'export 2042 manifesté, revenus 2024.

    Refuse un montant qui ne refait pas la `Figure` de la donnée : la figure et le fichier
    disent la même chose, ou l'un des deux est faux."""
    path = (raw or RAW) / DECLARATIONS_FILE
    if not path.exists():
        raise MenagesError(f"{path} absent : `make data` le télécharge")
    montants, nombres = CASES[nom]
    lignes: dict[str, tuple[float, float]] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle, delimiter=";"):
            if row["Année"] == str(YEAR) and row["Nom"] in set(montants) | set(nombres):
                lignes[row["Nom"]] = (float(row["Nombre"]), float(row["Montant"]))
    manquantes = sorted((set(montants) | set(nombres)) - set(lignes))
    if manquantes:
        raise MenagesError(f"cases {manquantes} absentes de {path.name} pour {YEAR}")
    nombre = sum(lignes[c][0] for c in nombres)
    montant = sum(lignes[c][1] for c in montants)
    figure = FIGURES[nom]
    if abs(montant - figure.value) > 1.0:
        raise MenagesError(f"{nom} : {path.name} donne {montant:,.0f} €, la figure "
                           f"{figure.value:,.0f} €")
    return nombre, montant


def _poids_menage(frame: pl.DataFrame) -> np.ndarray:
    """Le poids que l'agrégat lit, par personne : celui de son ménage, moyenne des poids
    de ses membres (`runner`, D-308)."""
    return (frame.select(pl.col("weight").mean().over("household_id"))
            .to_series().to_numpy().astype(np.float64))


def _mois(frame: pl.DataFrame) -> np.ndarray:
    if "mois_travailles" not in frame.columns:
        return np.full(frame.height, 12.0)
    bits = frame["mois_travailles"].fill_null(4095).to_numpy().astype(np.int64)
    mois = sum(((bits >> k) & 1) for k in range(12)).astype(np.float64)
    return np.where(mois > 0, mois, 12.0)


def salaire_horaire(frame: pl.DataFrame) -> np.ndarray:
    """Le salaire horaire brut de chacun : son salaire sur les heures d'un temps plein des
    mois qu'il travaille, à sa quotité. Zéro pour qui n'a pas de salaire."""
    brut = frame["salaire_brut_annuel"].to_numpy().astype(np.float64)
    quotite = frame["quotite_travail"].fill_null(1.0).to_numpy().astype(np.float64) \
        if "quotite_travail" in frame.columns else np.ones(frame.height)
    heures = HEURES_MENSUELLES * np.maximum(quotite, 1e-6) * _mois(frame)
    return np.where(brut > 0, brut / heures, 0.0)


def _gerant(frame: pl.DataFrame) -> np.ndarray:
    from impots.population.to_openfisca import GERANTS

    if "regime_non_salarie" not in frame.columns:
        return np.zeros(frame.height, dtype=bool)
    return frame["regime_non_salarie"].is_in(list(GERANTS)).fill_null(False).to_numpy()


def _bissection(f, lo: float, hi: float, cible: float, iterations: int = 200) -> float:
    """La racine de f(x) = cible pour f croissante sur [lo, hi]."""
    if f(hi) < cible:
        raise MenagesError(f"cible {cible:,.0f} hors d'atteinte (au plus {f(hi):,.0f})")
    for _ in range(iterations):
        mid = 0.5 * (lo + hi)
        if f(mid) < cible:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _tirage(eligible: np.ndarray, poids: np.ndarray, nombre: float,
            rng: np.random.Generator) -> tuple[np.ndarray, float]:
    """Qui en a : chaque éligible avec la probabilité `nombre / poids des éligibles`, plafonnée
    à un ; l'espérance du nombre pondéré est la cible quand la probabilité n'est pas
    plafonnée."""
    disponible = float(poids[eligible].sum())
    if disponible <= 0:
        raise MenagesError("aucun éligible : la population ne porte pas ce qu'il faut")
    p = min(nombre / disponible, 1.0)
    return eligible & (rng.random(eligible.shape) < p), p


def _heures_sup(frame: pl.DataFrame, poids: np.ndarray, rng: np.random.Generator,
                raw: Path | None) -> tuple[dict[str, np.ndarray], Composante]:
    from impots.population.incomes import EXEMPT_SHARE, IMPOSABLE_SUR_BRUT

    nombre, montant = declare("heures_sup", raw)
    champ = margins.CHAMP_SALARIES_ENQUETE.value
    nombre, montant = nombre * champ, montant * champ
    brut = frame["salaire_brut_annuel"].to_numpy().astype(np.float64)
    part = (frame[EXEMPT_SHARE].fill_null(0.0).to_numpy().astype(np.float64)
            if EXEMPT_SHARE in frame.columns else np.zeros(frame.height))
    quotite = frame["quotite_travail"].fill_null(1.0).to_numpy().astype(np.float64)
    horaire = salaire_horaire(frame)
    eligible = (brut > 0) & (part > 0) & ~_gerant(frame)
    tires, p = _tirage(eligible, poids, nombre, rng)
    base = np.where(tires, horaire * quotite, 0.0)
    imposable = IMPOSABLE_SUR_BRUT * brut
    # Le plafond légal, et jamais plus que la part exonérée ne pouvait porter.
    plafond = np.minimum(PLAFOND_HEURES_SUP, imposable)

    def total(c: float) -> float:
        return float((np.minimum(c * base, plafond) * poids).sum())

    c = _bissection(total, 0.0, 1e6, montant)
    hs = np.minimum(c * base, plafond)
    heures = np.where(hs > 0, hs / np.maximum(
        HEURES_SUP_IMPOSABLE_SUR_BRUT * MAJORATION_HEURES_SUP * horaire, 1e-9), 0.0)
    # La part exonérée : le même total, le reste réparti uniformément sur ceux qui en ont.
    exonere = float((part * imposable * poids).sum())
    reste = exonere - float((hs * poids).sum())
    if reste < 0:
        raise MenagesError(f"les heures supplémentaires ({montant:,.0f} €) dépassent la part "
                           f"exonérée des salaires ({exonere:,.0f} €)")
    porteurs = part > 0
    assiette = float((imposable * poids)[porteurs].sum())
    uniforme = reste / assiette
    nouvelle = np.where(porteurs, uniforme + np.where(imposable > 0, hs / np.maximum(
        imposable, 1e-9), 0.0), part)
    note = (f"tirés avec la probabilité {p:.3f} parmi les salariés hors gérants ; "
            f"{c / HEURES_SUP_IMPOSABLE_SUR_BRUT / MAJORATION_HEURES_SUP:.0f} heures par "
            f"an à temps plein avant le plafond ; part exonérée uniforme ramenée de "
            f"{float(np.median(part[porteurs])):.4f} à {uniforme:.4f}")
    figure = FIGURES["heures_sup"]
    return ({HEURES_SUP: hs, HEURES_SUP_HEURES: heures, EXEMPT_SHARE: nouvelle},
            Composante("heures_sup", figure.source, figure.url, montant,
                       float((hs * poids).sum()), nombre, float(poids[hs > 0].sum()),
                       note=note + " ; cibles ramenées au champ de l'enquête"))


def _frais_reels(frame: pl.DataFrame, poids: np.ndarray, rng: np.random.Generator,
                 raw: Path | None) -> tuple[dict[str, np.ndarray], Composante]:
    from impots.population.incomes import IMPOSABLE_SUR_BRUT

    nombre, montant = declare("frais_reels", raw)
    champ = margins.CHAMP_SALARIES_ENQUETE.value
    nombre, montant = nombre * champ, montant * champ
    brut = frame["salaire_brut_annuel"].to_numpy().astype(np.float64)
    quotite = frame["quotite_travail"].fill_null(1.0).to_numpy().astype(np.float64)
    salarie = brut > 0
    temps = np.where(salarie, quotite * _mois(frame) / 12.0, 0.0)
    deduction = np.clip(DEDUCTION_TAUX * IMPOSABLE_SUR_BRUT * brut, DEDUCTION_MIN,
                        DEDUCTION_MAX)
    z = rng.standard_normal(frame.height)
    w = np.where(salarie, poids, 0.0)

    def frais(mu: float, sigma: float) -> np.ndarray:
        return np.where(salarie, temps * np.exp(mu + sigma * z), 0.0)

    def mu_pour(sigma: float) -> float:
        return _bissection(lambda mu: float(w[frais(mu, sigma) > deduction].sum()),
                           -20.0, 20.0, nombre, iterations=80)

    def montant_pour(sigma: float) -> float:
        f = frais(mu_pour(sigma), sigma)
        return float((f * w)[f > deduction].sum())

    sigma = _bissection(montant_pour, 0.05, 3.0, montant, iterations=50)
    mu = mu_pour(sigma)
    trajet = frais(mu, sigma)
    declares = np.where(trajet > deduction, trajet, 0.0)
    figure = FIGURES["frais_reels"]
    note = (f"loi log-normale des frais de trajet à temps plein : médiane "
            f"{np.exp(mu):.0f} €, écart-type du logarithme {sigma:.3f} ; frais de trajet de tous les salariés "
            f"{float((trajet * w).sum()) / 1e9:.2f} Md€ (extrapolation de la loi) ; cibles "
            f"ramenées au champ de l'enquête")
    # Le montant est calé à la bissection près, et le nombre l'est exactement par μ.
    return ({FRAIS_TRAJET: trajet, FRAIS_REELS: declares},
            Composante("frais_reels", figure.source, figure.url, montant,
                       float((declares * w).sum()), nombre, float(w[declares > 0].sum()),
                       note=note))


def _foyers(frame: pl.DataFrame) -> pl.DataFrame:
    """Par personne : son foyer est-il en couple, combien de personnes à charge a-t-il,
    tous ses adultes ont-ils un revenu d'activité."""
    actif = (pl.col("salaire_brut_annuel") > 0)
    if "revenu_non_salarie_annuel" in frame.columns:
        actif = actif | (pl.col("revenu_non_salarie_annuel").fill_null(0.0) > 0)
    adulte = pl.col("role_foyer") != "personne_a_charge"
    return frame.select(
        (pl.col("role_foyer") == "conjoint").any().over("foyer_id").alias("couple"),
        (pl.col("role_foyer") == "personne_a_charge").sum().over("foyer_id")
        .alias("a_charge"),
        (actif | ~adulte).all().over("foyer_id").alias("adultes_actifs"),
    )


def _pensions(frame: pl.DataFrame, poids: np.ndarray, rng: np.random.Generator,
              raw: Path | None) -> tuple[dict[str, np.ndarray], list[Composante]]:
    foyers = _foyers(frame)
    principal = (frame["role_foyer"] == "declarant_principal").to_numpy()
    age = frame["age"].to_numpy()
    a_charge = foyers["a_charge"].to_numpy().astype(np.float64)
    couple = foyers["couple"].to_numpy()
    isole = frame["parent_isole"].fill_null(False).to_numpy().astype(bool)
    colonnes: dict[str, np.ndarray] = {}
    composantes = []

    nombre, montant = declare("pensions_percues", raw)
    tires, p = _tirage(principal & isole & (a_charge > 0), poids, nombre, rng)
    cle = np.where(tires, a_charge, 0.0)
    colonnes[PENSION_PERCUE] = cle * (montant / float((cle * poids).sum()))
    figure = FIGURES["pensions_percues"]
    composantes.append(Composante(
        "pensions_percues", figure.source, figure.url, montant,
        float((colonnes[PENSION_PERCUE] * poids).sum()), nombre,
        float(poids[tires].sum()),
        note=f"parents isolés tirés avec la probabilité {p:.3f}, montant par enfant"))

    for nom, colonne, (bas, haut), condition in (
            ("pensions_versees_mineurs", PENSION_VERSEE_MINEURS, AGES_VERSE_MINEURS,
             ~couple & (a_charge == 0)),
            ("pensions_versees_majeurs", PENSION_VERSEE_MAJEURS, AGES_VERSE_MAJEURS,
             a_charge == 0)):
        nombre, montant = declare(nom, raw)
        tires, p = _tirage(principal & condition & (age >= bas) & (age <= haut), poids,
                           nombre, rng)
        colonnes[colonne] = np.where(tires, montant / float(poids[tires].sum()), 0.0)
        figure = FIGURES[nom]
        composantes.append(Composante(
            nom, figure.source, figure.url, montant,
            float((colonnes[colonne] * poids).sum()), nombre, float(poids[tires].sum()),
            note=f"tirés avec la probabilité {p:.3f}, un montant égal"))
    return colonnes, composantes


def _garde(frame: pl.DataFrame, poids: np.ndarray, rng: np.random.Generator,
           raw: Path | None) -> tuple[dict[str, np.ndarray], Composante]:
    nombre, montant = declare("frais_garde", raw)
    foyers = _foyers(frame)
    enfant = ((frame["role_foyer"] == "personne_a_charge").to_numpy()
              & (frame["age"].to_numpy() < AGE_GARDE))
    eligible = enfant & foyers["adultes_actifs"].to_numpy()
    note = "enfants de moins de six ans dont tous les adultes du foyer travaillent"
    if float(poids[eligible].sum()) < nombre:
        eligible, note = enfant, "tous les enfants de moins de six ans à charge (les " \
            "foyers actifs n'en avaient pas assez)"
    tires, p = _tirage(eligible, poids, nombre, rng)
    tirage = rng.gamma(FORME_GARDE, 1.0 / FORME_GARDE, frame.height)
    cle = np.where(tires, tirage, 0.0)
    frais = cle * (montant / float((cle * poids).sum()))
    au_dessus = float(poids[frais > PLAFOND_GARDE].sum()) / float(poids[tires].sum())
    figure = FIGURES["frais_garde"]
    return ({FRAIS_GARDE: frais}, Composante(
        "frais_garde", figure.source, figure.url, montant, float((frais * poids).sum()),
        nombre, float(poids[tires].sum()),
        note=f"{note}, tirés avec la probabilité {p:.3f} ; loi gamma de forme "
             f"{FORME_GARDE:g} : {au_dessus:.1%} des enfants gardés au-dessus du plafond de "
             f"{PLAFOND_GARDE:.0f} € (une hypothèse)"))


def _interets(frame: pl.DataFrame, poids: np.ndarray) -> tuple[dict[str, np.ndarray],
                                                                Composante]:
    figure = margins.INTERETS_EMPRUNT_RESIDENCE_PRINCIPALE
    revenu = sum(frame[c].fill_null(0.0).to_numpy().astype(np.float64)
                 for c in ("salaire_brut_annuel", "pension_annuelle", "chomage_annuel",
                           "revenu_non_salarie_annuel") if c in frame.columns)
    revenu_menage = (frame.select("household_id").with_columns(pl.Series("r", revenu))
                     .select(pl.col("r").sum().over("household_id")).to_series().to_numpy())
    reference = (frame["role_menage"] == "personne_de_reference").to_numpy()
    accedant = (frame["statut_occupation"] == "primo_accedant").to_numpy()
    restant = np.clip((AGE_FIN_EMPRUNT - frame["age"].to_numpy()) / DUREE_EMPRUNT,
                      PART_MIN_EMPRUNT, 1.0)
    cle = np.where(reference & accedant, revenu_menage * restant, 0.0)
    interets = cle * (figure.value / float((cle * poids).sum()))
    menages = float(poids[reference & accedant].sum())
    return ({INTERETS_EMPRUNT: interets}, Composante(
        "interets_emprunt", figure.source, figure.url, figure.value,
        float((interets * poids).sum()), margins.ACCEDANTS.value,
        float(poids[interets > 0].sum()),
        note=f"{menages / 1e6:.2f} M ménages accédants dans la population contre "
             f"{margins.ACCEDANTS.value / 1e6:.2f} M au compte du logement (nombre non "
             f"calé) ; montant au prorata du revenu du ménage et de la part restante du "
             f"prêt"))


def impute(frame: pl.DataFrame, year: int = YEAR, *, seed: int = SEED,
           raw: Path | None = None) -> tuple[pl.DataFrame, Stats]:
    """La population avec les colonnes de `COLONNES`, et la part exonérée des salaires
    redistribuée vers les heures supplémentaires. Chaque total est calé sur sa source ;
    `Stats` les met contre elle."""
    if year != YEAR:
        raise MenagesError(
            f"données de ménages imputées pour {year} : les sources décrivent {YEAR}, et "
            f"une autre année demanderait de vieillir les montants, ce qui n'est pas fait")
    frame = frame.sort("person_id")
    rng = np.random.default_rng(seed)
    poids = _poids_menage(frame)
    colonnes: dict[str, np.ndarray] = {}
    composantes: list[Composante] = []
    for etape in (_heures_sup, _frais_reels, _garde):
        ajout, composante = etape(frame, poids, rng, raw)
        colonnes.update(ajout)
        composantes.append(composante)
    ajout, liste = _pensions(frame, poids, rng, raw)
    colonnes.update(ajout)
    composantes.extend(liste)
    ajout, composante = _interets(frame, poids)
    colonnes.update(ajout)
    composantes.append(composante)
    for c in composantes:
        if c.depense and abs(c.ecart_montant) > TOLERANCE_MONTANT:
            raise MenagesError(f"{c.nom} : {c.montant:,.0f} € imputés contre "
                               f"{c.cible_montant:,.0f} € publiés")
    frame = frame.with_columns([pl.Series(nom, valeurs.astype(np.float64))
                                for nom, valeurs in colonnes.items()])
    return frame, Stats(tuple(composantes))


def garde_par_foyer(frame: pl.DataFrame, foyer_ids: np.ndarray) -> dict[str, np.ndarray]:
    """Les cases 7GA, 7GB, 7GC de chaque foyer, dans l'ordre de `foyer_ids` : les frais de
    ses enfants gardés, dans l'ordre des `person_id`. Au-delà du troisième, ils vont sur la
    7GC, qui plafonne alors un peu trop tôt (rare : 0,1 % des enfants gardés)."""
    gardes = (frame.filter(pl.col(FRAIS_GARDE) > 0).sort("person_id")
              .select("foyer_id", FRAIS_GARDE)
              .with_columns(pl.int_range(pl.len()).over("foyer_id").alias("rang")))
    index = {str(f): i for i, f in enumerate(foyer_ids)}
    cases = {case: np.zeros(len(foyer_ids)) for case in CASES_GARDE}
    for foyer, montant, rang in gardes.iter_rows():
        cases[CASES_GARDE[min(rang, len(CASES_GARDE) - 1)]][index[str(foyer)]] += montant
    return cases


def ecart_emploi_domicile(raw: Path | None = None) -> Composante:
    """La table par décile que `niches` dépense pour la case 7DB, contre le total de la
    2042 : deux publications de la DGFiP. Le crédit publié, rapporté au taux de 50 %, est
    une base après plafond et après les aides ; la 2042, des dépenses déclarées."""
    from impots.population import niches

    niche = next(n for n in niches.IMPUTABLE if n.case == "f7db")
    table = niches.brackets(niche, YEAR, raw)
    base = sum(b.amount_eur for b in table) / niche.rate
    foyers = sum(b.claimants for b in table)
    figure = margins.EMPLOI_DOMICILE_DECLARE
    nombre = 5_190_857.0
    return Composante("emploi_domicile", figure.source, figure.url, figure.value, base,
                      nombre, foyers, depense=False,
                      note="la base de l'imputation des niches (crédit par décile sur 50 %) "
                           "contre les dépenses déclarées en 7DB")
