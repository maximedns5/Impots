"""B1 — the prestations knobs, verified through outcomes rather than read-back.

Every test here runs a household through the engine and looks at the benefit that came
out. That is deliberate and it is the point of the file: reading back the parameter you
just wrote confirms your own write path (D-042), and this increment contains a defect
that only an outcome check could find.

`af_cond_ress.plafond_tranche_1` and `plafond_tranche_2` exist in the tree and accept a
write. The AF formula never reads them — it builds its own ceiling from the `_base`
value plus one majoration per child, and the non-base parameters are published
already-derived figures (62 474 + 2 x 6 246 = 74 966). A knob aimed at them writes
successfully, raises no warning, and moves nothing. `test_the_derived_plafonds_move_nothing`
is that defect, kept as a regression.
"""

from __future__ import annotations

import pydantic
import pytest

from impots.api.schemas import (
    AF_PLAFOND_TRANCHE_1_BASE_2024,
    AF_PLAFOND_TRANCHE_2_BASE_2024,
    HouseholdInput,
    ReformSpec,
)
from impots.engine import compute
from impots.engine.reforms import PRESTATION_KNOBS, SCALAR_KNOBS, resolve
from impots.engine.system import baseline, clear_cache

pytestmark = pytest.mark.slow

#: Households chosen because each actually receives the benefit under test. A knob
#: verified on a household that gets nothing passes for the wrong reason — the mistake
#: the CVAE franchise sizing made in Phase 2.
SANS_EMPLOI = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1990}]}
)
TEMPS_PARTIEL = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 11000, "annee_naissance": 1990}],
     "children": [{"annee_naissance": 2015}]}
)
LOCATAIRE = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 11000, "annee_naissance": 1990}],
     "children": [{"annee_naissance": 2015}],
     "logement": {"statut": "locataire_vide", "loyer_mensuel": 700, "zone_apl": 1}}
)
FAMILLE_MODESTE = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 40000, "annee_naissance": 1985}],
     "children": [{"annee_naissance": 2012}, {"annee_naissance": 2015}]}
)
FAMILLE_AISEE = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 100000, "annee_naissance": 1980},
                {"salaire_brut_annuel": 50000, "annee_naissance": 1982}],
     "children": [{"annee_naissance": 2012}, {"annee_naissance": 2015}],
     "couple_marie_ou_pacse": True}
)

#: knob -> (household, output, value to set, expected direction)
CASES = {
    "rsa_montant_de_base": (SANS_EMPLOI, "rsa", 700.0, +1),
    "ppa_montant_de_base": (TEMPS_PARTIEL, "ppa", 700.0, +1),
    "ppa_pente": (TEMPS_PARTIEL, "ppa", 0.70, +1),
    "ppa_bonification_taux_max": (TEMPS_PARTIEL, "ppa", 0.40, +1),
    "bmaf": (FAMILLE_MODESTE, "af", 500.0, +1),
    "af_taux_2_enfants": (FAMILLE_MODESTE, "af", 0.40, +1),
    "af_taux_3_enfants": (FAMILLE_MODESTE, "af", 0.50, 0),
    "af_modulation_taux_tranche_2": (FAMILLE_AISEE, "af", 1.0, 0),
    "af_modulation_taux_tranche_3": (FAMILLE_AISEE, "af", 1.0, +1),
    # Lowered, not raised: raising tranche 1 alone would push it above tranche 2 and
    # the validator refuses that — the guard doing its job inside a fixture.
    #
    # 12 000, not 20 000, and the difference is a finding. The modulation compares
    # against BASE RESSOURCES — net income, two years back — not against gross salary.
    # A 40 000 gross household modulates on about 28 800, so a ceiling of 20 000 + two
    # majorations (32 492) still leaves it in tranche 1 and moves nothing. A test
    # written against gross income would have passed for the wrong reason, or here,
    # failed for the right one.
    "af_plafond_tranche_1_base": (FAMILLE_MODESTE, "af", 12_000.0, -1),
    "af_plafond_tranche_2_base": (FAMILLE_AISEE, "af", 500_000.0, +1),
    "af_majoration_plafond_par_enfant": (FAMILLE_AISEE, "af", 50_000.0, +1),
    "al_minoration_forfaitaire": (LOCATAIRE, "aide_logement", 20.0, -1),
}


