# State of the project, and what is left — 2026-09-08

For the next implementing session: read this, then `docs/ROADMAP_NEXT.md` for
the queue, then the last two addenda of `docs/REVIEW_2026-08-29.md` for the
rules. This file supersedes the sequence in WHAT_NOW for "what happens next".

## Where we are

Every phase of the original architecture is built, guarded and on CI:
mechanical engine (DGFiP-validated to the euro), calibrated population
(person-weighted distribution lines inside tolerance after the D-073 sweep;
PPS sampler corrected, D-074), behavioural bands (verified store, one live +
newly-woken channels), macro fan (refusals enforced by tests), firm module
(all instruments inside tolerance on real cells), allègements + prestations +
niches knobs, niche imputation (opt-in, spent-registered), narrow-band and
double-entry guards, full-pass log discipline. Verification culture: six
reviewer errors, multiple implementer errors, **seven upstream artefacts** and
now one of our own guards caught by the machinery — the standing rules in the
review file are project law.

**Phase 5 (patrimoine) is complete**, M0 through M5 plus the ISF-2017
backtest: IFI cells from DGFiP n° 33/n° 45 by barème inversion, household IFI
in the calculator, the ISF-1989 regime switch, three named legal corrections
each with citation + decision + kill test, cell-bound placement (the open top
cell REFUSES an invented ceiling), a flat-and-says-so composition band, the
wealth-rate and disclosure dials, and an out-of-sample backtest against IPP
Rapport n° 46 whose +19,7 % on the non-capped group is pinned OUTSIDE
tolerance rather than swallowed by widening it (D-079 … D-091).

**F2 (reform composer) is complete** — D-092. Named scenarios with mandatory
provenance, saved as JSON and never overwritten; A/B comparison that
differences the mechanical layer and only that; a budget-neutral solver that
root-finds one scalar knob against the mechanical cost and **refuses every
banded quantity**, refuses a non-scalar knob, and does not present a
non-converged iterate as an answer. CLI (`impots scenario …`), read-only HTTP
(`GET /scenarios`), and a UI picker driven by a single knob table from which
sending, resetting and loading are all derived.

**F2's first real solve found a bug in one of our guards** — D-093. The
double-entry identity scaled its residual by the reform's NET, which the
solver drives to zero on purpose; a fixed 305 000 EUR leakage was being
divided by nothing. Fixed with a second, tighter allowance against the GROSS
movement.

**And an adversarial review then found two bugs in that fix** — D-094. The
gross summed the BUCKETS before taking absolute values, so it collapsed for a
reform whose arms share a bucket (the shape it was written for); and the firm
guard bought indulgence with movement it cannot see, so it now carries its own
constant, 300x tighter, measured on its own side. Nine confirmed findings in
all, each re-verified by hand; the review also found a denylist where an
allowlist was needed, a `load()` that 500'd a whole listing on one bad file, a
scenario name interpolated into a path, and a refusal test parametrized over
the dict it was testing.

## Next, and the deadline is real

**F1 — the PLF 2027, priced the week it publishes**, with dated,
pre-registered, committed chiffrages. Early October. F2 exists for this.

**Both preparation pieces are done — D-095.** `docs/PLF2027_COVERAGE.md` is
the coverage triage, built on the PLF 2026's real article structure and
verified by tests rather than asserted; `src/impots/chiffrages.py` is the
grading harness, with the three questions answered at birth and a red-light
test that must pass before any real case enters. Publication week is now
execution: read the articles, map to categories, register, commit.

**The headline is 1 of 29 fiscal articles — 3.4 %.** Three more have their
parameters in the tree but no taxpayer in this population to exercise them,
so wiring them would publish a confident zero. Twenty-three are outside the
model's structure or its data. That number is a pre-registered limitation
because it was decided in September; decided in October it would have been
an excuse.

**F1b's gate is run and its verdict is written — D-097.** An RCM imputation
from published DGFiP fractiles is feasible and honest for the PFU (a
proportional tax's yield depends only on each cell's total, which is
published down to the top millime) and unusable for the CDHR (a ratio-defined
measure needs within-cell dispersion no fractile table contains, at any
fineness). The generalisation is the reusable part: any measure defined on a
threshold, a ratio or an individual average rate is out of reach of a
fractile imputation. Nothing is built past the gate; building the imputation
is the owner's call.

**F4 is done — D-098.** `impots fiche <scenario>` assembles the whole honesty
stack into one exportable document shaped on the real évaluation préalable
skeleton. Rendering it against live responses found three defects that reading
the code had not: a channel band indexed as a pair, channels hidden whenever
the overall band was withheld (an employer reform computes +17 113 jobs
[15 056 ; 19 093] and the reader saw «no band» and nothing else), and French
typography eating the prose commas.

