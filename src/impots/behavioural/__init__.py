"""The behavioural layer (L3) — bands, not point estimates.

Official French costings are mechanical by design; FIPECO's own defence is that
behavioural responses are "difficult, often impossible to measure". This project's
claim is that showing the band honestly — as a range with its evidence attached and
its applicability graded — beats omitting it. This package is that claim.

The layer boundary is the product. Nothing in `engine/`, `population/` or
`entreprises/` knows this package exists, and the mechanical number it post-processes
is never modified. A test asserts exactly that.
"""
