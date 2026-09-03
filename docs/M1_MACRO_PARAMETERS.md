# M1 — The macro parameter fan-out

**Date**: 2026-09-03 · **Gate**: PHASE4_SPEC.md §2 · **Reproduce**: `pytest tests/test_macro_parameters.py`
**Status**: **verified 2026-09-03** (ten adversarial verifiers, ref `wf_8caa3e5e-1e6`). One row returned WRONG and is dead; four returned SCOPE_PROBLEM and load with their scope repaired. 113 findings; the corrections are in §9.

The spec asked for four parameter families and warned that its own seeds were
reviewer-compiled and suspect by precedent. They were. Two of the four families have a
good French primary source, one has a source that says something narrower than the spec
assumed, and one has no French source at all for the object requested.

## 1. Where the spec's seeds landed

| Spec's seed | Measured against the source | Verdict |
|---|---|---|
| tax-side **0.2–0.6** | Mésange tax-side variants: **0.20–0.51 at one year**, **0.72–0.90 at three** | a year-one range wearing no horizon |
| spending-side **0.5–1.2** | **0.78–1.38**; public investment is 1.31 at one year, 1.38 at two | ceiling excludes its own most important case |
| **1.3–2.5 in slack** | Mésange is linear and has no cycle state | **no source — row dead** |
| MPC by income position | French evidence measures propensity out of **wealth** | **wrong object — row dead** |

Neither multiplier seed is a lie; both are the kind of half-remembered summary that
stops being true the moment someone attaches it to a horizon. `eti_all` was killed at
2.5× its true value by the same mechanism, and the precedent is why these were checked
rather than loaded.

## 2. The source that carries the layer

`insee_G2017-04_mesange.pdf` — Bardaji, Campagne, Khder, Lafféter, Simon et al., *Le
modèle macroéconométrique Mésange : réestimation et nouveautés*, INSEE Document de
travail G2017/04 / DG Trésor, mai 2017. Section 4, "Principales variantes", p. 100–139.

Mésange is the quarterly model INSEE and the DG Trésor maintain jointly — the official
French answer to "what does this instrument do". It publishes, for a permanent
1-point-of-GDP shock on each instrument, the response of GDP, consumption, investment,
household income, employment and the primary balance at 1, 2, 3, 5 and 10 years and in
the long run.

**GDP response per point of GDP of expansionary impulse**, parsed from the document:

| Instrument | 1 y | 2 y | 3 y | 5 y | 10 y | LT |
|---|---:|---:|---:|---:|---:|---:|
| Investissement public | 1.31 | 1.38 | 1.22 | 0.93 | 0.57 | 0.22 |
| Dépense publique générique | 0.78 | 1.06 | 1.03 | 0.86 | 0.53 | 0.16 |
| Cotisations employeurs | 0.20 | 0.55 | 0.76 | 0.97 | 1.29 | 1.73 |
| Cotisations salariés | 0.38 | 0.72 | 0.75 | 0.77 | 1.14 | 1.74 |
| TVA | 0.32 | 0.66 | 0.72 | 0.81 | 0.78 | 0.70 |
| CSG | 0.41 | 0.84 | 0.90 | 0.81 | 0.80 | 0.88 |
| Impôt sur le revenu | 0.41 | 0.83 | 0.88 | 0.81 | 0.87 | 1.05 |
| Taxe carbone | 0.51 | 0.80 | 0.75 | 0.87 | 0.86 | 0.68 |

**Market-sector employment, thousands, same shock:**

| Instrument | 1 y | 2 y | 3 y | 5 y | 10 y | LT |
|---|---:|---:|---:|---:|---:|---:|
| Investissement public | 92 | 198 | 201 | 91 | 45 | 14 |
| Dépense publique générique | 33 | 94 | 107 | 44 | −8 | −42 |
| Cotisations employeurs | 83 | 210 | 290 | 316 | 318 | 362 |
| Cotisations salariés | 25 | 119 | 204 | 262 | 306 | 363 |
| TVA | 32 | 118 | 153 | 113 | 69 | 64 |
| CSG | 23 | 105 | 166 | 167 | 151 | 161 |
| Impôt sur le revenu | 24 | 109 | 174 | 184 | 181 | 200 |
| Taxe carbone | 53 | 157 | 173 | 105 | 69 | 51 |

**No number above appears in any YAML file.** The store's table-valued rows declare
`from_source_table: gdp` and `impots.macro.mesange` parses them out of the PDF. D-026
says calibration inputs are computed from the primary file by tested code, and
forty-eight retyped figures is exactly the transcription the rule exists to prevent.
`test_the_multiplier_yaml_contains_no_multipliers` enforces it.

