# B3 — Réductions et crédits d'impôt

**Date**: 2026-09-03 · **Menu item**: `WHAT_NOW.md` B3 · **Reproduce**: `pytest tests/test_niches.py -m ""`
**Status**: the household calculator prices the five biggest niches exactly, thirteen reform knobs move them, and the population can now be given bases from the published DGFiP decile table (§8). The net-yield reconciliation line moves from **+22.5 % to +10.4 %**.

The 19.53 bn € of réductions and crédits is the stated reason the model's income tax is
validated against the barème line (98.84 bn) rather than against net receipts. It was
not that the formulas were missing — openfisca carries all of them — but that nothing
could ever supply a base. `reductions` and `credits_impot` were zero for every
household, and there was no way to make them anything else.

## 1. What a household can now declare

| Field | Case | Instrument | Measured effect |
|---|---|---|---|
| `salarie_domicile` | 7DB | **crédit** 50 % | 5 000 € → 2 500 € |
| `salarie_domicile_aides_percues` | 7DR | subtracted from the base | −1 000 € → −500 € of credit |
| `dons_oeuvres` | 7UF | réduction 66 % | 1 000 € → 660 € |
| `dons_aide_personnes_en_difficulte` | 7UD | réduction 75 % | 1 000 € → 750 € |
| `frais_garde_par_enfant` | 7GA/7GB/7GC | **crédit** 50 %, ceiling **per child** | 2 000 € → 1 000 € |
| `cotisations_syndicales` | 7AC (*individu*) | crédit 66 % | 350 € → 231 € |
| `enfants_college` / `_lycee` / `_superieur` | 7EA / 7EC / 7EF | flat per child | 61 € / 153 € / 183 € |

**No rate above was read off a table.** Each was measured by running a household through
the engine, and only then checked against the parameter the tree prints — agreement
between the two is the evidence, because either alone can be a parameter no formula
reads (§4).

Two facts a reader should not have to discover for themselves, and which the UI panel
states: the home-help and childcare items are **crédits**, so they are paid out to
households with no tax to reduce, and a foyer claiming enough of them leaves with a
**negative** income tax. A donation, being a réduction, gives a household with no tax
nothing at all.

## 2. The ceiling that decided the wire format

`frais_garde_par_enfant` is a list, not a total, and the reason is measured:

| Same 6 000 € of childcare | Credit |
|---|---|
| all on one child | **1 750 €** |
| 3 000 € on each of two | **3 000 €** |

The ceiling is 3 500 € **per child**. A single total split equally across eligible
children would have reported 3 000 € for a household that spent it all on one — 71 %
too much. The list keeps the engine's arithmetic exact and pushes the assumption up to
the UI, where one field can fill the list evenly and say that it is doing so.

## 3. What it costs nationally

From the annexe au PLF 2026, *Voies et moyens tome II*, read out of the PDF on disk.
Each dispositif carries a number, and that number is how to find it again.

| Dispositif | n° | budget 2024 | budget 2025 | bénéficiaires |
|---|---|---:|---:|---:|
| Emploi d'un salarié à domicile | 110246 | 6 420 | 7 029 | 4 909 243 |
| Frais de garde des moins de 6 ans | 110203 | 1 737 | 1 799 | 1 928 960 |
| Dons (art. 200, agrégé) | 110201 | 1 990 | 2 204 | 5 621 930 |
| Frais de scolarité, secondaire | 110215 | 221 | 229 | 3 216 467 |
| Frais de scolarité, supérieur | 110242 | 217 | 225 | 1 517 485 |
| Cotisations syndicales | 110202 | 149 | 156 | — |
| **Total** | | **10 734** | **11 642** | |

**WHICH COLUMN, AND WHY IT MATTERS.** The Voies et Moyens columns are **budgetary**
years, and a budgetary year N carries the dispositif assessed on the **revenus N−1**.
A model simulating 2024 incomes therefore compares against the **budget-2025** column,
not the one labelled 2024. Three of the five research passes got this wrong in the same
direction, and one of them presented the resulting 3.4 % discrepancy as a reassuring
cross-check when that discrepancy *was* the one-year lag; corrected, the same
comparison closes to 0.19 %.

The correction is not free, though, and the honest position keeps both columns: the
budget-2025 figure is the right vintage but a **forecast**, and the PLF 2025 forecast
for the same dispositif in 2024 came in at 6 724 M € against a realised 6 420 M €, a
4.5 % overshoot. Neither column is a clean comparator. Both are printed above.

