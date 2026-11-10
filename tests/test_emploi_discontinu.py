"""Les mois travaillés (but 19, étape « ppa ») : l'emploi discontinu dans l'année.

Sur la population de la fixture (`eec_sample.parquet`), comme `test_non_salaries` : le
squelette, `attach_incomes` aux cibles ramenées à la fixture, puis
`attach_mois_travailles`.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots.engine.system import baseline
from impots.population import emploi_discontinu as ed
from impots.population import margins
from impots.population.incomes import attach_incomes, household_share_of_france
from impots.population.skeleton import build_skeleton
from impots.population.to_openfisca import build_simulation, monthly_by_month

FIXTURE = Path(__file__).parent / "fixtures" / "eec_sample.parquet"


@pytest.fixture(scope="module")
def avant() -> pl.DataFrame:
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    skeleton, _ = build_skeleton(children_per_household=children,
                                 source=pl.read_parquet(FIXTURE))
    frame, _ = attach_incomes(skeleton, targets_scale=household_share_of_france(skeleton))
    return frame


@pytest.fixture(scope="module")
def apres(avant: pl.DataFrame) -> tuple[pl.DataFrame, ed.Statistiques]:
    return ed.attach_mois_travailles(avant, seed=20240101)


def _employes(frame: pl.DataFrame) -> np.ndarray:
    return (frame["is_salarie"] & (frame["statut_activite"] == "employed")).to_numpy()


def test_the_wage_bill_is_unchanged_and_spread_over_more_people(
        avant: pl.DataFrame, apres: tuple[pl.DataFrame, ed.Statistiques]) -> None:
    """La masse calée des salaires ne bouge pas, à l'euro près ; elle est partagée entre
    les salariés de la semaine et des personnes sans emploi qui ont quitté un emploi
    salarié dans l'année. Sur le code d'avant, le module n'existait pas."""
    frame, stats = apres
    w = avant["weight"].to_numpy()
    before = avant["salaire_brut_annuel"].to_numpy()
    after = frame["salaire_brut_annuel"].to_numpy()
    assert float((after * w).sum()) == pytest.approx(float((before * w).sum()), rel=1e-12)
    employe = _employes(avant)
    sortant = (~employe) & (after > 0) & (before == 0)
    assert sortant.any() and stats.sortants_payes > 0
    # Nobody else is touched: the gérants keep their pay, the others have none.
    autre = ~employe & ~sortant
    assert np.allclose(after[autre], before[autre])
    assert stats.facteur == pytest.approx(1.0, abs=0.05)


def test_a_recent_hire_is_paid_fewer_months_at_the_same_rate(
        avant: pl.DataFrame, apres: tuple[pl.DataFrame, ed.Statistiques]) -> None:
    """Le salarié dans son poste depuis moins d'un an (ANCEMPL4 = 1) a moins de douze mois
    de salaire, au taux mensuel d'avant fois le facteur commun ; celui qui y est depuis un
    an ou plus garde ses douze mois."""
    frame, stats = apres
    employe = _employes(avant)
    mois = ed.nombre_de_mois(frame["mois_travailles"].to_numpy())
    recent = employe & (avant["anciennete_emploi"].fill_null("").to_numpy() == "1")
    ancien = employe & ~recent
    # Short of twelve unless the months before were worked too (`PLEIN_AVANT`, 0,41).
    assert recent.any() and (mois[recent] < 12).mean() > 0.35
    assert (mois[ancien] == 12).all()
    taux_avant = avant["salaire_brut_annuel"].to_numpy()[recent] / 12.0
    taux_apres = frame["salaire_brut_annuel"].to_numpy()[recent] / mois[recent]
    assert np.allclose(taux_apres, taux_avant * stats.facteur)


def test_the_survey_month_is_worked_by_an_employee_and_not_by_a_leaver(
        avant: pl.DataFrame, apres: tuple[pl.DataFrame, ed.Statistiques]) -> None:
    """Le mois de l'enquête est dans le trimestre de la vague ; l'employé y travaille, la
    personne sans emploi non."""
    frame, _ = apres
    t, employe = ed._tirer(avant, 20240101)
    trimestre = avant["household_id"].str.split("-").list.last().cast(pl.Int64).to_numpy()
    assert ((t.mois_enquete - 1) // 3 + 1 == trimestre).all()
    m = frame["mois_travailles"].to_numpy()
    bit = (m >> (t.mois_enquete - 1)) & 1
    assert (bit[employe] == 1).all()
    paye = frame["salaire_brut_annuel"].to_numpy() > 0
    assert (bit[t.sortant & paye & ~employe] == 0).all()


def test_the_volume_of_work_falls_toward_the_insee(
        apres: tuple[pl.DataFrame, ed.Statistiques]) -> None:
    """Le volume de travail moyen en EQTP des salariés de l'année baisse vers les 0,77 de
    l'Insee (sur la population entière : de 0,935 à 0,813)."""
    _, stats = apres
    assert stats.volume_eqtp < stats.volume_avant - 0.05


def test_monthly_by_month_keeps_the_annual_amount() -> None:
    """Le salaire va aux mois travaillés, le chômage aux autres, le total de l'année ne
    change pas ; sans masque, ou avec un masque plein, le douzième de chaque mois."""
    frame = pl.DataFrame({"mois_travailles": [ed.TOUS_LES_MOIS, 0b000000000111, 0]})
    annual = np.array([1200.0, 900.0, 600.0])
    salary = monthly_by_month(frame, annual, worked=True)
    chomage = monthly_by_month(frame, annual, worked=False)
    assert np.allclose(np.sum(salary, axis=0), annual)
    assert np.allclose(np.sum(chomage, axis=0), annual)
    assert [s[1] for s in salary] == [300.0] * 3 + [0.0] * 9
    assert [c[1] for c in chomage] == [0.0] * 3 + [100.0] * 9
    assert all(s[0] == 100.0 for s in salary)
    assert np.allclose(monthly_by_month(pl.DataFrame({"x": [1]}), np.array([120.0]),
                                        worked=True), 10.0)


def test_the_simulation_pays_the_salary_on_the_months_worked(
        apres: tuple[pl.DataFrame, ed.Statistiques]) -> None:
    """Le câblage écrit le salaire sur les mois travaillés seulement, et le brut de
    l'année refait celui du cadre (hors fonctionnaires, payés en traitement)."""
    frame, _ = apres
    frame = frame.sort("person_id")
    built = build_simulation(frame, baseline(), 2024)
    base = np.stack([built.simulation.calculate("salaire_de_base", f"2024-{m:02d}")
                     for m in range(1, 13)])
    m = frame["mois_travailles"].to_numpy()
    prive = ~frame["titulaire"].to_numpy().astype(bool)
    partiel = prive & (m != ed.TOUS_LES_MOIS) & (frame["salaire_brut_annuel"].to_numpy() > 0)
    assert partiel.any()
    for k in range(12):
        off = partiel & (((m >> k) & 1) == 0)
        assert (base[k][off] == 0).all()
    assert np.allclose(base.sum(axis=0)[prive], frame["salaire_brut_annuel"].to_numpy()[prive],
                       rtol=1e-5)
