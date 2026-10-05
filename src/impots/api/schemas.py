"""The wire format — single source of truth (spec §4).

Deliberately free of any FastAPI import: `impots.engine` imports these models, and
the engine must stay usable without a web framework (Phase 1 runs it over a
population, not over HTTP).

Sign convention (spec §3.3): every monetary field in a response is a **positive
magnitude**; the direction is carried by the field name. `ir` is tax paid,
`cotisations_salariales` is contributions withheld. Only `delta` is signed, and a
positive delta means "more of that thing under the reform" — so `delta.ir = +200`
reads as "pays 200 EUR more tax".
"""

from __future__ import annotations

from itertools import pairwise
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from impots.entreprises.reforms import FirmReformSpec

# Year window Phase 0 will answer for. The golden values are 2024; the engine
# holds law well outside this range, but nothing here has been checked against it.
MIN_YEAR = 2022
MAX_YEAR = 2026
MIN_BIRTH_YEAR = 1920
MAX_SALARY = 10_000_000.0
MAX_CHILDREN = 8
# v1 replaces the active brackets of the IR scale in place; it never adds brackets
# to the ParameterScale (spec §3.4).
MAX_BAREME_BRACKETS = 5
MIN_BAREME_BRACKETS = 2


# --------------------------------------------------------------------------- #
# Request: the household
# --------------------------------------------------------------------------- #
#: Every model a request body reaches. `allow_inf_nan=False` because `Infinity` is
#: JSON to Python's parser and `ge=0` is true of it: an infinite threshold reached
#: the engine (D-173). `test_every_model_the_api_accepts_refuses_non_finite_numbers`
#: derives the list from the routes, so a new input model cannot forget it.
INPUT_CONFIG = ConfigDict(extra="forbid", allow_inf_nan=False)


#: The rate from which the restriction on access to employment opens the AAH. Pinned here
#: because a validator must not need a tax-benefit system;
#: `test_the_aah_rsdae_rate_matches_the_tree` keeps it honest.
AAH_TAUX_RSDAE = 0.5


class Handicap(BaseModel):
    """A disability the CDAPH recognised, as the AAH reads it (D-184).

    Only what opens the AAH: the rate, and for a rate between 50 and 79 % the restriction
    on access to employment. openfisca's generic `handicap` flag is NOT set from it. That
    flag would exempt an AAH recipient's housing aid from the high-rent taper, as the law
    does, but it would also open the ASI beside a retirement pension, where openfisca then
    pays the AAH and the ASI above the AAH amount (D-184).
    """

    model_config = INPUT_CONFIG

    taux_incapacite: Annotated[float, Field(ge=0, le=1)] = Field(
        description="Permanent incapacity rate recognised by the CDAPH, as a fraction: 0.8 "
        "for 80 %. From 80 % it opens the AAH (CSS art. L. 821-1); from 50 %, only with "
        "the restriction below (art. L. 821-2). Written onto `taux_incapacite` on every "
        "covered month, like the salary.",
    )
    restriction_substantielle_durable_acces_emploi: bool = Field(
        default=False,
        description="The substantial and lasting restriction on access to employment "
        "(RSDAE) the CDAPH recognises for a rate between 50 and 79 %.",
    )

    @model_validator(mode="after")
    def _check_restriction(self) -> Handicap:
        if (self.restriction_substantielle_durable_acces_emploi
                and self.taux_incapacite < AAH_TAUX_RSDAE):
            raise ValueError(
                f"La restriction substantielle et durable d'accès à l'emploi n'ouvre l'AAH "
                f"qu'à partir de {AAH_TAUX_RSDAE:.0%} d'incapacité ; à "
                f"{self.taux_incapacite:.0%}, le moteur l'ignorerait sans rien dire."
            )
        return self


class Adult(BaseModel):
    model_config = INPUT_CONFIG

    salaire_brut_annuel: Annotated[float, Field(ge=0, le=MAX_SALARY)] = Field(
        description="Gross annual salary in EUR. Divided by 12 onto the monthly "
        "`salaire_de_base` input the engine expects."
    )
    annee_naissance: Annotated[int, Field(ge=MIN_BIRTH_YEAR, le=MAX_YEAR)]
    pension_annuelle: Annotated[float, Field(ge=0, le=MAX_SALARY)] = Field(
        default=0.0,
        description="Annual retirement pension in EUR, AS DECLARED (the taxable amount, "
        "box 1AS), written monthly onto `retraite_imposable` and onto `retraite_brute` "
        "exactly as the population build writes its `pension_annuelle`, which is "
        "calibrated on declared pensions. The amount typed is taxed as typed whatever is "
        "computed first; disposable income takes off it the CSG imposable, the CRDS and "
        "the CASA, at the rate the RFR of N-2 sets, and not the deductible CSG, which a "
        "declared amount is already net of (D-176). Without this field no pensioner "
        "could be expressed, and a knob that bites only on pensions could not be watched "
        "moving on any household (D-081, PLF 2027 art. 3).",
    )
    chomage_brut_annuel: Annotated[float, Field(ge=0, le=MAX_SALARY)] = Field(
        default=0.0,
        description="Annual unemployment benefit in EUR, GROSS: before its CSG and CRDS, "
        "so not the taxable amount of box 1AP, which is net of the deductible CSG. Written "
        "monthly onto `chomage_brut`, on the same years as the salary, exactly as the "
        "population build writes its `chomage_annuel`, which is the Unédic spend and gross "
        "too. What is due on it is computed: CSG and CRDS on 98.25 % of it, at the rate the "
        "RFR of N-2 sets and only down to the monthly gross SMIC, and the income tax on the "
        "amount net of the deductible CSG. Those levies have no row of their own, since the "
        "CSG and CRDS rows are the salary's: they are inside `revenu_disponible` (D-183).",
    )
    pension_invalidite_annuelle: Annotated[float, Field(ge=0, le=MAX_SALARY)] = Field(
        default=0.0,
        description="Annual invalidity pension of the social security in EUR, AS DECLARED: "
        "the taxable amount of box 1AZ, already net of the deductible CSG, like "
        "`pension_annuelle`, and without the majoration pour tierce personne, which bears "
        "neither tax nor levy. Written monthly onto openfisca's `pensions_invalidite`, which "
        "is that box and has no gross counterpart, on the same years as the salary. Taxed "
        "with the pensions, after their 10 % abatement; disposable income takes off it the "
        "CSG imposable, the CRDS and the CASA, at the rate the RFR of N-2 sets, as off a "
        "declared retirement pension (`engine.corrections`, correction 9). Below the ASPA's "
        "age it opens the allocation supplémentaire d'invalidité, the ceiling less the "
        "resources (CSS art. L. 815-24-1), capped for the lone beneficiary of a couple "
        "(art. D. 815-19, 2° b, correction 10). Beside a spouse at the ASPA's age it is half "
        "the couple's ceiling less half the couple's resources, and the spouse's ASPA the "
        "other half of its own (art. D. 815-19, 2° c, and D. 815-1; corrections 13 and 14, "
        "D-194). At 62 the pension gives way to a retirement pension "
        "and its holder, réputé inapte au travail, may claim the ASPA, which ends the ASI: "
        "typed past 62, it prices as that retirement pension would (D-190).",
    )
    handicap: Handicap | None = Field(
        default=None,
        description="A disability the CDAPH recognised. Absent means none. At 80 % the "
        "AAH goes on past 62, topping a pension up to the AAH amount, and its holder is "
        "taken not to claim the ASPA (D-185).",
    )
    carte_invalidite: bool = Field(
        default=False,
        description="Holds the carte « mobilité inclusion » marked « invalidité » (CASF "
        "art. L. 241-3), or the carte d'invalidité it replaced. Written as case P of the "
        "2042 for the first adult and case F for the second, on every covered year: half a "
        "part more (CGI art. 195, 1 d bis, 3, 4 and 5), the abatement of art. 157 bis under "
        "its income ceilings, and that abatement off the resources of the housing aid and "
        "the family benefits, which read N-2. A separate application from the CDAPH rate: "
        "the mention also goes to a third-category invalidity pensioner and, for good, to "
        "an APA recipient in groups 1 or 2, so no rate is required beside it, and none "
        "implies it (D-188).",
    )
    fin_de_droits_ass: bool = Field(
        default=False,
        description="A job seeker whose unemployment insurance rights are exhausted and who "
        "meets the ASS's work condition: five years of salaried work in the ten before the "
        "end of the contract that opened those rights (C. trav. art. L. 5423-1 and "
        "R. 5423-1). Written onto `ass_precondition_remplie` and a job seeker's `activite` "
        "on every covered month; the resources test is the engine's. Refused beside a "
        "salary, since the ASS is cumulated with one for three months only (art. "
        "R. 5425-2), beside unemployment benefit, never paid for the same months, and from "
        "the year of the 62nd birthday, from which the ASS turns on the insurance duration "
        "(art. L. 5421-4) (D-189). The ASS is taxed as a salary, after the 10 % deduction "
        "it shares with the claimant's other salaries, so it enters the RFR, and bears no CSG "
        "and no CRDS (art. L. 5428-1; `engine.corrections`, correction 12, D-192).",
    )

    @model_validator(mode="after")
    def _check_fin_de_droits(self) -> Adult:
        """Refuse the incomes the ASS is never paid beside, rather than price them wrong."""
        if not self.fin_de_droits_ass:
            return self
        if self.salaire_brut_annuel:
            raise ValueError(
                "L'ASS ne se cumule avec un salaire que pendant trois mois, consécutifs ou "
                "non (C. trav. art. R. 5425-2) ; au-delà, son versement est interrompu tant "
                "que l'activité se poursuit. Le salaire est écrit sur chaque mois de trois "
                "années, et le moteur verserait l'ASS d'un demandeur d'emploi à côté, sans "
                "fin. Saisissez un salaire nul, ou décochez la fin de droits."
            )
        if self.chomage_brut_annuel:
            raise ValueError(
                "L'ASS suit l'épuisement des droits à l'allocation chômage (C. trav. art. "
                "L. 5423-1), ou la remplace sur option à partir de 50 ans (art. L. 5423-2) : "
                "les deux ne sont jamais versées pour les mêmes mois. L'allocation chômage "
                "est écrite sur chaque mois de trois années, et le moteur ne verserait alors "
                "aucune ASS, sans rien dire."
            )
        return self


