# Phase 7 — The Accuracy Campaign: Specification

**Project**: Impôts · **Phase**: 7 · **Nature**: not construction —
refinement, ordered by measurement. Conventions unchanged; all standing
rules bind; UNMEASURED labels appear where the new anchor rule requires
them. The **PLF 2027 interrupt** (early October) stands over every stage;
the ERFS interrupt stays dormant; owner-gated items stay owner-gated.

## The organising principle

The question "what makes the model more accurate" is itself an empirical
question, and this phase refuses to answer it by intuition. **A0 runs
first and its ranking orders everything else.** Levers are then taken in
descending measured importance, each behind its own gate, and a lever the
budget ranks low is *recorded as deprioritised with its score* — refusing
work is a result here, exactly as refusing a chiffrage was in F1.

## A0 — the accuracy budget (the phase's spine)

On a fixed, committed set of reference reforms (one per instrument family:
barème, allègements, prestations taper, niches, IS, CVAE, IFI, a
trajectory case), run a variance attribution across every declared
uncertainty source: the parameter store's distributions (Monte Carlo,
existing machinery), the uprating pair, cell-bound intervals, composition
band, incidence assumption, and — approximated by sensitivity where
sampling is impossible — the population-construction choices themselves
(the D-015 residual, proxied by the aged/frozen and person/household-
weighting deltas already measured). Output: **per reference reform, the
share of output variance attributable to each source**, committed as
`reports/accuracy_budget.md`, prose computing its own numbers. Method:
variance-based ranking (Sobol where distributions exist, one-at-a-time
bounds elsewhere — state which, per source). The budget is measurement
infrastructure: three questions, kill test (a synthetic case with a known
dominant source must rank it first).

## The candidate levers A0 ranks (each gated, none pre-committed)

* **L1 — top-tail recalibration.** DGFiP n° 41 reaches the top millième
  (confirmed by the F1b gate). Rake the synthetic income distribution's
  upper tail to the published centile/millième tranches — opt-in,
  spent-registered, artefacts declared like every imputation. Expected to
  matter for: top-decile ETI reforms, CDHR-adjacent questions, the IR top
  lines. The threshold-on-ratio refusal class is unaffected and stays.
* **L2 — the take-up layer.** Replace grade-time take-up bridges with an
  explicit, opt-in claiming model for RSA/PPA/AL, calibrated to DREES
  non-recours evidence read from the publications (files, not prose;
  verifier pass on every rate). Converts bridge-adjusted grading into
  modelled levels — and the bridges' spent/validation bookkeeping moves
  accordingly, stated in the ledger. Expected to matter for: every benefit
  line, the bottom-decile distribution, prestations reform pricing.
* **L3 — the behavioural evidence season.** Re-open the store with the
  verifier machinery at full strength: the eight disaggregated
  Bargain-Orsini-Peichl France rows (the averages died; the rows exist),
  ETI refinements (Sicsic, Lehmann et al.), and any wealth-pair support
  sharpening. Dead rows stay dead unless a paper's own table revives them.
  Expected to matter for: band widths everywhere; possibly reviving a
  dormant channel honestly.
* **L4 — firm-side depth.** Sectoral fiscal-to-accounting ratios (Stat 39
  by-sector effective rates in place of the single national ratio), and a
  deficit-carry-forward stock from published aggregates (UNMEASURED: which
  DGFiP publication carries the stock of déficits reportables — the gate
  finds out). Expected to matter for: the IS line's ±20 % gate, the two
  red sectors (run the perimeter diagnostic from the 2026-09-02 addendum
  if it never ran).
* **L5 — niche coverage** past ~55 %, and the remaining prestations UI
  knobs if any survive.
* **L6 — small closures.** The 55 unexplained REI communes; D-113/D-114
  style instrument sweeps as they arise.

## Standing measurement, not a lever: the grading calendar

When outturns and évaluations préalables publish, grade everything
pre-registered — the chiffrage suite and the PLF pre-registrations are the
only accuracy measurements that cost nothing and cannot be argued with.
S4's interrupt executes the PLF week as specced in Phase 6.

## Sequencing

A0 → levers in A0's order, one per session-or-two, each behind an M0-style
gate, each ending with the budget re-run so the ranking updates on the new
state — the campaign converges when the top-ranked lever is one the
project refuses (data-gated) or the owner stops it. Reports per stage;
D-entries as always; reality beats this spec, on the record.
