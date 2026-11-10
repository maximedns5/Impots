"""F3 M2 — ageing the population mechanically, and losing its calibration by doing so.

**Uprate, never re-synthesise.** Redrawing a population each year would move household
identities from one year to the next, and a per-household trajectory would then mean
nothing: the «same» household in 2028 would be a different draw. So the frame's rows, its
household structure and its weights are left exactly as they are, and only the money
columns move.

WHAT THIS COSTS, AND IT IS THE POINT OF THE MILESTONE RATHER THAN A FOOTNOTE.

**An uprated population is no longer calibrated.** Every total on the spent side of the
calibration ledger — the wage bill, the pension mass, the benefit counts — was fitted to
the base year. Multiply the incomes by a wage index and the population no longer reproduces
any published total, because there are no published totals for a future year to reproduce.
A reconciliation of an aged year therefore compares a simulated 2028 figure with a
published 2024 one, and those are figures about different things.

That is why `reporting.Line` now refuses to return a tolerance verdict when
`population_year` and `comparator_year` differ. The refusal is M2's completion condition,
and it is a refusal rather than a widened tolerance for the reason this project keeps
finding: a loose verdict reads as validation, and there is nothing here being validated.

**THREE LIMITS, STATED BECAUSE NONE OF THEM IS VISIBLE IN THE OUTPUT.**

1. **Household structure does not move.** No births, no deaths, no separations, nobody
   ageing out of a family. The population's demography is frozen at the base year, which
   biases every trajectory towards demographic immobility — and towards understating any
   measure whose cost grows with the number of pensioners.
2. **Weights are not recalibrated.** There are no published margins for a future year to
   rake onto, so the weights stay as they were. The population therefore represents the
   base year's France, uprated — not the France of the target year.
3. **Ages do not advance.** Deliberately, and it is the same choice as (1): advancing ages
   without advancing anything else would produce a population that is older but has the
   same number of children, which is worse than one that is uniformly frozen. A trajectory
   priced here is «this law, on today's France, with tomorrow's money».

**THE INDICES ARE DECLARED, NEVER FORECAST.** Phase 4's refusals bind here as they do in
`trajectoires`: this project does not predict wages or prices. `Uprating` carries rates the
caller states and a source they name, and refuses to invent either.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: The frame columns this module multiplies, and what each is uprated ON.
#:
#: Named as data rather than written into the function so a money column added to the
#: population cannot be silently left behind — `test_every_money_column_is_uprated_or_named`
#: reads this against the frame and fails on anything unaccounted for. A column left out
#: would silently shrink in real terms every year, which is a trajectory that slowly
#: invents an impoverishment.
UPRATED = {
    "salaire_brut_annuel": "wage",
    "pension_annuelle": "price",
    "chomage_annuel": "wage",
    "loyer_mensuel": "price",
    # The self-employed's income, by the wage per head: the Insee's mean non-salarié
    # income is published by year, but not as an index the grid's years declare (D-360).
    "revenu_non_salarie_annuel": "wage",
}

#: Money columns deliberately NOT uprated, with the reason. Empty today, and kept as the
#: place a future exception must be justified rather than just omitted.
NOT_UPRATED: dict[str, str] = {}


class UpratingError(RuntimeError):
    """A population was asked to be aged in a way that would mislead."""


@dataclass(frozen=True)
class Uprating:
    """Declared annual indices. Never forecast, never defaulted.

    `wage` and `price` are annual growth rates — 0.025 for 2,5 % a year. Two indices and
    not one because wages and prices do not move together, and using a single index would
    quietly assume they do: pensions and rents follow prices, salaries do not.
    """

    wage: float
    price: float
    source: str
    base_year: int
    wage_by_year: tuple[tuple[int, float], ...] = ()
    """Année par année, quand le texte noté donne ses taux ainsi (D-317) : `factor` les
    enchaîne et refuse une année qui manque. Vides, les taux constants valent."""
    price_by_year: tuple[tuple[int, float], ...] = ()

    @classmethod
    def par_annee(cls, wage: dict[int, float], price: dict[int, float], source: str,
                  base_year: int) -> Uprating:
        """Des indices année par année. `wage` et `price` gardent leur moyenne
        géométrique, pour qui lit un taux annuel ; `factor` lit les années."""
        def mean(rates: dict[int, float]) -> float:
            product = 1.0
            for rate in rates.values():
                product *= 1.0 + rate
            return product ** (1.0 / len(rates)) - 1.0 if rates else 0.0

        if not wage or not price:
            raise UpratingError("des indices par année sans année : rien à enchaîner")
        return cls(wage=mean(wage), price=mean(price), source=source, base_year=base_year,
                   wage_by_year=tuple(sorted(wage.items())),
                   price_by_year=tuple(sorted(price.items())))

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise UpratingError(
                "un vieillissement sans source est une prévision anonyme. Dire d'où "
                "viennent les indices — une hypothèse de LFI, un indice constaté, ou "
                "« 2 % ronds, choisis pour être lisibles » — est ce qui permet d'en "
                "discuter. Ce projet ne prévoit ni les salaires ni les prix : il chiffre "
                "« si les salaires montent de X et les prix de Y ».")
        if bool(self.wage_by_year) != bool(self.price_by_year):
            raise UpratingError(
                "des salaires par année et des prix constants, ou l'inverse : les deux "
                "indices se donnent de la même façon")
        rates = [("wage", self.wage), ("price", self.price),
                 *((f"wage {y}", r) for y, r in self.wage_by_year),
                 *((f"price {y}", r) for y, r in self.price_by_year)]
        for name, rate in rates:
            if not -0.5 < rate < 0.5:
                raise UpratingError(
                    f"indice {name} = {rate} hors de ]-50 %, +50 %[ : ce n'est "
                    f"probablement pas un taux annuel")

    def factor(self, kind: str, year: int) -> float:
        """Cumulative uprating from `base_year` to `year`, on the named index."""
        if kind not in ("wage", "price"):
            raise UpratingError(f"indice inconnu : {kind}")
        by_year = dict(self.wage_by_year if kind == "wage" else self.price_by_year)
        if year < self.base_year:
            # Backwards only on observed indices, year by year (D-359): the rate of year
            # y is the growth from y − 1 to y, so going back from the base to `year`
            # divides by the years after `year`, the base included.
            if not by_year:
                raise UpratingError(
                    f"ramener la population de {self.base_year} à {year} sur un taux "
                    f"constant : reculer demande des indices constatés année par année "
                    f"(D-359).")
            back = range(year + 1, self.base_year + 1)
            missing = [y for y in back if y not in by_year]
            if missing:
                raise UpratingError(
                    f"ramener la population de {self.base_year} à {year} : l'indice "
                    f"{kind} n'a pas de taux constaté pour {missing}, et l'outil n'en "
                    f"invente pas")
            factor = 1.0
            for y in back:
                factor /= 1.0 + by_year[y]
            return factor
        if by_year:
            missing = [y for y in range(self.base_year + 1, year + 1) if y not in by_year]
            if missing:
                raise UpratingError(
                    f"vieillir vers {year} depuis {self.base_year} : l'indice {kind} n'a "
                    f"pas de taux pour {missing}, et l'outil n'en invente pas")
            factor = 1.0
            for y in range(self.base_year + 1, year + 1):
                factor *= 1.0 + by_year[y]
            return factor
        rate = self.wage if kind == "wage" else self.price
        return (1.0 + rate) ** (year - self.base_year)

    def key(self) -> str:
        """What an aged population's numbers depend on, for a cache key: the two indices
        and the base year, the target year being keyed already. The source is a label and
        stays out — two names for the same rates are the same population (D-226)."""
        key = f"w{self.wage:+.6f}_p{self.price:+.6f}_b{self.base_year}"
        if self.wage_by_year:
            years = "".join(f"_{y}w{w:+.6f}" for y, w in self.wage_by_year)
            years += "".join(f"_{y}p{p:+.6f}" for y, p in self.price_by_year)
            key += years
        return key


def uprate(frame: Any, year: int, uprating: Uprating) -> Any:
    """Return the frame with its money columns moved to `year`. Nothing else changes.

    Rows, household identifiers, weights, ages and structure are untouched — see the
    module docstring for why, and for what that costs.
    """
    import polars as pl

    if year == uprating.base_year:
        return frame
    missing = [c for c in UPRATED if c not in frame.columns]
    if missing:
        raise UpratingError(
            f"colonnes absentes de la population : {missing}. Vieillir une population "
            f"dont il manque une colonne monétaire la déformerait en silence.")
    return frame.with_columns([
        (pl.col(column) * uprating.factor(kind, year)).alias(column)
        for column, kind in UPRATED.items()
    ])


def caveat(year: int, uprating: Uprating) -> str:
    """The sentence that must travel with any figure computed on an aged population."""
    from impots.reporting import pct_fr

    back = year < uprating.base_year
    if uprating.wage_by_year:
        years = (range(year + 1, uprating.base_year + 1) if back
                 else range(uprating.base_year + 1, year + 1))
        wages, prices = dict(uprating.wage_by_year), dict(uprating.price_by_year)
        rates = (f"salaires {', '.join(f'{pct_fr(wages[y], 1)} en {y}' for y in years)}, "
                 f"prix {', '.join(f'{pct_fr(prices[y], 1)} en {y}' for y in years)}")
    else:
        rates = (f"salaires {pct_fr(uprating.wage, 1)} par an, prix "
                 f"{pct_fr(uprating.price, 1)} par an")
    if back:
        return (
            f"Population ramenée mécaniquement de {uprating.base_year} à {year}, chaque "
            f"montant divisé par les évolutions constatées — {rates} ({uprating.source}). "
            "La structure des ménages, les âges et les poids sont ceux de "
            f"{uprating.base_year} : c'est la France de {uprating.base_year} avec l'argent "
            f"de {year}. **Cette population n'est pas calibrée sur {year}** : les totaux "
            "dépensés au registre le sont sur l'année de base (D-359).")
    return (
        f"Population vieillie mécaniquement de {uprating.base_year} à {year} — {rates}, "
        f"hypothèses "
        f"DÉCLARÉES et non prévues ({uprating.source}). "
        "La structure des ménages, les âges et les poids n'ont PAS bougé : c'est la "
        "France de l'année de base avec l'argent de l'année d'arrivée, et cela biaise "
        "vers l'immobilité démographique. "
        "**Cette population n'est plus calibrée** : les totaux dépensés au registre le "
        "sont sur l'année de base, et il n'existe pas de total publié pour une année "
        "future. Toute ligne de réconciliation sur cette année refuse un verdict de "
        "tolérance plutôt que d'en donner un qui se lirait comme une validation."
    )
