"""La dimension « territoires » (but 29, volet `territoires`, D-645 à D-648) : où tombe le
gain d'une mesure, par région et par type de territoire.

Les cellules du jumeau (décile × type de ménage) n'ont pas de territoire. La table de
passage commitée (`parametres/territoires.json`, `jumeau.table_territoires`, D-645) dit
comment les ménages, les personnes et le revenu disponible de chaque cellule se
répartissent entre la métropole et les quatre départements d'outre-mer de l'enquête, et
entre l'agglomération parisienne, les grandes agglomérations, les villes moyennes et
petites, le rural et l'outre-mer. Le gain par ménage d'une cellule est supposé le même
partout : le gain d'un territoire est la moyenne des gains des cellules, pondérée par ses
ménages dans chacune.

Ce module tourne dans le navigateur (D-415) : numpy seulement ; la table est un JSON lu
une fois. Il porte aussi les deux lectures de la table que le contrôle de D-646 fait (un
quantile du niveau de vie d'un territoire, une part sous un seuil), sur la table seule.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

from impots.jumeau.impacts import Dimension, Indicateur, Source, inscrire
from impots.jumeau.impacts._commun import QUANTILES, niveaux, statut

CLE = "territoires"
TABLE = Path(__file__).resolve().parents[1] / "parametres" / "territoires.json"
#: Le seuil d'indifférence des gagnants (`gagnants.SEUIL`, 10 € par ménage et par an),
#: écrit ici pour ne pas charger les blocs quand le mode réduit n'en a pas besoin ; un
#: test le tient égal.
SEUIL_GAGNANT = 10.0

SOURCES = (
    Source("Insee, enquête Emploi 2024, fichier détail (`FD_EEC_2024`)",
           "STCOMM2020 (statut de la commune dans l'unité urbaine 2020), METRODOM",
           "le rural (hors unité urbaine) et l'outre-mer, observés, ménage par ménage"),
    Source("Insee, recensement 2023 (base_cc_logement_2023) ; openfisca-france, zonage APL",
           "`margins.APL_ZONE_BY_STCOMM`, `margins.DOM_HOUSEHOLDS_BY_DEPARTEMENT`",
           "la zone APL et le département d'outre-mer, tirés sur les résidences "
           "principales de même statut de commune et d'occupation"),
    Source("Une passe de référence sur toute la population de D-553 (droit de 2026)",
           "`parametres/territoires.json`, son empreinte dans `meta` (D-645)",
           "le décile de niveau de vie et le revenu disponible de chaque ménage, sommés "
           "par cellule et territoire, seuil de 30 ménages observés"),
    Source("Les cellules et les blocs des ménages du jumeau", "`jumeau.gagnants` (D-409)",
           "le gain par ménage de chaque cellule, année par année"),
)

LIMITES = (
    "Pourquoi « illustratif » ici : la répartition des cellules entre les territoires est "
    "une hypothèse (le même gain par ménage partout dans une cellule), pas une passe par "
    "territoire ; c'est vrai même pour un programme chiffré tel quel.",
    "Les types de territoire : Paris, l'agglomération parisienne (zone APL 1) ; grandes "
    "villes, les agglomérations de plus de 100 000 habitants (zone 2) ; villes moyennes, "
    "le reste des unités urbaines (zone 3) ; rural, les communes hors unité urbaine ; "
    "outre-mer, Guadeloupe, Martinique, Guyane et La Réunion (pas Mayotte).",
    "Le gain par ménage d'une cellule (décile × type) est supposé le même partout : deux "
    "ménages de la même cellule gagnent autant à Paris et en Guyane. Les prix, les loyers "
    "et l'emploi locaux ne sont pas modélisés ; l'emploi du jumeau est national, réparti "
    "aux cellules, pas aux territoires.",
    "Une mesure territoriale (un taux outre-mer, une aide au logement de zone 1) n'est vue "
    "que par la passe de sa mesure, au décile : son ciblage géographique est perdu.",
    "Aucune région métropolitaine : l'enquête Emploi diffusée n'en porte pas. La zone APL "
    "est tirée sur le statut de la commune et d'occupation (les ménages de zone 1 sont des "
    "ménages urbains de même statut, pas ceux de l'Île-de-France) ; le rural (hors unité "
    "urbaine) et l'outre-mer sont observés.",
    "Le rangement dans les cellules vient d'une passe au droit de 2026 sans les imputations "
    "du capital ; les cellules du jumeau, d'une passe au droit de 2024 sur 30 000 ménages : "
    "les ménages d'une cellule diffèrent de 4 % en médiane entre les deux (D-645).",
    "Une case de moins de 30 ménages observés prend la répartition de son décile (D-645).",
    "Le contrôle de la table (D-646, D-647) : le rural tenu (sa pauvreté 4,0 points sous "
    "celle de la métropole, 4,9 publiés), La Réunion manquée (médiane à 0,82 de celle de "
    "la métropole, 0,74 publiés) : la population tire ses revenus sur des lois nationales, "
    "l'outre-mer y est moins pauvre qu'en vrai, et un gain y pèse en % un peu moins qu'il "
    "ne le devrait.",
    "La bande, quand il y en a, est celle de la moyenne nationale (5 à 95 % des tirages des "
    "θ) ; les barres par territoire sont au réglage.",
)


#: Les noms courts des barres (la page n'a qu'une étroite colonne d'étiquettes) ; les
#: noms longs, et ce qu'est chaque zone, sont dans les limites.
COURTS = {"zone_1": "Paris (zone 1)", "zone_2": "Grandes villes", "zone_3": "Villes moyennes",
          "rural": "Rural", "outre_mer": "Outre-mer"}


@cache
def table(chemin: str = str(TABLE)) -> dict[str, Any]:
    return json.loads(Path(chemin).read_text(encoding="utf-8"))


def axe(t: Mapping[str, Any], nom: str) -> dict[str, Any]:
    """Un axe de la table : ses territoires et ses sommes en tableaux (50, T)."""
    a = t["axes"][nom]
    out = {k: np.asarray(a[k], dtype=float)
           for k in ("menages", "personnes", "uc", "revenu_disponible")}
    out["cles"] = [x["cle"] for x in a["territoires"]]
    out["libelles"] = [x["libelle"] for x in a["territoires"]]
    return out


def parts(a: Mapping[str, Any]) -> np.ndarray:
    """(50, T) : la part des ménages de chaque cellule dans chaque territoire."""
    m = a["menages"]
    s = m.sum(axis=1, keepdims=True)
    return np.divide(m, s, out=np.zeros_like(m), where=s > 0)


def relatif(a: Mapping[str, Any]) -> np.ndarray:
    """(50, T) : le revenu disponible par ménage d'une case rapporté à celui de sa cellule
    (1 pour une case vide)."""
    m, rd = a["menages"], a["revenu_disponible"]
    case = np.divide(rd, m, out=np.zeros_like(rd), where=m > 0)
    cell = rd.sum(axis=1) / m.sum(axis=1)
    return np.where(m > 0, case / cell[:, None], 1.0)


# --------------------------------------------------------------------- le contrôle
def repartition(t: Mapping[str, Any], nom: str, cle: str) -> np.ndarray:
    """La fonction de répartition des personnes du territoire aux onze bornes des
    déciles (0, les neuf seuils, +∞) : forme (11,)."""
    a = axe(t, nom)
    j = a["cles"].index(cle)
    p = a["personnes"][:, j].reshape(t["deciles"], len(t["types"])).sum(axis=1)
    return np.concatenate([[0.0], np.cumsum(p) / p.sum()])


def quantile(t: Mapping[str, Any], nom: str, cle: str, q: float) -> float | None:
    """Le quantile q du niveau de vie des personnes du territoire, interpolé linéairement
    entre les seuils de décile ; None s'il tombe dans le premier ou le dernier décile
    (aucune borne)."""
    f = repartition(t, nom, cle)
    s = t["seuils_niveau_de_vie"]
    d = int(np.searchsorted(f, q, side="left"))  # q dans ]f[d-1] ; f[d]]
    if d <= 1 or d >= len(f) - 1:
        return None
    return float(s[d - 2] + (q - f[d - 1]) / (f[d] - f[d - 1]) * (s[d - 1] - s[d - 2]))


def part_sous(t: Mapping[str, Any], nom: str, cle: str, seuil: float) -> float | None:
    """La part des personnes du territoire sous un niveau de vie, même interpolation ;
    None si le seuil tombe dans le premier ou le dernier décile."""
    s = t["seuils_niveau_de_vie"]
    d = int(np.searchsorted(s, seuil))  # seuil dans [s[d-1] ; s[d]], décile d+1
    if d == 0 or d >= len(s):
        return None
    f = repartition(t, nom, cle)
    return float(f[d] + (seuil - s[d - 1]) / (s[d] - s[d - 1]) * (f[d + 1] - f[d]))


# --------------------------------------------------------------------- la dimension
class TerritoiresAbsents(ValueError):
    """Un gain des cellules que le réglage ne porte pas : la dimension n'est pas calculée,
    et la page dit pourquoi (D-605)."""


def gains_cellules(trajectoire: Any, depart: Any, cellules: Any, mode: str | None
                   ) -> tuple[np.ndarray, str]:
    """(années, 50, n) : le gain par ménage de chaque cellule (€ par an), et ce qu'il
    porte. Le mode structurel : `gagnants_perdants` (le choc statique et la dynamique) ;
    sinon le choc statique de chaque mesure sur son décile, réparti au prorata des
    ménages."""
    menages = np.asarray(cellules["menages"], dtype=float)
    if mode == "structurel":
        from impots.jumeau.gagnants import gagnants_perdants

        g = gagnants_perdants(trajectoire, depart, cellules)
        return g.par_menage, "le choc statique et la dynamique (gagnants, D-409)"
    from impots.jumeau.blocs.menages import choc_menages

    n_types = menages.size // 10
    par_decile = menages.reshape(10, n_types).sum(axis=1)
    out = np.zeros((len(trajectoire.annees), menages.size, 1))
    lus = set()
    for k, a in enumerate(trajectoire.annees):
        for m in trajectoire.mesures:
            choc = choc_menages(m, a).get("deciles")
            if choc is not None:
                lus.add(m.identifiant)
                par = np.asarray(choc, dtype=float) * 1e9 / par_decile
                out[k, :, 0] += np.repeat(par, n_types)
    sans = [m for m in trajectoire.mesures if m.identifiant not in lus]
    if sans:
        # Absent, jamais zéro : une mesure dont le choc par décile n'est pas porté.
        raisons = "; ".join(f"« {m.identifiant} » : "
                            f"{(m.non_portes or {}).get('menages', 'aucun choc par décile')}"
                            for m in sans)
        raise TerritoiresAbsents(f"le mode {mode or 'réduit'} ne porte pas les cellules et "
                                 f"le choc par décile manque ({raisons})")
    return out, "le choc statique seul (le mode réduit ne porte pas la dynamique)"


def revenu_reference(reference: Sequence[Any], cellules: Any) -> np.ndarray | None:
    """(années, 50, n) : le revenu disponible par ménage de chaque cellule dans la
    référence, sa part du PIB nominal de la référence, comme `blocs.menages`."""
    from impots.jumeau.blocs.menages import charger

    pib = niveaux(reference, "pib")
    if pib is None:
        return None
    rd = np.asarray(cellules["revenu_disponible"], dtype=float)
    menages = np.asarray(cellules["menages"], dtype=float)
    part = rd / 1e9 / charger().pib_cellules
    return part[None, :, None] * pib[:, None, :] * 1e9 / menages[None, :, None]


def par_territoire(g: np.ndarray, y: np.ndarray | None, menages: np.ndarray,
                   a: Mapping[str, Any]) -> dict[str, np.ndarray | None]:
    """Pour chaque territoire de l'axe, (années, n) : le gain moyen par ménage (€), en %
    du revenu de référence, la part des ménages gagnants ; et la même chose pour
    l'ensemble (la dernière colonne)."""
    w = parts(a) * menages[:, None]  # (50, T) ménages du jumeau par case
    w = np.concatenate([w, menages[:, None]], axis=1)  # + l'ensemble
    kappa = np.concatenate([relatif(a), np.ones((menages.size, 1))], axis=1)
    poids = w.sum(axis=0)  # (T+1,)
    euros = np.einsum("akn,kt->atn", g, w) / poids[None, :, None]
    gagne = np.einsum("akn,kt->atn", (g > SEUIL_GAGNANT).astype(float), w) / \
        poids[None, :, None]
    pct = None
    if y is not None:
        revenu = np.einsum("akn,kt->atn", y, w * kappa)
        pct = 100.0 * np.einsum("akn,kt->atn", g, w) / revenu
    return {"euros": euros, "pct": pct, "gagnants": 100.0 * gagne}


