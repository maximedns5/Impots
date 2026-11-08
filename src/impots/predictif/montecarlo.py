"""The Monte Carlo beside the θ box (D-336, decision 6).

The box says how far Δb moves when every claimed effect runs through its published range;
it is not a probability, and says so. This is the other object, named apart: the
distribution of Δb at the last year under DECLARED LAWS, drawn on the replay of the report
(`rejouer`), without a pass.

THE LAWS, declared here and nowhere else:

* each claimed row follows its own law in the store (`store.Parameter`): triangular on
  (low, centre, high), uniform on [low, high], or normal with [low, high] read as a 90 %
  interval, as `Parameter.draw` reads them;
* the rows of ONE ARTICLE are tied by a gaussian copula of correlation ρ = 0,8; rows of
  different articles are independent. THE KEY OF AN ARTICLE IS THE STORE'S YAML FILE the
  row lives in — one file per article in the shipped store (C1 in `eti.yaml`, Cabannes,
  Houdré and Landais; C7 in `labour_supply.yaml`, Bargain, Orsini and Peichl; C10 in
  `dividends.yaml`, Bach et al.). The citations are not one string per article, the files
  are;
* the multiplier's shift z is a standard normal, independent of the rows: m = c(h) + z sd,
  centre Mésange, sd IMK, CENSORED at zero by the bound of decision 2 (m = max(0, ·)). A
  truncation in the strict sense would differ by instrument and horizon, which one common
  z cannot carry; the censored mass is the share of draws at the bound.

THE OUTPUTS, per view, under one persistence (« lue », the verdict's, by default): the
share of draws where Δb at the last year is positive, its quantiles at 5, 50 and 95 %, and
Sobol indices, first order and total (Saltelli's sampling, Jansen's total estimator) BY
ARTICLE — the rows of an article are correlated, and Sobol indices are defined for
independent inputs, so each article is one input, and the multiplier another.

2 000 draws by default, at a fixed seed: a share of 0,05 to ± 0,005. Vectorised on the
draws; with Sobol, N (K + 2) replays of the chain, K the number of articles.
"""

from __future__ import annotations

import functools
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
import yaml

from impots.predictif import rejouer

DRAWS = 2_000
SEED = 20261103
RHO = 0.8
COPULA_KEY = "fichier YAML du magasin où vit la ligne (un article par fichier)"
LAWS = ("Lois du magasin, ligne par ligne ; copule gaussienne de corrélation ρ entre les "
        "lignes d'un même article, indépendance entre articles ; décalage du "
        "multiplicateur normal centré réduit, multiplicateur Mésange + z × écart-type IMK censuré à "
        "zéro ; indépendant des lignes.")
NOT_A_FORECAST = ("Une distribution sous des lois déclarées, à côté de la boîte θ : elle "
                  "dépend de ces lois, et en changer change la réponse (D-336).")

_NORMAL = NormalDist()
_phi = np.vectorize(_NORMAL.cdf, otypes=[float])
_phi_inverse = np.vectorize(_NORMAL.inv_cdf, otypes=[float])


