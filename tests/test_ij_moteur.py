"""Les IJ dans l'impôt et la CSG (corrections 22 et 23, D-306), et leurs deux boutons.

openfisca n'impose aucune indemnité journalière et ne lève pas la CSG qu'il porte pour
elles. Les corrections font entrer dans les salaires les IJ maladie et la part des IJ AT-MP
que l'exonération laisse, nettes de leur CSG déductible ; elles lèvent la CSG des IJ et
mettent les IJ nettes dans le revenu disponible. Les tests tournent sur des ménages de la
population, leurs IJ imputées (D-305), avec et sans elles.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from impots.api.schemas import ReformSpec
from impots.engine import corrections
from impots.engine.system import baseline, reformed_for, uncorrected_baseline
from impots.population import ij, runner
from impots.population.cli import PROCESSED
from impots.population.to_openfisca import build_simulation

YEAR = 2024


@pytest.fixture(scope="module")
def frames() -> tuple[pl.DataFrame, pl.DataFrame]:
    population = pl.read_parquet(PROCESSED / "population_2024.parquet").sort("person_id")
    with_ij = runner.subsample(ij.impute(population), 40).sort("person_id")
    return with_ij, with_ij.drop("ij_maladie_annuel", "ij_atmp_annuel")


def _calc(frame: pl.DataFrame, system, variable: str, **kwargs) -> np.ndarray:
    built = build_simulation(frame, system, YEAR)
    return np.asarray(built.calculate(variable, **kwargs), dtype=np.float64)


def _sick_pay(frame: pl.DataFrame) -> float:
    return float(frame["ij_maladie_annuel"].sum() + frame["ij_atmp_annuel"].sum())


# --- ce qu'openfisca ne fait pas : les tests qui tueront les corrections ---------------


def test_openfisca_taxes_no_sick_pay(frames) -> None:
    """The day openfisca taxes the allowances, correction 22 must go (D-306)."""
    with_ij, without = frames
    system = uncorrected_baseline()
    assert np.array_equal(_calc(with_ij, system, "revenu_categoriel_tspr"),
                          _calc(without, system, "revenu_categoriel_tspr"))


def test_openfisca_levies_no_csg_on_sick_pay(frames) -> None:
    """…and the day it levies their CSG, correction 23 must go."""
    with_ij, without = frames
    system = uncorrected_baseline()
    assert corrections.CSG_IJ not in system.variables
    assert np.array_equal(_calc(with_ij, system, "pensions_nettes"),
                          _calc(without, system, "pensions_nettes"))


def test_openfisca_does_not_carry_the_exempt_share() -> None:
    parameters = uncorrected_baseline().parameters
    assert "indemnites_journalieres" not in parameters.impot_revenu.children


# --- correction 22 : les IJ dans les salaires -------------------------------------------


def test_the_taxable_sick_pay_joins_the_salaries(frames) -> None:
    """A foyer of one earner between the deduction's floor and ceiling gains 90 % of its
    taxable allowances: the sickness ones and half the work-accident ones, net of 3,8 %."""
    with_ij, without = frames
    gained = (_calc(with_ij, baseline(), "revenu_categoriel_tspr")
              - _calc(without, baseline(), "revenu_categoriel_tspr"))
    members = with_ij.group_by("foyer_id").agg(
        pl.len().alias("n"), pl.col("salaire_brut_annuel").sum().alias("salaire"),
        pl.col("ij_maladie_annuel").sum().alias("m"),
        pl.col("ij_atmp_annuel").sum().alias("a")).sort("foyer_id")
    plain = ((members["n"] == 1) & (members["salaire"] > 20_000)
             & (members["salaire"] < 80_000)).to_numpy()
    assert plain.sum() >= 3
    taxable = (1 - 0.038) * (members["m"].to_numpy() + 0.5 * members["a"].to_numpy())
    assert gained[plain] == pytest.approx(0.9 * taxable[plain], rel=2e-3, abs=2.0)
    assert (gained >= -0.5).all() and gained.sum() > 0


def test_without_sick_pay_the_salaries_are_openfisca_s(frames) -> None:
    _, without = frames
    assert np.allclose(_calc(without, baseline(), "revenu_categoriel_tspr"),
                       _calc(without, uncorrected_baseline(), "revenu_categoriel_tspr"))


def test_the_exempt_share_is_in_the_tree_from_2010() -> None:
    parameters = baseline().parameters
    path = corrections.PATH_IJ_AT_MP_EXONEREE
    assert parameters(f"{YEAR}-01-01").impot_revenu.indemnites_journalieres \
        .part_exoneree_at_mp == 0.5
    assert path == ("impot_revenu", "indemnites_journalieres", "part_exoneree_at_mp")


def test_the_exempt_share_keeps_the_inaptitude_age() -> None:
    """openfisca's `modify_parameters` starts again from the baseline's tree each call: a
    second call would undo correction 6's age of 62 (D-185). The tree carries both."""
    parameters = baseline().parameters(f"{YEAR}-01-01")
    assert parameters.prestations_sociales.prestations_etat_de_sante.invalidite.aah \
        .age_legal_retraite == corrections.AGE_INAPTITUDE
    assert parameters.impot_revenu.indemnites_journalieres.part_exoneree_at_mp == 0.5


