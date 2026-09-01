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


def simulate(system: object, chiffre_affaires: list[float], benefice: list[float]) -> object:
    builder = SimulationBuilder()
    builder.create_entities(system)
    builder.declare_person_entity("entreprise", np.arange(len(chiffre_affaires)))
    simulation = builder.build(system)
    simulation.set_input("chiffre_affaires", YEAR, np.array(chiffre_affaires, dtype=np.float64))
    simulation.set_input("benefice_imposable", YEAR, np.array(benefice, dtype=np.float64))
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
    assert p.impot_societes.taux_normal("2021-01-01") == pytest.approx(0.265)
    assert p.impot_societes.plafond_taux_reduit("2022-01-01") == 38_120
    assert p.impot_societes.plafond_taux_reduit("2026-01-01") == 42_500


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
