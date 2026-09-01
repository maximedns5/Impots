"""The firm tax engine (PHASE2_SPEC §1, §2, §5).

Golden cases here assert **relative** tolerance 1e-5, never ±2 € (§1.4).
openfisca-core computes in float32, which is about seven significant digits: on a
34.8 M€ liability that is a couple of euros, so an absolute euro tolerance would
be either meaningless at the top of the distribution or unsatisfiable.

Every case below is derived by hand in its own assertion, not read back off the
engine — an engine that agrees with itself proves nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from openfisca_core.simulation_builder import SimulationBuilder

from impots import guards
from impots.entreprises import aggregate as firm_aggregate
from impots.entreprises import runner as firm_runner
from impots.entreprises import system as firm_system
from impots.entreprises.population import Cell, build_firms
from impots.entreprises.reforms import SCALAR_KNOBS, FirmReformSpec, resolve, verify_scales

YEAR = "2026"

#: float32 gives ~7 significant digits; §1.4 fixes the tolerance there.
RELATIVE_TOLERANCE = 1e-5


def simulate(
    system: object,
    chiffre_affaires: list[float],
    benefice: list[float],
    valeur_ajoutee: list[float] | None = None,
    year: str = YEAR,
) -> object:
    builder = SimulationBuilder()
    builder.create_entities(system)
    builder.declare_person_entity("entreprise", np.arange(len(chiffre_affaires)))
    simulation = builder.build(system)
    simulation.set_input("chiffre_affaires", year, np.array(chiffre_affaires, dtype=np.float64))
    simulation.set_input("benefice_imposable", year, np.array(benefice, dtype=np.float64))
    if valeur_ajoutee is not None:
        simulation.set_input("valeur_ajoutee", year, np.array(valeur_ajoutee, dtype=np.float64))
    return simulation


def close(got: float, expected: float) -> bool:
    return abs(got - expected) <= RELATIVE_TOLERANCE * max(abs(expected), 1.0)


@pytest.fixture(scope="module")
def tbs() -> object:
    return firm_system.baseline()


# --------------------------------------------------------------------------- #
# the parameter tree
# --------------------------------------------------------------------------- #
def test_parameters_resolve_by_date(tbs: object) -> None:
    """Dated values are the whole point: a backdated run and a reform are the same
    operation on the tree."""
    p = tbs.parameters  # type: ignore[attr-defined]
    assert p.impot_societes.taux_normal("2026-01-01") == 0.25
    assert p.impot_societes.plafond_taux_reduit("2026-01-01") == 42_500


def test_the_reduced_rate_slice_widened_for_fy2022_not_fy2023(tbs: object) -> None:
    """Confirmed against Légifrance, and it caught an error in the first encoding.

    The three parameters on the same page of CGI 219-I do not switch on the same
    event. The 25 % rate and the 10 M€ turnover ceiling switch on exercices
    *ouverts*; the 42 500 € profit slice switches on exercices **clos** à compter du
    31 décembre 2022. For a calendar-year firm that means FY2022 already gets
    42 500 €, and dating it from 2023 — the obvious reading — over-taxes every
    small firm by 660 € for a whole year.
    """
    p = tbs.parameters.impot_societes  # type: ignore[attr-defined]
    assert p.plafond_taux_reduit("2021-01-01") == 38_120
    assert p.plafond_taux_reduit("2022-01-01") == 42_500


def test_the_normal_rate_has_no_value_before_2022(tbs: object) -> None:
    """From 2019 to 2021 the normal rate was a two-bracket scale that also depended
    on turnover. This module does not encode that, so an earlier query resolves to
    nothing and any formula using it fails — rather than silently applying a flat
    rate that never existed."""
    assert tbs.parameters.impot_societes.taux_normal("2021-01-01") is None  # type: ignore[attr-defined]


def test_the_two_pme_turnover_thresholds_are_separate(tbs: object) -> None:
    """They diverged in 2021 and sharing one constant would wrongly exempt every
    firm between 7.63 M€ and 10 M€ from the contribution sociale.

    CGI 219-I-b moved its reduced-rate ceiling to 10 M€; CSS art. 235 ter ZC left
    the contribution sociale exemption at 7.63 M€.
    """
    p = tbs.parameters.impot_societes  # type: ignore[attr-defined]
    assert p.plafond_ca_taux_reduit("2026-01-01") == 10_000_000
    assert p.contribution_sociale.seuil_ca_exoneration("2026-01-01") == 7_630_000


def test_no_parameter_node_is_a_python_keyword(tbs: object) -> None:
    """A node named `is` breaks attribute access on the parameter tree, and the
    breakage is silent — `parameters.is_` resolves to nothing useful. Verified in
    the prototype; asserted here so it cannot come back."""
    import keyword

    def walk(node: object, path: str = "") -> list[str]:
        found = []
        for name in getattr(node, "_children", {}) or {}:
            if keyword.iskeyword(name):
                found.append(f"{path}.{name}")
            found += walk(node._children[name], f"{path}.{name}")  # type: ignore[attr-defined]
        return found

    assert walk(tbs.parameters) == []  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# IS — hand-derived goldens
# --------------------------------------------------------------------------- #
def test_pme_at_the_reduced_rate_kink(tbs: object) -> None:
    """42 500 € of profit at 15 % is 6 375 €. One euro more is taxed at 25 %: the
    reduced rate applies to a slice, not to the whole profit."""
    result = simulate(tbs, [1e6, 1e6], [42_500.0, 85_000.0])
    tax = result.calculate("impot_societes", YEAR)  # type: ignore[attr-defined]
    assert close(tax[0], 42_500 * 0.15)
    assert close(tax[1], 42_500 * 0.15 + 42_500 * 0.25)


def test_a_firm_over_the_turnover_ceiling_loses_the_reduced_rate(tbs: object) -> None:
    """The ceiling is on turnover, not profit: two firms with identical profits pay
    differently because one sells more."""
    result = simulate(tbs, [9e6, 11e6], [42_500.0, 42_500.0])
    tax = result.calculate("impot_societes", YEAR)  # type: ignore[attr-defined]
    assert close(tax[0], 42_500 * 0.15)
    assert close(tax[1], 42_500 * 0.25)


def test_loss_makers_pay_no_is(tbs: object) -> None:
    result = simulate(tbs, [5e6], [0.0])
    assert result.calculate("impot_societes", YEAR)[0] == 0.0  # type: ignore[attr-defined]


def test_large_firm_pays_the_normal_rate_throughout(tbs: object) -> None:
    result = simulate(tbs, [50e6], [10e6])
    assert close(result.calculate("impot_societes", YEAR)[0], 10e6 * 0.25)  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# contribution sociale sur l'IS
# --------------------------------------------------------------------------- #
def test_contribution_sociale_applies_above_the_abattement(tbs: object) -> None:
    """3.3 % of the IS *exceeding* 763 000 €, so a firm whose IS is 1 250 000 € pays
    on 487 000 € of it."""
    result = simulate(tbs, [30e6], [5e6])
    got = result.calculate("contribution_sociale_is", YEAR)[0]  # type: ignore[attr-defined]
    assert close(got, (5e6 * 0.25 - 763_000) * 0.033)


def test_contribution_sociale_exempts_small_turnover(tbs: object) -> None:
    """The exemption is on turnover, so a small firm with a large profit still pays
    nothing — which is the kind of asymmetry an effective-rate profile shows up."""
    result = simulate(tbs, [7e6], [10e6])
    assert result.calculate("contribution_sociale_is", YEAR)[0] == 0.0  # type: ignore[attr-defined]


def test_contribution_sociale_is_zero_when_is_is_below_the_abattement(tbs: object) -> None:
    result = simulate(tbs, [30e6], [1e6])
    assert result.calculate("contribution_sociale_is", YEAR)[0] == 0.0  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# C3S
# --------------------------------------------------------------------------- #
def test_c3s_is_an_abattement_not_a_threshold(tbs: object) -> None:
    """A firm one euro over 19 M€ pays 0.16 % of that one euro, not of 19 000 001 €.
    Reading it as a threshold puts a 30 000 € cliff into the effective-rate profile
    that does not exist in the law."""
    result = simulate(tbs, [19e6, 19e6 + 1_000.0, 25e6], [1e6, 1e6, 1e6])
    tax = result.calculate("c3s", YEAR)  # type: ignore[attr-defined]
    assert tax[0] == 0.0
    assert close(tax[1], 1_000.0 * 0.0016)
    assert close(tax[2], (25e6 - 19e6) * 0.0016)


def test_the_c3s_abattement_has_a_two_euro_resolution_floor(tbs: object) -> None:
    """Found while writing the test above, and worth pinning rather than hiding.

    float32 has an ULP of **2 €** at 19 000 000, so a firm one euro over the C3S
    abattement is not representable: it rounds back onto the threshold and pays
    nothing. Two euros over is representable and pays.

    At aggregate scale this is irrelevant — it concerns the handful of firms
    sitting within a couple of euros of the abattement, and costs fractions of a
    centime each. It matters because it bounds what a *per-firm* C3S figure can
    honestly claim, which is why §1.4 forbids displaying one to more precision
    than float32 warrants.
    """
    result = simulate(tbs, [19e6 + 1.0, 19e6 + 2.0], [1e6, 1e6])
    tax = result.calculate("c3s", YEAR)  # type: ignore[attr-defined]
    assert tax[0] == 0.0, "one euro over the abattement is below float32 resolution"
    assert close(tax[1], 2.0 * 0.0016)


def test_c3s_does_not_depend_on_profit(tbs: object) -> None:
    """It is a turnover tax: a loss-maker pays it in full. That is the whole reason
    it is politically contested, and the reason it is our cleanest validation line."""
    result = simulate(tbs, [25e6, 25e6], [0.0, 5e6])
    tax = result.calculate("c3s", YEAR)  # type: ignore[attr-defined]
    assert tax[0] == tax[1]


# --------------------------------------------------------------------------- #
# totals and effective rate
# --------------------------------------------------------------------------- #
def test_total_is_the_sum_of_the_parts(tbs: object) -> None:
    result = simulate(tbs, [30e6], [5e6])
    total = result.calculate("prelevements_entreprise", YEAR)[0]  # type: ignore[attr-defined]
    parts = sum(
        result.calculate(name, YEAR)[0]  # type: ignore[attr-defined]
        for name in ("impot_societes", "contribution_sociale_is", "cebge", "cvae", "c3s")
    )
    assert close(total, parts)


def test_effective_rate_is_zero_rather_than_infinite_for_loss_makers(tbs: object) -> None:
    """A firm with no profit has no effective rate on profit. Reporting one would put
    a meaningless spike in every distribution it enters."""
    result = simulate(tbs, [25e6], [0.0])
    assert result.calculate("taux_effectif", YEAR)[0] == 0.0  # type: ignore[attr-defined]


def test_effective_rate_exceeds_the_headline_rate_when_turnover_taxes_bite(
    tbs: object,
) -> None:
    """C3S is charged on turnover, so a low-margin firm can pay well over 25 % of its
    profit — the single most useful thing the firm module can show."""
    result = simulate(tbs, [100e6], [1e6])
    assert result.calculate("taux_effectif", YEAR)[0] > 0.25  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# scale and precision
# --------------------------------------------------------------------------- #
def test_computes_at_scale_without_nan(tbs: object) -> None:
    """500 000 firms is the whole IS population's order of magnitude and runs in
    well under a second, which is why the firm side needs no batch machinery."""
    rng = np.random.default_rng(7)
    turnover = rng.lognormal(np.log(400_000), 1.8, 200_000)
    profit = np.maximum(rng.normal(0.06, 0.10, 200_000) * turnover, 0)
    result = simulate(tbs, turnover.tolist(), profit.tolist())
    tax = result.calculate("prelevements_entreprise", YEAR)  # type: ignore[attr-defined]
    assert np.isfinite(tax).all()
    assert (tax >= 0).all()


def test_float32_precision_is_within_the_declared_tolerance(tbs: object) -> None:
    """The reason golden cases here are relative: on a 34.8 M€ liability float32
    lands a couple of euros away, and an absolute ±2 € rule would be either
    meaningless or unsatisfiable depending on firm size."""
    profit = 139_246_664.0
    result = simulate(tbs, [500e6], [profit])
    assert close(result.calculate("impot_societes", YEAR)[0], profit * 0.25)  # type: ignore[attr-defined]


# --------------------------------------------------------------------------- #
# reforms
# --------------------------------------------------------------------------- #
def test_reform_moves_the_tax_and_leaves_the_baseline_alone(tbs: object) -> None:
    firm_system.clear_cache()
    turnover, profit = [50e6, 1e6], [10e6, 100_000.0]
    before = simulate(tbs, turnover, profit).calculate("impot_societes", YEAR)  # type: ignore[attr-defined]

    reformed = firm_system.reformed_for(FirmReformSpec(is_taux_normal=0.30), 2026)
    after = simulate(reformed, turnover, profit).calculate("impot_societes", YEAR)  # type: ignore[attr-defined]
    assert after.sum() > before.sum()

    again = simulate(tbs, turnover, profit).calculate("impot_societes", YEAR)  # type: ignore[attr-defined]
    assert np.allclose(again, before)
    assert tbs.parameters.impot_societes.taux_normal("2026-01-01") == 0.25  # type: ignore[attr-defined]


def test_reform_cache_returns_the_same_system(tbs: object) -> None:
    firm_system.clear_cache()
    first = firm_system.reformed_for(FirmReformSpec(c3s_taux=0.002), 2026)
    assert firm_system.reformed_for(FirmReformSpec(c3s_taux=0.002), 2026) is first
    assert firm_system.reformed_for(FirmReformSpec(c3s_taux=0.003), 2026) is not first
    assert firm_system.reformed_for(FirmReformSpec(c3s_taux=0.002), 2027) is not first


@pytest.mark.parametrize("knob", sorted(SCALAR_KNOBS))
def test_every_whitelisted_knob_reaches_its_parameter(knob: str, tbs: object) -> None:
    """A knob whose path silently stopped resolving would look exactly like a reform
    the user asked for and got."""
    current = float(resolve(tbs.parameters, SCALAR_KNOBS[knob])("2026-01-01"))  # type: ignore[attr-defined]
    wanted = current * 1.5 if current else 1000.0
    if knob.endswith("taux"):
        wanted = min(wanted, 1.0)
    reformed = firm_system.reformed_for(FirmReformSpec(**{knob: wanted}), 2026)
    applied = float(resolve(reformed.parameters, SCALAR_KNOBS[knob])("2026-01-01"))
    assert applied == pytest.approx(wanted, rel=1e-9)


def test_verify_scales_refuses_a_mismatch(tbs: object) -> None:
    """The read-back guard must fire when the parameters are not what was asked —
    D-007's lesson, in place before the CVAE barème arrives to need it."""
    with pytest.raises(AssertionError, match="ne correspondent pas"):
        verify_scales(tbs, FirmReformSpec(is_taux_normal=0.99), 2026)


