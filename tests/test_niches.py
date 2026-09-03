"""B3 — the IR niches, verified through outcomes.

Same discipline as the prestations knobs (D-062): every assertion runs a household
through the engine and looks at the tax that came out. No rate here was read off a
table — each was measured, and the measured value is what the test pins.

The one that decided a design choice is `test_the_childcare_ceiling_is_per_child`:
6 000 € of childcare on one child yields 1 750 €, while 3 000 € on each of two yields
3 000 € — 71 % more for identical spending, because the ceiling is per child. That is
why `frais_garde_par_enfant` is a list and not a total. A total split equally would
have quietly overstated the credit for every household with one heavily-cared-for
child.
"""

from __future__ import annotations

import pytest

from impots.api.schemas import (
    NICHE_CASES,
    NICHE_GARDE_CASES,
    NICHE_SYNDICALES_CASE,
    HouseholdInput,
)
from impots.engine import compute
from impots.engine.situations import build_situation
from impots.engine.system import baseline

pytestmark = pytest.mark.slow

#: A couple with tax to reduce and a child young enough for the childcare credit.
#: Chosen so every niche can actually bite: a household with no tax cannot show a
#: réduction at all, and one with no young child cannot show the childcare credit.
FOYER = {
    "adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1985},
               {"salaire_brut_annuel": 30_000, "annee_naissance": 1987}],
    "couple_marie_ou_pacse": True,
    "children": [{"annee_naissance": 2021}, {"annee_naissance": 2010}],
}


def _ir(niches=None, tier="light", household=None):
    payload = dict(household or FOYER)
    if niches is not None:
        payload["niches"] = niches
    return compute(HouseholdInput.model_validate(payload), 2024, tier=tier).baseline


#: niche -> (input, expected reduction in net IR). Every figure MEASURED, not tabulated.
MEASURED = {
    "salarie_domicile": ({"salarie_domicile": 5_000}, 2_500.0),
    "dons_oeuvres": ({"dons_oeuvres": 1_000}, 660.0),
    "dons_aide_personnes_en_difficulte": (
        {"dons_aide_personnes_en_difficulte": 1_000}, 750.0),
    "frais_garde_par_enfant": ({"frais_garde_par_enfant": [2_000.0]}, 1_000.0),
    "cotisations_syndicales": ({"cotisations_syndicales": [200.0, 150.0]}, 231.0),
    "enfants_college": ({"enfants_college": 1}, 61.0),
    "enfants_lycee": ({"enfants_lycee": 1}, 153.0),
    "enfants_superieur": ({"enfants_superieur": 1}, 183.0),
}


# --- every niche moves net IR by the amount the law implies -------------------------


@pytest.mark.parametrize("niche", sorted(MEASURED))
def test_each_niche_reduces_net_ir_by_the_measured_amount(niche: str):
    before = _ir()["ir"]
    payload, expected = MEASURED[niche]
    after = _ir(payload)["ir"]
    assert before - after == pytest.approx(expected, abs=1.0), (
        f"{niche}: expected the tax to fall by {expected}, it fell by {before - after}"
    )


def test_the_rates_are_the_statutory_ones():
    """Read as rates rather than amounts, so a reader can check them against the law.

    50 % on home help and childcare, 66 % on ordinary donations and union dues, 75 %
    on donations to organisations helping people in difficulty.
    """
    for payload, base, rate in (
        ({"salarie_domicile": 5_000}, 5_000, 0.50),
        ({"dons_oeuvres": 1_000}, 1_000, 0.66),
        ({"dons_aide_personnes_en_difficulte": 1_000}, 1_000, 0.75),
        ({"frais_garde_par_enfant": [2_000.0]}, 2_000, 0.50),
        ({"cotisations_syndicales": [350.0]}, 350, 0.66),
    ):
        moved = _ir()["ir"] - _ir(payload)["ir"]
        assert moved / base == pytest.approx(rate, abs=0.005), payload


def test_the_decomposition_adds_up():
    """barème − réductions − crédits = net. The identity a reader will check first."""
    rows = _ir({"salarie_domicile": 5_000, "dons_oeuvres": 1_000, "enfants_lycee": 1})
    assert rows["ir"] == pytest.approx(
        rows["ir_avant_reductions"] - rows["reductions"] - rows["credits_impot"], abs=1.5)


def test_a_household_with_no_niches_reports_explicit_zeros():
    """The population's state, and why its IR is a barème figure.

    Reported as zero rather than absent: an omission a reader can see beats one they
    have to infer from a missing row.
    """
    rows = _ir()
    assert rows["reductions"] == 0.0 and rows["credits_impot"] == 0.0
    assert rows["ir"] > 0


