# Impôts — a transparent simulator of French taxation

Not a predictive model of the French economy. A layered simulator that computes
what a tax reform does, and is explicit about how much each answer can be trusted.

## The five layers

| Layer | What it computes | Fidelity |
|-------|------------------|----------|
| L0 | Legislation as code — every rate, threshold, barème, date-versioned | exact |
| L1 | A calibrated synthetic population of households and firms | aggregates good, tails weak |
| L2 | Mechanical simulation: who pays what on day one | 1–3% on aggregates |
| L3 | Behavioural response, as a Monte Carlo band over published elasticities | a range, never a number |
| L4 | Macro closure, as a fan chart | illustrative only |

The layering is the product: a user sees the mechanical number, the behavioural
band and the macro fan stacked, each labelled.

## Status — Phases 0 and 1 are built

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

```
src/impots/engine/       typed wrapper over openfisca-france — household scale (L2)
src/impots/population/   the synthetic population and distributional engine (L1)
src/impots/api/          five FastAPI endpoints
ui/index.html            the calculator and the population tab, one file, no build step
tests/golden/            household regression anchors, ±2 €
tests/fixtures/          a 400-household EEC sample so CI needs no network
reports/                 the reconciliation report, generated
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
  reconciles to +8.9 % of the published barème and foyers imposés to −2.3 %, but
  RSA runs at +106 % and the interdecile ratio at +41 %, because 13.5 M adults —
  the self-employed and the inactive — have no modelled income. Read D-015 before
  quoting any level.
* **No capital income, no self-employment income, no réductions d'impôt.** The top
  of the distribution is a construction.

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
