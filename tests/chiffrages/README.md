# Chiffrage backtest cases

One YAML per historical article. The suite compares this simulator's **mechanical**
result against the **published mechanical** costing — so it grades L2 on historical
law, independently of everything the behavioural layer adds.

```yaml
key: ir_bareme_indexation_2024
article: "LFI 2024, art. 2"
year: 2024
scope: household            # household | firm
description: Indexation du barème de l'IR sur l'inflation (+4,8 %)
reform:                     # a ReformSpec the simulator can express
  ir_bareme:
    - {threshold: 0, rate: 0.00}
    - {threshold: 11294, rate: 0.11}
published:
  amount_eur: 6.1e9
  sign: cost                # cost | yield — carried, never inferred
  basis: annee-pleine       # annee-pleine | premiere-annee | unstated
  source:
    document: Voies et moyens tome I, PLF 2024
    url: https://…          # required: a case without one cannot be re-found
    page: "p. 34"
    quote: "…"              # verbatim
    checked: 2026-09-02
tolerance: 0.15
tolerance_reason: >
  Why this number and not another. Declared per case: a 2013 measure run against a
  2024 population is not owed the same latitude as a 2024 one.
caveat: >
  Anything a reader needs in order not to over-read the result.
```

A red case is a **finding to write up**, never a number to tune away, and
mechanical-before-economic (D-029) binds: try wrong vintage, a knob that does not
express the article, and an année-pleine/première-année basis mismatch *before*
reaching for population realism.
