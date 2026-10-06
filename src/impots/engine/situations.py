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


def pin_rfr_n_2(simulation: Any, year: int) -> None:
    """Compute the RFR of N-2 before anything else asks for it, and pin it as an input.

    Every CSG on a replacement income — pensions and unemployment benefit alike — takes
    its rate from the RFR of N-2. openfisca cuts ANY nested evaluation of a variable at
    another period (`max_spiral_loops = 1`), so when that RFR is first asked for from
    inside a year-N computation — the income tax, with `rni` of N on the stack — its own
    `rni` of N-2 is cut to zero, and the rate read through it is the exemption. That is
    how the income tax came to assess a 30 000 EUR chômeur on the gross amount and how
    `revenu_disponible` came to miss the CSG and CRDS owed on it, by evaluation order (D-177).

    Asked for first, on its own, the RFR of N-2 runs the year N-2 chain whole. The only
    cut is then the RFR of N-4 itself, a year where nothing is supplied, so the CSG of
    N-2 is the exemption and the replacement income of N-2 enters gross: the one
    assumption this pin makes, measured in D-177. Pinned, no later computation reopens
    it, in whatever order it runs.

    Since D-192 the RFR of N-2 holds a claimant's ASS of N-2, whose resources read the
    replacement incomes of the twelve months before, net of a CSG whose rate reads the RFR
    of N-4 and N-5: the same cut, on years where nothing is supplied. The ASS that enters it
    is the one a hand computation gives, 6 292.80 EUR for a claimant alone in 2022, so an
    RFR of 5 663.80 (`test_the_ass_is_taxed_as_a_salary_after_the_ten_per_cent_deduction`).

    Called by both builders, once every input is set: the household one and
    `population.to_openfisca`. Each simulation pins its own, under its own tax-benefit
    system, so a reform reads the RFR of N-2 its own parameters give.
    """
    period = str(year - 2)
    simulation.set_input("rfr", period, simulation.calculate("rfr", period))


#: The months of housing aid pinned by `pin_benefit_history`, oldest first: the reference
#: quarter of January's prime d'activité (October to December of N-1), then every month
#: of N. Starting earlier, in January of N-1, gives the same answer to the cent on the
#: fixture population and on the 120 points of the renter EMTR curve, at twice the cost.
HOUSING_MONTHS_BEFORE_N = (10, 11, 12)


def pin_benefit_history(simulation: Any, year: int) -> None:
    """Pin the housing aid month by month, oldest first, before any benefit is asked for.

    Housing aid and the RSA feed each other through the months: the aid's neutralisation
    reads the RSA of the month before, whose forfait logement reads the aid of that
    month, and the prime d'activité reads the aid of its reference quarter. With the aid
    of one month on the stack, openfisca cuts the aid of the month before to zero
    (`pin_rfr_n_2` says why), so the PPA of January to March could lose the forfait
    logement of its quarter, by evaluation order (D-178). Computed oldest first, each
    month finds the one before it already pinned, and nothing is cut. The first one,
    October of N-1, reads September as zero aid in the RSA's forfait: the assumption,
    measured as changing nothing in D-178.

    The amount the MVA reads, `aide_logement_montant`, is pinned beside the aid. Since
    D-203 the ASPA and the ASI of a month count a spouse's MVA of the three months before,
    and the housing aid reaches them through its student-grant test and the RSA's
    resources (D-179). Left to the cache, each month's amount was purged at the end of its
    own pin, invalidated by a spiral beneath it, then cut to zero under the next month's
    pin, and an ASI computed there stayed cached without the MVA (correction 19). The
    value pinned is the one the aid was just computed from, still cached, or, where a
    spiral purged it, recomputed with the aid of the month and of the months before pinned.

    The RFR of the four years before the income history is computed and pinned first.
    Nothing is supplied there, so it is zero either way; pinned, the housing chain stops
    reopening the empty years 2016 to 2021 month after month, which is where most of the
    cost went. Only for a simulation that will compute benefits: the light tier never
    asks for one and must not pay for this.
    """
    for empty in range(year - 3, year - 7, -1):
        simulation.set_input("rfr", str(empty), simulation.calculate("rfr", str(empty)))
    pinned = [f"{year - 1}-{m:02d}" for m in HOUSING_MONTHS_BEFORE_N] + months(year)
    for month in pinned:
        simulation.set_input("aide_logement", month, simulation.calculate("aide_logement", month))
        simulation.set_input("aide_logement_montant", month,
                             simulation.calculate("aide_logement_montant", month))


