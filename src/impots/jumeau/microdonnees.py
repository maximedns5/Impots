"""Les élasticités du jumeau estimées sur des données fines (but 23, D-425, D-426).

L'histoire agrégée n'identifie aucun θ (D-421, l'étape zéro) : sept années nationales,
des chocs petits. Ici, des panneaux par région, secteur et année (créations de sociétés,
défaillances), et par branche et année (emploi salarié), croisés avec une DOSE de réforme
propre à chaque secteur : l'exposition structurelle du secteur (Ésane 2023, la
distribution des salaires) fois le paramètre voté de l'année (le barème, daté par la base
des mesures votées). Aucun montant officiel d'une réforme n'y entre : seulement des taux,
des seuils et des structures.

Trois doses par secteur u et année t, toutes nulles sous le droit de 2012 (négatives pour
une baisse de prélèvement) :

* `travail` L, en fraction du coût du travail : −g [r_t a_u(k_t) + 1,8 % f_u,t], r_t le
  taux du CICE puis de la baisse de 6 points de la cotisation maladie (même assiette :
  les salaires sous k_t = 2,5 SMIC), f_u,t la part de la masse salariale sous le seuil
  du taux réduit d'allocations familiales (1,6 SMIC en 2015, 3,5 SMIC en 2017), g la part
  des salaires bruts dans le coût du travail (D11/D1 des SNF, t. 7.101) ;
* `marge` D, en points de valeur ajoutée : 100 (L FP_u + IS_u,t + CVAE_u,t)/VA_u, IS la
  baisse du taux normal sur le profit imposable de chaque catégorie de taille, CVAE la
  baisse de son taux sur la valeur ajoutée de chaque catégorie ;
* `taux` T, en points de taux apparent sur le profit imposable : la même somme sur
  κ EBE_u, κ le profit imposable sur l'EBE (DGFiP sur Ésane), le Δτ du bloc `naissances`.

Les estimateurs : moindres carrés à effets fixes (projetés par projections alternées),
la variance groupée CR1, et le bootstrap sauvage groupé (Webb, six points, sous H₀ pour
la p-valeur, sans contrainte pour l'écart-type), parce que les grappes sont peu nombreuses
(9 ou 10 secteurs, 30 branches). Les spécifications sont celles de D-425, avant tout
calcul ; ce module ne les choisit pas, il les exécute.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from impots.dette import comptes


class MicrodonneesError(ValueError):
    """Une donnée absente, une forme inattendue, un panneau qui ne s'estime pas."""


# --------------------------------------------------------------------------- #
# les fichiers (manifestés, D-425)
# --------------------------------------------------------------------------- #
BDM_CREATIONS = "insee_bdm_creations_region_secteur_m2022_2012_2025.xml"
BDM_CREATIONS_ARRETEE = "insee_bdm_creations_region_secteur_arretee_2000_2021.xml"
BDM_DEFAILLANCES = "insee_bdm_defaillances_region_secteur_1990_2025.xml"
ESANE = "insee_esane2023_caracteristiques_par_taille.xlsx"
SALAIRES = "insee_ip2079_salaires_prive_2024.xlsx"
EMPLOI = "insee_cn2025_t6210_emploi_salarie_branches.xlsx"
COMPTE_SNF = "insee_cn2025_t7101_compte_snf.xlsx"
DGFIP_IS = "dgfip_stat_39_impot_benefice_2024_donnees.xlsx"

#: Les treize régions métropolitaines (codes de 2016).
REGIONS = ("R11", "R24", "R27", "R28", "R32", "R44", "R52", "R53", "R75", "R76", "R84",
           "R93", "R94")

#: Les secteurs des panneaux et leur assiette dans Ésane (niveau, code). L'agriculture et
#: la finance n'ont pas d'Ésane complet : elles sont hors des panneaux.
SECTEURS_ESANE: dict[str, tuple[tuple[str, str], ...]] = {
    "BE": (("a10", "BE"),), "FZ": (("a10", "FZ"),), "G": (("a21", "G"),),
    "H": (("a21", "H"),), "I": (("a21", "I"),), "JZ": (("a21", "J"),),
    "LZ": (("a21", "L"),), "MN": (("a10", "MN"),),
    "OQ": (("a21", "P"), ("a21", "Q")), "RU": (("a21", "R"), ("a21", "S")),
    "PQS": (("a21", "P"), ("a21", "Q"), ("a21", "S")),
}
SECTEURS_DEFAILLANCES = ("BE", "FZ", "G", "H", "I", "JZ", "LZ", "MN", "PQS")
SECTEURS_CREATIONS = ("BE", "FZ", "G", "H", "I", "JZ", "LZ", "MN", "OQ", "RU")

