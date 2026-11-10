"""Population frame -> a vectorised OpenFisca simulation (PHASE1_SPEC §1, §4.4).

This is the most dangerous module in the project. Both of the failure modes the
Phase 1 spec calls out live here, and five that the spec does not mention.

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

**#4 — a pension priced two ways, by evaluation order.** `retraite_imposable` is
`retraite_brute + csg_deductible_retraite`, and the rate of every pension levy reads
the RFR of N-2, which reads `retraite_imposable` of N-2. openfisca cuts that regress
at its second turn, wherever the order of evaluation puts the turn, and keeps what
was computed beside the cut. The runner's order — the income tax first — left the
deductible CSG at zero; `revenu_disponible` computed first took it off a second
time. On the 400-dwelling fixture, 164 ménages of 400 moved between the two and the
median niveau de vie by 1.7 %; the population EMTR read one order, the
reconciliation report the other. `pension_annuelle` is calibrated on DECLARED
pensions, so it is now written on `retraite_imposable` (box 1AS) as well as on
`retraite_brute`, and the regress through pensions no longer exists (D-176).

**#5 — the RFR of N-2, read from inside year N.** Unemployment benefit has the same
regress, and its input is GROSS (Unédic spend), so it cannot be pinned the way a
declared pension is. And openfisca cuts any nested evaluation of a variable at another
period: asked for from inside the income tax of N, the RFR of N-2 lost its own `rni`
to the cut and read as the exemption. The income tax then assessed a 30 000 EUR
chômeur on the gross amount, and `revenu_disponible` missed the CSG and CRDS owed. The RFR
of N-2 is now computed first and pinned, by `engine.situations.pin_rfr_n_2`, which the
household builder calls too (D-177).

**#6 — housing aid and the RSA, month by month.** The aid's neutralisation reads the
RSA of the month before, whose forfait logement reads the aid of that month. With the
aid of one month on the stack, the aid of the month before was cut to zero, and the
prime d'activité of January to March lost the forfait logement of its reference
quarter: 12 renter ménages of the fixture moved by up to 352 EUR between the runner's
order and `revenu_disponible` first, the order of the population EMTR. Before the first
non-fiscal variable, `PopulationSimulation.calculate` now pins the aid month by month,
oldest first, by `engine.situations.pin_benefit_history`, which the household builder
calls for its full tier too (D-178).

**#7 — case T on year N alone.** The rate of the CSG on a pension or an unemployment
benefit reads the RFR and the parts of N-2. Case T was written on N only, so a lone
parent's half-part reached the income tax of N and not that rate: on the fixture, a
pensioner of 82 was levied at 6.6 % instead of 3.8 %, and one of 67 at 3.8 % instead of
nothing, 839.58 and 104.64 EUR of revenu disponible. It is now written on N-2 and N-1
too, as the household builder writes it (D-199).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import polars as pl
from openfisca_core.simulation_builder import SimulationBuilder

from impots import decomposition
from impots.engine.outputs import LIGHT_ROWS
from impots.engine.situations import pin_benefit_history, pin_rfr_n_2

#: Years of income history written behind the simulated year. Two, because the
#: longest reference window is the aide au logement's rolling twelve months
#: ending in November of N-1 (D-005). Same steady-state assumption as the
#: household engine's `historique_revenus`, which D-011 made the only mode.
HISTORY_YEARS = 2

#: What `build_simulation` computes, named. Results memoised on disk from a simulation
#: built here (the EMTR caches of `behavioural.emtr`) carry it in their key, so that a
#: file written under one wiring is never served under another. Change it whenever a
#: change here moves a number: D-176 moved every pensioner's revenu disponible in the
#: order the population EMTR reads it, D-177 the income tax and the revenu disponible of
#: every chômeur above the SMIC floor, D-178 the prime d'activité of renters in the order
#: the population EMTR reads it. D-180 is a correction to the baseline system rather than
#: to this wiring, but the caches hold its numbers too: the housing aid of anyone whose
#: salary is under the minimum professional-expenses deduction, beside other income. D-188
#: likewise: the abatement of art. 157 bis doubled for a couple both over 65, which lowers
#: its RFR, and two years on the rate of the CSG on its pensions. D-195 is the skeleton's,
#: and changes the case T this wiring writes: a lone declarant the survey records as living
#: in a couple, whose partner the skeleton could not pair, loses the half-part. The caches
#: check only a population's height, which that keeps, and would serve the rebuilt
#: population its old rates. D-199 writes that case T on N-2 and N-1 as well, where the
#: rate of the CSG on a lone parent's pension or unemployment benefit reads it: on the
#: fixture, two pensioners' revenu disponible rises, by 839.58 and 104.64 EUR. The
#: population itself does not change, and a cache written before would be served after.
# A run without E1 wires every earner as private: its EMTR caches are not E1's (D-354).
# The self-employed's income (but 19, étape 2) changes the population, whose height the
# caches check, and its wiring here: every number of every self-employed household moves.
# The étape « ir » pays the gérants a salary and writes the exempt share of the salaries
# (correction 24): every employee's income tax moves.
WIRING = "D-346_ns_ir" + ("_sansE1" if decomposition.sans("E1") else "")

#: What the light tier, the rake and the niche imputation ask of a simulation: the
#: fiscal block, which never reaches a benefit. The ASS the income tax reads since D-192
#: is computed only for an adult in « fin de droits », and this wiring declares none.
#: Anything else first pins the benefit history (failure mode #6), once, so the light
#: tier never pays for it.
FISCAL_VARIABLES = frozenset(
    {name for row in LIGHT_ROWS for name in (row.variable, *row.extra)}
    | {"nbptr", "rfr", "impot_revenu_restant_a_payer"})

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
    benefits_pinned: bool = False

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
        if not self.benefits_pinned and variable not in FISCAL_VARIABLES:
            # Failure mode #6: before the first benefit, whoever asks for it.
            pin_benefit_history(self.simulation, self.year)
            self.benefits_pinned = True
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
    years: tuple[int, ...] | None = None,
) -> None:
    """Write imputed niche bases onto the simulation, on the right entity, for `year` or
    for each of `years`.

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
        for period in (years or (year,)):
            if variable.entity.key == "foyer_fiscal":
                simulation.set_input(case, str(period), values)
            elif variable.entity.key == "individu":
                # Scattered onto the principal declarant. A foyer-shaped array written to
                # an individual variable is silently dropped, not rejected.
                individual = np.zeros(frame.height, dtype=np.float64)
                individual[principal_rows] = values
                simulation.set_input(case, str(period), individual)
            else:
                raise WiringError(
                    f"niche case {case!r} lives on {variable.entity.key}, which this "
                    f"wiring does not handle"
                )