# --- the ceiling that decided the wire format ---------------------------------------


def test_the_childcare_ceiling_is_per_child():
    """6 000 on one child gives 1 750; 3 000 on each of two gives 3 000.

    The same money, 71 % more credit, because the ceiling is 3 500 per child. This is
    why the field is a list: a single total split equally would have reported 3 000 for
    a household that spent it all on one child, overstating by 1 750.
    """
    jeunes = {"adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1985}],
              "children": [{"annee_naissance": 2020}, {"annee_naissance": 2022}]}
    one = _ir({"frais_garde_par_enfant": [6_000.0]}, household=jeunes)["credits_impot"]
    two = _ir({"frais_garde_par_enfant": [3_000.0, 3_000.0]},
              household=jeunes)["credits_impot"]
    assert one == pytest.approx(1_750.0, abs=1.0)
    assert two == pytest.approx(3_000.0, abs=1.0)
    assert two > one * 1.5


def test_the_ceiling_binds_rather_than_scaling():
    jeunes = {"adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1985}],
              "children": [{"annee_naissance": 2020}]}
    at_cap = _ir({"frais_garde_par_enfant": [3_500.0]}, household=jeunes)["credits_impot"]
    over_cap = _ir({"frais_garde_par_enfant": [9_000.0]}, household=jeunes)["credits_impot"]
    assert at_cap == pytest.approx(over_cap, abs=1.0)


def test_aid_received_reduces_the_home_help_base():
    """Omitting `salarie_domicile_aides_percues` overstates the credit.

    APA, PCH and pre-funded CESU are not the household's own spending, and the credit
    is 50 % of what remains after they are deducted.
    """
    gross = _ir({"salarie_domicile": 5_000})["credits_impot"]
    net = _ir({"salarie_domicile": 5_000,
               "salarie_domicile_aides_percues": 1_000})["credits_impot"]
    assert gross == pytest.approx(2_500.0, abs=1.0)
    assert net == pytest.approx(2_000.0, abs=1.0)


# --- refundability, which is not a detail -------------------------------------------


def test_the_credits_are_refundable_and_can_push_the_tax_negative():
    """`ci_saldom` and `ci_gardenf` are CRÉDITS: the state pays out the excess.

    A household claiming enough of them owes nothing and is owed money. That is why
    these two are the largest niches and why they cannot be imputed to taxpayers
    alone — a population that gave them only to households with tax to reduce would
    understate them and would misplace who benefits.
    """
    rows = _ir({"salarie_domicile": 5_000, "dons_oeuvres": 1_000,
                "frais_garde_par_enfant": [2_000.0], "enfants_lycee": 1,
                "cotisations_syndicales": [200.0]})
    assert rows["ir"] < 0, "the refundable credits should exceed the tax due here"


def test_a_reduction_cannot_go_below_zero_tax():
    """A RÉDUCTION, unlike a crédit, is capped by the tax owed.

    A household with no tax gets nothing from a donation, which is the distributional
    fact that makes the réduction/crédit distinction worth carrying in the wire format.
    """
    modeste = {"adults": [{"salaire_brut_annuel": 14_000, "annee_naissance": 1990}]}
    before = _ir(household=modeste)["ir"]
    after = _ir({"dons_oeuvres": 2_000}, household=modeste)["ir"]
    assert before == pytest.approx(0.0, abs=1.0)
    assert after == pytest.approx(0.0, abs=1.0)


# --- the wire format ---------------------------------------------------------------


def test_every_declared_case_exists_with_the_entity_and_period_assumed():
    """A case name is verified against the registry, never assumed.

    `f7d*` also contains five PME-subscription boxes and an invalidity flag; a
    plausible-looking name would have been the wrong box.
    """
    variables = baseline().variables
    for field, case in NICHE_CASES.items():
        variable = variables.get(case)
        assert variable is not None, f"{field} -> {case} is not an openfisca variable"
        assert variable.entity.key == "foyer_fiscal", case
        assert str(variable.definition_period) == "year", case
    for case in NICHE_GARDE_CASES:
        assert variables.get(case) is not None
    syndicales = variables.get(NICHE_SYNDICALES_CASE)
    assert syndicales is not None
    assert syndicales.entity.key == "individu", (
        "union dues follow the member, not the foyer, and the situation builder writes "
        "them onto the adults for that reason"
    )


