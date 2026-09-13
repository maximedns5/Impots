# Handoff — Phase 7 closure (C1–C4), then Phase 8

**From:** the reviewer session, 2026-09-13. **Read first:** the 2026-09-13 addendum in docs/REVIEW_2026-08-29.md, then this. Phase 8 (docs/PHASE8_SPEC.md, docs/OPUS_HANDOFF_PHASE8.md) is written and waiting — **it starts only after C4 is reviewed.** Owner's sequencing.

## First, a correction to your own report

The durations lead does not survive verification: **nine** (not eight) of the top 15 are API tests, **all fifteen are slow-marked** — the API nine through `@population_test`, which composes `pytest.mark.slow` (test_api.py:375), invisible to a grep for the literal decorator — and the POSTs are **tier "quick"**, not full-tier. The fast gate already skips them all. Full reasoning and the ruling in the addendum. Write the D-entry (the composed-mark grep trap; check markers by asking pytest — `--collect-only -m slow` against the expected set — not by grepping source). Baseline memoisation across API tests is **refused by default**; take it only if you also build the cache-poisoning kill test the addendum specifies.

## The closure milestones

Terminal states already assigned, no work needed: L1 landed; L2 **dormant interrupt** (blocker: DREES quarantine; wake: a sourced, manifested take-up file — register it beside the ERFS interrupt in STATE_AND_NEXT.md); L3 closed as recorded; L4's two refusals closed as recorded.

- **C1 — L4 perimeter diagnostic.** The 2026-09-02 addendum procedure on the two red sectors (industrie +38.3 %, immobilier −70.9 %), which never ran. Mechanical before economic. Terminal state per sector: a named perimeter cause, or a red pin with « no hypothesis » recorded. Both close it; only silence doesn't.
- **C2 — L5.** Niche coverage past ~55 % and any surviving prestations UI knobs, per the Phase 7 spec's own L5 line. Every niche behind its data gate; a gate that fails converts the niche to refused-with-reason, and that closes it too. Phantom-check every newly claimed parameter node; V&M tome II comparisons state vintage and the budget-year column.
- **C3 — L6.** The 55 unexplained REI communes to a terminal state (named cause, or pinned with the count and the attempt recorded). The durations item closes with the D-entry above.
- **C4 — A0 final re-run + docs/PHASE7_CLOSING.md.** The closing measurement, not a summary: re-run the budget on the post-lever state. Raked lines must come back « not comparable (queue recalée) » **by construction** — if one renders a verdict, that is a defect in the refusal, not a validation to report. The closing report speaks to the movement of unspent lines only, states what the campaign bought and what it refused, logs the full pass, rewrites STATE_AND_NEXT.md, and stops. Reviewer verdict before the phase is called closed.

## Standing

PLF 2027 (early October) interrupts anything, including this closure — park cleanly if it lands mid-milestone. Nothing publishes. Reality beats this handoff, and the addendum beats both; divergences to DECISIONS.md as always.
