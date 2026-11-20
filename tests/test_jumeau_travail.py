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


def test_la_loi_absorbe_le_bas_pour_une_grande_hausse():
    """Sous l'ancienne forme (e(m), m en Smic d'avant) : une hausse de 2 % diffuse au bas
    (0,37 % de la hausse en masse brute, zéro avec la loi seule) ; celle de Mélenchon
    (+16,17 %) relève par la loi tous les postes où le bas diffuse : à θ 0, rien ne reste
    à la diffusion (D-533, l'écart de forme 1). Sous le défaut de D-551, le recentrage,
    le bas diffuse au-dessus du nouveau Smic : 0,87 % pour 2 %, 1,25 % pour Mélenchon."""
    with travail.formes(recentrage="ancien"):
        p = travail.charger()
    petite = travail.cascade(p, 1.02, 0.0)
    part = petite.b_diff[:, 0].sum() / petite.brut[:, 0].sum() / 0.02
    assert part == pytest.approx(0.0037, abs=5e-4)
    grande = travail.cascade(p, SMIC_MELENCHON, 0.0)
    assert grande.b_diff[:, 0].sum() == 0.0
    q = travail.charger()
    petite = travail.cascade(q, 1.02, 0.0)
    assert petite.b_diff[:, 0].sum() / petite.brut[:, 0].sum() / 0.02 == pytest.approx(
        0.0087, abs=5e-4)
    grande = travail.cascade(q, SMIC_MELENCHON, 0.0)
    assert grande.b_diff[:, 0].sum() / grande.brut[:, 0].sum() / (
        SMIC_MELENCHON - 1.0) == pytest.approx(0.0125, abs=5e-4)


# ------------------------------------------------------------- l'interaction (D-540)
class _Mesure:
    def __init__(self, ident, travail_):
        self.identifiant, self.travail, self.impulsions = ident, travail_, {}


@pytest.mark.parametrize("recentrage, rapport", [("ancien", 0.886), ("nouveau", 1.181)])
def test_deux_hausses_du_smic_ne_se_somment_pas(recentrage, rapport):
    """Le choc combiné (D-540) : deux hausses de 8 % font une hausse de 16,64 %, que la
    diffusion lit d'un coup (w = max(m (1 + e g), 1 + g)) ; la somme de leurs effets
    séparés n'en est pas la valeur. Sous l'ancienne forme, 0,886 de la somme au centre :
    la loi de la seconde hausse absorbe une part de la diffusion de la première. Sous le
    recentrage (le défaut, D-551), 1,181 : la diffusion suit le Smic, et la bande qui
    diffuse monte vers des salaires plus hauts. Le partage de Shapley rend chacune à la
    moitié du tout, et une mesure seule garde sa valeur d'avant."""
    with travail.formes(recentrage=recentrage):
        p = travail.charger()
    bloc = travail.Travail(params=p)
    t = np.array([0.5])
    spec = {"smic": 1.08, "passe": True}
    seul = bloc._valeur([(spec, 1)], t)
    deux = bloc._valeur([(spec, 1), (spec, 1)], t)
    somme = 2.0 * seul[0].sum()
    assert deux[0].sum() != pytest.approx(somme, rel=1e-3)
    assert deux[0].sum() / somme == pytest.approx(rapport, abs=2e-3)
    parts = bloc._partage({"a": (spec, 1), "b": (spec, 1)}, t)
    assert parts["a"][0].sum() == pytest.approx(deux[0].sum() / 2.0)
    assert bloc._partage({"a": (spec, 1)}, t)["a"][0].sum() == seul[0].sum()


def test_le_seuil_d_une_mesure_ne_touche_que_les_salaires_qu_il_coupe(p):
    """Un seuil de sortie à 2 Smic (la fin des exonérations de Mélenchon) retire
    l'allègement de 2 à 3 Smic seulement, la formule gardant son 3 (openfisca) ; une
    hausse du Smic qui diffuse sous 1,5 Smic d'avant n'en change pas la diffusion :
    l'interaction est nulle au réglage par défaut."""
    x = np.array([1.0, 1.5, 1.99, 2.0, 2.5, 3.0])
    assert np.array_equal(travail.rgdu(p, x, 2.0)[:3], travail.rgdu(p, x)[:3])
    assert not travail.rgdu(p, x, 2.0)[3:].any()
    retire = travail.allegement_retire(p, 2.0)
    assert retire[:2].sum() == 0.0 and retire[2:4].all()
    bloc = travail.Travail(params=p)
    t = np.array([0.5])
    smic = {"smic": SMIC_MELENCHON, "passe": True}
    exo = {travail.ALLEGEMENTS: {"plafond": 2.0}, "passe": True}
    parts = bloc._partage({"smic": (smic, 1), "exo": (exo, 1)}, t)
    seul = bloc._valeur([(smic, 1)], t)
    assert set(parts) == {"smic", "exo"}
    assert np.allclose(parts["exo"][1], 0.0)
    assert np.allclose(parts["smic"][1], seul[1])


def test_le_recentrage_porte_la_diffusion_de_melenchon(p):
    """La forme `recentrage` « nouveau » (D-540, l'écart 1 de D-533), le défaut depuis
    D-551 (décision du propriétaire) : la diffusion du Smic de Mélenchon, en part de la
    hausse de la masse brute, est 0,109 au centre, contre 0,061 sous l'ancienne forme
    (D-534) ; les autres formes gardent leur défaut."""
    def part(q):
        c = travail.cascade(q, SMIC_MELENCHON, 0.5)
        return c.b_diff[:, 0].sum() / c.brut[:, 0].sum() / (SMIC_MELENCHON - 1.0)

    assert p.formes["recentrage"] == "nouveau"
    assert p.formes["profil"] == "tenu" and p.formes["portee"] == "1,5"
    assert part(p) == pytest.approx(0.109, abs=2e-3)
    with travail.formes(recentrage="ancien"):
        q = travail.charger()
    assert part(q) == pytest.approx(0.061, abs=2e-3)
