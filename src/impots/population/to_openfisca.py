"""Population frame -> a vectorised OpenFisca simulation (PHASE1_SPEC §1, §4.4).

This is the most dangerous module in the project. Both of the failure modes the
Phase 1 spec calls out live here, and a third that the spec does not mention.

**#1 — roles are flattened *subrole* keys.** `join_with_persons` matches each role
string against `entity.flattened_roles`. The intuitive names from the JSON path
(`declarant`, `parent`) match nothing, every person gets a null role, `nbptr`
comes out 0.0 for every foyer, and **no exception is raised**. `ROLE_VOCABULARY`
below is asserted against the live entities before anything is built.

**#2 — enum defaults crash the benefits cascade.** Left at its default
(`non_renseigne`), `zone_apl` makes the aides-logement formulas index the
parameter tree by an enum value that has no entry, raising
`ParameterNotFoundError`. And because benefit reference periods look back
(D-005), setting year N alone is not enough — the lookback months of N-1 and N-2
must carry inputs too.

**#3 — group-level inputs are one value per *group*, not per person.** Of the four
variables §1.3 tells you to set for all 36 months, three (`zone_apl`,
`statut_occupation_logement`, `loyer`) live on the ménage. Passing a per-person
array raises loudly, which is a mercy — but the order of a group-level array must
match the order of the ids handed to `declare_entity`, and getting *that* wrong is
silent: households swap rents and nothing complains. Every group-level array here
is built by grouping and sorting on the same key used to declare the entity, and
its length is asserted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl
from openfisca_core.simulation_builder import SimulationBuilder

#: Years of income history written behind the simulated year. Two, because the
#: longest reference window is the aide au logement's rolling twelve months
#: ending in November of N-1 (D-005). Same steady-state assumption as the
#: household engine's `historique_revenus`, which D-011 made the only mode.
HISTORY_YEARS = 2

#: entity -> the flattened subrole keys it accepts. Asserted, not trusted.
ROLE_VOCABULARY: dict[str, tuple[str, ...]] = {
    "foyer_fiscal": ("declarant_principal", "conjoint", "personne_a_charge"),
    "famille": ("demandeur", "conjoint", "enfant"),
    "menage": ("personne_de_reference", "conjoint", "enfant", "autre"),
}

#: population column -> (entity, openfisca variable) for the group-level inputs.
MENAGE_INPUTS = (
    ("statut_occupation", "statut_occupation_logement"),
    ("zone_apl", "zone_apl"),
)


class WiringError(RuntimeError):
    """The population frame cannot be wired to OpenFisca as it stands."""


@dataclass
class PopulationSimulation:
    """A built simulation plus the keys needed to read results back out."""

    simulation: Any
    year: int
    household_ids: np.ndarray
    foyer_ids: np.ndarray
    famille_ids: np.ndarray
    n_persons: int

    def calculate(
        self, variable: str, add: bool = False, month: int | None = None
    ) -> np.ndarray:
        """Compute one variable, with the guards that separate noise from bugs.

        All-population runs legitimately emit `RuntimeWarning: divide by zero`
        from openfisca's own formulas on zero-income households. A NaN is not
        legitimate: it is how the role bug surfaces.

        `month` reads a single month instead of the year. The published allocataire
        counts are stocks *au 31 décembre*, and an annual read would count everyone
        entitled at any point in the year — a different statistic, larger, and the
        difference is exactly the churn the published figure excludes.
        """
        period = str(self.year) if month is None else f"{self.year}-{month:02d}"
        result = (
            self.simulation.calculate_add(variable, period)
            if add
            else self.simulation.calculate(variable, period)
        )
        nan_count = int(np.isnan(result).sum())
        if nan_count:
            raise WiringError(
                f"{variable} produced {nan_count} NaN of {result.size} — a wiring bug, "
                "not an edge case. Check the role vocabulary and the group-level inputs."
            )
        return result


def check_role_vocabulary(tax_benefit_system: Any) -> None:
    """Fail loudly if the subrole keys have moved under us.

    They are version-dependent, and if they change, every role silently becomes
    null: `nbptr` goes to 0 and the tax is garbage with no error anywhere.
    """
    for entity in tax_benefit_system.entities:
        if entity.is_person:
            continue
        actual = tuple(role.key for role in entity.flattened_roles)
        expected = ROLE_VOCABULARY.get(entity.key)
        if expected is None:
            continue
        if actual != expected:
            raise WiringError(
                f"{entity.key} subroles are {actual}, expected {expected}. "
                "Roles that do not match are silently dropped — fix this before running."
            )


def _text(series: pl.Series) -> np.ndarray:
    """A numpy *string* array, not an object array.

    `Series.to_numpy()` on a polars String column yields dtype `object`, which
    OpenFisca's enum encoder refuses ("not supported") and which would make the
    role join behave unpredictably. Everything crossing the boundary as text goes
    through here.
    """
    return series.to_numpy().astype(str)


def _group_frame(frame: pl.DataFrame, key: str, columns: list[str]) -> pl.DataFrame:
    """One row per group, sorted by the group key.

    The sort is load-bearing: `declare_entity` is given these same sorted ids, and
    a group-level input array is positional. First-per-group is safe for the
    columns used here because they are ménage attributes replicated onto every
    member by `skeleton.py`.
    """
    return frame.group_by(key).agg([pl.col(c).first() for c in columns]).sort(key)


def _set_niche_inputs(
    simulation: Any, tax_benefit_system: Any, year: int,
    bases: dict[str, Any], frame: pl.DataFrame, foyer_ids: Any,
) -> None:
    """Write imputed niche bases onto the simulation, on the right entity.

    Raises on a case the system does not carry or an array of the wrong length: a
    mis-shaped input is not an error in openfisca, it is a silent zero.
    """
    # `foyer_ids` is sorted, and `frame` is sorted by person_id with exactly one
    # principal declarant per foyer, so sorting the declarants by foyer_id puts them in
    # the same order as `foyer_ids`. Asserted rather than assumed: if it ever stops
    # holding, every union-dues figure would land on the wrong household silently.
    is_principal = (frame["role_foyer"] == "declarant_principal").to_numpy()
    declarant_foyers = _text(frame["foyer_id"])[is_principal]
    order = np.argsort(declarant_foyers, kind="stable")
    if not np.array_equal(declarant_foyers[order], foyer_ids):
        raise WiringError(
            "the principal declarants do not line up one-to-one with the foyers "
            "fiscaux; an individual-level niche would land on the wrong household"
        )
    principal_rows = np.flatnonzero(is_principal)[order]

    for case, values in bases.items():
        variable = tax_benefit_system.variables.get(case)
        if variable is None:
            raise WiringError(f"niche case {case!r} is not an OpenFisca variable")
        values = np.asarray(values, dtype=np.float64)
        if values.shape != (foyer_ids.size,):
            raise WiringError(
                f"niche case {case!r} has {values.shape}, expected ({foyer_ids.size},) "
                f"— one value per foyer fiscal, in `foyer_ids` order"
            )
        if variable.entity.key == "foyer_fiscal":
            simulation.set_input(case, str(year), values)
        elif variable.entity.key == "individu":
            # Scattered onto the principal declarant. A foyer-shaped array written to
            # an individual variable is silently dropped, not rejected.
            individual = np.zeros(frame.height, dtype=np.float64)
            individual[principal_rows] = values
            simulation.set_input(case, str(year), individual)
        else:
            raise WiringError(
                f"niche case {case!r} lives on {variable.entity.key}, which this "
                f"wiring does not handle"
            )


def build_simulation(
    frame: pl.DataFrame, tax_benefit_system: Any, year: int,
    niche_bases: dict[str, Any] | None = None,
) -> PopulationSimulation:
    """Wire a population frame into a vectorised simulation for `year`.

    `niche_bases` maps a déclaration case to an array ordered by `foyer_ids`, in euros
    and for the simulated year only. Individual-level cases — `f7ac` is the only one —
    are scattered onto each foyer's principal declarant, since the entitlement follows
    the member and openfisca will silently ignore a foyer-shaped array written to an
    individual variable.
    """
    check_role_vocabulary(tax_benefit_system)

    required = {
        "person_id", "household_id", "foyer_id", "famille_id", "age",
        "role_menage", "role_foyer", "role_famille",
        "salaire_brut_annuel", "pension_annuelle", "chomage_annuel",
        "statut_occupation", "zone_apl", "loyer_mensuel", "parent_isole",
    }
    missing = required - set(frame.columns)
    if missing:
        raise WiringError(f"population frame is missing {sorted(missing)}")

    frame = frame.sort("person_id")
    n_persons = frame.height

    for entity, column in (("menage", "role_menage"), ("foyer_fiscal", "role_foyer"),
                           ("famille", "role_famille")):
        unknown = set(frame[column].unique()) - set(ROLE_VOCABULARY[entity])
        if unknown:
            raise WiringError(f"{column} contains roles OpenFisca will drop silently: {unknown}")

    builder = SimulationBuilder()
    builder.create_entities(tax_benefit_system)
    builder.declare_person_entity("individu", np.arange(n_persons))

    household_ids = np.sort(_text(frame["household_id"].unique()))
    foyer_ids = np.sort(_text(frame["foyer_id"].unique()))
    famille_ids = np.sort(_text(frame["famille_id"].unique()))

    for entity, ids, person_key, role_column in (
        ("menage", household_ids, "household_id", "role_menage"),
        ("foyer_fiscal", foyer_ids, "foyer_id", "role_foyer"),
        ("famille", famille_ids, "famille_id", "role_famille"),
    ):
        instance = builder.declare_entity(entity, ids)
        builder.join_with_persons(
            instance, _text(frame[person_key]), _text(frame[role_column])
        )

    simulation = builder.build(tax_benefit_system)

    # ---- individual inputs -------------------------------------------------
    births = np.array(
        [f"{year - age:04d}-01-01" for age in frame["age"].to_list()], dtype="datetime64[D]"
    )
    simulation.set_input("date_naissance", "ETERNITY", births)
    monthly_salary = (frame["salaire_brut_annuel"].to_numpy() / 12.0).astype(np.float64)
    # Pensions and unemployment benefit are monthly individual inputs too. Leaving
    # them out is not a visible failure: the simulation runs, every guard passes,
    # and 14 M pensioners simply appear to live on nothing — which then shows up
    # three steps away as an RSA bill three times the published one.
    monthly_pension = (frame["pension_annuelle"].to_numpy() / 12.0).astype(np.float64)
    monthly_chomage = (frame["chomage_annuel"].to_numpy() / 12.0).astype(np.float64)

    # ---- ménage inputs, ordered to match `household_ids` -------------------
    menage = _group_frame(
        frame, "household_id", ["statut_occupation", "zone_apl", "loyer_mensuel"]
    )
    if menage.height != household_ids.size:
        raise WiringError("ménage-level frame does not line up with the declared ménages")
    statut = _text(menage["statut_occupation"])
    zone = _text(menage["zone_apl"])
    loyer = menage["loyer_mensuel"].to_numpy().astype(np.float64)

    for offset in range(HISTORY_YEARS, -1, -1):
        for month in range(1, 13):
            period = f"{year - offset}-{month:02d}"
            simulation.set_input("salaire_de_base", period, monthly_salary)
            simulation.set_input("retraite_brute", period, monthly_pension)
            simulation.set_input("chomage_brut", period, monthly_chomage)
            simulation.set_input("statut_occupation_logement", period, statut)
            simulation.set_input("zone_apl", period, zone)
            simulation.set_input("loyer", period, loyer)

    # ---- foyer fiscal inputs, ordered to match `foyer_ids` -----------------
    foyer = _group_frame(frame, "foyer_id", ["parent_isole"])
    if foyer.height != foyer_ids.size:
        raise WiringError("foyer-level frame does not line up with the declared foyers")
    simulation.set_input("caseT", str(year), foyer["parent_isole"].to_numpy().astype(bool))

    if niche_bases:
        _set_niche_inputs(
            simulation, tax_benefit_system, year, niche_bases, frame, foyer_ids)

    return PopulationSimulation(
        simulation=simulation,
        year=year,
        household_ids=household_ids,
        foyer_ids=foyer_ids,
        famille_ids=famille_ids,
        n_persons=n_persons,
    )
