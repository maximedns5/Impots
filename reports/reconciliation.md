# Reconciliation report

**Population vintage**: `2024` · **Generated**: 2026-08-28 by `impots population reconcile` · **Engine**: openfisca-france 176.0.8

How far the synthetic population's simulated aggregates sit from published national totals. This page is the product, not an appendix: a distributional number is worth what this table says it is worth.

## The rule that makes this table mean something

A figure used to **calibrate** the population is *spent*. The model was tuned to hit it, so hitting it is evidence of nothing except that the tuning ran. Those lines are listed separately and are never counted as validation. Everything in the validation table below was **not** tuned to.

## Calibration targets (spent)

| Line | Simulated | Published | Residual | Source |
|---|---:|---:|---:|---|
| Masse salariale brute | 1 107.7 bn € | 1 111.7 bn € | -0.4% | INSEE comptes nationaux (D11) |
| Pensions et retraites | — | 400.4 bn € | — | DGFiP |
| Allocations chômage | — | 35.9 bn € | — | Unédic |

## Validation lines (untouched by calibration)

| Line | Simulated | Published | Residual | Tolerance | Status | Source |
|---|---:|---:|---:|---:|---|---|
| Impôt sur le revenu — barème | 107.7 bn € | 98.8 bn € | +8.9% | ±10% | within tolerance | DGFiP |
| Impôt sur le revenu — recettes nettes | 107.7 bn € | 88.0 bn € | +22.4% | ±10% | OUTSIDE tolerance | budget.gouv.fr |
| Salaires déclarés (imposables) | 911.3 bn € | 932.1 bn € | -2.2% | ±10% | within tolerance | DGFiP |
| Foyers fiscaux | 34.99 M | 41.64 M | -16.0% | ±10% | OUTSIDE tolerance | DGFiP |
| Foyers imposés | 19.22 M | 19.68 M | -2.3% | ±10% | within tolerance | DGFiP |
| Allocations familiales | 10.4 bn € | 13.8 bn € | -24.6% | ±25% | within tolerance | CNAF / DREES |
| Prime d'activité (bridge-adjusted) | 7.8 bn € | 10.7 bn € | -27.2% | ±13% | OUTSIDE tolerance | CNAF / DREES |
| Prime d'activité | 13.4 bn € | 10.7 bn € | +25.6% | ±25% | OUTSIDE tolerance | CNAF / DREES |
| RSA (bridge-adjusted) | 18.8 bn € | 12.4 bn € | +52.1% | ±14% | OUTSIDE tolerance | CNAF / DREES |
| RSA | 25.5 bn € | 12.4 bn € | +106.0% | ±25% | OUTSIDE tolerance | CNAF / DREES |
| Aides au logement | 11.9 bn € | 16.0 bn € | -25.3% | ±25% | OUTSIDE tolerance | CNAF / DREES |
| Niveau de vie médian | 22 646 | 25 920 | -12.6% | ±15% | within tolerance | INSEE Filosofi 2023 |
| Rapport interdécile D9/D1 | 5 | 4 | +41.3% | ±15% | OUTSIDE tolerance | INSEE Filosofi 2023 |
| Ménages | 31.45 M | 31.00 M | +1.5% | ±15% | within tolerance | INSEE recensement |

### What each line means

* **Masse salariale brute** — Calibrated: the wage level was scaled to hit this. It proves the scaling worked, nothing more.
* **Pensions et retraites** — Calibrated: the pension mass was scaled to hit this.
* **Allocations chômage** — Calibrated: the benefit mass was scaled to hit this.
* **Impôt sur le revenu — barème** — The right comparator for this model: our households have none of the réductions et crédits d'impôt (19.5 bn) that separate the barème from the net yield, and no capital income.
* **Impôt sur le revenu — recettes nettes** — Shown for completeness and expected to be missed high: this figure is net of réductions/crédits and includes the PFU on capital income, neither of which the model has.
* **Salaires déclarés (imposables)** — Semi-independent: the gross wage level is calibrated, so this tests the engine's gross-to-taxable transformation rather than the population.
* **Foyers fiscaux** — Structural, and one of the few lines untouched by the wage calibration: it depends on how the population was assembled into tax units, not on how much anybody earns.
* **Foyers imposés** — Depends on both the assembly and the income distribution near the tax threshold, so it is the sharpest available test of the middle of the synthetic wage distribution.
* **Allocations familiales** — No published take-up bridge for this benefit; judged on the flat ±25 % benefit tolerance.
* **Prime d'activité (bridge-adjusted)** — Simulated entitlement divided by the mid-point of the take-up bridge (1.73), which is what should be comparable with observed spend.
* **Prime d'activité** — OpenFisca computes legal entitlement, so this line *should* exceed observed spend by a factor of 1.68-1.77 (DREES ER n° 1370/1379). Landing inside that band is the target; landing above it means something other than non-take-up is at work.
* **RSA (bridge-adjusted)** — Simulated entitlement divided by the mid-point of the take-up bridge (1.35), which is what should be comparable with observed spend.
* **RSA** — OpenFisca computes legal entitlement, so this line *should* exceed observed spend by a factor of 1.30-1.41 (DREES ER n° 1370/1379). Landing inside that band is the target; landing above it means something other than non-take-up is at work.
* **Aides au logement** — No published take-up bridge for this benefit; judged on the flat ±25 % benefit tolerance.
* **Niveau de vie médian** — Mean of decile 5, against the published median: close but not the same statistic. Filosofi is a 2023 vintage in 2023 euros.
* **Rapport interdécile D9/D1** — A pure shape statistic, unaffected by the wage level we calibrated — the most informative single line in this table.
* **Ménages** — Reproduced from the EEC weights; a check on the weighting, not on the model.

