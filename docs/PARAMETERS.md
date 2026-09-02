# Behavioural parameters — SUPERSEDED

> **This file is a historical record. Do not seed anything from it.**
>
> The sole source of truth for behavioural parameters is
> `src/impots/behavioural/parameters/`, where every row carries its primary
> source, its support bound and a verifier's verdict, and where the loader
> refuses anything unverified.
>
> This table was compiled by hand in August 2026 and the Phase 3 verifier
> fan-out found it wrong in ways that matter (D-031):
>
> * **ETI, all — 0.05.** The paper says **0.02**, stable across six
>   specifications. 0.05 appears in none of them.
> * **Labour supply, intensive 0.10 and extensive 0.30.** Bargain-Orsini-Peichl
>   reports France disaggregated by sex and marital status — eight values running
>   0.02 to 0.145. These two scalars are averages the paper never states, and
>   both rows were removed rather than repaired.
> * **Employer contributions → wages, unlinked — 0.15.** The estimate is **0.0**.
>
> The rows below that survived verification live in the YAML store with their
> corrected values, and several corrections went further than the value: the
> top-decile ETI's support bound was a *cumulative* multi-year change where the
> estimator uses one-year differences, which halved what this project may call
> "in-support".
>
> Kept because the compilation errors are themselves evidence — about how a
> plausible-looking table of numbers survives review until something goes to the
> primary source.


Central value, sampling range, confidence. L3 samples over the range; it never
uses the central value alone.

| Parameter | Central | Range | Confidence | Source |
|---|---|---|---|---|
| ETI, all | 0.05 | 0.00–0.15 | high | Cabannes-Houdré-Landais |
| ETI, top decile | 0.30 | 0.15–0.50 | medium | ibid. |
| ETI, capital income | 0.90 | 0.70–1.20 | high | Lefebvre-Lehmann-Sicsic |
| Labour supply, intensive | 0.10 | 0.05–0.25 | medium | Bargain-Orsini-Peichl |
| Labour supply, extensive | 0.30 | 0.15–0.50 | medium | ibid. |
| Dividend response (owner-managers) | 3.0 | 2.5–4.2 | high | IPP, PFU 2018 |
| Wealth tax, real elasticity | 0.05 | 0.00–0.15 | high | Garbinti et al. |
| Wealth tax, reporting elasticity | 0.55 | 0.30–0.80 | high | ibid. |
| Employer contributions -> wages, benefit-linked | 1.00 | 0.90–1.05 | high | Bozio-Breda-Grenet |
| Employer contributions -> wages, unlinked | 0.15 | 0.05–0.20 | high | ibid. |
| Employment elasticity to labour cost at SMIC | -0.25 | -0.20 to -0.35 | high | Bunel-L'Horty |
| Corporate tax incidence on workers | 0.50 | 0.35–0.65 | medium | Fuest-Peichl-Siegloch |
| Production-tax cut -> investment | ~0 | not distinguishable from 0 | contested | IPP report 60 |
| VAT pass-through (cuts) | 0.40 | 0.20–0.60 | medium | Carbonnier |
| Energy demand, transport | -0.40 | -0.30 to -0.50 | high | Douenne-Fabre |
| Fiscal multiplier, spending | 1.00 | 0.50–1.20 | medium | OFCE |
| Fiscal multiplier, tax | 0.40 | 0.20–0.60 | low | OFCE, inferred |
| Top-earner migration | 0.05 | 0.00–1.00 | low | no French estimate exists |
