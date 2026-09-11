# Phase 8 — Le laboratoire de politique fiscale (spec)

**Date:** 2026-09-11
**Author:** reviewer session (Fable)
**Status:** authorized by owner ("Write the detailed spec phase 8, knowing that we have to take the maximum of different taxes, impôts, on products, people and companies")
**Prerequisites:** Phase 6 closed (1f4e38f, 1313 passed, 2 skipped). Phase 7 (accuracy campaign) runs **in parallel** and is not blocked by, nor blocks, this phase — see §8 for the merge fence.
**Governing verdict (unchanged since the audit):** we do not build a predictive model; we build a transparent simulator with layered, labelled fidelity — mechanical (exact) → population → behavioural (band) → macro (fan). Honesty is the product.

Reality beats this spec. When implementation reveals the spec is wrong, follow reality and record the divergence in DECISIONS.md, as every phase has.

---

## §0 What Phase 8 is, and is not

Phase 8 turns the simulator into a **policy laboratory**: the user can move the maximum feasible set of taxes and impôts — on products, on people, on companies — and see three things per scenario:

1. **The receipts consequence**, with the full honesty stack (mechanical Δ exact, behavioural band, macro fan, applicability grades, double-entry identity).
2. **The debt trajectory consequence** — a debt/GDP fan under explicit r, g, and spending scenarios (§3).
3. **The reindustrialization panel** — what the scenario does to the tax burden on production, by sector, against the German/EU benchmark, with evidence-graded response bands and no promised factories (§5).

Plus an **objective explorer** (§4): given a target ("primary balance +30 bn"), search the instrument space for candidate bundles — on the mechanical layer only — and present each candidate through the full honesty stack.

### The non-negotiable honesty rule of this phase

Public spending is roughly 57% of GDP and this model prices only the transfer slice of it. Therefore: **every debt trajectory rendered by this tool carries an explicit, named spending scenario, chosen by the user or clearly displayed as the default's name — the tool refuses to render a debt path without one.** A debt tool that silently holds spending fixed while the user moves taxes is a machine for implying that taxes alone must close the gap. We will not build that machine. This is a guard with a kill test (§3.5), not a documentation promise.

### What Phase 8 refuses, up front

- **No optimization on banded quantities.** The explorer searches mechanical-layer scalars only; bands and fans are stress applied to candidates afterwards. Allowlist refusal, kill-tested (§4.2).
- **No distributional TVA.** Aggregate TVA knob only, until Budget de Famille microdata (~2027-28). Permanent banner on the instrument (§2.3.1).
- **No reindustrialization outcomes.** Instrument panel, composition, benchmark, evidence bands — never a factory count, never an employment promise (§5.1).
- **No future-year receipts "comparisons".** Vintage refusal fires before any gap is evaluated, per the trajectory rules (F3).
- **No invented instruments.** We re-price instruments that exist in law. We do not model hypothetical taxes (e.g. a new carbon tax design) — that is a different product with different honesty requirements.
- **CDHR stays refused** (threshold-on-ratio ill-posedness, on the record). Phase 8's "maximum d'instruments" does not reopen closed refusals; it adds instruments that pass their gates.

### Definition of done (phase level)

- M0 recon report reviewed and the design freeze recorded in DECISIONS.md.
- Debt closure (§3) live with its 2019→2025 backtest graded and its spending-scenario guard kill-tested.
- Aggregate-instrument engine (§2.2) live with ≥ 8 new instruments priced, each with receipts anchor manifested, refusal surface tested, and double-entry identity extended over them.
- Objective explorer (§4) live with its banded-target refusal kill-tested and one worked end-to-end example on the record.
- Reindustrialization panel (§5) live with the C4 zero-band rendered on production-tax scenarios and the benchmark data manifested.
- `make full` green; full pass logged in reports/full_pass_log.md.
- Every new guard has a kill test that has been seen to fire. Every anchor in this spec is either **[VERIFIED]**, **[ENACTED]** (confirm at BOFiP), or **UNMEASURED** — and every UNMEASURED anchor is measured or replaced before the code that depends on it ships.

---

## §1 M0 — Reconnaissance gate

