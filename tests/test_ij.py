"""Les indemnités journalières imputées sur la population (but 8, D-305).

La masse est celle du CCSS de mai 2026, lue dans le PDF manifesté et refusée si les deux
tableaux démentent le texte ; la clé est la fréquence des arrêts de l'enquête Emploi par
tranche d'âge et PCS, sur un salaire plafonné. Les totaux imputés sont ceux du CCSS, et
la vérification refuse une colonne qui s'en écarte.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from impots.engine.system import baseline
from impots.population import ij, runner
from impots.population.to_openfisca import IJ_INPUTS, WiringError, build_simulation

@pytest.fixture(scope="module")
def population() -> pl.DataFrame:
    from impots.population.cli import PROCESSED

    return pl.read_parquet(PROCESSED / "population_2024.parquet").sort("person_id")


@pytest.fixture(scope="module")
def imputed(population) -> pl.DataFrame:
    return ij.impute(population)


@pytest.fixture(autouse=True)
def _fresh_reading():
    ij.published.cache_clear()
    yield
    ij.published.cache_clear()


# --- la source -----------------------------------------------------------------------


def test_the_ccss_lines_are_read() -> None:
    source = ij.published()
    assert (source.total_2024, source.total_2025) == (15_645.0, 16_445.0)
    assert (source.atmp_2024, source.atmp_2025) == (4_955.0, 5_480.0)
    assert source.maladie_2024 == 10_690.0


def test_a_reading_that_contradicts_the_text_is_refused(monkeypatch) -> None:
    """The tables give 33,3 % of AT-MP in 2025; the text says 34 %. A reading that took
    the wrong figure (a loose thousands pattern did: 1 231 %) is refused."""
    monkeypatch.setattr(ij, "ATMP_SHARE_2025_TEXT", 0.30)
    with pytest.raises(ij.SickPayError, match="la lecture est fausse"):
        ij.published()


def test_a_missing_line_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(ij, "TOTAL_PAGE", ij.TOTAL_PAGE + 1)
    with pytest.raises(ij.SickPayError, match="fiche 2.3"):
        ij.published()


def test_the_frequencies_are_the_eec_weekly_rates() -> None:
    cells = ij.frequencies()
    assert len(cells) == 20
    assert cells[("50", "ouvrier")] == pytest.approx(0.0862, abs=5e-5)
    assert cells[("15", "cadre")] == pytest.approx(0.0055, abs=5e-5)


# --- l'imputation --------------------------------------------------------------------


def test_the_imputed_totals_are_the_ccss_s(imputed) -> None:
    totals = ij.verify(imputed, ij.published())
    assert totals["maladie"] == pytest.approx(10_690.0, rel=1e-9)
    assert totals["atmp"] == pytest.approx(4_955.0, rel=1e-9)


def test_only_the_private_sector_s_employees_receive_it(imputed) -> None:
    private = (imputed["is_salarie"] & ~imputed["secteur_public"]
               & (imputed["statut_activite"] == "employed"))
    receive = (imputed["ij_maladie_annuel"] > 0) | (imputed["ij_atmp_annuel"] > 0)
    assert not (receive & ~private).any()
    paid = private & (imputed["salaire_brut_annuel"] > 0)
    assert (imputed.filter(paid)["ij_maladie_annuel"] > 0).all()


def test_the_key_is_the_cell_s_rate_on_a_capped_wage() -> None:
    cap = ij.reference_wage_cap()
    assert cap == pytest.approx(1.8 * 1_766.92 * 12, rel=1e-3)
    frame = pl.DataFrame({
        "is_salarie": [True] * 5, "secteur_public": [False] * 4 + [True],
        "statut_activite": ["employed"] * 5, "age": [52, 52, 52, 52, 52],
        "pcs": ["ouvrier", "ouvrier", "ouvrier", "ouvrier", "ouvrier"],
        "salaire_brut_annuel": [15_000.0, 30_000.0, 100_000.0, 200_000.0, 30_000.0],
    })
    key = ij.keys(frame, cap, {("50", "ouvrier"): 0.1})
    assert key[1] == pytest.approx(2 * key[0])
    assert key[2] == key[3] == pytest.approx(0.1 * cap)
    assert key[4] == 0.0


def test_a_cell_the_survey_lacks_is_refused() -> None:
    frame = pl.DataFrame({"is_salarie": [True], "secteur_public": [False],
                          "statut_activite": ["employed"], "age": [30], "pcs": ["cadre"],
                          "salaire_brut_annuel": [30_000.0]})
    with pytest.raises(ij.SickPayError, match="cellule"):
        ij.keys(frame, 40_000.0, {("50", "cadre"): 0.02})


@pytest.mark.parametrize("column", ["ij_maladie_annuel", "ij_atmp_annuel"])
def test_a_column_off_its_aggregate_is_refused(imputed, column) -> None:
    off = imputed.with_columns(pl.col(column) * 1.001)
    with pytest.raises(ij.SickPayError, match="publiés par le CCSS"):
        ij.verify(off, ij.published())


def test_a_negative_sick_pay_is_refused(imputed) -> None:
    """One person below zero, another raised to keep the total: only the sign is wrong."""
    values = imputed["ij_maladie_annuel"].to_numpy().copy()
    weights = imputed["weight"].to_numpy()
    i, j = np.flatnonzero(values > 0)[:2]
    shift = (-1.0 - values[i]) * weights[i]
    values[i] = -1.0
    values[j] -= shift / weights[j]
    with pytest.raises(ij.SickPayError, match="négative"):
        ij.verify(imputed.with_columns(pl.Series("ij_maladie_annuel", values)),
                  ij.published())


def test_another_year_is_refused_before_any_pass(population) -> None:
    with pytest.raises(ij.SickPayError, match="2025"):
        ij.impute(population, 2025)
    with pytest.raises(ij.SickPayError, match="2025"):
        runner.run(population, year=2025, sample=5, impute_ij=True)


# --- le branchement ------------------------------------------------------------------


def test_the_sick_pay_reaches_openfisca(imputed) -> None:
    frame = runner.subsample(imputed, 8).sort("person_id")
    built = build_simulation(frame, baseline(), 2024)
    for variable, column in IJ_INPUTS.items():
        got = np.asarray(built.simulation.calculate(variable, "2024-03"))
        assert got == pytest.approx(frame[column].to_numpy() / 12.0)
    assert frame["ij_maladie_annuel"].sum() > 0


def test_a_frame_with_half_the_sick_pay_is_refused(imputed) -> None:
    frame = runner.subsample(imputed, 4).drop("ij_atmp_annuel")
    with pytest.raises(WiringError, match="only part of the sick pay"):
        build_simulation(frame, baseline(), 2024)


def test_without_the_flag_no_sick_pay_is_written(population) -> None:
    frame = runner.subsample(population, 4).sort("person_id")
    built = build_simulation(frame, baseline(), 2024)
    got = np.asarray(built.simulation.calculate("indemnites_journalieres_maladie",
                                                "2024-03"))
    assert not got.any()
