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


#: Raw inputs whose canonical URL is known. Anything in data/raw/ that is NOT here
#: gets manifested with a null url and an explicit "not reproducible" note, because
#: an unmanifested file that backs a figure is exactly the gap D-026 closes: a
#: checksum without a URL proves the file has not changed, not where it came from.
KNOWN_SOURCES: dict[str, tuple[str, str]] = {
    "FD_EEC_2024.parquet": (
        "https://www.insee.fr/fr/statistiques/fichier/8632441/FD_EEC_2024.parquet",
        "Enquête Emploi en Continu 2024, fichier détail",
    ),
    "Varmod_EEC_2024.csv": (
        "https://www.insee.fr/fr/statistiques/fichier/8632441/Varmod_EEC_2024.csv",
        "Dictionnaire des variables et modalités de l'EEC 2024",
    ),
    "dgfip_stat_39_impot_benefice_2024.pdf": (
        "https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/"
        "0_etudes_et_stats/0_publications/dgfip_statistiques/2025/num39_09/"
        "dgfip_stat_39_limpot-sur-le-benefice-2024-des-entreprises_publi.pdf",
        "DGFiP Statistiques n° 39 — l'impôt sur le bénéfice 2024 des entreprises",
    ),
    "ipp_rapport60_impots_production_2025.pdf": (
        "https://www.ipp.eu/wp-content/uploads/2025/10/FS_ImpotsProductions-9.pdf",
        "IPP Rapport n° 60, octobre 2025 — « La baisse des impôts de production : "
        "ciblage et évaluation ». The evaluation behind the C4 behavioural channel; "
        "its confidence intervals are read from its own tables, never from a summary "
        "(D-026, D-031).",
    ),
    "insee_TES_symetrique_A38_2023SD.xlsx": (
        "https://www.insee.fr/fr/statistiques/fichier/8574722/"
        "TES_symetrique_A38_2023SD.xlsx",
        "INSEE, comptes nationaux base 2020 — tableau entrées-sorties symétrique A38, "
        "année 2023, version semi-définitive. Domestic and import matrices; the basis "
        "of the L4 sectoral composition and its import-leakage correction (D-049).",
    ),
    "insee_TES_symetrique_A38_2022DEF.xlsx": (
        "https://www.insee.fr/fr/statistiques/fichier/8574722/"
        "TES_symetrique_A38_2022DEF.xlsx",
        "The same, année 2022, version définitive — carried so the vintage choice can "
        "be checked against a settled year rather than only asserted.",
    ),
    "insee_cn2024_t6208_emploi_par_branche_a38.xlsx": (
        "https://www.insee.fr/fr/statistiques/fichier/8574683/T_6208.xlsx",
        "INSEE, comptes nationaux — tableau 6.208, emploi intérieur total par branche "
        "en nombre de personnes (38 postes). Same accounts vintage as the TES; the "
        "source of the employment coefficients.",
    ),
    "insee_ia112_taux_implicite_is_2016_2022.xlsx": (
        "https://www.insee.fr/fr/statistiques/fichier/8630968/IA112.xlsx",
        "INSEE Analyses n° 112 — taux implicite d'IS par taille d'entreprise",
    ),
    "insee_entfra2023_fiche36_impot_societes.pdf": (
        "https://www.insee.fr/fr/statistiques/fichier/7678564/ENTFRA23-F20.pdf",
        "INSEE Références, Les entreprises en France 2023, fiche « Impôt sur les "
        "sociétés » — the source of P_LOSS_BY_SIZE, the one figure in the cell table "
        "read from a publication rather than computed (D-026)",
    ),
    "ccss_mai2026_comptes_secu_resultats2025.pdf": (
        "https://www.securite-sociale.fr/files/live/sites/SSFR/files/medias/CCSS/2026/"
        "CCSS%20mai%202026_assembl%c3%a9_V2.pdf",
        "Rapport à la Commission des comptes de la Sécurité sociale, mai 2026 — C3S",
    ),
    "insee_cn2025_t3217_principaux_impots_par_categorie.xlsx": (
        "https://www.insee.fr/fr/statistiques/fichier/8988845/t_3217_fr.xlsx",
        "INSEE comptes nationaux, tableau 3.217 — principaux impôts par catégorie",
    ),
    "urssaf_c3s_notice_mars2026.pdf": (
        "https://www.urssaf.fr/files/live/sites/urssaffr/files/outils-documentation/"
        "guides/C3S-Notice.pdf",
        "Notice URSSAF C3S — confirms the base is prior-year turnover",
    ),
    "Dictionnaire_EEC_2024.pdf": (
        "https://www.insee.fr/fr/statistiques/fichier/8632441/"
        "EEC%202024%20_%20Dictionnaire%20des%20codes%20_%20Fichier%20detail_2024.pdf",
        "Dictionnaire des codes de l'EEC 2024",
    ),
    "insee_esane2023_caracteristiques_par_taille.xlsx": (
        "https://www.insee.fr/fr/statistiques/fichier/8611562/"
        "DD_esane23m23ep_caracteristiques_taille.xlsx",
        "INSEE Ésane 2023 — caractéristiques comptables et financières par secteur "
        "(NAF a10/a21/a88/a272) et catégorie d'entreprise. The firm cell table's shape.",
    ),
    "insee_focus372_tissu_productif_categorie_2023.xlsx": (
        "https://www.insee.fr/fr/statistiques/fichier/8675639/IF372.xlsx",
        "INSEE Focus n° 372 — le tissu productif par catégorie d'entreprise. Splits "
        "Ésane's merged ETI/GE class and publishes the value-added dispersion.",
    ),
    "dgfip_stat_39_impot_benefice_2024_donnees.xlsx": (
        "https://www.impots.gouv.fr/sites/default/files/media/9_statistiques/"
        "0_etudes_et_stats/0_publications/dgfip_statistiques/2025/num39_09/"
        "dgfip_stat_39_limpot-sur-le-benefice-2024-des-entreprises.xlsx",
        "DGFiP Statistiques n° 39 — données des figures. The fiscal control totals: "
        "IS-liable firm count, résultat fiscal and bénéfices by size and by sector.",
    ),
}


