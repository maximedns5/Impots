"""Les prestations neuves des programmes (but 21, étape 3), sur des ménages types.

Chaque montant est refait à la main depuis les entrées du ménage et les revenus nets que
le moteur calcule mois par mois, jamais lu sur la ligne qu'il vérifie. Aucune population :
les mesures des candidats se préenregistrent avant leur premier calcul sur elle.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from impots.api.schemas import HouseholdInput, ReformSpec
from impots.engine import compute
from impots.engine.compute import _build
from impots.engine.outputs import check_registry
from impots.engine.situations import build_situation
from impots.engine.system import baseline, reformed_for

ANNEE = 2026

#: Les champs du candidat de chaque groupe, aux valeurs de son programme ; les tests en
#: changent un à la fois.
RIA = {"socle": 300.0, "insertion": 250.0, "taux_revenus_activite": 0.30,
       "plafond_revenus_activite": 1_833.0, "remplace_rsa": True, "remplace_ppa": True,
       "remplace_ass": True}
REVENU_FAMILIAL = {"montant_par_enfant": 240.0, "montant_troisieme_enfant": 480.0,
                   "age_maximum": 18, "remplace_af": True, "remplace_cf": True,
                   "remplace_ars": True}
AFU = {"montant_par_enfant": 350.0, "age_maximum": 20, "remplace_af": True,
       "remplace_cf": False, "remplace_ars": False}
GARANTIE = {"seuil": 1_337.0}


def _menage(adultes: list[dict[str, Any]], enfants: tuple[int, ...] = (),
            couple: bool = False, loyer: float | None = None) -> HouseholdInput:
    data: dict[str, Any] = {"adults": adultes,
                            "children": [{"annee_naissance": a} for a in enfants]}
    if couple:
        data["couple_marie_ou_pacse"] = True
    if loyer is not None:
        data["logement"] = {"statut": "locataire_vide", "loyer_mensuel": loyer,
                            "zone_apl": 2}
    return HouseholdInput.model_validate(data)


def _adulte(salaire: float = 0.0, naissance: int = 1990, **autres: Any) -> dict[str, Any]:
    return {"salaire_brut_annuel": salaire, "annee_naissance": naissance, **autres}


def _mois(menage: HouseholdInput, reforme: ReformSpec, variable: str) -> list[list[float]]:
    """Une variable de chaque individu, mois par mois, dans le système de la réforme."""
    simulation = _build(reformed_for(reforme, ANNEE), build_situation(menage, ANNEE),
                        ANNEE, "full")
    return [[float(v) for v in simulation.calculate(variable, f"{ANNEE}-{m:02d}")]
            for m in range(1, 13)]


def _lignes(menage: HouseholdInput, reforme: ReformSpec) -> tuple[dict, dict]:
    resultat = compute(menage, ANNEE, reforme, tier="full")
    return resultat.baseline, resultat.reform


def _retombe(avant: dict, apres: dict, lignes: tuple[str, ...]) -> None:
    """Le revenu disponible bouge exactement de ce que bougent les lignes nommées."""
    delta = sum(apres[k] - avant[k] for k in lignes)
    assert apres["revenu_disponible"] - avant["revenu_disponible"] == pytest.approx(
        delta, abs=0.05)


# --- le bouton à sa valeur par défaut ------------------------------------------------


def test_a_reform_without_a_new_benefit_adds_nothing_to_the_law() -> None:
    """Un groupe à `None` n'ajoute aucune variable et ne touche à aucune formule : une
    réforme qui ne pose que la BMAF a le `prestations_sociales` de la loi, et les trois
    lignes lisent zéro."""
    loi = baseline()
    reforme = reformed_for(ReformSpec(bmaf=500.0), ANNEE)
    for name in ("ria", "allocation_enfant", "garantie_autonomie"):
        assert name not in loi.variables and name not in reforme.variables
    for name in ("prestations_sociales", "rsa", "ppa", "af"):
        assert (reforme.variables[name].formulas.keys()
                == loi.variables[name].formulas.keys())
    avant, apres = _lignes(_menage([_adulte(naissance=2004)], (2015,)), ReformSpec(bmaf=500.0))
    for name in ("ria", "allocation_enfant", "garantie_autonomie"):
        assert avant[name] == apres[name] == 0.0
    assert check_registry(loi) == []


def test_the_registry_reads_the_new_benefits_where_the_reform_adds_them() -> None:
    """Leurs lignes ont l'entité et la période de leur variable, dans le système qui les a."""
    systeme = reformed_for(ReformSpec(ria=RIA, allocation_enfant=REVENU_FAMILIAL,
                                      garantie_autonomie=GARANTIE), ANNEE)
    assert check_registry(systeme) == []
    for name in ("ria", "allocation_enfant", "garantie_autonomie"):
        assert name in systeme.variables


