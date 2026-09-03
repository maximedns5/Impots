"""The macro layer (L4) — an explicit fan, never a forecast.

The original audit rated this layer one bar out of five: *"directionally informative,
quantitatively a range spanning a factor of 3–5. Label it as illustrative."* That is a
design input, not a defect to engineer away, and the fan's width is the honest form of
it.

The architectural rule the whole package exists to enforce: **multipliers and the
input-output table have disjoint jobs.** Literature multipliers already contain
input-output propagation and induced effects, so running a shock through the IO table
*and* applying a multiplier to the result counts the same euro twice. The aggregate
path comes from multiplier ranges on the leakage-corrected impulse; the IO table
supplies only what multipliers cannot — sectoral composition, and the import leakage
that scales the impulse before the multiplier sees it.
"""
