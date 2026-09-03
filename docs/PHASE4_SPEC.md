# Phase 4 — The Macro Fan (L4): Implementation Specification

**Project**: Impôts · **Phase**: 4 of 4 · **Prerequisites**: Phases 0–3 + hardening as built; D-000..D-045+; the standing rules (guards ship with kill tests; update() never creates; files, not agent prose; mechanical before economic)
**Owner decisions recorded** (log as a D-entry): deployment stays private for now; the Phase 4 fork is the macro fan. Both taken 2026-09-03 with the review file as evidence.
**Audience**: the implementing agent. Like Phase 3, there is no new engine surface: L4 is arithmetic over things the lower layers already measure, plus one new dataset (the INSEE input-output table) behind an M0 reconnaissance gate, plus parameters that pass the verifier fan-out before loading. The risk profile is Phase 3's, with one addition: **this is the layer where the project is most tempted to lie.** The original audit rated L4 one bar of five: "directionally informative, quantitatively a range spanning a factor of 3–5. Label it as illustrative." That rating is a design input, not a defect to engineer away.

---

## 0. What Phase 4 is

Given a reform's mechanical and behavioural outputs, produce **ΔGDP, Δemployment and Δdeficit paths at horizons of 1–3 years, as an explicit fan** — p10/p50/p90 — with its assumptions printed on its face, its uncertainty decomposed by source, and a sectoral composition grounded in the input-output structure. The fan is the fourth stacked answer in the UI, subordinate to the three that exist, and it never appears without its assumptions strip.

**What it is not, stated in the spec so it need not be re-litigated later**: not a forecast; not a DSGE, CGE, HANK or ABM (all on the kill list since the original audit); no monetary-policy reaction; no debt-dynamics beyond arithmetic; no horizon past 3 years; never a point estimate.

**Definition of done**:
1. `src/impots/macro/` produces the fan for any reform the lower layers can price; worked examples reproduce to stated precision.
2. Every macro parameter passed the verifier fan-out; dead rows killed their features visibly (Phase 3 precedent).
3. The M0 TES gate passed: the IO table's identities verified before any propagation code.
4. The CICE containment test (§5) passes: the fan, run on the CICE-shaped shock, contains the published evaluation range.
5. New guards carry kill tests; double-entry extends to the macro block; all prior suites green; full-pass log line newer than this work.
6. UI fan chart with assumptions strip and decomposition; mechanical/behavioural presentation unchanged.

## 0.5 Pre-flight
The full-pass log rule from the 2026-09-03 addendum (`make full` + committed log line) if not yet landed; ERFS interrupt above everything, acceptance test unchanged.

---

## 1. Architecture — three blocks, one anti-double-counting rule

**The rule first**, because the design exists to enforce it: the literature's fiscal multipliers already *include* input-output propagation and induced effects. Running a shock through the IO table **and** applying a literature multiplier to the result counts the same propagation twice. So the two mechanisms have disjoint jobs:

