"""L'état publié d'une année, de 2010 à 2025 (CADRE.md §6) : `etat_initial(annee)`.

Lu dans les tables manifestées, chaque fichier ouvert une fois par processus :

* Insee t. 1.101 (emplois du PIB, par secteur) et t. 1.105 (l'approche revenus) ;
* Insee t. 3.201 (le compte consolidé des APU, ligne à ligne, et ses totaux) ;
* la dette de Maastricht de fin d'année de l'Insee (`dette.comptes.debt`, unités
  vérifiées par `check_units`) ;
* l'ajustement flux-stocks d'Eurostat (gov_10dd_edpt3) de 2021 à 2025, et celui de
  l'Insee (t. 3.105, le passage du déficit à la dette) de 2010 à 2020 (lot 5, D-410) ;
* les indices de prix (t. 1.103) et le volume chaîné du PIB (t. 1.102), et les
  principaux impôts (t. 3.217), par `jumeau.series` (lot 5, D-410).

CE QUE LES COMPTES PUBLIÉS NE BOUCLENT PAS, ET CE QUE LE CADRE EN FAIT (D-405). Chaque
écart est un champ nommé, LU dans les publications, jamais un résidu silencieux :

* les tables de l'Insee sont imprimées au millième de milliard : la somme des totaux
  publiés s'écarte du PIB publié d'un ou deux millièmes (``arrondi_emplois``,
  ``arrondi_revenus``). Un écart au-delà de l'arrondi imprimé est refusé ;
* en 2023 et 2024, les secteurs de P3 et de P51G de la t. 1.101 ne somment pas à leurs
  totaux (de 0,12 et 0,09 Md€ en tout) : ``ventilation_emplois``, le total publié moins la
  somme publiée de ses secteurs ;
* l'ajustement d'Eurostat est F_ASS + ORADJ + YA3 : ORADJ, le total des ajustements,
  contient déjà K61 et KX (`comptes.SFA_COMPOSANTES`, corrigé par D-410) ;
  ``ecart_eurostat`` est GD_CH − B9_T3 moins cet ajustement, l'écart interne
  de la table : de −0,1 à +0,3 million, il dépasse en 2023 l'arrondi de ses cinq postes
  imprimés au dixième de million, parce que ces postes sont eux-mêmes des totaux de
  postes arrondis ; il n'est donc borné par aucun arrondi, il est lu et dit (D-405) ;
  ``ecart_millesime_dette`` est l'écart entre l'Insee et Eurostat sur la
  variation du stock et sur B9 (0,35 Md€ en 2025, où le stock de l'Insee est plus récent).

L'AJUSTEMENT D'AVANT 2021 (D-410). Eurostat ne publie la table de passage de la France
que de 2021 à 2025 ; l'Insee publie la sienne, la t. 3.105, de 2009 à 2025, au même
millésime que la t. 3.201 et que la dette. De 2010 à 2020, ``sfa`` est la somme de ses
cinq groupes imprimés, (1) à (5) ; ``ecart_eurostat`` (le nom du lot 1) y est l'écart
interne de la table, sa variation moins son déficit moins l'ajustement (nul : la table
somme exactement) ; ``ecart_millesime_dette`` est la variation du stock de l'Insee moins
celle de la table, plus B9 et le déficit de la table : quelques centièmes de milliard,
l'arrondi au dixième, sauf 2014 (−0,63 Md€, où la table et le stock divergent).
De 2021 à 2025, la table d'Eurostat est gardée, imprimée au dixième de million ; la
t. 3.105 la recoupe à l'arrondi près (`series.recoupements`).

LES PRIX ET LE VOLUME (D-410). ``prix_<emploi>`` est l'indice de la t. 1.103 de l'année
sur celui de l'année d'avant ; la variation des stocks n'a pas d'indice publié, et son
prix est absent, comme celui de l'effet non ventilé, nul sur l'histoire. La croissance
du PIB en volume est celle que publie la t. 1.102, pas celle que le cadre chaînerait :
sans prix des stocks, la formule du cadre ne se calcule pas sur l'histoire.

L'HISTOIRE LONGUE, DE 1996 À 2009 (D-446). `etat_initial` lit aussi ces années, chaque
série depuis 1995 (`series.lire(..., longue=True)`) ; la dette de l'Insee commence au
quatrième trimestre de 1995, d'où 1996. L'ajustement flux-stocks n'y est imprimé nulle
part (la t. 3.105 commence en 2009, la table d'Eurostat en 2021) : avant 2010, ``sfa`` est
la variation du stock de la dette de l'Insee moins le déficit de la t. 3.201 (−B9), un
calcul dit (`sfa_calcule`) ; ``ecart_eurostat`` et ``ecart_millesime_dette`` y sont nuls
par construction. Sur les années où la t. 3.105 existe, ce calcul s'en écarte de
``ecart_millesime_dette`` (testé). Les créations et les défaillances n'y sont pas (une
autre méthode avant 2009, D-421) ; le chômage est celui de l'Insee (t. 302) avant 2009.

LES CHAMPS DES LOTS 2 À 4 (D-412). Ceux qu'une série publiée porte exactement sont
écrits, chacun avec sa source au registre : l'emploi intérieur total et salarié (t. 6.208
et 6.210), les chômeurs BIT (Eurostat, 15-74 ans ; l'enquête Emploi n'en compte aucun
au-delà), la population active (leur somme, la convention du lot 4), la rémunération
moyenne par salarié (D1 de la t. 1.105 sur l'emploi salarié, la définition du lot 4), le
solde des échanges (P6 − P7) et la contribution du solde extérieur à la croissance (la
formule du bloc `commerce`, sur la t. 1.101 et la t. 1.103). Ceux qu'aucune série ne
porte restent absents : le stock, les créations et les fermetures de sociétés, les
sorties induites, la productivité (lot 2), la FBCF des seules sociétés non financières
(la t. 1.101 les publie avec les EI), la demande mondiale, les prix relatifs, le solde
courant (lot 3). Les séries sans champ exact (créations d'entreprises, défaillances,
salaire brut moyen, taux de chômage, OAT, volumes) vont au groupe ``histoire``.
"""

