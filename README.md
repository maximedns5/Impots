# Impôts — a transparent simulator of French taxation

[![test](https://github.com/maximedns5/Impots/actions/workflows/test.yml/badge.svg)](https://github.com/maximedns5/Impots/actions/workflows/test.yml)

Not a predictive model of the French economy. A layered simulator that computes
what a tax reform does, and is explicit about how much each answer can be trusted.

## The five layers

| Layer | What it computes | Fidelity |
|-------|------------------|----------|
| L0 | Legislation as code — every rate, threshold, barème, date-versioned | exact |
| L1 | A calibrated synthetic population of households and firms | aggregates good, tails weak |
| L2 | Mechanical simulation: who pays what on day one | 1–3% on aggregates |
| L3 | Behavioural response, as a Monte Carlo band over published elasticities | a range, never a number |
| L4 | Macro order of magnitude and sectoral composition, as a fan | wide by construction, and often unavailable |

The layering is the product: a user sees the mechanical number, the behavioural
band and the macro fan stacked, each labelled — and each drawn quieter than the one
above it, because that is the order of the evidence behind them.

L4 is honest about being mostly unavailable. Transfers and corporate instruments have
no published French multiplier, so a reform touching only those gets a block saying so
with the reason, not a number. When it does apply, the fan is wide: the width comes from
how much published studies disagree with each other, which for tax instruments exceeds
the central estimate itself.

## Status — Phases 0–4 are built

**Phase 0 — one household. Any reform. Exact numbers.** Describe a household,
optionally edit the IR barème, décote, plafond du quotient familial or CSG rates,
and see the exact mechanical result under current law and under your reform, side
by side.

**Phase 1 — the same reform, priced for the country.** A synthetic population of
199 451 households built entirely from open data: household structure observed in
the INSEE Enquête Emploi, incomes synthesised from published distributions. It
answers what a reform costs nationally and who gains and loses by decile of niveau
de vie — with a [reconciliation report](reports/reconciliation.md) that states, line
by line, how far it sits from published totals and which of those lines were spent
on calibration and therefore prove nothing.

**Phase 2 — the firm side.** IS, its contributions additionnelles, the CEBGE, the
CVAE and the C3S, priced mechanically over a synthetic firm population built from
published sector × size cells. A firm reform is priced inside an HTTP request —
about 500 000 firms in hundredths of a second — so there is no quick tier and no
batch job. It has [its own reconciliation report](reports/reconciliation_entreprises.md).
The population is built from published INSEE and DGFiP tables by tested code, and
the report's free test — total IS over total taxable profit, where the denominator
is calibrated and the numerator is not — lands within 1.2 % of the published
average rate. Three of its six sector lines pass and three fail, all six visible.

**Phase 3 — the band.** Official French costings are mechanical by design; FIPECO's
own position is that behavioural responses are "difficult, often impossible to
measure". This project's claim is that showing the band honestly — as a range with
its evidence attached and its applicability graded — beats omitting it. Raising the
top rate from 45 % to 50 % yields +0.66 bn mechanically; the taxable-income response
gives back about a third of that, and the band says so with the paper it rests on and
a grade saying whether the reform is inside the evidence. **One channel of four is
live**: the other three are written, tested, and honest about why they report nothing.

**Phase 4 — the macro fan.** Order of magnitude and sectoral composition, never a
forecast. Multipliers and employment come per instrument and per horizon from Mésange,
the model INSEE and the DG Trésor maintain jointly, parsed out of the published PDF
rather than retyped; the width comes from two IMK meta-regressions of 104 and 98 studies.
The input-output table supplies **shape** — where a shock lands by branch, and how much
leaks abroad — and never size, because the literature's multipliers already contain
input-output propagation and import crowding-out. Getting that boundary wrong in either
direction is a double count, and both are refused by tests.

Most of what this layer refuses is the interesting part. There is no revenue-feedback
loop, because the elasticity row failed verification. There is no cycle-state scenario
for tax instruments, because the regime effect is established on the spending side only.
Transfers get no multiplier rather than borrowing the generic-spending one, which would
overstate by a factor of two to three. The acceptance gate is the CICE: the employment
fan must contain what published evaluations span, 100k to 400k, **and** its median must
land inside — it does, on both bracketing variants, with nothing tuned.

```
src/impots/engine/       typed wrapper over openfisca-france — household scale (L2)
src/impots/population/   the synthetic population and distributional engine (L1)
src/impots/entreprises/  the firm tax system, its own parameter tree and population
src/impots/behavioural/  elasticities, channels, marginal rates, bands (L3)
src/impots/macro/        input-output table, multipliers, shocks, the fan (L4)
src/impots/reporting.py  the shared report engine — the spent/validation rule lives here
src/impots/guards.py     weight identities and the checks both weighting defects needed
src/impots/api/          seven FastAPI endpoints
ui/index.html            three tabs — household, population, firms — one file, no build
tests/chiffrages/        historical PLF costings, compared against the mechanical engine
tests/golden/            household regression anchors, ±2 €
tests/fixtures/          a 400-household EEC sample and an invented firm cell table
reports/                 the two reconciliation reports, generated
docs/                    the phase specs, the decision log, parameters, sources
```

## Quickstart

From a clean checkout, five commands:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/verify_openfisca.py      # must print "All Phase 0 engine assumptions hold."
uvicorn impots.api.main:app
```

Then open **http://localhost:8000**. The first request is warm: the server builds
the tax-benefit system and runs a throwaway simulation during start-up, which
takes about five seconds and is why `uvicorn` pauses before it says *Application
startup complete*.

`ui/index.html` also works opened straight off the filesystem — it falls back to
`http://localhost:8000`, which is what the permissive CORS policy is for.

After cloning, install the data guard — `core.hooksPath` is local config and does
not travel with the repository:

```bash
git config core.hooksPath .githooks
```

It refuses any commit that adds a file under `data/` (D-016): ERFS microdata is
not redistributable, and a compliance rule that lives only in a decision log is
one distracted `git add -A` from being fiction. CI asserts the same on the pushed
tree for anyone who forgets.

Run the tests with `pytest` (a few minutes; most of it is openfisca computing).
`node ui/check.mjs` checks the page's logic and is deliberately outside CI — D-003.

### Building the population

The population needs the INSEE Enquête Emploi fichier détail, which is Licence
Ouverte but too large to commit. Download it once, then build:

```bash
curl -o data/raw/FD_EEC_2024.parquet \
  https://www.insee.fr/fr/statistiques/fichier/8632441/FD_EEC_2024.parquet
curl -o data/raw/Varmod_EEC_2024.csv \
  https://www.insee.fr/fr/statistiques/fichier/8632441/Varmod_EEC_2024.csv
impots population manifest       # record checksums; the pipeline refuses unmanifested inputs
impots population build          # -> data/processed/population_2024.parquet, ~5 s
impots population reconcile      # -> reports/reconciliation.md, ~3 min
impots population run --reform my_reform.json --sample 20000
```

`build` rakes the household weights onto published margins (D-017) before
attaching incomes — the order matters, since incomes calibrate the wage bill
against whatever weights are in force. `--no-raking` reproduces the unraked
vintage, and `reconcile --compare-unraked` builds both and shows every line
before and after.

`scripts/verify_eec.py` re-runs the M0 reconnaissance against the raw file, and
`scripts/verify_population_engine.py` is the population-scale engine gate — run it
before and after any change to the runner.

### Naming a reform, and making it pay for itself

A scenario is a reform with provenance attached: what it encodes, and when it was
written. Both are required, and a saved scenario is never overwritten — the point is
to **pre-register** a chiffrage so it can be confronted later with the évaluation
préalable and eventually the outturn, and a chiffrage that can be revised after the
fact while keeping its date is not one.

```bash
impots scenario save rsa_700 --reform rsa700.json \
  --source "variante interne : RSA socle porté à 700 EUR/mois"
impots scenario compare rsa_700 rsa_700_af_40 --sample 8000
impots scenario solve csg_activite_imposable --on rsa_700 \
  --low 0.024 --high 0.20 --sample 8000 --tolerance 300e6
```

The comparison prints both reforms layer by layer and differences **only** the
mechanical one: the difference of two intervals is an interval, so the behavioural
band and the macro fan are shown side by side and left undifferenced.

The solver root-finds one scalar knob against the mechanical cost. On the run above it
converged in three population draws — RSA socle at 700 € costs 3.54 bn, and
**+0.343 points of CSG activité imposable** pays for it. It refuses to solve against a
banded quantity, refuses a knob that is not a single number, and when it does not
converge it says so rather than handing back its last try. Those refusals are the
feature; see D-092.

They are also how one of our own guards got caught. The double-entry identity scaled
its residual by the reform's *net* cost — and a budget-neutral solver drives that to
zero on purpose, so at exactly the iterate you care about it divided a fixed 305 000 €
leakage by nothing and refused a correct run. D-093.

### Try this

A single earning 240 000 € under a top rate lifted from 45 % to 50 % pays exactly
**200 € more**, and the arithmetic is checkable on paper: about 4 006 € of their
income sits above the 180 294 € threshold, and five points of that is 200 €. It is
the smallest complete demonstration that the reform machinery does what it says.

## What the numbers are, and are not

* **Mechanical only.** Day-one effect at constant behaviour. Nobody works less,
  nobody moves, nobody restructures their income. That is L3, and it is not built.
* **One household, never a population.** Phase 0 refuses to answer "what does this
  reform cost". It has no population to answer it with.
* **Salarié du privé.** Only gross salary and date of birth are supplied; every
  other input takes the engine's default. No self-employment, no capital income,
  no property income, no pensions.
* **Benefits are assessed on reference periods Phase 0 leaves empty**, which
  inflates RSA, prime d'activité and aide au logement — by 11 % of disposable
  income in a measured case. Read `docs/DECISIONS.md` D-005 before quoting any
  benefit figure; the `historique_revenus` flag turns the defect off.
* **Golden values are regression anchors, not tax advice.** They pin this wrapper
  against openfisca-france 176.0.8. They have also been checked against the
  DGFiP's own simulator — `tests/golden/CROSSCHECK.md`, done 2026-08-29, both
  households agreeing **to the euro** on income tax and on revenu fiscal de
  référence, and matching on the intermediates (droits simples, décote, parts)
  too. That is the one check in the project that could have caught a systematic
  error rather than a regression, and it passed.

### And about the population specifically

* **No income in it is observed.** The EEC carries no wage, pension or benefit of
  any kind. Every euro is drawn from a published distribution and calibrated to a
  published total (`docs/M0_RECON.md`, D-012).
* **Reform deltas are the product; baseline levels are not.** The income tax total
  reconciles to +8.8 % of the published barème and foyers imposés to −1.9 %,
  but RSA runs at +113 % and its allocataire count at +96 %, because 13.5 M adults
  — the self-employed and the inactive — have no modelled income. Read D-015
  before quoting any level.
* **Several lines are inside their tolerance only because a component is empty**,
  and each says so in its own note. The zero-masked sweep (D-073,
  `docs/ZERO_MASKED_SWEEP.md`) checked every line, household and firm, for
  comparisons valid only because one side is identically zero. Two examples of the
  class: prime d'activité passes at ±25 % and would not if the 8.01 M
  primo-accédant households carried a housing payment; the two INSEE distribution
  lines pass with no capital income on our side and a target that includes it.
* **No capital income and no self-employment income.** The top of the distribution
  is a construction. Réductions and crédits d'impôt now exist, but only under
  `--impute-niches`, only five families of them, and only as a decile mean per
  claimant (D-066, `docs/B3_IR_NICHES.md`).

### And about the behavioural band specifically

* **The mechanical number never changes.** The band is a range *around* it, drawn
  subordinate to it, and a regression test asserts that turning the band on moves no
  mechanical figure by a single euro.
* **All four channels are live.** The taxable-income response, employment at the
  SMIC, contribution incidence, and the production-tax investment band — the last
  centred on zero with bounds read from the evaluation's own tables (D-037). The
  employer-contribution knobs that C2 and C3 had been waiting for since Phase 3 now
  exist (D-038).
* **C2 can never claim to be "in support"**, by design: two of its three rows cannot
  say how far they carry, and the line between its two published points is this
  project's construction rather than the literature's. The guardrail refuses to
  launder a construction as evidence (D-040).
* **C3 reports a range, not a number.** No French lever moves a contribution of a
  single linkage class, so the tool shows both incidence assumptions. The mechanical
  total is identical at both ends — it is the split that moves, not the cost.
* **The best-identified French elasticity is missing on purpose.** Capital income
  responds far more sharply than labour income, and this population carries none until
  real income microdata is available — not in prospect (D-096). The UI says so where a
  capital knob would appear. Any band on a reform
  touching the top is understated for that reason.
* **Five of the seed table's rows died.** `eti_all` is 0.02, not the 0.05 that was
  written down; the two labour-supply scalars turned out to be averages their cited
  paper never states. A row that dies is removed and its channel narrows visibly —
  the removals are in the YAML with their reasons.
* **A reform larger than the evidence gets a widened band and the word
  "extrapolation"**, never a confident number (D-031, D-034).
* **The chiffrage backtest suite grades the mechanical engine against the state's own
  arithmetic** on historical articles — independent of everything the band adds. Four
  cases ship; five more died under source-checking, and **three of the four survivors
  are red**, each with its finding written up rather than tuned away (D-035, D-041).
* **The two red household cases are the project's sharpest self-measurement.** The
  barème indexation overshoots by 10 % on an instrument with progressive brackets; the
  2025 allègements step overshoots by **107 %** on two narrow cliffs. The contrast
  says the synthetic population's error is not a level shift but a mis-shaped density
  — and that any reform whose yield turns on the mass in a narrow wage band is badly
  overstated until real incomes arrive (D-041).

### And about the firm module specifically

* **No firm financial is observed.** SIRENE gives counts per sector × size cell and
  ESANE gives that cell's totals; neither publishes a firm. Every individual amount
  is a parametric draw inside a published cell, so results exist at cell level only
  — no firm-level output, and no top-tail claims.
* **The IS *level* is calibrated; the IS *rate* is not.** The cell table's
  fiscal-to-accounting ratio is computed to reproduce DGFiP's published taxable
  profit, so landing near the published IS total is mostly arithmetic. What is free
  is the rate the statutory schedule produces on a synthetic distribution, and the
  by-sector lines. Read those (D-027).
* **Three of six sector lines are outside tolerance**: industrie +74 %, activités
  immobilières −91 %, information et communication −70 %. Two hypotheses are
  recorded and neither has been tested; the lines stay red until one is.
* **The CEBGE line is at +45 % and rests entirely on the top tail** — 198 firms
  above 3 bn of turnover carry 10.6 of its 10.9 bn. This module disclaims top-tail
  claims, so that line is at the edge of what a cell-based population can price.
* **No loss carry-forward, no intégration fiscale, no crédits d'impôt.** The first
  biases IS upward, the second over-counts firms at the reduced rate, the third
  means the simulated IS is an IS before créances.
* **CFE is absent on purpose.** It turns on communal valeur locative and thousands
  of local rates; a plausible-looking imitation would be worse than a declared hole.
* **The CVAE base is a proxy** — accounting value added, which does not add back
  the rents and crédit-bail that are not deductible from the fiscal one, so CVAE is
  understated and the bias is correlated with sector (D-021).
* **The CEBGE is computed on one exercice** where the statute uses two, so the
  entries and exits created by its second-year threshold — where the 2026 yield
  actually moves — are not represented (D-022).

### Running the tests

```
pytest                 # the gate: everything but the full-population tests, ~1 min 45
pytest -m ""           # everything, ~20 min — run it before pushing
pytest -m slow         # only the population runs
```

The split exists because local test pain is how green suites rot. The slow tests are
marked, never weakened: each runs a 20 000-household pass through the full benefits
cascade and takes about a minute. They skip on a checkout without a built population,
which is why CI passes them over today — `-m ""` there is what picks them up the day
the data is available.

## Non-goals

CGE. DSGE/HANK. Agent-based macro. Dynamic pension microsimulation. A third
French rules-as-code DSL.

## Licence

**AGPL-3.0-or-later** ([`LICENSE`](LICENSE)). Inherited rather than chosen:
`openfisca-core` and `openfisca-france` are AGPL-3.0-or-later and this package
imports them, so anything distributed here is a derivative work. Dual-licensing
is not available — you cannot relicense someone else's copyleft.

**If you host this**, AGPL section 13 obliges you to offer everyone who reaches it
over a network the Corresponding Source of *your* version. Set
`IMPOTS_SOURCE_URL` to a URL serving your source: `GET /health` reports it, the UI
footer links it, and the server logs a warning at startup if it is bound beyond
localhost without one. Running it on your own machine triggers nothing.

Data is licensed separately from code and the AGPL does not reach it. The INSEE
Enquête Emploi is Licence Ouverte / Etalab 2.0 (redistribution with attribution,
which is what makes `tests/fixtures/eec_sample.parquet` committable). ERFS, if the
population moves to it, is **not** redistributable — see `docs/PHASE1C_ERFS.md` §5.
