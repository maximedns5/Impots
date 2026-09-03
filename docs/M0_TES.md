# M0 — Reconnaissance of the INSEE symmetric input-output table

**Date**: 2026-09-03 · **Gate**: PHASE4_SPEC.md §3 · **Reproduce**: `python scripts/verify_tes.py [vintage]`
**Status**: **green on both published vintages.** The propagation layer (M2) may now be written.

The Phase 4 spec asked for five assertions before any Leontief code exists. Four hold
as written. The fifth — "the import matrix present and **non-negative**" — is false of
the published table, and asserting it fails on correct data. That is the finding, and
§4 explains what replaced it.

Two further defects surfaced only because the gate was written before the propagation
code rather than after: both totals read the same column, and final consumption meant
households alone. Neither would have raised. Both would have silently biased every
number the macro layer produced.

## 1. The files

| | |
|---|---|
| Source | insee.fr/fr/statistiques/8574722, Licence Ouverte / Etalab |
| Table | *TES symétrique* — branch × branch, already converted from supply-use form |
| Chosen | `insee_TES_symetrique_A38_2023SD.xlsx` (66 298 B, sha256 `319076fa…`) |
| Second witness | `insee_TES_symetrique_A38_2022DEF.xlsx` (66 185 B, sha256 `db4189aa…`) |
| Employment | `insee_cn2024_t6208_emploi_par_branche_a38.xlsx` (52 777 B, sha256 `51a94b81…`) |
| Branches | **37**, not the 38 the A38 name implies |
| Unit | millions of euros at basic prices, one decimal, as published |

Not committed: `data/raw/` is gitignored but for the manifest, and the tests skip
themselves when the spreadsheets are absent, so CI stays green on a clean clone.

**Vintage**: 2023SD (semi-definitive) is the base, because the macro layer's reference
year should be the most recent published. 2022DEF (definitive) is kept and the gate
runs against it too — a second witness is what showed the SIFIM cell in §4 to be a
provisional-data artefact rather than a permanent feature.

## 2. The five assertions

| Spec's question | Answer |
|---|---|
| Row totals = column totals per branch | **exact** — worst branch off by 0.000 M€ |
| Import matrix present and non-negative | present; **not non-negative** — see §4 |
| Leontief invertibility (spectral radius < 1) | **ρ = 0.4591** (2022DEF: 0.5380) |
| Employment coefficients positive and finite | **0.129 to 41.50** jobs per M€ |
| Vintage and base year recorded | both, and the base year travels with the table |

The accounts, as read:

| | 2023SD |
|---|---|
| Intermediate consumption, domestic | 2 064.2 bn |
| Intermediate consumption, imported | 630.9 bn |
| Total final uses | 3 245.8 bn |
| **Total emplois** | **5 310.0 bn** |
| Import leakage (imported / total IC) | **23.4 %** (2022DEF: 24.9 %) |
| Output multipliers | 1.000 (TZ) to 2.156 (KZ) |
| Employment | 30 395 thousand persons (2022: 30 064) |

The leakage figure is the one §1 requires to be *computed rather than assumed*. It is
computed, from the import matrix, and it is nearly a quarter — large enough that a
propagation layer ignoring it would overstate every domestic effect by roughly a third.

## 3. Three things the sheets do that the reader had to be taught

**The two sheets have different geometries.** On the domestic sheet the intermediate
matrix starts at column 45 with product codes in column 3; on the import sheet it
starts at column 10 with codes in column 9. Each sheet's block is now found from its
own headers. A reader carrying one set of constants reads the import matrix out of the
wrong columns.

**"Total des emplois" is a prefix of "Total des emplois finals".** A substring match
returned the same column for both, so the two totals came back identical at 3 245.8 bn
— and the balance identity closed anyway, because it was comparing a column with
itself. Found by reading the numbers, not by the code failing. Fixed with exact
matching; pinned by `test_the_two_totals_are_not_the_same_column`.

**Final consumption is four columns under one merged header.** Ménages / APU / ISBLSM /
TOTAL, with the institutional sector on the code row beneath. Matching the header alone
takes its leftmost column, so `consommation_finale` meant **households only**: 1 158.7
bn where the total is 1 888.2 bn. The aggregate balance stayed green throughout,
because it rests on a different published column. It surfaced from adding the
components up by hand and finding 730 bn missing.

