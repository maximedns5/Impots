"""Published figures the population is calibrated to and validated against.

Every number that did not come out of the EEC lives here, with its source, its
year and its scope. Nothing downstream may hardcode a statistic: if a figure is
not in this module with a citation, it does not belong in the model.

**The rule that makes the reconciliation report worth reading** (§4.3): a margin
used to calibrate is *spent* and can never afterwards be a validation line. Each
entry below declares which it is, and `reconcile.py` refuses to print a
calibration target in the validation section.

Scope warnings are not decoration. The published wage distribution is *net,
full-time-equivalent, private sector*; the model needs *gross, actual, all
sectors*. The conversion is explicit in `incomes.py` and its assumptions are
listed there rather than buried in a constant.
"""

from __future__ import annotations

from impots.reporting import Figure, Use
from impots.reporting import figures_by_use as _figures_by_use

# --------------------------------------------------------------------------- #
# Wage distribution — INSEE Base Tous Salariés 2024
#
# Published as NET, full-time-equivalent, MONTHLY, private sector. Three
# conversions stand between these numbers and `salaire_de_base`, and each one is
# an assumption: net -> gross (a single published ratio, so it cannot capture the
# fact that the ratio rises with income through the CSG/CRDS base and the
# tranche-2 contributions), EQTP -> actual (part-time and part-year), and private
# -> all sectors (public pay is flatter and we apply the private shape to it).
# --------------------------------------------------------------------------- #
BTS_URL = "https://www.insee.fr/fr/statistiques/8568701"

#: Net EQTP monthly wage deciles, private sector, all employees.
WAGE_DECILES_NET_EQTP_MONTHLY: dict[int, float] = {
    1: 1492.0, 2: 1669.0, 3: 1823.0, 4: 1992.0, 5: 2190.0,
    6: 2442.0, 7: 2785.0, 8: 3305.0, 9: 4334.0,
}

#: Per socio-professional category: (D1, median, D9) net EQTP monthly.
WAGE_QUANTILES_BY_PCS: dict[str, tuple[float, float, float]] = {
    "cadre": (2300.0, 3750.0, 7280.0),
    "profession_intermediaire": (1650.0, 2440.0, 3710.0),
    "employe": (1420.0, 1810.0, 2610.0),
    "ouvrier": (1440.0, 1950.0, 2810.0),
}

#: Mean net EQTP monthly by sex — used to reproduce the gender pay gap, which the
#: PCS split alone does not capture (women are over-represented in lower-paying
#: PCS *and* paid less inside each one).
WAGE_MEAN_NET_EQTP_BY_SEX: dict[str, float] = {"male": 2891.0, "female": 2514.0}
WAGE_MEAN_NET_EQTP_MONTHLY = 2733.0

#: Mean net EQTP monthly by age band — the age gradient is steep and the EEC's
#: five bands are enough to carry most of it.
WAGE_MEAN_NET_EQTP_BY_AGE: dict[str, float] = {"under_25": 1620.0, "25_39": 2550.0}

NET_TO_GROSS_RATIO = Figure(
    value=0.7587, unit="ratio", year=2024,
    scope="Salariés du secteur privé, ensemble : salaire net / salaire brut",
    source="INSEE, Base Tous Salariés 2024", url=BTS_URL, use="context",
    caveat="A single average ratio. The real net/gross wedge rises with pay, so "
           "applying one ratio compresses the top of the gross distribution.",
)

# --------------------------------------------------------------------------- #
# Wage bill — the one CALIBRATION target on incomes. Spent: it can never appear
# as a validation line.
# --------------------------------------------------------------------------- #
TOTAL_GROSS_WAGES = Figure(
    value=1_111.650e9, unit="EUR", year=2024,
    scope="D11 « salaires et traitements bruts », ensemble de l'économie, comptes "
          "nationaux base 2020, compte SEMI-DÉFINITIF — tous secteurs, tous employeurs",
    source="INSEE, « Les comptes de la Nation en 2025 » (29 mai 2026), tableau 6205",
    url="https://www.insee.fr/fr/statistiques/8988833",
    use="calibration",
    caveat="Covers every employee in the economy, including those in collective "
           "households the EEC does not survey. Our population is employees aged "
           "15+ in ordinary households, so it should land slightly below.",
)

