"""Les boutons des programmes de 2027 que le moteur avait sans les câbler (but 21, étape 2).

Chaque bouton est vu bouger son nombre sur un ménage type ou des entreprises types, jamais
sur la population, et vu ne rien coûter à la valeur du droit. `test_knobs.py` voit chacun
bouger dans le bon sens ; ici, les nombres qu'ils doivent donner, calculés à la main quand
la règle le permet.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest
from pydantic import ValidationError

from impots.api.schemas import HouseholdInput, ReformSpec
from impots.engine import compute, situations
from impots.engine.compute import _build
from impots.engine.system import baseline, reformed_for
from knob_cases import FAMILLE_IMPOSABLE, JEUNE_SALARIE, LOGE_SEUL, RENTIER, RENTIER_AISE

YEAR = 2026


def _run(household: dict, reform: ReformSpec | None, year: int = YEAR):
    return compute(HouseholdInput.model_validate(household), year, reform=reform, tier="full")


def _both(household: dict, reform: ReformSpec, year: int = YEAR) -> tuple[dict, dict]:
    result = _run(household, reform, year)
    return result.baseline, result.reform


# --------------------------------------------------------------------------- #
# L'exonération d'impôt sur le revenu des jeunes
# --------------------------------------------------------------------------- #
JEUNES = {"ir_exoneration_jeunes_age": 30, "ir_exoneration_jeunes_plafond_smic": 4.0}


def test_a_young_salary_under_the_ceiling_owes_no_income_tax() -> None:
    """26 ans en 2026, 40 000 EUR bruts, sous 4 SMIC : tout le salaire sort de l'impôt, et
    rien d'autre ne bouge — la CSG et les cotisations lisent le salaire entier."""
    before, after = _both(JEUNE_SALARIE, ReformSpec(**JEUNES))
    assert before["ir"] > 1_000
    assert after["ir"] == 0.0
    for row in ("csg_deductible", "csg_imposable", "cotisations_salariales", "salaire_net"):
        assert after[row] == pytest.approx(before[row]), row
    assert after["revenu_disponible"] - before["revenu_disponible"] == pytest.approx(
        before["ir"], abs=0.01)


def test_the_age_is_read_on_the_first_of_january() -> None:
    """Né en 1996 : 30 ans au 1er janvier 2026, donc pas « moins de 30 ans »."""
    trente = {"adults": [{"salaire_brut_annuel": 40_000, "annee_naissance": 1996}]}
    before, after = _both(trente, ReformSpec(**JEUNES))
    assert after["ir"] == pytest.approx(before["ir"])
    vingt_neuf = {"adults": [{"salaire_brut_annuel": 40_000, "annee_naissance": 1997}]}
    _, after = _both(vingt_neuf, ReformSpec(**JEUNES))
    assert after["ir"] == 0.0


def test_above_the_ceiling_the_salary_is_taxed_and_nothing_is_lost() -> None:
    """Un abattement, pas une falaise : à 80 000 EUR, un plafond d'un demi-SMIC exonère une
    part, un SMIC davantage, deux plus encore, et l'impôt baisse avec le plafond sans jamais remonter."""
    rich = {"adults": [{"salaire_brut_annuel": 80_000, "annee_naissance": 2000}]}
    irs = [_both(rich, ReformSpec(ir_exoneration_jeunes_age=30,
                                  ir_exoneration_jeunes_plafond_smic=p))[1]["ir"]
           for p in (0.0, 0.5, 1.0, 2.0, 4.0)]
    base = _run(rich, None).baseline["ir"]
    assert irs[0] == pytest.approx(base)
    assert base > irs[1] > irs[2] > irs[3] > 0
    assert irs[4] == 0.0


def test_a_young_dependant_s_salary_is_exempt_in_the_parents_foyer() -> None:
    """L'âge se lit sur la personne, au sein du foyer : seul le salaire du jeune sort."""
    parent = {"adults": [{"salaire_brut_annuel": 50_000, "annee_naissance": 1970}]}
    before, after = _both(parent, ReformSpec(**JEUNES))
    assert after["ir"] == pytest.approx(before["ir"])


