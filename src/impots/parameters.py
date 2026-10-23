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

import math
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


def _refuse_shared_baseline(parameters: Any) -> None:
    """Refuse a write aimed at the process-wide baseline tree.

    `engine.system.baseline()` is memoised — it costs about three seconds to build, so it
    is built once — and the production reform path never writes to it: `Reform(tbs)`
    clones the tree first, which `test_no_mutation` proves. But an ad-hoc script that
    calls `update_existing(baseline().parameters, ...)` mutates the tree every later
    caller in that process will read, including the one it is being compared against.

    THIS IS NOT HYPOTHETICAL AND THE FAILURE IS SILENT. Probing whether `taux_cdhr` is a
    live knob, I wrote 0.30 into `baseline()` and compared the result with `baseline()` —
    the same object. The tax did not move, and the obvious reading was "dead parameter,
    an eighth upstream artefact". It is not dead: on two distinct systems it moves the
    CDHR from -75 836 to -281 236. The measurement was comparing a tree with itself,
    which is the D-044 shape appearing in a five-line script.

    A guard that fires only outside the production path costs nothing there and turns a
    silent wrong answer into a message.
    """
    # `baseline` memoises in a module-level `_TBS`, not an lru_cache. Read that directly
    # rather than calling `baseline()`, which would BUILD the system just to check —
    # three seconds, on every parameter write, to answer a question that is "no" whenever
    # it has not been built.
    from impots.engine import system as system_module

    cached = getattr(system_module, "_TBS", None)
    if cached is None:
        return  # never built: this cannot be it
    if parameters is cached.parameters:
        raise ParameterWriteError(
            "écriture refusée sur l'arbre de `baseline()`, qui est mémoïsé et partagé par "
            "tout le processus. Le chemin de production ne passe jamais par ici — "
            "`Reform(tbs)` clone l'arbre d'abord. Un script qui écrit ici modifie l'arbre "
            "que tous les appels suivants liront, y compris celui auquel on croit le "
            "comparer : la comparaison porte alors sur un arbre et lui-même, et un "
            "paramètre bien vivant paraît mort. Construire un "
            "`FranceTaxBenefitSystem()` neuf pour ce genre de sonde."
        )


def update_existing(
    parameters: Any,
    path: tuple[str, ...],
    *,
    start: Any,
    value: float,
    instant: str,
    superseded_by: dict[str, str] | None = None,
    knob_for: dict[str, str] | None = None,
    not_before: dict[str, str] | None = None,
) -> None:
    """Write a parameter that exists at `instant`. Refuse to create one that does not.

    `instant` is the reform's own start date, so "exists" means "exists for the year
    being reformed" — not "exists somewhere in the tree's history". The refusal names
    what replaced the parameter, and the knob that moves it (`knob_for`); or, for one
    the tree only has from a later year, what governs until then (`not_before`).
    """
    _refuse_shared_baseline(parameters)
    if not exists_at(parameters, path, instant):
        name = path[-1]
        replacement = (superseded_by or {}).get(name)
        knob = (knob_for or {}).get(replacement or "")
        if replacement:
            hint = (f" Ce paramètre a été remplacé par « {replacement} »"
                    + (f", que règle le bouton « {knob} »" if knob else "") + ".")
        elif name in (not_before or {}):
            hint = f" Il n'existe pas encore à cette date : {not_before[name]}."
        else:
            hint = ""
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


def differs(got: float, wanted: float) -> bool:
    """A read-back mismatch, failing closed on anything non-finite.

    `abs(got - wanted) > 1e-9 * max(abs(wanted), 1.0)` let both through: NaN compares
    false with everything, and a tolerance relative to an infinite request is itself
    infinite. An infinite CEBGE threshold priced a repeal at +3,24 md€ on the fixture
    without a word (D-173). One rule, read by every read-back on both sides.
    """
    if not (math.isfinite(got) and math.isfinite(wanted)):
        return True
    return abs(got - wanted) > 1e-9 * max(abs(wanted), 1.0)

