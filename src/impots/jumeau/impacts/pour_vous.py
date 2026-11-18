"""Pour vous : ce qu'une mesure change pour un ménage comme le vôtre (but 29, volet `cas`,
D-630 à D-634).

Le lecteur dit sa situation (seul ou en couple, ses enfants, son activité, son logement,
son âge) ; la dimension rend, pour chaque cas type de la grille (`impots.cas_types`) et
chaque année :

    le statique      s_c,t = Σ_m k_m Δ_c,m / RD_c       la mesure elle-même, impôts,
                     prestations, TVA et accises compris : le ménage passé par OpenFisca au
                     droit de 2026 avant et après le scénario (`jumeau/parametres/
                     cas_types.json`), en part de son revenu disponible, chaque année où la
                     mesure s'applique ; k_m l'intensité d'une mesure composée (D-605) ; À
                     DÉFAUT (l'indépendant, une loi simple, une mesure hors du tableau), le
                     gain par ménage du décile de sa cellule (`Mesure.menages`, D-409)
    l'économie       ΔRD^nom = s RD + ŵ_t SN_c + p̂c_t (P_c + B_c)    ŵ le salaire moyen par
                     tête du jumeau (variante sur référence) sur le salaire net du cas type ;
                     les pensions P et les prestations B indexées sur le prix de la
                     consommation (D-414)
    le revenu réel   Δln y_t = ln(1 + ΔRD^nom / RD_c) − ln(1 + p̂c_t)
    le chômage       Δr_t = r_c (U_v / U_r − 1)          r_c le taux de chômage de la
                     cellule du cas type (chômeurs sur actifs), un actif seulement
    la satisfaction  ΔS_t = β Δln y − δ Δr − ε Δu − φ π̄   les coefficients du moral (D-595)
    la santé         ΔEV = 12 s g Δln y (mois, si l'écart durait) ;
                     Δ(bonne santé) = −c (e − u) Δr (points de probabilité) (D-620)
    l'âge de départ  Δa : l'écart d'âge légal du programme (`sante.yaml`, D-622) l'année
                     où la génération du cas type atteint l'âge légal de la référence ;
                     l'âge effectif τ Δa

LE STATUT : « illustratif ». Le statique est exact pour le cas type (OpenFisca) ; le reste
est l'économie du jumeau, et la satisfaction et la santé ne sont pas jugées (D-596, D-621).
Aucune personne n'est décrite : des cas types seulement.

Ce module tourne dans le navigateur (D-415) : numpy et la bibliothèque standard.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from impots.jumeau.impacts import Dimension, Indicateur, Source, inscrire
from impots.jumeau.impacts import moral as _moral
from impots.jumeau.impacts import sante as _sante

TABLEAU = Path(__file__).resolve().parents[1] / "parametres" / "cas_types.json"
CLE = "pour_vous"
DEFAUT = "seul-0-smic-locataire-30_49"
#: Les cas types que la fiche générique montre en barres ; la section « Pour vous » de la
#: page lit tous les cas dans `notes["cas"]`.
VITRINE = {
    "seul-0-smic-locataire-30_49": "Seul, au Smic, locataire",
    "seul-2-smic-locataire-30_49": "Parent seul, 2 enfants, Smic, locataire",
    "couple-2-median-proprietaire-30_49": "Couple, 2 enfants, salaires médians, propriétaire",
    "seul-0-eleve-proprietaire-30_49": "Seul, salaire élevé, propriétaire",
    "seul-0-chomeur-locataire-30_49": "Seul, au chômage, locataire",
    "couple-0-retraite-proprietaire-62_plus": "Couple de retraités, propriétaire",
    "seul-0-independant-locataire-30_49": "Seul, indépendant, locataire (la cellule)",
}
BORNES = ("centre", "bas", "haut")


class PourVousError(ValueError):
    """Une entrée que la dimension refuse."""


@lru_cache(maxsize=1)
def charger(chemin: Path = TABLEAU) -> dict[str, Any]:
    return json.loads(chemin.read_text(encoding="utf-8"))


def choisir(foyer: str, enfants: int, activite: str, logement: str, age: str) -> str:
    """La clé du cas type pour ce que dit le lecteur (la règle de `cas_types.choisir`)."""
    if activite == "retraite":
        return f"{foyer}-0-retraite-{logement}-62_plus"
    return f"{foyer}-{int(enfants)}-{activite}-{logement}-{'50_61' if age == '62_plus' else age}"


# --------------------------------------------------------------------------- entrées
def _champ(etats: Sequence[Any], champ: str, tirage: int = 0) -> np.ndarray | None:
    if not all(e.present(champ) for e in etats):
        return None
    return np.array([float(np.asarray(e[champ]).ravel()[tirage]) for e in etats])


def economie(variante: Any, reference: Any, tirage: int = 0) -> dict[str, Any]:
    """Ce que la dimension lit du jumeau, variante contre référence, par année : ŵ, p̂c,
    U_v / U_r − 1, Δu (points), π̄ (points, moyenne sur trois ans) ; zéro et dit quand le
    mode ne les porte pas."""
    annees, var, ref = _moral._etats(variante, reference)
    n = len(annees)
    lus: list[str] = []
    wv, wr = _champ(var, "salaire_moyen", tirage), _champ(ref, "salaire_moyen", tirage)
    w = np.zeros(n)
    if wv is not None and wr is not None:
        # Sans la part que le bloc `travail` écrit (la hausse mécanique des bas salaires
        # d'une hausse du Smic, D-478) : le statique du cas type la porte déjà.
        wv = wv - np.array([_origine(e, "salaire_moyen", "travail", tirage) for e in var])
        w = wv / wr - 1.0
        lus.append("salaire_moyen")
    pv = _champ(var, "ecart_prix_consommation", tirage)
    pr = _champ(ref, "ecart_prix_consommation", tirage)
    dp = np.zeros(n)
    if pv is not None and pr is not None:
        dp = pv - pr
        lus.append("ecart_prix_consommation")
    uv, ur = _champ(var, "chomage", tirage), _champ(ref, "chomage", tirage)
    av, ar = _champ(var, "population_active", tirage), _champ(ref, "population_active",
                                                            tirage)
    ru, du = np.zeros(n), np.zeros(n)
    if uv is not None and ur is not None and av is not None and ar is not None:
        ru, du = uv / ur - 1.0, 100.0 * (uv / av - ur / ar)
        lus.append("chomage")
    infl = _moral.moyenne(100.0 * np.diff(np.concatenate([[0.0], dp])), 3)
    return {"annees": tuple(int(a) for a in annees), "w": w, "dp": dp, "ru": ru, "du": du,
            "inflation": infl, "lus": lus}


def _origine(etat: Any, champ: str, origine: str, tirage: int) -> float:
    """La somme des contributions d'une origine à un champ additif (zéro sans elles)."""
    try:
        parts = etat.de(champ)
    except Exception:  # un état sans contributions (publié) : rien à retrancher
        return 0.0
    return float(sum(float(np.asarray(v).ravel()[tirage]) for (o, _), v in parts.items()
                     if o == origine))


