"""Les allègements généraux, leur champ et leur proratisation (but 19, étape « alleg »).

Cinq personnes du privé, droit 2024 : un salarié à temps plein, un mi-temps payé deux
SMIC de l'heure, un gérant majoritaire et un salarié d'un particulier au SMIC, un salarié
payé six mois au SMIC. Avant l'étape, le mi-temps était lu à temps plein (un SMIC par
mois, toute la réduction générale), et le gérant et le salarié du particulier recevaient
les allègements que la loi ne leur donne pas (CSS art. L. 241-13, II). Vus échouer sur le
câblage d'avant, sauf le dernier, qui tenait déjà : le SMIC d'un salarié payé six mois
est celui de ses six mois, parce qu'openfisca calcule chaque mois sur le SMIC du mois.
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl
import pytest

from impots.engine import system
from impots.population.to_openfisca import build_simulation

YEAR = 2024
#: Le SMIC brut d'un mois à temps plein de janvier à octobre 2024 : 11,65 € pour 151,67
#: heures (11,88 € en novembre et décembre). Un salaire d'un SMIC de janvier par mois est
#: au plus au SMIC de chaque mois de l'année.
SMIC = 11.65 * 151.67
SMIC_ANNUEL = 12 * SMIC
#: Le coefficient maximal de la réduction générale en 2024 (moins de 50 salariés).
T_MAX = 0.3194
SIX_MOIS = (1 << 6) - 1


def _frame(salaires: list[float], **over) -> pl.DataFrame:
    n = len(salaires)
    columns = {
        "person_id": [f"p{i}" for i in range(n)], "household_id": [f"m{i}" for i in range(n)],
        "foyer_id": [f"f{i}" for i in range(n)], "famille_id": [f"a{i}" for i in range(n)],
        "age": [40] * n, "role_menage": ["personne_de_reference"] * n,
        "role_foyer": ["declarant_principal"] * n, "role_famille": ["demandeur"] * n,
        "salaire_brut_annuel": salaires, "pension_annuelle": [0.0] * n,
        "chomage_annuel": [0.0] * n, "statut_occupation": ["proprietaire"] * n,
        "zone_apl": ["zone_2"] * n, "loyer_mensuel": [0.0] * n, "parent_isole": [False] * n,
        "secteur_public": [False] * n, "fonction_publique": [None] * n,
        "titulaire": [False] * n, "quotite_travail": [1.0] * n,
        "regime_non_salarie": [None] * n, "revenu_non_salarie_annuel": [0.0] * n,
        "secteur_non_salarie": [None] * n, "particulier_employeur": [False] * n,
        "mois_travailles": [(1 << 12) - 1] * n}
    columns.update(over)
    return pl.DataFrame(columns).with_columns(
        pl.col("regime_non_salarie", "secteur_non_salarie", "fonction_publique").cast(pl.String))


def _add(frame: pl.DataFrame, variable: str) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sim = build_simulation(frame, system.baseline(), YEAR).simulation
        return np.asarray(sim.calculate_add(variable, str(YEAR)))


def test_a_half_timer_at_twice_the_smic_an_hour_has_no_reduction_generale() -> None:
    """À mi-temps, payé deux SMIC de l'heure : un SMIC par mois. Son SMIC proratisé est un
    demi-SMIC, son salaire en vaut deux, au-delà de 1,6 : pas de réduction générale ; sous
    2,5 et 3,5, les deux bandeaux, 6 et 1,8 % du brut. À temps plein au même salaire du
    mois, la réduction générale entière."""
    frame = _frame([SMIC_ANNUEL, SMIC_ANNUEL], quotite_travail=[1.0, 0.5])
    general = _add(frame, "allegement_general")
    assert general[0] == pytest.approx(T_MAX * SMIC_ANNUEL, rel=1e-3)
    assert general[1] == 0.0
    assert _add(frame, "allegement_cotisation_maladie")[1] == pytest.approx(
        0.06 * SMIC_ANNUEL, rel=1e-6)
    assert _add(frame, "allegement_cotisation_allocations_familiales")[1] == pytest.approx(
        0.018 * SMIC_ANNUEL, rel=1e-6)


def test_a_part_timer_above_the_prorated_ceiling_loses_the_bandeau_maladie() -> None:
    """À 40 %, payé trois SMIC de l'heure : 1,2 SMIC par mois, sous 2,5 SMIC à temps plein,
    mais trois fois son SMIC proratisé, au-delà de 2,5 (et du seuil gelé de décembre
    2023) : ni réduction générale ni bandeau maladie ; le bandeau famille, sous 3,5."""
    salaire = 1.2 * SMIC_ANNUEL
    frame = _frame([salaire], quotite_travail=[0.4])
    assert _add(frame, "allegement_general")[0] == 0.0
    assert _add(frame, "allegement_cotisation_maladie")[0] == 0.0
    assert _add(frame, "allegement_cotisation_allocations_familiales")[0] == pytest.approx(
        0.018 * salaire, rel=1e-6)


def test_a_gerant_and_a_private_person_s_employee_give_no_allegement() -> None:
    frame = _frame([SMIC_ANNUEL] * 3, regime_non_salarie=[None, "gerant_bic", None],
                   particulier_employeur=[False, False, True])
    for variable, rate in (("allegement_general", T_MAX),
                           ("allegement_cotisation_maladie", 0.06),
                           ("allegement_cotisation_allocations_familiales", 0.018)):
        amount = _add(frame, variable)
        assert amount[0] == pytest.approx(rate * SMIC_ANNUEL, rel=1e-3)
        assert amount[1] == 0.0 and amount[2] == 0.0


def test_an_employee_paid_six_months_has_the_smic_of_six_months() -> None:
    """Payé six mois au SMIC du mois (janvier à juin) : la réduction générale entière sur ce
    qu'il gagne, le SMIC de référence n'étant que celui des mois payés. Lu sur douze mois,
    il serait à un demi-SMIC, au même taux plafonné ; payé deux SMIC par mois sur six mois,
    il n'en a pas, ce qu'un SMIC de douze mois lui aurait donné."""
    six = 6 * SMIC
    frame = _frame([six, 2 * six], mois_travailles=[SIX_MOIS, SIX_MOIS])
    general = _add(frame, "allegement_general")
    assert general[0] == pytest.approx(T_MAX * six, rel=1e-3)
    assert general[1] == 0.0
