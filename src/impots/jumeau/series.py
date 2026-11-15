"""Les séries publiées de 2010 à 2025 que le jumeau rejoue (but 23, lot 5, D-410).

Le lot 6 note le jumeau sur l'histoire : il lui faut, pour chaque année, ce qui s'est
passé, tel que l'Insee, Eurostat et la Banque de France l'ont publié. Ce module lit ces
séries dans les fichiers manifestés de `data/raw` (D-028 : un fichier sans source est
refusé avant d'être ouvert) et dit, pour chacune, d'où elle vient et sous quel code.

CE QUE CHAQUE SÉRIE PORTE, et ce qu'elle n'est pas :

* les comptes nationaux de l'Insee, base 2020, millésime 2025 : les emplois du PIB
  (t. 1.101, déjà lus par `historique`), les indices de prix (t. 1.103) et les volumes
  chaînés (t. 1.102), les principaux impôts (t. 3.217), le passage du déficit à la dette
  (t. 3.105), l'emploi intérieur total et salarié (t. 6.208, 6.210) et les salaires bruts
  (t. 6.205). Le salaire moyen par tête est le quotient des deux derniers : un calcul dit,
  comme D-362, pas une série que l'Insee imprime ;
* le chômage au sens du BIT (Eurostat une_rt_a, 15-74 ans) et le taux de l'OAT à dix ans
  (Eurostat irt_lt_mcby_a, le critère de convergence) ;
* les créations d'entreprises (Insee, BDM, méthode 2022 : l'année est la somme des douze
  mois bruts, ce que l'Insee publie comme nombre annuel) et les défaillances (Banque de
  France, reprises par la BDM : l'année est le cumul brut glissant de décembre) ;
* les cotisations sociales effectives reçues par les APU, à la charge des employeurs
  (D611) et des salariés (D613CE), lues dans le compte des APU (t. 7.301) : la t. 3.217
  n'en publie que la somme avec celles des non-salariés (D-421) ;
* la demande mondiale adressée à la France en volume (OCDE, Economic Outlook n° 119,
  « Export market for goods and services, volume », XMKT, dollars de 2021 chaînés) : la
  somme des importations des partenaires pondérées par leur part dans les exportations
  françaises (D-421).

CHAQUE SÉRIE RECOUPE SON TOTAL PUBLIÉ (`recoupements`), et l'écart est dit, jamais
absorbé : les secteurs d'une table contre son total, la t. 3.217 contre la t. 3.201,
les sous-lignes de la t. 3.105 contre leurs groupes et contre Eurostat, les sexes du
chômage contre l'ensemble, les mois de l'OAT contre l'année. Un écart au-delà de
l'arrondi imprimé est un constat que le test fige, pas un résidu qu'on borne après coup.

Une valeur absente ou textuelle (« N.D. ») d'une année où la série doit exister est
refusée ; une case vide de la t. 3.217 est l'impôt qui n'existe pas cette année-là
(la CVAE avant 2010, la taxe professionnelle après) : la série n'a pas cette année, elle
n'y vaut pas zéro.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from impots.dette import comptes
from impots.jumeau.champs import IMPOTS_3217

PREMIERE, DERNIERE = 2010, 2025
ANNEES = tuple(range(PREMIERE, DERNIERE + 1))

T1102_1103 = comptes.PIB_FILE
T3105 = "insee_cn2025_t3105_passage_deficit_dette.xlsx"
T3217 = "insee_cn2025_t3217_principaux_impots_par_categorie.xlsx"
T6205 = "insee_cn2025_t6205_salaires_bruts_branches.xlsx"
T6208 = "insee_cn2025_t6208_emploi_total_branches.xlsx"
T6210 = "insee_cn2025_t6210_emploi_salarie_branches.xlsx"
BDM_CREATIONS = "insee_bdm_creations_entreprises_2009_2025.xml"
BDM_DEFAILLANCES = "insee_bdm_defaillances_entreprises_2009_2025.xml"
EUROSTAT_CHOMAGE = "eurostat_une_rt_a_fr_2009_2025.json"
EUROSTAT_OAT = "eurostat_irt_lt_mcby_a_fr_2009_2025.json"
EUROSTAT_OAT_MOIS = "eurostat_irt_lt_mcby_m_fr_2009_2025.json"
T7301 = comptes.APU_FILE
OCDE_EO = "ocde_eo119_xmkt_fra_2009_2025.csv"

#: Tous les fichiers que ce module ouvre, pour les tests qui en dépendent.
FICHIERS = (T1102_1103, T3105, T3217, T6205, T6208, T6210, BDM_CREATIONS,
            BDM_DEFAILLANCES, EUROSTAT_CHOMAGE, EUROSTAT_OAT, EUROSTAT_OAT_MOIS,
            comptes.TOTALS_FILE, comptes.SFA_FILE, T7301, OCDE_EO)

#: La moitié de la dernière décimale imprimée : au millième de milliard (t. 1.10x),
#: au centième (t. 3.217), au dixième (t. 3.105, et les milliers de personnes de 6.208).
DEMI = {"millieme": 0.0005, "centieme": 0.005, "dixieme": 0.05}


class SerieError(ValueError):
    """Une série publiée qui ne se lit pas comme ce module le dit."""


@dataclass(frozen=True)
class Serie:
    nom: str
    libelle: str
    unite: str
    producteur: str
    fichier: str
    code: str
    """Le code de la série chez son producteur : idbank, code de ligne, poste Eurostat."""
    lire: Callable[[], dict[int, float]]


# ------------------------------------------------------------------ lecture des fichiers
def _sourcer(fichier: str) -> None:
    from impots.population.ingest import require_sourced

    require_sourced(fichier)
    if not (comptes.RAW / fichier).exists():
        raise SerieError(f"{fichier} est au manifeste mais absent de data/raw "
                         f"(`impots data fetch {fichier}`)")


def _nombre(valeur: Any, quoi: str) -> float:
    if valeur is None or isinstance(valeur, str):
        raise SerieError(f"{quoi} : cellule « {valeur} », lue comme zéro elle passerait")
    return float(valeur)


@functools.cache
def _feuille(fichier: str, onglet: str) -> tuple[list[tuple[Any, ...]], dict[int, int]]:
    rows = comptes._rows(fichier, onglet)
    return rows, comptes._year_columns(rows)


def _ligne_code(fichier: str, onglet: str, code: str, *, apres: str | None = None,
                premiere: int = PREMIERE) -> dict[int, float]:
    """La ligne de code `code` (colonne A) d'une table des comptes nationaux, de
    `premiere` à 2025 ; `apres` désigne le total sous lequel chercher un code qui se
    répète (S13 est à la fois sous P3 et sous P51G)."""
    rows, colonnes = _feuille(fichier, onglet)
    debut = 0
    if apres is not None:
        debuts = [i for i, r in enumerate(rows) if r[0] is not None
                  and str(r[0]).strip() == apres]
        if len(debuts) != 1:
            raise SerieError(f"{fichier} {onglet} : {len(debuts)} ligne(s) « {apres} »")
        debut = debuts[0]
    trouves = [i for i, r in enumerate(rows) if i >= debut and r[0] is not None
               and str(r[0]).strip() == code]
    if not trouves:
        raise SerieError(f"{fichier} {onglet} : ligne « {code} » absente")
    i = trouves[0]
    return {a: _nombre(rows[i][colonnes[a]], f"{fichier} {code} {a}")
            for a in range(premiere, DERNIERE + 1)}


def _lignes_libelle(fichier: str, onglet: str) -> dict[str, list[int]]:
    rows, _ = _feuille(fichier, onglet)
    places: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        libelle = r[1].strip() if isinstance(r[1], str) else ""
        if libelle:
            places.setdefault(libelle, []).append(i)
    return places


def _ligne_libelle(fichier: str, onglet: str, libelle: str, *, vide_absent: bool = False
                   ) -> dict[int, float]:
    """La ligne de libellé exact `libelle` ; une case vide est une année sans la série si
    `vide_absent` (la t. 3.217), refusée sinon. « N.D. » est toujours refusé."""
    rows, colonnes = _feuille(fichier, onglet)
    places = _lignes_libelle(fichier, onglet)
    if len(places.get(libelle, [])) != 1:
        raise SerieError(f"{fichier} : {len(places.get(libelle, []))} ligne(s) "
                         f"« {libelle} », attendu 1 (libellé entier)")
    out = {}
    for a in ANNEES:
        cellule = rows[places[libelle][0]][colonnes[a]]
        if vide_absent and cellule in (None, ""):
            continue
        out[a] = _nombre(cellule, f"{fichier} « {libelle} » {a}")
    return out


@functools.cache
def _eurostat(fichier: str) -> dict[tuple[str, ...], dict[str, float]]:
    """Un fichier JSON-stat d'Eurostat : {(modalités hors temps) : {période : valeur}}."""
    _sourcer(fichier)
    donnees = json.loads((comptes.RAW / fichier).read_text(encoding="utf-8"))
    dims = donnees["id"]
    tailles = donnees["size"]
    index = {d: {v: k for k, v in donnees["dimension"][d]["category"]["index"].items()}
             for d in dims}
    out: dict[tuple[str, ...], dict[str, float]] = {}
    for cle, valeur in donnees["value"].items():
        reste, position = int(cle), []
        for d, n in zip(reversed(dims), reversed(tailles), strict=True):
            position.append(index[d][reste % n])
            reste //= n
        position.reverse()
        temps = position[dims.index("time")]
        modalites = tuple(p for d, p in zip(dims, position, strict=True) if d != "time")
        out.setdefault(modalites, {})[temps] = float(valeur)
    return out