## Verdict

**8 validation line(s) outside declared tolerance**: Impôt sur le revenu — recettes nettes (+22%), Foyers fiscaux (-16%), Prime d'activité (bridge-adjusted) (-27%), Prime d'activité (+26%), RSA (bridge-adjusted) (+52%), RSA (+106%), Aides au logement (-25%), Rapport interdécile D9/D1 (+41%)

Per §5 of the Phase 1 specification these are stated, not smoothed over. The known causes are listed below; none of them is fixed by tuning, and tuning to close them would spend the very lines that make this table worth reading.

## Known limitations of this population

* **No income is observed.** The EEC fichier détail carries no wage, pension or benefit of any kind (docs/M0_RECON.md). Every euro in this population is drawn from a published distribution and calibrated to a published total.
* **No self-employment income.** 3.87 M people are recorded in employment as indépendants and receive nothing, which understates their households and overstates their entitlement to means-tested benefits.
* **No capital income, no property income.** The top of the distribution is a construction; nothing above roughly the 95th percentile is publishable.
* **No réductions or crédits d'impôt.** Worth 19.5 bn nationally, which is why the income tax line is compared against the barème rather than the net yield.
* **Children under 15 are synthesised**, not observed: their number is drawn from published family-size margins and their ages uniformly. Household composition above 15 is real.
* **Age is banded.** The EEC gives five age groups; exact ages are drawn inside them, so any threshold that does not fall on a band edge is fuzzy for an individual household and only right on average.
* **Benefits assume 100 % take-up.** OpenFisca computes legal entitlement; DREES measures non-take-up of RSA at 33-37 % of eligible households.
* **Assortative mating is absent.** Two earners in a household are drawn independently, which flattens the top of the household income distribution.

## Sources

