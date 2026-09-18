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

## D-077 — Décision du propriétaire : la phase suivante est le module patrimoine, publication toujours différée

Décision du propriétaire, 2026-09-04, consignée comme `docs/PHASE5_SPEC.md` le demande :
**la phase 5 est le module patrimoine** — IFI exactement, ISF ressuscité et plancher de
type Zucman honnêtement. Les trajectoires restent sur l'étagère comme l'autre option
spécifiée en principe. **La publication reste différée** : toute la section C du handoff
prestations est gelée, et le brouillon d'issue amont (`docs/UPSTREAM_ISSUE_DRAFT.md`,
D-075) continue d'attendre, prêt et non publié.

**Pourquoi cette phase peut être honnête**, et c'est la raison de l'avoir choisie : la
DGFiP publie l'IFI par tranche de patrimoine taxable — effectifs, base, impôt dû. Cette
table **est** la population. Le module n'a donc presque rien à synthétiser, et la ligne de
base devient une **vérification mécanique à calibration zéro** au lieu d'un ajustement.
C'est l'inverse exact de la situation de D-015. Corollaire à tenir : si l'on se surprend à
ajuster quoi que ce soit sur la table n° 33, c'est le dessin du module qui échoue, pas
qui a besoin d'aide.

**Hors périmètre, à refuser** : succession/DMTG (une phase entière à soi), **patrimoine
synthétique au niveau ménage** — les cellules seulement, une queue haute synthétisée
serait l'erreur D-015 exactement aux percentiles où elle est la moins survivable —, les
trajectoires, et tout canal de migration au-delà d'une bande étiquetée basse confiance.

### État du reliquat prestations (§B du handoff précédent), mesuré et non supposé

Le handoff demande de vérifier avant de commencer, et de n'interleaver qu'au mot du
propriétaire, pas par défaut. Mesuré :

* **Boutons : livrés.** 16 boutons prestations, chacun avec un ménage sur lequel il
  déplace une sortie (`tests/knob_cases.py`), et le registre est complet par test.
* **UI : partielle, 28 boutons sur 40 exposés.** Manquent notamment les **trois boutons
  forfait logement du RSA** ajoutés à l'incrément précédent, `af_taux_2_enfants`,
  `af_taux_3_enfants`, `af_majoration_plafond_par_enfant`, `ppa_bonification_taux_max`,
  et cinq boutons de niches.
* **Goldens d'exemple travaillé : absents.** §B demandait au moins un changement de base
  RSA et un changement de pente PPA dérivés à la main, le second montrant le déplacement
  du taux marginal effectif. `tests/golden/` n'en porte aucun.
* **Re-balayage des chiffrages : absent.** La suite compte quatre cas ; le backtest de la
  modulation AF de 2015 n'y est pas.

Le reliquat est donc réel et reste ouvert. Il n'est pas repris ici : la phase 5 commence.

## D-078 — M0 patrimoine : le spec se trompe sur ce que la DGFiP publie, et la vérification de remplacement est meilleure

Portail `scripts/verify_ifi.py`, vert. Détail complet dans `docs/M0_IFI.md`.

**`PHASE5_SPEC.md` §2 fonde tout le module sur une table qui n'existe pas.** Il annonce
que la publication DGFiP donne, par tranche, « redevable counts, taxable base, tax due »,
et que la vérification mécanique consiste à appliquer notre barème à la **base publiée par
tranche**. Lecture faite des quatre millésimes, feuille par feuille : **la base par
tranche n'est pas publiée**. Ce qui l'est : les parts de foyers et d'IFI et l'IFI moyen
par tranche (n° 33, Graphique 3), et l'effectif, la base, l'IFI et les dons **en agrégat
seulement** (n° 45, Tableau 1). Quatre tranches, pas six — l'assujettissement commence à
1,3 M, donc la tranche 0,8–1,3 M du barème n'apparaît jamais dans la distribution.

**La vérification de remplacement n'est pas plus faible, et c'est le point.** Inverser le
barème sur l'IFI moyen de chaque tranche donne la base moyenne implicite ; l'agrégat
reconstitué est ensuite confronté à l'agrégat publié **indépendamment**. Rien n'est
ajusté : l'impôt par tranche et la base agrégée sont deux publications distinctes, et
c'est notre arithmétique qui les relie. Deux propriétés falsifiables en sortent :

1. **la base moyenne implicite doit tomber dans sa propre tranche** — rien ne l'y force,
   et un barème mal lu l'en fait sortir. Mesuré : 1,7052 / 3,1772 / 6,0747 / 14,7126 M€,
   les quatre dedans ;
2. **le manque doit avoir le bon signe** — décote, plafonnement et réduction dons baissent
   tous l'impôt, donc inverser l'impôt doit sous-estimer la base. Mesuré **−6,46 %**. Un
   manque de signe inverse aurait dit que l'arithmétique est fausse, pas incomplète.

**La table s'est vérifiée elle-même.** Les deux routes publiées vers l'IFI d'une tranche —
sa part du total, et son IFI moyen fois son effectif — sont deux nombres distincts de la
publication et concordent à **+0,003 %**. C'est un contrôle de notre lecture, pas une
tautologie.

**Trois pièges, tous du type déjà catalogué.** (a) L'en-tête ment sur les unités :
`Patrimoine net total (M€)` contient 466 792 714 707, soit des **euros** — le piège des
niches à l'envers, refusé par une bande de plausibilité plutôt que cru. (b) Les feuilles
ne sont pas adressables par coordonnées : le libellé est en colonne 2 dans n° 45, le bloc
de données commence ligne 26 sous un graphique dans n° 33 ; les deux lecteurs **cherchent**
leur bloc par forme. (c) Les bornes de tranche sont vérifiées contre les libellés du
fichier, pour qu'une publication qui recouperait ses tranches échoue bruyamment.

**Et l'effectif publié est arrondi.** 186 100 à la centaine, alors que base ÷ moyenne
publiée vaut **186 094,000** — entier à six décimales, ce qui l'identifie comme le vrai.
Les cellules sont bâties dessus : 0,0032 % d'erreur gratuite sous chaque figure de la
phase est précisément ce qui ne se voit jamais.

**Un millésime que le spec ignore.** `n° 45` (avril 2026) publie l'IFI 2025 — 193 600
foyers, 2,3319 md — et porte 2024 en colonne de comparaison. Les deux sont manifestés ;
les tranches restent lues sur n° 33.

**Le contrôle fantôme est passé** sur `impot_fortune_immobiliere_ifi_partir_2018` : lu par
une formule, barème exactement celui qu'annonce §1. Le portail assert aussi que
`aide_a_domicile` reste, lui, non lu — la garde ne peut pas passer à vide.

## D-079 — M1 : l'IFI au foyer, et deux défauts du moteur que les goldens ont sortis

Calculateur IFI au foyer (`src/impots/patrimoine/ifi.py`), entrées en forme 2042-IFI,
goldens dérivés à la main à chaque coude du barème, dans la fenêtre de décote, sur
l'abattement RP, le passif, les dons et leur plafond. La chaîne reste **celle du
moteur** — `assiette_isf_ifi` → `isf_ifi_iai` → `decote_isf_ifi` → `isf_ifi_avant_plaf`
→ `isf_ifi_apres_plaf` → `isf_ifi` — parce que la réutiliser fait hériter gratuitement
de la décote, du plafonnement à 75 % et du plafond des dons.

**Sans revenu, l'IFI vaut ZÉRO.** Le plafonnement plafonne IFI + IR à 75 % du revenu ;
à revenu nul, le plafond est nul et tout l'IFI est abattu. Mesuré : 2 M€ de base
donnent 7 400 € de barème et **0 €** d'IFI à revenu nul, 7 400 € dès 50 000 € de
salaire. Tous les goldens du module portent donc un revenu. Un golden sans revenu
aurait affiché zéro et n'aurait rien testé — la comparaison masquée par un zéro, dans
le premier fichier de test du module.

### Défaut 1 — le moteur impose sous le seuil d'assujettissement, et rend l'impôt non monotone

CGI art. 964 : l'IFI est dû par ceux dont le patrimoine immobilier net taxable
**excède 1 300 000 €**. En dessous, rien. Or `isf_ifi_iai` en version 2018+ vaut
`bareme.calc(assiette)` **sans aucun test d'éligibilité**. Mesuré : **500 €** à
900 000 €, **2 500 €** à 1 299 999 €.

Ce qui prouve que c'est un défaut et non une lecture : **l'impôt devient non
monotone**. 1 299 999 € doit 2 500 €, 1 300 000 € doit 1 250 € — franchir le seuil
**divise l'impôt par deux**, parce que la décote ne commence qu'au seuil. Un impôt qui
baisse quand la base monte n'est la politique de personne.

La formule ISF 1989-2017 portait bien une garde — `(assiette >= bareme.rates[1])` —
mais elle compare une assiette en euros au **taux** 0,007 et non au seuil : toujours
vraie. Cette garde-là n'a donc jamais fonctionné non plus.

Notre calculateur applique le seuil, **lu dans l'arbre** (la borne inférieure de la
décote, qui est le même 1 300 000 par construction) plutôt qu'écrit en dur. Et la
correction embarque son test-témoin : `test_the_engine_alone_would_tax_below_the_threshold`
échoue si openfisca corrige un jour, ce qui est le bon moment pour retirer notre garde
plutôt que de garder une correction qui ne corrige rien.

### Défaut 2 — le forfait mobilier de 5 %, qui est CONTESTÉ et non une coquille

`assiette_isf_ifi` majore la base de 5 % au titre du forfait mobilier. Ce n'est **pas**
un copier-coller : le paramètre porte sa propre documentation et un raisonnement
juridique réel — art. 973 CGI renvoie l'évaluation des biens IFI aux règles des DMTG,
et art. 764 I-3° plancher les meubles meublants à 5 %. Le fichier ISF annule d'ailleurs
son propre forfait au 2018-01-01, et un fichier IFI neuf a été créé à 0,05. C'était une
décision.

Notre lecture diffère : **art. 965 ne met que de l'immobilier dans la base**. L'art. 973
dit comment **évaluer ce qui est dans la base** ; l'art. 764 plancher une classe d'actifs
que la base IFI exclut entièrement. Importer ce plancher revient à taxer les meubles à
travers un impôt dont la base n'en contient aucun.

**Et les données tranchent, ce qui évite de s'en tenir à deux lectures.** Reconstituer
la base agrégée depuis l'impôt publié par tranche donne **−6,46 %** contre l'agrégat
publié indépendamment **sans** forfait, et **−10,92 % avec**. Tous les postes non
modélisés — décote, plafonnement, dons — baissent l'impôt et poussent donc la
reconstitution **vers le bas** : la vérité est au-dessus des deux, et la lecture qui
s'en approche par en dessous est la meilleure. Le forfait éloigne de 4,46 points.

Preuve indicative, pas démonstration : un allègement assez gros sauverait le forfait.
La correction est donc **par défaut mais commutable** — `forfait_mobilier=False` par
défaut, `openfisca_reading()` calcule l'autre, et l'écart est reportable (+9,5 % d'impôt
sur une base de 2 M€) plutôt qu'enfoui.

**Les deux défauts interagissent**, ce qui est le détail le plus parlant : sur un foyer
à 1 299 999 €, le moteur brut applique d'abord le forfait, ce qui porte la base à
1 364 999 € — **au-dessus du seuil et dans la fenêtre de décote** — puis facture
2 517,48 €. Un foyer qui ne doit rien se voit ainsi taxé au travers d'une fenêtre où il
n'aurait jamais dû entrer.

**Rien n'est publié en amont** : la section C reste gelée (D-077). Ces deux constats
rejoignent le dossier amont en attente avec le paramètre fantôme.

## D-080 — M2 : les cellules IFI, et le résidu chiffré poste par poste plutôt que toléré

`src/impots/patrimoine/cells.py`. **Chaque ligne que ce module produit est de la
validation** : il n'y a rien à calibrer, puisque la DGFiP publie la population. C'est la
propriété distinctive de la phase (D-077), et elle disparaît le jour où quelque chose ici
prend un facteur choisi pour refermer un écart.

Chaque cellule tire sa base moyenne en **inversant le barème** sur son impôt moyen publié
(D-078, la base par tranche n'étant pas publiée). L'inversion ne voit aucun allègement, si
bien que toute base implicite est une **borne inférieure** et que l'agrégat reconstitué
tombe nécessairement sous l'agrégat publié.

**§2 demande que ce résidu soit chiffré et expliqué, pas accepté.** Contre les 466,79 md
publiés :

| Poste | Base expliquée | Part du manque |
|---|---|---|
| Manque total | 30,18 md | −6,46 % |
| Dons : 220,7 M déclarés → 165,5 M de réduction à 75 %, remis puis ré-inversés | 17,43 md | **58 %** |
| Décote : au plus 1 250 € sur les foyers de la fenêtre 1,3–1,4 M | 0,97 md | 3 %, **borne haute** |
| Reste, pour le plafonnement et le divers | 11,77 md | 39 % |

Le plafonnement est le domicile plausible de l'essentiel du reste — il mord exactement là
où le patrimoine est gros et le revenu petit — mais **nous n'avons pas de quoi le
répartir**, et il est laissé nommé et non attribué plutôt qu'obtenu par différence puis
déclaré expliqué. Le plafond de 50 000 € par foyer sur les dons n'est pas appliqué non
plus, ce qui fait de leur 58 % une borne haute.

**Les deux propriétés falsifiables de D-078 deviennent la validation des cellules.**
Toutes les moyennes tombent strictement dans leur tranche — et le test exige *strictement*,
parce qu'une moyenne collée à une borne signalerait une inversion saturée et non résolue.
Le manque garde le bon signe.

**L'arithmétique du barème est dupliquée exprès, et le test l'empêche de dériver.**
`bareme.tax_on` refait ce que fait `isf_ifi_iai`, parce qu'inverser un impôt demande ~200
évaluations et que 200 simulations par cellule n'est pas une chose à faire. Le test
d'équivalence confronte les deux sur une échelle qui traverse tous les coudes — en
neutralisant le forfait mobilier, pour comparer **le barème** et non la convention de
base.

**Le test « rien n'est calibré » est comportemental, pas lexical.** Un grep sur
« calibrat » serait battu par le docstring de ce module, qui emploie le mot six fois pour
dire qu'il ne l'est pas — la leçon de D-071, une règle par nom perd contre la réutilisation
du nom. Le test nomme donc l'implémentation qui le ferait échouer : un facteur ajusté
refermerait le manque, et ne bougerait pas quand son entrée bouge. Il vérifie donc que le
manque **existe encore** et que doubler tous les taux du barème **abaisse** chaque base
implicite.

**Les trois millésimes du comparateur sont énoncés** dans le module : tranches 2024
(n° 33, paru avril 2025), agrégats 2024 (n° 45, paru avril 2026, qui imprime 2024 à côté
de 2025), et droit appliqué 2024. L'année budgétaire de comptabilisation est une
quatrième, et n'est pas utilisée ici : elle appartient à la section de réconciliation,
contre la source budgétaire manifestée et non contre une phrase de docstring.

## D-081 — M3 : les boutons IFI, le régime ISF, et trois affirmations du spec que la mesure renverse

### Les boutons : neuf, et quatre ont failli passer pour morts

Neuf boutons IFI, chacun vérifié **en faisant tourner un ménage** et en regardant l'impôt
bouger. Quatre — les trois paramètres de décote et le plafond des dons — n'ont rien bougé
au premier essai, non parce qu'ils sont morts mais parce que le ménage ne les exerçait
pas : la décote ne mord que dans la fenêtre 1,3–1,4 M, et le plafond des dons ne se voit
qu'avec des dons assez gros pour l'atteindre. C'est exactement le quasi-accident de D-071,
où trois boutons employeur ont failli être supprimés parce qu'on regardait la mauvaise
ligne. **Un ménage ne suffit jamais à déclarer un bouton mort.**

**Il n'existe pas de paramètre de seuil d'assujettissement.** Les enfants du nœud IFI
sont exactement `bareme`, `decote`, `forfait_mobilier`, `plaf`, `reduc_exo`, `reduc_impot`
— mesuré. Le seuil de 1,3 M dont §3 demande un bouton n'existe dans l'arbre que comme
**borne inférieure de la décote**, et c'est donc `ifi_decote_borne_inferieure` qui le
déplace. La « confusion classique » que le spec annonçait est réelle, et elle se règle en
regardant plutôt qu'en supposant qu'un paramètre au nom évident existe.

**La décote n'a pas de plancher à zéro, et un bouton peut la retourner en surtaxe.**
`decote_isf_ifi` vaut `parametre − taux × assiette` sans `max(0, …)`, et
`isf_ifi_avant_reduction` la retranche. Mesuré : sur une assiette de 1,35 M, porter le
taux de 0,0125 à 0,02 donne une décote de **−9 500 €** et fait passer l'impôt de 2 225 à
12 350 €. Un validateur refuse désormais ces combinaisons. **Sa première version vérifiait
la mauvaise borne** — elle testait l'entrée de la fenêtre alors que la décote est la plus
petite au sommet — et a laissé passer une décote de −2 500 € ; c'est
`test_each_knob_moves_its_output` qui l'a attrapée, en voyant l'impôt monter là où il
devait descendre.

### Le régime ISF : identique en barème, différent en base — et un cinquième fantôme

**Tous les paramètres ISF-2017 sont identiques aux paramètres IFI-2024** : barème, bornes
et taux de décote, plafonnement à 75 %, abattement RP à 30 %, forfait à 5 %. Vérifié un à
un. Un « retour de l'ISF » n'est donc pas un autre barème : c'est **le même barème sur une
base plus large**. Cela rend la réforme bien plus facile à raisonner et bien plus difficile
à rater.

Ce que le moteur cache : `isf_droits_sociaux` et `isf_actions_sal` portent
`end = "2017-12-31"` et renvoient zéro après 2017 sans qu'aucune formule tourne.
`assiette_isf_ifi.formula_2018_01_01` les appelle toujours — elles valent simplement zéro.
Les cases b1cb/b1cd/b1ce/b1cf sont donc lues en 2017 et **abandonnées en silence** en 2024,
et ce silence EST toute la différence ISF/IFI dans ce moteur.

**Écrire le nœud ISF en 2024 est un cinquième fantôme.** Ressusciter tout le nœud
`impot_solidarite_fortune_isf_1989_2017` au 2024-01-01 réussit, se relit correctement, et
déplace l'impôt de **zéro** : aucune formule sélectionnée en 2024 ne lit ce nœud. Le
« (dated parameters exist) » de §3 est vrai et sans effet.

**`update_variable` ne lève pas une date de fin, et échoue en silence.** Redéfinir la
variable sans `end` et appeler `update_variable` ne lève rien et laisse `end` au
2017-12-31 — la docstring d'openfisca-core le dit : « All attributes of the updated
variable that are not explicitly overridden by the new variable will stay unchanged ».
C'est la classe aveugle-à-la-relecture dans l'API des variables et non dans l'arbre des
paramètres. `replace_variable` marche, parce qu'il supprime puis recharge.

Et la copie doit être **littérale** : `Variable.set()` lit `attributes.pop(...)` sur le
`__dict__` **propre** de la classe, si bien qu'une sous-classe arrive sans aucun attribut
et se fait rejeter pour « Missing attribute 'value_type' ». Échec bruyant au moins.

Mesuré de bout en bout : un ménage 2024 avec 2 M d'immobilier et 2,5 M de valeurs
mobilières paie **7 400 €** sous l'IFI et **30 690 €** sous l'ISF ressuscité, assiette
2 000 000 contre 4 500 000, le système de référence restant intact.

### Les corrections passent dans la ligne de base, pour qu'il n'y ait qu'un chiffre

Les deux corrections de D-079 s'appliquent désormais à `engine.system.baseline()`.
Livrer une ligne de sortie nommée `ifi` dont on sait qu'elle est fausse n'est pas une
chose à faire. Le rayon d'action est nul et c'est la suite complète qui le prouve : les
deux ne mordent que sur un foyer déclarant de l'immobilier, et rien d'autre dans ce projet
n'en déclare. `uncorrected_baseline()` existe, nommé à voix haute, pour les tests-témoins.

### Le plancher de type Zucman n'est pas chiffrable, et le refus est le résultat

§2 ancre la cellule ≥ 100 M sur l'IPP Note 92. **Cette note ne contient aucun chiffre de
patrimoine.** Vérifié contre le PDF : son unique tableau s'intitule « Distribution des
revenus en 2016 » et ses deux colonnes en euros sont « Revenu fiscal » et « Revenu
économique » ; les auteurs excluent explicitement le patrimoine de leur mesure, qui
« n'inclut ni les variations de patrimoine, ni les revenus latents non encore réalisés ».

**Et elle contient un nombre fait pour être mal lu** : la ligne P99,9998 porte `75` foyers
et `150 040 000` — un montant à neuf chiffres à côté d'un petit effectif, dans une note sur
les milliardaires. C'est le seuil de **revenu économique annuel** d'entrée dans les
0,0002 % les plus riches, pas un seuil de patrimoine. Bâtir une cellule « ≥ 100 M » dessus
échangerait silencieusement une dimension de revenu contre une dimension de patrimoine, et
le chiffre obtenu aurait l'air parfaitement raisonnable.

Trois raisons indépendantes rendent le plancher non chiffrable ici, et le module les
énonce plutôt que de rendre un nombre : la tranche haute publiée est **ouverte** au-dessus
de 10 M ; nos cellules ne portent que de l'immobilier alors que le plancher porte sur le
patrimoine **total** ; et le plancher se crédite de l'**impôt sur le revenu**, pas de
l'IFI. Cette dernière n'est pas théorique : l'arithmétique correcte contre l'IFI rend
**zéro pour tout plafond posé**, parce que le taux marginal de 1,5 % de l'IFI sur toute la
base au-dessus de 10 M dépasse 2 % sur le seul excédent au-dessus de 100 M. Un zéro produit
par une comparaison mal posée est pire qu'un refus, donc le calcul est conservé,
inatteignable et testé, pour que personne ne le redérive et ne livre le zéro.

### L'incertitude de cellule, et pourquoi la méthode du spec ne tient pas

§2 propose de borner par « masse à la moyenne publiée contre uniforme sur la tranche ».
**Une loi uniforme sur [a, b] a pour moyenne (a+b)/2, qui n'est pas la moyenne publiée** —
mesuré, 1,935 M contre 1,7052 M sur la première tranche : elle contredit la donnée qu'elle
prétend respecter, et n'est l'extrême de rien.

L'encadrement honnête porte sur les lois réellement compatibles avec le publié : support
dans [a, b] et moyenne imposée. Sur cette famille et pour un impôt convexe, le **minimum**
est la masse ponctuelle à la moyenne (Jensen) et le **maximum** la loi à deux points sur
les bornes qui reproduit la moyenne. Les deux sont atteints, donc l'intervalle est serré et
non seulement valide.

Propriété qui rend l'outil crédible : **la largeur est nulle là où le placement ne peut pas
compter**. Les tranches publiées coïncident exactement avec les tranches du barème, donc
l'impôt y est affine et E[f(W)] = f(E[W]) ; la ligne de base ne porte aucune incertitude de
placement, et une réforme qui ne bouge que des taux non plus. Elle n'apparaît que lorsqu'une
réforme met un coude **dans** une tranche : porter le seuil à 2 M ouvre une bande de
[0 ; 175,3] M€, parce que la donnée publiée ne peut pas dire combien des 137 705 foyers de
la première tranche sont au-dessus de 2 M.

Et la tranche haute étant **ouverte**, aucun maximum n'existe pour elle : `extremal()`
refuse plutôt que de substituer un plafond commode.

## D-082 — Le barème de l'IFI devient un bouton, et la fusion silencieuse qui dictait sa forme

M3 avait livré neuf boutons IFI sans le principal. Un jeu de boutons auquel manque son
levier de tête se lit comme complet alors qu'il ne l'est pas, ce que ce projet traite
comme un défaut. Trois boutons de plus, tous vérifiés en faisant tourner un ménage :

| Bouton | Ménage qui l'exerce | Mesuré |
|---|---|---|
| `ifi_bareme` (échelle) | 20 M de bâti, 5 M de salaire | 248 190 → 398 190 € en doublant le taux du haut |
| `ifi_plafond_reductions` | 12 M + 100 k de dons | 198 190 → 238 190 € en abaissant le plafond |
| `ifi_non_bati_seuil` | bois, ruraux, groupements | 15 180 → 15 440 € |
| `ifi_non_bati_taux_bois_forets` | idem | 12 690 → 14 690 € |

Les deux derniers sont **morts sur un foyer qui ne détient que du bâti**, et ont donc
leur propre ménage. C'est la même discipline que pour la décote : un ménage ne suffit
jamais à déclarer un bouton mort.

**`ifi_plafond_reductions` vise le nœud vivant, et son jumeau est mort.**
`plafond_somme_trois_reductions_pme_fcip_fip_pme_dons` est lu ;
`plafond_somme_reduction_pme_fcip_fip_pme` porte le même 50 000 et n'est lu par personne
— l'un des six sosies morts trouvés en amont (D-075). Un bouton visant le jumeau
s'écrirait sans erreur et ne bougerait rien.

### La fusion de tranches, et pourquoi la garde ne peut pas être dans le chemin d'écriture

**Deux tranches au même seuil sont FUSIONNÉES par le moteur, et leurs taux ADDITIONNÉS.**
Mesuré sur le barème IFI : écrire le seuil de la tranche 0 à 1 300 000 fait passer cinq
tranches à quatre et le taux de tête à **0,012 = 0,005 + 0,007**. La bande 1,3–2,57 M
double en silence. Rien ne lève.

La garde ne peut pas être posée dans `update_bracket`, parce que **le moteur s'appuie
délibérément sur cette fusion** : `_apply_bareme` neutralise les tranches actives en
surplus en leur donnant le seuil du haut et un taux **zéro**, où additionner est
inoffensif. Interdire les seuils égaux casserait le mécanisme légitime.

La protection va donc là où le barème entier est visible — le validateur de spec —
exactement comme pour l'IR. Et le validateur porte **son propre test-témoin** :
`test_the_merge_is_real_and_sums_the_rates` mesure la fusion sur le moteur et échoue si
openfisca cesse un jour de fusionner, moment où le validateur deviendrait sans objet.

**Le premier seuil n'est PAS forcé à zéro, contrairement à l'IR.** Le barème de l'IR doit
couvrir chaque euro de revenu ; l'IFI exonère tout ce qui est sous 800 000 **en n'y ayant
aucune tranche**. Recopier la règle de l'IR interdirait le barème légal lui-même.

**Et le seuil d'assujettissement ne pouvait décidément pas être un bouton de paramètre.**
Les deux contournements ont été mesurés et corrompent tous deux le barème : porter le
seuil de la tranche 0 à 1,3 M fusionne les tranches (bande à 1,2 %), et le porter à
1 299 999,99 supprime la bande à 0,5 %. La garde de `patrimoine.corrections`, au niveau
de la formule, n'est donc pas la solution la plus propre : c'est la seule juste.

Vérifié à la main de bout en bout : un barème à deux tranches — 1 % dès 1,3 M, 2 % dès
5 M — sur une base de 20 M donne 3,7 M × 1 % + 15 M × 2 % = **337 000 €**, et le moteur
rend 337 000,00 €.

## D-083 — Le balayage du récit : la « défaillance la plus informative » de la phase 1 n'était pas celle qu'on croyait

Dette de relecture, ordonnée en pré-vol de M4. D-073 a fait passer le rapport interdécile
de +39,1 % à **+3,6 %** en le lisant comme l'INSEE le publie — des seuils pondérés par
personne, et non un rapport de moyennes de déciles. Plusieurs documents racontaient encore
l'ancienne histoire, et un projet dont les documents survivent à leurs propres corrections
n'a pas de récit, il a des sédiments.

**Ce qui est tombé.** La ligne interdécile était citée comme la preuve maîtresse que la
*forme* de la distribution synthétique était fausse — « la ligne la plus informative de la
branche A' », dans `margins.py`, dans `PHASE1C_ERFS.md`, dans l'audit du 1er septembre.
L'essentiel de ce +39 % était un **mauvais estimateur**, pas un défaut de population.

**Ce qui tient, et qui porte désormais l'argument.** Rien de tout cela ne dépend d'un
choix de statistique :

* le **backtest des allègements 2025 à +112 %** — un chiffrage publié, manqué d'un facteur
  deux, parce que le rendement dépend de la masse entre 2,25 et 2,5 SMIC (D-076) ;
* les **lignes RSA**, +113 % en euros et +96 % en allocataires ;
* l'**ASF à 9,0 md contre ~2 md publiés**, un instrument de plus, même cause ;
* l'**absence totale de revenus du capital**, à cause de laquelle les deux lignes de
  distribution sont dans leur tolérance plutôt que malgré (D-080).

**Le dossier ERFS ne s'en trouve pas affaibli, il s'en trouve mieux argumenté.** La thèse
n'est plus « la forme d'ensemble est fausse » mais « elle échoue **aux seuils et dans la
population à revenu nul** » — ce que l'ERFS corrige précisément. Vider 13,5 M d'adultes de
la distribution déforme la densité partout ailleurs, et c'est cela que le backtest mesure.
Un dossier qui citerait la ligne tombée appellerait exactement la correction qu'elle vient
de recevoir.

**Documents mis à jour** : `PHASE1C_ERFS.md` (le tableau des causes, la thèse en une
phrase), `AUDIT_2026-09-01.md` (deux encadrés de correction plutôt qu'une réécriture — un
audit se corrige au vu de tous, il ne se repeint pas), `margins.py` (le `caveat` de la
figure, qui se disait « la plus informative »).

**Et une leçon d'épistémologie que l'audit avait ratée**, notée là où il la ratait : être
**non dépensée** est nécessaire pour qu'une ligne dise quelque chose, et non suffisant. La
ligne interdécile était non dépensée et ne disait rien, parce qu'elle comparait la mauvaise
statistique. L'indépendance vis-à-vis de la calibration est un mode de défaillance ;
comparer le comparable en est un autre, et l'audit ne vérifiait que le premier.

## D-084 — L'audit « nommez l'implémentation qui la ferait échouer », et ce qu'il a trouvé

Seconde dette de relecture, ordonnée en pré-vol de M4. La règle, dans sa forme finale :
**pour chaque garde et chaque test, nommer l'implémentation qui le ferait échouer ; un
contrôle sans implémentation défaillante est de la décoration.** Le précédent est la garde
de conservation du poids de l'échantillonneur PPS, vraie par construction sous n'importe
quel plan de sondage, verte pendant toute la période où l'estimateur était biaisé (D-074).

### Les huit gardes de `guards.py` : toutes saines

| Garde | Lève | Test-témoin |
|---|---|---|
| `weight_identity` | oui | `catches_the_summed_weight_defect`, `catches_the_rescaled_pps_defect` |
| `no_nan` | oui | accepte du propre, lève sur NaN et inf |
| `non_negative` | oui | accepte, lève sur un négatif |
| `not_greater` | compte | vérifié à 1 et à 0 |
| `niche_blind_spot` | signale | vérifié dans les deux sens, plus le cas où il doit se taire |
| `sector_balance` | oui | deux témoins |
| `firm_balance` | oui | un témoin |
| `weighted_total` | non — c'est un utilitaire, pas une garde | sans objet |

**Et le premier outil que j'ai écrit pour cet audit était lui-même faux** : un scanner par
expression régulière a déclaré « 0 test-témoin » pour cinq gardes qui en ont. La règle
s'applique à l'outillage de l'audit comme au reste, et c'est la lecture à la main qui a
tranché.

### Les 579 tests : 47 portent la signature du risque, cinq relus, cinq valides

Signature retenue : un nom en *preserv*, *sums_to*, *agree*, *matches*, *identity*,
*total*, *deterministic* — ce qui annonce une propriété potentiellement vraie par
construction. Les cinq plus exposés ont été relus ligne à ligne :

* `test_total_is_the_sum_of_the_parts` — échoue si le moteur change la composition de
  `prelevements_entreprise` ; la liste des cinq prélèvements est écrite **indépendamment**
  dans le test. Valide, et c'est exactement le défaut trouvé côté firmes (numérateur à
  cinq prélèvements là où on lisait « IS »).
* `test_the_allocation_totals_the_impulse` — **valide, et sa valeur n'était pas écrite**.
  Elle l'est maintenant : l'allocation répartit sur les emplois finals *y compris
  importés*, précisément pour que le total soit conservé, la fuite étant calculée et
  reportée en aval et jamais appliquée là. Le test échoue donc si quelqu'un déduit la
  fuite dans l'allocation — le double compte que la phase 4 a attrapé deux fois.
* `test_household_margins_sum_to_the_published_total` — confronte deux figures **publiées
  séparément** ; échoue sur une faute de transcription ou un millésime mélangé. Valide.
* `test_published_cell_totals_are_reproduced_exactly` — vérifie l'erreur de calibration
  contre zéro ; échoue sur une étape de construction qui déplace un total en silence,
  c'est-à-dire les deux défauts de pondération de la phase 1. Valide.
