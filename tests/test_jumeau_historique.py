"""But 23, lot 1 — l'état publié de 2010 à 2025 tient les identités du cadre (CADRE.md §6).

`etat_initial(annee)` lit les tables manifestées de l'Insee et d'Eurostat. Les identités
des emplois, des revenus, du compte des APU et des contributions tiennent à 1e-9 du PIB
chaque année ; celle de la dette, de 2021 à 2025, où Eurostat publie l'ajustement
flux-stocks, et refuse avant, en nommant « sfa ». Chaque écart publié que le cadre nomme
est lu, et ce qui le cause est vérifié ici (D-405).
"""

from __future__ import annotations

import numpy as np
import pytest

from impots.dette import comptes
from impots.dette.reference import start_from_accounts
from impots.jumeau import historique, identites
from impots.jumeau.blocs import ordre_lot1
from impots.jumeau.pas import Entrees
from impots.jumeau.trajectoire import calculer
from impots.predictif import annuel, rejouer

ANNEES = list(range(2010, 2026))
AVEC_SFA = [2021, 2022, 2023, 2024, 2025]

pytestmark = pytest.mark.skipif(
    not all((comptes.RAW / f).exists() for f in (
        comptes.PIB_FILE, comptes.TOTALS_FILE, comptes.APU_FILE, comptes.DETTE_FILE,
        comptes.SFA_FILE, historique.PIB_REVENUS_FILE)),
    reason="les tables de l'Insee et d'Eurostat ne sont pas dans ce checkout (data/raw est "
           "ignoré ; `impots data fetch`)")

SANS_DETTE = ("emplois", "revenus", "apu", "contributions")


@pytest.mark.parametrize("annee", ANNEES)
def test_l_etat_publie_tient_les_identites(annee) -> None:
    etat = historique.etat_initial(annee)
    if annee in AVEC_SFA:
        residus = identites.verifier(etat)
    else:
        residus = identites.verifier(etat, identites=SANS_DETTE)
        with pytest.raises(identites.IdentiteIncalculable, match="« sfa »"):
            identites.verifier(etat, identites=("dette",))
    assert max(abs(float(r[0])) for r in residus.values()) < 1e-9
    assert etat["pib"][0] > 1_900 and 0.8 < etat["ratio_dette"][0] < 1.2


def test_les_ecarts_publies_sont_ce_qu_ils_disent() -> None:
    """L'arrondi des totaux est sous la moitié du millième de chaque terme imprimé (le
    refus est dans `etat_initial`) ; la ventilation des secteurs ne s'écarte au-delà de
    l'arrondi de ses dix termes qu'en 2023 et 2024 ; l'écart de millésime de la dette ne
    dépasse le millième qu'en 2025, où il est l'écart entre la variation du stock de
    l'Insee et GD_CH d'Eurostat, B9 étant le même."""
    etats = {a: historique.etat_initial(a) for a in ANNEES}
    ventiles = sorted(a for a, e in etats.items()
                      if abs(e["ventilation_emplois"][0]) > 10 * historique.DEMI_MILLIEME)
    assert ventiles == [2023, 2024]
    millesime = sorted(a for a in AVEC_SFA
                       if abs(etats[a]["ecart_millesime_dette"][0]) > 1e-3)
    assert millesime == [2025]
    eurostat = historique._eurostat()[2025]
    assert eurostat["B9_T3"] == pytest.approx(-etats[2025]["b9"][0], abs=1e-9)
    variation = etats[2025]["dette"][0] - etats[2025]["dette_ouverture"][0]
    assert etats[2025]["ecart_millesime_dette"][0] == pytest.approx(
        variation - eurostat["GD_CH"], abs=1e-9)


def test_l_ajustement_de_comptes_est_celui_du_cadre() -> None:
    """ORADJ, le total des ajustements, contient K61 et KX : `comptes.sfa_publie` les
    comptait deux fois (D-405) ; corrigé par D-410, il est F_ASS + ORADJ + YA3, l'ajustement
    du cadre, à 1e-9 près. Sur l'ancienne somme, l'écart valait K61 + KX, de −510 à
    +483,5 M€ selon l'année."""
    publie = comptes.sfa_publie(AVEC_SFA)
    pib = comptes.gdp(AVEC_SFA)
    for annee in AVEC_SFA:
        sfa = historique.etat_initial(annee)["sfa"][0]
        assert publie[annee] * pib[annee] / 1e9 == pytest.approx(sfa, abs=1e-9)


def test_le_jumeau_part_de_2025_comme_la_chaine() -> None:
    """La référence du jumeau depuis l'état publié de 2025 est celle de `rejouer`
    depuis `start_from_accounts(2025)`, à 1e-9 : même départ, mêmes règles."""
    depart = historique.etat_initial(2025)
    start = start_from_accounts(2025)
    annees = list(range(2026, 2036))
    rejeu = {"start": annuel._start(start),
             "cadre": {"growth": {"real": 0.01, "prices": 0.02},
                       "spending": {"rule": "gele_en_volume", "growth": None},
                       "taux": {"kind": "implicite_tenu", "market_rate": None,
                                "reference": [start.implicit_rate] * 10,
                                "marginal": start.implicit_rate}}}
    _, attendu, _ = rejouer.reference_path(rejeu, rejeu["start"], len(annees))
    jumeau = calculer(depart, entrees=Entrees.depuis_rejeu(rejeu, annees), mesures=[],
                      theta={}, blocs=ordre_lot1(depart, persistance="lue", boucle=False))
    reference, _ = jumeau.niveaux("ratio_dette")
    assert np.max(np.abs(reference[:, 0] - np.array(attendu))) < 1e-9
