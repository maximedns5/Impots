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
# Revenus d'activité des non-salariés — Insee Première n° 2114 (juin 2026), revenus
# 2024, et ses tableaux complémentaires (IP2114.xlsx, au manifeste). Tout montant est
# MENSUEL, en euros, « déficits mis à 0 » : un exercice déficitaire compte pour un
# revenu nul. Le revenu de l'Insee est le revenu professionnel : pour un non-salarié
# « classique », le bénéfice (net des charges et des cotisations obligatoires) ou la
# rémunération du gérant ; pour un micro-entrepreneur, le chiffre d'affaires après
# l'abattement forfaitaire du régime micro. C'est, au gérant près, ce que la 2042-C-PRO
# déclare : 48,4 Md€ de BIC et de BNC réels professionnels en 2024 (DGFiP), contre
# 924 000 entrepreneurs individuels à 4 410 € par mois, 48,9 Md€ (Insee).
# --------------------------------------------------------------------------- #
NON_SALARIES_URL = "https://www.insee.fr/fr/statistiques/9013403"

#: Les non-salariés classiques (hors micro-entrepreneurs, hors agriculture), par
#: secteur : (effectif fin 2024 en milliers, part des revenus nuls ou déficitaires en
#: %, D1, Q1, médiane, Q3, D9 des revenus positifs, revenu moyen, part des gérants
#: majoritaires en %). Tableau complémentaire 3 pour l'effectif, la part nulle et les
#: quantiles ; tableau complémentaire 1 pour la moyenne et la part des gérants (2024).
#: « ensemble » est la ligne « Ensemble des non-salariés hors micro-entrepreneurs ».
CLASSIQUES_PAR_SECTEUR: dict[str, tuple[float, ...]] = {
    "industrie": (63, 12.4, 420, 1100, 2450, 4520, 7740, 3320, 72.82),
    "construction": (227, 7.5, 770, 1620, 2620, 3960, 6060, 3050, 69.8),
    "commerce_auto": (46, 12.2, 570, 1310, 2440, 3980, 6260, 2830, 78.86),
    "commerce_gros": (48, 16.5, 490, 1250, 2860, 5500, 9780, 3940, 74.06),
    "pharmacie": (24, 3.8, 2430, 3680, 5240, 7830, 11920, 6390, 87.4),
    "metiers_bouche": (36, 8.4, 620, 1370, 2280, 3600, 5490, 2650, 77.34),
    "detail_magasin": (119, 12.9, 410, 1040, 2140, 3710, 6210, 2650, 75.06),
    "detail_hors_magasin": (28, 17.1, 140, 430, 1120, 2360, 4160, 1560, 43.41),
    "transports": (60, 11.1, 430, 880, 1630, 2800, 4450, 2050, 43.72),
    "hebergement_restauration": (142, 17.3, 300, 880, 1780, 3030, 5000, 2080, 76.37),
    "information_communication": (43, 14.0, 650, 1840, 3880, 6300, 8990, 4190, 80.29),
    "finance": (45, 12.0, 800, 2330, 4700, 8580, 14360, 6170, 69.99),
    "immobilier": (42, 27.2, 260, 820, 2030, 4040, 7020, 2480, 57.0),
    "juridique": (105, 3.7, 1750, 3080, 5320, 9540, 16230, 8240, 26.1),
    "conseil": (60, 15.7, 570, 1440, 3310, 6130, 10270, 4510, 79.29),
    "architecture": (47, 10.0, 710, 1790, 3320, 5480, 8690, 4070, 72.12),
    "autres_specialisees": (30, 13.7, 420, 1050, 2240, 4120, 6840, 2950, 63.04),
    "veterinaires": (12, 2.7, 1880, 3480, 5670, 8530, 11940, 6370, 35.0),
    "services_administratifs": (45, 18.8, 450, 1200, 2540, 4700, 8310, 3370, 75.25),
    "arts": (23, 17.9, 210, 660, 1490, 2830, 5000, 2030, 51.76),
    "enseignement": (42, 11.8, 310, 800, 1640, 2750, 4450, 2020, 33.87),
    "services_personnels": (85, 8.9, 390, 870, 1540, 2340, 3440, 1710, 47.52),
    "medecins": (166, 1.8, 2780, 4980, 8090, 12880, 20090, 10180, 13.6),
    "paramedicaux": (279, 1.5, 1610, 2530, 3570, 4890, 6600, 3890, 2.211),
    "autres_sante": (29, 9.4, 400, 970, 1940, 3250, 5170, 2410, 29.08),
    "ensemble": (1864, 9.6, 650, 1550, 3000, 5300, 9360, 4150, 50.31),
}