def test_a_node_openfisca_grew_is_refused() -> None:
    parameters = uncorrected_baseline().parameters.clone()
    corrections._at_mp_exempt_share(parameters)
    with pytest.raises(RuntimeError, match="read again"):
        corrections._at_mp_exempt_share(parameters)


# --- correction 23 : la CSG des IJ, et les IJ dans le revenu disponible ---------------


def test_the_csg_is_six_point_two_percent_of_the_month_s_sick_pay(frames) -> None:
    with_ij, _ = frames
    levied = _calc(with_ij, baseline(), corrections.CSG_IJ, month=3)
    # openfisca computes in float32: six digits are what a sum of its arrays holds.
    assert levied.sum() == pytest.approx(-0.062 * _sick_pay(with_ij) / 12, rel=1e-5)


def test_the_net_sick_pay_is_among_the_replacement_incomes(frames) -> None:
    """The allowances net of their CSG, in `pensions_nettes` and so in the disposable
    income. That income moves by more than this: the allowances bear an income tax now,
    and openfisca already counted them in the RSA's and the prime's resources."""
    with_ij, without = frames
    gained = (_calc(with_ij, baseline(), "pensions_nettes").sum()
              - _calc(without, baseline(), "pensions_nettes").sum())
    assert gained == pytest.approx((1 - 0.062) * _sick_pay(with_ij), rel=1e-5)
    tax = (_calc(with_ij, baseline(), "impot_revenu_restant_a_payer").sum()
           - _calc(without, baseline(), "impot_revenu_restant_a_payer").sum())
    assert tax < 0


# --- les deux boutons -------------------------------------------------------------------


def test_taxing_all_the_work_accident_allowances_raises_the_income_tax(frames) -> None:
    with_ij, without = frames
    reform = reformed_for(ReformSpec(ij_at_mp_part_exoneree=0.0), YEAR)
    for frame, moves in ((with_ij, True), (without, False)):
        before = _calc(frame, baseline(), "impot_revenu_restant_a_payer").sum()
        after = _calc(frame, reform, "impot_revenu_restant_a_payer").sum()
        cost = (_calc(frame, reform, "revenu_disponible").sum()
                - _calc(frame, baseline(), "revenu_disponible").sum())
        assert bool(after < before) is moves
        assert cost == pytest.approx(after - before, rel=1e-5, abs=1.0)


def test_the_csg_rate_takes_three_points_of_the_sick_pay(frames) -> None:
    with_ij, without = frames
    reform = reformed_for(ReformSpec(csg_ij_taux=0.092), YEAR)
    cost = (_calc(with_ij, reform, "revenu_disponible").sum()
            - _calc(with_ij, baseline(), "revenu_disponible").sum())
    # Two float32 disposable incomes differenced: a few cents over 40 households.
    assert cost == pytest.approx(-0.03 * _sick_pay(with_ij), abs=0.05)
    assert (_calc(without, reform, "revenu_disponible").sum()
            == pytest.approx(_calc(without, baseline(), "revenu_disponible").sum()))


@pytest.mark.parametrize("knob, value", [("ij_at_mp_part_exoneree", 0.25),
                                         ("csg_ij_taux", 0.08)])
def test_each_knob_is_read_back_from_the_tree(knob, value) -> None:
    from impots.engine.reforms import SCALAR_KNOBS
    from impots.parameters import resolve

    tree = reformed_for(ReformSpec(**{knob: value}), YEAR).parameters
    assert float(resolve(tree, SCALAR_KNOBS[knob])(f"{YEAR}-07-01")) == pytest.approx(value)


# --- la CSG des IJ dans le registre des recettes (D-307) -------------------------------


def test_the_csg_on_sick_pay_is_a_row_an_instrument_and_a_receipt() -> None:
    """GUARD (D-307). The first pass of the CSG case was refused by the ledger: the cost
    by disposable income was a yield of 467,7 M€, and no instrument held it."""
    from impots import guards
    from impots.engine.outputs import REGISTRY
    from impots.macro import shocks
    from impots.population import aggregate

    row = next(r for r in REGISTRY if r.key == "csg_ij")
    assert row.variable == corrections.CSG_IJ and row.entity == "individu" and row.negate
    assert "csg_ij" in aggregate.INSTRUMENTS and "csg_ij" in guards.STATE_RECEIPTS
    assert shocks.INSTRUMENT_MAP["csg_ij"] == shocks.INSTRUMENT_MAP["csg_deductible"]
    guards.sector_balance({"csg_ij": 467.7e6}, reform_cost=-467.7e6)


def test_a_pass_that_raises_the_csg_on_sick_pay_balances_its_ledger(frames) -> None:
    from impots.population import aggregate

    with_ij, _ = frames
    result = runner.run(with_ij, year=YEAR, reform=ReformSpec(csg_ij_taux=0.092),
                        tier="full")
    agg = aggregate.aggregate(result.households)
    assert agg.reform_cost < 0
    assert agg.deltas["csg_ij"] == pytest.approx(-agg.reform_cost, rel=1e-3)