def _run(household, knob=None, value=None, **extra):
    if knob is None:
        return compute(household, 2024, tier="full").baseline
    spec = ReformSpec(**{knob: value}, **extra)
    return compute(household, 2024, reform=spec, tier="full").reform


# --- every knob moves the benefit it claims to move ---------------------------------


@pytest.mark.parametrize("knob", sorted(k for k in CASES if CASES[k][3] != 0))
def test_each_knob_moves_its_benefit(knob: str):
    """The verification that matters: an outcome, on a household that receives it."""
    household, output, value, direction = CASES[knob]
    before = _run(household)[output]
    after = _run(household, knob, value)[output]
    assert before > 0, f"{knob}: the fixture receives no {output}, so nothing is proven"
    assert abs(after - before) > 0.5, f"{knob} moved nothing: {before} -> {after}"
    assert (after - before) * direction > 0, (
        f"{knob} moved the wrong way: {before} -> {after}"
    )


def test_every_prestation_knob_is_covered_here():
    """A knob added without a case would otherwise ship unverified."""
    assert set(CASES) == PRESTATION_KNOBS


def test_the_third_child_rate_does_nothing_to_a_two_child_family():
    """A direction of zero is a claim too, and it is checked."""
    household, output, value, _ = CASES["af_taux_3_enfants"]
    assert _run(household, "af_taux_3_enfants", value)[output] == pytest.approx(
        _run(household)[output])


# --- the defect an outcome check found and a read-back would not ---------------------


def test_the_derived_plafonds_move_nothing(monkeypatch):
    """`plafond_tranche_1` / `_2` are published derived values no formula reads.

    They accept a write and change nothing. This is the D-044 failure in a new shape,
    and it is why the knobs point at `_base`. Kept as a regression so a future edit
    cannot quietly re-aim them at the convenient-looking name.
    """
    from impots.engine import reforms

    monkeypatch.setitem(reforms.SCALAR_KNOBS, "af_plafond_tranche_2_base",
                        (*reforms.PATH_AF_RESSOURCES, "plafond_tranche_2"))
    # The reform cache keys on the SPEC, not on the paths the spec resolves to, so
    # without this the previous test's correctly-aimed build is served straight back
    # and the assertion measures nothing.
    clear_cache()
    before = _run(FAMILLE_AISEE)["af"]
    after = _run(FAMILLE_AISEE, "af_plafond_tranche_2_base", 500_000.0)["af"]
    clear_cache()
    assert after == pytest.approx(before), (
        "the derived plafond now moves the benefit — either openfisca changed the "
        "formula, in which case re-aim the knob, or this test is no longer testing "
        "what it says"
    )


def test_the_real_plafonds_are_the_ones_the_formula_reads():
    """The other half: aimed at `_base`, the same reform does move."""
    before = _run(FAMILLE_AISEE)["af"]
    after = _run(FAMILLE_AISEE, "af_plafond_tranche_2_base", 500_000.0)["af"]
    assert after > before


# --- the ordering guard, and its kill test ------------------------------------------


def test_inverted_af_plafonds_are_refused():
    with pytest.raises(pydantic.ValidationError, match="aucune des deux tranches"):
        ReformSpec(af_plafond_tranche_1_base=90_000.0, af_plafond_tranche_2_base=80_000.0)


