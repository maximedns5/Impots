# Phase 3 — The Behavioural Layer: Implementation Specification

**Project**: Impôts · **Phase**: 3 of 4 · **Prerequisites**: Phases 0–2 as built; reviews of 2026-08-29 and the 2026-09-02 addenda; D-000..D-028
**Audience**: the implementing agent. Convention adjusted for this phase: there is **no new engine mechanics to verify** — the behavioural layer is arithmetic post-processing over measured mechanical outputs, deliberately outside OpenFisca. What replaces engine verification is **source verification**: every elasticity that enters this layer passes the same adversarial verifier machinery that D-025 ran on the firm parameters, before first use. D-026 binds: agents locate and verify sources; they never author a value.
**Why this phase exists**: official French costings are mechanical *by design* (FIPECO: behavioural responses "difficult, often impossible to measure"). This project's founding claim is that showing the behavioural band honestly — as a range with its evidence attached — beats omitting it. Phase 3 is that claim, implemented. It is also where the project is most exposed to its own failure mode: a band computed from a bad parameter looks exactly like a band computed from a good one.

---

## 0. What Phase 3 is

Every headline number gains its band. A reform's result becomes three stacked answers — the mechanical figure (unchanged, still visually primary), a behavioural band with its channels named, and an applicability grade saying how far the reform sits from the evidence the band rests on. Plus the two items the roadmap has owed since Phase 0: the **chiffrage backtest suite** in `tests/chiffrages/` (empty since 2026-08-28), and the **EMTR machinery** at population scale.

**Definition of done**:
1. `src/impots/behavioural/` computes bands for the four v1 channels (§3); each channel's worked example reproduces to stated precision.
2. Every parameter in the behavioural store has a verifier verdict recorded (§2); unverified rows cannot be loaded (enforced in code, tested).
3. Applicability grading (§4) is enforced in code: a reform outside a channel's historical support gets a widened, flagged band or no band — never a confident one.
4. `tests/chiffrages/` carries ≥5 historical PLF articles with published costings, running in CI, each within its declared tolerance or carrying a written finding.
5. Population baseline artifacts include the EMTR distribution by decile (§6).
6. API and UI expose the band; the mechanical number is unchanged everywhere; all prior suites green.