from __future__ import annotations

import functools
import json
from typing import Any

from impots.dette import comptes
from impots.jumeau.champs import (
    APU_DEPENSES,
    APU_RECETTES,
    EMPLOIS_PUBLIES,
    IMPOTS_3217,
    REGISTRE,
)
from impots.jumeau.etat import Etat

PREMIERE, DERNIERE = 2010, 2025
#: La première année de l'histoire longue (D-446) : la dette commence fin 1995.
PREMIERE_LONGUE = 1996
PIB_REVENUS_FILE = "insee_cn2025_t1105_pib_trois_approches.xlsx"
PUBLIE = ("publie", "")
#: La moitié de la dernière décimale imprimée, en Md€.
DEMI_MILLIEME = 0.0005
#: Les totaux de la t. 1.101 sous lesquels se rangent ses secteurs.
TOTAUX_1101 = ("P3", "P51G", "P53", "P52", "P6", "P7")


class HistoriqueError(ValueError):
    """Une table publiée qui ne se lit pas comme le cadre le dit."""


def _cellule(rows: list[tuple[Any, ...]], i: int, colonne: int, quoi: str) -> float:
    valeur = rows[i][colonne]
    if valeur is None or isinstance(valeur, str):
        raise HistoriqueError(f"{quoi} : cellule « {valeur} », lue comme zéro elle passerait")
    return float(valeur)


@functools.lru_cache(maxsize=1)
def _t1101() -> dict[int, dict[str, float]]:
    """Les totaux et les secteurs de la t. 1.101, par année, en Md€."""
    rows = comptes._rows(comptes.PIB_FILE, "T_1101 en niveau")
    colonnes = comptes._year_columns(rows)
    places: dict[tuple[str, str | None], int] = {}
    parent = None
    for i, row in enumerate(rows):
        code = str(row[0]).strip() if row[0] is not None else None
        if code is None:
            continue
        if code in (*TOTAUX_1101, "B1GQ"):
            parent = code
            cle: tuple[str, str | None] = (code, None)
        elif code in ("P31", "P32", "TFU", "DINT", "DINT_S"):
            continue
        else:
            cle = (str(parent), code)
        if cle in places:
            raise HistoriqueError(f"t. 1.101 : « {cle} » deux fois")
        places[cle] = i
    voulus = [(code, None) for code in (*TOTAUX_1101, "B1GQ")]
    voulus += [(c, s) for _, _, c, s in EMPLOIS_PUBLIES if s is not None]
    manquants = [c for c in voulus if c not in places]
    if manquants:
        raise HistoriqueError(f"t. 1.101 : lignes absentes {manquants}")
    return {annee: {f"{c}|{s or ''}": _cellule(rows, places[(c, s)], j, f"1.101 {c} {s}")
                    for c, s in voulus} for annee, j in colonnes.items()}


