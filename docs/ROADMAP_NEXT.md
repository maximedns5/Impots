# What's left, and what to build next — 2026-09-08

Two parts: the closure work that finishes what is open (Session A, do first),
and a proposed feature backlog for the phases after (F1–F8, owner picks the
order; a recommended sequence closes the file). The real-income-microdata
interrupt is DORMANT, not dead (D-096): it still outranks everything on
arrival, as always.

---

## Session A — closure (do first, one session)

1. **The b1cg correction** in `corrections.py` (formula-level, the seuil-gate
   precedent) with its kill test: declared valeurs mobilières must replace
   the 5 % forfait presumption (art. 764 I-3°), never stack on it. Add the
   finding to the upstream dossier (sixth artefact).
2. **Record the ISF-2017 backtest** in the reconciliation's patrimoine
   section exactly as reported (−0.5 % pass; +19.7 % pinned red with its
   mechanism; cap shape −64.7 % vs −67.7 %), closing Phase 5's books.
3. **Status-check and clear**: the narrative sweep, the
   name-the-failing-implementation audit, the prestations leftovers
   (2015 AF-modulation backtest first, worked goldens, remaining UI knobs).
4. Apply the new pointer rule to all existing handoffs' source references
   (identifiers + sha256, never bare URLs as load-bearing).

## The feature backlog

**F1 · PLF 2027 live pricing — timely, do while it is.** The PLF 2027 lands
in the Assemblée in early October — weeks from now. Build the scenario
machinery (F2) in time to encode its fiscal articles as a named scenario the
week they publish, price each article the tool can express, and **pre-register
the chiffrages internally** (dated, committed, graded later against
évaluations préalables and eventually outturns). Whether or not anything is
ever published, this is the tool's first contemporaneous real-world test, and
pre-registration is the strongest credibility instrument a model can own.
*Effort: small on top of F2. Value: the highest per hour on this page.*

**F2 · Reform composer.** ~~Named multi-knob scenarios saved/loaded as
JSON; side-by-side A/B comparison of two reforms (all layers: mechanical,
band, fan); and a **budget-neutral solver**.~~ **DONE, 2026-09-08 — D-092.**
`impots scenario save|list|show|compare|solve`, read-only `GET /scenarios`,
and a UI picker. The solver refuses every banded quantity, refuses a
non-scalar knob, and never presents a non-converged iterate as an answer.

Two things it does NOT do, stated rather than left to be discovered. The
roadmap's «barème shift» is not solvable: `ir_bareme` is a full scale, not a
scalar, and root-finding needs a scalar — the refusal says so and says what
to add. And the A/B comparison shows the banded layers side by side without
differencing them, because the difference of two intervals is an interval.

It also found a bug in our own double-entry guard on its first real run
(D-093): the identity scaled its residual by the reform's net, which the
solver drives to zero by construction.

**F3 · Trajectories (multi-year).** **GATED, 2026-09-08 — D-099.** The M0 gate
(`docs/M0_TRAJECTORIES.md`) measured the premise and overturned it: the dated
tree encodes the future on TWO parameters out of sixty-two (the CVAE and its
dégrèvement, ending 2030), and reconducts 2026 everywhere else. So a barème
freeze cannot be priced against a baseline that is already frozen — F3's first
deliverable is a second, indexed counterfactual, not a knob. Spec written:
`docs/F3_SPEC.md`. The gate also found the firm engine crashing at 2029 on a
YAML value parsed as a string; fixed and guarded. Original text follows.

The other Phase-5 finalist, still the
biggest modelling item: price reforms over 2024–2030 paths using the dated
tree that already encodes the future (CVAE trajectory, CEBGE expiry);
**indexation policy as a knob** — the barème-freeze stealth tax priced per
year; deficit paths with the fan per year. Population uprating per year is
the honest hard part: uprate mechanically (wage/price indices, stated),
never re-synthesise. *Effort: a full phase with a spec. Value: every
existing knob gains a time dimension.*

**F4 · The fiche de chiffrage generator.** ~~One exportable report per reform~~
**DONE, 2026-09-08 — D-098.** `impots fiche <scenario>`; shaped on the real
évaluation préalable skeleton read in F1. Three rules with kill tests: a
mechanical figure never appears without its band or the reason there is none;
the fan never renders without its assumptions strip; a section a model cannot
write is marked, not omitted. Original text follows.

One exportable report per reform
assembling the whole honesty stack — mechanical figure, behavioural band
with channels and grade, cell-bound and composition intervals where they
apply, fan with assumptions strip, narrow-band and zero-base warnings, data
vintages, and the relevant reconciliation lines. Shaped like an évaluation
préalable annex, but with the uncertainty grammar no official fiche carries.
*Effort: one increment, mostly assembly. Value: the project's identity in a
single artefact; also what C2 (methods page) would one day be built from.*

**F5 · Taxe foncière from the REI.** A new base, and genuinely open: the
DGFiP REI file (data.gouv) carries per-commune rates and bases. Cell design
(commune × base), TF knobs national and local, validation against published
TF receipts. The last big open-data tax with no open model. *Effort: a
short phase — M0 recon gate on the REI first; the file is large and its
columns are a known swamp. Value: high; nothing public does this.*

**F6 · EMTR/ATR explorer.** Curves across the income range per household
type, baseline vs reform, bracket-crossing and taper-stacking made visible —
the machinery (engine + finite differences) exists; this is presentation
over measurement. France's EMTR landscape is itself a finding (63.5 % peaks
on modest households). *Effort: small. Value: pedagogic, and a demo that
sells the tool's seriousness.*

**F7 · Succession/DMTG (exploratory gate only).** Topical and big, but
public per-estate data is thin. Authorise only an M0-style reconnaissance:
what do DGFiP/Insee actually publish on transmissions by size? If cells are
buildable, it becomes a phase; if not, it is closed with a reopen condition
like the Zucman floor. *Do not build past the gate without the owner.*

**F8 · Aggregate VAT scaffolding.** Rate knobs priced on national-accounts
COICOP aggregates with an explicit "no distribution until BDF 2026 arrives
(~2027-28)" banner. Honest but thin; ranks last while F1–F6 exist.

## Recommended sequence

**A → F2 → F1** (the composer exists before the PLF drops — that timing
matters more than anything else on this page) **→ F4 → F3 as the next full
phase → F5 → F6**, with F7's gate run whenever a session has spare room and
F8 parked. Standing items outside the queue: CAF cross-check (owner,
30 min); real income microdata is not available for the foreseeable future
(D-096), so nothing is being waited on there;
upstream dossier and all publication (owner). The maintenance charter gets
written the first quiet week — after F1's pre-registrations are in, quiet
weeks exist again.
