"""Les ménages du haut dans chaque échantillon des taux marginaux, à leur propre poids (D-310).

Un échantillon de 3 000 ménages tiré proportionnellement au poids garde 1,5 % de la
population : du haut, quelques ménages seulement, chacun porté à 10 338. Pour un taux
supérieur de l'IR porté à 50 %, trois à sept ménages par échantillon faisaient tout C1, de
−297 M€ à −1 493 M€ d'un échantillon à l'autre, quand tous les ménages du haut de la
population donnent −570 M€. Ceux dont les salaires atteignent `HAUT_CERTAIN` sont désormais
dans chaque échantillon, au poids qu'ils ont dans la population ; le reste est tiré comme
avant.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from impots.behavioural import emtr


def _population(n: int = 1_000, hauts: int = 10) -> pl.DataFrame:
    """`n` ménages d'une personne ; les `hauts` derniers au-dessus du seuil."""
    rng = np.random.default_rng(7)
    salaires = rng.uniform(10_000, 60_000, n)
    salaires[-hauts:] = emtr.HAUT_CERTAIN * rng.uniform(1.0, 8.0, hauts)
    return pl.DataFrame({
        "person_id": np.arange(n), "household_id": np.arange(n),
        "salaire_brut_annuel": salaires, "weight": rng.uniform(100.0, 200.0, n),
    })


def test_every_household_of_the_top_is_in_every_sample_at_its_own_weight() -> None:
    population = _population()
    hauts = population.filter(pl.col("salaire_brut_annuel") >= emtr.HAUT_CERTAIN)
    for graine in emtr.C1_SAMPLES:
        tire = emtr._priced(population, 100, seed=graine)
        gardes = tire.filter(pl.col("household_id").is_in(hauts["household_id"]))
        assert gardes.sort("household_id")["weight"].to_list() == \
            hauts.sort("household_id")["weight"].to_list(), graine


def test_the_rest_is_still_drawn_and_still_estimates_its_total() -> None:
    """The top taken whole, the rest of the population is drawn as before: `sample`
    households, whose weights carry the rest's total."""
    population = _population()
    dessous = population.filter(pl.col("salaire_brut_annuel") < emtr.HAUT_CERTAIN)
    tire = emtr._priced(population, 100, seed=emtr.C1_SAMPLES[1])
    reste = tire.filter(pl.col("salaire_brut_annuel") < emtr.HAUT_CERTAIN)
    assert reste["household_id"].n_unique() == 100
    assert reste["weight"].sum() == pytest.approx(dessous["weight"].sum(), rel=1e-9)


def test_on_the_population_the_four_samples_share_the_whole_top() -> None:
    """On the real population, the four samples C1 reads hold the same households above
    the threshold, at their weights: a reform of the top bracket reads the same rates
    whatever the seed."""
    from impots.population.build import PROCESSED

    chemin = PROCESSED / "population_2024.parquet"
    if not chemin.exists():
        pytest.skip("no population built in this checkout")
    population = pl.read_parquet(chemin)
    base = population.group_by("household_id").agg(pl.col("salaire_brut_annuel").sum())
    hauts = set(base.filter(pl.col("salaire_brut_annuel") >= emtr.HAUT_CERTAIN)
                ["household_id"].to_list())
    assert len(hauts) > 1_000  # 2 294 au millésime 2024
    for graine in emtr.C1_SAMPLES:
        tire = emtr._priced(population, 3_000, seed=graine)
        assert hauts <= set(tire["household_id"].to_list()), graine


def test_the_threshold_is_in_the_key_of_the_cached_rates(monkeypatch) -> None:
    """Rates drawn with another threshold are rates of another sample: the key says so,
    beside the frame's fingerprint (D-276), which would also tell them apart."""
    avant = emtr.cache_key("2024", 2024, sample=3_000)
    monkeypatch.setattr(emtr, "HAUT_CERTAIN", 250_000.0)
    assert emtr.cache_key("2024", 2024, sample=3_000) != avant
    assert emtr.cache_key("2024", 2024) == emtr.cache_key("2024", 2024)
