"""Les boutons qui lisent les données de ménages imputées (but 21, étape 4, suite).

Chaque bouton est tenu sur un ménage type dont les entrées sont écrites à la main (le
format d'entrée ne les porte pas) : ce qu'il ôte, ce qu'il laisse, et 0 € à sa valeur par
défaut. Les valeurs sont celles d'aucun candidat : aucune mesure n'est chiffrée ici.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from impots.api.schemas import HouseholdInput, ReformSpec
from impots.engine import situations
from impots.engine.compute import _build
from impots.engine.system import baseline, reformed_for
from impots.population import imputations as imp

YEAR = 2026
SALARIE = {"adults": [{"salaire_brut_annuel": 30_000, "annee_naissance": 1985}]}
#: Un parent seul de deux enfants mineurs, imposable.
PARENT = {"adults": [{"salaire_brut_annuel": 60_000, "annee_naissance": 1985}],
          "children": [{"annee_naissance": 2012}, {"annee_naissance": 2015}]}


def _simulation(system, household: dict, entrees: dict):
    situation = situations.build_situation(HouseholdInput.model_validate(household), YEAR,
                                           True)
    personne = next(iter(situation["individus"]))
    situation["individus"][personne].update(
        {nom: valeur if isinstance(valeur, dict) else {str(YEAR): valeur}
         for nom, valeur in entrees.items()})
    return _build(system, situation, YEAR, "full")


def _lire(system, household: dict, entrees: dict, *variables: str) -> dict[str, float]:
    simulation = _simulation(system, household, entrees)
    return {v: float(simulation.calculate_add(v, str(YEAR)).sum()) for v in
            ("impot_revenu_restant_a_payer", "revenu_disponible", *variables)}


def _deux(spec: ReformSpec, household: dict, entrees: dict, *variables: str):
    return (_lire(baseline(), household, entrees, *variables),
            _lire(reformed_for(spec, YEAR), household, entrees, *variables))


# --- les pensions alimentaires perçues ------------------------------------------------
PENSION = {"pensions_alimentaires_percues": 6_000.0}


def test_the_alimony_leaves_the_taxable_income_up_to_the_ceiling_per_child() -> None:
    """6 000 € perçus, deux enfants, 1 234 € par enfant : 2 468 € sortent des revenus
    imposés comme des pensions, et l'impôt baisse."""
    spec = ReformSpec(pensions_alimentaires_exonerees=True,
                      pensions_alimentaires_plafond_par_enfant=1_234.0)
    avant, apres = _deux(spec, PARENT, PENSION, "revenu_assimile_pension")
    assert avant["revenu_assimile_pension"] == pytest.approx(6_000.0)
    assert apres["revenu_assimile_pension"] == pytest.approx(6_000.0 - 2 * 1_234.0)
    assert apres["impot_revenu_restant_a_payer"] > avant["impot_revenu_restant_a_payer"]


def test_the_alimony_is_exempt_from_the_priced_year_only() -> None:
    """Le premier jour, les revenus de N-1 et N-2 restent imposés comme ils l'étaient : le
    revenu fiscal de référence qui fixe le taux de CSG d'une pension ou l'ARS ne bouge pas
    (sans la date, le garde des secteurs refusait la passe : 18 M€ de CSG sur les pensions
    sans instrument, 1 500 ménages)."""
    spec = ReformSpec(pensions_alimentaires_exonerees=True,
                      pensions_alimentaires_plafond_par_enfant=1_234.0)
    entrees = {"pensions_alimentaires_percues": {str(y): 6_000.0 for y in (2024, 2025, 2026)}}
    loi = _simulation(baseline(), PARENT, entrees)
    reforme = _simulation(reformed_for(spec, YEAR), PARENT, entrees)
    for annee, ecart in (("2024", 0.0), ("2025", 0.0), ("2026", 2 * 1_234.0)):
        assert (float(loi.calculate("revenu_assimile_pension", annee).sum())
                - float(reforme.calculate("revenu_assimile_pension", annee).sum())
                == pytest.approx(ecart)), annee