def test_one_sided_plafond_moves_are_checked_against_the_other_baseline():
    """Raising only the first ceiling above the untouched second is the real mistake.

    It is how the defect was found: lifting tranche 1 alone gave a 150 k household
    2 214 EUR where the full rate is 1 771 — an amount belonging to neither tranche.
    """
    with pytest.raises(pydantic.ValidationError):
        ReformSpec(af_plafond_tranche_1_base=500_000.0)
    with pytest.raises(pydantic.ValidationError):
        ReformSpec(af_plafond_tranche_2_base=50_000.0)


def test_an_ordered_pair_is_accepted():
    """The guard must not refuse everything."""
    spec = ReformSpec(af_plafond_tranche_1_base=70_000.0,
                      af_plafond_tranche_2_base=120_000.0)
    assert spec.af_plafond_tranche_1_base == 70_000.0


def test_the_validator_baselines_match_the_tree():
    """The two constants the validator compares against are the legal 2024 values.

    Pinned in the schema so a validator needs no tax-benefit system; checked here so
    they cannot drift away from the tree they claim to mirror.
    """
    parameters = baseline().parameters
    for constant, knob in (
        (AF_PLAFOND_TRANCHE_1_BASE_2024, "af_plafond_tranche_1_base"),
        (AF_PLAFOND_TRANCHE_2_BASE_2024, "af_plafond_tranche_2_base"),
    ):
        assert float(resolve(parameters, SCALAR_KNOBS[knob])("2024-01-01")) == constant


# --- reforms a reader would actually propose ----------------------------------------


def test_universal_family_allowances_restore_the_full_rate():
    """Setting both modulation tranches to 1 undoes the 2015 modulation.

    A live proposal, and now one reform. The wealthy family should end up on exactly
    the rate the modest one already gets.
    """
    modest = _run(FAMILLE_MODESTE)["af"]
    before = _run(FAMILLE_AISEE)["af"]
    after = _run(FAMILLE_AISEE, "af_modulation_taux_tranche_2", 1.0,
                 af_modulation_taux_tranche_3=1.0)["af"]
    assert before < modest
    assert after == pytest.approx(modest, rel=1e-6)


def test_abolishing_the_housing_cut_returns_five_euros_a_month():
    """The 2017 minoration, removed: twelve months of five euros, to the cent."""
    before = _run(LOCATAIRE)["aide_logement"]
    after = _run(LOCATAIRE, "al_minoration_forfaitaire", 0.0)["aide_logement"]
    assert after - before == pytest.approx(60.0, abs=0.5)


def test_a_steeper_ppa_taper_raises_the_benefit_of_a_working_household():
    """`ppa_pente` is the marginal-rate lever: more activity income added back before
    the taper means more benefit, and a lower effective marginal rate."""
    before = _run(TEMPS_PARTIEL)["ppa"]
    after = _run(TEMPS_PARTIEL, "ppa_pente", 0.70)["ppa"]
    assert after > before


# --- the standing rules ------------------------------------------------------------


def test_a_prestation_reform_does_not_mutate_the_baseline():
    before = _run(SANS_EMPLOI)["rsa"]
    _run(SANS_EMPLOI, "rsa_montant_de_base", 900.0)
    assert _run(SANS_EMPLOI)["rsa"] == pytest.approx(before)


def test_every_prestation_knob_resolves_in_the_baseline_tree():
    """No knob may point at a path that does not exist at the instant it writes for."""
    parameters = baseline().parameters
    for knob in sorted(PRESTATION_KNOBS):
        value = resolve(parameters, SCALAR_KNOBS[knob])("2024-01-01")
        assert value is not None, f"{knob} resolves to a null parameter"


def test_the_rsa_taper_is_not_a_knob_because_it_is_null():
    """`rsa.rsa_m.pente` exists as a child and has no value at this instant.

    Recorded rather than worked around: a knob writing to it would be writing to a
    parameter the formula cannot be reading, which is the same defect as the derived
    plafonds one level down.
    """
    parameters = baseline().parameters
    pente = resolve(parameters, ("prestations_sociales", "solidarite_insertion",
                                 "minima_sociaux", "rsa", "rsa_m", "pente"))
    assert pente("2024-01-01") is None
    assert not any("pente" in SCALAR_KNOBS[k] for k in PRESTATION_KNOBS if "rsa" in k)


