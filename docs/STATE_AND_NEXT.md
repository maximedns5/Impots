# State of the project, and the directions open — 2026-09-09 (post-Phase 6)

Supersedes the 2026-09-09 in-flight version. For any next session: read
this, `docs/CHARTER.md`, and the review file's last addenda.

## Where the project stands, whole-arc

Six weeks from the first audit, the tool prices household taxation exactly
(DGFiP-validated; niches, prestations, allègements as knobs), firms
(IS/CVAE/C3S/CEBGE on real DGFiP-Ésane cells, every line in tolerance),
wealth (IFI exact, ISF revival, backtested out-of-sample against IPP's 2017
tables), behavioural effects as bands on adversarially-verified evidence, a
macro fan that refuses to be a number, and — added in Phase 6 — taxe
foncière from the REI at commune resolution.

Around the model: a reform composer with a budget-neutral solver, the fiche
de chiffrage generator, a pre-registration harness whose integrity lives in
git history rather than in the file it protects, the PLF coverage triage
(29 fiscal articles, four buckets, two headline denominators), multi-year
trajectories with populations uprated and never re-synthesised, an EMTR
explorer, and a maintenance charter that is itself under test.

**1 315 tests**, seven replayable `verify_*.py` gate scripts, CI green on an
instrument that has been shown to fail, and **113 decision entries** recording
every error in both directions.

## Phase 6 — closed 2026-09-09

| | | |
|---|---|---|
| S1 | F3 M4 — the band, year by year | done |
| S2 | F3 M5 — trajectory outputs; F3 closes | done |
| S3 | F1b — the capital-income gate | **gate run, cleared; the build is the owner's call** |
| S4 | PLF 2027 week | **armed, calendar-triggered, early October** |
| S5 | F6 — the EMTR/ATR explorer | done |
| S6 | F5 — taxe foncière from the REI | done (D-111) |
| S7 | the maintenance charter | done (D-112) |
| S8 | wrap | this document |

Two backfills ran before S1, at the reviewer's order: the missing D-entry
stubs, and `scripts/verify_rei.py`, which turned the REI gate's findings
into assertions that stay.

## The calendar item that is not a choice

**PLF 2027, early October — S4 interrupts anything.** The runbook, harness
and triage are ready. When the text publishes: manifest it, re-derive the
triage (the re-sweep rule — levers have changed since, so articles that were
inexpressible may not be any more), wire the pre-identified knobs, register
chiffrages with tolerances fixed **at registration**.

F3 makes this materially stronger than last year: multi-year articles get
priced per year, each with its basis labelled legislated or reconducted, and
the fan's horizon refusal binds per year rather than for the whole run.

The F1b gate has run and cleared, so the CDHR is no longer a blocker for
that week. What remains is an owner decision (below), not a task.

## Directions open — the owner picks

* **F1b's build: the RCM imputation.** The gate cleared. Whether to build it
  is a judgement about how much imputed capital income the project wants to
  carry, and it was left to the owner deliberately.
* **F7 — succession/DMTG.** Gate only, never past it without the owner.
  Re-triaged 2026-09-09: still worth a reconnaissance session, still
  authorised no further.
* **F8 — aggregate VAT.** Re-triaged 2026-09-09: **still waiting on Budget de
  Famille 2026, expected ~2027-28.** Unchanged and correctly parked; nothing
  about Phase 6 moved it.
* **The CAF cross-check.** Prepared since 2026-09-03, 30 minutes at a
  browser, owner-only. **No reCAPTCHA circumvention under any
  circumstances.** Unchanged.
* **The upstream dossier** (7 catalogued artefacts, each with a kill test)
  and **all publication and deployment**: owner's, deferred, no pressure.
  Each phase widens the gap between what this tool does and what any public
  tool does; the option ripens by itself.
* **Zucman**: closed, reopen condition on the record. **ERFS**: dormant, not
  dead (D-096) — fires if access ever materialises.
* **A sourced production-tax series** is the one identified blocker on a
  known-desirable case: the multi-year CVAE chiffrage needs it, and every
  series to hand is quarantined.

## What the next session does if nobody says otherwise

Maintenance, per `docs/CHARTER.md` — and nothing more. Building has reached
the point where the charter's cadence (pin bumps, vintage refreshes on the
nine-source calendar, full passes) is the real work until the PLF drops.

## Standing, unchanged

ERFS microdata is not redistributable; only aggregates leave it. `data/` is
committed by allowlist only. Do not fabricate the numbers. The review file's
addenda, all of them, including the five standing questions and «reality
beats every spec, on the record».