def _base(ident: str, mesures: Mapping[str, Any]) -> str | None:
    """La clé du tableau d'une mesure (« …_2 » : la deuxième fois qu'on la compose)."""
    if ident in mesures:
        return ident
    b = re.sub(r"_\d+$", "", ident)
    return b if b in mesures else None


def statique(cas: Mapping[str, Any], tab: Mapping[str, Any], mesures: Sequence[Any],
             composition: Sequence[Mapping[str, Any]] | None, annees: Sequence[int],
             cellules: Any) -> tuple[np.ndarray, list[dict[str, Any]]]:
    """Le gain statique du cas type par année (euros de 2026, gain positif), et, mesure par
    mesure, d'où il vient (« openfisca » ou « cellule »)."""
    from impots.jumeau.cellules import TYPES

    out = np.zeros(len(annees))
    origines = []
    menages_dec = np.asarray(cellules["menages"], float).reshape(-1, len(TYPES)).sum(axis=1)
    for i, m in enumerate(mesures):
        el = (composition[i] if composition and i < len(composition) else {}) or {}
        k = float(el.get("echelle", 1.0)) if el.get("candidat") else 1.0
        cle = _base(getattr(m, "identifiant", ""), tab["mesures"])
        actives = {int(a) for a in getattr(m, "annees", ())}
        ent = tab["mesures"].get(cle) if cle else None
        # Un cas type absent des écarts d'une mesure chiffrée n'y change rien (compact).
        ec = (dict((ent.get("ecarts") or {}).get(cas["cle"]) or {})
              if ent is not None and "ecarts" in ent and cas.get("reference") else None)
        if ec is not None:
            gain = k * (ec.get("revenu_disponible", 0.0) - ec.get("taxes_consommation", 0.0))
            for j, a in enumerate(annees):
                if a in actives:
                    out[j] += gain
            origines.append({"mesure": m.identifiant, "origine": "openfisca", "echelle": k,
                             "ecarts": {x: k * v for x, v in ec.items()}})
            continue
        if ent is not None and ent.get("vide"):
            origines.append({"mesure": m.identifiant, "origine": "aucun ménage touché"})
            continue
        men = getattr(m, "menages", None) or {}
        d = int(cas["decile"]) - 1
        lu = False
        for j, a in enumerate(annees):
            x = men.get(a, men.get(str(a)))
            if x and x.get("deciles") is not None:
                out[j] += float(x["deciles"][d]) * 1e9 / menages_dec[d]
                lu = True
        origines.append({"mesure": m.identifiant,
                         "origine": "cellule" if lu else "absent",
                         "raison": "le cas type n'est pas dans le tableau d'OpenFisca"
                         if ent is not None or cle else "la mesure n'est pas dans le "
                         "tableau d'OpenFisca"})
    return out, origines


