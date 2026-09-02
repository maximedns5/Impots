# Reconciliation report — entreprises

**Vintage**: `2023` · **Generated**: 2026-09-02 by `impots entreprises reconcile` · **Engine**: openfisca-core 44.7.0 (système propre, hors openfisca-france)

How far the synthetic firm population's simulated aggregates sit from published national totals. Read the fidelity column before the residual column: several lines here are reproduced by construction and prove only that the build works.

## The rule that makes this table mean something

A figure used to **calibrate** is *spent*. The model was tuned to hit it, so hitting it is evidence of nothing except that the tuning ran. Those lines are listed separately and are never counted as validation. Everything in the validation table below was **not** tuned to.

## Calibration targets (spent)

| Line | Simulated | Published | Residual | Source |
|---|---:|---:|---:|---|
| Bénéfice imposable total | 284.0 bn € | 284.0 bn € | +0.0% | DGFiP |
| Entreprises redevables | 2.72 M | 2.72 M | -0.0% | DGFiP |
| Part sans bénéfice imposable | 0.39 | 0.38 | +3.8% | DGFiP |

## Validation lines (untouched by calibration)

| Line | Simulated | Published | Residual | Tolerance | Status | Source |
|---|---:|---:|---:|---:|---|---|
| Impôt sur les sociétés | 69.3 bn € | 69.5 bn € | -0.2% | ±20% | within tolerance | INSEE comptes nationaux |
| Taux moyen d'IS sur les bénéfices | 0.24 | 0.24 | +0.6% | ±15% | within tolerance | DGFiP |
| Contribution sociale sur l'IS | 1.4 bn € | 1.5 bn € | -3.9% | ±25% | within tolerance | budget.gouv.fr |
| Contribution exceptionnelle (CEBGE) | 9.3 bn € | 7.5 bn € | +23.1% | ±25% | within tolerance | budget.gouv.fr |
| CVAE | 3.3 bn € | 4.0 bn € | -18.4% | ±25% | within tolerance | budget.gouv.fr |
| C3S | 5.3 bn € | 5.2 bn € | +1.2% | ±25% | within tolerance | CCSS |
| IS — Industrie | 21.1 bn € | 15.2 bn € | +38.3% | ±20% | OUTSIDE tolerance | DGFiP |
| IS — Commerce, transports, hébergement | 19.3 bn € | 18.9 bn € | +2.0% | ±20% | within tolerance | DGFiP |
| IS — Construction | 5.8 bn € | 5.0 bn € | +16.8% | ±20% | within tolerance | DGFiP |
| IS — Activités spécialisées et de soutien | 10.8 bn € | 9.2 bn € | +17.7% | ±20% | within tolerance | DGFiP |
| IS — Activités immobilières | 1.1 bn € | 3.9 bn € | -70.9% | ±20% | OUTSIDE tolerance | DGFiP |
| IS — Information et communication | 2.8 bn € | 3.5 bn € | -21.4% | ±20% | OUTSIDE tolerance | DGFiP |

### What each line means

