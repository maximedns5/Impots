# Handoff — Phase 8 : le laboratoire de politique fiscale

**For:** the implementer session. **From:** the reviewer session, 2026-09-11.
**Read first, in order:** this file → docs/PHASE8_SPEC.md (the whole thing) → docs/REVIEW_2026-08-29.md (latest addendum) → your own DECISIONS.md tail.

## What this phase is

The owner's request, verbatim intent: a laboratory where he can move **the maximum of different taxes and impôts — on products, on people, on companies** — and see what happens to receipts, to the **national debt trajectory**, and to a **reindustrialization panel**. The spec turns that into six milestones. The framing you already know holds: mechanical exact → band → fan, honesty is the product. Three phase-defining refusals: the explorer never optimizes on banded quantities; no debt path renders without a **named spending scenario** (spending is ~57% of GDP and we microsimulate only transfers — the tool must never silently imply taxes alone carry the burden); the reindustrialization panel prices instruments and renders the IPP zero-band, and never promises factories.

## Order of work

**M0 recon before any design freeze.** docs/M0_PHASE8.md per spec §1 (R1–R8): locate, download on the owner's network (container and VM are proxy-blocked for insee.fr and friends — established), manifest with sha256. You locate and verify; you never author figures (D-026). Report to the reviewer; items that come back "does not exist" convert instruments to refused-with-reason — that is the gate working.

Then **M1 (debt closure) first** — it is the spine. Then M2 (aggregate engine + produits), M3 (entreprises + personnes + coverage table), M4 (explorer), M5 (panel), M6 (consolidation). Each milestone: report in the usual format; divergences from spec are expected and go to DECISIONS.md — reality beats the spec, on the record.

## Hard points to not rediscover

- Anchor correction: public debt end-Q1 2026 = **3 536.1 bn € / 117.5% PIB** (INSEE Informations rapides n°158) — measured 2026-09-11; the reviewer's earlier conversational "~3,300/~114%" was stale and is superseded (ledger #9). The 2026 interest charge ≈ 77 bn is **UNMEASURED** until you manifest the PLF 2026 mission « Engagements financiers de l'État » doc.
- AFT publishes « Encours détaillé des OAT » + BTF + auction data; mirrors on data.gouv.fr. Identifiers, not URLs, are load-bearing (pointer rule).
- The debt identity backtest (2019→2025) uses **realized SFA** — omitting it and passing means you fitted, not tested.
- Mésange multipliers are net of imports. Do not re-add leakage. (Incident on record.)
- Voies et Moyens: budget-year columns. (Incident on record.) Every B-instrument receipts anchor states year + source + sha256.
- The aggregate engine's distributional refusal is an **allowlist** with kill tests you have seen fire. `refuse_banded`'s denylist history is the cautionary tale.
- Extend the double-entry identity over the aggregate layer and test it against a deliberately broken ledger — the first version self-balanced.
- CDHR stays refused; DMTG stays gate-only (F7); PFU population stays gated on F1b. "Maximum d'instruments" does not reopen closed refusals.
- Phase 7 owns population/calibrate.py and the L-lever files — do not touch them from Phase 8; write the reviewer a note instead.
- PLF 2027 (early October) interrupts everything; park cleanly.
- Nothing publishes, nothing deploys (input-hardening precondition stands; owner gate).

## DoD reminders you will be graded on

Guards with kill tests seen to fire; anchors [VERIFIED]/[ENACTED-confirm-at-BOFiP]/UNMEASURED-then-measured; tolerances measured with `binding`, pre-registered by commit; comparator vintage & perimeter stated; codes not labels; phantom-check any OpenFisca node you newly claim; aged AND frozen displays on trajectory outputs; `make full` green with the pass logged.

Questions, contradictions between this handoff and the spec, or between the spec and reality: the spec wins over this handoff; reality wins over the spec; put it on the record either way.