#: Les branches marchandes A38 de l'emploi (t. 6.210) : leur ligne et leurs divisions.
BRANCHES: dict[str, tuple[str, tuple[int, ...]]] = {
    "BZ": ("A38_BZ", (5, 6, 7, 8, 9)), "CA": ("A17_C1", (10, 11, 12)),
    "CB": ("A38_CB", (13, 14, 15)), "CC": ("A38_CC", (16, 17, 18)),
    "CD": ("A17_C2", (19,)), "CE": ("A38_CE", (20,)), "CF": ("A38_CF", (21,)),
    "CG": ("A38_CG", (22, 23)), "CH": ("A38_CH", (24, 25)), "CI": ("A38_CI", (26,)),
    "CJ": ("A38_CJ", (27,)), "CK": ("A38_CK", (28,)), "CL": ("A17_C4", (29, 30)),
    "CM": ("A38_CM", (31, 32, 33)), "DZ": ("A38_DZ", (35,)),
    "EZ": ("A38_EZ", (36, 37, 38, 39)), "FZ": ("A5_FZ", (41, 42, 43)),
    "GZ": ("A17_GZ", (45, 46, 47)), "HZ": ("A17_HZ", (49, 50, 51, 52, 53)),
    "IZ": ("A17_IZ", (55, 56)), "JA": ("A38_JA", (58, 59, 60)), "JB": ("A38_JB", (61,)),
    "JC": ("A38_JC", (62, 63)), "LZ": ("A10_LZ", (68,)), "MA": ("A38_MA", (69, 70, 71)),
    "MB": ("A38_MB", (72,)), "MC": ("A38_MC", (73, 74, 75)),
    "NZ": ("A38_NZ", (77, 78, 79, 80, 81, 82)), "RZ": ("A38_RZ", (90, 91, 92, 93)),
    "SZ": ("A38_SZ", (94, 95, 96)),
}

CATEGORIES = ("MIC", "PME", "ETIGE")
_CATEGORIE = {"Microentreprises": "MIC", "Petites et moyennes": "PME",
              "Entreprises de taille": "ETIGE", "Ensemble": "ENS"}
_GRANDEURS = {"n": 4, "eqtp": 5, "ca": 8, "va": 10, "fp": 11, "ebe": 12}


# --------------------------------------------------------------------------- #
# le droit voté : des paramètres, datés par la base des mesures votées
# --------------------------------------------------------------------------- #
#: Chaque paramètre et la mesure de `votees` qui le date ; un test vérifie que chaque
#: année où il change est une année d'effet de sa mesure.
PARAMETRES = {
    "cice": {2013: 0.04, 2014: 0.06, 2017: 0.07, 2018: 0.06, 2019: 0.06},
    "cice_seuil_smic": {2013: 2.5, 2025: 2.25},
    "famille_seuil_smic": {2015: 1.6, 2016: 3.5, 2025: 3.3},
    "is_petites": {2017: 28.0, 2021: 26.5, 2022: 25.0},
    "is_grandes": {2019: 31.0, 2021: 27.5, 2022: 25.0},
    "cvae_multiple": {2021: 0.5, 2023: 0.25, 2024: 0.28 / 1.5, 2025: 0.28 * 1.474 / 1.5},
}
MESURES_DES_PARAMETRES = {
    "cice": ("lfr2012_3_cice", "lfi2017_cice_7", "lfi2018_cice_6_suppression",
             "lfss2018_cice_allegements"),
    "cice_seuil_smic": ("lfr2012_3_cice", "lfss2025_allegements"),
    "famille_seuil_smic": ("lfrss2014_pacte_allegements", "lfss2016_pacte_famille",
                           "lfss2025_allegements"),
    "is_petites": ("lfi2017_is_28", "lfi2018_is_25"),
    "is_grandes": ("lfi2018_is_25", "lfi2020_is_grandes_entreprises"),
    "cvae_multiple": ("lfi2021_cvae_regions", "lfi2023_cvae", "lfi2024_cvae_etalement",
                      "lfi2025_cvae_report"),
}
IS_AVANT = 33.33
#: La baisse de cotisation familiale : 1,8 point (5,25 % → 3,45 %), lfrss2014.
FAMILLE_POINTS = 0.018
#: Le seuil de 3,5 SMIC entre en vigueur le 1er avril 2016 : trois trimestres en 2016.
FAMILLE_2016_PART = 0.75
#: La part du profit des catégories au taux normal (le reste au taux réduit de 15 %) :
#: 1 − (effet du taux réduit) / (33,3 − 15), Insee Analyses n° 112, tableau complémentaire,
#: 2016 (−9,4 points pour les micro, −1,4 pour les PME, et −0,9 sur l'ensemble, figure 3,
#: pour les ETI et GE, une approximation).
PART_TAUX_NORMAL = {"MIC": 1 - 9.4 / 18.3, "PME": 1 - 1.4 / 18.3, "ETIGE": 1.0}
#: Le SMIC net mensuel moyen de 2024 (1 398,69 € de janvier à octobre, 1 426,30 € en
#: novembre et décembre), en euros, l'unité des centiles de l'Insee Première n° 2079.
SMIC_NET_2024 = (10 * 1398.69 + 2 * 1426.30) / 12


