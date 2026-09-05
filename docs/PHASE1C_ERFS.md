# Branch C — moving the population onto ERFS

**Status**: planned, not started · **Decided**: 2026-08-29 (D-016) · **Prerequisite**: Phase 1 as built
**Access**: available — Max holds a Quetelet-Progedo account

Branch A' (D-012) built the population from the open EEC because that is what was
reachable. The EEC carries real household structure and **no income of any kind**,
so every euro in the current population is a construction. ERFS replaces the half
that is invented with the half that is measured.

This document is the migration plan. It exists so that the work is a known shape
before the data arrives, and so that nothing is built in the meantime that ERFS
would throw away.

---

## 1. Why this is not a marginal improvement

The reconciliation report's failures have one dominant measured cause: **13.5 M adults
have no modelled income** — 3.87 M self-employed and 9.6 M inactive below the
retirement proxy. Zero-income adults form zero-income familles and claim RSA.

It shows up in two shapes, and the second is the one that took longest to see. The
obvious one is the bottom: a population with too many zero incomes over-claims
means-tested benefits. The other is that emptying 13.5 M adults out of the distribution
**mis-shapes the density everywhere else**, so any reform whose yield depends on the mass
in a narrow wage band is badly out — measured at +112 % on a published costing. Neither
is fixed by reweighting; both are fixed by observing incomes.

| Line | A' today | Cause | Under ERFS |
|---|---|---|---|
| RSA | +113 % | zero-income adults | incomes observed |
| Allocataires du RSA | +96 % | the same, counted in foyers rather than euros | observed |
| Chiffrage allègements 2025 | +112 % | mass in a narrow wage band | observed |
| Foyers fiscaux | −15 % | tax units inferred from dwelling structure | declared |
| Prime d'activité | −28 % vs bridge | income distribution near the taper | observed |
| Allocations familiales | −23 % | children synthesised; AF is income-modulated | observed |

**The interdecile ratio is no longer on this list, and removing it strengthens the
case rather than weakening it.** It sat here at +41 %, cited as the headline proof that
the synthetic distribution's *shape* was wrong. The zero-masked sweep (D-073) found that
most of that number was a **wrong estimator**: the line compared a ratio of decile MEANS
against INSEE's ratio of person-weighted THRESHOLDS. Read as the statistic INSEE actually
publishes, it is **+3,6 %** — inside tolerance.

So the honest version of the argument is narrower and better evidenced. The synthetic
distribution does not fail across its broad shape; it fails **at thresholds and in the
zero-income population**, which is exactly what ERFS fixes. The evidence that stands:

* the **+112 % allègements backtest** — a published costing, missed by a factor of two,
  because the yield depends on the mass between 2,25 and 2,5 SMIC and a synthetic
  distribution puts the wrong number of people in a narrow band (D-076);
* the **RSA lines**, +113 % in euros and +96 % in allocataires, driven by the 13.5 M
  adults with no modelled income;
* **`asf` at 9,0 md against a published ~2 md** — one more instrument, same cause;
* **no capital income at all**, which the two distribution lines are inside tolerance
  *because of* rather than despite (D-080).

A case that cites the line that fell would invite exactly the correction it just
received. These four stood.

**The deeper reason, which is easy to miss.** In A' the wage level is *calibrated*
to a published wage bill, which spends that margin (§4.3) and leaves the income-tax
line only semi-independent: it tests the tax schedule applied to a distribution
whose level we set. With ERFS the incomes are observed, so **the wage bill stops
being a calibration target and becomes a validation line**, and the income-tax
residual becomes a real test of the model rather than a partial test of our own
scaling. That is worth more than any single number in the table.

## 2. What to request from Progedo

* **Dataset**: ERFS — Enquête Revenus Fiscaux et Sociaux, *fichier détail*
  (individus + ménages), most recent vintage available. ERFS-FPR is the version
  distributed through Progedo/ADISP; confirm which is offered under the account.
* **Vintage**: the latest. Phase 1 simulates 2024 law; an ERFS two or three years
  behind is still far better than synthesised incomes, and the vintage gap is
  reported rather than corrected.
* **Variables to confirm on arrival** — the migration turns on these:
  * household and tax-unit identifiers, and the **link-to-reference-person**
    variable the EEC lacks entirely;
  * **exact age or date of birth**, not a band;
  * declared income by category: wages, pensions, unemployment benefit,
    self-employment (BIC/BNC/BA), property and capital income;
  * housing: tenure, **rent paid** (an assumption in A', anchored only on a
    published €/m² and an invented surface rule);
  * region, and the weight variable with its documentation.
* **Declared purpose**: state the research purpose the agreement requires. It
  binds what may be done with the data — see §5.

## 3. What changes in the code, and what does not

The §4.1 parquet schema is the seam, and it was designed for exactly this. Two
modules are rewritten; **everything downstream is untouched**:

