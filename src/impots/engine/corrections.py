"""Where this project's reading of the BENEFITS law, and of the abatement of art. 157 bis that
the income tax and the benefits both read (D-188), differs from openfisca's, and why.

The same bar as `patrimoine.corrections`, which holds the IFI ones: a legal citation, a
measured demonstration of the difference, a decision-log entry, and a KILL TEST that fails
the day openfisca changes its mind, at which point the correction must be removed rather
than kept as decoration. Applied to `engine.system.baseline()`, so every path, the
household calculator and the population alike, prices the same law.

---

**Correction 1 — the minimum deduction may not eat a pension (CGI art. 83, 3°), D-180.**

The housing aid counts « le total des revenus nets catégoriels retenus pour
l'établissement de l'impôt sur le revenu » (CCH art. R. 822-4). For salaries and
unemployment benefit, one category, the net is the gross less the 10 % deduction, whose
minimum (495 EUR on 2023 incomes) applies « sans pouvoir excéder le montant brut des
traitements et salaires ». openfisca's own income tax caps it so
(`revenu_assimile_salaire_apres_abattements` floors at zero).

`aide_logement_base_ressources_individu` does not. It nets the salaries first, floored
at zero, and carries what the deduction left over onto the unemployment line, NOT
floored: `chomage_imposable + min_(0, salaires - abattement)`. With no unemployment
benefit the line goes negative and is taken off the pension. Measured on a pensioner at
the ASPA level who rents (7 000 EUR of pension): 100 EUR of salary, 82.16 of it taxable
over the rolling year, lowered the base from 6 300 to 5 887.16 EUR and raised the housing
aid by 149.67 EUR a year, and the EMTR read -1.04.

The correction adds back exactly what that line took below zero, only under the
forfaitaire deduction: real expenses (frais réels) above the salaries leave a deficit in
the income tax too, and openfisca's treatment of them stands. Wrapped around openfisca's
own formula rather than copied, so everything else in it stays openfisca's.

Only the 2021 era is corrected. The 2018 one carries the same line, but no year this
project accepts reaches it (the API starts in 2022, the housing aid is read from
October N-1), and `update_variable` keeps openfisca's formulas before 2021 as they are.

**Blast radius, measured:** a salary under the minimum deduction, beside other income in
the family. The fixture population has no salary under 1 000 EUR, and nothing in it moves.
On the household path, the EMTR at zero salary of a housed pensioner (pensions of 7 000 to
15 000 EUR measured) went from -1.04 to 0.21.

---

**Correction 2 — the MVA goes to a full AAH or to one beside a pension (CSS art.
L. 821-1-2, 2°), D-184.**

The majoration pour la vie autonome goes to AAH recipients who « perçoivent l'allocation
aux adultes handicapés à taux plein ou en complément d'un avantage de vieillesse ou
d'invalidité ou d'une rente d'accident du travail ». `eligibilite_caah` asks only for an
AAH above zero. Measured with a renter at 80 %: 3 000 EUR a year of unemployment benefit
takes January's AAH to 936.37 EUR, which is neither, and openfisca still paid 104.77 EUR
of MVA every month, 1 257.24 over the year (D-182).

The correction keeps openfisca's test and adds the 2°: the AAH of the month at its full
amount, to the cent, or a retirement pension, an invalidity pension or an accident rent
that month. Wrapped around openfisca's formula. Its branch for ASI recipients stands,
because the article extends the MVA to them without the 2°. The approximation to state: an
AAH cut by a pension AND by another resource keeps the MVA.

**Blast radius:** an AAH reduced by something other than a pension or an accident rent,
in a dwelling with a housing aid, without professional income. On the wire, unemployment
benefit beside an AAH. The population carries no AAH, and nothing in it moves.

---

**Correction 3 — the age of 62 for AAH holders (CSS art. L. 821-2 and L. 351-1-5), D-185.**

The AAH between 50 and 79 % « prend fin à l'âge auquel le bénéficiaire est réputé inapte
au travail dans les conditions prévues au dixième alinéa de l'article L. 821-1 », and the
2023 reform « a maintenu à 62 ans l'âge de départ en retraite pour les titulaires de
l'AAH » (loi n° 2023-270, art. 11; Cnav-Cnaf circular 2024-1), who may claim the ASPA from
that age. openfisca reads both off `aah.age_legal_retraite`, which jumped to the general
legal age, 64, on 2023-09-01. So the AAH at 50-79 % ran two years too long, and the ASPA
of anyone with an incapacity over 50 % opened two years too late: at 62, 60 % without the
restriction on employment drew the RSA, 7 697.09 EUR of disposable income instead of the
ASPA's 12 144.27. The parameter is set back to 62 from that date, and the AAH's own test
made strict, since « prend fin à l'âge » is not « up to and including the age ».

**Correction 4 — the AAH without the ASPA (CSS art. L. 821-1), D-185.**

An AAH holder at 80 % or more « n'a pas l'obligation de demander l'Aspa pour continuer à
percevoir l'AAH » (circular 2024-1), since the AAH is open for want of an old-age benefit
« à l'exclusion de l'allocation de solidarité aux personnes âgées », and an ASPA that is
claimed may only be topped up to the AAH amount. openfisca paid both in full: at 80 %,
aged 66, with 3 000 EUR of pension, 9 058.56 EUR of AAH and 9 144.27 of ASPA, for 25 992.84
of disposable income against 16 848.57 at 60. The correction takes the CAF's default: an
AAH holder does not claim the ASPA. `aspa_eligibilite` leaves out whoever is eligible for
the AAH, which is read off the rate and the age, never off a benefit, so no circle opens.
The ASI keeps openfisca's age test (below the ASPA's age, art. L. 815-24) through the
original formula, since openfisca reads that age off the ASPA's eligibility.

**The approximations to state.** Someone born before 1955 still had to claim the ASPA,
with a differential AAH on top. The totals differ only where the ASPA's ceiling exceeds
the AAH amount, as from January to March 2024 (1 012.02 against 971.37 EUR a month). An
AAH holder with a pension above the AAH amount in such a month loses the small ASPA they
might claim. In a couple, the ASPA of the other spouse now counts the AAH as a resource,
as it does for a younger AAH holder (D-179). openfisca leaves it out when the AAH holder is
of ASPA age, citing a CNAV note of 1982 that this project has not been able to read.

**Blast radius:** a disability over 50 % from 62. On the wire, the disability field. The
population carries no disability, and nothing in it moves.

---

**Correction 5 — the high-rent taper spares an AAH beneficiary (CCH art. D. 823-16), D-187.**

The housing aid falls once the rent passes a threshold and is nil at a second one;
« Toutefois, cette diminution ne s'applique pas lorsque le demandeur ou son conjoint est
bénéficiaire de l'allocation aux adultes handicapés prévue à l'article L. 821-1 du code
de la sécurité sociale ou de l'allocation d'éducation de l'enfant handicapé prévue à
l'article L. 541-1 du même code ». openfisca lifts the taper on its generic `handicap`
flag instead, which this project never sets, since it also opens the ASI beside a
pension (D-184). Measured with a renter alone at 80 %, 1 300 EUR in zone 1: the rent was
above the threshold of suppression until the ceiling's revaluation in October 2024, then
tapered by a coefficient of 0.095, so 84.72 EUR of aid over the year against 4 026.60
untapered, and three months of MVA, 314.31 EUR, instead of 1 257.24.

The correction adds the article's own condition to openfisca's exceptions: the AAH paid
that month to a parent of the famille, the claimant or the spouse. Paid, not eligible:
a « bénéficiaire » is someone the AAH is paid to, and an AAH that a pension takes to zero
lifts nothing. A dependent's AAH lifts nothing either. The AEEH half of the sentence
needs nothing: openfisca pays the AEEH only for a child it flags `handicap`, and the flag
already lifts the taper. Wrapped around openfisca's formula, which stands for everyone
else; the aid untapered is its own, less the flat minoration that follows the taper. The
correction starts with openfisca's formula, in July 2016; the article quoted is the one
in force since September 2019, and no year this project accepts reads the aid before
October 2021.

**Blast radius:** an AAH beneficiary, or the spouse of one, whose rent passes the
threshold. On the wire, the disability field with a dwelling. The population carries no
AAH, and nothing in it moves.

---

**Correction 6 — the abatement of art. 157 bis, doubled for a couple (CGI art. 157 bis), D-188.**

Whoever is over 65 at the end of the year, or meets one of the invalidity conditions of
art. 195, deducts from the net income 2 796 EUR while it does not exceed 17 510 EUR, 1 398
up to 28 170 (2024 incomes), and « Dans le cas de personnes mariées soumises à une imposition
commune, la déduction prévue aux deuxième et troisième alinéas est doublée si les deux époux
remplissent les conditions d'âge ou d'invalidité ». `abat_spe` adds the two spouses'
eligibilities as numpy booleans, whose sum is a logical or: one abatement however many
qualified. Measured: two pensioners over 65 at 8 000 EUR each, 14 400 EUR of net income,
deducted 2 796 EUR instead of 5 592; two holders of the invalidity card the same.

The correction adds what the boolean sum drops, the second spouse's abatement when both
qualify, under openfisca's own cap at the net income. Wrapped around openfisca's formula,
whose eligibility it repeats only to count it: age or case P for the declarant, age or
case F for the spouse. The age is read on 1 January, where the article says 31 December;
with births on 1 January, as both builders write them, the two agree.

What it leaves: the ceilings. The article closes each bracket on the right (« si ce revenu
n'excède pas 17 510 € »), openfisca's scale opens the next one at the ceiling itself, so
exactly 17 510 EUR of net income gets 1 398 and exactly 28 170 nothing. But openfisca's net
income carries thousandths of a euro from the monthly inputs (31 300 EUR of pension makes
28 170.002), so a bracket closed on the right would only hold on an income rounded to the
euro, as the declaration has it: one euro wide, noted in D-188 and not corrected.

**Blast radius:** a couple both over 65 or invalid, under 28 170 EUR of net income. Its
income tax does not move, since a couple that poor owes none; its RFR does, and with it the
rate of the CSG on its replacement incomes two years on. On the wire, two adults over 65 or
two card holders. The population has such couples: on the fixture, the RFR of 2024 falls
by 1 398 EUR for 6 foyers of 439, that of 2022 by 1 310 for 2, and one ménage of 400 gains
113.11 EUR of disposable income, its pension's CRDS gone.

**Correction 7 — the same abatement in the benefits' resources (CCH art. R. 822-4, II, 2°),
D-188.**

The housing aid deducts « L'abattement mentionné à l'article 157 bis du code général des
impôts pour les personnes nées avant le 1er janvier 1931 et pour les personnes invalides »,
and the family benefits « L'abattement mentionné à l'article 157 bis du code général des
impôts en faveur des personnes âgées ou invalides » (CSS art. R. 532-3, b). openfisca reads
both off one copy, `abattements_speciaux_prestations_familiales`, on the incomes of N-2,
with the same boolean sum. Measured: two card holders at 10 000 EUR each were deducted
2 620 EUR (2022 incomes) instead of 5 240.

The correction counts the spouses as correction 6 does, under the copy's own criteria:
born before 1931, or case P or F. A card holder beside a spouse over 65 born after 1930
keeps one abatement here, where the income tax of the same year gives two. Two things
stand as openfisca has them: the age criterion, the housing aid's, which the copy applies
to the family benefits too, where the article says « personnes âgées »; and the ceilings,
as in correction 6. The copy's own test that the spouse exists read the declarant's age;
the correction reads the spouse's, which changes nothing for a couple.

**Blast radius:** two invalid spouses, or two born before 1931, under the ceiling, with a
housing aid or a family benefit. On the wire, two card holders. The population carries no
card, and on the fixture no couple born before 1931 sits under the ceiling: nothing moves.
"""