def _eurostat_serie(fichier: str, *modalites: str) -> dict[str, float]:
    donnees = _eurostat(fichier)
    trouves = [m for m in donnees if all(x in m for x in modalites)]
    if len(trouves) != 1:
        raise SerieError(f"{fichier} : {len(trouves)} série(s) pour {modalites}")
    return donnees[trouves[0]]


@functools.cache
def _bdm(fichier: str) -> dict[str, dict[str, float]]:
    """Un export SDMX de la BDM : {idbank : {période : valeur}} ; une observation sans
    valeur numérique est refusée."""
    _sourcer(fichier)
    texte = (comptes.RAW / fichier).read_text(encoding="utf-8")
    out: dict[str, dict[str, float]] = {}
    for entete, corps in re.findall(r"<Series ([^>]*)>(.*?)</Series>", texte, re.S):
        attributs = dict(re.findall(r'(\w+)="([^"]*)"', entete))
        obs = {}
        for o in re.findall(r"<Obs ([^>]*)/>", corps):
            a = dict(re.findall(r'(\w+)="([^"]*)"', o))
            if a.get("OBS_VALUE") in (None, "", "NaN"):
                raise SerieError(f"{fichier} {attributs['IDBANK']} {a.get('TIME_PERIOD')} : "
                                 f"observation sans valeur ({a.get('OBS_STATUS')})")
            obs[a["TIME_PERIOD"]] = float(a["OBS_VALUE"])
        out[attributs["IDBANK"]] = obs
    return out