PRIVATE_WAGE_BILL = Figure(
    value=726.5e9, unit="EUR", year=2024,
    scope="Masse salariale du secteur privé (champ Urssaf), France entière",
    source="Urssaf Caisse nationale, open.urssaf.fr",
    url="https://open.urssaf.fr/explore/dataset/masse-salariale-du-secteur-prive/",
    use="context",
    caveat="Urssaf perimeter: excludes agricultural employees (MSA, ~27 bn) and "
           "public employers. 20.27 M employees on average over 2024.",
)

PRIVATE_EMPLOYEES = Figure(
    value=20.27e6, unit="count", year=2024,
    scope="Effectif salarié moyen annuel du secteur privé, champ Urssaf",
    source="Urssaf Caisse nationale", url=PRIVATE_WAGE_BILL.url, use="context",
)

# --------------------------------------------------------------------------- #
# IR niches — the second CALIBRATION target, and it is now spent (B3).
#
# The population is given réduction and crédit bases until it reproduces this table,
# so the niche totals match it by construction and can never be cited as validation.
# What it costs is named on IR_NET_YIELD below: that line is no longer independent
# evidence for the niche component. The barème line is unaffected and stays clean,
# because niches are subtracted after the barème — which is exactly what
# `test_the_bareme_line_is_untouched_by_imputation` asserts.
# --------------------------------------------------------------------------- #
NICHE_CREDITS_BY_DECILE = Figure(
    value=10.605e9, unit="EUR", year=2024,
    scope="Cinq dispositifs (emploi à domicile, frais de garde, cotisations "
          "syndicales, dons aux œuvres, dons aux personnes en difficulté), montants et "
          "nombres de foyers par décile de RFR par part, millésime des revenus 2024",
    source="DGFiP, données d'assiette IR par décile de RFR par part",
    url="https://www.impots.gouv.fr/impot-sur-le-revenu",
    use="calibration",
    caveat="Spent. About 10.6 bn of the 19.53 bn of réductions and crédits: the other "
           "45 % has no imputation, and scolarité is excluded because its déclaration "
           "cases are counts of children while the published column aggregates the "
           "three levels into one amount. Within a decile every claimant receives the "
           "same base, because a count and a total are all that is published — so a "
           "reform's incidence comes out as a ten-step function and anything finer is "
           "an artefact.",
)

# --------------------------------------------------------------------------- #
# Capital income — the third CALIBRATION target, spent when the imputation runs (D-248).
#
# The population is given the PFU's base until it reproduces n° 41's hors-barème tax by
# fractile, so the PFU it pays matches by construction. What it costs is named on
# IR_NET_YIELD below: the PFU part of that line is no longer independent evidence.
# --------------------------------------------------------------------------- #
CAPITAL_PFU_BY_FRACTILE = Figure(
    value=10.32e9, unit="EUR", year=2024,
    scope="Impôt hors barème hors CEHR, moyenne par foyer et total, par décile de RFR "
          "par part, dernier centième et dernier millième, revenus 2024",
    source="DGFiP Statistiques n° 41 (novembre 2025), « L'impôt sur le revenu 2024 », "
           "tableau 2",
    url="https://www.impots.gouv.fr/statistiques", use="calibration",
    caveat="Spent when `impute_capital` runs. The base is the tax over 12,8 %; every "
           "foyer of a band gets its band's base, holders or not, in the national "
           "composition of the 2042 boxes, so the PFU comes out right at twelve steps "
           "and anything finer, or any share of holders, is an artefact. The CEHR, "
           "printed in the same cell, is stripped (1,98 bn). The population has 15 % "
           "fewer foyers per ménage than France, so each band's mean is multiplied by "
           "the ratio (×1,17) for the total to come back, as the wage bill's does.",
)