def test_an_empty_reform_is_not_a_reform() -> None:
    assert FirmReformSpec().is_empty()
    assert not FirmReformSpec(c3s_taux=0.002).is_empty()


def test_reduced_rate_above_the_normal_rate_is_refused() -> None:
    """Almost never the intention, and silently produces a surtax on small profits."""
    with pytest.raises(ValueError, match="surtaxe"):
        FirmReformSpec(is_taux_normal=0.25, is_taux_reduit=0.30)


def test_cebge_thresholds_must_be_ordered() -> None:
    with pytest.raises(ValueError, match="strictement croissants"):
        FirmReformSpec(cebge_seuils_et_taux=[
            {"seuil_ca": 3e9, "taux": 0.412}, {"seuil_ca": 1e9, "taux": 0.206},
        ])


def test_unknown_knobs_are_refused() -> None:
    """The reform surface is a whitelist: raw parameter paths must not get through."""
    with pytest.raises(ValueError, match="Extra inputs"):
        FirmReformSpec.model_validate({"impot_societes.taux_normal": 0.3})


# --------------------------------------------------------------------------- #
# the synthetic firm population (§3)
#
# Runs on tests/fixtures/firm_cells.json — invented cells with a realistic shape.
# SIRENE and ESANE stay out of the tree and CI has no network.
# --------------------------------------------------------------------------- #
FIXTURE = Path(__file__).parent / "fixtures" / "firm_cells.json"


