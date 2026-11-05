"""Phase 9 M3 §4 — the GDP → receipts loop, from Mésange's primary-balance row (D-218).

D-059 refused this loop for want of a source: the elasticity row had five defects, two of
them invented numbers. M0 found a better candidate inside the model the multipliers
already come from (D-214). Each Mésange variant prints the primary balance of the APU,
in points of GDP, for the same simulated shock as its GDP row. The row CONTAINS the shock:
a one-point income-tax cut leaves the balance at −0,81 in the first year. What the
reform's activity gives back is the gap to the shock's cost AS THE CHAIN ALREADY COUNTS
IT — the engine's gross ex ante figure:

    rétroaction(h) = solde(h) + coût ex ante brut du choc   (points of GDP per variant)

One point for the labour taxes and the CSG. For VAT, the variant costs 1,18 points gross
for one net because the APU pay about 15 % of VAT (folio 112); D-218 measured the feedback
against 1,18, for a VAT cost counted gross. The VAT the engine prices since D-323 is the
households', which holds none of the APU's own: it is the variant's net point, and its
coefficient is 1 (`mesange.points_du_cout`, D-348).

WHAT IT MEASURES, named exactly. Not « the receipts' response »: the row is the induced
effect on the primary balance — receipts, unemployment benefits, the transfers Mésange
indexes on GDP and the spending indexed on prices (note 70 and tableau 10, folio 93).
And the PRIMARY balance: the interest on the extra debt is the chain's, at the scenario's
marginal rate.
GDP and balance come from one model under one set of simulation conditions, so nothing
here combines an elasticity estimated on past fluctuations with a multiplier measured
elsewhere.

FOUR CONDITIONS, from D-214, each a refusal rather than a footnote:

1. **Spending frozen in volume only.** During a variant Mésange's spending reacts in
   prices, and in volume « seules les recettes et les prestations chômage réagissent »
   (note 70). That is `gele_en_volume`. Under any other spending rule the loop is ABSENT,
   with its reason; correcting it by a formula would derive a number, not read one.
2. **Uniform fiscal variants only.** The targeted low-wage variant prints no balance row,
   and an instrument without one gets NO macro effect at all here — neither feedback nor
   GDP in the denominator — rather than half of a variant. It is listed, with why. The
   carbon tax is out too: its shock falls on energy volumes, so its gap holds the tax
   base shrinking as energy use falls, which is not an effect of activity (folio 121).
3. **A named persistence past three years.** The horizons 1 to 3 are read as printed.
   Beyond, a named PERSISTENCE scenario decides, and none is the default: « lue » reads
   Mésange's own columns at 5 and 10 years, under its central specification (wage
   setting), and interpolates linearly between the horizons it prints (D-336, decision
   1) — 4 between 3 and 5, 6 to 9 between 5 and 10; « eteint » extinguishes the effect
   after three years, « tenu » holds it at its third-year level. The two last stay as
   sensitivities. A path past three years without one is refused. The long-term column
   stays refused (D-055): 1,73 under wage setting, 0,25 under a Phillips curve. Which
   horizons are read is the store's `usable_horizons`, never a constant here.
4. **The reform's prices held constant in g.** No table prints a GDP deflator.

θ OF THE MULTIPLIER. The multiplier at θ is the Mésange centre ∓ one IMK standard
deviation, floored at zero (`theta.multiplier_at`, D-336 decision 2). The feedback
follows it PROPORTIONALLY, the assumption D-059 already makes for jobs. M0 measured how
far that is from true: the ratio of feedback to GDP effect runs from 0,46 (income tax,
year one) to 1,40 (employer contributions, year one). Named in the conventions, not
hidden. And it is bounded by the shock's gross cost: a tax cut does not finance itself
past 100 %, which Mésange calls « erroné » (folio 108, D-336 decision 2).

SUPERPOSITION. Mésange is linear and its variants are permanent shocks. An impulse that
changes from one year to the next is therefore the sum of permanent shocks started in
successive years, each read at its own horizon. With the fast version's carried years the
impulse is constant in points of GDP, and only the first shock exists.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from impots.macro import mesange
from impots.macro.fan import MULTIPLIER_FAMILY, _require
from impots.macro.store import Store, TableParameter
from impots.predictif.theta import ThetaError, multiplier_at

#: The one spending rule under which Mésange's balance row can be read as it is printed.
SPENDING_RULE = "gele_en_volume"
MULTIPLIER_TABLE = "multiplier_by_instrument"
BALANCE_TABLE = "primary_balance_by_instrument"

#: The persistence the verdict reads (D-336, decision 1); the two others are published
#: beside it as sensitivities.
READ = "lue"
Persistence = Literal["lue", "eteint", "tenu"]
PERSISTENCE_LABELS: dict[str, str] = {
    READ: ("Effet macro lu dans Mésange à 1, 2, 3, 5 et 10 ans (spécification centrale), "
           "interpolé linéairement entre eux"),
    "eteint": "Effet macro éteint après trois ans",
    "tenu": "Effet macro tenu au niveau de la troisième année",
}

PRICES_HELD = ("Prix de la réforme tenus constants dans la croissance nominale : Mésange "
               "n'imprime aucun déflateur du PIB (D-214).")
PROPORTIONAL = ("Rétroaction proportionnelle au multiplicateur quand θ macro le déplace : "
                "hypothèse de §4.1. Bonne pour l'IR et la CSG, médiocre pour les "
                "cotisations employeurs la première année, où la rétroaction vaut 1,40 "
                "fois l'effet sur le PIB contre 0,46 pour l'IR (D-214).")
EX_ANTE = ("Impulsion = chiffrage mécanique, ex ante comme les variantes de Mésange. Le "
           "comportement de la phase 3 ne la modifie pas, et son recoupement avec la "
           "réponse de Mésange n'est pas mesuré.")
LINEAR = ("Chocs superposés : Mésange est linéaire, et une impulsion qui change d'une "
          "année à l'autre y est la somme de chocs permanents décalés.")
NO_BALANCE_ROW = ("pas de ligne de solde dans Mésange (variante ciblée, encadré 14) : ni "
                  "rétroaction ni effet sur le PIB, plutôt que la moitié d'une variante")
NOT_FISCAL = ("choc de dépense en volume : son coût nominal suit les prix publics, et "
              "l'écart au coût ex ante d'un choc fiscal ne s'y lit pas")
CARBON = ("le choc porte sur les volumes d'énergie (folio 120) : l'écart du solde contient "
          "la baisse de l'assiette énergie, qui n'est pas un effet de l'activité")
GROSS_COST = ("Rétroaction mesurée contre le coût que la chaîne compte : un point par "
              "point de variante ; pour la TVA, le moteur chiffre celle des ménages, le point "
              "net de la variante, sans les 15 % que les APU se versent (folio 112, D-348).")
WHAT_IT_IS = ("La ligne de Mésange est l'effet induit sur le solde PRIMAIRE : recettes, "
              "prestations chômage, transferts indexés sur le PIB et dépenses indexées sur "
              "les prix (note 70, tableau 10). Les intérêts de la dette supplémentaire sont "
              "ceux de la chaîne.")
FIRST_YEAR = ("La colonne « 1 an » est lue comme une moyenne de la première année, ce que "
              "le document dit pour le tableau 12 et que la ligne de solde ne répète pas.")
BOUNDED = ("Multiplicateur borné à zéro, et rétroaction d'une impulsion bornée à son coût "
           "brut : une baisse d'impôt ne s'autofinance pas au-delà de 100 %, ce que Mésange "
           "dit « erroné » (folio 108, D-336).")
READ_SCOPE = ("Persistance « lue » : colonnes 5 et 10 ans de Mésange sous sa spécification "
              "centrale (« wage setting »), interpolées linéairement entre les horizons "
              "imprimés. Sous courbe de Phillips, les horizons longs tombent (cotisations "
              "employeurs : 1,73 contre 0,25 à long terme) ; la colonne de long terme reste "
              "refusée (D-055, D-336).")


class FeedbackError(ValueError):
    """The loop was asked for where Mésange's row cannot be read as printed."""


