"""Ce qui rapproche ou sépare : la pauvreté, les inégalités, les écarts entre groupes (D-591).

LA QUESTION. La mesure rapproche-t-elle les gens ou les éloigne-t-elle les uns des autres ?
On ne mesure pas l'entente elle-même (la confiance, la cohésion) : aucun coefficient
publié ne la relie de façon sûre à ce que le jumeau calcule, et la dimension n'en invente
pas. On mesure ce que la littérature tient pour ses conditions matérielles, avec les
définitions de l'Insee : le taux de pauvreté monétaire (60 % du niveau de vie médian),
le coefficient de Gini, le rapport interdécile D9/D1 et le rapport S80/S20 des niveaux de
vie, et l'écart entre groupes (types de ménages ; âge, statut, territoire quand la
distribution les porte).

LA MÉTHODE, ET SA LIMITE. Le jumeau ne porte pas de ménages, mais cinquante cellules
(décile × type, `jumeau.cellules`). Une distribution des niveaux de vie se reconstitue
dans chaque cellule, de deux façons, dites dans chaque résultat (`Distribution.source`) :

* **mesurée** : les quantiles du niveau de vie des personnes de chaque cellule, lus une
  fois sur la passe de référence des cellules (`scripts/jumeau_niveaux_de_vie.py`, des
  agrégats commités dans `reports/jumeau/niveaux_de_vie_cellules.json`), et les
  indicateurs mesurés directement sur la passe pour recouper la reconstitution ;
* **approchée** (à défaut) : le niveau de vie moyen de chaque décile (somme des revenus
  disponibles sur somme des unités de consommation), placé au milieu de son décile, une
  fonction de quantile linéaire par morceaux entre ces points (prolongée aux bouts, pas
  sous zéro), chaque cellule à la moyenne de sa cellule.

La variante déplace chaque personne d'une cellule du gain de sa cellule par unité de
consommation (le même pour tous, `pouvoir`), aux prix de l'année : le niveau de vie de
référence suit le PIB de la référence, comme le revenu des cellules. Puis, sur le mélange
des cellules (chaque quantile, une masse de personnes ; la fonction de répartition
interpolée entre les points, continue), la médiane, le seuil à 60 %, la part des
personnes sous le seuil, les déciles D1 et D9, les masses des 20 % du bas et du haut, et
le Gini des points. Ces indicateurs sont relatifs : un prix plus haut pour tous ne les
change pas, ils se lisent sur le nominal.

La limite : le déplacement est uniforme dans la cellule (une mesure ciblée sur les plus
pauvres d'un décile n'y est pas vue comme telle), et les rangs ne se refont pas entre
cellules au-delà de ce que les montants font. L'écart à la variation que donnerait la
microsimulation elle-même se mesure sur un cas (D-592) ; il est dit à côté des nombres.

Ce module tourne dans le navigateur (D-415) : numpy seulement.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from impots.jumeau.cellules import N_CELLULES, N_DECILES, TYPES
from impots.jumeau.impacts import Dimension, Indicateur, Source, inscrire
from impots.jumeau.impacts.pouvoir import LIBELLES_TYPES, Revenus, bande, chemin, revenus_de

ROOT = Path(__file__).resolve().parents[4]
FICHIER = ROOT / "reports" / "jumeau" / "niveaux_de_vie_cellules.json"
#: Le seuil de pauvreté monétaire, en part du niveau de vie médian (Insee, la définition
#: européenne).
SEUIL_PAUVRETE = 0.6
#: Les points par cellule de la distribution approchée.
POINTS_APPROCHES = 10


class EntenteError(ValueError):
    """Une distribution des niveaux de vie qui ne se lit pas."""


@dataclass(frozen=True)
class Distribution:
    """Les niveaux de vie des personnes de chaque cellule, l'année des cellules.

    `quantiles` (50, K) en € par unité de consommation et par an, aux rangs `rangs` (K,)
    de la cellule ; `groupes` : pour une famille de groupes (« Âge de la personne de
    référence »…), chaque groupe → (personnes par cellule (50,), niveau de vie moyen de
    ses personnes dans la cellule (50,)) ; `reference` : les indicateurs mesurés
    directement sur la passe, pour recouper la reconstitution."""

    rangs: np.ndarray
    quantiles: np.ndarray
    source: str
    groupes: Mapping[str, Mapping[str, tuple[np.ndarray, np.ndarray]]] = field(
        default_factory=dict)
    reference: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        q = np.asarray(self.quantiles, dtype=float)
        if q.shape != (N_CELLULES, np.size(self.rangs)):
            raise EntenteError(f"quantiles de forme {q.shape}")
        if not np.all(np.isfinite(q)) or np.any(np.diff(q, axis=1) < -1e-9):
            raise EntenteError("quantiles non finis ou non croissants")


def approchee(cellules: Any) -> Distribution:
    """La distribution approchée depuis les seules cellules (voir le module)."""
    rd, uc = cellules["revenu_disponible"], cellules["uc"]
    m_d = cellules.par_decile("revenu_disponible") / cellules.par_decile("uc")
    milieux = (np.arange(N_DECILES) + 0.5) / N_DECILES
    pente_bas = (m_d[1] - m_d[0]) / (milieux[1] - milieux[0])
    pente_haut = (m_d[-1] - m_d[-2]) / (milieux[-1] - milieux[-2])
    xp = np.concatenate([[0.0], milieux, [1.0]])
    fp = np.concatenate([[max(m_d[0] - pente_bas * milieux[0], 0.0)], m_d,
                         [m_d[-1] + pente_haut * (1.0 - milieux[-1])]])
    rangs = (np.arange(POINTS_APPROCHES) + 0.5) / POINTS_APPROCHES
    q = np.empty((N_CELLULES, POINTS_APPROCHES))
    for k in range(N_CELLULES):
        d = k // len(TYPES)
        forme = np.interp((d + rangs) / N_DECILES, xp, fp)
        m_c = rd[k] / uc[k] if uc[k] > 0 else m_d[d]
        q[k] = forme * m_c / forme.mean()
    return Distribution(rangs=rangs, quantiles=q,
                        source="approchée : les niveaux de vie moyens des déciles, "
                               "interpolés linéairement entre les milieux des déciles")


def depuis_dict(d: Mapping[str, Any]) -> Distribution:
    """La distribution mesurée, telle que `scripts/jumeau_niveaux_de_vie.py` l'écrit."""
    if tuple(d["types"]) != TYPES or int(d["deciles"]) != N_DECILES:
        raise EntenteError("une distribution d'un autre découpage que celui du code")
    groupes = {fam: {g: (np.asarray(v["personnes"], dtype=float),
                         np.asarray(v["niveau_de_vie"], dtype=float))
                     for g, v in gs.items()} for fam, gs in d.get("groupes", {}).items()}
    return Distribution(rangs=np.asarray(d["rangs"], dtype=float),
                        quantiles=np.asarray(d["quantiles"], dtype=float),
                        source=d["source"], groupes=groupes,
                        reference=dict(d.get("reference", {})))