#: The rates of CSS art. R. 541-1: from 80 % a child opens the AEEH; from 50 %, only where
#: it attends an establishment or needs a « dispositif adapté ou d'accompagnement » or care
#: the CDAPH recommends (art. L. 541-1, third alinéa). And the rate from which the carte
#: « mobilité inclusion » carries the mention « invalidité » (CASF art. L. 241-3), which
#: gives the child's half-part (CGI art. 195, 2). None is in openfisca's tree, whose AEEH
#: reads only its `handicap` flag: they are the law's, quoted in D-191.
AEEH_TAUX = 0.8
AEEH_TAUX_MINIMUM = 0.5
CARTE_INVALIDITE_TAUX = 0.8
#: The age from which a child opens no AEEH: the family benefits run « jusqu'à l'âge de
#: vingt ans » (CSS art. R. 512-2). Pinned because a refusal must not wait for a
#: simulation; `test_the_aeeh_age_limit_matches_the_tree` keeps it honest.
AEEH_AGE_MAXIMUM = 20
#: The AEEH's complément categories (CSS art. R. 541-2 and D. 541-2).
AEEH_CATEGORIES = 6


def _pour_cent(rate: float) -> str:
    """A rate as French writes it: 0.8 -> « 80 % », 0.795 -> « 79,5 % », never rounded up
    to the threshold it misses."""
    return f"{rate * 100:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " %"


class HandicapEnfant(BaseModel):
    """A child's disability as the CDAPH recognised it: what the AEEH and the income tax
    read (D-191).

    The rate decides what the builder writes, and is not written itself. openfisca's AEEH
    reads its generic `handicap` flag, which the builder writes where the AEEH is open,
    with the complément's category; its half-part reads `invalidite`, which the builder
    writes for the card. On a child the flag is what the law asks: it opens the AEEH, and it lifts
    the housing aid's high-rent taper, which CCH art. D. 823-16 lifts for « le demandeur
    ou son conjoint [...] bénéficiaire [...] de l'allocation d'éducation de l'enfant
    handicapé ». It opens no ASI, which needs a pension. A child of 20 or more is refused,
    since there is no AEEH from that age and the flag would still lift the taper.
    """

    model_config = INPUT_CONFIG

    taux_incapacite: Annotated[float, Field(ge=0, le=1)] = Field(
        description="Permanent incapacity rate recognised by the CDAPH, as a fraction: 0.8 "
        "for 80 %. From 80 % it opens the AEEH (CSS art. L. 541-1, R. 541-1); from 50 %, "
        "only with the establishment, support or care below. Not written into the "
        "situation: it decides what is.",
    )
    etablissement_accompagnement_ou_soins: bool = Field(
        default=False,
        description="Between 50 and 79 %: the child attends an establishment of CASF art. "
        "L. 312-1, I, 2° or 12°, or its state requires a « dispositif adapté ou "
        "d'accompagnement » (code de l'éducation, art. L. 351-1) or care the CDAPH "
        "recommends (CSS art. L. 541-1, third alinéa).",
    )
    complement_categorie: Annotated[int, Field(ge=1, le=AEEH_CATEGORIES)] | None = Field(
        default=None,
        description="The category, 1 to 6, of the AEEH complément the CDAPH granted (CSS "
        "art. R. 541-2), paid at its own rate of the BMAF (art. D. 541-2). From the second, "
        "a parent alone also receives the majoration of art. L. 541-4, which D. 541-3 "
        "reserves to a complément granted for the parent's activity or a paid third "
        "person: always so in the fifth and sixth categories, assumed so in the second to "
        "the fourth (D-191). Only where the AEEH is open.",
    )
    carte_invalidite: bool = Field(
        default=False,
        description="The child holds the carte « mobilité inclusion » with the mention "
        "« invalidité », granted from 80 % (CASF art. L. 241-3): half a part more on the "
        "quotient familial (CGI art. 195, 2).",
    )

    @property
    def ouvre_aeeh(self) -> bool:
        """Whether the rate, and below 80 % the establishment, support or care, open the
        AEEH (CSS art. L. 541-1, R. 541-1). The age is the builder's to check."""
        return self.taux_incapacite >= AEEH_TAUX or (
            self.taux_incapacite >= AEEH_TAUX_MINIMUM
            and self.etablissement_accompagnement_ou_soins)

    @model_validator(mode="after")
    def _check_thresholds(self) -> HandicapEnfant:
        if (self.etablissement_accompagnement_ou_soins
                and self.taux_incapacite < AEEH_TAUX_MINIMUM):
            raise ValueError(
                f"L'établissement, l'accompagnement ou les soins n'ouvrent l'AEEH qu'à partir "
                f"de {_pour_cent(AEEH_TAUX_MINIMUM)} d'incapacité ; à "
                f"{_pour_cent(self.taux_incapacite)}, le moteur l'ignorerait sans rien dire."
            )
        if self.complement_categorie is not None and not self.ouvre_aeeh:
            raise ValueError(
                f"Un complément de l'AEEH suppose l'AEEH : un taux d'au moins "
                f"{_pour_cent(AEEH_TAUX)}, ou d'au moins {_pour_cent(AEEH_TAUX_MINIMUM)} avec "
                f"un établissement, un accompagnement ou des soins ; à "
                f"{_pour_cent(self.taux_incapacite)}, il n'y a rien à compléter."
            )
        if self.carte_invalidite and self.taux_incapacite < CARTE_INVALIDITE_TAUX:
            raise ValueError(
                f"La carte mobilité inclusion « invalidité » suppose un taux d'au moins "
                f"{_pour_cent(CARTE_INVALIDITE_TAUX)} (CASF art. L. 241-3) ; à "
                f"{_pour_cent(self.taux_incapacite)}, la demi-part ne serait pas due."
            )
        return self


