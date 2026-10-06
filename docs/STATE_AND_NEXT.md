# State of the project, and the directions open — 2026-10-06 (Phase 8 and the household calculator on `main`)

Supersedes the 2026-10-05 version, which stopped at D-194. D-195 to D-197 added the
population skeleton's case T, case 7DG and a lone adult's situation de famille. The
2026-10-05 version had superseded the 2026-10-01 one. That one kept its sections on
Phase 8, the CI and the PLF 2027 up to date, but it never described the household
calculator's arc, D-176 to D-194, and it counted 192 entries. It had itself superseded
the 2026-09-22 version, which predated D-158 to D-171. For any next session: read
this, `docs/CHARTER.md`, `docs/PHASE8_SPEC.md`, and the review file's last addenda
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

**Since 2026-10-02 the work has gone to the household calculator** (D-176 to D-197):
what a household can declare, and fourteen places where this project corrects
openfisca's reading of the law. It has its own section below.

**1 729 tests at the last logged full pass** (`a9ea26f`, 2026-09-25), before the
household arc added its own. The CI `fast` job counted 1 696 passed, 120 skipped and
223 deselected on `4f19e36` (D-194), and D-195 to D-197 add 53 tests. The project also
has eleven replayable `verify_*.py` gate scripts and **198 decision entries**, D-000 to
D-197, recording every error in both directions.

## The household calculator, D-176 to D-197

**What a household can declare** (`api/schemas.py`):
- **per adult:**
  - the gross salary and the birth year;
  - the declared retirement pension (box 1AS, D-175, D-176);
  - the gross unemployment benefit (D-183);
  - a CDAPH incapacity rate and the RSDAE (D-184);
  - the invalidity card (D-188);
  - « fin de droits » for the ASS (D-189);
  - the declared invalidity pension (box 1AZ, D-190).
- **per child:** the birth year, and a disability: rate, establishment or care, AEEH
  complement category and card (D-191).
- **per household:** besides the couple's status and case T, a lone adult's situation de
  famille, célibataire, divorcé ou veuf (D-197). A widowed parent gets the married parts
  and never case T.

