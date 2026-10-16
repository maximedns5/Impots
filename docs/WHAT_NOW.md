# What we can do now

**Status: re-triaged 2026-09-09, after Phase 6 closed.** The four-layer
architecture was completed 2026-09-03; since then the project has added the
reform composer and its budget-neutral solver, the fiche de chiffrage
generator, the pre-registration harness, the PLF coverage triage, multi-year
trajectories on uprated populations, the EMTR explorer, taxe foncière at
commune resolution, and a maintenance charter that is itself under test. CI
green, **1 315 tests**, every guard carrying its kill test.

This document is the full menu of what is possible from here — every option,
its cost, what it needs, and a recommended sequence at the end. **It is a
menu, not a plan: the owner picks.** For what the project IS today rather
than what it could do next, read `docs/STATE_AND_NEXT.md`; for the steady
state, `docs/CHARTER.md`.

---

## A. Armed and waiting — will fire on an external event

**A1 · The migration to real income microdata (Phase 1C).** Loaded since
D-016, acceptance test ready (the barème-indexation backtest). **Not
scheduled — ERFS access is unavailable for the foreseeable future (D-096),
so this is a plan on the shelf rather than work in a queue.** If real income
microdata ever arrives: real incomes
replace the synthetic ones, which fixes the three failing benefit lines (RSA
+106 %, AL, AF), collapses the D-015 density error the cliffs backtest
measured at +107 %, moves the wage bill from calibration to validation
(making the IR line a real test at last), makes the top tail publishable, and
— the sleeper — introduces **capital income**, which wakes the PFU/dividend
channel: the best-identified behavioural elasticity in the French literature
(3.0, IPP), currently structurally impossible. Interrupt rule: outranks
everything, at any milestone. *Cost: ~2–4 sessions when it lands. Nothing to
do today except not forget it.*

**A2 · Indirect taxes (TVA, accises, carbone).** Blocked on Budget de Famille
2026 microdata, expected ~2027–28. Nothing honest can be built before then;
this stays on the shelf by design.

## B. Model improvements possible today — no new data needed

**B1 · Benefits/prestations knobs.** **DONE (2026-09-03, D-062).** The RSA,
prime d'activité, AF and AL parameters are already in openfisca-france; the
population already computes them. Adding a prestations knob set (barème RSA,
taper rates, AF modulation, AL parameters) does three things at once: covers
the *other half* of French fiscal debate (the tool currently reforms taxes
but not transfers), constitutes a **spending instrument** — which wakes
`multiplier_regime_shift`, currently loaded and unusable — and exercises C1's
participation-tax-rate machinery where France's EMTRs actually peak (the
63.5 % top-EMTR households the fan already found). Same recipe as the
allègements knobs: verified paths, read-back, kill tests, chiffrage re-sweep.
*Done: the knob set shipped with two double-entry leaks the balance guard
caught. The spending instrument it unlocked is live, and the EMTR machinery it
exercised became F6's explorer (S5).*

**B2 · The CAF cross-check.** **PREPARED, NOT RUN (2026-09-03, D-070).**
`tests/golden/CROSSCHECK_CAF.md` carries three households covering AF, PPA, RSA
and AL, with our figures computed and the estimator's column blank. It needs a
browser and Max: the CAF estimator sits behind reCAPTCHA, and D-019's rule —
do not fabricate the numbers — holds. **Read the file's warning first**: 
mesdroitssociaux.gouv.fr, mes-aides.org and ESTIME are all powered by OpenFisca,
so checking against them compares our engine with itself and would pass
perfectly while proving nothing. *Cost: an hour with the CAF's own tool.*

**B3 · IR niches — réductions and crédits d'impôt.** **DONE (2026-09-03,
D-064 to D-069).** The household calculator now prices the five biggest niches
exactly — seven declaration cases as wire-format fields, thirteen knobs on
their rates and ceilings, every rate measured rather than tabulated — and the
Voies et Moyens costs are sourced per numbered dispositif (11.6 bn of 19.53 bn,
about 59 %). The imputation is done too (D-068): bases drawn from the DGFiP decile
table move the IR-net line from **+22.5 % to +10.4 %**. It is opt-in and off by
default because it is a CALIBRATION — the niche totals then match DGFiP by
construction and that source is spent. Four things fell out worth knowing: the
Voies et Moyens columns are BUDGETARY years (D-067); openfisca applies no
eligibility test to these cases at all (D-065); there is a phantom parameter
tree for the home-help credit whose values match the live one exactly (D-064);
and the barème reconciliation line was reading the NET figure, hidden for as
long as every niche was zero (D-069). *Still open: the global cap cannot be
priced even with imputation — a decile-mean draw has no tail — and about 45 %
of the niches remain unmodelled.*

