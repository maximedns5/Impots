"""L'état publié d'une année, de 2010 à 2025 (CADRE.md §6) : `etat_initial(annee)`.

Lu dans les tables manifestées, chaque fichier ouvert une fois par processus :

* Insee t. 1.101 (emplois du PIB, par secteur) et t. 1.105 (l'approche revenus) ;
* Insee t. 3.201 (le compte consolidé des APU, ligne à ligne, et ses totaux) ;
* la dette de Maastricht de fin d'année de l'Insee (`dette.comptes.debt`, unités
  vérifiées par `check_units`) ;
* l'ajustement flux-stocks d'Eurostat (gov_10dd_edpt3), quand l'année y est publiée.

CE QUE LES COMPTES PUBLIÉS NE BOUCLENT PAS, ET CE QUE LE CADRE EN FAIT (D-405). Chaque
écart est un champ nommé, LU dans les publications, jamais un résidu silencieux :

* les tables de l'Insee sont imprimées au millième de milliard : la somme des totaux
  publiés s'écarte du PIB publié d'un ou deux millièmes (``arrondi_emplois``,
  ``arrondi_revenus``). Un écart au-delà de l'arrondi imprimé est refusé ;
* en 2023 et 2024, les secteurs de P3 et de P51G de la t. 1.101 ne somment pas à leurs
  totaux (de 0,12 et 0,09 Md€ en tout) : ``ventilation_emplois``, le total publié moins la
  somme publiée de ses secteurs ;
* l'ajustement d'Eurostat est F_ASS + ORADJ + YA3 : ORADJ, le total des ajustements,
  contient déjà K61 et KX, et la somme des cinq de `comptes.SFA_COMPOSANTES` les compte
  deux fois ; ``ecart_eurostat`` est GD_CH − B9_T3 moins cet ajustement, l'écart interne
  de la table : de −0,1 à +0,3 million, il dépasse en 2023 l'arrondi de ses cinq postes
  imprimés au dixième de million, parce que ces postes sont eux-mêmes des totaux de
  postes arrondis ; il n'est donc borné par aucun arrondi, il est lu et dit (D-405) ;
  ``ecart_millesime_dette`` est l'écart entre l'Insee et Eurostat sur la
  variation du stock et sur B9 (0,35 Md€ en 2025, où le stock de l'Insee est plus récent).

Ce qui manque reste absent : Eurostat ne publie l'ajustement que de 2021 à 2025 dans le
fichier manifesté, et l'identité de la dette refuse, en nommant « sfa », de 2010 à 2020 ;
le lot 5 apporte la série. Les déflateurs (t. 1.103) et le chaînage du volume sur
l'histoire sont aussi au lot 5.
"""

from __future__ import annotations

import functools
import json
from typing import Any

from impots.dette import comptes
from impots.jumeau.champs import APU_DEPENSES, APU_RECETTES, EMPLOIS_PUBLIES
from impots.jumeau.etat import Etat

PREMIERE, DERNIERE = 2010, 2025
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
    """La dette de fin d'année, Md€, de 2009 à 2025, unités vérifiées."""
    annees = list(range(PREMIERE - 1, DERNIERE + 1))
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


def etat_initial(annee: int) -> Etat:
    """L'état publié de `annee` : emplois, revenus, compte des APU, dette."""
    if not PREMIERE <= annee <= DERNIERE:
        raise HistoriqueError(f"{annee} hors de {PREMIERE}–{DERNIERE}")
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
        ecrire("sfa", sfa)
        ecrire("ecart_eurostat", eurostat["GD_CH"] - eurostat["B9_T3"] - sfa)
        ecrire("ecart_millesime_dette", (stocks[annee] - stocks[annee - 1])
               - eurostat["GD_CH"] + (apu["b9"] + eurostat["B9_T3"]))
    etat.fixer("ratio_dette", etat["dette"] / etat["pib"])
    etat.fixer("taux_implicite", etat["interets_nets"] / etat["dette_ouverture"])
    return etat
