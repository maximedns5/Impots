"""The chiffrage backtest suite (PHASE3_SPEC §5).

Empty since 2026-08-28, and the one thing the roadmap has owed longest. Each case is
a historical PLF article whose *published mechanical* costing is on record: the
article, the figure, the ReformSpec that expresses it, and a declared tolerance.

**What this grades, and why it is worth having.** Official French costings are
mechanical by construction — FIPECO's own position is that behavioural responses are
"difficult, often impossible to measure". So this suite tests **L2**, the mechanical
engine, against the state's own arithmetic on historical law. That makes it entirely
independent of everything Phase 3 adds: no elasticity, no band and no grade touches
a chiffrage case. A behavioural bug cannot turn one green, and a mechanical bug
cannot hide behind one.

**A red case is a finding, never a number to tune away.** And the mechanical-before-
economic rule (D-029) binds here too: a miss gets a mechanical explanation attempt —
wrong vintage, a knob that does not express the article, a basis mismatch between
année pleine and première année — before anyone reaches for population realism.

Tolerances are declared per case rather than inherited. A case comparing a 2013
measure against a 2024 population is not owed the same latitude as one comparing a
2024 measure, and saying so per case is more honest than one global number.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

CASES = Path(__file__).resolve().parents[3] / "tests" / "chiffrages"

Scope = Literal["household", "firm"]
Sign = Literal["cost", "yield"]
Basis = Literal["annee-pleine", "premiere-annee", "unstated"]


class ChiffrageError(RuntimeError):
    """A case cannot be run as written."""


@dataclass(frozen=True)
class Published:
    """The state's own figure, and enough provenance to re-find it."""

    amount_eur: float
    sign: Sign
    basis: Basis
    document: str
    url: str
    page: str = ""
    quote: str = ""
    checked: str = ""

    @property
    def signed(self) -> float:
        """Positive = raises money for the state, negative = costs it.

        The published documents are inconsistent about this — some print a cost as a
        positive number under a "coût" heading — so the sign is carried explicitly
        rather than inferred, and getting it wrong would flip a case from green to
        red at twice the magnitude.
        """
        return -abs(self.amount_eur) if self.sign == "cost" else abs(self.amount_eur)


@dataclass(frozen=True)
class Case:
    key: str
    article: str
    year: int
    scope: Scope
    reform: dict[str, Any]
    published: Published
    tolerance: float
    tolerance_reason: str
    description: str = ""
    caveat: str = ""
    bound: Literal["two-sided", "lower"] = "two-sided"
    """`lower` when the simulator can express only PART of what the published figure
    costs, so the honest test is an inequality.

    The barème indexations are the case that forced this. Each article indexes the
    scale, the décote and the plafond du quotient familial — all expressible — but
    ALSO the 10 % déduction forfaitaire floors and ceilings, the abattement on
    pensions, and several specific QF caps, none of which this simulator exposes.
    Those are inside the published cost. So the expressible subset is a strict subset
    of what was costed, the simulated figure MUST land below it, and a symmetric
    window would have half its area in a region the case itself says should never be
    reached. Landing above the published figure is a finding, not a pass."""
    mirror: bool = False
    """The reform encodes the article's REVERSE.

    Needed more often than it looks. Where an article's end state is already the law
    the parameter tree carries, replaying it is a no-op against the baseline, so the
    case has to run the repeal instead — and the resulting delta then carries the
    opposite sign to the published figure. Declared per case rather than inferred,
    because a sign flipped by accident turns a green case red at twice the magnitude
    and a red one green."""
    expect_red: bool = False
    """Set when a case is known to miss and the miss is written up. It still runs and
    still reports its residual — this only stops a documented finding from failing
    CI, and every such case must carry its `caveat` explaining the miss."""

    def residual(self, simulated: float) -> float:
        published = self.published.signed
        if self.mirror:
            simulated = -simulated
        return (simulated - published) / abs(published) if published else float("nan")

    def magnitude_residual(self, simulated: float) -> float:
        """How much bigger the simulated effect is than the published one, in size.

        Distinct from `residual`, and the distinction is not pedantic: for a COST the
        published figure is negative, so a simulated value further below it is a
        *larger* cost — an overshoot — while the signed residual reads negative, which
        looks like an undershoot. A one-sided test written on the signed residual
        passes exactly the cases it should fail.
        """
        published = abs(self.published.signed)
        if self.mirror:
            simulated = -simulated
        return (abs(simulated) - published) / published if published else float("nan")

    def passes(self, simulated: float) -> bool:
        if self.bound == "lower":
            # The expressible instruments are a strict subset of what was costed, so
            # the simulated effect must be SMALLER — and not smaller by more than the
            # tolerance. Exceeding the published figure means something is wrong,
            # however close the number looks.
            return -self.tolerance <= self.magnitude_residual(simulated) <= 0.0
        return abs(self.residual(simulated)) <= self.tolerance


def _case(path: Path, raw: dict[str, Any]) -> Case:
    published = raw.get("published") or {}
    source = published.get("source") or {}
    missing = [k for k in ("article", "year", "scope", "reform", "tolerance") if k not in raw]
    if missing:
        raise ChiffrageError(f"{path.name} is missing {missing}")
    if not source.get("url"):
        raise ChiffrageError(
            f"{path.name} has no source URL. A costing without one cannot be re-found, "
            "and this suite exists to compare against the record, not against memory."
        )
    return Case(
        key=raw.get("key", path.stem),
        article=raw["article"],
        year=int(raw["year"]),
        scope=raw["scope"],
        reform=raw["reform"] or {},
        published=Published(
            amount_eur=float(published["amount_eur"]),
            sign=published.get("sign", "cost"),
            basis=published.get("basis", "unstated"),
            document=source.get("document", ""),
            url=source["url"],
            page=str(source.get("page", "")),
            quote=source.get("quote", ""),
            checked=str(source.get("checked", "")),
        ),
        tolerance=float(raw["tolerance"]),
        tolerance_reason=raw.get("tolerance_reason", ""),
        description=raw.get("description", ""),
        caveat=raw.get("caveat", ""),
        bound=raw.get("bound", "two-sided"),
        mirror=bool(raw.get("mirror", False)),
        expect_red=bool(raw.get("expect_red", False)),
    )


def load(directory: Path | None = None) -> list[Case]:
    directory = directory or CASES
    return [
        _case(path, yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        for path in sorted(directory.glob("*.yaml"))
    ]
