# Phase 0 — The Household Calculator: Implementation Specification

**Project**: Impôts — a transparent, layered simulator of French taxation
**Phase**: 0 of 4 (see `docs/AUDIT` roadmap §09)
**Audience**: the implementing agent (Claude Opus session). This document is the complete build brief. Everything marked **[VERIFIED]** was executed against `openfisca-france 176.0.8` / `openfisca-core 44.7.0` on 2026-08-28 — reproduce with `scripts/verify_openfisca.py` before writing any other code.
**Repo root**: this folder (`Impots/`). The scaffold (pyproject.toml, src/impots/, tests/, docs/) already exists — extend it, do not recreate it.

---

## 0. What Phase 0 is

One household. Any reform. Exact numbers.

A user describes a household (adults, children, salaries, optionally housing), optionally edits tax parameters (IR barème, décote, plafond QF, CSG), and sees the exact mechanical result under current law and under their reform, side by side with the delta. No population, no behaviour, no macro — those are Phases 1 and 3. The engine is OpenFisca-France; we build a typed wrapper, a small API, and a static UI.

**Definition of done** (all must hold):
1. `pytest` green, including all golden cases in §6 at ±2 € tolerance.
2. `uvicorn impots.api.main:app` serves; `POST /simulate` answers a light-tier request in < 1.5 s warm, a full-tier request in < 6 s warm.
3. `ui/index.html` opened in a browser against the local API: a couple with 2 kids and a top-rate reform produces correct baseline/reform/delta columns.
4. The no-mutation test passes: applying a reform never changes baseline results.
5. README quickstart works from a clean `python -m venv` in ≤ 5 commands.

**Explicitly out of scope for Phase 0**: any population-level number ("this reform costs €X bn"), any behavioural response, benefits reform knobs (RSA/AF parameters), taxe d'habitation/foncière, self-employment income, capital income (PFU), deployment. Refuse the temptation.

---

## 1. Environment **[VERIFIED]**

```
python >= 3.11
openfisca-france == 176.0.8      # pin exactly; weekly releases can shift golden values
openfisca-core  == 44.7.0        # comes with the above; pin anyway
fastapi >= 0.110
uvicorn[standard]
pydantic >= 2.6
pytest, pyyaml, httpx (for API tests), ruff
```

Add these to `pyproject.toml` `[project.dependencies]` / `[project.optional-dependencies].dev`. Note: `openfisca-france` pulls numpy; do not add pandas/polars in Phase 0 — nothing here needs a dataframe.

Measured timings to design around **[VERIFIED]**:

| Operation | Time |
|---|---|
| `FranceTaxBenefitSystem()` construction | ~3.4 s (once per process) |
| Applying a parametric `Reform` | ~0.8 s (once per distinct reform) |
| Light computation (IR + salaire_net), warm process | ~0.5 s |
| Full cascade (`revenu_disponible`, all benefits), warm | ~2.3–4.8 s |
| First computation in a process (lazy warm-up) | +2 s over warm |

Consequences: the TBS is a **module-level singleton**; reformed TBS instances are **cached by reform hash**; the API **warms up on startup** by running one dummy light simulation; the UI shows a loading state because full-tier is seconds, not milliseconds.

---

## 2. Architecture

```
src/impots/
  engine/
    __init__.py
    system.py        # TBS singleton + reform cache
    situations.py    # HouseholdInput -> OpenFisca situation dict
    outputs.py       # variable registry: what we extract, entity, period, sign
    reforms.py       # ReformSpec (JSON) -> openfisca Reform subclass
    compute.py       # orchestration: compute(household, year, reform, tier, emtr)
  api/
    __init__.py
    main.py          # FastAPI app, CORS, warm-up
    schemas.py       # pydantic models (single source of truth for the wire format)
ui/
  index.html         # static, no build step, vanilla JS + fetch
scripts/
  verify_openfisca.py  # the [VERIFIED] smoke test — run first, keep green
tests/
  golden/            # YAML cases
  test_golden.py
  test_reforms.py
  test_api.py
```

