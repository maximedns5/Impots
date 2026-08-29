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
- Is a live academic affiliation available? Decides whether L1 is synthesised
  from open data or built on real ERFS/BDF extracts via ADISP.
- Households first, or firms first? Firms are the real gap; households are the
  easier start.
- Contribute the firm package to the OpenFisca org, or fork?
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