# --- what the double-entry guard found, kept as regressions -------------------------


def test_the_prime_de_noel_rides_on_rsa_eligibility():
    """`aefa` is not reformed here — it is switched ON by becoming RSA-eligible.

    A household just outside the RSA gains 152.45 EUR it was not receiving, and that
    money is inside `revenu_disponible` but was in none of the itemised transfers. At
    national scale it was 36 M EUR, 0.99 % of an RSA reform: ten times the guard's
    tolerance, and the guard is how it was found.
    """
    juste_au_dessus = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 12_000, "annee_naissance": 1990}]}
    )
    before = _run(juste_au_dessus)
    after = _run(juste_au_dessus, "rsa_montant_de_base", 900.0)
    assert before["rsa"] == 0.0 and before["aefa"] == 0.0
    assert after["rsa"] > 0.0
    assert after["aefa"] == pytest.approx(152.45, abs=0.01)
    # And the bottom line is the sum of both, which is the identity that failed.
    assert after["revenu_disponible"] - before["revenu_disponible"] == pytest.approx(
        (after["rsa"] - before["rsa"]) + (after["aefa"] - before["aefa"]), abs=0.5)


def test_benefit_crds_is_itemised_and_negative():
    """Benefits are reported GROSS; disposable income carries them NET.

    The 0.5 % between the two made a national AF reform miss by exactly 0.50 %. The
    CRDS columns are negative as the engine stores them, which is why they belong on
    the transfer side rather than among the receipts.
    """
    before = _run(FAMILLE_AISEE)
    after = _run(FAMILLE_AISEE, "af_modulation_taux_tranche_3", 1.0,
                 af_modulation_taux_tranche_2=1.0)
    assert before["crds_pfam"] <= 0.0, "CRDS is stored as a negative addend"
    gross = after["af"] - before["af"]
    crds = after["crds_pfam"] - before["crds_pfam"]
    assert gross > 0 and crds < 0
    assert abs(crds) == pytest.approx(gross * 0.005, rel=0.02), "CRDS on benefits is 0.5 %"


def test_the_guard_would_still_fail_without_the_new_lines():
    """The kill test: remove either itemisation and the reconstitution breaks.

    Numbers are the measured national ones. Without `aefa` the RSA reform misses by
    0.99 %; without the benefit CRDS the AF reform misses by 0.50 %. Both are well
    outside the 0.1 % tolerance, so neither could be waved through as noise.
    """
    from impots import guards

    # Built to balance exactly rather than transcribed, so the test cannot rot as the
    # population is revised. The proportions are the measured national ones: the prime
    # de Noël is about 1 % of an RSA reform, the benefit CRDS exactly 0.5 % of an AF one.
    rsa_reform = {"rsa": 3.5949e9, "ppa": 0.0037e9, "aide_logement": 0.0299e9,
                  "aefa": 0.0359e9}
    cost = sum(rsa_reform.values())
    guards.sector_balance(rsa_reform, reform_cost=cost)
    with pytest.raises(guards.SectorBalanceError, match="ne correspond pas"):
        guards.sector_balance({k: v for k, v in rsa_reform.items() if k != "aefa"},
                              reform_cost=cost)

    af_reform = {"af": 1002.187e6, "crds_pfam": -1002.187e6 * 0.005}
    cost = sum(af_reform.values())
    guards.sector_balance(af_reform, reform_cost=cost)
    with pytest.raises(guards.SectorBalanceError, match="ne correspond pas"):
        guards.sector_balance({k: v for k, v in af_reform.items() if k != "crds_pfam"},
                              reform_cost=cost)