Against 19.53 bn of réductions and crédits in total, these five families are **11.6 bn,
about 59 %** — so even a complete imputation of them would leave two fifths of the
niches unmodelled.

## 4. A phantom parameter tree, and the standing rule it earned

`impot_revenu.credits_impots.aide_a_domicile` exists, resolves non-null at 2024-01-01,
documents itself as *«CGI - art 199. sexdecies»* — the very article that governs the
home-help credit — and carries the same values at every leaf as the live node: rate 0.5,
invalidity ceiling 20 000, increment 1 500, first-year ceilings 15 000 and 18 000.

**No formula in openfisca-france reads it.** A knob aimed at it would write
successfully, warn nothing, move nothing, and pass a read-back — because the dead tree
answers the same values as the live one. And `aide_a_domicile` is the *more* natural
name for "home help" than `emploi_salarie_domicile`, so it is exactly what a careful
implementer would reach for.

This is the third shape of one failure:

| | What existed | Why a read-back missed it |
|---|---|---|
| D-044 | `update()` silently **created** an absent child | the check found the value it had just written |
| D-062 | published-but-**derived** AF plafonds | they accept a write; the formula computes its own |
| **here** | a complete **duplicate tree** for the same article | identical values, so the read-back agrees |

`test_every_knob_aims_at_a_node_some_formula_reads` now requires every knob's node to be
mentioned somewhere in openfisca's model source, and its kill test asserts the phantom
stays invisible — otherwise the rule would be passing vacuously.

## 5. The engine applies no eligibility test, and that is correct

Measured: a household with a fifteen-year-old receives the childcare credit, and so does
a household with **no children at all**. These cases are boxes on the 2042 and openfisca
trusts the declarant exactly as the paper form does; eligibility is the administration's
business, not the formula's.

Right for a tax engine, wrong for a calculator someone uses to decide something. An
earlier version of this project's own docstring asserted that "the engine decides
eligibility from the children's ages" — it does not, and the claim is corrected in place.
`situations.assert_niche_eligibility` now refuses more childcare amounts than there are
children under six at 1 January, more union dues than adults, and more school children
than dependants. It raises `ValueError`, which the API turns into a 422.

## 6. The confident zero, and why the flag still matters after imputation

Without imputation, no household declares any niche base, so `reductions` and
`credits_impot` total exactly 0.0000 bn.

The consequence is a trap. Cut the home-help credit from 50 % to 30 % on this population
and the reform costs **exactly 0 €** — and a reader told "0 €" concludes the credit is
worthless, when the truth is that the population has no home-help spending for the rate
to apply to.

So the tool refuses to print it bare. `guards.niche_blind_spot` detects a reform touching
a niche knob on a population with no bases, and the response carries a block naming the
knobs, the declared base (zero), and what the omission is worth nationally. It is drawn
**above** the headline figure, because a warning underneath is one the reader reaches
after they have already believed the number. It falls silent the moment the population
has bases, which is the half that stops it becoming furniture.

## 7. Open

* **The imputation itself.** It is now feasible: DGFiP publishes réductions and crédits
  by decile of RFR per part, and the Voies et Moyens gives beneficiary counts per
  dispositif. Both are on disk and manifested. Two traps are already identified and must
  be carried into that work — the decile files' *«montants en milliers d'euros»* header
  is true for the 2018–2021 vintages and **false from 2022**, and the DLF distribution
  sheet labels a column *«en M€»* whose cells are in euros. Either misread is a factor of
  a thousand or a million.
* **A point of law, settled in D-196.** openfisca places `ci_saldom` in the
  globally-capped list, and the cap measurably destroys entitlement: a household with
  7 500 € of home-help credit and 3 500 € of childcare credit receives 10 000 €, not
  11 000 €. That is the law. Art. 200-0 A, 2, b takes in « Les réductions [...] et crédits
  d'impôt sur le revenu, à l'exception de ceux mentionnés aux articles » it lists, and 199
  sexdecies is not among them (versions of 1 January 2024 to 16 February 2025 and of 16
  February 2025 to 21 February 2026, read on Légifrance); BOI-IR-LIQ-20-20-10-10, § 75,
  lists the home-help credit under the 10 000 € cap.
* The wire format ticks the invalidity ceiling (7DG, 20 000 €) from an adult's or a
  child's invalidity card and from a child's complément of the AEEH (D-196). It cannot
  express the invalidity pension of the third category, which opens it too, the
  first-year bonus (7DQ) or dependent ascendants (7DL), which change the home-help
  ceiling as well. And openfisca leaves out the 1 500 € increment the law gives each
  member of the foyer over 65.
