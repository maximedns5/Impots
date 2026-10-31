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
    ij.ald_share.cache_clear()
    yield
    ij.published.cache_clear()
    ij.ald_share.cache_clear()


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
    with pytest.raises(ij.SickPayError, match=r"fiche 2\.3"):
        ij.published()


def test_the_ald_share_of_the_days_is_read() -> None:
    """PLFSS 2026, annexe 9, p. 228 : « en 2013 le nombre de jours indemnisés des personnes en
    ALD représentait 40% des indemnités journalières contre 33% en 2024 » (D-312)."""
    assert ij.ald_share() == ij.AldShare(share_2013=0.40, share_2024=0.33)


def test_a_missing_ald_sentence_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(ij, "ALD_PAGE", ij.ALD_PAGE + 1)
    with pytest.raises(ij.SickPayError, match="ALD manque"):
        ij.ald_share()


def test_an_ald_share_that_rose_is_refused(monkeypatch) -> None:
    """The annex says the share fell, and why: a reading that found it rising read the
    wrong figures."""
    import pypdf

    class _Page:
        def extract_text(self) -> str:
            return ("En effet, en 2013 le nombre de jours indemnisés des personnes en ALD "
                    "représentait 30% des indemnités journalières contre \n33% en 2024.")

    class _Reader:
        def __init__(self, _path) -> None:
            self.pages = [_Page()] * ij.ALD_PAGE

    monkeypatch.setattr(pypdf, "PdfReader", _Reader)
    with pytest.raises(ij.SickPayError, match="la lecture est fausse"):
        ij.ald_share()


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


def test_the_totals_the_aggregate_reads_are_the_ccss_s(population) -> None:
    """GUARD (D-314). The aggregate weighs each ménage by the mean of its members' weights
    (`runner`), and D-308's pass saw 0,34 % less sick pay than the CCSS: the imputation
    was scaled on the persons' own weights. On a subsample, as a pass draws it, the totals
    under the household weights are the CCSS's."""
    frame = ij.impute(runner.subsample(population, 20_000).sort("person_id"))
    household = frame.select(pl.col("weight").mean().over("household_id")).to_series()
    differ = frame.group_by("household_id").agg(pl.col("weight").n_unique() > 1)
    assert differ["weight"].sum() > 100
    for column, expected in (("ij_maladie_annuel", 10_690.0), ("ij_atmp_annuel", 4_955.0),
                             ("ij_maladie_ald_annuel", 0.33 * 10_690.0)):
        total = float(household.to_numpy() @ frame[column].to_numpy()) / 1e6
        assert total == pytest.approx(expected, rel=1e-9), column


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


def test_the_ald_part_is_a_third_of_each_sickness_allowance(imputed) -> None:
    """33 % of each person's sickness allowances, the share of the days (D-312): 3 527,7 M€."""
    assert imputed["ij_maladie_ald_annuel"].to_numpy() == pytest.approx(
        0.33 * imputed["ij_maladie_annuel"].to_numpy(), rel=1e-12)
    totals = ij.verify(imputed, ij.published())
    assert totals["ald"] == pytest.approx(0.33 * 10_690.0, rel=1e-9)


@pytest.mark.parametrize("column, origin", [("ij_maladie_annuel", "publiés par le CCSS"),
                                            ("ij_atmp_annuel", "publiés par le CCSS"),
                                            ("ij_maladie_ald_annuel", "PLFSS 2026")])
def test_a_column_off_its_aggregate_is_refused(imputed, column, origin) -> None:
    off = imputed.with_columns(pl.col(column) * 1.001)
    with pytest.raises(ij.SickPayError, match=origin):
        ij.verify(off, ij.published())


def test_an_ald_part_above_its_sickness_is_refused(imputed) -> None:
    """Two people swap their ALD parts at equal weight: the total holds, but one of them
    now has more ALD than sickness."""
    ald = imputed["ij_maladie_ald_annuel"].to_numpy().copy()
    maladie = imputed["ij_maladie_annuel"].to_numpy()
    weights = ij.household_weights(imputed)  # the weights `verify` reads
    paid = np.flatnonzero(maladie > 0)
    low, high = paid[np.argmin(maladie[paid])], paid[np.argmax(maladie[paid])]
    moved = ald[high] * weights[high] / weights[low]
    ald[low], ald[high] = ald[low] + moved, 0.0
    with pytest.raises(ij.SickPayError, match="dépasse la maladie"):
        ij.verify(imputed.with_columns(pl.Series("ij_maladie_ald_annuel", ald)),
                  ij.published())


def test_a_negative_sick_pay_is_refused(imputed) -> None:
    """One person below zero, another raised to keep the total: only the sign is wrong."""
    values = imputed["ij_maladie_annuel"].to_numpy().copy()
    weights = ij.household_weights(imputed)  # the weights `verify` reads
    i, j = np.flatnonzero(values > 0)[:2]
    shift = (-1.0 - values[i]) * weights[i]
    values[i] = -1.0
    values[j] -= shift / weights[j]
    with pytest.raises(ij.SickPayError, match="négative"):
        ij.verify(imputed.with_columns(pl.Series("ij_maladie_annuel", values)),
                  ij.published())


def test_a_negative_ald_part_is_refused(imputed) -> None:
    """One ALD part below zero, another raised within its sickness to keep the total: only
    the sign is wrong, and no other check sees it."""
    ald = imputed["ij_maladie_ald_annuel"].to_numpy().copy()
    maladie = imputed["ij_maladie_annuel"].to_numpy()
    weights = ij.household_weights(imputed)  # the weights `verify` reads
    paid = np.flatnonzero(maladie > 0)
    low = paid[np.argmin((ald * weights)[paid])]
    high = paid[np.argmax((maladie * weights)[paid])]
    ald[high] += (ald[low] + 1.0) * weights[low] / weights[high]
    ald[low] = -1.0
    assert ald[high] <= maladie[high]
    with pytest.raises(ij.SickPayError, match="négative"):
        ij.verify(imputed.with_columns(pl.Series("ij_maladie_ald_annuel", ald)),
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


def test_raw_openfisca_gets_no_ald_input_and_runs(imputed) -> None:
    """Kill tests run raw openfisca, which has no ALD variable and taxes no allowance: the
    project's input is not written there (D-312), the others are."""
    from impots.engine.system import uncorrected_baseline

    frame = runner.subsample(imputed, 4).sort("person_id")
    built = build_simulation(frame, uncorrected_baseline(), 2024)
    got = np.asarray(built.simulation.calculate("indemnites_journalieres_maladie", "2024-03"))
    assert got == pytest.approx(frame["ij_maladie_annuel"].to_numpy() / 12.0)


def test_an_input_openfisca_should_carry_still_raises(imputed, monkeypatch) -> None:
    """GUARD (D-312). Only a variable the corrections add may be missing: a renamed
    openfisca variable is refused, not dropped."""
    from openfisca_core.errors import VariableNotFoundError

    from impots.population import to_openfisca

    inputs = {**IJ_INPUTS, "variable_absente": "ij_maladie_ald_annuel"}
    monkeypatch.setattr(to_openfisca, "IJ_INPUTS", inputs)
    frame = runner.subsample(imputed, 4).sort("person_id")
    with pytest.raises(VariableNotFoundError):
        build_simulation(frame, baseline(), 2024)


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
