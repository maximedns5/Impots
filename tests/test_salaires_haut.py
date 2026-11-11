"""The top of the wage draw meets the published centiles (but 19, étape « haut »).

A synthetic frame, without the population: employees of the four PCS, of every age band
and both sexes, in the private sector and the three versants, beside inactive people and
children, as in the survey. Before the étape, the Pareto tail was spliced on the 5 % of
rows above an unweighted cut, so the inactive rows moved it, and the fonction publique
took the private sector's shape.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from impots.population import incomes, margins


def _weighted_quantile(values: np.ndarray, weight: np.ndarray, p: float) -> float:
    order = np.argsort(values)
    cumulative = np.cumsum(weight[order]) / weight.sum()
    return float(values[order][np.searchsorted(cumulative, p)])


@pytest.fixture(scope="module")
def frame() -> pl.DataFrame:
    rng = np.random.default_rng(11)
    n = 120_000
    employed = rng.uniform(size=n) < 0.6
    pick = rng.choice(4, p=[0.10, 0.08, 0.05, 0.77], size=n)
    versant = [("etat", "territoriale", "hospitaliere", None)[k] if e else None
               for k, e in zip(pick, employed, strict=True)]
    pcs = rng.choice(["cadre", "profession_intermediaire", "employe", "ouvrier"], size=n)
    return pl.DataFrame({
        "pcs": [str(c) if e else None for c, e in zip(pcs, employed, strict=True)],
        "sex": rng.choice(["female", "male"], size=n),
        "age": np.where(employed, rng.integers(18, 65, size=n), rng.integers(0, 90, size=n)),
        "is_salarie": employed,
        "statut_activite": np.where(employed, "employed", "inactive"),
        "weight": rng.uniform(100.0, 400.0, size=n),
        "fonction_publique": versant,
    }, schema_overrides={"fonction_publique": pl.String, "pcs": pl.String})


@pytest.fixture(scope="module")
def draws(frame: pl.DataFrame) -> np.ndarray:
    return incomes._draw_net_eqtp(frame, np.random.default_rng(incomes.SEED))


def _group(frame: pl.DataFrame, versant: str | None) -> np.ndarray:
    employee = frame["is_salarie"].to_numpy()
    fp = frame["fonction_publique"].to_numpy()
    return employee & (np.array([v is None for v in fp]) if versant is None else fp == versant)


@pytest.mark.parametrize("p", [0.5, 0.8, 0.9, 0.95, 0.97, 0.99])
def test_the_private_upper_half_is_the_published_centiles(frame, draws, p) -> None:
    """IP n° 2079, tableau complémentaire 3. The old draw put P95 10 % and P99 8 % high."""
    mine = _group(frame, None)
    got = _weighted_quantile(draws[mine], frame["weight"].to_numpy()[mine], p)
    assert got == pytest.approx(margins.WAGE_CENTILES_PRIVATE_NET_EQTP_MONTHLY[p], rel=0.015)


@pytest.mark.parametrize("versant", ["etat", "territoriale", "hospitaliere"])
def test_the_fonction_publique_has_its_own_upper_half(frame, draws, versant) -> None:
    """Siasp 2024 : D1, Q1, median, Q3 and D9 of each versant, not the private shape."""
    mine = _group(frame, versant)
    weight = frame["weight"].to_numpy()[mine]
    for p, published in margins.WAGE_QUANTILES_FP_NET_EQTP_MONTHLY[versant].items():
        got = _weighted_quantile(draws[mine], weight, p)
        assert got == pytest.approx(published, rel=0.015)


def test_the_private_means_by_age_and_sex_are_the_published_ones(frame, draws) -> None:
    """ECRT 2026, fiche 2.6, figure 3, relative to the private mean (the frame's mix of
    ages is not the survey's). The old draw had no gradient after 25."""
    mine = _group(frame, None)
    weight = frame["weight"].to_numpy()
    age = frame["age"].to_numpy()
    female = frame["sex"].to_numpy() == "female"
    got, published, mass = [], [], []
    for low, high, women, men in margins.WAGE_MEAN_NET_EQTP_BY_AGE_SEX:
        band = mine & (age >= low) & (age < high)
        for cell, mean in ((band & female, women), (band & ~female, men)):
            got.append(float((draws * weight)[cell].sum() / weight[cell].sum()))
            published.append(mean)
            mass.append(float(weight[cell].sum()))
    got, published, mass = np.array(got), np.array(published), np.array(mass)
    level = (got * mass).sum() / (published * mass).sum()
    assert got / level == pytest.approx(published, rel=0.005)


def test_variant_a_keeps_the_drawn_lower_half(frame, monkeypatch) -> None:
    """Variant (a): below the median the draw is only scaled, so its D1 is the drawn one
    and not the published one; nobody in the lower half is above the published median."""
    monkeypatch.setattr(incomes, "WHOLE_DISTRIBUTION", False)
    draws = incomes._draw_net_eqtp(frame, np.random.default_rng(incomes.SEED))
    mine = _group(frame, None)
    weight = frame["weight"].to_numpy()[mine]
    low = draws[mine] < margins.WAGE_CENTILES_PRIVATE_NET_EQTP_MONTHLY[0.5]
    assert weight[low].sum() / weight.sum() == pytest.approx(0.5, abs=0.01)
    d1 = _weighted_quantile(draws[mine], weight, 0.1)
    assert abs(d1 / margins.WAGE_CENTILES_PRIVATE_NET_EQTP_MONTHLY[0.1] - 1) > 0.02


@pytest.mark.parametrize("p", [0.05, 0.1, 0.25, 0.4])
def test_the_whole_distribution_is_read_on_the_published_centiles(frame, draws, p) -> None:
    """Variant (d), the default: the lower half too is read on the published curve."""
    mine = _group(frame, None)
    got = _weighted_quantile(draws[mine], frame["weight"].to_numpy()[mine], p)
    assert got == pytest.approx(margins.WAGE_CENTILES_PRIVATE_NET_EQTP_MONTHLY[p], rel=0.015)


@pytest.fixture(scope="module")
def part_time(frame: pl.DataFrame) -> pl.DataFrame:
    """The frame, with the part-time where the survey has them: among the employés, low
    in the draw (three in five of them at 40 %), and nowhere else."""
    rng = np.random.default_rng(12)
    employe = (frame["pcs"] == "employe").fill_null(False).to_numpy()
    quotite = np.where(employe & (rng.uniform(size=frame.height) < 0.6), 0.4, 1.0)
    return frame.with_columns(pl.Series("quotite_travail", quotite))


@pytest.mark.parametrize("p", [0.25, 0.5, 0.8])
def test_the_published_quantiles_are_held_in_eqtp(part_time, p) -> None:
    """IP n° 2079 counts « salariés en EQTP » : a poste at 40 % is 0,4 of one. Ranked by
    head, the part-time take more of the curve than they hold, and every full-time employee
    above them is read higher : the quantiles of the employees weighted by their EQTP come
    out above the published ones. Fails on the code before (rank by head, `RANG_EQTP`
    off) : the EQTP quartile 1,4 % and median 2,7 % high (but 19, étape « milieu »)."""
    draws = incomes._draw_net_eqtp(part_time, np.random.default_rng(incomes.SEED))
    mine = _group(part_time, None)
    eqtp = (part_time["weight"] * part_time["quotite_travail"]).to_numpy()[mine]
    got = _weighted_quantile(draws[mine], eqtp, p)
    assert got == pytest.approx(margins.WAGE_CENTILES_PRIVATE_NET_EQTP_MONTHLY[p], rel=0.01)
