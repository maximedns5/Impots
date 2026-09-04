# Phase 5 — Patrimoine: Implementation Specification

**Project**: Impôts · **Phase**: 5 · **Owner decision** (2026-09-04, log it): the
next model phase is the wealth module; publication remains deferred; the
trajectories phase stays on the shelf as the other spec'd-in-principle option.
**Audience**: the implementing agent. Conventions unchanged. **[VERIFIED]** =
executed live against openfisca-france 176.0.8 on 2026-09-04. The ERFS
interrupt outranks every milestone. The prestations knobs (previous handoff §B)
remain open backlog if unshipped — check, and interleave at the owner's word,
not by default.
**Why this phase**: wealth taxation is the hottest live debate in French
fiscal politics (IFI reform, ISF revival, the Zucman-style floor), the
behavioural evidence is the best-identified in the entire literature, and the
module can be built almost without synthesis — which is what makes an honest
version possible.

---

## 0. What Phase 5 is

A patrimoine module that prices: **IFI under current law** (exactly, at the
household level; by cells at the national level), **parametric IFI reforms**
(barème, seuil, décote, plafonnement, abattement RP), **an ISF-style revival**
(the 1989–2017 regime is already dated in the parameter tree), and
**hypothetical instruments** (a Zucman-style minimum on ultra-high wealth) —
each with the wealth-tax behavioural pair as its band and an **enforcement
dial next to the rate dial**, which the evidence says matters more.

**Definition of done**:
1. Household calculator prices IFI exactly (2042-IFI-shaped inputs), goldens
   at every kink, décote window, and the plafonnement.
2. The cell population reproduces DGFiP's published per-tranche IFI to
   declared tolerance with **zero calibration** (§2 — the design makes the
   baseline a pure mechanical check).
3. Reform pricing carries cell-bound uncertainty honestly (§3); ISF/Zucman
   pricing carries the base-composition band visibly (§4).
4. Behavioural rows pass the fan-out before loading; the enforcement dial
   ships (§5).
5. Reconciliation gains a patrimoine section under the ledger rules; the ISF
   historical backtest runs (§6).
6. All standing rules honoured: kill tests, name-the-failing-implementation,
   zero-masked comparisons, comparator vintage, phantom check on every node.

**Out of scope — refuse**: succession/DMTG (a full phase of its own);
**household-level synthetic wealth** (cells only — a synthesized top tail is
the D-015 mistake at the exact percentiles where it is least survivable);
trajectoires; any migration channel beyond a low-confidence labelled band.

## 1. Engine state **[VERIFIED]** — L0 is mostly free

openfisca-france already carries the full ISF-IFI chain at foyer_fiscal/year:
`assiette_isf_ifi`, `isf_ifi_iai`, `decote_isf_ifi`, `isf_ifi_avant_plaf` /
`_apres_plaf`, `isf_ifi`, bases `isf_ifi_imm_bati` / `_imm_non_bati`,
réductions (dons, PME). Parameters at
`taxation_capital.impot_fortune_immobiliere_ifi_partir_2018`:
barème **[800 k: 0.5 %, 1.3 M: 0.7 %, 2.57 M: 1.0 %, 5 M: 1.25 %, 10 M: 1.5 %]**,
décote (17 500 − 1.25 % over 1.3–1.4 M), plafonnement 0.75,
abattement résidence principale 0.30, dons 75 % capped 50 k. Sibling nodes:
`impot_solidarite_fortune_isf_1989_2017` and
`impot_grandes_fortunes_1982_1986` — three dated wealth-tax regimes on the
shelf. Build duty: the **phantom check on every one of these nodes** (prove a
formula reads them — the aide_a_domicile precedent is exactly one namespace
away), and hand-derived goldens before anything else consumes the outputs.

## 2. The cell population — DGFiP tranches, zero synthesis

Source: **DGFiP Statistiques n° 33 (avril 2025), "L'impôt sur la fortune
immobilière en 2024"** (impots.gouv.fr, PDF located; manifest it, and sweep
for the sibling vintages 2022/2023 while there). It publishes, per tranche of
taxable wealth: redevable counts, taxable base, tax due. That table IS the
population. Design consequence, and the reason this module can be honest:

* **Baseline = validation, not calibration.** Apply our barème arithmetic to
  the published base per tranche and compare to the published tax per
  tranche. Nothing is fitted; agreement is evidence about our arithmetic and
  their table simultaneously. (Expect residuals from décote/plafonnement/
  réductions inside tranches — quantify, explain, tolerate explicitly.)