* **Bénéfice imposable total** — **Spent, and it is the most consequential spend in this table.** The cell table's fiscal-to-accounting ratio is computed to reproduce this total, so hitting it is arithmetic. Everything the IS level does downstream inherits that — see the next line.
* **Impôt sur les sociétés** — **The level of this line is calibrated and the rate is not.** The taxable profit above is reproduced by construction, and IS is roughly a quarter of it, so landing near the published total is most of the way guaranteed. What this line still tests is whether applying the real schedule — the 15 % slice, its ceilings, its eligibility — to a *synthetic distribution* of a correct total lands where the published tax does. That test is the line below, and it is the one to read. Biased upward by the absence of loss carry-forward.
* **Taux moyen d'IS sur les bénéfices** — **The free test, and the one the module should be judged on.** Total IS over total taxable profit. The denominator is calibrated and the numerator is not: it comes from applying the statutory schedule to a synthetic distribution that nothing pinned. If the distribution were wrong — too many firms in the 15 % slice, too few above it — this rate would miss even though the level above did not.
* **IS — recettes nettes (pour mémoire)** — Expected to be missed high, and shown for that reason: this figure is net of 24.6 bn of remboursements et dégrèvements and of every crédit d'impôt, none of which the model has.
* **Contribution sociale sur l'IS** — Mechanically downstream of the IS line — it is 3.3 % of IS above a 763 000 € abattement — so it carries the IS residual plus the composition of firms around that abattement, and is not independent evidence.
* **Contribution exceptionnelle (CEBGE)** — Published for 2025, the CEBGE's *first* exercice at a 1 bn threshold; the model runs 2026, the second, at 1.5 bn tested on that year alone. Different payers, so this sizes the instrument rather than scoring the year — and the model's stationarity assumption (D-022) cannot represent the entries and exits that threshold creates.
* **CVAE** — Published for 2025 at a 0.19 % maximum rate against a simulated year at 0.28 %, so a like-for-like comparison would scale the published figure by roughly 1.47 before reading the residual. Biased downward by the accounting value-added proxy, which does not add back rents and crédit-bail (D-021).
* **C3S** — The cleanest line in the table: the base is turnover, which is calibrated per cell, and the rate is a flat 0.16 % above a 19 M€ abattement. A residual here is almost entirely the distribution of turnover *within* cells — the one thing in the population that no published source constrains. Graded against the C3S booked in 2024, which is the receipt assessed on 2023 turnover — the vintage this population carries. C3S due in year N is levied on year N-1 turnover, so comparing against the same year's receipt would be off by a year of nominal growth. The sectoral caps for banks and commissionnaires are still not modelled.
* **Entreprises redevables** — **Spent.** The cell table fixes the firm count per cell and the build reproduces it exactly; a non-zero residual here would mean the weighting broke, which is what the guard around it exists to catch.
* **Part sans bénéfice imposable** — **Spent.** P(loss) is an input to each cell's Bernoulli draw. It is printed because every IS line above is meaningless if it is wrong — not because hitting it is evidence.
* **IS — Industrie** — NAF B+C+D+E. One of the module's few genuinely free lines: the sector shape is Ésane's and the calibration is national and by size class, so nothing was fitted to this.
* **IS — Commerce, transports, hébergement** — NAF G+H+I. One of the module's few genuinely free lines: the sector shape is Ésane's and the calibration is national and by size class, so nothing was fitted to this.
* **IS — Construction** — NAF F. One of the module's few genuinely free lines: the sector shape is Ésane's and the calibration is national and by size class, so nothing was fitted to this.
* **IS — Activités spécialisées et de soutien** — NAF M+N. One of the module's few genuinely free lines: the sector shape is Ésane's and the calibration is national and by size class, so nothing was fitted to this.
* **IS — Activités immobilières** — NAF L. One of the module's few genuinely free lines: the sector shape is Ésane's and the calibration is national and by size class, so nothing was fitted to this.
* **IS — Information et communication** — NAF J. One of the module's few genuinely free lines: the sector shape is Ésane's and the calibration is national and by size class, so nothing was fitted to this.
* **Taux effectif moyen (moyenne par entreprise)** — Context, because it is not the same statistic as the published one and never was. This averages a *rate per firm* over all firms, so France's two and a half million micro-enterprises dominate it; DGFiP's figure is profit-weighted, so a few thousand large firms dominate that. The like-for-like comparison is the aggregate rate line above, which lands inside tolerance. Printed rather than dropped because it is the number a reader would otherwise compute themselves from the by-size table.
* **Écart de taux effectif GE − PME** — Context only, and it is expected to have the WRONG SIGN. INSEE's implicit rate falls with size because its denominator is ENE over all firms including loss-makers; the model's rises with size because C3S and CVAE hit turnover and value added whether or not there is a profit. The two measure different objects, and picking whichever one the model resembles would be calibrating to a validation line.

## Verdict

**3 validation line(s) outside declared tolerance**: IS — Industrie (+38.3%), IS — Activités immobilières (-70.9%), IS — Information et communication (-21.4%)

These are stated, not smoothed over. The known causes are listed below; none of them is fixed by tuning, and tuning to close them would spend the very lines that make this table worth reading.

## Known limitations

* ### What dominates these residuals
* 
* **Fiscal-to-accounting ratio: 0.501.** A single national scalar converts accounting result into taxable profit. Fiscal result is not accounting result and no open source publishes the difference per firm. This one choice moves the IS line more than anything else in the model, which is exactly why the IS tolerance is not narrowed: a tighter gate would be an invitation to tune this number until the line goes green, and a margin spent that way can never be evidence again.
* 
* **No loss carry-forward.** A real firm's deficits reduce its tax in later years; ours cannot, because carry-forward needs firm panels that are not open data. This biases simulated IS upward, mechanically.
* 
* **No fiscal integration.** Groups are modelled as independent legal units, which over-counts firms at the reduced rate — a member of an intégration fiscale is not an IS payer at all, only the parent is.
* 
* **No CFE.** It depends on communal valeur locative and thousands of local rates. A plausible-looking imitation would be worse than a declared hole.
* 
* **Within-cell dispersion is assumed, not published.** ESANE gives cell means and totals, never quantiles, so the shape inside a cell is declared (lognormal, sigma 1.4) rather than fitted. Every line whose residual depends on where firms sit *within* a cell — the C3S abattement, the CVAE schedule, the CEBGE thresholds — inherits that assumption. 38.9% of firms pay no IS in this build.

## Sources

