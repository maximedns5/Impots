"""Engine wiring, tiers, EMTR and timing budget (spec §3.2, §3.3, §3.5, §6).

These are the tests that would catch a change of shape rather than a change of
number: a variable that moved entity, a light request that quietly started
computing the whole benefits cascade, a salary written annually onto a monthly
variable.
"""

from __future__ import annotations

import functools
import time

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


def test_an_unemployed_persons_emtr_compares_two_computations_of_the_same_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unemployment benefit has no field on the wire yet, so it is written into the
    situation the way a field would write it. The household builder has to close the
    regress for whatever a situation carries: the EMTR's base comes from the registry,
    its bumped leg from a fresh simulation that computes `revenu_disponible` first, and
    before D-177 those two read the RFR of N-2 differently. A 30 000 EUR chômeur offered
    100 EUR of salary was reported a marginal rate of -2.68.

    Both legs of the hand computation go through `compute`, so through the same builder
    as the rate under test: the bumped one by perturbing the situation it builds."""
    from impots.engine import situations

    original = situations.build_situation
    bump = {"on": False}

    def with_unemployment_benefit(household, year, historique_revenus=True):
        situation = original(household, year, historique_revenus)
        situation["individus"]["adulte_0"]["chomage_brut"] = {
            month: 2_500.0
            for covered in situations.covered_years(year, historique_revenus)
            for month in situations.months(covered)
        }
        return perturb_first_adult(situation, year, EMTR_STEP) if bump["on"] else situation

    monkeypatch.setattr(situations, "build_situation", with_unemployment_benefit)
    unemployed = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1980}]})
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

    No field reaches the AAH yet: the taux d'incapacité, and the partner's invalidity
    inputs, are written into the situation the way a field would write them, on every
    covered month. Both legs of the hand computation go through `compute` (D-179)."""
    from impots.engine import situations

    original = situations.build_situation
    bump = {"on": False}
    person, partner_inputs = AAH_PARTNERS[partner]

    def with_disability(household, year, historique_revenus=True):
        situation = original(household, year, historique_revenus)
        covered = [month for y in situations.covered_years(year, historique_revenus)
                   for month in situations.months(y)]
        situation["individus"]["adulte_0"]["taux_incapacite"] = dict.fromkeys(covered, 0.8)
        for name, value in partner_inputs.items():
            situation["individus"]["adulte_1"][name] = dict.fromkeys(covered, value)
        return perturb_first_adult(situation, year, EMTR_STEP) if bump["on"] else situation

    monkeypatch.setattr(situations, "build_situation", with_disability)
    couple = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 6_000, "annee_naissance": 1975}, person],
         "couple_marie_ou_pacse": True})
    result = compute(couple, 2024, tier="full", emtr=True)
    bump["on"] = True
    bumped = compute(couple, 2024, tier="full").baseline["revenu_disponible"]
    by_hand = 1.0 - (bumped - result.baseline["revenu_disponible"]) / EMTR_STEP
    assert result.emtr == pytest.approx(by_hand, abs=1e-3)
    assert 0.0 < result.emtr < 1.0
