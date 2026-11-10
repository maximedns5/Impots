"""La part exonérée d'impôt des salaires (but 19, étape « ir », correction 24).

D11, sur lequel la masse salariale est calée, compte des salaires que l'impôt exonère
(heures supplémentaires, apprentis, épargne salariale placée…) : la population porte la part
exonérée de chaque salaire, et seul l'impôt la lit.
"""

from __future__ import annotations

import numpy as np
import pytest
from openfisca_core.simulation_builder import SimulationBuilder

from impots.engine.system import baseline


def _single(share: float, monthly_gross: float = 3_000.0) -> object:
    case = {"individus": {"a": {"date_naissance": {"ETERNITY": "1980-01-01"}}},
            "foyers_fiscaux": {"f": {"declarants": ["a"]}},
            "familles": {"fa": {"parents": ["a"]}},
            "menages": {"m": {"personne_de_reference": ["a"]}}}
    simulation = SimulationBuilder().build_from_entities(baseline(), case)
    for month in range(1, 13):
        simulation.set_input("salaire_de_base", f"2024-{month:02d}", np.array([monthly_gross]))
    simulation.set_input("part_salaire_exoneree_ir", "2024", np.array([share]))
    return simulation


def test_the_exempt_share_comes_off_the_declared_salary_before_the_deduction() -> None:
    """Un salarié dont 10 % du salaire imposable est exonéré déclare 90 % de ce salaire, et
    la déduction de 10 % tombe sur ce qu'il déclare. Échoue sur le code d'avant : la variable
    n'existait pas, et openfisca imposait tout le salaire."""
    whole, exempt = _single(0.0), _single(0.1)
    taxable = float(whole.calculate_add("salaire_imposable", "2024")[0])
    assert float(exempt.calculate_add("salaire_imposable", "2024")[0]) == taxable
    declared = 0.9 * taxable
    assert float(exempt.calculate("revenu_categoriel_tspr", "2024")[0]) == pytest.approx(
        declared - round(0.1 * declared), abs=1.0)
    assert float(whole.calculate("revenu_categoriel_tspr", "2024")[0]) == pytest.approx(
        taxable - round(0.1 * taxable), abs=1.0)
    assert exempt.calculate("ip_net", "2024")[0] < whole.calculate("ip_net", "2024")[0]


def test_nothing_but_the_income_tax_reads_the_exempt_share() -> None:
    """La CSG, le salaire net et la prime d'activité lisent le salaire entier."""
    whole, exempt = _single(0.0, 1_900.0), _single(0.1, 1_900.0)
    for variable in ("csg_deductible_salaire", "salaire_net", "ppa"):
        assert exempt.calculate_add(variable, "2024") == pytest.approx(
            whole.calculate_add(variable, "2024")), variable