from __future__ import annotations

from typing import Any

from impots.patrimoine.corrections import Correction

CORRECTIONS: tuple[Correction, ...] = (
    Correction(
        name="aide_logement_deduction_forfaitaire_plafonnee",
        citation="CGI art. 83, 3° — la déduction de 10 % « ne peut être inférieure à "
                 "[un minimum] … sans pouvoir excéder le montant brut des traitements et "
                 "salaires » ; CCH art. R. 822-4 — l'aide au logement compte les revenus "
                 "nets catégoriels retenus pour l'impôt sur le revenu",
        decision="D-180",
        kill_test="test_the_engine_alone_lets_the_deduction_minimum_eat_a_pension",
    ),
    Correction(
        name="mva_aah_taux_plein_ou_complement",
        citation="CSS art. L. 821-1-2, 2° — la majoration pour la vie autonome va aux "
                 "bénéficiaires qui « perçoivent l'allocation aux adultes handicapés à taux "
                 "plein ou en complément d'un avantage de vieillesse ou d'invalidité ou "
                 "d'une rente d'accident du travail »",
        decision="D-184",
        kill_test="test_the_engine_alone_pays_the_mva_beside_an_aah_cut_by_unemployment_benefit",
    ),
    Correction(
        name="aah_age_inaptitude_62_ans",
        citation="CSS art. L. 821-2 — l'AAH entre 50 et 79 % « prend fin à l'âge auquel le "
                 "bénéficiaire est réputé inapte au travail », que l'art. L. 351-1-5 fixe à "
                 "62 ans pour les titulaires de l'AAH (loi n° 2023-270, art. 11), qui "
                 "peuvent demander l'ASPA dès cet âge",
        decision="D-185",
        kill_test="test_the_engine_alone_pays_the_aah_at_fifty_per_cent_until_64",
    ),
    Correction(
        name="aah_sans_aspa",
        citation="CSS art. L. 821-1 — l'AAH est ouverte faute d'un avantage de vieillesse "
                 "« à l'exclusion de l'allocation de solidarité aux personnes âgées », et "
                 "l'AAH et l'ASPA perçue ne peuvent ensemble « excéder le montant de "
                 "l'allocation aux adultes handicapés »",
        decision="D-185",
        kill_test="test_the_engine_alone_pays_the_aah_and_the_aspa_in_full_to_one_person",
    ),
    Correction(
        name="aide_logement_sans_degressivite_beneficiaire_aah",
        citation="CCH art. D. 823-16 — la dégressivité des loyers élevés « ne s'applique pas "
                 "lorsque le demandeur ou son conjoint est bénéficiaire de l'allocation aux "
                 "adultes handicapés prévue à l'article L. 821-1 du code de la sécurité "
                 "sociale »",
        decision="D-187",
        kill_test="test_the_engine_alone_tapers_the_aid_of_an_aah_beneficiary",
    ),
    Correction(
        name="abattement_157_bis_double_pour_un_couple",
        citation="CGI art. 157 bis — « Dans le cas de personnes mariées soumises à une "
                 "imposition commune, la déduction prévue aux deuxième et troisième alinéas "
                 "est doublée si les deux époux remplissent les conditions d'âge ou "
                 "d'invalidité »",
        decision="D-188",
        kill_test="test_the_engine_alone_abates_a_couple_once",
    ),
    Correction(
        name="abattement_157_bis_des_prestations_double_pour_un_couple",
        citation="CCH art. R. 822-4, II, 2° — sont déduits des ressources de l'aide au "
                 "logement « L'abattement mentionné à l'article 157 bis du code général des "
                 "impôts pour les personnes nées avant le 1er janvier 1931 et pour les "
                 "personnes invalides », que cet article double quand les deux époux "
                 "remplissent les conditions ; CSS art. R. 532-3, b), pour les prestations "
                 "familiales",
        decision="D-188",
        kill_test="test_the_engine_alone_takes_one_abatement_off_a_couple_s_benefit_resources",
    ),
)

