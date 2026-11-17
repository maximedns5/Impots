"""Le bloc `travail` du jumeau : la diffusion des hausses du Smic sourcée (D-533)."""

from __future__ import annotations

import numpy as np
import pytest

from impots.jumeau.blocs import travail

#: Le Smic de Mélenchon, 1 700 € net (D-507) : le coefficient de sa passe.
SMIC_MELENCHON = 1.1617


@pytest.fixture(scope="module")
def p() -> travail.Parametres:
    return travail.charger()


def test_le_bas_de_la_diffusion_est_goarant_muller(p):
    """θ 0 : 0,16 entre 1 et 1,1 Smic, rien au-delà (Goarant et Muller, fig. 11), et non
    plus la loi seule ; θ ½ reste Koubi et Lhommeau sans effets fixes."""
    e0 = travail.diffusion(p, np.array([0.0]))[:, 0]
    dans = (p.multiples >= 1.0) & (p.multiples < 1.1)
    assert dans.any()
    assert np.allclose(e0[dans], 0.16)
    assert np.allclose(e0[~dans], 0.0)
    e_demi = travail.diffusion(p, np.array([0.5]))[:, 0]
    assert e_demi[dans][0] == pytest.approx(0.473)


def test_la_loi_absorbe_le_bas_pour_une_grande_hausse(p):
    """Une hausse de 2 % diffuse au bas (0,37 % de la hausse en masse brute, zéro avec la
    loi seule) ; celle de Mélenchon (+16,17 %) relève par la loi tous les postes où le bas
    diffuse : à θ 0, rien ne reste à la diffusion (D-533, l'écart de forme 1)."""
    petite = travail.cascade(p, 1.02, 0.0)
    part = petite.b_diff[:, 0].sum() / petite.brut[:, 0].sum() / 0.02
    assert part == pytest.approx(0.0037, abs=5e-4)
    grande = travail.cascade(p, SMIC_MELENCHON, 0.0)
    assert grande.b_diff[:, 0].sum() == 0.0