```
rewritten     skeleton.py    dwelling assembly -> read declared households and tax units
              incomes.py     synthesis -> read declared income by category

untouched     ingest.py      one more manifested source
              to_openfisca.py  same schema, same 36-month wiring, same guards
              runner.py      unchanged
              aggregate.py   unchanged
              reconcile.py   same table, different lines spent (§4)
              api/, ui/      unchanged; the L1 banner text changes
```

Concretely, `skeleton.py` loses the parts that exist only because the EEC is thin:
the NOI/COUPL_LOG partner inference, the rattachement age rule, the whole
under-15 synthesis, and the age draw inside bands. `incomes.py` loses the
quantile curves, the Pareto splice, the net-to-gross ratio and the level
calibrations. Both shrink substantially.

**New work ERFS creates**: income categories Phase 1 does not currently model at
all — self-employment, property and capital income — arrive as columns and need
wiring into OpenFisca (`rpns_*`, `revenus_capitaux_*`). That is where the
migration's real effort sits, not in the reading.

## 4. What moves between the calibration and validation columns

| Margin | A' | ERFS |
|---|---|---|
| Total gross wages | **calibration** (spent) | **validation** |
| Declared pensions | **calibration** (spent) | **validation** |
| Unemployment benefit | **calibration** (spent) | **validation** |
| Children under 15, children per family | **calibration** (spent) | observed, drops out |
| Income tax, foyer counts, benefits, deciles | validation (semi-independent for IR) | validation, fully independent |

`margins.py` tags every figure with its use and `reconcile.py` enforces the rule
mechanically, so this migration is a change of tags, not of logic.

## 5. Compliance — the constraint that binds on this repository

ERFS is **not** Licence Ouverte. It arrives under a signed agreement restricting
use to the declared purpose and forbidding redistribution and any attempt at
re-identification. Three consequences, all of which must hold in code before the
data lands:

1. **No ERFS-derived rows may enter the repository, ever.**
   `tests/fixtures/eec_sample.parquet` stays EEC-derived or becomes fully
   synthetic. Its README already says so.
2. **`data/raw/` and `data/processed/` must remain gitignored** for anything
   ERFS-derived. The committed `data/processed/baseline_*.json` holds only
   national aggregates and decile means and is safe — but that is a property to
   re-check, not to assume, once the population is built on restricted data.
3. **Only aggregates are published.** The reconciliation report and the API's
   population endpoints already emit nothing below a decile mean. Keep it that way.

A pre-commit check that refuses to stage anything under `data/` would make (1)
and (2) mechanical rather than remembered. Worth adding *before* the data arrives.

## 6. Migration milestones

| # | Deliverable | Gate |
|---|---|---|
| C0 | Agreement signed, data in hand; `verify_erfs.py` written the way `verify_eec.py` was | inventory before design |
| C1 | `skeleton.py` reading declared households and tax units; schema tests green unchanged | the seam holds |
| C2 | `incomes.py` reading declared income; new categories wired into OpenFisca | `verify_population_engine.py` green at full N |
| C3 | Reconciliation regenerated with the calibration/validation columns re-tagged | IR now a genuine test |
| C4 | D-015's unpublishable list revisited; UI banner rewritten | levels become publishable, or the reasons change |

## 7. What not to do while waiting

**Do not patch A''s income gaps.** Modelling self-employment and disability income
by hand inside the open-data branch is roughly a month of work that ERFS deletes.
The one exception is anything that survives the migration: the guards, the
reconciliation machinery, the take-up bridge, and raking if it is added — those
are branch-independent and keep their value.

---

## §6 addendum — the migration's acceptance test (2026-09-02)

**The barème-indexation backtest re-runs before anything else on the ERFS
population.** `tests/chiffrages/ir_bareme_indexation_lfi2024.yaml`, and it is the
acceptance test for this migration rather than one check among many.

Why that case and not the reconciliation table. It currently misses by **+10 % in
magnitude**: the model produces a larger effect than the state's published costing
while moving a strict *subset* of the instruments that costing covers. Vintage drift
is a few percent, and the missing base — capital income, indépendants,
réductions/crédits — pushes the other way. What is left points at the synthetic
income distribution carrying more mass in the bracket-crossing region than the real
one, which is D-015 measured against an external figure for the first time instead of
declared.

Real observed incomes are exactly the thing that should fix it. So:

* **Expected**: the overshoot collapses. Not necessarily to zero — the missing
  instruments still bias the simulated figure *down*, so the case should end up
  inside its one-sided band rather than at parity.
* **If it does not collapse**, the migration has a problem that the reconciliation
  table would take much longer to surface, because a distributional error that
  survives real incomes is not a distributional error — it is a wiring one.
* Either way the result is recorded before any other Phase 1C work proceeds.

The suite's other two cases are firm-side and unaffected by this migration; they are
the control group.
