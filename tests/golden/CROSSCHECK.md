# Cross-check against the DGFiP simulator

`tests/golden/*.yaml` proves the wrapper reads openfisca-france consistently. It
cannot prove openfisca-france is right. This file is where that second question
gets answered, by a human, against the tax administration's own calculator.

**Status: DONE — 2026-08-29. Both cases agree with the DGFiP simulator to the euro.**

Method: run against the official simulator (simulateur-ir-ifi.impots.gouv.fr,
"Calcul de l'impôt 2025 sur les revenus 2024", modèle simplifié — the 2025 build
computes client-side in `calc.js`), driven through the browser by the reviewing
Claude session with Max present; the arithmetic is DGFiP's own, so the check's
independence from OpenFisca holds. Intermediate figures recorded below for
future localisation of any drift.

It stays a blocker for *publication*, not for development (Phase 1 spec §0.5, P2):
Phase 1 work proceeds, but no public claim of correctness is made until a human
has done this. Do not fabricate the numbers.

Unaffected by D-011. That decision re-anchored three golden values, all of them in
the benefits block. The two figures below are income tax and revenu fiscal de
référence, which are assessed on the year itself and did not move by a cent.

## Why it matters

A golden test that agrees with the engine will keep agreeing with the engine
after both drift away from the law. The DGFiP simulator is independent of
OpenFisca, so it is the only check here that can catch a systematic error rather
than a regression. Doing it once, by hand, is worth more than any number of
self-consistent assertions.

## How to run it

1. Go to **impots.gouv.fr → "Simulateur de l'impôt sur le revenu"**, and pick the
   **modèle simplifié**.
2. Year of income: **2024** (tax assessed in 2025).
3. Enter the **`salaire_imposable`** figures below — *not* the gross salary. The
   DGFiP simulator expects the amount pre-filled on a French tax return, which is
   salary after employee contributions and deductible CSG. That is exactly what
   our `salaire_imposable` row reports, which is why the comparison is meaningful.
   Do **not** enter the brut: the two calculators would then be answering
   different questions and any agreement would be luck.
4. Take the result before the prélèvement à la source and before any reduction or
   credit — the figure the simulator labels *impôt sur les revenus*.
5. Record it below, with the date and the simulator's own version string if it
   shows one.

## The two cases

### `single_30k`

One adult born 1990, no children, no other income.

| Field | Value to enter |
|---|---|
| Situation de famille | Célibataire |
| Nombre de parts | 1 |
| Salaires (case 1AJ) | **24 603 €** |

| | Amount |
|---|---|
| Our engine, `ir` | **812 €** |
| Our engine, `revenu_fiscal_reference` | 22 143 € |
| DGFiP simulator | **812 €** (RFR 22 143 €; droits simples 1 171 €; décote 359 €; parts 1; TMI 11 %) |
| Difference | **0 € on IR, 0 € on RFR** |

### `couple_70k_2kids`

Two adults born 1985 and 1987, married or pacsed, two children born 2015 and
2018, no other income.

| Field | Value to enter |
|---|---|
| Situation de famille | Mariés ou pacsés, imposition commune |
| Personnes à charge | 2 enfants |
| Nombre de parts | 3 |
| Salaires déclarant 1 (case 1AJ) | **36 899 €** |
| Salaires déclarant 2 (case 1BJ) | **20 502 €** |

| | Amount |
|---|---|
| Our engine, `ir` | **1 274 €** |
| Our engine, `revenu_fiscal_reference` | 51 661 € |
| DGFiP simulator | **1 274 €** (RFR 51 661 €; droits simples 1 889 €; décote 615 €; parts 3; TMI 11 %) |
| Difference | **0 € on IR, 0 € on RFR** |

## Reading the result

* **Within a few euros** — expected. The two calculators round at different
  points and the DGFiP one applies the arrondi à l'euro le plus proche at a
  different stage. Record the figures and move on.
* **Tens of euros** — investigate. The usual suspects are the décote, the
  plafonnement du quotient familial, and the 10 % abattement hitting its floor or
  ceiling. Compare `ir_avant_reductions` (our `ir_plaf_qf`) rather than the final
  figure to localise it.
* **Hundreds of euros, or a different number of parts** — stop and write it up in
  `docs/DECISIONS.md` before touching any golden value. A gap that size means the
  household is not being modelled the way the form models it.

## What this cross-check deliberately does not cover

The benefits block. `af`, `ppa`, `rsa` and `aide_logement` have no equivalent in
the DGFiP income-tax simulator, and their reference-period defect is documented
separately in `docs/DECISIONS.md` D-005 — do not treat agreement on income tax as
evidence about them. The CAF simulator would be the corresponding check, and it
is a Phase 0.5 task.
