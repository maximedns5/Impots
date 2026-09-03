"""B2 — composition, leakage, and the guard against counting propagation twice.

The identity that matters here is not arithmetic but architectural: the table supplies
SHAPE, the multiplier supplies SIZE, and anything that lets the table supply size is a
defect however correct its arithmetic. So the tests below check dimensionlessness as
carefully as they check numbers.
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.macro import io_layer, tes

pytest.importorskip("openpyxl")

HAVE_TES = (tes.RAW / "insee_TES_symetrique_A38_2023SD.xlsx").exists()
needs_tes = pytest.mark.skipif(
    not HAVE_TES, reason="data/raw/ has no INSEE input-output table"
)
pytestmark = needs_tes


@pytest.fixture(scope="module")
def table():
    return tes.load("2023SD")


@pytest.fixture(scope="module")
def jobs(table):
    return tes.employment(table.branches, table.base_year)


def _impulse(table, key):
    total = (table.final_uses[key] + table.imported_final_uses[key]).clip(min=0)
    return total / total.sum() * 1000.0


# --- the architectural guard -------------------------------------------------------


def test_a_closed_matrix_is_refused(table):
    """Kill test for `assert_type_one`: Type II must not slip in as 'more realism'."""
    coefficients = io_layer.technical_coefficients(table)
    closed = np.zeros((table.n + 1, table.n + 1))
    closed[: table.n, : table.n] = coefficients
    with pytest.raises(io_layer.IoLayerError, match="double counting"):
        io_layer.assert_type_one(closed, table)


#: Household income generated per unit of gross output, for the closure below. French
#: compensation of employees is about 1 450 bn against 5 310 bn of output, so 0.25 is a
#: conservative reading of the labour share and ignores mixed income entirely.
LABOUR_SHARE = 0.25


def test_the_type_two_round_would_more_than_double_the_answer(table):
    """The rule is not cosmetic — measure what closing the model would have added.

    The closure is deliberately crude: a uniform labour share turning output into
    household income, and observed household consumption shares turning that income
    back into demand. It is not a calibrated Type II model. What it establishes is
    that the induced round is worth MORE THAN THE ENTIRE TYPE I ANSWER at any plausible
    closure, so including it silently alongside a literature multiplier — which already
    contains it — would not be a rounding error but a doubling.
    """
    coefficients = io_layer.technical_coefficients(table)
    type_one = io_layer.leontief_inverse(coefficients).sum(axis=0).mean()

    consumption = table.final_uses["consommation_finale_menages"].clip(min=0)
    closed = np.zeros((table.n + 1, table.n + 1))
    closed[: table.n, : table.n] = coefficients
    closed[: table.n, table.n] = consumption / consumption.sum()
    closed[table.n, : table.n] = LABOUR_SHARE
    type_two = np.linalg.inv(np.eye(table.n + 1) - closed).sum(axis=0)[: table.n].mean()

    assert type_two > type_one * 2.0, (
        f"the induced round adds only {type_two / type_one - 1:.1%}; if that were true "
        f"the anti-double-counting rule would not be worth its complexity"
    )


def test_the_type_two_answer_is_also_unstable(table):
    """A second reason to refuse it: it is exquisitely sensitive to a number nobody
    measures directly. Between labour shares of 0.25 and 0.40 the closed multiplier
    nearly doubles again, so a Type II figure would carry an implied precision it does
    not have."""
    coefficients = io_layer.technical_coefficients(table)
    consumption = table.final_uses["consommation_finale_menages"].clip(min=0)

    def closed_multiplier(share):
        closed = np.zeros((table.n + 1, table.n + 1))
        closed[: table.n, : table.n] = coefficients
        closed[: table.n, table.n] = consumption / consumption.sum()
        closed[table.n, : table.n] = share
        return np.linalg.inv(np.eye(table.n + 1) - closed).sum(axis=0)[: table.n].mean()

    assert closed_multiplier(0.40) > closed_multiplier(0.25) * 1.5


def test_nothing_public_returns_a_level(table, jobs):
    """Every field of a Composition is a share, a fraction, or an intensity."""
    result = io_layer.composition(table, _impulse(table, "consommation_finale_menages"),
                                  jobs, use="consommation_finale")
    assert result.output_shares.sum() == pytest.approx(1.0)
    assert result.employment_shares.sum() == pytest.approx(1.0)
    assert 0.0 < result.leakage < 1.0
    assert 0.0 < result.domestic_share < 1.0
    # Doubling the impulse must change nothing: a share that moved with size would be
    # a level in disguise.
    doubled = io_layer.composition(table, _impulse(table, "consommation_finale_menages") * 2,
                                   jobs, use="consommation_finale")
    assert doubled.output_shares == pytest.approx(result.output_shares)
    assert doubled.leakage == pytest.approx(result.leakage)


# --- leakage, both channels --------------------------------------------------------


def test_leakage_counts_the_direct_channel(table, jobs):
    """The bug this test exists for: reading only the domestic sheet halves the answer.

    Final demand for a product is met partly by imported product bought as such. That
    channel is invisible on the domestic table, and an impulse routed entirely through
    the domestic Leontief credits French branches with output bought abroad.
    """
    result = io_layer.composition(table, _impulse(table, "consommation_finale_menages"),
                                  jobs, use="consommation_finale")
    assert result.direct_leakage > 0.05, "the direct channel is not being counted"
    assert result.leakage > result.direct_leakage, "the indirect channel is missing"
    assert 0.20 < result.leakage < 0.40


def test_capital_formation_leaks_more_than_consumption(table, jobs):
    """Equipment is imported more than services are — the split must be per-category."""
    consumption = io_layer.composition(
        table, _impulse(table, "consommation_finale_menages"), jobs, use="consommation_finale")
    capital = io_layer.composition(table, _impulse(table, "fbcf"), jobs, use="fbcf")
    assert capital.leakage > consumption.leakage


def test_the_import_split_is_per_product_not_an_average(table):
    share = io_layer.import_share_of_final_use(table, "consommation_finale")
    assert share.min() == 0.0 and share.max() > 0.3
    assert ((share >= 0) & (share <= 1)).all()


def test_an_unknown_final_use_category_raises(table):
    with pytest.raises(io_layer.IoLayerError, match="unknown final-use"):
        io_layer.import_share_of_final_use(table, "consommation_des_martiens")


# --- composition is actually shaped by the impulse ---------------------------------


def test_the_composition_follows_the_impulse(table, jobs):
    """A construction impulse and a consumption impulse must not look alike."""
    consumption = io_layer.composition(
        table, _impulse(table, "consommation_finale_menages"), jobs, use="consommation_finale")
    capital = io_layer.composition(table, _impulse(table, "fbcf"), jobs, use="fbcf")
    branches = list(table.branches)
    assert capital.output_shares[branches.index("FZ")] > 0.25, "construction leads FBCF"
    assert consumption.output_shares[branches.index("FZ")] < 0.10
    assert consumption.output_shares[branches.index("LZ")] > 0.10, "housing leads consumption"


def test_employment_intensity_is_in_persons_not_thousands(table, jobs):
    """A coefficient of 0.005 is a factor-of-a-thousand error waiting to happen."""
    result = io_layer.composition(table, _impulse(table, "consommation_finale_menages"),
                                  jobs, use="consommation_finale")
    # The whole economy runs at 30 395 thousand persons on 5 310 bn of output, so any
    # plausible mix sits within a factor of three of 5.7 persons per million euros.
    assert 2.0 < result.persons_per_million_eur < 18.0


# --- refusals ----------------------------------------------------------------------


def test_a_mixed_sign_impulse_is_refused(table, jobs):
    demand = _impulse(table, "consommation_finale_menages")
    demand[3] = -100.0
    with pytest.raises(io_layer.IoLayerError, match="negative final-demand"):
        io_layer.composition(table, demand, jobs, use="consommation_finale")


def test_a_negligible_impulse_is_refused(table, jobs):
    with pytest.raises(io_layer.IoLayerError, match="numerical noise"):
        io_layer.composition(table, np.zeros(table.n), jobs)


def test_a_wrong_length_demand_is_refused(table, jobs):
    with pytest.raises(io_layer.IoLayerError, match="expected"):
        io_layer.composition(table, np.ones(table.n - 1) * 100, jobs)


def test_a_divergent_matrix_is_refused(table):
    runaway = io_layer.technical_coefficients(table).copy()
    np.fill_diagonal(runaway, 1.5)
    with pytest.raises(io_layer.IoLayerError, match="spectral radius"):
        io_layer.leontief_inverse(runaway)
