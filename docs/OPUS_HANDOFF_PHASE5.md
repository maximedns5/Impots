# Handoff prompt — Phase 5: Patrimoine

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are implementing **Phase 5** of the Impôts project: the wealth module —
IFI exactly, ISF revival and Zucman-style floors honestly. Read
`docs/PHASE5_SPEC.md` in full first, then the last three addenda of
`docs/REVIEW_2026-08-29.md` (the narrative-sweep obligation, the
name-the-failing-implementation rule, and the zero-masked-comparison rule all
bind here).

Working rules, beyond the standing ones:

1. First actions: suites green, full-pass log fresh; check whether the
   prestations knobs shipped (previous handoff §B) and record their status;
   then M0.
2. The engine's ISF-IFI chain is verified present [spec §1] but every node
   still gets the phantom check — the dead aide_a_domicile tree lives one
   namespace away from these parameters.
3. §2's design is the point of the module: the baseline is a mechanical
   check, ZERO calibration, and the reconciliation says so. If you find
   yourself fitting anything to the n° 33 table, stop — that is the design
   failing, not needing help.
4. Never invent a within-tranche density: cell-bound uncertainty is an
   interval from extreme placements, reported as its own uncertainty class.
5. The composition scaling (§4) ships banded or not at all; the degraded
   "IFI-base lower bound" mode is acceptable and a confident point is not.
6. Behavioural rows through the fan-out before loading; the enforcement dial
   ships beside the rate dial — it is the module's signature, from the
   project's first audit.
7. Comparator vintages stated on every published figure (assessment year vs
   booking year vs simulated year). No publication of anything — the owner
   has deferred all of section C; the upstream draft continues to wait.
8. ERFS interrupt above everything. Reality beats the spec, on the record.

Deliverables: `src/impots/patrimoine/` (cells, knobs, composition, bands),
household IFI in the calculator with kink goldens, the ISF historical
backtest, reconciliation section, UI tab with rate + enforcement dials,
decision log current.
