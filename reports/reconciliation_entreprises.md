# Reconciliation report — entreprises

**Vintage**: `fixture` · **Generated**: 2026-09-01 by `impots entreprises reconcile` · **Engine**: openfisca-core 44.7.0 (système propre, hors openfisca-france)

> **These residuals mean nothing.** This population was built from the committed fixture cell table, which is invented — not from SIRENE and ESANE. Every published figure below is therefore being compared against made-up sector totals, and a line that lands inside its tolerance has done so by coincidence. The table is here to show that the machinery runs end to end; it is not evidence about French corporate tax. Build from a real cell table before quoting a single number from this page.

How far the synthetic firm population's simulated aggregates sit from published national totals. Read the fidelity column before the residual column: several lines here are reproduced by construction and prove only that the build works.

## The rule that makes this table mean something

A figure used to **calibrate** is *spent*. The model was tuned to hit it, so hitting it is evidence of nothing except that the tuning ran. Those lines are listed separately and are never counted as validation. Everything in the validation table below was **not** tuned to.

## Calibration targets (spent)

| Line | Simulated | Published | Residual | Source |
|---|---:|---:|---:|---|
| Entreprises redevables | 1.10 M | 2.72 M | -59.7% | DGFiP |
| Part sans bénéfice imposable | 0.34 | 0.38 | -8.0% | DGFiP |

## Validation lines (untouched by calibration)

| Line | Simulated | Published | Residual | Tolerance | Status | Source |
|---|---:|---:|---:|---:|---|---|
| Impôt sur les sociétés | 20.4 bn € | 69.5 bn € | -70.6% | ±20% | OUTSIDE tolerance | INSEE comptes nationaux |
| Contribution sociale sur l'IS | 0.5 bn € | 1.5 bn € | -68.5% | ±25% | OUTSIDE tolerance | budget.gouv.fr |
| Contribution exceptionnelle (CEBGE) | 3.1 bn € | 7.5 bn € | -59.4% | ±25% | OUTSIDE tolerance | budget.gouv.fr |
| CVAE | 1.1 bn € | 4.0 bn € | -72.4% | ±25% | OUTSIDE tolerance | budget.gouv.fr |
| C3S | 2.1 bn € | 5.3 bn € | -59.8% | ±25% | OUTSIDE tolerance | CCSS |
| Taux effectif moyen | 0.10 | 0.24 | -56.9% | ±15% | OUTSIDE tolerance | DGFiP |

### What each line means