* `test_run_preserves_the_weighted_totals` — compare la valeur enregistrée par la garde à
  un recalcul frais depuis la frame d'entrée ; échoue si un passage repondère. Valide.

### Conclusion, et la seule décoration connue

L'inventaire est sain. La seule garde connue sans implémentation défaillante reste
`test_subsample_preserves_total_weight`, déjà identifiée en D-074, **conservée
délibérément** et accompagnée depuis de
`test_subsample_is_unbiased_and_the_old_sampler_was_not`, qui embarque l'ancien
échantillonneur comme témoin négatif. Une garde vraie par construction n'est pas à
supprimer si elle documente une invariance réelle ; elle est à **accompagner** d'une garde
qui, elle, peut échouer.

## D-085 — M4.1 : la mise à l'échelle de composition, bandée et PLATE, et la source du cahier des charges qui ne peut pas la porter

§4 demande un facteur de composition **par tranche** — patrimoine total sur immobilier
taxable — sourcé sur les comptes distributionnels de la Banque de France et les agrégats
HVP, porté comme une bande.

**La source nommée ne peut pas descendre à notre niveau, et elle le dit elle-même.** Note
12 de la méthodologie BdF : « Les données expérimentales actuellement publiées ne
permettent pas pour le moment d'aller plus finement que le top 10% ou le top 5% ». Les
redevables de l'IFI sont ~186 000 foyers sur ~41,6 M, soit le **top 0,45 %** : la coupe la
plus fine des comptes distributionnels est un ordre de grandeur trop grossière. Le fichier
est manifesté **pour cette phrase**, pas pour ses chiffres.

**Ce qui existe est l'HVP de l'INSEE**, dont la coupe la plus fine au-dessus du neuvième
décile est **une seule ligne** — « Supérieur à P99 », lue dans la publication et vérifiée
caractère par caractère par un test : financier 27 · immobilier 36 · professionnel 5 ·
professionnel d'entreprise 29 · résiduel 3 · dette privée −4 · dette professionnelle −3.

**Une ligne au-dessus de D9, quatre tranches à couvrir.** Le facteur par tranche n'est donc
**pas sourçable**, et `per_tranche_factor()` lève avec sa raison plutôt que d'être absent.
Le facteur livré est **PLAT**, et la planéité est une limite énoncée, pas une hypothèse
d'uniformité : la composition se déplace vers le financier et le professionnel quand le
patrimoine monte, donc un facteur plat **sous-estime** une base ISF en haut de la fourchette
et la surestime en bas.

### Le point de droit qui vaut 34 points de base

**34 % du patrimoine du centile supérieur est professionnel** (5 + 29), et les **biens
professionnels étaient exonérés d'ISF** — CGI art. 885 N à 885 R, par le dernier alinéa de
l'art. 885 A (BOFiP). Le facteur n'est donc pas total-sur-immobilier :

* faux : 100 / 36 = **2,78**
* juste : (27 + 36 + 3) / 36 = **1,83**

Se tromper là-dessus aurait gonflé de 34 points la base de **toutes** les figures ISF que
ce module peut produire, et cela tient à un fait juridique, pas à l'arithmétique. Le test
`test_professional_wealth_is_excluded_because_the_isf_exempted_it` calcule les deux et
exige qu'ils diffèrent, pour que l'erreur ne puisse pas revenir en silence.

### Pourquoi la bande est large, et dans quel sens chaque raison pousse

Bande retenue : **[1,83 ; 2,06]**, centre 1,95. Le plafond est **dérivé** — on applique la
dette privée au seul dénominateur, (27+36+3)/(36−4) = 2,06 — et non choisi. Ce n'est pas
un intervalle de confiance et cela ne prétend pas l'être : c'est l'éventail que la donnée
publiée autorise.

* **Deux classements différents.** P99 range les *ménages* par patrimoine **total** (seuil
  2,2 M€ brut) ; les tranches IFI rangent des *foyers* par **immobilier taxable** au-delà
  de 1,3 M. Un ménage avec 1 M de pierre et 10 M de titres est dans P99 et ne paie aucun
  IFI. Ce ne sont pas les mêmes gens — le piège exact qui a coulé l'ancrage IPP (D-081).
* **Abattement RP et dette.** Le 36 % de l'HVP est de l'immobilier **brut** ; la base IFI
  est nette de dette et amputée de 30 % sur la résidence principale. Le vrai dénominateur
  est plus petit, donc le vrai facteur est **plus haut**.
* **Couverture du haut par l'enquête.** 10 250 ménages répondants ; la cellule P99 est
  mince et les enquêtes patrimoine sous-couvrent notoirement le très haut, là où le
  financier se concentre. Pousse **aussi vers le haut**.
* **Ménages contre foyers fiscaux.** Deux unités différentes.

Ordre de grandeur en sortie : sur les 466,79 md de base IFI publiée, la bande donne une
base ISF de **856 à 963 md**. À vérifier en M5 contre les statistiques ISF 2017 publiées,
qui sont le seul point de contrôle réel — et c'est précisément le backtest que le cahier
des charges programme.

**Le mode dégradé est livré et n'est pas un échec.** `IFI_BASE_LOWER_BOUND` chiffre un ISF
sur la seule base IFI, composition non modélisée, borne basse explicite. Règle permanente :
dégradé-mais-vrai vaut mieux que confiant-et-mis-à-l'échelle.

## D-086 — M4.2 : les lignes comportementales du patrimoine, et un cahier des charges à 0 sur 3

Le cahier des charges annonçait trois chiffres. **Aucun des trois n'existe dans l'article
qu'il désigne.** Vérifié par fan-out adverse à deux lentilles par affirmation, puis
recontrôlé à la main dans le PDF.

| Annoncé | Ce que porte l'article |
|---|---|
| « real elasticity ~0,05 » | 0,05 : **zéro occurrence**. Quatre estimations réelles : 0,08 (0,06) · 0,13 (0,04) · 0,14 (0,11) · 0,02 (0,10) |
| « reporting/enforcement ~0,55 » | « 0.55 » figure deux fois : un **taux marginal** de 2010 (0,55 %) et une cellule d'annexe. **Aucune élasticité d'application n'existe** |
| « Spain 0,64 » | « 0.64 » : **zéro occurrence**. « Spain » : une, dans un titre de bibliographie. Aucune élasticité espagnole, même citée |

**Et ma propre lecture était fausse aussi.** J'avais retenu 0,02–0,13 comme fourchette des
coudes purs, en prenant la phrase du résumé p. 4 pour l'ensemble. Ce résumé ne cite que les
deux panneaux **dynamiques** ; la figure 1 p. 36 en porte **quatre**, et le plus grand —
**0,14 (0,11)** — dépasse le plafond que j'avais annoncé. Vérifié moi-même dans la figure
après le verdict. La règle vaut pour le lecteur autant que pour le cahier des charges : le
résumé d'un article n'est pas l'article.

### Ce qui charge

**`wealth_tax_rate_elasticity` — centre ZÉRO, bande [0 ; 0,36].** Le centre n'est pas une
prudence, c'est le résultat : « We cannot reject the null hypothesis of no bunching at
kinks, and the implied elasticities are small and statistically indistinguishable from
zero » (p. 11). Le plafond est la plus grande estimation plus deux écarts-types
(0,14 + 2 × 0,11) : **une bande plus étroite que les écarts-types de sa propre source
serait plus fausse que pas de bande du tout**. Verdict SCOPE_PROBLEM — estimé sur l'ISF
2006-2010, dont la base est le patrimoine total, appliqué à un IFI immobilier qui se
déplace moins facilement ; comme le centre est zéro, le biais ne joue que sur le plafond.

**`wealth_disclosure_growth_effect_pp` — le résultat principal de l'article, dans ses
propres unités.** Ce n'est **pas** une élasticité et cela ne doit jamais être multiplié par
une variation de taux : l'unité est le **point de pourcentage de croissance annuelle du
patrimoine déclaré**. ITT de 0,50 pp juste sous le seuil, 0,13 pp juste au-dessus, 0,28 pp
en poolant — contre 2,2 % de croissance de contrôle, soit ~20 % et ~15 %.

La piste qui aurait pu sauver le « 0,55 » est **circulaire** : l'équivalence « de 0,7 % à
2,84 % » est calculée par les auteurs **en supposant** une élasticité de 0,13, donc elle ne
peut pas en établir une.

Ce qui survit et justifie le cadran d'application : les réponses aux obligations
déclaratives sont **dix fois** celles aux coudes de taux — un rapport d'ITT, 0,28 pp contre
au plus 0,03 pp.

### Ce qui ne charge pas, et reste écrit

Deux lignes en `removed:`, avec leur raison, parce qu'un canal qui rétrécit sans cause
visible est pire qu'un canal absent. Le repère espagnol pourra revenir le jour où quelqu'un
manifeste la source espagnole **elle-même** et la fait vérifier : recopier un chiffre depuis
un cahier des charges est exactement ce que D-026 interdit. La migration reste absente,
faute de source.

**Restent pour clore M4** : câbler les canaux sur ces deux lignes, et le cadran
d'application à côté du cadran de taux — dont la forme est désormais dictée par la mesure,
puisque l'effet d'application se mesure en points de croissance et non en élasticité.

## D-087 — M4.3 : les deux canaux patrimoine, et le cadran qui ne bouge aucun paramètre

**C5 — patrimoine déclaré et taux.** Le moteur est la variation du taux de rétention
(1 − t) en logs, parce que c'est l'objet contre lequel une élasticité de ce type est
définie ; prendre la variation du taux lui-même serait une autre grandeur qui a le même
signe. Bande **centrée sur zéro**, dans la bande de revenus.

**C6 — obligations déclaratives.** En **points de croissance annuelle du patrimoine
déclaré**, jamais en euros de la bande, et c'est l'unité qui le décide, pas la prudence :
cumuler un effet de croissance suppose un horizon, et un effet cumulé sur un horizon tu
est exactement le nombre confiant-et-faux que ce projet refuse. L'équivalent un an en
euros est dans les diagnostics, l'horizon nommé à côté.

**La symétrie est une hypothèse et porte l'étiquette.** L'étude observe un ALLÈGEMENT des
obligations, suivi d'une baisse du patrimoine déclaré. Appliquer la même amplitude en sens
inverse à un durcissement est tout ce que la preuve autorise, et ce n'est pas une mesure.

### Le cadran d'application, seul levier du simulateur qui ne touche aucun paramètre

`ifi_obligations_declaratives` ∈ {allegees, renforcees}. Les obligations déclaratives ne
sont **pas** un paramètre du code des impôts : ce cadran ne change rien au calcul mécanique
et n'agit que sur la bande. Il est donc **délibérément hors de `SCALAR_KNOBS`**, dont la
règle permanente est que tout bouton déplace une sortie — règle qu'il échouerait pour la
bonne raison. Un test vérifie qu'il laisse l'IFI mécanique inchangé au centime.

C'est la signature du module, promise depuis le premier audit du projet, et elle repose sur
un fait mesuré : **les réponses aux obligations déclaratives valent dix fois celles aux
coudes de taux** — 0,28 pp d'ITT contre au plus 0,03 pp. Un simulateur de fortune muni d'un
cadran de taux et privé de cadran d'application mettrait le petit levier dans la main de
l'utilisateur en cachant le grand.

Ordre de grandeur mesuré sur la base publiée de 466,79 md : un durcissement rend +0,295
point de croissance, soit ~1,38 md de base déclarée sur un an. Le triplement du taux
marginal (0,7 % → 2 %) rend, lui, une bande de −30 à −2 M€ de recettes, centrée à
−12,9 M€. Les deux cadrans ne jouent pas dans la même cour, et c'est le résultat.

**Les deux canaux sont disjoints**, vérifié : une réforme de barème ne déclenche pas C6, et
le cadran seul ne déclenche pas C5.

## D-088 — M5 : l'onglet patrimoine, la section de réconciliation, et une ligne budgétaire qui n'est pas le bon comparateur

### La section : tout est validation ou contexte, et le tableau de calibration est VIDE

C'est la propriété distinctive du module et elle se voit sur la page : le rapport ménages
porte quatre lignes de calibration, celui-ci n'en porte aucune. La DGFiP publie la
population, donc les cellules sont **lues** et non ajustées, et il n'y a aucune marge à
dépenser. Un test exige que le tableau « Calibration targets » ne contienne que son
en-tête — le vide **est** la preuve, et il cesse de l'être dès que quelqu'un y ajoute une
ligne.

**Une seule ligne est réellement falsifiable**, et c'est le contrôle mécanique de M2 :
base agrégée reconstituée par inversion du barème, **−6,46 %** contre un agrégat publié
séparément, tolérance déclarée ±12 %. Les deux autres sont du contexte et le disent :
l'IFI total « pour mémoire » reproduit la publication **par construction** — les cellules
en sont lues — et l'afficher comme validation serait la comparaison masquée dans sa forme
la plus pure, un contrôle qui ne peut pas échouer imprimé comme s'il le pouvait.

### La ligne budgétaire n'est pas le comparateur, et §6 se contredisait

`PHASE5_SPEC` §6 demande de comparer « total IFI yield vs the budget line (~2,2-2,3 bn
recent years) ». **Les deux moitiés de cette phrase ne désignent pas la même série.**
Vérifié moi-même dans les sources manifestées :

* bulletin statistique n° 45, millésime d'imposition 2024 : **2 159 M€** ;
* ligne budgétaire 1406, exécution 2024 : **2 739 M€** (Voies et moyens, annexe au PLF
  2026, tome I, p. 23) ;
* écart **+26,9 %**, entièrement comptable.

La ligne budgétaire est sur base d'**encaissement** et agrège les avis courants, les
émissions antérieures non recouvrées et le contrôle fiscal ; le bulletin est sur base
d'**émission**, qui est ce que le moteur calcule. Suivre §6 à la lettre aurait imprimé
plus d'un quart de l'impôt comme erreur de modèle.

**Et ce n'est pas notre déduction** : l'éditeur des deux séries l'écrit dans le bulletin
même d'où viennent les cellules (n° 33, encadré 1), vérifié dans le fichier manifesté —
« Les données budgétaires publiées par ailleurs peuvent donc être différentes des montants
présentés dans cette publication. » Un test le relit dans le PDF, pour que l'affirmation ne
survive pas à la phrase.

La ligne budgétaire figure donc en **contexte**, non notée, avec l'écart nommé. Piège noté
au passage : **2 739 M€ figure aussi page 29** du même document, pour les accises sur le
gaz. Un grep sur le nombre trouve d'abord la mauvaise ligne.

### L'onglet UI, et trois choses qu'un lecteur prendrait pour des bogues

Déclaration IFI, ligne de résultat, et **les deux cadrans côte à côte** — la signature du
module. Trois avertissements à l'écran, chacun tenu par un test : le cadran d'application
**ne change rien au calcul mécanique** (sinon on le bouge, on voit l'IFI inchangé, on
conclut qu'il est cassé) ; un foyer **sans revenu ne doit aucun IFI** quel que soit son
patrimoine, à cause du plafonnement ; et **l'absence de case pour les titres est la
définition de l'impôt** (CGI art. 965), pas un manque du formulaire.

### Ce qui reste ouvert, et pourquoi

**Le backtest ISF-2017 n'est pas fait, faute de source.** Le fan-out lancé pour la trouver
a vu **six agents sur sept caler**, et la passe de vérification adverse n'a jamais tourné ;
seul l'agent budgétaire a rendu, et ses chiffres ont été revérifiés à la main ici. La
question restée sans réponse — le passage ISF 2017 → IFI 2018 donne-t-il un facteur de
composition **mesuré** plutôt que le [1,83 ; 2,06] tiré d'une enquête — est donc ouverte,
et je ne lui invente pas de réponse.

**Et le garde de provenance a mordu sur mon propre travail** pour la première fois : le PDF
de Garbinti et al. est resté un jour dans `data/raw/` sans être manifesté, alors que ses
chiffres servaient déjà deux lignes du magasin comportemental.

## D-089 — Le facteur de composition « mesuré » n'existe pas : le passage ISF→IFI a changé la population de 64 %

Question laissée ouverte par D-088, et refermée ici — par un refus, qui est le bon
résultat. L'idée était séduisante : l'ISF a été remplacé par l'IFI au 1er janvier 2018, donc
le rapport entre la base ISF 2017 et la base IFI 2018 serait un facteur de composition
**mesuré**, bien meilleur que le [1,83 ; 2,06] tiré d'une enquête (D-085).

**Il ne l'est pas, et l'écart n'est pas un détail.** Vérifié moi-même dans le rapport du
Sénat n° 42 (2019-2020), manifesté :

| Tranche de patrimoine net taxable | Redevables ISF 2017 exonérés d'IFI | Part de la tranche |
|---|---|---|
| 1,3 – 2,57 M€ | 190 237 | **74 %** |
| 2,57 – 5 M€ | 31 366 | 43 % |
| 5 – 10 M€ | 5 281 | 26 % |
| > 10 M€ | 1 317 | **18 %** |
| **Total** | **228 201** | **64 %** |

**64 % des redevables de l'ISF sortent entièrement de l'impôt**, et le taux de sortie va de
74 % en bas à 18 % en haut. Le rapport des bases agrégées confondrait donc un effet de
composition avec un effet de sélection **massif et non uniforme entre tranches**. Ce serait
un nombre qui a l'air mesuré et qui mesure autre chose — exactement le piège que le même
projet a évité sur l'ancrage IPP (D-081) et sur le fractile P99 (D-085).

**Le gradient s'explique, et l'explication confirme le refus.** Ce n'est pas que les hauts
patrimoines soient plus immobiliers — l'enquête dit l'inverse. C'est un effet de **seuil** :
avec 15 M€ de patrimoine total, il suffit d'en avoir 1,3 M€ en pierre pour rester redevable
de l'IFI, alors qu'avec 1,4 M€ de total il faut que la quasi-totalité le soit. Le taux de
sortie décroît donc avec la richesse pour une raison arithmétique, sans rien dire de la
composition.

La bande de composition reste donc celle de D-085 — **[1,83 ; 2,06], plate, tirée de
l'HVP** — avec ses limites déjà écrites. Aucune source mesurée ne la remplace.

**Ce que ces tableaux valent quand même**, et c'est réel : ils sont la meilleure
description publiée de ce qu'a fait le changement de régime, par tranche. Ils serviront au
backtest ISF-2017 le jour où sa source arrivera, et ils bornent déjà l'ordre de grandeur :
le gain cumulé pour les sortants est de **1 655 M€**, à comparer aux ~2,2 md d'IFI émis.

**Le backtest ISF-2017 reste sans source.** Ni le rapport du Sénat ni les bulletins DGFiP
que nous détenons ne donnent l'ISF 2017 par tranche en effectifs, base ET impôt. Le
candidat suivant est le rapport IPP n° 46 sur le plafonnement de l'ISF, non encore lu.

## D-090 — Le backtest ISF-2017, et un sixième défaut du moteur trouvé en le construisant

Le seul chiffre **hors échantillon** du module patrimoine. Tout le reste compare le
moteur à des données dont les cellules sont issues ; ici l'ISF est mort en 2017, les
chiffres ont été publiés en 2023 à partir de dossiers fiscaux que ce projet n'a jamais
touchés, et rien n'a été ajusté dessus.

**L'URL du handoff était morte.** `uploads/2023/10/Rapport_IPP_46_ISFplaf-2.pdf` renvoie
404 ; le fichier a été redéposé en juin 2025 sous `uploads/2025/06/46_…`. La session de
relecture disait la source « localisée, lue et confirmée » — elle l'était, mais le lien
ne résolvait plus. Relevé sur la page de publication et manifesté.

**Et le tableau annoncé n'est pas celui qui sert.** Le handoff attend du tableau 1.1
l'ISF par tranche, avant et après plafonnement. Le tableau 1.1 donne les **effectifs** par
tranche et, pour toutes les colonnes monétaires, seulement la **part attribuable aux
foyers plafonnés** — aucun montant, aucune base. C'est le **tableau 1.2** qui porte les
niveaux, par statut de plafonnement plutôt que par tranche, et c'est lui qui rend le
backtest possible.

### Le résultat

Ménage moyen reconstruit poste par poste — ses composantes somment au total publié **à la
décimale près**, dans les deux groupes, ce qui est le contrôle de la lecture — puis passé
dans la chaîne ISF du moteur à la période 2017.

| | nous | publié | écart |
|---|---|---|---|
| plafonnés, avant plafonnement | 152 725 € | 153 417 € | **−0,5 %** |
| plafonnés, après plafonnement | 53 987 € | 49 483 € | +9,1 % |
| non-plafonnés | 30 918 € | 25 821 € | **+19,7 %** |

**Le −0,5 % est en partie deux erreurs qui s'annulent, et le dire est le point.** Jensen
tire vers le bas — un ménage moyen passé dans un barème convexe sous-estime l'impôt moyen
— et les **réductions ISF-PME et dons**, que nous ne modélisons pas, tirent vers le haut.
Sur les non-plafonnés, dont les patrimoines font le tiers, la seconde domine et donne
+19,7 %. Sur les plafonnés elles se compensent à peu près. Un backtest qui tombe à un
demi-point parce que deux effets non modélisés s'annulent n'est pas un backtest qui tombe
là parce que tout est juste, et le module ne revendique pas le second.

**La tolérance n'a pas été élargie pour absorber le manque.** Un groupe passe, l'autre non,
et les deux faits sont épinglés : un backtest qui admet tout ne mesure rien.

**Le +9,1 % sur le plafonnement s'explique mécaniquement**, vérifié et non affirmé. Le
plafonnement compare l'ensemble des impôts à 75 % du revenu ; notre ménage n'a que du
salaire, faute d'une composition de revenu publiée, et produit donc 34 893 € d'impôts
plafonnables contre les 51 154 € publiés (IR 32 486 + prélèvements sociaux 18 668). Les
prélèvements sociaux manquants sur les revenus du capital font moins mordre le plafond. Ce
que le plafond reproduit, en revanche, c'est sa **forme** : −64,7 % de l'impôt d'avant
contre −67,7 % publiés, sur un mécanisme qui vaut les deux tiers de la note.

### Sixième défaut du moteur : le mobilier déclaré compté deux fois

`isf_droits_sociaux` somme `b1cg` — le mobilier déclaré — et `assiette_isf_ifi` le
**rajoute** ensuite comme forfait mobilier. Mesuré : 1 000 000 € déclarés donnent une
assiette de **2 000 000 €**.

L'art. 764 I-3° fait des 5 % un **plancher**, « la preuve contraire étant aussi réservée » :
déclarer la valeur réelle **remplace** la présomption, elle ne s'y ajoute pas. Être taxé
deux fois pour avoir usé d'une option légale n'est la politique de personne, et cela frappe
précisément le contribuable qui déclare au lieu de présumer.

**Invisible jusqu'ici, et pas par chance** : `isf_droits_sociaux` porte
`end = "2017-12-31"`, donc à 2024 il vaut zéro, b1cg n'est pas dans le total et l'ajouter
une fois est correct. Le défaut n'apparaît que là où cette variable est vivante — en 2017,
**et à 2024 sous notre propre résurrection de l'ISF**, qui relève la date de fin et
ramène le double compte avec la base financière. Corrigé, avec son test-témoin, et le
rayon d'action à 2024 est nul — ce que la suite prouve.

### Le mapping décide de la réponse, donc le mauvais est épinglé comme tel

« Valeur titres avec contrôle » ne doit **pas** aller en `b1cb` : ce case applique
`taux_actions_conservees_6_ans` = 0,25, soit l'exonération de 75 % des titres sous
engagement de conservation, que le total post-abattements du rapport n'applique
manifestement pas — ses colonnes avant et après abattements ne diffèrent que de 647 k€ sur
13 929 k€, soit l'abattement résidence principale et peu d'autre. Y router les titres
exonérerait 1 045 k€ que le rapport compte encore, et fait passer le résultat de −0,5 % à
**−10,7 %**. Un test épingle la mauvaise lecture comme mauvaise.

**Détail de cohérence noté** : les quatre effectifs de tranche du tableau 1.1 somment à
356 231 contre 356 229 annoncés — deux foyers d'écart, arrondi interne à la publication,
consigné plutôt que réconcilié.

## D-091 — Clôture de la phase 5 : le dossier amont, la règle du pointeur, et l'état réel du reliquat

### Le dossier amont porte maintenant six constats, et aucun n'est publié

`docs/UPSTREAM_ISSUE_DRAFT.md` devient un dossier indexé plutôt qu'un brouillon d'issue
unique : l'arbre fantôme `aide_a_domicile`, six sosies morts de plus, l'IFI facturé sous
son seuil d'assujettissement avec la non-monotonie qui le prouve, le forfait mobilier de
5 % sur une base immobilière (contesté, argumenté des deux côtés), la garde ISF qui compare
des euros à un taux, et le double compte de `b1cg`. Plus un septième côté `openfisca-core` :
`update_variable` n'efface pas une date de fin et ne le signale pas.

Quatre des six ont la même forme : un paramètre ou une formule qui **résout, accepte une
écriture, se relit correctement et ne fait rien** — ou le fait deux fois. Aucune relecture
ne les attrape. C'est l'argument du dossier, et c'est aussi le résumé de ce que ce projet a
appris en six phases.

### La règle du pointeur, née d'un incident

`docs/SOURCE_POINTERS.md`. Un passage de relais transmet des **identifiants** — titre,
éditeur, numéro, date, **sujet** du tableau visé, et le **sha256** dès que le fichier est
manifesté — **jamais une URL nue comme référence porteuse**. L'implémenteur re-résout au
moment de l'usage.

Deux corollaires appris le même jour. Une URL peut être **périmée alors que l'index de
recherche la sert encore** : le chemin de 2023 était toujours renvoyé après le redépôt de
2025, et c'est la **page de publication** de l'éditeur qui portait le bon. Et un numéro de
tableau n'est pas un identifiant suffisant : le cahier des charges nommait « tableau 1.1 »
pour des montants que seul le tableau des niveaux porte.

Le fichier liste les neuf sources porteuses de la phase avec leur sha256 et le **sujet** à
transmettre. Deux d'entre elles sont manifestées **pour ce qu'elles ne contiennent pas** —
l'IPP Note 92 qui n'a aucun chiffre de patrimoine, la méthodologie BdF qui énonce sa propre
limite. C'est délibéré : établir qu'une source ne porte pas ce qu'on lui prêtait est un
résultat, et le perdre coûterait le même travail une seconde fois.

### Le reliquat, vérifié plutôt que supposé

| Item | État |
|---|---|
| Balayage du récit | **fait** — 308043c |
| Audit « nommez l'implémentation qui la ferait échouer » | **fait** — 26e6650 |
| Backtest modulation AF 2015 | **ouvert** — la suite compte quatre chiffrages, aucun n'est celui-là |
| Goldens d'exemple travaillé (base RSA, pente PPA) | **ouvert** — les cinq goldens sont tous IR/salaire |
| Boutons exposés dans l'UI | **31 sur 52** — et le dénominateur a monté, la phase 5 ayant ajouté douze boutons IFI dont trois seulement sont câblés à l'écran |

Le chiffre d'UI mérite d'être lu correctement : il n'a pas empiré par régression, il a
empiré parce que le jeu de boutons s'est enrichi plus vite que l'écran. Les onze boutons
IFI non exposés sont les plus fins — bornes de décote, seuils non bâti, plafond des
réductions — et l'onglet patrimoine porte déjà les leviers principaux.

## D-092 — Le solveur budgétairement neutre ne résout que sur l'étage mécanique, et le refus est la fonctionnalité

**2026-09-08 · F2 · `src/impots/scenarios.py`, `tests/test_scenarios.py`**

La feuille de route demande, pour F2, « un solveur de neutralité budgétaire — étant
donné une réforme qui coûte X, trouver par recherche de racine le déplacement de barème
ou de taux qui l'annule, étage mécanique uniquement, honnête par construction ». La
clôture de la phase 5 ajoutait la condition qui fait toute la différence : « le solveur
doit REFUSER de résoudre sur des grandeurs en bande, avec le refus testé ».

**Pourquoi c'est un choix de conception et non une limitation à lever plus tard.** Le
chiffre mécanique est un nombre. La bande comportementale, l'éventail macro, l'incertitude
de cellule et la bande de composition sont des **intervalles**. « La valeur du bouton qui
annule un intervalle » n'est pas une question bien posée : toute valeur de bouton dont
l'intervalle contient zéro y répond, et une recherche de racine rendrait celle qu'elle a
croisée en premier. Le résultat serait un nombre faux portant exactement la provenance
d'un nombre vrai — le mode de défaillance que ce projet redoute le plus.

`BANDED_QUANTITIES` nomme les quatre grandeurs refusées avec, pour chacune, la raison pour
laquelle elle est un intervalle. `refuse_banded()` est publique et séparée, pour que
l'appelant puisse poser la question avant de dépenser des minutes à en découvrir la
réponse. Le refus est atteignable depuis la ligne de commande (`--quantity`) précisément
pour qu'il ne soit pas une branche morte.

**Deux propriétés d'honnêteté, chacune avec son test qui tue.**

1. **Une exécution qui ne converge pas ne rend PAS sa dernière itérée.** C'est la
   propriété la plus susceptible d'être « corrigée » par quelqu'un qui trouve `None`
   gênant. `test_a_run_that_does_not_converge_does_not_return_its_last_iterate` échoue à
   la seconde où le retour final devient `SolverResult(knob, x1, f1, …)` — vérifié en
   cassant le code, pas en le lisant : le test tombe sur `value=0.376`.
2. **Un coût qui ne change pas de signe sur l'intervalle n'a pas de racine, et on le
   dit.** Le solveur ne rend pas une borne, il rend les deux coûts et la phrase « aucune
   valeur de ce bouton n'y neutralise la réforme ».

**Sécante plutôt que bissection, et la raison est le coût.** Chaque évaluation est un
tirage de population — des minutes, pas des millisecondes — donc l'écart entre 8 et 40
évaluations est l'écart entre un outil et un travail par lots. Le prix de ce choix est que
la sécante peut diverger là où la bissection ne le peut pas, d'où trois garde-fous : un
plafond d'évaluations, un repli sur le milieu quand la sécante sort de l'intervalle, et le
non-retour de la dernière itérée ci-dessus. **Le repli n'est pas décoratif** : sans lui, la
sécante propose 62,05 pour un bouton borné à 1,0 par le modèle de fil — donc une exécution
de population dépensée pour découvrir une erreur de validation. Vérifié en le neutralisant.

**La tolérance est large et c'est un aveu, pas un réglage.** 50 M EUR par défaut, parce
que le chiffre mécanique lui-même sort d'un sous-échantillon de 20 000 ménages dont le
bruit d'échantillonnage sur un agrégat national est de cet ordre (D-074). Une tolérance
plus serrée poursuivrait le tirage.

**La provenance fait partie de l'objet `Scenario`, et l'enregistrement est immuable.**
`source` et `created` sont obligatoires, et `save()` refuse d'écraser. Un scénario existe
pour **préenregistrer** un chiffrage — F2 existe pour que F1 soit possible : chiffrer le
PLF 2027 la semaine de sa publication, avec des chiffrages datés et versionnés,
confrontables ensuite aux évaluations préalables puis au réalisé. Réécrire un fichier
laisserait réviser un chiffrage en gardant sa date, ce que le préenregistrement est
exactement fait pour empêcher. Une révision est un nouveau scénario sous un nouveau nom.

**La comparaison A/B affiche les étages en bande et ne les différencie pas.** La
différence de deux intervalles est un intervalle. `LayerComparison.comparable` est faux
pour tout étage en bande, `mechanical_gap` rend `None` plutôt que zéro quand la
comparaison n'a pas pu être faite, et
`test_comparison_differences_the_mechanical_layer_and_only_that` échoue si quelqu'un
ajoute la soustraction.

**Ce que le solveur ne fait pas, énoncé plutôt que découvert.** `ir_bareme` n'est pas
soluble : c'est un barème complet, pas un scalaire, et une recherche de racine se fait sur
un scalaire. `ifi_obligations_declaratives` non plus : c'est un régime, envoyé comme une
chaîne. `scalar_knobs()` est **dérivée** du modèle de fil et non tenue à la main, si bien
qu'un bouton ajouté à `ReformSpec` devient soluble le jour où il atterrit — 54 boutons
aujourd'hui.

**Et cette dérivation s'est trompée une première fois, ce qui vaut d'être noté.** Elle
sondait `{bouton: 0.5}` et déclarait scalaire ce qui validait. Quatre boutons
authentiquement scalaires — `af_plafond_tranche_2_base` et les trois `ifi_decote_*` — ont
des validateurs CROISÉS : 0,5 seul est refusé parce que le plafond de tranche 2 doit
dépasser celui de tranche 1 et que les trois paramètres de décote sont couplés. La sonde
lisait ce refus comme « pas un scalaire » et le solveur les écartait avec un message qui
nommait le mauvais problème. Corrigé en lisant l'ANNOTATION plutôt qu'en sondant une
valeur. Le test porte les quatre noms.

**Et cette phrase-ci était fausse aussi**, dans sa première rédaction : « les bornes
restent appliquées là où elles doivent l'être, à la première évaluation ». Non. Elles
l'étaient à la SECONDE, après qu'une exécution de population complète avait déjà été
payée pour la première borne — et sous la forme d'une `ValidationError` pydantic brute
qui échappait au solveur et à la ligne de commande en trace de pile. `knob_pricer` expose
désormais `price.validate`, et le solveur valide les DEUX bornes avant d'évaluer quoi que
ce soit. Le cas vivant est `ifi_decote_taux` : déclaré `ge=0, le=1` mais refusé au-delà de
0,0125 par un validateur croisé, si bien qu'encadrer sur l'intervalle déclaré est une
chose raisonnable à faire et mérite une réponse en millisecondes. Le cahier des charges parlait d'un « déplacement de barème » ; le
faire supposerait un scalaire qui paramètre le barème, et ce scalaire n'existe pas dans le
modèle. Le refus le dit, et dit quoi ajouter pour le lever.

## D-093 — Le contrôle de partie double divisait une fuite constante par un net que le solveur annule exprès

> **Corrigé deux fois par D-094, le même jour.** La forme du brut donnée ci-dessous —
> `abs(receipts) + abs(transfers)` — est FAUSSE : elle somme les seaux avant la valeur
> absolue, donc elle s'effondre pour une réforme dont les deux bras sont dans le même
> seau. Et `firm_balance` ne partage pas la constante des ménages. Lire D-094 avec
> celle-ci.

**2026-09-08 · F2 · `src/impots/guards.py`, `tests/test_population.py`**

**Trouvé par le solveur, pas par une relecture.** La première résolution réelle — RSA
socle à 700 EUR, payé par la CSG — est tombée à sa troisième évaluation sur
`SectorBalanceError` : « écart de +305 719 EUR (+0,57 %) », alors que les instruments
avaient bougé de 3,7 md d'un côté et 3,67 md de l'autre. Le solveur ne s'est pas trompé.
La garde, si.

**Le mécanisme.** `sector_balance` comparait l'écart inexpliqué à
`max(|coût|, |coût reconstitué|, plancher)` — c'est-à-dire au **net**. Or la tolérance de
0,1 % a toujours été pensée comme « une part de la TAILLE de la réforme », et le net n'est
un bon indicateur de taille que tant que la réforme ne se compense pas elle-même. **Le
solveur de neutralité budgétaire en construit exprès qui se compensent** : il cherche la
valeur de bouton qui annule le net. À l'itérée qui intéresse l'utilisateur, le
dénominateur s'effondre et une fuite fixe est divisée par presque rien.

**Mesuré plutôt que supposé**, cinq réformes à 8 000 ménages :

| réforme | brut | net | résidu | /brut |
|---|---|---|---|---|
| rsa 700 | 3,545 md | +3 545 M | 303 660 EUR | 8,57e-05 |
| csg +0,5 pt | 5,625 md | −5 245 M | 2 188 EUR | 3,89e-07 |
| rsa 700 + csg 2,9 | 9,171 md | −1 699 M | 305 868 EUR | 3,34e-05 |
| rsa 700 + csg 3,05 | 10,862 md | −3 268 M | 307 200 EUR | 2,83e-05 |
| décote 60 % | 1,909 md | −1 909 M | −30 EUR | −1,59e-08 |

Le résidu est **constant à environ 305 000 EUR partout où le bras RSA apparaît**, et
quasi nul là où il n'apparaît pas. Ce n'est donc pas du bruit flottant — du bruit
flottant croîtrait avec le brut, et les 5,6 md de la CSG seule n'en produisent que
2 188 EUR. C'est la fuite de ce bras-là à travers des instruments non reportés, exactement
ce que `BALANCE_RTOL` existe pour tolérer, et elle ne rétrécit pas parce qu'un second bras
annule le titre. **Seul le dénominateur bouge.**

**Le correctif est une SECONDE allocation, pas un relâchement.** `BALANCE_GROSS_RTOL`
vaut 3e-4 — trois fois et demie le plus grand rapport mesuré, et **plus serré** que
`BALANCE_RTOL` à 1e-3. Comme le brut n'est jamais inférieur au net, une constante plus
serrée sur le brut ne peut pas relâcher une réforme que le test au net jugeait déjà : elle
ne mord que là où le test au net a cessé de vouloir dire quelque chose.
`test_the_gross_allowance_is_tighter_than_the_net_one` échoue si quelqu'un inverse
l'ordre.

**Trois tests qui tuent, dont un qui vise le correctif lui-même.**

* `test_an_offsetting_reform_is_not_accused_of_an_imbalance` rejoue les chiffres exacts de
  l'échec. Vérifié en neutralisant l'allocation brute : il tombe.
* `test_a_sector_that_moved_without_entering_the_cost_is_caught_at_a_zero_net` **vise le
  correctif** : même forme compensée, même net quasi nul, mais un milliard de transferts
  omis du coût. C'est la seule façon dont ce correctif pourrait être faux, donc c'est le
  test qui compte.
* `test_the_original_failure_still_breaches_under_the_gross_scale` rejoue la réforme à
  17,7 md de coût du travail annoncée à zéro — celle pour laquelle la garde a été écrite.
  Elle la refuse toujours, à 100 % du brut.

`firm_balance` portait la même forme et reçoit la même allocation : une réforme
entreprises qui monte un impôt pour en baisser un autre a le même net quasi nul et le même
brut en milliards.

**Le message dit désormais les deux échelles** — « x % du net et y % du brut » — parce
qu'un lecteur qui voit « +0,57 % » sans savoir de quoi ne peut pas juger si la garde a
trouvé quelque chose.

**Ce que cet incident dit du reste.** Une garde restée verte pendant toute la phase 1
n'était verte que parce que rien ne l'avait poussée dans le régime où elle se dégrade. F2
l'y a poussée dès sa première utilisation réelle. C'est le même motif que le biais
d'échantillonnage de D-074 : le contrôle existait, passait, et ne pouvait pas échouer là
où il fallait. **Chercher les gardes dont le dénominateur peut tendre vers zéro** est
désormais une question à poser aux suivantes.

### D-092, addendum — la première résolution réelle, de bout en bout

Enregistrée ici parce qu'une machinerie dont personne n'a jamais montré la sortie n'est
pas une machinerie dont on sait qu'elle marche.

    impots scenario save rsa_700 --reform … --source "variante interne : RSA socle à 700 EUR/mois"
    impots scenario compare rsa_700 rsa_700_af_40 --sample 8000
    impots scenario solve csg_activite_imposable --on rsa_700 --low 0.024 --high 0.20 \
        --sample 8000 --tolerance 300e6

**A/B.** RSA socle à 700 EUR/mois coûte **3,54 md**. Le même plus les AF deux enfants
portées à 40 % de la BMAF coûte **4,67 md**. Écart mécanique **+1,12 md**. Seul l'étage
mécanique est différencié ; les étages en bande sont affichés côte à côte.

**Solveur.** Coût +3,545 md au taux de droit courant (2,4 %), −178,454 md à 20 % : le
signe change, donc une racine existe dans l'intervalle. La sécante la trouve en **une
seule itération supplémentaire** — trois évaluations en tout :

    csg_activite_imposable = 2,743 %   coût résiduel -0,053 md EUR

Soit **+0,343 point de CSG activité imposable** pour financer le RSA à 700 EUR. Trois
tirages de population, pas quarante : c'est ce que la sécante achète, et c'est ce qui rend
l'outil utilisable la semaine où le PLF paraît plutôt que le mois suivant.

Le chiffre porte le bruit d'échantillonnage de 8 000 ménages et la tolérance déclarée de
300 M EUR le dit. Ce n'est pas un chiffrage publiable ; c'est la démonstration que la
chaîne tourne. Un chiffrage se ferait au tirage complet, avec une tolérance annoncée en
conséquence.

**Et c'est cette résolution qui a trouvé D-093** : à sa troisième évaluation — celle qui
approche la neutralité, donc exactement celle qui intéresse — la garde de partie double
a refusé la course. La garde avait tort, et elle avait tort depuis toujours ; il fallait
un outil qui pousse le net vers zéro pour le montrer.

## D-094 — Ce que la relecture adverse du 8 septembre a trouvé, y compris deux erreurs dans D-093 lui-même

**2026-09-08 · F2 · relecture en éventail, 5 dimensions, verdicts vérifiés indépendamment**

Avant de committer F2, cinq relecteurs indépendants ont attaqué l'incrément (solveur,
refus, garde D-093, refonte de l'interface, câblage), et chaque constat a été soumis à un
sceptique chargé de le RÉFUTER. Vingt et un constats bruts, neuf non réfutés. **J'ai
revérifié à la main chacun de ceux qui portent** — la règle permanente veut qu'un éventail
ne soit jamais le seul chemin vers un fait porteur, et elle a bien servi : sur les points
de garde, le sceptique avait raison sur deux points et tort sur un troisième.

### Les deux erreurs dans D-093, c'est-à-dire dans le correctif lui-même

**1. Le brut sommait les SEAUX, pas les mouvements.** J'avais écrit
`gross = abs(receipts) + abs(transfers)`, où `receipts` et `transfers` sont déjà des
sommes sur leur seau. Une réforme dont les deux bras sont dans le MÊME seau — RSA en
hausse, AF en baisse, tous deux des transferts — les voit se compenser AVANT que la valeur
absolue n'intervienne. Mesuré : sur « rsa 700 + af −20 % », la forme par seau lisait
2,713 md contre un mouvement réel de 5,165 md ; dans le cas extrême (rsa +3,673 md, af
−3,670 md) elle lisait 3,0 M contre 7,34 md, soit **0,04 % de la vérité**, et la garde
refusait une exécution correcte à « 10 % du brut ».

**C'est exactement le défaut que D-093 décrivait, dans une autre forme.** J'avais corrigé
la forme sur laquelle j'avais testé, et le test que j'avais écrit s'accordait avec elle.
Le brut est désormais la somme des |mouvements| instrument par instrument.

**2. `firm_balance` achetait de l'indulgence avec ce qu'elle ne mesure pas.** Le résidu du
côté entreprises mesure par construction le mouvement HORS `FIRM_COMPONENTS` ; l'échelonner
sur le mouvement DEDANS est un non-sens. Avec la constante des ménages, une réforme
compensée de 40 md achetait 12 M EUR d'indulgence et avalait une fuite réelle de 5 M EUR
hors périmètre — que l'ancienne garde au net attrapait.

**Et les deux côtés ne tolèrent pas la même chose**, ce qui est la raison de fond. Le
contrôle ménages sanctionne une FUITE : `revenu_disponible` traverse une cascade plus large
que les instruments reportés, d'où un résidu réel mesuré jusqu'à 8,55e-05 du brut. Le
contrôle entreprises n'en sanctionne aucune : `FIRM_COMPONENTS` est une seconde route
indépendante vers le même total OpenFisca, donc un instrument dans l'une et pas dans
l'autre EST le défaut à trouver. Mesuré sur quatre réformes réelles à période 2026, le
résidu entreprises vaut **5,43e-08 du brut** — de l'accumulation flottante, quatre ordres
de grandeur en dessous. D'où `FIRM_BALANCE_GROSS_RTOL = 1e-6`, environ dix-huit fois le
pire mesuré, contre 3e-4 côté ménages.

**Un constat de sceptique REJETÉ, vérifié à la main** : il affirmait que
`employer_contribution_delta` « s'annule algébriquement de `unexplained` ». Faux — il entre
dans `expected_cost` (vérifié : le coût reconstitué passe de −17,68 md à −0,00 md quand on
le fournit). Il gonfle bien le brut, mais c'est un mouvement légitime qui doit y compter
une fois.

### Le reste, corrigé

* **Le refus était une liste NOIRE.** `if quantity in BANDED_QUANTITIES` laissait passer
  « behavioral » (orthographe anglaise), « Behavioural », « cell-bound », « macro » avec
  une espace finale et la chaîne vide — tous répondus par un nombre mécanique convergé,
  indiscernable d'une vraie réponse. C'est le repli silencieux que ce module entier existe
  pour empêcher. Désormais `SOLVABLE_QUANTITIES = {"mechanical"}`, une liste BLANCHE : une
  liste noire refuse ce qu'elle reconnaît, et l'appelant qui a le plus besoin d'être refusé
  est celui qui a mal tapé le nom. **Et la ligne de commande refusait APRÈS avoir chargé la
  population** ; elle refuse maintenant en 0,4 s, ce qui est tout l'intérêt d'avoir rendu
  `refuse_banded` publique.

* **`load()` n'enveloppait que la validation du ReformSpec.** Une écriture tronquée, un
  marqueur de conflit ou un `created` manquant ressortaient en `JSONDecodeError` ou
  `KeyError` bruts — traces de pile pour `impots scenario list`, erreur 500 pour
  `GET /scenarios`, et **un seul mauvais fichier emportait tous les bons**.

* **Le nom d'un scénario était interpolé dans un chemin.** `Scenario(name="../plf2027")`
  écrivait hors du dossier, là où `available()` ne le liste jamais : un chiffrage qui a
  l'air enregistré et ne l'est pas. Refusé plutôt qu'assaini — renommer en silence ce
  qu'on vous a demandé est une surprise de plus.

* **« Aucune valeur de ce bouton n'y neutralise la réforme »** était une affirmation
  universelle tirée de deux échantillons. Un coût qui passe sous la cible et remonte à
  l'intérieur de l'intervalle a deux racines et deux bornes de même signe. Le message dit
  désormais ce qu'il sait.

* **`max_iterations=1` n'était pas honoré** : l'encadrement coûte deux évaluations, donc
  le plafond était dépassé du double. Refusé.

* **Le contrôle d'aller-retour de l'interface était unidirectionnel et posé à la mauvaise
  question.** Il ne signalait jamais les boutons que le panneau AJOUTE — charger un seul
  taux d'allègement en envoie deux — et il criait au loup sur un bouton dont la valeur
  ÉGALE le droit courant, parce qu'il se comparait à `reformSpec()` au lieu du contenu des
  champs. Et l'avertissement imprimait une cause unique codée en dur (« un même champ
  pilote plusieurs boutons ») y compris pour un bouton qui n'a aucun champ — ce qui est le
  cas de `scenarios/rsa_700_af_40.json`, dans ce dépôt même.