def parametre(nom: str, annee: int, avant: float) -> float:
    """La valeur d'un paramètre en `annee` : la dernière étape à cette date, `avant`
    avant la première."""
    valeur = avant
    for a, v in sorted(PARAMETRES[nom].items()):
        if a <= annee:
            valeur = v
    return valeur


def taux_cvae(ca_millions: float) -> float:
    """Le taux effectif de la CVAE avant 2021 selon le chiffre d'affaires (CGI, art. 1586
    quinquies, le barème progressif du dégrèvement), en fraction de la valeur ajoutée."""
    x = ca_millions
    if x < 0.5:
        return 0.0
    if x < 3:
        return 0.005 * (x - 0.5) / 2.5
    if x < 10:
        return 0.005 + 0.009 * (x - 3) / 7
    if x < 50:
        return 0.014 + 0.001 * (x - 10) / 40
    return 0.015


# --------------------------------------------------------------------------- #
# les lectures
# --------------------------------------------------------------------------- #
def _texte(fichier: str) -> str:
    from impots.population.ingest import require_sourced

    require_sourced(fichier)
    chemin = comptes.RAW / fichier
    if not chemin.exists():
        raise MicrodonneesError(f"{fichier} est au manifeste mais absent de data/raw")
    return chemin.read_text(encoding="utf-8")


_SERIE = re.compile(r"<Series ([^>]*)>(.*?)</Series>", re.S)
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')
_OBS = re.compile(r'<Obs ([^>]*)/>')


def series_bdm(texte: str) -> list[tuple[dict[str, str], dict[str, float]]]:
    """Les séries d'une réponse SDMX de la BDM : (attributs, {période : valeur})."""
    out = []
    for attributs, corps in _SERIE.findall(texte):
        obs = {}
        for o in _OBS.findall(corps):
            a = dict(_ATTR.findall(o))
            if "OBS_VALUE" in a and a["OBS_VALUE"] not in ("", "NaN"):
                obs[a["TIME_PERIOD"]] = float(a["OBS_VALUE"])
        out.append((dict(_ATTR.findall(attributs)), obs))
    return out


def annuel(obs: Mapping[str, float]) -> dict[int, float]:
    """La somme des quatre trimestres de chaque année complète ; une année incomplète
    n'entre pas."""
    par_annee: dict[int, list[float]] = {}
    for periode, v in obs.items():
        m = re.fullmatch(r"(\d{4})-Q([1-4])", periode)
        if not m:
            raise MicrodonneesError(f"période trimestrielle attendue, lu « {periode} »")
        par_annee.setdefault(int(m.group(1)), []).append(v)
    return {a: float(sum(v)) for a, v in par_annee.items() if len(v) == 4}


def panneau_bdm(texte: str, indicateur: str, secteurs: Sequence[str]
                ) -> dict[tuple[str, str], dict[int, float]]:
    """{(région, secteur) : {année : nombre}} pour les régions métropolitaines."""
    out: dict[tuple[str, str], dict[int, float]] = {}
    for a, obs in series_bdm(texte):
        if (a.get("INDICATEUR") == indicateur and a.get("REF_AREA") in REGIONS
                and a.get("ACTIVITE_CREAT_ENT") in secteurs and a.get("CORRECTION") == "BRUT"
                and a.get("FREQ") == "T"):
            cle = (a["REF_AREA"], a["ACTIVITE_CREAT_ENT"])
            if cle in out:
                raise MicrodonneesError(f"deux séries pour {cle} ({indicateur})")
            out[cle] = annuel(obs)
    if not out:
        raise MicrodonneesError(f"aucune série « {indicateur} » régionale")
    return out


