"""Phase 9 M1 §3 — the chain reform → primary balance → debt.

The question this answers: does this reform lower the debt, and on what conditions? The
headline is the DIFFERENCE between two paths under the same named scenarios, Δb_t, because
a level of debt in 2035 depends on hypotheses nobody can source while the difference a
reform makes depends far less on them. Both levels are shown beside it.

HOW THE DIFFERENCE IS COMPUTED. The reform adds Δcost_t to the deficit of year t (engine
convention: a cost is positive). In euros, the extra debt follows
ΔD_t = ΔD_{t-1} (1 + m) + Δcost_t, where m is the rate on the MARGINAL euro of debt — the
held implicit rate, or the market rate when the scenario says new debt is issued there.
Divided by the same GDP as the reference (no GDP feedback before M3), this is the debt
identity itself applied to the difference, so `path.project` computes it: b0 = 0, r = m,
p = −Δcost_t / Y_t.

WHAT M1 DOES NOT YET CARRY, AND SAYS SO. The GDP → receipts feedback arrives in M3
(D-214: Mésange's balance row, under `gele_en_volume` only); until then the macro slice is
ABSENT, with its reason, and `dominant_source` refuses to name a winner. θ arrives in M2.
A year the engine did not price is refused unless the caller names the carry convention,
which then labels every year it filled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from impots.dette import path as path_module
from impots.dette.decomposition import Decomposition, Slice
from impots.dette.path import DebtError, SpendingScenario, YearInputs, check_scenario_name
from impots.dette.reference import RECEIPTS_CONVENTION, Start, reference_years
from impots.dette.scenarios import GrowthScenario, RateScenario

BANNER = (
    "Prédictif conditionnel : chaque chiffre dépend des scénarios nommés de dépense, de "
    "croissance et de taux, et des coefficients θ qui placeront chaque effet dans sa "
    "fourchette publiée. Ce n'est pas une prévision : changer un scénario change la "
    "réponse."
)

#: The one convention that may fill a year the engine did not price (M0, R3: ten years
#: priced one by one take about an hour). Named, because a filled year that looked priced
#: would be the quiet version of an invented number.
CARRY = "part_pib_constante"
CARRY_LABEL = ("Δ tenu en part de PIB constante au-delà de la dernière année chiffrée "
               "(convention, pas un chiffrage)")

ABSENT_FEEDBACK = (
    "Retour du PIB sur les recettes : non branché avant M3 (D-214). Absent, pas nul : le "
    "solde de la réforme ne compte ni l'activité qu'elle crée ni celle qu'elle détruit.")
ABSENT_BAND = "Bande comportementale non demandée : seul le chiffre mécanique est porté."
ABSENT_GRID = ("Une seule combinaison de scénarios : chaque autre combinaison est un autre "
               "calcul, sous ses propres noms.")
RATE_PROXY = ("Taux implicite de la dette négociable de l'État (encours AFT) appliqué à "
              "toute la dette des APU")


@dataclass(frozen=True)
class ReformCosts:
    """What the engine priced, year by year. Engine convention: a COST is positive."""

    by_year: dict[int, float]
    carry: str | None = None
    behavioural: dict[int, tuple[float, float]] | None = None
    """Receipts band (p10, p90) per priced year, RECEIPTS POSITIVE as `band.compute`
    returns it — the opposite sign of `by_year`, stated because a sign error here would
    put the band on the wrong side of the mechanical path and still look like a band."""

    def __post_init__(self) -> None:
        if not self.by_year:
            raise DebtError("aucune année chiffrée : une trajectoire de réforme sans "
                            "chiffrage n'est que la référence, et se dirait autre chose")
        if self.carry not in (None, CARRY):
            raise DebtError(f"convention de report « {self.carry} » inconnue ; seule "
                            f"« {CARRY} » existe")
        if self.behavioural is not None:
            if set(self.behavioural) != set(self.by_year):
                raise DebtError(
                    "la bande comportementale ne couvre pas les mêmes années que le "
                    "chiffrage : une bande sur une partie des années se tracerait comme "
                    "une bande sur toutes.")
            for year, (low, high) in self.behavioural.items():
                if high < low:
                    raise DebtError(f"{year} : bande retournée ({low:,.0f} > {high:,.0f})")


@dataclass(frozen=True)
class Trajectoire:
    """Two debt paths under the same named scenarios, and the difference a reform makes."""

    years: tuple[int, ...]
    reference: tuple[float, ...]
    reform: tuple[float, ...]
    delta: tuple[float, ...]
    reference_primary: tuple[float, ...]
    delta_primary: tuple[float, ...]
    priced_years: tuple[int, ...]
    carried_years: tuple[int, ...]
    decomposition: Decomposition
    spending_name: str
    growth_name: str
    rate_name: str
    conventions: tuple[str, ...]
    absent: dict[str, str] = field(default_factory=dict)
    banner: str = BANNER

    def __post_init__(self) -> None:
        if self.banner != BANNER:
            raise DebtError(
                "la bannière du prédictif conditionnel est un champ vérifié, pas une "
                "décoration : une trajectoire sans elle se lit comme une prévision.")
        for name, what in ((self.spending_name, "de dépense"),
                           (self.growth_name, "de croissance"),
                           (self.rate_name, "de taux")):
            check_scenario_name(name, what)
        n = len(self.years)
        if any(len(s) != n for s in (self.reference, self.reform, self.delta,
                                     self.reference_primary, self.delta_primary)):
            raise DebtError("séries de longueurs différentes : une trajectoire décalée "
                            "d'un an se tracerait sans erreur visible")

    def lines(self) -> list[str]:
        out = [f"Dépense : {self.spending_name} · Croissance : {self.growth_name} · "
               f"Taux : {self.rate_name}"]
        for i, year in enumerate(self.years):
            tag = " (report)" if year in self.carried_years else ""
            out.append(f"  {year} : référence {self.reference[i]:.2%}, réforme "
                       f"{self.reform[i]:.2%}, écart {self.delta[i] * 100:+.3f} pt{tag}")
        out.extend(f"  convention : {c}" for c in self.conventions)
        out.extend(f"  absent — {k} : {v}" for k, v in self.absent.items())
        out.append(self.banner)
        return out


def _costs_by_year(costs: ReformCosts, years: list[int],
                   gdp: dict[int, float]) -> tuple[dict[int, float], tuple[int, ...]]:
    """Priced years as priced; later years by the named carry convention, or refused."""
    priced = sorted(costs.by_year)
    if priced[0] != years[0] or priced != list(range(priced[0], priced[0] + len(priced))):
        raise DebtError(
            f"années chiffrées {priced} : elles doivent former une suite qui commence à "
            f"la première année projetée, {years[0]}. Un trou serait comblé en silence.")
    if priced[-1] > years[-1]:
        raise DebtError(f"année chiffrée {priced[-1]} au-delà de l'horizon {years[-1]}")
    missing = [y for y in years if y > priced[-1]]
    if missing and costs.carry is None:
        raise DebtError(
            f"années {missing} non chiffrées et aucune convention de report nommée. "
            f"Les remplir sans le dire ferait passer une convention pour un chiffrage ; "
            f"nommer « {CARRY} » les remplit et les étiquette.")
    out = {y: costs.by_year[y] for y in priced}
    last = priced[-1]
    for year in missing:
        out[year] = costs.by_year[last] / gdp[last] * gdp[year]
    return out, tuple(missing)


def _rate_path(start: Start, rate: RateScenario, reference: list[Any],
               spending: SpendingScenario, growth: GrowthScenario,
               securities: list[Any] | None) -> tuple[list[float], float, tuple[str, ...]]:
    """(r_t for the reference, the marginal rate m on extra debt, conventions)."""
    horizon = len(reference)
    if rate.kind == "implicite_tenu":
        return [start.implicit_rate] * horizon, start.implicit_rate, ()

    from impots.dette import maturite

    if not securities:
        raise DebtError(
            "scénario « marché » sans encours AFT : le taux implicite se déduit des lignes "
            "qui arrivent à échéance, et sans elles il serait inventé. Fichiers "
            "aft_encours_detaille_*.html, au manifeste.")
    if maturite.AS_OF.year != start.year + 1:
        raise DebtError(
            f"l'encours AFT est daté de {maturite.AS_OF:%Y-%m-%d} et la trajectoire part "
            f"de {start.year} : les échéances de l'une ne sont pas celles de l'autre.")
    assert rate.market_rate is not None      # RateScenario refuses otherwise
    # First pass at the held rate, for the deficits the State must issue; the rate path
    # those deficits imply then replaces it. One pass: the deficits move with r by
    # second-order amounts only, and a loop to a fixed point would hide that choice.
    first = path_module.project(start.debt_ratio, [
        YearInputs(year=y.year, r=start.implicit_rate, g=growth.nominal,
                   primary_balance=y.primary_balance) for y in reference],
        spending=spending)
    deficits = [(point.interest_ratio - y.primary_balance) * y.gdp_eur
                for point, y in zip(first, reference, strict=True)]
    points = maturite.implicit_rate_path(securities, market_rate=rate.market_rate,
                                         scenario=rate.name, deficit_eur=deficits,
                                         years=horizon)
    return [p.implicit_rate for p in points], rate.market_rate, (RATE_PROXY,)


def run(start: Start, *, horizon: int, costs: ReformCosts,
        spending: SpendingScenario | None, growth: GrowthScenario | None,
        rate: RateScenario | None, securities: list[Any] | None = None) -> Trajectoire:
    """The reference path, the reform path, and the difference, under named scenarios."""
    if rate is None:
        raise DebtError(
            "aucun scénario de taux nommé : la charge d'intérêts fait la boule de neige, "
            "et un taux que personne n'a choisi se lirait comme une prévision.")
    reference = reference_years(start, horizon, spending=spending, growth=growth)
    assert spending is not None and growth is not None   # reference_years refuses
    years = [y.year for y in reference]
    gdp = {start.year: start.gdp_eur, **{y.year: y.gdp_eur for y in reference}}

    rates, marginal, rate_conventions = _rate_path(start, rate, reference, spending,
                                                   growth, securities)
    reference_points = path_module.project(start.debt_ratio, [
        YearInputs(year=y.year, r=r, g=growth.nominal, primary_balance=y.primary_balance)
        for y, r in zip(reference, rates, strict=True)], spending=spending)

    cost, carried = _costs_by_year(costs, years, gdp)

    def delta_path(balance: dict[int, float]) -> list[float]:
        points = path_module.project(0.0, [
            YearInputs(year=y, r=marginal, g=growth.nominal, primary_balance=balance[y])
            for y in years], spending=spending)
        return [p.ratio for p in points]

    delta_primary = {y: -cost[y] / gdp[y] for y in years}
    delta = delta_path(delta_primary)
    ref = [p.ratio for p in reference_points]
    reform = [b + d for b, d in zip(ref, delta, strict=True)]

    if costs.behavioural is not None:
        band, _ = _costs_by_year(
            ReformCosts(by_year={y: lo for y, (lo, _) in costs.behavioural.items()},
                        carry=costs.carry), years, gdp)
        band_high, _ = _costs_by_year(
            ReformCosts(by_year={y: hi for y, (_, hi) in costs.behavioural.items()},
                        carry=costs.carry), years, gdp)
        # Receipts positive: more receipts improve the balance, so p = +receipts / Y.
        low_path = delta_path({y: band[y] / gdp[y] for y in years})
        high_path = delta_path({y: band_high[y] / gdp[y] for y in years})
        behaviour = Slice(
            source="bande", label="Bande comportementale (p10-p90)",
            low=tuple(b + min(a, c) for b, a, c in zip(ref, low_path, high_path,
                                                         strict=True)),
            high=tuple(b + max(a, c) for b, a, c in zip(ref, low_path, high_path,
                                                          strict=True)))
    else:
        behaviour = Slice(source="bande", label="Bande comportementale", computed=False,
                          reason=ABSENT_BAND)

    decomposition = Decomposition(
        years=tuple(years), central=tuple(reform), spending_name=spending.name,
        slices=(
            behaviour,
            Slice(source="eventail", label="Rétroaction macro", computed=False,
                  reason=ABSENT_FEEDBACK),
            Slice(source="scenario", label="Grille de scénarios", computed=False,
                  reason=ABSENT_GRID),
        ))
    conventions = [RECEIPTS_CONVENTION, *rate_conventions]
    if carried:
        conventions.append(CARRY_LABEL)
    return Trajectoire(
        years=tuple(years), reference=tuple(ref), reform=tuple(reform),
        delta=tuple(delta),
        reference_primary=tuple(y.primary_balance for y in reference),
        delta_primary=tuple(delta_primary[y] for y in years),
        priced_years=tuple(sorted(costs.by_year)), carried_years=carried,
        decomposition=decomposition, spending_name=spending.name,
        growth_name=growth.name, rate_name=rate.name, conventions=tuple(conventions),
        absent={"rétroaction": ABSENT_FEEDBACK,
                **({} if costs.behavioural is not None else {"bande": ABSENT_BAND})},
    )
