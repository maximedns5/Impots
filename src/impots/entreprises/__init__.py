"""Layer L0/L2 for firms: French corporate taxation as code, over a synthetic
firm population.

A sibling tax-benefit system on the same pinned `openfisca-core` — one engine,
two rule sets. Firms are not people, so nothing here is grafted into
openfisca-france; a single custom `entreprise` entity carries the whole module,
which means the subrole trap that dominated Phase 1 does not exist on this side.

Encodes: IS and its two surcharges (contribution sociale, CEBGE), CVAE, C3S.
Deliberately does not encode CFE — it depends on communal valeur locative and
thousands of local rates, and faking it would be worse than omitting it.
"""