def test_the_two_youth_fields_go_together() -> None:
    with pytest.raises(ValidationError, match="sans"):
        ReformSpec(ir_exoneration_jeunes_age=30)
    with pytest.raises(ValidationError, match="sans"):
        ReformSpec(ir_exoneration_jeunes_plafond_smic=4.0)


# --------------------------------------------------------------------------- #
# La suppression du PFU
# --------------------------------------------------------------------------- #
def test_without_the_pfu_a_high_income_pays_more_and_a_modest_one_less() -> None:
    """Au barème, les dividendes d'un foyer à la tranche haute paient plus qu'au PFU, même
    abattus de 40 % ; ceux d'un foyer à 11 % paient moins. Le PFU sort de l'impôt, les
    prélèvements sociaux ne bougent pas."""
    before, after = _both(RENTIER_AISE, ReformSpec(pfu_supprime=True))
    assert before["pfu"] == pytest.approx(12_800.0)
    assert after["pfu"] == 0.0
    assert after["ir"] > before["ir"] + 5_000
    assert after["prelevements_sociaux_capital"] == pytest.approx(
        before["prelevements_sociaux_capital"])
    before, after = _both(RENTIER, ReformSpec(pfu_supprime=True))
    assert after["pfu"] == 0.0
    assert after["ir"] < before["ir"]


def test_the_pfu_kept_costs_nothing() -> None:
    before, after = _both(RENTIER_AISE, ReformSpec(pfu_supprime=False))
    for row in ("ir", "pfu", "revenu_disponible"):
        assert after[row] == pytest.approx(before[row]), row


def test_the_pfu_removed_and_a_pfu_rate_together_are_refused() -> None:
    with pytest.raises(ValidationError, match="pfu_taux"):
        ReformSpec(pfu_supprime=True, pfu_taux=0.2)


def test_the_pfu_removed_imputes_the_capital_on_a_population_pass() -> None:
    from impots.engine.reforms import moves_capital

    assert moves_capital(ReformSpec(pfu_supprime=True))


# --------------------------------------------------------------------------- #
# La réduction d'impôt des familles
# --------------------------------------------------------------------------- #
def familles(montant: float, enfants: int) -> ReformSpec:
    return ReformSpec(reduction_impot_familles_montant=montant,
                      reduction_impot_familles_enfants_min=enfants)


def test_the_family_reduction_comes_off_the_tax_and_stops_at_it() -> None:
    """500 EUR ôtent 500 EUR à l'impôt ; 3 000 EUR, plus que l'impôt, le ramènent à zéro et
    rien de plus : une réduction, pas un crédit."""
    before, after = _both(FAMILLE_IMPOSABLE, familles(500.0, 2))
    assert before["ir"] > 1_000
    assert after["ir"] == pytest.approx(before["ir"] - 500.0, abs=0.5)
    _, after = _both(FAMILLE_IMPOSABLE, familles(3_000.0, 2))
    assert after["ir"] == 0.0
    assert after["revenu_disponible"] - before["revenu_disponible"] == pytest.approx(
        before["ir"], abs=0.5)


def test_the_family_reduction_needs_the_children_and_the_work() -> None:
    """Deux enfants pour un seuil de trois, ou des parents sans revenu d'activité : rien."""
    before, after = _both(FAMILLE_IMPOSABLE, familles(3_000.0, 3))
    assert after["ir"] == pytest.approx(before["ir"])
    retraite = {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1965,
                            "pension_annuelle": 60_000}],
                "children": [{"annee_naissance": 2010}, {"annee_naissance": 2012}]}
    before, after = _both(retraite, familles(3_000.0, 2))
    assert before["ir"] > 0
    assert after["ir"] == pytest.approx(before["ir"])


def test_a_family_reduction_of_nothing_costs_nothing() -> None:
    before, after = _both(FAMILLE_IMPOSABLE, familles(0.0, 2))
    assert after["ir"] == pytest.approx(before["ir"])