def load_cells() -> tuple[list[Cell], float]:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [Cell(**cell) for cell in raw["cells"]], raw["fiscal_to_accounting"]


@pytest.fixture(scope="module")
def firm_population() -> tuple[pl.DataFrame, object]:
    cells, ratio = load_cells()
    return build_firms(cells, fiscal_to_accounting=ratio)


def test_published_cell_totals_are_reproduced_exactly(
    firm_population: tuple[pl.DataFrame, object],
) -> None:
    """Firm counts, turnover and value added are what the build calibrates on, so
    they are reproduced exactly rather than approximately — and that is checked,
    not assumed. Both Phase 1 weighting defects were steps that quietly moved a
    total while every other guard stayed green."""
    _, stats = firm_population
    for name, error in stats.calibration_error.items():  # type: ignore[attr-defined]
        assert abs(error) < 1e-9, f"{name} drifted by {error:+.2e}"


def test_calibrated_totals_match_the_published_cells(
    firm_population: tuple[pl.DataFrame, object],
) -> None:
    firms, _ = firm_population
    cells, _ratio = load_cells()
    assert firms["weight"].sum() == pytest.approx(sum(c.n_firms for c in cells), rel=1e-12)
    assert guards.weighted_total(firms, "chiffre_affaires") == pytest.approx(
        sum(c.turnover_total for c in cells), rel=1e-9
    )
    assert guards.weighted_total(firms, "valeur_ajoutee") == pytest.approx(
        sum(c.value_added_total for c in cells), rel=1e-9
    )