Nothing in §2–§5 is design-frozen until the recon below is done and reviewed. Recon **locates and manifests data**; it never authors figures (D-026: calibration inputs arrive as files with checksums, not as agent prose). Deliverable: `docs/M0_PHASE8.md` — one section per R-item, each ending in either MANIFEST entries (path, source identifier, sha256, vintage) or a dated "does not exist / not accessible" finding.

Pointer rule applies: the identifiers below are dataset/publication names, not URLs. URLs rot (my own stale IPP URL is on the record); names are for the implementer to resolve, download **on the owner's network** (insee.fr and some *.gouv.fr downloads are proxy-blocked from both container and VM — established fact), and checksum.

- **R1 — AFT debt stock and maturity structure.** Agence France Trésor publishes the detailed outstanding of OAT (« Encours détaillé des OAT ») and BTF, plus auction results; AFT datasets are mirrored on data.gouv.fr (e.g. « Encours de la France » series). **[VERIFIED 2026-09-11 that these publications exist; contents UNMEASURED until manifested.]** Need: per-line outstanding, coupon, maturity date → redemption schedule and coupon-weighted implicit rate. Also: average maturity of the debt (AFT monthly bulletin) — UNMEASURED, expected ≈ 8–9 years, measure it.
- **R2 — Interest burden anchor.** PLF 2026, mission « Engagements financiers de l'État », programme 117 « Charge de la dette et trésorerie de l'État » (Sénat rapport général on that mission is a usable secondary). Secondary press puts the 2026 charge near €77 bn — **UNMEASURED until the mission document is manifested.** This anchors the model's implicit-rate × stock arithmetic at t₀.
- **R3 — Debt stock and ratio.** INSEE Informations rapides n°158: end-Q1 2026 public debt (Maastricht) = **3 536.1 bn €, 117.5% of GDP** — **[VERIFIED 2026-09-11 via INSEE publication; manifest the INSEE file itself]**. Note on the record: the reviewer's conversational figure ("~3,300 bn / ~114%") was stale; the measured figure replaces it (reviewer error ledger #9, see REVIEW file). Also manifest: the quarterly series (for the §6 backtest) and annual GDP (the 2024 anchor 2 919.9 bn is already on the record).
- **R4 — Accises data.** DGDDI open-data portal (douane.gouv.fr « Open data ») for energy/tobacco/alcohol receipts and volumes; OFDT for tobacco volumes/prices; the accise framework is now in CIBS (code des impositions sur les biens et services) — rates are **[ENACTED — confirm current rates at BOFiP/Légifrance via economie.gouv.fr mirrors]**. Need per-instrument: receipts (latest closed year), physical base (volumes), rate structure. All UNMEASURED until manifested.
- **R5 — TVA aggregate.** Receipts: DGFiP/Voies et Moyens tome I (budget-year column rule is on the record — read the right column). Base by rate: comptes nationaux consumption at COICOP level with a published rate mapping (INSEE CN). UNMEASURED until manifested. The F8 scaffolding note in ROADMAP_NEXT.md is superseded by this section.
- **R6 — DMTG.** The F7 reconnaissance gate as previously specified stands unchanged — this spec does not widen it. Gate-only: DGFiP receipts + whatever tabulation exists (enquête Patrimoine moments are quarantined pending source verification). No DMTG module ships in Phase 8 unless the gate passes with microdata-free feasibility demonstrated.
- **R7 — Company-side and local instruments.** Taxe sur les salaires (Voies et Moyens + URSSAF), versement mobilité (URSSAF open data, per-AOM rates exist), DMTO (DGFiP/DGCL départements series), TASCOM, TGAP, TTF (receipts in Voies et Moyens), taxe d'habitation résidences secondaires + THLV and taxe foncière (REI — we have verify_rei.py and the M0_REI.md findings; reuse, do not re-derive), CIR (MESR GECIR statistical publications; the créance/costing distinction must be stated). Receipts UNMEASURED until manifested.
- **R8 — Production-tax benchmark.** Eurostat national tax lists / « taxes on production » (D.29) by member state as % of value added, and the sectoral IO composition we already hold in macro/io_layer (Phase 4 provenance — reuse the manifested TES, do not re-import). Germany-vs-France D.29 gap UNMEASURED until measured from the manifested file.

