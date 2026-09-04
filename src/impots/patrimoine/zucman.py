"""A Zucman-style floor, and why it cannot be priced from the published cells.

PHASE5_SPEC §2 asks for a ">=100 M extension cell" to price a minimum tax on very large
wealth, and names its anchor: "IPP Note 92 ... for counts/aggregates at the very top —
read from the PDF per D-026, LOW confidence".

**The note carries no wealth figures at all.** Read and verified against the PDF: its
only table is titled "Distribution des revenus en 2016" and its two euro columns are
"Revenu fiscal (en euros)" and "Revenu économique (en euros)". There is no patrimoine
column, no wealth band and no wealth fractile. The authors state that their income
measure "n'inclut ni les variations de patrimoine, ni les revenus latents non encore
réalisés" — they exclude wealth on purpose.

**And it contains a number designed to be misread.** Row P99,9998 holds `75` households
and `150 040 000` — a nine-figure euro amount next to a small count in a note about
"milliardaires". That is the ANNUAL ECONOMIC INCOME threshold for entering the top
0,0002 %, not a wealth threshold; the mean beside it, 634 504 000, is mean annual income.
Building a ">=100 M" cell on either would silently swap an income dimension for a wealth
one, and the resulting figure would look entirely reasonable.

So the spec's premise is half right and it is the wrong half: the note supplies counts
and aggregates of INCOME at the very top.

WHAT REMAINS TRUE, AND WHY IT IS STILL NOT ENOUGH. The note does print a complete
fractile-to-headcount mapping (37 833 500 foyers at P0 down to 75 at P99,9998), so
"top 0,0002 %" resolves to "75 foyers" from the printed table alone. The missing leg is
headcount-to-WEALTH, and no external join fixes it cleanly either: those 75 foyers are
ranked by economic income, and the top-75-by-income set is not the top-75-by-wealth set.

WHAT THIS MODULE DOES INSTEAD. It refuses to invent the cell, and prices a floor only as
an explicit function of a ceiling the caller must supply and source. The DGFiP cells stop
at an OPEN tranche above 10 M — there is no published ceiling — so the placement of mass
inside that tranche is exactly what a 100 M floor depends on, and it is exactly what is
unpublished. `price_floor` therefore returns a band that widens with the assumed ceiling
and is labelled a construction wherever it appears.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

from impots.patrimoine import placement
from impots.patrimoine.bareme import Scale
from impots.patrimoine.cells import IfiCell


class ZucmanAnchorError(RuntimeError):
    """A floor was asked for without an anchor the published data can support."""


#: Stated so a reader meets it wherever the number goes, per §2's "visually flagged as a
#: construction everywhere it appears".
CONSTRUCTION_BANNER = (
    "CONSTRUCTION — pas une mesure. Aucune source publiée ne donne le nombre de foyers "
    "au-dessus de 100 M€ de patrimoine ni ce qu'ils détiennent : la tranche haute de la "
    "DGFiP est OUVERTE au-dessus de 10 M€, et l'IPP Note 92, que le spec désignait comme "
    "ancrage, ne contient aucun chiffre de patrimoine. Le résultat ci-dessous est donc "
    "fonction d'un plafond POSÉ, pas mesuré, et il bouge avec lui."
)


#: What a Zucman-style floor would need before it could be priced here, and which of
#: those this project has. Written as data so the refusal message cannot drift from the
#: reasons, and so a future increment can tick items off rather than re-derive them.
REQUIREMENTS: tuple[tuple[str, bool, str], ...] = (
    ("Effectifs et masse au-dessus de 100 M EUR de patrimoine", False,
     "La tranche haute publiée par la DGFiP est OUVERTE au-dessus de 10 M EUR. Rien "
     "n'est publié sur ce qu'elle contient, et c'est précisément ce dont un plancher à "
     "100 M dépend. L'IPP Note 92, désignée par le spec comme ancrage, ne porte aucun "
     "chiffre de patrimoine — seulement des revenus."),
    ("Patrimoine TOTAL, pas seulement immobilier", False,
     "Un plancher de type Zucman porte sur l'ensemble du patrimoine. Nos cellules ne "
     "portent que de l'immobilier taxable, parce que c'est ce que l'IFI mesure. Le "
     "passage de l'un à l'autre est la mise à l'échelle de composition du §4, qui doit "
     "être bandée et ne l'est pas encore."),
    ("Impôts sur le REVENU acquittés par ces foyers", False,
     "Le plancher se crédite de l'impôt sur le revenu payé, pas de l'IFI. Comparer un "
     "plancher à l'IFI seul est une erreur de dimension : mesuré, cela rend zéro pour "
     "tout plafond posé, parce que le taux marginal de 1,5 % de l'IFI sur toute la base "
     "au-dessus de 10 M dépasse 2 % sur le seul excédent au-dessus de 100 M. Un zéro "
     "produit par une comparaison mal posée est pire qu'un refus."),
    ("Un barème de l'IFI lisible et vérifié", True,
     "Acquis : M0 à M2. Ce n'est pas ce qui manque."),
)


def why_not_priceable() -> str:
    """The refusal, assembled from `REQUIREMENTS` so it cannot drift from them."""
    missing = [f"  - {what}\n      {why}" for what, have, why in REQUIREMENTS if not have]
    return (CONSTRUCTION_BANNER + "\n\nIl manque, pour chiffrer honnêtement :\n"
            + "\n".join(missing))


@dataclass(frozen=True)
class FloorEstimate:
    """What a floor yields, given an assumption that is stated rather than hidden."""

    threshold_eur: float
    rate: float
    assumed_ceiling_eur: float
    low_eur: float
    high_eur: float
    banner: str = CONSTRUCTION_BANNER

    @property
    def width_eur(self) -> float:
        return self.high_eur - self.low_eur


def price_floor(cells: list[IfiCell], scale: Scale, *, threshold_eur: float, rate: float,
                assumed_ceiling_eur: float | None) -> FloorEstimate:
    """A minimum tax of `rate` on wealth above `threshold_eur`, as a band.

    `assumed_ceiling_eur` is REQUIRED and has no default. The top published tranche is
    open, so without a ceiling the answer is unbounded rather than uncertain, and a
    default would be this project inventing the density it refuses to invent.
    """
    raise ZucmanAnchorError(
        f"Un plancher de {rate:.0%} au-dessus de {threshold_eur:,.0f} EUR n'est pas "
        f"chiffrable ici, et pas seulement faute d'un plafond.\n\n" + why_not_priceable()
    )


def _unreachable_pricing(cells: list[IfiCell], scale: Scale, *, threshold_eur: float,
                         rate: float, assumed_ceiling_eur: float | None) -> FloorEstimate:
    """The arithmetic, kept because it is right and its answer is not.

    Given a ceiling it computes the top-up correctly against the IFI — and returns ZERO
    for every plausible ceiling, because the IFI's 1,5 % marginal rate on the whole base
    above 10 M exceeds 2 % on the excess above 100 M. That result is arithmetically sound
    and substantively meaningless: a Zucman floor credits INCOME tax, not the IFI. It is
    kept, unreachable and tested, so nobody re-derives it and ships the zero.
    """
    if assumed_ceiling_eur is None:
        raise ZucmanAnchorError("no ceiling")
    if assumed_ceiling_eur <= threshold_eur:
        raise ZucmanAnchorError(
            f"Le plafond posé ({assumed_ceiling_eur:,.0f} EUR) est sous le seuil du "
            f"plancher ({threshold_eur:,.0f} EUR) : aucun foyer n'y serait soumis, et le "
            f"chiffrage vaudrait zéro pour une raison qui n'a rien à voir avec la mesure."
        )

    low = high = 0.0
    for cell in cells:
        placements = [placement.point_mass(cell)]
        with contextlib.suppress(placement.PlacementError):
            placements.append(placement.extremal(cell, ceiling=assumed_ceiling_eur))
        amounts = []
        for built in placements:
            floor_tax = sum(
                share * rate * max(0.0, base - threshold_eur)
                for base, share in built.points
            ) * cell.foyers
            current = built.tax(scale, cell.foyers)
            # A minimum tax tops up to the floor; it never refunds.
            amounts.append(max(0.0, floor_tax - current))
        low += min(amounts)
        high += max(amounts)
    return FloorEstimate(threshold_eur=threshold_eur, rate=rate,
                         assumed_ceiling_eur=assumed_ceiling_eur,
                         low_eur=low, high_eur=high)
