# State of the project, and the directions open — 2026-10-16 (Phase 9, M2 done)

The sixth 2026-10-16 update adds D-217, Phase 9's M2: every open behavioural row declares
which end of its range θ = 1 designates, θ places each row through its published centre,
a pinned store runs the Phase 3 channels at θ unchanged, and the debt path's behaviour
slice becomes the θ box, read at its corners. No θ has a default — not the endpoint's,
the command's or the page's. The fifth added D-216, Phase 9's M1b: `impots predictif` prices every
year of the horizon on the frozen and the aged population and writes
`reports/predictif_<scenario>.json`, which `GET /predictif` serves; the page gains a
« Et la dette ? » panel whose scenario lists start empty. The fourth added D-215, Phase 9's M1: the chain reform → primary
balance → debt is linked (`predictif/chaine.py`, `dette/reference.py`), the spending rule
finally computes, growth and rate scenarios are named, and `POST /predictif/simulate`
serves the fast version (first projected year priced, later years carried as a share of
GDP, labelled). The third added D-214, Phase 9's reconnaissance (`docs/M0_PHASE9.md`):
Mésange's « Solde primaire des APU » row can carry the GDP → receipts loop, under
`gele_en_volume` only, for the fiscal variants, at one to three years, with the reform's
prices held. The second added D-213: the owner lifts the « no predictive model » rule
in favour of a conditional predictive layer, where every effect is set by a θ in [0, 1]
inside its published range, and `docs/PHASE9_SPEC.md` specifies it. The first added
D-212: with GitHub Actions out of runners and the owner carrying on without it, the
workflow runs on manual dispatch only. The fourth 2026-10-15
update added D-211: at the owner's request, the pension mass is
calibrated on the retirement boxes 1AS-1DS, 374,4 Md€, instead of the 400,4 Md€ of
« pensions et rentes ». The third added D-210: the 400,4 Md€ pension target decomposed box by
box; 26 Md€ of it are not retirement pensions, and without them art. 3 lands 1,8 % above
the annex. The second added D-209, the three candidate sources of the missing pension
foyers, which account for a quarter of art. 3's gap. The first added D-206 to D-208: `grade` refuses a comparator whose sign
contradicts its amount; art. 3's yield lands above the annex because the population's
pension mass sits on too few foyers; and a correction to D-205, whose cache fallback has
not yet run. The 2026-10-14 version it updates added D-204, the owner's full pass and the
three PLF 2027 registrations graded against the annex, and D-205, the CI cache fallback.
The 2026-10-06 version that one updated superseded the 2026-10-05 one, which stopped at
D-194.
D-195 to D-203 added the population skeleton's case T, case 7DG, a lone adult's
situation de famille, the home-help ceiling's increment for members over 65, the
population's case T on N-2 and N-1, the AAH of a pensioner left out of a spouse's ASPA,
alternating residence, adult dependants, and the MVA among a spouse's ASPA resources.
The 2026-10-05 version had superseded the 2026-10-01 one. That one kept its sections on
Phase 8, the CI and the PLF 2027 up to date, but it never described the household
calculator's arc, D-176 to D-194, and it counted 192 entries. It had itself superseded
the 2026-09-22 version, which predated D-158 to D-171. For any next session: read this,
`docs/CHARTER.md`, `docs/PHASE8_SPEC.md`, `docs/PHASE9_SPEC.md`, and the review file's last addenda
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

**Since 2026-10-02 the work has gone to the household calculator** (D-176 to D-203):
what a household can declare, and twenty-one places where this project corrects
openfisca's reading of the law. It has its own section below.

**2 222 tests at the last logged full pass** (`5b1ec10`, 2026-10-14, logged in
`b24de21`): 2 106 passed and 116 skipped, the skips being tests whose source files a fresh
clone's `tests` profile does not fetch (D-204). The CI `fast` job counted 1 781 passed,
120 skipped and 223 deselected on `50932a7` (D-200), and D-201 to D-203 add 98 tests. D-198 to D-203 ran
their own tests only, at the owner's request, and the CI `fast` job ran the suite on each
PR. The project also has fourteen replayable `verify_*.py` gate scripts and **218 decision
entries**, D-000 to D-217, recording every error in both directions.

