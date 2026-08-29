"""Population-scale engine gate for Phase 1.

Encodes the [VERIFIED] mechanics of PHASE1_SPEC.md §1 as assertions:
  - vectorised SimulationBuilder pattern (create_entities first)
  - roles are FLATTENED SUBROLE keys (silent-failure mode #1)
  - enum inputs + 3-year history required for the benefits cascade (#2, D-005)
  - NaN count must be zero; RuntimeWarnings from ir.py edge cases are expected noise

Run:  python scripts/verify_population_engine.py [N]     (default N=10000)
Verified green 2026-08-28 on openfisca-france 176.0.8 (aggregate IR = 5.9% of
gross wages on this exact synthetic population, seed 42).
"""
import sys
import time

import numpy as np
from openfisca_core.simulation_builder import SimulationBuilder
from openfisca_france import FranceTaxBenefitSystem

N = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
YEAR = 2024
SEED = 42

# Silent-failure mode #1: these must be flattened SUBROLE keys.
# 'declarant' / 'parent' match nothing, nbptr computes 0.0, and NO ERROR IS RAISED.
ROLE = {
    "foyer_fiscal": "declarant_principal",
    "famille": "demandeur",
    "menage": "personne_de_reference",
}

def months_of(y):
    return [f"{y}-{m:02d}" for m in range(1, 13)]

t0 = time.time()
tbs = FranceTaxBenefitSystem()
print(f"TBS loaded in {time.time()-t0:.1f}s")

# Assert the subrole vocabulary is what we think it is (it is version-dependent).
expected = {
    "foyer_fiscal": ["declarant_principal", "conjoint", "personne_a_charge"],
    "famille": ["demandeur", "conjoint", "enfant"],
    "menage": ["personne_de_reference", "conjoint", "enfant", "autre"],
}
for ent in tbs.entities:
    if not ent.is_person:
        keys = [r.key for r in ent.flattened_roles]
        assert keys == expected[ent.key], f"{ent.key} subroles changed: {keys}"
print("subrole vocabulary OK")

rng = np.random.default_rng(SEED)
ids = np.arange(N)

sb = SimulationBuilder()
sb.create_entities(tbs)                       # required init step
sb.declare_person_entity("individu", ids)
for ent, role in ROLE.items():
    inst = sb.declare_entity(ent, ids)
    sb.join_with_persons(inst, ids, np.array([role] * N))
sim = sb.build(tbs)

annual = rng.lognormal(mean=np.log(28000), sigma=0.55, size=N)
# Fatal-failure mode #2: enum defaults ('non_renseigne') crash vectorised
# parameter lookups in aides_logement, and benefit reference periods look back
# into N-1/N-2 (D-005) — so ALL 36 months of N-2..N get explicit inputs.
for y in (YEAR - 2, YEAR - 1, YEAR):
    for m in months_of(y):
        sim.set_input("salaire_de_base", m, annual / 12)
        sim.set_input("zone_apl", m, np.array(["zone_2"] * N))
        sim.set_input("statut_occupation_logement", m, np.array(["locataire_vide"] * N))
        sim.set_input("loyer", m, np.full(N, 700.0))

t0 = time.time()
ir = sim.calculate("impot_revenu_restant_a_payer", str(YEAR))
t_ir = time.time() - t0
nbptr = sim.calculate("nbptr", str(YEAR))

# The guards that separate expected noise from silent failure:
assert np.isnan(ir).sum() == 0, "NaN in IR: wiring bug (bad roles or inputs)"
assert nbptr.min() >= 1, "nbptr=0: role join failed silently (see spec §1.2)"

ratio = -ir.sum() / (annual.sum())
print(f"N={N}: IR calc {t_ir:.1f}s, total IR = {ratio:.1%} of gross wages")
assert 0.03 < ratio < 0.09, f"aggregate IR ratio {ratio:.1%} outside sanity band"

t0 = time.time()
rd = sim.calculate("revenu_disponible", str(YEAR))
t_rd = time.time() - t0
assert np.isnan(rd).sum() == 0
al = sim.calculate_add("aide_logement", str(YEAR))
print(f"full cascade {t_rd:.1f}s; mean RD={rd.mean():.0f}, mean AL={al.mean():.0f}")
assert (rd > 0).all(), "non-positive disposable income for a wage-earning population"

print("\nPopulation-engine assumptions hold. Build the pipeline on this pattern.")
