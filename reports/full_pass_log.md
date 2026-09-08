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
