"""The elasticity store (PHASE3_SPEC §2).

Not the engine's dated-law tree, and the difference is the point: a rate in
`impots/*/parameters/` is a *statute*, true because it was voted. A number here is
an *estimate*, true only to the extent some identification strategy supports it, and
only over the range of variation that strategy actually observed. So every entry
carries three things a statute never needs — a range to sample, a support bound
saying how far it may be extrapolated, and a verifier's verdict.

**The loader refuses a row whose verdict is null.** That is the one hard rule here.
The project has measured what happens without it: six statistics through research
agents in Phase 1 gave six scope problems, and Phase 2's firm-data agent returned
`WRONG` with fifteen. An unverified elasticity that loads is a band that looks
exactly like a verified one, which is this phase's characteristic failure.

A row that dies under verification is **removed**, not softened. Its channel then
reports narrower evidence, or none — never an international guess inherited quietly
to keep a number on the screen.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import numpy as np
import yaml

PARAMETERS = Path(__file__).resolve().parent / "parameters"

Distribution = Literal["triangular", "uniform", "normal"]
Confidence = Literal["high", "medium", "low"]
#: Which end of the published range θ = 1 designates (Phase 9, D-217): always the
#: STRONGEST response of the economy. Declared per row, never inferred from the sign —
#: the SMIC employment elasticity runs −0.52 to −0.31 and its strongest response is the
#: low end.
ThetaEnd = Literal["low", "high"]

#: Verdicts a verifier may return. Only these two let a row load: `CONFIRMED` and
#: `SCOPE_PROBLEM` — the latter because Phase 2 measured that a scope problem means
#: the citations need repair while the values hold, which is a documentation defect,
#: not a wrong number. `WRONG` and a null verdict both refuse.
LOADABLE_VERDICTS = frozenset({"CONFIRMED", "SCOPE_PROBLEM"})


class UnverifiedParameter(RuntimeError):
    """A parameter tried to load without a verifier verdict."""


class MisrankedRow(UnverifiedParameter):
    """A row broke PHASE11_SPEC §2's order of sources: an international row without its
    rank, countries or years, or a lower rank where a higher one is loaded for the same
    channel, with no exception declared (D-243, guards 1 and 2 of §10)."""


class UndeclaredTheta(UnverifiedParameter):
    """An open row tried to load without saying which end θ = 1 designates.

    A subclass of `UnverifiedParameter` on purpose: both are a row that cannot be read
    without a statement its author did not make, and both refuse in the same place."""


@dataclass(frozen=True)
class Support:
    """How far this estimate may be carried before it stops being evidence.

    `max_variation_graded_in_support` is in the units of the elasticity's *own*
    driver — for an ETI, the largest change in the net-of-tax marginal rate the
    identifying reforms actually moved. It is the Lucas guardrail's data, and §4
    enforces it in code rather than trusting a reader to remember it.
    """

    estimated_on: str
    max_variation_graded_in_support: float | None = None

    @property
    def is_gradeable(self) -> bool:
        """False when the literature does not support a bound. A channel resting on
        such a row cannot be graded `in-support`, ever — an ungradeable support is
        not a permissive one."""
        return self.max_variation_graded_in_support is not None


@dataclass(frozen=True)
class Source:
    citation: str
    url: str = ""
    vintage: str = ""
    quote: str = ""


@dataclass(frozen=True)
class Verifier:
    """The adversarial pass's verdict, recorded where the value is."""

    verdict: str | None = None
    date: str = ""
    ref: str = ""
    note: str = ""


#: PHASE11_SPEC §2, condition 1: French first, then several countries France among
#: them, then an international meta-analysis, last another country.
RANKS = {1: "estimation française", 2: "plusieurs pays dont la France",
         3: "méta-analyse internationale", 4: "un autre pays"}


@dataclass(frozen=True)
class Rank:
    """Where a row stands in the order of sources (D-243). A row without this block is
    one the phase 9 rule loaded — French, or a model centred on France."""

    level: int
    channel: str
    """What the row measures, so that two rows of one channel can be ranked together."""
    countries: str = ""
    years: str = ""
    why: str = ""
    """Why the rank above is missing — condition 1 makes the row write it."""
    exception: str = ""
    """A declared exception to condition 1, with its D-entry: the rank above exists and
    is set aside, and the row says why."""