#: Les micro-entrepreneurs économiquement actifs, par secteur : (effectif fin 2024 en
#: milliers, revenu moyen, part des pluriactifs en %). Tableau complémentaire 2 pour
#: l'effectif et la moyenne, tableau complémentaire 1 pour les pluriactifs. Les
#: secteurs absents sont fermés au régime (pharmacie, droit, médecine, vétérinaires).
MICRO_PAR_SECTEUR: dict[str, tuple[float, float, float]] = {
    "industrie": (142, 370, 33.6),
    "construction": (219, 900, 12.3),
    "commerce_auto": (39, 530, 27.8),
    "commerce_gros": (38, 850, 25.1),
    "metiers_bouche": (6, 490, 32.1),
    "detail_magasin": (34, 550, 22.7),
    "detail_hors_magasin": (125, 340, 25.5),
    "transports": (91, 290, 44.1),
    "hebergement_restauration": (53, 660, 24.0),
    "information_communication": (112, 1060, 33.9),
    "finance": (10, 1090, 21.0),
    "immobilier": (44, 1030, 21.9),
    "conseil": (134, 1010, 34.2),
    "architecture": (34, 1160, 29.9),
    "autres_specialisees": (135, 720, 33.8),
    "services_administratifs": (184, 630, 33.7),
    "arts": (93, 510, 41.9),
    "enseignement": (184, 650, 45.7),
    "services_personnels": (266, 500, 28.7),
    "paramedicaux": (15, 1340, 35.2),
    "autres_sante": (86, 780, 41.6),
    "ensemble": (2047, 680, 31.5),
}

#: La dispersion des revenus positifs des micro-entrepreneurs, tous secteurs (D1, Q1,
#: médiane, Q3, D9), et leur part de revenus nuls en % : tableau complémentaire 3,
#: ligne « Micro-entrepreneurs économiquement actifs ». Le texte la donne aussi (« un
#: sur quatre gagne moins de 80 euros, un sur deux moins de 330, un sur dix plus de
#: 1 790 »). L'Insee ne la publie pas par secteur.
MICRO_QUANTILES: tuple[float, float, float, float, float] = (20, 80, 330, 950, 1790)
MICRO_PART_NULLE = 0.8

#: Les micro-entrepreneurs principalement salariés (texte, p. 3) : 28 % de l'ensemble,
#: 250 € par mois d'activité non salariée. L'enquête Emploi les compte parmi les
#: salariés, leur emploi principal : ils sortent du champ de la population, secteur par
#: secteur au prorata de ses pluriactifs (« près de neuf sur dix » des pluriactifs sont
#: principalement salariés : 28 sur les 31,5 % du tableau complémentaire 1).
MICRO_PRINCIPALEMENT_SALARIES = (28.0, 250.0)

#: À secteur identique, l'écart de revenu des femmes non salariées (texte, p. 4) :
#: −30 % chez les classiques, −14 % chez les micro-entrepreneurs.
ECART_FEMMES_CLASSIQUES = 0.30
ECART_FEMMES_MICRO = 0.14

#: Les non-salariés agricoles (encadré) : (effectif fin 2024 en milliers, revenu moyen
#: déficits mis à 0, part des revenus nuls ou déficitaires en %). L'Insee ne publie pas
#: leur dispersion : la forme est une hypothèse (`incomes.py`).
AGRICOLES: dict[str, tuple[float, float, float]] = {
    "reel": (302, 2410, 21.7),
    "micro_ba": (101, 810, 2.1),
}

