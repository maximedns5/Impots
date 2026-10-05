"""Engine wiring, tiers, EMTR and timing budget (spec §3.2, §3.3, §3.5, §6).

These are the tests that would catch a change of shape rather than a change of
number: a variable that moved entity, a light request that quietly started
computing the whole benefits cascade, a salary written annually onto a monthly
variable.
"""

from __future__ import annotations

import functools
import time
from typing import Any

import pytest
from openfisca_core.simulation_builder import SimulationBuilder

from impots.api.schemas import HouseholdInput, ReformSpec
from impots.engine import baseline, compute
from impots.engine.compute import EMTR_STEP
from impots.engine.outputs import FULL_ROWS, LIGHT_ROWS, check_registry, extract
from impots.engine.situations import build_situation, perturb_first_adult

SINGLE = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 30000, "annee_naissance": 1990}]}
)
COUPLE = HouseholdInput.model_validate(
    {
        "adults": [
            {"salaire_brut_annuel": 45000, "annee_naissance": 1985},
            {"salaire_brut_annuel": 25000, "annee_naissance": 1987},
        ],
        "children": [{"annee_naissance": 2015}, {"annee_naissance": 2018}],
        "couple_marie_ou_pacse": True,
    }
)

# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #
def test_registry_matches_the_engine() -> None:
    """Every registry row still names a real variable, on the entity and period we
    think it has. openfisca-france ships weekly; this turns a rename into a named
    failure instead of a silent zero."""
    assert check_registry(baseline()) == []


def test_dead_names_stay_dead() -> None:
    """`irpp` and `prime_activite` are the two names most likely to be typed from
    memory, and neither exists any more."""
    variables = baseline().variables
    assert variables.get("irpp") is None
    assert variables.get("prime_activite") is None
    assert variables.get("taux_marginal_imposition") is None
    assert variables.get("impot_revenu_restant_a_payer") is not None
    assert variables.get("ppa") is not None


# --------------------------------------------------------------------------- #
# situation building
# --------------------------------------------------------------------------- #
def test_single_situation_shape() -> None:
    situation = build_situation(SINGLE, 2024)
    assert list(situation) == ["individus", "foyers_fiscaux", "familles", "menages"]
    assert situation["foyers_fiscaux"]["ff_0"] == {"declarants": ["adulte_0"]}
    assert situation["familles"]["fam_0"] == {"parents": ["adulte_0"]}
    assert situation["menages"]["men_0"] == {"personne_de_reference": ["adulte_0"]}


def test_couple_situation_wiring() -> None:
    """Every adult in declarants + parents + (personne_de_reference | conjoint);
    every child in personnes_a_charge + both `enfants` roles."""
    situation = build_situation(COUPLE, 2024)
    adults, children = ["adulte_0", "adulte_1"], ["enfant_0", "enfant_1"]

    assert situation["foyers_fiscaux"]["ff_0"]["declarants"] == adults
    assert situation["foyers_fiscaux"]["ff_0"]["personnes_a_charge"] == children
    assert situation["familles"]["fam_0"]["parents"] == adults
    assert situation["familles"]["fam_0"]["enfants"] == children

    menage = situation["menages"]["men_0"]
    assert menage["personne_de_reference"] == ["adulte_0"]
    assert menage["conjoint"] == ["adulte_1"]
    assert menage["enfants"] == children

    assert set(situation["individus"]) == set(adults + children)
    for child in children:
        assert "salaire_de_base" not in situation["individus"][child]


def test_salary_is_written_monthly() -> None:
    """`salaire_de_base` is a monthly variable: an annual figure written to a year
    period would be silently divided by the engine's own conventions, or ignored."""
    situation = build_situation(SINGLE, 2024, historique_revenus=False)
    salary = situation["individus"]["adulte_0"]["salaire_de_base"]
    assert list(salary) == [f"2024-{m:02d}" for m in range(1, 13)]
    assert all(value == pytest.approx(2500.0) for value in salary.values())
    assert sum(salary.values()) == pytest.approx(30000.0)
    assert situation["individus"]["adulte_0"]["date_naissance"] == {"ETERNITY": "1990-01-01"}


def test_perturbation_touches_only_the_first_adult() -> None:
    situation = build_situation(COUPLE, 2024, historique_revenus=False)
    perturbed = perturb_first_adult(situation, 2024, EMTR_STEP)
    first = perturbed["individus"]["adulte_0"]["salaire_de_base"]
    second = perturbed["individus"]["adulte_1"]["salaire_de_base"]
    assert sum(first.values()) == pytest.approx(45000.0 + EMTR_STEP)
    assert sum(second.values()) == pytest.approx(25000.0)
    # the original must not have moved
    assert sum(situation["individus"]["adulte_0"]["salaire_de_base"].values()) == pytest.approx(
        45000.0
    )


# --------------------------------------------------------------------------- #
# tiers
# --------------------------------------------------------------------------- #
def test_light_tier_leaves_benefit_rows_unset() -> None:
    """`None`, not `0`: the light tier did not compute these, which is a different
    statement from "this household receives nothing"."""
    rows = compute(SINGLE, 2024, tier="light").baseline
    for key in ("af", "ppa", "rsa", "aide_logement", "revenu_disponible"):
        assert rows.get(key) is None


def test_light_tier_does_not_trigger_the_benefits_cascade() -> None:
    """Structural proof, not a stopwatch: after a light extraction the engine must
    never have computed `revenu_disponible` or any famille variable.

    This is what keeps a light request at ~0.5 s instead of ~3 s.
    """
    situation = build_situation(SINGLE, 2024)
    simulation = SimulationBuilder().build_from_entities(baseline(), situation)
    extract(simulation, 2024, "light")

    for name in ("revenu_disponible", "af", "ppa", "rsa", "aide_logement"):
        known = list(simulation.get_holder(name).get_known_periods())
        assert known == [], f"the light tier computed {name} — the cascade was triggered"

    # and the tax block *was* computed
    assert list(simulation.get_holder("impot_revenu_restant_a_payer").get_known_periods())


def test_full_tier_computes_everything() -> None:
    rows = compute(COUPLE, 2024, tier="full").baseline
    assert {row.key for row in FULL_ROWS} <= set(rows)
    assert rows["revenu_disponible"] is not None
    assert rows["af"] > 0  # two children


def test_tiers_agree_on_the_rows_they_share() -> None:
    light = compute(COUPLE, 2024, tier="light").baseline
    full = compute(COUPLE, 2024, tier="full").baseline
    for row in LIGHT_ROWS:
        assert light[row.key] == full[row.key], row.key


# --------------------------------------------------------------------------- #
# sign convention
# --------------------------------------------------------------------------- #
def test_amounts_are_positive_magnitudes() -> None:
    """Tax and contributions leave the household; the wire format states the
    magnitude and lets the field name carry the direction."""
    result = compute(SINGLE, 2024, tier="full", debug=True)
    rows = result.baseline
    for key in ("ir", "cotisations_salariales", "cotisations_employeur",
                "csg_deductible", "csg_imposable", "crds"):
        assert rows[key] > 0, f"{key} should be a positive magnitude, got {rows[key]}"
        assert rows["raw"][key] < 0, f"{key} should come out of the engine negative"
    assert rows["salaire_net"] == rows["raw"]["salaire_net"]


def test_zero_tax_is_not_negative_zero() -> None:
    """A household that owes nothing must serialise as 0.0, not -0.0."""
    smic = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 21621.60, "annee_naissance": 1995}]}
    )
    ir = compute(smic, 2024, tier="light").baseline["ir"]
    assert ir == 0.0
    assert str(ir) == "0.0"


def test_individu_rows_sum_across_members() -> None:
    rows = compute(COUPLE, 2024, tier="light").baseline
    assert rows["salaire_brut"] == pytest.approx(70000.0)


def test_raw_passthrough_is_debug_only() -> None:
    assert "raw" not in compute(SINGLE, 2024, tier="light").baseline
    assert "raw" in compute(SINGLE, 2024, tier="light", debug=True).baseline


# --------------------------------------------------------------------------- #
# EMTR
# --------------------------------------------------------------------------- #
def test_emtr_requires_the_full_tier() -> None:
    with pytest.raises(ValueError, match="tier='full'"):
        compute(SINGLE, 2024, tier="light", emtr=True)


def test_emtr_is_a_finite_difference_on_disposable_income() -> None:
    """There is no marginal-rate variable in openfisca — recompute it by hand and
    check the wrapper's arithmetic, including the direction of the subtraction."""
    result = compute(SINGLE, 2024, tier="full", emtr=True)
    base = result.baseline["revenu_disponible"]

    bumped_household = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 30000 + EMTR_STEP, "annee_naissance": 1990}]}
    )
    bumped = compute(bumped_household, 2024, tier="full").baseline["revenu_disponible"]

    by_hand = 1.0 - (bumped - base) / EMTR_STEP
    assert result.emtr == pytest.approx(by_hand, abs=1e-3)
    assert 0.0 < result.emtr < 1.0


def test_emtr_is_computed_for_the_reform_column_too() -> None:
    """With a reform loaded, the Δ column needs both marginal rates or it has a hole."""
    flat = ReformSpec.model_validate(
        {"ir_bareme": [{"threshold": 0, "rate": 0.0}, {"threshold": 5000, "rate": 0.50}]}
    )
    result = compute(SINGLE, 2024, reform=flat, tier="full", emtr=True)
    assert result.emtr is not None
    assert result.emtr_reform is not None
    assert result.emtr_reform > result.emtr  # a 50 % bracket from 5 000 € bites harder


def test_emtr_is_absent_unless_asked_for() -> None:
    result = compute(SINGLE, 2024, tier="full")
    assert result.emtr is None
    assert result.timings["emtr_ms"] is None


# --------------------------------------------------------------------------- #
# timing budget
# --------------------------------------------------------------------------- #
def _time_once(**kwargs: object) -> float:
    started = time.perf_counter()
    compute(SINGLE, 2024, **kwargs)  # type: ignore[arg-type]
    return time.perf_counter() - started


def _fastest_seconds(runs: int, **kwargs: object) -> float:
    """The floor, not the middle.

    Noise on a shared machine only ever *adds* time, so the minimum of several
    runs is the robust estimate of how fast the code can go. A median is pulled
    around by whatever else the machine was doing during that particular window.
    """
    return min(_time_once(**kwargs) for _ in range(runs))


def test_light_compute_is_within_budget(quiet_machine: None) -> None:
    """< 1.5 s warm. Generous on purpose: this catches a light request that started
    computing the benefits cascade, not a machine that is 20 % slower than mine."""
    assert _fastest_seconds(3, tier="light") < 1.5


def test_full_compute_is_within_budget(quiet_machine: None) -> None:
    """< 6 s warm."""
    assert _fastest_seconds(3, tier="full") < 6.0


def test_light_is_materially_faster_than_full(quiet_machine: None) -> None:
    """If these two converge, the light tier is over-computing.

    The two tiers are timed *interleaved*, so a load spike lands on both rather
    than on whichever happened to be measured first — timing them in separate
    blocks made this test flaky enough to invert (light 3.5 s vs full 1.7 s for
    identical code) on a busy machine.
    """
    light = min(_time_once(tier="light") for _ in range(3))
    full = min(_time_once(tier="full") for _ in range(3))
    interleaved = [(_time_once(tier="light"), _time_once(tier="full")) for _ in range(2)]
    light = min([light, *(pair[0] for pair in interleaved)])
    full = min([full, *(pair[1] for pair in interleaved)])
    assert light < full, f"light {light:.2f}s is not faster than full {full:.2f}s"


def test_timings_are_reported() -> None:
    """The UI's loading copy and the perf regression test both read these."""
    timings = compute(SINGLE, 2024, tier="light").timings
    assert timings["build_ms"] >= 0
    assert timings["compute_ms"] > 0
    assert timings["total_ms"] >= timings["compute_ms"]


# --------------------------------------------------------------------------- #
# parent isolé (case T) — not in the Phase 0 spec; see docs/DECISIONS.md D-006
# --------------------------------------------------------------------------- #
LONE_PARENT = {
    "adults": [{"salaire_brut_annuel": 40000, "annee_naissance": 1985}],
    "children": [{"annee_naissance": 2015}],
}


@pytest.mark.parametrize(
    ("children", "with_case_t", "without_case_t"),
    [(1, 2.0, 1.5), (2, 2.5, 2.0), (3, 3.5, 3.0)],
)
def test_single_parent_gets_the_extra_half_part(
    children: int, with_case_t: float, without_case_t: float
) -> None:
    """French law grants a parent isolé an extra half part. `caseT` is the only
    lever — `nbptr` multiplies the `isol` parameter by it, and nothing is inferred
    from the shape of the household. Getting this wrong over-taxes single parents.
    """
    payload = {
        "adults": [{"salaire_brut_annuel": 40000, "annee_naissance": 1985}],
        "children": [{"annee_naissance": 2010 + i} for i in range(children)],
    }
    claimed = HouseholdInput.model_validate({**payload, "parent_isole": True})
    waived = HouseholdInput.model_validate({**payload, "parent_isole": False})
    assert compute(claimed, 2024, tier="light").baseline["parts_fiscales"] == with_case_t
    assert compute(waived, 2024, tier="light").baseline["parts_fiscales"] == without_case_t


def test_parent_isole_is_inferred_from_the_household() -> None:
    """Unset means "work it out": a lone adult with children is a parent isolé."""
    assert HouseholdInput.model_validate(LONE_PARENT).resolved_parent_isole() is True
    assert HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 40000, "annee_naissance": 1985}]}
    ).resolved_parent_isole() is False
    assert HouseholdInput.model_validate(
        {
            "adults": [
                {"salaire_brut_annuel": 40000, "annee_naissance": 1985},
                {"salaire_brut_annuel": 20000, "annee_naissance": 1986},
            ],
            "children": [{"annee_naissance": 2015}],
            "couple_marie_ou_pacse": True,
        }
    ).resolved_parent_isole() is False


def test_the_half_part_is_worth_real_money() -> None:
    """Not a cosmetic row: at 40 k€ with one child it is 919 € of income tax."""
    claimed = compute(
        HouseholdInput.model_validate({**LONE_PARENT, "parent_isole": True}), 2024, tier="light"
    ).baseline
    waived = compute(
        HouseholdInput.model_validate({**LONE_PARENT, "parent_isole": False}), 2024, tier="light"
    ).baseline
    assert waived["ir"] - claimed["ir"] == pytest.approx(919, abs=2)


def test_parent_isole_is_refused_when_it_cannot_apply() -> None:
    with pytest.raises(ValueError, match="adulte seul"):
        HouseholdInput.model_validate({**LONE_PARENT, "children": [], "parent_isole": True})


# --------------------------------------------------------------------------- #
# income history — the reference-period problem (docs/DECISIONS.md D-005)
# --------------------------------------------------------------------------- #
RENTER = HouseholdInput.model_validate(
    {
        "adults": [{"salaire_brut_annuel": 30000, "annee_naissance": 1990}],
        "logement": {"statut": "locataire_vide", "loyer_mensuel": 600, "zone_apl": 2},
    }
)


def test_income_history_changes_which_years_are_supplied() -> None:
    single = build_situation(RENTER, 2024, historique_revenus=False)
    with_history = build_situation(RENTER, 2024)   # the default since D-011
    assert len(single["individus"]["adulte_0"]["salaire_de_base"]) == 12
    assert len(with_history["individus"]["adulte_0"]["salaire_de_base"]) == 36
    # the annual amount is preserved in each year, not spread across them
    salaries = with_history["individus"]["adulte_0"]["salaire_de_base"]
    for year in (2022, 2023, 2024):
        annual = sum(v for k, v in salaries.items() if k.startswith(f"{year}-"))
        assert annual == pytest.approx(30000.0)


def test_income_history_removes_phantom_benefits() -> None:
    """Both behaviours pinned, so the size of the error stays visible.

    RSA and the prime d'activité are assessed on the previous quarter; the aide au
    logement on a rolling twelve months ending thirteen months back. Supply the
    target year alone and every one of those windows reads as zero income, so a
    30 k€ earner is awarded housing aid and RSA they are not entitled to.
    """
    naive = compute(RENTER, 2024, tier="full", historique_revenus=False).baseline
    honest = compute(RENTER, 2024, tier="full").baseline   # the default since D-011

    assert naive["aide_logement"] == pytest.approx(1989.32, abs=2)
    assert naive["rsa"] == pytest.approx(534.82, abs=2)
    assert honest["aide_logement"] == 0.0
    assert honest["rsa"] == 0.0

    # ~2 485 €, or 11 % of disposable income
    assert naive["revenu_disponible"] - honest["revenu_disponible"] == pytest.approx(2485, abs=5)


def test_income_history_does_not_move_the_tax_block() -> None:
    """Income tax is assessed on the year itself; only the benefits move."""
    naive = compute(RENTER, 2024, tier="full", historique_revenus=False).baseline
    honest = compute(RENTER, 2024, tier="full").baseline
    for key in ("ir", "salaire_net", "parts_fiscales", "revenu_fiscal_reference"):
        assert naive[key] == honest[key], key


def test_emtr_step_stays_inside_the_target_year() -> None:
    """With three years of salary on file, the marginal euro must still be a euro
    of 2024 — spreading it over 36 months would divide the EMTR step by three."""
    situation = build_situation(RENTER, 2024)
    perturbed = perturb_first_adult(situation, 2024, EMTR_STEP)
    salaries = perturbed["individus"]["adulte_0"]["salaire_de_base"]
    in_2024 = sum(v for k, v in salaries.items() if k.startswith("2024-"))
    in_2023 = sum(v for k, v in salaries.items() if k.startswith("2023-"))
    assert in_2024 == pytest.approx(30000.0 + EMTR_STEP)
    assert in_2023 == pytest.approx(30000.0)


def test_history_is_the_default() -> None:
    """D-011: a caller who says nothing gets the defensible wiring, not the one
    that credits phantom benefits."""
    assert len(build_situation(SINGLE, 2024)["individus"]["adulte_0"]["salaire_de_base"]) == 36
    assert compute(SINGLE, 2024, tier="full").historique_revenus is True


def test_a_write_aimed_at_the_shared_baseline_is_refused() -> None:
    """`baseline()` is memoised, so writing to its tree mutates every later read.

    The production path never does this — `Reform(tbs)` clones first, which
    `test_no_mutation` proves — but an ad-hoc probe does, and the failure is SILENT: the
    script then compares the mutated tree against itself, the number does not move, and
    a live parameter looks dead. That is exactly what happened while checking whether
    `taux_cdhr` was a real knob (it is: -75 836 to -281 236 on two distinct systems).

    Fails if the guard is removed from `update_existing`.
    """
    from impots.engine.system import baseline
    from impots.parameters import ParameterWriteError, update_existing

    path = ("impot_revenu", "contributions_exceptionnelles",
            "contribution_differentielle_hauts_revenus", "taux_cdhr")
    with pytest.raises(ParameterWriteError, match="mémoïsé"):
        update_existing(baseline().parameters, path, start="2026-01-01",
                        value=0.30, instant="2026-01-01")


