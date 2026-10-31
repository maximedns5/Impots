"""Where this project's reading of the BENEFITS law, of the abatement of art. 157 bis that the
income tax and the benefits both read (D-188), of the income tax on a benefit, the ASS
(D-192), of the home-help credit's ceiling (D-198, D-201), and of the caps of the quotient
familial beside a child in alternating residence (D-201) or a person in case R (D-202), differs
from openfisca's, and why.

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
with a differential AAH on top. For one person the totals differ only where the ASPA's
ceiling exceeds the AAH amount, as from January to March 2024 (1 012.02 against 971.37 EUR a
month). An AAH holder with a pension above the AAH amount in such a month loses the small
ASPA they might claim. In a couple, the ASPA of the other spouse now counts the AAH as a
resource, as it does for a younger AAH holder (D-179). openfisca left it out when the AAH
holder was of ASPA age, citing a ministerial letter of 1982; D-200 read it, and the Cnav's
rule turns on the AAH holder's pension, not on the age (correction 16).

**Claiming, in a couple (D-203).** From the generation that reached the age in 2017, the
claim is the household's (loi n° 2016-1917, art. 87, VI), and the engine keeps the CAF's
default. In a couple it weighs: claimed, the ASPA leaves out the AAH « du demandeur » and is
the couple's, served by halves, which the AAH tops up. By hand, D-185's couple would have
23 985.57 EUR of disposable income against 18 943.38; with 3 000 EUR of pension, 22 485.57
against 27 912.58. Where the AAH holder, born before 1955, had to claim, the engine's figure
for a couple is not a near one.

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

---

**Correction 8 — the ASS counts the spouse's unemployment benefit, whoever heads the famille
(C. trav. art. R. 5423-2), D-189.**

The ASS's resources comprise « l'allocation de solidarité ainsi que les autres ressources de
l'intéressé et, le cas échéant, de son conjoint ». openfisca reads one base per famille: the
first parent's own resources, plus the second parent's own resources AND unemployment
benefit (`ass_base_ressources_conjoint`). A claimant who is the famille's second parent saw
the first one's benefit vanish. Measured with 24 000 EUR of gross benefit beside a claimant
without resources: the ASS was 1 263.50 EUR over 2024 with the claimant first, and the full
6 768 with the claimant second; June's, 126.31 against 570.30.

The correction adds openfisca's own term, read on the first parent: the benefit of the
twelve months before, unless it stopped last month. Only when the first parent does not
hold the ASS's work condition: a claimant's own past benefit is not a resource (art.
R. 5423-3, 1°), which openfisca's base already has for the first parent. Wrapped around
openfisca's formula. Like openfisca, it counts the benefit net of its CSG and CRDS where the
article reads the amounts « telles qu'elles doivent être déclarées », and leaves the first
parent's daily sickness allowances out, which no field carries.

**Blast radius:** a couple whose first adult draws unemployment benefit beside a second in
« fin de droits ». On the wire, the unemployment benefit field beside the « fin de droits »
one. The population declares nobody in « fin de droits », and nothing in it moves.

---

**Correction 9 — the invalidity pension bears the levies of a pension (CSS art. L. 136-8 and
L. 137-41), D-190.**

« Sont assujetties à la contribution au taux de 8,3 % les pensions de retraite, et les
pensions d'invalidité » (art. L. 136-8, II), the intermediate and reduced rates following
the same RFR bands, and the CASA is « assise sur les avantages de retraite et d'invalidité »
(art. L. 137-41). openfisca levies the retirement pension only: `pensions_nettes` adds
`pensions_invalidite` whole, so the disposable income kept the whole declared amount.
Measured on a pensioner alone at 44: 28 412 EUR of disposable income on 30 000 EUR declared,
against 27 452 for the same retirement pension; 19 850 against 19 210 on 20 000; 15 000
against 14 925 on 15 000, where the reduced rate leaves only the CRDS to take.

The correction reads openfisca's own levies on a retirement pension, the CSG imposable, the
CRDS and the CASA at the rate the RFR of N-2 sets, on the invalidity pension instead, and
takes them off `pensions_nettes`. The deductible CSG stays out: the field is the declared
amount, already net of it, as the retirement pension's is (D-176), and their base is that
declared amount, about 6 % under the gross one, as for the retirement pension. Wrapped
around openfisca's formulas, which stand for the retirement pension, from 2019, the date of
the levy formulas it wraps.

**Blast radius:** an invalidity pension whose foyer's RFR of N-2 passes the exemption
threshold. On the wire, the invalidity pension field. The population carries no invalidity
pension, and nothing in it moves.

**Correction 10 — the ASI of a lone beneficiary in a couple (CSS art. D. 815-19, 2° b),
D-190.**

The ASI is the ceiling less the resources (art. L. 815-24-1), the couple's ceiling for a
couple. When the spouse « n'est pas bénéficiaire de l'allocation supplémentaire
d'invalidité », « le montant de l'allocation servie ne peut excéder le montant du plafond
mentionné au 1° auquel est soustrait le montant minimum de la pension d'invalidité mentionné
à l'article L. 341-5 » (art. D. 815-19, 2° b); the Cnav applies it when the spouse draws
neither the ASI nor the ASPA, the ASPA being the 2° c) (circulars 2022-22 to 2025-30).
openfisca pays the couple ceiling less the couple's resources. Measured on 6 000 EUR of
invalidity pension beside a spouse without income: 1 074.24 EUR a month from April 2024
against a cap of 571.50, and 12 683.20 EUR of ASI over 2024 against 6 739.27.

The correction caps openfisca's amount, for a parent of a couple whose famille counts one
allocataire of the ASI or the ASPA, at the month's single ceiling less the minimum
invalidity pension in force. openfisca's tree has no minimum invalidity pension:
`PENSION_INVALIDITE_MINIMUM` carries it, as the Cnav circulars give it, revalued each
1 January since 2023. Wrapped around openfisca's formula, from April 2020, when the ASI
became the ceiling less the resources.

**Blast radius:** a couple where one spouse draws the ASI and the other neither the ASI nor
the ASPA, with resources low enough for the cap to bind. On the wire, the invalidity pension
field in a couple. The population carries no invalidity pension, and nothing in it moves.

---

**Correction 11 — each AEEH complément at its own category's rate (CSS art. D. 541-2), D-191.**

The AEEH's complément goes by the category the CDAPH grants (art. R. 541-2), each at its
own share of the BMAF: « Le taux du complément de deuxième catégorie de l'allocation
d'éducation de l'enfant handicapé est fixé à 65 % de la base mensuelle de calcul des
allocations familiales », 92 % for the third, 142.57 % for the fourth, 182.21 % for the
fifth. openfisca pays the second to the fifth category the complément of the category below
(its parameters are right, its formula reads the wrong one): measured on a couple's child
at 80 % in 2024, 3 100.02 EUR for the second category, the first's amount, instead of
5 369.68; 6 864.33 for the fourth instead of 9 663.76. The first and sixth categories, the
base and the lone parent's majoration are right.

The correction adds what is missing, 41 %, 27 %, 50.57 % and 39.64 % of the BMAF for the
second to the fifth category, wherever openfisca's own test opens the AEEH: its `handicap`
flag, under the age of 20. Wrapped around openfisca's formula, which stands for the rest.

Not corrected, and unreachable: openfisca adds the sixth category's complément outside that
test, so a child of 20, or one without the flag, would draw it alone. The builder writes a
category only with the flag, and refuses a complément from 20 (D-191, D-202).

**Blast radius:** a child with a complément of the second to the fifth category. On the
wire, the child's disability field. The population carries no disability, and nothing in it
moves.

---

**Correction 12 — the ASS is taxed as a salary (C. trav. art. L. 5428-1; CGI art. 158, 5),
D-192.**

To the allocations France Travail pays, and to the ASS, « Les règles fixées au 5 de l'article
158 du code général des impôts sont applicables » (C. trav. art. L. 5428-1): the ASS « est
imposable entre les mains des bénéficiaires dans la catégorie des traitements et salaires »
(BOI-RSA-CHAMP-20-20, § 20), declared in box 1AP with the unemployment benefit, after the 10 %
deduction of CGI art. 83, 3°, which « s'applique séparément aux rémunérations perçues par
chaque membre du foyer fiscal ». It bears no CSG (CSS art. L. 136-1-2, II, 5°), and so no CRDS.
openfisca's `ass` enters no income-tax variable. Measured in 2024 on a claimant alone without
resources: 6 768 EUR of ASS and an RFR of 0, where the law gives 6 768 - 677 = 6 091. Beside a
spouse's 15 000 EUR of declared pension, the RFR of N-2 was 13 500 instead of 19 163.80, and
the pension of N went unlevied where the reduced rate takes 75 EUR of CRDS.

The correction puts the ASS of the year among each member's salaries in
`revenu_categoriel_tspr`, where the income tax sums the categories: openfisca's own deduction
formula, run on the member's salaries and ASS together, less the same formula on the salaries
alone. A member's salaries, unemployment benefit and ASS thus share one deduction and one
minimum. Not earlier in the chain: `revenu_assimile_salaire_apres_abattements` and
`traitements_salaires_pensions_rentes` are also read by the family benefits on N-2, for their
resources, where CSS art. R. 532-7 leaves out the « indemnités de chômage » of a person
admitted to the ASS, and for their test of `biactivite`, where the ASS is no professional
income. Nor in `chomage_imposable`, which the ASS's own eligibility reads through
`chomage_net`, and on which openfisca levies the CSG and CRDS the ASS does not bear. The housing
aid reads none of them since 2021. Wrapped around openfisca's formulas.

What it leaves: the IFI's cap on income and the ceiling of the union-dues credit read the
salaries before this category, and do not see the ASS (D-192).

Read only when someone in the simulation meets `ass_precondition_remplie` in the year, without
which the ASS is nil: the RFR of a simulation without a claimant, the population's and every
light tier's but a claimant's, computes neither the ASS nor the AAH and ASI its eligibility
reads.

**Blast radius:** a household with a claimant in « fin de droits ». Its income tax does not
move: under the ASS's ceilings, the 0 % bracket and the décote leave none. Its RFR does, and
with the RFR of N-2, the rate of the CSG on the household's other replacement incomes. Its
light tier now computes the ASS, and the AAH and the ASI its eligibility reads, but none of
the benefits the ASS tops up. The population declares no one in « fin de droits », and
nothing in it moves.

---

**Correction 13 — the ASI beside a spouse at the ASPA (CSS art. D. 815-19, 2° c), D-194.**

When the spouse « bénéficie de l'allocation de solidarité aux personnes âgées visée à
l'article L. 815-1 », « le montant de l'allocation servie est égal à la différence entre la
moitié du plafond mentionné au 2° et la moitié des ressources du couple » (art. D. 815-19,
2° c, since April 2020); the plafond of the 2° is the ASI's couple ceiling. openfisca prices
that case against the ASPA's couple ceiling instead, then pays the ASI only to one
allocataire or to two at the ASI: beside a spouse at the ASPA, nothing. Measured on 6 000 EUR
of invalidity pension beside a spouse of 66 with 3 000 EUR of retirement pension: no ASI
over 2024, against 4 841.60 EUR, 412.12 a month from April.

The correction pays a parent eligible to the ASI, whose spouse is eligible to the ASPA, half
the ASI's couple ceiling less half the couple's resources, on openfisca's own base. Wrapped
around correction 10's formula, itself around openfisca's, which stand for every other case:
`apply` wraps the `asi` that correction 10 left, so both hold. The two never meet, since
correction 10 needs one allocataire in the famille and this one two. From April 2020, like
the c).

**Correction 14 — the ASPA beside a spouse at the ASI (CSS art. D. 815-1), D-194.**

The couple's maximum « est servi par moitié à chacun des deux allocataires concernés », and
« Les dispositions du b sont également applicables pour le calcul de l'allocation de
solidarité aux personnes âgées servie au demandeur lorsque son conjoint [...] bénéficie de
l'allocation supplémentaire d'invalidité » (art. D. 815-1, in force since April 2018); the
allowance is reduced « à due concurrence » of what it and the resources pass the couple's
ceiling by (art. L. 815-9 and D. 815-2). openfisca prices that case as before April 2020,
when the ASI took its own half of a shared excess: half the couple maximum, less half of
what the resources and the ASI pass half the ceiling by. With no ASI to take the other half,
measured on the couple above: 9 427.01 EUR of ASPA over 2024 against 4 927.01, and 4 140.52
EUR to a couple whose 20 000 EUR pass both ceilings, against nothing. Correction 13 alone
would not mend it. The ASI the formula adds is the demandeur's if `maries`, the conjoint's
otherwise (neither builder sets `statut_marital`), and it divides that monthly amount by
twelve with the annual maximum: fed correction 13's ASI, the couple above still drew 9 427.01
EUR, whichever spouse heads the famille (measured).

The correction pays the famille half of the couple's ASPA as two beneficiaries draw it, the
couple's maximum less what it and the resources pass the couple's ceiling by, on openfisca's
own base: 410.58 EUR a month above. Neither allowance counts the other, so the couple ends at
half of each ceiling, whatever its resources below them. Wrapped around openfisca's formula,
which stands for every other famille. From April 2020, the date of openfisca's formula and
of the c).

**Blast radius, of both:** a couple where one spouse is eligible to the ASI and the other to
the ASPA. On the wire, the invalidity pension field beside a spouse at the ASPA's age, from 65,
or from 62 for an invalidity pensioner or an incapacity over 50 %. The population carries no
invalidity pension, and nothing in it moves.

---

**Correction 15 — the home-help ceiling raised for each member over 65 (CGI art. 199 sexdecies,
3), D-198.**

« La limite de 12 000 € est majorée de 1 500 € par enfant à charge au sens des articles 196 et
196 B et au titre de chacun des membres du foyer fiscal âgé de plus de soixante-cinq ans », up to
15 000 EUR, and the first year's limit of 15 000 EUR « fait l'objet des majorations prévues au
présent alinéa », up to 18 000. The DGFiP reads the age « au 31 décembre ou à la date du décès »
(Brochure pratique 2025): a member counts from the year they turn 65. openfisca's `ci_saldom`
raises its ceilings for the dependants (`nb_pac2`) and the ascendants of case 7DL only, as the
docstring of its 2011 formula says. Measured on two pensioners born in 1954 and 1955 declaring
18 000 EUR of home help: 6 000 EUR of credit over 2024, against the 7 500 the DGFiP's simulator
gives.

The correction runs openfisca's formula with the declarants of 65 or more on 31 December among
the persons it counts, so the increment, both caps, the first year and the 20 000 EUR of case
7DG, which takes no increment, stay openfisca's, read from the tree a reform moves. The
declarants only: a dependant already counts once in `nb_pac2`, as the DGFiP's simulator counts
a dependent child born in 1950 once. A person in case R, which `nb_pac2` also counts (`nbR`)
and the simulator does not, comes with the card, so with case 7DG, which takes no increment
(D-202). The age is read off `date_naissance`, so a birth on 31 December
counts; with births on 1 January, as both builders write them, it is the year of birth. Wrapped
from 2020, the date of openfisca's formula; no year this project accepts reads an earlier one.

**Blast radius:** a foyer with a declarant of 65 or more on 31 December whose home help, less the
aid received, passes 12 000 EUR (15 000 the first year), without case 7DG. On the wire, the
home-help field beside an adult born 65 years or more before the year simulated. The population
declares no home help unless it imputes it, and its imputed bases are decile means, 3 759.31 EUR
at most on 2024 incomes: nothing in it moves.

---

**Correction 16 — the AAH of a pensioner left out of a spouse's minimum (CSS art. R. 815-22;
ministerial letter of 19 March 1982), D-200.**

The ASPA counts « tous les avantages d'invalidité et de vieillesse dont bénéficie l'intéressé,
des revenus professionnels et autres », « indépendamment des ressources exclues par des
dispositions particulières » (art. R. 815-22), the spouses' totalled (art. R. 815-27); the ASI's
resources are the same (art. R. 815-61). The article's list has no AAH. The ministerial letter
of 19 March 1982 holds that the AAH « ne doit donc pas être exclue des ressources », then
tempers it by the AAH's subsidiarity: « il peut être fait abstraction de l'allocation aux
adultes handicapés à taux différentiel dont bénéficient les titulaires d'un avantage de
vieillesse ou d'invalidité ». Circular Cnav 2007/15 kept it for the ASPA, and the Cnav's list
of the resources the ASPA excludes names the « Allocation aux adultes handicapés (AAH et ses
compléments) du demandeur » and the « AAH (et ses compléments) du conjoint, concubin ou pacsé
s'il est titulaire d'un avantage de vieillesse ou d'invalidité »; its list for the ASI says the
same. The line is the pension, not the age.

openfisca leaves out the AAH of whoever is eligible to the ASPA or the ASI, or draws an
invalidity pension: the age, then, and not the retirement pension. Since correction 4 an AAH
holder is never eligible to the ASPA, so the AAH of a retirement pensioner counted at every
age; raw openfisca counted it below 64. Measured beside a spouse of 70 with 5 000 EUR of
pension, an AAH holder at 80 % with 3 000 EUR of pension: 1 451.69 EUR of ASPA over 2024
instead of 10 854.02, and 18 510.25 EUR of disposable income instead of 27 912.58.

The correction takes off openfisca's base the AAH its formula counted, for whoever draws a
retirement pension that month: openfisca's own tests, from the same periods, and the base
otherwise its own. Without a pension the AAH counts, at any age: D-185's couple keeps its
18 943.38 EUR.

What it leaves: the compléments, which the lists treat as the AAH, are correction 21's. And the
line itself: the first euro of pension takes the AAH out of the spouse's resources, 29 202.83
EUR of disposable income with 100 EUR of pension against 18 943.38 without (D-200).

**Blast radius:** a couple where one spouse draws the AAH and a retirement pension, and the
other is eligible to the ASPA or the ASI. On the wire, the disability field with a pension,
beside a spouse at the ASPA's age or with an invalidity pension. The population carries no
disability, and nothing in it moves.

---

**Correction 17 — the home-help increment halved, not taken off, for a child in alternating
residence (CGI art. 199 sexdecies, 3), D-201.**

« Le montant de 1 500 € est divisé par deux pour les enfants réputés à charge égale de l'un et
l'autre de leurs parents »: 750 EUR more for each such child, under the same caps. openfisca's
`nb_pac2` is `nbF + nbJ + nbR - nbH / 2`, labelled as counting « les enfants en résidence
alternée comme une demi personne à charge »; but `nbF` already leaves them out, so each one takes
half an increment off the ceiling instead of adding it. Measured on a parent alone at 40 000 EUR
with one such child, declaring 18 000 EUR of home help: 5 625 EUR of credit over 2024, against
the 6 375 the DGFiP's simulator gives.

The correction runs the formula correction 15 left, itself around openfisca's, with each child in
alternating residence counted once more among the persons the ceilings are raised for: `nbH` in
full, which turns the half taken off into the half the article adds. Composed with correction 15
rather than merged into it, so that each can be retired on its own kill test. The increment, both
caps, the first year and the 20 000 EUR of case 7DG without increment stay openfisca's.

**Blast radius:** a foyer with a child in alternating residence whose home help, less the aid
received, passes 12 000 EUR (15 000 the first year), without case 7DG. On the wire, the child's
alternating residence beside the home-help field. The population carries no alternating
residence, and nothing in it moves.

---

**Correction 18 — the caps of the quotient familial beside a child in alternating residence
(CGI art. 197, I, 2), D-201.**

Two of openfisca's readings in `ir_plaf_qf` that a child in alternating residence exposes.

The widow's reduction: « Les contribuables veufs ayant des enfants à charge qui bénéficient d'une
part supplémentaire de quotient familial en application du I de l'article 194 ont droit à une
réduction d'impôt égale à 1 993 € pour cette part supplémentaire », and a shared child is at
charge, « que celle-ci soit exclusive, principale ou réputée également partagée entre les
parents » (art. 196). openfisca gives the reduction where `nb_pac` is positive, which leaves the
shared children out: a widow whose only child is shared paid 25 237.45 EUR at 150 000 EUR,
against 23 244.45 and the DGFiP simulator's 23 244.

Case T's half ceilings: « Lorsque les contribuables entretiennent uniquement des enfants dont la
charge est réputée également partagée entre l'un et l'autre des parents, la réduction d'impôt
correspondant à la demi-part accordée au titre de chacun des deux premiers enfants est limitée à
la moitié de cette somme », of 4 224 EUR. openfisca caps the first two half-parts above one part
at 2 112 EUR each, whatever they are. With one child, shared, the second is a card's, the
parent's, capped at 1 791 EUR, or the child's quarter, at 895.50: a parent alone with the card
paid 23 705.95 EUR at 150 000 EUR, against 24 026.95 and the simulator's 24 027.

The correction runs openfisca's formula of 2013 with `nb_pac` counting the shared children too,
which only the widow's reduction and case L's ceiling read there, and which a shared child closes
as the law does (art. 195, 1: « n'ayant pas d'enfant à leur charge, exclusive, principale ou
réputée également partagée »). And, for a lone parent of case T whose only child is shared, with
the tax on one part raised by what openfisca's caps give too much: (min((parts - 1) x 2, 2) - 1)
x (half of 4 224 - 1 791), read from the tree a reform moves. Raising that tax by the sum is
lowering the caps by it: the capped tax, the complements the cap limits and the DOM's abatement
follow from openfisca's own formula. Two shared children fill the two half-parts with theirs, and
nothing changes there.

**Blast radius:** a widow whose children are all shared, or a parent of case T with one child,
shared, beside the card, the parent's or the child's, whose quotient is capped. On the wire, the
child's alternating residence beside a widow's situation or a card. The population carries no
alternating residence, and nothing in it moves.

---

**Correction 19 — no ASF for a child in alternating residence (CSS art. L. 523-1, I, 3°),
D-201.**

The ASF goes to « tout enfant dont le père ou la mère, ou les père et mère, se soustraient ou se
trouvent [...] hors d'état de faire face à leurs obligations d'entretien », the parent having
done so « depuis au moins un mois » (art. R. 523-1). Where parents have « un droit de résidence
alternée sur leur enfant qui est mis en oeuvre de manière effective et équivalente, l'un et
l'autre des parents doivent être considérés comme assumant la charge effective et permanente de
leur enfant » (Cour de cassation, avis n° 006 0005 of 26 June 2006, as the minister quotes it in
answer to written question n° 14550): the other parent maintains the child. openfisca's `asf_elig_enfant` never reads `garde_alternee`, and paid a
parent alone at 15 000 EUR 2 336.09 EUR of ASF over 2024 for one shared child.

The correction keeps openfisca's eligibility and leaves the shared child out; the RSA's ASF
forfait reads the same eligibility, and follows. What it leaves: a contribution ordered beside
the alternating residence and left unpaid (3°), or paid below the ASF (4°), would open it, and
the wire format carries neither.

**Blast radius:** a parent alone with a shared child under 20. On the wire, the child's
alternating residence beside a single adult. The population carries none, and nothing in it
moves.

---

**Correction 20 — the first child's ceiling only beside a child (CGI art. 197, I, 2), D-202.**

The reduction the quotient familial brings is capped at 1 791 EUR a half-part on 2024 incomes,
and for single or divorced taxpayers who meet the conditions of art. 194, II, case T, « la
réduction d'impôt correspondant à la part accordée au titre du premier enfant à charge est
limitée » to 4 224 EUR. A lone adult claims case T for a person in case R, whom the 2042 names
beside the children, but then has no first child's part: « les contribuables célibataires ou
divorcés qui vivent seuls et supportent effectivement la charge d'une personne mentionnée à
l'article 196 A bis du CGI, à l'exclusion de tout enfant, ne sont pas concernés par le
plafonnement spécifique correspondant à la part accordée au titre du premier enfant à charge »
(BOI-IR-LIQ-10-10-10-30, § 55). openfisca's `ir_plaf_qf` gives the 4 224 EUR to every single or
divorced taxpayer with case T. Measured on a lone adult with case T and one person in case R:
21 914.95 EUR before reductions at 150 000 EUR, where the DGFiP's simulator gives 22 557, and
3 362.08 at 80 000 EUR, where it gives 3 800.

The correction runs openfisca's formula with case T read only where a child is at charge,
exclusively, mainly or alternately. The parts, which `nbptr` computes with case T, stay
openfisca's, and so does every ceiling of a foyer with a child: only the first child's ceiling
of a foyer without one gives way to the general one. Wrapped from 2013, the date of the formula
in force since; before it, openfisca's stands.

**Blast radius:** a lone adult with case T whose only dependants are persons in case R, with an
income for which the ceiling binds. On the wire, the case R field beside one adult. The
population writes no case R, and nothing in it moves.

---

**Correction 21 — the AAH's compléments counted as the AAH in a spouse's minimum (CSS art.
R. 815-22; the Cnav's lists), D-203.**

The ASPA counts « tous les avantages d'invalidité et de vieillesse dont bénéficie l'intéressé, des
revenus professionnels et autres » (art. R. 815-22), whose list of exclusions has neither the AAH
nor its compléments. The Cnav's list of the resources the ASPA excludes names the « Compléments
d'allocation aux adultes handicapés (AAH) du demandeur : complément de ressources (CRH) et
majoration pour la vie autonome (MVA) » and the « Compléments d'AAH du conjoint, concubin ou
partenaire pacsé s'il est titulaire d'un avantage de vieillesse ou d'invalidité », as it names
the AAH (correction 16); its list for the ASI says the same. A pensionless spouse's MVA counts.
openfisca's base counts the AAH and never reads `caah`. Measured on D-185's couple renting at 500
EUR in zone 2, the AAH holder drawing the MVA, 104.77 EUR a month: 1 884.82 EUR of ASPA over 2024
instead of 627.58; beside an invalidity pensioner at 6 000 EUR, 714.00 EUR of ASI instead of
nothing.

The correction adds the compléments of the three months before, as openfisca reads the AAH,
under the tests the AAH counts under: openfisca's (neither minimum, no invalidity pension) and
correction 16's (no retirement pension). Wrapped around correction 16's formula. It reads `caah`
only where it can count: a parent with an incapacity of 80 % or more, without which there is no
MVA (art. L. 821-1-2), who passes those tests beside a parent eligible to the ASPA or the ASI.
Elsewhere the term is nil, and the population, which writes no disability, never reads it.

**The circle.** The MVA reads the housing aid of its month, and the housing aid reaches the ASPA
and the ASI of its month through its student-grant test and the RSA's resources (D-179). The pin
of D-178 kept `aide_logement`, not the amount the MVA reads: each month's amount was purged at
the end of its own pin, invalidated by a spiral beneath it, and met again under the next month's
pin it was cut to zero by openfisca's spiral guard. Beside the invalidity pensioner, the ASI of
January, computed during January's pin on December's MVA cut so, stayed in the cache: 714.00 EUR
in both evaluation orders, where a simulation without the pin gives nothing. So
`situations.pin_benefit_history` pins `aide_logement_montant` too, and every figure agrees, by
hand and in both orders.

**Blast radius:** a couple where one spouse draws the AAH at 80 % or more without a pension, in
a dwelling with a housing aid, and the other is eligible to the ASPA or the ASI. On the wire, the
disability field without a pension, beside a spouse at the ASPA's age or with an invalidity
pension, with a dwelling. The population carries no disability, and nothing in it moves.

---

**Correction 22 — sick pay is taxed as a salary (CGI art. 80 quinquies and 81, 8°), D-306.**

The law, as the PLF 2027's own fiche states it (annex, art. 2, pp. 18 and 20): the daily
allowances of the sickness insurance are taxable « au même titre que le complément de salaire
versé par l'employeur », except those of an « affection comportant un traitement prolongé et
une thérapeutique particulièrement coûteuse » (art. 80 quinquies); those of a work accident or
an occupational disease have been « exonérées d'IR à hauteur de 50 % de leur montant, en
application du 8° de l'article 81 du CGI » since the finance law for 2010. openfisca taxes
none of them: no allowance reaches `revenu_assimile_salaire`, and
`indemnites_journalieres_imposables` is read by the AAH alone.

The correction adds, to each member's salaries, the sickness allowances and the taxable share
of the work-accident ones, net of their deductible CSG, through openfisca's own deduction, as
correction 12 does with the ASS. The exempt share is a parameter this project brings into the
tree, `impot_revenu.indemnites_journalieres.part_exoneree_at_mp` (0,5 from 2010), so that a
knob can move it.

**The ALD exemption, since D-312.** The sickness allowances of a person in ALD, in the sense of
the 3° and 4° of CSS art. L. 160-14, are exempt (art. 80 quinquies). openfisca has no variable
for them: the correction adds one, `indemnites_journalieres_maladie_ald`, the part of
`indemnites_journalieres_maladie` served for an ALD, an input that `population.ij` writes (33 %
of each person's sickness allowances, the share of the days the PLFSS 2026's annex gives for
2024). Its exempt share is a second parameter, `part_exoneree_ald`, 1 since the exemption's
creation in 1978 (Voies et moyens 2026, dépense 120204), so that the PLF 2027's halving is a
knob. Before D-312 every sickness allowance was taxed, and the income tax of a population that
carried them was too high by what that exemption costs.

---

**Correction 23 — the CSG on sick pay, and sick pay among the replacement incomes (CSS art.
L. 136-8), D-306.**

openfisca carries the rate, `csg.remplacement.indemnites_journalieres.taux_global` (6,2 %),
and nothing that levies it: « TODO: manque CSG sur IJ » (`csg_crds.py`). The correction adds
`csg_indemnites_journalieres`, the rate on the sickness and work-accident allowances of the
month, negative as openfisca's levies are. Maternity and paternity allowances are left out:
the population carries none, and the PLF 2027's measure does not move them. Nor is the CRDS
levied on them. Then `pensions_nettes`, openfisca's « pensions et revenus de remplacement »,
gains the allowances net of that CSG, so that they are in the disposable income and a change
of their rate or of their tax shows in it. Wrapped around correction 7's formula.

**Blast radius of both:** a person with a daily allowance. The wire carries none; the
population carries them only when `impute_ij` runs (D-305). Elsewhere nothing moves.
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
    Correction(
        name="ass_chomage_du_conjoint_premier_parent",
        citation="C. trav. art. R. 5423-2 — les ressources de l'ASS « comprennent "
                 "l'allocation de solidarité ainsi que les autres ressources de l'intéressé "
                 "et, le cas échéant, de son conjoint, partenaire lié par un pacte civil de "
                 "solidarité ou concubin »",
        decision="D-189",
        kill_test="test_the_engine_alone_ignores_the_unemployment_benefit_of_a_spouse_heading_"
                  "the_famille",
    ),
    Correction(
        name="pension_invalidite_prelevements",
        citation="CSS art. L. 136-8, II — « Sont assujetties à la contribution au taux de 8,3 % "
                 "les pensions de retraite, et les pensions d'invalidité » ; art. L. 137-41 — la "
                 "CASA est « assise sur les avantages de retraite et d'invalidité »",
        decision="D-190",
        kill_test="test_the_engine_alone_levies_nothing_on_an_invalidity_pension",
    ),
    Correction(
        name="asi_seul_allocataire_du_couple",
        citation="CSS art. D. 815-19, 2° b) — quand le conjoint n'est pas bénéficiaire de l'ASI, "
                 "« le montant de l'allocation servie ne peut excéder le montant du plafond "
                 "mentionné au 1° auquel est soustrait le montant minimum de la pension "
                 "d'invalidité mentionné à l'article L. 341-5 »",
        decision="D-190",
        kill_test="test_the_engine_alone_pays_a_lone_beneficiary_in_a_couple_the_couple_ceiling",
    ),
    Correction(
        name="aeeh_complement_au_taux_de_sa_categorie",
        citation="CSS art. D. 541-2 — « Le taux du complément de deuxième catégorie de "
                 "l'allocation d'éducation de l'enfant handicapé est fixé à 65 % de la base "
                 "mensuelle de calcul des allocations familiales », et chaque catégorie à "
                 "son propre taux",
        decision="D-191",
        kill_test="test_the_engine_alone_pays_each_complement_the_rate_of_the_category_below",
    ),
    Correction(
        name="ass_imposable_comme_un_salaire",
        citation="C. trav. art. L. 5428-1 — « Les règles fixées au 5 de l'article 158 du code "
                 "général des impôts sont applicables » : l'allocation de solidarité spécifique "
                 "« est imposable entre les mains des bénéficiaires dans la catégorie des "
                 "traitements et salaires » (BOI-RSA-CHAMP-20-20, § 20)",
        decision="D-192",
        kill_test="test_the_engine_alone_leaves_the_ass_out_of_the_income_tax",
    ),
    Correction(
        name="asi_moitie_a_cote_d_un_conjoint_a_l_aspa",
        citation="CSS art. D. 815-19, 2° c) — quand le conjoint bénéficie de l'ASPA, « le "
                 "montant de l'allocation servie est égal à la différence entre la moitié du "
                 "plafond mentionné au 2° et la moitié des ressources du couple »",
        decision="D-194",
        kill_test="test_the_engine_alone_pays_no_asi_beside_a_spouse_at_the_aspa",
    ),
    Correction(
        name="aspa_moitie_a_cote_d_un_conjoint_a_l_asi",
        citation="CSS art. D. 815-1 — le montant du couple « est servi par moitié à chacun des "
                 "deux allocataires concernés », et « Les dispositions du b sont également "
                 "applicables pour le calcul de l'allocation de solidarité aux personnes âgées "
                 "servie au demandeur lorsque son conjoint [...] bénéficie de l'allocation "
                 "supplémentaire d'invalidité »",
        decision="D-194",
        kill_test="test_the_engine_alone_pays_the_aspa_beside_an_asi_spouse_half_the_couple_maximum",
    ),
    Correction(
        name="emploi_domicile_plafond_majore_par_membre_de_plus_de_65_ans",
        citation="CGI art. 199 sexdecies, 3 — « La limite de 12 000 € est majorée de 1 500 € par "
                 "enfant à charge au sens des articles 196 et 196 B et au titre de chacun des "
                 "membres du foyer fiscal âgé de plus de soixante-cinq ans », et la limite de la "
                 "première année « fait l'objet des majorations prévues au présent alinéa »",
        decision="D-198",
        kill_test="test_the_engine_alone_leaves_the_members_over_65_out_of_the_home_help_ceiling",
    ),
    Correction(
        name="aah_d_un_conjoint_retraite_hors_des_ressources_du_minimum",
        citation="CSS art. R. 815-22 — toutes les ressources comptent, « indépendamment des "
                 "ressources exclues par des dispositions particulières » ; la lettre "
                 "ministérielle du 19 mars 1982, que reprend la liste de la Cnav, exclut l'« AAH "
                 "(et ses compléments) du conjoint, concubin ou pacsé s'il est titulaire d'un "
                 "avantage de vieillesse ou d'invalidité »",
        decision="D-200",
        kill_test="test_the_engine_alone_counts_the_aah_of_a_pensioner_beside_a_spouse_at_the_"
                  "aspa",
    ),
    Correction(
        name="emploi_domicile_majoration_moitie_enfant_en_residence_alternee",
        citation="CGI art. 199 sexdecies, 3 — la limite est majorée de 1 500 € par enfant à "
                 "charge, et « Le montant de 1 500 € est divisé par deux pour les enfants réputés "
                 "à charge égale de l'un et l'autre de leurs parents »",
        decision="D-201",
        kill_test="test_the_engine_alone_takes_a_shared_child_off_the_home_help_ceiling",
    ),
    Correction(
        name="plafonnement_quotient_familial_enfants_en_residence_alternee",
        citation="CGI art. 197, I, 2 — « la réduction d'impôt correspondant à la demi-part "
                 "accordée au titre de chacun des deux premiers enfants est limitée à la moitié de "
                 "cette somme », et la réduction de 1 993 € des « contribuables veufs ayant des "
                 "enfants à charge », que la charge soit « réputée également partagée entre les "
                 "parents » (art. 196)",
        decision="D-201",
        kill_test="test_the_engine_alone_caps_a_shared_child_s_quotient_as_a_child_at_charge",
    ),
    Correction(
        name="asf_pas_pour_un_enfant_en_residence_alternee",
        citation="CSS art. L. 523-1, I, 3° — l'ASF va à « tout enfant dont le père ou la mère [...] "
                 "se soustraient ou se trouvent [...] hors d'état de faire face à leurs obligations "
                 "d'entretien », ce que ne fait pas le parent qui l'héberge en alternance",
        decision="D-201",
        kill_test="test_the_engine_alone_pays_the_asf_for_a_shared_child",
    ),
    Correction(
        name="plafond_qf_part_du_premier_enfant_reservee_aux_foyers_qui_en_ont_un",
        citation="CGI art. 197, I, 2 — pour les célibataires ou divorcés qui répondent aux "
                 "conditions du II de l'article 194, « la réduction d'impôt correspondant à la "
                 "part accordée au titre du premier enfant à charge est limitée » (4 224 € sur "
                 "les revenus de 2024) ; ceux qui « supportent effectivement la charge d'une "
                 "personne mentionnée à l'article 196 A bis du CGI, à l'exclusion de tout enfant, "
                 "ne sont pas concernés par le plafonnement spécifique » (BOI-IR-LIQ-10-10-10-30, "
                 "§ 55)",
        decision="D-202",
        kill_test="test_the_engine_alone_caps_a_lone_adult_s_case_r_half_part_at_the_first_"
                  "child_s_ceiling",
    ),
    Correction(
        name="complements_de_l_aah_d_un_conjoint_sans_pension_dans_les_ressources_du_minimum",
        citation="CSS art. R. 815-22 — « Il est tenu compte, pour l'appréciation des ressources, "
                 "de tous les avantages d'invalidité et de vieillesse dont bénéficie l'intéressé, "
                 "des revenus professionnels et autres » ; la liste de la Cnav n'exclut que les "
                 "compléments de l'AAH du demandeur et les « Compléments d'AAH du conjoint, "
                 "concubin ou partenaire pacsé s'il est titulaire d'un avantage de vieillesse ou "
                 "d'invalidité »",
        decision="D-203",
        kill_test="test_the_engine_alone_leaves_the_mva_of_a_spouse_out_of_the_aspa",
    ),
)

AL_BASE = "aide_logement_base_ressources_individu"
AL_AMOUNT = "aide_logement_montant_brut"
ASS_BASE = "ass_base_ressources"
MVA_ELIGIBILITY = "eligibilite_caah"
AAH_ELIGIBILITY = "aah_eligible"
ASPA_ELIGIBILITY = "aspa_eligibilite"
ASI_ELIGIBILITY = "asi_eligibilite"
AEEH = "aeeh"
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
PENSIONS_NETTES = "pensions_nettes"
#: openfisca's levies on a retirement pension that a declared amount still owes, the
#: deductible CSG being already off it: read on the invalidity pension by correction 9.
PENSION_LEVIES = ("csg_imposable_retraite", "crds_retraite", "casa")
#: The date of the levy formulas correction 9 wraps; before it, openfisca's net pensions stand.
LEVIES_SINCE = "2019-01-01"
ASI_AMOUNT = "asi"
ASPA_AMOUNT = "aspa"
#: Since this date the ASI is the ceiling less the resources (CSS art. L. 815-24-1), and
#: art. D. 815-19 caps the lone beneficiary of a couple and halves the ASI beside a spouse at
#: the ASPA; openfisca's formula for the ASPA starts on the same date.
ASI_DIFFERENTIELLE_DEPUIS = "2020-04-01"
#: The minimum invalidity pension of an employee (CSS art. L. 341-5), a month, from each date,
#: as the Cnav circulars give it: 2022-22 for April 2020 to July 2022, then 2023-09, 2024-13,
#: 2024-42 and 2025-30. openfisca's tree does not carry it.
PENSION_INVALIDITE_MINIMUM: tuple[tuple[str, float], ...] = (
    ("2020-04-01", 292.80), ("2021-04-01", 293.96), ("2022-04-01", 297.20),
    ("2022-07-01", 309.09), ("2023-01-01", 311.56), ("2024-01-01", 328.07),
    ("2025-01-01", 335.29), ("2026-01-01", 338.31),
)
#: The income tax's category of salaries, pensions and rentes, where correction 12 puts the
#: ASS among each member's salaries, and the two variables of openfisca's deduction it reruns.
SALARY_CATEGORY = "revenu_categoriel_tspr"
SALARIES = "revenu_assimile_salaire"
SALARIES_AFTER_DEDUCTION = "revenu_assimile_salaire_apres_abattements"
#: The ASS's work condition, without which openfisca's ASS is nil (`ass_eligibilite_individu`).
ASS_CONDITION = "ass_precondition_remplie"
#: The home-help credit, the date of the formula correction 15 wraps, and the count of persons
#: that formula raises its ceilings for: the dependants, among whom the correction adds the
#: declarants over 65.
HOME_HELP_CREDIT = "ci_saldom"
HOME_HELP_SINCE = "2020-01-01"
HOME_HELP_INCREMENTS = "nb_pac2"
#: The age from which a member of the foyer raises the home-help ceiling (CGI art. 199 sexdecies,
#: 3), reached « au 31 décembre ou à la date du décès » (Brochure pratique 2025). openfisca's
#: tree has no such parameter, since its formula never reads an age.
AGE_SALDOM = 65
#: Each person's resources for the ASPA and the ASI, which correction 16 rids of the AAH of
#: whoever draws a retirement pension, and to which correction 21 adds the AAH's compléments
#: wherever the AAH counts.
ASI_ASPA_BASE = "asi_aspa_base_ressources_individu"
#: The AAH's compléments as paid, the MVA since December 2019 (openfisca's `caah`).
AAH_COMPLEMENTS = "caah"
#: The children in alternating residence of a foyer fiscal, case H, which correction 17 counts
#: once more among the home-help increments and correction 18 among the dependants of the caps.
CHILDREN_SHARED = "nbH"
#: The income tax after the caps of the quotient familial, the date of the formula correction 18
#: wraps, and the two variables of it the correction makes read otherwise: the dependants, and the
#: tax on one part (two for a couple) from which the caps are taken.
QUOTIENT_CAPS = "ir_plaf_qf"
QUOTIENT_CAPS_SINCE = "2013-01-01"
DEPENDANTS = "nb_pac"
TAX_WITHOUT_QUOTIENT = "ir_ss_qf"
#: A child's eligibility to the ASF, which correction 19 withholds from a shared child.
ASF_ELIGIBILITY = "asf_elig_enfant"
#: Case T, which `ir_plaf_qf` reads to choose a lone parent's first child's ceiling, and which
#: correction 20 lets it read only where a child is at charge.
CASE_T = "caseT"


#: The daily allowances corrections 22 and 23 read, sickness first, then work accidents and
#: occupational diseases, whose taxable share is the one the exemption leaves.
SICK_PAY_SICKNESS = "indemnites_journalieres_maladie"
SICK_PAY_WORK = ("indemnites_journalieres_accident_travail",
                 "indemnites_journalieres_maladie_professionnelle")
#: The share of the work-accident allowances the income tax exempts (CGI art. 81, 8°): a
#: parameter this project brings into the tree, so that a knob can move it (D-306).
PATH_IJ_AT_MP_EXONEREE = ("impot_revenu", "indemnites_journalieres", "part_exoneree_at_mp")
IJ_AT_MP_EXONEREE = 0.5
IJ_AT_MP_EXONEREE_DEPUIS = "2010-01-01"
#: The part of the sickness allowances served for an ALD (CSS art. L. 160-14, 3° and 4°), an
#: input this project adds, and the share of it the income tax exempts (CGI art. 80
#: quinquies): 1 since 1978 (D-312).
SICK_PAY_ALD = "indemnites_journalieres_maladie_ald"
PATH_IJ_ALD_EXONEREE = ("impot_revenu", "indemnites_journalieres", "part_exoneree_ald")
IJ_ALD_EXONEREE = 1.0
IJ_ALD_EXONEREE_DEPUIS = "1978-01-01"
#: openfisca's CSG on the allowances, which nothing levies (correction 23).
PATH_CSG_IJ = ("prelevements_sociaux", "contributions_sociales", "csg", "remplacement",
               "indemnites_journalieres")
CSG_IJ = "csg_indemnites_journalieres"


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
            # One call for every parameter: openfisca's `modify_parameters` starts again from
            # the baseline's tree, so a second call would undo the first (D-306).
            self.modify_parameters(modifier_function=_parameter_corrections)
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
            ass_base_formula = self.get_variable(ASS_BASE).get_formula("0001-01-01")
            self.update_variable(_spouse_s_benefit_whoever_heads_the_famille(ass_base_formula))
            nettes_formula = self.get_variable(PENSIONS_NETTES).get_formula(LEVIES_SINCE)
            levy_formulas = tuple(self.get_variable(name).get_formula(LEVIES_SINCE)
                                  for name in PENSION_LEVIES)
            self.update_variable(_invalidity_pension_levied(nettes_formula, levy_formulas))
            asi_amount = self.get_variable(ASI_AMOUNT).get_formula(ASI_DIFFERENTIELLE_DEPUIS)
            self.update_variable(_asi_capped_for_a_lone_beneficiary_in_a_couple(asi_amount))
            aeeh_formula = self.get_variable(AEEH).get_formula("2006-01-01")
            self.update_variable(_aeeh_complement_at_its_own_category(aeeh_formula))
            category_formula = self.get_variable(SALARY_CATEGORY).get_formula("0001-01-01")
            deduction = self.get_variable(SALARIES_AFTER_DEDUCTION)
            self.update_variable(_ass_taxed_as_a_salary(category_formula, deduction.get_formula))
            # Read after correction 10's update: correction 13 wraps the capped `asi`, so the
            # variable keeps both.
            asi_capped = self.get_variable(ASI_AMOUNT).get_formula(ASI_DIFFERENTIELLE_DEPUIS)
            self.update_variable(_asi_half_beside_a_spouse_at_the_aspa(asi_capped))
            aspa_amount = self.get_variable(ASPA_AMOUNT).get_formula(ASI_DIFFERENTIELLE_DEPUIS)
            self.update_variable(_aspa_half_beside_a_spouse_at_the_asi(aspa_amount))
            saldom_formula = self.get_variable(HOME_HELP_CREDIT).get_formula(HOME_HELP_SINCE)
            self.update_variable(_home_help_ceiling_raised_for_the_declarants_over_65(
                saldom_formula))
            base_formula = self.get_variable(ASI_ASPA_BASE).get_formula("0001-01-01")
            self.update_variable(_aah_of_a_pensioner_left_out(base_formula))
            # Read after correction 15's update: correction 17 wraps the credit it left, so the
            # variable keeps both, the declarants over 65 and the shared children.
            saldom_corrected = self.get_variable(HOME_HELP_CREDIT).get_formula(HOME_HELP_SINCE)
            self.update_variable(_home_help_increment_halved_for_a_shared_child(saldom_corrected))
            caps_formula = self.get_variable(QUOTIENT_CAPS).get_formula(QUOTIENT_CAPS_SINCE)
            self.update_variable(_quotient_caps_beside_shared_children(caps_formula))
            asf_formula = self.get_variable(ASF_ELIGIBILITY).get_formula("0001-01-01")
            self.update_variable(_asf_not_for_a_shared_child(asf_formula))
            # Read after correction 18's update: correction 20 wraps the caps it left, so the
            # variable keeps both, the shared children and case T beside a child only.
            caps_corrected = self.get_variable(QUOTIENT_CAPS).get_formula(QUOTIENT_CAPS_SINCE)
            self.update_variable(_first_child_ceiling_only_beside_a_child(caps_corrected))
            # Read after correction 16's update: correction 21 wraps the base it left, so the
            # variable keeps both.
            pensioner_base = self.get_variable(ASI_ASPA_BASE).get_formula("0001-01-01")
            self.update_variable(_aah_complements_counted_as_the_aah(pensioner_base))
            # Corrections 22 and 23 (D-306). Read after correction 12's update and correction
            # 7's: each wraps the formula those left, so the variables keep both.
            self.add_variable(_csg_on_sick_pay())
            self.add_variable(_ald_sick_pay())
            category_corrected = self.get_variable(SALARY_CATEGORY).get_formula("0001-01-01")
            self.update_variable(_sick_pay_taxed_as_a_salary(category_corrected,
                                                             deduction.get_formula))
            nettes_corrected = self.get_variable(PENSIONS_NETTES).get_formula(LEVIES_SINCE)
            self.update_variable(_sick_pay_among_the_replacement_incomes(nettes_corrected))

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


def _parameter_corrections(parameters: Any) -> Any:
    """The parameters the corrections change or add, in one modifier: correction 6's age,
    then correction 22's two exempt shares."""
    return _sick_pay_exempt_shares(_inaptitude_age(parameters))


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


