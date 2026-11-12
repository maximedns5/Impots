"""Les données de ménages imputées pour les mesures des programmes (but 21, étape 4).

Chaque total imputé est celui de sa source par construction : ces tests tiennent que la
source est lue comme la `Figure` la dit, que la calibration refait son total, que les
règles de répartition (qui en a) sont celles que le module déclare, et que la passe les
porte jusqu'à openfisca. Aucun ne dit que les totaux sont justes : ils sont dépensés.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from impots.engine.system import baseline
from impots.population import imputations as imp
from impots.population import margins, menages, runner

DECLARATIONS_PRESENT = (menages.RAW / menages.DECLARATIONS_FILE).exists()
needs_boxes = pytest.mark.skipif(not DECLARATIONS_PRESENT,
                                 reason="cases 2042 absentes de data/raw")


@pytest.fixture(scope="module")
def population() -> pl.DataFrame:
    from impots.population.cli import PROCESSED

    frame = pl.read_parquet(PROCESSED / "population_2024.parquet")
    return runner.subsample(frame, 3_000).sort("person_id")


@pytest.fixture(scope="module")
def imputed(population):
    return menages.impute(population)


def _poids(frame: pl.DataFrame) -> np.ndarray:
    return frame.select(pl.col("weight").mean().over("household_id")).to_series().to_numpy()


# --- les sources ---------------------------------------------------------------------


@needs_boxes
@pytest.mark.parametrize("nom", sorted(menages.CASES))
def test_each_figure_is_its_boxes_in_the_manifested_export(nom) -> None:
    """La figure de `margins` et l'export 2042 disent le même montant, à l'euro."""
    nombre, montant = menages.declare(nom)
    assert montant == pytest.approx(menages.FIGURES[nom].value, abs=1.0)
    assert nombre > 0


@needs_boxes
def test_a_figure_the_export_contradicts_is_refused(monkeypatch) -> None:
    figure = margins.HEURES_SUP_DECLAREES
    monkeypatch.setitem(menages.FIGURES, "heures_sup",
                        type(figure)(**{**figure.__dict__, "value": figure.value * 1.01}))
    with pytest.raises(menages.MenagesError, match="la figure"):
        menages.declare("heures_sup")


def test_the_deduction_is_the_trees() -> None:
    """La déduction de 10 % que la loi des frais réels compare est celle de l'arbre."""
    abatpro = baseline().parameters("2024-01-01").impot_revenu.calcul_revenus_imposables \
        .deductions.abatpro
    assert pytest.approx(float(abatpro.taux)) == menages.DEDUCTION_TAUX
    assert float(abatpro.min) == menages.DEDUCTION_MIN
    assert float(abatpro.max) == menages.DEDUCTION_MAX


def test_every_imputed_figure_is_spent() -> None:
    for figure in (*menages.FIGURES.values(), margins.INTERETS_EMPRUNT_RESIDENCE_PRINCIPALE):
        assert figure.use == "calibration", figure.scope


# --- la calibration ------------------------------------------------------------------


@needs_boxes
def test_each_total_is_its_source(imputed) -> None:
    """Le montant de chaque donnée refait sa cible (dépensée) ; le nombre de qui en a la
    refait au tirage près, sauf les ménages accédants, dont le nombre n'est pas calé."""
    frame, stats = imputed
    poids_moyen = float(_poids(frame).mean())
    for c in stats.composantes:
        assert c.depense
        assert abs(c.ecart_montant) < menages.TOLERANCE_MONTANT, c.nom
        if c.nom != "interets_emprunt":
            # Un tirage de Bernoulli : quatre écarts-types relatifs sur ce nombre de tirés.
            tires = c.cible_nombre / poids_moyen
            assert abs(c.ecart_nombre) < 4.0 / np.sqrt(tires), (c.nom, c.ecart_nombre)


@needs_boxes
def test_the_exempt_share_keeps_its_total_and_moves_to_overtime(population, imputed) -> None:
    """Les heures supplémentaires sont prises dans la part exonérée : le total exonéré ne
    bouge pas, et qui fait des heures a une part plus haute que qui n'en fait pas."""
    from impots.population.incomes import EXEMPT_SHARE, IMPOSABLE_SUR_BRUT

    frame, _ = imputed
    poids = _poids(population)
    imposable = IMPOSABLE_SUR_BRUT * population["salaire_brut_annuel"].to_numpy()
    avant = float((population[EXEMPT_SHARE].to_numpy() * imposable * poids).sum())
    apres = float((frame[EXEMPT_SHARE].to_numpy() * imposable * poids).sum())
    assert apres == pytest.approx(avant, rel=1e-9)
    hs = frame[menages.HEURES_SUP].to_numpy()
    part = frame[EXEMPT_SHARE].to_numpy()
    porteurs = population[EXEMPT_SHARE].to_numpy() > 0
    assert part[porteurs & (hs > 0)].min() > part[porteurs & (hs == 0)].max()
    assert hs.max() <= menages.PLAFOND_HEURES_SUP
    # Des heures communes à temps plein : le montant suit le salaire horaire.
    heures = frame[menages.HEURES_SUP_HEURES].to_numpy()
    plein = (hs > 0) & (hs < menages.PLAFOND_HEURES_SUP) \
        & (frame["quotite_travail"].to_numpy() == 1.0)
    assert np.ptp(heures[plein]) < 1e-6 * heures[plein].max()