AL_BASE = "aide_logement_base_ressources_individu"
AL_AMOUNT = "aide_logement_montant_brut"
MVA_ELIGIBILITY = "eligibilite_caah"
AAH_ELIGIBILITY = "aah_eligible"
ASPA_ELIGIBILITY = "aspa_eligibilite"
ASI_ELIGIBILITY = "asi_eligibilite"
#: The age openfisca reads both for the end of the AAH at 50-79 % and for the ASPA's
#: opening to anyone with an incapacity over 50 %.
AGE_AAH = ("prestations_sociales", "prestations_etat_de_sante", "invalidite", "aah",
           "age_legal_retraite")
#: Since the 2023 reform, the age at which an AAH holder is deemed unfit for work
#: (CSS art. L. 351-1-5), from the reform's entry into force.
AGE_INAPTITUDE = 62
AGE_INAPTITUDE_DEPUIS = "2023-09-01"
ABATEMENT_157_BIS = "abat_spe"
ABATEMENT_157_BIS_BENEFITS = "abattements_speciaux_prestations_familiales"
#: The age from which art. 157 bis abates, as openfisca's `abat_spe` reads it: on 1 January,
#: where the article says « au 31 décembre de l'année d'imposition », which births on
#: 1 January, as both builders write them, make the same.
AGE_157_BIS = 65
#: Born before this date, the housing aid deducts the abatement for age (CCH art. R. 822-4,
#: II, 2°), as openfisca's copy for the benefits reads it.
NE_AVANT_157_BIS_PRESTATIONS = "1931-01-01"


