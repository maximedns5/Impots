"""Les salaires que la population distingue : le point d'indice et le SMIC (but 21, étape 4).

Les règles tiennent sur une population faite à la main, salaire horaire par salaire
horaire : la loi relève au nouveau SMIC ce qui est entre l'ancien et le nouveau, et dans la
même proportion ce qui est sous l'ancien ; la diffusion suit le profil publié tranche par
tranche, au privé seulement ; le point d'indice multiplie le traitement des titulaires, pas
leurs primes. Le coût retire le salaire qu'un employeur privé paie et compte celui que
l'État paie ; le garde des secteurs le reconstitue. Les passes sur la population réelle
sont lourdes (`tests/lourds.txt`).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest
from pydantic import ValidationError

from impots.api.schemas import ReformSpec
from impots.engine.system import baseline
from impots.population import aggregate, margins, salaires

SMIC_2024 = salaires.smic_horaire(2024)
HEURES = 151.67 * 12


def _frame(horaires, public=None, titulaire=None, quotite=None) -> pl.DataFrame:
    n = len(horaires)
    public = public or [False] * n
    titulaire = titulaire or [False] * n
    quotite = quotite or [1.0] * n
    return pl.DataFrame({
        "person_id": list(range(n)), "household_id": [str(i) for i in range(n)],
        "weight": [1.0] * n,
        "salaire_brut_annuel": [h * HEURES * q for h, q in zip(horaires, quotite, strict=True)],
        "quotite_travail": quotite, "mois_travailles": [4095] * n,
        "secteur_public": public, "titulaire": titulaire,
        "regime_non_salarie": [None] * n,
    })


def _horaire_apres(frame: pl.DataFrame) -> np.ndarray:
    return frame[salaires.SALAIRE_REFORME].to_numpy() / (
        HEURES * frame["quotite_travail"].to_numpy())


# --- les boutons ---------------------------------------------------------------------


def test_a_diffusion_without_its_raise_is_refused() -> None:
    for spec in ({"smic_diffusion_profil": "annee_sans_effets_fixes"},
                 {"smic_revalorisation": 1.02, "smic_diffusion_echelle": 0.5},
                 {"point_indice_contractuels": 1.0}):
        with pytest.raises(ValidationError, match="exige"):
            ReformSpec(**spec)
    with pytest.raises(ValidationError):
        ReformSpec(smic_revalorisation=1.02, smic_diffusion_profil="un_an")


def test_a_household_refuses_the_salary_knobs() -> None:
    """Le salaire d'un ménage seul est donné : les boutons n'y bougeraient rien."""
    from impots.engine.reforms import make_reform

    with pytest.raises(ValueError, match="population"):
        make_reform(ReformSpec(point_indice_revalorisation=1.02), 2024, "essai")


def test_the_salary_knobs_are_stripped_from_the_tree() -> None:
    spec = ReformSpec(smic_revalorisation=1.02, ppa_pente=0.6)
    assert salaires.touche(spec) and not salaires.touche(ReformSpec(ppa_pente=0.6))
    assert salaires.sans_salaires(spec).model_dump(exclude_none=True) == {"ppa_pente": 0.6}


def test_the_raised_smic_is_every_month_of_the_year_only() -> None:
    system = salaires.reforme_smic(baseline(), 1.02, 2024)
    for instant in ("2024-01-01", "2024-11-01"):
        avant = baseline().parameters(instant).marche_travail.salaire_minimum.smic
        apres = system.parameters(instant).marche_travail.salaire_minimum.smic
        assert float(apres.smic_b_horaire) == pytest.approx(1.02 * float(avant.smic_b_horaire))
        assert float(apres.smic_b_mensuel) == pytest.approx(1.02 * float(avant.smic_b_mensuel))
    assert float(system.parameters("2025-01-01").marche_travail.salaire_minimum.smic
                 .smic_b_horaire) == 11.88


# --- le SMIC -------------------------------------------------------------------------


def test_the_law_alone_raises_the_wages_under_the_new_smic() -> None:
    """Le premier jour : sous l'ancien SMIC, relevé dans la proportion ; entre l'ancien et
    le nouveau, au nouveau ; au-dessus, rien."""
    s = SMIC_2024
    frame = _frame([0.8 * s, s, 1.01 * s, 1.03 * s, 1.2 * s], quotite=[1.0, 1.0, 0.5, 1.0, 1.0])
    out, stats = salaires.appliquer(frame, ReformSpec(smic_revalorisation=1.02), 2024)
    apres = _horaire_apres(out)
    assert apres == pytest.approx([0.8 * s * 1.02, 1.02 * s, 1.02 * s, 1.03 * s, 1.2 * s])
    assert (stats.releves_par_la_loi, stats.releves_sous_le_smic,
            stats.releves_par_diffusion) == (2.0, 1.0, 0.0)
    assert stats.smic_horaire_apres == pytest.approx(1.02 * s)


def test_the_diffusion_follows_the_published_profile_in_the_private_sector() -> None:
    s = SMIC_2024
    profil = "annee_sans_effets_fixes"
    elasticites = margins.SMIC_DIFFUSION_PROFILS[profil]
    horaires = [1.05 * s, 1.15 * s, 1.25 * s, 1.35 * s, 1.45 * s, 1.55 * s, 1.15 * s]
    frame = _frame(horaires, public=[False] * 6 + [True])
    spec = ReformSpec(smic_revalorisation=1.02, smic_diffusion_profil=profil,
                      smic_diffusion_echelle=0.5)
    apres = _horaire_apres(salaires.appliquer(frame, spec, 2024)[0])
    attendu = [h * (1 + 0.5 * e * 0.02) for h, e in zip(horaires[:5], elasticites,
                                                         strict=True)]
    # Au-delà de 1,5 SMIC, rien ; dans le public, rien.
    assert apres == pytest.approx([*attendu, horaires[5], horaires[6]])


def test_the_diffusion_never_lowers_what_the_law_gives() -> None:
    s = SMIC_2024
    frame = _frame([1.001 * s])
    spec = ReformSpec(smic_revalorisation=1.05,
                      smic_diffusion_profil="trimestre_sans_effets_fixes")
    assert _horaire_apres(salaires.appliquer(frame, spec, 2024)[0]) == pytest.approx(
        [1.05 * s])


def test_every_published_profile_is_read_in_its_bands() -> None:
    ratio = np.array([0.9, 1.0, 1.09, 1.1, 1.49, 1.5, 3.0])
    for profil, e in margins.SMIC_DIFFUSION_PROFILS.items():
        assert salaires.diffusion(ratio, profil, 1.0) == pytest.approx(
            [0.0, e[0], e[0], e[1], e[4], 0.0, 0.0])


# --- le point d'indice ---------------------------------------------------------------


def test_the_point_raises_the_titulars_traitement_not_their_primes() -> None:
    tau = salaires.taux_de_prime()
    frame = _frame([20.0, 20.0, 20.0], public=[True, True, False],
                   titulaire=[True, False, False])
    brut = frame["salaire_brut_annuel"].to_numpy()
    spec = ReformSpec(point_indice_revalorisation=1.03, point_indice_contractuels=0.5)
    out, stats = salaires.appliquer(frame, spec, 2024)
    traitement = brut[0] / (1 + tau)
    assert out[salaires.SALAIRE_REFORME].to_list() == pytest.approx(
        [traitement * 1.03 + brut[0] - traitement, brut[1] * 1.015, brut[2]])
    assert out[salaires.PRIMES_REFORME][0] == pytest.approx(brut[0] - traitement)
    assert stats.masse_point_indice == pytest.approx(traitement * 0.03 + brut[1] * 0.015)


# --- le coût -------------------------------------------------------------------------


def test_the_cost_takes_off_the_private_wage_and_counts_the_public_one() -> None:
    """Un salaire privé relevé de 100 : le ménage en reçoit 80 nets, l'employeur paie 100
    et 30 de cotisations ; l'État reçoit 20 + 30 et ne paie rien. Un salaire public relevé
    de 100 : l'État paie 100, 30 de cotisations à lui-même et 5 d'indemnités, reçoit 20."""
    rows = {
        "weight": [1.0, 1.0], "n_persons": [1, 1], "n_aged_14_plus": [1, 1],
        "n_children_under_14": [0, 0],
        "salaire_brut": [0.0, 0.0], "salaire_brut_reform": [100.0, 100.0],
        "salaire_super_brut": [0.0, 0.0], "salaire_super_brut_reform": [130.0, 135.0],
        "cotisations_salariales": [0.0, 0.0], "cotisations_salariales_reform": [20.0, 20.0],
        "revenu_disponible": [0.0, 0.0], "revenu_disponible_reform": [80.0, 85.0],
        "salaire_brut_prive": [0.0, 0.0], "salaire_brut_prive_reform": [100.0, 0.0],
        "salaire_brut_public": [0.0, 0.0], "salaire_brut_public_reform": [0.0, 100.0],
        "salaire_super_brut_public": [0.0, 0.0],
        "salaire_super_brut_public_reform": [0.0, 135.0],
        "remuneration_hors_brut_public": [0.0, 0.0],
        "remuneration_hors_brut_public_reform": [0.0, 5.0],
    }
    agg = aggregate.aggregate(pl.DataFrame(rows))
    # Privé : −20 − 30 = −50 ; public : 100 + 5 − 20 = 85.
    assert agg.reform_cost == pytest.approx(35.0)
    assert agg.balance["unexplained"] == pytest.approx(0.0)


def test_a_reform_without_salaries_costs_what_it_did() -> None:
    rows = {"weight": [1.0], "n_persons": [1], "n_aged_14_plus": [1],
            "n_children_under_14": [0], "revenu_disponible": [0.0],
            "revenu_disponible_reform": [10.0], "rsa": [0.0], "rsa_reform": [10.0]}
    agg = aggregate.aggregate(pl.DataFrame(rows))
    assert agg.reform_cost == pytest.approx(10.0)


# --- sur la population (lourds) ------------------------------------------------------


POPULATION = Path(__file__).resolve().parents[1] / "data" / "processed" / \
    "population_2024.parquet"


@pytest.mark.parametrize("spec", [
    {"point_indice_revalorisation": 1.03, "point_indice_contractuels": 0.5},
    {"smic_revalorisation": 1.04, "smic_diffusion_profil": "annee_sans_effets_fixes",
     "smic_diffusion_echelle": 0.5},
], ids=["point", "smic"])
def test_a_salary_reform_balances_on_the_population(spec) -> None:
    """Sur 1 500 ménages : le garde des secteurs reconstitue le coût (il refuse sinon),
    le privé relevé n'entre pas dans le coût, le public y entre. Des valeurs qu'aucun
    candidat ne propose : aucune mesure n'est chiffrée ici."""
    from impots.population.runner import run

    result = run(POPULATION, year=2024, reform=ReformSpec(**spec), tier="full", sample=1_500)
    agg = aggregate.aggregate(result.households)
    payes = aggregate.salaires_payes(result.households,
                                     result.households["weight"].to_numpy())
    assert abs(agg.balance["unexplained"]) < 1e-3 * abs(agg.reform_cost)
    stats = result.guards["salaires"]
    if "point_indice_revalorisation" in spec:
        assert payes["salaire_brut_prive"] == pytest.approx(0.0, abs=1.0)
        assert payes["salaire_brut_public"] > 0 and stats.masse_point_indice > 0
    else:
        assert payes["salaire_brut_prive"] > 0
        assert stats.releves_par_la_loi > 0 and stats.releves_par_diffusion > 0
