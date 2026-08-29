# Golden cases

Regression anchors, not truth claims. Each value here was produced by
`openfisca-france 176.0.8` / `openfisca-core 44.7.0` on 2026-08-28 and pins
*our wrapper against that version of the engine* — nothing more.

Tolerance is ±2 € (±0.001 for parts and rates). If a dependency bump moves a
value, that is a finding: record it in `docs/DECISIONS.md` and say why the law
or the engine changed. Do not silently re-anchor.

The independent check that these numbers are *right*, rather than merely stable,
is `CROSSCHECK.md` — a human entering the same households into the DGFiP
simulator.

## Schema

```yaml
name: str                 # must match the filename stem
description: str
year: int
tier: light | full
household: {...}          # the HouseholdInput wire format
reform: {...}             # optional ReformSpec
expected: {row: value}    # current-law column
expected_reform: {...}    # optional, reform column
expected_delta: {...}     # optional, reform - baseline
expected_emtr: float      # optional, full tier only
tolerance: float          # optional, defaults to 2.0
```
