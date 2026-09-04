"""The chiffrage backtest suite (PHASE3_SPEC §5).

Each case compares this simulator's **mechanical** result against the **published
mechanical** costing of a historical article. That makes the suite a test of L2 on
historical law, independent of everything the behavioural layer adds: no elasticity,
band or grade touches a case, so a behavioural bug cannot turn one green and a
mechanical bug cannot hide behind one.

A red case is a **finding**, not a number to tune away. `expect_red` keeps a
documented miss from failing CI while still printing its residual — and every case
carrying it must carry the write-up too, which is asserted below.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from impots.behavioural import chiffrages

CASES = chiffrages.load()
FIRM_POPULATION = (
    Path(__file__).resolve().parents[1] / "data" / "processed" / "firms_2023.parquet"
)


def run_case(case: chiffrages.Case) -> float:
    """The signed change in state revenue this reform produces, mechanically."""
    if case.scope == "firm":
        import polars as pl

        from impots.entreprises import aggregate as firm_aggregate
        from impots.entreprises import runner as firm_runner
        from impots.entreprises.reforms import FirmReformSpec

        result = firm_runner.run(
            pl.read_parquet(FIRM_POPULATION), year=case.year,
            reform=FirmReformSpec.model_validate(case.reform),
        )
        aggregates = firm_aggregate.aggregate(result.firms)
        # `reform_cost` is positive when the reform costs the state; the suite works
        # in revenue, so the sign is flipped once, here.
        return -(aggregates.reform_cost or 0.0)

    import polars as pl

    from impots.api.schemas import ReformSpec
    from impots.population import aggregate as aggregate_module
    from impots.population.build import PROCESSED
    from impots.population.runner import run as population_run

    frame = pl.read_parquet(PROCESSED / "population_2024.parquet")
    result = population_run(
        frame, year=case.year, reform=ReformSpec.model_validate(case.reform),
        tier=case.tier, sample=20_000,
    )
    return -(aggregate_module.aggregate(result.households).reform_cost or 0.0)


def test_the_suite_is_not_empty() -> None:
    """§5 has owed this since 2026-08-28."""
    assert CASES, "tests/chiffrages/ carries no cases"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.key)
def test_every_case_carries_enough_provenance_to_be_re_found(
    case: chiffrages.Case,
) -> None:
    """A costing that cannot be re-found is a number somebody remembered."""
    assert case.published.url.startswith("http")
    assert case.published.document
    assert case.published.quote, f"{case.key} has no verbatim quote"
    assert case.tolerance_reason, f"{case.key} declares a tolerance without a reason"
    if case.expect_red:
        assert case.caveat, (
            f"{case.key} is expected to miss and carries no write-up — a red case is "
            f"a finding, and a finding has to be written down"
        )


HOUSEHOLD_POPULATION = (
    Path(__file__).resolve().parents[1] / "data" / "processed" / "population_2024.parquet"
)


def available(case: chiffrages.Case) -> bool:
    path = FIRM_POPULATION if case.scope == "firm" else HOUSEHOLD_POPULATION
    return path.exists()


@pytest.mark.slow
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.key)
def test_case_lands_within_its_declared_tolerance(case: chiffrages.Case) -> None:
    if not available(case):
        pytest.skip(f"no {case.scope} population built in this checkout")
    simulated = run_case(case)
    residual = case.residual(simulated)
    message = (
        f"{case.key}: simulated {simulated / 1e9:+.3f} bn against published "
        f"{case.published.signed / 1e9:+.3f} bn = {residual:+.1%}, "
        f"tolerance ±{case.tolerance:.0%} ({case.bound})"
    )
    if case.expect_red:
        assert not case.passes(simulated), (
            f"{message} — this case is recorded as a known miss and now passes. "
            f"That is good news, but the write-up is stale: re-check it and drop "
            f"expect_red rather than leaving a green case labelled red."
        )
        return
    assert case.passes(simulated), message


@pytest.mark.slow
def test_the_known_misses_are_the_size_they_are_documented_to_be() -> None:
    """A red case still has to be pinned. A finding that drifts silently is not a
    finding — the write-up quotes a simulated cost a third too large, so the number
    is held there. Signed negative because the case is mirror-encoded: the model
    overshoots the article's cost in magnitude.

    **The tolerance is per case, and the reason is measured.** Household cases run on a
    deterministic 20 000-household subsample, so their residual carries the draw's noise
    as well as the model's error, and the allègements case is the one where that matters:
    the sampler fix (D-074) moved it from +1.073 to +1.219 on the subsample, while the
    same case run on the FULL population — no sampling at all — gives **+1.115**. The
    0.104 between those two is the draw, not the model, and the earlier +1.073 was the
    biased sampler.

    So this case is pinned at its sample-free value with a tolerance that covers the
    measured draw noise. The firm case does not sample and the IR case moves little, so
    both keep the tight ±0.03. The sample-free value cannot simply be used for every
    case: a full-tier reform run over 199 451 households holds two simulations at once
    and is killed for memory on this machine (SIGKILL, measured) — the baseline-only
    reconciliation run fits, a reform run does not.
    """
    for key, expected, tolerance in (
        ("c3s_abattement_lfss2016", -0.34, 0.03),
        ("ir_bareme_indexation_lfi2024", -0.104, 0.03),
        # Pinned on the full population; ±0.15 covers the 0.104 of subsample noise
        # measured between the sampled and sample-free runs of this same case.
        ("allegements_points_de_sortie_lfss2025", 1.115, 0.15),
    ):
        case = next(c for c in CASES if c.key == key)
        if not available(case):
            pytest.skip(f"no {case.scope} population built in this checkout")
        # Once, not twice: each of these is a full population run.
        simulated = run_case(case)
        residual = case.residual(simulated)
        assert residual == pytest.approx(expected, abs=tolerance), key
        assert not case.passes(simulated), f"{key}: a documented miss that no longer misses"


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.bound == "lower"] or [None], ids=lambda c: c.key if c else "none"
)
def test_a_one_sided_case_fails_when_it_exceeds_the_published_figure(
    case: chiffrages.Case | None,
) -> None:
    """Every one-sided case, not just the first. The bound has to be read in
    MAGNITUDE: for a cost the published figure is negative, so a simulated value
    further below it is a larger cost — an overshoot — while the signed residual reads
    negative and looks like an undershoot. Written on the signed residual, a one-sided
    test passes exactly the cases it should fail, which is what the barème-indexation
    case did until it was measured."""
    if case is None:
        pytest.skip("no one-sided cases in the suite")
    published = case.published.signed
    sign = -1.0 if case.mirror else 1.0
    assert not case.passes(sign * published * (1.0 + 0.5 * case.tolerance)), (
        f"{case.key}: exceeding the published figure must fail a lower bound"
    )
    assert case.passes(sign * published * (1.0 - 0.5 * case.tolerance)), (
        f"{case.key}: undershooting inside the tolerance must pass"
    )
    assert not case.passes(sign * published * (1.0 - 2.0 * case.tolerance)), (
        f"{case.key}: undershooting past the tolerance must fail"
    )