def test_the_alimony_at_the_law_costs_nothing() -> None:
    avant, apres = _deux(ReformSpec(pensions_alimentaires_exonerees=False), PARENT, PENSION)
    assert apres == avant


def test_an_alimony_ceiling_without_the_exemption_is_refused() -> None:
    with pytest.raises(ValidationError, match="pensions_alimentaires_exonerees"):
        ReformSpec(pensions_alimentaires_plafond_par_enfant=1_000.0)


# --- la réduction d'impôt sur les intérêts d'emprunt ----------------------------------
INTERETS = {"interets_emprunt_residence_principale": 5_000.0}


def test_the_interest_reduction_reads_the_minors_and_stops_at_its_ceiling() -> None:
    """Deux enfants mineurs : 60 % de 5 000 €, 3 000 €, bornés à 700 + 2 × 150 = 1 000 €.
    Sans plafond, 60 % de 2 000 €, 1 200 € entiers (sous l'impôt de 1 554 €)."""
    spec = ReformSpec(interets_emprunt_taux=[0.0, 0.3, 0.6], interets_emprunt_plafond=700.0,
                      interets_emprunt_plafond_par_enfant=150.0)
    avant, apres = _deux(spec, PARENT, INTERETS)
    assert (apres["impot_revenu_restant_a_payer"] - avant["impot_revenu_restant_a_payer"]
            == pytest.approx(1_000.0))
    _, sans = _deux(ReformSpec(interets_emprunt_taux=[0.0, 0.3, 0.6]), PARENT,
                    {"interets_emprunt_residence_principale": 2_000.0})
    assert (sans["impot_revenu_restant_a_payer"] - avant["impot_revenu_restant_a_payer"]
            == pytest.approx(1_200.0))


def test_the_interest_reduction_is_a_reduction() -> None:
    """Sans enfant, le premier taux ; et la réduction s'arrête à l'impôt dû."""
    avant, apres = _deux(ReformSpec(interets_emprunt_taux=[0.0, 0.3]), SALARIE, INTERETS)
    assert apres == avant
    avant, apres = _deux(ReformSpec(interets_emprunt_taux=[0.9]), SALARIE,
                         {"interets_emprunt_residence_principale": 50_000.0})
    assert avant["impot_revenu_restant_a_payer"] < 0
    assert apres["impot_revenu_restant_a_payer"] == pytest.approx(0.0)


def test_no_interest_costs_nothing() -> None:
    avant, apres = _deux(ReformSpec(interets_emprunt_taux=[0.3]), PARENT, {})
    assert apres == avant


# --- le crédit d'impôt sur les frais de trajet ----------------------------------------
TRAJETS = {"frais_trajet_domicile_travail": 4_000.0}


def test_the_commuting_credit_is_its_rate_above_the_threshold_within_the_ceiling() -> None:
    """20 % de 4 000 − 1 000 €, 600 €, bornés à 500 € ; un crédit, qui va au revenu
    disponible même au-delà de l'impôt."""
    spec = ReformSpec(credit_trajets_taux=0.2, credit_trajets_franchise=1_000.0,
                      credit_trajets_plafond=500.0)
    avant, apres = _deux(spec, SALARIE, TRAJETS)
    assert (apres["revenu_disponible"] - avant["revenu_disponible"]
            == pytest.approx(500.0, abs=0.01))
    avant, apres = _deux(ReformSpec(credit_trajets_taux=0.2), SALARIE,
                         {"frais_trajet_domicile_travail": 10_000.0})
    assert (apres["impot_revenu_restant_a_payer"] - avant["impot_revenu_restant_a_payer"]
            == pytest.approx(2_000.0))
    assert apres["impot_revenu_restant_a_payer"] > 0  # au-delà des 788 € d'impôt


