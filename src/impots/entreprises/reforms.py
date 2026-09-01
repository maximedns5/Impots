"""FirmReformSpec -> an openfisca `Reform` (PHASE2_SPEC §1.3).

A whitelist of named knobs, never raw parameter paths — same reasoning as the
household side: raw paths are an injection surface into the parameter tree and
make the cache key unbounded.

The knobs are chosen to price the questions actually being asked of French
corporate tax: move the IS rate, widen or narrow the PME reduced-rate slice,
renew or drop the CEBGE, change the C3S abattement. `cebge_seuils_et_taux` is
paired because a threshold without its rate is not a policy.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Annotated, Any

from openfisca_core import periods
from openfisca_core.reforms import Reform
from pydantic import BaseModel, ConfigDict, Field, model_validator

#: knob -> path in the parameter tree. Never `is`: a node of that name breaks
#: attribute access on the parameter tree, since it is a Python keyword.
SCALAR_KNOBS: dict[str, tuple[str, ...]] = {
    "is_taux_normal": ("impot_societes", "taux_normal"),
    "is_taux_reduit": ("impot_societes", "taux_reduit"),
    "is_plafond_taux_reduit": ("impot_societes", "plafond_taux_reduit"),
    "is_pme_plafond_ca": ("impot_societes", "plafond_ca_taux_reduit"),
    "cs_taux": ("impot_societes", "contribution_sociale", "taux"),
    "cs_abattement": ("impot_societes", "contribution_sociale", "abattement"),
    "c3s_taux": ("c3s", "taux"),
    "c3s_abattement": ("c3s", "abattement"),
}


class CebgeTranche(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seuil_ca: Annotated[float, Field(ge=0)]
    taux: Annotated[float, Field(ge=0.0, le=1.0)]


class FirmReformSpec(BaseModel):
    """The whitelisted firm-tax knobs. All optional; an empty spec is no reform."""

    model_config = ConfigDict(extra="forbid")

    is_taux_normal: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    is_taux_reduit: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    is_plafond_taux_reduit: Annotated[float, Field(ge=0, le=100_000_000)] | None = None
    is_pme_plafond_ca: Annotated[float, Field(ge=0, le=1_000_000_000)] | None = None
    cs_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    cs_abattement: Annotated[float, Field(ge=0, le=1_000_000_000)] | None = None
    c3s_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    c3s_abattement: Annotated[float, Field(ge=0, le=1_000_000_000)] | None = None
    cebge_seuils_et_taux: list[CebgeTranche] | None = Field(
        default=None,
        description="Paired thresholds and rates for the CEBGE. A threshold without "
        "its rate is not a policy, so they move together or not at all.",
    )

    @model_validator(mode="after")
    def _check(self) -> FirmReformSpec:
        both_rates_set = self.is_taux_reduit is not None and self.is_taux_normal is not None
        if both_rates_set and self.is_taux_reduit > self.is_taux_normal:
            raise ValueError(
                "le taux réduit dépasse le taux normal : la tranche réduite "
                "deviendrait une surtaxe, ce qui n'est presque jamais l'intention."
            )
        if self.cebge_seuils_et_taux is not None:
            tranches = self.cebge_seuils_et_taux
            if not tranches:
                raise ValueError("cebge_seuils_et_taux ne peut pas être une liste vide")
            seuils = [t.seuil_ca for t in tranches]
            if any(a >= b for a, b in pairwise(seuils)):
                raise ValueError(
                    f"les seuils de CA doivent être strictement croissants ; reçu {seuils}"
                )
        return self

    def is_empty(self) -> bool:
        """True when no knob is set — treated as no reform rather than as an identity
        reform, so nothing is rebuilt to prove that nothing changed."""
        return not self.model_dump(exclude_none=True)


def resolve(parameters: Any, path: tuple[str, ...]) -> Any:
    node = parameters
    for part in path:
        node = getattr(node, part)
    return node


def make_reform(spec: FirmReformSpec, year: int, name: str) -> type[Reform]:
    """The `Reform` applying `spec` from `{year}-01-01`.

    `Reform(system)` clones the parameter tree, so the baseline survives — the
    property `test_no_mutation` keeps honest on the household side and does the
    same here.
    """
    start = periods.instant(f"{year}-01-01")
    reform_name = f"impots-firm-reform:{name}"

    class FirmReform(Reform):
        name = reform_name

        def apply(self) -> None:
            def modify(parameters: Any) -> Any:
                for knob, path in SCALAR_KNOBS.items():
                    value = getattr(spec, knob)
                    if value is not None:
                        resolve(parameters, path).update(start=start, value=value)
                return parameters

            self.modify_parameters(modifier_function=modify)

    return FirmReform


def verify_scales(system: Any, spec: FirmReformSpec, year: int) -> None:
    """Read the reformed parameters back and refuse anything that is not what was asked.

    D-007 made portable. On the household side the prescribed way of neutralising
    surplus barème brackets silently *summed* their rates — three 40 % brackets
    became one at 120 %, and a 240 k€ household was charged 158 160 € instead of
    58 720 € with no error raised anywhere. Nothing here is barème-shaped yet; the
    CVAE schedule will be, and the guard exists before the thing it guards.
    """
    instant = f"{year}-01-01"
    problems: list[str] = []
    for knob, path in SCALAR_KNOBS.items():
        wanted = getattr(spec, knob)
        if wanted is None:
            continue
        got = float(resolve(system.parameters, path)(instant))
        if abs(got - wanted) > 1e-9 * max(abs(wanted), 1.0):
            problems.append(f"{knob}: demandé {wanted}, appliqué {got}")
    if problems:
        raise AssertionError(
            "les paramètres appliqués ne correspondent pas à la réforme demandée — "
            + "; ".join(problems)
        )