def test_the_guard_does_not_block_a_system_of_ones_own() -> None:
    """The kill test for the guard above: refusing everything would prove nothing."""
    from openfisca_france import FranceTaxBenefitSystem

    from impots.parameters import update_existing

    fresh = FranceTaxBenefitSystem()
    path = ("impot_revenu", "contributions_exceptionnelles",
            "contribution_differentielle_hauts_revenus", "taux_cdhr")
    update_existing(fresh.parameters, path, start="2026-01-01",
                    value=0.30, instant="2026-01-01")
    node = fresh.parameters("2026-01-01").impot_revenu.contributions_exceptionnelles
    assert float(node.contribution_differentielle_hauts_revenus.taux_cdhr) == 0.30


# --------------------------------------------------------------------------- #
# pensions — the CSG spiral (docs/DECISIONS.md D-176)
# --------------------------------------------------------------------------- #
# `retraite_imposable` is `retraite_brute + csg_deductible_retraite`, and the rate of
# every pension levy reads the RFR of N-2, which reads `retraite_imposable` of N-2: a
# regress through the years that openfisca cuts at its second turn, wherever the
# evaluation order happens to put that turn. `pension_annuelle` is the DECLARED amount
# (D-175), already net of the deductible CSG.
PENSIONER = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1955,
                 "pension_annuelle": 50_000}]}
)
LOW_PENSIONER = HouseholdInput.model_validate(
    {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1955,
                 "pension_annuelle": 15_000}]}
)
EARNER_AND_PENSIONER = HouseholdInput.model_validate(
    {
        "adults": [
            {"salaire_brut_annuel": 35000, "annee_naissance": 1965},
            {"salaire_brut_annuel": 0, "annee_naissance": 1955, "pension_annuelle": 25_000},
        ],
        "couple_marie_ou_pacse": True,
    }
)
PENSION_HOUSEHOLDS = {"pensioner": PENSIONER, "earner_and_pensioner": EARNER_AND_PENSIONER}
#: CSG imposable 2.4 % + CRDS 0.5 % + CASA 0.3 %, at the full rate: the pension levies
#: that are NOT deductible, and so the only ones left to take off a declared amount.
NON_DEDUCTIBLE_FULL_RATE = 0.024 + 0.005 + 0.003


@functools.cache
def _both_orders(name: str) -> tuple[dict, dict]:
    """The same household on two fresh simulations: through the registry, as the API
    computes it, and with `revenu_disponible` computed first, as the EMTR's bumped leg
    and the population EMTR compute it."""
    situation = build_situation(PENSION_HOUSEHOLDS[name], 2024)
    registry = extract(SimulationBuilder().build_from_entities(baseline(), situation),
                       2024, "full")
    first = SimulationBuilder().build_from_entities(baseline(), situation)
    disposable = float(first.calculate("revenu_disponible", "2024")[0])
    return registry, {
        "revenu_disponible": disposable,
        "ir": -float(first.calculate("impot_revenu_restant_a_payer", "2024")[0]),
        "retraite_imposable": float(first.calculate_add("retraite_imposable", "2024").sum()),
    }


@pytest.mark.parametrize("name", sorted(PENSION_HOUSEHOLDS))
def test_a_pension_prices_the_same_whatever_is_computed_first(name: str) -> None:
    """Measured on the code before D-176: the 50 000 EUR pensioner's disposable income
    came out 2 065 EUR lower when `revenu_disponible` was computed first, and the
    earner-and-pensioner couple's 1 263 EUR lower. Same household, same law, two
    answers, chosen by which variable a caller happened to ask for first."""
    registry, first = _both_orders(name)
    for key in ("revenu_disponible", "ir", "retraite_imposable"):
        assert first[key] == pytest.approx(registry[key], abs=0.5), key


def test_disposable_income_takes_only_the_non_deductible_levies_off_a_declared_pension(
) -> None:
    """By hand, in the order that used to go wrong. A declared pension is already net of
    the deductible CSG (5.9 % at the full rate); what is left to take off it is the
    CSG imposable, the CRDS and the CASA, 3.2 % between them.

    Computed first, `revenu_disponible` took the deductible CSG off a SECOND time — 2 950
    EUR on this pensioner — and the income tax it netted was assessed on 47 050 EUR,
    not on the 50 000 typed."""
    _, first = _both_orders("pensioner")
    expected = 50_000 * (1 - NON_DEDUCTIBLE_FULL_RATE) - first["ir"]
    assert first["revenu_disponible"] == pytest.approx(expected, abs=1.0)
    assert first["retraite_imposable"] == pytest.approx(50_000, abs=0.5)


def test_a_pensioner_below_the_exemption_threshold_pays_no_csg() -> None:
    """Born in 1955 with 15 000 EUR declared: an RFR for 2022 of 15 000 - 10 % - 2 620
    (the abattement for the over-65s) = 10 880, under the 12 230 EUR exemption threshold
    for one part. No CSG, CRDS or CASA in 2024, no income tax, no benefit at this level.

    The registry order charged 75 EUR of CRDS: the levies were first computed inside the
    prime d'activité's cascade, on an RFR of N-2 read inside a cut spiral that had lost
    the abattement — 13 500, over the threshold, so the taux réduit."""
    rows = compute(LOW_PENSIONER, 2024, tier="full").baseline
    assert rows["ir"] == 0.0
    assert rows["revenu_disponible"] == pytest.approx(15_000, abs=0.5)


def test_the_reported_taxable_pension_is_the_declared_one_beside_a_salary() -> None:
    """D-175 pinned this on a lone pensioner. Beside a salary it did not hold: the row
    read 24 050 — the 25 000 declared less 3.8 %, the deductible CSG at the taux réduit,
    from an RFR of N-2 that had lost the pension — while the income tax in the same
    response had been assessed on 25 000. Two bases in one answer."""
    rows = compute(EARNER_AND_PENSIONER, 2024, tier="light").baseline
    assert rows["retraite_imposable"] == pytest.approx(25_000, abs=0.5)


def test_a_pensioners_emtr_compares_two_computations_of_the_same_kind() -> None:
    """The EMTR's base comes from the registry and its bumped leg from a fresh
    simulation that computes `revenu_disponible` first. Before D-176 those were the two
    regimes above, and a 50 000 EUR pensioner offered 100 EUR of salary was reported a
    marginal rate of 20.86 — 2 086 %. Recomputed by hand, both legs through the
    registry."""
    result = compute(PENSIONER, 2024, tier="full", emtr=True)
    bumped = perturb_first_adult(build_situation(PENSIONER, 2024), 2024, EMTR_STEP)
    by_hand = 1.0 - (
        extract(SimulationBuilder().build_from_entities(baseline(), bumped), 2024, "full")[
            "revenu_disponible"] - result.baseline["revenu_disponible"]
    ) / EMTR_STEP
    assert result.emtr == pytest.approx(by_hand, abs=1e-3)
    assert 0.0 < result.emtr < 1.0


def _chomeur(amount: float = 30_000, **household: Any) -> HouseholdInput:
    """A chômeur and nothing else. Built when a test asks, not at import: a model the
    wire format refuses would otherwise fail every test in this file at once."""
    return HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1980,
                     "chomage_brut_annuel": amount}], **household})


def test_an_unemployed_persons_emtr_compares_two_computations_of_the_same_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The household builder has to close the regress for whatever a situation carries:
    the EMTR's base comes from the registry, its bumped leg from a fresh simulation that
    computes `revenu_disponible` first, and before D-177 those two read the RFR of N-2
    differently. A 30 000 EUR chômeur offered 100 EUR of salary was reported a marginal
    rate of -2.68. The benefit was written into the situation by hand then, the way a
    field would write it; it is typed on the wire since D-183.

    Both legs of the hand computation go through `compute`, so through the same builder
    as the rate under test: the bumped one by perturbing the situation it builds."""
    from impots.engine import situations

    original = situations.build_situation
    bump = {"on": False}

    def bumped_on_demand(household, year, historique_revenus=True):
        situation = original(household, year, historique_revenus)
        return perturb_first_adult(situation, year, EMTR_STEP) if bump["on"] else situation

    monkeypatch.setattr(situations, "build_situation", bumped_on_demand)
    unemployed = _chomeur()
    result = compute(unemployed, 2024, tier="full", emtr=True)
    bump["on"] = True
    bumped = compute(unemployed, 2024, tier="full").baseline["revenu_disponible"]
    by_hand = 1.0 - (bumped - result.baseline["revenu_disponible"]) / EMTR_STEP
    assert result.emtr == pytest.approx(by_hand, abs=1e-3)
    assert 0.0 < result.emtr < 1.0


def test_a_renters_emtr_compares_two_computations_of_the_same_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Housing aid and the RSA feed each other through the months: the aid's
    neutralisation reads the RSA of the month before, whose forfait logement reads the
    aid of that month. With the aid of N on the stack, openfisca cut the aid of N-1 to
    zero, and the prime d'activité of January to March lost the forfait logement of its
    reference quarter. The EMTR's bumped leg, `revenu_disponible` first, fell into that;
    its base, through the registry, did not. Before D-178 a single renter on 17 000 EUR
    was reported a marginal rate of -0.68, and on 9 000 EUR of -1.36.

    Both legs of the hand computation go through `compute`, the bumped one by perturbing
    the situation it builds."""
    from impots.engine import situations

    original = situations.build_situation
    bump = {"on": False}

    def bumped_on_demand(household, year, historique_revenus=True):
        situation = original(household, year, historique_revenus)
        return perturb_first_adult(situation, year, EMTR_STEP) if bump["on"] else situation

    monkeypatch.setattr(situations, "build_situation", bumped_on_demand)
    renter = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 17_000, "annee_naissance": 1984}],
         "logement": {"statut": "locataire_vide", "loyer_mensuel": 700, "zone_apl": 2}})
    result = compute(renter, 2024, tier="full", emtr=True)
    bump["on"] = True
    bumped = compute(renter, 2024, tier="full").baseline["revenu_disponible"]
    by_hand = 1.0 - (bumped - result.baseline["revenu_disponible"]) / EMTR_STEP
    assert result.emtr == pytest.approx(by_hand, abs=1e-3)
    assert 0.0 < result.emtr < 1.0


#: Beside an AAH recipient, the partner whose minimum reads the AAH of the three months
#: before: an ASPA pensioner, and an ASI recipient (invalidity pension and handicap).
AAH_PARTNERS = {
    "aspa": ({"salaire_brut_annuel": 0, "annee_naissance": 1955, "pension_annuelle": 5_000},
             {}),
    "asi": ({"salaire_brut_annuel": 0, "annee_naissance": 1972},
            {"pensions_invalidite": 250.0, "handicap": True}),
}


@pytest.mark.parametrize("partner", sorted(AAH_PARTNERS))
def test_an_aah_recipients_emtr_beside_a_partners_minimum_compares_like_with_like(
    partner: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ASPA and the ASI count the household's other minima over the three months
    before, an AAH among them. `revenu_disponible` computed first reaches the AAH of a
    month through the PAJE's childcare supplement, and beneath it the ASI of the month
    before reads a family base where the AAH of earlier months is cut to zero; the
    partner's minimum then read that base. On the unhoused AAH + ASPA couple, the ASPA of
    January to March came out at 1 012, 831 and 507 EUR instead of 183. The registry
    order did not cut it. Housed, the D-178 pin protected the base; without a dwelling,
    the builder skipped that pin, and the EMTR compared one order with the other: -16.19
    beside the ASPA pensioner and -17.61 beside the ASI recipient, against 0.23 by hand.

    The taux d'incapacité was written into the situation by hand then; it is typed on the
    wire since D-184. The partner's invalidity inputs, which no field writes, still are,
    on every covered month. Both legs of the hand computation go through `compute`
    (D-179)."""
    from impots.engine import situations

    original = situations.build_situation
    bump = {"on": False}
    person, partner_inputs = AAH_PARTNERS[partner]

    def with_partner_inputs(household, year, historique_revenus=True):
        situation = original(household, year, historique_revenus)
        covered = [month for y in situations.covered_years(year, historique_revenus)
                   for month in situations.months(y)]
        for name, value in partner_inputs.items():
            situation["individus"]["adulte_1"][name] = dict.fromkeys(covered, value)
        return perturb_first_adult(situation, year, EMTR_STEP) if bump["on"] else situation

    monkeypatch.setattr(situations, "build_situation", with_partner_inputs)
    couple = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 6_000, "annee_naissance": 1975,
                     "handicap": {"taux_incapacite": 0.8}}, person],
         "couple_marie_ou_pacse": True})
    result = compute(couple, 2024, tier="full", emtr=True)
    bump["on"] = True
    bumped = compute(couple, 2024, tier="full").baseline["revenu_disponible"]
    by_hand = 1.0 - (bumped - result.baseline["revenu_disponible"]) / EMTR_STEP
    assert result.emtr == pytest.approx(by_hand, abs=1e-3)
    assert 0.0 < result.emtr < 1.0


#: A pensioner at the ASPA level who rents, the household on which D-180 was found.
ASPA_PENSIONER = {"annee_naissance": 1950, "pension_annuelle": 7_000}
RENTING = {"statut": "locataire_vide", "loyer_mensuel": 500, "zone_apl": 2}


def _aspa_renter(salary: float) -> HouseholdInput:
    return HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": salary, **ASPA_PENSIONER}], "logement": RENTING})


def test_a_small_salary_beside_a_pension_leaves_the_housing_aid_alone() -> None:
    """The housing aid counts net categorical income (CCH art. R. 822-4), and the 10 %
    deduction on salaries may not exceed the gross salaries it is taken from (CGI art. 83,
    3°). openfisca took the 495 EUR minimum off 82 EUR of taxable salary and carried the
    difference onto the pension: declaring 100 EUR of salary raised this pensioner's
    housing aid from 3 115.89 to 3 265.56 EUR a year (D-180)."""
    without = compute(_aspa_renter(0), 2024, tier="full").baseline
    with_salary = compute(_aspa_renter(100), 2024, tier="full").baseline
    assert with_salary["aide_logement"] == pytest.approx(without["aide_logement"], abs=0.01)


def test_a_housed_pensioners_emtr_at_zero_salary_is_the_salarys_own_levies() -> None:
    """The same defect, seen through the EMTR's finite difference: 100 EUR of salary lifted
    the housing aid more than the salary itself, and a pensioner at the ASPA level who
    rents was reported a marginal rate of -1.04. Below the minimum deduction, a salary
    owes its own contributions and nothing else moves, so the rate is what they take."""
    result = compute(_aspa_renter(0), 2024, tier="full", emtr=True)
    net = compute(_aspa_renter(EMTR_STEP), 2024, tier="light").baseline["salaire_net"]
    assert result.emtr == pytest.approx(1.0 - net / EMTR_STEP, abs=1e-3)


def test_the_engine_alone_lets_the_deduction_minimum_eat_a_pension() -> None:
    """The kill test for the correction above: without it, the defect is there.

    7 000 EUR of pension less its 10 % is 6 300. Over the housing aid's rolling year, 100
    EUR of gross salary is 82.16 of taxable salary; the 495 EUR minimum deduction exceeds
    it by 412.84, and the raw engine takes that off the pension. The day this fails,
    openfisca caps the deduction itself, and `engine.corrections` must go."""
    from impots.engine import situations
    from impots.engine.system import uncorrected_baseline

    situation = situations.build_situation(_aspa_renter(100), 2024)
    raw = SimulationBuilder().build_from_entities(uncorrected_baseline(), situation)
    base = float(raw.calculate("aide_logement_base_ressources_individu", "2024-06")[0])
    assert base == pytest.approx(6_300 - (495 - 82.16), abs=0.05), (
        "openfisca no longer lets the minimum deduction eat a pension: remove the "
        "correction rather than keep one that corrects nothing")


def test_each_benefit_correction_names_a_kill_test_that_exists() -> None:
    """A correction whose kill test does not exist could never be retired when openfisca
    fixes the thing it corrects (the rule of `patrimoine.corrections`, here for benefits).

    A citation of the social security code is accepted since D-184: the MVA correction
    rests on the CSS, and benefits law lives there more often than in the CGI. One of the
    construction code since D-187: the housing aid's taper rests on the CCH. One of the
    labour code since D-189: the ASS's resources rest on the C. trav."""
    from pathlib import Path

    from impots.engine.corrections import CORRECTIONS

    source = Path(__file__).read_text(encoding="utf-8")
    assert CORRECTIONS
    for correction in CORRECTIONS:
        assert correction.citation.startswith(
            ("CGI art.", "CSS art.", "CCH art.", "C. trav. art.")), correction.name
        assert correction.decision.startswith("D-"), correction.name
        assert f"def {correction.kill_test}" in source, correction.name


# --------------------------------------------------------------------------- #
# unemployment benefit on the wire (docs/DECISIONS.md D-183)
# --------------------------------------------------------------------------- #
def test_unemployment_benefit_is_written_gross_and_monthly_on_every_covered_year() -> None:
    """Onto `chomage_brut`, a twelfth a month, on N-2 to N: as the salary is written, and
    as the population writes its `chomage_annuel`. The history is what gives the CSG of N
    its RFR of N-2 and the housing aid its reference year. An adult who declares no
    benefit carries no such input, so a situation lists what was typed and nothing else."""
    benefit = build_situation(_chomeur(), 2024)["individus"]["adulte_0"]["chomage_brut"]
    assert len(benefit) == 36
    for year in (2022, 2023, 2024):
        in_year = [value for key, value in benefit.items() if key.startswith(f"{year}-")]
        assert in_year == [pytest.approx(2_500.0)] * 12
    single_year = build_situation(_chomeur(), 2024, historique_revenus=False)
    assert list(single_year["individus"]["adulte_0"]["chomage_brut"]) == [
        f"2024-{month:02d}" for month in range(1, 13)]
    assert "chomage_brut" not in build_situation(SINGLE, 2024)["individus"]["adulte_0"]


def test_a_chomeur_is_taxed_and_levied_as_the_law_says() -> None:
    """By hand. The CSG is assessed on 98.25 % of the benefit (the 1.75 % abatement), 3.8 %
    of it deductible: 30 000 - 0.038 x 29 475 = 28 879.95 EUR taxable, the amount of box
    1AP. Less the 10 % deduction that salaries and unemployment benefit share, 25 991.95
    of RFR. The income tax is the one assessed when that taxable amount is itself the
    input, which no spiral can reach (D-177). Above the SMIC floor, and with an RFR of N-2
    over the full-rate threshold, 6.2 % of CSG and 0.5 % of CRDS are due on the 29 475.

    Those levies have no row of their own: the CSG and CRDS rows are the salary's. They
    are in the disposable income, and that is where they are checked."""
    assiette = 30_000 * (1 - 0.0175)
    taxable = 30_000 - 0.038 * assiette
    rows = compute(_chomeur(), 2024, tier="full").baseline
    assert rows["chomage_brut"] == pytest.approx(30_000, abs=0.5)
    assert rows["revenu_fiscal_reference"] == pytest.approx(0.9 * taxable, abs=0.5)

    oracle = build_situation(HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1980}]}), 2024)
    oracle["individus"]["adulte_0"]["chomage_imposable"] = {
        f"2024-{month:02d}": taxable / 12 for month in range(1, 13)}
    simulation = SimulationBuilder().build_from_entities(baseline(), oracle)
    ir_on_taxable = -float(simulation.calculate("impot_revenu_restant_a_payer", "2024")[0])
    assert rows["ir"] == pytest.approx(ir_on_taxable, abs=0.5)

    levies = (0.062 + 0.005) * assiette
    assert rows["revenu_disponible"] == pytest.approx(30_000 - levies - rows["ir"], abs=1.0)