def test_loss_share_matches_the_published_probability(
    firm_population: tuple[pl.DataFrame, object],
) -> None:
    """P(loss) is the ONLY loss mechanism.

    The first version drew profit margins that could go negative and *then* applied
    the Bernoulli, zeroing a second tranche of firms on top: the realised loss
    share came out at 49 % against a specified 28 %. The share of firms paying no
    IS is a validation line (§3.4), so that bug would have made the line measure
    the build rather than the model.
    """
    _, stats = firm_population
    cells, _ = load_cells()
    total = sum(c.n_firms for c in cells)
    expected = sum(c.n_firms * c.p_loss for c in cells) / total
    assert stats.share_loss_making == pytest.approx(expected, abs=0.02)  # type: ignore[attr-defined]


def test_population_is_deterministic() -> None:
    cells, ratio = load_cells()
    first, _ = build_firms(cells, fiscal_to_accounting=ratio)
    second, _ = build_firms(cells, fiscal_to_accounting=ratio)
    assert first.equals(second)


def test_value_added_never_exceeds_turnover(
    firm_population: tuple[pl.DataFrame, object],
) -> None:
    _, stats = firm_population
    assert stats.cells_with_va_above_ca == 0  # type: ignore[attr-defined]


def test_no_negative_financials(firm_population: tuple[pl.DataFrame, object]) -> None:
    firms, _ = firm_population
    for column in ("chiffre_affaires", "valeur_ajoutee", "benefice_imposable", "weight"):
        assert (firms[column].to_numpy() >= 0).all(), column


