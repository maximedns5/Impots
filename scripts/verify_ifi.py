#!/usr/bin/env python
"""M0 — the IFI reconnaissance gate (PHASE5_SPEC §7).

Runs before any pricing code exists, and nothing in `patrimoine/` may be built on the
cells until this is green. Phase 4's M0 changed the shape of its problem — the spec
asked for a non-negative import matrix and the published table is not non-negative —
and this one changes its problem too, harder.

**`PHASE5_SPEC.md` §2 says the tranche table publishes "redevable counts, taxable base,
tax due", and that the mechanical check is to apply our barème to the published base
per tranche. The base per tranche is NOT published.** What is published is counts and
tax per tranche, plus the base in AGGREGATE only. So the zero-calibration check is
reformulated, and this gate is where that is established rather than assumed:

  1. the two published routes to a tranche's IFI agree — share of the total, and mean
     times count. They are separate numbers in the publication, so agreement is a
     check on our reading, not a tautology;
  2. the shares sum to 100 %;
  3. the barème resolves from the engine's own parameter tree at the assessment year,
     and every node it comes from is READ BY A FORMULA (the phantom rule — the dead
     aide_a_domicile tree lives one namespace away from these parameters);
  4. inverting the barème on each tranche's mean IFI puts the implied mean base INSIDE
     that tranche. This is the falsifiable part: nothing forces it, and a barème we
     have misread would put a mean outside its own bracket;
  5. the reconstructed aggregate base is close to the independently published one, and
     the residual has the sign the unmodelled reliefs predict — décote, plafonnement
     and the dons reduction all lower tax, so inverting tax must UNDERSTATE the base.
     A residual of the wrong sign would mean our arithmetic is wrong, not incomplete.

Nothing here is fitted. If a future edit makes any of these pass by adjusting a factor,
the module's whole claim — that its baseline is a mechanical check with zero calibration
(D-077) — is gone.

Run: `python scripts/verify_ifi.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from impots.patrimoine import ifi_cells

#: The two published routes to a tranche's IFI are rounded differently in the source,
#: so they are not expected to agree to the cent — but a percent apart would mean we
#: have paired the wrong columns.
TRANCHE_AGREEMENT = 0.005

#: How far the reconstructed aggregate base may sit below the published one. The gap is
#: real and expected: inverting tax cannot see the décote, the plafonnement or the dons
#: reduction, all of which lower tax and therefore make the implied base too small.
#: The ceiling is set generously because the gate's job is to catch a misread barème,
#: not to grade the model — M2 quantifies the pieces.
MAX_BASE_SHORTFALL = 0.12


def check(label: str, ok: bool, detail: str = "") -> bool:
    # bool(), not the argument as given, for the reason verify_tes.py records: a numpy
    # comparison returns np.bool_ and letting one propagate makes the verdict fail an
    # `is False` test while being false.
    ok = bool(ok)
    print(f"  {'OK  ' if ok else 'FAIL'} {label}{(' — ' + detail) if detail else ''}")
    return ok


def barometer(year: int) -> list[tuple[float, float]]:
    """The IFI scale as (threshold, marginal rate), read from the engine's tree."""
    from openfisca_france import FranceTaxBenefitSystem

    node = (FranceTaxBenefitSystem()
            .get_parameters_at_instant(f"{year}-01-01")
            .taxation_capital.impot_fortune_immobiliere_ifi_partir_2018.bareme)
    return list(zip(node.thresholds, node.rates, strict=True))


def tax_on(base: float, scale: list[tuple[float, float]]) -> float:
    """Marginal-rate tax on `base`, before décote, plafonnement and réductions."""
    total = 0.0
    for index, (threshold, rate) in enumerate(scale):
        upper = scale[index + 1][0] if index + 1 < len(scale) else float("inf")
        total += max(0.0, min(base, upper) - threshold) * rate
    return total