@dataclass(frozen=True)
class Parameter:
    key: str
    central: float
    low: float
    high: float
    applies_to: str
    support: Support
    source: Source
    verifier: Verifier
    confidence: Confidence = "medium"
    distribution: Distribution = "triangular"
    responds_to_knobs: tuple[str, ...] = ()
    note: str = ""
    theta_one: ThetaEnd | None = None
    """The end θ = 1 designates. None only for a FIXED row (low = high), which carries
    no θ; the loader refuses an open row without it (D-217)."""
    theta_reason: str = ""
    rank: Rank | None = None

    @property
    def is_open(self) -> bool:
        """A row with a range: θ can move it. A fixed row is shown as fixed, not as
        θ-insensitive by accident."""
        return self.low != self.high

    def __post_init__(self) -> None:
        if not self.low <= self.central <= self.high:
            raise ValueError(
                f"{self.key}: central {self.central} is outside [{self.low}, {self.high}]"
            )

    def claims(self, knob: str) -> bool:
        """Whether this parameter responds to a reform knob. Patterns allowed, because
        `decote_seuil_celib` and `decote_taux` are one instrument to an elasticity."""
        return any(fnmatch.fnmatch(knob, pattern) for pattern in self.responds_to_knobs)

    def draw(self, rng: np.random.Generator, size: int) -> np.ndarray:
        """Sample the parameter. Never the central value alone — the point of the
        store is that the band, not the point, is the answer."""
        if self.low == self.high:
            return np.full(size, self.central)
        if self.distribution == "uniform":
            return rng.uniform(self.low, self.high, size)
        if self.distribution == "normal":
            # Interpret [low, high] as a 90 % interval, which is how published
            # confidence intervals arrive; 1.645 is the one-sided 95 % z.
            return rng.normal(self.central, (self.high - self.low) / (2 * 1.645), size)
        return rng.triangular(self.low, self.central, self.high, size)


@dataclass
class Store:
    parameters: dict[str, Parameter] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    """Grading thresholds (§4). They live here rather than in code so that changing
    how strict the Lucas guardrail is, is a data change with a diff."""
    rejected: dict[str, str] = field(default_factory=dict)
    """Rows present in the tree but refused, and why. Kept so a channel can say
    'no usable evidence' with a reason instead of silently having fewer inputs."""

    def __getitem__(self, key: str) -> Parameter:
        return self.parameters[key]

    def __contains__(self, key: str) -> bool:
        return key in self.parameters

    def for_knob(self, knob: str) -> list[Parameter]:
        return [p for p in self.parameters.values() if p.claims(knob)]

    def vintage(self) -> str:
        """A fingerprint of what is loaded, reported alongside every band so a band
        can be traced to the evidence that produced it."""
        keys = ",".join(sorted(self.parameters))
        return f"{len(self.parameters)} rows [{keys}]"


def _parse(key: str, raw: dict[str, Any]) -> Parameter:
    value = raw.get("value") or {}
    support = raw.get("support") or {}
    source = raw.get("source") or {}
    verifier = raw.get("verifier") or {}
    return Parameter(
        key=key,
        central=float(value["central"]),
        low=float(value["low"]),
        high=float(value["high"]),
        distribution=value.get("distribution", "triangular"),
        applies_to=raw.get("applies_to", ""),
        responds_to_knobs=tuple(raw.get("responds_to_knobs") or ()),
        support=Support(
            estimated_on=support.get("estimated_on", ""),
            max_variation_graded_in_support=(
                None if support.get("max_variation_graded_in_support") is None
                else float(support["max_variation_graded_in_support"])
            ),
        ),
        source=Source(
            citation=source.get("citation", ""), url=source.get("url", ""),
            vintage=str(source.get("vintage", "")), quote=source.get("quote", ""),
        ),
        verifier=Verifier(
            verdict=verifier.get("verdict"), date=str(verifier.get("date") or ""),
            ref=verifier.get("ref", ""), note=verifier.get("note", ""),
        ),
        confidence=raw.get("confidence", "medium"),
        note=raw.get("note", ""),
        theta_one=(raw.get("theta") or {}).get("un"),
        theta_reason=str((raw.get("theta") or {}).get("raison") or "").strip(),
        rank=_rank(raw.get("rang")),
    )


def _rank(raw: dict[str, Any] | None) -> Rank | None:
    if raw is None:
        return None
    return Rank(level=int(raw.get("niveau", 0)), channel=str(raw.get("canal") or ""),
                countries=str(raw.get("pays") or "").strip(),
                years=str(raw.get("annees") or "").strip(),
                why=str(raw.get("pourquoi") or "").strip(),
                exception=str(raw.get("exception") or "").strip())


