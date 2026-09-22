# State of the project, and the directions open — 2026-09-22 (post-Phase 8)

Supersedes the 2026-09-13 post-Phase-7 version. For any next session: read
this, `docs/CHARTER.md`, `docs/PHASE8_SPEC.md`, and the review file's last
addenda.

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

**1 596 tests**, eleven replayable `verify_*.py` gate scripts, and **157 decision
entries** recording every error in both directions.

## Phase 8 — the policy laboratory, closed 2026-09-22

| | | |
|---|---|---|
| M0 | Recon (§1) | done, pre-branch |
| M1 | Debt closure (§3) | done — `dette/`, spending-scenario refusal kill-tested |
| M2 | Aggregate engine + produits (§2.2–2.3.1) | **partial** — engine + 9 instruments (D-153); TVA and the four accises blocked on downloads |
| M3 | Entreprises + personnes (§2.3.2–3) | **partial** — coverage claim (D-154); CIR and TH/TF gates blocked on files |
| M4 | Objective explorer (§4) | done — D-155, worked example rendered |
| M5 | Reindustrialization panel (§5) | done — D-156 |
| M6 | Consolidation | this document, D-157 |

**Thirty instruments, sixteen priced — 53 %.** The number that matters is the
other one: **six lines are classified without being priced**, and counting them
would inflate the claim to 73 %. `COVERAGE_INSTRUMENTS.md` renders both, every
figure computed and none typed.

### What Phase 8 refuses, and where each refusal lives

* **A debt path without a named spending scenario** — `dette/path.py`. The
  spending choice moves the trajectory more than the tax package being explored;
  a chart that leaves it unstated implies tax carries the adjustment alone.
* **A distributional output from an aggregate instrument** —
  `agregats/engine.py`. No population behind the number; a decile table split
  off a national total is indistinguishable from a real one.
* **A banded objective or constraint** — `explorer.py`. Optimising *on* an
  interval is not a badly answered question, it is a badly posed one.
* **A structural-transformation outcome** — `reindustrialisation.py`. « Combien
  d'usines ? » needs a model class whose honest band, at country scale, contains
  both signs.
* **A receipts anchor from memory** — `agregats/anchors.py`. The euros live in a
  generated table, never in code.

## M6 — the guards sweep, and what it found

The three questions applied instrument by instrument over everything the branch
added. **Forty-nine guards were mutated and seen to fail** in the closing pass,
on top of the kill halves that live permanently in the test files.

**Question 1 — can a denominator tend to zero?** Two findings, one fixed and one
reported:

* **Fixed.** `Burden` accepted a priced aggregate larger than the national D.29
  that is supposed to contain it — 38 md€ against 10 md€ printed as « 380 % de
  couverture, écart −28,0 md€ ». That never comes from coverage: it comes from a
  unit error or the wrong file, and the symptom sends the reader to fix whichever
  of the two numbers was right. Guarded, and the guard was tested on three other
  shapes (equality with lines missing, equality with nothing missing, and
  preservation through a scenario re-render).
* **Reported, not fixed — `population/calibrate.py` is fenced to Phase 7 (§8).**
  A margin cell whose published target is **zero** is skipped by both
  `_apply_margin` and `_fit`, so it is never measured. Measured rather than read:
  a four-household rake with a target of 0 on one category keeps **2.0
  households** there, converges in two iterations, and `check_rake_result` —
  D-150's own guard — **accepts it**. Whether any published margin target is
  actually zero cannot be checked on a machine without `data/raw/`. This is §10's
  own rule looking back at us: *a comparison correct only because one side is
  zero is untested.*

Checked and clean: `explorer.grid()`, `check_base_split` (the anchor is guarded
strictly positive at construction), the income mass denominators (each guarded
`if mass > 0`), and the raking divisions themselves.

**Question 2 — will the fix be tested on a shape other than the one that
alerted?** Applied to the perimeter guard above; three other shapes, one of which
must *pass*, because a guard that refuses honest full coverage would forbid the
state the project is working towards.

**Question 3 — will we have seen this check fail?** Every guard in
`explorer.py`, `reindustrialisation.py`, `agregats/anchors.py`,
`agregats/engine.py`, and the three population guards of D-149/D-150 was mutated
and its test seen to go red. `instrument_coverage.py` carries its own permanent
kill half — `test_the_claim_would_fail_if_a_name_went_stale` fabricates a row
naming a lever nobody has.

## Blocked on downloads — the owner's machine, not this one

