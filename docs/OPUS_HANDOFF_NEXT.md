# Handoff prompt — post-Phase 3 increment

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are continuing the Impôts project after Phase 3 shipped and was reviewed.
The Phase 3 verdict (final addendum of `docs/REVIEW_2026-08-29.md`) is accepted
project law: the 3-of-5 chiffrage shortfall is accepted with conditions, the
parameter fan-out's kills stand, and the dormant channels are correctly dormant.
Read that addendum in full first, then this brief. The ERFS interrupt rule
outranks everything below: the day Progedo delivers, run Phase 1C — its
acceptance test is defined in item A4.

## A. Verdict housekeeping (small, do first, one commit each)

1. `docs/PARAMETERS.md` gets a superseded banner at the top: sole source of
   truth is `behavioural/parameters/`; the file is a historical record whose
   compilation errors (eti_all 0.05 vs the paper's 0.02) are documented in the
   review. Nothing may ever be seeded from it again.
2. The five dead chiffrage cases get post-mortems in the decision log — why
   each died (unverifiable costing, inexpressible knob, wrong vintage…). Add
   the standing rule: every new ReformSpec knob triggers a re-sweep of
   expressible historical articles.
3. New standing test rule, applied to existing bounds too: a tolerance on a
   signed quantity is two-sided or written on the magnitude, never one-sided
   on the raw value. Sweep the suites for other instances of the bug class.
4. Append to `docs/PHASE1C_ERFS.md` §6: the barème-indexation backtest is the
   migration's acceptance test — it re-runs before anything else on the ERFS
   population, and real incomes are expected to collapse the +10 %
   bracket-mass overshoot (D-015's first external measurement).

## B. C4 revival — bounds read, not derived (D-026-compliant, ~30 min)

Download the IPP Report 60 PDF ("La baisse des impôts de production", Oct 2025,
ipp.eu) into `data/raw/` with a manifest entry. Read the actual confidence
intervals from the actual results tables; cite table and page in the parameter
YAML; record the verifier verdict. If the tables carry a usable interval, C4
wakes as the zero-band with real bounds. If they genuinely do not, C4's "no
usable evidence" stands — concluded from the table, not from anyone's summary.

## C. The main build: employer-contribution knobs → C2/C3 wake

The Phase 3 spec wired C2/C3 to a knob that never existed (spec error, on the
record). Add it now. Verified anchors, checked live against openfisca-france
176.0.8 on 2026-09-03 — variables `allegement_general`,
`allegement_cotisation_maladie`, `allegement_cotisation_allocations_familiales`
(all individu/month), and the parameter node
`prelevements_sociaux.reductions_cotisations_sociales.allegement_general
.ensemble_des_entreprises`, which at 2024-01-01 resolves to plafond = 1.6
(SMIC multiple) and taux 0.3234 (50+ salariés) / 0.3194 (<50). The famille
bandeau lives at `...reductions_cotisations_sociales
.allegement_cotisation_allocations_familiales` (children include
`plafond_smic*` and `reduction`); the maladie bandeau's rates are
`...cotisations_securite_sociale_regime_general.mmid.tx_normal` / `tx_red` —
its plafond node you must introspect and pin yourself, same as every other
path: **read-back verification per D-007 for every scale- or
threshold-shaped edit, no exceptions.**

Scope: extend the household `ReformSpec` whitelist with (at minimum) the
réduction générale's plafond and taux, and the two bandeaux's plafonds and
rates; reform-cache keys and `verify_*` read-backs as everywhere else; C2/C3
applicability metadata updated so both channels wake with no channel-code
changes; worked-example goldens per new knob (hand-derived, engine-checked at
one household before population use); re-sweep chiffrage articles now
expressible (the 2025-2026 allègements refonte is the obvious candidate — and
politically the hottest thing this simulator could price); UI reform panel
gains the knobs with the C3 incidence-range display the Phase 3 spec §3
specified. EMTR artifacts likely need no change; verify rather than assume.

## D. Rules in force, abbreviated

Mechanical before economic. Codes, not labels. Files, not agent prose, for any
figure (D-026). No unverified parameter loads. The mechanical number never
changes and its presentation never changes. Reality beats every spec, on the
record — expected entries D-033+.

Deliverables: the A-items committed; C4 resolved from the table; the knobs
live end-to-end (engine → API → UI) with goldens; chiffrage re-sweep done;
decision log current. If the git remote exists by the time you start, your
first push must go green in CI before anything else merges.