def invert(tax: float, scale: list[tuple[float, float]]) -> float:
    """The base that produces `tax` under the scale. Monotone, so bisection is exact
    enough and cannot be fooled by a bracket boundary the way an algebraic inversion
    written per-bracket can."""
    low, high = 0.0, 1.0e9
    for _ in range(200):
        mid = (low + high) / 2.0
        if tax_on(mid, scale) < tax:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def audit() -> bool:
    aggregate = ifi_cells.aggregate()
    tranches = ifi_cells.tranches()
    year = ifi_cells.TRANCHE_YEAR
    passed = True

    print(f"Agrégat {aggregate.year} (n° 45, Tableau 1) — "
          f"{aggregate.foyers:,.0f} foyers, base {aggregate.base_eur / 1e9:.2f} md, "
          f"IFI {aggregate.ifi_eur / 1e9:.4f} md, dons {aggregate.dons_eur / 1e6:.1f} M")
    print(f"Tranches {year} (n° 33, Graphique 3) — {len(tranches)} tranches\n")

    print("1. Les deux routes publiées vers l'IFI d'une tranche")
    for tranche in tranches:
        from_mean = tranche.foyers * tranche.mean_ifi_eur
        gap = from_mean / tranche.ifi_eur - 1 if tranche.ifi_eur else float("inf")
        passed &= check(f"{tranche.label:14}", abs(gap) <= TRANCHE_AGREEMENT,
                        f"part {tranche.ifi_eur / 1e6:.1f} M vs moyenne×n "
                        f"{from_mean / 1e6:.1f} M ({gap:+.3%})")

    print("\n2. Les parts somment à 100 %")
    share_foyers = sum(t.foyers for t in tranches) / aggregate.foyers
    share_ifi = sum(t.ifi_eur for t in tranches) / aggregate.ifi_eur
    passed &= check("foyers", abs(share_foyers - 1) < 0.001, f"{share_foyers:.4%}")
    passed &= check("IFI", abs(share_ifi - 1) < 0.001, f"{share_ifi:.4%}")

    print("\n3. Le barème vient de l'arbre du moteur, et ses nœuds sont lus")
    scale = barometer(year)
    # No leading (0, 0) bracket: the tree starts at 800 000, and the exemption below it
    # is the absence of a bracket rather than a zero one. Written down because the
    # first version of this gate asserted a zero bracket and failed on the tree being
    # right — spec §1's figures are confirmed exactly as it states them.
    expected = [(800_000.0, 0.005), (1_300_000.0, 0.007), (2_570_000.0, 0.01),
                (5_000_000.0, 0.0125), (10_000_000.0, 0.015)]
    passed &= check("barème résolu", scale == expected, f"{scale}")
    passed &= check("nœud lu par une formule", _is_read("impot_fortune_immobiliere_ifi"),
                    "sinon c'est un arbre fantôme comme aide_a_domicile (D-064)")

    print("\n4. Le barème inversé place la base moyenne DANS sa tranche")
    reconstructed = 0.0
    for tranche in tranches:
        implied = invert(tranche.mean_ifi_eur, scale)
        reconstructed += implied * tranche.foyers
        inside = tranche.lower_eur <= implied <= tranche.upper_eur
        passed &= check(f"{tranche.label:14}", inside,
                        f"base moyenne implicite {implied / 1e6:.4f} M€")

    print("\n5. L'agrégat reconstitué contre l'agrégat publié, indépendant")
    shortfall = 1 - reconstructed / aggregate.base_eur
    passed &= check(
        "manque du bon signe et de taille plausible",
        0.0 <= shortfall <= MAX_BASE_SHORTFALL,
        f"reconstitué {reconstructed / 1e9:.2f} md contre {aggregate.base_eur / 1e9:.2f} md "
        f"publié, soit {-shortfall:+.2%} — l'inversion ne peut pas voir la décote, le "
        f"plafonnement ni les dons, qui tous baissent l'impôt",
    )
    return passed


def _is_read(fragment: str) -> bool:
    """Does any formula in openfisca-france read a parameter under this namespace?"""
    import openfisca_france

    root = Path(openfisca_france.__file__).parent / "model"
    return any(
        fragment in path.read_text(encoding="utf-8", errors="ignore")
        for path in root.rglob("*.py")
    )


def main() -> int:
    print("IFI reconnaissance — DGFiP n° 33 (tranches) + n° 45 (agrégats)\n")
    passed = audit()
    print()
    if passed:
        print("M0 gate PASSED — les cellules peuvent servir. Voir docs/M0_IFI.md.")
        return 0
    print("M0 gate FAILED — aucun code de tarification tant que ce n'est pas vert.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
