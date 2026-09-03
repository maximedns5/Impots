"""The macro parameter store (PHASE4_SPEC §2).

The behavioural store's rule, extended one step: a row loads only with a verifier's
verdict, and a row that dies is **removed with its reason** rather than softened. What
is new here is where the numbers come from.

**Table-valued rows carry no numbers in YAML.** A multiplier is not one figure but
eight instruments times six horizons, and retyping forty-eight numbers into a
configuration file is precisely the transcription D-026 forbids. So `multipliers.yaml`
declares `from_source_table: gdp` and the values are parsed out of the published PDF by
`impots.macro.mesange`. The YAML holds what the PDF cannot: scope, support, the
verdict, and the reasons a row is narrower than someone might wish.

That inverts the usual failure. A stale YAML cannot drift away from its source, because
there is nothing in it to drift; but a source file that goes missing kills its rows
loudly, which is the direction this project wants to fail in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from impots.behavioural.store import (
    LOADABLE_VERDICTS,
    Confidence,
    Distribution,
    Parameter,
    Source,
    Support,
    UnverifiedParameter,
    Verifier,
)
from impots.macro import imk, mesange

PARAMETERS = Path(__file__).resolve().parent / "parameters"

#: Readers a `source_table` block may name. A YAML file cannot nominate arbitrary
#: import paths: the point of parsing from the primary file is that the parser is
#: reviewed code, and an open-ended importer would hand that property back.
READERS = {"impots.macro.mesange": mesange, "impots.macro.imk": imk}


class MissingSourceTable(RuntimeError):
    """A table-valued parameter's primary file is absent."""


@dataclass(frozen=True)
class TableParameter:
    """A parameter whose value is a table read from a primary document.

    `values[instrument][horizon]` — no central/low/high, because the source publishes
    a profile per instrument and flattening it to one figure is how the spec's seeds
    came to be a year-one range wearing no horizon.
    """

    key: str
    values: dict[str, tuple[float, ...]]
    horizons: tuple[str, ...]
    applies_to: str
    support: Support
    source: Source
    verifier: Verifier
    confidence: Confidence = "medium"
    distribution: Distribution = "triangular"
    responds_to_knobs: tuple[str, ...] = ()
    note: str = ""

    def at(self, instrument: str, horizon: str) -> float:
        if instrument not in self.values:
            raise KeyError(
                f"{self.key}: no instrument {instrument!r}. Instruments without a "
                f"published variant have no multiplier and must not borrow one; "
                f"have {sorted(self.values)}"
            )
        if horizon not in self.horizons:
            raise KeyError(f"{self.key}: no horizon {horizon!r}; have {self.horizons}")
        return self.values[instrument][self.horizons.index(horizon)]

    def profile(self, instrument: str) -> tuple[float, ...]:
        if instrument not in self.values:
            raise KeyError(f"{self.key}: no instrument {instrument!r}")
        return self.values[instrument]


@dataclass
class Store:
    parameters: dict[str, Parameter] = field(default_factory=dict)
    tables: dict[str, TableParameter] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    rejected: dict[str, str] = field(default_factory=dict)
    removed: dict[str, str] = field(default_factory=dict)
    """Rows deliberately killed, with the reason. A feature resting on one reports
    'no usable evidence, because ...' rather than quietly having fewer inputs."""

    def __getitem__(self, key: str) -> Parameter:
        return self.parameters[key]

    def __contains__(self, key: str) -> bool:
        return key in self.parameters or key in self.tables

    def why_removed(self, key: str) -> str:
        """The reason a feature is dead, for the assumptions strip to print."""
        if key in self.removed:
            return self.removed[key]
        if key in self.rejected:
            return self.rejected[key]
        raise KeyError(f"{key!r} was not removed or rejected")

    def vintage(self) -> str:
        keys = ",".join(sorted([*self.parameters, *self.tables]))
        return f"{len(self.parameters) + len(self.tables)} rows [{keys}]"