def apply_to(system: Any) -> Any:
    """Return `system` with the benefit corrections applied, as a Reform (the system handed
    in is untouched)."""
    from openfisca_core.reforms import Reform

    class BenefitCorrections(Reform):
        name = "impots-legal-corrections:prestations"

        def apply(self) -> None:
            openfisca_formula = self.get_variable(AL_BASE).get_formula("2021-01-01")
            self.update_variable(_capped_deduction_base(openfisca_formula))
            mva_formula = self.get_variable(MVA_ELIGIBILITY).get_formula("2015-07-01")
            self.update_variable(_mva_full_rate_or_complement(mva_formula))
            self.modify_parameters(modifier_function=_inaptitude_age)
            aah_formula = self.get_variable(AAH_ELIGIBILITY).get_formula("2011-01-01")
            self.update_variable(_aah_ends_at_the_inaptitude_age(aah_formula))
            aspa_formula = self.get_variable(ASPA_ELIGIBILITY).get_formula("0001-01-01")
            asi_formula = self.get_variable(ASI_ELIGIBILITY).get_formula("0001-01-01")
            self.update_variable(_aspa_not_claimed_beside_the_aah(aspa_formula))
            self.update_variable(_asi_below_the_aspa_age(asi_formula, aspa_formula))
            al_amount_formula = self.get_variable(AL_AMOUNT).get_formula("2016-07-01")
            self.update_variable(_no_taper_for_an_aah_beneficiary(al_amount_formula))
            abatement_formula = self.get_variable(ABATEMENT_157_BIS).get_formula("0001-01-01")
            self.update_variable(_abatement_157_bis_per_spouse(abatement_formula))
            benefits_formula = self.get_variable(ABATEMENT_157_BIS_BENEFITS).get_formula(
                "0001-01-01")
            self.update_variable(_benefits_abatement_157_bis_per_spouse(benefits_formula))

    return BenefitCorrections(system)


