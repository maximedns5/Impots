"""La dimension de la santé (but 29, volet `sante`, D-620 à D-624) : les nombres que tiennent
ses coefficients, sur une trajectoire et des cellules synthétiques, et le contrôle de
l'état de départ sur les cellules commitées."""

from __future__ import annotations

import numpy as np
import pytest

from impots.jumeau import impacts
from impots.jumeau.impacts import sante

P = sante.charger()


class FauxEtat:
    def __init__(self, annee: int, valeurs: dict[str, float]) -> None:
        self.annee = annee
        self.v = {k: np.array([float(x)]) for k, x in valeurs.items()}

    def present(self, nom: str) -> bool:
        return nom in self.v

    def __getitem__(self, nom: str) -> np.ndarray:
        return self.v[nom]


class FaussesCellules:
    """Dix déciles, cinq cellules chacun (la première pleine), niveau de vie 1 à 10."""

    def __init__(self) -> None:
        z = np.zeros(50)
        pers = z.copy()
        pers[::5] = 5.5e6  # 55 millions de personnes, autant par décile
        self.v = {"personnes": pers,
                  "revenu_disponible": np.where(pers > 0, np.repeat(np.arange(1.0, 11.0), 5),
                                                1.0),
                  "uc": np.ones(50)}

    def __getitem__(self, nom: str) -> np.ndarray:
        return self.v[nom]

    def par_decile(self, nom: str) -> np.ndarray:
        return self.v[nom].reshape(10, 5).sum(axis=1)


def etat(annee: int, rdb: float, chomage: float) -> FauxEtat:
    v = {f"rdb_d{d:02d}": rdb * d for d in range(1, 11)}
    v |= {"chomage": chomage, "population_active": 30000.0, "ecart_prix_consommation": 0.0}
    return FauxEtat(annee, v)


def test_le_gradient_de_l_insee():
    # (84,4 − 71,7) / ln(5 800 / 470) et (88,3 − 80,0) / ln(5 800 / 470)
    assert sante.gradient(P, "hommes") == pytest.approx(5.0540, abs=1e-4)
    assert sante.gradient(P, "femmes") == pytest.approx(3.3030, abs=1e-4)
    assert sante.gradient(P) == pytest.approx(4.1785, abs=1e-4)


def test_les_canaux_a_la_main():
    cel = FaussesCellules()
    ref = [etat(2026, 10.0, 2400.0), etat(2027, 10.0, 2400.0)]
    var = [etat(2026, 10.1, 2430.0), etat(2027, 10.1, 2430.0)]  # +1 %, 30 000 chômeurs
    da = np.array([0.0, 1.0])  # un an de départ plus tardif la deuxième année
    d = sante.dimension(var, ref, None, cel, params=P, ecart_age=da)
    assert d.statut == "illustratif"
    ind = {i.cle: i for i in d.indicateurs}
    s, g = 1 / 12, sante.gradient(P)
    ev = 12 * s * g * np.log(1.01)  # mois
    assert ind["esperance_de_vie"].valeurs == pytest.approx([ev, ev])
    # le chômage : 30 000 × 0,002594 × 0,30 décès de plus, × 31,19 années
    deces_chom = -30000 * 0.002594 * 0.30
    # le revenu : décès répartis selon le gradient, Δln μ = −s g ln 1,01 / e†
    ln = np.log(np.arange(1.0, 11.0))
    deces_rev = 643332 * (1 - np.exp(-s * g * np.log(1.01) / 10.57))
    assert ind["deces_evites"].valeurs == pytest.approx(
        [deces_rev + deces_chom] * 2, rel=1e-9)
    assert ind["bonne_sante"].valeurs == pytest.approx(
        [-30000 * 0.143 * 0.25 / 1e3] * 2)
    # le renoncement : 0,5 × (pente médicale + dentaire) × ln 1,01 × 45 millions d'adultes
    lnq = (ln[-2:].mean() - ln[:2].mean())
    b = (3.9 - 0.4) / lnq + (9.2 - 1.5) / lnq
    assert ind["renoncements_evites"].valeurs == pytest.approx(
        [0.5 * b / 100 * np.log(1.01) * 0.8183 * 55e6 / 1e3] * 2)
    # l'âge : −0,5 × 1 an × 840 764 années de retraite, dont 0,70 sans limitation
    rt = ind["retraite_sans_limitation"]
    assert rt.valeurs == pytest.approx([0.0, -0.5 * 840764 * 0.70 / 1e3])
    assert rt.bas[1] == pytest.approx(-1.0 * 840764 * 0.89 / 1e3)
    assert rt.haut[1] == pytest.approx(-0.25 * 840764 * 0.70 / 1e3)
    vie = ind["annees_de_vie"]
    assert vie.par_groupe["l'âge de départ"] == pytest.approx([0.0, 0.0])
    assert vie.haut[1] - vie.bas[1] > 2 * 0.1 * 840764 / 1e3 * 0.99
    assert vie.par_groupe["le chômage"] == pytest.approx([deces_chom * 31.19 / 1e3] * 2)


