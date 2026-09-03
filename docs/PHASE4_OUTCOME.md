# Phase 4 — outcome

**Date**: 2026-09-03 · **Spec**: `PHASE4_SPEC.md` · **Handoff**: `OPUS_HANDOFF_PHASE4.md`
**Status**: M0 through M5 complete. Suite 556 passing.

The layer ships. What follows is the short account of what it does, what it refuses, and
where the spec turned out to be wrong — which is the part worth reading, because it is
the fifth phase in a row where the specification's assumptions did not survive contact
with the primary sources.

## 1. What shipped

| | |
|---|---|
| **B1** `shocks.py` | reform deltas → instrument-labelled fiscal impulse, with double entry and the product allocation |
| **B2** `io_layer.py` | first-round sectoral composition and import leakage, from the TES — shares and fractions only, never a level |
| **B3** `fan.py` | seeded Monte Carlo, p10/p50/p90 per indicator per horizon, spread decomposed |
| Readers | `tes.py`, `mesange.py`, `imk.py` — every calibration figure parsed from a primary file by tested code |
| Store | `store.py` — refuses any row a verifier has not passed; dead rows carry their reasons |
| Validation | the CICE containment gate, passing on both bracketing variants with nothing tuned |
| API + UI | a `Macro` block behind an opt-in flag; L4 rendered quieter than L3, with its assumptions strip non-optional |

## 2. What the spec got wrong

Six items, each found by measuring rather than by reading.

| Spec said | The data said | Recorded |
|---|---|---|
| the import matrix is "present and **non-negative**" | it is present; one cell is −23.9 bn (the SIFIM adjustment), and the balance closes on it exactly | D-048 |
| multipliers are "0.2–0.6 tax-side, 0.5–1.2 spending-side" | a year-one range wearing no horizon (0.72–0.90 at three years), and a ceiling excluding public investment's own 1.31 | D-051 |
| "1.3–2.5 in slack" | no source: Mésange is linear, and the literature is openly split | D-052 |
| "MPC by income position, French evidence first" | the French evidence measures propensity out of **wealth** along the **wealth** distribution — a different object | D-052 |
| an "Okun-style employment-output linkage" | Mésange supplies something better and instrument-specific: 290k jobs at three years for employer contributions against 107k for generic spending | D-051 |
| the IO layer supplies "the import-leakage correction **which scales the impulse** handed to B3" | Mésange's multipliers are already net of import crowding-out; scaling would double-count | D-058 |

The last is the one that would have done the most damage, because it is the instruction
a careful implementer follows. It removes about a quarter of every effect and leaves
nothing looking wrong.

## 3. What the layer refuses, and why that is the product

* **No revenue-feedback loop.** The elasticity row returned WRONG. Δdéficit stops at
  mechanical plus behavioural; the layer does not claim to close the public balance.
* **No cycle-state scenario for tax instruments.** The regime effect is established on
  the spending side (+0.769 in a downswing, upswing not significant) and every
  instrument here is fiscal. The toggle refuses itself with its reason on screen.
* **No multiplier for transfers.** Borrowing the generic-spending variant would
  overstate by two to three; the meta-analyses put transfers at 0.39 and 0.54 against
  1.01 and 0.90 for spending.
* **No multiplier for corporate instruments.** They do not inherit the
  employer-contribution one: labour cost is not capital cost.
* **No horizons past three years.** The long columns are set by a specification choice —
  employer contributions run 1.73 at LT under wage-setting and 0.25 under a Phillips
  curve — which converges with §0's independent refusal of horizons past three years.
* **No point estimate, anywhere.** There is no mean in the renderer and none in the fan.

Most reforms this repository can express therefore get **no macro path at all**, and the
UI renders that as a block with a reason. That is the designed outcome, not a gap.

## 4. The verification, and what it cost

Ten adversarial verifiers over five parameter rows, 113 findings, one WRONG and nine
SCOPE_PROBLEM (D-055). **No transcription error anywhere** — all 48 Mésange values, all
28 IMK columns, every page reference exact. Every defect was in what the numbers were
said to mean.

The single most consequential finding was specific to this repository: Mésange's
labour-tax variants are non-targeted, the document publishes a targeted counterpart, and
Phase 3's entire allègements work moves exactly the knobs that would have taken the
uniform multiplier — **290k jobs at three years instead of 403k**.

It also caught two D-026 violations by the implementer (D-056): figures in a `note:` and
a sentence in a `quote:` that came from search-engine summaries rather than from the
cited documents. Values were being parsed from primary files by tested code while the
prose around them was not, and nothing checked the prose. There is now a test comparing
every `quote:` field to its PDF letter by letter.

## 5. Numbers a reader can check

* TES 2023SD: 37 branches, IC 2 064.2 bn domestic + 630.9 imported, final uses 3 245.8,
  total 5 310.0; GDP at acquisition prices 2 871.7 bn; ρ = 0.4591.
* Import leakage: **27.4 %** for a consumption-shaped impulse (12.8 % direct),
  **33.6 %** for capital formation. Computed, reported, not applied.
* A 5 bn CSG cut: first-year GDP band **−2.4 / +2.2 / +6.7 bn**; jobs at three years
  **+0.5 / +29 / +58** thousand FTE.
* CICE containment: uniform **[−39, 239, 517]**, targeted **[−35, 332, 699]** thousand
  FTE at three years, against a published 100–400.

## 6. Open

* **ERFS remains the interrupt that outranks everything here**, with the
  barème-indexation backtest as its acceptance test (`PHASE1C_ERFS.md` §6).
* The Mésange conclusion warns its results are not meant to be transposed to evaluating
  past policies. The CICE episode records that and is labelled a sanity check on the
  machinery, not a validation of the parameters. A second episode on a prospective
  reform would be worth more than a second backtest.
* `multiplier_regime_shift` is loaded, sourced, and unusable by any reform this
  repository can currently express. It should stay that way until a spending instrument
  exists.
* The derived GDP (2 871.7 bn) has not been cross-checked against a published figure.
  The only anchor is Mésange's own «22 Md€ en 2015». It scales every employment number.