**Review gate:** M0_PHASE8.md goes to the reviewer before any §2–§5 code. Items that come back "does not exist" convert their instruments to Bucket D (refused, reason recorded) — that is a success of the gate, not a failure of the phase.

---

## §2 Instrument maximization — « le maximum de taxes et d'impôts »

### §2.1 The four buckets

Every instrument in the inventory below is classified into exactly one bucket, and the classification is itself a reviewable artifact (it goes in M0_PHASE8.md, revised by recon results):

- **Bucket A — priced on the microsimulation layer.** Exists now or is a knob on an existing engine (households via openfisca-france population layer; firms via the cells engine). Distributional output allowed, per existing grades.
- **Bucket B — priced on the new aggregate layer** (§2.2). Receipts anchor × rate re-pricing on a static national base, optional evidence-graded behavioural band. **No distributional output, ever, and the refusal says why.**
- **Bucket C — gated.** A named recon gate must pass before any code. If the gate fails, the instrument moves to D with the finding recorded.
- **Bucket D — refused, with the reason on the record.** Refusals are allowlists: the UI/API names the instrument and states the refusal reason; it does not silently omit.

House rules that bind every bucket: codes not labels (no substring matching on French labels — the `"IS" in label` incident is on the record); phantom check for any OpenFisca parameter node claimed (the node must be READ by a formula in model source — dead `aide_a_domicile` tree, six dead look-alikes, one dead twin are on the record); update() never creates; comparator vintage and perimeter always stated.

### §2.2 The aggregate-instrument engine (new, one engine for all of Bucket B)

One module (suggested: `src/impots/agregats/`), one dataclass per instrument, all sharing:

- **Inputs:** receipts anchor (year, source, sha256 — from MANIFEST, never from prose), rate structure as enacted, physical or value base where the re-pricing is rate×base rather than proportional receipts scaling. Each field carries its vintage.
- **Mechanical re-pricing:** new_receipts = f(new_rates) holding the base fixed. For single-rate instruments this is proportional; for multi-rate (TVA) it is per-rate-component using the base split from R5. Exact arithmetic, labelled mechanical, grade stated.
- **Behavioural band (optional, per instrument):** an elasticity interval from the evidence table (BOP-style rows: source, population, identification, grade — the 8-row discipline from Phase 7 L3 applies; new rows go through the same season format). Banded or absent, never confidently wrong. No elasticity row → mechanical only, and the output says "aucune réponse comportementale modélisée" rather than showing 0 as if measured.
- **Refusal surface:** every aggregate instrument REFUSES distributional queries (deciles, types de ménage, incidence) with a named reason. Allowlist: the only outputs an aggregate instrument can produce are national receipts (mechanical + band) and its contribution to the §3 primary-balance path. Kill test: request a decile split of TVA → named refusal; the test proves the guard fires (a guard nobody has seen fail is not a guard).
- **Double-entry:** every Bucket B instrument enters the reform-cost identity. The sum-of-instruments vs headline check extends over the aggregate layer; a scenario mixing micro and aggregate instruments must balance across both. The first double-entry guard self-balanced (on the record) — the extended one must be tested against an artificially broken ledger.

### §2.3 The inventory

Status keys: [A]/[B]/[C]/[D] as above; « déjà en place » marks instruments live before Phase 8.

#### §2.3.1 Produits (taxes on products)

| Instrument | Bucket | Notes |
|---|---|---|
| TVA (20 / 10 / 5.5 / 2.1) | **B** | Per-rate base split from CN COICOP (R5). Permanent banner: « agrégat national — aucune distribution avant Budget de Famille (~2027-28) ». Rate knobs per taux; base-restructuring scenarios (moving goods between rates) allowed only if R5 yields a per-rate base at COICOP granularity — else that sub-knob is D. |
| Accise énergies (ex-TICPE) | **B** | Rate-per-volume × CCTN/DGEC volumes. Behavioural band from fuel-demand elasticity rows (evidence season; short-run vs long-run stated). |
| Accise tabacs | **B** | OFDT volumes; price-elasticity band from evidence rows. Note: the receipts response to large hikes is the historically graded case (§6.2). |
| Accise alcools | **B** | Volumes DGDDI/OFDT. |
| Accise électricité (ex-TICFE) / gaz (ex-TICGN) | **B** | Post-2022 rate history is turbulent (bouclier tarifaire) — vintage discipline matters more than usual; anchor on latest closed year. |
| TSN (services numériques) | **B** | Receipts-scaling only; high-mobility-base warning grade on any band. |
| TTF | **B** | Same warning grade; the literature on TTF base flight is contested — band wide or absent. |
| TICPE-style new carbon instruments | **D** | We re-price existing accises; we do not design hypothetical taxes. Reason on record. |

