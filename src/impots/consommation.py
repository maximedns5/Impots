"""La consommation des ménages par poste, imputée, et la TVA et les accises qu'elle paie.

But 12, D-323. La source est le tableau TF106 de l'enquête Budget de famille 2017 (Insee,
France entière) : la dépense moyenne par ménage, en euros de 2017, de chaque poste à cinq
positions de la COICOP, par décile de niveau de vie. Un ménage reçoit, pour chaque poste,
la dépense de son décile au prorata de ses unités de consommation sur la moyenne de son
décile : la moyenne du décile est gardée, et rien d'autre n'est supposé. Les euros de 2017
sont portés à l'année par la croissance de la consommation des ménages de leur division
dans les comptes nationaux ; une division que les deux nomenclatures découpent autrement
suit le total. La calibration de la population n'est pas touchée : ce module ajoute des
colonnes, il ne change aucun poids.

La TVA et les accises se calculent à volumes constants, la taxe répercutée en entier dans
les prix (`regles.md`, R1 à R5) : la consommation ne réagit pas aux prix, et c'est dit.
"""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
BDF = RAW / "insee_bdf2017_france_entiere_csv.zip"
CN = RAW / "insee_cn2025_conso_effective_fonction.xlsx"
POSTES = Path(__file__).with_name("consommation_postes_2026.csv")
ANNEE_ENQUETE = 2017
#: Les divisions que la COICOP de l'enquête (1998) et celle des comptes (2018) découpent de
#: même : un poste y suit sa division dans les comptes, et elle seule. Leurs classes ne se
#: répondent pas toujours (le tabac est 02.2 dans l'une, 02.3 dans l'autre). Les autres
#: divisions (08, 09, 10, 12) ont été redécoupées : leurs postes suivent le total (D-323).
DIVISIONS_COMMUNES = frozenset({"01", "02", "03", "04", "05", "06", "07", "11"})
#: Les postes que l'imputation répartit entre d'autres, et entre lesquels (R11) : la facture
#: commune d'électricité et de gaz, au prorata des factures séparées du même décile.
REPARTIS: dict[str, tuple[str, str]] = {"04500": ("04511", "0452Z")}
#: La dernière année des comptes nationaux lus.
DERNIERE_ANNEE_CN = 2025

#: Les groupes de postes qu'un bouton de TVA peut nommer, au lieu d'un code.
GROUPES: dict[str, tuple[str, ...]] = {
    "electricite": ("04511",), "gaz": ("0452Z",), "fioul": ("0453Z",),
    "carburants": ("07221",), "energie": ("04511", "0452Z", "0453Z", "07221"),
    "restauration": ("11111", "11112"),
}

#: Les accises et les prix TTC moyens par année (regles.md, § 5 et R8, R9). Les accises
#: des carburants et du fioul en €/L, de l'électricité et du gaz en €/MWh. Les prix servent
#: à passer des euros aux volumes, de la même année que les euros.
LOI_ENERGIE: dict[int, dict[str, dict[str, float]]] = {
    2024: {
        "accise": {"gazole": 0.6075, "essence": 0.6629, "fioul": 0.1637,
                   "electricite": 21.0, "gaz": 16.37},
        "prix": {"gazole": 1.694, "essence": 1.784, "fioul": 1.200, "electricite": 280.0,
                 "gaz": 130.0},
    },
    2026: {
        "accise": {"gazole": 0.6075, "essence": 0.6702, "fioul": 0.1642,
                   "electricite": 30.68, "gaz": 16.42},
        "prix": {"gazole": 2.051, "essence": 1.938, "fioul": 1.598, "electricite": 235.0,
                 "gaz": 134.0},
    },
}
def loi_energie(annee: int) -> dict[str, float]:
    """Les accises de `annee` : celles de la loi relevée, ou, au-delà de la dernière, les
    tarifs de celle-ci reconduits tels quels, le droit tel qu'il est écrit (D-328). Les
    tarifs des accises sont des montants en euros, que la loi ne revalorise pas d'elle-même."""
    connues = sorted(LOI_ENERGIE)
    if annee in LOI_ENERGIE:
        return dict(LOI_ENERGIE[annee]["accise"])
    if annee > connues[-1]:
        return dict(LOI_ENERGIE[connues[-1]]["accise"])
    raise ConsommationError(f"les accises de {annee} ne sont pas écrites (connues : {connues})")


