# Handoff prompt — Phase 4 build (the macro fan)

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are implementing **Phase 4** of the Impôts project: the macro layer — ΔGDP,
Δemployment, Δdeficit as an explicit fan. Phases 0–3 and the hardening
increment are built; the review file's addenda are project law; the owner has
decided: deployment stays private, and this fork is the one being taken.

**Read `docs/PHASE4_SPEC.md` in full first.** The one architectural rule that
must survive every implementation pressure: **multipliers and the IO table
have disjoint jobs** — aggregate path from literature multiplier ranges on the
leakage-corrected net impulse; sectoral composition and import leakage from
the TES; never both propagating the same euro. The spec's §1 anti-double-
counting rule has an assertion and a kill test with its name on it.

Working rules:

1. First actions: suites green, full-pass log line fresh, then M0 — the TES
   reconnaissance gate. No propagation code before `verify_tes.py` is green
   and `docs/M0_TES.md` is written. The EEC M0 changed the shape of its
   problem; assume this one might too.
2. M1 is the verifier fan-out over every macro parameter. The multiplier and
   MPC seeds in the spec are reviewer-compiled and therefore suspect by
   precedent (`eti_all` was killed at 2.5× its true value). Dead rows kill
   their features, visibly.
3. Every guard ships with its kill test — no exceptions, per the standing
   rule. Double-entry extends to shock construction.
4. The CICE containment test is the acceptance gate: the employment fan must
   contain 100k–400k jobs for the CICE-shaped impulse. If it fails, stop and
   understand before shipping — do not widen parameters to pass (that is
   calibrating to a validation line; §4.3's rule applies to macro too).
5. The fan never renders without its assumptions strip; the L4 banner ships
   verbatim in spirit; mechanical and behavioural presentation unchanged,
   regression-tested.
6. ERFS interrupt above all milestones. Out of scope stays out: no forecast,
   no monetary policy, no debt dynamics, no horizon past 3 years, no DSGE/CGE/
   ABM revival under any framing.
7. Reality beats the spec, on the record — D-entries as always.

Deliverables: `src/impots/macro/` (shocks, io_layer, fan), `scripts/verify_tes.py`,
`docs/M0_TES.md`, parameter rows with verdicts, the containment test in the
gate suite, UI fan with strip and decomposition, decision log current.