def reference_cas(cas: Mapping[str, Any], cellules: Any, tab: Mapping[str, Any]
                  ) -> dict[str, float]:
    """Le revenu disponible de référence du cas type et ses parts (euros de 2026) ; pour un
    cas sans OpenFisca (l'indépendant), le revenu disponible moyen d'un ménage de sa
    cellule, porté de 2024 à 2026 par le Smic."""
    from impots.jumeau.cellules import indice

    if cas.get("reference"):
        return dict(cas["reference"])
    n = tab["niveaux"]
    k = indice(int(cas["decile"]), cas["type"])
    porte = float(n["smic_annuel_brut_2026"]) / float(n["smic_annuel_brut_2024"])
    rd = float(np.asarray(cellules["revenu_disponible"])[k]) / float(
        np.asarray(cellules["menages"])[k]) * porte
    return {"revenu_disponible": rd, "salaire_net": 0.0, "pensions_chomage": 0.0,
            "prestations": 0.0, "impot_revenu": 0.0, "prelevements_travail": 0.0,
            "taxes_consommation": 0.0}


def taux_chomage_cellule(cas: Mapping[str, Any], cellules: Any) -> float:
    from impots.jumeau.cellules import indice

    k = indice(int(cas["decile"]), cas["type"])
    u = float(np.asarray(cellules["chomeurs"])[k])
    e = float(np.asarray(cellules["en_emploi"])[k])
    return u / (u + e) if u + e > 0 else 0.0


def generation_atteint(p: Mapping[str, Any], naissance: int) -> int:
    """L'année où la génération atteint l'âge légal de la référence."""
    for a in range(2026, 2101):
        if a - naissance >= float(_sante._chemin(p["retraite"]["reference"]["ages"], [a])[0]):
            return a
    return 2100