def test_a_commuting_credit_of_nothing_costs_nothing() -> None:
    avant, apres = _deux(ReformSpec(credit_trajets_taux=0.0), SALARIE, TRAJETS)
    assert apres == avant


# --- l'exonération des heures supplémentaires -----------------------------------------
HEURES = {"heures_sup_brut": 3_000.0, "heures_sup_nombre": 150.0}
LIGNES = ("cotisations_salariales", "csg_deductible_salaire", "csg_imposable_salaire",
          "crds_salaire", "salaire_super_brut", "salaire_de_base", "salaire_net")


def test_the_overtime_exemption_takes_its_share_of_the_hours_beyond_the_threshold() -> None:
    """150 heures pour 3 000 €, 30 d'abord non exonérées, 60 au plus : 60 heures, 1 200 €,
    4 % des 30 000 € bruts. La moitié de la CSG et de la CRDS de cette part sort, et la
    moitié des cotisations patronales nettes ; l'impôt ne bouge pas : le net imposable
    que les heures gagnent reste exonéré."""
    spec = ReformSpec(heures_sup_exoneration_csg_crds=0.5,
                      heures_sup_exoneration_patronale=0.5,
                      heures_sup_franchise_heures=30.0, heures_sup_plafond_heures=60.0)
    avant, apres = _deux(spec, SALARIE, HEURES, *LIGNES)
    part = 0.5 * 1_200.0 / 30_000.0
    for ligne in ("csg_deductible_salaire", "csg_imposable_salaire", "crds_salaire"):
        assert apres[ligne] == pytest.approx(avant[ligne] * (1.0 - part)), ligne
    employeur = avant["salaire_super_brut"] - avant["salaire_de_base"]
    assert (avant["salaire_super_brut"] - apres["salaire_super_brut"]
            == pytest.approx(part * employeur, abs=0.01))
    assert apres["impot_revenu_restant_a_payer"] == pytest.approx(
        avant["impot_revenu_restant_a_payer"])
    assert apres["salaire_net"] > avant["salaire_net"]


def test_the_salaried_exemption_takes_only_what_the_law_leaves(monkeypatch) -> None:
    """Un non-cadre du privé ne paie que ses cotisations de retraite, 11,31 % du brut, que
    la loi ôte déjà de ses heures (CSS art. D. 241-21) : rien de plus à exonérer (un cadre
    au-dessus du plafond de la sécurité sociale en paie moins encore). Avec une réduction
    légale ramenée à 5 % par la main du test, la part au-delà sort : la moitié de ce qui
    dépasse 5 % du brut, sur les 5 % du salaire que portent les 75 heures exonérées."""
    from impots.engine import boutons_programmes

    spec = ReformSpec(heures_sup_exoneration_salariale=0.5,
                      heures_sup_plafond_heures=75.0)
    avant, apres = _deux(spec, SALARIE, HEURES, *LIGNES)
    assert avant["cotisations_salariales"] == pytest.approx(-0.1131 * 30_000.0, abs=1.0)
    assert apres == avant
    monkeypatch.setattr(boutons_programmes, "TAUX_REDUCTION_HEURES_SUP_LOI", 0.05)
    avant, apres = _deux(spec, SALARIE, HEURES, *LIGNES)
    reste = -avant["cotisations_salariales"] - 0.05 * 30_000.0
    assert (apres["cotisations_salariales"] - avant["cotisations_salariales"]
            == pytest.approx(0.5 * (1_500.0 / 30_000.0) * reste, abs=0.05))
    assert apres["impot_revenu_restant_a_payer"] == pytest.approx(
        avant["impot_revenu_restant_a_payer"])