# --------------------------------------------------------------------------- #
# La CVEC
# --------------------------------------------------------------------------- #
def _cvec(system, etudiant: bool, boursier: bool = False) -> tuple[float, float]:
    """(CVEC, revenu disponible) d'un adulte seul, les deux entrées écrites à la main : le
    format d'entrée ne les porte pas."""
    household = HouseholdInput.model_validate(
        {"adults": [{"salaire_brut_annuel": 8_000, "annee_naissance": 2005}]})
    situation = situations.build_situation(household, YEAR, True)
    person = next(iter(situation["individus"]))
    situation["individus"][person].update(
        {"etudiant_superieur": {str(YEAR): etudiant},
         "boursier_superieur": {str(YEAR): boursier}})
    simulation = _build(system, situation, YEAR, "full")
    return (float(simulation.calculate("cvec", str(YEAR)).sum()),
            float(simulation.calculate("revenu_disponible", str(YEAR))[0]))


def test_a_student_pays_the_cvec_and_its_removal_gives_it_back() -> None:
    cvec, revenu = _cvec(baseline(), etudiant=True)
    assert cvec == pytest.approx(105.0)
    _, revenu_non_etudiant = _cvec(baseline(), etudiant=False)
    assert revenu_non_etudiant - revenu == pytest.approx(105.0)
    supprimee, revenu_sans = _cvec(reformed_for(ReformSpec(cvec_montant=0.0), YEAR),
                                   etudiant=True)
    assert supprimee == 0.0
    assert revenu_sans - revenu == pytest.approx(105.0)


def test_a_scholarship_holder_pays_no_cvec() -> None:
    assert _cvec(baseline(), etudiant=True, boursier=True)[0] == 0.0


def test_the_cvec_at_the_law_costs_nothing() -> None:
    law, revenu = _cvec(baseline(), etudiant=True)
    again, revenu_loi = _cvec(reformed_for(ReformSpec(cvec_montant=105.0), YEAR),
                              etudiant=True)
    assert again == law and revenu_loi == pytest.approx(revenu)


def test_a_population_pass_refuses_the_cvec() -> None:
    """La population ne porte ni les étudiants du supérieur ni les boursiers : un coût nul
    se lirait comme un chiffrage. Refusé avant toute passe."""
    from impots.population.runner import WiringError, run

    with pytest.raises(WiringError, match="étudiants du supérieur"):
        run(pl.DataFrame({"person_id": [1]}), year=YEAR, reform=ReformSpec(cvec_montant=0.0))


# --------------------------------------------------------------------------- #
# L'indexation année par année
# --------------------------------------------------------------------------- #
def _rsa(indexations: dict, year: int) -> tuple[float, float]:
    before, after = _both(LOGE_SEUL, ReformSpec(indexations=indexations), year)
    return before["rsa"], after["rsa"]


def test_an_april_indexation_moves_april_to_december() -> None:
    """En 2027, au-delà de l'arbre, le RSA de chaque mois vaut celui d'avril 2026 : 10 % de
    plus dès avril, c'est 10 % de neuf mois sur douze."""
    before, after = _rsa({"rsa": {2027: 1.10}}, 2027)
    assert after == pytest.approx(before * (1 + 0.10 * 9 / 12), abs=0.05)


def test_an_indexation_of_the_year_before_is_carried_through_the_year() -> None:
    before, after = _rsa({"rsa": {2026: 1.10}}, 2027)
    assert after == pytest.approx(before * 1.10, abs=0.05)


def test_the_years_compose_in_order() -> None:
    before, after = _rsa({"rsa": {2026: 1.10, 2027: 1.10}}, 2027)
    assert after == pytest.approx(before * (3 * 1.10 + 9 * 1.21) / 12, abs=0.05)


def test_an_indexation_of_a_later_year_moves_nothing_now() -> None:
    before, after = _rsa({"rsa": {2028: 0.90}}, 2027)
    assert after == pytest.approx(before)


def test_an_indexation_of_one_costs_nothing() -> None:
    before, after = _rsa({"rsa": {2026: 1.0, 2027: 1.0}}, 2027)
    assert after == pytest.approx(before)


def test_the_housing_aid_is_indexed_in_october() -> None:
    before, after = _both(LOGE_SEUL, ReformSpec(indexations={"aides_logement": {2026: 1.10}}),
                          2027)
    assert after["aide_logement"] > before["aide_logement"] * 1.05
    assert after["rsa"] == pytest.approx(before["rsa"])


