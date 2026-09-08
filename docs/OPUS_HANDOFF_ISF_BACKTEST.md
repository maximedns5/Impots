# Handoff prompt — the ISF-2017 backtest (Phase 5's last piece)

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are closing **Phase 5 (patrimoine)** of the Impôts project. M5 shipped as
`a576773` (925 passed); the phase is complete except its real out-of-sample
test — the ISF-2017 backtest — which the previous session rightly refused to
fake for lack of data. **The data has now been located, read and confirmed by
the reviewing session.** Read the last addendum of
`docs/REVIEW_2026-08-29.md` first; every instruction below comes from it.

## A. The backtest — this session's centrepiece

**Source, confirmed**: IPP Rapport n° 46 (octobre 2023), *Le plafonnement de
l'impôt sur la fortune* —
`https://www.ipp.eu/wp-content/uploads/2023/10/Rapport_IPP_46_ISFplaf-2.pdf`.
**Table 1.1, page 17** carries ISF 2017 by tranche (1.3–2.57 M / 2.57–10 M /
10–50 M / >50 M): redevable counts, share of capped households, and ISF
**both pre- and post-plafonnement**. Built on POTE + déclarations ISF via
CASD, published as aggregates — the exact mode this project runs on.

Method, in order:

1. **Manifest the PDF** into `data/raw/` (sha256, URL, date, licence note).
   Sweep the companion Rapport n° 47 (ISFcrea) into the manifest while
   there — it is the ISF→IFI evaluation and may serve later lines.
2. **Read Table 1.1 from the file yourself** (D-026 — no agent prose;
   the pdf tooling reads pages directly). Record the comparator vintages
   the report itself states: 2017 declarations, 2016 reference income —
   and reconcile that convention explicitly with our simulated year before
   comparing anything (the comparator-vintage rule has been the entire
   error four times).
3. **The design, sharper than IFI's**: per tranche, our
   `isf_ifi_avant_plaf` under 2017 ISF parameters against the published
   pre-plafonnement ISF, and `isf_ifi` against post — the **plafonnement
   machinery itself is tested per tranche**, on the mechanism the report
   studies (72.54 % of >50 M households capped is the headline figure to
   reproduce or miss legibly).
4. If the table lacks a per-tranche base column, apply the **D-078
   inversion verbatim**: implied mean base must land inside its own
   tranche; the shortfall must carry the sign the ISF-era réductions
   (dons, PME) predict. Both properties are falsifiable; that is why they
   are the design.
5. **The composition band meets its only genuine check here**: the
   856–963 bn range must be confronted with what the 2017 tranches imply.
   Containment or miss, the result is recorded either way — and a miss
   gets a mechanical explanation attempt before any economic one, per
   standing rule. Do not tune anything to pass; nothing in this module is
   calibrated and the reconciliation says so.

## B. Behind it, if the session has room (check status first — some may
have landed in M4's pre-flight)

The prestations §B leftovers in their ordered form: the 2015
AF-modulation backtest (published costings exist), worked-example goldens,
the remaining UI knobs. And confirm the narrative sweep and the
name-the-failing-implementation audit actually landed as the M4 pre-flight
ordered — if not, they come before everything.

## C. Operational posture on fan-outs (now explicit project law)

Fan-outs are unreliable-by-default for load-bearing work: two incidents on
record (D-023: 6 of 11 returned; the source hunt: six of seven stalled,
verification never ran). Prefer few agents; run adversarial verification as
its own separate step, never a tail of the same workflow; hand-re-verify
any result that arrives unverified; never let a fan-out be the only path to
a load-bearing fact. For this session's centrepiece no fan-out is needed at
all: one PDF, read directly.

## D. Boundaries

The Zucman floor stays closed (reopens only on a published source above the
IFI tranches' ceiling). CAF cross-check, ERFS, the upstream draft's three
answers, all of publication: the owner's, untouched. ERFS interrupts
everything on arrival — its acceptance test is unchanged. Reality beats
this brief, on the record — D-entries as always.

When the backtest is recorded, Phase 5 closes, and the project returns to
the owner's fork: trajectories, deeper coverage, or the steady-state
charter. That choice is not this session's to make.
