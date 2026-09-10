"""Phase 7 A0 — the accuracy budget: which declared uncertainty source actually moves a price.

**This module ranks error sources so that effort follows variance rather than intuition.**
Phase 7's levers are taken in the order this file produces, and a lever it ranks low is
deprioritised *with its score recorded* — refusing work is a result here, exactly as
refusing a chiffrage was in F1. That makes this measurement infrastructure of the most
load-bearing kind: a wrong ranking does not produce a wrong number, it produces a wasted
phase. It therefore ships with the same teeth as model code, and its kill test exists
before any real case is priced.

WHAT A0 MAY AND MAY NOT COMPARE, WHICH IS THE WHOLE DESIGN.

The sources this phase names do not have the same epistemic status, and the single worst
thing this module could do is put them on one axis without saying so. Three classes:

* `SAMPLED` — a real, named, samplable law exists, so variance is estimable and a share of
  output variance is a measurement. Today this is exactly the behavioural store's
  `Parameter.draw` (triangular / uniform / normal) and the firm-side placement seed.
* `SWING` — only BOUNDS exist: two endpoints and nothing between them. A swing can be
  measured honestly, but converting it to a variance share requires assuming a shape
  across the interval, and that assumption is a convention, not a finding. `VARIANCE_OF_A
  _RANGE` below is that convention, isolated in one named constant so it can be argued
  with rather than buried.
* `UNMEASURED` — the spec declares the source and the repository has neither a law nor
  bounds for it. It is reported as UNMEASURED and given **no share at all**. It is never
  silently dropped: a source missing from a budget reads as a source that does not matter.

**A share is only ever computed within a class.** Mixing them yields `share=None` and a
stated refusal, because a `SWING` converted through an assumed shape and a `SAMPLED`
variance are not the same kind of number, and a ranking that pretended otherwise would
send the campaign at whichever source happened to have the most generous convention.

THE TRAP THIS MODULE WAS BUILT AROUND, AND WHY THE UPRATING PAIR IS NOT AN INTERVAL.

`trajectoires.YearUncertainty.uprating_eur` is `(frozen, aged)` and its width is quoted
everywhere as «vieillissement ±». It is honest in its own context and it is NOT an
uprating uncertainty. Read `population/cli.py`: `frozen = price(frame, year)` prices the
RAW 2024 frame — incomes that never grew at all — and `aged` prices the uprated one. The
width is therefore the value of **doing the uprating versus not doing it**, not the spread
between a plausible high and a plausible low rate. Nobody's uncertainty about wage growth
includes «zero for five years».

Feeding that width in as the uprating source's spread would have handed A0 a large number
attributable to the wrong thing, and it would very likely have ranked near the top — which
is to say it would have aimed the entire accuracy campaign at a quantity that is not an
error. This is standing question four, «what is this number the difference of, exactly?»,
arriving in the one place where getting it wrong costs a phase rather than a figure.

So `uprating` is measured as a genuine two-sided swing around the DECLARED hypothesis, and
the endpoints are the caller's to state and to source. This project does not forecast wages
or prices (Phase 4's refusals bind here as everywhere); it prices «if wages move by X». An
uprating swing with no sourced endpoints is `UNMEASURED`, not a guess.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

#: How a source's spread is known. See the module docstring: shares are computed WITHIN a
#: class and never across, because these are not the same kind of number.
Method = Literal["sampled", "swing", "unmeasured"]

METHODS: tuple[Method, ...] = ("sampled", "swing", "unmeasured")

#: The convention that turns a pair of bounds into a variance, so several SWING sources can
#: be ranked against each other. A range [a, b] under a uniform assumption has variance
#: (b - a)^2 / 12.
#:
#: **This is a convention, not a measurement**, and it is named rather than inlined so that
#: the report can say so and a reader can disagree with one number instead of auditing an
#: expression. It is deliberately used ONLY to rank swings among themselves: a swing's
#: pseudo-variance is never compared with a sampled variance, because the uniform
#: assumption is doing work in one and nothing in the other.
VARIANCE_OF_A_RANGE = 12.0


class AccuracyError(RuntimeError):
    """A budget was asked for in a way that would produce a misleading ranking."""


@dataclass(frozen=True)
class Source:
    """One declared uncertainty source, and how this repository actually knows it.

    `evaluate` receives a draw index (for `sampled`) or an endpoint name (for `swing`) and
    returns the priced output in euros. It is supplied by the caller rather than looked up
    here so that a reference reform's pricing chain — household, firm, or trajectory —
    stays where it lives and this module never grows a second copy of it.
    """

    key: str
    label: str
    method: Method
    note: str = ""
    #: `sampled`: a callable taking an integer seed and returning euros.
    sample: Callable[[int], float] | None = None
    #: `swing`: a callable taking an endpoint label and returning euros, plus the two
    #: endpoint labels. Two-sided and around the declared central case — never a toggle
    #: against a counterfactual in which the mechanism is simply switched off.
    swing: Callable[[str], float] | None = None
    endpoints: tuple[str, str] | None = None
    #: Why the source is unmeasured, when it is. Mandatory in that case: an UNMEASURED row
    #: with no reason is indistinguishable from an oversight.
    unmeasured_reason: str = ""

    def __post_init__(self) -> None:
        if self.method not in METHODS:
            raise AccuracyError(f"méthode inconnue : {self.method!r}")
        if self.method == "sampled" and self.sample is None:
            raise AccuracyError(
                f"{self.key} : déclarée « sampled » sans échantillonneur. Une source "
                f"sampled DOIT porter une loi tirable — c'est ce qui la distingue d'un "
                f"encadrement, et c'est la seule raison pour laquelle sa part de variance "
                f"est une mesure plutôt qu'une convention.")
        if self.method == "swing" and (self.swing is None or self.endpoints is None):
            raise AccuracyError(
                f"{self.key} : déclarée « swing » sans fonction ou sans bornes nommées. "
                f"Les deux bornes sont NOMMÉES parce qu'un balayage doit dire de quoi il "
                f"est la différence — la paire vieillie/gelée des trajectoires est un "
                f"contre-factuel « sans vieillissement », pas une borne basse.")
        if self.method == "unmeasured" and not self.unmeasured_reason.strip():
            raise AccuracyError(
                f"{self.key} : UNMEASURED sans raison. Une source absente d'un budget se "
                f"lit « elle ne compte pas » ; c'est précisément l'erreur à ne pas faire.")


@dataclass(frozen=True)
class Contribution:
    """What one source contributed on one reference reform."""

    source: str
    label: str
    method: Method
    #: Estimated output variance in euros squared. None for UNMEASURED.
    variance: float | None
    #: Full width of the swing, in euros. Only for `swing`; the honest headline for a
    #: bounded source, since it needs no shape assumption at all.
    width_eur: float | None = None
    #: Share of the variance of the sources measured BY THE SAME METHOD. Never across.
    share: float | None = None
    note: str = ""

    @property
    def sigma_eur(self) -> float | None:
        """The spread as a standard deviation — the readable form of a variance."""
        return None if self.variance is None else math.sqrt(self.variance)


@dataclass(frozen=True)
class CaseBudget:
    """The attribution for one reference reform."""

    case: str
    label: str
    central_eur: float
    contributions: tuple[Contribution, ...]
    draws: int

    def ranked(self, method: Method) -> tuple[Contribution, ...]:
        """Contributions of one method, largest variance first.

        Restricted to a single method BY CONSTRUCTION rather than by convention, because a
        ranking that mixed a sampled variance with a swing's pseudo-variance would be
        ranking the conventions, not the sources.
        """
        rows = [c for c in self.contributions
                if c.method == method and c.variance is not None]
        return tuple(sorted(rows, key=lambda c: c.variance or 0.0, reverse=True))

    def dominant(self, method: Method = "sampled") -> Contribution | None:
        rows = self.ranked(method)
        return rows[0] if rows else None

    @property
    def unmeasured(self) -> tuple[Contribution, ...]:
        return tuple(c for c in self.contributions if c.method == "unmeasured")


@dataclass
class Budget:
    """The whole A0 attribution: every reference reform, every source."""

    cases: list[CaseBudget] = field(default_factory=list)
    seed: int = 20260910
    notes: list[str] = field(default_factory=list)

    def case(self, name: str) -> CaseBudget:
        for entry in self.cases:
            if entry.case == name:
                return entry
        raise AccuracyError(f"cas inconnu : {name}")


def _variance(values: Sequence[float]) -> float:
    """Sample variance, ddof=1. Refuses a single draw rather than returning zero.

    A one-draw variance of 0.0 would enter a ranking as «this source does not matter»,
    which is the opposite of what one draw licenses.
    """
    n = len(values)
    if n < 2:
        raise AccuracyError(
            f"variance sur {n} tirage(s) : un tirage unique donnerait 0,0, qui se lirait "
            f"« cette source ne bouge rien » alors qu'il ne dit rien du tout.")
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / (n - 1)


def measure(source: Source, *, draws: int, seed: int) -> Contribution:
    """Measure one source on one already-fixed reference reform.

    The reform is a FIXED DESIGN POINT here, never a source: reform knobs carry no
    distribution anywhere in this repository, and `ReformSpec`'s bounds are input
    validation — the schema says so itself — not a credible range for a legislated
    parameter. Treating a knob's validation bounds as an uncertainty would invent an error
    bar for a number the legislator states exactly.
    """
    if source.method == "unmeasured":
        return Contribution(source=source.key, label=source.label, method="unmeasured",
                            variance=None, note=source.unmeasured_reason)

    if source.method == "sampled":
        assert source.sample is not None  # guarded in __post_init__
        values = [source.sample(seed + i) for i in range(draws)]
        return Contribution(source=source.key, label=source.label, method="sampled",
                            variance=_variance(values), note=source.note)

    assert source.swing is not None and source.endpoints is not None
    low_name, high_name = source.endpoints
    low, high = source.swing(low_name), source.swing(high_name)
    width = abs(high - low)
    return Contribution(source=source.key, label=source.label, method="swing",
                        variance=(width ** 2) / VARIANCE_OF_A_RANGE, width_eur=width,
                        note=source.note)


def budget_for(case: str, label: str, central_eur: float, sources: Sequence[Source], *,
               draws: int = 64, seed: int = 20260910) -> CaseBudget:
    """Attribute one reference reform's output variance across its declared sources."""
    if not sources:
        raise AccuracyError(
            f"{case} : aucune source déclarée. Un budget vide se lit « rien n'est "
            f"incertain », ce qu'aucun chiffrage de ce projet ne prétend.")
    seen = {s.key for s in sources}
    if len(seen) != len(sources):
        raise AccuracyError(f"{case} : clés de source dupliquées")

    rows = [measure(s, draws=draws, seed=seed) for s in sources]

    # Shares WITHIN a method, never across. See the module docstring.
    scored: list[Contribution] = []
    for method in METHODS:
        family = [c for c in rows if c.method == method and c.variance is not None]
        total = sum(c.variance or 0.0 for c in family)
        for c in family:
            share = None if total <= 0 else (c.variance or 0.0) / total
            scored.append(Contribution(
                source=c.source, label=c.label, method=c.method, variance=c.variance,
                width_eur=c.width_eur, share=share, note=c.note))
    scored.extend(c for c in rows if c.variance is None)

    order = {s.key: i for i, s in enumerate(sources)}
    scored.sort(key=lambda c: order[c.source])
    return CaseBudget(case=case, label=label, central_eur=central_eur,
                      contributions=tuple(scored), draws=draws)