SICK_PAY_BY_BRANCH = Figure(
    value=15.645e9, unit="EUR", year=2024,
    scope="Indemnités journalières du régime général (anciens affiliés RSI compris), "
          "dépenses remboursées 2024 : 10,690 Md€ de maladie, 4,955 Md€ d'AT-MP",
    source="Rapport à la Commission des comptes de la sécurité sociale, mai 2026, "
           "fiche 2.3 tableau 1 et fiche 4.4 tableau 1",
    url="https://www.securite-sociale.fr/la-secu-en-detail/comptes-de-la-securite-sociale",
    use="calibration",
    caveat="Spent when `impute_ij` runs (D-305). Every employee of the private sector "
           "gets the expected sick pay of its cell (age band × PCS, the EEC's weekly "
           "sick-leave rate) on a wage capped at 1,8 SMIC, the two branches on the same "
           "key; the totals are the CCSS's by construction and any share of recipients "
           "is an artefact. No ALD split: no open source gives it.",
)


CAPITAL_BOXES_2042 = Figure(
    value=80.69e9, unit="EUR", year=2024,
    scope="Cases 2DC, 2TR, 2TS et 3VG des déclarations 2042, revenus 2024, total national",
    source="DGFiP, « L'impôt sur le revenu : les déclarations nationales » "
           "(data.economie.gouv.fr)",
    url="https://data.economie.gouv.fr/explore/dataset/ir-declarations-2042-nat/",
    use="context",
    caveat="Its SHARES split the imputed base over the four cases; its level is the "
           "second route to the base, against 80,63 bn derived from n° 41 (0,1 %). "
           "Life insurance at 7,5 % and the foyers taxed at the barème on option are "
           "on neither side the same way, which is why the agreement is closer than "
           "either route.",
)

# --------------------------------------------------------------------------- #
# Income tax — VALIDATION only. Never a calibration target.
# --------------------------------------------------------------------------- #
DGFIP_URL = "https://www.impots.gouv.fr/statistiques"

IR_NET_YIELD = Figure(
    value=87.99e9, unit="EUR", year=2024,
    scope="Impôt sur le revenu, recettes nettes de l'État, exécution budgétaire",
    source="budget.gouv.fr, exécution 2024", url="https://www.budget.gouv.fr/", use="validation",
    caveat="State budget outturn. Includes the prélèvement forfaitaire unique on "
           "capital income (~7.9 bn in 2025), which the population carries only when "
           "`impute_capital` runs — and then from CAPITAL_PFU_BY_FRACTILE, so that part "
           "is calibrated too (D-248). "
           "PART-CALIBRATED SINCE B3: with niche imputation on, about 10.6 bn of the "
           "réductions and crédits separating this figure from the barème are drawn "
           "from NICHE_CREDITS_BY_DECILE, so this line is no longer independent "
           "evidence for that component. The barème line above is the clean one.",
)

IR_BAREME_ON_2024_INCOME = Figure(
    value=98.84e9, unit="EUR", year=2024,
    scope="Impôt sur les revenus de 2024 soumis au barème, avant réductions et crédits",
    source="DGFiP, statistiques sur l'impôt sur le revenu", url=DGFIP_URL, use="validation",
    caveat="Barème only — this is the closer comparator for a model with no capital "
           "income. Reductions and tax credits (19.53 bn) are applied separately and "
           "are largely outside Phase 0's whitelist of modelled provisions.",
)