**F3 is gated, not built — D-099.** The M0 gate overturned the roadmap's
premise: the dated tree encodes the future on two parameters out of
sixty-two. A barème freeze priced against an already-frozen baseline returns
zero by construction, so F3's first deliverable is a second indexed
counterfactual, not a knob. `docs/F3_SPEC.md` is written against what was
measured. The gate also found the firm engine dying at 2029 on a YAML value
parsed as a string — one year, in the middle of the range a trajectory phase
sweeps, unseen because nobody had run 2029.

**F5 is gated — D-100.** `docs/M0_REI.md`: the foncier bâti reads to +0,9 %
against the published 43,1 Md€ (the headline 55,1 Md€ is the wrong
comparator), the non bâti misses 60 % and is pinned as failing, and the
column map is recorded — the REI never says «foncier», it says FB and FNB.
One limit the roadmap did not anticipate: the REI is COMMUNAL and this
population has no commune, so F5 delivers a per-commune model, not
per-household incidence.

**F3 M1 is built — D-101.** Two references, neither defaulted: `reconduit`
(current law extended, the legal one) and `indexe` (barème, décote and
plafond QF uprated on a DECLARED price hypothesis — supplied, never
forecast). Measured end to end: the 2028 barème freeze costs +0,000 md
against `reconduit` and −7,073 md against `indexe` at 2 %/yr. Both true,
different questions, and the stealth tax exists as a number only because the
second reference does. M2 (population uprating) is next and every result says
the population is not yet aged.

Two standing decisions for the owner, recorded and not taken:
pre-registration integrity is internal-grade (a commit hash in a private
repo). If external credibility ever matters, a timestamp OUTSIDE the repo is
needed at registration time — a public commit, a published hash. And whether
to build the RCM imputation F1b cleared: the cost is one increment, the price
is two more totals spent on the calibration ledger and one more income
category whose within-cell distribution is a declared fiction.
Everything else in `docs/ROADMAP_NEXT.md` (F4 fiche de chiffrage, F3
trajectories, F5 taxe foncière, F6 EMTR explorer, F7 DMTG gate) comes after.

Session-A leftovers still open, small: the 2015 AF-modulation backtest, the
worked-example goldens (RSA base, PPA taper showing the EMTR shift), and the
UI knob count at 31 exposed of 52 defined.

## Standing items that are NOT the session's

* **CAF cross-check**: prepared, not done, D-070 — needs Max at a browser;
  reCAPTCHA is never worked around.
* **Real income microdata (ERFS)**: NOT AVAILABLE for the foreseeable
  future (D-096). The interrupt rule is dormant, not dead — if the data ever
  arrives, Phase 1C and its acceptance test fire exactly as written; acceptance
  test is the barème-indexation backtest.
* **Upstream issue draft** and all of WHAT_NOW section C (publication,
  deployment, public repo): deferred by the owner; nothing posts.

## Backlog (owner picks, do not start unbidden)

Niche coverage beyond ~55 %; the global-cap blind spot (waits for real bases
— do not fix with invented dispersion); the maintenance charter (pin-bump
ritual, annual LF cycle) — worth writing the first quiet week, which exists
again once F1's pre-registrations are in.

## Rules in force

The review file's addenda, in full. In one breath: verify before building;
files, not agent prose; mechanical before economic; codes, not labels;
update() never creates; guards ship with kill tests and every check names
the implementation that would make it fail; comparisons are untested until
both sides have been non-zero; comparator vintage and perimeter stated
always; banded or absent, never confidently wrong; and reality beats every
spec, on the record.

Two added the same day. From D-093, a question to ask of every guard: **can
this check's denominator go to zero?** A guard whose tolerance is relative to
a quantity the tool can drive to zero is green until someone drives it there.
From D-095, a fourth, earned twice in one session: **what is this number the
difference of, exactly?** Both false alarms that day — a "dead" `taux_cdhr`
and a "dead" `cvae_taux_max` — were the same mistake, comparing a thing with
itself: once a memoised tree against itself, once `totals` where
`totals_reform` was meant. From D-094, the one that follows D-093: **did I test the fix on a shape other
than the one that alerted me?** Two of that day's nine confirmed findings were
in the fix written hours earlier — a correction does not inherit the vigilance
that motivated it. And a third, from the same day: **have I ever seen this
check fail?** `make full` read `tail`'s exit status instead of pytest's, so
the full-pass log — "the only record that the full suite is green" — could
only ever write PASS. A check with one possible verdict has never checked
anything, and the rule this project applies to its model guards had never been
applied to its own tooling.
