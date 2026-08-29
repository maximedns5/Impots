# Handoff prompt — Phase 1 build

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are implementing **Phase 1** of the Impôts project: the synthetic population
and distributional engine — any household reform, priced for the country, with
winners/losers by decile and a published reconciliation report. Phase 0 is built
and green; do not regress it.

**Read `docs/PHASE1_SPEC.md` in full before writing any code.** It is written
against the code as you (a previous session) actually built it — including
D-005/6/7 — not against the Phase 0 spec. Everything marked [VERIFIED] was
executed live, including the population-scale OpenFisca mechanics, which
contain two failure modes you must internalise before touching the builder:
roles are flattened SUBROLE keys and fail SILENTLY otherwise (nbptr=0, no
exception), and enum defaults crash the benefits cascade unless all 36 months
of N-2..N get explicit inputs.

Working rules:

1. **First actions, in order**: run the existing test suite (must be green);
   run `python scripts/verify_population_engine.py` (must print "assumptions
   hold"); then do the three §0.5 pre-flight items — including flipping
   `historique_revenus` to True and re-anchoring the affected goldens with a
   D-011 entry. That decision is taken; the spec is the record.
2. **Milestone M0 is a gate.** Download the EEC data (normal network required —
   if your environment cannot reach insee.fr, ask Max to download the three
   files into data/raw/), run your `verify_eec.py`, write `docs/M0_RECON.md`,
   and **stop to ask Max two questions** before design freeze: (a) which M0
   branch the data supports, and (b) whether a live academic affiliation makes
   branch C (ERFS via Progedo) available. Do not guess (b).
3. Milestone order M0 → M5 is strict. No UI number ships before the
   reconciliation report exists (M4 before M5).
4. The calibration/validation separation in §4.3 is an epistemic rule, not a
   style preference: a margin used for calibration is spent and can never be a
   validation line.
5. Guards are not optional: nbptr.min() >= 1 and NaN-count == 0 after every
   population run.
6. Reality wins over this spec, on the record in docs/DECISIONS.md — same as
   D-005/6/7. Expected entries: D-011..D-014 (spec §9).
7. Out-of-scope (§0) stays out: no firms, no behaviour, no indirect taxes, no
   top-tail claims.

Deliverables: `src/impots/population/` (ingest, skeleton, incomes, calibrate,
to_openfisca, runner, aggregate), `scripts/verify_eec.py`,
`scripts/verify_population_engine.py` (shipped — keep green), CLI entry points,
`reports/reconciliation.md` (generated), API quick tier + UI population tab,
tests + fixture sample, updated README.
