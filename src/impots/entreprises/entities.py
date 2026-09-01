"""The one entity the firm module has.

`is_person=True` is not a philosophical claim: openfisca-core needs exactly one
person-like entity per system, and here the taxable unit *is* the firm. A
single-entity system has no roles to join, which is why the silent role-drop that
cost Phase 1 a day cannot happen here.
"""

from __future__ import annotations

from openfisca_core.entities import build_entity

Entreprise = build_entity(
    key="entreprise",
    plural="entreprises",
    label="Unité légale soumise à l'impôt sur les sociétés",
    doc="""One legal unit (unité légale) in the SIRENE sense, liable to corporation
    tax. Not an establishment, and not a group: intégration fiscale is out of scope
    for v1 and would need LIFI, which is not open data.""",
    is_person=True,
)