def test_the_pensions_are_indexed_on_the_reform_pass() -> None:
    """Les pensions sont des données : leur coefficient multiplie la pension déclarée de la
    passe de la réforme, au 1er janvier."""
    retraite = {"adults": [{"salaire_brut_annuel": 0, "annee_naissance": 1955,
                            "pension_annuelle": 20_000}]}
    before, after = _both(retraite, ReformSpec(indexations={"pensions": {2026: 1.05}}))
    assert after["retraite_imposable"] == pytest.approx(1.05 * before["retraite_imposable"])
    # 1 000 EUR de pension de plus, dont l'impôt et les prélèvements prennent leur part.
    assert 300 < after["revenu_disponible"] - before["revenu_disponible"] < 1_000
    before, after = _both(retraite, ReformSpec(indexations={"pensions": {2026: 1.0}}))
    assert after["revenu_disponible"] == pytest.approx(before["revenu_disponible"])


def test_the_population_pass_indexes_the_pensions_of_the_reform_only() -> None:
    """Sur la population de 400 logements des tests (pas la population réelle)."""
    from impots.population import margins
    from impots.population.incomes import attach_incomes, household_share_of_france
    from impots.population.runner import run
    from impots.population.skeleton import build_skeleton

    source = Path(__file__).parent / "fixtures" / "eec_sample.parquet"
    children = {k: np.array(v) for k, v in margins.CHILDREN_PER_FAMILY.items()}
    frame, _ = build_skeleton(children_per_household=children, source=pl.read_parquet(source))
    frame, _ = attach_incomes(frame, targets_scale=household_share_of_france(frame))
    households = run(frame, year=2024, tier="light",
                     reform=ReformSpec(indexations={"pensions": {2024: 1.05}})).households
    base = households["retraite_imposable"].to_numpy()
    assert base.sum() > 0
    assert np.allclose(households["retraite_imposable_reform"].to_numpy(), 1.05 * base,
                       rtol=1e-6, atol=0.01)


@pytest.mark.parametrize("indexations, needle", [
    ({"loyers": {2027: 1.0}}, "connues"),
    ({"rsa": {2050: 1.0}}, "hors de"),
    ({"rsa": {}}, "aucune"),
])
def test_an_indexation_that_says_nothing_is_refused(indexations: dict, needle: str) -> None:
    with pytest.raises(ValidationError, match=needle):
        ReformSpec(indexations=indexations)


@pytest.mark.parametrize("other", [{"rsa_montant_de_base": 700.0}, {"bmaf": 500.0},
                                   {"ppa_revalorisation_avril": 1.02}])
def test_an_indexation_and_a_knob_on_the_same_amount_are_refused(other: dict) -> None:
    prestation = {"rsa_montant_de_base": "rsa", "bmaf": "prestations_familiales",
                  "ppa_revalorisation_avril": "prime_activite"}[next(iter(other))]
    with pytest.raises(ValidationError, match="même"):
        ReformSpec(indexations={prestation: {2027: 1.0}}, **other)


def test_the_read_back_refuses_a_faulty_indexation(monkeypatch) -> None:
    """Une écriture qui oublie l'année tombée avant celle chiffrée est refusée : la
    relecture tire l'attendu de la référence et des dates, pas de l'écriture."""
    from impots.engine import boutons_programmes
    from impots.engine.reforms import make_reform

    spec = ReformSpec(indexations={"rsa": {2026: 1.10, 2027: 1.10}})
    boutons_programmes.verifier_indexations(make_reform(spec, 2027, "juste")(baseline()),
                                            spec, 2027)
    real = boutons_programmes._coefficients
    monkeypatch.setattr(boutons_programmes, "_coefficients",
                        lambda s, annee: [t for t in real(s, annee) if t[1] == annee])
    broken = make_reform(spec, 2027, "faute")(baseline())
    monkeypatch.setattr(boutons_programmes, "_coefficients", real)
    with pytest.raises(AssertionError, match="rsa"):
        boutons_programmes.verifier_indexations(broken, spec, 2027)