**B4 · Capital-income knobs, mechanical only.** **DONE, and its gate has run
(F1b / Phase 6 S3, `docs/F1B_CAPITAL_GATE.md`).** PFU rate and base are
ReformSpec knobs, banner-limited ("population carries no capital income until
ERFS"), so the *household calculator* prices them exactly though the population
cannot. **What remains is an owner decision, not a task**: the gate cleared the
RCM imputation, and whether to build it is a judgement about how much imputed
capital income this project wants to carry.

**B5 · Population vintage refresh.** **DONE as mechanical uprating (F3 M2,
`src/impots/uprating.py`)** — and the milestone's real product was the cost:
an uprated population is **no longer calibrated**, so `reporting.Line` now
refuses a tolerance verdict when the population year and the comparator year
differ. Structure, ages and weights do not move; a trajectory is «this law, on
today's France, with tomorrow's money». The recurring half is in
`docs/CHARTER.md` §3.

**B6 · Open diagnostics, if still open.** The industrie/immobilier
perimeter check (profiled-enterprise vs legal-unit classification — the
opposite-signs signature) if the red lines still lack a mechanical verdict.

## C. Reach — code, method, and product (owner decisions)

**C1 · Make the repository public.** Separate from deploying the service, and
much cheaper: the code is AGPL already, the data guard keeps ERFS out
mechanically, the decision log and review file are — frankly — the most
instructive part of the project. A public repo satisfies the "open" mission
with zero hosting, invites the OpenFisca/LexImpact/IPP world in, and costs a
README pass plus one honest look for anything personal in the history.
*Recommended before any deployment.*

**C2 · The public methods page.** The reconciliation reports, the calibration
ledger rule, the accuracy-ceiling framing, and the receipts (three chiffrage
cases dead on the official record's own verifiability — the Cour des comptes'
2024 critique, now with evidence). This can exist before and independent of
any deployed simulator, and it is what makes the eventual deployment credible
rather than just available. *Cost: a writing session; most of it exists in
docs/.*

**C3 · Deployment (parked, owner's call).** The staged option remains the
recommended shape whenever reopened: household calculator public first
(validated, caveat-free), population/firm/macro tabs behind beta banners with
the deltas-only and refusal rules they already enforce. Needs: small host,
quick-tier limits, AGPL §13 link — the repo being public (C1) makes this a
formality. *Cheapest with real income microdata; possible any time, and since D-096 there is no reason to wait for it.*

**C4 · Upstream and allies.** D-018's posture was "offer when substantial".
The firm package now carries verified IS/CVAE/C3S/CEBGE parameters — that is
substantial. Offer it to the OpenFisca org; show LexImpact the chiffrage
suite; show IPP the parameter store with verifier verdicts. Worst case:
silence. Best case: users, correction, legitimacy. *Cost: two emails and a
README. Requires C1 in practice.*

**C5 · Write it up.** Two publishable stories, distinct audiences: the
*methodology* (adversarial verification of legislation-as-code and
parameters: guards with kill tests, D-042's self-confirming read-back, the
inventory rule — International Journal of Microsimulation material, or a
strong technical blog series), and the *tool* (an open, layered,
honesty-first French tax simulator — French policy/tech audience). The
Berkeley affiliation makes the first genuinely placeable. *Cost: real, but
the decision log has already written most of the first draft.*

**C6 · Use the tool — dogfood the live debates.** Price the 2026 allègements
refonte, a barème indexation freeze (the classic stealth tax rise), CSG
progressivity proposals — each analysis is simultaneously a product demo, a
stress test, and content for C2/C5. The tool exists to answer exactly these.
*Cost: per analysis, an evening. This is also just… the point of the project.*

## D. Sustainability

**D1 · Full-pass log discipline.** **DONE**, and the target itself had to be
fixed: it read `$?` after a pipe and could only ever report PASS. Verified to
fail in both directions since.

**D2 · The maintenance charter.** The steady-state rules the project now
needs more than features: the openfisca pin-bump ritual (monthly, deliberate,
with the golden re-anchor procedure and a D-entry per bump), the annual
loi-de-finances cycle (new barèmes arrive via the bump; new chiffrage cases
per LF article; vintage refreshes for Filosofi/Ésane/TES; B5's population
uprating), and the review cadence. One page, written once, followed
thereafter. **DONE — `docs/CHARTER.md` (D-112), and it is tested**: eight tests
assert the repository it describes still exists, because a charter that
describes a repository that no longer exists is worse than none — it will be
followed.

**D3 · A bigger runner for full-N work.** The 8 GB machine OOM-killed the
full-population comparison once already; the cloud container has the
headroom and the offer stands.

## What we cannot do, so it is never half-done by accident

Indirect taxes before BDF 2026 microdata. Capital-income behaviour before
ERFS. Pensions/dynamics (EIC/EIR is CASD-gated). CGE/DSGE/HANK/ABM — the
kill list from the first audit stands. Unconditional forecasting — never.
Since D-213 (2026-10-16) a CONDITIONAL predictive layer is specified in
`docs/PHASE9_SPEC.md`: every effect set by a θ in [0, 1] inside its published
range, every result read « if θ = … », a channel with no published range closed.

---

## Recommended sequence

With ERFS able to interrupt at any point: ~~**B1**~~ (done 2026-09-03) →
~~**B3** first half~~ (done 2026-09-03) → **B2** (CAF cross-check, an hour,
needs Max at a browser) → **C1 + C2** (public repo + methods page — the
mission, at zero hosting cost) → **C6** (two or three live-debate analyses,
which becomes the material for **C4/C5**) → real income microdata if it ever becomes available (D-096) → reopen
**C3** (deployment) with the migrated population. B3's imputation and **B4**
slot in wherever a session has appetite; D2 gets written the first quiet week.