#: openfisca variable -> the frame column `population.ij` writes (D-305).
IJ_INPUTS: dict[str, str] = {
    "indemnites_journalieres_maladie": "ij_maladie_annuel",
    "indemnites_journalieres_accident_travail": "ij_atmp_annuel",
    # The part of the sickness allowances served for an ALD, which correction 22 adds and
    # exempts (D-312): written beside the sickness allowances that contain it.
    "indemnites_journalieres_maladie_ald": "ij_maladie_ald_annuel",
}
#: The inputs of `IJ_INPUTS` that the corrections add, not openfisca. Raw openfisca, which
#: kill tests run, has none of them and taxes no allowance: they are not written there, as a
#: row of the project reads zero there (D-308). Any other missing variable still raises.
IJ_PROJECT_INPUTS = frozenset({"indemnites_journalieres_maladie_ald"})


#: The self-employed's régime (`incomes.REGIMES`) -> the 2042-C-PRO box written, and for
#: a micro-entrepreneur the nature of his turnover. The frame carries the Insee's income,
#: the turnover AFTER the abatement for a micro-entrepreneur; the box is the turnover,
#: so it is grossed up by the year's abatement. A réel profit is its own box: 5KC
#: (`abic_impn`), 5QC (`abnc_impo`), 5HC (`arag_impg`). A gérant majoritaire has no box
#: here: he is paid a salary (`incomes.attach_self_employment`, étape « ir »), and his
#: régime only names him. The micro-BA income
#: goes on the variable the boxes compute, `rpns_revenus_microBA_agricole`, as the
#: three-year average it is.
#:
#: **The versement libératoire is drawn, and not wired.** Its boxes (5TA, 5TB, 5TE:
#: `ebic_impv`, `ebic_imps`, `ebnc_impo`) feed openfisca's `microentreprise`, which
#: `revenus_non_salarie_nets` adds to each person as `sum(...)` of a vector: the
#: liberatory profit of EVERY foyer of the simulation, added to every person's disposable
#: income. One household computes right; a population of 15 000 ménages had a median
#: niveau de vie of 3.9 M€ (étape 2, measured). Until a correction holds it, the
#: micro-entrepreneurs drawn into the versement libératoire are declared in the micro
#: boxes: taxed at the barème rather than at 1 to 2.2 % of their turnover, which puts
#: their income tax a little high, and their RFR, benefits and CSG are the same.
SELF_EMPLOYMENT_INPUTS: dict[str, tuple[str, str | None]] = {
    "reel_bic": ("abic_impn", None),
    "reel_bnc": ("abnc_impo", None),
    "micro_vente": ("mbic_impv", "vente"), "micro_service": ("mbic_imps", "service"),
    "micro_bnc": ("mbnc_impo", "bnc"),
    "vl_vente": ("mbic_impv", "vente"), "vl_service": ("mbic_imps", "service"),
    "vl_bnc": ("mbnc_impo", "bnc"),
    "reel_ba": ("arag_impg", None),
    "micro_ba": ("rpns_revenus_microBA_agricole", None),
}