| Figure | Year | Scope | Source |
|---|---|---|---|
| `AVERAGE_RATE_ON_PROFITS` | 2024 | Série publiée « Taux moyen d'imposition », graphique 2 de DGFiP Stat n° 39 (valeur 2024 : 24,256 %) — IS brut rapporté aux bénéfices déclarés | [DGFiP Statistiques n° 39, septembre 2025, graphique 2](https://www.impots.gouv.fr/statistiques) |
| `C3S` | 2025 | C3S encaissée, tous redevables | [Rapport à la Commission des comptes de la Sécurité sociale, mai 2026](https://www.securite-sociale.fr/accueil/rapport-ccss-mai-2026) |
| `C3S_2024` | 2024 | C3S encaissée en 2024, assise sur le chiffre d'affaires 2023 | [Rapport à la Commission des comptes de la Sécurité sociale, mai 2026 ; INSEE tableau 3.217](https://www.securite-sociale.fr/accueil/rapport-ccss-mai-2026) |
| `C3S_BY_BOOKING_YEAR[2024]` | 2024 | C3S encaissée en 2024, assise sur le chiffre d'affaires 2023 | [Rapport à la Commission des comptes de la Sécurité sociale, mai 2026 ; INSEE tableau 3.217](https://www.securite-sociale.fr/accueil/rapport-ccss-mai-2026) |
| `C3S_BY_BOOKING_YEAR[2025]` | 2025 | C3S encaissée, tous redevables | [Rapport à la Commission des comptes de la Sécurité sociale, mai 2026](https://www.securite-sociale.fr/accueil/rapport-ccss-mai-2026) |
| `CEBGE` | 2025 | Contribution exceptionnelle sur les bénéfices des grandes entreprises, premier exercice (ligne 1441) | [Exécution budgétaire 2025 ; INSEE tableau 3.217 ; Cour des comptes](https://www.budget.gouv.fr/documentation/file-download/33360) |
| `CONTRIBUTION_SOCIALE` | 2025 | Contribution sociale sur l'IS (3,3 %), ligne 1302 du budget de l'État | [Exécution budgétaire 2025, tableau 3](https://www.budget.gouv.fr/documentation/file-download/33360) |
| `CVAE` | 2025 | CVAE, ligne 1497 du budget de l'État | [Exécution budgétaire 2025 ; Voies et moyens tome I, PLF 2026](https://www.budget.gouv.fr/documentation/file-download/33360) |
| `FIRMS_LIABLE` | 2024 | Entreprises redevables de l'IS (unités légales) | [DGFiP Statistiques n° 39, septembre 2025](https://www.impots.gouv.fr/statistiques) |
| `IMPLICIT_RATE_GE` | 2022 | Taux implicite d'IS brut des grandes entreprises : IS brut / excédent net d'exploitation, pondéré par l'ENE, contribution sociale incluse, avant crédits | [INSEE Analyses n° 112, septembre 2025 (Arnal, Di Nallo, Martin), figure 4](https://www.insee.fr/fr/statistiques/8582116) |
| `IMPLICIT_RATE_PME` | 2022 | Taux implicite d'IS brut des PME, même définition | [INSEE Analyses n° 112, septembre 2025, figure 4](https://www.insee.fr/fr/statistiques/8582116) |
| `IS_AVANT_CREDITS` | 2025 | IS avant crédits d'impôt, comptabilité nationale, ensemble des sociétés | [INSEE, comptes nationaux base 2020, tableau 3.217](https://www.insee.fr/fr/statistiques/fichier/8571311/t_3217.xlsx) |
| `IS_BRUT` | 2025 | IS brut, ligne 1301 du budget de l'État, avant remboursements | [Exécution budgétaire 2025, tableaux 2 et 3](https://www.budget.gouv.fr/documentation/file-download/33360) |
| `IS_NET_DGFIP` | 2025 | IS net et contribution sociale sur les bénéfices, encaissements DGFiP tous affectataires | [DGFiP Statistiques n° 43, mars 2026, tableau 1](https://www.impots.gouv.fr/statistiques) |
| `IS_NET_RECETTES` | 2025 | IS net des remboursements et dégrèvements, recettes budgétaires de l'État | [Exécution budgétaire 2025 (DGFiP/Direction du budget) ; Cour des comptes, Le budget de l'État en 2025](https://www.budget.gouv.fr/documentation/file-download/33360) |
| `SHARE_NO_TAXABLE_PROFIT` | 2024 | Part des redevables de l'IS sans bénéfice imposable positif | [DGFiP Statistiques n° 39, septembre 2025 (972 000 déficitaires sur 2 718 377, plus environ 1,7 % à résultat nul)](https://www.impots.gouv.fr/statistiques) |
| `TAXABLE_PROFIT` | 2024 | Bénéfices déclarés par les entreprises bénéficiaires à l'IS, toutes tailles | [DGFiP Statistiques n° 39, septembre 2025, tableau 2](https://www.impots.gouv.fr/statistiques) |