**Out of scope — refuse**: macro/GE closure (L4 — multipliers, price feedback: Phase 4's decision, not this one); indirect taxes; **capital-income channels** (dividend/PFU response, the best-identified French elasticity of all — structurally impossible until ERFS lands, because the population carries no capital income; say so in the UI where a capital knob would appear); migration/expatriation; firm investment response beyond §3-C4's zero-band; dynamic/multi-year responses.

---

## 0.5 Pre-flight

* The **ERFS interrupt rule** stands above everything: the day Progedo delivers, Phase 1C outranks this work.
* Confirm D-028's quarantine and ingest assertion landed; confirm the two red firm-sector diagnostics (review addendum, 2026-09-02) are logged as done or as open items — they may proceed in parallel with this phase, they do not gate it.
* Read `docs/PARAMETERS.md`. It is the seed of §2's store — and it is a reviewer-compiled table from 2026-08-28, **not yet at the citation standard D-025 established**. Treat every row as unverified input.

---

## 1. Architecture — the layer boundary is the product

The engine and populations stay purely mechanical. Nothing in `engine/`, `population/`, or `entreprises/` learns about behaviour. The new package consumes what the runners already produce:

```
reform → mechanical run (existing, unchanged)
       → per-household / per-cell mechanical quantities (Δtax, Δlabour-cost, marginal rates)
       → channel applicability check (§4)
       → per-channel response arithmetic (§3)
       → Monte Carlo over the parameter store (§2): N=1,000 seeded draws
       → band {p10, p50, p90} + per-channel decomposition + applicability grade
```

Determinism: one seed in one place; identical inputs give identical bands to the last digit (golden-tested). Cost: the arithmetic is vectorised post-processing on arrays the runner already holds — budget seconds, not minutes; the only expensive input is the EMTR run (§6), which is cached per (population vintage, year, reform).

## 2. The parameter store — `behavioural/parameters/*.yaml`

Not the engine's dated-law tree: elasticities are estimates, not statutes. Each entry:

```yaml
key: eti_top_decile
value: {central: 0.30, low: 0.15, high: 0.50, distribution: triangular}
applies_to: taxable income response of decile 10 to net-of-tax marginal rate
responds_to_knobs: [ir_bareme, decote_*, plafond_qf_demi_part]
support:            # the Lucas guardrail's data (§4)
  estimated_on: French IR reforms 1997–2004, marginal net-of-tax changes ≲ 5 points
  max_variation_graded_in_support: 0.05   # |Δ net-of-tax rate|
source: {citation: Cabannes, Houdré & Landais (2014), url: ..., vintage: ..., checked: null}
verifier: {verdict: null, date: null, ref: null}   # loader refuses null verdicts
confidence: medium
```

**M1 is a verifier fan-out over every row** — the D-023/D-025 pattern: one agent per parameter family confirming value, range, population, and support against the primary literature, one adversarial verifier per family attacking them, verdicts recorded in the YAML. Expect the D-025 outcome: values mostly holding, citations needing repair, and one or two rows dying — a row that dies is removed, and its channel narrows or reports "no usable evidence" rather than inheriting an international guess silently. Rows whose only basis is a non-French benchmark carry `confidence: low` and say so in the UI tooltip.

Seed rows from `docs/PARAMETERS.md`: ETI all/top-decile; labour supply extensive/intensive; employment elasticity to labour cost at the SMIC (with its fade-out above ~1.6 SMIC); employer-contribution pass-through, benefit-linked vs unlinked; production-tax investment response (a *null* with its confidence interval); fiscal-multiplier rows are **excluded** — they are L4.

## 3. The v1 channels

Each channel ships with: the formula; the mechanical inputs it requires (and a loud failure when absent — the Phase 2 lesson that computed-then-dropped inputs pass every guard); a hand-derived worked example in the test file's comments; and its decomposition line in the output.

* **C1 — ETI on IR reforms.** Per foyer: `Δln(1−τ')` from the marginal rates the EMTR machinery reports under baseline and reform; response `Δbase = e · base · Δln(1−τ')` with `e` drawn per income group (deciles 1–9 vs 10); revenue effect = mechanical + `τ'·Δbase` summed with weights. Output: revenue band and the offset share ("the behavioural response returns X–Y % of the mechanical yield").
* **C2 — Employment at the SMIC** (employer-contribution and SMIC-adjacent knobs). Per individu: Δlabour-cost from the mechanical run; employment response = elasticity × Δcost/cost, applied only below the fade-out threshold with the fade encoded, aggregated with weights to a jobs band; second-round wage-bill and contribution feedback reported, not iterated (one round only, stated — iteration is GE and belongs to L4).
* **C3 — Incidence pass-through** (employer-contribution knobs). Does not change totals; reallocates the mechanical delta between firms and wages by the linkage class of the contribution being moved (benefit-linked ≈ full pass-through to wages; unlinked ≈ mostly on the employer). Output: the winners/losers-by-decile table under both incidence assumptions, shown as a range — the distributional statement inherits the incidence uncertainty visibly.
* **C4 — Production-tax investment response: the zero band.** The best French evidence (IPP, 2021 CVAE/CFE cut) is a null. Encode it as a band centred on zero with the study's uncertainty, so a CVAE reform's behavioural line reads "no detectable investment response (±…)" — which is the honest, sourced answer and more informative than silence.

A knob no channel claims (e.g. `csg_activite_*` v1) yields: behavioural line = "mechanical only — no evidence-based channel wired for this instrument". Never an implicit zero presented as knowledge.

## 4. Applicability grading — the Lucas guardrail, in code

Per reform × channel: compute the reform's induced variation in the channel's own metric (C1: max |Δ net-of-tax marginal rate| weighted; C2: max relative labour-cost change) and compare to the store's `max_variation_graded_in_support`.

* **In support** → band as computed, grade `in-support`.
* **Beyond support** → band width doubled, grade `illustrative`, UI copy: *"this reform is larger than any the evidence was estimated on; the band is an extrapolation."*
* **Structurally novel** (no channel claims the knob) → mechanical only, grade `no-evidence`.

The grade is data in the API response and a visible label in the UI, and the grading thresholds live in the parameter store, not in code.

## 5. The chiffrage backtest suite — `tests/chiffrages/`, at last

Select **≥5 historical PLF/LFR articles** whose instruments exist in the current ReformSpecs (barème indexations and rate changes, décote changes, CVAE trajectory steps are the natural candidates), each encoded as YAML: the article, the Voies et Moyens / évaluation préalable published mechanical costing with URL and vintage (adversarially source-checked — D-026), the ReformSpec that expresses it, and a declared tolerance (±15 % is realistic given population-vintage mismatch; declare per case, don't inherit). CI runs them; a red case is a finding to write up, not a number to tune away. Note what this grades: official chiffrages are mechanical, so the suite tests **L2**, on historical law — which is exactly what makes it independent of everything this phase adds. Stretch goal, one case: where the realised outturn is published (the CVAE 2023 step), check whether the behavioural band *contains* the outturn; record the answer either way.

## 6. EMTR at population scale

One additional full run with `salaire_de_base` +100 €/year on every individu (the Phase 0 finite-difference pattern, vectorised — cost: one full-tier run, minutes, cached). Emit: EMTR per household → decile distribution into the baseline artifacts and the population tab (France's EMTR distribution is a product feature in its own right), and the per-household marginal rates C1 consumes. Guard: EMTRs in [−0.2, 1.5]; NaN = 0; the distribution's decile medians golden-pinned per population vintage.

## 7. API & UI

`POST /simulate` and `/population/simulate` responses gain `behavioural: {band: {p10,p50,p90}, channels: [...], grade, seed, parameters_vintage}`. The UI's greyed "L3 — à venir" placeholder rows (waiting since Phase 0) finally activate: band rendered subordinate to the mechanical figure, channels and grade one click away, capital-knob caveat where relevant. The mechanical number's presentation does not change in any way — regression-tested on the UI checks.

## 8. Testing

Worked-example goldens per channel (stated precision); MC determinism and convergence (p10/p90 stable to <1 % between N=1,000 and N=4,000 at fixed seed); band monotonicity (widening any parameter range cannot narrow the band); applicability-grade unit tests at the boundaries; loader refuses unverified parameters (test proves it); chiffrage suite green; all Phase 0–2 suites untouched and green.

## 9. Milestones

| # | Deliverable | Gate |
|---|---|---|
| M0 | Pre-flight (§0.5) | |
| M1 | Parameter store + **verifier fan-out complete** | no unverified row loads; dead rows removed with their consequences stated |
| M2 | EMTR machinery + C1–C4 with worked-example goldens | |
| M3 | Monte Carlo + bands + applicability grading | |
| M4 | Chiffrage backtest suite (≥5 cases in CI) | red cases written up |
| M5 | API + UI | ship |

ERFS interrupt outranks all of it, at any milestone.

## 10. Decision-log entries expected

D-029 (parameter store schema + verifier verdicts), D-030 (channel formulas and their worked examples), D-031 (applicability thresholds chosen and why), D-032 (chiffrage case selection and tolerances), plus — as every phase so far has proven — whatever this spec got wrong, found by measuring.