The container running Phase 8 had **no `data/raw/` and no network**. No anchor
value, no GDP, no value added, and no comparator could be read here — which is
why the aggregate layer keeps its figures in generated tables and refuses when
they are absent.

| what | for | state |
|---|---|---|
| COICOP consumption split (R5) | TVA per-rate base | not manifested |
| CCTN / DGEC / DGDDI / OFDT volumes | the four accises | not manifested |
| **Eurostat `gov_10a_taxag`** | **M5's benchmark** | **not manifested — the one new download Phase 8 asks for** |
| GECIR / MESR publications | the CIR gate | not manifested |
| `insee_cn2025_t3217_principaux_impots_par_categorie.xlsx` | D.29 perimeter + national total | manifested, **sourced**, absent here |
| `insee_TES_symetrique_A38_2023SD.xlsx` | value added, M5 denominator | manifested, **sourced**, absent here |
| `insee_cn2025_pib_T1101_1103.xlsx`, `insee_dette_maastricht_detail.xlsx` | §6.1 debt backtest | manifested, **sourced**, absent here |
| `rei_2025.zip` | TH RS / TF recon | manifested, **sourced**, absent here |

145 files manifested: **69 sourced, 76 in D-028 quarantine.** A quarantined file
carries a checksum and no URL — the bytes are unchanged, their provenance is not
proved.

## Owner calls, on the record and not to be chased

* **Skip-vs-fail for the data-dependent tests.** Eighteen CI items — twelve
  failures and six errors — are missing-file failures, red on `main` at its own
  head too. The population tests **skip** on exactly this absence; `test_accuracy`,
  `test_top_tail`, `test_trajectoires` and `test_zero_masked` **fail** on it. So no
  checkout without the private data can ever be green, and the red carries no
  information. Turning a test into a skip to make a PR green is not a move any
  session should make unasked.
* **The §2.4 coverage threshold.** §9 expects it in the decision log; it exists
  in neither `M0_PHASE8.md` nor `DECISIONS.md`. Without a threshold there is no
  universe, so `COVERAGE_INSTRUMENTS.md` counts **lines** and says so — which
  weighs a droit de timbre like a four-billion contribution.
* **`make full`.** Not run by the Phase 8 sessions: the handoff forbids running
  it unasked, and the eighteen data-dependent items would be red under it
  regardless. **M6's DoD item « `make full` green with the pass logged » is
  therefore NOT met, and is stated unmet rather than quietly dropped.**
* **The reviewer's verdict** on Phase 8, to be appended here.

## Armed and waiting — the dormant interrupts

* **PLF 2027, early October — S4 interrupts anything.** Runbook, harness and
  triage ready. When the text publishes: manifest it, re-derive the triage (the
  re-sweep rule), wire the pre-identified knobs, register chiffrages with
  tolerances fixed **at registration**.
* **ERFS microdata** (D-096): dormant, not dead.
* **L2, the take-up layer**: dormant. Both DREES non-recours files sit in D-026
  quarantine, so nothing computed from them is reproducible. Wakes on a sourced,
  manifested take-up file.

## Directions open — the owner picks

* **Finish M2 and M3** the day the downloads land: TVA per-rate, the four
  accises, the CIR verdict, the TH/TF recon. All four are blocked on files, not
  on questions.
* **§6.1's debt backtest** — the two INSEE files are sourced and manifested.
* **F1b's build: the RCM imputation.** Gate cleared; building it is a judgement
  about how much imputed capital income to carry.
* **F7 — succession/DMTG.** Gate only, never past it without the owner.
* **F8 — aggregate VAT.** Still waiting on Budget de Famille 2026 (~2027-28).
* **The CAF cross-check.** 30 minutes at a browser, owner-only. **No reCAPTCHA
  circumvention under any circumstances.**
* **The upstream dossier** and **all publication and deployment**: owner's,
  deferred. The input-hardening precondition (the path-traversal finding) stands.

## What the next session does if nobody says otherwise

**Nothing, until the reviewer's verdict on Phase 8.** Then, in order: whichever
of M2/M3's blocked pieces have had their files land, and §6.1's backtest.

Maintenance per `docs/CHARTER.md` otherwise — pin bumps, vintage refreshes on the
nine-source calendar, full passes.

## Standing, unchanged

ERFS microdata is not redistributable; only aggregates leave it. `data/` is
committed by allowlist only. Do not fabricate the numbers. Calibration inputs via
files only (D-026); a figure from memory is a recollection. Banded or absent,
never confidently wrong. The review file's addenda, all of them, including the
five standing questions and « reality beats every spec, on the record ».