#### §2.3.2 Personnes (people)

| Instrument | Bucket | Notes |
|---|---|---|
| IR (barème, décote, QF, CEHR, niches B3) | **A** — déjà en place | Nothing to do beyond Phase 7 accuracy work. |
| CSG/CRDS (all bases) | **A** — déjà en place | |
| PFU / RCM household calculator | **A** — déjà en place | |
| PFU population layer | **C** | Gated on the F1B_CAPITAL_GATE verdict (RCM-by-tranche). Phase 8 neither advances nor blocks it. |
| CDHR | **D** | Closed refusal (threshold-on-ratio, ill-posed from cell means at any granularity). Restated here so "maximum d'instruments" is not read as reopening it. |
| IFI (+ ISF/IGF historical) | **A** — déjà en place | |
| DMTG (successions/donations) | **C** | F7 gate, unchanged (R6). |
| TH résidences secondaires + THLV | **C→B** | Recon in R7 against REI. If REI carries the base: B with commune-level aggregation to national; still no household distribution. |
| Taxe foncière (part ménages) | **C→B** | Same route via REI. The ménages/entreprises split of TF is itself UNMEASURED — if no published split exists, the instrument prices the total with the split labelled as scenario. |
| Prestations (RSA, PPA, AF, APL…) | **A** — déjà en place | Spending-side instruments; they enter §3 through the primary balance like any reform. |

#### §2.3.3 Entreprises (companies)

| Instrument | Bucket | Notes |
|---|---|---|
| IS (taux normal/réduit, CS, CEBGE) | **A** — déjà en place | |
| CVAE (to 2030), C3S | **A** — déjà en place | C3S N-1 assessment/N+1 booking rule stays load-bearing. |
| Cotisations + allègements | **A** — déjà en place | |
| CIR | **C** | Gate: MESR GECIR publications must support a créance-based re-pricing with the créance/décaissement distinction explicit. The carry-forward stock problem is the same UNMEASURED class as Phase 7 L4 — if it cannot be measured, CIR prices the créance flow with a banner, or moves to D. |
| Taxe sur les salaires | **B** | Sectoral incidence (banques/santé/associations) can be STATED as composition from published data without being modelled as distribution. |
| Versement mobilité | **B** | URSSAF open data; national aggregate with the per-AOM rate structure summarized, re-priced by a uniform multiplier (per-AOM knobs are D — no local simulator). |
| DMTO | **B** | Behavioural band from transaction-volume elasticity rows if the evidence table gains them; else mechanical with « aucune réponse modélisée ». |
| TASCOM, TGAP, forfait social, taxe apprentissage & assimilés | **B** | The « petites taxes » tranche: one row each, receipts anchor each (Voies et Moyens — budget-year column rule), proportional re-pricing, no bands unless evidence rows exist. Coverage breadth is the point; per-instrument depth is not. |
| CFE / CVAE locales beyond existing | **C** | Only via REI reuse; no new local simulator. |

### §2.4 What "maximum" means, measurably

DoD for §2: the laboratory's instrument list, rendered in the UI, covers **every tax listed in Voies et Moyens tome I with receipts above a threshold chosen and recorded at M0** (suggested: 1 bn €), where each is either priced (A/B), gated with the gate named (C), or refused with the reason displayed (D). "Maximum" is thus an auditable coverage claim against a published universe — not a vibe. The coverage table (instrument, receipts, bucket, grade) is itself a deliverable: `docs/COVERAGE_INSTRUMENTS.md`.

---

## §3 Debt-dynamics closure — the accounting spine

Suggested module: `src/impots/dette/`. This ships FIRST (M1): everything else in the phase hangs receipts off this spine.