def test_an_empty_skeleton_is_refused() -> None:
    with pytest.raises(ValueError, match="needs a published skeleton"):
        build_firms([], fiscal_to_accounting=0.8)


# --------------------------------------------------------------------------- #
# running the population
# --------------------------------------------------------------------------- #
def test_run_preserves_the_weighted_totals(
    firm_population: tuple[pl.DataFrame, object],
) -> None:
    """A run reweights nothing, so any drift in the weighted firm count or turnover
    is a bug in the run itself (§3.5)."""
    firms, _ = firm_population
    result = firm_runner.run(firms, 2026)
    assert result.guards["weighted_firms"] == pytest.approx(firms["weight"].sum(), rel=1e-12)
    assert result.guards["weighted_turnover"] == pytest.approx(
        guards.weighted_total(firms, "chiffre_affaires"), rel=1e-9
    )


def test_run_refuses_a_population_missing_inputs() -> None:
    """A variable that silently takes its default computes a plausible tax forever."""
    with pytest.raises(firm_runner.FirmRunError, match="missing required inputs"):
        firm_runner.run(pl.DataFrame({"weight": [1.0], "chiffre_affaires": [1e6]}), 2026)


def test_effective_rate_rises_with_firm_size(
    firm_population: tuple[pl.DataFrame, object],
) -> None:
    """The shape the module exists to show: turnover taxes and the surcharges make
    large firms pay a higher share of profit than the headline rate, while the
    reduced rate pulls the small end down."""
    firms, _ = firm_population
    agg = firm_aggregate.aggregate(firm_runner.run(firms, 2026).firms)
    rates = {row.taille: row.mean_effective_rate for row in agg.by_size}
    assert rates["micro"] < rates["PME"] < rates["ETI"] < rates["GE"]


def test_zero_is_share_is_reported(firm_population: tuple[pl.DataFrame, object]) -> None:
    """The scalar that decides whether the IS line means anything at all (§3.3)."""
    firms, _ = firm_population
    agg = firm_aggregate.aggregate(firm_runner.run(firms, 2026).firms)
    assert 0.20 < agg.share_zero_is < 0.50


def test_a_reform_moves_the_incidence_table(
    firm_population: tuple[pl.DataFrame, object],
) -> None:
    firms, _ = firm_population
    result = firm_runner.run(firms, 2026, reform=FirmReformSpec(is_taux_normal=0.28))
    agg = firm_aggregate.aggregate(result.firms)
    assert agg.deltas["impot_societes"] > 0
    assert agg.reform_cost is not None and agg.reform_cost < 0, "a rate rise raises money"
    # A rise in the normal rate cannot touch a firm whose whole profit sits in the
    # reduced-rate slice, so the smallest cells must move least.
    by_size = {row.taille: row for row in agg.cells if row.naf_section == "C"}
    assert abs(by_size["micro"].mean_delta or 0) < abs(by_size["GE"].mean_delta or 0)


def test_c3s_reform_reaches_loss_makers(
    firm_population: tuple[pl.DataFrame, object],
) -> None:
    """C3S is charged on turnover, so raising it touches firms that pay no IS at
    all — the incidence a profit-tax reform cannot reproduce."""
    firms, _ = firm_population
    result = firm_runner.run(firms, 2026, reform=FirmReformSpec(c3s_taux=0.0032))
    agg = firm_aggregate.aggregate(result.firms)
    assert agg.deltas["c3s"] > 0
    assert agg.deltas["impot_societes"] == 0.0, "a turnover tax does not move profit tax"


# --------------------------------------------------------------------------- #
# CVAE (CGI art. 1586 ter à septies)
# --------------------------------------------------------------------------- #
#: The three worked examples DGFiP publishes for the 2026 millésime (BOFiP
#: BOI-CVAE-LIQ-10 n° 65 and notice 1329-AC). They pin the schedule AND the
#: rounding rule at once, which is why they are the first thing tested.
CVAE_CONTROL_POINTS = ((2_700_000.0, 0.0008), (6_200_000.0, 0.0017), (40_100_000.0, 0.0028))


def implied_cvae_rate(simulation: object, index: int, turnover: float, va: float) -> float:
    """Back out the rate the engine applied, from the euros it charged."""
    cvae = float(simulation.calculate("cvae", YEAR)[index])  # type: ignore[attr-defined]
    degrevement = 188.0 if turnover <= 2_000_000 else 0.0
    return (cvae + degrevement) / va