@functools.lru_cache(maxsize=1)
def _t1105() -> dict[int, dict[str, float]]:
    """L'approche revenus de la t. 1.105 : B1GQ, D1, B2A3G, D2, D3 (imprimé négatif)."""
    rows = comptes._rows(PIB_REVENUS_FILE, "T_1105 en niveau")
    colonnes = comptes._year_columns(rows)
    debuts = [i for i, r in enumerate(rows) if r[0] == "B1GQ"
              and "approche revenus" in str(r[1])]
    if len(debuts) != 1:
        raise HistoriqueError(f"t. 1.105 : {len(debuts)} ligne(s) « approche revenus »")
    places = {"B1GQ": debuts[0]}
    for i in range(debuts[0] + 1, debuts[0] + 5):
        places[str(rows[i][0]).strip()] = i
    if set(places) != {"B1GQ", "D1", "B2A3G", "D2", "D3"}:
        raise HistoriqueError(f"t. 1.105 : approche revenus lue {sorted(places)}")
    return {annee: {c: _cellule(rows, i, j, f"1.105 {c}") for c, i in places.items()}
            for annee, j in colonnes.items()}


@functools.lru_cache(maxsize=1)
def _t3201() -> dict[int, dict[str, float]]:
    """Les lignes de la t. 3.201, par section, en Md€."""
    rows = comptes._rows(comptes.TOTALS_FILE, comptes.TOTALS_SHEET)
    colonnes = comptes._year_columns(rows)
    bornes = {}
    for marque in comptes.SECTIONS:
        trouves = [i for i, r in enumerate(rows) if comptes._label(r) == marque]
        if len(trouves) != 1:
            raise HistoriqueError(f"t. 3.201 : {len(trouves)} section(s) « {marque} »")
        bornes[marque] = trouves[0]
    sections = {"DEPENSES": range(bornes["DEPENSES"], bornes["RECETTES"]),
                "RECETTES": range(bornes["RECETTES"], bornes["SOLDES"]),
                "SOLDES": range(bornes["SOLDES"], len(rows))}
    voulus = [("RECETTES", nom, lib) for nom, _, _, lib in APU_RECETTES]
    voulus += [("DEPENSES", nom, lib) for nom, _, _, lib in APU_DEPENSES]
    voulus += [("DEPENSES", "d41p", "Intérêts (D41)"), ("RECETTES", "d41r", "Intérêts (D41)"),
               ("DEPENSES", "total_d", "Total des dépenses"),
               ("RECETTES", "total_r", "Total des recettes"),
               ("SOLDES", "b9", comptes.TOTALS_LABELS["net_lending"])]
    places = {}
    for section, nom, libelle in voulus:
        trouves = [i for i in sections[section] if comptes._label(rows[i]) == libelle]
        if len(trouves) != 1:
            raise HistoriqueError(f"t. 3.201 : {len(trouves)} ligne(s) « {libelle} » en "
                                  f"{section}, attendu 1 (libellé entier)")
        places[nom] = trouves[0]
    return {annee: {n: _cellule(rows, i, j, f"3.201 {n}") for n, i in places.items()}
            for annee, j in colonnes.items()}


@functools.lru_cache(maxsize=1)
def _dette() -> dict[int, float]:
    """La dette de fin d'année, Md€, de 1995 à 2025, unités vérifiées."""
    annees = list(range(PREMIERE_LONGUE - 1, DERNIERE + 1))
    comptes.check_units(annees)
    return {a: stock / 1e9 for a, (stock, _) in comptes.debt(annees).items()}


@functools.lru_cache(maxsize=1)
def _eurostat() -> dict[int, dict[str, float]]:
    """GD_CH, B9_T3, F_ASS, ORADJ, YA3 par année publiée, Md€."""
    from impots.population.ingest import require_sourced

    require_sourced(comptes.SFA_FILE)
    chemin = comptes.RAW / comptes.SFA_FILE
    if not chemin.exists():
        raise HistoriqueError(f"{comptes.SFA_FILE} est au manifeste mais absent")
    donnees = json.loads(chemin.read_text(encoding="utf-8"))
    postes = donnees["dimension"]["na_item"]["category"]["index"]
    temps = donnees["dimension"]["time"]["category"]["index"]
    valeurs = donnees.get("value", {})
    out: dict[int, dict[str, float]] = {}
    for annee, t in temps.items():
        lus = {}
        for poste in ("GD_CH", "B9_T3", "F_ASS", "ORADJ", "YA3"):
            brute = valeurs.get(str(postes[poste] * len(temps) + t))
            if brute is not None:
                lus[poste] = float(brute) / 1e3            # le fichier est en MILLIONS
        if len(lus) == 5:
            out[int(annee)] = lus
        elif lus:
            raise HistoriqueError(f"{comptes.SFA_FILE} {annee} : postes partiels {sorted(lus)}")
    return out