The gate now checks the components against their totals — the check that catches a
wrong column, where the headline identity cannot:

```
consommation_finale     = menages + apu + isblsm            off by 0.000 M EUR
formation_brute_capital = fbcf + objets_de_valeur + stocks   off by 0.000 M EUR
total_emplois_finals    = CF + FBC + exportations            off by 0.000 M EUR
total_emplois           = emplois finals + IC                off by 0.000 M EUR
```

The institutional split is kept rather than collapsed: a public-spending shock and a
household-transfer shock enter through different columns, and the MPC that applies to
one does not apply to the other.

Employment brought two of its own. The nomenclature is hierarchical — a branch is
written at the coarsest level where it coincides with itself — so three branches carry
an A17 code with a different letter (`CA`→`C1`, `CD`→`C2`, `CL`→`C4`); matching by
suffix alone left ten branches unmatched, which a zero-fill would have turned into ten
branches contributing no jobs to any shock. And the year headers are **strings**, so an
`isinstance(..., int)` lookup found no years at all and reported it as a missing year.

## 4. Where the spec was wrong: the table is not non-negative

One cell is negative in 2023SD, in both matrices:

```
KZ -> LZ   domestic  -23 893.2 M EUR      imported  -309.4 M EUR
           (financial services consumed by the real-estate branch)
```

This is the SIFIM adjustment — financial intermediation services indirectly measured,
whose interest component on household housing loans is booked as household final
consumption rather than as intermediate consumption of the real-estate branch, leaving
the correction as a negative cell. It is published data: the product balance closes on
it exactly, to 0.000 M€. It is absent from 2022DEF, so it is a feature of the
semi-definitive vintage, not a permanent one.

**Measured consequences**, rather than assumed ones:

* one negative technical coefficient, `A[KZ, LZ] = −0.0586`;
* two negative entries in the Leontief inverse, largest magnitude 0.0883;
* every **column multiplier stays ≥ 1** — 1.000 (TZ) to 2.156 (KZ) — so a unit of final
  demand still raises total output for every branch, which is the property propagation
  actually rests on;
* zeroing the cell would move branch multipliers by at most 0.130 (LZ), mean 0.007.

**Decision — the cell is kept as published, not clamped.** Reality wins over the spec.
Clamping would break the balance identity that currently closes exactly, to buy a
non-negativity nothing downstream needs. What the gate asserts instead is the set of
properties that do matter, and that survive the negative:

* negatives are **few enough to enumerate and name** (ceiling 5 — a scattering would be
  a misread sheet, not an accounting convention);
* every **per-cell import share** lies in [0, 1] — 0.0000 to 0.9918;
* every **per-branch import share** lies in [0, 1] — 0.000 to 0.725;
* every **output multiplier is at least unity**.

The IO layer must therefore never assume non-negativity of the table. Recorded as
D-048.

## 5. The chosen aggregation

**A38 as published: 37 branches.** It is the finest symmetric table INSEE publishes;
A17 and A88 exist, but A88 is published only in supply-use form and would need a
symmetrisation this project has no business performing. The name says 38 and the file
carries 37 — the count is read from the file, and the gate asserts it was read rather
than assumed.

The two employment outliers were checked rather than trimmed, and both are real:

| | jobs per M€ | output | jobs | |
|---|---|---|---|---|
| TZ | 41.50 | 3.3 bn | 138.0 k | households as employers — output is essentially wages alone |
| CD | 0.13 | 48.1 bn | 6.2 k | coking and refining — capital-intensive |

## 6. What M2 inherits

* `impots.macro.tes.load(vintage)` → branches, both matrices, eleven final-use vectors,
  total output, vintage, base year.
* `impots.macro.tes.employment(branches, year)` → thousands of persons, ordered to
  match, raising rather than zero-filling a gap.
* Leakage is **computed** (23.4 %), never assumed.
* Multipliers from the literature already contain IO propagation; the table supplies
  **composition**, not a second round of size. The anti-double-counting rule stands.

## 7. Open

* The negative SIFIM cell should be re-checked when 2023 goes definitive — if it
  persists, it is structural rather than provisional, and `test_the_published_table_is_not_non_negative` is where that gets noticed.
* ERFS remains the interrupt that outranks these milestones.