Two conventions travel with every value, both assumptions rather than readings:

* **Sign.** Mésange publishes some variants as a cut and others as a rise. The reader
  flips whole tables — the primary balance with the GDP row, since the convention
  reverses the *shock*, not a selection of its consequences — so a VAT cut reads +0.32
  on GDP and −0.80 on the balance. Legitimate because the model is linear; nobody
  measured whether a tax rise costs what an equal cut buys.
* **Support.** The identifying shock is exactly one point of GDP. A larger reform is an
  extrapolation of the model, not a reading of its results.

## 3. The employment linkage is better than the Okun the spec asked for

§2 asked for an "Okun-style employment-output linkage, French estimates". Mésange
supplies something strictly better: employment **per instrument**, on the same shock and
the same horizons as the multiplier it belongs to.

The difference is not cosmetic. At three years a point of GDP through employer
contributions yields 290k jobs; through generic public spending, 107k. An aggregate
employment-output elasticity applied after the fact would give both the same job content
and be wrong about one of them by a factor approaching three. The spec's row is
therefore replaced rather than filled, and the Okun search that motivated it turned up
only tertiary sources — Wikipedia and secondary summaries of Blanchard-Cohen — which
would not have passed sourcing anyway.

## 4. Revenue-GDP elasticity — **WRONG, and dead**

This row was authored at 1.07 with a band [0.98, 1.16] derived from the published
t-statistic. It went first on the list for the adversarial pass, which was right, and it
came back **WRONG** on five counts. Three are fatal:

* the `note` carried **figures that appear nowhere in the document** — "1.5 in 2017 and
  2022, 0.4 in 2023". The only published annual elasticities are Table 5 p. 14: **0.84
  (2020), 1.15 (2021), 1.48 (2022)**, and no 2023 figure can exist in a note dated
  February 2023. Those numbers came from a search-engine summary. See §9.
* **R² 0.88 was read from the wrong column.** Table 2 prints R² only for equation (1);
  the cell for equation (2) is empty, and p. 8 says R² "n'est défini que lorsque
  l'équation estimée comprend une constante". 0.89 % came from (2), 0.88 from (1).
* the band is **twenty times too narrow for its use**. σ = coefficient/t is the
  sampling error of the mean slope (±0.087 ≈ ±0.96 bn); forecast uncertainty is the
  equation's residual (0.89 % ≈ ±19.7 bn).

Two more: HCFP's preferred specification is not 1.07 alone but Table 3 equation (4),
1.05 on GDP plus 0.60 on the private wage share (regression sd 0.89 % → 0.74 %), which
is what HCFP itself applies in Table 5. And the refusal of cycle-dependence I recorded
was **backwards**: Table 4 prints 0.18** (t = 2.29), and Table 5 *applies* the cyclical
term in HCFP's own re-reading. The truth is weaker and more interesting than either
version — the effect is marginally significant and might be rejected once the
uncertainty on the 1.6 % threshold is allowed for.

**What dies with it: B3 has no revenue-feedback loop.** Δdeficit stops at mechanical
plus behavioural, and the fan does not claim to close the public balance. A correct row
needs the three-term specification with a band drawn from the residual — sourcing work
to redo, not a number to patch.

## 5. What is dead, and what dies with it

| Row | Why | What stops working |
|---|---|---|
| `multiplier_slack_state` | as posed, dead: Mésange is linear, and the literature is openly split (Auerbach-Gorodnichenko up to 2.5 in recession, Ramey-Zubairy below unity regardless) | **superseded** by `multiplier_regime_shift`, which measures the *scenario gap* rather than an estimate; see §7 |
| `multiplier_confidence_band` | as posed, dead: Mésange publishes no interval and its sensitivity analysis (§4.4, four hypothesis sets) is **degenerate at one year** — 1.31 everywhere for public investment, −0.32 everywhere for VAT | **superseded** by `multiplier_dispersion`; see §7 |
| `multiplier_impot_societes` | no corporate-tax variant in section 4 | firm-side reforms get no aggregate multiplier; they must not borrow the employer-contributions one, which runs through labour cost, not capital cost |
| `revenue_elasticity_by_cycle_state` | HCFP tests it and finds it insignificant | the revenue loop closes at one elasticity, stated |
| `mpc_by_income_position` | the French HFCS evidence (Arrondel, Lamarche, Savignac) measures propensity to consume **wealth** along the **wealth** distribution — 0.5 centime per euro on average, 11 centimes for financial wealth below the median, zero in the top decile. That is not consumption out of an increment of **income** by **income** decile. | **B1 does not differentiate the consumption impulse by decile.** It applies one bridge and says so — which §1 explicitly provided for. |

