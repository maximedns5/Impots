# Handoff prompt — Phase 0 build

Paste everything below this line into a fresh session pointed at the `Impots/` folder.

---

You are implementing **Phase 0** of the Impôts project: a household-level French
tax calculator (one household, any reform, exact numbers) on top of
openfisca-france. This repo already contains a scaffold and, crucially,
**`docs/PHASE0_SPEC.md` — read it in full before writing any code.** It is a
complete build brief in which every code pattern, variable name, parameter path,
timing and golden value marked [VERIFIED] was actually executed against
openfisca-france 176.0.8. Do not re-derive those from memory; your training
data about OpenFisca variable names is unreliable (`irpp` and `prime_activite`
no longer exist — the spec has the correct names).

Working rules:

1. **First action**: create a venv, `pip install -e .[dev]` (add the spec §1
   pins to pyproject.toml first), then run `python scripts/verify_openfisca.py`.
   Do not proceed until it prints "All Phase 0 engine assumptions hold."
2. Build in milestone order M0 → M4 (spec §8). Do not start the UI before the
   engine's golden tests are green.
3. When the spec and reality disagree, reality wins — but record the
   discrepancy in `docs/DECISIONS.md` (spec §9) rather than silently adapting.
4. Anything the spec lists as out of scope (§0) stays out, even if easy.
5. Every amount shown to a user follows the sign convention in spec §3.3, and
   the UI ships with the honesty banner in §5 — it is not optional copy.
6. Definition of done is the 5-point list in spec §0; end by verifying each
   point explicitly and appending decision-log entries D-002 and D-003.

Deliverables: `src/impots/engine/`, `src/impots/api/`, `ui/index.html`,
`tests/` (golden YAML + pytest), `.github/workflows/test.yml`, updated README
quickstart. All of it stays in this repo.