FOYERS_FISCAUX = Figure(
    value=41_635_259, unit="count", year=2024,
    scope="Nombre de foyers fiscaux, revenus 2024, France entière + non-résidents",
    source="DGFiP/DESF, IRCOM 2025 (revenus 2024), fichier national, ligne Total",
    url=DGFIP_URL, use="validation",
    caveat="Includes 298 023 non-resident foyers, which this population does not "
           "contain at all — expect to land about 0.7 % below on that count alone.",
)
FOYERS_IMPOSES = Figure(
    value=19_681_757, unit="count", year=2024,
    scope="Foyers fiscaux imposés (impôt dû non nul), revenus 2024",
    source="DGFiP/DESF, IRCOM 2025 (revenus 2024)", url=DGFIP_URL, use="validation",
    caveat="47.2 % of all foyers. A structural check that does not depend on the "
           "wage level we calibrated, which makes it one of the few genuinely "
           "independent lines available in branch A'.",
)
DECLARED_WAGES = Figure(
    value=932.1e9, unit="EUR", year=2024,
    scope="Traitements et salaires déclarés à l'impôt sur le revenu",
    source="DGFiP", url=DGFIP_URL, use="validation",
    caveat="Taxable wages, i.e. after employee contributions and deductible CSG — "
           "compare against `salaire_imposable`, not `salaire_brut`.",
)
DECLARED_PENSIONS = Figure(
    value=374_366_431_543.0, unit="EUR", year=2024,
    scope="Pensions, retraites et rentes déclarées en cases 1AS-1DS (retraites)",
    source="DGFiP, L'impôt sur le revenu : les déclarations nationales (2042)",
    url="https://data.economie.gouv.fr/explore/dataset/ir-declarations-2042-nat/",
    use="calibration",
    caveat="Used as the pension calibration target, and therefore spent. Until D-211 the "
           "target was Stat 41's « pensions et rentes », 400,4 Md€, which adds 26 Md€ of "
           "invalidity, alimony, foreign pensions, capital and life annuities to these "
           "boxes (D-210). `incomes.py` drew all of it onto retirees, and art. 3 of the "
           "PLF 2027 ran 17,7 % high on that population. "
           "`ingest.declared_retirement_pensions` reads the boxes; a test holds the two "
           "equal.",
)

UNEMPLOYMENT_BENEFIT_SPEND = Figure(
    value=35.9e9, unit="EUR", year=2024,
    scope="Allocations chômage et aides au reclassement versées par l'Assurance chômage",
    source="Unédic, Situation financière de l'Assurance chômage 2025-2027 (juin 2025)",
    url="https://www.unedic.org/publications", use="calibration",
    caveat="~2.5 M people indemnified. The EEC counts 2.33 M unemployed on the ILO "
           "definition, which is a different population: some indemnified people are "
           "not ILO-unemployed and vice versa. Used as a level calibration only.",
)

# --------------------------------------------------------------------------- #
# Benefits — VALIDATION only. Expected to run high: OpenFisca computes legal
# entitlement, i.e. 100 % take-up.
# --------------------------------------------------------------------------- #
CNAF_URL = "https://www.caf.fr/allocataires/caf-du-nord/statistiques"

BENEFIT_SPEND: dict[str, Figure] = {
    "af": Figure(13.77e9, "EUR", 2024, "Allocations familiales, tous régimes, France entière",
                 "CNAF", CNAF_URL, "validation"),
    "ppa": Figure(10.65e9, "EUR", 2024, "Prime d'activité, tous régimes, France entière",
                  "CNAF", CNAF_URL, "validation"),
    "rsa": Figure(12.36e9, "EUR", 2024, "RSA, tous régimes, France entière (dont prime de Noël)",
                  "CNAF", CNAF_URL, "validation"),
    "aide_logement": Figure(15.99e9, "EUR", 2024,
                            "Aides au logement (APL + ALS + ALF), tous régimes, France entière",
                            "CNAF", CNAF_URL, "validation"),
}

BENEFIT_RECIPIENTS: dict[str, Figure] = {
    "af": Figure(4.752e6, "count", 2024, "Allocataires AF au 31/12, CAF, France entière",
                 "CNAF", CNAF_URL, "validation"),
    "ppa": Figure(4_812_900, "count", 2024,
                  "Allocataires prime d'activité au 31/12, tous régimes",
                  "DREES, Panorama Minima sociaux 2025, vue d'ensemble tableau 2",
                  CNAF_URL, "validation"),
    "rsa": Figure(1_840_200, "count", 2024,
                  "Foyers allocataires du RSA au 31/12, tous régimes",
                  "DREES, Panorama Minima sociaux 2025, vue d'ensemble tableau 2",
                  CNAF_URL, "validation"),
    "aide_logement": Figure(5_809_400, "count", 2024,
                            "Allocataires d'une aide au logement au 31/12, tous régimes",
                            "DREES, Panorama Minima sociaux 2025, vue d'ensemble tableau 2",
                            CNAF_URL, "validation"),
}

