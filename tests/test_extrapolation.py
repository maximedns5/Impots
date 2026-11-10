"""Les totaux assis sur les salaires portés aux salariés de la France entière (étape
« extrapolation » du but 19, décision du propriétaire du 10 novembre 2026).

L'enquête Emploi voit 25,29 M de salariés, les comptes nationaux en comptent 27,18 M. Chaque
salaire reste à sa valeur publiée ; les cotisations, la CSG, les allègements et les masses
de salaires d'un salarié comptent 27,18 / 25,29 fois dans un total et dans l'écart d'une
réforme. L'impôt sur le revenu et son assiette, les prestations et les niveaux de vie ne
bougent pas. Ces tests tiennent les nombres sur la population de la fixture.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots import guards
from impots.api.schemas import ReformSpec
from impots.population import aggregate as aggregate_module
from impots.population import margins
from impots.population.emploi_discontinu import attach_mois_travailles
from impots.population.incomes import attach_incomes, household_share_of_france
from impots.population.runner import run
from impots.population.skeleton import SEED, build_skeleton

FIXTURE = Path(__file__).parent / "fixtures" / "eec_sample.parquet"

#: Les salariés de l'enquête cotisent pour les absents, les gérants pour eux seuls.
K = 27_181_700.0 / (29_187_000.0 * 0.8665994595935453)

#: Une réforme sur les seuls salaires, les cotisations retraite salariales à 22 % de ce
#: qu'elles sont (Attal, « Droit au brut »).
ATTAL = ReformSpec.model_validate({"cotisations_salariales_retraite_echelle": 0.22})


@pytest.fixture(scope="module")
def population() -> pl.DataFrame:
    """La population de la fixture, comme `tests/test_population.py` la bâtit."""
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    frame, _ = build_skeleton(children_per_household=children, source=pl.read_parquet(FIXTURE))
    frame, _ = attach_incomes(frame, targets_scale=household_share_of_france(frame))
    frame, _ = attach_mois_travailles(frame, seed=SEED)
    return frame


@pytest.fixture(scope="module")
def reformed(population: pl.DataFrame) -> pl.DataFrame:
    return run(population, 2024, reform=ATTAL, tier="full").households


def _both(households: pl.DataFrame, monkeypatch: pytest.MonkeyPatch
          ) -> tuple[aggregate_module.Aggregates, aggregate_module.Aggregates]:
    """Les agrégats sur le champ de l'enquête, puis portés à la France entière.

    L'identité comptable de `sector_balance` n'est pas appelée ici : sur les 400 ménages
    de la fixture, cette réforme fuit déjà de 0,15 % du net vers des prestations que la
    passe ne rapporte pas (180 739 € sur 116,7 M€, avant comme après l'extrapolation),
    au-delà des 0,1 % permis. Ce que l'extrapolation ajoute est vérifié à part, poste par
    poste (`test_a_wage_reform_costs_france_s_employees`) ; sur 15 000 ménages réels,
    l'identité tient (rapport de l'étape)."""
    monkeypatch.setattr(aggregate_module, "sector_balance", lambda *a, **k: {"ok": 1.0})
    monkeypatch.setattr(aggregate_module, "EXTRAPOLER_SALARIES", False)
    survey = aggregate_module.aggregate(households)
    monkeypatch.setattr(aggregate_module, "EXTRAPOLER_SALARIES", True)
    return survey, aggregate_module.aggregate(households)


def test_the_factor_is_the_accounts_headcount_over_the_survey_s() -> None:
    """27 181 700 salariés (T_6210) sur 25 293 000 (ECRT 2026 fiche 2.1, part de l'EEC)."""
    assert margins.EXTRAPOLATION_SALARIES.value == pytest.approx(K, rel=1e-12)
    assert margins.EXTRAPOLATION_SALARIES.value == pytest.approx(1.07466, abs=1e-5)
    assert margins.EXTRAPOLATION_SALARIES.value * margins.CHAMP_SALARIES_ENQUETE.value == (
        pytest.approx(1.0, rel=1e-12))


def test_the_wage_bill_is_carried_to_d11_less_nothing(population: pl.DataFrame,
                                                     reformed: pl.DataFrame,
                                                     monkeypatch: pytest.MonkeyPatch
                                                     ) -> None:
    """Le brut porté : celui des gérants une fois, celui des salariés K fois. Sur la
    population, c'est D11 entier : (D11 − gérants) × 0,9305 × K + gérants."""
    survey, france = _both(reformed, monkeypatch)
    weight = population.group_by("household_id").agg(pl.col("weight").mean())
    persons = population.join(weight.rename({"weight": "w"}), on="household_id")
    gerant = persons["regime_non_salarie"].is_in(["gerant_bic", "gerant_bnc"]).fill_null(
        False).to_numpy()
    wages = persons["salaire_brut_annuel"].to_numpy() * persons["w"].to_numpy()
    expected = float(wages[gerant].sum() + K * wages[~gerant].sum())
    assert survey.totals["salaire_brut"] == pytest.approx(float(wages.sum()), rel=1e-6)
    assert france.totals["salaire_brut"] == pytest.approx(expected, rel=1e-6)
    assert france.extrapolation_salaires == pytest.approx(K)
    assert survey.extrapolation_salaires == 1.0


def test_the_levies_on_wages_are_carried_and_the_rest_is_not(
        reformed: pl.DataFrame, monkeypatch: pytest.MonkeyPatch) -> None:
    survey, france = _both(reformed, monkeypatch)
    for name in ("cotisations_salariales", "csg_deductible", "csg_imposable", "crds",
                 "allegement_general", "salaire_super_brut", "salaire_net"):
        ratio = france.totals[name] / survey.totals[name]
        assert 1.0 < ratio <= K * (1 + 1e-9), name
    # L'assiette de l'impôt est calée sur les salaires déclarés : elle ne se porte pas.
    for name in ("salaire_imposable", "ir", "ir_avant_niches", "ppa", "rsa", "aide_logement",
                 "af", "retraite_imposable", "csg_retraite", "csg_non_salarie"):
        assert france.totals[name] == survey.totals[name], name
    assert france.counts == survey.counts
    assert france.niveau_de_vie_quantiles == survey.niveau_de_vie_quantiles
    assert [row.mean_delta for row in france.deciles] == [
        row.mean_delta for row in survey.deciles]


def test_a_wage_reform_costs_france_s_employees(reformed: pl.DataFrame,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """Le coût d'une baisse des cotisations salariales gagne ce que les absents auraient
    reçu en net : K − 1 fois la baisse des cotisations des salariés enquêtés, et ni l'impôt
    ni la prime ne bougent ; l'identité comptable tient (`sector_balance`, sinon lève)."""
    survey, france = _both(reformed, monkeypatch)
    assert survey.reform_cost is not None and survey.reform_cost > 0
    added = -(france.deltas["cotisations_salariales"] - survey.deltas["cotisations_salariales"])
    # K − 1 fois la baisse, moins celle des gérants (4 % de la baisse sur la fixture).
    bound = -(K - 1) * survey.deltas["cotisations_salariales"]
    assert 0.9 * bound < added <= bound * (1 + 1e-9)
    assert france.reform_cost - survey.reform_cost == pytest.approx(added, rel=1e-6)
    assert france.deltas["ir"] == survey.deltas["ir"]
    assert france.deltas["ppa"] == survey.deltas["ppa"]
    # L'identité, sur ce que l'extrapolation ajoute : le coût gagne exactement ce que
    # les prélèvements de l'État perdent de plus, les cotisations patronales comprises.
    receipts = [name for name in guards.STATE_RECEIPTS if name in france.deltas]
    lost = -sum(france.deltas[name] - survey.deltas[name] for name in receipts) - (
        france.employer_contribution_delta - survey.employer_contribution_delta)
    assert france.reform_cost - survey.reform_cost == pytest.approx(lost, rel=1e-6)


def test_an_employer_cut_is_carried_too(population: pl.DataFrame,
                                        monkeypatch: pytest.MonkeyPatch) -> None:
    """La réduction générale étendue à 2 SMIC : les cotisations patronales payées baissent
    de K fois ce qu'elles baissent chez les salariés enquêtés, gérants mis à part."""
    households = run(population, 2024, tier="full", reform=ReformSpec.model_validate(
        {"allegement_general_plafond": 2.0})).households
    survey, france = _both(households, monkeypatch)
    assert survey.employer_contribution_delta < 0
    ratio = france.employer_contribution_delta / survey.employer_contribution_delta
    assert 1.0 < ratio <= K * (1 + 1e-9)
    assert france.reform_cost - survey.reform_cost == pytest.approx(
        -(france.employer_contribution_delta - survey.employer_contribution_delta), rel=1e-6)
