# Cross-check against the CAF's own estimator

`tests/golden/CROSSCHECK.md` did this for income tax, against the DGFiP simulator, and
D-019 lifted the publication blocker for the IR path on the strength of it. **The
benefit levels have never had an equivalent check**, which the 2026-09-01 audit recorded
as an open gap and which is still true.

**Status: PREPARED, NOT DONE.** Everything below is ready to run; the numbers in the
right-hand column are blank on purpose.

## Why this session did not run it

The DGFiP check was driven through a browser with Max present. The CAF estimator
(`wwwd.caf.fr/wps/portal/caffr/simulateurpa/`) is a portal application that loads Google
reCAPTCHA. Driving it from a script would mean working around a bot protection, which is
not something to do and would not produce a check worth having anyway. This session has
no browser, so it stopped here and prepared the run instead.

D-019's instruction stands and applies to this file too: **do not fabricate the
numbers.**

## The trap to avoid, which is the whole point of the exercise

**Do not use `mesdroitssociaux.gouv.fr`. Do not use `mes-aides.org`. Do not use ESTIME.**

All three are powered by **OpenFisca** — the same engine this project wraps. Checking
our benefit figures against them would compare openfisca-france with itself and agree
perfectly while telling us nothing. A check that cannot fail is not a check, and this
one is easy to run by accident because those sites are the most findable French benefit
simulators there are.

The CAF's own estimator is independent: it is the Caisse nationale's production
arithmetic, not a reimplementation of it. That independence is the only reason this
exercise is worth an hour.

## How to run it

1. Go to **caf.fr → Aides et démarches → Mes démarches → Faire une simulation**, or
   directly to the *Estimateur de prestations*. Use the CAF's own tool, not a partner or
   aggregator site.
2. For each household below, enter the situation exactly as described. Where the
   estimator asks for a monthly income, give the **monthly gross salary** shown — the
   CAF assesses on declared resources, and the ressources it wants are net, so follow
   the tool's own wording and record which figure you gave.
3. Record the estimator's monthly amounts in the right-hand column, **per benefit**, not
   just the total. A total can agree while two components are wrong in opposite
   directions.
4. Note the date and any version string the tool shows.
5. Anything more than a few euros apart is a finding to investigate, not to average
   away.

## Why per-benefit, and why these three households

Three households, chosen so that between them every benefit this project reports is
exercised at a level where it can be wrong visibly:

| | AF | PPA | RSA | AL |
|---|:--:|:--:|:--:|:--:|
| A — lone parent, two children, half-time | ● | ● | | ● |
| B — couple, two children, two modest salaries | ● | ● | | ~ |
| C — single, no income | | | ● | ● |

`~` marks a figure our engine puts within a few euros of zero, which is a prediction
worth testing in its own right: a tool that returns a hundred euros there disagrees
about a threshold, not about an amount.

---

## Household A — parent isolé, two children, half-time SMIC

**Situation to enter**: one adult born 1992, living alone with two dependent children
born 2019 and 2021. Tenant of an unfurnished dwelling, **rent 650 €/month**, APL
**zone 2**. Gross salary **900 €/month** (10 800 €/year); net taxable as our engine
computes it is 8 857 €/year.

| Benefit | Our engine, €/month | CAF estimator, €/month |
|---|---:|---|
| Allocations familiales | **147,62** | |
| Prime d'activité | **297,54** | |
| RSA | **0,00** | |
| Aide au logement | **475,50** | |

## Household B — couple, two children, two modest salaries

**Situation to enter**: two adults born 1988 and 1990, married or pacsés, two dependent
children born 2016 and 2019. Tenant, **rent 800 €/month**, APL **zone 2**. Gross
salaries **1 800 €/month** and **1 200 €/month** (21 600 € and 14 400 €/year); combined
net taxable 29 523 €/year.

| Benefit | Our engine, €/month | CAF estimator, €/month |
|---|---:|---|
| Allocations familiales | **147,62** | |
| Prime d'activité | **453,21** | |
| RSA | **0,00** | |
| Aide au logement | **4,65** | |

## Household C — single, no income

**Situation to enter**: one adult born 1995, living alone, no children, no income at
all. Tenant, **rent 500 €/month**, APL **zone 3**.

| Benefit | Our engine, €/month | CAF estimator, €/month |
|---|---:|---|
| RSA | **553,27** | |
| Aide au logement | **276,88** | |

---

## What the result licenses

Agreement would do for the benefit path what D-019 did for income tax: it would make the
household calculator's benefit figures independently validated for the cases covered,
and it would remove the audit's oldest open gap.

It would **not** license the population's benefit totals. Those miss their published
aggregates by −25 % to +106 % (D-015), and that is a question about who the synthetic
households are, not about whether the benefit formulas are right. A correct formula
applied to the wrong population is still the wrong national figure — which is precisely
why these two checks are separate and why passing this one changes nothing about that.

## Recording

When it is run, fill the right-hand columns, add the date and the tool's version, and
open a decision entry the way D-019 did — including the intermediates if the estimator
shows any, because two engines can reach the same total through different errors.
