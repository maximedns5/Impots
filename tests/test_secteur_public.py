"""Le secteur public câblé (but 16, D-346).

Jusqu'à D-346, chaque salarié partait dans OpenFisca comme « privé non cadre » : le quart
de la masse salariale versée par les administrations recevait les allègements et les
barèmes de la CNAV et de l'Agirc-Arrco. Trois personnes à 36 000 € brut, un titulaire de
l'État, un contractuel territorial et un salarié du privé, tiennent les nombres : le
titulaire est payé d'un traitement indiciaire et de primes qui redonnent son brut, aucun
employeur public n'a d'allègement, et les mesures d'Attal et de Mélenchon ne touchent que
ceux qu'elles visent. Vus échouer sur le câblage d'avant (titulaire en « privé non cadre »,
allègement et baisse de cotisations sur les trois).
"""

from __future__ import annotations

import warnings

import numpy as np
import polars as pl
import pytest

from impots.api.schemas import ReformSpec
from impots.engine import system
from impots.population.to_openfisca import WiringError, build_simulation

YEAR = 2026


def _frame(gross: float = 36_000.0, **over) -> pl.DataFrame:
    n = 3
    columns = {
        "person_id": ["p1", "p2", "p3"], "household_id": ["m1", "m2", "m3"],
        "foyer_id": ["f1", "f2", "f3"], "famille_id": ["a1", "a2", "a3"], "age": [40] * n,
        "role_menage": ["personne_de_reference"] * n, "role_foyer": ["declarant_principal"] * n,
        "role_famille": ["demandeur"] * n, "salaire_brut_annuel": [gross] * n,
        "pension_annuelle": [0.0] * n, "chomage_annuel": [0.0] * n,
        "statut_occupation": ["proprietaire"] * n, "zone_apl": ["zone_2"] * n,
        "loyer_mensuel": [0.0] * n, "parent_isole": [False] * n,
        "secteur_public": [True, True, False],
        "fonction_publique": ["etat", "territoriale", None],
        "titulaire": [True, False, False]}
    columns.update(over)
    return pl.DataFrame(columns)


def _run(frame: pl.DataFrame, spec: dict | None = None):
    tbs = system.reformed_for(ReformSpec(**spec), YEAR) if spec else system.baseline()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return build_simulation(frame, tbs, YEAR).simulation


def _add(sim, variable: str) -> np.ndarray:
    return np.asarray(sim.calculate_add(variable, str(YEAR)))


def test_a_titular_servant_is_paid_a_traitement_and_primes_that_give_back_his_gross() -> None:
    sim = _run(_frame())
    assert list(sim.calculate("categorie_salarie", f"{YEAR}-01").decode_to_str()) == [
        "public_titulaire_etat", "public_non_titulaire", "prive_non_cadre"]
    paid = (_add(sim, "salaire_de_base") + _add(sim, "remuneration_principale")
            + _add(sim, "primes_fonction_publique"))
    assert paid == pytest.approx([36_000.0] * 3, abs=1e-6)
    assert _add(sim, "traitement_indiciaire_brut")[0] == pytest.approx(36_000.0 / 1.195)


def test_no_public_employer_receives_the_allegement() -> None:
    general = _add(_run(_frame()), "allegement_general")
    assert general[0] == 0.0 and general[1] == 0.0 and general[2] > 3_000.0


def test_the_measures_touch_only_those_they_aim_at() -> None:
    # Mélenchon : la réduction générale s'arrête à 2 SMIC ; 60 000 € est au-delà.
    base, reformed = _run(_frame(60_000.0)), _run(_frame(60_000.0),
                                                   {"allegement_general_plafond": 2.0})
    lost = _add(reformed, "allegement_general") - _add(base, "allegement_general")
    assert lost[0] == 0.0 and lost[1] == 0.0 and lost[2] < -1_000.0
    # Attal : l'échelle des cotisations de retraite porte sur la CNAV et l'Agirc-Arrco ;
    # le titulaire cotise à la pension civile, le contractuel à la CNAV seule.
    base, reformed = _run(_frame()), _run(_frame(),
                                         {"cotisations_salariales_retraite_echelle": 0.22})
    gain = _add(reformed, "salaire_net") - _add(base, "salaire_net")
    assert gain[0] == 0.0 and 0.0 < gain[1] < gain[2]


def test_a_frame_with_public_earners_but_no_status_is_refused() -> None:
    frame = _frame().drop("fonction_publique", "titulaire")
    with pytest.raises(WiringError, match="fonction_publique, titulaire"):
        _run(frame)


def test_what_separates_the_super_brut_from_d121_is_taken_person_by_person() -> None:
    """But 19, étape 1. Le super-brut moins le brut tient trois choses que D121 ne compte
    pas : la contribution de l'État aux pensions de ses titulaires (74,28 % du TIB de
    36 000 / 1,195, soit 22 377 €), les prélèvements que l'Insee classe en impôts sur les
    salaires (au privé, au SMIC comme à 36 000 € : formation 1,23 %, CSA 0,3 %, Fnal
    0,1 %, AGS 0,2 %, soit 658,80 €), l'indemnité de résidence et le SFT (des salaires)."""
    from impots.population.runner import employeurs_d121

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        built = build_simulation(_frame(), system.baseline(), 2024)
    parts = employeurs_d121(built)
    assert parts["pension_employeur_etat"] == pytest.approx(
        [0.7428 * 36_000.0 / 1.195, 0.0, 0.0], abs=1.0)
    assert parts["prelevements_salaires_d291"][2] == pytest.approx(36_000.0 * 0.0183, abs=0.01)
    assert parts["remuneration_hors_brut"][2] == 0.0
    hors_brut = (np.asarray(built.calculate("indemnite_residence", add=True))
                 + np.asarray(built.calculate("supplement_familial_traitement", add=True)))
    assert parts["remuneration_hors_brut"] == pytest.approx(hors_brut)
    assert (parts["remuneration_hors_brut"][:2] > 0).all()