### Un test qui ne pouvait pas échouer, dans le test du refus phare

`test_the_solver_refuses_every_banded_quantity` était paramétré sur
`sorted(sc.BANDED_QUANTITIES)` — **le dictionnaire même qu'il teste**. Retirer une entrée
retirait son propre cas de test : la suite passait de 35 verts à 33 verts, tout verts,
pendant que le solveur répondait par un nombre à `quantity="cell_bound"`. C'est la forme
D-044 exactement, et elle s'était installée dans la garde du refus qui définit F2. Les
quatre noms sont désormais écrits en toutes lettres.

**Et la garde de D-093 n'était pas épinglée** : `test_the_gross_allowance_is_tighter...`
n'affirmait que `gross < net`, si bien que porter la constante à 9,9e-4 — tripler la
tolérance réelle — laissait toute la suite verte. Les deux constantes sont maintenant
épinglées à leur valeur, avec leur mesure en commentaire : une tolérance qu'on peut
élargir sans qu'un test s'en aperçoive est une tolérance que personne ne défend.

### Ce qu'il faut en retenir

Trois des neuf constats non réfutés portaient sur du code écrit le jour même **pour
corriger un autre défaut**, et deux d'entre eux sur le correctif de D-093. Un correctif
n'hérite pas de la vigilance qui l'a motivé. La question de D-093 — « le dénominateur de
ce contrôle peut-il tendre vers zéro ? » — doit se doubler d'une seconde : **« ai-je testé
le correctif sur une autre forme que celle qui m'a alerté ? »**

### D-094, addendum — `make full` ne pouvait pas enregistrer un échec

Trouvé en lisant la sortie du gate plutôt qu'en croyant sa ligne de journal, et c'est le
défaut le plus gênant de la journée parce qu'il porte sur l'instrument de discipline
lui-même. `reports/full_pass_log.md` s'annonce comme « le seul enregistrement attestant
que la suite complète est verte », et la règle attachée veut qu'« aucune passe de
relecture ne sorte sans une ligne plus récente que le travail qu'elle rapporte ».

    out=$$($(VENV)/python -m pytest -q -m "" 2>&1 | tail -1); \
    status=$$?; \

**`$?` après un tube rend le code de sortie du DERNIER maillon.** `tail` réussit toujours.
Donc `status` valait 0 quoi qu'il arrive, `result` valait **toujours PASS**, et
`exit $$status` sortait toujours 0. Le fichier était structurellement incapable de dire
autre chose que « vert ».

Pire : la sortie de pytest, capturée dans `$out` puis passée à un `sed` que BSD refuse
(`.*?` n'existe pas en ERE POSIX), n'était **jamais imprimée**. Une exécution complète en
échec n'affichait donc rien du tout — j'ai moi-même annoncé « gate PASSED, 60m45s » sur la
seule foi de cette ligne, et cette annonce ne reposait sur rien.

pytest écrit désormais dans un fichier, son code de sortie est lu directement, la ligne de
résumé est toujours affichée et un échec imprime ses quarante dernières lignes. Vérifié
**dans les deux sens** avec un faux pytest sortant 0 puis 1 :

    | PASS | ... | 816 passed, 2 skipped, 220 deselected |     exit 0
    | FAIL | ... | 3 failed, 813 passed |                      exit 2

Les lignes antérieures du journal portent un avertissement en tête de fichier : elles ne
sont pas des preuves. La colonne `tests` vide y est le symptôme visible du même bug.

**Ce que ça ajoute aux deux questions de D-093 et D-094** : quand un contrôle ne peut
produire qu'un seul verdict, il n'a jamais rien vérifié. Un test vert dont on n'a jamais
vu la version rouge est une hypothèse, pas une mesure — ce que ce projet impose déjà aux
gardes du modèle, et qu'il n'avait pas imposé à son propre outillage.

## D-095 — La préparation de F1 : un triage qui se vérifie, un barème qui se prouve rouge, et un chiffre de couverture de 3,4 %

**2026-09-08 · F1 · `src/impots/plf_coverage.py`, `src/impots/chiffrages.py`,
`scripts/write_plf_coverage.py`, `docs/PLF2027_COVERAGE.md`**

Les deux pièces que le cahier des charges de préparation demandait, plus ce que leur
construction a trouvé.

### 1. Le triage, bâti sur le texte réel et vérifié par des tests

Le PLF 2027 n'existe pas ; deviner ses numéros d'articles serait la fabrication que ce
projet interdit. Le triage est donc bâti sur le **texte 2026 réel** — Assemblée nationale
n° 1906, manifesté `88ef308e62a2`, découpé mécaniquement en 82 articles dont 29 fiscaux —
et ce sont les **catégories**, pas les numéros, qui sont le livrable.

**Le chiffre est mauvais et c'est l'intérêt du document. 1 article sur 29 — 3,4 % —
produit aujourd'hui un chiffre défendable.** Trois autres ont leurs paramètres dans
l'arbre mais aucun contribuable dans la population pour les exercer ; vingt-trois sont
hors structure ou hors données. Le savoir en septembre est une limite préenregistrée ; le
découvrir en octobre serait une excuse.

**Le triage est du CODE VÉRIFIÉ, pas de la prose.** `tests/test_plf_coverage.py` contrôle
que chaque bouton nommé existe verbatim dans le modèle de fil et que chaque chemin de
paramètre résout au 2026-01-01. Un document qui dérive du code qu'il décrit est pire que
pas de document : il sera cru le jour J, sous pression. Le `.md` est **généré** et un test
échoue si quelqu'un l'édite à la main.

### 2. Deux drapeaux que les trois cases ne pouvaient pas porter

Le cahier des charges demandait exactement une case par article. « Chiffrable » cachait
deux questions indépendantes, et les confondre est la façon même dont un zéro confiant se
publie : `engine_ready` (les paramètres existent et la formule les lit) et
`population_can_exercise` (la population contient des contribuables que la mesure atteint).

**L'article 2, la CDHR, a forcé la distinction.** Ses cinq paramètres résolvent, sa
variable tourne, et elle mord : **−75 836 EUR** sur un foyer à 2 M EUR de dividendes. À la
lettre, c'est un « petit bouton » — du câblage. Mais la CDHR porte le taux moyen à 20 %, et
un contribuable purement salarié le dépasse déjà : sur une population **sans revenus du
capital**, l'assiette est vide par construction et le câblage publierait 0,00 EUR contre un
rendement d'environ un milliard. Une case ne dit pas cela ; deux drapeaux le disent.

### 3. Quatre pièges qui auraient produit un faux chiffre en octobre

* **L'article 9 (dons Coluche) aurait chiffré exactement zéro.** Le bouton est exact et le
  paramètre vivant — mais **l'arbre de référence porte déjà le plafond à 2 000 EUR depuis
  2025-01-01**, la mesure ayant été votée. Chiffrer l'article contre cette base, c'est
  chiffrer un changement contre lui-même. Et même contre un contrefactuel à 1 000 EUR,
  l'assiette imputée va de 157 à 447 EUR par décile sans dispersion intra-décile : aucun
  foyer de cette population n'atteint l'un ou l'autre plafond.
* **L'article 11 (CVAE) n'est pas exprimable avec un bouton.** `cvae_taux_max` ne gouverne
  que la tranche au-dessus de 50 M EUR. Mesuré : cette tranche porte **71,9 %** de la CVAE
  de référence, et **205 959 des 213 730** redevables pondérés — 96,4 % — sont en dessous
  et ne voient aucun changement de taux, alors que l'article déplace les six coefficients
  du barème ensemble.
* **L'article 5 cache une mesure atteignable dans un paquet de vingt-trois.** Son 12°
  abroge l'article 199 quater F, la réduction pour frais de scolarité, pour laquelle trois
  boutons existent et sont vivants. Le paquet est hors structure ; cette sous-mesure ne
  l'est pas.
* **Une réforme CDHR déplacerait les déciles sans déplacer la ligne IR affichée.** Mesuré :
  porter `taux_cdhr` de 20 à 30 % déplace `revenu_disponible` de 205 400 EUR et
  `impot_revenu_restant_a_payer` de rien du tout — or c'est ce dernier que le registre
  publie comme `ir`. Comme `STATE_RECEIPTS` ne porte aucune ligne CDHR, **la garde de
  partie double refuserait la course**, ce qui est le bon comportement et constitue le
  prérequis de câblage à satisfaire avant que le bouton puisse exister.

### 4. Le barème de notation, avec les trois questions posées à la naissance

`chiffrages.py` : un cas YAML par chiffrage, la tolérance **déclarée avant** que le chiffre
officiel existe, le comparateur avec sa discipline complète (source, millésime, périmètre,
net de quoi), et une note `within`/`outside` avec sa direction.

* **Question 1 — le dénominateur peut-il tendre vers zéro ?** Oui, et pas en théorie : un
  article chiffré « sans impact budgétaire » publie 0. Une tolérance purement relative
  exigerait alors une précision infinie. Une tolérance est donc une **paire**, relative et
  absolue, l'indulgence étant la plus large des deux, et `binding` dit laquelle a tranché.
  C'est la leçon de D-093 appliquée **avant** l'incident.
* **Question 2 — testé sur une autre forme ?** La notation est exercée sur un comparateur
  nul, un comparateur négatif, des signes opposés, et chaque borne mordant à son tour.
* **Question 3 — a-t-on déjà vu ce contrôle échouer ?** `test_the_harness_grades_red` est
  le premier test du fichier : un cas d'essai portant un écart connu doit être noté
  `outside` avant qu'aucun cas réel n'entre. Un barème dont on n'a jamais vu le voyant
  rouge n'est pas un barème, c'est un espoir — exactement le défaut de `make full`.

**Et la règle qui fait tenir le reste : `verify_tolerance_unchanged` lit la tolérance dans
l'HISTORIQUE GIT, pas dans le fichier.** Une tolérance élargie une fois le chiffre officiel
connu transforme chaque manqué en réussi et laisse un fichier trait pour trait identique à
un fichier honnête. Le fichier ne peut pas attraper cela — il ne montre que sa dernière
version. Git s'en souvient. Un cas jamais committé refuse d'être noté : **le commit EST le
préenregistrement**.

**L'intégrité est de qualité INTERNE et le dit.** Le témoin est un hash de commit dans un
dépôt privé plus une ligne datée dans le journal de passe. C'est honnête en interne et ne
convaincrait personne à l'extérieur, le propriétaire du dépôt pouvant réécrire l'histoire.
Si la crédibilité externe devient un enjeu, il faudrait un horodatage **hors du dépôt** au
moment de l'enregistrement — un commit public, un hash publié. C'est une décision du
propriétaire : elle est **enregistrée comme option, pas prise**.

### 5. Une garde née d'une erreur de mesure de la session

En sondant si `taux_cdhr` était un bouton vivant, j'ai écrit 0,30 dans `baseline()` et
comparé le résultat à `baseline()` — **le même objet**, la fonction étant mémoïsée. L'impôt
n'a pas bougé et la lecture évidente était « paramètre mort, huitième artefact amont ». Il
n'est pas mort : sur deux systèmes distincts il porte la CDHR de −75 836 à −281 236. La
mesure comparait un arbre à lui-même — la forme D-044 dans un script de cinq lignes.

Le chemin de production n'a jamais été en cause (`Reform(tbs)` clone d'abord, ce que
`test_no_mutation` prouve). Mais le piège était réel, alors `update_existing` **refuse
désormais une écriture visant l'arbre partagé de `baseline()`**, avec son test qui tue et
son test miroir prouvant qu'un système à soi passe toujours. Une garde qui ne se déclenche
qu'en dehors du chemin de production n'y coûte rien et convertit une réponse fausse
silencieuse en message.

**Et j'ai refait la même faute une seconde fois dans la même session**, en lisant
`totals` au lieu de `totals_reform` pour juger le bouton CVAE : delta +0,000, « bouton
mort ». C'est le piège de D-071 mot pour mot — trois boutons employeur avaient failli être
déclarés morts parce qu'on regardait la mauvaise ligne. Corrigé : le bouton porte
−0,759 md. **Deux fausses alertes en une session, toutes deux de la forme « comparer une
chose à elle-même ».** La quatrième question à poser : *de quoi ce nombre est-il la
différence, exactement ?*

## D-096 — L'ERFS n'arrive pas : la règle d'interruption devient dormante, pas morte

**2026-09-08 · décision du propriétaire, consignée**

L'accès à l'ERFS n'est **pas disponible dans un avenir prévisible**. Le projet planifie
désormais **sans**.

**Ce qui ne change pas.** `docs/PHASE1C_ERFS.md` n'est ni périmé ni annulé : il est
complet, et il se déclenche exactement tel qu'il est écrit — test d'acceptation compris,
le backtest d'indexation du barème — le jour où des microdonnées de revenus réelles
arrivent. La règle d'interruption garde son rang au-dessus de tout. Ce qui change est
l'hypothèse de planification, pas le plan.

**Ce qui change.** Un balayage, un commit : toute bannière, tout avertissement, tout
document qui disait ou laissait entendre « en attendant l'ERFS (bientôt) » dit désormais
« en attendant des microdonnées de revenus réelles ». Même honnêteté, sans fausse
imminence — `DATA_DOWNLOADS.md` ne dit plus « soumettre maintenant, 2 à 6 semaines de
délai », `WHAT_NOW.md` ne dit plus « quand Progedo livrera », `ROADMAP_NEXT.md` ne dit plus
« la file est à cinq semaines et plus », et `calibrate.py` parle de la propriété générale
d'une source rétrospective plutôt que de l'ERFS.

**Et le triage continue de nommer l'ERFS comme la serrure.** Une porte lointaine reste une
porte : les articles classés `population_blind` portent un champ `unlock` obligatoire — le
dataclass refuse de se construire sans — qui dit ce qui ouvrirait chacun. Le document ne
doit mentir dans aucun des deux sens : ni promettre une arrivée, ni faire passer un refus
de données pour un refus définitif. Le contraire d'une fausse imminence n'est pas un faux
définitif.

**La conséquence de fond, qui n'est pas administrative.** Les revenus du capital resteront
absents de la population. C'est ce qui rend la CDHR non chiffrable (D-095), et c'est ce qui
ferme les canaux comportementaux de capital que PHASE3_SPEC refusait déjà « jusqu'à
l'ERFS ». F1b existe pour tester si des statistiques **publiées** par tranche ouvrent une
partie de cette porte sans microdonnées — la question est posée, la réponse n'est pas
supposée.

## D-097 — Gate F1b : le PFU est imputable depuis des données publiées, la CDHR ne l'est pas

**2026-09-08 · `docs/F1B_CAPITAL_GATE.md`**

Le refus de l'article 2 avait nommé le trou — la population ne porte aucun revenu du
capital. Ce gate demande ce que les données **publiées** permettent, puisque les
microdonnées ne viendront pas (D-096). Verdict : **oui pour le PFU, non pour la CDHR.**

**Le cahier des charges se trompait sur sa source.** Il annonçait « des revenus de
capitaux mobiliers par tranche de RFR » dans les statistiques IR de la DGFiP. Ce n'est pas
publié. Ce qui l'est, dans DGFiP Statistiques n° 41 (tableaux manifestés), c'est l'**impôt
hors barème par fractile** — un impôt, pas une assiette. L'assiette est **dérivable** :
10,32 Md€ de PFU au titre de l'IR divisés par 12,8 % donnent 80,6 Md€, à comparer aux
70,09 Md€ de RCM plus une vingtaine de milliards de plus-values du tableau 1, soit 9 %
d'écart — que l'option pour le barème explique. Deux routes indépendantes vers le même
ordre de grandeur, ce qui rend la dérivation utilisable.

**Et il se trompait sur la raison du refus attendu**, ce qui est la partie réutilisable.
Il prévoyait que la CDHR resterait refusée « parce qu'elle mord dans le centile supérieur,
où une imputation par tranche est trop grossière ». Or la granularité publiée descend au
**millime** — le tableau 2 porte « dont dernier centième » et « dont dernier millième ».
L'argument de finesse ne tient donc pas. Le vrai refus est plus fort :

**Un impôt PROPORTIONNEL ne dépend que de l'assiette totale de chaque cellule, jamais de
sa dispersion interne.** L'artefact « tous les foyers d'une cellule reçoivent la même
base » n'entame pas le rendement d'un changement de taux du PFU : la somme est la somme.
**La CDHR, elle, est définie sur un RATIO** — elle porte le taux moyen à 20 % du RFR pour
ceux qui sont en dessous. Une imputation uniforme donne à tous les foyers d'une cellule le
même ratio, donc les met tous du même côté du seuil : la CDHR frapperait les 41 000 foyers
du millime ou aucun, selon le côté où tombe la moyenne. Le rendement serait un artefact du
placement de cette moyenne, sautant de zéro à des milliards au franchissement d'un seuil
que rien dans les données ne fixe.

Ce n'est pas « trop grossier », c'est **mal posé** : la mesure est définie sur une
dispersion que la source ne contient à aucun fractile. **Et la règle généralise** : toute
mesure définie sur un seuil, un ratio ou un taux moyen individuel est hors d'atteinte
d'une imputation par fractile, quelle que soit sa finesse — ce qui inclut le plafonnement
de l'IFI et toute contribution différentielle future. C'est la même forme que le plafond
des dons Coluche (D-095) : un bouton correct sur une assiette dont l'imputation a aplati
la dispersion qui portait tout l'effet.

**Rien n'est construit.** Le gate décide que la question a une réponse ; construire
l'imputation RCM appartient au propriétaire. Son prix est permanent : deux totaux de plus
dépensés au registre de calibration, et une catégorie de revenu de plus dont la
distribution intra-cellule est une fiction déclarée. Ce qu'elle achèterait : les boutons de
taux du PFU au niveau population, la CSG sur les revenus du capital, et une part de
l'incidence du haut de distribution. Ce qu'elle n'achèterait pas : la CDHR.

## D-098 — F4 : la fiche de chiffrage, et trois branches que seul un rendu réel a montrées

**2026-09-08 · `src/impots/fiche.py`, `tests/test_fiche.py`, `impots fiche`**

Une fiche par réforme, assemblant tout l'étage d'honnêteté. **Elle reprend le plan d'une
évaluation préalable** — mêmes six sections, même numérotation, relevés sur les 599 pages
du PLF 2026 manifestées en F1 — parce que c'est le document qu'un lecteur français de
chiffrage sait déjà lire. Qui sait où est le 4.2.1 y trouvera notre chiffre.

**Ce qui diffère, c'est ce que le 4.2.1 CONTIENT.** La fiche officielle y met un nombre
dans un tableau de cinq lignes. « Non chiffrable » figure dans cinq des vingt-neuf fiches
fiscales du PLF 2026, ce qui est honnête ; les vingt-quatre autres donnent un point sans
intervalle, ce qui ne l'est pas. La nôtre y met la pile : mécanique, bande avec son grade,
canaux, éventail avec son bandeau, avertissements.

**Trois règles, chacune avec son test qui tue** — et un générateur de rapport est
exactement l'endroit où elles se relâcheraient, parce qu'un nombre nu se met mieux en page
qu'un nombre qualifié.

1. **Un chiffre mécanique ne paraît jamais seul** : soit la bande est à côté, soit la
   RAISON qu'il n'y en ait pas est à côté.