### §3.1 The identity

In ratio-to-GDP terms, per year:

    b_{t+1} = b_t * (1 + r_t) / (1 + g_t) - p_{t+1} + sfa_{t+1}

where b = debt/GDP (Maastricht), r = implicit nominal interest rate on the stock, g = nominal GDP growth, p = primary balance/GDP (surplus positive), sfa = stock-flow adjustment/GDP. This is arithmetic, not economics: it is the **mechanical layer** of the debt tool, and it is exact **given its inputs**. The honesty layering therefore lives in how each input is produced and labelled:

- **b_0:** measured. End-Q1 2026: 117.5% / 3 536.1 bn € [VERIFIED — INSEE Informations rapides n°158; manifest at R3]. The tool anchors on the latest manifested quarter and states it.
- **r_t:** derived from the AFT maturity structure (§3.2) under a user-chosen market-rate scenario. Labelled « scénario », never « prévision ».
- **g_t:** user scenario from a small named set (e.g. « croissance nominale 3.0% », « stagnation 1.5% », user-set) — scenario, not forecast. No hidden default: the UI shows the name.
- **p_t:** the model's own output (§3.4) — this is where reforms enter — plus the spending scenario (§3.5).
- **sfa_t:** explicit named input, default « nul », with a banner stating that historically the SFA is not negligible and the default is a simplification. UNMEASURED historical SFA series to be manifested at R3 for the backtest (§6.1), where it is NOT optional — the backtest uses the realized SFA, because a backtest that omits a realized term and still "passes" has been fitted, not tested.

### §3.2 The implicit rate from the maturity structure

From R1 (per-line outstanding, coupon, maturity): build the redemption schedule. Each year, the maturing fraction rolls into new issuance at the scenario market rate; the implicit rate is the coupon-weighted blend of surviving old lines and accumulated new issuance. Inflation-indexed lines (OATi/OAT€i) are a named simplification at M0: either modelled with the scenario inflation path or carried at a stated fixed real coupon — decide at recon, record the choice as a D-entry, banner it either way.

New borrowing (the running deficit) also enters at the scenario rate. BTF (short) vs OAT (long) split: use the AFT-published issuance structure, held fixed as a scenario default with its name shown.

**Kill tests (the three questions apply — what implementation would fail this check?):**
- Zero-rollover, zero-deficit scenario → implicit rate constant forever. An implementation that leaks the market rate into a frozen stock fails here.
- Instant-full-rollover scenario → implicit rate equals market rate in year 1.
- Market scenario == current implicit rate → interest charge in year 1 ≈ the R2 anchor (tolerance measured at implementation, recorded with `binding`, never a shared constant).
- Redemption schedule sums to the manifested stock (relative tolerance measured, float32 lesson applies).

### §3.3 What the debt tool refuses

- **No path without a named spending scenario** (§3.5). Guard + kill test.
- **No probability language.** Scenarios are scenarios. The fan is a scenario grid crossed with the behavioural band and macro fan of the reform — decomposed, each slice labelled with its source (mechanical / band / fan / scenario). Never a confidence interval, because nothing here has a probability model.
- **Horizon cap.** Chosen and recorded at M0 (suggested: 10 years). Beyond it, refusal: « au-delà de l'horizon, l'arithmétique est exacte et vide ». The aged/frozen discipline from F3 applies to the receipts feeding p_t: the aged barème is the default display, the frozen one is shown beside it.
- **Vintage refusal** on any comparison of projected receipts to future-year documents: « non comparable » before any gap is computed (F3 rule, unchanged).

### §3.4 Reforms → primary balance

A scenario bundle (any mix of A and B instruments) produces Δreceipts and Δprestations through the existing engines: mechanical exact, behavioural band, macro fan (Mésange multipliers are net of imports — the leakage double-count is on the record; do not re-add it). The mapping to p_t states its base year and uprating (F3 machinery reused: uprate, never re-synthesise; two indices; legislated/reconducted basis from the tree walk). Double-entry identity runs on every bundle before it touches the debt path.

### §3.5 The spending scenario — guard, not footnote

Named scenarios shipped at M1 (each one line of arithmetic on the aggregate spending path, never a spending microsimulation — we do not have one and do not pretend to):