# --------------------------------------------------------------------------- #
# disability on the wire: the AAH (docs/DECISIONS.md D-184)
# --------------------------------------------------------------------------- #
#: The AAH in 2024: 971.37 EUR a month from January, 1 016.05 from April.
AAH_2024 = 3 * 971.37 + 9 * 1_016.05
#: The majoration pour la vie autonome, 104.77 EUR a month all year.
MVA_2024 = 12 * 104.77


def _handicape(taux: float = 0.8, *, rsdae: bool = False, naissance: int = 1980,
               logement: dict[str, Any] | None = None, **revenus: Any) -> HouseholdInput:
    """One adult the CDAPH recognised, and nothing else unless asked. Built when a test
    asks, like `_chomeur`."""
    handicap: dict[str, Any] = {"taux_incapacite": taux}
    if rsdae:
        handicap["restriction_substantielle_durable_acces_emploi"] = True
    household: dict[str, Any] = {"adults": [
        {"salaire_brut_annuel": 0, "annee_naissance": naissance, "handicap": handicap,
         **revenus}]}
    if logement is not None:
        household["logement"] = logement
    return HouseholdInput.model_validate(household)


def test_a_disability_is_written_on_every_covered_month() -> None:
    """The rate the CDAPH recognised, on every month from N-2 to N, like the salary: the
    AAH of N-2 and N-1 is what the RSA, the prime d'activité and a partner's minimum read
    back. The restriction on employment only when recognised. And not openfisca's generic
    `handicap` flag, which would also open the ASI beside a retirement pension (D-184)."""
    adult = build_situation(_handicape(), 2024)["individus"]["adulte_0"]
    assert list(adult["taux_incapacite"].values()) == [0.8] * 36
    assert "aah_restriction_substantielle_durable_acces_emploi" not in adult
    assert "handicap" not in adult
    restricted = build_situation(_handicape(0.6, rsdae=True), 2024)["individus"]["adulte_0"]
    assert list(restricted["aah_restriction_substantielle_durable_acces_emploi"].values()) == [
        True] * 36
    assert "taux_incapacite" not in build_situation(SINGLE, 2024)["individus"]["adulte_0"]


def test_an_aah_without_resources_is_paid_in_full() -> None:
    """By hand: 971.37 EUR a month to March, 1 016.05 from April, 12 058.56 over 2024, and
    the disposable income is the AAH. Without a dwelling there is no housing aid, so no
    majoration pour la vie autonome."""
    rows = compute(_handicape(), 2024, tier="full").baseline
    assert rows["aah"] == pytest.approx(AAH_2024, abs=0.05)
    assert rows["mva"] == 0.0
    assert rows["revenu_disponible"] == pytest.approx(AAH_2024, abs=0.05)


def test_between_fifty_and_seventy_nine_per_cent_the_aah_needs_the_restriction() -> None:
    """CSS art. L. 821-2: from 50 % the AAH opens only with a substantial and lasting
    restriction on access to employment, recognised by the CDAPH."""
    with_restriction = compute(_handicape(0.6, rsdae=True), 2024, tier="full").baseline
    without = compute(_handicape(0.6), 2024, tier="full").baseline
    assert with_restriction["aah"] == pytest.approx(AAH_2024, abs=0.05)
    assert without["aah"] == 0.0


def test_the_restriction_on_employment_is_refused_below_fifty_per_cent() -> None:
    """Below 50 % it opens nothing, and the engine would ignore it without a word."""
    with pytest.raises(ValueError, match="50"):
        _handicape(0.4, rsdae=True)


def test_a_housed_aah_without_resources_carries_the_mva() -> None:
    """CSS art. L. 821-1-2: an independent dwelling with a housing aid, the AAH at its full
    rate, no professional income. 104.77 EUR a month."""
    rows = compute(_handicape(logement=RENTING), 2024, tier="full").baseline
    assert rows["aah"] == pytest.approx(AAH_2024, abs=0.05)
    assert rows["mva"] == pytest.approx(MVA_2024, abs=0.05)
    assert rows["aide_logement"] > 0


def test_an_aah_cut_by_unemployment_benefit_carries_no_mva() -> None:
    """CSS art. L. 821-1-2, 2°: the MVA goes to an AAH « à taux plein ou en complément
    d'un avantage de vieillesse ou d'invalidité ou d'une rente d'accident du travail ».
    3 000 EUR of unemployment benefit a year takes January's AAH to 936.37 EUR: neither,
    so no MVA. openfisca paid it all year, 1 257.24 EUR (D-182, D-184)."""
    rows = compute(_handicape(logement=RENTING, chomage_brut_annuel=3_000), 2024,
                   tier="full").baseline
    assert rows["aah"] < AAH_2024 - 100
    assert rows["mva"] == 0.0


def test_an_aah_topping_up_a_pension_keeps_its_mva() -> None:
    """The other half of the 2°: an AAH cut by a retirement pension complements an old-age
    benefit, and keeps the MVA. Aged 60, 3 000 EUR of pension: the AAH tops it up to the
    AAH amount exactly."""
    rows = compute(_handicape(naissance=1964, logement=RENTING, pension_annuelle=3_000), 2024,
                   tier="full").baseline
    assert rows["aah"] + 3_000 == pytest.approx(AAH_2024, abs=0.05)
    assert rows["mva"] == pytest.approx(MVA_2024, abs=0.05)


def test_the_engine_alone_pays_the_mva_beside_an_aah_cut_by_unemployment_benefit() -> None:
    """The kill test for the MVA correction: without it, the defect is there. The day this
    fails, openfisca checks the « taux plein » itself, and `engine.corrections` must
    drop its own."""
    from impots.engine.system import uncorrected_baseline

    situation = build_situation(_handicape(logement=RENTING, chomage_brut_annuel=3_000), 2024)
    raw = SimulationBuilder().build_from_entities(uncorrected_baseline(), situation)
    assert float(raw.calculate("aah", "2024-01")[0]) == pytest.approx(936.37, abs=0.01)
    assert float(raw.calculate("caah", "2024-01")[0]) == pytest.approx(104.77, abs=0.01), (
        "openfisca no longer pays the MVA beside a reduced AAH: remove the correction "
        "rather than keep one that corrects nothing")


#: The ASPA in 2024 for a person alone, 1 012.02 EUR a month.
ASPA_SEULE_2024 = 12_144.27


@pytest.mark.parametrize("naissance", [1960, 1958])
def test_past_62_an_aah_at_eighty_per_cent_is_paid_without_the_aspa(naissance: int) -> None:
    """At 80 % the AAH goes on past 62, topping the pension up to the AAH amount, and its
    recipient « n'a pas l'obligation de demander l'Aspa pour continuer à percevoir l'AAH »
    (Cnav-Cnaf circular 2024-1; CSS art. L. 821-1). So nothing changes from 60 to 64 or 66.
    openfisca paid the AAH and the ASPA in full on the same pension: 25 992.84 EUR of
    disposable income at 66 against 16 848.57 at 60. D-184 refused the case; D-185 prices it."""
    at_60 = compute(_handicape(naissance=1964, logement=RENTING, pension_annuelle=3_000), 2024,
                    tier="full").baseline
    later = compute(_handicape(naissance=naissance, logement=RENTING, pension_annuelle=3_000),
                    2024, tier="full").baseline
    assert later["aah"] + 3_000 == pytest.approx(AAH_2024, abs=0.05)
    assert later["mva"] == pytest.approx(MVA_2024, abs=0.05)
    assert later["revenu_disponible"] == pytest.approx(at_60["revenu_disponible"], abs=0.05)


def test_past_62_an_aah_without_resources_is_the_aah_alone() -> None:
    """Aged 66, no pension, no dwelling: the AAH, 12 058.56 EUR, and no ASPA beside it.
    openfisca paid both, 24 202.83 EUR."""
    rows = compute(_handicape(naissance=1958), 2024, tier="full").baseline
    assert rows["aah"] == pytest.approx(AAH_2024, abs=0.05)
    assert rows["revenu_disponible"] == pytest.approx(AAH_2024, abs=0.05)


@pytest.mark.parametrize(("naissance", "aah"), [(1963, AAH_2024), (1962, 0.0), (1961, 0.0)])
def test_between_fifty_and_seventy_nine_per_cent_the_aah_ends_at_62(
    naissance: int, aah: float,
) -> None:
    """The AAH under CSS art. L. 821-2 « prend fin à l'âge auquel le bénéficiaire est réputé
    inapte au travail », which the 2023 reform kept at 62 for AAH holders (art. L. 351-1-5;
    Cnav-Cnaf circular 2024-1). openfisca read the general legal age, 64, and paid it two
    years longer. A birth on 1 January makes the year of the birthday the first without it."""
    rows = compute(_handicape(0.6, rsdae=True, naissance=naissance), 2024, tier="full").baseline
    assert rows["aah"] == pytest.approx(aah, abs=0.05)


def test_from_62_a_rate_over_fifty_per_cent_opens_the_aspa() -> None:
    """60 % without the restriction on employment: no AAH, and from 62 the ASPA, which the
    law opens at that age to anyone with an incapacity over 50 % (circular 2024-1). openfisca
    waited for 64 and paid the RSA in between: 7 697.09 EUR of disposable income at 62
    instead of the ASPA's 12 144.27."""
    rows = compute(_handicape(0.6, naissance=1962), 2024, tier="full").baseline
    assert rows["aah"] == 0.0
    assert rows["rsa"] == 0.0
    assert rows["revenu_disponible"] == pytest.approx(ASPA_SEULE_2024, abs=0.05)


def test_past_the_aspa_age_the_asi_stays_shut() -> None:
    """The ASI is for people below the ASPA's age (CSS art. L. 815-24), and openfisca reads
    that age off the ASPA's eligibility. An AAH recipient no longer claims the ASPA, so the
    correction keeps the ASI on the age alone: with openfisca's `handicap` flag and a
    pension, aged 66, the ASI must stay shut."""
    situation = build_situation(HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1958,
                     "pension_annuelle": 3_000}]}), 2024)
    covered = [f"{year}-{month:02d}" for year in (2022, 2023, 2024) for month in range(1, 13)]
    situation["individus"]["adulte_0"]["taux_incapacite"] = dict.fromkeys(covered, 0.8)
    situation["individus"]["adulte_0"]["handicap"] = dict.fromkeys(covered, True)
    simulation = SimulationBuilder().build_from_entities(baseline(), situation)
    assert float(simulation.calculate_add("asi", "2024").sum()) == 0.0
    assert float(simulation.calculate_add("aspa", "2024").sum()) == 0.0
    assert float(simulation.calculate_add("aah", "2024").sum()) + 3_000 == pytest.approx(
        AAH_2024, abs=0.05)


def test_the_engine_alone_pays_the_aah_at_fifty_per_cent_until_64() -> None:
    """The kill test for the age correction: raw openfisca still reads 64. The day this
    fails, openfisca has moved to L. 351-1-5's age, and the correction must go."""
    from impots.engine.system import uncorrected_baseline

    situation = build_situation(_handicape(0.6, rsdae=True, naissance=1961), 2024)
    raw = SimulationBuilder().build_from_entities(uncorrected_baseline(), situation)
    assert float(raw.calculate_add("aah", "2024").sum()) == pytest.approx(AAH_2024, abs=0.05), (
        "openfisca no longer pays the AAH at 50-79 % past 62: remove the age correction")


def test_at_eighty_per_cent_the_aah_has_no_age_limit() -> None:
    """At 80 % the AAH does not end at 62; at 63, without resources, it is paid in full."""
    rows = compute(_handicape(naissance=1961), 2024, tier="full").baseline
    assert rows["aah"] == pytest.approx(AAH_2024, abs=0.05)


def test_a_rate_that_opens_no_aah_pays_none_at_any_age() -> None:
    """60 % without the restriction opens no AAH at any age, only the ASPA from 62 (D-185)."""
    rows = compute(_handicape(0.6, naissance=1958, pension_annuelle=3_000), 2024,
                   tier="full").baseline
    assert rows["aah"] == 0.0


def test_the_engine_alone_pays_the_aah_and_the_aspa_in_full_to_one_person() -> None:
    """The kill test for the ASPA correction. 80 %, aged 66, 3 000 EUR of pension: raw
    openfisca tops the pension up to the AAH amount with the AAH, and up to the ASPA's with
    the ASPA, both at once. It was the kill test of D-184's refusal, which D-185 replaced
    with the correction; the day this fails, the correction must go."""
    from impots.engine.system import uncorrected_baseline

    situation = build_situation(HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1958,
                     "pension_annuelle": 3_000}]}), 2024)
    situation["individus"]["adulte_0"]["taux_incapacite"] = dict.fromkeys(
        [f"{year}-{month:02d}" for year in (2022, 2023, 2024) for month in range(1, 13)], 0.8)
    simulation = SimulationBuilder().build_from_entities(uncorrected_baseline(), situation)
    aah = float(simulation.calculate("aah", "2024-06")[0])
    aspa = float(simulation.calculate("aspa", "2024-06")[0])
    assert aah == pytest.approx(1_016.05 - 250, abs=0.01)
    assert aspa > 700, (
        "openfisca no longer pays the ASPA beside the AAH: remove the ASPA correction")


def test_the_aah_rsdae_rate_matches_the_tree() -> None:
    """The wire format pins the rate from which the restriction opens the AAH, because a
    validator must not need a tax-benefit system. Read here from the tree, not trusted."""
    from impots.api.schemas import AAH_TAUX_RSDAE

    tree = baseline().parameters("2024-01-01").prestations_sociales \
        .prestations_etat_de_sante.invalidite.aah.taux_capacite
    assert float(tree.taux_incapacite_rsdae) == AAH_TAUX_RSDAE


def test_the_aspa_has_a_row_of_its_own() -> None:
    """A pensioner at the ASPA level who rents (D-180's household): the ASPA tops the 7 000
    EUR of pension up to its ceiling, 12 144.27 EUR for a person alone in 2024. Before D-186
    it was inside `revenu_disponible` with no row, and the page could show a pensioner's
    disposable income without the 5 144.27 EUR that made it."""
    rows = compute(_aspa_renter(0), 2024, tier="full").baseline
    assert rows["aspa"] == pytest.approx(12_144.27 - 7_000, abs=0.05)


# --------------------------------------------------------------------------- #
# the high-rent taper and the AAH (docs/DECISIONS.md D-187)
# --------------------------------------------------------------------------- #
#: A rent in zone 1 above the taper's threshold for one person, and above the threshold of
#: suppression until the ceiling's revaluation in October 2024; and one under the taper.
#: Both exceed the rent ceiling, so the aid before the taper is the same.
HIGH_RENT = {"statut": "locataire_vide", "loyer_mensuel": 1_300, "zone_apl": 1}
LOW_RENT = {"statut": "locataire_vide", "loyer_mensuel": 900, "zone_apl": 1}


def _pinned(situation: dict[str, Any]) -> Any:
    """A simulation built as `compute` builds the full tier: the RFR of N-2 and the
    housing aid pinned before anything is asked of it (D-177, D-178)."""
    from impots.engine import situations

    simulation = SimulationBuilder().build_from_entities(baseline(), situation)
    situations.pin_rfr_n_2(simulation, 2024)
    situations.pin_benefit_history(simulation, 2024)
    return simulation


def test_an_aah_beneficiary_keeps_the_whole_housing_aid_above_the_taper() -> None:
    """CCH art. D. 823-16: the aid falls once the rent passes a threshold, « Toutefois, cette
    diminution ne s'applique pas lorsque le demandeur ou son conjoint est bénéficiaire de
    l'allocation aux adultes handicapés ». At 1 300 EUR in zone 1, openfisca paid 84.72 EUR
    over 2024, three months of a tapered aid, against 4 026.60 untapered; the MVA, which
    needs a housing aid every month, followed with 314.31 EUR instead of 1 257.24 (D-184,
    D-187)."""
    high = compute(_handicape(logement=HIGH_RENT), 2024, tier="full").baseline
    low = compute(_handicape(logement=LOW_RENT), 2024, tier="full").baseline
    assert high["aah"] == pytest.approx(AAH_2024, abs=0.05)
    assert high["aide_logement"] == pytest.approx(4_026.60, abs=0.05)
    assert high["aide_logement"] == pytest.approx(low["aide_logement"], abs=0.05)
    assert high["mva"] == pytest.approx(MVA_2024, abs=0.05)
    assert high["revenu_disponible"] == pytest.approx(low["revenu_disponible"], abs=0.05)


def test_the_spouse_s_aah_lifts_the_taper_too() -> None:
    """« le demandeur ou son conjoint »: here the AAH is the spouse's. At 1 600 EUR in zone 1
    the couple's aid was cut to nothing; it is the aid the couple gets under the taper."""
    def couple(logement: dict[str, Any]) -> HouseholdInput:
        return HouseholdInput.model_validate({"adults": [
            {"salaire_brut_annuel": 0, "annee_naissance": 1980},
            {"salaire_brut_annuel": 0, "annee_naissance": 1980,
             "handicap": {"taux_incapacite": 0.8}}],
            "couple_marie_ou_pacse": True, "logement": logement})

    high = compute(couple({**HIGH_RENT, "loyer_mensuel": 1_600}), 2024, tier="full").baseline
    low = compute(couple(LOW_RENT), 2024, tier="full").baseline
    assert high["aah"] == pytest.approx(AAH_2024, abs=0.05)
    assert low["aide_logement"] > 0
    assert high["aide_logement"] == pytest.approx(low["aide_logement"], abs=0.05)


