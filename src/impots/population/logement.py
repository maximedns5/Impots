"""Where a ménage lives, for the housing aid: its APL zone, its DOM, its rent.

The EEC has no commune. It says whether the commune is a ville-centre, a banlieue, a
ville isolée or outside any urban unit (`STCOMM2020`), and whether it is in
metropolitan France or a DOM (`METRODOM`). The housing aid needs more: the APL zone
sets the loyer plafond, and Paris and its agglomeration (zone 1) have the highest.

**The zone is drawn**, not mapped. Before, ville-centre and banlieue were zone 2 and
the rest zone 3, so that no ménage was in zone 1 and every tenant of a banlieue of
Paris had the plafond of Tours. Now each ménage gets zone 1, 2 or 3 with the share of
the census's résidences principales of its kind (same urban-unit status, same tenure:
HLM, other tenant, owner) that are in a commune of that zone
(`margins.APL_ZONE_BY_STCOMM`). The level is right by construction; which ménages are
in zone 1 is not known, so their other traits are those of a banlieue or a
ville-centre at large. Every DOM is zone 2.

**The DOM département is drawn** the same way, on the census's résidences principales
(`margins.DOM_HOUSEHOLDS_BY_DEPARTEMENT`), and passed to openfisca as a commune code
(`to_openfisca`), so that the DOM's own rules apply: the allocations familiales from
the first child, the housing aid's plafonds and forfait de charges, the income tax's
abattement.

**The social rent** is the RPLS's euros per m² (Île-de-France for zone 1, province and
DROM elsewhere) times the surface rule of `SURFACE_BASE_M2` and
`SURFACE_PER_PERSON_M2`, an assumption. The private rent keeps the figure it had.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from impots.population import margins

#: The draws read their own stream: nothing else in the skeleton moves.
ZONE_STREAM = 8

#: Surface of the dwelling, an assumption (no published surface distribution is used).
SURFACE_BASE_M2 = 30.0
SURFACE_PER_PERSON_M2 = 12.0

ZONES = ("zone_1", "zone_2", "zone_3")
RENTERS = ("locataire_vide", "locataire_meuble", "locataire_foyer")


def tenure_class(statut: np.ndarray) -> np.ndarray:
    """The census's three tenures as the zone table splits them."""
    return np.where(statut == "locataire_hlm", "hlm",
                    np.where(np.isin(statut, RENTERS), "autre_locataire", "autre"))


def draw_zone_and_departement(
    stcomm: np.ndarray, dom: np.ndarray, statut: np.ndarray, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """One APL zone and one DOM département (None in metropole) per ménage.

    The arrays are per ménage, in a fixed order. One uniform per ménage decides both:
    the zone in metropole, the département in a DOM.
    """
    rng = np.random.default_rng([seed, ZONE_STREAM])
    u = rng.random(len(stcomm))
    tenure = tenure_class(np.asarray(statut))
    zone = np.full(len(stcomm), "zone_3", dtype=object)
    for key, counts in margins.APL_ZONE_BY_STCOMM.items():
        status, cls = key.split("|")
        mask = (np.asarray(stcomm) == status) & (tenure == cls) & ~np.asarray(dom)
        cumulative = np.cumsum(counts) / sum(counts)
        zone[mask] = np.array(ZONES, dtype=object)[
            np.searchsorted(cumulative, u[mask], side="right").clip(0, 2)]
    departement = np.full(len(stcomm), None, dtype=object)
    dom = np.asarray(dom)
    if dom.any():
        codes = np.array(list(margins.DOM_HOUSEHOLDS_BY_DEPARTEMENT), dtype=object)
        counts = np.array(list(margins.DOM_HOUSEHOLDS_BY_DEPARTEMENT.values()))
        cumulative = np.cumsum(counts) / counts.sum()
        departement[dom] = codes[np.searchsorted(cumulative, u[dom], side="right").clip(
            0, len(codes) - 1)]
        zone[dom] = "zone_2"
    return zone, departement


def monthly_rent(statut: np.ndarray, zone: np.ndarray, household_size: np.ndarray
                 ) -> np.ndarray:
    """The monthly rent, hors charges, per person row (every member carries it)."""
    surface = SURFACE_BASE_M2 + SURFACE_PER_PERSON_M2 * household_size
    social_per_m2 = np.where(
        zone == "zone_1", margins.HLM_RENT_PER_M2["ile_de_france"].value,
        margins.HLM_RENT_PER_M2["province_drom"].value)
    social = statut == "locataire_hlm"
    private = np.isin(statut, RENTERS)
    return np.where(social, surface * social_per_m2,
                    np.where(private, surface * margins.RENT_PER_M2["prive"].value, 0.0))


def household_size(frame: pl.DataFrame) -> np.ndarray:
    """The number of persons of each row's ménage, per row."""
    return (
        frame.group_by("household_id").agg(pl.len().alias("size"))
        .join(frame.select("household_id"), on="household_id", how="right")["size"]
        .to_numpy()
    )