@pytest.mark.parametrize(("turnover", "expected_rate"), CVAE_CONTROL_POINTS)
def test_cvae_matches_the_published_worked_examples(
    tbs: object, turnover: float, expected_rate: float
) -> None:
    """DGFiP's own examples. A schedule that misses these is wrong regardless of how
    convincingly it is derived."""
    va = 0.30 * turnover
    simulation = simulate(tbs, [turnover], [0.05 * turnover], [va])
    assert close(implied_cvae_rate(simulation, 0, turnover, va), expected_rate)


def test_cvae_rate_is_rounded_to_the_hundredth_of_a_point(tbs: object) -> None:
    """The rounding is not cosmetic. Unrounded, a CA of 2.7 M€ gives 0.08272 %; the
    statute rounds it to 0.08 %, which is 3.3 % less tax. Dropping the rule turns the
    schedule into a continuous function and biases the bottom of it by several
    percent — the CVAE analogue of the barème-collapse defect (D-007)."""
    turnover, va = 2_700_000.0, 810_000.0
    unrounded = 0.00094 * (turnover - 500_000) / 2_500_000
    assert unrounded == pytest.approx(0.0008272), "the unrounded rate must differ"
    simulation = simulate(tbs, [turnover], [0.0], [va])
    applied = implied_cvae_rate(simulation, 0, turnover, va)
    assert close(applied, 0.0008)
    assert not close(applied, unrounded)


def test_cvae_is_nil_below_the_rate_threshold_not_the_scope_threshold(tbs: object) -> None:
    """Two thresholds that are constantly conflated: 152 500 € puts a firm in scope
    and on the filing hook, but the rate is nil until 500 000 €. Using the scope
    threshold as the payment threshold would charge some 350 000 firms that owe
    nothing."""
    turnovers = [140_000.0, 300_000.0, 499_999.0, 600_000.0]
    simulation = simulate(tbs, turnovers, [0.0] * 4, [0.3 * t for t in turnovers])
    cvae = simulation.calculate("cvae", YEAR)  # type: ignore[attr-defined]
    assert list(cvae[:3]) == [0.0, 0.0, 0.0]
    assert cvae[3] == 0.0, "at 600 k€ the rate is tiny and the franchise still absorbs it"


def test_cvae_franchise_is_owed_from_64_euros_not_63(tbs: object) -> None:
    """Since 2024 there is no minimum contribution, only a franchise: 'si le montant
    est inférieur ou égal à 63 €, la CVAE n'est pas due'. Strictly greater, so the
    first euro owed is the 64th."""
    p = tbs.parameters(f"{YEAR}-01-01")  # type: ignore[attr-defined]
    assert p.cvae.franchise == 63

    # A firm engineered to land either side of the franchise by moving its VA alone.
    # Note the rate used to size it: 0.09 %, the rounded one the engine applies — not
    # the 0.094 % the formula produces before rounding. Sizing this with the unrounded
    # rate puts both firms under the franchise and the test passes for the wrong
    # reason, which is what it did on the first attempt.
    turnover = 3_000_000.0  # top of the first bracket, no dégrèvement above 2 M€
    rate = 0.0009
    just_under = [(63.0 / rate)]
    just_over = [(64.5 / rate)]
    under = simulate(tbs, [turnover], [0.0], just_under)
    over = simulate(tbs, [turnover], [0.0], just_over)
    assert under.calculate("cvae", YEAR)[0] == 0.0  # type: ignore[attr-defined]
    assert over.calculate("cvae", YEAR)[0] > 63.0  # type: ignore[attr-defined]


def test_cvae_value_added_is_capped_as_a_share_of_turnover(tbs: object) -> None:
    """80 % below 7.6 M€ of turnover and 85 % above. It bites only on labour-heavy
    firms, but when it bites it sets the assiette outright."""
    turnover = 5_000_000.0
    uncapped = simulate(tbs, [turnover], [0.0], [4_500_000.0])
    at_cap = simulate(tbs, [turnover], [0.0], [4_000_000.0])
    assert uncapped.calculate("cvae", YEAR)[0] == pytest.approx(  # type: ignore[attr-defined]
        at_cap.calculate("cvae", YEAR)[0]  # type: ignore[attr-defined]
    ), "VA above 80 % of CA must be cut back to the cap, so both firms pay the same"


def test_cvae_is_abolished_from_2030(tbs: object) -> None:
    """The LF 2025 trajectory ends in abrogation, last imposition due for 2029. The
    parameters go null and the formula must return zero rather than raise."""
    simulation = simulate(tbs, [40_000_000.0], [1_000_000.0], [12_000_000.0], year="2030")
    assert simulation.calculate("cvae", "2030")[0] == 0.0  # type: ignore[attr-defined]