def test_an_aah_that_is_not_paid_lifts_no_taper() -> None:
    """A « bénéficiaire » of the AAH is someone it is paid to, not someone eligible for it. At
    80 % and aged 60, a 13 000 EUR pension leaves no AAH, and the aid is tapered as for anyone
    with that pension: 24.81 EUR at 1 300 EUR, against 1 510.35 under the taper."""
    disabled = compute(_handicape(naissance=1964, logement=HIGH_RENT, pension_annuelle=13_000),
                       2024, tier="full").baseline
    twin = compute(HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1964,
                     "pension_annuelle": 13_000}], "logement": HIGH_RENT}),
        2024, tier="full").baseline
    assert disabled["aah"] == 0.0
    assert disabled["aide_logement"] == pytest.approx(24.81, abs=0.05)
    assert disabled["aide_logement"] == pytest.approx(twin["aide_logement"], abs=0.05)


def test_a_dependent_s_aah_lifts_no_taper() -> None:
    """Only the claimant's or the spouse's AAH lifts it. A child of 22 at 80 % in the
    famille draws the AAH, written by hand since the child's field refuses a child of 20
    or more (D-191), and the aid stays the tapered one, 84.72 EUR, as without that
    disability."""
    household = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1970}],
         "children": [{"annee_naissance": 2002}], "logement": HIGH_RENT})
    covered = [f"{year}-{month:02d}" for year in (2022, 2023, 2024) for month in range(1, 13)]

    def aid(taux: float | None) -> tuple[float, float]:
        situation = build_situation(household, 2024)
        if taux is not None:
            situation["individus"]["enfant_0"]["taux_incapacite"] = dict.fromkeys(covered, taux)
        simulation = _pinned(situation)
        return (float(simulation.calculate_add("aah", "2024").sum()),
                float(simulation.calculate_add("aide_logement", "2024").sum()))

    aah, with_disability = aid(0.8)
    assert aah == pytest.approx(AAH_2024, abs=0.05)
    assert with_disability == pytest.approx(aid(None)[1], abs=0.05)
    assert with_disability == pytest.approx(84.72, abs=0.05)


def test_the_untapered_aid_prices_the_same_whatever_is_computed_first() -> None:
    """The correction reads the AAH of the month inside the housing aid, which the builder
    pins month by month (D-178). Through the registry, as the API computes it, and with
    `revenu_disponible` first, as the EMTR's bumped leg does, every figure agrees."""
    situation = build_situation(_handicape(logement=HIGH_RENT), 2024)
    registry = extract(_pinned(situation), 2024, "full")
    first = _pinned(situation)
    disposable = float(first.calculate("revenu_disponible", "2024")[0])
    assert disposable == pytest.approx(registry["revenu_disponible"], abs=0.05)
    for key, variable in (("aide_logement", "aide_logement"), ("aah", "aah"), ("mva", "caah")):
        assert float(first.calculate_add(variable, "2024").sum()) == pytest.approx(
            registry[key], abs=0.05), key


def test_the_engine_alone_tapers_the_aid_of_an_aah_beneficiary() -> None:
    """The kill test for the taper correction. openfisca lifts the taper only on its generic
    `handicap` flag, which this project never sets, since it also opens the ASI beside a
    pension (D-184). The day this fails, openfisca reads the AAH itself, and the correction
    must go."""
    from impots.engine.system import uncorrected_baseline

    situation = build_situation(_handicape(logement=HIGH_RENT), 2024)
    raw = SimulationBuilder().build_from_entities(uncorrected_baseline(), situation)
    month = "2024-11"
    assert float(raw.calculate("aah", month)[0]) > 0
    before = float(raw.calculate("aide_logement_montant_brut_avant_degressivite", month)[0])
    after = float(raw.calculate("aide_logement_montant_brut", month)[0])
    assert after < before / 2, (
        "openfisca no longer tapers the aid of an AAH beneficiary: remove the correction "
        "rather than keep one that corrects nothing")


# --------------------------------------------------------------------------- #
# the invalidity card: cases P and F, and the abatement of art. 157 bis (D-188)
# --------------------------------------------------------------------------- #
def _adulte(salaire: float = 0, naissance: int = 1980, *, carte: bool = False,
            **fields: Any) -> dict[str, Any]:
    """One adult of the wire format; `carte` declares the card « mobilité inclusion »
    marked « invalidité »."""
    adult = {"salaire_brut_annuel": salaire, "annee_naissance": naissance, **fields}
    if carte:
        adult["carte_invalidite"] = True
    return adult


def _foyer(*adults: dict[str, Any], **household: Any) -> HouseholdInput:
    """One adult, or two married or pacsés."""
    payload: dict[str, Any] = {"adults": list(adults), **household}
    if len(adults) == 2:
        payload["couple_marie_ou_pacse"] = True
    return HouseholdInput.model_validate(payload)


def _rows(household: HouseholdInput, tier: str = "light") -> dict[str, Any]:
    return compute(household, 2024, tier=tier).baseline


def _foyer_variable(household: HouseholdInput, variable: str, year: str,
                    system: Any = None) -> float:
    """A variable of the foyer fiscal, read off a simulation of `household` on `system`
    (the corrected baseline unless told otherwise)."""
    situation = build_situation(household, 2024)
    simulation = SimulationBuilder().build_from_entities(system or baseline(), situation)
    return float(simulation.calculate(variable, year)[0])


def test_the_card_is_written_as_case_p_or_f_on_every_covered_year() -> None:
    """The first adult's card is case P of the 2042, the second's case F: booleans of the
    foyer fiscal, on N-2 to N like every input the history carries, since the housing aid
    and the family benefits deduct the abatement it opens from the resources of N-2 (CCH
    art. R. 822-4; CSS art. R. 532-3), and the CSG of a replacement income reads the RFR
    and the parts of N-2. Nothing is written on the individual: openfisca's own
    `invalidite` flag counts dependent children only (cases G and I), and the card is not
    a CDAPH rate."""
    seul = build_situation(_foyer(_adulte(40_000, carte=True)), 2024)
    foyer = seul["foyers_fiscaux"]["ff_0"]
    assert foyer["caseP"] == {"2022": True, "2023": True, "2024": True}
    assert "caseF" not in foyer
    assert set(seul["individus"]["adulte_0"]) == {"salaire_de_base", "date_naissance"}
    conjoint = build_situation(_foyer(_adulte(40_000), _adulte(20_000, carte=True)), 2024)
    assert "caseP" not in conjoint["foyers_fiscaux"]["ff_0"]
    assert conjoint["foyers_fiscaux"]["ff_0"]["caseF"] == {
        "2022": True, "2023": True, "2024": True}
    une_annee = build_situation(_foyer(_adulte(40_000, carte=True)), 2024,
                                historique_revenus=False)
    assert une_annee["foyers_fiscaux"]["ff_0"]["caseP"] == {"2024": True}
    sans = build_situation(_foyer(_adulte(40_000), _adulte(20_000)), 2024)
    assert not {"caseP", "caseF"} & set(sans["foyers_fiscaux"]["ff_0"])


def test_a_card_holder_alone_gets_half_a_part_more() -> None:
    """CGI art. 195, 1, d bis: the income of a person alone without a dependent child who
    holds the card « mobilité inclusion » marked « invalidité » is divided by 1.5. By hand
    at 40 000 EUR: 29 523.60 of net income, above the abatement's ceiling; 1.5 x 0.11 x
    (19 682.40 - 11 497) = 1 350.59 before the décote, the half-part's advantage (671.97)
    under its cap; a décote of 889 - 45.25 % x 1 350.59 = 278 leaves 1 073 EUR, against
    2 023 without the card. Both tiers compute the income tax, and agree on every row they
    share."""
    sans = _rows(_foyer(_adulte(40_000)))
    light = _rows(_foyer(_adulte(40_000, carte=True)))
    full = _rows(_foyer(_adulte(40_000, carte=True)), "full")
    assert (sans["parts_fiscales"], light["parts_fiscales"]) == (1.0, 1.5)
    assert sans["ir"] == pytest.approx(2_023, abs=0.5)
    assert light["ir"] == pytest.approx(1_073, abs=0.5)
    assert light["revenu_fiscal_reference"] == pytest.approx(
        sans["revenu_fiscal_reference"], abs=0.01)
    for row in LIGHT_ROWS:
        assert full[row.key] == light[row.key], row.key


@pytest.mark.parametrize("titulaire", [0, 1])
def test_a_couple_gets_half_a_part_whichever_spouse_holds_the_card(titulaire: int) -> None:
    """Art. 195, 3: the quotient « est augmenté d'une demi-part pour les contribuables mariés,
    lorsque l'un ou l'autre des conjoints remplit l'une des conditions fixées aux c, d et
    d bis du 1 », case P for the first, case F for the second; and by a whole part « lorsque
    chacun des conjoints remplit l'une des conditions » (art. 195, 4). By hand at 40 000 and
    20 000 EUR, 44 285.40 of net income: two parts pay 2 342.05 before a décote of 410, so
    1 932 EUR; 2.5 parts 1 709.72 before 696, so 1 014; three parts 1 077.38 before 982,
    so 95."""
    adultes = [_adulte(40_000), _adulte(20_000)]
    adultes[titulaire] = {**adultes[titulaire], "carte_invalidite": True}
    une = _rows(_foyer(*adultes))
    deux = _rows(_foyer(_adulte(40_000, carte=True), _adulte(20_000, carte=True)))
    aucune = _rows(_foyer(_adulte(40_000), _adulte(20_000)))
    assert (aucune["parts_fiscales"], une["parts_fiscales"], deux["parts_fiscales"]) == (
        2.0, 2.5, 3.0)
    assert aucune["ir"] == pytest.approx(1_932, abs=0.5)
    assert une["ir"] == pytest.approx(1_014, abs=0.5)
    assert deux["ir"] == pytest.approx(95, abs=0.5)


def test_the_card_abates_a_low_net_income_at_any_age() -> None:
    """CGI art. 157 bis: the taxpayer « remplissant l'une des conditions d'invalidité
    mentionnées à l'article 195 » deducts from the net income 2 796 EUR « si ce revenu
    n'excède pas 17 510 € », 1 398 « si ce revenu est compris entre 17 510 € et 28 170 € »
    (2024 incomes), whatever the age. Born in 1980, at 20 000 EUR of salary, 14 761.80 of
    net income becomes an RFR of 11 965.80, and no tax is due either way. At 38 000 EUR,
    28 047.43 is abated to 26 649.43; 1.5 parts pay 1 034.43 before a décote of 421, so
    613 EUR, against 1 756 without the card."""
    for salaire, abattement in ((20_000, 2_796), (38_000, 1_398)):
        sans = _rows(_foyer(_adulte(salaire)))
        avec = _rows(_foyer(_adulte(salaire, carte=True)))
        assert avec["revenu_fiscal_reference"] == pytest.approx(
            sans["revenu_fiscal_reference"] - abattement, abs=0.01), salaire
        assert sans["parts_fiscales"] == 1.0 and avec["parts_fiscales"] == 1.5
    assert _rows(_foyer(_adulte(38_000, carte=True)))["ir"] == pytest.approx(613, abs=0.5)
    assert _rows(_foyer(_adulte(38_000)))["ir"] == pytest.approx(1_756, abs=0.5)


def test_the_card_holders_half_part_is_capped_then_given_its_complement() -> None:
    """Art. 197, I, 2: the reduction the quotient brings « ne peut excéder 1 791 € par
    demi-part », and whoever has a half-part under the d bis of art. 195, 1 « ont droit à
    une réduction d'impôt égale à 1 785 € pour chacune de ces demi-parts lorsque la
    réduction de leur cotisation d'impôt est plafonnée en application du premier alinéa »,
    which « ne peut toutefois excéder l'augmentation de la cotisation d'impôt résultant du
    plafonnement ». At 200 000 EUR, 151 123.75 of net income, the half-part would be worth
    45 905.69 - 37 878.16 = 8 027.53 EUR uncapped; it is worth 1 791 + 1 785 = 3 576."""
    sans = _rows(_foyer(_adulte(200_000)))
    avec = _rows(_foyer(_adulte(200_000, carte=True)))
    assert sans["ir_avant_reductions"] == pytest.approx(45_905.69, abs=0.01)
    assert avec["ir_avant_reductions"] == pytest.approx(45_905.69 - 1_791 - 1_785, abs=0.01)
    assert avec["ir"] == pytest.approx(42_330, abs=0.5)


def test_the_abatement_is_doubled_when_both_spouses_qualify() -> None:
    """Art. 157 bis: « Dans le cas de personnes mariées soumises à une imposition commune, la
    déduction prévue aux deuxième et troisième alinéas est doublée si les deux époux
    remplissent les conditions d'âge ou d'invalidité. » openfisca counted the spouses with
    numpy booleans, whose sum is a logical or: one abatement however many qualified. Two
    card holders at 10 000 EUR each, 14 761.79 of net income, deduct 2 x 2 796; one card,
    once. Two pensioners over 65 at 8 000 EUR, 14 400 of net income, deduct 2 x 2 796; a
    pensioner over 65 beside a card holder, 10 800 + 8 857.08, deduct 2 x 1 398. Never more
    than the net income: two pensioners at 2 000 EUR, 3 100 of net income after the minimum
    deduction of 450 each, deduct 3 100. No couple's income tax moves, since a couple under
    28 170 EUR of net income owes none: its RFR does."""
    def rfr(*adultes: dict[str, Any]) -> float:
        return _rows(_foyer(*adultes))["revenu_fiscal_reference"]

    aucune = rfr(_adulte(10_000), _adulte(10_000, 1982))
    assert rfr(_adulte(10_000, carte=True), _adulte(10_000, 1982)) == pytest.approx(
        aucune - 2_796, abs=0.01)
    assert rfr(_adulte(10_000, carte=True), _adulte(10_000, 1982, carte=True)) == (
        pytest.approx(aucune - 2 * 2_796, abs=0.01))
    assert rfr(_adulte(0, 1950, pension_annuelle=8_000),
               _adulte(0, 1952, pension_annuelle=8_000)) == pytest.approx(
        14_400 - 2 * 2_796, abs=0.01)
    assert rfr(_adulte(0, 1955, pension_annuelle=12_000),
               _adulte(12_000, 1970, carte=True)) == pytest.approx(
        10_800 + 8_857.08 - 2 * 1_398, abs=0.01)
    modeste = _foyer(_adulte(0, 1950, pension_annuelle=2_000),
                     _adulte(0, 1952, pension_annuelle=2_000))
    assert _foyer_variable(modeste, "rng", "2024") == pytest.approx(3_100, abs=0.01)
    assert _foyer_variable(modeste, "abat_spe", "2024") == pytest.approx(3_100, abs=0.01)


def test_the_engine_alone_abates_a_couple_once() -> None:
    """The kill test for the art. 157 bis correction of the income tax, on raw openfisca.
    Age alone shows the defect, so no card is needed: two pensioners over 65, 14 400 EUR of
    net income, deduct one abatement where the article doubles it. The day this fails,
    openfisca counts the spouses itself, and the correction must go."""
    from impots.engine.system import uncorrected_baseline

    couple = _foyer(_adulte(0, 1950, pension_annuelle=8_000),
                    _adulte(0, 1952, pension_annuelle=8_000))
    assert _foyer_variable(couple, "abat_spe", "2024", uncorrected_baseline()) == 2_796, (
        "openfisca now doubles the abatement of a couple: remove the correction rather than "
        "keep one that corrects nothing")


def test_the_benefits_deduct_the_abatement_doubled_for_two_invalid_spouses() -> None:
    """The housing aid deducts « L'abattement mentionné à l'article 157 bis du code général
    des impôts pour les personnes nées avant le 1er janvier 1931 et pour les personnes
    invalides » (CCH art. R. 822-4, II, 2°), the article that doubles it « si les deux époux
    remplissent les conditions d'âge ou d'invalidité ». openfisca's copy of it for the
    benefits, read on N-2, summed the same booleans. On 2022 incomes (2 620 EUR up to 16 410
    of net income, 1 310 up to 26 400):
    * two card holders at 10 000 EUR each, 14 761.79 of net income: 2 x 2 620;
    * a card holder beside a pensioner over 65 born after 1930: 1 310 once, since the aid
      deducts it for invalides and for those born before 1931 only, where the income tax of
      the same year, which reads age or invalidity, deducts it twice."""
    abattement = "abattements_speciaux_prestations_familiales"
    deux_cartes = _foyer(_adulte(10_000, carte=True), _adulte(10_000, 1982, carte=True))
    assert _foyer_variable(deux_cartes, abattement, "2022") == 2 * 2_620
    mixte = _foyer(_adulte(0, 1955, pension_annuelle=12_000), _adulte(12_000, 1970, carte=True))
    assert _foyer_variable(mixte, abattement, "2022") == 1_310
    assert _foyer_variable(mixte, "abat_spe", "2022") == 2 * 1_310


def test_the_engine_alone_takes_one_abatement_off_a_couple_s_benefit_resources() -> None:
    """The kill test for the art. 157 bis correction of the benefits' resources, on raw
    openfisca. Two pensioners born before 1931, at 8 000 EUR each, qualify twice and are
    deducted 2 620 EUR once. The day this fails, openfisca counts the spouses itself, and
    the correction must go."""
    from impots.engine.system import uncorrected_baseline

    couple = _foyer(_adulte(0, 1928, pension_annuelle=8_000),
                    _adulte(0, 1930, pension_annuelle=8_000))
    assert _foyer_variable(couple, "abattements_speciaux_prestations_familiales", "2022",
                           uncorrected_baseline()) == 2_620, (
        "openfisca now doubles the benefits' abatement: remove the correction rather than "
        "keep one that corrects nothing")


def test_the_card_asks_for_no_cdaph_rate() -> None:
    """The mention « invalidité » goes to an incapacity of at least 80 %, but also to whoever
    « a été classée dans la catégorie mentionnée au 3° de l'article L. 341-4 du code de la
    sécurité sociale » (CASF art. L. 241-3, I, 1°), and « à titre définitif » to applicants
    for and recipients of the APA in groups 1 or 2, « au vu de la seule décision
    d'attribution de l'allocation » (II). The wire format knows the CDAPH rate only, so it
    asks for none beside the card: a rate typed to satisfy it would open an AAH. Nor is a
    rate of 80 % a card, which is applied for apart."""
    sans_taux = _foyer(_adulte(0, 1940, carte=True, pension_annuelle=15_000))
    assert sans_taux.adults[0].handicap is None and sans_taux.adults[0].carte_invalidite
    taux_bas = _foyer(_adulte(20_000, carte=True, handicap={"taux_incapacite": 0.5}))
    assert taux_bas.adults[0].carte_invalidite is True
    taux_plein = _foyer(_adulte(20_000, handicap={"taux_incapacite": 0.8}))
    assert taux_plein.adults[0].carte_invalidite is False