@needs_boxes
def test_frais_reels_are_declared_above_the_deduction_only(imputed) -> None:
    frame, _ = imputed
    from impots.population.incomes import IMPOSABLE_SUR_BRUT

    trajet = frame[menages.FRAIS_TRAJET].to_numpy()
    reels = frame[menages.FRAIS_REELS].to_numpy()
    deduction = np.clip(menages.DEDUCTION_TAUX * IMPOSABLE_SUR_BRUT
                        * frame["salaire_brut_annuel"].to_numpy(),
                        menages.DEDUCTION_MIN, menages.DEDUCTION_MAX)
    assert np.array_equal(reels > 0, trajet > deduction)
    assert np.allclose(reels[reels > 0], trajet[reels > 0])
    assert (trajet[frame["salaire_brut_annuel"].to_numpy() == 0] == 0).all()


@needs_boxes
def test_who_has_what_follows_the_declared_rules(imputed) -> None:
    frame, _ = imputed
    foyers = menages._foyers(frame)
    principal = frame["role_foyer"].to_numpy() == "declarant_principal"
    age = frame["age"].to_numpy()
    percue = frame[menages.PENSION_PERCUE].to_numpy() > 0
    assert (principal & frame["parent_isole"].to_numpy())[percue].all()
    mineurs = frame[menages.PENSION_VERSEE_MINEURS].to_numpy() > 0
    assert (principal & ~foyers["couple"].to_numpy() & (foyers["a_charge"].to_numpy() == 0)
            & (age >= 25) & (age <= 64))[mineurs].all()
    garde = frame[menages.FRAIS_GARDE].to_numpy() > 0
    assert ((frame["role_foyer"].to_numpy() == "personne_a_charge") & (age < 6))[garde].all()
    interets = frame[menages.INTERETS_EMPRUNT].to_numpy() > 0
    assert ((frame["statut_occupation"].to_numpy() == "primo_accedant")
            & (frame["role_menage"].to_numpy() == "personne_de_reference"))[interets].all()


@needs_boxes
def test_another_year_is_refused(population) -> None:
    with pytest.raises(menages.MenagesError, match="2025"):
        menages.impute(population, 2025)
    with pytest.raises(imp.ImputationRefusee, match="2025"):
        imp.imputations(None, 2025, demandees=[imp.MENAGES])


def test_the_imputation_is_asked_for_never_required() -> None:
    assert imp.imputations(None, 2024, demandees=[imp.MENAGES]).runner() == {
        "impute_menages": True}
    assert not imp.imputations(None, 2024).menages


# --- la passe ------------------------------------------------------------------------


@needs_boxes
def test_the_childcare_goes_child_by_child_onto_the_cases(imputed) -> None:
    frame, _ = imputed
    foyer_ids = np.sort(frame["foyer_id"].unique().to_numpy().astype(str))
    cases = menages.garde_par_foyer(frame, foyer_ids)
    total = sum(float(v.sum()) for v in cases.values())
    assert total == pytest.approx(float(frame[menages.FRAIS_GARDE].sum()))
    # Un foyer à deux enfants gardés a ses deux cases remplies.
    deux = (frame.filter(pl.col(menages.FRAIS_GARDE) > 0).group_by("foyer_id").len()
            .filter(pl.col("len") == 2)["foyer_id"])
    if deux.len():
        i = int(np.searchsorted(foyer_ids, str(deux[0])))
        assert cases["f7ga"][i] > 0 and cases["f7gb"][i] > 0


@needs_boxes
def test_openfisca_reads_the_imputed_data(imputed) -> None:
    """Les frais réels, les pensions perçues et versées et les frais de garde arrivent sur
    les variables d'openfisca de leur case."""
    from impots.population.to_openfisca import build_simulation

    frame, _ = imputed
    some = frame.filter(pl.col("household_id").is_in(
        frame.filter((pl.col(menages.PENSION_PERCUE) > 0) | (pl.col(menages.FRAIS_GARDE) > 0)
                     | (pl.col(menages.PENSION_VERSEE_MINEURS) > 0))["household_id"]
        .unique()[:60].implode()))
    built = build_simulation(some, baseline(), 2024)
    sim = built.simulation
    assert float(sim.calculate("frais_reels", "2024").sum()) == pytest.approx(
        float(some[menages.FRAIS_REELS].sum()), abs=len(some))
    assert float(sim.calculate_add("pensions_alimentaires_percues", "2024").sum()) == \
        pytest.approx(float(some[menages.PENSION_PERCUE].sum()), rel=1e-6)
    assert float(sim.calculate("f6gu", "2024").sum()) == pytest.approx(
        float(some[menages.PENSION_VERSEE_MINEURS].sum()), abs=len(some))
    garde = sum(float(sim.calculate(c, "2024").sum()) for c in menages.CASES_GARDE)
    assert garde == pytest.approx(float(some[menages.FRAIS_GARDE].sum()), abs=len(some))