#: The régimes of the gérants majoritaires, paid a salary: no self-employment box.
GERANTS = frozenset({"gerant_bic", "gerant_bnc"})

#: The share of a salary the income tax exempts (correction 24), by the column that carries it.
EXEMPT_SHARE_INPUT = ("part_salaire_exoneree_ir", "part_salaire_exoneree")


def micro_turnover(income: np.ndarray, abatement: float, minimum: float) -> np.ndarray:
    """The turnover whose micro income is `income`: the inverse of openfisca's
    `abat_rpns`, income = turnover − max(abatement × turnover, minimum), below the ceiling.
    A nil income is a nil turnover."""
    income = np.asarray(income, dtype=np.float64)
    return np.where(income > 0, np.maximum(income / (1.0 - abatement), income + minimum), 0.0)


def self_employment_inputs(frame: pl.DataFrame, tax_benefit_system: Any, year: int
                           ) -> tuple[dict[str, np.ndarray], Any]:
    """({openfisca variable: annual amount per person}, `categorie_non_salarie` encoded),
    for one year of the law. Empty, and None, for a frame that carries no self-employment
    columns: a population built before but 19 (étape 2), whose self-employed earned
    nothing; any frame `incomes.attach_incomes` builds carries them."""
    if "regime_non_salarie" not in frame.columns:
        return {}, None
    from impots.population.incomes import CATEGORIE_PAR_SECTEUR

    regime = frame["regime_non_salarie"].to_numpy()
    income = frame["revenu_non_salarie_annuel"].to_numpy().astype(np.float64)
    unknown = {r for r in regime if r is not None} - set(SELF_EMPLOYMENT_INPUTS) - GERANTS
    if unknown:
        raise WiringError(f"régimes non salariés inconnus du câblage : {sorted(unknown)}")
    micro = tax_benefit_system.parameters(year).impot_revenu.calcul_revenus_imposables \
        .rpns.micro.microentreprise
    abatement = {"vente": micro.regime_micro_bic.marchandises.taux,
                 "service": micro.regime_micro_bic.services.taux,
                 "bnc": micro.regime_micro_bnc.taux}
    inputs: dict[str, np.ndarray] = {}
    for name, (variable, nature) in SELF_EMPLOYMENT_INPUTS.items():
        mine = regime == name
        if not mine.any():
            continue
        amount = np.where(mine, income, 0.0)
        if nature is not None:
            amount = micro_turnover(amount, abatement[nature], micro.montant_minimum)
        inputs[variable] = inputs.get(variable, 0.0) + amount
    # A classique's contributions category, which sets his CSG base. Left `non_pertinent`
    # for the micro-entrepreneurs, whose contributions openfisca levies on the versement
    # libératoire's turnover only, and for the farmers, whose MSA contributions and CSG
    # it does not model.
    sector = frame["secteur_non_salarie"].to_numpy()
    reel = np.isin(regime, ("reel_bic", "reel_bnc"))
    names = np.full(frame.height, "non_pertinent", dtype=object)
    names[reel] = [CATEGORIE_PAR_SECTEUR[s] for s in sector[reel]]
    possible = tax_benefit_system.variables["categorie_non_salarie"].possible_values
    return inputs, possible.encode(names.astype(str))


#: The public service's side, as the frame carries it -> openfisca's category (D-346).
CATEGORIE_PUBLIQUE = {"etat": "public_titulaire_etat",
                      "territoriale": "public_titulaire_territoriale",
                      "hospitaliere": "public_titulaire_hospitaliere"}