def prix_energie(annee: int, prix_au_dela: dict[int, float] | None = None) -> dict[str, float]:
    """Les prix TTC de l'énergie de `annee`, l'année des euros qu'ils convertissent en
    volumes : ceux relevés, ou, au-delà du dernier, les siens portés par l'indice des prix
    qui porte aussi les euros, pour que les volumes ne bougent pas d'eux-mêmes (D-328)."""
    connues = sorted(LOI_ENERGIE)
    if annee in LOI_ENERGIE:
        return dict(LOI_ENERGIE[annee]["prix"])
    if annee < connues[-1]:
        raise ConsommationError(f"les prix de l'énergie de {annee} ne sont pas écrits "
                                f"(connus : {connues})")
    facteur = 1.0
    for a in range(connues[-1] + 1, annee + 1):
        if not prix_au_dela or a not in prix_au_dela:
            raise ConsommationError(f"pas de prix de l'énergie en {a} : donner l'indice des "
                                    "prix de cette année")
        facteur *= 1.0 + prix_au_dela[a]
    return {k: v * facteur for k, v in LOI_ENERGIE[connues[-1]]["prix"].items()}


def prix_du_cadre(uprating, annee: int) -> dict[int, float]:
    """L'indice des prix d'un cadre (`Uprating`), année par année, de la première année
    après les comptes jusqu'à `annee` : ce qui porte la consommation d'une population
    vieillie par ce cadre (D-328)."""
    par_annee = dict(uprating.price_by_year)
    return {a: par_annee.get(a, uprating.price) if par_annee else uprating.price
            for a in range(DERNIERE_ANNEE_CN + 1, annee + 1)}


#: La part du gazole dans la dépense de carburants des ménages, SDES 2024 (29,9 Md€ de
#: gazole, 22,75 de supercarburants) : l'enquête ne sépare pas les carburants (D-323).
PART_GAZOLE = 29.901 / (29.901 + 22.752)


class ConsommationError(RuntimeError):
    """La consommation ne peut pas être imputée ou taxée telle que demandé."""


@dataclass(frozen=True)
class Poste:
    code: str
    libelle: str
    taux: float
    taux_bas: float
    taux_haut: float
    mixte: bool
    energie: str


@lru_cache(maxsize=1)
def postes(path: Path = POSTES) -> tuple[Poste, ...]:
    with path.open(encoding="utf-8") as f:
        return tuple(Poste(r["code"], r["libelle"], float(r["taux"]), float(r["taux_bas"]),
                           float(r["taux_haut"]), r["mixte"] == "1", r["energie"])
                     for r in csv.DictReader(f))


