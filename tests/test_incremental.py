"""Le moteur rapide (D-462) redonne les nombres de l'ancien, ménage par ménage.

Sur la population de test, une réforme des aides au logement : la référence lue sur
disque, la réforme sur les ménages non propriétaires seuls, et chaque colonne de chaque
ménage égale à celle de l'ancien moteur. Le crible du barème lit la première tranche
changée.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots.api.schemas import ReformSpec

FIXTURE = Path(__file__).parent / "fixtures" / "eec_sample.parquet"


@pytest.fixture(scope="module")
def frame() -> pl.DataFrame:
    from impots.population import margins
    from impots.population.incomes import attach_incomes, household_share_of_france
    from impots.population.skeleton import build_skeleton

    children = {k: np.array(v) for k, v in margins.CHILDREN_PER_FAMILY.items()}
    built, _ = build_skeleton(children_per_household=children,
                              source=pl.read_parquet(FIXTURE))
    built, _ = attach_incomes(built, targets_scale=household_share_of_france(built))
    return built


def test_the_fast_engine_gives_every_household_the_old_engines_rows(
        frame, monkeypatch, tmp_path) -> None:
    from impots.engine import incremental
    from impots.population.runner import run

    monkeypatch.setattr(incremental, "PROCESSED", tmp_path)
    reform = ReformSpec(al_revalorisation_portee=1.1)
    monkeypatch.delenv(incremental.ENV, raising=False)
    old = run(frame, year=2026, reform=reform, tier="full").households
    monkeypatch.setenv(incremental.ENV, "rapide")
    run(frame, year=2026, reform=None, tier="full")  # writes the reference
    fast = run(frame, year=2026, reform=reform, tier="full")
    assert fast.guards["moteur_rapide_reference"] == "lue"
    assert incremental.REPLI not in fast.guards
    assert 0 < fast.guards["moteur_rapide_menages"] < fast.n_households
    assert fast.households.columns == old.columns
    for column in old.columns:
        if old[column].dtype.is_numeric():
            np.testing.assert_array_equal(fast.households[column].to_numpy(),
                                          old[column].to_numpy(), err_msg=column)


def test_the_scale_crible_reads_the_first_bracket_changed() -> None:
    from impots.engine import incremental
    from impots.engine.reforms import PATH_BAREME, resolve
    from impots.engine.system import baseline

    loi = resolve(baseline().parameters, PATH_BAREME)("2026-01-01")
    brackets = [{"threshold": float(t), "rate": float(r)}
                for t, r in zip(loi.thresholds, loi.rates, strict=True)]
    assert incremental.seuil_bareme(ReformSpec(ir_bareme=brackets), 2026) is None
    top = [*brackets[:5], {"threshold": 250_000.0, "rate": 0.6}]
    assert incremental.seuil_bareme(ReformSpec(ir_bareme=top), 2026) == 250_000.0