* **Impôt sur les sociétés** — **The ship gate.** Semi-independent: profit is not calibrated, but the fiscal-to-accounting ratio that converts it is derived from published DGFiP assiette totals, so this line is not fully free of its sources. Biased upward by the absence of loss carry-forward, and upward again by treating every group member as a separate unit.
* **IS — recettes nettes (pour mémoire)** — Expected to be missed high, and shown for that reason: this figure is net of 24.6 bn of remboursements et dégrèvements and of every crédit d'impôt, none of which the model has.
* **Contribution sociale sur l'IS** — Mechanically downstream of the IS line — it is 3.3 % of IS above a 763 000 € abattement — so it carries the IS residual plus the composition of firms around that abattement, and is not independent evidence.
* **Contribution exceptionnelle (CEBGE)** — Published for 2025, the CEBGE's *first* exercice at a 1 bn threshold; the model runs 2026, the second, at 1.5 bn tested on that year alone. Different payers, so this sizes the instrument rather than scoring the year — and the model's stationarity assumption (D-022) cannot represent the entries and exits that threshold creates.
* **CVAE** — Published for 2025 at a 0.19 % maximum rate against a simulated year at 0.28 %, so a like-for-like comparison would scale the published figure by roughly 1.47 before reading the residual. Biased downward by the accounting value-added proxy, which does not add back rents and crédit-bail (D-021).
* **C3S** — The cleanest line in the table: the base is turnover, which is calibrated per cell, and the rate is a flat 0.16 % above a 19 M€ abattement. A residual here is almost entirely the distribution of turnover *within* cells — the one thing in the population that no published source constrains. Two known offsets first: receipts booked in a year are assessed on the *previous* year's turnover, which the model does not have, and the sectoral caps for banks and commissionnaires are not modelled.
* **Entreprises redevables** — **Spent.** The cell table fixes the firm count per cell and the build reproduces it exactly; a non-zero residual here would mean the weighting broke, which is what the guard around it exists to catch.
* **Part sans bénéfice imposable** — **Spent.** P(loss) is an input to each cell's Bernoulli draw. It is printed because every IS line above is meaningless if it is wrong — not because hitting it is evidence.
* **Taux effectif moyen** — Read the caveat before the residual. The model's statistic is not either published one: its denominator is taxable profit (like DGFiP's) but loss-makers stay in the average at zero (like INSEE's). It should therefore land *below* the DGFiP figure by roughly the share of loss-makers, and a line that matched it exactly would be the suspicious outcome.
* **Écart de taux effectif GE − PME** — Context only, and it is expected to have the WRONG SIGN. INSEE's implicit rate falls with size because its denominator is ENE over all firms including loss-makers; the model's rises with size because C3S and CVAE hit turnover and value added whether or not there is a profit. The two measure different objects, and picking whichever one the model resembles would be calibrating to a validation line.

## Verdict

**6 validation line(s) outside declared tolerance**: Impôt sur les sociétés (-70.6%), Contribution sociale sur l'IS (-68.5%), Contribution exceptionnelle (CEBGE) (-59.4%), CVAE (-72.4%), C3S (-59.8%), Taux effectif moyen (-56.9%)

These are stated, not smoothed over. The known causes are listed below; none of them is fixed by tuning, and tuning to close them would spend the very lines that make this table worth reading.

## Known limitations

* ### What dominates these residuals
* 
* **Fiscal-to-accounting ratio: 0.820.** A single national scalar converts accounting result into taxable profit. Fiscal result is not accounting result and no open source publishes the difference per firm. This one choice moves the IS line more than anything else in the model, which is exactly why the IS tolerance is not narrowed: a tighter gate would be an invitation to tune this number until the line goes green, and a margin spent that way can never be evidence again.
* 
* **No loss carry-forward.** A real firm's deficits reduce its tax in later years; ours cannot, because carry-forward needs firm panels that are not open data. This biases simulated IS upward, mechanically.
* 
* **No fiscal integration.** Groups are modelled as independent legal units, which over-counts firms at the reduced rate — a member of an intégration fiscale is not an IS payer at all, only the parent is.
* 
* **No CFE.** It depends on communal valeur locative and thousands of local rates. A plausible-looking imitation would be worse than a declared hole.
* 
* **Within-cell dispersion is assumed, not published.** ESANE gives cell means and totals, never quantiles, so the shape inside a cell is declared (lognormal, sigma 1.4) rather than fitted. Every line whose residual depends on where firms sit *within* a cell — the C3S abattement, the CVAE schedule, the CEBGE thresholds — inherits that assumption. 34.5% of firms pay no IS in this build.

## Sources

| Figure | Year | Scope | Source |
|---|---|---|---|
| `AVERAGE_RATE_ON_PROFITS` | 2024 | Série publiée « Taux moyen d'imposition », graphique 2 de DGFiP Stat n° 39 (valeur 2024 : 24,256 %) — IS brut rapporté aux bénéfices déclarés | [DGFiP Statistiques n° 39, septembre 2025, graphique 2](https://www.impots.gouv.fr/statistiques) |
| `C3S` | 2025 | C3S encaissée, tous redevables | [Rapport à la Commission des comptes de la Sécurité sociale, mai 2026](https://www.securite-sociale.fr/accueil/rapport-ccss-mai-2026) |
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
