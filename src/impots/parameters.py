"""Writing to an OpenFisca parameter tree, safely (D-044).

One rule, and it exists because breaking it produced a reform that reported success
and changed nothing:

    **`update()` may never create.**

`ParameterNode.update()` will happily write a child that does not exist at the
requested date. Nothing raises. The node afterwards *has* that child, so a read-back
finds exactly the value it was given and passes — and the year's formula, which looks
for a different name, sees nothing. The 2026 allègements refonte replaced
`entreprises_de_moins_de_50_salaries` with `t_delta_petites_entreprises`; writing the
old name succeeded, the D-007 read-back confirmed it, and labour cost moved by 0.00.

So every reform write goes through `update_existing`, which checks the target against
the tree **as the formula sees it at that instant** before writing. Creating a
parameter is still possible, through `create_parameter`, which has a different name
precisely so that doing it is a decision someone typed rather than a default someone
inherited.
"""

from __future__ import annotations

from typing import Any


class ParameterWriteError(ValueError):
    """A reform tried to write a parameter that does not exist at its start date.

    A `ValueError` on purpose: the API maps those to 422, and asking for a knob the
    requested year does not have is the caller's mistake, not the server's.
    """


def resolve(parameters: Any, path: tuple[str, ...]) -> Any:
    """Walk a dotted parameter path. Shared so both tax systems walk it identically."""
    node = parameters
    for part in path:
        node = getattr(node, part)
    return node


def exists_at(parameters: Any, path: tuple[str, ...], instant: str) -> bool:
    """Whether `path` resolves on the tree **as evaluated at `instant`**.

    Evaluated, not editable. An editable `ParameterNode` answers `hasattr` for any
    child defined at *any* date, so asking it what exists in 2024 also returns 2025's
    parameters — which is how a knob can write into a year that is not the one being
    reformed.
    """
    node = parameters(instant) if callable(parameters) else parameters
    try:
        for part in path:
            if not hasattr(node, part):
                return False
            node = getattr(node, part)
    except (AttributeError, KeyError):
        return False
    return True


def update_existing(
    parameters: Any,
    path: tuple[str, ...],
    *,
    start: Any,
    value: float,
    instant: str,
    superseded_by: dict[str, str] | None = None,
) -> None:
    """Write a parameter that exists at `instant`. Refuse to create one that does not.

    `instant` is the reform's own start date, so "exists" means "exists for the year
    being reformed" — not "exists somewhere in the tree's history".
    """
    if not exists_at(parameters, path, instant):
        name = path[-1]
        replacement = (superseded_by or {}).get(name)
        hint = (
            f" Ce paramètre a été remplacé par « {replacement} »."
            if replacement else ""
        )
        raise ParameterWriteError(
            f"le paramètre « {'.'.join(path)} » n'existe pas au {instant} : l'écrire "
            f"ne changerait rien, car `update()` créerait un enfant que la formule de "
            f"cette année ne lit pas — et une relecture le retrouverait, ce qui rend "
            f"la vérification muette.{hint}"
        )
    resolve(parameters, path).update(start=start, value=value)


def update_bracket(
    scale: Any, index: int, *, active: int, start: Any,
    rate: float | None = None, threshold: float | None = None,
) -> None:
    """Write one bracket of a scale, refusing an index the scale does not have.

    A scale's brackets are indexed rather than named, so `update()` cannot conjure one
    the way it conjures a named child — an out-of-range index raises on its own. The
    check is here anyway for two reasons: the count of *active* brackets is smaller
    than the list at most dates, so an index can be in range and still be a bracket
    the year does not use; and routing every parameter write through this module is
    what makes "no direct writes" a property a test can assert rather than a habit.
    """
    if not 0 <= index < active:
        raise ParameterWriteError(
            f"la tranche {index} n'est pas active à cette date (le barème en compte "
            f"{active}) : l'écrire porterait sur une tranche que la formule ignore"
        )
    if rate is not None:
        scale.brackets[index].rate.update(start=start, value=rate)
    if threshold is not None:
        scale.brackets[index].threshold.update(start=start, value=threshold)


def create_parameter(
    parameters: Any, path: tuple[str, ...], *, start: Any, value: float
) -> None:
    """Deliberately bring a parameter into existence.

    Separate from `update_existing`, and named so that it reads as a decision at the
    call site. Nothing in this project calls it yet; it exists so that when something
    legitimately needs to add a parameter, doing so is visible in a diff rather than
    indistinguishable from a typo.
    """
    resolve(parameters, path).update(start=start, value=value)