- « Dépenses constantes en % du PIB » (spending grows with nominal GDP)
- « Dépenses gelées en volume » (spending grows with the price index only)
- « Trajectoire personnalisée » (user sets a growth rate)

The renderer REFUSES a debt path when the scenario object is absent — not a default silently applied: the API errors, the UI forces the choice and displays the name on the chart itself (not a tooltip). **Kill test:** render call without spending scenario → named refusal; and a UI-level test asserts the scenario name appears in the rendered chart title/legend. Additionally the chart carries the standing banner: « les dépenses publiques (~57% du PIB) ne sont pas microsimulées ici ; seule la tranche transferts l'est ; ce panneau est un scénario comptable ».

### §3.6 Decomposition display

Every debt fan renders its decomposition: the mechanical path (all bands at center, scenario fixed), then the band envelope, then the macro fan envelope, then the scenario grid as separate labelled lines — so a user can see WHICH uncertainty dominates. This is the same discipline as the CICE fan display, extended.

---

## §4 The objective explorer — « peut-on réduire la dette ? »

### §4.1 What it does

Generalizes the D-078 inverse solver from one knob to bundles. Input: a target on a **mechanical-layer scalar** (e.g. Δreceipts ≥ +30 bn; primary balance ≥ x% by year T under named scenarios) plus constraints (per-instrument bounds; optionally distributional constraints evaluated on the population layer for A-instruments — e.g. « decile 1–3 net loss ≤ 0 », which is mechanical and therefore admissible). Output: candidate bundles, each rendered through the FULL honesty stack — mechanical Δ, band, fan, grades, double-entry check, aged AND frozen displays, debt path under named scenarios.

### §4.2 The refusal that makes it honest

The solver's objective/constraint vocabulary is an **allowlist of mechanical-graded scalars**. Submitting a banded or fanned quantity as target or constraint (« maximize employment », « minimize behavioural loss », « target debt/GDP including macro feedback ») → named refusal explaining the layer rule. Bands and fans are applied to candidates AFTER search, as stress — a candidate whose band straddles zero on the target is flagged « fragile », prominently.

**Kill tests:** banded target → refusal fires (prove it); a hand-built case where the mechanical optimum is band-fragile → the fragile flag renders. The refusal reuses/extends `refuse_banded` — and inherits its repaired denylist→allowlist history; the new surface gets its own tests, not inherited confidence.

### §4.3 Search that can be audited

Deliberately dumb: seeded grid/greedy/coordinate search over discretized knob ranges, iteration log persisted, re-runnable to identical output. No black-box optimizer, no gradient magic — auditability outranks optimality, and the honest claim is « voici des candidats », never « voici l'optimum ». Anti-fooling rule, displayed and tested: **a plan that closes the gap only in the frozen display is not a plan** — candidate evaluation runs on the aged barème by default.

### §4.4 Worked example (DoD item)

One end-to-end example on the record in docs: target « +20 bn de recettes mécaniques », bounds ±2 points on each of ~10 instruments, showing candidates, fragility flags, the debt-path consequence under two spending scenarios, and the double-entry ledger. Chosen for pedagogy, not advocacy; the doc states it is an illustration of machinery, not a recommendation.

---

## §5 The reindustrialization panel

### §5.1 What it is, and the refusal that defines it

An honest instrument panel, not an outcome model. It answers: **what does this scenario do to the tax burden on production, on which sectors, compared to whom, and what does the evidence say firms did last time?** It refuses to answer: « combien d'usines ? », « combien d'emplois industriels ? ». The refusal is rendered, not silent — a permanent panel banner: « ce panneau chiffre des instruments et des compositions ; il ne modélise pas la transformation structurelle de l'économie ». A structural transformation claim would require a model class (dynamic firm location/entry) whose honest uncertainty band, at country scale, spans sign — banded-or-absent says: absent.

### §5.2 Contents