#: The inputs that open the AAH, the ASI or the ASS. The disability field writes the first
#: since D-184, the invalidity pension field the second since D-190, and the « fin de
#: droits » field the last since D-189. The other, `handicap`, the child's field writes since
#: D-191, on a child where the AEEH is open; on an adult a situation carries it only when
#: someone adds it, as the D-179 tests do for the ASI.
MINIMA_INPUTS = ("taux_incapacite", "pensions_invalidite", "handicap", "ass_precondition_remplie")


#: The 2042 boxes the invalidity card is declared in, in the order of the adults: case P
#: for the declarant, case F for the spouse (D-188).
INVALIDITY_CASES = ("caseP", "caseF")

#: Case 7DG of the 2042, in its home-help section: the ceiling of 20 000 EUR of the credit for
#: employing someone at home (CGI art. 199 sexdecies, 3), a boolean of the foyer fiscal that only
#: that credit reads. Ticked by the builder, never typed (D-196).
HOME_HELP_INVALIDITY_CASE = "f7dg"


def has_benefit_cascade(situation: dict[str, Any]) -> bool:
    """Whether `pin_benefit_history` has anything to protect in this situation.

    A dwelling opens the housing aid's circle with the RSA (D-178). An AAH opens another,
    dwelling or not: the ASPA and the ASI count the household's AAH of the three months
    before. `revenu_disponible` computed first reaches the AAH of a month through the
    PAJE's childcare supplement, under the CRDS of the IFI cap, and beneath that AAH the
    ASI of the month before reads a family base where the AAH of earlier months is cut to
    zero. That base stays cached for the rest of the computation, and the partner's ASPA
    or ASI read it: 1 800 EUR of disposable income by evaluation order on an unhoused
    couple (D-179).

    The housing-aid pin closes this circle too, as a side effect. Each month's housing
    aid, zero without a dwelling but evaluated all the same, reaches that month's ASPA
    through its student-grant test, which reads the RSA's resources. No AAH is on the
    stack there, so the family base it caches counts the AAH in full. The D-179 tests
    guard that. A household with neither a dwelling nor one of `MINIMA_INPUTS` has no
    circle to close, and its full tier keeps its cost.

    A child's disability writes `handicap` on the child since D-191. There the flag opens
    the AEEH, which reads no resource, and no ASI, which needs a pension: on a household
    without a dwelling the pin runs for nothing, about 1.5 s, and moves no figure in
    either evaluation order (measured). Left so, rather than read the flag by role.
    """
    housed = "statut_occupation_logement" in situation["menages"][MENAGE_ID]
    return housed or any(
        name in person for person in situation["individus"].values() for name in MINIMA_INPUTS)


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


