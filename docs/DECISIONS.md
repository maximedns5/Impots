# Decision log

Append-only. One entry per architectural decision, dated, with the reasoning
that was available at the time.

## D-000 — Reuse OpenFisca-France rather than encode legislation from scratch
Date: 2026-08-28 · Status: proposed

OpenFisca-France has 16,484 commits, ships releases weekly (v176 in Aug 2026),
and already encodes IR, CSG, cotisations and the benefit system with
date-versioned YAML parameters and a reform-layering API. Re-encoding French
tax law solo is not a viable use of the time available.

Consequence: the project inherits AGPL-3.0 and OpenFisca's issue backlog.

## D-001 — Open questions, not yet decided
- ~~Is a live academic affiliation available?~~ **Resolved 2026-08-28 (D-012):**
  yes — ERFS via Quetelet-Progedo is available. Phase 1 shipped on open data
  anyway (branch A'); the migration is planned in D-016.
- Households first, or firms first? Firms are the real gap; households are the
  easier start.
- Contribute the firm package to the OpenFisca org, or fork? **Now the live
  question**: D-017 makes the licence AGPL either way, so this is about
  maintenance and reach, not about licensing.
- ~~What licence?~~ **Resolved 2026-09-01 (D-017):** AGPL-3.0-or-later.
- What does v1 explicitly refuse to answer?

## D-002 — Phase 0 verified against openfisca-france 176.0.8 before handoff
Date: 2026-08-28 · Status: accepted

Every API pattern, variable name, parameter path, timing and golden value in
docs/PHASE0_SPEC.md was executed against openfisca-france 176.0.8 /
openfisca-core 44.7.0 in a live environment before being written down
(scripts/verify_openfisca.py reproduces the whole check). Notable findings
baked into the spec: `irpp` and `prime_activite` no longer exist (use
`impot_revenu_restant_a_payer` and `ppa`); fiscal amounts are negative;
TBS load ~3.4s, light compute ~0.5s warm, full benefits cascade ~2.3-4.8s —
hence singleton + reform cache + startup warm-up + two-tier computation.

Implementation is delegated to an Opus session via docs/OPUS_HANDOFF.md.

## D-003 — Phase 0 stack: FastAPI + a single static HTML file, no framework
Date: 2026-08-28 · Status: accepted

*(Spec §9 asks for this entry as D-002 and the next one as D-003. Both numbers
were already taken when this session started, and the log is append-only, so
everything below is shifted by one. Numbering, not content, differs.)*

The household calculator is `engine/` (a typed wrapper over openfisca-france),
`api/` (three FastAPI endpoints) and `ui/index.html` (one file, vanilla JS, no
build step). No bundler, no npm, no component framework.

Reasoning available at the time: this is a solo project whose scarce resource is
maintenance attention, and the UI is a form and a table. A build step would add a
toolchain to keep alive, a lockfile to audit and a class of failure ("it works in
dev") that a static file cannot have. The file opens from `file://` as well as
from the API, which is why CORS is wide open — a Phase 0 choice that must not
survive contact with a deployment.

Consequence: the UI has no test in `pytest`. `ui/check.mjs` exercises its logic
under a DOM shim and needs node, so it is deliberately outside CI; run it by hand
after touching the page.

## D-004 — openfisca-france pinned to 176.0.8, and what golden values mean
Date: 2026-08-28 · Status: accepted

`pyproject.toml` pins `openfisca-france==176.0.8` and `openfisca-core==44.7.0`
exactly, and CI asserts both before running anything.

Reasoning: openfisca-france releases weekly and its parameter tree moves with the
law. Every value in `tests/golden/*.yaml` was produced by that exact pair. They
are **regression anchors on our wrapper, not claims about French tax law**: they
answer "does this wrapper still read the engine the way it did on 2026-08-28",
which is the question a test can actually settle.

Policy when a bump moves a golden value: find out whether the law changed or the
engine did, write it down here, and only then re-anchor. Re-anchoring first
destroys the only evidence that anything happened. The independent check that the
numbers are *right* rather than merely stable is `tests/golden/CROSSCHECK.md`.

Consequence: dependency bumps are deliberate acts with a paper trail, not
`pip install -U`.

## D-005 — Benefits are assessed on reference periods Phase 0 leaves empty
Date: 2026-08-28 · Status: accepted, with a known defect left visible

**The finding.** The spec's situation wiring (§3.2) supplies `salaire_de_base` for
the twelve months of the simulated year and nothing else. But means-tested
benefits are not assessed on the simulated year:

  * RSA and the prime d'activité look back one quarter;
  * the aide au logement looks back a rolling twelve months ending thirteen
    months before the month it pays.

With only the target year on file, every one of those windows reads as zero
income. Measured on openfisca-france 176.0.8, a single adult on 30 000 € gross
renting at 600 €/month in zone 2:

| | year only (spec wiring) | with two years of history |
|---|---|---|
| aide au logement | 1 989.32 € | 0.00 € |
| RSA | 534.82 € | 0.00 € |
| revenu disponible | 25 633.75 € | 23 148.28 € |

That is **2 485 € too high, 11 % of disposable income** — a thousand times the
±2 € tolerance the golden cases are held to. The same mechanism puts 607.75 € of
January RSA into `single_30k` and 740.07 € into `smic_single`, and it pays RSA to
a household earning 240 000 €.

**The decision.** `situations.build_situation` takes `historique_revenus`, which
replicates salary and housing across years N-2, N-1 and N and removes the error.
It is **off by default**. Three reasons: the spec's golden values were verified
against the single-year wiring and silently re-anchoring verified numbers is
exactly what D-004 forbids; the defect is in the *inputs we choose to supply*,
not in the engine, so it belongs to a decision rather than a patch; and Phase 1
will supply real income histories from a population, at which point the flag
becomes the only sensible setting.

Both behaviours are pinned by `test_income_history_removes_phantom_benefits`, so
the size of the error cannot drift unnoticed. The golden YAML files carry the
artefact in a comment, the API echoes `historique_revenus` in every response, and
the UI states plainly which mode produced the benefit figures it is showing.

**Open question for whoever picks this up next**: flipping the default to `True`
and re-anchoring the three affected golden values, with this entry as the record
of why, is probably the right Phase 0.5 move. It was not taken here because it
would have meant failing the spec's own definition of done on the author's
initiative.

## D-006 — `caseT` (parent isolé): a half-part the spec does not mention
Date: 2026-08-28 · Status: accepted

**The finding.** French law grants a lone parent an extra half fiscal part.
openfisca-france exposes it as `caseT`, a boolean on `foyer_fiscal` at year
period, and it is the *only* lever: `nbptr` multiplies the `isol` parameter by
`caseT` directly and infers nothing from the shape of the household. The Phase 0
spec never mentions it, and its wiring rules (§3.2) therefore produce 1.5 / 2.0 /
3.0 parts for a lone adult with 1 / 2 / 3 children where the law gives 2.0 / 2.5 /
3.5.

This is not cosmetic and it does not err on the taxpayer's side: fewer parts means
more tax. A lone parent on 40 000 € with one child was being shown **1 073 € of
income tax instead of 154 € — 919 € too much**.

**The decision.** `HouseholdInput.parent_isole` is a tri-state: unset means
"infer", and a household of one adult with at least one dependent child claims
case T, because that is precisely what such a household describes. It can be set
to `false` for a lone filer who does not in fact live alone, and is refused for
any other household shape. The UI shows the checkbox only when it can apply and
explains when to clear it.

Consequence: this is a departure from a spec whose numbers were otherwise
verified. It is recorded here rather than silently adopted, per the handoff's
rule 3 — reality wins, but it wins on the record.

## D-007 — Surplus barème brackets are zeroed, not duplicated
Date: 2026-08-28 · Status: accepted

**The finding.** The spec's §3.4 recipe for a user barème of fewer than five
brackets is to give each surplus bracket the top threshold and the top rate,
"setting them equal to the top makes them no-ops". They are not no-ops. Building a
`MarginalRateTaxScale` from a `ParameterScale` **merges brackets that share a
threshold by summing their rates** — the behaviour cotisation scales rely on to
stack contributions. Three brackets at 40 % therefore merge into one at 120 %.

A three-bracket reform (0 % / 20 % above 15 000 / 40 % above 60 000) taxed a
240 000 € household **158 160 € instead of 58 720 €**, silently, with no warning
from any layer. The spec's own §7.5 names this as the most likely first bug and
§3.4 warns "do not improvise it" — the warning was right, the recipe was not.

**The decision.** Surplus brackets take the top threshold and a rate of **zero**,
so the merge sums to exactly the top rate. Verified for barèmes of 2, 3, 4 and 5
brackets. In addition, `system.reformed()` reads the evaluated scale back through
`reforms.verify_bareme` and refuses to serve a reformed system whose scale is not
bracket-for-bracket what was requested: a tax figure that is wrong but plausible
is the worst failure this project can produce, so it fails loudly instead.

The number of active brackets is also derived from the parameter tree at the
requested date rather than hardcoded to five, which is only true for recent years.

## D-008 — Phase 0 dependencies trimmed; the dataframe stack moved to an extra
Date: 2026-08-28 · Status: accepted

The scaffold's `polars`, `pandas`, `pyarrow`, `dbnomics` and `scikit-learn` moved
from `[project.dependencies]` to an optional `data` extra. Nothing in the
household calculator needs a dataframe (spec §1), and they roughly triple install
time in CI. `pip install -e ".[data]"` brings them back for Phase 1.

## D-009 — Local environment: homebrew's Python is unusable on this machine
Date: 2026-08-28 · Status: accepted, environment-specific

Every homebrew CPython on this host (3.12 and 3.14 both checked) ships a
`pyexpat` linked against a newer `/usr/lib/libexpat` than macOS 26.2 provides:

    Symbol not found: _XML_SetAllocTrackerActivationThreshold

which breaks `plistlib`, hence `platform.mac_ver()`, hence pip's wheel-tag
computation — `python -m venv` cannot even bootstrap pip. The project venv is
therefore built with `uv`, whose standalone interpreters bundle their own libexpat.

This is a local defect, not a project constraint: `python3 -m venv` is still the
documented quickstart and is what CI uses. Recorded so that the next person who
hits it does not spend the afternoon on it.

## D-010 — The timing budget skips rather than lies on a loaded machine
Date: 2026-08-28 · Status: accepted

The spec's definition of done sets a wall-clock budget: a light `/simulate` under
1.5 s warm, a full one under 6 s. Those assertions exist to catch a *change in
what the code does* — a light request that quietly started computing the benefits
cascade turns 0.5 s into 3 s — not to benchmark hardware.

A stopwatch cannot do that job on an oversubscribed machine. Measured on this
host at load 33 on 8 cores with 6.7 GB swapped, the same full-tier computation
took 6.5 s and 18 s within a minute of each other, and constructing the
tax-benefit system took 13 s against the spec's measured 3.4 s. Nothing in the
wrapper changed between those samples.

The timing tests therefore take a `quiet_machine` fixture that skips, with the
observed load in the skip reason, when the one-minute load average exceeds the
core count. Loosening the budget until it passed under any load would have thrown
away the only signal it carries. `IMPOTS_SKIP_PERF=1` still forces the skip, and
CI sets it — a shared runner is never quiet enough for this measurement.

The structural version of the same check,
`test_light_tier_does_not_trigger_the_benefits_cascade`, asserts directly that no
famille or ménage variable was ever computed in a light request. It has no timing
dependency and always runs. It is the test that actually protects the property;
the stopwatch is corroboration.

**Outcome.** Once the load fell to 5–7, the full suite ran green with nothing
skipped: 90 passed in 1 min 51 s, including all five timing assertions. The same
suite had taken 10 min 09 s with four timing failures an hour earlier, on the same
code. The budget is met; what needed guarding against was the measurement, not the
software.

## D-011 — `historique_revenus` is now the default; three goldens re-anchored
Date: 2026-08-28 · Status: accepted · Supersedes the default chosen in D-005

D-005 measured the defect and left the flag off, explicitly flagging the flip as
"probably the right Phase 0.5 move". Phase 1 forces the question, and the answer
is yes on two independent grounds:

1. **The single-year wiring is not a defensible default for anyone.** It credits
   a 30 k€ earner 1 989 € of housing aid and 535 € of RSA they are not entitled
   to, and a 70 k€ couple 1 134 € of RSA. Shipping that as what a caller gets when
   they say nothing was always the wrong way round.
2. **The population engine cannot use it at all.** At population scale the
   benefits cascade does not merely mis-pay, it *raises*
   `ParameterNotFoundError` unless all 36 months of N-2..N carry explicit inputs
   (PHASE1_SPEC §1.3, verified). A default that Phase 1 must override everywhere
   is not a default.

Re-anchored in the same change, each YAML carrying the old value and the reason:

| Case | Line | Was | Now |
|---|---|---|---|
| `single_30k` | rsa | 607.75 | 0 |
| `single_30k` | revenu_disponible | 23 908.48 | 23 148.28 |
| `smic_single` | ppa | 2 369.60 | 2 794.04 |
| `smic_single` | rsa | 740.07 | 0 |
| `smic_single` | revenu_disponible | 20 365.80 | 19 895.59 |
| `couple_70k_2kids` | revenu_disponible | 58 181.96 | 55 895.45 |

`smic_single` is the instructive one: two lines moved in *opposite* directions.
The phantom RSA disappears, and the prime d'activité **rises** by 424 €, because
it is no longer ramping up from an empty reference quarter through the first
months of the year. "Remove the phantom benefits" was not the same thing as
"benefits go down", and a case that only ever moved one way would have hidden
that.

Unchanged and worth stating: the whole income-tax block (`ir`, `salaire_net`,
`parts_fiscales`, `rfr`), both light-tier goldens, and the EMTR. Income tax is
assessed on the year itself; only the lookback-assessed benefits move.
`test_income_history_does_not_move_the_tax_block` pins that, and
`test_income_history_removes_phantom_benefits` keeps **both** modes measured so
the size of the old error stays visible rather than being deleted along with the
default.

Modelling assumption now load-bearing: **steady state**. Years N-2 and N-1 repeat
year N's salary and housing. A household that changed job, moved, or had a child
is not modelled — real histories arrive with ERFS (Phase 1 branch C) or not at
all. The UI says so where the numbers are shown.

## D-012 — M0 branch: A' (EEC structure, synthetic incomes), ERFS to follow
Date: 2026-08-28 · Status: accepted · Evidence: `docs/M0_RECON.md`, `scripts/verify_eec.py`

**What M0 found.** The open EEC fichier détail *does* group individuals into
households — `IDENT` × `TRIM` gives 199 451 dwelling-quarters of plausible size,
so branch B (synthetic assembly) is moot. But it carries **no income variable of
any kind**: the five numeric columns in the whole file are a weight and four
hours-worked measures. The spec's §3 gate expected the household identifier to be
the pivot; it is present, and the pivot turns out to be income.

Three further gaps, none anticipated by the spec, all measured in M0_RECON:
children under 15 are absent from the file entirely (27 863 dwelling-quarters
declare children and contain none); age is banded into five groups of which one
(25-49) holds 36 % of the population; and there is no region variable and no
link-to-reference-person variable.

**Decision (Max, at the M0 gate): build A' now.** Household structure is observed;
incomes, dependent children and exact ages are synthesised from published margins.
The §4.1 parquet schema is unchanged, so `skeleton.py` and `incomes.py` are the
only modules that would be rewritten when better microdata arrives.

**Branch C is available** — Max holds ERFS access via Quetelet-Progedo. It is
therefore a scheduling question, not a design one, and it is worth pursuing in
parallel because it closes all four gaps at once: real fiscal incomes, real
children, exact ages, real geography.

**Licensing consequence, load-bearing for this repo.** EEC is Licence Ouverte /
Etalab: redistributable with attribution, which is what makes §7's committed
`tests/fixtures/eec_sample.parquet` legal. **ERFS is not.** It arrives under a
signed agreement restricting use to the declared research purpose and forbidding
redistribution and re-identification. So if the population ever moves to ERFS:
the committed CI fixture must stay EEC-derived or become fully synthetic, no
ERFS-derived rows may enter the repository, and the reconciliation report must
publish only aggregates. Worth fixing in code before the data arrives, not after.

**Epistemic consequence, stated here because §4.3 will lean on it.** With wages
calibrated to published wage margins, the aggregate IR yield is only a
*semi*-independent validation line: it partly measures our own calibration. The
genuinely independent lines in branch A' are the ones driven by household
structure and the tax schedule rather than by the wage level — foyer counts,
benefit caseloads, the shape of the decile distribution. The reconciliation
report must say which is which rather than presenting one undifferentiated table.

## D-013 — Household assembly: one ménage per dwelling-quarter, one tax unit per adult unit
Date: 2026-08-28 · Status: accepted · Departs from PHASE1_SPEC §4.4

**The unit.** `IDENT` × `TRIM` — a dwelling in a quarter. The EEC rotates, so a
dwelling appears in up to four quarters and `EXTRIAN` is an annual weight that
sums to the population over the *whole* file. Keeping every dwelling-quarter and
never rescaling gives 199 451 household observations at the correct total weight,
against 80 171 distinct dwellings.

**Who is whose**, since the file has no link-to-reference-person variable:
reference person = lowest `NOI` (absent in 1.4 % of households, where the lowest
present wins); partner = in a couple-typed household with exactly two
`COUPL_LOG` = yes, the coupled person who is not the reference (unresolved in
1 222 of 96 846 couple households); dependent child = anyone else young enough to
be rattaché.

**The departure.** §4.4 prescribes "one foyer + one famille per ménage". Measured,
18 226 dwelling-quarters (9 %) contain an adult who is neither the reference
person, nor their partner, nor a rattachable child — a flatmate, a grandparent, a
30-year-old still at home. Folding them into a single foyer fiscal would make each
one a `personne_a_charge`, inflating that household's quotient familial and
zeroing a tax liability that really exists. So: **one ménage per dwelling-quarter,
one foyer fiscal and one famille per adult unit inside it.** Two couples sharing a
flat are still modelled as one couple plus two singles; that residue is counted,
not hidden.

**Rattachement.** A young adult is a dependant if under 21, or under 25 and not in
work — the nearest the EEC can express of "still studying" (art. 196 B CGI).
Attaching every 15-24-year-old, the obvious reading, hands a half-part to
households whose 23-year-old works full time. The exact age is drawn inside a
ten-year band, so for any individual it is a coin flip; in aggregate it puts about
the right number of young adults on each side.

**Two notions of "child", kept apart, after conflating them cost 20 % of the
child population.** `is_child` is rattachement — it drives roles, `nbptr` and AF.
`insee_child` is INSEE's "enfant d'une famille": anyone under 25 in the dwelling
who is not the reference person or their partner. The published family-size
margins count the *second*. Subtracting only the first from them over-generated
under-15s by 20 %, inventing a small child for every employed 21-24-year-old
living at home. With the counting fixed, the synthesis lands on 11.64 M under-15s
against a published 11.62 M with no correction applied at all.

## D-014 — Calibration margins, and what they cost us in validation
Date: 2026-08-28 · Status: accepted

**Spent on calibration** (and therefore permanently unavailable as validation):

| Margin | Value | Source |
|---|---|---|
| Total gross wages (D11, whole economy) | 1 111.65 bn € | INSEE comptes nationaux 2025, semi-definitive |
| Declared pensions and annuities | 400.4 bn € | DGFiP |
| Unemployment benefit paid | 35.9 bn € | Unédic |
| Children under 15 | 11.39 M (+2 % residual) | INSEE RP 2023 |
| Children per family, by family type | distribution | INSEE RP 2023 |

**Left untouched, and therefore able to say something**: the income-tax yield,
foyer counts, every benefit total and caseload, the niveau-de-vie distribution and
the interdecile ratio.

**What branch A' costs this table.** With wages calibrated to a wage-bill margin,
the income-tax line is only *semi*-independent: it tests the tax schedule applied
to a distribution whose level we set. The genuinely independent lines are the ones
driven by household structure rather than by the wage level — **foyers imposés
(−0.5 %)** is the strongest result in the report for exactly that reason, and the
**interdecile ratio** is the most informative failure.

**The rule bit, once, visibly.** `RETIREMENT_AGE` — the age above which an
inactive person is treated as a pensioner — moves the simulated income tax from
+14.0 % at 60 to +10.5 % at 55. It was chosen on the count criterion (which cut
best reproduces DREES's ~17 M pensioners: 55 gives 15.96 M, 62 gives 14.24 M),
*not* on its effect on the tax line, and `incomes.py` records the reasoning in
that order. Choosing it the other way would have converted a validation line into
a calibration target through the back door and quietly emptied the reconciliation
report of meaning. This is the failure mode §4.3 exists to prevent, and it is
easier to fall into than it looks.

## D-015 — Aggregates the population is not yet fit to publish
Date: 2026-08-28 · Status: accepted, and the reason the UI banner is not optional

The reconciliation report states every residual. Three of them are large enough
that the corresponding number must not be published as a finding:

**RSA, +110 %.** With the take-up bridge applied (a 100 %-take-up model should
exceed observed spend by 1.30-1.41×, DREES ER 1370/1379) it is still +55 % above
where it should sit. The cause is measured, not guessed: **13.5 M adults have no
modelled income at all** — 3.87 M self-employed, who receive nothing because
Phase 1 models no self-employment income, and 9.6 M inactive people under the
retirement proxy, who in reality live on AAH, invalidity pensions, ASPA or a
partner's earnings. Zero-income adults form zero-income familles and claim RSA.

**Prime d'activité.** Raw, it is +24.5 %, inside the flat benefit tolerance. Judged
against its own take-up bridge (1.68-1.77×) it is *28 % too low*. Both statements
are true and the report prints both, because a benefit computed at full
entitlement is not comparable with observed spend without the bridge, and the
bridge is where the interesting error is.

**Interdecile ratio D9/D1, +43 %.** The distribution is too dispersed, and it is
too dispersed at the bottom for the same reason RSA is too high: households whose
only adults have no modelled income sit far below where their real counterparts
sit. This is the single number that says the decile table is not yet publishable
as a description of French inequality — as opposed to a usable ranking of who a
*reform* helps and harms, which is what Phase 1 is for and which depends on
differences rather than levels.

**Allocations familiales, −31.6 %.** The AF-eligible family count is close
(4.22 M against 4.75 M, −11 %); the spend gap is larger because AF is
income-modulated and the wage calibration scaled wages up by 9 %, pushing families
across modulation thresholds.

Consequence, and it binds on the UI: **the population tab reports reform deltas,
never baseline levels of RSA, PPA or the income distribution**, and it links to
this report. Closing these gaps means modelling self-employment and disability
income, or moving to ERFS (branch C, D-012) — where all of it is observed.

## D-016 — Branch C (ERFS) is planned now; A''s income gaps are not patched
Date: 2026-08-29 · Status: accepted · Plan: `docs/PHASE1C_ERFS.md`

D-012 recorded that ERFS access exists and left branch C as a scheduling
question. It is now decided: **plan the migration now, and do not spend effort
closing branch A''s income gaps in the meantime.**

Reasoning. The reconciliation report's four failing lines have one cause — 13.5 M
adults with no modelled income — and closing it inside the open-data branch means
building a self-employment and disability income model by hand, roughly a month of
work that ERFS deletes on arrival. The §4.1 parquet schema was designed as the
seam and holds: only `skeleton.py` and `incomes.py` are rewritten.

The argument that decided it is not the failing lines, though. It is that A'
*calibrates* the wage level, which spends the wage-bill margin and leaves the
income-tax residual only semi-independent — it tests the tax schedule applied to a
distribution whose level we chose. Under ERFS incomes are observed, the wage bill
moves back to the validation column, and the income-tax line becomes a real test.
No amount of patching A' can produce that.

Consequence, and it is a constraint on the repository rather than a preference:
ERFS is not redistributable. Nothing ERFS-derived may be committed, the CI fixture
stays EEC-derived, and only aggregates are published. `docs/PHASE1C_ERFS.md` §5
lists the checks; a pre-commit hook refusing anything under `data/` would make
them mechanical, and should exist before the data does.


## D-017 — Raking (`calibrate.py`): build it, as Branch-C infrastructure
Date: 2026-09-01 · Status: accepted and **implemented** · Rationale: `docs/REVIEW_2026-08-29.md` §1

Phase 1 shipped without spec §4.3's IPF raking; the omission was reported rather
than buried, and the reviewing session ruled on it.

My argument for skipping it — that `EXTRIAN` is already calibrated by INSEE on
sex×age, so re-raking would be near-identity — is accepted as far as it goes and
found to miss the point. **Raking is joint.** Keeping sex×age in the margin set
is not there to move those margins; it is there to *constrain* the adjustment
made to the others. And the +1.5 % ménages against −0.0 % individuals pair is not
the clean bill I read it as: at fixed persons, 1.5 % too many households means
household size runs about 1.5 % small — a composition skew, mild here, and
exactly what a household-type margin corrects.

Ruling:

* Build `calibrate.py`: margins-agnostic IPF, weight-ratio bounds [0.2, 5],
  convergence and bounds tests. It sits on **Branch C's** critical path, not A''s
  — ERFS arrives weighted to its own vintage, two or three years stale, and must
  be re-raked to simulation-year margins. Both branches need it and the Progedo
  waiting window is the slot for it.
* Run it once on A' with two margin sets: households by type (RP), and
  age-band × sex as drift constraints. No region margin — the EEC has none
  (M0_RECON §4.3). Record before/after for **every** reconciliation line
  whichever way they move: if the effect is as small as I predicted, the report
  saying so is worth having; if AF or the foyer counts move, better still.
* The income-mass scaling stays as-is for A' — it dies with ERFS — and the
  wage-bill margin stays marked spent (D-014 already handles that correctly).

### What was built

`calibrate.py`: margins-agnostic IPF, bounds [0.2, 5], convergence and bounds
test-asserted. Two margin sets, per the ruling. Two things in it are worth
knowing about:

**Raking runs before incomes, and the order is load-bearing.** Its margins are
purely demographic, so it needs nothing incomes produce — while incomes calibrate
the wage bill against the weights in force. Raking afterwards silently moves the
wage bill off the target it was just scaled onto, leaving a spent calibration
margin that no longer holds. Built in the wrong order first; caught by checking
the wage bill after the change, which is now exact to 0.0000 %.

**A household spans several age×sex cells but carries one weight**, so textbook
IPF does not apply to a person-level margin. The household's adjustment is the
mean of its members' cell factors, weighted by membership — integrated household
weighting. Letting members of one household drift apart would break every
household-level aggregate downstream, and there is a test pinning that they do not.

**The household typology had to be fixed before it could be a margin.** Mapping
every `role_menage == "autre"` member to "ménage complexe" put 2.6 M households
there against a census 1.1 M, by counting every adult child living at home as an
unrelated person — INSEE counts a child of the family at any age, while our tax
roles stop at rattachement age (D-013). A member younger than the reference
person now counts as a child of the family. Worst margin miss fell from 133 % to
41 % on that correction alone, before any raking.

### What it did

Converged in 25 iterations. Weight ratios 0.84 to 1.81, **nothing clipped**.
Effective sample size 143 973 of 199 451 households — the precision cost, and a
modest one.

| Margin | worst miss before | after |
|---|---|---|
| Households by type | 41.5 % | 0.84 % |
| Age band × sex (drift) | 2.2 % | 0.00 % |

And on the validation lines, from `reconcile --compare-unraked`:

| Line | unraked | raked |
|---|---|---|
| Ménages | +1.5 % | **+0.0 %** |
| IR — barème | +6.6 % | +8.7 % |
| Salaires déclarés | −4.2 % | −3.1 % |
| Foyers imposés | −2.6 % | −2.2 % |
| Allocations familiales | −25.6 % | −25.2 % |
| RSA | +103.0 % | +106.2 % |
| Niveau de vie médian | −12.7 % | −12.1 % |
| Rapport interdécile | +40.6 % | +39.4 % |

**The honest reading.** The ménage count goes to its target because that is the
margin — calibrated, spent, and no evidence of anything. Everywhere else the
effect is under three points and mixed in direction: income tax and RSA get
slightly worse, the distribution and the foyer counts slightly better. Both passes
ran on a 50 000-household subsample selected proportional to weight, so raking
changes *which* households are drawn as well as how they are weighted, and
movements of about a point are sampling noise rather than signal.

So the prediction that this would be near-identity on A' was roughly right about
the *size* of the effect and wrong about the reason it was worth doing. The
correction it makes is to household composition, which the aggregate household
count hid; the population's large residuals are an income-modelling failure and no
reweighting was ever going to close them (D-015). The value banked here is that
Branch C now has a calibration stage waiting for it, and that the report says
plainly what raking did not fix.

## D-018 — Licence: AGPL-3.0-or-later, and the firm package is an in-repo extension
Date: 2026-09-01 · Status: accepted · Closes **both** open questions in D-001

`LICENSE` holds the verbatim GNU AGPL v3 text; `pyproject.toml` declares
`license = "AGPL-3.0-or-later"` under PEP 639, which is why the build now
requires setuptools >= 77.

**Determined rather than chosen.** `openfisca-core` and `openfisca-france` are
both AGPL-3.0-or-later, and this package imports them directly, so anything
distributed is a derivative work and must be AGPL-compatible. Dual-licensing was
never available: you cannot relicense someone else's copyleft. The alternative
considered and rejected was splitting the tree — putting the parts that do not
import openfisca (`margins.py`, the reconciliation machinery, the EEC skeleton)
under a permissive licence and keeping the rest AGPL. It is legitimate, and it
buys nothing at this size against real ongoing maintenance.

**What is actually live is section 13**, which is what separates AGPL from GPL:
anyone who lets users interact with a modified version *over a network* must offer
those users its Corresponding Source. Running the calculator locally triggers
nothing. Hosting it does — and Phase 0 deferred deployment precisely as out of
scope, which is why this had not bitten yet.

So the obligation is engineered rather than documented:

* `IMPOTS_SOURCE_URL` names a URL serving this version's source. Read from the
  environment, not hardcoded, so a fork that deploys advertises **its own**
  source rather than ours.
* `GET /health` reports `licence` and `source_url`; the UI footer renders the
  link, and shows no link at all when the server has not been told — a missing
  offer is a deployment that has not met the condition, and hiding it would be
  worse than showing it.
* Startup logs a warning when the server is bound beyond localhost with no source
  URL set.

**What this forecloses, stated plainly:** a closed hosted version of this software
is not possible, now or later. If that ever mattered it would have to be decided
before the Phase 2 firm package is written, not after — which is why D-001's
"contribute upstream or fork?" is now the live question rather than a distant one.

**One argument the analysis undersold**, and the reviewing session was right to
put it back: for *this* project section 13 is not a cost, it is the thesis. The
product's signature is showing its working. A licence under which nobody can host
a closed fork of the honesty machine is the licence that matches the mission.

**Data is not covered.** Code licensing and data licensing are independent. The
INSEE Enquête Emploi is Licence Ouverte / Etalab 2.0 (redistribution with
attribution — what makes the committed CI fixture legal); ERFS is restricted and
non-redistributable (D-016, `docs/PHASE1C_ERFS.md` §5). The AGPL changes neither.

### D-001's other half, settled in the same entry

Since the licence is AGPL either way, "contribute the firm package upstream or
fork?" was never a licensing question — it is about maintenance and reach, and it
is cheaper to settle before any firm code exists than after.

The Phase 2 firm package is developed **in-repo, as an independent extension
package following OpenFisca conventions** — YAML dated parameters,
openfisca-test-format YAML cases — AGPL like everything else, and structured so
it can be *offered* upstream once it has substance (IS, C3S, CFE encoded and
tested). Contribution is the goal; the fork-shaped start is the schedule. Gating
Phase 2 on OpenFisca-org governance and review latency, which the Phase 0 audit
measured as thin, would trade a month of work for a queue.

*(Not legal advice. For anything with stakes beyond this repository, a lawyer,
not a language model.)*


## D-019 — The DGFiP cross-check passed; the publication blocker is lifted for IR
Date: 2026-09-01 · Status: accepted · Evidence: `tests/golden/CROSSCHECK.md`

Phase 1 spec §0.5 P2 kept `CROSSCHECK.md` a blocker for publication, not for
development: golden tests prove this wrapper reads openfisca-france consistently,
and cannot prove openfisca-france is right. Done on 2026-08-29 against the
official simulator (simulateur-ir-ifi.impots.gouv.fr, revenus 2024, modèle
simplifié), driven through the browser by the reviewing session with Max present.
The arithmetic is DGFiP's own, so independence from OpenFisca holds.

| Case | Our `ir` | DGFiP | Our `rfr` | DGFiP |
|---|---|---|---|---|
| `single_30k` | 812 € | **812 €** | 22 143 € | **22 143 €** |
| `couple_70k_2kids` | 1 274 € | **1 274 €** | 51 661 € | **51 661 €** |

Zero difference on both, and the intermediates agree too: droits simples 1 171 /
décote 359 / 1 part for the single, 1 889 / 615 / 3 parts for the couple — which
are exactly what `ir_plaf_qf`, the décote and `nbptr` report. Agreement on the
intermediates matters more than agreement on the total: two engines can reach the
same final figure through different errors, and these did not.

**What this licenses and what it does not.** The household calculator's income-tax
path is now independently validated and may be described as correct for the cases
covered — salaried households, no capital income, no réductions or crédits.
Nothing else moved: the population's benefit levels remain unpublishable (D-015),
the golden benefit lines were never covered by this check (the DGFiP IR simulator
has no equivalent), and the corresponding CAF cross-check remains undone.

## D-020 — Firm-tax parameters: what the primary sources changed
Date: 2026-09-01 · Status: accepted · Evidence: legislation confirmation against Légifrance/BOFiP

PHASE2_SPEC marks its tax parameters `[ENACTED]` — checked against secondary
sources, to be confirmed against the primary text during M1. The confirmation ran
and changed three things.

**The PLF 2026 proposal to raise the reduced-rate slice from 42 500 € to
100 000 € was never enacted.** 42 500 € stands. The spec flagged this as the
figure to confirm and it was right to.

**The three parameters on the same page of CGI 219-I do not switch on the same
event, and the first encoding got one wrong.** The 25 % normal rate and the 10 M€
turnover ceiling apply to exercices *ouverts* from their dates; the 42 500 €
profit slice applies to exercices **clos à compter du 31 décembre 2022**. For a
calendar-year firm that means FY2022 already gets 42 500 €. Dating it from 2023 —
which is what "raised by the LF 2023" invites — over-taxes every eligible small
firm by 660 € for a full year. Corrected, and pinned by a test that says why.

**The two PME turnover thresholds diverged in 2021 and must never share a
constant.** CGI 219-I-b moved the reduced-rate ceiling to 10 M€; CSS art. 235 ter
ZC left the contribution sociale exemption at 7.63 M€. Reusing one "PME CA
threshold" would wrongly exempt every firm between them. They were already
separate parameters here, which is the trap not falling.

**Two biases recorded rather than fixed**, because the population cannot support
the fix:

* *Exercice dates.* Every firm is treated as calendar-year, since SIRENE and
  ESANE carry no exercice dates. A firm straddling the calendar year is taxed at
  the wrong rate in a transition year, and the prorata rules cut in opposite
  directions for the two thresholds — turnover is scaled **up** to twelve months,
  the profit slice **down**.
* *Group scope.* Conseil d'État, 13 March 2025, n° 481538 held that the turnover
  test applies to the whole group holding a company, integrated or not — wider
  than the statute read alone. Intégration fiscale is out of scope (§0), so the
  eligible population here is over-stated at the margin.

The normal rate carries **no value before 2022** on purpose: from 2019 to 2021 it
was a two-bracket scale that also depended on turnover, which this module does not
encode, and a query for an earlier year now resolves to nothing and fails loudly
rather than returning a flat rate that never existed.

## D-021 — CVAE: encoded in full, on an assiette that is a declared proxy
Date: 2026-09-01 · Status: accepted · Evidence: CGI art. 1586 ter–septies confirmed against Légifrance and BOFiP BOI-CVAE-LIQ-10 (19/11/2025); DGFiP notice 1329-AC millésime 2026

The CVAE placeholder is gone; the schedule is encoded from the primary text. Four
things the confirmation settled, each of which the obvious implementation gets
wrong.

**The rate schedule is continuous, not marginal.** Each bracket formula yields the
*average* rate applied to the whole value added — there are no stacked brackets, so
the household module's barème machinery does not apply here and `verify_scales`
has nothing barème-shaped to guard. That is a change from what D-007's note
anticipated, recorded here so the next reader does not go looking for it.

**The rate is rounded to the hundredth of a percentage point, half-up.** Skipping
this turns a step function into a continuous one and moves the rate by up to ±6 %
at the bottom of the schedule. Three official worked examples (CA 2.7 M€ → 0.08 %,
6.2 M€ → 0.17 %, 40.1 M€ → 0.28 %) pin the formulas and the rounding together and
are kept as tests. Sizing a franchise test with the *unrounded* rate made it pass
for the wrong reason on the first attempt, which is now written into the test.

**The 2026 rate goes up, not down.** LF 2025 art. 62 deferred the phase-out by
three years, so the maximum rate returns from 0.19 % (2025) to 0.28 % (2026)
before resuming its decline and lapsing in 2030. Anyone assuming a monotone
phase-out codes the wrong number, so the trajectory is a test.

**Two thresholds that are not the same threshold.** 152 500 € puts a firm in
scope; the rate is nil below 500 000 €. And since 2024 there is no minimum
contribution, only a franchise — the CVAE is owed from 64 €, not 63 €.

**What is not right, and cannot be made right from open data.** The base is the
*accounting* value added from ESANE, because no open source publishes the fiscal
one. Rents, crédit-bail and location-gérance are intermediate consumption in
accounting but are **not** deductible from the CVAE base, so the simulated
assiette is understated — most for firms that lease their assets, which is
correlated with sector. The bias therefore distorts the incidence table and not
only the total, and cannot be removed by a single national factor. It is in the L1
banner and in the reconciliation report, not only here.

## D-022 — CEBGE: encoded on a stationarity assumption, stated rather than hidden
Date: 2026-09-01 · Status: accepted · Evidence: LF 2025 art. 48 and LF 2026 art. 12 confirmed against Légifrance/JO; BOFiP BOI-IS-AUT-60 (12/08/2026)

The CEBGE is real, renewed, and not in the CGI: it lives in article 48 of the LF
2025, amended in place by article 12 of the LF 2026. A parameter store keyed on
CGI articles needs a slot for it, which is why it sits at the tree's root.

**Two features dominate the yield and the naive reading has neither.** The base is
the **average of two exercices' IS**, so a firm whose profit collapsed still pays
on the average. And each threshold carries a **100 M€ smoothing band** over which
the rate ramps linearly — without it a firm at 1.50 bn would pay in full what a
firm at 1.49 bn does not pay at all. The upper band interpolates *between* the two
rates (20.6 % → 41.2 %) rather than ramping from zero; coding it like the lower
band undercharges by 16.5 points. Both published worked examples are tests.

**The population has one year, and the statute tests two.** Liability, rate and
smoothing all read turnover across the current and preceding exercice, and the
base needs the prior exercice's IS. Our firms have a single year. Rather than
default the prior term to zero — which would silently halve every base, the exact
shape of D-005 and D-011 — `is_avant_report` carries a **formula** returning this
year's IS, so the assumption is stationarity, it is visible in the code, and a
population that supplies a real prior year overrides it because an input beats a
formula.

**What that assumption costs.** The second exercice's threshold is 1.5 bn tested
on *that exercice alone*, disregarding the prior year. So a firm at 1.2 bn in 2026
after 1.1 bn in 2025 leaves the tax it was in the year before, and a firm crossing
1.5 bn enters. Those entries and exits are precisely where the 2026 yield moves,
and a stationary population cannot show them. Declared in the banner; it is a
reason the CEBGE line is reported as mechanical arithmetic and not as a forecast.

**Reviving a lapsed CEBGE is refused, not improvised.** The parameters go null
after the second exercice. A reform knob that moved the threshold in a later year
would have no band width to derive the smoothing from, and putting 100 M€ back
would be inserting a number no source supports for that year. The knob raises with
that sentence instead. Relatedly, a fully-null parameter is *removed* from the
OpenFisca tree rather than set to `None`: the guard is `hasattr`, and an `is None`
check raises `ParameterNotFoundError` from inside a formula instead of returning
zero.

## D-023 — The firm parameters rest on research whose adversarial pass ran once
Date: 2026-09-01 · Status: accepted · Evidence: workflow wf_ec6ad4bc-ac8 — 6 of 11 agents returned

The legislation confirmation behind D-020, D-021 and D-022 was run as a fan-out
with a verifier per topic. **Six of eleven agents returned; one verifier out of
five did.** The IS core was verified. CVAE, the CEBGE, the C3S and the validation
figures rest on a single agent's confirmation each, unverified.

That is worth recording because of what the one completed verification found. It
returned `SCOPE_PROBLEM` with twelve defects against a report whose *values* were
all correct — among them a **verbatim quote that does not exist on the page it
cites, carried under `confirmed_against_primary: true`**, and a single un-pinned
Légifrance URL backing four differently-dated rows, which resolves to the current
text and so "confirms" a 2002 parameter against the 2026 statute.

So the prior is explicit: on this evidence a single-agent confirmation gets the
numbers right and the citations wrong. The values encoded in D-021 and D-022 are
internally consistent, reproduce five published worked examples the agents did not
author, and match the statutory structure — that is real evidence, and it is why
they were encoded. Their **citations** are not yet at the standard the IS core's
are, and the parameter YAML carries the URLs as given.

Consequences taken now, rather than left as intent:

* No firm figure is published as validated on the strength of these citations. The
  reconciliation report's fidelity column says which lines rest on confirmed
  sources and which on unverified ones.
* The IS-core corrections the verifier listed — date-pinned URLs per parameter
  version, the groupe-fiscal member exclusion, the ordering of the 42 500 € slice
  after deficit imputation — are open work, not silently absorbed.
* Re-running the four missing verifiers is the first item of firm-module work, and
  it is cheap. It is not a blocker for the module's arithmetic, which is what
  P2 gates on.

## D-024 — Firm tolerances, and why the IS gate is deliberately wide
Date: 2026-09-01 · Status: accepted · Evidence: reports/reconciliation_entreprises.md

Declared tolerances for the firm reconciliation: calibration ±1 %, IS ±20 %,
other instruments ±25 %, shape ±15 %.

**±20 % on IS looks lax and is the point.** One modelling choice — the single
national fiscal-to-accounting ratio — dominates that residual, and it is a free
parameter in the sense that nothing outside the model pins it. A tighter gate
would not make the model better; it would make tuning that ratio until the line
goes green the cheapest way to pass, and a margin spent that way can never be
evidence again. The gate is set where it is so that passing it means the
*mechanics* are right, and the report carries the ratio's value in its method
notes so a reader can judge the choice rather than inherit it.

**±25 % on the other instruments** because their bases are proxies (accounting
value added for CVAE, D-021), or their published year is not the simulated one
(the CEBGE's 2025 figure is its first exercice at a 1 bn threshold; the model runs
the second at 1.5 bn).

**The comparator choice matters more than the tolerance.** The model computes IS
before any crédit d'impôt, so it is judged against the national accounts' "IS
avant crédits d'impôt" (69.5 bn, 2025) and not against net budget receipts
(59.9 bn), which are net of 24.6 bn of remboursements and are shown only to size
the gap. Picking the closer of the two after seeing the result would be
calibrating to a validation line.

**On the fixture, every line is outside tolerance, and that is the correct
outcome.** The committed cell table is invented and holds 1.10 M firms against
2.72 M real ones, so the residuals run at −60 % to −72 % more or less uniformly.
The report says so above the table, in those words, rather than in a footnote. The
ship gate is not met and cannot be met until a real cell table is loaded; what the
fixture demonstrates is that the machinery runs end to end.

**One line is expected to have the wrong sign** and is tagged `context` for that
reason. INSEE's implicit rate falls with firm size (denominator is ENE over all
firms, so loss-makers drag it down); the model's effective rate rises with size,
because C3S and CVAE hit turnover and value added whether or not there is a
profit. DGFiP's average rate on profits orders the sizes the other way again.
Three objects, three orderings — and choosing whichever one the model resembles
would be the purest available form of calibrating to a validation line.

## D-025 — The verification completed, and what it did to D-023
Date: 2026-09-01 · Status: accepted · Supersedes the caveat in D-023 · Evidence: workflow wf_ec6ad4bc-ac8, 12/12 agents, 5/5 verifiers

D-023 recorded that four of the five adversarial verifiers had not returned and
that CVAE, the CEBGE, the C3S and the validation figures therefore rested on
single-agent confirmation. They have all returned now. **Every one came back
`SCOPE_PROBLEM` except the firm-data agent, which came back `WRONG`.**

**No encoded value was refuted.** The C3S verifier is the plainest: *"I attempted
to refute all 12 reported parameters and could not break a single numeric value."*
The CVAE verifier independently re-derived the 2025/2028 bracket coefficients this
repo encodes, finding the 0.176 % / 0.175 % discontinuity that those exact numbers
produce at 10 M€ — a corroboration that would have been impossible if the
coefficients were invented. The CEBGE rates were attacked directly and held: a
secondary source had reported them halved to 10.3 % / 20.6 %, and the verifier
showed 10.3 % is BOFiP's worked *example* of the smoothed rate at 1.55 bn, not a
statutory rate. Acting on that "correction" would have halved a correct parameter.

**What the verifiers changed here, and it is all real:**

* *A warning aimed at a correct source, removed.* The dégrèvement parameter carried
  a comment saying BOI-CVAE-LIQ-10 n° 78 still held the stale LF 2024 trajectory.
  The verifier fetched the document and found n° 78 is about exercice dates within
  a group; the sentence does not exist. Warning withdrawn, and the withdrawal is
  written into the file so it is not re-added.
* *The CEBGE's ordinal count is not expressible by date, demonstrated.* BOI-IS-AUT-60
  § 320 and § 325 give two companies **closing on the same day, 31/12/2026**, one in
  its first exercice at a 1 bn threshold and one deemed in its second at 1.5 bn. No
  date-keyed parameter tree can express that. The majority case is kept and the
  parameter file now carries the refutation rather than a vague "assumes calendar
  exercices".
* *C3S is assessed on the previous year's turnover, and the model uses the current
  year's.* The verifier named this exact implementation — `0.16 % × max(0, CA_N −
  19 M€)` graded against receipts booked in N — as an off-by-one-year error. It is
  unfixable in a one-year population, so it is declared in the formula, in the
  banner and on the report line: simulated C3S is overstated by about one year of
  nominal turnover growth.
* *The effective-rate line's construction is now named.* DGFiP Statistiques n° 39
  contains three constructions of "the" average rate on profits — 24.26 % (the
  published series), 24.32 % (Tableau 2) and 24.34 % (graphique 2's own
  denominator). This is the single line the "who pays" reconciliation is graded on,
  so it is pinned to the published series explicitly rather than left to drift to
  whichever number is nearest.
* *Three IS perimeters, not two.* DGFiP Statistiques n° 43 publishes 61.8 bn for
  2025 — 1.9 bn above the budget line, because it bundles the contribution sociale.
  Recorded as context so that a reader grading this model against "the DGFiP figure"
  knows which of the three they hold. Likewise CVAE has four published perimeters,
  and the ~0.5 bn between two of them is the taxe additionnelle CCI the model does
  not levy.

**One accidental benefit of an assumption.** The verifier showed the CEBGE's
second-year rate is **non-monotonic in current-year turnover** — with prior-year CA
at 3.5 bn, a firm at 1.55 bn pays 10.3 %, at 1.59 bn pays 18.5 %, and at 1.60 bn
jumps to 41.2 % — and warned that an implementation testing the rate bands in
statutory order returns 41.2 % for the first case. The model does not have this bug,
for two reasons worth separating: the band order in the formula happens to be
correct, and the stationarity assumption (D-022) collapses the two turnover tests
into one so the pathological case cannot arise at all. The assumption removes a real
discontinuity. That is a limitation, not a feature — the model cannot price a reform
whose effect runs through that cliff.

**The firm-data agent returned `WRONG`, with 15 problems.** That is the SIRENE ×
ESANE research for the real cell table — the one thing standing between this module
and a meaningful reconciliation. Nothing from it has been used: the committed cell
table is invented. It must be re-run before any real cell table is built, and until
then the ship gate stays where D-024 left it.

**The IS-core corrections remain open.** Date-pinned Légifrance URLs per parameter
version, the groupe-fiscal member exclusion, and the ordering of the 42 500 € slice
after deficit imputation and the zone abattements. None affects a value; all affect
whether a future reader can re-find what was confirmed.

## D-026 — Calibration inputs never pass through an agent's prose
Date: 2026-09-02 · Status: accepted · Evidence: two measured failures of the alternative

**The principle.** A figure the model is calibrated to must be computed by tested
code from a primary file whose sha256 is in `data/raw/MANIFEST.json`. Agents locate
files and adversarially verify what the code computed. **They are never the source
of record for a figure.**

This is not a judgement about agents in general; it is a conclusion from two
measurements of the same method on the same kind of task:

* Phase 1 put six statistics through research agents. Six came back with scope
  problems.
* Phase 2's firm-data agent — the SIRENE/ESANE research for the cell table — came
  back **`WRONG`**, with fifteen problems.

A third data point runs the other way and is why the verifier layer stays: the one
IS-core verifier that completed found a **fabricated verbatim quote carried under
`confirmed_against_primary: true`**, in a report whose values were otherwise all
correct. Agents are good at attacking a claim and unreliable at being one.

**What changed in the code.** `entreprises/cells.py` computes the whole cell table
from three manifested spreadsheets — INSEE Ésane 2023, INSEE Focus 372, DGFiP
Statistiques 39 — and `impots population manifest` now checksums *every* file in
`data/raw/`, recording a null URL and an explicit "not reproducible by a third
party" note for the 79 that have no recorded source. The gap is visible instead of
silent, which is the point.

**The one figure still outside the rule**, and it is deliberately the only one:
`P_LOSS_BY_SIZE`. Loss-making is a *count*, and no machine-readable source
publishes it per size class — Ésane has no loss counts and DGFiP's data file has
loss *amounts*. It is read from INSEE Références 2023 fiche 3.6, cited at its
definition, and flagged in the provenance so it cannot be mistaken for a computed
figure.

## D-027 — The cell table, and what four verifiers did to it
Date: 2026-09-02 · Status: accepted · Evidence: reports/reconciliation_entreprises.md (vintage 2023); workflow wf_8c8764da-bd4, 5/5 agents

The firm module runs on a cell table computed from three manifested files — INSEE
Ésane 2023, INSEE Focus 372, DGFiP Statistiques 39 — rather than on the invented
fixture. **The first version of it was wrong in four material ways, and the
verifiers found all four.** Recording the corrected state alongside what it looked
like before, because the difference is the argument for the method.

### What the verification found

Two of four returned `WRONG`. None of it was arguable.

**The published split I estimated.** Ésane merges "ETI ou GE" into one class at the
`a21` level, so the code split it using national mean turnover per firm. Focus 372
**publishes that split**, in the same workbook: figure 3b for turnover and 3c for
value added, by broad sector. The estimate was out by up to 7 points on turnover and
12 on value added — 128 bn and 39 bn misallocated against a table two sheets away.
Estimating what a file already publishes is precisely the failure D-026 exists to
stop, and it happened inside the module written to implement D-026.

**The haircut that ignored its own distribution.** Half of Ésane's micro-enterprises
are not liable to IS, so the code scaled the micro class by 0.51 — counts *and*
values alike, removing 334 bn of turnover. But the firms that fall out are the
*smallest*: micro-entrepreneurs, not micro SARLs. Under the lognormal this module
itself fits to that class (σ ≈ 2.6–3.1), the smallest half holds between 0.1 % and
2 % of turnover. The module was fitting a heavy-tailed distribution and then
adjusting it as though it were uniform. Now the value share comes from the fitted
lognormal's own tail: `1 − Φ(Φ⁻¹(1−p) − σ)`.

**The floor that zeroed whole sectors.** A cell's published résultat is net of its
own loss-makers. The code took `max(net, 0)` — so every cell with a negative
aggregate got a taxable base of exactly zero, including 8 057 information-and-
communication PMEs turning over 46.8 bn, and the whole of real-estate ETI and GE.
Losses are now added back across a size class in proportion to value added, an
assumption that cannot zero a sector.

**The guard that guarded nothing.** `"IS" in label.upper()` also matches the
"entreprises à l'IR" row directly beneath, because ENTREPRISES contains IS. The
right row was being selected by publication order alone; a reordered sheet would
have silently substituted the 4.7 M income-tax count for the 2.7 M corporation-tax
one and moved every level in the table with it.

Two further fixes came from the one verifier that returned `CONFIRMED` and still
found latent defects: Ésane's note de lecture declares **two** missing-data codes
(`S` and `N`) where the reader handled one, and a suppressed value on a surviving
cell was being coerced to zero, contradicting the module's own stated rule.

### What I had got wrong about my own results

D-027's first draft offered two hypotheses for the failing sector lines — a champ
gap for immobilier, and the régime mère-fille for industrie. **Both were guesses,
and the real cause of the two worst was a code defect.** Fixing the floor took
information-et-communication from −70 % to −21 % and immobilier from −91 % to
−71 %. The lesson is the ordering: a residual gets a mechanical explanation before
it gets an economic one, and I reached for the economics first.

### Where it stands

Every instrument line is inside tolerance: **IS −0.2 %**, the free rate test
**+0.6 %**, contribution sociale −3.9 %, **CEBGE +23.1 %** (it was +45 % before the
dispersion was fitted and the haircut corrected), CVAE −18.4 %, **C3S +1.2 %**.

Four of six sector lines pass — Commerce/transports +2.0 %, Construction +16.8 %,
Activités spécialisées +17.7 %, and information-et-communication now near the edge
at −21.4 %. Two remain out: **industrie +38.3 %** and **activités immobilières
−70.9 %**. No hypothesis is recorded for either this time. DGFiP counts 587 000
IS-liable firms in immobilier against a small fraction of that in Ésane's marchand
field, which *looks* like champ — but that is exactly the kind of guess the last
draft got wrong, so the lines stay red and unexplained until something is measured.

### Three things that are now true of the method

**The fiscal-to-accounting ratio is computed, not chosen.** D-024 set the IS
tolerance at ±20 % because that scalar was free and a tighter gate would have
invited tuning it. It is derived now, so there is nothing to tune.

**The IS *level* is calibrated and the report says so.** Reproducing the taxable-
profit total by construction makes landing near the published IS total mostly
arithmetic. Taxable profit moved into the calibration table as spent, and the
informative line — the aggregate rate on profits, where the denominator is
calibrated and the numerator is not — was added beside it.

**By-size cannot be validated against DGFiP; by-sector can.** DGFiP's TPE/PME/ETI/GE
are fiscal buckets and INSEE's are the LME decree applied to profiled enterprises;
DGFiP counts 220 600 PME where INSEE counts 164 000. A by-size residual measures the
taxonomy gap, which is the same category error the C3S vintage fix corrected.
Sectors are NAF in both sources, so the six sector lines are the module's real
evidence.

**And the dispersion inside a cell stopped being an assumption.** Focus 372 publishes
value-added quartiles, which fit a lognormal σ directly. The fitted values run 0.68
to 3.14 against the single assumed 1.4 — wrong in both directions at once. It
mattered most where it was least visible: too fat a tail invents firms above the
CEBGE's 1.5 bn threshold.

## D-028 — Provenance is a property of the tree, not a fact about it
Date: 2026-09-02 · Status: accepted · Evidence: reviewer audit, 2026-09-02 addendum

The reviewer verified directly that none of the 73 unsourced files in `data/raw/`
was reachable from any code under `src/`. That was true. It was true *by audit* —
a statement about one afternoon — and this decision makes it true by construction.

**Two mechanisms.** `require_sourced()` refuses to open a raw input whose manifest
entry has no URL, and it is called from both readers that touch published files.
And every unsourced file moves to `data/raw/_unsourced/`, keeping its manifest
entry marked `quarantined`, so that its presence in the tree can never be read as
provenance. Adding a URL to `KNOWN_SOURCES` releases it on the next `impots
population manifest`. 73 files moved; 12 remain sourced, which is every file the
pipeline actually opens.

The distinction being enforced: a checksum proves a file has not *changed*; only a
URL proves where it came from. A figure computed from a file with the first and not
the second is reproducible by nobody.

Tests carry both halves — the assertion itself, and a static check that every data
filename named in an ingest module resolves to a manifest entry with a URL and no
quarantine flag.

## D-029 — Two standing rules, promoted from lessons
Date: 2026-09-02 · Status: accepted

**Mechanical before economic.** A residual gets a mechanical explanation attempt,
and the *failure* of that attempt recorded, before any economic hypothesis is
written down. Adopted because it was violated to visible cost: D-027's first draft
offered a champ story for immobilier and the régime mère-fille for industrie, and
the real cause of the two worst lines was a `max(net, 0)` that zeroed every cell
with a negative aggregate. The rule binds reviewers too.

**Codes, not labels.** No substring matching against a French display string
anywhere in ingest. `"IS" in label.upper()` is true of *"Nombre d'entreprises à
l'IR"*, because ENTREPRISES contains IS; the corporation-tax row was being selected
by publication order alone, and a reordered sheet would have swapped a 4.7 M count
for a 2.7 M one and moved every level in the firm table with it. Logic keys on a
code, or compares a whole label. A test walks the ingest modules' ASTs and fails on
any `<string> in <label-ish name>` — and it caught the first repair, which had
replaced the vacuous test with a narrower substring rather than with equality.

## D-030 — The two red sector lines are one perimeter effect, measured
Date: 2026-09-02 · Status: accepted · Evidence: the reviewer's two diagnostics, run

D-027 left industrie at +38.3 % and activités immobilières at −70.9 % red and
deliberately unexplained. Under the mechanical-before-economic rule the reviewer
proposed two cheap checks. Both were run and both point the same way.

**Check 1 — a quantity the model never touches.** Ésane's firm count divided by
DGFiP's runs at 1.90, 2.00, 2.12, 2.17 and 2.22 across five sectors — that ratio is
just the IS-liability rate — and at **0.48** for activités immobilières. A fourfold
outlier against an otherwise flat pattern, on counts the model does not use.

**Check 2 — where the residual sits.** 88 % of the industrie overshoot is in ETI
and GE (18.6 bn of 21.1 bn), which is the signature of group structure rather than
of base construction.

**The mechanism both indicate.** Ésane classifies *profiled enterprises*, so an
industrial group's property arm is consolidated into industry; DGFiP classifies
*legal units* and taxes that arm in real estate. The two residuals carry opposite
signs because they are the same activity, counted on either side of a boundary the
two sources draw differently. **Pooled, the pair lands at +16.2 %** — inside the
±20 % gate.

The report now carries all three lines: the two unpooled ones stay red, because the
model's sector split really is wrong at that boundary, and the pooled one says the
mass is in the right place. Neither is dropped. What is *not* claimed is that this
explains the residual completely — 16.2 % is inside the gate, not at zero, and the
information-et-communication line remains at −21.4 % with no diagnostic run.

## D-031 — The behavioural store, and the five rows that died in it
Date: 2026-09-02 · Status: accepted · Evidence: workflow wf_0acd2e4f-b5b, 10/10 agents, 5/5 verifiers

Phase 3's characteristic failure is that **a band computed from a bad parameter looks
exactly like a band computed from a good one**. So the store's one hard rule is that
a row without a verifier verdict cannot load, enforced in code and tested. `WRONG`
refuses too; `SCOPE_PROBLEM` loads, because Phase 2 measured what that verdict means
— citations needing repair while the values hold — and refusing it would discard
every parameter this project has.

The fan-out ran the D-025 pattern over five parameter families: five researchers, five
adversaries. **Every verdict came back `SCOPE_PROBLEM`, and five rows died.**

**What the seed table got wrong.** `docs/PARAMETERS.md` was a reviewer-compiled table
and the spec said to treat every row as unverified input. It was right to.

* `eti_all` is **0.02**, not 0.05. The seed's value appears in no specification of the
  cited paper; 0.02 is stable across six.
* `labour_supply_intensive` (0.10) and `labour_supply_extensive` (0.30) have **no
  defensible primary basis at all**. Bargain-Orsini-Peichl reports France
  disaggregated by sex and marital status — eight rows, running 0.02 to 0.145 — and
  the seed's two scalars are averages the paper never states. Both removed.
* `passthrough_unlinked` is **0.0**, not 0.15.

**The correction that matters most is not a value but a bound.** `eti_top_decile`'s
support was filed at 0.06 — a *cumulative* 1999-2003 change — while the estimator
works on one-year differences. The verifier re-derived the largest single-year move
from the paper (0.0317) and checked the chain against a printed table to four decimal
places. **0.06 → 0.03**, which halves the reform size this project will call
"in-support". A guardrail set from the wrong window is worse than none, because it
looks strict.

**C4 has no channel, and that is the honest v1.** The production-tax investment row
was to carry a band centred on zero with the study's uncertainty — the informative
answer to "did the CVAE cut raise investment?". Its only dimensionally-valid row is
an elasticity **with no published value**: the bounds were derived, not read, and
carried `confirmed_against_primary: true` — the exact flag that hid the fabricated
quote found in Phase 2. Its underlying ratio also divides a first stage by an outcome
estimated on *differently reweighted samples*, which the authors themselves flag as a
limitation of the method one page before the caveat that was quoted. The other four
rows are dimensionally incommensurable — a quarterly level effect of 0.00054 beside
log-point coefficients — and the verifier's warning is exact: guardrail code
comparing a reform against one and applying the other "will silently commit a units
error". All five removed. The channel reports **no usable evidence**.

Removed rows stay in the YAML under `removed:` with their reason, so a channel that
narrows shows why in the data and not only in this log.

## D-032 — C2 and C3 have no lever, and the spec assumed one
Date: 2026-09-02 · Status: accepted

PHASE3_SPEC lists four v1 channels. Two of them — employment at the SMIC, and
employer-contribution incidence — price **employer social contributions**, and no
reform knob in this simulator moves one. The household spec exposes the barème, the
décote, the plafond du quotient familial and the two CSG rates; CSG is an *employee*
contribution, and the spec itself names `csg_activite_*` as its example of a knob no
channel claims.

Adding an employer-contribution knob is an engine change with its own verification
burden — the allègements généraux are a barème, not a scalar — and it is not smuggled
in under a behavioural phase. So both channels are written, tested, and dormant, and
they say so: *"aucun paramètre de cotisation patronale n'est exposé par le
simulateur, donc rien ne déclenche ce canal."*

That leaves v1 with **one live channel**, C1. Stating that plainly is worth more than
four channels of which three quietly return zero.

## D-033 — What the EMTR machinery measures, and the choice inside it
Date: 2026-09-02 · Status: accepted

Marginal rates are a finite difference: OpenFisca has no `taux_marginal_imposition`.
Two choices are worth recording because neither is forced.

**The step goes to earners, and the denominator counts them.** Bumping every individu
by 100 € would turn people with no earnings into earners, which is a different
experiment. So this is a household's marginal rate on an extra euro spread across the
earners it has — not a primary earner's rate and not a second earner's. A household
with no earnings has no marginal rate on labour at all, and is recorded as such rather
than given a zero, because zero would say "keeps every euro".

**Full tier, not as a technicality.** The PPA and RSA tapers are most of the marginal
rate at low wages. A light-tier EMTR would produce a tidy distribution that is simply
wrong at the bottom, which is where the policy argument lives. On the 2024 population,
median EMTR runs from 20.8 % in the first decile of marginal rates to 63.5 % in the
tenth, and the households in that top decile are poor, not rich.

The band is opt-in over HTTP because it costs two more full-tier runs. Baseline rates
and whole results are both memoised on disk, keyed on the sample size as well as the
reform — a subsample is a different population, not a cheaper view of the same one.

## D-034 — What the first band says, and what it does not
Date: 2026-09-02 · Status: accepted · Evidence: /population/simulate, 2024 population

Raising the top rate from 45 % to 50 % yields **+0.662 bn** mechanically. With the
taxable-income response, the band is **+0.36 to +0.50 bn**, median +0.43 bn: the
response gives back about **35 %** of the mechanical yield, and the reform grades
`in-support`.

Four things that number is not.

It is **not a forecast**. It is what the measured elasticities imply at constant
everything else, over one year, on a synthetic population whose top tail is a
construction (D-015). It is graded in-support because a five-point rate move sits
inside the identifying variation of the underlying reforms — barely, now that the
bound is 0.03 for the top decile.

It **omits the best-identified French elasticity there is.** Capital income responds
far more sharply than labour income, and the population carries no capital income
until ERFS lands, so no capital channel exists. The UI says this where a capital knob
would appear. A band that silently omitted it would understate the response to any
reform touching the top.

It rests on a **short-run** elasticity whose own authors argue the long-run value —
the one relevant to judging a barème — is lower.

And the band's width comes from ranges that are **specification spreads, not
confidence intervals**, for the top-decile row. That is labelled in the store rather
than papered over: the published interval is tighter, and narrowing to it was left
undone rather than guessed at.

## D-035 — The chiffrage suite: three cases from eight, and two of them red
Date: 2026-09-02 · Status: accepted · Evidence: workflows wf_bad98eea-d5e and wf_a42cf764-e0a

PHASE3_SPEC §5 asks for **at least five** historical cases. The suite ships with
**three**, because eight were located and five died under adversarial source-checking.
Shipping three that survive beats five with two rotten, and the deaths are the more
useful record.

**What died, and why it matters that it did.**

* *LFI 2023 barème indexation (6,2 Md€).* The figure is a **budget-year cash** number,
  not an assiette one — so the revalorised prélèvement-à-la-source grids are inside
  it, which the case's own caveat declared harmless. And its source locator named a
  section heading that **does not exist** in the cited document, carried under
  `confirmed_against_primary: true`. That is the third time in this project that flag
  has sat on something unverifiable.
* *PLF 2025 indexation (3,7 Md€).* Costed at 2,0 % while the enacted LF 2025 indexed
  at **1,8 %**. Those values never governed anyone's tax, and this suite grades
  historical *law*.
* *IS rate 28 → 25 % (4,1 Md€).* Unrunnable, and its spec did not express the article:
  the 4,1 Md€ is measured against the LFI 2017 trajectory, which also carried a second
  instrument the case ignored.

**Two structural defects the checking exposed, both now fixed in code.**

*The firm module could not price any year before 2024.* `prelevements_entreprise`
computes CVAE unconditionally, and the CVAE guard checked `taux_max` — dated from
2010 — before reaching into `bareme.pente_t1`, dated from 2024 because the earlier
bracket coefficients were never verified. Every backdated run died with a
`ParameterNotFoundError` naming a CVAE parameter, which says nothing about the cause.
The guard now covers the whole schedule, and years before 2022 fail with a sentence
explaining the real limit: the pre-2022 normal rate depended on turnover *and* a
profit tranche at once, and this system carries a scalar rate.

*A one-sided bound has to be read in magnitude.* Each barème indexation also indexes
the déduction forfaitaire floors, the pension abattement and several specific QF caps
— none expressible here, all inside the published cost. So the expressible subset
must produce a *smaller* effect, and the test is an inequality. But for a cost the
published figure is negative, so a simulated value further below it is a **larger**
cost while the signed residual reads negative and looks like an undershoot. Written on
the signed residual, the one-sided test passes exactly the cases it should fail.

**Two of the three cases are red, and both are findings.**

*C3S abattement, −34 %.* The obvious explanation — ten years of nominal turnover
growth — is refuted by the model's own aggregate, which lands within 1,2 % of the
published receipt. The level is right, so the miss is the **distribution of turnover
within the 3,25–19 M€ band** — precisely the quantity the reconciliation report can
only declare as unconstrained. The case converts a declared assumption into a measured
error of about a third.

*Barème indexation 2024, +10 % in magnitude.* The model produces a **larger** effect
than the state's while moving a strict **subset** of the instruments. Both halves
together are the result. Vintage drift is a few percent, not ten; the missing base
(capital, indépendants, réductions) pushes the other way. What remains points at the
synthetic income distribution carrying more mass in the bracket-crossing region than
the real one — consistent with D-015, and the first external measurement of that
concentration rather than a declaration of it.

The green case, the CEBGE, is recorded as **not independent evidence**: zeroing its
rates reproduces a reconciliation line the project already grades. It is kept as an
end-to-end check that knob, tree and runner agree, and labelled so nobody counts it
twice.

## D-036 — Post-mortems on the five dead chiffrage cases
Date: 2026-09-02 · Status: accepted · Required by the Phase 3 verdict

Eight historical articles were located for the backtest suite and five died under
source-checking. Why each died is data — about how verifiable the official record
actually is, and about where this simulator's coverage stops.

**1. LFI 2023 barème indexation (6,2 Md€) — wrong basis, and a fabricated locator.**
The figure is a **budget-year cash** number, not an assiette one, so the
prélèvement-à-la-source grids revalorised on 1 January 2023 are inside it — and the
case's own caveat singled that component out as harmless. Separately, its source
locator named a section heading that does not exist in the cited document, carried
under `confirmed_against_primary: true`. *Class: the published figure is not the
object it appears to be.*

**2. PLF 2025 indexation (3,7 Md€) — costed on a text that never became law.**
The PLF indexed at 2,0 %; the enacted LF 2025 indexed at 1,8 %. Those values governed
nobody's tax. The suite grades historical **law**, and a costing of a superseded draft
grades nothing. Its base also straddled two revenue years with no published
decomposition. *Class: draft costing mistaken for enacted law.*

**3. IS rate 28 → 25 % (4,1 Md€) — the spec did not express the article.**
The 4,1 Md€ is measured against the **LFI 2017 trajectory**, not against a flat 28 %,
and that counterfactual also carried the PME turnover-ceiling rise the article
suppressed — a second instrument the case ignored. *Class: a costing whose
counterfactual is another law.*

**4. CVAE trajectory steps — inexpressible at their own years.** Rejected during
location: the firm module could not price any year before 2024 (fixed since, floor now
2022), and the steps interact with the dégrèvement and the taxe additionnelle CCI,
which the knobs do not carry. *Class: coverage.*

**5. Décote revaluations — no separately published figure.** Each rides inside a
barème-indexation costing and is never priced alone. *Class: the record does not
isolate the instrument.*

**Three of the five are failures of the official record's verifiability, not of this
project** — a figure that is not what it looks like, a draft mistaken for law, a
counterfactual that is itself a law. That is worth knowing about the material any
backtest suite in this domain has to work with.

**Standing rule, from the verdict.** *Every time a knob is added to a ReformSpec, the
expressible historical articles are re-swept.* Coverage is what killed cases 3, 4 and
5, so coverage growing is the event that makes new cases possible. The employer-
contribution knobs are the first trigger.

## D-037 — C4 wakes: bounds read from the tables, and it is still a zero
Date: 2026-09-02 · Status: accepted · Evidence: IPP Rapport n° 60, manifested (sha256 e8234692…)

D-031 removed every production-tax investment row because the only dimensionally
valid one had **no published value** — its bounds were derived and then marked
confirmed. The verdict's ruling was that the report itself publishes intervals, and
that the conclusion should come from the table rather than from anyone's summary of
it. The report is now in `data/raw/` with a manifest entry, and its tables were read.

**The bounds exist, and the channel wakes.** Tableau 4.2 (p. 143) and Tableau 4.3
(p. 144) give the synthetic-difference-in-differences effect on log corporate
investment for two treatment comparisons, each with its standard error and its own
first stage:

| comparison | Δlog CET | effect on log investment | 95 % interval, per unit \|Δlog tax\| |
|---|---:|---:|---|
| group 1 vs 3 | −0.6323 | +0.0221 (0.0110) | [+0.001, +0.069] |
| group 2 vs 3 | −0.3491 | −0.0035 (0.0108) | [−0.071, +0.051] |

The band is the union: **[−0.071, +0.069], centred on zero.**

**Zero is the authors' position, not a convenient rounding.** p. 12: *"On ne détecte
en revanche pas d'effet sur les exportations ou l'investissement."* p. 14: *"le
rapport trouve peu de résultats empiriques clairs."* And p. 142 explains why their
own positive coefficients are not enough: *"Si la méthode échoue dans le cas de
variables telles que le CA ou la masse salariale, il est naturel d'interpréter les
résultats positifs sur l'investissement avec une grande prudence."* The same
synthetic DiD produces implausible negative effects on turnover and the wage bill.

**What the derivation does not resolve, stated rather than smoothed.** The report
notes (p. 141) that its method weights units differently per variable, so dividing an
outcome by a first stage crosses two samples — the N differ, 235 456 against 255 304.
The report also publishes balance-sheet-ratio effects on an *identical* sample, all
positive and significant, which would support a positive central value. They are not
used, because the authors place the whole set under the same caution. Confidence is
`low` and the band's width carries the disagreement instead of resolving it.

**Two implementation consequences.**

*C4 reports per cent of investment, never euros, and is never summed into the revenue
band.* Investment is not revenue; adding them is a category error that typechecks. The
band assembly now sums only channels denominated in EUR, and every channel carries its
own band in its own unit.

*The driver stays in logs.* −0.63 log points is a **47 %** cut, not a 63 % one, and an
earlier row died partly for exactly that conversion. Keeping the parameter, the
support bound and the channel arithmetic all in log space removes the opportunity.

**What the band says.** Halving the CVAE rate moves corporate investment by somewhere
between −3.0 % and +2.8 %, centred on zero. A band that wide is not a null dressed up
— it is the honest statement that a serious evaluation could not rule out effects of
several per cent in either direction, which is more informative than silence and quite
different from a tightly estimated zero.

## D-038 — The employer-contribution knobs, and the trap in their parameter node
Date: 2026-09-02 · Status: accepted · Evidence: paths introspected live against openfisca-france 176.0.8

C2 and C3 were written in Phase 3 against a knob the ReformSpec never had — a spec
error on the record (D-032). Seven knobs now exist: the réduction générale's plafond
and its two rates, and each bandeau's plafond and rate.

**Every path was introspected rather than taken from the brief**, which is how two
things surfaced. The maladie bandeau's parameters live under `alleg_gen.mmid`, not
under the `mmid` of `cotisations_securite_sociale_regime_general` — that one carries
the 13 %/7 % rates the bandeau reduces, not the reduction itself.

**And the plafond node changes shape by year.** `plafond` before 2024;
`plafond_smic_courant` **and** `plafond_smic_2023_12_31` during 2024;
`plafond_smic_2025_01_01` from 2025. Worse, the 2024 formula reads
`max(plafond_smic_courant × smic, plafond_smic_2023_12_31 × smic_2023-12)` — so
writing one child leaves the other winning the max and the reform doing **nothing**,
with no error raised anywhere. The knob writes every child the year's formula reads,
and `verify_allegements` reads them all back per D-007.

A second-order version of the same trap: `update()` *creates* a child that did not
exist, so asking the editable tree which plafonds exist returns every one ever
defined — including next year's. Discovery is done on the node evaluated **at** the
instant, so a 2024 reform cannot silently move the 2025 ceiling.

**The worked examples are hand-checkable** because both bandeaux are flat rates above
a cliff. At 2.83 SMIC, removing the famille bandeau costs exactly 0.018 × 60 000 =
1 080 €, and extending the maladie cliff past the worker saves exactly 0.06 × 60 000
= 3 600 €. Also pinned: the réduction générale reaches nothing at that wage, and its
plafond and rate are not interchangeable — just above the ceiling, extending it is
worth several times raising the rate, and well below the ranking reverses.

## D-039 — The public cost had one side, and employer reforms fell through it
Date: 2026-09-02 · Status: accepted · Evidence: found by wiring C2

`Aggregates.reform_cost` was the change in household disposable income. That is the
right measure for every reform this project had priced until now, because a household
gain is a state loss.

An employer-contribution reform is not one of those. It changes what the state
**collects** without moving disposable income at all — the gain lands on the firm. So
extending the réduction générale from 1.6 to 2 SMIC reported a public cost of
**exactly zero** while cutting labour cost by 17.7 bn. The headline would have read
*« la réforme coûte 0,00 Md € »*.

The cost now has both terms. The employer side is measured as Δ(salaire_super_brut −
salaire_brut), **not** as Δ`cotisations_employeur`: that variable is gross of the
allègements and does not move when one changes — it is why the bug was invisible, and
a test asserts the gross measure still reads zero so the next reader does not
"simplify" back to it.

Two things worth naming. This was a **mechanical** defect found by building the
behavioural layer on top of it — the layer boundary held, and the traffic across it
ran the useful way. And the correction moves no number it has no business moving: a
household reform's employer term is zero, so its cost is what it always was, which is
also a test.

## D-040 — C2 and C3 awake, and what they refuse to say
Date: 2026-09-02 · Status: accepted

**C2 — employment.** −0.43 at the SMIC (Bunel & L'Horty 2012, support 0.04
confirmed), declining to −0.1 at twice it, and **zero above**. The straight line
between the two published points is this project's construction and is labelled as
such in the store, in the channel's diagnostics and in the UI. The zero above is a
refusal: an earlier row carried a constant −0.2 there, resting partly on a Swedish
study that was cited nowhere and whose downloaded PDF turned out to be a different
paper. **C2 can therefore never grade `in-support`** — two of its three rows cannot
say how far they carry — and that is the guardrail refusing to launder a construction
as evidence, not a defect.

**C3 — incidence.** 1.0 for benefit-linked contributions, 0.0 for unlinked. No French
knob moves a contribution of a single class: maladie and famille cover is universal,
so a worker's entitlement does not depend on what was paid, and the réduction
générale spans both kinds at once. **The range is the answer** — the distributional
statement inherits the incidence uncertainty visibly, which is what the spec asked
for. C3 is denominated in euros and is still kept **out** of the revenue band: it
reallocates, the mechanical total is identical at both ends, and adding it would count
the same euros twice. Membership in the band is declared per channel rather than
inferred from the unit, precisely because the unit does not settle it.

**Two sign errors, caught by asking what the number should look like.** A first
version reported 99 000 jobs **lost** from a 1.5 % cut in labour cost — an extra
negation on top of an already-negative elasticity. And a contribution cut passed
through fully was reported as wages **falling**. Both directions are now pinned by
tests that state the expected sign in their names.

**A distinction the channels now draw.** Inputs *not supplied by the caller* are
different from inputs *promised and broken*. The second raises — that is the Phase 1
lesson, where quantities were computed and silently dropped while every guard stayed
green. The first reports "not computed" with a reason. Conflating them made two
channels raise on reforms that simply did not concern them.

**Corrections applied from the verifiers.** `passthrough_unlinked`'s support was
0.041, taken wholly from a reform the paper itself classifies as an **income tax**
change; it is 0.018, the variation of the one reform that actually identifies it. A
threshold twice too wide would have graded as "in support" reforms that nothing
supports. Four further rows were removed: two whose ranges were invented under
`confirmed_against_primary: true` when the paper publishes only two point averages,
one employee-side row with a fabricated upper bound and suppressed standard errors,
and one official *calibration* presented as corroborating the estimate when the two
bodies differ by a third.

## D-041 — The re-sweep, and the sharpest measurement of D-015 yet
Date: 2026-09-02 · Status: accepted · Evidence: tests/chiffrages/allegements_points_de_sortie_lfss2025.yaml

D-036's standing rule fired for the first time: new knobs, so the expressible
historical articles were re-swept. The employer-contribution knobs make the LFSS 2025
step of the allègements refonte expressible, and its published figure was already in
the repository — CCSS mai 2026, table 2, in a file manifested for the C3S line.

**The case is red by a factor of two, and that is the most useful result in the
suite.** Simulated 4.15 Md€ against a published 2.0 Md€: **+107 %**.

**Mechanical explanations tried first, and both fail.** Re-encoding at 2025 as a
mirror — ceilings back to 2.5 and 3.5 against 2025 law and the 2025 SMIC — gives
4.84 Md€, or +142 %: the alternative encoding is *worse*, so the vintage is not the
cause. And the published figure is 1.6 CNAM plus 0.4 CNAF, which is exactly the two
branches the two bandeaux belong to, so nothing is missing from the comparator.

**What is left is the shape of the synthetic income distribution, and this instrument
measures it far more sharply than the barème does.** Both bandeaux are **cliffs**:
below the ceiling a flat rate, above it nothing. Lowering a ceiling removes the whole
reduction from everyone between the old and the new one, so the yield is proportional
to the mass in that band **alone** — 2.25 to 2.5 SMIC, and 3.3 to 3.5 SMIC. A
population with too many earners there overshoots directly, with nothing to damp it.

**The contrast between the two red cases is the finding.** The barème indexation reads
+10 % on an instrument with progressive brackets; this reads +107 % on two narrow
cliffs. So D-015's error is not a gentle level shift in the synthetic distribution —
it is a mis-shaped density, and any reform whose yield turns on the mass in a narrow
wage band will be badly overstated until the population carries observed incomes.
PHASE1C_ERFS §6 makes the barème case the migration's acceptance test; this one
should re-run second, and it is the more demanding of the two.

## D-042 — Read-back is not enough: check the parameter exists before writing it
Date: 2026-09-02 · Status: accepted · Evidence: the 2026 refonte, found during the re-sweep

The re-sweep surfaced a defect in the knobs added the same day, and it is a new shape
of an old failure.

**The 2026 refonte does not reparameterise the allègements. It replaces them.** Both
bandeaux disappear and the réduction générale becomes a power function — `puissance`,
`t_min`, `t_delta_petites_entreprises` — reaching 3 SMIC. So
`entreprises_de_moins_de_50_salaries` does not exist in 2026.

Writing to it anyway **succeeded**. `update()` creates a child that does not exist; the
D-007 read-back then found exactly the value it had just written and passed; and
labour cost moved by **0.00**. A reform that reports success and does nothing, with
every guard green — the failure this project keeps finding, arriving this time through
the guard built to catch it.

**The lesson is precise: reading back a child you created proves nothing.** Existence
is now checked *before* the write, against the node as the year's formula sees it, and
the refusal names the replacement so a reader is not left hunting. The check is
surgical — `plafond` survives the 2026 rewrite and its knob still works, because the
concept survives even though the rate parameters do not.

## D-043 — CI has run, it was green on the first try, and why that is not luck
Date: 2026-09-02 · Status: accepted · Evidence: 5 runs on github.com/maximedns5/Impots, 5 successes

The hardening brief opens by saying the workflow "has never executed on a real
runner". That was true when it was written and is no longer: **five runs, five
successes, no red run in the project's history.** The README now carries the badge.

The brief asks for this to be said plainly if the first run was green, because it is
a result rather than a non-event. It was — and it was green for a reason worth
recording, since the same reason is reusable.

**The first push was rehearsed against a clean tree.** Before pushing, `git archive
HEAD` was exported to a temporary directory and the suite run there with nothing
under `data/` but the two files git actually tracks. That is what CI sees, and it is
not what a working copy looks like: this repository's `data/` holds 86 manifested
inputs locally and two committed files remotely.

The rehearsal caught exactly one failure, and it was a real one. A provenance test
called `require_sourced` on an invented filename and matched the resulting message —
which passes locally, where the manifest exists, and fails on a fresh checkout, where
a different error fires first. **The test was asserting its environment rather than
its behaviour.** It now writes its own two-entry manifest and checks both cases it
cares about.

So the rule, and it costs four minutes: **rehearse on `git archive HEAD` before the
first push of anything that touches data paths, manifests or fixtures.** A red first
run would have been recoverable; the interesting part is that the failure it would
have exposed was a test that could never have failed on the machine that wrote it.

Nothing else surfaced — no path, timeout, cache or fixture problem. The
`needs_population` / `needs_primary` skip marks did their job: 31 tests skip on a
clean checkout and 295 run.

## D-044 — `update()` may never create, and the verify audit that came with it
Date: 2026-09-02 · Status: accepted · Closes the class D-042 found an instance of

D-042 fixed the instance: check the parameter exists before writing it. The verdict
ruled the generalisation, and this is it. **Every reform write now goes through
`impots.parameters.update_existing`**, which resolves the target against the tree *as
the year's formula sees it* and refuses otherwise. Creating a parameter is still
possible — through `create_parameter`, which has a different name so that choosing it
shows up in a diff. Nothing calls it yet.

`ParameterWriteError` subclasses `ValueError` deliberately: the API maps those to 422,
and asking for a knob the requested year does not have is the caller's mistake. A knob
aimed at the 2026 allègements now returns 422 with the parameter path in the message
rather than 500.

The scale brackets go through `update_bracket`. Indexed rather than named, they cannot
be conjured the way a named child can — but the count of *active* brackets is smaller
than the list at most dates, so an index can be in range and still name a bracket the
year ignores. And routing every write through one module is what turns "no direct
writes" from a habit into a property a test asserts.

### The audit, and it found the pattern twice

The verdict asked for every `verify_*` to be checked once for the shared-write-path
shape — a check comparing against whatever the write path now contains rather than
against an independently constructed expectation — and for the result to be recorded
either way. It was found twice, both latent, both now closed.

* **`verify_allegements`** enumerated which plafonds to check from the **reformed**
  tree. If the write path had created a child, verify would have found it and compared
  it against itself. The enumeration now comes from the baseline, and a plafond present
  in current law but missing from the reformed system is reported as a reform that
  *deleted* a ceiling rather than moved it — a failure mode the old shape could not
  express.
* **`verify_scales`** read the CEBGE smoothing width out of the **reformed** tree and
  then derived its expected bound as `seuil + largeur`. No knob writes that width
  today, so it was latent; had one ever been added, the expectation would have moved
  with the thing it was checking. It now reads from the baseline.

`verify_bareme` was clean: it compares the evaluated scale bracket by bracket against
the user's spec, which is as independent a source as exists here.

The general form is worth stating because it outlives these two: **a verification is
only as good as its causal independence from the thing it verifies.** A read-back that
shares a write path can only tell you the write happened, never that it landed where
the formula looks.

## D-045 — Double entry, and the first version of it that did not work
Date: 2026-09-03 · Status: accepted · Evidence: the 17.7 bn bug, re-expressed as a test

Every reform run now checks its own headline against the instruments that moved. The
household side compares `reform_cost` with the figure reconstituted from the reported
receipts, transfers and the employer-contribution delta; the firm side compares it
with the sum of the five firm instruments, where `prelevements_entreprise` is an
OpenFisca formula and the components are added up separately.

**The first version of this guard did not work, and how it failed is worth more than
the guard.** It asserted the sectors balance — `households + firms + state = 0` — with
the state's side written in terms of the firm's. Removing the firm term moved both
sides together and the identity balanced at zero. Tested against the exact bug it was
written for, it passed. That is D-044's shape appearing *inside the guard meant to
enforce D-044*: a check is only as good as its independence from the thing it checks,
and writing one side in terms of the other is the easiest way to lose that without
noticing.

The bug was never an accounting *inconsistency*. The accounting was consistent;
`reform_cost` reported one sector out of two. So the thing to check is not that the
sectors balance — they will, being derived from each other — but that **the headline
agrees with the sum of the instruments**, assembled by the guard and computed
elsewhere. Re-expressed, the 17.7 bn reform under the pre-D-039 cost now breaches by
100 %, and the guard is surgical: an income-tax reform has no employer term, so the
old household-only cost was always right for it and still passes.

**The tolerance is a measurement, not a preference.** `revenu_disponible` runs over the
whole benefits cascade, which is wider than the instruments this runner reports
individually: a 10.4 bn CSG rise pulls 0.066 % of itself through the complément
familial, the ARS and minima that have no row. The floor is 0.1 % — an order of
magnitude below the failure it guards, and the residual is named `unexplained` rather
than "residual" so the number means something when read.

**And the guard caught a regression I had just introduced.** Wiring it revealed that
`cost` was being computed before the deltas dictionary was populated, so `reform_cost`
came back `None` for every reform without an employer term — the household reforms,
which is to say most of them. It had been that way for two commits and no existing
test noticed, because they assert on `deltas` rather than on the cost. The double
entry found it on its first run.

## D-046 — The narrow-band flag: constants, and why they are where they are
Date: 2026-09-03 · Status: accepted · Evidence: the two backtest cases

The backtest suite measured the failure; the runtime now points at it whenever a user
walks into it. Per reform, the share of what it moves that comes from households close
to one of **its own** thresholds. Above a declared share, the API and UI carry the
D-015 caveat. It adjusts nothing.

**Window: ±15 % of the threshold.** Set from the instrument that motivated the flag,
not from taste: the 2025 step moved the maladie ceiling from about 2.5 to 2.25 SMIC,
an 11 % move, and a window narrower than the move itself would miss the households the
measure acts on. Wide enough to hold a real cliff step, narrow enough that a reform
touching the whole distribution does not sit inside it everywhere.

**Share: 50 %.** Below it a reform is broad-based and its total does not hinge on the
density anywhere in particular; above it the total is mostly one band's population.

**Measured per threshold family, against the income that family is defined on** — the
barème and décote on taxable salary, the plafonds on gross wage — and the largest
share wins. Comparing a SMIC multiple against taxable income would put every threshold
in the wrong place on the axis.

**And the wage family is measured per EARNER, not per household**, which is the
difference between a flag that works and one that happens to work. A plafond is an
individual threshold: a two-earner household at 1.5 SMIC each has a household gross of
3 SMIC and sits inside a 3.3-SMIC window while neither earner is near it. At household
level the cliff case scored **56 %** against a 50 % bar — the right side of the line,
for the wrong reason and by six points. Per earner it scores **78 %**.

Measured on the real population, against a 50 % bar:

| reform | share | flagged |
|---|---:|---|
| allègements 2025 step (two cliffs) | 78.1 % | **yes** |
| barème indexation LFI 2024 | 25.0 % | no |
| réduction générale 1.6 → 2.0 SMIC | 19.9 % | no |
| top rate 45 → 50 % | 0.1 % | no |

The third row is the one that shows the flag is measuring the right thing rather than
just "is this an employer knob". Extending the réduction générale is an allègement
reform and does *not* flag — because the réduction is degressive, so its yield is
spread across everyone below the ceiling rather than concentrated between two of them.
Cliffs flag; slopes do not.

A rate change with no threshold of its own — a CSG rate, the décote rate — contributes
nothing and correctly leaves the share at zero: it moves everyone it touches
proportionally and cannot concentrate a yield anywhere.

## D-047 — Tiering the suite: 23 minutes to 1 min 45, with nothing removed
Date: 2026-09-03 · Status: accepted · Evidence: measured before and after

The verdict's reasoning is the operative part: *local test pain is how green suites
rot.* Nothing here is deleted or weakened — the work is measurement, re-tiering and a
mark.

**Two real speedups first, both from measuring rather than marking.**

*A chiffrage case runs at the tier its instruments need.* Measured per case: the 2025
allègements step gives **+4.146 bn on both tiers**, in 19 s light against 63 s full,
because its cost is entirely employer-side and `salaire_super_brut` exists in the
light tier. The barème indexation gives **zero** on the light tier — not an
approximation, zero, because the light tier does not compute `revenu_disponible` at
all. So the tier is a per-case field, `full` by default, and the light case is light
on evidence rather than on hope.

*A test was running each case twice.* The pinned-miss assertion called `run_case`
once for the residual and again for the pass check — two full population runs per
case, for one measurement. Fixed. Those two changes alone took the chiffrage suite
from 470 s to 166 s.

**Then the mark.** Profiling showed fourteen tests at about 65 s each, every one a
20 000-household pass. They carry `slow`; `pyproject.toml` sets the default run to
`-m 'not slow'`.

| | before | after |
|---|---:|---:|
| default gate | 23 min 29 | **1 min 44** |
| full pass | 23 min 29 | 14 min 40 |
| tests | 396 | 423 |

In `test_api.py` the two facts are composed into one decorator: a test that needs the
population is also a test the gate skips, and remembering the second mark separately
is how a fast gate quietly stops being fast.

**Where the full pass actually runs, said plainly.** CI now uses `-m ""`, but those
tests **skip there anyway** — CI has no built population, by design, since the EEC
file is 11.7 MB and downloading it is not CI's job. So the full pass genuinely runs
only on a machine that has the data, and `-m ""` in CI is what will pick them up the
day that changes rather than silently skipping a suite everyone believes is running.
The README carries the three commands and the same caveat.

## D-048 — The input-output table is not non-negative, and the spec said it would be

`PHASE4_SPEC.md` §3 asks the M0 gate to assert "the import matrix present and
non-negative". The import matrix is present. It is not non-negative, and the assertion
fails on correct data.

One cell, in the 2023 semi-definitive vintage, in both matrices:

```
KZ -> LZ   domestic  -23 893.2 M EUR      imported  -309.4 M EUR
```

Financial services against the real-estate branch: the SIFIM adjustment, whose interest
component on household housing loans is booked as household final consumption rather
than as intermediate consumption of real estate. Published data — the product balance
closes on it to 0.000 M€ — and absent from the 2022 definitive vintage, so a feature of
the semi-definitive publication rather than a permanent one.

**The cell is kept as published.** Clamping it to zero would break a balance identity
that currently closes exactly, in exchange for a property nothing downstream requires.
Reality wins over the spec, on the record, which is the standing rule.

What replaced the assertion is the set of properties propagation actually rests on,
each measured rather than assumed:

* negatives few enough to enumerate and name — ceiling 5, since a scattering would mean
  a misread sheet rather than an accounting convention;
* per-cell import shares in [0, 1] — 0.0000 to 0.9918;
* per-branch import shares in [0, 1] — 0.000 to 0.725;
* every output multiplier at least unity — 1.000 (TZ) to 2.156 (KZ).

That last one is the substantive replacement. Non-negativity was never the thing worth
having; "a unit of final demand raises total output, for every branch" is, and it
survives the negative cell. Measured consequences: one negative technical coefficient
(−0.0586), two negative entries in the Leontief inverse (largest 0.0883), ρ = 0.4591,
and zeroing the cell would move branch multipliers by at most 0.130.

**The IO layer may never assume non-negativity of this table.**

## D-049 — The gate found two silent misreads, which is the argument for gates

Neither would have raised. Both would have biased every number the macro layer produced,
and the M0 discipline — the gate written *before* the propagation code — is the only
reason either was found.

**Both totals read the same column.** "Total des emplois" is a substring of "Total des
emplois finals", which sits to its left. A substring match returned the same column for
both; the two totals came back identical at 3 245.8 bn; and the balance identity closed
**anyway**, because it was comparing a column against itself. This is the same failure
mode as D-045's first double-entry guard: a check that shares a path with the thing it
checks will confirm itself. Found by reading the numbers, not by the code failing.

**Final consumption meant households alone.** Four columns sit under one merged header
— Ménages / APU / ISBLSM / TOTAL — with the institutional sector on the code row
beneath. Matching the header takes its leftmost column: 1 158.7 bn where the total is
1 888.2 bn, a 730 bn omission. The aggregate balance stayed green throughout, because
it rests on a separate published column that is correct either way. It surfaced only
from adding the components up by hand.

The gate now asserts each total against its own components, which is the check that can
catch a wrong column where a headline identity structurally cannot. All four close to
0.000 M€. The reader raises on a missing sub-column rather than falling back to the
header — the fallback *is* the bug.

The institutional split is kept rather than collapsed into a total: a public-spending
shock and a household-transfer shock enter through different columns, and the MPC that
applies to one does not apply to the other.

Two smaller ones, same character: the employment nomenclature is hierarchical, so three
branches carry an A17 code with a different letter and suffix-matching left ten
unmatched — a zero-fill would have made ten branches contribute no jobs to any shock,
so it raises instead. And the year headers are strings, so an `isinstance(..., int)`
lookup found no years and reported it as a missing year.

Recorded because the pattern now has four instances (D-045, D-044's read-back, and both
above): **a verification that shares a path with what it verifies is not a
verification.** Every check added here compares two independently-published quantities.

## D-050 — Owner decisions of 2026-09-03

Two, taken by Max and recorded here so they stop being re-litigated:

* **Deployment stays private.** No public instance. The AGPL licence and the public
  repository stand; what does not follow is a hosted service, which would put fidelity
  labels in front of readers who have not read the caveats.
* **The Phase 4 fork is the macro fan** — not the reform-authoring UI, not the
  historical backtest suite. The macro layer is where the project's remaining
  credibility risk is concentrated, so it gets built under the tightest guardrails
  rather than deferred.

The Phase 4 exclusions stand and are refusals, not deferrals: no forecast, no
DSGE/CGE/HANK/ABM under any framing, no monetary policy, no debt dynamics beyond
arithmetic, no horizon past three years, and never a point estimate.

## D-051 — Both multiplier seeds were wrong, in the way summaries are wrong

`PHASE4_SPEC.md` §2 proposed "0.2–0.6 tax-side, 0.5–1.2 spending-side, 1.3–2.5 in
slack", and flagged them as reviewer-compiled and suspect by precedent. Measured against
Mésange (INSEE/DG Trésor G2017/04, section 4):

* **tax-side 0.2–0.6 is a year-one range wearing no horizon.** The tax variants run
  0.20–0.51 at one year and 0.72–0.90 at three. Applied at three years, the seed
  understates by about a third.
* **spending-side 0.5–1.2 excludes its own most important case.** Public investment is
  1.31 at one year and 1.38 at two, above the ceiling.
* **1.3–2.5 in slack has no source.** Mésange is linear and has no cycle state.

Neither is a fabrication; both are the kind of half-remembered summary that stops being
true the moment a horizon is attached. `eti_all` died at 2.5× its true value by the same
mechanism, which is why these were checked rather than loaded. **Fourth phase running,
same finding: a compiled range is a hypothesis about a document, not a reading of one.**

The replacement is not a wider band but a **profile**: eight instruments × six horizons,
parsed from the PDF, with the employment response attached to each. And it replaces the
spec's "Okun-style" employment row outright — at three years a point of GDP through
employer contributions yields 290k jobs against 107k through generic public spending,
so an aggregate employment-output elasticity would be wrong about one of them by a
factor near three.

**No multiplier value lives in a YAML file.** Forty-eight figures retyped into
configuration is precisely the transcription D-026 forbids, so `multipliers.yaml`
declares `from_source_table: gdp` and `impots.macro.mesange` parses the document.
`test_the_multiplier_yaml_contains_no_multipliers` enforces that there is nothing to
drift.

Two conventions are assumptions and are labelled as such on every row that carries them:
the sign flip that brings contractionary variants into one convention rests on the
model's linearity, and the identifying shock is exactly one point of GDP, so a larger
reform extrapolates the model rather than reading it.

## D-052 — Two rows die, and the second one takes a feature with it

**`multiplier_slack_state`.** No source. Mésange cannot answer it, and the international
literature is openly split — Auerbach and Gorodnichenko reach 2.5 in recession, Ramey
and Zubairy find multipliers below unity irrespective of slack. Importing a number into
that disagreement would be picking a side by default of formatting. Nothing is lost:
§1 already required cycle state to be a **scenario, user-visible, never estimated**. The
fan does not draw on this dimension; it computes at a stated state and shows which.

**`mpc_by_income_position`.** The French evidence measures the wrong object. Arrondel,
Lamarche and Savignac (HFCS) estimate the propensity to consume **wealth**, varying
along the **wealth** distribution — about 0.5 centime per euro on average, 11 centimes
for financial wealth below the median, zero in the top decile. B1 needs consumption out
of an increment of **income**, by **income** decile. Loading one for the other repeats
exactly what killed `eti_labour_income_low_earners`: two different objects summed into
one channel because they share a name. **Consequence, accepted: B1 does not
differentiate the consumption impulse by decile.** It applies one bridge and states it,
which §1 explicitly provided for.

**`revenue_elasticity_by_cycle_state`** dies for the opposite reason — the source
forbids it. HCFP tests cycle dependence three ways (output gap, nominal growth, real
growth) and finds none significant; the one detectable regime is "à la limite de la
significativité" and "pourrait même être rejetée". Varying this row with the cycle would
promote noise to a parameter.

**`multiplier_confidence_band`** is the one that hurts. Mésange publishes no interval,
and its own sensitivity analysis is **degenerate at one year** — 1.31 for public
investment under every one of four hypothesis sets, −0.32 for VAT under all of them. A
band drawn from it would be an artefact of a model that is deterministic in the short
run by construction. The credible band is cross-model dispersion, which needs a
meta-analysis this repo does not have on disk. **B3 therefore has no sourced width, and
that is the open blocker for M3** — recorded here rather than papered over with a
convention, because a fan whose width is invented is the one output of this project that
would be actively misleading.

## D-053 — The macro store loads nothing, and that is the correct state

Every M1 row carries `verdict: null`, so `impots.macro.store.load()` raises and no macro
feature can produce a number.

The values were located, downloaded, manifested and parsed from the primary documents by
tested code — D-026's first half. Its second half is that the figures are then
*adversarially verified by someone other than whoever computed them*, and no independent
pass has run. Reading my own parsed tables back off the screen is exactly the read-back
verification D-044 recorded as a blind spot: a check sharing a path with the thing it
checks confirms itself, and this project has now measured that failure four times.

So the store refuses, `strict=False` reports what is missing and why, and the five dead
rows carry their reasons in `Store.removed` so a feature can say "no usable evidence,
because …" rather than quietly having fewer inputs.

## D-054 — The fan's width, and a banner line that turned out to be a measurement

D-052 recorded `multiplier_confidence_band` as dead and named it the blocker for M3.
It is resolved, and the resolution changed the architecture rather than filling a hole.

Two open-access IMK meta-regressions are now on disk, manifested and parsed by
`impots.macro.imk`: Gechert (2013), 104 studies and 1 069 reported multipliers, and
Gechert and Rannenberg (2014), 98 studies and 1 882 observations broken out by cycle
regime.

**The centre and the width come from different places, and neither could supply the
other.** Mésange gives a French, official, dated value per instrument per horizon and no
interval. IMK gives dispersion across studies and no horizon. Composed in **relative**
terms — a coefficient of variation applied around the Mésange centre — they combine;
composed in levels they would not, since they measure different objects.

**The centres cross-validate, which is the only external check the Mésange parse has.**
Year-one income tax 0.41 against TAX means of 0.44 and 0.54; public investment 1.31
against INVEST 1.22 and 1.36; generic public spending 0.78 against SPEND 0.90 and 1.00.
An official French model and two international meta-analyses land in the same place by
unrelated routes.

**The L4 banner's copy is a measured quantity, not a rhetorical one.** "L'éventail des
estimations crédibles pour un même choc varie d'un facteur 3 à 5": the downturn mean is
1.37 against 0.39 in an upturn, a ratio of **3.5**. The sentence was specified before
anyone checked; it survives checking.

**`multiplier_slack_state` is superseded rather than revived.** The replacement is not an
estimator: §1 requires cycle state to be a user-visible scenario, never drawn, and the
new row supplies the sourced *size of the gap* between two displayed scenarios. It also
inherits a restriction the paper states explicitly — the regime effect appears on the
**spending** side, and tax multipliers are not regime-sensitive, so shifting a tax
instrument with it would contradict the source that justifies it.

The dominant caveat rides on every row: these dispersions are across studies with
different countries, horizons and identification strategies. Gechert's own conclusion is
that reported multipliers vary with study design, so this is **not** the sampling error
of France's multiplier at a given horizon, and the resulting fan is wider than the
genuine uncertainty about a French reform. Conservative, and a choice.

Both rows load with `verdict: null` like the rest. D-053 is unchanged: the store still
refuses everything.

## D-055 — The verification cost ten agents and paid for itself twice over

Ten adversarial verifiers over the five M1 rows, two lenses each, ref `wf_8caa3e5e-1e6`.
**113 findings. One WRONG, nine SCOPE_PROBLEM.**

**No transcription error anywhere.** All 48 Mésange values, all 28 IMK columns, every
page reference: exact, including the CSG/IR trap where both read 0.41 in year one.
D-026's first half — parse from the primary file with tested code — did its job
completely. Every single defect was in what the numbers were said to MEAN.

That is worth stating plainly, because it is the fourth phase in a row where the same
split appears: **the arithmetic is fine and the scope is wrong.** Phase 1 gave six scope
problems out of six statistics; Phase 2's firm-data pass returned fifteen; Phase 3's
`eti_all` was killed by a scope error, not a typo. A verification that only re-checks
digits would have passed everything here.

**The most consequential finding is specific to this repository.** Mésange's four
labour-tax variants are NON-TARGETED — a uniform 3.7-point cut landing 80 % on qualified
workers — and the document publishes a targeted counterpart at encadré 14, concentrated
on 1 to 1.6 SMIC, landing 44 % on unqualified workers whose labour demand is more
elastic. Phase 3's entire allègements-généraux work moves exactly those knobs, and
`responds_to_knobs: [cotisations_*]` would have handed every one of them the uniform
multiplier: **290 000 jobs at three years instead of 403 000, an understatement of
39 %**. The ninth variant is now parsed and `shocks.targets_low_wages` routes to it from
the reform's knobs, since the deltas cannot tell the two apart.

Four more that changed behaviour rather than wording: the VAT shock is **1.18 point of
GDP ex ante** for one point net (the state pays about 15 % of its own VAT), so a reform
costed gross took a multiplier overstated by 18 %; only the fiscal variants are ex ante
at all, the two spending ones being shocks in volume; employment is in **full-time
equivalents**, not persons, which now coexists in this layer with `io_layer`'s
person-counts and must never be added to them; and the long horizons are determined by a
specification choice rather than measured — employer contributions give 1.73 at LT under
wage setting and 0.25 under a Phillips curve — so `usable_horizons` stops at three years,
which is where §0 had independently already refused to go.

## D-056 — I violated D-026 twice, in the file that proclaims it

The rule this project cares most about is that calibration inputs never pass through
prose. I broke it twice in one sitting, the same way both times, and the verifiers found
both.

* `revenue_elasticity.yaml`'s `note` carried "1,5 en 2017 et 2022, 0,4 en 2023". **None
  of those figures is in the cited document.** It prints 0.84 (2020), 1.15 (2021), 1.48
  (2022), and cannot print a 2023 value at all, being dated February 2023. They came
  from a search-engine summary.
* `dispersion.yaml`'s `quote:` field set a **paraphrase in quotation position**. Gechert
  writes "Reported multipliers vary with study-design, whose influence should be laid
  open when drawing policy conclusions". The file printed a search result's rewording.

The pattern is exact and worth naming, because it is not the failure D-026 was written
to prevent and the existing tests were blind to it. **Values were computed from primary
files by tested code, while the prose around them — quotes, notes, characterisations —
came from whatever was to hand.** D-026 was honoured in the half that had a test and
violated in the half that did not. `test_the_multiplier_yaml_contains_no_multipliers`
proves no number is transcribed; nothing proved the sentences were read.

`test_every_quote_is_verbatim_in_its_source` now compares every `quote:` field to its
PDF letter by letter, surviving hyphenation and ligatures but not paraphrase. The rule
extends: **a `quote:` is a quotation or it is not a `quote:`**, and a `note:` may not
carry a figure the cited document does not print.

## D-057 — Correction to D-054: the banner's factor is not a measurement

D-054 said the L4 banner's "l'éventail des estimations crédibles pour un même choc varie
d'un facteur 3 à 5" turned out to be a measured quantity, on the strength of
RLO/RUP = 1.37/0.39 = 3.5. **That was wrong**, and the reasoning was wrong in three ways
at once.

The 3.5 is a ratio of two RAW subsample means. The same paper's controlled estimate
contradicts it: the meta-regression's regime effect is **additive** — "spending
multipliers to significantly increase by about 0.6 to 0.8 units during a downturn" —
with RLO at +0.769 (0.143, significant at 1 %) and **RUP at −0.049 (0.097), not
significant**. There is therefore no measured upswing multiplier to divide by. No
controlled reading reproduces 3.5 (2.52 and 2.08 depending on specification), the
authors write that the reference multiplier "should not be interpreted as the true
multiplier since it depends on the reference specification", and **nothing in either
paper yields 5**.

The banner must describe dispersion qualitatively. The honest statement available is
that a downturn adds something like 0.6 to 0.8 to a SPENDING multiplier, which is not a
factor, does not apply to the tax instruments this repository actually simulates, and
therefore leaves `multiplier_regime_shift` loaded, sourced, and with an empty
`responds_to_knobs` — a row nothing may currently use.

The general lesson is the one D-026 keeps teaching: a ratio computed from two published
numbers is a NEW estimate, and inherits none of their authority.

## D-058 — A second double count, one level up: leakage is already in the multiplier

`PHASE4_SPEC.md` §1 asks the input-output layer to supply "the import-leakage correction
to the impulse, **which scales the aggregate impulse handed to B3**". Following that
instruction with a Mésange multiplier would have subtracted France's import propensity
twice, removing roughly a quarter of every effect — silently, and plausibly enough that
nothing downstream would have looked wrong.

Mésange's multipliers are already net of import crowding-out. The document says so where
it explains the first-year public-investment figure: « l'effet multiplicateur l'emporte
nettement sur **l'éviction par les importations**, avec un accroissement de l'activité de
1,31 point de PIB ». Every variant table carries an Importations row, and the employer-
contribution commentary discusses the trade balance deteriorating through import
dynamism. The leakage is inside the model.

This is the same shape as the Type I rule one level down, and the resolution is the
same: **computed, reported, and not applied.** The measurement is real and §1 was right
to demand it rather than let it be assumed — 27.4 % for a consumption-shaped impulse,
33.6 % for capital formation, both channels counted. It does its legitimate work inside
B2, whose output shares already exclude the directly imported part of final demand. The
aggregate path takes the impulse whole.

The spec's instruction was safe for the multiplier it imagined — a generic literature
range that might not embed French import behaviour — and unsafe for the one M1 actually
found. That is the third time in this phase that a rule written against one design has
had to be re-derived against the design that survived contact with the sources.

`test_leakage_is_reported_but_not_applied` asserts the median equals the central
multiplier times the undiminished impulse, and separately asserts that the
leakage-applied figure differs by more than 20 % — a kill test that would be vacuous
without the second half.

## D-059 — What the fan can and cannot say, after the verification took two of its dimensions

§1 specifies a Monte Carlo over four dimensions. Two of them no longer exist, and the
fan reports their absence rather than their zero.

**No revenue-feedback loop.** The elasticity row returned WRONG (D-055), so Δdéficit
stops at mechanical plus behavioural and this layer does not close the public balance.
§1's closing identity is not implemented because its parameter is not sourced.

**No usable cycle scenario.** The regime magnitude is sourced, and it is established on
the SPENDING side: Gechert and Rannenberg's controlled coefficient is +0.769 for a
downswing while the upswing coefficient is −0.049 and not significant. Every instrument
this repository simulates is fiscal. Applying the shift to them would contradict the
paper that supplies it, so `multiplier_regime_shift` loads with an empty
`responds_to_knobs` and the toggle refuses itself **with its reason printed** rather than
contributing a silent zero. The decomposition therefore reports 100 % parameter
uncertainty — a fact about the evidence, not a property of the method, and the
assumptions strip says which.

**What remains** is instrument-specific multipliers and employment at one, two and three
years, with a width from cross-study dispersion whose scope problem rides on every
number: those dispersions pool countries, horizons and identification strategies, and are
not the sampling error of France's multiplier at a horizon. The resulting fan is wide —
a five-billion CSG cut gives a first-year GDP band from −2.4 to +6.7 bn — and that width
is the honest reading of the literature rather than a defect of the arithmetic.

Two smaller decisions inside it. The triangular draw is scaled so its standard deviation
equals the published one (half-width = sd·√6); the SHAPE is a stated convention, since
both papers report the distributions as non-normal and multimodal and nothing available
characterises them further. And employment carries the multiplier's uncertainty
**proportionally**, because no source gives employment a dispersion of its own and within
a variant jobs and output move together at the model's own calibration — an assumption,
and the only one available.

The L4 banner ships without a numeric factor, per D-057.

## D-060 — The CICE gate passes, and the source it rests on disavows the use

The acceptance gate for the macro layer: the employment fan must contain the range
published evaluations span for the CICE. It does, on both bracketing variants, **and
the median lands inside the range too** — which is the half that makes containment mean
anything, since a wide enough fan contains every estimate ever published.

| | p10 | median | p90 | contains 100–400k | median inside |
|---|---:|---:|---:|:---:|:---:|
| uniform variant | −39k | **239k** | 517k | yes | yes |
| targeted variant | −35k | **332k** | 699k | yes | yes |

Nothing was tuned. The parameters are exactly what M1's verification left standing, and
the gate was run once.

**The band is sourced to methods, not scenarios.** France Stratégie's 2020 synthesis:
"L'effet total reste estimé à 100 000 emplois environ" (TEPP, micro-econometric, on firm
data) and 400 000 for OFCE's macro-sectoral estimate once intersectoral feedback is
injected into a macro model — the report notes the upper figure looks high. A third
reading, 160 000, is **net of the measure's financing** and is deliberately excluded:
Mésange's variants are explicitly unfinanced, so the fan produces a gross figure and
comparing it to a net one would compare two different quantities.

**Two variants, because neither is the CICE.** The CICE targeted wages below 2.5 SMIC;
Mésange publishes a uniform variant covering all wages and a targeted one concentrated
between 1 and 1.6 SMIC. The truth is bracketed, so the episode runs both and requires
both to pass rather than picking whichever agrees.

**The source disavows this use, and the episode file says so.** Mésange's note 79: the
targeted variant's « impact ne permet pas d'évaluer l'effet de mesures d'allègement de
cotisations spécifiquement mises en place au cours des dernières années » — which is the
CICE exactly. Its conclusion: the results « n'ont cependant pas vocation à être
directement transposés à l'évaluation des politiques économiques passées » — which is a
backtest exactly. So this episode is a **sanity check on the machinery's order of
magnitude, not a validation of the parameters**, and it may not later be cited as
evidence that the multipliers are right. Recording that in the file is what stops the
citation happening.

The p10 is negative in both rows. That is the honest consequence of a width taken from
cross-study dispersion whose standard deviation exceeds the central tax multiplier: the
literature does contain reported multipliers below zero. It is not a claim that the CICE
plausibly destroyed jobs; it is a statement about how much the published estimates
disagree.

The episode's quotes are checked verbatim against the report by the same guard the
parameter store now carries (D-056). A validation line taken from a search summary would
be worse than a parameter taken from one, since it decides whether the layer ships.

## D-061 — The fan on screen, and the three refusals built into the renderer

M5 puts L4 in front of a reader. Three properties are enforced by tests rather than by
intention, because each is one careless edit away from being lost.

**It never renders without its assumptions strip.** §4 lists what must accompany the
quantiles — cycle state, design, leakage, horizon, vintage, grade — so the strip is
built in the same expression as the chart, and `test_the_strip_is_not_hidden_behind_a_disclosure`
asserts it precedes any `<details>`. A strip inside a disclosure is a strip the reader
can leave closed.

**It shows what it does not describe.** Most reforms this repository can express have no
macro path: transfers and corporate instruments have no published multiplier. So the
covered share is on screen, flagged when it falls below 90 %, and every uncovered
instrument is listed with the reason it is missing. An unavailable fan is a block with a
reason, never an error and never an empty space.

**It never turns a fan into a number.** There is no mean in the renderer, and a test
asserts the word does not appear. p10, median, p90, on a scale shared across horizons and
always including zero — a per-row scale would make a widening band look stable.

Visually L4 is quieter than L3, which is quieter than the mechanical figure. That
ordering is the evidence ordering: arithmetic, then a band with elasticities behind it,
then an order of magnitude drawn from a literature that disagrees with itself. The
hatched left rule on the L4 block is doing that work.

The banner ships without a numeric factor (D-057), the employment unit is named on screen
as full-time equivalents so it cannot be added to the person-counts the input-output
layer reports, and the leakage line says "calculée, non appliquée" with its reason —
D-058 made visible rather than buried in a decision file.

**The UI had no tests at all before this.** `tests/test_ui.py` adds twenty-five static
checks on the single file, including regressions pinning the mechanical and behavioural
presentation that §4 requires to be unchanged, and one asserting the file stays
buildless and free of external scripts.

## D-062 — The prestations knobs, and the two things the double-entry guard found

`WHAT_NOW.md` B1: the tool could reform taxes but not transfers, which meant it could
price an austerity package's revenue side and say nothing about its spending side.
Thirteen knobs now cover RSA, the prime d'activité, family allowances and the flat
housing cut. Every path was **read out of the tree**, and every knob is verified by
running a household through the engine and looking at the benefit that came out.

**That verification method is the point, because a read-back would have passed a defect.**
`af_cond_ress.plafond_tranche_1` and `plafond_tranche_2` exist, accept a write, and are
never read by the AF formula: they are published figures already including two
children's majoration (62 474 + 2 × 6 246 = 74 966), while the formula builds its own
ceiling from the `_base` value plus one majoration per child. A knob aimed at them
writes successfully, warns nothing, and moves nothing. This is D-044's failure in a new
shape — not a created child this time, but a *derived* parameter — and only an outcome
check could see it. The knobs point at `_base`, and the defect is kept as a regression.

Two more findings from measuring rather than assuming. The AF modulation compares
against **base ressources** — net income, two years back — not gross salary, so a
ceiling set near gross income does nothing: a test written against gross would have
passed for the wrong reason. And `rsa.rsa_m.pente` exists as a child with a **null value
at this instant**, so the RSA taper is not parameterised and is deliberately not a knob.

**The two ceilings need a guard.** Lifting tranche 1 alone above an untouched tranche 2
puts a household in neither band: a 150 k family came out at 2 214 € where the full rate
is 1 771. A validator refuses an inverted pair, checking a one-sided move against the
other ceiling's legal value, and it ships with both halves of its kill test.

### What the double-entry guard caught, which is why it exists

A national RSA reform missed by **0.99 %** — ten times tolerance. The cause: raising the
RSA base brings households into **eligibility**, and eligibility carries the prime de
Noël (`aefa`, a flat 152.45 €) which sits inside `revenu_disponible` and was in none of
the itemised transfers. 36 M€ on 3.66 bn.

With that fixed, a national AF reform missed by **0.50 %** in the other direction —
exactly the CRDS rate. `revenu_disponible` sums `af_nettes_crds`, so it carries benefits
**net**, while the population reports them **gross**. The benefit-side CRDS
(`crds_pfam`, `crds_logement`, `crds_mini`) is now itemised on the *transfer* side,
where it nets the benefit down to what the state actually bears. The AF reform now
reconstitutes to 0.0000 %.

Neither was found by reading code. Both were found by a guard whose whole job is to
notice that the headline and the instruments disagree, and both would have quietly
biased every prestation costing the tool will ever produce.

## D-063 — B1 does not wake the regime row, and the reason is worth keeping

`WHAT_NOW.md` argued that prestations knobs would constitute a **spending instrument**
and thereby wake `multiplier_regime_shift`, which has been loaded and unusable since
M1. Measured: they do not. A prestation reform still returns *no macro path at all*.

The expectation conflated two different blockers. The regime row is dormant because the
effect it carries is established on the spending side while every instrument this
repository simulates is fiscal — but the thing that would make a transfer reform usable
is a **transfer multiplier**, and there is none. Mésange publishes no transfer variant;
its generic public-spending variant is a composite that is 46 % cash benefits but whose
components the document says transmit at different speeds; and borrowing it would
overstate by two to three, since IMK puts transfers at 0.39 and 0.54 against 1.01 and
0.90 for spending (D-052).

So adding a spending *instrument* does not supply a spending *multiplier*. The macro
layer correctly reports "aucun instrument de cette réforme n'a de multiplicateur
publié", and `multiplier_regime_shift` stays loaded, sourced and unused.

This is the sixth expectation in this project to meet the primary sources and lose, and
the pattern is stable enough to state: **a document's reasoning about what a change will
unlock is a hypothesis about the sources, not a reading of them.** The knobs are still
worth having for the other two reasons B1 gave — half the fiscal debate, and the EMTR
machinery now has `ppa_pente`, the single parameter that most directly sets the marginal
rate a working household on the prime d'activité faces.

## D-064 — The IR niches, and a phantom parameter tree that would have passed a read-back

`WHAT_NOW.md` B3: the 19.53 bn of réductions and crédits was the stated reason the
model's income tax is validated against the barème (98.84 bn) rather than net receipts.
The formulas were never missing — openfisca carries all of them — but nothing could
supply a base, so `reductions` and `credits_impot` were zero for every household with no
way to make them otherwise.

Seven declaration cases are now wire-format fields and thirteen knobs move their rates
and ceilings. **No rate was read off a table**: each was measured by running a household
through the engine, then checked against the parameter the tree prints. Agreement
between the two is the evidence, and this increment is exactly why.

**`impot_revenu.credits_impots.aide_a_domicile` is a complete phantom tree.** It
resolves non-null at 2024-01-01, documents itself as «CGI - art 199. sexdecies» — the
article that governs the home-help credit — and carries the *same value at every leaf*
as the live node: rate 0.5, invalidity ceiling 20 000, increment 1 500, first-year
ceilings 15 000 and 18 000. No formula in openfisca-france reads it. And
`aide_a_domicile` is the more natural name for "home help" than the live
`emploi_salarie_domicile`, so it is precisely what a careful implementer reaches for.

A read-back could not have caught it, because the dead tree answers the same values as
the live one. That makes three shapes of one failure: `update()` silently creating an
absent child (D-044), published-but-derived plafonds the AF formula never consults
(D-062), and now a duplicate tree for the same article. **Resolving non-null is not the
property that matters; being read is.**
`test_every_knob_aims_at_a_node_some_formula_reads` now requires every knob's node to
appear somewhere in openfisca's model source, and its kill test asserts the phantom stays
invisible so the rule cannot pass vacuously.

One measured fact decided the wire format. The childcare ceiling is **per child**: the
same 6 000 € yields 1 750 € on one child and 3 000 € split across two. A single total
divided equally would have overstated the credit by 71 % for the first household, so
`frais_garde_par_enfant` is a list and the UI carries the even-split convenience with its
own label.

## D-065 — The engine applies no eligibility test, and my docstring said it did

Measured: a household with a fifteen-year-old receives the childcare credit, and so does
a household with **no children at all**. These cases are boxes on the 2042 and openfisca
trusts the declarant exactly as the paper form does — eligibility is the administration's
job, not the formula's. That is correct behaviour for a tax engine.

It is wrong for a calculator someone uses to decide something, and the first version of
`Niches.frais_garde_par_enfant`'s docstring asserted the opposite: "the engine decides
eligibility from the children's ages". It does not. The claim was written in the same
sitting that built the field, and an adversarial pass caught it by testing the premise
rather than reading the sentence.

`situations.assert_niche_eligibility` now refuses more childcare amounts than there are
children under six at 1 January, more union dues than adults, and more school children
than dependants, raising `ValueError` so the API answers 422. Its kill test proves the
premise: it injects the case past the wire format and shows openfisca computing a
childcare credit for a childless foyer without complaint.

The age boundary carries its own honest limit: only the birth *year* is available, so a
child born on 1 January of `year - 6` is treated as eligible when they are in fact
exactly six. One day a year, stated in the constant's comment rather than rounded away.

## D-066 — The confident zero, refused

No household in the synthetic population declares any niche base, so `reductions` and
`credits_impot` total exactly 0.0000 bn. Cut the home-help credit from 50 % to 30 % and
the reform costs **exactly 0 €**.

That is the most dangerous output this project could produce. A reader told "0 €"
concludes the credit is worthless; the truth is that the population has no home-help
spending for the rate to apply to, and the omission is worth 19.53 bn nationally.

`guards.niche_blind_spot` detects a reform touching a niche knob on a population with no
bases, and the response carries a block naming the knobs, the declared base and the
national stake. It renders **above** the headline, because a warning underneath is one
the reader reaches after believing the number. It falls silent as soon as the population
has bases — the half that keeps it from becoming permanent furniture — and silent on any
reform that touches no niche.

## D-067 — Voies et Moyens columns are budgetary years, not income years

The annexe's cost columns are **budgetary**, and budgetary year N carries the dispositif
assessed on the **revenus N−1**. A model simulating 2024 incomes compares against the
column labelled **2025**.

Three of five research passes got this wrong in the same direction, and one presented
the resulting 3.4 % discrepancy as a reassuring cross-check when the discrepancy *was*
the lag; corrected, the same comparison closes to 0.19 %. **A residual small enough to
feel like validation is the most dangerous size for a systematic error to be.**

The correction is not free and both columns stay printed: the right-vintage figure is a
**forecast**, and the PLF 2025 forecast for the same dispositif in 2024 came in at
6 724 M € against a realised 6 420 M €, a 4.5 % overshoot. Neither column is a clean
comparator, so `docs/B3_IR_NICHES.md` §3 gives both and says why.

Sourced from the PDF on disk, read by this session rather than taken from the research
prose: saldom 6 420 / 7 029 (n° 110246, 4 909 243 bénéficiaires), garde 1 737 / 1 799
(110203), dons 1 990 / 2 204 (110201), scolarité 221 / 229 and 217 / 225 (110215,
110242), syndicales 149 / 156 (110202). Five families, **11.6 bn of 19.53 bn — about
59 %**, so a complete imputation of them would still leave two fifths unmodelled.

**What did NOT get settled, and is not being propagated.** openfisca places `ci_saldom`
in the globally-capped list, and the cap measurably destroys entitlement — 7 500 € of
home-help credit plus 3 500 € of childcare credit yields 10 000 €, not 11 000 €. Whether
art. 199 sexdecies genuinely belongs to the enumeration of art. 200-0 A could not be
confirmed: Légifrance returned 403 to the research pass and 404 to a second attempt. It
is recorded as a question with its measured consequence attached, not as a finding.

## D-068 — The niche imputation, and what spending a calibration target costs

`WHAT_NOW.md` B3 asked for imputation of take-up bases so that the IR-net line becomes
meaningful. Done: the population can be given réduction and crédit bases from the DGFiP
table of amounts and claimant counts **by decile of revenu fiscal de référence per
part**, and the net-yield line moves from **+22.5 % to +10.4 %**.

Opt-in and off by default, because it is a **calibration**. The niche totals then match
DGFiP by construction — the imputed 10.71 bn against a 10.605 bn target is a check on
the draw, not evidence of anything. `margins.NICHE_CREDITS_BY_DECILE` carries
`use="calibration"` and is now spent; `IR_NET_YIELD`'s caveat says in as many words that
the line is no longer independent for the niche component. **The barème line is
untouched and stays the clean one** — and its not moving is the test that the imputation
is correct, since niches are subtracted after the barème.

**Three artefacts, stated because none is visible in the output.** Every claimant in a
decile receives the same base — a count and a total are all DGFiP publishes, so the
incidence of a reform comes out as a ten-step function and anything finer is an artefact.
Who claims is a seeded draw conditioned only on the decile, so the *number* of claimants
is right and their *identity* is arbitrary. And about 45 % of the niches are still
missing: 10.6 bn imputed of 19.53 bn, with scolarité deliberately excluded because its
cases are counts of children while the published column aggregates the three levels.

**The global cap is still unpriceable, and the flag survives to say so.** Moving it from
10 000 € to 4 000 € costs exactly 0.000 bn *even with bases in place*: the cap binds only
above 10 000 €, the imputation gives every claimant a decile mean, and the largest of
those is about 1 900 €. Nobody reaches the cap because nobody can. That is a worse
failure than the original zero — a warning that disappears while the problem does not —
so `DISPERSION_DEPENDENT_KNOBS` keeps the blind-spot flag firing for that one knob when
the bases are imputed, and a population with genuine dispersion would silence it
legitimately.

Two traps the source file sets, both now guarded. The workbook is denominated in
**thousands** of euros for the 2018-2021 vintages and in **euros** from 2022 — the 2018
sheet reads 4 860 210 where 2023 reads 6 019 895 605, and both mean about six billion; a
plausibility band refuses the wrong convention outright. And the published decile bounds
are **not contiguous** — decile 1 ends at 1 972 while decile 2 begins at 1 972.1667, nine
such slivers in all — so each band runs to the next band's lower bound instead of its own
printed upper, or every foyer in a sliver would be dropped silently and the claimant
count would miss its target for no visible reason.

## D-069 — The barème line was reading the net figure, and only zero niches hid it

The reconciliation's barème line compared `ir` — **net** of réductions and crédits —
against a published target that is explicitly **gross** of them. It was right only
because every household's niches were zero, so the two quantities coincided.

Turning imputation on made them differ, and the line appeared to **improve from +8.7 %
to −1.7 %**. Nothing had improved. The comparison had started measuring a different
thing, and in the direction that looks like success — which is how this kind of defect
survives review.

Fixed by adding `ir_avant_niches` (openfisca's `ip_net`: after the décote, before the
article 199 réductions) and reading the barème line on it. The historical figure moves
from +9.1 % to **+8.7 %**: `ir` also carried the sign convention and the réduction sous
condition de revenus, so the old number was wrong by 0.35 bn as well as wrong by
construction. `test_the_bareme_comparator_is_not_the_net_figure` pins both halves.

The general form is worth keeping: **a comparison that is correct only because one side
is identically zero is not correct, it is untested.** Two earlier instances in this
project were the double-entry guard that balanced because both sides were derived from
each other (D-045) and the read-back that confirmed its own write (D-044).

## D-070 — The CAF cross-check is prepared, not done

The 2026-09-01 audit's oldest open gap: benefit levels have no independent validation of
any kind, where income tax has had one since D-019. `tests/golden/CROSSCHECK_CAF.md` now
carries three households — a lone parent on half-time SMIC, a modest couple, and a single
person with no income — chosen so that between them AF, PPA, RSA and AL are each
exercised at a level where being wrong would show. Our figures are computed and recorded;
the estimator's column is deliberately blank.

**This session did not run it and did not fake it.** The DGFiP check was browser-driven
with Max present; the CAF estimator is a portal application behind Google reCAPTCHA, and
working around a bot protection is neither acceptable nor a check worth having. D-019's
instruction — *do not fabricate the numbers* — applies here.

**The trap the file exists to prevent** is worth stating on its own, because it is easy
to fall into and would produce a confident, meaningless pass:
`mesdroitssociaux.gouv.fr`, `mes-aides.org` and ESTIME are all **powered by OpenFisca**.
Checking our benefit figures against them compares openfisca-france with itself. They are
also the most findable French benefit simulators there are, so an hour spent on one of
them would end in perfect agreement and zero information. The CAF's own estimator is the
Caisse nationale's production arithmetic, and that independence is the only reason the
exercise is worth doing.

## D-071 — A fourth read-back-blind parameter, and the grep rule that could not catch it

`af_cm.modulation.taux_tranche_1` resolves to 1.0 at 2024-01-01 and the AF formula never
reads it: `taux_helper` hardcodes the full rate as `(base_ressources <= plafond1) * 1`.
A knob aimed at it writes successfully and moves nothing — measured, halving it left a
two-child family's allocations at 1 771,44 € to the centime. It is not shipped.

**The standing rule from D-064 passed it**, and the reason is worth keeping. That rule
required a knob's parameter node to appear somewhere in openfisca's model source. Two
things defeat it here: `modulation` is referenced (its siblings are read), and
`taux_tranche_1` is referenced too — under `af_maj_dom.majoration_premier_enfant`, an
unrelated parameter that happens to reuse the leaf name. **A name-based rule is defeated
by name reuse**, and no refinement of the grep fixes that.

So the rule is replaced by outcome coverage: `tests/knob_cases.py` carries one household
per knob on which it demonstrably moves an output, and `test_knobs.py` runs all forty.
Four shapes of one failure are now on the record — a silently created child (D-044), a
derived parameter the formula recomputes (D-062), a duplicate tree for the same article
(D-064), and a rate superseded by a literal (here). Every one resolves non-null and every
one passes a read-back. **Running a household is the only check that has caught all
four.**

One knob is exempt, with the reason recorded and its own negative test:
`allegement_general_taux_50_et_plus` governs employers of fifty or more, and
`HouseholdInput` cannot express one — the engine reads every foyer as a small employer.
The parameter IS read by the formula on the other branch, so the levier is real and it is
the wire format that cannot reach it. The exemption fails the day an effectif becomes
declarable, which is the right moment to turn it into a case.

**A near-miss worth recording.** Three employer knobs were briefly read as dead because
they were watched on `cotisations_employeur` — which is GROSS of the allègements, the
reductions landing in `salaire_super_brut` instead. Deleting them would have been a
mistake caused by watching the wrong row. Three new output rows (`allegement_general`,
`allegement_bandeau_maladie`, `allegement_bandeau_famille`) make the reductions visible,
because a reader who moves an allègement knob and sees the contributions row unchanged is
being misled by the table, not by the engine.

## D-072 — A report line that claimed a target was hit without comparing anything

`reporting.Line.status` returned `"calibrated (spent)"` for any line whose `use` was
calibration — **before** checking whether a simulated value existed and before computing
a residual. Two lines pass a hardcoded `None`, because no output row extracted the
quantity. The report therefore printed

    Pensions et retraites | — | 400,4 bn € | calibrated (spent)

beside the note "the pension mass was scaled to hit this": the assertion that a target
was met, printed by a line that had compared nothing. `passes` returned True. A third
line, "Part sans bénéfice imposable", missed its own target by 3.8 % against a ±1 %
tolerance and rendered identically.

Fixed: absence of a comparison is reported first and as itself, and a calibration line
that HAS a value is graded against its target like any other. Being a calibration
explains why *hitting* it proves little — it never explained why *missing* it would be
fine.

**And the quantities existed all along.** Adding the two rows the lines needed makes them
compare: pensions +1.1 %, unemployment +0.8 %, against the calibration tolerance.
*(Corrigé par D-074 : cette tolérance est de ±2 %, non de ±10 % comme écrit ici d'abord, et les deux chiffres ci-dessus étaient ceux d'un sous-échantillon de 20 000 produit par un échantillonneur biaisé. Sur la population complète les deux lignes valent −0,05 % et +0,26 %.)*
Both pass. Nobody knew, because nothing had ever asked.

The class this belongs to is the one the reviewer ruled on: a comparison that cannot
fail is not a comparison. Here it could not even run.

## D-073 — Le balayage des comparaisons masquées, et deux lignes qui comparaient la mauvaise statistique

Verdict du relecteur : *une comparaison qui n'est juste que parce qu'un des deux côtés est
identiquement nul n'est pas juste, elle n'est pas testée*. Balayage exécuté sur toutes les
lignes de réconciliation, ménages et entreprises. Le registre complet est
`docs/ZERO_MASKED_SWEEP.md` ; ce qui est décidé ici est ce qui a changé dans le code.

**Le résultat le plus important n'est pas un zéro.** Deux lignes de distribution
comparaient la mauvaise statistique : la moyenne du décile 5 face à une médiane publiée,
et un rapport de moyennes de déciles face à un rapport de seuils. Corrigé en quantiles
pondérés par personne — ce que l'INSEE publie —, le niveau de vie médian passe de −12,2 %
à −5,0 % et D9/D1 de +39,1 % à +3,6 % sur la population complète. Plus de la moitié de
chaque résidu était un choix d'estimateur. Les deux notes de ligne calculent cet écart
**depuis leur propre passage** plutôt que de le recopier, pour la raison de D-072 : une
affirmation sur une comparaison, écrite là où la comparaison n'a pas été faite, est le
défaut lui-même. Le tableau de déciles reste pondéré par ménage, qui est ce dont l'incidence
d'une réforme a besoin, et un test interdit que la correction y fuie.

**Deux lignes qui s'améliorent grâce à un changement que nous avons fait** sont exactement
le mouvement qu'il faut suspecter. C'est la raison de la note, du registre et du test
plutôt que d'un simple commit.

**Quatre figures `use="validation"` étaient imprimées dans la table des sources sans
qu'aucune ligne ne compare quoi que ce soit à elles** — les comptes d'allocataires AF,
PPA, RSA, AL. C'est D-072 d'un cran au-dessus : non pas une comparaison masquée par un
zéro, mais une cible qui *avait l'air* dépensée sans l'avoir jamais été. Les quatre
lignes existent maintenant, comptées au niveau **famille** et en **décembre** parce que
la cible est un stock au 31/12 ; l'une d'elles, le RSA, sort à **+96,3 %**.

**Ce que le balayage a établi et qui n'est pas corrigé ici**, par ordre de gravité :
`loyer_mensuel` est identiquement nul chez 8,01 M de ménages primo-accédants, ce qui
applique à tort le forfait logement de la PPA et du RSA — et corriger la population fera
**sortir la PPA de sa tolérance** (+22,5 points mesurés), ce qui est le bon résultat et
la raison de le faire délibérément. Suivent sept lignes IS sectorielles jamais balayées dont
trois hors tolérance, un « taux effectif moyen » dont le numérateur porte cinq
prélèvements et non l'IS, et le secteur public non câblé — sur une ligne structurellement
incapable de le détecter.

**Une figure a dû être mesurée deux fois.** Le balayage annonçait que D9/D1 sortirait de
sa tolérance dès 10 % de capital ajouté. Notre propre mesure donne +5,5 points de
résidu, ce qui la laisse dedans. Le sens était bon, la magnitude non. D-026 tient : la prose d'un agent n'est
jamais la source d'une figure, y compris quand elle vient d'un balayage que nous avons
nous-même commandé.

**Et un drapeau qui n'existait nulle part.** Deux des lignes masquées n'avaient aucune
autre lecture *disponible* : le générateur du rapport ne passait jamais `impute_niches`,
et `docs/B3_IR_NICHES.md` documentait un `--impute-niches` qui n'existait sur aucune
commande — une référence pendante, qui se lit comme une couverture. Le drapeau existe
maintenant sur `population run` et `population reconcile`, à faux par défaut. Mesuré :
l'IR net passe de +22,5 % à +10,4 %, les foyers imposés de −2,3 % à −8,8 %, **et la ligne
barème ne bouge pas d'un centième**. C'est cette troisième ligne qui dit que la correction
est juste plutôt que seulement favorable.

## D-074 — Le sous-échantillon n'était pas un tirage PPS, et le test qui le gardait ne pouvait pas échouer

Trouvé en corrigeant l'échec de gate laissé par D-073 : deux lignes de calibration
sortaient de leur tolérance de ±2 % — pensions à +2,29 %, chômage à −2,40 % — alors que la
calibration atteint sa cible **exactement** sur la frame complète (mesuré : −0,0000 % et
+0,0000 %). Le résidu ne pouvait donc venir que du tirage.

**Et il grandissait avec la taille du tirage.** Masse des pensions : +1,12 % à n=20 000,
+2,34 % à 50 000, **+6,39 % à 100 000**. Chômage : +0,55 %, −2,61 %, **−5,80 %**. Une
erreur d'échantillonnage décroît en 1/√n ; une erreur qui croît est un **biais**.

La cause : `np.random.default_rng().choice(..., replace=False, p=w)` **n'est pas un tirage
PPS**. numpy tire séquentiellement et renormalise les probabilités restantes après chaque
tirage, si bien que la probabilité d'inclusion réalisée d'une unité lourde **sature vers
1** au lieu d'atteindre n·w/W. Le code attribuait ensuite à chaque survivant le poids
constant W/n, qui n'est correct **que si** π = n·w/W.

Mesuré sur une population synthétique à queue lourde : les six unités les plus lourdes ont
un π supposé de 1,80 à 1,31 — **des valeurs supérieures à 1, ce qui est déjà la preuve,
aucune probabilité d'inclusion ne pouvant excéder un** — contre un π réalisé de 0,94 à
0,86, tandis que les plus légères ressortent à 1,5× leur π supposé. Sur une variable
corrélée au poids, l'estimateur est biaisé de **−18,7 %** ; Horvitz-Thompson avec les π
réellement réalisés rend +0,03 %.

**Le test qui gardait cela ne pouvait pas échouer.** `test_subsample_preserves_total_weight`
vérifie que le poids total est conservé — or W_certain + k·(W_reste/k) = W **par
construction**, quel que soit le plan de sondage. C'est exactement la classe que D-073
balayait, dans l'échantillonneur lui-même.

**La correction, en deux parties.** (1) Une **strate exhaustive** : quand n·w/W ≥ 1, aucun
plan ne peut donner à l'unité la probabilité que l'argument d'auto-pondération suppose,
puisque ce nombre dépasse 1. Ces unités sont prises avec certitude et **gardent leur propre
poids** ; les retirer réduit W et n pour le reste, ce qui peut en faire basculer d'autres,
donc la boucle itère jusqu'au point fixe. (2) **PPS systématique (Madow)** sur le reste,
dans un ordre permuté aléatoirement : π = k·w/W_reste exactement, ≤ 1 par construction de
la strate, donc le poids constant W_reste/k est exact.

Après correction, l'erreur **décroît** avec n comme elle le doit, et les quatre lignes de
calibration rentrent : masse salariale −0,09 %, pensions +0,43 %, chômage −1,00 %.

**Une alerte qui n'en était pas une, et qui vaut d'être écrite.** Sur le tirage de
50 000 la ligne du barème est passée de +8,5 % à +10,9 %, donc hors de sa tolérance de
±10 %, et cela a d'abord été rapporté comme le prix honnête de la correction. C'était
faux. La population **complète**, sans aucun échantillonnage, donne **+8,8 %**, dans la
tolérance. Le +10,9 % était la variance d'un seul tirage, pas un biais. La leçon est
celle du reste de ce projet : un seul tirage n'établit rien, et la population complète
est le seul arbitre.

Vérifié en mesurant plutôt qu'en supposant. Sur quatre graines à n=50 000, le résidu du
barème vaut +6,90 %, +10,23 %, +8,18 % et +9,62 % — **moyenne +8,73 %** contre +8,8 % sur
la population complète, soit **0,07 point d'écart**, et un **écart-type de 1,49 point par
tirage**. L'échantillonneur corrigé est donc sans biais sur cette ligne, et le bruit d'un
seul tirage y est du même ordre que la tolérance de ±10 % elle-même. C'est la raison de
fond de produire le rapport **sur la population complète**, ce qui retire la question de
l'échantillonnage de la page de crédibilité au lieu de la commenter.

**La garde a dû être écrite deux fois.** La première version tirait une variable à queue
lourde **indépendante du poids** et ne détectait rien (+0,34 %) : le biais porte sur la
corrélation entre la variable et le poids. La garde retenue prend `y = w`, le cas le plus
net, et **embarque l'ancien échantillonneur comme témoin négatif** — une garde dont on n'a
jamais montré qu'elle échoue est une garde que personne n'a testée.

## D-075 — Ce que la vérification adverse a ajouté à D-064, avant de le signaler en amont

Préparation de l'item A2 du handoff : signaler le paramètre fantôme en amont. Cinq
affirmations de D-064 ont été soumises à réfutation adverse à deux angles chacune, puis
tout ce qui portait le rapport a été **remesuré à la main** (D-026 : la prose d'un agent
n'est jamais la source d'une figure, y compris quand elle vient d'un balayage que nous
avons commandé).

**Ce qui tient, reproduit ici même.** Sur un foyer dont le crédit de référence est
**non nul** — 5 000 EUR, la vérification anti-zéro-masqué sans laquelle la démonstration
ne vaudrait rien — écrire 0,9 dans `aide_a_domicile.taux` via une `Reform` réussit, se
relit à 0,9, et laisse `ci_saldom` à **5 000,0**. La même écriture sur
`emploi_salarie_domicile.taux` le porte à **9 000,0**. Sept feuilles sur sept identiques
au 2024-01-01. Zéro occurrence de `aide_a_domicile` dans les `.py` du paquet.

**Ce que D-064 ne disait pas.** L'identité des valeurs ne vaut qu'à partir du 2017-01-01 ;
avant, le nœud fantôme n'a **aucune** valeur et un accès au 2015-01-01 lève
`ParameterNotFoundError`. Et la chronologie est l'inverse de l'intuition : `aide_a_domicile`
est arrivé **le premier** (2022-11-16, import des barèmes IPP, chaque feuille portant encore
son `ipp_csv_id`), sans jamais être branché ; le dossier réellement lu a été créé **deux ans
plus tard** à côté. Ce n'est donc pas un renommage dont on aurait oublié de supprimer
l'original, c'est un import jamais câblé que le dossier câblé a redoublé. Il continue d'être
entretenu comme vivant — `last_value_still_valid_on: "2025-02-24"`.

**Et ce n'est pas un cas isolé.** Balayage de l'arbre entier : 4 645 chemins, 3 432 non nuls
au 2024-01-01, **715 lus par aucune formule**. Ce chiffre est une borne basse produite par
notre propre outil et ne prouve rien seul. Ce qui compte, et que **nous avons vérifié à la
main un par un**, ce sont les nœuds morts portant les **mêmes valeurs qu'un jumeau vivant** :
il y en a **six**, pas un — le premier jet du rapport en annonçait un seul et se trompait.

Les six reproduisent, en amont et sans que nous y soyons pour rien, **les trois formes que ce
projet avait cataloguées séparément** :

* l'arbre dupliqué pour le même article (D-064) — `aide_a_domicile` ;
* le paramètre **dérivé** que les formules recalculent (D-062) — `csg.activite.taux_global`
  vaut 0,092, soit exactement `deductible` 0,068 + `imposable` 0,024, et n'est lu nulle part ;
* le nom qui **défait une règle par grep** (D-071) — `taux_global` existe bien dans le
  source, mais sous `csg.remplacement.allocations_chomage` et sous `taxation_capital`,
  jamais sous `csg.activite`. Un grep sur la feuille conclut « utilisé » et se trompe,
  exactement comme il l'avait fait pour `af_cm.modulation.taux_tranche_1`.

Le plus piégeux du lot n'est aucun de ceux-là : `csg.remplacement.allocations_chomage.abattement`
est **au bon endroit dans l'arbre**, décrit pour cela, avec le bon barème — et les formules
CSG sur le chômage vont chercher `csg.activite.abattement` de côté. Qui réforme l'abattement
de CSG sur le chômage écrit dans le nœud mort.

**Rien n'a été publié.** Le brouillon est prêt, en français, au format du template amont ; le
dépôt aval n'y est pas nommé. Trois décisions restent au propriétaire du dépôt : publier ou
non, sous quel compte, et signaler ou non le doublon comme une classe plutôt qu'un cas.

## D-076 — Ce que l'échantillonneur corrigé a fait remonter : cf, asf, et un chiffrage épinglé sur du bruit

Deux échecs de gate après D-074, tous deux réels, tous deux des conséquences directes du
passage à un échantillonnage sans biais.

**Le garde d'écriture double a trouvé une troisième fuite.** Une réforme nationale de la
CSG bouclait à +0,11 % contre un plancher de 0,1 % : 11,86 M€ inexpliqués sur 10,6 md. La
mesure des postes désigne exactement `cf` (complément familial, 3,59 M€) et `asf`
(allocation de soutien familial, 8,23 M€) — 11,82 M€, le résidu à l'arrondi près. Les deux
sont sous condition de ressources, donc une réforme qui change le revenu net les déplace ;
les deux sont dans `revenu_disponible` via `prestations_familiales` ; aucune n'avait de
ligne. Les voici itemisées, comme `aefa` et la CRDS sur prestations l'ont été en D-062.

**La fuite était là avant, et c'est le tirage biaisé qui la maintenait sous le plancher.**
C'est le sens de la correction : un échantillonneur qui se trompe peut faire passer un
garde aussi bien qu'il peut le faire échouer.

**Un chiffrage était épinglé sur une valeur de tirage.** Le cas
`allegements_points_de_sortie_lfss2025` — le plus sensible au tirage de toute la suite,
parce que son rendement dépend de la masse salariale dans une bande étroite — était épinglé
à +107 %. Sur la **population complète**, sans aucun échantillonnage, il vaut **+112 %**
(4,23 md€ contre 2,0 md€ publiés) ; sur le sous-échantillon de 20 000 il vaut maintenant
+122 %. Le +107 % venait de l'échantillonneur biaisé, et les 10 points entre +112 % et
+122 % sont le tirage.

Le cas est donc réépinglé sur sa valeur **sans échantillon**, avec une tolérance de ±0,15
qui couvre le bruit de tirage mesuré, et la fiche du chiffrage porte les trois chiffres
plutôt qu'un seul. Réépingler sur +122 % aurait figé un artefact d'échantillonnage dans
une fiche dont le rôle est précisément d'empêcher un constat de dériver en silence.

**Une contrainte machine, notée parce qu'elle a coûté deux essais.** Un passage plein
tarif avec réforme sur les 199 451 ménages tient deux simulations en mémoire simultanément
et se fait tuer par l'OOM killer (SIGKILL, exit 137, mesuré). Le passage de réconciliation,
qui n'a qu'un système, tient. La valeur sans échantillon n'est donc pas disponible pour
tous les cas de la suite, et c'est pourquoi la tolérance reste par cas.

**Ce que les deux nouvelles lignes montrent, et qui n'est pas rassurant.** Une fois
itemisées, `cf` vaut 1,17 md€ et `asf` **9,04 md€** sur la population complète. La CNAF
publie une ASF de l'ordre de 2 md€. Le modèle est donc environ 4,5 fois trop haut sur cette
prestation — soit, ramené au barème mensuel d'environ 187 € par enfant, quelque 4 M
d'enfants bénéficiaires contre à peu près 1,4 M réels. Ce n'est pas une régression
introduite ici : c'est D-015 sur un instrument de plus, la population portant trop de
familles monoparentales éligibles, et cela devient visible seulement parce que
l'instrument a enfin une ligne. Aucune ligne de validation n'est ouverte pour l'ASF dans
cet incrément — il faudrait une figure publiée choisie et versée au registre — mais le
niveau est noté ici pour qu'il ne passe pas inaperçu.
