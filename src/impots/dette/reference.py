"""Phase 9 M1 §3.2 — the reference path, and the spending rule finally applied.

Until this module, `SpendingScenario` was a guard with no arithmetic (D-213, correction 3):
`project` refused a path without one and then never read its rule, because every year's
primary balance arrived ready-made. Here the rule acts. The reference path is built from
the last published APU account and three named hypotheses — spending, growth, rates — and
the primary balance of each year is what they imply.

THE ARITHMETIC, ONE LINE PER RULE, in ratios to GDP:

* receipts stay a constant share of GDP — « prélèvements constants en % du PIB », a named
  convention, not a forecast of receipts;
* ``part_pib_constante`` — spending keeps its share: s_t = s_{t-1};
* ``gele_en_volume`` — spending grows with prices only: s_t = s_{t-1} (1 + π) / (1 + g),
  so its share falls by the real growth;
* ``personnalise`` — spending grows at its stated nominal rate:
  s_t = s_{t-1} (1 + c) / (1 + g), c the stated rate.

THE STARTING POINT IS PUBLISHED, NEVER EXTRAPOLATED: consolidated spending and receipts
from table 3.201 (closed on itself and checked against 7.301 in `comptes.apu_totals`), the
Maastricht ratio from the debt detail, and the implicit rate as the year's net interest
over the opening stock — the same definition the §6.1 backtest uses.
"""

from __future__ import annotations

from dataclasses import dataclass

from impots.dette import comptes
from impots.dette.path import HORIZON_CAP_YEARS, DebtError, SpendingScenario
from impots.dette.scenarios import GrowthScenario

RECEIPTS_CONVENTION = "Prélèvements constants en % du PIB"


@dataclass(frozen=True)
class Start:
    """The last published year, from which every path departs."""

    year: int
    gdp_eur: float
    receipts_ratio: float
    """Primary receipts (total receipts less interest received) over GDP."""
    spending_ratio: float
    """Primary spending (total spending less interest paid) over GDP."""
    debt_ratio: float
    """Maastricht debt over GDP at the end of `year`, as published."""
    implicit_rate: float
    """Net interest of `year` over the debt at the end of the year before."""

    @property
    def primary_balance(self) -> float:
        return self.receipts_ratio - self.spending_ratio


def start_from_accounts(year: int) -> Start:
    """The published starting point. Refuses rather than fills a missing file."""
    totals = comptes.apu_totals(year)
    product = comptes.gdp([year])[year]
    comptes.check_units([year - 1, year])
    stocks = comptes.debt([year - 1, year])
    opening_stock, _ = stocks[year - 1]
    _, ratio = stocks[year]
    return Start(
        year=year, gdp_eur=product,
        receipts_ratio=totals.primary_receipts_eur / product,
        spending_ratio=totals.primary_spending_eur / product,
        debt_ratio=ratio,
        implicit_rate=totals.interest_net_eur / opening_stock,
    )


@dataclass(frozen=True)
class ReferenceYear:
    year: int
    gdp_eur: float
    receipts_ratio: float
    spending_ratio: float

    @property
    def primary_balance(self) -> float:
        """SURPLUS POSITIVE, `path`'s convention."""
        return self.receipts_ratio - self.spending_ratio


def reference_years(start: Start, horizon: int, *,
                    spending: SpendingScenario | None,
                    growth: GrowthScenario | None) -> list[ReferenceYear]:
    """The reference primary balance, year by year, as the named rules imply it."""
    if spending is None:
        raise DebtError(
            "aucun scénario de dépense nommé : la trajectoire de référence en dépend "
            "autant que celle de la réforme, et aucun défaut n'est appliqué.")
    if growth is None:
        raise DebtError(
            "aucun scénario de croissance nommé : la croissance nominale fixe le "
            "dénominateur de chaque ratio, et un taux que personne n'a choisi se lirait "
            "comme une prévision.")
    if not 1 <= horizon <= HORIZON_CAP_YEARS:
        raise DebtError(
            f"horizon de {horizon} ans hors de [1 ; {HORIZON_CAP_YEARS}] : au-delà, "
            f"l'arithmétique est exacte et vide.")

    nominal = growth.nominal
    if spending.rule == "part_pib_constante":
        factor = 1.0
    elif spending.rule == "gele_en_volume":
        factor = (1.0 + growth.prices) / (1.0 + nominal)
    elif spending.rule == "personnalise":
        assert spending.growth is not None     # SpendingScenario refuses otherwise
        factor = (1.0 + spending.growth) / (1.0 + nominal)
    else:  # pragma: no cover - SpendingRule is a closed Literal
        raise DebtError(f"règle de dépense inconnue : {spending.rule}")

    out: list[ReferenceYear] = []
    product, share = start.gdp_eur, start.spending_ratio
    for offset in range(1, horizon + 1):
        product *= 1.0 + nominal
        share *= factor
        out.append(ReferenceYear(year=start.year + offset, gdp_eur=product,
                                 receipts_ratio=start.receipts_ratio,
                                 spending_ratio=share))
    return out
