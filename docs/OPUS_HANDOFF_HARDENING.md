# Handoff prompt — hardening increment (post-knobs)

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are continuing the Impôts project after the knobs increment (D-033..D-042)
shipped and was reviewed. The final addendum of `docs/REVIEW_2026-08-29.md` is
accepted project law — read it first. Nothing from the previous handoff is
outstanding; this increment is hardening: it turns the last cycle's four
findings into structure. The ERFS interrupt rule stands above everything —
the day Progedo delivers, drop this and run Phase 1C (its acceptance test is
the barème-indexation backtest, per PHASE1C_ERFS §6).

Work items, in order, one commit each with its decision-log entry (D-043+):

1. **CI, for real.** The remote exists (github.com/maximedns5/Impots) and the
   workflow has never executed on a real runner. Push, watch the Actions run,
   and fix what a real runner surfaces (paths, timeouts, the pip cache, the
   fixture-only data path). Done means: a green run on GitHub visible in the
   README badge, and from now on nothing merges red. If the run is green on
   the first try, say so in the log — that is a result, not a non-event.

2. **`update()` may never create.** Wrap every reform parameter write so that
   targeting a node absent at the reform's start date is an error by default;
   node creation is a separate, explicit operation with its own name. This
   closes D-042's class, not its instance. Then audit every `verify_*`
   function once for the shared-write-path pattern (a check comparing against
   what the write path now contains rather than an independently constructed
   expectation) and record what you find either way.

3. **The double-entry identity.** Every reform run — household and firm —
   asserts that sector deltas balance: what households and firms gain, the
   state loses, to a stated tolerance. Wire it into the runners as a guard in
   the same family as nbptr>=1 and NaN==0. The 17.7 bn/zero-cost bug is the
   regression test: re-express it and prove the identity kills it.

4. **The narrow-band flag.** Per reform, compute the share of mechanical yield
   from households inside a small window around the reform's own thresholds
   (window and share-threshold are declared constants, logged in the decision
   entry). Above threshold, API and UI carry the specific D-015 caveat: the
   yield turns on a narrow wage band where the synthetic density is least
   reliable, and the level is likely overstated until ERFS. The +107 % cliff
   backtest case is the test: it must trigger the flag; the barème indexation
   case must not.

5. **Tier the suite.** Chiffrage cases whose instruments touch neither
   benefits nor housing run light-tier; mark the rest. pytest marks split a
   default gate (target < 5 min locally) from the full pass (CI always, or
   nightly). No case is deleted or weakened — only re-tiered, and the full
   pass still runs somewhere on every merge day.

Boundaries: do NOT start Phase 4 (macro layer / indirect taxes) — that fork is
a project decision to be taken with the owner, not an implementation default.
Do not touch the mechanical layer's results or presentation; items 2–4 are
guards and metadata, and every existing golden must pass unchanged. Rules in
force as always: mechanical before economic; codes, not labels; files, not
agent prose (D-026); no unverified parameter loads; reality beats this brief,
on the record.
