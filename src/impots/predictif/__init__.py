"""The conditional predictive layer (Phase 9, D-213).

Every effect on behaviour and on the economy is set by a coefficient θ in [0, 1] that
places it inside its published range, and every result reads « si θ = … » under named
scenarios. Nothing here is a forecast: change θ or a scenario and the answer changes, and
the sweep of θ from 0 to 1 is the honest answer.

`chaine` links reform → primary balance → debt (M1, D-215); `annuel` prices every year
(M1b, D-216); `theta`, `comportement` and `macro` place each effect in its range (M2,
D-217); `retroaction` reads Mésange's balance row for the GDP → receipts loop (M3, D-218).
What a result does not carry is reported ABSENT with its reason, never drawn as zero.
"""