def lire(chemin_: Path = FICHIER) -> Distribution | None:
    if not chemin_.exists():
        return None
    return depuis_dict(json.loads(chemin_.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- #
# les indicateurs d'une distribution
# --------------------------------------------------------------------------- #
def _repartition(x: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Les points triés et la fonction de répartition au milieu de chaque masse."""
    o = np.argsort(x, kind="stable")
    xs, ws = x[o], w[o]
    cum = np.cumsum(ws)
    return xs, (cum - 0.5 * ws) / cum[-1]


def quantile(x: np.ndarray, w: np.ndarray, p: float) -> float:
    xs, f = _repartition(x, w)
    return float(np.interp(p, f, xs))


def gini(x: np.ndarray, w: np.ndarray) -> float:
    """Le Gini de points pondérés : Σ_i Σ_j w_i w_j |x_i − x_j| / (2 W² μ)."""
    o = np.argsort(x, kind="stable")
    xs, ws = x[o], w[o]
    big_w = ws.sum()
    mu = float((ws * xs).sum() / big_w)
    cum_w = np.cumsum(ws) - ws
    cum_xw = np.cumsum(ws * xs) - ws * xs
    # Σ_{i>j} w_i w_j (x_i − x_j) = Σ_i w_i (x_i W_<i − S_<i)
    s = float((ws * (xs * cum_w - cum_xw)).sum())
    return 2.0 * s / (2.0 * big_w ** 2 * mu)


def _masse_sous(x: np.ndarray, w: np.ndarray, p: float) -> float:
    """La part du revenu des p premiers % des personnes (interpolée)."""
    o = np.argsort(x, kind="stable")
    xs, ws = x[o], w[o]
    cw = np.concatenate([[0.0], np.cumsum(ws)]) / ws.sum()
    cx = np.concatenate([[0.0], np.cumsum(ws * xs)]) / (ws * xs).sum()
    return float(np.interp(p, cw, cx))


def indicateurs(x: np.ndarray, w: np.ndarray, cellule: np.ndarray, rangs: np.ndarray
                ) -> dict[str, Any]:
    """Les indicateurs de points (x, w), cellule de chaque point : la médiane, le seuil, le
    taux de pauvreté (ensemble et par cellule), D9/D1, S80/S20, Gini."""
    med = quantile(x, w, 0.5)
    seuil = SEUIL_PAUVRETE * med
    xs, f = _repartition(x, w)
    taux = float(np.interp(seuil, xs, f, left=0.0, right=1.0))
    k = rangs.size
    xc = x.reshape(-1, k)
    # Dans chaque cellule, la répartition linéaire entre ses quantiles, aux mêmes bouts.
    par_cellule = np.array([np.interp(seuil, xc[c], rangs, left=0.0, right=1.0)
                            for c in range(xc.shape[0])])
    s20 = _masse_sous(x, w, 0.2)
    return {"mediane": med, "seuil": seuil, "pauvrete": taux, "pauvrete_cellules":
            par_cellule, "d9_d1": quantile(x, w, 0.9) / quantile(x, w, 0.1),
            "s80_s20": (1.0 - _masse_sous(x, w, 0.8)) / s20, "gini": gini(x, w),
            "moyenne": float((x * w).sum() / w.sum())}


# --------------------------------------------------------------------------- #
# la dimension
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Calcul:
    annees: tuple[int, ...]
    reference: dict[str, np.ndarray]
    """Chaque indicateur de la référence, (années, tirages) ; ils ne bougent pas avec
    les années (la distribution de référence suit le PIB, uniformément)."""
    variante: dict[str, np.ndarray]
    pauvrete_types: dict[str, np.ndarray]
    pauvrete_types_ref: dict[str, float]
    positions: dict[str, dict[str, np.ndarray]]
    """Par famille de groupes, la position de chaque groupe (son niveau de vie moyen
    sur celui de l'ensemble, moins 1, en %), écart variante − référence (années, tirages)."""
    positions_ref: dict[str, dict[str, float]]


def calculer_entente(r: Revenus, cellules: Any, distribution: Distribution,
                     pib_cellules: float, pib_reference: np.ndarray) -> Calcul:
    """Les indicateurs, année par année et tirage par tirage. `pib_reference` (années,
    tirages) en Md€ ; `pib_cellules` celui de l'année des cellules."""
    k = distribution.rangs.size
    q = distribution.quantiles.reshape(-1)
    cellule = np.repeat(np.arange(N_CELLULES), k)
    pers = np.asarray(cellules["personnes"], dtype=float)
    w = np.repeat(pers / k, k)
    # Le gain par UC, ramené à l'année des cellules (divisé par la croissance du PIB).
    gain = r.nominal * 1e9 / r.uc[None, :, None]                          # (A, 50, n)
    echelle = pib_cellules / np.asarray(pib_reference, dtype=float)        # (A, n)
    base = indicateurs(q, w, cellule, distribution.rangs)
    cles = ("pauvrete", "d9_d1", "s80_s20", "gini", "mediane", "moyenne")
    A, n = gain.shape[0], gain.shape[2]
    var = {c: np.empty((A, n)) for c in cles}
    typ = np.tile(np.arange(len(TYPES)), N_DECILES)
    pt = {LIBELLES_TYPES[t]: np.empty((A, n)) for t in TYPES}
    pt_ref = {LIBELLES_TYPES[t]: float((base["pauvrete_cellules"] * pers)[typ == i].sum()
                                       / pers[typ == i].sum())
              for i, t in enumerate(TYPES)}
    familles = {"Type de ménage": {LIBELLES_TYPES[t]: (pers * (typ == i),
                                                       cellules["revenu_disponible"]
                                                       / cellules["uc"])
                                   for i, t in enumerate(TYPES)}}
    familles.update(distribution.groupes)
    moy_ref = base["moyenne"]

    def position(gs: Mapping[str, tuple[np.ndarray, np.ndarray]], delta: np.ndarray,
                 moyenne: float) -> dict[str, float]:
        return {g: 100.0 * (float((p * (nv + delta)).sum() / p.sum()) / moyenne - 1.0)
                for g, (p, nv) in gs.items() if p.sum() > 0}

    positions_ref = {f: position(gs, np.zeros(N_CELLULES), moy_ref)
                     for f, gs in familles.items()}
    positions = {f: {g: np.empty((A, n)) for g in gs} for f, gs in positions_ref.items()}
    for a in range(A):
        for j in range(n):
            delta = gain[a, :, j] * echelle[a, j]
            x = q + np.repeat(delta, k)
            ind = indicateurs(x, w, cellule, distribution.rangs)
            for c in cles:
                var[c][a, j] = ind[c]
            for i, t in enumerate(TYPES):
                s = typ == i
                pt[LIBELLES_TYPES[t]][a, j] = float(
                    (ind["pauvrete_cellules"] * pers)[s].sum() / pers[s].sum())
            for f, gs in familles.items():
                for g, v in position(gs, delta, ind["moyenne"]).items():
                    positions[f][g][a, j] = v - positions_ref[f][g]
    ref = {c: np.full((A, n), base[c]) for c in cles}
    return Calcul(annees=r.annees, reference=ref, variante=var, pauvrete_types=pt,
                  pauvrete_types_ref=pt_ref, positions=positions, positions_ref=positions_ref)


SOURCES = (
    Source("Insee, définitions : pauvreté monétaire, niveau de vie, Gini, rapport "
           "interdécile, S80/S20", "insee.fr, « Définitions »",
           "le seuil à 60 % du niveau de vie médian ; l'échelle de l'OCDE modifiée"),
    Source("Cellules de ménages du jumeau (D-409), population de D-553",
           "`data/processed/jumeau_cellules_2024.json`",
           "le revenu disponible, les personnes et les unités de consommation des cellules"),
)
LIMITES = (
    "Les indicateurs sont reconstitués sur cinquante cellules : chaque personne d'une "
    "cellule y gagne autant par unité de consommation ; une mesure ciblée à l'intérieur "
    "d'une cellule n'est pas vue comme telle.",
    "On ne mesure pas l'entente elle-même (la confiance, la cohésion) : aucun coefficient "
    "publié n'est appliqué ; la dimension dit les écarts de niveau de vie, que la "
    "littérature tient pour une de leurs conditions.",
    "Les rangs ne se refont pas entre cellules au-delà de ce que les montants font ; le "
    "seuil de pauvreté bouge avec la médiane (la pauvreté relative).",
)


@inscrire("entente")
def entente(variante: Any, reference: Any, depart: Any, cellules: Any,
            **options: Any) -> Dimension:
    """Ce qui rapproche ou sépare : pauvreté, Gini, D9/D1, S80/S20, écarts entre groupes.

    Les mêmes entrées que `pouvoir.pouvoir_achat` ; `options["distribution"]` : une
    `Distribution` (ou son dictionnaire) ; à défaut celle de `FICHIER` si elle est là,
    sinon l'approchée."""
    from impots.jumeau.blocs.menages import charger

    params = options.get("params") or charger()
    r, _mesures = revenus_de(variante, reference, depart, cellules,
                             {**options, "params": params})
    dist = options.get("distribution")
    if isinstance(dist, Mapping):
        dist = depuis_dict(dist)
    if dist is None and options.get("lire_fichier", True):
        dist = lire()
    if dist is None:
        dist = approchee(cellules)
    n = r.n
    if options.get("revenus") is not None:
        pib = np.full((len(r.annees), n), params.pib_cellules)
    else:
        c = chemin(variante, reference, options.get("mesures"), options.get("annees"))
        pib = np.stack([np.broadcast_to(np.asarray(e["pib"], dtype=float), (n,))
                        for e in c.reference])
    calc = calculer_entente(r, cellules, dist, params.pib_cellules, pib)
    debut = options.get("tirages_depuis", 1 if n > 2 else None)

    def ecart(cle: str, facteur: float = 1.0) -> np.ndarray:
        return facteur * (calc.variante[cle] - calc.reference[cle])

    def ind(cle: str, libelle: str, unite: str, serie: np.ndarray, sens: int,
            par_groupe: Mapping[str, np.ndarray] | None = None) -> Indicateur:
        v, b, h = bande(serie, debut)
        return Indicateur(cle=cle, libelle=libelle, unite=unite, valeurs=v, bas=b, haut=h,
                          par_groupe=None if par_groupe is None else
                          {g: s[:, 0] for g, s in par_groupe.items()}, sens=sens)

    pauvrete_types = {g: 100.0 * (s - calc.pauvrete_types_ref[g])
                      for g, s in calc.pauvrete_types.items()}
    indicateurs_ = [
        ind("pauvrete", "Taux de pauvreté (60 % du niveau de vie médian)",
            "points de %", ecart("pauvrete", 100.0), -1, pauvrete_types),
        ind("gini", "Coefficient de Gini des niveaux de vie", "points de Gini (×100)",
            ecart("gini", 100.0), -1),
        ind("d9_d1", "Rapport interdécile D9/D1", "écart du rapport", ecart("d9_d1"), -1),
        ind("s80_s20", "Rapport S80/S20 (masse des 20 % du haut sur celle du bas)",
            "écart du rapport", ecart("s80_s20"), -1),
    ]
    for famille, pos in calc.positions.items():
        ref = calc.positions_ref[famille]
        # L'écart moyen des groupes à la moyenne : Σ_g s_g |position_g|, s_g la part des
        # personnes ; son écart variante − référence (points de %).
        parts = _parts(famille, cellules, dist)
        absolu_ref = sum(parts[g] * abs(ref[g]) for g in ref)
        absolu_var = sum(parts[g] * np.abs(ref[g] + pos[g]) for g in ref)
        indicateurs_.append(ind(
            f"ecart_{_cle(famille)}", f"Écart moyen des groupes à la moyenne : {famille}",
            "points de % du niveau de vie moyen", absolu_var - absolu_ref, -1, pos))
    juge = options.get("juge_entente")
    return Dimension(
        cle="entente", titre="Ce qui rapproche ou sépare",
        question="La mesure rapproche-t-elle les niveaux de vie, ou les éloigne-t-elle ?",
        annees=r.annees, indicateurs=tuple(indicateurs_),
        statut="jugé" if juge else "sourcé, non jugé", sources=SOURCES, limites=LIMITES,
        juge=juge,
        notes={"distribution": dist.source,
               "reference": {"pauvrete_pct": 100.0 * float(calc.reference["pauvrete"][0, 0]),
                             "gini": float(calc.reference["gini"][0, 0]),
                             "d9_d1": float(calc.reference["d9_d1"][0, 0]),
                             "s80_s20": float(calc.reference["s80_s20"][0, 0]),
                             "mediane_euros_2024": float(calc.reference["mediane"][0, 0])},
               "reference_mesuree_sur_la_passe": dict(dist.reference),
               "pauvrete_types_reference_pct": {g: 100.0 * v for g, v in
                                                calc.pauvrete_types_ref.items()},
               "positions_reference_pct": calc.positions_ref,
               "tirages": n, "tirages_depuis": debut})


def _cle(famille: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", famille).encode("ascii", "ignore").decode().lower()
    return "_".join(w for w in "".join(ch if ch.isalnum() else " " for ch in s).split())


def _parts(famille: str, cellules: Any, dist: Distribution) -> dict[str, float]:
    pers = np.asarray(cellules["personnes"], dtype=float)
    if famille == "Type de ménage":
        typ = np.tile(np.arange(len(TYPES)), N_DECILES)
        return {LIBELLES_TYPES[t]: float(pers[typ == i].sum() / pers.sum())
                for i, t in enumerate(TYPES)}
    gs = dist.groupes[famille]
    total = sum(float(p.sum()) for p, _ in gs.values())
    return {g: float(p.sum()) / total for g, (p, _) in gs.items()}


__all__ = ["Distribution", "approchee", "calculer_entente", "depuis_dict", "entente",
           "gini", "indicateurs", "lire"]