class Child(BaseModel):
    model_config = INPUT_CONFIG

    annee_naissance: Annotated[int, Field(ge=MIN_BIRTH_YEAR, le=MAX_YEAR)]
    handicap: HandicapEnfant | None = Field(
        default=None,
        description="A disability the CDAPH recognised. Absent means none. Opens the AEEH "
        "up to the age of 20, and with the card half a part more (D-191). Refused for a "
        "child of 20 or more in the year simulated.",
    )


class Logement(BaseModel):
    """Optional ménage-level housing inputs. Without them `aide_logement` is 0 —
    that is the engine answering the question as asked, not a wiring bug (spec §7.9)."""

    model_config = INPUT_CONFIG

    statut: str = Field(
        description="`statut_occupation_logement` enum member name, e.g. 'locataire_vide'. "
        "Only the locataire_* statuts can ever produce a housing aid."
    )
    loyer_mensuel: Annotated[float, Field(ge=0, le=100_000)] = 0.0
    # Not optional, and not defaulted silently: leaving `zone_apl` unset does not
    # mean "no zone", it means zone 2. Stating it keeps a substantive assumption
    # visible. Zone 0 ("non renseigné") exists in the engine's enum and crashes the
    # housing cascade, hence the 1..3 bound.
    zone_apl: Annotated[int, Field(ge=1, le=3)] = 2


class Niches(BaseModel):
    """Bases for the réductions and crédits d'impôt (B3).

    Without them every niche is zero, which is why the population's income tax is a
    BARÈME figure and is validated against the barème line (98.84 bn) rather than
    against net receipts: the 19.53 bn of réductions and crédits nationally is money
    the model had no way to express.

    **Amounts are for the simulated year only, not spread across the income history.**
    The three-year history exists to give means-tested benefits a realistic reference
    period; asserting three identical years of charitable giving would be a different
    claim, and one nobody made.

    Every rate below was verified by computation rather than read off a rate table:
    5 000 € of home help returns a 2 500 € credit, 1 000 € of donations 660 € or 750 €
    depending on the class, 200 € of union dues 132 €.
    """

    model_config = INPUT_CONFIG

    salarie_domicile: Annotated[float, Field(ge=0, le=100_000)] = 0.0
    """Sommes versées pour l'emploi d'un salarié à domicile (case 7DB). A CRÉDIT at
    50 %, so it reaches households with no tax to reduce — which is why it is the
    largest niche and why it cannot be imputed to taxpayers alone."""
    salarie_domicile_aides_percues: Annotated[float, Field(ge=0, le=100_000)] = 0.0
    """Aides perçues for that employment — APA, PCH, CESU préfinancé (case 7DR). They
    reduce the eligible base, so omitting them overstates the credit."""
    dons_oeuvres: Annotated[float, Field(ge=0, le=1_000_000)] = 0.0
    """Dons to organismes d'intérêt général (case 7UF) — 66 %."""
    dons_aide_personnes_en_difficulte: Annotated[float, Field(ge=0, le=1_000_000)] = 0.0
    """Dons to organismes d'aide aux personnes en difficulté (case 7UD) — 75 %. A
    separate case because the rate and the ceiling both differ."""
    frais_garde_par_enfant: Annotated[list[float], Field(max_length=3)] = Field(
        default_factory=list)
    """Frais de garde, PER CHILD under six (cases 7GA, 7GB, 7GC in order).

    A list rather than a total because the ceiling applies per child: splitting one
    total equally would give a different — and generally larger — credit than an
    uneven real split whenever the ceiling binds.

    **THE ENGINE APPLIES NO ELIGIBILITY TEST**, and an earlier version of this
    docstring said it did. Measured: a household with a fifteen-year-old gets the
    credit, and so does a household with NO CHILDREN AT ALL. These cases are
    declaration boxes and openfisca trusts the declarant, exactly as the paper form
    does — eligibility is the administration's job, not the formula's. So the wire
    format checks it instead: `situations.assert_niche_eligibility` refuses more
    childcare amounts than there are children young enough to have them."""
    cotisations_syndicales: Annotated[list[float], Field(max_length=2)] = Field(
        default_factory=list)
    """Union dues, PER ADULT in order (case 7AC). Individual-level, unlike every other
    niche here, because the entitlement follows the member and not the foyer. Checked
    against the number of adults for the same reason as the childcare list."""
    enfants_college: Annotated[int, Field(ge=0, le=MAX_CHILDREN)] = 0
    enfants_lycee: Annotated[int, Field(ge=0, le=MAX_CHILDREN)] = 0
    enfants_superieur: Annotated[int, Field(ge=0, le=MAX_CHILDREN)] = 0
    """Counts of children in education (cases 7EA, 7EC, 7EF) — flat amounts per child,
    not a rate on a base: 61 €, 153 € and 183 € respectively as computed. Their sum is
    checked against the household's dependants, since the engine will otherwise grant a
    school-fees reduction to a childless foyer."""

    @property
    def declared_school_children(self) -> int:
        return self.enfants_college + self.enfants_lycee + self.enfants_superieur


#: Niche field -> the déclaration case it writes. One source of truth, so the wire
#: format, the situation builder and the tests cannot disagree about which box a field
#: lands in. Every case was enumerated out of the live variable registry, not from a
#: form: `f7d*` alone also contains five PME-subscription boxes and an invalidity flag,
#: and picking a plausible-looking name would have been picking the wrong one.
NICHE_CASES: dict[str, str] = {
    "salarie_domicile": "f7db",
    "salarie_domicile_aides_percues": "f7dr",
    "dons_oeuvres": "f7uf",
    "dons_aide_personnes_en_difficulte": "f7ud",
    "enfants_college": "f7ea",
    "enfants_lycee": "f7ec",
    "enfants_superieur": "f7ef",
}
#: The per-child childcare cases, in the order the list fills them.
NICHE_GARDE_CASES: tuple[str, ...] = ("f7ga", "f7gb", "f7gc")
#: Individual-level, so it is written onto the adults rather than the foyer fiscal.
NICHE_SYNDICALES_CASE = "f7ac"


class Patrimoine(BaseModel):
    """A 2042-IFI-shaped wealth declaration, in euros.

    Field names are the form's language; the codes they map to are in
    `impots.patrimoine.ifi.CASES`, which is the single place the mapping lives.

    Note what is NOT here: any financial wealth. The IFI base is real estate only
    (CGI art. 965), so there is nowhere to declare shares, deposits or life insurance —
    and that absence is the correct model of the tax rather than a gap in the form.
    """

    model_config = INPUT_CONFIG

    residence_principale: Annotated[float, Field(ge=0, le=1e9)] = 0.0
    """Gross value. The 30 % abattement is the engine's to apply, not the caller's."""
    autres_immeubles_batis: Annotated[float, Field(ge=0, le=1e10)] = 0.0
    bois_et_forets: Annotated[float, Field(ge=0, le=1e10)] = 0.0
    biens_ruraux_loues_long_terme: Annotated[float, Field(ge=0, le=1e10)] = 0.0
    parts_groupements_forestiers_agricoles: Annotated[float, Field(ge=0, le=1e10)] = 0.0
    autres_biens_non_batis: Annotated[float, Field(ge=0, le=1e10)] = 0.0
    meubles_meublants_declares: Annotated[float, Field(ge=0, le=1e9)] = 0.0
    passif_deductible: Annotated[float, Field(ge=0, le=1e10)] = 0.0
    dons_organismes_interet_general: Annotated[float, Field(ge=0, le=1e8)] = 0.0

    # --- ISF only ---------------------------------------------------------------------
    # Financial wealth. The IFI base excludes it entirely (CGI art. 965), so under
    # current law these are declared and IGNORED — the engine reads them at 2017 and
    # drops them silently at 2024. They matter only under an ISF revival, which is why
    # `patrimoine.regimes` exists. Declaring them without the revival is not an error and
    # not a no-op to hide: `RegimeNote` on the result says they were dropped.
    droits_sociaux_non_exoneres: Annotated[float, Field(ge=0, le=1e10)] = 0.0
    valeurs_mobilieres: Annotated[float, Field(ge=0, le=1e10)] = 0.0
    liquidites: Annotated[float, Field(ge=0, le=1e10)] = 0.0
    droits_sociaux_conserves_six_ans: Annotated[float, Field(ge=0, le=1e10)] = 0.0


