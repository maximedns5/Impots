"""Le revenu des non-salariés (but 19, étape 2) : tiré de l'Insee, calé, câblé.

Sur la population de la fixture (`eec_sample.parquet`, 1/500), comme `test_population` :
le squelette, puis `attach_incomes` aux cibles ramenées à la part de la France que la
fixture représente.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots.population import incomes, margins
from impots.population.incomes import (
    attach_incomes,
    attach_self_employment,
    household_share_of_france,
)
from impots.population.skeleton import build_skeleton
from impots.population.to_openfisca import micro_turnover

FIXTURE = Path(__file__).parent / "fixtures" / "eec_sample.parquet"
DECLARATIONS_2042 = (Path(__file__).resolve().parents[1] / "data" / "raw"
                     / "dgfip_ir_2042_nat_export_2026-10-15.csv")


@pytest.fixture(scope="module")
def skeleton() -> pl.DataFrame:
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    frame, _ = build_skeleton(children_per_household=children,
                              source=pl.read_parquet(FIXTURE))
    return frame


@pytest.fixture(scope="module")
def population(skeleton: pl.DataFrame) -> tuple[pl.DataFrame, float]:
    share = household_share_of_france(skeleton)
    frame, _ = attach_incomes(skeleton, targets_scale=share)
    return frame, share


def _self_employed(frame: pl.DataFrame) -> np.ndarray:
    return ((frame["statut_activite"] == "employed") & ~frame["is_salarie"]).to_numpy()


def test_the_self_employment_income_is_calibrated_on_its_published_total(
        population: tuple[pl.DataFrame, float]) -> None:
    """Le total pondéré est la cible de l'Insee hors gérants majoritaires (73,76 Md€)
    ramenée à la fixture, comme la masse salariale l'est à la sienne. Échoue sur le code de
    l'étape 2, qui y comptait les gérants (117,5 Md€), et sur le code d'avant elle : la
    colonne n'existait pas."""
    frame, share = population
    total = float((frame["revenu_non_salarie_annuel"] * frame["weight"]).sum())
    assert total == pytest.approx(margins.SELF_EMPLOYMENT_INCOME.value * share, rel=1e-9)


def test_only_the_self_employed_draw_it_and_most_of_them_earn(
        population: tuple[pl.DataFrame, float]) -> None:
    """Un revenu et un régime pour chaque non-salarié, et pour lui seul. La part des
    revenus nuls publiée va de 0,8 % (micro-entrepreneurs) à 21,7 % (agricoles au réel) :
    5 % pour l'ensemble des non-agricoles, 16,9 % des agricoles."""
    frame, _ = population
    self_employed = _self_employed(frame)
    regime = frame["regime_non_salarie"].to_numpy()
    income = frame["revenu_non_salarie_annuel"].to_numpy()
    assert all(r in incomes.REGIMES for r in regime[self_employed])
    assert all(r is None for r in regime[~self_employed])
    assert (income[~self_employed] == 0).all()
    # The gérants majoritaires are paid a salary, not a profit (étape « ir »).
    gerant = np.isin(regime, ("gerant_bic", "gerant_bnc"))
    earning = self_employed & ~gerant
    weight = frame["weight"].to_numpy()[earning]
    nil = float(weight[income[earning] == 0].sum() / weight.sum())
    assert 0.0 < nil < 0.15


def test_the_draw_moves_no_pension_or_unemployment_benefit_and_wages_by_one_factor(
        skeleton: pl.DataFrame, monkeypatch: pytest.MonkeyPatch) -> None:
    """Le tirage des non-salariés lit son propre flux : les pensions et allocations chômage
    sont celles d'avant lui, euro pour euro. Les salaires des salariés aussi, à un facteur
    commun près : les gérants majoritaires sont payés sur D11 (étape « ir »), ce qu'ils
    reçoivent manque aux autres, et rien d'autre ne bouge."""
    share = household_share_of_france(skeleton)
    after, stats = attach_incomes(skeleton, targets_scale=share)

    def nothing(frame: pl.DataFrame, seed: int, targets_scale: float):
        empty = pl.Series([None] * frame.height, dtype=pl.String)
        return frame.with_columns(pl.lit(0.0).alias("revenu_non_salarie_annuel"),
                                  empty.alias("regime_non_salarie"),
                                  empty.alias("secteur_non_salarie"),
                                  pl.lit(0.0).alias(incomes.GERANT_GROSS_PAY)), None

    monkeypatch.setattr(incomes, "attach_self_employment", nothing)
    before, _ = attach_incomes(skeleton, targets_scale=share)
    for column in ("pension_annuelle", "chomage_annuel"):
        assert after[column].to_list() == before[column].to_list(), column
    employee = (skeleton["is_salarie"] & (skeleton["statut_activite"] == "employed")).to_numpy()
    ratio = (after["salaire_brut_annuel"].to_numpy()[employee]
             / before["salaire_brut_annuel"].to_numpy()[employee])
    d11 = margins.TOTAL_GROSS_WAGES.value * share
    assert ratio == pytest.approx(1.0 - stats.gerants_gross_pay / d11, rel=1e-9)


