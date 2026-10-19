"""Effective marginal tax rates at population scale (PHASE3_SPEC §6).

OpenFisca has no marginal-rate variable — there is no `taux_marginal_imposition` —
so an EMTR is a finite difference, exactly as in Phase 0: raise gross salary by a
small step, see how much of it reaches disposable income, and keep the rest as the
rate. What changes here is the scale: one extra full-tier run over the whole
population instead of one household.

**Full tier only, and not as a technicality.** The taper of the prime d'activité and
the RSA is most of the marginal rate at low wages. A light-tier EMTR would report a
tidy distribution that is simply wrong at the bottom — where the interesting numbers
are, and where the policy argument lives.

## The step is applied to earners, and the denominator counts them

Bumping *every* individu by 100 EUR would turn people with no earnings into earners,
which is a different experiment. The step goes to individuals who already have a
salary, and the denominator is the total extra gross the household received. So this
is a household's marginal rate on an extra euro spread across its earners — not a
primary earner's rate, and not a second earner's. A household with no earnings has no
marginal rate on labour at all; it is recorded as such rather than given a zero,
because zero here would say "keeps every euro", which is a claim.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from impots.engine.system import baseline, reformed_for
from impots.identifiants import millesime
from impots.population import to_openfisca
from impots.population.runner import subsample
from impots.population.to_openfisca import build_simulation

PROCESSED = Path(__file__).resolve().parents[3] / "data" / "processed"

#: Gross-salary step, in EUR per year. Same as Phase 0, so the two are comparable.
EMTR_STEP = 100.0

#: Rates outside this are arithmetic accidents, not policy. Above 1.0 is real and
#: common in France — a euro that costs a household more than a euro happens wherever
#: two tapers overlap — so the upper bound is generous on purpose. Values outside are
#: clipped and counted, never dropped silently.
EMTR_BOUNDS = (-0.2, 1.5)


@dataclass
class EmtrResult:
    households: pl.DataFrame
    """household_id, weight, n_earners, emtr, and emtr_reform when a reform was run."""
    year: int
    timings: dict[str, float] = field(default_factory=dict)
    guards: dict[str, Any] = field(default_factory=dict)

    @property
    def with_earnings(self) -> pl.DataFrame:
        """The households an EMTR means anything for."""
        return self.households.filter(pl.col("n_earners") > 0)


def _bump(frame: pl.DataFrame, step: float) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.col("salaire_brut_annuel") > 0)
        .then(pl.col("salaire_brut_annuel") + step)
        .otherwise(pl.col("salaire_brut_annuel"))
        .alias("salaire_brut_annuel")
    )


def _disposable(frame: pl.DataFrame, system: Any, year: int) -> np.ndarray:
    return build_simulation(frame, system, year).calculate("revenu_disponible").astype(np.float64)


def _rate(
    frame: pl.DataFrame, system: Any, year: int, earners: np.ndarray, step: float,
    guards: dict[str, Any], label: str,
) -> np.ndarray:
    base = _disposable(frame, system, year)
    bumped = _disposable(_bump(frame, step), system, year)
    extra = step * earners
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = 1.0 - (bumped - base) / extra
    # A household with no earner received no extra euro; the ratio is 0/0. It has no
    # marginal rate on labour, which is not the same as a rate of zero.
    rate = np.where(earners > 0, rate, np.nan)
    guards[f"{label}_nan"] = int(np.isnan(rate[earners > 0]).sum())
    low, high = EMTR_BOUNDS
    clipped = np.clip(rate, low, high)
    guards[f"{label}_clipped"] = int(
        np.count_nonzero((rate < low) | (rate > high) & ~np.isnan(rate))
    )
    return clipped


def compute(
    population: pl.DataFrame | Path,
    year: int = 2024,
    reform: Any = None,
    sample: int | None = None,
    step: float = EMTR_STEP,
    vintage: str | None = None,
    uprating_key: str | None = None,
) -> EmtrResult:
    """Marginal rates for every household, under current law and optionally a reform.

    Two full-tier runs per law priced (base and bumped), so four when a reform is
    given. This is the expensive input to the behavioural layer and the reason the
    caller caches it. `uprating_key` is `Uprating.key()` when the population was aged,
    None when it is the vintage as built.
    """
    frame = pl.read_parquet(population) if isinstance(population, Path) else population
    if sample is not None:
        frame = subsample(frame, sample)
    frame = frame.sort("person_id")

    per_household = (
        frame.group_by("household_id")
        .agg(
            pl.col("weight").mean().alias("weight"),
            (pl.col("salaire_brut_annuel") > 0).sum().alias("n_earners"),
        )
        .sort("household_id")
    )
    earners = per_household["n_earners"].to_numpy().astype(np.float64)

    guards: dict[str, Any] = {}
    timings: dict[str, float] = {}

    # The baseline rates do not depend on the reform, so they are memoised on disk:
    # the second reform priced against the same population pays half as much. Keyed on
    # the sample size too, because a subsample is a different population — and on the
    # population wiring, because rates computed under another one are another law's
    # rates (D-176). And on the uprating, when there is one: an aged population has the
    # same rows as the vintage, so the height check below would not see it (D-226).
    started = time.perf_counter()
    aged = f"_{uprating_key}" if uprating_key is not None else ""
    cache = (
        PROCESSED
        / (f"emtr_baseline_{millesime(vintage)}_{year}_{sample or 'full'}_{int(step)}"
           f"_{to_openfisca.WIRING}{aged}.parquet")
        if vintage else None
    )
    if cache is not None and cache.exists():
        cached_rates = pl.read_parquet(cache)
        if cached_rates.height == per_household.height:
            columns = {"emtr": cached_rates["emtr"].to_numpy()}
            guards["baseline_cached"] = True
        else:  # the population moved under the cache; recompute rather than trust it
            columns = {"emtr": _rate(frame, baseline(), year, earners, step, guards,
                                     "baseline")}
    else:
        columns = {"emtr": _rate(frame, baseline(), year, earners, step, guards,
                                 "baseline")}
    if cache is not None and not cache.exists():
        PROCESSED.mkdir(parents=True, exist_ok=True)
        pl.DataFrame({"emtr": columns["emtr"]}).write_parquet(cache)
    timings["baseline_s"] = round(time.perf_counter() - started, 2)

    if reform is not None and not reform.is_empty():
        started = time.perf_counter()
        columns["emtr_reform"] = _rate(
            frame, reformed_for(reform, year), year, earners, step, guards, "reform"
        )
        timings["reform_s"] = round(time.perf_counter() - started, 2)

    households = per_household.with_columns(
        [pl.Series(name, values) for name, values in columns.items()]
    )
    guards["households_without_earnings"] = int((earners == 0).sum())
    return EmtrResult(households=households, year=year, timings=timings, guards=guards)


def weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """Weighted quantile by rank, not by value-cut.

    The value-cut version collapses when many households share a rate, which is
    exactly what happens here: everyone in the same bracket with no taper has the
    same EMTR to the last digit. Phase 1 met this on deciles of niveau de vie and
    produced an empty decile.
    """
    finite = np.isfinite(values)
    values, weights = values[finite], weights[finite]
    if not values.size:
        return float("nan")
    order = np.argsort(values, kind="stable")
    values, weights = values[order], weights[order]
    cumulative = np.cumsum(weights)
    if cumulative[-1] <= 0:
        return float("nan")
    return float(np.interp(q * cumulative[-1], cumulative, values))


def distribution(result: EmtrResult, deciles: int = 10) -> list[dict[str, float]]:
    """The EMTR distribution by decile of marginal rate — a product in its own right.

    France's marginal-rate distribution is not a smooth curve: it has a long right
    tail created by benefit tapers overlapping income tax, and the households in that
    tail are poor, not rich. That fact is the reason to publish this table.
    """
    frame = result.with_earnings
    if frame.is_empty():
        return []
    values = frame["emtr"].to_numpy()
    weights = frame["weight"].to_numpy()
    edges = [weighted_quantile(values, weights, k / deciles) for k in range(deciles + 1)]
    rows: list[dict[str, float]] = []
    for index in range(deciles):
        low, high = edges[index], edges[index + 1]
        mask = (values >= low) & (values <= high) if index == deciles - 1 else (
            (values >= low) & (values < high)
        )
        selected, selected_weights = values[mask], weights[mask]
        total = selected_weights.sum()
        rows.append({
            "decile": index + 1,
            "households": float(total),
            "emtr_median": weighted_quantile(selected, selected_weights, 0.5),
            "emtr_mean": float((selected * selected_weights).sum() / total) if total else 0.0,
        })
    return rows


def cache_key(
    vintage: str, year: int, reform: Any = None, sample: int | None = None,
    uprating_key: str | None = None,
) -> str:
    """A fingerprint of everything the rates depend on.

    The sample size is in the key because a subsample is a different population, not
    a cheaper view of the same one — omitting it would serve 3 000 households' rates
    for a request that asked for 20 000. The population wiring is in it for the same
    reason: a file written before D-176 holds rates of a wiring that no longer exists.
    So is the uprating of an aged population (D-226), and only then, so that the
    vintage's own keys do not move.
    """
    fields = {"vintage": vintage, "year": year, "sample": sample,
              "reform": None if reform is None else reform.model_dump(exclude_none=True),
              "wiring": to_openfisca.WIRING}
    if uprating_key is not None:
        fields["uprating"] = uprating_key
    payload = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


#: One distinct reform, one file. Unbounded, whoever chooses reforms over HTTP chooses
#: the disk used (D-173); the most recently used are kept.
CACHE_MAX = 64


def _make_room(vintage: str) -> None:
    """Keep at most `CACHE_MAX - 1` reform files, so the one about to be written fits.

    Only names this cache writes are touched — the 16-hex key — never a baseline file or
    anything else in data/processed. Evicting BEFORE the write is what guarantees the
    newest result survives, whatever the clock's resolution.
    """
    own = re.compile(rf"emtr_{re.escape(vintage)}_[0-9a-f]{{16}}\.parquet")
    files = sorted((p for p in PROCESSED.glob(f"emtr_{vintage}_*.parquet")
                    if own.fullmatch(p.name)), key=lambda p: p.stat().st_mtime_ns)
    for stale in files[: max(len(files) - (CACHE_MAX - 1), 0)]:
        stale.unlink(missing_ok=True)


def cached(
    population: pl.DataFrame | Path, vintage: str, year: int = 2024, reform: Any = None,
    sample: int | None = None, uprating_key: str | None = None,
) -> EmtrResult:
    """`compute`, memoised on disk. A minute and a half the first time, milliseconds
    after — which matters most for the same reform priced twice, since a user
    adjusting one knob and re-running is the normal way this tool is used.
    `uprating_key` is `Uprating.key()` when `population` was aged: the frame alone
    does not say so, and the key must."""
    vintage = millesime(vintage)
    key = cache_key(vintage, year, reform, sample, uprating_key)
    path = PROCESSED / f"emtr_{vintage}_{key}.parquet"
    if path.exists():
        path.touch()  # most recently USED, not most recently written, survives eviction
        return EmtrResult(households=pl.read_parquet(path), year=year,
                          guards={"cached": True})
    result = compute(population, year=year, reform=reform, sample=sample, vintage=vintage,
                     uprating_key=uprating_key)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    _make_room(vintage)
    result.households.write_parquet(path)
    return result