The page sends every one of them (D-186, then each entry's own page change). Each entry
refuses, with a 422 naming the article, the combinations the engine would price wrong.
The builder also writes what the law derives from them: case 7DG, the home-help credit's
20 000 € ceiling, for a card or an AEEH complement in the household (D-196).

**Fourteen corrections to openfisca** (`engine.corrections`). Each has a legal citation,
a measured defect, and a kill test that fails the day openfisca changes its mind.

| # | What | Law | Entry |
|---|---|---|---|
| 1 | the minimum deduction may not eat a pension | CGI art. 83, 3° | D-180 |
| 2 | the MVA goes to a full AAH, or to one beside a pension | CSS art. L. 821-1-2 | D-184 |
| 3 | the age of 62 for AAH holders | CSS art. L. 821-2 and L. 351-1-5 | D-185 |
| 4 | the AAH without the ASPA | CSS art. L. 821-1 | D-185 |
| 5 | the high-rent taper spares an AAH beneficiary | CCH art. D. 823-16 | D-187 |
| 6 | the art. 157 bis abatement doubled for a couple | CGI art. 157 bis | D-188 |
| 7 | the same abatement in the benefits' resources | CCH art. R. 822-4 | D-188 |
| 8 | the ASS counts the spouse's unemployment benefit | C. trav. art. R. 5423-2 | D-189 |
| 9 | the invalidity pension bears a pension's levies | CSS art. L. 136-8 and L. 137-41 | D-190 |
| 10 | the ASI of a lone beneficiary in a couple | CSS art. D. 815-19, 2° b | D-190 |
| 11 | each AEEH complement at its own category's rate | CSS art. D. 541-2 | D-191 |
| 12 | the ASS taxed as a salary | C. trav. art. L. 5428-1 | D-192 |
| 13 | the ASI beside a spouse at the ASPA | CSS art. D. 815-19, 2° c | D-194 |
| 14 | the ASPA beside a spouse at the ASI | CSS art. D. 815-1 | D-194 |

D-193 found openfisca right: case T and the card's half-part stack, each under its own
ceiling. Fourteen tests pin it to the DGFiP's own figures.

**What the owner has to know.**
- **`to_openfisca.WIRING` is « D-195 ».** Two changes move the population.
  - **D-188.** Correction 6 doubles the abatement for every couple whose two spouses
    are over 65, not only for card holders: on the fixture, 6 of 439 foyers lose
    1 398 € of RFR.
  - **D-195.** The skeleton no longer gives case T to a declarant who lives in a couple.
    On the full EEC, 444 such declarants lose a half-part: +47,1 M€ of income tax,
    weighted, and 10 773 more taxable foyers.
  - **The population must be rebuilt first.** Nothing keys `population_2024.parquet` on
    the skeleton: `impots population build`, then `make full`. Step 0 of
    `docs/PLF2027_ENREGISTREMENT.md` does it, and the PLF 2027 registrations price what
    that run builds.
  - Corrections 2 to 5 and 8 to 14 cannot reach the population: it declares no
    disability, no ASS and no invalidity pension.
- **`PENSION_INVALIDITE_MINIMUM`** (correction 10) stops at January 2026. It needs a row
  every January from the Cnav circular, or correction 10 keeps the last amount.
- **Correction 14 rests on CSS art. D. 815-1 as the CNRACL applies it.** No Cnav text
  says how the ASPA is paid beside a spouse at the ASI (D-194).
- **`aspa`, `ass` and `aeeh` are not in `STATE_TRANSFERS`** (D-186, D-189, D-191). That
  is to decide on a `make full`.
- **D-195's contradictory dwellings**, an owner's call: 89 foyers in a dwelling typed
  « famille monoparentale » whose reference answers « en couple ». Case T stays as it
  was, and a test pins the choice.
- **The upstream dossier** gains the openfisca-france defects these entries correct, the
  widowed parent's case T (D-193, D-197), and the NaN tax of a `jeune_veuf` (D-197).

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
  (D-174, D-175; prepared on `claude/plf2027`, merged into `main` by #9). Done in the
  cloud: the text manifested, the
  splitter fixed (it dropped articles 23, 38 and 47), the 33 fiscal articles triaged —
  **3 priceable**: art. 2 (barème revaluation), art. 3 (pension abatement cap, knob wired
  that day), art. 15 (CEBGE third exercice, through a deliberate prorogation and a new
  firm registry path). **Waiting on the owner's machine**, because INSEE does not answer
  the cloud container: `make full` on `main`'s head, then the three registrations, exactly as
  `docs/PLF2027_ENREGISTREMENT.md` writes them, tolerances committed before any figure.
  The annex stays unopened until the registrations are pushed. That `make full` builds
  the population at `WIRING` « D-195 », after step 0 rebuilds it, so the registrations
  price the corrected law (D-188, D-195); the runbook accepts every entry from D-176 on.
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
* **The household calculator's open items**, each in its entry's « Ce qui reste »:
  - the D-185 couple question, to settle in law;
  - `aspa`, `ass` and `aeeh` in `STATE_TRANSFERS`, on a `make full`;
  - disabled children of 20 or more (their AAH, and the card's half-part of an adult
    dependant);
  - alternating residence, and its quarter parts;
  - case 7DG for a third-category invalidity pensioner without the card, whose category
    the format does not carry (D-196);
  - case L, for a parent who raised a now-adult child alone for five years, and the year
    of the death (D-197);
  - the population's case T on N-2 and N-1, which the household builder writes and the
    population wiring does not (D-195);
  - the population's widowed parent, who keeps case T because the population carries no
    situation de famille (D-195).
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
   bumps, vintage refreshes on the nine-source calendar, full passes, and each
   January a row in `engine.corrections.PENSION_INVALIDITE_MINIMUM` (D-190).

`docs/OPUS_HANDOFF_DATA_CHAIN.md` is a completed brief, kept for its record: its
mission closed with D-159 and D-160.

## Standing, unchanged

ERFS microdata is not redistributable; only aggregates leave it. `data/` is
committed by allowlist only. Do not fabricate the numbers. Calibration inputs via
files only (D-026); a figure from memory is a recollection. Banded or absent,
never confidently wrong. The review file's addenda, all of them, including the
five standing questions and « reality beats every spec, on the record ».
