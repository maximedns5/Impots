# M1 — The macro parameter fan-out

**Date**: 2026-09-03 · **Gate**: PHASE4_SPEC.md §2 · **Reproduce**: `pytest tests/test_macro_parameters.py`
**Status**: sources located and parsed; **the independent adversarial pass has not run, so the store loads nothing.** Three rows sourced, five rows dead.

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

## 4. Revenue-GDP elasticity: 1.07, and a refusal that came with it

HCFP, *L'élasticité des prélèvements obligatoires au PIB*, note méthodologique
n° 2023-1, février 2023, Tableau 2 p. 7, équation (2): **1.07** over 1991–2021, R² 0.88,
"toutefois statistiquement non différente de l'unité". The band [0.98, 1.16] is derived
from the published t-statistic of 24.68 (σ = 0.0434, ±2σ) and contains equation (1)'s
1.01 — a derivation, flagged as one, and first on the list for the adversarial pass.

The same document **forbids** something the spec would have allowed. §1 makes cycle
state a toggle on the multipliers, and it would be natural to vary the revenue
elasticity with it too. HCFP tests exactly that (tableau 4) under three definitions —
output gap, nominal growth, real growth — and finds none significant. The one detectable
regime (0.92 below 1.6 % growth, 1.1 above) is "à la limite de la significativité au
seuil de 5 %" and "pourrait même être rejetée". Making this row cycle-dependent would
promote noise to a parameter. Recorded as a removed row.

## 5. What is dead, and what dies with it

| Row | Why | What stops working |
|---|---|---|
| `multiplier_slack_state` | Mésange is linear; the literature is openly split (Auerbach-Gorodnichenko up to 2.5 in recession, Ramey-Zubairy below unity regardless of slack) | nothing — §1 already required cycle state to be a **scenario, user-visible, never estimated**. The fan does not draw on this dimension; it computes at a stated state. |
| `multiplier_confidence_band` | Mésange publishes no interval, and its own sensitivity analysis (§4.4, four hypothesis sets) is **degenerate at one year** — 1.31 everywhere for public investment, −0.32 everywhere for VAT. The only movement is employer contributions under a Phillips curve (0.29 vs 0.20). | **B3 has no sourced width.** A credible band is cross-model dispersion and needs a meta-analysis this repo does not have on disk. This is the open blocker for M3. |
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

## 7. Open

* The independent adversarial pass on the three sourced rows.
* A cross-model dispersion source for the multiplier band — the M3 blocker.
* ERFS remains the interrupt that outranks all of this.
