"""Phase 9 M1 §3 — the chain reform → primary balance → debt.

The question this answers: does this reform lower the debt, and on what conditions? The
headline is the DIFFERENCE between two paths under the same named scenarios, Δb_t, because
a level of debt in 2035 depends on hypotheses nobody can source while the difference a
reform makes depends far less on them. Both levels are shown beside it.

HOW THE DIFFERENCE IS COMPUTED. The reform adds Δcost_t to the deficit of year t (engine
convention: a cost is positive). In euros, the extra debt follows
ΔD_t = ΔD_{t-1} (1 + m) + Δcost_t, where m is the rate on the MARGINAL euro of debt — the
held implicit rate, or the market rate when the scenario says new debt is issued there.
Divided by the reference's GDP, this is the debt identity itself applied to the
difference, so `path.project` computes it: b0 = 0, r = m, p = −Δcost_t / Y_t. The loop
below then divides by the reform's own GDP.

THE GDP → RECEIPTS LOOP (M3, D-218). When the caller hands the reform's impulse by
instrument, `retroaction` reads Mésange's primary-balance row: the feedback improves the
reform's primary balance, and the GDP the reform adds divides its debt — the reform
path's ratio is (reference ratio + extra debt over reference GDP) / (1 + y_t), the debt
identity of §4.4 with the reform's own GDP. Only under `gele_en_volume`, Mésange's own
spending; under any other rule the loop is ABSENT, with its reason. The `eventail` slice
then sweeps the multiplier's θ from 0 to 1, the rest at its value. A year the engine did
not price is refused unless the caller names the carry convention, which then labels
every year it filled — the impulse included.

θ (M2, D-217). Every path is computed under a `Theta` the caller chose — there is no
default, and `run` refuses without one (guard 1). With behaviour, the reform's central
path is the receipts AT θ, and the `bande` slice is the θ box: the receipts at the corners
where every claimed row is at 0 or 1 (`comportement.evaluate`). The mechanical difference
stands beside it, θ having no effect on it. Without behaviour, the θ are still listed —
a result names every hypothesis it was asked under — with the statement that nothing
reads them. `Trajectoire` refuses to exist without a θ for each open row and a reason for
each closed channel (guard 2), the way it refuses to exist without its banner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from impots.behavioural.store import Store
from impots.behavioural.store import load as load_store
from impots.dette import path as path_module
from impots.dette.decomposition import Decomposition, Slice
from impots.dette.path import DebtError, SpendingScenario, YearInputs, check_scenario_name
from impots.dette.reference import RECEIPTS_CONVENTION, Start, reference_years
from impots.dette.scenarios import GrowthScenario, RateScenario
from impots.predictif import retroaction
from impots.predictif.comportement import AtTheta
from impots.predictif.theta import MACRO_ROW, Theta, ThetaError

BANNER = (
    "Prédictif conditionnel : chaque chiffre dépend des scénarios nommés de dépense, de "
    "croissance et de taux, et des coefficients θ qui placeront chaque effet dans sa "
    "fourchette publiée. Ce n'est pas une prévision : changer un scénario change la "
    "réponse."
)

#: The last APU account the manifested tables publish (millésime 2025). Every path starts
#: there; its first projected year is the one the population layer prices first.
START_YEAR = 2025

#: The one convention that may fill a year the engine did not price (M0, R3: ten years
#: priced one by one take about an hour). Named, because a filled year that looked priced
#: would be the quiet version of an invented number.
CARRY = "part_pib_constante"
CARRY_LABEL = ("Δ tenu en part de PIB constante au-delà de la dernière année chiffrée "
               "(convention, pas un chiffrage)")

ABSENT_FEEDBACK = (
    "Retour du PIB sur les recettes non demandé. Absent, pas nul : le solde de la "
    "réforme ne compte ni l'activité qu'elle crée ni celle qu'elle détruit.")
EVENTAIL_LABEL = ("Éventail macro : θ du multiplicateur de 0 à 1, comportement à sa "
                  "valeur, bornes lues aux deux bouts")
ABSENT_BAND = "Comportement non demandé : seul le chiffre mécanique est porté."
THETA_UNREAD = ("Vue mécanique : les θ sont listés parce que la requête les nomme, mais "
                "aucun canal de comportement ne les lit.")
THETA_MACRO_ONLY = ("Comportement non demandé : les θ des lignes de comportement sont "
                    "listés sans être lus ; seul celui du multiplicateur l'est.")
BOX_LABEL = ("Boîte θ du comportement : chaque effet revendiqué n'importe où dans sa "
             "fourchette publiée, bornes lues aux coins")
BOX_CONVENTION = ("Boîte θ : étendue des résultats quand chaque θ revendiqué parcourt "
                  "[0 ; 1], lue aux coins après contrôle de monotonie. Ni une somme de "
                  "tranches, ni un intervalle de probabilité.")

#: The two channels the loop opens. Closed, with the reason, whenever it is not applied.
MACRO_CHANNELS = ("rétroaction PIB → recettes", "multiplicateur macro")

#: The channels a result carries NO θ for, each with the reason it is closed (§2.5).
#: Guard 2: a trajectory whose closed channel lost its reason refuses to exist — a closed
#: channel shown without one reads as a channel that does not matter.
CLOSED: dict[str, str] = {
    "offre de travail": (
        "aucune ligne vérifiée au magasin (D-031) ; les élasticités de Bargain, Orsini et "
        "Peichl restent à manifester (§6.1)."),
    "IS et investissement des entreprises": (
        "aucune variante d'IS dans Mésange 2017, et aucune réestimation publiée depuis ; "
        "le seul chiffre localisé, un multiplicateur moyen de 0,7 pour la hausse d'IS de "
        "2013 dans un billet de l'OFCE, n'est plus en ligne et n'aurait ni profil par "
        "horizon ni ligne de solde (§5, §6.2, D-219)."),
    "transferts": (
        "Mésange n'a pas de variante de transfert. Les deux méta-analyses IMK donnent "
        "0,39 (écart-type 0,47) et 0,54 (écart-type 1,16) : elles divergent sur le "
        "centre, d'un facteur 2,5 sur la largeur, mêlent les horizons d'un à douze ans "
        "et n'ont ni ligne de solde ni centre français (§5, D-214, D-219)."),
    "créations d'entreprises": (
        "aucune évaluation publiée de leur réponse aux impôts au manifeste (§6.3)."),
    "R&D et CIR": "aucun fichier GECIR ni MESR au manifeste (D-154, §6.4).",
    "dividendes": "la population ne porte aucun revenu du capital (§6.5).",
}
ABSENT_GRID = ("Une seule combinaison de scénarios : chaque autre combinaison est un autre "
               "calcul, sous ses propres noms.")
RATE_PROXY = ("Taux implicite de la dette négociable de l'État (encours AFT) appliqué à "
              "toute la dette des APU")


@dataclass(frozen=True)
class ReformCosts:
    """What the engine priced, year by year. Engine convention: a COST is positive."""

    by_year: dict[int, float]
    carry: str | None = None
    behavioural: dict[int, AtTheta] | None = None
    """The receipts at θ and the θ box per priced year (`comportement.evaluate`), RECEIPTS
    POSITIVE and mechanical included — the opposite sign of `by_year`, stated because a
    sign error here would put the box on the wrong side of the mechanical path and still
    look like a box."""
    impulses: dict[int, dict[str, float]] | None = None
    """The reform's impulse by Mésange variant per priced year, EXPANSIONARY-POSITIVE
    euros (`shocks.Impulse.by_instrument`). Given, it asks for the GDP → receipts loop."""
    uncovered: dict[str, str] = field(default_factory=dict)
    """Deltas with no multiplier, and why (`shocks.Impulse.reasons()`)."""

    def __post_init__(self) -> None:
        if not self.by_year:
            raise DebtError("aucune année chiffrée : une trajectoire de réforme sans "
                            "chiffrage n'est que la référence, et se dirait autre chose")
        if self.carry not in (None, CARRY):
            raise DebtError(f"convention de report « {self.carry} » inconnue ; seule "
                            f"« {CARRY} » existe")
        if self.impulses is not None and set(self.impulses) != set(self.by_year):
            raise DebtError(
                "l'impulsion macro ne couvre pas les mêmes années que le chiffrage : une "
                "année chiffrée sans impulsion serait une année sans choc, en silence.")
        if self.behavioural is not None:
            if set(self.behavioural) != set(self.by_year):
                raise DebtError(
                    "la bande comportementale ne couvre pas les mêmes années que le "
                    "chiffrage : une bande sur une partie des années se tracerait comme "
                    "une bande sur toutes.")
            for year, at in self.behavioural.items():
                low, high = at.box
                if high < low:
                    raise DebtError(f"{year} : boîte retournée ({low:,.0f} > {high:,.0f})")
                if not low <= at.receipts <= high:
                    raise DebtError(
                        f"{year} : recettes à θ ({at.receipts:,.0f}) hors de leur boîte "
                        f"[{low:,.0f} ; {high:,.0f}]")


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
    delta_mechanical: tuple[float, ...]
    """The difference with every behavioural channel off — θ has no effect on it."""
    theta: dict[str, float]
    """Every open row with the θ it ran at, even when they were set together (§2.3)."""
    open_rows: tuple[str, ...]
    """The rows the store loaded with a range: what `theta` must cover, exactly."""
    theta_applied: bool
    """False in the mechanical view, where the θ are listed but nothing reads them."""
    gdp_gap: tuple[float, ...] | None = None
    """y_t, the reform's GDP over the reference's minus one, when the loop is applied."""
    feedback_primary: tuple[float, ...] | None = None
    """φ_t, the loop's share of the reform's primary balance, when applied."""
    persistence: str | None = None
    closed: dict[str, str] = field(default_factory=lambda: dict(CLOSED))
    absent: dict[str, str] = field(default_factory=dict)
    banner: str = BANNER

    def __post_init__(self) -> None:
        if self.banner != BANNER:
            raise DebtError(
                "la bannière du prédictif conditionnel est un champ vérifié, pas une "
                "décoration : une trajectoire sans elle se lit comme une prévision.")
        # GUARD 2 (§2.4): no result without its θ, no closed channel without its reason.
        missing = sorted(set(self.open_rows) - set(self.theta))
        stray = sorted(set(self.theta) - set(self.open_rows))
        if missing or stray:
            raise ThetaError(
                f"θ manquant pour {missing}, ou donné à une ligne non ouverte {stray} : "
                f"un résultat se lit avec chacun de ses θ, ou ne se lit pas.")
        outside = sorted(k for k, v in self.theta.items() if not 0.0 <= v <= 1.0)
        if outside:
            raise ThetaError(f"θ hors de [0 ; 1] pour {outside}")
        applied = MACRO_ROW in self.open_rows
        expected = [*CLOSED, *(() if applied else MACRO_CHANNELS)]
        unreasoned = sorted(k for k in expected if not str(self.closed.get(k, "")).strip())
        if applied and any(k in self.closed for k in MACRO_CHANNELS):
            raise ThetaError("la rétroaction est appliquée et pourtant listée fermée : "
                             "le résultat se contredirait")
        if applied and self.gdp_gap is None:
            raise ThetaError("θ du multiplicateur listé sans effet sur le PIB")
        if unreasoned:
            raise ThetaError(
                f"canaux fermés sans leur raison : {unreasoned}. Un canal fermé affiché "
                f"sans raison se lit comme un canal qui ne compte pas.")
        for name, what in ((self.spending_name, "de dépense"),
                           (self.growth_name, "de croissance"),
                           (self.rate_name, "de taux")):
            check_scenario_name(name, what)
        n = len(self.years)
        if any(len(s) != n for s in (self.reference, self.reform, self.delta,
                                     self.reference_primary, self.delta_primary,
                                     self.delta_mechanical,
                                     *(s for s in (self.gdp_gap, self.feedback_primary)
                                       if s is not None))):
            raise DebtError("séries de longueurs différentes : une trajectoire décalée "
                            "d'un an se tracerait sans erreur visible")

    def lines(self) -> list[str]:
        out = [f"Dépense : {self.spending_name} · Croissance : {self.growth_name} · "
               f"Taux : {self.rate_name}"]
        for i, year in enumerate(self.years):
            tag = " (report)" if year in self.carried_years else ""
            out.append(f"  {year} : référence {self.reference[i]:.2%}, réforme "
                       f"{self.reform[i]:.2%}, écart {self.delta[i] * 100:+.3f} pt{tag}")
        out.append("  θ : " + ", ".join(f"{k} = {v:g}" for k, v in self.theta.items())
                   + ("" if self.theta_applied else " (non lus : vue mécanique)"))
        out.extend(f"  convention : {c}" for c in self.conventions)
        out.extend(f"  absent — {k} : {v}" for k, v in self.absent.items())
        out.extend(f"  fermé — {k} : {v}" for k, v in self.closed.items())
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
        rate: RateScenario | None, theta: Theta | None,
        securities: list[Any] | None = None, store: Store | None = None,
        persistence: str | None = None, macro_store: Any = None) -> Trajectoire:
    """The reference path, the reform path, and the difference, under named scenarios
    and the θ the caller chose. `store` is the behavioural store the θ are read against
    (the shipped one by default) — the same one `comportement.evaluate` ran on.
    `persistence` and `macro_store` serve the GDP → receipts loop, asked for by giving
    `costs.impulses`; the macro store defaults to the shipped one."""
    if rate is None:
        raise DebtError(
            "aucun scénario de taux nommé : la charge d'intérêts fait la boule de neige, "
            "et un taux que personne n'a choisi se lirait comme une prévision.")
    if theta is None:
        raise ThetaError(
            "aucun θ nommé : chaque effet de comportement se place dans sa fourchette par "
            "le θ de l'utilisateur, et un θ que personne n'a choisi serait celui de "
            "l'outil. Aucun défaut, pas même 1/2.")
    store = store if store is not None else load_store()
    theta.check_known(store)
    table = theta.table(store)
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

    ref = [p.ratio for p in reference_points]
    mechanical = delta_path({y: -cost[y] / gdp[y] for y in years})

    def fill(series: dict[int, float]) -> dict[int, float]:
        """Priced years as given, later ones held as a share of GDP — the cost's own
        convention, so the impulse and the cost it comes from are carried alike."""
        filled, _ = _costs_by_year(ReformCosts(by_year=series, carry=costs.carry),
                                   years, gdp)
        return filled

    def receipts(pick) -> dict[int, float]:
        """One receipts series per year — priced years as evaluated, later ones by the
        same carry convention as the cost — as a primary balance, p = +receipts / Y."""
        assert costs.behavioural is not None
        filled, _ = _costs_by_year(
            ReformCosts(by_year={y: pick(at) for y, at in costs.behavioural.items()},
                        carry=costs.carry), years, gdp)
        return {y: filled[y] / gdp[y] for y in years}

    # --- the GDP → receipts loop, when asked for and readable --------------------- #
    feedback_reason = ABSENT_FEEDBACK
    feedback: dict[float, retroaction.Feedback] = {}
    if costs.impulses is not None:
        if spending.rule != retroaction.SPENDING_RULE:
            feedback_reason = retroaction.spending_reason(spending.name)
        else:
            instruments = sorted({i for year in costs.impulses.values() for i in year})
            impulses = {y: {} for y in years}
            for instrument in instruments:
                series = fill({y: costs.impulses[y].get(instrument, 0.0)
                                  for y in costs.impulses})
                for y in years:
                    impulses[y][instrument] = series[y]
            if macro_store is None:
                from impots.macro import store as macro_store_module
                macro_store = macro_store_module.load()
            at_theta = theta.for_row(MACRO_ROW)
            try:
                for value in sorted({at_theta, 0.0, 1.0}):
                    feedback[value] = retroaction.compute(
                        impulses, gdp, years, store=macro_store, theta=value,
                        persistence=persistence, spending_rule=spending.rule,
                        spending_name=spending.name, uncovered=costs.uncovered)
            except retroaction.NothingToRead as error:
                feedback, feedback_reason = {}, str(error)
    if persistence is not None and (costs.impulses is None
                                    or spending.rule != retroaction.SPENDING_RULE):
        raise DebtError(
            f"persistance « {persistence} » sans rétroaction appliquée (non demandée, ou "
            f"absente sous « {spending.name} ») : elle serait ignorée en silence.")
    applied = feedback.get(theta.for_row(MACRO_ROW)) if feedback else None
    zero = dict.fromkeys(years, 0.0)

    def reform_path(primary: dict[int, float],
                    loop: retroaction.Feedback | None) -> list[float]:
        """The reform's debt ratio: extra debt over reference GDP, the whole divided by
        the reform's GDP gap (§4.4). Without the loop, the gap is zero."""
        phi = dict(zip(years, loop.balance, strict=True)) if loop else zero
        gap = loop.gdp_gap if loop else (0.0,) * len(years)
        raw = delta_path({y: primary[y] + phi[y] for y in years})
        return [(b + d) / (1.0 + g) for b, d, g in zip(ref, raw, gap, strict=True)]

    def envelope(label: str, source: str, one: list[float], two: list[float]) -> Slice:
        return Slice(source=source, label=label,
                     low=tuple(min(a, b) for a, b in zip(one, two, strict=True)),
                     high=tuple(max(a, b) for a, b in zip(one, two, strict=True)))

    if costs.behavioural is not None:
        base_primary = receipts(lambda at: at.receipts)
        behaviour = envelope(BOX_LABEL, "bande",
                             reform_path(receipts(lambda at: at.box[0]), applied),
                             reform_path(receipts(lambda at: at.box[1]), applied))
    else:
        base_primary = {y: -cost[y] / gdp[y] for y in years}
        behaviour = Slice(source="bande", label="Boîte θ du comportement", computed=False,
                          reason=ABSENT_BAND)
    reform = reform_path(base_primary, applied)
    delta = [r - b for r, b in zip(reform, ref, strict=True)]
    delta_primary = {y: base_primary[y] + (dict(zip(years, applied.balance, strict=True))[y]
                                           if applied else 0.0) for y in years}
    eventail = (envelope(EVENTAIL_LABEL, "eventail", reform_path(base_primary, feedback[0.0]),
                         reform_path(base_primary, feedback[1.0]))
                if applied else Slice(source="eventail", label="Rétroaction macro",
                                      computed=False, reason=feedback_reason))

    decomposition = Decomposition(
        years=tuple(years), central=tuple(reform), spending_name=spending.name,
        slices=(
            behaviour,
            eventail,
            Slice(source="scenario", label="Grille de scénarios", computed=False,
                  reason=ABSENT_GRID),
        ))
    conventions = [RECEIPTS_CONVENTION, *rate_conventions]
    if costs.behavioural is not None:
        conventions.append(BOX_CONVENTION)
    if applied:
        conventions.extend(applied.conventions)
        if persistence is not None and len(years) > retroaction.MAX_HORIZON:
            conventions.append(f"Au-delà de trois ans : "
                               f"{retroaction.PERSISTENCE_LABELS[persistence]}.")
    if carried:
        conventions.append(CARRY_LABEL)
    if applied:
        table = {**table, MACRO_ROW: applied.theta}
        closed = dict(CLOSED)
        absent = {} if not applied.uncovered else {
            "rétroaction, instruments non couverts": " ; ".join(
                f"{k} : {v}" for k, v in sorted(applied.uncovered.items()))}
    else:
        closed = {**CLOSED, **dict.fromkeys(MACRO_CHANNELS, feedback_reason)}
        absent = {"rétroaction": feedback_reason}
    if costs.behavioural is None:
        absent.update({"bande": ABSENT_BAND,
                       "θ": THETA_UNREAD if not applied else THETA_MACRO_ONLY})
    return Trajectoire(
        years=tuple(years), reference=tuple(ref), reform=tuple(reform),
        delta=tuple(delta),
        reference_primary=tuple(y.primary_balance for y in reference),
        delta_primary=tuple(delta_primary[y] for y in years),
        priced_years=tuple(sorted(costs.by_year)), carried_years=carried,
        decomposition=decomposition, spending_name=spending.name,
        growth_name=growth.name, rate_name=rate.name, conventions=tuple(conventions),
        delta_mechanical=tuple(mechanical), theta=table,
        open_rows=tuple(sorted([*(k for k, p in store.parameters.items() if p.is_open),
                                *((MACRO_ROW,) if applied else ())])),
        theta_applied=costs.behavioural is not None or applied is not None,
        gdp_gap=applied.gdp_gap if applied else None,
        feedback_primary=applied.balance if applied else None,
        persistence=persistence if applied else None,
        closed=closed, absent=absent,
    )