def _support(raw: dict[str, Any]) -> Support:
    bound = raw.get("max_variation_graded_in_support")
    return Support(
        estimated_on=raw.get("estimated_on", ""),
        max_variation_graded_in_support=None if bound is None else float(bound),
    )


def _source(raw: dict[str, Any]) -> Source:
    return Source(citation=raw.get("citation", ""), url=raw.get("url", ""),
                  vintage=str(raw.get("vintage", "")), quote=raw.get("quote", ""))


def _verifier(raw: dict[str, Any]) -> Verifier:
    return Verifier(verdict=raw.get("verdict"), date=str(raw.get("date") or ""),
                    ref=raw.get("ref") or "", note=raw.get("note", ""))


def _scalar(key: str, raw: dict[str, Any]) -> Parameter:
    value = raw["value"]
    return Parameter(
        key=key, central=float(value["central"]), low=float(value["low"]),
        high=float(value["high"]), distribution=value.get("distribution", "triangular"),
        applies_to=raw.get("applies_to", ""),
        responds_to_knobs=tuple(raw.get("responds_to_knobs") or ()),
        support=_support(raw.get("support") or {}), source=_source(raw.get("source") or {}),
        verifier=_verifier(raw.get("verifier") or {}),
        confidence=raw.get("confidence", "medium"), note=raw.get("note", ""),
    )


def _table(key: str, raw: dict[str, Any], declared: dict[str, Any],
           raw_dir: Path | None) -> TableParameter:
    reader_name = declared.get("reader")
    reader = READERS.get(reader_name)
    if reader is None:
        raise MissingSourceTable(
            f"{key}: source_table names reader {reader_name!r}, which is not one of "
            f"{sorted(READERS)}. Readers are reviewed code, not a YAML import path."
        )
    value = raw["value"]
    # Everything in the value block other than the row name and the distribution is an
    # argument for the reader, so a second document is a data change, not a code change.
    options = {k: v for k, v in value.items()
               if k not in ("from_source_table", "distribution")}
    values, horizons = reader.table(value["from_source_table"], raw=raw_dir, **options)
    return TableParameter(
        key=key,
        values=values,
        horizons=horizons,
        applies_to=raw.get("applies_to", ""),
        responds_to_knobs=tuple(raw.get("responds_to_knobs") or ()),
        support=_support(raw.get("support") or {}), source=_source(declared),
        verifier=_verifier(raw.get("verifier") or {}),
        confidence=raw.get("confidence", "medium"),
        distribution=value.get("distribution", "triangular"),
        note=raw.get("note", ""),
    )


def load(directory: Path | None = None, *, strict: bool = True,
         raw: Path | None = None) -> Store:
    """Load the macro store, refusing anything a verifier has not passed.

    `strict=False` records refusals in `Store.rejected` rather than raising. It exists
    for the report that lists what is missing and why — never for a band. Producing a
    number is always strict.
    """
    store = Store()
    for path in sorted((directory or PARAMETERS).glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        store.thresholds.update(document.get("thresholds") or {})
        store.removed.update(document.get("removed") or {})
        declared = document.get("source_table") or {}
        for key, body in (document.get("parameters") or {}).items():
            verdict = (body.get("verifier") or {}).get("verdict")
            if verdict not in LOADABLE_VERDICTS:
                reason = (
                    f"verdict {verdict!r} — only {sorted(LOADABLE_VERDICTS)} load. "
                    f"{(body.get('verifier') or {}).get('note', '').strip()}"
                )
                if strict:
                    raise UnverifiedParameter(f"{path.name}:{key}: {reason}")
                store.rejected[key] = reason
                continue
            if "from_source_table" in (body.get("value") or {}):
                store.tables[key] = _table(key, body, declared, raw)
            else:
                store.parameters[key] = _scalar(key, body)
    return store


def draw(parameter: Parameter, rng: np.random.Generator, size: int) -> np.ndarray:
    """Sample a scalar parameter. Delegates, so both stores share one sampler."""
    return parameter.draw(rng, size)