def test_niches_are_written_to_the_target_year_only():
    """Not spread across the income history.

    The history exists so means-tested benefits get a realistic reference period.
    Copying a donation into 2023 and 2022 would assert three identical years of
    charitable giving that nobody claimed.
    """
    situation = build_situation(
        HouseholdInput.model_validate({**FOYER, "niches": {"dons_oeuvres": 1_000}}), 2024)
    foyer = next(iter(situation["foyers_fiscaux"].values()))
    assert set(foyer["f7uf"]) == {"2024"}
    # The salary, by contrast, does span the history — the two conventions coexist.
    individu = next(iter(situation["individus"].values()))
    assert len(individu["salaire_de_base"]) > 12


def test_a_zero_niche_is_omitted_rather_than_written():
    situation = build_situation(
        HouseholdInput.model_validate({**FOYER, "niches": {"dons_oeuvres": 0.0}}), 2024)
    foyer = next(iter(situation["foyers_fiscaux"].values()))
    assert "f7uf" not in foyer


def test_union_dues_land_on_the_adults_in_order():
    situation = build_situation(
        HouseholdInput.model_validate(
            {**FOYER, "niches": {"cotisations_syndicales": [200.0, 150.0]}}), 2024)
    amounts = [
        person[NICHE_SYNDICALES_CASE]["2024"]
        for person in situation["individus"].values()
        if NICHE_SYNDICALES_CASE in person
    ]
    assert amounts == [200.0, 150.0]