class NothingToRead(FeedbackError):
    """No instrument of the reform has a balance row: the loop is absent, not refused —
    a reform made only of transfers has no Mésange variant, and says so."""


def spending_reason(name: str) -> str:
    return (f"Rétroaction non appliquée sous « {name} » : pendant une variante, la dépense "
            f"de Mésange ne réagit qu'en prix (note 70, folio 93). Sous une autre règle, "
            f"une partie de l'amélioration du solde disparaîtrait, et la corriger par une "
            f"formule serait dériver un chiffre, pas le lire (D-214).")


#: Fiscal variants whose gap is not an effect of activity, and why.
NOT_ACTIVITY = {"taxe_carbone": CARBON}


def is_fiscal(instrument: str) -> bool:
    """A uniform fiscal variant whose balance gap the loop may read."""
    spec = mesange.VARIANTS.get(instrument)
    return (spec is not None and spec.basis == "ex_ante_fiscal" and not spec.targeted
            and instrument not in NOT_ACTIVITY)


def check_balance(balance: TableParameter) -> None:
    """GUARD (§4.6): the row includes the shock, and costs less than it.

    For a uniform fiscal variant, in the expansionary convention, the first-year balance
    must lie strictly between −1 (the shock's net cost, one point for every fiscal
    variant, nothing given back) and 0. A row read with the wrong sign, or one that
    excluded the shock, falls outside — and the loop would then add a point of GDP that
    nobody measured.
    """
    for instrument in sorted(balance.values):
        if not is_fiscal(instrument):
            continue
        first = balance.at(instrument, "1")
        if not -1.0 < first < 0.0:
            raise FeedbackError(
                f"solde primaire de « {instrument} » à un an : {first}, hors de ]−1 ; 0[. "
                f"La ligne doit contenir le choc (un point net) et en rendre une part ; "
                f"lue autrement, « solde + 1 » inventerait une rétroaction.")