- **Burden metric:** taxes on production (D.29-aligned aggregate over the priced instruments: CVAE, CFE-in-scope, C3S, taxe sur les salaires, versement mobilité, TASCOM, …) as % of value added, total and by sector where the instrument engines carry sector (cells engine carries sector for A-instruments; B-instruments enter at national level with their sectoral composition STATED from published data where available, labelled composition-not-incidence).
- **Benchmark:** France vs Germany (and EU where the manifested Eurostat file supports it) on D.29/VA — measured from R8, vintage stated, perimeter differences between national D.29 and our priced aggregate stated explicitly (they will not coincide; the gap is displayed, not hidden — a comparison that is correct only because perimeters were silently aligned is not correct).
- **Scenario view:** any §2/§4 scenario re-renders the burden metric and the benchmark gap. First-round sectoral composition through the existing IO layer (Phase 4 machinery, its provenance and its incident history — no leakage re-add).
- **Evidence bands:** the response of investment/employment to production-tax changes, as evidence rows. The anchor row is the **C4 zero-band**: the IPP evaluation of the 2021 production-tax cut (~10 bn €/yr) found no detectable investment response — this row renders ON the panel whenever a production-tax instrument moves, with its grade. Other rows (energy-cost elasticities for electro-intensives, labour-cost at the SMIC vs above) enter only through the evidence-season format with source/population/identification/grade. No row → « aucune réponse modélisée », never an invented elasticity.

### §5.3 Kill tests

- Production-tax cut scenario → panel renders the C4 zero-band row and the no-factories banner (test asserts presence of both).
- Benchmark render with mismatched vintages between the France aggregate and the Eurostat file → vintage refusal fires.
- A sector query against a B-instrument → composition-not-incidence label present, incidence claim absent.

---

## §6 Validation and backtests

Grading discipline unchanged: tolerances are measured properties recorded per-case with `binding`, pre-registered via git history (`verify_tolerance_unchanged` pattern — commit = pre-registration). A backtest that admits everything measures nothing; each case below states what outcome would count as failure BEFORE it runs.

### §6.1 Debt identity backtest, 2019 → 2025 [M1 DoD]

All inputs realized and published: annual b, r (implicit: charge/stock), g, p, and realized SFA (INSEE/Eurostat). Feed 2019 initial conditions + realized inputs through §3.1 and compare the b path to the published path year by year. Because the identity is arithmetic, the residual isolates data/perimeter errors — expected near zero, and precisely BECAUSE of that, the dangerous-residual rule applies: a small residual must be decomposed (mechanical before economic: perimeter, vintage, SFA booking) before it is celebrated. Failure = any year off by more than the pre-registered tolerance with no named mechanical cause.

### §6.2 An accise episode [M2 DoD]

Tobacco 2018–2020 (the €10/pack trajectory): known rate path, published receipts and volumes. Run the mechanical re-pricing + the evidence band; grade containment like CICE (does the band contain the realized receipts delta, and where is the median?). Pre-register: mechanical-only is EXPECTED to overpredict receipts (demand fell) — the interesting graded claim is the band. If no defensible elasticity row exists at implementation time, the case still runs and the mechanical miss is displayed as the demonstration of why the band matters.

### §6.3 A TVA episode [M2, best-effort]