def test_the_card_takes_the_abatement_off_the_resources_of_the_housing_aid() -> None:
    """CCH art. R. 822-4, II: « Sont déduits du décompte des ressources : […] 2° L'abattement
    mentionné à l'article 157 bis du code général des impôts pour les personnes nées avant le
    1er janvier 1931 et pour les personnes invalides. » The aid reads the resources of N-2,
    hence the card on every covered year. A renter at 15 000 EUR: the 2022 abatement, 2 620
    EUR, comes off resources rounded up to the hundred, 11 100 EUR becoming 8 500, and the
    aid rises from 1 319.13 to 2 292.33 EUR over 2024."""
    def simulation(carte: bool) -> Any:
        return _pinned(build_situation(_foyer(_adulte(15_000, carte=carte), logement=RENTING),
                                       2024))

    sans, avec = simulation(False), simulation(True)
    assert float(avec.calculate("abattements_speciaux_prestations_familiales", "2022")[0]) == (
        2_620)
    for month in ("2024-01", "2024-07"):
        ecart = (float(sans.calculate("aide_logement_base_ressources", month)[0])
                 - float(avec.calculate("aide_logement_base_ressources", month)[0]))
        assert ecart == pytest.approx(2_620, abs=100), month
    assert _rows(_foyer(_adulte(15_000), logement=RENTING), "full")["aide_logement"] == (
        pytest.approx(1_319.13, abs=0.05))
    assert _rows(_foyer(_adulte(15_000, carte=True), logement=RENTING), "full")[
        "aide_logement"] == pytest.approx(2_292.33, abs=0.05)


def test_the_card_reaches_the_csg_of_a_pension_through_the_rfr_and_parts_of_n_2() -> None:
    """The CSG of a pension takes its rate from the RFR of N-2, against thresholds raised for
    each half-part of N-2. Born in 1960, 18 000 EUR of pension: an RFR of 16 200 in 2022,
    above the tree's exemption threshold for one part (12 230), pays the median rate, 576
    EUR of CSG imposable, CRDS and CASA out of the disposable income. With the card, the
    2022 abatement (2 620) and the half-part both count: 13 580 under 12 230 + 3 265 for
    1.5 parts, so no levy at all. Either alone leaves the reduced rate."""
    def rows(carte: bool) -> dict[str, Any]:
        return _rows(_foyer(_adulte(0, 1960, carte=carte, pension_annuelle=18_000)), "full")

    sans, avec = rows(False), rows(True)
    assert sans["revenu_disponible"] == pytest.approx(18_000 - 576, abs=0.05)
    assert avec["revenu_disponible"] == pytest.approx(18_000, abs=0.05)
    carte = _foyer(_adulte(0, 1960, carte=True, pension_annuelle=18_000))
    assert _foyer_variable(carte, "rfr", "2022") == pytest.approx(16_200 - 2_620, abs=0.01)
    assert _foyer_variable(carte, "nbptr", "2022") == 1.5


def test_a_card_holders_aid_prices_the_same_whatever_is_computed_first() -> None:
    """The card is read on N-2 inside the housing aid, which the builder pins month by month
    (D-178). Through the registry, as the API computes it, and with `revenu_disponible` first,
    as the EMTR's bumped leg does, the figures agree."""
    situation = build_situation(_foyer(_adulte(15_000, carte=True), logement=RENTING), 2024)
    registry = extract(_pinned(situation), 2024, "full")
    first = _pinned(situation)
    disposable = float(first.calculate("revenu_disponible", "2024")[0])
    assert disposable == pytest.approx(registry["revenu_disponible"], abs=0.05)
    assert float(first.calculate_add("aide_logement", "2024").sum()) == pytest.approx(
        registry["aide_logement"], abs=0.05)


# --------------------------------------------------------------------------- #
# the ASS on the wire (docs/DECISIONS.md D-189)
# --------------------------------------------------------------------------- #
#: The ASS's daily amount, month by month in 2024: 18.17 EUR until March (décret n° 2023-301),
#: 19.01 from April (décret n° 2024-341). A month is paid as 30 days.
ASS_JOUR = {**dict.fromkeys(range(1, 4), 18.17), **dict.fromkeys(range(4, 13), 19.01)}
#: The full ASS over 2024: 3 x 545.10 + 9 x 570.30 EUR.
ASS_PLEINE_2024 = 6_768.00
#: The RSA of a person alone: 607.75 EUR a month until March 2024, 635.71 from April.
RSA_SEUL = {**dict.fromkeys(range(1, 4), 607.75), **dict.fromkeys(range(4, 13), 635.71)}
#: A spouse's gross unemployment benefit high enough to reduce a couple's ASS.
ARE_DU_CONJOINT = 24_000


def _fin_de_droits(naissance: int = 1975, *, conjoint: dict[str, Any] | None = None,
                   second: bool = False, logement: dict[str, Any] | None = None,
                   ass: bool = True, **revenus: Any) -> HouseholdInput:
    """An adult whose unemployment insurance rights are exhausted and who meets the ASS's
    work condition, and nothing else unless asked. `conjoint` adds a spouse, `second` puts
    the claimant second, as the famille's `conjoint`, and `ass=False` builds the same
    household without the declaration. Built when a test asks, like `_chomeur`."""
    claimant: dict[str, Any] = {"salaire_brut_annuel": 0, "annee_naissance": naissance,
                                **revenus}
    if ass:
        claimant["fin_de_droits_ass"] = True
    adults = [claimant]
    if conjoint is not None:
        spouse = {"salaire_brut_annuel": 0, "annee_naissance": 1975, **conjoint}
        adults = [spouse, claimant] if second else [claimant, spouse]
    household: dict[str, Any] = {"adults": adults, "couple_marie_ou_pacse": len(adults) == 2}
    if logement is not None:
        household["logement"] = logement
    return HouseholdInput.model_validate(household)


#: The households the ASS tests price, each computed once.
ASS_CASES: dict[str, Any] = {
    "seul": lambda: _fin_de_droits(),
    "locataire": lambda: _fin_de_droits(logement=RENTING),
    "locataire_sans_ass": lambda: _fin_de_droits(logement=RENTING, ass=False),
    "couple": lambda: _fin_de_droits(conjoint={"salaire_brut_annuel": 24_000}),
    "couple_sans_ass": lambda: _fin_de_droits(conjoint={"salaire_brut_annuel": 24_000},
                                              ass=False),
    "conjoint_au_chomage": lambda: _fin_de_droits(
        conjoint={"chomage_brut_annuel": ARE_DU_CONJOINT}),
    "allocataire_second": lambda: _fin_de_droits(
        conjoint={"chomage_brut_annuel": ARE_DU_CONJOINT}, second=True),
    "deux_allocataires": lambda: _fin_de_droits(conjoint={"fin_de_droits_ass": True}),
    "aah": lambda: _fin_de_droits(handicap={"taux_incapacite": 0.8}),
    # Since D-192, for the income tax: a spouse's declared pension, a spouse's salary high
    # enough to leave a small ASS, and the claimant holding the invalidity card.
    "pension_du_conjoint": lambda: _fin_de_droits(
        conjoint={"annee_naissance": 1960, "pension_annuelle": 15_000}),
    "conjoint_a_28000": lambda: _fin_de_droits(conjoint={"salaire_brut_annuel": 28_000}),
    "conjoint_a_28000_sans_ass": lambda: _fin_de_droits(
        conjoint={"salaire_brut_annuel": 28_000}, ass=False),
    "carte": lambda: _fin_de_droits(carte_invalidite=True),
}


@functools.cache
def _ass_rows(name: str) -> dict[str, Any]:
    """The full tier of one of `ASS_CASES`, through `compute`, as the API prices it."""
    return compute(ASS_CASES[name](), 2024, tier="full").baseline


@functools.cache
def _ass_both_orders(name: str) -> tuple[Any, dict[str, Any], Any]:
    """One of `ASS_CASES` on two simulations built as `compute` builds the full tier: read
    through the registry, as the API reads it, and with `revenu_disponible` computed first,
    as the EMTR's bumped leg computes it."""
    situation = build_situation(ASS_CASES[name](), 2024)
    registry = _pinned(situation)
    rows = extract(registry, 2024, "full")
    first = _pinned(situation)
    first.calculate("revenu_disponible", "2024")
    return registry, rows, first


def _mois(month: int) -> str:
    """Month `month` of 2024, counting back into 2023 from 0 (December) down."""
    return f"2024-{month:02d}" if month >= 1 else f"2023-{month + 12:02d}"


def test_the_ass_inputs_are_written_on_every_covered_month() -> None:
    """« En fin de droits, condition d'activité remplie » is written as openfisca reads it, on
    every month from N-2 to N like the salary: `ass_precondition_remplie`, the five years of
    salaried work in the ten (C. trav. art. R. 5423-1, 1°), and a job seeker's `activite`
    (art. L. 5423-1, and R. 5423-1, 2°). An adult who does not declare it carries neither."""
    adult = build_situation(_fin_de_droits(), 2024)["individus"]["adulte_0"]
    assert list(adult["ass_precondition_remplie"].values()) == [True] * 36
    assert list(adult["activite"].values()) == ["chomeur"] * 36
    other = build_situation(SINGLE, 2024)["individus"]["adulte_0"]
    assert "ass_precondition_remplie" not in other
    assert "activite" not in other


def test_a_claimant_without_resources_draws_the_full_ass() -> None:
    """By hand: 30 days at 18.17 EUR until March and at 19.01 from April, 6 768 EUR over 2024
    (décrets n° 2023-301 and n° 2024-341). Alone and without resources, the claimant is far
    under the ceiling of 70 daily amounts (C. trav. art. R. 5423-1, 3°)."""
    assert sum(30 * jour for jour in ASS_JOUR.values()) == pytest.approx(ASS_PLEINE_2024)
    assert _ass_rows("seul")["ass"] == pytest.approx(ASS_PLEINE_2024, abs=0.05)


def test_the_rsa_counts_the_ass_and_tops_it_up() -> None:
    """The RSA counts the ASS of its three months of reference and makes up the difference:
    607.75 - 545.10 = 62.65 EUR in January, 635.71 - 570.30 = 65.41 from July, and in
    between the quarter still holds ASS from before its revaluation. 827.04 EUR of RSA, the
    prime de Noël of 152.45, and 7 747.49 of disposable income: without a dwelling, no
    housing aid."""
    ass = {month: 30 * jour for month, jour in ASS_JOUR.items()}
    ass.update({month - 12: 30 * 18.17 for month in (10, 11, 12)})  # October to December 2023
    rsa = sum(RSA_SEUL[month] - sum(ass[month - back] for back in (1, 2, 3)) / 3
              for month in range(1, 13))
    rows = _ass_rows("seul")
    assert rsa == pytest.approx(827.04, abs=0.005)
    assert rows["rsa"] == pytest.approx(rsa, abs=0.05)
    assert rows["revenu_disponible"] == pytest.approx(ASS_PLEINE_2024 + rsa + 152.45, abs=0.05)


def test_in_a_couple_the_ass_takes_the_spouse_s_declared_salary() -> None:
    """C. trav. art. R. 5423-1, 3°, R. 5423-2 and R. 5423-6: in a couple the ASS tops the
    resources up to 110 daily amounts, the spouse's salary counted « telles qu'elles doivent
    être déclarées à l'administration fiscale pour le calcul de l'impôt sur le revenu avant
    déduction des divers abattements », a twelfth of the twelve months before. On 24 000 EUR
    gross, 19 682.16 EUR taxable, 1 640.18 a month: 1 998.70 - 1 640.18 = 358.52 EUR until
    March, 2 091.10 - 1 640.18 = 450.92 from April, 5 133.84 over 2024. The salary of 2023,
    which the first months read, is the same."""
    rows = _ass_both_orders("couple")[1]
    mensuel = rows["salaire_imposable"] / 12
    attendu = sum(min(30 * jour, 110 * jour - mensuel) for jour in ASS_JOUR.values())
    assert attendu == pytest.approx(5_133.84, abs=0.05)
    assert rows["ass"] == pytest.approx(attendu, abs=0.05)


def test_the_prime_d_activite_counts_the_ass() -> None:
    """The prime d'activité counts « Les revenus de remplacement des revenus professionnels »
    (CSS art. L. 842-4, 2°), which the allocations de solidarité are (C. trav. art.
    L. 5421-2). Month by month, the couple on 24 000 EUR loses the mean ASS of the three
    months before: 4 949.04 EUR of prime d'activité over 2024."""
    simulation, rows, _ = _ass_both_orders("couple")
    ass = {month: float(simulation.calculate("ass", _mois(month)).sum())
           for month in range(-2, 12)}
    lost = sum(sum(ass[month - back] for back in (1, 2, 3)) / 3 for month in range(1, 13))
    assert lost == pytest.approx(4_949.04, abs=0.05)
    assert _ass_rows("couple_sans_ass")["ppa"] - rows["ppa"] == pytest.approx(lost, abs=0.05)


def test_the_housing_aid_leaves_the_ass_out() -> None:
    """CCH art. R. 822-15: neither the professional income nor the unemployment allowances of
    a claimant who « perçoit l'allocation de solidarité spécifique » count in the housing
    aid. Renting at 500 EUR in zone 2, the aid is the one without the ASS, 3 532.77 EUR.
    Beside it the RSA takes a forfait logement of 12 %, 76.29 EUR, and tops the ASS up in
    April only: 635.71 - 545.10 - 76.29 = 14.32 EUR. In May the quarter leaves 5.92, under
    the 6 EUR below which the tree pays no RSA."""
    with_ass = _ass_both_orders("locataire")[1]
    without = _ass_rows("locataire_sans_ass")
    assert with_ass["ass"] == pytest.approx(ASS_PLEINE_2024, abs=0.05)
    assert with_ass["aide_logement"] == pytest.approx(3_532.77, abs=0.05)
    assert with_ass["aide_logement"] == pytest.approx(without["aide_logement"], abs=0.05)
    assert with_ass["rsa"] == pytest.approx(635.71 - 545.10 - 76.29, abs=0.05)


@pytest.mark.parametrize("name", ["locataire", "couple", "allocataire_second"])
def test_the_ass_prices_the_same_whatever_is_computed_first(name: str) -> None:
    """`ass_precondition_remplie` is one of `situations.MINIMA_INPUTS`, so the builder pins the
    benefit history even without a dwelling (D-178, D-179). Through the registry, as the API
    reads it, and with `revenu_disponible` first, as the EMTR's bumped leg computes it, the
    ASS, the minima beside it and the disposable income agree: for a renter, beside a
    spouse's salary, and beside a spouse's unemployment benefit read by the correction."""
    _, rows, first = _ass_both_orders(name)
    assert float(first.calculate("revenu_disponible", "2024")[0]) == pytest.approx(
        rows["revenu_disponible"], abs=0.05)
    for key in ("ass", "rsa", "ppa", "aide_logement"):
        assert float(first.calculate_add(key, "2024").sum()) == pytest.approx(
            rows[key], abs=0.05), key