def _capped_deduction_base(openfisca_formula: Any) -> Any:
    """`aide_logement_base_ressources_individu`, with the forfaitaire deduction kept within
    the gross of the salary and unemployment category: openfisca's formula, plus what its
    unemployment line took below zero."""
    from openfisca_core.model_api import ADD, MONTH, Variable, max_, min_, round_
    from openfisca_core.periods import Period
    from openfisca_france.entities import Individu

    class aide_logement_base_ressources_individu(Variable):  # openfisca's naming
        value_type = float
        entity = Individu
        label = ("Base ressource individuelle des aides logement, déduction forfaitaire "
                 "plafonnée au brut des salaires (CGI art. 83, 3°)")
        definition_period = MONTH
        is_period_size_independent = True
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042159036"

        def formula_2021_01_01(individu, period, parameters):
            # The same quantities openfisca's formula reads, from the same periods.
            rolling = Period(("year", period.start, 1)).offset(-1).offset(-1, "month")
            salaires = (individu("salaire_imposable", rolling, options=[ADD])
                        + individu("f1tt", period.n_2) + individu("f3vj", period.n_2))
            chomage = individu("chomage_imposable", rolling, options=[ADD])
            deductions = parameters(period.last_year).impot_revenu.calcul_revenus_imposables.deductions
            forfait = round_(min_(max_(deductions.abatpro.taux * (salaires + chomage),
                                       deductions.abatpro.min), deductions.abatpro.max))
            forfaitaire = individu("frais_reels", period.last_year) <= forfait
            ligne_chomage = chomage + min_(0, (salaires - forfait) * ((salaires + chomage) > 0))
            pris_en_trop = max_(0, -ligne_chomage) * forfaitaire

            taux = parameters(period).prestations_sociales.aides_logement.allocations_logement \
                .ressources.abattements.chomage_indemnise
            abattement = individu("aide_logement_abattement_indemnites_chomage", period)
            neutralisation = individu("aide_logement_condition_neutralisation", period)
            return (openfisca_formula(individu, period, parameters)
                    + pris_en_trop * (1 - taux * abattement) * (1 - neutralisation))

    return aide_logement_base_ressources_individu


