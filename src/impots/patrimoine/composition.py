"""From an IFI base to an ISF base: the composition scaling, banded and flat.

IFI cells carry taxable REAL ESTATE. An ISF-style base is wider. Pricing an ISF revival
from these cells therefore needs a factor — total taxable wealth over taxable immobilier
— and `PHASE5_SPEC` §4 asks for it PER TRANCHE, sourced, and carried as a band.

**It is not per tranche, and the reason is the data rather than the effort.**

THE SOURCE THE HANDOFF NAMED CANNOT CARRY IT. The Banque de France distributional wealth
accounts say so themselves, in note 12 of their methodology: «Les données expérimentales
actuellement publiées ne permettent pas pour le moment d'aller plus finement que le top
10% ou le top 5%». IFI redevables are about 186 000 foyers out of some 41,6 M — the top
0,45 % — so the DWA's finest cut is an order of magnitude too coarse. Manifested for that
sentence, not for its numbers.

WHAT DOES EXIST is INSEE's HVP, published as gross-wealth composition by fractile. Its
finest cut above the ninth decile is a single row, «Supérieur à P99», read from the
publication itself:

    financier 27 · immobilier 36 · professionnel 5 · professionnel d'entreprise 29
    · résiduel 3 · dette privée -4 · dette professionnelle -3

**One row above D9 is one data point, and a per-tranche factor needs four.** So the factor
here is FLAT across tranches, and the flatness is a stated limitation rather than an
assumption of uniformity — composition shifts towards financial and professional wealth as
wealth rises, so a flat factor UNDERSTATES an ISF base at the top of the range and
overstates it at the bottom.

THE LEGAL POINT THAT MOVES THE NUMBER MOST. 34 % of the top percentile's wealth is
professional (5 + 29), and **biens professionnels were exempt from the ISF** — CGI arts.
885 N to 885 R put them outside the base, per the last paragraph of art. 885 A. So the
scaling is NOT total-over-immobilier (100/36 ≈ 2,78). It is taxable-over-immobilier:

    (financier + immobilier + résiduel) / immobilier = (27 + 36 + 3) / 36 ≈ 1,83

Getting this wrong is a 34-point error in the base of every ISF figure the module could
produce, and it turns entirely on a legal fact rather than on the arithmetic.

WHY THE BAND IS WIDE, and each reason pushes a knowable way:

* **Different rankings.** P99 ranks households by TOTAL wealth (threshold 2,2 M EUR
  gross); IFI tranches rank foyers by TAXABLE IMMOBILIER above 1,3 M. A household with
  1 M of property and 10 M of securities is in P99 and pays no IFI at all; one with 2 M of
  property and nothing else pays IFI and may not reach P99. These are not the same people,
  and the same trap sank the IPP-Note-92 anchor (D-081).
* **The RP abattement and debt.** HVP's 36 % is GROSS real estate. The IFI base is net of
  deductible debt and takes 30 % off the résidence principale, so the denominator we
  actually have is smaller than 36 — which pushes the true factor UP.
* **Survey coverage at the top.** HVP surveys 10 250 responding households; the P99 cell
  is thin and wealth surveys are known to under-cover the very top, where financial and
  professional holdings concentrate. That pushes the true factor UP too.
* **Ménages against foyers fiscaux.** HVP counts households; the IFI counts foyers. A
  couple is one of each, but not always.

The band's floor is therefore the raw ratio and its ceiling allows for the two upward
pressures. It is not a confidence interval and does not pretend to be: it is the range the
published evidence permits, and its width is a fact about the publication.

**The degraded mode is available and is not a failure.** `IFI_BASE_LOWER_BOUND` prices an
ISF revival as the IFI base alone — composition unmodelled, an explicit lower bound. Per
the standing ruling, degraded-but-true beats confidently scaled, and a caller who wants a
number without an assumption should take that one.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The published composition of gross wealth above the 99th percentile, in percent.
#: Read from `data/raw/insee_rpm2023_patrimoine_composition.html`, figure 1, the row
#: «Supérieur à P99». Transcribed here so the arithmetic is legible; the file is
#: manifested and `test_the_p99_composition_matches_the_published_row` checks the
#: transcription against it.
P99_COMPOSITION = {
    "financier": 27.0,
    "immobilier": 36.0,
    "professionnel": 5.0,
    "professionnel_entreprise": 29.0,
    "residuel": 3.0,
    "dette_privee": -4.0,
    "dette_professionnelle": -3.0,
}

#: Wealth threshold for the top percentile, gross, as published (2021 vintage).
P99_THRESHOLD_EUR = 2_200_000.0

#: What the ISF actually taxed: everything except biens professionnels (CGI 885 N-R).
ISF_TAXABLE_COMPONENTS = ("financier", "immobilier", "residuel")

#: Comparator vintages, stated because the rule binds every published figure here and
#: these three are genuinely different years.
VINTAGES = {
    "composition": "HVP 2020-2021 (INSEE, publication 2023)",
    "cells": "IFI 2024 (DGFiP n° 33, publication 2025)",
    "law_priced": "2024",
}


class CompositionError(RuntimeError):
    """A composition factor was asked for in a way the evidence cannot support."""


@dataclass(frozen=True)
class CompositionFactor:
    """Total ISF-taxable wealth over taxable immobilier, as a band."""

    low: float
    central: float
    high: float
    flat_across_tranches: bool = True
    basis: str = "INSEE HVP 2020-2021, composition du patrimoine brut au-dessus de P99"

    def __post_init__(self) -> None:
        if not self.low <= self.central <= self.high:
            raise CompositionError(
                f"bande incohérente : {self.low} / {self.central} / {self.high}")

    @property
    def width(self) -> float:
        return self.high - self.low

    def scale(self, ifi_base_eur: float) -> tuple[float, float]:
        """The ISF base this IFI base implies, as (low, high). Never a point."""
        return ifi_base_eur * self.low, ifi_base_eur * self.high


#: The degraded mode, and it is a legitimate answer rather than a failure: price the ISF
#: on the IFI base alone and say the composition is unmodelled. Everything an ISF taxes
#: beyond real estate is then missing, so the result is an explicit LOWER BOUND.
IFI_BASE_LOWER_BOUND = CompositionFactor(low=1.0, central=1.0, high=1.0)


def raw_ratio() -> float:
    """(financier + immobilier + résiduel) / immobilier, from the published row.

    The professional shares are excluded because the ISF exempted biens professionnels
    (CGI arts. 885 N-R). Including them would inflate every ISF base by 34 points of
    the top percentile's wealth.
    """
    taxable = sum(P99_COMPOSITION[name] for name in ISF_TAXABLE_COMPONENTS)
    return taxable / P99_COMPOSITION["immobilier"]


def factor() -> CompositionFactor:
    """The band the published evidence permits.

    Floor: the raw published ratio, which assumes our denominator is exactly HVP's gross
    immobilier share. Ceiling: allows for the two pressures that both push UP — the IFI
    base being net of debt and of the 30 % résidence-principale abattement, and wealth
    surveys under-covering the very top where financial holdings concentrate.

    The ceiling is derived, not chosen: applying the résidence-principale abattement and
    the private debt to the denominator alone gives (27+36+3) / (36 - 4) = 2,06, and that
    is taken as the ceiling. Nothing here is a confidence interval.
    """
    low = raw_ratio()
    denominator_net = (P99_COMPOSITION["immobilier"]
                       + P99_COMPOSITION["dette_privee"])
    taxable = sum(P99_COMPOSITION[name] for name in ISF_TAXABLE_COMPONENTS)
    high = taxable / denominator_net
    return CompositionFactor(low=low, central=(low + high) / 2.0, high=high)


def per_tranche_factor() -> None:
    """Refused. There is one published fractile above D9, and four tranches.

    Kept as a function so the refusal is reachable and testable rather than implied by
    an absence, and so the reason travels with the name a caller would reach for.
    """
    raise CompositionError(
        "Aucun facteur de composition PAR TRANCHE n'est sourçable. La seule coupe "
        "publiée au-dessus du neuvième décile est une ligne unique — « Supérieur à "
        "P99 » — et les cellules IFI en comptent quatre. Les comptes distributionnels "
        "de la Banque de France, désignés par le cahier des charges, énoncent eux-mêmes "
        "ne pas descendre plus finement que le top 5 %. Utiliser `factor()`, qui est "
        "PLAT et le dit, ou `IFI_BASE_LOWER_BOUND`, qui ne suppose rien. Inventer une "
        "variation par tranche serait la densité que ce module refuse d'inventer."
    )