def _annuel_eurostat(fichier: str, *modalites: str) -> dict[int, float]:
    serie = _eurostat_serie(fichier, *modalites)
    manquants = [a for a in ANNEES if str(a) not in serie]
    if manquants:
        raise SerieError(f"{fichier} {modalites} : années absentes {manquants}")
    return {a: serie[str(a)] for a in ANNEES}


def _somme_mois(fichier: str, idbank: str) -> dict[int, float]:
    serie = _bdm(fichier)[idbank]
    out = {}
    for a in ANNEES:
        mois = [serie.get(f"{a}-{m:02d}") for m in range(1, 13)]
        if any(v is None for v in mois):
            raise SerieError(f"{fichier} {idbank} {a} : {mois.count(None)} mois absent(s)")
        out[a] = sum(mois)       # type: ignore[arg-type]
    return out


def _decembre(fichier: str, idbank: str) -> dict[int, float]:
    serie = _bdm(fichier)[idbank]
    manquants = [a for a in ANNEES if f"{a}-12" not in serie]
    if manquants:
        raise SerieError(f"{fichier} {idbank} : décembre absent en {manquants}")
    return {a: serie[f"{a}-12"] for a in ANNEES}


def _ocde_eo(fichier: str, mesure: str, pays: str) -> dict[int, float]:
    """Une série annuelle de l'Economic Outlook de l'OCDE, export CSV du SDMX (une
    observation par ligne), de 2009 à 2025 ; une année absente ou deux fois est refusée."""
    import csv

    _sourcer(fichier)
    with (comptes.RAW / fichier).open(encoding="utf-8-sig", newline="") as f:
        lignes = [r for r in csv.DictReader(f)
                  if r["MEASURE"] == mesure and r["REF_AREA"] == pays and r["FREQ"] == "A"]
    out: dict[int, float] = {}
    for r in lignes:
        a = int(r["TIME_PERIOD"])
        if a in out:
            raise SerieError(f"{fichier} {mesure} {pays} {a} : deux observations")
        out[a] = _nombre(float(r["OBS_VALUE"]) if r["OBS_VALUE"] else None,
                         f"{fichier} {mesure} {a}")
    manquants = [a for a in range(PREMIERE - 1, DERNIERE + 1) if a not in out]
    if manquants:
        raise SerieError(f"{fichier} {mesure} {pays} : années absentes {manquants}")
    return {a: out[a] for a in range(PREMIERE - 1, DERNIERE + 1)}