class HouseholdInput(BaseModel):
    model_config = INPUT_CONFIG

    adults: Annotated[list[Adult], Field(min_length=1, max_length=2)]
    children: Annotated[list[Child], Field(max_length=MAX_CHILDREN)] = Field(default_factory=list)
    couple_marie_ou_pacse: bool = False
    parent_isole: bool | None = Field(
        default=None,
        description="Case T — parent isolé. Worth half a fiscal part. Left unset it is "
        "inferred: true for a lone adult with at least one dependent child, which is "
        "what a one-adult household with children describes, false otherwise. Set it "
        "explicitly to false for a lone filer who does not in fact live alone.",
    )
    logement: Logement | None = None
    niches: Niches | None = None
    """Réductions and crédits d'impôt bases. Absent means every niche is zero, which
    is the engine answering as asked and not a wiring gap."""
    patrimoine: Patrimoine | None = None
    """IFI declaration. Absent means no real estate wealth, hence no IFI.

    A warning that costs nothing to give: IFI is abated entirely by the plafonnement
    when the foyer has no income, so a wealth declaration with zero salary prices zero.
    That is the law working, not the model failing."""

    def resolved_parent_isole(self) -> bool:
        """Whether to claim case T for this household."""
        lone_parent = len(self.adults) == 1 and bool(self.children)
        return lone_parent if self.parent_isole is None else self.parent_isole

    @model_validator(mode="after")
    def _check_couple(self) -> HouseholdInput:
        if len(self.adults) == 2 and not self.couple_marie_ou_pacse:
            raise ValueError(
                "Phase 0 modélise un adulte seul ou un couple marié/pacsé. Le concubinage "
                "(deux foyers fiscaux distincts) n'est pas encore supporté : mettez "
                "couple_marie_ou_pacse=true, ou simulez chaque adulte séparément."
            )
        if len(self.adults) == 1 and self.couple_marie_ou_pacse:
            raise ValueError(
                "couple_marie_ou_pacse=true demande deux adultes ; un seul a été fourni."
            )
        if self.parent_isole and (len(self.adults) != 1 or not self.children):
            raise ValueError(
                "parent_isole=true suppose un adulte seul avec au moins un enfant à charge."
            )
        claimants = [adult for adult in self.adults if adult.fin_de_droits_ass]
        if len(claimants) == 2 and any(adult.pension_annuelle for adult in self.adults):
            raise ValueError(
                "Deux adultes en fin de droits, à côté d'une pension : les ressources de "
                "chacun comprennent l'ASS de l'autre (C. trav. art. R. 5423-2), ce que le "
                "moteur ne fait pas. Sans autre ressource, les deux allocations restent "
                "pleines sous le plafond du couple, et le calcul est exact."
            )
        return self


# --------------------------------------------------------------------------- #
# Request: the reform
# --------------------------------------------------------------------------- #
class IRBracket(BaseModel):
    model_config = INPUT_CONFIG

    threshold: Annotated[float, Field(ge=0)]
    rate: Annotated[float, Field(ge=0.0, le=1.0)]


#: The 2024 legal values of the two AF modulation ceilings, needed only so that a
#: reform moving ONE of them can be checked against the other's baseline. Pinned here
#: rather than read from the tree because a validator must not need a tax-benefit
#: system: `test_af_plafond_baselines_match_the_tree` keeps them honest.
#: Active brackets in the IFI scale at 2024: 800 k, 1,3 M, 2,57 M, 5 M, 10 M.
IFI_BAREME_BRACKETS = 5

AF_PLAFOND_TRANCHE_1_BASE_2024 = 62_474.0
AF_PLAFOND_TRANCHE_2_BASE_2024 = 87_430.0


#: The IFI décote as it stands at 2024-01-01, so a one-sided knob move is judged
#: against the real other side rather than against nothing. Read from the tree by
#: `test_the_ifi_decote_constants_match_the_tree`, not trusted here.
IFI_DECOTE_PARAMETRE_2024 = 17_500.0
IFI_DECOTE_TAUX_2024 = 0.0125
IFI_DECOTE_BORNE_INF_2024 = 1_300_000.0
IFI_DECOTE_BORNE_SUP_2024 = 1_400_000.0


