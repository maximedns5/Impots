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

from impots import service
from impots.api.schemas import ReformSpec
from impots.identifiants import millesime
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
    "**Take-up is an expectation by amount.** OpenFisca computes legal entitlement; "
    "the RSA and the prime d'activité are served as each famille's probability of "
    "take-up times its entitlement, calibrated on DREES's non-take-up (n° 1370: 33-37 % "
    "of eligible households for the RSA; n° 1379, not read, 48-52 % for the prime). "
    "Housing aid keeps full take-up: no published national rate was found. The "
    "full-take-up figures stay as `*_droit`.",
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
    "insee_cn2025_t7301_compte_administrations_publiques_S13.xlsx": (
        "https://www.insee.fr/fr/statistiques/fichier/8988833/T_7301_fr.xlsx",
        "INSEE, comptes nationaux annuels base 2020, tableau 7.301 — compte des "
        "administrations publiques (S13), millésime 2025 (1949→2025). D41 et B9 : les "
        "entrées r et p du backtest de dette §6.1.",
    ),
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
    "plfss2026_annexe9_evaluations_prealables.pdf": (
        "https://www.securite-sociale.fr/files/live/sites/SSFR/files/medias/PLFSS/2026/"
        "PLFSS2026-Annexe09-GenerationXBOOK_avec%20couverture.pdf",
        "PLFSS 2026, annexe 9 : évaluations préalables des articles — la part des jours "
        "d'IJ des personnes en ALD, p. 228 (D-312)",
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
                 sample=args.sample, impute_niches=args.impute_niches,
                 impute_capital=args.impute_capital, impute_ij=args.impute_ij)
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
    from impots.population.runner import households_par_lots

    households = households_par_lots(
        population, args.lots, year=args.year, tier="full", sample=args.sample,
        impute_niches=args.impute_niches, impute_capital=args.impute_capital)
    agg = aggregate_module.aggregate(households)

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


def cmd_firms_cells(args: argparse.Namespace) -> int:
    """Écrit `data/processed/firm_cells_{vintage}.json` — le maillon qui manquait."""
    from impots.entreprises.cells import write_cell_table

    path = write_cell_table(vintage=args.vintage)
    print(f"wrote {path}")
    return 0


# data — la chaîne de préparation (impots.donnees)

def _afficher_etats(etats) -> int:
    rouges = [e for e in etats if not e.ok]
    largeur = max(len(e.chemin) for e in etats)
    for e in etats:
        marque = "OK " if e.ok else "KO "
        print(f"  {marque} {e.chemin:<{largeur}}  {e.detail}")
        if not e.ok:
            print(f"      {'':<{largeur}}  → {e.reparer}   ({e.pour})")
    if rouges:
        print(f"\n{len(rouges)} dépendance(s) manquante(s) ou invalide(s) sur {len(etats)}. "
              f"La suite qui les lit échouerait : rien n'est lancé.")
        return 1
    print(f"\n{len(etats)} dépendances présentes et valides.")
    return 0


def _donnees_refusees(commande):
    """Un nom de fichier ou de profil inconnu est un refus lisible, code 2 — pas une
    trace de pile (D-173)."""
    import functools

    @functools.wraps(commande)
    def enveloppe(args: argparse.Namespace) -> int:
        from impots.donnees import DonneesError

        try:
            return commande(args)
        except DonneesError as erreur:
            print(f"refusé : {erreur}", file=sys.stderr)
            return 2

    return enveloppe


@_donnees_refusees
def cmd_data_check(args: argparse.Namespace) -> int:
    from impots import donnees

    print(f"préflight — profil « {args.profile} »")
    return _afficher_etats(donnees.verifier(donnees.profil(args.profile),
                                            profil_nom=args.profile))


@_donnees_refusees
def cmd_data_fetch(args: argparse.Namespace) -> int:
    from impots import donnees

    noms = args.files or donnees.bruts(donnees.profil(args.profile))
    echecs = 0
    for nom in noms:
        resultat = donnees.telecharger(nom)
        echecs += resultat.etat == "échec"
        print(f"  {resultat.etat:<13} {nom}  {resultat.detail}")
    if echecs:
        print(f"\n{echecs} téléchargement(s) en échec sur {len(noms)}.")
        return 1
    return 0


@_donnees_refusees
def cmd_data_prepare(args: argparse.Namespace) -> int:
    from impots import donnees

    telechargements, etats = donnees.preparer(args.profile)
    for t in telechargements:
        print(f"  {t.etat:<13} {t.fichier}  {t.detail}")
    print()
    return _afficher_etats(etats)


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


# --------------------------------------------------------------------------- #
# F2 — scenarios, A/B, and the budget-neutral solver
# --------------------------------------------------------------------------- #


def _scenario_dir(args: argparse.Namespace) -> Path | None:
    return Path(args.dir) if getattr(args, "dir", None) else None


