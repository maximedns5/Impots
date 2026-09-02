"""Is this reform's yield concentrated in a narrow wage band? (D-046)

Metadata about a mechanical result, never a change to it.

The backtest suite measured why this matters. The barème indexation overshoots its
published cost by 10 %; the 2025 allègements step, which moves two **cliffs**,
overshoots by 107 %. Same population, same engine — the difference is that a cliff's
yield comes entirely from the households sitting between the old ceiling and the new
one, so it is proportional to the density in a narrow band and to nothing else. That
density is the least reliable thing in a synthetic population (D-015).

So the flag answers one question per reform: **how much of what this reform moves
comes from households close to one of its own thresholds?** Above a declared share,
the answer carries the D-015 caveat wherever the number is shown. It says nothing
about the direction of the error and does not adjust anything — it points at the part
of the distribution the result is resting on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

#: Half-width of the window around a threshold, as a fraction of the threshold.
#:
#: 15 % is set from the instrument that motivated the flag rather than from taste: the
#: 2025 step moved the maladie ceiling from about 2.5 to 2.25 SMIC, an 11 % move, and a
#: window narrower than the move itself would miss the very households the measure
#: acts on. Wide enough to contain a real cliff step, narrow enough that a reform
#: touching the whole distribution does not land inside it everywhere.
WINDOW = 0.15

#: Share of the reform's absolute movement that must come from inside those windows
#: before the caveat appears.
#:
#: A half. Below it a reform is broad-based and its total does not hinge on the
#: density anywhere in particular; above it the total is mostly one band's population,
#: and the level should be read as provisional until real incomes land.
SHARE = 0.50


@dataclass
class NarrowBand:
    share: float
    """Fraction of the reform's absolute movement coming from within a window."""
    thresholds: list[float] = field(default_factory=list)
    flagged: bool = False
    window: float = WINDOW
    share_threshold: float = SHARE

    @property
    def caveat(self) -> str:
        if not self.flagged:
            return ""
        return (
            f"Le rendement de cette réforme tient à une bande de salaires étroite : "
            f"{self.share:.0%} de ce qu'elle déplace vient de ménages situés à moins "
            f"de {self.window:.0%} d'un de ses propres seuils. C'est précisément là "
            f"que la population de synthèse est la moins fiable (D-015) — les "
            f"rétrotests mesurent un dépassement de 107 % sur un dispositif à seuil "
            f"contre 10 % sur un barème progressif. Lisez le niveau comme surestimé "
            f"tant que la population ne porte pas de revenus observés."
        )


def household_thresholds(reform: Any, smic_annual: float) -> list[float]:
    """The reform's own thresholds, as annual income levels.

    Only knobs that *have* a threshold contribute. A rate change with no threshold of
    its own — a CSG rate, the décote rate — moves everyone it touches proportionally
    and cannot concentrate a yield in a band, so it adds nothing here and correctly
    leaves the share at zero.
    """
    if reform is None:
        return []
    spec = reform.model_dump(exclude_none=True)
    thresholds: list[float] = []

    for bracket in spec.get("ir_bareme") or []:
        value = float(bracket["threshold"] if isinstance(bracket, dict) else bracket.threshold)
        if value > 0:
            thresholds.append(value)

    for knob in ("decote_seuil_celib", "decote_seuil_couple", "plafond_qf_demi_part"):
        if spec.get(knob):
            thresholds.append(float(spec[knob]))

    # Plafonds are in multiples of the SMIC, so they become wage levels here.
    for knob in ("allegement_general_plafond", "bandeau_maladie_plafond",
                 "bandeau_famille_plafond"):
        if spec.get(knob):
            thresholds.append(float(spec[knob]) * smic_annual)

    return sorted(set(thresholds))


def measure(
    income: np.ndarray,
    movement: np.ndarray,
    weights: np.ndarray,
    thresholds: list[float],
    *,
    window: float = WINDOW,
    share_threshold: float = SHARE,
) -> NarrowBand:
    """Share of a reform's absolute movement coming from within a window.

    `movement` is per household and signed; its absolute value is used, because a
    reform whose winners and losers cancel still rests on the density where they sit.
    """
    if not thresholds or not len(income) or weights.sum() <= 0:
        return NarrowBand(share=0.0, thresholds=thresholds, flagged=False,
                          window=window, share_threshold=share_threshold)

    weighted = np.abs(movement) * weights
    total = float(weighted.sum())
    if total <= 0:
        return NarrowBand(share=0.0, thresholds=thresholds, flagged=False,
                          window=window, share_threshold=share_threshold)

    inside = np.zeros(len(income), dtype=bool)
    for threshold in thresholds:
        if threshold > 0:
            inside |= np.abs(income - threshold) <= window * threshold

    share = float(weighted[inside].sum() / total)
    return NarrowBand(
        share=share, thresholds=thresholds, flagged=share > share_threshold,
        window=window, share_threshold=share_threshold,
    )