def creations(texte: str | None = None, indicateur: str = "TYPE-ENT_PM",
              arretee: bool = False) -> dict[tuple[str, str], dict[int, float]]:
    fichier = BDM_CREATIONS_ARRETEE if arretee else BDM_CREATIONS
    return panneau_bdm(texte if texte is not None else _texte(fichier), indicateur,
                       SECTEURS_CREATIONS)


def defaillances(texte: str | None = None) -> dict[tuple[str, str], dict[int, float]]:
    return panneau_bdm(texte if texte is not None else _texte(BDM_DEFAILLANCES),
                       "NOMBRE_DEFAILLANCES", SECTEURS_DEFAILLANCES)


def emploi_branches() -> dict[str, dict[int, float]]:
    """{branche A38 : {année : milliers de salariés}} (t. 6.210, en niveau)."""
    rows = comptes._rows(EMPLOI, "T_6210 en niveau")
    colonnes = comptes._year_columns(rows)
    par_code = {str(r[0]).strip(): r for r in rows if r[0] is not None}
    out = {}
    for branche, (code, _) in BRANCHES.items():
        if code not in par_code:
            raise MicrodonneesError(f"t. 6.210 : ligne « {code} » absente ({branche})")
        r = par_code[code]
        out[branche] = {a: float(r[i]) for a, i in colonnes.items()
                        if r[i] is not None and str(r[i]).strip() not in ("", "nd")}
    return out


def esane() -> dict[tuple[str, str], dict[str, dict[str, float | None]]]:
    """{(niveau, code) : {catégorie : {grandeur : M€ ou effectif, None si secret}}}."""
    rows = comptes._rows(ESANE, "princ_caract_taille")
    out: dict[tuple[str, str], dict[str, dict[str, float | None]]] = {}
    for r in rows:
        if r[0] not in ("a10", "a21", "a88") or r[3] is None:
            continue
        cat = next((v for k, v in _CATEGORIE.items() if str(r[3]).startswith(k)), None)
        if cat is None:
            raise MicrodonneesError(f"Ésane : catégorie inconnue « {r[3]} »")
        out.setdefault((r[0], str(r[1])), {})[cat] = {
            g: (None if r[i] in ("S", "N", None) else float(r[i]))
            for g, i in _GRANDEURS.items()}
    return out


def combler_divisions(table: dict[tuple[str, str], dict[str, dict[str, float | None]]]
                      ) -> list[str]:
    """Les totaux secrets d'une division (a88) : le reste de sa section (a21) moins les
    divisions publiées, partagé entre les divisions secrètes selon leurs EQTP s'ils sont
    tous publiés, sinon selon leur nombre d'entreprises. Rend les divisions comblées."""
    comblees = []
    divisions: dict[str, list[str]] = {}
    for niveau, code in table:
        if niveau == "a88" and code.isdigit():
            divisions.setdefault(_parent_a21(int(code)), []).append(code)
    for lettre, codes in divisions.items():
        parent = table.get(("a21", lettre))
        if parent is None:
            continue
        for g in _GRANDEURS:
            secrets = [c for c in codes if table[("a88", c)]["ENS"][g] is None]
            if not secrets:
                continue
            connu = sum(table[("a88", c)]["ENS"][g] for c in codes if c not in secrets)
            reste = max(parent["ENS"][g] - connu, 0.0)
            cle = "eqtp" if all(table[("a88", c)]["ENS"]["eqtp"] is not None
                                for c in secrets) else "n"
            poids = {c: table[("a88", c)]["ENS"][cle] or 0.0 for c in secrets}
            total = sum(poids.values()) or float(len(secrets))
            for c in secrets:
                table[("a88", c)]["ENS"][g] = reste * (poids[c] or total / len(secrets)) / total
                comblees.append(f"{c}:{g}")
    return comblees


def _completer(cellule: dict[str, dict[str, float | None]], parent: Any = None
               ) -> dict[str, dict[str, float]]:
    """Les trois catégories d'une ligne d'Ésane, chaque grandeur connue. Un secret seul
    se déduit de l'ensemble ; deux secrets (PME, ETI-GE) se partagent le reste selon les
    effectifs en EQTP s'ils sont publiés, sinon selon les parts du parent."""
    ens = cellule["ENS"]
    if any(v is None for v in ens.values()):
        raise MicrodonneesError("Ésane : un total d'ensemble est secret")
    out: dict[str, dict[str, float]] = {c: {} for c in CATEGORIES}
    for g in _GRANDEURS:
        connus = {c: cellule[c][g] for c in CATEGORIES if cellule[c][g] is not None}
        manquants = [c for c in CATEGORIES if c not in connus]
        reste = ens[g] - sum(connus.values())
        for c, v in connus.items():
            out[c][g] = v
        if len(manquants) == 1:
            out[manquants[0]][g] = reste
        elif len(manquants) > 1:
            poids = {c: cellule[c]["eqtp"] for c in manquants}
            if any(p is None for p in poids.values()) or g == "eqtp":
                if parent is None:
                    raise MicrodonneesError("Ésane : deux secrets et aucun parent")
                poids = {c: parent[c][g] for c in manquants}
            total = sum(poids.values())
            for c in manquants:
                out[c][g] = reste * poids[c] / total if total else 0.0
    return out


