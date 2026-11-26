"""But 28, volet `boucle` — la boucle population ↔ jumeau (`jumeau.boucle`, D-545).

Sur une petite population factice et les cellules synthétiques de `test_jumeau_menages`
(aucune donnée, aucune passe) :

1. la transition : un chômeur devient salarié à son taux mensuel, ou à celui d'un
   donneur ; ses personnes-années gagnées ; les autres membres ne bougent pas ;
2. les coefficients d'une passe, par personne-année, en part du salaire moyen ;
3. avec les coefficients du forfait, le jumeau est celui d'avant, au bit : la boucle
   remplace, elle n'ajoute pas (le double compte) ;
4. une allocation chômage perdue plus grosse que le forfait se lit exactement dans la
   dépense de la première année, et les identités tiennent.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import polars as pl
import pytest

from impots.jumeau import boucle
from impots.jumeau.blocs.menages import reference, structure
from impots.jumeau.cellules import N_CELLULES
from test_jumeau_menages import CELLULES, PARAMS, _hausse_cotisations, _jumeau, _theta

ST = structure(CELLULES, PARAMS.pib_cellules)


def _population() -> pl.DataFrame:
    """Trois ménages : un chômeur qui a travaillé trois mois (2 000 € par mois), une
    chômeuse sans salaire dans l'année, un salarié."""
    lignes = [
        # person, ménage, âge, sexe, statut, salaire, chômage, masque
        (1, "A", 30, "male", "unemployed", 6_000.0, 9_000.0, 0b111),
        (2, "A", 31, "female", "employed", 24_000.0, 0.0, 0xFFF),
        (3, "B", 40, "male", "unemployed", 0.0, 12_000.0, 0xFFF),
        (4, "C", 50, "male", "employed", 40_000.0, 0.0, 0xFFF),
    ]
    p, h, a, s, st, sal, ch, mo = zip(*lignes, strict=True)
    return pl.DataFrame({
        "person_id": list(p), "household_id": list(h),
        "foyer_id": [f"{x}#0" for x in h], "famille_id": [f"{x}#0" for x in h],
        "weight": [100.0, 100.0, 200.0, 300.0], "age": list(a), "sex": list(s),
        "statut_activite": list(st), "is_salarie": [False, True, False, True],
        "salaire_brut_annuel": list(sal), "chomage_annuel": list(ch),
        "mois_travailles": list(mo)})


def test_un_chomeur_devient_salarie_a_son_taux_ou_a_celui_d_un_donneur() -> None:
    f = _population()
    taux = boucle.taux_mensuels(f)
    assert taux[0] == pytest.approx(2_000.0)
    assert taux[2] == pytest.approx(2_000.0)  # le seul donneur de son sexe
    assert np.isnan(taux[1]) and np.isnan(taux[3])
    v, liens = boucle.variantes(f)
    assert liens["annees"].to_list() == pytest.approx([0.75, 1.0])
    assert liens["salaire_brut"].to_list() == pytest.approx([24_000.0, 24_000.0])
    a = v.filter(pl.col("household_id") == liens["household_id"][0]).sort("person_id")
    assert a["statut_activite"].to_list() == ["employed", "employed"]
    assert a["salaire_brut_annuel"].to_list() == pytest.approx([24_000.0, 24_000.0])
    assert a["chomage_annuel"].to_list() == [0.0, 0.0]
    assert a["mois_travailles"].to_list() == [0xFFF, 0xFFF]
    assert set(v["person_id"].to_list()).isdisjoint(f["person_id"].to_list())


def _menages(ids, sb, net, csg, ir, ch, ppa, rd) -> pl.DataFrame:
    n = len(ids)
    z = [0.0] * n
    return pl.DataFrame({"household_id": ids, "salaire_super_brut": sb,
                         "salaire_net": net, "csg_deductible": csg, "csg_imposable": z,
                         "crds": z, "ir": ir, "csg_chomage": z, "chomage_brut": ch,
                         "ppa": ppa, "revenu_disponible": rd})


def test_les_coefficients_d_une_passe_par_personne_annee() -> None:
    orig = _menages(["A", "B"], [30_000.0, 0.0], [20_000.0, 0.0], [2_000.0, 0.0],
                    [500.0, 0.0], [9_000.0, 12_000.0], [0.0, 0.0], [28_500.0, 12_000.0])
    var = _menages(["vA", "vB"], [60_000.0, 30_000.0], [40_000.0, 20_000.0],
                   [4_000.0, 2_000.0], [2_000.0, 0.0], [0.0, 0.0], [0.0, 1_000.0],
                   [38_000.0, 21_000.0])
    liens = pl.DataFrame({"household_id": ["vA", "vB"], "origine": ["A", "B"],
                          "person_id": [1, 3], "annees": [0.5, 1.0],
                          "salaire_brut": [24_000.0, 24_000.0]})
    c = boucle.coefficients(orig, var, liens, {"A": 3, "B": 7}, 50_000.0,
                            {"A": 100.0, "B": 100.0})
    emplois = 150.0
    assert c.super_brut == pytest.approx(100.0 * (30_000 + 30_000) / emplois / 50_000)
    assert c.d61 == pytest.approx(100.0 * (8_000 + 8_000) / emplois / 50_000)
    assert c.d5 == pytest.approx(100.0 * (3_500 + 2_000) / emplois / 50_000)
    assert c.chomage == pytest.approx(-100.0 * 21_000 / emplois / 50_000)
    assert c.prestations == pytest.approx(100.0 * 1_000 / emplois / 50_000)
    assert c.rd == pytest.approx(100.0 * 18_500 / emplois / 50_000)
    assert c.meta["residu"] == pytest.approx(0.0)
    assert c.rd_cellules[3] == pytest.approx(100.0 * 9_500 / emplois / 50_000)
    assert c.rd_cellules.shape == (N_CELLULES,)


def _traj(coef, depart=False):
    m = _hausse_cotisations()
    if coef is not None:
        m = dataclasses.replace(m, boucle=coef)
    t, d = _jumeau([m], _theta(0.5))
    return (t, d) if depart else t


def test_avec_le_forfait_la_boucle_ne_change_rien() -> None:
    avant, apres = _traj(None), _traj(boucle.forfait(ST))
    for c in ("b9", "c_menages", "emploi_salarie", "remunerations", "apu_d_d62"):
        np.testing.assert_allclose(apres.difference(c), avant.difference(c), rtol=0,
                                   atol=1e-12)


def test_une_allocation_perdue_plus_grosse_se_lit_dans_la_depense() -> None:
    f = boucle.forfait(ST)
    coef = dataclasses.replace(f, chomage=f.chomage - 0.2)
    avant, (apres, depart) = _traj(None), _traj(coef, depart=True)
    # aucune correction du revenu des ménages : l'économie ne bouge pas, la dépense oui
    np.testing.assert_allclose(apres.difference("emploi_salarie"),
                               avant.difference("emploi_salarie"), rtol=0, atol=1e-12)
    e = apres.difference("emploi_salarie")[0, 0]
    assert e < 0.0  # la hausse des cotisations détruit des emplois
    r = reference(PARAMS, depart, apres.reference[0]["pib"])
    m = PARAMS.part_marchande * float(r.d1[0]) * e / r.emploi_marchand
    d62 = apres.difference("apu_d_d62")[0, 0] - avant.difference("apu_d_d62")[0, 0]
    assert d62 == pytest.approx(-0.2 * m, rel=1e-9)
    assert d62 > 0.0  # un emploi détruit rend plus d'allocation que le forfait ne dit
