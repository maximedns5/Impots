#!/usr/bin/env python
"""M0 — the input-output reconnaissance gate (PHASE4_SPEC §3).

Runs before any propagation code exists, and nothing in `io_layer.py` may be written
until this is green. The EEC's M0 changed the shape of its problem — roles, weights and
the meaning of "child" all turned out to differ from the spec's assumption — which is
why this is a procedure rather than a memory. It changed this one too: the spec asks
for "the import matrix present and non-negative", and the published table is not
non-negative. See docs/M0_TES.md.

What it asserts, in the spec's order:

  1. the product balance holds per branch, to published rounding;
  2. the import matrix is present, and its negatives are confined and identified;
  3. the Leontief inverse exists — spectral radius of A strictly below 1;
  4. employment coefficients are positive and finite;
  5. the vintage and base year are recorded rather than assumed.

Run: `python scripts/verify_tes.py [vintage]`
"""

from __future__ import annotations

import sys

import numpy as np

from impots.macro import tes

#: Published values are millions of euros to one decimal, so a per-product balance is
#: expected to close well inside a single million.
BALANCE_TOLERANCE_MEUR = 1.0

#: The table carries accounting adjustments that are legitimately negative (SIFIM, on
#: financial services against real estate). A handful is an accounting convention and
#: gets named below; a scattering would be a misread of the sheet. The gate draws the
#: line at "few enough to enumerate and explain".
MAX_NEGATIVE_CELLS = 5

#: A spectral radius near 1 would mean unbounded output from a unit of demand; anything
#: above this deserves examination before it is inverted.
SPECTRAL_CEILING = 0.9


def check(label: str, ok: bool, detail: str = "") -> bool:
    # bool(), not the argument as given: numpy comparisons return np.bool_, and letting
    # one propagate makes the gate's verdict fail an `is False` test while being false.
    ok = bool(ok)
    print(f"  {'OK  ' if ok else 'FAIL'} {label}{(' — ' + detail) if detail else ''}")
    return ok


def _negatives(matrix, branches) -> list[str]:
    return [
        f"{branches[i]}->{branches[j]} {matrix[i, j]:,.1f}"
        for i, j in np.argwhere(matrix < 0)
    ]