def test_cvae_rate_rose_in_2026_rather_than_falling(tbs: object) -> None:
    """The counter-intuitive fact worth pinning: LF 2025 deferred the phase-out by
    three years, so the maximum rate goes back UP from 0.19 % in 2025 to 0.28 % in
    2026. A reader assuming a monotone phase-out would code the wrong number."""
    p = tbs.parameters  # type: ignore[attr-defined]
    assert p("2025-01-01").cvae.taux_max == pytest.approx(0.0019)
    assert p("2026-01-01").cvae.taux_max == pytest.approx(0.0028)
    assert p("2029-01-01").cvae.taux_max == pytest.approx(0.0009)


# --------------------------------------------------------------------------- #
# CEBGE (LF 2025 art. 48, prorogé par LF 2026 art. 12)
# --------------------------------------------------------------------------- #
def cebge_rate(simulation: object, index: int, year: str = YEAR) -> float:
    """The rate the engine applied, backed out of the euros charged."""
    cebge = float(simulation.calculate("cebge", year)[index])  # type: ignore[attr-defined]
    assiette = float(simulation.calculate("impot_societes", year)[index])  # type: ignore[attr-defined]
    return cebge / assiette


def test_cebge_smoothing_reproduces_the_published_example(tbs: object) -> None:
    """BOFiP BOI-IS-AUT-60 § 270: turnover of 1.045 bn in the first exercice gives a
    rate of 9.27 %, not 20.6 %. Without the smoothing band a firm at 1.50 bn would pay
    in full what a firm at 1.49 bn does not pay at all."""
    simulation = simulate(tbs, [1_045_000_000.0], [40_000_000.0], year="2025")
    assert close(cebge_rate(simulation, 0, "2025"), 0.0927)


def test_cebge_interpolates_between_the_two_rates_above_3bn(tbs: object) -> None:
    """BOFiP § 290: at 3.08 bn the rate is 20.6 + (41.2 - 20.6) x 0.8 = 37.08 %. This
    band interpolates between two rates rather than ramping from zero, and coding it
    like the lower band would charge 16.48 points too little."""
    simulation = simulate(tbs, [3_080_000_000.0], [100_000_000.0])
    assert close(cebge_rate(simulation, 0), 0.3708)


def test_cebge_thresholds_and_rates_by_turnover(tbs: object) -> None:
    """The whole 2026 profile in one pass, including both ends."""
    turnovers = [1_400_000_000.0, 1_600_000_000.0, 2_000_000_000.0, 3_500_000_000.0]
    simulation = simulate(tbs, turnovers, [100_000_000.0] * 4)
    rates = [cebge_rate(simulation, i) for i in range(4)]
    assert rates[0] == 0.0, "below 1.5 bn the second exercice is not liable at all"
    assert close(rates[1], 0.206), "at the top of the band, the full lower rate"
    assert close(rates[2], 0.206)
    assert close(rates[3], 0.412), "above 3.1 bn, the higher rate in full"


def test_cebge_base_is_the_two_year_average_of_is(tbs: object) -> None:
    """The base is the mean of this exercice's IS and the previous one's, so a firm
    whose profit halved still pays on the average. Absent a prior year the model
    assumes stationarity — which the formula on `is_avant_report` makes explicit
    rather than defaulting the term to zero and silently halving every base."""
    turnover = 2_000_000_000.0
    stationary = simulate(tbs, [turnover], [100_000_000.0])
    assert close(cebge_rate(stationary, 0), 0.206), "stationarity: average == this year"

    builder = SimulationBuilder()
    builder.create_entities(tbs)
    builder.declare_person_entity("entreprise", np.arange(1))
    given_history = builder.build(tbs)
    given_history.set_input("chiffre_affaires", YEAR, np.array([turnover]))
    given_history.set_input("benefice_imposable", YEAR, np.array([100_000_000.0]))
    given_history.set_input("is_avant_report", YEAR, np.array([0.0]))
    charged = float(given_history.calculate("cebge", YEAR)[0])
    this_year_is = float(given_history.calculate("impot_societes", YEAR)[0])
    assert close(charged, 0.5 * this_year_is * 0.206), (
        "a supplied prior-year IS of zero must halve the base, not be ignored"
    )


def test_cebge_lapses_after_the_second_exercice(tbs: object) -> None:
    """Self-limiting by exercice count: the two first exercices closed on or after
    31 December 2025, which for a calendar filer is FY2025 and FY2026."""
    simulation = simulate(tbs, [5_000_000_000.0], [500_000_000.0], year="2027")
    assert simulation.calculate("cebge", "2027")[0] == 0.0  # type: ignore[attr-defined]


def test_cebge_reform_moves_its_smoothing_band_with_its_threshold(tbs: object) -> None:
    """The paired knob's real job. A reform that moved the threshold but left the
    100 M€ ramp where it was would tax firms at a rate nobody asked for — either a
    cliff or a band running backwards."""
    spec = FirmReformSpec(cebge_seuils_et_taux=[{"seuil_ca": 500_000_000, "taux": 0.30}])
    reformed = firm_system.reformed_for(spec, 2026)
    p = reformed.parameters(f"{YEAR}-01-01")
    assert p.cebge.seuil_ca == 500_000_000
    assert p.cebge.taux_base == pytest.approx(0.30)
    assert p.cebge.lissage.borne_haute == 600_000_000, "band must follow the threshold"
    verify_scales(reformed, spec, 2026)