#: How far a 100 %-take-up entitlement total should EXCEED observed spend.
#:
#: This is the bridge the reconciliation report actually needs, and it is not the
#: same number as the non-take-up rate: DREES's "+41 % to +46 %" uplift is computed
#: over the recourants' mass under each bound, not over what the caisses paid. The
#: ranges below are the ratio of eligible mass to paid mass, which is what a model
#: computing legal entitlement should reproduce.
#:
#: A benefit line inside its band is behaving exactly as a full-take-up model
#: should. One above it is over-paying for some other reason.
TAKE_UP_BRIDGE: dict[str, tuple[float, float]] = {
    "rsa": (1.30, 1.41),
    "ppa": (1.68, 1.77),
}

#: Non-take-up. The reconciliation report cites this rather than hardcoding a
#: remembered "about a third": a model computing legal entitlement cannot be
#: graded against actual spend without it.
RSA_NON_TAKE_UP = Figure(
    value=0.35, unit="ratio", year=2021,
    scope="Taux de non-recours au RSA, en % des foyers éligibles un trimestre donné "
          "(fourchette publiée 33-37 %)",
    source="DREES, Études et Résultats n° 1370",
    url="https://drees.solidarites-sante.gouv.fr/publications-communique-de-presse/"
        "etudes-et-resultats/quantifier-le-non-recours-au-rsa",
    use="context",
    caveat="33-37 % of eligible households; 29-32 % measured on the financial mass, "
           "which is the relevant one for comparing spend. 2021 reference year — "
           "the most recent DREES quantification.",
)

# --------------------------------------------------------------------------- #
# Rent — the weakest input in the model, and the one the housing-benefit
# validation line rests on. Published per square metre; the surface itself is an
# assumption, stated in `incomes.py`.
# --------------------------------------------------------------------------- #
RENT_PER_M2: dict[str, Figure] = {
    "prive": Figure(8.8, "EUR_per_m2_per_month", 2024,
                    "Loyer au m² des locataires du parc privé",
                    "INSEE, France portrait social 2024 — dépenses de logement",
                    "https://www.insee.fr/fr/statistiques/8612568", "context"),
    "social": Figure(5.6, "EUR_per_m2_per_month", 2024,
                     "Loyer au m² des locataires du parc social",
                     "INSEE, France portrait social 2024 — dépenses de logement",
                     "https://www.insee.fr/fr/statistiques/8612568", "context",
                     caveat="No published surface distribution was used: the dwelling "
                            "size rule in incomes.py is an assumption, not a measurement."),
}

# --------------------------------------------------------------------------- #
# Living standards — VALIDATION for the decile table.
# --------------------------------------------------------------------------- #
FILOSOFI_URL = "https://www.insee.fr/fr/statistiques/8402386"

#: Deciles of niveau de vie, EUR per consumption unit per year, France
#: métropolitaine, Filosofi 2023.
NIVEAU_DE_VIE_DECILES: dict[int, float] = {
    1: 13_200.0, 2: 17_010.0, 3: 20_300.0, 4: 23_190.0, 5: 25_920.0,
    6: 28_860.0, 7: 32_600.0, 8: 38_100.0, 9: 46_500.0,
}

NIVEAU_DE_VIE_MEDIAN = Figure(
    value=25_920.0, unit="EUR_per_uc_per_year", year=2023,
    scope="Médiane du niveau de vie, France métropolitaine, ménages fiscaux en logement ordinaire",
    source="INSEE, Filosofi 2023", url=FILOSOFI_URL, use="validation",
    caveat="2023 vintage in current euros; our simulation is 2024 law on 2024 incomes, "
           "so expect the model to sit above this by roughly a year of nominal growth. "
           "Filosofi's UC scale adds 0.5 UC for children in shared custody; ours does not.",
)
NIVEAU_DE_VIE_GINI = Figure(
    value=0.297, unit="ratio", year=2023, scope="Indice de Gini du niveau de vie, métropole",
    source="INSEE, Filosofi 2023", url=FILOSOFI_URL, use="validation",
)
NIVEAU_DE_VIE_D9_D1 = Figure(
    value=3.5, unit="ratio", year=2023, scope="Rapport interdécile D9/D1 du niveau de vie",
    source="INSEE, Filosofi 2023", url=FILOSOFI_URL, use="validation",
    caveat="A pure shape statistic, unaffected by the wage-bill level we calibrated "
           "on — but no longer the branch's most informative line, and the demotion is "
           "on the record. It read +39 % and was cited as the headline proof that the "
           "synthetic distribution's shape was wrong; most of that was a WRONG "
           "ESTIMATOR, a ratio of decile means against INSEE's ratio of person-weighted "
           "thresholds (D-073). Read as published, +3,6 %. What carries that argument "
           "now is the +112 % allègements backtest, which is a published costing and "
           "does not depend on our choice of statistic. Still conditionally valid: this "
           "line sits inside tolerance with NO capital income on our side and capital "
           "in the target.",
)

