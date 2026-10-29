"""Le calendrier du prélèvement à la source (D-291) : l'effet budgétaire d'une année, depuis
les effets en année pleine des années de revenus.

Une mesure d'impôt sur le revenu qui vaut à partir des revenus N0 pèse sur l'année Y par le
solde des avis sur les revenus Y−1, et par le PAS de Y, dont le taux de janvier à août vient
des revenus Y−2 et celui de septembre à décembre des revenus Y−1. Le modèle est validé hors
échantillon sur la seule chronique que l'annexe du PLF 2027 publie pour une mesure de ce
calendrier, l'art. 3 : 1,4 Md€ en 2027, 1,8 Md€ en 2028, 1,1 Md€ à compter de 2029.
"""

from __future__ import annotations

import pytest

from impots import pas

#: PLF 2027, évaluations préalables, art. 3, § 4.2, p. 36.
ART3 = {2027: 1.4e9, 2028: 1.8e9, 2029: 1.1e9}
ART3_FULL_YEAR = 1.1e9


def test_the_first_year_is_the_full_year_of_the_avis_and_a_third_of_the_pas() -> None:
    effects = pas.budget_effects({2026: 3.0e9, 2027: 3.3e9, 2028: 3.6e9, 2029: 3.9e9},
                                 first_income_year=2026, years=(2026, 2027, 2028, 2029))
    assert effects[2026] == 0.0
    assert effects[2027] == pytest.approx(3.0e9 + 3.3e9 * 4 / 12)
    assert effects[2028] == pytest.approx(3.3e9 * 8 / 12 + 3.6e9)
    assert effects[2029] == pytest.approx(3.9e9)


def test_a_measure_in_force_long_enough_weighs_its_full_year() -> None:
    effects = pas.budget_effects({y: 1.0e9 for y in range(2020, 2031)},
                                 first_income_year=2020, years=range(2023, 2031))
    assert all(v == pytest.approx(1.0e9) for v in effects.values())


def test_the_published_chronicle_of_art_3_is_given_back_within_five_percent() -> None:
    effects = pas.budget_effects({y: ART3_FULL_YEAR for y in range(2026, 2030)},
                                 first_income_year=2026, years=tuple(ART3))
    for year, published in ART3.items():
        assert abs(effects[year] / published - 1) < 0.05, (year, effects[year])
    assert effects[2029] == ART3[2029]


@pytest.mark.parametrize("months", [0, 13, 4.5])
def test_months_outside_a_year_are_refused(months) -> None:
    with pytest.raises(pas.PasError, match="mois"):
        pas.budget_effects({2026: 1.0}, first_income_year=2026, years=(2027,),
                           months_updated=months)


def test_an_income_year_the_measure_covers_but_the_effects_lack_is_refused() -> None:
    with pytest.raises(pas.PasError, match=r"\[2027\]"):
        pas.budget_effects({2026: 1.0e9}, first_income_year=2026, years=(2027,))


def test_the_ratio_of_the_first_year_to_the_full_year_is_four_thirds() -> None:
    assert pas.first_year_ratio() == pytest.approx(4 / 3)
    assert pas.first_year_ratio(months_updated=3) == pytest.approx(1.25)
