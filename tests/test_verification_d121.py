"""La grille compare ce qu'elle doit (but 19, étape 1) : les cotisations des employeurs au
sens D121, l'IR net d'une passe imputée, l'année des impôts des entreprises. Sans passe :
l'arithmétique de la grille, sur des totaux posés."""

from __future__ import annotations

import pytest

from impots import verification


def test_d121_is_super_brut_minus_brut_minus_three_things_each_shown_apart() -> None:
    """Les nombres du diagnostic (2024, échantillon, Md€) : 428,9 − 17,4 − 77,3 − 2,9 =
    331,3. La mesure de D-363 reste à côté, inchangée."""
    t = {"salaire_super_brut": 1_540.6e9, "salaire_brut": 1_111.7e9,
         "prelevements_salaires_d291": 17.4e9, "pension_employeur_etat": 77.3e9,
         "remuneration_hors_brut": 2.9e9}
    m = verification.employeurs(t)
    key = "salaire_super_brut - salaire_brut - D291 - pension de l'État - hors brut"
    assert m[key] == pytest.approx(331.3e9)
    assert m["prelevements_salaires_d291"] == 17.4e9
    assert m["pension_employeur_etat"] == 77.3e9
    assert m["remuneration_hors_brut"] == 2.9e9


def test_the_capital_is_aged_by_the_published_hors_bareme_tax() -> None:
    assert verification.indice_capital(2024) is None
    assert verification.indice_capital(2023) == pytest.approx(7.602575235 / 10.32)
    assert verification.indice_capital(2022) == pytest.approx(7.505 / 10.32)
    with pytest.raises(verification.VerificationError):
        verification.indice_capital(2021)