#: Number of dependent children (under 25, INSEE's "enfant d'une famille") by
#: family type, as a probability vector over 0, 1, 2, ... children. Derived from
#: the 2023 family counts below; the published "4 or more" class is split 70/30
#: between 4 and 5, which is an assumption about a class holding 0.4 M families.
#:
#:   couples with children  1: 2.640 M  2: 2.809 M  3: 0.978 M  4+: 0.346 M
#:   lone parents           1: 1.444 M  2: 0.785 M  3: 0.241 M  4+: 0.096 M
#:
#: These count children under 25, which is the same population the EEC shows us
#: partially (its 15-24s) — so the draw is for the household *total* and the
#: children already visible are subtracted, never added to.
CHILDREN_PER_FAMILY: dict[str, list[float]] = {
    # TYPLOG5 "2" — famille monoparentale
    "2": [0.0, 0.5628, 0.3060, 0.0940, 0.0261, 0.0111],
    # TYPLOG5 "4" — couple avec enfant(s)
    "4": [0.0, 0.3898, 0.4148, 0.1444, 0.0357, 0.0153],
}

#: Under-15s the synthesis has to produce. Published as children who are an
#: "enfant d'une famille" — living with at least one resident parent — so it is a
#: LOWER BOUND on the under-15 population of ordinary households, short by roughly
#: 250 000 (about 2 %) for children living with neither parent.
CHILDREN_UNDER_15 = Figure(
    value=11_391_293, unit="count", year=2023,
    scope="Enfants des familles âgés de 0 à 14 ans, France hors Mayotte, logements ordinaires",
    source="INSEE, recensement de la population 2023",
    url="https://www.insee.fr/fr/statistiques/2381486", use="calibration",
    caveat="A lower bound: excludes under-15s not attached to a resident parent. "
           "The synthesis targets this figure plus that ~2 % residual.",
)

CHILDREN_DISTRIBUTION = Figure(
    value=9.34e6, unit="count", year=2023,
    scope="Familles avec au moins un enfant de moins de 25 ans, France",
    source="INSEE, recensement de la population — séries famille",
    url="https://www.insee.fr/fr/statistiques/8268533", use="calibration",
    caveat="Used to synthesise the under-15 children the EEC omits, so it is spent. "
           "INSEE's 'enfant d'une famille' is broader than the tax definition of a "
           "dependant: it covers any child living with a parent who has no partner "
           "or child of their own, at any age. Capping the draw at children under 25 "
           "keeps the two roughly aligned but does not make them identical.",
)

#: Households by type — the raking margin that actually does work (D-017).
#: Census 2023 counts, France. Our household is a dwelling-quarter and INSEE's is
#: a dwelling, which is why the total (31.27 M) is compared rather than imposed.
#: `couple_sans_enfant` is published rounded (7.80 M) and is carried here as the
#: residual against the household total, so the parts sum to the whole exactly.
#: Raking to components that do not add up to their own total makes IPF chase a
#: contradiction, and `test_household_margins_sum_to_the_published_total` pins it.
HOUSEHOLDS_BY_TYPE: dict[str, float] = {
    "personne_seule": 12_224_900.0,
    "couple_sans_enfant": 7_799_800.0,
    "couple_avec_enfant": 7_162_000.0,
    "monoparentale": 2_965_000.0,
    "complexe": 1_123_000.0,
}