def test_more_childcare_amounts_than_cases_is_refused():
    """Three non-alternating cases exist, so a fourth child's costs have nowhere to go
    and must be an error rather than a silent drop."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        HouseholdInput.model_validate(
            {**FOYER, "niches": {"frais_garde_par_enfant": [1.0, 2.0, 3.0, 4.0]}})


def test_niches_absent_means_absent_not_zero_written():
    situation = build_situation(HouseholdInput.model_validate(FOYER), 2024)
    foyer = next(iter(situation["foyers_fiscaux"].values()))
    assert not any(key.startswith("f7") for key in foyer)


# --- the reform knobs ---------------------------------------------------------------

#: knob -> (value to set, the niches a household must declare for it to bite,
#:          household overrides, expected sign of the change in NET TAX)
#: A knob verified on a household that declares no matching base passes for the wrong
#: reason, so every case here declares one.
KNOB_CASES = {
    "saldom_taux": (0.30, {"salarie_domicile": 5_000}, {}, +1),
    "saldom_plafond": (6_000.0, {"salarie_domicile": 15_000}, {}, +1),
    "gardenf_taux": (0.30, {"frais_garde_par_enfant": [2_000.0]}, {}, +1),
    "gardenf_plafond": (1_000.0, {"frais_garde_par_enfant": [3_000.0]}, {}, +1),
    "dons_taux": (0.50, {"dons_oeuvres": 1_000}, {}, +1),
    "dons_plafond_part_rfr": (0.02, {"dons_oeuvres": 30_000}, {}, +1),
    "dons_coluche_taux": (0.50, {"dons_aide_personnes_en_difficulte": 800}, {}, +1),
    "dons_coluche_plafond": (200.0, {"dons_aide_personnes_en_difficulte": 800}, {}, +1),
    "cotisations_syndicales_taux": (0.40, {"cotisations_syndicales": [300.0]}, {}, +1),
    # Flat amounts, so RAISING them lowers the tax — the mirror sign, and checked.
    "frais_scolarite_college": (200.0, {"enfants_college": 1}, {}, -1),
    "frais_scolarite_lycee": (300.0, {"enfants_lycee": 1}, {}, -1),
    "frais_scolarite_superieur": (400.0, {"enfants_superieur": 1}, {}, -1),
    "plafond_global_niches": (
        4_000.0,
        {"salarie_domicile": 12_000,
         "frais_garde_par_enfant": [3_500.0, 3_500.0, 3_500.0]},
        {"children": [{"annee_naissance": 2019}, {"annee_naissance": 2021},
                      {"annee_naissance": 2022}]},
        +1),
}

#: Gross salary high enough that the household has tax for a réduction to reduce.
AISE = 90_000


def _foyer(niches, **overrides):
    payload = {
        "adults": [{"salaire_brut_annuel": AISE, "annee_naissance": 1985}],
        "children": [{"annee_naissance": 2021}, {"annee_naissance": 2010}],
        "niches": niches,
    }
    payload.update(overrides)
    return HouseholdInput.model_validate(payload)


@pytest.mark.parametrize("knob", sorted(KNOB_CASES))
def test_each_niche_knob_moves_the_tax(knob: str):
    from impots.api.schemas import ReformSpec

    value, niches, overrides, sign = KNOB_CASES[knob]
    household = _foyer(niches, **overrides)
    before = compute(household, 2024, tier="light").baseline["ir"]
    after = compute(household, 2024, reform=ReformSpec(**{knob: value}),
                    tier="light").reform["ir"]
    assert abs(after - before) > 0.5, f"{knob} moved nothing: {before} -> {after}"
    assert (after - before) * sign > 0, (
        f"{knob} moved the wrong way: {before} -> {after}. A rate or ceiling CUT must "
        f"raise the tax; a flat amount RAISED must lower it."
    )


def test_every_niche_knob_is_covered_here():
    from impots.engine.reforms import NICHE_KNOBS

    assert set(KNOB_CASES) == NICHE_KNOBS


def test_every_niche_knob_resolves_in_the_baseline_tree():
    from impots.engine.reforms import NICHE_KNOBS, SCALAR_KNOBS, resolve

    parameters = baseline().parameters
    for knob in sorted(NICHE_KNOBS):
        value = resolve(parameters, SCALAR_KNOBS[knob])("2024-01-01")
        assert value is not None, (
            f"{knob} resolves to a null parameter, which the formula cannot be reading"
        )


def test_the_global_cap_says_nothing_about_a_household_below_it():
    """`plafond_global_niches` is a lever on the top of the distribution, only.

    A household claiming 2 500 EUR of credits is untouched by moving the cap from
    10 000 to 9 000 and hit by moving it to 2 000. Worth a test because a chiffrage of
    this knob is easy to read as a statement about niches in general, and it is not.
    """
    from impots.api.schemas import ReformSpec

    household = _foyer({"salarie_domicile": 5_000})
    before = compute(household, 2024, tier="light").baseline["ir"]
    untouched = compute(household, 2024, reform=ReformSpec(plafond_global_niches=9_000.0),
                        tier="light").reform["ir"]
    binding = compute(household, 2024, reform=ReformSpec(plafond_global_niches=2_000.0),
                      tier="light").reform["ir"]
    assert untouched == pytest.approx(before, abs=1.0)
    assert binding > before + 400


def test_the_donation_ceiling_is_a_share_of_income_not_a_euro_amount():
    """`dons_plafond_part_rfr` is 0.2 — twenty percent of the revenu fiscal de
    référence. Its bound is [0, 1] for that reason, and a euro figure typed into it
    would be refused rather than silently read as 20 000 %."""
    import pydantic

    from impots.api.schemas import ReformSpec

    with pytest.raises(pydantic.ValidationError):
        ReformSpec(dons_plafond_part_rfr=20_000.0)
    assert ReformSpec(dons_plafond_part_rfr=0.10) is not None


def test_the_childcare_ceiling_knob_stays_per_child():
    """Halving it halves the per-child cap, not the household's total."""
    from impots.api.schemas import ReformSpec

    jeunes = {"children": [{"annee_naissance": 2020}, {"annee_naissance": 2022}]}
    household = _foyer({"frais_garde_par_enfant": [3_500.0, 3_500.0]}, **jeunes)
    before = compute(household, 2024, tier="light").baseline["credits_impot"]
    after = compute(household, 2024, reform=ReformSpec(gardenf_plafond=1_750.0),
                    tier="light").reform["credits_impot"]
    assert before == pytest.approx(3_500.0, abs=1.0)
    assert after == pytest.approx(1_750.0, abs=1.0)


def test_a_niche_reform_does_not_mutate_the_baseline():
    from impots.api.schemas import ReformSpec

    household = _foyer({"salarie_domicile": 5_000})
    before = compute(household, 2024, tier="light").baseline["ir"]
    compute(household, 2024, reform=ReformSpec(saldom_taux=0.10), tier="light")
    assert compute(household, 2024, tier="light").baseline["ir"] == pytest.approx(before)


# --- eligibility, which the engine does not check ----------------------------------