def _mva_full_rate_or_complement(openfisca_formula: Any) -> Any:
    """`eligibilite_caah`, with the 2° of CSS art. L. 821-1-2: openfisca's test, and an AAH
    at its full amount or beside an old-age benefit, an invalidity one or an accident
    rent. Recipients of the ASI keep openfisca's branch."""
    from openfisca_core.model_api import MONTH, Variable, set_input_dispatch_by_period
    from openfisca_france.entities import Individu

    class eligibilite_caah(Variable):  # openfisca's naming
        entity = Individu
        value_type = float
        label = ("Eligibilité aux compléments à l'aah : AAH à taux plein ou en complément "
                 "d'un avantage de vieillesse ou d'invalidité (CSS art. L. 821-1-2, 2°)")
        definition_period = MONTH
        set_input = set_input_dispatch_by_period

        def formula_2015_07_01(individu, period, parameters):
            montant = parameters(period).prestations_sociales.prestations_etat_de_sante \
                .invalidite.aah.montant
            taux_plein = individu("aah", period) >= montant - 0.01
            en_complement = (individu("retraite_brute", period)
                             + individu("pensions_invalidite", period)
                             + individu("rente_accident_travail", period)) > 0
            asi = individu("asi_eligibilite", period) * (individu("asi", period) > 0)
            return (openfisca_formula(individu, period, parameters)
                    * ((taux_plein + en_complement + asi) > 0))

    return eligibilite_caah


def _inaptitude_age(parameters: Any) -> Any:
    """`aah.age_legal_retraite` back to 62 from the 2023 reform: the age of L. 351-1-5,
    which its two readers mean, rather than the general legal age."""
    from impots.parameters import update_existing

    update_existing(parameters, AGE_AAH, start=AGE_INAPTITUDE_DEPUIS, value=AGE_INAPTITUDE,
                    instant=AGE_INAPTITUDE_DEPUIS)
    return parameters