def test_the_gerants_are_paid_their_declared_pay_out_of_d11(
        population: tuple[pl.DataFrame, float]) -> None:
    """Un gérant majoritaire est payé en salaire (art. 62 du CGI), pas en bénéfice : la part
    imposable de ces salaires est celle des cases 1GB à 1JB (30,7 Md€), et la masse brute de
    tous est D11, celle des salariés ramenée au champ de l'enquête (étape « haut »). Échoue sur le code de l'étape 2, qui leur donnait
    43,8 Md€ de BIC et de BNC à côté d'une masse salariale qui les comptait déjà."""
    frame, share = population
    regime = frame["regime_non_salarie"].to_numpy()
    gerant = np.isin(regime, ("gerant_bic", "gerant_bnc"))
    weight = frame["weight"].to_numpy()
    wages = frame["salaire_brut_annuel"].to_numpy()
    assert gerant.any()
    assert (frame["revenu_non_salarie_annuel"].to_numpy()[gerant] == 0).all()
    assert (wages[gerant] > 0).mean() >= 0.75  # 12,7 % de revenus nuls publiés
    taxable = incomes.IMPOSABLE_SUR_BRUT * float((wages * weight)[gerant].sum())
    assert taxable == pytest.approx(margins.GERANTS_REMUNERATION.value * share, rel=1e-9)
    gerants = float((wages * weight)[gerant].sum())
    assert float((wages * weight).sum()) == pytest.approx(
        gerants + (margins.TOTAL_GROSS_WAGES.value * share - gerants)
        * margins.CHAMP_SALARIES_ENQUETE.value, rel=1e-9)
    # No share of a gérant's pay is exempt: its taxable part is the declared one.
    assert (frame[incomes.EXEMPT_SHARE].to_numpy()[gerant] == 0).all()


def test_the_exempt_share_makes_the_declared_salaries(
        population: tuple[pl.DataFrame, float]) -> None:
    """La part exonérée d'impôt des salaires (heures supplémentaires, apprentis, épargne
    salariale…) est fixée pour que les salaires imposables des salariés, lus par openfisca
    et cette part déduite, refassent les salaires déclarés (`DECLARED_TAXABLE_WAGES`) à 3 %
    près : `IMPOSABLE_SUR_BRUT` est un rapport moyen, mesuré sur la population et non sur la
    fixture. Échoue sur le code d'avant : il n'y avait pas de part, et les salaires
    imposables passaient de 7 % les salaires déclarés.

    Depuis l'étape « haut » (la masse des salariés ramenée au champ de l'enquête), la part
    vaut 2,1 % sur la population ; sur cette fixture, dont les salariés pèsent moins, les
    salaires imposables passent déjà sous les salaires déclarés, et la part, qui ne peut être
    négative, est nulle : les salaires imposables restent alors sous la cible, sans part."""
    from impots.engine.system import baseline
    from impots.population.to_openfisca import build_simulation

    frame, share = population
    frame = frame.sort("person_id")
    exempt = frame[incomes.EXEMPT_SHARE].to_numpy()
    employee = (frame["is_salarie"] & (frame["statut_activite"] == "employed")).to_numpy()
    paid = employee & (frame["salaire_brut_annuel"].to_numpy() > 0)
    assert exempt.min() >= 0.0
    assert np.unique(exempt[paid]).size == 1  # une part commune
    assert (exempt[~employee] == 0).all()
    built = build_simulation(frame, baseline(), 2024)
    taxable = built.simulation.calculate_add("salaire_imposable", "2024")
    declared = float((taxable * (1 - exempt) * frame["weight"].to_numpy())[employee].sum())
    target = margins.DECLARED_TAXABLE_WAGES.value * share
    if exempt[paid][0] > 0:
        assert declared == pytest.approx(target, rel=0.03)
    else:
        assert declared < target * 1.03