def _avalanche(seed: int) -> float:
    """A seed mixed to a well-scattered value in [0, 1) — splitmix64's finaliser.

    Used instead of `numpy` so the synthetic case has no dependency on the sampling stack
    it exists to check, and instead of a linear congruence so that CONSECUTIVE seeds
    scatter: `budget_for` evaluates a sampler at seed, seed+1, seed+2, and a mixer without
    avalanche would hand it a ramp.
    """
    mask = 0xFFFFFFFFFFFFFFFF
    x = (seed + 0x9E3779B97F4A7C15) & mask
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & mask
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & mask
    x ^= x >> 31
    return x / 2 ** 64


def synthetic_case(dominant: str = "loud", *, scale: float = 1.0) -> list[Source]:
    """A case whose answer is known before it is measured — A0's kill test.

    THE POINT OF THIS FUNCTION IS THAT ITS ANSWER DOES NOT COME FROM THE CODE UNDER TEST.
    Three sampled sources with hand-chosen spreads standing in a 100 : 10 : 1 ratio, so the
    ranking is arithmetic anyone can check on paper, not something `budget_for` computes
    and then agrees with itself about. That is the D-044 shape this project has now walked
    into five times, and a budget derived from the thing it ranks would be the sixth.

    `dominant` names which source is loud so a test can move the answer and watch the
    ranking follow — a ranker that returns a fixed order passes a single-arrangement test
    and fails this one.
    """
    spreads = {"loud": 1.0, "middle": 0.1, "quiet": 0.01}
    if dominant not in spreads:
        raise AccuracyError(f"source inconnue : {dominant}")
    # Rotate the spreads so the named source carries the largest one.
    names = list(spreads)
    factors = [1.0, 0.1, 0.01]
    shift = names.index(dominant)
    assigned = {names[(i + shift) % len(names)]: factors[i] for i in range(len(names))}

    def make(name: str) -> Source:
        amplitude = assigned[name] * scale * 1e9

        def sample(seed: int, _a: float = amplitude) -> float:
            # Deterministic, seed-driven, no RNG import and no hidden state, so a failing
            # test replays exactly from its seed.
            #
            # THE FIRST VERSION OF THIS WAS `(seed * k) % p`, WHICH IS NOT A DRAW — it is an
            # arithmetic progression, and `budget_for` evaluates it at seed, seed+1, ... So
            # moving the base seed only TRANSLATED the window, and variance is invariant
            # under translation: two different seeds returned variances equal to the last
            # bit. `test_a_different_seed_moves_the_variances` caught it. A ramp would still
            # have passed every ranking test here, because the 100 : 10 : 1 amplitudes
            # survive it — which is precisely why the determinism test had to exist too.
            return 10e9 + _a * (_avalanche(seed) - 0.5)

        return Source(key=name, label=f"source {name}", method="sampled", sample=sample,
                      note=f"amplitude {amplitude:.3e}")

    return [make(n) for n in names]
