"""The conditional predictive layer (Phase 9, D-213).

Every effect on behaviour and on the economy is set by a coefficient θ in [0, 1] that
places it inside its published range, and every result reads « si θ = … » under named
scenarios. Nothing here is a forecast: change θ or a scenario and the answer changes, and
the sweep of θ from 0 to 1 is the honest answer.

M1 (this package's first module, `chaine`) links the chain reform → primary balance →
debt. θ arrives in M2 and the GDP → receipts feedback in M3; until then each is reported
ABSENT with its reason, never drawn as zero.
"""
