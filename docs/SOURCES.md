# Data sources

## Open tier — usable today, no accreditation

| Source | Grain | Use | Endpoint |
|---|---|---|---|
| OpenFisca-France parameters | statutory rates, date-versioned | the legal rule set | pypi: OpenFisca-France |
| Filosofi | income deciles by commune/IRIS | calibration targets | insee.fr, data.gouv.fr |
| Enquête Emploi fichier détail | ~110k individuals/yr | population skeleton | insee.fr (open download) |
| SIRENE | exhaustive firm register | firm demography | portail-api.insee.fr |
| ESANE published tables | sector x size aggregates | firm calibration targets | insee.fr |
| URSSAF open data | quarterly wage bill, exonérations | contribution totals | open.urssaf.fr |
| INSEE TES | input-output flows | macro layer backbone | insee.fr |
| Voies et Moyens (PLF annexes) | tax yields, dépenses fiscales | validation ground truth | budget.gouv.fr |
| DBnomics | INSEE/Eurostat/OECD/BdF series | macro time series | db.nomics.world |
| BODACC, RNE/INPI | firm failures, filed accounts | firm distress, partial financials | data.gouv.fr |

## Accredited tier — CASD, needs an institution

ERFS-FPR, POTE, FARE/ESANE microdata, DSN/Base Tous Salariés, LIFI, EIC/EIR.
Comité du Secret Statistique authorisation, ~4-8 months lead time,
~EUR 290/month subsidised, 12-month minimum. An unaffiliated individual cannot
subscribe alone.

## The gap with no workaround

Budget de Famille: last usable vintage 2017. New wave launched Jan 2026,
microdata expected 2027-28. All indirect-tax incidence work before then rests
on nine-year-old consumption patterns or Eurostat's coarser HBS.