def test_an_ass_claimant_s_emtr_prices_the_first_euro_as_the_cumul_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bumped leg adds 100 EUR of salary in N to a job seeker. openfisca keeps a job
    seeker's ASS whatever the salary beside it, which is what the cumul does for the first
    three months of a resumed activity (C. trav. art. R. 5425-2); the RSA takes the salary
    back. Without the job seeker's `activite`, openfisca's own count of those three months
    stopped the ASS from April, and the rate read 12.27. Both legs of the hand computation
    go through `compute`, the bumped one by perturbing the situation it builds."""
    from impots.engine import situations

    original = situations.build_situation
    bump = {"on": False}

    def bumped_on_demand(household, year, historique_revenus=True):
        situation = original(household, year, historique_revenus)
        return perturb_first_adult(situation, year, EMTR_STEP) if bump["on"] else situation

    monkeypatch.setattr(situations, "build_situation", bumped_on_demand)
    claimant = _fin_de_droits()
    result = compute(claimant, 2024, tier="full", emtr=True)
    bump["on"] = True
    bumped = compute(claimant, 2024, tier="full").baseline["revenu_disponible"]
    by_hand = 1.0 - (bumped - result.baseline["revenu_disponible"]) / EMTR_STEP
    assert result.emtr == pytest.approx(by_hand, abs=1e-3)
    assert 0.0 < result.emtr < 1.0


@pytest.mark.parametrize(("revenu", "article"), [("salaire_brut_annuel", r"R\. 5425-2"),
                                                 ("chomage_brut_annuel", r"L\. 5423-1")],
                         ids=["salaire", "chomage"])
def test_the_ass_is_refused_beside_an_income_of_its_own(revenu: str, article: str) -> None:
    """A salary on every month of three years is not the three months of cumul the law
    allows (C. trav. art. R. 5425-2), and openfisca would pay a job seeker's ASS beside it
    for good. Unemployment benefit and the ASS are never paid for the same months (art.
    L. 5423-1 and L. 5423-2), and openfisca would pay no ASS at all, without a word."""
    with pytest.raises(ValueError, match=article):
        _fin_de_droits(**{revenu: 6_000})


def test_from_the_year_of_62_the_ass_is_refused() -> None:
    """From the legal retirement age, 62 at the earliest (CSS art. D. 161-2-1-9), the ASS stops
    for whoever has the full-rate insurance duration, and at 67 for everyone (C. trav. art.
    L. 5421-4, 1° and 2°). The wire format does not carry the insurance duration. Born in
    1962, 62 in 2024: refused. Born in 1963: written like any claimant."""
    with pytest.raises(ValueError, match=r"L\. 5421-4"):
        build_situation(_fin_de_droits(naissance=1962), 2024)
    adult = build_situation(_fin_de_droits(naissance=1963), 2024)["individus"]["adulte_0"]
    assert list(adult["ass_precondition_remplie"].values()) == [True] * 36


def test_two_claimants_are_priced_alone_and_refused_beside_a_pension() -> None:
    """Each claimant's resources count the other's ASS (C. trav. art. R. 5423-2), which
    openfisca leaves out. Without other resources, two full allocations stay under the
    couple's 110 daily amounts, and the answer is the law's: 13 536 EUR. Beside a pension the
    two could cross it, and the household is refused."""
    assert _ass_rows("deux_allocataires")["ass"] == pytest.approx(2 * ASS_PLEINE_2024, abs=0.05)
    with pytest.raises(ValueError, match=r"R\. 5423-2"):
        _fin_de_droits(pension_annuelle=6_000, conjoint={"fin_de_droits_ass": True})


def test_the_ass_is_not_paid_beside_the_aah() -> None:
    """C. trav. art. L. 5423-7: the ASS « ne peut être cumulée avec l'allocation aux adultes
    handicapés […] dès lors qu'un versement a été effectué au titre de cette dernière
    allocation ». At 80 % and without resources, the AAH alone, 12 058.56 EUR."""
    rows = _ass_rows("aah")
    assert rows["aah"] == pytest.approx(AAH_2024, abs=0.05)
    assert rows["ass"] == 0.0


def test_the_ass_does_not_depend_on_which_adult_claims_it() -> None:
    """C. trav. art. R. 5423-2 counts « les autres ressources de l'intéressé et, le cas
    échéant, de son conjoint ». openfisca adds the unemployment benefit to the famille's
    second parent only: with the claimant second, the first one's 24 000 EUR of benefit
    vanished from the ASS's resources, and the ASS was paid in full, 6 768 EUR instead of
    1 263.50."""
    first = _ass_rows("conjoint_au_chomage")
    second = _ass_both_orders("allocataire_second")[1]
    assert first["ass"] == pytest.approx(1_263.50, abs=0.05)
    assert second["ass"] == pytest.approx(first["ass"], abs=0.05)
    assert second["revenu_disponible"] == pytest.approx(first["revenu_disponible"], abs=0.05)


def test_the_engine_alone_ignores_the_unemployment_benefit_of_a_spouse_heading_the_famille(
) -> None:
    """The kill test for the ASS correction: raw openfisca, the claimant second, the ASS's
    inputs written by hand. The first adult's 24 000 EUR of unemployment benefit is not in
    the resources, and June's ASS is the full 30 x 19.01 EUR. The day this fails, openfisca
    counts it itself, and `engine.corrections` must drop its own."""
    from impots.engine.system import uncorrected_baseline

    situation = build_situation(_fin_de_droits(
        conjoint={"chomage_brut_annuel": ARE_DU_CONJOINT}, second=True, ass=False), 2024)
    covered = [f"{year}-{month:02d}" for year in (2022, 2023, 2024) for month in range(1, 13)]
    situation["individus"]["adulte_1"]["ass_precondition_remplie"] = dict.fromkeys(covered, True)
    situation["individus"]["adulte_1"]["activite"] = dict.fromkeys(covered, "chomeur")
    raw = SimulationBuilder().build_from_entities(uncorrected_baseline(), situation)
    assert float(raw.calculate("ass", "2024-06")[1]) == pytest.approx(30 * 19.01, abs=0.01), (
        "openfisca now counts the unemployment benefit of a claimant's spouse who heads the "
        "famille: remove the correction rather than keep one that corrects nothing")


def _benefit_until_2023(situation: dict[str, Any], adult: str, monthly: float) -> dict[str, Any]:
    """Unemployment benefit on every month of 2022 and 2023, and none in 2024: the end of an
    insurance right, which the wire format, writing the same incomes on every covered year,
    cannot say. Written by hand, as the D-179 tests write what no field carries."""
    months = [f"{year}-{month:02d}" for year in (2022, 2023) for month in range(1, 13)]
    situation["individus"][adult]["chomage_brut"] = dict.fromkeys(months, monthly)
    return situation


def test_a_claimant_s_own_past_benefit_is_no_resource() -> None:
    """C. trav. art. R. 5423-3, 1°: the ASS's resources leave out « L'allocation d'assurance
    précédemment perçue par l'intéressé ». Alone, with 2 000 EUR a month of benefit until
    December 2023, the claimant draws the full ASS from January, 545.10 EUR, though the
    benefit of the twelve months before had not stopped by the month before. openfisca never
    counts the first parent's benefit; the correction adds it only for a first parent who
    does not claim the ASS, and must not add it here."""
    situation = _benefit_until_2023(build_situation(_fin_de_droits(), 2024), "adulte_0", 2_000.0)
    simulation = _pinned(situation)
    assert float(simulation.calculate("ass", "2024-01")[0]) == pytest.approx(
        30 * 18.17, abs=0.01)


def test_a_spouse_s_benefit_that_has_stopped_is_no_resource() -> None:
    """C. trav. art. R. 5423-5: resources « dont la perception est interrompue de manière
    certaine » leave the base, as in openfisca's own term for the second parent, which the
    correction reads on the first. The claimant second, the first adult's 3 000 EUR a month
    of benefit ended in December 2023: in January the benefit of the twelve months before
    reduces the ASS, from February it no longer does, and June's is the full 570.30 EUR."""
    situation = _benefit_until_2023(
        build_situation(_fin_de_droits(conjoint={}, second=True), 2024), "adulte_0", 3_000.0)
    simulation = _pinned(situation)
    assert float(simulation.calculate("ass", "2024-01")[1]) < 30 * 18.17 - 100
    assert float(simulation.calculate("ass", "2024-06")[1]) == pytest.approx(
        30 * 19.01, abs=0.01)


# --------------------------------------------------------------------------- #
# the invalidity pension and the ASI (docs/DECISIONS.md D-190)
# --------------------------------------------------------------------------- #
#: The ASI's resource ceilings, a year, for a person alone and for a couple: from April 2023,
#: then from April 2024 (Cnav circulars 2023-09 and 2024-13). Since April 2020 the ASI is the
#: ceiling less the resources (CSS art. L. 815-24-1).
ASI_PLAFOND_SEUL = (10_320.07, 10_794.79)
ASI_PLAFOND_COUPLE = (18_060.13, 18_890.89)
#: The minimum invalidity pension of an employee (CSS art. L. 341-5), a month, from January
#: 2024 (Cnav circular 2024-13): what art. D. 815-19 takes off the single ceiling to cap the
#: ASI of a beneficiary whose spouse draws neither the ASI nor the ASPA.
PENSION_INVALIDITE_MINIMUM_2024 = 328.07


def _asi_by_hand(ceilings: tuple[float, float], resources: float) -> float:
    """The ceiling less the resources, a month at a time: three months at the 2023 ceiling,
    nine at the 2024 one."""
    before, after = ceilings
    return (3 * max(0.0, (before - resources) / 12)
            + 9 * max(0.0, (after - resources) / 12))


def _invalide(pension: float, *, naissance: int = 1980, logement: dict[str, Any] | None = None,
              **adult: Any) -> HouseholdInput:
    """One adult with an invalidity pension of the social security, as declared, and nothing
    else unless asked. Built when a test asks, like `_chomeur`."""
    household: dict[str, Any] = {"adults": [
        {"salaire_brut_annuel": 0, "annee_naissance": naissance,
         "pension_invalidite_annuelle": pension, **adult}]}
    if logement is not None:
        household["logement"] = logement
    return HouseholdInput.model_validate(household)


def _couple_invalide(pension: float, conjoint: float) -> HouseholdInput:
    """A married couple below 62: an invalidity pension, and the spouse's, or nothing at all
    when `conjoint` is zero."""
    return HouseholdInput.model_validate({"adults": [
        {"salaire_brut_annuel": 0, "annee_naissance": 1980, "pension_invalidite_annuelle": pension},
        {"salaire_brut_annuel": 0, "annee_naissance": 1982,
         "pension_invalidite_annuelle": conjoint}],
        "couple_marie_ou_pacse": True})


@functools.cache
def _priced(pension: float, naissance: int = 1980, retraite: bool = False) -> dict[str, Any]:
    """The full tier of one adult with that pension and nothing else, computed once for the
    tests that read it. `retraite` declares the same amount as a retirement pension (box
    1AS) instead of an invalidity one (box 1AZ)."""
    field = "pension_annuelle" if retraite else "pension_invalidite_annuelle"
    household = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": naissance, field: pension}]})
    return compute(household, 2024, tier="full").baseline


def test_an_invalidity_pension_is_written_on_every_covered_month() -> None:
    """Onto `pensions_invalidite`, box 1AZ, a twelfth a month on N-2 to N, like the salary: the
    RFR of N-2 sets the rate of its levies, and the ASI reads the three months before. With it,
    `inapte_travail`: at 62 the pension gives way to a retirement pension, and « A cet âge, les
    intéressés sont réputés inaptes au travail » (circular Cnav 2023-25). openfisca reads that
    flag for the ASPA's anticipated age, from 62, and for the housing aid's dependent adults,
    which no adult of the wire format is. Never openfisca's generic `handicap` flag (D-184), nor
    the retirement boxes."""
    adult = build_situation(_invalide(6_000), 2024)["individus"]["adulte_0"]
    assert list(adult["pensions_invalidite"].values()) == [pytest.approx(500.0)] * 36
    assert list(adult["inapte_travail"].values()) == [True] * 36
    for name in ("handicap", "retraite_brute", "retraite_imposable"):
        assert name not in adult, name
    salaried = build_situation(SINGLE, 2024)["individus"]["adulte_0"]
    assert "pensions_invalidite" not in salaried
    assert "inapte_travail" not in salaried


def test_a_small_invalidity_pension_is_topped_up_by_the_asi() -> None:
    """CSS art. L. 815-24-1: the ASI is « la différence entre le plafond applicable à la
    situation du ou des allocataires et le total des ressources ». 6 000 EUR alone: 360.01 EUR a
    month to March, 399.57 from April, 4 676.11 over 2024. The RFR of N-2, 5 400 EUR, is under
    the exemption threshold, so no levy, and the disposable income is the pension and the ASI."""
    rows = _priced(6_000)
    assert rows["pension_invalidite"] == pytest.approx(6_000, abs=0.5)
    assert rows["asi"] == pytest.approx(_asi_by_hand(ASI_PLAFOND_SEUL, 6_000), abs=0.05)
    assert rows["aah"] == 0.0
    assert rows["rsa"] == 0.0
    assert rows["ir"] == 0.0
    assert rows["revenu_disponible"] == pytest.approx(6_000 + rows["asi"], abs=0.05)


#: What is left to take off a DECLARED pension, already net of its deductible CSG, by the band
#: its RFR of N-2 falls in, as openfisca's tree splits the CSG of pensions: at the reduced rate
#: (3.8 %) the whole CSG is deductible and only the CRDS (0.5 %) is left; at the intermediate
#: (6.6 %) and full (8.3 %) rates, the CSG imposable (2.4 %), the CRDS and the CASA (0.3 %).
#: CSS art. L. 136-8, II: « Sont assujetties à la contribution au taux de 8,3 % les pensions de
#: retraite, et les pensions d'invalidité »; art. L. 137-41: the CASA is « assise sur les
#: avantages de retraite et d'invalidité ».
LEVIES_BY_BAND = [(15_000, 0.005), (20_000, 0.032), (30_000, 0.032)]


@pytest.mark.parametrize(("pension", "rate"), LEVIES_BY_BAND,
                         ids=["reduit", "intermediaire", "plein"])
def test_an_invalidity_pension_is_levied_as_the_law_says(pension: float, rate: float) -> None:
    """By hand: RFR of N-2 of 13 500, 18 000 and 27 000 EUR, in the reduced, intermediate and
    full bands of 2024 (above 12 230, 15 988 and 24 813 EUR for one part). openfisca levied
    nothing on an invalidity pension, and the disposable income kept the whole declared amount:
    15 000, 19 850 and 28 412 EUR instead of 14 925, 19 210 and 27 452. Above the ASI's ceiling,
    no ASI."""
    rows = _priced(pension)
    assert rows["asi"] == 0.0
    assert rows["revenu_fiscal_reference"] == pytest.approx(0.9 * pension, abs=0.5)
    assert rows["revenu_disponible"] == pytest.approx(
        pension * (1 - rate) - rows["ir"], abs=0.5)


def test_an_invalidity_pension_is_taxed_and_levied_like_a_retirement_pension() -> None:
    """Box 1AZ joins box 1AS in the pensions' 10 % abatement, and the CSG, the CRDS and the CASA
    treat the two pensions alike: 30 000 EUR declared either way, at 44, pay the same 1 588 EUR
    of income tax and leave the same disposable income. The invalidity pension is not a
    retirement pension for anything else: its row is its own."""
    invalidite, retraite = _priced(30_000), _priced(30_000, retraite=True)
    for key in ("ir", "revenu_fiscal_reference", "revenu_disponible"):
        assert invalidite[key] == pytest.approx(retraite[key], abs=0.5), key
    assert invalidite["pension_invalidite"] == pytest.approx(30_000, abs=0.5)
    assert invalidite["retraite_imposable"] == 0.0


def test_the_engine_alone_levies_nothing_on_an_invalidity_pension() -> None:
    """The kill test for the levies correction. openfisca's pension levies read the retirement
    pension only, and its net pensions add `pensions_invalidite` whole, in the full-rate band
    as below the exemption threshold. The day this fails, openfisca levies the invalidity
    pension itself, and the correction must go."""
    from impots.engine import situations
    from impots.engine.system import uncorrected_baseline

    situation = build_situation(_invalide(30_000), 2024)
    raw = SimulationBuilder().build_from_entities(uncorrected_baseline(), situation)
    situations.pin_rfr_n_2(raw, 2024)
    assert float(raw.calculate("rfr", "2022")[0]) == pytest.approx(27_000, abs=0.5)
    assert float(raw.calculate("pensions_nettes", "2024")[0]) == pytest.approx(30_000, abs=0.01), (
        "openfisca now levies the invalidity pension: remove the correction rather than keep "
        "one that levies it twice")


def test_an_aah_tops_up_an_invalidity_pension_and_its_asi() -> None:
    """CSS art. L. 821-1: below the AAH amount, the AAH « s'ajoute à la prestation sans que le
    total des deux avantages puisse excéder le montant de l'allocation aux adultes
    handicapés ». openfisca tops up the pension and the ASI of the month BEFORE: in April it
    reads March's ASI, under the old ceiling, so the year ends 39.56 EUR above the AAH amount.
    It cannot read the month's own ASI, whose resources read the ASS, which reads the AAH of
    the month: the lag is openfisca's, measured and stated in D-190. The MVA stays, the AAH
    being paid « en complément d'un avantage de vieillesse ou d'invalidité » (art. L. 821-1-2,
    2°, correction 2)."""
    rows = compute(_invalide(6_000, handicap={"taux_incapacite": 0.8}, logement=RENTING), 2024,
                   tier="full").baseline
    asi = _asi_by_hand(ASI_PLAFOND_SEUL, 6_000)
    april = (ASI_PLAFOND_SEUL[1] - ASI_PLAFOND_SEUL[0]) / 12
    assert rows["asi"] == pytest.approx(asi, abs=0.05)
    assert rows["aah"] + 6_000 + asi == pytest.approx(AAH_2024 + april, abs=0.05)
    assert rows["mva"] == pytest.approx(MVA_2024, abs=0.05)


@pytest.mark.parametrize("pension", [6_000, 1_200], ids=["6 000 chacun", "1 200 chacun"])
def test_two_invalidity_pensioners_share_the_couple_ceiling_less_the_couple_s_resources(
    pension: float,
) -> None:
    """« Le montant de la ou des allocations est égal à la différence entre le plafond
    applicable à la situation du ou des allocataires et le total des ressources » of the
    couple (CSS art. L. 815-24-1), « servi par moitié à chacun des deux allocataires
    concernés » (art. D. 815-19, 2° a). Each on 6 000 EUR: 6 683.20 EUR over 2024, half each,
    and the couple ends at its ceiling, 18 683.20 EUR. Each on 1 200 EUR, a pension low enough
    for each half, 687.12 EUR a month from April, to pass what a lone beneficiary may draw
    (571.50): the 2° a) has no such cap, and two beneficiaries keep their halves."""
    from impots.engine import situations

    simulation = _pinned(situations.build_situation(_couple_invalide(pension, pension), 2024))
    rows = extract(simulation, 2024, "full")
    asi = _asi_by_hand(ASI_PLAFOND_COUPLE, 2 * pension)
    assert rows["asi"] == pytest.approx(asi, abs=0.05)
    each = simulation.calculate_add("asi", "2024")
    assert list(each) == [pytest.approx(asi / 2, abs=0.05)] * 2
    assert rows["revenu_disponible"] == pytest.approx(2 * pension + asi, abs=0.05)


def test_a_lone_beneficiary_in_a_couple_draws_the_single_ceiling_less_the_minimum_pension(
) -> None:
    """When the spouse draws neither the ASI nor the ASPA, « le montant de l'allocation servie
    ne peut excéder le montant du plafond mentionné au 1° auquel est soustrait le montant
    minimum de la pension d'invalidité mentionné à l'article L. 341-5 » (CSS art. D. 815-19, 2°
    b). On 6 000 EUR beside a spouse without income: 531.94 EUR a month to March, 571.50 from
    April (571.49 in Cnav circular 2024-13, which rounds the ceiling to the cent first), 6 739.27
    over 2024. openfisca paid the couple ceiling less the resources, 1 074.24 EUR a month from
    April and 12 683.20 over the year, the ASI of two."""
    rows = compute(_couple_invalide(6_000, 0), 2024, tier="full").baseline
    cap = (3 * (ASI_PLAFOND_SEUL[0] / 12 - PENSION_INVALIDITE_MINIMUM_2024)
           + 9 * (ASI_PLAFOND_SEUL[1] / 12 - PENSION_INVALIDITE_MINIMUM_2024))
    assert rows["asi"] == pytest.approx(cap, abs=0.05)
    assert rows["rsa"] == 0.0
    assert rows["revenu_disponible"] == pytest.approx(6_000 + cap, abs=0.05)


def test_the_engine_alone_pays_a_lone_beneficiary_in_a_couple_the_couple_ceiling() -> None:
    """The kill test for the ASI's cap: raw openfisca pays the beneficiary the couple ceiling
    less the couple's resources, 1 574.24 - 500 EUR in June 2024, above the 571.50 that art.
    D. 815-19 allows. The day this fails, openfisca caps it itself, and the correction must
    go."""
    from impots.engine.system import uncorrected_baseline

    situation = build_situation(_couple_invalide(6_000, 0), 2024)
    raw = SimulationBuilder().build_from_entities(uncorrected_baseline(), situation)
    paid = raw.calculate("asi", "2024-06")
    assert float(paid[0]) == pytest.approx(ASI_PLAFOND_COUPLE[1] / 12 - 500, abs=0.01), (
        "openfisca now caps the ASI of a lone beneficiary in a couple: remove the correction")
    assert float(paid[1]) == 0.0