* **Reforms need within-tranche placement only at moving boundaries.** Do
  not invent a density: bracket the answer with the two extreme placements
  (mass at published mean vs uniform across the tranche) and report the
  interval as **cell-bound uncertainty** — a new, honest uncertainty class,
  distinct from parameter and scenario spread, shown as such.
* **The ≥100 M extension cell** (for Zucman-style floors) cannot come from
  n° 33. Anchor it on published figures only — IPP Note 92 ("Quels impôts
  les milliardaires paient-ils", built on POTE) for counts/aggregates at the
  very top — read from the PDF per D-026, LOW confidence, and the cell is
  visually flagged as a construction everywhere it appears.

Comparator-vintage rule applies with force: n° 33's year of assessment vs
budget-line booking year vs our simulated year — state all three.

## 3. Knobs

IFI: barème (scale — read-back + phantom + kill tests as always), seuil
d'assujettissement (1.3 M, distinct from the 800 k barème entry — a classic
confusion, golden it), décote parameters, plafonnement rate, abattement RP,
dons reduction. Regime knobs: **switch to ISF-2017 base and barème** (dated
parameters exist); **Zucman-style floor** (rate × threshold on the extension
cell + affected tranches). Chiffrage re-sweep: ISF→IFI 2018 itself has
published costings and outturns — the strongest wealth backtest available.

## 4. The base-composition problem — the module's hardest honesty test

IFI cells are **immobilier-only** wealth. ISF and Zucman-style bases include
financial wealth. Pricing them from IFI cells requires a per-tranche
composition scaling (total wealth / taxable immobilier), sourced from the
Banque de France distributional wealth accounts and HVP aggregates (open),
carried as a **banded factor, never a point**, and stated on every ISF/Zucman
output: the band is the composition uncertainty, and it does not shrink by
wishing. If the sourced composition evidence dies under the fan-out, ISF/
Zucman pricing ships as "IFI-base lower bound only, composition unmodelled" —
that degraded-but-true mode is acceptable; a confident scaling is not.

## 5. Behaviour — the pair, and the dial

Fan-out rows (D-026, adversarial verification, dead rows kill features):
real elasticity of taxable wealth to the net-of-tax rate ~0.05 [0–0.15]
(Garbinti, Goupille-Lebret, Munoz, Stantcheva, Zucman — French ISF,
tax-kink identification, HIGH confidence expected); reporting/enforcement
response ~an order of magnitude larger [0.3–0.8] (same source, the
information-threshold result); Spain 0.64 as low-confidence benchmark;
migration LOW confidence or absent. Product consequence, from the very first
audit and now buildable: **the UI shows an enforcement dial beside the rate
dial**, because the evidence says reported wealth responds to enforcement
design far more than to the rate. Behavioural bands apply the pair to the
reform's Δ net-of-tax rate per tranche; applicability grading as everywhere
(an ISF revival is within historical support — France ran it until 2017; a
2 % floor at 100 M is beyond it and grades `illustrative`).

## 6. Validation & reconciliation

Patrimoine section in the report: per-tranche mechanical check (§2), total
IFI yield vs the budget line (~2.2–2.3 bn recent years — verify exact
figures and vintages from the manifested sources, not from this sentence),
redevable count, and the **ISF historical backtest**: run the 2017 ISF
parameters against DGFiP's published 2017 ISF tranche statistics — a real
out-of-sample test of the regime-switch machinery on data that existed
before this project. Ledger rules: nothing here is calibrated, so every line
is validation — say so, it is the module's distinctive property.

## 7. Milestones

M0 download + recon gate on n° 33 (+ siblings, + IPP Note 92) →
M1 engine introspection + household IFI calculator with kink goldens →
M2 cells + the zero-calibration mechanical check →
M3 knobs incl. regime switch + cell-bound uncertainty →
M4 composition scaling + behavioural fan-out + enforcement dial →
M5 UI tab + reconciliation section + ISF backtest. ERFS interrupts anywhere.

## 8. Expected D-entries
Owner decision (this phase, publication deferred); n° 33 recon; composition
sourcing verdicts; behavioural fan-out verdicts; the backtest result; and
whatever this spec got wrong — found, as six phases have proven, by measuring.