def _rank_problem(parameter: Parameter) -> str:
    """Why a row cannot stand at its declared rank, or '' when it can (§10, guard 1)."""
    rank = parameter.rank
    if rank is None:
        return ""
    if rank.level not in RANKS:
        return f"rang {rank.level} inconnu ; les rangs sont {RANKS}"
    if not rank.channel:
        return "rang sans canal : deux lignes d'un même canal ne pourraient se classer"
    if rank.level >= 2 and not (rank.countries and rank.years):
        return (f"ligne de rang {rank.level} ({RANKS[rank.level]}) sans les pays ou les "
                f"années de son échantillon : l'étiquette « international » les porte "
                f"(PHASE11_SPEC §2, condition 5)")
    if rank.level >= 2 and not (rank.why or rank.exception):
        return (f"ligne de rang {rank.level} sans dire pourquoi le rang au-dessus manque, "
                f"ni l'exception qui l'écarte (PHASE11_SPEC §2, condition 1)")
    return ""


def _outranked(parameters: dict[str, Parameter]) -> dict[str, str]:
    """Rows of a channel with a better-ranked row loaded, and no exception (guard 2)."""
    best: dict[str, int] = {}
    for parameter in parameters.values():
        if parameter.rank is not None:
            channel = parameter.rank.channel
            best[channel] = min(best.get(channel, parameter.rank.level),
                                parameter.rank.level)
    return {key: (f"rang {p.rank.level} alors qu'une ligne de rang "
                  f"{best[p.rank.channel]} est chargée pour le canal "
                  f"« {p.rank.channel} » : on ne descend d'un rang que si le précédent "
                  f"manque, ou par une exception déclarée (PHASE11_SPEC §2, condition 1)")
            for key, p in parameters.items()
            if p.rank is not None and p.rank.level > best[p.rank.channel]
            and not p.rank.exception}


def _theta_problem(parameter: Parameter) -> str:
    """Why an open row cannot be read under θ, or '' when it can (D-217)."""
    if not parameter.is_open:
        return ""
    if parameter.theta_one not in ("low", "high"):
        return (f"θ undeclared (theta.un = {parameter.theta_one!r}): an open row must say "
                f"which end of its range θ = 1 designates — the strongest response — "
                f"because the sign does not tell, and a default would be a guess")
    if not parameter.theta_reason:
        return "θ declared without its reason (theta.raison): the direction is a claim"
    return ""


def load(directory: Path | None = None, *, strict: bool = True) -> Store:
    """Load the store, refusing anything a verifier has not passed.

    `strict=False` records refusals in `Store.rejected` instead of raising. It exists
    for the report that lists what is missing and why — never for a band. Producing a
    number is always strict.
    """
    directory = directory or PARAMETERS
    store = Store()
    for path in sorted(directory.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        store.thresholds.update(document.get("thresholds") or {})
        # Rows a verifier killed stay in the file under `removed`, with the reason.
        # Deleting them outright would make a channel narrow with no visible cause;
        # keeping them here means the store itself records what was tried and refused.
        for key, reason in (document.get("removed") or {}).items():
            store.rejected[key] = str(reason)
        for key, raw in (document.get("parameters") or {}).items():
            parameter = _parse(key, raw)
            verdict = parameter.verifier.verdict
            if verdict not in LOADABLE_VERDICTS:
                reason = (
                    "no verifier verdict — an unverified elasticity produces a band "
                    "indistinguishable from a verified one"
                    if verdict is None
                    else f"verifier returned {verdict}"
                )
                if strict:
                    raise UnverifiedParameter(f"{key} ({path.name}): {reason}")
                store.rejected[key] = reason
                continue
            problem = _theta_problem(parameter)
            if problem:
                if strict:
                    raise UndeclaredTheta(f"{key} ({path.name}): {problem}")
                store.rejected[key] = problem
                continue
            problem = _rank_problem(parameter)
            if problem:
                if strict:
                    raise MisrankedRow(f"{key} ({path.name}): {problem}")
                store.rejected[key] = problem
                continue
            store.parameters[key] = parameter
    for key, problem in _outranked(store.parameters).items():
        if strict:
            raise MisrankedRow(f"{key}: {problem}")
        store.rejected[key] = problem
        del store.parameters[key]
    return store