@lru_cache(maxsize=1)
def tf106(path: Path = BDF) -> dict[str, np.ndarray]:
    """La dépense moyenne par ménage de 2017 de chaque poste de la table, par décile, les
    postes de `REPARTIS` répartis entre les leurs.

    Refusé si un poste de la table manque à TF106, ou si une feuille de TF106 hors de la
    division 13 manque à la table : une dépense que la table oublie n'est jamais taxée."""
    if not path.exists():
        raise ConsommationError(f"{path.name} absent : `impots data fetch {path.name}`")
    with zipfile.ZipFile(path) as z:
        nom = next(n for n in z.namelist() if n.lower() == "tf106.csv")
        texte = z.read(nom).decode("latin-1")
    valeurs: dict[str, np.ndarray] = {}
    for r in csv.DictReader(io.StringIO(texte), delimiter=";"):
        if r["DECUC"] in {str(d) for d in range(1, 11)}:
            valeurs.setdefault(r["NOMENCLATURE"], np.zeros(10))[int(r["DECUC"]) - 1] = float(
                r["CONSO"])
    table = {p.code for p in postes()}
    manquants = sorted(table - set(valeurs))
    if manquants:
        raise ConsommationError(f"TF106 ne donne pas les postes {manquants} de la table")
    feuilles = {c for c in valeurs if len(c) == 5 and not c.startswith("13")}
    oublies = sorted(feuilles - table)
    if oublies:
        raise ConsommationError(f"la table oublie les postes {oublies} de TF106")
    out = {code: valeurs[code].copy() for code in sorted(table)}
    for code, (a, b) in REPARTIS.items():
        commun = out.pop(code)
        part = out[a] / (out[a] + out[b])
        out[a] = out[a] + commun * part
        out[b] = out[b] + commun * (1.0 - part)
    return out


@lru_cache(maxsize=1)
def _comptes(path: Path = CN) -> dict[str, dict[int, float]]:
    import openpyxl

    if not path.exists():
        raise ConsommationError(f"{path.name} absent : `impots data fetch {path.name}`")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = list(wb["MEURcour"].iter_rows(values_only=True))
    entete = next(r for r in rows if r and "2017" in [str(c) for c in r])
    colonnes = {int(c): j for j, c in enumerate(entete) if c is not None and str(c).isdigit()}
    out: dict[str, dict[int, float]] = {}
    for r in rows:
        code = str(r[1]).strip() if r and r[1] else ""
        if code.startswith("CP") and code[2:].isdigit():
            out[code] = {a: float(r[j]) for a, j in colonnes.items() if r[j] not in (None, "")}
    return out


def _total(cn: dict[str, dict[int, float]], annee: int) -> float:
    return sum(v[annee] for k, v in cn.items() if len(k) == 4 and int(k[2:]) <= 13)


def croissance(annee: int, prix_au_dela: dict[int, float] | None = None) -> dict[str, float]:
    """Le facteur qui porte les euros de 2017 de chaque poste à `annee`.

    Au-delà de la dernière année des comptes, les prix de `prix_au_dela` (un taux par
    année, ceux du texte noté) prolongent le total : il faut les donner."""
    cn = _comptes()
    derniere = min(annee, DERNIERE_ANNEE_CN)
    au_dela = 1.0
    for a in range(DERNIERE_ANNEE_CN + 1, annee + 1):
        if not prix_au_dela or a not in prix_au_dela:
            raise ConsommationError(f"pas de comptes nationaux en {a} : donner l'indice des "
                                    "prix de cette année")
        au_dela *= 1.0 + prix_au_dela[a]
    total = _total(cn, derniere) / _total(cn, ANNEE_ENQUETE)
    out = {}
    for p in postes():
        division = p.code[:2]
        facteur = total
        if division in DIVISIONS_COMMUNES:
            ligne = cn["CP" + division]
            facteur = ligne[derniere] / ligne[ANNEE_ENQUETE]
        out[p.code] = facteur * au_dela
    return out


def imputer(deciles: np.ndarray, uc: np.ndarray, poids: np.ndarray, annee: int,
            prix_au_dela: dict[int, float] | None = None) -> dict[str, np.ndarray]:
    """La dépense de chaque ménage, poste par poste, en euros de `annee`.

    `deciles` va de 1 à 10 (niveau de vie) ; `uc` sont les unités de consommation ; `poids`
    les poids des ménages, qui donnent la moyenne des unités de chaque décile."""
    d = np.asarray(deciles, dtype=int)
    if d.min() < 1 or d.max() > 10:
        raise ConsommationError("les déciles vont de 1 à 10")
    uc = np.asarray(uc, dtype=np.float64)
    poids = np.asarray(poids, dtype=np.float64)
    moyenne = np.array([np.average(uc[d == k], weights=poids[d == k]) if (d == k).any()
                        else 1.0 for k in range(1, 11)])
    relatif = uc / moyenne[d - 1]
    facteurs = croissance(annee, prix_au_dela)
    return {code: valeurs[d - 1] * relatif * facteurs[code]
            for code, valeurs in tf106().items()}