HOUSEHOLD_TYPES = Figure(
    value=31_274_700.0, unit="count", year=2023,
    scope="Ménages par type, France — exploitation complémentaire du recensement",
    source="INSEE, recensement de la population 2023",
    url="https://www.insee.fr/fr/statistiques/2381486", use="calibration",
    caveat="Spent once raking runs against it. INSEE's household is a dwelling; "
           "ours is a dwelling-quarter, and the typology is derived from entity "
           "roles rather than from the EEC's TYPLOG5 so that the same margin "
           "survives the move to ERFS.",
)

#: Households, from the census. Reproduced by construction from EEC weights
#: (31.45 M against ~31 M published), which is a check on the weighting rather
#: than on the model.
HOUSEHOLDS = Figure(
    value=31_274_700.0, unit="count", year=2023, scope="Nombre de ménages, France",
    source="INSEE, recensement de la population 2023 — exploitation complémentaire",
    url="https://www.insee.fr/fr/statistiques/2381486", use="calibration",
    caveat="Spent since D-017: HOUSEHOLDS_BY_TYPE sums to exactly this, and raking "
           "targets it. It was a validation line only while nothing was fitted to "
           "it — and it was previously compared against the 2022 count (31.0 M), "
           "which flattered the residual to +0.0 % against a target the raking was "
           "not even aiming at.",
)


# --------------------------------------------------------------------------- #
# Foyers fiscaux as the DGFiP counts them (but 19, étape 3).
#
# A foyer fiscal is a déclaration, not a dwelling: concubins file two, a young adult
# who is not rattaché files his own. The skeleton draws both from the figures below;
# the famille (CAF) is left as it was, so that the benefits see the same households.
# --------------------------------------------------------------------------- #
POP3_URL = "https://www.insee.fr/fr/statistiques/fichier/8202264/TD_POP3_2021_csv.zip"

#: Share of the persons living in a couple who are in « concubinage ou union libre »
#: (STAT_CONJ_19 = 3 over 1 + 2 + 3), by quinquennial age (lower bound; 80 = 80 or
#: more). Recomputed from TD_POP3_2021, lines NIVGEO = COM summed, both sexes.
UNION_LIBRE_SHARE_BY_AGE: dict[int, float] = {
    15: 0.863051, 20: 0.727370, 25: 0.505629, 30: 0.325125, 35: 0.249017,
    40: 0.206582, 45: 0.185745, 50: 0.158176, 55: 0.122499, 60: 0.084792,
    65: 0.060995, 70: 0.044832, 75: 0.035380, 80: 0.026810,
}

UNION_LIBRE_SHARE = Figure(
    value=0.188, unit="ratio", year=2021,
    scope="Personnes de 15 ans ou plus en couple : part en concubinage ou union libre "
          "(6,11 M sur 32,49 M), France hors Mayotte",
    source="Insee, recensement 2021, tableau détaillé TD_POP3 (sexe, âge, statut "
           "conjugal)",
    url=POP3_URL, use="calibration",
    caveat="Spent: the skeleton splits each paired couple into two foyers fiscaux with "
           "the mean of its two members' shares, by age. The draw ignores who, in "
           "reality, is married (concubins are younger and more often both in work than "
           "an age-only draw says). The famille (CAF) is not split.",
)

#: Enfants célibataires majeurs rattachés au foyer fiscal de leurs parents, case 0DJ
#: (the second column of the export, the number of children, not of foyers).
RATTACHES_MAJEURS = Figure(
    value=2_014_392, unit="count", year=2024,
    scope="Nombre d'enfants célibataires rattachés (case 0DJ, nombre d'enfants), "
          "déclarations des revenus 2024 ; 1 720 889 foyers",
    source="DGFiP, « L'impôt sur le revenu : les déclarations nationales » (2042), "
           "export manifesté dgfip_ir_2042_nat_export_2026-10-15.csv",
    url="https://data.economie.gouv.fr/explore/dataset/ir-declarations-2042-nat/",
    use="calibration",
    caveat="Spent: the probability that an eligible young adult living with his parents "
           "is rattaché is set so that the weighted rattachés reach it. 0DJ also counts "
           "rattachés who do not live with their parents (students in their own "
           "dwelling), whom the EEC puts in a household of their own: the model, which "
           "can only rattach a co-resident child, therefore rattaches a little too many "
           "of those it sees. How many is not published.",
)

