"""Les jeunes actifs chez leurs parents, foyers de la prime à part (but 19, « ppa2 »).

Sur la population de la fixture (`eec_sample.parquet`), comme `test_emploi_discontinu` :
le squelette, `attach_incomes` aux cibles ramenées à la fixture, les mois travaillés,
puis `attach_familles_jeunes`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots.engine.system import baseline
from impots.population import emploi_discontinu as ed
from impots.population import familles_jeunes as fj
from impots.population import margins
from impots.population.incomes import attach_incomes, household_share_of_france
from impots.population.skeleton import build_skeleton
from impots.population.to_openfisca import build_simulation

FIXTURE = Path(__file__).parent / "fixtures" / "eec_sample.parquet"


@pytest.fixture(scope="module")
def avant() -> pl.DataFrame:
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    skeleton, _ = build_skeleton(children_per_household=children,
                                 source=pl.read_parquet(FIXTURE))
    frame, _ = attach_incomes(skeleton, targets_scale=household_share_of_france(skeleton))
    frame, _ = ed.attach_mois_travailles(frame, seed=20240101)
    return frame.sort("person_id")


@pytest.fixture(scope="module")
def apres(avant: pl.DataFrame) -> tuple[pl.DataFrame, fj.FamillesJeunesStats]:
    return fj.attach_familles_jeunes(avant)


def test_only_working_young_adults_above_the_threshold_leave(
        avant: pl.DataFrame, apres: tuple[pl.DataFrame, fj.FamillesJeunesStats]) -> None:
    """Un enfant de 18 à 24 ans payé au-delà de 55 % de 169 h de Smic par mois travaillé
    devient demandeur d'une famille à lui, hébergé ; personne d'autre ne bouge."""
    frame, stats = apres
    assert stats.jeunes > 0 and stats.familles_apres == stats.familles_avant + stats.jeunes
    sorti = (frame["famille_id"] != avant["famille_id"]).to_numpy()
    assert sorti.sum() == stats.jeunes
    jeunes = frame.filter(pl.Series(sorti))
    assert (jeunes["role_famille"] == "demandeur").all()
    assert jeunes["aide_logement_heberge"].all()
    assert jeunes["age"].is_between(18, 24).all()
    mensuel = avant.filter(pl.Series(sorti)).select(fj.revenu_mensuel(avant))
    assert (mensuel.to_series() > fj.SEUIL_A_CHARGE).all()
    reste = ~sorti
    for col in ("famille_id", "role_famille", "foyer_id", "household_id",
                "salaire_brut_annuel"):
        assert (frame[col].to_numpy()[reste] == avant[col].to_numpy()[reste]).all()
    # Un enfant de 18 à 24 ans sous le seuil reste à la charge de ses parents.
    sous = avant.filter((pl.col("role_famille") == "enfant") & (pl.col("age") >= 18)
                        & (pl.col("age") < 25) & (pl.col("salaire_brut_annuel") > 0)
                        & (fj.revenu_mensuel(avant) <= fj.SEUIL_A_CHARGE))
    assert set(sous["person_id"].to_list()).isdisjoint(set(jeunes["person_id"].to_list()))


def test_the_young_adult_earns_a_prime_and_leaves_the_parents_base(
        avant: pl.DataFrame, apres: tuple[pl.DataFrame, fj.FamillesJeunesStats]) -> None:
    """Le nombre que le module change : un jeune salarié sorti a une prime à son nom, et
    son salaire quitte la base ressources de ses parents. Sur le code d'avant, le module
    n'existait pas, et le moteur ne lui donnait aucune prime (il est enfant)."""
    frame, _ = apres
    sorti = (frame["famille_id"] != avant["famille_id"]).to_numpy()
    built_avant = build_simulation(avant, baseline(), 2024)
    built_apres = build_simulation(frame, baseline(), 2024)
    ppa_apres = built_apres.calculate("ppa", month=12)
    ids_apres = np.asarray(built_apres.famille_ids).astype(str)
    jeunes_familles = set(frame.filter(pl.Series(sorti))["famille_id"].to_list())
    a_eux = np.isin(ids_apres, list(jeunes_familles))
    assert (ppa_apres[a_eux] > 0).any()
    # Les parents : leur revenu d'activité de la prime perd le salaire du jeune.
    parents = set(avant.filter(pl.Series(sorti))["famille_id"].to_list())
    ids_avant = np.asarray(built_avant.famille_ids).astype(str)
    ra_avant = built_avant.calculate("ppa_revenu_activite", month=12)
    ra_apres = built_apres.calculate("ppa_revenu_activite", month=12)
    chez_avant = np.isin(ids_avant, list(parents))
    chez_apres = np.isin(ids_apres, list(parents))
    assert ra_apres[chez_apres].sum() < ra_avant[chez_avant].sum()