# ------------------------------------------------------------------ le registre
_REGISTRE: dict[str, Serie] = {}


def _serie(nom: str, libelle: str, unite: str, producteur: str, fichier: str, code: str,
           lire: Callable[[], dict[int, float]]) -> None:
    if nom in _REGISTRE:
        raise ValueError(f"série « {nom} » déclarée deux fois")
    _REGISTRE[nom] = Serie(nom, libelle, unite, producteur, fichier, code, lire)


INSEE_CN = "Insee, comptes nationaux annuels base 2020 (millésime 2025)"
MDE = "Md€ courants"

# Les emplois du PIB, t. 1.101 : la valeur, déjà lue par `historique` ; le volume chaîné
# (t. 1.102, Md€ 2020) et l'indice de prix (t. 1.103, base 100 en 2020). Ces trois-là
# commencent en 2009 : le prix et le volume de 2010 se lisent contre l'année d'avant.
#: (nom, total de la t. 1.10x, secteur)
EMPLOIS_SERIES: tuple[tuple[str, str, str | None], ...] = (
    ("pib", "B1GQ", None), ("c_menages", "P3", "S14B"), ("c_isbl", "P3", "S15"),
    ("c_apu", "P3", "S13"), ("fbcf", "P51G", None), ("fbcf_snf", "P51G", "S11X14AA"),
    ("fbcf_sf", "P51G", "S12X14AF"), ("fbcf_apu", "P51G", "S13"),
    ("fbcf_menages", "P51G", "S14B"), ("fbcf_isbl", "P51G", "S15"),
    ("objets_valeur", "P53", None), ("exportations", "P6", None),
    ("importations", "P7", None))
for _nom, _total, _secteur in EMPLOIS_SERIES:
    _code = f"{_total} {_secteur}" if _secteur else _total
    for _quoi, _onglet, _unite, _prefixe in (
            ("valeur", "T_1101 en niveau", MDE, ""),
            ("volume chaîné", "T_1102 en niveau", "Md€ 2020 chaînés", "volume_"),
            ("indice de prix", "T_1103 en niveau", "indice, 2020 = 100", "indice_prix_")):
        _serie(f"{_prefixe}{_nom}", f"{_code}, {_quoi}", _unite, INSEE_CN,
               T1102_1103, f"t. {_onglet[2]}.{_onglet[3:6]} {_code}",
               functools.partial(_ligne_code, T1102_1103, _onglet,
                                 _secteur or _total, apres=_total if _secteur else None,
                                 premiere=PREMIERE - 1))
_serie("var_stocks", "P52, valeur", MDE, INSEE_CN, T1102_1103, "t. 1.101 P52",
       functools.partial(_ligne_code, T1102_1103, "T_1101 en niveau", "P52"))

# Les principaux impôts, t. 3.217, Md€ courants : la liste est au registre des champs,
# que `historique` écrit dans l'état publié (`champs.IMPOTS_3217`).
#: Les catégories de la t. 3.217 qui somment au D2 de la t. 3.201 (moins les impôts de
#: l'Union européenne), au D5 et au D91.
CATEGORIES_D2 = ("Taxe sur la valeur ajoutée (TVA) (D211)",
                 "Impôts et droits sur les importations (D212)",
                 "Impôts sur les produits (D214)",
                 "Impôts sur les salaires et la main d'œuvre (D291)",
                 "Impôts divers sur la production (D292)")
CATEGORIES_D5 = ("Impôts courants sur le revenu (D51)", "Autres impôts courants (D59)")
CATEGORIE_D91 = "Impôts en capital (D91r)"
IMPOTS_UE = "dont impôts de l’Union européenne"
for _nom, _libelle in IMPOTS_3217:
    _serie(f"impot_{_nom}", _libelle, MDE, INSEE_CN, T3217, f"t. 3.217 « {_libelle} »",
           functools.partial(_ligne_libelle, T3217, "T_3217", _libelle, vide_absent=True))