The Jan 2014 19.6→20 / 7→10 change, receipts vs predicted, with the comparator vintage and perimeter rules in force (both incidents' worth of scar tissue applies). If the base-vintage data for 2013 cannot be manifested cleanly, record the attempt and the refusal — « non comparable » is an acceptable graded outcome; a forced comparison is not.

### §6.4 Chiffrage crosschecks [M3]

Each new B-instrument whose re-pricing has an official costing analogue (Voies et Moyens tome II for the niches-adjacent ones; PLF évaluations préalables for rate changes) gets a comparison with vintage/perimeter stated. Divergences get the four-step treatment: mechanical explanation first, red-pin if unexplained.

---

## §7 Milestones

Order is load-bearing: the spine first, breadth second, cleverness last.

- **M0 — Recon** (§1). Deliverable: docs/M0_PHASE8.md + MANIFEST entries + bucket table draft. Review gate before design freeze. Expected effort dominated by owner-network downloads.
- **M1 — Debt closure** (§3). dette/ module, AFT structure loaded, spending-scenario guard kill-tested, §6.1 backtest graded, UI fan with decomposition. DoD: all §3 kill tests seen to fire; full pass green.
- **M2 — Aggregate engine + produits tranche** (§2.2, §2.3.1). Engine + TVA + accises (énergies, tabacs, alcools, électricité/gaz) + TSN/TTF; refusal surface tested; §6.2 graded, §6.3 attempted. DoD: double-entry identity extended and tested against a broken ledger.
- **M3 — Entreprises + personnes tranches** (§2.3.2–3). Taxe sur les salaires, versement mobilité, DMTO, petites taxes; TH RS/TF per recon verdict; CIR gate resolved (priced-with-banner or D). §6.4 crosschecks. COVERAGE_INSTRUMENTS.md rendered against the Voies et Moyens universe (§2.4).
- **M4 — Objective explorer** (§4). Generalized solver, allowlist refusal kill-tested, fragility flags, worked example doc.
- **M5 — Reindustrialization panel** (§5). Burden metric, benchmark, C4 zero-band rendering, §5.3 kill tests.
- **M6 — Consolidation.** Guards sweep over everything new (three questions applied instrument by instrument, findings logged), docs current (STATE_AND_NEXT.md rewritten), `make full` green with the pass logged, reviewer verdict appended.

Each milestone ends with a report to the reviewer in the established format: what was built, what diverged from spec (with D-entries), what is red and why it is allowed to stay red.

## §8 Interrupts, fences, and owner gates

- **PLF 2027 interrupt (early October) outranks everything in this phase.** When it lands: S4 runbook, triage harness, pre-registered tolerances. Phase 8 work parks mid-milestone if needed; the parking state is recorded.
- **Phase 7 runs in parallel** and owns the population-calibration files; Phase 8 does not touch population/calibrate.py or the L1–L6 lever files. Any Phase 8 need discovered there becomes a note to the reviewer, not an edit.
- **Dormant ERFS interrupt** unchanged: if access arrives, PHASE1C_ERFS.md wakes with priority over M3–M5.
- **Owner-gated, unchanged:** publication/deployment (input-hardening precondition stands — the path-traversal finding), CAF crosscheck execution, upstream dossier, licence posture (AGPL-3.0-or-later inherited). Nothing in Phase 8 publishes anything.
- **Fan-outs remain unreliable-by-default** (two stall incidents): recon may use parallel agents to LOCATE sources, but every located file is verified and manifested serially, and no located figure enters code except through a file (D-026).

## §9 Expected D-entries (non-exhaustive; reality will add more)

- Threshold for the §2.4 coverage universe (the Voies et Moyens cutoff) and the resulting bucket table.
- OATi/OAT€i treatment choice (§3.2).
- BTF/OAT issuance-split scenario default.
- Horizon cap and the per-year display convention.
- SFA default and its banner text.
- Spending-scenario set (names, arithmetic, default-refusal behaviour).
- Aggregate-engine refusal allowlist (exact query classes refused, per instrument).
- Per-instrument receipts anchors (year, source, sha256) — one entry per manifested anchor or a grouped entry referencing MANIFEST.
- CIR gate verdict; TH/TF recon verdict; every C→B or C→D conversion.
- §6 tolerances with `binding`, pre-registered by commit.
- Explorer target/constraint allowlist v1.
- Benchmark perimeter statement (our priced aggregate vs D.29).

## §10 Standing rules, bound by reference

Everything in docs/REVIEW_2026-08-29.md and DECISIONS.md remains in force without restatement; the ones this phase leans on hardest: the three questions; guards ship with kill tests that have been seen to fire; refusals are allowlists; update() never creates; read-backs compare against independently-constructed expectations (D-042); double-entry identity on every reform run; comparator vintage & perimeter always stated; a comparison correct only because one side is zero is untested; a residual small enough to feel like validation is the most dangerous size; a backtest that admits everything measures nothing; calibration inputs via files only (D-026); mechanical before economic; codes not labels; phantom check; pointer rule; anchors measured-before-written or UNMEASURED; measurement infrastructure gets model-code rules; tolerances are measured (relative, absolute) pairs with `binding`; the calibration ledger (spent margins never validate); banded or absent, never confidently wrong; cell-bound uncertainty over invented density; uprate never re-synthesise; vintage refusal before gap evaluation; aged/frozen always shown — « cette loi, sur la France d'aujourd'hui, avec l'argent de demain ».

— end of spec —
