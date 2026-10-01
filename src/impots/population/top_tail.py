"""Phase 7 L1 — raking the synthetic income distribution onto DGFiP n° 41's fractiles.

**This is a CALIBRATION and it is opt-in and off by default.** Once it has run, the IR top
lines fit the published fractiles by construction and can never afterwards be cited as
evidence about anything. `reporting.Use` has a word for this — `calibration` — and
`SpentMarginError` exists to catch a line that forgets. The gate (D-120) stated the bill
before the build; this module is the build, and the bill is unchanged.

WHAT THE GATE MEASURED, AND WHY IT IS A REDISTRIBUTION RATHER THAN A TOP-UP.

Mean RFR per part, full population against n° 41: deciles 3-9 within +0,3 % to +9,2 %, the
last decile -6,6 %, the top centième -34,2 %, the top millième **-64,3 %** — 327 271 €
against 916 590 €. The synthetic distribution is not merely short at the top, it is
**compressed at both ends**: too much mass in the upper middle, far too little at the
extreme.

That shape is what makes the fix a redistribution. Converting the published NESTED means
into disjoint band targets shows it directly: the 90-99 band must come DOWN (×0,94) while
99-99,9 goes up (×1,13) and 99,9-100 goes up by ×2,80. Deciles 5 to 9 come down too, by 3
to 8 %. Adding income only at the top would overshoot the decile — the top centième is 36
md€ short while the whole decile is only 23 md€ short, so a top-up alone would push the
decile past its own published mean.

THE NESTED-TO-DISJOINT CONVERSION IS THE STEP MOST LIKELY TO BE GOT WRONG, so it is done
once, here, and named. n° 41 publishes «dernier dixième», then «dont dernier centième» and
«dont dernier millième» BENEATH it — each contained in the one above. Treating them as
three separate bands would triple-count the top thousandth and produce targets that no
distribution can satisfy simultaneously.

THREE ARTEFACTS, DECLARED, BECAUSE NONE IS VISIBLE IN THE OUTPUT.

1. **The multiplier is uniform inside a band.** A foyer at the 99,91st percentile gets the
   same ×2,80 as one at the 99,99th. The published data cannot distinguish them, and
   inventing a within-band gradient would be inventing a density — the same artefact, and
   the same refusal, as the niche imputation's «every foyer in a cell gets the same base».
2. **Fractile membership is computed BEFORE the scaling and not recomputed.** Scaling moves
   foyers across band boundaries, so the raked population does not exactly reproduce the
   targets; `residuals()` measures what is left rather than asserting it away. One pass is
   the honest thing to ship, and the residual is the honest thing to publish.
3. **Composition inside a foyer is preserved.** One factor multiplies every money column of
   a foyer's members, so the wage/pension/unemployment mix is untouched. This is a choice,
   not a neutral act: the real top millième is far more capital- and BNC-heavy than ours,
   and scaling salaries cannot represent that. It makes the LEVEL right and leaves the
   COMPOSITION as wrong as it was.

WHAT IT COSTS THE CALIBRATED TOTAL. The national income total moves, and by how much is
measured rather than assumed — `apply` returns it. The shaved bands are large and the
inflated one is tiny, so the two nearly cancel, but «nearly» is not «exactly» and the
figure travels with the result.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from impots.donnees import RAW

#: DGFiP Statistiques n° 41 (novembre 2025), Tableau 2, column «RFR par part fiscale —
#: Moyenne (en €)». READ, never typed: a comparator copied by hand is one nobody can
#: re-derive, and this file is the whole basis of the calibration.
#: Ancré à la racine du dépôt — c'était `Path("data/raw/...")`, relatif au répertoire
#: COURANT, si bien qu'un classeur présent se lisait « absent » hors de la racine.
WORKBOOK = RAW / "dgfip_stat_41_ir_2024_tables.xlsx"

#: The money columns a foyer's factor multiplies. Named as data so a column added to the
#: population cannot be silently left behind — the same reason `uprating.UPRATED` is a
#: dict rather than a list inside a function.
SCALED = ("salaire_brut_annuel", "pension_annuelle", "chomage_annuel")

#: Disjoint bands, as cumulative-weight fractions of foyers ordered by RFR per part.
#: The last three are the nested published rows converted to disjoint ones.
#: «1er», not «1e» — the publication writes «1er dixième», and a label that does not match
#: is a band silently left unscaled rather than an error. Harmless today (the first decile
#: is published «n.s.» and has no target at all) and a trap the day it is not.
BANDS: tuple[tuple[str, float, float], ...] = (
    *((f"{i + 1}{'er' if i == 0 else 'e'} dixième", i / 10, (i + 1) / 10)
      for i in range(9)),
    ("90–99 %", 0.90, 0.99),
    ("99–99,9 %", 0.99, 0.999),
    ("99,9–100 %", 0.999, 1.0),
)

#: A factor outside this range is not a recalibration, it is a different population.
#: The gate measured ×0,92 to ×2,80; anything beyond this says the comparator or the
#: population has moved and the run should stop rather than quietly rewrite incomes.
FACTOR_BOUNDS = (0.5, 5.0)


class TopTailError(RuntimeError):
    """A raking was asked for in a way that would silently rewrite the population."""


@dataclass(frozen=True)
class RakeResult:
    """What the rake did, in the terms a reader needs to judge it."""

    factors: Any
    """One multiplier per foyer, aligned with the sorted foyer order."""
    band_factors: dict[str, float]
    total_before_eur: float
    total_after_eur: float
    foyers_moved: float
    """Weighted count of foyers whose income was changed by more than 0,1 %."""

    @property
    def total_shift(self) -> float:
        """Relative change in the national income total — the price of the rake."""
        if self.total_before_eur == 0:
            raise TopTailError("total avant nul : le rapport ne dirait rien")
        return self.total_after_eur / self.total_before_eur - 1


def published_targets(workbook: Path | None = None) -> dict[str, float]:
    """The disjoint band targets, derived from n° 41's nested published means.

    **The nested-to-disjoint step lives here and nowhere else.** «dont dernier centième»
    is contained in «dernier dixième», and «dont dernier millième» in both; treating the
    three as separate bands would count the top thousandth three times and produce a set
    of targets no distribution can meet at once.
    """
    import openpyxl

    path = workbook or WORKBOOK
    if not Path(path).exists():
        # Même type qu'avant — seul le message change : l'erreur brute d'openpyxl ne
        # disait ni d'où vient le classeur, ni quelle commande le produit.
        raise FileNotFoundError(
            f"{path} not found — `impots data fetch {Path(path).name}` le télécharge "
            f"depuis son entrée de manifeste ; `impots data check` liste le reste.")
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    published: dict[str, float] = {}
    for row in book["Tableau 2"].iter_rows(min_row=5, max_row=16, max_col=4,
                                           values_only=True):
        label, value = row[1], row[3]
        if label and isinstance(value, (int, float)):
            published[" ".join(str(label).split())] = float(value)

    needed = ("dernier dixième", "dont dernier centième", "dont dernier millième")
    missing = [key for key in needed if key not in published]
    if missing:
        raise TopTailError(
            f"n° 41 ne porte plus {missing} : le millésime a changé de forme et les "
            f"cibles disjointes ne peuvent pas être dérivées.")

    decile, centieme, millieme = (published[key] for key in needed)
    targets = {label: published[label] for label in published
               if label.endswith("dixième") and not label.startswith("dernier")}
    # Weight shares: the decile spans 10 %, the centième 1 %, the millième 0,1 %.
    targets["99,9–100 %"] = millieme
    targets["99–99,9 %"] = (centieme * 0.010 - millieme * 0.001) / 0.009
    targets["90–99 %"] = (decile * 0.100 - centieme * 0.010) / 0.090
    return targets


def band_means(per_part: Any, weights: Any) -> dict[str, float]:
    """Weighted mean RFR per part in each disjoint band, and the band memberships."""
    import numpy as np

    order = np.argsort(per_part)
    ordered, ordered_weights = per_part[order], weights[order]
    cumulative = np.cumsum(ordered_weights)
    total = cumulative[-1]
    means: dict[str, float] = {}
    for label, low, high in BANDS:
        mask = (cumulative > low * total) & (cumulative <= high * total)
        if mask.any() and ordered_weights[mask].sum() > 0:
            means[label] = float((ordered[mask] * ordered_weights[mask]).sum()
                                 / ordered_weights[mask].sum())
    return means


def factors(per_part: Any, weights: Any,
            targets: dict[str, float] | None = None) -> tuple[Any, dict[str, float]]:
    """One multiplier per foyer, in the ORIGINAL foyer order.

    Returned unsorted deliberately: the caller holds a frame keyed by `foyer_id`, and a
    silently re-ordered array is the kind of mistake that produces a plausible population
    nobody can trace.
    """
    import numpy as np

    targets = targets if targets is not None else published_targets()
    order = np.argsort(per_part)
    cumulative = np.cumsum(weights[order])
    total = cumulative[-1]

    out = np.ones(len(per_part), dtype=np.float64)
    applied: dict[str, float] = {}
    for label, low, high in BANDS:
        if label not in targets:
            continue
        mask = (cumulative > low * total) & (cumulative <= high * total)
        if not mask.any() or weights[order][mask].sum() == 0:
            continue
        current = float((per_part[order][mask] * weights[order][mask]).sum()
                        / weights[order][mask].sum())
        if current <= 0:
            # A band whose mean RFR is zero or negative cannot be scaled onto a positive
            # target: no multiplier reaches it. Left at 1.0 and reported, rather than
            # divided by and turned into an infinity that propagates silently.
            continue
        factor = targets[label] / current
        low_bound, high_bound = FACTOR_BOUNDS
        if not low_bound <= factor <= high_bound:
            raise TopTailError(
                f"{label} : facteur {factor:.2f} hors de [{low_bound}, {high_bound}]. "
                f"Le gate a mesuré ×0,92 à ×2,80 ; au-delà, ce n'est plus un recalage, "
                f"c'est une autre population, et il vaut mieux s'arrêter que réécrire "
                f"des revenus en silence.")
        out[order[mask]] = factor
        applied[label] = factor
    return out, applied


def apply(frame: Any, foyer_ids: Any, per_foyer: Any,
          band_factors: dict[str, float] | None = None) -> tuple[Any, RakeResult]:
    """Scale the frame's money columns by each foyer's factor. Rows and weights untouched.

    **Only money moves.** Household structure, ages, weights and identities are left
    exactly as they are, for the same reason `uprating` leaves them alone: a population
    whose rows moved would make every per-foyer trajectory meaningless, and the rake is a
    level correction, not a redraw.
    """
    import numpy as np
    import polars as pl

    missing = [column for column in SCALED if column not in frame.columns]
    if missing:
        raise TopTailError(
            f"colonnes absentes de la population : {missing}. Recaler une population dont "
            f"il manque une colonne monétaire la déformerait en silence.")

    lookup = dict(zip(list(foyer_ids), [float(x) for x in per_foyer], strict=True))
    factor_column = np.array([lookup.get(f, 1.0) for f in frame["foyer_id"].to_list()])

    before = sum(float((frame[column] * frame["weight"]).sum()) for column in SCALED)
    raked = frame.with_columns(
        [(pl.col(column) * pl.Series("_f", factor_column)).alias(column)
         for column in SCALED])
    after = sum(float((raked[column] * raked["weight"]).sum()) for column in SCALED)

    moved_mask = np.abs(factor_column - 1.0) > 1e-3
    moved = float(frame["weight"].to_numpy()[moved_mask].sum())

    return raked, RakeResult(
        factors=per_foyer, band_factors=dict(band_factors or {}),
        total_before_eur=before, total_after_eur=after, foyers_moved=moved)


def residuals(per_part: Any, weights: Any,
              targets: dict[str, float] | None = None) -> dict[str, float]:
    """What the rake did NOT achieve, band by band, as a relative residual.

    Exists because artefact 2 is real: fractile membership is fixed before scaling, and
    scaling moves foyers across the boundaries. The raked population therefore lands NEAR
    its targets rather than on them, and the honest thing is to publish the miss rather
    than to iterate until a number looks tidy.
    """
    targets = targets if targets is not None else published_targets()
    means = band_means(per_part, weights)
    return {label: means[label] / targets[label] - 1
            for label in targets if label in means and targets[label] != 0}
