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

from impots.parameters import differs, resolve, update_existing

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
    "cvae_taux_max": ("cvae", "taux_max"),
    "cvae_degrevement": ("cvae", "degrevement", "montant"),
}

#: The CEBGE knob is paired rather than scalar, and these are the paths one tranche
#: writes to: its threshold, its rate, and the top of the 100 M€ band over which the
#: rate ramps up from zero. The band is *derived* from the threshold rather than
#: exposed, so a reform cannot leave a threshold and its smoothing band inconsistent
#: — which would silently tax a firm at a rate the spec never asked for.
CEBGE_TRANCHE_PATHS: tuple[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]], ...] = (
    (("cebge", "seuil_ca"), ("cebge", "taux_base"), ("cebge", "lissage", "borne_haute")),
    (
        ("cebge", "seuil_ca_taux_majore"),
        ("cebge", "taux_majore"),
        ("cebge", "lissage", "borne_haute_taux_majore"),
    ),
)


class CebgeTranche(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)  # D-173

    seuil_ca: Annotated[float, Field(ge=0)]
    taux: Annotated[float, Field(ge=0.0, le=1.0)]


class FirmReformSpec(BaseModel):
    """The whitelisted firm-tax knobs. All optional; an empty spec is no reform."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)  # D-173

    is_taux_normal: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    is_taux_reduit: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    is_plafond_taux_reduit: Annotated[float, Field(ge=0, le=100_000_000)] | None = None
    is_pme_plafond_ca: Annotated[float, Field(ge=0, le=1_000_000_000)] | None = None
    cs_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    cs_abattement: Annotated[float, Field(ge=0, le=1_000_000_000)] | None = None
    c3s_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    c3s_abattement: Annotated[float, Field(ge=0, le=1_000_000_000)] | None = None
    cvae_taux_max: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    cvae_degrevement: Annotated[float, Field(ge=0, le=1_000_000)] | None = None
    cebge_seuils_et_taux: list[CebgeTranche] | None = Field(
        default=None,
        max_length=len(CEBGE_TRANCHE_PATHS),
        description="Paired thresholds and rates for the CEBGE, lowest first. A "
        "threshold without its rate is not a policy, so they move together or not at "
        "all. At most two tranches, matching the statute's own shape.",
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


def _largeur(parameters: Any, instant: str) -> float:
    """Width of the CEBGE smoothing bands, or a refusal.

    The CEBGE lapses after its second exercice, and its parameters go null with it.
    A reform that revives it in a later year therefore has no band width to derive
    the smoothing from — and inventing 100 M€ back would be putting a number into
    the tree that no source supports for that year. Refusing says so out loud.
    """
    width = resolve(parameters, ("cebge", "lissage", "largeur"))(instant)
    if width is None:
        raise ValueError(
            f"la CEBGE n'existe plus au {instant} : ses paramètres sont nuls, donc la "
            "largeur de la bande de lissage n'est pas définie et le barème réformé "
            "serait une falaise. Rétablir la CEBGE demande un paramétrage daté, pas "
            "un curseur."
        )
    return float(width)


def make_reform(spec: FirmReformSpec, year: int, name: str) -> type[Reform]:
    """The `Reform` applying `spec` from `{year}-01-01`.

    `Reform(system)` clones the parameter tree, so the baseline survives — the
    property `test_no_mutation` keeps honest on the household side and does the
    same here.
    """
    start = periods.instant(f"{year}-01-01")
    instant = f"{year}-01-01"
    reform_name = f"impots-firm-reform:{name}"

    class FirmReform(Reform):
        name = reform_name

        def apply(self) -> None:
            def modify(parameters: Any) -> Any:
                for knob, path in SCALAR_KNOBS.items():
                    value = getattr(spec, knob)
                    if value is not None:
                        update_existing(parameters, path, start=start, value=value,
                                        instant=instant)
                largeur = _largeur(parameters, instant) if spec.cebge_seuils_et_taux else 0.0
                for tranche, paths in zip(
                    spec.cebge_seuils_et_taux or (), CEBGE_TRANCHE_PATHS, strict=False
                ):
                    seuil_path, taux_path, borne_path = paths
                    update_existing(parameters, seuil_path, start=start,
                                    value=tranche.seuil_ca, instant=instant)
                    update_existing(parameters, taux_path, start=start,
                                    value=tranche.taux, instant=instant)
                    update_existing(parameters, borne_path, start=start,
                                    value=tranche.seuil_ca + largeur, instant=instant)
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
        if differs(got, wanted):
            problems.append(f"{knob}: demandé {wanted}, appliqué {got}")
    if not spec.cebge_seuils_et_taux:
        if problems:
            raise AssertionError(
                "les paramètres appliqués ne correspondent pas à la réforme demandée — "
                + " ; ".join(problems)
            )
        return
    # From the BASELINE, not from the system under test: the expected smoothing bound
    # is `seuil + largeur`, so reading `largeur` out of the reformed tree would let a
    # reform that moved it define the answer it is checked against.
    from impots.entreprises.system import baseline as _baseline

    largeur = _largeur(_baseline().parameters, instant)
    for index, (tranche, paths) in enumerate(
        zip(spec.cebge_seuils_et_taux or (), CEBGE_TRANCHE_PATHS, strict=False)
    ):
        seuil_path, taux_path, borne_path = paths
        for label, path, wanted_value in (
            ("seuil_ca", seuil_path, tranche.seuil_ca),
            ("taux", taux_path, tranche.taux),
            ("borne de lissage", borne_path, tranche.seuil_ca + largeur),
        ):
            got = float(resolve(system.parameters, path)(instant))
            if differs(got, wanted_value):
                problems.append(
                    f"cebge_seuils_et_taux[{index}].{label}: demandé {wanted_value}, "
                    f"appliqué {got}"
                )
    if problems:
        raise AssertionError(
            "les paramètres appliqués ne correspondent pas à la réforme demandée — "
            + "; ".join(problems)
        )