def _parent_a21(division: int) -> str:
    bornes = ((9, "B"), (33, "C"), (35, "D"), (39, "E"), (43, "F"), (47, "G"), (53, "H"),
              (56, "I"), (63, "J"), (66, "K"), (68, "L"), (75, "M"), (82, "N"), (84, "O"),
              (85, "P"), (88, "Q"), (93, "R"), (96, "S"))
    return next(lettre for borne, lettre in bornes if division <= borne)


# --------------------------------------------------------------------------- #
# les expositions
# --------------------------------------------------------------------------- #
@dataclass
class Exposition:
    """Un secteur ou une branche : ses grandeurs d'Ésane 2023 par catégorie (M€), son coût
    du travail par EQTP relatif à l'ensemble, et les parts de sa masse salariale brute
    sous chaque seuil de SMIC."""

    nom: str
    par_categorie: dict[str, dict[str, float]]
    cout_relatif: float
    parts_smic: dict[float, float] = field(default_factory=dict)

    def total(self, g: str) -> float:
        return sum(self.par_categorie[c][g] for c in CATEGORIES)


def distribution_nationale() -> np.ndarray:
    """Les salaires nets mensuels en EQTP de 2024, cent masses de 1 % : les centiles 5 à
    99 (tableau complémentaire 3), les quatre premiers au 5e centile, le dernier à la
    valeur qui redonne la moyenne publiée (2 733 €, figure 3)."""
    rows = comptes._rows(SALAIRES, "Tableau complémentaire 3")
    centiles = {int(str(r[0])[1:]): float(r[1]) for r in rows
                if r[0] is not None and re.fullmatch(r"c\d+", str(r[0]))}
    if sorted(centiles) != list(range(5, 100)):
        raise MicrodonneesError(f"centiles 5 à 99 attendus, lus {sorted(centiles)[:3]}…")
    rows3 = comptes._rows(SALAIRES, "Figure 3")
    moyenne = next(float(r[5]) for r in rows3 if r[0] == "Moyenne")
    masses = [centiles[5]] * 4 + [centiles[p] for p in range(5, 100)]
    masses.append(100 * moyenne - sum(masses))
    return np.array(masses)


def parts_sous_seuils(salaires: np.ndarray, relatif: float, seuils: Sequence[float]
                      ) -> dict[float, float]:
    """La part de la masse salariale sous k SMIC quand la distribution nationale est mise
    à l'échelle du coût relatif du secteur (une hypothèse : la forme est commune)."""
    w = salaires * relatif
    return {k: float(w[w <= k * SMIC_NET_2024].sum() / w.sum()) for k in seuils}


SEUILS = (1.6, 2.25, 2.5, 3.3, 3.5)


def expositions(unites: Mapping[str, Sequence[tuple[str, str]]] | None = None,
                *, branches: bool = False) -> dict[str, Exposition]:
    """Les expositions des secteurs des panneaux (ou des branches A38 de l'emploi)."""
    table = esane()
    combler_divisions(table)
    cellules: dict[tuple[str, str], dict[str, dict[str, float]]] = {}

    def cellule(cle: tuple[str, str]) -> dict[str, dict[str, float]]:
        if cle not in cellules:
            parent = None
            if cle[0] == "a88":
                parent = cellule(("a21", _parent_a21(int(cle[1]))))
            if cle not in table:
                raise MicrodonneesError(f"Ésane : ligne {cle} absente")
            cellules[cle] = _completer(table[cle], parent)
        return cellules[cle]

    if branches:
        unites = {b: tuple(("a88", f"{d:02d}") for d in divs)
                  for b, (_, divs) in BRANCHES.items()}
    elif unites is None:
        unites = SECTEURS_ESANE
    tout = [("a21", x) for x in "BCDEFGHIJLMNPQRS"]
    fp = sum(cellule(c)[k]["fp"] for c in tout for k in CATEGORIES)
    eqtp = sum(cellule(c)[k]["eqtp"] for c in tout for k in CATEGORIES)
    salaires = distribution_nationale()
    out = {}
    for nom, cles in unites.items():
        par_cat = {k: {g: sum(cellule(c)[k][g] for c in cles) for g in _GRANDEURS}
                   for k in CATEGORIES}
        e = Exposition(nom, par_cat, 0.0)
        e.cout_relatif = (e.total("fp") / e.total("eqtp")) / (fp / eqtp)
        e.parts_smic = parts_sous_seuils(salaires, e.cout_relatif, SEUILS)
        out[nom] = e
    return out