# Le passage du déficit à la dette, t. 3.105, Md€ au dixième.
T3105_DEFICIT = "Déficit des administrations publiques (*) - D"
T3105_GROUPES = (
    "Acquisitions d'actifs nettes des cessions et hors autres comptes à recevoir (1)",
    "Variation du passif financier hors dette de Maastricht et hors autres comptes à "
    "payer (2)",
    "Changements de volume inclus dans la dette de Maastricht (3)",
    "F8 Solde des autres comptes à recevoir/à payer (4)",
    "Ecart statistique B9nf - B9f (5)")
T3105_VARIATION = ("Variation de la dette au sens de Maastricht = D + (1) + (2) + (3) + "
                   "(4) + (5)")


def _t3105(libelle: str) -> dict[int, float]:
    return _ligne_libelle(T3105, "t_3105", libelle)


def sfa_insee() -> dict[int, float]:
    """L'ajustement flux-stocks de l'Insee : la somme des cinq groupes imprimés de la
    t. 3.105, (1) à (5), Md€."""
    groupes = [_t3105(g) for g in T3105_GROUPES]
    return {a: sum(g[a] for g in groupes) for a in ANNEES}


_serie("deficit_maastricht", "Déficit des APU (D, compté positif)", MDE, INSEE_CN, T3105,
       "t. 3.105 D", functools.partial(_t3105, T3105_DEFICIT))
_serie("variation_dette", "Variation de la dette de Maastricht", MDE, INSEE_CN, T3105,
       "t. 3.105 D + (1) + … + (5)", functools.partial(_t3105, T3105_VARIATION))
_serie("sfa_insee", "Ajustement flux-stocks, (1) + … + (5)", MDE, INSEE_CN, T3105,
       "t. 3.105 (1) à (5)", sfa_insee)

# Le travail : l'emploi intérieur (milliers de personnes) et les salaires bruts (Md€).
_serie("emploi_total", "Emploi intérieur total", "milliers de personnes", INSEE_CN, T6208,
       "t. 6.208 _T", functools.partial(_ligne_code, T6208, "T_6208 en niveau", "_T"))
_serie("emploi_salarie", "Emploi intérieur salarié", "milliers de personnes", INSEE_CN,
       T6210, "t. 6.210 _T",
       functools.partial(_ligne_code, T6210, "T_6210 en niveau", "_T"))
_serie("salaires_bruts", "Salaires et traitements bruts (D11)", MDE, INSEE_CN, T6205,
       "t. 6.205 _T", functools.partial(_ligne_code, T6205, "T_6205 en niveau", "_T"))


def salaire_moyen() -> dict[int, float]:
    """Le salaire brut moyen par tête, en euros par an : D11 (t. 6.205) sur l'emploi
    intérieur salarié (t. 6.210). Un quotient de deux séries publiées (D-362)."""
    d11 = lire("salaires_bruts")
    emploi = lire("emploi_salarie")
    return {a: d11[a] * 1e9 / (emploi[a] * 1e3) for a in ANNEES}


_serie("salaire_moyen", "Salaire brut moyen par tête (D11 / emploi salarié)", "€ par an",
       INSEE_CN, T6205, "t. 6.205 _T / t. 6.210 _T", salaire_moyen)

EUROSTAT = "Eurostat"
_serie("taux_chomage", "Taux de chômage au sens du BIT, 15-74 ans", "% de la population "
       "active", EUROSTAT, EUROSTAT_CHOMAGE, "une_rt_a FR Y15-74 T PC_ACT",
       functools.partial(_annuel_eurostat, EUROSTAT_CHOMAGE, "PC_ACT", "T"))
_serie("chomeurs", "Chômeurs au sens du BIT, 15-74 ans", "milliers de personnes",
       EUROSTAT, EUROSTAT_CHOMAGE, "une_rt_a FR Y15-74 T THS_PER",
       functools.partial(_annuel_eurostat, EUROSTAT_CHOMAGE, "THS_PER", "T"))
