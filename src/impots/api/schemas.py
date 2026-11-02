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

import math
from itertools import pairwise
from typing import Annotated, Any, Literal, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from impots.entreprises.reforms import FirmReformSpec
from impots.predictif.transformations import TRANSFORMATIONS

# Year window Phase 0 will answer for. The golden values are 2024; the engine
# holds law well outside this range, but nothing here has been checked against it.
MIN_YEAR = 2022
MAX_YEAR = 2026
MIN_BIRTH_YEAR = 1920
MAX_SALARY = 10_000_000.0
MAX_CHILDREN = 8
# The active brackets of the IR scale are replaced in place. One more may be asked for:
# it wakes the first dormant bracket the ParameterScale already carries (the 1990s scale
# had thirteen), so nothing is added to the tree (spec §3.4, D-320). The IFI keeps five.
MAX_BAREME_BRACKETS = 6
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
#: The rate from which the AAH is open without that restriction: « au moins 80 % » (CSS art.
#: D. 821-1). The builder reads it on a child of 20 or more, who draws the AAH in a famille of
#: their own (D-202); `test_the_aah_rate_matches_the_tree` keeps it honest.
AAH_TAUX = 0.8


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
        "implies it (D-188). Beside declared home help it also ticks case 7DG: the home-help "
        "credit's ceiling of 20 000 EUR, without increments (CGI art. 199 sexdecies, 3; "
        "BOI-IR-RICI-150-20, § 180; D-196).",
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
    """A child's disability as the CDAPH recognised it: what the AEEH, the AAH and the income
    tax read (D-191, D-202).

    Under 20, the rate decides what the builder writes, and is not written itself. openfisca's
    AEEH reads its generic `handicap` flag, which the builder writes where the AEEH is open,
    with the complément's category; its half-part reads `invalidite`, which the builder
    writes for the card. On a child the flag is what the law asks: it opens the AEEH, and it lifts
    the housing aid's high-rent taper, which CCH art. D. 823-16 lifts for « le demandeur
    ou son conjoint [...] bénéficiaire [...] de l'allocation d'éducation de l'enfant
    handicapé ». It opens no ASI, which needs a pension.

    From 20 there is no AEEH (CSS art. R. 512-2): its complément and its establishment are
    refused. The child stays a dependant, « infirmes » at any age (CGI art. 196), and from 80 %
    draws the AAH (CSS art. L. 821-1, D. 821-1) in a famille of their own, where the flag lifts
    no parent's taper. The builder checks the age, which is the year's (D-202).
    """

    model_config = INPUT_CONFIG

    taux_incapacite: Annotated[float, Field(ge=0, le=1)] = Field(
        description="Permanent incapacity rate recognised by the CDAPH, as a fraction: 0.8 "
        "for 80 %. Under 20, from 80 % it opens the AEEH (CSS art. L. 541-1, R. 541-1); from "
        "50 %, only with the establishment, support or care below; not written into the "
        "situation, it decides what is. From 20, the family benefits having stopped (art. "
        "R. 512-2), from 80 % it opens the child's own AAH (art. L. 821-1, D. 821-1), against "
        "the child's own resources (art. L. 821-3): written onto `taux_incapacite` on every "
        "covered month, and the child draws it in a famille of their own, at no one's charge "
        "for the parents' RSA (CASF art. R. 262-3) or prime d'activité; without a MVA, which "
        "asks an independent dwelling (CSS art. L. 821-1-2). Under 80 % nothing, since the "
        "restriction of art. L. 821-2 is not carried for a child. Beside a rented dwelling, "
        "the AAH-drawing child is refused: a descendant at 80 % is a dependant of the parents' "
        "housing aid (CCH art. R. 823-4, 3°), which the engine cannot price beside a famille "
        "of the child's own (D-202).",
    )
    etablissement_accompagnement_ou_soins: bool = Field(
        default=False,
        description="Between 50 and 79 %: the child attends an establishment of CASF art. "
        "L. 312-1, I, 2° or 12°, or its state requires a « dispositif adapté ou "
        "d'accompagnement » (code de l'éducation, art. L. 351-1) or care the CDAPH "
        "recommends (CSS art. L. 541-1, third alinéa). The AEEH's: refused from 20 (D-202).",
    )
    complement_categorie: Annotated[int, Field(ge=1, le=AEEH_CATEGORIES)] | None = Field(
        default=None,
        description="The category, 1 to 6, of the AEEH complément the CDAPH granted (CSS "
        "art. R. 541-2), paid at its own rate of the BMAF (art. D. 541-2). From the second, "
        "a parent alone also receives the majoration of art. L. 541-4, which D. 541-3 "
        "reserves to a complément granted for the parent's activity or a paid third "
        "person: always so in the fifth and sixth categories, assumed so in the second to "
        "the fourth (D-191). Only where the AEEH is open, so refused from 20 (D-202). Whatever "
        "its category, beside declared home help it ticks case 7DG, the home-help credit's "
        "ceiling of 20 000 EUR (CGI art. 199 sexdecies, 3; D-196).",
    )
    carte_invalidite: bool = Field(
        default=False,
        description="The child holds the carte « mobilité inclusion » with the mention "
        "« invalidité », granted from 80 % (CASF art. L. 241-3): half a part more on the "
        "quotient familial (CGI art. 195, 2), at any age, the infirm child being a dependant "
        "« quel que soit leur âge » (BOI-IR-LIQ-10-10-10-20, § 500; D-202), and beside "
        "declared home help case 7DG, the home-help credit's ceiling of 20 000 EUR (D-196).",
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


#: The age from which a child is no minor on 1 January of the year simulated, as openfisca's
#: `majeur` reads it on births of 1 January: CGI art. 194, I presumes « les enfants mineurs » at
#: equal charge in alternating residence (D-201).
ALTERNANCE_AGE_MAXIMUM = 18


class Child(BaseModel):
    model_config = INPUT_CONFIG

    annee_naissance: Annotated[int, Field(ge=MIN_BIRTH_YEAR, le=MAX_YEAR)]
    handicap: HandicapEnfant | None = Field(
        default=None,
        description="A disability the CDAPH recognised. Absent means none. Opens the AEEH "
        "up to the age of 20, and with the card half a part more (D-191). From 20 in the year "
        "simulated, the child is an infirm dependant at any age (CGI art. 196), with the "
        "card's half-part, and from 80 % draws the AAH in a famille of their own; the AEEH's "
        "complément and establishment are refused, and so is a rented dwelling beside a child "
        "who draws the AAH (D-202).",
    )
    residence_alternee: bool = Field(
        default=False,
        description="The child lives in alternating residence at each parent's home (C. civ. "
        "art. 373-2-9), « réputés être à la charge égale de l'un et de l'autre parent » (CGI art. "
        "194, I): case H of the 2042, written on openfisca's `garde_alternee` on every covered "
        "month. A quarter part for each of the first two such children, half a part from the "
        "third, and less beside children at charge (art. 194, I, a to c); case T a quarter for one "
        "and half a part from two when every child is shared (II); half the ceilings for these "
        "quarters (art. 197, I, 2), the widow's reduction whole (correction 18). Half the "
        "home-help increment (art. 199 sexdecies, 3; correction 17), half the childcare ceiling "
        "(art. 200 quater B; cases 7GE to 7GG) and half the school-fee reduction (art. 199 quater "
        "F; cases 7EB, 7ED, 7EG). The family allowances are shared by half (CSS art. L. 521-2, "
        "R. 521-2 and R. 521-3), as when the parents ask for it or designate no one; the other "
        "family benefits and the housing aid count the child in full, as for the parent the "
        "parents designate (art. R. 513-1; CCH art. L. 823-2); no ASF is paid for the child, whose "
        "other parent maintains them too (correction 19). Refused for a child of 18 or more on 1 "
        "January, who is no minor, and beside school fees when some children are shared and "
        "others not (D-201).",
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
    largest niche and why it cannot be imputed to taxpayers alone.

    Retained net of the aid received up to 12 000 EUR, plus 1 500 per dependent child and per
    adult of 65 or more on 31 December, 15 000 at most: openfisca counts the children, and
    correction 15 adds the adults (D-198). Up to 20 000, without increments, when a member of the
    foyer holds the invalidity card or a child opens a complément of the AEEH: the builder then
    ticks case 7DG, which no field types (CGI art. 199 sexdecies, 3; D-196)."""
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
#: and picking a plausible-looking name would have been picking the wrong one. That flag,
#: `f7dg`, has no field: the builder ticks it from the card and the AEEH's complément (D-196).
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
#: The same for children in alternating residence, whose ceiling is half (CGI art. 200 quater B):
#: the i-th amount of the list is the i-th child under six's, and goes to the next of these when
#: that child is shared (D-201).
NICHE_GARDE_ALTERNEE_CASES: tuple[str, ...] = ("f7ge", "f7gf", "f7gg")
#: The school-fee counts of shared children, whose amounts are halved (art. 199 quater F): written
#: there when every child is shared (D-201).
NICHE_SCOLARITE_ALTERNEE_CASES: dict[str, str] = {
    "enfants_college": "f7eb",
    "enfants_lycee": "f7ed",
    "enfants_superieur": "f7eg",
}
#: Individual-level, so it is written onto the adults rather than the foyer fiscal.
NICHE_SYNDICALES_CASE = "f7ac"


class RevenusCapital(BaseModel):
    """Capital income taxed at the prélèvement forfaitaire unique, in euros a year (D-249).

    The four boxes the population's imputation fills (D-248), and nothing else: the PFU is
    the default, and the option for the barème (case 2OP) is not expressible. Without this
    block the PFU knob moves nothing for a household, which is the engine answering as
    asked and not a wiring gap.

    **Written on every covered year, like the salary**, and unlike a niche: the revenu
    fiscal de référence of N-2 contains it, and that RFR sets the CSG rate of a pension
    and the means tests of N-2. A dividend declared once would be a different household.
    Measured: 10 000 EUR of dividends owe 1 280 EUR of PFU and 1 720 EUR of social levies.
    """

    model_config = INPUT_CONFIG

    dividendes: Annotated[float, Field(ge=0, le=100_000_000)] = 0.0
    """Revenus distribués, case 2DC: dividends, the one base whose response to the PFU
    is measured (Bach et al.; D-249)."""
    interets: Annotated[float, Field(ge=0, le=100_000_000)] = 0.0
    """Produits de placement à revenu fixe, case 2TR."""
    autres_revenus_distribues: Annotated[float, Field(ge=0, le=100_000_000)] = 0.0
    """Autres revenus distribués et revenus des structures soumises hors de France à un
    régime fiscal privilégié, case 2TS."""
    plus_values: Annotated[float, Field(ge=0, le=100_000_000)] = 0.0
    """Plus-values de cession de valeurs mobilières, case 3VG."""


#: Capital field -> the déclaration case it writes. The same four cases
#: `population.capital.CASES` imputes, and a test holds the two together.
CAPITAL_CASES: dict[str, str] = {
    "dividendes": "f2dc",
    "interets": "f2tr",
    "autres_revenus_distribues": "f2ts",
    "plus_values": "f3vg",
}


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


#: The situations de famille a lone adult declares in the cadre A of the 2042, « Célibataire »,
#: « Divorcé(e)/séparé(e) » and « Veuf(ve) », under the names openfisca's `statut_marital` gives
#: them. A couple's, married or pacsé, is `couple_marie_ou_pacse` (D-197).
SituationFamille = Literal["celibataire", "divorce", "veuf"]


class HouseholdInput(BaseModel):
    model_config = INPUT_CONFIG

    adults: Annotated[list[Adult], Field(min_length=1, max_length=2)]
    children: Annotated[list[Child], Field(max_length=MAX_CHILDREN)] = Field(default_factory=list)
    couple_marie_ou_pacse: bool = False
    situation_famille: SituationFamille = Field(
        default="celibataire",
        description="The situation de famille of a lone adult, as the 2042 declares it: "
        "célibataire (C), divorcé or separated (D), or veuf (V), the spouse or PACS partner "
        "having died before the year simulated. Written onto openfisca's monthly "
        "`statut_marital` on every covered month, like the salary, since the CSG of a "
        "replacement income reads the parts of N-2; célibataire, the default, is what "
        "openfisca's formula answers for a lone declarant, and writes nothing. A widow with a "
        "dependent child has the parts of a married couple (CGI art. 194, I), each half-part "
        "above one capped at the general ceiling, with the widow's own complementary "
        "reduction (art. 197, I, 2), and never case T, which is for « célibataires ou "
        "divorcés qui vivent seuls » (art. 194, II). Divorced or separated is taxed as single. "
        "Without a dependant a widow has one part, as a single person has: the half-part of "
        "art. 195, 1, a asks five years of raising a child alone, which the format does not "
        "carry. Divorced or widowed is refused beside a spouse, the couple's situation being "
        "`couple_marie_ou_pacse` (art. 6, 1). The year of the death, which takes two "
        "declarations (art. 6, 8), is not expressible, and openfisca's `jeune_veuf` is "
        "refused (D-197).",
    )
    parent_isole: bool | None = Field(
        default=None,
        description="Case T — parent isolé. Worth half a fiscal part. Left unset it is "
        "inferred: true for a lone adult with at least one dependent child, which is "
        "what a one-adult household with children describes, or with a person in case R, "
        "whom the 2042 names beside the children (D-202), false otherwise. Set it "
        "explicitly to false for a lone filer who does not in fact live alone. Never for a "
        "widow, who has a married couple's parts instead: not inferred, and refused when "
        "claimed (CGI art. 194, II; D-197).",
    )
    personnes_invalides_recueillies: Annotated[int, Field(ge=0, le=MAX_CHILDREN)] = Field(
        default=0,
        description="Case R of the 2042: the persons « (autres que vos enfants) vivant sous "
        "votre toit et titulaires de la carte d'invalidité ou de la CMI-invalidité ». « Tout "
        "contribuable peut considérer comme étant à sa charge, au sens de l'article 196, à la "
        "condition qu'elles vivent sous son toit, les personnes titulaires de la carte "
        "“ mobilité inclusion ” portant la mention “ invalidité ” » (CGI art. 196 A bis), with "
        "no condition of resources or kinship (BOI-IR-LIQ-10-10-10-30, § 30). Each is "
        "assimilated to a dependent child for the parts (art. 194, I), « soit une demi-part en "
        "tant que personne à charge et une demi-part en tant que personne invalide », and "
        "counts towards the third dependant's full part (§ 50); the card's half-part takes "
        "the general ceiling and the complementary reduction (art. 197, I, 2; § 55). Written "
        "onto openfisca's `nbR` on every covered year, like cases P and F, since the CSG of a "
        "replacement income reads the parts of N-2. A lone adult with such a person claims "
        "case T, the 2042's « avec votre (ou vos) enfant(s) ou des personnes invalides "
        "recueillies sous votre toit », and without a child the half-parts take the general "
        "ceiling, not the first child's (§ 55; `engine.corrections`, correction 20). Beside "
        "declared home help it ticks case 7DG, « Vous, votre conjoint ou une personne à votre "
        "charge avez la carte »: 20 000 EUR without increments (D-196). The person's own "
        "incomes and benefits are not computed: the AAH is exempt (CGI art. 81, 2°) and the "
        "person's, and the format carries no income of theirs, which would enter the foyer's "
        "(art. 6, 1). Refused beside a rented dwelling, whose aid reads the resources of "
        "« des personnes vivant habituellement à son foyer » (CCH art. L. 823-1, 2°) and counts "
        "a relative at 80 % among its dependants (art. R. 823-4, 3°), neither of which the "
        "format says (D-202).",
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
    capital: RevenusCapital | None = None
    """Capital income at the PFU. Absent means none, hence no PFU and no social levies
    on capital (D-249)."""

    def has_dependants(self) -> bool:
        """Whether the foyer has a dependant: a child, or a person in case R."""
        return bool(self.children) or self.personnes_invalides_recueillies > 0

    def resolved_parent_isole(self) -> bool:
        """Whether to claim case T for this household. Never inferred for a widow: case T is
        for « contribuables célibataires ou divorcés qui vivent seuls » (CGI art. 194, II), and
        a widow with a dependent child has a married couple's parts (I). openfisca would add
        the half-part to them (D-197). A person in case R opens it as a child does: the 2042
        asks case T of whoever lives alone « avec votre (ou vos) enfant(s) ou des personnes
        invalides recueillies sous votre toit » (D-202)."""
        lone_parent = (len(self.adults) == 1 and self.has_dependants()
                       and self.situation_famille != "veuf")
        return lone_parent if self.parent_isole is None else self.parent_isole

    @field_validator("situation_famille", mode="before")
    @classmethod
    def _refuse_the_year_of_the_death(cls, value: Any) -> Any:
        """openfisca's `jeune_veuf` is the survivor's own declaration for the months after a
        death in the year; on a lone declarant it counts no adult, and prices the income tax
        as NaN (D-197). Refused with the reason, rather than with the list of values."""
        if value == "jeune_veuf":
            raise ValueError(
                "L'année du décès n'est pas exprimable : « l'impôt afférent aux bénéfices et "
                "revenus non encore taxés est établi au nom des époux ou partenaires », et « Le "
                "conjoint ou le partenaire survivant est personnellement imposable pour la "
                "période postérieure au décès » (CGI art. 6, 8), avec les parts d'un couple "
                "marié. Ce sont deux déclarations, que le format ne porte pas. Choisissez veuf "
                "pour les années qui suivent."
            )
        return value

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
        if self.parent_isole and (len(self.adults) != 1 or not self.has_dependants()):
            raise ValueError(
                "parent_isole=true suppose un adulte seul avec au moins un enfant à charge, "
                "ou une personne invalide recueillie sous son toit (case R)."
            )
        if (self.personnes_invalides_recueillies and self.logement is not None
                and self.logement.statut.startswith("locataire")):
            raise ValueError(
                "Une personne invalide recueillie (case R) n'est pas exprimable à côté d'un "
                "logement loué : l'aide au logement compte les ressources « des personnes vivant "
                "habituellement à son foyer » (CCH art. L. 823-1, 2°), et compte parmi ses "
                "personnes à charge l'ascendant, le descendant ou le collatéral dont "
                "l'incapacité est d'au moins 80 % (art. R. 823-4, 3°). Le format ne dit ni les "
                "ressources de la personne ni sa parenté : le moteur n'en compterait aucune."
            )
        if len(self.adults) == 2 and self.situation_famille != "celibataire":
            raise ValueError(
                "situation_famille est celle d'un adulte seul. Un couple marié ou pacsé fait "
                "l'objet d'une imposition commune (CGI art. 6, 1) : sa situation est "
                "couple_marie_ou_pacse. Divorcé ou veuf, chacun déclare seul."
            )
        if self.situation_famille == "veuf" and self.parent_isole:
            raise ValueError(
                "La case T est réservée aux « contribuables célibataires ou divorcés qui vivent "
                "seuls » (CGI art. 194, II). Un veuf qui a un enfant à charge a déjà les parts "
                "d'un couple marié (art. 194, I), et la notice lui dit « ne cochez pas la case "
                "T ». Le moteur ajouterait une demi-part."
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
    # The daily allowances (D-306): the share of the work-accident ones exempt from the
    # income tax (CGI art. 81, 8°: 0.5 since 2010) and their CSG rate (CSS art. L. 136-8:
    # 6.2 %). The wire carries no allowance; the population does when `impute_ij` runs.
    ij_at_mp_part_exoneree: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    # The share of the sickness allowances served for an ALD exempt from the income tax
    # (CGI art. 80 quinquies: 1; the PLF 2027's art. 2 halves it), D-312.
    ij_ald_part_exoneree: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    csg_ij_taux: Annotated[float, Field(ge=0.0, le=0.2)] | None = None
    # Employer social contributions (D-038). Plafonds are in multiples of the SMIC,
    # which is why their ceiling is 10 and not 1: 1.6 is today's réduction générale.
    allegement_general_plafond: Annotated[float, Field(ge=0.0, le=10.0)] | None = None
    allegement_general_taux_50_et_plus: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    allegement_general_taux_moins_de_50: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    # The 2026 curve (D-240). From the refonte the réduction générale is
    # t_min + t_delta × (½ (3 SMIC / rémunération − 1))^puissance below its `plafond`, and
    # the two rates above no longer exist: these three move it, from 2026 only.
    allegement_general_t_min: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    allegement_general_t_delta_moins_de_50: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    allegement_general_t_delta_50_et_plus: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
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
    # PLF 2027 art. 74 (D-298): the two revaluations the article suspends, each a
    # COEFFICIENT on what the tree carries on its legal date in the priced year — 1.021
    # revalues by 2,1 % — written from that date and not from January. A level would not
    # say the same thing: the level on that date is the tree's.
    ppa_revalorisation_avril: Annotated[float, Field(ge=0.5, le=2.0)] | None = None
    """The prime d'activité's montant forfaitaire, from 1 April (CSS L. 842-3, sixth
    paragraph). The bonification is a share of it and follows."""
    al_revalorisation_octobre: Annotated[float, Field(ge=0.5, le=2.0)] | None = None
    """The housing-aid expense parameters, from 1 October (CCH L. 823-4): rent ceilings,
    charge allowances, the foyers' rent equivalences and the flat minimum contribution,
    every leaf the tree's last October revision moved."""
    # The same two, CARRIED (D-301): the revaluation of the year before the priced year,
    # written at that year's legal date, so that the whole priced year carries the level
    # it left. What a multi-year path prices after a revaluation's first year.
    ppa_revalorisation_portee: Annotated[float, Field(ge=0.5, le=2.0)] | None = None
    al_revalorisation_portee: Annotated[float, Field(ge=0.5, le=2.0)] | None = None

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
    # Capital income (D-249).
    pfu_taux: Annotated[float, Field(ge=0.0, le=1.0)] | None = None
    """The income-tax part of the prélèvement forfaitaire unique, 12,8 % today: one
    parameter for dividends, interest, plus-values and the life insurance above its
    threshold. The social levies, 17,2 %, are not this knob. It bites only on capital
    income, which a household declares in `capital` and the population carries only
    with `impute_capital` (D-248)."""
    # The social part of the PFU (D-320): the CSG on capital income at its general rate
    # (10,6 % from 2026, LFSS 2026) and the prélèvement de solidarité (7,5 %). The CRDS
    # (0,5 %) and the CSG kept at 9,2 % on the « allégés » products are not moved.
    csg_capital_taux_global: Annotated[float, Field(ge=0.0, le=0.3)] | None = None
    prelevement_solidarite_capital: Annotated[float, Field(ge=0.0, le=0.3)] | None = None
    # The CSG on retirement and invalidity pensions (D-320): its TAXABLE part, at the full
    # and the median rate. The deductible part is not a knob: both builders pin the declared
    # pension on box 1AS, already net of it (D-176), so no formula would read a new rate.
    csg_pensions_imposable_taux_plein: Annotated[float, Field(ge=0.0, le=0.2)] | None = None
    csg_pensions_imposable_taux_median: Annotated[float, Field(ge=0.0, le=0.2)] | None = None
    # The quotient familial (D-320): the parts a child brings in the general case, and the
    # ceiling of the advantage for the first child of a lone parent (case T).
    qf_parts_enf1: Annotated[float, Field(ge=0.0, le=3.0)] | None = None
    qf_parts_enf2: Annotated[float, Field(ge=0.0, le=3.0)] | None = None
    qf_parts_enf3_et_sup: Annotated[float, Field(ge=0.0, le=3.0)] | None = None
    plafond_qf_parent_isole: Annotated[float, Field(ge=0, le=100_000)] | None = None
    # The employee's retirement contributions (D-320), all at once: the Cnav's capped and
    # uncapped rates, Agirc-Arrco, the CEG and the CET, each multiplied by this factor (1
    # leaves them, 0 removes them). Not the employer's.
    cotisations_salariales_retraite_echelle: Annotated[float, Field(ge=0.0, le=2.0)] | None = None
    # The consumption taxes paid by households (D-323, but 12). They move nothing in the
    # tax-benefit tree: the population pass prices them on the consumption it imputes
    # (`impots.consommation`), at constant volumes. A scenario that sets one must ask for
    # the « consommation » imputation, or the pass refuses.
    tva_taux_normal: Annotated[float, Field(ge=0.0, le=0.5)] | None = None
    tva_taux_intermediaire: Annotated[float, Field(ge=0.0, le=0.5)] | None = None
    tva_taux_reduit: Annotated[float, Field(ge=0.0, le=0.5)] | None = None
    tva_taux_super_reduit: Annotated[float, Field(ge=0.0, le=0.5)] | None = None
    tva_postes: dict[str, Annotated[float, Field(ge=0.0, le=0.5)]] | None = None
    """A rate for one poste of the Budget de famille survey (its five-position COICOP
    code) or a named group (`impots.consommation.GROUPES`: energie, carburants,
    electricite, gaz, fioul, restauration). Applied after the four rate knobs."""
    accise_gazole: Annotated[float, Field(ge=0.0, le=3.0)] | None = None
    accise_essence: Annotated[float, Field(ge=0.0, le=3.0)] | None = None
    accise_fioul: Annotated[float, Field(ge=0.0, le=3.0)] | None = None
    """EUR per litre."""
    accise_electricite: Annotated[float, Field(ge=0.0, le=200.0)] | None = None
    accise_gaz: Annotated[float, Field(ge=0.0, le=200.0)] | None = None
    """EUR per MWh."""

    @field_validator("tva_postes")
    @classmethod
    def _check_tva_postes(cls, value: dict[str, float] | None) -> dict[str, float] | None:
        if value is None:
            return value
        from impots.consommation import GROUPES, REPARTIS, postes

        # A poste the imputation splits between others has no spending of its own (R11).
        connus = set(GROUPES) | ({p.code for p in postes()} - set(REPARTIS))
        inconnus = sorted(set(value) - connus)
        if inconnus or not value:
            raise ValueError(f"tva_postes : {inconnus or 'aucun'} ; postes et groupes connus "
                             f"dans impots.consommation")
        return value

    @model_validator(mode="after")
    def _check_revalorisations(self) -> ReformSpec:
        """Two knobs on the same amount do not compose: a level is written from January
        and a coefficient multiplies what the tree carries, so each would read the other's
        write, and the pair would say what neither says alone (D-298, D-301)."""
        for first, second in (("ppa_montant_de_base", "ppa_revalorisation_avril"),
                              ("ppa_montant_de_base", "ppa_revalorisation_portee"),
                              ("ppa_revalorisation_avril", "ppa_revalorisation_portee"),
                              ("al_revalorisation_octobre", "al_revalorisation_portee")):
            if getattr(self, first) is not None and getattr(self, second) is not None:
                raise ValueError(
                    f"« {first} » et « {second} » portent le même montant : l'un ou "
                    f"l'autre, pas les deux.")
        return self

    @model_validator(mode="after")
    def _check_bareme(self) -> ReformSpec:
        if self.ir_bareme is None:
            return self
        n = len(self.ir_bareme)
        if n < MIN_BAREME_BRACKETS:
            raise ValueError(f"Le barème doit compter au moins {MIN_BAREME_BRACKETS} tranches.")
        if n > MAX_BAREME_BRACKETS:
            raise ValueError(
                f"Le barème est limité à {MAX_BAREME_BRACKETS} tranches : les tranches "
                "actives du barème légal sont remplacées sur place, et une seule tranche "
                "dormante du ParameterScale peut être réveillée (D-320)."
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
    csg_ij: float
    """The CSG on the sick pay, levied by correction 23 (D-306). Zero for a household the
    wire format builds, which carries no allowance; a receipt of its own in the ledger
    (D-307)."""
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
    pfu: float
    """The prélèvement forfaitaire unique owed on capital income, income-tax part: a
    « dont » of `ir`, never added to it (D-248). Zero for a household that declares no
    `capital` (D-249), and for a population run without `impute_capital`."""
    prelevements_sociaux_capital: float
    """The social levies on that income, which `ir` does not hold (D-248)."""
    dividendes: float
    """The dividends declared at the PFU, case 2DC: the base of the dividend channel C10,
    read back from the engine, never a receipt (D-249)."""
    cdhr: float
    """The contribution différentielle sur les hauts revenus, from 2025: a high income's
    tax topped up to 20 % of its RFR, PFU included. Not in `ir`, a receipt of its own;
    zero without capital income (D-250)."""
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
    impute_capital: bool = False
    """Hand out the base the PFU taxes from DGFiP n° 41's fractiles of RFR per part, so
    the population carries capital income at all (D-248). Opt-in and OFF BY DEFAULT for
    the same reason as the niches: it is a CALIBRATION, and the PFU part of the net-yield
    line stops being evidence. It costs an extra pass, and holds for the 2024 income
    only: another year is refused by name."""

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


class FirmCir(BaseModel):
    """The CIR, priced on the créance flow of a GECIR millésime (D-222). Its own block,
    never summed into `reform_cost`: a créance is paid over five or six years, and the
    budget's dépense fiscale for a year is printed beside it, not mixed in."""

    model_config = ConfigDict(extra="forbid")

    millesime: int
    rates: dict[str, float]
    rates_reform: dict[str, float]
    creance_publiee_eur: float
    """The GECIR total; `creance_eur` is the same rebuilt from the base split."""
    creance_eur: float
    creance_reform_eur: float
    delta_creance_eur: float
    """Positive: the State grants more credit. A cost, in créance."""
    depense_fiscale_eur: dict[int, float]
    """Voies et Moyens' dépense fiscale n° 200302 by budget year — another object."""
    banner: str
    sources: list[str]


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
    cir: FirmCir | None = None
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


# --------------------------------------------------------------------------- #
# Phase 9 M1 — the conditional predictive chain (PHASE9_SPEC §3.4)
#
# Every hypothesis is a REQUIRED field: no spending, growth or rate scenario has a
# default, because a default here would be the scenario nobody chose (D-213).
# --------------------------------------------------------------------------- #
class PredictifSpending(BaseModel):
    model_config = INPUT_CONFIG

    rule: Literal["part_pib_constante", "gele_en_volume", "personnalise"]
    name: str | None = None
    """Required with « personnalise », whose name is the caller's; the two shipped rules
    carry their own names and refuse another."""
    growth: float | None = None


class PredictifGrowth(BaseModel):
    model_config = INPUT_CONFIG

    name: str
    real: Annotated[float, Field(gt=-1.0, lt=1.0)]
    prices: Annotated[float, Field(gt=-1.0, lt=1.0)]


class PredictifRate(BaseModel):
    model_config = INPUT_CONFIG

    name: str
    kind: Literal["implicite_tenu", "marche"]
    market_rate: Annotated[float, Field(gt=-0.1, lt=0.5)] | None = None


class PredictifUprating(BaseModel):
    """How the first year's population is aged (D-226). REQUIRED, like every hypothesis.

    The wage index is the caller's, with where it comes from: this project forecasts
    neither wages nor prices. The price index is NOT asked: it is the growth scenario's
    (`annuel.uprating_for`), so the reform's euros and the GDP that divides them inflate
    together (D-216). A blank source or a rate that is not an annual one is refused by
    `Uprating`'s own message rather than by a bound here, so that the refusal says why.
    """

    model_config = INPUT_CONFIG

    wage: float
    source: str


class PredictifTheta(BaseModel):
    """The user's θ (PHASE9_SPEC §2, D-217). REQUIRED: there is no default, not even 1/2.

    `common` sets every open row; `rows` names some and wins over it. A value outside
    [0, 1] is refused by the chain's own message rather than by a bound here, so that the
    refusal says why — and is never a clip.
    """

    model_config = INPUT_CONFIG

    common: float | None = None
    rows: dict[str, float] = Field(default_factory=dict)


#: The firm-layer knobs the predictive chain refuses: the CIR is priced on the créance
#: flow, which is not a year's receipts (D-222), so it stays out of the path.
FIRM_KNOBS_OUT_OF_CHAIN = ("cir_taux", "cir_taux_au_dela")


def _refuse_firm_knobs_out_of_chain(spec: FirmReformSpec | None) -> None:
    named = sorted(set(spec.model_dump(exclude_none=True) if spec else {})
                   & set(FIRM_KNOBS_OUT_OF_CHAIN))
    if named:
        raise ValueError(
            f"{named} hors de la chaîne prédictive : le CIR se chiffre sur le flux de "
            f"créances, qui n'est pas la recette d'une année (D-222). Le chiffrer est le "
            f"rôle de `/entreprises/simulate`.")


def _refuse_a_law_the_carry_cannot_see(specs: list[FirmReformSpec | None],
                                       horizon: int) -> None:
    """The carried path prices its first year and holds it as a share of GDP to the end of
    the horizon. A firm knob whose law moves within the horizon would be held at its first
    year's law: the CVAE's is cut in 2028 and abolished in 2030 (D-254). Refused, pointing
    to the path that prices each year under its own law."""
    from impots.entreprises import system as firm_system
    from impots.entreprises.reforms import law_moves
    from impots.predictif.chaine import START_YEAR

    first, last = START_YEAR + 1, START_YEAR + horizon
    moves: dict[str, int] = {}
    for spec in specs:
        if spec is not None and not spec.is_empty():
            moves.update(law_moves(spec, firm_system.baseline().parameters, first, last))
    if moves:
        named = ", ".join(f"« {knob} » en {year}" for knob, year in sorted(moves.items()))
        raise ValueError(
            f"le droit que règle {named} change dans l'horizon : ce chemin chiffre {first} "
            f"et le reporte, et le tiendrait à son droit de {first} jusqu'en {last}. "
            f"`impots predictif` chiffre chaque année sous le sien (D-254).")


class PredictifRequest(BaseModel):
    model_config = INPUT_CONFIG

    reform: ReformSpec = Field(default_factory=ReformSpec)
    """The households' reform; empty is allowed when `firm_reform` carries one."""
    firm_reform: FirmReformSpec | None = None
    """The firm layer's reform, priced for the first year by `/entreprises/simulate`'s
    own pass and added to the households' (PHASE11_SPEC §3). Its taxes have no Mésange
    variant: the loop is absent for them, and said so."""
    spending: PredictifSpending
    growth: PredictifGrowth
    rate: PredictifRate
    horizon: Annotated[int, Field(ge=1, le=10)]
    theta: PredictifTheta
    uprating: PredictifUprating
    behavioural: bool = False
    macro: bool = False
    """The GDP → receipts loop from Mésange's balance row (D-218). Off, the path is
    without it and says so; on, it reads only under « gele_en_volume »."""
    persistence: Literal["eteint", "tenu"] | None = None
    """Past three years, the loop needs one, and none is the default."""
    indices: list[str] | None = None
    """The §7 indices asked for, by key; all of them when omitted. The list is closed,
    and a key outside it is refused by name (D-223)."""

    @model_validator(mode="after")
    def _check_reform(self) -> PredictifRequest:
        if self.reform.is_empty() and (self.firm_reform is None
                                       or self.firm_reform.is_empty()):
            raise ValueError("Une réforme est requise : sans réforme, la trajectoire de "
                             "la réforme est celle de la référence.")
        _refuse_firm_knobs_out_of_chain(self.firm_reform)
        _refuse_a_law_the_carry_cannot_see([self.firm_reform], self.horizon)
        return self


def _walkable(annotation: Any) -> bool:
    """A knob a grid can walk: a number, with or without its bounds, or None."""
    for arg in get_args(annotation) or (annotation,):
        if arg is type(None):
            continue
        if get_origin(arg) is Annotated:
            arg = get_args(arg)[0]
        if arg not in (float, int):
            return False
    return True


class ExplorationBound(BaseModel):
    """One knob of the grid: a scalar field of `ReformSpec` or a named transformation
    (`predictif.transformations`), its range and its step."""

    model_config = INPUT_CONFIG

    knob: str
    low: float
    high: float
    step: Annotated[float, Field(gt=0)]


class ExplorationTarget(BaseModel):
    """Δb at `year`, the horizon's last when omitted, at most `at_most_points` points of
    GDP. A lower debt is a negative difference: the target is met from below (D-224)."""

    model_config = INPUT_CONFIG

    year: int | None = None
    at_most_points: float


class ExplorationRequest(BaseModel):
    """A search for the bundles whose debt difference meets a target, at a fixed θ and
    under named scenarios (PHASE10_SPEC §2): every hypothesis `/predictif/simulate` asks
    for, and what to search over. A file read by `impots exploration`, never a request:
    a search is two population passes per bundle."""

    model_config = INPUT_CONFIG

    name: str
    titre: str
    question: str
    """The question the search answers, in a sentence: the report leads with it."""
    base: ReformSpec = Field(default_factory=ReformSpec)
    """The fixed part of every bundle; empty is allowed."""
    firm_base: FirmReformSpec | None = None
    """The fixed firm part of every bundle (PHASE11_SPEC §3). Absent rather than empty
    by default, so a household search's request reads as it always did."""
    bounds: Annotated[list[ExplorationBound], Field(min_length=1)]
    target: ExplorationTarget
    spending: PredictifSpending
    growth: PredictifGrowth
    rate: PredictifRate
    horizon: Annotated[int, Field(ge=1, le=10)]
    uprating: PredictifUprating
    theta: PredictifTheta
    """Required, like the simulator's: no default, not even 1/2 (D-217)."""
    behavioural: bool = False
    macro: bool = False
    persistence: Literal["eteint", "tenu"] | None = None

    @model_validator(mode="after")
    def _check_exploration_bounds(self) -> ExplorationRequest:
        if not self.question.strip():
            raise ValueError(
                "exploration sans question : le rapport s'ouvre sur elle, et un tableau de "
                "paquets sans la question qu'il tranche se lit comme une recommandation.")
        _refuse_firm_knobs_out_of_chain(self.firm_base)
        fixed = set(self.base.model_dump(exclude_none=True))
        firm_fixed = set(self.firm_base.model_dump(exclude_none=True)
                         if self.firm_base else {})
        for bound in self.bounds:
            firm_field = FirmReformSpec.model_fields.get(bound.knob)
            if firm_field is not None:
                if bound.knob in FIRM_KNOBS_OUT_OF_CHAIN:
                    _refuse_firm_knobs_out_of_chain(FirmReformSpec.model_validate(
                        {bound.knob: bound.low}))
                if not _walkable(firm_field.annotation):
                    raise ValueError(
                        f"bouton « {bound.knob} » : ce n'est pas un nombre, et la grille "
                        f"ne sait parcourir que des nombres.")
                if bound.knob in firm_fixed:
                    raise ValueError(
                        f"bouton « {bound.knob} » fixé aussi dans `firm_base` : la grille "
                        f"l'écraserait, et le rapport afficherait une base que rien n'a "
                        f"chiffrée.")
                continue
            transformation = TRANSFORMATIONS.get(bound.knob)
            if transformation is not None:
                clash = sorted(fixed & set(transformation.writes))
                if clash:
                    raise ValueError(
                        f"bouton « {bound.knob} » : il écrit {clash}, fixé aussi dans la "
                        f"base ; la transformation l'écraserait, et le rapport afficherait "
                        f"une base que rien n'a chiffrée.")
                continue
            field = ReformSpec.model_fields.get(bound.knob)
            if field is None:
                raise ValueError(
                    f"bouton « {bound.knob} » inconnu : un bouton est un champ de la "
                    f"réforme des ménages, de celle des entreprises, ou une "
                    f"transformation nommée ({sorted(TRANSFORMATIONS)}), jamais un "
                    f"chemin du barème ni un θ.")
            if not _walkable(field.annotation):
                raise ValueError(
                    f"bouton « {bound.knob} » : ce n'est pas un nombre, et la grille ne "
                    f"sait parcourir que des nombres. Un barème entre par une "
                    f"transformation nommée, testée à part (PHASE10_SPEC §5).")
            if bound.knob in fixed:
                raise ValueError(
                    f"bouton « {bound.knob} » fixé aussi dans la base : la grille "
                    f"l'écraserait, et le rapport afficherait une base que rien n'a "
                    f"chiffrée.")
        # Knob by knob for the grid: whether its law moves does not depend on the value.
        _refuse_a_law_the_carry_cannot_see(
            [self.firm_base, *(FirmReformSpec.model_validate({b.knob: b.low})
                               for b in self.bounds if b.knob in FirmReformSpec.model_fields)],
            self.horizon)
        return self


class PredictifSlice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    label: str
    computed: bool
    reason: str = ""
    low: list[float] = Field(default_factory=list)
    high: list[float] = Field(default_factory=list)


class PredictifStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    debt_ratio: float
    primary_balance: float
    implicit_rate: float
    gdp_eur: float


class PredictifBehaviour(BaseModel):
    """The first year's receipts at θ and its θ box, RECEIPTS POSITIVE, mechanical
    included (`comportement.evaluate`)."""

    model_config = ConfigDict(extra="forbid")

    receipts_first_year_eur: float
    box_first_year_eur: list[float]
    claimed: list[str]
    """The open rows the reform's knobs claim — the only ones the box moves."""
    grade: str


class PredictifIndex(BaseModel):
    """One index of §7 (`predictif.indices`), in its own unit, never added to another."""

    model_config = ConfigDict(extra="forbid")

    key: str
    pour: str
    label: str
    unit: str
    stage: str
    source: str
    theta: list[str]
    """The θ that move it; empty for an index no θ reads, shown as fixed."""
    note: str
    available: bool
    values: dict[str, float]
    """By year, by Mésange horizon (« 1 », « 2 », « 3 ») or by decile (« D1 »…)."""
    box: dict[str, list[float]] | None = None
    reason: str = ""
    conventions: list[str] = Field(default_factory=list)
    uncovered: dict[str, str] = Field(default_factory=dict)


class PredictifPersistence(BaseModel):
    """One persistence scenario's path, when the loop runs past three years and the
    request named none: the two are computed from the same pass and shown side by side,
    neither of them in the lead (D-230)."""

    model_config = ConfigDict(extra="forbid")

    persistence: Literal["eteint", "tenu"]
    label: str
    reform: list[float]
    delta: list[float]
    delta_primary: list[float]
    slices: list[PredictifSlice]
    conventions: list[str]
    """Every convention of this path, the common ones included."""
    gdp_gap: list[float]
    feedback_primary: list[float]
    indices: list[PredictifIndex] = Field(default_factory=list)
    """The chain-stage indices, which depend on the path; the others are the response's."""


#: The layers a predictive first year's cost is ranged under, and sums over.
FIRST_YEAR_LAYERS = ("menages", "entreprises")


class PredictifResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    years: list[int]
    reference: list[float]
    reform: list[float] | None
    """None when the two persistence scenarios stand side by side (`side_by_side`)."""
    delta: list[float] | None
    """Reform minus reference, in points of GDP (0.01 = one point); None side by side."""
    reference_primary: list[float]
    delta_primary: list[float] | None
    priced_years: list[int]
    carried_years: list[int]
    spending_name: str
    growth_name: str
    rate_name: str
    conventions: list[str]
    absent: dict[str, str]
    slices: list[PredictifSlice]
    start: PredictifStart
    mechanical_first_year_eur: float
    """The engine's cost for the first projected year, COST POSITIVE."""
    mechanical_first_year_by_layer: dict[str, float]
    """That cost by layer, « menages » and « entreprises », which sum to it (PHASE11_SPEC
    §10, guard 8). No default, so a response cannot leave its layers out."""
    delta_mechanical: list[float]
    """The difference with every behavioural channel off; θ has no effect on it."""
    theta: dict[str, float]
    """Every open row with the θ it ran at (§2.3)."""
    theta_applied: bool
    closed: dict[str, str]
    """Every channel with no θ in this result, and why (§2.5)."""
    behaviour: PredictifBehaviour | None = None
    gdp_gap: list[float] | None = None
    """y_t, the reform's GDP over the reference's minus one, when the loop runs."""
    feedback_primary: list[float] | None = None
    """φ_t, the loop's share of the reform's primary balance, when it runs."""
    persistence: str | None = None
    side_by_side: list[PredictifPersistence] = Field(default_factory=list)
    """Both persistence scenarios, when the loop runs past three years and none was named
    (D-230). The response then carries NO path of its own: a path in the lead would be a
    default by placement."""
    indices: list[PredictifIndex] = Field(default_factory=list)
    population_view: Literal["figee", "vieillie"]
    """The population the first year was priced on, in `predictif.annuel`'s words:
    « vieillie », the 2024 population aged to that year, the command's headline (D-216,
    D-226). No default, so a response cannot leave it out."""
    population_note: str
    banner: str
    debt_banner: str

    @model_validator(mode="after")
    def _one_path_or_both_scenarios(self) -> PredictifResponse:
        own = (self.reform, self.delta, self.delta_primary, self.gdp_gap,
               self.feedback_primary, self.persistence)
        if not self.side_by_side:
            if self.reform is None or self.delta is None or self.delta_primary is None:
                raise ValueError("réponse sans trajectoire ni scénarios côte à côte")
            return self
        if any(v is not None for v in own) or self.slices:
            raise ValueError(
                "côte à côte, la réponse ne porte aucune trajectoire en propre : l'une des "
                "deux en tête se lirait comme le défaut (D-230)")
        if sorted(p.persistence for p in self.side_by_side) != ["eteint", "tenu"]:
            raise ValueError("côte à côte, ce sont les deux scénarios de persistance, "
                             "chacun une fois")
        return self

    @model_validator(mode="after")
    def _cost_is_the_sum_of_its_layers(self) -> PredictifResponse:
        layers = self.mechanical_first_year_by_layer
        unknown = sorted(set(layers) - set(FIRST_YEAR_LAYERS))
        if not layers or unknown:
            raise ValueError(f"couche inconnue {unknown} ou aucune : le coût de la première "
                             f"année se range sous {list(FIRST_YEAR_LAYERS)}")
        total = sum(layers.values())
        if not math.isclose(total, self.mechanical_first_year_eur, rel_tol=1e-9, abs_tol=1.0):
            raise ValueError(
                f"coût de la première année, {self.mechanical_first_year_eur:.0f} €, qui "
                f"n'est pas la somme de ses couches, {total:.0f} € (PHASE11_SPEC §10)")
        return self


class PredictifReportYear(BaseModel):
    """One year of an annual report. The reform's paths are None when two persistence
    scenarios stand side by side: neither is the lead (D-230, D-236)."""

    model_config = ConfigDict(extra="forbid")

    year: int
    basis: str
    mechanical_frozen_eur: float
    mechanical_aged_eur: float
    reference: float
    reform_aged: float | None
    delta_aged: float | None
    reform_frozen: float | None
    delta_frozen: float | None
    mechanical_by_layer: dict[str, dict[str, float]] | None = None
    """By view, the cost by layer, when a firm reform is priced (D-246); absent from the
    reports of household reforms."""

    @model_validator(mode="after")
    def _layers_sum_to_the_cost(self) -> PredictifReportYear:
        if self.mechanical_by_layer is None:
            return self
        totals = {"figee": self.mechanical_frozen_eur, "vieillie": self.mechanical_aged_eur}
        if set(self.mechanical_by_layer) != set(totals):
            raise ValueError(f"{self.year} : couches pour {sorted(self.mechanical_by_layer)},"
                             f" les vues sont {sorted(totals)}")
        for view, layers in self.mechanical_by_layer.items():
            unknown = sorted(set(layers) - set(FIRST_YEAR_LAYERS))
            total = sum(layers.values())
            if unknown or not math.isclose(total, totals[view], rel_tol=1e-9, abs_tol=1.0):
                raise ValueError(
                    f"{self.year}, vue « {view} » : coût {totals[view]:.0f} € qui n'est pas "
                    f"la somme de ses couches {layers} (PHASE11_SPEC §10)")
        return self


class PredictifReportPathYear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    reform_aged: float
    delta_aged: float
    reform_frozen: float
    delta_frozen: float


class PredictifReportPath(BaseModel):
    """One persistence scenario of an annual report with the loop, in both views."""

    model_config = ConfigDict(extra="forbid")

    persistence: Literal["eteint", "tenu"]
    label: str
    years: list[PredictifReportPathYear]
    conventions: list[str]
    gdp_gap_aged: list[float]


#: Δb at θ inside its corners, and equal to the path, to float noise (a share of GDP).
BOX_SLACK = 1e-9
BOX_VIEWS = {"vieillie", "figee"}


class PredictifBoxReading(BaseModel):
    """One view of one reading of the box: Δb at θ, then at each corner (D-275)."""

    model_config = ConfigDict(extra="forbid")

    theta: float
    corners: list[tuple[str, float]]


class PredictifBoxPath(BaseModel):
    """The box under one persistence: every year priced, and the first year carried."""

    model_config = ConfigDict(extra="forbid")

    persistence: Literal["eteint", "tenu"] | None
    every_year: dict[Literal["vieillie", "figee"], PredictifBoxReading]
    first_year: dict[Literal["vieillie", "figee"], PredictifBoxReading]


class PredictifThetaBox(BaseModel):
    """Δb at an annual report's last year, at θ and at every corner of its θ box, every
    year priced and the first year carried as the explorer carries it (D-275)."""

    model_config = ConfigDict(extra="forbid")

    year: int
    rows: list[str]
    paths: list[PredictifBoxPath]

    @model_validator(mode="after")
    def _corners_hold(self) -> PredictifThetaBox:
        if not self.rows or len(set(self.rows)) != len(self.rows):
            raise ValueError(f"boîte θ sans ligne, ou une ligne deux fois ({self.rows}) : "
                             f"ses coins ne diraient pas ce qui déplace la dette.")
        expected: list[str] | None = None
        for path in self.paths:
            for reading in ("every_year", "first_year"):
                views = getattr(path, reading)
                if set(views) != BOX_VIEWS:
                    raise ValueError(f"boîte θ, {reading} : vues {sorted(views)}, il en faut "
                                     f"deux, {sorted(BOX_VIEWS)}.")
                for view, one in views.items():
                    if len(one.corners) != 2 ** len(self.rows):
                        raise ValueError(
                            f"boîte θ, {reading}, vue « {view} » : {len(one.corners)} coins "
                            f"pour {len(self.rows)} lignes, il en faut {2 ** len(self.rows)}.")
                    labels = [label for label, _ in one.corners]
                    if expected is None:
                        named = {frozenset(part.split(" = ")[0] for part in label.split(", "))
                                 for label in labels}
                        if named != {frozenset(self.rows)} or len(set(labels)) != len(labels):
                            raise ValueError(
                                f"boîte θ : ses coins ne nomment pas les lignes {self.rows}, "
                                f"chacun une fois.")
                        expected = labels
                    elif labels != expected:
                        raise ValueError(
                            f"boîte θ, {reading}, vue « {view} » : ses coins ne nomment pas "
                            f"ceux des autres lectures, dans le même ordre.")
                    values = [value for _, value in one.corners]
                    if not min(values) - BOX_SLACK <= one.theta <= max(values) + BOX_SLACK:
                        raise ValueError(
                            f"boîte θ, {reading}, vue « {view} » : Δb à θ ({one.theta:+.5f}) "
                            f"sort de sa boîte [{min(values):+.5f} ; {max(values):+.5f}].")
        return self


class PredictifReportResponse(BaseModel):
    """A full path, every year priced (`impots predictif`). Read from a file; never runs."""

    model_config = ConfigDict(extra="forbid")

    scenario: str
    titre: str
    source: str
    reference: str
    computed: str
    spending_name: str
    growth_name: str
    rate_name: str
    start: PredictifStart
    years: list[PredictifReportYear]
    conventions: list[str]
    absent: dict[str, str]
    theta: dict[str, float]
    theta_applied: bool
    closed: dict[str, str]
    uprating_note: str
    banner: str
    debt_banner: str
    behavioural: bool = False
    macro: bool = False
    persistence: Literal["eteint", "tenu"] | None = None
    side_by_side: list[PredictifReportPath] = Field(default_factory=list)
    theta_box: PredictifThetaBox | None = None
    """With behaviour or the loop, Δb at the last year at θ and at the box's corners
    (D-275); absent from the reports before it."""
    commit: str | None = None
    dirty: bool | None = None
    where: str | None = None
    annees: list[int] | None = None
    """The years the text applies the measure in, when it names them (D-288); absent
    from the reports before it."""

    @model_validator(mode="after")
    def _check_report_paths(self) -> PredictifReportResponse:
        own = [y for y in self.years
               if None not in (y.reform_aged, y.delta_aged, y.reform_frozen, y.delta_frozen)]
        if self.side_by_side:
            if own:
                raise ValueError(
                    "rapport annuel avec une trajectoire en propre ET des scénarios côte à "
                    "côte : celle en tête serait le défaut par la place qu'elle occupe "
                    "(D-230).")
            persistences = [p.persistence for p in self.side_by_side]
            if sorted(persistences) != ["eteint", "tenu"]:
                raise ValueError(
                    f"scénarios côte à côte {persistences} : les deux persistances, chacune "
                    f"une fois (D-230).")
            if any(len(p.years) != len(self.years) for p in self.side_by_side):
                raise ValueError("un scénario côte à côte ne couvre pas toutes les années")
        elif len(own) != len(self.years):
            raise ValueError(
                "rapport annuel sans trajectoire pour certaines années, et sans scénarios "
                "côte à côte : une année sans chemin se lirait comme un écart nul.")
        return self

    @model_validator(mode="after")
    def _box_is_the_paths(self) -> PredictifReportResponse:
        """Every year priced, the box at θ is the path the report draws, at its last year,
        under each of its persistences. Read after the paths themselves: a box is held to
        paths that already hold."""
        box = self.theta_box
        if box is None:
            return self
        if not self.years or box.year != self.years[-1].year:
            raise ValueError(f"boîte θ de {box.year}, et la dernière année du rapport est "
                             f"{self.years[-1].year if self.years else None} : elle "
                             f"se lirait pour une autre année.")
        drawn = ({p.persistence: (p.years[-1].delta_aged, p.years[-1].delta_frozen)
                  for p in self.side_by_side} if self.side_by_side
                 else {self.persistence: (self.years[-1].delta_aged,
                                          self.years[-1].delta_frozen)})
        if [p.persistence for p in box.paths] != list(drawn):
            raise ValueError(f"persistances de la boîte {[p.persistence for p in box.paths]}"
                             f", et celles du rapport {list(drawn)}.")
        for path in box.paths:
            aged, frozen = drawn[path.persistence]
            for view, value in (("vieillie", aged), ("figee", frozen)):
                at = path.every_year[view].theta
                if value is None or not math.isclose(at, value, rel_tol=1e-12,
                                                     abs_tol=1e-15):
                    raise ValueError(
                        f"boîte θ, vue « {view} », persistance {path.persistence} : Δb à θ "
                        f"{at!r} n'est pas le chemin du rapport, {value!r}, à sa dernière "
                        f"année.")
        return self

class PredictifReportList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rapports: list[str] = Field(default_factory=list)


class ExplorationEvaluation(BaseModel):
    """One bundle as the search evaluated it. Costs in euros, COST POSITIVE; Δb as a share
    of GDP, negative when the reform lowers the debt; the corners in the θ box's order."""

    model_config = ConfigDict(extra="forbid")

    knobs: dict[str, float]
    cost_aged_eur: float
    cost_frozen_eur: float
    delta_aged: float
    delta_frozen: float
    corners: Annotated[list[tuple[str, float]], Field(min_length=1)]
    corner_low: float
    corner_high: float
    meets_target: bool


class ExplorationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knobs: dict[str, float]
    delta_aged: float
    delta_frozen: float
    meets_target: bool
    frozen_only: bool
    robust: bool | None
    verdict: str


class ExplorationIndices(BaseModel):
    """The indices of §7 for the bundle nearest the target, aged view, from the pass that
    priced it (PHASE10_SPEC §5): each in its own unit, none added to another."""

    model_config = ConfigDict(extra="forbid")

    knobs: dict[str, float]
    delta_aged: float
    absent: dict[str, str] = Field(default_factory=dict)
    """What the bundle's path lacks, with why (`Trajectoire.absent`), D-238."""
    closed: dict[str, str] = Field(default_factory=dict)
    rows: Annotated[list[PredictifIndex], Field(min_length=1)]

    @model_validator(mode="after")
    def _check_exploration_indices(self) -> ExplorationIndices:
        silent = sorted(k for k, v in {**self.absent, **self.closed}.items()
                        if not v.strip())
        if silent:
            raise ValueError(
                f"absent sans sa raison : {silent}. Une absence muette se lit comme un "
                f"zéro mesuré.")
        return self


class ExplorationSearch(BaseModel):
    """One search, under one persistence scenario or none (D-230)."""

    model_config = ConfigDict(extra="forbid")

    persistence: Literal["eteint", "tenu"] | None
    persistence_label: str | None
    digest: str
    log: dict[str, Any]
    evaluations: Annotated[list[ExplorationEvaluation], Field(min_length=1)]
    candidates: list[ExplorationCandidate]
    excluded: list[Any]
    closest: ExplorationEvaluation | None
    indices: ExplorationIndices | None = None
    """Absent from the reports written before M4 (D-237)."""

    @model_validator(mode="after")
    def _check_exploration_search(self) -> ExplorationSearch:
        evaluated = [sorted(e.knobs.items()) for e in self.evaluations]
        if self.indices is not None:
            nearest = next((e for e in self.evaluations
                            if e.knobs == self.indices.knobs), None)
            if nearest is None or nearest.delta_aged != self.indices.delta_aged:
                raise ValueError(
                    f"indices du paquet {self.indices.knobs}, qui n'est pas un paquet "
                    f"évalué à cet écart : ils se liraient comme ceux d'un paquet chiffré.")
        for candidate in self.candidates:
            if candidate.robust is None or not candidate.verdict.strip():
                raise ValueError(
                    f"candidat {candidate.knobs} sans verdict θ : « robuste » ou « dépend "
                    f"de θ » est ce qui le rend lisible, et sans lui il se lirait robuste.")
            if sorted(candidate.knobs.items()) not in evaluated:
                raise ValueError(
                    f"candidat {candidate.knobs} absent des paquets évalués : un candidat "
                    f"dont on ne voit ni le coût ni les coins ne se vérifie pas.")
        for evaluation in self.evaluations:
            values = [value for _, value in evaluation.corners]
            if (evaluation.corner_low, evaluation.corner_high) != (min(values), max(values)):
                raise ValueError(
                    f"paquet {evaluation.knobs} : l'étendue affichée n'est pas celle de ses "
                    f"coins.")
        if not any(c.meets_target for c in self.candidates) and self.closest is None:
            raise ValueError(
                "aucun candidat et aucun paquet le plus proche : « aucun » se lirait sans "
                "dire à quelle distance de la cible la grille est restée.")
        return self


class ExplorationTransformation(BaseModel):
    """A named transformation the grid walked, with the law in force it read."""

    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    writes: list[str]
    year: int
    law: dict[str, Any]


class ExplorationHypotheses(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spending_name: str
    growth_name: str
    rate_name: str
    horizon: int
    target_year: int
    target_points: float
    target_share: float
    theta: dict[str, Any]
    uprating: dict[str, Any]
    behavioural: bool
    macro: bool
    looped: bool
    transformations: list[ExplorationTransformation] = Field(default_factory=list)


class ExplorationReport(BaseModel):
    """A search, precomputed by `impots exploration` (PHASE10_SPEC §2). Read from a file;
    never runs: a search is two population passes per bundle."""

    model_config = ConfigDict(extra="forbid")

    name: str
    titre: str
    question: str
    computed: str
    commit: str
    where: str | None = None
    """Where the passes ran (PHASE10_SPEC §5); absent from the reports before M4."""
    request: dict[str, Any]
    hypotheses: ExplorationHypotheses
    start: PredictifStart
    unit: str
    views: dict[str, str]
    conventions: list[str]
    banner: str
    debt_banner: str
    bundles: int
    passes: int
    searches: Annotated[list[ExplorationSearch], Field(min_length=1)]

    @model_validator(mode="after")
    def _check_exploration_report(self) -> ExplorationReport:
        if not self.commit.strip():
            raise ValueError(
                "rapport sans commit : il ne dirait pas quel code l'a produit, et ne se "
                "rejouerait pas.")
        persistences = [s.persistence for s in self.searches]
        if len(set(persistences)) != len(persistences) or (
                len(persistences) > 1 and None in persistences):
            raise ValueError(
                f"recherches sous {persistences} : deux recherches côte à côte sont les "
                f"deux scénarios de persistance, chacun une fois (D-230).")
        walked = sorted(b.get("knob") for b in self.request.get("bounds", [])
                        if b.get("knob") in TRANSFORMATIONS)
        named = sorted(t.name for t in self.hypotheses.transformations)
        if walked != named:
            raise ValueError(
                f"transformations {walked} parcourues, {named} nommées : une "
                f"transformation sans le droit qu'elle a lu ne se rejouerait pas, son "
                f"facteur ne disant pas de quoi.")
        for search in self.searches:
            if len(search.evaluations) != self.bundles:
                raise ValueError(
                    f"{len(search.evaluations)} paquets évalués pour {self.bundles} dans la "
                    f"grille : chaque paquet figure au rapport, pas seulement les candidats.")
        return self


class ExplorationReportList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explorations: list[str] = Field(default_factory=list)