def _this_year(variable_name: str, value: Any, year: int) -> dict[str, Any]:
    """Write a value onto the target year ONLY, never onto the income history.

    `_spread` and `_constant` both write every covered year, which is right for a
    salary or a housing status — the history is there so means-tested benefits get a
    realistic reference period. It is wrong for a niche base: a donation declared in
    2024 is a 2024 fact, and copying it to 2023 and 2022 would assert three identical
    years of charitable giving that nobody claimed.
    """
    return dict.fromkeys(_period_keys(variable_name, [year]), value)


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
    assert_ass_expressible(household, year)
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
        if adult.pension_annuelle:
            # Monthly, like the salary, and on the same years: the population build
            # writes these two this way too, so one pensioner prices the same on both
            # paths.
            #
            # The declared amount is ALSO pinned on `retraite_imposable` (box 1AS),
            # whose formula `retraite_brute + csg_deductible_retraite` would otherwise
            # run. The rate of that CSG reads the RFR of N-2, which reads
            # `retraite_imposable` of N-2: a regress openfisca cuts at its second turn,
            # wherever the evaluation order puts it. Left to run, the same household
            # priced two ways — 2 065 EUR of disposable income apart on a 50 000 EUR
            # pensioner — and the EMTR compared one with the other (D-176). Pinned, the
            # income tax never asks for that CSG, and the levies still due on a
            # declared pension (CSG imposable, CRDS, CASA) read an RFR of N-2 that no
            # longer depends on it. Their base stays `retraite_brute`, the declared
            # amount, about 6 % under the gross one: accepted and measured in D-176.
            individus[key]["retraite_brute"] = _spread(
                "retraite_brute", adult.pension_annuelle, years)
            individus[key]["retraite_imposable"] = _spread(
                "retraite_imposable", adult.pension_annuelle, years)
        if adult.chomage_brut_annuel:
            # Gross, like the population's `chomage_annuel`, so it cannot be pinned on
            # its taxable box the way a declared pension is: the CSG that takes it there
            # reads the RFR of N-2, and that regress is closed by `pin_rfr_n_2` instead
            # (D-177). Neither path sets `activite` or `date_debut_chomage` for it (the
            # « fin de droits » field writes `activite`, and is refused beside this
            # benefit, D-189). Without a salary beside the benefit they move nothing
            # reported; with one, they would take 30 % off it in the housing aid, a relief
            # for the fall in income on passing from work to unemployment, which a salary
            # earned beside the benefit in every year of the history is not (D-183).
            individus[key]["chomage_brut"] = _spread(
                "chomage_brut", adult.chomage_brut_annuel, years)
        if adult.pension_invalidite_annuelle:
            # Declared, like the retirement pension: openfisca's `pensions_invalidite` IS box
            # 1AZ, taxed with the pensions, and no formula of openfisca takes a gross
            # invalidity pension to it. Monthly, on the same years as the salary: the RFR of
            # N-2 sets the rate of its levies, and the ASI and the AAH read the months before.
            # The levies themselves are correction 9 of `engine.corrections` (D-190).
            individus[key]["pensions_invalidite"] = _spread(
                "pensions_invalidite", adult.pension_invalidite_annuelle, years)
            # At 62 the invalidity pension gives way to a retirement pension, and « A cet âge,
            # les intéressés sont réputés inaptes au travail » and may claim the ASPA, which
            # ends the ASI (circular Cnav 2023-25). openfisca opens the ASPA early on this
            # flag, from `aah.age_legal_retraite` (62, correction 3), and reads it nowhere
            # else for a parent of the famille: written on every month, it acts from 62 only.
            # Without it the ASI ran on to 65, below the ASPA's ceiling (D-190).
            individus[key]["inapte_travail"] = _constant("inapte_travail", True, years)
        if adult.handicap is not None:
            individus[key].update(_disability_inputs(adult.handicap, years))
        if adult.fin_de_droits_ass:
            individus[key].update(_ass_inputs(years))
    if household.situation_famille != "celibataire":
        # A lone adult's situation de famille, divorced or widowed, under openfisca's own name
        # (D-197). `statut_marital` is monthly, and the income tax reads it in January, on the
        # declarant: written on every covered month like the salary, since the CSG of a
        # replacement income reads the parts of N-2. Célibataire, the default, is what
        # openfisca's formula answers for a lone declarant, and writes nothing. The wire
        # format refuses a situation beside a spouse, so the adult is the only one.
        individus[adult_ids[0]]["statut_marital"] = _constant(
            "statut_marital", _coerce_enum("statut_marital", household.situation_famille), years)

    child_ids: list[str] = []
    for i, child in enumerate(household.children):
        key = child_id(i)
        child_ids.append(key)
        individus[key] = {"date_naissance": {"ETERNITY": f"{child.annee_naissance}-01-01"}}
        if child.handicap is not None:
            individus[key].update(_child_disability_inputs(child, year, years))

    menage: dict[str, Any] = {"personne_de_reference": [adult_ids[0]]}
    if len(adult_ids) > 1:
        menage["conjoint"] = [adult_ids[1]]
    if child_ids:
        menage["enfants"] = list(child_ids)

    if household.logement is not None:
        menage.update(_housing_inputs(household.logement, years))

    if household.niches is not None:
        from impots.api import schemas

        assert_niche_eligibility(household, year)
        for index, amount in enumerate(household.niches.cotisations_syndicales):
            if index < len(adult_ids) and amount:
                individus[adult_ids[index]][schemas.NICHE_SYNDICALES_CASE] = _this_year(
                    schemas.NICHE_SYNDICALES_CASE, float(amount), year)

    foyer_fiscal: dict[str, Any] = {"declarants": list(adult_ids)}
    if child_ids:
        foyer_fiscal["personnes_a_charge"] = list(child_ids)
    if household.niches is not None:
        foyer_fiscal.update(_niche_inputs(household.niches, year))
    if household.patrimoine is not None:
        foyer_fiscal.update(_patrimoine_inputs(household.patrimoine, year))
    if household.resolved_parent_isole():
        # `caseT` — "parent isolé au 1er janvier". Worth half a part, and the only
        # lever for it: `nbptr` multiplies the `isol` parameter by caseT directly,
        # and nothing is inferred from the shape of the household. Without it a
        # single parent with one child gets 1.5 parts instead of 2.0 and is
        # over-taxed. The Phase 0 spec does not mention it; see DECISIONS D-006.
        foyer_fiscal["caseT"] = _constant("caseT", True, years)
    for adult, case in zip(household.adults, INVALIDITY_CASES, strict=False):
        if adult.carte_invalidite:
            # The card « mobilité inclusion » marked « invalidité »: case P for the
            # declarant, F for the spouse, booleans of the foyer fiscal, and not
            # openfisca's individual `invalidite`, which counts dependent children only
            # (cases G and I). On every covered year, like the salary: the housing aid
            # and the family benefits take the abatement of art. 157 bis it opens off the
            # resources of N-2, and the CSG of a replacement income reads the RFR and the
            # parts of N-2 (D-188).
            foyer_fiscal[case] = _constant(case, True, years)
    if (household.niches is not None and household.niches.salarie_domicile
            and _opens_the_home_help_invalidity_ceiling(household)):
        # Case 7DG, beside the home help of case 7DB and like it on N alone: the credit of N
        # reads both of N, and nothing reads the credit of another year (D-196).
        foyer_fiscal[HOME_HELP_INVALIDITY_CASE] = _this_year(
            HOME_HELP_INVALIDITY_CASE, True, year)

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


