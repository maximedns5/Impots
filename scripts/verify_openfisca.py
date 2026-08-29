"""Smoke test for the Phase 0 engine assumptions.

Run FIRST, before writing any other code:  python scripts/verify_openfisca.py
Every assertion here was verified against openfisca-france 176.0.8 (2026-08-28).
If an assertion fails after a version bump, the golden values in tests/golden/
have moved with the law: record it in docs/DECISIONS.md before re-anchoring.
"""
import time
from importlib.metadata import version

t0 = time.time()
from openfisca_core import periods
from openfisca_core.reforms import Reform
from openfisca_core.simulation_builder import SimulationBuilder
from openfisca_france import FranceTaxBenefitSystem

print(f"openfisca-france {version('openfisca-france')} / openfisca-core {version('openfisca-core')}")
tbs = FranceTaxBenefitSystem()
print(f"TBS loaded in {time.time()-t0:.1f}s — {len(tbs.variables)} variables")

YEAR = "2024"
MONTHS = [f"{YEAR}-{m:02d}" for m in range(1, 13)]

def close(a, b, tol=2.0):
    assert abs(a - b) <= tol, f"expected {b}, got {a:.0f}"

def sit_single(monthly, birth="1990-01-01"):
    return {
        "individus": {"a0": {"salaire_de_base": {m: monthly for m in MONTHS},
                             "date_naissance": {"ETERNITY": birth}}},
        "foyers_fiscaux": {"ff0": {"declarants": ["a0"]}},
        "familles": {"f0": {"parents": ["a0"]}},
        "menages": {"m0": {"personne_de_reference": ["a0"]}},
    }

def build(s, system=None):
    return SimulationBuilder().build_from_entities(system or tbs, s)

# --- registry sanity: names, entities, periods -------------------------------
expect = {
    "salaire_de_base": ("individu", "month"), "salaire_net": ("individu", "month"),
    "impot_revenu_restant_a_payer": ("foyer_fiscal", "year"),
    "nbptr": ("foyer_fiscal", "year"), "af": ("famille", "month"),
    "ppa": ("famille", "month"), "revenu_disponible": ("menage", "year"),
}
for name, (ent, per) in expect.items():
    v = tbs.variables.get(name)
    assert v is not None, f"variable {name} missing"
    assert v.entity.key == ent and str(v.definition_period) == per, name
assert tbs.variables.get("irpp") is None          # dead name
assert tbs.variables.get("prime_activite") is None  # it's `ppa`
print("variable registry OK")

# --- golden case: single 30k -------------------------------------------------
sim = build(sit_single(2500.0))
close(sim.calculate_add("salaire_net", YEAR)[0], 23748)
close(-sim.calculate("impot_revenu_restant_a_payer", YEAR)[0], 812)
close(sim.calculate("revenu_disponible", YEAR)[0], 23908)
print("golden single_30k OK")

# --- golden case: SMIC single ------------------------------------------------
sim = build(sit_single(1801.80, "1995-01-01"))
close(-sim.calculate("impot_revenu_restant_a_payer", YEAR)[0], 0)
close(sim.calculate_add("ppa", YEAR)[0], 2370)
print("golden smic_single OK")

# --- barème read pattern -----------------------------------------------------
bareme = tbs.parameters.impot_revenu.bareme_ir_depuis_1945.bareme
at = bareme("2024-01-01")
assert at.thresholds == [0, 11497, 29315, 83823, 180294], at.thresholds
assert at.rates == [0, 0.11, 0.3, 0.41, 0.45], at.rates
d = tbs.parameters.impot_revenu.calcul_impot_revenu.plaf_qf.decote
assert d.seuil_celib("2024-01-01") == 889 and d.seuil_couple("2024-01-01") == 1470
csg = tbs.parameters.prelevements_sociaux.contributions_sociales.csg.activite
assert abs(csg.imposable("2024-01-01") - 0.024) < 1e-9
print("parameter paths OK")

# --- reform + no-mutation ----------------------------------------------------
class TopRate50(Reform):
    name = "top-rate-50"
    def apply(self):
        def modify(parameters):
            b = parameters.impot_revenu.bareme_ir_depuis_1945.bareme
            b.brackets[4].rate.update(start=periods.instant("2024-01-01"), value=0.50)
            return parameters
        self.modify_parameters(modifier_function=modify)

reformed = TopRate50(tbs)
s240 = sit_single(20000.0, "1980-01-01")
ir_base = -build(s240).calculate("impot_revenu_restant_a_payer", YEAR)[0]
ir_ref = -build(s240, reformed).calculate("impot_revenu_restant_a_payer", YEAR)[0]
close(ir_base, 59668); close(ir_ref, 59868); close(ir_ref - ir_base, 200)
# baseline untouched after reform:
close(-build(s240).calculate("impot_revenu_restant_a_payer", YEAR)[0], 59668)
assert bareme("2024-01-01").rates[-1] == 0.45
print("reform mechanics + no-mutation OK  (delta = +200 EUR, checkable by hand)")

print("\nAll Phase 0 engine assumptions hold. Build on.")