@dataclass(frozen=True)
class Fiscalite:
    """La TVA de chaque poste et les accises sur l'énergie, d'une année et d'un droit."""

    annee: int
    taux: dict[str, float] = field(default_factory=dict)
    accise: dict[str, float] = field(default_factory=dict)
    prix: dict[str, float] = field(default_factory=dict)

    @classmethod
    def droit(cls, annee: int, borne: str = "taux", *, annee_prix: int | None = None,
              prix_au_dela: dict[int, float] | None = None) -> Fiscalite:
        """Le droit de `annee` ; `borne` prend le taux principal des postes mêlés, ou leur
        taux le plus bas (`taux_bas`) ou le plus haut (`taux_haut`) : D-323. Les prix sont
        ceux de `annee_prix`, l'année des euros de la consommation, `annee` par défaut."""
        return cls(annee, {p.code: getattr(p, borne) for p in postes()}, loi_energie(annee),
                   prix_energie(annee if annee_prix is None else annee_prix, prix_au_dela))

    def reformee(self, spec) -> Fiscalite:
        """Le même droit, sous les boutons de consommation d'une `ReformSpec`."""
        taux = dict(self.taux)
        base = {p.code: p.taux for p in postes()}
        for bouton, valeur in ((0.20, spec.tva_taux_normal),
                               (0.10, spec.tva_taux_intermediaire),
                               (0.055, spec.tva_taux_reduit),
                               (0.021, spec.tva_taux_super_reduit)):
            if valeur is not None:
                for code, t in base.items():
                    if t == bouton:
                        taux[code] = valeur
        for cle, valeur in (spec.tva_postes or {}).items():
            for code in GROUPES.get(cle, (cle,)):
                if code not in taux:
                    raise ConsommationError(f"« {cle} » n'est ni un poste ni un groupe")
                taux[code] = valeur
        accise = dict(self.accise)
        for nom in accise:
            valeur = getattr(spec, f"accise_{nom}", None)
            if valeur is not None:
                accise[nom] = valeur
        return Fiscalite(self.annee, taux, accise, dict(self.prix))


#: Les volumes d'énergie : le poste, et la part de sa dépense qui va à chaque produit.
_ENERGIE = {"electricite": (("electricite", 1.0),), "gaz": (("gaz", 1.0),),
            "fioul": (("fioul", 1.0),),
            "carburants": (("gazole", PART_GAZOLE), ("essence", 1.0 - PART_GAZOLE))}


def taxes(conso: dict[str, np.ndarray], fisc: Fiscalite,
          reference: Fiscalite | None = None) -> dict[str, np.ndarray]:
    """La TVA et les accises de chaque ménage sous `fisc`.

    Sans `reference`, `fisc` est le droit sous lequel la dépense a été observée. Avec elle,
    la dépense est celle de `reference`, et `fisc` la taxe à volumes constants : la
    quantité achetée ne bouge pas, la taxe est répercutée en entier (R4, R5)."""
    ref = reference or fisc
    n = len(next(iter(conso.values())))
    tva = np.zeros(n)
    accises = np.zeros(n)
    par_taux: dict[float, np.ndarray] = {}
    energie = {p.code: p.energie for p in postes()}
    for code, depense in conso.items():
        t0, t1 = ref.taux[code], fisc.taux[code]
        if energie[code]:
            for produit, part in _ENERGIE[energie[code]]:
                d0 = depense * part
                volume = d0 / ref.prix[produit]
                hors_taxes = ref.prix[produit] / (1 + t0) - ref.accise[produit]
                d1 = volume * (hors_taxes + fisc.accise[produit]) * (1 + t1)
                accises += volume * fisc.accise[produit]
                v = d1 * t1 / (1 + t1)
                tva += v
                par_taux[t1] = par_taux.get(t1, 0) + v
        else:
            v = depense / (1 + t0) * t1
            tva += v
            par_taux[t1] = par_taux.get(t1, 0) + v
    return {"tva": tva, "accises": accises, **{f"tva_{t:g}": v for t, v in par_taux.items()}}


