"""La zone APL tirée, le département des DOM, le loyer du parc social (but 19, étape al).

Avant l'étape, la ville-centre et la banlieue étaient en zone 2, le reste en zone 3 :
aucun ménage en zone 1. Les DOM n'étaient pas transmis à OpenFisca : une famille d'un
enfant à La Réunion n'avait pas d'allocations familiales, un foyer réunionnais payait
l'impôt de la métropole. Le loyer HLM était à 5,6 €/m² partout. Les tests ci-dessous
tiennent les parts du recensement, le loyer du RPLS et les deux règles des DOM ; ceux des
DOM sont vus échouer sur le câblage d'avant (sans `departement`, les deux montants
sont ceux de la métropole).
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl
import pytest

from impots.engine import system
from impots.population import logement, margins
from impots.population.to_openfisca import build_simulation

YEAR = 2024


def test_the_zone_table_adds_up_to_its_declared_total() -> None:
    total = sum(sum(counts) for counts in margins.APL_ZONE_BY_STCOMM.values())
    assert total == pytest.approx(margins.APL_ZONE_SOURCES.value, rel=1e-3)


def test_the_drawn_zones_reproduce_the_census_shares() -> None:
    # 60 000 ménages de chaque case : les parts tirées refont celles du recensement.
    keys = list(margins.APL_ZONE_BY_STCOMM)
    statut_of = {"hlm": "locataire_hlm", "autre_locataire": "locataire_vide",
                 "autre": "proprietaire"}
    n = 60_000
    stcomm = np.repeat([k.split("|")[0] for k in keys], n)
    statut = np.repeat([statut_of[k.split("|")[1]] for k in keys], n)
    zone, departement = logement.draw_zone_and_departement(
        stcomm, np.zeros(stcomm.size, dtype=bool), statut, seed=1)
    for index, key in enumerate(keys):
        drawn = zone[index * n:(index + 1) * n]
        counts = np.array(margins.APL_ZONE_BY_STCOMM[key])
        for z, expected in zip(logement.ZONES, counts / counts.sum(), strict=True):
            assert (drawn == z).mean() == pytest.approx(expected, abs=0.006), (key, z)
    assert all(d is None for d in departement)
    # Une banlieue loue en zone 1 près d'une fois sur deux (HLM : 46 %) ; avant, jamais.
    assert (zone[stcomm == "B"] == "zone_1").mean() > 0.3


def test_the_dom_are_zone_2_and_drawn_by_departement() -> None:
    n = 200_000
    zone, departement = logement.draw_zone_and_departement(
        np.array(["C"] * n), np.ones(n, dtype=bool), np.array(["locataire_hlm"] * n), seed=3)
    assert set(zone) == {"zone_2"}
    counts = margins.DOM_HOUSEHOLDS_BY_DEPARTEMENT
    total = sum(counts.values())
    for code, households in counts.items():
        assert (departement == code).mean() == pytest.approx(households / total, abs=0.004)


def test_the_social_rent_is_rpls_by_zone() -> None:
    statut = np.array(["locataire_hlm", "locataire_hlm", "locataire_vide", "proprietaire"])
    zone = np.array(["zone_1", "zone_3", "zone_1", "zone_1"])
    rent = logement.monthly_rent(statut, zone, np.array([2, 2, 2, 2]))
    surface = 30.0 + 12.0 * 2
    assert rent == pytest.approx([surface * 7.68, surface * 6.15, surface * 8.8, 0.0])


def _family(departement: str | None) -> pl.DataFrame:
    """A lone parent of one child of 5, 30 000 € of wages, tenant."""
    return pl.DataFrame({
        "person_id": ["p1", "p2"], "household_id": ["m1", "m1"],
        "foyer_id": ["f1", "f1"], "famille_id": ["a1", "a1"], "age": [35, 5],
        "role_menage": ["personne_de_reference", "enfant"],
        "role_foyer": ["declarant_principal", "personne_a_charge"],
        "role_famille": ["demandeur", "enfant"],
        "salaire_brut_annuel": [30_000.0, 0.0], "pension_annuelle": [0.0, 0.0],
        "chomage_annuel": [0.0, 0.0], "statut_occupation": ["locataire_vide"] * 2,
        "zone_apl": ["zone_2"] * 2, "loyer_mensuel": [500.0] * 2,
        "parent_isole": [True, True], "departement": [departement] * 2,
    }, schema_overrides={"departement": pl.String})


def _year(frame: pl.DataFrame, variable: str) -> float:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        simulation = build_simulation(frame, system.baseline(), YEAR).simulation
    return float(np.asarray(simulation.calculate_add(variable, str(YEAR))).sum())


def test_a_reunion_family_of_one_child_receives_the_allocations_familiales() -> None:
    assert _year(_family(None), "af") == 0.0
    assert _year(_family("974"), "af") > 250.0  # 24,05 € par mois au 1er avril 2024


def test_a_reunion_foyer_has_the_dom_abattement_on_its_income_tax() -> None:
    def single(departement: str | None) -> pl.DataFrame:
        return _family(departement).head(1).with_columns(
            pl.lit(40_000.0).alias("salaire_brut_annuel"), pl.lit(False).alias("parent_isole"))

    metro = -_year(single(None), "impot_revenu_restant_a_payer")
    reunion = -_year(single("974"), "impot_revenu_restant_a_payer")
    assert metro > 1_500.0
    # 30 % de la cotisation, dans la limite de 2 450 € ; la décote se calcule après,
    # sur l'impôt réduit, et en retire encore un peu (1 168 € contre 2 023 €).
    assert reunion <= metro * 0.7
    assert reunion > metro * 0.5


# ---- who is on the lease (étape al, second part) ---------------------------------------

def _two_familles(heberge: bool | None, colocation: bool | None,
                  statut: str = "locataire_vide") -> pl.DataFrame:
    """Two adults alone in one dwelling of 700 € a month, each his own famille and foyer:
    the reference person (6 000 € of wages) and a second adult with no income."""
    columns = {
        "person_id": ["p1", "p2"], "household_id": ["m1", "m1"],
        "foyer_id": ["f1", "f2"], "famille_id": ["a1", "a2"], "age": [55, 30],
        "role_menage": ["personne_de_reference", "autre"],
        "role_foyer": ["declarant_principal", "declarant_principal"],
        "role_famille": ["demandeur", "demandeur"],
        "salaire_brut_annuel": [6_000.0, 0.0], "pension_annuelle": [0.0, 0.0],
        "chomage_annuel": [0.0, 0.0], "statut_occupation": [statut] * 2,
        "zone_apl": ["zone_2"] * 2, "loyer_mensuel": [700.0] * 2,
        "parent_isole": [False, False],
    }
    if heberge is not None:
        columns["aide_logement_heberge"] = [False, heberge]
    if colocation is not None:
        columns["colocation"] = [colocation] * 2
    return pl.DataFrame(columns)


def _per_famille(frame: pl.DataFrame, variable: str, month: bool = False) -> np.ndarray:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        simulation = build_simulation(frame, system.baseline(), YEAR).simulation
    if month:
        return np.asarray(simulation.calculate(variable, f"{YEAR}-06"))
    return np.asarray(simulation.calculate_add(variable, str(YEAR)))


@pytest.mark.parametrize("statut", ["locataire_vide", "locataire_hlm"])
def test_a_famille_lodged_off_the_lease_has_no_housing_aid(statut: str) -> None:
    before = _per_famille(_two_familles(None, None, statut), "aide_logement")
    after = _per_famille(_two_familles(True, False, statut), "aide_logement")
    assert before[1] > 2_000.0          # avant : l'hébergé touchait l'aide sur tout le loyer
    assert after[1] == 0.0
    assert after[0] == pytest.approx(before[0])


def test_the_lodged_keeps_the_forfait_logement_of_the_rsa_in_full() -> None:
    before = _per_famille(_two_familles(None, None), "rsa_forfait_logement", month=True)
    after = _per_famille(_two_familles(True, False), "rsa_forfait_logement", month=True)
    # Logé gratuitement : le forfait d'une personne seule, 12 % du montant de base.
    assert after[1] == pytest.approx(before[1]) and after[1] > 70.0


def test_a_colocation_shares_the_rent_under_the_colocation_plafond() -> None:
    alone = _per_famille(_two_familles(None, None), "aide_logement_loyer_plafond", month=True)
    coloc = _per_famille(_two_familles(False, True), "aide_logement_loyer_plafond", month=True)
    assert coloc == pytest.approx(alone * 0.75, abs=0.01)
    rent = _per_famille(_two_familles(False, True), "aide_logement_loyer_reel", month=True)
    assert rent == pytest.approx([350.0, 350.0])
    aid_before = _per_famille(_two_familles(None, None), "aide_logement")
    aid_coloc = _per_famille(_two_familles(False, True), "aide_logement")
    assert (aid_coloc < aid_before - 300.0).all()
