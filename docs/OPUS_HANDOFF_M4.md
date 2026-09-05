# Handoff prompt — Phase 5 M4 (+ ordered debts)

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are continuing **Phase 5 (patrimoine)** of the Impôts project, at the
M3→M4 boundary. M3 shipped and was reviewed (final addendum of
`docs/REVIEW_2026-08-29.md` — read it first; every ruling below comes from
it). 886 tests, 52 knobs, the barème knob verified against hand arithmetic,
the merge guard living in the spec validator with a kill test on openfisca's
own merge behaviour. The ERFS interrupt outranks everything, as always.

## A. Pre-flight — two reviewer debts, now mandatory, one commit each

These have survived two cycles as backlog and are ordered done BEFORE any
composition work:

1. **The narrative sweep.** D-073 moved D9/D1 from +39.1 % to +3.6 %
   (person-weighted, the statistic INSEE actually publishes), which means
   several documents still tell the old story of Phase 1's "most informative
   failure" as a density defect. Find every place the old narrative survives
   — reconciliation notes, banners, PHASE1C_ERFS's case, README, the audit
   artifacts' repo copies — and update each to the surviving evidence (the
   +107 % cliff backtest, the RSA lines, the zero-income population). The
   ERFS migration stays fully justified; its argument must cite what stood,
   not what fell.
2. **The name-the-failing-implementation audit.** For every guard and test
   in the inventory, ask: what implementation would make this fail? A check
   with no failing implementation is decoration (the PPS sampler's
   weight-preservation guard was the proof). Record the audit's findings
   either way; fix or annotate what it catches.

Also in pre-flight, ruled and quick: **track `data/raw/MANIFEST.json` in
git** — hashes, URLs, dates, licences; provenance metadata, no data; the
73-entry unsourced section is part of the record, not a reason to hide it.

## B. M4 — the build

1. **Composition scaling** (IFI cells are immobilier-only; ISF-style bases
   are total wealth): per-tranche factor sourced from the Banque de France
   distributional wealth accounts and HVP aggregates — files manifested and
   read per D-026, comparator vintages stated. Carried as a **band, never a
   point**. If the sourced evidence dies under verification, ship the
   degraded mode: "IFI-base lower bound only, composition unmodelled" —
   degraded-but-true beats confidently scaled, by standing ruling.
2. **The behavioural fan-out** for the wealth rows: the Garbinti pair (real
   elasticity ~0.05 [0–0.15]; reporting/enforcement response ~0.55
   [0.3–0.8]), Spain 0.64 as low-confidence benchmark, migration
   low-confidence or absent. Same machinery as every store row: adversarial
   verification before loading, dead rows kill features visibly. Expect the
   Phase-3 pattern: values may hold while supports and citations need
   repair — the eti_top_decile support correction is the precedent to
   re-read before grading "in-support" for wealth reforms.
3. **The enforcement dial**, beside the rate dial — the module's signature,
   promised since the project's first audit. The evidence says reported
   wealth responds to enforcement design roughly an order of magnitude more
   than to the rate; the UI must make that legible, with both dials feeding
   the band and the applicability grade.

## C. Then M5 closes the module

UI tab; reconciliation patrimoine section (all-validation ledger — nothing
in this module is calibrated; the report says so as its distinctive
property); the **ISF-2017 historical backtest** (2017 parameters against
DGFiP's published 2017 ISF statistics — the regime-switch machinery's real
out-of-sample test).

## D. Behind M5, in this order (same session if room, else next)

The prestations §B leftovers: the **2015 AF-modulation backtest** first
(published costings exist; the knob re-sweep rule demands it), worked-example
goldens second, the 12 remaining UI knobs third.

## E. Boundaries

The **Zucman floor is closed** — reopen only on a published source giving
counts and aggregates above the IFI tranches' ceiling; neither ERFS nor
invention qualifies. CAF cross-check, ERFS, the upstream draft's three
answers: the owner's, untouched. Nothing publishes. Reality beats this
brief, on the record — D-entries as always, and the standing rules in one
breath at the end of `docs/STATE_AND_NEXT.md` all bind.
