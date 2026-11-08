"""La grille des curseurs (but 15, D-343, D-344) : sa définition, ses points, ses réformes.

Les passes elles-mêmes ne tournent pas ici (elles sont la série de D-344) ; ce qui est tenu,
ce sont les nombres qui décident de ce qu'elles chiffrent : la loi de chaque curseur est un
point de sa grille, le témoin est où D-344 le dit, λ = 0 est la loi et λ = 1 l'article.
"""

from __future__ import annotations

import itertools
import math

import pytest

from impots import grille

CURSEURS, PAIRES, RAW = grille.charger()


def test_the_definition_is_the_preregistered_one() -> None:
    assert RAW["preenregistrement"] == "D-344" and RAW["cadre"] == "central"
    assert len(CURSEURS) == 19 and len(PAIRES) == 11
    assert len(grille.taches(CURSEURS, PAIRES)) == 169


@pytest.mark.parametrize("cid", sorted(CURSEURS))
def test_the_law_is_a_point_of_every_grid_and_the_witness_is_beside_it(cid) -> None:
    c = CURSEURS[cid]
    values = c.valeurs()
    assert len(values) == grille.NOMBRE[c.forme]
    assert values[0] == c.bornes[0] and values[-1] == c.bornes[1]
    assert any(math.isclose(v, c.valeur_loi, abs_tol=1e-12) for v in values)
    w = c.temoin()
    assert w not in values and c.bornes[0] < w < c.bornes[1]
    k = min(range(len(values)), key=lambda i: abs(values[i] - c.valeur_loi))
    neighbour = values[k + 1] if k + 1 < len(values) else values[k - 1]
    assert min(values[k], neighbour) < w < max(values[k], neighbour)


def test_a_ceiling_over_a_decade_is_geometric_and_its_witness_too() -> None:
    c = CURSEURS["plafond_qf"]
    values = c.valeurs()
    assert c.geometrique and c.interpolation == "pchip"
    ratios = {round(b / a, 9) for a, b in itertools.pairwise(values)}
    assert len(ratios) == 1
    assert c.temoin() == pytest.approx(math.sqrt(values[0] * values[1]))


def test_a_knob_moves_its_field_alone() -> None:
    assert grille.reformes(CURSEURS["tva_carburants"], 0.1) == (
        {"tva_postes": {"carburants": 0.1}}, None, None)
    assert grille.reformes(CURSEURS["cvae"], 0.5) == ({}, {"cvae_echelle": 0.5}, None)
    menages, _, _ = grille.reformes(CURSEURS["tranche_60"], 0.45)
    bareme = menages["ir_bareme"]
    assert len(bareme) == 6 and bareme[5]["rate"] == bareme[4]["rate"] == 0.45


def test_lambda_zero_is_the_law_and_one_the_article() -> None:
    from impots import scenarios

    c = CURSEURS["plf_art_2"]
    article = scenarios.load("plf2027_art_2").reform.model_dump(exclude_none=True, mode="json")
    one, _, year = grille.reformes(c, 1.0)
    assert year == 2026 and one == pytest.approx(article)
    zero, _, _ = grille.reformes(c, 0.0)
    assert zero["plafond_qf_demi_part"] == grille.loi_menages("plafond_qf_demi_part", 2026)
    assert zero["ir_bareme"] == grille.loi_menages("ir_bareme", 2026)
    assert grille.reformes(CURSEURS["plf_art_74_ppa"], 0.0)[0] == {
        "ppa_revalorisation_avril": 1.0}
    _, firm, year = grille.reformes(CURSEURS["plf_art_15"], 0.0)
    assert year == 2027 and {row["taux"] for row in firm["cebge_seuils_et_taux"]} == {0.0}


def test_a_pair_moves_both_knobs_and_refuses_a_field_written_twice() -> None:
    a, b = CURSEURS["tva_carburants"], CURSEURS["tva_energie"]
    menages, firm, _ = grille.combiner(grille.reformes(a, 0.0), grille.reformes(b, 0.1))
    assert menages == {"tva_postes": {"carburants": 0.0, "energie": 0.1}} and firm is None
    with pytest.raises(grille.GrilleError, match="écrit deux fois"):
        grille.combiner(grille.reformes(CURSEURS["csg_deductible"], 0.05),
                        grille.reformes(CURSEURS["csg_deductible"], 0.06))
