"""Phase 9 M2 §2 — the coefficients θ, each between 0 and 1.

Every open channel gets a θ that places its parameter inside its PUBLISHED range, through
the published centre:

    p(θ) = bas + 2θ (centre − bas)             for θ ≤ 1/2
    p(θ) = centre + (2θ − 1)(haut − centre)    for θ ≥ 1/2

θ = 0 is the low end, θ = 1/2 the published centre, θ = 1 the high end — where « low » and
« high » are read in the row's declared direction, so that θ = 1 is everywhere the
STRONGEST response of the economy (the row's `theta.un`, D-217). θ = 0 is therefore not
« no effect »: it is the weakest effect the literature supports.

Passing through the centre is deliberate, against the linear p = bas + θ (haut − bas) the
report first wrote: for `eti_all` (0,01 · 0,02 · 0,02) the linear form would put θ = 1/2
on 0,015, a value no specification of the paper reports, where 0,02 is stable across six.

TWO CLASSES OF SOURCE. A behavioural row publishes bounds; θ reads them as they are. The
macro multiplier publishes a centre (Mésange) and a cross-study dispersion (IMK); θ reads
centre ∓ ONE published standard deviation, never the triangular draw’s ± sd·√6, which is a
shape convention (D-059). It inherits that dispersion's scope problem — countries,
horizons and methods pooled — and can put a multiplier below zero at θ = 0, as the fan
already does.

WHAT θ IS NOT. Not a probability: the box θ ∈ [0, 1] is not a confidence interval, and the
probability vocabulary of `dette.path.PROBABILITY_WORDS` stays forbidden. Not chosen by the
tool: there is no default θ anywhere, and the explorer never searches over it.

THE PINNED VIEW. `pinned(store, theta)` returns a store whose open rows are replaced by
their value at θ, with low = high = central. `Parameter.draw` already returns a constant
for such a row, so every channel runs at θ WITHOUT KNOWING IT, and the Monte Carlo band of
Phase 3 keeps its code path untouched.
"""

from __future__ import annotations

import dataclasses
import itertools
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from impots.behavioural.store import Parameter, Store


class ThetaError(ValueError):
    """A θ was asked for in a way that would mislead."""


def _check(value: float, what: str) -> float:
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ThetaError(
            f"θ = {value} pour {what}, hors de [0 ; 1] : θ place un effet DANS sa "
            f"fourchette publiée, et au-delà il inventerait une valeur que personne n'a "
            f"publiée. Refusé plutôt qu'écrêté.")
    return value


def value_at(parameter: Parameter, theta: float) -> float:
    """The row's value at θ, through its published centre, in its declared direction."""
    theta = _check(theta, parameter.key)
    if not parameter.is_open:
        return parameter.central
    if parameter.theta_one not in ("low", "high"):
        raise ThetaError(f"{parameter.key} : sens de θ non déclaré (D-217)")
    t = theta if parameter.theta_one == "high" else 1.0 - theta
    low, centre, high = parameter.low, parameter.central, parameter.high
    # Both halves written FROM the centre, so that θ = 1/2 returns the published figure
    # to the last digit (guard 5) rather than `low + (centre − low)` up to a rounding.
    if t <= 0.5:
        return centre - (1.0 - 2.0 * t) * (centre - low)
    return centre + (2.0 * t - 1.0) * (high - centre)


def multiplier_at(centre: float, sd: float, theta: float) -> float:
    """A multiplier at θ: centre ∓ one published cross-study standard deviation."""
    theta = _check(theta, "le multiplicateur")
    if sd <= 0:
        raise ThetaError("un multiplicateur sans dispersion publiée n'a pas de fourchette "
                         "à parcourir : θ n'a rien à placer")
    return centre + (2.0 * theta - 1.0) * sd


@dataclass(frozen=True)
class Theta:
    """One θ per open row, or a common θ for all of them. NEVER a default.

    A row named in `rows` takes its own value; every other row takes `common`; a row with
    neither is refused when asked for, rather than given 1/2 in silence.
    """

    rows: Mapping[str, float] = field(default_factory=dict)
    common: float | None = None

    def __post_init__(self) -> None:
        if self.common is None and not self.rows:
            raise ThetaError(
                "aucun θ : ni θ commun, ni θ par canal. Aucun défaut n'est appliqué — "
                "θ est l'hypothèse de l'utilisateur, jamais celle de l'outil.")
        if self.common is not None:
            _check(self.common, "θ commun")
        for key, value in self.rows.items():
            _check(value, key)

    def for_row(self, key: str) -> float:
        if key in self.rows:
            return float(self.rows[key])
        if self.common is not None:
            return float(self.common)
        raise ThetaError(f"aucun θ pour « {key} » et aucun θ commun : il n'est pas "
                         f"remplacé par 1/2, il est refusé")

    def check_known(self, store: Store) -> None:
        """A θ named for a row the store does not hold is a typo that would silently
        apply the common θ instead — refused by name (the D-092 lesson: refuse what is
        not recognised)."""
        unknown = sorted(set(self.rows) - {k for k, p in store.parameters.items()
                                           if p.is_open})
        if unknown:
            raise ThetaError(f"θ pour des lignes inconnues ou fixes : {unknown}")

    def table(self, store: Store) -> dict[str, float]:
        """Every open row with the θ it runs at — what a result must display (§2.4, 2)."""
        return {k: self.for_row(k) for k, p in sorted(store.parameters.items()) if p.is_open}


def pinned(store: Store, theta: Theta) -> Store:
    """The store with every open row fixed at its value at θ (see the module docstring)."""
    theta.check_known(store)
    parameters = {}
    for key, parameter in store.parameters.items():
        if parameter.is_open:
            value = value_at(parameter, theta.for_row(key))
            parameter = dataclasses.replace(parameter, central=value, low=value, high=value)
        parameters[key] = parameter
    return Store(parameters=parameters, thresholds=dict(store.thresholds),
                 rejected=dict(store.rejected))


def corners(keys: Iterable[str], base: Theta) -> list[Theta]:
    """The 2^K corners of the θ box over `keys`: each key at 0 or at 1, every other row at
    the θ `base` gives it. A corner moves only what the reform touches."""
    keys = sorted(keys)
    return [Theta(rows={**base.rows, **dict(zip(keys, combo, strict=True))},
                  common=base.common)
            for combo in itertools.product((0.0, 1.0), repeat=len(keys))]
