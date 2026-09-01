"""Firm-engine gate for Phase 2.

Encodes the [VERIFIED] pattern of PHASE2_SPEC.md par.1 as assertions: a custom
`entreprise` entity on openfisca-core, YAML dated parameters, vectorised
formulas at 500k firms, the household engine's Reform API, and the float32
precision bound that dictates relative tolerances.

Run:  python scripts/verify_firm_engine.py
Verified green 2026-08-29 on openfisca-core 44.7.0 (prototype: 500k firms,
IS computed in ~0.01s, hand-check within float32 relative precision).
Self-contained: writes its parameter YAML to a temp dir.
"""
import tempfile
import time
from pathlib import Path

import numpy as np
from openfisca_core import periods
from openfisca_core.entities import build_entity
from openfisca_core.periods import YEAR
from openfisca_core.reforms import Reform
from openfisca_core.simulation_builder import SimulationBuilder
from openfisca_core.taxbenefitsystems import TaxBenefitSystem
from openfisca_core.variables import Variable

# --- parameters: dated YAML, node named impot_societes (NEVER `is`: keyword clash,
#     verified — `parameters.is_` does not resolve) ---------------------------
PARAMS = {
    "impot_societes/taux_normal.yaml": "description: Taux normal IS\nvalues:\n  2022-01-01:\n    value: 0.25\n",
    "impot_societes/taux_reduit.yaml": "description: Taux reduit PME\nvalues:\n  2023-01-01:\n    value: 0.15\n",
    "impot_societes/plafond_taux_reduit.yaml": "description: Plafond du taux reduit\nvalues:\n  2023-01-01:\n    value: 42500\n",
}

Entreprise = build_entity(key="entreprise", plural="entreprises",
                          label="Unité légale soumise à l'IS", is_person=True)

class chiffre_affaires(Variable):
    value_type = float; entity = Entreprise; definition_period = YEAR
    label = "Chiffre d'affaires HT"

class benefice_imposable(Variable):
    value_type = float; entity = Entreprise; definition_period = YEAR
    label = "Résultat fiscal imposable (>= 0; les déficitaires portent 0)"

class eligible_taux_reduit(Variable):
    value_type = bool; entity = Entreprise; definition_period = YEAR
    label = "Éligibilité PME (CA <= 10M; conditions de capital réputées remplies)"
    def formula(entreprise, period, parameters):
        return entreprise("chiffre_affaires", period) <= 10_000_000

class is_brut(Variable):
    value_type = float; entity = Entreprise; definition_period = YEAR
    label = "IS brut, taux normal + taux réduit PME"
    def formula(entreprise, period, parameters):
        p = parameters(period).impot_societes
        b = entreprise("benefice_imposable", period)
        eligible = entreprise("eligible_taux_reduit", period)
        part_reduite = np.minimum(b, p.plafond_taux_reduit) * eligible
        return part_reduite * p.taux_reduit + (b - part_reduite) * p.taux_normal

def build_tbs(params_dir):
    class FirmSystem(TaxBenefitSystem):
        def __init__(self):
            super().__init__([Entreprise])
            self.load_parameters(str(params_dir))
            for v in (chiffre_affaires, benefice_imposable, eligible_taux_reduit, is_brut):
                self.add_variable(v)
    return FirmSystem()

def build_sim(tbs, ca, benef, year="2026"):
    n = len(ca)
    sb = SimulationBuilder()
    sb.create_entities(tbs)
    sb.declare_person_entity("entreprise", np.arange(n))
    sim = sb.build(tbs)
    sim.set_input("chiffre_affaires", year, ca)
    sim.set_input("benefice_imposable", year, benef)
    return sim

def main():
    tmp = Path(tempfile.mkdtemp())
    for rel, text in PARAMS.items():
        p = tmp / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)

    tbs = build_tbs(tmp)
    assert tbs.parameters.impot_societes.taux_normal("2026-01-01") == 0.25
    print("parameter tree OK (impot_societes, dated values)")

    N = 500_000
    rng = np.random.default_rng(7)
    ca = rng.lognormal(np.log(400_000), 1.8, N)
    benef = np.maximum(rng.normal(0.06, 0.10, N) * ca, 0)

    sim = build_sim(tbs, ca, benef)
    t0 = time.time(); tax = sim.calculate("is_brut", "2026"); dt = time.time() - t0
    assert np.isnan(tax).sum() == 0
    assert (tax >= 0).all()
    print(f"N={N}: IS computed in {dt:.2f}s, total {tax.sum()/1e9:.2f} bn, NaN=0")

    # float32 bound: hand-check the largest firm with RELATIVE tolerance (spec 1.4)
    i = int(np.argmax(ca)); b = float(benef[i])
    expected = (min(b, 42500) * 0.15 + max(b - 42500, 0) * 0.25) if ca[i] <= 10e6 else b * 0.25
    rel = abs(tax[i] - expected) / max(expected, 1.0)
    assert rel < 1e-5, f"relative error {rel:.2e} exceeds float32 expectation"
    print(f"hand-check: engine={tax[i]:,.0f} expected={expected:,.0f} rel_err={rel:.1e}")

    # kink golden: PME exactly at the 42 500 threshold
    sim_k = build_sim(tbs, np.array([1e6, 1e6]), np.array([42_500.0, 85_000.0]))
    tk = sim_k.calculate("is_brut", "2026")
    assert abs(tk[0] - 42_500 * 0.15) < 1
    assert abs(tk[1] - (42_500 * 0.15 + 42_500 * 0.25)) < 1
    print("PME kink golden OK (6 375 / 17 000)")

    # Reform API parity + no mutation
    class IS30(Reform):
        name = "IS 30"
        def apply(self):
            def modify(parameters):
                parameters.impot_societes.taux_normal.update(
                    start=periods.instant("2026-01-01"), value=0.30)
                return parameters
            self.modify_parameters(modifier_function=modify)

    reformed = IS30(tbs)
    tax_r = build_sim(reformed, ca, benef).calculate("is_brut", "2026")
    assert tax_r.sum() > tax.sum() * 1.15
    tax_again = build_sim(tbs, ca, benef).calculate("is_brut", "2026")
    assert abs(float(tax_again.sum()) - float(tax.sum())) < 1.0
    assert tbs.parameters.impot_societes.taux_normal("2026-01-01") == 0.25
    print(f"reform OK: {tax.sum()/1e9:.2f} -> {tax_r.sum()/1e9:.2f} bn; baseline untouched")

    print("\nFirm-engine assumptions hold. Build the entreprises package on this pattern.")

if __name__ == "__main__":
    main()