# --- le revenu d'incitation à l'activité ---------------------------------------------


def test_the_ria_pays_its_socle_to_an_adult_without_income() -> None:
    """Sans revenu ni allocation chômage : le socle seul, 300 € par mois, 3 600 € l'an ; le
    RSA et la prime de Noël qu'il touchait disparaissent."""
    menage = _menage([_adulte()], loyer=450.0)
    avant, apres = _lignes(menage, ReformSpec(ria=RIA))
    assert apres["ria"] == pytest.approx(3_600.0, abs=0.01)
    assert avant["rsa"] > 0 and apres["rsa"] == apres["ppa"] == apres["aefa"] == 0.0
    _retombe(avant, apres, ("ria", "rsa", "ppa", "aefa", "crds_mini", "aide_logement"))


def test_the_ria_keeps_seventy_per_cent_of_a_salary_s_place() -> None:
    """Un mi-temps : socle et insertion, moins 30 % du salaire net de chaque mois."""
    menage = _menage([_adulte(salaire=12_000.0)])
    reforme = ReformSpec(ria=RIA)
    nets = _mois(menage, reforme, "salaire_net")
    attendu = sum(max(0.0, 550.0 - 0.30 * mois[0]) for mois in nets)
    assert 0 < attendu < 550.0 * 12
    avant, apres = _lignes(menage, reforme)
    assert apres["ria"] == pytest.approx(attendu, abs=0.05)
    assert avant["ppa"] > 0 and apres["ppa"] == 0.0
    _retombe(avant, apres, ("ria", "rsa", "ppa", "aefa", "crds_mini"))


def test_the_ria_stops_above_its_ceiling_and_the_ceiling_is_what_stops_it() -> None:
    """Au-delà de 1 833 € de revenus d'activité nets par mois, rien ; à 2 000 € nets, la
    déduction seule laisserait 550 − 600 < 0, donc rien non plus. Avec un taux de 10 %,
    seul le plafond éteint l'allocation : le lever la rouvre, à la main."""
    menage = _menage([_adulte(salaire=31_000.0)])
    nets = _mois(menage, ReformSpec(ria=RIA), "salaire_net")
    assert min(m[0] for m in nets) > 1_833.0
    assert _lignes(menage, ReformSpec(ria=RIA))[1]["ria"] == 0.0
    bas = {**RIA, "taux_revenus_activite": 0.10}
    assert _lignes(menage, ReformSpec(ria=bas))[1]["ria"] == 0.0
    sans_plafond = ReformSpec(ria={**bas, "plafond_revenus_activite": None})
    attendu = sum(max(0.0, 550.0 - 0.10 * m[0]) for m in nets)
    assert attendu > 0
    assert _lignes(menage, sans_plafond)[1]["ria"] == pytest.approx(attendu, abs=0.05)


def test_the_ria_is_individual_and_stops_at_65() -> None:
    """Deux adultes sans revenu : deux socles, la famille n'y change rien. Un adulte de 66
    ans, rien."""
    couple = _menage([_adulte(), _adulte(naissance=1992)], couple=True)
    assert _lignes(couple, ReformSpec(ria=RIA))[1]["ria"] == pytest.approx(7_200.0, abs=0.01)
    senior = _menage([_adulte(naissance=1960)])
    assert _lignes(senior, ReformSpec(ria=RIA))[1]["ria"] == 0.0