def cmd_manifest(_: argparse.Namespace) -> int:
    """Re-record the checksums of every raw input, named or not."""
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
    from impots.population.ingest import QUARANTINE

    known = {**known, **KNOWN_SOURCES}
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    candidates = [f for f in RAW.iterdir() if f.is_file() and f.name != "MANIFEST.json"]
    candidates += [f for f in QUARANTINE.iterdir() if f.is_file()]

    entries, quarantined, released = [], 0, 0
    for file in sorted(candidates, key=lambda f: f.name):
        sourced = file.name in known
        # A sourced file belongs in data/raw/; an unsourced one belongs out of the way,
        # so that its presence in the tree can never be mistaken for provenance (D-028).
        # Adding a URL to KNOWN_SOURCES releases it on the next run.
        target = (RAW if sourced else QUARANTINE) / file.name
        if file != target:
            file.rename(target)
            released += sourced
            quarantined += not sourced
        url, description = known.get(file.name, (None, (
            "Source URL not recorded, so nothing computed from this file is "
            "reproducible by a third party. Quarantined under data/raw/_unsourced/ "
            "(D-028): the checksum still tracks it, and pipeline code refuses to open "
            "it. Re-source it if something needs it."
        )))
        entries.append({"filename": file.name, "path": target, "url": url,
                        "quarantined": not sourced,
                        "licence": "Licence Ouverte / Etalab 2.0" if url else "unknown",
                        "description": description})
    path = write_manifest(entries)
    sourced_count = sum(1 for e in entries if e["url"])
    print(f"wrote {path} with {len(entries)} inputs, {sourced_count} sourced")
    if quarantined:
        print(f"  moved {quarantined} unsourced file(s) to data/raw/_unsourced/")
    if released:
        print(f"  released {released} newly-sourced file(s) back to data/raw/")
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
    result = run(population, year=args.year, reform=reform, tier=args.tier,
                 sample=args.sample, impute_niches=args.impute_niches)
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

    # `impute_niches` is off by default, and that is a reported fact rather than a
    # detail: two lines of the report — the net IR yield and the count of foyers
    # imposés — compare a figure that is GROSS of réductions and crédits against a
    # target that is net of them, and they do so only because this flag is off. The
    # zero-masked sweep (D-073) measured the second at 6.4 points. There was no way to
    # produce the other reading at all until this flag existed.
    result = run(population, year=args.year, tier="full", sample=args.sample,
                 impute_niches=args.impute_niches)
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


