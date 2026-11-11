"""Les foyers fiscaux comme la DGFiP les compte (but 19, étape 3, D-365).

Le squelette sépare désormais le foyer fiscal de la famille : des concubins font deux
déclarations et une seule famille, un jeune majeur non rattaché déclare seul et reste
enfant de la famille. Ces tests tiennent les nombres que ce découpage tire de ses
sources publiées, sur le fixture de 400 logements (aucune passe sur la population).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
import pytest

from impots.population import margins
from impots.population.calibrate import TENURE, standard_margins, with_cells
from impots.population.incomes import household_share_of_france
from impots.population.skeleton import (
    _assign_units,
    _union_libre_probability,
    build_skeleton,
    child_share_by_age,
)

FIXTURE = Path(__file__).parent / "fixtures" / "eec_sample.parquet"


@pytest.fixture(scope="module")
def skeleton() -> pl.DataFrame:
    children = {key: np.array(value) for key, value in margins.CHILDREN_PER_FAMILY.items()}
    frame, _ = build_skeleton(children_per_household=children,
                              source=pl.read_parquet(FIXTURE))
    return frame


def test_the_child_share_holds_the_census_children_of_18_to_24() -> None:
    """La forme régionale, décalée sur l'échelle logit, retombe sur les 2 930 587
    enfants des familles de 18 à 24 ans du recensement 2021 (TD_FAM6v1)."""
    shares = child_share_by_age()
    population = margins.ORDINARY_HOUSEHOLD_POPULATION_15_24
    children = sum(population[15 if a < 20 else 20] / 5.0 * shares[a] for a in range(18, 25))
    assert children == pytest.approx(margins.CHILDREN_18_24.value, rel=1e-6)
    assert shares[18] == pytest.approx(0.7908, abs=1e-4)
    assert shares[24] == pytest.approx(0.3418, abs=1e-4)
    assert all(shares[a] > shares[a + 1] for a in range(17, 24))


def test_a_child_of_the_family_is_younger_than_a_young_adult_on_his_own(
        skeleton: pl.DataFrame) -> None:
    """Le tirage uniforme donnait 19,5 ans en moyenne aux deux ; le tirage selon la
    place donne aux enfants de la famille de 15 à 24 ans un âge moyen sous 19 ans."""
    young = skeleton.filter(pl.col("age").is_between(15, 24) & ~pl.col("synthetic"))
    child = young.filter(pl.col("role_famille") == "enfant")["age"].mean()
    other = young.filter(pl.col("role_famille") != "enfant")["age"].mean()
    assert child < 19.0 < other


def test_union_libre_probability_reads_the_census_by_age() -> None:
    assert _union_libre_probability(np.array([15, 24, 25, 47, 80, 95])).tolist() == [
        0.863051, 0.727370, 0.505629, 0.185745, 0.026810, 0.026810]


def test_rattached_adults_reach_case_0dj_at_the_frame_s_scale(skeleton: pl.DataFrame) -> None:
    """Les majeurs rattachés pondérés valent la case 0DJ (2 014 392), ramenée à la part
    de la France que pèse le fixture : à l'aléa du tirage près, sur 400 logements."""
    adults = skeleton.filter(
        (pl.col("role_foyer") == "personne_a_charge") & (pl.col("age") >= 18))
    target = margins.RATTACHES_MAJEURS.value * household_share_of_france(skeleton)
    assert float(adults["weight"].sum()) == pytest.approx(target, rel=0.35)
    # and no adult rattaché is past what the law allows
    assert adults.filter(pl.col("age") >= 25).is_empty()
    assert adults.filter((pl.col("age") >= 21) & (pl.col("statut_activite") == "employed")
                         ).is_empty()


def test_a_minor_is_never_a_declarant_in_his_parents_famille(skeleton: pl.DataFrame) -> None:
    minors = skeleton.filter((pl.col("age") < 18) & (pl.col("role_famille") == "enfant"))
    assert (minors["role_foyer"] == "personne_a_charge").all()


def test_concubins_are_two_foyers_and_one_famille() -> None:
    """Le conjoint en union libre déclare seul ; la famille de la CAF garde le couple et
    l'enfant ; l'enfant reste au foyer de la personne de référence, sans case T."""
    people = pl.DataFrame({
        "household_id": ["H-1"] * 4,
        "noi": ["01", "02", "03", "04"],
        "is_reference": [True, False, False, False],
        "is_conjoint": [False, True, False, False],
        "is_child": [False, False, True, True],
        "is_extra": [False, False, False, False],
        "separate_return": [False, True, False, False],
        "rattache": [False, False, True, False],
        "couple_flag": ["1", "1", "2", "2"],
        "hh_type": ["4"] * 4,
    })
    frame = _assign_units(people)
    assert frame["famille_id"].n_unique() == 1
    assert frame["role_famille"].to_list() == ["demandeur", "conjoint", "enfant", "enfant"]
    assert frame["foyer_id"].to_list() == ["H-1#0", "H-1#2", "H-1#0", "H-1#4"]
    assert frame["role_foyer"].to_list() == [
        "declarant_principal", "declarant_principal", "personne_a_charge",
        "declarant_principal"]
    assert not frame["parent_isole"].any()


def test_the_split_adds_foyers_and_leaves_the_familles(skeleton: pl.DataFrame) -> None:
    """Sur le fixture : plus de foyers que de familles, autant de familles qu'avant le
    découpage (une par unité 0 et par adulte en plus)."""
    assert skeleton["foyer_id"].n_unique() > skeleton["famille_id"].n_unique()
    units = skeleton.select(pl.col("famille_id").str.split("#").list.get(0)).n_unique()
    assert units == skeleton["household_id"].n_unique()
    per_foyer = skeleton.group_by("foyer_id").agg(
        (pl.col("role_foyer") == "declarant_principal").sum().alias("n"))
    assert (per_foyer["n"] == 1).all()


def test_tenure_targets_are_log_t10_shares_on_the_household_total() -> None:
    targets = margins.tenure_targets()
    assert sum(targets.values()) == pytest.approx(margins.HOUSEHOLDS.value, abs=1.0)
    assert targets["locataire_hlm"] / sum(targets.values()) == pytest.approx(
        4_546_449 / 31_220_147, rel=1e-9)
    assert set(TENURE.values()) == set(targets)


def test_the_tenure_margin_covers_every_household(skeleton: pl.DataFrame) -> None:
    framed = with_cells(skeleton)
    tenure = next(m for m in standard_margins(framed) if m.name == "tenure")
    assert set(framed["tenure"].unique()) <= set(tenure.targets)