@dataclass(frozen=True)
class Feedback:
    """The macro response of the reform, year by year, at one θ of the multiplier."""

    years: tuple[int, ...]
    gdp_gap: tuple[float, ...]
    """y_t: the reform's GDP over the reference's, minus one (0.002 = +0,2 %)."""
    balance: tuple[float, ...]
    """φ_t: the feedback on the primary balance, as a share of GDP; positive improves it."""
    theta: float
    persistence: str | None
    instruments: tuple[str, ...]
    uncovered: dict[str, str] = field(default_factory=dict)
    conventions: tuple[str, ...] = (WHAT_IT_IS, GROSS_COST, PRICES_HELD, PROPORTIONAL,
                                    EX_ANTE, LINEAR, FIRST_YEAR, BOUNDED)


def read_horizons(store: Store) -> tuple[int, ...]:
    """The horizons, in years, the loop reads as Mésange prints them: the numeric usable
    horizons of BOTH its rows. Read from the store, never written here (D-336)."""
    tables = (_require(store, MULTIPLIER_TABLE), _require(store, BALANCE_TABLE))
    common = set.intersection(*({int(h) for h in t.usable_horizons if str(h).isdigit()}
                                for t in tables))
    if 1 not in common:
        raise FeedbackError("aucun horizon d'un an lisible dans Mésange : la boucle n'a "
                            "pas de première année à lire")
    return tuple(sorted(common))


def short_horizon(store: Store) -> int:
    """The last horizon read without a gap from the first year on — three years in the
    shipped store. Past it, a persistence scenario must be named."""
    read = set(read_horizons(store))
    horizon = 1
    while horizon + 1 in read:
        horizon += 1
    return horizon


def max_horizon(store: Store | None = None) -> int:
    """`short_horizon` of the shipped macro store, unless one is given."""
    if store is None:
        from impots.macro import store as store_module

        store = store_module.load()
    return short_horizon(store)


