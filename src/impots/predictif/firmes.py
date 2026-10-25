"""Phase 11 M2 — the firm layer's two views (M0 of Phase 11, R7; D-246).

The firm population is one vintage — Ésane 2023 — priced under the law of the year. M1
served the same figure in both views (D-244). M0 fixed what each view is:

* FROZEN: the vintage as it is, under the law of the year — the analogue of the
  households' frozen population.
* AGED: that same cost followed at the pace of the scenario's NOMINAL GDP from the
  vintage's year. The national accounts give GDP up to the chain's start year; the
  growth scenario carries it beyond, exactly as `reference_years` grows the debt's
  denominator. A named convention, the analogue of the households' uprating — not a
  claim that profits track GDP year by year.

A vintage without a year — the committed fixture of synthetic test cells — has no aged
view: it is refused by name rather than given a year it does not have.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from impots.dette import comptes
from impots.dette.path import DebtError
from impots.dette.scenarios import GrowthScenario
from impots.predictif.chaine import START_YEAR

FROZEN, AGED = "figee", "vieillie"


class FirmViewError(ValueError):
    """The firm layer's view was asked for in a way it cannot honour."""


def base_year(vintage: str) -> int:
    """The year a firm vintage describes, or a refusal when it names none."""
    if not re.fullmatch(r"\d{4}", vintage):
        raise FirmViewError(
            f"la population d'entreprises « {vintage} » n'a pas d'année : sa vue vieillie, "
            f"le coût suivi au PIB nominal depuis le millésime, ne se calcule pas. Elle "
            f"n'en reçoit pas une par défaut ; construire le millésime réel "
            f"(`impots entreprises build`) et le servir (IMPOTS_FIRM_VINTAGE).")
    return int(vintage)


def nominal_gdp(year: int, growth: GrowthScenario,
                gdp_of: Callable[[list[int]], dict[int, float]] = comptes.gdp) -> float:
    """GDP in euros: the accounts up to the chain's start year, the scenario beyond."""
    if year <= START_YEAR:
        return float(gdp_of([year])[year])
    return float(gdp_of([START_YEAR])[START_YEAR]) * (1.0 + growth.nominal) ** (
        year - START_YEAR)


def aging_factor(year: int, growth: GrowthScenario | None, vintage: str,
                 gdp_of: Callable[[list[int]], dict[int, float]] = comptes.gdp) -> float:
    """GDP of `year` over GDP of the vintage's year: what the aged view multiplies by."""
    base = base_year(vintage)
    if growth is None:
        raise FirmViewError(
            "vue vieillie des entreprises sans scénario de croissance : le coût du "
            "millésime suit le PIB nominal du scénario, et aucun taux n'est choisi par "
            "l'outil")
    if year < base:
        raise FirmViewError(f"{year} précède le millésime {base} : la vue vieillie ne "
                            f"remonte pas le temps")
    try:
        return nominal_gdp(year, growth, gdp_of) / nominal_gdp(base, growth, gdp_of)
    except DebtError as error:
        raise FirmViewError(f"PIB des comptes illisible : {error}") from error


def convention(vintage: str) -> str:
    """The firm layer's conventions for a report that spans years: both views named once,
    without the factor of any one year."""
    return (f"Couche entreprises : le millésime {vintage}, sous le droit de chaque année. "
            f"Vue figée : le millésime tel quel ; vue vieillie : son coût suivi au PIB "
            f"nominal du scénario depuis le millésime (M0, R7). L'IS est compté à "
            f"l'exercice, non à la caisse (PHASE11_SPEC §3).")


def note(view: str, vintage: str, year: int, factor: float | None) -> str:
    if view == AGED and factor is not None:
        shown = f"{factor:.4f}".replace(".", ",")
        return (f"vue vieillie : le coût du millésime {vintage} suivi au PIB nominal du "
                f"scénario, ×{shown} jusqu'à {year} (M0, R7)")
    return f"vue figée : le millésime {vintage} tel quel"
