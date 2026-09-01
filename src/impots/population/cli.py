"""`impots …` — the command line for both populations.

Population runs are batch jobs: a full-tier run over 199 451 households is
minutes, not seconds (§1.1), so the CLI writes parquet and the API reads it. The
only thing that ever runs behind an HTTP request is the bounded quick tier.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from impots.api.schemas import ReformSpec
from impots.population import aggregate as aggregate_module
from impots.population import reconcile as reconcile_module
from impots.population.build import PROCESSED, build
from impots.population.ingest import RAW, write_manifest
from impots.population.runner import RUNS_DIR, run

#: Limitations stated in the reconciliation report and in the UI. Measured, not
#: guessed — every figure here comes out of a population build.
KNOWN_LIMITATIONS = [
    "**No income is observed.** The EEC fichier détail carries no wage, pension or "
    "benefit of any kind (docs/M0_RECON.md). Every euro in this population is drawn "
    "from a published distribution and calibrated to a published total.",
    "**No self-employment income.** 3.87 M people are recorded in employment as "
    "indépendants and receive nothing, which understates their households and "
    "overstates their entitlement to means-tested benefits.",
    "**No capital income, no property income.** The top of the distribution is a "
    "construction; nothing above roughly the 95th percentile is publishable.",
    "**No réductions or crédits d'impôt.** Worth 19.5 bn nationally, which is why the "
    "income tax line is compared against the barème rather than the net yield.",
    "**Children under 15 are synthesised**, not observed: their number is drawn from "
    "published family-size margins and their ages uniformly. Household composition "
    "above 15 is real.",
    "**Age is banded.** The EEC gives five age groups; exact ages are drawn inside "
    "them, so any threshold that does not fall on a band edge is fuzzy for an "
    "individual household and only right on average.",
    "**Benefits assume 100 % take-up.** OpenFisca computes legal entitlement; DREES "
    "measures non-take-up of RSA at 33-37 % of eligible households.",
    "**Assortative mating is absent.** Two earners in a household are drawn "
    "independently, which flattens the top of the household income distribution.",
]


def spaced(value: float, decimals: int = 0) -> str:
    """A number with French thousands separators.

    Exists because `f"...{x:,}...".replace(",", " ")` over a whole string also
    replaces the commas in the prose around it. That has now happened three times
    — in a report caveat, in a CLI line, and in a dict repr — so the formatting
    lives in one place that can only ever see a number.
    """
    return f"{value:,.{decimals}f}".replace(",", " ")


def _load_reform(path: str | None) -> ReformSpec | None:
    if path is None:
        return None
    return ReformSpec.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def _print_aggregates(agg: aggregate_module.Aggregates) -> None:
    print(f"\n  households {agg.households / 1e6:.2f} M · persons {agg.persons / 1e6:.2f} M")
    print("\n  weighted totals (bn EUR):")
    for name, value in agg.totals.items():
        print(f"    {name:22} {value / 1e9:9.1f}")
    if agg.deciles:
        print("\n  deciles of niveau de vie (EUR per consumption unit per year):")
        for row in agg.deciles:
            line = f"    D{row.decile:<2} mean {spaced(row.mean_niveau_de_vie):>9}"
            if row.mean_delta is not None:
                sign = "+" if row.mean_delta >= 0 else "−"
                line += (f"   Δ {sign}{spaced(abs(row.mean_delta)):>8}"
                         f"   winners {row.share_winners:5.1%}"
                         f"  losers {row.share_losers:5.1%}")
            print(line)
    if agg.reform_cost is not None:
        direction = "costs" if agg.reform_cost > 0 else "raises"
        print(f"\n  the reform {direction} {abs(agg.reform_cost) / 1e9:.1f} bn EUR "
              "of household disposable income")


def cmd_manifest(_: argparse.Namespace) -> int:
    """Re-record the checksums of the raw inputs."""
    known = {
        "FD_EEC_2024.parquet": (
            "https://www.insee.fr/fr/statistiques/fichier/8632441/FD_EEC_2024.parquet",
            "Enquête Emploi en Continu 2024, fichier détail",
        ),
        "Varmod_EEC_2024.csv": (
            "https://www.insee.fr/fr/statistiques/fichier/8632441/Varmod_EEC_2024.csv",
            "Dictionnaire des variables et modalités de l'EEC 2024",
        ),
    }
    entries = [
        {"filename": name, "url": url, "licence": "Licence Ouverte / Etalab 2.0",
         "description": description}
        for name, (url, description) in known.items()
        if (RAW / name).exists()
    ]
    path = write_manifest(entries)
    print(f"wrote {path} with {len(entries)} inputs")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    path, provenance = build(vintage=args.vintage, seed=args.seed, raking=not args.no_raking)
    print(f"wrote {path}")
    print(f"  {spaced(provenance['rows'])} persons in "
          f"{spaced(provenance['households'])} households")
    incomes = provenance["incomes"]
    print(f"  employees {incomes['employees'] / 1e6:.2f} M · "
          f"gross wages {incomes['gross_wages_after_calibration'] / 1e9:.0f} bn "
          f"(calibration factor {incomes['wage_calibration_factor']:.4f})")
    print(f"  pensioners {incomes['pensioners'] / 1e6:.2f} M · "
          f"pensions {incomes['pensions_total'] / 1e9:.0f} bn")
    print(f"  synthesised children {provenance['skeleton']['children_synthesised']:,}")
    raking = provenance.get("raking")
    if raking:
        print(f"  raked in {raking['iterations']} iterations · "
              f"weight ratios {raking['weight_ratio_range'][0]:.2f}-"
              f"{raking['weight_ratio_range'][1]:.2f} · "
              f"{raking['clipped_households']} clipped · "
              f"effective sample {spaced(raking['effective_sample_size'])} households")
        for name, before in raking["fit_before"].items():
            print(f"    {name:16} worst miss {before:6.2%} -> {raking['fit_after'][name]:6.2%}")
    else:
        print("  NOT raked (--no-raking)")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    population = PROCESSED / f"population_{args.vintage}.parquet"
    if not population.exists():
        print(f"{population} not found — run `impots population build` first", file=sys.stderr)
        return 1
    reform = _load_reform(args.reform)
    result = run(population, year=args.year, reform=reform, tier=args.tier, sample=args.sample)
    print(f"ran {result.n_households:,} households / {result.n_persons:,} persons "
          f"({result.tier} tier{f', sample {result.sampled:,}' if result.sampled else ''})")
    print(f"  timings {result.timings} · guards {result.guards}")

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"run_{args.vintage}_{args.tier}{'_reform' if reform else ''}.parquet"
    result.households.write_parquet(RUNS_DIR / name)
    print(f"  wrote {RUNS_DIR / name}")

    _print_aggregates(aggregate_module.aggregate(result.households))
    return 0


def _write_baseline_summary(agg, vintage: str, sampled: int | None) -> Path:
    """The precomputed baseline the API serves.

    `GET /population/baseline` must not run the engine: a full-tier population run
    is minutes. It reads this file, which the reconcile step writes.
    """
    lines = [
        {"label": line.label, "simulated": line.simulated, "published": line.published,
         "residual": line.residual, "use": line.use, "status": line.status,
         "source": line.source}
        for line in reconcile_module.build_lines(agg)
    ]
    summary = {
        "vintage": vintage,
        "branch": "A' — EEC household structure, synthetic incomes (D-012)",
        "households": agg.households,
        "persons": agg.persons,
        "sampled_households": sampled,
        "totals": agg.totals,
        "counts": agg.counts,
        "deciles": [vars(row) for row in agg.deciles],
        "reconciliation": lines,
        "limitations": KNOWN_LIMITATIONS,
    }
    path = PROCESSED / f"baseline_{vintage}.json"
    path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def cmd_reconcile(args: argparse.Namespace) -> int:
    population = PROCESSED / f"population_{args.vintage}.parquet"
    if not population.exists():
        print(f"{population} not found — run `impots population build` first", file=sys.stderr)
        return 1
    unraked = None
    if args.compare_unraked:
        # Build the same population without the calibration step and run it, so the
        # report can show what raking did to every line (D-017) rather than only to
        # the margins it was fitted on.
        #
        # Run FIRST and released before the raked pass begins. A full-tier run over
        # 199 451 households holds a couple of GB; holding two at once is what an
        # 8 GB machine gets killed for, and the two runs need nothing from each
        # other except their aggregates.
        import gc

        from impots.population.build import build_frame

        print("  building and running the unraked vintage for comparison…")
        frame, _ = build_frame(raking=False)
        unraked_result = run(frame, year=args.year, tier="full", sample=args.sample)
        unraked = aggregate_module.aggregate(unraked_result.households)
        del frame, unraked_result
        gc.collect()

    result = run(population, year=args.year, tier="full", sample=args.sample)
    agg = aggregate_module.aggregate(result.households)

    path = reconcile_module.write(
        agg, vintage=args.vintage, notes=KNOWN_LIMITATIONS, unraked=unraked,
        sample=args.sample,
    )
    print(f"wrote {path}")
    print(f"wrote {_write_baseline_summary(agg, args.vintage, args.sample)}")
    was = (
        {line.label: line.residual for line in reconcile_module.build_lines(unraked)}
        if unraked else {}
    )
    for line in reconcile_module.build_lines(agg):
        if line.use != "validation":
            continue
        residual = "—" if line.residual is None else f"{line.residual:+7.1%}"
        previous = was.get(line.label)
        shift = "" if previous is None else f"   (was {previous:+7.1%})"
        print(f"  {line.label:34} {residual}  {line.status}{shift}")
    return 0


# --------------------------------------------------------------------------- #
# firms
# --------------------------------------------------------------------------- #
def cmd_firms_build(args: argparse.Namespace) -> int:
    from pathlib import Path

    from impots.entreprises.build import build as build_firms

    path, provenance = build_firms(
        cells_path=Path(args.cells) if args.cells else None, seed=args.seed
    )
    stats = provenance["population"]
    print(f"wrote {path}")
    if provenance["cells_are_synthetic"]:
        print("  NOTE: built from the synthetic CI fixture, not from SIRENE x ESANE. "
              "Nothing computed from it is a claim about France.")
    print(f"  {stats['cells']} cells -> {spaced(stats['rows'])} synthetic firms "
          f"standing for {stats['weighted_firms'] / 1e6:.2f} M")
    print(f"  turnover {spaced(stats['weighted_turnover'] / 1e9)} bn · "
          f"value added {spaced(stats['weighted_value_added'] / 1e9)} bn · "
          f"taxable profit {spaced(stats['weighted_taxable_profit'] / 1e9)} bn")
    print(f"  loss-making {stats['share_loss_making']:.1%} · "
          f"fiscal/accounting ratio {stats['fiscal_to_accounting']}")
    worst = max(abs(e) for e in stats["calibration_error"].values())
    print(f"  published cell totals reproduced to {worst:.1e} relative")
    return 0


def cmd_firms_run(args: argparse.Namespace) -> int:
    from impots.entreprises import aggregate as firm_aggregate
    from impots.entreprises import runner as firm_runner
    from impots.entreprises.build import PROCESSED as FIRM_PROCESSED
    from impots.entreprises.reforms import FirmReformSpec

    path = FIRM_PROCESSED / f"firms_{args.vintage}.parquet"
    if not path.exists():
        print(f"{path} not found — run `impots entreprises build` first", file=sys.stderr)
        return 1

    reform = None
    if args.reform:
        reform = FirmReformSpec.model_validate(
            json.loads(Path(args.reform).read_text(encoding="utf-8"))
        )
    result = firm_runner.run(pl_read(path), year=args.year, reform=reform)
    print(f"priced {spaced(result.n_firms)} firms in {result.timings}")
    print(f"  guards {result.guards}")

    agg = firm_aggregate.aggregate(result.firms)
    print(f"\n  {agg.n_firms / 1e6:.2f} M firms · turnover {spaced(agg.turnover / 1e9)} bn · "
          f"{agg.share_zero_is:.1%} pay no IS")
    print("\n  weighted totals (bn EUR):")
    for name, value in agg.totals.items():
        line = f"    {name:26} {value / 1e9:9.2f}"
        if name in agg.deltas:
            line += f"   Δ {agg.deltas[name] / 1e9:+8.2f}"
        print(line)
    print("\n  effective rate on profit, by size:")
    for row in agg.by_size:
        line = (f"    {row.taille:6} n={row.n_firms / 1e6:6.3f} M  "
                f"mean {row.mean_effective_rate:6.1%}  median {row.median_effective_rate:6.1%}  "
                f"no tax {row.share_zero_tax:5.1%}")
        print(line)
    if agg.cells and agg.deltas:
        print("\n  most affected sector x size cells:")
        for cell in sorted(agg.cells, key=lambda c: -abs(c.mean_delta or 0.0))[:6]:
            print(f"    {cell.naf_section} {cell.taille:6} mean Δ "
                  f"{spaced(cell.mean_delta or 0.0):>12} EUR   "
                  f"affected {cell.share_affected:5.1%}")
    if agg.reform_cost is not None:
        direction = "costs" if agg.reform_cost > 0 else "raises"
        print(f"\n  the reform {direction} {abs(agg.reform_cost) / 1e9:.2f} bn EUR")
    return 0


def pl_read(path: object) -> object:
    import polars as pl

    return pl.read_parquet(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="impots", description=__doc__)
    subcommands = parser.add_subparsers(dest="group", required=True)
    population = subcommands.add_parser("population", help="the L1 synthetic population")
    actions = population.add_subparsers(dest="action", required=True)

    manifest = actions.add_parser("manifest", help="record checksums of the raw inputs")
    manifest.set_defaults(func=cmd_manifest)

    builder = actions.add_parser("build", help="build the population parquet")
    builder.add_argument("--vintage", default="2024")
    builder.add_argument("--seed", type=int, default=None)
    builder.add_argument("--no-raking", action="store_true",
                         help="skip the calibration step (D-017); used to produce the "
                              "unraked comparison in the reconciliation report")
    builder.set_defaults(func=cmd_build)

    runner_parser = actions.add_parser("run", help="run a reform over the population")
    runner_parser.add_argument("--vintage", default="2024")
    runner_parser.add_argument("--year", type=int, default=2024)
    runner_parser.add_argument("--reform", help="path to a ReformSpec JSON file")
    runner_parser.add_argument("--tier", choices=["light", "full"], default="full")
    runner_parser.add_argument("--sample", type=int, default=None,
                               help="run a deterministic subsample of N households")
    runner_parser.set_defaults(func=cmd_run)

    reconciler = actions.add_parser("reconcile", help="generate reports/reconciliation.md")
    reconciler.add_argument("--vintage", default="2024")
    reconciler.add_argument("--year", type=int, default=2024)
    reconciler.add_argument("--sample", type=int, default=None)
    reconciler.add_argument("--compare-unraked", action="store_true",
                            help="also build and run the population without raking, and "
                                 "show every line before and after (D-017)")
    reconciler.set_defaults(func=cmd_reconcile)

    firms = subcommands.add_parser("entreprises", help="the firm module")
    firm_actions = firms.add_subparsers(dest="action", required=True)

    firm_builder = firm_actions.add_parser("build", help="build the firm population parquet")
    firm_builder.add_argument("--cells", help="path to a sector x size cell table (JSON); "
                                             "defaults to the synthetic CI fixture")
    firm_builder.add_argument("--seed", type=int, default=None)
    firm_builder.set_defaults(func=cmd_firms_build)

    firm_runner_parser = firm_actions.add_parser("run", help="price a firm-tax reform")
    firm_runner_parser.add_argument("--vintage", default="fixture")
    firm_runner_parser.add_argument("--year", type=int, default=2026)
    firm_runner_parser.add_argument("--reform", help="path to a FirmReformSpec JSON file")
    firm_runner_parser.set_defaults(func=cmd_firms_run)

    args = parser.parse_args(argv)
    if getattr(args, "seed", 0) is None:
        if args.group == "entreprises":
            from impots.entreprises.population import SEED as DEFAULT_SEED
        else:
            from impots.population.skeleton import SEED as DEFAULT_SEED

        args.seed = DEFAULT_SEED
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
