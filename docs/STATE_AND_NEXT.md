# State of the project, and what is left — 2026-09-04

For the next implementing session: read this, then `docs/PHASE5_SPEC.md` *as
amended by D-078*, then the last two addenda of `docs/REVIEW_2026-08-29.md`.
This file supersedes the sequence in WHAT_NOW for "what happens next".

## Where we are

Every phase of the original architecture is built, guarded and on CI:
mechanical engine (DGFiP-validated to the euro), calibrated population
(person-weighted distribution lines now inside tolerance after the D-073
sweep; PPS sampler corrected, D-074), behavioural bands (verified store, one
live + newly-woken channels), macro fan (refusals enforced by tests), firm
module (all instruments inside tolerance on real cells), allègements +
prestations + niches knobs, niche imputation (opt-in, spent-registered),
narrow-band and double-entry guards, 544 test functions, full-pass log
discipline. Verification culture: four reviewer errors, multiple implementer
errors and four upstream artefacts caught by the machinery — the standing
rules in the review file are project law.

## In flight — Phase 5 (patrimoine), at the M0/M1 boundary

M0 is done and green (`scripts/verify_ifi.py`, `docs/M0_IFI.md`, D-078) but
**uncommitted — committing it is the first action**. D-078 supersedes spec
§2: the per-tranche base table does not exist; the barème-inversion design
with its two falsifiable properties replaces it, four tranches not six,
n° 45 (IFI 2025, 193 600 redevables) added to the vintages.

Remaining milestones, per spec as amended:
* **M1** — household IFI in the calculator: 2042-IFI-shaped inputs, goldens
  at every barème kink, the décote window (1.3–1.4 M), plafonnement 75 %,
  abattement RP 30 %. The engine chain is verified present; every parameter
  node still gets the phantom check.
* **M2** — cells from the inversion design; validation via D-078's
  falsifiable properties as the template; comparator vintages stated
  (assessment vs booking vs simulated year).
* **M3** — knobs: IFI barème/seuil/décote/plafonnement/abattement/dons; the
  ISF-2017 regime switch (dated parameters exist); the Zucman-style floor on
  the flagged ≥100 M extension cell (IPP Note 92 anchors, LOW confidence).
  Cell-bound uncertainty from extreme placements — never an invented density.
* **M4** — composition scaling (BdF/HVP, banded or the degraded
  "IFI-base lower bound" mode); behavioural fan-out (Garbinti pair: real
  ~0.05, reporting ~0.55; Spain 0.64 low-conf benchmark); the **enforcement
  dial beside the rate dial** — the module's signature.
* **M5** — UI tab, reconciliation patrimoine section (all-validation ledger,
  say so), the ISF-2017 historical backtest.

## Standing items that are NOT the session's

* **CAF cross-check**: prepared, not done, D-070 — needs Max at a browser;
  reCAPTCHA is never worked around.
* **ERFS**: submitted, waiting; interrupts everything on arrival; acceptance
  test is the barème-indexation backtest.
* **Upstream issue draft** and all of WHAT_NOW section C (publication,
  deployment, public repo): deferred by the owner; nothing posts.

## Backlog after Phase 5 (owner picks, do not start unbidden)

The trajectories phase (multi-year, indexation knobs — the other Phase-5
candidate, still live); niche coverage beyond ~55 %; the global-cap blind
spot (waits for real bases — do not fix with invented dispersion); the
maintenance charter (pin-bump ritual, annual LF cycle) — worth writing the
first quiet week.

## Rules in force

The review file's addenda, in full. In one breath: verify before building;
files, not agent prose; mechanical before economic; codes, not labels;
update() never creates; guards ship with kill tests and every check names
the implementation that would make it fail; comparisons are untested until
both sides have been non-zero; comparator vintage and perimeter stated
always; banded or absent, never confidently wrong; and reality beats every
spec, on the record.