#: Les boutons de `ReformSpec` que cette couche lit, et que l'arbre d'openfisca ignore.
BOUTONS = ("tva_taux_normal", "tva_taux_intermediaire", "tva_taux_reduit",
           "tva_taux_super_reduit", "tva_postes", "accise_gazole", "accise_essence",
           "accise_fioul", "accise_electricite", "accise_gaz")


def touche(spec) -> bool:
    """Si une réforme règle un bouton de la consommation."""
    return spec is not None and any(getattr(spec, b, None) is not None for b in BOUTONS)


def sans_consommation(spec):
    """La même réforme sans ses boutons de consommation : ce que l'arbre reçoit."""
    return spec.model_copy(update=dict.fromkeys(BOUTONS))


def imputer_menages(households, annee: int, prix_au_dela: dict[int, float] | None = None,
                    ) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    # `annee` est celle des euros de la consommation, qui suit la population (D-328).
    """La consommation de chaque ménage d'une passe, poste par poste, avec ses poids et son
    niveau de vie (le revenu disponible de référence par unité de consommation)."""
    from impots.population.aggregate import consumption_units, weighted_decile_index

    uc = consumption_units(households["n_aged_14_plus"].to_numpy(),
                           households["n_children_under_14"].to_numpy())
    poids = households["weight"].to_numpy().astype(np.float64)
    niveau = households["revenu_disponible"].to_numpy().astype(np.float64) / uc
    deciles = weighted_decile_index(niveau, poids) + 1
    if prix_au_dela is None and annee > DERNIERE_ANNEE_CN:
        # Past the national accounts, the prices of the set that ages the cases of the
        # PLF 2027 (D-317), the same everywhere a pass imputes consumption (D-323).
        from impots import hypotheses

        prix_au_dela = dict(hypotheses.jeu("plf2027").prix)
    return imputer(deciles, uc, poids, annee, prix_au_dela), poids, niveau


def colonnes(households, annee: int, spec=None,
             prix_au_dela: dict[int, float] | None = None,
             annee_consommation: int | None = None) -> dict[str, np.ndarray]:
    """La TVA et les accises de chaque ménage d'une passe, au droit de `annee` et, si une
    réforme est donnée, sous elle : les colonnes que le registre des recettes lit.

    La consommation suit la population (D-328) : ses euros sont ceux de
    `annee_consommation`, l'année où la population a été vieillie, ou son millésime quand
    elle ne l'est pas ; `annee` par défaut. Les prix qui en tirent les volumes sont ceux de
    la même année ; le droit, celui de `annee`."""
    euros = annee if annee_consommation is None else annee_consommation
    if euros > DERNIERE_ANNEE_CN and prix_au_dela is None:
        from impots import hypotheses

        prix_au_dela = dict(hypotheses.jeu("plf2027").prix)
    conso, _, _ = imputer_menages(households, euros, prix_au_dela)
    droit = Fiscalite.droit(annee, annee_prix=euros, prix_au_dela=prix_au_dela)
    base = taxes(conso, droit)
    out = {"tva_menages": base["tva"], "accises_energie": base["accises"],
           "consommation_imputee": sum(conso.values())}
    if touche(spec):
        reforme = taxes(conso, droit.reformee(spec), reference=droit)
        out["tva_menages_reform"] = reforme["tva"]
        out["accises_energie_reform"] = reforme["accises"]
    return out