* `f7df`, the old réduction base for retirees, is **dead** (`end = 2016-12-31`) and its
  cerfa box has been recycled for Scellier carry-forwards under `f7df_2024`. A knob or
  input aimed at "7DF" today would land on property investment relief.

## 8. The imputation (added 2026-09-03)

`impots population run --impute-niches`, or `impute_niches: true` on the API, hands out
bases from the DGFiP table of niche amounts and claimant counts **by decile of revenu
fiscal de référence per part**. It costs one extra baseline pass, because the decile a
foyer belongs to depends on a quantity the first pass has to compute.

| | without | with |
|---|---:|---:|
| Réductions | 0.000 bn | 2.06 bn |
| Crédits d'impôt | 0.000 bn | 8.66 bn |
| **IR — barème** vs 98.84 | **+8.7 %** | **+8.7 %** |
| **IR — recettes nettes** vs 87.99 | **+22.5 %** | **+10.4 %** |

The imputed total lands within **1.0 %** of the 10.605 bn target — sampling noise on the
20 000-household quick tier, and a check on the draw rather than on anything true.

**The barème line does not move, and that is the test.** Niches are subtracted after the
barème, so a correct imputation cannot touch it. It moving would have meant the
comparator was wrong — which it was, until this increment (§9).

### What it is, in the project's own vocabulary

A **calibration**, and its source is now spent: `margins.NICHE_CREDITS_BY_DECILE` carries
`use="calibration"`, and `IR_NET_YIELD`'s caveat says in as many words that the line is
no longer independent evidence for the niche component. The barème line is untouched and
stays the clean one.

### Three artefacts, none of them visible in the output

1. **Every claimant in a decile receives the same base.** A count and a total are all
   DGFiP publishes, so the mean is all there is. A reform's incidence therefore comes out
   as a ten-step function, and any feature finer than a decile is an artefact.
2. **Who claims is arbitrary.** The draw is seeded and conditioned only on the decile.
   Real claiming correlates with children, age and home ownership; this uses none of
   them, so the number of claimants per decile is right and their identity is not.
3. **About 45 % of the niches are still missing** — 10.6 bn imputed of 19.53 bn. Scolarité
   is deliberately excluded: its cases are counts of children while the published column
   aggregates the three levels into one amount, so the split cannot be recovered.

### The global cap is still unpriceable, and the flag survives to say so

Moving the cap from 10 000 € to 4 000 € costs **exactly 0.000 bn even with bases in
place**. Artefact 1 is why: the cap binds only on foyers claiming more than it, the
imputation gives every claimant a decile mean, and the largest of those is about 1 900 €.
Nobody reaches the cap because nobody can.

That is the more dangerous failure — a warning that disappears while the problem does
not — so `guards.DISPERSION_DEPENDENT_KNOBS` keeps the blind-spot flag firing for this
one knob when the bases are imputed, and only for it. A population with genuine
dispersion (an ERFS-based one) would silence it legitimately.

### Two traps the file itself sets

Both were flagged by the verification pass and both are now guarded:

* the same workbook is denominated in **thousands** of euros for the 2018–2021 vintages
  and in **euros** from 2022 — the 2018 sheet reads 4 860 210 where 2023 reads
  6 019 895 605, and both mean about six billion. `brackets()` asserts the total lands
  in a plausible band and refuses the 2018 sheet outright.
* the published decile bounds are **not contiguous**: decile 1 ends at 1 972 while
  decile 2 begins at 1 972.1667, and there are nine such slivers. Banding on the printed
  pairs drops every foyer in one, silently, and the claimant count then misses its target
  for no visible reason. Each band runs to the *next* band's lower bound instead.

## 9. What the imputation exposed: the barème line read the wrong quantity

The reconciliation's barème line compared `ir` — the figure **net** of réductions and
crédits — against a published target that is explicitly **gross** of them. It was
correct only because every household's niches were zero, so the two coincided.

Turning imputation on made them differ, and the line appeared to *improve* from +8.7 %
to −1.7 %. Nothing had improved; the comparison had started measuring a different thing.

Fixed by adding `ir_avant_niches` (openfisca's `ip_net`: after the décote, before the
article 199 réductions) and reading the barème line on that. The historical figure moves
slightly, from +9.1 % to **+8.7 %**, because `ir` also carried the sign convention and
the réduction sous condition de revenus — so the old number was wrong by 0.35 bn as well
as by construction.