def test_l_ecart_d_age_des_programmes():
    an = list(range(2026, 2036))
    m = sante.ecart_age_legal(P, "melenchon", an)
    assert m[0] == 0.0 and m[1] == pytest.approx(-0.75)
    assert m[6] == pytest.approx(-3.75) and m[7:] == pytest.approx([-4.0] * 3)
    r = sante.ecart_age_legal(P, "retailleau", an)
    assert r[:3] == pytest.approx([0, 0, 0]) and r[3] == pytest.approx(-0.25)
    assert r[7:] == pytest.approx([-1.0] * 3)
    assert sante.ecart_age_legal(P, "attal", an) == pytest.approx([0.0] * 10)
    ph = sante.ecart_age_legal(P, "philippe", an)
    assert ph[1] == pytest.approx(0.25) and ph[-1] == pytest.approx(0.75)


def test_inscrite():
    assert "sante" in impacts.dimensions()


def test_controle_depart_sur_les_cellules_commitees():
    """D-621 : l'écart d'espérance de vie D10 − D1 que g implique sur les cellules de
    `entrees_navigateur.json` (population de D-687 ; sur celle de D-553 : 2,0780, 10,502,
    6,864, D-693), face à l'Insee Première n° 1687."""
    import json

    from impots.jumeau.cellules import Cellules
    from impots.jumeau.navigateur import FICHIER

    c = json.loads(FICHIER.read_text(encoding="utf-8"))["cellules"]
    cel = Cellules(valeurs={k: np.asarray(v, float) for k, v in c["valeurs"].items()},
                   parts_offre=c["parts_offre"])
    out = sante.controle_depart(cel, P)
    assert out["ecart_ln_d10_d1"] == pytest.approx(2.0835, abs=5e-4)
    assert out["hommes"]["d10_d1"] == pytest.approx(10.530, abs=5e-3)
    assert out["femmes"]["d10_d1"] == pytest.approx(6.882, abs=5e-3)
    # Le juge (ip1687.xls, figure 1) : vingtiles 19-20 moins 1-2.
    assert 0.8 <= out["hommes"]["d10_d1"] / 11.65 <= 1.2
    assert 0.8 <= out["femmes"]["d10_d1"] / 7.55 <= 1.2


def _cellules_commitees():
    import json

    from impots.jumeau.cellules import Cellules
    from impots.jumeau.navigateur import FICHIER

    c = json.loads(FICHIER.read_text(encoding="utf-8"))["cellules"]
    return Cellules(valeurs={k: np.asarray(v, float) for k, v in c["valeurs"].items()},
                    parts_offre=c["parts_offre"])


def test_le_revenu_du_chomage_ne_compte_pas_deux_fois():
    """D-639 : le revenu que le jumeau donne aux déciles pour les chômeurs qui retrouvent
    un emploi sort du canal du revenu vers la durée de vie ; le canal du chômage (Sullivan
    et von Wachter, perte de revenu comprise) le compte déjà. Avant : compté deux fois."""
    from impots.jumeau.blocs import menages as M

    cel = _cellules_commitees()
    depart = FauxEtat(2025, {"remunerations": 1500.0, "pib": 3000.0})

    def e(rdb, chom, emp):
        x = etat(2026, rdb, chom)
        x.v |= {"pib": np.array([3000.0]), "emploi_total": np.array([emp]),
                "emploi_salarie": np.array([emp - 3000.0])}
        return x

    ref = [e(100.0, 2400.0, 30000.0)]
    var = [e(101.0, 2300.0, 30100.0)]  # 100 000 chômeurs de moins, autant d'emplois
    o = sante.revenu_du_chomage(var, ref, depart, cel)
    p = M.charger()
    st = M.structure(cel, p.pib_cellules)
    r = M.reference(p, depart, np.array([3000.0]))
    a_la_main = (st.rho * st.part_chomeurs * p.part_marchande * float(r.d1[0]) * 100.0
                 / r.emploi_marchand
                 - st.part_chomeurs * st.allocation_sur_salaire * float(r.salaire[0])
                 * 100.0 * 1e3 / 1e9)
    np.testing.assert_allclose(o[0], np.bincount(st.decile, weights=a_la_main,
                                                 minlength=10), rtol=1e-12)
    assert o.sum() > 0.0
    avec = sante.dimension(var, ref, depart, cel, params=P)
    sans = sante.dimension(var, ref, None, cel, params=P)
    vie = {d: {i.cle: i for i in x.indicateurs}["annees_de_vie"] for d, x in
           (("avec", avec), ("sans", sans))}
    assert vie["avec"].par_groupe["le revenu réel"][0] < vie["sans"].par_groupe[
        "le revenu réel"][0]
    assert vie["avec"].par_groupe["le chômage"][0] == vie["sans"].par_groupe["le chômage"][0]
    # Des actifs en plus (l'emploi et le chômage montent ensemble) : rien à retirer.
    var2 = [e(101.0, 2500.0, 30100.0)]
    assert not sante.revenu_du_chomage(var2, ref, depart, cel).any()
