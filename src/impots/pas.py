"""Le calendrier du prélèvement à la source : l'effet budgétaire d'une année (D-291).

Le simulateur chiffre une année de revenus : l'effet d'une mesure d'impôt sur le revenu en
année pleine. Les évaluations préalables publient souvent l'effet budgétaire d'une année
civile, et sous le PAS les deux ne se confondent pas la première année. Comparer l'un à
l'autre est une discordance de base, que D-029 veut qu'on essaie d'abord comme explication
mécanique (D-204).

LE MODÈLE. Une mesure qui vaut à partir des revenus N0 pèse sur l'année civile Y :
- par le solde des avis sur les revenus Y−1 : l'impôt de ces revenus, moins le PAS déjà
  prélevé sur eux en Y−1 ;
- par le PAS de Y, dont le taux de janvier à août vient de l'impôt des revenus Y−2, et
  celui de septembre à décembre de l'impôt des revenus Y−1 (CGI, art. 204 H).
L'effet du taux sur le PAS est pris proportionnel à l'effet en année pleine des revenus
qu'il frappe. Pour une mesure en vigueur depuis N0, l'année N0+1 pèse donc l'année pleine
des revenus N0 et un tiers de celle des revenus N0+1 ; l'année N0+2, les deux tiers de
celle-ci et l'année pleine des revenus N0+2 ; ensuite, l'année pleine.

CE QU'IL NE PORTE PAS. Les grilles de taux par défaut, les acomptes des revenus sans tiers
collecteur et la modulation : le taux est celui du foyer, mis à jour en septembre. Il est
validé hors échantillon sur la seule chronique que l'annexe du PLF 2027 publie pour une
mesure de ce calendrier, l'art. 3 (1,4 ; 1,8 ; 1,1 Md€ pour 1,1 Md€ en année pleine), qu'il
redonne à 5 % près (`tests/test_pas.py`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

#: Les mois où le taux du PAS vient de l'impôt des revenus de l'année précédente :
#: septembre à décembre (CGI, art. 204 H).
MONTHS_UPDATED = 4


class PasError(ValueError):
    """Le calendrier ne peut pas être appliqué tel qu'on le demande."""


def budget_effects(full_year: Mapping[int, float], *, first_income_year: int,
                   years: Iterable[int], months_updated: int = MONTHS_UPDATED
                   ) -> dict[int, float]:
    """L'effet budgétaire de chaque année de `years`, depuis les effets en année pleine des
    années de revenus `full_year`, pour une mesure en vigueur à partir des revenus
    `first_income_year`."""
    if not isinstance(months_updated, int) or not 1 <= months_updated <= 12:
        raise PasError(f"{months_updated!r} mois : un nombre entier de mois, de 1 à 12.")
    share = months_updated / 12
    years = list(years)

    def effect(income_year: int) -> float:
        return full_year[income_year] if income_year >= first_income_year else 0.0

    needed = sorted({y for year in years for y in (year - 1, year)
                     if y >= first_income_year} - set(full_year))
    if needed:
        raise PasError(f"la mesure vaut à partir des revenus {first_income_year}, et l'effet "
                       f"en année pleine des revenus {needed} manque.")

    def withheld(year: int) -> float:
        """L'effet sur le PAS prélevé en `year` sur les revenus de `year`."""
        weight = ((1 - share) * (year - 2 >= first_income_year)
                  + share * (year - 1 >= first_income_year))
        return weight * effect(year)

    return {year: (effect(year - 1) - withheld(year - 1)) + withheld(year)
            for year in years}


def first_year_ratio(months_updated: int = MONTHS_UPDATED) -> float:
    """L'effet budgétaire de la première année sur l'effet en année pleine, à effet
    constant d'une année de revenus à l'autre."""
    return 1 + months_updated / 12