def test_the_draw_is_reproducible(skeleton: pl.DataFrame) -> None:
    """Même graine, même tirage ; une autre graine, un autre."""
    share = household_share_of_france(skeleton)
    one, _ = attach_self_employment(skeleton, targets_scale=share)
    two, _ = attach_self_employment(skeleton, targets_scale=share)
    other, _ = attach_self_employment(skeleton, seed=7, targets_scale=share)
    column = "revenu_non_salarie_annuel"
    assert one[column].to_list() == two[column].to_list()
    assert one[column].to_list() != other[column].to_list()


def test_the_sector_reads_the_naf_division_and_the_pcs() -> None:
    """Le médecin et l'infirmier libéraux sont dans la même division (86) : la PCS les
    sépare, comme le pharmacien du commerce de détail."""
    naf = np.array(["86", "86", "86", "47", "47", "01", "69", None, "00"], dtype=object)
    pcs = np.array(["cadre", "profession_intermediaire", None, "cadre", None, None, "cadre",
                    None, None], dtype=object)
    assert incomes._sector_cells(naf, pcs).tolist() == [
        "medecins", "paramedicaux", "autres_sante", "pharmacie", "detail",
        incomes.AGRICULTURE, "juridique", "ensemble", "ensemble"]


def test_the_micro_turnover_inverts_openfisca_s_abatement() -> None:
    """La case est le chiffre d'affaires ; le revenu de l'Insee, ce qu'il en reste après
    l'abattement d'openfisca, max(taux × CA, 305 €)."""
    income = np.array([0.0, 50.0, 1_000.0, 20_000.0])
    for rate in (0.71, 0.50, 0.34):
        turnover = micro_turnover(income, rate, 305.0)
        assert turnover - np.maximum(rate * turnover, np.where(turnover > 0, 305.0, 0.0)) \
            == pytest.approx(income)


def test_openfisca_reads_the_drawn_income_back(
        population: tuple[pl.DataFrame, float]) -> None:
    """Ce que la population tire est ce qu'openfisca impose : le revenu professionnel
    (`rpns_imposables`) et le bénéfice au versement libératoire (`microentreprise`, au
    foyer) refont le revenu tiré, foyer par foyer, à deux euros près : le moteur arrondit
    (114 511 € lus pour 114 512,22 tirés). Et la CSG d'un classique au réel n'est plus
    nulle."""
    from impots.engine.system import baseline
    from impots.population.to_openfisca import build_simulation

    frame, _ = population
    frame = frame.sort("person_id")
    built = build_simulation(frame, baseline(), 2024)
    rpns = built.simulation.calculate("rpns_imposables", "2024")
    liberatoire = built.simulation.calculate("microentreprise", "2024")
    foyer = np.searchsorted(built.foyer_ids, frame["foyer_id"].to_numpy().astype(str))
    drawn = np.bincount(foyer, weights=frame["revenu_non_salarie_annuel"].to_numpy(),
                        minlength=built.foyer_ids.size)
    read = np.bincount(foyer, weights=rpns, minlength=built.foyer_ids.size) + liberatoire
    assert read == pytest.approx(drawn, abs=2.0)

    csg = -(built.simulation.calculate("csg_deductible_non_salarie", "2024")
            + built.simulation.calculate("csg_imposable_non_salarie", "2024"))
    reel = frame["regime_non_salarie"].is_in(["reel_bic", "reel_bnc"]).fill_null(False) \
        & (frame["revenu_non_salarie_annuel"] > 0)
    assert (csg[reel.to_numpy()] > 0).all()

    # openfisca's `revenus_non_salarie_nets` adds the liberatory profit of the whole
    # simulation to each person (`sum` of a vector): a population wired on those boxes had
    # a median niveau de vie of 3.9 M€. The net income cannot exceed the income drawn.
    nets = built.simulation.calculate("revenus_non_salarie_nets", "2024")
    assert nets.sum() <= frame["revenu_non_salarie_annuel"].sum()


@pytest.mark.skipif(not DECLARATIONS_2042.exists(),
                    reason="2042 aggregates absent — `make data`")