def test_cebge_knob_refuses_more_tranches_than_the_statute_has(tbs: object) -> None:
    with pytest.raises(ValueError, match=r"at most 2 items after validation, not 3"):
        FirmReformSpec(cebge_seuils_et_taux=[
            {"seuil_ca": 1e9, "taux": 0.2}, {"seuil_ca": 3e9, "taux": 0.4},
            {"seuil_ca": 5e9, "taux": 0.5},
        ])


# --------------------------------------------------------------------------- #
# the reconciliation report (§5)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def firm_aggregates() -> object:
    from impots.entreprises.build import FIXTURE_CELLS, load_cells

    cells, ratio, _ = load_cells(FIXTURE_CELLS)
    firms, _ = build_firms(cells, fiscal_to_accounting=ratio)
    return firm_aggregate.aggregate(firm_runner.run(firms, 2026).firms)


def test_every_published_figure_carries_a_source_and_a_url() -> None:
    """Nothing downstream may hardcode a statistic. A figure without a citation is
    indistinguishable from one somebody remembered."""
    from impots.entreprises import margins

    for use in ("calibration", "validation", "context"):
        for name, figure in margins.figures_by_use(use).items():
            assert figure.source, f"{name} has no source"
            assert figure.url.startswith("http"), f"{name} has no usable url"
            assert figure.scope, f"{name} does not say what it counts"


def test_a_calibration_target_is_never_printed_as_validation(firm_aggregates: object) -> None:
    """The rule the whole report rests on. `Line.from_figure` takes `use` from the
    figure, so a spent margin cannot be re-tagged at the point of display — which is
    exactly what happened to the household ménage count before raking existed."""
    from impots.entreprises import margins, reconcile

    spent = {figure.value for figure in margins.figures_by_use("calibration").values()}
    for line in reconcile.build_lines(firm_aggregates, 2026):
        if line.published in spent:
            assert line.use == "calibration", (
                f"{line.label} compares against a calibration target but is tagged "
                f"{line.use!r}"
            )


def test_the_report_leads_with_the_synthetic_cell_warning(firm_aggregates: object) -> None:
    """The fixture cells are invented. A tidy residual table with no warning invites
    exactly the wrong conclusion, so the warning goes above the table, not in a
    footnote."""
    from impots.entreprises import reconcile

    report = reconcile.render(firm_aggregates, "fixture", 2026, cells_are_synthetic=True)
    assert "These residuals mean nothing" in report
    assert report.index("These residuals mean nothing") < report.index("| Line |")

    real = reconcile.render(firm_aggregates, "2024", 2026, cells_are_synthetic=False)
    assert "These residuals mean nothing" not in real


def test_the_report_names_the_ratio_that_dominates_it(firm_aggregates: object) -> None:
    """§3.3 requires the fiscal-to-accounting ratio in the method notes: it is one
    scalar and it moves the IS line more than anything else in the model."""
    from impots.entreprises import reconcile

    report = reconcile.render(
        firm_aggregates, "fixture", 2026, fiscal_to_accounting=0.82
    )
    assert "0.820" in report
    assert "No loss carry-forward" in report
    assert "No CFE" in report


def test_the_effective_rate_gap_is_context_and_expected_to_disagree(
    firm_aggregates: object,
) -> None:
    """The two published effective-rate series order firm sizes in opposite
    directions because they measure different objects. The model resembles neither,
    so this line is context — tagging it validation would let the report claim credit
    for whichever series it happened to match."""
    from impots.entreprises import reconcile

    lines = {line.label: line for line in reconcile.build_lines(firm_aggregates, 2026)}
    gap = lines["Écart de taux effectif GE − PME"]
    assert gap.use == "context"
    assert gap.published < 0, "INSEE's implicit rate falls with size"
    assert gap.simulated > 0, "the model's rises with size, because turnover taxes bite"


def test_the_ship_gate_line_is_the_national_accounts_figure(firm_aggregates: object) -> None:
    """Which published IS number the model is judged against is most of the work. It
    computes IS before any crédit d'impôt, so the comparator is the national-accounts
    'avant crédits' line — not the net budget receipts, which are shown alongside and
    are missed high by construction."""
    from impots.entreprises import margins, reconcile

    lines = {line.label: line for line in reconcile.build_lines(firm_aggregates, 2026)}
    assert lines["Impôt sur les sociétés"].published == margins.IS_AVANT_CREDITS.value
    assert lines["Impôt sur les sociétés"].tolerance == 0.20
    assert lines["IS — recettes nettes (pour mémoire)"].use == "context"