@pytest.mark.parametrize(("naissance", "asi", "aspa"), [
    (1963, _asi_by_hand(ASI_PLAFOND_SEUL, 6_000), 0.0),
    (1962, 0.0, ASPA_SEULE_2024 - 6_000),
    (1959, 0.0, ASPA_SEULE_2024 - 6_000),
], ids=["61 ans", "62 ans", "65 ans"])
def test_from_62_an_invalidity_pensioner_draws_the_aspa_and_not_the_asi(
    naissance: int, asi: float, aspa: float,
) -> None:
    """The ASI goes to those « sans remplir la condition d'âge pour bénéficier de l'allocation
    aux personnes âgées » (CSS art. L. 815-24), and for an invalidity pensioner that age is 62:
    « A cet âge, les intéressés sont réputés inaptes au travail [...] et ils peuvent accéder à
    l'allocation de solidarité aux personnes âgées (Aspa) » (circular Cnav 2023-25). openfisca
    opens the ASPA early on a rate over 50 % or on `inapte_travail`, and otherwise paid the ASI
    until 65: at 62, 10 676.11 EUR of disposable income instead of the ASPA's 12 144.27."""
    rows = _priced(6_000, naissance)
    assert rows["asi"] == pytest.approx(asi, abs=0.05)
    assert rows["aspa"] == pytest.approx(aspa, abs=0.05)
    assert rows["revenu_disponible"] == pytest.approx(6_000 + asi + aspa, abs=0.05)


def test_past_62_an_aah_tops_up_an_invalidity_pension_without_the_asi_or_the_aspa() -> None:
    """At 80 % and 63, the AAH goes on and tops the pension up to its amount; its holder is
    taken not to claim the ASPA (D-185), and the ASI has stopped at the ASPA's age."""
    rows = compute(_invalide(6_000, naissance=1961, handicap={"taux_incapacite": 0.8}), 2024,
                   tier="full").baseline
    assert rows["asi"] == 0.0
    assert rows["aspa"] == 0.0
    assert rows["aah"] + 6_000 == pytest.approx(AAH_2024, abs=0.05)


def test_a_retirement_pension_alone_opens_no_asi() -> None:
    """The ASI also goes to the holder of an old-age benefit whose invalidity reduces their
    capacity of work in determined proportions (CSS art. L. 815-24). openfisca opens that branch
    on its generic `handicap` flag, which this project never sets: at 80 %, aged 60, with 3 000
    EUR of retirement pension, it paid 7 676.11 EUR of ASI and the AAH above the AAH amount
    (D-184). The ASI has a row now, and on that household it reads zero."""
    rows = compute(_handicape(naissance=1964, logement=RENTING, pension_annuelle=3_000), 2024,
                   tier="full").baseline
    assert rows["asi"] == 0.0
    assert rows["aah"] + 3_000 == pytest.approx(AAH_2024, abs=0.05)


#: Households whose minima read each other's months: the ASI beside an AAH in a dwelling, a
#: couple whose two ASI read one family base, a lone beneficiary in a couple under the cap, the
#: ASPA that the age opens, and the levies, which read the RFR of N-2 from inside the
#: disposable income.
ASI_ORDER_CASES: dict[str, dict[str, Any]] = {
    "aah_asi_locataire": {"adults": [
        {"salaire_brut_annuel": 0, "annee_naissance": 1980, "pension_invalidite_annuelle": 6_000,
         "handicap": {"taux_incapacite": 0.8}}], "logement": RENTING},
    "couple": {"adults": [
        {"salaire_brut_annuel": 0, "annee_naissance": 1980, "pension_invalidite_annuelle": 6_000},
        {"salaire_brut_annuel": 0, "annee_naissance": 1982, "pension_invalidite_annuelle": 6_000}],
        "couple_marie_ou_pacse": True},
    "couple_un_allocataire": {"adults": [
        {"salaire_brut_annuel": 0, "annee_naissance": 1980, "pension_invalidite_annuelle": 6_000},
        {"salaire_brut_annuel": 0, "annee_naissance": 1982}], "couple_marie_ou_pacse": True},
    "aspa_a_62_ans": {"adults": [
        {"salaire_brut_annuel": 0, "annee_naissance": 1962,
         "pension_invalidite_annuelle": 6_000}]},
    "prelevements": {"adults": [
        {"salaire_brut_annuel": 0, "annee_naissance": 1980,
         "pension_invalidite_annuelle": 30_000}]},
}


@pytest.mark.parametrize("name", sorted(ASI_ORDER_CASES))
def test_the_asi_prices_the_same_whatever_is_computed_first(name: str) -> None:
    """Built as `compute` builds the full tier: `pensions_invalidite` is one of the inputs that
    open a benefit cascade, so the housing aid is pinned month by month (D-178, D-179). Through
    the registry, as the API computes it, and with `revenu_disponible` first, as the EMTR's
    bumped leg does, every figure agrees."""
    from impots.engine import situations

    situation = build_situation(HouseholdInput.model_validate(ASI_ORDER_CASES[name]), 2024)
    assert situations.has_benefit_cascade(situation)
    registry = extract(_pinned(situation), 2024, "full")
    first = _pinned(situation)
    disposable = float(first.calculate("revenu_disponible", "2024")[0])
    assert disposable == pytest.approx(registry["revenu_disponible"], abs=0.05)
    for key, variable in (("asi", "asi"), ("aah", "aah"), ("mva", "caah"), ("aspa", "aspa"),
                          ("aide_logement", "aide_logement"), ("ir", "impot_revenu_restant_a_payer")):
        value = (float(first.calculate(variable, "2024").sum()) if key == "ir"
                 else float(first.calculate_add(variable, "2024").sum()))
        assert abs(value) == pytest.approx(registry[key], abs=0.05), key


# --------------------------------------------------------------------------- #
# a child's disability: the AEEH and the child's half-part (docs/DECISIONS.md D-191)
# --------------------------------------------------------------------------- #
#: The BMAF of 2024, summed over the year: 445.93 EUR a month to March, 466.44 from April.
BMAF_2024 = 3 * 445.93 + 9 * 466.44
#: The AEEH, 32 % of the BMAF for each child (CSS art. D. 541-1): 1 771.44 EUR in 2024.
AEEH_BASE_2024 = 0.32 * BMAF_2024
#: Each complément as a share of the BMAF (art. D. 541-2). The sixth is the majoration
#: pour tierce personne: 1 210.90 EUR a month to March, 1 266.60 from April.
AEEH_COMPLEMENTS = {1: 0.24, 2: 0.65, 3: 0.92, 4: 1.4257, 5: 1.8221}
MTP_2024 = 3 * 1_210.90 + 9 * 1_266.60
#: The majoration for a lone parent, by the complément's category (art. D. 541-4).
AEEH_MAJORATIONS = {2: 0.13, 3: 0.18, 4: 0.57, 5: 0.73, 6: 1.07}
#: Rents in zone 1 for a parent alone with one child: one above the threshold of the taper,
#: where the aid falls to 1 108.89 EUR over 2024, and one under it.
AEEH_HIGH_RENT = {"statut": "locataire_vide", "loyer_mensuel": 1_700, "zone_apl": 1}
AEEH_LOW_RENT = {"statut": "locataire_vide", "loyer_mensuel": 900, "zone_apl": 1}


def _aeeh_by_hand(categorie: int | None, isole: bool) -> float:
    """The AEEH of 2024 for one child, from the articles and the BMAF."""
    complement = MTP_2024 if categorie == 6 else AEEH_COMPLEMENTS.get(categorie, 0.0) * BMAF_2024
    majoration = AEEH_MAJORATIONS.get(categorie, 0.0) * BMAF_2024 if isole else 0.0
    return AEEH_BASE_2024 + complement + majoration


def _parent_of(handicap: dict[str, Any] | None, *, couple: bool = False, naissance: int = 2014,
               salaire: float = 0, logement: dict[str, Any] | None = None) -> HouseholdInput:
    """A parent, or a couple, and one child whose disability is `handicap`; nothing else
    unless asked."""
    child: dict[str, Any] = {"annee_naissance": naissance}
    if handicap is not None:
        child["handicap"] = handicap
    household: dict[str, Any] = {
        "adults": [{"salaire_brut_annuel": salaire, "annee_naissance": 1985}],
        "children": [child]}
    if couple:
        household["adults"].append({"salaire_brut_annuel": 0, "annee_naissance": 1985})
        household["couple_marie_ou_pacse"] = True
    if logement is not None:
        household["logement"] = logement
    return HouseholdInput.model_validate(household)


def _aeeh(household: HouseholdInput, system: Any = None) -> float:
    """The AEEH of 2024 alone, on the situation the builder writes. It reads no resource,
    so nothing needs pinning."""
    situation = build_situation(household, 2024)
    simulation = SimulationBuilder().build_from_entities(system or baseline(), situation)
    return float(simulation.calculate_add("aeeh", "2024")[0])


def test_a_childs_disability_is_written_on_every_covered_month() -> None:
    """Where the AEEH is open, openfisca's `handicap` flag, which its AEEH reads, with the
    complément's category; the card where it is held. On every month from N-2 to N, like
    the adult's inputs. The rate itself is not written: openfisca's AEEH never reads it,
    and a rate that opens nothing writes nothing."""
    covered = 36
    child = build_situation(_parent_of(
        {"taux_incapacite": 0.8, "complement_categorie": 3, "carte_invalidite": True}),
        2024)["individus"]["enfant_0"]
    assert list(child["handicap"].values()) == [True] * covered
    assert list(child["aeeh_niveau_handicap"].values()) == [3] * covered
    assert list(child["invalidite"].values()) == [True] * covered
    assert "taux_incapacite" not in child

    with_care = build_situation(_parent_of(
        {"taux_incapacite": 0.6, "etablissement_accompagnement_ou_soins": True}),
        2024)["individus"]["enfant_0"]
    assert list(with_care["handicap"].values()) == [True] * covered
    assert "aeeh_niveau_handicap" not in with_care and "invalidite" not in with_care

    for handicap in ({"taux_incapacite": 0.6}, None):
        bare = build_situation(_parent_of(handicap), 2024)["individus"]["enfant_0"]
        assert set(bare) == {"date_naissance"}, handicap


def test_from_eighty_per_cent_a_child_opens_the_aeeh_and_leaves_the_rsa_alone() -> None:
    """CSS art. L. 541-1 and R. 541-1: from 80 %, 32 % of the BMAF a month, 1 771.44 EUR in
    2024. The RSA does not count it (CASF art. R. 262-11, 6°), so a parent without income
    keeps the same RSA, and the disposable income rises by the AEEH exactly."""
    without = compute(_parent_of(None), 2024, tier="full").baseline
    rows = compute(_parent_of({"taux_incapacite": 0.8}), 2024, tier="full").baseline
    assert rows["aeeh"] == pytest.approx(AEEH_BASE_2024, abs=0.05)
    assert without["aeeh"] == 0.0
    assert without["rsa"] > 0
    assert rows["rsa"] == pytest.approx(without["rsa"], abs=0.01)
    assert rows["revenu_disponible"] - without["revenu_disponible"] == pytest.approx(
        AEEH_BASE_2024, abs=0.05)


def test_the_aeeh_leaves_the_prime_d_activite_and_the_housing_aid_alone() -> None:
    """The prime d'activité does not count it either (CSS art. R. 844-5, 6°), nor does the
    housing aid, which counts taxable income. A parent on 15 000 EUR who rents keeps both."""
    without = compute(_parent_of(None, salaire=15_000, logement=RENTING), 2024,
                      tier="full").baseline
    rows = compute(_parent_of({"taux_incapacite": 0.8}, salaire=15_000, logement=RENTING),
                   2024, tier="full").baseline
    assert without["ppa"] > 0 and without["aide_logement"] > 0
    assert rows["ppa"] == pytest.approx(without["ppa"], abs=0.01)
    assert rows["aide_logement"] == pytest.approx(without["aide_logement"], abs=0.01)
    assert rows["revenu_disponible"] - without["revenu_disponible"] == pytest.approx(
        AEEH_BASE_2024, abs=0.05)


def test_between_fifty_and_seventy_nine_per_cent_the_aeeh_needs_establishment_support_or_care(
) -> None:
    """CSS art. L. 541-1, third alinéa, and R. 541-1: from 50 %, the AEEH only where the
    child attends an establishment, or needs a « dispositif adapté ou d'accompagnement » or
    care the CDAPH recommends. Under 50 %, nothing."""
    assert _aeeh(_parent_of({"taux_incapacite": 0.6, "etablissement_accompagnement_ou_soins": True})
                 ) == pytest.approx(AEEH_BASE_2024, abs=0.05)
    assert _aeeh(_parent_of({"taux_incapacite": 0.6})) == 0.0
    assert _aeeh(_parent_of({"taux_incapacite": 0.4})) == 0.0


def test_the_establishment_support_or_care_is_refused_below_fifty_per_cent() -> None:
    """Below 50 % it opens nothing, and the engine would ignore it without a word."""
    with pytest.raises(ValueError, match="50"):
        _parent_of({"taux_incapacite": 0.4, "etablissement_accompagnement_ou_soins": True})


def test_a_complement_is_refused_without_the_aeeh() -> None:
    """A complément is a complément of the AEEH (art. L. 541-1, second alinéa): at 60 %
    without an establishment, support or care, there is no AEEH for it to complete."""
    with pytest.raises(ValueError, match="complément"):
        _parent_of({"taux_incapacite": 0.6, "complement_categorie": 2})


def test_the_card_is_refused_below_eighty_per_cent() -> None:
    """The mention « invalidité » of the carte mobilité inclusion goes to a rate of at least
    80 % (CASF art. L. 241-3), and a child cannot hold an invalidity pension's category."""
    with pytest.raises(ValueError, match="80"):
        _parent_of({"taux_incapacite": 0.7, "etablissement_accompagnement_ou_soins": True,
                    "carte_invalidite": True})


@pytest.mark.parametrize("categorie", [1, 2, 3, 4, 5, 6])
def test_each_complement_is_paid_at_its_own_category(categorie: int) -> None:
    """CSS art. D. 541-2: « Le taux du complément de deuxième catégorie [...] est fixé à 65 %
    de la base mensuelle de calcul des allocations familiales », and so for each category;
    the sixth is the majoration pour tierce personne. openfisca paid the second to the
    fifth category the complément of the category below: 3 100.02 EUR for a couple's child
    of the second category in 2024, instead of 5 369.68 (D-191)."""
    couple = _parent_of({"taux_incapacite": 0.8, "complement_categorie": categorie}, couple=True)
    assert _aeeh(couple) == pytest.approx(_aeeh_by_hand(categorie, isole=False), abs=0.05)


@pytest.mark.parametrize("categorie", [1, 2, 3, 4, 5, 6])
def test_a_lone_parent_gets_the_majoration_from_the_second_category(categorie: int) -> None:
    """CSS art. L. 541-4 and D. 541-4: a parent alone, from the second category, 13 % of the
    BMAF a month up to 107 % at the sixth. None at the first."""
    alone = _parent_of({"taux_incapacite": 0.8, "complement_categorie": categorie})
    assert _aeeh(alone) == pytest.approx(_aeeh_by_hand(categorie, isole=True), abs=0.05)


def test_the_aeeh_stops_at_twenty() -> None:
    """The family benefits run « jusqu'à l'âge de vingt ans » (CSS art. R. 512-2), and so
    does openfisca's AEEH. A child of 19 draws it all year. From 20 the disability is an
    adult's, the AAH, which the child's field does not open: refused, rather than priced as
    no AEEH beside a flag that would still lift the housing aid's taper."""
    assert _aeeh(_parent_of({"taux_incapacite": 0.8}, naissance=2005)) == pytest.approx(
        AEEH_BASE_2024, abs=0.05)
    with pytest.raises(ValueError, match="20 ans"):
        build_situation(_parent_of({"taux_incapacite": 0.8}, naissance=2004), 2024)
    assert build_situation(_parent_of(None, naissance=2004), 2024)


def test_the_aeeh_age_limit_matches_the_tree() -> None:
    """The builder pins the age from which a child opens no AEEH, because a refusal must
    not wait for a simulation. Read here from the tree, not trusted."""
    from impots.api.schemas import AEEH_AGE_MAXIMUM

    tree = baseline().parameters("2024-01-01").prestations_sociales \
        .prestations_familiales.education_presence_parentale.aeeh
    assert int(tree.age_maximum_enfant) == AEEH_AGE_MAXIMUM


def test_the_engine_alone_pays_each_complement_the_rate_of_the_category_below() -> None:
    """The kill test for the AEEH correction: raw openfisca pays the second category the
    first category's complément. The day this fails, openfisca pays each category its own,
    and `engine.corrections` must drop its own."""
    from impots.engine.system import uncorrected_baseline

    couple = _parent_of({"taux_incapacite": 0.8, "complement_categorie": 2}, couple=True)
    assert _aeeh(couple, uncorrected_baseline()) == pytest.approx(
        _aeeh_by_hand(1, isole=False), abs=0.05), (
        "openfisca no longer pays the second category the first's complément: remove the "
        "AEEH correction rather than keep one that corrects nothing")


def test_the_card_adds_a_half_part_to_the_quotient() -> None:
    """CGI art. 195, 2: the quotient « est augmenté d'une demi-part pour chaque enfant à
    charge [...] titulaire de la carte "mobilité inclusion" portant la mention
    "invalidité" ». A parent alone on 40 000 EUR: 2 parts, 154 EUR of tax; with the card,
    2.5 parts, and the décote takes the rest. The AEEH's flag alone moves nothing."""
    none = compute(_parent_of(None, salaire=40_000), 2024).baseline
    flag = compute(_parent_of({"taux_incapacite": 0.8}, salaire=40_000), 2024).baseline
    card = compute(_parent_of({"taux_incapacite": 0.8, "carte_invalidite": True},
                              salaire=40_000), 2024).baseline
    assert (none["parts_fiscales"], flag["parts_fiscales"], card["parts_fiscales"]) == (
        2.0, 2.0, 2.5)
    assert none["ir"] == pytest.approx(154, abs=0.5)
    assert flag["ir"] == none["ir"]
    assert card["ir"] == 0.0


def test_past_the_cap_the_card_is_worth_the_cap_and_the_complementary_reduction() -> None:
    """CGI art. 197, I, 2: the half-part's gain is capped at 1 791 EUR, and a half-part of
    art. 195, 2 then earns « une réduction d'impôt égale à 1 785 € ». A parent alone on
    150 000 EUR saves the two, 3 576 EUR."""
    none = compute(_parent_of(None, salaire=150_000), 2024).baseline
    card = compute(_parent_of({"taux_incapacite": 0.8, "carte_invalidite": True},
                              salaire=150_000), 2024).baseline
    assert none["ir"] - card["ir"] == pytest.approx(1_791 + 1_785, abs=1.0)