def _aah_ends_at_the_inaptitude_age(openfisca_formula: Any) -> Any:
    """`aah_eligible`, with the AAH at 50-79 % ending AT the age, not after it."""
    from openfisca_core.model_api import MONTH, Variable, not_, set_input_dispatch_by_period
    from openfisca_france.entities import Individu

    class aah_eligible(Variable):  # openfisca's naming
        value_type = bool
        entity = Individu
        label = ("Eligibilité à l'AAH ; entre 50 et 79 %, jusqu'à l'âge où le bénéficiaire "
                 "est réputé inapte au travail (CSS art. L. 821-2)")
        definition_period = MONTH
        set_input = set_input_dispatch_by_period

        def formula_2011_01_01(individu, period, parameters):
            aah = parameters(period).prestations_sociales.prestations_etat_de_sante \
                .invalidite.aah
            fin = ((individu("taux_incapacite", period) < aah.taux_capacite.taux_incapacite)
                   * (individu("age", period) >= aah.age_legal_retraite))
            return openfisca_formula(individu, period, parameters) * not_(fin)

    return aah_eligible


def _aspa_not_claimed_beside_the_aah(openfisca_formula: Any) -> Any:
    """`aspa_eligibilite`, leaving out whoever is eligible for the AAH: an AAH holder does
    not claim the ASPA (circular Cnav-Cnaf 2024-1)."""
    from openfisca_core.model_api import MONTH, Variable, not_, set_input_dispatch_by_period
    from openfisca_france.entities import Individu

    class aspa_eligibilite(Variable):  # openfisca's naming
        value_type = bool
        entity = Individu
        label = ("Indicatrice individuelle d'éligibilité à l'ASPA, hors titulaires de l'AAH, "
                 "qui ne sont pas tenus de la demander (CSS art. L. 821-1)")
        definition_period = MONTH
        set_input = set_input_dispatch_by_period

        def formula(individu, period, parameters):
            return (openfisca_formula(individu, period, parameters)
                    * not_(individu("aah_eligible", period)))

    return aspa_eligibilite


def _asi_below_the_aspa_age(openfisca_formula: Any, aspa_formula: Any) -> Any:
    """`asi_eligibilite`, kept below the ASPA's age. openfisca reads that age off the ASPA's
    eligibility, which correction 4 narrows; the ASI reads openfisca's own instead."""
    from openfisca_core.model_api import MONTH, Variable, not_, set_input_dispatch_by_period
    from openfisca_france.entities import Individu

    class asi_eligibilite(Variable):  # openfisca's naming
        value_type = bool
        entity = Individu
        label = ("Indicatrice individuelle d'éligibilité à l'ASI, sous l'âge de l'ASPA "
                 "(CSS art. L. 815-24)")
        definition_period = MONTH
        set_input = set_input_dispatch_by_period

        def formula(individu, period, parameters):
            return (openfisca_formula(individu, period)
                    * not_(aspa_formula(individu, period, parameters)))

    return asi_eligibilite