class ReformSpec(BaseModel):
    """A whitelist of named knobs, never raw parameter paths.

    Raw paths would be an injection surface into the parameter tree and would make
    the reform-cache key unbounded (spec §3.4).
    """

    model_config = INPUT_CONFIG

    ir_bareme: list[IRBracket] | None = Field(
        default=None,
        description="Complete replacement of the active IR scale: 2 to 5 brackets, "
        "first threshold 0, thresholds strictly increasing.",
    )
    decote_seuil_celib: Annotated[float, Field(ge=0, le=100_000)] | None = None
    decote_seuil_couple: Annotated[float, Field(ge=0, le=100_000)] | None = None
    decote_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    plafond_qf_demi_part: Annotated[float, Field(ge=0, le=100_000)] | None = None
    # The cap on the 10 % pension abatement, per foyer (CGI 158, 5, a). PLF 2027 art. 3
    # adds a 3 000 EUR sub-cap for RETIREMENT pensions only and keeps the common cap for
    # alimony and invalidity pensions. This knob moves the common cap, which is exact for
    # every foyer this tool can express: the only pension it carries is a retirement one.
    abattement_pensions_plafond: Annotated[float, Field(ge=0, le=100_000)] | None = None
    csg_activite_imposable: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    csg_activite_deductible: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    # Employer social contributions (D-038). Plafonds are in multiples of the SMIC,
    # which is why their ceiling is 10 and not 1: 1.6 is today's réduction générale.
    allegement_general_plafond: Annotated[float, Field(ge=0.0, le=10.0)] | None = None
    allegement_general_taux_50_et_plus: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    allegement_general_taux_moins_de_50: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    bandeau_maladie_plafond: Annotated[float, Field(ge=0.0, le=10.0)] | None = None
    bandeau_maladie_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    bandeau_famille_plafond: Annotated[float, Field(ge=0.0, le=10.0)] | None = None
    bandeau_famille_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    # Prestations (B1) — the spending side of the debate. Monthly amounts in euros,
    # rates as fractions, income ceilings in euros per year. The upper bounds are
    # deliberately generous: this tool exists to price proposals, including ones
    # nobody has made, and a bound tight enough to be "realistic" would be a
    # political judgement wearing a validation's clothes.
    rsa_montant_de_base: Annotated[float, Field(ge=0, le=5_000)] | None = None
    rsa_forfait_logement_1_personne: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    rsa_forfait_logement_2_personnes: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    rsa_forfait_logement_3_personnes_ou_plus: Annotated[
        float, Field(ge=0.0, le=1.0)] | None = None
    """The forfait logement, as a share of the RSA base, stepped by household size
    (12 %, 16 %, 16.5 %). It is DEDUCTED, so raising it lowers the benefit — the one
    knob in this family whose sign runs the other way."""
    ppa_montant_de_base: Annotated[float, Field(ge=0, le=5_000)] | None = None
    ppa_pente: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    """The share of activity income added back before the taper — 61 % today. The
    single parameter that most directly sets the marginal rate a working household on
    the prime d'activité faces."""
    ppa_bonification_taux_max: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    bmaf: Annotated[float, Field(ge=0, le=5_000)] | None = None
    """The base every family benefit is a multiple of. Broad: it moves AF, CF, ASF and
    the rest together, not one of them."""
    af_taux_2_enfants: Annotated[float, Field(ge=0.0, le=5.0)] | None = None
    af_taux_3_enfants: Annotated[float, Field(ge=0.0, le=5.0)] | None = None
    af_modulation_taux_tranche_2: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    af_modulation_taux_tranche_3: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    """Setting both modulation tranches to 1 restores universal family allowances,
    which is a live proposal and is now one knob."""
    af_plafond_tranche_1_base: Annotated[float, Field(ge=0, le=1_000_000)] | None = None
    af_plafond_tranche_2_base: Annotated[float, Field(ge=0, le=1_000_000)] | None = None
    af_majoration_plafond_par_enfant: Annotated[float, Field(ge=0, le=100_000)] | None = None
    """The modulation ceilings the formula actually reads. It builds its own threshold
    from the `_base` value plus one majoration per child; the published
    `plafond_tranche_1` / `plafond_tranche_2` are derived figures no formula consults,
    and a knob aimed at them would move nothing."""
    al_minoration_forfaitaire: Annotated[float, Field(ge=0, le=1_000)] | None = None

    # --- IFI (Phase 5) ---------------------------------------------------------------
    # Bounds are wide on purpose: this is a policy simulator and an IFI reform may
    # legitimately move a threshold a long way. What is NOT allowed is a combination
    # that turns the décote into a surcharge — see `_check_ifi_decote`.
    ifi_decote_parametre: Annotated[float, Field(ge=0, le=1_000_000)] | None = None
    ifi_decote_taux: Annotated[float, Field(ge=0, le=1)] | None = None
    ifi_decote_borne_inferieure: Annotated[float, Field(ge=0, le=50_000_000)] | None = None
    ifi_decote_borne_superieure: Annotated[float, Field(ge=0, le=50_000_000)] | None = None
    ifi_plafonnement_taux: Annotated[float, Field(ge=0, le=5)] | None = None
    ifi_abattement_residence_principale: Annotated[float, Field(ge=0, le=1)] | None = None
    ifi_dons_taux: Annotated[float, Field(ge=0, le=1)] | None = None
    ifi_dons_plafond: Annotated[float, Field(ge=0, le=10_000_000)] | None = None
    ifi_forfait_mobilier: Annotated[float, Field(ge=0, le=1)] | None = None
    ifi_plafond_reductions: Annotated[float, Field(ge=0, le=10_000_000)] | None = None
    ifi_non_bati_seuil: Annotated[float, Field(ge=0, le=10_000_000)] | None = None
    ifi_non_bati_taux_bois_forets: Annotated[float, Field(ge=0, le=1)] | None = None
    ifi_obligations_declaratives: Literal["allegees", "renforcees"] | None = Field(
        default=None,
        description="Régime déclaratif de l'IFI. LE SEUL LEVIER DE CE SIMULATEUR QUI NE "
        "TOUCHE AUCUN PARAMÈTRE : les obligations déclaratives ne sont pas dans le code "
        "des impôts sous forme de paramètre, donc ce cadran ne change RIEN au calcul "
        "mécanique et n'agit que sur la bande comportementale (canal C6). C'est voulu et "
        "c'est la raison d'être du module : la même étude qui ne détecte aucune réponse "
        "aux coudes de taux trouve des réponses DIX FOIS plus grandes aux obligations "
        "déclaratives. Un simulateur de fortune avec un cadran de taux et sans cadran "
        "d'application mettrait le petit levier dans la main de l'utilisateur en cachant "
        "le grand.",
    )
    ifi_bareme: list[IRBracket] | None = Field(
        default=None,
        description="Complete replacement of the active IFI scale: 1 to 5 brackets, "
        "thresholds strictly increasing. UNLIKE the IR scale the first threshold is NOT "
        "0 — the IFI's exempt band below 800 000 EUR is the ABSENCE of a bracket, not a "
        "zero-rated one, and a scale starting at 0 taxes from the first euro.",
    )
    """The 2017 flat cut to housing benefit — five euros a month."""
    # IR niches (B3). Rates as fractions, ceilings in euros except
    # `dons_plafond_part_rfr`, which is a SHARE of the revenu fiscal de référence, and
    # `plafond_global_niches`, which caps the lot.
    saldom_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    saldom_plafond: Annotated[float, Field(ge=0, le=200_000)] | None = None
    gardenf_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    gardenf_plafond: Annotated[float, Field(ge=0, le=100_000)] | None = None
    """Per CHILD, not per household — 3 500 EUR today, and the ceiling that makes an
    uneven split of the same total worth more than an even one."""
    dons_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    dons_plafond_part_rfr: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    """A share of the revenu fiscal de référence — 20 % today, not a euro amount."""
    dons_coluche_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    dons_coluche_plafond: Annotated[float, Field(ge=0, le=100_000)] | None = None
    """The 75 % rate for donations to organisations helping people in difficulty, and
    the euro ceiling above which the ordinary 66 % takes over."""
    cotisations_syndicales_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    frais_scolarite_college: Annotated[float, Field(ge=0, le=10_000)] | None = None
    frais_scolarite_lycee: Annotated[float, Field(ge=0, le=10_000)] | None = None
    frais_scolarite_superieur: Annotated[float, Field(ge=0, le=10_000)] | None = None
    """Flat amounts per child — 61, 153 and 183 EUR — not rates on a base."""
    plafond_global_niches: Annotated[float, Field(ge=0, le=1_000_000)] | None = None
    """The global cap on réductions and crédits, 10 000 EUR. It bites only on a
    household claiming more than that, so a chiffrage of it says nothing about anyone
    else."""

    @model_validator(mode="after")
    def _check_bareme(self) -> ReformSpec:
        if self.ir_bareme is None:
            return self
        n = len(self.ir_bareme)
        if n < MIN_BAREME_BRACKETS:
            raise ValueError(f"Le barème doit compter au moins {MIN_BAREME_BRACKETS} tranches.")
        if n > MAX_BAREME_BRACKETS:
            raise ValueError(
                f"Le barème est limité à {MAX_BAREME_BRACKETS} tranches en v1 : les tranches "
                "actives du barème légal sont remplacées sur place, aucune tranche n'est ajoutée "
                "au ParameterScale."
            )
        if self.ir_bareme[0].threshold != 0:
            raise ValueError(
                "La première tranche doit commencer à 0 € : un barème marginal doit couvrir "
                "l'ensemble des revenus."
            )
        thresholds = [b.threshold for b in self.ir_bareme]
        if any(a >= b for a, b in pairwise(thresholds)):
            raise ValueError(f"Les seuils doivent être strictement croissants ; reçu {thresholds}.")
        return self

    @model_validator(mode="after")
    def _check_ifi_bareme(self) -> ReformSpec:
        """Strictly increasing thresholds, and the reason is not tidiness.

        openfisca MERGES brackets that share a threshold, by SUMMING their rates.
        Measured on the IFI scale: writing bracket 0's threshold to 1 300 000 turns five
        brackets into four and the head rate into 0,012 — the sum of 0,005 and 0,007 —
        so the 1,3-2,57 M band silently doubles. Nothing raises. The engine's own
        surplus-bracket trick relies on that merge (with a rate of ZERO, where summing
        is harmless), which is exactly why a user-supplied scale must never reach it
        with a live rate.

        The first threshold is deliberately NOT forced to 0, unlike the IR scale: the
        IFI exempts everything below 800 000 by having no bracket there.
        """
        if self.ifi_bareme is None:
            return self
        count = len(self.ifi_bareme)
        if not 1 <= count <= IFI_BAREME_BRACKETS:
            raise ValueError(
                f"Le barème de l'IFI compte {IFI_BAREME_BRACKETS} tranches actives ; "
                f"{count} fournies. Les tranches sont remplacées sur place, aucune n'est "
                f"ajoutée."
            )
        thresholds = [bracket.threshold for bracket in self.ifi_bareme]
        if any(a >= b for a, b in pairwise(thresholds)):
            raise ValueError(
                f"Les seuils du barème de l'IFI doivent être strictement croissants ; "
                f"reçu {thresholds}. Deux tranches au même seuil sont FUSIONNÉES par "
                f"le moteur et leurs taux ADDITIONNÉS, sans erreur : le barème obtenu "
                f"ne serait pas celui demandé."
            )
        return self

    @model_validator(mode="after")
    def _check_ifi_decote(self) -> ReformSpec:
        """The décote must stay a relief, and its window must stay ordered.

        `decote_isf_ifi` is `parametre - taux x assiette` with **no floor at zero**, and
        `isf_ifi_avant_reduction` subtracts it. So a décote driven negative does not
        vanish — it is subtracted as a negative and RAISES the tax. Measured: on an
        assiette of 1 350 000 EUR, moving `taux_decote` from 0,0125 to 0,02 makes the
        décote -9 500 EUR and the tax 2 225 -> 12 350 EUR. A relief that becomes a
        surcharge is not a reform anyone means to express, and nothing downstream
        refuses it.

        The check is at the window's UPPER bound. `parametre - taux x assiette` FALLS as
        the assiette rises, so the décote is smallest at the top of the window and that
        is the only end where it can go negative. The first version of this validator
        checked the lower bound and passed a reform that produced a -2 500 EUR décote —
        caught by `test_each_knob_moves_its_output`, which saw the tax rise where it
        should have fallen. In force the window is exactly calibrated so the décote
        reaches zero at 1,4 M, so ANY widening of the upper bound without a matching
        rise in the parameter goes negative.

        Values default to the ones in force so a one-sided move is judged against the
        real other side (the D-062 rule).
        """
        parametre = (self.ifi_decote_parametre
                     if self.ifi_decote_parametre is not None
                     else IFI_DECOTE_PARAMETRE_2024)
        taux = self.ifi_decote_taux if self.ifi_decote_taux is not None else IFI_DECOTE_TAUX_2024
        lower = (self.ifi_decote_borne_inferieure
                 if self.ifi_decote_borne_inferieure is not None
                 else IFI_DECOTE_BORNE_INF_2024)
        upper = (self.ifi_decote_borne_superieure
                 if self.ifi_decote_borne_superieure is not None
                 else IFI_DECOTE_BORNE_SUP_2024)

        if {self.ifi_decote_borne_inferieure, self.ifi_decote_borne_superieure} != {None} \
                and lower >= upper:
            raise ValueError(
                f"La fenêtre de décote de l'IFI serait vide ou inversée : borne "
                f"inférieure {lower:,.0f} EUR contre borne supérieure {upper:,.0f} EUR. "
                f"Aucun foyer n'y entrerait."
            )
        touched = {self.ifi_decote_parametre, self.ifi_decote_taux,
                   self.ifi_decote_borne_superieure}
        if touched != {None}:
            at_upper = parametre - taux * upper
            if at_upper < 0:
                raise ValueError(
                    f"Cette décote d'IFI serait NÉGATIVE et augmenterait l'impôt : au "
                    f"sommet de la fenêtre ({upper:,.0f} EUR) elle vaut "
                    f"{at_upper:,.0f} EUR. La formule ne la borne pas à zéro, si bien "
                    f"qu'un allègement négatif est retranché comme tel et alourdit "
                    f"l'impôt. Relever le paramètre, baisser le taux, ou resserrer la "
                    f"borne supérieure."
                )
        return self

    @model_validator(mode="after")
    def _check_af_plafonds(self) -> ReformSpec:
        """The two modulation ceilings must stay ordered.

        Inverting them is not caught anywhere downstream: the AF formula branches on
        `above tranche 1` then `above tranche 2`, so a tranche-1 ceiling above the
        tranche-2 one produces a household that is in neither band and receives an
        amount belonging to neither rate. Measured, not theorised — lifting only the
        first ceiling gave a 150 k household 2 214 EUR where full rate is 1 771.

        The unset ceiling keeps its legal value, so a reform moving one must be checked
        against the other's baseline, not against nothing.
        """
        low, high = self.af_plafond_tranche_1_base, self.af_plafond_tranche_2_base
        if low is None and high is None:
            return self
        effective_low = low if low is not None else AF_PLAFOND_TRANCHE_1_BASE_2024
        effective_high = high if high is not None else AF_PLAFOND_TRANCHE_2_BASE_2024
        if effective_low > effective_high:
            raise ValueError(
                f"Le plafond de tranche 1 ({effective_low:,.0f} €) doit rester "
                f"inférieur ou égal à celui de tranche 2 ({effective_high:,.0f} €) : "
                f"au-dessus, un foyer n'est dans aucune des deux tranches et perçoit "
                f"un montant qui ne correspond à aucun taux."
                .replace(",", " ")
            )
        return self

    def is_empty(self) -> bool:
        """True when no knob is set — treated as 'no reform' rather than as an
        identity reform, so we never pay 0.5 s to clone the parameter tree for nothing."""
        return not self.model_dump(exclude_none=True)


