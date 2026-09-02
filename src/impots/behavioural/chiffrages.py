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
    expect_red: bool = False
    """Set when a case is known to miss and the miss is written up. It still runs and
    still reports its residual — this only stops a documented finding from failing
    CI, and every such case must carry its `caveat` explaining the miss."""

    def residual(self, simulated: float) -> float:
        published = self.published.signed
        return (simulated - published) / abs(published) if published else float("nan")

    def passes(self, simulated: float) -> bool:
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
        expect_red=bool(raw.get("expect_red", False)),
    )


def load(directory: Path | None = None) -> list[Case]:
    directory = directory or CASES
    return [
        _case(path, yaml.safe_load(path.read_text(encoding="utf-8")) or {})
        for path in sorted(directory.glob("*.yaml"))
    ]