def calcul_cas(cas: Mapping[str, Any], tab: Mapping[str, Any], eco: Mapping[str, Any],
               mesures: Sequence[Any], composition: Sequence[Mapping[str, Any]] | None,
               cellules: Any, pm: Mapping[str, Any], ps: Mapping[str, Any],
               programme: str | None) -> dict[str, Any]:
    """Toutes les séries d'un cas type."""
    annees = eco["annees"]
    ref = reference_cas(cas, cellules, tab)
    rd = float(ref["revenu_disponible"])
    s, origines = statique(cas, tab, mesures, composition, annees, cellules)
    indexees = (float(ref["prestations"]) + (float(ref["pensions_chomage"])
                                             if cas["activite"] == "retraite" else 0.0))
    nominal = s + eco["w"] * float(ref["salaire_net"]) + eco["dp"] * indexees
    dln = np.log1p(nominal / rd) - np.log1p(eco["dp"])
    reel = rd * np.expm1(dln)
    actif = cas["activite"] in ("smic", "median", "eleve", "independant")
    r0 = taux_chomage_cellule(cas, cellules) if actif else 0.0
    drisque = r0 * eco["ru"]
    # La satisfaction : chaque canal à chaque borne, l'enveloppe des bornes de même sens.
    canaux = {}
    for b in BORNES:
        k = _moral.coefficients(pm, b)
        canaux[b] = np.array([k.beta * dln, -k.delta * drisque, -k.epsilon * eco["du"],
                              -k.phi * eco["inflation"]])
    pile = np.stack([canaux[b] for b in BORNES])
    sat = canaux["centre"].sum(axis=0)
    sat_bas, sat_haut = pile.min(axis=0).sum(axis=0), pile.max(axis=0).sum(axis=0)
    g = _sante.gradient(ps)
    cs = ps["chomage_sante"]
    ecart_sante = float(cs["emploi"]) - float(cs["chomeurs"])
    ev = {b: 12.0 * _sante.coefficients(ps, b).s * g * dln for b in BORNES}
    bs = {b: -_sante.coefficients(ps, b).c * ecart_sante * drisque for b in BORNES}
    out: dict[str, Any] = {
        "revenu_disponible_reference": rd,
        "revenu_reel": reel, "revenu_reel_pct": 100.0 * np.expm1(dln), "statique": s,
        "risque_chomage_base": 100.0 * r0, "risque_chomage": 100.0 * drisque,
        "satisfaction": sat, "satisfaction_bas": sat_bas, "satisfaction_haut": sat_haut,
        "esperance_vie": ev["centre"], "esperance_vie_bas": np.minimum(ev["bas"], ev["haut"]),
        "esperance_vie_haut": np.maximum(ev["bas"], ev["haut"]),
        "bonne_sante": bs["centre"], "origines": origines,
    }
    # L'âge de départ : un actif, pour un programme entier qui le règle (D-622).
    out["depart"] = None
    if cas["activite"] != "retraite":
        naissance = 2026 - int(cas["age_ans"])
        a = generation_atteint(ps, naissance)
        da = float(_sante.ecart_age_legal(ps, programme, [a])[0]) if programme else 0.0
        taus = [_sante.coefficients(ps, b).tau for b in BORNES]
        lam = _sante.coefficients(ps, "centre").lam
        out["depart"] = {
            "annee": a, "age_legal_reference": round(a - naissance + 0.0, 2),
            "ecart_age_legal": da, "programme": programme,
            "ecart_age_effectif": taus[0] * da,
            "ecart_age_effectif_bande": [min(t * da for t in taus), max(t * da for t in taus)],
            "retraite_sans_limitation_ans": -taus[0] * da * lam,
        }
    return out


# --------------------------------------------------------------------------- la dimension
def sources(tab: Mapping[str, Any], pm: Mapping[str, Any], ps: Mapping[str, Any]
            ) -> tuple[Source, ...]:
    n = tab["niveaux"]
    return (
        Source("OpenFisca France, le moteur des ménages du projet (`engine.compute`)",
               f"`impots.cas_types`, droit de {tab['annee']}, commit {tab['commit']}",
               "chaque cas type avant et après le scénario de la mesure, toutes les lignes "
               "du registre (impôts, cotisations, prestations, revenu disponible)"),
        Source(n["source"], "salariés, pensions, allocations, loyers",
               f"Smic {n['smic_annuel_brut_2026']:,.0f} € bruts par an en 2026 ; médiane "
               f"{n['salaire_median_brut_2024']:,} € et neuvième décile "
               f"{n['salaire_d9_brut_2024']:,} € bruts (2024, portés par le Smic) ; pension "
               f"médiane {n['pension_mediane_2024']:,} € ; allocation chômage médiane "
               f"{n['chomage_median_2024']:,} € ; loyer médian par taille "
               f"{n['loyer_median_par_taille_2024']}"),
        Source("Insee, enquête Budget de famille 2017, tableau TF106 (`consommation`)",
               "la dépense du décile de niveau de vie, au prorata des unités de "
               "consommation", "la TVA et les accises du cas type, à volumes constants"),
        *(_moral.sources(pm)[:5]), *(_sante.sources(ps)[:1]), _sante.sources(ps)[1],
        _sante.sources(ps)[3], _sante.sources(ps)[5],
    )