def part_salaires_bruts() -> float:
    """g = D11/D1 des sociétés non financières en 2023 (t. 7.101), l'année d'Ésane."""
    rows = comptes._rows(COMPTE_SNF, "T_7101")
    colonnes = comptes._year_columns(rows)
    d = {str(r[0]).strip(): r for r in rows if r[0] is not None}
    return float(d["D11"][colonnes[2023]]) / float(d["D1"][colonnes[2023]])


def profit_imposable_sur_ebe() -> float:
    """κ : les bénéfices déclarés à l'IS en 2024 (DGFiP, Statistiques n° 39, tableau 2)
    sur l'EBE de l'ensemble d'Ésane 2023 (hors agriculture et finance)."""
    rows = comptes._rows(DGFIP_IS, "Tableau 2")
    benefices = next(float(r[6]) for r in rows if r[1] and str(r[1]).startswith("Bénéfices"))
    table = esane()
    ebe = sum(table[("a21", x)]["ENS"]["ebe"] for x in "BCDEFGHIJLMNPQRS")
    return benefices / 1e6 / ebe


# --------------------------------------------------------------------------- #
# les doses
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Constantes:
    g: float
    kappa: float


def constantes() -> Constantes:
    return Constantes(g=part_salaires_bruts(), kappa=profit_imposable_sur_ebe())


def doses(e: Exposition, annee: int, k: Constantes) -> dict[str, float]:
    """Les composantes de la dose de `annee` pour une exposition, en M€ de 2023 (signe :
    négatif pour une baisse), et les trois doses (`travail`, `marge`, `taux`)."""
    fp, va, ebe = e.total("fp"), e.total("va"), e.total("ebe")
    seuil = parametre("cice_seuil_smic", annee, 2.5)
    cice = -k.g * parametre("cice", annee, 0.0) * e.parts_smic[seuil] * fp
    fam = 0.0
    if annee >= 2015:
        bas = e.parts_smic[1.6]
        haut = e.parts_smic[parametre("famille_seuil_smic", annee, 1.6)]
        part = bas + FAMILLE_2016_PART * (haut - bas) if annee == 2016 else haut
        fam = -k.g * FAMILLE_POINTS * part * fp
    impot = 0.0
    cvae = 0.0
    for c in CATEGORIES:
        x = e.par_categorie[c]
        nom = "is_grandes" if c == "ETIGE" else "is_petites"
        dt = parametre(nom, annee, IS_AVANT) - IS_AVANT
        impot += PART_TAUX_NORMAL[c] * dt / 100 * k.kappa * max(x["ebe"], 0.0)
        if annee >= 2010 and x["n"] > 0:
            m = parametre("cvae_multiple", annee, 1.0)
            cvae += (m - 1.0) * taux_cvae(x["ca"] / x["n"]) * x["va"]
    total = cice + fam + impot + cvae
    return {"cice": cice, "famille": fam, "is": impot, "cvae": cvae,
            "travail": (cice + fam) / fp, "marge": 100 * total / va,
            "taux": 100 * total / (k.kappa * ebe),
            "marge_travail": 100 * (cice + fam) / va,
            "marge_profit": 100 * (impot + cvae) / va,
            "taux_travail": 100 * (cice + fam) / (k.kappa * ebe),
            "taux_profit": 100 * (impot + cvae) / (k.kappa * ebe)}


# --------------------------------------------------------------------------- #
# les estimateurs
# --------------------------------------------------------------------------- #
def projeter(z: np.ndarray, groupes: Sequence[np.ndarray], tol: float = 1e-11,
             max_iter: int = 10_000) -> np.ndarray:
    """z moins ses moyennes par chaque partition de `groupes`, jusqu'au point fixe
    (projections alternées) : le résidu de la régression sur tous les effets fixes."""
    z = np.array(z, dtype=float, copy=True)
    if z.ndim == 1:
        z = z[:, None]
    for _ in range(max_iter):
        avant = z.copy()
        for g in groupes:
            n = np.bincount(g)
            for j in range(z.shape[1]):
                z[:, j] -= (np.bincount(g, weights=z[:, j]) / n)[g]
        if np.max(np.abs(z - avant)) < tol * max(1.0, np.max(np.abs(z))):
            return z
    raise MicrodonneesError("projections alternées sans convergence")