def _spouse_s_benefit_whoever_heads_the_famille(openfisca_formula: Any) -> Any:
    """`ass_base_ressources`, with the first parent's unemployment benefit counted when the
    first parent does not claim the ASS (C. trav. art. R. 5423-2): openfisca adds it to the
    second parent's resources only. The term is openfisca's own for the second parent."""
    from openfisca_core.model_api import ADD, MONTH, Variable, not_, set_input_divide_by_period
    from openfisca_core.periods import Period
    from openfisca_france.entities import Famille

    class ass_base_ressources(Variable):  # openfisca's naming
        value_type = float
        entity = Famille
        label = ("Base de ressources de l'ASS, l'allocation chômage du conjoint de l'allocataire "
                 "comprise quel que soit son rôle dans la famille (C. trav. art. R. 5423-2)")
        definition_period = MONTH
        set_input = set_input_divide_by_period

        def formula(famille, period):
            # As `ass_base_ressources_conjoint` reads it for the second parent: the benefit
            # of the twelve months before, unless it stopped last month.
            annee = Period(("year", period.start, 1)).offset(-1)
            mois_precedent = Period(("month", period.start, 1)).offset(-1)
            chomage = famille.demandeur("chomage_net", annee, options=[ADD])
            interrompu = famille.demandeur("chomage_net", mois_precedent) == 0
            allocataire = famille.demandeur("ass_precondition_remplie", period)
            return (openfisca_formula(famille, period)
                    + chomage * not_(interrompu) * not_(allocataire))

    return ass_base_ressources