LIMITES = (
    "Des cas types, pas des personnes : un ménage de la grille, dont les revenus sont des "
    "médianes de la population ; votre situation précise peut en être loin (un loyer, des "
    "heures, un patrimoine, des revenus du capital qu'il n'a pas).",
    "Le statique (la mesure elle-même) est exact pour le cas type : OpenFisca au droit de "
    "2026, avant et après la mesure, impôts, cotisations, prestations, TVA et accises. Il "
    "est tenu en part du revenu chaque année où la mesure s'applique : la croissance des "
    "revenus et les seuils des années suivantes ne le changent pas.",
    "L'indépendant, une loi simple ou une mesure hors du tableau prennent le gain moyen par "
    "ménage du décile de leur cellule (décile de niveau de vie × type de ménage) : une "
    "approximation, dite mesure par mesure.",
    "Une proposition composée somme les statiques de ses mesures, chacune fois son "
    "intensité, sans leurs interactions (D-605).",
    "Après la mesure, l'économie du jumeau : le salaire moyen par tête (cotisations des "
    "employeurs comprises, D-606) sur votre salaire net, l'indexation des pensions et des "
    "prestations sur les prix, et les prix de la consommation. Le mode réduit ne les porte "
    "pas : le statique seul.",
    "Le risque de chômage est le taux de chômage de votre cellule, qui bouge comme le "
    "nombre de chômeurs du jumeau ; il ne dit rien de votre emploi à vous.",
    "La satisfaction et la santé reprennent les coefficients des dimensions du moral "
    "(D-595) et de la santé (D-620), non jugés ; l'espérance de vie est celle qu'on aurait "
    "si l'écart de revenu durait toute la vie, avec la part causale choisie (1/12).",
    "L'âge de départ n'est lu que pour un programme entier qui le règle (D-622) ; une "
    "mesure seule ou une proposition composée ne le porte pas.",
)


def _r(x: np.ndarray, d: int) -> list[float]:
    return [round(float(v), d) for v in np.asarray(x).ravel()]