def _borne(valeur: float, termes: int, demi: float, quoi: str, annee: int) -> float:
    if abs(valeur) > termes * demi:
        raise HistoriqueError(
            f"{quoi} {annee} : {valeur:+.6f} Md€, au-delà de l'arrondi de {termes} termes "
            f"imprimés ({termes * demi:.6f}) : ce n'est pas un arrondi")
    return valeur


def _lire(nom: str, annee: int) -> dict[int, float]:
    """La série de `jumeau.series`, longue (D-446) pour une année d'avant 2010."""
    from impots.jumeau import series

    return series.lire(nom, longue=annee < series.PREMIERE)


def sfa_calcule(annee: int) -> dict[str, float]:
    """L'ajustement flux-stocks d'une année sans table de passage (D-446) : la variation
    du stock de dette de l'Insee moins le déficit de la t. 3.201, Md€ ; le déficit et la
    variation avec lui."""
    stocks, b9 = _dette(), _t3201()[annee]["b9"]
    variation = stocks[annee] - stocks[annee - 1]
    return {"sfa": variation + b9, "variation": variation, "deficit": -b9}


def etat_initial(annee: int) -> Etat:
    """L'état publié de `annee` : emplois, revenus, compte des APU, dette ; de 1996 à
    2009, l'histoire longue (D-446)."""
    if not PREMIERE_LONGUE <= annee <= DERNIERE:
        raise HistoriqueError(f"{annee} hors de {PREMIERE_LONGUE}–{DERNIERE}")
    etat = Etat(annee, 1, publie=True)

    def ecrire(nom: str, valeur: float) -> None:
        etat.ecrire(nom, PUBLIE, valeur)

    emplois = _t1101()[annee]
    pib = emplois["B1GQ|"]
    ecrire("pib", pib)
    for nom, _, code, secteur in EMPLOIS_PUBLIES:
        ecrire(nom, emplois[f"{code}|{secteur or ''}"])
    secteurs = {code: sum(emplois[f"{c}|{s}"] for _, _, c, s in EMPLOIS_PUBLIES
                          if c == code and s) for code in ("P3", "P51G")}
    ecrire("ventilation_emplois", sum(emplois[f"{c}|"] - secteurs[c] for c in secteurs))
    totaux = sum((-1.0 if c == "P7" else 1.0) * emplois[f"{c}|"] for c in TOTAUX_1101)
    ecrire("arrondi_emplois", _borne(pib - totaux, len(TOTAUX_1101) + 1, DEMI_MILLIEME,
                                     "t. 1.101, PIB moins ses totaux", annee))
    ecrire("emplois_non_ventiles", 0.0)

    revenus = _t1105()[annee]
    if revenus["B1GQ"] != pib:
        raise HistoriqueError(f"{annee} : PIB {revenus['B1GQ']} en 1.105, {pib} en 1.101")
    ecrire("remunerations", revenus["D1"])
    ecrire("ebe_revenu_mixte", revenus["B2A3G"])
    ecrire("impots_production", revenus["D2"])
    ecrire("subventions", -revenus["D3"])
    somme = revenus["D1"] + revenus["B2A3G"] + revenus["D2"] + revenus["D3"]
    ecrire("arrondi_revenus", _borne(pib - somme, 5, DEMI_MILLIEME,
                                     "t. 1.105, PIB moins ses revenus", annee))
    ecrire("revenus_non_ventiles", 0.0)

    apu = _t3201()[annee]
    for nom, *_ in (*APU_RECETTES, *APU_DEPENSES):
        ecrire(nom, apu[nom])
    ecrire("solde_induit", 0.0)
    ecrire("mesures_non_ventilees", 0.0)
    ecrire("apu_recettes", apu["total_r"] - apu["d41r"])
    ecrire("apu_depenses_primaires", apu["total_d"] - apu["d41p"])
    ecrire("interets_nets", apu["d41p"] - apu["d41r"])
    ecrire("b9", apu["b9"])
    ecrire("solde_primaire", apu["b9"] + apu["d41p"] - apu["d41r"])

    stocks = _dette()
    ecrire("dette_ouverture", stocks[annee - 1])
    ecrire("dette", stocks[annee])
    eurostat = _eurostat().get(annee)
    if eurostat is not None:
        sfa = eurostat["F_ASS"] + eurostat["ORADJ"] + eurostat["YA3"]
        variation, deficit = eurostat["GD_CH"], eurostat["B9_T3"]
    elif annee < PREMIERE:
        calcul = sfa_calcule(annee)
        sfa, variation, deficit = calcul["sfa"], calcul["variation"], calcul["deficit"]
    else:
        from impots.jumeau import series

        sfa = series.lire("sfa_insee")[annee]
        variation = series.lire("variation_dette")[annee]
        deficit = series.lire("deficit_maastricht")[annee]
    ecrire("sfa", sfa)
    ecrire("ecart_eurostat", variation - deficit - sfa)
    ecrire("ecart_millesime_dette", (stocks[annee] - stocks[annee - 1])
           - variation + (apu["b9"] + deficit))
    etat.fixer("ratio_dette", etat["dette"] / etat["pib"])
    etat.fixer("taux_implicite", etat["interets_nets"] / etat["dette_ouverture"])
    _prix_et_impots(etat, annee)
    _series_des_lots(etat, annee)
    return etat