def public_service(frame: pl.DataFrame, monthly_gross: np.ndarray, tax_benefit_system: Any
                   ) -> tuple[Any, np.ndarray, np.ndarray]:
    """(categorie_salarie, salaire_de_base, traitement_indiciaire_brut), monthly, per person.

    THE PUBLIC SERVICE WAS NOT WIRED until D-346: every earner went to openfisca as a
    private non-executive, so a fifth of the wage bill received the allègements and the
    CNAV and Agirc-Arrco scales. A titular civil servant is now paid a traitement
    indiciaire and openfisca's own primes on it (`TAUX_DE_PRIME`, primes over the
    traitement), so the gross pay the frame carries is split as TIB = gross / (1 + rate);
    a non-titular agent keeps a salaire de base under `public_non_titulaire`. A frame
    without the public columns is refused if it carries a public earner, rather than read
    as all private (D-346)."""
    from openfisca_france.model.base import TAUX_DE_PRIME

    possible = tax_benefit_system.variables["categorie_salarie"].possible_values
    public = (frame["secteur_public"].to_numpy().astype(bool)
              if "secteur_public" in frame.columns else np.zeros(frame.height, dtype=bool))
    if decomposition.sans("E1"):  # every earner private, as before D-346 (D-354)
        public = np.zeros(frame.height, dtype=bool)
    names = np.full(frame.height, "prive_non_cadre", dtype=object)
    tib = np.zeros(frame.height)
    if public.any():
        if not {"fonction_publique", "titulaire"} <= set(frame.columns):
            raise WiringError("population frame carries public earners without their side "
                              "and status (fonction_publique, titulaire) : D-346")
        side = frame["fonction_publique"].to_numpy()
        titular = frame["titulaire"].to_numpy().astype(bool) & public
        for key, name in CATEGORIE_PUBLIQUE.items():
            names[titular & (side == key)] = name
        names[public & ~titular] = "public_non_titulaire"
        tib = np.where(titular, monthly_gross / (1.0 + TAUX_DE_PRIME), 0.0)
        monthly_gross = np.where(titular, 0.0, monthly_gross)
    return possible.encode(names.astype(str)), monthly_gross, tib


