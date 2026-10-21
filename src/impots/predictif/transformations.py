"""Phase 10 M4 — the named transformations: one number a grid can walk, written as the
reform's own knobs (PHASE10_SPEC §5).

A barème is not a scalar, and the grid walks only numbers (D-234). A transformation is how
one enters a search all the same. It is NAMED, it says which knobs it writes, and it reads
the law in force for the year it is applied to, so that « 0,95 » means the same thing in
the request, in the report and in the replay: the report records the law it read. It
writes only through the whitelisted knobs of `ReformSpec`, so the engine applies the
result, and reads it back, as it does any reform (`verify_bareme`).

THE LIST IS CLOSED. A name outside `TRANSFORMATIONS` is not a transformation, and the
request refuses it as an unknown knob (the D-092 lesson).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


class TransformationError(ValueError):
    """A transformation was asked for without what it transforms."""


@dataclass(frozen=True)
class Transformation:
    name: str
    label: str
    writes: tuple[str, ...]
    """The `ReformSpec` fields it writes: the base may not fix them too."""
    reads: tuple[str, ...]
    """The keys of the law in force it reads, which the report records."""
    apply: Callable[[float, Mapping[str, Any]], dict[str, Any]]


def _ir_scale(value: float, law: Mapping[str, Any]) -> dict[str, Any]:
    bareme = law.get("bareme") or []
    if not bareme:
        raise TransformationError(
            "droit en vigueur sans barème de l'IR : la mise à l'échelle ne porterait sur "
            "rien, et le paquet se chiffrerait à zéro.")
    return {"ir_bareme": [{"threshold": float(b["threshold"]),
                           "rate": float(b["rate"]) * value} for b in bareme]}


IR_SCALE = Transformation(
    name="ir_bareme_echelle",
    label="chaque taux du barème de l'IR en vigueur multiplié par ce facteur, les seuils "
          "inchangés",
    writes=("ir_bareme",), reads=("bareme",), apply=_ir_scale)

TRANSFORMATIONS: dict[str, Transformation] = {IR_SCALE.name: IR_SCALE}


def used(knobs: list[str]) -> list[Transformation]:
    """The transformations among a grid's knobs, in the order the grid names them."""
    return [TRANSFORMATIONS[k] for k in knobs if k in TRANSFORMATIONS]


def expand(knobs: Mapping[str, float],
           law: Mapping[str, Any] | None) -> dict[str, Any]:
    """The grid point as the reform's knobs: each transformation replaced by what it
    writes, from `law`, the law in force as `engine.reforms.read_ir_parameters` reads it."""
    out: dict[str, Any] = {}
    for knob, value in knobs.items():
        transformation = TRANSFORMATIONS.get(knob)
        if transformation is None:
            out[knob] = value
            continue
        if law is None:
            raise TransformationError(
                f"transformation « {knob} » sans le droit en vigueur : un facteur sans le "
                f"barème qu'il met à l'échelle ne veut rien dire.")
        out.update(transformation.apply(value, law))
    return out