def _prix_et_impots(etat: Etat, annee: int) -> None:
    """Les prix des emplois, le volume du PIB et les principaux impôts de l'année (D-410)."""
    for nom, _, _, _ in EMPLOIS_PUBLIES:
        if nom == "var_stocks":
            continue                       # aucun indice publié : le prix est absent
        indice = _lire(f"indice_prix_{nom}", annee)
        etat.fixer(f"prix_{nom}", indice[annee] / indice[annee - 1])
    volume = _lire("volume_pib", annee)
    etat.fixer("croissance_volume_pib", volume[annee] / volume[annee - 1] - 1.0)
    for nom, _ in IMPOTS_3217:
        valeurs = _lire(f"impot_{nom}", annee)
        if annee in valeurs:
            etat.ecrire(f"impot_{nom}", PUBLIE, valeurs[annee])


#: Les champs du groupe ``histoire`` lus tels quels dans une série de `jumeau.series`,
#: {champ : série}. Les volumes sont `volume_<emploi>`, du même nom des deux côtés.
SERIES_HISTOIRE = {"salaires_bruts": "salaires_bruts",
                   "salaire_brut_moyen": "salaire_moyen", "taux_chomage": "taux_chomage",
                   "creations_entreprises": "creations_entreprises",
                   "creations_micro": "creations_micro",
                   "creations_classiques": "creations_classiques",
                   "creations_ei_hors_micro": "creations_ei_hors_micro",
                   "defaillances": "defaillances", "taux_oat_10ans": "taux_oat_10ans"}


def _poser(etat: Etat, nom: str, valeur: float) -> None:
    if REGISTRE[nom].additif:
        etat.ecrire(nom, PUBLIE, valeur)
    else:
        etat.fixer(nom, valeur)


def _series_des_lots(etat: Etat, annee: int) -> None:
    """Les champs des lots 2 à 4 qu'une série publiée porte exactement, et le groupe
    ``histoire`` (D-412). Ce que le module ne dit pas ici reste absent."""
    from impots.jumeau import series

    emploi_total = _lire("emploi_total", annee)[annee]
    emploi_salarie = _lire("emploi_salarie", annee)[annee]
    chomeurs = _lire("chomeurs", annee)[annee]
    _poser(etat, "emploi_total", emploi_total)
    _poser(etat, "emploi_salarie", emploi_salarie)
    _poser(etat, "chomage", chomeurs)
    _poser(etat, "population_active", emploi_total + chomeurs)
    # D1 en Md€, l'emploi en milliers : des euros par salarié, comme le lot 4.
    _poser(etat, "salaire_moyen", float(etat["remunerations"][0]) * 1e6 / emploi_salarie)

    x, m = float(etat["exportations"][0]), float(etat["importations"][0])
    _poser(etat, "solde_exterieur", x - m)
    avant = _t1101()[annee - 1]
    volume = ((x / float(etat["prix_exportations"][0]) - avant["P6|"])
              - (m / float(etat["prix_importations"][0]) - avant["P7|"]))
    _poser(etat, "contribution_solde_exterieur", volume / avant["B1GQ|"])

    _poser(etat, "volume_pib", _lire("volume_pib", annee)[annee])
    for nom, _, _, _ in EMPLOIS_PUBLIES:
        if nom != "var_stocks":
            _poser(etat, f"volume_{nom}", _lire(f"volume_{nom}", annee)[annee])
    for champ, serie in SERIES_HISTOIRE.items():
        if annee < PREMIERE and series.SERIES[serie].longue is None:
            continue                       # les créations, les défaillances (D-446)
        _poser(etat, champ, _lire(serie, annee)[annee])
