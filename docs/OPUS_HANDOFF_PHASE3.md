# Handoff prompt — Phase 3 build

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are implementing **Phase 3** of the Impôts project: the behavioural layer —
every headline number gains an evidence-based band, plus the chiffrage backtest
suite and population-scale EMTRs. Phases 0–2 are built; reviews and D-000..D-028
are accepted decisions.

**Read `docs/PHASE3_SPEC.md` in full first.** This phase's discipline differs
from 1 and 2: there is no new engine surface to verify — the risk lives in the
PARAMETERS, so §2's verifier fan-out (the D-025 machinery, D-026 binding) is
milestone M1 and gates everything: no unverified elasticity ever loads, and a row
that dies under verification is removed, with its channel narrowing visibly.

Working rules:

1. First actions: full suite green; read docs/PARAMETERS.md and treat every row
   as unverified input; then M0 → M5 in order.
2. Layer boundary is absolute: nothing in engine/, population/ or entreprises/
   learns about behaviour. The mechanical number never changes — regression-test
   that claim.
3. Channels fail loudly on missing inputs (the computed-then-dropped lesson).
   A knob without a channel yields "mechanical only — no evidence-based channel",
   never an implicit zero.
4. The applicability grade (§4) is enforced in code, thresholds in the store.
   No confident band outside historical support, ever.
5. Chiffrage cases: sources adversarially checked (D-026); a red case is a
   finding to write up, never a number to tune away. Mechanical-before-economic
   applies to backtest misses too.
6. The ERFS interrupt rule outranks every milestone. Reality wins over this spec,
   on the record — D-029..D-032 plus whatever you find.
7. Out of scope stays out: no macro/GE, no indirect taxes, no capital-income
   channels until ERFS (say why in the UI), no multi-year dynamics.

Deliverables: src/impots/behavioural/ (store, channels, mc, grading), EMTR
machinery + cached artifacts, tests/chiffrages/ populated and in CI, API/UI band
exposure, updated README, decision log.