def cmd_emtr(args: argparse.Namespace) -> int:
    """Compute the marginal-rate distribution and fold it into the baseline artifact.

    One extra full-tier pass with salaries bumped by 100 EUR. Minutes, and worth it:
    France's EMTR distribution is a product in its own right, not a diagnostic.
    """
    from impots.behavioural import emtr as emtr_module
    from impots.population.build import PROCESSED

    population = PROCESSED / f"population_{args.vintage}.parquet"
    if not population.exists():
        print(f"{population} not found — run `impots population build` first",
              file=sys.stderr)
        return 1

    result = emtr_module.compute(
        pl_read(population), year=args.year, sample=args.sample,
        vintage=args.vintage if args.sample is None else None,
    )
    rows = emtr_module.distribution(result)
    print(f"marginal rates for {spaced(result.households.height)} households "
          f"in {result.timings}")
    print(f"  guards {result.guards}")
    print(f"\n  {'decile':>6} {'ménages':>12} {'médiane':>9} {'moyenne':>9}")
    for row in rows:
        print(f"  {row['decile']:>6} {spaced(row['households']):>12} "
              f"{row['emtr_median']:>8.1%} {row['emtr_mean']:>8.1%}")

    baseline_path = PROCESSED / f"baseline_{args.vintage}.json"
    if baseline_path.exists():
        summary = json.loads(baseline_path.read_text(encoding="utf-8"))
        summary["emtr_deciles"] = rows
        baseline_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\n  folded into {baseline_path.name}")
    return 0


def cmd_firms_reconcile(args: argparse.Namespace) -> int:
    from impots.entreprises import aggregate as firm_aggregate
    from impots.entreprises import reconcile as firm_reconcile
    from impots.entreprises import runner as firm_runner
    from impots.entreprises.build import PROCESSED as FIRM_PROCESSED

    path = FIRM_PROCESSED / f"firms_{args.vintage}.parquet"
    if not path.exists():
        print(f"{path} not found — run `impots entreprises build` first", file=sys.stderr)
        return 1

    manifest_path = FIRM_PROCESSED / f"firms_{args.vintage}.manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists()
        else {"cells_are_synthetic": True, "population": {}}
    )
    result = firm_runner.run(pl_read(path), year=args.year)
    agg = firm_aggregate.aggregate(result.firms)
    synthetic = bool(manifest.get("cells_are_synthetic", True))
    report = firm_reconcile.write(
        agg, args.vintage, args.year, synthetic,
        manifest.get("population", {}).get("fiscal_to_accounting"),
    )
    print(f"wrote {report}")

    lines = firm_reconcile.build_lines(
        agg, args.year, firm_reconcile._vintage_year(args.vintage)
    )
    outside = [line for line in lines if line.status.startswith("OUTSIDE")]
    print(f"  {len(lines)} lines, {len(outside)} outside tolerance")
    for line in outside:
        print(f"    {line.label:38} {line.residual:+7.1%} (±{line.tolerance:.0%})")
    if synthetic:
        print(
            "\n  NOTE: the cell table is the committed fixture and is invented. These "
            "residuals\n  are arithmetic about a fiction and validate nothing."
        )
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


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface, separate from running it so that tests can read it.

    A flag that exists only inside `main` can be asserted about only by grepping, and
    grep is exactly what let a dead parameter survive a standing rule (see
    `tests/knob_cases.py`).
    """
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
    runner_parser.add_argument(
        "--impute-niches", action="store_true",
        help="draw réduction and crédit d'impôt bases from the published DGFiP decile "
             "table before taking the figures (D-066). It is a CALIBRATION: the national "
             "niche total then matches DGFiP by construction")
    runner_parser.set_defaults(func=cmd_run)

    reconciler = actions.add_parser("reconcile", help="generate reports/reconciliation.md")
    reconciler.add_argument("--vintage", default="2024")
    reconciler.add_argument("--year", type=int, default=2024)
    reconciler.add_argument("--sample", type=int, default=None)
    reconciler.add_argument(
        "--impute-niches", action="store_true",
        help="draw réduction and crédit d'impôt bases from the published decile table "
             "(D-066). Off by default, which leaves the net-IR and foyers-imposés "
             "lines comparing a gross figure against a net target (D-073)")
    reconciler.add_argument("--compare-unraked", action="store_true",
                            help="also build and run the population without raking, and "
                                 "show every line before and after (D-017)")
    reconciler.set_defaults(func=cmd_reconcile)

    emtr_parser = actions.add_parser(
        "emtr", help="marginal-rate distribution, folded into the baseline artifact"
    )
    emtr_parser.add_argument("--vintage", default="2024")
    emtr_parser.add_argument("--year", type=int, default=2024)
    emtr_parser.add_argument("--sample", type=int, default=None,
                             help="households to sample; omit for the full population")
    emtr_parser.set_defaults(func=cmd_emtr)

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

    firm_reconciler = firm_actions.add_parser(
        "reconcile", help="generate reports/reconciliation_entreprises.md"
    )
    firm_reconciler.add_argument("--vintage", default="fixture")
    firm_reconciler.add_argument("--year", type=int, default=2026)
    firm_reconciler.set_defaults(func=cmd_firms_reconcile)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
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