def build_simulation(
    frame: pl.DataFrame, tax_benefit_system: Any, year: int,
    niche_bases: dict[str, Any] | None = None,
    capital_bases: dict[str, Any] | None = None,
) -> PopulationSimulation:
    """Wire a population frame into a vectorised simulation for `year`.

    `niche_bases` maps a déclaration case to an array ordered by `foyer_ids`, in euros
    and for the simulated year only. Individual-level cases — `f7ac` is the only one —
    are scattered onto each foyer's principal declarant, since the entitlement follows
    the member and openfisca will silently ignore a foyer-shaped array written to an
    individual variable.

    `capital_bases` has the same shape and is written on every year of the history, as
    the earnings are (D-248).
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
    categorie, monthly_salary, monthly_tib = public_service(frame, monthly_salary,
                                                            tax_benefit_system)
    # Pensions and unemployment benefit are monthly individual inputs too. Leaving
    # them out is not a visible failure: the simulation runs, every guard passes,
    # and 14 M pensioners simply appear to live on nothing — which then shows up
    # three steps away as an RSA bill three times the published one.
    monthly_pension = (frame["pension_annuelle"].to_numpy() / 12.0).astype(np.float64)
    monthly_chomage = (frame["chomage_annuel"].to_numpy() / 12.0).astype(np.float64)
    # The sick pay `population.ij` imputes, when the run asked for it (D-305): openfisca
    # reads it in the RSA's, the prime's, the ASS's and the ASPA's resources only.
    monthly_ij = {
        variable: (frame[column].to_numpy() / 12.0).astype(np.float64)
        for variable, column in IJ_INPUTS.items() if column in frame.columns
    }
    if monthly_ij and len(monthly_ij) != len(IJ_INPUTS):
        raise WiringError(f"population frame carries only part of the sick pay "
                          f"{sorted(IJ_INPUTS.values())}")
    for variable in IJ_PROJECT_INPUTS & set(monthly_ij):
        if variable not in tax_benefit_system.variables:
            del monthly_ij[variable]

    # ---- ménage inputs, ordered to match `household_ids` -------------------
    menage = _group_frame(
        frame, "household_id", ["statut_occupation", "zone_apl", "loyer_mensuel"]
    )
    if menage.height != household_ids.size:
        raise WiringError("ménage-level frame does not line up with the declared ménages")
    statut = _text(menage["statut_occupation"])
    zone = _text(menage["zone_apl"])
    loyer = menage["loyer_mensuel"].to_numpy().astype(np.float64)
    # The DOM (étape al): the drawn département, as a commune code openfisca's
    # `residence_<dom>` read by their prefix. Metropole keeps the default, the empty
    # string, so that nothing else reading `depcom` moves there.
    depcom = None
    if "departement" in frame.columns:
        depcom = _text(_group_frame(frame, "household_id", ["departement"]).select(
            (pl.col("departement") + "01").fill_null(""))["departement"])

    for offset in range(HISTORY_YEARS, -1, -1):
        for month in range(1, 13):
            period = f"{year - offset}-{month:02d}"
            simulation.set_input("salaire_de_base", period, monthly_salary)
            simulation.set_input("traitement_indiciaire_brut", period, monthly_tib)
            simulation.set_input("categorie_salarie", period, categorie)
            simulation.set_input("retraite_brute", period, monthly_pension)
            # Failure mode #4. `pension_annuelle` is calibrated on DECLARED pensions,
            # so it is pinned on the declared box as well; see the module docstring.
            simulation.set_input("retraite_imposable", period, monthly_pension)
            simulation.set_input("chomage_brut", period, monthly_chomage)
            for variable, values in monthly_ij.items():
                simulation.set_input(variable, period, values)
            simulation.set_input("statut_occupation_logement", period, statut)
            simulation.set_input("zone_apl", period, zone)
            simulation.set_input("loyer", period, loyer)
            if depcom is not None:
                simulation.set_input("depcom", period, depcom)

    # ---- the self-employed's income, on each year of the history -----------
    # Annual boxes, written N-2 to N as the earnings are: the RSA and the prime read the
    # last known year, the housing aid N-2, and the RFR of N-2 is pinned below.
    for offset in range(HISTORY_YEARS, -1, -1):
        inputs, categorie_ns = self_employment_inputs(frame, tax_benefit_system,
                                                      year - offset)
        for variable, values in inputs.items():
            simulation.set_input(variable, str(year - offset), values)
        if categorie_ns is not None:
            simulation.set_input("categorie_non_salarie", str(year - offset), categorie_ns)

    # ---- the exempt share of the salaries (correction 24), each year of the history -----
    # Written only where the system carries the variable: raw openfisca, which the kill
    # tests run, has none, and a frame built before the étape « ir » no column.
    variable, column = EXEMPT_SHARE_INPUT
    if column in frame.columns and variable in tax_benefit_system.variables:
        share = frame[column].fill_null(0.0).to_numpy().astype(np.float64)
        for offset in range(HISTORY_YEARS, -1, -1):
            simulation.set_input(variable, str(year - offset), share)

    # ---- foyer fiscal inputs, ordered to match `foyer_ids` -----------------
    foyer = _group_frame(frame, "foyer_id", ["parent_isole"])
    if foyer.height != foyer_ids.size:
        raise WiringError("foyer-level frame does not line up with the declared foyers")
    # Failure mode #7. Case T on every year of the history, as the household builder
    # writes it: the rate of the CSG on a pension or an unemployment benefit reads the
    # parts of N-2. The survey sees the foyer in N only, so N-2 and N-1 take its case T,
    # the steady state the income history already assumes.
    parent_isole = foyer["parent_isole"].to_numpy().astype(bool)
    for offset in range(HISTORY_YEARS, -1, -1):
        simulation.set_input("caseT", str(year - offset), parent_isole)
    # The fiscal domicile of a DOM foyer, for the income tax's DOM abattement, on every
    # year of the history, before the RFR of N-2 is pinned. A foyer lives in one ménage.
    if "departement" in frame.columns:
        depcom_foyer = _text(_group_frame(frame, "foyer_id", ["departement"]).select(
            (pl.col("departement") + "01").fill_null("00000"))["departement"])
        for offset in range(HISTORY_YEARS, -1, -1):
            simulation.set_input("depcom_foyer", str(year - offset), depcom_foyer)

    if niche_bases:
        _set_niche_inputs(
            simulation, tax_benefit_system, year, niche_bases, frame, foyer_ids)
    # The capital income on every year of the history, as the earnings are: the RFR of
    # N-2, which sets the CSG rate on a pension, holds it (D-248).
    if capital_bases:
        _set_niche_inputs(
            simulation, tax_benefit_system, year, capital_bases, frame, foyer_ids,
            years=tuple(year - offset for offset in range(HISTORY_YEARS, -1, -1)))

    # Failure mode #5, and last on purpose: the RFR of N-2 is computed from the inputs
    # of N-2, so every one of them must already be set.
    pin_rfr_n_2(simulation, year)

    return PopulationSimulation(
        simulation=simulation,
        year=year,
        household_ids=household_ids,
        foyer_ids=foyer_ids,
        famille_ids=famille_ids,
        n_persons=n_persons,
    )
