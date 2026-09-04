"""Pricing a 2024 household under the ISF, and what that turns out to mean.

**The measured finding that shapes this module: the ISF-2017 and IFI-2024 parameters are
IDENTICAL.** Barème thresholds and rates, décote bounds, décote rate and parameter,
plafonnement at 75 %, abattement résidence principale at 30 %, forfait mobilier at 5 % —
every one, checked side by side. So an "ISF revival" is not a different tax schedule at
all in this engine. It is the IFI schedule applied to a WIDER BASE.

That is worth stating plainly because it makes the reform far easier to reason about and
far harder to get wrong: whatever an ISF revival costs, it is the yield of adding
financial wealth to the base, not of changing rates.

**HOW THE ENGINE HIDES THE FINANCIAL BASE.** `isf_droits_sociaux` and `isf_actions_sal`
both carry `end = "2017-12-31"`, so after 2017 they return the default zero with no
formula run. `assiette_isf_ifi.formula_2018_01_01` still CALLS `isf_droits_sociaux` — it
is simply always nil. So the déclaration cases b1cb / b1cd / b1ce / b1cf are read at 2017
and silently dropped at 2024, and that silence is the whole ISF-versus-IFI difference
here.

**`update_variable` DOES NOT LIFT AN END DATE, AND FAILS SILENTLY.** Redefining the
variable without an `end` and calling `update_variable` raises nothing, and leaves
`end` at 2017-12-31 — openfisca-core's own docstring says why: "All attributes of the
updated variable that are not explicitly overridden by the new variable will stay
unchanged." The household then prices unchanged, and a read-back of the variable finds it
present. This is the read-back-blind class in the variable API rather than the parameter
tree, and it would have passed every check this project had before it started running
households.

`replace_variable` works, because it deletes the variable and reloads it, so the
inherited `end` goes with it. That is what this module uses.

**WHAT THIS IS NOT.** It is not a claim about what an ISF revival would raise nationally.
The cells carry immobilier wealth only (that is what DGFiP publishes), so pricing a
national ISF from them needs the base-composition scaling of PHASE5_SPEC §4, banded, and
that is a separate question from this module. Here a household with financial wealth
DECLARED can be priced under either regime, and the difference is exact.
"""

from __future__ import annotations

from typing import Any

#: The déclaration cases the ISF read and the IFI does not. Financial wealth: shares,
#: securities, liquid assets. Their absence from the IFI is the tax's definition
#: (CGI art. 965), not a gap.
ISF_ONLY_CASES: dict[str, str] = {
    "droits_sociaux_non_exoneres": "b1cd",
    "valeurs_mobilieres": "b1ce",
    "liquidites": "b1cf",
    "droits_sociaux_conserves_six_ans": "b1cb",
}

#: Variables the engine retired at the end of 2017, which an ISF revival must revive.
RETIRED_AT_2017 = ("isf_droits_sociaux", "isf_actions_sal")


def isf_1989_2017(system: Any) -> Any:
    """`system`, with the ISF's financial base revived for periods after 2017.

    Applied on top of whatever it is given, so the project's legal corrections
    (`patrimoine.corrections`) stay in force — an ISF revival should not also revive
    openfisca's missing liability threshold.
    """
    from openfisca_core.reforms import Reform

    class IsfRevival(Reform):
        name = "impots-regime:isf-1989-2017"

        def apply(self) -> None:
            for name in RETIRED_AT_2017:
                # replace_variable, NOT update_variable: the latter inherits `end` and
                # would leave these retired at 2017-12-31 while raising nothing. See the
                # module docstring — that is the silent failure this project keeps
                # meeting, here in the variable API.
                self.replace_variable(_without_end(name))

    return IsfRevival(system)


def _without_end(name: str) -> Any:
    """The engine's own variable class, with its 2017 end date removed.

    Subclassing the DEFINING CLASS rather than rewriting the formula is deliberate: the
    ISF arithmetic is openfisca's and we have no business reimplementing it. All that is
    removed is the date at which it stops applying.

    Subclassing does NOT work, and the reason is worth writing down because it cost two
    attempts. `Variable.set()` reads `attributes.pop(name)` off the class's OWN
    `__dict__`, so inherited attributes are invisible to it, and `replace_variable`
    passes no `baseline_variable` to fall back on. A subclass therefore arrives with
    every attribute missing and openfisca rejects it for "Missing attribute
    'value_type'" — which is at least a loud failure rather than a silent one.

    So the definition is COPIED and `end` is dropped from the copy. The formulas come
    across with it, so the arithmetic is still openfisca's.
    """
    from openfisca_core.variables import Variable
    from openfisca_france.model.prelevements_obligatoires import isf as module

    original = getattr(module, name)
    namespace = {key: value for key, value in vars(original).items()
                 if not key.startswith("__")}
    removed = namespace.pop("end", None)
    if removed is None:  # pragma: no cover - the whole point is that it has one
        raise RuntimeError(
            f"{name} no longer carries an `end` date, so reviving it is a no-op. Either "
            f"openfisca has un-retired it — in which case delete this module — or the "
            f"variable has been renamed."
        )
    return type(name, (Variable,), namespace)


def is_revived(system: Any) -> bool:
    """Whether financial wealth actually enters the base in this system.

    Asserted rather than assumed, because the failure mode this guards against is
    exactly a reform that applied cleanly and changed nothing.
    """
    return all(getattr(system.get_variable(name), "end", None) is None
               for name in RETIRED_AT_2017)
