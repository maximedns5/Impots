# Handoff prompt — the prestations knobs (WHAT_NOW B1)

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are continuing the Impôts project. The imputation increment shipped and
was reviewed (final addendum of docs/REVIEW_2026-08-29.md — read it first;
its zero-masked-comparison sweep is your item A). This increment adds the
transfer side of the system as reform knobs: RSA, prime d'activité and
allocations familiales. It is the largest remaining item on WHAT_NOW and it
makes the tool cover both halves of French fiscal debate. The ERFS interrupt
rule stands above everything.

## A. Housekeeping first (one commit each, D-entries)

1. The zero-masked-comparison sweep the verdict orders: every reconciliation
   line, household and firm, checked for comparisons valid only because a
   model component is identically zero; component-non-zero tests or
   conditional-validity annotations per line.
2. The phantom-tree upstream issue (openfisca-france: dead
   `aide_a_domicile` tree) — file it if a prior session has not; one
   write-up, reproduction included.

## B. The build: prestations knobs

Verified anchors — checked live against openfisca-france 176.0.8 on
2026-09-04, values at 2024-01-01. Every path below still gets the full
treatment: model-source presence check (the phantom rule — the parameter
must be READ by a formula, prove it), read-back against an independent
expectation, existence-before-write, kill tests.

* **RSA** — node `prestations_sociales.solidarite_insertion.minima_sociaux.rsa`:
  `rsa_m.montant_de_base_du_rsa` = 607.75 €/month; couple/child majorations
  under `rsa_maj.maj_montant_max` (0.5 / 0.3 / 0.4); forfait logement rates
  under `rsa_fl.forfait_logement` (0.12 / 0.16 / 0.165). v1 knobs: the base
  amount and the three forfait-logement rates.
* **Prime d'activité** — sibling node `...minima_sociaux.ppa`:
  `pa_m.montant_de_base` = 595.25; **the taper** —
  `pa_m.majoration_ressources_revenus_activite` = 0.61, the single most
  policy-relevant dial in the French transfer system (it IS the
  work-incentive debate); bonification under `pa_m.bonification`
  (taux_bonification_max 0.29101, seuils 59/120 — note the seuils are in
  SMIC-hours units; label them correctly in the UI or leave them un-knobbed
  in v1). v1 knobs: base, taper, bonification max rate.
* **AF** — node `prestations_familiales.prestations_generales.af`:
  rates as BMAF fractions under `af_cm.taux` (enf2 0.32, enf3 0.41); the
  2015 **modulation** under `af_cm.modulation` (taux_tranche_1/2/3 =
  1 / 0.5 / 0.25) with income thresholds under `af_cond_ress`
  (plafond_tranche_1 74 966, tranche_2 99 922, +6 246 per extra child);
  age-14 majoration `af_maj.maj_age_deux_enfants.taux1` = 0.16. v1 knobs:
  the three modulation rates, the two plafonds, the per-child increment.
* **BMAF** — `prestations_familiales.bmaf.bmaf` = 445.93: the master scalar
  most family benefits price off. A powerful single knob; if exposed, its
  blast radius (every BMAF-linked prestation) must be stated in the UI.
* **AL is explicitly deferred** — the aides-logement barème is an order of
  magnitude more structure (zones, plafonds, R0, slopes); a v1 knob set
  would be theatre. Say so where a user would look for it.

Wiring, same as every knob increment: ReformSpec whitelist + cache keys +
verify read-backs; worked-example goldens hand-derived at one household
before population use (an RSA base change and a PPA taper change at least —
the taper golden should show the EMTR shift, which the EMTR machinery
measures); chiffrage re-sweep (revalorisation articles and the 2015 AF
modulation are now expressible — the modulation is a strong backtest
candidate with published costings); UI panel with the transfer knobs.

Watch three things:

1. **Double-entry signs.** Transfers invert the flow: a benefit increase is
   a state cost and a household gain. The identity guard must handle both
   directions — the sign-error class from the allègements increment
   (99 000 jobs "lost" from a cost cut) lives exactly here. Kill test with a
   deliberately mis-signed transfer.
2. **Behavioural honesty.** The labour-supply rows that would speak to a
   taper reform died in the Phase 3 fan-out (the BOP averages). Unless a
   verified row exists, a PPA-taper reform reports "mechanical only — no
   evidence-based channel", never an implicit response. The applicability
   machinery already does this; verify it fires, don't assume.
3. **The spending instrument.** Transfer knobs are the spending-side
   instrument `multiplier_regime_shift` has waited for. Check whether the
   fan's spending-multiplier rows survived M1 verification: if yes, wire the
   instrument class and the fan covers transfer reforms; if the rows died,
   the fan reports its coverage gap for these knobs — gracefully, per the
   M5 refusal machinery.

## C. Boundaries

No reCAPTCHA circumvention under any circumstances — the CAF cross-check
belongs to Max and stays blank until he runs it. No within-decile dispersion
invention for the global cap (verdict). No AL knobs. Benefits population
LEVELS stay under their D-015/D-011 banners — these knobs price *deltas*.
Reality beats this brief, on the record — D-entries as always.