def _no_taper_for_an_aah_beneficiary(openfisca_formula: Any) -> Any:
    """`aide_logement_montant_brut`, untapered when the claimant or the spouse is paid the
    AAH that month (CCH art. D. 823-16): openfisca's formula for everyone else."""
    from openfisca_core.model_api import (
        MONTH,
        Variable,
        max_,
        round_,
        set_input_divide_by_period,
        where,
    )
    from openfisca_france.entities import Famille

    class aide_logement_montant_brut(Variable):  # openfisca's naming
        value_type = float
        entity = Famille
        label = ("Montant des aides au logement après dégressivité et minoration forfaitaire, "
                 "avant CRDS ; sans dégressivité pour un bénéficiaire de l'AAH "
                 "(CCH art. D. 823-16)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000038878905"
        definition_period = MONTH
        set_input = set_input_divide_by_period

        def formula_2016_07_01(famille, period, parameters):
            beneficiaire = famille.any(famille.members("aah", period) > 0, role=Famille.PARENT)
            minoration = parameters(period).prestations_sociales.aides_logement \
                .allocations_logement.locatif.minoration_forfaitaire
            sans_degressivite = max_(0, round_(
                famille("aide_logement_montant_brut_avant_degressivite", period), 2) - minoration)
            return where(beneficiaire, sans_degressivite,
                         openfisca_formula(famille, period, parameters))

    return aide_logement_montant_brut


def _with_the_second_spouse(openfisca_value: Any, foyer_fiscal: Any, period: Any,
                            parameters: Any, both: Any) -> Any:
    """openfisca's abatement plus the second spouse's, when both qualify, under openfisca's
    own cap at the net income. openfisca's is `min_(rng, any × abatement + children)`, so
    adding one abatement and capping again gives `min_(rng, 2 × abatement + children)`."""
    from openfisca_core.model_api import min_

    rng = foyer_fiscal("rng", period)
    scale = parameters(period).impot_revenu.calcul_revenus_imposables.abat_rni \
        .contribuable_age_invalide
    return min_(rng, openfisca_value + both * scale.calc(rng))


def _abatement_157_bis_per_spouse(openfisca_formula: Any) -> Any:
    """`abat_spe`, with the abatement of CGI art. 157 bis doubled when both spouses are over
    65 or invalid: openfisca's formula, plus what its boolean sum drops."""
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class abat_spe(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = ("Abattements spéciaux ; celui des personnes âgées ou invalides doublé quand "
                 "les deux époux en remplissent les conditions (CGI art. 157 bis)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000047622555"
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            age_declarant = foyer_fiscal.declarant_principal("age", period.first_month)
            age_conjoint = foyer_fiscal.conjoint("age", period.first_month)
            declarant = (((age_declarant >= AGE_157_BIS) | foyer_fiscal("caseP", period))
                         & (age_declarant > 0))
            conjoint = (((age_conjoint >= AGE_157_BIS) | foyer_fiscal("caseF", period))
                        & (age_conjoint > 0))
            return _with_the_second_spouse(openfisca_formula(foyer_fiscal, period, parameters),
                                           foyer_fiscal, period, parameters, declarant * conjoint)

    return abat_spe


def _benefits_abatement_157_bis_per_spouse(openfisca_formula: Any) -> Any:
    """`abattements_speciaux_prestations_familiales`, the copy of the abatement the housing aid
    and the family benefits take off their resources, doubled when both spouses qualify
    under its own criteria, born before 1931 or invalid (CCH art. R. 822-4, II, 2°)."""
    from numpy import datetime64
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class abattements_speciaux_prestations_familiales(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = ("Abattements spéciaux des ressources des prestations ; celui de l'art. 157 bis "
                 "du CGI doublé quand les deux époux sont nés avant 1931 ou invalides "
                 "(CCH art. R. 822-4)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000045920163"
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            limite = datetime64(NE_AVANT_157_BIS_PRESTATIONS)
            mois = period.first_month
            declarant = (
                ((foyer_fiscal.declarant_principal("date_naissance", mois) < limite)
                 | foyer_fiscal("caseP", period))
                & (foyer_fiscal.declarant_principal("age", mois) > 0))
            conjoint = (
                ((foyer_fiscal.conjoint("date_naissance", mois) < limite)
                 | foyer_fiscal("caseF", period))
                & (foyer_fiscal.conjoint("age", mois) > 0))
            return _with_the_second_spouse(openfisca_formula(foyer_fiscal, period, parameters),
                                           foyer_fiscal, period, parameters, declarant * conjoint)

    return abattements_speciaux_prestations_familiales
