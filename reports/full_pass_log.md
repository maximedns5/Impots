# Full-pass log

One line per `make full`. CI cannot run the population tests — it has no
population, by design — so this file is the only record that the full suite is
green. No review handoff goes out without a line newer than the work it reports.

> **Les lignes antérieures au 2026-09-08 ne sont pas des preuves.** La cible `make full`
> lisait le code de sortie de `tail` et non celui de pytest, si bien que `result` valait
> toujours PASS et que la sortie de pytest était avalée en chemin : une exécution en échec
> n'imprimait rien et journalisait PASS. Corrigé le 2026-09-08 (D-094), vérifié dans les
> deux sens. La colonne `tests` vide de ces lignes est le second symptôme — un `sed`
> refusé par BSD.

| date | commit | result | duration | tests |
|---|---|---|---|---|
| 2026-09-03 | `edbcd16` | PASS | 19m17s |  |
| 2026-09-03 | `ca609af` | PASS | 27m02s |  |
| 2026-09-08 | `a576773` | PASS | 60m45s |  |
| 2026-09-08 | `a576773` | PASS | 60m53s | 1042 passed, 2 skipped, 18 warnings |
| 2026-09-08 | `32c4de1` | PASS | 58m42s | 1142 passed, 2 skipped, 18 warnings |
| 2026-09-08 | `81510fa` | PASS | 56m46s | 1168 passed, 5 skipped, 18 warnings |
| 2026-09-08 | `9b0a5aa` | PASS | 66m30s | 1197 passed, 2 skipped, 18 warnings |
| 2026-09-09 | `cc4a629` | PASS | 60m53s | 1262 passed, 2 skipped, 18 warnings |
| 2026-09-09 | `f593847` | TUÉ | 214m11s | interrompu par l'opérateur, PAS un échec : deux passes concurrentes après un réveil de veille, charge 110 sur 8 cœurs. La colonne comptes portait des points de progression, pas un résumé. Voir D-113. |
| 2026-09-09 | `f593847` | TUÉ | 195m51s | interrompu par l'opérateur, PAS un échec : deux passes concurrentes après un réveil de veille, charge 110 sur 8 cœurs. La colonne comptes portait des points de progression, pas un résumé. Voir D-113. |
| 2026-09-09 | `f593847` | PASS | 82m49s | 1313 passed, 2 skipped, 18 warnings |
| 2026-09-10 | `2917acf` | PASS | 60m44s | 1338 passed, 2 skipped, 18 warnings |
| 2026-09-11 | `b66d49f` | PASS | 65m12s | 1340 passed, 5 skipped, 18 warnings |
| 2026-09-11 | `db1ab7f` | PASS | 58m57s | 1352 passed, 2 skipped, 18 warnings |
| 2026-09-12 | `31741ae` | PASS | 58m16s (horloge 359m, machine en veille) | 1356 passed, 2 skipped, 18 warnings |
| 2026-09-13 | `76f0c49` | PASS | 59m55s (horloge 154m, machine en veille) | 1358 passed, 2 skipped, 18 warnings |
| 2026-09-18 | `46bc81f` | FAIL | 69m53s | 8 failed, 1393 passed, 4 skipped, 10 warnings |
| 2026-09-23 | `3101fff` | FAIL | 50m25s | 12 failed, 1443 passed, 138 skipped, 1 warning, 6 errors |
| 2026-09-23 | `f1e5837` | PASS | 79m42s | 1697 passed, 5 skipped, 18 warnings |
| 2026-09-23 | `9442046` | PASS | 64m41s | 1697 passed, 5 skipped, 18 warnings |
| 2026-09-25 | `a9ea26f` | PASS | 60m31s | 1724 passed, 3 skipped, 18 warnings |
