# M0 — Reconnaissance of the EEC fichier détail 2024

**Date**: 2026-08-28 · **Gate**: PHASE1_SPEC.md §3 · **Reproduce**: `python scripts/verify_eec.py --inventory`
**Status**: findings complete, **branch decision open — two questions for Max at the end.**

The Phase 1 spec left exactly one fact unverified: whether the open EEC fichier
détail groups individuals into households, and which income variables it carries.
It carries the first. It does not carry the second, at all — and that is the
finding that matters.

## 1. The file

| | |
|---|---|
| Source | insee.fr/fr/statistiques/8632441, Licence Ouverte / Etalab |
| Files | `FD_EEC_2024.parquet` (11.7 MB), `Varmod_EEC_2024.csv`, `Dictionnaire_EEC_2024.pdf` |
| Rows | **353 420** (matches the spec) |
| Columns | **83** (matches the spec) |
| Reference year | 2024, all four quarters |
| Weight | `EXTRIAN`, no nulls, range [0.29, 2 384.20], **sums to 55 435 998** — +0.8 % against ~55 M aged 15+ |

`EXTRIAN` is an *annual* weight summed across the whole file, not per quarter:
a person surveyed in several quarters contributes several rows. Any pipeline that
keeps one quarter must rescale, or keep all four and accept each household
appearing up to four times at a quarter of its weight.

## 2. The gate, question 1: household identifier — **YES**

`IDENT` ("numéro identifiant anonymisé de logement") plus `NOI` ("numéro
identifiant de l'individu dans le logement"):

* 80 171 distinct dwellings; **199 451 dwelling-quarters**, which is the household unit;
* persons per dwelling-quarter: 1 to 10 — a plausible household size distribution
  (84 759 singles, 87 098 pairs), not an artefact;
* the panel rotates: a person appears in 1–4 quarters (40 865 / 35 751 / 31 999 / 36 264);
* `TYPLOG5`, `METRODOM` and `STCOMM2020` are perfectly constant within a
  dwelling-quarter; `SO` disagrees in 349 cases out of 199 451 (0.17 %, survey
  noise — take the modal value).

**Branch A is structurally available.** Households are real, not assembled. This
is better than the spec's expected case for the open FD.

## 3. The gate, question 2: income variables — **NONE**

The only name-match is `SALTYP`, which is *nature du contrat*, not a salary. The
five numeric columns in the entire file are `EXTRIAN`, `HEFFEMP`, `HEFFTOT`,
`HHABEMP`, `HHABTOT` — a weight and four hours-worked measures.

There is **no wage, no pension, no unemployment benefit, no income of any kind**.

This is worse than any branch in §3 anticipated. The spec's §4.2 plan was "EEC
wage variable where present; where absent/banded, hot-deck imputation within
age×sex×CS×region strata". Hot-deck needs donors that carry the value being
imputed. There are none inside this file. Every euro in the population would be a
**synthetic draw from external published distributions**, conditioned on what the
EEC *does* observe: PCS (`PCS1Q`, `STAT_CS`), sector (`NAFG*`), contract
(`SALTYP`, `STATUTDET`), hours (`HHABEMP`, `TXTPPRED`), public/private (`PUB3FP`),
age band, sex, diploma (`DIP7`), Métropole/DOM.

That is a defensible construction. It is not a measurement, and the reconciliation
report would have to say so in those words.

**29.0 M people (52.4 % of the weighted 15+ population) are in employment** and
would each need a wage invented. A further 2.3 M are unemployed and 24.1 M
inactive — of whom 13.4 M are 65-89, needing a pension.

## 4. Three further gaps, all discovered here, none in the spec

**4.1 Children under 15 are not in the file.** The EEC surveys the 15+ population.
`TYPLOG5` tells us a dwelling contains children; the children are not rows.

* 62 456 dwelling-quarters (31 %) are "famille monoparentale" or "couple avec enfant";
* of those, **27 863 contain no person under 25 in the file at all** — 6 254 lone
  parents recorded as a single person, 21 609 couples recorded as exactly two.
  Every dependent child in those households is invisible.

Consequence: `personnes_a_charge`, `nbptr`, `af`, `caseT` and the whole
quotient-familial machinery would run on children **synthesised from margins**
(source 5), not observed. The count and the ages would both be inventions.

**4.2 Age is banded into five groups, and one of them is the entire working life.**
`AGE6` gives 15-24 / 25-49 / 50-64 / 65-89 / 90+. The 25-49 band alone holds
20.2 M people (36.5 %). OpenFisca wants `date_naissance`; we would draw a year
uniformly inside a band. The ≥65 abattement (worth 224 € on a 30 k€ pensioner —
measured in Phase 0) is at least cleanly determinable, since 65 is a band edge.

**4.3 There is no region and no link-to-reference-person variable.**
Geography is `METRODOM` (métropole / DOM) and `STCOMM2020` (ville-centre /
banlieue / ville isolée / hors unité urbaine). The §4.1 schema's `region` column
cannot be filled from this file; `zone_apl` would be a mapping from
`STCOMM2020`, which is a proxy for urban density, not for the APL zoning.

There is no `LPR`/`LIEN` variable saying who is whose partner or child. Within a
dwelling we would infer it from `TYPLOG5` + `COUPL_LOG` + `ENFRED` + `AGE6` —
workable for the 82 % of households that are single-person, a couple, or a couple
with one visible child, and guesswork for the rest.

What the file *does* give us cleanly: `SO` maps one-to-one onto OpenFisca's
`statut_occupation_logement` (accédant / propriétaire / HLM / vide / meublé /
logé gratuitement), which is a genuine win for the housing block — though the
**rent amount is absent** and would also be imputed.

## 5. What this means for the branch decision

The spec's three branches assumed the household identifier was the pivot. It is
not: it is present, and the pivot turns out to be income.

| | Structure | Incomes | Children | Ages |
|---|---|---|---|---|
| **A' — EEC as it is** | observed (IDENT×TRIM) | **100 % synthetic** | synthetic from margins | 5 bands, drawn within |
| **C — ERFS via Progedo** | observed | **observed** (fiscal + social) | observed | exact |

Branch B (synthetic assembly) is moot — we have real households.

Branch A' is buildable and honest, and the reconciliation report is exactly the
instrument for stating its cost. But note what that cost is: the aggregate IR
yield the report validates against would be produced by a wage distribution we
constructed to match published wage margins. Hitting the IR total then partly
measures the calibration, not the model. §4.3's rule ("a margin used for
calibration is spent") is doing very heavy lifting in this branch, and the
number of genuinely independent validation lines shrinks.

Branch C removes all four gaps at once — incomes, children, exact ages, region.
It is not a marginal improvement here; it is the difference between a population
whose incomes are measured and one whose incomes are assumed.

## 6. Recommendation

Build **A'**, and treat branch C as the thing that would change the schedule
rather than the design: §4.1's parquet schema is identical either way (the spec
was right about that), so `skeleton.py` and `incomes.py` are the only modules
that differ. If ERFS is reachable, applying for it now and building A' meanwhile
costs nothing and de-risks everything.

Two decisions are Max's, and the second one changes roughly a month of work.