def test_a_job_seeker_draws_the_insertion_less_his_allowance() -> None:
    """Une allocation chômage dans le mois justifie l'insertion (hypothèse) et se déduit à
    100 % : 550 € moins l'allocation nette de chaque mois. Sans l'hypothèse, 300 € moins
    l'allocation."""
    menage = _menage([_adulte(chomage_brut_annuel=3_000.0)])
    nets = _mois(menage, ReformSpec(ria=RIA), "chomage_net")
    assert all(m[0] > 0 for m in nets)
    attendu = sum(max(0.0, 550.0 - m[0]) for m in nets)
    assert _lignes(menage, ReformSpec(ria=RIA))[1]["ria"] == pytest.approx(attendu, abs=0.05)
    sans = ReformSpec(ria={**RIA, "insertion_demandeurs_emploi": False})
    attendu = sum(max(0.0, 300.0 - m[0]) for m in nets)
    assert _lignes(menage, sans)[1]["ria"] == pytest.approx(attendu, abs=0.05)


def test_a_replacement_flag_left_down_keeps_the_benefit() -> None:
    """Le RSA reste quand son drapeau est baissé : il est alors calculé sans le RIA."""
    menage = _menage([_adulte()], loyer=450.0)
    avant, apres = _lignes(menage, ReformSpec(ria={**RIA, "remplace_rsa": False}))
    assert apres["rsa"] == pytest.approx(avant["rsa"], abs=0.01) and avant["rsa"] > 0
    assert apres["ria"] == pytest.approx(3_600.0, abs=0.01)


# --- l'allocation par enfant ---------------------------------------------------------


def test_the_revenu_familial_pays_240_from_the_first_child_and_480_for_the_third() -> None:
    """Trois enfants de 16, 12 et 2 ans : 240 + 240 + 480 = 960 € par mois ; les
    allocations familiales, le complément familial et l'ARS tombent, la PAJE reste."""
    menage = _menage([_adulte(salaire=22_000.0), _adulte(salaire=18_000.0, naissance=1988)],
                     (2010, 2014, 2024), couple=True)
    avant, apres = _lignes(menage, ReformSpec(allocation_enfant=REVENU_FAMILIAL))
    assert apres["allocation_enfant"] == pytest.approx(960.0 * 12, abs=0.01)
    assert avant["af"] > 0 and avant["ars"] > 0
    assert apres["af"] == apres["cf"] == apres["ars"] == 0.0
    # L'hypothèse dite : l'allocation n'entre pas dans les ressources de la prime
    # d'activité, d'où les allocations familiales sortent ; la prime monte.
    assert apres["ppa"] > avant["ppa"] > 0
    _retombe(avant, apres, ("allocation_enfant", "af", "cf", "ars", "crds_pfam", "ppa",
                            "rsa", "aefa", "crds_mini", "aide_logement"))


def test_the_age_limit_and_the_one_child_family() -> None:
    """Un enfant de 18 ans n'ouvre rien sous « jusqu'à 18 ans » ; un enfant unique de 10
    ans ouvre 240 € par mois, que les allocations familiales ne lui versaient pas."""
    grand = _menage([_adulte(salaire=30_000.0)], (2008,))
    assert _lignes(grand, ReformSpec(allocation_enfant=REVENU_FAMILIAL))[1][
        "allocation_enfant"] == 0.0
    unique = _menage([_adulte(salaire=30_000.0)], (2016,))
    avant, apres = _lignes(unique, ReformSpec(allocation_enfant=REVENU_FAMILIAL))
    assert avant["af"] == 0.0
    assert apres["allocation_enfant"] == pytest.approx(240.0 * 12, abs=0.01)