#: Enfants des familles aged 18 to 24, ordinary households, France hors Mayotte.
FAM6_URL = "https://www.insee.fr/fr/statistiques/fichier/8205229/TD_FAM6v1_2021_csv.zip"
CHILDREN_18_24 = Figure(
    value=2_930_587, unit="count", year=2021,
    scope="Enfants des familles âgés de 18 à 24 ans (AGEFOR5 = 18), France hors Mayotte",
    source="Insee, recensement 2021, tableau détaillé TD_FAM6v1 (enfants par âge et type "
           "de famille), lignes NIVGEO = COM",
    url=FAM6_URL, use="calibration",
    caveat="Anchors the share of 18-24-year-olds living as a child of the family; the "
           "shape inside the band is regional (CHILD_SHARE_SHAPE).",
)

#: Persons of 15-19 and 20-24 years in ordinary households (CATPR = 01), census 2021,
#: TD_POP2 (already manifested), lines NIVGEO = COM. Spread evenly over the five years.
ORDINARY_HOUSEHOLD_POPULATION_15_24: dict[int, float] = {15: 4_024_913.0, 20: 3_673_432.0}

#: Share of young people living with their parents, by single year of age: Nouvelle-
#: Aquitaine, census 2013, Insee Flash Nouvelle-Aquitaine n° 21, figure 1
#: (https://www.insee.fr/fr/statistiques/2573899): 72,1 % at 18, 51,1 % at 20, 37,3 % at
#: 22, 20,7 % at 25. 19, 21, 23 and 24 are interpolated, 15 to 17 are an assumption near
#: the 98,1 % of under-18s that SL_PERS1 (RP 2022) counts as children of a family. No
#: national table by single year of age was found (searched: Insee Première n° 1686,
#: RP séries longues SL_PERS1, TD_FAM6, all banded). The SHAPE only is used: the level
#: of 18-24 is moved, by one shift on the logit scale, onto CHILDREN_18_24.
CHILD_SHARE_SHAPE: dict[int, float] = {
    15: 0.97, 16: 0.97, 17: 0.97,
    18: 0.721, 19: 0.616, 20: 0.511, 21: 0.442, 22: 0.373, 23: 0.318, 24: 0.262,
}

# --------------------------------------------------------------------------- #
# Housing tenure — a raking margin (but 19, étape 3, D-365).
# --------------------------------------------------------------------------- #
LOG_T10_URL = "https://www.insee.fr/fr/statistiques/2011101?geo=FE-1"

#: Résidences principales by statut d'occupation, RP 2023, LOG T10, France.
TENURE_2023: dict[str, float] = {
    "proprietaire": 17_944_861.0,
    "locataire_hlm": 4_546_449.0,
    "locataire_autre": 12_584_249.0 - 4_546_449.0,
    "loge_gratuitement": 691_037.0,
}

HOUSEHOLDS_BY_TENURE = Figure(
    value=31_220_147.0, unit="count", year=2023,
    scope="Résidences principales selon le statut d'occupation : propriétaires "
          "(accédants compris), locataires d'un logement HLM loué vide, autres locataires "
          "(vide non HLM, meublé, chambre d'hôtel), logés gratuitement",
    source="Insee, RP 2023, exploitation principale, tableau LOG T10",
    url=LOG_T10_URL, use="calibration",
    caveat="Spent once the raking targets it. Its total (31,22 M) is not the household "
           "total of HOUSEHOLDS_BY_TYPE (31,27 M, exploitation complémentaire): the "
           "shares are kept and scaled onto the latter, so that the two margins do not "
           "contradict each other (D-150). The EEC's usufruitiers are owners.",
)


def tenure_targets() -> dict[str, float]:
    """LOG T10's shares on the household total the type margin holds."""
    total = sum(TENURE_2023.values())
    return {key: value / total * HOUSEHOLDS.value for key, value in TENURE_2023.items()}


def figures_by_use(use: Use) -> dict[str, Figure]:
    """Every module-level `Figure` declared with the given use."""
    return _figures_by_use(globals(), use)
