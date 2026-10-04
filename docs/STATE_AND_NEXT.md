# State of the project, and the directions open — 2026-10-01 (Phase 8 on `main`)

Supersedes the 2026-09-22 version, which predated D-158 to D-171 and had gone stale
on four counts: it called `make full` red, §6.1 open, the data-dependent tests
unrunnable in CI, and ERFS dormant. For any next session: read this,
`docs/CHARTER.md`, `docs/PHASE8_SPEC.md`, and the review file's last addenda
(`docs/REVIEW_2026-08-29.md`).

## Where the project stands, whole-arc

Seven weeks from the first audit, the tool prices household taxation exactly
(DGFiP-validated; niches, prestations, allègements as knobs), firms
(IS/CVAE/C3S/CEBGE on real DGFiP-Ésane cells), wealth (IFI exact, ISF revival,
backtested out-of-sample against IPP's 2017 tables), taxe foncière from the REI
at commune resolution, behavioural effects as bands on adversarially-verified
evidence, and a macro fan that refuses to be a number.

Phase 8 added the **policy laboratory** on top of that: a debt-dynamics spine
that refuses to draw a path without a named spending scenario, an aggregate
instrument engine for taxes with no population behind them, an auditable
coverage claim over the instrument universe, an objective explorer that hands
back candidates rather than an optimum, and a reindustrialization panel whose
defining feature is what it will not answer.

**Phase 8 is on `main`** since 2026-10-01: merge commit `1e12460` (PR #2), which
carries PR #1's 33 commits and `aa869dd`. Merged rather than squashed, so every
hash cited in this document, in `DECISIONS.md` and in the pass log is reachable
from `main`.

**1 729 tests** where the data is present (the CI `fast` job counts 1 388 passed,
120 skipped, 221 deselected), eleven replayable `verify_*.py` gate scripts, and
**182 decision entries**, D-000 to D-181, recording every error in both
directions.

## Verification, as it stands

* **Last logged full pass: `a9ea26f`, 2026-09-25 — PASS, 1 724 passed, 3 skipped,
  60 min 31 s.** Every line since the red `3101fff` one is green (`f1e5837`,
  `9442046`, `a9ea26f`). `main`'s head is newer: `d8f8076` touched only the two
  pass reports, and `aa869dd` the import guard, `ci_local` and two test files
  (D-171), so no full pass has been logged on `1e12460` itself.
* **CI on `main`, run 36882194476 on `1e12460` — the full suite has still never
  finished on a runner.** `fast` passed (1 388 passed, 120 skipped, 221 deselected,
  11 min 23 s), and so did `perf` and `no-data-committed`. The full `pytest` job
  fetched, built and preflighted cleanly, then ran 73 min of tests until the
  runner received a shutdown signal (16:25:36 UTC), at about 63 % of the suite;
  the job is marked failed. **Up to that point it had printed only passes and
  skips — no test had failed or errored.** It is the second full job to die
  before its summary on a runner: `f1e5837`'s was SIGTERMed (D-160). The cause is
  not established. It is not the concurrency group, since `cancel-in-progress` is
  off on `main`, and not a timeout, since none is set. At the observed rate the
  suite needs about two hours there, against one locally.
* **Automatic CI** — every PR and every push to `main` — runs `fast`, `perf` and
  `no-data-committed`; `fast` also carries the two engine-assumption scripts.
  **The full suite is out of automatic CI since 2026-10-02 (D-172)**, by the
  owner's decision: it runs only when the workflow is dispatched by hand, and
  `make full` is the full verification. `fast` was green on `aa869dd`: 1 388
  passed, 120 skipped, 10 min 57 s.
* **pytest is started two ways.** `make gate` and `make full` run
  `python -m pytest`, which puts the repo root on `sys.path`; CI and
  `make ci-local` run bare `pytest`, which does not. Five tests passed on the
  first route and failed on the second (D-171). The import guard now reports a
  `scripts` package import on either route, and `ci_local` is pinned to the
  workflow's command; the Makefile keeps its route.
* **`make ci-deps`** (≈ 15 s) and **`make ci-local`** replay CI in a throwaway
  worktree with a venv rebuilt from `pyproject.toml` alone (D-165). It is the
  check that `make full` cannot make, because `make full` runs in the owner's
  environment.

## The data chain (D-158 to D-160)

`impots data check | fetch | prepare`, `make data`, and a preflight that stops
`make full` in a second rather than an hour. The `tests` profile is declared
explicitly and checked against the readers' own constants by introspection
(D-160). Fetches go through the production manifest loader, refuse quarantined
entries, and keep a file only if its size **and** digest match.

Two EconStor PDFs are re-stamped by the publisher on every request, so their
entries carry `normalization: pdf-stamp-v1` and are judged on a normalised digest
(D-159); the other 144 keep the raw comparison.

**146 files manifested: 70 sourced, 76 in D-028 quarantine.**

## Phase 8 — milestones

| | | |
|---|---|---|
| M0 | Recon (§1) | done |
| M1 | Debt closure (§3) | **done — closed 2026-09-25**, §6.1 graded (D-167, D-168) |
| M2 | Aggregate engine + produits (§2.2–2.3.1) | **partial, and frozen by instruction** — engine + 9 instruments (D-153); the anchor list verified and corrected (D-166, D-169) |
| M3 | Entreprises + personnes (§2.3.2–3) | **partial** — coverage claim (D-154); CIR and TH/TF gates blocked on files |
| M4 | Objective explorer (§4) | done — D-155 |
| M5 | Reindustrialization panel (§5) | done — D-156 |
| M6 | Consolidation | done — D-157; its « `make full` green, pass logged » item met since `f1e5837` |

**Thirty instruments, sixteen priced — 53 %.** The number that matters is the
other one: **six lines are classified without being priced**, and counting them
would inflate the claim to 73 %. `COVERAGE_INSTRUMENTS.md` renders both, every
figure computed and none typed; nothing has touched it since D-154.

### M1 — §6.1, and what its scope is

* **The SFA is built from its published components**, `F_ASS + ORADJ + K61 + KX +
  YA3` from Eurostat `gov_10dd_edpt3` (`eurostat_gov_10dd_edpt3_fr_sfa.json`,
  manifested). Both dataset codes first announced were wrong: `gov_10dd_sfa` is a
  404 and `gov_10dd_edpt1` has no stock-flow item (D-163).
* **Window 2021→2025, one vintage** (D-167). The notifications carrying 2019–2020
  are on another vintage: the 2019 adjustment changes sign between them.
* **Tolerance ±0.10 pt of GDP, pre-registered at `c6c5db4` before any residual.**
* **Result: five years in the band, largest residual +0.039 pt (2022)** (D-168).
  2025's +0.001 pt is two errors cancelling: an own-year error of −0.031 pt
  against the +0.031 pt carried from 2024. The vintage term, measured apart, is
  +0.031 pt too.
* **Out of scope, stated:** 2019 and 2020, so the +69 md€ Covid adjustment.
  Reopening them needs a current-vintage source that neither Eurostat nor the two
  notifications examined provide.
* **The snowball hinge** (D-170): the 2025 carry factor is 0.9998, so the backtest
  window never left the damping regime that §3 projects beyond. Two tests on
  constructed paths cover both sides of the hinge and the `r = g` limit.

### M2 — the anchors, verified rather than assumed

Of the nine receipts-scaling instruments, **three have a line in the Voies et
moyens tome I**: TSN (line 1430, 785 M€, exécution 2024), TTF (1797, 1 332 M€) and
TGAP (1756, 1 150 M€); TVA nette and the accises énergies are there as aggregates
(D-166). **Six are not, by construction**: taxe sur les salaires and forfait social
go to the Sécurité sociale, taxe d'apprentissage to France compétences, versement
mobilité, DMTO and TASCOM to local authorities.

The CCSS report (`ccss_mai2026_comptes_secu_resultats2025.pdf`) is **sourced**, not
quarantined (D-169, correcting D-166). It gives a usable net series for the forfait
social; the taxe sur les salaires and the tabacs and alcools accises sit in tables
that need a parse. That parse is M2 work, and M2 is frozen by instruction
(D-166, D-169). `docs/M2_ANCHORS.md` carries the corrected table and the revised
download list.

### What Phase 8 refuses, and where each refusal lives

* **A debt path without a named spending scenario** — `dette/path.py`.
* **A distributional output from an aggregate instrument** — `agregats/engine.py`.
* **A banded objective or constraint** — `explorer.py`.
* **A structural-transformation outcome** — `reindustrialisation.py`.
* **A receipts anchor from memory** — `agregats/anchors.py`. The euros live in a
  generated table, never in code.

## Blocked on downloads

| what | for | state |
|---|---|---|
| COICOP consumption split (R5) | TVA per-rate base | not manifested |
| CCTN / DGEC / DGDDI / OFDT volumes | the accises' bases | not manifested |
| **Eurostat `gov_10a_taxag`** | **M5's benchmark** | **not manifested** |
| GECIR / MESR publications | the CIR gate | not manifested |
| DGFiP / DGCL local-tax statements | versement mobilité, DMTO, TASCOM anchors | no candidate in the manifest (D-166) |
| `ccss_mai2026_comptes_secu_resultats2025.pdf` | taxe sur les salaires, tabacs, alcools | **sourced** — needs a table parse, M2 work |
| `rei_2025.zip` | TH RS / TF recon | sourced |

## Owner calls, on the record and not to be chased

* **The reviewer's verdict on Phase 8** is not in the review file, whose last
  addendum is 2026-09-17. Its recommendations reached the work — D-162 cites « A »
  (the PLF dry run first), D-166 cites « D » (the M2 anchor list), D-163 the SFA
  route — but nothing is appended.
* **The §2.4 coverage threshold.** §9 expects it in the decision log; it is in
  neither `M0_PHASE8.md` nor `DECISIONS.md`. Without it there is no universe, so
  `COVERAGE_INSTRUMENTS.md` counts **lines** and says so.
* **Skip versus fail for the data-dependent tests.** No longer a CI blocker: the
  chain fetches and builds what they read before the suite runs. Without the
  files, some still **fail** — `test_accuracy`, `test_top_tail` and
  `test_trajectoires` among them — each naming the command that produces its
  file; the population tests skip. Which
  of the two is right stays the owner's call.
* **`population/calibrate.py`, fenced to Phase 7 (§8).** A margin cell whose
  published target is **zero** is skipped by both `_apply_margin` and `_fit`, so it
  is never measured: a four-household rake with a zero target keeps 2.0 households
  there, converges, and D-150's own guard accepts it (D-157). Whether any published
  target is zero has not been checked.
* **ERFS documentation location** (D-135): left in the delivery with its digests
  recorded, rather than copied under `data/raw/`. Defensible either way; the
  reviewer's to rule.

## Armed and waiting

* **PLF 2027 — published 2026-10-01 (AN text 3210), and the interrupt is running**
  (D-174, D-175, branch `claude/plf2027`). Done in the cloud: the text manifested, the
  splitter fixed (it dropped articles 23, 38 and 47), the 33 fiscal articles triaged —
  **3 priceable**: art. 2 (barème revaluation), art. 3 (pension abatement cap, knob wired
  that day), art. 15 (CEBGE third exercice, through a deliberate prorogation and a new
  firm registry path). **Waiting on the owner's machine**, because INSEE does not answer
  the cloud container: `make full` on the head, then the three registrations, exactly as
  `docs/PLF2027_ENREGISTREMENT.md` writes them, tolerances committed before any figure.
  The annex stays unopened until the registrations are pushed.
* **ERFS 2022 (FPR, lil-1696) — the interrupt ran, E3 is « nothing ».** E0 rails
  (D-134), E1 inventory (D-135), E2 validation table (D-137), and the two
  re-examination gates (D-141) are done. No recalibration is drawn; the E2 table
  goes to the reviewer. A3 is not measured, because it is the one level-sensitive
  axis and its deflation choice must be pre-registered. ERFS bytes and row-derived
  outputs never transit the cloud (addendum 2026-09-17). *The 2026-09-22 version
  of this document called ERFS « dormant »; it was not.*
* **L2, the take-up layer**: dormant. Both DREES non-recours files sit in D-026
  quarantine. Wakes on a sourced, manifested take-up file.

## Directions open — the owner picks

* **Lift M2's freeze**, and the anchors in hand become rows: TSN, TTF and TGAP from
  the Voies et moyens, the forfait social from the CCSS report. Then the CCSS table
  parse for three more, and the local-tax statements for the last three.
* **Finish M3** the day the files land: the CIR verdict and the TH/TF recon.
* **TVA per-rate and the accises' bases**, blocked on COICOP and the volume series.
* **§6.1 beyond 2021**, if a current-vintage source for 2019–2020 appears.
* **F1b's build: the RCM imputation.** Gate cleared; building it is a judgement
  about how much imputed capital income to carry.
* **F7 — succession/DMTG.** Gate only, never past it without the owner.
* **F8 — aggregate VAT.** Still waiting on Budget de Famille 2026 (~2027-28).
* **The CAF cross-check.** 30 minutes at a browser, owner-only. **No reCAPTCHA
  circumvention under any circumstances.**
* **The upstream dossier** and **all publication and deployment**: owner's,
  deferred. The input-hardening pass the reviewer made a precondition is done for
  strings, paths and reform JSON (D-173). What it leaves is the owner's, at deployment
  time: the open CORS policy (it is what lets `ui/index.html` open from disk),
  authentication, rate limiting, and a concurrency cap on `POST /population/simulate`.

## What the next session does if nobody says otherwise

1. **The PLF 2027 is out and its registrations outrank everything** (§8, D-162,
   D-175): if `chiffrages_preregistres/plf2027_art_*.yaml` are committed, find the
   annex link on the AN dossier page, manifest it, and grade (runbook, step 5); if not,
   the owner's step comes first, `docs/PLF2027_ENREGISTREMENT.md`.
2. **Otherwise, nothing new.** M2 is frozen, and the reviewer's verdicts on Phase 8
   and on the ERFS E2 table are pending. Maintenance per `docs/CHARTER.md`: pin
   bumps, vintage refreshes on the nine-source calendar, full passes.

`docs/OPUS_HANDOFF_DATA_CHAIN.md` is a completed brief, kept for its record: its
mission closed with D-159 and D-160.

## Standing, unchanged

ERFS microdata is not redistributable; only aggregates leave it. `data/` is
committed by allowlist only. Do not fabricate the numbers. Calibration inputs via
files only (D-026); a figure from memory is a recollection. Banded or absent,
never confidently wrong. The review file's addenda, all of them, including the
five standing questions and « reality beats every spec, on the record ».