Loading the wealth propensity in place of the income one would repeat exactly the error
that killed `eti_labour_income_low_earners` in Phase 3: two different objects summed
into one channel because they share a name.

## 6. Why the store loads nothing today

Every row above carries `verdict: null`, and `impots.macro.store.load()` raises. That is
the correct state, not an oversight.

The values were located, downloaded, manifested and **parsed by code from the primary
documents** — which satisfies D-026's first half. Its second half is that agents (or
anyone) *adversarially verify what the code computed*, and no independent pass has run.
Reading my own tables back off the screen is the read-back verification D-044 already
recorded as a blind spot: a check that shares a path with the thing it checks confirms
itself.

The three rows most worth attacking, in order:

1. **the derived elasticity band** — σ from a t-statistic assumes a symmetry the paper
   never claims, and the regression's GDP is in **value**; used against a volume GDP it
   would count inflation twice;
2. **the sign convention** — every contractionary variant is reversed on a linearity
   assumption, and the VAT and carbon-tax rows depend on it entirely;
3. **"LT" is not a year** — it must never reach a dated horizon profile.

## 7. The width, found where Mésange could not supply it

The two rows below arrive unverified like the rest — §6 is unchanged by them.

Two open-access IMK meta-regressions, downloaded, manifested and parsed by
`impots.macro.imk` under the same no-transcription rule:

* **WP117** (Gechert 2013) — 104 studies, 1 069 reported multipliers;
* **WP139** (Gechert and Rannenberg 2014) — 98 studies, 1 882 observations, broken out
  by cycle regime.

| | mean | sd | cv | N |
|---|---:|---:|---:|---:|
| TAX (WP117) | 0.54 | 0.66 | **1.22** | 240 |
| GSPEND (WP117) | 1.01 | 0.78 | 0.77 | 721 |
| INVEST (WP117) | 1.36 | 0.89 | 0.65 | 112 |
| TAX (WP139) | 0.44 | 0.69 | **1.57** | 318 |
| RUP — upturn | 0.39 | 0.77 | 1.97 | 355 |
| RAV — regime not distinguished | 0.75 | 0.96 | 1.28 | 1 078 |
| RLO — downturn | **1.37** | 1.08 | 0.79 | 449 |

**The centres sit in the same region** — Mésange's year-one income tax 0.41 against TAX
means of 0.44 and 0.54, public investment 1.31 against INVEST 1.22 and 1.36. I first
wrote that they "cross-validate"; the verification refuted that for two comparisons of
three when tested against the meta mean's own standard error, and the comparison is not
homogeneous in horizon anyway (Table 1 pools one to twelve years). The agreement is
reassuring to look at and is not evidence.

**The architecture that follows**: centre from Mésange (French, official, dated, per
instrument and per horizon), **absolute** width from IMK dispersion — the standard
deviation, not the coefficient of variation. §9 explains why that changed.

**The banner's "facteur 3 à 5" is NOT a measurement**, contrary to what I first wrote
here and in D-054. See §9.

**The scope problem, which is the first thing the adversarial pass should attack**: these
dispersions are *across studies* — different countries, horizons, identification
strategies. Gechert's own conclusion is that reported multipliers vary with study design.
They are therefore not the sampling error of France's multiplier at a given horizon, and
a fan built on them is wider than the genuine uncertainty about a French reform. That is
the conservative direction, and it is a choice.

And `multiplier_regime_shift` is deliberately **not an estimator**. §1 requires cycle
state to be a user-visible scenario, never drawn. The row supplies the sourced *size* of
the gap between two displayed scenarios. It also carries a restriction the paper is
explicit about: the regime effect is found on the **spending** side, and tax multipliers
are not regime-sensitive — so applying a shift to tax instruments would contradict the
source.

## 8. Open

* The independent adversarial pass, now over **five** sourced rows.
* ERFS remains the interrupt that outranks all of this.

## 9. The adversarial pass, 2026-09-03

Ten verifiers, two lenses per row — one checking every digit against the printed table,
one attacking what the numbers are said to mean. Ref `wf_8caa3e5e-1e6`. **113 findings.**