The existing `src/impots/legislation|mechanical/...` packages from the scaffold: put `engine/` alongside them (it *is* the mechanical layer's household-level face; Phase 1 will reuse `engine/` verbatim over a population).

---

## 3. Engine wrapper

### 3.1 `system.py` — singleton and reform cache

```python
from functools import lru_cache
from openfisca_france import FranceTaxBenefitSystem

_TBS = None

def baseline() -> FranceTaxBenefitSystem:
    global _TBS
    if _TBS is None:
        _TBS = FranceTaxBenefitSystem()   # ~3.4 s, once
    return _TBS

@lru_cache(maxsize=32)
def reformed(reform_key: str):
    """reform_key = canonical JSON dump of a ReformSpec (sorted keys).
    Body: parse it back, build the Reform subclass (see reforms.py), apply to baseline()."""
```

Never hand the mutable parameter tree of `baseline()` to anything. **[VERIFIED]** `Reform(baseline_tbs)` clones — after applying a top-rate-50% reform, a baseline simulation still used 45% and a fresh TBS still reported `rates[-1] == 0.45`. Keep the regression test anyway (§6, `test_no_mutation`).

### 3.2 `situations.py` — building the situation dict

The four entities and their **exact** plural keys and roles **[VERIFIED]**:

| Entity | Plural key | Roles used |
|---|---|---|
| individu | `individus` | — |
| foyer_fiscal | `foyers_fiscaux` | `declarants`, `personnes_a_charge` |
| famille | `familles` | `parents`, `enfants` |
| menage | `menages` | `personne_de_reference`, `conjoint`, `enfants` |

Wiring rules:
- Every adult appears in: `declarants`, `parents`, and (`personne_de_reference` | `conjoint`).
- Every child appears in: `personnes_a_charge`, `enfants` (famille), `enfants` (menage).
- One foyer fiscal, one famille, one ménage. (Cohabiting-unmarried = two foyers fiscaux is a Phase-0.5 nicety; v1 supports single or married/pacsed couple only. Say so in the UI.)

Input variables, periods, and how to set them **[VERIFIED]**:
- `salaire_de_base` (gross salary) is a **monthly** variable. Set it per month: `{f"{year}-{m:02d}": annual/12 for m in 1..12}`. The wrapper takes annual amounts from the user and divides by 12.
- `date_naissance` is set at `"ETERNITY"`.
- For the full tier add ménage-level housing inputs: `statut_occupation_logement` (enum string, e.g. `"locataire_vide"`), `loyer` (monthly), and `depcom` or `zone_apl` if provided. These are optional; without them, aide_logement computes as 0 — the UI must label benefits as "computed from the fields you filled".

Verified minimal situation (single, 30 k€ gross):

```python
YEAR = "2024"
MONTHS = [f"{YEAR}-{m:02d}" for m in range(1, 13)]
situation = {
    "individus": {"adult_0": {
        "salaire_de_base": {m: 2500.0 for m in MONTHS},
        "date_naissance": {"ETERNITY": "1990-01-01"},
    }},
    "foyers_fiscaux": {"ff_0": {"declarants": ["adult_0"]}},
    "familles":       {"fam_0": {"parents": ["adult_0"]}},
    "menages":        {"men_0": {"personne_de_reference": ["adult_0"]}},
}
```

Public signature:

```python
def build_situation(household: HouseholdInput, year: int) -> dict: ...
```

### 3.3 `outputs.py` — the variable registry

Extract exactly these; do not free-form. **[VERIFIED]** names, entities, periods (things that look right but are wrong: `irpp` no longer exists; prime d'activité is `ppa`, not `prime_activite`; there is no `taux_marginal_imposition` variable — EMTR is computed by finite difference, §3.5).

| Registry key | OpenFisca variable | Entity | Period | Aggregation to annual |
|---|---|---|---|---|
| salaire_brut | `salaire_de_base` | individu | month | input, sum |
| salaire_super_brut | `salaire_super_brut` | individu | month | `calculate_add` |
| salaire_net | `salaire_net` | individu | month | `calculate_add` |
| salaire_imposable | `salaire_imposable` | individu | month | `calculate_add` |
| cotisations_salariales | `cotisations_salariales` | individu | month | `calculate_add` |
| cotisations_employeur | `cotisations_employeur` | individu | month | `calculate_add` |
| csg_deductible | `csg_deductible_salaire` | individu | month | `calculate_add` |
| csg_imposable | `csg_imposable_salaire` | individu | month | `calculate_add` |
| crds | `crds_salaire` | individu | month | `calculate_add` |
| ir | `impot_revenu_restant_a_payer` | foyer_fiscal | year | `calculate` |
| ir_avant_reductions | `ir_plaf_qf` | foyer_fiscal | year | `calculate` |
| parts_fiscales | `nbptr` | foyer_fiscal | year | `calculate` |
| revenu_fiscal_reference | `rfr` | foyer_fiscal | year | `calculate` |
| af | `af` | famille | month | `calculate_add` — full tier |
| ppa | `ppa` | famille | month | `calculate_add` — full tier |
| rsa | `rsa` | famille | month | `calculate_add` — full tier |
| aide_logement | `aide_logement` | famille | month | `calculate_add` — full tier |
| revenu_disponible | `revenu_disponible` | menage | year | `calculate` — full tier |

**Sign conventions** **[VERIFIED]**: `impot_revenu_restant_a_payer` and the cotisation variables come out **negative** (money leaving the household). The wire format normalises: all amounts in the API response are **positive magnitudes** with semantic direction carried by the field name; keep a `raw` passthrough only in debug mode.

**Tiers**: `light` = individu + foyer_fiscal rows only (~0.5 s). `full` = everything (~2.3–4.8 s). The famille/menage rows exist only in `full` responses.

### 3.4 `reforms.py` — the reform whitelist

`ReformSpec` (wire format) is a whitelist of named knobs, not raw parameter paths — the API must not accept arbitrary paths (that is an injection surface into the parameter tree and makes caching keys unbounded).

```json
{
  "ir_bareme": [ {"threshold": 0, "rate": 0.0}, {"threshold": 11497, "rate": 0.11},
                 {"threshold": 29315, "rate": 0.30}, {"threshold": 83823, "rate": 0.41},
                 {"threshold": 180294, "rate": 0.50} ],
  "decote_seuil_celib": 900.0,
  "decote_seuil_couple": 1500.0,
  "decote_taux": 0.4525,
  "plafond_qf_demi_part": 1600.0,
  "csg_activite_imposable": 0.024,
  "csg_activite_deductible": 0.068
}
```

All fields optional; `ir_bareme`, when present, is a **complete replacement** (2–8 brackets, thresholds strictly increasing, rates in [0,1] — validate in pydantic).

Verified parameter paths and current-law 2024 values **[VERIFIED]**:

| Knob | Parameter path | 2024 value |
|---|---|---|
| ir_bareme | `impot_revenu.bareme_ir_depuis_1945.bareme` (`ParameterScale`, 14 dated brackets; brackets [0..4] active) | thresholds 0 / 11 497 / 29 315 / 83 823 / 180 294; rates 0 / .11 / .30 / .41 / .45 |
| decote_seuil_celib | `impot_revenu.calcul_impot_revenu.plaf_qf.decote.seuil_celib` | 889 |
| decote_seuil_couple | `...plaf_qf.decote.seuil_couple` | 1470 |
| decote_taux | `...plaf_qf.decote.taux` | 0.4525 |
| plafond_qf_demi_part | `...plaf_qf.plafond_avantages_procures_par_demi_part.general` | 1791 |
| csg_activite_imposable | `prelevements_sociaux.contributions_sociales.csg.activite.imposable` | 0.024 |
| csg_activite_deductible | `prelevements_sociaux.contributions_sociales.csg.activite.deductible` | 0.068 |

Verified reform construction pattern (this exact code ran and produced the golden delta in §6):

```python
from openfisca_core.reforms import Reform
from openfisca_core import periods

def make_reform(spec: ReformSpec, year: int):
    start = periods.instant(f"{year}-01-01")

    class _R(Reform):
        name = f"user-reform-{hash_of_spec}"
        def apply(self):
            def modify(parameters):
                if spec.ir_bareme is not None:
                    bareme = parameters.impot_revenu.bareme_ir_depuis_1945.bareme
                    for i, br in enumerate(spec.ir_bareme):
                        bareme.brackets[i].rate.update(start=start, value=br.rate)
                        bareme.brackets[i].threshold.update(start=start, value=br.threshold)
                    # deactivate any remaining active brackets above the new top:
                    for j in range(len(spec.ir_bareme), 5):
                        bareme.brackets[j].rate.update(start=start, value=spec.ir_bareme[-1].rate)
                        bareme.brackets[j].threshold.update(start=start, value=spec.ir_bareme[-1].threshold)
                if spec.decote_seuil_celib is not None:
                    parameters.impot_revenu.calcul_impot_revenu.plaf_qf.decote.seuil_celib.update(start=start, value=spec.decote_seuil_celib)
                # ... same .update(start=..., value=...) pattern for every other knob
                return parameters
            self.modify_parameters(modifier_function=modify)
    return _R
```

Bracket-count subtlety: the `ParameterScale` holds 14 historical brackets; at any 2024+ instant only 5 resolve to active values. When the user supplies fewer than 5 brackets, collapse the extras onto the top bracket as shown (setting them equal to the top makes them no-ops). When more than 5: reject in validation for v1 (adding brackets to a ParameterScale is possible but untested here — do not improvise it in Phase 0).

### 3.5 `compute.py` — orchestration

```python
def compute(household: HouseholdInput, year: int,
            reform: ReformSpec | None = None,
            tier: Literal["light", "full"] = "light",
            emtr: bool = False) -> ComputeResult: ...
```

Behaviour:
1. Build situation once; build one `Simulation` on `baseline()`, one on `reformed(key)` if a reform is present. A `Simulation` is single-use per TBS — never reuse across TBS instances.
2. Extract the registry rows for the tier; normalise signs; sum individu rows across household members.
3. `delta = reform - baseline` per row (signed: positive delta on `ir` = pays more).
4. If `emtr` (full tier only): rerun baseline with `salaire_de_base` + 100 €/year on the *first* adult (spread /12), `emtr = 1 - (Δrevenu_disponible / 100)`. **[VERIFIED]**: 49.8 % for a single at 30 k€ — plausible (11 % IR bracket + employee contributions + CSG). Two extra full sims ≈ +5 s: the API only computes EMTR when asked.
5. Return timings in the payload (`build_ms`, `compute_ms`) — they feed the UI loading copy and the perf regression test.

---

## 4. API

`impots.api.main`, FastAPI. CORS: allow `*` for Phase 0 (local tool). On startup: construct `baseline()` and run one dummy light compute so the first user request is warm.

### Endpoints

**`GET /health`** → `{"status": "ok", "openfisca_france": "176.0.8", "openfisca_core": "44.7.0", "warm": true}`

**`GET /parameters/ir?year=2024`** — current-law values the UI needs to prefill the reform panel. Read from the live parameter tree (paths in §3.4), never hardcode:
```json
{"year": 2024,
 "bareme": [{"threshold": 0, "rate": 0.0}, {"threshold": 11497, "rate": 0.11}, ...],
 "decote": {"seuil_celib": 889, "seuil_couple": 1470, "taux": 0.4525},
 "plafond_qf_demi_part": 1791,
 "csg_activite": {"imposable": 0.024, "deductible": 0.068}}
```
Access pattern **[VERIFIED]**: `bareme("2024-01-01").thresholds` / `.rates` (a `MarginalRateTaxScale` — note it exposes `thresholds`/`rates` lists, *not* `.brackets`).

**`POST /simulate`**
```json
{"household": {
   "adults": [{"salaire_brut_annuel": 45000, "annee_naissance": 1985},
              {"salaire_brut_annuel": 25000, "annee_naissance": 1987}],
   "children": [{"annee_naissance": 2015}, {"annee_naissance": 2018}],
   "couple_marie_ou_pacse": true,
   "logement": {"statut": "locataire_vide", "loyer_mensuel": 900, "zone_apl": 2}},
 "year": 2024,
 "reform": { ... ReformSpec or null ... },
 "tier": "light",
 "emtr": false}
```
Response: `{"baseline": {rows}, "reform": {rows} | null, "delta": {rows} | null, "emtr": 0.498 | null, "timings": {...}, "engine": {"openfisca_france": "176.0.8"}}`.

Validation (pydantic): 1–2 adults, 0–8 children, salaries in [0, 10 M€], birth years in [1920, year], barème constraints from §3.4. Reject `emtr && tier=="light"` with 422 and a message saying why (EMTR needs the benefits cascade).

`test_api.py` uses `httpx.AsyncClient`/`TestClient` — health, one light simulate, one reform simulate, one validation failure.

---

## 5. UI — `ui/index.html`

One file, no build step, no framework. Vanilla JS, `fetch` to `http://localhost:8000`. It must work when opened as a file (hence permissive CORS).

Layout (desktop two-column, stacks on mobile):
- **Left — the household.** Adults (1 or 2, toggle "marié/pacsé"), annual gross salary each, birth-year, children with birth-years, optional housing block (statut, loyer, zone) gated behind "calculer aussi les prestations" which switches tier to `full`.
- **Left, below — the reform panel.** Prefilled from `GET /parameters/ir`. Editable barème table (rate % + threshold per row, add/remove down to 2 rows, max 5), décote fields, CSG fields. A "réinitialiser au droit courant" button. The panel starts collapsed; the tool is useful with no reform at all.
- **Right — results.** Three-column table: *Droit courant / Votre réforme / Δ*. Rows grouped: salary block (super-brut → brut → net → imposable), tax block (IR, parts, RFR), benefits block (full tier only: AF, PPA, RSA, aide logement), and **revenu disponible** as the bold bottom line. Δ coloured (more disposable income green, less red). EMTR shown as a single labelled figure when requested.
- **The honesty banner** (non-negotiable, this is the product's signature): a fixed strip above results — *"Couche mécanique (L2) : effet au premier jour, à droit constant, sans réaction comportementale. Les couches comportementale et macro arriveront en phase 3."* Grey placeholder rows labelled "L3 — réponse comportementale (à venir)" under the results table.
- Loading states: skeleton rows + the API's own `timings` for copy ("calcul complet ~3 s").
- Errors: surface 422 messages verbatim; on network failure, show the uvicorn launch command.

No chart in Phase 0 (a waterfall is Phase-0.5 polish; if added later, follow the repo's dataviz conventions).

---

## 6. Tests — golden values **[VERIFIED]**

These exact values were produced by `openfisca-france 176.0.8` on 2026-08-28. They are **regression anchors** (they pin *our wrapper + that version*), not truth claims. Tolerance ±2 €. If a dependency bump moves them, that is a finding to record in `docs/DECISIONS.md`, not silently re-anchor.

`tests/golden/*.yaml`, one file per case:

| Case | Input (year 2024) | Expected |
|---|---|---|
| `single_30k` | 1 adult (b. 1990), 30 000 € brut | `salaire_net = 23 748`, `ir = 812`, `revenu_disponible = 23 908` |
| `couple_70k_2kids` | adults b. 1985/1987, 45 000 + 25 000 €, kids b. 2015/2018 | `ir = 1 274`, `parts_fiscales = 3.0`, `af = 1 771`, `revenu_disponible = 58 182` |
| `smic_single` | 1 adult (b. 1995), 21 621.60 € brut (12 × 1 801.80) | `ir = 0`, `ppa = 2 370` |
| `single_240k` | 1 adult (b. 1980), 240 000 € brut | `ir = 59 668` |
| `single_240k_toprate50` | same + reform `ir_bareme` top rate → 0.50 | `ir = 59 868`, `delta_ir = +200` |

The last case's arithmetic is independently checkable and was checked: 240 k€ brut → ≈184 k€ taxable after the capped 10 % abattement → ≈4 k€ sits above the 180 294 € threshold → 5 pts × 4 k€ ≈ 200 €. Keep that derivation as a comment in the YAML.

Also:
- `test_no_mutation`: compute baseline; apply top-rate-50 reform; recompute baseline; assert identical to the euro.
- `test_reform_cache`: two identical ReformSpecs → same TBS object (cache hit); a differing one → different object.
- `test_perf`: warm light compute < 1.5 s, warm full < 6 s (generous bounds; they catch accidental cascade-triggering, e.g. computing `revenu_disponible` in the light tier).
- **Manual cross-check task** (documented in the test README, done by a human once): enter `single_30k` and `couple_70k_2kids` into the DGFiP simulator (impots.gouv.fr, "simulateur de l'impôt sur le revenu", modèle simplifié, using the *salaire imposable* our engine reports as the input) and record both results in `tests/golden/CROSSCHECK.md`. Expect agreement within a few euros; investigate anything larger.

CI: a GitHub Actions workflow (`.github/workflows/test.yml`) — Python 3.11, pip cache, `pip install -e .[dev]`, `pytest`. The OpenFisca install is ~1 min; cache it.

---

## 7. Pitfalls — read before coding **[all VERIFIED the hard way]**

1. **Monthly vs annual.** Salary/benefit variables are monthly; fiscal variables are annual. Use `calculate_add(var, "2024")` to annualise monthly variables; `calculate(var, "2024")` on a monthly variable raises. Set monthly inputs per-month.
2. **Signs.** `impot_revenu_restant_a_payer`, `cotisations_*` are negative. Normalise at the wrapper boundary, nowhere else.
3. **Dead names.** `irpp` is gone (→ `impot_revenu_restant_a_payer`; `irpp_economique` also exists). `prime_activite` is `ppa`. There is no marginal-rate variable.
4. **Barème indexing.** The 2024 *income* barème (voted in LF 2025) is stored at 2024 instants: `bareme("2024-01-01")` → 11 497 / 29 315 / 83 823 / 180 294. Do not add a year.
5. **`MarginalRateTaxScale` vs `ParameterScale`.** The *evaluated* scale (`bareme(instant)`) has `.thresholds`/`.rates`; the *editable* node (`bareme`) has `.brackets[i].rate.update(...)`. Confusing them is the most likely first bug.
6. **Simulations are single-use snapshots** tied to one TBS. New request → new `SimulationBuilder().build_from_entities(...)`.
7. **Cold-start.** 3.4 s TBS load + ~2 s first-compute warm-up. Warm up in the API startup hook, not on request one.
8. **Default profiles.** We set only `salaire_de_base` and `date_naissance`; everything else defaults (private-sector non-cadre employee, no other income). This is fine for v1 — but state it in the UI ("salarié du privé" assumption).
9. **Zero benefits ≠ bug.** Without housing inputs `aide_logement = 0`; a childless well-paid single gets `ppa = 0`. The golden cases distinguish these from wiring errors.
10. **Version drift.** openfisca-france releases weekly and golden values move with the law. Pin the version; bump deliberately with a decision-log entry.

---

## 8. Milestones

| # | Deliverable | Done when |
|---|---|---|
| M0 | Environment + `scripts/verify_openfisca.py` green | smoke output matches §6 values |
| M1 | `engine/` complete | golden + no-mutation + cache tests green |
| M2 | API | `test_api.py` green; warm timings within budget |
| M3 | UI | manual script: couple+2kids+top-rate-50 shows Δ ir = +200 story end-to-end |
| M4 | Polish | README quickstart verified from clean venv; CI green; CROSSCHECK.md filled |

Work in this order. Do not start the UI before M1 is green — every hour of UI work on a wrong engine is wasted twice.

---

## 9. Decision-log entries to append when done

Append to `docs/DECISIONS.md`: D-002 (Phase 0 stack: FastAPI + static HTML, no framework — rationale: solo maintainability), D-003 (pinned openfisca-france 176.0.8 + golden-value policy), plus anything you had to decide that this spec did not cover — *especially* anything where the spec turned out to be wrong.
