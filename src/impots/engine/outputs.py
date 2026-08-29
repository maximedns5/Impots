"""The variable registry: what we extract, from which entity, over which period,
and with which sign (spec §3.3).

This is a closed list on purpose. Free-form variable access would let the API
surface 3 142 openfisca variables we have never checked, each with its own period
and sign convention.

Names that look right and are wrong: `irpp` no longer exists (it is
`impot_revenu_restant_a_payer`), prime d'activité is `ppa` not `prime_activite`,
and there is no marginal-rate variable at all — EMTR is a finite difference
(see `compute.emtr`).

**Signs, measured on openfisca-france 176.0.8**: `impot_revenu_restant_a_payer`,
`cotisations_salariales`, `cotisations_employeur`, `csg_*_salaire` and
`crds_salaire` all come out negative (money leaving the household). They are
negated exactly once, here, at the wrapper boundary — never again downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Entity = Literal["individu", "foyer_fiscal", "famille", "menage"]
Period = Literal["month", "year"]
Tier = Literal["light", "full"]


@dataclass(frozen=True)
class Row:
    key: str
    """Key in the wire format."""
    variable: str
    """OpenFisca variable name."""
    entity: Entity
    period: Period
    tier: Tier
    negate: bool
    """True when the engine reports this as a negative number and the wire format
    reports a positive magnitude."""
    money: bool = True
    """False for counts such as `nbptr`, which must not be formatted as EUR."""
    label: str = ""
    """French label for the UI."""


REGISTRY: tuple[Row, ...] = (
    # --- salary block: individu, monthly, summed over household members --------
    Row("salaire_brut", "salaire_de_base", "individu", "month", "light", False,
        label="Salaire brut"),
    Row("salaire_super_brut", "salaire_super_brut", "individu", "month", "light", False,
        label="Coût du travail (super-brut)"),
    Row("salaire_net", "salaire_net", "individu", "month", "light", False,
        label="Salaire net"),
    Row("salaire_imposable", "salaire_imposable", "individu", "month", "light", False,
        label="Salaire imposable"),
    Row("cotisations_salariales", "cotisations_salariales", "individu", "month", "light", True,
        label="Cotisations salariales"),
    Row("cotisations_employeur", "cotisations_employeur", "individu", "month", "light", True,
        label="Cotisations employeur"),
    Row("csg_deductible", "csg_deductible_salaire", "individu", "month", "light", True,
        label="CSG déductible"),
    Row("csg_imposable", "csg_imposable_salaire", "individu", "month", "light", True,
        label="CSG imposable"),
    Row("crds", "crds_salaire", "individu", "month", "light", True,
        label="CRDS"),
    # --- tax block: foyer fiscal, annual --------------------------------------
    Row("ir", "impot_revenu_restant_a_payer", "foyer_fiscal", "year", "light", True,
        label="Impôt sur le revenu"),
    Row("ir_avant_reductions", "ir_plaf_qf", "foyer_fiscal", "year", "light", False,
        label="IR après plafonnement du QF"),
    Row("parts_fiscales", "nbptr", "foyer_fiscal", "year", "light", False, money=False,
        label="Parts fiscales"),
    Row("revenu_fiscal_reference", "rfr", "foyer_fiscal", "year", "light", False,
        label="Revenu fiscal de référence"),
    # --- benefits block: famille, monthly — full tier only ---------------------
    Row("af", "af", "famille", "month", "full", False,
        label="Allocations familiales"),
    Row("ppa", "ppa", "famille", "month", "full", False,
        label="Prime d'activité"),
    Row("rsa", "rsa", "famille", "month", "full", False,
        label="RSA"),
    Row("aide_logement", "aide_logement", "famille", "month", "full", False,
        label="Aide au logement"),
    # --- bottom line: ménage, annual — full tier only --------------------------
    Row("revenu_disponible", "revenu_disponible", "menage", "year", "full", False,
        label="Revenu disponible"),
)

BY_KEY: dict[str, Row] = {row.key: row for row in REGISTRY}
LIGHT_ROWS: tuple[Row, ...] = tuple(r for r in REGISTRY if r.tier == "light")
FULL_ROWS: tuple[Row, ...] = REGISTRY


def rows_for(tier: Tier) -> tuple[Row, ...]:
    """The registry rows a given tier computes.

    `light` deliberately stops at the foyer fiscal: touching `revenu_disponible`
    or any famille variable triggers the whole benefits cascade and turns a 0.5 s
    request into a 3 s one.
    """
    return LIGHT_ROWS if tier == "light" else FULL_ROWS


def extract(simulation: Any, year: int, tier: Tier, debug: bool = False) -> dict[str, Any]:
    """Read the registry off a built Simulation and normalise it.

    Monthly variables are annualised with `calculate_add`; annual variables use
    `calculate` (calling `calculate` on a monthly variable raises). Individual
    variables are summed across household members — children contribute 0 salary,
    which is what makes the sum the household total.
    """
    period = str(year)
    values: dict[str, Any] = {}
    raw: dict[str, float] = {}

    for row in rows_for(tier):
        array = (
            simulation.calculate_add(row.variable, period)
            if row.period == "month"
            else simulation.calculate(row.variable, period)
        )
        total = float(array.sum()) if row.entity == "individu" else float(array[0])
        raw[row.key] = round(total, 2)
        # `+ 0.0` collapses IEEE negative zero: a household that owes no tax must
        # serialise as 0.0, not -0.0.
        values[row.key] = round(-total if row.negate else total, 2) + 0.0

    if debug:
        values["raw"] = raw
    return values


def check_registry(tax_benefit_system: Any) -> list[str]:
    """Assert every registry row still matches the engine. Returns a list of
    problems, empty when the registry is sound.

    A weekly openfisca release can rename a variable or move it between entities;
    this turns that into a named test failure instead of a silent zero.
    """
    problems: list[str] = []
    for row in REGISTRY:
        variable = tax_benefit_system.variables.get(row.variable)
        if variable is None:
            problems.append(f"{row.key}: variable {row.variable!r} no longer exists")
            continue
        if variable.entity.key != row.entity:
            problems.append(
                f"{row.key}: {row.variable} is on entity {variable.entity.key!r}, "
                f"registry says {row.entity!r}"
            )
        actual_period = str(variable.definition_period).lower()
        if actual_period != row.period:
            problems.append(
                f"{row.key}: {row.variable} has period {actual_period!r}, "
                f"registry says {row.period!r}"
            )
    for dead in ("irpp", "prime_activite", "taux_marginal_imposition"):
        if tax_benefit_system.variables.get(dead) is not None:
            problems.append(f"{dead!r} exists again — the registry comment is now wrong")
    return problems
