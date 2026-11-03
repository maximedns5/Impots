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

import gc
import hashlib
import json
import os
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
from impots.population.runner import SAMPLE_SEED, subsample
from impots.population.to_openfisca import build_simulation

PROCESSED = Path(__file__).resolve().parents[3] / "data" / "processed"

#: Gross-salary step, in EUR per year. Same as Phase 0, so the two are comparable.
EMTR_STEP = 100.0

#: Rates outside this are arithmetic accidents, not policy. Above 1.0 is real and
#: common in France — a euro that costs a household more than a euro happens wherever
#: two tapers overlap — so the upper bound is generous on purpose. Values outside are
#: clipped and counted, never dropped silently.
EMTR_BOUNDS = (-0.2, 1.5)

#: The column each cache file carries: the fingerprint of the frame its rates were
#: computed on. The keys name the vintage, the year, the sample, the reform and the
#: uprating, never the frame, and two frames of the same rows can share them (D-276).
FRAME = "frame_fingerprint"

#: The samples C1 reads, the study's first (D-284). C1 sums the terms of a few top-decile
#: households whose 100 € step crosses a small jump under one law only, and one sample
#: of 3 000 carries a standard deviation of up to 0.09 point of Δb 2035 (D-283). Four
#: samples, pooled, halve it. The other channels read the first sample alone.
C1_SAMPLES = (SAMPLE_SEED, 1, 2, 3)


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


#: The household's income tax as the engine computes it, per foyer: NEGATIVE when paid
#: (`engine.outputs`, measured on openfisca-france 176.0.8).
IR_VARIABLE = "impot_revenu_restant_a_payer"

#: What the cache files of the rates carry since D-336: the income tax's own marginal rate
#: beside the total one. In every file name and key, so that a file written before, which
#: has no IR column, is never served (D-276).
COLUMNS_VERSION = "ir"


def _disposable(frame: pl.DataFrame, system: Any, year: int) -> tuple[np.ndarray, np.ndarray]:
    """The households' disposable income and the income tax they pay (positive when
    paid), and the simulation they were read from freed.

    A simulation is a cycle, its holders and populations pointing back at it, that only a
    full collection frees; a large heap seldom runs one. A pass of the path builds sixteen
    here, four per sample, and kept them all: in 2035, the sample's top households more
    numerous, it grew past the container (D-332)."""
    from impots.population.runner import _household_index, _to_households

    simulation = build_simulation(frame, system, year)
    disposable = simulation.calculate("revenu_disponible").astype(np.float64)
    # Per foyer and negative when paid: summed into the ménages, sign turned once, here.
    index = _household_index(frame.sort("person_id"), "foyer_id", simulation.household_ids)
    tax = -_to_households(simulation.calculate(IR_VARIABLE).astype(np.float64), index,
                          simulation.household_ids.size)
    del simulation
    gc.collect()
    return disposable, tax


def _rate(
    frame: pl.DataFrame, system: Any, year: int, earners: np.ndarray, step: float,
    guards: dict[str, Any], label: str,
) -> tuple[np.ndarray, np.ndarray]:
    """(The total marginal rate, the income tax's alone), by the same finite difference
    in the same simulations (D-336, decision 4): τ = 1 − Δ disposable / step, and
    τ_IR = Δ income tax paid / step."""
    base, tax_base = _disposable(frame, system, year)
    bumped, tax_bumped = _disposable(_bump(frame, step), system, year)
    extra = step * earners
    with np.errstate(divide="ignore", invalid="ignore"):
        rate = 1.0 - (bumped - base) / extra
        rate_ir = (tax_bumped - tax_base) / extra
    # A household with no earner received no extra euro; the ratio is 0/0. It has no
    # marginal rate on labour, which is not the same as a rate of zero.
    rate = np.where(earners > 0, rate, np.nan)
    rate_ir = np.where(earners > 0, rate_ir, np.nan)
    guards[f"{label}_nan"] = int(np.isnan(rate[earners > 0]).sum())
    low, high = EMTR_BOUNDS
    clipped = np.clip(rate, low, high)
    guards[f"{label}_clipped"] = int(
        np.count_nonzero((rate < low) | (rate > high) & ~np.isnan(rate))
    )
    guards[f"{label}_ir_clipped"] = int(
        np.count_nonzero((rate_ir < low) | (rate_ir > high) & ~np.isnan(rate_ir))
    )
    return clipped, np.clip(rate_ir, low, high)


