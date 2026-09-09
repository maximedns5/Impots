# Phase 6 — The Consolidation March: everything remaining, staged

**Project**: Impôts · **Phase**: 6 (the last planned building phase)
**Audience**: implementing sessions, possibly several in sequence — each
stage is a natural session boundary with its own definition of done and a
report back to the owner. Conventions unchanged; every standing rule in the
review file binds; **[ANCHORED]** marks facts pinned by the reviewer on
2026-09-09. `docs/STATE_AND_NEXT.md` (2026-09-09) is the map this spec
executes.

**Two interrupts stand over the whole phase**: the **PLF 2027 calendar
trigger** — the day the text publishes (expected early October), whatever
stage is running pauses and S4 executes; and the dormant **ERFS interrupt**,
unchanged, should access ever materialise.

**Owner-gated, never this phase's to touch**: the CAF cross-check, the
upstream dossier, everything publication- or deployment-shaped, and any
re-opening of closed items (Zucman; ERFS posture).

---

## S1 — F3 M4: the band, year by year

Per-year uncertainty where **the uprating hypothesis and the behavioural
response are two distinct uncertainties that compose** — and stay
decomposed in every output, per the project's uncertainty grammar
(parameter / scenario / cell-bound / composition each kept visible; this
adds *uprating* as a named class, measured by the aged/frozen pair from
M2's ruling). The macro fan's horizon refusal binds **per year, not per
reform**: a 2024–2030 trajectory shows the fan only for the years inside
the declared horizon, and says why it stops. Applicability grading runs per
year too — a reform in-support in 2026 can be out-of-support by 2030 as
uprated incomes drift from the estimation range; measure, don't assume.
Kill tests for every new guard; the three questions at birth.

**Done when**: a trajectory output carries, per year — mechanical figure,
basis (legislated/reconducted), band with uprating and behavioural
contributions separable, fan or its refusal — and the worked example
(the 2028 barème freeze) reproduces with all decorations in place.

## S2 — F3 M5: trajectory outputs, and the phase closes

UI: the trajectory view (load the repo's dataviz conventions before any
chart); the **aged/frozen pair** shown per M2's ruling; the banner sentence
verbatim: *"ce qui est chiffré : ce droit, sur la France d'aujourd'hui,
avec l'argent de demain."* Fiche generator extended to trajectories (one
fiche per reform, per-year table inside, bases and uncertainty classes
named). Reconciliation untouched — future years stay "not comparable" by
the vintage refusal; if the **projection-vs-projection gate** (RESF annex,
offered in the M2 verdict) has not been run, run it here: extractable at a
pinnable perimeter → the new line class exists, never pass/fail; otherwise
it is not created. Chiffrage re-sweep: multi-year articles (CVAE
trajectory, CEBGE expiry) now expressible as trajectory cases.

**Done when**: F3's definition of done in PHASE-F3's spec holds end to end,
all suites green, the full-pass log line fresh, D-entries current.

## S3 — F1b: the capital-income gate (before the PLF week, hard order)

As authorised in OPUS_HANDOFF_NO_ERFS §C, unchanged: an M0-style gate on
DGFiP's published RCM-by-RFR-tranche tables (the niche-imputation table
family) and IPP Note 92 for the extreme top. Question: can the existing
opt-in, spent-registered imputation machinery honestly unlock PFU-level
pricing? Expectations held honestly: PFU tranche-level plausibly yes;
**the CDHR probably stays refused** (bites inside the top percentile;
tranche-level too coarse) — and the refusal, if confirmed, is restated
with the gate's evidence. The gate decides; nothing builds past it
unbidden. This runs before S4 because the CDHR will be in the PLF text and
the triage's article-2 entry must cite the gate's verdict, not a guess.

## S4 — PLF 2027 week (calendar-triggered; interrupts any stage)

Execute `docs/`' publication-week runbook exactly: manifest the text the
day it publishes; re-derive the triage on the real articles (the 2026-based
classifications are priors, not answers); wire the pre-identified small
knobs (phantom check, read-back, kill tests — no exceptions under time
pressure; **time pressure is when the rules earn their keep**); register
the chiffrages with tolerances declared at registration, the git-history
integrity mechanism as the record; price multi-year articles as
trajectories with bases labelled. Report to the owner: both coverage
headlines (articles and yield), the pre-registration list, and what was
refused with reasons. Nothing publishes.

## S5 — F6: the EMTR/ATR explorer (small, one session)

Curves across the income range per household type, baseline vs reform;
bracket-crossings and taper-stacking visible; the 63.5 %-peak finding made
explorable. Existing machinery (engine + finite differences + the cached
EMTR artifacts); dataviz conventions; presentation-regression tests in the
UI suite. No new model claims — this is measurement made legible.

## S6 — F5: taxe foncière from the REI (a mini-phase with its own gates)

The last big open-data tax with no open model. **[ANCHORED]** sources: the
REI on data.gouv.fr ("Impôts locaux : fichier de recensement des éléments
d'imposition à la fiscalité directe locale"), the same dataset queryable on
data.economie.gouv.fr (Opendatasoft API — likely the better ingest route),
and the OFGL mirror carrying 2024–2025 vintages. Milestones:

* **M0 — the gate, and the file's reputation precedes it**: the REI's
  columns are a documented swamp. verify_rei.py asserts row counts vs
  published commune counts, per-commune identities (bases × rates = produits
  to rounding), vintage fields, and the unit traps (the lying-header class
  is catalogued; expect it). Design freeze after M0 only.
* **M1 — cells**: commune × taxe (TFPB/TFPNB) with bases and rates as
  published; no synthesis anywhere; the baseline is again a mechanical
  check (our arithmetic on their bases vs their produits).
* **M2 — knobs**: national revalorisation coefficient (the annual
  valeurs-locatives uplift — the fiscally hottest TF parameter), rate
  changes national and by commune-set; validation against published TF
  receipts, comparator vintages stated.
* **M3 — surface**: UI tab or an extension of the household calculator
  (résidence's commune as input), reconciliation section, fiche support.

Out of scope: valeur-locative *revision* modelling (the 2028 réforme des
valeurs locatives is a structural change — gate it separately if it
survives), exonérations fine structure in v1.

## S7 — the maintenance charter (write it, adopt it, one session)

One page, committed as `docs/CHARTER.md`, then followed: the
**openfisca pin-bump ritual** (deliberate, monthly-ish: bump in a branch,
run everything, re-anchor goldens only with a D-entry citing the law that
moved them); the **annual LF cycle** (each LF: parameters arrive via bump,
new chiffrage cases per article, the triage archived and graded); the
**vintage-refresh calendar** (Ésane, Filosofi, DGFiP stats, REI, TES —
which month each typically publishes, and the manifest update as the
ritual); the full-pass cadence; and the doctrine that every maintenance
change follows the same rules as building (kill tests, D-entries, the
three questions). The charter is infrastructure: it gets the
measurement-infrastructure treatment at birth.

## S8 — wrap

Refresh STATE_AND_NEXT and WHAT_NOW to the post-Phase-6 reality; re-triage
the parked list (succession gate, VAT wait, dormant items) with current
dates; a closing report to the owner stating, in the project's own
honest grammar, what the tool now is, what it refuses, and what only the
owner can decide next.

---

## Sequencing rule

S1 → S2 → S3 → (S4 on its calendar) → S5 → S6 → S7 → S8, with S4
interrupting anything. A stage's definition of done is checked before the
next begins; each stage ends with a report to the owner in the established
format. Reality beats this spec, on the record — D-entries as always, and
when a stage's ground truth contradicts this document, the contradiction is
the finding.