# --------------------------------------------------------------------------- #
# L'enveloppe d'impôts de production
# --------------------------------------------------------------------------- #
def _firms(weights: tuple[float, ...] = (1_000.0, 200.0, 5.0)) -> pl.DataFrame:
    """Trois entreprises types : une PME sous les seuils de la CVAE et de la C3S, une ETI
    au-dessus des deux, une grande entreprise ; chacune pondérée."""
    return pl.DataFrame({
        "firm_id": ["pme", "eti", "ge"],
        "weight": list(weights),
        "chiffre_affaires": [3_000_000.0, 60_000_000.0, 2_000_000_000.0],
        "valeur_ajoutee": [1_200_000.0, 20_000_000.0, 600_000_000.0],
        "benefice_imposable": [200_000.0, 4_000_000.0, 150_000_000.0],
        "capital_libere_detenu_personnes_physiques": [True, False, False],
        "is_avant_report": [40_000.0, 1_000_000.0, 37_000_000.0],
    })


def _production(result, suffix: str = "") -> float:
    firms = result.firms
    weight = firms["weight"].to_numpy()
    return float(((firms[f"cvae{suffix}"] + firms[f"c3s{suffix}"]).to_numpy() * weight).sum())


def test_an_envelope_cuts_the_production_taxes_by_itself() -> None:
    """La baisse statique de la CVAE et de la C3S est l'enveloppe (D-380) : la C3S par son
    taux, la CVAE par un facteur réglé sur la population de la passe, au millionième."""
    from impots.entreprises.reforms import FirmReformSpec
    from impots.entreprises.runner import run

    law = _production(run(_firms(), year=YEAR))
    assert law > 0
    baisse = 0.4 * law
    result = run(_firms(), year=YEAR,
                 reform=FirmReformSpec(impots_production_baisse=baisse))
    cut = law - _production(result, "_reform")
    assert cut == pytest.approx(baisse, rel=1e-5)
    traduction = result.guards["enveloppe"]
    assert traduction["baisse_cvae_eur"] + traduction["baisse_c3s_eur"] == pytest.approx(baisse)
    # Le prorata : chacune baisse de la même part de ce qu'elle rapporte.
    assert traduction["baisse_cvae_eur"] / traduction["cvae_loi_eur"] == pytest.approx(0.4)


def test_the_share_of_the_cvae_is_the_translation_s_hypothesis() -> None:
    from impots.entreprises.reforms import FirmReformSpec
    from impots.entreprises.runner import run

    law = run(_firms(), year=YEAR)
    c3s_law = float((law.firms["c3s"] * law.firms["weight"]).sum())
    result = run(_firms(), year=YEAR, reform=FirmReformSpec(
        impots_production_baisse=0.5 * c3s_law, impots_production_part_cvae=0.0))
    firms = result.firms
    assert float((firms["c3s_reform"] * firms["weight"]).sum()) == pytest.approx(0.5 * c3s_law)
    assert np.allclose(firms["cvae_reform"].to_numpy(), firms["cvae"].to_numpy())


def test_an_envelope_of_nothing_costs_nothing() -> None:
    from impots.entreprises.reforms import FirmReformSpec
    from impots.entreprises.runner import run

    result = run(_firms(), year=YEAR, reform=FirmReformSpec(impots_production_baisse=0.0))
    assert _production(result, "_reform") == pytest.approx(_production(result))
    firms = result.firms
    assert np.allclose(firms["prelevements_entreprise_reform"].to_numpy(),
                       firms["prelevements_entreprise"].to_numpy())


def test_an_envelope_beyond_what_the_engine_carries_is_refused() -> None:
    from impots.entreprises.reforms import EnveloppeError, FirmReformSpec
    from impots.entreprises.runner import run

    law = _production(run(_firms(), year=YEAR))
    with pytest.raises(EnveloppeError, match="CFE"):
        run(_firms(), year=YEAR, reform=FirmReformSpec(impots_production_baisse=1.5 * law))


def test_an_untranslated_envelope_is_never_a_reform() -> None:
    from impots.entreprises.reforms import FirmReformSpec, make_reform

    with pytest.raises(ValueError, match="traduit"):
        make_reform(FirmReformSpec(impots_production_baisse=1e9), YEAR, "x")


@pytest.mark.parametrize("fields", [{"impots_production_part_cvae": 0.5},
                                    {"impots_production_baisse": 1e9, "c3s_taux": 0.001},
                                    {"impots_production_baisse": 1e9, "cvae_echelle": 0.5}])
def test_an_envelope_beside_the_knobs_it_sets_is_refused(fields: dict) -> None:
    from impots.entreprises.reforms import FirmReformSpec

    with pytest.raises(ValidationError):
        FirmReformSpec(**fields)