# --------------------------------------------------------------------------- #
# Request envelope
# --------------------------------------------------------------------------- #
Tier = Literal["light", "full"]


class SimulateRequest(BaseModel):
    model_config = INPUT_CONFIG

    household: HouseholdInput
    year: Annotated[int, Field(ge=MIN_YEAR, le=MAX_YEAR)] = 2024
    reform: ReformSpec | None = None
    tier: Tier = "light"
    emtr: bool = False
    historique_revenus: bool = Field(
        default=True,
        description="Replicate the salary and housing across the two preceding years so "
        "that means-tested benefits are assessed against a real reference period rather "
        "than an empty one. On by default since D-011; set false only to reproduce the "
        "Phase 0 single-year wiring — see docs/DECISIONS.md D-005 and D-011.",
    )
    debug: bool = False

    @model_validator(mode="after")
    def _check_envelope(self) -> SimulateRequest:
        if self.emtr and self.tier == "light":
            raise ValueError(
                "emtr=true exige tier='full' : le taux marginal effectif est calculé par "
                "différence finie sur le revenu disponible, ce qui demande la cascade complète "
                "des prestations."
            )
        born_late = [
            a.annee_naissance for a in self.household.adults if a.annee_naissance > self.year
        ] + [c.annee_naissance for c in self.household.children if c.annee_naissance > self.year]
        if born_late:
            raise ValueError(
                f"Année de naissance postérieure à l'année simulée ({self.year}) : {born_late}."
            )
        return self