def test_no_overtime_and_no_exemption_cost_nothing() -> None:
    spec = ReformSpec(heures_sup_exoneration_csg_crds=0.5)
    avant, apres = _deux(spec, SALARIE, {}, *LIGNES)
    assert apres == avant
    avant, apres = _deux(ReformSpec(heures_sup_exoneration_csg_crds=0.0), SALARIE, HEURES,
                         *LIGNES)
    assert apres == avant


def test_an_hours_bound_without_an_exemption_is_refused() -> None:
    with pytest.raises(ValidationError, match="ne borne rien"):
        ReformSpec(heures_sup_plafond_heures=100.0)


# --- la passe -------------------------------------------------------------------------
@pytest.mark.parametrize("knobs", [{"pensions_alimentaires_exonerees": True},
                                   {"interets_emprunt_taux": [0.1]},
                                   {"credit_trajets_taux": 0.1},
                                   {"heures_sup_exoneration_csg_crds": 0.1},
                                   {"cvec_montant": 50.0}])
def test_each_knob_imputes_the_households_data(knobs) -> None:
    """Une passe qui règle un de ces boutons impute les données de ménages, à toute année :
    le runner les vieillit (`menages.impute`)."""
    assert imp.imputations(ReformSpec(**knobs), 2027).menages


def test_a_population_pass_without_the_data_is_refused() -> None:
    import polars as pl

    from impots.population.runner import WiringError, run

    with pytest.raises(WiringError, match="données de ménages"):
        run(pl.DataFrame({"person_id": [1]}), year=YEAR, reform=ReformSpec(cvec_montant=50.0))


POPULATION_PATH = "population_2024.parquet"


@pytest.mark.parametrize("knobs", [
    {"heures_sup_exoneration_csg_crds": 0.3, "heures_sup_exoneration_patronale": 0.3,
     "heures_sup_exoneration_salariale": 0.3, "heures_sup_franchise_heures": 10.0},
    {"credit_trajets_taux": 0.05, "credit_trajets_franchise": 2_500.0},
    {"interets_emprunt_taux": [0.0, 0.1], "interets_emprunt_plafond": 300.0},
    {"pensions_alimentaires_exonerees": True,
     "pensions_alimentaires_plafond_par_enfant": 700.0},
    {"cvec_montant": 50.0},
    {"heures_sup_exoneration_csg_crds": 0.0},
], ids=["heures_sup", "trajets", "interets", "pensions", "cvec", "rien"])
def test_a_knob_on_the_households_data_balances_on_an_aged_population(knobs) -> None:
    """Sur 1 500 ménages vieillis de 2024 à 2026 : les données imputées sur 2024 et
    vieillies, le garde des secteurs reconstitue le coût (il refuse sinon), le coût est
    une dépense (une recette pour la CVEC abaissée de 105 à 50 €), et une exonération
    nulle coûte 0 € exactement. Des valeurs qu'aucun candidat ne propose."""
    import polars as pl

    from impots import uprating as up
    from impots.population import aggregate, menages
    from impots.population.cli import PROCESSED
    from impots.population.runner import run

    vieillissement = up.Uprating(wage=0.025, price=0.015, source="essai", base_year=2024)
    frame = up.uprate(pl.read_parquet(PROCESSED / POPULATION_PATH), 2026, vieillissement)
    reform = ReformSpec(**knobs)
    imputed = imp.imputations(reform, 2026)
    result = run(frame, year=2026, reform=reform, tier="full", sample=1_500,
                 **imputed.runner(),
                 menages_facteurs=menages.facteurs_de(vieillissement, 2026))
    agg = aggregate.aggregate(result.households)
    assert result.guards["menages"].facteurs["wage"] == pytest.approx(1.025 ** 2)
    if knobs == {"heures_sup_exoneration_csg_crds": 0.0}:
        assert agg.reform_cost == 0.0
        return
    assert agg.reform_cost > 0
    assert abs(agg.balance["unexplained"]) < 1e-3 * abs(agg.reform_cost)
    if "cvec_montant" in knobs:
        assert agg.deltas["cvec"] < 0
