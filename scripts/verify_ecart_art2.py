#!/usr/bin/env python
"""PLF 2027 art. 2 graded outside its tolerance, −30,3 % — the gap, volet par volet (D-291).

D-204 named four mechanical explanations and measured none. This script measures them, so
the explanation stays a measurement rather than a sentence (the D-125 pattern):

1. **The control.** The registered scenario replayed on the population as registered
   (pensions scaled back to the pre-D-211 target, as `verify_pensions_art3.py` does) must
   land on the registered euro: what follows is then about that number.
2. **The components.** The scale's thresholds, the décote and the general half-share
   ceiling, priced apart on today's population, and their sum against the whole.
3. **The vintage.** The population's incomes are those of 2024. The annex estimated the
   measure on 2025 incomes and published the 2027 budget effect of 2026 incomes. The whole
   scenario priced on the population aged to 2026 and 2027, under two declared bracketing
   index pairs, never a forecast.
4. **The basis.** The annex's 4,2 Md€ is the budget effect of 2027: the avis on 2026 incomes
   and the PAS of 2027 (§ 4.2.1.1). `impots.pas` turns full-year effects into it, the model
   validated on art. 3's published chronicle.
5. **The level.** The population's tax at the scale against the DGFiP's 98,84 Md€ on 2024
   incomes: a scale that bites too much costs too much to index.

What it does not measure: the four other quotient ceilings, the alimony deduction ceiling,
the married-child allowance and the default PAS grids, which the annex prices and no knob
reaches. They stay a declared downward bias.

Usage: `.venv/bin/python scripts/verify_ecart_art2.py` (about twenty minutes; needs
`data/processed/population_2024.parquet`). It writes `reports/ecart_art2.json`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"
OUT = ROOT / "reports" / "ecart_art2.json"

REGISTERED = 2_926_586_879.963867  # chiffrages_preregistres/plf2027_art_2.yaml
PUBLISHED_2027 = 4.2e9             # annex, art. 2, § 4.2.1.1, p. 29
TOLERANCE = 0.20                   # declared at registration, unchanged
REGISTRATION_TARGET = 400.4e9      # the pension target before D-211
SAMPLE = 20_000
#: Declared bracketing indices for ageing 2024 incomes, never a forecast: wages and prices
#: by year, low and high.
INDICES = {"bas": (0.02, 0.01), "haut": (0.03, 0.02)}
INDICES_SOURCE = ("bornes déclarées pour vieillir les revenus de 2024, pas une prévision "
                  "(D-291)")


class EcartError(RuntimeError):
    """The measurement would not be about the registered number."""


def as_registered(frame: pl.DataFrame) -> pl.DataFrame:
    """The population with its pensions scaled back to the pre-D-211 target."""
    mass = float((frame["pension_annuelle"] * frame["weight"]).sum())
    return frame.with_columns(pl.col("pension_annuelle") * (REGISTRATION_TARGET / mass))


def components(reform) -> dict[str, object]:
    """The scenario's three volets, each alone."""
    from impots.api.schemas import ReformSpec

    return {
        "tranches": ReformSpec(ir_bareme=reform.ir_bareme),
        "decote": ReformSpec(decote_seuil_celib=reform.decote_seuil_celib,
                             decote_seuil_couple=reform.decote_seuil_couple),
        "demi_part": ReformSpec(plafond_qf_demi_part=reform.plafond_qf_demi_part),
    }


def main() -> int:
    from impots import pas, scenarios
    from impots import uprating as up
    from impots.population import aggregate, runner

    if not POPULATION.exists():
        print(f"{POPULATION} absent — `impots population build` d'abord", file=sys.stderr)
        return 1
    scenario = scenarios.load("plf2027_art_2")
    frame = pl.read_parquet(POPULATION)

    def cost(population: pl.DataFrame, reform, year: int = scenario.year) -> float:
        result = runner.run(population, year=year, reform=reform, tier="full", sample=SAMPLE)
        return float(aggregate.aggregate(result.households).reform_cost or 0.0)

    from impots.predictif import recherche

    commit, dirty = recherche.code_state(ROOT)
    found: dict[str, object] = {"commit": commit, "dirty": dirty,
                                "registered": REGISTERED, "published_2027": PUBLISHED_2027}

    # 1. The control.
    control = cost(as_registered(frame), scenario.reform)
    print(f"1. rejoué tel qu'enregistré : {control / 1e9:.6f} Md€ "
          f"(enregistré {REGISTERED / 1e9:.6f})", flush=True)
    if abs(control - REGISTERED) > 1.0:
        raise EcartError(f"le chiffrage rejoué ({control:,.0f}) n'est pas celui enregistré "
                         f"({REGISTERED:,.0f}) : la mesure ne porterait pas sur lui.")
    found["control"] = control

    # 2. The components, on today's population.
    whole = cost(frame, scenario.reform)
    parts = {name: cost(frame, reform) for name, reform in components(scenario.reform).items()}
    found.update(today=whole, components=parts)
    print(f"2. aujourd'hui : {whole / 1e9:.3f} Md€ ; "
          + " ; ".join(f"{k} {v / 1e9:.3f}" for k, v in parts.items())
          + f" ; somme {sum(parts.values()) / 1e9:.3f}", flush=True)

    # 3. The vintage, and 4. the basis.
    aged: dict[str, dict[str, float]] = {}
    for label, (wage, price) in INDICES.items():
        uprating = up.Uprating(wage=wage, price=price, source=INDICES_SOURCE, base_year=2024)
        by_year = {year: cost(up.uprate(frame, year, uprating), scenario.reform, year)
                   for year in (2026, 2027)}
        budget = pas.budget_effects(by_year, first_income_year=2026, years=(2027,))[2027]
        aged[label] = {"wage": wage, "price": price, "2026": by_year[2026],
                       "2027": by_year[2027], "budget_2027": budget}
        print(f"3. vieilli ({label}, salaires {wage:.0%}, prix {price:.0%}) : revenus 2026 "
              f"{by_year[2026] / 1e9:.3f}, 2027 {by_year[2027] / 1e9:.3f} ; "
              f"4. effet budgétaire 2027 {budget / 1e9:.3f} Md€", flush=True)
    found["aged"] = aged
    registered_basis = pas.budget_effects({2026: REGISTERED, 2027: REGISTERED},
                                          first_income_year=2026, years=(2027,))[2027]
    found["registered_budget_2027"] = registered_basis
    print(f"4. l'enregistré sur la base de 2027 : {registered_basis / 1e9:.3f} Md€, "
          f"{registered_basis / PUBLISHED_2027 - 1:+.1%} du publié", flush=True)

    # 5. The level.
    from impots.population.margins import IR_BAREME_ON_2024_INCOME

    result = runner.run(frame, year=2024, reform=None, tier="full", sample=SAMPLE)
    level = float(aggregate.aggregate(result.households).totals["ir_avant_niches"])
    found["level"] = {"simulated": level, "published": IR_BAREME_ON_2024_INCOME.value}
    print(f"5. impôt au barème, revenus 2024 : {level / 1e9:.2f} Md€ contre "
          f"{IR_BAREME_ON_2024_INCOME.value / 1e9:.2f}, "
          f"{level / IR_BAREME_ON_2024_INCOME.value - 1:+.1%}", flush=True)

    OUT.write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except EcartError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