def test_an_aeeh_household_keeps_the_whole_housing_aid_above_the_taper() -> None:
    """CCH art. D. 823-16: the taper « ne s'applique pas lorsque le demandeur ou son
    conjoint est bénéficiaire [...] de l'allocation d'éducation de l'enfant handicapé ».
    openfisca lifts it on its `handicap` flag, which the builder writes only where the AEEH
    is open, so nothing needs correcting. At 1 700 EUR in zone 1 the parent keeps the aid
    of a rent under the taper; without the disability it falls to 1 108.89 EUR."""
    child = {"taux_incapacite": 0.8}
    high = compute(_parent_of(child, logement=AEEH_HIGH_RENT), 2024, tier="full").baseline
    low = compute(_parent_of(child, logement=AEEH_LOW_RENT), 2024, tier="full").baseline
    tapered = compute(_parent_of(None, logement=AEEH_HIGH_RENT), 2024, tier="full").baseline
    assert high["aide_logement"] == pytest.approx(low["aide_logement"], abs=0.05)
    assert tapered["aide_logement"] == pytest.approx(1_108.89, abs=0.05)


def test_an_aeeh_household_prices_the_same_whatever_is_computed_first() -> None:
    """Through the registry, as the API computes it, and with `revenu_disponible` first, as
    the EMTR's bumped leg does: the AEEH, the RSA, the housing aid above the taper and the
    disposable income agree."""
    situation = build_situation(_parent_of(
        {"taux_incapacite": 0.8, "complement_categorie": 3}, logement=AEEH_HIGH_RENT), 2024)
    registry = extract(_pinned(situation), 2024, "full")
    first = _pinned(situation)
    disposable = float(first.calculate("revenu_disponible", "2024")[0])
    assert disposable == pytest.approx(registry["revenu_disponible"], abs=0.05)
    for key in ("aeeh", "rsa", "aide_logement"):
        assert float(first.calculate_add(key, "2024").sum()) == pytest.approx(
            registry[key], abs=0.05), key


def test_the_aeeh_correction_adds_nothing_where_openfisca_opens_no_aeeh() -> None:
    """The correction adds the missing part of a complément only where openfisca's own test
    opens the AEEH: its `handicap` flag, under 20. A second category written by hand, without
    the flag on a child of 10, or with it on a child of 20, whom the wire refuses, draws
    nothing, as in raw openfisca."""
    covered = [f"{year}-{month:02d}" for year in (2022, 2023, 2024) for month in range(1, 13)]

    def aeeh(naissance: int, *, flag: bool) -> float:
        situation = build_situation(_parent_of(None, naissance=naissance), 2024)
        child = situation["individus"]["enfant_0"]
        child["aeeh_niveau_handicap"] = dict.fromkeys(covered, 2)
        if flag:
            child["handicap"] = dict.fromkeys(covered, True)
        simulation = SimulationBuilder().build_from_entities(baseline(), situation)
        return float(simulation.calculate_add("aeeh", "2024")[0])

    assert aeeh(2014, flag=False) == 0.0
    assert aeeh(2004, flag=True) == 0.0


# --------------------------------------------------------------------------- #
# the ASS in the income tax (docs/DECISIONS.md D-192)
# --------------------------------------------------------------------------- #
#: The ASS's daily amount, month by month in 2022, as openfisca's tree has it: 16.91 EUR until
#: March, 17.21 from April (décret n° 2022-493), 17.90 from July. A month is paid as 30 days.
ASS_JOUR_2022 = {**dict.fromkeys(range(1, 4), 16.91), **dict.fromkeys(range(4, 7), 17.21),
                 **dict.fromkeys(range(7, 13), 17.90)}
#: The minimum of the 10 % deduction of CGI art. 83, 3°, on the incomes of 2022 and of 2024
#: (versions of 3 June 2023 and of 19 June 2025): « ne peut être inférieur à 472 € », then
#: « à 504 € ».
DEDUCTION_MINIMUM_2022 = 472
DEDUCTION_MINIMUM_2024 = 504
#: The CSG exemption threshold of two parts on the RFR of 2022, for the levies of 2024:
#: 12 230 EUR and 3 265 more for each half-part, as openfisca's tree has it (D-188).
CSG_EXONERATION_DEUX_PARTS_2024 = 12_230 + 2 * 3_265


def _deduction(salaires: float, minimum: float = DEDUCTION_MINIMUM_2024) -> float:
    """CGI art. 83, 3°, by hand: a tenth of a member's salaries, which the ASS is taxed with,
    rounded to the euro, never under the minimum nor over the salaries themselves."""
    return min(max(round(0.10 * salaires), minimum), salaires)


def test_the_ass_is_taxed_as_a_salary_after_the_ten_per_cent_deduction() -> None:
    """C. trav. art. L. 5428-1: « Les règles fixées au 5 de l'article 158 du code général des
    impôts sont applicables », and so the ASS « est imposable entre les mains des bénéficiaires
    dans la catégorie des traitements et salaires » (BOI-RSA-CHAMP-20-20, § 20), after the 10 %
    deduction of CGI art. 83, 3°. Alone and without resources: 6 768 EUR of ASS less 677 is an
    RFR of 6 091 in 2024; 6 292.80 less 629 is 5 663.80 in 2022, the RFR the builder pins for
    the levies of 2024 (D-177). openfisca's own RFR was nil in both years. The income tax stays
    nil, and nothing else moves: the ASS bears no CSG and no CRDS (CSS art. L. 136-1-2, II, 5°),
    and the disposable income is D-189's, 7 747.49 EUR."""
    simulation, rows, _ = _ass_both_orders("seul")
    ass_2022 = sum(30 * jour for jour in ASS_JOUR_2022.values())
    assert ass_2022 == pytest.approx(6_292.80)
    assert _deduction(ASS_PLEINE_2024) == 677
    assert rows["revenu_fiscal_reference"] == pytest.approx(
        ASS_PLEINE_2024 - _deduction(ASS_PLEINE_2024), abs=0.01)
    assert float(simulation.calculate("rfr", "2022")[0]) == pytest.approx(
        ass_2022 - _deduction(ass_2022, DEDUCTION_MINIMUM_2022), abs=0.01)
    assert rows["ir"] == 0.0
    assert rows["revenu_disponible"] == pytest.approx(7_747.49, abs=0.05)


def test_a_small_ass_takes_the_minimum_deduction_apart_from_the_spouse_s_salary() -> None:
    """The deduction « ne peut être inférieur à 504 €, sans pouvoir excéder le montant brut des
    traitements et salaires. Cette disposition s'applique séparément aux rémunérations perçues
    par chaque membre du foyer fiscal » (CGI art. 83, 3°). Beside a spouse's 28 000 EUR of gross
    salary the ASS only tops the couple up to its ceiling, 1 853.48 EUR over 2024: a tenth would
    be 185, so 504 come off, and the RFR rises by 1 349.48 over the same couple without the ASS.
    The spouse's own deduction does not move."""
    with_ass = _ass_rows("conjoint_a_28000")
    without = _ass_rows("conjoint_a_28000_sans_ass")
    assert with_ass["ass"] == pytest.approx(1_853.48, abs=0.05)
    assert _deduction(with_ass["ass"]) == DEDUCTION_MINIMUM_2024
    assert with_ass["revenu_fiscal_reference"] - without["revenu_fiscal_reference"] == (
        pytest.approx(with_ass["ass"] - DEDUCTION_MINIMUM_2024, abs=0.01))


def test_the_deduction_is_taken_once_on_a_claimant_s_salary_and_ass_together() -> None:
    """The ASS is one of the claimant's « traitements et salaires », so it shares their deduction
    with a salary rather than opening a second minimum. 1 000 EUR of gross salary in 2024,
    written by hand as the EMTR's bumped leg writes its 100 EUR (the wire format refuses a
    salary beside the ASS, D-189), make 820.15 EUR taxable beside the 6 768 EUR of ASS, which a
    job seeker keeps: 7 588.15 less 759 is an RFR of 6 829.15. Two deductions, 677 and the
    minimum of 504, would have left 6 407.15; without the correction it was 316.15."""
    situation = perturb_first_adult(build_situation(ASS_CASES["seul"](), 2024), 2024, 1_000)
    simulation = _pinned(situation)
    salaire = float(simulation.calculate_add("salaire_imposable", "2024").sum())
    ass = float(simulation.calculate_add("ass", "2024").sum())
    assert salaire == pytest.approx(820.15, abs=0.01)
    assert ass == pytest.approx(ASS_PLEINE_2024, abs=0.05)
    assert float(simulation.calculate("rfr", "2024")[0]) == pytest.approx(
        salaire + ass - _deduction(salaire + ass), abs=0.01)


def test_beside_a_declared_pension_the_ass_reaches_the_crds_through_the_rfr_of_n_2() -> None:
    """D-189's measure. A spouse born in 1960 declares 15 000 EUR of pension, 13 500 after its
    10 %. Without the ASS, the RFR of 2022 that sets the rate of the levies on the pension of
    2024 was 13 500, under the exemption threshold of two parts, 12 230 + 2 x 3 265 = 18 760.
    With the ASS of 2022 it is 19 163.80, above it: the reduced rate, whose CSG of 3.8 % a
    declared pension is already net of (D-176), leaves 75 EUR of CRDS, 0.5 % of 15 000, and no
    CASA. The disposable income is the pension less that CRDS, the full ASS, and the prime de
    Noël of 152.45 EUR."""
    simulation, rows, _ = _ass_both_orders("pension_du_conjoint")
    ass_2022 = sum(30 * jour for jour in ASS_JOUR_2022.values())
    rfr_2022 = 0.9 * 15_000 + ass_2022 - _deduction(ass_2022, DEDUCTION_MINIMUM_2022)
    assert rfr_2022 > CSG_EXONERATION_DEUX_PARTS_2024 > 0.9 * 15_000
    assert float(simulation.calculate("rfr", "2022")[0]) == pytest.approx(rfr_2022, abs=0.01)
    assert rows["revenu_fiscal_reference"] == pytest.approx(
        0.9 * 15_000 + ASS_PLEINE_2024 - _deduction(ASS_PLEINE_2024), abs=0.01)
    assert rows["ass"] == pytest.approx(ASS_PLEINE_2024, abs=0.05)
    assert rows["ir"] == 0.0
    assert rows["revenu_disponible"] == pytest.approx(
        15_000 - 0.005 * 15_000 + ASS_PLEINE_2024 + 152.45, abs=0.05)


def test_the_ass_of_n_2_sets_the_rate_of_the_csg_on_a_spouse_s_unemployment_benefit() -> None:
    """The CSG on unemployment benefit takes its rate from the RFR of N-2. Beside a spouse's
    24 000 EUR of gross benefit, that RFR was the benefit less its 10 %, 21 600 EUR, under the
    full-rate threshold of two parts, 15 988 + 2 x 4 269 = 24 526 in openfisca's tree: the
    reduced rate, 3.8 %, all deductible. With the claimant's ASS of 2022 it passes it, and the
    rate is the full one, 6.2 %, of which 2.4 % is not deductible: 565.92 EUR more on 98.25 % of
    the benefit. The ASS's resources read that benefit net of its CSG (D-189), so the ASS rises
    with it, from 1 263.50 to 1 531.73 EUR."""
    simulation, rows, _ = _ass_both_orders("conjoint_au_chomage")
    ass_2022 = float(simulation.calculate_add("ass", "2022").sum())
    rfr_2022 = 0.9 * ARE_DU_CONJOINT + ass_2022 - _deduction(ass_2022, DEDUCTION_MINIMUM_2022)
    assert rfr_2022 > 15_988 + 2 * 4_269 > 0.9 * ARE_DU_CONJOINT
    assert float(simulation.calculate("rfr", "2022")[0]) == pytest.approx(rfr_2022, abs=0.01)
    csg_imposable = -float(simulation.calculate_add("csg_imposable_chomage", "2024").sum())
    assert csg_imposable == pytest.approx(0.024 * 0.9825 * ARE_DU_CONJOINT, abs=0.05)
    assert rows["ass"] == pytest.approx(1_531.73, abs=0.05)


def test_a_card_holder_s_ass_meets_the_abatement_of_art_157_bis() -> None:
    """The ASS is in the revenu net global, so the abatement of CGI art. 157 bis meets it. A
    claimant alone who holds the card « mobilité inclusion » marked « invalidité » (D-188) has
    6 091 EUR of net income, under 17 510, and deducts 2 796: an RFR of 6 768 - 677 - 2 796 =
    3 295. Added to the RFR rather than to the income, the ASS would have escaped the
    abatement and left 6 091."""
    rows = _ass_rows("carte")
    assert rows["revenu_fiscal_reference"] == pytest.approx(
        ASS_PLEINE_2024 - _deduction(ASS_PLEINE_2024) - 2_796, abs=0.01)
    assert rows["ir"] == 0.0


def test_the_family_benefits_leave_the_claimant_s_ass_out_of_their_resources() -> None:
    """The family benefits read the incomes of N-2 retained for the income tax, but when a person
    « en chômage total depuis au moins deux mois consécutifs, ne bénéficie pas ou ne bénéficie
    plus d'une indemnisation » by the insurance, « il n'est pas tenu compte des revenus
    d'activité professionnelle ni des indemnités de chômage perçus par l'intéressé », from
    « l'admission à l'allocation de solidarité spécifique » (CSS art. R. 532-7). A claimant beside
    a spouse's 24 000 EUR of salary, with two children: the ASS of 2022 enters the RFR of 2022,
    after its own deduction, and not the resources of the family benefits, which stay the
    spouse's, 17 714.16 EUR; nor does it make the couple « biactif », the ASS being no
    professional income."""
    def simulation(ass: bool) -> Any:
        claimant = _adulte(0, 1975, fin_de_droits_ass=True) if ass else _adulte(0, 1975)
        household = _foyer(claimant, _adulte(24_000, 1975),
                           children=[{"annee_naissance": 2012}, {"annee_naissance": 2015}])
        return _pinned(build_situation(household, 2024))

    with_ass, without = simulation(True), simulation(False)
    ass_2022 = float(with_ass.calculate_add("ass", "2022").sum())
    rfr_2022 = (float(with_ass.calculate("rfr", "2022")[0])
                - float(without.calculate("rfr", "2022")[0]))
    assert rfr_2022 == pytest.approx(
        ass_2022 - _deduction(ass_2022, DEDUCTION_MINIMUM_2022), abs=0.01)
    for month in ("2024-01", "2024-07"):
        base = float(with_ass.calculate("prestations_familiales_base_ressources", month)[0])
        assert base == pytest.approx(17_714.16, abs=0.01), month
        assert base == pytest.approx(float(without.calculate(
            "prestations_familiales_base_ressources", month)[0]), abs=0.01), month
        assert not bool(with_ass.calculate("biactivite", month)[0]), month


@pytest.mark.parametrize("name", ["seul", "pension_du_conjoint", "conjoint_au_chomage",
                                  "allocataire_second", "carte"])
def test_the_ass_is_taxed_the_same_whatever_is_computed_first(name: str) -> None:
    """The income tax of N reads the ASS of N, and the RFR of N-2, pinned first (D-177), the ASS
    of N-2. Through the registry, as the API reads it, the income tax comes first and the ASS is
    computed inside it; with `revenu_disponible` first, as the EMTR's bumped leg computes it,
    the ASS comes through the minima. The tax rows, the ASS and the disposable income agree."""
    _, rows, first = _ass_both_orders(name)
    computed_first = {
        "revenu_fiscal_reference": float(first.calculate("rfr", "2024")[0]),
        "ir": -float(first.calculate("impot_revenu_restant_a_payer", "2024")[0]) + 0.0,
        "ass": float(first.calculate_add("ass", "2024").sum()),
        "revenu_disponible": float(first.calculate("revenu_disponible", "2024")[0]),
    }
    for key, value in computed_first.items():
        assert value == pytest.approx(rows[key], abs=0.05), key


@pytest.mark.parametrize("name", ["seul", "pension_du_conjoint"])
def test_the_light_tier_taxes_the_ass_as_the_full_tier_does(name: str) -> None:
    """The income tax reads the ASS, so the light tier of a claimant computes it, with the AAH
    and the ASI its eligibility reads, and nothing the ASS tops up: neither the RSA, nor the
    prime d'activité, nor the housing aid, nor the disposable income. Its rows are the full
    tier's, the RFR among them."""
    from impots.engine import situations

    light = compute(ASS_CASES[name](), 2024, tier="light").baseline
    full = _ass_rows(name)
    for row in LIGHT_ROWS:
        assert light[row.key] == full[row.key], row.key
    simulation = SimulationBuilder().build_from_entities(
        baseline(), build_situation(ASS_CASES[name](), 2024))
    situations.pin_rfr_n_2(simulation, 2024)
    extract(simulation, 2024, "light")
    for variable in ("revenu_disponible", "af", "ppa", "rsa", "aide_logement"):
        assert not list(simulation.get_holder(variable).get_known_periods()), variable
    assert list(simulation.get_holder("ass").get_known_periods())


def test_without_a_claimant_the_income_tax_never_computes_the_ass() -> None:
    """The ASS needs its work condition, `ass_precondition_remplie`: nobody meets it, the ASS is
    nil, and computing it would cost its whole chain, the AAH and the ASI of thirteen months,
    for every RFR the light tier, the builders' pins and the population ask for. The correction
    reads the ASS only when someone in the simulation meets the condition that year."""
    from impots.engine import situations

    simulation = SimulationBuilder().build_from_entities(baseline(),
                                                         build_situation(COUPLE, 2024))
    situations.pin_rfr_n_2(simulation, 2024)
    extract(simulation, 2024, "light")
    assert list(simulation.get_holder("rfr").get_known_periods())
    assert not list(simulation.get_holder("ass").get_known_periods())


def test_the_engine_alone_leaves_the_ass_out_of_the_income_tax() -> None:
    """The kill test for the ASS's taxation, on raw openfisca: the claimant alone draws the full
    6 768 EUR of 2024, and the RFR is nil. The day this fails, openfisca taxes the ASS itself,
    and `engine.corrections` must drop its own."""
    from impots.engine.system import uncorrected_baseline

    situation = build_situation(ASS_CASES["seul"](), 2024)
    raw = SimulationBuilder().build_from_entities(uncorrected_baseline(), situation)
    assert float(raw.calculate_add("ass", "2024").sum()) == pytest.approx(
        ASS_PLEINE_2024, abs=0.05)
    assert float(raw.calculate("rfr", "2024")[0]) == 0.0, (
        "openfisca now taxes the ASS: remove the correction rather than keep one that "
        "corrects nothing")