def test_the_versement_liberatoire_shares_are_the_declared_boxes() -> None:
    """Les parts du versement libératoire sont les cases remplies de la 2042-C-PRO 2024."""
    from impots.population import ingest

    boxes = ingest.load_declarations_2042().filter(pl.col("Année") == "2024")
    count = dict(zip(boxes["Nom"].to_list(), boxes["Nombre"].to_list(), strict=True))
    cases = {"vente": (("5TA", "5UA"), ("5KO", "5LO", "5MO")),
             "service": (("5TB", "5UB", "5VB"), ("5KP", "5LP", "5MP")),
             "bnc": (("5TE", "5UE"), ("5HQ", "5IQ", "5JQ"))}
    for nature, (with_vl, without) in cases.items():
        assert margins.VERSEMENT_LIBERATOIRE[nature] == (
            int(sum(count[c] for c in with_vl)), int(sum(count[c] for c in without)))


INSEE_2114 = (Path(__file__).resolve().parents[1] / "data" / "raw"
              / "insee_ip2114_revenus_non_salaries_2024.xlsx")

#: margins' row -> the Insee's label, in the complementary tables of n° 2114.
LIBELLES = {
    "industrie": "Industrie (hors artisanat commercial)", "construction": "Construction",
    "commerce_auto": "Commerce et réparation d'automobiles",
    "commerce_gros": "Commerce de gros", "pharmacie": "Commerce pharmaceutique",
    "metiers_bouche": "Métiers de bouche",
    "detail_magasin": "Commerce de détail en magasin",
    "detail_hors_magasin": "Commerce de détail hors magasin", "transports": "Transports",
    "hebergement_restauration": "Hébergement et restauration",
    "information_communication": "Information et communication",
    "finance": "Activités financières et d'assurance", "immobilier": "Activités immobilières",
    "juridique": "Activités juridiques et comptables", "conseil": "Conseil de gestion",
    "architecture": "Architecture, ingénierie",
    "autres_specialisees": "Autres activités spécialisées", "veterinaires": "Vétérinaires",
    "services_administratifs": "Services administratifs et de soutien aux entreprises",
    "arts": "Arts, spectacles et activités récréatives", "enseignement": "Enseignement",
    "services_personnels": "Services personnels", "medecins": "Médecins et dentistes",
    "paramedicaux": "Professions paramédicales, sages-femmes",
    "autres_sante": "Autres services de santé et action sociale",
}


def _sheet(name: str) -> dict[str, tuple]:
    import openpyxl

    book = openpyxl.load_workbook(INSEE_2114, read_only=True, data_only=True)
    return {str(r[0]).strip(): r[1:] for r in book[name].iter_rows(values_only=True)
            if r[0] is not None}


@pytest.mark.skipif(not INSEE_2114.exists(), reason="Insee Première n° 2114 absente")
def test_the_sector_tables_are_the_insee_s_cells() -> None:
    """Chaque nombre des tables par secteur de `margins` est la case de l'Insee : une
    erreur de recopie déplacerait un secteur entier."""
    c1 = _sheet("Tableau complémentaire 1")
    c2 = _sheet("Tableau complémentaire 2")
    c3 = _sheet("Tableau complémentaire 3")
    libelles = {**LIBELLES, "ensemble": None}
    for row, label in libelles.items():
        count, zero, *quantiles, mean, gerants = margins.CLASSIQUES_PAR_SECTEUR[row]
        dispersion = c3[label or "Ensemble des non-salariés hors micro-entrepreneurs"]
        assert (count, zero, *quantiles) == pytest.approx(dispersion[:7]), row
        table = c1[label or "Ensemble"]
        # La publication arrondit la part des gérants au centième, la case ne l'est pas.
        assert gerants == pytest.approx(table[2], abs=0.005), row
        assert mean == pytest.approx(table[6]), row
        if row in margins.MICRO_PAR_SECTEUR:
            micro = c2[label or "Ensemble"]
            assert margins.MICRO_PAR_SECTEUR[row] == pytest.approx(
                (micro[0], micro[2], table[5])), row
        else:
            assert c2[label][0] == "so", row
    micro = c3["Micro-entrepreneurs économiquement actifs"]
    assert (margins.MICRO_PART_NULLE, *margins.MICRO_QUANTILES) == pytest.approx(micro[1:7])
    agricoles = _sheet("Figure encadre")
    for key, label in (("reel", "Non-salariés du régime agricole imposés au régime réel"),
                       ("micro_ba", "Micro-bénéfices agricoles (micro-BA) économiquement "
                                    "actifs")):
        cells = agricoles[label]
        assert margins.AGRICOLES[key] == pytest.approx((cells[0], cells[2], cells[6])), key
