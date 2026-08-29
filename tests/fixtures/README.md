# Test fixtures

## `eec_sample.parquet`

400 complete dwelling-quarters (about 700 persons) drawn from the INSEE **Enquête
Emploi en Continu 2024, fichier détail**, with `seed=20240101`.

Sampled by *household*, not by person: the role-assignment logic under test
operates on whole dwellings, and a person-level sample would tear couples and
families apart and test nothing real.

**Source**: INSEE, https://www.insee.fr/fr/statistiques/8632441
**Licence**: Licence Ouverte / Etalab 2.0 — redistribution is permitted with
attribution, which is what makes committing this file legal.

It exists because CI has neither network access nor the 11.7 MB full file, and
because the population pipeline should be exercised on real EEC codes rather than
on invented ones: every silent-failure mode found in Phase 1 came from the shape
of the real data, not from its size.

**If the population ever moves to ERFS microdata (branch C, D-012), nothing
ERFS-derived may replace this file.** ERFS arrives under a signed agreement that
forbids redistribution; this fixture must stay EEC-derived or become fully
synthetic.