_serie("taux_oat_10ans", "Rendement de l'OAT à dix ans, moyenne annuelle", "%", EUROSTAT,
       EUROSTAT_OAT, "irt_lt_mcby_a FR MCBY",
       functools.partial(_annuel_eurostat, EUROSTAT_OAT, "MCBY"))

BDM = "Insee, BDM"
CREATIONS = {"creations_entreprises": ("010755537", "Créations d'entreprises, ensemble"),
             "creations_micro": ("010755410", "Créations de micro-entrepreneurs"),
             "creations_classiques": ("011811818", "Créations d'entreprises classiques "
                                      "(hors micro-entrepreneurs)"),
             "creations_ei_hors_micro": ("011811817", "Créations d'entrepreneurs "
                                         "individuels hors micro-entrepreneurs")}
for _nom, (_idbank, _libelle) in CREATIONS.items():
    _serie(_nom, _libelle, "unités par an", BDM, BDM_CREATIONS,
           f"idbank {_idbank} (somme des douze mois bruts)",
           functools.partial(_somme_mois, BDM_CREATIONS, _idbank))
DEFAILLANCES_TOTAL = "001656101"
DEFAILLANCES_SECTEURS = ("001656093", "001656094", "001656095", "001656096", "001656097",
                         "001656098", "001656099", "001656100", "001656102", "001656103",
                         "001656104")
_serie("defaillances", "Défaillances d'entreprises, tous secteurs", "unités par an",
       "Banque de France, via la BDM de l'Insee", BDM_DEFAILLANCES,
       f"idbank {DEFAILLANCES_TOTAL} (cumul brut sur 12 mois, décembre)",
       functools.partial(_decembre, BDM_DEFAILLANCES, DEFAILLANCES_TOTAL))

# Les cotisations effectives reçues par les APU, par payeur (t. 7.301, ressources) : la
# t. 3.217 publie leur somme avec les cotisations des non-salariés, D611 + D613.
_serie("cotisations_employeurs_apu", "D611, cotisations effectives à la charge des "
       "employeurs, reçues par les APU", MDE, INSEE_CN, T7301, "t. 7.301 S13 D611",
       functools.partial(_ligne_code, T7301, "T_7301", "D611"))
_serie("cotisations_salaries_apu", "D613CE, cotisations effectives obligatoires à la "
       "charge des salariés, reçues par les APU", MDE, INSEE_CN, T7301,
       "t. 7.301 S13 D613CE", functools.partial(_ligne_code, T7301, "T_7301", "D613CE"))
_serie("cotisations_menages_apu", "D613, cotisations effectives à la charge des ménages "
       "(salariés et non-salariés), reçues par les APU", MDE, INSEE_CN, T7301,
       "t. 7.301 S13 D613", functools.partial(_ligne_code, T7301, "T_7301", "D613"))

_serie("demande_mondiale", "Demande mondiale adressée à la France, en volume",
       "dollars de 2021, volumes chaînés", "OCDE, Economic Outlook n° 119", OCDE_EO,
       "EO XMKT FRA A", functools.partial(_ocde_eo, OCDE_EO, "XMKT", "FRA"))

SERIES: dict[str, Serie] = dict(_REGISTRE)


def lire(nom: str) -> dict[int, float]:
    """La série `nom`, {année : valeur}, de 2010 à 2025 (moins les années où elle
    n'existe pas, pour un impôt de la t. 3.217)."""
    if nom not in SERIES:
        raise SerieError(f"série « {nom} » inconnue (jumeau/series.py)")
    return SERIES[nom].lire()


# ------------------------------------------------------------------ les recoupements
def _somme_secteurs(fichier: str, onglet: str, prefixe: str) -> dict[int, float]:
    rows, colonnes = _feuille(fichier, onglet)
    lignes = [i for i, r in enumerate(rows) if r[0] is not None
              and str(r[0]).strip().startswith(prefixe)]
    return {a: sum(_nombre(rows[i][colonnes[a]], f"{fichier} {rows[i][0]} {a}")
                   for i in lignes) for a in ANNEES}