#: A child is under six at 1 January of `year` when born in `year - 6` or later. Only
#: the birth YEAR is carried, so a child born on 1 January of `year - 6` is treated as
#: eligible when they are in fact exactly six — the one day of the year this is wrong,
#: and stated rather than silently rounded.
CHILDCARE_MAX_AGE = 6


def assert_niche_eligibility(household: Any, year: int) -> None:
    """Refuse niche declarations the household cannot support.

    **openfisca applies no eligibility test to these cases and this is not an
    oversight**: they are boxes on the 2042, and the engine trusts the declarant the
    way the paper form does. Measured — a household with a fifteen-year-old receives
    the childcare credit, and so does a household with no children at all.

    That is fine for a tax engine and wrong for a calculator someone uses to decide
    something, so the check lives here. It raises ValueError, which the API turns into
    a 422 rather than a 500.
    """
    niches = getattr(household, "niches", None)
    if niches is None:
        return

    claimed = [amount for amount in niches.frais_garde_par_enfant if amount]
    eligible = sum(
        1 for child in household.children
        if child.annee_naissance >= year - CHILDCARE_MAX_AGE
    )
    if len(claimed) > eligible:
        raise ValueError(
            f"frais_garde_par_enfant déclare {len(claimed)} enfant(s) gardé(s) mais le "
            f"foyer ne compte que {eligible} enfant(s) de moins de {CHILDCARE_MAX_AGE} "
            f"ans au 1er janvier {year}. Le moteur ne vérifie pas l'âge — il ferait le "
            f"calcul sans broncher, et même pour un foyer sans enfant."
        )

    dues = [amount for amount in niches.cotisations_syndicales if amount]
    if len(dues) > len(household.adults):
        raise ValueError(
            f"cotisations_syndicales déclare {len(dues)} adhérent(s) pour "
            f"{len(household.adults)} adulte(s) dans le foyer."
        )

    scolarises = niches.declared_school_children
    if scolarises > len(household.children):
        raise ValueError(
            f"les frais de scolarité déclarent {scolarises} enfant(s) scolarisé(s) pour "
            f"{len(household.children)} enfant(s) à charge."
        )