## The household calculator, D-176 to D-203

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
  complement category and card (D-191); alternating residence (D-201). From 20, a child
  at 80 % or more draws their own AAH, in a famille of their own (D-202).
- **per household:** besides the couple's status and case T, a lone adult's situation de
  famille, célibataire, divorcé ou veuf (D-197). A widowed parent gets the married parts
  and never case T. The persons in case R, card holders living under the roof (D-202).

The page sends every one of them (D-186, then each entry's own page change). Each entry
refuses, with a 422 naming the article, the combinations the engine would price wrong.
The builder also writes what the law derives from them: case 7DG, the home-help credit's
20 000 € ceiling, for a card or an AEEH complement in the household (D-196).

**Twenty-one corrections to openfisca** (`engine.corrections`). Each has a legal citation,
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
| 15 | the home-help ceiling raised for each member over 65 | CGI art. 199 sexdecies, 3 | D-198 |
| 16 | the AAH of a pensioner left out of a spouse's ASPA or ASI | CSS art. R. 815-22 | D-200 |
| 17 | the home-help increment halved for a shared child, not taken off | CGI art. 199 sexdecies, 3 | D-201 |
| 18 | the quotient caps beside a child in alternating residence | CGI art. 197, I, 2 | D-201 |
| 19 | no ASF for a child in alternating residence | CSS art. L. 523-1, I, 3° | D-201 |
| 20 | the first child's ceiling only beside a child | CGI art. 197, I, 2 | D-202 |
| 21 | the AAH's compléments counted as the AAH in a spouse's minimum | CSS art. R. 815-22 | D-203 |

D-193 found openfisca right: case T and the card's half-part stack, each under its own
ceiling. Fourteen tests pin it to the DGFiP's own figures. D-200 settled D-185's couple
question: without a pension, a spouse's AAH counts in the ASPA's resources, and D-185's
couple keeps its 18 943,38 €.

**What the owner has to know.**
- **`to_openfisca.WIRING` is « D-199 ».** Three changes move the population.
  - **D-188.** Correction 6 doubles the abatement for every couple whose two spouses
    are over 65, not only for card holders: on the fixture, 6 of 439 foyers lose
    1 398 € of RFR.
  - **D-195.** The skeleton no longer gives case T to a declarant who lives in a couple.
    On the full EEC, 444 such declarants lose a half-part: +47,1 M€ of income tax,
    weighted, and 10 773 more taxable foyers.
  - **D-199.** The population writes case T on N-2 and N-1 too, where the CSG rate on a
    pension or an unemployment benefit reads the parts: on the fixture, two pensioners'
    disposable income rises, by 839,58 € and 104,64 €. This one needs no rebuild.
  - **The population was rebuilt on 2026-10-14**, on the owner's machine, before the
    full pass and the PLF 2027 registrations (D-204). Nothing keys
    `population_2024.parquet` on the skeleton, so any older checkout still needs
    `impots population build`.
  - Corrections 2 to 5, 8 to 14 and 16 to 21 cannot reach the population: it declares
    no disability, no ASS, no invalidity pension, no alternating residence and no case R.
    Correction 15 reaches it only under a reform: its imputed home-help bases, 3 759,31 €
    at most, stay under the 12 000 € ceiling (D-198).
  - D-203 also pins the housing-aid amount the MVA reads, in the history both paths
    build. The fixture prices the same; a renting couple beside an AAH holder costs about
    5 s more at the full tier.
- **`PENSION_INVALIDITE_MINIMUM`** (correction 10) stops at January 2026. It needs a row
  every January from the Cnav circular, or correction 10 keeps the last amount.
- **Correction 14 rests on CSS art. D. 815-1 as the CNRACL applies it.** No Cnav text
  says how the ASPA is paid beside a spouse at the ASI (D-194).
- **Correction 16 applies the Cnav's list as published** (D-200), an owner's call. The
  first euro of a retirement pension takes an AAH holder's AAH out of the spouse's ASPA
  resources: 29 202,83 € of disposable income with 100 € of pension, 18 943,38 € without.
  Read narrowly, the ministerial letter of 1982 tied the exclusion to the AAH holder
  claiming the allocation supplémentaire.
- **Claiming the ASPA beside an AAH holder** (D-203), an owner's call. The engine never
  claims it (correction 4). From the generation born in 1955 the claim is the household's;
  for D-185's couple it would give about 5 000 € more, and less with a pension. Whether to
  show both figures is a product choice. A holder born before 1955 had to claim, which the
  engine does not model.
- **`aspa`, `ass` and `aeeh` are not in `STATE_TRANSFERS`** (D-186, D-189, D-191). That
  is to decide on a `make full`.
- **D-195's contradictory dwellings**, an owner's call: 89 foyers in a dwelling typed
  « famille monoparentale » whose reference answers « en couple ». Case T stays as it
  was, and a test pins the choice.
- **The upstream dossier** gains the openfisca-france defects these entries correct, the
  widowed parent's case T (D-193, D-197), the NaN tax of a `jeune_veuf` (D-197), the
  home-help increment of a case R dependant (D-198), and the RSA's at-charge test beside a
  child's AAH and the housing aid's strict 80 % (D-202).

## Verification, as it stands

* **Last logged full pass: `5b1ec10`, 2026-10-14 — PASS, 2 106 passed, 116 skipped,
  107 min 39 s**, on the owner's machine in a fresh clone (D-204). The 116 skips are
  data-absent skips: `make data` fetches the `tests` profile only. The previous line,
  `a9ea26f` on 2026-09-25, had 3 skips on a machine holding every manifested file.
  Every line since the red `3101fff` one is green.
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
* **GitHub Actions has been unavailable since 2026-10-15, 13:56 UTC** — no job gets a
  runner, the shape of an exhausted minutes quota (D-161) — and the owner decided to
  carry on without it (D-211). Until that changes, nothing below runs on its own: a PR
  is verified by its own targeted tests and by the owner's `make full`, which is now the
  only whole-suite check. Since 2026-10-16 the workflow runs on manual dispatch only
  (D-212), so a push no longer leaves a red cross that checked nothing; the comment
  under `on:` in `.github/workflows/test.yml` says how to restore the two triggers.
* **Automatic CI**, when restored — every PR and every push to `main` — runs `fast`,
  `perf` and `no-data-committed`; `fast` also carries the two engine-assumption scripts.
  **The full suite is out of automatic CI since 2026-10-02 (D-172)**, by the
  owner's decision: it runs only when the workflow is dispatched by hand, and
  `make full` is the full verification. `fast` was green on `aa869dd`: 1 388
  passed, 120 skipped, 10 min 57 s.
* **The raw-sources cache falls back on the previous one** when the manifest changes
  (D-205), so a PR that adds an entry outside the `tests` profile no longer contacts
  any source server. A restored file is kept only if it matches the manifest, and
  `donnees.elaguer_cache` drops what the manifest no longer sources. The first PR after
  it found no cache at all (D-208); the fallback first ran on D-209's PR, restoring the
  previous key and downloading nothing (D-210).
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

* **PLF 2027 — registered and graded (D-204).** Published 2026-10-01 (AN text 3210);
  the 33 fiscal articles triaged, 3 priceable (D-174, D-175). On 2026-10-14 the owner
  ran the full pass and the three registrations, one commit each (`be5b5f6`,
  `e449490`, `25b2a61`). The annex was then manifested and the cases graded: **art. 3
  within (−17,7 %), art. 15 within (−28,3 %), art. 2 outside (−30,3 % against 20 %)**.
  Art. 2's published figure is a first-year budget effect (2027 notices plus PAS),
  against our one income year; art. 15's grade rests on counting the 0,5 Md€ of shifted
  closings in 2028. Both are written up in D-204, with what remains. Since 2026-10-15
  `grade` refuses a comparator whose sign contradicts its amount (D-206). Art. 3 lands
  17,7 % above the annex although its tolerance declared only downward biases: the
  population puts the 400,4 Md€ of declared pensions on 12,24 M foyers, against 15,09 M
  beneficiaries of the 10 % abatement in the Voies et moyens, and the whole abatement
  costs 11 % too much against that independent line (D-207,
  `scripts/verify_pensions_art3.py`). The three leads D-207 named — retirees in
  institutions, the age rule for pensions, cohabiting couples in one foyer — are
  measured in D-209 (`scripts/verify_pensions_foyers.py`): together they bring the
  pension foyers to 12,83 M and take 3,7 % off what art. 3 removes, a quarter of the gap.
  The rest is the level (D-210, `scripts/verify_pensions_masse.py`): the target mixes
  374,4 Md€ of retirement pensions (boxes 1AS-1DS) with 26 Md€ of invalidity, alimony,
  foreign pensions, capital and annuities, all drawn onto retirees. Scaled to the
  retirement boxes, art. 3 lands at 1,119 Md€, +1,8 %. Since D-211 the population is
  calibrated on those boxes: on a 20 000-household sample the IR barème line moves from
  +11,0 % to +6,7 % of the DGFiP, and foyers imposés from −1,6 % to −4,5 %. The
  registered chiffrages keep their commit and their grades.
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
  - claiming the ASPA beside an AAH holder: both figures, and the claim owed by a holder
    born before 1955 (D-203);
  - `aspa`, `ass` and `aeeh` in `STATE_TRANSFERS`, on a `make full`;
  - a rented dwelling beside a child at the AAH or a person in case R, refused for now;
    a case R person's own incomes; a child of 20 or more at 50 to 79 % (D-202);
  - alternating residence's benefit side: the allocataire, the housing aid and the RSA
    (D-201);
  - case 7DG for a third-category invalidity pensioner without the card, whose category
    the format does not carry (D-196);
  - case L, for a parent who raised a now-adult child alone for five years, and the year
    of the death (D-197);
  - the N-3 RFR, which also keeps the 3.8 % CSG rate (CSS art. L. 136-8, III, 2°) and
    openfisca does not read (D-199);
  - the population's widowed parent, who keeps case T because the population carries no
    situation de famille (D-195).
* **The upstream dossier** and **all publication and deployment**: owner's,
  deferred. The input-hardening pass the reviewer made a precondition is done for
  strings, paths and reform JSON (D-173). What it leaves is the owner's, at deployment
  time: the open CORS policy (it is what lets `ui/index.html` open from disk),
  authentication, rate limiting, and a concurrency cap on `POST /population/simulate`.

## What the next session does if nobody says otherwise

1. **The PLF 2027 is graded** (D-204), the sign guard is in (D-206), art. 3's direction
   is explained (D-207), its candidate causes measured (D-209), the pension target
   decomposed (D-210) and the population recalibrated on the retirement boxes (D-211).
   What it leaves: a full pass and the reports regenerated on the owner's machine, the
   first since the pension target moved and, with Actions down, the only whole-suite
   check D-210 and D-211 will get; the report's direction line, which counts
   signs; and art. 2's outside grade.
2. **Phase 9, M3** (`docs/PHASE9_SPEC.md` §4): the GDP → receipts loop from Mésange's
   primary-balance row, under `gele_en_volume` only, which also wires the multiplier's
   θ (`predictif/macro.py`, defined in M2 and not yet read by the debt path). M1, M1b and
   M2 are done (D-215 to D-217). A full ten-year `impots predictif` run is about an hour
   on the owner's machine, and now takes `--theta`. Still open from M0: the HCFP note (its host
   refuses this container), the IZA DP 6735 to manifest, France Stratégie's 2023
   capital-taxation report to read, and the AFT outstanding, which www.aft.gouv.fr
   refuses here too (403): the `marche` rate scenario needs it.
3. **Otherwise, nothing new.** M2 is frozen, and the reviewer's verdicts on Phase 8
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
