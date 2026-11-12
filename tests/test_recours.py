"""Le non-recours en espérance (but 19, étape 4) : la loi de recours et la passe qui la sert."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots.api.schemas import ReformSpec
from impots.population import margins, recours
from impots.population.aggregate import aggregate
from impots.population.incomes import attach_incomes, household_share_of_france
from impots.population.runner import run
from impots.population.skeleton import build_skeleton

FIXTURE = Path(__file__).parent / "fixtures" / "eec_sample.parquet"


def test_the_take_up_law_is_the_calibrated_one() -> None:
    """Les nombres de la loi : τ ajusté sur les tranches publiées, p_max calé sur le taux en
    foyers (15 000 ménages, 2024). Les changer change le coût de toute réforme du RSA ou de
    la prime : ils se préenregistrent."""
    assert (recours.RSA.tau, recours.RSA.p_max) == (79.0, 0.6892)
    assert (recours.PPA.tau, recours.PPA.p_max) == (21.0, 0.5322)
    assert recours.RSA.cible_foyers == pytest.approx(0.65)
    assert recours.PPA.cible_foyers == pytest.approx(0.50)
    # Croissante, nulle en zéro, saturée au p_max.
    x = np.array([0.0, 10.0, 50.0, 100.0, 450.0, 5000.0])
    p = recours.probabilite("rsa", x)
    assert p[0] == 0.0 and np.all(np.diff(p) > 0)
    assert p[-1] == pytest.approx(0.6892, rel=1e-9)
    assert recours.probabilite("rsa", np.array([450.0]))[0] == pytest.approx(
        0.6892 * (1 - np.exp(-450 / 79)), rel=1e-12)
    assert recours.probabilite("ppa", np.array([25.0]))[0] == pytest.approx(
        0.5322 * (1 - np.exp(-25 / 21)), rel=1e-12)


def test_p_max_reproduces_the_published_rate_exactly() -> None:
    x = np.array([20.0, 80.0, 300.0, 480.0])
    w = np.array([1.0, 2.0, 3.0, 4.0])
    p_max = recours.p_max_cale("rsa", x, w)
    mean = (w * recours.probabilite("rsa", x, p_max)).sum() / w.sum()
    assert mean == pytest.approx(recours.RSA.cible_foyers, rel=1e-12)


def test_the_consumption_units_are_the_rsa_scale() -> None:
    """n° 1370, note 2 : 1 ; +0,5 ; +0,3 ; +0,3 (couple) ou +0,4 (parent isolé) ; +0,4."""
    parents = np.array([1, 2, 1, 2, 1, 2, 1])
    enfants = np.array([0, 0, 1, 1, 2, 2, 3])
    assert recours.unites(parents, enfants) == pytest.approx(
        [1.0, 1.5, 1.5, 1.8, 1.8, 2.1, 2.2])


def test_the_deflator_is_the_baseline_s_and_one_in_2021() -> None:
    assert recours.deflateur("rsa", 2021, 11) == pytest.approx(1.0)
    # 565,34 € fin 2021 ; 635,71 € d'avril 2024 (loi de référence).
    assert recours.deflateur("rsa", 2024, 12) == pytest.approx(565.34 / 635.71)
    assert recours.deflateur("ppa", 2024, 12) == pytest.approx(553.71 / 622.63)


def test_the_bridge_is_still_there_for_the_reconciliation() -> None:
    """Le pont reste lu par la réconciliation et la grille tant qu'elles ne sont pas
    préenregistrées autrement (consigne de l'étape 4)."""
    assert margins.TAKE_UP_BRIDGE == {"rsa": (1.30, 1.41), "ppa": (1.68, 1.77)}


@pytest.fixture(scope="module")
def population() -> pl.DataFrame:
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    frame, _ = build_skeleton(children_per_household=children,
                              source=pl.read_parquet(FIXTURE))
    frame, _ = attach_incomes(frame, targets_scale=household_share_of_france(frame))
    return frame


def test_the_run_serves_in_expectation_and_keeps_the_entitlement(
        population: pl.DataFrame) -> None:
    """La passe sert `p × droit` et garde le droit ; le revenu disponible perd exactement
    ce qui n'est pas réclamé ; le coût d'une réforme est la différence des espérances, et
    l'identité comptable (D-045) tient sur elle."""
    reform = ReformSpec.model_validate({"rsa_montant_de_base": 700.0})
    households = run(population, 2024, reform=reform, tier="full").households
    for suffix in ("", "_reform"):
        unclaimed = sum(households[f"{k}_droit{suffix}"] - households[f"{k}{suffix}"]
                        for k in ("rsa", "ppa", "crds_mini", "aefa"))
        assert np.allclose(households[f"revenu_disponible_droit{suffix}"]
                           - households[f"revenu_disponible{suffix}"], unclaimed, atol=1e-6)
        rsa, droit = households[f"rsa{suffix}"], households[f"rsa_droit{suffix}"]
        assert (rsa <= recours.RSA.p_max * droit + 1e-6).all()
        assert droit.sum() > 0 and rsa.sum() > 0

    agg = aggregate(households)
    assert agg.reform_cost == pytest.approx(agg.deltas["revenu_disponible"])
    assert agg.reform_cost_droit == pytest.approx(agg.deltas["revenu_disponible_droit"])
    assert 0 < agg.reform_cost < agg.reform_cost_droit
    # The guard ran on the served deltas (it raises past its allowance); what is left is
    # openfisca's own leakage through benefits without a row, not the take-up layer.
    assert abs(agg.balance["unexplained"]) < 1e-4 * agg.reform_cost
    assert agg.niveau_de_vie_quantiles_droit[10] >= agg.niveau_de_vie_quantiles[10]
    assert 0 < agg.counts["n_allocataires_rsa_servi"] < agg.counts["n_allocataires_rsa"]


def test_the_new_benefits_are_served_with_the_rsa_law_and_balance(
        population: pl.DataFrame) -> None:
    """Les prestations neuves d'une réforme (but 21, étape 3), sur l'échantillon de test et à
    des valeurs qui ne sont celles d'aucun candidat : le RIA et la garantie d'autonomie sont
    servis en espérance avec la loi du RSA, sous son p_max ; l'allocation par enfant, à
    recours 1, n'a pas de droit à part ; la loi n'en porte aucune ; et le garde des secteurs
    reconstitue le coût avec elles parmi les transferts (mesuré : 1,53 € d'écart sur 84 M€)."""
    reform = ReformSpec.model_validate({
        "ria": {"socle": 400.0, "insertion": 100.0, "taux_revenus_activite": 0.5,
                "remplace_rsa": True, "remplace_ppa": True, "remplace_ass": True},
        "allocation_enfant": {"montant_par_enfant": 200.0, "age_maximum": 16,
                              "remplace_af": True, "remplace_cf": False,
                              "remplace_ars": False},
        "garantie_autonomie": {"seuil": 800.0}})
    households = run(population, 2024, reform=reform, tier="full").households
    for key in ("ria", "garantie_autonomie"):
        assert (households[key] == 0).all() and (households[f"{key}_droit"] == 0).all()
        servi, droit = households[f"{key}_reform"], households[f"{key}_droit_reform"]
        assert droit.sum() > 0 and (servi <= recours.RSA.p_max * droit + 1e-6).all()
    assert (households["allocation_enfant"] == 0).all()
    assert households["allocation_enfant_reform"].sum() > 0
    assert (households["rsa_reform"] == 0).all() and (households["ppa_reform"] == 0).all()
    agg = aggregate(households)
    assert agg.reform_cost > 0
    assert abs(agg.balance["unexplained"]) < 1e-4 * agg.reform_cost