# --------------------------------------------------------------------------- #
# Response
# --------------------------------------------------------------------------- #
class ResultRows(BaseModel):
    """One column of the results table. All amounts are annual EUR, positive
    magnitudes, summed across household members where the variable is individual.

    The famille/ménage rows are `None` in a `light` response — they were not
    computed, which is not the same as being zero."""

    model_config = ConfigDict(extra="forbid")

    # salary block (individu, summed over members)
    salaire_brut: float
    salaire_super_brut: float
    salaire_net: float
    salaire_imposable: float
    cotisations_salariales: float
    cotisations_employeur: float
    retraite_imposable: float
    chomage_brut: float
    pension_invalidite: float
    """The invalidity pension as declared, box 1AZ. Zero for a household that declares none.
    Its CSG imposable, CRDS and CASA have no row, like a retirement pension's: they are inside
    `revenu_disponible` (D-190)."""
    allegement_general: float
    allegement_bandeau_maladie: float
    allegement_bandeau_famille: float
    """The employer-contribution reductions. Reported separately because
    `cotisations_employeur` is GROSS of them: without these rows a reform to the
    allègements moved nothing a reader could see."""
    csg_deductible: float
    csg_imposable: float
    crds: float
    # tax block (foyer fiscal)
    ir: float
    ir_avant_reductions: float
    parts_fiscales: float
    revenu_fiscal_reference: float
    ir_avant_niches: float
    """After the décote, before réductions and crédits — the quantity the published
    barème figure measures."""
    reductions: float
    credits_impot: float
    """Réductions and crédits d'impôt. Zero for a household that declares no base,
    which is every household in the synthetic population — the 19.53 bn of niches
    nationally is why the population's IR is validated against the barème line and not
    against net receipts."""
    # benefits block (famille) — full tier only
    af: float | None = None
    aeeh: float | None = None
    """The allocation d'éducation de l'enfant handicapé, with its compléments and the lone
    parent's majoration, for the famille. Zero for a household that declares no child's
    disability (D-191)."""
    ppa: float | None = None
    rsa: float | None = None
    ass: float | None = None
    """The allocation de solidarité spécifique, summed over the adults who draw it. Zero
    unless an adult is declared `fin_de_droits_ass` (D-189)."""
    aide_logement: float | None = None
    aah: float | None = None
    mva: float | None = None
    """The AAH, and the majoration pour la vie autonome that rides on it. Zero for a
    household that declares no disability (D-184)."""
    aspa: float | None = None
    """The allocation de solidarité aux personnes âgées, for the famille (D-186)."""
    asi: float | None = None
    """The allocation supplémentaire d'invalidité, on the individual who receives it. Zero
    for a household that declares no invalidity pension (D-190)."""
    aefa: float | None = None
    cf: float | None = None
    asf: float | None = None
    ifi: float | None = None
    """Impôt sur la fortune immobilière, POSITIVE. Zero for all but ~186 000 foyers
    nationally, and zero for any foyer with no income whatever its wealth — the
    plafonnement caps IFI plus income tax at 75 % of income (D-079)."""
    """The prime de Noël. It rides on RSA eligibility rather than being reformed
    directly, which is how it went unitemised until the double-entry guard found it."""
    crds_pfam: float | None = None
    crds_logement: float | None = None
    crds_mini: float | None = None
    """CRDS levied on the benefits above — NEGATIVE, as the engine stores it, because a
    benefit's net value is `gross + crds`. Shown rather than folded in so a reader can
    see that the reported benefit is gross and the disposable income is not."""
    # bottom line (ménage) — full tier only
    revenu_disponible: float | None = None
    # unnormalised engine output, debug requests only
    raw: dict[str, float] | None = None


class Timings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    build_ms: float
    compute_ms: float
    emtr_ms: float | None = None
    total_ms: float
    reform_cache_hit: bool | None = None


class SimulateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline: ResultRows
    reform: ResultRows | None = None
    delta: ResultRows | None = None
    emtr: float | None = None
    emtr_reform: float | None = None
    tier: Tier
    year: int
    historique_revenus: bool
    timings: Timings
    engine: dict[str, str]


# --------------------------------------------------------------------------- #
# GET /parameters/ir
# --------------------------------------------------------------------------- #
class DecoteParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seuil_celib: float
    seuil_couple: float
    taux: float


class CsgActiviteParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    imposable: float
    deductible: float


class IRParameters(BaseModel):
    """Current law, read live from the parameter tree — never hardcoded (spec §4)."""

    model_config = ConfigDict(extra="forbid")

    year: int
    bareme: list[IRBracket]
    decote: DecoteParameters
    plafond_qf_demi_part: float
    csg_activite: CsgActiviteParameters


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    openfisca_france: str
    openfisca_core: str
    warm: bool
    licence: str = "AGPL-3.0-or-later"
    source_url: str | None = Field(
        default=None,
        description="Where this running version's Corresponding Source can be obtained. "
        "AGPL section 13 requires offering it to anyone interacting with the software "
        "over a network; set IMPOTS_SOURCE_URL before deploying. None means the "
        "server has not been told, which is only acceptable when it is not reachable "
        "by anyone else.",
    )


# --------------------------------------------------------------------------- #
# Population (L1) — PHASE1_SPEC §6
#
# Only the quick tier is reachable over HTTP. A full-tier run over 199 451
# households is minutes, not seconds, and belongs to the CLI (§1.1).
# --------------------------------------------------------------------------- #
PopulationTier = Literal["quick"]

#: Households in a quick-tier subsample. Deterministic, PPS, self-weighting.
QUICK_TIER_HOUSEHOLDS = 20_000


class EmtrDecile(BaseModel):
    """One decile of the marginal-rate distribution — deciles of EMTR, not of income.

    Worth its own table rather than a footnote: France's marginal-rate distribution
    has a long right tail created by benefit tapers overlapping income tax, and the
    households in that tail are poor, not rich.
    """

    model_config = ConfigDict(extra="forbid")

    decile: int
    households: float
    emtr_median: float
    emtr_mean: float


class NarrowBandFlag(BaseModel):
    """Whether a reform's yield rests on a narrow wage band (D-046)."""

    model_config = ConfigDict(extra="forbid")

    share: float
    flagged: bool
    window: float
    share_threshold: float
    thresholds: list[float] = Field(default_factory=list)
    caveat: str = ""


class BehaviouralBand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p10: float
    p50: float
    p90: float
    unit: str = "EUR"


class BehaviouralChannel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    applies: bool
    central: float | None = None
    band: BehaviouralBand | None = None
    """The channel's own band, in its own unit. C4 reports a percentage change in
    investment, which is why a channel carries a band separately from the revenue one
    it may or may not belong in."""
    unit: str = "EUR"
    message: str = ""
    grade: str | None = None
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class Behavioural(BaseModel):
    """The band around a mechanical figure (L3).

    `mechanical` is repeated here on purpose: a client reading this block must be
    able to see that the band is a range *around* the mechanical number and never a
    replacement for it.
    """

    model_config = ConfigDict(extra="forbid")

    mechanical: float
    band: BehaviouralBand | None = None
    grade: str
    grade_reason: str = ""
    channels: list[BehaviouralChannel] = Field(default_factory=list)
    seed: int
    draws: int
    parameters_vintage: str = ""
    notes: list[str] = Field(default_factory=list)
    emtr_households: int | None = None
    """How many households the marginal rates were computed on, when a channel needed
    them. Stated because it is a subsample and the band inherits its noise."""