@inscrire(CLE)
def pour_vous(variante: Any, reference: Any, depart: Any, cellules: Any, *,
              mesures: Sequence[Any] = (), composition: Sequence[Mapping[str, Any]] | None
              = None, programme: str | None = None, illustratives: Mapping[str, str] |
              None = None, tableau: Mapping[str, Any] | None = None,
              cle_statique: str | None = None, **_: Any) -> Dimension:
    if cellules is None:
        raise PourVousError("la dimension lit les cellules de ménages")
    tab = tableau if tableau is not None else charger()
    pm, ps = _moral.charger(), _sante.charger()
    eco = economie(variante, reference)
    annees = eco["annees"]
    if cle_statique:
        # Un programme calculé par ses mesures seules (D-502) : son statique est celui du
        # programme entier, chiffré d'un coup (les interactions statiques comprises).
        mesures, composition = [_ensemble(cle_statique, mesures)], None
    res = {}
    for k, c in tab["cas"].items():
        res[k] = calcul_cas({**c, "cle": k}, tab, eco, list(mesures), composition,
                            cellules, pm, ps, programme)
    d = res[DEFAUT]
    vit = {lib: k for k, lib in VITRINE.items() if k in res}
    ind = (
        Indicateur("revenu_reel", "Le revenu disponible réel du ménage (seul, au Smic, "
                   "locataire, par défaut)", "€ par an", d["revenu_reel"],
                   par_groupe={lib: res[k]["revenu_reel"] for lib, k in vit.items()}),
        Indicateur("revenu_reel_pct", "Le revenu disponible réel, en part", "%",
                   d["revenu_reel_pct"],
                   par_groupe={lib: res[k]["revenu_reel_pct"] for lib, k in vit.items()}),
        Indicateur("statique", "Dont la mesure elle-même (impôts, prestations, TVA), avant "
                   "l'économie", "€ par an", d["statique"],
                   par_groupe={lib: res[k]["statique"] for lib, k in vit.items()}),
        Indicateur("risque_chomage", "Le risque d'être au chômage (un actif)",
                   "points de pourcentage", d["risque_chomage"], sens=-1,
                   par_groupe={lib: res[k]["risque_chomage"] for lib, k in vit.items()}),
        Indicateur("satisfaction", "La satisfaction dans la vie d'un adulte du ménage",
                   "points (0 à 10)", d["satisfaction"], bas=d["satisfaction_bas"],
                   haut=d["satisfaction_haut"],
                   par_groupe={lib: res[k]["satisfaction"] for lib, k in vit.items()}),
        Indicateur("esperance_vie", "L'espérance de vie, si l'écart de revenu durait",
                   "mois", d["esperance_vie"], bas=d["esperance_vie_bas"],
                   haut=d["esperance_vie_haut"],
                   par_groupe={lib: res[k]["esperance_vie"] for lib, k in vit.items()}),
    )
    cas_json = {}
    for k, r in res.items():
        # Compact (la page porte tous les cas de chaque programme précalculé) : le % se
        # relit du revenu réel (100 réel / rd), les bandes à l'horizon seulement.
        cas_json[k] = {
            "rd": round(r["revenu_disponible_reference"]),
            "reel": _r(r["revenu_reel"], 0), "statique": _r(r["statique"], 0),
            "risque0": round(r["risque_chomage_base"], 2), "risque": _r(r["risque_chomage"], 3),
            "sat": _r(r["satisfaction"], 4), "ev": _r(r["esperance_vie"], 3),
            "sat_bande": [round(float(r["satisfaction_bas"][-1]), 4),
                          round(float(r["satisfaction_haut"][-1]), 4)],
            "ev_bande": [round(float(r["esperance_vie_bas"][-1]), 3),
                         round(float(r["esperance_vie_haut"][-1]), 3)],
            "bonne_sante": round(float(r["bonne_sante"][-1]), 4),
            "depart": r["depart"], "origines": _compte(r["origines"]),
            "lignes": _lignes(r["origines"]),
        }
    exact = all(o["origine"] in ("openfisca", "aucun ménage touché")
                for o in res[DEFAUT]["origines"])
    limites = list(LIMITES)
    if illustratives:
        limites += [f"« {i} » : {x}." for i, x in illustratives.items()]
    if "salaire_moyen" not in eco["lus"]:
        limites.append("Ce calcul ne porte ni les salaires ni les prix du jumeau (le mode "
                       "réduit) : le revenu réel est le statique seul.")
    notes = {
        "cas": cas_json, "defaut": DEFAUT, "grille": tab["grille"],
        "tableau": {"commit": tab["commit"], "annee": tab["annee"],
                    "commande": tab["commande"]},
        "economie": {"lus": eco["lus"], "salaire_moyen_pct": _r(100 * eco["w"], 4),
                     "prix_consommation_pct": _r(100 * eco["dp"], 4),
                     "chomeurs_pct": _r(100 * eco["ru"], 4),
                     "taux_chomage_points": _r(eco["du"], 4)},
        "exact_par_defaut": exact, "decisions": "D-630 à D-634",
    }
    return Dimension(
        cle=CLE, titre="Pour vous",
        question=("Pour un ménage comme le vôtre : combien de revenu en plus ou en moins, "
                  "quels impôts et prestations, quel risque de chômage, et ce que cela "
                  "fait à la satisfaction et à la santé ?"),
        annees=annees, indicateurs=ind, statut="illustratif",
        sources=sources(tab, pm, ps), limites=tuple(limites), notes=notes)


def _ensemble(ident: str, mesures: Sequence[Any]) -> Any:
    """Une mesure qui porte `ident`, les années de toutes et la somme de leurs chocs par
    décile (pour la cellule)."""
    from types import SimpleNamespace

    annees = sorted({int(a) for m in mesures for a in getattr(m, "annees", ())})
    menages: dict[int, dict[str, Any]] = {}
    for m in mesures:
        for a, x in (getattr(m, "menages", None) or {}).items():
            if x and x.get("deciles") is not None:
                d = menages.setdefault(int(a), {"deciles": np.zeros(10)})
                d["deciles"] = d["deciles"] + np.asarray(x["deciles"], float)
    return SimpleNamespace(identifiant=ident, annees=tuple(annees), menages=menages)


def _compte(origines: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for o in origines:
        out[o["origine"]] = out.get(o["origine"], 0) + 1
    return out


def _lignes(origines: Sequence[Mapping[str, Any]]) -> dict[str, float] | None:
    """Les lignes du statique (impôt, prélèvements, prestations, TVA), en euros de 2026,
    sommées sur les mesures chiffrées par OpenFisca ; None s'il n'y en a aucune."""
    tot: dict[str, float] = {}
    for o in origines:
        for x, v in (o.get("ecarts") or {}).items():
            tot[x] = tot.get(x, 0.0) + float(v)
    return {x: round(v, 2) for x, v in tot.items()} or None