def _codes(valeurs: Sequence[Any]) -> np.ndarray:
    _, inv = np.unique(np.asarray(valeurs, dtype=object).astype(str), return_inverse=True)
    return inv


def rang_effets(effets: Sequence[np.ndarray]) -> int:
    """Le rang des indicatrices de deux partitions : leurs modalités moins le nombre de
    composantes connexes du graphe biparti qu'elles forment (une seule partition : ses
    modalités ; au-delà de deux, la somme moins une par partition ajoutée, un majorant)."""
    tailles = [int(e.max()) + 1 for e in effets]
    if len(effets) != 2:
        return sum(tailles) - (len(effets) - 1)
    parent = list(range(tailles[0] + tailles[1]))

    def racine(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in set(zip(effets[0].tolist(), effets[1].tolist(), strict=True)):
        ra, rb = racine(a), racine(tailles[0] + b)
        if ra != rb:
            parent[ra] = rb
    composantes = len({racine(i) for i in range(len(parent))})
    return sum(tailles) - composantes


#: Les poids de Webb (2014) : six points, pour peu de grappes.
WEBB = np.array([-np.sqrt(1.5), -1.0, -np.sqrt(0.5), np.sqrt(0.5), 1.0, np.sqrt(1.5)])


@dataclass
class Resultat:
    noms: tuple[str, ...]
    beta: np.ndarray
    se_cr1: np.ndarray
    se_bootstrap: np.ndarray
    p_cr1: np.ndarray
    p_wcr: np.ndarray
    n: int
    grappes: int
    k_fe: int

    def ligne(self, nom: str) -> dict[str, float]:
        j = self.noms.index(nom)
        return {"coef": float(self.beta[j]), "se_cr1": float(self.se_cr1[j]),
                "se_bootstrap": float(self.se_bootstrap[j]),
                "se": float(max(self.se_cr1[j], self.se_bootstrap[j])),
                "p_cr1": float(self.p_cr1[j]), "p_wcr": float(self.p_wcr[j])}


def _cr1(X: np.ndarray, u: np.ndarray, grappe: np.ndarray, A: np.ndarray, k_tot: int
         ) -> np.ndarray:
    n, k = X.shape
    G = int(grappe.max()) + 1
    S = np.zeros((G, k))
    np.add.at(S, grappe, X * u[:, None])
    c = G / (G - 1) * (n - 1) / max(n - k_tot, 1)
    return c * A @ (S.T @ S) @ A


def estimer(y: np.ndarray, X: np.ndarray, noms: Sequence[str], effets: Sequence[np.ndarray],
            grappe: np.ndarray, *, tirages: int = 9_999, graine: int = 20261114,
            poids: str = "webb", interet: Sequence[int] | None = None) -> Resultat:
    """MCO à effets fixes, variance CR1 groupée, bootstrap sauvage groupé : la p-valeur
    sous H₀ (β_j = 0, résidus contraints, WCR) et l'écart-type des tirages sans contrainte
    (WCU), pour chaque coefficient (la p-valeur, pour ceux d'`interet` seulement)."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    if not (np.isfinite(y).all() and np.isfinite(X).all()):
        raise MicrodonneesError("valeur non finie dans le panneau")
    effets = [_codes(e) for e in effets]
    grappe = _codes(grappe)
    Z = projeter(np.column_stack([y, X]), effets)
    yt, Xt = Z[:, 0], Z[:, 1:]
    n, k = Xt.shape
    k_fe = rang_effets(effets)
    k_tot = k + k_fe
    XtX = Xt.T @ Xt
    if np.linalg.matrix_rank(XtX) < k:
        raise MicrodonneesError("régresseurs colinéaires aux effets fixes")
    A = np.linalg.inv(XtX)
    beta = A @ Xt.T @ yt
    u = yt - Xt @ beta
    V = _cr1(Xt, u, grappe, A, k_tot)
    se = np.sqrt(np.diag(V))
    G = int(grappe.max()) + 1
    t = beta / se
    p_cr1 = np.array([student_bilateral(abs(x), G - 1) for x in t])
    rng = np.random.default_rng(graine)
    tirs = (rng.choice(WEBB, size=(tirages, G)) if poids == "webb"
            else rng.choice(np.array([-1.0, 1.0]), size=(tirages, G)))
    # sans contrainte : y* = Xβ + v_g u
    beta_u = _bootstrap_beta(Xt, Xt @ beta, u, grappe, A, tirs)
    se_boot = beta_u.std(axis=0, ddof=1)
    p_wcr = np.full(k, np.nan)
    for j in (range(k) if interet is None else interet):
        autres = [i for i in range(k) if i != j]
        if autres:
            Xr = Xt[:, autres]
            br = np.linalg.lstsq(Xr, yt, rcond=None)[0]
            ajuste = Xr @ br
        else:
            ajuste = np.zeros(n)
        ur = yt - ajuste
        t_star = _bootstrap_t(Xt, ajuste, ur, grappe, A, tirs, j, k_tot)
        p_wcr[j] = float(np.mean(np.abs(t_star) >= abs(t[j])))
    return Resultat(tuple(noms), beta, se, se_boot, p_cr1, p_wcr, n, G, k_fe)


def _betacf(a: float, b: float, x: float) -> float:
    """La fraction continue de la fonction bêta incomplète (Numerical Recipes, 6.4)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for k in range(1, 300):
        k2 = 2 * k
        aa = k * (b - k) * x / ((qam + k2) * (a + k2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(1.0 + aa / c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + k) * (qab + k) * x / ((a + k2) * (qap + k2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c if abs(1.0 + aa / c) > 1e-300 else 1e-300
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-14:
            return h
    raise MicrodonneesError("fonction bêta incomplète sans convergence")


def student_bilateral(t: float, ddl: int) -> float:
    """P(|T| ≥ t) pour une loi de Student à `ddl` degrés : I_x(ddl/2, 1/2), x =
    ddl/(ddl + t²), la bêta incomplète régularisée."""
    import math

    a, b = ddl / 2.0, 0.5
    x = ddl / (ddl + t * t)
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        return math.exp(ln_front) * _betacf(a, b, x) / a
    return 1.0 - math.exp(ln_front) * _betacf(b, a, 1.0 - x) / b


def _bootstrap_beta(X, ajuste, u, grappe, A, tirs) -> np.ndarray:
    G = tirs.shape[1]
    S = np.zeros((G, X.shape[1]))
    np.add.at(S, grappe, X * u[:, None])
    return (A @ (X.T @ ajuste))[None, :] + (tirs @ S) @ A.T


def _bootstrap_t(X, ajuste, u, grappe, A, tirs, j, k_tot) -> np.ndarray:
    """t*_j de chaque tirage, sa variance CR1 recalculée (vectorisé sur les tirages)."""
    n, k = X.shape
    G = tirs.shape[1]
    Sxu = np.zeros((G, k))
    np.add.at(Sxu, grappe, X * u[:, None])
    Sxa = np.zeros((G, k))
    np.add.at(Sxa, grappe, X * ajuste[:, None])
    XX = np.zeros((G, k, k))
    np.add.at(XX, grappe, X[:, :, None] * X[:, None, :])
    b = (A @ (X.T @ ajuste))[None, :] + (tirs @ Sxu) @ A.T          # (B, k)
    # X_g'u*_g = X_g'ŷ_g + v_g X_g'ũ_g − X_g'X_g β*
    score = (Sxa[None, :, :] + tirs[:, :, None] * Sxu[None, :, :]
             - np.einsum("gkl,bl->bgk", XX, b))                       # (B, G, k)
    c = G / (G - 1) * (n - 1) / max(n - k_tot, 1)
    a_j = A[j]                                                          # (k,)
    proj = score @ a_j                                                  # (B, G)
    var_j = c * np.sum(proj ** 2, axis=1)
    return b[:, j] / np.sqrt(var_j)


# --------------------------------------------------------------------------- #
# l'échelle des θ
# --------------------------------------------------------------------------- #
def vers_theta(valeur: float, se: float, bas: float, centre: float, haut: float
               ) -> dict[str, float]:
    """θ d'une valeur sur une ligne linéaire par morceaux (bas, centre, haut) et son
    écart-type par la pente du morceau où elle tombe (prolongé au-delà des bornes)."""
    if valeur <= centre:
        pente = 2 * (centre - bas)
        theta = (valeur - bas) / pente
    else:
        pente = 2 * (haut - centre)
        theta = 0.5 + (valeur - centre) / pente
    return {"theta": float(theta), "se_theta": float(se / pente),
            "identifie": bool(se / pente < 0.25)}