def cmd_scenario_save(args: argparse.Namespace) -> int:
    """Register a scenario. Dated at save time, and never overwritten.

    The date is stamped here rather than taken from a flag: a pre-registration whose
    date the author chooses is not one.
    """
    from datetime import date as _date

    from impots import scenarios as scenarios_module

    try:
        reform = _load_reform(args.reform)
    except OSError as error:
        print(f"--reform illisible : {error}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as error:
        print(f"--reform n'est pas du JSON : {error}", file=sys.stderr)
        return 1
    except Exception as error:  # pydantic ValidationError, a ValueError subclass
        print(f"--reform ne valide pas : {error}", file=sys.stderr)
        return 1
    if reform is None:
        print("--reform is required: a scenario is a reform with provenance attached",
              file=sys.stderr)
        return 1
    firm_reform = None
    if args.firm_reform is not None:
        from impots.entreprises.reforms import FirmReformSpec

        try:
            firm_reform = FirmReformSpec.model_validate(
                json.loads(Path(args.firm_reform).read_text(encoding="utf-8")))
        except OSError as error:
            print(f"--firm-reform illisible : {error}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as error:
            print(f"--firm-reform n'est pas du JSON : {error}", file=sys.stderr)
            return 1
        except Exception as error:  # pydantic ValidationError, a ValueError subclass
            print(f"--firm-reform ne valide pas : {error}", file=sys.stderr)
            return 1
    try:
        scenario = scenarios_module.Scenario(
            name=args.name, reform=reform, year=args.year,
            created=_date.today().isoformat(), source=args.source,
            note=args.note or "", tags=tuple(args.tag or ()), firm_reform=firm_reform)
        path = scenario.save(_scenario_dir(args))
    except scenarios_module.ScenarioError as error:
        print(str(error), file=sys.stderr)
        return 1
    knobs = sorted([*reform.model_dump(exclude_none=True),
                    *(firm_reform.model_dump(exclude_none=True) if firm_reform else {})])
    print(f"enregistré {path}")
    print(f"  {len(knobs)} bouton(s) : {', '.join(knobs)}")
    print(f"  daté du {scenario.created} — le fichier ne sera pas réécrit")
    return 0


def cmd_scenario_list(args: argparse.Namespace) -> int:
    from impots import scenarios as scenarios_module

    directory = _scenario_dir(args)
    names = scenarios_module.available(directory)
    if not names:
        print("aucun scénario enregistré")
        return 0
    for name in names:
        try:
            scenario = scenarios_module.load(name, directory)
        except scenarios_module.ScenarioError as error:
            # Named, and the listing carries on. A truncated write used to abort the
            # whole command with a JSONDecodeError, taking every scenario that sorts
            # after it down with the bad one.
            print(f"  {name:24} ILLISIBLE — {error}")
            continue
        knobs = len(scenario.reform.model_dump(exclude_none=True))
        print(f"  {name:24} {scenario.created}  {knobs:2} bouton(s)  {scenario.source}")
    return 0


def cmd_scenario_show(args: argparse.Namespace) -> int:
    from impots import scenarios as scenarios_module

    try:
        scenario = scenarios_module.load(args.name, _scenario_dir(args))
    except scenarios_module.ScenarioError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(scenario.to_dict(), indent=2, ensure_ascii=False))
    return 0


def cmd_scenario_compare(args: argparse.Namespace) -> int:
    """Price two scenarios and lay the layers side by side.

    Only the mechanical layer is differenced, and the report says so where a banded
    layer appears: the difference of two intervals is an interval.
    """
    import polars as pl

    from impots import scenarios as scenarios_module

    directory = _scenario_dir(args)
    try:
        left = scenarios_module.load(args.a, directory)
        right = scenarios_module.load(args.b, directory)
    except scenarios_module.ScenarioError as error:
        print(str(error), file=sys.stderr)
        return 1

    population = PROCESSED / f"population_{args.vintage}.parquet"
    if not population.exists():
        print(f"{population} not found — run `impots population build` first",
              file=sys.stderr)
        return 1
    frame = pl.read_parquet(population)

    def price(scenario):
        return scenarios_module.mechanical_price(
            scenario, frame=frame, households=args.sample)

    comparison = scenarios_module.compare(left, right, price)
    width = max(len(left.name), len(right.name), 12)
    print(f"\n  {'':22} {left.name:>{width}} {right.name:>{width}}")
    print(f"  {'-' * (24 + 2 * width)}")
    for layer in comparison.layers:
        if layer.comparable:
            print(f"  {layer.layer:22} {layer.a / 1e9:>{width}.2f} "
                  f"{layer.b / 1e9:>{width}.2f}   (md EUR)")
        else:
            print(f"  {layer.layer:22} {layer.a!s:>{width}} {layer.b!s:>{width}}")
        if layer.note:
            print(f"    {layer.note}")
    gap = comparison.mechanical_gap
    if gap is not None:
        print(f"\n  écart mécanique : {gap / 1e9:+.2f} md EUR "
              f"({right.name} moins {left.name})")
    print(f"\n  Sous-échantillon de {args.sample:,} ménages repondérés."
          .replace(",", " "))
    print("  Les étages en bande sont AFFICHÉS et non DIFFÉRENCIÉS : la différence de "
          "deux\n  intervalles est un intervalle, pas un nombre.")
    return 0


def cmd_scenario_solve(args: argparse.Namespace) -> int:
    """Root-find one knob against the MECHANICAL cost. Refuses anything else."""
    import polars as pl

    from impots import scenarios as scenarios_module

    # FIRST, before the parquet is read and before a single household is priced. The
    # module makes `refuse_banded` public precisely so a caller can ask the question
    # without paying for the answer, and a CLI that loads the population and only then
    # refuses has thrown that away.
    try:
        scenarios_module.refuse_banded(args.quantity)
    except scenarios_module.ScenarioError as error:
        print(f"\n{error}", file=sys.stderr)
        return 1

    directory = _scenario_dir(args)
    base = None
    if args.on:
        try:
            base = scenarios_module.load(args.on, directory).reform
        except scenarios_module.ScenarioError as error:
            print(str(error), file=sys.stderr)
            return 1

    population = PROCESSED / f"population_{args.vintage}.parquet"
    if not population.exists():
        print(f"{population} not found — run `impots population build` first",
              file=sys.stderr)
        return 1
    frame = pl.read_parquet(population)

    try:
        price = scenarios_module.knob_pricer(
            args.knob, year=args.year, base=base, frame=frame, households=args.sample)
    except scenarios_module.ScenarioError as error:
        print(str(error), file=sys.stderr)
        return 1

    def traced(value: float) -> float:
        cost = price(value)
        print(f"    {args.knob} = {value:<12.6g} coût {cost / 1e9:+8.3f} md EUR",
              flush=True)
        return cost

    print(f"\n  Recherche de racine sur « {args.knob} » dans "
          f"[{args.low:g}, {args.high:g}], cible {args.target / 1e9:+.2f} md EUR")
    if base is not None:
        print(f"  au-dessus du scénario « {args.on} »")
    print(f"  chaque évaluation est un tirage de {args.sample:,} ménages\n"
          .replace(",", " "))

    try:
        result = scenarios_module.solve_budget_neutral(
            args.knob, traced, bracket=(args.low, args.high), target_eur=args.target,
            quantity=args.quantity, tolerance_eur=args.tolerance,
            max_iterations=args.max_evaluations)
    except scenarios_module.ScenarioError as error:
        print(f"\n{error}", file=sys.stderr)
        return 1

    print()
    if result.converged:
        print(f"  {args.knob} = {result.value:.6g}")
        print(f"  coût résiduel {result.cost_at_value / 1e9:+.3f} md EUR "
              f"en {result.iterations} évaluations — {result.message}")
        print(f"\n  Tolérance déclarée : {args.tolerance / 1e9:.2f} md EUR. Elle est "
              f"large parce que le\n  chiffre mécanique lui-même porte le bruit "
              f"d'échantillonnage du tirage (D-074).")
    else:
        print(f"  PAS DE RÉPONSE en {result.iterations} évaluations.")
        print(f"  {result.message}")
        return 2
    return 0


# --------------------------------------------------------------------------- #
# F1 — pre-registered chiffrages
# --------------------------------------------------------------------------- #


def _vieillir_menages(args: argparse.Namespace, year: int, frame):
    """The household population aged from its vintage to the case's year, and what the
    registry keeps of it (D-317). A case whose year is not its population's, without
    declared indices, is refused: it would apply that year's law to another year's
    incomes."""
    from impots import hypotheses
    from impots import uprating as up

    base = int(args.vintage) if args.vintage.isdigit() else None
    if args.vieillir is None:
        if base is None or year != base:
            raise ValueError(
                f"« {args.case} » chiffre {year} sur la population « {args.vintage} » : "
                f"sans indices déclarés (--vieillir), le droit de {year} s'appliquerait aux "
                f"revenus de {args.vintage} (but 10, D-317). Jeux connus : "
                f"{', '.join(sorted(hypotheses.JEUX))}")
        return frame, None
    if base is None:
        raise ValueError(f"le millésime « {args.vintage} » n'a pas d'année : il ne se "
                         "vieillit pas")
    try:
        uprating, record = hypotheses.vieillissement_menages(args.vieillir, base, year)
    except hypotheses.HypothesesError as error:
        raise ValueError(str(error)) from error
    return (frame if uprating is None else up.uprate(frame, year, uprating)), record


def _vieillir_entreprises(args: argparse.Namespace) -> tuple[float, dict | None]:
    """The firm cost's ageing factor from the vintage to the case's year (D-246, D-317).
    A vintage with a year that is not the case's, without declared indices, is refused.
    A vintage with no year, the tests' populations, has nothing to age from: it is
    registered as it is, and refused only if indices are asked for."""
    from impots import hypotheses
    from impots.predictif import firmes

    # The year of the vintage's taxes, not of its name (but 19, étape 1 : the vintage
    # « 2023 » carries the DGFiP's profits of 2024).
    base = firmes.base_year(args.vintage) if args.vintage.isdigit() else None
    if base is None:
        if args.vieillir is not None:
            raise ValueError(f"le millésime « {args.vintage} » n'a pas d'année : il ne se "
                             "vieillit pas")
        return 1.0, None
    if args.vieillir is None:
        if args.year != base:
            raise ValueError(
                f"« {args.case} » chiffre {args.year} sur les entreprises de {base} : sans "
                f"indices déclarés (--vieillir), leur coût resterait celui de {base} (but "
                f"10, D-317). Jeux connus : {', '.join(sorted(hypotheses.JEUX))}")
        return 1.0, None
    try:
        return hypotheses.vieillissement_entreprises(args.vieillir, base, args.year)
    except hypotheses.HypothesesError as error:
        raise ValueError(str(error)) from error


def cmd_chiffrage_register(args: argparse.Namespace) -> int:
    """Price a registered scenario and pre-register the result.

    The pricing happens HERE rather than being passed in, so the figure in the file is one
    this command computed on a tree whose commit it also records. A chiffrage typed by hand
    into a YAML file records a claim; one computed here records a run.
    """
    import polars as pl

    from impots import preregistration as chiffrages_module
    from impots import scenarios as scenarios_module

    try:
        tolerance = chiffrages_module.Tolerance(
            relative=args.tolerance_relative,
            absolute_eur=args.tolerance_absolute,
            rationale=args.tolerance_rationale)
    except chiffrages_module.ChiffrageError as error:
        print(str(error), file=sys.stderr)
        return 1

    directory = Path(args.dir) if args.dir else None
    try:
        scenario = scenarios_module.load(args.scenario)
    except scenarios_module.ScenarioError as error:
        print(str(error), file=sys.stderr)
        return 1

    population = PROCESSED / f"population_{args.vintage}.parquet"
    if not population.exists():
        print(f"{population} not found — run `impots population build` first",
              file=sys.stderr)
        return 1

    frame = pl.read_parquet(population)
    try:
        frame, vieillissement = _vieillir_menages(args, scenario.year, frame)
    except ValueError as error:
        print(f"refusé : {error}", file=sys.stderr)
        return 1

    print(f"  chiffrage de « {args.scenario} » sur {args.sample:,} ménages…"
          .replace(",", " "), flush=True)
    # The consumption imputed for a year past the national accounts follows the prices
    # of the same set that ages the incomes (D-323).
    prix_au_dela = None
    menages_facteurs = None
    if vieillissement is not None:
        from impots import hypotheses
        from impots.population import menages

        prix_au_dela = dict(hypotheses.jeu(vieillissement["jeu"]).prix)
        # The households' data are imputed on the frame brought back to 2024, then aged
        # by the same factors (but 21, étape 4): only from a 2024 vintage.
        if vieillissement["de"] == menages.YEAR:
            menages_facteurs = {"wage": vieillissement["facteur_salaires"],
                                "price": vieillissement["facteur_prix"]}
    # The imputed capital ages with the frame, on its wage index, as in the service's aged
    # view (D-249, D-388).
    capital_index = (vieillissement["facteur_salaires"] if vieillissement is not None
                     else None)
    priced = scenarios_module.mechanical_price(
        scenario, frame=frame, households=args.sample, prix_au_dela=prix_au_dela,
        menages_facteurs=menages_facteurs, capital_index=capital_index)

    try:
        path = chiffrages_module.register(
            args.case, mechanical_eur=priced["mechanical"], tolerance=tolerance,
            population_vintage=args.vintage, sample=args.sample,
            scenario=args.scenario, note=args.note or "", mirror=args.mirror,
            apres_annexe=args.apres_annexe, vieillissement=vieillissement,
            directory=directory)
    except chiffrages_module.ChiffrageError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"préenregistré {path}")
    print(f"  mécanique {priced['mechanical'] / 1e9:+.3f} md EUR")
    print(f"  toléré {tolerance.relative:.0%} ou "
          f"{tolerance.absolute_eur / 1e6:.0f} M EUR, au choix du plus large")
    print("\n  CE FICHIER N'EST PAS ENCORE UN PRÉENREGISTREMENT : le commit l'est.")
    print(f"  `git add {path} && git commit` — tant qu'il n'est pas committé, "
          f"la notation le refusera.")
    return 0


