"""EEC fichier détail -> households of persons carrying OpenFisca entity roles.

Branch A' (D-012): the household *structure* is observed, everything else is
constructed. What the EEC gives us and what it does not:

  observed   dwelling membership (IDENT x TRIM), sex, activity status, housing
             tenure, household configuration, urban-unit class
  banded     age, in five groups — one of which (25-49) holds 36 % of the population
  absent     every income; every child under 15; region; who is whose partner or child

This module handles the structural half. `incomes.py` handles the money.

## The household unit

`IDENT` identifies a dwelling and `TRIM` a quarter. The survey rotates, so one
dwelling appears in up to four quarters; `EXTRIAN` is an annual weight that sums
to the 15+ population **over the whole file**, not per quarter. We therefore keep
every (IDENT, TRIM) as its own household observation and never rescale: summing
person weights across all of them already reproduces the population. This yields
199 451 households rather than the 80 171 distinct dwellings, which is more
observations at the same total weight.

## Who is whose

There is no link-to-reference-person variable, so relationships are inferred:

  reference person  the lowest `NOI` in the dwelling-quarter (INSEE's convention;
                    absent in 1.4 % of households, where the lowest present wins)
  conjoint          in a couple-typed household with exactly two `COUPL_LOG` = yes
                    persons, the coupled person who is not the reference
  dependent child   in a household typed as having children: anyone else young
                    enough to be rattaché — under 21 outright, or under 25 and not
                    in work (the closest proxy the EEC affords for "student").
                    The 15-24 band is the only one that can hold one, since
                    under-15s are absent from the file entirely.
  extra adult       anyone else — a flatmate, a grandparent, an adult child

The rule above makes a child of the FAMILLE (the CAF's unit, where the benefits'
own age and income tests then apply). The foyer fiscal is narrower since the but 19
(étape 3, D-365): rattachement is an option, so an eligible adult child is rattaché
with one probability set on case 0DJ, and a couple in union libre files two
déclarations (`_draw_foyers`). The exact age inside 15-24 is drawn by place in the
dwelling, a child of the family younger than a young adult on his own
(`_draw_young_ages_by_role`).

## One deviation from the spec, and why

PHASE1_SPEC §4.4 says "v1: one foyer + one famille per ménage". Measured on the
real file, 6 637 dwelling-quarters (3.3 %) hold more than two people aged 25+.
Folding those into a single foyer fiscal would make a 45-year-old flatmate a
`personne_a_charge` — inflating the household's quotient familial and zeroing a
tax liability that genuinely exists. The error per affected household is large
even though the share is small, and separating them costs about fifteen lines.

So: **one ménage per dwelling-quarter, but one tax unit per adult unit inside it.**
The reference person, their partner and their dependent children form unit 0;
each remaining adult becomes their own foyer fiscal and famille. Two couples
sharing a flat are still modelled as one couple plus two singles — that residue
is left, and counted, rather than hidden. Logged as D-013.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import polars as pl

from impots.population import logement, margins
from impots.population.ingest import load_eec

#: Published under-15 counts cover only children living with a resident parent.
#: Roughly 2 % of under-15s live with neither, so the synthesis targets the
#: published figure plus that residual (see margins.CHILDREN_UNDER_15).
UNATTACHED_CHILD_RESIDUAL = 0.02

#: How far the synthesised under-15 count may sit above the published target
#: before it is thinned. Thinning distorts the family-size distribution — and AF
#: has a cliff at two children — so a small excess is left alone and reported.
MAX_SILENT_CHILD_CORRECTION = 0.05

#: Fixed everywhere in the pipeline: the population must be reproducible bit for
#: bit, because the golden aggregates are asserted to the euro (§5).
SEED = 20240101

#: AGE6 code -> inclusive [low, high] year range. The '00' code ("14 ans ou
#: moins") is defined in the dictionary but carried by no row: the EEC surveys
#: the 15+ population, which is why children have to be synthesised.
AGE_BANDS: dict[str, tuple[int, int]] = {
    "15": (15, 24),
    "25": (25, 49),
    "50": (50, 64),
    "65": (65, 89),
    "90": (90, 99),
}

#: EEC `SO` -> OpenFisca `statut_occupation_logement`. Code 7 (usufruitier) has no
#: OpenFisca equivalent and behaves like ownership for our purposes; code 9 is
#: non-response (5 rows in the whole file).
STATUT_OCCUPATION: dict[str, str] = {
    "1": "primo_accedant",
    "2": "proprietaire",
    "3": "locataire_hlm",
    "4": "locataire_vide",
    "5": "locataire_meuble",
    "6": "loge_gratuitement",
    "7": "proprietaire",
    "9": "locataire_vide",
}

#: EEC `STCOMM2020` -> APL zone: no longer a mapping but a draw, ménage by ménage, on
#: the census's résidences principales of the same urban-unit status and tenure
#: (`logement.draw_zone_and_departement`, étape al of but 19). The mapping it replaces
#: (ville-centre and banlieue zone 2, the rest zone 3) could not produce zone 1.

#: EEC `PCS1Q` -> the four categories INSEE publishes wage distributions for.
#: Farmers (10) and artisans/shopkeepers (20) are self-employed: they get no wage, and
#: their income is drawn on their sector by `incomes.attach_self_employment`.
PCS_GROUP: dict[str, str] = {
    "30": "cadre",
    "40": "profession_intermediaire",
    "51": "employe",
    "52": "employe",
    "61": "ouvrier",
    "62": "ouvrier",
}

#: EEC `PUB3FP` -> the side of the public service (D-346).
FONCTION_PUBLIQUE = {"1": "etat", "2": "territoriale", "3": "hospitaliere"}

#: EEC `TXTPPRED` -> the fraction of a full-time job actually worked. Band
#: midpoints; "plus de 80 %" is read as 0.9. A part-timer whose rate is unrecorded
#: (`TPPRED` = 2 with no `TXTPPRED`) takes 0.6, near the observed average.
PART_TIME_FACTOR: dict[str, float] = {"1": 0.40, "2": 0.50, "3": 0.65, "4": 0.80, "5": 0.90}
PART_TIME_DEFAULT = 0.60

#: EEC `ACTEU` (BIT concept) refined by age band.
ACTIVITE: dict[str, str] = {"1": "employed", "2": "unemployed", "3": "inactive"}

#: Rattachement au foyer fiscal: unconditional below this age, and up to
#: `RATTACHEMENT_MAX_AGE` for a child still studying (art. 196 B CGI).
RATTACHEMENT_AGE = 21
RATTACHEMENT_MAX_AGE = 25

#: INSEE counts an "enfant d'une famille" up to any age, but the published
#: family-size margins used here are the under-25 tables, so that is the bound the
#: synthesis has to match.
INSEE_CHILD_MAX_AGE = 25

MENAGE_ROLES = ("personne_de_reference", "conjoint", "enfant", "autre")
FOYER_ROLES = ("declarant_principal", "conjoint", "personne_a_charge")
FAMILLE_ROLES = ("demandeur", "conjoint", "enfant")

COUPLE_HOUSEHOLD_TYPES = ("3", "4")      # couple sans enfant, couple avec enfant
CHILD_HOUSEHOLD_TYPES = ("2", "4")       # famille monoparentale, couple avec enfant


@dataclass(frozen=True)
class SkeletonStats:
    """What the assembly had to assume, counted. Feeds the reconciliation report."""

    households: int
    persons_observed: int
    children_synthesised: int
    households_with_extra_adults: int
    couple_households_without_a_pair: int
    households_missing_noi_01: int
    rattachement_probability: float = 1.0
    """The probability that an eligible adult child is rattaché (0DJ, `_draw_foyers`)."""


def _observed_persons(eec: pl.DataFrame) -> pl.DataFrame:
    """One row per surveyed person-quarter, with roles inferred."""
    over = pl.col("household_id")
    frame = (
        eec.select(
            pl.concat_str([pl.col("IDENT"), pl.lit("-"), pl.col("TRIM")]).alias("household_id"),
            pl.col("NOI").alias("noi"),
            pl.col("EXTRIAN").alias("weight"),
            pl.col("AGE6").alias("age_band"),
            pl.col("SEXE").alias("sexe"),
            pl.col("ACTEU").alias("acteu"),
            pl.col("TYPLOG5").alias("typlog"),
            pl.col("COUPL_LOG").alias("couple_flag"),
            pl.col("SO").alias("so"),
            pl.col("METRODOM").alias("metrodom"),
            pl.col("STCOMM2020").alias("stcomm"),
            pl.col("STATUT").alias("statut_emploi"),
            pl.col("PCS1Q").alias("pcs_code"),
            # The establishment's sector, NAF rév. 2 in 88 divisions: what the
            # self-employment income is drawn on (`incomes.py`), as the Insee publishes it.
            pl.col("NAFG088UN").alias("naf88"),
            pl.col("PUB3FP").alias("employeur"),
            pl.col("STATUTDET").alias("statut_detaille"),
            pl.col("TPPRED").alias("temps_partiel"),
            pl.col("TXTPPRED").alias("taux_partiel"),
            # The year's employment around the survey week, for the months worked
            # (`emploi_discontinu`, étape « ppa » of but 19): the seniority in the job
            # (ANCEMPL4), the time since the last job of anyone out of work (ANCSSEMP),
            # and the class of the current or last job, whose second character tells a
            # fixed-term contract (ACL_EMPLOI).
            # Read as missing from a hand-made survey frame that lacks them: nobody's year
            # is then cut (a tenure of a year or more is the default).
            *(pl.col(code).alias(name) if code in eec.columns
              else pl.lit(None, dtype=pl.String).alias(name)
              for code, name in (("ANCEMPL4", "anciennete_emploi"),
                                 ("ANCSSEMP", "anciennete_sans_emploi"),
                                 ("ACL_EMPLOI", "classe_emploi"))),
        )
        .sort(["household_id", "noi"])
        .with_columns(
            pl.int_range(pl.len()).over(over).alias("rank"),
            (pl.col("couple_flag") == "1").sum().over(over).alias("n_coupled"),
            pl.col("typlog").first().over(over).alias("hh_type"),
            pl.col("so").first().over(over).alias("hh_so"),
            pl.col("metrodom").first().over(over).alias("hh_metrodom"),
            pl.col("stcomm").first().over(over).alias("hh_stcomm"),
        )
    )

    is_reference = pl.col("rank") == 0
    reference_is_coupled = (
        pl.when(is_reference).then(pl.col("couple_flag") == "1").otherwise(None)
        .max().over(over).fill_null(False)
    )
    couple_resolves = (
        pl.col("hh_type").is_in(COUPLE_HOUSEHOLD_TYPES)
        & (pl.col("n_coupled") == 2)
        & reference_is_coupled
    )
    is_conjoint = couple_resolves & ~is_reference & (pl.col("couple_flag") == "1")

    frame = frame.with_columns(
        is_reference.alias("is_reference"),
        is_conjoint.alias("is_conjoint"),
    )
    return frame


def _classify_dependants(people: pl.DataFrame) -> pl.DataFrame:
    """Decide who is a child of the famille, and who is a unit of their own.

    Only in a household the EEC types as containing children, only for someone who
    is neither the reference person nor their partner, and only if they are young
    enough to be rattaché: under 21 unconditionally, or under 25 and out of work,
    which is the nearest thing to "still studying" this file can express.
    """
    rattachable = (pl.col("age") < RATTACHEMENT_AGE) | (
        (pl.col("age") < RATTACHEMENT_MAX_AGE) & (pl.col("statut_activite") != "employed")
    )
    is_child = (
        pl.col("hh_type").is_in(CHILD_HOUSEHOLD_TYPES)
        & ~pl.col("is_reference")
        & ~pl.col("is_conjoint")
        & rattachable
    )
    # Two different notions of "child", deliberately kept apart:
    #
    #   is_child     enfant de la famille, rattachable au foyer fiscal — drives the
    #                famille roles and AF; whether the child is rattaché is drawn
    #                after (`_draw_foyers`), on case 0DJ
    #   insee_child  "enfant d'une famille" in INSEE's sense: anyone under 25 in the
    #                dwelling who is neither the reference person nor their partner
    #
    # The published family-size distribution counts the second. Subtracting only the
    # first from it over-generated under-15s by 20 %, by exactly the employed
    # 21-24-year-olds who still live at home: INSEE counts them as children of the
    # family, the tax code does not rattach them, and the synthesis was quietly
    # inventing a small child for each one.
    insee_child = (
        pl.col("hh_type").is_in(CHILD_HOUSEHOLD_TYPES)
        & ~pl.col("is_reference")
        & ~pl.col("is_conjoint")
        & (pl.col("age") < INSEE_CHILD_MAX_AGE)
    )
    return people.with_columns(
        is_child.alias("is_child"), insee_child.alias("insee_child")
    ).with_columns(
        (~pl.col("is_reference") & ~pl.col("is_conjoint") & ~pl.col("is_child")).alias("is_extra")
    )


def _draw_ages(bands: pl.Series, rng: np.random.Generator) -> np.ndarray:
    """An exact year of age drawn uniformly inside each five-way band.

    Uniform is crude where the band is wide — 25-49 especially — but the one
    threshold that moves tax cleanly, the over-65 abattement, sits on a band edge
    and so stays exact. Inside 15-24 the draw is redone by role
    (`_draw_young_ages_by_role`); this one is kept, and still consumed from the same
    generator, so that every later draw of the skeleton is the one it was.
    """
    codes = bands.to_numpy()
    ages = np.empty(len(codes), dtype=np.int64)
    for code, (low, high) in AGE_BANDS.items():
        mask = codes == code
        count = int(mask.sum())
        if count:
            ages[mask] = rng.integers(low, high + 1, size=count)
    return ages


def child_share_by_age() -> dict[int, float]:
    """The share of each single year of 15-24 living as a child of the family.

    The regional shape of `margins.CHILD_SHARE_SHAPE`, its 18-24 part moved by one shift
    on the logit scale until the ordinary-household population of those ages, spread
    evenly over each five-year band, holds the census's 2,93 M children of the family
    (`margins.CHILDREN_18_24`). 15-17 keep the shape's level.
    """
    population = {
        age: margins.ORDINARY_HOUSEHOLD_POPULATION_15_24[15 if age < 20 else 20] / 5.0
        for age in range(15, 25)
    }
    shape = margins.CHILD_SHARE_SHAPE
    logit = {age: np.log(shape[age] / (1.0 - shape[age])) for age in range(18, 25)}

    def children(shift: float) -> float:
        return sum(population[a] / (1.0 + np.exp(-(logit[a] + shift))) for a in logit)

    low, high = -5.0, 5.0
    for _ in range(200):
        middle = (low + high) / 2.0
        if children(middle) < margins.CHILDREN_18_24.value:
            low = middle
        else:
            high = middle
    shift = (low + high) / 2.0
    shares = {age: shape[age] for age in range(15, 18)}
    shares.update({a: float(1.0 / (1.0 + np.exp(-(logit[a] + shift)))) for a in logit})
    return shares


def _draw_young_ages_by_role(
    ages: np.ndarray, bands: np.ndarray, child_of_family: np.ndarray, seed: int
) -> np.ndarray:
    """Redraw the exact age of the 15-24-year-olds according to their place.

    A 15-24-year-old who lives with his parents is younger, on average, than one who
    heads his own household: the uniform draw handed half the children of the family
    20 years or more, which took them out of the allocations familiales (paid to under-
    20s) and out of the unconditional rattachement (under 21). Here a child of the
    family receives age *a* with a probability proportional to N(a)·s(a), anyone else
    in the band with N(a)·(1 − s(a)): N the census population of each year, s the share
    living as a child (`child_share_by_age`). Its own generator, so that nothing else
    drawn from the skeleton's moves.
    """
    rng = np.random.default_rng([seed, 15])
    shares = child_share_by_age()
    years = np.arange(15, 25)
    population = np.array([
        margins.ORDINARY_HOUSEHOLD_POPULATION_15_24[15 if a < 20 else 20] / 5.0
        for a in years])
    share = np.array([shares[int(a)] for a in years])
    young = bands == "15"
    ages = ages.copy()
    for is_child, weights in ((True, population * share),
                              (False, population * (1.0 - share))):
        mask = young & (child_of_family == is_child)
        count = int(mask.sum())
        if count:
            ages[mask] = rng.choice(years, size=count, p=weights / weights.sum())
    return ages


def _union_libre_probability(age: np.ndarray) -> np.ndarray:
    """The census share of union libre among the persons in a couple, by age."""
    lows = np.array(sorted(margins.UNION_LIBRE_SHARE_BY_AGE))
    values = np.array([margins.UNION_LIBRE_SHARE_BY_AGE[k] for k in lows])
    index = np.clip(np.searchsorted(lows, age, side="right") - 1, 0, lows.size - 1)
    return values[index]


def _draw_foyers(people: pl.DataFrame, seed: int) -> tuple[pl.DataFrame, float]:
    """Who files his own déclaration though he lives in unit 0: two draws.

    **Concubins** (`separate_return` on the conjoint). A couple married or pacsé files
    one déclaration; a couple in union libre files two (art. 6 CGI). The EEC does not
    say which couple is which. Each paired couple is split with the mean of its two
    members' census shares of union libre by age (`margins.UNION_LIBRE_SHARE_BY_AGE`).
    The children stay on the reference person's déclaration. The couple stays one
    famille: the CAF treats any couple as one, and OpenFisca reads both parents'
    foyers when the conjoint is the principal declarant of his own
    (`famille.conjoint.foyer_fiscal`, × `has_role(DECLARANT_PRINCIPAL)`).

    **Majeurs rattachés** (`rattache`). Rattachement is an option (art. 6, 3 CGI), not
    a rule: under 21, or under 25 and studying, a child MAY ask for it. Every minor
    child of the family is rattaché; an eligible adult child (18-20, or 21-24 and not
    in work, the nearest the EEC comes to « studying ») is rattaché with one common
    probability, set so that the weighted rattachés reach case 0DJ
    (`margins.RATTACHES_MAJEURS`), scaled to the frame's share of the country. A child
    who is not rattaché files his own déclaration and stays an enfant of the famille,
    where the CAF's own age and income tests apply.
    """
    rng = np.random.default_rng([seed, 6])
    over = pl.col("household_id")
    partner_age = (
        pl.when(pl.col("is_conjoint")).then(pl.col("age")).otherwise(None).max().over(over)
    )
    reference_age = (
        pl.when(pl.col("is_reference")).then(pl.col("age")).otherwise(None).max().over(over)
    )
    people = people.with_columns(
        partner_age.alias("__partner_age"), reference_age.alias("__reference_age"))
    is_conjoint = people["is_conjoint"].to_numpy()
    p_split = 0.5 * (
        _union_libre_probability(people["__reference_age"].fill_null(0).to_numpy())
        + _union_libre_probability(people["__partner_age"].fill_null(0).to_numpy()))
    separate = is_conjoint & (rng.random(people.height) < p_split)

    # Rattachement: one probability for every eligible adult child of the family.
    from impots.population.incomes import household_share_of_france

    age = people["age"].to_numpy()
    child = people["is_child"].to_numpy()
    employed = (people["statut_activite"] == "employed").to_numpy()
    eligible = child & (age >= 18) & (
        (age < RATTACHEMENT_AGE) | ((age < RATTACHEMENT_MAX_AGE) & ~employed))
    weight = people["weight"].to_numpy().astype(np.float64)
    eligible_weight = float(weight[eligible].sum())
    target = margins.RATTACHES_MAJEURS.value * household_share_of_france(people)
    probability = min(1.0, target / eligible_weight) if eligible_weight > 0 else 0.0
    draw = rng.random(people.height)
    rattache = child & ((age < 18) | (eligible & (draw < probability)))
    return people.drop("__partner_age", "__reference_age").with_columns(
        pl.Series("separate_return", separate),
        pl.Series("rattache", rattache),
    ), probability


def build_skeleton(
    children_per_household: dict[str, np.ndarray] | None = None,
    seed: int = SEED,
    source: pl.DataFrame | None = None,
) -> tuple[pl.DataFrame, SkeletonStats]:
    """Assemble the structural population.

    `children_per_household` maps a household-type code to a probability vector
    over 0, 1, 2, ... additional children under 15; it comes from published
    margins (`margins.py`), never from this module. Passing `None` synthesises no
    children at all, which is only useful for testing the structure in isolation.

    `source` overrides the EEC loader, for tests running on the committed fixture.
    """
    rng = np.random.default_rng(seed)
    observed = _observed_persons(load_eec() if source is None else source)

    stats_missing_noi = (
        observed.group_by("household_id")
        .agg((pl.col("noi") == "01").any().alias("has01"))
        .filter(~pl.col("has01")).height
    )
    stats_no_pair = (
        observed.filter(pl.col("hh_type").is_in(COUPLE_HOUSEHOLD_TYPES))
        .group_by("household_id").agg(pl.col("n_coupled").first())
        .filter(pl.col("n_coupled") != 2).height
    )
    # Ages are drawn before roles are settled, because whether a young adult is a
    # dependant turns on their exact age, not on their band.
    child_of_family = (
        observed["hh_type"].is_in(CHILD_HOUSEHOLD_TYPES)
        & ~observed["is_reference"] & ~observed["is_conjoint"]
    ).to_numpy()
    ages = _draw_young_ages_by_role(
        _draw_ages(observed["age_band"], rng), observed["age_band"].to_numpy(),
        child_of_family, seed)
    people = observed.with_columns(
        pl.Series("age", ages),
        pl.when(pl.col("sexe") == "1").then(pl.lit("male")).otherwise(pl.lit("female")).alias("sex"),
        pl.col("acteu").replace_strict(ACTIVITE, default="inactive").alias("statut_activite"),
        pl.when(pl.col("hh_metrodom") == "1").then(pl.lit("metropole"))
          .otherwise(pl.lit("dom")).alias("region"),
        pl.col("hh_so").replace_strict(STATUT_OCCUPATION, default="locataire_vide")
          .alias("statut_occupation"),
        pl.lit(False).alias("synthetic"),
        # Job characteristics: what the wage synthesis conditions on.
        # STATUT is null for anyone not in employment, so the comparison yields
        # null rather than False. Left unfilled it propagates into every arithmetic
        # downstream, which is how it announced itself.
        (pl.col("statut_emploi") == "2").fill_null(False).alias("is_salarie"),
        pl.col("pcs_code").replace_strict(PCS_GROUP, default=None).alias("pcs"),
        (pl.col("employeur").is_in(["1", "2", "3"])).fill_null(False)
          .alias("secteur_public"),
        # The public employer's side and the agent's status (D-346): a titular civil
        # servant is paid a traitement indiciaire and primes, contributes to the civil
        # pension schemes and gives his employer no allègement. The EEC tells « CDI,
        # fonctionnaire » (STATUTDET 21) from fixed-term and other contracts, not a
        # titular from a contractual on a CDI: those are read as titular.
        pl.col("employeur").replace_strict(FONCTION_PUBLIQUE, default=None)
          .alias("fonction_publique"),
        ((pl.col("employeur").is_in(["1", "2", "3"]))
         & (pl.col("statut_detaille") == "21")).fill_null(False).alias("titulaire"),
        pl.when(pl.col("temps_partiel") == "2")
          .then(pl.col("taux_partiel").replace_strict(PART_TIME_FACTOR,
                                                      default=PART_TIME_DEFAULT))
          .otherwise(1.0).alias("quotite_travail"),
    )
    people = _classify_dependants(people)
    stats_extra = people.filter(pl.col("is_extra")).select("household_id").n_unique()
    people, rattachement_probability = _draw_foyers(people, seed)

    if children_per_household is not None:
        children = _synthesise_children(people, children_per_household, rng)
        people = pl.concat([people, children], how="diagonal_relaxed")
    people = _draw_zone(people, seed)

    people = logement.lodging(_assign_units(people))
    people = people.sort(["household_id", "unit", "role_rank"]).with_columns(
        pl.int_range(pl.len()).alias("person_id")
    )

    stats = SkeletonStats(
        households=people["household_id"].n_unique(),
        persons_observed=int((~people["synthetic"]).sum()),
        children_synthesised=int(people["synthetic"].sum()),
        households_with_extra_adults=stats_extra,
        couple_households_without_a_pair=stats_no_pair,
        households_missing_noi_01=stats_missing_noi,
        rattachement_probability=rattachement_probability,
    )
    return people.select(SKELETON_COLUMNS), stats


def _synthesise_children(
    people: pl.DataFrame, distribution: dict[str, np.ndarray], rng: np.random.Generator
) -> pl.DataFrame:
    """Invent the under-15 children the EEC does not survey.

    A household typed "famille monoparentale" or "couple avec enfant" contains at
    least one dependent child by construction; the EEC shows us only those aged 15
    or over. We draw the number of *additional* under-15 children from published
    margins conditioned on household type, then draw each child's age.

    Everything here is an invention constrained to match a published margin. It is
    the single largest fidelity cost in branch A' and is stated as such wherever
    the numbers are shown.
    """
    households = (
        people.group_by("household_id")
        .agg(
            pl.col("hh_type").first(),
            pl.col("weight").first(),
            pl.col("region").first(),
            pl.col("statut_occupation").first(),
            pl.col("insee_child").sum().alias("visible_children"),
        )
        .filter(pl.col("hh_type").is_in(CHILD_HOUSEHOLD_TYPES))
        .sort("household_id")
    )
    if households.is_empty():
        return people.head(0)

    rows: list[dict[str, object]] = []
    types = households["hh_type"].to_list()
    ids = households["household_id"].to_list()
    weights = households["weight"].to_list()
    regions = households["region"].to_list()
    occupations = households["statut_occupation"].to_list()
    visible = households["visible_children"].to_list()

    for household, hh_type, weight, region, occupation, seen in zip(
        ids, types, weights, regions, occupations, visible, strict=True
    ):
        probabilities = distribution[hh_type]
        total = int(rng.choice(len(probabilities), p=probabilities))
        extra = max(0, total - int(seen))
        for index in range(extra):
            rows.append({
                "household_id": household,
                "noi": f"9{index}",
                "weight": weight,
                "age": int(rng.integers(0, 15)),
                "sex": "male" if rng.random() < 0.512 else "female",
                "statut_activite": "student",
                # A synthesised child carries the same job columns as any other
                # non-worker: the concat is `diagonal_relaxed`, so a column left
                # out here arrives as null and poisons the arithmetic downstream.
                "is_salarie": False,
                "pcs": None,
                "secteur_public": False,
                "fonction_publique": None,
                "titulaire": False,
                "quotite_travail": 1.0,
                "region": region,
                "statut_occupation": occupation,
                "hh_type": hh_type,
                "is_reference": False,
                "is_conjoint": False,
                "is_child": True,
                "is_extra": False,
                "rattache": True,
                "separate_return": False,
                "synthetic": True,
            })
    if not rows:
        return people.head(0)
    children = pl.DataFrame(rows)

    # Head-count check against the published under-15 population. Thinning is a
    # last resort and is capped: removing children one at a time pushes two-child
    # families below the threshold where allocations familiales begin, so a large
    # cull would buy the right head-count at the cost of the AF total. If the gap
    # is wide, that is a finding about the family-size margins, not something to
    # quietly correct away.
    target = margins.CHILDREN_UNDER_15.value * (1.0 + UNATTACHED_CHILD_RESIDUAL)
    drawn = float(children["weight"].sum())
    if drawn > target * (1.0 + MAX_SILENT_CHILD_CORRECTION):
        keep = rng.random(children.height) < (target / drawn)
        children = children.filter(pl.Series(keep))
    return children


def _draw_zone(people: pl.DataFrame, seed: int) -> pl.DataFrame:
    """The APL zone and the DOM département of each ménage (`logement`), on every row.

    Drawn once the synthesised children are in, on the ménage's observed members'
    urban-unit status, region and tenure, from its own stream: no other draw moves.
    """
    households = (
        people.group_by("household_id").agg(
            pl.col("hh_stcomm").drop_nulls().first(),
            pl.col("region").first(),
            pl.col("statut_occupation").first(),
        ).sort("household_id")
    )
    zone, departement = logement.draw_zone_and_departement(
        households["hh_stcomm"].to_numpy(), (households["region"] == "dom").to_numpy(),
        households["statut_occupation"].to_numpy(), seed)
    drawn = households.select("household_id").with_columns(
        pl.Series("zone_apl", zone.tolist(), dtype=pl.String),
        pl.Series("departement", departement.tolist(), dtype=pl.String),
    )
    return people.join(drawn, on="household_id", how="left", maintain_order="left")


def _assign_units(people: pl.DataFrame) -> pl.DataFrame:
    """Split each ménage into tax units and stamp the subrole vocabulary.

    Unit 0 is the reference person, their partner and the dependent children: it is
    the famille. Every other adult is a unit of their own — see the module docstring
    for why this departs from §4.4's "one foyer per ménage".

    The foyer fiscal is unit 0 less those who file their own déclaration inside it
    (`_draw_foyers`): a conjoint in union libre, an adult child not rattaché. Each
    becomes the principal declarant of a foyer numbered by his seat, as an extra adult
    is, and keeps his place in the famille. Without that split a famille and a foyer
    were one identifier, and splitting the foyer would have split the famille the CAF
    pays.
    """
    over = pl.col("household_id")
    people = people.sort(["household_id", "noi"]).with_columns(
        pl.int_range(pl.len()).over(over).alias("seat")
    )
    if "separate_return" not in people.columns:
        people = people.with_columns(pl.lit(False).alias("separate_return"))
    if "rattache" not in people.columns:
        people = people.with_columns(pl.col("is_child").alias("rattache"))
    people = people.with_columns(
        pl.col("separate_return").fill_null(False),
        pl.col("rattache").fill_null(False),
    )
    own_return = (
        (pl.col("is_conjoint") & pl.col("separate_return"))
        | (pl.col("is_child") & ~pl.col("rattache"))
    )
    unit = pl.when(pl.col("is_extra")).then(pl.col("seat") + 1).otherwise(0)
    foyer_unit = pl.when(pl.col("is_extra") | own_return).then(pl.col("seat") + 1).otherwise(0)
    role_rank = (
        pl.when(pl.col("is_reference")).then(0)
        .when(pl.col("is_conjoint")).then(1)
        .otherwise(2)
    )
    menage_role = (
        pl.when(pl.col("is_reference")).then(pl.lit("personne_de_reference"))
        .when(pl.col("is_conjoint")).then(pl.lit("conjoint"))
        .when(pl.col("is_child")).then(pl.lit("enfant"))
        .otherwise(pl.lit("autre"))
    )
    # An extra adult heads their own foyer and famille, so they are a
    # declarant_principal / demandeur there even though the ménage calls them
    # "autre". Conflating the two vocabularies is exactly silent-failure mode #1.
    foyer_role = (
        pl.when(own_return).then(pl.lit("declarant_principal"))
        .when(pl.col("is_conjoint")).then(pl.lit("conjoint"))
        .when(pl.col("is_child")).then(pl.lit("personne_a_charge"))
        .otherwise(pl.lit("declarant_principal"))
    )
    famille_role = (
        pl.when(pl.col("is_conjoint")).then(pl.lit("conjoint"))
        .when(pl.col("is_child")).then(pl.lit("enfant"))
        .otherwise(pl.lit("demandeur"))
    )
    people = people.with_columns(
        unit.alias("unit"),
        role_rank.alias("role_rank"),
        menage_role.alias("role_menage"),
        foyer_role.alias("role_foyer"),
        famille_role.alias("role_famille"),
    ).with_columns(
        pl.concat_str([over, pl.lit("#"), foyer_unit.cast(pl.String)]).alias("foyer_id"),
        pl.concat_str([over, pl.lit("#"), pl.col("unit").cast(pl.String)]).alias("famille_id"),
    )
    # Case T, art. 194, II CGI: « contribuables célibataires ou divorcés qui vivent
    # seuls », with at least one dependant. The engine's D-006 rule, derived per foyer
    # because that is the entity OpenFisca reads it on, and with one thing the survey
    # tells the skeleton that the household form does not ask (D-195):
    #
    #   one declarant    over BOTH declarant roles. A foyer with a `conjoint` is a
    #                    married or PACSed couple, which the article does not reach.
    #   not in a couple  `COUPL_LOG`, « en couple avec quelqu'un vivant dans le
    #                    logement », in a dwelling `TYPLOG5` says holds a couple: the
    #                    two signals that pair a partner (D-013), both saying so.
    #                    Living in a couple, married or not, is not living alone (CE,
    #                    15 avril 2016, n° 375682). This is the declarant whose partner
    #                    could not be paired — absent from the file, or one of more than
    #                    two coupled persons. Where the dwelling is typed « famille
    #                    monoparentale », the signals disagree, and case T is left as it
    #                    was: the owner's call. Sharing the dwelling is not a couple.
    declarant = pl.col("role_foyer").is_in(["declarant_principal", "conjoint"])
    in_a_couple = (
        declarant
        & (pl.col("couple_flag") == "1")
        & pl.col("hh_type").is_in(COUPLE_HOUSEHOLD_TYPES)
    ).fill_null(False)
    return people.with_columns(
        (
            declarant.sum().over("foyer_id").eq(1)
            & (pl.col("role_foyer") == "personne_a_charge").sum().over("foyer_id").gt(0)
            & ~in_a_couple.any().over("foyer_id")
        ).alias("parent_isole")
    )


SKELETON_COLUMNS = [
    "person_id", "household_id", "foyer_id", "famille_id", "weight",
    "age", "sex", "region",
    "role_menage", "role_foyer", "role_famille",
    "statut_activite", "statut_occupation", "zone_apl", "departement",
    "aide_logement_heberge", "colocation",
    "is_salarie", "pcs", "secteur_public", "fonction_publique", "titulaire",
    "quotite_travail", "naf88",
    "statut_detaille", "anciennete_emploi", "anciennete_sans_emploi", "classe_emploi",
    "parent_isole", "synthetic",
]