def interpolated(table: TableParameter, instrument: str, horizon: int,
                 read: tuple[int, ...]) -> float:
    """The row at `horizon`, linear between the two horizons Mésange prints around it."""
    if horizon in read:
        return table.at(instrument, str(horizon))
    below = max(h for h in read if h < horizon)
    above = min(h for h in read if h > horizon)
    low, high = table.at(instrument, str(below)), table.at(instrument, str(above))
    return low + (horizon - below) / (above - below) * (high - low)


def read_horizon(horizon: int, persistence: str | None, read: tuple[int, ...],
                 short: int) -> int | None:
    """The horizon a persistence scenario reads at `horizon`; None when it reads nothing
    (« eteint » past the short horizon)."""
    if persistence == READ:
        if horizon > read[-1]:
            raise FeedbackError(
                f"horizon de {horizon} ans au-delà du dernier que Mésange imprime et que la "
                f"boucle lit ({read[-1]} ans) : le long terme reste refusé (D-055)")
        return horizon
    if horizon <= short:
        return horizon
    # `compute` refuses a path past the short horizon without a persistence scenario.
    assert persistence is not None
    return None if persistence == "eteint" else short


def covers(store: Store, instrument: str) -> bool:
    """Whether the loop reads `instrument`: a uniform fiscal variant with a balance row."""
    spec = mesange.VARIANTS.get(instrument)
    return (instrument not in NOT_ACTIVITY and spec is not None and not spec.targeted
            and is_fiscal(instrument)
            and instrument in _require(store, BALANCE_TABLE).values)


def replay_tables(store: Store, instruments: Sequence[str]) -> dict[str, Any]:
    """The numbers the loop reads for `instruments`, written out so that a report can be
    replayed without the store (D-336, decision 6, `predictif.rejouer`): the horizons
    read, the short one, and for each instrument the loop covers its GDP and balance rows
    at those horizons, its IMK standard deviation and its gross ex ante cost per point."""
    read = read_horizons(store)
    multipliers = _require(store, MULTIPLIER_TABLE)
    balance = _require(store, BALANCE_TABLE)
    dispersion = _require(store, "multiplier_dispersion")
    tables = {}
    for instrument in sorted(set(instruments)):
        if not covers(store, instrument):
            continue
        tables[instrument] = {
            "pib": {str(h): multipliers.at(instrument, str(h)) for h in read},
            "solde": {str(h): balance.at(instrument, str(h)) for h in read},
            "sd": dispersion.at(MULTIPLIER_FAMILY[instrument], "all"),
            "brut": mesange.points_du_cout(instrument),
        }
    return {"horizons": list(read), "court": short_horizon(store), "instruments": tables}


def _response(store: Store, instrument: str, horizon: int, theta: float,
              persistence: str | None) -> tuple[float, float]:
    """(GDP in % per variant, feedback in points of GDP per variant) at a horizon."""
    read = read_horizons(store)
    at = read_horizon(horizon, persistence, read, short_horizon(store))
    if at is None:
        return 0.0, 0.0
    multipliers = _require(store, MULTIPLIER_TABLE)
    balance = _require(store, BALANCE_TABLE)
    dispersion = _require(store, "multiplier_dispersion")
    centre = interpolated(multipliers, instrument, at, read)
    if centre == 0.0:
        raise FeedbackError(f"multiplicateur nul pour « {instrument} » à {at} an(s) : la "
                            f"proportion de la rétroaction serait indéfinie")
    family = MULTIPLIER_FAMILY.get(instrument)
    if family is None:
        raise FeedbackError(f"aucune famille de dispersion pour « {instrument} »")
    gdp = multiplier_at(centre, dispersion.at(family, "all"), theta)
    gross = mesange.points_du_cout(instrument)
    feedback = (interpolated(balance, instrument, at, read) + gross) * gdp / centre
    # Bounded by the shock's gross cost, `gross` points per variant point (D-336).
    return gdp, min(feedback, gross)