def cmd_chiffrage_register_entreprises(args: argparse.Namespace) -> int:
    """Price a FIRM reform over the firm population and pre-register the result.

    Refuses a population built on synthetic cells, and one that does not declare
    otherwise: a chiffrage on test cells says nothing about France, and the registry
    would put it on the scoreboard beside the real ones.
    """
    import json

    import polars as pl

    from impots import preregistration as chiffrages_module
    from impots.entreprises import build as firm_build
    from impots.entreprises.reforms import FirmReformSpec

    try:
        tolerance = chiffrages_module.Tolerance(
            relative=args.tolerance_relative,
            absolute_eur=args.tolerance_absolute,
            rationale=args.tolerance_rationale)
    except chiffrages_module.ChiffrageError as error:
        print(str(error), file=sys.stderr)
        return 1
    try:
        spec = FirmReformSpec.model_validate_json(Path(args.reform).read_text(encoding="utf-8"))
    except OSError as error:
        print(f"refusé : {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"refusé : {args.reform} n'est pas une réforme entreprises — {error}",
              file=sys.stderr)
        return 1
    if spec.is_empty():
        print("refusé : la réforme est vide, il n'y a rien à chiffrer", file=sys.stderr)
        return 1

    population = firm_build.PROCESSED / f"firms_{args.vintage}.parquet"
    if not population.exists():
        print(f"{population} introuvable — lancer `impots entreprises cells` puis "
              f"`impots entreprises build`", file=sys.stderr)
        return 1
    manifest = firm_build.PROCESSED / f"firms_{args.vintage}.manifest.json"
    synthetic = True
    if manifest.exists():
        try:
            declared = json.loads(manifest.read_text(encoding="utf-8"))
            synthetic = declared.get("cells_are_synthetic", True) is not False
        except (OSError, ValueError, AttributeError):
            synthetic = True
    if synthetic:
        print(f"refusé : la population d'entreprises « {args.vintage} » est bâtie sur des "
              f"cellules synthétiques de test, ou ne déclare pas le contraire. Un chiffrage "
              f"sur elle ne dit rien de la France, et le registre le mettrait au tableau à "
              f"côté des vrais. Construire la population depuis SIRENE × ESANE : "
              f"`impots entreprises cells` puis `impots entreprises build`.",
              file=sys.stderr)
        return 1

    try:
        facteur, vieillissement = _vieillir_entreprises(args)
    except ValueError as error:
        print(f"refusé : {error}", file=sys.stderr)
        return 1

    print(f"  chiffrage entreprises de « {args.case} » pour {args.year}…", flush=True)
    try:
        path = chiffrages_module.register_firm(
            args.case, spec=spec, year=args.year, frame=pl.read_parquet(population),
            tolerance=tolerance, population_vintage=f"entreprises-{args.vintage}",
            note=args.note or "", facteur=facteur, vieillissement=vieillissement,
            apres_annexe=args.apres_annexe,
            directory=Path(args.dir) if args.dir else None)
    except chiffrages_module.ChiffrageError as error:
        print(str(error), file=sys.stderr)
        return 1
    chiffrage = chiffrages_module.load(args.case, path.parent)
    print(f"préenregistré {path}")
    print(f"  mécanique {chiffrage.mechanical_eur / 1e9:+.3f} md EUR")
    print(f"  toléré {tolerance.relative:.0%} ou "
          f"{tolerance.absolute_eur / 1e6:.0f} M EUR, au choix du plus large")
    print("\n  CE FICHIER N'EST PAS ENCORE UN PRÉENREGISTREMENT : le commit l'est.")
    print(f"  `git add {path} && git commit` — tant qu'il n'est pas committé, "
          f"la notation le refusera.")
    return 0


def cmd_chiffrage_list(args: argparse.Namespace) -> int:
    from impots import preregistration as chiffrages_module

    directory = Path(args.dir) if args.dir else None
    names = chiffrages_module.available(directory)
    if not names:
        print("aucun chiffrage préenregistré")
        return 0
    for name in names:
        try:
            case = chiffrages_module.load(name, directory)
        except chiffrages_module.ChiffrageError as error:
            print(f"  {name:26} ILLISIBLE — {error}")
            continue
        state = "noté" if case.comparator else "en attente d'un comparateur"
        print(f"  {name:26} {case.pre_registered[:10]}  "
              f"{case.mechanical_eur / 1e9:+8.3f} md  {state}")
    return 0


def cmd_chiffrage_grade(args: argparse.Namespace) -> int:
    """Grade one case against the official figure. Refuses more than it computes."""
    from impots import preregistration as chiffrages_module

    directory = Path(args.dir) if args.dir else None
    try:
        case = chiffrages_module.load(args.case, directory)
        chiffrages_module.verify_tolerance_unchanged(args.case, directory)
        verdict = chiffrages_module.grade(case)
    except chiffrages_module.ChiffrageError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"\n  {verdict.case} — **{verdict.verdict}** ({verdict.direction})")
    print(f"  simulé  {verdict.simulated_eur / 1e9:+.3f} md")
    print(f"  publié  {verdict.published_eur / 1e9:+.3f} md  "
          f"({case.comparator.source}, {case.comparator.vintage}, "
          f"{case.comparator.perimeter}, {case.comparator.net_of})")
    relative = ("n/a — un écart relatif à zéro n'est pas un nombre"
                if verdict.relative_gap is None else f"{verdict.relative_gap:+.1%}")
    print(f"  écart   {verdict.gap_eur / 1e9:+.3f} md ({relative})")
    print(f"  toléré  {verdict.allowed_eur / 1e9:.3f} md — borne {verdict.binding}, "
          f"déclarée le {case.pre_registered[:10]}")
    return 0 if verdict.verdict == "within" else 2


def cmd_chiffrage_revise(args: argparse.Namespace) -> int:
    """A new case on the published basis, written after the annex (D-292)."""
    from impots import preregistration as chiffrages_module

    directory = Path(args.dir) if args.dir else None
    try:
        path = chiffrages_module.revise_to_budget_year(
            args.case, args.new, year=args.annee, raison=args.raison, directory=directory)
        case = chiffrages_module.load(args.new, directory)
    except chiffrages_module.ChiffrageError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"  -> {path} : {case.mechanical_eur / 1e9:+.3f} md, l'effet budgétaire de "
          f"{args.annee}, révision de « {args.case} » écrite après l'annexe")
    return 0


def cmd_chiffrage_report(args: argparse.Namespace) -> int:
    from impots import preregistration as chiffrages_module

    directory = Path(args.dir) if args.dir else None
    text = chiffrages_module.report(directory)
    out = Path(args.out) if args.out else Path(__file__).resolve().parents[3] / "reports" / "chiffrages_preregistres.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"  -> {out}")
    return 0


