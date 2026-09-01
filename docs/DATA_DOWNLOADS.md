# Data to download — status as of 2026-08-29

Everything goes into `data/raw/` with a `MANIFEST.json` entry (sha256, URL,
date). The P2 pre-commit guard keeps raw data out of git. Cloud/bridge egress
blocks insee.fr file paths, so these are downloaded on the Mac (browser or
curl on Max's own network).

## Household side (Phase 1C — the priority)

| What | Where | Status |
|---|---|---|
| **ERFS fichier détail** (latest vintage) + documentation | Quetelet-Progedo / data.progedo.fr — the request per docs/PHASE1C_ERFS.md §2, under Max's account | **Submit now if not done** — 2-6 weeks lead time gates the whole 1C migration. NEVER into git (D-016). |
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