def audit(table, jobs) -> bool:
    """Every assertion, against a table already in hand.

    Split from `main` so tests can hand it a doctored table and prove each check
    actually fires — a gate nobody has watched fail is not a gate.
    """
    passed = True

    # 5 — provenance first: everything below is about one specific file.
    print("provenance")
    passed &= check("vintage and source recorded",
                    bool(table.vintage and table.source_file),
                    f"{table.source_file}, {table.vintage}")
    passed &= check("branch count read from the file, not assumed",
                    table.n > 0, f"{table.n} branches (A38 publishes 37)")
    passed &= check("base year travels with the table",
                    1990 < table.base_year < 2100, str(table.base_year))

    # 1 — the product balance.
    print("\nidentities")
    uses = table.domestic.sum(axis=1) + table.final_uses["total_emplois_finals"]
    residual = np.abs(uses - table.total_output)
    passed &= check(
        "total uses = total resources, per product",
        bool(residual.max() <= BALANCE_TOLERANCE_MEUR),
        f"worst branch {table.branches[int(residual.argmax())]} off by "
        f"{residual.max():.3f} M EUR",
    )
    aggregate = abs(uses.sum() - table.total_output.sum())
    passed &= check("and in aggregate", aggregate <= BALANCE_TOLERANCE_MEUR,
                    f"{aggregate:.3f} M EUR on {table.total_output.sum() / 1e3:,.0f} bn")

    # The balance above is built on "Total des emplois finals", one published column,
    # and stays green while every component beneath it is misread. It did: final
    # consumption came back as households alone, 730 bn short, for as long as nothing
    # added the parts up. These are the checks that catch a wrong column.
    fu = table.final_uses
    for whole, parts in (
        ("consommation_finale",
         ("consommation_finale_menages", "consommation_finale_apu",
          "consommation_finale_isblsm")),
        ("formation_brute_capital", ("fbcf", "objets_de_valeur", "variation_stocks")),
        ("total_emplois_finals",
         ("consommation_finale", "formation_brute_capital", "exportations")),
    ):
        gap = abs(sum(fu[p].sum() for p in parts) - fu[whole].sum())
        passed &= check(f"{whole} = {' + '.join(parts)}", gap <= BALANCE_TOLERANCE_MEUR,
                        f"off by {gap:.3f} M EUR")
    gap = abs(fu["total_emplois_finals"].sum() + table.domestic.sum()
              - fu["total_emplois"].sum())
    passed &= check("total_emplois = total_emplois_finals + intermediate consumption",
                    gap <= BALANCE_TOLERANCE_MEUR, f"off by {gap:.3f} M EUR")

    # 2 — the import matrix. Non-negativity is NOT asserted: it is false on correct
    # data. What is asserted is that the negatives are few and named, and that every
    # quantity propagation will actually divide by stays in range.
    print("\nimports")
    passed &= check("import matrix present and shaped like the domestic one",
                    table.imported.shape == table.domestic.shape, f"{table.imported.shape}")
    for name, matrix in (("domestic", table.domestic), ("imported", table.imported)):
        cells = _negatives(matrix, table.branches)
        passed &= check(f"{name} negatives confined and identified",
                        len(cells) <= MAX_NEGATIVE_CELLS,
                        f"{len(cells)}: {', '.join(cells) if cells else 'none'}")
    combined = table.domestic + table.imported
    with np.errstate(divide="ignore", invalid="ignore"):
        cell_share = np.where(combined > 0, table.imported / np.maximum(combined, 1e-9), 0.0)
    passed &= check("per-cell import share within [0, 1]",
                    bool(((cell_share >= 0) & (cell_share <= 1)).all()),
                    f"{cell_share.min():.4f} to {cell_share.max():.4f}")
    branch_share = table.imported.sum(axis=0) / np.maximum(combined.sum(axis=0), 1e-9)
    passed &= check("per-branch import share of intermediate consumption within [0, 1]",
                    bool(((branch_share >= 0) & (branch_share <= 1)).all()),
                    f"{branch_share.min():.3f} to {branch_share.max():.3f}")
    leakage = table.imported.sum() / combined.sum()
    passed &= check("economy-wide import leakage is a real fraction", 0.0 < leakage < 1.0,
                    f"{leakage:.1%} — the leakage §1 wants computed, not assumed")

    # 3 — invertibility.
    print("\nLeontief")
    output = table.total_output.copy()
    zero_output = [table.branches[i] for i, v in enumerate(output) if v <= 0]
    passed &= check("every branch has positive output", not zero_output,
                    f"zero-output branches: {zero_output}" if zero_output else "")
    coefficients = table.domestic / np.maximum(output, 1e-9)
    radius = float(np.max(np.abs(np.linalg.eigvals(coefficients))))
    passed &= check("spectral radius of A below 1", radius < 1.0, f"rho = {radius:.4f}")
    passed &= check("and comfortably so", radius < SPECTRAL_CEILING,
                    f"ceiling {SPECTRAL_CEILING}")
    try:
        inverse = np.linalg.inv(np.eye(table.n) - coefficients)
    except np.linalg.LinAlgError as error:
        inverse = None
        passed &= check("(I - A) inverts", False, str(error))
    if inverse is not None:
        passed &= check("(I - A) inverts to finite entries", bool(np.isfinite(inverse).all()))
        multipliers = inverse.sum(axis=0)
        # The SIFIM cell puts negative entries in the inverse. The property that has to
        # survive it is the one propagation relies on: a unit of final demand for any
        # branch raises total output, never lowers it.
        passed &= check("every output multiplier at least unity",
                        bool((multipliers >= 1.0 - 1e-6).all()),
                        f"{multipliers.min():.3f} ({table.branches[int(multipliers.argmin())]}) "
                        f"to {multipliers.max():.3f} ({table.branches[int(multipliers.argmax())]})")

    # 4 — employment coefficients.
    print(f"\nemployment ({table.base_year})")
    passed &= check("one row per branch", len(jobs) == table.n, f"{len(jobs)}")
    passed &= check("positive and finite", bool((jobs > 0).all() and np.isfinite(jobs).all()),
                    f"total {jobs.sum():,.0f} thousand persons")
    per_output = jobs / (output / 1e3)
    passed &= check("coefficients positive and finite",
                    bool((per_output > 0).all() and np.isfinite(per_output).all()),
                    f"{per_output.min():.3f} ({table.branches[int(per_output.argmin())]}) to "
                    f"{per_output.max():.2f} ({table.branches[int(per_output.argmax())]}) per M EUR")

    return passed


def main(vintage: str = "2023SD") -> int:
    print(f"TES reconnaissance — vintage {vintage}\n")
    table = tes.load(vintage)
    jobs = tes.employment(table.branches, year=table.base_year)
    passed = audit(table, jobs)
    print()
    if passed:
        print("M0 gate PASSED — the table may be propagated through. See docs/M0_TES.md.")
        return 0
    print("M0 gate FAILED — no propagation code until this is green.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
