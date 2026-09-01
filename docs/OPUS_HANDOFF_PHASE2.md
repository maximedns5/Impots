# Handoff prompt — Phase 2 build

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are implementing **Phase 2** of the Impôts project: the firm module — IS,
CVAE, C3S priced mechanically over a synthetic firm population, with its own
reconciliation report. Phases 0-1 are built and green; the review verdicts of
2026-08-29 (docs/REVIEW_2026-08-29.md) are accepted project decisions.

**Read `docs/PHASE2_SPEC.md` in full first.** Conventions unchanged:
[VERIFIED] items were executed live (scripts/verify_firm_engine.py reproduces
the engine pattern — run it before building); [ENACTED] tax parameters were
checked against post-LF-2026 secondary sources and each must be confirmed
against BOFiP/Légifrance during M1, recording the confirmation in the YAML
comment.

Working rules:

1. **First actions**: full test suite green; `python scripts/verify_firm_engine.py`
   green; then the REVISED §0.5 pre-flight (2026-09-01): the old P1–P4 are
   closed — what blocks you is extracting and TESTING the shared reconciliation
   machinery out of `population/reconcile.py` before building the firm report
   on it. Read `docs/AUDIT_2026-09-01.md` §04 and §07 first: the weight-defect
   and formatter-defect entries are the regression tests to write.
2. **The ERFS interrupt rule stands**: the day Progedo delivers, pause Phase 2,
   run the Phase 1C migration, come back.
3. Firm golden tests use RELATIVE tolerance 1e-5 (float32, spec §1.4) — never
   ±2 €. Every scale-shaped parameter gets a read-back verify (D-007 is
   portable).
4. Never name a parameter node `is` (spec §1.2). CFE is not simulated in v1
   (spec §2.5) — do not improvise it.
5. §3.4's calibration/validation separation is the same hard rule as Phase 1:
   C3S, CVAE, IS receipts and the zero-IS share are validation lines and must
   never be tuned to.
6. Reality wins over the spec, on the record — expected entries D-018..D-022,
   plus whatever you find that this spec got wrong.
7. Out of scope stays out: groups/intégration fiscale, tax credits,
   employer-contribution reforms, behaviour, TVA, exact CFE.

Deliverables: `src/impots/entreprises/` (system, variables, parameters YAML,
reforms, population, runner, reconcile), scripts kept green, firm goldens,
`reports/reconciliation_entreprises.md`, API endpoint + UI tab, updated README,
closed pre-flight ledger.
