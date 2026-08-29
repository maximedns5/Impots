"""HouseholdInput -> OpenFisca situation dict (spec §3.2).

The wiring rules, verified against openfisca-france 176.0.8:

    individu      -> `individus`
    foyer_fiscal  -> `foyers_fiscaux`   roles: declarants, personnes_a_charge
    famille       -> `familles`         roles: parents, enfants
    menage        -> `menages`          roles: personne_de_reference, conjoint, enfants

Every adult appears in `declarants`, `parents` and exactly one of
`personne_de_reference` / `conjoint`. Every child appears in `personnes_a_charge`,
`familles.enfants` and `menages.enfants`. One foyer fiscal, one famille, one ménage:
Phase 0 models a single person or a married/pacsé couple only.

`salaire_de_base` is a **monthly** input, so the annual figure the user types is
divided by 12 and written to each of the twelve months. `date_naissance` is set at
`"ETERNITY"`.

**Income history.** Means-tested benefits are not assessed on the simulated year:
RSA and the prime d'activité look back a quarter, and the aide au logement looks
back a rolling twelve months ending thirteen months before the month it pays. Fill
in only the target year and the engine sees a household that earned nothing in
every reference window, and pays accordingly — a single on 30 000 € renting at
600 €/month is awarded 1 989 € of housing aid and 535 € of RSA it is not entitled
to, overstating disposable income by 2 485 € (11 %).

`historique_revenus` writes the same salary and housing across years N-2, N-1 and
N, which removes the error. It is **on by default** (D-011): the single-year
wiring is not a defensible default for anyone, and the population engine cannot
use it at all — the benefits cascade *crashes* at population scale without the
lookback months. Pass `historique_revenus=False` to reproduce the Phase 0 wiring;
`test_income_history_removes_phantom_benefits` keeps both modes measured. See
D-005 and D-011.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - typing only
    from impots.api.schemas import HouseholdInput

FOYER_FISCAL_ID = "ff_0"
FAMILLE_ID = "fam_0"
MENAGE_ID = "men_0"


#: Years of salary history written when `historique_revenus` is on. Two is enough:
#: the longest reference window in play is the aide au logement's rolling twelve
#: months ending in November of N-1.
HISTORY_YEARS = 2


def months(year: int) -> list[str]:
    """The twelve monthly period strings of `year`."""
    return [f"{year}-{m:02d}" for m in range(1, 13)]


def covered_years(year: int, historique: bool) -> list[int]:
    """Which years the situation supplies inputs for."""
    return list(range(year - HISTORY_YEARS, year + 1)) if historique else [year]


def adult_id(i: int) -> str:
    return f"adulte_{i}"


def child_id(i: int) -> str:
    return f"enfant_{i}"


def _period_keys(variable_name: str, years: list[int]) -> list[str]:
    """The period keys under which `variable_name` must be supplied as an input.

    Read from the live variable definition rather than assumed: getting a period
    wrong yields a silent zero, not an error, and several of these variables use
    `set_input_divide_by_period` — writing `{"2024": 600}` to the monthly `loyer`
    would mean 50 €/month, not 600. Reforms only touch parameters, never variable
    definitions, so the baseline system is authoritative here.
    """
    from impots.engine.system import baseline

    variable = baseline().variables.get(variable_name)
    if variable is None:  # pragma: no cover - guarded by the registry tests
        raise KeyError(f"unknown OpenFisca variable {variable_name!r}")
    period = str(variable.definition_period).lower()
    if period == "eternity":
        return ["ETERNITY"]
    if period == "month":
        return [month for year in years for month in months(year)]
    return [str(year) for year in years]


def _spread(variable_name: str, annual_value: float, years: list[int]) -> dict[str, float]:
    """Write an annual amount onto the periods the variable uses, in every year."""
    keys = _period_keys(variable_name, years)
    per_year = len(keys) / len(years) if years else 1
    return {key: annual_value / per_year for key in keys}


def _constant(variable_name: str, value: Any, years: list[int]) -> dict[str, Any]:
    """Write the same value onto every period the variable uses (not divided)."""
    return dict.fromkeys(_period_keys(variable_name, years), value)


def _coerce_enum(variable_name: str, value: Any) -> Any:
    """Accept either an enum member name or its integer index for an Enum variable.

    The wire format takes `zone_apl` as an int (1/2/3) because that is how users
    think about APL zones, while the engine wants the enum member. Non-enum
    variables pass straight through.
    """
    from impots.engine.system import baseline

    variable = baseline().variables.get(variable_name)
    possible = getattr(variable, "possible_values", None)
    if possible is None:
        return value
    names = [member.name for member in possible]
    if isinstance(value, str):
        if value in names:
            return value
        raise ValueError(
            f"{variable_name}={value!r} inconnu ; valeurs acceptées : {', '.join(names)}"
        )
    if isinstance(value, bool):  # bool is an int subclass — reject it explicitly
        # ValueError, not TypeError: the API turns ValueError into a 422, which is
        # what a bad input deserves. A TypeError would surface as a 500.
        raise ValueError(
            f"{variable_name} attend un nom d'énumération ou un entier, pas un booléen"
        )
    if isinstance(value, int):
        # Users pass APL zones as 1/2/3; enum members are 0-indexed and may or may
        # not carry a leading "non renseigné" member, so match on the name suffix.
        for name in names:
            if name.rstrip("_").endswith(str(value)):
                return name
        raise ValueError(
            f"{variable_name}={value!r} ne correspond à aucune valeur ; "
            f"valeurs acceptées : {', '.join(names)}"
        )
    return value


def build_situation(
    household: HouseholdInput, year: int, historique_revenus: bool = True
) -> dict[str, Any]:
    """Build the OpenFisca situation dict for one household and one year.

    With `historique_revenus` (the default since D-011), the same salary and housing
    are also written to the two preceding years, so that means-tested benefits are
    assessed against a realistic reference period instead of an empty one.
    """
    years = covered_years(year, historique_revenus)
    individus: dict[str, dict[str, Any]] = {}

    adult_ids: list[str] = []
    for i, adult in enumerate(household.adults):
        key = adult_id(i)
        adult_ids.append(key)
        individus[key] = {
            "salaire_de_base": _spread("salaire_de_base", adult.salaire_brut_annuel, years),
            "date_naissance": {"ETERNITY": f"{adult.annee_naissance}-01-01"},
        }

    child_ids: list[str] = []
    for i, child in enumerate(household.children):
        key = child_id(i)
        child_ids.append(key)
        individus[key] = {"date_naissance": {"ETERNITY": f"{child.annee_naissance}-01-01"}}

    menage: dict[str, Any] = {"personne_de_reference": [adult_ids[0]]}
    if len(adult_ids) > 1:
        menage["conjoint"] = [adult_ids[1]]
    if child_ids:
        menage["enfants"] = list(child_ids)

    if household.logement is not None:
        menage.update(_housing_inputs(household.logement, years))

    foyer_fiscal: dict[str, Any] = {"declarants": list(adult_ids)}
    if child_ids:
        foyer_fiscal["personnes_a_charge"] = list(child_ids)
    if household.resolved_parent_isole():
        # `caseT` — "parent isolé au 1er janvier". Worth half a part, and the only
        # lever for it: `nbptr` multiplies the `isol` parameter by caseT directly,
        # and nothing is inferred from the shape of the household. Without it a
        # single parent with one child gets 1.5 parts instead of 2.0 and is
        # over-taxed. The Phase 0 spec does not mention it; see DECISIONS D-006.
        foyer_fiscal["caseT"] = _constant("caseT", True, years)

    return {
        "individus": individus,
        "foyers_fiscaux": {FOYER_FISCAL_ID: foyer_fiscal},
        "familles": {
            FAMILLE_ID: {
                "parents": list(adult_ids),
                **({"enfants": list(child_ids)} if child_ids else {}),
            }
        },
        "menages": {MENAGE_ID: menage},
    }


def _housing_inputs(logement: Any, years: list[int]) -> dict[str, Any]:
    """Ménage-level housing inputs.

    `statut_occupation_logement` and `loyer` are both required for any housing aid:
    either one alone yields zero, silently. `zone_apl` is never truly absent — the
    engine defaults it to zone 2 — so the wire format always carries it explicitly
    rather than letting a substantive assumption go unstated.
    """
    return {
        "statut_occupation_logement": _constant(
            "statut_occupation_logement",
            _coerce_enum("statut_occupation_logement", logement.statut),
            years,
        ),
        "loyer": _spread("loyer", logement.loyer_mensuel * 12.0, years),
        "zone_apl": _constant("zone_apl", _coerce_enum("zone_apl", logement.zone_apl), years),
    }


def perturb_first_adult(situation: dict[str, Any], year: int, delta_annual: float) -> dict[str, Any]:
    """A copy of `situation` with `delta_annual` EUR added to the first adult's gross
    salary **in `year` only**. Used for the EMTR finite difference (spec §3.5).

    Scoped to the target year on purpose: with an income history in place the salary
    dict spans three years, and spreading the bump across all of them would perturb
    the marginal euro by a third of what the EMTR assumes.
    """
    import copy

    perturbed = copy.deepcopy(situation)
    salaries = perturbed["individus"][adult_id(0)]["salaire_de_base"]
    target = [key for key in salaries if key.startswith(f"{year}-") or key == str(year)]
    per_period = delta_annual / len(target)
    for key in target:
        salaries[key] += per_period
    return perturbed