2. **L'éventail ne se rend jamais sans son bandeau d'hypothèses.** Le modèle de fil rend
   déjà le bandeau obligatoire, l'interface a son propre test ; la fiche est la troisième
   surface et ne devait pas être la faible.
3. **Une section qu'un modèle ne peut pas remplir est MARQUÉE, pas omise.** Les sections
   1, 2, 3 et 5 — diagnostic, options, dispositif juridique, consultations — sont des
   jugements, pas des grandeurs. Les supprimer laisserait un document qui RESSEMBLE à une
   évaluation préalable complète, et un lecteur en conclurait que le jugement manquant a
   été porté. C'est la différence entre un chiffrage et une contrefaçon.

### Trois défauts que seul un rendu sur réponse réelle a montrés

* **`BehaviouralChannel.band` est un `BehaviouralBand`, pas une paire.** Mon
  `c.band[0]` plantait — et la branche n'avait jamais tourné en vrai, parce qu'aucun canal
  ne s'appliquait aux réformes essayées d'abord. Une branche non testée dans un moteur de
  rendu dont le métier est d'imprimer des bandes.
* **Les canaux étaient imbriqués dans la branche « bande présente ».** Un allègement
  employeur ne produit AUCUNE bande d'ensemble — la réforme dépasse le support des
  élasticités, donc le grade est « illustrative » et la bande est retenue — pendant que
  deux canaux s'appliquent avec leurs bandes propres, dont **+17 113 emplois
  [15 056 ; 19 093]**. Le lecteur recevait « pas de bande » et rien d'autre. **Retenir ce
  qui a été calculé sous-estime aussi gravement qu'un point nu surestime.** Les canaux
  sont désormais imprimés dans les deux cas, avec la phrase qui empêche de les additionner
  ou de les prendre pour la bande d'ensemble.
* **La typographie mangeait la prose.** `.replace(",", …)` appliqué à des f-strings
  entières transformait les virgules de phrase en séparateurs de milliers : « EEC
  household structure, synthetic incomes » sortait « structure  synthetic ». Et `:.4g`
  rendait 9 770 165 637 en « 9.77e+09 » — de la notation scientifique, dans un document
  français, à propos d'euros. Corrigé par des formateurs qui ne touchent que des nombres.

### Et la forme D-044 une seconde fois dans la même session

`test_every_section_a_model_cannot_write_is_printed_with_its_reason` était paramétré sur
`fiche.NOT_OURS` — **la collection qu'il teste**. Vider `NOT_OURS` laissait les 27 tests
verts pendant que la fiche supprimait silencieusement toutes ses sections déclinées.
C'est exactement ce que j'avais corrigé quelques heures plus tôt dans
`test_scenarios.py`, et je l'ai réécrit. Les quatre numéros sont maintenant en toutes
lettres, avec un test séparé qui vérifie que la collection les contient.

**Le motif mérite d'être nommé comme habitude et non comme accident** : quand on écrit un
test paramétré, la source des paramètres doit venir d'ailleurs que du code testé. Que je
l'aie refait le jour même où je l'ai documenté dit que la vigilance ne suffit pas — il
faut la question, posée à chaque test paramétré : **d'où viennent ces paramètres ?**

**Et mon propre kill test s'est trompé d'abord** : muter `NOT_OURS = (` en `= () or (`
produit `() or (…)`, qui vaut le tuple non vide. Le test passait, j'ai cru qu'il ne mordait
pas, et c'était la mutation qui était fausse. Vérifier qu'un test échoue demande de
vérifier aussi que la mutation fait ce qu'on croit.

## D-099 — Gate M0 des trajectoires : l'arbre ne code pas l'avenir, et le moteur mourait en 2029

**2026-09-08 · `docs/M0_TRAJECTORIES.md`, `docs/F3_SPEC.md`**

**La feuille de route annonçait « l'arbre daté qui code déjà l'avenir ». Mesuré : deux
paramètres sur soixante-deux.** `exists_at` répond « oui » jusqu'en 2032 pour presque tout,
et c'est trompeur — openfisca reconduit indéfiniment la dernière valeur datée. La bonne
mesure n'est pas l'existence mais le CHANGEMENT.

* **Ménages** : 4 chemins sur 52 bougent après 2026, et une seule fois, en 2027 (bmaf, RSA,
  PPA base et bonification). À partir de 2028, tout l'étage est le droit 2027 reconduit.
* **Entreprises** : 2 chemins sur 10 — la CVAE et son dégrèvement — portent une vraie
  trajectoire, et le paramètre **cesse d'exister** en 2030 : l'arbre encode la suppression.
  Exécuté : CVAE 3,282 md en 2026 puis 2,222 / 1,066 / 0,000, et un décrochage de 9,3 md
  entre 2026 et 2027 qui est l'expiration de la CEBGE.

La feuille de route avait donc raison sur ses deux exemples et tort sur la généralisation.

**Le problème central que cela crée, et il est structurel.** Le barème IR est **déjà gelé**
dans la référence à partir de 2026. Chiffrer un gel de barème contre cette référence, c'est
chiffrer un changement contre lui-même : zéro par construction — la forme exacte de
l'article 9 du PLF 2026 (D-095) et du champ `mirror` de la suite de backtests. Le premier
livrable de F3 n'est donc pas un bouton, c'est **une seconde référence** : une
contrefactuelle indexée sur une hypothèse de prix déclarée. Et les deux chiffres se
publient ensemble, parce qu'ils répondent à deux questions différentes et sont vrais tous
les deux.

**Un défaut trouvé en ouvrant le gate.** Le moteur entreprises tournait en 2026, 2030 et
2031 et **plantait en 2029** : `cvae/bareme/pente_t3.yaml` portait `value: 6e-05`, que YAML
1.1 lit comme la CHAÎNE `'6e-05'` faute de point décimal. La chaîne traversait tout et
mourait à la multiplication, une seule année, au milieu de la plage qu'une phase de
trajectoires balaie par définition. Personne ne l'avait vu parce que personne n'avait fait
tourner 2029.

**C'est notre fichier, pas celui d'openfisca.** Mon premier réflexe a été de le classer en
huitième artefact amont ; vérification faite, il est à nous. Troisième fois de la journée
qu'une vérification avant annonce change la réponse.
`test_every_parameter_value_we_ship_is_a_number` balaie désormais les 41 fichiers de
paramètres et refuse toute valeur non numérique — en se limitant structurellement aux blocs
`values:` datés, parce que le magasin comportemental écrit aussi `value:` et y met
légitimement un dictionnaire.

**Et ce garde a d'abord été INERTE**, ce qui est le fait le plus instructif du lot. Il
testait `isinstance(key, str)` sur les dates ; or YAML rend un `datetime.date`. Aucune clé
ne correspondait, le bloc n'était jamais inspecté, et le test passait avec la valeur cassée
en place. Trouvé uniquement parce que j'ai exigé que le kill test morde **et vérifié que ma
mutation faisait bien ce que je croyais** — une première tentative de mutation
(`= () or (…)`) laissait le tuple non vide et m'avait fait croire à un test faible alors
que la mutation était fausse.

**Quatre contrôles inertes en une session** — le test paramétré sur `BANDED_QUANTITIES`, la
constante non épinglée de D-093, le test paramétré sur `NOT_OURS`, et ce garde de dates.
La troisième question permanente (« a-t-on déjà vu ce contrôle échouer ? ») n'est pas une
précaution occasionnelle : c'est la seule chose qui les a tous trouvés.

## D-100 — Gate M0 du REI (F5) : le bâti valide à +0,9 %, le non bâti manque 60 %

**2026-09-08 · `docs/M0_REI.md`**

**Verdict : oui pour le foncier bâti, non en l'état pour le non bâti.** Rien construit
au-delà du gate.

**Le marais annoncé est réel et a maintenant une carte.** REI 2025 : 34 907 communes ×
**1043 colonnes**, 112 Mo, manifesté. Quatre pièges, relevés en les rencontrant :

1. **le CSV est en LATIN-1** — la lecture UTF-8 échoue à l'octet 10082, et un
   `errors="replace"` donnerait des libellés corrompus sans lever d'erreur ;
2. séparateur point-virgule, décimal virgule ;
3. **le foncier n'est jamais nommé « foncier »** : chercher `FONCIER|BÂTI` dans les titres
   ramène 9 variables sur 1043 et **aucune n'est une base ni un taux de TF**. Les vraies
   colonnes ont des titres en « FB » (118) et « FNB » (57). Un gate qui aurait cherché le
   mot aurait conclu que le fichier ne porte pas la taxe foncière ;
4. la CFE occupe **500 des 1043 colonnes** — ce n'est pas un fichier de TF.

**La validation, et son périmètre est la moitié de l'information.** DGFiP Statistiques
n° 46 met en avant **55,1 Md€**, qui **inclut taxes annexes et frais de gestion** ; le
comparateur d'une reconstitution base × taux est la phrase suivante : « hors taxes annexes
et frais de gestion, **43,1 Md€** ». Prendre le chiffre mis en avant aurait donné −21 % et
fait conclure à un modèle faux.

    commune seule                40,154 md   -6,84 %
    commune + intercommunalité   42,773 md   -0,76 %
    + TSE, GEMAPI, TASA          43,483 md   +0,89 %

Les deux dernières encadrent le publié à moins de 1 %. Le document ne dit pas lesquelles de
ces strates comptent parmi les « taxes annexes » qu'il exclut : les deux sont données,
aucune n'est choisie.

**CE QUE CETTE VALIDATION NE PROUVE PAS.** La publication n° 46 est tirée du même REI. La
comparaison valide **la lecture du fichier** — bonnes colonnes, bon facteur cent sur les
taux — et **pas un modèle**. C'est la distinction du registre de calibration appliquée à
une source externe : une ligne qui colle parce qu'elle vient de la même source ne dit rien
du monde.

**Le non bâti échoue et l'échec est publié.** Ma lecture donne 1,089 md contre 2,7 md
publiés, soit **−59,7 %**. Strates manquantes non trouvées dans le temps du gate. La
tolérance n'est pas élargie pour l'absorber : le bâti est validé, le non bâti ne l'est pas,
les deux faits sont épinglés, et F5 devrait traiter le non bâti comme un M1 à part entière.

**Et une limite que la feuille de route ne mentionnait pas.** Le REI est **communal** ; la
population de ce projet n'a ni commune ni valeur locative. **Une TF par ménage n'est pas
atteignable depuis ce fichier seul.** F5 livrerait un modèle par commune — donc pas
d'incidence par décile sans une source supplémentaire. Une phase qui promettrait la
distribution promettrait ce qu'elle ne peut pas tenir.

## D-101 — F3 M1 : les deux références, et le gel du barème enfin chiffrable

**2026-09-08 · `src/impots/trajectoires.py`, `tests/test_trajectoires.py`**

Le gate M0 (D-099) avait mesuré le problème : le barème IR est **gelé depuis 2026** — 2026,
2027 et 2028 portent tous les seuils de 2025 — donc chiffrer un gel contre le droit courant
rend zéro, parce que le droit courant EST le gel.

**Deux références, et chaque chiffre nomme la sienne.**

* `reconduit` — le droit courant prolongé. C'est la référence **légale** : personne n'a
  voté d'indexation au-delà de 2025, et l'impôt dû en 2028 se calcule vraiment sur les
  seuils de 2025.
* `indexe` — le même droit dont le barème, la décote et le plafond par demi-part sont
  indexés sur une hypothèse de prix **déclarée**.

**Mesuré de bout en bout sur le moteur réel**, gel du barème en 2028 :

    référence « reconduit »   +0,000 md€
    référence « indexe » (2 %) −7,073 md€

**Les deux sont vrais et répondent à deux questions différentes.** Le zéro n'est pas un
bug : il n'y a rien à geler qui ne le soit déjà. Les 7,07 md sont l'impôt discret, et il
n'existe comme nombre que parce que la seconde référence existe. C'est la démonstration que
`indexe` était nécessaire et non un raffinement.

**Aucun défaut nulle part.** `reference` est obligatoire, et une liste BLANCHE la valide —
D-094 : une référence mal orthographiée qui retomberait sur « reconduit » publierait un
zéro pour un gel et l'appellerait un résultat. `indexe` exige en plus l'hypothèse ET sa
source.

**L'hypothèse est FOURNIE, jamais prévue.** Les refus de la phase 4 tiennent : ce projet ne
prévoit pas l'inflation. Chiffrer « si les prix montent de X » est de l'arithmétique ;
choisir X ne nous appartient pas, et `Indexation` refuse de le faire — pas de taux par
défaut, source obligatoire.

**Deux honnêtetés portées par chaque résultat plutôt que par un document annexe :**

* `indexe` est une **borne inférieure** de ce qu'une vraie indexation coûterait — une loi
  d'indexation déplace aussi les planchers et plafonds de la déduction de 10 %,
  l'abattement sur les pensions et plusieurs plafonds spécifiques de quotient familial, que
  ce module n'expose pas ;
* **la population n'est pas vieillie** — M2 n'existe pas, donc une trajectoire applique le
  droit d'une année future à une population 2024. `Trajectory.caveat` le dit sur chaque
  résultat.