def _bande(x: np.ndarray | None) -> tuple[np.ndarray | None, np.ndarray | None]:
    if x is None or x.shape[1] < 2:
        return None, None
    lo, hi = (np.percentile(x, q, axis=1) for q in QUANTILES)
    return lo, hi


@inscrire(CLE)
def territoires(variante: Any, reference: Any, depart: Any, cellules: Any,
                **options: Any) -> Dimension:
    traj = options.get("trajectoire")
    mode = options.get("mode")
    t = table()
    menages = np.asarray(cellules["menages"], dtype=float)
    g, porte = gains_cellules(traj, depart, cellules, mode)
    y = revenu_reference(reference, cellules)
    tirages = options.get("tirages")
    gt = yt = None
    if tirages is not None and mode == "structurel" and \
            len(tirages.annees) == len(traj.annees):
        gt, _ = gains_cellules(tirages, depart, cellules, mode)
        yt = revenu_reference(tirages.reference, cellules)

    indicateurs: list[Indicateur] = []
    for nom_axe, titre_axe in (("types", "par type de territoire"),
                               ("regions", "par région")):
        a = axe(t, nom_axe)
        r = par_territoire(g, y, menages, a)
        rt = par_territoire(gt, yt, menages, a) if gt is not None else None
        for cle, libelle, unite, sens in (
                ("pct", "Gain en % du revenu", "%", 1),
                ("euros", "Gain par ménage", "€ par an", 1),
                ("gagnants", "Part des gagnants (plus de 10 € par an)", "%", 0)):
            x = r[cle]
            if x is None:
                continue
            bas, haut = _bande(None if rt is None or rt[cle] is None else rt[cle][:, -1, :])
            groupes = {COURTS.get(k, lib): x[:, j, 0]
                       for j, (k, lib) in enumerate(zip(a["cles"], a["libelles"], strict=True))}
            indicateurs.append(Indicateur(
                f"{cle}_{nom_axe}", f"{libelle}, {titre_axe}", unite, x[:, -1, 0],
                bas=bas, haut=haut, par_groupe=groupes, sens=sens))
        if nom_axe == "types" and r["pct"] is not None:
            # L'écart entre le type de territoire qui gagne le plus et celui qui gagne le
            # moins (en % du revenu, hors outre-mer, l'autre axe le montre).
            p = r["pct"][:, :4, 0]
            indicateurs.append(Indicateur(
                "ecart_types", "Écart entre types de territoire (métropole)", "points de %",
                p.max(axis=1) - p.min(axis=1),
                sens=0))
    statut_, limites = statut(options)
    limites = [*limites, *LIMITES, f"Le gain des cellules : {porte}."]
    if y is None:
        limites.append("Sans le PIB de la référence, le gain n'est pas rapporté au revenu.")
    return Dimension(
        cle=CLE, titre="Où ça tombe : les territoires",
        question="Qui gagne ou perd, outre-mer ou en métropole, dans les grandes villes ou "
                 "à la campagne ?",
        annees=tuple(int(a) for a in options.get("annees") or traj.annees),
        indicateurs=tuple(indicateurs), statut="illustratif", sources=SOURCES,
        limites=tuple(limites),
        notes={"decision": "D-645", "controle": "D-646, D-647",
               "statut_des_autres_dimensions": statut_,
               "seuil_gagnant": SEUIL_GAGNANT,
               "table": {k: t["meta"].get(k) for k in ("population_sha256", "passe",
                                                       "passe_sha256", "commit")}})