**No transcription error, anywhere.** All 48 Mésange values, all 28 IMK columns, every
page reference: exact. The CSG/IR trap — both 0.41 in year one — is correctly passed.
Parsing from primary files by tested code did what D-026 says it does.

**Every verdict was about scope.** One WRONG, nine SCOPE_PROBLEM. The rule that a scope
problem means the citations need repair while the values hold turned out to understate
it: several repairs changed behaviour.

### What changed in the code

| Finding | Consequence |
|---|---|
| The four labour-tax variants are **non-targeted**, and the document publishes a **targeted** counterpart (encadré 14, 1–1.6 SMIC) | A ninth variant is parsed, and `shocks.targets_low_wages` routes allègements to it. Phase 3's entire allègements work would otherwise have taken the uniform multiplier and **understated employment by 39 % at three years** — 290k against 403k. The single most consequential finding. |
| The VAT shock is **1.18 pt ex ante** for 1 pt net, the state paying ~15 % of its own VAT | `VariantSpec.ex_ante_points`. A VAT reform costed gross — the usual PLF convention — took a multiplier overstated by 18 %. |
| Only the **fiscal** variants are ex ante; the two spending variants are shocks **in volume** | The support field described three lines of eight wrongly. |
| Employment is in **full-time equivalents**, not persons | The row said persons. Note `io_layer` counts *persons*, from the national accounts: two employment units now coexist in this layer and must not be added. |
| The long horizons are **specification-determined**, not measured — employer contributions run 1.73 at LT under wage-setting and 0.25 under a Phillips curve | `usable_horizons` stops at three years. Independently, §0 already refused horizons past three years; the two reasons agree. |
| `depense_publique` is a **composite**: 8 % public investment, 25 % public wages, 9 % in-kind, 12 % intermediate, **46 % cash benefits** — and overlaps `investissement_public` | Recorded, with the overlap declared in `NON_ORTHOGONAL`. It also strengthens B1's refusal to route transfers through it. |
| Its long-run employment is **−42k market but +26k total including public** | Reporting the market figure alone inverts the conclusion. |
| Simulation conditions — permanent shock, constant real rates, constant nominal exchange rates, **no endogenous policy reaction** — appeared nowhere | Now in `applies_to` and destined for the assumptions strip. |
| The dispersion **sd is nearly flat** across families (0.43–0.89) while means vary fourfold | The width is now the **absolute sd**. The coefficient of variation mostly reported the inverse of the mean, and combined with a normal law it fixed P(k<0) at 20.7 % for every fiscal lever regardless of the French centre. |
| The papers say multipliers are **"by and large not normally distributed"**, multimodal | `distribution: normal` removed. The triangular draw is now labelled a convention, not a measurement. |
| The regime effect is **additive** (RLO +0.769, se 0.143, ***) and the upswing coefficient is **not significant** (−0.049, se 0.097) | `imk.regime_effect()` parses the controlled coefficients. The ratio of raw means has no counterpart in the paper. |
| RAV is "average **or unspecified**" and RLO is "downswing **or crisis**" | Both glosses had dropped a load-bearing half. |

### The correction I owe the record

**The L4 banner's "facteur 3 à 5" is not a measured quantity.** D-054 said it was, on
the strength of RLO/RUP = 1.37/0.39 = 3.5. That is a ratio of two raw subsample means
which the same paper's controlled estimate contradicts; no controlled reading reproduces
it (2.52, 2.08 depending on specification); the denominator's coefficient is not
significantly different from zero; the authors write that κ "should not be interpreted
as the true multiplier"; and **nothing anywhere yields 5**. The banner should describe
dispersion qualitatively and stop.

### Two D-026 violations, by me, in the same sitting

Both the same mechanism, and neither caught by any existing test:

1. the elasticity row's `note` carried annual figures from a **search-engine summary**,
   not from the cited document, which prints different ones;
2. `dispersion.yaml`'s `quote:` field set a **paraphrase in quotation position**. The
   paper says "Reported multipliers vary with study-design, whose influence should be
   laid open when drawing policy conclusions"; the file printed a search result's
   rewording of it.

The pattern is exact: values were being computed from primary files by tested code
while the **prose around them** — quotes, notes, characterisations — came from wherever
was convenient, and nothing checked the prose. D-026 was being honoured in the half that
had a test and violated in the half that did not.

`test_every_quote_is_verbatim_in_its_source` now compares every `quote:` field against
its PDF letter by letter. It fails on a paraphrase and passes a real quotation through
hyphenation and ligature differences.