**Le test qui compte** est `test_a_freeze_against_current_law_costs_exactly_nothing`, et
son moteur d'essai **dérive** le zéro d'un écart de seuils au lieu de le coder en dur — la
première version rendait 0,0 dans les deux branches et aurait passé quoi qu'il arrive
(ruff l'a signalé, `RUF034`). Son jumeau
`test_the_indexed_reference_is_not_folded_into_the_measure` vérifie la soustraction :
sans elle, une réforme nulle chiffrée contre `indexe` reviendrait chargée du coût entier
de l'indexation — un très gros nombre attribué à une mesure qui ne fait rien.

## D-102 — F3 M2 : vieillir la population, et perdre sa calibration en le faisant

**2026-09-09 · `src/impots/uprating.py`, `src/impots/reporting.py`, `reconcile.py`**

**Vieillir, jamais re-synthétiser.** Re-tirer une population chaque année déplacerait
l'identité des ménages, et une trajectoire par ménage ne voudrait plus rien dire : le
« même » ménage en 2028 serait un autre tirage. Les lignes, la structure et les poids sont
donc laissés tels quels ; seules les colonnes monétaires bougent, sur **deux indices** —
salaires et prix — parce qu'ils ne montent pas ensemble et qu'un indice unique le
supposerait en silence.

**Ce que cela coûte est le milestone, pas une note de bas de page.** Une population
vieillie **n'est plus calibrée** : tous les totaux dépensés au registre l'ont été sur
l'année de base, et il n'existe pas de total publié pour une année future. Une
réconciliation de 2028 comparerait un simulé 2028 à un publié 2024 — deux chiffres qui ne
portent pas sur la même chose.

**D'où la condition d'achèvement, et elle est tenue.** `reporting.Line` refuse tout verdict
de tolérance quand `population_year` et `comparator_year` diffèrent, **avant même d'évaluer
l'écart** — un verdict lâche se lirait comme une validation, et il n'y a rien ici à
valider. Mesuré de bout en bout sur la population réelle :

    année de base   2 calibrées, 2 hors cible, 9 dans la tolérance, 8 hors tolérance
    vieillie 2028   21 lignes « not comparable (population vieillie) », aucune ne passe

Vérifié dans les deux sens : retirer le refus fait tomber les tests du vieilli, et
remplacer « les millésimes diffèrent » par « un millésime est posé » fait tomber ceux de
l'année de base.

**Le vieillissement change matériellement le chiffre**, ce qui justifie le milestone plutôt
que de le décorer. Gel du barème 2028 contre la référence indexée :

    population 2024 figée   -7,073 md€
    population vieillie     -8,339 md€   (+18 %)

Les revenus montent, davantage de foyers franchissent des seuils gelés, et le gel mord plus
fort. Chiffrer une trajectoire sur une population figée sous-estime donc l'impôt discret.

**Trois limites, portées par chaque résultat parce qu'aucune n'est visible dans la
sortie** : la structure des ménages ne bouge pas ; les poids ne sont pas recalés (il
n'existe pas de marge publiée pour une année future) ; les âges n'avancent pas
délibérément — une population plus vieille avec autant d'enfants serait pire qu'une
population uniformément figée. Ce qui est chiffré est « ce droit, sur la France
d'aujourd'hui, avec l'argent de demain ».

**Et un doublon supprimé au passage.** Le formateur typographique français avait été écrit
deux fois : une fois dans `fiche` (D-098) et une seconde, en pire, dans le premier jet
d'`uprating`, qui imprimait « +2.5% » dans un document français. `num_fr` et `pct_fr` vivent
désormais dans `reporting`. **Le déplacement a changé un défaut** — la version partagée
partait sur une décimale là où celle de la fiche en avait zéro — et deux tests de la fiche
l'ont attrapé. Un formateur dupliqué est un formateur qui diverge ; un défaut déplacé est
un défaut qui se propage.

## D-103 — F3 M3 : les boutons gagnent une dimension temporelle, et chaque année dit sur quoi elle repose

**2026-09-09 · `src/impots/trajectoires.py`, `tests/test_trajectoires.py`**

Chaque bouton devient chiffrable année par année, et chaque résultat porte sa **base** :

* `legislated` — un législateur a fixé les paramètres de cette année ; la valeur de
  l'arbre EST la loi, et le chiffre ne dépend d'aucune hypothèse ;
* `reconducted` — aucun législateur ne s'est encore prononcé, l'arbre reporte la dernière
  valeur. C'est juste en droit tant que rien n'est voté, **et très probablement dépassé** —
  ce qui est exactement pourquoi le choix de référence décide alors du chiffre.

**La frontière est MESURÉE, pas déclarée.** `last_legislated_year` parcourt les chemins de
paramètres connus année par année et rend la dernière année où une valeur change. Mesuré :
**ménages 2027**, **entreprises 2030**. Coder 2027 et 2030 en dur ferait mentir le module
la première fois qu'une LFI légifère plus loin ; les dériver fait que la classification se
met à jour toute seule et que le test d'épinglage tombe bruyamment à la place.

**La disparition d'un paramètre compte comme une législation.** Les paramètres de la CVAE
**cessent d'exister** en 2030 : cette absence EST la suppression, pas un trou. C'est ce qui
rend le côté entreprises légiféré jusqu'en 2030 et non 2029. Vérifié en cassant la règle —
ignorer les années manquantes ramène la frontière à 2029 et fait tomber deux tests.

**Une troisième situation, que la spec n'avait pas prévue, est sortie de l'écriture.**
Indexer une année **déjà légiférée** — 2026, par exemple — ne rétablit pas une indexation
manquante : cela **écrase un barème voté** par une contrefactuelle. C'est légitime, et ce
n'est pas la même affirmation qu'indexer 2029. Les deux notes sont désormais distinctes,
et l'avertissement porte le mot ATTENTION.

**Mesuré de bout en bout**, IS ramené à 26 % :

    2026  -3,105 md€  legislated     (la CEBGE encore active élargit l'assiette IS)
    2027  -2,735 md€  legislated
    2028  -2,735 md€  legislated
    2029  -2,735 md€  legislated
    2030  -2,735 md€  legislated
    2031  -2,735 md€  reconducted

**Et une lenteur qui n'était pas un détail.** `last_legislated_year` lit 52 chemins sur
neuf années, et `basis_for` l'appelait une fois par année de chaque balayage : la suite de
tests passait de 18 s à **181 s** sans faire tourner le moteur une seule fois. Mise en
cache — l'arbre ne change pas dans un processus, donc le cache ne peut pas rancir.

## D-104 — Trois contradictions entre PHASE6_SPEC et le terrain, relevées avant de l'exécuter

**2026-09-09 · lecture de `docs/PHASE6_SPEC.md` contre l'état du dépôt**

La spec le demande elle-même : « quand la vérité de terrain d'une étape contredit ce
document, la contradiction est le constat ». Trois, relevées avant de commencer S1.

**1. S3 est déjà fait, et son verdict est plus fort que celui que la spec anticipe.** La
spec programme le gate capital « avant S4, ordre dur ». Il a été exécuté le 2026-09-08 —
D-097, `docs/F1B_CAPITAL_GATE.md`. Surtout, la spec en énonce l'attente ainsi : la CDHR
resterait refusée parce qu'elle « mord dans le centile supérieur ; le niveau de tranche est
trop grossier ». **Cette raison est fausse** : la granularité publiée descend au
**millime** — DGFiP n° 41 porte « dont dernier centième » et « dont dernier millième ». Le
vrai refus est plus fort et se généralise : la CDHR est définie sur un **ratio**, donc une
imputation uniforme met tous les foyers d'une cellule du même côté du seuil de 20 %, et le
rendement sauterait de zéro à des milliards selon le placement de la moyenne. Ce n'est pas
« trop grossier », c'est **mal posé**, et cela vaut pour toute mesure définie sur un seuil,
un ratio ou un taux moyen individuel. L'entrée article 2 du triage cite déjà ce verdict.

**2. Le « projection-vs-projection gate (RESF) » : deux sources de vérité avaient
divergé.** *(Amendé le 2026-09-09 — voir D-105.)* J'avais écrit que l'offre « n'a jamais
été offerte ». **C'est faux, et la correction importe** : l'offre existe bel et bien, dans
`REVIEW_2026-08-29.md`, § « One optional line class, offered to the gate — not a
softening ». Ce que j'ai vérifié est exact — zéro occurrence de RESF dans tout
`DECISIONS.md`, y compris D-102 qui est le verdict M2 — et la conclusion tirée de ces
éléments était raisonnable ; elle était fausse quand même, parce que je cherchais dans le
fichier où les décisions sont censées vivre et que celle-ci vivait ailleurs.

Le constat n'est donc pas « la spec renvoie à une option inexistante » mais **« un lecteur
diligent pouvait manquer une décision engageante en lisant le fichier des décisions »**.
La correction est structurelle et vaut mieux que la mienne : toute décision du fichier de
relecture qui engage du travail reçoit désormais une souche dans `DECISIONS.md` (D-105).
L'offre RESF reste **optionnelle** — à prendre en S2 ou à décliner avec motif.

**3. La route d'ingestion du REI que la spec juge « probablement meilleure » ne marche
pas.** S6 annonce « le même jeu de données interrogeable sur data.economie.gouv.fr (API
Opendatasoft — probablement la meilleure route d'ingestion) ». Mesuré, deux fois : cette
API rend **records=0, champs=0** — c'est une coquille sans enregistrements. La route qui
marche est la liste de ressources de data.gouv.fr, qui pointe vers des archives ZIP
annuelles ; le REI 2025 y est, manifesté (D-100).

**Un manque, non une contradiction** : S6 M0 exige un `scripts/verify_rei.py` qui asserte
les identités par commune. Le gate D-100 a fait ces vérifications **en ligne** et a
enregistré ses chiffres, mais n'a pas laissé de script rejouable. Si S6 démarre, le script
est à écrire — et l'écrire ferait passer les contrôles du gate de « mesurés une fois » à
« rejouables », ce qui est la différence entre un constat et un garde-fou.

## D-105 — Index des décisions prises dans le fichier de relecture (rattrapage de souches)

**2026-09-09 · règle nouvelle et rattrapage · `docs/REVIEW_2026-08-29.md`**

**La règle, posée par le relecteur et exécutée ici.** Toute décision, tout arbitrage et
toute offre du fichier de relecture qui **crée, ordonne ou conditionne du travail** reçoit
une **souche d'entrée D au moment où elle est écrite** — une ligne, pointant vers la
section — de sorte que `DECISIONS.md` soit un index complet de ce qui engage.

**Pourquoi.** Une session a audité `DECISIONS.md` — là où les décisions sont censées
vivre — pour savoir si une offre existait, n'a rien trouvé, et a conclu correctement
**depuis ses éléments** qu'il n'y en avait pas. L'offre existait, dans le fichier de
relecture. Deux sources de vérité avaient divergé, et le défaut n'est ni dans l'audit ni
dans l'offre : il est dans le fait qu'un lecteur diligent pouvait manquer une décision
engageante en lisant le fichier des décisions. Cf. D-104, dont la cause est corrigée
ci-dessous.

### Souches, offres encore ouvertes de ce fichier

* **D-105.1 · Classe de ligne « projection contre projection » (RESF)** — OFFERTE, non
  prise. § « One optional line class, offered to the gate — not a softening ». L'annexe
  RESF de chaque PLF publie la trajectoire pluriannuelle de recettes du gouvernement ;
  comparer notre base vieillie à ce chemin donnerait un contexte aux années futures **sans
  jamais valoir validation** — aucun pass/fail, seulement une distance, les deux millésimes
  énoncés. Conditionnée à un gate M0 : si le périmètre du comparateur ne peut pas être
  épinglé, la classe n'est pas créée. Le refus de millésime de D-102 est intact dans les
  deux cas. **Statut : à prendre ou à décliner avec motif en S2.**
* **D-105.2 · La classe de refus « seuil sur ratio »** — RÈGLE. § « The CDHR: my refusal
  was wrong and the right one is stronger ». Tout instrument défini par un **seuil portant
  sur un ratio ou une grandeur par unité** est catégoriquement non chiffrable depuis des
  moyennes de cellule, **si fines soient-elles**, parce que le placement intra-cellule EST
  la réponse. Même famille que les constats de falaise, vue de l'autre côté. **Le triage
  cite la classe, plus l'ancienne conjecture** — appliqué ci-dessous.
* **D-105.3 · Les ancres de spec se mesurent avant de s'écrire** — RÈGLE, escalade de la
  règle du pointeur. Une route, un jeu de données, un point d'accès inscrit dans une spec
  est **mesuré avant d'être écrit** quand mesurer est bon marché, et **étiqueté NON MESURÉ**
  quand ça ne l'est pas. Née de « probablement la meilleure route d'ingestion », écrite
  depuis un résultat de recherche et non depuis une mesure, pour un point d'accès vide.
* **D-105.4 · `scripts/verify_rei.py`** — ORDONNÉ. § « The verify_rei.py gap: backfill
  ordered ». Rejouer les chiffres de D-100 comme assertions. Fait dans le même commit.

### Souches, décisions déjà exécutées

* **Article 2 gagne une quatrième case** (`population_blind`) — fait, D-095/D-104.
* **Le titre gagne un second dénominateur** (part des articles ET part du rendement) —
  fait, D-095.
* **L'aphorisme du formateur rejoint la doctrine** : « un formateur dupliqué diverge ; un
  défaut déplacé se propage », avec son corollaire — consolider une infrastructure partagée
  est un changement de rayon d'action silencieux. Fait, D-102.
* **Les trois limites déclarées tiennent telles quelles** — aucune action, enregistré pour
  que personne ne prenne plus tard la retenue pour un oubli. D-102.

## D-106 — `verify_rei.py` : le constat du gate devient un garde-fou qui reste

**2026-09-09 · `scripts/verify_rei.py`, `tests/test_entreprises.py` · exécute D-105.4**

Le gate F5 (D-100) avait mesuré une fois et écrit les chiffres. C'est un constat. Le script
les rejoue comme **assertions** : lancé après tout changement de millésime du REI, il tombe
sur les pièges au lieu de laisser un lecteur les redécouvrir.

Six familles d'assertions, une par piège : l'encodage latin-1 (asserté explicitement,
parce que le correctif tentant — `errors="replace"` — corrompt les libellés **sans lever
d'erreur**) ; la forme, 34 907 lignes et 1043 colonnes ; le fait que le fichier ne dise
jamais « foncier » ; l'identité base × taux par commune ; la reconstruction nationale
contre le BON comparateur ; et le trou du non bâti.

**Deux choses valent d'être notées.**

**Le comparateur est asserté dans les deux sens.** Le script vérifie que la reconstruction
tombe près de 43,1 md **et LOIN de 55,1 md**. Le second est le chiffre que la publication
met en avant, taxes annexes et frais de gestion compris ; le confondre donne −21 % et
condamnerait une lecture juste. Un garde qui ne vérifie que la bonne cible ne protège pas
contre le choix de la mauvaise.

**Le trou du non bâti est épinglé COMME trou.** −59,7 % est asserté comme devant rester
tel. Épingler un manque le garde visible, et une lecture ultérieure qui le corrige fera
**échouer** cette assertion — ce qui force l'entrée D qui enregistre la correction, au lieu
de la laisser passer en silence.

**Et le script a attrapé sa propre assertion, plus paresseuse que le constat dont elle
venait.** J'avais asserté « aucune des variables trouvées en cherchant « foncier » ne porte
BASE ou TAUX » ; ça échoue sur deux lignes CFE titrées « CFE - BASES BRUTES : PROPRIÉTÉS
NON BÂTIES », qui ne sont pas de la taxe foncière. L'affirmation juste est plus étroite et
plus utile : **aucune des variables trouvées n'est l'une des dix-huit colonnes dont un
modèle TF a besoin**. Le premier lancement du garde a donc corrigé le garde.

**Le kill test.** Doubler le comparateur publié doit faire rougir le script — ce qui prouve
que le contrôle national compare quelque chose au lieu de l'imprimer. Un garde dont on n'a
jamais vu le voyant rouge n'est pas un garde ; c'est la troisième question permanente,
posée à la naissance.

## D-107 — S1 / F3 M4 : la bande année par année, et le vieillissement devient une classe nommée

**2026-09-09 · `src/impots/trajectoires.py`, `tests/test_trajectoires.py`**

Chaque année d'une trajectoire porte désormais : le chiffre mécanique, sa base
(`legislated`/`reconducted`, D-103), **deux classes d'incertitude tenues séparées**, et
l'éventail macro ou son refus.

### Le vieillissement devient une classe, et elle est MESURÉE

La grammaire d'incertitude du projet gardait déjà visibles paramètre / scénario /
cellule / composition. Il s'y ajoute **`uprating`**, et sa largeur n'est pas supposée :
c'est la paire figée/vieillie de M2. Sur le gel du barème 2028 :

    population 2024 figée   -7,073 md€
    population vieillie     -8,339 md€     -> classe « vieillissement » : 1,266 md€

**Plus large que bien des bandes comportementales, et invisible tant qu'on ne la nomme
pas.** Le titre reste le chiffre vieilli, qui est le plus complet.

### Les deux classes ne sont JAMAIS fusionnées

Il n'y a délibérément ni `total` ni bande combinée. Les additionner affirmerait une
indépendance que personne n'a établie **et** détruirait la seule information exploitable :
laquelle des deux fait le travail. Sur le gel 2028 c'est le vieillissement qui domine, et
un intervalle fusionné le cacherait. `test_the_two_classes_are_never_merged_into_one_band`
échoue le jour où une propriété combinée apparaît — vérifié en en ajoutant une.

### Le refus d'horizon macro s'impose PAR ANNÉE, pas par réforme

Une trajectoire 2024-2030 n'est pas « dans l'horizon » ou « hors » en bloc : 2027 est à un
an et 2032 à six. Montrer un seul éventail pour la réforme étirerait en silence un
multiplicateur à trois ans sur six. Chaque année est donc jugée sur sa propre distance.

**L'horizon est LU dans le magasin**, pas écrit : `usable_horizons` vaut `["1","2","3"]`
dans `multipliers.yaml`, plafonné à trois pour deux raisons indépendantes et convergentes
— le refus posé par §0, et la mesure montrant que les colonnes longues sont déterminées par
un choix de spécification plutôt qu'observées (cotisations employeurs : 1,73 à LT en
« wage setting » contre 0,25 sous courbe de Phillips, un facteur sept).

**Et ma première lecture du magasin était vide.** Je lisais `store.parameters` alors que
tout multiplicateur porte `from_source_table` et atterrit dans `store.tables` : la fonction
levait « aucun horizon utilisable » là où trois l'étaient. Le mauvais conteneur, pas le
mauvais magasin — deuxième fois dans cette session qu'un conteneur mal choisi produit un
vide convaincant (cf. `totals` contre `totals_reform`, D-095).

### L'applicabilité se grade PAR ANNÉE

Une réforme dans le support en 2026 peut en sortir en 2030, les revenus vieillis dérivant
hors de la plage d'estimation des élasticités. Chaque année apporte donc son propre verdict
au lieu de reporter celui de la première — mesurer, pas supposer.

### Une incohérence attrapée en la regardant tourner

« L'horizon autorise un éventail » et « un éventail a été calculé » sont deux affirmations
différentes, et la première version imprimait la seconde en pensant la première : un
lecteur voyait « l'éventail est montré » à côté de « pas d'éventail ». Les trois cas —
autorisé et présent, autorisé et absent, refusé — disent maintenant chacun ce qui est vrai.

## D-108 — Le gate « projection contre projection » (RESF) : NON, pour deux raisons indépendantes

**2026-09-09 · exécute D-105.1 · `data/raw/resf_2026.pdf` manifesté**

L'offre du relecteur : comparer notre base vieillie à la trajectoire de recettes du
gouvernement — jamais un pass/fail, seulement une distance, les deux millésimes énoncés —
pour donner un contexte aux années futures sans faire semblant de valider. Conditionnée à
un gate : **le périmètre du comparateur peut-il être épinglé ?**

**Il ne peut pas. La classe de ligne n'est pas créée.**

**Raison 1 — la série par impôt s'arrête en 2026, et les années à servir commencent en
2027.** Le RESF 2026 porte bien un tableau de recettes par impôt (p. 85-92) : IR 94,9 Md€
en 2025, TVA nette budgétaire 96,8, recettes fiscales nettes 325,7. Mais **sur 2025 et 2026
seulement**. Toute la matière qui court jusqu'à 2029 est **agrégée** — soldes publics,
ratio d'endettement, dépense primaire nette en points de PIB — et ne descend à aucun impôt.
Or les années qu'une ligne « projection contre projection » servirait sont précisément
celles que le refus de millésime rend non comparables : 2027 et au-delà. Le comparateur
manque exactement là où la classe existerait.

**Raison 2 — et elle serait fatale même si la série allait jusqu'en 2030.** Le chiffre par
impôt du RESF est **budgétaire** : des recettes encaissées par l'État sur un exercice, avec
le calendrier du prélèvement à la source et les prélèvements sur assiettes. Ce modèle
calcule l'**impôt dû au titre d'une année de revenus**. Ce sont deux grandeurs
différentes, le rapport ne publie pas le pont entre elles, et les rapprocher sans ce pont
serait précisément la comparaison de périmètre non épinglé que le gate devait exclure.

**Deux raisons indépendantes qui concluent pareil**, ce qui est le cas confortable : la
première pourrait tomber si un RESF futur publiait une série par impôt jusqu'en 2030 ; la
seconde tiendrait quand même.

**Ce qui ne change pas.** Le refus de millésime de D-102 est intact — il l'était dans les
deux branches du gate, et l'offre le disait. Les années vieillies restent « not
comparable », sans contexte chiffré, et c'est l'état honnête plutôt qu'un manque.

**Le RESF reste manifesté**, comme la note IPP n° 92 et la méthodologie Banque de France
l'ont été en phase 5 : **pour ce qu'il ne contient pas**. Une source dont on a établi
qu'elle ne porte pas ce qu'on lui prêtait est un résultat, et le reperdre coûterait le même
travail une seconde fois.

## D-109 — S2 / F3 M5 : les sorties de trajectoire, et la phase F3 se ferme

**2026-09-09 · `fiche.py`, `trajectoires.py`, `ui/index.html`, `api/`, `impots trajectoire`**

Quatre livrables, dont un qui s'est soldé par un refus.

### 1. La fiche porte la trajectoire

Une section 4.2.1 bis, un tableau par année : base, mécanique, **la paire figée → vieillie**
(pas seulement sa largeur — montrer « ±1,27 md€ » cacherait dans quel sens le
vieillissement déplace le chiffre, et il l'éloigne de zéro), la bande comportementale et
son grade, l'éventail ou son refus. **Les deux classes ne sont jamais additionnées**, et la
fiche dit pourquoi. Les années dont l'éventail est refusé sont listées **une par une** avec
leur motif, le refus étant posé par année et non par réforme.

### 2. L'exemple travaillé, calculé pour de bon

`impots trajectoire gel_bareme --reference indexe` sur 4 000 ménages :

    2026  legislated    -2,569 md€   vieillissement ±0,196
    2027  legislated    -5,311 md€   vieillissement ±0,608
    2028  reconducted   -8,231 md€   vieillissement ±1,232
    2029  reconducted  -11,340 md€   vieillissement ±2,072

**Le chiffre ET son incertitude croissent avec l'horizon** — ce que M5 demandait de rendre
visible. Contre `reconduit`, la même trajectoire rend **+0,000 md€ chaque année** : la
propriété falsifiable de M1, reproduite sur quatre ans.

**Et la première version de la commande validait `--reference` puis l'ignorait**,
chiffrant la réforme contre le droit courant quelle que soit la référence demandée. Les
quatre zéros étaient donc justes pour la mauvaise raison. Corrigé en passant par
`tj.price`, qui applique la référence — et pour `indexe` fait la soustraction sans laquelle
le coût entier de l'indexation se serait replié dans chaque chiffre.

### 3. La vue d'interface, sur les conventions du dépôt

Une ligne par année, l'idiome du graphique d'éventail réutilisé parce que c'est la même
sorte de grandeur — un point préféré dans un intervalle mesuré : `tspan` pour l'écart
figée→vieillie, `taged` pour le chiffre retenu, zéro toujours tracé. **Aucune courbe** :
une ligne lissée suggérerait des valeurs jamais calculées, et un test le refuse
(`<path`, `polyline`, `<svg` bannis du rendu). Les années `reconducted` sont visuellement
distinctes, pas seulement étiquetées. La bannière est imprimée **verbatim depuis
l'artefact**.

**L'artefact est PRÉCALCULÉ et les points d'accès sont en lecture seule.** Une trajectoire
est N exécutions de population **deux fois** — figée et vieillie — soit des minutes par
année. La règle §1.1 du projet s'applique telle quelle : les travaux par lots vivent dans
la ligne de commande, et seule la lecture passe par HTTP.

### 4. Le gate RESF : non — cf. D-108

### 5. Le re-balayage des chiffrages : la machinerie est prête, le comparateur est en quarantaine

Les articles pluriannuels sont désormais exprimables — la trajectoire CVAE et l'expiration
de la CEBGE sont dans l'arbre et mesurées (D-099). Mais un cas de backtest CVAE
pluriannuel a besoin d'une série de recettes CVAE publiée, et **les cinq fichiers DGFiP
d'impôts de production du dépôt sont tous en quarantaine** (URL non enregistrée, D-028) :
rien de calculé à partir d'eux n'est reproductible par un tiers. Le balayage conclut donc
que la machinerie est prête et que **le déblocage est une source, pas du code** — retrouver
la publication avec son URL, la manifester, et le cas devient écrivable. Noté plutôt que
contourné : bâtir sur un fichier en quarantaine reviendrait à produire un chiffre que
personne ne peut refaire.

## D-110 — S5 / F6 : l'explorateur EMTR, et une falaise dont la hauteur ne veut rien dire

**2026-09-09 · `src/impots/emtr_explorer.py`, `impots emtr`, `ui/index.html`**

**Aucune affirmation de modèle nouvelle** : tout sort de machinerie déjà écrite et déjà
testée — le moteur, la différence finie de `behavioural.emtr`, le tier complet. Ce qui est
neuf, c'est que les taux deviennent **lisibles** au lieu d'arriver en statistique de
distribution.

### Le constat de D-033, retrouvé par l'autre bout

D-033 mesurait sur la population : l'EMTR médian va de 20,8 % au premier décile de taux
marginaux à **63,5 %** au dixième, et **les ménages de ce dixième sont pauvres, pas
riches**. Un célibataire locataire balayé sur la plage de revenus se tient à **63,5-63,6 %
entre 24 000 et 28 000 EUR** — le même nombre, obtenu d'un ménage construit au lieu d'un
décile de population. Cet accord est tout l'intérêt de l'explorateur : la statistique
devient un endroit sur une courbe, et le mécanisme se voit — les pentes du RSA et de la
prime d'activité qui s'empilent, se dépilent, puis la première tranche d'IR par-dessus.

### Une falaise, et pourquoi sa hauteur ne doit jamais être citée

Le balayage rend **147,3 % à 8 000 EUR**. Un taux au-dessus de 100 % signifie qu'un euro de
brut en plus laisse le ménage **moins riche** — c'est réel et c'est ce que l'explorateur
doit montrer. Mais **sa hauteur est un artefact du pas de la différence finie** : mesurée
sur 100 EUR, une falaise qui retire 47 EUR se lit 147 % ; la même mesurée sur 500 EUR se
lirait 109 %. **L'EMPLACEMENT est un constat, la HAUTEUR est une propriété de
l'instrument.** `Curve.cliffs` les nomme, le rendu les marque en rouge sans les tracer
comme des pentes, et l'échelle s'arrête à 100 % — la mettre à l'échelle du pic écraserait
tous les taux réels dans le tiers gauche et rendrait illisible exactement ce qu'on veut
montrer.

### Quatre exécutions pour toute la courbe, pas deux par point

Un ménage au tier complet avec son EMTR coûte ~2,5 s : soixante points chiffrés un par un,
deux fois pour la référence et la réforme, font **cinq minutes**. Or
`behavioural.emtr.compute` chiffre déjà une **trame entière** en une passe. Un balayage est
donc une trame synthétique d'un ménage par point de revenu, et la courbe coûte les quatre
exécutions d'un EMTR de population. Passer par ce chemin lui fait aussi hériter de ses
gardes au lieu de s'en inventer.

**Le tier complet n'est pas négociable ici**, et D-033 dit pourquoi : la pente du RSA et de
la prime d'activité fait l'essentiel du taux marginal aux bas salaires. Une courbe en tier
léger serait nette et fausse exactement là où l'argument politique se joue.

### Une règle graduée, pas un échantillon

Chaque point pèse 1 et porte `synthetic=True`. Un balayage n'est l'échantillon de personne :
c'est **un** type de ménage promené sur une plage de revenus. En lire une distribution
reviendrait à en lire une sur une règle graduée, et les poids sont ce qui permettrait
d'essayer. Le type de ménage est imprimé en toutes lettres, parce qu'une courbe d'EMTR sans
son ménage est une courbe de rien en particulier : à 24 000 EUR, un célibataire locataire et
un couple avec deux enfants ne sont pas au même endroit du paysage.

## D-111 — S6 / F5 : la taxe foncière sur cellules publiées, et l'impôt d'un ménage qu'on ne peut pas calculer

**2026-09-09 · `src/impots/foncier/{cells,knobs,reconcile}.py`**

**Le premier module du projet dont les cellules ne sont pas une construction.** Chaque base
et chaque taux est lu du REI tel que la DGFiP l'a publié : aucune imputation, aucun tirage,
aucune cellule ajustée à un total. Cela change ce qu'EST le contrôle de base. Ailleurs la
réconciliation demande « notre population synthétique reproduit-elle un total publié » ;
ici elle demande « **notre arithmétique sur LEURS bases reproduit-elle LEURS produits** »,
commune par commune. C'est une question bien plus forte, et elle a une réponse bien plus
nette.

### L'identité, et le terme qui y manquait

La forme évidente est `base × taux = produit`. Sur 34 819 communes elle tient à 0,023 %
d'écart médian — déjà de l'arrondi. Mais le REI publie aussi un **lissage** (`E16`) que
**13 430 communes** portent, et l'ajouter fait tomber leur écart médian de 0,0355 % à
0,0012 %. L'identité retenue est donc

    base × taux / 100 + lissage = produit

et le lissage n'est pas une correction qu'on applique en douce : c'est un terme publié du
calcul qu'une lecture à deux facteurs omet purement et simplement. Écart médian d'ensemble
après ajout : **0,0059 %**, p99 **0,405 %**.

**55 communes sur 34 819 restent au-delà de 1 %**, la pire à 5,97 %, et **aucune ne porte
de lissage** — le terme n'est donc pas ce qui leur manque. Leur taux effectif est sous leur
taux publié (base 227 676 à 19,40 % devrait rendre 44 169 ; le REI dit 41 682, soit 18,31 %
effectif), ce qui désigne un abattement ou une exonération que ce module ne lit pas.
Épinglées comme **inexpliquées** : un résidu nommé est une piste, un résidu absorbé dans une
tolérance est un mensonge à barres d'erreur. **Et j'avais épinglé 79 avant de mesurer avec
le lissage** — la constante suit désormais la mesure et non l'inverse.

### Trois leviers, et l'intuition sur leur ordre était fausse

Coefficient de revalorisation national (le plus chaud fiscalement : depuis la LF 2017 il
vaut 1 + l'IPCH de novembre N-1, donc le modifier change une RÈGLE d'indexation et non un
taux) ; changement de taux national ; changement de taux sur un ensemble de communes — la
forme honnête de la plupart des vraies questions de TF, puisque c'est le niveau où la
décision se prend.

    revalorisation +3,2 %     +1,2849 md€
    revalorisation +1,0 %     +0,4015 md€
    taux national +1 point    +1,0796 md€
    taux +1 pt sur Paris      +0,0898 md€   (une commune, 8 % du point national)

**Un point de revalorisation vaut MOINS qu'un point de taux** — 0,40 contre 1,08 md€ —
parce qu'un point de revalorisation est 1 % de base tandis qu'un point de taux est un point
sur un taux moyen proche de 20 %, soit une hausse relative de 5 %. Mon premier jet de
docstring affirmait le contraire, d'intuition ; l'arithmétique l'a contredit.

**Et la garde de l'ensemble vide a attrapé son auteur** : mon premier essai « Paris » usait
75101-75120, qui sont des arrondissements et ne correspondent à aucune commune — Paris est
une commune, 75056. Un zéro venu d'un ensemble vide se lit « la mesure est gratuite » et
est indiscernable d'un vrai zéro tant que personne ne compte.

### La surface s'arrête à la commune, et c'est le constat

**Ce modèle ne peut pas calculer la taxe foncière d'un ménage, et ce n'est pas une limite
temporaire.** La TF d'un logement est la valeur locative cadastrale de CE logement
multipliée par les taux de sa commune. Les taux sont publiés ; la valeur locative d'un
logement individuel ne l'est par aucune source ouverte. D'où l'absence d'extension du
calculateur : afficher le taux de la commune à côté des autres chiffres d'un ménage se
lirait comme une estimation de son impôt à tous les coups. **Le refus est la
fonctionnalité.**

### Deux défauts trouvés en assemblant

**`Line.status` plantait sur une cible nulle.** `residual` rend `None` quand
`published == 0`, et `status` l'écartait par une assertion : toute ligne visant
légitimement zéro levait une `AssertionError`. Corrigé en « not comparable (cible nulle) »
— un résidu relatif à zéro n'est pas un grand nombre, ce n'est pas un nombre, exactement le
raisonnement du barème de chiffrages (D-095).

**Et c'est en le heurtant que j'ai vu l'erreur de catégorie.** Je poussais l'audit
d'identité dans le gabarit `Line`, qui compare un simulé à une CIBLE publiée ; or l'identité
compare un calcul au chiffre de la MÊME source, par commune, avec zéro pour cible. Ce n'est
pas une ligne de réconciliation, c'est un audit, et il est rendu comme tel.

## D-112 — La charte de maintenance est de l'infrastructure, et elle est testée comme telle

**Phase 6 S7, 2026-09-09.** `docs/CHARTER.md` : six sections — le rituel de montée de
version d'openfisca, le cycle annuel des lois de finances, le calendrier de
rafraîchissement des millésimes, la cadence de passe complète, les cinq questions
permanentes, et ce que la maintenance ne fait jamais.

### Pourquoi une charte plutôt qu'un README

Ce projet a produit cent onze entrées D, et une entrée D raconte un incident. Une charte
raconte le **rituel** qui empêche l'incident de se reproduire, ce qui est une autre chose et
manquait. La différence est celle entre « voici pourquoi ce garde existe » et « voici quoi
faire lundi quand openfisca sort une version ». Le second lecteur n'aura pas lu les cent
onze.

### La règle qui la rend utile : une maintenance suit les mêmes règles qu'une construction

Rien n'est « juste une mise à jour ». Les pires défauts de ce projet sont arrivés par des
chemins qui avaient l'air routiniers — `value: 6e-05` lu comme une chaîne par YAML 1.1 dans
NOTRE fichier, un `$?` lu après un tube qui ne rendait que PASS, quatre contrôles inertes
en une session. Aucun n'est venu d'un travail qui se savait délicat.

Deux prescriptions portent l'essentiel :

**Un golden ne se ré-ancre qu'avec une entrée D citant le texte qui l'a déplacé.** Numéro
d'article, date, effet. Sans citation, un golden ré-ancré est un test qu'on a fait taire, et
il est trait pour trait identique à un test honnêtement remis à jour.

**Un kill test qui passe au vert est une entrée D, pas un test à supprimer.** Sept artefacts
amont sont recensés ; le jour où l'amont en corrige un, la tentation sera de retirer le
garde. C'est le moment exact où il faut écrire ce qui a changé.

### Elle est testée, et le premier test a trouvé son auteur

`tests/test_charter.py` — huit tests. La charte affirme des choses sur ce dépôt : que les
scripts `verify_*.py` existent, que le calendrier cite des sources que le manifeste porte
vraiment, que les artefacts qu'elle nomme ont leur entrée D, qu'il y a cinq questions
permanentes. **Une charte qui décrit un dépôt qui n'existe plus est pire que rien : elle
sera suivie.**

Le compte des questions permanentes en est l'illustration : ma première version balayait
tout le fichier avec `^\d\. \*\*` et trouvait **neuf** questions — les étapes numérotées du
rituel de montée de version et du cycle LF étaient comptées avec. Le test a échoué à sa
première exécution, ce qui est la seule preuve qu'il sait échouer. Corrigé en découpant la
section, avec la raison en commentaire pour que le prochain lecteur ne « simplifie » pas la
découpe.

### Ce que la charte interdit explicitement

Élargir une tolérance pour faire passer une ligne ; supprimer un test devenu gênant ;
recopier un chiffre depuis un cahier des charges, un résumé ou une recherche ; publier quoi
que ce soit. Le premier est le plus dangereux parce qu'il est le plus discret — une
tolérance élargie après coup transforme chaque manqué en réussi et laisse un fichier
indiscernable d'un fichier honnête. Le dernier est du ressort du propriétaire et le reste.

### Post-scriptum : la charte affirmait six mauvaises entrées, et son test ne pouvait pas le voir

Écrite de mémoire, la section 1 recensait les artefacts amont comme « D-044, D-062, D-064,
D-071, D-081, D-090 ». **Trois sur six n'ont rien à voir avec l'amont** — D-062 est le jeu
de leviers prestations. Le vrai registre est la table de `docs/UPSTREAM_ISSUE_DRAFT.md` :
six constats côté `openfisca-france`, un septième côté `openfisca-core`, mesurés en D-064,
D-075, D-079, D-081, D-090 et clos par D-091.

Le test l'a laissé passer parce qu'il vérifiait que les six entrées **existaient** dans le
journal. Elles existaient. **L'existence n'est pas l'appartenance** — c'est la forme D-044
pour la cinquième fois de ce projet : un contrôle dérivé d'autre chose que ce qu'il
contrôle ne peut pas échouer quand ce qu'il contrôle est faux.

Corrigé des deux côtés. La charte **pointe** désormais le registre au lieu d'en recopier une
liste, parce qu'une liste recopiée diverge, et c'est exactement ce qui venait d'arriver. Le
test lit la table du dossier, compte ses lignes, et exige que la charte porte le pointeur —
vérifié en le retirant : il échoue.

**Et c'est le paragraphe d'à côté qui l'a déclenché.** Je citais « D-072 » pour les leviers
prestations dans `WHAT_NOW.md`, également de mémoire ; en le vérifiant (D-072 est une ligne
de rapport, D-062 est la bonne) j'ai regardé la charte écrite dix minutes plus tôt. Les
numéros remémorés sont des graines de recherche et rien de plus — la charte le dit dans sa
propre section 6, et l'a enfreint dans sa section 1.

## D-113 — Une passe tuée s'écrivait ÉCHEC, avec des points de progression en guise de comptes

**2026-09-09, en répondant à « comment va la passe ? ».** Elle n'allait pas. Deux `make
full` tournaient en parallèle — celle de 12h52 et celle de 13h10 — depuis **3 h 30 et
3 h 11**, contre 60 minutes de norme sur les huit dernières passes. Aucune n'avait fini.

### Le diagnostic, et ce qui l'a donné

La charge valait **110,64 sur 8 cœurs**, en hausse (110 / 82 / 40 sur 1, 5 et 15 minutes).
Ce n'était ni le swap — 350 Mo de RSS chacune, 29 % de mémoire libre — ni les deux pytest,
qui ne consommaient qu'un cœur chacun. La signature était ailleurs : `trustd`,
`searchpartyuseragent`, `accessoryupdaterd`, `amsengagementd`, `IDSBlastDoorService`,
`CloudKeychainProxy` — **tous démarrés dans la même fenêtre de trois minutes**. C'est un
réveil de veille, et la ruée des démons qui suit.

**Ce que cela vaut pour le gate, indépendamment de la cause** : `quiet_machine` saute les
tests de rythme quand la charge dépasse le nombre de cœurs, et sa docstring documente déjà
6,5 s contre 18 s pour le même calcul à charge 33. À charge 110, aucune des deux passes
n'aurait été verte au sens de la charte — elle l'écrit noir sur blanc en §4. Les deux ont
été tuées, et **une seule** sera relancée au calme.

### Le vrai défaut : l'instrument, pas la machine

Les tuer a écrit deux lignes au journal :

    | 2026-09-09 | f593847 | FAIL | 214m11s | ....................................... |

**Une passe tuée est indiscernable d'une suite en échec.** Deux erreurs dans la même ligne :

1. `result` valait FAIL dès que `status != 0`, alors que 130 (SIGINT) et 143 (SIGTERM)
   disent « on m'a interrompu », pas « le code est faux ». Un futur lecteur — ou moi dans
   trois semaines — aurait lu deux échecs sur `f593847` et cherché une régression qui
   n'existe pas.
2. `counts=$(tail -1 $out …)` prenait la **dernière ligne quelle qu'elle soit**. Sur un run
   interrompu c'est une ligne de points de progression. La colonne comptes affichait donc
   trente-neuf points là où elle promet un résumé.

Corrigé : `grep -E '[0-9]+ (passed|failed|error)'` pour n'accepter qu'une ligne qui
ressemble à un résumé, et un `if/elif/else` qui rend PASS, TUÉ ou FAIL. Vérifié sur les cinq
codes de sortie (0, 1, 2, 130, 143) et sur les deux formes de sortie.

**Et ma première vérification était fausse.** J'ai testé la logique avec une chaîne
`[ … ] && echo PASS || { … ; } && echo TUÉ || echo FAIL`, qui imprimait « TUÉ » en plus de
« PASS » pour status=0. Le défaut était dans ma paraphrase, pas dans le Makefile — mais je
l'aurais lu comme un défaut du Makefile si le bruit avait été moins visible. C'est le
corollaire de la troisième question permanente : **vérifier que la mutation fait bien ce
qu'on croit**, et ici, vérifier le banc d'essai avant l'objet. Retesté avec la vraie
structure `if/elif/else` dans `/bin/sh`.

Les deux lignes du journal sont **annotées TUÉ, pas effacées** : un journal de passes dont
on retire les lignes gênantes ne vaut rien, et l'annotation porte la raison.

### La ligne à retenir

Le journal de passe complète est l'unique preuve que la suite est verte, puisque la CI ne
peut pas faire tourner les tests de population. **C'est de l'infrastructure de mesure, et
elle reçoit le même traitement que le code de modèle** — comme le `$?` lu après un tube qui
ne rendait que PASS, trouvé au même endroit quelques jours plus tôt. Deux défauts dans la
même cible, tous deux du côté qui décide si le travail est bon.

## D-114 — Le marqueur `slow` affirmait tourner en CI, et je l'ai compté à 14 au lieu de 217

**2026-09-09, en répondant à « pourquoi est-ce si long ? ».** La passe complète prend une
heure ; expliquer pourquoi a sorti deux erreurs, l'une dans le dépôt et l'autre dans ma
réponse.

### Le marqueur mentait, et dans le sens dangereux

Sa description disait : « excluded from the default gate, **always run in CI** ». C'est
faux. La CI lance bien `pytest -q -m ""`, mais ces tests **sautent** faute de population
construite — le workflow le dit lui-même en commentaire (« those tests currently SKIP here
anyway… `-m ""` is what makes CI pick them up the day that changes, rather than silently
continuing to skip a suite everyone believes is running »), et l'en-tête du journal de passe
le dit aussi (« CI cannot run the population tests — it has no population, by design »).

**Deux sources de vérité disaient l'inverse l'une de l'autre, et la fausse était celle que
pytest affiche** avec `--markers`. Un lecteur qui la croit saute l'heure locale en pensant
que la CI couvre le terrain — exactement le défaut que le commentaire du workflow nomme.
Corrigé, en pointant les deux autres sources plutôt qu'en réécrivant une troisième version.

**Et la correction elle-même a cassé le fichier** : une chaîne TOML simple ne peut pas
courir sur plusieurs lignes, `tomllib` a refusé le fichier. Rattrapé parce que j'ai vérifié
le parse au lieu de supposer qu'un remplacement de texte est inoffensif. Refait en chaîne
multi-lignes, puis vérifié que le marqueur **filtre encore** et pas seulement qu'il se lit.

### Mon compte était faux d'un facteur quinze

J'ai annoncé « 14 tests slow ». C'est le nombre de **décorateurs** —
`grep -c "pytest.mark.slow"`. Le nombre de **tests** est **217** : la paramétrisation les
multiplie, et `-m 'slow'` en collecte 217 sur 1 315.

L'erreur est celle de la cinquième question permanente prise à l'envers : je savais demander
d'où viennent les paramètres d'un test paramétré, et pas que compter les décorateurs n'est
pas compter les tests. Un grep sur le code source compte des occurrences syntaxiques ;
seule la collecte compte des cas. **La mesure était à une commande de distance et je ne l'ai
pas lancée** parce que la passe tournait — mais `--collect-only` coûte deux secondes et
n'aurait rien perturbé.

### Ce qui rend la question répondable la prochaine fois

`--durations=15` ajouté à la cible `full`. Chaque passe laissera désormais la distribution
de son heure dans sa sortie, au lieu qu'on la redérive d'un coût unitaire documenté et d'une
arithmétique. Vérifié que le bloc de durées ne perturbe pas l'extraction des comptes : ses
lignes (`62.11s call …`) ne ressemblent pas à un résumé et le `grep` les ignore.

**Passe de référence de cette entrée** : `1313 passed, 2 skipped, 18 warnings` en 82m49s,
machine au calme, **2 sauts et non 5** — les budgets de temps ont donc réellement tourné.

## D-115 — A0 : le budget d'exactitude, et la source qui n'était pas celle qu'on croyait

**Phase 7 S-A0, 2026-09-10.** `src/impots/accuracy.py` + `tests/test_accuracy.py`. Le
classement produit ici ordonne les leviers L1-L6 de toute la phase : **un mauvais classement
ne produit pas un mauvais nombre, il produit une phase gaspillée.** D'où le traitement
d'infrastructure de mesure, et le kill test écrit AVANT qu'aucun cas réel ne soit chiffré,
comme la spec l'ordonne.

### Trois classes, et une part qui ne se calcule jamais entre elles

Les sources déclarées par la spec n'ont pas le même statut épistémique, et la pire chose que
ce module pouvait faire était de les mettre sur un même axe sans le dire.

* `sampled` — une loi nommée et tirable existe. C'est exactement `Parameter.draw` du store
  comportemental et les graines de placement. La part de variance y est une **mesure**.
* `swing` — seules deux **bornes** existent. La largeur est mesurable honnêtement, mais la
  convertir en part de variance suppose une forme sur l'intervalle. `VARIANCE_OF_A_RANGE =
  12.0` isole cette convention dans une constante nommée, pour qu'on puisse la contester en
  un endroit au lieu d'auditer une expression.
* `unmeasured` — la spec déclare la source, le dépôt n'a ni loi ni bornes. Elle est
  **rapportée sans part**, jamais omise : une source absente d'un budget se lit « elle ne
  compte pas ».

**Les parts se calculent DANS une classe et jamais entre elles.** Sinon on classe les
conventions, et la campagne partirait vers la source dont la convention est la plus
généreuse.

### La paire vieillie/gelée n'est pas un intervalle d'uprating

`YearUncertainty.uprating_eur` vaut `(frozen, aged)` et sa largeur s'affiche partout
« vieillissement ± ». Dans son contexte c'est honnête. Comme source d'incertitude, c'est
faux, et `population/cli.py` le dit : `frozen = price(frame, year)` chiffre la frame 2024
**brute** — des revenus qui n'ont pas bougé d'un euro — contre `aged` qui chiffre la frame
vieillie. La largeur mesure donc **vieillir contre ne pas vieillir**, pas l'écart entre une
hypothèse haute et une hypothèse basse. Personne n'a « zéro pendant cinq ans » dans son
incertitude sur les salaires.

L'injecter telle quelle aurait donné à A0 un grand nombre attribué à la mauvaise chose, il
aurait très probablement classé en tête, et **la campagne entière serait partie vers une
grandeur qui n'est pas une erreur**. C'est la quatrième question permanente — « de quoi ce
nombre est-il la différence, exactement ? » — arrivant au seul endroit où se tromper coûte
une phase et non un chiffre. Les bornes d'un `swing` sont donc **nommées** et c'est vérifié
par un test : une source qui ne peut pas nommer ses bornes ne peut pas glisser un
contre-factuel à la place d'une borne basse.

### L'inventaire réel des sources, qui n'est pas celui d'une lecture naïve de la spec

La taxonomie fait autorité et existait déjà : `scenarios.BANDED_QUANTITIES` nomme quatre
classes d'intervalle — behavioural, macro, cell_bound, composition. Mesuré au gate :

* **Store comportemental** : 10 lignes, dont **2 dégénérées** (`employment_elasticity_at_
  fadeout`, `employment_fadeout_smic_multiple`, low == high). `in_revenue_band=True`
  n'apparaît que **deux fois** dans `channels.py` (C1 ETI, C5 patrimoine) : seules trois
  lignes peuvent déplacer un euro. Une étude Sobol « sur le store » est en réalité une étude
  à trois paramètres pour la plupart des réformes, et le dire change ce qu'on peut en
  conclure.
* **cell_bound** : existe côté **patrimoine** (`placement.band` rend un (bas, haut) exact),
  **n'existe pas** côté entreprises ni foncier. Ce que le côté entreprises a à la place est
  une **mesure de placement tirable** (`build_firms(seed=…)`, qui reproduit effectif, chiffre
  d'affaires et valeur ajoutée à moins de 1e-9) — et **une seule graine a jamais été
  tirée**. Cette source est donc `unmeasured` aujourd'hui, et A0 la mesurera pour la
  première fois.
* **composition** : `CompositionFactor(low, central, high)`, plat, sourcé sur un seul
  fractile (D-085). Un `swing`, et le fichier dit lui-même « rien ici n'est un intervalle de
  confiance ».
* **Les boutons de réforme ne sont pas une source.** Ce sont les points de conception fixes.
  Les bornes `ge`/`le` de `ReformSpec` sont de la validation d'entrée — le schéma l'écrit —
  et non une plage crédible pour un paramètre voté. Les prendre pour une incertitude
  inventerait une barre d'erreur sur un nombre que le législateur fixe exactement.

### Le kill test, et ce qu'il a attrapé chez son auteur

Trois sources synthétiques d'amplitudes 100 : 10 : 1, **paramétré sur LAQUELLE domine** — un
classeur figé passe n'importe quel arrangement unique. Vérifié en mutant le classeur : tri
ascendant → 7 échecs ; ordre de déclaration sans tri → 4 échecs, et **jamais sur
l'arrangement `loud`**, ce qui est exactement la raison d'être de la paramétrisation.

**Et mon échantillonneur synthétique n'échantillonnait pas.** Première version :
`(seed * k) % p`, évaluée en seed, seed+1, seed+2 — c'est une **progression arithmétique**,
pas un tirage, et la variance est invariante par translation : deux graines de base
différentes rendaient des variances égales au dernier bit. Attrapé par le test de
déterminisme, pas par les tests de classement — **une rampe passe tous les tests de
classement**, puisque les amplitudes 100 : 10 : 1 y survivent. Remplacé par le finaliseur
splitmix64, dont l'avalanche disperse des graines consécutives.

C'est la cinquième question permanente sous un autre angle : je savais demander d'où
viennent les paramètres d'un test paramétré ; je n'avais pas demandé si mon générateur
générait quelque chose.

## D-116 — A0 tourne : trois mesures, deux cas construits pour ne rien pouvoir dire

**Phase 7 A0, 2026-09-10.** `src/impots/accuracy_cases.py`, `scripts/accuracy_budget.py`,
`reports/accuracy_budget.md`. Huit réformes de référence, une par famille d'instrument,
committées comme données : si les cas bougeaient d'un passage à l'autre, le score d'un
levier serait un fait sur la réforme que quelqu'un a choisie cette semaine-là.

### Ce qui est mesuré, dont une première

| famille | source | contribution relative | méthode |
|---|---|---|---|
| IFI | placement intra-tranche | **17,44 %** | swing |
| CVAE | placement intra-cellule | **2,52 %** | sampled, 128 tirages |
| IS | placement intra-cellule | **0,46 %** | sampled, 128 tirages |

**Le placement des entreprises n'avait jamais été tiré à une seconde graine.** Une seule,
20260101, a produit tous les chiffres entreprises que ce projet a publiés. A0 la tire
correctement : sur l'IS à 30 %, −15,5262 md€ avec un écart-type de placement de 0,0717 md€.

**Et la lecture qui vaut plus que le classement : le placement pèse cinq fois plus, en
relatif, sur la CVAE que sur l'IS** — même mesure, même tirage. La raison est structurelle,
pas statistique : la CVAE est un instrument à coudes, l'IS est quasi linéaire sur la tranche
qui porte l'assiette, et un placement qui fait passer des entreprises de part et d'autre
d'un coude change le résultat là où une transformation linéaire l'absorbe. C'est l'argument
du refus seuil-sur-ratio (D-105.2), rencontré cette fois par la mesure et non par le
raisonnement.

### Deux cas de référence construits pour ne rien pouvoir dire, et le garde qui en sort

**CVAE.** Mon premier cas était `cvae_taux_max = 0,0028` — **la valeur en vigueur**. La
réforme chiffrait −0,0000 md€, sa variance de placement valait exactement zéro, et le
rapport l'a écrit : « placement, part 0,0 % ». Une phrase sur la CVAE qui était en réalité
une phrase sur une réforme qui ne fait rien. Porté à 0,5 % : −1,8545 md€, et la source
apparaît.

**IFI.** Mon premier cas était le barème inchangé. Or `placement.band` rend un **point** à
barème inchangé — les tests patrimoine l'affirment eux-mêmes comme garde anti-théâtre
(« the baseline band is a point, not an interval »), puisque seule une réforme qui coupe une
tranche ouvre l'encadrement. Le cas mesurait donc rigoureusement zéro. Porté au seuil à
2 M€ : largeur 0,1753 md€ sur −1,0052 md€.

**Et en corrigeant l'IFI j'ai fabriqué un barème non monotone** : j'avais réécrit le seuil
de 800 k€ en 2 M€ **en laissant 1,3 M€ derrière**, donnant `[(2,0 M€, …), (1,3 M€, …), …]`.
Le module a rendu un nombre sans broncher. Le seuil d'assujettissement est la ligne 1,3 M€,
et l'élever supprime la ligne 800 k€ — c'est le barème que les tests patrimoine utilisent
pour ce cas exact. Une vérification de monotonie est maintenant dans le code.

`central_for` refuse désormais tout cas de référence sous 50 M€ de chiffrage — **une
réforme nulle rend toute part de variance calculée dessus une affirmation sur le néant.**
C'est la règle permanente « une comparaison n'est pas testée tant que les deux côtés ne sont
pas non nuls », arrivée dans un endroit nouveau. Vérifié dans les deux sens : la valeur
0,0028 est refusée, les trois cas retenus passent.

### La résolution de l'instrument, qui n'est pas une source

Douze tirages de sous-échantillon à n = 4 000 sur la décote : écart-type **0,0427 md€, soit
1,37 %**. **Cette variance vaut exactement zéro en production** — `run(sample=None)` chiffre
la frame entière. Ce n'est donc pas une erreur du modèle, et la classer comme telle enverrait
la phase 7 vers une grandeur qui n'existe pas quand le modèle tourne. Elle est rapportée dans
sa propre section, et ce qu'elle borne est la **finesse d'A0 lui-même** : à 1,37 %, une
source qui pèse 0,46 % est indiscernable du bruit de tirage sur un sous-échantillon de cette
taille. La contribution IS est donc mesurée sur la chaîne entreprises, qui n'échantillonne
pas — et il fallait le dire.

C'est le jumeau du piège de l'uprating (D-115) : deux grandeurs qui ressemblent à de
l'incertitude et n'en sont pas, toutes deux repérées par la même question.

### Ce que ce passage NE dit pas

Quatre des huit cas n'ont **aucune source mesurable aujourd'hui**, et trois sources déclarées
par la spec sont NON MESURÉES avec leur raison — le store comportemental (attribuer par
paramètre demande une passe moteur par cas, prévu en v2), la construction de population
(reconstruire à une seconde graine est un gate en soi), l'uprating (bornes à sourcer). Le
classement ordonne **ce qui a pu être mesuré**, pas l'ensemble des erreurs du modèle. Le lire
autrement serait exactement l'erreur que ce budget existe pour éviter, et le rapport le dit
dans son propre texte.

## D-117 — Le drapeau `--durations` était inerte, et je l'avais ajouté pour répondre à une question

**2026-09-10.** Quatrième défaut trouvé dans le gate lui-même, et le premier que j'ai
**fabriqué en corrigeant le troisième**.

D-114 ajoutait `--durations=15` à la cible `full` avec une justification explicite : « pour
que le prochain "pourquoi est-ce si long ?" se réponde depuis le journal plutôt que d'être
redérivé ». La passe suivante a été verte — `1338 passed, 2 skipped, 60m44s` sur `2917acf` —
et le fichier de sortie faisait **180 octets**. Aucune ligne de durée.

La cause : pytest écrit dans `$out`, la recette n'en imprime que `tail -1` en cas de succès
(`tail -40` seulement en cas d'ÉCHEC), puis `rm -f $$out`. Le bloc de durées était produit,
écrit, puis supprimé sans jamais être lu. **Le drapeau tournait et ne servait à rien.**

C'est la troisième question permanente prise par l'autre bout : je demande « ai-je déjà vu
ce contrôle échouer ? » ; il fallait demander **« ai-je déjà vu cette sortie exister ? »**.
Ajouter un instrument et ne pas vérifier que son résultat survit revient exactement au même
défaut — quelque chose qui a l'air de mesurer et ne mesure rien.

Corrigé : le bloc est extrait par `awk "/slowest .* durations/,0"` vers
`reports/full_pass_durations.md`, avec la date, le commit et les comptes. **Vérifié en
faisant tourner les lignes exactes de la recette sur une vraie sortie pytest courte** — pas
sur un fichier fabriqué, et pas en se contentant de `make -n`.

### Et la correction elle-même contenait un no-op silencieux

Mon script de correction faisait deux substitutions. La première portait
`assert old in s` ; la seconde, non — elle cherchait `LOG = reports/...` alors que le
fichier écrit `LOG  := reports/...`. **`str.replace` ne signale rien quand le motif est
absent** : `DURATIONS` n'a jamais été défini, et la recette redirigeait vers une chaîne
vide. Attrapé en relisant `grep "^DURATIONS"` juste après, qui ne rendait rien.

La règle qui en sort, et elle vaut au-delà des Makefile : **toute substitution de texte
porte son ancrage assertif**, sinon un remplacement qui ne remplace rien passe pour un
succès. Deux substitutions, une assertion : c'est celle sans assertion qui a échoué.

### Ce que la passe a par ailleurs établi

`2917acf` · **1338 passed, 2 skipped, 60m44s**, machine au calme. Deux sauts et non cinq :
les budgets de temps ont tourné. Et la passe précédente n'avait jamais abouti — je l'avais
lancée avec un `&` dans un appel de premier plan au lieu du mode fond du harnais, si bien
que le shell et toute sa descendance ont été moissonnés à la fin de l'appel
(`make: *** [full] Terminated: 15`). **Aucune ligne n'a été écrite au journal** dans ce
cas-là, contrairement au cas D-113 : quand `make` lui-même reçoit SIGTERM, le `printf` de
fin de recette ne tourne jamais. Le journal ne peut donc pas enregistrer sa propre mort par
le haut, et c'est une limite à connaître plutôt qu'un défaut à corriger — un journal écrit
par un processus tué ne serait pas plus fiable.

## D-118 — A0 v2 : l'attribution comportementale fonctionne, et son résultat est un refus

**Phase 7, 2026-09-11.** `src/impots/accuracy_behavioural.py`. Le mécanisme est juste, il
tourne, il est instantané une fois la passe moteur payée — et **ce qu'il produit n'est pas
classable**. C'est le résultat, établi par la mesure et non par l'argument.

### Ce qui est attribué, et pourquoi ce n'est pas une variance

Mon premier jet attribuait la **variance**, en lisant les tirages par canal sur le résultat.
`BehaviouralResult` **ne les expose pas** : il porte `band` en trois percentiles et
`channels` en dicts de trois percentiles ; les tableaux de tirages sont locaux à `compute`
et meurent avec elle. J'avais écrit `result._channel_results` — un attribut inventé. Des
percentiles ne s'additionnent pas, donc aucune décomposition de variance n'est disponible
par l'API publique, et aller chercher les internes des canaux ferait dépendre l'attribution
d'une forme privée.

La quantité attribuée est donc **la largeur de la bande publiée, p90 − p10**. Deux mérites :
elle est honnêtement accessible, et c'est le nombre qu'un lecteur de fiche voit. Ce n'est
PAS une décomposition de variance et le module ne l'appelle jamais ainsi : les contributions
ne sont pas normalisées à 100 %, et l'écart — les effets conjoints — est une ligne du
tableau.

### Le garde qui compte : refuser quand le grade bouge

`compute` applique `grading.widen` avant de prendre la bande : un canal noté
*illustrative* voit sa bande étirée d'un facteur deux autour de sa médiane. **Si épingler un
paramètre change le grade, les deux largeurs diffèrent par un étirement post hoc autant que
par le paramètre**, et leur différence serait la somme de deux choses sans rapport présentée
comme une. Quatrième question permanente, à l'endroit où elle aurait fait le plus de dégâts.
Le grade est donc relevé à chaque évaluation et toute ligne où il a bougé est refusée.

### Le résultat : non résolvable au sous-échantillon

Balayé sur quatre tailles, deux cas :

| n | décote : largeur / dominante | plafond QF : largeur / dominante |
|---|---|---|
| 2 000 | 0,0359 md€ / `eti_top_decile` 33,7 % | 0,2620 md€ / `eti_top_decile` 92,1 % |
| 3 000 | 0,0607 md€ / `eti_top_decile` 87,8 % | 0,0322 md€ / **`eti_all` 100,0 %** |
| 4 000 | 0,0264 md€ / `eti_top_decile` 44,9 % | 0,0420 md€ / `eti_top_decile` 33,4 % |
| 6 000 | 0,0326 md€ / **`eti_all` 30,0 %** | 0,0287 md€ / **`eti_all` 59,3 %** |

**La largeur de bande varie d'un facteur 9,1 selon la taille du sous-échantillon**, sans
tendance, et la ligne dominante bascule sur les deux cas. Un classement lu sur une seule
taille est un fait sur le tirage, pas sur le modèle.

**La cause était déjà mesurée dans le même rapport, par moi, une section plus haut.** La
résolution de l'instrument donne le bruit de sous-échantillon à ~1,4 % du chiffrage, soit
~0,043 md€ sur une décote de 3,1 md€. Les largeurs de bande valent 0,026 à 0,062 md€ — **le
même ordre de grandeur**. J'avais écrit noir sur blanc qu'« une source dont la contribution
est plus petite que cet écart-type est indiscernable du bruit de tirage », puis construit
v2 sans appliquer la phrase.

### Ce que j'ai failli publier

Après **un seul cas** (n = 3 000), j'ai lu « `eti_top_decile` porte 87,8 % de la bande » et
j'allais en faire un fait général sur le store — d'autant plus séduisant qu'il était
contre-intuitif : une réforme de décote, instrument des ménages modestes, dont l'incertitude
serait portée par l'élasticité du décile supérieur. Le second cas a rendu `eti_all` à 100 %.
Le balayage a rendu les deux, selon la taille.

C'est la deuxième question permanente — **ai-je testé sur une autre forme que celle qui m'a
alerté ?** — et la réponse était non jusqu'à ce que je la pose.

### Ce qu'il faudrait

Une passe sur la **population complète** (199 451 ménages, `sample=None`), où le bruit de
tirage est nul par construction. C'est un travail par lots, pas une passe de quarante
secondes. **L3 n'est donc pas classé, et son score au dossier est « non résolvable au
sous-échantillon »** — la spec dit que refuser du travail est un résultat ; publier le
classement de n = 3 000 en aurait été un autre, faux.

Et une réforme de pure prestation (RSA, allègements) est **refusée** plutôt que classée :
aucun canal de revenu ne s'y applique, la bande publiée est de largeur nulle, et répartir
zéro entre des paramètres produirait un classement de rien.

## D-119 — Gate L4 : le taux effectif sectoriel n'est pas dans le fichier, et le déficit est un flux

**Phase 7 L4 M0, 2026-09-11.** `scripts/verify_stat39.py`. Le levier L4 est celui que A0 a
classé en tête ; sa spec porte un item **NON MESURÉ** explicite — « quelle publication DGFiP
porte le stock de déficits reportables : le gate le découvre ». Il le découvre, et il
découvre aussi que le premier item ne peut pas être construit tel qu'il est formulé.

### Item 1 : « des taux effectifs sectoriels tirés de Stat 39 » — impossible

Le Tableau 1 porte bien une ventilation **par secteur** : dix secteurs, résultat fiscal et
IS brut, qui somment au total à **0,00e+00 près** une fois écartée la ligne « dont industrie
manufacturière » (un sous-ensemble d'Industrie ; l'inclure double-compterait 31,4 md€, et
c'est l'exactitude de la somme qui prouve que l'exclusion est la bonne).

Mais leur rapport n'est pas un taux effectif, et **le fichier le prouve sur ses propres
chiffres** : IS brut / résultat fiscal vaut **40,1 %** au niveau agrégé contre un taux normal
de **25 %**, et « Autres activités » atteint **125,8 %**. Un impôt ne peut pas dépasser sa
base. Les deux colonnes ne partagent donc pas de périmètre.

La raison est dans une autre feuille du même classeur. Graphique 2 décompose le **bénéfice
imposable** par taux, et l'identité tombe :

    B.I. 283,65 md€  +  déficit −111,9 md€  =  171,75  contre  172,0 publié   (−0,17 %)

**Le résultat fiscal est NET des déficits ; l'IS est assis sur la base POSITIVE.** Sur le bon
dénominateur le taux redevient sain : IS / bénéfice imposable = **24,34 %**, à 0,08 point du
« taux moyen d'imposition » que la publication calcule elle-même (24,26 %), et juste sous les
25 % comme la tranche à 15 % l'implique.

**Or le bénéfice imposable n'est publié que nationalement, ventilé par TAUX et non par
secteur.** La ventilation sectorielle existe donc uniquement sur le mauvais dénominateur.
Construire des « taux effectifs sectoriels » depuis ces tables produirait des taux supérieurs
à 100 % — la spec supposait une grandeur que la source ne porte pas.

### Item 2 : le stock de déficits reportables — réponse mesurée, et c'est non

Graphique 2 porte le déficit **imputé chaque année** : −65,4 / −60,2 / −100,9 / −83,1 /
−113,3 / −101,8 / −111,9 md€ de 2018 à 2024. C'est un **flux** — ce qui a été absorbé — et
non le **stock** de ce qui reste à absorber. La forme le dit : un stock ne ferait pas ces
allers-retours d'une année sur l'autre. **Stat 39 ne porte pas le stock.** L'étiquette NON
MESURÉE de la spec est donc levée par un constat négatif, qui est un résultat : chercher
ailleurs, ou renoncer, mais pas construire sur ce fichier en croyant l'avoir.

### Deux pièges de lecture, dont un déjà vu deux fois

Dans Graphique 2, **les libellés sont en colonne 1** (pas 0, les données commencent ligne 21
sous un bloc de titre) et **toutes les valeurs sont des chaînes** — `'18.223428762'`. Un
filtre `isinstance(x, float)` rend une série vide et une somme de zéro **sans erreur**.
C'est la troisième fois que cette classe apparaît dans ce projet : les colonnes à virgule
décimale du REI, le `value: 6e-05` lu comme une chaîne par YAML 1.1, et maintenant un
classeur DGFiP. Ici le script a planté bruyamment parce que la clé n'existait pas — de la
chance, pas de la conception, et le commentaire le dit.

**Et un défaut de millésime dans la source elle-même** : l'en-tête de colonne du Tableau 1
annonce « Variation 2022/2023 » alors que le titre du même tableau dit « variation du
résultat fiscal entre 2023 et 2024 ». Sur une publication de septembre 2025 portant sur
2024, c'est l'en-tête qui a tort. Non corrigé de notre côté : nous ne lisons pas cette
colonne, et la noter suffit.

### Ce que L4 devient

L'item « ratios sectoriels » est **écarté avec son constat**, pas reporté : la donnée
n'existe pas dans la source que la spec désignait. L'item « stock de déficits » est **ouvert
et non résolu** — aucune publication n'a été trouvée qui le porte, et la règle du pointeur
interdit d'en nommer une sans l'avoir confrontée aux octets. Ce qui reste de L4 est le
diagnostic de périmètre industrie/immobilier, qui n'est pas bloqué par de la donnée.

Refuser du travail est un résultat, dit la spec de phase. Ici le refus est mesuré, il est
rejouable (`scripts/verify_stat39.py`, neuf assertions), et il épargne une construction qui
aurait produit des taux effectifs supérieurs à 100 % avant que quiconque s'en aperçoive.

## D-120 — Gate L1 : la queue haute manque les deux tiers de son revenu, et c'est mesuré

**Phase 7 L1 M0, 2026-09-11.** `scripts/gate_l1_top_tail.py`. Contrairement à L4, ce gate
autorise son levier — et le chiffre qu'il rend est assez gros pour changer la lecture de
plusieurs lignes du modèle.

### La mesure

RFR par part fiscale, moyenne par fractile, population complète contre DGFiP n° 41
Tableau 2 :

| fractile | publié | simulé | écart |
|---|---|---|---|
| 3e au 9e dixième | — | — | **+0,3 % à +9,2 %** |
| dernier dixième | 65 532 € | 61 186 € | −6,6 % |
| **dont dernier centième** | 213 672 € | 140 677 € | **−34,2 %** |
| **dont dernier millième** | 916 590 € | 327 271 € | **−64,3 %** |

La distribution synthétique est **trop resserrée** : le 2e dixième est 9,4 % trop bas, les
dixièmes 5 à 9 sont 3,6 à 9,2 % trop hauts, et l'extrémité s'effondre. Au millième supérieur
il manque près des deux tiers du revenu.

**Et cette grandeur-là est résolvable**, contrairement à celle de A0 v2 : n = 20 000 et la
population complète donnent 327 734 € et 327 271 €, soit 0,1 % d'écart. n = 4 000 rend
253 811 € — sans surprise, le millième supérieur d'un échantillon de 4 000 foyers, c'est
quatre foyers. Le gate mesure donc aux trois tailles et publie l'écart plutôt qu'un chiffre.

### Ce que la mesure implique pour les lignes existantes

Trois lectures du rapport de réconciliation reposent sur cette queue et doivent être relues
à la lumière de ce chiffre : la ligne barème (dont le résidu est déjà déclaré comme un
PLANCHER), le rapport interdécile D9/D1, et toute question CDHR — la contribution mord au
centile supérieur, là où il manque un tiers du revenu.

### Le piège de lecture, et il a failli refuser le levier

Le Tableau 2 a **24 colonnes**, et son en-tête de groupe (« RFR par part fiscale ») est une
ligne AU-DESSUS de l'en-tête de colonne (« Moyenne (en €) »). Lu sur les dix premières
colonnes, le tableau semble ne publier que de l'IMPÔT par fractile — et j'ai commencé par
écrire exactement cela, en concluant que L1 était impossible **pour la même raison que L4 la
veille** : la ventilation existe, mais sur la mauvaise grandeur.

C'était faux. La colonne 3 est un revenu, et les 916 590 € du millième supérieur sont une
moyenne de RFR par part. Ce qui a rattrapé l'erreur est d'avoir lu **les 24 colonnes** avant
de conclure, au lieu des 10 qui tenaient à l'écran.

**La leçon n'est pas « lire tout le fichier ».** C'est que je venais de refuser un levier
pour une raison de forme précise, et que cette forme est devenue le motif que je cherchais
dans le fichier suivant. Un refus fraîchement écrit est un biais, pas une grille de lecture.

### Ce que construire L1 coûtera, à dire avant de commencer

Caler la queue sur les fractiles publiés **dépense n° 41 comme source de validation** : une
fois le calage fait, les lignes IR du haut de distribution s'ajustent par construction et ne
peuvent plus être citées comme preuve de quoi que ce soit. C'est la même règle que pour
l'imputation des niches (D-064 et suivants) : opt-in, inscrit au registre des dépenses,
artefacts déclarés — « tous les foyers d'une cellule reçoivent la même base », identités
tirées sur graine.

Le gate autorise donc L1, avec sa facture énoncée d'avance.

## D-121 — L1 construit : la queue recalée, et le prix qu'elle coûte au total calibré

**Phase 7 L1, 2026-09-11.** `src/impots/population/top_tail.py`, `tests/test_top_tail.py`.
Le gate (D-120) avait autorisé le levier et énoncé sa facture d'avance ; voici la
construction, et la facture s'est révélée plus grosse que prévue.

### Ce que le recalage fait

Mesuré sur la population complète, moyenne de RFR par part, avant et après :

| bande | cible | avant | après |
|---|---|---|---|
| 2e au 9e dixième | — | −9,4 % à +9,2 % | **±0,9 %** |
| 90–99 % | 49 072 € | +6,7 % | −0,2 % |
| 99–99,9 % | 135 570 € | −11,6 % | +0,8 % |
| **99,9–100 %** | 916 590 € | **−64,3 %** | **+7,8 %** |

Le millième supérieur passe de 327 271 € à 987 747 €. Toutes les autres bandes rentrent à
moins d'un point.

### C'est une REDISTRIBUTION, et c'est ce que la conversion emboîtée→disjointe révèle

n° 41 publie « dernier dixième », puis « dont dernier centième » et « dont dernier millième »
**à l'intérieur**. Les traiter comme trois bandes séparées compterait le millième trois fois
et produirait des cibles qu'aucune distribution ne peut satisfaire ensemble. Converties en
bandes disjointes, elles disent : 90–99 **descend** (×0,94), 99–99,9 monte (×1,13),
99,9–100 monte de ×2,80 — et les dixièmes 5 à 9 descendent de 3 à 8 %.

Un simple abondement du sommet était donc impossible : **le centile supérieur manque 36 md€
quand le dixième entier n'en manque que 23**, si bien qu'ajouter au centile ferait dépasser
le dixième sa propre moyenne publiée. La distribution synthétique n'est pas seulement courte
en haut, elle est **comprimée aux deux bouts**.

### Le prix : −2,03 % sur le total des revenus

Le recalage ne peut PAS à la fois coller aux fractiles publiés et préserver le total
calibré. Mesuré : 1 548,0 → 1 516,5 md€, soit **−2,03 %**, et 61,84 M de foyers pondérés
déplacés. La masse salariale était calibrée ; le recalage la déplace de deux points.

Ce n'est pas une contradiction entre sources — la masse salariale (comptes nationaux) et le
RFR des foyers déclarants ne mesurent pas le même périmètre — mais c'en est une pour NOTRE
population, qui ne peut pas satisfaire les deux. Le chiffre est **rendu par `apply`** et non
absorbé : une calibration qui déplace en silence un total auquel le modèle est calibré est
exactement la forme d'une ligne qui se valide elle-même.

### Trois artefacts déclarés, dont un qui laisse un résidu visible

1. **Le facteur est uniforme dans une bande.** Un foyer au 99,91e centile reçoit le même
   ×2,80 qu'un foyer au 99,99e. La donnée publiée ne les distingue pas, et inventer un
   gradient intra-bande serait inventer une densité — même artefact et même refus que
   l'imputation des niches.
2. **L'appartenance aux fractiles est calculée AVANT le recalage et non recalculée.** Le
   recalage fait franchir les frontières, d'où le **+7,8 %** résiduel au millième :
   `residuals()` le publie au lieu d'itérer jusqu'à ce qu'un nombre soit joli. Une passe est
   la chose honnête à livrer, le résidu la chose honnête à publier.
3. **La composition interne d'un foyer est préservée.** Un seul facteur multiplie toutes les
   colonnes monétaires, donc le mélange salaire/pension/chômage ne bouge pas. **Ce n'est pas
   neutre** : le vrai millième supérieur est bien plus riche en capital et en BNC que le
   nôtre, et multiplier des salaires ne sait pas représenter cela. Le recalage rend le
   NIVEAU juste et laisse la COMPOSITION aussi fausse qu'elle l'était.

### Deux défauts attrapés dans ma propre construction

**`BANDS` fabriquait « 1e dixième » quand la publication écrit « 1er dixième ».** Un libellé
qui ne correspond pas n'est pas une erreur : c'est une bande **silencieusement non recalée**.
Sans effet aujourd'hui — le premier dixième est publié « n.s. » et n'a aucune cible — et un
piège le jour où il en aurait une.

**Et `apply` fabriquait ses `band_factors`** à partir d'une médiane, dans un `zip` à un seul
élément : un champ qui avait l'air de rapporter les facteurs par bande et n'en rapportait
aucun. Corrigé en faisant rendre à `factors()` le tableau ET le dictionnaire, qui est la
seule source où ils existent.

## D-122 — L1 câblé : le levier s'applique, et la source qu'il dépense est refusée

**Phase 7 L1, suite et fin, 2026-09-12.** D-121 livrait le module et ses tests et je l'ai
annoncé « construit ». **Il ne l'était pas** : `top_tail` n'était appelé par rien — ni
drapeau sur `run()`, ni enregistrement de la dépense. La spec disait « opt-in,
spent-registered » et aucune des deux moitiés n'existait. Un composant mesuré et testé hors
du pipeline n'est pas un levier ; c'est la pire des situations, celle où quelqu'un supposera
plus tard que le recalage est actif.

### Moitié une : le drapeau, et un ordre qui porte

`run(..., rake_top_tail=False)`, off par défaut — une calibration qui tournerait sauf
demande contraire serait le pire défaut imaginable : tout l'aval serait ajusté et personne
ne le saurait. `_rake_top_tail` suit la forme de `_impute_niches`, et pour la même raison :
la bande d'un foyer dépend de son RFR par part, qui est une SORTIE, d'où une passe
supplémentaire.

**Le recalage passe AVANT l'imputation des niches, et l'ordre est porteur.** Les bases de
niches sont distribuées par décile de RFR par part ; le recalage déplace le RFR par part.
Imputer d'abord distribuerait des bases selon un classement que le recalage invalide
ensuite — une population plausible que personne ne pourrait relier à un défaut. L'ordre est
asserté sur le source, pas seulement commenté.

Vérifié de bout en bout à n = 20 000 : `salaire_brut` passe de 1 120,668 à 1 103,397 md€
(−1,54 %, cohérent avec les −2,03 % de la population complète), les gardes
`top_tail_total_shift` et `top_tail_foyers_moved` apparaissent, le chronométrage `rake_s`
aussi. Drapeau à False : aucune des trois.

### Moitié deux : la dépense est refusée, pas seulement documentée

`Line.raked_top_tail` rend **« not comparable (queue recalée) »** avant toute évaluation de
tolérance. C'est la condition d'achèvement de L1 et l'analogue exact de celle de F3 M2 : une
fois le recalage passé, les lignes IR du haut collent aux fractiles publiés par
construction, et un verdict de tolérance rapporterait **le recalage qui fonctionne** plutôt
que le modèle qui a raison.

Champ séparé de `population_year` plutôt que fondu dedans, parce que les deux refus n'ont
pas la même raison : une population vieillie est comparée à la mauvaise ANNÉE, une
population recalée à un chiffre auquel elle a été ajustée. Deux raisons, deux messages, et un
test qui exige qu'ils diffèrent.

Le kill test accompagne le refus : **la même ligne sans le drapeau doit rendre un vrai
verdict**, sinon le refus ne prouve rien sur le drapeau.

### La leçon, qui n'est pas sur le code

J'ai écrit « L1 construit » sur un module que rien n'appelait. Les tests passaient, la
mesure était juste, le docstring promettait « opt-in, spent-registered » — et la promesse
tenait lieu d'implémentation. **Un docstring qui décrit un câblage absent est la forme
documentaire du contrôle qui ne peut pas échouer** : il se relit correctement et ne fait
rien. C'est la question « ai-je déjà vu cette sortie exister ? » (D-117) appliquée non à une
sortie mais à un point d'entrée.

## D-123 — La colonne durée mesurait l'horloge murale, sommeil compris

**2026-09-12.** Cinquième défaut trouvé dans le journal de passe, et le troisième que ce
projet y trouve depuis qu'il a décidé de regarder son instrument avec les mêmes dents que
son modèle.

La passe sur `31741ae` s'est journalisée **PASS, 359m55s** — six fois la norme — avec
`1356 passed, 2 skipped`. Rien n'avait ralenti : les quinze tests les plus lents étaient aux
mêmes temps qu'à la passe précédente (266 s contre 290 s pour le plus lourd). Le temps
n'était donc pas dans les tests.

**Et pytest disait la réponse dans la ligne que je jetais.** Son résumé porte
« in 3496.55s (0:58:16) » : la suite a travaillé **58 minutes**. `elapsed` est un écart de
`date +%s`, donc de l'**horloge murale** — il compte les cinq heures pendant lesquelles la
machine a dormi. Le `sed -E 's/ in [0-9].*$//'` qui fabrique la colonne « comptes » coupait
précisément la durée réelle avant de la lire.

Un lecteur futur comparant « 359m55s » à la norme d'une heure conclurait à une catastrophe
qui n'a pas eu lieu. C'est la même famille que D-113 (un run tué écrit ÉCHEC) et D-117 (le
bloc de durées produit puis supprimé) : **l'information existait, était produite, et était
détruite par le code chargé de la rapporter.**

Corrigé : la colonne porte le temps **travaillé**, lu dans le résumé de pytest ; l'horloge
murale ne la suit que lorsqu'elle en diverge de plus de 20 %, et alors elle est **nommée**
— « 58m16s (horloge 359m, machine en veille) ». Un run tué, qui ne produit aucun résumé,
retombe sur l'horloge murale, faute de mieux et en le sachant.

Vérifié sur la vraie ligne de résumé de la passe concernée et sur le cas sans résumé. **La
ligne déjà écrite a été corrigée dans le journal plutôt que laissée** : elle affirmait une
durée fausse, et un journal de passes dont on tolère une ligne fausse ne vaut pas plus que
l'absence de journal.

**Ce que la passe établit par ailleurs** : `31741ae`, **1356 passed, 2 skipped**, deux sauts
et non cinq — les budgets de temps ont tourné. L1 câblé est vert.

## D-124 — Une marque posée par composition est invisible à un grep du décorateur

**2026-09-13, C3 partiel.** J'avais relayé un constat depuis le bloc de durées de D-117 :
« huit des quinze tests les plus lents sont des tests API, chacun payant sa propre passe
plein tarif, et aucun n'est marqué slow ». **Les trois parties sont fausses**, et la
vérification les défait une à une.

**Neuf, pas huit.** Compté depuis le fichier : 9 `test_api.py`, 3 `test_population.py`, 1
chacun pour `test_scenarios`, `test_niche_imputation`, `test_knobs`.

**Les quinze sont marqués slow, sans exception.** Vérifié par comparaison d'ensembles :
`pytest --collect-only -m slow` en collecte 217, et **zéro** des quinze plus lents en est
absent. La porte rapide (`addopts = "-m 'not slow'"`) les saute donc déjà tous. Il n'y a pas
de test lourd non marqué, et rien à corriger.

**Les POST tournent en tier « quick »**, pas plein tarif ; seules les passes de taux
marginal de la bande sont plein tarif, et le client à portée de module les paie une fois par
conception — le fichier le dit dans son propre en-tête.

### La cause mécanique, nommée avant toute autre explication

`tests/test_api.py:375` définit `population_test = needs_population(pytest.mark.slow(f))`.
**La marque est appliquée par composition, à travers un enrobage.** Un `grep
"pytest.mark.slow"` la trouve sur les six autres (test_population 610/655/742,
test_scenarios 373, test_niche_imputation 209) et **ne la trouve jamais** sur les neuf tests
API. Mon compte de « 14 tests slow » à D-114 venait du même grep, et j'avais déjà corrigé ce
chiffre une fois — de 14 décorateurs à 217 cas — sans voir que le grep manquait aussi des
fichiers entiers.

Et le décorateur explique lui-même pourquoi il compose : « composé pour que les deux faits
voyagent ensemble : tout test qui fait tourner la population est aussi un test que la porte
rapide saute, et oublier la seconde marque est la façon dont une porte rapide cesse
discrètement d'être rapide ». La bonne pratique du dépôt est exactement ce que mon outil de
lecture ne savait pas voir.

### La règle

**Pour connaître les marques d'un test, on demande à pytest, on ne grep pas le source.**
`--collect-only -m slow` contre l'ensemble attendu ; une comparaison d'ensembles, pas une
recherche de motif. Un grep du décorateur littéral rend un sous-ensemble silencieux dès
qu'une marque passe par un enrobage, une fixture paramétrée ou un `pytestmark` de module.

Même famille que D-113, D-117 et D-123 : **l'instrument, pas le modèle.** Quatre fois de
suite, le défaut était dans ce qui rapporte et non dans ce qui calcule.

### Et le suivi tentant est refusé

Mémoïser la baseline entre tests API achèterait de vraies minutes (neuf tests à 60-130 s).
**Refusé par défaut** : la quasi-fausse-découverte née d'une baseline mémoïsée est déjà au
dossier (D-095), et un cache qui laisse des tests de population se confirmer mutuellement
achète des minutes contre du risque de justesse. Si quelqu'un le veut quand même : derrière
un kill test d'empoisonnement de cache — corrompre délibérément une entrée, un test
dépendant DOIT échouer — et une clé incluant réforme, tier, graine et somme de contrôle de
la population. Sans cet appétit, la passe complète coûte ce que coûte l'honnêteté.

## D-125 — C1 : le diagnostic de périmètre tient, et sa portée était surdite

**Phase 7 C1, 2026-09-13.** `scripts/verify_perimetre.py`. La procédure de l'addendum du
2026-09-02 — deux contrôles mécaniques avant toute hypothèse économique — était réputée
n'avoir jamais tourné. Elle avait tourné : sa conclusion était écrite dans
`margins.POOLED_SECTORS`. **Rien ne la vérifiait**, exactement l'état où étaient les
constats REI avant `verify_rei.py` : une mesure faite une fois, crue ensuite.

### Les deux contrôles, rejoués

**Un — sur une grandeur que le modèle ne touche pas.** Effectifs d'entreprises par secteur,
Ésane brut sur DGFiP : **1,90 à 2,22** dans le champ marchand — c'est le taux
d'assujettissement à l'IS — et **0,48 pour les activités immobilières**. Deux sources qui
divergent d'un facteur quatre sur un comptage qu'aucune réforme ne peut déplacer : le résidu
est de périmètre, pas de modèle.

**Deux — décomposition du résidu par taille.** **88,4 %** de l'IS industrie modélisé est en
ETI et GE. Concentration dans les grandes unités : effet de groupe. Une répartition uniforme
aurait désigné la construction d'assiette.

**Et le résidu lui-même** : industrie modélisée 21,055 md€ contre 15,230 publié, **+38,3 %**
— le chiffre au dossier, reproduit.

**État terminal de C1 : cause mécanique nommée.** Ésane classe des entreprises *profilées*,
la DGFiP des *unités légales* ; le bras immobilier d'un groupe industriel est consolidé dans
l'industrie d'un côté, imposé dans l'immobilier de l'autre. Les deux résidus ont des signes
opposés parce que c'est la même activité comptée des deux côtés d'une frontière que les
sources tracent différemment.

### La correction : « dans tous les secteurs » était faux

L'énoncé disait que le rapport vaut 1,90-2,22 **« in every sector »**. Ce n'est pas le cas :
administration 8,94, autres activités 4,33, finance 0,70, agriculture 0,12. Ces quatre-là
sont **hors du champ « principalement marchands »** d'Ésane — que `cells.py` nomme déjà — et
ne sont pas comparables sur un effectif.

Ramené au champ marchand, l'énoncé est exact, et **l'immobilier devient le seul aberrant** :
la portée corrigée rend le diagnostic plus fort, pas plus faible. Un quantificateur
universel non vérifié avait transformé un constat net en affirmation fausse.

### Deux pièges de lecture, tous deux silencieux

**Ésane ne déclare aucune dimension.** `ws.max_row` vaut 1, `calculate_dimension()` rend
« A1:A1 », et un `iter_rows` sans `max_row` explicite **ne rend rien du tout** — un ensemble
vide qui a l'air d'un résultat. Mon premier passage de ce contrôle a construit un
dictionnaire vide et n'a échoué que parce que `min()` a levé dessus.

**La colonne d'effectifs de Stat 39 est titrée « en milliers » et porte des unités.**
« Tous secteurs » vaut 2 718 376,9, et le Graphique 1 confirme 2,718 **millions**
d'entreprises. Multiplier par mille, comme l'en-tête l'ordonne, met tous les rapports à
0,00 — ce qu'a fait mon premier jet. La charte nomme cette classe (« un en-tête d'unité qui
ment ») ; c'est la première fois qu'elle est rencontrée dans ce fichier.

## D-126 — C2 : la clé de répartition existe par dispositif, et deux pièges avant tout calcul

**Phase 7 C2, 2026-09-13.** Le gate de L5 demandait si la couverture des niches peut
dépasser ~55 %. **La donnée existe** : les deux fichiers DGFiP de répartition portent les
montants et les effectifs **par dispositif** et par décile de RFR par part, millésime 2024 —
23 crédits d'impôt et 31 réductions, 54 lignes en tout.

### Le piège qui aurait faussé tout taux de couverture

Les 54 lignes totalisent **27,11 md€**, alors que les Voies et Moyens chiffrent les RICI à
19,53 md€. L'écart n'est pas une erreur de lecture : les fichiers **mélangent des dépenses
fiscales et des crédits mécaniques d'impôt déjà payé** —

* CI prélèvement forfaitaire versé sur RCM : **7 648 M€**
* Crédit d'impôt sur revenus étrangers imposés en France : **3 658 M€**
* impôt payé à l'étranger, retenue à la source des non-résidents, régularisation du
  prélèvement libératoire : ~513 M€ de plus

Près de **11,9 md€ sur 27,11 ne sont pas des niches** : ce sont des imputations d'impôt déjà
acquitté. Un taux de couverture calculé sur ce dénominateur gonflerait la performance avec
des dispositifs qui ne sont pas l'objet. La question « quelle part des niches est
modélisée ? » n'a de sens qu'après ce tri.

### L'état par candidat, mesuré

Les cinq familles déjà modélisées pèsent ~11,1 md€ dans ce fichier (saldom 6 507, garde
1 796, dons 2 147, scolarité 468, syndicales 155). Les plus gros non modélisés, confrontés à
ce qu'openfisca sait calculer :

| dispositif | 2024 | openfisca |
|---|---|---|
| Investissement locatif Pinel | 1 544 M€ | **oui** (`duflot_pinel_denormandie_metropole`/`_om`) |
| Investissements outre-mer (entreprise) | 750 M€ | à vérifier (la variable trouvée est du logement) |
| Accueil en établissement (EHPAD) | 307 M€ | à vérifier (les variables trouvées sont l'APA) |
| Investissement locatif Scellier | 258 M€ | **aucune variable** → refusé avec motif |
| CI agriculture biologique | 157 M€ | **aucune variable** → refusé avec motif |
| Frais de comptabilité | 146 M€ | **oui** (`frais_de_comptabilite`) |
| Souscriptions au capital de PME | 101 M€ | **oui** (`cappme`) |

Immédiatement constructibles : **~1 791 M€**. Refusés faute de variable amont : Scellier et
agriculture biologique.

### Trois pièges de lecture dans ces fichiers, tous silencieux

1. **La colonne de décile porte des chaînes** — `'       1'`, avec des espaces de tête. Un
   filtre `isinstance(v, (int, float))` rend zéro ligne de données **sans erreur**, et le
   classement sort vide comme s'il n'y avait aucun dispositif. C'est ce qu'a fait mon
   premier passage.
2. **L'en-tête d'unité ment.** Une note dit « (montants en milliers d'euros) ». Les valeurs
   sont en **euros** : la somme du CI emploi salarié à domicile vaut 6,507 md€, à 1,4 % des
   6,420 md€ réalisés des Voies et Moyens, alors qu'en milliers elle donnerait 6 507 md€.
   **Troisième en-tête d'unité mensonger du projet, deuxième de la journée** après celui de
   Stat 39. Vérifié que `niches.py` n'applique aucun facteur 1000 — le code existant est
   juste.
3. Les feuilles portent un préfixe de ligne variable (`PAR_004`, `PAR_XXX`, ou rien selon le
   millésime), donc l'en-tête ne se trouve pas à un numéro de ligne fixe.

### Ce que C2 n'est PAS

**Rien n'a été construit.** Le gate dit que la donnée existe, nomme les candidats, chiffre le
gain accessible et refuse deux dispositifs faute de variable amont. La couverture n'a pas
bougé. Ce travail reste ouvert, avec son classement au dossier, et je le dis plutôt que de
laisser « C2 » cocher une case.

## D-127 — C3 : les 55 communes épinglées, l'hypothèse d'abattement à moitié fausse

**Phase 7 C3, 2026-09-13.** État terminal des 55 communes du REI dont l'identité
`base × taux / 100 + lissage = produit` ne reproduit pas le produit publié à 1 % près.

### La recherche de la cause, et son résultat négatif

L'hypothèse au dossier était « un abattement ou une exonération que ce module ne lit pas ».
Elle est **testable** : si un tel terme existe, il est publié quelque part dans les 1 043
colonnes du REI. Balayage sur les 55 communes, **454 colonnes non nulles testées** : aucune
ne reproduit l'écart. La plus proche, `BAMINTPT1`, en est à **71 % d'erreur médiane**.

**État terminal : épinglé, avec la tentative au dossier** — ce que le handoff autorise
explicitement comme clôture au même titre qu'une cause nommée.

### Et l'hypothèse était à moitié fausse

La note affirmait « leur taux effectif est sous leur taux publié », au pluriel universel.
Mesuré : **46 des 55 ont effectivement un calculé supérieur au publié — mais 9 vont dans
l'autre sens.** Un abattement non lu ne peut pas faire percevoir PLUS que l'identité ne
prédit. L'hypothèse ne couvre donc au mieux que 46 cas sur 55, et la note le dit désormais.

**Deuxième quantificateur universel non vérifié de la journée**, après « dans tous les
secteurs » de C1. Les deux venaient d'un constat juste dont la portée avait été élargie
sans être mesurée.

### L'ordre de grandeur, pour que l'épinglage soit lisible

Écart net **34 886 € sur 43,487 md€**, soit **8,0 × 10⁻⁷** du produit national — moins d'un
millionième. Cela ne rend pas l'anomalie acceptable, cela dit ce qu'il en coûte de la
laisser ouverte, ce qui est l'information dont un lecteur a besoin pour décider s'il y
revient.

### Un défaut dans ma propre mesure, et le garde qui l'a attrapé

J'ai d'abord recompté **54** au lieu de 55, et j'ai failli le porter au débit du module. La
cause est chez moi : le module divise par le produit **publié**, j'ai divisé par le produit
**calculé**. Deux dénominateurs, deux erreurs relatives, et une commune qui bascule de part
et d'autre du seuil de 1 %. Le choix du module est le bon — le publié est la grandeur de
référence.

Et la correction de la note a d'abord échoué sur une `assert old in s` : le texte était
replié sur plusieurs lignes et mon ancrage ne correspondait à rien. **L'assertion a fait
exactement son travail** — rien n'a été écrit — là où le `str.replace` sans ancrage de
D-117 avait silencieusement ne rien faire et laissé croire à un succès. La règle tenait.

## D-128 — La porte de relecture de la phase 7 est levée par le propriétaire

**2026-09-13.** Le handoff de clôture posait : « **Gate: Phase 8 M0 starts after C4 is
reviewed, not before.** Owner's sequencing request, now on the record. » Le propriétaire a
demandé explicitement de démarrer la phase 8 maintenant.

**La porte était la sienne ; il la lève.** C'est enregistré ici plutôt que passé sous
silence, parce qu'une séquence inscrite au dossier ne s'enjambe pas en silence — et parce
que le handoff dit lui-même « divergences from spec are expected and go to DECISIONS.md ».

**Ce que cela change et ce que cela ne change pas.** `docs/PHASE7_CLOSING.md` reste non
relu : aucun relecteur n'a donné de verdict sur C1-C4, et ce rapport ne devient pas juste
parce que la phase suivante commence. La phase 7 est **exécutée et verte**
(`76f0c49`, 1358 passed, 2 skipped, passe journalisée) — elle n'est pas **validée**. La
distinction est exactement celle que ce projet fait partout ailleurs entre une mesure et une
validation, et elle vaut pour son propre processus.

**Le reliquat qui part en phase 8 sans être clos** : C2 n'a rien construit. La donnée existe,
les candidats sont classés et chiffrés (~1 791 M€), la couverture des niches n'a pas bougé.
Dit ici pour qu'il ne se découvre pas au détour d'un handoff.

## D-129 — La charge d'intérêt 2026 vaut 58,6 md€, pas 77 : l'ancre de presse était une projection 2028

**Phase 8 M0, 2026-09-13.** Premier constat du gate de reconnaissance, et il corrige la spec
avant qu'une ligne de code de la phase ne soit écrite.

`PHASE8_SPEC.md` §1 R2 annonçait : « Secondary press puts the 2026 charge near €77 bn —
**UNMEASURED until the mission document is manifested.** » L'étiquette était la bonne ; la
mesure la contredit.

Manifesté : le projet annuel de performances (bleu budgétaire) du PLF 2026, mission
« Engagements financiers de l'État », 117 pages, sha256 `2715898f5466cd90…`. Tableau
« RÉCAPITULATION DES CRÉDITS PAR PROGRAMME ET TITRE POUR 2025, 2026, 2027 ET 2028 »,
programme 117 :

| colonne | montant |
|---|---|
| LFI 2025 | 54,207 md€ |
| **PLF 2026** | **58,615 md€** |
| prévision indicative 2027 | 68,660 md€ |
| prévision indicative 2028 | **76,676 md€** |

**Les ~77 md€ sont la projection indicative 2028.** La charge 2026 vaut 58,615 md€, et poser
t₀ sur 77 aurait surestimé l'ancre de **31 %** — dans un module dont toute l'arithmétique est
taux implicite × encours, cela déplace le taux implicite de moitié.

### Ce qui rend le rattachement des colonnes sûr

Le document imprime les variations à côté des montants : **+8,13 %, +17,14 %, +11,67 %**.
Elles se reproduisent exactement depuis les quatre valeurs. Le rattachement n'est donc pas une
lecture au jugé d'une colonne parmi quatre : il est **vérifié par une identité interne au
document**.

C'est le piège « colonnes d'année budgétaire » que le handoff signalait pour les Voies et
Moyens — « incident on record » — rencontré dans un autre document que celui pour lequel
l'avertissement avait été écrit. L'avertissement portait sur la source ; le piège portait sur
la forme.

### Et l'ancre de dette, elle, tient

Même gate, `insee_ir158_dette_t1_2026.pdf` (sha256 `71475685591aca39…`) : « la dette publique
au sens de Maastricht s'établit à **3 536,1 Md€** », « **117,5 %** du PIB ». Exactement le
chiffre que la spec portait en [VERIFIED], **désormais lu dans le fichier manifesté plutôt
que relayé**. Deux ancres au même gate : l'une confirmée, l'autre renversée, et seule la
lecture des octets distinguait les deux.

### R1 : l'AFT refuse les clients scriptés

`www.aft.gouv.fr` rend **403** sur tout : page d'encours, bulletins mensuels, chaque fichier
sous `/files/medias-aft/`, avec ou sans User-Agent de navigateur. Vérifié **depuis la machine
du propriétaire**, qui atteint insee.fr et data.gouv.fr sans peine — ce n'est donc pas le
blocage proxy du conteneur que le handoff décrivait, c'est un refus côté éditeur.

Des instantanés `web.archive.org` existent et portent des sha256 stables. **Ils ne sont pas
manifestés** : un instantané d'archive n'est pas le fichier de l'éditeur, et interposer un
intermédiaire dans la provenance de la donnée qui porterait l'échéancier de remboursement et
le taux implicite est une décision qui revient au propriétaire, pas à la session. R1 reste
**PARTIEL**, identifiants au dossier.

## D-130 — Amendement §3 : un encours à DEUX BLOCS, et la date qui faussait le partage

**Phase 8 M0, 2026-09-13.** Amendement à `PHASE8_SPEC.md` §3, demandé par l'addendum
2026-09-13 (bis) et à écrire avant toute ligne de code §3.

### Le défaut de périmètre, et pourquoi le tolérancer aurait été pire que de le laisser

L'ancre R2 (programme 117, **58,615 md€**) est la charge d'intérêt de la dette **de l'ÉTAT**.
L'encours b₀ de §3.1 (**3 536,1 md€**) est celui de **toutes les APU** au sens de Maastricht.
Le troisième kill test de §3.2 — taux implicite × encours ≈ ancre R2 — **échouerait donc sur
le périmètre**, et un implémenteur qui l'élargirait jusqu'à le faire passer aurait calibré
une erreur de périmètre dans le module. C'est la forme exacte que ce projet refuse partout
ailleurs : une tolérance qui absorbe un défaut le rend indiscernable de son absence.

### Le partage, mesuré à date commune

| bloc | 2025T4 | part |
|---|---|---|
| **Bloc 1** — État négociable, par ligne (AFT) | **2 737,0 md€** | 79,1 % |
| **Bloc 2** — État non négociable | 85,7 md€ | 2,5 % |
| **Bloc 2** — ODAC + APUL + ASSO | 637,8 md€ | 18,4 % |
| **Bloc 2**, total | **723,5 md€** | 20,9 % |
| somme | **3 460,5 md€** | — |
| APU publié (INSEE, 2025T4) | 3 460,5 md€ | écart **+2,2 × 10⁻¹⁶** |

Bloc 1 porte la machinerie fine de maturité et est ancré sur P117. Bloc 2 est porté à un taux
implicite agrégé, avec sa bannière de bloc grossier.

### La date faussait le partage d'un facteur douze

Premier calcul : INSEE État (Maastricht) **2 889,0 md€ au 2026T1** contre AFT dette
négociable **2 882,0 md€ au 31 juillet 2026** → composante non négociable de l'État ≈
**7 md€**. C'est faux, et faux de façon plausible.

Les deux chiffres ne sont pas à la même date, et entre les deux il y a quatre mois
d'émissions : le bulletin n° 435 donne la série négociable **fin 2023 / fin 2024 / fin 2025 /
fin juin 2026 / fin juillet 2026 = 2 430 / 2 602 / 2 737 / 2 858 / 2 882**. À **date
commune** (fin 2025 contre 2025T4) : 2 822,7 − 2 737,0 = **85,7 md€**. **Douze fois le
chiffre obtenu en différenciant deux dates.**

Quatrième question permanente — « de quoi ce nombre est-il la différence, exactement ? » —
appliquée à deux sources dont chacune est juste. Le module définira donc ses deux blocs **à
une date unique et déclarée**, et c'est une contrainte de construction, pas une préférence
de présentation.

### Le kill test du partage

Bloc 1 + Bloc 2 = total APU **par construction** de Bloc 2 (résidu) : cette égalité ne teste
rien. Le vrai test est que **Bloc 1 seul reproduise le total CT+MLT du bulletin**. Mesuré au
31 juillet 2026 : MLT **2 662** + CT **220** = **2 882** = encours négociable publié — exact.

Seconde ancre, au niveau total : **intérêts des APU (D.41, comptes nationaux)**, qui vérifie
Bloc 1 + Bloc 2 ensemble. **NON MESURÉE** tant qu'elle n'est pas localisée dans les fichiers
CN manifestés.

### Les trois fichiers AFT, manifestés

Servis par l'éditeur, capturés dans un navigateur interactif sur la machine du propriétaire
(l'AFT rend 403 à tout client scripté ; aucun intermédiaire d'archive). **Les sha256 ont été
RECALCULÉS depuis les octets sur disque**, jamais recopiés depuis l'addendum — une relecture
qui recopie l'attente du relecteur ne vérifie rien (D-042). Les trois concordent, tailles
comprises.

`aft_encours_detaille_oat_2026-09-13.html` (108 515 o, 59 ISIN distincts),
`aft_encours_detaille_btf_2026-09-13.html` (73 692 o, 30 ISIN),
`aft_bulletin_mensuel_435_aout_2026.pdf` (890 202 o, 7 p.).

**Durée de vie moyenne, mesurée** : dette négociable **8 ans et 163 jours**, MLT 9 ans et
42 jours, court terme 128 jours. L'« attendu ≈ 8-9 ans » de la spec est désormais un nombre
avec un fichier derrière.

**Règle de provenance actée** : les instantanés Wayback sont admissibles en reconnaissance,
**jamais comme entrée manifestée**. Et le parse HTML (ISIN, coupon, échéance) ira dans un
script de vérification avec kill tests, comme `verify_rei.py` — jamais en ligne dans le
moteur.

## D-131 — M1 §3.1 : l'identité de dette, ses refus, et le backtest qui est bloqué

**Phase 8 M1, 2026-09-13.** `src/impots/dette/path.py`, `tests/test_dette.py` (15 tests).

### Ce qui est construit

La récurrence `b_{t+1} = b_t (1+r_t)/(1+g_t) − p_{t+1} + sfa_{t+1}`, en ratio au PIB. C'est
de l'arithmétique, exacte à ses entrées près — **toute l'honnêteté du module est donc dans
les refus, pas dans l'algèbre**, et chaque refus porte son kill test.

* **Aucune trajectoire sans scénario de dépense NOMMÉ.** C'est le refus qui définit la
  phase. La dépense publique pèse ~57 % du PIB et seule la tranche des transferts est
  microsimulée ici : une trajectoire où les recettes bougent et où la dépense reste tue
  laisserait entendre que l'impôt porte seul l'ajustement — une implication que personne
  n'a écrite et que tout le monde lirait. **Aucun défaut n'est appliqué** : un défaut ici
  serait une affirmation politique déguisée en valeur par défaut d'ingénierie.
* **Aucun vocabulaire de probabilité dans le nom d'un scénario.** Rien ici n'a de modèle de
  probabilité. Le contrôle est **de forme denylist**, et le module le dit : une nouvelle
  façon d'écrire « probable » passerait. La version allowlist exigerait d'énumérer d'avance
  tout nom acceptable, ce que la « trajectoire personnalisée » interdit. La limite est
  énoncée plutôt que cachée — `refuse_banded` est au dossier pour avoir fait l'inverse.
* **Plafond d'horizon à 10 ans.** Au-delà, « l'arithmétique est exacte et vide ». Refusé par
  son nom, jamais tronqué en silence : une trajectoire raccourcie sans le dire ressemble à
  une trajectoire finie.
* **Le signe du solde primaire est SURPLUS POSITIF**, et il a son propre test. La
  littérature est partagée sur cette convention, et l'inverser retourne toutes les
  trajectoires en les laissant parfaitement plausibles.

**Trois mutations, trois captures.** Défaut silencieux au lieu du refus → le test du
scénario tombe. Plafond en `> cap+1` → le test d'horizon tombe. Signe du solde inversé →
deux tests tombent, dont la reconstruction de la décomposition §3.6. Les gardes savent
échouer.

### Le backtest 2019→2025 est BLOQUÉ, et c'est ma propre règle qui me l'oppose

L'addendum débloquait « §3.1 + le backtest 2019→2025 + §3.2 sur le Bloc 1 ». Le backtest ne
l'est pas, et le constat mérite d'être précis.

Le backtest exige la **SFA réalisée** — « omettre un terme réalisé et passer, c'est ajuster,
pas tester ». Or la SFA réalisée ne peut pas être dérivée de l'identité que le code
implémente : **elle passerait alors par construction**, ce qui est la forme D-044 appliquée
à un backtest entier. Il faut donc des composantes indépendantes : encours (manifesté),
PIB (manifesté), **et le compte des APU — capacité de financement et intérêts D.41**.

Ce compte est sur le disque : `insee_cn2024_t7301_compte_administrations_publiques_S13.xlsx`.
Il est **en quarantaine** dans `data/raw/_unsourced/` — sha256 présent, **URL de source
jamais enregistrée**, donc rien de ce qui en sortirait n'est reproductible par un tiers
(D-026). Je ne l'ouvre pas comme entrée porteuse.

« Localiser n'est pas manifester » était ma phrase pour les items R4-R8 restants ; elle
m'est opposée ici, et c'est correct. **Le backtest attend qu'un compte des APU sourcé soit
manifesté**, et cela figure sur la liste de téléchargement.

### Ce qui reste de M1

§3.2 sur le Bloc 1 (taux implicite depuis la structure de maturité) est débloqué : les trois
fichiers AFT sont manifestés. Le parse HTML ira dans un script de vérification avec kill
tests, jamais en ligne dans le moteur — règle actée à l'addendum.

## D-132 — §3.2 : le parc AFT se reconstitue, et un séparateur de milliers valait 4×10¹⁰

**Phase 8 M1 §3.2, 2026-09-14.** `scripts/verify_aft.py` — le parse par ligne, en script de
vérification avec kill tests comme l'addendum l'a tranché, jamais en ligne dans le moteur.

### Le kill test du Bloc 1 passe

Bloc 1 + Bloc 2 = total APU tient **par construction** de Bloc 2 comme résidu : cette
égalité ne teste rien. Le vrai test est que le Bloc 1 seul reproduise les totaux que l'AFT
publie elle-même. Mesuré sur les 103 titres du bulletin n° 435 :

| | reconstruit | publié | écart |
|---|---|---|---|
| moyen et long terme | 2 662,3 md€ | 2 662 | **+0,010 %** |
| court terme | 219,6 md€ | 220 | −0,163 % |
| **total négociable** | **2 881,9 md€** | **2 882** | **−0,003 %** |
| dont indexés | 312,8 md€ | 313 | −0,076 % |

Tolérance **0,5 %**, mesurée à l'implémentation et non choisie : la ligne la plus lâche est
le court terme à 0,163 %, ce qui est l'arrondi de chiffres que le bulletin imprime au md€.

### Le séparateur de milliers, qui vaut 4×10¹⁰

**Trois conventions cohabitent dans le même document** : `24 030 000` séparé par U+202F
seul ; `24  030  000` par U+202F suivi d'une espace ordinaire ; et l'espace
ordinaire **seule**, qui n'est pas un séparateur mais une **frontière de colonne**.

Confondre les deux fusionne l'encours avec le démembré qui le suit. FR0000571218 se lit
alors **44 514 880 458 968 967 100** au lieu de 44 514 880 458 — **4 × 10¹⁰ fois sa valeur**,
et cela reste un entier valide. Mon premier parse faisait exactement cela, et le total MLT
sortait à 2,2 × 10²³ euros ; un défaut moins spectaculaire aurait été plus dangereux.

La règle : **le séparateur EXIGE l'espace fine**, une espace ordinaire peut la suivre, une
espace ordinaire seule sépare des colonnes. Et la date est retirée **avant** toute lecture
de nombre, sans quoi « 24 septembre 2026 24 030 000 000 » colle l'année à l'encours.

Ce projet écrit lui-même U+202F (`reporting.THIN_SPACE`) pour la typographie française ; il
lui fallait apprendre à le relire.

### La page HTML des OAT ne porte que du nominal

`Encours détaillé des OAT` liste **59 lignes, toutes nominales** — aucune OATi, aucune
OAT€i. Les indexées pèsent **313 md€, près de 11 %** de l'encours négociable. **Un Bloc 1
bâti sur cette seule page les omettrait en silence.** Le bulletin est donc la source
complète par ligne, et les deux pages HTML sont un recoupement, pas l'entrée.

### Et mon assertion était plus grossière que le constat

Premier jet : « OATi n'apparaît pas dans la page ». Elle échouait — parce que le mot
figure dans le **menu de navigation** du site. J'ai testé le document là où le constat porte
sur les **lignes de données**. C'est l'erreur exacte de la première version de
`verify_rei.py`, qui butait sur des lignes CFE. Resserré sur les cellules de libellé.

### Deux mesures fausses avant celle-ci, toutes deux par comparaison de grandeurs distinctes

J'ai d'abord cru le parse incomplet : 103 lignes extraites contre « 65 OAT + 7 OATi +
14 OAT€i » lus dans le bulletin. Ces 86 étaient un **comptage d'occurrences du mot** dans
tout le texte — titres et prose compris — et non un comptage de titres. Le PDF porte
exactement 103 ISIN, tous capturés. Comparer un compte de lignes à un compte de mots est la
quatrième question permanente, encore.

## D-133 — §3.2 : le taux implicite du Bloc 1, et un kill test inerte attrapé par mutation

**Phase 8 M1 §3.2, 2026-09-14.** `src/impots/dette/maturite.py`,
`tests/test_dette_maturite.py` (9 tests). Les quatre kill tests de la spec passent.

### Les quatre, et pourquoi trois sont sur des portefeuilles CONSTRUITS

| kill test | résultat |
|---|---|
| roulement nul + déficit nul → taux constant | **1,00 % sur 5 ans**, taux de marché à 3 % qui ne fuit pas |
| roulement intégral immédiat → taux = taux de marché | **3,50 % en an 1**, exact |
| échéancier = encours manifesté | **2 881,9 md€**, écart 0,00e+00 |
| marché = implicite courant → charge an 1 ≈ ancre P117 | **52,78 md€ contre 58,615**, −9,9 % |

« Roulement nul » et « roulement intégral » **n'existent pas dans le parc réel** : un test
qui ne voit que les données réelles ne sait pas distinguer un roulement juste d'un
roulement cassé. D'où les portefeuilles construits.

### L'écart de −9,9 % est un écart de PÉRIMÈTRE, mesuré et non resserré

P117 est une charge **budgétaire** sur toute la dette de l'État. Ce module somme des jambes
de coupon et **omet la provision d'indexation** — simplification déclarée, et **signée** :
elle ne peut que sous-estimer. Vérification de taille : 2 % d'inflation sur les 312,8 md€
indexés font **6,3 md€**, ce qui couvre largement les 5,8 md€ d'écart.

Le test assère donc **le signe et l'ordre de grandeur**, pas seulement « dans la tolérance ».
Une tolérance dans laquelle une erreur de périmètre tient à l'aise est une erreur de
périmètre avec un certificat.

### Trois simplifications nommées

1. **Lignes indexées portées à leur coupon RÉEL sur leur encours INDEXÉ.** La jambe de
   coupon est juste ; c'est la provision d'indexation qui manque. §3.2 offrait le choix
   entre modéliser l'inflation du scénario et porter un coupon réel fixe : c'est le second.
2. **Les BTF n'ont pas de coupon** — ce sont des titres à escompte. Leur coût arrive par le
   **roulement**, et comme ils échoient tous dans l'année ils roulent intégralement en an 1
   au taux du scénario. La machinerie le fait sans cas particulier, ce qui est la raison de
   le modéliser ainsi plutôt que d'imputer un coupon synthétique.
3. **La structure d'émission BTF/OAT est tenue à l'observé**, défaut de scénario nommé.

### Le kill test qui ne pouvait pas échouer, attrapé par mutation

Trois mutations lancées : fuite du taux de marché dans le stock gelé → 3 échecs ; coupon
ancien non retiré au roulement → 3 échecs ; **lignes déjà échues jetées → 0 échec.**

Le test de report en avant était **inerte**. Il tournait sur le bulletin manifesté, dont
l'échéance la plus proche est le **5 août 2026** quand `as_of` vaut le **31 juillet 2026** :
**zéro titre déjà échu**, donc une prémisse qui ne se produit jamais et un test qui passe
contre une implémentation qui les jette.

Forme D-044, dans un fichier **dont le docstring explique lui-même** pourquoi trois des
quatre kill tests sont construits. Je l'ai écrit, puis j'ai fait l'inverse à la quatrième.
Réécrit sur un portefeuille construit portant une ligne échue en 2020 ; la mutation est
maintenant attrapée.

C'est la troisième question permanente qui a servi, et elle n'a servi que parce que la
mutation a été lancée : **les neuf tests passaient**, et rien dans leur lecture ne
distinguait le test vivant du test mort.

## D-134 — Interruption ERFS, E0 : les rails avant le premier octet

**2026-09-17.** L'interruption ERFS se déclenche. Le propriétaire détient **ERFS 2022,
version FPR, livraison lil-1696**, obtenue par sa propre convention Quetelet-Progedo/ADISP.
E0 pose les rails ; **aucun octet de donnée n'a été lu** à ce stade.

### Route et millésime

* **Route** : ADISP (Quetelet-Progedo), livraison **lil-1696**.
* **Millésime** : **2022**, version FPR (fichier de production et de recherche).
* **Référence de convention** : **NON RENSEIGNÉE — demandée au propriétaire.** Le handoff
  annonçait que le document « se trouve à côté des fichiers » ; il n'y est pas. Recherche
  faite sur toute la livraison (`convention`, `diffusion`, `contrat`, `engagement`,
  `charte`, `licence`) : aucun document de ce type. La livraison ne porte que les tables,
  la documentation méthodologique et les formulaires CERFA publics.

### Les quatre règles de conformité

1. **Rien d'ERFS-dérivé dans git** — fichiers, fixtures, goldens, données de test comprises.
2. **Aucune valeur de ligne** dans une sortie, un journal, un message d'erreur ou un
   document : schéma, dictionnaire, comptages et agrégats au-dessus d'un plancher de
   diffusion, rien d'autre.
3. **Tout est opt-in et absent de la CI.**
4. **Aucun transit par le nuage** : ni les octets ERFS ni aucune sortie dérivée de lignes ne
   quittent cette machine. Le relecteur s'est lié à la même règle ; cette session aussi, et
   c'est pourquoi rien de tout ceci n'ira dans un document distant ou un artefact.

### Plancher de diffusion : 11 ménages, PAR DÉFAUT et non par lecture

Le handoff demandait de lire le plancher dans la clause de diffusion de la convention et de
le citer. **La convention est introuvable dans la livraison**, donc le plancher retenu est
le défaut que le handoff lui-même fixe — **11 ménages** — et il est enregistré **comme un
défaut, pas comme une citation**. La distinction compte : un plancher cité engage la
convention, un plancher par défaut engage seulement notre prudence, et confondre les deux
serait exactement le genre d'ancrage relayé que ce projet refuse ailleurs.

**Même traitement pour les rapports** : la question de savoir si des agrégats non
divulgatifs peuvent figurer dans des rapports committés se tranche par la clause. Faute de
clause, **conservateur** : rien d'ERFS-dérivé dans un rapport committé jusqu'à lecture.

### Les rails, et leurs kill tests vus tomber

**Emplacement.** Livraison déplacée de `~/Downloads/lil-1696` vers `~/Dev/lil-1696`, à côté
du dépôt et hors de son arbre. Même volume, déplacement instantané, `Downloads` vidé.
Vérifié : **rien d'ERFS-microdonnées dans l'arbre du dépôt**, ni dans l'index, ni dans
l'historique. Quatre correspondances de nom examinées une à une plutôt qu'effacées par
réflexe : deux documents de plan (noms de variables, aucune valeur) et deux publications
INSEE agrégées, non suivies et déjà ignorées.

**Configuration locale** (`src/impots/erfs/config.py`) : variable d'environnement
`IMPOTS_ERFS_DIR`, sinon `~/.impots.local`. **Aucun défaut, pas même l'emplacement réglé** —
un chemin par défaut marcherait sur une machine et lirait zéro ligne en silence sur toutes
les autres, la forme que ce projet a rencontrée à l'Ésane sans `max_row` et à la colonne de
déciles en chaînes.

**Garde étendu** (`scripts/check_no_data_committed.py`), deux refus, chacun **prouvé sur un
offenseur factice** :

* un fichier nommé `fpr_menage_sample.csv` mis en index → refusé, code 1 ;
* le chemin absolu de la livraison écrit en dur dans `src/` → refusé, code 1 ;
* un document qui **nomme** la livraison → **accepté**, parce que la règle porte sur un
  littéral de chemin dans du CODE et non sur le droit d'un document à dire où vivent les
  données. Le fichier de revue le dit déjà, et c'est légitime.

Le garde doit **nommer** les motifs qu'il refuse, donc il se contient lui-même : il
s'exclut **par chemin exact**, pas par règle, pour que l'exemption ne puisse pas s'élargir.

### Deux erreurs de ma part pendant la pose des rails

**J'ai détruit des fixtures de test.** Pour nettoyer un offenseur factice j'ai fait
`rm -rf tests/fixtures`, or ce répertoire existait : `README.md`, `firm_cells.json` et
`eec_sample.parquet` — les 51 Ko sous Licence Ouverte **qui font tourner la CI**. Restaurés
par `git checkout`, 77 tests repassent. La règle que je m'applique : **regarder avant de
supprimer**, y compris dans un nettoyage qu'on croit porter sur ce qu'on vient de créer.

**Et j'ai lu un code de retour à travers un tube**, exactement le défaut D-113 : mes trois
sondes affichaient « code retour 0 » alors que le garde refusait. Relancé sans tube : 1, 1,
0 — les bons. Le défaut que ce projet a trouvé dans son propre Makefile, reproduit dans mon
shell deux semaines plus tard.

## D-135 — Interruption ERFS, E1 : l'inventaire formel, et le piège de casse

**2026-09-17.** `scripts/verify_erfs.py`. **Métadonnées seules** : empreintes, comptages,
noms de colonnes, accord entre deux encodages. **Aucune valeur de ligne n'apparaît nulle
part**, et rien de ce qui suit n'a quitté cette machine.

### L'inventaire

| fichier | octets | sha256 (16) |
|---|---|---|
| `fpr_menage_2022.csv` | 10 974 882 | `0bced584a8a4649b…` |
| `fpr_indiv_2022.csv` | 79 214 326 | `887c5ba0c3701945…` |
| `fpr_menage_2022.dta` | 30 156 170 | `f1541057bff7d193…` |
| `fpr_indiv_2022.dta` | 332 462 106 | `1d1fda6585443eb0…` |
| `Format_lil-1696_stata.txt` | 91 884 | `85ffdc67ed0d0af2…` |

**Les quatre tailles attendues par l'addendum sont confirmées au octet près.**

**Comptages contre le publié.** Le document de méthodologie livré avec les données écrit
« 92 000 individus pour environ 44 000 ménages ». Mesuré : **91 921 individus** (−0,09 %) et
**43 684 ménages** (−0,72 %). Tolérance 2 %, large **exprès** : épingler à quatre chiffres
une donnée que la source qualifie d'« environ » serait inventer une précision qu'elle
récuse. Schéma : **87 colonnes** au ménage, **467** à l'individu, séparateur `;`, latin-1.

### Le parse CSV, confirmé par l'autorité Stata

C'est la raison de garder la paire `.dta`. Ni pandas ni pyreadstat ne sont installés, et
ajouter une dépendance compilée pour lire quatre nombres serait un mauvais marché : le
format 111 place `nvar` aux octets 4-5, `nobs` aux 6-9, puis les noms en champs de 33 octets
terminés par NUL. **En-tête décodé à la main, avec `struct` seul.**

Accord : 87 × 43 684 et 467 × 91 921 des deux côtés, **noms identiques et dans le même
ordre**.

### Le piège de casse, qui ne lève jamais

**Stata minusculise les noms de variables ; le CSV les conserve.** Les divergences sont
**toutes** de casse — et elles sont massives : **37 des 87** colonnes ménage et **443 des
467** colonnes individu portent des majuscules côté CSV.

Un code qui croiserait des noms issus du `.dta` avec les colonnes du CSV **sélectionnerait
le vide sans rien lever** — 443 colonnes sur 467 introuvables, une jointure qui rend zéro
ligne, une moyenne sur un tableau vide. C'est exactement la famille de défauts que ce projet
collectionne : l'Ésane sans `max_row`, la colonne de déciles en chaînes, le séparateur fin de
l'AFT. Épinglé par une assertion qui **exige** des divergences et exige qu'elles soient
toutes de casse.

**Trois kill tests lancés, trois captures** : un comptage attendu faux → échec ; la tolérance
resserrée à 0,1 % → échec ; le décalage de l'en-tête Stata d'un octet → 4 échecs.

### Un écart avec l'addendum, énoncé plutôt que suivi en silence

L'addendum autorise : « The documentation PDFs are public and may be manifested into
`data/raw/` normally. » **Je ne les y ai pas copiés.** `data/raw/` est **dans l'arbre du
dépôt**, et E0 pose que tout ce qui est ERFS sous l'arbre git est une infraction que le garde
refuse — les fichiers s'appellent `Dictionnaire ERFS 2022_FPR.pdf`,
`EEC2022_Dictionnaire_des_codes_FPR.pdf`. Les deux règles se contredisent sur ce point précis,
et la prudence dit de ne pas faire entrer d'ERFS-nommé sous l'arbre pour un gain nul.

**Les empreintes sont donc prises SUR PLACE et enregistrées ici** — c'est tout ce que
« manifester » apporte :

`Dictionnaire ERFS 2022_FPR.pdf` 488 560 o `0a0ef10af680ea8a…` · `Méthodologie_ERFS_2022.pdf`
275 720 o `d06fa2395ae7d707…` · `Liste_Variables_FPR_2022.xls` 25 926 o `9334620bee8077e5…` ·
`EEC2022_Dictionnaire_des_codes_FPR.pdf` 5 092 795 o `27666eb99d43c791…`.

**À trancher par le relecteur** : copier la documentation publique sous `data/raw/` malgré
son nom, ou la laisser dans la livraison avec ses empreintes au journal. J'ai pris la
seconde ; la première est défendable et ce n'est pas à moi de renverser E0 pour elle.

## D-136 — E2 préenregistré, et un .gitignore qui a avalé le code qu'il protégeait

**2026-09-17.** Le tableau de validation E2 est préenregistré **avant tout chiffre ERFS**.
Et en le committant j'ai découvert que **trois commits antérieurs de cette interruption
étaient incomplets**, en silence.

### Le défaut : un garde assez large pour avaler sa propre implémentation

Le bloc `.gitignore` posé en E0 contenait `*erfs*` et `*ERFS*`. Ces motifs n'ignorent pas
seulement des données : ils ignorent **`src/impots/erfs/`** — c'est-à-dire le code qui met en
œuvre la protection. Conséquences, toutes muettes :

* `e8aa748` (« E0 : les rails ») **ne contenait pas `src/impots/erfs/config.py`**. J'ai
  rapporté une configuration locale construite ; seuls le garde, le `.gitignore` et les
  documents étaient entrés.
* `20aeecf` (« E1 : l'inventaire ») **ne contenait pas `scripts/verify_erfs.py`**. J'ai
  rapporté un script de vérification avec kill tests ; il n'était pas dans git.
* Le commit du préenregistrement E2 **n'a rien committé du tout** — « nothing to commit,
  working tree clean » — alors que quatre fichiers venaient d'être écrits.

**`git add -A` a rapporté un succès en n'ajoutant rien.** C'est la forme que ce projet
collectionne : une opération qui réussit sans rien faire, et un rapport qui la croit. Trois
de mes comptes rendus ont donc surestimé ce qui avait atterri, et je le dis ici parce qu'un
journal qui tait ça ne vaut rien.

### La correction, et pourquoi elle ne desserre rien

Les deux rails visent désormais des **extensions de données**, pas tout chemin contenant
« erfs » :

* `.gitignore` : `*erfs*.csv`, `*erfs*.dta`, `*erfs*.parquet`, `fpr_*.csv`, … et
  `lil-1696*`. Une source `.py` n'est plus ignorée.
* le garde : un fichier ERFS-nommé reste refusé, **sauf** une source `.py` sous `src/`,
  `tests/` ou `scripts/` — **du code Python ne peut pas ÊTRE une microdonnée**.

**Re-prouvé après desserrage**, ce qui est la moitié qui compte : `tests/fpr_menage_sample.csv`
refusé, `src/impots/erfs_extract.parquet` refusé, `data/interim/erfs_join.dta` refusé, et un
chemin absolu écrit en dur **à l'intérieur de `src/impots/erfs/`** refusé. L'exemption `.py`
n'ouvre donc aucun trou.

### Le préenregistrement lui-même

Cinq axes, trois rendent un verdict. **A1** parts de revenu par décile, ±10 % — les déciles 5
à 9 sont déjà mesurés à +3,6/+9,2 % contre Filosofi, comparateur différent et non dépensé,
donc 10 % admet le connu et refuse le pire quand 20 % n'aurait rien pu refuser. **A2**
composition × quartile de revenu, ±15 % — les deux marges ont été rakées SÉPARÉMENT, leur
joint n'est contraint par rien, et c'est l'axe où une calibration par marges peut être exacte
et fausse à la fois. **A3** masse d'éligibilité aux prestations, ±20 % — la réconciliation
compare une dépense à travers un pont de non-recours ; l'effectif éligible est une autre
grandeur.

**Deux axes sans verdict, déclarés d'avance.** Les queues : en bas des revenus quasi nuls
font exploser tout résidu relatif, en haut **les deux sources sous-comptent** — la nôtre de
64,3 % avant L1, et l'ERFS la sienne parce qu'une enquête ne voit pas le sommet. Comparer
deux sous-comptages ne mesure ni l'un ni l'autre. Et le joint capital, qui **échoue par
construction** : la population porte identiquement zéro revenu du capital, donc −100 % est
une absence et non une mesure. Ce que cet axe doit rendre est la grandeur que le gate F1b
n'avait pas : **quelle part des ménages ERFS porte un revenu du capital**.

**Le refus de source dépensée de L1 ne s'applique pas ici** : la population n'a jamais été
ajustée sur l'ERFS, sur aucun axe. Les verdicts contre l'ERFS sont donc légitimes, et c'est
toute la valeur de cette interruption.

## D-137 — E2 : le tableau de validation ERFS, et le joint que le raking n'avait jamais contraint

**2026-09-18.** Mesuré **après** le commit de préenregistrement `090cb6d`, jamais avant.
Moteur **au millésime 2022** contre **ERFS 2022**, tables ménage et individu, **agrégats
pondérés seulement**. Rien n'a quitté cette machine.

**Divulgation, vérifiée et non supposée** : la plus petite case publiée ci-dessous compte
**163 ménages non pondérés**, quinze fois le plancher de 11. Aucune valeur de ligne
n'apparaît. La ligne prudente de D-134 portait sur un fichier de rapport committé en
l'absence de clause ; la règle 2 du handoff **autorise explicitement** « aggregates above a
disclosure floor », et c'est exactement ce qui suit.

### A1 — parts du revenu par décile : PASSE sur les huit déciles à verdict

Pondéré **personne**, des deux côtés. Ce point a failli être manqué : ma première passe ERFS
utilisait `wprm`, le poids **ménage**, alors que la statistique publiée — et le module
`aggregate` de ce projet, qui le dit dans son propre commentaire — pondère par **personne**.
L'ERFS porte `wpri` pour cela. Comparer les deux conventions aurait reproduit l'erreur
d'estimateur que la réconciliation avait déjà corrigée une fois.

| décile | ERFS | nous | écart |
|---|---|---|---|
| D2 | 5,25 % | 4,97 % | −5,5 % |
| D3 | 6,36 % | 6,26 % | −1,6 % |
| D4 | 7,34 % | 7,42 % | +1,1 % |
| D5 | 8,21 % | 8,52 % | **+3,7 %** |
| D6 | 9,16 % | 9,63 % | **+5,1 %** |
| D7 | 10,27 % | 10,83 % | **+5,5 %** |
| D8 | 11,67 % | 12,34 % | **+5,7 %** |
| D9 | 13,88 % | 14,53 % | **+4,7 %** |

Les huit tiennent la bande de ±10 %. **Mais le motif est systématique** : D5 à D9 sont hauts
de +3,7 à +5,7 %. C'est **la même distorsion**, dans le même sens et du même ordre, que celle
mesurée au gate L1 contre DGFiP n° 41 (+3,6 à +9,2 % sur ces déciles). Deux comparateurs
indépendants, dont un jamais dépensé, disent la même chose : la distribution est **tassée
vers le milieu supérieur**.

D1 (−9,7 %) et D10 (−8,3 %) sont **sans verdict par préenregistrement**, et le restent.

### A2 — composition × quartile : ÉCHEC, dix cases hors bande, et c'est le résultat du jour

| quartile | composition | ERFS | nous | écart |
|---|---|---|---|---|
| Q2 | Monoparentale | 10,7 % | 17,8 % | **+66 %** |
| Q3 | Monoparentale | 6,7 % | 12,1 % | **+82 %** |
| Q4 | Monoparentale | 4,2 % | 5,7 % | +33 % |
| Q3 | Personne seule | 16,2 % | 20,6 % | +27 % |
| Q4 | Personne seule | 12,4 % | 18,8 % | **+51 %** |
| Q1–Q4 | **Autre** | 2,2 à 5,0 % | **0,0 %** | **−100 %** |

Trois constats, et aucun n'était visible sur les marges :

1. **Les ménages « autres » n'existent pas chez nous.** Zéro, dans les quatre quartiles ;
   l'ERFS en compte 2,2 à 5,0 %. Notre France synthétique ne porte **aucun ménage à trois
   adultes ou plus** — ni cohabitation, ni multigénérationnel. Ce n'est pas un écart de
   calage, c'est une catégorie absente.
2. **Nos familles monoparentales sont beaucoup trop riches** : +66 % au Q2, +82 % au Q3.
   Elles devraient être concentrées en bas ; elles sont étalées vers le haut.
3. **Nos personnes seules le sont aussi**, et de plus en plus haut : +13 % au Q1, +51 % au Q4.

**C'est exactement ce que le préenregistrement annonçait comme l'axe le plus informatif** :
le raking a atteint les marges type-de-ménage ET personne **séparément**, et leur **joint**
n'était contraint par rien. Une population peut toucher ses deux marges et se tromper
lourdement sur leur croisement — ici elle le fait, et aucune ligne de réconciliation
existante ne pouvait le voir.

### A4 — le capital : échec par construction, et la grandeur que F1b n'avait pas

La population synthétique porte **zéro** revenu du capital ; le résidu est −100 % et n'est
pas une mesure. Ce que l'axe **rend**, en revanche, est ce que le gate F1b cherchait :

* **79,0 %** des ménages ERFS portent un revenu du capital — dont 71,4 % un revenu financier
  (prélèvement libératoire et imputés), 33,9 % des valeurs mobilières, 13,8 % du foncier ;
* masse : **107,3 md€**, soit **8,63 %** du revenu disponible ;
* **62,2 %** de cette masse est détenue par le dernier décile de niveau de vie.

Un modèle qui ignore le capital ignore donc **8,6 % du revenu disponible**, concentré aux
deux tiers dans le dernier décile — c'est-à-dire précisément là où le gate L1 venait déjà de
recaler la queue.

### Ce que E2 ne fait pas

**A3 (masse d'éligibilité aux prestations) n'est pas mesurée** dans cette passe. Et il faut
dire pourquoi plutôt que la laisser tomber : c'est le seul axe préenregistré qui ne soit
**pas invariant au niveau**. Nos revenus sont calibrés sur 2024, l'ERFS observe 2022, et les
seuils d'éligibilité sont nominaux : un écart de niveau de ~8 % entre les deux millésimes
déplacerait mécaniquement l'effectif éligible sans qu'aucune erreur de modèle soit en cause.
A1, A2 et A4 sont des parts et des joints, donc insensibles au niveau ; A3 ne l'est pas.
Le mesurer demande soit de déflater, soit de l'assumer — et ce choix se préenregistre, il ne
s'improvise pas après avoir vu le chiffre.

**E3 reste « rien ».** Aucun recalage. Le tableau part au relecteur ; les dépenses se
décident ensuite, une par une, au registre.

## D-138 — A3 : la FORME des prestations est fausse, et dans un sens qui se lit

**2026-09-18.** Mesuré après le commit de méthode `cde6383`, jamais avant.

| quartile de niveau de vie | ERFS | nous | écart | ±20 % |
|---|---|---|---|---|
| Q1 | 57,4 % | **69,3 %** | +21 % | HORS |
| Q2 | 23,9 % | 17,8 % | −25 % | HORS |
| Q3 | 12,2 % | 9,4 % | −23 % | HORS |
| Q4 | 6,5 % | **3,5 %** | −46 % | HORS |

**Les quatre quartiles sont hors bande, et le motif est monotone** : notre masse de
prestations est **trop concentrée en bas**. L'ERFS en place 42,6 % au-dessus du premier
quartile ; nous, 30,7 %. Plus on monte, plus l'écart se creuse — jusqu'à moitié moins que
l'observé au dernier quartile.

### Ce que ce constat ajoute, et ce qu'il ne prouve pas

**Il ajoute un défaut de CIBLAGE, invisible sur les lignes existantes.** La réconciliation
mesure des masses de dépense à travers des ponts de non-recours ; elle ne peut pas voir *où*
la prestation atterrit dans la distribution. A3 le voit, et c'est le pire des deux cas que le
préenregistrement envisageait : « si la forme est fausse, [le défaut] est de ciblage, ce qui
est plus grave ».

**Il ne prouve pas** que tout l'écart est du modèle, et deux réserves doivent voyager avec :

1. **Les paniers ne sont pas identiques.** Nous sommons `ppa + rsa + aide_logement + af` ;
   l'ERFS somme `PPA + prest_precarite_rsa + prest_logement + prest_fam_petite_enfance +
   prest_fam_autres`. Les prestations familiales montent plus haut dans la distribution que
   les minima sociaux, donc une part de l'écart des quartiles hauts est un écart de
   périmètre et non de ciblage. Nommé plutôt que corrigé : corriger demanderait d'apparier
   dispositif à dispositif, ce qui se préenregistre.
2. **Le non-recours n'est neutre que s'il est uniforme.** Le préenregistrement l'a dit :
   « un non-recours uniforme sur la distribution laisse la forme intacte ». Il ne l'est
   probablement pas — le non-recours du RSA est plus fort en bas — mais cela jouerait dans
   le sens **inverse** de l'écart mesuré : un non-recours concentré en bas rendrait la forme
   ERFS *moins* basse, donc l'écart réel serait **plus grand** que celui affiché, pas plus
   petit.

### Le lien avec A2, qui n'est probablement pas une coïncidence

A2 a montré que nos familles monoparentales sont **trop riches** (+66 % au Q2, +82 % au Q3)
et que les ménages « autres » sont **absents**. Ce sont précisément les ménages qui portent
des prestations. Si les monoparentales sont mal placées dans la distribution, la forme de la
masse de prestations l'est aussi — **le défaut de joint de A2 et le défaut de ciblage de A3
peuvent être la même erreur vue deux fois**, et c'est une hypothèse à tester, pas un
résultat.

### État du tableau E2

| axe | verdict |
|---|---|
| A1 parts de revenu par décile (D2-D9) | **PASSE**, motif systématique +3,7 à +5,7 % |
| A2 composition × revenu | **ÉCHEC**, 10 cases, dont une catégorie absente |
| A3 forme des prestations | **ÉCHEC**, 4 quartiles sur 4 |
| A4 capital | échec par construction ; rend 79,0 % des ménages, 8,63 % du revenu |
| queues D1/D10 | sans verdict, par préenregistrement |

**E3 reste « rien ».** Aucun recalage n'est tiré de ceci ; le tableau part au relecteur.

## D-139 — La documentation publique rejoint `data/raw/`, sur décision du propriétaire

**2026-09-18.** D-135 avait relevé une contradiction entre l'addendum (« the documentation
PDFs are public and may be manifested into `data/raw/` normally ») et la règle E0 (tout ERFS
sous l'arbre git est refusé), et avait tranché **conservateur** en laissant les fichiers dans
la livraison. **Le propriétaire tranche l'inverse : les mettre dans `data/raw/` et tout
ignorer.** C'est sa décision, elle lève la contradiction, et elle est appliquée.

**Dix fichiers copiés, dix empreintes confrontées à l'original** — une copie n'est pas fidèle
parce qu'elle vient de `cp`, elle l'est parce qu'on l'a vérifiée : dictionnaire FPR,
méthodologie, liste des variables, dictionnaire des codes EEC, questionnaire EEC, fichier de
formats Stata, et les quatre CERFA 2042. Manifeste : 144 entrées.

**Ce qui n'y est pas et n'y sera jamais** : les deux tables. `fpr_menage_2022.csv` et
`fpr_indiv_2022.csv` restent dans la livraison, hors de l'arbre.

**Un renommage, parce que l'extension mentait.** `Liste_Variables_FPR_2022.xls` est un
classeur **OOXML** — magie `PK`, `[Content_Types].xml`. openpyxl le refuse sur son extension,
xlrd sur son contenu ; les deux erreurs se contredisent et aucune ne dit la vérité. Copié en
`.xlsx`, qui est ce qu'il est. Quatrième en-tête ou extension menteur de ce projet, après le
« en milliers » de Stat 39, le « (montants en milliers d'euros) » des fichiers de niches, et
la colonne d'effectifs du Tableau 1.

**Les rails tiennent après la décision, et c'est la moitié qui compte.** Vérifié : aucune
documentation n'est suivie par git ; l'arbre est propre pour le garde ; et une vraie donnée
glissée sous `data/raw/` — `fpr_menage_2022.csv` copié en `erfs_probe.csv` et forcé dans
l'index — **est toujours refusée, code 1**. Élargir l'emplacement autorisé n'a pas élargi ce
qui peut entrer dans git.

## D-140 — La convention est retrouvée, et elle ne fixe AUCUN seuil chiffré

**2026-09-18.** D-134 enregistrait un plancher de divulgation de 11 ménages « PAR DÉFAUT et
non par lecture », faute de convention. La convention a été retrouvée et lue. Elle change la
réponse, mais pas dans le sens attendu.

### Ce qui est maintenant connu

**Référence** : Progedo-ADISP, **demande n° 38715** — *engagement de confidentialité auprès
du Comité du Secret Statistique*, signé le **2025-09-03** à Boulogne-Billancourt. Le
document n'était pas dans la livraison : il est dans `~/Downloads`, en **scan** (5 caractères
de texte extractible sur six pages), donc invisible à toute recherche par contenu. Retrouvé
par nom, rendu en image, et lu.

### Elle ne fixe aucun seuil, et c'est le constat

L'engagement impose une **obligation de RÉSULTAT**, pas un seuil :

> « de manière générale, toute procédure nécessaire dans le but d'empêcher l'identification
> directe ou indirecte d'unités statistiques individuelles »

et renvoie les nombres à « les règles générales du secret statistique » et aux « règles de
secret éventuellement spécifiques à certaines sources (**disponibles dans leur documentation
ou auprès des producteurs**) ». J'ai suivi ce renvoi : la méthodologie ERFS, le dictionnaire
FPR et le dictionnaire des codes EEC **n'énoncent aucune règle de case** — ils décrivent des
tables de diffusion, pas un seuil.

**Il n'y a donc rien à citer, et le 11 du handoff n'a jamais été dans la convention.**

### Ce qui remplace le défaut : un mécanisme, pas un meilleur nombre

`src/impots/erfs/disclosure.py`. Trois choix, chacun tiré de l'obligation de résultat :

* **le plancher est un argument OBLIGATOIRE, sans défaut** — puisque aucune source ne le
  fixe, tout nombre est le choix de quelqu'un, et le forcer à être passé le maintient un
  choix plutôt qu'une constante que personne ne réexamine ;
* **le comptage est NON PONDÉRÉ** — une pondération transforme trois ménages en milliers de
  personnes et ne divulgue pas moins pour autant ;
* **une case fine refuse le TABLEAU ENTIER**, pas seulement elle-même : retirer une case d'un
  tableau dont les marges sont publiées la laisse retrouvable par soustraction. Une
  suppression que l'arithmétique défait n'est pas une suppression.

**Et l'argument qui rend le nombre manquant sans importance** : la case la plus fine publiée
par E2 porte **163 ménages non pondérés**. Un plancher de 11, 50 ou 100 ne change **rien** à
ce qui a été publié. Le plancher suggéré passe donc à **50**, très au-dessus du défaut qu'il
remplace, et il ne coûte rien parce qu'il ne mordra que sur ce que personne ne voulait
publier.

### Trois obligations que personne n'avait relevées, parce que le document manquait

1. **Stockage chiffré pendant le travail** — « stocker les données sur un serveur sécurisé ou
   dans un espace crypté ». Vérifié : **FileVault est actif**. L'obligation est satisfaite au
   niveau du volume. Le répertoire est en outre passé de `drwxr-xr-x` à `drwx------`.
2. **Destruction des fichiers à l'issue du travail de recherche.** C'est une obligation
   datée, pas une bonne pratique, et elle n'était nulle part au dossier.
3. **Information du diffuseur** : toute communication ou publication doit lui être signalée
   avec ses références, ainsi qu'au Comité du secret statistique — et, **pour les travaux sur
   données d'origine fiscale**, au bureau des études statistiques en matière fiscale de la
   DGFiP. Les sources doivent être citées selon le modèle fourni.

Les manquements exposent aux articles **226-13 et 226-14** du code pénal (un an, 15 000 €) et
226-16 à 226-24. Cela ne change pas ce que fait le projet — rien ne publie — mais cela change
ce qui devra être fait **le jour où quelque chose publiera**, et c'est désormais au dossier
plutôt que dans un tiroir.

## D-141 — Les deux gates du ré-examen : la clé ERFS a été essayée, et elle n'ouvre pas la CDHR

**Contexte.** L'interruption ERFS prévoyait après E2 « des gates de ré-examen, pas des
promesses » pour la CDHR et pour la couche population du PFU. E3 reste « rien » : ces deux
gates DÉCIDENT, ils ne construisent pas et ne recalibrent rien.

**Le déclencheur est dans le code.** `plf_coverage.py` donnait comme `unlock` de l'article 2
« real income microdata (ERFS) ». La condition est remplie. Le ré-examen n'était donc pas
une faveur mais une obligation que le dépôt s'était imposée — et le motif du refus F1b
(« imputation uniforme dans la cellule, donc tous les foyers du même côté du seuil ») visait
un défaut de l'IMPUTATION. L'ERFS porte de la dispersion réelle : **ce motif est mort.**

**Méthode : critère préenregistré par commit `04f96ce`, avant tout rendement.** Bande
[0,75 ; 3,0] md€ autour des 1,50 md€ publiés — un facteur 2, argumenté depuis trois erreurs
de proxy nommées et signées (IRPP simulé par l'INSEE et non liquidé par la DGFiP ; `revdecm`
du ménage et non RFR retraité du foyer ; millésime 2022 antérieur à une CDHR à seuils
nominaux). Les deux issues écrites d'avance.

**Résultat — trois jambes, deux cèdent.**

| jambe | mesure | porte le refus ? |
|---|---|---|
| rendement | hors bande de **moins de deux pour cent** (chiffre non publiable) | **non** |
| plancher de divulgation | contributeurs sous le plancher de 50 | **non** |
| bande sans verdict d'E2 | la CDHR vit tout entière dans le dernier centile | **oui, seule** |

*Jambe 1.* La tolérance n'est pas élargie — mais un dépassement d'un pour cent ne soutient
rien, et l'autopsie post hoc explique tout l'écart : **la livraison ne porte aucune colonne
d'impôt au prélèvement forfaitaire.** `rev_financier_prelev_lib_imputes` est le REVENU
soumis au prélèvement, jamais le prélèvement. La jambe fiscale était amputée du PFU —
2,29 md€ sur les 70 ménages concernés, l'impôt même que la CDHR compte au numérateur.
Rétabli à 12,8 %, le rendement rentre dans la bande. Sans valeur probante pour
le verdict, mais probant pour ceci : **le rendement ne fournit aucun motif de refus.**

*Jambe 2.* Le plancher de 50 est le NÔTRE (D-140 : la convention n'en fixe aucun) ; au
défaut de 11 du cahier des charges, ces 36 passeraient. Un refus qui bascule avec un
paramètre choisi après coup est une préférence, pas un refus.

*Et le préenregistrement s'est trompé,* ce qui est consigné plutôt que corrigé en silence.
Le §6 annonçait « le refus ne pourra pas s'appuyer sur la rareté », sur la foi de 109
ménages sous 20 %. Ce 109 appliquait 250 k€ à tout le monde ; le seuil légal est 500 k€ pour
un couple, et 22 472 des 42 831 ménages en sont un. La population réelle est de 70 au-dessus
du seuil, et les contributeurs tombent sous le plancher. La rareté mord exactement là où le préenregistrement la disait
absente.

*Jambe 3, la seule qui tienne.* E2 classe le dernier centile en `no_verdict` parce que
l'ERFS sous-compte sa propre queue — une enquête ne voit pas le sommet. Trancher sur la
CDHR, c'est rendre un verdict là où le dépôt s'est engagé, par commit et avant tout chiffre
ERFS, à n'en rendre aucun. C'est la seule jambe qui ne dépende d'aucun choix postérieur aux
données.

**Décision 1 — refus de la CDHR reconduit, sur la jambe 3 seule, et la serrure est
renommée.** La CDHR n'est plus « mal posée » : avec de la dispersion réelle elle se pose
très bien. Elle est **inobservable dans cette source**, affirmation bien plus étroite. La
clé n'est donc pas « des microdonnées » — essayées, sans succès — mais **une source qui VOIT
LE SOMMET** : échantillon lourd DGFiP, POTE. Le défaut est dans le PLAN DE SONDAGE, pas dans
la granularité, et aucune enquête auprès des ménages ne l'ouvrira. `plf_coverage.py` est
corrigé : laisser « ERFS » en serrure enverrait le prochain lecteur chercher une clé déjà
connue pour ne pas tourner.

**Le test qui gardait cette clause ne pouvait pas la prendre en défaut.** Il n'affirmait que
la présence de « microdata » et « D-096 » — vraies pendant tout le temps où la clause était
fausse. C'est la forme D-044. Remplacé par un test qui nomme l'implémentation qui le fait
échouer, et **vu échouer** sur la clause rétablie.

**Décision 2 — la couche PFU s'ouvre, mais PAS par l'ERFS.** Deux raisons mesurées.
**(a) 44,7 % de l'assiette capital de l'ERFS est IMPUTÉE** : 39,63 md€ déclarés contre
32,00 md€ de revenus financiers imputés par l'INSEE. Bâtir dessus importerait un modèle
d'imputation **sous une étiquette de microdonnée** — le défaut du §3, relocalisé et rendu
invisible. **(b) Le prix serait le tableau lui-même** : une couche PFU bâtie sur l'ERFS en
ferait une cible de calibration, et A1/A2/A3 cesseraient d'être des verdicts le jour même,
comme les fractiles de la n° 41 dépensés par le recalage L1. La route publiée du §2 fournit
déjà l'assiette (71,6 md€ ERFS 2022 contre ~80,6 md€ dérivés n° 41 2024 : deux routes
indépendantes, même ordre). **L'ERFS reste la validation**, rôle que l'axe A4 lui assigne
déjà mot pour mot.

**Un manquement, relevé sur nous-mêmes.** La première rédaction portait les chiffres
de la reconstruction CDHR, tous dérivés d'une cellule de moins de 50 ménages — donc sous
le plancher que le paragraphe voisin invoquait. Écrire « la garde refuse ce tableau »
au-dessus du tableau refusé est la forme de défaut que ce dépôt traque ailleurs. Corrigé
en bandes (§9 du gate). Cela ne renforce pas la jambe 2 — au plancher de 11 ces effectifs
passeraient — mais cela lie : **le gate CDHR ne peut pas publier sa propre preuve** sous
nos règles. L'historique git conserve les figures retirées (`0da23f4`) ; le dépôt ne
publie rien, le fait est consigné plutôt que tu.

**Ce que ces gates ne décident pas.** Construire ou non. E3 reste « rien ».