class _InvalidityPensionAsRetirement:
    """The individuals as openfisca's levies on a pension see them, with the invalidity
    pension where they read the retirement pension (correction 9). Everything else they read,
    the RFR and the parts of N-2 among them, is the population's own."""

    def __init__(self, individu: Any) -> None:
        self._individu = individu

    def __call__(self, variable_name: str, period: Any, options: Any = None) -> Any:
        if variable_name == "retraite_brute":
            variable_name = "pensions_invalidite"
        return self._individu(variable_name, period, options)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._individu, name)


def _invalidity_pension_levied(openfisca_formula: Any, levy_formulas: tuple[Any, ...]) -> Any:
    """`pensions_nettes`, less the CSG imposable, the CRDS and the CASA due on the invalidity
    pension: openfisca's own levies on a retirement pension, read on the invalidity one,
    month by month, and openfisca's formula for the rest."""
    from openfisca_core.model_api import MONTH, YEAR, Variable
    from openfisca_france.entities import Individu

    class pensions_nettes(Variable):  # openfisca's naming
        value_type = float
        entity = Individu
        label = ("Pensions et revenus de remplacement, la pension d'invalidité nette de sa CSG "
                 "imposable, de sa CRDS et de sa CASA (CSS art. L. 136-8 et L. 137-41)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042683546"
        definition_period = YEAR

        def formula_2019_01_01(individu, period, parameters):
            invalidite = _InvalidityPensionAsRetirement(individu)
            levies = sum(levy(invalidite, month, parameters)  # negative, as openfisca's are
                         for month in period.get_subperiods(MONTH)
                         for levy in levy_formulas)
            return openfisca_formula(individu, period) + levies

    return pensions_nettes


def minimum_invalidity_pension(instant: str) -> float:
    """The minimum invalidity pension of an employee in force at `instant` ('YYYY-MM-DD'), a
    month (`PENSION_INVALIDITE_MINIMUM`)."""
    in_force = [amount for start, amount in PENSION_INVALIDITE_MINIMUM if start <= instant]
    if not in_force:
        raise ValueError(f"aucune pension d'invalidité minimale connue au {instant}")
    return in_force[-1]


def _asi_capped_for_a_lone_beneficiary_in_a_couple(openfisca_formula: Any) -> Any:
    """`asi`, capped for the lone allocataire of a couple at the single ceiling less the
    minimum invalidity pension (CSS art. D. 815-19, 2° b): openfisca's amount otherwise."""
    from openfisca_core.model_api import (
        MONTH,
        Variable,
        calculate_output_add,
        min_,
        set_input_divide_by_period,
        where,
    )
    from openfisca_france.entities import Individu

    class asi(Variable):  # openfisca's naming
        value_type = float
        entity = Individu
        label = ("Allocation supplémentaire d'invalidité (ASI), plafonnée pour le seul "
                 "allocataire d'un couple (CSS art. D. 815-19, 2° b)")
        definition_period = MONTH
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042956446"
        set_input = set_input_divide_by_period
        calculate_output = calculate_output_add

        def formula_2020_04_01(individu, period, parameters):
            montant = openfisca_formula(individu, period, parameters)
            seul_allocataire_du_couple = (
                individu.famille("en_couple", period)
                * (individu.famille("asi_aspa_nb_alloc", period) == 1))
            plafond_seul = parameters(period).prestations_sociales.prestations_etat_de_sante \
                .invalidite.asi.plafond_ressource_seul / 12
            plafond = plafond_seul - minimum_invalidity_pension(str(period.start))
            return where(seul_allocataire_du_couple, min_(montant, plafond), montant)

    return asi


def _asi_half_beside_a_spouse_at_the_aspa(capped_formula: Any) -> Any:
    """`asi`, for a parent whose spouse is eligible to the ASPA: half the ASI's couple ceiling
    less half the couple's resources (CSS art. D. 815-19, 2° c). openfisca prices that case
    against the ASPA's ceiling and pays it nothing. Correction 10's formula, itself around
    openfisca's, stands for every other case."""
    from openfisca_core.model_api import (
        MONTH,
        Variable,
        calculate_output_add,
        max_,
        set_input_divide_by_period,
        where,
    )
    from openfisca_france.entities import Famille, Individu

    class asi(Variable):  # openfisca's naming
        value_type = float
        entity = Individu
        label = ("Allocation supplémentaire d'invalidité (ASI), plafonnée pour le seul "
                 "allocataire d'un couple, et à côté d'un conjoint à l'ASPA la moitié du "
                 "plafond du couple moins la moitié des ressources (CSS art. D. 815-19, 2°)")
        definition_period = MONTH
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000042956446"
        set_input = set_input_divide_by_period
        calculate_output = calculate_output_add

        def formula_2020_04_01(individu, period, parameters):
            famille = individu.famille
            a_cote_de_l_aspa = (
                individu.has_role(Famille.DEMANDEUR)
                * famille.demandeur("asi_eligibilite", period)
                * famille.conjoint("aspa_eligibilite", period)
                + individu.has_role(Famille.CONJOINT)
                * famille.conjoint("asi_eligibilite", period)
                * famille.demandeur("aspa_eligibilite", period))
            plafond = parameters(period).prestations_sociales.prestations_etat_de_sante \
                .invalidite.asi.plafond_ressource_couple / 12
            moitie = max_(plafond - famille("asi_aspa_base_ressources", period), 0) / 2
            return where(a_cote_de_l_aspa, moitie,
                         capped_formula(individu, period, parameters))

    return asi


def _aspa_half_beside_a_spouse_at_the_asi(openfisca_formula: Any) -> Any:
    """`aspa`, for a couple whose other spouse is eligible to the ASI: half of the couple's ASPA,
    as two beneficiaries draw it (CSS art. D. 815-1). openfisca's formula otherwise."""
    from openfisca_core.model_api import (
        MONTH,
        Variable,
        calculate_output_add,
        max_,
        set_input_divide_by_period,
        where,
    )
    from openfisca_france.entities import Famille

    class aspa(Variable):  # openfisca's naming
        calculate_output = calculate_output_add
        value_type = float
        entity = Famille
        label = ("Allocation de solidarité aux personnes âgées ; à côté d'un conjoint à l'ASI, la "
                 "moitié du montant du couple (CSS art. D. 815-1)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000036760292"
        definition_period = MONTH
        set_input = set_input_divide_by_period

        def formula_2020_04_01(famille, period, parameters):
            a_cote_de_l_asi = (
                famille.demandeur("aspa_eligibilite", period)
                * famille.conjoint("asi_eligibilite", period)
                + famille.conjoint("aspa_eligibilite", period)
                * famille.demandeur("asi_eligibilite", period))
            aspa = parameters(period).prestations_sociales.solidarite_insertion \
                .minimum_vieillesse.aspa
            # The b) of art. D. 815-1, as two beneficiaries draw it: the couple's maximum, less
            # what it and the resources pass the couple's ceiling by (art. L. 815-9, D. 815-2).
            maximum = aspa.montant_maximum_annuel.couples / 12
            depassement = max_(famille("asi_aspa_base_ressources", period) + maximum
                               - aspa.plafond_ressources.couples / 12, 0)
            moitie = max_(maximum - depassement, 0) / 2
            return where(a_cote_de_l_asi, moitie,
                         openfisca_formula(famille, period, parameters))

    return aspa


def _aah_of_a_pensioner_left_out(openfisca_formula: Any) -> Any:
    """`asi_aspa_base_ressources_individu`, without the AAH of whoever draws a retirement
    pension that month: the ASPA and the ASI leave out the AAH « du conjoint [...] s'il est
    titulaire d'un avantage de vieillesse ou d'invalidité » (the Cnav's lists, after the
    ministerial letter of 19 March 1982). openfisca's formula, less the AAH it counted."""
    from openfisca_core.model_api import ADD, MONTH, Variable, not_, set_input_divide_by_period
    from openfisca_france.entities import Individu

    class asi_aspa_base_ressources_individu(Variable):  # openfisca's naming
        value_type = float
        entity = Individu
        label = ("Base ressources individuelle du minimum vieillesse/ASPA, hors l'AAH de qui est "
                 "titulaire d'une pension de retraite (lettre ministérielle du 19 mars 1982)")
        definition_period = MONTH
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000047770487"
        set_input = set_input_divide_by_period

        def formula(individu, period, parameters):
            # The AAH openfisca's formula counts, from the same periods and on its own tests: it
            # leaves out only that of whoever is eligible to the ASPA or the ASI, or draws an
            # invalidity pension.
            aah = individu("aah", period.last_3_months, options=[ADD])
            comptee = (aah * not_(individu("aspa_eligibilite", period))
                       * not_(individu("asi_eligibilite", period))
                       * not_(individu("pensions_invalidite", period) > 0))
            retraite = individu("retraite_brute", period) > 0
            return openfisca_formula(individu, period, parameters) - comptee * retraite / 3

    return asi_aspa_base_ressources_individu


def _aeeh_complement_at_its_own_category(openfisca_formula: Any) -> Any:
    """`aeeh`, with each complément at its own category's rate (CSS art. D. 541-2):
    openfisca's formula, plus what it leaves out by paying the second to the fifth category
    the complément of the category below, wherever its own test opens the AEEH."""
    from openfisca_core.model_api import (
        MONTH,
        Variable,
        calculate_output_add,
        set_input_divide_by_period,
    )
    from openfisca_france.entities import Famille

    class aeeh(Variable):  # openfisca's naming
        value_type = float
        entity = Famille
        label = ("Allocation d'éducation de l'enfant handicapé, chaque complément au taux de sa "
                 "catégorie (CSS art. D. 541-2)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006737170"
        definition_period = MONTH
        set_input = set_input_divide_by_period
        calculate_output = calculate_output_add

        def formula_2006_01_01(famille, period, parameters):
            prestations_familiales = parameters(period).prestations_sociales \
                .prestations_familiales
            regle = prestations_familiales.education_presence_parentale.aeeh
            complement = regle.complement_allocation
            # openfisca's own test of who opens the AEEH, read from the same variables.
            ouverte = (famille.members("handicap", period)
                       * (famille.members("age", period) < regle.age_maximum_enfant))
            niveau = famille.members("aeeh_niveau_handicap", period)
            manque = ouverte * prestations_familiales.bmaf.bmaf * (
                (niveau == 2) * (complement.categorie_2 - complement.categorie_1)
                + (niveau == 3) * (complement.categorie_3 - complement.categorie_2)
                + (niveau == 4) * (complement.categorie_4 - complement.categorie_3)
                + (niveau == 5) * (complement.categorie_5 - complement.categorie_4))
            return (openfisca_formula(famille, period, parameters)
                    + famille.sum(manque, role=Famille.ENFANT))

    return aeeh


class _SalariesWithTheAss:
    """The individuals as openfisca's deduction formula sees them, with the year's ASS among each
    one's salaries (correction 12). Everything else it reads, the real expenses among them, is
    the individuals' own."""

    def __init__(self, individu: Any, ass: Any) -> None:
        self._individu = individu
        self._ass = ass

    def __call__(self, variable_name: str, period: Any, options: Any = None) -> Any:
        value = self._individu(variable_name, period, options)
        return value + self._ass if variable_name == SALARIES else value

    def __getattr__(self, name: str) -> Any:
        return getattr(self._individu, name)


def _ass_taxed_as_a_salary(openfisca_formula: Any, deduction_formula: Any) -> Any:
    """`revenu_categoriel_tspr`, with the ASS of the year among each member's salaries (C. trav.
    art. L. 5428-1, CGI art. 158, 5): openfisca's formula, plus what openfisca's own deduction
    leaves of a member's salaries and ASS together, less what it leaves of the salaries alone.
    Nothing is read when nobody in the simulation meets the ASS's work condition that year."""
    from openfisca_core.model_api import ADD, YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class revenu_categoriel_tspr(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = ("Revenu catégoriel - Traitements, salaires, pensions et rentes, l'allocation de "
                 "solidarité spécifique comprise (C. trav. art. L. 5428-1)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000037388531"
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            montant = openfisca_formula(foyer_fiscal, period, parameters)
            individus = foyer_fiscal.members
            if not individus(ASS_CONDITION, period, options=[ADD]).any():
                return montant
            ass = individus("ass", period, options=[ADD])
            avec = deduction_formula(period)(_SalariesWithTheAss(individus, ass), period,
                                             parameters)
            sans = individus(SALARIES_AFTER_DEDUCTION, period)
            return montant + foyer_fiscal.sum(avec - sans)

    return revenu_categoriel_tspr


class _DeclarantsOver65AmongTheIncrements:
    """The foyers fiscaux as openfisca's home-help credit sees them, with the declarants of 65 or
    more on 31 December among the persons its ceilings are raised for (correction 15). Everything
    else it reads, the expenses, the aid received and the boxes 7DG, 7DL and 7DQ, is the foyers'
    own."""

    def __init__(self, foyer_fiscal: Any, declarants: Any) -> None:
        self._foyer_fiscal = foyer_fiscal
        self._declarants = declarants

    def __call__(self, variable_name: str, period: Any, options: Any = None) -> Any:
        value = self._foyer_fiscal(variable_name, period, options)
        return value + self._declarants if variable_name == HOME_HELP_INCREMENTS else value

    def __getattr__(self, name: str) -> Any:
        return getattr(self._foyer_fiscal, name)


def _home_help_ceiling_raised_for_the_declarants_over_65(openfisca_formula: Any) -> Any:
    """`ci_saldom`, with the ordinary ceiling and the first year's raised by the increment for
    each declarant of 65 or more on 31 December (CGI art. 199 sexdecies, 3): openfisca's formula,
    which raises them for the dependants and the ascendants of case 7DL only, run with those
    declarants among the dependants it counts. Its increment, its caps and its 20 000 EUR without
    increment stand, read from the tree."""
    from numpy import datetime64
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class ci_saldom(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = ("Crédit d'impôt emploi d'un salarié à domicile, le plafond majoré pour chaque "
                 "membre du foyer de plus de 65 ans (CGI art. 199 sexdecies, 3)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000046861251"
        definition_period = YEAR

        def formula_2020_01_01(foyer_fiscal, period, parameters):
            # 65 or more on 31 December: born before 1 January of the year 64 years back.
            ne_avant = datetime64(f"{period.start.year - AGE_SALDOM + 1:04d}-01-01")
            plus_de_65_ans = foyer_fiscal.members("date_naissance", period) < ne_avant
            declarants = foyer_fiscal.sum(plus_de_65_ans, role=FoyerFiscal.DECLARANT)
            return openfisca_formula(_DeclarantsOver65AmongTheIncrements(foyer_fiscal, declarants),
                                     period, parameters)

    return ci_saldom


class _SharedChildrenAmongTheIncrements:
    """The foyers fiscaux as the home-help credit sees them, with each child in alternating
    residence counted once more among the persons its ceilings are raised for (correction 17):
    `nb_pac2` takes half of each off, and the article adds half. Everything else it reads is the
    foyers' own, through correction 15's view of them."""

    def __init__(self, foyer_fiscal: Any, shared: Any) -> None:
        self._foyer_fiscal = foyer_fiscal
        self._shared = shared

    def __call__(self, variable_name: str, period: Any, options: Any = None) -> Any:
        value = self._foyer_fiscal(variable_name, period, options)
        return value + self._shared if variable_name == HOME_HELP_INCREMENTS else value

    def __getattr__(self, name: str) -> Any:
        return getattr(self._foyer_fiscal, name)


def _home_help_increment_halved_for_a_shared_child(home_help_formula: Any) -> Any:
    """`ci_saldom`, each child in alternating residence raising the ceilings by half the increment
    (CGI art. 199 sexdecies, 3): the formula correction 15 left, openfisca's within it, run with
    those children counted once more in `nb_pac2`, which counts them for minus a half."""
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class ci_saldom(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = ("Crédit d'impôt emploi d'un salarié à domicile, le plafond majoré pour chaque "
                 "membre du foyer de plus de 65 ans et de moitié pour chaque enfant en résidence "
                 "alternée (CGI art. 199 sexdecies, 3)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000046861251"
        definition_period = YEAR

        def formula_2020_01_01(foyer_fiscal, period, parameters):
            # `nb_pac2` is `nbF + nbJ + nbR - nbH / 2`, and `nbF` leaves the shared children out:
            # `nbH` once more turns the half taken off into the half the article adds.
            shared = foyer_fiscal(CHILDREN_SHARED, period)
            return home_help_formula(_SharedChildrenAmongTheIncrements(foyer_fiscal, shared),
                                     period, parameters)

    return ci_saldom


class _SharedChildrenInTheQuotientCaps:
    """The foyers fiscaux as openfisca's caps of the quotient familial see them (correction 18):
    the children in alternating residence among the dependants of `nb_pac`, and the tax on one
    part raised by `excess`, what the caps give too much to a lone parent of case T whose only
    child is shared. Everything else it reads is the foyers' own."""

    def __init__(self, foyer_fiscal: Any, shared: Any, excess: Any) -> None:
        self._foyer_fiscal = foyer_fiscal
        self._shared = shared
        self._excess = excess

    def __call__(self, variable_name: str, period: Any, options: Any = None) -> Any:
        value = self._foyer_fiscal(variable_name, period, options)
        if variable_name == DEPENDANTS:
            return value + self._shared
        if variable_name == TAX_WITHOUT_QUOTIENT:
            return value + self._excess
        return value

    def __getattr__(self, name: str) -> Any:
        return getattr(self._foyer_fiscal, name)


def _quotient_caps_beside_shared_children(openfisca_formula: Any) -> Any:
    """`ir_plaf_qf`, a child in alternating residence at its own caps (CGI art. 197, I, 2):
    openfisca's formula of 2013, run with the shared children among the dependants, which gives a
    widow whose children are all shared their reduction of « cette part supplémentaire »; and, for a
    parent of case T whose only child is shared, with the tax on one part raised by what its caps
    give too much. openfisca caps the first two half-parts above one part at half of the first
    child's ceiling each, where only the shared child's, its quarter and case T's, is the first
    child's: the rest is a card's, at 1 791 EUR or half of it."""
    from numpy import maximum, minimum
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class ir_plaf_qf(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = ("Impôt après plafonnement du quotient familial et réduction complémentaire, les "
                 "enfants en résidence alternée à leurs plafonds (CGI art. 197, I, 2)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000053542636/2025-06-01"
        definition_period = YEAR

        def formula_2013_01_01(foyer_fiscal, period, parameters):
            shared = foyer_fiscal(CHILDREN_SHARED, period)
            plafonds = parameters(period).impot_revenu.calcul_impot_revenu.plaf_qf
            demi_part = plafonds.plafond_avantages_procures_par_demi_part
            # openfisca's B1, under case T: the first min((parts - 1) x 2, 2) half-parts above one
            # part at half of `celib_enf` each, the rest at `general`. With one child, shared, the
            # first is the child's and case T's quarters; any other is a card's, at `general` (a
            # quarter counting half), so the caps were too high by (that count - 1) times the gap.
            premieres = minimum((foyer_fiscal("nbptr", period) - 1) * 2, 2)
            seul_enfant_partage = (foyer_fiscal("celibataire_ou_divorce", period)
                                   * foyer_fiscal("caseT", period)
                                   * (foyer_fiscal(DEPENDANTS, period) == 0) * (shared == 1))
            excess = (seul_enfant_partage * maximum(premieres - 1, 0)
                      * (demi_part.celib_enf / 2 - demi_part.general))
            return openfisca_formula(_SharedChildrenInTheQuotientCaps(foyer_fiscal, shared, excess),
                                     period, parameters)

    return ir_plaf_qf


def _asf_not_for_a_shared_child(openfisca_formula: Any) -> Any:
    """`asf_elig_enfant`, leaving out a child in alternating residence, whose other parent
    maintains them and evades no « obligations d'entretien » (CSS art. L. 523-1, I, 3°)."""
    from openfisca_core.model_api import MONTH, Variable, not_, set_input_dispatch_by_period
    from openfisca_france.entities import Individu

    class asf_elig_enfant(Variable):  # openfisca's naming
        value_type = bool
        entity = Individu
        label = ("Enfant pouvant ouvrir droit à l'ASF, hors résidence alternée, où l'autre parent "
                 "assume la charge de l'enfant (CSS art. L. 523-1, I, 3°)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000044629511"
        definition_period = MONTH
        set_input = set_input_dispatch_by_period

        def formula(individu, period, parameters):
            return (openfisca_formula(individu, period, parameters)
                    * not_(individu("garde_alternee", period)))

    return asf_elig_enfant


class _CaseTOnlyBesideAChild:
    """The foyers fiscaux as openfisca's ceiling of the quotient familial sees them, with case T
    read only where a child is at charge (correction 20). Everything else it reads, the parts
    case T gave through `nbptr` among them, is the foyers' own."""

    def __init__(self, foyer_fiscal: Any, beside_a_child: Any) -> None:
        self._foyer_fiscal = foyer_fiscal
        self._beside_a_child = beside_a_child

    def __call__(self, variable_name: str, period: Any, options: Any = None) -> Any:
        value = self._foyer_fiscal(variable_name, period, options)
        return value & self._beside_a_child if variable_name == CASE_T else value

    def __getattr__(self, name: str) -> Any:
        return getattr(self._foyer_fiscal, name)


def _first_child_ceiling_only_beside_a_child(openfisca_formula: Any) -> Any:
    """`ir_plaf_qf`, with the ceiling of a lone parent's first child (CGI art. 197, I, 2) only
    for a foyer that has a child at charge, exclusively, mainly or alternately: a lone adult with
    case T whose only dependants are persons in case R takes the general ceiling
    (BOI-IR-LIQ-10-10-10-30, § 55). openfisca's formula, run with case T so read."""
    from openfisca_core.model_api import YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class ir_plaf_qf(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = ("Impôt après plafonnement du quotient familial et réduction complémentaire, le "
                 "plafond de la part du premier enfant réservé aux foyers qui en ont un "
                 "(CGI art. 197, I, 2)")
        reference = ("https://bofip.impots.gouv.fr/bofip/1032-PGP.html/"
                     "identifiant=BOI-IR-LIQ-10-10-10-30-20240618")
        definition_period = YEAR

        def formula_2013_01_01(foyer_fiscal, period, parameters):
            # Children at charge: openfisca's dependants but the persons of case R, and those
            # in alternating residence, whom `nb_pac` leaves out.
            enfants = foyer_fiscal("nb_pac", period) - foyer_fiscal("nbR", period)
            beside_a_child = (enfants > 0) | (foyer_fiscal("nbH", period) > 0)
            return openfisca_formula(_CaseTOnlyBesideAChild(foyer_fiscal, beside_a_child),
                                     period, parameters)

    return ir_plaf_qf


def _aah_complements_counted_as_the_aah(pensioner_formula: Any) -> Any:
    """`asi_aspa_base_ressources_individu`, with the AAH's compléments of the three months before
    wherever the AAH counts: the Cnav's lists leave out those of the demandeur and the
    « Compléments d'AAH du conjoint [...] s'il est titulaire d'un avantage de vieillesse ou
    d'invalidité », nothing more (correction 21). Correction 16's formula, plus `caah` under the
    tests the AAH counts under, read only where a parent's compléments can count beside a parent
    eligible to the ASPA or the ASI. Elsewhere the term is nil, and `caah` is never asked for."""
    from openfisca_core.model_api import ADD, MONTH, Variable, not_, set_input_divide_by_period
    from openfisca_france.entities import Famille, Individu

    class asi_aspa_base_ressources_individu(Variable):  # openfisca's naming
        value_type = float
        entity = Individu
        label = ("Base ressources individuelle du minimum vieillesse/ASPA, hors l'AAH de qui est "
                 "titulaire d'une pension de retraite, et avec les compléments de l'AAH là où "
                 "l'AAH compte (liste des ressources exclues de la Cnav)")
        definition_period = MONTH
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000047770487"
        set_input = set_input_divide_by_period

        def formula(individu, period, parameters):
            base = pensioner_formula(individu, period, parameters)
            aah = parameters(period).prestations_sociales.prestations_etat_de_sante \
                .invalidite.aah
            # The tests the AAH counts under, openfisca's and correction 16's, on a parent, the
            # only members whose resources the couple's base sums, who can draw the MVA: an
            # incapacity of 80 % or more (CSS art. L. 821-1-2).
            comptes = (individu.has_role(Famille.PARENT)
                       * (individu("taux_incapacite", period) >= aah.taux_capacite.taux_incapacite)
                       * not_(individu(ASPA_ELIGIBILITY, period))
                       * not_(individu(ASI_ELIGIBILITY, period))
                       * not_(individu("pensions_invalidite", period) > 0)
                       * not_(individu("retraite_brute", period) > 0))
            famille = individu.famille
            a_cote_d_un_minimum = sum(
                role(name, period) for role in (famille.demandeur, famille.conjoint)
                for name in (ASPA_ELIGIBILITY, ASI_ELIGIBILITY)) > 0
            lus = comptes * a_cote_d_un_minimum
            if not lus.any():
                return base
            complements = individu(AAH_COMPLEMENTS, period.last_3_months, options=[ADD])
            return base + complements * lus / 3

    return asi_aspa_base_ressources_individu


def _sick_pay_exempt_shares(parameters: Any) -> Any:
    """Bring `impot_revenu.indemnites_journalieres` into the tree: the exempt share of the
    work-accident allowances, 0,5 from 2010 (CGI art. 81, 8°), and that of the sickness
    allowances served for an ALD, 1 from 1978 (art. 80 quinquies, D-312). Refused if openfisca
    has grown a node of that name, which is the day this correction must be read again."""
    from openfisca_core.parameters import ParameterNode

    parent, node, leaf = PATH_IJ_AT_MP_EXONEREE
    ald_parent, ald_node, ald_leaf = PATH_IJ_ALD_EXONEREE
    assert (ald_parent, ald_node) == (parent, node)
    if node in getattr(parameters, parent).children:
        raise RuntimeError(f"openfisca carries {parent}.{node} now: correction 22 must be read "
                           f"again before it adds its own (D-306)")
    getattr(parameters, parent).add_child(node, ParameterNode(f"{parent}.{node}", data={
        "description": "Indemnités journalières de sécurité sociale (correction 22, D-306)",
        leaf: {
            "description": "Part des indemnités journalières AT-MP exonérée d'impôt sur le "
                           "revenu (CGI art. 81, 8°)",
            "values": {IJ_AT_MP_EXONEREE_DEPUIS: {"value": IJ_AT_MP_EXONEREE}},
            "metadata": {"unit": "/1"},
        },
        ald_leaf: {
            "description": "Part des indemnités journalières maladie servies au titre d'une "
                           "ALD exonérée d'impôt sur le revenu (CGI art. 80 quinquies)",
            "values": {IJ_ALD_EXONEREE_DEPUIS: {"value": IJ_ALD_EXONEREE}},
            "metadata": {"unit": "/1"},
        },
    }))
    return parameters


def _ald_sick_pay() -> Any:
    """`indemnites_journalieres_maladie_ald`: the part of a person's sickness allowances served
    for an ALD (CSS art. L. 160-14, 3° and 4°), an input; zero unless the population writes it
    (D-312)."""
    from openfisca_core.model_api import MONTH, Variable, set_input_divide_by_period
    from openfisca_france.entities import Individu

    class indemnites_journalieres_maladie_ald(Variable):
        value_type = float
        entity = Individu
        label = ("Dont indemnités journalières de maladie servies au titre d'une affection de "
                 "longue durée (CSS art. L. 160-14, 3° et 4°), correction 22 (D-312)")
        # The law as the PLF 2027 annex states it (art. 2, p. 18), the share as the PLFSS
        # 2026's annex 9 gives it (art. 29, p. 228).
        reference = ("https://www.assemblee-nationale.fr/dyn/contenu/visualisation/1128179/"
                     "file/PLF%202027%20-%20Evaluations%20pr%C3%A9alables.pdf")
        definition_period = MONTH
        set_input = set_input_divide_by_period

    return indemnites_journalieres_maladie_ald


def _sick_pay(individu: Any, period: Any, options: Any = None) -> tuple[Any, Any]:
    """The sickness allowances and the work-accident ones, of the period."""
    sickness = individu(SICK_PAY_SICKNESS, period, options=options)
    work = sum(individu(name, period, options=options) for name in SICK_PAY_WORK)
    return sickness, work


class _SalariesWithTheSickPay(_SalariesWithTheAss):
    """The individuals as openfisca's deduction formula sees them, with the taxable sick pay of
    the year among each one's salaries (correction 22)."""


def _sick_pay_taxed_as_a_salary(openfisca_formula: Any, deduction_formula: Any) -> Any:
    """`revenu_categoriel_tspr`, with the taxable sick pay among each member's salaries (CGI
    art. 80 quinquies and 81, 8°): the formula it wraps, plus what openfisca's own deduction
    leaves of a member's salaries and taxable allowances together, less what it leaves of the
    salaries alone. The taxable allowances are the sickness ones and the share of the
    work-accident ones the exemption leaves, less the exempt share of the sickness ones served
    for an ALD (D-312), net of their deductible CSG. Nothing is read when nobody in the
    simulation has an allowance that year."""
    from openfisca_core.model_api import ADD, YEAR, Variable
    from openfisca_france.entities import FoyerFiscal

    class revenu_categoriel_tspr(Variable):  # openfisca's naming
        value_type = float
        entity = FoyerFiscal
        label = ("Revenu catégoriel - Traitements, salaires, pensions et rentes, les indemnités "
                 "journalières imposables comprises (CGI art. 80 quinquies et 81, 8°)")
        # The law as the PLF 2027 annex states it (art. 2, pp. 18 and 20).
        reference = ("https://www.assemblee-nationale.fr/dyn/contenu/visualisation/1128179/"
                     "file/PLF%202027%20-%20Evaluations%20pr%C3%A9alables.pdf")
        definition_period = YEAR

        def formula(foyer_fiscal, period, parameters):
            montant = openfisca_formula(foyer_fiscal, period, parameters)
            individus = foyer_fiscal.members
            sickness, work = _sick_pay(individus, period, options=[ADD])
            if not ((sickness + work) > 0).any():
                return montant
            ald = individus(SICK_PAY_ALD, period, options=[ADD])
            tree = parameters(period.start)
            exempt = tree.impot_revenu.indemnites_journalieres.part_exoneree_at_mp
            exempt_ald = tree.impot_revenu.indemnites_journalieres.part_exoneree_ald
            deductible = tree.prelevements_sociaux.contributions_sociales.csg.remplacement \
                .indemnites_journalieres.deductible.taux
            taxable = (1 - deductible) * (sickness - exempt_ald * ald + (1 - exempt) * work)
            avec = deduction_formula(period)(_SalariesWithTheSickPay(individus, taxable),
                                             period, parameters)
            sans = individus(SALARIES_AFTER_DEDUCTION, period)
            return montant + foyer_fiscal.sum(avec - sans)

    return revenu_categoriel_tspr


def _csg_on_sick_pay() -> Any:
    """`csg_indemnites_journalieres`: openfisca's rate on the sickness and work-accident
    allowances of the month (CSS art. L. 136-8), negative as its levies are."""
    from openfisca_core.model_api import MONTH, Variable
    from openfisca_france.entities import Individu

    class csg_indemnites_journalieres(Variable):
        value_type = float
        entity = Individu
        label = ("CSG sur les indemnités journalières maladie et AT-MP (CSS art. L. 136-8), "
                 "correction 23 (D-306)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006740335"
        definition_period = MONTH

        def formula(individu, period, parameters):
            rate = parameters(period).prelevements_sociaux.contributions_sociales.csg \
                .remplacement.indemnites_journalieres.taux_global
            sickness, work = _sick_pay(individu, period)
            return -rate * (sickness + work)

    return csg_indemnites_journalieres


def _sick_pay_among_the_replacement_incomes(openfisca_formula: Any) -> Any:
    """`pensions_nettes`, with the year's sickness and work-accident allowances net of their
    CSG: the formula it wraps (correction 7's) for the rest."""
    from openfisca_core.model_api import ADD, YEAR, Variable
    from openfisca_france.entities import Individu

    class pensions_nettes(Variable):  # openfisca's naming
        value_type = float
        entity = Individu
        label = ("Pensions et revenus de remplacement, les indemnités journalières nettes de "
                 "leur CSG comprises (correction 23, D-306)")
        reference = "https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006740335"
        definition_period = YEAR

        def formula_2019_01_01(individu, period, parameters):
            sickness, work = _sick_pay(individu, period, options=[ADD])
            levied = individu(CSG_IJ, period, options=[ADD])
            return openfisca_formula(individu, period, parameters) + sickness + work + levied

    return pensions_nettes