# --------------------------------------------------------------------------- #
# Macro (Phase 4, L4) — PHASE4_SPEC §4
#
# The fan never renders without its strip, so the strip is REQUIRED on this block
# rather than optional: a client cannot receive quantiles without also receiving the
# cycle state, the design, the leakage, the horizon, the vintage and the grade.
# --------------------------------------------------------------------------- #
class MacroQuantiles(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p10: float
    p50: float
    p90: float
    unit: str


class MacroDecomposition(BaseModel):
    """Where the spread comes from, reported separately (§1)."""

    model_config = ConfigDict(extra="forbid")

    horizon: str
    parameter: float
    scenario: float
    scenario_available: bool
    scenario_unavailable_because: str = ""


class MacroBranch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    label: str
    output_share: float
    employment_share: float


class MacroAssumptions(BaseModel):
    """Everything §4 forbids the fan to render without."""

    model_config = ConfigDict(extra="forbid")

    cycle_state: str
    design: str
    leakage: float | None = None
    leakage_applied: bool
    horizons: list[str]
    parameters_vintage: str
    grade: str
    covered_share: float
    instruments: list[str]
    simulation_conditions: str
    caveats: list[str] = Field(default_factory=list)
    banner: str


class Macro(BaseModel):
    """The macro fan (L4).

    `unavailable` is not an error state. Most reforms this repository can express have
    no macro path at all — transfers and corporate instruments have no published
    multiplier — and saying so with a reason is the designed outcome, not a failure.
    """

    model_config = ConfigDict(extra="forbid")

    available: bool
    unavailable_because: str = ""
    gdp: dict[str, MacroQuantiles] = Field(default_factory=dict)
    jobs: dict[str, MacroQuantiles] = Field(default_factory=dict)
    decomposition: list[MacroDecomposition] = Field(default_factory=list)
    composition: list[MacroBranch] = Field(default_factory=list)
    assumptions: MacroAssumptions | None = None
    notes: list[str] = Field(default_factory=list)
    uncovered: dict[str, str] = Field(default_factory=dict)
    """Instruments the reform moved that have no multiplier, with the reason each is
    missing. Carried so the client can show what the fan does NOT describe."""


class NicheBlindSpot(BaseModel):
    """A reform moved a niche this population cannot answer for (B3).

    Present rather than absent is the whole point: without it the response would carry
    a confident zero, and a confident zero here reads as "this credit does nothing"
    when it means "this population declares no such spending".
    """

    model_config = ConfigDict(extra="forbid")

    knobs: list[str]
    declared_base_eur: float
    """Réductions plus crédits across the population. Zero is the whole problem."""
    national_niches_eur: float = 19.53e9
    """What the omission is worth nationally, for scale — DGFiP, against a barème
    yield of 98.84 bn."""
    message: str


class PopulationSimulateRequest(BaseModel):
    model_config = INPUT_CONFIG

    reform: ReformSpec
    year: Annotated[int, Field(ge=MIN_YEAR, le=MAX_YEAR)] = 2024
    tier: PopulationTier = "quick"
    behavioural: bool = False
    """Opt-in, because the marginal rates a behavioural band needs are two more
    full-tier runs. Off by default so the mechanical answer stays fast, and the
    response says how many households the rates were computed on when it is on."""
    macro: bool = False
    """Opt-in, and cheap — the fan is a thousand draws over a parsed table. Off by
    default because most reforms have no macro path and a block saying so on every
    response would be noise."""
    impute_niches: bool = False
    """Hand out réduction and crédit bases from the published DGFiP decile table, so a
    niche reform costs something. Opt-in and OFF BY DEFAULT because it is a
    CALIBRATION: the niche totals then match DGFiP by construction, and the net-yield
    reconciliation line stops being independent evidence for that component. It also
    costs an extra baseline pass, since the deciles are of a quantity the first pass
    has to compute."""

    @model_validator(mode="after")
    def _check_reform(self) -> PopulationSimulateRequest:
        if self.reform.is_empty():
            raise ValueError(
                "Une réforme est requise : sans réforme, /population/baseline sert "
                "les agrégats de référence déjà calculés, sans refaire tourner le moteur."
            )
        return self


class DecileRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decile: int
    n_households: float
    mean_niveau_de_vie: float
    mean_baseline: float
    mean_reform: float | None = None
    mean_delta: float | None = None
    share_winners: float | None = None
    share_losers: float | None = None
    share_unaffected: float | None = None


class ReconciliationLine(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    simulated: float | None
    published: float
    residual: float | None
    use: str
    status: str
    source: str


class PopulationMeta(BaseModel):
    """Which population produced the numbers on screen, and how far it can be trusted."""

    model_config = ConfigDict(extra="forbid")

    vintage: str
    branch: str
    households: float
    persons: float
    tier: str
    sampled_households: int | None
    note: str
    limitations: list[str]


class PopulationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: PopulationMeta
    totals: dict[str, float]
    totals_reform: dict[str, float] = Field(default_factory=dict)
    deltas: dict[str, float] = Field(default_factory=dict)
    reform_cost: float | None = None
    deciles: list[DecileRow] = Field(default_factory=list)
    emtr_deciles: list[EmtrDecile] = Field(default_factory=list)
    narrow_band: NarrowBandFlag | None = None
    reconciliation: list[ReconciliationLine] = Field(default_factory=list)
    behavioural: Behavioural | None = None
    macro: Macro | None = None
    niche_blind_spot: NicheBlindSpot | None = None
    timings: dict[str, float] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Firms (Phase 2) — PHASE2_SPEC §4
#
# Synchronous: the whole IS population prices in well under a second, so there is
# no quick tier and no batch machinery on this side.
# --------------------------------------------------------------------------- #
class FirmSimulateRequest(BaseModel):
    model_config = INPUT_CONFIG

    reform: FirmReformSpec
    year: Annotated[int, Field(ge=2022, le=MAX_YEAR + 4)] = 2026

    @model_validator(mode="after")
    def _check_reform(self) -> FirmSimulateRequest:
        if self.reform.is_empty():
            raise ValueError(
                "Une réforme est requise : sans réforme, /entreprises/baseline sert "
                "les agrégats de référence sans refaire tourner le moteur."
            )
        return self


class FirmCell(BaseModel):
    """One sector x size cell of the incidence table."""

    model_config = ConfigDict(extra="forbid")

    naf_section: str
    taille: str
    n_firms: float
    turnover: float
    tax_baseline: float
    is_brut: float
    mean_effective_rate: float
    tax_reform: float | None = None
    mean_delta: float | None = None
    delta_effective_rate: float | None = None
    share_affected: float | None = None


class FirmSizeRow(BaseModel):
    """The effective-rate profile — the firm analogue of the interdecile ratio."""

    model_config = ConfigDict(extra="forbid")

    taille: str
    n_firms: float
    mean_effective_rate: float
    median_effective_rate: float
    share_zero_tax: float


class FirmMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vintage: str
    year: int
    cells_are_synthetic: bool
    n_firms: float
    turnover: float
    share_zero_is: float
    note: str
    limitations: list[str]


class FirmResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meta: FirmMeta
    totals: dict[str, float]
    totals_reform: dict[str, float] = Field(default_factory=dict)
    deltas: dict[str, float] = Field(default_factory=dict)
    reform_cost: float | None = None
    cells: list[FirmCell] = Field(default_factory=list)
    by_size: list[FirmSizeRow] = Field(default_factory=list)
    behavioural: Behavioural | None = None
    timings: dict[str, float] = Field(default_factory=dict)


class ScenarioSummary(BaseModel):
    """One registered scenario, as the UI's scenario picker needs it.

    READ ONLY, and there is no write counterpart on purpose. Registering a scenario is
    what dates it, and a date the HTTP surface can produce is a date anyone can produce:
    pre-registration lives in the CLI, where it lands in the working tree and gets
    committed. See D-092.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    year: int
    created: str
    source: str
    note: str = ""
    tags: list[str] = Field(default_factory=list)
    knobs: list[str] = Field(default_factory=list)


class ScenarioDetail(ScenarioSummary):
    """A scenario with its reform, so the UI can load it into the knob panel."""

    reform: ReformSpec


class ScenarioListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenarios: list[ScenarioSummary] = Field(default_factory=list)
    unreadable: dict[str, str] = Field(default_factory=dict)
    """Names that no longer validate, with the reason. Listed rather than hidden: a
    scenario that silently vanishes from the picker is a chiffrage that silently stops
    being confrontable."""


class TrajectoryYear(BaseModel):
    """One year of a trajectory, with its uncertainty classes kept apart (F3 M5)."""

    model_config = ConfigDict(extra="forbid")

    year: int
    basis: str
    mechanical_eur: float
    uprating_frozen_eur: float
    uprating_aged_eur: float
    behavioural_low_eur: float | None = None
    behavioural_high_eur: float | None = None
    behavioural_grade: str = ""
    fan_shown: bool = False
    fan_note: str = ""


class TrajectoryResponse(BaseModel):
    """A precomputed trajectory. Read from a file; never runs the engine.

    A trajectory is N population runs — one per year, twice over for the frozen/aged
    pair — so it is a batch job and lives in the CLI, like every other population run.
    """

    model_config = ConfigDict(extra="forbid")

    scenario: str
    titre: str
    source: str
    reference: str
    computed: str
    banner: str
    uprating_note: str = ""
    years: list[TrajectoryYear] = Field(default_factory=list)


class TrajectoryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trajectoires: list[str] = Field(default_factory=list)


class EmtrCurvePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    salaire_brut_annuel: float
    emtr: float
    emtr_reform: float | None = None


class EmtrCurveResponse(BaseModel):
    """A precomputed EMTR sweep (F6). Read from a file; never runs the engine.

    Four full-tier runs per curve, so it is a batch job like every other full-tier run.
    """

    model_config = ConfigDict(extra="forbid")

    household_type: str
    label: str
    year: int
    computed: str
    step_eur: float
    reform: dict[str, Any] | None = None
    points: list[EmtrCurvePoint] = Field(default_factory=list)
    peak_eur: float
    peak_emtr: float
    cliffs_eur: list[float] = Field(default_factory=list)
    crossings_eur: list[float] = Field(default_factory=list)


class EmtrCurveListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    courbes: list[str] = Field(default_factory=list)