@functools.cache
def row_files(directory: Path | None = None) -> dict[str, str]:
    """Each row of the shipped store, and the YAML file it lives in: the copula's key."""
    from impots.behavioural.store import PARAMETERS

    out: dict[str, str] = {}
    for path in sorted((directory or PARAMETERS).glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key in document.get("parameters") or {}:
            out[key] = path.stem
    return out


def quantile_function(row: Mapping[str, Any], u: np.ndarray) -> np.ndarray:
    """The row's law, inverted: what `Parameter.draw` samples, at the uniforms `u`."""
    low, mode, high = float(row["low"]), float(row["central"]), float(row["high"])
    if low == high:
        return np.full(u.shape, mode)
    law = row.get("loi", "triangular")
    if law == "uniform":
        return low + u * (high - low)
    if law == "normal":
        return mode + (high - low) / (2 * 1.645) * _phi_inverse(np.clip(u, 1e-12, 1 - 1e-12))
    cut = (mode - low) / (high - low)
    lower = low + np.sqrt(u * (high - low) * (mode - low))
    upper = high - np.sqrt((1.0 - u) * (high - low) * (high - mode))
    return np.where(u < cut, lower, upper)


def _groups(rejeu: Mapping[str, Any]) -> dict[str, list[str]]:
    """The inputs: one per article (the claimed open rows of one file), and the
    multiplier when the loop reads one."""
    groups: dict[str, list[str]] = {}
    for key, row in sorted(rejeu["lignes"].items()):
        if float(row["low"]) != float(row["high"]):
            groups.setdefault(str(row["fichier"]), []).append(key)
    if rejeu["looped"] and (rejeu.get("macro") or {}).get("instruments"):
        groups[rejouer.MACRO_ROW] = [rejouer.MACRO_ROW]
    return groups


def _draw(rejeu: Mapping[str, Any], groups: Mapping[str, list[str]], n: int,
          rng: np.random.Generator, rho: float) -> dict[str, np.ndarray]:
    """One column per row, and the multiplier's shift z: the copula within an article."""
    out: dict[str, np.ndarray] = {}
    for name, keys in groups.items():
        if name == rejouer.MACRO_ROW:
            out[name] = rng.standard_normal(n)
            continue
        k = len(keys)
        correlation = np.full((k, k), rho) + (1.0 - rho) * np.eye(k)
        normals = rng.standard_normal((n, k)) @ np.linalg.cholesky(correlation).T
        uniforms = _phi(normals)
        for i, key in enumerate(keys):
            out[key] = quantile_function(rejeu["lignes"][key], uniforms[:, i])
    return out


def _last(payload: Mapping[str, Any], columns: Mapping[str, np.ndarray], *, view: str,
          persistence: str | None, rows: Sequence[str], **options: Any) -> np.ndarray:
    values = {key: columns[key] for key in rows}
    z = columns.get(rejouer.MACRO_ROW, 0.0)
    delta = rejouer.chemin(payload, view=view, values=values, z=z,
                           persistence=persistence, **options).delta[-1]
    n = len(next(iter(columns.values()))) if columns else 1
    return np.broadcast_to(np.asarray(delta, dtype=float), (n,)).copy()


def run(payload: Mapping[str, Any], *, draws: int = DRAWS, seed: int = SEED,
        rho: float = RHO, persistence: str | None = rejouer.READ,
        views: Sequence[str] = ("vieillie", "figee"), **options: Any) -> dict[str, Any]:
    """The distribution of Δb at the last year, per view, and its Sobol indices;
    `options` are `rejouer.chemin`'s (the wage variant, D-349)."""
    rejeu = payload["rejeu"]
    if not rejeu["looped"]:
        persistence = None
    groups = _groups(rejeu)
    rows = [key for key in rejeu["lignes"]]
    rng = np.random.default_rng(seed)
    a, b = _draw(rejeu, groups, draws, rng, rho), _draw(rejeu, groups, draws, rng, rho)
    # The fixed claimed rows sit at their centre in every draw.
    for key in rows:
        if key not in a:
            a[key] = b[key] = np.full(draws, float(rejeu["lignes"][key]["central"]))
    out: dict[str, Any] = {}
    for view in views:
        f_a = _last(payload, a, view=view, persistence=persistence, rows=rows, **options)
        f_b = _last(payload, b, view=view, persistence=persistence, rows=rows, **options)
        variance = float(np.var(np.concatenate([f_a, f_b])))
        sobol: dict[str, Any] = {}
        for name, keys in groups.items():
            mixed = dict(a)
            for key in keys:
                mixed[key] = b[key]
            f_ab = _last(payload, mixed, view=view, persistence=persistence, rows=rows,
                         **options)
            sobol[name] = ({"premier_ordre": float(np.mean(f_b * (f_ab - f_a)) / variance),
                            "total": float(0.5 * np.mean((f_a - f_ab) ** 2) / variance)}
                           if variance > 0 else None)
        q05, q50, q95 = (float(x) for x in np.quantile(f_a, [0.05, 0.50, 0.95]))
        out[view] = {"p_hausse": float(np.mean(f_a > 0.0)),
                     "quantiles": {"q05": q05, "q50": q50, "q95": q95},
                     "sobol": sobol, "evaluations": draws * (len(groups) + 2)}
    multiplier = None
    if rejouer.MACRO_ROW in groups:
        multiplier = {"loi": "normale (centre Mésange, écart-type IMK), censurée à zéro",
                      "decalage_moyen": float(np.mean(a[rejouer.MACRO_ROW]))}
    return {
        "objet": "distribution sous des lois déclarées",
        "lois": LAWS, "rho": rho, "cle_copule": COPULA_KEY,
        "groupes": {name: list(keys) for name, keys in groups.items()},
        "multiplicateur": multiplier, "tirages": draws, "graine": seed,
        "persistence": persistence, "annee": int(payload["years"][-1]["year"]),
        "vues": out, "note": NOT_A_FORECAST,
    }


#: The verdict's thresholds, fixed by D-345 before any pass: « hausse » when at least 90 %
#: of the draws raise the debt, « baisse » when at most 10 % do, « dépend » between.
SEUIL_VERDICT = 0.90


def verdict(monte: Mapping[str, Any], *, view: str = "vieillie",
            threshold: float = SEUIL_VERDICT) -> str:
    """The verdict (D-345): « hausse » when P(Δb > 0) ≥ `threshold`, « baisse » when
    P ≤ 1 − `threshold`, « dépend » between; the θ box stays published beside it."""
    share = monte["vues"][view]["p_hausse"]
    if share >= threshold:
        return "hausse"
    if share <= 1.0 - threshold + 1e-12:  # 1 − 0,9 is 0,0999… in floating point
        return "baisse"
    return "dépend"

