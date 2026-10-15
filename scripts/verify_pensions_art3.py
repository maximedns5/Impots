#!/usr/bin/env python
"""PLF 2027 art. 3 graded inside its tolerance but on the wrong side — the diagnosis (D-207).

The registration listed only downward biases: no capital income, so lower marginal rates,
and a counterfactual ceiling frozen at 4 439 EUR. The simulated yield came out 17,7 %
ABOVE the annex's 1,1 Md€. This script replays what explains it, so the explanation stays
a measurement rather than a sentence (the D-125 pattern).

WHAT IT MEASURES, three ways:

1. **The population, without the engine.** The pension mass is calibrated on the DGFiP's
   «pensions et rentes», 400,4 Md€ (Stat 41, Tableau 1), which covers every pension the
   abatement covers — retirement, invalidity, alimony. It is drawn onto inactive persons of
   55 or more and they sit in fewer foyers than the published counts: fewer than the
   annex's 13,4 M foyers with a retirement pension, fewer still than the 15,09 M foyers
   the Voies et moyens count as beneficiaries of the abatement. The same mass on fewer
   foyers is a fatter tail above 30 000 EUR, which is exactly where the 3 000 EUR ceiling
   bites.

2. **An independent line, never a calibration target.** The whole 10 % abatement, removed
   on 2024 incomes under 2024 law, against Voies et moyens tome II (PLF 2026), dépense
   fiscale 120401, column «prévision 2025» — the one assise on 2024 incomes (see the
   manifest note on vintage).

3. **The registered chiffrage itself, at foyer level.** The gain splits into foyers paying
   more times the gain per foyer, against the annex's 4,6 M foyers. The runner sums foyers
   into ménages, so its foyer-level tax is read by wrapping `runner._extract`; if that
   internal changes, this script fails loudly rather than counting ménages as foyers.

The pins hold the numbers D-207 quotes. A change in the population or the engine fails
here first, and the diagnosis is then to be re-read, not the pins widened.

Usage: `.venv/bin/python scripts/verify_pensions_art3.py` (about five minutes; needs
`data/processed/population_2024.parquet`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

POPULATION = ROOT / "data" / "processed" / "population_2024.parquet"

ANNEX_FOYERS_RETRAITE = 13.4e6     # art. 3, § 4.1.2, p. 36
ANNEX_FOYERS_TOUCHES = 4.6e6       # idem, « un tiers »
ANNEX_GAIN = 1.1e9                 # art. 3, § 4.2, p. 36, à compter de 2029
VM_120401_FOYERS = 15_085_237      # VM tome II PLF 2026, p. 78
VM_120401_REVENUS_2024 = 5.322e9   # idem, colonne « prévision 2025 »
REGISTERED = -1_294_878_105.204834  # chiffrages_preregistres/plf2027_art_3.yaml

#: Pinned at D-207. Relative tolerance: the sample is seeded, so a drift means a change.
PINS = {
    "foyers_pension": 12.24e6,
    "abattement_entier": 5.909e9,
    "foyers_touches": 4.904e6,
}
PIN_TOLERANCE = 0.01


def _foyers(frame: pl.DataFrame) -> pl.DataFrame:
    """One row per foyer, weighted as the runner weights it: the mean of member weights."""
    return (frame.group_by("foyer_id")
            .agg(pl.col("weight").mean().alias("w"),
                 pl.col("pension_annuelle").sum().alias("pension"))
            .sort("foyer_id"))


def main() -> int:
    from impots import scenarios
    from impots.api.schemas import ReformSpec
    from impots.population import aggregate, runner

    if not POPULATION.exists():
        print(f"{POPULATION} absent — `impots population build` d'abord", file=sys.stderr)
        return 1
    frame = pl.read_parquet(POPULATION)
    failures: list[str] = []

    def pin(name: str, value: float) -> None:
        expected = PINS[name]
        if abs(value / expected - 1) > PIN_TOLERANCE:
            failures.append(f"{name} : {value:,.0f} contre {expected:,.0f} épinglé")

    # 1. The population alone.
    whole = _foyers(frame)
    w, pension = whole["w"].to_numpy(), whole["pension"].to_numpy()
    print(f"1. foyers avec une pension : {w[pension > 0].sum() / 1e6:.2f} M "
          f"(annexe : {ANNEX_FOYERS_RETRAITE / 1e6:.1f} M de retraités ; "
          f"VM 120401 : {VM_120401_FOYERS / 1e6:.2f} M bénéficiaires)")
    pin("foyers_pension", w[pension > 0].sum())
    print(f"   pension moyenne par foyer pensionné : "
          f"{(pension * w).sum() / w[pension > 0].sum():,.0f} EUR")

    # 2. The whole abatement on 2024 incomes, against the independent line.
    result = runner.run(frame, year=2024, tier="full", sample=20_000,
                        reform=ReformSpec(abattement_pensions_plafond=0.0))
    cost = -float(aggregate.aggregate(result.households).reform_cost)
    print(f"2. l'abattement entier, revenus 2024 : {cost / 1e9:.3f} Md€ contre "
          f"{VM_120401_REVENUS_2024 / 1e9:.3f} (VM 120401), {cost / VM_120401_REVENUS_2024 - 1:+.1%}")
    pin("abattement_entier", cost)

    # 3. The registered chiffrage, at foyer level.
    captured: list[tuple[np.ndarray, pl.DataFrame]] = []
    extract = runner._extract

    def spy(built, sampled, tier, guards):
        captured.append((np.asarray(built.calculate("impot_revenu_restant_a_payer"),
                                    dtype=np.float64), _foyers(sampled)))
        return extract(built, sampled, tier, guards)

    scenario = scenarios.load("plf2027_art_3")
    runner._extract = spy
    try:
        result = runner.run(frame, year=scenario.year, reform=scenario.reform,
                            tier="full", sample=20_000)
    finally:
        runner._extract = extract
    mechanical = float(aggregate.aggregate(result.households).reform_cost)
    if abs(mechanical - REGISTERED) > 1.0:
        failures.append(f"le chiffrage rejoué ({mechanical:,.0f}) n'est pas celui enregistré")
    (before, foyers), (after, _) = captured[0], captured[-1]
    w, pension = foyers["w"].to_numpy(), foyers["pension"].to_numpy()
    paid = before - after   # the engine signs tax paid negative
    hit = paid > 0.5
    per_foyer = (paid * w)[hit].sum() / w[hit].sum()
    print(f"3. art. 3 : {-mechanical / 1e9:.3f} Md€ contre {ANNEX_GAIN / 1e9:.1f}, "
          f"{-mechanical / ANNEX_GAIN - 1:+.1%}")
    print(f"   foyers qui paient davantage : {w[hit].sum() / 1e6:.3f} M contre "
          f"{ANNEX_FOYERS_TOUCHES / 1e6:.1f}, {w[hit].sum() / ANNEX_FOYERS_TOUCHES - 1:+.1%}")
    print(f"   gain par foyer touché : {per_foyer:.0f} EUR contre "
          f"{ANNEX_GAIN / ANNEX_FOYERS_TOUCHES:.0f}, "
          f"{per_foyer / (ANNEX_GAIN / ANNEX_FOYERS_TOUCHES) - 1:+.1%}")
    pin("foyers_touches", w[hit].sum())

    for failure in failures:
        print(f"ÉCHEC  {failure}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