| Figure | Year | Scope | Source |
|---|---|---|---|
| `CHILDREN_DISTRIBUTION` | 2023 | Familles avec au moins un enfant de moins de 25 ans, France | [INSEE, recensement de la population — séries famille](https://www.insee.fr/fr/statistiques/8268533) |
| `CHILDREN_UNDER_15` | 2023 | Enfants des familles âgés de 0 à 14 ans, France hors Mayotte, logements ordinaires | [INSEE, recensement de la population 2023](https://www.insee.fr/fr/statistiques/2381486) |
| `DECLARED_PENSIONS` | 2024 | Pensions, retraites et rentes déclarées | [DGFiP](https://www.impots.gouv.fr/statistiques) |
| `TOTAL_GROSS_WAGES` | 2024 | D11 « salaires et traitements bruts », ensemble de l'économie, comptes nationaux base 2020, compte SEMI-DÉFINITIF — tous secteurs, tous employeurs | [INSEE, « Les comptes de la Nation en 2025 » (29 mai 2026), tableau 6205](https://www.insee.fr/fr/statistiques/8988833) |
| `UNEMPLOYMENT_BENEFIT_SPEND` | 2024 | Allocations chômage et aides au reclassement versées par l'Assurance chômage | [Unédic, Situation financière de l'Assurance chômage 2025-2027 (juin 2025)](https://www.unedic.org/publications) |
| `BENEFIT_RECIPIENTS[af]` | 2024 | Allocataires AF au 31/12, CAF, France entière | [CNAF](https://www.caf.fr/allocataires/caf-du-nord/statistiques) |
| `BENEFIT_RECIPIENTS[aide_logement]` | 2024 | Allocataires d'une aide au logement au 31/12, tous régimes | [DREES, Panorama Minima sociaux 2025, vue d'ensemble tableau 2](https://www.caf.fr/allocataires/caf-du-nord/statistiques) |
| `BENEFIT_RECIPIENTS[ppa]` | 2024 | Allocataires prime d'activité au 31/12, tous régimes | [DREES, Panorama Minima sociaux 2025, vue d'ensemble tableau 2](https://www.caf.fr/allocataires/caf-du-nord/statistiques) |
| `BENEFIT_RECIPIENTS[rsa]` | 2024 | Foyers allocataires du RSA au 31/12, tous régimes | [DREES, Panorama Minima sociaux 2025, vue d'ensemble tableau 2](https://www.caf.fr/allocataires/caf-du-nord/statistiques) |
| `BENEFIT_SPEND[af]` | 2024 | Allocations familiales, tous régimes, France entière | [CNAF](https://www.caf.fr/allocataires/caf-du-nord/statistiques) |
| `BENEFIT_SPEND[aide_logement]` | 2024 | Aides au logement (APL + ALS + ALF), tous régimes, France entière | [CNAF](https://www.caf.fr/allocataires/caf-du-nord/statistiques) |
| `BENEFIT_SPEND[ppa]` | 2024 | Prime d'activité, tous régimes, France entière | [CNAF](https://www.caf.fr/allocataires/caf-du-nord/statistiques) |
| `BENEFIT_SPEND[rsa]` | 2024 | RSA, tous régimes, France entière (dont prime de Noël) | [CNAF](https://www.caf.fr/allocataires/caf-du-nord/statistiques) |
| `DECLARED_WAGES` | 2024 | Traitements et salaires déclarés à l'impôt sur le revenu | [DGFiP](https://www.impots.gouv.fr/statistiques) |
| `FOYERS_FISCAUX` | 2024 | Nombre de foyers fiscaux, revenus 2024, France entière + non-résidents | [DGFiP/DESF, IRCOM 2025 (revenus 2024), fichier national, ligne Total](https://www.impots.gouv.fr/statistiques) |
| `FOYERS_IMPOSES` | 2024 | Foyers fiscaux imposés (impôt dû non nul), revenus 2024 | [DGFiP/DESF, IRCOM 2025 (revenus 2024)](https://www.impots.gouv.fr/statistiques) |
| `IR_BAREME_ON_2024_INCOME` | 2024 | Impôt sur les revenus de 2024 soumis au barème, avant réductions et crédits | [DGFiP, statistiques sur l'impôt sur le revenu](https://www.impots.gouv.fr/statistiques) |
| `IR_NET_YIELD` | 2024 | Impôt sur le revenu, recettes nettes de l'État, exécution budgétaire | [budget.gouv.fr, exécution 2024](https://www.budget.gouv.fr/) |
| `NIVEAU_DE_VIE_D9_D1` | 2023 | Rapport interdécile D9/D1 du niveau de vie | [INSEE, Filosofi 2023](https://www.insee.fr/fr/statistiques/8402386) |
| `NIVEAU_DE_VIE_GINI` | 2023 | Indice de Gini du niveau de vie, métropole | [INSEE, Filosofi 2023](https://www.insee.fr/fr/statistiques/8402386) |
| `NIVEAU_DE_VIE_MEDIAN` | 2023 | Médiane du niveau de vie, France métropolitaine, ménages fiscaux en logement ordinaire | [INSEE, Filosofi 2023](https://www.insee.fr/fr/statistiques/8402386) |
| `HOUSEHOLDS` | 2022 | Nombre de ménages, France | [INSEE, recensement de la population 2022](https://www.insee.fr/fr/statistiques/8268533) |
| `NET_TO_GROSS_RATIO` | 2024 | Salariés du secteur privé, ensemble : salaire net / salaire brut | [INSEE, Base Tous Salariés 2024](https://www.insee.fr/fr/statistiques/8568701) |
| `PRIVATE_EMPLOYEES` | 2024 | Effectif salarié moyen annuel du secteur privé, champ Urssaf | [Urssaf Caisse nationale](https://open.urssaf.fr/explore/dataset/masse-salariale-du-secteur-prive/) |
| `PRIVATE_WAGE_BILL` | 2024 | Masse salariale du secteur privé (champ Urssaf), France entière | [Urssaf Caisse nationale, open.urssaf.fr](https://open.urssaf.fr/explore/dataset/masse-salariale-du-secteur-prive/) |
| `RENT_PER_M2[prive]` | 2024 | Loyer au m² des locataires du parc privé | [INSEE, France portrait social 2024 — dépenses de logement](https://www.insee.fr/fr/statistiques/8612568) |
| `RENT_PER_M2[social]` | 2024 | Loyer au m² des locataires du parc social | [INSEE, France portrait social 2024 — dépenses de logement](https://www.insee.fr/fr/statistiques/8612568) |
| `RSA_NON_TAKE_UP` | 2021 | Taux de non-recours au RSA, en % des foyers éligibles un trimestre donné (fourchette publiée 33-37 %) | [DREES, Études et Résultats n° 1370](https://drees.solidarites-sante.gouv.fr/publications-communique-de-presse/etudes-et-resultats/quantifier-le-non-recours-au-rsa) |