#: Every household whose salaries reach this is in every sample, at its own weight
#: (D-310). A draw of 3 000 households keeps 1,5 % of the population, so of its top only a
#: handful, each carried at 10 338: for a top rate of the IR at 50 %, three to seven
#: households made the whole of C1, from −297 to −1 493 M€ from one sample to the next,
#: where every household of the top gives −570 M€. The least of the households a rise of
#: the top rate touches earns 235 310 €; 2 294 households reach this threshold in 2024.
HAUT_CERTAIN = 200_000.0


def _priced(population: pl.DataFrame | Path, sample: int | None,
            seed: int = SAMPLE_SEED) -> pl.DataFrame:
    """The frame the rates are computed on: the population, subsampled, by person.

    A sample is every household whose salaries reach `HAUT_CERTAIN`, at its own weight,
    plus `sample` households drawn from the rest as the runner draws them. The draw's
    weights carry the rest's total, so the two together estimate the population's."""
    frame = pl.read_parquet(population) if isinstance(population, Path) else population
    if sample is not None:
        base = frame.group_by("household_id").agg(pl.col("salaire_brut_annuel").sum())
        hauts = base.filter(pl.col("salaire_brut_annuel") >= HAUT_CERTAIN)["household_id"]
        dedans = frame["household_id"].is_in(hauts)
        frame = pl.concat([frame.filter(dedans),
                           subsample(frame.filter(~dedans), sample, seed=seed)])
    return frame.sort("person_id")


def _drawn(seed: int) -> str:
    """What a file name says of the sample's seed: nothing for the study's, so that its
    files keep their names (D-284)."""
    return "" if seed == SAMPLE_SEED else f"_g{seed}"


def fingerprint(frame: pl.DataFrame) -> str:
    """What a cache file says of the frame its rates were computed on: every row, every
    column, in order. Stable within one polars version; another recomputes."""
    # polars 2 hashes a row with one seed, where polars 1 took four (D-328): the print is
    # the version's own, and a file written under the other recomputes, as said above.
    import inspect

    seeds = ({"seed": 0, "seed_1": 1, "seed_2": 2, "seed_3": 3}
             if "seed_1" in inspect.signature(pl.DataFrame.hash_rows).parameters
             else {"seed": 0})
    rows = frame.hash_rows(**seeds).to_numpy()
    columns = ",".join(f"{name}:{dtype}" for name, dtype in frame.schema.items())
    return hashlib.sha256(columns.encode() + rows.tobytes()).hexdigest()[:16]


def _computed_on(cached: pl.DataFrame, frame_print: str) -> bool:
    """A cache file serves only the frame it names; one that names none, written before
    the files said it, is not served (D-276)."""
    return FRAME in cached.columns and bool((cached[FRAME] == frame_print).all())