def compute(impulses: Mapping[int, Mapping[str, float]], gdp: Mapping[int, float],
            years: Sequence[int], *, store: Store, theta: float,
            persistence: str | None, spending_rule: str, spending_name: str = "",
            uncovered: Mapping[str, str] | None = None) -> Feedback:
    """The GDP gap and the balance feedback, every year of `years`, at θ.

    `impulses` are euros, EXPANSIONARY-POSITIVE, keyed by Mésange variant
    (`shocks.Impulse.by_instrument`), for every year of `years`. `uncovered` carries the
    deltas the shock builder could not map, with their reasons, so they travel to the
    result rather than vanish.
    """
    if spending_rule != SPENDING_RULE:
        raise FeedbackError(spending_reason(spending_name or spending_rule))
    if persistence is not None and persistence not in PERSISTENCE_LABELS:
        raise FeedbackError(f"persistance « {persistence} » inconnue ; seules "
                            f"{sorted(PERSISTENCE_LABELS)} existent")
    if len(years) > short_horizon(store) and persistence is None:
        # Decided on the horizon, not on the impulse's shape: a permanent reform's path
        # past year three depends on persistence whatever year its shocks start.
        raise FeedbackError(
            f"trajectoire de {len(years)} ans sans scénario de persistance : au-delà de "
            f"{short_horizon(store)} ans, il faut nommer « lue », « eteint » ou « tenu » "
            f"(D-055, D-336). Aucun n'est le défaut.")
    if not 0.0 <= theta <= 1.0:
        raise ThetaError(f"θ du multiplicateur = {theta}, hors de [0 ; 1] : refusé, pas écrêté")
    if sorted(impulses) != sorted(years):
        raise FeedbackError(f"impulsions pour {sorted(impulses)}, années {list(years)} : une "
                            f"année sans impulsion serait une année sans choc, en silence")
    check_balance(_require(store, BALANCE_TABLE))

    instruments = sorted({i for year in impulses.values() for i, v in year.items() if v})
    missing = dict(uncovered or {})
    covered = []
    for instrument in instruments:
        spec = mesange.VARIANTS.get(instrument)
        if instrument in NOT_ACTIVITY:
            missing[instrument] = NOT_ACTIVITY[instrument]
        elif spec is not None and spec.targeted:
            missing[instrument] = NO_BALANCE_ROW
        elif not is_fiscal(instrument):
            missing[instrument] = NOT_FISCAL
        elif instrument not in _require(store, BALANCE_TABLE).values:
            missing[instrument] = NO_BALANCE_ROW
        else:
            covered.append(instrument)
    if not covered:
        raise NothingToRead(
            "aucun instrument de cette réforme n'a de ligne de solde dans Mésange : il n'y "
            "a pas de rétroaction à lire, et une rétroaction nulle se lirait comme un "
            f"constat. Non couverts : {missing or 'aucun instrument mappé'}")

    # Variant units: the engine's cost per variant point (`mesange.points_du_cout`), as
    # `fan.run` divides it, and the feedback is measured against the same (`_response`).
    units = {i: [impulses[y].get(i, 0.0) * 100.0
                 / (mesange.points_du_cout(i) * gdp[y]) for y in years]
             for i in covered}
    gap, balance = [], []
    for k in range(len(years)):
        y_k = phi_k = 0.0
        for instrument in covered:
            path = units[instrument]
            for j in range(k + 1):
                step = path[j] - (path[j - 1] if j else 0.0)
                if step:
                    m, f = _response(store, instrument, k - j + 1, theta, persistence)
                    y_k += step * m / 100.0
                    phi_k += step * f / 100.0
        gap.append(y_k)
        balance.append(phi_k)
    conventions = Feedback.conventions + ((READ_SCOPE,) if persistence == READ else ())
    return Feedback(years=tuple(years), gdp_gap=tuple(gap), balance=tuple(balance),
                    theta=float(theta), persistence=persistence,
                    instruments=tuple(covered), uncovered=missing, conventions=conventions)