def test_the_engine_itself_applies_no_eligibility_test():
    """The premise of the guard, proven rather than asserted.

    These cases are boxes on the 2042 and openfisca trusts the declarant the way the
    paper form does. Fill the childcare box for a household with no children and it
    computes the credit without complaint. That is correct behaviour for a tax engine
    and unacceptable in a calculator someone uses to decide something.
    """
    from openfisca_core.simulations import SimulationBuilder

    from impots.api.schemas import Niches
    from impots.engine.situations import _niche_inputs, build_situation

    sans_enfant = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1985}]})
    situation = build_situation(sans_enfant, 2024)
    # Inject the case directly, bypassing the wire format's own check.
    foyer = next(iter(situation["foyers_fiscaux"].values()))
    foyer.update(_niche_inputs(Niches(frais_garde_par_enfant=[2_000.0]), 2024))
    simulation = SimulationBuilder().build_from_entities(baseline(), situation)
    assert float(simulation.calculate("credits_impot", "2024").sum()) == pytest.approx(
        1_000.0, abs=1.0), "openfisca declined to compute it, so the guard is unnecessary"


@pytest.mark.parametrize("children,niches,fragment", [
    ([], {"frais_garde_par_enfant": [2_000.0]}, "moins de 6 ans"),
    ([{"annee_naissance": 2009}], {"frais_garde_par_enfant": [2_000.0]}, "moins de 6 ans"),
    ([{"annee_naissance": 2021}, {"annee_naissance": 2010}],
     {"frais_garde_par_enfant": [2_000.0, 1_000.0]}, "moins de 6 ans"),
    ([{"annee_naissance": 2012}], {"enfants_college": 2}, "scolarisé"),
    ([], {"cotisations_syndicales": [200.0, 150.0]}, "adhérent"),
])
def test_an_ineligible_declaration_is_refused(children, niches, fragment):
    from impots.engine.situations import build_situation

    household = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1985}],
         "children": children, "niches": niches})
    with pytest.raises(ValueError, match=fragment):
        build_situation(household, 2024)


def test_an_eligible_declaration_is_accepted():
    """The other half: the guard must not refuse a household that qualifies."""
    from impots.engine.situations import build_situation

    household = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1985}],
         "children": [{"annee_naissance": 2021}, {"annee_naissance": 2022}],
         "niches": {"frais_garde_par_enfant": [2_000.0, 1_000.0],
                    "enfants_college": 0, "cotisations_syndicales": [200.0]}})
    assert build_situation(household, 2024) is not None


def test_the_age_boundary_is_stated_and_holds():
    """Under six at 1 January: born in `year - 6` or later.

    Only the birth year is carried, so a child born on 1 January of `year - 6` is
    treated as eligible when they are in fact exactly six — one day a year, stated in
    `CHILDCARE_MAX_AGE`'s comment rather than silently rounded.
    """
    from impots.engine.situations import CHILDCARE_MAX_AGE, build_situation

    assert CHILDCARE_MAX_AGE == 6
    for birth_year, accepted in ((2018, True), (2017, False)):
        household = HouseholdInput.model_validate(
            {"adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1985}],
             "children": [{"annee_naissance": birth_year}],
             "niches": {"frais_garde_par_enfant": [2_000.0]}})
        if accepted:
            assert build_situation(household, 2024) is not None
        else:
            with pytest.raises(ValueError):
                build_situation(household, 2024)


# --- the confident zero the population refuses to print -----------------------------


def test_a_niche_reform_on_a_population_with_no_bases_is_flagged():
    """The most dangerous output this project could produce.

    Cut the home-help credit from 50 % to 30 % on this population and the cost is
    exactly 0.0000 bn, because no household declares home-help spending. A reader told
    "0 €" concludes the credit is worthless. The flag says the zero is an absence of
    data, not an absence of effect.
    """
    from impots.engine.reforms import NICHE_KNOBS
    from impots.guards import niche_blind_spot

    empty = {"reductions": 0.0, "credits_impot": 0.0}
    assert niche_blind_spot(["saldom_taux"], empty, NICHE_KNOBS) == ("saldom_taux",)
    # Silent on a reform that touches no niche...
    assert niche_blind_spot(["ir_bareme"], empty, NICHE_KNOBS) == ()
    # ...and silent once the population actually has bases, which is the half that
    # keeps the flag from becoming permanent furniture.
    assert niche_blind_spot(["saldom_taux"], {"credits_impot": 2.5e9}, NICHE_KNOBS) == ()


def test_the_flag_names_every_niche_knob_the_reform_moved():
    from impots.engine.reforms import NICHE_KNOBS
    from impots.guards import niche_blind_spot

    flagged = niche_blind_spot(
        ["saldom_taux", "dons_taux", "ir_bareme", "plafond_global_niches"],
        {"reductions": 0.0, "credits_impot": 0.0}, NICHE_KNOBS)
    assert flagged == ("dons_taux", "plafond_global_niches", "saldom_taux")