def compute(
    population: pl.DataFrame | Path,
    year: int = 2024,
    reform: Any = None,
    sample: int | None = None,
    step: float = EMTR_STEP,
    vintage: str | None = None,
    uprating_key: str | None = None,
    seed: int = SAMPLE_SEED,
) -> EmtrResult:
    """Marginal rates for every household, under current law and optionally a reform.

    Two full-tier runs per law priced (base and bumped), so four when a reform is
    given. This is the expensive input to the behavioural layer and the reason the
    caller caches it. `uprating_key` is `Uprating.key()` when the population was aged,
    None when it is the vintage as built. `seed` draws the sample: another seed is another
    sample of the same size (D-284).
    """
    # The tree's marginal rates do not see a consumption tax, priced at constant volumes on
    # the imputed consumption: the reform the tree reads is the spec without those knobs,
    # as the runner hands it (D-323, D-328). Built with them, the tree refused the reform.
    from impots import consommation

    if consommation.touche(reform):
        reform = consommation.sans_consommation(reform)
    frame = _priced(population, sample, seed)
    frame_print = fingerprint(frame)

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
    # same rows as the vintage, so the height check below would not see it (D-226). The
    # file names the frame it was computed on, and serves no other (D-276).
    started = time.perf_counter()
    aged = f"_{uprating_key}" if uprating_key is not None else ""
    cache = (
        PROCESSED
        / (f"emtr_baseline_{millesime(vintage)}_{year}_{sample or 'full'}_{int(step)}"
           f"_{to_openfisca.WIRING}{aged}{_drawn(seed)}_{COLUMNS_VERSION}.parquet")
        if vintage else None
    )
    cached_rates = pl.read_parquet(cache) if cache is not None and cache.exists() else None
    if (cached_rates is not None and cached_rates.height == per_household.height
            and _computed_on(cached_rates, frame_print) and "emtr_ir" in cached_rates.columns):
        columns = {"emtr": cached_rates["emtr"].to_numpy(),
                   "emtr_ir": cached_rates["emtr_ir"].to_numpy()}
        guards["baseline_cached"] = True
    else:  # none, or of another population or frame: recomputed rather than trusted
        total, ir = _rate(frame, baseline(), year, earners, step, guards, "baseline")
        columns = {"emtr": total, "emtr_ir": ir}
        if cache is not None:
            PROCESSED.mkdir(parents=True, exist_ok=True)
            _write_atomically(pl.DataFrame({**columns, FRAME: frame_print}), cache)
    timings["baseline_s"] = round(time.perf_counter() - started, 2)

    if reform is not None and not reform.is_empty():
        started = time.perf_counter()
        columns["emtr_reform"], columns["emtr_ir_reform"] = _rate(
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
    uprating_key: str | None = None, seed: int = SAMPLE_SEED,
) -> str:
    """A fingerprint of everything the rates depend on.

    The sample size is in the key because a subsample is a different population, not
    a cheaper view of the same one — omitting it would serve 3 000 households' rates
    for a request that asked for 20 000. The population wiring is in it for the same
    reason: a file written before D-176 holds rates of a wiring that no longer exists.
    So is the uprating of an aged population (D-226), and only then, so that the
    vintage's own keys do not move. So is the sample's seed, when it is not the study's
    (D-284). And the threshold above which a sample keeps every household (D-310).
    """
    fields = {"vintage": vintage, "year": year, "sample": sample,
              "reform": None if reform is None else reform.model_dump(exclude_none=True),
              "wiring": to_openfisca.WIRING, "columns": COLUMNS_VERSION}
    if sample is not None:
        fields["haut_certain"] = HAUT_CERTAIN
    if uprating_key is not None:
        fields["uprating"] = uprating_key
    if seed != SAMPLE_SEED:
        fields["seed"] = seed
    payload = json.dumps(fields, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


#: One distinct reform and sample, one file. Unbounded, whoever chooses reforms over HTTP
#: chooses the disk used (D-173); the most recently used are kept. Sixty-four reforms,
#: each with the samples C1 reads (D-284).
CACHE_MAX = 64 * len(C1_SAMPLES)


def _temporary(path: Path) -> Path:
    """Where `path` is written before it takes its name: same directory, so the rename
    stays on one file system, and a name no reader or eviction takes for a cache."""
    return path.with_name(f".{path.name}.{os.getpid()}.tmp")


def _write_atomically(frame: pl.DataFrame, path: Path) -> None:
    """Write a cache whole or not at all (D-309). Two processes share `data/processed` —
    two API requests, two pytest-xdist workers — and a file written in place could be read
    half-written. `os.replace` gives it its name in one step."""
    temporary = _temporary(path)
    try:
        frame.write_parquet(temporary)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


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
    sample: int | None = None, uprating_key: str | None = None, seed: int = SAMPLE_SEED,
) -> EmtrResult:
    """`compute`, memoised on disk. A minute and a half the first time, milliseconds
    after — which matters most for the same reform priced twice, since a user
    adjusting one knob and re-running is the normal way this tool is used.
    `uprating_key` is `Uprating.key()` when `population` was aged: the frame alone
    does not say so, and the key must. The file names the frame it was computed on, and
    serves no other (D-276)."""
    vintage = millesime(vintage)
    key = cache_key(vintage, year, reform, sample, uprating_key, seed)
    path = PROCESSED / f"emtr_{vintage}_{key}.parquet"
    frame_print = fingerprint(_priced(population, sample, seed))
    if path.exists():
        households = pl.read_parquet(path)
        if _computed_on(households, frame_print):
            path.touch()  # most recently USED, not most recently written, survives eviction
            return EmtrResult(households=households.drop(FRAME), year=year,
                              guards={"cached": True})
    result = compute(population, year=year, reform=reform, sample=sample, vintage=vintage,
                     uprating_key=uprating_key, seed=seed)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    _make_room(vintage)
    _write_atomically(result.households.with_columns(pl.lit(frame_print).alias(FRAME)), path)
    return result