* the **aggregate path** comes from literature multiplier ranges applied to the reform's net fiscal impulse — never from the IO table;
* the **IO table** provides what multipliers cannot: the **sectoral composition** of the first-round shock and the **import-leakage correction** to the impulse (France leaks a substantial share of demand abroad; the TES's own import matrix measures it — computed, not assumed).

**B1 — Shock construction** (`shocks.py`). Map lower-layer outputs to a dated net fiscal impulse and its first-round sector allocation: household disposable-income deltas by decile × MPC-by-decile (store parameter) → consumption impulse, allocated to products via the national-accounts COICOP→NAF bridge (decile-differentiated only if the fan-out verifies a source; otherwise one bridge, stated); firm-side deltas → cost/investment impulse via the C2/C4 evidence already in the store (production-tax investment stays the read-from-the-table zero-band); the state side closes the loop (double-entry extends here: impulse components must sum to the reform's balanced deltas — kill test: a deliberately unbalanced shock must die).

**B2 — Composition and leakage** (`io_layer.py`). Static Leontief on the domestic TES at the aggregation M0 selects (A38 target, A17 fallback): first-round output and employment composition by branch (employment via branch coefficients from the same accounts vintage), and the import content of the impulse, which scales the aggregate impulse handed to B3. Type I only; the induced round belongs to the multiplier and must not be added here (this sentence is a test: an assertion that B2's output is first-round-only).

**B3 — The fan** (`fan.py`). Monte Carlo (seeded, N=1,000) over: instrument-specific multiplier ranges (tax vs transfer vs cost-side; store parameters), the cycle-state toggle (normal vs slack — a *scenario*, user-visible, never estimated), horizon profile (impact/peak/decay shape from the sourced literature), and the revenue-feedback elasticity (revenue ≈ unit-elastic to nominal GDP; store parameter) closing Δdeficit = mechanical + behavioural + macro revenue feedback. Output: p10/p50/p90 per indicator per horizon year, with the spread decomposed into parameter vs scenario contributions, reported separately — the original methodology's §13 discipline, finally implemented.

## 2. Parameter store additions — same YAML, same fan-out gate

New rows (all through the adversarial verifier before loading; dead rows kill features): multipliers by instrument × cycle state (candidate sources: OFCE e-mod publications, DG Trésor/Mésange documentation, ECB/IMF meta-analyses — the ranges the audit recorded, 0.2–0.6 tax-side, 0.5–1.2 spending-side, 1.3–2.5 in slack, are *reviewer-compiled seeds and therefore suspect by precedent*: eti_all's fate applies); MPC by income position (French evidence first — HFCS-based estimates; an international benchmark row must carry `confidence: low` and say so in the tooltip); revenue-GDP elasticity (Trésor's published aggregate elasticity); employment-output linkage (Okun-style, French estimates). Support metadata as in Phase 3: a reform impulse larger than the literature's estimated shocks grades `illustrative` and widens.

## 3. M0 — the TES reconnaissance gate

Download from insee.fr (comptes nationaux annuels, latest définitif/semi-définitif vintage): the TES/TEI at the finest published level, with the import table and branch employment. Manifested, sourced, adversarially re-checked (D-026). `scripts/verify_tes.py` asserts before any propagation code exists: row totals = column totals per branch (to published rounding); the import matrix present and non-negative; Leontief invertibility (spectral radius < 1); employment coefficients positive and finite; vintage and base year recorded. `docs/M0_TES.md` records findings and the chosen aggregation. **Design freeze for B2 only after M0** — the EEC precedent (M0 changed the shape of the problem) is why this gate exists.

## 4. Output contract & UI

The fan never renders without its strip: cycle-state chosen, Type I + literature-multiplier design, import leakage %, horizon, `parameters_vintage`, grade. Decomposition view: parameter vs scenario spread. Copy for the banner, non-negotiable and to be shipped verbatim in spirit: *"Couche macro (L4) : ordre de grandeur et composition, pas une prévision. L'éventail des estimations crédibles pour un même choc varie d'un facteur 3 à 5 ; c'est une propriété de la littérature, pas de ce modèle."* Load the repo's dataviz conventions before drawing the fan chart. Mechanical and behavioural presentation unchanged — regression-tested, as always.

## 5. Validation — episodes, identities, and one containment test

* **Identities**: IO balance re-asserted at load; double-entry across B1; deficit arithmetic closed to tolerance. Each with its kill test.
* **The CICE containment test (acceptance)**: construct the CICE-shaped impulse (≈1 % of GDP, cost-side, wages ≤2.5 SMIC) and run the fan. The employment fan at the relevant horizon must **contain the published evaluation range (~100k–400k jobs)**. Containment, not matching — the fan being wide enough to hold the real disagreement between France Stratégie's own evaluators is precisely its claim to honesty. If it fails, the calibration is wrong in a way the project must understand before shipping the layer.
* **A second episode** (choose from: 2019 bascule — expect ≈ no additional employment effect, per IPP; the 2021 production-tax cut — expect the zero-band to dominate) as a narrative comparison in the report, not a test.
* No aggregate time-series backtest: n is too small and the exercise would manufacture false confidence; the report says so.

## 6. Testing
Worked-example goldens per block; MC determinism and convergence; band monotonicity; kill tests for every new guard (standing rule); the containment test in the gate suite (it needs only the fixture population — verify, don't assume); chiffrage and all prior suites untouched.

## 7. Milestones
M0 TES gate → M1 parameter fan-out (dead rows kill features) → M2 B1+B2 with identities and kill tests → M3 B3 fan + decomposition → M4 validation episodes + containment → M5 UI. ERFS interrupt at any point; if it fires, the indexation acceptance test and Phase 1C take precedence and this spec resumes after.

## 8. Decision-log entries expected
The owner-decisions entry (deploy private; fork = macro fan), D-TES vintage/aggregation, D-parameter verdicts, D-containment result, and — as five phases have now proven without exception — whatever this spec got wrong, found by measuring.