def test_the_afu_per_child_per_family_and_its_degressivity() -> None:
    """350 € par mois et par enfant de moins de 20 ans : deux enfants, 8 400 € l'an ; lu par
    famille, 4 200 €. Dégressive de 10 % de l'impôt sur le revenu du foyer, un douzième par
    mois, sans descendre sous 100 € par enfant."""
    menage = _menage([_adulte(salaire=150_000.0)], (2008, 2012))
    avant, apres = _lignes(menage, ReformSpec(allocation_enfant=AFU))
    assert apres["allocation_enfant"] == pytest.approx(8_400.0, abs=0.01)
    assert avant["af"] > 0 and apres["af"] == 0.0 and apres["ars"] == avant["ars"]
    par_famille = ReformSpec(allocation_enfant={**AFU, "par_famille": True})
    assert _lignes(menage, par_famille)[1]["allocation_enfant"] == pytest.approx(
        4_200.0, abs=0.01)

    impot = apres["ir"]
    assert impot > 0
    for part, plancher in ((0.10, 0.0), (0.10, 100.0), (1.0, 100.0)):
        reforme = ReformSpec(allocation_enfant={**AFU, "degressivite_part_ir": part,
                                                "plancher_par_enfant": plancher})
        mensuel = min(700.0, max(2 * plancher, 700.0 - part * impot / 12.0))
        assert _lignes(menage, reforme)[1]["allocation_enfant"] == pytest.approx(
            12 * mensuel, abs=0.05), (part, plancher)


# --- la garantie d'autonomie des jeunes ----------------------------------------------


def test_the_guarantee_tops_a_young_person_up_to_the_threshold() -> None:
    """Un jeune de 20 ans au salaire de 6 000 € brut l'an : 1 337 € moins son salaire net de
    chaque mois. Deux jeunes sans revenu : deux seuils entiers. À 26 ans, rien."""
    jeune = _menage([_adulte(salaire=6_000.0, naissance=2006)])
    nets = _mois(jeune, ReformSpec(garantie_autonomie=GARANTIE), "salaire_net")
    attendu = sum(max(0.0, 1_337.0 - m[0]) for m in nets)
    avant, apres = _lignes(jeune, ReformSpec(garantie_autonomie=GARANTIE))
    assert apres["garantie_autonomie"] == pytest.approx(attendu, abs=0.05)
    assert apres["ppa"] == pytest.approx(avant["ppa"], abs=0.01)
    _retombe(avant, apres, ("garantie_autonomie",))

    deux = _menage([_adulte(naissance=2004), _adulte(naissance=2005)], couple=True)
    assert _lignes(deux, ReformSpec(garantie_autonomie=GARANTIE))[1][
        "garantie_autonomie"] == pytest.approx(2 * 1_337.0 * 12, abs=0.01)
    vieux = _menage([_adulte(naissance=2000)])
    assert _lignes(vieux, ReformSpec(garantie_autonomie=GARANTIE))[1][
        "garantie_autonomie"] == 0.0


# --- ce que le schéma refuse ----------------------------------------------------------


def test_a_knob_of_a_replaced_benefit_is_refused() -> None:
    with pytest.raises(ValidationError, match="rsa_montant_de_base"):
        ReformSpec(ria=RIA, rsa_montant_de_base=700.0)
    with pytest.raises(ValidationError, match="af_taux_2_enfants"):
        ReformSpec(allocation_enfant=AFU, af_taux_2_enfants=0.5)
    ReformSpec(ria={**RIA, "remplace_rsa": False}, rsa_montant_de_base=700.0)


def test_the_candidate_s_fields_have_no_default() -> None:
    """Ce que le candidat énonce s'écrit : un groupe sans ses drapeaux ou sans son âge est
    refusé, comme des âges inversés ou un seuil infini."""
    sans_taux = {k: v for k, v in RIA.items() if k != "taux_revenus_activite"}
    for invalide in ({"ria": sans_taux},
                     {"allocation_enfant": {"montant_par_enfant": 240.0, "age_maximum": 18}},
                     {"ria": {**RIA, "age_minimum": 65}},
                     {"garantie_autonomie": {"seuil": 1_337.0, "age_minimum": 25}},
                     {"garantie_autonomie": {"seuil": float("inf")}}):
        with pytest.raises(ValidationError):
            ReformSpec.model_validate(invalide)