#: Le versement libératoire parmi les micro-entrepreneurs, par nature d'activité :
#: cases remplies de la 2042-C-PRO, revenus 2024, avec le versement contre sans (DGFiP,
#: déclarations nationales 2042, au manifeste). Ventes : 5TA, 5UA contre 5KO, 5LO,
#: 5MO ; services : 5TB, 5UB, 5VB contre 5KP, 5LP, 5MP ; BNC : 5TE, 5UE contre 5HQ,
#: 5IQ, 5JQ. `test_non_salaries` les relit dans le fichier.
VERSEMENT_LIBERATOIRE: dict[str, tuple[int, int]] = {
    "vente": (229_159, 228_690),
    "service": (337_872, 349_143),
    "bnc": (281_611, 482_337),
}

#: Le total que la population doit porter, au champ de l'enquête Emploi : les
#: non-salariés dont c'est l'emploi principal. Effectifs fois revenus moyens publiés :
#: classiques 1 864 000 × 4 150 €, micro-entrepreneurs 2 047 000 × 680 € moins les
#: principalement salariés 0,28 × 2 047 000 × 250 €, agricoles au réel 302 000 × 2 410 €
#: et au micro-BA 101 000 × 810 € ; 9 793,9 M€ par mois, douze fois.
SELF_EMPLOYMENT_INCOME = Figure(
    value=117_526_800_000.0, unit="EUR", year=2024,
    scope="Revenus d'activité non salariés 2024 (déficits mis à 0) des non-salariés en "
          "activité au 31 décembre, hors micro-entrepreneurs principalement salariés, "
          "agriculture comprise, France hors Mayotte",
    source="INSEE, Insee Première n° 2114 (juin 2026), figure 1, encadré et texte ; "
           "effectifs fois revenus moyens",
    url=NON_SALARIES_URL, use="calibration",
    caveat="Dépensé : le revenu des non-salariés ne peut plus être une ligne de "
           "validation. Ce n'est pas une case publiée mais la somme de cinq produits "
           "publiés : l'Insee publie des effectifs et des revenus moyens, pas leur total. "
           "L'enquête Emploi compte 3,87 M de non-salariés dans leur emploi principal, "
           "contre 3,74 M dans ce champ : le calage baisse les revenus tirés d'environ "
           "3 %. Les gérants majoritaires (940 000, 3 880 €) y sont ; la DGFiP déclare "
           "leur rémunération en salaires (art. 62 du CGI), et les BIC, BNC et BA "
           "déclarés (2042-C-PRO) sont donc un autre total, plus petit.",
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
#: Insee, « Niveau de vie en 2023 : comparaisons régionales et départementales »
#: (Filosofi 2023), file `TCRD_022.xlsx` (https://www.insee.fr/fr/statistiques/fichier/
#: 2012717/TCRD_022.xlsx, sha256 1331aa54…65a5, read on 10 November 2026), sheet REG,
#: row « France métropolitaine » : median 25 920, D1 13 200, D9 46 500 EUR. The page
#: this constant named until but 19, 8402386, answers 404 (D-364).
FILOSOFI_URL = "https://www.insee.fr/fr/statistiques/2012717"

#: Deciles of niveau de vie, EUR per consumption unit per year, France
#: métropolitaine, Filosofi 2023: the three the page publishes. D2 to D8 (17 010 …
#: 38 100) stood here until but 19 and are found in no publication read (diagnostic
#: `famille_logement_niveau_de_vie.md`, C8) : withdrawn, not replaced. Nothing read them.
NIVEAU_DE_VIE_DECILES: dict[int, float] = {1: 13_200.0, 5: 25_920.0, 9: 46_500.0}

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
    caveat="Non retrouvé : la page de l'URL (TCRD_022) ne publie que D1, la médiane et "
           "D9 ; aucune ligne ne lit ce nombre (but 19, étape 1).",
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


def figures_by_use(use: Use) -> dict[str, Figure]:
    """Every module-level `Figure` declared with the given use."""
    return _figures_by_use(globals(), use)