def cmd_fiche(args: argparse.Namespace) -> int:
    """Render the fiche de chiffrage for a registered scenario (F4).

    Runs the population, assembles the honesty stack, and writes markdown. The run is
    done HERE rather than read from a file so the fiche and its numbers come from the
    same execution — a fiche assembled from a stale run is a fiche that disagrees with
    itself and says nothing about it.
    """
    from datetime import date as _date

    from impots import scenarios as scenarios_module
    from impots.api.schemas import PopulationResponse
    from impots.fiche import FicheError, Provenance, render

    directory = Path(args.dir) if args.dir else None
    try:
        scenario = scenarios_module.load(args.scenario, directory)
        scenario.check_years([args.year])
    except scenarios_module.ScenarioError as error:
        print(str(error), file=sys.stderr)
        return 1

    population = PROCESSED / f"population_{args.vintage}.parquet"
    if not population.exists():
        print(f"{population} not found — run `impots population build` first",
              file=sys.stderr)
        return 1

    from fastapi.testclient import TestClient

    from impots.api.main import app

    print(f"  chiffrage de « {args.scenario} » sur {args.sample:,} ménages…"
          .replace(",", " "), flush=True)
    payload = {"year": args.year,
               "reform": scenario.reform.model_dump(exclude_none=True, mode="json"),
               "behavioural": not args.no_behavioural, "macro": not args.no_macro}
    reply = TestClient(app).post("/population/simulate", json=payload)
    if reply.status_code != 200:
        print(f"la simulation a échoué ({reply.status_code}) : {reply.text[:300]}",
              file=sys.stderr)
        return 1

    commit = ""
    try:
        from impots.preregistration import head_commit
        commit = head_commit()[:7]
    except Exception:  # pragma: no cover - outside a repo
        pass

    try:
        text = render(PopulationResponse.model_validate(reply.json()),
                      Provenance(titre=args.titre or scenario.name,
                                 source=scenario.source,
                                 date=_date.today().isoformat(),
                                 scenario=scenario.name, commit=commit,
                                 preregistre=args.preregistre))
    except FicheError as error:
        print(str(error), file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else (
        Path(__file__).resolve().parents[3] / "reports" / f"fiche_{scenario.name}.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"  -> {out} ({len(text.splitlines())} lignes)")
    return 0


def cmd_trajectoire(args: argparse.Namespace) -> int:
    """Price a scenario year by year and write the artefact the UI and fiche read (F3 M5).

    Two population runs per year — the frozen population and the aged one — because the
    uprating uncertainty class IS that pair (D-107). At the default sample that is minutes
    per year, which is why this is a CLI batch job and not an HTTP request.
    """
    import json as _json
    from datetime import date as _date
    from typing import Any

    import polars as pl

    from impots import scenarios as scenarios_module
    from impots import trajectoires as tj
    from impots import uprating as up
    from impots.api.schemas import ReformSpec
    from impots.engine.reforms import moves_capital
    from impots.population import imputations as imp

    directory = Path(args.dir) if args.dir else None
    try:
        scenario = scenarios_module.load(args.scenario, directory)
        scenario.check_years(range(args.start, args.end + 1))
        tj.require_reference(args.reference)
        # What the passes cannot impute, refused before the first one (but 14).
        for year in range(args.start, args.end + 1):
            imp.imputations(scenario.reform_in(year), year, possibles=CHEMIN_POSSIBLES,
                            chemin="la trajectoire")
        hypothesis = up.Uprating(wage=args.wage, price=args.price,
                                 source=args.hypothesis_source, base_year=args.base_year)
    except (scenarios_module.ScenarioError, tj.TrajectoryError,
            up.UpratingError, imp.ImputationRefusee) as error:
        print(str(error), file=sys.stderr)
        return 1

    population = PROCESSED / f"population_{args.vintage}.parquet"
    if not population.exists():
        print(f"{population} not found — run `impots population build` first",
              file=sys.stderr)
        return 1
    frame = pl.read_parquet(population)
    from impots.engine.reforms import read_ir_parameters
    from impots.engine.system import baseline as engine_baseline

    tbs = engine_baseline()
    indexation = (tj.Indexation(rate=args.price, source=args.hypothesis_source)
                  if args.reference == "indexe" else None)
    # Decided once, on the scenario's reform, for every pass of a year: against `indexe`
    # the cost is a difference of two passes, and a capital imputed in one of them only
    # would put the whole tax on capital into the cost (D-249).
    capital = moves_capital(scenario.reform)

    def runner(pop: object, year: int, index: float):
        """A `run` callable for `tj.price`: reform dict -> mechanical cost.

        Routed through `tj.price` rather than run directly so the REFERENCE is actually
        applied — the first version validated `--reference` and then ignored it, pricing
        the reform against current law whichever was asked for. Against `indexe` the cost
        is the difference between indexed-plus-reform and indexed-alone, and skipping that
        subtraction would have folded the whole cost of indexation into every figure.
        """
        def run(spec: dict[str, Any] | None) -> float:
            if not spec:
                return 0.0
            reform = ReformSpec.model_validate(spec)
            return _chemin_pass(pop, year, reform, capital=capital, index=index,
                                sample=args.sample,
                                view="figee" if pop is frame else "vieillie",
                                uprating=hypothesis, vintage=args.vintage,
                                chemin="la trajectoire")
        return run

    def price(pop: object, year: int, index: float) -> float:
        # A dated revaluation is carried after the scenario's year (D-301).
        reform = scenario.reform_in(year).model_dump(exclude_none=True, mode="json")
        return tj.price(year, args.reference, reform=reform,
                        law=read_ir_parameters(tbs, year), run=runner(pop, year, index),
                        indexation=indexation).mechanical_eur

    rows = []
    for year in range(args.start, args.end + 1):
        print(f"  {year}…", flush=True)
        # The imputed capital ages with the frame, on the wage index (D-249).
        frozen = price(frame, year, 1.0)
        aged = price(up.uprate(frame, year, hypothesis), year,
                     hypothesis.factor("wage", year))
        rows.append(tj.year_uncertainty(
            year, basis=tj.basis_for(args.side, year), frozen_eur=frozen,
            aged_eur=aged, base_year=args.start))

    payload = {
        "scenario": scenario.name, "titre": args.titre or scenario.name,
        "source": scenario.source, "reference": args.reference,
        "computed": _date.today().isoformat(),
        "banner": ("Ce qui est chiffré : ce droit, sur la France d'aujourd'hui, "
                   "avec l'argent de demain."),
        "uprating_note": up.caveat(args.start, hypothesis),
        "years": [{
            "year": r.year, "basis": r.basis, "mechanical_eur": r.mechanical_eur,
            "uprating_frozen_eur": r.uprating_eur[0],
            "uprating_aged_eur": r.uprating_eur[1],
            "behavioural_low_eur": (r.behavioural_eur or [None, None])[0],
            "behavioural_high_eur": (r.behavioural_eur or [None, None])[1],
            "behavioural_grade": r.behavioural_grade,
            "fan_shown": r.fan is not None, "fan_note": r.fan_note,
        } for r in rows],
    }
    out = Path(__file__).resolve().parents[3] / "reports" / f"trajectoire_{scenario.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"  -> {out}")
    for r in rows:
        print(f"     {r.line()}")
    return 0


def cmd_predictif(args: argparse.Namespace) -> int:
    """The debt path of a scenario, every year priced, both views (Phase 9 M1b).

    `POST /predictif/simulate` prices one year and carries it; this prices them all, on the
    frozen population and on the population aged with the growth scenario's prices, then
    builds the debt path from each. Two population runs per year (four against `indexe`):
    at the default sample that is about an hour for ten years, which is why it is a
    command and writes a report rather than answering a request.

    With `--behavioural` or `--macro` (Phase 10 M3, D-236), every year and view goes
    through the simulator's own pass, `service.price_first_year`: the cost, what the channels
    read, the reform's macro impulse. The receipts at θ are then evaluated year by year
    and the GDP → receipts loop reads one impulse per year. Past three years with the
    loop and no `--persistence`, both persistence scenarios are drawn side by side.
    """
    import json as _json
    import subprocess as _subprocess
    from datetime import date as _date
    from typing import Any

    import polars as pl

    from impots import scenarios as scenarios_module
    from impots import trajectoires as tj
    from impots import uprating as up
    from impots.dette import maturite
    from impots.dette import reference as reference_module
    from impots.dette.path import SHIPPED, DebtError, SpendingScenario
    from impots.dette.scenarios import GrowthScenario, RateScenario
    from impots.engine.reforms import read_ir_parameters
    from impots.engine.system import baseline as engine_baseline
    from impots.population import imputations as imp
    from impots.predictif import annuel, chaine, recherche, retroaction
    from impots.predictif.theta import Theta, ThetaError
    from impots.service import ServiceError

    whole = args.behavioural or args.macro
    # The report names the code that priced it and whether `src/` differed, as an
    # exploration report does; it is not refused here, the reader decides (D-275).
    try:
        commit, dirty = recherche.code_state()
    except (OSError, _subprocess.CalledProcessError):
        commit = dirty = None
    directory = Path(args.dir) if args.dir else None
    try:
        scenario = scenarios_module.load(args.scenario, directory)
        tj.require_reference(args.reference)
        if args.spending == "personnalise":
            spending = SpendingScenario(args.spending_name or "", "personnalise",
                                        growth=args.spending_growth)
        elif args.spending_name is not None or args.spending_growth is not None:
            raise DebtError(
                f"la règle « {args.spending} » porte son propre nom et ne lit aucun taux : "
                f"un nom ou un taux fourni avec elle serait ignoré.")
        else:
            spending = SHIPPED[args.spending]
        growth = GrowthScenario(args.growth_name, args.real, args.prices)
        rate = RateScenario(args.rate_name, args.rate_kind, market_rate=args.market_rate)
        theta = Theta(common=args.theta)
        uprating = annuel.uprating_for(growth, wage=args.wage,
                                       source=args.hypothesis_source,
                                       base_year=args.base_year)
        start = reference_module.start_from_accounts(chaine.START_YEAR)
        if scenario.annees:
            _annees_refusals(scenario, range(start.year + 1, start.year + 1 + args.horizon))
        securities = maturite.load_block1() if rate.kind == "marche" else None
        looped = args.macro and spending.rule == retroaction.SPENDING_RULE
        if args.persistence is not None and not looped:
            raise DebtError(
                f"persistance « {args.persistence} » sans boucle appliquée (--macro non "
                f"demandé, ou absente sous « {spending.name} ») : elle serait ignorée.")
        if whole:
            _whole_pass_refusals(args)
        # What the passes cannot impute, refused before the first one (but 14).
        for year in range(start.year + 1, start.year + 1 + args.horizon):
            if scenario.applies(year):
                imp.imputations(scenario.reform_in(year), year,
                                possibles=CHEMIN_POSSIBLES, chemin="le chemin annuel")
    except (scenarios_module.ScenarioError, tj.TrajectoryError, up.UpratingError,
            DebtError, ThetaError, maturite.MaturityError, OSError,
            imp.ImputationRefusee) as error:
        print(str(error), file=sys.stderr)
        return 1

    population = PROCESSED / f"population_{args.vintage}.parquet"
    if not population.exists():
        print(f"{population} not found — run `impots population build` first",
              file=sys.stderr)
        return 1
    frame = pl.read_parquet(population)
    tbs = engine_baseline()
    # Against `indexe` the barème is indexed on the SAME prices the GDP grows with: a
    # third price index would be the incoherence `annuel.check_coherence` refuses.
    indexation = (tj.Indexation(rate=growth.prices, source=args.hypothesis_source)
                  if args.reference == "indexe" else None)


    firm_part = service.firm_part(scenario.firm_reform, growth=growth)
    from impots.engine.reforms import moves_capital

    # Decided once on the scenario's reform, for both passes of a difference (D-249).
    capital = moves_capital(scenario.reform)

    def price(year: int, view: str) -> float | annuel.Layered:
        if not scenario.applies(year):
            return annuel.Layered(cost=0.0, layers={"menages": 0.0, "entreprises": 0.0})
        pop = frame if view == "figee" else up.uprate(frame, year, uprating)
        # The imputed capital ages with the frame, on the wage index, or not at all in
        # the frozen view (D-249).
        index = 1.0 if view == "figee" else uprating.factor("wage", year)

        def run(spec: dict[str, Any] | None) -> float:
            if not spec:
                return 0.0
            reform = ReformSpec.model_validate(spec)
            return _chemin_pass(pop, year, reform, capital=capital, index=index,
                                sample=args.sample, view=view, uprating=uprating,
                                vintage=args.vintage, chemin="le chemin annuel")

        print(f"  {year} · {view}…", flush=True)
        # The first year writes a revaluation at its legal date, the years after carry
        # the level it left, January to December (D-301).
        reform = scenario.reform_in(year).model_dump(exclude_none=True, mode="json")
        households = tj.price(year, args.reference, reform=reform,
                              law=read_ir_parameters(tbs, year), run=run,
                              indexation=indexation).mechanical_eur
        if not firm_part:
            return households
        # The firm layer beside the households' (D-246): its own pass, its own view.
        firms = service.firm_first_year(scenario.firm_reform, year, view=view,
                                     growth=growth).cost
        return annuel.Layered(cost=households + firms,
                              layers={"menages": households, "entreprises": firms})

    years = list(range(start.year + 1, start.year + 1 + args.horizon))
    store = macro_store = None
    if whole:
        from impots.behavioural.store import load as load_store
        from impots.predictif.exploration import Priced

        try:
            store = load_store()
            theta.check_known(store)
            macro_store = service.predictif_macro_store() if looped else None
        except (ThetaError, service.MacroSourceError) as error:
            print(str(error), file=sys.stderr)
            return 1

        def price(year: int, view: str) -> Priced:
            if not scenario.applies(year):
                # A year the text does not cover: the reform is empty, and its pass is
                # of the measure's kind, a firm reform alone (D-288).
                return Priced(cost=0.0, impulse={} if args.macro else None,
                              layers={"menages": 0.0, "entreprises": 0.0},
                              behaviour_asked=args.behavioural)
            print(f"  {year} · {view} · passe du simulateur…", flush=True)
            _liberer()
            # In a fresh process, which gives back all it took when it ends (D-331).
            first = _isole(
                service.price_first_year,
                service.YearPass(reform=scenario.reform_in(year), year=year,
                             behavioural=args.behavioural),
                uprating=uprating, macro=args.macro, view=view, **firm_part)
            # A firm reform alone with behaviour asked says so, for no household channel
            # reads it: the path is priced, and says why the band is absent (D-273).
            return Priced(cost=first.cost, inputs=first.inputs, impulse=first.impulse,
                          uncovered=dict(first.uncovered),
                          layers=getattr(first, "layers", None),
                          behaviour_asked=getattr(first, "behaviour_asked", False))
    try:
        prices = annuel.price_years(years, price,
                                    basis_for=lambda y: tj.basis_for("menages", y))
        rapport = annuel.build(
            start, prices, scenario=scenario.name, titre=args.titre or scenario.name,
            source=scenario.source, reference=args.reference,
            computed=_date.today().isoformat(), spending=spending, growth=growth,
            rate=rate, theta=theta, uprating=uprating,
            uprating_note=up.caveat(years[-1], uprating), securities=securities,
            reform=scenario.reform, behavioural=args.behavioural, macro=args.macro,
            persistence=args.persistence, store=store, macro_store=macro_store,
            firm_note=(service.firm_report_note(scenario.firm_reform, years) if firm_part
                       else None), commit=commit, dirty=dirty, where=args.ou,
            annees=scenario.annees)
    except (DebtError, ThetaError, tj.TrajectoryError, up.UpratingError,
            maturite.MaturityError, retroaction.FeedbackError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except ServiceError as error:
        print(str(error.detail), file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(__file__).resolve().parents[3] / "reports")
    out = out_dir / f"predictif_{scenario.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(rapport.payload(), indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"  -> {out}")
    for path in rapport.paths:
        if path.label is not None:
            print(f"     {path.label}")
        for line in path.aged.lines():
            print(f"     {line}")
    return 0


def _isole(function: object, *args: object, **kwargs: object) -> object:
    """`function(*args, **kwargs)` in a fresh process, its value returned (D-331).

    A pass of the annual path takes up to ten gigabytes, and a process does not give all
    of it back: freed caches and a tuned allocator left the paths of Tondelier and of
    Lisnard killed on a 15-gigabyte machine. A process that ends gives everything back.
    The child is spawned, not forked: it starts clean, and computes what the parent would
    have, on the same code, the same files and the same environment."""
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=1,
                             mp_context=multiprocessing.get_context("spawn")) as pool:
        return pool.submit(function, *args, **kwargs).result()


def _liberer() -> None:
    """Free what a pass of the annual path keeps and the next one does not read: the
    reformed systems of the year before, each with its trees by instant, held by two caches
    of 32, and the baseline's trees by instant (D-330). Kept, a ten-year path of a large
    reform grew by two gigabytes a pass and was killed in its second year on a 15-gigabyte
    machine."""
    import gc

    from impots.engine import parametres
    from impots.engine import system as engine_system
    from impots.entreprises import system as firm_system

    engine_system.reformed.cache_clear()
    firm_system.reformed.cache_clear()
    # And the baseline's trees by instant: a cache without bound, which a path filled with
    # every month of every year it priced. The next pass rebuilds the ones it reads.
    parametres.memoriser(engine_system.baseline())
    gc.collect()


#: What the passes of the trajectory and of the annual path can impute: the capital, the
#: consumption and the households' data of the but 21 (D-396), each whenever the reform moves
#: it. Not the sick pay, which the CCSS gives for 2024 alone (D-305, D-306), nor the niches,
#: a calibration these paths never ran.
CHEMIN_POSSIBLES = ("capital", "consommation", "menages")


def _chemin_pass(pop: object, year: int, reform: object, *, capital: bool, index: float,
                 sample: int, view: str, uprating: object, vintage: str,
                 chemin: str) -> float:
    """One pass of the trajectory or of the annual path: its mechanical cost.

    What it imputes is the one policy's (`population.imputations`): the consumption
    whenever the reform moves it (D-328), the capital whenever the SCENARIO's reform moves
    it — `capital`, decided once for both passes of a difference, for against `indexe` a
    capital imputed in one of them only would put the whole tax on capital into the cost
    (D-249). What the path cannot impute is refused with its reason before the pass, and
    the confident-zero guard reads the pass after it (but 14)."""
    from impots import guards
    from impots.population import aggregate as agg_mod
    from impots.population import imputations as imp
    from impots.population.runner import run as population_run

    imputed = imp.imputations(reform, year, demandees=(imp.CAPITAL,) if capital else (),
                              possibles=CHEMIN_POSSIBLES, chemin=chemin)
    # Where the consumption's euros come from follows the view (D-328); whether it is
    # imputed at all is the policy's, which `_consommation` agrees with.
    kwargs = {**imputed.runner(), **_consommation(reform, year, view, uprating, vintage),
              **({"capital_index": index} if imputed.capital else {}),
              **({"menages_facteurs": _menages_facteurs(year, view, uprating)}
                 if imputed.menages else {})}
    result = population_run(pop, year=year, reform=reform, tier="full", sample=sample,
                            **kwargs)
    agg = agg_mod.aggregate(result.households)
    guards.refuse_zero_confiant(reform.model_dump(exclude_none=True), imputed.noms(),
                                agg.totals, chemin=chemin)
    return guards.cout_calcule(agg.reform_cost, chemin=chemin)


def _menages_facteurs(year: int, view: str, uprating: object) -> dict[str, float]:
    """What aged the frame of a pass of the annual path, which the households' data read
    when they are imputed (but 21, étape 4) : the frame's factors in the aged view, none in
    the frozen one, whose frame is the vintage's — as the service does (D-396)."""
    from impots.population import menages

    if view == "figee":
        return {"wage": 1.0, "price": 1.0}
    return menages.facteurs_de(uprating, year)


def _consommation(reform: object, year: int, view: str, uprating: object,
                  vintage: str) -> dict[str, object]:
    """What a pass of the annual path tells the runner of the consumption, when its reform
    moves a consumption tax (D-328): the aged view's euros are the year's, at the frame's
    own price index ; the frozen view's, the vintage's."""
    from impots import consommation

    if not consommation.touche(reform):
        return {}
    if view == "figee":
        return {"impute_consommation": True, "annee_consommation": int(vintage)}
    return {"impute_consommation": True, "annee_consommation": year,
            "prix_au_dela": consommation.prix_du_cadre(uprating, year)}


def _annees_refusals(scenario: object, path: range) -> None:
    """What a measure bounded to its years cannot be on the annual path (D-288), refused
    before the first pass: a household reform, whose channels read inputs each year that a
    year without the measure does not have; and a year the path does not reach."""
    from impots.dette.path import DebtError

    if not scenario.reform.is_empty() or scenario.firm_reform is None or (
            scenario.firm_reform.is_empty()):
        raise DebtError(
            f"« {scenario.name} » borne sa mesure à {list(scenario.annees)} : le chemin "
            f"annuel ne le lit que pour une réforme des seules entreprises. Les canaux des "
            f"ménages lisent chaque année des entrées qu'une année sans mesure n'a pas.")
    outside = [y for y in scenario.annees if y not in path]
    if outside:
        raise DebtError(
            f"« {scenario.name} » s'applique en {outside}, hors du chemin "
            f"({path.start}–{path.stop - 1}) : la mesure n'y serait chiffrée nulle part.")


def _whole_pass_refusals(args: argparse.Namespace) -> None:
    """What `--behavioural` and `--macro` cannot honour, refused before the first pass.

    They go through the simulator's pass, which prices against current law on its own
    sample of the 2024 population. Against « indexe » the cost is the difference of two
    passes (`trajectoires.price`), and neither the channels' inputs nor the impulse are
    built to be subtracted; another sample or vintage would price the years on one
    population and the simulator's first year on another."""
    from impots.api.schemas import QUICK_TIER_HOUSEHOLDS
    from impots.dette.path import DebtError
    from impots.service import POPULATION_VINTAGE

    if args.reference != "reconduit":
        raise DebtError(
            f"--behavioural ou --macro contre la référence « {args.reference} » : le coût y "
            f"est la différence de deux passes, et ni les entrées des canaux ni "
            f"l'impulsion ne se soustraient. Refusé plutôt que chiffré à moitié.")
    if args.sample != QUICK_TIER_HOUSEHOLDS or args.vintage != POPULATION_VINTAGE:
        raise DebtError(
            f"--behavioural ou --macro passent par la passe du simulateur, "
            f"{QUICK_TIER_HOUSEHOLDS} ménages du millésime {POPULATION_VINTAGE} : "
            f"--sample {args.sample} ou --vintage {args.vintage} chiffreraient les années "
            f"sur une autre population que la sienne.")


def cmd_etude(args: argparse.Namespace) -> int:
    """Une étude en trois réponses (but 6, D-301) : ses passes, sa page, sa dérive."""
    from impots import etude

    try:
        study = etude.definition(args.nom)
        if args.action == "lancer":
            return study.launch(args.ou)
        sortie = Path(args.sortie) if getattr(args, "sortie", None) else None
        if args.action == "premiere":
            print(f"  -> {study.write_first_year(args.scenario, where=args.ou, sortie=sortie)}")
            return 0
        if args.action == "plage":
            written = study.write_plage(args.mesure, args.champ, args.point, where=args.ou,
                                        sortie=sortie)
            print(f"  -> {written}")
            return 0
        if args.action == "temoin":
            return study.witness(args.ou)
        if args.action == "avant":
            print(f"-> {study.figer_avant()}")
            return 0
        if args.action == "ecrire":
            text = study.render(study.load())
            study.page.parent.mkdir(parents=True, exist_ok=True)
            study.page.write_text(text, encoding="utf-8")
            print(f"-> {study.page} ({len(text.splitlines())} lignes)")
            return 0
        why = study.drift()
    except etude.EtudeError as error:
        print(str(error), file=sys.stderr)
        return 1
    if why:
        print(why, file=sys.stderr)
        return 1
    print(f"« {study.nom} » : chiffrée, puis refusée, sans page : {study.refus}"
          if study.refus else
          f"{study.page} : la page est celle de ses rapports." if study.page.exists() else
          f"« {study.nom} » : ni rapports ni page, ses passes n'ont pas tourné.")
    return 0


def cmd_grille(args: argparse.Namespace) -> int:
    """La grille des curseurs (but 15, D-343) : ses passes, un point, sa compilation."""
    from impots import grille

    try:
        if args.action == "lancer":
            return grille.lancer(args.ou)
        if args.action == "point":
            cible = tuple(args.cible.split(",")) if args.genre == "paire" else args.cible
            index = None if args.index < 0 else args.index
            sortie = Path(args.sortie) if args.sortie else None
            print(f"  -> {grille.ecrire(args.genre, cible, index, where=args.ou, sortie=sortie)}")
            return 0
        compiled = grille.compiler()
        for c in compiled["curseurs"]:
            t = c["temoin"]
            dette = ("absente" if t["dette_tenue"] is None else
                     f"dette {t['ecart_dette'] * 100:+.4f} pt / ±{t['tolerance_dette'] * 100:.4f}"
                     f" {'tenue' if t['dette_tenue'] else 'MANQUÉE'}")
            print(f"{c['id']:26s} coût {t['ecart_cout'] / 1e6:+10.2f} M€ / "
                  f"±{t['tolerance_cout'] / 1e6:.1f} {'tenu' if t['cout_tenu'] else 'MANQUÉ'}"
                  f" ; {dette}")
        for p in compiled["paires"]:
            print(f"{p['a']} × {p['b']} : terme croisé {p['cout']['total'] / 1e6:+.1f} M€")
        return 0
    except grille.GrilleError as error:
        print(str(error), file=sys.stderr)
        return 1


def cmd_programme(args: argparse.Namespace) -> int:
    """Un programme présidentiel (but 11, D-319) : ce que le moteur en chiffre, ce qu'il en
    refuse, et, avec des hypothèses, les trois réponses sur la part chiffrée."""
    from pydantic import ValidationError

    from impots import programme_chiffrage as pc
    from impots import programmes as pg
    from impots.service import ServiceError

    if args.slug is None:
        for slug in pg.lister():
            print(slug)
        return 0
    try:
        programme = pg.charger(args.slug)
        hypotheses = pc.lire_hypotheses(Path(args.hypotheses)) if args.hypotheses else None
        mesures = tuple(args.mesures.split(",")) if args.mesures else None
        report = pc.rapport(programme, valeurs=pc.lire_valeurs(args.valeur),
                            mesures=mesures, rho=args.rho, hypotheses=hypotheses)
    except (pg.ProgrammeError, pc.ChiffrageError, ValidationError, OSError,
            json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except ServiceError as error:
        print(f"chiffrage refusé ({error.status_code}) : {error.detail}", file=sys.stderr)
        return 1
    if args.sortie:
        out = Path(args.sortie)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        print(f"-> {out}")
    for line in pc.resume(report):
        print(line)
    return 0


def cmd_verification(args: argparse.Namespace) -> int:
    """La grille de vérification (but 18, D-362, D-363)."""
    from impots import verification

    return verification.main_args(args.action, getattr(args, "annee", None),
                                  getattr(args, "lots", 4))


def cmd_site(args: argparse.Namespace) -> int:
    """Le site des études (but 7, D-304) : le construire, ou vérifier qu'il est à jour."""
    from impots import site

    return site.main_args(args.action)


def cmd_exploration(args: argparse.Namespace) -> int:
    """The bundles whose debt difference meets a target, at a fixed θ (Phase 10 M1).

    Reads an `ExplorationRequest`, prices each bundle of its grid in both views through
    `/predictif/simulate`'s own seams — its hypotheses, its first-year pass — and writes
    `reports/exploration_<name>.json`. Two quick passes per bundle, of two to four
    minutes each: a search is a command, never a request (PHASE10_SPEC §2).
    """
    import json as _json
    import subprocess as _subprocess
    from datetime import date as _date

    from pydantic import ValidationError

    from impots import explorer
    from impots import scenarios as scenarios_module
    from impots.api.schemas import ExplorationRequest
    from impots.dette import maturite
    from impots.dette import reference as reference_module
    from impots.dette.path import DebtError
    from impots.entreprises.reforms import FirmReformSpec
    from impots.predictif import chaine, recherche, retroaction
    from impots.predictif.exploration import VIEWS, Priced
    from impots.predictif.theta import ThetaError
    from impots.service import ServiceError
    from impots.uprating import UpratingError

    try:
        request = ExplorationRequest.model_validate_json(
            Path(args.request).read_text(encoding="utf-8"))
        scenarios_module._check_name(request.name)
    except (OSError, ValidationError, scenarios_module.ScenarioError) as error:
        print(str(error), file=sys.stderr)
        return 1
    try:
        commit, dirty = recherche.code_state()
    except (OSError, _subprocess.CalledProcessError) as error:
        print(f"aucun dépôt git lisible ({error}) : le rapport ne pourrait pas nommer le "
              f"code qui l'a produit.", file=sys.stderr)
        return 1
    if dirty:
        print("src/ a des modifications non commitées : le rapport nommerait un commit dont "
              "il n'a pas chiffré le code. Commiter d'abord.", file=sys.stderr)
        return 1
    try:
        hypotheses = service.predictif_hypotheses(request)
        start = reference_module.start_from_accounts(chaine.START_YEAR)
        year = start.year + 1
        # A transformation scales the law of the year it prices: read once, here.
        law = recherche.law_in_force(year) if recherche.needs_law(request) else None
        grid = recherche.check_grid(request, max_bundles=args.max_paquets, law=law)
        securities = maturite.load_block1() if hypotheses.rate.kind == "marche" else None
        macro_store = service.predictif_macro_store() if hypotheses.looped else None
    except (DebtError, ThetaError, UpratingError, recherche.RechercheError,
            explorer.ExplorerError, maturite.MaturityError, service.MacroSourceError,
            OSError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if year > service.MAX_YEAR:
        print(f"la première année projetée, {year}, sort de la fenêtre que la couche "
              f"population sert ({service.MIN_YEAR}–{service.MAX_YEAR}).", file=sys.stderr)
        return 1
    print(f"  {len(grid)} paquets × {len(VIEWS)} vues = {len(grid) * len(VIEWS)} passes "
          f"rapides, {len(hypotheses.persistences)} recherche(s)", flush=True)

    def price(reform: ReformSpec, view: str,
              firm: FirmReformSpec | None = None) -> Priced:
        shown = {**reform.model_dump(exclude_none=True),
                 **(firm.model_dump(exclude_none=True) if firm is not None else {})}
        print(f"  {shown} · {view}…", flush=True)
        first = service.price_first_year(
            service.first_year_request(reform, year, request.behavioural),
            uprating=hypotheses.uprating, macro=request.macro, view=view,
            **service.firm_part(firm, growth=hypotheses.growth))
        return Priced(cost=first.cost, inputs=first.inputs, impulse=first.impulse,
                      uncovered=dict(first.uncovered), deciles=list(first.deciles),
                      behaviour_asked=getattr(first, "behaviour_asked", False))

    try:
        payload = recherche.run(request, price=price, hypotheses=hypotheses, start=start,
                                macro_store=macro_store, securities=securities,
                                max_bundles=args.max_paquets, law=law, commit=commit,
                                computed=_date.today().isoformat(), where=args.ou)
    except ServiceError as error:
        print(str(error.detail), file=sys.stderr)
        return 1
    except (DebtError, ThetaError, explorer.ExplorerError, recherche.RechercheError,
            retroaction.FeedbackError, maturite.MaturityError) as error:
        print(str(error), file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(__file__).resolve().parents[3] / "reports")
    out = out_dir / f"exploration_{request.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"  -> {out}")
    for search in payload["searches"]:
        label = search["persistence_label"] or "sans persistance"
        plans = [c for c in search["candidates"] if c["meets_target"]]
        robust = [c for c in plans if c["robust"]]
        print(f"     {label} : {len(plans)} paquet(s) tiennent la cible à θ, "
              f"{len(robust)} robuste(s) ; empreinte {search['digest'][:8]}")
    return 0


def cmd_emtr_explorer(args: argparse.Namespace) -> int:
    """Sweep a household type across the income range and write the artefact (F6 / S5).

    Four full-tier runs for the whole curve, not two per point: the sweep is a synthetic
    frame priced in one pass by the machinery the behavioural layer already uses.
    """
    import json as _json
    from datetime import date as _date

    from impots import emtr_explorer as explorer

    reform = None
    if args.reform:
        try:
            reform = _load_reform(args.reform)
        except Exception as error:
            print(f"--reform ne valide pas : {error}", file=sys.stderr)
            return 1

    try:
        curve = explorer.curve(args.type, year=args.year, reform=reform,
                               step=args.step, maximum=args.max)
    except explorer.ExplorerError as error:
        print(str(error), file=sys.stderr)
        return 1

    payload = {
        "household_type": curve.household_type, "label": curve.label,
        "year": curve.year, "computed": _date.today().isoformat(),
        "step_eur": args.step, "reform": curve.reform,
        "points": [{"salaire_brut_annuel": p.salaire_brut_annuel, "emtr": p.emtr,
                    "emtr_reform": p.emtr_reform} for p in curve.points],
        "peak_eur": curve.peak.salaire_brut_annuel, "peak_emtr": curve.peak.emtr,
        "cliffs_eur": [p.salaire_brut_annuel for p in curve.cliffs],
        "crossings_eur": list(curve.crossings()),
    }
    out = (Path(__file__).resolve().parents[3] / "reports"
           / f"emtr_{curve.household_type}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(f"  {curve.label}")
    print(f"  -> {out} ({len(curve.points)} points)")
    print(f"  pic {curve.peak.emtr:.1%} à {curve.peak.salaire_brut_annuel:,.0f} EUR"
          .replace(",", " "))
    if curve.cliffs:
        print(f"  falaises à {[int(p.salaire_brut_annuel) for p in curve.cliffs]} — "
              f"leur HAUTEUR est un artefact du pas de 100 EUR, pas un taux subi")
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
    builder.add_argument("--vintage", type=millesime, default="2024")
    builder.add_argument("--seed", type=int, default=None)
    builder.add_argument("--no-raking", action="store_true",
                         help="skip the calibration step (D-017); used to produce the "
                              "unraked comparison in the reconciliation report")
    builder.set_defaults(func=cmd_build)

    runner_parser = actions.add_parser("run", help="run a reform over the population")
    runner_parser.add_argument("--vintage", type=millesime, default="2024")
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
    runner_parser.add_argument(
        "--impute-capital", action="store_true",
        help="hand out the base the PFU taxes from DGFiP n° 41's fractiles before taking "
             "the figures (D-248). A CALIBRATION too: the PFU then matches n° 41 by "
             "construction. Revenus 2024 only")
    runner_parser.add_argument(
        "--impute-ij", action="store_true",
        help="hand the régime général's sick pay (maladie, AT-MP) to the private "
             "sector's employees from the CCSS of May 2026 (D-305). A CALIBRATION: the "
             "totals are the CCSS's by construction. Neither the IR nor the CSG sees them "
             "yet. 2024 only")
    runner_parser.set_defaults(func=cmd_run)

    reconciler = actions.add_parser("reconcile", help="generate reports/reconciliation.md")
    reconciler.add_argument("--vintage", type=millesime, default="2024")
    reconciler.add_argument("--year", type=int, default=2024)
    reconciler.add_argument("--sample", type=int, default=None)
    reconciler.add_argument(
        "--impute-niches", action="store_true",
        help="draw réduction and crédit d'impôt bases from the published decile table "
             "(D-066). Off by default, which leaves the net-IR and foyers-imposés "
             "lines comparing a gross figure against a net target (D-073)")
    reconciler.add_argument(
        "--impute-capital", action="store_true",
        help="hand out the PFU's base from DGFiP n° 41's fractiles (D-248). Off by "
             "default, which leaves the PFU in the net-IR target and out of the model")
    reconciler.add_argument("--lots", type=int, default=1,
                            help="run the population that many groups of ménages at a "
                                 "time, to hold in memory (D-362)")
    reconciler.add_argument("--compare-unraked", action="store_true",
                            help="also build and run the population without raking, and "
                                 "show every line before and after (D-017)")
    reconciler.set_defaults(func=cmd_reconcile)

    emtr_parser = actions.add_parser(
        "emtr", help="marginal-rate distribution, folded into the baseline artifact"
    )
    emtr_parser.add_argument("--vintage", type=millesime, default="2024")
    emtr_parser.add_argument("--year", type=int, default=2024)
    emtr_parser.add_argument("--sample", type=int, default=None,
                             help="households to sample; omit for the full population")
    emtr_parser.set_defaults(func=cmd_emtr)

    data = subcommands.add_parser(
        "data", help="the data chain: what the suite reads, where it comes from, how to "
                     "produce it")
    data_actions = data.add_subparsers(dest="action", required=True)
    data_check = data_actions.add_parser(
        "check", help="preflight — list every missing or invalid dependency and the "
                      "command that fixes it; exits 1 if any")
    data_check.add_argument("--profile", default="tests")
    data_check.set_defaults(func=cmd_data_check)
    data_fetch = data_actions.add_parser(
        "fetch", help="download raw sources by their manifest URL, verifying size and sha256")
    data_fetch.add_argument("--profile", default="tests")
    data_fetch.add_argument("files", nargs="*", help="manifest filenames (default: the profile)")
    data_fetch.set_defaults(func=cmd_data_fetch)
    data_prepare = data_actions.add_parser(
        "prepare", help="fetch, build the derived artefacts, then check — the bootstrap")
    data_prepare.add_argument("--profile", default="tests")
    data_prepare.set_defaults(func=cmd_data_prepare)

    firms = subcommands.add_parser("entreprises", help="the firm module")
    firm_actions = firms.add_subparsers(dest="action", required=True)

    firm_builder = firm_actions.add_parser("build", help="build the firm population parquet")
    firm_builder.add_argument("--cells", help="path to a sector x size cell table (JSON); "
                                             "defaults to the synthetic CI fixture")
    firm_builder.add_argument("--seed", type=int, default=None)
    firm_builder.set_defaults(func=cmd_firms_build)

    firm_cells = firm_actions.add_parser(
        "cells", help="build the REAL sector x size cell table from the three published "
                      "spreadsheets (Ésane, Focus 372, DGFiP n° 39)")
    firm_cells.add_argument("--vintage", type=millesime, default="2023")
    firm_cells.set_defaults(func=cmd_firms_cells)

    firm_runner_parser = firm_actions.add_parser("run", help="price a firm-tax reform")
    firm_runner_parser.add_argument("--vintage", type=millesime, default="fixture")
    firm_runner_parser.add_argument("--year", type=int, default=2026)
    firm_runner_parser.add_argument("--reform", help="path to a FirmReformSpec JSON file")
    firm_runner_parser.set_defaults(func=cmd_firms_run)

    firm_reconciler = firm_actions.add_parser(
        "reconcile", help="generate reports/reconciliation_entreprises.md"
    )
    firm_reconciler.add_argument("--vintage", type=millesime, default="fixture")
    firm_reconciler.add_argument("--year", type=int, default=2026)
    firm_reconciler.set_defaults(func=cmd_firms_reconcile)

    scenario = subcommands.add_parser(
        "scenario", help="named reforms: save, compare, and solve for neutrality (F2)")
    scenario_actions = scenario.add_subparsers(dest="action", required=True)

    saver = scenario_actions.add_parser("save", help="register a dated scenario")
    saver.add_argument("name")
    saver.add_argument("--reform", required=True, help="path to a ReformSpec JSON file")
    saver.add_argument("--firm-reform", dest="firm_reform",
                       help="path to a FirmReformSpec JSON file, beside the households' "
                            "reform (D-254)")
    saver.add_argument("--source", required=True,
                       help="the article or proposal this encodes — required, because a "
                            "chiffrage without one cannot be graded later")
    saver.add_argument("--year", type=int, default=2024)
    saver.add_argument("--note", default="")
    saver.add_argument("--tag", action="append")
    saver.add_argument("--dir", help="scenario directory (default: scenarios/)")
    saver.set_defaults(func=cmd_scenario_save)

    lister = scenario_actions.add_parser("list", help="list registered scenarios")
    lister.add_argument("--dir")
    lister.set_defaults(func=cmd_scenario_list)

    shower = scenario_actions.add_parser("show", help="print one scenario as JSON")
    shower.add_argument("name")
    shower.add_argument("--dir")
    shower.set_defaults(func=cmd_scenario_show)

    comparer = scenario_actions.add_parser("compare", help="price two scenarios side by side")
    comparer.add_argument("a")
    comparer.add_argument("b")
    comparer.add_argument("--vintage", type=millesime, default="2024")
    comparer.add_argument("--sample", type=int, default=20_000)
    comparer.add_argument("--dir")
    comparer.set_defaults(func=cmd_scenario_compare)

    solver = scenario_actions.add_parser(
        "solve", help="find the knob value that neutralises a reform (mechanical only)")
    solver.add_argument("knob")
    solver.add_argument("--on", help="scenario the knob is varied on top of")
    solver.add_argument("--low", type=float, required=True)
    solver.add_argument("--high", type=float, required=True)
    solver.add_argument("--target", type=float, default=0.0,
                        help="target mechanical cost in EUR (default 0 = neutral)")
    solver.add_argument("--tolerance", type=float, default=50e6,
                        help="what counts as hitting the target, in EUR")
    solver.add_argument("--max-evaluations", type=int, default=12,
                        help="each evaluation is a population run")
    solver.add_argument("--quantity", default="mechanical",
                        help="kept so the refusal is reachable from the CLI. NOT "
                             "restricted by `choices`: argparse would reject an unknown "
                             "value with its own generic message, and the whole point is "
                             "that the module's refusal — which says WHY a banded "
                             "quantity is not solvable — is the thing the caller reads")
    solver.add_argument("--vintage", type=millesime, default="2024")
    solver.add_argument("--year", type=int, default=2024)
    solver.add_argument("--sample", type=int, default=20_000)
    solver.add_argument("--dir")
    solver.set_defaults(func=cmd_scenario_solve)

    chiffrage = subcommands.add_parser(
        "chiffrage", help="pre-registered chiffrages and their grades (F1)")
    chiffrage_actions = chiffrage.add_subparsers(dest="action", required=True)

    registrar = chiffrage_actions.add_parser(
        "register", help="price a scenario and pre-register the figure")
    registrar.add_argument("case")
    registrar.add_argument("--scenario", required=True)
    registrar.add_argument("--tolerance-relative", type=float, required=True,
                           help="share of the published figure, e.g. 0.20")
    registrar.add_argument("--tolerance-absolute", type=float, required=True,
                           help="floor in EUR — what makes a chiffrage published at zero "
                                "gradable at all")
    registrar.add_argument("--tolerance-rationale", required=True,
                           help="why THIS tolerance, stated before the answer is known")
    registrar.add_argument("--vintage", type=millesime, default="2024")
    registrar.add_argument("--sample", type=int, default=20_000)
    registrar.add_argument("--note", default="")
    registrar.add_argument("--mirror", action="store_true",
                           help="the scenario prices the article's REVERSE, because the "
                                "tree already carries its end state; graded turned back "
                                "(D-298)")
    registrar.add_argument("--apres-annexe", metavar="RAISON", default=None,
                           help="a new case written after its annex was opened: a revision "
                                "in D-292's sense, counted apart from the blind cases, with "
                                "its reason (D-306)")
    registrar.add_argument("--vieillir", metavar="JEU", default=None,
                           help="the declared indices that age the population from its "
                                "vintage to the case's year, e.g. plf2027 (D-317); "
                                "required when the two years differ")
    registrar.add_argument("--dir")
    registrar.set_defaults(func=cmd_chiffrage_register)

    firm_registrar = chiffrage_actions.add_parser(
        "register-entreprises",
        help="price a FIRM reform over the firm population and pre-register the figure")
    firm_registrar.add_argument("case")
    firm_registrar.add_argument("--reform", required=True,
                                help="a FirmReformSpec, as JSON")
    firm_registrar.add_argument("--year", type=int, required=True,
                                help="the exercice the reform applies to — no default, "
                                     "because a wrong one prices a different law")
    firm_registrar.add_argument("--tolerance-relative", type=float, required=True)
    firm_registrar.add_argument("--tolerance-absolute", type=float, required=True)
    firm_registrar.add_argument("--tolerance-rationale", required=True,
                                help="why THIS tolerance, stated before the answer is known")
    firm_registrar.add_argument("--vintage", type=millesime, default="2023")
    firm_registrar.add_argument("--note", default="")
    firm_registrar.add_argument("--apres-annexe", metavar="RAISON", default=None,
                                help="a revision written after the annex was opened (D-292)")
    firm_registrar.add_argument("--vieillir", metavar="JEU", default=None,
                                help="the declared indices that age the vintage's cost to "
                                     "the case's year, e.g. plf2027 (D-246, D-317); "
                                     "required when the two years differ")
    firm_registrar.add_argument("--dir")
    firm_registrar.set_defaults(func=cmd_chiffrage_register_entreprises)

    chiffrage_lister = chiffrage_actions.add_parser("list", help="list the cases")
    chiffrage_lister.add_argument("--dir")
    chiffrage_lister.set_defaults(func=cmd_chiffrage_list)

    grader = chiffrage_actions.add_parser(
        "grade", help="grade one case against the published figure")
    grader.add_argument("case")
    grader.add_argument("--dir")
    grader.set_defaults(func=cmd_chiffrage_grade)

    reviser = chiffrage_actions.add_parser(
        "revise", help="a new case on the published basis, after the annex (D-292)")
    reviser.add_argument("case")
    reviser.add_argument("--as", dest="new", required=True)
    reviser.add_argument("--annee", type=int, required=True,
                         help="the budget year the comparator publishes")
    reviser.add_argument("--raison", required=True)
    reviser.add_argument("--dir")
    reviser.set_defaults(func=cmd_chiffrage_revise)

    reporter = chiffrage_actions.add_parser(
        "report", help="regenerate reports/chiffrages.md")
    reporter.add_argument("--out")
    reporter.add_argument("--dir")
    reporter.set_defaults(func=cmd_chiffrage_report)

    fiche_parser = subcommands.add_parser(
        "fiche", help="render the fiche de chiffrage for a scenario (F4)")
    fiche_parser.add_argument("scenario")
    fiche_parser.add_argument("--titre")
    fiche_parser.add_argument("--vintage", type=millesime, default="2024")
    fiche_parser.add_argument("--year", type=int, default=2024)
    fiche_parser.add_argument("--sample", type=int, default=20_000)
    fiche_parser.add_argument("--no-behavioural", action="store_true")
    fiche_parser.add_argument("--no-macro", action="store_true")
    fiche_parser.add_argument("--preregistre", action="store_true",
                              help="state in 6.3 that this chiffrage is pre-registered")
    fiche_parser.add_argument("--out")
    fiche_parser.add_argument("--dir")
    fiche_parser.set_defaults(func=cmd_fiche)

    trajectoire = subcommands.add_parser(
        "trajectoire", help="price a scenario year by year and write the artefact (F3 M5)")
    trajectoire.add_argument("scenario")
    trajectoire.add_argument("--start", type=int, default=2026)
    trajectoire.add_argument("--end", type=int, default=2030)
    trajectoire.add_argument("--reference", required=True,
                             choices=["reconduit", "indexe"],
                             help="no default: the two answer different questions")
    trajectoire.add_argument("--side", default="menages",
                             choices=["menages", "entreprises"])
    trajectoire.add_argument("--wage", type=float, required=True)
    trajectoire.add_argument("--price", type=float, required=True)
    trajectoire.add_argument("--hypothesis-source", required=True,
                             help="where the indices come from — declared, never forecast")
    trajectoire.add_argument("--base-year", type=int, default=2024)
    trajectoire.add_argument("--vintage", type=millesime, default="2024")
    trajectoire.add_argument("--sample", type=int, default=8_000)
    trajectoire.add_argument("--titre")
    trajectoire.add_argument("--dir")
    trajectoire.set_defaults(func=cmd_trajectoire)

    predictif = subcommands.add_parser(
        "predictif",
        help="the debt path of a scenario, every year priced, both views (Phase 9 M1b)")
    predictif.add_argument("scenario")
    predictif.add_argument("--reference", required=True, choices=["reconduit", "indexe"],
                           help="no default: the two answer different questions")
    # No hypothesis has a default (D-213): each is named on the report it produces.
    predictif.add_argument("--spending", required=True,
                           choices=["part_pib_constante", "gele_en_volume",
                                    "personnalise"])
    predictif.add_argument("--spending-name")
    predictif.add_argument("--spending-growth", type=float)
    predictif.add_argument("--growth-name", required=True)
    predictif.add_argument("--real", type=float, required=True,
                           help="annual GDP growth in volume")
    predictif.add_argument("--prices", type=float, required=True,
                           help="annual price growth; the population ages with it too")
    predictif.add_argument("--rate-name", required=True)
    predictif.add_argument("--rate-kind", required=True,
                           choices=["implicite_tenu", "marche"])
    predictif.add_argument("--market-rate", type=float)
    predictif.add_argument("--horizon", type=int, required=True)
    predictif.add_argument("--theta", type=float, required=True,
                           help="θ commun, de 0 à 1, sans défaut (D-217). La commande ne "
                                "chiffre aucun comportement : il est listé, pas lu.")
    predictif.add_argument("--wage", type=float, required=True,
                           help="annual wage growth used to age the population")
    predictif.add_argument("--hypothesis-source", required=True,
                           help="where the indices come from — declared, never forecast")
    predictif.add_argument("--base-year", type=int, default=2024)
    predictif.add_argument("--vintage", type=millesime, default="2024")
    predictif.add_argument("--sample", type=int, default=20_000)
    predictif.add_argument("--titre")
    predictif.add_argument("--dir")
    predictif.add_argument("--out-dir")
    predictif.add_argument("--behavioural", action="store_true",
                           help="the receipts at θ each year, through the simulator's pass")
    predictif.add_argument("--macro", action="store_true",
                           help="the GDP → receipts loop, one impulse per year (D-236)")
    predictif.add_argument("--ou", help="where the passes run, which the report says "
                           "(D-275)")
    predictif.add_argument("--persistence", choices=["lue", "eteint", "tenu"],
                           help="past three years with the loop; all three side by side if absent")
    predictif.set_defaults(func=cmd_predictif)

    exploration = subcommands.add_parser(
        "exploration",
        help="search the bundles whose debt difference meets a target, at a fixed θ "
             "(Phase 10 M1)")
    exploration.add_argument("request", help="an ExplorationRequest, as a JSON file")
    exploration.add_argument("--max-paquets", type=int, default=12,
                             help="refuse a larger grid rather than truncate it; each "
                                  "bundle is two quick passes")
    exploration.add_argument("--out-dir")
    exploration.add_argument("--ou", help="where the passes run, which the report says "
                                          "(PHASE10_SPEC §5)")
    exploration.set_defaults(func=cmd_exploration)

    etude = subcommands.add_parser(
        "etude", help="une étude en trois réponses : ses passes, sa page (but 6, D-301)")
    etude_actions = etude.add_subparsers(dest="action", required=True)
    lancer = etude_actions.add_parser("lancer", help="les passes, l'une après l'autre")
    lancer.add_argument("nom", help="l'étude, etudes/<nom>.json")
    lancer.add_argument("--ou", required=True, help="where the passes run, which each "
                                                    "report says")
    premiere = etude_actions.add_parser("premiere", help="la première année d'un scénario")
    premiere.add_argument("nom")
    premiere.add_argument("scenario")
    premiere.add_argument("--ou", required=True)
    point = etude_actions.add_parser("plage", help="un point de la plage d'une mesure d'un "
                                                   "programme (D-328)")
    for arg in ("nom", "mesure", "champ", "point"):
        point.add_argument(arg)
    point.add_argument("--ou", required=True)
    for passe in (premiere, point):
        passe.add_argument("--sortie", help="écrire le rapport là, et non sous les rapports "
                                            "de l'étude : la passe témoin (D-335)")
    temoin = etude_actions.add_parser(
        "temoin", help="rejouer la passe la plus courte de l'étude sur ce commit, et dire si "
                       "elle redonne son rapport à l'identique (D-335, D-336)")
    temoin.add_argument("nom")
    temoin.add_argument("--ou", required=True)
    for action, text in (("avant", "figer ce que dit la série commitée, avant la suivante "
                                    "(D-350)"),
                         ("ecrire", "la page, depuis les seuls rapports commités"),
                         ("verifier", "la page commitée est-elle celle de ses rapports ?")):
        etude_actions.add_parser(action, help=text).add_argument("nom")
    etude.set_defaults(func=cmd_etude)

    grille_parser = subcommands.add_parser(
        "grille", help="la grille des curseurs : ses passes, un point, sa compilation "
                       "(but 15, D-343)")
    grille_actions = grille_parser.add_subparsers(dest="action", required=True)
    grille_lancer = grille_actions.add_parser("lancer", help="toutes les passes, reprises")
    grille_lancer.add_argument("--ou", required=True)
    grille_point = grille_actions.add_parser("point", help="une passe de la grille")
    grille_point.add_argument("genre", choices=("point", "temoin", "paire"))
    grille_point.add_argument("cible", help="le curseur, ou « a,b » pour une paire")
    grille_point.add_argument("index", type=int, help="l'index du point, -1 sinon")
    grille_point.add_argument("--ou", required=True)
    grille_point.add_argument("--sortie")
    grille_actions.add_parser("compiler", help="site/grille.json, depuis les rapports")
    grille_parser.set_defaults(func=cmd_grille)

    programme = subcommands.add_parser(
        "programme", help="un programme présidentiel : sa part chiffrée, ses refus, et ses "
                          "trois réponses (but 11, D-319)")
    programme.add_argument("slug", nargs="?", help="programmes/<slug>.json ; sans lui, la "
                                                   "liste des programmes")
    programme.add_argument("--valeur", action="append", metavar="MESURE:CHAMP=VALEUR",
                           help="un paramètre réglé dans sa plage, autant que voulu")
    programme.add_argument("--mesures", help="les seules mesures chiffrées retenues, par id, "
                                             "séparées par des virgules")
    programme.add_argument("--rho", type=float, help="la réalisation des annonces du "
                                                      "candidat, dans [0, 1] : la couche "
                                                      "déclarée, à part (D-319)")
    programme.add_argument("--hypotheses", help="un JSON des hypothèses de la chaîne (θ, "
                                                "croissance, taux, dépense, horizon, "
                                                "salaires) : sans lui, rien n'est simulé")
    programme.add_argument("--sortie", help="où écrire le rapport JSON")
    programme.set_defaults(func=cmd_programme)

    verif = subcommands.add_parser(
        "verification", help="la grille de vérification : chaque instrument contre un "
                             "total publié (but 18, D-362)")
    verif_actions = verif.add_subparsers(dest="action", required=True)
    verif_passe = verif_actions.add_parser("passe", help="une passe d'une année")
    verif_passe.add_argument("--annee", type=int, required=True)
    verif_passe.add_argument("--lots", type=int, default=4)
    verif_actions.add_parser("ecrire", help="la grille et la loi d'erreur")
    verif.set_defaults(func=cmd_verification)

    site = subcommands.add_parser(
        "site", help="le site statique des études : sans calcul, sans script (but 7, D-304)")
    site_actions = site.add_subparsers(dest="action", required=True)
    site_actions.add_parser("construire", help="site/, depuis les études et leurs rapports")
    site_actions.add_parser("verifier", help="le site commité est-il celui des études ?")
    site_actions.add_parser("publiable", help="le site dit-il où signaler une erreur ? (D-357)")
    site.set_defaults(func=cmd_site)

    emtr_parser = subcommands.add_parser(
        "emtr", help="sweep a household type across the income range (F6)")
    emtr_parser.add_argument("type")
    emtr_parser.add_argument("--year", type=int, default=2024)
    emtr_parser.add_argument("--step", type=float, default=500.0)
    emtr_parser.add_argument("--max", type=float, default=60_000.0)
    emtr_parser.add_argument("--reform", help="path to a ReformSpec JSON file")
    emtr_parser.set_defaults(func=cmd_emtr_explorer)

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