#: The lowest legal retirement age of the years this project prices: 62, for those born
#: from 1955 to August 1961 (CSS art. D. 161-2-1-9, 6°). From that age the ASS stops for
#: whoever has the insurance duration of the full rate, and at 67 for everyone (C. trav.
#: art. L. 5421-4, 1° and 2°).
ASS_AGE_LEGAL = 62


def assert_ass_expressible(household: Any, year: int) -> None:
    """Refuse « fin de droits » from the year of the 62nd birthday.

    From the legal retirement age the ASS « cesse d'être versé » to whoever justifies the
    insurance duration required for a full-rate pension (C. trav. art. L. 5421-4, 1°),
    and the wire format does not carry that duration. openfisca stops it at 789 months,
    65 years and 9 months, an age the law of 2024 does not name. Refused rather than paid
    or withheld on a guess (D-189). The year is the builder's, so the refusal is here and
    not in the wire format. ValueError, which the API turns into a 422.
    """
    for index, adult in enumerate(household.adults):
        age = year - adult.annee_naissance
        if getattr(adult, "fin_de_droits_ass", False) and age >= ASS_AGE_LEGAL:
            raise ValueError(
                f"Adulte {index + 1} : la fin de droits n'est pas exprimable à {age} ans en "
                f"{year}. Dès l'âge légal de départ en retraite, {ASS_AGE_LEGAL} ans au plus "
                f"tôt, l'ASS cesse pour qui a la durée d'assurance du taux plein, et à 67 ans "
                f"pour tous (C. trav. art. L. 5421-4) ; le format d'entrée ne dit pas la durée "
                f"d'assurance. Refusé à partir de l'année des {ASS_AGE_LEGAL} ans plutôt que "
                f"versé ou retenu au hasard."
            )


def _ass_inputs(years: list[int]) -> dict[str, Any]:
    """« En fin de droits, condition d'activité remplie », on every covered month: the
    work condition openfisca reads as `ass_precondition_remplie`, and a job seeker's
    `activite`, which the ASS is for (C. trav. art. L. 5423-1).

    Without a salary, which the wire format refuses beside the ASS, the precondition alone
    opens it. `activite` decides what a salary does to it: openfisca keeps a job seeker's
    ASS whatever is earned beside it, as the cumul does for the first three months of a
    resumed activity (art. R. 5425-2), and otherwise counts those three months and stops
    it. The EMTR's bumped leg is such a salary: a job seeker's 100 EUR is priced beside the
    ASS, and without `activite` the ASS stopped in April (D-189).
    """
    return {
        "ass_precondition_remplie": _constant("ass_precondition_remplie", True, years),
        "activite": _constant("activite", _coerce_enum("activite", "chomeur"), years),
    }


def _disability_inputs(handicap: Any, years: list[int]) -> dict[str, Any]:
    """The CDAPH's decision, on every covered month: the rate, and the restriction on
    access to employment when recognised. Not openfisca's generic `handicap` flag, which
    would open the ASI beside a retirement pension (`api.schemas.Handicap`, D-184)."""
    inputs = {"taux_incapacite": _constant("taux_incapacite", handicap.taux_incapacite, years)}
    if handicap.restriction_substantielle_durable_acces_emploi:
        inputs["aah_restriction_substantielle_durable_acces_emploi"] = _constant(
            "aah_restriction_substantielle_durable_acces_emploi", True, years)
    return inputs