def recoupements() -> dict[str, dict[int, float]]:
    """Chaque série contre son total publié : {recoupement : {année : écart}}, l'écart
    dans l'unité de la série (Md€, milliers, points de %, unités)."""
    out: dict[str, dict[int, float]] = {}

    # Les indices de prix contre la valeur sur le volume (t. 1.103 = 1.101 / 1.102).
    for nom, _, _ in EMPLOIS_SERIES:
        valeur, volume, indice = (lire(f"{p}{nom}") for p in ("", "volume_", "indice_prix_"))
        out[f"indice_prix_{nom}"] = {a: indice[a] - 100 * valeur[a] / volume[a]
                                     for a in ANNEES}

    # La t. 3.217 contre la t. 3.201 : D2 moins les impôts de l'UE, D5, D91.
    from impots.jumeau import historique

    apu = historique._t3201()
    categorie = functools.partial(_ligne_libelle, T3217, "T_3217", vide_absent=True)
    d2 = [categorie(c) for c in CATEGORIES_D2]
    ue = categorie(IMPOTS_UE)
    d5 = [categorie(c) for c in CATEGORIES_D5]
    d91 = categorie(CATEGORIE_D91)
    out["t3217_d2_moins_ue"] = {a: sum(c[a] for c in d2) - ue[a] - apu[a]["apu_r_d2"]
                                for a in ANNEES}
    out["t3217_d5"] = {a: sum(c[a] for c in d5) - apu[a]["apu_r_d5"] for a in ANNEES}
    out["t3217_d91"] = {a: d91[a] - apu[a]["apu_r_d91"] for a in ANNEES}

    # La t. 3.105 : ses lignes somment à la variation ; son déficit est −B9 de la
    # t. 3.201 ; son ajustement est celui d'Eurostat les années où Eurostat le publie.
    deficit, variation, sfa = (lire(n) for n in ("deficit_maastricht", "variation_dette",
                                                  "sfa_insee"))
    out["t3105_variation"] = {a: variation[a] - deficit[a] - sfa[a] for a in ANNEES}
    out["t3105_deficit"] = {a: deficit[a] + apu[a]["b9"] for a in ANNEES}
    eurostat = historique._eurostat()
    out["t3105_eurostat"] = {a: sfa[a] - (e["F_ASS"] + e["ORADJ"] + e["YA3"])
                             for a, e in eurostat.items() if a in ANNEES}

    # L'emploi et les salaires : le total des branches contre ses cinq grandes branches.
    for nom, fichier, onglet in (("emploi_total", T6208, "T_6208 en niveau"),
                                 ("emploi_salarie", T6210, "T_6210 en niveau"),
                                 ("salaires_bruts", T6205, "T_6205 en niveau")):
        total = lire(nom)
        branches = _somme_secteurs(fichier, onglet, "A5_")
        out[nom] = {a: total[a] - branches[a] for a in ANNEES}

    # Le chômage : hommes plus femmes contre l'ensemble.
    hommes = _annuel_eurostat(EUROSTAT_CHOMAGE, "THS_PER", "M")
    femmes = _annuel_eurostat(EUROSTAT_CHOMAGE, "THS_PER", "F")
    ensemble = lire("chomeurs")
    out["chomeurs"] = {a: ensemble[a] - hommes[a] - femmes[a] for a in ANNEES}

    # L'OAT : la moyenne annuelle contre celle des douze mois.
    mois = _eurostat_serie(EUROSTAT_OAT_MOIS, "MCBY")
    oat = lire("taux_oat_10ans")
    out["taux_oat_10ans"] = {a: oat[a] - sum(mois[f"{a}-{m:02d}"] for m in range(1, 13)) / 12
                             for a in ANNEES}

    # Les créations : les micro-entrepreneurs plus les entreprises classiques ; les
    # défaillances : les onze secteurs contre le total.
    micro, classiques, toutes = (lire(n) for n in ("creations_micro",
                                                   "creations_classiques",
                                                   "creations_entreprises"))
    out["creations_entreprises"] = {a: toutes[a] - micro[a] - classiques[a]
                                    for a in ANNEES}
    secteurs = [_decembre(BDM_DEFAILLANCES, i) for i in DEFAILLANCES_SECTEURS]
    total = lire("defaillances")
    out["defaillances"] = {a: total[a] - sum(s[a] for s in secteurs) for a in ANNEES}

    # Les cotisations effectives par payeur (t. 7.301) contre leur somme (t. 3.217).
    employeurs, menages = lire("cotisations_employeurs_apu"), lire("cotisations_menages_apu")
    effectives = lire("impot_cotisations_effectives")
    out["cotisations_effectives"] = {a: effectives[a] - employeurs[a] - menages[a]
                                     for a in ANNEES}
    return out
