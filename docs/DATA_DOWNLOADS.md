# Data to download — status as of 2026-08-29, bootstrap added 2026-09-24

Everything goes into `data/raw/` with a `MANIFEST.json` entry (sha256, URL,
date). The P2 pre-commit guard keeps raw data out of git. Cloud/bridge egress
blocks insee.fr file paths, so these are downloaded on the Mac (browser or
curl on Max's own network).

## The bootstrap — `make data`, or `impots data prepare` (D-158)

What the test suite reads is now declared, fetched and checked by one command
instead of discovered one failure at a time.

```
impots data check   --profile tests   # preflight: what is missing, and the command that fixes it
impots data fetch   --profile tests   # download by manifest entry: URL, size, sha256
impots data prepare --profile tests   # fetch + build the derived artefacts + check
make data                             # the same, as a target
```

**The `tests` profile is derived from the readers' own constants**, not listed by
hand: 10 raw sources (16,8 Mo, all Licence Ouverte or open access, all sourced in the
manifest) and 2 derived artefacts.

| artefact | produced by | read by |
|---|---|---|
| `dgfip_stats_33_ifi_2024.xlsx` | fetch (impots.gouv.fr) | IFI tranches — `test_accuracy` |
| `dgfip_stat_41_ir_2024_tables.xlsx` | fetch (impots.gouv.fr) | top-tail targets — `test_top_tail` |
| `imk_wp117_…pdf`, `imk_wp139_…pdf`, `insee_G2017-04_mesange.pdf` | fetch (econstor.eu, insee.fr) | the macro store — `test_trajectoires` |
| `insee_esane2023_…xlsx`, `insee_focus372_…xlsx`, `dgfip_stat_39_…xlsx` | fetch | inputs of the firm cell table |
| `FD_EEC_2024.parquet`, `Varmod_EEC_2024.csv` | fetch (insee.fr) | inputs of the population |
| `data/processed/firm_cells_2023.json` | `impots entreprises cells` | firm placement sampler — `test_accuracy` |
| `data/processed/population_2024.parquet` | `impots population build` | `test_zero_masked`, the API |

**Three things this replaced, each a defect rather than a missing file.** No command
wrote `firm_cells_2023.json` — it was only ever read, and a code comment called it
« Committed » when `data/processed/*` is gitignored and it has never been in git. The
macro store reads THREE documents while the failing test's trace named one. And four
modules resolved `data/...` against the current directory rather than the repository.

**What the fetch refuses**: a quarantined or URL-less entry (D-028), and any served
file whose byte count or sha256 differs from the manifest — the `.part` is deleted and
nothing is written. A publication that changed under the same URL is a vintage
decision to record (D-004), not an update to absorb.

`make full` runs the preflight first and stops in about a second if anything is
missing, instead of failing 47 minutes in.

## Household side (Phase 1C — the priority)

| What | Where | Status |
|---|---|---|
| **ERFS fichier détail** (latest vintage) + documentation | Quetelet-Progedo / data.progedo.fr — the request per docs/PHASE1C_ERFS.md §2 | **Not available for the foreseeable future** (D-096). The 1C migration is a plan on the shelf, not a queue being waited on. If access ever opens, nothing about the plan changes. NEVER into git (D-016). |
| EEC FD 2024 (parquet + Varmod + dictionnaire PDF) | insee.fr/fr/statistiques/8632441 | done (M0) |
| Filosofi latest tables | insee.fr + data.gouv.fr | done if used by reconcile; re-pull the 2023 vintage tables if only partials are on disk |

## Firm side (Phase 2, milestone M2)

| What | Where | Notes |
|---|---|---|
| **SIRENE stock** — `StockUniteLegale_utf8.zip`, `StockEtablissement_utf8.zip` | files.data.gouv.fr/insee-sirene/ (monthly refresh; take one dated vintage and pin it) | firm skeleton: counts by NAF × size band × catégorie juridique. Big (GBs unzipped) — keep zipped, read streaming. |
| **ESANE** — "caractéristiques comptables, financières et d'emploi des entreprises" by sector (A38/A88) × size | insee.fr (Esane annual results, latest vintage ~2023) | CA / VA / EBE / résultat per cell — the financial layer |
| **DGFiP IS statistics** — recettes, nombre de redevables, répartition des bénéfices, share of deficit firms | impots.gouv.fr/statistiques + data.economie.gouv.fr + Voies et Moyens tome I (PLF 2026/2027) | validation lines + the §3.3 scalars (P(loss), fiscal/comptable ratio) |
| **CVAE + C3S receipts** by year | Voies et Moyens / comptes de la Sécurité sociale (C3S) / DGCL for CVAE local shares | validation lines |
| **URSSAF open data** — wage bill, effectifs by sector × size | open.urssaf.fr | already in use for Phase 1; firm-side cross-check |
| Effective-rate-by-size profile | CPO / DGFiP publications (taux implicite d'IS par taille) | the firm analogue of D9/D1 — validation shape line |

## Explicitly NOT needed yet

* Budget de Famille (indirect taxes — Phase 4; 2026 wave microdata lands ~2027-28).
* INSEE TES input-output (Phase 3 macro layer).
* BODACC / RNE bulk (firm demography dynamics — not in mechanical v1).
* Anything CASD (FARE, LIFI, POTE, DSN): out of reach by design; the day that
  changes is the day this file gets a new section.