def _child_disability_inputs(child: Any, year: int, years: list[int]) -> dict[str, Any]:
    """A child's disability (`api.schemas.HandicapEnfant`, D-191), on every covered month.

    Where the AEEH is open, openfisca's generic `handicap` flag, which its AEEH reads, and
    the complément's category with it; for the card, `invalidite`, which gives the
    half-part. The rate is not written: it decided all this, and openfisca reads it for
    nobody under 20 who is a dependant (the AAH opens at 20). On a child the flag also
    lifts the housing aid's taper, as CCH art. D. 823-16 does for an AEEH beneficiary; the
    household's `has_benefit_cascade` then holds, and the pin of D-178 runs, moving no
    figure.

    A child of 20 or more in the year simulated is refused: the AEEH has stopped, the
    disability is then an adult's (the AAH), and the flag would still lift the taper.
    Under 20 that year, the child is under 20 on every covered month."""
    from impots.api import schemas

    age = year - child.annee_naissance
    if age >= schemas.AEEH_AGE_MAXIMUM:
        raise ValueError(
            f"Le handicap d'un enfant de {age} ans n'est pas modélisé : l'AEEH s'arrête à "
            f"{schemas.AEEH_AGE_MAXIMUM} ans (CSS art. R. 512-2), et au-delà c'est l'AAH d'un "
            f"adulte, que le champ de l'enfant n'ouvre pas."
        )
    handicap = child.handicap
    inputs: dict[str, Any] = {}
    if handicap.ouvre_aeeh:
        inputs["handicap"] = _constant("handicap", True, years)
        if handicap.complement_categorie is not None:
            inputs["aeeh_niveau_handicap"] = _constant(
                "aeeh_niveau_handicap", handicap.complement_categorie, years)
    if handicap.carte_invalidite:
        inputs["invalidite"] = _constant("invalidite", True, years)
    return inputs


def _opens_the_home_help_invalidity_ceiling(household: Any) -> bool:
    """Whether a member of the foyer opens the 20 000 EUR ceiling of the home-help credit, case
    7DG, as far as the wire format can say it (D-196).

    CGI art. 199 sexdecies, 3 gives it to an invalidity pensioner of the third category (CSS
    art. L. 341-4, 3°), to whoever has such a person in their charge under their roof, and to
    whoever has in their charge « un enfant donnant droit au complément d'allocation d'éducation
    de l'enfant handicapé prévu par le deuxième alinéa de l'article L. 541-1 ». The BOFiP gives
    it, « en pratique », to a foyer one of whose members holds the card « mobilité inclusion »
    marked « invalidité », or « sans être titulaire de la carte », draws the pension of the third
    category or the complément (BOI-IR-RICI-150-20, § 180), and the 2042 asks: « Vous (ou votre
    conjoint ou une personne à charge) avez la carte d'invalidité ou la carte mobilité inclusion,
    mention “invalidité” ».

    So an adult's card (cases P and F), a dependent child's card, and a child's complément of
    the AEEH, whatever its category: the format grants one only where the AEEH is open, and the
    builder refuses a child of 20 or more before this is asked. Not a child's AEEH alone, nor a
    disability without the card. The third category is not in the format, which carries the
    invalidity pension without it; its pensioner has the card for the asking (CASF art.
    L. 241-3), and through the card, this ceiling."""
    if any(adult.carte_invalidite for adult in household.adults):
        return True
    return any(
        child.handicap is not None
        and (child.handicap.carte_invalidite or child.handicap.complement_categorie is not None)
        for child in household.children)


def _patrimoine_inputs(patrimoine: Any, year: int) -> dict[str, Any]:
    """The 2042-IFI cases, written for the target year only.

    `_this_year` and not a multi-year block: wealth is assessed at 1 January of the
    year being priced, and writing a wealth stock across several periods would make
    the engine tax it in each of them.

    The field-to-case mapping lives in `impots.patrimoine.ifi.CASES` and is imported
    rather than restated, so the two cannot drift apart.
    """
    from impots.patrimoine.ifi import CASES

    return {
        code: _this_year(code, getattr(patrimoine, field), year)
        for field, code in CASES.items()
        if getattr(patrimoine, field, 0.0)
    }


def _niche_inputs(niches: Any, year: int) -> dict[str, Any]:
    """Foyer-fiscal-level réduction and crédit bases, on the target year only.

    Zero-valued fields are omitted rather than written as zero. Both produce the same
    answer, but an input dict that lists only what the household actually declared is
    what a reader can check against a paper 2042.
    """
    from impots.api import schemas

    inputs: dict[str, Any] = {}
    for field, case in schemas.NICHE_CASES.items():
        value = getattr(niches, field, 0)
        if value:
            inputs[case] = _this_year(case, value, year)
    for index, amount in enumerate(niches.frais_garde_par_enfant):
        if index < len(schemas.NICHE_GARDE_CASES) and amount:
            case = schemas.NICHE_GARDE_CASES[index]
            inputs[case] = _this_year(case, float(amount), year)
    return inputs


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
